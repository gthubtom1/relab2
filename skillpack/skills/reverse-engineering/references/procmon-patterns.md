# Procmon 行为监控与过滤

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/pe-reverse/techniques/04-dynamic-analysis/08-procmon-patterns.md`（已适配本机工具链）
> **什么时候用**：需要**非侵入式**观察目标的文件/注册表/网络/进程行为 —— 不改内存、不下断点、目标不需要知道被观察。
> 这是唯一能拿到「目标本来会做什么」而不是「我让它做什么」的手段。
>
> **与已有文档的分工**：
> - `debugger-breakpoints.md` — 侵入式，需要停目标；本篇是旁路观察。
> - `ioc-extraction.md` — 从本篇的 CSV 里提取指标；本篇是**数据采集端**。
> - `external-memory-rw.md` — 主动读内存；本篇是被动等目标自己动。

## 适用信号

- 目标运行时确实有文件/注册表/网络活动，需要完整时间线。
- 目标有反调试，不能附加调试器。
- 需要确定初始化顺序（哪一步先于哪一步）。
- 需要过滤掉系统噪音，只看目标进程。

## 前置

```powershell
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
$pm = 'D:\Tools\Sysinternals\Procmon64.exe'   # GUI + CLI 皆可用
```

★ **Procmon 有完整的 CLI**（源文档只提 GUI）。CLI 适合自动化，但**过滤器只能靠 GUI 配置**
（见「坑 1」）。

## 步骤

### 1. ★★ 先算体积，再决定采集窗口（实测）

**Procmon 默认捕获全系统事件。** 本机实测体积增长：

| 采集窗口 | `.pml` 体积 |
|---|---|
| 8 秒 | **331 MB** |
| 20 秒 | **540 MB** |

导出 CSV 后体积约 `.pml` 的 25%（实测 331 MB pml → 87 MB CSV；540 MB pml → 124 MB CSV）。

**第一个实验用 20 秒抓到了 658044 行 CSV。** 一个普通程序在 20 秒内产生 73 条事件
—— 也就是说**超过 99.99% 的数据是噪音**。

★ **结论：先配过滤再采集**。没过滤就采，磁盘和解析时间都会被噪音吃掉。

### 2. ★ `/RunTime` 的单位是秒（实测踩坑）

```powershell
# 错：我以为 /RunTime 20 是 20 分钟，实际是 20 秒
& $pm /AcceptEula /Quiet /Minimized /RunTime 20 /BackingFile "$dir\cap.pml"
```

我第一次用 `/RunTime 20` 然后等 6 秒才启动目标 —— **采集早就在第 20 秒结束了，
目标一个事件都没抓到**。CSV 里 `target.exe events = 0`。

★ **正确做法：把目标启动安排在采集窗口内**。完整脚本：

```powershell
$ErrorActionPreference = 'Continue'
$pm  = 'D:\Tools\Sysinternals\Procmon64.exe'
$dir = 'C:\relab2\_kbverify\pm'
New-Item -ItemType Directory -Force -Path $dir | Out-Null
Get-ChildItem "$dir\*" | Remove-Item -Force -EA SilentlyContinue

# 20 秒窗口
& $pm /AcceptEula /Quiet /Minimized /RunTime 20 /BackingFile "$dir\cap.pml"
Write-Host "capture running (20s window)"
Start-Sleep -Seconds 3
& 'C:\path\to\target.exe' | Out-Null      # ★ 在窗口内启动目标
Write-Host "target.exe launched and exited"
Start-Sleep -Seconds 20
Get-ChildItem "$dir\cap.pml" | Format-Table Name,@{n='MB';e={[math]::Round($_.Length/1MB,1)}}
```

实测输出：

```
capture running (20s window)
target.exe launched and exited

