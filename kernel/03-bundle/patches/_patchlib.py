#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
_patchlib.py —— 所有 `apply_*_fix.py` 共用的底座（当前 10 个）。

规矩（每个 apply_*_fix.py 都必须遵守，dead-references 修补一律走这里）：
  * 定点改写：只改规则里点名的那些片段，不重排、不重写整篇。
  * 幂等：跑第二次不改一个字节，也不重复写归档注释。
  * 归档：改过的每一行，改写前的原文逐字写进文件末尾的
    <!-- hubcore: deadrefs-fixed-by ... --> 注释块，供人工比对。
  * 注释块里的行**不参与**改写（否则第二次跑会在归档里再改一遍）。
  * 保留目标文件原有的换行风格与 BOM。
  * 找不到该改的内容时：照旧返回 0 并报「无改动」；只有目标文件不在时返回 2。
  * Python 3.10+ 标准库；不联网；不做任何 git 操作。
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

MARKER_OPEN = "<!-- hubcore: deadrefs-fixed-by"
MARKER_END = "-->"


# FIX-17：设为 "1" 才允许「命中 0 次且规则没有 verify」这种无法判定的情况按
# 幂等空转放行。默认关 —— 闸门不许在分不清的时候给绿灯。
ALLOW_UNVERIFIED = os.environ.get("PATCHLIB_ALLOW_UNVERIFIED", "") == "1"
def read_text(path: Path) -> tuple[str, bool]:
    raw = path.read_bytes()
    has_bom = raw.startswith(b"\xef\xbb\xbf")
    return raw.decode("utf-8-sig"), has_bom


def write_text(path: Path, text: str, has_bom: bool) -> int:
    data = text.encode("utf-8-sig" if has_bom else "utf-8")
    path.write_bytes(data)
    return len(data)


def comment_mask(lines: list[str]) -> list[bool]:
    mask = [False] * len(lines)
    inside = False
    for i, line in enumerate(lines):
        opens, closes = line.count("<!--"), line.count("-->")
        if inside:
            mask[i] = True
        if inside:
            if closes:
                inside = False
        elif opens and opens > closes:
            inside = True
            mask[i] = True
    return mask


class Rule:
    """一条定点改写规则。name 用来在报告里点名。

    verify（FIX-17）：改写后必须能在文件里命中的一条正则 —— 它是「已经改过了」
    的**正面**证据。旧代码只有 find（负面证据：一处都匹配不上），而「一处都
    匹配不上」同时对应两种完全相反的情况：
        (a) 上一轮已经改过了，重跑是幂等空转；
        (b) 上游源文变了，这条规则从此再也匹配不上。
    两者输出完全一样（都是「[无改动]」+ exit 0），闸门在 (b) 上给的是假绿灯。
    有了 verify，(a) 时 verify 命中 → 判「已是新版」；(b) 时 verify 不命中 →
    判「漂移」，退出码 3，不写入任何字节。
    """

    def __init__(self, name: str, find: str | re.Pattern[str], repl: str,
                 expect: int | None = None,
                 verify: str | re.Pattern[str] | None = None):
        self.name = name
        self.find = re.compile(find) if isinstance(find, str) else find
        self.repl = repl
        self.expect = expect          # 期望命中次数；None = 不限
        self.verify = re.compile(verify) if isinstance(verify, str) else verify


