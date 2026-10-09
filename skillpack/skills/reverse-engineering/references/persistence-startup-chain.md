# 持久化与启动链 IOC 提取

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/pe-reverse/techniques/06-ioc-extraction/02-persistence-startup-chain.md`（已适配本机工具链）
> **什么时候用**：目标在重启后仍然存在/恢复，或者系统里多出服务、计划任务、启动项。
> 目标是把「启动路径」拆成**可查询的 IOC**：注册表键、服务名、任务名、文件落点、命令行、触发条件。

## 适用信号

- 静态字符串里有 `CurrentVersion\Run` / `RunOnce` / `Services` / `schtasks` / `Startup` / `CurrentVersion` / `Image File Execution Options` / `AppInit_DLLs`。
- 导入表有 `RegSetValueExW` / `CreateServiceW` / `StartServiceW` / `CopyFileW` / `MoveFileExW`。
- Procmon 里有 `RegSetValue` / `CreateService` / `schtasks /Create` / `CreateFile`。
- 行为上：重启后进程自己回来、服务列表多一项、任务计划多一项。

## 前置

```powershell
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
$r2   = (Resolve-ReverseToolSpec -Name 'r2').Command
$floss = (Resolve-ReverseToolSpec -Name 'floss').Command
$cdb  = (Resolve-ReverseToolSpec -Name 'cdbX64').Command
$pm   = 'D:\Tools\Sysinternals\Procmon64.exe'
$sys  = 'D:\Tools\Sysinternals\Autoruns64.exe'    # 一次性扫全部自启动点
```

★ **`Autoruns64.exe` 是本机已有的 Sysinternals 工具**，比手工逐个查注册表全得多。
先扫一遍，再针对性深挖。

## 步骤

### 1. 用 Autoruns 快速摸底（先扫全貌）

```powershell
& 'D:\Tools\Sysinternals\Autoruns64.exe' /accepteula /m <异常项的名字片段> /c /v
```

输出会分组列出：Registry Run Keys / Startup Folder / Scheduled Tasks / Services /
WMI Event Subscriptions / IFEO / AppInit_DLLs / DLL Hijacks。

★ 用途是**定位方向**，不是取证。判据形态：输出的 `Entry` / `File` / `Publisher` 列。
带 `Not verified` / 空 Publisher / 指向临时目录的项优先看。

### 2. 静态打点（字符串 + 导入）

```powershell
& $floss .\sample.exe | Select-String -Pattern `
  'Run\\|RunOnce|Services|schtasks|Startup|WMI|CurrentVersion|Image File Execution|AppInit_DLLs'

& $r2 -2 -qc 'ii' .\sample.exe | Select-String -Pattern `
  'RegCreateKeyExW|RegSetValueExW|CreateServiceW|OpenSCManagerW|StartServiceW|CopyFileW|MoveFileExW|ShellExecuteW'
```

在反汇编器里优先追这几个调用点：
```
RegCreateKeyExW / RegSetValueExW      → 注册表持久化
CreateServiceW / OpenSCManagerW       → 服务持久化
ShellExecuteW("schtasks")             → 计划任务（通过 shell 调命令行）
CopyFileW / MoveFileExW               → 落地到启动目录
IWbemServices::PutInstance            → WMI 事件订阅
```

### 3. Procmon 过滤器（接 `procmon-patterns.md`）

**GUI 配好保存为 `.pmc`**（过滤栈无 CLI，见那篇坑 1），然后：

```powershell
& $pm /AcceptEula /Quiet /Minimized /RunTime 30 /LoadConfig "$dir\persist.pmc" /BackingFile "$dir\persist.pml"
```

过滤器栈（GUI 顺序）：

```
Include: Process Name  is  sample.exe
Include: Operation     is  RegSetValue
Include: Operation     is  RegCreateKey
Include: Operation     is  CreateFile
Include: Operation     is  Process Create
Include: Path          contains  \CurrentVersion\Run
Include: Path          contains  \Services\
Include: Path          contains  \Startup
Include: Path          contains  \Schedule\TaskCache
```

### 4. 从 CSV 提取持久化 IOC

```python
import csv
from pathlib import Path

