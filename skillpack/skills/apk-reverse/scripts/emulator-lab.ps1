#Requires -Version 5.1
<#
.SYNOPSIS
  第三方安卓模拟器能力层 —— 发现 / 连接 / 控制 / 抓包 / 动态调试 / 测试，一条龙。

.DESCRIPTION
  本脚本面向「智能体自动控制」设计：**所有输出都是文本**，不需要看任何图形界面。

  覆盖范围是消费级安卓模拟器（MuMu / 雷电 / 夜神 / 蓝叠 / MEmu）以及官方
  AVD。**先不安装任何模拟器**：装完之后本脚本就能自动认出来，无需改代码。

  四条设计铁律（每一条都对应一类真实踩过的坑）：

  1. 端口不是猜的，是**查**的。
     每家模拟器的 adb 端口都不同（MuMu 16384、雷电 5555、夜神 62001……），
     而且多开会变。写死端口的脚本换个模拟器就废。这里同时用三种手段：
       a) 厂商管理 CLI 自报端口（MuMuManager info 给 JSON，最准）
       b) 已开端口扫描（走探测层 Test-ReverseTcpPort）
       c) `adb devices` 里已有的条目
     三者合并去重，谁先答就用谁。

  2. 装没装**不猜**，走探测层（Resolve-ReverseToolSpec）。
     `Get-Command` 返回空 ≠ 没装（PATH 快照陷阱）。

  3. adb 相关操作**必须串行**。
     本机曾有 6 个 adb.exe，daemon 全监听 5037，版本不同就互相踢 ——
     并行跑两个 adb 任务时手机直接掉线、install 卡 1200 秒。

  4. 多设备时**不猜**，多开必须显式 -Serial。
     模拟器多开 + 真机插着 = 5 台在线，猜错一次就是往错的设备上装包。

  抓包分三层，能力不同、成本不同，按需要选（见 pcap / proxy 动作）：
     ① pcap tcpdump   设备侧全量包，模拟器带 tcpdump/busybox 就能用
     ② pcap dumpcap   PC 侧抓虚拟网卡，不改设备，Npcap 已在装
     ③ proxy mitm     改设备全局代理 + CA 证书，解密 HTTP(S)，最常用

  动态调试的坑：frida-server 版本必须与本机 frida 严格一致；
  多设备时 `frida -U` 会挂错设备，必须 `-H 127.0.0.1:<转发端口>`。

.EXAMPLE
  .\emulator-lab.ps1 doctor
  .\emulator-lab.ps1 scan
  .\emulator-lab.ps1 connect -Auto
  .\emulator-lab.ps1 profile 127.0.0.1:16384
  .\emulator-lab.ps1 start -Vendor mumu -Index 0
  .\emulator-lab.ps1 tap 127.0.0.1:16384 540 1200
  .\emulator-lab.ps1 proxy on -Port 8080
  .\emulator-lab.ps1 frida deploy -Server D:\Tools\frida\frida-server-17.9.6-android-arm64
#>
[CmdletBinding()]
param(
  [Parameter(Position = 0)]
  [ValidateSet('doctor', 'scan', 'connect', 'list', 'profile', 'start', 'stop',
               'restart', 'key', 'tap', 'swipe', 'text', 'shot',
               'proxy', 'cert', 'pcap', 'frida', 'iflist', 'selftest')]
  [string] $Action = 'doctor',

  [Parameter(Position = 1)]
  [string] $Target,

  [string] $Serial,
  [string] $Vendor,
  [int]    $Index = -1,
  [string] $Name,
  [int]    $Port = 8080,
  [string] $Apk,
  [string] $Out,
  [string] $Server,
  [string] $ListenPort,
  [string] $KeyCode,
  [int]    $X = -1,
  [int]    $Y = -1,
  [int]    $X2 = -1,
  [int]    $Y2 = -1,
  [int]    $DurationMs = 300,
  [int]    $TimeoutSec = 20,
  [string] $Cert,
  [string] $Interface,
  [string] $Filter,
  [switch] $Auto,
  [switch] $All,
  [switch] $SkipPortScan
)

$ErrorActionPreference = 'Stop'

# ── PSModulePath 自愈：与仓内其它入口脚本同一套写法 ──────────────────
$__psmpDir = $PSScriptRoot
if (-not $__psmpDir) { $__psmpDir = Split-Path -Parent $MyInvocation.MyCommand.Path }
while ($__psmpDir) {
    $__psmpInit = Join-Path $__psmpDir 'skillpack\skills\scripts\lib\PsModulePathInit.ps1'
    if (Test-Path -LiteralPath $__psmpInit -ErrorAction SilentlyContinue) { . $__psmpInit; break }
    $__psmpParent = Split-Path -Parent $__psmpDir
    if (-not $__psmpParent -or $__psmpParent -eq $__psmpDir) { break }
    $__psmpDir = $__psmpParent
}
Remove-Variable -Name __psmpDir, __psmpInit, __psmpParent -ErrorAction SilentlyContinue

# ── 探测层：工具定位的唯一入口 ───────────────────────────────────────
function Import-Probe {
    param([string]$StartDir)
    # 只负责找路径，**不在函数里 dot-source**。
    # PowerShell 函数有自己的作用域，dot-source 出来的函数只活到函数返回
    # —— 调用方拿到 True 却用不了它（apk-debug.ps1 踩过：Import-Probe -> True
    # 但 HasFn=False）。
    $d = $StartDir
    while ($d) {
        foreach ($rel in @('skillpack\skills\scripts\lib\Bootstrap.ps1',
                           '..\..\scripts\lib\Bootstrap.ps1')) {
            $p = Join-Path $d $rel
            if (Test-Path -LiteralPath $p -ErrorAction SilentlyContinue) {
                return (Resolve-Path -LiteralPath $p).Path
            }
        }
        $parent = Split-Path -Parent $d -ErrorAction SilentlyContinue
        if (-not $parent -or $parent -eq $d) { break }
        $d = $parent
    }
    return $null
}

$__probePath = Import-Probe -StartDir $PSScriptRoot
if (-not $__probePath) {
    Write-Error @"
探测层找不到（从 $PSScriptRoot 逐级上溯没找到
skillpack\skills\scripts\lib\Bootstrap.ps1）。

这个脚本必须放在**仓库内**（<仓根>\skillpack\skills\<技能名>\scripts\ 下），
否则它不知道去哪里找工具解析层。
"@
    exit 2
}
. $__probePath

function Say   { param([string]$m) Write-Host $m }
function Step  { param([string]$m) Write-Host "`n=== $m ===" -ForegroundColor Cyan }
function Ok    { param([string]$m) Write-Host "  [OK] $m" -ForegroundColor Green }
function Warn2 { param([string]$m) Write-Host "  [!!] $m" -ForegroundColor Yellow }
function Die   { param([string]$m) Write-Host "  [XX] $m" -ForegroundColor Red; exit 1 }

function Tool {
    param([string]$Name)
    $spec = Resolve-ReverseToolSpec -Name $Name
    if ($spec.Available) { return $spec.Command }
    return $null
}

function Need-Tool {
    param([string]$Name, [string]$Hint = '')
    $c = Tool $Name
    if (-not $c) { Die "缺工具 '$Name'。$Hint" }
    return $c
}

$script:AdbPath = $null
function Need-Adb {
    if ($script:AdbPath) { return $script:AdbPath }
    $script:AdbPath = Tool 'adb'
    if (-not $script:AdbPath) {
        Die @"
缺 adb。装法见 skillpack/skills/TOOLS.md §4.2：
  winget install --id Google.PlatformTools --source winget
"@
    }
    return $script:AdbPath
}
# ── 原生工具调用统一出口 ─────────────────────────────────────────────