def apply_rules(path: Path, script_rel: str, rules: list[Rule], dry_run: bool = False) -> int:
    if not path.is_file():
        print(f"[错误] 目标文件不存在：{path}", file=sys.stderr)
        return 2
    text, has_bom = read_text(path)
    newline = "\r\n" if "\r\n" in text else "\n"
    before_bytes = len(text.encode("utf-8-sig" if has_bom else "utf-8"))
    before_lines = len(text.splitlines())

    lines = text.splitlines(keepends=True)
    mask = comment_mask(lines)
    changed: list[str] = []          # 归档用：L<行号>: <改前原文>
    hits: list[tuple[str, int, int | None]] = []

    for rule in rules:
        n = 0
        for i, line in enumerate(lines):
            if mask[i]:
                continue
            new_line, k = rule.find.subn(rule.repl, line)
            if k:
                n += k
                body = line.rstrip("\r\n")
                if body not in changed:
                    changed.append(f"L{i + 1}: {body}")
                lines[i] = new_line
        hits.append((rule.name, n, rule.expect))

    total = sum(n for _, n, _ in hits)
    for name, n, expect in hits:
        print(f"  规则「{name}」命中 {n} 次")
        if total and expect is not None and n != expect:
            print(f"[警告] 规则「{name}」命中 {n} 次，期望 {expect} 次。"
                  f"源文可能变了，请人工核对后再决定要不要继续。", file=sys.stderr)

    # ---- FIX-17：把「已经改过了」和「源文漂移了」分开判 ----
    # 正面证据 = 每条规则的 verify 在改写后命中；负面证据 = find 一处都不匹配。
    # 旧代码只看负面证据，于是这两种情况输出完全一样（[无改动] + exit 0）。
    post_text = "".join(lines)
    bad = [r for r in rules if r.verify is not None and not r.verify.search(post_text)]
    unverifiable = [r for r in rules if r.verify is None]
    has_marker = f"{MARKER_OPEN} {script_rel}" in text

    if total == 0:
        if bad:
            print("[漂移] 一条都没匹配上，且验收模式也不满足 —— 这不是「已经改过」，"
                  "是源文变了。未写入任何字节。", file=sys.stderr)
            for r in bad:
                print(f"        规则「{r.name}」：命中 0 次，验收模式在文件里找不到。",
                      file=sys.stderr)
            return 3
        if unverifiable:
            if not ALLOW_UNVERIFIED:
                print("[无法判定] 一条都没匹配上，但这些规则没有验收模式（verify=None），"
                      "分不清是「已改过」还是「源文漂移」。未写入任何字节。",
                      file=sys.stderr)
                for r in unverifiable:
                    print(f"        规则「{r.name}」缺 verify。", file=sys.stderr)
                print(f"        确认是幂等空转可设环境变量 PATCHLIB_ALLOW_UNVERIFIED=1 放行。",
                      file=sys.stderr)
                return 3
        print(f"[已是新版] {path.name}：{len(rules)} 条规则一处都没匹配上，"
              f"但全部验收模式命中，判定为上一轮已改过。"
              f"（归档标记{'在' if has_marker else '不在'}文件里）未写入任何字节。")
        return 0

    if bad:
        print("[漂移] 改写后验收模式不满足，拒绝写入。", file=sys.stderr)
        for r in bad:
            print(f"        规则「{r.name}」：改完也找不到验收模式。", file=sys.stderr)
        return 3

    block: list[str] = []
    block.append(f"{MARKER_OPEN} {script_rel}" + newline)
    block.append("     归档：下面每一行是本次改写前的原文（逐字保留；渲染时不可见）" + newline)
    for row in changed:
        block.append("     " + row + newline)
    block.append(MARKER_END + newline)
    while lines and not lines[-1].strip():
        lines.pop()
    lines.append(newline)                       # 空行隔开
    lines.extend(block)

    new_text = "".join(lines)
    after_bytes = len(new_text.encode("utf-8-sig" if has_bom else "utf-8"))
    after_lines = len(new_text.splitlines())
    print(f"[结果] 改写 {total} 处，涉及 {len(changed)} 行")
    print(f"[统计] 字节 {before_bytes} → {after_bytes}（{after_bytes - before_bytes:+d}）")
    print(f"[统计] 总行 {before_lines} → {after_lines}（{after_lines - before_lines:+d}）")
    if dry_run:
        print("[预演] --dry-run：未写入任何字节。")
        return 0
    write_text(path, new_text, has_bom)
    print(f"[已写] {path}")
    return 0