PERSIST_MARKERS = ["currentversion\\run", "\\services\\",
                   "\\startup", "taskcache", "image file execution options",
                   "appinit_dlls"]

rows = csv.DictReader(Path(r"C:\path\persist.csv").open(
    encoding="utf-8", errors="replace"))

for r in rows:
    path  = (r.get("Path")        or "")
    op    = (r.get("Operation")   or "")
    det   = (r.get("Detail")      or "")
    res   = (r.get("Result")      or "")
    if any(m in path.lower() for m in PERSIST_MARKERS):
        if res != "SUCCESS":
            continue                       # 只取成功写入的
        print("%-16s %-60s %s" % (op, path[:60], det[:80]))
```

★ **只看 `Result = SUCCESS`**。`ACCESS DENIED` / `NAME NOT FOUND` 说明尝试过但没成，
是「意图」证据而不是「落地」证据 —— 两者在报告里要分开列。

### 5. 常见路径表

| 路径 | 成功标志 | 下一跳 |
|---|---|---|
| `HKCU/HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Run` | 值名 + 命令行落盘 | Sigma `registry_set` 规则 |
| `...\CurrentVersion\RunOnce` | 同上（一次性） | 同上，注意区分 Run/RunOnce |
| `CreateServiceW` | 服务名、ImagePath、StartType | 服务 IOC；查 `sc qc <name>` |
| `schtasks /Create` | 任务名、触发器、Action | 导出任务 XML：`schtasks /Query /TN <name> /XML` |
| Startup 文件夹 | `.lnk` 或 exe 落地 | 文件 IOC；解 `.lnk`：`Get-Item $p | Select -Expand Target` |
| WMI EventFilter | Filter / Consumer / Binding 三件套 | WMI IOC；`Get-WMIObject -Namespace root\subscription -Class __FilterToConsumerBinding` |
| IFEO `Debugger` | 目标进程名 + Debugger 值 | 劫持链 —— 任何启动该 exe 的进程都会跑 Debugger |
| `AppInit_DLLs` | DLL 路径 + `LoadAppInit_DLLs=1` | DLL 加载链；影响几乎所有 GUI 进程 |

★ **IFEO 的 `Debugger` 值是最阴的**：不需要写任何文件，改一个注册表值就能让
「任何启动目标 exe 的进程」执行指定程序。Sigma 规则要单独覆盖。

### 6. 用 cdb 断在写入 API 上回溯 caller

```powershell
$cmds = "$env:TEMP\persist.txt"
@'
bu ntdll!NtSetValueKey
g
.echo ===REGWRITE===
kv
r rcx rdx r8
q
'@ | Set-Content -Path $cmds -Encoding ASCII

& $cdb -logo "$env:TEMP\persist.log" -cf $cmds .\sample.exe > $null
```

★ **必须断 `ntdll!NtSetValueKey`，不能断 `advapi32!RegSetValueExW`** ——
后者是 forwarder，断不上（见 `debugger-breakpoints.md` 判据 1）。
`kernel32!CreateServiceW` 同理。

命中后记录：

```
API:         NtSetValueKey
caller VA:   （从 kv 输出里找样本自身的帧）
key:         目标键路径（r8 指向 UNICODE_STRING）
value name:  r9
data:        第 5 个参数（栈上）
return code: rax
```

★ `kv` 里**必须有样本自身的帧**。只有 `ntdll!` 内部帧说明断在 loader 层，没抓到调用者。

### 7. 验证真的持久化了

**重启是最强判据**，但很多目标在测试机重启会丢环境。用等价手段：

```powershell
# 服务
Get-Service -Name <svc> | Select-Object Name, Status, StartType
sc.exe qc <svc>                       # 看 ImagePath 和 StartType

# 计划任务
schtasks /Query /TN <task> /XML /FO LIST
Get-ScheduledTask | Where-Object TaskName -match <pattern>

