# Trampoline Hook（内联 detour / 函数劫持）

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/pe-reverse/techniques/04-dynamic-analysis/02-trampoline-detour.md`（已适配本机工具链）
> **什么时候用**：需要在某个函数执行时插入自定义逻辑（记录参数、改返回值、拦截调用），同时保持原功能可用。
>
> **与 `naked-function-hook.md` 的分工**：那篇是**手写裸汇编 gateway**（最低开销、完整寄存器控制，代价是 x64 要写 .asm）；
> 本篇是**字节级 trampoline**（用 Python 拼字节、用 `WriteProcessMemory` 写，可脚本化、可自动化、可外部验证）。
> 只想快速验证一个 hook 想法、想进自动化流程 → 用本篇；要极限性能或要完整控制寄存器 → 用那篇。

## 适用信号

- 已定位目标函数地址（Ghidra / IDA / r2 / 特征码）。
- 函数开头有可覆盖空间，但**必须落在指令边界上**。
- 需要保持原始功能（不能直接 NOP 掉）。
- 想在自动化流程里做 hook 并**可外部验证**（读回字节确认）。

## 前置

```powershell
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
$r2   = (Resolve-ReverseToolSpec -Name 'r2').Command
$py   = 'D:\EXE\python\python.exe'    # capstone 5.0.7（算指令边界）
$cdb  = (Resolve-ReverseToolSpec -Name 'cdbX64').Command
```

## 步骤

### 1. 算 detourSize（必须落在指令边界）

**这是全篇最容易出错、后果最严重的一步。** `JMP rel32` 需要 5 字节，但**不能截断变长指令**。

用 `disasm-jit-asm.md` 判据 2 的算法（实测脚本，capstone 5.0.7）：

```python
# 逐条累加指令长度直到 >= 5
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
md = Cs(CS_ARCH_X86, CS_MODE_64); md.detail = True

def detour_size(data, base, minimum=5):
    total, n = 0, 0
    for ins in md.disasm(data, base):
        print("  0x%x (+%d) len=%d  %s %s"
              % (ins.address, ins.address - base, ins.size, ins.mnemonic, ins.op_str))
        total += ins.size; n += 1
        if total >= minimum:
            break
    return total, n
```

★ **实测 `user32!MessageBoxW` 的 detourSize 是 7，不是 5**：

```
user32!MessageBoxW rva=0x7c760
first 16 bytes: 48 83 ec 38 45 33 db 44 39 1d c2 7b 03 00 74 2e
  0x18007c760 (+0) len=4  sub rsp, 0x38
  0x18007c764 (+4) len=3  xor r11d, r11d
=> detourSize = 7 (2 instructions)
```

naive 取前 5 字节会切在 `xor r11d, r11d`（占 `+4..+6`）中间。**这条被截断的指令会导致
函数体解码整体错位、行为完全不可预测。**

### 2. Trampoline 的字节布局

```
原始调用:   caller → [func: push rbp; mov rbp,rsp; ...]

Hook 之后:  caller → [func: JMP trampoline] → trampoline:
                        ├─ 保存寄存器（push volatile regs）
                        ├─ CALL callback
                        ├─ 恢复寄存器
                        ├─ 原始被覆盖的 N 字节（逐字节复制）
                        └─ JMP func + N
```

`N` = detourSize（第 1 步算出）。

### 3. rel32 偏移公式

```
rel32 = dst - src - 5        # 5 = 1(opcode) + 4(rel32)
```

★ `src` 是**这段 JMP 最终被写入的地址**，不是构造时的占位地址。
写 trampoline 时，尾部 `JMP func+N` 的 `src` 是 trampoline 里的某个偏移 ——
那在分配内存时就是已知的，可以一次算对；而**装到目标的那条 `JMP trampoline` 的 `src`
才是运行时地址**，必须等 `VirtualAlloc` 之后才能填。

实测验证（`D:\EXE\python\python.exe`）：

```python
import struct
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
md = Cs(CS_ARCH_X86, CS_MODE_64)

target = 0x00007FF6F44B3000
detour = 0x00007FF6F44B3020
rel = target - detour - 5
jmp = b"\xe9" + struct.pack("<i", rel)
print("rel32 JMP  :", jmp.hex(" "), " rel32 = 0x%x" % (rel & 0xffffffff))
for i in md.disasm(jmp, detour):
    print("   decode  :", i.mnemonic, i.op_str, "(%d bytes)" % i.size)
```

实测输出：

```
rel32 JMP  : e9 db ff ff ff  rel32 = 0xffffffdb
   decode  : jmp 0x7ff6f44b3000 (5 bytes)
