#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""verify-tool-identity.py —— ⑥-2 门2 的可执行判据：核心工具「解析得到 + 跑得起来 + 身份对得上」。

为什么要有这道门（2026-10-17 实测）
------------------------------------
`docs/ASSESS-全量验收任务书-2026-10-17.md` 的门2 原文是：

    Resolve-ReverseToolSpec ×N → Available=True 且 Via≠scan，且**实跑 `--version`** 出版本号

逐条实测后，这条判据**本身是错的**（不是工具坏）——拿同一个 `--version` 通吃七个工具：

    · `diec --version`  → **包装器坑，不是开关错**：探测层解析到的 `D:\Tools\cli\diec.cmd`
                          对 help/version 形态一律不返回（libpng warning 刷屏、stdout 0 字节、
                          20~25 s 仍在跑，三次独立复现）；**同一台机器上**裸
                          `pack\die\diec.exe --version` → `die 3.11`，0.06~0.13 s。
                          → 该修的是**探测层**（deny 掉那个 .cmd + 给 `diec` 补别名），不是判据；
                            修完 `diec --version` 就是可用的版本探针
    · `r2 --version`    → rc=1 `ERROR: Missing file to open`（radare2 只认 `-v`）
    · `idat --version`  → rc=2 `Failed to initialize IDA as library`（PySide6 在非 GUI 会话下加载失败；
                          IDA 自己的 `-h` 是正常形态，rc=2 + 开关表）
    · `ghidra` / `x64dbg` → 探测层给的根本不是可执行本体（前者 GUI 启动器 `ghidraRun.bat`、
                          后者 MCP 启动器 `start-x64dbg-mcp.ps1`）
    · `python`          → Via=scan-ambiguous，选中工具自带 venv `runtime\angr-mcp-venv`（不是系统 python）

所以「出版本号」不能一个开关通吃：**每个工具要用它自己的、文档化（或实测选定）的探针**。
逐工具依据：

    依据 A  references/env-selfcheck.md §5.3   `r2 -v` / `upx --version`
    依据 B  config/tool-recipes.json           tool.upx / tool.idat(`-h`, rc 期望 2)
                                               / tool.ghidra_headless(`--help`, rc 期望 1)
                                               / tool.radare2(`-v`)
    依据 C  config/tool-recipes.json 的 _no_recipe.diec-version-probe（2026-10-17 记账行）
                                               ★ 本门实测**更正**了它的归因：挂的是 `.cmd` **包装器**，
                                                 不是 `--version` 这个开关（见上面逐条实测）；
                                                 该行「要版本一律用 `diec -h`」在包装器形态下同样挂
    依据 D  本门实测选定：`diec` 用 `--version`（裸 exe 0.06 s → `die 3.11`）；
                                               `r2` 用 `-v`（`--version` 报 Missing file）；
                                               `x64dbg` 用 `-help`（它没有版本开关，`-v` 答 unknown argument）

判据（每一行三条，缺一即该行判红）
----------------------------------
    ① `Available=True`
    ② `Via ∉ {scan, scan-ambiguous}`      ← 探测层自述「最低可信度、须实跑确认身份」的两级
    ③ 探针在 `--timeout` 内返回，退出码在 `expect_exit` 内，且 stdout 命中 `expect_regex`

三条不变量（都是踩过的坑，不要"顺手优化"掉）
--------------------------------------------
· **分母自证**：分母 = 探针表长度，由脚本自己打印；模块顶层断言表非空（0 行成功的门 = 假绿）。
· **绝不 `capture_output=True`**：探针进程可能拉孙进程（ghidra 的 java、x64dbg 的插件 JVM），
  孙进程继承管道写端 → 父进程被 kill 后管道仍在 → `communicate()` 等不到 EOF → **永不超时**
  （`docs/KNOWN-BOUNDARIES.md` 第 18 条的现场：`--timeout 600` 实测挂 2104 秒）。
  本门一律：输出落临时文件 + `Popen` + `wait(timeout)` + 超时 `taskkill /F /T`。
· **无窗口**：`CREATE_NO_WINDOW`（探针一律不弹窗口）；GUI 型 id（`ghidra` 不许解析到
  `ghidraRun.bat`、`x64dbg` 不许解析到 MCP 启动器）由 ② 之前的**本体检查**另判一条。

