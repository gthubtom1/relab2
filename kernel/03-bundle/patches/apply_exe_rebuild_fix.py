#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
apply_exe_rebuild_fix.py —— 修 workflows/exe-rebuild.md 的死链。

死链（check_dead_refs.py 判出来的，证据在 DEAD-REFS.md）：
  L71 / L139  `../INVARIANTS.md` —— 这条线在 workflows/ 下，上跳一级到的是
              02-hubcore/ 根，那儿没有 INVARIANTS.md；真身在 docs/methods/INVARIANTS.md。
  L246        `templates/memory-tree/CHANGES.md` —— build_hubcore.py 只搬
              hub/templates/ 根下的文件，memory-tree/ 子目录整个没跟过来。

用法：python apply_exe_rebuild_fix.py --target <02-hubcore/workflows/exe-rebuild.md>
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _patchlib import Rule, apply_rules   # noqa: E402

SCRIPT_REL = "03-bundle/patches/apply_exe_rebuild_fix.py"

RULES = [
    Rule("INVARIANTS 改指真身",
         r"`\.\./INVARIANTS\.md`", "`../docs/methods/INVARIANTS.md`", expect=2,
         verify=r"`\.\./docs/methods/INVARIANTS\.md`"),
    Rule("CHANGES 模板：改成诚实的自足说明",
         r"模板见 `templates/memory-tree/CHANGES\.md`。",
         "改动图模板没随本系统带过来（`build_hubcore.py` 只搬 `templates/` 根下的文件，"
         "memory-tree 子目录没跟过来）；上面这七项就是最低要求，按齐写进产品根 `CHANGES.md`。",
          expect=1,
          verify=r"改动图模板没随本系统带过来"),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    return apply_rules(Path(a.target), SCRIPT_REL, RULES, a.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
