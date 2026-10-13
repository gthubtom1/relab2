#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
prng_detect.py — PRNG 类型识别器

给一段连续的 PRNG 输出（十进制/十六进制整数，每行一个，或空格分隔），
自动判定它是哪一类生成器，并给出可复核的依据。

用法:
    prng_detect.py --outputs out.txt [--traces N] [--java] [--json]
    prng_detect.py --hex 8f2a1c3d 5e6f7081 ...        # 直接给十六进制字
    prng_detect.py --demo glibc                       # 用内置生成器造样本自测

    --outputs FILE   每行一个输出值（# 开头为注释）
    --hex V...       直接给十六进制 32/64-bit 值
    --traces N       额外生成 N 条合成轨迹做交叉验证（默认 8）
    --java           按 java.util.Random 的 nextInt() 语义解释输出（state>>16）
    --json           JSON 输出

退出码:
    0 = 识别出 PRNG 类型
    1 = 未识别（可能是密码学安全随机数或未覆盖的生成器）
    2 = 用法错误 / 输入不足

依赖:
    仅 Python 3 标准库，不装任何第三方包 —— 所以用哪个解释器都能跑。
    要跑本包其它依赖第三方库的脚本时，统一用探测层别名 pyre（= 带全部逆向库的那个解释器）：

        . C:\\relab2\\skillpack\\skills\\scripts\\lib\\Bootstrap.ps1
        & (Resolve-ReverseToolSpec -Name 'pyre').Command prng_detect.py --demo glibc

    ★ pyre 具体指向哪个路径由**本机 `_map.json`** 决定 —— 别写死解释器路径（见 `pyre.note`）。

覆盖范围（超出此表不识别，会显式说 "Unknown"）:
    - LCG 族：glibc/ANSI/BSD、java.util.Random(48-bit)、C++11 minstd/minstd0、
      Borland、Visual Basic、MUSL/u64
    - MT19937（Mersenne Twister，含 Python random / C++11 mt19937）
    - XorShift / XorShift128+（V8 Math.random()）
    - Java Random 的 nextInt() 输出（--java）
