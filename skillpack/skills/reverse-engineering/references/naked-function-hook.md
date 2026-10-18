# Naked Function Hook（裸汇编 gateway）

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/pe-reverse/techniques/04-dynamic-analysis/04-naked-function-hook.md`（已适配本机工具链）
> **什么时候用**：需要在 hook 里**完整访问 CPU 状态**（所有通用寄存器 + 标志位），并且希望最小开销、代码自洽可控。
>
> **与 `trampoline-detour.md` 的分工**：那篇是**字节级 trampoline**（Python 拼字节、`WriteProcessMemory` 写、可外部读回验证，
> 适合自动化流程）；本篇是**手写 gateway**（`.asm` / `__declspec(naked)`，性能最低、可移植性最差、调试最难，
> 适合已经确定要做裸汇编的场景）。**先看 trampoline 那篇能解决就别用本篇。**

## 适用信号

- 已确定目标函数地址，需要保留完整寄存器上下文做过滤/记录。
- 热路径上的 hook，Python/callback 的开销不可接受。
- 目标需要精确保存 `EFLAGS`（条件跳转依赖标志位的逻辑）。

## 前置

```powershell
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
$cdb  = (Resolve-ReverseToolSpec -Name 'cdbX64').Command
$r2   = (Resolve-ReverseToolSpec -Name 'r2').Command
$rasm = (Resolve-ReverseToolSpec -Name 'rasm2').Command
```

⚠️ **本机没有 MSVC**（`cl` 不在 PATH，只有 MinGW gcc `D:\Tools\runtime\mingw64\mingw64\bin\gcc.exe`）。
源文档的 MSVC `__declspec(naked)` + MASM `.asm` 路线**在本机不可用**，已改为 MinGW/GCC 形态
（GCC 用 `__attribute__((naked))` + AT&T 内联汇编，或用 `rasm2` 生成裸字节）。

## 步骤

### 1. x86 gateway（32 位，`__declspec(naked)`）

```c
/* x86 — MSVC 形态（需要 MSVC）。本机无 MSVC，此处仅作参考对照。 */
extern DWORD WINAPI MyCallback(DWORD a, DWORD b, DWORD *regs);

__declspec(naked) void NakedHookGateway(void) {
    __asm {
        pushad              /* 0x60 —— 保存 EDI/ESI/EBP/ESP/EBX/EDX/ECX/EAX */
        pushfd              /* 0x9C —— 保存 EFLAGS */

        /* ESP 此刻指向 saved EFLAGS，ESP+4 是 saved EDI ... ESP+28 是 saved EAX */
        /* EAX 就是 hook 点的返回值槽，直接可取 */
        push dword ptr [esp + 28]        /* 把原 eax 当第 1 参 */
        push eax
        call MyCallback

        popfd               /* 0x9D */
        popad               /* 0x61 */

        /* 这里应当放原始被覆盖的字节（安装时填） */
        /* 然后 jmp 回 target + detourLen */
    }
}
```

★ `pushad`/`popad` = `0x60`/`0x61`，**x86 专有**。x64 没有对应指令。

### 2. x64 gateway（本机主力：GCC AT&T 形态）

```c
/* x64 —— GCC/Clang 形态，本机 gcc 15.2.0 实测可编 */
extern void MyCallback(unsigned long long *regs);

