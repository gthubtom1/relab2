#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
apply_matrix_fix.py —— 幂等补丁器：把 workflows/protocol-automation.md 里的
「调度子技能矩阵」整段替换成 03-bundle/patches/matrix.md 的内容。

用法：
    python apply_matrix_fix.py --target <workflows/protocol-automation.md 的路径>
                               [--matrix <matrix.md>] [--dry-run]

行为约定：
  * 幂等：跑第二次输出「无改动」，不写文件，退出码 0。
  * 替换前把旧段原文逐字存进 <!-- hubcore: matrix-replaced-by --> 注释，便于人工比对。
  * 找不到旧段、且也没有替换标记时：报「未找到旧矩阵，可能是已经改过或源文变了」，退出码 3，不瞎改。
  * 只用 Python 3.12 标准库；不联网；不做任何 git 操作。
  * 保留目标文件原有的换行风格与 BOM；不改动注释块以外的任何内容。
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

MARKER = "<!-- hubcore: matrix-replaced-by"
MARKER_END = "-->"

# 旧段起点：形如 "## 调度子技能矩阵（工作流管路，技能管能力）" 的二级标题
START_RE = re.compile(r"^##\s*.*调度子技能矩阵")
# 旧段终点：原书矩阵后面那段「能让人点就让人点。」
END_RE = re.compile(r"^\*\*能让人点就让人点。\*\*")
# 兜底终点：下一个二级标题
NEXT_H2_RE = re.compile(r"^##\s")
# 次级特征串：旧矩阵的表头行（万一标题被改过，仍能兜住）。
# 必须限定成**旧表头**的整行：以竖线开头、以竖线结尾，且第三列是旧版的「目的」——
# 新版表头是「需要哪一类能力 | 打开哪个文件」，只靠字面会把新版表格误判成旧表头。
FALLBACK_RE = re.compile(r"^\|.*要哪一类能力.*目的.*\|")


def split_keepends(text: str) -> list[str]:
    return text.splitlines(keepends=True)


def comment_mask(lines: list[str]) -> list[bool]:
    """标出落在 HTML 注释块内的行。归档原文里也含特征串，必须屏蔽掉。"""
    mask = [False] * len(lines)
    inside = False
    for i, line in enumerate(lines):
        if inside:
            mask[i] = True
        opens = line.count("<!--")
        closes = line.count("-->")
        if inside:
            if closes:
                inside = False
        elif opens and opens > closes:
            inside = True
            mask[i] = True
    return mask


def line_body(line: str) -> str:
    return line.rstrip("\r\n")


def read_text(path: Path) -> tuple[str, bool]:
    raw = path.read_bytes()
    has_bom = raw.startswith(b"\xef\xbb\xbf")
    return raw.decode("utf-8-sig"), has_bom


def write_text(path: Path, text: str, has_bom: bool) -> int:
    data = text.encode("utf-8-sig" if has_bom else "utf-8")
    path.write_bytes(data)
    return len(data)


def find_start(lines: list[str], mask: list[bool], allow_fallback: bool) -> int | None:
    for i, line in enumerate(lines):
        if mask[i]:
            continue
        if START_RE.match(line_body(line)):
            return i
    if not allow_fallback:
        return None
    for i, line in enumerate(lines):
        if mask[i]:
            continue
        if FALLBACK_RE.match(line_body(line)):
            return i
    return None


def find_region(lines: list[str], mask: list[bool], allow_fallback: bool) -> tuple[int, int] | None:
    start = find_start(lines, mask, allow_fallback)
    if start is None:
        return None

    end = None
    for j in range(start + 1, len(lines)):
        if mask[j]:
            continue
        body = line_body(lines[j])
        if END_RE.match(body):
            end = j
            break
        if NEXT_H2_RE.match(body):
            end = j - 1
            break
    if end is None:
        end = len(lines) - 1
    return start, end