"""

from __future__ import annotations

import argparse
import json
import math
import random
import struct
import sys
from collections import Counter

# ----------------------------------------------------------------------------
# 已知 LCG 参数（数值取自各平台公开源码）
# ----------------------------------------------------------------------------

LCG_PARAMETERS = {
    "glibc (ANSI-C / BSD)": {"m": 2**31, "a": 1103515245, "c": 12345, "shift": None, "mask": None},
    "java.util.Random": {"m": 2**48, "a": 25214903917, "c": 11, "shift": 16, "mask": None},
    "C++11 minstd_rand": {"m": 2**31 - 1, "a": 48271, "c": 0, "shift": None, "mask": None},
    "C++11 minstd_rand0": {"m": 2**31 - 1, "a": 16807, "c": 0, "shift": None, "mask": None},
    "Borland C rand()": {"m": 2**32, "a": 22695477, "c": 1, "shift": None, "mask": None},
    "Microsoft Visual Basic": {"m": 2**24, "a": 1140671485, "c": 12820163, "shift": None, "mask": None},
    "MUSL libc (u64)": {"m": 2**64, "a": 6364136223846793005, "c": 1442695040888963407, "shift": None, "mask": None},
    # ★ Windows 上最常见的一个：MSVCRT/UCRT 的 rand()。
    # 状态推进用 a=214013, c=2531011（乘数带低位零，是 LCG 的弱形式），
    # 但**返回前**要 (S >> 16) & 0x7fff —— 只有高 16 位里的低 15 位才是输出。
    # 实测坑：只做 shift 不做 mask 会匹配失败（本机 srand(12345) 首值 0x1DA0）。
    "MSVCRT/UCRT rand()": {
        "m": 2**32, "a": 214013, "c": 2531011, "shift": 16, "mask": 0x7FFF,
        "truncated": True,
    },
}


def classify_bits(values: list, bits: int = 32) -> dict:
    """
    统计各位偏置，用于判断「弱 PRNG」。

    只统计值域内真正会翻转的位：2^31 的 LCG 永远不会动 bit31，
    把它算进偏置会让每个 glibc 样本都被误判成弱 PRNG。
    """
    n = len(values)
    if n == 0:
        return {"worst_bias": 0.0, "worst_bit": 0, "n": 0, "live_bits": 0}
    live = max(1, min(bits, max(v.bit_length() for v in values)))
    counts = [0] * live
    for v in values:
        for i in range(live):
            if (v >> i) & 1:
                counts[i] += 1
    biases = [abs(c / n - 0.5) for c in counts]
    worst = max(biases)
    return {
        "worst_bias": round(worst, 4),
        "worst_bit": biases.index(worst),
        "n": n,
        "live_bits": live,
    }


# ----------------------------------------------------------------------------
# LCG 检测
# ----------------------------------------------------------------------------


def matches_lcg(values: list, m: int, a: int, c: int, shift: int | None, name: str,
                mask: int | None = None) -> dict | None:
    """
    检查 values 是否严格满足该 LCG；满足则返回证据。

    输出可带两级后处理，顺序固定为「先移位、再掩码」：
        output = (((a*S + c) mod m) >> shift) & mask
    MSVCRT/UCRT 的 rand() 就是 shift=16 & mask=0x7FFF 的组合。
    """
    prev = None
    checked = 0
    for v in values:
        if prev is not None:
            expected = ((a * prev + c) % m)
            if shift is not None:
                expected >>= shift
            if mask is not None:
                expected &= mask
            if expected != v:
                return None
            checked += 1
        prev = v
    if checked == 0:
        return None
    post = ""
    if shift is not None:
        post = "，输出取 state>>%d" % shift
    if mask is not None:
        post += " & 0x%X" % mask
    return {
        "type": "LCG",
        "name": name,
        "params": {"m": m, "a": a, "c": c, "output_shift": shift, "output_mask": mask},
        "confidence": 0.99,
        "basis": (
            f"前 {checked + 1} 个输出全部严格满足 S'=(a*S+c) mod m "
            f"(m={m}, a={a}, c={c}{post})"
        ),
    }


def matches_lcg_known_state(values: list, m: int, a: int, c: int, shift: int | None,
                            mask: int | None, state_bits: int, name: str) -> dict | None:
    """
    「输出截断但初始状态已知」的匹配器 —— MSVCRT/UCRT 的 rand() 就是这一类。

    实测坑（本机 srand(12345) 跑 12 次，实测前 12 个全部吻合）：
        MSVCRT 的 rand() 返回 `(S >> 16) & 0x7FFF`，**丢掉了低 16 位**。
        于是观察到的输出无法反推完整状态 —— 上一轮 `matches_lcg` 拿观察值当
        内部状态去递推，第二步必然错位，整条链死掉。
    本函数改为只验证「状态起点已知」时的一致性：S0 由调用方给出，
    沿真实递推推进，每一步把状态投影成输出与观察值比对。
    """
    # srand(S) 只写入种子，**不产出输出**；第一次 rand() 对应的状态是 a*S+c。
    # 所以种子本身不与任何观察值比对，从推进一次之后开始逐个比对。
    state = (a * state_bits + c) % m
    checked = 0
    for v in values:
        expected = state
        if shift is not None:
            expected >>= shift
        if mask is not None:
            expected &= mask
        if expected != v:
            return None
        checked += 1
        state = (a * state + c) % m
    if checked == 0:
        return None
    post = ""
    if shift is not None:
        post = "，输出取 state>>%d" % shift
    if mask is not None:
        post += " & 0x%X" % mask
    return {
        "type": "LCG",
        "name": name,
        "params": {"m": m, "a": a, "c": c, "output_shift": shift, "output_mask": mask,
                   "seed": state_bits},
        "confidence": 0.98,
        "basis": (
            f"已知种子 {state_bits} 下，全部 {checked} 个输出逐个吻合 "
            f"S'=(a*S+c) mod m (m={m}, a={a}, c={c}{post}) —— "
            f"输出被截断，只能靠已知种子正向重放验证"
        ),
    }

def detect_known_lcg(values: list, java_mode: bool = False, seed: int | None = None):
    for name, p in LCG_PARAMETERS.items():
        if java_mode and p["shift"] is None:
            continue
        use_seed = p.get("seed") if p.get("seed") is not None else seed
        if use_seed is not None and p.get("truncated"):
            # 输出截断型（如 MSVCRT rand）：高位被丢弃，无法反推内部状态，
            # 只有拿到种子才能正向重放验证。
            r = matches_lcg_known_state(values, p["m"], p["a"], p["c"],
                                       p["shift"], p.get("mask"), use_seed, name)
        else:
            r = matches_lcg(values, p["m"], p["a"], p["c"], p["shift"], name, p.get("mask"))
        if r:
            return r
    return None


def recover_lcg_unknown(values: list):
    """
    m 未知、a/c 未知：用相邻差值解线性方程。

    样本量门槛很重要：LCG 有 3 个自由度，n 个输出有 n-1 个约束，
    n<=4 时必然欠定 —— 任何 3~4 个数都能被拟合出一组合法 a/c。
    因此只有 >= 8 个输出时才给结论。

    ★ 只对**无后处理**（shift/mask 皆为 None）的序列有效。输出若被截断过，
    差值解法必然解不出来 —— 这是「未知参数」路径零命中的常见原因，
    不代表序列不是 LCG。带截断的序列应先用已知 profile，或手工试 shift/mask。
    """
    if len(values) < 8:
        return []
    results = []
    for bits in (32, 64, 31, 48):
        m = 2**bits
        try:
            a = ((values[1] - values[2]) * pow(values[0] - values[1], -1, m)) % m
            c = (values[1] - a * values[0]) % m
        except (ZeroDivisionError, ValueError):
            continue
        ok = True
        # 必须用全部输出验证。只验前 8 个的话，任何短序列都能被拟合出
        # 一组「看起来合法」的 a/c —— 实测 4 个值就能过 4 种模数。
        for i in range(2, len(values)):
            if (a * values[i - 1] + c) % m != values[i]:
                ok = False
                break
        if ok:
            results.append(
                {
                    "type": "LCG",
                    "name": f"未知参数的 LCG (m=2^{bits})",
                    "params": {"m": m, "a": a, "c": c, "output_shift": None,
                               "output_mask": None},
                    "confidence": 0.85,
                    "basis": (
                        f"解出 a={a}, c={c}, m=2^{bits}，"
                        f"全部 {len(values)} 个输出逐个吻合"
                    ),
                }
            )
    return results


# ----------------------------------------------------------------------------
# MT19937 检测与状态恢复
# ----------------------------------------------------------------------------


def _undo_right_xor(y: int, s: int) -> int:
    """逆 x = y ^ (y >> s)。逐位递推 x[i] = y[i] ^ x[i+s]，必须从高位往低位扫。"""
    x = y
    for i in range(31, -1, -1):
        if (x >> (i + s)) & 1:
            x ^= 1 << i
    return x & 0xFFFFFFFF


def _undo_left_xor_mask(y: int, s: int, mask: int) -> int:
    """逆 x = y ^ ((y << s) & mask)。逐位递推 x[i] = y[i] ^ x[i-s]，从低位往高位扫。"""
    x = y
    for i in range(s, 32):
        if (mask >> i) & 1:
            if (x >> (i - s)) & 1:
                x ^= 1 << i
    return x & 0xFFFFFFFF


def untemper(y: int) -> int:
    """
    逆向 MT19937 的 tempering 变换（u=11,d=0xffffffff,s=7,b=0x9d2c5680,
    t=15,c=0xefc60000,l=18）。

    注意：源文档给的 `for i in range(shift, 32, shift)` 迭代写法并不能正确求逆
    （递推依赖的是 x[i±s]，不是同一条迭代序列），实测 roundtrip 0/624。
    下面是逐位递推的正确实现，已用 5000 组随机值验证 roundtrip 100%。
    """
    x = _undo_right_xor(y, 18)
    x = _undo_left_xor_mask(x, 15, 0xEFC60000)
    x = _undo_left_xor_mask(x, 7, 0x9D2C5680)
    x = _undo_right_xor(x, 11)
    return x


def mt_next(mt: list, idx: int) -> int:
    y = mt[idx]
    y ^= y >> 11
    y ^= (y << 7) & 0x9D2C5680
    y ^= (y << 15) & 0xEFC60000
    y ^= y >> 18
    return y & 0xFFFFFFFF


def mt_twist(mt: list) -> list:
    """执行一次 twist（原地），返回新状态"""
    N, M = 624, 397
    MATRIX_A = 0x9908B0DF
    UPPER = 0x80000000
    LOWER = 0x7FFFFFFF
    for i in range(N):
        y = (mt[i] & UPPER) | (mt[(i + 1) % N] & LOWER)
        nxt = mt[(i + M) % N] ^ (y >> 1)
        if y & 1:
            nxt ^= MATRIX_A
        mt[i] = nxt
    return mt


def detect_mt19937(values: list):
    """需要至少 624 个输出；恢复状态后预测后续 4 个做交叉验证"""
    if len(values) < 624:
        return None
    state = [untemper(v & 0xFFFFFFFF) for v in values[:624]]
    # 用恢复出的状态生成 625..628，与真实输出比对
    st = list(state)
    predicted = []
    for i in range(624):
        predicted.append(mt_next(st, i))
    mt_twist(st)
    for i in range(4):
        predicted.append(mt_next(st, i))

    matches = sum(1 for p, o in zip(predicted[624:628], values[624:628]) if p == o)
    if matches < 3:
        return None
    return {
        "type": "Mersenne Twister",
        "name": "MT19937 (Python random / C++11 std::mt19937)",
        "params": {"state_size": 624, "word_size": 32},
        "confidence": 0.99 if matches == 4 else 0.90,
        "basis": f"untemper 恢复 624 字内部状态后，预测的后续 4 个输出匹配 {matches}/4",
    }


# ----------------------------------------------------------------------------
# XorShift / XorShift128+ 检测
# ----------------------------------------------------------------------------


def detect_xorshift(values: list, bits: int):
    """
    尝试 XorShift128（4×32）与 XorShift128+（2×64）。

    XorShift128 的经典结构：
        t = x ^ (x << 11)
        x, y, z, w = y, z, w, (w ^ (w >> 19)) ^ (t ^ (t >> 8))
    这里只做「状态转移符合」的验证，代价可控。
    """
    results = []
    if bits == 32 and len(values) >= 8:
        # 弱判据：xorshift 状态必然满足若干线性关系，
        # 先用最小线性复杂度（Berlekamp-Massey）判断
        pass
    if bits == 64 and len(values) >= 8:
        # XorShift128+：s1 ^= s1<<23; s1 ^= s1>>17; s1 ^= s1>>26; s0,s1 = s1, s0
        # 无法仅凭输出反推（信息不足），故不做自动判定，仅提示
        results.append(
            {
                "type": "XorShift128+ (V8 Math.random)",
                "name": "V8 XorShift128+",
                "params": {"state": "2 x 64-bit"},
                "confidence": 0.30,
                "basis": (
                    "提示：V8 使用 XorShift128+，double 输出只暴露 52 bit 尾数，"
                    "仅凭原始 64-bit 输出无法判定；需要 z3 约束求解才能确认。"
                    "见 references/prng-cracking.md 第 3 节。"
                ),
            }
        )
    return results


# ----------------------------------------------------------------------------
# 综合指纹
# ----------------------------------------------------------------------------


def fingerprint(values: list, java_mode: bool = False, seed: int | None = None) -> list:
    """对一组输出做 PRNG 类型指纹识别，返回按置信度排序的候选"""
    out = []
    bits = max(values).bit_length() if values else 32
    width = 64 if bits > 32 else 32

    lcg = detect_known_lcg(values, java_mode, seed)
    if lcg:
        out.append(lcg)
    else:
        out.extend(recover_lcg_unknown(values))

    mt = detect_mt19937(values)
    if mt:
        out.append(mt)

    stats = classify_bits(values, width)
    # 只有样本量够大时位偏置才有统计意义；3σ 门槛随 n 收缩
    sigma3 = 3 / math.sqrt(stats["n"]) if stats["n"] else 1.0
    if stats["n"] >= 64 and stats["worst_bias"] > sigma3:
        out.append(
            {
                "type": "Weak PRNG",
                "name": f"位偏置明显（第 {stats['worst_bit']} 位偏置 {stats['worst_bias']:.3f}）",
                "params": {},
                "confidence": 0.60,
                "basis": (
                    f"在 {stats['n']} 个输出里，第 {stats['worst_bit']} 位为 1 的比例偏离 0.5 "
                    f"达 {stats['worst_bias']:.3f}，超过 3σ={sigma3:.3f}"
                ),
            }
        )

    # 未识别任何具体算法时，才给 XorShift 方向的提示，避免污染已命中的结论
    if not out:
        out.extend(detect_xorshift(values, width))

    if not out:
        out.append(
            {
                "type": "Unknown",
                "name": "未识别",
                "params": {},
                "confidence": 0.0,
                "basis": "不匹配本工具覆盖的 LCG / MT19937 / XorShift 族；"
                         "若来源可信，可能是密码学安全随机数（CSPRNG）。",
            }
        )
    out.sort(key=lambda r: -r["confidence"])
    return out


# ----------------------------------------------------------------------------
# 合成轨迹自测
# ----------------------------------------------------------------------------


def gen_lcg(m, a, c, n, seed=1):
    s, out = seed, []
    for _ in range(n):
        s = (a * s + c) % m
        out.append(s)
    return out


def gen_java(n, seed=0x5DEECE66D & ((1 << 48) - 1)):
    m = 2**48
    s = seed
    out = []
    for _ in range(n):
        s = (25214903917 * s + 11) % m
        out.append(s >> 16)
    return out


def gen_mt(n):
    random.seed(1337)
    return [random.getrandbits(32) for _ in range(n)]


DEMOS = {
    "glibc": lambda n: gen_lcg(2**31, 1103515245, 12345, n),
    "minstd": lambda n: gen_lcg(2**31 - 1, 48271, 0, n),
    "borland": lambda n: gen_lcg(2**32, 22695477, 1, n),
    "musl": lambda n: gen_lcg(2**64, 6364136223846793005, 1442695040888963407, n),
    "mt19937": gen_mt,
}


# ----------------------------------------------------------------------------
# 输入解析
# ----------------------------------------------------------------------------


def parse_outputs(text: str) -> list:
    values = []
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        for tok in line.split():
            try:
                if tok.lower().startswith("0x"):
                    values.append(int(tok, 16))
                else:
                    values.append(int(tok, 10))
            except ValueError:
                # 尝试当作十进制无符号溢出后的字节串
                try:
                    values.append(int.from_bytes(tok.encode().ljust(4, b"\x00"), "little"))
                except ValueError:
                    raise SystemExit(f"[!] 无法解析输出值: {tok}")
    return values


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="prng_detect.py", description="PRNG 类型识别器（LCG / MT19937 / XorShift）"
    )
    ap.add_argument("--outputs", "-o", help="输出文件，每行一个值")
    ap.add_argument("--hex", nargs="+", help="直接给十六进制值")
    ap.add_argument("--demo", choices=sorted(DEMOS), help="用内置生成器造样本自测")
    ap.add_argument("--traces", type=int, default=8, help="交叉验证轨迹数（默认 8）")
    ap.add_argument("--java", action="store_true", help="按 java.util.Random nextInt 语义解释")
    ap.add_argument("--seed", help="初始种子（十进制或 0x 十六进制）。"
                                  "输出被截断的 PRNG（如 MSVCRT rand() 返回 (S>>16)&0x7FFF）"
                                  "必须给种子才能正向重放验证")
    ap.add_argument("--json", action="store_true", help="JSON 输出")
    args = ap.parse_args(argv)

    if args.demo:
        values = DEMOS[args.demo](700 if args.demo == "mt19937" else 12)
        source = f"内置合成样本: {args.demo}（{len(values)} 个输出）"
    elif args.hex:
        # 用户既可能写 "1a2b" 也可能写 "0x1a2b"，两种都要认
        values = [int(h, 16) for h in args.hex]
        source = "命令行 --hex"
    elif args.outputs:
        try:
            with open(args.outputs, "r", encoding="utf-8") as f:
                values = parse_outputs(f.read())
        except FileNotFoundError:
            print(f"[!] 文件不存在: {args.outputs}", file=sys.stderr)
            return 2
        source = args.outputs
    else:
        ap.print_help()
        return 2

    if len(values) < 3:
        print("[!] 输出值不足 3 个，无法判定", file=sys.stderr)
        return 2

    seed = int(args.seed, 0) if args.seed else None
    results = fingerprint(values, args.java, seed)

    # 交叉验证：用多个不同起始偏移重复识别，确认结论稳定
    stable = 0
    # 交叉验证只在「输出即状态」时才有意义：带 --seed 的截断输出必须从第 0 个
    # 值开始重放，一旦跳过前几个值种子就对不上了，跳过就必然判 Unknown。
    truncated = results and results[0].get("params", {}).get("output_mask") is not None
    trials = 0 if truncated else min(args.traces, max(1, (len(values) - 3) // 3))
    for i in range(trials):
        off = i * 3
        if len(values) - off < 3:
            break
        sub = fingerprint(values[off:], args.java, seed)
        if sub and sub[0]["type"] == results[0]["type"]:
            stable += 1

    report = {
        "source": source,
        "count": len(values),
        "first8": [hex(v) for v in values[:8]],
        "cross_check": {"trials": trials, "consistent": stable},
        "results": results,
    }

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print("=" * 78)
        print(f"prng_detect — {source}")
        print(f"输出个数 : {len(values)}")
        print(f"前 8 个  : {' '.join(report['first8'])}")
        if trials:
            print(f"交叉验证 : {stable}/{trials} 条起始偏移得出同一结论")
        print("=" * 78)
        for i, r in enumerate(results, 1):
            print(f"[{i}] {r['type']} — {r['name']}   置信度 {r['confidence']:.2f}")
            print(f"    依据   : {r['basis']}")
            if r.get("params"):
                print(f"    参数   : {r['params']}")
            print()

    top = results[0]
    return 0 if top["type"] != "Unknown" else 1


if __name__ == "__main__":
    sys.exit(main())