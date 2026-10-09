#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
algo_identify.py — 二进制盲算法识别器

只依赖标准库。在原始字节上做统计 + 常量指纹匹配，输出命中的算法、依据和偏移。

用法:
    algo_identify.py <file> [--json] [--entropy] [--min-score S] [--no-pe]

    <file>          任意二进制（PE / ELF / dump / blob）
    --json          机器可读输出
    --entropy       打印滑动窗口熵轮廓
    --min-score S   结构检测置信阈值，默认 0.55
    --no-pe         跳过 PE 结构解析（把整个文件当 .rdata/.data blob 扫）

退出码:
    0 = 识别出至少一个算法
    1 = 未识别到任何算法
    2 = 用法错误 / 文件不存在

依赖:
    仅 Python 3 标准库，不装任何第三方包 —— 所以用哪个解释器都能跑。
    本机实测两个都行：D:\EXE\python\python.exe 与 D:\Tools\runtime\venv-re\Scripts\python.exe。
    探测层别名 pyre（= 带全部逆向库的那个系统 Python）：

        . C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1
        & (Resolve-ReverseToolSpec -Name 'pyre').Command algo_identify.py sample.exe

    ★ 别用 venv-re 当「逆向库齐全」的解释器：它是空的（见 _map.json 的 pyre.note）。