```

反汇编回环确认字节语义正确（目标地址对、长度 5）= 公式正确。

### 4. 安装 detour（本机实测往返）

```python
# roundtrip.py —— 核心片段
import ctypes, ctypes.wintypes as wt, struct

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.OpenProcess.restype      = wt.HANDLE
k32.OpenProcess.argtypes      = [wt.DWORD, wt.BOOL, wt.DWORD]
k32.ReadProcessMemory.restype = wt.BOOL
k32.ReadProcessMemory.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                  ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
k32.VirtualProtectEx.restype  = wt.BOOL
k32.VirtualProtectEx.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_size_t,
                                  wt.DWORD, ctypes.POINTER(wt.DWORD)]
k32.WriteProcessMemory.restype = wt.BOOL
k32.WriteProcessMemory.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                   ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]

pid, base, rva, stub = int(sys.argv[1]), int(sys.argv[2],16), int(sys.argv[3],16), int(sys.argv[4],16)
h = k32.OpenProcess(0x0400 | 0x0008 | 0x0010 | 0x0020, False, pid)
addr = base + rva
n = ctypes.c_size_t()

def read():
    b = ctypes.create_string_buffer(16)
    k32.ReadProcessMemory(h, ctypes.c_void_p(addr), b, 16, ctypes.byref(n))
    return b.raw[:16]

before = read()
print("1) before  : " + before.hex(" "))

old = wt.DWORD()
k32.VirtualProtectEx(h, ctypes.c_void_p(addr), 16, 0x40, ctypes.byref(old))
print("2) VProtEx  : oldProt=0x%x" % old.value)

jmp = b"\xe9" + struct.pack("<i", stub - addr - 5)
k32.WriteProcessMemory(h, ctypes.c_void_p(addr), jmp, 5, ctypes.byref(n))
d = wt.DWORD(); k32.VirtualProtectEx(h, ctypes.c_void_p(addr), 16, old.value, ctypes.byref(d))
after = read()
print("3) detour   : " + after.hex(" "))
```

实测（本机，hook 目标是一个真实 x64 程序的 `main`，RVA `0x1440`）：

```
1) before  : 56 53 48 83 ec 38 e8 15 02 00 00 48 8d 1d ce 1b
2) VProtEx  : oldProt=0x20
3) detour   : e9 54 85 00 00 38 e8 15 02 00 00 48 8d 1d ce 1b
   wrote   : e9 54 85 00 00
4) restored : 56 53 48 83 ec 38 e8 15 02 00 00 48 8d 1d ce 1b

VERDICT: PASS
```

★ 三行 hex 对照就是判据：`before` 的前 5 字节被替换成 `e9 54 85 00 00`（`JMP rel32`），
**第 6 字节及之后保持不变**（`38` 仍在前），`restored` 与 `before` 逐字节相同。

★ `oldProt=0x20` = `PAGE_EXECUTE_READ`（代码段的标准保护）。写完**必须还原**。

### 5. 卸载（写回原始字节）

```python
k32.VirtualProtectEx(h, ctypes.c_void_p(addr), 16, 0x40, ctypes.byref(old))
k32.WriteProcessMemory(h, ctypes.c_void_p(addr), before[:5], 5, ctypes.byref(n))
d = wt.DWORD(); k32.VirtualProtectEx(h, ctypes.c_void_p(addr), 16, old.value, ctypes.byref(d))
back = read()
print("4) restored : " + back.hex(" "))
assert back == before
```

★ **恢复的是「当初覆盖的那几个字节」**（detourSize 个），不是 16 个 ——
覆盖 5 字节就只写回 5 字节。写多了会破坏后面本没动过的指令。

### 6. x86 vs x64 差异

| | x86 | x64 |
|---|---|---|
| `JMP rel32` | `E9 xx xx xx xx`（5 字节，范围 ±2GB） | 同，范围受限 |
| 绝对 `JMP` | `E9 rel32` | `FF 25 00 00 00 00` + 8 字节地址（**14 字节**） |
| `CALL rel32` | `E8 xx xx xx xx`（5 字节） | 同 |
| 保存寄存器 | `pushad`(0x60) / `popad`(0x61)，1 字节 | **无 pushad** —— 需逐个 push/pop volatile 寄存器 |
| shadow space | 不需要 | **需要 0x20**（32 字节） |

x64 必须手动保存 volatile 寄存器（`RAX, RCX, RDX, R8-R11`），非 volatile（`RBX, RBP,
RSP, R12-R15`）可不动但更稳妥是全存。

### 7. NOP 填充

```python
def write_nop_sled(addr, count):
    """把 count 字节填 0x90。"""
    old = wt.DWORD()
    k32.VirtualProtectEx(h, ctypes.c_void_p(addr), count, 0x40, ctypes.byref(old))
    k32.WriteProcessMemory(h, ctypes.c_void_p(addr), b"\x90" * count, count, ctypes.byref(n))
    d = wt.DWORD(); k32.VirtualProtectEx(h, ctypes.c_void_p(addr), count, old.value, ctypes.byref(d))
