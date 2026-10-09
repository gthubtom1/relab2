#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""SO/ELF 全量体检：节区、导出符号、导入、字符串、.init_array、构建 ID。

用于 APK 逆向里拿到 lib/*.so 后的第一轮结构确认，判断：架构、是否 strip、
是否有加固特征 so、JNI 入口在哪、构造函数有几个。

用法（Windows）:
    D:\\EXE\\python\\python.exe so-structure-audit.py libil2cpp.so
    D:\\EXE\\python\\python.exe so-structure-audit.py libtarget.so --jni --strings 256
"""
import argparse
import re
import sys
from pathlib import Path

try:
    from elftools.elf.elffile import ELFFile
    from elftools.elf.sections import SymbolTableSection
except ImportError as e:  # pragma: no cover
    sys.exit("缺少 pyelftools: %s\n用 D:\\EXE\\python\\python.exe 运行" % e)

MACHINE = {"EM_ARM": "ARM32", "EM_AARCH64": "ARM64",
           "EM_386": "x86", "EM_X86_64": "x86_64"}

# 加固厂商特征 so（文件名关键字 -> 厂商）
PACKER_HINTS = [
    ("jiagu", "爱加密"), ("DexHelper", "梆梆(bangcle)"), ("shell", "腾讯乐固/通用壳"),
    ("tprt", "腾讯乐固"), ("nqshield", "网易易盾"), ("legu", "乐固"),
    ("SecShell", "梆梆"), ("DexProtector", "DexProtector"),
    ("libexec", "通用执行壳"),
]


def sec_flags(sec):
    return "".join([
        "W" if sec["sh_flags"] & 0x1 else "-",
        "A" if sec["sh_flags"] & 0x2 else "-",
        "X" if sec["sh_flags"] & 0x4 else "-",
    ])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("so")
    ap.add_argument("--jni", action="store_true", help="列出 JNI 相关导出")
    ap.add_argument("--strings", type=int, default=0, metavar="N",
                    help="扫描可打印字符串，最短长度 N")
    ap.add_argument("--grep", default="", help="只显示含该子串的字符串")
    ap.add_argument("--max-sections", type=int, default=0, help="最多列出 N 个节区（0=全部）")
    args = ap.parse_args()

    path = Path(args.so)
    if not path.exists():
        sys.exit("文件不存在: %s" % path)

    blob = path.read_bytes()
    if blob[:4] != b"\x7fELF":
        sys.exit("不是 ELF: %s" % path)

    print("=" * 68)
    print("file      : %s" % path)
    print("size      : %d bytes" % len(blob))

    with path.open("rb") as f:
        elf = ELFFile(f)
        print("class     : ELF%d" % elf.elfclass)
        mach = elf.header["e_machine"]
        print("machine   : %s" % MACHINE.get(mach, mach))
        print("type      : %s" % elf.header["e_type"])
        print("entry     : 0x%x" % elf.header["e_entry"])
        print("stripped  : %s" % ("yes" if not elf.get_section_by_name(".symtab") else "no"))

        # 加固特征
        low = path.name.lower()
        for key, vendor in PACKER_HINTS:
            if key.lower() in low:
                print("packer?   : 文件名命中 '%s' -> 可能 %s" % (key, vendor))
                break

        # 节区
        print("\n-- sections --")
        secs = list(elf.iter_sections())
        show = secs if not args.max_sections else secs[: args.max_sections]
        for s in show:
            print("  %-20s %-16s %s addr=0x%-10x size=0x%-8x off=0x%-8x"
                  % (s.name or "<null>", s["sh_type"], sec_flags(s),
                     s["sh_addr"], s["sh_size"], s["sh_offset"]))
        if len(secs) > len(show):
            print("  ... 其余 %d 个节区省略" % (len(secs) - len(show)))

        # .init_array / .fini_array
        print("\n-- init_array / fini_array (构造函数 & 反调试入口) --")
        w = 8 if elf.elfclass == 64 else 4
        found = False
        for s in elf.iter_sections():
            if s.name in (".init_array", ".preinit_array", ".fini_array"):
                if s["sh_size"] == 0:
                    continue
                found = True
                d = s.data()
                for i in range(0, len(d) - w + 1, w):
                    print("  %s[%d] = 0x%08x"
                          % (s.name, i // w, int.from_bytes(d[i:i+w], "little")))
        if not found:
            print("  (无 —— 初始化逻辑不在构造函数里，查 JNI_OnLoad)")

        # build-id
        print("\n-- build-id --")
        found = False
        for seg in elf.iter_segments():
            if seg["p_type"] != "PT_NOTE":
                continue
            d = seg.data()
            # ELF note 头: namesz(4) descsz(4) type(4) name(name padded) desc(desc padded)
            if len(d) < 16:
                continue
            namesz = int.from_bytes(d[0:4], "little")
            descsz = int.from_bytes(d[4:8], "little")
            ntype = int.from_bytes(d[8:12], "little")
            name_end = 12 + namesz
            if d[12:16] != b"GNU\x00" or ntype != 3:
                continue
            desc = d[name_end:name_end + descsz]
            print("  %s" % desc.hex())
            found = True
            break
        if not found:
            print("  (无 GNU build-id)")

        # 导出符号
        dynsym = elf.get_section_by_name(".dynsym")
        if dynsym and isinstance(dynsym, SymbolTableSection):
            exports, imports, jni = [], [], []
            for sym in dynsym.iter_symbols():
                n = sym.name
                if not n:
                    continue
                if sym["st_shndx"] == "SHN_UNDEF":
                    imports.append(n)
                else:
                    exports.append((n, sym["st_value"], sym["st_size"]))
                    if n.startswith("Java_") or "JNI_OnLoad" in n:
                        jni.append((n, sym["st_value"], sym["st_size"]))
            print("\n-- exports -- %d 条" % len(exports))
            if args.jni:
                if jni:
                    for n, v, s in sorted(jni, key=lambda x: x[1]):
                        print("  JNI  %-60s addr=0x%-10x size=%d" % (n, v, s))
                else:
                    print("  (无 JNI_*/JNI_OnLoad 导出 -> 高度可能用 RegisterNatives 动态注册)")
            print("\n-- imports -- %d 条" % len(imports))
            for n in sorted(imports)[:40]:
                print("  %s" % n)
            if len(imports) > 40:
                print("  ... 其余 %d 条省略" % (len(imports) - 40))

    # 字符串
    if args.strings:
        pat = re.compile(rb"[\x20-\x7e]{%d,}" % args.strings)
        print("\n-- strings (>=%d) --" % args.strings)
        n = 0
        for m in pat.finditer(blob):
            s = m.group().decode("ascii", "replace")
            if args.grep and args.grep.lower() not in s.lower():
                continue
            print("  0x%08x  %s" % (m.start(), s))
            n += 1
            if n >= 200:
                print("  ... 超过 200 条截断")
                break

    print("\n" + "=" * 68)
    print("判据：")
    print("  stripped=yes + exports 极少 + imports 极少 -> 强混淆，考虑脱壳/虚拟化")
    print("  exports 无 JNI_* 且无 JNI_OnLoad        -> 走 RegisterNatives 动态注册追踪")
    print("  init_array 有多条                       -> 逐条反查（解密/反调试入口）")
    print("  文件名命中加固关键字                    -> 转 packer/vmp-dex2c-detection 判定形态")


if __name__ == "__main__":
    main()
