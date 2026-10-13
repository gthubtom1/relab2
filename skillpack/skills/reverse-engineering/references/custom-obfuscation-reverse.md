# 自定义混淆/加密还原方法论

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/general/techniques/crypto/02-custom-obfuscation-reverse.md`
> **什么时候用**：`crypto-algorithm-identification.md` 的 `algo_identify.py` **退出码 1**（一个标准算法都没命中）—— 确认目标用的不是标准算法，而是魔改 XOR、自制 S-box、白盒查找表，或从 native 层拼出来的自定义加密。

## 适用信号

- 密文长度 **==** 明文长度（流密码 / XOR / 替换密码）
- 抓包能看到固定头 + 变长密文
- 有 Key / IV 入参，但用标准算法库匹配不上
- 同一段数据跨进程 / 跨版本结果不变（硬编码 S-box）
- 结果随某个 ID 或时间戳变化（派生密钥）
- `.rdata` 里有**多张** 1024 字节的乱序表（白盒 T-box）

## 层次框架

```
L1 黑盒：输入 → 观察 → 差分 → 统计推断     （不用跑目标）
L2 灰盒：动态插桩 → 截获中间状态 → 分离步骤 （要能跑起来）
L3 白盒：逆向实现 → 提取参数 → 独立复现     （读反编译代码）
L4 符号：约束求解 → 符号执行 → 自动恢复密钥 （angr / z3）
```

| 观察到的信号 | 起点 |
|---|---|
| 加密前后长度相同 | L1 + L2 |
| 密文长度是 8/16/32 的整数倍 | L3 找实现 |
| 有 Key 和 IV 参数 | L2 动态 dump |
| 无 Key 参数但结果确定 | L3 白盒 / 硬编码提取 |
| 跨版本结果不变 | L3 静态提取 |
| 结果随 ID/时间变化 | L4 找派生函数 |

★ 往上走一层成本指数上升。**能用 L1 解决的不要上 L4** —— 符号执行在一个
有反调试的样本上可能几十分钟不出结果，而 L1 的频率分析是秒级。

## 前置

```powershell
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
$frida = (Resolve-ReverseToolSpec -Name 'frida').Command
$r2    = (Resolve-ReverseToolSpec -Name 'r2').Command
```

| 用途 | 工具 | 说明 |
|---|---|---|
| Python 解释器 | `(Resolve-ReverseToolSpec -Name 'pyre').Command` | **angr / z3 / unicorn 都在这里** |
| 符号执行 | `angr` 10.0.1 | 只装在这个解释器里 |
| 约束求解 | `z3` | 同上 |
| 动态插桩 | `frida` / `objection` | Android 与本机进程通用 |
| 静态定位 | `r2` / `analyzeHeadless` | 找常量引用点 |

```powershell
$py = (Resolve-ReverseToolSpec -Name 'pyre').Command
& $py -c "import angr, z3; print('angr', angr.__version__)"   # 先确认库在
```

★ 别在 `(Resolve-ReverseToolSpec -Name 'pyre').Command` 里找 angr —— 那个环境是空的。

## 步骤

### L1 黑盒：XOR 模式自动探测

最常见的「自定义加密」就是 XOR。**单字节 XOR 用频率分析就能破**：

```python
from collections import Counter

def detect_single_byte_xor(ciphertext: bytes):
    """返回 (候选密钥, 可打印字符占比)。占比高才说明破对了。"""
    if not ciphertext:
        return None, 0.0
    common_byte, _ = Counter(ciphertext).most_common(1)[0]
    key = common_byte ^ 0x20                 # 假设最频繁字节对应空格
    dec = bytes(b ^ key for b in ciphertext)
    return key, sum(32 <= b <= 126 for b in dec) / len(dec)
```

**判据不是「解出了东西」，而是明文的「语言像不像」。** 实测（253 字节英文文本，
真密钥 `0x5A`）：

```
真密钥 0x5A   可打印占比 = 1.0000
错误密钥 0x00  可打印占比 = 0.9960     <-- ★ 一样高！
```

★ **「可打印占比」单独用会骗人**：这段明文只用到 29 种字节且全部落在
32~126，所以**无论 XOR 哪个单字节密钥，解出来仍在可打印区间**。
必须改用**字符频率评分**：

```python
ENGLISH = b"etaoinshrdluETAOINSHRDLU .,;:'\"\n"

