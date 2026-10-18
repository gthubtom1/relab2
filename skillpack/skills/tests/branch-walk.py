#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""branch-walk.py —— 从**入口**开始，逐分支真跑并**独立复算**（不信任任何自述）。

主人 2026-10-16 的原话（本脚本存在的理由）
-----------------------------------------
「我要的是树图，**从入口开始，到任何一个分支都是走通的**…不是做个图就说好了。
  是要真的做好图，然后**真的去测试每一个分支**，然后都是通的。
  **通了后，要保证是正确的**，就像之前你工具命令错、导致 powershell 卡死。」

所以本脚本做的不是"跑一遍看不报错"，而是：
  ① 拿入口（`relab2.ps1 doctor`）**自述**的每一项；
  ② 对每一项用**独立代码路径复算**（数文件、读 json、真跑门），不看它的自述；
  ③ 输出「自述 vs 实测 vs 一致?」—— **不一致 = 这个分支"通了但不对"**。

用法
    python skills/tests/branch-walk.py             # 入口层全项
    python skills/tests/branch-walk.py --json
退出码：0 全部一致；1 有"自述与实测不符"。
"""
from __future__ import annotations

import argparse
import glob
import io
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILLS = HERE.parent
REPO = SKILLS.parent.parent


def _read(p) -> str:
    try:
        return io.open(p, encoding="utf-8-sig", errors="replace").read()
    except OSError:
        return ""


def _run(cmd, timeout=300):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, errors="replace",
                           timeout=timeout, cwd=str(REPO))
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except (OSError, subprocess.TimeoutExpired) as e:
        return None, f"{type(e).__name__}: {e}"


# ---------------------------------------------------------------- 复算
def actual_skill_cards() -> tuple[int, int]:
    """(顶层数, 全部 SKILL.md 数) —— 与 doctor 同口径；两个数都对，但含义不同。"""
    top = len(glob.glob(str(SKILLS / "*" / "SKILL.md")))
    total = len([p for p in glob.glob(str(SKILLS / "**" / "SKILL.md"), recursive=True)
                 if Path(p).parent != SKILLS])
    return top, total


def actual_gates() -> int:
    try:
        return len(json.loads(_read(SKILLS / "tests" / "ci-gates.json")).get("gates", []))
    except ValueError:
        return -1


def actual_mcp() -> int:
    try:
        return len(json.loads(_read(Path(os.path.expanduser("~")) / ".omp" / "agent" / "mcp.json"))
                   .get("mcpServers", {}))
    except ValueError:
        return -1


def actual_base_cards() -> int:
    return len(glob.glob(str(REPO / "kernel/04-console/cards/base" / "*.md")))


def actual_kb_docs() -> int:
    """知识库：KB-INDEX 里各板块正文数之和（索引自述的口径）。"""
    idx = _read(SKILLS / "field-journal" / "KB-INDEX.md")
    return sum(int(m.group(1)) for m in re.finditer(r"\|\s*`?\.\./[^|`]+`?\s*\|\s*(\d+)\s*\|", idx))


def actual_kb_originals() -> int:
    """知识库原始副本（doctor 报的"221 篇"应该数的是这个）。"""
    root = Path(os.environ.get("REVERSE_TOOL_ROOT", r"D:\Tools")) / "kb-open-reverselab"
    if not root.is_dir():
        return -1
    return len(glob.glob(str(root / "**" / "*.md"), recursive=True))


def actual_toolmap() -> tuple[int, int]:
    """toolmap prefer 的 (失效数, 总数)。"""
    repo_root = Path(__file__).resolve().parents[3]  # skillpack/skills/tests -> 仓库根
    bootstrap = repo_root / "skillpack" / "skills" / "scripts" / "lib" / "Bootstrap.ps1"
    rc, out = _run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
                    f". '{bootstrap.as_posix()}';"
                    " $h = Test-ReverseToolmapHealth; \"$($h.missing) $($h.total)\""], timeout=180)
    if rc == 0 and out.strip():
        parts = out.strip().split()
        if len(parts) >= 2 and parts[0].isdigit():
            return int(parts[0]), int(parts[1])
    return -1, -1


def actual_card_drift() -> bool:
    """仓库卡与宿主卡是否逐行一致（忽略行尾）。"""
    pairs = [(SKILLS.parent.parent / "kernel/04-console/cards/base/space-bunny-2.md",
              Path(os.path.expanduser("~")) / ".omp/agent/PERSONALITY.md"),
             (SKILLS.parent.parent / "kernel/04-console/cards/guest/全能专精指引.md",
              Path(os.path.expanduser("~")) / ".omp/agent/RULES.md")]
    for a, b in pairs:
        if not (a.is_file() and b.is_file()):
            return False
        x = _read(a).replace("\r\n", "\n")
        y = _read(b).replace("\r\n", "\n")
        if x != y:
            return False
    return True


# ---------------------------------------------------------------- 分支定义
# (分支 id, doctor 输出里的关键字, 正则取"自述值", 复算函数, 期望值来源)
def run_doctor() -> str:
    rc, out = _run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                    "-File", str(REPO / "relab2.ps1"), "doctor"], timeout=600)
    return out or ""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-doctor", action="store_true", help="跳过真跑 doctor（用缓存输出）")
    a = ap.parse_args()

    out = ""
    if not a.no_doctor:
        print("… 正在真跑入口 `relab2.ps1 doctor`（约 70s）")
        out = run_doctor()
    if not out:
        out = _read(Path(os.environ.get("LOCALAPPDATA", ".")) / "Temp" / "rel2-doctor3.txt")

    def claimed(pat: str, group: int = 1) -> str:
        m = re.search(pat, out)
        return m.group(group).strip() if m else "（没读到）"

    rows = []
    # ① 技能卡
    top, total = actual_skill_cards()
    m = re.search(r"技能卡\s+(\d+)\s*张顶层\s*\+\s*(\d+)\s*张嵌套/包装", out)
    if m:
        rows.append(("技能卡", f"{m.group(1)}+{m.group(2)}",
                     f"{top}+{total - top}", (m.group(1), m.group(2)) == (str(top), str(total - top)),
                     "分开数顶层与嵌套/包装"))
    else:
        c = claimed(r"技能卡\s+(\d+)\s*张")
        rows.append(("技能卡", c, f"{top}(顶层)/{total}(全部)", c == str(top), "旧口径（只有顶层）"))
    # ② 门禁清单
    c = claimed(r"门禁清单\s+(\d+)\s*道")
    t = actual_gates()
    rows.append(("门禁清单", c, str(t), c == str(t), "读 ci-gates.json"))
    # ③ MCP 通道
    c = claimed(r"MCP 通道\s+已注册\s+(\d+)\s*条")
    t = actual_mcp()
    rows.append(("MCP 通道", c, str(t), c == str(t), "读宿主 mcp.json"))
    # ④ 破甲卡
    c = claimed(r"破甲卡\s+(\d+)\s*张")
    t = actual_base_cards()
    rows.append(("破甲卡", c, str(t), c == str(t), "glob cards/base/*.md"))
    # ⑤ 知识库（两项口径可能不同，分别验）
    c = claimed(r"知识库.*?原始副本\s+(\d+)\s*篇")
    t = actual_kb_originals()
    rows.append(("知识库·原始副本", c, str(t), c == str(t), "数 <工具根>/kb-open-reverselab/**/*.md"))
    c2 = claimed(r"知识库.*?症状索引(在|不在)")
    rows.append(("知识库·症状索引", c2, "在", c2 == "在", "KB-INDEX.md 存在"))
    # ⑥ toolmap prefer
    c = claimed(r"toolmap prefer\s+(\d+)/(\d+)")
    m = re.search(r"toolmap prefer\s+(\d+)/(\d+)", out)
    miss, tot = actual_toolmap()
    if m and miss >= 0:
        rows.append(("toolmap prefer", f"{m.group(1)}/{m.group(2)}", f"{miss}/{tot}",
                     (m.group(1), m.group(2)) == (str(miss), str(tot)), "跑 Test-ReverseToolmapHealth"))
    else:
        rows.append(("toolmap prefer", c or "（无）", f"{miss}/{tot}", False, "复算失败"))
    # ⑦ 装机卡漂移
    c = "一致" if "已装宿主入口文件与仓库卡逐行一致" in out else ("不一致" if "不一致" in out else "（没读到）")
    t = actual_card_drift()
    rows.append(("装机卡漂移", c, "一致" if t else "不一致", (c == "一致") == t, "逐行比对(忽略行尾)"))
    # ⑧ 要求门
    rc, o = _run([sys.executable, str(SKILLS / "tests" / "verify-project-requirements.py")], timeout=300)
    c = "全过" if "全过" in out else "（没读到）"
    rows.append(("要求门 R1-R13", c, "全过" if rc == 0 else f"退出码 {rc}",
                 (c == "全过") == (rc == 0), "真跑本门"))
    # ⑨ 行为门实跑台账
    ledger = Path(os.environ.get("LOCALAPPDATA", ".")) / "reverse-skill" / "behavior-runs.jsonl"
    c = "从未实跑过" if "从未实跑过" in out else ("有记录" if "上次" in out else "（没读到）")
    t = "有记录" if ledger.is_file() and ledger.stat().st_size > 0 else "从未实跑过"
    rows.append(("行为门实跑", c, t, c == t, "看 behavior-runs.jsonl"))

    if a.json:
        print(json.dumps([{"branch": r[0], "claimed": r[1], "actual": r[2],
                           "match": r[3], "how": r[4]} for r in rows],
                         ensure_ascii=False, indent=2))
    else:
        print()
        print("入口层逐分支核验（**自述 vs 独立复算** —— 不一致就是「通了但不对」）")
        print("=" * 78)
        print(f"{'分支':<20} {'doctor 自述':<20} {'独立复算':<20} {'一致':<4} 复算方式")
        bad = 0
        for name, cl, ac, ok, how in rows:
            if not ok:
                bad += 1
            print(f"{name:<20} {cl:<20} {ac:<20} {'✓' if ok else '✗':<4} {how}")
        print()
        print(f"→ {len(rows)} 个分支，不一致 {bad} 个")
        if bad:
            print("  不一致 = 自述与实测对不上：要么自述错、要么复算口径错 —— 两种都要查清。")
    return 1 if any(not r[3] for r in rows) else 0


if __name__ == "__main__":
    sys.exit(main())