__attribute__((naked)) void NakedHookGateway64(void) {
    __asm__ volatile (
        "push %%rax\n\t"
        "push %%rcx\n\t"
        "push %%rdx\n\t"
        "push %%r8\n\t"
        "push %%r9\n\t"
        "push %%r10\n\t"
        "push %%r11\n\t"
        /* x64 shadow space：32 字节。即使回调不用也必须留 */
        "sub $0x28, %%rsp\n\t"
        "mov %%rsp, %%rdi\n\t"   /* rdi = 寄存器快照首地址（见下方布局） */
        "call MyCallback\n\t"
        "add $0x28, %%rsp\n\t"
        "pop %%r11\n\t"
        "pop %%r10\n\t"
        "pop %%r9\n\t"
        "pop %%r8\n\t"
        "pop %%rdx\n\t"
        "pop %%rcx\n\t"
        "pop %%rax\n\t"
        "ret\n\t"
    );
}
```

**寄存器快照布局**（`MyCallback` 收到的 `regs` 指向的栈，从低到高）：

```
regs[0]  = saved RAX
regs[1]  = saved RCX
regs[2]  = saved RDX
regs[3]  = saved R8
regs[4]  = saved R9
regs[5]  = saved R10
regs[6]  = saved R11
```

**注意：x64 没有 `pushfd` 对应物**。`pushfq`/`popfq` 存在但很少需要 ——
绝大多数 x64 gateway 不保存 `RFLAGS`（调用 callback 已经会改标志位，
若目标函数在 hook 后依赖标志位，应保存 `pushfq`/`popfq`）。

```c
/* 需要保留 RFLAGS 时（目标 hook 点之后紧跟条件跳转） */
"pushfq\n\t"
...
"popfq\n\t"
```

### 3. 用 rasm2 生成裸字节（不写 .asm 的替代）

```powershell
& $rasm -a x86 -b 64 -s 0x0 "push rax"
# 50
& $rasm -a x86 -b 64 -s 0x0 "push rcx"
# 51
& $rasm -a x86 -b 64 -s 0x0 "sub rsp, 0x28"
# 4883ec28
& $rasm -a x86 -b 64 -s 0x0 "mov rdi, rsp"
# 4889e7
& $rasm -a x86 -b 64 -s 0x0 "ret"
# c3
```

★ **必须带 `-s 0x0`**，否则静默返回空。

★ `mov rdi, rsp` 是 GCC 语法的反序；rasm2 用 Intel 语法直接写 `mov rdi, rsp` 即可。

### 4. 安装 detour（与 trampoline 同一套原语）

```python
import ctypes, ctypes.wintypes as wt, struct

def detour32(target, gateway):
    """写 5 字节 JMP rel32。detour 边界必须已算好（见 trampoline-detour.md）。"""
    old = wt.DWORD()
    k32.VirtualProtectEx(h, ctypes.c_void_p(target), 5, 0x40, ctypes.byref(old))
    rel = gateway - target - 5
    jmp = b"\xe9" + struct.pack("<i", rel)
    n = ctypes.c_size_t()
    k32.WriteProcessMemory(h, ctypes.c_void_p(target), jmp, 5, ctypes.byref(n))
    d = wt.DWORD()
    k32.VirtualProtectEx(h, ctypes.c_void_p(target), 5, old.value, ctypes.byref(d))
    return old.value
```

★ `gateway` 必须在本进程可执行的内存里（自己进程内 hook）或已映射到目标进程
（外部注入场景）。**外部注入时 gateway 代码要连同 trampoline 一起写进目标内存** ——
见 `manual-map-injection.md`。

### 5. trampoline 回跳（原始字节 + JMP）

```python
def write_trampoline_back(tramp, orig_bytes, jump_back):
    """在 trampoline 里写：原始 N 字节 + JMP rel32 回 target+N。"""
    n = len(orig_bytes)
    # trampoline 尾部 5 字节就是 JMP，其 src = tramp + n
    rel = jump_back - (tramp + n) - 5
    body = orig_bytes + b"\xe9" + struct.pack("<i", rel)
    old = wt.DWORD()
    k32.VirtualProtectEx(h, ctypes.c_void_p(tramp), len(body), 0x40, ctypes.byref(old))
    w = ctypes.c_size_t()
    k32.WriteProcessMemory(h, ctypes.c_void_p(tramp), body, len(body), ctypes.byref(w))
    d = wt.DWORD()
    k32.VirtualProtectEx(h, ctypes.c_void_p(tramp), len(body), old.value, ctypes.byref(d))
    return body
