# 反调试检测与绕过

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/pe-reverse/04-dynamic-analysis/05-anti-debug-bypass.md`（已适配本机工具链）
> **什么时候用**：附加调试器后目标闪退 / 静默退出 / 行为异常；想在附加状态下跑通反调试保护的样本。
> **与 `../anti-analysis.md` 的分工**：那篇是**清单**（有哪些反分析手段、按四级火箭怎么排断点、`E-anti-debug-*` 规则索引）；本篇是**手法**（每一类检测的字节级结构、怎么定位、怎么绕过、怎么验证）。清单查「有没有」，本篇查「怎么破」。

## 适用信号

- x64dbg/cdb 附加后目标立刻退出，或什么都不发生。
- 目标无调试器时正常运行，附加后行为异常（网络不上、UI 不弹、一直卡住）。
- 导入表出现 `IsDebuggerPresent`、`CheckRemoteDebuggerPresent`、`NtQueryInformationProcess`、`OutputDebugStringA`。
- 代码里出现 `int 3` / `int 2d` / `rdtsc` / 读 DR0–DR7。
- 附加后 `PEB.BeingDebugged` 变 1（这是**结果**，先看「步骤 3」怎么确认）。

## 前置

```powershell
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
$r2   = (Resolve-ReverseToolSpec -Name 'r2').Command
$cdb  = (Resolve-ReverseToolSpec -Name 'cdbX64').Command
$inj  = (Resolve-ReverseToolSpec -Name 'scyllahide').Command   # InjectorCLIx64.exe
$rdi  = (Resolve-ReverseToolSpec -Name 'r2').Command
```

cdb 只能走 alias：`%LOCALAPPDATA%\Microsoft\WindowsApps\cdbX64.exe`（x86 用 `cdbX86.exe`）。

## 先建立一个基线

**没有基线就无法判断「绕过后到底有没有生效」。** 先在无调试器状态下跑一遍，记录输出：

```powershell
& .\adbg.exe
```

实测（我编译的一个覆盖 5 种检测的测试程序）：

```
IsDebuggerPresent = 0
PEB.BeingDebugged = 0
PEB.NtGlobalFlag  = 0 (raw 0)
ProcessDebugPort != 0 : 0
RDTSC gap > 10ms      : 0
STILL_ALIVE
```

**全部为 0，且最后一行 `STILL_ALIVE` 存在。** 这就是「正常状态」的判据快照。

## 步骤

### 1. 静态定位：确认有哪些检测

```powershell
& $r2 -2 -qc 'ii; q' .\adbg.exe | Select-String 'Debugger|NtQuery|TickCount'
```

并全文搜特征码：

```powershell
# x64 PEB 访问
& $r2 -2 -qc '/x 65488b042560000000; q' .\sample.exe
# 时间源
& $r2 -2 -qc '/x 0f31; q' .\sample.exe       # rdtsc
# 硬件断点读取
& $r2 -2 -qc '/x 0f2300..; q' .\sample.exe    # mov dr0..dr7
```

### 2. 动态确认：cdb 附加后哪些标志变 1

```powershell
$exe  = 'C:\path\to\adbg.exe'
$cdb  = "$env:LOCALAPPDATA\Microsoft\WindowsApps\cdbX64.exe"
$log  = "$env:TEMP\cdb_adbg.txt"
$cmds = "$env:TEMP\adbg_cdb.txt"

@'
vertarget
bu ntdll!LdrpDoDebuggerBreak
g
.echo ===AFTER_LOADER_BREAK===
r @$peb
db @$peb+2 L1
dd @$peb+0xbc L1
q
'@ | Set-Content -Path $cmds -Encoding ASCII

