# 调试器断点策略（cdb / x64dbg）

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/pe-reverse/techniques/03-static-analysis/03-x64dbg-breakpoints.md`（已适配本机工具链）
> **什么时候用**：目标已加载进调试器，需要在关键 API / 关键代码处设断点观察行为、记录参数、自动继续而不打断分析。
>
> **与已有文档的分工**：
> - `anti-debug-bypass.md` —— **绕过**检测（有哪些检测、怎么破、怎么验证）。
> - `../tools-dynamic.md` —— x64dbg / Frida 等工具的通用用法。
> - 本篇 —— **断点怎么设、怎么证明它真的命中了**。断点操作本身的判据。
>
> **工具替换说明**：源文档全篇用 x64dbg 脚本语法。本机 **x64dbg 在位**（含 ScyllaHide 插件），
> MCP 通道 `x64dbg-automate-mcp` 已实测握手。但**可脚本化、能进自动化流程、判据可外部观测的断点操作主力是 cdb**，
> 所以本篇以 cdb 为主线，x64dbg 只讲 MCP / 交互式差异。

## 适用信号

- 目标 PE 已加载，需要在某个 WinAPI 上观察参数与返回值。
- 需要「记录但不中断」（日志断点），避免每次都停。
- 需要硬件断点躲过 INT3 完整性校验或 `NtSetInformationThread(ThreadHideFromDebugger)`。
- 需要条件断点（只在特定参数/返回值时停）。

## 前置

```powershell
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
$cdb = (Resolve-ReverseToolSpec -Name 'cdbX64').Command
# → C:\Users\<user>\AppData\Local\Microsoft\WindowsApps\cdbX64.exe
$x86 = (Resolve-ReverseToolSpec -Name 'cdbX86').Command   # 只调 32 位目标
```

★ **cdb 只能走 alias 路径**，WindowsApps 包目录里的 `cdb.exe` 直跑会「拒绝访问」，
**绝对不能把 WindowsApps 加进 PATH**。

## 步骤

### 1. 断点类型与判据对照

| 类型 | 机制 | 容量 | 判据（外部可观测） |
|---|---|---|---|
| 软件断点 | `INT3`（`0xCC`）改写目标首字节 | 无上限 | 日志出现 `Breakpoint 0 hit`；`ub <addr>` 后原字节恢复 |
| 硬件断点 | CPU 调试寄存器 DR0–DR3 | **只有 4 个** | 日志出现 `Breakpoint 0 hit`；`r dr0 dr7` 可见寄存器 |
| 内存断点 | 目标页设 `PAGE_GUARD` | 无数 | 日志出现 `Breakpoint 0 hit` 或 `break on guard` |
| 条件断点 | 断点 + 表达式，不满足则自动继续 | 无上限 | 日志出现 `Breakpoint was hit ... condition` 或直接继续 |
| 日志断点 | 打印后自动继续（不暂停） | 无上限 | 日志里有输出行、**且没有** `Breakpoint 0 hit` 停在现场 |

★ 最后一行是关键：**日志断点的判据是「有输出但没停」**，不要拿 `Breakpoint 0 hit` 去判它。

### 2. ★★ 断哪个符号：ntdll，不是 kernel32（实测复现）

这是本篇最重要的一条，也是最容易把人卡半小时的坑。

```powershell
$cmds = "$env:TEMP\bp_wrong.txt"
@'
bu kernel32!GetTickCount64
g
.echo ===AFTER===
q
'@ | Set-Content -Path $cmds -Encoding ASCII

& $cdb -logo "$env:TEMP\bp_wrong.log" -cf $cmds .\cdbtest2.exe > $null
Select-String -Path "$env:TEMP\bp_wrong.log" -Pattern "Couldn't resolve|Breakpoint 0 hit|==="
```

实测输出：

```
0:000> bu kernel32!GetTickCount64
Couldn't resolve error at 'kernel32!GetTickCount64'
0:000> g
0:000> .echo ===AFTER===
===AFTER===
```

**`Couldn't resolve error at 'kernel32!GetTickCount64'` = 这个断点根本没绑上。**

★★ **不是 forwarder**。本机 2026-10-10 双重实测：