反例控制组 `--negctl`：① 查一个必然不存在的 id ② 给一个必然错参数的探针
→ 两者都必须被判红，否则本门自己失败（没有控制组的门不算门）。

用法
----
    python skillpack/skills/tests/verify-tool-identity.py
    python skillpack/skills/tests/verify-tool-identity.py --ids diec,r2 --json out.json
    python skillpack/skills/tests/verify-tool-identity.py --negctl
退出码：0 全绿 / 20 有红（含分母为 0）/ 21 控制组没抓住反例 / 22 本机没有 PowerShell（无法测量）

★ 本门是**本机门**（判据是「这台机器上这 7 把刀能解析、能跑、身份对得上」），
  不要注册进 CI 的 runner 集合 —— 云端 runner 上没有这些商业工具，注册进去只会得到
  一条与代码无关的红。它在验收里的位置是 ASSESS 任务书的「门2」。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent          # skillpack/skills/tests
SKILLS = HERE.parent                            # skillpack/skills
REPO = SKILLS.parent.parent                     # 仓库根
BOOTSTRAP_REL = Path("scripts") / "lib" / "Bootstrap.ps1"

# 探针进程控制标志（Windows）。POSIX 上为 0。
CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0
NEW_PROCESS_GROUP = 0x00000200 if os.name == "nt" else 0

# ② Via 判据：这两级是探测层自述的「最低可信度」，不予采信
LOW_TRUST_VIA = {"scan", "scan-ambiguous"}


class Row:
    """一行判据：一个工具 id + 它自己的探针 + 该探针的预期身份证据。"""

    __slots__ = ("id", "argv", "expect_exit", "expect_regex", "identity", "source")

    def __init__(self, id, argv, expect_exit, expect_regex, identity, source):
        self.id = id
        self.argv = argv
        self.expect_exit = expect_exit          # list[int] | None(=任何退出码都行)
        self.expect_regex = expect_regex        # 版本号 / 身份串
        self.identity = identity                # 探针拿到的"身份证据"是什么
        self.source = source                    # 依据出处（文档/配方/实测）


# 探针表（分母 = 本表长度）。argv 里的 {sample} 由脚本现造一个 64 字节样本填充。
PROBES: list[Row] = [
    Row("diec", ["--version"], [0], r"^die \d+\.\d+",
        "`die 3.11`（DIE 命令行版自己的版本行）",
        "实测选定（2026-10-17，依据 D）：裸 diec.exe `--version` 0.06~0.13 s → `die 3.11`；"
        "`--help` 亦可（0.03 s 打印 `Detect It Easy v3.11`）。★ 经 `cli\\diec.cmd` 包装时"
        "**两种形态都不返回**（libpng 刷屏 + 0 字节 stdout），已由 _map.json 的 deny "
        "（`*cli\\diec.cmd`）+ aliases.diec 让本 id 落到裸 exe"),
    Row("r2", ["-v"], [0], r"^radare2 \d+\.\d+",
        "`radare2 6.2.4 +1 abi:152 @ windows-x86_64`",
        "依据 A（env-selfcheck §5.3 `r2 -v`）+ 依据 B（tool.radare2 `-v`）；"
        "tool-recipes:44 明写 r2 **没有** `--version`（那样报 Missing file）"),
    Row("upx", ["--version"], [0], r"^upx \d",
        "`upx 5.2.1`",
        "依据 B（tool.upx）"),
    Row("idat", ["-h"], [2], r"Command line switches",
        "命令开关表（IDA 自己打印的 usage，rc=2 是它的正常形态）",
        "依据 B（tool.idat：`-h`，expect_exit=[2]，regex `Command line switches|IDA`）"),
    Row("ghidra", ["--help"], [1], r"Headless Analyzer Usage",
        "`Headless Analyzer Usage: analyzeHeadless`",
        "依据 B（tool.ghidra_headless；`ghidra` 必须解析到同一个 analyzeHeadless.bat，"
        "默认 map 与 _no_recipe.ghidra 都写明 GUI 的 ghidraRun.bat 不能进 bash）"),
    Row("x64dbg", ["-help"], [0], r"(?i)x64dbg",
        "headless.exe 自己打印的 Help 块（含 `x64dbg` 与 `-help  Show this message`）",
        "实测选定：headless.exe 没有版本开关（`-v`/`--version` 都答 `unknown argument`），"
        "它自己声明的帮助开关是 `-help`；默认 map 的 x64dbg→headless.exe 是唯一合法形态"),
    Row("python", ["--version"], [0], r"^Python \d+\.\d+",
        "`Python 3.14.3`",
        "依据 A（env-selfcheck §5「Python 工具链在哪个解释器里」）；工具自带 venv 的 python 不是系统 python"),
]

