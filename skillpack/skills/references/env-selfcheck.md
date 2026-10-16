# 环境自检：换机 / PATH 漂移 / 「本机缺工具」

**什么时候读这条**（任一命中即读，不要跳过）：

- 你的任务要跑工具，但 `Get-Command <id>` 返回空
- 用户说「这台机器上什么都没装」但你怀疑不是
- 刚换机、刚装完工具、重装了系统、或用户改过 PATH
- 要启动 `idalib-mcp` / `pyghidra-mcp` / `x64dbg-mcp` 之前

**这份手册的存在理由**：2026-10-08 实测事故。当天 agent 第一步跑 `Get-Command` 发现
`diec`/`r2`/`idat`/`ghidraRun` **全部为空**，于是判定「本机缺工具」并直接停手。
实际原因是工具根整体迁移过，注册表 PATH 已更新，
**但 agent 所在进程仍持有启动时的旧快照**（38 条指向已删除目录的死条目）。
绕了很大一圈才定位到。**「查不到就报缺工具」这个结论，在排除本手册第 1 条之前不成立。**

---

## 1. 先排除 PATH 快照陷阱（最高频，必做）

工具迁移目录后，**已运行的进程不会自动刷新环境**。所以：

```powershell
# 进程 PATH（你继承的） vs 注册表 PATH（新进程才拿到）
$proc = $env:PATH -split ';' | Where-Object { $_ }
$user = [Environment]::GetEnvironmentVariable('PATH','User') -split ';' | Where-Object { $_ }
$mach = [Environment]::GetEnvironmentVariable('PATH','Machine') -split ';' | Where-Object { $_ }

# 进程 PATH 里有多少条指向不存在的目录？
($proc | Where-Object { -not (Test-Path $_) }).Count
# > 0 就是中招了

# 看看注册表里写的是什么（这才是新进程的真实值）
$user | Where-Object { $_ -match 'Tools|HACKER' } | Select-Object -First 5
```

**判定**：进程 PATH 有死条目、注册表正常 → **就是快照问题，工具全都在，别报缺工具。**

**免重启修复**（写进当前进程，立即生效）：

```powershell
$env:PATH = [Environment]::GetEnvironmentVariable('PATH','Machine') + ';' +
            [Environment]::GetEnvironmentVariable('PATH','User')
# 然后重跑 Get-Command 验证
(Get-Command diec -ErrorAction SilentlyContinue).Source
```

> 根治：本包的 `scripts/lib/Bootstrap.ps1` 已内置自愈。`Resolve-ReverseToolSpec` 每次调用前
> 自动执行 `Sync-ReverseEnvironment`，它会合并注册表 PATH、丢弃失效目录、补 `DOTNET_ROOT`，
> 且幂等不抛异常。**所以只要走探测层就不受快照影响** —— 这也是下面第 2 条必须走探测层的原因。

---

## 2. 永远走四级探测，不要只看 `Get-Command`

`Get-Command` 只是**第 2 级**。商业工具在子目录、目录名≠工具名（`IDA Pro 9.3\idat.exe`
里才是 IDA），单靠它必然漏。

```powershell
$root = $env:REVERSE_SKILL_ROOT; if (-not $root) { $root = '<仓根>' }   # 换机先跑 relab2-root.ps1
. "$root\skillpack\skills\scripts\lib\Bootstrap.ps1"
$r = Resolve-ReverseToolSpec -Name 'idat'
$r.Available   # 有没有
$r.Command     # 在哪（用完整路径调用，别依赖 cwd）
$r.Via         # env / PATH / map / scan —— scan 最不可信
```

| 级 | 手段 | Via | 可信度 |
|---|---|---|---|
| 1 | 同名大写环境变量 | `env` | 最高 |
| 2 | `Get-Command` 查 PATH | `PATH` | 高 |
| 3 | `D:\Tools\_map.json` 别名 | `map` | 高 |
| 4 | 工具根递归找同名 exe | `scan` | **最低，须实跑版本确认身份** |

**`Available=False` 且四级全失败，才允许报「本机缺该工具」。**

---

## 3. 环境变量错位（比缺工具更阴）

