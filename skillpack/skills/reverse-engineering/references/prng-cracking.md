# PRNG 破解：从输出序列反推生成器与后续值

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/general/techniques/crypto/03-prng-randomness-cracking.md`
> **什么时候用**：从游戏/客户端里捞到一串连续「随机数」（随机种子、随机点位、随机延迟、抽奖结果），要回答「这是哪类 PRNG」「能不能预测下一个」「是不是密码学安全随机」。

配套工具：`skills/reverse-engineering/scripts/prng_detect.py`（纯标准库）。

## 适用信号

- 逆向到一段「取随机数」的逻辑，怀疑是 `rand()` / LCG / xorshift
- 从内存或抓包里拿到一串连续输出值，想知道算法类型
- 抽奖、掉落、地图点位、机器人移动「看起来有规律」
- 想判断「这是普通 PRNG（可预测）还是 CSPRNG（不可预测）」
- 需要**预测后续输出**（自建/实验程序）

## 前置

```powershell
$py = (Resolve-ReverseToolSpec -Name 'pyre').Command
$pd = 'C:\relab2\skillpack\skills\reverse-engineering\scripts\prng_detect.py'
```

`prng_detect.py` **只用标准库**，任何解释器都能跑。但本机统一用 `(Resolve-ReverseToolSpec -Name 'pyre').Command`。

**第一步永远是先造样本自测**（不用找样本，脚本自带生成器）：

```powershell
& $py $pd --demo glibc
& $py $pd --demo musl
& $py $pd --demo mt19937
```

## 步骤

### 步骤 1：把输出喂进去

```powershell
# 文件：每行一个值（十进制或 0x 十六进制，# 开头为注释）
& $py $pd --outputs .\rand_out.txt

# 直接给十六进制字
& $py $pd --hex 8f2a1c3d 5e6f7081 12345678

# 带种子（输出被截断的 PRNG 必填，见坑 1）
& $py $pd --outputs .\rand_out.txt --seed 12345

# JSON
& $py $pd -o .\rand_out.txt --json
```

### 步骤 2：内置 demo 全绿（实测基线）

五个内置生成器**全部识别正确**，这是判断工具本身没坏的基线：

```
borland   rc=0  [1] LCG — Borland C rand()            置信度 0.99
glibc     rc=0  [1] LCG — glibc (ANSI-C / BSD)        置信度 0.99
minstd    rc=0  [1] LCG — C++11 minstd_rand           置信度 0.99
musl      rc=0  [1] LCG — MUSL libc (u64)              置信度 0.99
mt19937   rc=0  [1] Mersenne Twister — MT19937         置信度 0.99
```

每条的依据都是**逐个严格验证**，不是猜的。实测输出（glibc）：

```
[1] LCG — glibc (ANSI-C / BSD)   置信度 0.99
    依据   : 前 12 个输出全部严格满足 S'=(a*S+c) mod m
             (m=2147483648, a=1103515245, c=12345)
    参数   : {'m': 2147483648, 'a': 1103515245, 'c': 12345,
              'output_shift': None, 'output_mask': None}
```

MT19937 的依据更强 —— 它做的是**状态恢复 + 预测验证**：

```
[1] Mersenne Twister — MT19937 (Python random / C++11 std::mt19937)   置信度 0.99
    依据   : untemper 恢复 624 字内部状态后，预测的后续 4 个输出匹配 4/4
    参数   : {'state_size': 624, 'word_size': 32}
```

「预测 4 个、匹配 4 个」—— 这不是统计，是**把状态真算出来了**。

### 步骤 3：★ 真实编译程序的输出（不是 demo）

自建 `prng_probe.c`，用平台的原生 `rand()`，MinGW gcc `-O2` 编译：

```c
#include <stdio.h>
#include <stdlib.h>
int main(int argc, char **argv) {
    int mode = (argc > 1) ? atoi(argv[1]) : 0;
    if (mode == 0) {                 /* 原生 rand() */
        srand(12345);
        for (int i = 0; i < 12; i++) printf("%u\n", (unsigned)rand());
    } else {                         /* MMIX 64-bit LCG */
        unsigned long long s = 88172645463325252ULL;
        for (int i = 0; i < 12; i++) {
            s = s * 6364136223846793005ULL + 1442695040888963407ULL;
            printf("%llu\n", s);
        }
    }
    return 0;
}
```

★ **在 bash 里直接 `/d/Tools/runtime/mingw64/bin/gcc` 会报 `command not found`**。
必须写 bat 包装：

```bat
@echo off
set PATH=D:\Tools\runtime\mingw64\bin;%PATH%
cd /d C:\relab2\work
gcc -O2 -o prng_probe.exe prng_probe.c
```

实测输出（`prng_probe.exe 0`，原生 `rand()`）：

```
7584 19164 25795 22125 5828 23405 27477 5413 29072 23404 14959 14800
```

识别结果（**必须带 `--seed`**）：

```
==============================================================================
prng_detect — rand_out.txt
输出个数 : 12
前 8 个  : 0x1da0 0x4adc 0x64c3 0x566d 0x16c4 0x5b6d 0x6b55 0x1525
==============================================================================
[1] LCG — MSVCRT/UCRT rand()   置信度 0.98
    依据   : 已知种子 12345 下，全部 12 个输出逐个吻合
             S'=(a*S+c) mod m (m=4294967296, a=214013, c=2531011，
             输出取 state>>16 & 0x7FFF) —— 输出被截断，只能靠已知种子正向重放验证
    参数   : {'m': 4294967296, 'a': 214013, 'c': 2531011,
              'output_shift': 16, 'output_mask': 32767, 'seed': 12345}