& $cdb -logo $log -cf $cmds $exe *> $null
Get-Content $log | Select-String -NotMatch 'Nuget|Repository|Extension|Path validation|ModLoad|^\s*$'
```

实测输出：

```
0:000> r @$peb
$peb=000000d4dda0b000
0:000> db @$peb+2 L1
000000d4`dda0b002  01                                               .
0:000> dd @$peb+0xbc L1
000000d4`dda0b0bc  00000070
```

★ **这就是「被调试」的可观测判据**：
- `PEB+0x02`（`BeingDebugged`）= `01`
- `PEB+0xBC`（`NtGlobalFlag`，x64）= `0x00000070`

对照基线（无调试器时两者都是 `0`）。`0x70` 正是 `FLG_HEAP_ENABLE_TAIL_CHECK(0x10) | FLG_HEAP_ENABLE_FREE_CHECK(0x20) | FLG_HEAP_VALIDATE_PARAMETERS(0x40)` 三个位之和。

> x86 的 `NtGlobalFlag` 在 `PEB+0x68`，不是 `+0xBC`。`@$peb` 是 cdb 内建伪寄存器，x64/x86 都可用。

### 3. 反调试手法总表

**结构 + 偏移（x64 / x86 对照）**：

| 检测 | 位置 | x64 偏移 | x86 偏移 | 绕过 |
|---|---|---|---|---|
| `PEB.BeingDebugged` | GS/FS 段 | PEB+0x02 | PEB+0x02 | ScyllaHide `PebBeingDebugged=1`；或 patch 成 `xor eax,eax; ret` |
| `PEB.NtGlobalFlag` | GS/FS 段 | PEB+0xBC | PEB+0x68 | ScyllaHide `PebNtGlobalFlag=1` |
| `IsDebuggerPresent` | `kernel32` | — | — | ScyllaHide；或 hook 返回 0 |
| `CheckRemoteDebuggerPresent` | `kernel32` | — | — | ScyllaHide；或 hook 返回 0 |
| `NtQueryInformationProcess` | `ntdll` | — | — | ScyllaHide `NtQueryInformationProcessHook=1` |
| `NtSetInformationThread(ThreadHideFromDebugger=0x11)` | `ntdll` | — | — | ScyllaHide `NtSetInformationThreadHook=1` |
| `RDTSC` 时间差 | — | — | — | 硬断不停留检测区；patch 阈值 |
| 读 `DR0`–`DR7` | — | — | — | 不下硬件断点；或清 DR |

**NtQueryInformationProcess 的 InformationClass**（第 2 个参数 `rdx`）：

| Class | 含义 | 调试时表现 | 绕过 |
|---|---|---|---|
| `7` | `ProcessDebugPort` | 非零 | 返回 0 |
| `30` | `ProcessDebugObjectHandle` | 非零 | 返回 0 |
| `31` | `ProcessDebugFlags` | `0` | 返回 `1` |

### 4. 绕过手段一：ScyllaHide 注入（L1，推荐首选）

**原理**：ScyllaHide 的 `HookLibraryx64.dll` **不是调试器插件**，而是注入到目标进程里、在用户态 hook ntdll/win32u 的关键函数。**因此不依赖调试器本体**，对「查询调试器是否存在」这一类检测最有效。

**实测注入流程**（cdb 附加停在 loader 断点，注入后再继续）：

```powershell
$exe  = 'C:\path\to\adbg.exe'
$cdb  = "$env:LOCALAPPDATA\Microsoft\WindowsApps\cdbX64.exe"
$inj  = 'D:\Tools\ScyllaHide\InjectorCLIx64.exe'
$dll  = 'D:\Tools\ScyllaHide\Generic\HookLibraryx64.dll'
$log  = "$env:TEMP\cdb_sh.txt"
$cmds = "$env:TEMP\c_sh.txt"

@'
bu ntdll!LdrpDoDebuggerBreak
g
'@ | Set-Content -Path $cmds -Encoding ASCII

$cdbProc = Start-Process -FilePath $cdb -ArgumentList @('-logo',$log,'-cf',$cmds,$exe) `
           -WindowStyle Hidden -PassThru

# 等 cdb 停在 loader 断点
$deadline = (Get-Date).AddSeconds(40)
while ((Get-Date) -lt $deadline) {
  Start-Sleep -Milliseconds 500
  if ((Test-Path $log) -and
      ((Get-Content $log -Raw -EA SilentlyContinue) -match 'LdrpDoDebuggerBreak')) { break }
}

# ★ 必须按名字过滤子进程：cdb 的第一个子进程常常是 conhost.exe
$child = Get-CimInstance Win32_Process `
           -Filter "ParentProcessId=$($cdbProc.Id) AND Name='adbg.exe'" | Select-Object -First 1

Write-Host "debuggee pid = $($child.ProcessId)"
& $inj "pid:$($child.ProcessId)" $dll
```

实测输出：

```
debuggee pid = 5080
Loaded VA for NtUserBlockInput = 0x00007FFB630F8470
...
Loaded VA for NtUserGetThreadState = 0x00007FFB630F1030

