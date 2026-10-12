# VMP 虚拟化原理与 VM Entry 定位

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/pe-reverse/05-crypto-unpack/02-vmp-virtualization-analysis.md`（已适配本机工具链）
> **什么时候用**：目标被 VMProtect 虚拟化 —— 反汇编看到的是 handler 循环而不是原始指令，反编译结果是垃圾，但需要先定位 VM entry 才能交给去虚拟化工具链。

## 适用信号

- `diec` 输出 `VMProtect(3.x)` / `VMProtect(2.x)` 签名。
- 节区名 `.vmp0` / `.vmp1`（2.x）或自定义名（3.x）。
- 导入表极简：只剩 `LoadLibraryW`/`GetProcAddress` 等少数。
- 函数入口处是 `push rbx ... mov [rsp+xx], rXX` 的上下文保存序列，而非标准 prologue。
- 被调函数内部是**大循环 + 大量间接跳转**，单步看到 handler 反复跳。
- 程序正常运行，但**任何调试器附加后闪退或卡死**（VMP 自检）。

## 前置

```powershell
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
$diec = (Resolve-ReverseToolSpec -Name 'diec').Command
$r2   = (Resolve-ReverseToolSpec -Name 'r2').Command
$cdb  = (Resolve-ReverseToolSpec -Name 'cdbX64').Command
$inj  = (Resolve-ReverseToolSpec -Name 'scyllahide').Command
$py   = 'D:\EXE\python\python.exe'
```

## VMP 虚拟化执行模型

```
正常执行：  真实代码指令 → CPU 直接执行

VMP 虚拟化：被保护函数 → 编译为自定义字节码（加密）→ VM entry 桩
           → 保存真实寄存器/栈到 VM context（虚拟寄存器数组）
           → 跳入 dispatcher（取指循环）
           → 按 opcode 分发到 handler（mov/push/pop/add/xor/jmp/call/ret…）
           → handler 内部执行被 mutation 混淆的指令序列
           → VM exit 时从 context 恢复寄存器 → 跳回真实代码
```

六个必须理解的概念：

1. **VM entry**：被保护函数的原始入口被替换成「进入 VM」的桩。桩做两件事：把真实寄存器/栈上下文写入 VM context；把 VM key（解密字节码/立即数的密钥）装入寄存器，然后跳 dispatcher。
2. **VM context**：一片内存，充当**虚拟寄存器数组**（VMP 2.x 约 16+ 个虚拟寄存器）。**真实寄存器与虚拟寄存器之间没有固定映射**，每次编译都可能不同 —— 不要硬编码 context 布局。
3. **Dispatcher**：取指循环。2.x 常见 `movzx eax, byte [vm_ip]` + `jmp [handler_table + rax*8]`；3.x 改成加密/运行时计算的间接跳转，静态看不出目标。
4. **Handler 轮换**：同一语义（如 `mov`）有**多个变体 handler**（可达数十个），编译时按上下文随机选。**每次重新加壳 handler 顺序与数量都变 —— 不要试图建立跨样本指纹。**
5. **加密字节码与立即数**：opcode 和立即数被 VM key 做算术变换（XOR/ADD/乘），运行时在 handler 内解出。**静态看到的「立即数」不是真值。**
6. **VM exit**：字节码流中的 exit 指令触发：从 context 恢复真实寄存器，返回真实代码地址。调用点通常表现为 `jmp [rsp+xx]` 或 `ret`。

## 2.x 与 3.x 差异

| 特征 | VMP 2.x | VMP 3.x |
|---|---|---|
| 节区 | `.vmp0` / `.vmp1` | 节区名更隐蔽，需看特征字节 |
| dispatcher | `jmp [reg+offset]` 跳转表，静态可见 | 间接跳转被加密/运行时计算，静态看不出 |
| VM context | 固定布局，研究资料多 | 进出时被 XOR/ADD 变换（解密后才可用） |
| handler | 数量有限，已有公开指纹 | 数量更多、轮换更强、每样本差异更大 |
| 反调试 | SDK 自检可选 | 自检默认更强，含虚拟化工具检测 |
| 去虚拟化难度 | 社区工具可部分处理 | NoVmp 类工具大概率失效，需动态 DSE/trace |

版本判断：`diec` 输出 + `iS` 看节名 + 全文搜 `VMProtect` 字样。

## VM entry 定位四步法

### 第 1 步：上下文保存序列（静态特征）

x86 下 VM entry 桩开头是「把通用寄存器压入 VM context」：

```asm
pushad                       ; 或逐寄存器 push
mov esi, <VM_KEY>            ; VM key → esi
mov edi, <VM_CONTEXT_ADDR>
; 写入 context 槽位
jmp <dispatcher>
```

x64 下没有 `pushad`，表现为 `push rbx; push rsi; push rdi; ... mov [rsp+offset], rXX` 的寄存器搬运序列。

**r2 特征搜索**（通配符用 `.`）：

```powershell
# x64: mov esi, dword [rip+imm32] —— VM key 常见 esi
& $r2 -2 -qc '/x 8b35....; q' .\vmp_sample.exe
# x64: jmp qword ptr [rip+imm32] —— 间接跳转进 dispatcher
& $r2 -2 -qc '/x ff25....; q' .\vmp_sample.exe
```

### 第 2 步：间接跳转表（dispatcher 定位）

在函数调用点 `call sub_XXXX` 进入后，观察前几十条指令。若出现「取字节 → 查表跳转」循环，即为 dispatcher：

```asm
vm_loop:
  movzx eax, byte [rdi]        ; 取 opcode (rdi = vm_ip)
  inc rdi
  jmp qword [r12 + rax*8]      ; r12 = handler_table, 8 字节指针表
