# Direct Syscall（绕过用户态 Hook）

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/pe-reverse/techniques/04-dynamic-analysis/07-direct-syscall.md`（已适配本机工具链）
> **什么时候用**：目标进程的 ntdll 导出函数被安全软件/反作弊 inline hook 或 IAT hook，
> 走标准 API 会被拦截；需要直接执行 `syscall` 指令绕过用户态拦截。
>
> **核心事实**：syscall 号（SSN）**因 Windows 版本而异**。任何硬编码的 SSN 表都是过期且危险的。
> **必须运行时从本机 ntdll 提取** —— 本篇给出已在本机实测的提取脚本与输出。

## 适用信号

- `NtReadVirtualMemory` 返回 `STATUS_ACCESS_DENIED`（但你确实有权限）。
- ntdll 导出函数**开头不是** `4C 8B D1 B8 ...` 形态，而是 `E9`（JMP）或 `CC`（INT3）—— 被 hook 了。
- Procmon 里**看不到**本该出现的 API 调用（hook 层拦截或记录）。

## 前置

```powershell
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
$py = (Resolve-ReverseToolSpec -Name 'pyre').Command   # pefile 2024.8.26（静态提取 SSN）
$cdb = (Resolve-ReverseToolSpec -Name 'cdbX64').Command  # 运行时确认 ntdll 未被 hook
```

## 步骤

### 1. 读 syscall 的调用链（理解为什么要绕）

```
kernel32.ReadProcessMemory          ← win32 封装
  → kernelbase.ReadProcessMemory    ← 真正的实现
    → ntdll.NtReadVirtualMemory    ← syscall stub
      → mov r10, rcx               ← 参数从 rcx 搬到 r10（syscall ABI 约定）
        mov eax, <SSN>             ← 系统调用号
          test byte [SharedUserData+0x308], 1   ← KUSER_SHARED_DATA 的 HeuristicFlag
          je short
            ...
        syscall                    ← 进内核
          ret
```

★ **win32 层的封装（kernel32/kernelbase）才是 EDR 主要 hook 的地方**。
直接 `syscall` 完全跳过 kernel32/kernelbase 整条用户态链。

### 2. ★★ 实测提取 SSN（本机 ntdll）

**关键观察**：所有 `NtXxx` 的 stub 开头形态**高度一致**：
`4C 8B D1` (`mov r10,rcx`) + `B8 SS SS SS SS` (`mov eax,SSN`)。
**SSN 就在 stub 的第 4 字节起的 4 字节小端值。**

```python
# ssn.py —— 从本机 ntdll.dll 磁盘文件提取 SSN
import pefile

