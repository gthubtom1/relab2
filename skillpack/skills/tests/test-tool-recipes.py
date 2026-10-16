#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test-tool-recipes.py —— 把「工具该怎么调」**真的跑一遍**。

为什么有这个门（2026-10-16）：
    仓库此前 37 道门全是"文件里有没有这些字"的文本门。`TOOLS.md` 写着 `diec -d -e -j`，
    而 `relab2-tools-mcp.py` 的 `triage_target` 写的是 `diec --extended` —— 两边从没对过账。
    错参数的后果不是报错，是**进程永不退出**：实测一条 triage 卡满 240 s 超时、stdout 0 字节，
    还留下 ghost 进程。没有任何门能发现它，因为**没有任何门真的执行过工具链路**。

    本门读 `skills/config/tool-recipes.json`（唯一事实源），对每条配方：
      · 工具不在本机 → SKIP（打印出来，不算过也不是错 —— 换机后没装的工具不该让门红）
      · 工具在      → **真跑**，断言：在 timeout 内返回 + 退出码在允许集 + 有最小输出量
    所以它同时是「换机验收」的一部分：新机器跑一遍就知道**哪些刀真的能挥**，
    而不是只知道"路径解析成功了"。

用法：
    python skills/tests/test-tool-recipes.py
    python skills/tests/test-tool-recipes.py --only triage.format
    python skills/tests/test-tool-recipes.py --list
退出码：0 全过（含 SKIP）；1 有配方真跑失败。

留痕（2026-10-16 补）：
    每轮结束都把**逐条结果**写到 %LOCALAPPDATA%\\reverse-skill\\tools-mcp\\recipes-last.json，
    并把路径打在屏幕上。此前一道门红了只留一行 `fail=1` —— 事后没人能回答"红的是哪条"，
    只能整轮重跑靠猜。红门必须留下可查的现场。
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import struct
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILLS = HERE.parent                      # skillpack/skills
REPO = SKILLS.parent.parent               # 仓库根
RECIPES = SKILLS / "config" / "tool-recipes.json"
TOOLS_MCP = SKILLS / "scripts" / "relab2-tools-mcp.py"

NEW_PROCESS_GROUP = 0x00000200 if os.name == "nt" else 0


def _load_ctx():
    """复用工具桥的工具解析链（探测层 → 能力索引），避免这里再写一套路径规则。"""
    spec = importlib.util.spec_from_file_location("relab2_tools_mcp", TOOLS_MCP)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    ns = argparse.Namespace(skill_root=str(REPO), tool_root=os.environ.get("REVERSE_TOOL_ROOT", ""))
    return mod.Ctx(ns)


