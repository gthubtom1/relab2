#Requires -Version 5.1
<#
start.ps1 —— 幂等起 x64dbg（或 x32dbg），让 x64dbg-MCP(9094/9095) 可用。

为什么要有这个包装：工具根路径不许写死；而且"已在监听"要直接成功返回，
不要重复起实例（多开会把 9094/9095 搅乱，并留下僵尸进程）。

★ 2026-10-16 重写 —— 修「换机就断」：
  旧版只找 `<工具根>\cli\start-x64dbg-mcp.ps1`，而那个文件**是某台机器工具根里的手放文件、
  不随仓库走** —— 换机后本脚本必然 exit 2，而卡里写着"跑 scripts/start.ps1 起 MCP"。
  现在改成三级解析，**任何一级成功都不依赖某台机器上的专属文件**：
    ① 兼容层：工具根下若有 cli\start-x64dbg-mcp.ps1（本机已验证幂等）→ 转调它
    ② 探测层：Bootstrap.ps1 的 Resolve-ReverseToolSpec（env → PATH → 别名表 → 工具根递归）
    ③ 工具根内的常见布局扫描
  并且对 ②③ 拿到的 exe 做一次**headless → GUI** 归一：
  x64dbg-MCP 是**活在被调试进程里的插件**，headless.exe 不加载插件、端口永远不监听
  （x64dbg-reverse/SKILL.md 已记这条坑）。GUI 进程由 Win32_Process::Create **脱离父 shell** 启动，
  所以经 bash 调用不会把本轮卡死。

用法：
  powershell -NoProfile -ExecutionPolicy Bypass -File start.ps1
  ... -Target <样本路径>         ★ 首选：读 PE Machine 自动选 x64/x32 与端口
                                （0x014C→x32/9095，0x8664→x64/9094，其它→exit 2）
  ... -Arch x32                起 x32 调试器（端口 9095）；显式 -Arch 优先于 -Target
  ... -WaitSeconds 40          等更久（慢机器 / 大盘首启）
  ... -DryRun                  只解析并打印将要启动的文件，不真启动（验收用）

退出码：0 = 已监听（新起或本来就在）；1 = 起了但端口没监听；2 = 找不到可用的启动器/可执行文件，
        或 -Target 不是可用 PE（非 MZ / ARM64 等）
#>
[CmdletBinding()]
param(
    [string]$ToolRoot = '',
    [ValidateSet('x64', 'x32')][string]$Arch = 'x64',
    [int]$Port = 0,
    [int]$WaitSeconds = 30,
    [switch]$DryRun,
    [switch]$SkipProbe,
    [string]$ExactToolRoot = '',
    # ★ 按目标自动选架构：给一个 PE 路径，脚本自己读 Machine 字段决定 x64/x32 与端口。
    #   根因（2026-10-18 实测）：把 32 位 PE 送进 x64dbg 只会弹「请您用 x32dbg 来调试这个程序」，
    #   LoadBinary 永远 NO_TARGET，而错误里不写"架构不匹配" —— 极易误判成 MCP 坏了。
    #   靠人记着传 -Arch x32 不可靠，所以这里把判断做成默认行为。
    [string]$Target = ''
)

$ErrorActionPreference = 'Continue'
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }   # scan-ok: 控制台编码设置失败只影响中文显示，不影响启动/监听判定

