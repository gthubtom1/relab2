# 注册码算法还原与 keygen 复现

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/pe-reverse/techniques/10-license-keygen/03-key-algorithm-recovery.md`（已适配本机工具链）
> **什么时候用**：已定位校验函数（02），反编译在手。目标：把「输入 key → 输出 TRUE」的映射
> 完整还原成 Python，并**反向**构造任意合法 key。
>
> 本地 / lab 目标按项目 `scope.md` 直接套用。

## 适用信号

| 构件 | 反编译中的形态 | 含义 |
|---|---|---|
| 位域字段布局 | `(x >> 21) & 0x7FF`、`(x >> 5) & 0x7FF` | key 内嵌「授权类型 / 期限 / 版本」字段 |
| CRC 截断校验 | `crc32(buf) & 0x1FFFFFF == A` | 校验串只取 CRC 的低 25~31 bit |
| XOR + 移位混淆 | `ebx = ((A << 7) ^ A) & 0xFFFFFFFF` | 防直接读字段的轻量混淆 |
| 常量异或 | `C ^ ebx ^ 0x12345678` | 与魔数异或还原明文 |
| 自定义哈希链 | 3~4 个 32 位哈希拼成 96~128 位 | 无签名时最常见的「伪签名」 |
| 字符集映射 | 查表 `0123456789ABCDEFGHJKMNPQRSTUVWXYZ` 或 5-bit 分组 | key 文本 ↔ 二进制数值互转 |

★★ **关键判断**：若反编译中**没有**模幂 / 椭圆曲线 / 验签调用，
仅由上述构件组成 → A 类本地算法，key 可由输入（用户名/邮箱）完全推导 → 直接写 keygen。

## 前置

```powershell
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
$r2  = (Resolve-ReverseToolSpec -Name 'r2').Command
$py  = (Resolve-ReverseToolSpec -Name 'pyre').Command
```

## 步骤

### 1. 逐构件还原

#### 1.1 位域字段布局

```python
# 反编译: r15 = C ^ ebx ^ 0x12345678
#         type = (r15 >> 21) & 0x7FF
#         term = (r15 >> 5)  & 0x7FF     # 0x7FF 通常表示永久
def parse_fields(r15: int) -> dict:
    return {
        "type":      (r15 >> 21) & 0x7FF,
        "permanent": ((r15 >> 5) & 0x7FF) == 0x7FF,
        "reserved":   r15 & 0x1F,
    }
```

★ **字段语义靠枚举验证**：构造不同值观察程序行为（`type=0` 标准版 vs `type=1` 便携版）。

#### 1.2 CRC 截断校验

```python
import binascii

def crc32_trunc(buf: bytes, mask: int) -> int:
    return binascii.crc32(buf) & mask          # mask 例如 0x1FFFFFF（25 bit）
```

★ **先确定 CRC 变体**（poly / init / xorout / refin / refout）。Python 的
`binascii.crc32` 是**标准变体**（zlib）。用**已知明文对**（官方 key + 其校验串）
暴力比对 poly 变体来锁定；其他变体用 `crcmod` 或手写查表。

★ **CRC 是线性可逆的** —— 只要知道「哪几个字节参与计算」，
就能构造出通过校验的任意输入。这是 A 类最常见的可利用点。

#### 1.3 XOR + 移位混淆

```python
def deobf(ebx: int, val: int, magic: int) -> int:
    return (val ^ ebx ^ magic) & 0xFFFFFFFF

# ebx = ((A << 7) ^ A) & 0xFFFFFFFF
# r15 = deobf(ebx, C, 0x12345678)
```

★ 混淆只是「防肉眼直读」，不增加安全性。还原后直接得到明文字段。

#### 1.4 自定义哈希链（伪签名）

```python
def make_96bit(email: str) -> int:
    e = email.encode()
    return (h1(e) << 64) | (h2(e) << 32) | h3(e)
```

★ **若 key 中只有部分字符参与校验**（如 192 字符中仅 19 字符参与），
其余是自由熵 —— keygen 只需精确复现被校验切片，剩余位任意。

#### 1.5 5-bit 字符集映射（base32 风格）

```python
ALPHABET = "0123456789ABCDEFGHJKMNPQRSTUVWXYZ"   # 32 字符（去掉易混淆的 I/L/O）

def to_base32(value: int, width: int) -> str:
    return "".join(ALPHABET[(value >> (5 * i)) & 0x1F]
                   for i in range(width - 1, -1, -1))

def from_base32(text: str) -> int:
    v = 0
    for ch in text:
        v = (v << 5) | ALPHABET.index(ch)
    return v