工具装在非默认位置时，`Get-Command` 能找到 exe，但 exe **跑不起来**。这类故障表现为
「静默无输出」或一句莫名的英文报错，容易被误判成工具坏了。

启动前必须探测式设值（**禁止写死盘符**）：

```powershell
# DOTNET_ROOT —— SDK 不在 C:\Program Files\dotnet 时，ilspycmd 等 apphost 会报
#                "You must install .NET to run this application."
$env:DOTNET_ROOT = (Get-Command dotnet).Source.Replace('\dotnet.exe','')

# JAVA_HOME —— 某些构建工具优先读它，不读 PATH
$env:JAVA_HOME = (Get-Command java).Source.Replace('\bin\java.exe','')
```

**排查环境变量是否指向死目录**（今天的真凶之一）：

```powershell
Get-Item 'HKCU:\Environment' | Select-Object -ExpandProperty Property | ForEach-Object {
  $n = $_
  $v = (Get-ItemProperty 'HKCU:\Environment').$n
  if ($v -notmatch '\\') { return }              # 值里没有路径，跳过
  foreach ($seg in ($v -split ';')) {            # PATH 这类是 ';' 分隔的列表
    $p = $seg.Trim()
    if ($p -and -not (Test-Path $p)) { "死路径: $n = $p" }
  }
}
```

**已知的死路径后果**（实测）：

| 变量错位 | 症状 |
|---|---|
| `IDADIR` | `idat.exe` **静默零输出**，看起来像工具坏了 |
| `GHIDRA_INSTALL_DIR` | `pyghidra-mcp` 拉不起来（requires 前置） |
| `JAVA_HOME` | node-gyp / Maven / Gradle 构建失败 |
| `DOTNET_ROOT` | ilspycmd 等 .NET tool 报「You must install .NET」 |

本机应指向：`IDADIR` = IDA 本体目录、`GHIDRA_INSTALL_DIR` = Ghidra 根、
`JAVA_HOME` = JDK 根、`REVERSE_TOOL_ROOT` = 工具根、`REVERSE_SKILL_ROOT` = 本包根。
**全部用 `Get-Command` / `Test-Path` 探测，不写死。**

---

## 4. GUI 版陷阱：探测「成功」≠ 能执行

PATH 里往往同时躺着 GUI 版和 CLI 版，**PATH 级命中早于 `_map.json` 级**，所以探测可能返回 GUI。

| 探测 id | 会返回（若未配 deny） | 实际该用 | CLI 孪生 |
|---|---|---|---|
| `die` | `die.exe`（GUI） | `diec.exe` | ✔ |
| `ida` / `ida64` | `ida.exe`（GUI） | `idat.exe` | ✔ |
| `Wireshark` / `wshark` | `Wireshark.exe`（GUI） | `tshark.exe` | ✔ |
| `x64dbg` / `x32dbg` | `x64dbg.exe`（GUI） | `headless.exe` | ✔ |

**GUI 禁入 bash**：弹窗等输入、零 stdout、进程永不退出 → 命令不返回 → 模型不运行 →
**没有模型能察觉自己卡住**（终端计时器继续走，token 静止）。

- 规范 id 就用 CLI 名：`diec` / `idat` / `tshark` / `x64dbg`(已配 headless)
- 需要 GUI 的人工场景用显式键：`x64dbg-gui` / `x32dbg-gui`
- 机制在 `D:\Tools\_map.json` 的 `deny` 段：GUI 路径被 deny 后才会回落到 CLI 孪生
- 无 CLI 孪生的（PE-bear、Scylla、010 Editor、JEB）：只能人工桌面操作，agent 不得拉起

**动手前先验身份**：`Via=scan` 或首次使用的工具，先实跑一次 `--version` 确认。

---

## 5. 换机后 10 分钟自检清单