Name       MB
----
cap.pml  539.7
```

★ `/Terminate` 也可以提前结束，但**先等 `/RunTime` 自然到期更干净**
（`/Terminate` 有时会让最后一次 flush 丢失）。

### 3. 导出 CSV

```powershell
& $pm /AcceptEula /Quiet /OpenLog "$dir\cap.pml" /SaveAs "$dir\cap.csv"
```

实测：540 MB `.pml` → 124 MB CSV，约 3 秒。

★ **CSV 是 UTF-8 with BOM**，开头有 `﻿`（实测 `file` 报 UTF-8 BOM）。
用 Python `csv` 模块读没问题；用 `Select-String` 记得指定 `-Encoding UTF8`。

### 4. ★ 分析：按进程名切片（本机实测脚本）

```python
# pm_analyze.py
import csv, collections, sys

path = sys.argv[1] if len(sys.argv) > 1 else r"C:\path\cap.csv"
target = (sys.argv[2] if len(sys.argv) > 2 else "target").lower()

ops   = collections.Counter()
pairs = collections.Counter()
n = 0

with open(path, newline="", encoding="utf-8", errors="replace") as f:
    for row in csv.DictReader(f):
        n += 1
        pn = (row.get("Process Name") or "").strip()
        if target not in pn.lower():
            continue
        op = (row.get("Operation") or "").strip()
        p  = (row.get("Path") or "").strip()
        ops[op] += 1
        pairs[(op, p[:70])] += 1

print("total rows in csv =", n)
print("target events     =", sum(ops.values()))
print("\n--- operations ---")
for op, c in ops.most_common():
    print("%6d  %s" % (c, op))
print("\n--- unique (op, path) ---")
for (op, p), c in pairs.most_common(25):
    print("%6d  %-22s %s" % (c, op, p))
```

**实测输出**（20 秒全系统捕获，658044 行 CSV，其中目标 73 条）：

```
total rows in csv = 658044
target events     = 73

--- operations ---
    26  RegOpenKey
    17  Process Profiling
    11  RegQueryValue
     8  RegCloseKey
     5  Load Image
     2  Thread Create
     1  Process Start
     1  CreateFile
     1  QueryNameInformationFile
     1  WriteFile

--- unique (op, path) ---
    17  Process Profiling
     4  RegOpenKey             HKLM\System\CurrentControlSet\Control\Session Manager
     3  RegCloseKey            HKLM\System\CurrentControlSet\Control\Session Manager
     2  Thread Create
     2  RegOpenKey             HKLM\SYSTEM\CurrentControlSet\Control\Session Manager
     2  RegQueryValue          HKLM\System\CurrentControlSet\Control\Session Manager\ResourcePolicies
     2  RegOpenKey             HKLM\System\CurrentControlSet\Control\Nls\CustomLocale
     2  RegOpenKey             HKLM\System\CurrentControlSet\Control\Nls\ExtendedLocale
     2  RegOpenKey             HKLM\System\CurrentControlSet\Control\StateSeparation\RedirectionMap\K
     2  RegOpenKey             HKLM\System\CurrentControlSet\Control\Terminal Server
     2  RegOpenKey             HKLM\System\CurrentControlSet\Control\SafeBoot\Option
     2  RegOpenKey             HKLM\System\CurrentControlSet\Control\Srp\GP\DLL
     2  RegOpenKey             HKLM\System\CurrentControlSet\Control\Nls\Sorting\Versions
     1  Process Start
     1  Load Image             C:\relab2\_kbverify\target.exe
     1  Load Image             C:\Windows\System32\ntdll.dll
     1  Load Image             C:\Windows\System32\kernel32.dll
     1  Load Image             C:\Windows\System32\KernelBase.dll
     1  RegQueryValue          HKLM\System\CurrentControlSet\Control\Nls\CustomLocale\zh-CN
     1  RegQueryValue          HKLM\System\CurrentControlSet\Control\Nls\ExtendedLocale\zh-CN
     1  RegQueryValue          HKLM\...\Control\Session Manager\RaiseExceptionOnOverflowCheck
     1  CreateFile             C:\relab2
     1  QueryNameInformationFile
     1  WriteFile