function Invoke-VersionProbe {
    param([string] $Exe, [string[]] $ProbeArgs = @())
    # 原生工具的版本串常写在 stderr，而全局 ErrorActionPreference='Stop' 会把正常 stderr
    # 包成 NativeCommandError 并**中断整个脚本**（见经验卡 ps-native-stderr-breaks-strict-mode）。
    # 两个流必须写两个文件：Start-Process 拒绝 RedirectStandardOutput 与
    # RedirectStandardError 指向同一个路径。
    $o = [IO.Path]::GetTempFileName()
    $e = [IO.Path]::GetTempFileName()
    try {
        $sp = @{ }
        if ($ProbeArgs) { $sp['ArgumentList'] = $ProbeArgs }
        $null = Start-Process -FilePath $Exe @sp `
                              -RedirectStandardOutput $o -RedirectStandardError $e `
                              -WindowStyle Hidden -PassThru -Wait -ErrorAction SilentlyContinue
        foreach ($f in @($o, $e)) {
            $t = @(Get-Content -LiteralPath $f -Encoding UTF8 -ErrorAction SilentlyContinue |
                   Where-Object { $_.Trim() })
            if ($t.Count) { return ([string]$t[0]).Trim() }
        }
        return ''
    } catch { return '' }
    finally { Remove-Item -LiteralPath $o, $e -Force -ErrorAction SilentlyContinue }
}

# adb / frida / tshark 都把**正常进度信息**写 stderr。脚本全局是
# ErrorActionPreference='Stop'，于是 PowerShell 把这些 stderr 行包成
# NativeCommandError 并**中断整个脚本** —— 实测 install 直接死在调用点。
# 所以：局部放宽 + 退出码照旧从 $LASTEXITCODE 取（不靠 stderr 判断成败）。
function Invoke-Native {
    param(
        [string] $Exe,
        [string[]] $NativeArgs,
        [int] $WaitSec = 0
    )
    $script:NativeOut = @()
    $script:NativeRc = 0
    $ErrorActionPreference = 'Continue'
    try {
        if ($WaitSec -gt 0) {
            # 长跑命令（logcat / tcpdump / frida REPL）不能同步等死：
            # 走临时文件重定向 + 轮询，超时则杀掉并保留已产出的内容。
            $o = [IO.Path]::GetTempFileName()
            $e = [IO.Path]::GetTempFileName()
            try {
                $p = Start-Process -FilePath $Exe -ArgumentList $NativeArgs `
                                     -RedirectStandardOutput $o -RedirectStandardError $e `
                                     -WindowStyle Hidden -PassThru -ErrorAction SilentlyContinue
                $secs = 0
                while ($p -and -not $p.HasExited -and $secs -lt $WaitSec) {
                    Start-Sleep -Seconds 1
                    $secs++
                }
                if ($p -and -not $p.HasExited) { try { $p.Kill() } catch { } }
                $script:NativeOut = @(Get-Content -LiteralPath $o -Encoding UTF8 -ErrorAction SilentlyContinue)
                $script:NativeRc = 0
                if ($p -and $null -ne $p.ExitCode) { $script:NativeRc = $p.ExitCode }
            } finally {
                Remove-Item -LiteralPath $o, $e -Force -ErrorAction SilentlyContinue
            }
        } else {
            $script:NativeOut = @(& $Exe @NativeArgs 2>&1)
            $script:NativeRc = $LASTEXITCODE
        }
    } finally {
        $ErrorActionPreference = 'Stop'
    }
    return $script:NativeOut
}

function Get-ReverseTcpPort {
    param([int] $Port, [string] $HostName = '127.0.0.1')
    # 必须走探测层的 Test-ReverseTcpPort：verify-repository-security 有
    # tcp-client-health-probe 规则，脚本里自己 new TcpClient 会让安全门禁报错
    #（Bootstrap.ps1 那一条是登记在案的唯一例外）。
    return (Test-ReverseTcpPort -Port $Port -TargetHost $HostName)
}

# ── 模拟器厂商档案（数据来源见 references/emulator-lab.md）──────────────
#
# 端口表来自 MAA1999/M9A 官方文档（MAA 同时支持这些模拟器，维护它的人把
# 各家端口编译进了一张表，是能找到的最权威版本）。控制 CLI 语法来自各家
# 官方帮助页：
#   MuMu  MuMuManager.exe —— mumu.163.com/help/20240726/35047_1170006.html
#   雷电  ldconsole.exe   —— help.ldmnq.com/docs/LD9adbserver
#   夜神  NoxConsole.exe  —— support.bignox.com/en/function/command
#   MEmu  memuc.exe       —— memuplay.com MEMUC 参考手册
#
# 这张表**只用来缩小扫描范围**，不作为判据。真端口以运行时探测为准
# （多开会变、版本会变、用户能自己改）。
$script:VendorProfiles = @(
    [pscustomobject]@{
        Id = 'mumu'; Label = 'MuMu 模拟器 12'; Key = 'mumu'
        # MuMuManager info -v all 直接吐 JSON，字段 adb_host_ip / adb_port /
        # is_android_started 是权威来源，所以 mumu 是**唯一不需要猜端口**的一家。
        Ports = @(16384, 16416, 16448, 16480, 16512, 16544, 16576)
        ExecName = 'MuMuManager.exe'
        ExecGlobs = @('*\Netease\MuMuPlayer*\shell\MuMuManager.exe',
                      '*\MuMuPlayer*\shell\MuMuManager.exe',
                      '*\MuMuPlayerGlobal-12.0*\nx_device\MuMuManager.exe')
        Cli = 'mumu'
        Fdaemon = @('MuMuVMHeadless.exe', 'MuMuPlayer.exe', 'Muvm6Headless.exe')
    }
    [pscustomobject]@{
        Id = 'ldplayer'; Label = '雷电模拟器'; Key = 'ld'
        Ports = @(5555, 5557, 5559, 5561)
        ExecName = 'ldconsole.exe'
        ExecGlobs = @('*\ldplayer9box\ldconsole.exe', '*\LDPlayer\ldconsole.exe',
                      '*\leidian\LDPlayer9\ldconsole.exe')
        Cli = 'ldconsole'
        Fdaemon = @('Ld9BoxHeadless.exe', 'Ld2BoxHeadless.exe', 'dnplayer.exe')
    }
    [pscustomobject]@{
        Id = 'nox'; Label = '夜神模拟器'; Key = 'nox'
        Ports = @(62001, 62025, 62065)
        ExecName = 'NoxConsole.exe'
        ExecGlobs = @('*\Nox\bin\NoxConsole.exe', '*\Nox\NoxConsole.exe',
                      '*\NoxVMBox\Nox\bin\NoxConsole.exe')
        Cli = 'noxconsole'
        Fdaemon = @('NoxVMHandle.exe', 'Nox.exe', 'NoxVMHeadless.exe')
    }
    [pscustomobject]@{
        Id = 'memu'; Label = 'MEmu 模拟器'; Key = 'memu'
        Ports = @(21503, 21505)
        ExecName = 'memuc.exe'
        ExecGlobs = @('*\Microvirt\MEmu\memuc.exe', '*\MEmu\memuc.exe',
                      '*\Microvirt\MEmuHyperv\memuc.exe')
        Cli = 'memuc'
        Fdaemon = @('MEmuHeadless.exe', 'MEmu.exe', 'MEmuPlayer.exe')
    }
    [pscustomobject]@{
        Id = 'bluestacks'; Label = '蓝叠'; Key = 'bstk'
        # 蓝叠没有官方的实例启停 CLI，只有 adb 端口 + HD-Player.exe
        # --instance <name>。这里不猜实例名：没有 CLI 就报「需手动起」。
        Ports = @(5556, 5565, 5575, 5585, 5595, 5554)
        ExecName = 'HD-Player.exe'
        ExecGlobs = @('*\BlueStacks_nxt\HD-Player.exe', '*\BlueStacks\HD-Player.exe')
        Cli = 'hdplayer'
        Fdaemon = @('HD-Player.exe', 'BlueStacksSvc.exe', 'bsts_vmservice.exe')
    }
    [pscustomobject]@{
        Id = 'avd'; Label = '官方 AVD'; Key = 'avd'
        # AVD 用 emulator-<console 端口减一> 这个 adb 别名：emulator-5554 即 5554。
        Ports = @()
        ExecName = 'emulator.exe'
        ExecGlobs = @('*\android-sdk\emulator\emulator.exe')
        Cli = 'emulator'
        Fdaemon = @('qemu-system-x86_64.exe', 'qemu-system-x86_64-headless.exe',
                     'emulator.exe')
    }
)

