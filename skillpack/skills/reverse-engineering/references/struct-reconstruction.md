# 内存结构体逆向重建

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/pe-reverse/techniques/03-static-analysis/01-struct-reconstruction.md`（已适配本机工具链）
> **什么时候用**：反编译里反复出现 `*(this + 0xXX)` / `*(int*)(entity + 0x36C)` 这类固定偏移访问，需要把裸偏移还原成有类型、有语义的 `struct` 定义。
>
> **与 `reclass-reconstruction.md` 的分工**：本篇是**方法论**（怎么从汇编模式推类型、怎么分指针链与内嵌对象、证据账本怎么记）；那篇是**桌面侧实时重建**（ReClass GUI + hex dump 逐字段标注），且含导出 C++ 的完整流程。本篇的重心在「没有 GUI 时怎么用 capstone + pefile + cdb 手工完成同样的事」。

## 适用信号

- 反编译/反汇编里同一个基址被多种偏移访问：`*(int*)(a+0x36C)`、`*(float*)(a+0x378)`、`*(char**)(a+0x268)`。
- 已知某基地址指向一个对象，但要确定它的字段布局和 `sizeof`。
- 看到一个 `new`/`malloc` 的尺寸常量，或一个 `memset(ptr, 0, N)` 的 N —— 这是 `SizeOf` 的候选。
- 存在自引用字段（`node->next` 同类型指针）形成的链表。
- vtable 指针出现在对象首偏移（x86 `+0x0` / x64 `+0x0` 或 `+0x8`）。

## 前置

```powershell
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
$r2   = (Resolve-ReverseToolSpec -Name 'r2').Command      # D:\Tools\radare2\bin\r2.exe
$cdb  = (Resolve-ReverseToolSpec -Name 'cdbX64').Command # WindowsApps alias
$py   = 'D:\EXE\python\python.exe'                        # pefile 2024.8.26 + capstone 5.0.7
```

`pefile` / `capstone` 只在 `D:\EXE\python\python.exe`（`D:\Tools\runtime\venv-re` 是空的，只有 pyghidra-mcp）。用探测层确认解释器路径。

## 步骤

### 1. 从汇编模式推字段类型

不要靠猜，靠**访问指令的助记符**。这是最快的类型判据：

| 指令模式 | 推断类型 | 宽度 |
|---|---|---|
| `mov eax, [rcx+XXh]` | `uint32_t` / `int` | 4 |
| `mov rax, [rcx+XXh]` | `uintptr_t` / 指针 | 8（x64） |
| `movss xmm0, [rcx+XXh]` | `float`（SSE 标量） | 4 |
| `movsd xmm0, [rcx+XXh]` | `double` | 8 |
| `movups xmm0, [rcx+XXh]` | 4 个连续 float（`FVector`/矩阵行） | 16 |
| `movzx eax, byte ptr [rcx+XXh]` | `uint8_t`（零扩展） | 1 |
| `cmp byte ptr [rcx+XXh], 0` | `bool` | 1 |
| `lea rax, [rcx+XXh]` | **取地址** → 内嵌子对象或数组元素 | 随子对象 |
| `movss xmm0, [rcx+XXh]` 紧跟 `mulss`/`divss` | 标量乘除 → 大概率是数值字段（坐标/速度/缩放） | 4 |

批量提取这类访问用 r2（`\x` 通配符是 `.` 不是 `?`）：

```powershell
# x64 目标：找所有 mov eax, [rcx+disp8] 形态
& $r2 -2 -qc '/x 8b41..; q' .\sample.exe
# 找 movss xmm0, [rcx+disp8]
& $r2 -2 -qc '/x 0f1041..; q' .\sample.exe
```

或者用 capstone 直接从字节反汇编并按操作数类型聚合（更准，能区分 `movzx`/`movsx`）：

```python
import sys
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from capstone.x86 import X86_OP_MEM, X86_OP_REG

md = Cs(CS_ARCH_X86, CS_MODE_64)
md.detail = True

code = open(sys.argv[1], "rb").read()
base = int(sys.argv[2], 16)