def english_score(data: bytes) -> float:
    """常见英文字符占比。正确密钥下明显高于其他所有候选。"""
    return sum(1 for b in data if b in ENGLISH) / len(data)
```

判据取「正确密钥的频率评分显著高于其余 255 个候选」，而不是绝对阈值。

**多字节 XOR 用 Kasiski + 重合指数**：

1. 找重复 3~5 字节子串，记录间距
2. 取所有间距的 **gcd** → 候选密钥长度
3. 对每个密钥位置**单独**做频率分析

```python
from math import gcd
from functools import reduce

def kasiski_keylen(ct: bytes, min_len=3):
    dists = []
    for L in range(min_len, 6):
        seen = {}
        for i in range(len(ct) - L):
            chunk = ct[i:i + L]
            if chunk in seen:
                d = i - seen[chunk]
                if d < 2000:
                    dists.append(d)
            else:
                seen[chunk] = i
    return reduce(gcd, dists) if dists else 1
```

实测（真密钥长度 7）→ `估计 = 7`，**正确**。

**同密钥多次加密的差分**（拿到两条以上密文时最有价值）：

```python
def xor_two_cts(c1: bytes, c2: bytes):
    """同一 key 加密两段不同明文：c1^c2 == p1^p2。"""
    n = min(len(c1), len(c2))
    x = bytes(a ^ b for a, b in zip(c1[:n], c2[:n]))
    return x, english_score(x)
```

原理：`p ^ k ^ p' ^ k = p ^ p'`。⚠ 实测这条**没有区分度**：
两段异或后的可打印占比 0.3433，与随机数据 0.3594 基本相同。
原因是 `p ^ p'` 在明文结构差异大时不可读。
**只在两段明文高度相似时**才有辅助价值，别当主判据。

### L1 黑盒：区分校验和 / 压缩 / 加密

拿到一段「看不懂的字节」，先用最简单的规则排除：

```python
def classify_checksum(data: bytes, pos: int, size: int) -> str:
    """size >= 16 -> 哈希；能对上 XOR/SUM -> 简单校验；否则是 CRC/加密。"""
    if size >= 16:
        return "hash (MD5/SHA)"
    body = data[:pos] + data[pos + size:]
    xor_v = 0
    for b in body:
        xor_v ^= b
    add_v = sum(body) & ((1 << (size * 8)) - 1)
    ck = int.from_bytes(data[pos:pos + size], "big")
    if xor_v == ck:
        return "XOR checksum"
    if add_v == ck:
        return "additive checksum"
    return "CRC or unknown"
```

用**多条样本**统计命中率，别只看一条。实测各 50 条：

```
XOR checksum        : 50/50 命中 -> 确认
additive checksum   : 46/50 命中 -> 确认
CRC or unknown      : 49/50 命中
```

一条命中是巧合，**≥90% 命中才是规律**。
注意 additive 只有 46/50 —— 1 字节加和天然会发生 mod 256 回绕，
**永远用多条样本统计**，单条对不上不能下结论。

### L2 灰盒：动态插桩截获中间状态

核心思想：**不要在函数入口/出口看，要在中间看**。

```javascript
// 加密函数出口拿输入输出对
const enc = Module.findExportByName(null, "MyEncrypt")
  || Module.findBaseAddress("target.dll").add(0x1234);

Interceptor.attach(enc, {
  onEnter(args) { this.key = args[2]; this.plain = args[1]; },
  onLeave(ret) {
    console.log("key  =", hexdump(this.key,  {length: 32}));
    console.log("plain=", hexdump(this.plain, {length: 32}));
    console.log("crypt=", hexdump(ret,      {length: 32}));
  }
});
```

拿到 `key / plain / crypt` 三元组后，**离线**去试各种算法组合 —— 这一步把
「动态」变回「静态」，迭代速度是数量级的差别。

**内存写入追踪**（找「谁写了输出缓冲区」）：