```

**这是 Windows 上最重要的一个 PRNG。** 前面第一步「不带 seed」跑同一份数据：

```
rc=1
[1] Unknown — 未识别   置信度 0.00
    依据   : 不匹配本工具覆盖的 LCG / MT19937 / XorShift 族；
             若来源可信，可能是密码学安全随机数（CSPRNG）。
```

带了错误的 seed（`--seed 999`）也回 Unknown：

```
rc=1  [1] Unknown — 未识别   置信度 0.00
```

**⇒ 结论「Unknown」不能直接当成 CSPRNG 的证据。**
输出被截断的 PRNG 在没有正确种子时**必然** Unknown。必须先排除截断再下结论。

MMIX 那组（`prng_probe.exe 1`）不需要 seed：

```
[1] LCG — MUSL libc (u64)   置信度 0.99
    依据   : 前 12 个输出全部严格满足 S'=(a*S+c) mod m
             (m=18446744073709551616, a=6364136223846793005, c=1442695040888963407)
```

注：MMIX 参数与 MUSL 相同（都是 `6364136223846793005 / 1442695040888963407 / 2^64`），
**凭输出无法区分这两个来源**。工具报 MUSL 是因为 profile 表里先命中它。
要区分得看代码里调的哪个库。

### 步骤 4：MT19937 状态恢复与预测

MT19937 是最值得预测的目标（624 字状态，可完全恢复）：

```python
def untemper(y):                     # 逆 tempering，4 步异或移位
    y ^= y >> 18
    y ^= (y << 15) & 0xEFC60000
    y ^= (y << 7) & 0x9D2C5680
    y ^= y >> 11
    return y & 0xFFFFFFFF