# --- 目标位数探测（只在用户没显式指定 -Arch 时生效，显式指定永远优先）---
$archFromTarget = ''
if ($Target -and -not $PSBoundParameters.ContainsKey('Arch')) {
    if (-not (Test-Path -LiteralPath $Target)) {
        Write-Host ("ERROR: -Target 不存在: {0}" -f $Target) -ForegroundColor Red
        exit 2
    }
    try {
        $fs = [System.IO.File]::OpenRead((Resolve-Path -LiteralPath $Target).Path)
        try {
            $br = New-Object System.IO.BinaryReader($fs)
            $mz = $br.ReadBytes(2)
            if ($mz[0] -ne 0x4D -or $mz[1] -ne 0x5A) {
                Write-Host ("ERROR: -Target 不是 PE/MZ 文件: {0}" -f $Target) -ForegroundColor Red
                exit 2
            }
            $fs.Position = 0x3C
            $lfanew = $br.ReadInt32()
            $fs.Position = $lfanew + 4
            $machine = $br.ReadUInt16()
            $archFromTarget = switch ($machine) {
                0x014c { 'x32' }   # IMAGE_FILE_MACHINE_I386
                0x8664 { 'x64' }   # IMAGE_FILE_MACHINE_AMD64
                default { '' }
            }
            Write-Host ("target arch probe: {0} -> Machine=0x{1:X4} -> {2}" -f `
                (Split-Path -Leaf $Target), $machine, $(if ($archFromTarget) { $archFromTarget } else { 'unsupported' }))
            if (-not $archFromTarget) {
                Write-Host ("ERROR: Machine=0x{0:X4} 既不是 i386 也不是 AMD64，x64dbg/x32dbg 都不适用（ARM64 目标请走其它调试器）" -f $machine) -ForegroundColor Red
                exit 2
            }
        }
        finally { $fs.Dispose() }
    }
    catch {
        Write-Host ("ERROR: 读 PE 头失败: {0}" -f $_.Exception.Message) -ForegroundColor Red
        exit 2
    }
    $Arch = $archFromTarget
}

if ($Port -le 0) { $Port = if ($Arch -eq 'x32') { 9095 } else { 9094 } }
$name = if ($Arch -eq 'x32') { 'x32dbg' } else { 'x64dbg' }
$guiExe = if ($Arch -eq 'x32') { 'x32dbg.exe' } else { 'x64dbg.exe' }

function Test-Listening([int]$p) {
    return $null -ne (Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue)
}

if (Test-Listening $Port) {
    Write-Host ("{0} MCP already listening on {1}" -f $name, $Port)
    exit 0
}

# --- 工具根：环境变量优先，约定值兜底（与全仓一致，不写死）---
$roots = New-Object System.Collections.Generic.List[string]
if ($ExactToolRoot) {
    # 只用这一个根（验收/排查用：模拟"换到一台只有这个工具根的机器"）
    [void]$roots.Add($ExactToolRoot)
}
else {
    if ($ToolRoot) { [void]$roots.Add($ToolRoot) }
    if ($env:REVERSE_TOOL_ROOT) { [void]$roots.Add($env:REVERSE_TOOL_ROOT) }
    [void]$roots.Add('D:\Tools')
}

# --- ① 兼容层：本机工具根里的幂等启动器（有就先用它，行为已被实测验证）---
$legacy = $null
foreach ($r in $roots) {
    if (-not $r) { continue }
    $cand = Join-Path $r ('cli\start-' + $name + '-mcp.ps1')
    if (Test-Path -LiteralPath $cand) { $legacy = $cand; break }
}

$exe = $null
$via = ''

# --- ② 探测层 ---
if (-not $legacy -and -not $SkipProbe) {
    $bs = Join-Path $PSScriptRoot '..\..\scripts\lib\Bootstrap.ps1'
    if (Test-Path -LiteralPath $bs) {
        try {
            . (Resolve-Path -LiteralPath $bs).Path
            $spec = Resolve-ReverseToolSpec -Name $name -ErrorAction SilentlyContinue
            if ($spec -and $spec.Available -and $spec.Command) {
                $cmd = [string]$spec.Command
                if ($cmd -match '\.(ps1|cmd|bat)$') {
                    $legacy = $cmd          # 探测层给的是启动器 → 转调
                }
                else {
                    $exe = $cmd
                    $via = 'probe:' + ([string]$spec.Via)
                }
            }
        }
        catch { }   # scan-ok: 逐个候选 exe 探测，单个失败就试下一个；全都不行时上面/下面有 exit 2 报错（不静默成功）
    }
}

# --- ③ 工具根内常见布局扫描（先 headless 后 GUI：显式走一遍归一，避免"扫描顺手给了个 GUI 名"掩盖归一失效）---
if (-not $legacy -and -not $exe) {
    $relCands = if ($Arch -eq 'x32') {
        @('disasm\x64dbg\release\x32\headless.exe', 'disasm\x64dbg\release\x32\x32dbg.exe')
    }
    else {
        @('disasm\x64dbg\release\x64\headless.exe', 'disasm\x64dbg\release\x64\x64dbg.exe')
    }
    foreach ($rc in $relCands) {
        foreach ($r in $roots) {
            if (-not $r) { continue }
            $cand = Join-Path $r $rc
            if (Test-Path -LiteralPath $cand) { $exe = $cand; $via = 'tool-root-scan'; break }
        }
        if ($exe) { break }
    }
}

# --- headless → GUI 归一：插件只在 GUI 进程里加载，headless 永远等不到 9094/9095 ---
if ($exe -and ($exe -match 'headless\.exe$')) {
    $gui = Join-Path (Split-Path -Parent $exe) $guiExe
    if (Test-Path -LiteralPath $gui) {
        Write-Host ("note: 归一 {0} → GUI {1}（headless 不加载 MCP 插件）" -f (Split-Path -Leaf $exe), $guiExe) -ForegroundColor DarkGray
        $exe = $gui
        $via = $via + '→gui'
    }
    else {
        Write-Host ("ERROR: 只找到 headless（{0}）—— x64dbg-MCP 是**活在被调试进程里的插件**，" -f $exe) -ForegroundColor Red
        Write-Host '       没有独立服务进程；headless 不加载插件，9094/9095 永远不会监听。' -ForegroundColor Red
        Write-Host ("       同目录也没有 {0}。要动态调试请装 GUI 版，或把工具根指对。" -f $guiExe) -ForegroundColor Yellow
        Write-Host '       （headless 仍可用于一次性批处理，但它不是本脚本的目标形态。）' -ForegroundColor DarkGray
        exit 2
    }
}

if (-not $legacy -and -not $exe) {
    Write-Host ("ERROR: 找不到 {0} 的可用启动方式（探测层 / 工具根扫描都没命中）。" -f $name) -ForegroundColor Red
    Write-Host '  · 确认工具根：$env:REVERSE_TOOL_ROOT，或本脚本 -ToolRoot <路径>' -ForegroundColor Yellow
    Write-Host ("  · 确认已安装：<工具根>\disasm\x64dbg\release\{0}\{1} 是否存在" -f $Arch, $guiExe) -ForegroundColor Yellow
    exit 2
}

if ($DryRun) {
    Write-Host ("DRYRUN target = {0}" -f ($(if ($legacy) { $legacy } else { $exe })))
    Write-Host ("DRYRUN via    = {0}" -f ($(if ($legacy) { 'legacy-launcher' } else { $via })))
    Write-Host ("DRYRUN port   = {0}" -f $Port)
    exit 0
}

if ($legacy) {
    Write-Host ("starting {0} via {1}" -f $name, $legacy)
    # ★ 2026-10-16（D4 复核 → 有意，scan-ok）：这里**故意**不判 $LASTEXITCODE。
    #   理由：紧随其后的 Test-Listening $Port 是**功能性**判据，比退出码更强 ——
    #   启动器 rc≠0 也好、跑完但没起服务也好，都会落到下面的 exit 2。
    #   补一次 rc 检查只是把同一件事说两遍，还会让"启动器自己吞了错"更难看出。
    & $legacy -Port $Port -WaitSeconds $WaitSeconds   # scan-ok: 紧随其后的 Test-Listening 是**功能性**判据（比退出码更强）：rc≠0 或"跑完但没起服务"都会落到下面的 exit 2
    if (Test-Listening $Port) { Write-Host ("LISTEN on {0}" -f $Port) -ForegroundColor Green; exit 0 }
    Write-Host ("ERROR: {0} 秒内 {1} 未监听。" -f $WaitSeconds, $Port) -ForegroundColor Red
    exit 2
}

Write-Host ("starting {0} detached via {1} ..." -f $name, $via)
# ★ 必须脱离：Start-Process / & 会把子进程生命周期绑在这个 shell 上，shell 一退 x64dbg 就死。
Invoke-CimMethod -ClassName Win32_Process -MethodName Create `
    -Arguments @{ CommandLine = "`"$exe`"" } | Out-Null

for ($i = 0; $i -lt $WaitSeconds; $i++) {
    if (Test-Listening $Port) { Write-Host ("LISTEN on {0}" -f $Port) -ForegroundColor Green; exit 0 }
    Start-Sleep -Seconds 1
}
Write-Host ("WARNING: 已启动 {0}，但 {1} 秒内端口 {2} 未监听。" -f $name, $WaitSeconds, $Port) -ForegroundColor Yellow
Write-Host '         检查 x64dbg 窗口上是否停了模态错误框（插件没加载也会这样）。' -ForegroundColor Yellow
exit 1