```

★ 见「每 5 bit 查 32 字符表」就想 base32。`width` 由 key 段长度反推
（25 字符 × 5 bit = 125 bit）。

### 2. 三段式 keygen 模板

```python
"""keygen 骨架: parse → verify → generate，全程自校验断言。

★ 本模板已在本机 (Resolve-ReverseToolSpec -Name 'pyre').Command (3.12) 实跑通过，
  修正了源文档模板的两个真实 bug（见文末「模板的两个坑」）。
  常量按你的反编译结果替换。
"""
import binascii
from dataclasses import dataclass

ALPHABET = "0123456789ABCDEFGHJKMNPQRSTUVWXYZ"


def to_base32(v: int, w: int) -> str:
    return "".join(ALPHABET[(v >> (5 * i)) & 0x1F] for i in range(w - 1, -1, -1))


def from_base32(t: str) -> int:
    v = 0
    for ch in t:
        v = (v << 5) | ALPHABET.index(ch)
    return v


def normalize(raw: str) -> str:
    """归一化: 大写 + 去分隔符。"""
    return "".join(c for c in raw.upper() if c.isalnum())


@dataclass
class KeyFields:
    checksum: int
    entropy:  int
    c: int
    d: int


# ★ 修正 1：切段索引必须与 render 的宽度严格一致。
#   7+7+5+5 = 24 字符（不是源文档写的 25）。源文档的 [15:20]/[20:25]
#   与它自己的 render(..., range(0,25,5)) 差了一格，导致每个字段都读错位。
def parse(key: str) -> KeyFields:
    up = normalize(key)
    assert len(up) == 24, "expected 24 normalized chars, got %d" % len(up)
    # ★ 逐目标确认切段索引；有些实现解析前有「游离置换」，如 up[2] := up[14]
    return KeyFields(checksum=from_base32(up[19:24]),
                     entropy =from_base32(up[14:19]),
                     c       =from_base32(up[0:7]),
                     d       =from_base32(up[7:14]))


def compute_checksum(c: int, d: int, entropy: int) -> int:
    """★ 修正 2：checksum 只由 C/D/entropy 决定，不接受自身。
       源模板让 f.checksum 参与 ebx = ((checksum << 7) ^ checksum)，
       于是 checksum 同时是输入和输出 —— 自指方程，不动点迭代不收敛
       （本机实测 64 轮后仍不收敛）。
       真实目标里这个「混淆种子」通常来自别的字段或固定常量。
    """
    ebx = 0x5A5A5A5A                                    # 固定混淆种子（按反编译替换）
    r15 = (c ^ ebx ^ 0x12345678) & 0xFFFFFFFF
    r10 = (d ^ ebx ^ 0x87654321) & 0xFFFFFFFF
    buf = (r15.to_bytes(4, "little") + r10.to_bytes(4, "little")
           + entropy.to_bytes(4, "little"))
    return binascii.crc32(buf) & 0x1FFFFFF               # 25-bit 截断


def verify(key: str) -> bool:
    f = parse(key)
    return compute_checksum(f.c, f.d, f.entropy) == f.checksum


def generate(c: int, d: int, entropy: int) -> str:
    """先定 C/D/熵，算出校验串 A，最后拼回 24 字符。"""
    a = compute_checksum(c, d, entropy)
    f = KeyFields(a, entropy, c, d)
    up = (to_base32(f.c, 7) + to_base32(f.d, 7)
          + to_base32(f.entropy, 5) + to_base32(f.checksum, 5))
    return "-".join(up[i:i + 5] for i in range(0, 24, 5))


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--gen", nargs=3, metavar=("C", "D", "ENTROPY"))
    ap.add_argument("--verify", metavar="KEY")
    args = ap.parse_args()
    if args.gen:
        c, d, e = (int(x, 0) for x in args.gen)
        key = generate(c, d, e)
        assert verify(key), "self-check failed"
        print(key)
    elif args.verify:
        print("VALID" if verify(args.verify) else "INVALID")
```

**本机实测输出**（`python keygenfix.py`，三组不同字段）：
```
c=0xffe00000  d=0x2025     e=0x12345     -> 3YX00-00000-08150-28T5V-HTSU verify=True
c=0x0         d=0xdead     e=0x1         -> 00000-00000-1QND0-00019-RCUR verify=True
c=0x123456    d=0xfedcba   e=0x1fffff    -> 0014D-2P00F-WQ5T1-YYYYK-1BTA verify=True
OK - 三组均自洽