# 本体检查：这些 id 解析到下面这些"启动器"形态时，②/③ 再绿也不算 —— 它根本不是可执行本体。
LAUNCHER_TRAPS = {
    "ghidra": [
        (r"(?i)ghidraRun\.bat$", "GUI 启动器 ghidraRun.bat（弹窗等输入、零 stdout、进程不退）"),
        (r"(?i)ghidraRun$", "无扩展名的 sh 包装（Windows 下不可执行）"),
    ],
    "x64dbg": [
        (r"(?i)start-x64dbg-mcp\.ps1$", "MCP 启动器（项目自己的脚本，不是调试器本体）"),
        (r"(?i)x64dbg\.exe$", "GUI 版 x64dbg.exe（弹窗等输入、零 stdout、进程不退）"),
        (r"(?i)x96dbg\.exe$", "启动选择器 GUI x96dbg.exe"),
    ],
    "diec": [(r"(?i)\\die\.exe$", "GUI 版 die.exe")],
    "idat": [(r"(?i)\\ida\.exe$", "GUI 版 ida.exe")],
    "python": [(r"(?i)\\angr-mcp-venv\\", "工具自带 venv（environment-init §4.3：不要当系统工具用）")],
}


def log(msg=""):
    print(msg, flush=True)


def find_bootstrap() -> Path | None:
    cands = []
    env_root = os.environ.get("REVERSE_SKILL_ROOT")
    if env_root:
        for c in (Path(env_root), Path(env_root) / "skills", Path(env_root) / "skillpack" / "skills"):
            cands.append(c / BOOTSTRAP_REL)
    cands.append(SKILLS / BOOTSTRAP_REL)
    for c in cands:
        if c.is_file():
            return c
    return None


def find_powershell() -> str | None:
    """宿主优先 5.1（本仓主宿主），退 pwsh。"""
    for exe in ("powershell", "pwsh"):
        p = shutil.which(exe)
        if p:
            return p
    return None


PS_RESOLVE = r"""[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false)
$ErrorActionPreference='Continue'
. "{bootstrap}"
$ids = @({ids})
$out = @()
foreach ($id in $ids) {{
  $r = $null
  try {{ $r = Resolve-ReverseToolSpec -Name $id -ErrorAction Stop }} catch {{ }}
  if ($r -and $r.Available) {{
    $out += [pscustomobject]@{{
      id=$id; ok=$true; via=("" + $r.Via); cmd=("" + $r.Command); hint=("" + $r.VersionHint)
    }}
  }} else {{
    $out += [pscustomobject]@{{ id=$id; ok=$false; via=("" + $r.Via); cmd=''; hint='' }}
  }}
}}
ConvertTo-Json -InputObject @($out) -Compress
"""


