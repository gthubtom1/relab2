#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
apply_invariants_fix.py —— 修 docs/methods/INVARIANTS.md 的死链。

死链：
  L60  `workflows/review/SKILL.md` —— 生成器的改写规则只把六条线的
       `<hub>/.agents/skills/<线>/SKILL.md` 映射成 `workflows/<线>.md`，
       review 不在六条线里，所以原文照抄成了一条不存在的路径。
       真身是 docs/methods/review.md（附录在 docs/methods/review/）。
  顺带把同一句里的旧词「活技能」改成本系统的说法「活方法书」——
  §9.2.7 明写本系统不读不写技能目录，原词是上一代留下的口径残留。

用法：python apply_invariants_fix.py --target <02-hubcore/docs/methods/INVARIANTS.md>
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _patchlib import Rule, apply_rules   # noqa: E402

SCRIPT_REL = "03-bundle/patches/apply_invariants_fix.py"

RULES = [
    Rule("review 路径改指真身",
         r"`workflows/review/SKILL\.md`", "`docs/methods/review.md`", expect=1,
         verify=r"`docs/methods/review\.md`"),
    Rule("旧词「活技能」→「活方法书」",
         r"审查完不改活技能", "审查完不改活方法书", expect=1,
         verify=r"审查完不改活方法书"),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    return apply_rules(Path(a.target), SCRIPT_REL, RULES, a.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
