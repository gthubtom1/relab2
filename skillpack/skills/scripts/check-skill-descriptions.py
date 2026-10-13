#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校验每个技能 SKILL.md 的 frontmatter `description` 是否满足"可被检索"的形状。

背景：宿主会把 description 预载进系统提示，作为**选择该技能的唯一信号**。
所以它必须是：单行、带"用于：/不要用于："、长度可控、不是 YAML 块标量。

规则（全部硬性）：
  1. 存在 `description:` 且**单行**（不能是 `|` / `>` / `|-` / `>-` 块标量）
  2. 长度（UTF-8 字节）在 60..600 之间
  3. 含 `用于：` 且含 `不要用于：`
  4. 不含换行、不含未转义的 `"` 造成的 YAML 破坏（用未加引号的 plain scalar）
  5. 不含 `务必使用此技能` / `Ensure to use this skill`（老式"抢触发"话术）

用法：
    python skills/scripts/check-skill-descriptions.py            # 检查
    python skills/scripts/check-skill-descriptions.py --json
退出码：0 全过／1 有问题
"""
from __future__ import annotations

import argparse
import glob
import io
import json
import os
import re
import sys

MIN_BYTES, MAX_BYTES = 60, 300
BANNED = ("务必使用此技能", "Ensure to use this skill", "MUST use this skill")


def check(path: str) -> list[str]:
    raw = io.open(path, "r", encoding="utf-8-sig", errors="replace").read()
    m = re.match(r"^---\s*\n(.*?)\n---", raw, re.S)
    if not m:
        return ["no frontmatter"]
    fm = m.group(1)
    dm = re.search(r"^description:[ \t]*(.*)$", fm, re.M)
    if not dm:
        return ["no description field"]
    val = dm.group(1).strip()
    errs: list[str] = []

    # 1. 块标量 / 多行
    if val in ("|", ">", "|-", ">-", "|+", ">+", "|2", ">2", "|2-", ">2-"):
        errs.append("description is a YAML block scalar (must be single line)")
    if val.startswith("|") or val.startswith(">"):
        errs.append("description starts with block indicator")
    # 2. 长度
    n = len(val.encode("utf-8"))
    if n < MIN_BYTES:
        errs.append(f"too short ({n} bytes < {MIN_BYTES})")
    if n > MAX_BYTES:
        errs.append(f"too long ({n} bytes > {MAX_BYTES})")
    # 3. 结构
    if "用于：" not in val:
        errs.append("missing `用于：`")
    if "不要用于：" not in val:
        errs.append("missing `不要用于：`")
    # 4. YAML 破坏（plain scalar 里出现 ": " 或 " #" 会出问题）
    if re.search(r":\s", val):
        errs.append("plain scalar contains ': ' (quote it or remove)")
    if re.search(r"\s#", val):
        errs.append("plain scalar contains ' #' (quote it or remove)")
    # 5. 老式抢触发话术
    for b in BANNED:
        if b in val:
            errs.append(f"contains legacy trigger phrase: {b}")
    return errs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--root", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    args = ap.parse_args()

    paths = sorted(glob.glob(os.path.join(args.root, "*", "SKILL.md")))
    bad: dict[str, list[str]] = {}
    sizes: list[tuple[int, str]] = []
    for p in paths:
        errs = check(p)
        name = os.path.basename(os.path.dirname(p))
        if errs:
            bad[name] = errs
        else:
            raw = io.open(p, "r", encoding="utf-8-sig", errors="replace").read()
            dm = re.search(r"^description:[ \t]*(.*)$", raw, re.M)
            sizes.append((len(dm.group(1).strip().encode("utf-8")), name))

    total = sum(s for s, _ in sizes)
    if args.json:
        print(json.dumps({
            "checked": len(paths), "ok": len(sizes), "bad": bad,
            "description_total_bytes": total, "approx_tokens": total // 3,
        }, ensure_ascii=False, indent=2))
    else:
        print(f"checked={len(paths)} ok={len(sizes)} bad={len(bad)}")
        print(f"description 合计 {total} 字节 ≈ {total // 3} tokens")
        if bad:
            print("\n有问题：")
            for name, errs in sorted(bad.items()):
                print(f"  {name}: {'; '.join(errs)}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