# 收集 (offset, 宽度, 助记符) 三元组
hits = {}
for ins in md.disasm(code, base):
    if ins.mnemonic not in ("mov", "movzx", "movsx", "movss", "movsd",
                            "movups", "cmp", "lea"):
        continue
    for op in ins.operands:
        if op.type != X86_OP_MEM:
            continue
        m = op.mem
        # 只看 "基址 + 固定位移" 这种 this-pointer 模式
        if m.base == 0 or m.index != 0:
            continue
        disp = m.disp & 0xffffffff
        width = ins.op_size(0)
        hits.setdefault(disp, set()).add((ins.mnemonic, width))

for disp in sorted(hits):
    forms = ", ".join("%s/%dB" % (m, w) for m, w in sorted(hits[disp]))
    print("+0x%04x  %s" % (disp, forms))
```

实测输出形态（本机 `target.exe` 的 `.text` 段，参数需按样本调整）：

```
+0x0024  movss/4B
+0x0288  mov/4B, cmp/4B
+0x0302  mov/4B
...
```

★ 输出里同一个 `+0xXXXX` 出现多种宽度/助记符，说明那里**不是一个字段** —— 拆开。

### 2. 确定 `SizeOf`（三个独立来源，至少两个一致才算数）

```python
import pefile
pe = pefile.PE(r".\target.exe")

# 来源 1：new / malloc 的立即数
#   x64: 常见  mov ecx, <size>; call operator new
#   在 .text 里搜 lea ecx,[rip+X] 之后紧跟 call 的模式，人工确认
#
# 来源 2：memset(ptr, 0, SizeOf)  —— 构造函数的清零尺寸
# 来源 3：数组遍历步长（imul reg, reg, <stride>）
#
# 来源 4（最硬）：.bss 段的 vsize，若全局对象唯一
for s in pe.sections:
    n = s.Name.rstrip(b"\x00").decode(errors="ignore")
    print("%-10s VA=0x%05x raw=0x%05x vsize=0x%x rawsize=0x%x"
          % (n, s.VirtualAddress, s.PointerToRawData,
             s.Misc_VirtualSize, s.SizeOfRawData))
```

实测（我编译的测试程序，唯一全局结构体）：

```
.text      VA=0x01000 raw=0x00600 vsize=0x19f0 rawsize=0x1a00
.data      VA=0x03000 raw=0x02000 vsize=0x340 rawsize=0x400
.bss       VA=0x07000 raw=0x00000 vsize=0x180 rawsize=0x0
```

`.bss` 的 `vsize=0x180` 直接给出了零初始化全局对象的大小 —— 比从 `new` 里猜可靠得多。

### 3. 区分「指针链」与「内嵌对象」

这是本篇最容易搞错、后果最严重的一步。判别法只有一个：**看有没有解引用**。

```c
// 指针链（多级间接）：pB 在 +0x40，pC 在 +0x1C0
struct A { char pad[0x40]; B* pB; };   // +0x40 存的是「指向 B 的地址」
// 访问：*(uintptr_t*)((uintptr_t)obj + 0x40) → pB
//       *(uintptr_t*)((uintptr_t)pB   + 0x1C0) → pC

// 内嵌对象（直接偏移）：obj + 0x190 就是 USceneComponent 本身
struct Actor { char pad[0x190]; USceneComponent root; };  // +0x190 是对象本体
// 访问：((USceneComponent*)obj)->RelativeLocation
```

反编译里看到 `(x + 0x190) + 0x1A0` 这种**双层加法** → `+0x190` 是指针。
看到单层 `x + 0x190` → 内嵌。

★ 实测判别：把 `+0x190` 的 8 字节原样 hex dump 出来。

```
raw bytes at +0x190 = 00 30 4b f4 f6 7f 00 00
```

`0x00007ff6f44b3000` —— 小端 8 字节正好拼成 64 位地址，且落在目标模块的
image base（`0x7ff6f44b0000`）+ RVA 范围（`+0x3000`）内 → **指针，确认**。
反过来，如果这 8 字节是 `e8 03 00 00 00 00 00 00`（= 1000），那就是普通整数。

判别代码：

```python
import struct
def classify(raw8, module_base, image_size):
    v = struct.unpack("<Q", raw8)[0]
    if module_base <= v < module_base + image_size:
        return "pointer -> module (RVA 0x%x)" % (v - module_base)
    if 0x0000000000010000 <= v < 0x00007FFFFFFFFFFF:
        return "pointer -> heap/other module (%#x)" % v
    return "value (small int = %d)" % v