```

r2 里直接看：

```powershell
& $r2 -2 -qc 's 0x<被调函数VA>; pd 40; q' .\vmp_sample.exe
```

判据是 **`movzx` 取字节 → 寄存器缩放 → 间接跳转**这个三段式。断在取指处时，`RDI`（或对应寄存器）就是 VM 指令指针；配合内存 dump 能看到字节码流。字节码区通常在 `.vmp0` 或堆上。

### 第 3 步：VM key 追踪

handler 内解立即数的算术混淆以 VM key 为种子。在 VM entry 桩里 key 被装入固定寄存器（2.x 常见 `esi`/`edx`），在 handler 入口观察该寄存器的值即为当前 VM key。**不同 VM 实例（不同被保护函数）key 可能不同。**

### 第 4 步：动态断点组合

```powershell
$exe  = 'C:\path\to\vmp_sample.exe'
$cdb  = "$env:LOCALAPPDATA\Microsoft\WindowsApps\cdbX64.exe"
$cmds = "$env:TEMP\vmp_cdb.txt"

@'
bu ntdll!LdrpDoDebuggerBreak
bu kernel32!VirtualAlloc
bu kernel32!VirtualProtect
bu kernel32!GetProcAddress
g
.echo ===LOADER_BREAK===
g
.echo ===AFTER_FIRST_ALLOC===
r rcx
r rdx
r r8
q
'@ | Set-Content -Path $cmds -Encoding ASCII

& $cdb -cf $cmds $exe
```

`VirtualProtect` 命中时刻 = 解密完成点，是 dump 字节码的时机。

## VMP 自检与反调试绕过

VMP SDK 自检**独立于虚拟化**，运行时检测调试器：

| 检测手段 | 绕过 |
|---|---|
| `VMProtectIsDebuggerPresent()` | ScyllaHide 注入；或 patch 调用点；或 hook 返回 0 |
| `int 2d` / `int 3` 异常链 | ScyllaHide `KiUserExceptionDispatcherHook=1` |
| RDTSC 时间差 | 硬断不停留检测区；或 hook 时间源 |
| `NtQueryInformationProcess(DebugPort=7)` | ScyllaHide `NtQueryInformationProcessHook=1` |
| 虚拟化工具检测（3.x 新增） | 真实物理机；或关检测项 |

本机 ScyllaHide 默认档（`D:\Tools\ScyllaHide\Generic\scylla_hide.ini`）已开 `NtQueryInformationProcessHook` / `NtSetInformationThreadHook` / `PebBeingDebugged` / `PebNtGlobalFlag`，但 **`KiUserExceptionDispatcherHook` / `GetTickCount64Hook` 默认是 0** —— 处理 VMP 3.x 自检时要手动开。

完整绕过手法见 `anti-debug-bypass.md`。

## 快速定位脚本

从 Ghidra/IDA 导出函数列表，用字节模式筛出「上下文保存 + 间接跳转」的候选：

```python
import pefile

data = pefile.PE("vmp_sample.exe").__data__

# 函数头 64 字节里 push rbx/rsi/rdi（53/56/57）≥3 次，且含 ff25（jmp [rip+x]）
# 或 ff24/ff64（jmp [reg]、jmp [reg+reg*8] 等间接跳转）
cands = []
for off in range(0, len(data) - 64):
    head = data[off:off+64]
    pushes = sum(head.count(bytes([b])) for b in (0x53, 0x56, 0x57))
    indirect = (b"\xff\x25" in head or b"\xff\x24" in head
                or b"\xff\x64" in head or b"\xff\x14" in head)
    if pushes >= 3 and indirect:
        cands.append((off, pushes))
        if len(cands) >= 50:
            break