```powershell
# 证据 1：pefile 读 kernel32.dll 导出表
#   OpenProcess     ord=1045  fwd=-  addr=0x1b120
#   GetTickCount64  ord=789   fwd=-  addr=0x16070
#   OpenProcessToken ord=1046 fwd=api-ms-win-core-processthreads-l1-1-0.OpenProcessToken
# => 裸名就是 kernel32.dll 的真导出，forwarder 字段为 '-'（即 None）

# 证据 2：cdb 里枚举符号
x kernel32!*OpenProcess*
#   00007ffb`6383b120 KERNEL32!OpenProcessStub (OpenProcessStub)   ← 只有这个
#   00007ffb`638a50a8 KERNEL32!_imp_OpenProcess                    ← 导入指针，不是实现
#   （没有裸名 KERNEL32!OpenProcess 这一行）
```

真实原因是**公开 PDB 里只有 `*Stub` 别名**：`OpenProcessStub` 是 kernel32 的导出别名入口，
公开符号流里没有裸名 `OpenProcess`，所以 `bu KERNEL32!OpenProcess` 解析不到。
**判据**：枚举真身用 `x kernel32!*OpenProcess*`，看到的是 `*Stub` 就是这个原因，
换成 `bu KERNEL32!OpenProcessStub` 或 `ntdll!NtOpenProcess` 即可。

**`bl`（断点列表）显示绑定成功也不代表会命中。**

换 `ntdll`：

```powershell
$cmds = "$env:TEMP\bp_right.txt"
@'
bu ntdll!NtQuerySystemInformation
g
.echo ===AFTER_FIRST_HIT===
r rcx
r rdx
q
'@ | Set-Content -Path $cmds -Encoding ASCII

& $cdb -logo "$env:TEMP\bp_right.log" -cf $cmds .\cdbtest2.exe > $null
```

实测输出：

```
0:000> bu ntdll!NtQuerySystemInformation
0:000> g
Breakpoint 0 hit
ntdll!NtQuerySystemInformation:
00007ffb`6554dc50 4c8bd1          mov     r10,rcx
0:000> .echo ===AFTER_FIRST_HIT===
===AFTER_FIRST_HIT===
0:000> r rcx
rcx=0000000000000000
0:000> r rdx
rdx=000000e4c09ffa60
```

`Breakpoint 0 hit` + `ntdll!NtQuerySystemInformation:` + 反汇编行 = 三者齐全才算命中。

★ **`Couldn't resolve` 与 `Breakpoint 0 hit` 是互斥的判据**。源文档给的
`bp kernel32.IsDebuggerPresent` 之类写法在 cdb 上**不能直接用**，必须换到 `ntdll` 层。

### 3. 关键 API 断点集（cdb 形态，全部 `bu ntdll!...`）

| 目的 | cdb 断点 | 备注 |
|---|---|---|
| 反调试 | `bu ntdll!NtQueryInformationProcess` | 首选，见 `anti-debug-bypass.md` |
| 反调试 | `bu ntdll!NtSetInformationThread` | ThreadHideFromDebugger = `0x11` |
| 内存分配（脱壳） | `bu ntdll!NtAllocateVirtualMemory` | 壳解密缓冲区 |
| 内存保护 | `bu ntdll!NtProtectVirtualMemory` | 准备改代码段 → patch 点 |
| 跨进程内存 | `bu ntdll!NtReadVirtualMemory` / `bu ntdll!NtWriteVirtualMemory` | 注入/读取他人内存 |
| 线程创建 | `bu ntdll!NtCreateThreadEx` | 远程注入 |
| 模块加载 | `bu ntdll!LdrLoadDll` | 所有 DLL 加载都过这里 |
| 文件 | `bu ntdll!NtCreateFile` / `bu ntdll!NtWriteFile` | 落盘 |
| 注册表 | `bu ntdll!NtSetValueKey` / `bu ntdll!NtOpenKey` | 持久化，见 `ioc-extraction.md` |

**为什么全用 ntdll**：`NtCreateFile` 一个入口同时覆盖 `CreateFileA/W`、所有 Unicode/ANSI 变体，
且不会被 forwarder 问题绊倒。代价是参数变成了 native 布局（`OBJECT_ATTRIBUTES` 而不是路径字符串），
需要在 `r` 之后手工展开 —— 这一点见「坑 4」。

### 4. 条件断点