PID    : 5080 0x13D8
DLL Path: D:\Tools\ScyllaHide\Generic\HookLibraryx64.dll
exit=0
```

判据是 **`exit=0`** 且输出里有 `PID : <pid>` 和 `DLL Path:`。

> ★ 另一个坑：直接跑 `InjectorCLIx64.exe`（不带参数）会先向 stdout 打一堆 `Loaded VA for NtUserXXX`（那是在枚举 win32u 导出），然后才打印 usage。这不是错误 —— usage 才是它的真实参数格式：
> ```
> Usage: InjectorCLIx64.exe <process name> <dll path> [nowait]
> Usage: InjectorCLIx64.exe pid:<process id> <dll path> [nowait]
> ```

**配置文件**：本机有 6 套，路径 `D:\Tools\ScyllaHide\<profile>\scylla_hide.ini`：

```
D:\Tools\ScyllaHide\scylla_hide.ini              （默认，CurrentProfile=VMProtect x86/x64）
D:\Tools\ScyllaHide\Generic\scylla_hide.ini
D:\Tools\ScyllaHide\IDA\scylla_hide.ini
D:\Tools\ScyllaHide\Olly1\scylla_hide.ini
D:\Tools\ScyllaHide\Olly2\scylla_hide.ini
D:\Tools\ScyllaHide\TitanEngine\scylla_hide.ini
```

`Generic` 档实测内容（节选）：

```ini
[SETTINGS]
CurrentProfile=VMProtect x86/x64
[VMProtect x86/x64]
NtCloseHook=1
NtQueryInformationProcessHook=1
NtQueryObjectHook=1
NtSetInformationThreadHook=1
PebBeingDebugged=1
PebHeapFlags=1
PebNtGlobalFlag=1
PebStartupInfo=1
PebOsBuildNumber=1
RemoveDebugPrivileges=0
ServerPort=1337
```

★ **`PebBeingDebugged=1` / `PebNtGlobalFlag=1` 已经是默认开的** —— 处理大多数 PEB 类检测不用改配置。要处理 `RDTSC`/异常链检测才需要勾 `GetTickCount64Hook` / `KiUserExceptionDispatcherHook`（默认 0）。

### 5. 绕过手段二：硬件断点（L3）

**原理**：`ba 1 eip <addr>` 走调试寄存器 DR0–DR3，**不写目标内存、不改 INT3**。因此 `PEB.NtGlobalFlag` 之外的一些完整性校验、`NtSetInformationThread(ThreadHideFromDebugger)`、代码段 CRC 都测不出来。

```powershell
$cmds = "$env:TEMP\hwbp.txt"
@'
bu ntdll!LdrpDoDebuggerBreak
g
ba 1 eip 0x00007ff7f5361520
.echo ===HWBP_SET===
g
r rip
q
'@ | Set-Content -Path $cmds -Encoding ASCII

& $cdb -cf $cmds .\adbg.exe
```

判据：`.echo` 打出 `===HWBP_SET===` 说明硬件断点装上了（软断点会报 `Syntax error`）。**不要用硬件断点在 `RDTSC` 检测区间内停** —— 那正是时间差检测要找的。

### 6. 绕过手段三：直接 patch PEB / 检测代码

```python
import pefile, shutil

# 运行时改（进程内）—— 用 cdb 更直接，见步骤 2
# 静态改 —— patch 掉调用点

# 模式 A：NOP 掉 call [IAT]
# 原始: FF 15 <disp32>   (6 字节, call qword ptr [rip+disp32])
# 改后: 90 90 90 90 90 90
IAT_CALL = bytes.fromhex("ff15")     # 前缀，后接 disp32

# 模式 B：条件跳转恒成立
# 原始: 74 05 (jz +5)  →  EB 05 (jmp +5)
# 原始: 75 10 (jne +0x10) → 90 90 (NOP NOP)
JZ_TO_JMP = {0x74: 0xEB, 0x75: 0x90}   # jz→jmp ; jne→nop(单字节覆盖不了，用 0x90)