for off, n in cands:
    print(f"[?] file {off:#x}  pushes={n}  {data[off:off+16].hex(' ')}")
```

判据：输出里应能看到一批「pushes=3..8」的候选。**这个筛选必然有大量误报**（普通函数也满足），它的作用是**把 10 万个函数缩小到几十个候选**供人工/Ghidra 确认，不是直接给答案。

## 判据

VM entry 定位成功，四条**外部可观测**的证据缺一不可：

1. **上下文保存序列**：候选函数入口的 64 字节里，`53/56/57`（push rbx/rsi/rdi）出现 ≥3 次，且紧跟 `ff25`/`ff24`/`ff64`（间接跳转）。r2 反汇编能对上。
2. **Dispatcher 三段式**：在候选里能看到 `movzx <reg>, byte [reg2]` → `jmp [table + reg*8]` 的取指-跳转循环。单步 N 次能观察到**重复回到取指点**。
3. **VM key 可追踪**：在 handler 入口，VM key 寄存器（esi/edx）的值在多次命中之间**保持稳定或按可预测规律变化**（不是随机）。
4. **字节码区可读**：VM 指令指针寄存器指向的内存区域（`.vmp0` 或堆）能 dump 出非空的连续字节流，且这些字节不是标准 x86 指令序列（反汇编是乱码）。

**反证（必须排除）**：如果候选函数没有第 2 条的重复回跳，它就只是「带间接跳转的普通函数」，不是 VM entry。

## 坑

1. ★ **不要建立 handler 指纹**。同一语义的 handler 有数十个变体，每次重新加壳顺序和数量都变。跨样本比对 handler 地址是死路。
2. ★ **VM context 布局不固定**。真实寄存器与虚拟寄存器的映射每次编译都不同；3.x 里 context 进出还被 XOR/ADD 变换。**不要硬编码偏移。**
3. ★ **静态看到的立即数是假的**。opcode 和立即数都被 VM key 算术变换过，静态反汇编出的「常量」不是真值。
4. ★ **先过自检再分析**。VMP 3.x 自检默认很强，不处理就附加即闪退，根本走不到 VM entry。顺序是：ScyllaHide 注入 → 确认能跑 → 再定位 VM entry。
5. ★ **rdtsc 检测区内不能用硬件断点**。VMP 3.x 自检含 RDTSC 时间差检测。
6. **`KiUserExceptionDispatcherHook` 和 `GetTickCount64Hook` 在 ScyllaHide 默认档是 0**，处理 VMP 要手动开到 1。
7. **筛选脚本必然大量误报**，它只是缩小候选范围，别当答案。
8. **cdb 断点必须在 `g` 之前下**；**命令串必须 `-cf <文件>`**（内联带引号会被 cmd 转义坏）。
9. **x64dbg headless 会自杀**（command loop 空转即退）。x64dbg 只能 GUI + MCP，agent 不要用 `-d`。
10. **`movzx eax, byte [rdi]` 的寄存器选择随版本变**（可能是 `ecx`/`r8`），不要写死某个寄存器。


## 出口（结论回填）

做完本篇后，结论按性质回填 `assault.md`（`-Preset assault` 生成）：
- 识别出保护形态 / VM 版本 / handler 结构 → `## findings`（A-xxx，类型 `format`）
- 定位到 VM entry / dispatcher 地址 → `## functions`（状态「已分析」+ 证据）
- 还原出的 handler 语义 / 指令映射 → `## findings` + 对应功能行证据
- 拿不准的（如某 handler 变体含义）→ `## unknowns`（写明影响哪个功能）
- 层状态变化（L1 过层 / 部分过层）→ `## layers` 更新 + 证据

判定：**停在壳层打转 = 项目没推进**。过 L1 的意义是拿到货物，拿到就往下走。

## 相关

- `vmp-devirtualization-toolchain.md` — 定位到 VM entry 之后的**还原**流程（本篇的下一步）
- `unpack-and-memory-dump.md` — VMP 外层的 dump（本篇关注的是 dump 之后的虚拟化层）
- `anti-debug-bypass.md` — VMP 自检的完整绕过手法
- `tls-callback-analysis.md` — VMP 也可能把早期检测挂在 TLS 回调
- `aob-signature-scan.md` — handler 变体太多时，靠特征码而非地址定位
- `dynamic-api-resolution.md` — 3.x 的 API 解析链
- `../SKILL.md` — 总体流程