cdb 的条件断点有两条路：

```powershell
# 路线 A：命令文件里直接带条件（推荐，可脚本化）
@'
bu ntdll!NtQuerySystemInformation ".if (@rdx == 0x4) {.echo ===MATCH===; r r8}"
g
.echo ===STEP_DONE===
q
'@ | Set-Content -Path $cmds -Encoding ASCII

# 路线 B：设断点后用 bc/bd 开关，或在命中后手工判断
@'
bu ntdll!NtQuerySystemInformation
g
.echo ===HIT===
r rcx rdx r8 r9
q
'@ | Set-Content -Path $cmds -Encoding ASCII
```

★ 命令文件**每行一条、扁平**，结尾必须有 `q`。多层嵌套缩进（像 Python）不会被解析。

### 5. 日志断点（记录但不中断）

cdb 没有 x64dbg 那种「静默断点」对象，用 `.printf` + `gc` 组合：

```powershell
@'
bu ntdll!NtCreateFile
g
.echo ======LOOP-BEGIN=======
.echo ===CreateFile seen, rcx=@
r rcx
.echo ===
gc
.echo ======LOOP-END=======
q
'@ | Set-Content -Path $cmds -Encoding ASCII
```

更实用的做法是**跑到底再从日志筛**：

```powershell
@'
bu ntdll!NtCreateFile ".printf \"CREATEFILE rcx=%p ObjectName=%p\n\", @rcx, poi(@rcx+10); gc"
bu ntdll!NtWriteFile  ".printf \"WRITEFILE  rcx=%p\n\", @rcx; gc"
g
.echo ===CAPTURE_DONE===
q
'@ | Set-Content -Path $cmds -Encoding ASCII

& $cdb -logo "$env:TEMP\trace.log" -cf $cmds .\sample.exe > $null
```

判据形态：日志里**成百上千条 `CREATEFILE`/`WRITEFILE` 行，但没有 `Breakpoint 0 hit` 停住**，
最后有 `===CAPTURE_DONE===`。这就证明自动继续生效了。

### 6. 硬件断点（躲 INT3 完整性校验）

```powershell
@'
bu ntdll!LdrpDoDebuggerBreak
g
.echo ===SET_HWBP===
ba 1 eip 0x00007ff6f44b1440
r dr0 dr7
.echo ===HWBP_SET===
g
.echo ===HWBP_HIT===
q
'@ | Set-Content -Path $cmds -Encoding ASCII
```

★ 只有 4 个硬件断点。`ba 1 eip` 失败（目标页不允许）时 cdb 会报 `Syntax error`；
若 `.echo ===HWBP_SET===` 之后 `g` 直接结束，说明目标根本没执行到那条地址。

★ **不要用硬件断点在 `RDTSC` 检测区间内停** —— 那正是时间差检测要找的。见 `anti-debug-bypass.md` 步骤 5。

### 7. x64dbg 侧（交互 / MCP）

x64dbg 在本机可用，MCP 通道已握手。**只给交互式或 MCP 驱动的场景用**，判据仍以 MCP 返回为准：

| 操作 | x64dbg 命令 | cdp 等价（可脚本化时优先） |
|---|---|---|
| 运行 | `F9` | `g` |
| 运行到用户代码 | `F9` 后 `Ctrl+F9`，或插件 `RunToUserCode` | 无直接等价，走 loader 断点 |
| 步过 / 步入 | `F8` / `F7` | `p` / `t` |
| 执行到返回 | `Ctrl+F9` | `gu` |
| 模块导出断点 | `bp kernel32.GetTickCount64` | `bu ntdll!GetTickCount64` ← **换 ntdll** |
| 硬件断点 | `bph <addr>` | `ba 1 eip <addr>` |

MCP 侧的常用调用（`xd://mcp__x64dbg_automate_mcp_*`）：
`start_session` → `connect_to_session` → `set_breakpoint` → `go` → `get_registers` /
`read_memory` → `get_debugger_status`。

★ x64dbg 的 `kernel32.X` 断点语法在本机**也可能静默不命中**（同一个 `*Stub` 别名问题）。
用 MCP 时优先 `set_breakpoint` 传 `ntdll!NtXxx` 这样的完整符号名，命中与否用
`get_latest_event` 或 `get_debugger_status` 确认，不要凭「没报错」就算成功。