shutil.copyfile("sample.exe", "sample_patched.exe")
pe = pefile.PE("sample_patched.exe")
# set_bytes_at_offset / write 的完整实测流程见 code-patching.md
```

更干净的做法是**改判断指令本身**而非 NOP 掉整条 call：

```powershell
& $rasm -a x86 -b 64 'jne 0x7'
& $rasm -a x86 -b 64 'mov eax, 9999'
# 输出:
# 7505
# b80f270000
```

实测 `rasm2 -a x86 -b 32 'jz 0x5'` → `7403`（x86 的短跳偏移按 32 位算，**和 x64 结果不同**，别混用）。

### 7. 绕过手段四：Frida（可选）

本机 `frida` CLI 在 `D:\EXE\python\Scripts\frida.exe`，但脚本注入类方案**优先级低于 ScyllaHide**（ScyllaHide 不依赖调试器本体，隐蔽性更好）。需要时：

```javascript
// hook 常见反调试 API 返回「未被调试」
var isDebug = Module.findExportByName("kernel32.dll", "IsDebuggerPresent");
Interceptor.replace(isDebug, new NativeCallback(function () { return 0; }, 'int', []));

var ntqip = Module.findExportByName("ntdll.dll", "NtQueryInformationProcess");
Interceptor.attach(ntqip, {
    onEnter: function (args) { this.infoClass = args[1].toInt32(); },
    onLeave: function () {
        if (this.infoClass === 7)  args[1] = ptr(0);        // ProcessDebugPort
        if (this.infoClass === 30) args[1] = ptr(0);        // DebugObjectHandle
        if (this.infoClass === 31) args[1] = ptr(1);        // DebugFlags
    }
});

