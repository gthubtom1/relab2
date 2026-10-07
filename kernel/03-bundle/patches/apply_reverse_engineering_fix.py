#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
apply_reverse_engineering_fix.py —— 修 docs/methods/reverse-engineering.md 的死链。

死链：
  L12 / L24 / L100 / L120  `../INVARIANTS.md` —— 本书在 docs/methods/ 下，
       上跳一级是 docs/，那儿没有 INVARIANTS.md；真身是同目录的 INVARIANTS.md，
       统一写成中枢根相对的 `docs/methods/INVARIANTS.md`（与 AGENTS.md §16 的口径一致）。
  L51  `../README.md`「没有匹配的 skill」—— 那是旧中枢外部库那张能力对照表，
       build_hubcore.py 的 LINE_RULES 本来就要整行删掉它，但源文那句不是列表行，
       规则没匹配上，留了半句指着空气。这里不硬塞一本不相干的书，
       改成诚实的「本系统没有这张表 + 停在方法书能给的位置」。

用法：python apply_reverse_engineering_fix.py --target <02-hubcore/docs/methods/reverse-engineering.md>
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _patchlib import Rule, apply_rules   # noqa: E402

SCRIPT_REL = "03-bundle/patches/apply_reverse_engineering_fix.py"

RULES = [
    Rule("INVARIANTS 改指真身",
         r"`\.\./INVARIANTS\.md`", "`docs/methods/INVARIANTS.md`", expect=4,
         verify=r"`docs/methods/INVARIANTS\.md`"),
    Rule("外部库能力表：诚实的缺口说明",
         r"见 `\.\./README\.md`「没有匹配的 skill」。",
         "本系统没有那张「能力 → 深库」对照表——那是旧中枢外部库的索引，"
         "已随外部库一起移出，本系统不联网也不装外部库。"
         "没有匹配时停在方法书能给的位置：先调查、写假设、做区分性实验，"
         "把未知类型和剩下的变量记进账本，不许套最近一行当已解决。",
          expect=1,
          verify=r"本系统没有那张「能力 → 深库」对照表"),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    return apply_rules(Path(a.target), SCRIPT_REL, RULES, a.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
