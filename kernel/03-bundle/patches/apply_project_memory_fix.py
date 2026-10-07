#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
apply_project_memory_fix.py —— 修 docs/PROJECT-MEMORY.md 的死链。

死链（1 处）：
  L50  `见 [变更示例](../templates/memory-tree/change.example.json)。`
       build_hubcore.py 只搬 hub/templates/ 根下的文件（copy2 一层），
       memory-tree/ 子目录整个没跟过来；原件 change.example.json 确实存在，571 字节。
       这里不假装它在，也不硬塞别的示例：同一句后面已经把必填字段写全了
       （`id/name/purpose/intent`，`implementation` 省略或 null），
       补一句「示例文件没带过来，按这几个字段写齐即可」就够。

用法：python apply_project_memory_fix.py --target <02-hubcore/docs/PROJECT-MEMORY.md>
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _patchlib import Rule, apply_rules   # noqa: E402

SCRIPT_REL = "03-bundle/patches/apply_project_memory_fix.py"

RULES = [
    Rule("变更示例链接：诚实的缺口说明",
         r"，见 \[变更示例\]\(\.\./templates/memory-tree/change\.example\.json\)。",
         "。变更示例文件没随本系统带过来（生成器只搬 `templates/` 根下的文件，"
         "memory-tree 子目录没跟过来）；按下面这几个必填字段写齐即可，不要去找那个文件。",
          expect=1,
          verify=r"变更示例文件没随本系统带过来"),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    return apply_rules(Path(a.target), SCRIPT_REL, RULES, a.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
