# VMP/dex2c 加固识别与形态判定

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/apk-reverse/techniques/07-packer/03-vmp-dex2c-detection.md`
> **什么时候用**：jadx 打开 APK 后关键方法体是空的、`nop` 填充或只剩 `return-void`，需要先判定「虚拟化」还是「抽取」，再决定路线。

## 适用信号

- jadx 中目标方法体为空 / `nop` 填充 / 只剩 `return-void`
- 方法声明为 `native`，但 JNI 命名不符合 `Java_com_*`（走 RegisterNatives 动态注册）
- `lib/` 下出现加固特征 so：`libjiagu.so`（爱加密）、`libDexHelper.so`（梆梆）、`libshell*.so` / `libtprt.so`（腾讯乐固）、`libnqshield.so`（网易易盾）
- dex 方法数巨大但 CodeItem 很小或缺失
- so 的 `strings` 输出几乎不可读；so 内存在 dispatch 大循环
- 运行时行为完全正常，但静态读不到逻辑

## 两种形态

### 形态 A：商业加固 dex2c/VMP 壳（最普遍）

Java 方法在编译期或壳加载期被转成 **dex2c**（转 C++ 编译进 so）或**自定义字节码**（so 内 native 解释器 dispatch 执行）。

```
- dex 中方法体被 nop 填充或替换为 stub
- 方法以 native 形式存在，通过 RegisterNatives 动态绑定
- so 内有解释器：取 opcode → 跳转表 → handler 的 dispatch 循环
- 字符串池加密，运行时解密
```

### 形态 B：VMProtect 商品保护（保护 so 本体）

dex / Java 层**完全正常**，被保护的是 so 内的 C/C++/Rust 函数（license 校验、协议加密等）。so 入口是 VM entry 桩 + 解释器循环。

**判定要点：Java 层逻辑是否可读。可读 → 形态 B（转 so 分析）；不可读 → 形态 A（先走脱壳/还原）。**

## 前置

```powershell
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
$r = Resolve-ReverseToolSpec -Name 'apktool'; & $r.Command --version
$r = Resolve-ReverseToolSpec -Name 'jadx';    & $r.Command --version
```

Python 侧（capstone 5.0.7 / pyelftools 0.33 / lief 1.0.0 均在本机 `(Resolve-ReverseToolSpec -Name 'pyre').Command`）：

```powershell
$r = Resolve-ReverseToolSpec -Name 'python'; & $r.Command -c "import capstone,elftools;print(capstone.__version__, elftools.__version__)"
```

## 步骤

### 1. 解包并看加固 so

```powershell
$at = (Resolve-ReverseToolSpec -Name 'apktool').Command
& $at d target.apk -o target_apktool -f
Get-ChildItem target_apktool\lib -Recurse -Filter *.so | Select-Object FullName, Length
```

### 2. 统计 smali 空壳率（本机已验证脚本）

```powershell
$r = Resolve-ReverseToolSpec -Name 'python'
& $r.Command 'C:\relab2\skillpack\skills\apk-reverse\scripts\smali-stub-ratio.py' target_apktool
```

本机实测输出（一个 2 方法的最小样本，`stub_ratio_strict=50.0%` 时它命中了判据阈值，但绝对数只有 1 —— 这正说明分母小时比例不可单独采信）：

```
scanned_files=1
methods=2  stub(nop/return-only)=1  trivial=0
stub_ratio=33.3%  (全部分母含 trivial)
stub_ratio_strict=50.0%  (只看有指令的方法)
```

### 3. 扫 so 的解释器 dispatch（VMP 静态核心特征）

```powershell
$r = Resolve-ReverseToolSpec -Name 'python'
& $r.Command 'C:\relab2\skillpack\skills\apk-reverse\scripts\find-vm-dispatch.py' lib\arm64-v8a\libtarget.so
```

`find-vm-dispatch.py` 判定一个窗口是不是解释器，依据四条**共现**特征（单条指令没有信息量）：

| 特征 | 含义 |
|---|---|
| `LDRB_opcode` | 从 `[reg]` 取字节 = 取 opcode |
| `AND_mask` | `opcode & 0xff` 掩码 |
| `LDR_table_index` | `LDR Xt,[Xn,Xm,LSL #3]` = 8 字节/项的跳转表索引 |
| `BR_indirect_jump` | `BR Xn` 间接跳到 handler |

score ≥ 3 才报候选。本机用合成的 ARM64 dispatch 桩验证，命中全部 4 条：

```
elf_class : ELF64  machine=EM_AARCH64  entry=0x400478
insns     : 16

发现 1 个 dispatch 候选区间:

[score=4]  0x401000 - 0x401038   (16 insns)
   特征: AND_mask, BR_indirect_jump, LDRB_opcode, LDR_table_index, table_addr
     0x401000  stp      x29, x30, [sp, #-0x20]!
     0x401004  mov      x29, sp
     0x40100c  ldrb     w5, [x3]
     0x401010  and      w5, w5, #0xff
     0x401014  adr      x6, #0x402054
     0x401018  ldr      x7, [x6, x5, lsl #3]
     0x40101c  br       x7
```

### 4. DiE 扫 so 特征

```powershell
$diec = (Resolve-ReverseToolSpec -Name 'diec').Command
& $diec -b lib\arm64-v8a\libtarget.so
```

本机对一个真实 ARM32 Android SO 的输出格式：

```
ELF32
    Operation system: Android[ARM, 32-bit, DYN]
```

### 5. 查 `.init_array`（构造函数 / 反调试入口）

```powershell
$r = Resolve-ReverseToolSpec -Name 'python'
& $r.Command -c @"
from elftools.elf.elffile import ELFFile
import struct, sys
p = sys.argv[1]
with open(p,'rb') as f:
    e = ELFFile(f)
    w = 8 if e.elfclass == 64 else 4
    for s in e.iter_sections():
        if s.name in ('.init_array','.fini_array'):
            d = s.data()
            for i in range(0, len(d) - w + 1, w):
                va = int.from_bytes(d[i:i+w],'little')
                print('  %s[%d] = 0x%08x' % (s.name, i//w, va))
"@ lib\arm64-v8a\libtarget.so
```

本机实测（真实 ARM32 SO）：

```
=== .init_array (构造函数列表) ===
  .init_array[0] = 0x0005352c
```

## 判据

| 观察 | 结论 |
|---|---|
| Java 层可读 + so 内有 dispatch 候选 | **形态 B**：so 内函数被虚拟化，转 so 静态分析 |
| Java 层空/nop + 加固 so + dispatch 候选 | **形态 A**：商业 dex2c/VMP 壳，走 trace 路线 |
| Java 层空/nop + 加固 so + **无** dispatch | 疑似抽取壳（指令被抽走待回填），先试 dump 路线 |
| 无加固 so + 逻辑缺失 | 自定义 ClassLoader / 其他混淆，回 `entry-point-tracing` 重新定位入口 |
| dump 后目标方法仍无 CodeItem | **VMP 确认**，dump 路线终止，转 `vmp-dump-trace-recovery` |

**外部可观测的判据**：`find-vm-dispatch.py` 输出里出现 `[score=N]` 且 `N>=3` 的区间行，且该 so 在 `lib/<abi>/` 下；不是「看起来像虚拟化」。

### 与抽取壳的区分

| 特征 | 抽取壳（方法体被抽走） | VMP/dex2c |
|---|---|---|
| dex 方法体 | `nop` 填充 | `nop` 或 native stub |
| 指令在哪 | 壳运行后**回填** dex 内存 | 自定义字节码在 so，**不回填** |
| dump 是否有效 | 有效 | **无效**（dump 不到 CodeItem） |
| so dispatch | 无 | 有 |
| 还原难度 | 低 | 高（需 trace 解释器） |

## 坑

- **分母小时比例失真**：小样本 `stub_ratio` 能到 50% 却毫无意义，必须同时看绝对 stub 数和总方法数。
- **`find-vm-dispatch.py` 只扫 ARM/ARM64**：x86/x86_64 的 `.so` 会被直接拒绝退出。
- **`adr` 在真实 so 里可能换成 `add`/`ldr =`**：脚本把 `adr`、以及操作数含 `table` 的 `add` 都算作 `table_addr`，但命名被 strip 时这条特征会丢，所以 score 门槛是 3 不是 5。
- **`skipdata=True` 会产生 `.byte` 伪指令**：这些不参与打分，输出里出现 `.byte` 属正常，不影响判定。
- **OLLVM 控制流平坦化会把 dispatch 特征打散**：此时脚本报「未发现」，但 so 仍可能是混淆的，先走 `obfuscation-detection`。
- **`libjiagu`/`libshell` 这类文件名会随版本变化**，不要写死判断条件；同时看 so 大小和 `.init_array` 条目数。
- **dex2c 还原没有成熟开源还原器**，别指望一键工具，见 `vmp-dump-trace-recovery`。

## 相关

- `vmp-dump-trace-recovery.md` —— 形态判定后的 dump / trace / 还原路线
- `vmp-anti-debug-bypass.md` —— 做 trace 前必须先过的反调试
- `obfuscation-detection.md` —— 混淆形态（OLLVM / UPX / 字符串加密）
- `../dex-java/entry-point-tracing.md` —— 无加固 so 时的入口回溯
- `../native/il2cpp-offset-discovery.md` —— IL2CPP/UE4 so 的偏移发现
