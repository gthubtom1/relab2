#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
apply_review_fix.py —— 修 docs/methods/review.md 里指向自己三份附录的死链。

死链（7 处）：
  L20 / L42 / L73 / L75 / L76  `[hunt.md](hunt.md)` `[review-table.md](review-table.md)`
  `[runtime-skins.md](runtime-skins.md)`
  成因：这是目录式方法书。生成器把主书 SKILL.md 拍平成 docs/methods/review.md，
  附录进了 docs/methods/review/ 子目录，但主书里的相对链接没跟着改。
  （同一批里 browser-automation.md 也中招，见 apply_browser_automation_fix.py。）

用法：python apply_review_fix.py --target <02-hubcore/docs/methods/review.md>
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _patchlib import Rule, apply_rules   # noqa: E402

SCRIPT_REL = "03-bundle/patches/apply_review_fix.py"

RULES = [
    Rule("三份附录链接加子目录前缀",
         r"\]\((hunt|review-table|runtime-skins)\.md\)",
         r"](review/\1.md)", expect=7,
          # FIX-17：改写后必须能看到带子目录前缀的链接。
          verify=r"\]\(review/(hunt|review-table|runtime-skins)\.md\)"),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    return apply_rules(Path(a.target), SCRIPT_REL, RULES, a.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