```powershell
# 1. 死条目 / 环境变量死路径
($env:PATH -split ';' | Where-Object { -not (Test-Path $_) }).Count
Get-Item 'HKCU:\Environment' | Select-Object -ExpandProperty Property | ForEach-Object {
  $n=$_; $v=(Get-ItemProperty 'HKCU:\Environment').$n
  if ($v -notmatch '\\') { return }
  foreach ($seg in ($v -split ';')) { $p=$seg.Trim(); if ($p -and -not (Test-Path $p)) { "死路径: $n = $p" } } }

# 2. 探测层覆盖率（把你要用的工具都列上）
$root = $env:REVERSE_SKILL_ROOT; if (-not $root) { $root = '<仓根>' }   # 换机先跑 relab2-root.ps1
. "$root\skillpack\skills\scripts\lib\Bootstrap.ps1"
foreach ($t in @('diec','r2','upx','idat','ghidra','x64dbg','capa','python')) {
  $r = Resolve-ReverseToolSpec -Name $t
  "{0,-12} {1,-6} {2,-6} {3}" -f $t,$r.Available,$r.Via,$r.Command
}

# 3. 「能解析」不等于「能跑」——实跑版本
#    ★ `diec -h` / `r2 -v` 是版本/帮助探针，**不在** skills/config/tool-recipes.json 里；
#      本条只作「能跑」验证，实测两形态均安全（2026-10-16：`diec -h` 0.3s 打印 usage、`r2 -v` 0.3s 打印版本行）。
#      真正干活时的参数以配方为准：`diec -d -e -j <file>`、`r2 -q -c 'iI;q' <file>`。
diec -h; r2 -v; upx --version; java -version; dotnet --version

# 4. 有 GUI 混入吗
Resolve-ReverseToolSpec -Name 'die'    # 期望 diec.exe
Resolve-ReverseToolSpec -Name 'ida'    # 期望 idat.exe
Resolve-ReverseToolSpec -Name 'x64dbg' # 期望 headless.exe

# 5. Python 工具链在哪个解释器里（venv 可能抢走 python）
(Get-Command python).Source
python -c "import angr, z3, lief, capstone"   # 应无 ImportError
```

**注意**：venv 目录进了 PATH 会抢走全局 `python`，导致「明明装了 angr 却 import 不到」。
用绝对路径调系统解释器。

---

## 6. 两个约定根（本机已验证，换机必须先确认）

| 根 | 本机已验证值 | 可覆盖的环境变量 |
|---|---|---|
| 仓库根 | `<仓根>` | — |
| 技能包根 | `C:\relab2\skillpack` | `REVERSE_SKILL_ROOT` |
| 工具根 | `D:\Tools` | `REVERSE_TOOL_ROOT` |

**这三行是本机事实，不是通用约定 —— 换机一律先定位、再确认，不要默认成立。**
写死盘符去拼命令，正是「换个盘就全线失效」的来源：

```powershell
$root = & .\relab2-root.ps1 -Quiet        # 拿不到就说明仓库在别处 —— 问主人，不要猜
powershell -NoProfile -ExecutionPolicy Bypass -File "$root\selfcheck.ps1"   # 退出码非 0 就别往下走
```

探测层本身是自推导的：拿不到 `REVERSE_SKILL_ROOT` 时它会从自身位置反推仓库根并给出警告，
`REVERSE_SKILL_ROOT` 指向 skills 根 / 包根 / 仓库根三种写法都认。
**所以「变量没设」不是故障，别把它当缺环境来修。**

`D:\Tools\_map.json` 声明**探测不出来**的关系：目录名≠工具名、同名多份指定哪份、
以及要排除的陷阱（如捆绑的旧 Python）。仓内 `scripts/lib/toolmap.default.json`
是这些关系的通用默认值，本机 `_map.json` 存在时优先。**本包不维护任何工具状态文件**，
工具定位永远是运行时探测，不存在「索引过期」，也不需要刷新步骤。

---

## 结论口径

**允许说「本机缺该工具」的唯一条件**：第 1 条（PATH 快照）已排除、第 2 条四级探测
全部 `Available=False`、第 4 条已确认不是 GUI/CLI 孪生选错。

任一条未排除就报缺工具 = 误判，会让整条任务停在一个其实可以完成的状态上。

回滚：环境变量改动前先备份 `HKCU:\Environment` 全量；`_map.json` 改动前留副本。