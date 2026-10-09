#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""在 ARM64 ELF(.so) 里扫描 VMP/dex2c 解释器 dispatch 循环特征。

特征组合（静态判定 VMP/dex2c 加固 / VMProtect 虚拟化的核心）：
  1) LDRB / LDRB 变体从 [reg] 取字节   -> 从字节码流取 opcode
  2) AND imm  掩码操作                 -> opcode 提取 (opcode & 0xff)
  3) LDR Xt, [Xn, Xm, LSL #3]         -> 跳转表索引 (8 字节/项 handler 地址)
  4) BR Xn                             -> 间接跳转到 handler

单条指令几乎没有信息量，四条共现才是解释器信号。

用法（Windows）:
    D:\\EXE\\python\\python.exe find-vm-dispatch.py libil2cpp.so
    D:\\EXE\\python\\python.exe find-vm-dispatch.py libil2cpp.so --min-score 3
"""
import argparse
import struct
import sys
from pathlib import Path

try:
    from capstone import (Cs, CS_ARCH_ARM, CS_ARCH_ARM64,
                          CS_MODE_ARM, CS_MODE_LITTLE_ENDIAN)
    from elftools.elf.elffile import ELFFile
except ImportError as e:  # pragma: no cover
    sys.exit("缺少依赖 pefile/capstone/elftools: %s\n用 D:\\EXE\\python\\python.exe 运行" % e)


def load_code(path: Path):
    """返回 (instructions, arch_mode, meta)。只反汇编可执行节，跳过数据。"""
    data = path.read_bytes()
    if data[:4] != b"\x7fELF":
        sys.exit("不是 ELF 文件: %s" % path)

    meta = {}
    with path.open("rb") as f:
        elf = ELFFile(f)
        cls = elf.elfclass
        machine = elf.header["e_machine"]  # 'EM_AARCH64' or 'EM_ARM'
        meta["class"] = cls
        meta["machine"] = machine
        chunks = []
        # SHF_ALLOC=0x2, SHF_EXECINSTR=0x4
        for sec in elf.iter_sections():
            flags = sec["sh_flags"]
            if sec["sh_type"] == "SHT_NOBITS" or sec["sh_size"] == 0:
                continue
            if (flags & 0x2) and (flags & 0x4):
                chunks.append((sec["sh_addr"], sec.name, sec.data()))
        meta["baddr"] = elf.header["e_entry"]

    if machine == "EM_AARCH64":
        md = Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN)
    elif machine == "EM_ARM":
        md = Cs(CS_ARCH_ARM, CS_MODE_ARM)
    else:
        sys.exit("只支持 ARM/ARM64，当前: %s" % machine)
    md.detail = False
    md.skipdata = True

    ins = []
    for addr, name, blob in chunks:
        label = name or ".text"
        ins.append(("section:%s" % label, addr, 0, ""))
        for i in md.disasm(blob, addr):
            ins.append((label, i.address, i.size, i.mnemonic, i.op_str))
    return ins, cls, meta


def classify(mnemonic, op_str):
    """返回该指令命中的特征标签列表。"""
    tags = []
    m = mnemonic.lower()
    if m == "ldrb":
        tags.append("LDRB_opcode")
    elif m == "ldrh":
        tags.append("LDRH_opcode")
    elif m in ("and", "ands") and "#" in op_str:
        tags.append("AND_mask")
    elif m == "ldr" and ("lsl #3" in op_str or "uxtw" in op_str):
        tags.append("LDR_table_index")
    elif m == "adr" or (m == "add" and op_str.endswith("table")):
        tags.append("table_addr")
    elif m in ("br", "braa", "brab"):
        tags.append("BR_indirect_jump")
    elif m == "blr":
        tags.append("BLR_indirect_call")
    elif m in ("tbz", "tbnz"):
        tags.append("TBZ_branch")
    return tags


def score_window(tags, want=("LDRB_opcode", "AND_mask", "LDR_table_index", "BR_indirect_jump")):
    """四条核心特征缺几。≥3 才算强候选。"""
    return sum(1 for w in want if w in tags)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("so", help="目标 .so / ELF 文件")
    ap.add_argument("--min-score", type=int, default=3,
                    help="窗口内核心特征最少命中数（默认 3）")
    ap.add_argument("--window", type=int, default=24,
                    help="滑窗大小（指令条数，默认 24）")
    ap.add_argument("--top", type=int, default=15, help="输出前 N 个候选")
    args = ap.parse_args()

    path = Path(args.so)
    if not path.exists():
        sys.exit("文件不存在: %s" % path)

    ins, cls, meta = load_code(path)
    print("file      : %s" % path)
    print("elf_class : ELF%d  machine=%s  entry=0x%x"
          % (cls, meta["machine"], meta["baddr"]))
    print("insns     : %d" % len(ins))
    print()

    feats = []
    for rec in ins:
        if len(rec) == 5:
            feats.append(classify(rec[3], rec[4]))
        else:
            feats.append([])

    # 滑窗打分
    hits = []
    n = len(ins)
    window = max(2, min(args.window, n))
    for end in range(window, n + 1):
        win = range(end - window, end)
        tags = set()
        for k in win:
            tags.update(feats[k])
        s = score_window(tags)
        if s >= args.min_score:
            hits.append((s, end - window, end, sorted(tags)))
    # 去重: 窗口重叠的合并成一段区间
    merged = []
    for s, a, b, tags in hits:
        if merged and a <= merged[-1][2]:
            merged[-1][2] = max(merged[-1][2], b)
            merged[-1][3] |= set(tags)
            merged[-1][1] = max(merged[-1][1], s)
        else:
            merged.append([s, a, b, set(tags)])

    if not merged:
        print("未发现 dispatch 特征窗口（score>=%d）" % args.min_score)
        print("\n可能原因: 该 so 未做 VMP/dex2c 虚拟化；或经过 OLLVM 控制流平坦化（特征被打散）")
        return

    print("发现 %d 个 dispatch 候选区间:\n" % len(merged))
    for s, a, b, tags in sorted(merged, reverse=True)[: args.top]:
        va = ins[a][1]
        print("[score=%d]  0x%x - 0x%x   (%d insns)" % (s, va, ins[b - 1][1], b - a))
        print("   特征: %s" % ", ".join(sorted(tags)))
        for rec in ins[a:min(b, a + 12)]:
            if len(rec) == 5:
                print("     0x%x  %-8s %s" % (rec[1], rec[3], rec[4]))
        print()

    print("判据：")
    print("  有候选 + jadx 里目标方法体是 nop/stub  -> 形态 A: 商业 dex2c/VMP 壳")
    print("  有候选 + jadx Java 层完全可读          -> 形态 B: so 内函数被虚拟化(VMProtect 类)")
    print("  下一跳: vmp-dump-trace-recovery (trace 解释器) / obf-compile-detect (静态混淆)")


if __name__ == "__main__":
    main()