```

用途：禁条件跳转（`74 05` → `90 90`）、强制返回（函数体 NOP 掉留 `ret`）、NOP 掉反调试调用。
**具体 patch 语义见 `code-patching.md`。**

## 判据

1. ★★ **detourSize 落在指令边界**。判据形态：capstone 逐条打印的 `(+N) len=M`，
   最后一条的 `(+N) + M >= 5`，且打印 `=> detourSize = T`。
   **实测 `user32!MessageBoxW` 是 7 不是 5** —— 若脚本给出 5，说明切在指令中间。
2. ★★ **写入后的字节验证（round trip）**。判据形态是三行 hex 对照：
   ```
   1) before  : 56 53 48 83 ec 38 e8 15 02 00 00 ...
   3) detour   : e9 54 85 00 00 38 e8 15 02 00 00 ...
   4) restored : 56 53 48 83 ec 38 e8 15 02 00 00 ...
   ```
   三点必须成立：(a) `detour` 前 5 字节是 `E9` 开头的 rel32；(b) `detour[5:]` 与 `before[5:]` 完全相同；
   (c) `restored == before`。**这是本篇唯一真正可外部观测的判据**，实测 `VERDICT: PASS`。
3. **rel32 公式经反汇编验证**：判据形态是「拼出的 5 字节反汇编回 `jmp <目标地址>`」。
   实测 `e9 db ff ff ff` → `decode : jmp 0x7ff6f44b3000 (5 bytes)`。
   **若反汇编出的目标地址和预期不符，偏移算错了。**
4. **页保护还原**：判据形态是 `oldProt=0x20` 被记录，写完还原后再次查询得到相同值。
   **写完不复原 → 目标代码页变成可写，触发完整性校验 / 反作弊告警。**
5. **hook 实际生效**（在字节验证之上）。判据形态：hook 住某个高频函数后，
   目标程序的该函数不再被正常执行，或你的 callback 侧效应被观察到
   （文件生成 / 日志 / 计数器）。**字节改了 ≠ hook 生效** —— callback 写错、
   寄存器没保存对都会导致「改了但没效果」或直接崩溃。

## 坑

1. ★★ **naive「取前 5 字节」会在变长指令中间截断**。实测 `MessageBoxW` 的答案是 **7**。
   必须用 capstone 逐条累加到 ≥5 的第一条边界。切断了 `xor r11d, r11d` 这类
   会让整个函数体解码错位。
2. ★★ **`src` 是最终写入地址，不是构造地址**。trampoline 尾部的 `JMP func+N` 可以在分配时就算对
   （`src` 已知）；但装到目标的 `JMP trampoline` 的 `src` 必须等 `VirtualAlloc` 之后才有值。
   **算错 = 跳到随机地址 = 目标崩溃。**
3. ★★ **写完不还原页保护**。`oldProt` 必须记录并还原。实测 `oldProt=0x20`（`PAGE_EXECUTE_READ`）。
4. ★★ **x64 没有 `pushad`/`popad`**。用 MSVC/x64 时必须逐个 push/pop volatile 寄存器，
   且 call callback 前要留 **0x20 shadow space**，否则栈损坏。x86 的 `60`/`61` 在 x64 下非法。
5. **恢复时只写回覆盖过的字节**（detourSize 个）。实测覆盖 5 字节就写回 5 字节；
   写多了破坏后面对齐好的指令。
6. **`JMP rel32` 范围 ±2GB**。跳板或目标相距超过 2GB（罕见但可能）要用 14 字节绝对 `JMP`。
7. **`WriteProcessMemory` 到 `PAGE_EXECUTE_READ` 段会失败**。必须先 `VirtualProtectEx` 改 RWX。
8. **`$PID` 在 PowerShell 里是保留变量**，别拿它存目标进程 ID（见 `dll-injection-patterns.md` 坑 3）。
9. **`ctypes` 调 WinAPI 要设 `argtypes`/`restype`**，否则 64 位 HANDLE 被截断（实测报 `WinError 87`）。
10. **目标是 ASLR 下运行时地址**，`base + rva` 每次运行都不同。hook 前必须重新取当次的 base，
    复用上次的绝对地址 = 写到无关内存。

## 相关

- `disasm-jit-asm.md` — detourSize 算法的来源、rel32 字节构造
- `naked-function-hook.md` — 手写 gateway 的完整寄存器保存方案
- `code-patching.md` — 改跳转/NOP 填充的字节级细节
- `external-memory-rw.md` — 本篇用的 `ReadProcessMemory`/`VirtualProtectEx` 原语详解
- `dll-injection-patterns.md` — 把 trampoline 放进注入的 DLL 里
- `struct-reconstruction.md` — 找到 hook 目标后重建其结构体