```

- 拿到 **≥624 个连续 32-bit 输出** → untemper → 重建状态 → 预测后续
- 只需要 **624 个已知输出**（不是 19937 个），这是 MT 最有攻击面的地方

工具的判据就是这个：**恢复状态后预测后续 4 个，匹配 ≥3 个才算命中**。
匹配 4/4 给 0.99，3/4 给 0.90。

### 步骤 5：LCG 参数恢复（未知 a/c/m）

用相邻差值解线性方程：

```
a = (v2 - v3) * inverse(v1 - v2)  (mod m)
c = v2 - a * v1                  (mod m)
```

★ **样本量门槛 = 8 个**。LCG 有 3 个自由度（a/c/m），n 个输出只有 n-1 个约束，
`n ≤ 4` 时必然欠定 —— 任何 3~4 个数都能被拟合出一组合法 a/c。
所以少于 8 个输出直接不给结论。

★ 差值解法**只对无后处理的序列有效**。输出若被截断（shift/mask），差分解必失败。
工具的 `recover_lcg_unknown` 因此对截断序列零命中 —— 这是设计如此，不是 bug。

### 步骤 6：确认算法后怎么用

拿到 `(m, a, c, shift, mask)` 后，**不需要种子**就能从**任意一个观察到的输出**
往后推（只要该输出未被截断）：

```python
m, a, c, shift, mask = 2**32, 214013, 2531011, 16, 0x7FFF
# 截断型（MSVCRT）：低 16 位丢失，无法正推 —— 只能倒推：
# 由 y = (S>>16)&0x7FFF 解出 S 的高 16 位，低 16 位有 65536 个候选，
# 逐个代入后续输出验证，通常 2~3 个输出就能唯一确定。
```

**预测能力判据**：把预测值和「实际下一个输出」比对，**逐个吻合**才算成立。
工具的 `cross_check` 字段就是在多组起始偏移上重复这个验证：

```
交叉验证 : 8/8 条起始偏移得出同一结论
```

## 判据

「序列属于某 PRNG」必须满足**两条**，缺一不可：

1. **严格递推吻合**：stdout 出现 `全部 N 个输出逐个吻合` 或
   `前 N 个输出全部严格满足`，且 N = 实际喂进去的个数。
   实测 12 个输入 → 输出写「全部 12 个输出逐个吻合」，**不是**「前 8 个」。
2. **交叉验证一致**：`交叉验证 : 8/8` 或 `3/3` 条起始偏移得出同一结论。
   若显示 `1/3`（实测未带 seed 时的截断场景），说明结论只在一种取法下成立，不可信。

外加一条**反向判据**（排除误判）：

- 换 `--seed` 试不同的值，结论应当只在**正确种子**下出现。
  实测 `--seed 12345` → MSVCRT 命中；`--seed 999` → Unknown。
  **「换个种子就垮」是识别正确性的强证据**，比单次命中可信得多。

MT19937 的判据最强：`预测的后续 4 个输出匹配 4/4`。这是**因果预测**，
不是相关推断 —— 匹配 4/4 基本不可能是巧合。

**退出码**：`0` = 识别成功，`1` = Unknown，`2` = 输入不足/文件不存在。

## 坑

1. ★ **MSVCRT/UCRT 的 `rand()` 返回 `(S >> 16) & 0x7FFF`，高位被丢弃**。
   所以观察值**无法反推内部状态** —— 拿观察值当状态去递推，第二步必然错位。
   工具为此加了 `--seed`：给出种子后正向重放验证。
   实测本机 `srand(12345)` 的首值 `0x1DA0` 就是 `(0x9DA03218 >> 16) & 0x7FFF`。
2. ★ **只有 shift 没有 mask 会匹配失败**。MSVCRT 是 `>>16` **再** `& 0x7FFF`。
   实测「只 shift 不 mask」与真实输出不符（`shift-only matches: False`）。
   两级后处理的顺序固定为**先移位、再掩码**。
3. ★ **`srand(S)` 只写种子，不产出输出**；第一次 `rand()` 对应的状态是 `a*S+c`。
   种子本身**不与任何观察值比对**。一开始按「种子就是第一个输出」比对，
   第二步就错位，表现为明明 12 个值全对却报 Unknown。
4. ★ **带 seed 时不能做交叉验证**。截断输出必须**从第 0 个值**开始重放，
   一旦跳过前几个值种子就对不上，必然 Unknown。所以 `truncated` 时 `trials` 置 0，
   **不显示** `交叉验证` 行。看到带 seed 的输出没有交叉验证行是正常的。
5. ★ **「Unknown」≠ CSPRNG**。先确认不是截断型、不是需要 seed、样本 ≥ 8 个，
   再考虑「可能是密码学安全随机」。实测不加 seed 的 MSVCRT 输出就是 Unknown。
6. **参数指纹表有歧义**。MMIX 与 MUSL 参数相同，仅凭输出分不出。
   还要结合「代码里 import 的是哪个库」。
7. **XorShift128+（V8 `Math.random`）无法仅凭输出判定**。
   它是 64-bit 状态双精度只用 52 bit 尾数，信息量不够。
   工具只给 0.30 的提示条目，**必须用 z3 约束求解**才能确认。
8. **别信 `Get-FileHash` 在某些上下文不可用**；脚本自己算 sha256，不受影响。
9. **`--demo` 只有 5 个**（borland/glibc/minstd/musl/mt19937），
   没有 MSVCRT demo —— 因为 MSVCRT 需要 seed，跑不了 `--demo`。要测它请用真实样本。
10. **脚本 docstring 里的 Windows 路径要写成 `C:\\...`**。
    非 raw string 里 `<仓根>` 的 `\r` 会被当成回车，
    实测每次运行都刷 `SyntaxWarning: invalid escape sequence '\E'`。
    现已修成正则要用时前面加反斜杠。用 `-W error::SyntaxWarning` 自查：

    ```powershell
    & $py -W error::SyntaxWarning -c "import py_compile;py_compile.compile(r'$pd',doraise=True)"
    ```

## 相关

- `crypto-algorithm-identification.md` — 另一类常量指纹（哈希 IV、轮常数、S-box）
- `custom-obfuscation-reverse.md` — 自定义混淆里常藏 LFSR，Berlekamp-Massey 的入口
- `external-memory-rw.md` — 从目标进程里捞出 PRNG 状态/输出
- `../../game-reverse/references/game-speedhack-time-manipulation.md` — 时间类 PRNG 的实战观测
- `../../game-reverse/references/game-anti-cheat-bypass.md` — 反作弊侧如何检测可预测随机
- `../SKILL.md` — 总纲