function Get-VendorProfile {
    param([string]$Id)
    if (-not $Id) { return $null }
    $key = $Id.Trim().ToLowerInvariant()
    # 口语与缩写别名：用户嘴里的「雷电」「夜神」「蓝叠」「bs」都要落到同一份档案上。
    # 2026-10-11 实测漏了 bs -> bluestacks，被 test-emulator-lab.ps1 的用例抓出来。
    $alias = switch -Regex ($key) {
        '^(bstk|bs|bluestacks|blue|蓝叠)$' { 'bluestacks'; break }
        '^(mumu|mumu12)$'                     { 'mumu'; break }
        '^(nox|夜神|bignox)$'                 { 'nox'; break }
        '^(ldplayer|ld|雷电|ld9)$'            { 'ldplayer'; break }
        '^(avd|官方模拟器)$'                  { 'avd'; break }
        '^(memu|memuplayer)$'                 { 'memu'; break }
        default                               { $key }
    }
    return ($script:VendorProfiles | Where-Object {
        $_.Id -eq $alias -or $_.Key -eq $alias -or $_.Label -like "*$alias*" -or
        $_.Id.StartsWith($alias)
    } | Select-Object -First 1)
}

# ── 进程发现（不扫盘，比扫盘快两个数量级）──────────────────────────
function Get-RunningEmulators {
    $found = @()
    $procs = @(Get-CimInstance -ClassName Win32_Process -ErrorAction SilentlyContinue)
    foreach ($p in $procs) {
        $name = [string]$p.Name
        if ($name -notmatch '\.exe$') { continue }
        foreach ($vp in $script:VendorProfiles) {
            $hit = $false
            foreach ($f in $vp.Fdaemon) {
                if ($name -ieq $f) { $hit = $true; break }
            }
            if (-not $hit) { continue }
            $cmd = [string]$p.CommandLine
            $inst = ''
            if ($cmd -match '--(?:instance|comment)\s+("?)([^\s"]+)\1') { $inst = $Matches[2] }
            $found += [pscustomobject]@{
                Vendor   = $vp.Id
                Label    = $vp.Label
                ProcName = $name
                Pid      = $p.ProcessId
                Instance = $inst
                Cl       = $cmd
            }
            break
        }
    }
    return $found
}

# ── 厂商管理 CLI 定位 ───────────────────────────────────────────────
function Find-VendorCli {
    param([string]$VendorId)
    $vp = Get-VendorProfile -Id $VendorId
    if (-not $vp) { return @() }
    $hits = @()
    $running = @(Get-RunningEmulators | Where-Object { $_.Vendor -eq $vp.Id })
    foreach ($r in $running) {
        $p = Get-Process -Id $r.Pid -ErrorAction SilentlyContinue
        if (-not ($p -and $p.Path)) { continue }
        $dir = Split-Path -Parent $p.Path
        # 1) 同目录就是当前运行版本
        $cand = Join-Path $dir $vp.ExecName
        if (Test-Path -LiteralPath $cand) { $hits += $cand }
        # 2) 逐级上溯做模式匹配（用户装在 D:\Program Files 等处）
        for ($i = 0; $i -lt 5 -and $dir; $i++) {
            foreach ($g in $vp.ExecGlobs) {
                $m = Join-Path $dir (Split-Path -Leaf $g)
                if (Test-Path -LiteralPath $m) { $hits += $m }
            }
            $dir = Split-Path -Parent $dir
        }
    }
    # 3) 探测层登记（用户把它放进工具根 / 进了 PATH）
    foreach ($id in @($vp.Id, ($vp.ExecName -replace '\.exe$', ''))) {
        $spec = Resolve-ReverseToolSpec -Name $id -ErrorAction SilentlyContinue
        if ($spec -and $spec.Available -and $spec.Command) { $hits += $spec.Command }
    }
    return @($hits | Select-Object -Unique)
}

# ── 厂商 CLI 调用 ───────────────────────────────────────────────────
function Invoke-VendorCli {
    param([string]$CliPath, [string[]]$CliArgs)
    $null = Invoke-Native -Exe $CliPath -NativeArgs $CliArgs -WaitSec $TimeoutSec
    return [pscustomobject]@{
        Out = ($script:NativeOut -join [Environment]::NewLine)
        Rc  = $script:NativeRc
    }
}

# MuMuManager.exe info -v all 输出 JSON 数组（官方文档给了完整字段表），
# 这是唯一一家能**自报端口与启动状态**的模拟器 —— 优先用它，别去扫端口。
function Get-MumuInstances {
    param([string]$CliPath)
    if (-not $CliPath) { return @() }
    $r = Invoke-VendorCli -CliPath $CliPath -CliArgs @('info', '-v', 'all')
    $txt = $r.Out
    if (-not $txt) { return @() }
    # 老版本会先打一行标题，所以按第一个 '[' 切出 JSON 再解析，
    # 不依赖「整段恰好是合法 JSON」。
    $start = $txt.IndexOf('[')
    if ($start -lt 0) { return @() }
    $depth = 0
    $end = -1
    for ($i = $start; $i -lt $txt.Length; $i++) {
        $c = $txt[$i]
        if ($c -eq '[') { $depth++ }
        elseif ($c -eq ']') {
            $depth--
            if ($depth -eq 0) { $end = $i; break }
        }
    }
    if ($end -lt 0) { return @() }
    try {
        $parsed = $txt.Substring($start, $end - $start + 1) | ConvertFrom-Json
        # ★ PS 5.1 的 ConvertFrom-Json 对**顶层数组**返回一个「数组对象」，
        #   直接 @() 包住只会得到 1 个元素 —— 那个数组本身。
        #   实测后果：2 个 MuMu 实例被算成 1 个，端点列表渲染成
        #   'System.Object[]:System.Object[]'（PS 7 才改成自动展开）。
        #   显式 ForEach-Object 让管道枚举它，PS 5.1 / 7 行为一致。
        return @($parsed | ForEach-Object { $_ })
    } catch {
        return @()
    }
}

# ── adb 通道 ────────────────────────────────────────────────────────
function Adb {
    param(
        [string] $Dev,
        [string[]] $NativeArgs,
        [int] $WaitSec = 0
    )
    $adb = Need-Adb
    if (-not $Dev) { $Dev = Resolve-OneDevice }
    $null = Invoke-Native -Exe $adb -NativeArgs (@('-s', $Dev) + $NativeArgs) -WaitSec $WaitSec
    return $script:NativeOut
}

function Get-AdbDevices {
    $adb = Need-Adb
    $null = Invoke-Native -Exe $adb -NativeArgs @('devices')
    $rows = @()
    foreach ($line in $script:NativeOut) {
        $text = [string]$line
        # `adb devices` 的表头是 List of devices attached，正文才是
        # <serial>\t<state>。按「第一段是序列号、第二段是状态」取。
        if ($text -match '^(\S+)\s+(\S+)\s*$') {
            $rows += [pscustomobject]@{ Serial = $Matches[1]; State = $Matches[2] }
        }
    }
    return $rows
}

function Resolve-OneDevice {
    $devs = @(Get-AdbDevices | Where-Object { $_.State -eq 'device' })
    if ($devs.Count -eq 0) {
        Die @"
adb devices 里没有在线设备。先跑 '.\emulator-lab.ps1 connect -Auto'，
或检查真机的 USB 调试（开发者选项 → USB 调试、手机上点「一直允许」）。
"@
    }
    if ($devs.Count -gt 1) {
        $list = (@($devs | ForEach-Object { $_.Serial })) -join ', '
        Die @"
检测到 $($devs.Count) 台设备：$list
本脚本**不猜**。加 -Serial 指定：
  .\emulator-lab.ps1 $Action -Serial <序列号> ...
"@
    }
    return $devs[0].Serial
}

