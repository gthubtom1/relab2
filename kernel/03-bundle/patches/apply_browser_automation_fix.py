#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
apply_browser_automation_fix.py —— 修 docs/methods/browser-automation.md 的死链。

死链：
  22 处  目录式方法书主书里的附录链接全部指空：主书被拍平成
         docs/methods/browser-automation.md，13 份附录进了
         docs/methods/browser-automation/ 子目录，链接没跟着改。
  1 处   `计票抄 [scripts/proof.py](scripts/proof.py)。` ——
         生成器搬目录式技能时只 glob('*.md')，scripts/ 子目录整个没跟过来
         （原件 hub/.agents/skills/browser-automation/scripts/proof.py 确实存在，2178 字节）。
         这里不假装它在：改成诚实的「本系统没带这个脚本，按下面这份规则自己写」。

用法：python apply_browser_automation_fix.py --target <02-hubcore/docs/methods/browser-automation.md>
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _patchlib import Rule, apply_rules   # noqa: E402

SCRIPT_REL = "03-bundle/patches/apply_browser_automation_fix.py"

APPENDICES = ("catalog", "actions", "forms", "files", "windows", "auth",
              "network", "extract", "env", "recovery", "proof", "pitfalls", "contract")
_ALT = "|".join(APPENDICES)

RULES = [
    Rule("13 份附录链接加子目录前缀",
         rf"\]\(({_ALT})\.md\)", r"](browser-automation/\1.md)", expect=22,
         # FIX-17：改写后必须能看到带子目录前缀的链接，否则无法区分「已改过」与「源文漂移」。
         verify=r"\]\(browser-automation/[^)\s]+\.md\)"),
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