def resolve_all(ps: str, bootstrap: Path, ids: list[str], timeout: int) -> dict:
    script = PS_RESOLVE.format(
        bootstrap=str(bootstrap).replace("\\", "\\\\"),
        ids=",".join("'%s'" % i for i in ids),
    )
    t0 = time.time()
    try:
        p = subprocess.run([ps, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                           capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"_error": f"探测层调用失败：{type(e).__name__}", "_elapsed": round(time.time() - t0, 2)}
    out = (p.stdout or "").strip()
    try:
        data = json.loads(out or "[]")
    except ValueError:
        return {"_error": "探测层输出不是 JSON", "_raw": out[:400], "_rc": p.returncode,
                "_stderr": (p.stderr or "")[:400]}
    if isinstance(data, dict):
        data = [data]
    return {"_items": data, "_elapsed": round(time.time() - t0, 2), "_rc": p.returncode}


def run_probe(exe: str, argv: list[str], timeout: int, cwd: str) -> dict:
    """实跑探针。

    输出**落临时文件**（不用管道：孙进程继承写端会让 communicate() 永不返回）；
    超时则 `taskkill /F /T` 杀**整棵树**（ghidra 会起 java，x64dbg 会起插件 JVM）。
    """
    out_p = os.path.join(cwd, "probe-out.txt")
    err_p = os.path.join(cwd, "probe-err.txt")
    t0 = time.time()
    with open(out_p, "wb") as fo, open(err_p, "wb") as fe:
        try:
            proc = subprocess.Popen(
                [exe] + argv, stdout=fo, stderr=fe, stdin=subprocess.DEVNULL, cwd=cwd,
                creationflags=CREATE_NO_WINDOW | NEW_PROCESS_GROUP)
        except OSError as e:
            return {"rc": None, "timeout": False, "exception": repr(e),
                    "stdout": "", "stderr": "", "elapsed_s": round(time.time() - t0, 2)}
        try:
            proc.wait(timeout=timeout)
            timed_out = False
        except subprocess.TimeoutExpired:
            timed_out = True
            if os.name == "nt":
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                               capture_output=True, creationflags=CREATE_NO_WINDOW)
            else:
                proc.kill()
            try:
                proc.wait(timeout=10)
            except Exception:
                pass
        rc = proc.returncode

    def _read(path):
        try:
            with open(path, "rb") as f:
                return f.read().decode("utf-8", "replace")
        except OSError:
            return ""

    return {"rc": rc, "timeout": timed_out, "stdout": _read(out_p), "stderr": _read(err_p),
            "elapsed_s": round(time.time() - t0, 2)}


def make_sample(cwd: str) -> str:
    """造一个 64 字节最小样本（MZ 头）。`{sample}` 占位符要用。"""
    p = os.path.join(cwd, "sample.bin")
    with open(p, "wb") as f:
        f.write(b"MZ" + b"\x00" * 62)
    return p


def judge(row: Row, spec: dict | None, probe: dict | None) -> dict:
    """三条判据。返回一行的完整结果（含每条的 pass/fail 与证据）。"""
    r = {"id": row.id, "probe_argv": row.argv, "expect_exit": row.expect_exit,
         "expect_regex": row.expect_regex, "identity": row.identity, "source": row.source}
    avail = bool(spec and spec.get("ok"))
    via = (spec or {}).get("via") or ""
    cmd = (spec or {}).get("cmd") or ""
    r["available"] = avail
    r["via"] = via
    r["command"] = cmd
    r["cond_available"] = avail
    r["cond_via"] = bool(via) and via not in LOW_TRUST_VIA

    trap = None
    for pat, why in LAUNCHER_TRAPS.get(row.id, []):
        if cmd and re.search(pat, cmd):
            trap = why
            break
    r["cond_not_launcher"] = trap is None
    r["launcher_trap"] = trap

    if probe is None:
        r["rc"] = None
        r["stdout_first"] = []
        r["stderr_first"] = []
        r["cond_probe"] = False
        r["probe_note"] = "未实跑（前两条已红或无可执行本体）"
    else:
        rc = probe.get("rc")
        first = [l for l in (probe.get("stdout") or "").splitlines() if l.strip()]
        r["rc"] = rc
        r["timeout"] = probe.get("timeout")
        r["elapsed_s"] = probe.get("elapsed_s")
        r["stdout_first"] = first[:3]
        r["stderr_first"] = [l for l in (probe.get("stderr") or "").splitlines()
                             if l.strip() and "libpng warning" not in l][:3]
        r["stdout_bytes"] = len(probe.get("stdout") or "")
        exit_ok = row.expect_exit is None or rc in row.expect_exit
        rx_ok = bool(re.search(row.expect_regex, probe.get("stdout") or "", re.M))
        r["cond_probe"] = bool(exit_ok and rx_ok and not probe.get("timeout"))
        if probe.get("timeout"):
            r["probe_note"] = f"探针超时（>{r.get('elapsed_s')}s 未返回）"
        elif not exit_ok:
            r["probe_note"] = f"退出码 {rc} 不在 {row.expect_exit}"
        elif not rx_ok:
            r["probe_note"] = f"stdout 未命中 /{row.expect_regex}/"
        else:
            r["probe_note"] = "ok"

    r["verdict"] = "绿" if (r["cond_available"] and r["cond_via"]
                            and r["cond_not_launcher"] and r["cond_probe"]) else "红"
    reasons = []
    if not r["cond_available"]:
        reasons.append("Available=False（探测层四级全失败）")
    if not r["cond_via"]:
        reasons.append("Via=%s 属最低可信度（%s）" % (via or "n/a", ",".join(sorted(LOW_TRUST_VIA))))
    if not r["cond_not_launcher"]:
        reasons.append("解析到启动器/GUI，不是可执行本体：%s" % trap)
    if not r["cond_probe"]:
        reasons.append("探针未给出身份证据：%s" % r["probe_note"])
    r["fail_reasons"] = reasons
    return r