def make_pcap(path: Path) -> Path:
    """现场造一个最小 pcap（一条 TCP SYN），不依赖 scapy、不依赖外部样本。"""
    def cksum(data: bytes) -> int:
        if len(data) % 2:
            data += b"\x00"
        s = sum(struct.unpack("!%dH" % (len(data) // 2), data))
        while s >> 16:
            s = (s & 0xFFFF) + (s >> 16)
        return ~s & 0xFFFF

    tcp = struct.pack("!HHIIBBHHH", 51515, 80, 0, 0, (5 << 4), 0x02, 64240, 0, 0)
    ip = struct.pack("!BBHHHBBH4s4s", 0x45, 0, 20 + len(tcp), 0x1234, 0x4000, 64, 6, 0,
                     bytes([10, 0, 0, 1]), bytes([10, 0, 0, 2]))
    ip = ip[:10] + struct.pack("!H", cksum(ip)) + ip[12:]
    eth = b"\x02\x00\x00\x00\x00\x02" + b"\x02\x00\x00\x00\x00\x01" + b"\x08\x00"
    frame = eth + ip + tcp
    with path.open("wb") as f:
        f.write(struct.pack("<IHHiIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 1))
        f.write(struct.pack("<IIII", 0, 0, len(frame), len(frame)))
        f.write(frame)
    return path


def make_rule(path: Path) -> Path:
    """现场造一条最小 YARA 规则（匹配目标文件头的 `MZ`），不依赖外部规则集。"""
    path.write_text('rule rel2_smoke {\n  strings: $a = "MZ"\n  condition: $a\n}\n',
                    encoding="utf-8")
    return path


def run_recipe(ctx, rec: dict, samples: dict) -> dict:
    """真跑一条配方。返回 {status, detail, dur}，status ∈ ok/skip/fail。"""
    want = rec["tool"]
    cmd, via, why = ctx.resolve(want)
    if not cmd:
        return {"status": "skip", "detail": f"本机没有 {want}（{why}）", "dur": 0}
    argv = []
    for a in rec.get("args", []):
        if a in samples:
            p = samples[a]
            if not p:
                return {"status": "skip", "detail": f"样本 {a} 在本机找不到", "dur": 0}
            argv.append(str(p))
        else:
            argv.append(a)
    t = int(rec.get("timeout_s", 120))
    t0 = time.time()
    try:
        p = subprocess.Popen([cmd, *argv], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             stdin=subprocess.DEVNULL, creationflags=NEW_PROCESS_GROUP)
    except OSError as e:
        return {"status": "fail", "detail": f"起不来：{type(e).__name__}: {e}", "dur": 0}
    try:
        out, err = p.communicate(timeout=t)
        dur = round(time.time() - t0, 1)
    except subprocess.TimeoutExpired:
        # 杀整棵树 —— 孙进程也要死，否则会像 diec 那次一样留下 ghost 进程
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True, timeout=20)
        else:
            try:
                p.kill()
            except OSError:
                pass
        try:
            p.communicate(timeout=15)
        except Exception:  # noqa: BLE001
            pass
        return {"status": "fail",
                "detail": f"★ HANG：{t}s 内没返回（这就是『参数写错/等输入』的形态）", "dur": dur_elapsed(t0)}
    allowed = rec.get("expect_exit", [0])
    if p.returncode not in allowed:
        head = (err or out)[:100].decode("utf-8", "replace").replace("\n", " ")
        return {"status": "fail", "detail": f"退出码 {p.returncode}（允许 {allowed}）· {head}", "dur": dur}
    # ★ 2026-10-16 逐工具实测修正：`java` / `ncat` / `nuclei` 的版本信息**走 stderr**
    #   （实测 stdout 0B、stderr 有内容）—— 旧判据只看 stdout，把它们误判成"没真干活"。
    #   现在：输出量按两流之和计；内容断言用合并文本；配方可用 `expect_stream` 收窄。
    stream = rec.get("expect_stream", "any")
    if stream == "stdout":
        shown = out
    elif stream == "stderr":
        shown = err
    else:
        shown = out + b"\n" + err
    need = int(rec.get("min_stdout", 0))
    if len(shown) < need:
        return {"status": "fail",
                "detail": f"输出只有 {len(shown)}B（要求 ≥{need}B，stream={stream}）—— 输出为空通常等于没真干活",
                "dur": dur}
    # ★ 2026-10-16：「有输出」不等于「输出是对的」。主人原话：「通了后，要保证是**正确的**，
    #   就像之前你工具命令错、导致 powershell 卡死。」所以配方可以声明 `expect_regex`：
    #   输出必须匹配它，否则这条调用形态即使 rc=0 也算**没真干活**。
    exp = rec.get("expect_regex")
    if exp:
        text = shown.decode("utf-8", "replace")
        if not re.search(exp, text, re.I | re.M):
            head = text.strip().splitlines()[0][:80] if text.strip() else "（空）"
            return {"status": "fail",
                    "detail": f"输出不匹配 expect_regex `{exp}`（{rec.get('expect_why','')}）· 首行: {head}",
                    "dur": dur}
    return {"status": "ok",
            "detail": f"via={via} rc={p.returncode} {dur}s out={len(out)}B/err={len(err)}B"
                      + (f" · 输出匹配 `{exp}`" if exp else ""), "dur": dur}


def dur_elapsed(t0: float) -> float:
    return round(time.time() - t0, 1)


def write_artifact(ctx, rows, n_ok: int, n_skip: int, n_fail: int):
    """★ 2026-10-16：把这一轮的逐条结果落盘（仓库外，不脏工作树）。

    起因：一次 `ok=45 skip=0 fail=1` 事后**查不出红的是哪条** —— 门只在屏幕上刷一遍，
    没有留痕，也没有任何 artifact 能回放。红门不可诊断 = 红门等于噪声。
    这里落 JSON：谁红、谁跳、rc 多少、输出多大、匹配了哪条正则，全都留着。
    写不进去（无权限等）不影响门本身：门的结果不依赖留痕。"""
    import json as _json
    try:
        state = getattr(ctx, "state", None) or Path(tempfile.gettempdir())
        out = Path(state) / "recipes-last.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
            "host": os.environ.get("COMPUTERNAME", ""),
            "recipes_file": str(RECIPES),
            "totals": {"ok": n_ok, "skip": n_skip, "fail": n_fail},
            "fail_ids": [r["id"] for r, res in rows if res["status"] == "fail"],
            "skip_ids": [r["id"] for r, res in rows if res["status"] == "skip"],
            "results": [{"id": r["id"], "tool": r["tool"], "args": r.get("args"), **res}
                        for r, res in rows],
        }
        out.write_text(_json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        return out
    except OSError:
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", default="", help="只跑某条配方 id")
    ap.add_argument("--list", action="store_true", help="只列出配方")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    data = json.loads(RECIPES.read_text(encoding="utf-8"))
    recipes = data["recipes"]
    if a.only:
        recipes = [r for r in recipes if r["id"] == a.only]
    if a.list or not recipes:
        for r in recipes:
            print(f"  {r['id']:<22} {r['tool']:<8} {' '.join(r['args'])}")
        return 0

    tmp = Path(tempfile.mkdtemp(prefix="rel2-recipes-"))
    pe = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "notepad.exe"
    samples = {"{target}": pe if pe.is_file() else None,
               "{pe}": pe if pe.is_file() else None,
               "{anyfile}": REPO / "skillpack" / "VERSION",
               "{pcap}": make_pcap(tmp / "syn.pcap"),
               "{rule}": make_rule(tmp / "rel2-smoke.yar")}

    ctx = _load_ctx()
    rows, n_fail, n_ok, n_skip = [], 0, 0, 0
    for r in recipes:
        res = run_recipe(ctx, r, samples)
        rows.append((r, res))
        if res["status"] == "ok":
            n_ok += 1
        elif res["status"] == "skip":
            n_skip += 1
        else:
            n_fail += 1

    if a.json:
        print(json.dumps([{"id": r["id"], **res} for r, res in rows], ensure_ascii=False, indent=2))
    else:
        for r, res in rows:
            mark = {"ok": "PASS", "skip": "SKIP", "fail": "FAIL"}[res["status"]]
            print(f"  [{mark}] {r['id']:<22} {r['tool']:<8} {res['detail']}")
            if res["status"] == "fail" and r.get("note"):
                print(f"         配方备注：{r['note']}")
        print()
        print(f"test-tool-recipes: ok={n_ok} skip={n_skip} fail={n_fail}"
              f"（配方来自 skills/config/tool-recipes.json）")
        if n_skip:
            print("  SKIP = 本机没装这件工具。换机后装上了就应当变成 PASS —— 这是『刀真的能挥』的判据，")
            print("         比 doctor 的『路径解析成功』强一层。")
    art = write_artifact(ctx, rows, n_ok, n_skip, n_fail)
    if art:
        tail = f"；红的配方：{', '.join(r['id'] for r, res in rows if res['status'] == 'fail')}" if n_fail else ""
        print(f"逐条结果已落盘：{art}{tail}")
    return 1 if n_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
