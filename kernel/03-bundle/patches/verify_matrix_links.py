#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_matrix_links.py —— 逐条验证 matrix.md 里的相对路径能解析到真实文件。

用法：
    python verify_matrix_links.py [--matrix <matrix.md>] [--base <解析基准目录>]

默认：
    --matrix = 脚本同目录 matrix.md
    --base   = <context-isolation>/02-hubcore/workflows
               （即被替换的那份 workflows/protocol-automation.md 所在目录，
                 matrix.md 里的 ../docs/methods/x.md 就是相对它写的）

只用标准库；不联网。任一条解析不到真实文件 → 退出码 1。
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

LINK_RE = re.compile(r"(\.\.[/\\][\w./\\-]+\.md)")


def main(argv: list[str] | None = None) -> int:
    here = Path(__file__).resolve().parent
    ctx = here.parent.parent  # work/context-isolation
    ap = argparse.ArgumentParser(description="验证 matrix.md 里每条方法书相对路径真实存在")
    ap.add_argument("--matrix", default=str(here / "matrix.md"))
    ap.add_argument("--base", default=str(ctx / "02-hubcore" / "workflows"),
                    help="相对路径的解析基准目录（默认 02-hubcore/workflows）")
    args = ap.parse_args(argv)

    matrix = Path(args.matrix).resolve()
    base = Path(args.base).resolve()
    hubcore = (ctx / "02-hubcore").resolve()

    if not matrix.is_file():
        print(f"[错误] matrix 不存在：{matrix}", file=sys.stderr)
        return 2
    if not base.is_dir():
        print(f"[错误] 解析基准目录不存在：{base}", file=sys.stderr)
        return 2

    text = matrix.read_text(encoding="utf-8")
    lines = text.splitlines()

    print(f"matrix = {matrix}")
    print(f"base   = {base}")
    print(f"根边界  = {hubcore}（解析结果不允许跑出这个目录）")
    print("-" * 108)

    seen: list[str] = []
    rows: list[tuple[int, str, Path, bool, str]] = []
    for lineno, line in enumerate(lines, 1):
        for rel in LINK_RE.findall(line):
            norm = rel.replace("\\", "/")
            resolved = (base / norm).resolve()
            inside = hubcore == resolved or hubcore in resolved.parents
            ok = resolved.is_file() and inside
            why = ""
            if not inside:
                why = "跑出 02-hubcore 边界"
            elif not resolved.exists():
                why = "文件不存在"
            elif not resolved.is_file():
                why = "不是普通文件"
            size = resolved.stat().st_size if resolved.is_file() else 0
            rows.append((lineno, norm, resolved, ok, why or f"{size} 字节"))
            if norm not in seen:
                seen.append(norm)

    for lineno, norm, resolved, ok, why in rows:
        flag = "OK  " if ok else "FAIL"
        try:
            shown = resolved.relative_to(hubcore)
        except ValueError:
            shown = resolved
        print(f"{flag} matrix.md:{lineno:<3} {norm:<42} -> 02-hubcore/{shown}  [{why}]")

    print("-" * 108)
    print(f"引用 {len(rows)} 条，去重后 {len(seen)} 个不同文件，"
          f"通过 {sum(1 for r in rows if r[3])} 条，失败 {sum(1 for r in rows if not r[3])} 条。")

    # 八个阶段必须都在
    phases = ["0-spec", "1-env-traffic", "2-discovery", "3-solve-re",
              "4-protocol-verify", "5-automate", "6-test-regression", "7-handoff"]
    missing = [p for p in phases if p not in text]
    print(f"阶段覆盖：{len(phases) - len(missing)}/{len(phases)}" + (f"，缺 {missing}" if missing else "，齐全"))
    if missing:
        return 1
    # all([]) is True, so a matrix with zero recognised `../x.md` references used to
    # pass with "引用 0 条 … 失败 0 条" -- a green light that verified nothing
    # (DESIGN-RULES rule 12). An empty denominator must not read as success.
    if not rows:
        print("矩阵里一条 `../xxx.md` 引用都没有 —— 这不是「全通过」，是没验到东西。")
        print("检查 LINK_RE 是否与矩阵实际写法匹配（只认 ../ 开头的 token）。")
        return 1
    return 0 if all(r[3] for r in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