## 判据

1. ★★ **命中判据只有一条：日志里出现 `Breakpoint 0 hit`**，并且紧跟着目标函数名与反汇编行。
   实测形态：
   ```
   Breakpoint 0 hit
   ntdll!NtQuerySystemInformation:
   00007ffb`6554dc50 4c8bd1          mov     r10,rcx
   ```
   **`bl` 显示绑定成功不是判据。`Couldn't resolve error at '...'` 是断点没绑上的确证。**
   `.echo` 打出的标记行是**命令回显**，不是命中证据。
2. **日志断点的判据是「输出很多行 + 没有 `Breakpoint 0 hit` 停在现场」**，
   且末尾出现脚本自己打的结束标记（如 `===CAPTURE_DONE===`）。
3. **目标必须真的调用那个 API**。实测反例：目标启动即退出时，`g` 之后 cdb 停在
   `ntdll!NtTerminateProcess+0x14`，后续 `bu`+`g` 报 `No runnable debuggees error in 'g'`。
   **遇到这个报错不是断点设错，是进程已经结束** —— 先确认目标的生命周期。
4. **命中后寄存器与参数形态自洽**。实测 `r rcx` 得 `rcx=0000000000000000`
   （`NtQuerySystemInformation(SystemInformationClass=0)` 的第一个参数 `SYSTEM_BASIC_INFORMATION`
   确实是 `0`），`r rdx` 得一个栈地址（输出缓冲区）。**参数值与已知语义一致**才算这次命中可用；
   只是「停下来了」但参数看不懂，说明断在错误的层（可能应该断更上层 win32 封装）。
5. **硬件断点装上的判据是 `r dr0 dr7` 能看到非零的 DR0**，而不是 `.echo` 标记本身。

## 坑

★★ **真名带 `Kernel32` 后缀，不是 `Stub`**（2026-10-10 本机 cdb 枚举 + `bu` 绑定双重实测）：
```
  KERNEL32!GetTickCountKernel32        OK  能绑定   ← 真名
  KERNEL32!GetTickCount64Kernel32      OK  能绑定   ← 真名
  KERNELBASE!GetTickCount              OK  能绑定   ← 真实现
  KERNEL32!GetTickCount64Stub          FAIL Couldn't resolve  ← 不是这个
  KERNEL32!GetTickCountStub            FAIL Couldn't resolve  ← 不是这个
  KERNEL32!GetTickCount                FAIL Couldn't resolve
  KERNEL32!OpenProcessStub             OK  ← OpenProcess 系列才是 Stub 后缀
```
**GetTickCount 家族用 `Kernel32` 后缀，OpenProcess 家族用 `Stub` 后缀 —— 两套命名并不统一。**
所以别记规则，要**用 `x <dll>!*<name>*` 枚举真名再 `bu`**。
（此前本包写成「一律用 `*Stub`」是错的，已按实测纠正。）

1. ★★★ **`kernel32!X` 断点不命中**（不是 forwarder，是 PDB 里只有 `*Stub` 别名）。实测
   `bu kernel32!GetTickCount64` → `Couldn't resolve error at 'kernel32!GetTickCount64'`。
   **一律用 `bu ntdll!NtXxx`。** 这是本篇最贵的一条经验。
2. ★★ **`.echo` 标记会出现在日志里，但那只是命令回显**。看到 `===AFTER_LOADER_BREAK===`
   只说明 cdb 执行到了那条命令，**与任何断点是否命中无关**。判据必须另找 `Breakpoint 0 hit`。
3. ★★ **cdb 的 `-logo` 日志在本机是 UTF-8/ASCII，不是 UTF-16LE**。实测 `file cdb.log` →
   `ASCII text, with CRLF line terminators`，可以直接 `Select-String` / `grep`。
   （若你的 cdb 版本输出 UTF-16，用 `[IO.File]::ReadAllText($log,[Text.Encoding]::Unicode)`；
   先 `file` 判一下再选读法。）
