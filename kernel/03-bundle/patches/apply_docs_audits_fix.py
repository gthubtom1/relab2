#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
apply_docs_audits_fix.py —— 修三份文档里指向旧项目审计记录的死链。

死链（4 处，全部是 [文字](audits/...) 这种 markdown 链接）：
  docs/OPERATING-MODEL.md:261        audits/20260913-redesign/BEHAVIOR.md
  docs/OPERATING-MODEL.md:265        audits/20260913-redesign/VALIDATION.md
  docs/ENGINEERING-CONTINUITY.md:3   audits/20260913/REPORT.md
  docs/RESPONSIBILITY-PROTOCOL.md:3  audits/20260913-redesign/VALIDATION.md

成因：原件在 hub/docs/audits/ 下确实存在（REPORT.md 23129 字节、
BEHAVIOR.md 5425、VALIDATION.md 11730），但 build_hubcore.py 只搬
REQUIRED_DOCS 那 6 份，audits/ 整个没跟过来。
AGENTS.md §17 明写本系统「不背别的项目的包袱」，所以正确处理不是把这些
旧审计报告搬过来，而是把链接改成诚实的说明：那是旧项目的记录，本系统里
以当前这次跑出来的实物与行为证据为准。

一个脚本三份目标：--target 传哪个就只应用哪个文件的规则（POST_PATCHES 是按目标文件索引的）。

用法：python apply_docs_audits_fix.py --target <02-hubcore/docs/OPERATING-MODEL.md>
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _patchlib import Rule, apply_rules   # noqa: E402

SCRIPT_REL = "03-bundle/patches/apply_docs_audits_fix.py"

RULES_BY_NAME: dict[str, list[Rule]] = {
    "OPERATING-MODEL.md": [
        Rule("行为记录链接：诚实的缺口说明",
             r"见\[行为记录\]\(audits/20260913-redesign/BEHAVIOR\.md\)。",
             "（这项行为记录属于旧项目，没随本系统带过来；本系统里以当前这次跑出来的"
             "实物与行为证据为准，不要拿旧记录当现有证据。）", expect=1,
             verify=r"这项行为记录属于旧项目"),
        Rule("验证记录链接：诚实的缺口说明",
             r"本轮全部已运行与未运行范围见 \[验证记录\]\(audits/20260913-redesign/VALIDATION\.md\)。",
             "那次已运行/未运行范围属旧项目记录，没随本系统带过来；本系统里以当前这次"
             "跑出来的实物与行为证据为准。", expect=1,
             verify=r"那次已运行/未运行范围属旧项目记录"),
    ],
    "ENGINEERING-CONTINUITY.md": [
        Rule("2026-09-13 审计链接：诚实的缺口说明",
             r"来源与本次整改见 \[2026-09-13 审计\]\(audits/20260913/REPORT\.md\)，"
             r"旧需求与历史总结继续有效。",
             "来源与那次整改的审计报告属于旧项目，没随本系统带过来；"
             "本系统不背旧项目的账，旧需求与历史总结要查回旧仓库。", expect=1,
             verify=r"来源与那次整改的审计报告属于旧项目"),
    ],
    "RESPONSIBILITY-PROTOCOL.md": [
        Rule("验证记录链接：诚实的缺口说明",
             r"本轮实际验证见 \[验证记录\]\(audits/20260913-redesign/VALIDATION\.md\)。",
             "那次验证记录属于旧项目，没随本系统带过来；本系统里以当前这次跑出来的"
             "实物证据为准。", expect=1,
             verify=r"那次验证记录属于旧项目"),
    ],
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    target = Path(a.target)
    rules = RULES_BY_NAME.get(target.name)
    if rules is None:
        print(f"[跳过] {target.name} 不在本脚本的修补范围内（本脚本只管 "
              f"{'、'.join(RULES_BY_NAME)}）。未改动任何字节。")
        return 0
    return apply_rules(target, SCRIPT_REL, rules, a.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