def build_block(old_text: str, matrix_body: str, newline: str, tool_note: str) -> str:
    old_body = old_text.rstrip("\r\n")
    old_lines = old_body.splitlines()
    out: list[str] = []
    out.append(MARKER + newline)
    out.append("     旧矩阵原文（逐字保留，未改一个字；只用于人工比对，渲染时不可见）：" + newline)
    for line in old_lines:
        out.append(line + newline)
    out.append("     替换者：" + tool_note + newline)
    out.append(MARKER_END + newline)
    out.append(newline)
    for line in matrix_body.splitlines():
        out.append(line + newline)
    return "".join(out)


def main(argv: list[str] | None = None) -> int:
    here = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser(description="把 protocol-automation 工作流的调度矩阵换成本系统方法书矩阵")
    ap.add_argument("--target", required=True, help="待打补丁的 workflows/protocol-automation.md 路径")
    ap.add_argument("--matrix", default=str(here / "matrix.md"), help="新矩阵内容（默认：脚本同目录 matrix.md）")
    ap.add_argument("--dry-run", action="store_true", help="只报将要改什么，不写文件")
    args = ap.parse_args(argv)

    target = Path(args.target)
    matrix = Path(args.matrix)
    if not target.is_file():
        print(f"[错误] 目标文件不存在：{target}", file=sys.stderr)
        return 2
    if not matrix.is_file():
        print(f"[错误] 矩阵文件不存在：{matrix}", file=sys.stderr)
        return 2

    text, has_bom = read_text(target)
    before_bytes = len(text.encode("utf-8-sig" if has_bom else "utf-8"))
    before_lines = len(split_keepends(text))
    newline = "\r\n" if "\r\n" in text else "\n"

    lines = split_keepends(text)
    mask = comment_mask(lines)
    has_marker = any(MARKER in line for line in lines)

    # 已经有替换标记 = 旧段肯定换过了，这时只认一级锚点（章节标题），
    # 不再启用表格行兜底，避免把新版正文里的散文误当成旧表头。
    region = find_region(lines, mask, allow_fallback=not has_marker)
    if region is None:
        if has_marker:
            print(f"[无改动] {target.name} 已是新版矩阵（含 {MARKER} 标记），本次不写任何字节。")
            print(f"        字节 {before_bytes}，行 {before_lines}，未变。")
            return 0
        print("[未找到] 未找到旧矩阵，可能是已经改过或源文变了。", file=sys.stderr)
        print("          没有改动目标文件。", file=sys.stderr)
        return 3

    start, end = region
    old_text = "".join(lines[start:end + 1])
    n_old = len(old_text.rstrip("\r\n").splitlines())

    matrix_body = read_text(matrix)[0].rstrip("\r\n")
    tool_note = "03-bundle/patches/apply_matrix_fix.py"
    new_block = build_block(old_text, matrix_body, newline, tool_note)
    n_new = len(new_block.rstrip("\r\n").splitlines())

    new_text = "".join(lines[:start]) + new_block + "".join(lines[end + 1:])
    after_bytes = len(new_text.encode("utf-8-sig" if has_bom else "utf-8"))
    after_lines = len(split_keepends(new_text))

    print(f"[定位] 旧矩阵：第 {start + 1} 行 → 第 {end + 1} 行（共 {n_old} 行）")
    print(f"[结果] 替换了 {n_old} 行 → {n_new} 行")
    print(f"[统计] 字节 {before_bytes} → {after_bytes}（{after_bytes - before_bytes:+d}）")
    print(f"[统计] 总行 {before_lines} → {after_lines}（{after_lines - before_lines:+d}）")

    if args.dry_run:
        print("[预演] --dry-run：未写入任何字节。")
        return 0

    if new_text == text:
        print("[无改动] 内容与目标文件完全一致，没有写入。")
        return 0

    write_text(target, new_text, has_bom)
    print(f"[已写] {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