# ── 发现：厂商 CLI + 端口扫描 + adb devices 三路合并 ─────────────────
function Get-EmulatorInventory {
    param([switch]$NoScan)
    $candidates = New-Object System.Collections.Generic.List[object]
    $running = @(Get-RunningEmulators)

    foreach ($vp in $script:VendorProfiles) {
        $clis = @(Find-VendorCli -VendorId $vp.Id)
        if ($clis.Count -eq 0) { continue }
        $cli = $clis[0]
        if ($vp.Id -eq 'mumu') {
            foreach ($inst in (Get-MumuInstances -CliPath $cli)) {
                $ser = $null
                if ($inst.adb_host_ip -and $inst.adb_port) {
                    $ser = '{0}:{1}' -f $inst.adb_host_ip, $inst.adb_port
                }
                $candidates.Add([pscustomobject]@{
                    Vendor  = $vp.Id
                    Label   = $vp.Label
                    Serial  = $ser
                    Source  = 'mumu-json'
                    Index   = [string]$inst.index
                    Running = [bool]$inst.is_process_started
                    Booted  = [bool]$inst.is_android_started
                    Cli     = $cli
                    Pid     = $inst.pid
                })
            }
            continue
        }
        $mine = @($running | Where-Object { $_.Vendor -eq $vp.Id })
        if ($mine.Count -eq 0) { continue }
        foreach ($m in $mine) {
            $candidates.Add([pscustomobject]@{
                Vendor  = $vp.Id
                Label   = $vp.Label
                Serial  = $null
                Source  = 'vendor-cli'
                Index   = $m.Instance
                Running = $true
                Booted  = $false
                Cli     = $cli
                Pid     = $m.Pid
            })
        }
    }

    # 端口扫描：覆盖 CLI 认不出的实例（雷电/夜神/MEmu 的多开）
    if (-not $NoScan) {
        foreach ($vp in $script:VendorProfiles) {
            if ($vp.Ports.Count -eq 0) { continue }
            foreach ($p in $vp.Ports) {
                if (-not (Get-ReverseTcpPort -Port $p)) { continue }
                $candidates.Add([pscustomobject]@{
                    Vendor  = $vp.Id
                    Label   = $vp.Label
                    Serial  = ('127.0.0.1:{0}' -f $p)
                    Source  = 'port-scan'
                    Index   = ''
                    Running = $true
                    Booted  = $false
                    Cli     = $null
                    Pid     = 0
                })
            }
        }
    }

    # adb devices 里已有的 emulator-* / 127.0.0.1:* 条目
    try {
        foreach ($d in (Get-AdbDevices)) {
            if ($d.Serial -notmatch '^emulator-\d+$' -and
                $d.Serial -notmatch '^\d{1,3}(\.\d{1,3}){3}:\d+$') { continue }
            $vendor = 'unknown'
            $label = '未知厂商'
            if ($d.Serial -match '(?:emulator-)?(\d{4,5})$') {
                $num = [int]$Matches[1]
                foreach ($vp in $script:VendorProfiles) {
                    if ($vp.Ports -contains $num) { $vendor = $vp.Id; $label = $vp.Label; break }
                }
            }
            $candidates.Add([pscustomobject]@{
                Vendor  = $vendor
                Label   = $label
                Serial  = $d.Serial
                Source  = 'adb-devices'
                Index   = ''
                Running = ($d.State -eq 'device')
                Booted  = ($d.State -eq 'device')
                Cli     = $null
                Pid     = 0
            })
        }
    } catch { }

    # 去重：同一厂商同一序列号只留**信息最全**的一条（JSON > adb > 端口扫描）
    $rank = @{ 'mumu-json' = 3; 'vendor-cli' = 2; 'adb-devices' = 2; 'port-scan' = 1 }
    $best = @{}
    $order = New-Object System.Collections.Generic.List[string]
    foreach ($c in $candidates) {
        $key = if ($c.Serial) { "$($c.Vendor)|$($c.Serial)" } else { "$($c.Vendor)|pid:$($c.Pid)" }
        if (-not $best.ContainsKey($key)) {
            $best[$key] = $c
            $order.Add($key)
            continue
        }
        $old = $best[$key]
        if ($rank[$old.Source] -ge $rank[$c.Source]) { continue }
        $best[$key] = $c
    }
    return @($order | ForEach-Object { $best[$_] })
}

# 把候选连进 adb，返回真正 online 的序列号。
function Connect-Emulators {
    param([object[]] $Inventory)
    $adb = Need-Adb
    $null = Invoke-Native -Exe $adb -NativeArgs @('start-server') -WaitSec 20
    $online = @()
    foreach ($c in $Inventory) {
        if (-not $c.Serial) { continue }
        $null = Invoke-Native -Exe $adb -NativeArgs @('connect', $c.Serial) -WaitSec 20
        $txt = ($script:NativeOut -join ' ')
        if ($txt -match 'connected to|already connected') {
            $online += $c.Serial
            Ok ('{0,-14} {1}' -f $c.Label, $c.Serial)
        } else {
            $first = (($script:NativeOut | Select-Object -First 1) -replace '\s+', ' ').Trim()
            Warn2 ('{0,-14} {1} -> {2}' -f $c.Label, $c.Serial, $first)
        }
    }
    return $online
}

# 单设备选择：-Serial > 唯一在线设备 > 自动连上唯一的一台
function Resolve-Target {
    param([object[]] $Inventory)
    if ($Serial) { return $Serial }
    $online = @(Get-AdbDevices | Where-Object { $_.State -eq 'device' })
    if ($online.Count -eq 1) { return $online[0].Serial }
    if ($online.Count -eq 0 -and $Inventory) {
        $linked = @(Connect-Emulators -Inventory $Inventory)
        if ($linked.Count -eq 1) { return $linked[0] }
        if ($linked.Count -gt 1) {
            Die @"
连上 $($linked.Count) 台：$($linked -join ', ')
本脚本**不猜**。加 -Serial 指定：
  .\emulator-lab.ps1 $Action -Serial <序列号> ...
"@
        }
    }
    return Resolve-OneDevice
}

# ── 输入注入（走 adb input，任何设备通吃，不依赖厂商 CLI）────────────
$script:KeyCodes = @{
    'home' = 'KEYCODE_HOME'; 'back' = 'KEYCODE_BACK'; 'app' = 'KEYCODE_APP_SWITCH'
    'menu' = 'KEYCODE_MENU'; 'enter' = 'KEYCODE_ENTER'; 'del' = 'KEYCODE_DEL'
    'up' = 'KEYCODE_DPAD_UP'; 'down' = 'KEYCODE_DPAD_DOWN'
    'left' = 'KEYCODE_DPAD_LEFT'; 'right' = 'KEYCODE_DPAD_RIGHT'
    'power' = 'KEYCODE_POWER'; 'volup' = 'KEYCODE_VOLUME_UP'
    'voldown' = 'KEYCODE_VOLUME_DOWN'; 'mute' = 'KEYCODE_VOLUME_MUTE'
}

# ── frida-server 布局 ───────────────────────────────────────────────
# Android 端的 frida-server 是**裸 ELF**，没有后缀、没有 x 位标记，
# 所以不能直接 pull 回来执行 —— 官方做法是 gzip 压缩后再推。
# 17.9 起官方包名带架构后缀（frida-server-17.9.6-android-arm64），
# 老包是 frida-server-17.9.6-android-arm。两种都认。
$script:FridaLayout = @{
    Local  = 'frida-server'
    Remote = '/data/local/tmp/frida-server'
    Gz     = '/data/local/tmp/frida-server.gz'
    Pid    = '/data/local/tmp/frida.pid'
    Port   = 27042
}