var sit = Module.findExportByName("ntdll.dll", "NtSetInformationThread");
Interceptor.attach(sit, {
    onEnter: function (args) {
        if (args[1].toInt32() === 0x11) args[1] = ptr(0xFFFFFFFF);  // 阻止 ThreadHideFromDebugger
    }
});
```

### 8. 特殊形态：运行时自翻页（自保护 / 反篡改）

**症状**：目标把自身 `.text` / 载荷节在运行时翻成 `PAGE_NOACCESS`（自解密壳、反篡改常见的
`VirtualProtect` 自翻页）。此后调试器**再想读/设/删该页内的断点全部被拒**——cdb 会报
`Unable to remove breakpoint … Win32 error 0n998`。**这个报错不是命中**（详见经验卡
`cdb-noaccess-breakpoint-is-not-hit`）。

**关键认知**：ScyllaHide（hook API）与硬件断点（走 DR 寄存器）**都绕过不了「页保护自翻转」**——
前者改的是 API 返回值，后者不写目标内存，但**翻页本身把代码页变成不可读**，两者都没解决。
这不是反调试检测，是**反篡改**，需要另一套手法：

| 手法 | 做法 | 适用 |
|---|---|---|
| **翻转前 dump** | 在 `VirtualProtect`→NOACCESS 的**调用点**下断，命中的那一刻把该页 dump 出来（此时还是可读的） | 一次性拿到明文载荷 |
| **patch 掉翻转逻辑** | NOP 掉那次 `VirtualProtect(x, size, PAGE_NOACCESS)`，让它**永远不翻页**，之后正常下断点 | 要持续动态跟踪时 |
| **hook VirtualProtect 记录** | Frida/注入 hook `VirtualProtect`/`NtProtectVirtualMemory`，记录每次 `(addr,size,prot)` ——先看清它翻了哪些页、翻成什么 | 摸清翻页地图 |
| **在系统 DLL 下断** | 载荷要调用的系统 API（如 `WinHttp*`）下断，避开被翻页的目标区 | 载荷内部不可读时的替代观测点 |

★ **判据同经验卡**：一切断点结论用**断点命令内原子打印的 `@rip`** + 跑 **≥3 轮**看稳定性；
**单轮命中/未命中都不能定论**（bp 可能恰好被页翻吞掉）。运行时地址一律 **base + RVA 复核**，
差一位会得出完全相反的结论（本机实测：少进一位 → 误判「全局全程 NULL」）。

## 判据

反调试被成功绕过，必须**同时**满足：

1. **PEB 标志回零**（调试态 cdb 里读到）：
   ```
   db @$peb+2 L1     →  00    （BeingDebugged 从 01 变 00）
   dd @$peb+0xbc L1  →  00000000  （NtGlobalFlag 从 00000070 变 0）
   ```
2. **程序行为与无调试器基线一致**：实测基线是 `STILL_ALIVE` + 全部 0；绕过后必须**逐行相同**。`STILL_ALIVE` 消失 = 还在被检测。
3. **注入器退出码 0** 且输出含 `PID : <pid>` / `DLL Path:`。
4. **不依赖调试器本体**：断开调试器连接（ScyllaHide 场景）或改用纯注入器启动目标，目标仍正常运行 —— 这才是 L1 相对 L2 的真正优势。
5. **若用了硬件断点**：`g` 之后断点确实命中（`r rip` 等于目标地址），而不是靠 INT3 命中。

## 坑

1. ★ **必须按名字过滤子进程**。`Get-CimInstance Win32_Process -Filter "ParentProcessId=$pid"` 返回的第一个子进程**常常是 `conhost.exe`**，不是被调试程序。我第一次就注错到了 conhost 上。必须加 `AND Name='adbg.exe'`。
2. ★ **`PEB.NtGlobalFlag` 的偏移 x64 是 `+0xBC`，x86 是 `+0x68`**。写错会读到无关字段，得到看似合理的错值。
3. ★ **`@$tib` 在 cdb 里不可用**（实测 `Bad register error`），但 **`@$peb` 可用**（实测返回 `$peb=000000d4dda0b000`）。写 PEB 相关 cdb 脚本统一用 `@$peb`。
4. ★ **`RDTSC` 检测区内不要用硬件断点**。`ba` 停一次的时间差就是检测目标。要断就断在检测区之外。
5. ★ **`bu <symbol> C "命令"` 形式在 cdb 里会报错**（实测 `Couldn't resolve error at 'kernel32!IsDebuggerPresent C "..."'`）。要带命令就用换行分隔。
6. ★ **cdb 断点必须在 `g` 之前下**。`g` 之后才 `bu` 来不及。
7. ★ **`InjectorCLIx64.exe` 不带参数运行会先打一堆 `Loaded VA for NtUserXXX`**。那是在枚举 win32u 导出做自检，不是错误。真正的 usage 在最后。
8. **ScyllaHide 的 `Generic` 档默认已开 `PebBeingDebugged` / `PebNtGlobalFlag`**。很多教程说要手动勾，其实不用。真正需要动的是 `RDTSC`（`GetTickCount64Hook`）和异常链（`KiUserExceptionDispatcherHook`），这两个默认是 0。
9. **`rasm2` 的短跳偏移按 bits 变**。`-b 64 'jne 0x7'` → `7505`，`-b 32 'jz 0x5'` → `7403`。混用会写错跳转。
10. **`NtQueryInformationProcess` 的 class 30/31 值容易记错**：`31` = `ProcessDebugFlags`，被调试时为 `0`，**要返回 `1`**（不是 0）。返回 0 反而等于「在调试」。
11. **cdb 退出码不可信**（实测 `-2147024866`），判成功看日志有没有 `Breakpoint 0 hit`。
12. **`aslr` 下 `ba 1 eip <静态地址>` 会失效**。要用「基址 + RVA」动态算，或先 `.echo` 确认基址再算。


## 出口（结论回填）

回填位置：滚动报告 `assault.md`（`-Preset assault` 生成）的对应表。

- 检测点清单（API / 时序 / 完整性）与对应绕过手法 → `## findings` + `## layers` L3 行证据
- ScyllaHide 实测三项（peb/crdp/dbgport）结果 → L3 过层证据记录
- 绕不过的检测点 → `## unknowns`（注明影响：哪些动态手段因此不可用）
- 需要特殊配置的段（VMProtect/Themida 专项）→ 记录到该目标 `## layers` 备注

判定：L3 过层判据 = 三项归零 + 程序正常运行超 10s（外部可观测）。

## 相关

- `../anti-analysis.md` — 反分析手段**清单**与四级火箭断点顺序（本篇的清单对）
- `tls-callback-analysis.md` — 反调试常在 TLS 回调里就先触发
- `vmp-virtualization-analysis.md` — VMProtect 自检（`VMProtectIsDebuggerPresent`）是本篇手法的专项应用
- `dynamic-api-resolution.md` — 被动态解析的 `NtQueryInformationProcess` 怎么 hook
- `code-patching.md` — patch 反调试分支的完整流程与验证
- `aob-signature-scan.md` — 把检测点做成特征码跨版本复用
- `../SKILL.md` — 总体流程