```

实测输出：`pointer -> module (RVA 0x3000)` —— 正是内层 `Vec3` 对象的所在节。

### 4. 从已知值域反推语义

```
值域 0..100 且随伤害递减      → int health
值域 5.5 / 500.0 / 1.25       → float（不是 int；int 解释会是 1 或随机大数）
大 64 位且落在地址范围         → 指针（见上）
与相邻字段恒等/更大             → maxHealth / 上限
取值总在 {0,1}                 → bool flag
```

注意 `1.4e-45` 这种输出 —— 那不是 float，是把整数的小 bit 当成了 IEEE754 尾数，
说明该字段是 **int** 而不是 float。源文档里这点说得对，实测也确实如此。

### 5. 证据账本（写 `struct` 前必做）

**不要因为单次内存快照就把字段命名为 `confirmed`。** 逐字段维护：

| Offset | 宽度/读写 | 候选类型与语义 | 函数/RVA | 静态证据 | 动态证据 | 置信度 |
|---|---|---|---|---|---|---|
| `+0x190` | 8 / read | `Vec3* pRoot` | `main @ 0x1440` | `mov rax,[rcx+190h]` | 读出 `0x7ff6f44b3000`，落在模块内 | **Confirmed** |
| `+0x024` | 4 / r/w | `float health` | `main @ 0x1440` | `movss` | 读出 `87.50` | **Inferred** |
| `+0x268` | 4 / r/w | `int gold` | `main @ 0x1440` | `mov dword` | 读出 `1000` | **Inferred** |

三级定义：

- **Observed** — 反汇编/伪代码/xref/运行时日志直接显示的事实（偏移、宽度、指令）。
- **Inferred** — 由偏移、访问宽度、调用上下文或值域推导出的语义；必须保留推导依据。
- **Confirmed** — 有相互独立的静态证据，且在受控运行时获得动态一致性验证。

★ 记录时必须同时写：样本 SHA256、模块 image base、RVA/VA/文件偏移换算、函数地址、工具版本。
**把 ASLR 下的运行时地址误写成静态偏移是最常见的记录错误** —— 上表的 `+0x190`
是 RVA，`0x7ff6f44b3020` 才是本次运行的 VA，两者绝不能混。

### 6. 用 cdb 现场确认（不用 ReClass 的路径）

见「判据 2」中的完整实测。用 `ba 1 eip <addr>` 在**访问指令**上停，直接 `db` 出内存：

```powershell
$cmds = "$env:TEMP\struct.txt"
@'
ba 1 eip 0x00007ff7f5361520
g
.echo ===STRUCT_FIELD===
db rcx+0x190 L1
db rcx+0x24 L1
q
'@ | Set-Content -Path $cmds -Encoding ASCII
& $cdb -cf $cmds .\target.exe
```

判据看日志里的 `===STRUCT_FIELD===` **且** `db` 打出的字节与第 3 步的 hexdump 形态一致。

## 判据

1. **`SizeOf` 有两个独立来源且一致**。来源可数：`.bss` vsize / `new` 立即数 / `memset` 尺寸 / 数组步长。**只有一个来源 = Inferred，不是判据。**
2. **指针位通过 hexdump 判别**，而不是靠反编译的变量名。判据形态：raw bytes 小端拼出的值落在**已知模块 base + RVA** 区间内。实测输出 `raw bytes at +0x190 = 00 30 4b f4 f6 7f 00 00` + `pointer -> module (RVA 0x3000)`。**若 hexdump 出的是小整数（如 `64 00 00 00 ...`），就不是指针** —— 把它标成指针会导致后面整条指针链全错。
3. **类型判据来自指令助记符**：`movss` → float，`movzx byte` → uint8_t，`lea` → 内嵌对象。判据形态是 capstone 脚本输出的 `+0xXXXX  movss/4B` 这类 `(偏移, 助记符, 宽度)` 映射行。**若同一偏移出现两种宽度，说明这里不是一个字段**，需要拆开重新分析。
4. **结构体定义能通过外部读回自证**：定出的 `struct` 拿到目标的运行时地址后，`ReadProcessMemory` 整块读出并打印所有字段，值应与目标程序自己打印的值一致。实测：

```
ReadProcessMemory ok=1 got=624 of 624
+0x000 magic     = 0xc0ffee01
+0x004 pName     = "actor#0042"
+0x024 health    = 87.50
+0x028 level     = 42
+0x02C checksum  = 0x12345678
+0x190 pRoot     = 00007FF6F44B3000  <-- pointer, NOT inline
+0x268 gold      = 1000
+0x26C moveSpeed = 5.50
chain -> *pRoot+0x00 vec3 = (1.0, 2.0, 3.0)
```

`got=624 of 624`（一次读满，无分页错误）+ 全部字段值与目标自报一致 = 结构体定义正确。
5. **链表遍历必须终止**。自引用字段定错会导致死循环或立即变 NULL。判据形态：遍历 N 个节点后遇到 NULL，且 N 与数组索引范围一致。

## 坑

1. ★★ **`+0xXXXX` 是 RVA，不是运行时 VA**。ASLR 下每次运行 base 都变。记录时把「模块 base」「RVA」「VA」「文件偏移」四者分开写。实测：`ENTITY_ADDR=0x7ff6f44b3020`，减去 `IMAGEBASE=0x7ff6f44b0000` 得 RVA `0x3020`，`pefile` 在 `.data` 里搜哨兵值得到的 RVA 也是 `0x03020` —— **两条独立路径一致**，这种交叉验证才算数。
2. ★★ **全局对象在 `.bss` 里没有文件偏移**。`PointerToRawData=0`，靠扫文件内容找哨兵值是找不到的。改用「`.bss` vsize 定 size + 运行时地址定 base」，或让目标自报地址。
3. ★ **`#pragma pack` 会让所有偏移错位**。C 结构体自然对齐下 `float health` 会在 `+0x24`；`pack(1)` 下同样字段可能落在 `+0x21`。从汇编推偏移时**不要套任何编译器对齐假设**，只信反汇编里的实际 disp。
4. **vtable 不一定在 `+0x0`**。MSVC x64 带虚表时若类有多个继承层次，vtable 指针可能在 `+0x0` 也可能在 `+0x8`；单一继承无基类才常见 `+0x0`。看 `call [rax]` 前的 `mov rax, [rcx]` 实际偏移。
5. **`movss` 也可能是「加载 float 存进 double 字段」**。看写入侧：`cvtps2pd` 之后是 `movsd`，那才是真 double。
6. **满屏 `????` 通常是读了指针不是裸值**。先用第 3 步判别，别急着解释成「字符串被加密」。
7. **同名函数不同偏移**。同一个 `update()` 在不同类里偏移不同，合并结构体前务必核对调用者的 `this` 来源。
8. **`pefile` 不在 `venv-re`**，见「前置」。


## 出口（结论回填）

回填位置：滚动报告 `assault.md`（`-Preset assault` 生成）的对应表。

- 结构体布局（字段偏移 / 类型 / 语义）→ `## findings`（类型 `format`）或直接落成代码
- 读写验证记录（外部可观测：读回值符合预期）→ `## functions` 证据
- 不确定的字段 → `## unknowns`（注明影响哪些功能）

判定：结构恢复的成品是「能拿来做 patch / 复刻目标的结构定义」，不是一张截图。

## 相关

- `reclass-reconstruction.md` — 桌面侧 ReClass 实时重建与导出 C++（GUI）
- `disasm-jit-asm.md` — capstone / rasm2 的反汇编与字节生成（本篇的指令判据基础）
- `external-memory-rw.md` — 本篇判据 4 用的外部读写实现细节
- `dll-injection-patterns.md` — 拿到结构体后注入 DLL 做内部读写
- `pe-header-parsing.md` — `.bss` / 节区 VA 与 raw 的换算
- `code-patching.md` — 把结构体偏移做成 patch 目标