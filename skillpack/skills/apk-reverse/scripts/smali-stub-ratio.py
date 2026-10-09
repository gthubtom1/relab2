#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""统计 apktool 解包目录里 smali 方法的"空壳率"。

空壳方法 = 方法体只含 nop / return-void / return，即静态看不到业务逻辑。
空壳率偏高是抽取壳 / VMP / dex2c 的第一手信号。

用法（Windows）:
    D:\\EXE\\python\\python.exe smali-stub-ratio.py C:\\work\\apktool_out

    # 只看某个包路径下的 smali
    D:\\EXE\\python\\python.exe smali-stub-ratio.py C:\\work\\apktool_out --subpath smali_classes2
"""
import argparse
import re
import sys
from pathlib import Path

DIRECTIVE_PREFIXES = (".locals", ".param", ".line", ".prologue", ".annotation",
                      ".end annotation", ".local", ".source", ".debug",
                      ".registers", ".catch", ".catchall")

METHOD_RE = re.compile(r"^\.method\b", re.M)
END_RE = re.compile(r"^\.end method\b", re.M)
OP_RE = re.compile(r"^\s{4}(\S+)", re.M)

# 只由这些指令组成 => 视为空壳
STUB_OPS = {"nop", "return-void", "return"}
# 只有这些指令组成 => 视为 trivial（构造器/空 getter 也落这里，但不算强信号）
TRIVIAL_EXTRA = {"return-wide", "return-object"}


def analyze_smali(path: Path):
    text = path.read_text(encoding="utf-8", errors="ignore")
    total = stub = trivial = 0
    methods = list(METHOD_RE.finditer(text))
    for m in methods:
        end = END_RE.search(text, m.end())
        if end is None:
            continue
        body = text[m.end():end.start()]
        ops = [o for o in OP_RE.findall(body)
               if not o.startswith(".") and o not in DIRECTIVE_PREFIXES]
        if not ops:
            trivial += 1
            continue
        total += 1
        if set(ops) <= STUB_OPS:
            stub += 1
        elif set(ops) <= (STUB_OPS | TRIVIAL_EXTRA):
            trivial += 1
    return total, stub, trivial


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", help="apktool 解包目录")
    ap.add_argument("--subpath", default="", help="只统计该子目录，例如 smali_classes2")
    ap.add_argument("--top", type=int, default=10, help="列出空壳最多的前 N 个文件")
    args = ap.parse_args()

    root = Path(args.root)
    if not root.exists():
        sys.exit("路径不存在: %s" % root)
    if args.subpath:
        root = root / args.subpath
        if not root.exists():
            sys.exit("子路径不存在: %s" % root)

    files = sorted(root.rglob("*.smali"))
    if not files:
        sys.exit("没找到 .smali，先确认已 apktool d 解包: %s" % root)

    gt = gs = gtr = 0
    per_file = []
    for f in files:
        t, s, tr = analyze_smali(f)
        gt += t
        gs += s
        gtr += tr
        if s:
            per_file.append((s, t, f))

    denom = gt + gs + gtr
    print("scanned_files=%d" % len(files))
    print("methods=%d  stub(nop/return-only)=%d  trivial=%d" % (gt, gs, gtr))
    if denom:
        print("stub_ratio=%.1f%%  (全部分母含 trivial)" % (100.0 * gs / denom))
        print("stub_ratio_strict=%.1f%%  (只看有指令的方法)" % (100.0 * gs / max(gt, 1)))

    if per_file:
        print("\n-- stub 最多的文件 --")
        for s, t, f in sorted(per_file, reverse=True)[: args.top]:
            print("  %4d/%-4d  %s" % (s, t, f.relative_to(root)))

    print("\n判据：")
    print("  stub_ratio_strict < 10%   -> 常规应用，直接走 jadx 读逻辑")
    print("  stub_ratio_strict > 30%   -> 疑似抽取壳/VMP/dex2c，转 vmp-dex2c-detection 判定形态")
    print("  注意: 分母小的样本(方法数个位数)比例噪声大，看绝对数 stub 计数更有意义")


if __name__ == "__main__":
    main()