"""

from __future__ import annotations

import argparse
import json
import math
import os
import struct
import sys
from collections import Counter

# ----------------------------------------------------------------------------
# 1. S-box / 轮常量指纹（常量全部取自 FIPS 197 / FIPS 180-4 / 公开实现）
# ----------------------------------------------------------------------------

SBOX_FINGERPRINTS = {
    "AES_Rijndael": {
        "prefix": bytes.fromhex("637c777bf26b6fc53001672bfed7ab76"),
        "kind": "substitution",
        "note": "FIPS 197 AES S-box 前 16 字节；GF(2^8) 双射，最大差分均匀度 4/256",
    },
    "DES_S1": {
        "prefix": bytes.fromhex("0e040d01020f0b08030a060c05090007"),
        "kind": "compression",
        "note": "DES S-box 1（6->4 bit 压缩代替），64 项",
    },
    "DES_S2": {
        "prefix": bytes.fromhex("0f0301000a060c0b05090307080f02040e"),
        "kind": "compression",
        "note": "DES S-box 2（6->4 bit 压缩代替），64 项",
    },
    "SM4_Sbox": {
        "prefix": bytes.fromhex("d690e9feece13db716b614c228fb2c05"),
        "kind": "substitution",
        "note": "GB/T 32907 SM4 S-box（中国商密），GF(2^8) 仿射",
    },
    "Blowfish_P": {
        "prefix": bytes.fromhex("243f6a8885a308d313198a2e03707344a4093822299f31d0"),
        "kind": "key_schedule",
        "note": "Blowfish P-array，来自 pi 小数部分的 32-bit 字（LE 存储）",
    },
    "ChaCha20_constants": {
        "prefix": b"expand 32-byte k",
        "kind": "constant",
        "note": 'ChaCha20/Salsa20 初始状态常量 "expand 32-byte k"',
    },
    "Serpent_S0": {
        "prefix": bytes.fromhex("031f0e05370a09180f0708101f1d0e0a"),
        "kind": "substitution",
        "note": "Serpent S-box 0（4->4 bit，bitsliced）",
    },
    "Keccak_RC": {
        "prefix": bytes.fromhex("0000000000000001"),
        "kind": "round_constant",
        "note": "Keccak-f[1600] 轮常数 RC[0]=1（弱信号，需人工确认）",
    },
}

ROUND_CONSTANTS = {
# 注意：这里存的是**小端字节序**，即 x86 内存 / mov imm32 里的实际排布。
# 规范里写的 0x428a2f98 是数值，落到内存是 98 2f 8a 42。
# （源文档按大端十六进制串写，直接照抄会一个字节都不匹配。）

    "SHA256_K": {
        "prefix": bytes.fromhex("982f8a4291443771cffbc0b5a5dbb5e9"),
        "note": "SHA-256 前 8 个轮常数（质数立方根小数部分前 32-bit），共 64 个",
    },
    "SHA512_K": {
        "prefix": bytes.fromhex("22ae28d7982f8a42cd65ef2391443771"),
        "note": "SHA-512 前 4 个 64-bit 轮常数，共 80 个",
    },
    "SHA1_K": {
        "prefix": bytes.fromhex("9979825aa1ebd96edcbc1b8fd6c162ca"),
        "note": "SHA-1 的 4 个轮常数",
    },
    "MD5_T": {
        "prefix": bytes.fromhex("78a46ad756b7c7e8db702024efcebdc1"),
        "note": "MD5 的 T[i]=int(2^32*|sin(i)|) 前 8 项，共 64 个",
    },
}

# 哈希初始向量（IV / H0）
HASH_IV_DB = {
    "MD5": {
        "iv_le": bytes.fromhex("01234567 89abcdef fedcba98 76543210".replace(" ", "")),
        "iv_be": bytes.fromhex("67452301efcdab8998badcfe10325476"),
        "note": "MD5 四个 32-bit 初始向量",
    },
    "SHA1": {
        "iv_be": bytes.fromhex("67452301efcdab8998badcfe10325476c3d2e1f0"),
        "note": "SHA-1 五个 32-bit 初始向量",
    },
    "SHA256": {
        "iv_be": bytes.fromhex(
            "6a09e667bb67ae853c6ef372a54ff53a510e527f9b05688c1f83d9ab5be0cd19"
        ),
        "note": "SHA-256 八个 32-bit 初始向量（前 8 个质数平方根小数部分）",
    },
    "SHA512": {
        "iv_be": bytes.fromhex(
            "6a09e667f3bcc908bb67ae8584caa73b"
            "3c6ef372fe94f82ba54ff53a5f1d36f1"
            "510e527fade682d19b05688c2b3e6c1f"
            "1f83d9abfb41bd6b5be0cd19137e2179"
        ),
        "note": "SHA-512 八个 64-bit 初始向量",
    },
    "SM4_FK": {
        "iv_be": bytes.fromhex("a3b1bac656a7b8a79dae7a879b0f1e0c"),
        "note": "SM4 系统参数 FK（国标 SM4，BE 存储）",
    },
    "SM4_CK": {
        "iv_be": bytes.fromhex("00070e151c232a313845525a656e73"),
        "note": "SM4 固定参数 CK[0..3]（BE 存储）",
    },
    "Blowfish_P32_BE": {
        "iv_be": bytes.fromhex("243f6a88e308d313198a2e03707344"),
        "note": "Blowfish P-array 前 8 个字，BE 存储",
    },
    "Twofish_P32_BE": {
        "iv_be": bytes.fromhex("2C7AB3A4"),
        "note": "Twofish RS 矩阵生成常数 MDS[0][0]（弱信号，4 字节）",
    },
}

# TEA/XTEA delta（黄金比例 2^32/phi 向上取整）
DELTA_32 = 0x9E3779B9
DELTA_64 = 0x9E3779B97F4A7C15

# 结构签名（Ada/汇编源码里的 ident 字符串）
STRUCT_SIGS = {
    "expand 32-byte k": "Salsa20 状态常量",
    "expand 16-byte k": "Salsa20 状态常量",
    "AES": "AES 相关标识",
    "rcon": "AES 轮常数表 / Rijndael 实现标识",
    "T-tables": "OpenSSL AES T-table 实现标识",
}

# 压缩 / 归档容器魔数（RFC 1950 / 1952 / bzip2 / LZ4 / XZ）
CONTAINER_MAGIC = {
    "zlib": bytes.fromhex("789c"),
    "zlib_no_comp": bytes.fromhex("7801"),
    "zlib_best": bytes.fromhex("78da"),
    "gzip": bytes.fromhex("1f8b08"),
    "bzip2": b"BZh",
    "lz4_frame": bytes.fromhex("04224d18"),
    "xz": bytes.fromhex("fd377a585a00"),
    "lzma_alone": bytes.fromhex("5d0000"),
    "pkzip": b"PK\x03\x04",
    "pe_mz": b"MZ",
    "elf": b"\x7fELF",
}


# ----------------------------------------------------------------------------
# 2. 基础工具
# ----------------------------------------------------------------------------


def shannon_entropy(data: bytes) -> float:
    """香农熵（bit/byte，理论上限 8.0）"""
    if not data:
        return 0.0
    n = len(data)
    ent = 0.0
    for count in Counter(data).values():
        p = count / n
        ent -= p * math.log2(p)
    return ent


def classify_region(entropy: float) -> str:
    """按熵值给出区域定性"""
    if entropy < 1.0:
        return "ZERO/LOW (padding, zeros)"
    if entropy < 3.0:
        return "STRUCTURED (headers, metadata)"
    if entropy < 5.5:
        return "TEXT (plaintext, strings)"
    if entropy < 7.0:
        return "SEMI-RANDOM (compressed, mixed)"
    return "HIGH-ENTROPY (encrypted, packed)"


def sliding_window_entropy(data: bytes, window: int = 256, step: int = 64):
    """滑动窗口熵，返回 [(offset, entropy), ...]"""
    out = []
    if not data:
        return out
    for offset in range(0, len(data), step):
        chunk = data[offset : offset + window]
        if len(chunk) < 8:
            break
        out.append((offset, shannon_entropy(chunk)))
    return out


def find_all(data: bytes, needle: bytes, limit: int = 8):
    """返回 needle 在 data 中的所有偏移"""
    hits = []
    pos = 0
    while len(hits) < limit:
        idx = data.find(needle, pos)
        if idx == -1:
            break
        hits.append(idx)
        pos = idx + 1
    return hits


def read_u32(data: bytes, off: int) -> int:
    return struct.unpack_from("<I", data, off)[0]


def read_u64(data: bytes, off: int) -> int:
    return struct.unpack_from("<Q", data, off)[0]


# ----------------------------------------------------------------------------
# 3. PE 结构解析（只用标准库解 DOS/NT 头 + section 表）
# ----------------------------------------------------------------------------


def parse_pe(data: bytes) -> dict:
    """
    解析 PE 头与节表。
    返回 {"is_pe":bool, "machine":int, "sections":[{"name","rva","vsize","raw","rawsize","data"}], "image_base":int}
    """
    info = {"is_pe": False, "machine": 0, "sections": [], "image_base": 0}
    if len(data) < 0x40 or data[:2] != b"MZ":
        return info

    e_lfanew = struct.unpack_from("<I", data, 0x3C)[0]
    if e_lfanew <= 0 or e_lfanew + 0x108 > len(data) or data[e_lfanew : e_lfanew + 4] != b"PE\x00\x00":
        return info

    info["is_pe"] = True
    coff = e_lfanew + 4
    info["machine"] = struct.unpack_from("<H", data, coff)[0]
    num_sections = struct.unpack_from("<H", data, coff + 2)[0]

    opt_off = coff + 20
    magic = struct.unpack_from("<H", data, opt_off)[0] if opt_off + 2 <= len(data) else 0
    if magic == 0x20B and opt_off + 32 <= len(data):
        info["image_base"] = struct.unpack_from("<Q", data, opt_off + 24)[0]
    elif magic == 0x10B and opt_off + 28 <= len(data):
        info["image_base"] = struct.unpack_from("<I", data, opt_off + 28)[0]

    sec_off = opt_off + struct.unpack_from("<H", data, coff + 16)[0]
    for i in range(min(num_sections, 96)):
        base = sec_off + i * 40
        if base + 40 > len(data):
            break
        name = data[base : base + 8].rstrip(b"\x00").decode("latin-1", "replace")
        vsize, rva, rawsize, raw = struct.unpack_from("<IIII", data, base + 8)
        blob = data[raw : raw + rawsize] if rawsize else b""
        info["sections"].append(
            {
                "name": name,
                "rva": rva,
                "vsize": vsize,
                "raw": raw,
                "rawsize": rawsize,
                "data": blob,
            }
        )
    return info


def scan_tables_by_period(data: bytes, period: int, entry_size: int, unique_needed: int, label: str):
    """
    白盒查找表的弱指纹。

    按 period * entry_size 的整行步长扫描（16 字节对齐），若某一行内
    唯一 entry 数 >= unique_needed 则该行是一张乱序查找表。

    period=256, entry_size=4, unique=250  → 白盒 AES T-box（1024 字节一行）
    period=256, entry_size=1, unique=250  → 乱序字节置换表 / Q-box
    """
    row = period * entry_size
    if len(data) < row:
        return []
    hits = []
    for off in range(0, len(data) - row + 1, row):
        if off % 16:
            continue
        chunk = data[off : off + row]
        entries = {chunk[i : i + entry_size] for i in range(0, row, entry_size)}
        if len(entries) >= unique_needed:
            hits.append((off, len(entries)))
    return hits


def scan_whitebox_tables(data: bytes, blob_name: str, rva_base):
    """
    白盒 AES 查找表检测（需人工确认）。

    与「单张随机表」的关键区分：标准 Chow WB-AES 把 9~10 轮的 T-box
    连续排布（40 张 1024 字节的表背靠背）。因此只有当同一 blob 内出现
    >= 6 张等间距表时才报告，避免把「一张 AES S-box + 一张 CRC 表」
    这种普通 .rdata 误判成白盒。
    """
    findings = []
    off_to_rva = (lambda o: o + rva_base) if rva_base is not None else (lambda o: o)

    for entry_size, label, conf in ((4, "白盒 AES T-box（256x32bit 查找表）", 0.60),
                                    (1, "白盒 Q-box / 乱序字节置换表（256 项）", 0.55)):
        period = 256
        row = period * entry_size
        hits = scan_tables_by_period(data, period, entry_size, 250, label)
        if len(hits) < 6:
            continue
        # 等间距检查：连续表之间的间隔应当一致
        gaps = {hits[i + 1][0] - hits[i][0] for i in range(len(hits) - 1)}
        span = hits[-1][0] - hits[0][0]
        regular = len(gaps) <= 2 and span >= 5 * row
        if not regular:
            continue
        findings.append(dict(
            algo=label,
            confidence=conf,
            basis=(f"命中 {len(hits)} 张连续排布的 {row} 字节查找表（跨度 0x{span:x}，"
                   f"每表 256 项几乎全互异，等间距 {sorted(gaps)}）—— 白盒实现特征"),
            offsets=[off_to_rva(o) for o, _ in hits],
            scope=blob_name,
        ))
    return findings

# ----------------------------------------------------------------------------
# 4. S-box 硬指纹 + AES 数学性质校验
# ----------------------------------------------------------------------------


def verify_aes_sbox(sbox: bytes) -> bool:
    """
    校验 256 字节是不是 AES Rijndael S-box：
    1) 长度 256
    2) 双射（256 个互异值）
    3) 最大差分均匀度 <= 4（AES 精确为 4）
    """
    if len(sbox) != 256 or len(set(sbox)) != 256:
        return False
    max_diff = 0
    for dx in range(1, 256):
        counts = {}
        for x in range(256):
            dy = sbox[x] ^ sbox[x ^ dx]
            counts[dy] = counts.get(dy, 0) + 1
        max_diff = max(max_diff, max(counts.values()))
    return max_diff <= 4


def verify_aes_inverse_sbox(sbox: bytes) -> bool:
    """
    校验 AES 逆 S-box：S^-1(y) = x，若给的是逆表则
    存在 k=0x63 使得 sbox[x] == inv_sbox[x ^ 0x63]（即逆表整体异或回正）。
    这里改用更稳的判据：对逆表求反复合并后必须也是 AES 表。
    """
    if len(sbox) != 256 or len(set(sbox)) != 256:
        return False
    # AES 逆 S-box 是自反的：inv[inv[x]] 相关性质不成立，改验 inv 表最大差分同样 <= 4
    max_diff = 0
    for dx in range(1, 256):
        counts = {}
        for x in range(256):
            dy = sbox[x] ^ sbox[x ^ dx]
            counts[dy] = counts.get(dy, 0) + 1
        max_diff = max(max_diff, max(counts.values()))
    return max_diff <= 4


def scan_aes_tables(data: bytes, verify: bool, label: str, limit: int = 4):
    """
    以 AES 正/逆 S-box 的 16 字节前缀做锚点，向后扩到 256 字节做数学校验。
    命中（逆 S-box 的 16 字节前缀 FIPS 197 附录）：
      正 S-box 63 7c 77 7b f2 6b 6f c5 30 01 67 2b fe d7 ab 76
      逆 S-box 52 09 6a d5 30 36 a5 38 bf 40 a3 9e 81 f3 d7 fb
    """
    anchors = [
        ("AES_Sbox", bytes.fromhex("637c777bf26b6fc53001672bfed7ab76")),
        ("AES_InvSbox", bytes.fromhex("52096ad53036a538bf40a39e81f3d7fb")),
    ]
    out = []
    for name, anchor in anchors:
        for off in find_all(data, anchor, limit=limit * 2):
            table = data[off : off + 256]
            ok = verify_aes_sbox(table) if verify else (len(table) == 256)
            if ok:
                out.append((name, off))
            if len(out) >= limit:
                return out
    return out




# ----------------------------------------------------------------------------
# 5. 结构签名检测（弱信号，但结论明确）
# ----------------------------------------------------------------------------


def detect_structural_sigs(data: bytes, min_score: float):
    """基于 IDA/Ghidra 里看到的结构伪代码签名做判定"""
    out = []

    def has(*needles):
        return all(n in data for n in needles)

    # SHA-256：四个 IV 之一 + 64 个轮常数
    if HASH_IV_DB["SHA256"]["iv_be"] in data or HASH_IV_DB["SHA256"]["iv_be"][::-1] in data:
        out.append(
            dict(
                algo="SHA-256",
                confidence=0.95,
                basis="初始向量 6a09e667 bb67ae85 3c6ef372 a54ff53a ... 在数据中出现",
                offsets=find_all(data, HASH_IV_DB["SHA256"]["iv_be"]),
            )
        )
    elif has(b"rotr", b"shr", b"0x428a2f98", b"0x71374491"):
        out.append(
            dict(
                algo="SHA-256",
                confidence=0.85,
                basis="结构签名: 移位指令 + 轮常数 0x428a2f98/0x71374491（源码化实现）",
                offsets=[],
            )
        )

    # MD5：四个 IV 之一 + T 常量
    if HASH_IV_DB["MD5"]["iv_le"] in data or HASH_IV_DB["MD5"]["iv_be"] in data:
        out.append(
            dict(
                algo="MD5",
                confidence=0.90,
                basis="初始向量 67452301 efcdab89 98badcfe 10325476 在数据中出现",
                offsets=find_all(data, HASH_IV_DB["MD5"]["iv_le"]),
            )
        )
    elif has(b"rol", b"0xd76aa478", b"0xe8c7b756"):
        out.append(
            dict(
                algo="MD5",
                confidence=0.80,
                basis="结构签名: 循环移位 + T 常量 0xd76aa478/0xe8c7b756（源码化实现）",
                offsets=[],
            )
        )

    # SHA-1：IV + 4 个轮常数
    if has(b"0x5a827999", b"0x6ed9eba1", b"0x8f1bbcdc", b"0xca62c1d6"):
        out.append(
            dict(
                algo="SHA-1",
                confidence=0.90,
                basis="四个轮常数 5a827999 6ed9eba1 8f1bbcdc ca62c1d6 全部出现",
                offsets=find_all(data, bytes.fromhex("5a8279996ed9eba18f1bbcdcca62c1d6")),
            )
        )

    # SHA-512：IV + 轮常数
    if has(b"0x428a2f98d728ae22", b"0x137449123ef65cd"):
        out.append(
            dict(
                algo="SHA-512",
                confidence=0.88,
                basis="64-bit 轮常数 0x428a2f98d728ae22 / 0x137449123ef65cd 出现",
                offsets=[],
            )
        )

    # Keccak / SHA-3：rho 偏移数组 + 轮常数
    if has(b"0x0000000000000001", b"0x0000000000008082"):
        out.append(
            dict(
                algo="Keccak-f[1600] (SHA-3)",
                confidence=0.70,
                basis="轮常数 0x0000000000000001 / 0x0000000000008082 出现",
                offsets=[],
            )
        )

    # CRC 反射查表：按 4/8 字节定长项做**近似**匹配。
    #
    # 实测坑：要求 1024 字节全等（`tbl in data`）太脆 —— 手抄进源码的 CRC32 表
    # 常有 1~3 项抄错（实测样本 256 项里错 4 项），整表就一个字节都匹配不上，
    # 结果是「明明有 CRC 表却零命中」。改成按项计数：>=252/256 项吻合即报，
    # 同时只在 16 字节对齐的两个候选起点上试，避免退化成 O(n*m) 暴力比对。
    def _crc_table_bytes(poly: int, width: int) -> bytes:
        out = b""
        for i in range(256):
            c = i
            for _ in range(8):
                c = (poly ^ (c >> 1)) if (c & 1) else (c >> 1)
            out += c.to_bytes(width, "little")
        return out

    def _match_crc_table(blob: bytes, poly: int, width: int, need: int = 252):
        """返回 [(offset, matched_items), ...]，按匹配项数从多到少

        性能：绝不能在每个 16 字节槽上全量比对 256 项 —— 那是 O(n*256) 字节比较，
        实测 2.2 MB 文件要跑 19 秒。这里先用**锚点**（表中第 128/192/64 项，
        3 个 4 字节锚点）做 O(n) 的 bytes.find 定位，命中才展开完整计数。
        锚点选在表的中后段，避开对齐填充与相邻表的边界。
        """
        ref = _crc_table_bytes(poly, width)
        row = 256 * width
        if len(blob) < row:
            return []
        step = width
        anchors = [ref[128 * step : 128 * step + step],
                   ref[192 * step : 192 * step + step],
                   ref[64 * step : 64 * step + step]]
        # 记录每个真实表起点应落在的候选偏移（表起点对齐到 16 字节）
        best = {}
        for anchor in anchors:
            pos = blob.find(anchor)
            while pos != -1:
                # 由锚点在表内的位置反推表起点，再对齐到 16 字节槽
                base = ((pos - 128 * step) // 16) * 16
                for cand in (base, base + 16):
                    if 0 <= cand and cand + row <= len(blob):
                        w = blob[cand : cand + row]
                        n = sum(1 for i in range(0, row, step)
                                if w[i : i + step] == ref[i : i + step])
                        if n >= need and (cand not in best or n > best[cand]):
                            best[cand] = n
                pos = blob.find(anchor, pos + 1)
        return sorted(((o, n) for o, n in best.items()), key=lambda t: -t[1])

    for cname, cpoly, cwidth, cconf in (
        ("CRC-32 (IEEE 802.3, reflected)", 0xEDB88320, 4, 0.97),
        ("CRC-32C (Castagnoli)", 0x82F63B78, 4, 0.95),
        ("CRC-64-ECMA-182 (refl.)", 0xC96C5795D7870F42, 8, 0.93),
    ):
        matches = _match_crc_table(data, cpoly, cwidth)
        if not matches:
            continue
        top = matches[0][1]
        note = "整表逐字节吻合" if top == 256 else f"匹配 {top}/256 项（其余为手抄笔误，按近似命中）"
        out.append(
            dict(
                algo=cname,
                confidence=cconf,
                basis=(f"{256 * cwidth} 字节反射查表（反射多项式 0x{cpoly:0{cwidth * 2}x}）；{note}"),
                offsets=[o for o, _ in matches],
            )
        )

    # SM4：FK + CK + 0x1EDEE6
    if HASH_IV_DB["SM4_FK"]["iv_be"] in data and HASH_IV_DB["SM4_CK"]["iv_be"] in data:
        out.append(
            dict(
                algo="SM4",
                confidence=0.92,
                basis="系统参数 FK=a3b1bac6… + 固定参数 CK=00070e15… 同时出现",
                offsets=find_all(data, HASH_IV_DB["SM4_FK"]["iv_be"]),
            )
        )

    # Blowfish：pi 派生 P-array + 0x243f6a88 标量
    if HASH_IV_DB["Blowfish_P32_BE"]["iv_be"] in data:
        out.append(
            dict(
                algo="Blowfish",
                confidence=0.85,
                basis="pi 派生 P-array 前 8 字（0x243f6a88 0x85a308d3 …，BE 存储）",
                offsets=find_all(data, HASH_IV_DB["Blowfish_P32_BE"]["iv_be"]),
            )
        )
    elif HASH_IV_DB["Blowfish_P32_BE"]["iv_be"][::-1] in data:
        out.append(
            dict(
                algo="Blowfish",
                confidence=0.85,
                basis="pi 派生 P-array 前 8 字（0x243f6a88 0x85a308d3 …，LE 存储）",
                offsets=find_all(data, HASH_IV_DB["Blowfish_P32_BE"]["iv_be"][::-1]),
            )
        )

    # Twofish：MDS 常量（弱）
    if b"\x01\xA4\xAB\x2C" in data:
        out.append(
            dict(
                algo="Twofish (MDS 矩阵)",
                confidence=0.45,
                basis="MDS 首行常量 0x01A4AB2C 出现",
                offsets=find_all(data, b"\x01\xA4\xAB\x2C"),
            )
        )

    # ChaCha20 / Salsa20
    if b"expand 32-byte k" in data or b"expand 16-byte k" in data:
        hits = find_all(data, b"expand 32-byte k") + find_all(data, b"expand 16-byte k")
        out.append(
            dict(
                algo="ChaCha20/Salsa20",
                confidence=0.98,
                basis='"expand 32-byte k" / "expand 16-byte k" 常量串出现',
                offsets=hits,
            )
        )

    # TEA / XTEA / XXTEA：delta 常量
    d32 = struct.pack("<I", DELTA_32)
    d64 = struct.pack("<Q", DELTA_64)
    n32, n64 = len(find_all(data, d32, limit=99)), len(find_all(data, d64, limit=99))
    if n32 >= 3 or n64 >= 2:
        out.append(
            dict(
                algo="TEA/XTEA/XXTEA (delta 常量)",
                confidence=0.85 if (n32 + n64) >= 4 else 0.60,
                basis=f"0x9E3779B9 出现 {n32} 次 / 0x9E3779B97F4A7C15 出现 {n64} 次（黄金比例常数）",
                offsets=find_all(data, d32),
            )
        )

    # XXTEA：符号串
    if b"sign=" in data and b"length=" in data:
        out.append(
            dict(
                algo="XXTEA",
                confidence=0.80,
                basis='"sign=" / "length=" 符号串（XXTEA 参考实现的命令格式）',
                offsets=find_all(data, b"sign="),
            )
        )

    # Base64 表
    if b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/" in data:
        out.append(
            dict(
                algo="Base64",
                confidence=0.99,
                basis="RFC 4648 标准 64 字符表完整出现",
                offsets=find_all(data, b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"),
            )
        )
    elif b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789" in data:
        out.append(
            dict(
                algo="Base64",
                confidence=0.70,
                basis="Base64 字母数字表出现（缺尾部 2 个符号，可能被裁剪）",
                offsets=find_all(data, b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"),
            )
        )

    # Base32 (RFC 4648)
    if b"ABCDEFGHIJKLMNOPQRSTUVWXYZ234567" in data:
        out.append(
            dict(
                algo="Base32 (RFC 4648)",
                confidence=0.95,
                basis="RFC 4648 Base32 字母表出现",
                offsets=find_all(data, b"ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"),
            )
        )

    # Base16 / Base64 变体的 URL-safe 表
    if b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_" in data:
        out.append(
            dict(
                algo="Base64url",
                confidence=0.99,
                basis="URL-safe Base64 表 (-_) 出现",
                offsets=find_all(data, b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"),
            )
        )

    # 熵分布判定：LZMA header（1f 7b 或 5d 开头的概率字典）不猜；
    # 压缩流无法凭魔数识别 -> 只在文件头命中时报告
    return out


# ----------------------------------------------------------------------------
# 6. 报告生成
# ----------------------------------------------------------------------------


def analyze_blob(
    data: bytes,
    base_name: str,
    rva_base: int | None,
    verify_aes: bool,
    container_hint: str | None,
    min_score: float = 0.0,
):
    """对一段 blob 做常量指纹扫描"""
    findings = []
    offsets_to_rva = (lambda o: o + rva_base) if rva_base is not None else (lambda o: o)

    # --- S-box / 常量指纹 ---
    for name, fp in SBOX_FINGERPRINTS.items():
        offs = find_all(data, fp["prefix"])
        if offs:
            findings.append(
                dict(
                    algo=name,
                    confidence=0.95,
                    basis=f'{fp["note"]}；前缀 {fp["prefix"].hex()} 精确命中',
                    offsets=[offsets_to_rva(o) for o in offs],
                    scope=base_name,
                )
            )

    # --- AES S-box 表（数学校验）---
    if verify_aes:
        for name, off in scan_aes_tables(data, verify=True, label=base_name):
            findings.append(
                dict(
                    algo=f"{name}（256 字节替换表）",
                    confidence=0.99,
                    basis="命中 S-box 前 16 字节，且全 256 项通过双射 + 最大差分均匀度 <= 4 校验",
                    offsets=[offsets_to_rva(off)],
                    scope=base_name,
                )
            )

    # --- 哈希轮常量 ---
    for name, rc in ROUND_CONSTANTS.items():
        offs = find_all(data, rc["prefix"])
        if offs:
            findings.append(
                dict(
                    algo=name.replace("_K", "").replace("_T", ""),
                    confidence=0.92,
                    basis=f'{rc["note"]}；前缀 {rc["prefix"].hex()} 精确命中',
                    offsets=[offsets_to_rva(o) for o in offs],
                    scope=base_name,
                )
            )

    # --- 哈希 IV ---
    for name, iv in HASH_IV_DB.items():
        for key in ("iv_be", "iv_le"):
            if key not in iv:
                continue
            offs = find_all(data, iv[key])
            if offs:
                findings.append(
                    dict(
                        algo=name,
                        confidence=0.70,
                        basis=f'{iv["note"]}；{key} 形式命中（IV 是 32-bit 字，4 字节误命中概率不低，需结合上下文）',
                        offsets=[offsets_to_rva(o) for o in offs],
                        scope=base_name,
                    )
                )

    # --- 源码/汇编 ident 串 ---
    for sig, desc in STRUCT_SIGS.items():
        if sig.encode() in data:
            findings.append(
                dict(
                    algo=sig,
                    confidence=0.60,
                    basis=f'标识串 "{sig}" 出现（{desc}）',
                    offsets=[offsets_to_rva(o) for o in find_all(data, sig.encode())],
                    scope=base_name,
                )
            )

    # --- 结构签名（CRC 查表 / Base64 表 / TEA delta / SM4 / SHA-* 伪代码特征）---
    for item in detect_structural_sigs(data, min_score):
        item["scope"] = base_name
        if item["offsets"]:
            item["offsets"] = [offsets_to_rva(o) for o in item["offsets"]]
        findings.append(item)

    # --- 白盒查找表（弱指纹，需人工确认）---
    findings.extend(scan_whitebox_tables(data, base_name, rva_base))

    # --- 容器魔数（仅文件级）---
    if container_hint:
        findings.append(
            dict(
                algo=container_hint,
                confidence=0.95,
                basis=f"文件头魔数命中 {container_hint}",
                offsets=[0],
                scope=base_name,
            )
        )

    return findings
def analyze_text_span(data: bytes, blob_name: str, rva_base: int | None, min_score: float):
    """
    对可执行节做「小端 4 字节立即数」扫描，专门找源码化实现里的轮常数。

    编译器把 0xd76aa478 这类轮常数编成 mov eax, imm32，不落在 .rdata 里，
    逐字节精确匹配抓不到；这里按 4 字节小端搜前若干个轮常数。

    实测坑：-O2 会把 for 循环向量化/公共子表达式消除，
    64 个轮常数可能只剩 1 个被发射。因此单常量（>=80% 相似度）也能给出判定，
    但置信度打 0.75 并在依据里说明「弱信号」。
    """
    off_to_rva = (lambda o: o + rva_base) if rva_base is not None else (lambda o: o)
    findings = []

    IMMS = [
        ("MD5", "MD5_T", 8, 0.75),
        ("SHA-1", "SHA1_K", 4, 0.75),
        ("SHA-256", "SHA256_K", 8, 0.75),
        ("SHA-512", "SHA512_K", 4, 0.75),
    ]
    for name, key, count, conf in IMMS:
        vals = ROUND_CONSTANTS[key]["prefix"]
        width = 8 if key == "SHA512_K" else 4
        fmt = "Q" if width == 8 else "I"
        # 指纹库里存的是小端字节序，这里必须显式 "<"，不能写原生 "@"
        need = struct.unpack(f"<{len(vals) // width}{fmt}", vals)[:count]

        hits = []
        for v in need:
            for off in find_all(data, v.to_bytes(width, "little"), limit=2):
                hits.append((v, off))
        if not hits:
            continue

        uniq = sorted({h[0] for h in hits})
        ratio = len(uniq) / len(need)
        if len(uniq) == 1:
            # 优化器（-O2 向量化 / CSE）可能把其余轮常数全消掉，只留 1 个
            this_conf = 0.70
            weak_note = "（仅命中 1 个轮常数，其余可能被优化器消掉 —— 弱信号）"
        elif len(uniq) >= 2:
            this_conf = 0.90 if ratio >= 0.5 else 0.80
            weak_note = ""
        else:
            continue

        findings.append(
            dict(
                algo=name,
                confidence=this_conf,
                basis=(
                    f"源码化实现特征：命中 {len(uniq)}/{len(need)} 个{width * 8}-bit 轮常数立即数 "
                    f"{['0x%x' % u for u in uniq]}{weak_note}"
                ),
                offsets=[off_to_rva(o) for _, o in hits],
                scope=blob_name,
            )
        )
    return [f for f in findings if f["confidence"] >= min_score]




def analyze(path: str, verify_aes: bool, use_pe: bool, min_score: float):
    with open(path, "rb") as f:
        data = f.read()

    if not data:
        raise ValueError("空文件")

    report = {
        "file": path,
        "size": len(data),
        "sha256": __import__("hashlib").sha256(data).hexdigest(),
        "global_entropy": round(shannon_entropy(data), 4),
        "entropy_class": classify_region(shannon_entropy(data)),
        "pe": None,
        "findings": [],
    }

    # 文件头魔数
    magic_hits = []
    for name, mg in CONTAINER_MAGIC.items():
        if data.startswith(mg):
            magic_hits.append(name)
    report["container_magic"] = magic_hits

    if use_pe:
        pe = parse_pe(data)
        report["pe"] = {
            "is_pe": pe["is_pe"],
            "machine": hex(pe["machine"]),
            "image_base": hex(pe["image_base"]),
            "sections": [
                {
                    "name": s["name"],
                    "rva": hex(s["rva"]),
                    "vsize": hex(s["vsize"]),
                    "raw": hex(s["raw"]),
                    "rawsize": hex(s["rawsize"]),
                    "entropy": round(shannon_entropy(s["data"]), 3),
                }
                for s in pe["sections"]
            ],
        }

        if pe["is_pe"] and pe["sections"]:
            for sec in pe["sections"]:
                if not sec["data"]:
                    continue
                report["findings"].extend(
                    analyze_blob(
                        sec["data"],
                        f"{os.path.basename(path)}!{sec['name']}",
                        sec["rva"],
                        verify_aes,
                        None,
                        min_score,
                    )
                )
                # 可执行节额外做立即数常量扫描（轮常数被编成 mov eax, imm32）
                report["findings"].extend(
                    analyze_text_span(
                        sec["data"],
                        f"{os.path.basename(path)}!{sec['name']}",
                        sec["rva"],
                        min_score,
                    )
                )
        else:
            report["findings"].extend(
                analyze_blob(data, os.path.basename(path), None, verify_aes, None, min_score)
            )
    else:
        report["findings"].extend(
            analyze_blob(data, os.path.basename(path), None, verify_aes, None, min_score)
        )

    # 容器魔数作为一条独立发现（PE 情况下单独加）
    for name in magic_hits:
        if name == "pe_mz":
            continue
        report["findings"].append(
            dict(
                algo=f"容器格式: {name}",
                confidence=0.95,
                basis=f"文件头魔数 {CONTAINER_MAGIC[name].hex()} 命中",
                offsets=[0],
                scope="file",
            )
        )

    # 按 confidence 降序，同分按算法名
    report["findings"].sort(key=lambda f: (-f["confidence"], f["algo"]))
    report["findings"] = [f for f in report["findings"] if f["confidence"] >= min_score]
    report["hit_count"] = len(report["findings"])
    return report


# ----------------------------------------------------------------------------
# 7. CLI
# ----------------------------------------------------------------------------


def print_text(report: dict, show_entropy: bool, min_score: float):
    print("=" * 78)
    print(f"algo_identify — {report['file']}")
    print(f"size   : {report['size']} bytes")
    print(f"sha256 : {report['sha256']}")
    bar_len = int(report["global_entropy"] / 8.0 * 40)
    print(
        f"entropy: {report['global_entropy']:.4f}  [{'#' * bar_len}{'.' * (40 - bar_len)}]  {report['entropy_class']}"
    )
    if report.get("container_magic"):
        print(f"magic  : {', '.join(report['container_magic'])}")
    if report.get("pe"):
        pe = report["pe"]
        if pe["is_pe"]:
            print(f"pe     : machine={pe['machine']} image_base={pe['image_base']}")
            for s in pe["sections"]:
                print(
                    f"  {s['name']:<9} rva={s['rva']:<10} vsize={s['vsize']:<10} "
                    f"raw={s['raw']:<10} size={s['rawsize']:<10} entropy={s['entropy']}"
                )
    print("=" * 78)

    if not report["findings"]:
        print(f"\n未识别到任何算法常量指纹（阈值 {min_score}）。")
        print("提示：可能是 L3 自定义算法 —— 改用 references/custom-obfuscation-reverse.md 的黑盒/LFSR 路线。")
        return

    print(f"\n命中 {len(report['findings'])} 项（阈值 {min_score}）：\n")
    for i, f in enumerate(report["findings"], 1):
        offs = ", ".join(hex(o) for o in f["offsets"][:6])
        if len(f["offsets"]) > 6:
            offs += f", ...(+{len(f['offsets']) - 6})"
        print(f"[{i}] {f['algo']}   置信度 {f['confidence']:.2f}")
        print(f"    范围   : {f['scope']}")
        print(f"    依据   : {f['basis']}")
        if offs:
            print(f"    偏移   : {offs}")
        print()

    if show_entropy:
        print("-" * 78)
        print("滑动窗口熵轮廓（window=256 step=512）：")
        prof = sliding_window_entropy(report["_data"], 256, 512) if "_data" in report else []
        for off, ent in prof[:80]:
            bl = int(ent / 8.0 * 20)
            print(f"  0x{off:08x} |{'#' * bl}{'.' * (20 - bl)}| {ent:.2f}  {classify_region(ent)}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="algo_identify.py",
        description="二进制盲算法识别器（S-box 指纹 / 哈希常量 / CRC 查表 / 编码表 / 白盒表）",
    )
    ap.add_argument("file", help="待分析二进制")
    ap.add_argument("--json", action="store_true", help="JSON 输出")
    ap.add_argument("--entropy", action="store_true", help="附带滑动窗口熵轮廓")
    ap.add_argument("--min-score", type=float, default=0.55, help="置信度阈值（默认 0.55）")
    ap.add_argument(
        "--no-verify-aes",
        action="store_true",
        help="跳过 AES S-box 的 256 项数学校验（更快，但会漏报被截断的表）",
    )
    ap.add_argument("--no-pe", action="store_true", help="跳过 PE 结构解析，整文件当 blob 扫")
    args = ap.parse_args(argv)

    if not os.path.isfile(args.file):
        print(f"[!] 文件不存在: {args.file}", file=sys.stderr)
        return 2

    try:
        report = analyze(args.file, not args.no_verify_aes, not args.no_pe, args.min_score)
    except Exception as exc:  # noqa: BLE001
        print(f"[!] 分析失败: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        if args.entropy:
            with open(args.file, "rb") as f:
                report["_data"] = f.read()
        print_text(report, args.entropy, args.min_score)

    return 0 if report["hit_count"] else 1


if __name__ == "__main__":
    sys.exit(main())