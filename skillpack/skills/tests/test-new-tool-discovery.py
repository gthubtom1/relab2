#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test-new-tool-discovery.py —— 「换一台装了名字没见过的同类软件，中枢也认得出来、用得上」的可运行判据。

为什么有这个门（2026-10-16）：
    2026-10-15 的独立审计实测这件事**是断的**，而且断在两头：
      ① 能力发现的 `help` 兜底结构上不可能命中（`HELP_HINTS` 每能力只有 1 条正则，
         而判据要求 ≥2 条 → 永假）。审计造了 3 个虚构工具跑真实 `build()`：**3 个全落 unknown**。
      ② 就算认出来也**调不动**：`run_tool` 只查 57 条硬编码 id 的预探测表，表外的工具
         一律回「本机没有可用工具」——识别层泛化、调用层是清单，两套东西。
    两头都已修（help 兜底补足关键词 + `run_tool` 改成链式解析）。本门把那句话变成每次都会跑的断言：
    造一棵**合成工具根**，里面是虚构名字、且 `--help` 文本才是唯一能力线索，
    然后断言：**① 能力发现能归位；② 解析链能找到它；③ run_tool 真能跑起来拿到输出。**

用法：
    python skills/tests/test-new-tool-discovery.py
    python skills/tests/test-new-tool-discovery.py --json
退出码：0 全过；1 有断言失败。
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILLS = HERE.parent                      # skillpack/skills
REPO = SKILLS.parent.parent               # 仓库根

# 虚构名字 + 只有 --help 文本能说明能力（名字与目录名都不含规则里的关键词）
FAKE = {
    "ZorkDump": ("ZorkDump 1.0 - extract firmware image and dump the filesystem (squashfs / jffs2) from a router image.",
                 "firmware-unpack"),
    "BlipScan": ("BlipScan 1.0 - fast port scan with service detection and syn scan.",
                 "portscan"),
    "QuuxDecomp": ("QuuxDecomp 1.0 - decompile a binary function to pseudocode and print the control flow graph.",
                   "static-decompile"),
    # 反例：名字像工具、但 help 文本没有任何能力线索 —— 必须落 unknown，不能瞎猜
    "ZorpThing": ("ZorpThing 1.0 - a general utility that does various things.", None),
}


def make_fake_root() -> Path:
    root = Path(tempfile.mkdtemp(prefix="rel2-newtools-"))
    cli = root / "cli"
    cli.mkdir(parents=True)
    for name, (helptext, _cap) in FAKE.items():
        # .cmd 不能带 BOM（cmd.exe 会把 BOM 当命令）；用 ASCII 正文避免代码页干扰
        (cli / f"{name}.cmd").write_text(f"@echo off\r\necho {helptext}\r\nexit /b 0\r\n", encoding="ascii")
    return root


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    root = make_fake_root()
    os.environ["REVERSE_TOOL_ROOT"] = str(root)
    fails: list[str] = []
    report: dict = {"fake_root": str(root), "discovery": {}, "resolution": {}}

    # ① 能力发现
    spec = importlib.util.spec_from_file_location("ci", SKILLS / "scripts" / "capability-index.py")
    ci = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ci)  # type: ignore[union-attr]
    idx = ci.build(probe_help=True)
    found = {}
    for cap, lst in idx["capabilities"].items():
        for e in lst:
            if e["tool"] in FAKE:
                found[e["tool"]] = {"cap": cap, "how": e.get("how")}
    for tool, (_h, want) in FAKE.items():
        got = found.get(tool)
        got_cap = got["cap"] if got else None
        report["discovery"][tool] = got_cap
        if want is None:
            if got_cap is not None:
                fails.append(f"反例 {tool} 被瞎猜成 {got_cap}（help 无能力线索时应落 unknown）")
        elif got_cap != want:
            fails.append(f"{tool}: 期望 {want}，实得 {got_cap}")

    # ② 调得动 + ③ 真能跑
    spec2 = importlib.util.spec_from_file_location("m", SKILLS / "scripts" / "relab2-tools-mcp.py")
    m = importlib.util.module_from_spec(spec2)
    spec2.loader.exec_module(m)  # type: ignore[union-attr]
    ctx = m.Ctx(argparse.Namespace(skill_root=str(REPO), tool_root=str(root)))
    for tool, (_h, want) in FAKE.items():
        if want is None:
            continue  # 反例不要求可解析
        cmd, via, why = ctx.resolve(tool)
        report["resolution"][tool] = via if cmd else None
        if not cmd:
            fails.append(f"{tool}: 解析链找不到（{why}）—— 「认得出但调不动」又回来了")
            continue
        r = ctx.run(tool, ["--version"], 30)
        if r.get("status") != "ok" or not r.get("stdout_bytes"):
            fails.append(f"{tool}: 调不动（status={r.get('status')} bytes={r.get('stdout_bytes')}）")

    if a.json:
        print(json.dumps({"report": report, "fails": fails}, ensure_ascii=False, indent=2))
    else:
        print("① 能力发现（help 兜底 —— 名字与目录名都不是线索）")
        for tool, (_h, want) in FAKE.items():
            got = report["discovery"].get(tool)
            mark = "PASS" if (got == want or (want is None and got is None)) else "FAIL"
            print(f"   [{mark}] {tool:<11} 期望 {str(want):<18} 实得 {got}")
        print("② 调得动（解析链：预探测表 → 探测层 → 能力索引）")
        for tool, via in report["resolution"].items():
            print(f"   [{'PASS' if via else 'FAIL'}] {tool:<11} via={via}")
        print()
        print("新工具发现:", "PASS（认得出 + 调得动）" if not fails else "FAIL")
        for f in fails:
            print("  x", f)
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