switch ($Action) {

    # ── 环境自检：每项实跑，不只查「装没装」────────────────────────
    'doctor' {
        Step '模拟器能力链自检（每项都是实跑）'
        $rows = @(
            @{ Id = 'adb';        Note = '唯一必需：所有动态能力的地基' },
            @{ Id = 'tshark';     Note = 'PC 侧 pcap 解析' },
            @{ Id = 'dumpcap';    Note = 'PC 侧抓包（Npcap）' },
            @{ Id = 'mitmproxy';  Note = 'HTTP(S) 解密代理' },
            @{ Id = 'frida';      Note = '动态插桩客户端' },
            @{ Id = 'frida-ps';   Note = '进程枚举' },
            @{ Id = 'objection';  Note = 'Frida 增强' },
            @{ Id = 'emulator';   Note = '官方 AVD' },
            @{ Id = 'avdmanager'; Note = 'AVD 创建/管理' },
            @{ Id = 'scrcpy';     Note = '投屏（人看；agent 不需要）' }
        )
        foreach ($r in $rows) {
            $spec = Resolve-ReverseToolSpec -Name $r.Id
            if (-not $spec.Available) {
                Warn2 ('{0,-12} {1,-26} 缺失' -f $r.Id, $r.Note)
                continue
            }
            # avdmanager 没有 --version，用 `list avd`（无 AVD 时它报「没有可用 AVD」也算跑通），
            # 这是 2026-10-11 实测到的：早先写 --version 让它自己的 stderr 把 doctor 打死了。
            $probe = switch ($r.Id) {
                'tshark'     { Invoke-VersionProbe -Exe $spec.Command -ProbeArgs @('-v') }
                'dumpcap'    { Invoke-VersionProbe -Exe $spec.Command -ProbeArgs @('-v') }
                'mitmproxy'  { Invoke-VersionProbe -Exe $spec.Command -ProbeArgs @('--version') }
                'frida'      { Invoke-VersionProbe -Exe $spec.Command -ProbeArgs @('--version') }
                'frida-ps'   { Invoke-VersionProbe -Exe $spec.Command -ProbeArgs @('--version') }
                'objection'  { Invoke-VersionProbe -Exe $spec.Command -ProbeArgs @('version') }
                'emulator'   { Invoke-VersionProbe -Exe $spec.Command -ProbeArgs @('-version') }
                'avdmanager' { Invoke-VersionProbe -Exe $spec.Command -ProbeArgs @('list', 'avd') }
                'adb'        { Invoke-VersionProbe -Exe $spec.Command -ProbeArgs @('version') }
                'scrcpy'     { Invoke-VersionProbe -Exe $spec.Command -ProbeArgs @('--version') }
                default      { '' }
            }
            Ok ('{0,-12} via={1,-6} {2,-26} {3}' -f $r.Id, $spec.Via, $r.Note,
                ($probe -replace '\s+', ' '))
        }

        Step '官方 AVD 镜像（第三方模拟器不含此项）'
        $avdDir = Join-Path $env:USERPROFILE '.android\avd'
        $avdCount = @(Get-ChildItem -LiteralPath $avdDir -Filter '*.ini' `
                      -ErrorAction SilentlyContinue).Count
        if ($avdCount -gt 0) { Ok "$avdCount 个 AVD 定义（$avdDir）" }
        else { Warn2 '未发现 AVD —— 第三方模拟器不需要此项，属正常' }

        Step '厂商控制 CLI'
        $any = $false
        foreach ($vp in $script:VendorProfiles) {
            $clis = @(Find-VendorCli -VendorId $vp.Id)
            if ($clis.Count -eq 0) { continue }
            $any = $true
            Ok ('{0,-14} {1}' -f $vp.Label, $clis[0])
        }
        if (-not $any) {
            Say '  （未检测到任何厂商控制 CLI。装模拟器后本脚本会自动认出，无需改配置。）'
        }

        Step '设备'
        try {
            $devs = @(Get-AdbDevices)
            if ($devs.Count -eq 0) {
                Warn2 'adb devices 里没有设备 —— 静态链路可用，动态链路不可用'
            } else {
                foreach ($d in $devs) { Ok ('{0,-24} {1}' -f $d.Serial, $d.State) }
            }
        } catch { Warn2 'adb devices 查询失败' }
    }

    # ── 发现 ─────────────────────────────────────────────────────
    'scan' {
        Step '模拟器发现（厂商 CLI + 端口扫描 + adb devices）'
        $inv = @(Get-EmulatorInventory -NoScan:$SkipPortScan)
        if ($inv.Count -eq 0) {
            Warn2 '没发现任何模拟器实例'
            Say @"
装了但没认出来，按顺序查三件事：
  1. 模拟器是不是**已经启动**（没开时 MuMuManager 能报状态，端口却是死的）
  2. 模拟器设置里的「ADB 调试 / 远程连接」有没有开
  3. 厂商 CLI 在不在 PATH（装在 D:\Program Files\<厂商>\... 下是常态）
"@
            break
        }
        foreach ($c in $inv) {
            $state = if ($c.Booted) { '已启动' } elseif ($c.Running) { '进程中' } else { '未运行' }
            $ser = if ($c.Serial) { $c.Serial } else { '(待 connect)' }
            Ok ('{0,-14} {1,-24} idx={2,-4} {3,-8} src={4}' -f
                $c.Label, $ser, $c.Index, $state, $c.Source)
        }
    }

    'connect' {
        $inv = @(Get-EmulatorInventory -NoScan:$SkipPortScan)
        if ($inv.Count -eq 0) { Die '没发现任何模拟器实例，先跑 .\emulator-lab.ps1 scan' }
        Step ("连接 $($inv.Count) 个候选")
        $linked = @(Connect-Emulators -Inventory $inv)
        Step 'adb devices'
        foreach ($d in (Get-AdbDevices)) { Ok ('{0,-24} {1}' -f $d.Serial, $d.State) }
        if ($linked.Count -eq 0) {
            Die '一个都没连上。模拟器里打开「设置 → 其他/开发者 → ADB 调试（远程）」再试。'
        }
        Ok "$($linked.Count) 台已连上"
    }

    'list' {
        Step 'adb devices'
        $devs = @(Get-AdbDevices)
        if ($devs.Count -eq 0) { Warn2 '无设备'; break }
        foreach ($d in $devs) {
            $kind = if ($d.Serial -match '^emulator-\d+$') { '模拟器' }
                    elseif ($d.Serial -match '^\d{1,3}(\.\d{1,3}){3}:\d+$') { '模拟器/网络设备' }
                    else { 'USB 真机' }
            Ok ('{0,-24} {1,-8} {2}' -f $d.Serial, $d.State, $kind)
        }
    }

    # ── 设备画像：装包前先对一遍 API 级别与 ABI ───────────────────
    'profile' {
        if (-not $Target) { $Target = $Serial }
        if (-not $Target) { Die '用法：emulator-lab.ps1 profile <serial>' }
        $dev = Resolve-Target
        Step "设备画像 $dev"
        $props = @(
            'ro.product.model', 'ro.product.manufacturer', 'ro.product.brand',
            'ro.product.cpu.abi', 'ro.product.cpu.abilist',
            'ro.build.version.release', 'ro.build.version.sdk',
            'ro.kernel.qemu', 'ro.hardware', 'ro.boot.serialno'
        )
        foreach ($p in $props) {
            $v = (Adb -Dev $dev -NativeArgs @('shell', 'getprop', $p) |
                  Select-Object -First 1)
            Say ('{0,-32} {1}' -f $p, ($v -replace '\s+', ' '))
        }
        Step 'root / frida 现状'
        $su = (Adb -Dev $dev -NativeArgs @('shell', 'which', 'su') | Select-Object -First 1)
        if ($su) { Ok "有 su: $su" } else { Warn2 '没有 su（模拟器一般可用 adb root，见 doctor）' }
        $fsp = (Adb -Dev $dev -NativeArgs @('shell', 'ps', '-A') |
                Select-String -Pattern 'frida' | Select-Object -First 3)
        if ($fsp) { foreach ($l in $fsp) { Ok ('frida 进程: ' + ($l -replace '\s+', ' ')) } }
        else { Warn2 'frida-server 没在跑（跑 frida deploy 起）' }
        Step '抓包工具'
        foreach ($t in @('tcpdump', 'busybox', 'curl')) {
            $w = (Adb -Dev $dev -NativeArgs @('shell', 'which', $t) | Select-Object -First 1)
            if ($w) { Ok ('{0,-10} {1}' -f $t, $w) } else { Warn2 "$t 不在设备里" }
        }
    }

    # ── 实例控制（走厂商 CLI；没有 CLI 就报，不猜）────────────────
    'start' {
        if (-not $Vendor) {
            Die '用法：emulator-lab.ps1 start -Vendor mumu -Index 0（或 ldplayer/nox/memu/avd）'
        }
        $vp = Get-VendorProfile -Id $Vendor
        if (-not $vp) {
            $ids = (@($script:VendorProfiles | ForEach-Object { $_.Id })) -join ', '
            Die "认不出厂商 '$Vendor'。可选：$ids"
        }
        $clis = @(Find-VendorCli -VendorId $vp.Id)
        if ($clis.Count -eq 0) {
            Die @"
没找到 $($vp.Label) 的控制 CLI（$($vp.ExecName)）。

不是缺陷 —— 模拟器通常装在 D:\Program Files\<厂商>\... 或 C:\Program Files\... 下，
不在工具根、也不在 PATH，所以探测层认不出。两条出路：
  1. 手动起一次模拟器，然后用 .\emulator-lab.ps1 connect -Auto 接管（推荐路径）
  2. 把 $($vp.ExecName) 所在目录加进 PATH，或在 D:\Tools\_map.json 里登记别名
"@
        }
        $cli = $clis[0]
        $idx = if ($Index -ge 0) { [string]$Index } else { '0' }
        Step "$($vp.Label) 启动实例 $idx  ($cli)"
        $cargs = switch ($vp.Cli) {
            'mumu'       { @('control', '-v', $idx, 'launch') }
            'ldconsole'  { @('launch', '--index', $idx) }
            'noxconsole' { @('launch', '-index', $idx) }
            'memuc'      { @('start', '-i', $idx) }
            default      { Die "$($vp.Label) 没有可脚本化的启动命令；请手动起实例后用 connect -Auto" }
        }
        $r = Invoke-VendorCli -CliPath $cli -CliArgs $cargs
        if ($r.Rc -ne 0 -and $r.Out) { Warn2 ('rc=' + $r.Rc + ' ' + ($r.Out -replace '\s+', ' ')) }
        Ok '已下达启动命令。Android 冷启动要 30-120 秒。'
    }

    'stop' {
        $vp = Get-VendorProfile -Id $Vendor
        if (-not $vp) { Die '用法：emulator-lab.ps1 stop -Vendor mumu -Index 0' }
        $clis = @(Find-VendorCli -VendorId $vp.Id)
        if ($clis.Count -eq 0) { Die "没找到 $($vp.Label) 的控制 CLI" }
        $idx = if ($Index -ge 0) { [string]$Index } else { '0' }
        Step "$($vp.Label) 关闭实例 $idx"
        $cargs = switch ($vp.Cli) {
            'mumu'       { @('control', '-v', $idx, 'shutdown') }
            'ldconsole'  { @('quit', '--index', $idx) }
            'noxconsole' { @('quit', '-index', $idx) }
            'memuc'      { @('stop', '-i', $idx) }
            default      { Die "$($vp.Label) 没有可脚本化的停止命令" }
        }
        $null = Invoke-VendorCli -CliPath $clis[0] -CliArgs $cargs
        Ok '已下达关闭命令'
    }

    'restart' {
        $vp = Get-VendorProfile -Id $Vendor
        if (-not $vp) { Die '用法：emulator-lab.ps1 restart -Vendor mumu -Index 0' }
        $clis = @(Find-VendorCli -VendorId $vp.Id)
        if ($clis.Count -eq 0) { Die "没找到 $($vp.Label) 的控制 CLI" }
        $idx = if ($Index -ge 0) { [string]$Index } else { '0' }
        Step "$($vp.Label) 重启实例 $idx"
        $cargs = switch ($vp.Cli) {
            'mumu'       { @('control', '-v', $idx, 'restart') }
            'ldconsole'  { @('reboot', '--index', $idx) }
            'noxconsole' { @('reboot', '-index', $idx) }
            'memuc'      { @('restart', '-i', $idx) }
            default      { Die "$($vp.Label) 没有可脚本化的重启命令" }
        }
        $null = Invoke-VendorCli -CliPath $clis[0] -CliArgs $cargs
        Ok '已下达重启命令（Android 起来要 30-120 秒）'
    }

    # ── 输入注入 ─────────────────────────────────────────────────
    'key' {
        if (-not $KeyCode) {
            Die '用法：emulator-lab.ps1 key <home|back|app|enter|up|down|left|right|power|volup|voldown|KEYCODE_XXX>'
        }
        $code = $KeyCode
        $lk = $KeyCode.ToLowerInvariant()
        if ($script:KeyCodes.ContainsKey($lk)) { $code = $script:KeyCodes[$lk] }
        $dev = Resolve-Target
        Step "按键 $code -> $dev"
        $null = Adb -Dev $dev -NativeArgs @('shell', 'input', 'keyevent', $code)
        Ok '已发送'
    }

    'tap' {
        if ($Target -match '^\d+$' -and $Y -lt 0) {
            # 位置参数形态：tap <serial> <x> <y>
            $Y = [int]$X
            $X = [int]$Target
            $Target = $null
        }
        if ($X -lt 0 -or $Y -lt 0) { Die '用法：emulator-lab.ps1 tap <serial> <x> <y>' }
        $dev = Resolve-Target
        Step "点击 ($X,$Y) -> $dev"
        $null = Adb -Dev $dev -NativeArgs @('shell', 'input', 'tap', "$X", "$Y")
        Ok '已点击'
    }

    'swipe' {
        if ($Target -match '^\d+$') {
            # swipe <serial> <x1> <y1> <x2> <y2>
            $X2 = $X
            $Y2 = $Y
            $X = [int]$Target
            $Target = $null
        }
        if ($X -lt 0 -or $Y -lt 0 -or $X2 -lt 0 -or $Y2 -lt 0) {
            Die '用法：emulator-lab.ps1 swipe <serial> <x1> <y1> <x2> <y2> [-DurationMs 500]'
        }
        $dev = Resolve-Target
        Step "滑动 ($X,$Y)->($X2,$Y2) ${DurationMs}ms -> $dev"
        $null = Adb -Dev $dev -NativeArgs @('shell', 'input', 'swipe',
            "$X", "$Y", "$X2", "$Y2", "$DurationMs")
        Ok '已滑动'
    }

    'text' {
        if (-not $Target) { Die '用法：emulator-lab.ps1 text <要输入的文字> [-Serial x]' }
        $dev = Resolve-Target
        Step "输入文本 -> $dev"
        # input text 只认 %s 表示空格；中文/emoji 要走 IME，见 references/emulator-lab.md
        $escaped = $Target -replace ' ', '%s'
        $null = Adb -Dev $dev -NativeArgs @('shell', 'input', 'text', $escaped)
        Ok '已输入（input text 不支持中文/emoji，见 references/emulator-lab.md）'
    }

    'shot' {
        $dev = Resolve-Target
        $out = if ($Out) { $Out } else { 'shot_{0}.png' -f (Get-Date -Format yyyyMMdd_HHmmss) }
        if (-not $out.EndsWith('.png')) { $out += '.png' }
        $remote = '/sdcard/_emulab.png'
        Step "截图 -> $out"
        $null = Adb -Dev $dev -NativeArgs @('shell', 'screencap', '-p', $remote)
        $null = Adb -Dev $dev -NativeArgs @('pull', $remote, $out)
        $null = Adb -Dev $dev -NativeArgs @('shell', 'rm', $remote)
        if (Test-Path -LiteralPath $out) {
            Ok ('已保存 {0} ({1} KB)' -f $out, [math]::Round((Get-Item $out).Length / 1KB, 1))
        } else { Die "截图失败：$out 没生成" }
    }

    # ── 抓包 ②：PC 侧接口与 pcap ────────────────────────────────
    'iflist' {
        Step 'PC 侧抓包接口（dumpcap -D）'
        $dc = Need-Tool 'dumpcap' '装法：winget install --id WiresharkFoundation.Wireshark'
        $null = Invoke-Native -Exe $dc -NativeArgs @('-D')
        foreach ($l in $script:NativeOut) { Say ('  ' + ($l -replace '\s+', ' ')) }
        Say ''
        Say '模拟器的流量走本机的虚拟网卡（\Device\NPF_{…} / VMware / vEthernet 之类）。'
        Say '用 -Interface <编号或名称> 指定，编号从上面列表第 1 列取。'
    }

    'pcap' {
        # 三层入口的统一分发：tcpdump(设备侧) / dumpcap(PC侧) / tshark(解析)
        $mode = if ($Target) { $Target.ToLowerInvariant() } else { 'dumpcap' }
        switch ($mode) {
            'tcpdump' {
                $dev = Resolve-Target
                $remote = if ($Out) { $Out } else { '/sdcard/_emulab.pcap' }
                Step "设备侧 tcpdump -> $remote （$dev）"
                $tb = (Adb -Dev $dev -NativeArgs @('shell', 'which', 'tcpdump') | Select-Object -First 1)
                if (-not $tb) {
                    Warn2 '设备里没有 tcpdump。模拟器一般自带；若真没有，两条退路：'
                    Say '  1) .\emulator-lab.ps1 pcap dumpcap -Interface <虚拟网卡>   ← 不动设备'
                    Say '  2) push 一个静态 tcpdump 到 /data/local/tmp 再 chmod 755'
                    break
                }
                $secs = if ($TimeoutSec -gt 0) { $TimeoutSec } else { 30 }
                Say "抓 $secs 秒…"
                $null = Adb -Dev $dev -WaitSec ($secs + 15) -NativeArgs @(
                    'shell', 'tcpdump', '-i', 'any', '-s', '0', '-w', $remote, '-G', "$secs")
                $local = Split-Path -Leaf $remote
                $null = Adb -Dev $dev -NativeArgs @('pull', $remote, $local)
                Ok "已拉回 $local"
            }
            'tshark' {
                $file = $Out
                if ($Target -and (Test-Path -LiteralPath $Target)) { $file = $Target }
                if (-not $file) { Die '用法：emulator-lab.ps1 pcap tshark -Out <抓到的.pcap>' }
                if (-not (Test-Path -LiteralPath $file)) { Die "文件不存在: $file" }
                $ts = Need-Tool 'tshark' '装法：winget install --id WiresharkFoundation.Wireshark'
                Step "tshark 解析 $file"
                $targs = @('-r', $file)
                if ($Filter) { $targs += @('-Y', $Filter) }
                $targs += @('-T', 'fields', '-e', 'frame.number', '-e', 'ip.src',
                            '-e', 'ip.dst', '-e', 'tcp.dstport', '-e', 'udp.dstport',
                            '-e', 'frame.len')
                $null = Invoke-Native -Exe $ts -NativeArgs $targs
                foreach ($l in ($script:NativeOut | Select-Object -First 60)) { Say ('  ' + $l) }
            }
            default {
                $dc = Need-Tool 'dumpcap' '装法：winget install --id WiresharkFoundation.Wireshark'
                $out = if ($Out) { $Out } else { 'capture_{0}.pcapng' -f (Get-Date -Format yyyyMMdd_HHmmss) }
                $secs = if ($TimeoutSec -gt 0) { $TimeoutSec } else { 30 }
                Step "PC 侧抓包 $secs 秒 -> $out"
                if (-not $Interface) {
                    Warn2 '没给 -Interface。先跑 .\emulator-lab.ps1 iflist 看清接口名。'
                    Say '模拟器流量走虚拟网卡，不指定就抓到物理网卡（看不到模拟器里的包）。'
                    break
                }
                Say "抓 $secs 秒…"
                $null = Invoke-Native -Exe $dc -WaitSec ($secs + 20) -NativeArgs @(
                    '-i', $Interface, '-a', 'duration:' + $secs, '-w', $out)
                if (Test-Path -LiteralPath $out) {
                    Ok ('已保存 {0} ({1} MB)' -f $out,
                        [math]::Round((Get-Item $out).Length / 1MB, 2))
                } else { Die "抓包没产出 $out" }
            }
        }
    }

    # ── 抓包 ③：mitm 代理与 CA ───────────────────────────────────
    'proxy' {
        $mode = if ($Target) { $Target.ToLowerInvariant() } else { 'status' }
        $dev = Resolve-Target
        if ($mode -eq 'status') {
            Step "全局代理状态 $dev"
            $cur = (Adb -Dev $dev -NativeArgs @('shell', 'settings', 'get', 'global', 'http_proxy') |
                    Select-Object -First 1)
            Say ('global http_proxy = ' + ($cur -replace '\s+', ' '))
            break
        }
        if ($mode -eq 'off') {
            Step "关闭全局代理 $dev"
            $null = Adb -Dev $dev -NativeArgs @('shell', 'settings', 'put', 'global',
                'http_proxy', ':0')
            Ok '已关闭（记得重启目标 app 才生效）'
            break
        }
        $mp = Need-Tool 'mitmproxy' '装法：pip install mitmproxy'
        Step "打开 mitm 代理 :$Port 并指向设备 $dev"
        $null = Invoke-Native -Exe $mp -NativeArgs @('--version')
        Say ('  ' + ($script:NativeOut | Select-Object -First 1))
        $hostIp = if ($dev -match '^emulator-\d+$') { '10.0.2.2' }
                  elseif ($dev -match '^\d{1,3}(\.\d{1,3}){3}:\d+$') { '10.0.2.2' }
                  else { '<本机局域网IP>' }
        Say ''
        Say "设备端代理地址不要写 127.0.0.1（那是设备自己）："
        Say "  · 官方 AVD（QEMU NAT）   -> 10.0.2.2:$Port"
        Say "  · 第三方模拟器（共享网络）-> 10.0.2.2 或本机局域网 IP，先用 ipconfig 确认"
        Say "  · 真机（USB）             -> $hostIp"
        $null = Adb -Dev $dev -NativeArgs @('shell', 'settings', 'put', 'global',
            'http_proxy', ('{0}:{1}' -f $hostIp, $Port))
        Ok ('已设 global http_proxy = {0}:{1}' -f $hostIp, $Port)
        Say ''
        Say '配套两步：'
        Say "  1) 另开终端：mitmproxy --listen-port $Port"
        Say "  2) .\emulator-lab.ps1 cert install -Serial $dev"
        Say 'Android 7+ 的 app 默认不信任用户 CA，要 root + 写进系统证书库（见 references/emulator-lab.md）'
    }

    'cert' {
        $mode = if ($Target) { $Target.ToLowerInvariant() } else { 'install' }
        $dev = Resolve-Target
        if ($mode -eq 'show') {
            Step "已添加的用户证书 $dev"
            $fp = Adb -Dev $dev -NativeArgs @('shell',
                'ls', '/data/misc/user/0/cacerts-added')
            foreach ($l in ($fp | Select-Object -First 20)) { Say ('  ' + $l) }
            break
        }
        $homeDir = [Environment]::GetFolderPath('UserProfile')
        $ca = if ($Cert) { $Cert }
              else { Join-Path $homeDir '.mitmproxy\mitmproxy-ca-cert.cer' }
        if (-not (Test-Path -LiteralPath $ca)) {
            Die @"
找不到 mitm CA 证书：$ca
先跑一次 mitmproxy 生成：
  mitmproxy --listen-port $Port
证书落在 ~/.mitmproxy/mitmproxy-ca-cert.cer
"@
        }
        Step "安装 CA 到 $dev"
        $tmp = '/data/local/tmp/mitm-ca.cer'
        $null = Adb -Dev $dev -NativeArgs @('push', $ca, $tmp)
        $id = (Adb -Dev $dev -NativeArgs @('shell', 'id') | Select-Object -First 1)
        Say "  $id"
        $md5 = (Get-FileHash -LiteralPath $ca -Algorithm MD5).Hash.ToLowerInvariant()
        $name = ''
        for ($i = 0; $i -lt $md5.Length; $i += 2) {
            if ($i -gt 0) { $name += '.' }
            $name += $md5.Substring($i, 2)
        }
        Say ''
        Say "旧式系统证书文件名（由 CA 的 MD5 指纹算出）: $name"
        Say '用户证书已推送到 /data/local/tmp/mitm-ca.cer。'
        Say 'Android 7+ 的 app 默认只认系统证书，要升级成系统证书：'
        Say "  adb -s $dev root"
        Say "  adb -s $dev remount"
        Say "  # 把 mitm-ca.cer 复制到 /system/etc/security/cacerts/$name 并 chmod 644"
        Ok '完成'
    }

    # ── 动态调试：frida-server 部署 ───────────────────────────────
    'frida' {
        $mode = if ($Target) { $Target.ToLowerInvariant() } else { 'deploy' }
        switch ($mode) {
            'deploy' {
                $dev = Resolve-Target
                if (-not $Server) {
                    Die '用法：emulator-lab.ps1 frida deploy -Server <frida-server 可执行文件路径>'
                }
                if (-not (Test-Path -LiteralPath $Server)) { Die "文件不存在: $Server" }
                $fc = Need-Tool 'frida' '装法：pip install frida-tools'
                $clientVer = ((& $fc '--version' 2>&1 | Select-Object -First 1) -replace '\s+', ' ').Trim()
                Step "部署 frida-server -> $dev"
                Ok "本机 frida 版本: $clientVer"
                $abi = (Adb -Dev $dev -NativeArgs @('shell', 'getprop', 'ro.product.cpu.abi') |
                        Select-Object -First 1)
                Say "设备 ABI     : $abi"
                Say '★ 版本铁律：frida-server 与本机 frida 版本**必须完全一致**，差一位就「连不上」。'
                # Android 端的 frida-server 是裸 ELF：既没有可执行位标记，也不能被 adb
                # push 成可执行文件。官方做法是 gzip 压缩后推、再在设备上 gunzip。
                $gz = Join-Path $env:TEMP 'frida-server.gz'
                Remove-Item -LiteralPath $gz -Force -ErrorAction SilentlyContinue
                Say ('gzip 压缩中（' + (Split-Path -Leaf $Server) + '）…')
                & tar -czf $gz -C (Split-Path -Parent $Server) (Split-Path -Leaf $Server)
                if (-not (Test-Path -LiteralPath $gz)) {
                    Die 'gzip 失败：tar 不可用（Win10 自带的 bsdtar 正常应可用）'
                }
                $null = Adb -Dev $dev -NativeArgs @('push', $gz, $script:FridaLayout.Gz)
                $null = Adb -Dev $dev -NativeArgs @('shell', 'rm', $script:FridaLayout.Remote)
                $null = Adb -Dev $dev -NativeArgs @('shell', 'gunzip', '-f', $script:FridaLayout.Gz)
                $null = Adb -Dev $dev -NativeArgs @('shell', 'chmod', '755', $script:FridaLayout.Remote)
                Ok '已推送并解压'
                Step '启动 frida-server'
                $null = Adb -Dev $dev -NativeArgs @('shell', 'su', '-c', ('{0} -l 0.0.0.0:{1} >/dev/null 2>&1 &' -f
                    $script:FridaLayout.Remote, $script:FridaLayout.Port))
                Start-Sleep -Seconds 2
                $ps = (Adb -Dev $dev -NativeArgs @('shell', 'ps', '-A') |
                       Select-String -Pattern 'frida-server' | Select-Object -First 1)
                if ($ps) { Ok ('已运行: ' + ($ps -replace '\s+', ' ')) }
                else { Warn2 '没看到 frida-server 进程。无 root 时先试 adb -s <serial> root' }
                Remove-Item -LiteralPath $gz -Force -ErrorAction SilentlyContinue
            }
            'check' {
                $dev = Resolve-Target
                Step "frida 链路 $dev"
                $ps = (Adb -Dev $dev -NativeArgs @('shell', 'ps', '-A') |
                       Select-String -Pattern 'frida' | Select-Object -First 3)
                if ($ps) { foreach ($l in $ps) { Ok ($l -replace '\s+', ' ') } }
                else { Warn2 '设备上没有 frida 进程' }
                $fps = Tool 'frida-ps'
                if ($fps) {
                    # 多设备时 -U 会挂到错的那台，必须 -H 走转发端口
                    Step "adb forward tcp:27042 -> $dev"
                    $null = Adb -Dev $dev -NativeArgs @('forward', 'tcp:27042', 'tcp:27042')
                    $null = Invoke-Native -Exe $fps -NativeArgs @('-H', '127.0.0.1:27042', '-a')
                    foreach ($l in ($script:NativeOut | Select-Object -First 10)) { Say ('  ' + $l) }
                }
            }
            default { Die "frida 子动作只能是 deploy / check（收到 '$mode'）。" }
        }
    }

    # ── 契约自测入口（由 test-emulator-lab.ps1 调用）────────────────
    # 为什么要有这个隐藏动作，而不是让外部脚本 AST 提取函数再执行：
    #   提取出来的 ScriptBlock 里 $script: 指向它自己的 script 作用域，与本文件的
    #   $script:NativeOut 不是同一个变量槽 —— 实测永远读到空（apk-debug.ps1 的
    #   selftest-adb 是同一个道理）。让脚本自己跑自己，作用域语义天然一致，
    #   测的就是真代码路径。
    'selftest' {
        $sub = if ($Target) { $Target } else { 'ports' }
        switch ($sub) {
            'ports' {
                # 端口表契约：同一家内部互不重复，且落在已知量级
                $seen = @{}
                $dup = @()
                foreach ($vp in $script:VendorProfiles) {
                    foreach ($p in $vp.Ports) {
                        if ($seen.ContainsKey($p)) { $dup += "$p/$($seen[$p])/$($vp.Id)" }
                        $seen[$p] = $vp.Id
                    }
                }
                Write-Output ('VENDORS=' + $script:VendorProfiles.Count)
                Write-Output ('DUPPORTS=' + ($dup -join ','))
                Write-Output ('PORTCOUNT=' + $seen.Count)
            }
            'native' {
                # 原生调用契约：退出码与输出必须如实传出
                $null = Invoke-Native -Exe $env:EMULAB_FAKE_EXE -NativeArgs @('install')
                Write-Output ('RC=' + $script:NativeRc)
                Write-Output ('OUT=' + (($script:NativeOut | Select-Object -First 1) -replace '\s+', ' '))
            }
            'keymap' {
                Write-Output ('KEYS=' + (($script:KeyCodes.Keys | Sort-Object) -join ','))
                Write-Output ('HOME=' + $script:KeyCodes['home'])
            }
            'frida-layout' {
                Write-Output ('REMOTE=' + $script:FridaLayout.Remote)
                Write-Output ('PORT=' + $script:FridaLayout.Port)
            }
            'mumu-json' {
                # MuMuManager 的 `info -v all` 是**唯一**能自报端口的厂商 CLI，
                # 所以它的 JSON 解析必须能在没有真 MuMu 的机器上被测到：
                # 用 EMULAB_MUMU_FIXTURE（或仓内 fixture）指向一个复刻官方
                # 字段表的假 exe。判据是解析出的实例数与端点，不是「脚本没崩」。
                $fake = $env:EMULAB_MUMU_FIXTURE
                if (-not $fake) {
                    $fake = Join-Path (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)) `
                                      'scripts\experience-cards\fixtures\fake-mumu-manager.cmd'
                }
                if (-not (Test-Path -LiteralPath $fake)) {
                    Write-Output 'MU_FIXTURE=missing'
                    break
                }
                $insts = @(Get-MumuInstances -CliPath $fake)
                Write-Output 'MU_FIXTURE=found'
                Write-Output ('MU_INSTANCES=' + $insts.Count)
                $serials = @($insts | ForEach-Object {
                    if ($_.adb_host_ip -and $_.adb_port) {
                        '{0}:{1}' -f $_.adb_host_ip, $_.adb_port
                    }
                } | Where-Object { $_ })
                Write-Output ('MU_SERIALS=' + ($serials -join ','))
                Write-Output ('MU_BOOTED=' + @($insts | Where-Object { $_.is_android_started }).Count)
            }
            'vendor-lookup' {
                # 用例表与 test-emulator-lab.ps1 的 $expected 一一对应；
                # 两个地方各写一份会让「改了脚本忘了改测试」变成假绿。
                foreach ($v in @('mumu', 'ldplayer', 'nox', '夜神', 'memu', 'MEmu',
                                 'bluestacks', 'bs', 'avd', 'LDPlayer9', 'MuMu', 'nope')) {
                    $vp = Get-VendorProfile -Id $v
                    $id = if ($vp) { $vp.Id } else { 'NONE' }
                    Write-Output ("LOOKUP[$v]=$id")
                }
            }
            default { Die "未知 selftest 子动作: $sub" }
        }
    }
}

exit 0