```

★ `rel = jump_back - (tramp + n) - 5`，`jump_back = target + detourLen`。
这里的 `tramp + n` 是这段 JMP 在 trampoline 里的实际地址。

### 6. 用 cdb 验证 gateway

```powershell
$cmds = "$env:TEMP\gw.txt"
@'
bu ntdll!NtQuerySystemInformation
g
.echo ===HIT===
u rip-4 L8
r rsp
q
'@ | Set-Content -Path $cmds -Encoding ASCII
& $cdb -logo "$env:TEMP\gw.log" -cf $cmds .\target.exe > $null
Select-String -Path "$env:TEMP\gw.log" -Pattern "Breakpoint 0 hit|===HIT==="
```

判据看日志：`Breakpoint 0 hit` 后跟 `u rip-4 L8` 的反汇编。

## 判据

1. **gateway 的字节能被反汇编回原意**。判据形态：`rasm2` 输出非空 hex，
   且 capstone 反汇编回环后助记符与预期一致。**没有这一步不要写进内存。**
2. **hook 后栈平衡**。判据形态：hook 命中时 `r rsp` 与未 hook 时的 `r rsp` 相同
   （`call` 返回后栈指针回到原位）。**栈不平衡 = shadow space 或 push/pop 数量不对**，
   会在几层调用后崩溃。
3. **目标进程在 hook 前后都存活，且原功能未被破坏**。判据形态：
   `Get-Process -Id <pid>` 在 hook 前后都能查到，且目标的行为（输出/文件）与预期一致。
   **目标崩溃 = 寄存器没保存对或栈帧算错**，不是「hook 太激进」。
4. **trampoline 回跳正确**。判据形态：hook 命中后 `u rip L4` 能看到原始指令
   （而非跳到随机地址）；**若回跳偏移算错，跳板会执行到无关代码 → 崩溃或死循环**。
5. **卸载后字节完全恢复**。判据形态是 `roundtrip.py` 的三行 hex 对照（见 `trampoline-detour.md` 判据 2）。

## 坑

1. ★★ **x64 没有 `pushad`/`popad`**。MSVC x64 下 `pushad` 非法。
   必须逐个 push/pop volatile 寄存器（`RAX, RCX, RDX, R8-R11`）。
2. ★★ **x64 调用前必须留 0x20 shadow space**（32 字节）。这是 Windows x64 ABI 要求，
   不是可选优化。少留 = 栈损坏。
3. ★★ **`__declspec(naked)` 是 MSVC 扩展**。GCC/Clang 用 `__attribute__((naked))`，
   且 GCC 的 naked 函数里只能用**基本内联汇编**（不能有 C 变量、不能有栈帧）。
   本机 gcc 可用（实测 `gcc 15.2.0`），但**源文档的 MASM `.asm` 路线需 MSVC，本机不可用**。
4. ★ **GCC 用 AT&T 语法（`%rax`、`$0x28`）**，MSVC 用 Intel 语法（`rax`、`0x28`）。
   混抄两边代码必错。
5. **`regs` 指针指向的是快照栈，不是真实寄存器**。callback 里改 `regs[i]` **不会**改回真寄存器 ——
   要改真寄存器得让 gateway 在 `pop` 之前从 `regs` 重新 load。**大多数场景不需要改**。
6. **`call MyCallback` 会 clobber `RSP` 相对位置**。若 callback 抛异常或长跳转，
   gateway 的 `pop` 序列会崩。callback 必须正常返回。
7. **hook 点之后的条件跳转依赖 `RFLAGS`**。若目标函数在 hook 返回后紧跟 `je/jne`，
   而你的 callback 改了标志位，逻辑就错了。此时 gateway 要 `pushfq`/`popfq`。
8. **`detourLen` 必须落在指令边界**。见 `trampoline-detour.md` 步骤 1（实测 `MessageBoxW` 是 7 不是 5）。
9. **本机 gcc 可用但 MSVC 不可用**。源文档的 MSVC 片段在本机只能作参考，不能直接编。

## 相关

- `trampoline-detour.md` — 字节级 trampoline（本篇的「轻量替代」，先看那篇）
- `disasm-jit-asm.md` — rasm2 生成裸字节、capstone 验证反汇编
- `dll-injection-patterns.md` — 把 gateway 放进注入的 DLL
- `code-patching.md` — detour 的字节级 patch 视角
- `../tools-dynamic.md` — 调试器/注入框架通用用法

> **x64dbg 界面**（本机在位，含 ScyllaHide 插件，MCP `x64dbg-automate-mcp` 已握手）
> 提供内置的「汇编 detour」向导，可自动生成并安装含完整 prologue/epilogue 的 hook。
> 交互式快速验证时它比手写 gateway 省事得多；本篇只在你需要**完全控制字节**时才需要。