def run_gate(ids: list[str], timeout: int, json_out: str | None) -> int:
    log("=" * 78)
    log("verify-tool-identity —— ⑥-2 门2：Available=True 且 Via≠scan 且 该工具自己的探针给出身份证据")
    log("=" * 78)

    rows = [r for r in PROBES if r.id in ids]
    if not rows:
        log("分母=0：ids 过滤后没有任何一行判据 —— 判红（0 行成功的门是假绿）")
        return 20
    log(f"分母 = {len(rows)} 个工具（来源：本脚本 PROBES 表长度；全表 {len(PROBES)} 行）")
    log(f"判据：①Available ②Via∉{{{','.join(sorted(LOW_TRUST_VIA))}}} ③探针身份证据  超时={timeout}s")
    log("")

    ps = find_powershell()
    if not ps:
        log("本机没有 PowerShell（powershell / pwsh 都找不到）→ 无法测量，退出码 22")
        return 22
    log(f"PowerShell: {ps}")

    bootstrap = find_bootstrap()
    if not bootstrap:
        log(f"找不到 {BOOTSTRAP_REL}（试过 REVERSE_SKILL_ROOT 与 {SKILLS}）→ 无法测量，退出码 22")
        return 22
    log(f"探测层: {bootstrap}")
    log("")

    res = resolve_all(ps, bootstrap, [r.id for r in rows], timeout=max(timeout, 120))
    if "_error" in res:
        log(f"解析失败：{res['_error']} {json.dumps({k: v for k, v in res.items() if k != '_error'}, ensure_ascii=False)}")
        return 22
    specs = {d.get("id"): d for d in res["_items"]}
    log(f"探测层返回 {len(specs)} 行（{res.get('_elapsed')}s）")
    log("")

    results = []
    workdir = tempfile.mkdtemp(prefix="tool-identity-")
    sample = make_sample(workdir)
    for row in rows:
        spec = specs.get(row.id)
        probe = None
        argv = [a.replace("{sample}", sample) for a in row.argv]
        if spec and spec.get("ok") and spec.get("cmd"):
            if not any(re.search(p, spec["cmd"]) for p, _ in LAUNCHER_TRAPS.get(row.id, [])):
                probe = run_probe(spec["cmd"], argv, timeout, workdir)
        results.append(judge(row, spec, probe))

    for r in results:
        log(f"--- {r['id']} [{r['verdict']}]")
        log(f"    Available={r['available']}  Via={r['via'] or 'n/a'}")
        log(f"    Command={r['command'] or 'n/a'}")
        log(f"    探针={' '.join(r['probe_argv'])}  rc={r.get('rc')}  "
            f"t={r.get('elapsed_s')}s  身份={r['identity']}")
        if r["stdout_first"]:
            log(f"    stdout: {r['stdout_first'][0][:160]}")
        elif r.get("stderr_first"):
            log(f"    stderr: {r['stderr_first'][0][:160]}")
        if r["fail_reasons"]:
            for why in r["fail_reasons"]:
                log(f"    ✗ {why}")
        log("")

    green = [r for r in results if r["verdict"] == "绿"]
    red = [r for r in results if r["verdict"] != "绿"]
    log("=" * 78)
    log(f"分母={len(results)}  绿={len(green)}  红={len(red)}")
    for r in red:
        log(f"  红: {r['id']} —— {'；'.join(r['fail_reasons'])}")
    log("门2 结论: " + ("绿（全部三条件通过）" if not red else "红"))
    log("=" * 78)

    if json_out:
        payload = {"gate": "⑥-2 门2 工具身份", "denominator": len(results),
                   "criterion": "①Available=True ②Via∉{scan,scan-ambiguous} ③该工具自己的探针给出身份证据",
                   "powershell": ps, "bootstrap": str(bootstrap), "timeout_s": timeout,
                   "green": len(green), "red": len(red),
                   "verdict": "绿" if not red else "红", "rows": results}
        with open(json_out, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=1)
        log(f"WROTE {json_out}")

    return 0 if not red else 20