```javascript
// 输出缓冲区被写时立刻抓内容，比在函数返回时抓更早
Interceptor.attach(Module.findExportByName(null, "memcpy"), {
  onEnter(args) {
    const dst = args[0], src = args[1], n = args[2].toInt32();
    console.log(`memcpy dst=${dst} src=${src} n=${n}`);
  }
});
```

### L2 灰盒：数据流追踪

静态看不到中间值时，用 `MemoryAccessMonitor` 标出输入区间，
看哪些代码读了它 —— 每个 `from` 地址就是一个候选的变换步骤：

```javascript
MemoryAccessMonitor.enable({
  ranges: [{ base: inputAddr, size: inputSize }],
  onAccess(details) {
    // from = 读/写了输入区的那个指令地址
    // 这批地址就是「输入 -> 输出」的完整变换链
    console.log(`${details.operation} at ${details.address} from ${details.from}`);
  }
});
```

**判据**：`from` 地址聚成 5~20 个热点函数 → 变换链就这么长，逐个反编译即可。
地址爆炸成上千个说明有间接调用/查表分散了数据流。

### L3 白盒：查找表与硬编码常量

**先用 `algo_identify.py` 扫白盒**（它有专门的弱指纹）：

```powershell
& $py $ai .\sample.exe --min-score 0.5 | Select-String '白盒'
```

判据是「同一 blob 内 **≥6 张等间距**、每张 256 项几乎全互异的表」——
标准 Chow WB-AES 把 9~10 轮 T-box 连续排布。置信度只给 0.60，**必须人工确认**：

```python
# 确认：找到查表指令（按索引寻址的 movzx/lea），而不是常量数组
# 找 T-table 的典型模式： movzx eax, byte [rcx + rdx*4] ; 查表取 4 字节
```

在 r2 里：

```powershell
& $r2 -2 -qc '/x 8b048b0d8b34c8b1c; q' .\sample.exe 2>$null
```

★★ `/x` 返回空先查字节序与通配符（`.` 通配、`??` 不通配），不是 r2 的问题
（2026-10-10 本机实测复核，见 `crypto-algorithm-identification.md` 坑 3），
失败就改用 `aob-signature-scan.md` 里的 yara-python 方案。

**不透明常量展开**（运行时才算出来的常量）：静态看不到，就得动态 dump。
`VirtualProtect` 调用点前后 dump `.text`，diff 出来的就是被写进去的常量。

### L4 符号执行：angr 恢复密钥

只在「已知明文-密文对 + 密钥是符号变量 + 变换代码短」时才值得：

```python
import angr, claripy

proj = angr.Project("target.exe", auto_load_libs=False)
sym_key = claripy.BVS("key", 128)          # 128-bit 密钥
state = proj.factory.call_state(enc_addr, claripy.BVV(plain), sym_key)
sm = proj.factory.simulation_manager(state)
sm.run()
for st in sm.active:
    st.solver.add(st.regs.eax == int.from_bytes(cipher, "little"))
    if st.solver.satisfiable():
        print(st.solver.eval(sym_key))       # 拿到密钥
```

**判据是 `satisfiable()` 为 True**，而且最好换一组明文再解一次 ——
能对上的才叫密钥。

⚠ **成本警告**：angr 在有反调试、有 JNI、有大循环的目标上可能几十分钟无结果。
先用 `sm.step()` 步进几步看路径数是否爆炸；`sm.active` 超过几千条就直接放弃转 L3。
本机 angr 10.0.1 可用（`& $py -c "import angr"`），但**具体目标的可行性未在本机验证**。

### z3 直接解 XOR

比 angr 轻得多，优先试：

```python
from z3 import BitVec, Solver, sat

def solve_xor_key(plain_pairs, key_len):
    """多组 (plain, cipher) 解出 XOR 密钥"""
    s = Solver()
    k = BitVec("k", key_len * 8)
    for p, c in plain_pairs:
        kb = k.to_bytes(key_len, "big")
        val = BitVec("x", key_len * 8)
        s.add(val == BitVecVal(int.from_bytes(c, "big"), key_len * 8))
        # 逐字节 XOR 约束
        for i in range(key_len):
            pb = BitVecVal(p[i], 8)
            kb_i = BitVec(f"k{i}", 8)
            s.add(kb_i == (pb ^ BitVecVal(c[i], 8)))
    return s.check() == sat
```