```

★ 这份输出直接告诉你三件事：
1. **目标只加载了 4 个模块**（自己 + ntdll + kernel32 + KernelBase）—— 没有加密/混淆迹象。
2. **注册表访问集中在 `Control\Nls\*`**（locale 探测）和 `Session Manager` —— 这是
   CRT 初始化的标准行为，**不是可疑行为**。不要把这些当 IOC。
3. **唯一一次 `CreateFile` 是 `C:\relab2`（目录查询）** + 一次 `WriteFile` —— 落盘行为。

### 5. 过滤器配置（GUI，⚠️ 无 CLI）

**Procmon 的过滤器栈只能在 GUI 里配**，保存为 `.pmc` 文件后可用 `/LoadConfig` 加载。
CLI 能**加载**过滤器但不能**定义**过滤器。

```powershell
# GUI 里配好 → Filter → Save Filter → capture.pmc
& $pm /AcceptEula /Quiet /Minimized /RunTime 30 /LoadConfig "$dir\target.pmc" /BackingFile "$dir\cap.pml"
```

**四类场景的过滤器配方**（GUI 里按顺序添加）：

**文件落盘追踪**
```
Include: Process Name  is  target.exe
Include: Operation     is  WriteFile
Include: Operation     is  CreateFile
Exclude: Path          contains  C:\Windows
Exclude: Path          contains  .log
Include: Path          contains  C:\Users
```

**注册表持久化追踪**
```
Include: Process Name  is  target.exe
Include: Operation     is  RegSetValue
Include: Operation     is  RegCreateKey
Include: Path          contains  \CurrentVersion\Run
Include: Path          contains  \Services\
Include: Path          contains  \Startup
```

**进程注入追踪**
```
Include: Process Name  is  target.exe
Include: Operation     is  Process Create
Include: Operation     is  Load Image
Include: Detail        contains  target
```

**网络连接追踪**
```
Include: Operation     is  TCP Connect
Include: Operation     is  TCP Send
Include: Operation     is  TCP Receive
Include: Path          contains  <已知 IP>
```

★ **Include 在上、Exclude 在下**。Procmon 是**从上往下第一个匹配就停**（不是「全部满足」），
所以顺序决定语义。

### 6. 时间线分析

```python
# 把目标自己的事件按时间排出来，去掉 CRT 初始化噪音
import csv, sys

NOISE = ("\\Control\\Nls\\", "\\Control\\Session Manager",
         "\\Control\\Terminal Server", "\\Control\\SafeBoot",
         "\\Control\\StateSeparation\\", "\\Control\\Srp\\",
         "Process Profiling", "Load Image")

rows = []
with open(r"C:\path\cap.csv", newline="", encoding="utf-8", errors="replace") as f:
    for r in csv.DictReader(f):
        if "target" not in (r.get("Process Name") or "").lower():
            continue
        op = (r.get("Operation") or "")
        path = (r.get("Path") or "")
        if op in NOISE or any(n in path for n in NOISE):
            continue
        rows.append(r)

rows.sort(key=lambda r: r["Time of Day"])
for r in rows:
    print("%s  %-20s %-55s %s" % (r["Time of Day"], r["Operation"],
                                  r["Path"][:55], r["Result"]))