d = r"C:\Windows\System32\ntdll.dll"
pe = pefile.PE(d, fast_load=True)
pe.parse_data_directories(
    directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_EXPORT"]])

want = {"NtAllocateVirtualMemory", "NtProtectVirtualMemory",
        "NtFreeVirtualMemory", "NtWriteVirtualMemory", "NtReadVirtualMemory",
        "NtCreateThreadEx", "NtOpenProcess", "NtQueryInformationProcess",
        "NtCreateFile", "NtWriteFile", "NtClose", "NtDelayExecution",
        "NtQuerySystemInformation"}

for exp in pe.DIRECTORY_ENTRY_EXPORT.symbols:
    if exp.name and exp.name.decode() in want:
        n = exp.name.decode()
        rva = exp.address
        off = pe.get_offset_from_rva(rva)
        b = pe.get_data(rva, 0x20)
        # 提取 SSN：mov r10,rcx (4C 8B D1) 后紧跟 mov eax, imm32 (B8 ...)
        ssn = b[4] | (b[5] << 8) | (b[6] << 16) | (b[7] << 24) if b[:3] == b"\x4c\x8b\xd1" else -1
        print(f"{n:28s} rva=0x{rva:05x} off=0x{off:05x} SSN=0x{ssn:03x} ({ssn:4d}) bytes={b[:12].hex(' ')}")

print("ntdll ImageBase=0x%x" % pe.OPTIONAL_HEADER.ImageBase)
```

★ **`4c 8b d1` 和 `4989ca` 都是 `mov r10, rcx` 的合法编码**（前者 `mov r64, r/m64`，
后者 `mov r/m64, r64`）。ntdll 用前者。**两种都能用**，反汇编出来语义一致。

实测输出（本机 Windows 10 build 19045）：

```
NtAllocateVirtualMemory      rva=0x9d890 off=0x9cc90 SSN=0x018 (  24) bytes=4c 8b d1 b8 18 00 00 00 f6 04 25 08
NtClose                      rva=0x9d770 off=0x9cb70 SSN=0x00f (  15) bytes=4c 8b d1 b8 0f 00 00 00 f6 04 25 08
NtCreateFile                 rva=0x9e030 off=0x9d430 SSN=0x055 (  85) bytes=4c 8b d1 b8 55 00 00 00 f6 04 25 08
NtCreateThreadEx             rva=0x9edc0 off=0x9e1c0 SSN=0x0c2 ( 194) bytes=4c 8b d1 b8 c2 00 00 00 f6 04 25 08
NtDelayExecution             rva=0x9dc10 off=0x9d010 SSN=0x034 (  52) bytes=4c 8b d1 b8 34 00 00 00 f6 04 25 08
NtFreeVirtualMemory          rva=0x9d950 off=0x9cd50 SSN=0x01e (  30) bytes=4c 8b d1 b8 1e 00 00 00 f6 04 25 08
NtOpenProcess                rva=0x9da50 off=0x9ce50 SSN=0x026 (  38) bytes=4c 8b d1 b8 26 00 00 00 f6 04 25 08
NtProtectVirtualMemory       rva=0x9df90 off=0x9d390 SSN=0x050 (  80) bytes=4c 8b d1 b8 50 00 00 00 f6 04 25 08
NtQueryInformationProcess    rva=0x9d8b0 off=0x9ccb0 SSN=0x019 (  25) bytes=4c 8b d1 b8 19 00 00 00 f6 04 25 08
NtQuerySystemInformation     rva=0x9dc50 off=0x9d050 SSN=0x036 (  54) bytes=4c 8b d1 b8 36 00 00 00 f6 04 25 08
NtReadVirtualMemory          rva=0x9dd70 off=0x9d170 SSN=0x03f (  63) bytes=4c 8b d1 b8 3f 00 00 00 f6 04 25 08
NtWriteVirtualMemory         rva=0x9dcd0 off=0x9d0d0 SSN=0x03a (  58) bytes=4c 8b d1 b8 3a 00 00 00 f6 04 25 08
ntdll ImageBase=0x180000000
```

★ **这些数字只对本机 Windows 版本有效**。Win10 1809 / 2004 / 22H2 / Win11 各不相同。
**永远重新跑一遍这个脚本，不要抄表。**

★ **`test byte [0x7FFE0308], 1`（`f6 04 25 08 03 fe ff`）是 KUSER_SHARED_DATA 的
`HeuristicFlag`**（反调试启发式）。这个 flag 存在本身就是反调试的**信号** ——
某些检测会检查它。完整的 stub 生成时可以选择保留或跳过它。

### 3. 用 rasm2 验证 stub 字节

```powershell
$rasm = (Resolve-ReverseToolSpec -Name 'rasm2').Command
& $rasm -a x86 -b 64 -s 0x0 "mov r10, rcx"    # 4989ca  ← 另一种合法编码，见下注
& $rasm -a x86 -b 64 -s 0x0 "mov eax, 0x18"    # b818000000
& $rasm -a x86 -b 64 -s 0x0 "syscall"          # 0f05
& $rasm -a x86 -b 64 -s 0x0 "ret"              # c3
```

实测输出：

```
4989ca
b818000000
0f05
c3
```

★ **必须带 `-s 0x0`**，否则 stdout 为空、exit 0。

★ rasm2 给的是 `4989ca`（`mov r/m64, r64`），ntdll 用的是 `4c 8b d1`（`mov r64, r/m64`）。
**两者语义完全相同**，反汇编都是 `mov r10, rcx`。步骤 4 用 ntdll 原生的 `4c 8b d1` 形态。

### 4. 生成 stub 字节

```python
import struct
from capstone import Cs, CS_ARCH_X86, CS_MODE_64

md = Cs(CS_ARCH_X86, CS_MODE_64)

def gen_stub(ssn):
    """x64 syscall stub: mov r10,rcx; mov eax,ssn; syscall; ret"""
    return (b"\x4c\x8b\xd1"
            + b"\xb8" + struct.pack("<I", ssn)
            + b"\x0f\x05"
            + b"\xc3")

def show(bs, base=0):
    for ins in md.disasm(bs, base):
        print("   %-20s %s" % (ins.mnemonic, ins.op_str))

# 实测：SSN=0x18 (NtAllocateVirtualMemory)
stub = gen_stub(0x18)
print("syscall stub:", stub.hex(" "), "(%d bytes)" % len(stub))
show(stub)
```

实测输出：

```
syscall stub: 4c 8b d1 b8 18 00 00 00 0f 05 c3 (11 bytes)
   mov                    r10, rcx
   mov                    eax, 0x18
   syscall
   ret
```

★ **反汇编回环是必做的自检** —— 字节长度对但语义错（寄存器选错、立即数大小端反了）
不会在长度上暴露。

### 5. 装进可执行内存并调用

```python
import ctypes

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.GetModuleHandleA.restype = ctypes.c_void_p
k32.GetModuleHandleA.argtypes = [ctypes.c_char_p]
k32.GetProcAddress.restype = ctypes.c_void_p
k32.GetProcAddress.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
k32.VirtualAlloc.restype = ctypes.c_void_p
k32.VirtualAlloc.argtypes = [ctypes.c_void_p, ctypes.c_size_t, wt.DWORD, wt.DWORD]

PAGE_EXECUTE_READWRITE = 0x40
MEM_COMMIT, MEM_RESERVE = 0x1000, 0x2000

stub = gen_stub(0x18)
addr = k32.VirtualAlloc(None, len(stub), MEM_COMMIT|MEM_RESERVE, PAGE_EXECUTE_READWRITE)
ctypes.memmove(addr, stub, len(stub))

NtAVM_t = ctypes.CFUNCTYPE(
    ctypes.c_long,          # NTSTATUS
    ctypes.c_void_p,         # ProcessHandle
    ctypes.POINTER(ctypes.c_void_p),  # BaseAddress
    ctypes.c_void_p,         # ZeroBits
    ctypes.POINTER(ctypes.c_size_t), # RegionSize
    ctypes.c_ulong,          # AllocationType
    ctypes.c_ulong)          # Protect
NtAVM = NtAVM_t(addr)

h = k32.GetModuleHandleA(None)  # GetCurrentProcess 的伪句柄
base = ctypes.c_void_p()
size = ctypes.c_size_t(0x1000)
status = NtAVM(h, ctypes.byref(base), None, ctypes.byref(size),
               MEM_COMMIT|MEM_RESERVE, 0x04)  # PAGE_READWRITE
print("NtAllocateVirtualMemory status=0x%08x base=0x%x size=0x%x"
      % (status & 0xffffffff, base.value or 0, size.value))
```

★ `NtAllocateVirtualMemory` 返回的 `BaseAddress` 是**输出参数**（`BaseAddress*`），
不是返回值本身。返回的 `NTSTATUS` 只表示成败。

### 6. 运行时确认 ntdll 是否真被 hook

静态提取（步骤 2）读的是**磁盘文件**，一定干净。要确认**内存里**的 ntdll 没被 hook，
运行时读：

```python
import ctypes

ntdll = ctypes.WinDLL("ntdll.dll")
k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.GetProcAddress.restype = ctypes.c_void_p
k32.GetProcAddress.argtypes = [ctypes.c_void_p, ctypes.c_char_p]

p = k32.GetProcAddress(ntdll._handle, b"NtAllocateVirtualMemory")
raw = ctypes.string_at(p, 8)
print("runtime NtAllocateVirtualMemory stub:", raw.hex(" "))
is_clean = raw[:4] == b"\x4c\x8b\xd1\xb8"
print("hook detected!" if not is_clean else "clean stub (mov r10,rcx; mov eax,...)")
```

判据：头 4 字节是 `4c 8b d1 b8` = 未被 hook。是 `e9`（JMP）/ `cc`（INT3）/ `48 b8`（mov rax,绝对地址）
= 被 hook 了。

★ 若磁盘 ntdll 干净但内存里的被 hook，说明有 inline hook —— 这正是 direct syscall 要解决的问题。
若**磁盘** ntdll 也异常（企业版加固），走下一步。

### 7. Hell's Gate / Halo's Gate

当内存里的 ntdll stub 也被 hook（磁盘干净、运行时被改）时：

- **Hell's Gate**：从磁盘 PE 解析导出表拿**干净的** SSN（步骤 2 就是这个思路）。
- **Halo's Gate**：在内存里**邻近**找未被 hook 的 `NtXxx`，利用
  **SSN 按字母序/分组线性递增**的性质推算目标函数的 SSN。

```python
# Halo's Gate 思路（本机实测：相邻 stub 的 SSN 递增）
# NtAllocateVirtualMemory=24, NtClose=15, NtCreateFile=85, ...
# 运行时扫 ntdll 导出表，找一个已知干净的 Nt 函数，读它的 SSN，
# 再按已知偏移差推算目标函数的 SSN。
# ⚠️ 「已知偏移差」需要一份针对本机版本的映射表 —— 本篇不硬编，
#    用 Sysinternals 的信息或 zzzs 工具生成。
```

★ **不要硬编 SSN 表**。它会随 Windows 更新失效，且各版本不同。

## 判据

1. ★★ **提取出的 SSN 有效**：判据形态是「目标 `NtXxx` 的 stub 前 4 字节 == `4c 8b d1 b8`，
   且 stub 的 `mov eax, imm32`（`b8`）值落在合理范围（通常 0x000–0x1FF）」。
   实测输出 `NtAllocateVirtualMemory ... bytes=4c 8b d1 b8 18 00 00 00 ...` → SSN=0x18。
   **若前 4 字节不是 `4c 8b d1 b8`，这个函数的 stub 形态与预期不符（可能被 hook / 不同版本），
   不要继续用这个值。**
2. ★ **生成的 stub 反汇编回环正确**。判据形态是「反汇编出的助记符列表 =
   `[mov r10, rcx / mov eax, <ssn> / syscall / ret]` 四行」。
   实测输出确认四行齐全。**少一行（比如 `ret`）说明字节偏移错**，调用会返回到垃圾地址。
3. **运行时 `NtAllocateVirtualMemory` 返回 `STATUS_SUCCESS`（0）且 `base != 0`**。
   判据形态：`status=0x00000000 base=0x7ff7... size=0x1000`。
   **非零 status = syscall 号错了或调用约定不对**（见坑 3）。
4. **内存里的 ntdll 未被 hook**（用步骤 6 确认）。判据形态：运行时 stub 头 4 字节 == `4c 8b d1 b8`。
   **若被 hook，说明需要走 Hell's Gate 而不是直接提取。**
5. **与 win32 API 交叉验证**：direct syscall 分配的内存，用
   `VirtualQuery` 查它的 `Protect` 字段，应该是 `PAGE_READWRITE`（0x04）。
   确认是同一个地址空间、同一块内存。

## 坑

1. ★★★ **绝不硬编 SSN 表**。SSN 因 Windows 版本/构建而异 —— 本机 Win10 19045 上
   `NtAllocateVirtualMemory=0x18`，别的版本可能完全不同。**每次都重跑步骤 2 的提取脚本。**
2. ★★★ **磁盘 ntdll 与内存 ntdll 可能不同**。磁盘文件一定干净（步骤 2 读磁盘），
   内存里的可能已被 inline hook。**判断「要不要绕」看内存，不是磁盘**（步骤 6）。
3. ★★ **syscall ABI 的参数传递**。x64 syscall 约定：第 1 参数在 `RCX`，内核入口处
   在 `R10`。所以 stub 第一句是 `mov r10, rcx` —— 让内核从 `r10` 读第 1 参数。
   **改错这条 = 内核收到错误参数**。
4. ★★ **`mov eax, SSN` 的立即数是小端 32 位**。`B8 SS 00 00 00` 里 SS 是低字节。
   **写反了会调完全不同的 syscall**（可能是无害的，可能是危险的）。
5. ★ **`rasm2` 不带 `-s 0x0` 静默返回空**。见 `disasm-jit-asm.md` 坑 1。
6. **`test byte [KUSER_SHARED_DATA+0x308], 1` 这个 HeuristicFlag 检查**：
   某些 stub 有、某些没有。完整 stub 生成时若跳过它，在某些场景下行为不同。
7. **x86（32 位）stub 形态不同**。32 位没有 `mov r10, rcx`（没有 r10），
   stub 形态是 `mov eax, <SSN>` + `mov edx, 0x7FFE0308` + `syscall`。
   **本篇只覆盖 x64。**
8. **Halo's Gate 的「SSN 线性递增」不是普适规律**。它依赖 ntdll 导出表的组织方式，
   不同版本可能不满足。用前先实测相邻 stub 的 SSN。
9. **本机 gcc 可用，MSVC 不可用**。要写 `__declspec(naked)` 的 syscall 封装，
   用 gcc 的 `__attribute__((naked))` + AT&T 语法，或用本篇的纯 Python 字节方案。
10. **direct syscall 会让 Procmon 看不到 API 调用**（它 hook 的是用户态层）。
    这既是目的（绕过检测），也意味着**你的行为监控会失效** —— 调试时要意识到这一点。

## 相关

- `anti-debug-bypass.md` — syscall stub 里的 `KUSER_SHARED_DATA` HeuristicFlag 本身就是反调试信号
- `disasm-jit-asm.md` — stub 字节构造与 rasm2 用法
- `code-patching.md` — 如果不走 syscall，直接 patch 掉 ntdll 的 hook 前导
- `pe-header-parsing.md` — 从磁盘 PE 解析导出表拿干净 SSN（Hell's Gate）
- `procmon-patterns.md` — direct syscall 会让行为监控失效的原因