original : 3YX00-00000-08150-28T5V-HTSU verify=True
mutated  : 3YX10000000815028T5VHTSU  verify=False
OK - 单字符变异被检出
```

★ 最后两行是**关键判据**：三组字段都能往返自洽，且**单字符变异被检出**。
只满足前者的模板可能只是碰巧；两者都满足才说明 parse/verify/generate 三者对齐了。

★ **字段宽度约束**（否则往返时被截断，`verify` 失败）：
```
C    = up[0:7]    35 bit  （7 字符 × 5 bit）
D    = up[7:14]   35 bit
B    = up[14:19]  25 bit  ← entropy 上限 0x1FFFFFF
A    = up[19:24]  25 bit  ← checksum 上限 0x1FFFFFF
```
本机实测：`entropy = 0x7FFFFFF`（27 bit）超出 25-bit 字段，
往返后被截断，`verify=False`。**真实 keygen 里字段值来自反编译出的掩码，不会越界。**

### 模板的两个坑（本机实测发现）

1. **切段索引与渲染宽度差一格**。源模板 `render` 用 `range(0, 25, 5)`，
   但字段宽度 `7+7+5+5 = 24`。**生成 24 字符，却按 25 字符切** ——
   每个字段都读错位，`parse` 拿到的是错的 C/D/B/A。
   实测症状：`verify` 恒 False，且看不出哪里错。**切段索引必须由
   `render` 的各段宽度反推，不要手写。**
2. **checksum 自指导致不动点迭代不收敛**。源模板
   `ebx = ((f.checksum << 7) ^ f.checksum)` 让 checksum 参与自身计算。
   我按「迭代到不动点」的思路跑了 64 轮，**实测不收敛**（CRC 是仿射变换，
   不是压缩映射，不存在唯一不动点）。
   **正确做法：确认混淆种子来自哪个字段**（通常是另一个字段或固定常量），
   让 `compute_checksum` 只依赖不含自身的字段。

**使用三步**：
1. `parse` 的切段/置换按目标调整；
2. `compute_checksum` 的公式/常量按反编译替换；
3. 跑 `--gen` 断言自洽 → 用官方 key 做 `--verify` 回归（**官方 key 必须 VALID**）。

### 3. ★ 官方 key 回归（还原正确性的硬证据）

```powershell
& (Resolve-ReverseToolSpec -Name 'pyre').Command .\keygen.py --verify "AAAAA-BBBBB-CCCCC-DDDDD-EEEEE"
```

★ **官方 key 必须返回 VALID**。这是判断「还原对不对」的**唯一客观标准** ——
自洽断言只能证明「公式和 keygen 一致」，不能证明「和目标一致」。

### 4. 提取常量（用 r2，别肉眼抄）

```powershell
$r2 = (Resolve-ReverseToolSpec -Name 'r2').Command

# 反编译出的立即数：在 .text 里找对应字节
& $r2 -2 -qc '/x 78563412; q' .\target.exe       # mov ecx, 0x12345678 (小端)
& $r2 -2 -qc '/x 21436587; q' .\target.exe       # mov ecx, 0x87654321 (小端)