def negctl(timeout: int) -> int:
    """反例控制组：门必须抓得住这两条反例，否则门自己就不可信。"""
    log("=" * 78)
    log("negctl —— 反例控制组（两条都必须判红）")
    log("=" * 78)
    ps = find_powershell()
    if not ps:
        log("本机没有 PowerShell → 控制组无法执行，退出码 22")
        return 22
    bootstrap = find_bootstrap()
    if not bootstrap:
        log("找不到 Bootstrap.ps1 → 控制组无法执行，退出码 22")
        return 22

    ok = True

    # 反例 1：必然不存在的 id
    fake = Row("no-such-tool-xyz", ["--version"], [0], r".", "n/a", "negctl")
    res = resolve_all(ps, bootstrap, [fake.id], timeout=max(timeout, 120))
    specs = {d.get("id"): d for d in res.get("_items", [])}
    r1 = judge(fake, specs.get(fake.id), None)
    got_red = r1["verdict"] == "红"
    log(f"[反例1] 不存在的 id `{fake.id}` → {'判红 ✓' if got_red else '判绿 ✗（门失效）'}"
        f"（Available={r1['available']}）")
    ok &= got_red

    # 反例 2：真实工具 + 必然错的探针参数（r2 --version 实测 rc=1 Missing file to open）
    wrong = Row("r2", ["--version"], [0], r"^radare2 \d+\.\d+", "n/a",
                "negctl：r2 的 --version 是错参数")
    res2 = resolve_all(ps, bootstrap, ["r2"], timeout=max(timeout, 120))
    specs2 = {d.get("id"): d for d in res2.get("_items", [])}
    spec2 = specs2.get("r2")
    probe2 = None
    if spec2 and spec2.get("cmd"):
        workdir = tempfile.mkdtemp(prefix="tool-identity-negctl-")
        probe2 = run_probe(spec2["cmd"], ["--version"], timeout, workdir)
    r2 = judge(wrong, spec2, probe2)
    got_red2 = r2["verdict"] == "红"
    log(f"[反例2] r2 + 错探针 `--version` → {'判红 ✓' if got_red2 else '判绿 ✗（门失效）'}"
        f"（rc={r2.get('rc')} {r2['probe_note']}）")
    ok &= got_red2

    log("")
    log("控制组结论: " + ("两条反例都被抓住 ✓" if ok else "有反例没被抓住 ✗ —— 本门不可信"))
    return 0 if ok else 21


def main() -> int:
    ap = argparse.ArgumentParser(description="⑥-2 门2：核心工具身份门（本机门）")
    ap.add_argument("--ids", default="", help="逗号分隔的工具 id（默认全表）")
    ap.add_argument("--timeout", type=int, default=90, help="单个探针超时秒（默认 90）")
    ap.add_argument("--json", default="", help="把逐行结果写成 JSON")
    ap.add_argument("--negctl", action="store_true", help="跑反例控制组（两条反例必须判红）")
    ap.add_argument("--list", action="store_true", help="只打印探针表")
    a = ap.parse_args()

    if a.list:
        for r in PROBES:
            log(f"{r.id:<8} argv={' '.join(r.argv):<14} expect_exit={r.expect_exit} "
                f"regex=/{r.expect_regex}/  # {r.identity}")
        log(f"分母={len(PROBES)}")
        return 0

    if a.negctl:
        return negctl(a.timeout)

    ids = [x.strip() for x in a.ids.split(",") if x.strip()] or [r.id for r in PROBES]
    return run_gate(ids, a.timeout, a.json or None)


if __name__ == "__main__":
    sys.exit(main())