多组明文-密文对能把解唯一化。**一组往往有多个解，两组以上基本唯一**。

## 判据

「某个自定义变换已被还原」必须满足**三条**，缺一不可：

1. **能离线复现**：把提取到的参数（密钥/S-box/轮常数）填进自己写的实现，
   对**至少 3 组未参与推导**的样本，算出的密文与目标输出**逐字节相同**。
   「看着像」不算，必须逐字节 diff。
2. **参数有独立证据**：密钥/S-box 要么在 `.rdata` 里被 `r2 px` dump 出字节，
   要么在动态 hook 的参数里被打印出来。**不能只靠 z3 解出来的值**——
   z3 会给你一个「满足约束」的解，但不一定是程序真正用的那个。
3. **换样本仍成立**：用不同长度 / 不同内容的输入再验 3 组。
   判据是 `3/3 组逐字节一致`，不是 `1 组一致`。

分层验证的成本阶梯：

| 层 | 验证方式 | 判据 |
|---|---|---|
| L1 | 可打印占比 / 重合指数 | `printable_ratio > 0.9` |
| L2 | hook 抓到的三元组 | key/plain/crypt 三者都 dump 到了 |
| L3 | 找到查表指令 + dump 表 | `movzx eax, byte [rcx+rdx*4]` 存在 |
| L4 | z3/angr 可满足 | `satisfiable()==True` 且换样本仍 sat |

## 坑

1. ★ **别一上来就用 angr**。L1 频率分析秒级能破的单字节 XOR，
   用符号执行可能跑几十分钟。**从最低成本层开始往上爬**。
2. ★ **`srand`/种子固定时「随机」是伪随机**。同种子跑两次输出相同，
   说明用了普通 PRNG 而不是加密原语 —— 先跑 `prng-cracking.md` 排除这条。
3. **Frida 注入会触发反作弊/反调试**。目标有保护时先过
   `anti-debug-bypass.md`，否则脚本根本加载不进去，你看到的是「无输出」
   而不是「没有中间值」。
4. **hook 点选错看不到数据**。函数返回时缓冲区可能已被清零或已释放。
   优先 hook `memcpy`/`RtlMoveMemory` 这类**搬运指令**的调用点。
5. **`MemoryAccessMonitor` 会明显拖慢目标**，回调本身有开销。
   只监视真正需要的区间，别整片堆都挂上。
6. **自造验证样本时 `-O2` 会把常量折叠掉**。详见
   `crypto-algorithm-identification.md` 坑 4 —— 自建样本里没常量，
   不是工具没找到。写完样本先用 `python -c` 的 `find` 确认字节真在文件里。
7. **CRC/哈希表要近似匹配**。手抄表错 1 项就全表失配（实测错 4 项）。
   要求 `>=252/256` 项吻合。
8. **z3 一组约束通常有多个解**。至少用两组明文，否则解出来的「密钥」
   只是众多可行解之一，对不上真实实现。
9. **白盒结论永远要人工确认**。`algo_identify.py` 对白盒只给 0.60/0.55，
   因为「一张乱序表」和「白盒 T-box」在字节层面很像。
10. **别把 `Unknown` 当结论**。`algo_identify.py` 退出码 1 只说明「没命中已知指纹」，
    不代表「不是标准算法」—— 也可能是被混淆过的标准实现（运行时才生成 S-box）。
    这正是本文存在的理由。

## 相关

- `crypto-algorithm-identification.md` — 先跑常量指纹；退出码 1 才需要本文
- `prng-cracking.md` — 「随机」可能是可预测 PRNG，先排除
- `unpack-and-memory-dump.md` — 常量被壳压缩时的前置
- `anti-debug-bypass.md` — Frida 注入前必须先过反调试
- `aob-signature-scan.md` — 找查表指令的替代方案（r2 `/x` 不可靠时）
- `direct-syscall.md` — 加密 API 走直接系统调用时怎么 hook
- `../../game-reverse/references/game-anti-cheat-bypass.md` — 客户端侧自定义加密的实战视角
- `../SKILL.md` — 总纲