```

分析要点：
```
12:00:01  CreateFile      C:\data\config.dat          SUCCESS   → 读配置
12:00:03  RegQueryValue   HKLM\Software\App\Version     SUCCESS   → 读注册表配置
12:00:05  TCP Connect     192.168.1.1:443               SUCCESS   → 建连（C2?）
12:00:10  WriteFile       C:\data\output.bin  Offset:0 Len:4096  → 写数据（外泄?）
12:00:15  Process Create  C:\Windows\temp\helper.exe    SUCCESS   → 拉子进程（投放?）
```

★ **只看 `Result = SUCCESS` 的行**。`NAME NOT FOUND` / `ACCESS DENIED` 的失败行通常是探测行为
（枚举/试探），价值低于成功行，但也有分析意义（说明它在找什么）。

### 7. Procmon 看不到什么（重要边界）

- **Direct syscall** 的调用完全不出现 —— Procmon hook 的是用户态 API 层。见 `direct-syscall.md`。
- **纯内存内的操作**（改内存、算哈希）不出现。
- **子进程的行为**归在子进程的 `Process Name` 下，需要按多个名字过滤。
- **其他用户会话 / 提权进程**可能采不到（需要管理员权限 + 正确的过滤器）。

## 判据

1. ★★ **CSV 转换成功且行数合理**。判据形态：`total rows in csv = 658044` +
   `target events = 73`。**`target events = 0` 说明目标没在采集窗口内运行** ——
   实测踩过：`/RunTime 20` 是秒，我等 6 秒才启动目标，采集早结束了。
2. ★★ **操作分布能区分「目标行为」与「CRT 初始化噪音」**。判据形态是操作计数表。
   实测输出 `Load Image 5 / RegOpenKey 26 / Process Profiling 17 / ...`。
   **若 `Load Image` 数量远超模块数、或出现大量未知 DLL 加载 → 有隐藏加载/注入。**
   **若全是 `Control\Nls\*` / `Session Manager` → 那只是 CRT 初始化，不是 IOC。**
3. **`CreateFile` / `WriteFile` 有具体路径**。判据形态是 `(op, path)` 去重表里出现具体文件路径
   （实测 `CreateFile C:\relab2`）。**只有操作名没有路径 = 没抓到真正落盘行为。**
4. **时间线单调且间隔合理**。判据形态是按 `Time of Day` 排序后的事件序列。
   **同一毫秒内大量事件通常是枚举/扫描**，间隔拉长的事件才是有意义的动作。
5. **采集体积在预期内**。实测 20 秒 = 540 MB。**超过 1 GB 说明没配过滤器**，
   先加过滤再采（坑 2）。

## 坑

1. ★★★ **过滤器只能靠 GUI 配置**。CLI 的 `/LoadConfig` 只能加载 `.pmc`，
   不能定义。纯自动化场景只能用「全量采集 + 事后 CSV 过滤」，并接受体积代价。
2. ★★★ **体积爆炸是头号问题**。实测 8 秒 = 331 MB，20 秒 = 540 MB。
   20 秒的 CSV 有 658044 行，而目标只有 73 条 —— **99.99% 是噪音**。
   **必须先配过滤，否则磁盘和解析都被吃掉。**
3. ★★★ **`/RunTime` 的单位是秒**。我按分钟理解，导致采集在目标启动前就结束，
   `target events = 0`。**这是本篇最容易犯的错。**
4. ★ **CSV 是 UTF-8 with BOM**。用 `Select-String` 要 `-Encoding UTF8`；
   Python `csv` + `encoding="utf-8"` 直接可用。
5. ★ **`Path` 列里含逗号时，CSV 字段是被引号包起来的**。用 `awk -F,` 切会切错
   （我实测踩过：`awk -F',' '{print $4}'` 报语法错误）。
   **用 Python 的 `csv.DictReader`，别用 awk 切 CSV。**
6. ★ **Procmon 全系统采集需要管理员权限**。非管理员会漏掉提权进程和其他用户的操作。
7. **`Process Profiling` 是 Procmon 自己的内部事件**，不是目标行为，分析时排除。
8. **CRT 初始化会产生大量 `Control\Nls\*` 和 `Session Manager` 注册表访问**。
   实测目标 73 条事件里大部分是这类。**不要当 IOC。**
9. **`Load Image` 只记录映像加载**。手动映射的 DLL **不会**出现在这里
   （它不走 loader）—— 这既是手动映射的目的，也意味着**Procmon 无法发现手动映射**。
10. **采集完立刻删 `.pml`**。一个 540 MB 的 pml 用完就没用了，CSV 才是要留的。
11. **`/Terminate` 可能丢最后一次 flush**。等 `/RunTime` 自然到期更保险。

## 相关

- `ioc-extraction.md` — 从本篇的 CSV 提取指标并分级
- `persistence-startup-chain.md` — 本篇「注册表持久化」过滤集的展开
- `anti-debug-bypass.md` — 需要行为证据时为什么不改用调试器
- `direct-syscall.md` — direct syscall 让本篇的监控失效的原因
- `external-memory-rw.md` — 主动读内存 vs 本篇被动观察
- `aob-signature-scan.md` — 从 Procmon 观察到的路径/名字反查代码位置