4. ★★★ **断 ntdll 会拿到 native 布局参数，而 `OBJECT_ATTRIBUTES` 的路径字段是 `+0x10`**。

   `NtCreateFile` 的文件路径不在 `r8`（那是 `AccessMask`），而在第 2 个参数
   `rcx` 指向的 `OBJECT_ATTRIBUTES` 里的 **`ObjectName`**（`PUNICODE_STRING`），
   字符串再在 `UNICODE_STRING.Buffer`（`+0x08`）。

   偏移由**编译器 `offsetof` 实测**（mingw-w64 / Win10 x64，非人工推算）：

   ```
   OBJECT_ATTRIBUTES   Length=0x00  RootDirectory=0x08  ObjectName=0x10
                       Attributes=0x18  SecurityDescriptor=0x20  SecurityQoS=0x28
                       sizeof=0x30
   UNICODE_STRING      Length=0x00  MaximumLength=0x02  Buffer=0x08  sizeof=0x10
   ```

   ★★ **`+0x30` 是 `sizeof(OBJECT_ATTRIBUTES)`（结构体总长），不是字段偏移**。
   拿 `+0x30` 去读会越过结构尾部。

   ★★★ **更隐蔽的坑：`ObjectName` 在启动期调用里常常是 NULL**。
   cdb 运行时实测（断在 `NtCreateFile`，`dq @rcx L4`）：

   ```
   rcx+0x00 = 00000000`00000008   (Length)
   rcx+0x08 = 00007ffb`62b4fde6   (RootDirectory, 内核地址)
   rcx+0x10 = 00000000`00000000   ★ ObjectName = NULL
   rcx+0x18 = 00000003`00000100   (Attributes = OBJ_CASE_INSENSITIVE)
   ```

   所以裸 `du poi(poi(@rcx+10)+8)` 会报 `Memory access error at ')'` ——
   **这不是偏移写错，是那一次调用的 `ObjectName` 本来就是空的**。
   正确做法是**加条件过滤，只在非 NULL 时展开**：

   ```powershell
   @'
   bu ntdll!NtCreateFile ".if (poi(@rcx+10)) { du poi(poi(@rcx+10)+8) } .else { gc }"
   g
   .echo ===CAPTURE_DONE===
   q
   '@ | Set-Content -Path $cmds -Encoding ASCII
   ```

   ★ 判据：日志里出现 `===CAPTURE_DONE===` **且**有 `du` 展开出的字符串行；
   只有 `CAPTURE_DONE` 说明整场都是 NULL 调用。

   ★ 另一条实测结论：**`.printf` 里不能内嵌 `poi()`**（报 `Memory access error at ')'`），
   `r poi(...)` 也不行（`Bad register error`）。多层解引用用 `du`/`db`/`dq` 这类
   dump 命令，或者把中间指针先取出来再分步 dump。
5. **命令文件每行一条、扁平，结尾必须有 `q`**。缺 `q` 会让 cdb 挂起等输入；
   有缩进的多行结构不会被解析。
6. **`-cf` 脚本里 `#` 不是注释**。cdb 用 `$$` 注释，或干脆别写注释。
7. **cdb 的退出码不可信**（实测 `-2147024866`）。判成功看日志内容，不看 `$LASTEXITCODE`。
8. **`cdbX86` 只能调 32 位目标，`cdbX64` 只能调 64 位**。混用报
   `Win32 error 0n50 / 不支持该请求`。找 32 位样本看 `%SystemRoot%\SysWOW64\*`。
9. **WindowsApps 不能加进 PATH**。`cdb.exe` 直跑会「拒绝访问」。
10. **WindowsApps 不能加进 PATH**。`cdb.exe` 直跑会「拒绝访问」。
11. **`gc`（自动继续）在日志断点里可能漏掉最后几条**。若依赖退出时状态，用
    `bu ... ".printf ...; gc"` 并在脚本末尾单独确认结束标记，别只看进程退出码。

## 相关

- `anti-debug-bypass.md` — 断点为什么会被检测到，以及四层绕过手段
- `../tools-dynamic.md` — x64dbg / Frida 通用用法与 MCP 通道
- `dynamic-api-resolution.md` — 断点应该下在被解析出来的函数上，而不是导入表
- `unpack-and-memory-dump.md` — `NtAllocateVirtualMemory` / `NtProtectVirtualMemory` 断点的实际用法
- `tls-callback-analysis.md` — 断点下在入口点之前（loader 断点）
- `procmon-patterns.md` — 不想被调试时，用行为监控替代断点观察