# 注册表 Run
Get-ItemProperty 'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Run'
Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Run'

# WMI 订阅
Get-CimInstance -Namespace root\subscription -ClassName __FilterToConsumerBinding

# IFEO
Get-ChildItem 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options' |
  ForEach-Object { Get-ItemProperty $_.PSPath } |
  Where-Object Debugger
```

## 判据

1. ★★ **持久化 IOC 有「写入方」证据**。判据形态：Procmon 里 `Result = SUCCESS` 的
   `RegSetValue` / `CreateFile` 行，或 cdb 的 `kv` 输出里出现样本自身的帧。
   **只有「系统里有这个键」不足以说明是这个样本写的** —— 可能是别的软件或系统组件。
2. ★★ **命令行的完整性**。判据形态：Run 值的完整命令行（含引号和参数）、
   服务的 `ImagePath`、任务的 `Action`。**只有路径没有参数不足以复现行为。**
3. ★ **能区分「尝试」与「落地」**。判据形态：`Result` 列。`SUCCESS` = 落地，
   `ACCESS DENIED` / `NAME NOT FOUND` = 尝试。**报告里两类分开列。**
4. **触发条件明确**。判据形态：任务的 trigger XML、服务的 `StartType`、
   WMI 的 Filter/Consumer 绑定。**没有触发条件的持久化条目是不完整的 IOC。**
5. **重启后验证保持**（等价手段）。判据形态：`Get-Service` 显示 `Status: Running`、
   `schtasks /Query /XML` 能查到、或 Run 键值仍在。
   **若只能在 Procmon 里看到写入、重启后消失，说明落地不完整**（路径权限/时机问题）。

## 坑

1. ★★★ **`bp advapi32!RegSetValueExW` 在 cdb 上断不上**（forwarder）。
   实测同类现象：`bu kernel32!GetTickCount64` → `Couldn't resolve error`。
   **一律用 `bu ntdll!NtSetValueKey`**。
2. ★★★ **「系统里有这个启动项」不等于「是这个样本干的」**。
   必须有写入方证据（Procmon 的调用者进程 / cdb 的 caller 栈）。
   **杀软、Office、驱动都会写 Run 键。**
3. ★★ **`Result != SUCCESS` 的行不要当落地证据**。`NAME NOT FOUND` 只是查询探测。
4. ★★ **IFEO `Debugger` 值不需要落地任何文件** —— 这是最容易被漏检的持久化方式。
   检测规则要单独覆盖 IFEO，而不是只覆盖 Run 键。
5. ★ **`Startup` 文件夹的 `.lnk`** 只记录目标路径，不记录参数。
   用 `Get-Item $p | Select -Expand Target` 或 WScript.Shell 解析 `.lnk`。
6. **`schtasks` 的命令行参数有大小写和引号变体**（`/TN` vs `/tn`、`/Create` vs `/create`）。
   静态匹配时用不区分大小写的正则。
7. **WMI 订阅在 `root\subscription` 命名空间**，不在默认命名空间。
   用 `Get-CimInstance -Namespace root\subscription`。
8. **服务 `StartType` 决定持久化强度**。`Automatic` 重启就恢复；
   `Manual` 只在被触发时跑 —— 报告里要区分。
9. **Procmon 采不到已退出进程的写入**。目标若在退出前完成写入，采集必须覆盖整个生命周期。
10. **`FilterToConsumerBinding` 是 WMI 订阅的关联点**。只列 Filter 或只列 Consumer 都不完整。

## 相关

- `ioc-extraction.md` — 通用 IOC 提取与分级（本篇是持久化专项）
- `procmon-patterns.md` — CSV 采集端（本篇过滤器栈的底座）
- `debugger-breakpoints.md` — 断 `NtSetValueKey` 的正确形态
- `dynamic-api-resolution.md` — 持久化调用被动态解析时怎么找
- `yara-rule-writing.md` — 把持久化指标变成规则