#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
apply_browser_automation_proof_fix.py —— 修 docs/methods/browser-automation/proof.md 的死链。

死链（1 处）：`计票抄 [scripts/proof.py](scripts/proof.py)。`
  生成器搬目录式方法书时只搬 `*.md`，scripts/ 子目录没跟过来
  （原件 hub/.agents/skills/browser-automation/scripts/proof.py 存在，2178 字节）。
  不假装它在：改成诚实的「本系统没带这个脚本，按下面这份规则自己写」。

用法：python apply_browser_automation_proof_fix.py --target <02-hubcore/docs/methods/browser-automation/proof.md>
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _patchlib import Rule, apply_rules   # noqa: E402

SCRIPT_REL = "03-bundle/patches/apply_browser_automation_proof_fix.py"

RULES = [
    Rule("计票脚本：诚实的缺口说明",
         r"计票抄 \[scripts/proof\.py\]\(scripts/proof\.py\)。",
         "计票脚本属于旧中枢，本系统没带（生成器搬目录式方法书时只搬 `.md` 附录，"
         "`scripts/` 子目录没跟过来）。要计票就按下面这份规则自己写一份，"
         "不要去找那个不存在的脚本。",
         expect=1,
         verify=r"计票脚本属于旧中枢，本系统没带"),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    return apply_rules(Path(a.target), SCRIPT_REL, RULES, a.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