# 字符集表：作为字符串提取
& $r2 -2 -qc 'izz~ABCDEFGHJK' .\target.exe
```

★ **常量一定用 `/x` 搜出来并核对字节序**，不要从反编译伪码里抄 ——
伪码的十进制/十六进制显示经常带符号扩展，抄错一位整个 keygen 就废。

### 5. 非确定性校验陷阱

| 污染源 | 症状 | 处理 |
|---|---|---|
| 时间依赖 | 期限判定读系统时间 | 把时间作为**显式参数**，不要硬编码当前时间 |
| RNG / 会话状态 | 两次调用同一 key 结果不同 | 先锁定种子来源 |
| 多线程竞争 | 结果写共享标志位后被覆盖 | 以「标志位最终状态」为验证基准（05 的 L4） |

★ **先做确定性测试**：同一 key 连续调用校验函数 N 次，返回值是否恒定。
不恒定就按上表定位污染源，**在还原算法之前解决**。

## 判据

1. ★★★ **官方 key 回归 VALID**。判据形态：`keygen.py --verify "<官方key>"` 输出 `VALID`。
   **这是唯一能证明「还原正确」判据。** 自洽断言通过但官方 key INVALID
   = 切段错、字段语义错、或 CRC 变体选错。
2. ★★ **自洽断言通过**。判据形态：`--gen` 生成后 `assert verify(key)` 不抛异常。
   **这是弱证据** —— 它只证明 keygen 内部一致。
3. ★★ **算法里没有模幂 / 椭圆曲线 / 验签调用**。判据形态：反编译里搜不到
   大整数乘法循环、没有 `modPow` 例程、没有密码库导入。
   **若出现了，说明判类错了**（应该是 B 类），回 04。
4. **还原出的魔数/掩码/字符集/切段索引都被记录**。判据形态：一份完整的常量表
   （`0x12345678` 魔数、`0x1FFFFFF` 掩码、`ALPHABET` 字符串、切段索引 `[0:7]/[7:14]/[15:20]/[20:25]`）。
   **没有这张表，下次换样本要从头再来。**
5. ★ **确定性测试通过**。判据形态：同一 key 连续调用 N 次返回值恒定。
   不恒定说明算法还原里还缺一个输入（时间/RNG），**此时的「还原」是不完整的**。

## 坑

1. ★★★★ **切段索引与渲染宽度差一格（本机实测）**。源模板 `render` 用
   `range(0, 25, 5)`，但字段宽度 `7+7+5+5 = 24`。**生成 24 字符却按 25 字符切** ——
   每个字段都读错位，`verify` 恒 False 且看不出原因。
   实测症状：`c=0x123456 d=0xfedcba e=0x1fffff` 那组在修正前 `verify=False`，
   修正切段索引后 `verify=True`。**切段索引必须由 render 的各段宽度反推，不要手写。**
2. ★★★★ **checksum 自指 → 不动点迭代不收敛（本机实测）**。源模板
   `ebx = ((f.checksum << 7) ^ f.checksum)` 让 checksum 参与自身计算。
   我按「迭代到不动点」的思路跑了 **64 轮，实测不收敛**（CRC 是仿射变换，
   不是压缩映射，不保证有唯一不动点）。
   **正确做法：确认混淆种子来自哪个字段**（通常是另一个字段或固定常量），
   让 `compute_checksum` 只依赖不含自身的字段。
3. ★★★ **字段宽度越界会被静默截断（本机实测）**。`entropy = 0x7FFFFFF`（27 bit）
   超出 25-bit 字段（`up[14:19]`，5 字符 × 5 bit），往返后被截断，
   `verify=False`。**症状与「公式写错」完全一样**。
   在 `parse` 里加 `assert len(up) == 24` 和字段范围断言能提前暴露。
4. ★★★ **自洽断言通过 ≠ 还原正确**。`--gen` + `assert verify()` 只证明
   keygen 和它自己的公式一致。**必须用官方 key 回归**（判据 1）。
   我见过太多「自检全过但官方 key 判 INVALID」的 cases。
5. ★★★ **CRC 变体选错是最常见的还原失败原因**。`binascii.crc32` 是 zlib 变体；
   BZIP2 / POSIX / CRC32C / 自定义多项式的结果完全不同。
   **用官方 key + 其校验串暴力比对变体**，别猜。
6. ★★ **常量抄错一位 = 全盘错**。从反编译伪码抄立即数经常遇到符号扩展问题
   （`0xFFFFFFFF` 显示成 `-1`）。**用 `/x` 在 `.text` 里搜字节核对**。
7. ★★ **切段索引可能带「游离置换」**。有些实现在解析前做 `up[2] := up[14]` 之类的
   重排。不注意会导致「字段读出来是乱的」但校验居然还能过（因为校验也基于置换后的值）。
8. ★★ **小端 / 大端搞反**。`to_bytes(4, "little")` 是 x86 的真实布局。
   用 `struct.pack` 时写错字节序 = CRC 算出来完全不同。
9. ★ **「部分字符参与校验」容易被忽略**。192 字符的 key 里可能只有 19 个参与校验，
   其余是随机装饰。**先确定参与校验的切片范围**，不然会做很多无用功。
10. ★ **`ALPHABET.index(ch)` 对不在表里的字符抛 `ValueError`**。
    `normalize` 要先滤掉分隔符。
11. **`binascii.crc32` 在 Python 3 返回无符号 int**，但 `& mask` 后要确认没有负数。
12. **本机 gcc 可用但 MSVC 不可用**。要写验证工具时用 MinGW。

## 相关

- `license-keygen-02-validation-function-location.md` — 上一步：定位校验函数
- `license-keygen-05-keygen-verification-loop.md` — 下一步：实机验证（**必做**）
- `license-keygen-04-signature-chain-pubkey-swap.md` — 还原时发现签名现场 → 转这里
- `../../crypto-decode-tools.md` — 遇到更复杂的加密算法时
- `../code-patching.md` — 逻辑 patch 路线（不想写 keygen 时）