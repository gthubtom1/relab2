#Requires -Version 5.1
<#
.SYNOPSIS
    新机逆向环境一键建设 —— 《环境建设.md》的可执行版。

.DESCRIPTION
    一条命令把空机器建到「能做完整 EXE 逆向」的状态：探测 → 安装 → 登记 → 验收 → 攒 blocker。
    设计约束直接来自《环境建设.md》§0.2 / §2.5.1：

      · 幂等        每项装之前先探测（winget list / 四级探测层），装过的跳过
      · 零打断      只有四类阻塞（商业许可 / 账号登录 / 需要管理员而没有 / 两条路都不通）
                    才进 $script:blockers，其余一律自己决定并继续
      · 失败不中断  每步 try/catch，记失败继续下一个
      · PATH 刷新   每次 winget 装完立刻刷当前进程 $env:Path，否则得到假 MISSING（§2.5.1 ④）
      · 真验收      §5 门 1-4 真实执行，判据外部可观测（造真样本埋唯一标记）

.PARAMETER DryRun
    只打印将要做什么，不执行任何安装 / 下载 / 写注册表。

.PARAMETER VerifyOnly
    只跑 §5 的验收门 1-4，不做任何建设动作。

.PARAMETER SkipCommercial
    跳过 IDA / JEB / Binary Ninja / relab-tools（商业或需登录的部分）。

.PARAMETER ToolRoot
    工具根目录。默认 D:\Tools；不存在时按 §2.5.3 换到实际盘符。

.PARAMETER VenvPath
    pip 生态独立虚拟环境路径，默认 <ToolRoot>\runtime\python-venv（§4.3，绝不污染系统 Python）。

.PARAMETER NoDownload
    跳过 GitHub releases 直装环节（只装 winget 能覆盖的 + 已就位的）。
    联网受限 / 内网机用。

.PARAMETER KeepWork
    保留 $env:TEMP\setup-env 工作目录（默认验收跑完清掉）。

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File .\setup-env.ps1

.EXAMPLE
    .\setup-env.ps1 -DryRun        # 先看它打算干什么
    .\setup-env.ps1 -VerifyOnly   # 只跑验收门

.NOTES
    本文件必须保存为 **UTF-8 带 BOM**。PS 5.1 在 936 码页下读无 BOM 的 UTF-8 .ps1 会
    把中文读成乱码且**静默出错**（§2.5.1 ②）。用 write 工具落盘后请确认首字节是 EF BB BF。
#>
[CmdletBinding()]
param(
    [switch] $DryRun,
    [switch] $VerifyOnly,
    [switch] $SkipCommercial,
    [string] $ToolRoot      = '',
    [string] $VenvPath      = '',
    [switch] $NoDownload,
    [switch] $KeepWork
)
# ★ PSModulePath 自愈（2026-10-10 注入）：剔除 WindowsApps 版 PowerShell 7 的模块目录，否则 PS 5.1 会因 TypeData 重复定义失败而使 Get-FileHash / Get-ExecutionPolicy 不可用（已造成两次假绿 + 一次失败被吞）。模块本体见 skillpack\skills\scripts\lib\PsModulePathInit.ps1
# ★ 2026-10-10 去掉硬编码 `<仓根>\...` 绝对路径。
#   原来无条件 dot-source 固定路径：仓库 clone 到别处时它静默失效 ——
#   错误写到 stderr，但 $ErrorActionPreference 在后面才设，主流程照跑，
#   于是「PSModulePath 自愈」悄悄没了，只留一屏红字。
#   现在按本文件位置逐级上溯，找到含 skillpack/skills/scripts/lib/ 的仓根为止。
#   三个变量包在函数里：函数体内的赋值天然是局部的，出了函数就没了。
#   这一点很重要 —— README/START-HERE/TOOL-CHAIN 都教用户 dot-source 这些脚本
#   进交互会话，不隔离的话 $__psmpDir 等会落进用户的全局会话并覆盖同名变量
#   （2026-10-10 实测复现）。
function Resolve-Relab2PsModulePathInit {
    $dir = $PSScriptRoot
    if (-not $dir) { $dir = Split-Path -Parent $MyInvocation.MyCommand.Path }
    while ($dir) {
        $init = Join-Path $dir 'skillpack\skills\scripts\lib\PsModulePathInit.ps1'
        if (Test-Path -LiteralPath $init) { return $init }
        $parent = Split-Path -Parent $dir
        if (-not $parent -or $parent -eq $dir) { break }
        $dir = $parent
    }
    return $null
}
$__psmpInit = Resolve-Relab2PsModulePathInit
if ($__psmpInit) { . $__psmpInit }
Remove-Variable -Name __psmpInit -ErrorAction SilentlyContinue
Remove-Variable -Name Resolve-Relab2PsModulePathInit -ErrorAction SilentlyContinue
# ═════════════════════════════════════════════════════════════════════════════
# ★ 2026-10-10 修正：ToolRoot 此前**只从 -ToolRoot 参数取**，从不读环境变量
#   $env:REVERSE_TOOL_ROOT。而 环境初始化.md §2 教用户设置的正是那个环境变量，
#   setup-env.ps1 自身的 .NOTES 与 §4.5 也把「写 User 级 REVERSE_TOOL_ROOT」
#   当作登记动作 —— 文档与实现脱节，导致换机时验收门在**错的工具根**上判绿。
#   实测：设 $env:REVERSE_TOOL_ROOT='E:\fresh' 跑 -VerifyOnly，
#   §5 门2 仍 8/8 全 PASS，末尾还打印「工具根: D:\Tools」，全程不提示不符。
#   优先级：显式参数 > 环境变量 > 默认探测。
# ═════════════════════════════════════════════════════════════════════════════
if (-not $ToolRoot -and $env:REVERSE_TOOL_ROOT) {
    $ToolRoot = $env:REVERSE_TOOL_ROOT
    $script:ToolRootSource = '环境变量 REVERSE_TOOL_ROOT'
} elseif ($ToolRoot) {
    $script:ToolRootSource = '命令行参数 -ToolRoot'
} else {
    $script:ToolRootSource = '默认探测'
}

# ═════════════════════════════════════════════════════════════════════════════
# §2.5.1 ③ 切 UTF-8 码页 —— 否则中文输出全是乱码，会被误判成「命令失败」
# ═════════════════════════════════════════════════════════════════════════════
try { chcp 65001 > $null } catch { }
try {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    $OutputEncoding           = [System.Text.Encoding]::UTF8
} catch { }

$ErrorActionPreference = 'Continue'   # 任何单步失败都不许冲出脚本（§0.1 少停止）
$ProgressPreference    = 'SilentlyContinue'

# ═════════════════════════════════════════════════════════════════════════════
# 状态容器
# ═════════════════════════════════════════════════════════════════════════════
$script:Blockers   = New-Object System.Collections.Generic.List[object]
$script:Actions    = New-Object System.Collections.Generic.List[object]   # 干过什么（含跳过）
$script:Findings   = New-Object System.Collections.Generic.List[object]   # 探测到的现状
$script:GateResults = New-Object System.Collections.Generic.List[object]   # 验收门结果
$script:Started    = Get-Date

function Write-Step  ([string]$m) { Write-Host "==> $m" -ForegroundColor Cyan }
function Write-Act  ([string]$m) { Write-Host "  -> $m" -ForegroundColor Yellow }
function Write-Done ([string]$m) { Write-Host "  [OK] $m" -ForegroundColor Green }
function Write-Skip ([string]$m) { Write-Host "  [--] $m" -ForegroundColor DarkGray }
function Write-Warn2([string]$m) { Write-Host "  [!!] $m" -ForegroundColor Yellow }
function Write-Err  ([string]$m) { Write-Host "  [XX] $m" -ForegroundColor Red }
function Write-Dry  ([string]$m) { Write-Host "  (dry) $m" -ForegroundColor DarkCyan }

function Note-Blocker {
    param(
        [Parameter(Mandatory=$true)][string]$Category,   # 商业许可 / 账号登录 / 管理员 / 两条路都不通
        [Parameter(Mandatory=$true)][string]$Item,
        [Parameter(Mandatory=$true)][string]$Detail,
        [string]$Action = ''
    )
    if (-not $Action) {
        switch ($Category) {
            '商业许可'   { $Action = '需要你提供真实 license 文件（.hexlic / ida.key），AI 无权购买' }
            '账号登录'   { $Action = '需要你先完成 gh auth login / 提供 API key' }
            '管理员'     { $Action = '需要在管理员会话里重跑本脚本（或手动执行给出的命令）' }
            default      { $Action = '需要你指定走哪条路（两条自动路径都已失败）' }
        }
    }
    $script:Blockers.Add([pscustomobject]@{
        类别 = $Category
        事项 = $Item
        详情 = $Detail
        建议动作 = $Action
    })
    Write-Warn2 "阻塞[$Category] $Item —— 已记下，继续干别的"
}

function Add-Action {
    param([string]$Step,[string]$Item,[string]$Result)
    $script:Actions.Add([pscustomobject]@{ 阶段=$Step; 项目=$Item; 结果=$Result })
}

function Add-Finding {
    param([string]$Key,[string]$Value)
    $script:Findings.Add([pscustomobject]@{ 项=$Key; 值=$Value })
}

# ── §2.5.1 ④ 改完 PATH 当前进程不刷新 ───────────────────────────────────────────
function Update-Path {
    try {
        $m = [Environment]::GetEnvironmentVariable('PATH','Machine')
        $u = [Environment]::GetEnvironmentVariable('PATH','User')
        if ($m -and $u) { $env:Path = "$m;$u" }
        elseif ($m)      { $env:Path = $m }
        elseif ($u)      { $env:Path = $u }
    } catch { }
}

# ── 有没有这个命令 ─────────────────────────────────────────────────────────────
function Test-Command { param([string]$Name) [bool](Get-Command $Name -ErrorAction SilentlyContinue) }

# ── 全盘探 exe（Everything 优先，退回慢速）─────────────────────────────────────
$script:EsExe = $null
function Find-Exe {
    param([string]$Name, [int]$Max = 3)
    if (-not $script:EsExe) {
        $c = Get-Command 'es.exe' -ErrorAction SilentlyContinue
        if ($c) { $script:EsExe = $c.Source }
    }
    if ($script:EsExe) {
        try {
            $hits = & $script:EsExe -n $Max $Name 2>$null
            if ($hits) { return @($hits) }
        } catch { }
    }
    return @()
}

# ── 探测层：<ToolRoot> 下按已知目录搜 exe ──────────────────────────────────────
function Find-ToolExe {
    param([string]$RelativeExe, [string]$Root = '')
    if (-not $Root) { $Root = $script:ToolRoot }
    if (-not $Root) { return $null }
    $p = Join-Path $Root $RelativeExe
    if (Test-Path -LiteralPath $p -PathType Leaf -ErrorAction SilentlyContinue) { return $p }
    return $null
}

# ── shell 内建命令名 -> 真实可执行文件 ────────────────────────────────────────
# Get-Command 对 cmd 内建命令（curl、where、find）返回的是 .exe 本体，
# 直接拿 .Source 去 Start-Process 会报「不是有效的 Win32 应用程序」。
$script:ShellAliasMap = @{
    'curl'   = "$env:SystemRoot\System32\curl.exe"
    'where'  = "$env:SystemRoot\System32\where.exe"
    'find'   = "$env:SystemRoot\System32\find.exe"
    'sort'   = "$env:SystemRoot\System32\sort.exe"
    'more'   = "$env:SystemRoot\System32\more.com"
    'winget' = "$env:LOCALAPPDATA\Microsoft\WindowsApps\winget.exe"
}

function Resolve-ExePath {
    <#
      给一个可能是 exe / bat / cmd / shell 内建别名的名字，
      返回能直接交给 Start-Process / & 的真身路径；找不到返回 $null。
    #>
    param([string]$Name)
    if ([string]::IsNullOrWhiteSpace($Name)) { return $null }
    if (Test-Path -LiteralPath $Name -PathType Leaf -ErrorAction SilentlyContinue) { return $Name }
    $key = [IO.Path]::GetFileNameWithoutExtension($Name).ToLowerInvariant()
    if ($script:ShellAliasMap.ContainsKey($key)) {
        $cand = $script:ShellAliasMap[$key]
        if (Test-Path -LiteralPath $cand -PathType Leaf -ErrorAction SilentlyContinue) { return $cand }
    }
    $c = Get-Command $Name -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($c -and $c.Source -and (Test-Path -LiteralPath $c.Source -PathType Leaf -ErrorAction SilentlyContinue)) {
        return $c.Source
    }
    return $null
}

# ── winget：装一个包。返回 'installed' / 'already' / 'failed' ─────────────────
# ★ 必须带 --accept-source-agreements --accept-package-agreements --disable-interactivity，
#   否则 winget 首次运行会停在交互协议界面把无人值守会话卡死（§3.3）。
# ★ 只用 --source winget：msstore 源在很多机器上会弹协议窗口。
function Install-WingetPkg {
    param([string]$Id, [switch]$Quiet)
    $winget = Resolve-ExePath 'winget'
    if (-not $winget) {
        Write-Err "$Id : winget 不存在，无法用 winget 装"
        return 'failed'
    }
    if ($DryRun) { Write-Dry "winget install --source winget -e --id $Id"; return 'dryrun' }

    if (-not $Quiet) { Write-Act "正在装 $Id ..." }
    try {
        $out = & $winget install --source winget `
                  --accept-source-agreements --accept-package-agreements `
                  --disable-interactivity -e --id $Id 2>&1
        $code = $LASTEXITCODE
    } catch {
        Write-Err "$Id : winget 调用异常 $($_.Exception.Message)"
        return 'failed'
    }
    # winget 的退出码在「已是最新」时也是非 0，必须看输出文本而不是只看 rc
    $txt = ($out | ForEach-Object { [string]$_ }) -join "`n"
    if ($txt -match '已安装的现有包|already installed|No available upgrade|没有可用的升级|已为.*安装') {
        if (-not $Quiet) { Write-Skip "$Id 已装（winget 报：已是现有包/无升级）" }
        return 'already'
    }
    if ($code -eq 0) {
        Update-Path
        if (-not $Quiet) { Write-Done "$Id 安装完成" }
        return 'installed'
    }
    Write-Err "$Id winget rc=$code"
    # ★ 不要吞输出：失败原因全在 stderr 里（源不可达 / 需 UAC / 包名错）
    ($out | Select-Object -Last 4) | ForEach-Object { Write-Host "      $_" -ForegroundColor DarkRed }
    return 'failed'
}

# ── 从 GitHub releases 下载单个 asset ─────────────────────────────────────────
# 先走 API（拿最新版本 + asset 名），403（无 UA / 限流）时回退构造 URL。
function Get-GitHubAssetUrl {
    param([string]$Repo, [string]$Pattern, [string]$FallbackUrl = '')
    try {
        $api = "https://api.github.com/repos/$Repo/releases/latest"
        $r = Invoke-RestMethod -Uri $api -Headers @{ 'User-Agent' = 'setup-env'; 'Accept' = 'application/vnd.github+json' } -TimeoutSec 30
        $asset = $r.assets | Where-Object { $_.name -match $Pattern } | Select-Object -First 1
        if ($asset) { return $asset.browser_download_url }
    } catch { }
    if ($FallbackUrl) { return $FallbackUrl }
    return $null
}

function Install-GitHubAsset {
    param(
        [Parameter(Mandatory=$true)][string]$Repo,
        [Parameter(Mandatory=$true)][string]$Pattern,
        [Parameter(Mandatory=$true)][string]$DestDir,
        [Parameter(Mandatory=$true)][string]$ExeRelPath,   # 相对 DestDir 的落地 exe（用于验真）
        [string]$FallbackUrl = ''
    )
    $dest = Join-Path $DestDir $ExeRelPath
    if (Test-Path -LiteralPath $dest -PathType Leaf -ErrorAction SilentlyContinue) {
        Write-Skip "$Repo\$Pattern 已就位 -> $dest"
        Add-Action '工具链' "$Repo/$Pattern" '跳过（已存在）'
        return 'already'
    }
    if ($NoDownload) { Write-Skip "$Repo\$Pattern 因 -NoDownload 跳过"; return 'skipped' }
    if ($DryRun)     { Write-Dry "下载 $Repo/$Pattern -> $dest";           return 'dryrun' }

    Write-Act "下载 $Repo/$Pattern ..."
    try {
        $url = Get-GitHubAssetUrl -Repo $Repo -Pattern $Pattern -FallbackUrl $FallbackUrl
        if (-not $url) { Write-Err "$Repo : 拿不到下载地址（API 403 且无 fallback）"; return 'failed' }
        New-Item -ItemType Directory -Force -Path $DestDir | Out-Null
        $tmp = Join-Path $env:TEMP ("setupenv-" + [IO.Path]::GetFileName($url))
        # 用 curl 不用 Invoke-WebRequest：PowerShell 5.1 的 IWR 下载大文件会卡在半路
        # ★ 必须显式取 System32\curl.exe：Get-Command 'curl' 在 PS 里会给出 curl.exe 本体，
        #   但在某些环境会解析到 cmd 内建别名，Start-Process 直接吃那个会报
        #   「不是有效的 Win32 应用程序」（本机实测过）
        $curl = Resolve-ExePath 'curl'
        if ($curl) { & $curl -L --fail --retry 2 -o $tmp $url }
        else       { Invoke-WebRequest -Uri $url -OutFile $tmp -UseBasicParsing -TimeoutSec 900 }
        if (-not (Test-Path $tmp) -or (Get-Item $tmp).Length -lt 1024) {
            Write-Err "$Repo : 下载物异常小或为空"
            return 'failed'
        }
        Add-Action '工具链' "$Repo/$Pattern" "已下载 $((Get-Item $tmp).Length) B"
        Write-Done "$Repo/$Pattern 下载完成（$((Get-Item $tmp).Length) B）"
        return $tmp     # 返回临时包路径，交给调用方解压
    } catch {
        Write-Err "$Repo 下载失败: $($_.Exception.Message)"
        return 'failed'
    }
}

# ── 解压 zip 到目录（7z 优先，其次 Expand-Archive）─────────────────────────────
function Expand-Package {
    param([string]$Path, [string]$DestDir)
    if (-not $Path -or $Path -eq 'failed') { return $false }
    if (-not (Test-Path $Path)) { return $false }
    try {
        New-Item -ItemType Directory -Force -Path $DestDir | Out-Null
        $sz = Get-Command '7z.exe' -ErrorAction SilentlyContinue
        if (-not $sz) { $sz = Find-ToolExe '7-Zip\7z.exe' }
        if ($sz) {
            $sevenz = if ($sz.Source) { $sz.Source } else { $sz }
            & $sevenz x $Path "-o$DestDir" -y | Out-Null
        } else {
            Expand-Archive -LiteralPath $Path -DestinationPath $DestDir -Force
        }
        Update-Path
        return $true
    } catch {
        Write-Err "解压失败: $($_.Exception.Message)"
        return $false
    }
}

function Invoke-Check {
    <#
      实跑一次看真实输出。绝不用「Available=True」当通过判据（§0.3 反例第一条）。

      参数名刻意用 $ArgList 而不是 $Args：$args 是 PowerShell 的自动变量，
      在 param 块里声明 [string[]]$Args 拿到的是「未声明的实参」，实跑直接变成 0 参数。

      返回 @{ Code = <退出码，异常时 -1>; Out = <合并输出文本> }；文件不存在返回 $null
    #>
    param(
        [Parameter(Mandatory=$true)][string]$Exe,
        [string[]]$ArgList = @(),
        [int]$TimeoutSec = 60,
        [string]$Redirect = ''
    )
    if (-not (Test-Path -LiteralPath $Exe)) { return $null }
    $argList = @($ArgList | Where-Object { $null -ne $_ -and $_ -ne '' })
    try {
        if ($Redirect) {
            # ★ 调 .bat/.cmd 不能用 cmd /c 拼引号（§6.3），交给 Start-Process 自己加引号。
            # ★ 而且参数为空时必须**整个省掉** -ArgumentList：PS 5.1 的 Start-Process
            #   对空数组会直接抛「参数为 Null 或空」（ParameterArgumentValidationException），
            #   整个 Invoke-Check 被 catch 掉返回 Code=-1，文件一个都不建 —— 表现成
            #   「脱壳样本跑不起来」，其实是根本没启动（本机实测踩过）。
            $sp = @{ FilePath = $Exe; NoNewWindow = $true; Wait = $true; PassThru = $true
                     RedirectStandardOutput = $Redirect; RedirectStandardError = "$Redirect.err" }
            if ($argList.Count -gt 0) { $sp['ArgumentList'] = $argList }
            $p = Start-Process @sp
            return @{ Code = $p.ExitCode; Out = '' }
        }
        $out = & $Exe @argList 2>&1
        return @{ Code = $LASTEXITCODE; Out = (($out | ForEach-Object { [string]$_ }) -join "`n") }
    } catch {
        return @{ Code = -1; Out = $_.Exception.Message }
    }
}

# ═════════════════════════════════════════════════════════════════════════════
# §2.5.2 系统摸底
# ═════════════════════════════════════════════════════════════════════════════
function Invoke-Survey {
    Write-Step '§2.5.2 系统摸底'

    Add-Finding '操作系统'   ([Environment]::OSVersion.VersionString)
    Add-Finding 'PS 版本'    $PSVersionTable.PSVersion.ToString()
    Add-Finding 'pwsh 7'     $(if (Test-Command 'pwsh') { '有 -> ' + (Get-Command pwsh).Source } else { '缺（§3.1 优先补装）' })
    Add-Finding 'ACP 码页'   ([System.Text.Encoding]::Default.CodePage)
    Add-Finding '脚本BOM'    $(if ((Get-Content -LiteralPath $PSCommandPath -Encoding Byte -TotalCount 3 -ErrorAction SilentlyContinue) -join ',' -eq '239,187,191') { 'UTF-8 BOM ✓' } else { '★ 无 BOM —— PS 5.1 下会静默乱码（§2.5.1 ②）' })

    $id  = [Security.Principal.WindowsIdentity]::GetCurrent()
    $pr  = New-Object Security.Principal.WindowsPrincipal($id)
    $isAdmin = $pr.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    Add-Finding '管理员权限' $(if ($isAdmin) { 'True' } else { 'False' })
    $script:IsAdmin = $isAdmin

    $drives = Get-PSDrive -PSProvider FileSystem |
              Select-Object Name, @{ n='FreeGB'; e={ [math]::Round($_.Free/1GB,1) } }
    foreach ($d in $drives) { Add-Finding ("磁盘 {0} 空闲" -f $d.Name) ("{0} GB" -f $d.FreeGB) }
    $free = ($drives | Measure-Object -Property FreeGB -Sum).Sum
    Add-Finding '空闲合计' ("{0} GB" -f [math]::Round($free,1))
    if ($free -lt 30) {
        Note-Blocker '管理员' '磁盘空间' ("总空闲仅 {0} GB，低于 30 GB 门槛（§2.5.3）" -f [math]::Round($free,1)) `
                    '先清理磁盘再继续，否则 Ghidra/SDK 类大包会装到一半失败'
    }

    foreach ($c in 'winget','choco','scoop','git','gh','curl','gcc') {
        $g = Get-Command $c -ErrorAction SilentlyContinue
        Add-Finding "命令 $c" $(if ($g) { $g.Source } else { '缺' })
    }
    if (-not (Test-Command 'winget')) {
        Note-Blocker '两条路都不通' 'winget' 'winget 不存在，§3.3 批量装无法执行（§2.5.3）' `
                    '安装 App Installer（Microsoft Store 搜 App Installer），或改用 GitHub releases 直装'
    }

    foreach ($c in 'python','git','node','dotnet','java','7z','go','pwsh','es','tshark') {
        $g = Get-Command $c -ErrorAction SilentlyContinue
        Add-Finding "运行时 $c" $(if ($g) { $g.Source } else { '缺' })
    }

    # Everything 服务（§2.6）
    $svc = Get-Service 'Everything' -ErrorAction SilentlyContinue
    Add-Finding 'Everything 服务' $(if ($svc) { "$($svc.Status) / $($svc.StartType)" } else { '无服务' })

    # Npcap（§3.1，需管理员）
    $np = Get-Service 'npcap' -ErrorAction SilentlyContinue
    Add-Finding 'Npcap 服务' $(if ($np) { "$($np.Status) / $($np.StartType)" } else { '无服务' })

    Write-Act "摸底完成：管理员=$isAdmin，ACP=$([System.Text.Encoding]::Default.CodePage)，空闲 $([math]::Round($free,1)) GB"

    # 把 cdb alias 状态记进摸底（§6.2：只能走 alias，绝不加进 PATH）
    foreach ($a in 'cdbX64','cdbX86') {
        $p = Join-Path $env:LOCALAPPDATA "Microsoft\WindowsApps\$a.exe"
        Add-Finding "cdb alias $a" $(if (Test-Path $p) { $p } else { '缺' })
    }
    if ($env:Path -match 'WindowsApps\\cdb') {
        Write-Warn2 'PATH 里出现了 cdb —— §6.2：加了会「查得到但跑不了」，比没有更糟'
    }
}

# ═════════════════════════════════════════════════════════════════════════════
# §2.7 全盘扫已装（防重复安装 + 抓同名遮蔽）
# ═════════════════════════════════════════════════════════════════════════════
$script:ProbeList = @(
    # 运行时
    'python.exe','git.exe','node.exe','dotnet.exe','java.exe','7z.exe','go.exe','gcc.exe',
    # PowerShell 7（★ 新装系统经常没有）
    'pwsh.exe',
    # 搜索基础设施
    'es.exe',
    # 逆向工具（注意 GUI 孪生的 CLI 版）
    'diec.exe','upx.exe','r2.exe','analyzeHeadless.bat','x64dbg.exe','headless.exe',
    'cdbX64.exe','idat.exe','ida.exe','floss.exe','floss.cmd','capa.exe','capa.bat',
    'pe-sieve64.exe','InjectorCLIx64.exe','yara64.exe','tshark.exe','gh.exe',
    'ilspycmd.exe','de4dot.exe','jadx.bat','apktool.bat','adb.exe','binwalk.exe'
)

function Invoke-FullDiskScan {
    Write-Step '§2.7 全盘扫已装'
    if (-not (Test-Command 'es.exe') -and -not $script:EsExe) {
        Write-Warn2 'es.exe 还没有，跳过全盘扫（§2.6：Everything 装完再扫才有意义）'
        Add-Action '摸底' '全盘扫已装' '跳过（Everything 未就位）'
        return
    }
    $found = 0
    foreach ($p in $script:ProbeList) {
        $hits = Find-Exe -Name $p -Max 2
        if ($hits -and $hits.Count -gt 0) {
            $found++
            Write-Host ("  [有] {0,-24} -> {1}" -f $p, ($hits -join ' | ')) -ForegroundColor DarkGreen
            Add-Finding "扫描 $p" ($hits -join ' | ')
        }
    }
    Write-Act "扫描完成：$found / $($script:ProbeList.Count) 项已存在"

    # 同名遮蔽排查（§2.7）：PATH 里抢先的那个可能是残包
    foreach ($c in 'python','capa','floss','r2') {
        $all = @(Get-Command $c -All -ErrorAction SilentlyContinue)
        if ($all.Count -gt 1) {
            Write-Warn2 ("同名遮蔽 {0}：{1} 个候选，PATH 抢先的是 {2}" -f $c, $all.Count, $all[0].Source)
            Add-Finding "遮蔽 $c" (($all | ForEach-Object { $_.Source }) -join ' | ')
        }
    }
    Add-Action '摸底' '全盘扫已装' "命中 $found 项"
}

# ═════════════════════════════════════════════════════════════════════════════
# §3.3 批量装基础运行时
# ═════════════════════════════════════════════════════════════════════════════
$script:Runtimes = @(
    @{ Id='Python.Python.3.12';  Cmd='python'; Note='angr/qiling 需要 3.12+' },
    @{ Id='Git.Git';             Cmd='git';    Note='TLS 栈在本机可能被切断，见 §6.1' },
    @{ Id='OpenJS.NodeJS.LTS';   Cmd='node';   Note='.NET/Anthropic MCP 生态' },
    @{ Id='Microsoft.DotNet.SDK.8'; Cmd='dotnet'; Note='ilspycmd 需要；注意 ilspycmd 必须锁 9.1.x' },
    @{ Id='Microsoft.OpenJDK.21';   Cmd='java';  Note='Ghidra / jadx / apktool 宿主' },
    @{ Id='7zip.7zip';           Cmd='7z';     Note='分卷 7z 解压' },
    @{ Id='GoLang.Go';           Cmd='go';     Note='go 1.21+' },
    @{ Id='Microsoft.PowerShell'; Cmd='pwsh';   Note='★ 新装系统常缺，本手册大量命令的宿主' },
    @{ Id='voidtools.Everything'; Cmd='es';    Note='§2.6 搜索基础设施，没有它后面全是龟速' },
    @{ Id='Microsoft.WinDbg';    Cmd='';       Note='★ 新装系统必缺；只有 app execution alias 能跑' },
    @{ Id='VirusTotal.YARA';     Cmd='yara';   Note='规则匹配引擎' },
    @{ Id='DieCrew.DIE';         Cmd='diec';   Note='查壳（注意探测的是 CLI 孪生 diec，不是 die）' }
)

function Install-BaseRuntimes {
    Write-Step '§3.3 批量装基础运行时（失败不中断，继续下一个）'
    foreach ($r in $script:Runtimes) {
        $id   = $r.Id
        $have = $false
        if ($r.Cmd) { $have = Test-Command $r.Cmd }
        if ($id -eq 'Microsoft.WinDbg') {
            $have = Test-Path (Join-Path $env:LOCALAPPDATA 'Microsoft\WindowsApps\cdbX64.exe')
        }

        if ($have) {
            Write-Skip "$id 已装（$($r.Note)）"
            Add-Action '基础运行时' $id '跳过（已装）'
            continue
        }
        if ($DryRun) { Write-Dry "装 $id —— $($r.Note)"; Add-Action '基础运行时' $id 'dryrun'; continue }

        $r1 = Install-WingetPkg -Id $id
        switch ($r1) {
            'installed' { Add-Action '基础运行时' $id '已安装' }
            'already'   { Add-Action '基础运行时' $id '跳过（winget 报已装）' }
            default     {
                Add-Action '基础运行时' $id '安装失败'
                # Npcap 是唯一明确「需管理员」的，单独记 blocker（§3.3）
                if ($id -eq 'Insecure.Npcap') {
                    if ($script:IsAdmin) { Note-Blocker '两条路都不通' 'Npcap' '管理员会话下仍装失败，需手动跑官方安装器' '手动执行 https://npcap.com/dist/npcap-1.x.exe' }
                }
            }
        }
        Update-Path   # ★ 装完任何东西先刷 PATH 再验证，否则假 MISSING（§2.5.1 ④）
    }

    # Npcap 单独处理：它不在上面列表里（§3.1 表里有，§3.3 批量列表里也有，但失败率高）
    if (-not (Get-Service 'npcap' -ErrorAction SilentlyContinue)) {
        $r2 = Install-WingetPkg -Id 'Insecure.Npcap'
        if ($r2 -eq 'installed' -or $r2 -eq 'already') { Add-Action '基础运行时' 'Insecure.Npcap' '已安装' }
        else {
            Add-Action '基础运行时' 'Insecure.Npcap' '安装失败'
            if ($script:IsAdmin) {
                Note-Blocker '两条路都不通' 'Npcap' '有管理员权限但 winget 仍失败' '手动执行 npcap.com 官方安装器'
            } else {
                Note-Blocker '管理员' 'Npcap' '抓包驱动需要管理员权限，当前会话没有' '在管理员会话重跑本脚本'
            }
        }
    } else {
        Write-Skip 'Insecure.Npcap 已装（服务在运行）'
        Add-Action '基础运行时' 'Insecure.Npcap' '跳过（服务已存在）'
    }

    # §3.1 统一验证：实跑版本命令
    foreach ($c in 'python','git','node','dotnet','java','7z','go','pwsh','es') {
        $g = Get-Command $c -ErrorAction SilentlyContinue
        if ($g) { Write-Host ("  [OK] {0,-8} -> {1}" -f $c, $g.Source) -ForegroundColor DarkGreen }
        else    { Write-Host ("  [缺] {0}" -f $c) -ForegroundColor DarkYellow }
    }
}

# ═════════════════════════════════════════════════════════════════════════════
# §4.1 逆向工具链
# ═════════════════════════════════════════════════════════════════════════════
function Install-ReverseTools {
    Write-Step '§4.1 逆向工具链（winget 覆盖不到的走 GitHub releases 直装）'
    Update-Path

    # 探测层（非 winget 部分才用）
    $boot = $null
    foreach ($c in @(
        (Join-Path $PSScriptRoot 'skillpack\skills\scripts\lib\Bootstrap.ps1'),
        (Join-Path $env:REVERSE_SKILL_ROOT 'skillpack\skills\scripts\lib\Bootstrap.ps1')
    )) {
        if ($c -and (Test-Path -LiteralPath $c -ErrorAction SilentlyContinue)) { $boot = $c; break }
    }
    $script:Boot = $boot
    if ($boot) { Write-Act "探测层: $boot" } else { Write-Warn2 '探测层未找到，本节改用工具根直查' }

    function Resolve-Tool {
        param([string]$Name, [string]$FallbackRel = '')
        if ($script:Boot) {
            try { . $script:Boot; $r = Resolve-ReverseToolSpec -Name $Name; if ($r -and $r.Available) { return $r.Command } } catch { }
        }
        if ($FallbackRel) { $p = Find-ToolExe $FallbackRel; if ($p) { return $p } }
        $c = Get-Command $Name -ErrorAction SilentlyContinue
        if ($c) { return $c.Source }
        return $null
    }

    # ── winget 能直接覆盖的 ─────────────────────────────────────────────────────
    $wg = @(
        @{ Id='VirusTotal.YARA'; Cmd='yara';   Fallback='yara\yara64.exe' },
        @{ Id='DieCrew.DIE';     Cmd='diec';   Fallback='DIE\diec.exe' }
    )
    foreach ($w in $wg) {
        $p = Resolve-Tool -Name $w.Cmd -FallbackRel $w.Fallback
        if ($p) { Write-Skip "$($w.Id) 已就位 -> $p"; Add-Action '工具链' $w.Id '跳过（已就位）' }
        else {
            $r = Install-WingetPkg -Id $w.Id -Quiet
            Add-Action '工具链' $w.Id $(if ($r -eq 'installed') { '已安装' } else { "失败($r)" })
        }
        Update-Path
    }

    # ── WinDbg（cdb）：只认 app execution alias ─────────────────────────────────
    $cdbAlias = Join-Path $env:LOCALAPPDATA 'Microsoft\WindowsApps\cdbX64.exe'
    if (Test-Path $cdbAlias) {
        Write-Skip "cdbX64 alias 已在 -> $cdbAlias"
        Add-Action '工具链' 'Microsoft.WinDbg' '跳过（alias 已存在）'
    } else {
        $r = Install-WingetPkg -Id 'Microsoft.WinDbg' -Quiet
        if ($r -ne 'installed' -and -not (Test-Path $cdbAlias)) {
            Write-Err 'WinDbg 装完仍无 cdbX64 alias —— MSIX 包可能未注册完成，注销重登后重跑本脚本'
            Add-Action '工具链' 'Microsoft.WinDbg' "失败($r)"
        } else {
            Add-Action '工具链' 'Microsoft.WinDbg' '已安装'
        }
    }

    # ── GitHub releases 直装 ───────────────────────────────────────────────────
    $assets = @(
        @{ Repo='upx/upx';                    Pattern='win64\.zip$';      Dest="$script:ToolRoot\UPX";       Exe='upx.exe' },
        @{ Repo='radareorg/radare2';           Pattern='w64\.zip$';        Dest="$script:ToolRoot\radare2";  Exe='bin\r2.exe' },
        @{ Repo='hasherezade/pe-sieve';        Pattern='pe-sieve64\.exe';  Dest="$script:ToolRoot\pe-sieve"; Exe='pe-sieve64.exe' },
        @{ Repo='winsiderss/scyllahide';       Pattern='\.zip$';          Dest="$script:ToolRoot\ScyllaHide"; Exe='InjectorCLIx64.exe' },
        @{ Repo='NationalSecurityAgency/ghidra'; Pattern='PUBLIC_.*\.zip$'; Dest="$script:ToolRoot\Ghidra";   Exe='support\analyzeHeadless.bat' }
    )
    foreach ($a in $assets) {
        $destExe = Join-Path $a.Dest $a.Exe
        if (Test-Path -LiteralPath $destExe -PathType Leaf -ErrorAction SilentlyContinue) {
            Write-Skip "$($a.Repo) 已就位 -> $destExe"
            Add-Action '工具链' $a.Repo '跳过（已就位）'
            continue
        }
        $pkg = Install-GitHubAsset -Repo $a.Repo -Pattern $a.Pattern -DestDir $a.Dest -ExeRelPath $a.Exe
        if ($pkg -eq 'dryrun')  { Add-Action '工具链' $a.Repo 'dryrun'; continue }
        if ($pkg -eq 'skipped' -or $pkg -eq 'failed') { Add-Action '工具链' $a.Repo '跳过/失败'; continue }
        if (Expand-Package -Path $pkg -DestDir $a.Dest) {
            if (Test-Path -LiteralPath $destExe -PathType Leaf -ErrorAction SilentlyContinue) {
                Write-Done "$($a.Repo) 就位 -> $destExe"
            } else {
                Write-Warn2 "$($a.Repo) 解压后没找到 $($a.Exe)（release 目录结构可能变了，需人工确认）"
            }
        }
        Remove-Item -LiteralPath $pkg -Force -ErrorAction SilentlyContinue
    }

    # ── x64dbg：★ 只能 GUI，agent 不得拉起；这里只登记文件在位 ────────────────
    $x64 = Resolve-Tool -Name 'x64dbg' -FallbackRel 'x64dbg\release\x64\x64dbg.exe'
    if ($x64) { Write-Skip "x64dbg 已就位 -> $x64"; Add-Action '工具链' 'x64dbg' '跳过（已就位）' }
    else {
        Write-Warn2 'x64dbg 未找到。GUI 工具需人工下载（§6.2：headless 是空壳，只能 GUI + MCP）'
        Add-Action '工具链' 'x64dbg' '需人工下载（GUI 工具）'
    }

    # ── capa：★ 官方 exe 被 Defender 误报隔离；不要换 PyPI 残包 ──────────────────
    Write-Step '§4.1 capa 特判（Defender 误报 / PyPI 残包）'
    $capaExe = Find-ToolExe 'capa\capa.exe'
    $capaBat = Find-ToolExe 'capa\capa.bat'
    $capaRules = Find-ToolExe 'capa\rules-flat'
    if ($capaExe -and -not $capaRules) {
        Write-Warn2 'capa.exe 在位但规则目录 rules-flat 不在 —— 多半是被 Defender 隔离后残留'
        Note-Blocker '两条路都不通' 'capa 规则集' 'exe 在位但缺 rules-flat：官方 exe 被 Defender 误报隔离，PyPI 版又是不含规则集的残包' `
                    '把 capa 目录加入 Defender 排除项后重跑本脚本'
    }
    if ($capaBat -or $capaExe) {
        Write-Skip "capa 已就位 -> $(if($capaBat){$capaBat}else{$capaExe})"
        Add-Action '工具链' 'capa' '跳过（已就位）'
    } else {
        Write-Warn2 'capa 未就位。装法：官方 exe + 独立规则目录，或 python -m capa.main -r <规则目录>'
        Add-Action '工具链' 'capa' '需人工放置（官方 exe + 规则目录）'
    }
    Add-Finding 'Defender 排除项' $(if ($capaExe -and $capaRules) { 'capa 完好在位（未被隔离）' } else { '未验证' })

    # ── FLOSS：官方 zip 或装进 python-venv（§4.3：装 flare-floss 得到 floss.exe）───
    $flossBin = Resolve-Tool -Name 'floss' -FallbackRel 'cli\floss.cmd'
    if ($flossBin) { Write-Skip "FLOSS 已就位 -> $flossBin"; Add-Action '工具链' 'flare-floss' '跳过（已就位）' }
    else {
        Write-Warn2 'FLOSS 未就位。装 flare-floss 到独立 venv（其 Scripts 目录绝不能进 PATH，会遮蔽系统 Python）'
        Add-Action '工具链' 'flare-floss' '需 pip 装（独立 venv）'
    }
}

# ═════════════════════════════════════════════════════════════════════════════
# §4.2 .NET 工具链
# ═════════════════════════════════════════════════════════════════════════════
function Install-DotNetTools {
    Write-Step '§4.2 .NET 工具链'
    if (-not (Test-Command 'dotnet')) {
        Write-Warn2 'dotnet 不存在，§4.2 全部跳过（§3.1 应该先装 .NET SDK 8）'
        return
    }
    # DOTNET_ROOT 必须指向 SDK 目录，否则 ilspycmd 报「You must install .NET」（§4.2）
    $dn = (Get-Command 'dotnet').Source
    $env:DOTNET_ROOT = $dn.Replace('\dotnet.exe','')
    try { $env:DOTNET_ROOT = [Environment]::GetEnvironmentVariable('DOTNET_ROOT','Machine') } catch { }
    if (-not $env:DOTNET_ROOT) { $env:DOTNET_ROOT = $dn.Replace('\dotnet.exe','') }

    $have = Test-Command 'ilspycmd'
    if ($have) {
        Write-Skip "ilspycmd 已装 -> $((Get-Command ilspycmd).Source)"
        Add-Action '.NET' 'ilspycmd' '跳过（已装）'
    } else {
        if ($DryRun) { Write-Dry 'dotnet tool install -g ilspycmd --version 9.1.0.7988'; Add-Action '.NET' 'ilspycmd' 'dryrun' }
        else {
            Write-Act '正在装 ilspycmd（锁 9.1.x —— 10.x/11.x 的 NuGet 只有 tools\net10.0，需要 .NET 10）...'
            # ★ 必须锁版本，否则报「找不到 DotnetToolSettings.xml」，
            #   那个报错长得像下载损坏，实际是目标框架不匹配（§4.2）
            $o = & dotnet tool install -g ilspycmd --version 9.1.0.7988 2>&1
            if ($LASTEXITCODE -eq 0) {
                Update-Path
                Write-Done 'ilspycmd 安装完成'
                Add-Action '.NET' 'ilspycmd' '已安装'
            } else {
                Write-Err "ilspycmd 安装失败 rc=$LASTEXITCODE"
                ($o | Select-Object -Last 3) | ForEach-Object { Write-Host "      $_" -ForegroundColor DarkRed }
                Add-Action '.NET' 'ilspycmd' '失败'
            }
        }
    }

    foreach ($t in @(
        @{ Name='de4dot'; Rel='de4dot\de4dot.exe';          Repo='0xd4d/de4dot';  Pat='\.zip$' },
        @{ Name='dnSpy.Console'; Rel='dnSpy\dnSpy.Console.exe'; Repo='dnSpyEx/dnSpy'; Pat='\.zip$' },
        @{ Name='Confuser.CLI';  Rel='ConfuserEx\Confuser.CLI.exe'; Repo='milkvod/GConfuserEx'; Pat='\.zip$' }
    )) {
        $p = Find-ToolExe $t.Rel
        if ($p) { Write-Skip "$($t.Name) 已就位 -> $p"; Add-Action '.NET' $t.Name '跳过（已就位）'; continue }
        if ($DryRun) { Write-Dry "下载 $($t.Repo) -> $($t.Dest)"; continue }
        Write-Warn2 "$($t.Name) 未就位（绿色版，从 $($t.Repo)/releases 解压即用）"
        Add-Action '.NET' $t.Name '需人工放置'
    }
}

# ═════════════════════════════════════════════════════════════════════════════
# §4.3 pip 生态（独立 venv，绝不污染系统 Python）
# ═════════════════════════════════════════════════════════════════════════════
$script:VenvPyPkgs = @(
    'angr','capstone','unicorn','lief','pefile','yara-python','qiling','z3-solver',
    'dnfile','frida-tools','pyghidra-mcp'
)

function Install-PipEcosystem {
    Write-Step '§4.3 pip 生态（独立 venv）'
    if (-not (Test-Command 'python')) {
        Write-Warn2 'python 不存在，§4.3 跳过'
        return
    }
    $venv = Join-Path $script:ToolRoot 'runtime\python-venv'
    $venvPy = Join-Path $venv 'Scripts\python.exe'

    if (-not (Test-Path $venvPy)) {
        if ($DryRun) { Write-Dry "python -m venv $venv"; Add-Action 'pip' 'python-venv' 'dryrun'; return }
        Write-Act "建 venv: $venv"
        try {
            & python -m venv $venv
            if ($LASTEXITCODE -eq 0) { Write-Done "venv 建好 -> $venvPy"; Add-Action 'pip' 'python-venv' '已创建' }
            else { Write-Err "venv 创建失败 rc=$LASTEXITCODE"; Add-Action 'pip' 'python-venv' '失败'; return }
        } catch { Write-Err "venv 创建异常: $($_.Exception.Message)"; return }
    } else {
        Write-Skip "venv 已在 -> $venvPy"
    }

    if ($DryRun) { Write-Dry ("pip install " + ($script:VenvPyPkgs -join ' ')); return }

    $pip = Join-Path $venv 'Scripts\pip.exe'
    if (-not (Test-Path $pip)) { Write-Err "venv 里没有 pip.exe：$pip"; return }

    foreach ($pkg in $script:VenvPyPkgs) {
        Write-Act "pip install $pkg ..."
        try {
            $o = & $pip install --disable-pip-version-check -q $pkg 2>&1
            if ($LASTEXITCODE -eq 0) { Write-Done "$pkg ok"; Add-Action 'pip' $pkg '已安装' }
            else {
                Write-Err "$pkg 失败 rc=$LASTEXITCODE"
                ($o | Select-Object -Last 2) | ForEach-Object { Write-Host "      $_" -ForegroundColor DarkRed }
                Add-Action 'pip' $pkg '失败'
            }
        } catch {
            Write-Err "$pkg 异常: $($_.Exception.Message)"
            Add-Action 'pip' $pkg '异常'
        }
    }

    # §4.3 装完必须验证：逐个 import，不接受「装了就完」
    Write-Act '验证 venv import ...'
    $probe = 'import angr,capstone,unicorn,lief,pefile,yara,qiling,z3,dnfile;print("IMPORT_OK")'
    $r = Invoke-Check -Exe $venvPy -ArgList @('-c', $probe) -TimeoutSec 120
    if ($r -and $r.Out -match 'IMPORT_OK') {
        Write-Done 'venv 核心库 import 全通（angr/capstone/unicorn/lief/pefile/yara/qiling/z3/dnfile）'
        Add-Action 'pip' 'import 验证' '通过'
    } else {
        Write-Warn2 "venv import 验证未全通过: $(if($r){$r.Out.Substring(0,[Math]::Min(120,$r.Out.Length))}else{'无输出'})"
        Add-Action 'pip' 'import 验证' '未通过'
    }
    $r2 = Invoke-Check -Exe (Join-Path $venv 'Scripts\floss.exe') -ArgList @('--version') -TimeoutSec 60
    if ($r2) { Write-Act "venv floss --version => $($r2.Out)" }
}

# ═════════════════════════════════════════════════════════════════════════════
# §4.4 YARA 规则库
# ═════════════════════════════════════════════════════════════════════════════
function Install-YaraRules {
    Write-Step '§4.4 规则与签名库'
    $rulesDir = Join-Path $script:ToolRoot 'yara\yara-rules'
    if (Test-Path -LiteralPath $rulesDir -ErrorAction SilentlyContinue) {
        $n = (Get-ChildItem -LiteralPath $rulesDir -Filter '*.yar' -Recurse -ErrorAction SilentlyContinue).Count
        Write-Skip "YARA 规则库已在 -> $rulesDir（$n 个 .yar）"
        Add-Action '规则库' 'YARA-Rules' "跳过（已存在，$n 个 .yar）"
        return
    }
    if ($DryRun) { Write-Dry "拉 Yara-Rules/rules -> $rulesDir"; Add-Action '规则库' 'YARA-Rules' 'dryrun'; return }

    # ★ 本机 git 到 github 会被 TLS 切断（§4.6 / §6.1），走 gh 或 curl tarball
    $gh = $null
    $g = Get-Command 'gh' -ErrorAction SilentlyContinue
    if ($g) { $gh = $g.Source }
    if (-not $gh) { $gh = Find-ToolExe 'gh\bin\gh.exe' }

    $ok = $false
    if ($gh) {
        Write-Act "gh repo clone Yara-Rules/rules -> $rulesDir"
        $env:GH_TOKEN = $null
        $o = & $gh repo clone 'https://github.com/Yara-Rules/rules.git' $rulesDir 2>&1
        $ok = ($LASTEXITCODE -eq 0 -and (Test-Path $rulesDir))
    }
    if (-not $ok) {
        Write-Act "curl tarball（git TLS 被切断时的备选，§6.1）..."
        try {
            $tgz = Join-Path $env:TEMP 'setupenv-yara-rules.tar.gz'
            $curl = Get-Command 'curl.exe' -ErrorAction SilentlyContinue
            if ($curl) {
                & $curl.Source -L --fail -o $tgz 'https://codeload.github.com/Yara-Rules/rules/tar.gz/refs/heads/master'
                if ((Test-Path $tgz) -and (Get-Item $tgz).Length -gt 1024) {
                    $ex = Join-Path $script:ToolRoot 'yara'
                    New-Item -ItemType Directory -Force -Path $ex | Out-Null
                    $sz = Get-Command '7z.exe' -ErrorAction SilentlyContinue
                    if (-not $sz) { $sz = Find-ToolExe '7-Zip\7z.exe' }
                    if ($sz) {
                        $s = if ($sz.Source) { $sz.Source } else { $sz }
                        & $s x $tgz "-o$ex" -y | Out-Null
                        $inner = Get-ChildItem $ex -Directory -Filter 'rules-*' | Select-Object -First 1
                        if ($inner) { Move-Item $inner.FullName $rulesDir -Force }
                    }
                    $ok = (Test-Path $rulesDir)
                }
            }
        } catch { Write-Warn2 "tarball 备选失败: $($_.Exception.Message)" }
    }

    if ($ok) {
        $n = (Get-ChildItem -LiteralPath $rulesDir -Filter '*.yar' -Recurse -ErrorAction SilentlyContinue).Count
        Write-Done "YARA 规则库就位（$n 个 .yar）"
        Add-Action '规则库' 'YARA-Rules' "已装（$n 个 .yar）"
        Write-Warn2 '★ yara 命令行不接受目录参数，整库匹配必须传根目录下的 *_index.yar（§4.4）'
    } else {
        Write-Err 'YARA 规则库两条路都没成（gh clone / curl tarball）'
        Note-Blocker '两条路都不通' 'YARA-Rules 规则库' 'gh repo clone 与 curl tarball 均失败' `
                    '手动下载 https://github.com/Yara-Rules/rules/releases 的 zip 解压到 <工具根>\yara\yara-rules'
        Add-Action '规则库' 'YARA-Rules' '失败'
    }
}

# ═════════════════════════════════════════════════════════════════════════════
# §4.5 / §4.6 工具根登记 + 商业工具
# ═════════════════════════════════════════════════════════════════════════════
function Register-ToolRoot {
    Write-Step '§4.5 登记工具根 + 环境变量'
    # ★ 2026-10-10：显式打印工具根**来源**，否则「用了旧盘工具」这件事
    #   在 140 秒的输出里完全看不出来（验收门会在错的根上判绿）。
    Write-Act ("工具根: {0}    来源: {1}" -f $script:ToolRoot, $script:ToolRootSource)
    if (-not (Test-Path -LiteralPath $script:ToolRoot)) {
        Write-Warn2 ("工具根不存在: {0}（来源: {1}）—— 验收门将无法找到任何工具" -f `
                      $script:ToolRoot, $script:ToolRootSource)
    }
    $sk = $PSScriptRoot
    if (-not $sk) { $sk = Split-Path -Parent $MyInvocation.MyCommand.Path }
    foreach ($pair in @(
        @{ N='REVERSE_SKILL_ROOT'; V=$sk },
        @{ N='REVERSE_TOOL_ROOT';  V=$script:ToolRoot }
    )) {
        try {
            # ★ R2：只写 User 级，绝不写 Machine 级（红线）
            [System.Environment]::SetEnvironmentVariable($pair.N, $pair.V, [System.EnvironmentVariableTarget]::User)
            Set-Item -Path "Env:$($pair.N)" -Value $pair.V
            Write-Done "用户级 $($pair.N) = $($pair.V)"
            Add-Action '登记' $pair.N "已写 User 级 = $($pair.V)"
        } catch {
            Write-Err "写用户级 $($pair.N) 失败: $($_.Exception.Message)"
            Add-Action '登记' $pair.N '失败'
        }
    }
    Add-Finding 'REVERSE_TOOL_ROOT' $script:ToolRoot
}

<#
.SYNOPSIS
IDA install discovery. IDA directories always carry a version number, so never
hardcode one: probe the usual roots one level deep and match an IDA* name.
.DESCRIPTION
Returns tool-root hits first (tool root outranks system-wide installs), then
Program Files / drive roots / user dirs. Newest modification time first.
#>
function Get-IdaInstallCandidates {
    param([string]$ToolRoot)
    $roots = @(
        $ToolRoot
        (Join-Path $script:ToolRoot 'disasm')
        'C:\Program Files'
        'C:\Program Files (x86)'
        'C:\'
        'D:\'
        (Join-Path $env:USERPROFILE 'Desktop')
        (Join-Path $env:USERPROFILE 'Tools')
    ) | Where-Object { $_ -and (Test-Path -LiteralPath $_ -ErrorAction SilentlyContinue) }
    $hits = @(
        foreach ($root in $roots) {
            Get-ChildItem -LiteralPath $root -Directory -ErrorAction SilentlyContinue |
                Where-Object { $_.Name -match '(?i)^IDA\b|^IDA[_. ]' } |
                ForEach-Object {
                    $app = Join-Path $_.FullName 'App\IDA Pro'
                    if (Test-Path -LiteralPath $app -ErrorAction SilentlyContinue) { $app } else { $_.FullName }
                }
        }
    )
    return @($hits | Sort-Object -Unique)
}

function Invoke-CommercialTools {
    Write-Step '§4.6 商业工具'
    if ($SkipCommercial) {
        Write-Skip '-SkipCommercial：跳过 IDA / JEB / Binary Ninja / relab-tools'
        Add-Action '商业工具' '全部' '跳过（-SkipCommercial）'
        return
    }

    # 探测本机已有的 IDA（★ 找到文件 ≠ 能跑，必须实跑）
    $idaCands = @()
    $env:IDADIR2 = $null
    foreach ($p in (Get-IdaInstallCandidates -ToolRoot $script:ToolRoot)) {
        if (Test-Path -LiteralPath $p -ErrorAction SilentlyContinue) { $idaCands += $p }
    }

    if ($idaCands.Count -eq 0) {
        Write-Warn2 '未找到 IDA 安装目录'
        Note-Blocker '商业许可' 'IDA Professional' '本机无 IDA 安装目录' '提供 hexlic 并从 hex-rays.com 下载安装'
        Add-Action '商业工具' 'IDA' '缺失'
        return
    }

    foreach ($dir in $idaCands) {
        # ★ IDA 9.x 只有 idat.exe（单一分析器），8.3 才有 idat64.exe；x64 目标必须用 64 位分析器（§6.5）
        $idat = Join-Path $dir 'idat64.exe'
        if (-not (Test-Path $idat)) { $idat = Join-Path $dir 'idat.exe' }
        if (-not (Test-Path $idat)) { continue }

        $bak = Join-Path $env:TEMP 'setupenv-ida-probe'
        New-Item -ItemType Directory -Force -Path $bak | Out-Null
        $py  = Join-Path $bak 'probe.py'
        $out = Join-Path $bak 'out.txt'
        # ★ 脚本必须以 idc.qexit(0) 结尾（缺了就挂死到超时），开头必须 idaapi.auto_wait()
        #   （否则反编译出来全是 JUMPOUT 空壳）——§6.5
        @'
import idaapi, idc
idaapi.auto_wait()
idc.qexit(0)
'@ | Set-Content -LiteralPath $py -Encoding ASCII

        if ($DryRun) { Write-Dry "实跑 IDA headless: $idat"; continue }

        Write-Act "实跑 IDA headless: $idat"
        $env:IDADIR = $dir
        Remove-Item Env:\IDAUSR -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $out -Force -ErrorAction SilentlyContinue
        $ok = $false; $why = ''
        try {
            $log = Join-Path $bak 'ida.log'
            $p = Start-Process -FilePath $idat `
                    -ArgumentList @('-A', "-L$log", "-S$py", (Join-Path $script:WorkDir 'ida-probe.exe')) `
                    -NoNewWindow -Wait -PassThru `
                    -RedirectStandardOutput (Join-Path $bak 'o.txt') `
                    -RedirectStandardError  (Join-Path $bak 'e.txt')
            if ($p.ExitCode -eq 0) { $ok = $true }
            else {
                $lt = ''
                if (Test-Path $log) { $lt = (Get-Content $log -Raw -ErrorAction SilentlyContinue) }
                $why = if ($lt) { ($lt -split "`r?`n" | Where-Object { $_ } | Select-Object -First 1) } else { "exit=$($p.ExitCode)" }
            }
        } catch { $why = $_.Exception.Message }

        if ($ok) {
            Write-Done "IDA headless 可用 -> $idat"
            Add-Action '商业工具' "IDA $dir" 'headless 通过'
        } else {
            Write-Err "IDA headless 不可用：$why"
            Add-Action '商业工具' "IDA $dir" "不可用：$why"
            # 只对最可能可用的那个记一条 blocker，避免刷屏
            if ($idaCands[0] -eq $dir) {
                Note-Blocker '商业许可' 'IDA headless' ("$dir 实跑失败：$why") `
                            '需要真实 hexlic（9.x 是 .hexlic JSON，8.x 是 .key 文本，两种都要搜）+ 首次启动在 GUI 里点接受协议'
            }
        }
    }

    # relab-tools（商业/下架便携工具，9 卷 7z，770 MB）
    $rt = Join-Path $script:ToolRoot 'MANIFEST.json'
    if (Test-Path -LiteralPath $rt) {
        Write-Skip "relab-tools 已展开（MANIFEST.json 在位）-> $rt"
        Add-Action '商业工具' 'relab-tools' '跳过（已展开）'
    } else {
        $gh = (Get-Command 'gh' -ErrorAction SilentlyContinue)
        if (-not $gh) { $gh = Find-ToolExe 'gh\bin\gh.exe' }
        $authed = $false
        if ($gh) {
            try { $null = & $gh.Source auth status 2>&1; $authed = ($LASTEXITCODE -eq 0) } catch { }
        }
        if ($authed) {
            if ($DryRun) { Write-Dry "gh repo clone relab-tools -> $env:TEMP\relab-tools"; Add-Action '商业工具' 'relab-tools' 'dryrun' }
            else {
                Write-Act 'gh repo clone relab-tools ...'
                $dl = Join-Path $env:TEMP 'setupenv-relab-tools'
                try {
                    $o = & $gh.Source repo clone 'https://github.com/gthubtom1/relab-tools.git' $dl 2>&1
                    if ($LASTEXITCODE -eq 0) {
                        # ★ 解压会覆盖 _map.json —— 先备份（§4.6）
                        $bk = Join-Path $script:ToolRoot '_tools\backup'
                        New-Item -ItemType Directory -Force -Path $bk | Out-Null
                        $map = Join-Path $script:ToolRoot '_map.json'
                        if (Test-Path $map) {
                            Copy-Item $map (Join-Path $bk "_map.json.$(Get-Date -f yyyyMMdd-HHmmss).bak")
                            Write-Act '_map.json 已备份'
                        }
                        $sz = Get-Command '7z.exe' -ErrorAction SilentlyContinue
                        if (-not $sz) { $sz = Find-ToolExe '7-Zip\7z.exe' }
                        $sevenz = if ($sz.Source) { $sz.Source } elseif ($sz) { $sz } else { $null }
                        $vols = Get-ChildItem $dl -Filter 'relab-tools.7z.*' -ErrorAction SilentlyContinue | Sort-Object Name
                        if (-not $sevenz -or $vols.Count -eq 0) {
                            Write-Err 'relab-tools：缺 7z 或缺分卷，跳过解压'
                            Add-Action '商业工具' 'relab-tools' '已下载但未解压'
                        } else {
                            # ★ 完整性一律按 SHA256 校验，不要看魔数（分卷只有 .001 有魔数，§4.6）
                            $expect = @{}
                            $sf = Join-Path $dl 'SHA256SUMS.txt'
                            if (Test-Path $sf) {
                                Get-Content $sf | ForEach-Object {
                                    $parts = $_ -split '\s+', 2
                                    if ($parts.Count -eq 2) { $expect[$parts[1].Trim()] = $parts[0].ToLower() }
                                }
                            }
                            $allOk = $true
                            foreach ($v in $vols) {
                                $h = (Get-FileHash $v.FullName -Algorithm SHA256).Hash.ToLower()
                                if ($expect.ContainsKey($v.Name)) {
                                    if ($h -eq $expect[$v.Name]) { Write-Host "      OK   $($v.Name)" -ForegroundColor DarkGreen }
                                    else { Write-Host "      FAIL $($v.Name)" -ForegroundColor Red; $allOk = $false }
                                } else {
                                    Write-Warn2 "$($v.Name) 不在 SHA256SUMS.txt 里，跳过校验"
                                }
                            }
                            if (-not $allOk) {
                                Write-Err '分卷 SHA256 不符 —— 不解压（缺卷会直接失败，§4.6）'
                                Note-Blocker '两条路都不通' 'relab-tools 分卷' 'SHA256SUMS.txt 与本地分卷不符，可能下载不全' '重新 clone 后重跑'
                            } else {
                                $o7 = & $sevenz x (Join-Path $dl 'relab-tools.7z.001') "-o$script:ToolRoot" -y 2>&1
                                if ($LASTEXITCODE -eq 0) {
                                    foreach ($f in 'README.md','MANIFEST.json','SHA256SUMS.txt','_map.json') {
                                        if (Test-Path (Join-Path $script:ToolRoot $f)) { Write-Done "到位: $f" }
                                        else { Write-Warn2 "缺 $f" }
                                    }
                                    Write-Done 'relab-tools 已展开'
                                    Add-Action '商业工具' 'relab-tools' '已展开'
                                } else {
                                    Write-Err "7z 解压失败 rc=$LASTEXITCODE（分卷必须全卷齐全，§4.6）"
                                    Add-Action '商业工具' 'relab-tools' '解压失败'
                                }
                            }
                        }
                    } else {
                        Write-Err "gh repo clone 失败 rc=$LASTEXITCODE"
                        Note-Blocker '两条路都不通' 'relab-tools' 'gh 已登录但 repo clone 失败' '检查网络后重跑本脚本'
                    }
                } catch { Write-Err "relab-tools 异常: $($_.Exception.Message)" }
            }
        } else {
            # ★ 账号登录类：gh 未登录
            Note-Blocker '账号登录' 'relab-tools' 'gh 未登录，relab-tools 是私有仓库，拉不下来' '执行 gh auth login 后重跑本脚本'
            Add-Action '商业工具' 'relab-tools' '阻塞（gh 未登录）'
        }
    }
}

# ═════════════════════════════════════════════════════════════════════════════
# §2.8 MCP 通道：写文件不算完成，必须实测握手
# ★ stdio 型 MCP server 永不退出 —— 用 ReadToEnd 永远等不到结果（§6.2 / §2.8）
# ═════════════════════════════════════════════════════════════════════════════
function Invoke-McpChannels {
    Write-Step '§2.8 MCP 通道探测（握手实测，不是看文件在不在）'
    $cands = @(
        "$env:USERPROFILE\.omp\agent\mcp.json",
        "$env:USERPROFILE\.claude\mcp.json",
        "$env:USERPROFILE\.codex\config.toml",
        "$env:USERPROFILE\.cursor\mcp.json"
    )
    $found = @()
    foreach ($c in $cands) {
        if (Test-Path -LiteralPath $c -ErrorAction SilentlyContinue) { $found += $c }
    }
    foreach ($c in $cands) {
        if ($found -contains $c) { Write-Skip "已配置: $c" }
        else { Write-Warn2 "无配置: $c" }
    }
    if ($found.Count -eq 0) {
        Write-Warn2 '一个 MCP 配置都没有 —— 探测层/反编译能力会少一半（§2.8）'
        Add-Action 'MCP' '配置文件' '缺失（需按 §2.8 建）'
        return
    }

    # 逐个 server 做 initialize + tools/list 握手
    foreach ($f in $found) {
        if ([IO.Path]::GetExtension($f) -ne '.json') { continue }
        try { $j = Get-Content -LiteralPath $f -Raw -Encoding UTF8 | ConvertFrom-Json } catch { continue }
        if (-not $j.mcpServers) { continue }
        foreach ($p in $j.mcpServers.PSObject.Properties) {
            $name = $p.Name
            $srv  = $p.Value
            $cmd  = $srv.command
            if (-not $cmd) { continue }
            if (-not (Test-Path -LiteralPath $cmd -ErrorAction SilentlyContinue)) {
                Write-Err "$name : command 不存在 $cmd"
                Add-Action 'MCP' $name "command 缺失: $cmd"
                continue
            }
            if ($DryRun) { Write-Dry "握手 $name ($cmd)"; continue }

            $envVars = @{}
            if ($srv.env) { foreach ($e in $srv.env.PSObject.Properties) { $envVars[$e.Name] = [string]$e.Value } }
            $r = Test-McpHandshake -Exe $cmd -ArgList @($srv.args) -Envs $envVars
            if ($r.Ok) {
                Write-Done "$name 握手成功（$($r.Detail)）"
                Add-Action 'MCP' $name "握手通过（$($r.Detail)）"
            } else {
                Write-Err "$name 握手失败：$($r.Detail)"
                Add-Action 'MCP' $name "握手失败（$($r.Detail)）"
            }
        }
    }
}

function Test-McpHandshake {
    param([string]$Exe, [string[]]$ArgList, [hashtable]$Envs)
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $Exe
    foreach ($a in @($ArgList)) { if ($a) { $psi.ArgumentList.Add([string]$a) } }
    $psi.RedirectStandardInput  = $true
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError  = $true
    $psi.UseShellExecute = $false
    foreach ($k in $Envs.Keys) { $psi.EnvironmentVariables[$k] = $Envs[$k] }

    try {
        $p = New-Object System.Diagnostics.Process
        $p.StartInfo = $psi
        if (-not $p.Start()) { return @{ Ok=$false; Detail='进程起不来' } }
        # ★ 必须逐行读，ReadToEnd 会永久阻塞（stdio server 永不退出）
        $t = $p.StandardOutput.ReadLineAsync()
        if (-not $t.Wait(12000)) { try { $p.Kill() } catch {}; return @{ Ok=$false; Detail='12s 内无响应（可能需要交互或该 server 是 http 型）' } }
        $line = $t.Result
        $p.StandardInput.WriteLine('{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"setup-env","version":"1"}}}')
        $p.StandardInput.WriteLine('{"jsonrpc":"2.0","method":"notifications/initialized"}')
        $p.StandardInput.WriteLine('{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}')
        $p.StandardInput.Flush()
        $t2 = $p.StandardOutput.ReadLineAsync()
        $ok = $t2.Wait(12000) -and ($t2.Result -match 'serverInfo|"result"')
        try { $p.Kill() } catch { }
        return @{ Ok = $ok; Detail = $(if ($ok) { 'initialize + tools/list 有响应' } else { 'tools/list 无响应' }) }
    } catch {
        return @{ Ok=$false; Detail=$_.Exception.Message }
    }
}

# ═════════════════════════════════════════════════════════════════════════════
# §5 验收门
# ═════════════════════════════════════════════════════════════════════════════
function Add-Gate {
    param([string]$Gate,[string]$Name,[bool]$Ok,[string]$Evidence)
    $script:GateResults.Add([pscustomobject]@{ 门=$Gate; 检查项=$Name; 结果=$(if($Ok){'PASS'}else{'FAIL'}); 证据=$Evidence })
    if ($Ok) { Write-Host ("  [PASS] {0} · {1} —— {2}" -f $Gate,$Name,$Evidence) -ForegroundColor Green }
    else    { Write-Host ("  [FAIL] {0} · {1} —— {2}" -f $Gate,$Name,$Evidence) -ForegroundColor Red }
}

function Invoke-AcceptanceGates {
    Write-Step '§5 验收门（造真样本，判据外部可观测）'
    $work = $script:WorkDir

    # ── 造样本：埋唯一标记，分支靠 argv 运行时成立（§6.4）────────────────────
    Write-Act '门2 前置：造样本'
    $gcc = Resolve-AcceptTool -Id 'gcc'
    if (-not $gcc) {
        Add-Gate '门2' 'gcc 编译样本' $false 'gcc 不在（造不了样本，门2 无法执行）'
        Add-Gate '门2' '后续 7 项' $false '样本未生成'
        Add-Gate '门3' '反反调试三层翻转' $false 'gcc 不在'
    } else {
        # ★ 文件名统一叫 probe.exe：§4.6 的 IDA 摸底在建设阶段先跑，
        #   而 -VerifyOnly 不做建设、此时 probe.exe 还不存在，所以摸底那次允许 rc≠0，
        #   只记一条 blocker，不让它变成验收门的硬依赖
        $probe = Join-Path $work 'probe.exe'
        $src   = Join-Path $work 'probe.c'
        @'
#include <stdio.h>
#include <windows.h>
volatile int sink;
__declspec(dllexport) int verify(int x){ sink = x; volatile int k = 0x6B21; return x == k; }
int main(int argc, char** argv){
  int v = verify(argc > 1 ? 0x6B21 : 1);
  HANDLE h = CreateFileA("C:\\SETUPENV_MARKER.txt", GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, 0, NULL);
  if (h != INVALID_HANDLE_VALUE) CloseHandle(h);
  printf("SETUPENV_MARKER_9f2c v=%d\n", v);
  return 0;
}
'@ | Set-Content -LiteralPath $src -Encoding ASCII

        $r = Invoke-Check -Exe $gcc -ArgList @($src, '-O0', '-o', $probe) -TimeoutSec 180
        $sz = $(if (Test-Path $probe) { (Get-Item $probe).Length } else { 0 })
        Add-Gate '门2' 'gcc 编译样本' ($sz -gt 1024) "$sz bytes（rc=$($r.Code)）"

        # ── UPX 加壳 / DIE 查壳 / UPX 脱壳 ──────────────────────────────────
        $upx = Resolve-AcceptTool -Id 'upx'
        $packed   = Join-Path $work 'packed.exe'
        $unpacked = Join-Path $work 'unpacked.exe'
        $sz0 = $sz
        if ($upx) {
            $null = Invoke-Check -Exe $upx -ArgList @('--silent','-q', $probe, '-o', $packed) -TimeoutSec 120
            $sz1 = $(if (Test-Path $packed) { (Get-Item $packed).Length } else { 0 })
            Add-Gate '门2' 'UPX 加壳' ($sz1 -gt 0 -and $sz1 -lt $sz0) "$sz0 -> $sz1 bytes"
        } else {
            $sz1 = 0
            Add-Gate '门2' 'UPX 加壳' $false 'upx 不在'
        }

        $diec = Resolve-AcceptTool -Id 'diec'
        if ($diec -and (Test-Path $packed)) {
            # ★ 判据必须是「输出里出现样本真特征」，不是「有输出」（§5 判据表）
            $d = Invoke-Check -Exe $diec -ArgList @('-j', $packed) -TimeoutSec 120
            $hasUPX = ($d.Out -match 'UPX')
            $hasPE  = ($d.Out -match 'PE64|"filetype"\s*:\s*"PE')
            Add-Gate '门2' 'DIE 查壳' ($hasUPX -and $hasPE) "输出含 PE=$hasPE UPX=$hasUPX"
        } else {
            Add-Gate '门2' 'DIE 查壳' $false 'diec 不在或 packed 未生成'
        }

        if ($upx -and (Test-Path $packed)) {
            $null = Invoke-Check -Exe $upx -ArgList @('--silent','-q','-d', $packed, '-o', $unpacked) -TimeoutSec 120
            $sz2 = $(if (Test-Path $unpacked) { (Get-Item $unpacked).Length } else { 0 })
            # ★ 不要要求逐字节 sha256 相同 —— UPX 会改 PE 时间戳（§6.8）
            #   正确判据：体积还原 + 可执行 + UPX 特征消失
            $restored = ($sz2 -eq $sz0)
            # ★★ 两个坑，都是本机实测踩的：
            #   ① UPX 会给产出的 exe 打上 NTFS 备用数据流（Zone.Identifier），
            #      不摘掉的话脱壳样本双击会弹「为了计算机安全，此文件已被阻止」，
            #      Start-Process 直接抛「不是有效的 Win32 应用程序」，连 stdout 文件都不建；
            #   ② 判据必须看 stdout 里有没有埋进去的标记 —— 只看「输出文件被创建」
            #      是 §6.8 点名的假通过（程序崩了 Start-Process 也会建出空文件）。
            $runOut  = Join-Path $work 'unpacked-run.txt'
            $runFile = $null
            $runnable = $false
            $runErr = ''
            if ($restored) {
                try { Unblock-File -LiteralPath $unpacked -ErrorAction SilentlyContinue } catch { }
                Remove-Item -LiteralPath $runOut -Force -ErrorAction SilentlyContinue
                $runRes = Invoke-Check -Exe $unpacked -ArgList @() -TimeoutSec 60 -Redirect $runOut
                if (Test-Path -LiteralPath $runOut) {
                    $runFile = (Get-Content -LiteralPath $runOut -Raw -ErrorAction SilentlyContinue)
                    $runnable = ($null -ne $runFile) -and ($runFile -match 'SETUPENV_MARKER_9f2c')
                }
                if (-not $runnable -and (Test-Path -LiteralPath ($runOut + '.err'))) {
                    $runErr = (Get-Content -LiteralPath ($runOut + '.err') -Raw -ErrorAction SilentlyContinue)
                }
            }
            if (-not $runnable) {
                Write-Warn2 ("UPX 脱壳后的可执行判据没拿到：stdout 文件存在=" + (Test-Path $runOut) +
                             "，内容长度=" + $(if ($null -ne $runFile) { $runFile.Length } else { -1 }))
                if ($runFile) {
                    Write-Warn2 ('  脱壳样本 stdout 前几行: ' + (((@($runFile -split "`r?`n")) | Select-Object -First 3) -join ' / '))
                }
                if ($runErr) {
                    Write-Warn2 ('  脱壳样本 stderr: ' + ($runErr -replace "`r?`n", ' / '))
                }
            }
            $stillPacked = $false
            if ($diec -and (Test-Path $unpacked)) {
                $d2 = Invoke-Check -Exe $diec -ArgList @('-j', $unpacked) -TimeoutSec 120
                $stillPacked = ($d2.Out -match 'UPX')
            }
            Add-Gate '门2' 'UPX 脱壳' ($restored -and $runnable -and -not $stillPacked) `
                ("$sz1 -> $sz2 bytes（还原=$restored 可执行=$runnable UPX特征残留=$stillPacked）" +
                 $(if ($runFile) { "；实跑 stdout: " + (($runFile -split "`r?`n" | Where-Object { $_ -match 'SETUPENV_MARKER' } | Select-Object -First 1)) } else { '' }))
        } else {
            Add-Gate '门2' 'UPX 脱壳' $false '前置缺失'
        }

        # ── FLOSS 提串 ────────────────────────────────────────────────────────
        $floss = Resolve-AcceptTool -Id 'floss'
        if ($floss) {
            $fo = Join-Path $work 'floss.txt'
            # ★ 必须是「命中你埋进样本的唯一标记」，不是「输出有内容」（§5 / §6.8）
            # ★ sample 参数必须放在选项之前：'floss x.exe --only static'，
            #   反过来写 argparse 会把 sample 当成 --only 的取值而报 invalid choice（本机实测）
            $null = Invoke-Check -Exe $floss -ArgList @($probe, '--only', 'static') -TimeoutSec 300 -Redirect $fo
            $txt = ''
            if (Test-Path $fo) { $txt = Get-Content -LiteralPath $fo -Raw -ErrorAction SilentlyContinue }
            $hit = ($txt -match 'SETUPENV_MARKER_9f2c')
            $lines = 0
            if (Test-Path $fo) { $lines = (Get-Content -LiteralPath $fo).Count }
            Add-Gate '门2' 'FLOSS 提字符串' $hit "$lines 行，命中唯一标记 SETUPENV_MARKER_9f2c = $hit"
        } else {
            Add-Gate '门2' 'FLOSS 提字符串' $false 'floss 不在'
        }

        # ── capa 能力 ─────────────────────────────────────────────────────────
        $capa = Resolve-AcceptTool -Id 'capa'
        if ($capa) {
            $co = Join-Path $work 'capa.txt'
            # ★ capa 是 .bat：不能用 cmd /c 拼引号（§6.3），用 Start-Process 转发
            $null = Invoke-Check -Exe $capa -ArgList @($probe) -TimeoutSec 300 -Redirect $co
            $ctxt = ''
            if (Test-Path $co) { $ctxt = Get-Content -LiteralPath $co -Raw -ErrorAction SilentlyContinue }
            $hasTable = ($ctxt -match 'Capability|Namespace|ATT&CK|md5')
            Add-Gate '门2' 'capa 能力识别' $hasTable ("出能力表 = $hasTable（$((Get-Content -LiteralPath $co -EA SilentlyContinue).Count) 行）")
        } else {
            Add-Gate '门2' 'capa 能力识别' $false 'capa 不在'
        }

        # ── 反编译：伪代码必须含目标函数名 ───────────────────────────────────
        $gh = Resolve-AcceptTool -Id 'analyzeHeadless'
        if ($gh) {
            $jout = Join-Path $work 'gh-out.txt'
            $jfile = Join-Path $work 'GhidraExport.java'
            @'
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionIterator;
public class GhidraExport extends GhidraScript {
  @Override public void run() throws Exception {
    DecompInterface di = new DecompInterface();
    di.openProgram(currentProgram);
    StringBuilder sb = new StringBuilder();
    FunctionIterator it = currentProgram.getFunctionManager().getFunctions(true);
    while (it.hasNext()) {
      Function f = it.next();
      DecompileResults r = di.decompileFunction(f, 30, null);
      sb.append("//== ").append(f.getName()).append(" ==\n");
      sb.append(r.getDecompiledFunction()==null ? "" : r.getDecompiledFunction().getC()).append("\n");
    }
    di.dispose();
    java.nio.file.Files.write(java.nio.file.Paths.get("OUTPATH"),
        sb.toString().getBytes("UTF-8"));
  }
}
'@ -replace 'OUTPATH', $jout.Replace('\','/') | Set-Content -LiteralPath $jfile -Encoding ASCII

            $projDir = Join-Path $work 'ghproj'
            New-Item -ItemType Directory -Force -Path $projDir | Out-Null   # ★ 必须先建，否则 "Directory not found"
            $gl = Join-Path $work 'gh.log'
            # ★ 调 .bat 不能 cmd /c 拼引号 —— 直接 & 转发，让 bat 自己加引号（§6.3）
            $null = Invoke-Check -Exe $gh `
                -ArgList @($projDir, 'setupenv', '-import', $probe, '-deleteProject',
                        '-scriptPath', $work, '-postScript', 'GhidraExport.java') `
                -TimeoutSec 900 -Redirect $gl
            $ptxt = ''
            if (Test-Path $jout) { $ptxt = Get-Content -LiteralPath $jout -Raw -ErrorAction SilentlyContinue }
            # 判据：伪代码含目标函数名 verify，且能看到埋入的字符串（§5 判据表）
            $hasVerify = ($ptxt -match 'verify')
            $hasMarker = ($ptxt -match 'SETUPENV_MARKER')
            Add-Gate '门2' 'Ghidra 反编译' ($hasVerify -and $hasMarker) `
                "伪代码 $(($ptxt).Length) chars，含 verify=$hasVerify 含埋串=$hasMarker"
        } else {
            Add-Gate '门2' 'Ghidra 反编译' $false 'analyzeHeadless 不在'
        }

        # ── IDA headless（商业，可选；有就实跑）──────────────────────────────
        if (-not $SkipCommercial) {
            $idaDir = $script:IdaDir
            if ($idaDir) {
                $idat = Join-Path $idaDir 'idat64.exe'
                if (-not (Test-Path $idat)) { $idat = Join-Path $idaDir 'idat.exe' }
                $bak = Join-Path $work 'ida'
                New-Item -ItemType Directory -Force -Path $bak | Out-Null
                Copy-Item $probe (Join-Path $bak 's.exe') -Force
                $py  = Join-Path $bak 'x.py'
                $pc  = Join-Path $bak 'p.c'
                # ★ 脚本必须 idc.qexit(0) 结尾 + 开头 idaapi.auto_wait()（§6.5）
                "import idaapi,idc,ida_hexrays,idautils`nidaapi.auto_wait()`nL=[]`nfor ea in idautils.Functions():`n    nm=idc.get_func_name(ea)`n    try:`n        c=ida_hexrays.decompile(ea)`n        if c: L.append('//== '+nm+' ==\`n'+str(c))`n    except Exception: pass`nopen(r'$pc','w',encoding='utf-8').write('\n\n'.join(L))`nidc.qexit(0)`n" |
                    Set-Content -LiteralPath $py -Encoding ASCII
                $env:IDADIR = $idaDir
                Remove-Item Env:\IDAUSR -ErrorAction SilentlyContinue
                $ilog = Join-Path $bak 'i.log'
                $r = $null
                try {
                    $p = Start-Process -FilePath $idat `
                            -ArgumentList @('-A', "-L$ilog", "-S$py", 's.exe') `
                            -WorkingDirectory $bak -NoNewWindow -Wait -PassThru `
                            -RedirectStandardOutput (Join-Path $bak 'o.txt') `
                            -RedirectStandardError  (Join-Path $bak 'e.txt')
                    $r = $p.ExitCode
                } catch { $r = -1 }
                $ptxt2 = ''
                if (Test-Path $pc) { $ptxt2 = Get-Content -LiteralPath $pc -Raw -ErrorAction SilentlyContinue }
                $hasV2 = ($ptxt2 -match 'verify')
                Add-Gate '门2' 'IDA headless 反编译' ($r -eq 0 -and $hasV2) `
                    "idat=$(Split-Path -Leaf $idat) rc=$r，伪代码 $(($ptxt2).Length) chars，含 verify=$hasV2"
            } else {
                Add-Gate '门2' 'IDA headless 反编译' $false '无 IDA 目录'
            }
        }

        # ── cdb 断点：★ 断点必须在 g 之前，只 g 一次（§6.2）────────────────────
        $cdb = Join-Path $env:LOCALAPPDATA 'Microsoft\WindowsApps\cdbX64.exe'
        if (Test-Path $cdb) {
            # ★ 命令串写文件（带引号会被 cmd 吃掉，§6.2）
            $cf    = Join-Path $work 'cdb-cmds.txt'
            $lg    = Join-Path $work 'cdb.log'
            $cdbout = Join-Path $work 'cdb.stdout.txt'
            @'
bp kernelbase!CreateFileA
g
.echo BP_HIT_MARKER
r rcx
da @rcx
bc 0
g
q
'@ | Set-Content -LiteralPath $cf -Encoding ASCII
            Remove-Item -LiteralPath $lg -Force -ErrorAction SilentlyContinue
            $r = $null
            try {
                # ★ 只能用 alias；直跑 WindowsApps 里的 cdb.exe 会「拒绝访问」（§6.2）
                $r = Invoke-Check -Exe $cdb -ArgList @('-logo', $lg, '-cf', $cf, $probe) -TimeoutSec 300 `
                        -Redirect $cdbout
            } catch { }
            # ★★ 被调试进程自己的 stdout 会继承 cdb 的 stdout，**不会进 -logo 日志**。
            #   实测：样本 printf 的内容只在 -RedirectStandardOutput 里，-logo 文件里一个字都没有。
            #   所以两个文件都要读：命中判定看 -logo，断点里的参数回显看 stdout。
            $cout = ''
            if (Test-Path $cdbout) { $cout = Get-Content -LiteralPath $cdbout -Raw -ErrorAction SilentlyContinue }
            $all = $ltxt + "`n" + $cout
            # ★ 判据必须外部可观测：断点真命中 + da @rcx 真的读出了我们埋的路径参数。
            #   不看 .echo 标记 —— 命令回显也进日志（§6.2 / §6.8）
            $hit2 = ($all -match 'Breakpoint 0 hit')
            # da 会把字符串连同引号一起回显，实测形如：00007ff6`120a4000  "C:\SETUPENV_MARKER.txt"
            $addr = ($all -match 'SETUPENV_MARKER\.txt')
            Add-Gate '门2' 'cdb 断点命中' ($hit2 -and $addr) `
                "Breakpoint hit=$hit2，da @rcx 读出路径=$addr（日志 $(($ltxt).Length) chars / stdout $(($cout).Length) chars）"
        } else {
            Add-Gate '门2' 'cdb 断点命中' $false 'cdbX64 alias 不存在（WinDbg 未装或 MSIX 未注册）'
        }
    }

    # ── 门 1 · 自检退出码 ────────────────────────────────────────────────────
    Write-Step '门1 · selfcheck 退出码'
    $sc = Join-Path $PSScriptRoot 'selfcheck.ps1'
    if (Test-Path $sc) {
        $p = $null
        try {
            # ★ 不改机器执行策略（R1），只给这一条命令加 -ExecutionPolicy Bypass（§6.1）
            $p = Start-Process -FilePath 'powershell.exe' `
                    -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File', $sc) `
                    -NoNewWindow -Wait -PassThru `
                    -RedirectStandardOutput (Join-Path $script:WorkDir 'selfcheck.out') `
                    -RedirectStandardError  (Join-Path $script:WorkDir 'selfcheck.err')
        } catch { }
        Add-Gate '门1' 'selfcheck.ps1 退出码' ($p -and $p.ExitCode -eq 0) "exit=$(if($p){$p.ExitCode}else{'未启动'})（必要但不充分）"
    } else {
        Add-Gate '门1' 'selfcheck.ps1 退出码' $false "找不到 $sc"
    }

    # ── 门 3 · 反反调试三层翻转（硬证据）────────────────────────────────────
    # 本机实测踩过的三件事，都写在这里了：
    #   ① 探针要连续采样（带序号），才分得清哪一段是裸跑 / 调试下 / 注入后；
    #   ② cdb -p <pid> attach 时必须给命令文件把进程放行（g），
    #      否则 attach 后进程停在 LdrpDoDebuggerBreak，只有 5-7 条样本就退出，
    #      会被误判成「ScyllaHide 生效」（实测就是这样误判的）；
    #   ③ ★ InjectorCLIx64 的正确语法是 pid:<id> <HookLibraryx64.dll>，
    #      不是 -p <id> [ini]。用错时它只打印用法横幅，那串 'Loaded VA ...'
    #      是 banner 自带的样例文本，退出码也是 0 —— 看着像成功，其实一次都没注入。
    Write-Step '门3 · 反反调试三层翻转'
    $adbC = Join-Path $work 'adbg.c'
    $adbE = Join-Path $work 'adbg.exe'
    if (-not $gcc -or -not (Test-Path $adbC)) {
        Add-Gate '门3' '三层翻转' $false 'gcc 或反调试探针源不在'
    } else {
        $r = Invoke-Check -Exe $gcc -ArgList @($adbC, '-O0', '-o', $adbE) -TimeoutSec 180
        if (-not (Test-Path $adbE)) {
            Add-Gate '门3' '三层翻转' $false "探针编译失败 rc=$($r.Code)"
        } else {
            $cdb = Join-Path $env:LOCALAPPDATA 'Microsoft\WindowsApps\cdbX64.exe'
            $scylla = Resolve-AcceptTool -Id 'scyllahide'
            $scyllaDir = $null
            if ($scylla) { $scyllaDir = Split-Path -Parent $scylla }
            $hookDll = $null
            if ($scyllaDir) { $hookDll = Join-Path $scyllaDir 'HookLibraryx64.dll' }

            $runs = @()
            $runs += ,@{ Mode = 'L1 裸跑'; Inject = $false }
            if (Test-Path $cdb) { $runs += ,@{ Mode = 'L2 挂 cdb'; Inject = $false } }
            if ((Test-Path $cdb) -and $hookDll -and (Test-Path $hookDll)) {
                $runs += ,@{ Mode = 'L3 注入后'; Inject = $true }
            }

            $series = @{}
            foreach ($run in $runs) {
                $tag    = ($run.Mode -replace '[^0-9A-Za-z]', '')
                $sout   = Join-Path $work ("adbg-" + $tag + ".out")
                $cdbcf  = Join-Path $work ("cdb-" + $tag + ".txt")
                $cdbout = Join-Path $work ("cdb-" + $tag + ".cdbout")
                Remove-Item $sout -Force -ErrorAction SilentlyContinue

                $proc = $null
                $dbg  = $null
                try {
                    $proc = Start-Process -FilePath $adbE -PassThru -WindowStyle Hidden `
                                -RedirectStandardOutput $sout -RedirectStandardError ($sout + '.err')
                    Start-Sleep -Seconds 2
                    if (-not $proc.HasExited) {
                        if ($run.Inject) {
                            # ★ attach 之后才注入 —— 这才是「同一进程里检测翻转」的真实验证
                            if (Test-Path $cdb) {
                                "g`n.echo SETUPLENV_RELEASED`nq`n" | Set-Content -LiteralPath $cdbcf -Encoding ASCII
                                $dbg = Start-Process -FilePath $cdb `
                                        -ArgumentList @('-cf', $cdbcf, '-p', "$($proc.Id)") `
                                        -NoNewWindow -PassThru `
                                        -RedirectStandardOutput $cdbout -RedirectStandardError ($cdbout + '.err')
                                Start-Sleep -Seconds 6
                            }
                            $injf = Join-Path $work ("inj-" + $tag + ".txt")
                            $inj = Start-Process -FilePath $scylla `
                                    -ArgumentList @("pid:$($proc.Id)", $hookDll) `
                                    -NoNewWindow -Wait -PassThru `
                                    -RedirectStandardOutput $injf -RedirectStandardError ($injf + '.err')
                            $ij = ''
                            if (Test-Path $injf) { $ij = Get-Content $injf -Raw -ErrorAction SilentlyContinue }
                            # ★ 判据是 Hook injection successful，不是 Loaded VA
                            #   —— 后者是注入器用法横幅里的样例文本，用错语法时也会出现
                            if ($ij -notmatch 'Hook injection successful') {
                                Write-Warn2 'ScyllaHide 注入未成功（输出无 Hook injection successful）'
                                Write-Warn2 '正确语法：InjectorCLIx64 pid:<id> <HookLibraryx64.dll>，不是 -p <id> [ini]'
                            }
                            if ($dbg) { $null = $dbg.WaitForExit(30000) }
                        }
                        elseif ($run.Mode -like 'L2*') {
                            "g`n.echo SETUPLENV_RELEASED`nq`n" | Set-Content -LiteralPath $cdbcf -Encoding ASCII
                            $dbg = Start-Process -FilePath $cdb `
                                    -ArgumentList @('-cf', $cdbcf, '-p', "$($proc.Id)") `
                                    -NoNewWindow -PassThru `
                                    -RedirectStandardOutput $cdbout -RedirectStandardError ($cdbout + '.err')
                            $null = $dbg.WaitForExit(25000)
                        }
                        else {
                            $null = $proc.WaitForExit(30000)
                        }
                    }
                    Start-Sleep -Milliseconds 800
                    try { if (-not $proc.HasExited) { $proc.Kill() } } catch { }
                } catch {
                    Write-Warn2 ("$($run.Mode) 执行异常: " + $_.Exception.Message)
                    try { if ($proc -and -not $proc.HasExited) { $proc.Kill() } } catch { }
                }

                $got = @()
                if (Test-Path $sout) {
                    $got = @(Get-Content $sout -ErrorAction SilentlyContinue | Where-Object { $_ -match 'SAMPLE' })
                }
                $series[$run.Mode] = $got
                $one = @($got | Where-Object { $_ -match 'peb=1' }).Count
                Write-Host ("  {0,-14} 样本 {1,3} 条，检测到调试器 {2,3} 条" -f $run.Mode, $got.Count, $one) -ForegroundColor DarkGray
            }

            # ── L1：裸跑必须全 0，否则探针本身有问题，后两层无意义
            $l1    = @($series['L1 裸跑'])
            $l1one = @($l1 | Where-Object { $_ -match 'peb=1' }).Count
            Add-Gate '门3' 'L1 裸跑检测全 0' ($l1.Count -gt 0 -and $l1one -eq 0) `
                "$($l1.Count) 条样本，peb=1 的有 $l1one 条（应为 0）"

            # ── L2：挂上调试器后必须翻转 —— 证明探针真的能看见调试器
            $l2    = @($series['L2 挂 cdb'])
            $l2one = @($l2 | Where-Object { $_ -match 'peb=1' }).Count
            Add-Gate '门3' 'L2 挂 cdb 检测翻转' ($l2.Count -gt 0 -and $l2one -gt 0) `
                "$($l2.Count) 条样本，peb=1 的有 $l2one 条（应 > 0）"

            # ── L3：注入 ScyllaHide 后尾部必须回落 —— 证明反制真在工作
            $l3 = @($series['L3 注入后'])
            if ($l3.Count -eq 0) {
                Add-Gate '门3' 'L3 注入后检测回落' $false '未执行（缺 cdbX64 或 HookLibraryx64.dll）'
            } else {
                $l3one = @($l3 | Where-Object { $_ -match 'peb=1' }).Count
                $tail  = @($l3 | Select-Object -Last 5)
                $tailOne = @($tail | Where-Object { $_ -match 'peb=1' }).Count
                $flipped = ($l3one -gt 0) -and ($tailOne -eq 0)
                Add-Gate '门3' 'L3 注入后检测回落' $flipped `
                    "全程 $($l3.Count) 条中 peb=1 有 $l3one 条；尾部 5 条中 $tailOne 条（应为 0）"
            }
        }
    }

    # ── 门 4 · 工具根变量无死路径 ────────────────────────────────────────────
    Write-Step '门4 · 工具根变量无死路径'
    # ★ 不要在 ForEach-Object 里用 return（只退出当次迭代，等于 continue）——§5 门4
    # ★ 不要把「含反斜杠的每个分号段」都当路径：_NT_SYMBOL_PATH 这类值是
    #   srv*D:\symbols*https://msdl.microsoft.com/download/symbols 这种
    #   符号服务器规格串，第一段 D:\symbols 才是路径，后两段不是（§5 门4 的原样搬运会误报）。
    $dead = New-Object System.Collections.Generic.List[string]
    try {
        $reg = Get-ItemProperty 'HKCU:\Environment' -ErrorAction SilentlyContinue
        foreach ($prop in $reg.PSObject.Properties) {
            $name = $prop.Name
            if ($name -match '^PS') { continue }        # 跳过 PS* 内部变量
            $val  = [string]$prop.Value
            if ($val -notmatch '\\') { continue }       # 值里没有路径，跳过
            foreach ($seg in ($val -split ';')) {
                $p = $seg.Trim()
                # 带 * 的符号服务器规格串：只校验第一段，其余是 URL / 缓存名
                if ($p -like '*`**') {
                    $p = ($p -split '`*')[0].Trim()
                    if ($p -like 'srv*') { $p = ($p -split '`*')[1].Trim() }
                }
                if (-not $p) { continue }
                if ($p -notmatch '^[A-Za-z]:\\') { continue }   # 只认真盘符路径
                if (-not (Test-Path -LiteralPath $p -ErrorAction SilentlyContinue)) { $dead.Add("$name = $p") }
            }
        }
    } catch { }
    Add-Gate '门4' 'HKCU 环境变量无死路径' ($dead.Count -eq 0) `
        $(if ($dead.Count -eq 0) { '0 条死路径（符号服务器规格串已排除）' } else { ($dead -join ' ; ') })

    # ── 门 5 · 汇总 ───────────────────────────────────────────────────────────
    Write-Step '门5 · 需要主人决定的（四类阻塞）'
    if ($script:Blockers.Count -eq 0) {
        Write-Host '  （当前 0 项阻塞）' -ForegroundColor Green
    } else {
        Write-Host $script:Blockers.Count.ToString() + ' 项阻塞，详见文末表格' -ForegroundColor Yellow
    }
}

function Resolve-AcceptTool {
    param([Parameter(Mandatory=$true)][string]$Id)
    # 优先用探测层（4 级），退到工具根直查
    if ($script:Boot) {
        try { . $script:Boot; $r = Resolve-ReverseToolSpec -Name $Id; if ($r -and $r.Available) { return $r.Command } } catch { }
    }
    $fallback = $script:ToolFallback[$Id]
    if ($fallback) {
        $p = Find-ToolExe $fallback
        if ($p) { return $p }
    }
    $c = Get-Command $Id -ErrorAction SilentlyContinue
    if ($c) { return $c.Source }
    return $null
}

# ═════════════════════════════════════════════════════════════════════════════
# 报告（§7 模板）
# ═════════════════════════════════════════════════════════════════════════════
function Write-Report {
    $el = ((Get-Date) - $script:Started).TotalSeconds

    Write-Host ''
    Write-Host ('=' * 78) -ForegroundColor DarkCyan
    Write-Host " 【装了什么】 用时 $([math]::Round($el,1))s，共 $($script:Actions.Count) 项动作" -ForegroundColor Cyan
    Write-Host ('=' * 78) -ForegroundColor DarkCyan
    $script:Actions | Group-Object 阶段 | ForEach-Object {
        Write-Host ("  [{0}] {1} 项" -f $_.Name, $_.Count) -ForegroundColor Cyan
        $_.Group | ForEach-Object { Write-Host ("     {0,-34} {1}" -f $_.项目, $_.结果) -ForegroundColor DarkGray }
    }

    Write-Host ''
    Write-Host ('=' * 78) -ForegroundColor DarkCyan
    Write-Host ' 【摸底结果】' -ForegroundColor Cyan
    Write-Host ('=' * 78) -ForegroundColor DarkCyan
    $script:Findings | ForEach-Object {
        Write-Host ("  {0,-22} {1}" -f $_.项, $_.值) -ForegroundColor DarkGray
    }

    Write-Host ''
    Write-Host ('=' * 78) -ForegroundColor DarkCyan
    Write-Host ' 【验收结果】' -ForegroundColor Cyan
    Write-Host ('=' * 78) -ForegroundColor DarkCyan
    $pass = @($script:GateResults | Where-Object { $_.结果 -eq 'PASS' }).Count
    $fail = @($script:GateResults | Where-Object { $_.结果 -eq 'FAIL' }).Count
    if ($script:GateResults.Count -eq 0) {
        Write-Host '  （本次未跑验收门 —— 加 -VerifyOnly 跑）' -ForegroundColor DarkYellow
    } else {
        Write-Host ("  通过 $pass / $($script:GateResults.Count)（未通过 $fail）") -ForegroundColor $(if($fail -eq 0){'Green'}else{'Yellow'})
        $script:GateResults | ForEach-Object {
            $c = if ($_.结果 -eq 'PASS') { 'Green' } else { 'Red' }
            Write-Host ("   {0}  {1,-10} {2,-24} {3}" -f $_.结果, $_.门, $_.检查项, $_.证据) -ForegroundColor $c
        }
    }

    Write-Host ''
    Write-Host ('=' * 78) -ForegroundColor DarkCyan
    Write-Host " 【需要主人决定】 $($script:Blockers.Count) 项（只可能是这四类：商业许可 / 账号登录 / 管理员 / 两条路都不通）" -ForegroundColor Cyan
    Write-Host ('=' * 78) -ForegroundColor DarkCyan
    if ($script:Blockers.Count -eq 0) {
        Write-Host '  当前无阻塞。' -ForegroundColor Green
    } else {
        $script:Blockers | Format-Table -AutoSize -Wrap | Out-String -Width 200 | Write-Host
    }

    Write-Host ''
    Write-Host ' 【我自己做的决定】' -ForegroundColor Cyan
    Write-Host ('   工具根     : {0}（D:\Tools 不存在时按 §2.5.3 换实际盘符）' -f $script:ToolRoot)
    Write-Host ('   pip 生态   : {0}（独立 venv，绝不污染系统 Python）' -f $script:VenvPath)
    Write-Host '   .NET 工具  : ilspycmd 锁 9.1.0.7988（10.x/11.x 需 .NET 10，§4.2）'
    Write-Host '   WinDbg     : 只认 app execution alias，绝不加进 PATH（§6.2）'
    Write-Host '   capa       : 官方 exe + 独立规则目录；不换 PyPI 残包（§4.1）'
    Write-Host ''
    Write-Host ' 未通过项没有用「已完成」覆盖 —— 见上方【验收结果】里的 FAIL 行（§7）。'
    Write-Host ''
}

# ═════════════════════════════════════════════════════════════════════════════
# 主流程
# ═════════════════════════════════════════════════════════════════════════════
$script:ToolRoot   = $ToolRoot
$script:IsAdmin    = $false
$script:Boot       = $null
$script:IdaDir     = $null
$script:EsExe      = $null
$script:WorkDir    = Join-Path $env:TEMP 'setup-env'
$script:ToolFallback = @{
    gcc              = 'runtime\mingw64\bin\gcc.exe'
    upx              = 'UPX\upx.exe'
    diec             = 'DIE\diec.exe'
    floss            = 'cli\floss.cmd'
    capa             = 'capa\capa.bat'
    scyllahide       = 'ScyllaHide\InjectorCLIx64.exe'
    analyzeHeadless  = 'Ghidra\support\analyzeHeadless.bat'
    yara             = 'yara\yara64.exe'
    r2               = 'radare2\bin\r2.exe'
    'pe-sieve'       = 'pe-sieve\pe-sieve64.exe'
}

Write-Host ''
Write-Host '############################################################' -ForegroundColor DarkCyan
Write-Host '#  relab2 新机逆向环境一键建设                             #' -ForegroundColor Cyan
Write-Host '############################################################' -ForegroundColor DarkCyan
Write-Host (" 模式     : " + $(if ($DryRun) { 'DryRun（只打印，不执行）' }
                        elseif ($VerifyOnly) { 'VerifyOnly（只跑验收门）' }
                        else { '全量建设' })) -ForegroundColor Yellow
Write-Host (" 跳过商业 : " + $(if ($SkipCommercial) { '是' } else { '否' })) -ForegroundColor Yellow
Write-Host (" 工作目录 : " + $script:WorkDir) -ForegroundColor DarkGray
Write-Host (" 脚本BOM  : " + $((Get-Content -LiteralPath $PSCommandPath -Encoding Byte -TotalCount 3 -EA SilentlyContinue) -join ' ')) -ForegroundColor DarkGray

# ── 工具根定位（§2.5.3：磁盘不是 D 盘就换位置）────────────────────────────────
if (-not $script:ToolRoot) {
    $cands = @('D:\Tools','C:\Tools',"$env:LOCALAPPDATA\Tools")
    $script:ToolRoot = $null
    foreach ($c in $cands) { if (Test-Path -LiteralPath $c -ErrorAction SilentlyContinue) { $script:ToolRoot = $c; break } }
    if (-not $script:ToolRoot) {
        $root = [IO.Path]::GetPathRoot($env:SystemRoot)          # 例：C:\
        $script:ToolRoot = Join-Path $root 'Tools'
    }
}
if (-not $VenvPath) { $VenvPath = Join-Path $script:ToolRoot 'runtime\python-venv' }
$script:VenvPath = $VenvPath

# ── 反反调试探针源码（门 3 用；放在工作目录，不污染仓库）─────────────────────
$script:AdbgExe = Join-Path $script:WorkDir 'adbg.exe'

# 工作目录
if (-not $DryRun) {
    try {
        New-Item -ItemType Directory -Force -Path $script:WorkDir | Out-Null
        # 反调试探针源码：★ x64 上 mov %fs:0x30 不可用，必须 __readgsqword(0x60)（§6.6）
        # 反调试探针源码：★ x64 上 mov %fs:0x30 不可用，必须 __readgsqword(0x60)（§6.6）
        # 每条样本带 T= 序号，是门 3 能分清「裸跑段 / 调试器段 / 注入后段」的关键；
        # 而且必须 fflush —— 注入是「往活进程里塞 DLL」，不刷新缓冲区就永远看不到后面几条。
        $adbgC = Join-Path $script:WorkDir 'adbg.c'
        $adbgSrc = @'
#include <stdio.h>
#include <windows.h>
#include <winternl.h>
static void samp(void){
  int peb=0, crdp=0, dbg=0;
  /* PEB.BeingDebugged —— x64 上段前缀 mov %fs:0x30 不可用，走 gs:0x60 偏移读 */
  { char *p; __asm__ __volatile__("movq %%gs:0x60, %0":"=r"(p)); peb = (int)*(p+2); }
  { BOOL r=FALSE; crdp = (CheckRemoteDebuggerPresent(GetCurrentProcess(), &r) && r) ? 1 : 0; }
  { HMODULE n=GetModuleHandleA("ntdll.dll");
    typedef NTSTATUS (WINAPI *QIP)(HANDLE,ULONG,PVOID,ULONG,PULONG);
    QIP q=(QIP)GetProcAddress(n,"NtQueryInformationProcess");
    if(q){ ULONG_PTR d=0; if(q(GetCurrentProcess(),7,&d,sizeof(d),NULL)==0 && d) dbg=1; } }
  printf("SAMPLE peb=%d crdp=%d dbgport=%d\n", peb, crdp, dbg);
  fflush(stdout);
}
int main(void){
  /* 裸跑     : 全 0
     挂调试器 : 变 1，证明探针能看见调试器
     注入后   : 回落到 0，证明反制在工作  —— 200 次 * 500ms = 100s 足够长 */
  for (int i=0;i<200;i++){ printf("T=%03d ", i); samp(); Sleep(500); }
  return 0;
}
'@
        [System.IO.File]::WriteAllText($adbgC, $adbgSrc, (New-Object System.Text.ASCIIEncoding))
    } catch { Write-Warn2 "工作目录准备失败: $($_.Exception.Message)" }
}

# ── 建设流程 ──────────────────────────────────────────────────────────────────
Invoke-Survey

# 探测层要先加载，后面 §4.1 与验收门都依赖它
foreach ($c in @(
    (Join-Path $PSScriptRoot 'skillpack\skills\scripts\lib\Bootstrap.ps1'),
    (Join-Path $env:REVERSE_SKILL_ROOT 'skillpack\skills\scripts\lib\Bootstrap.ps1')
)) {
    if ($c -and (Test-Path -LiteralPath $c -ErrorAction SilentlyContinue)) { $script:Boot = $c; break }
}

# 找 IDA 目录（验收门要用）
foreach ($p in (Get-IdaInstallCandidates -ToolRoot $script:ToolRoot)) {
    if (Test-Path -LiteralPath $p -ErrorAction SilentlyContinue) { $script:IdaDir = $p; break }
}

if ($VerifyOnly) {
    Write-Step 'VerifyOnly：跳过全部建设动作，直接跑 §5 验收门'
    Invoke-AcceptanceGates
} else {
    if (-not $DryRun) {
        Invoke-FullDiskScan
        Install-BaseRuntimes
        Install-ReverseTools
        Install-DotNetTools
        Install-PipEcosystem
        Install-YaraRules
        Register-ToolRoot
        Invoke-CommercialTools
        Invoke-McpChannels
    } else {
        Write-Step 'DryRun：只打印将要做什么'
        Write-Host '  [§2.7] 全盘扫已装 —— 用 es.exe 探测下列条目：' -ForegroundColor DarkCyan
        foreach ($p in $script:ProbeList) { Write-Host "           $p" -ForegroundColor DarkGray }
        Write-Host '' -ForegroundColor DarkCyan
        Write-Host '  [§3.3] 基础运行时（已装则跳过）—— winget 包 id：' -ForegroundColor DarkCyan
        foreach ($r in $script:Runtimes) { Write-Host ("           {0,-28} ({1})" -f $r.Id, $r.Note) -ForegroundColor DarkGray }
        Write-Host "           Insecure.Npcap            (抓包驱动，需管理员)" -ForegroundColor DarkGray
        Write-Host '' -ForegroundColor DarkCyan
        Write-Host '  [§4.1] 逆向工具链 —— GitHub releases 直装：' -ForegroundColor DarkCyan
        foreach ($a in @(
            @('upx/upx','win64.zip -> UPX\upx.exe'),
            @('radareorg/radare2','w64.zip -> radare2\bin\r2.exe'),
            @('hasherezade/pe-sieve','pe-sieve64.exe -> pe-sieve\'),
            @('winsiderss/scyllahide','zip -> ScyllaHide\InjectorCLIx64.exe'),
            @('NationalSecurityAgency/ghidra','PUBLIC_*.zip -> Ghidra\support\analyzeHeadless.bat')
        )) { Write-Host ("           {0,-34} {1}" -f $a[0], $a[1]) -ForegroundColor DarkGray }
        Write-Host '           x64dbg                    GUI 工具，仅登记文件在位（§6.2 headless 是空壳）' -ForegroundColor DarkGray
        Write-Host '           capa                      官方 exe + 独立规则目录（不换 PyPI 残包）' -ForegroundColor DarkGray
        Write-Host '           flare-floss               独立 venv（Scripts 绝不能进 PATH）' -ForegroundColor DarkGray
        Write-Host '' -ForegroundColor DarkCyan
        Write-Host '  [§4.2] .NET   ilspycmd 锁 9.1.0.7988 / de4dot / dnSpy.Console / Confuser.CLI（绿色版人工放置）' -ForegroundColor DarkCyan
        Write-Host ("  [§4.3] pip    venv = {0}" -f $VenvPath) -ForegroundColor DarkCyan
        Write-Host ("           {0}" -f ($script:VenvPyPkgs -join ' ')) -ForegroundColor DarkGray
        Write-Host '  [§4.4] 规则   Yara-Rules/rules -> yara\yara-rules（gh clone，失败退 curl tarball）' -ForegroundColor DarkCyan
        Write-Host '  [§4.5] 登记   写 User 级 REVERSE_SKILL_ROOT / REVERSE_TOOL_ROOT（绝不写 Machine，R2）' -ForegroundColor DarkCyan
        Write-Host '  [§4.6] 商业   IDA headless 实跑 / relab-tools 7z 分卷 SHA256 校验后解压' -ForegroundColor DarkCyan
        Write-Host '  [§2.8] MCP    读 mcp.json 逐个 server 做 initialize + tools/list 握手' -ForegroundColor DarkCyan
        Write-Host '  [§5]   验收   门1 自检 / 门2 端到端 / 门3 反调试翻转 / 门4 死路径 / 门5 攒 blocker' -ForegroundColor DarkCyan
        Add-Action 'DryRun' '全部建设动作' '未执行（-DryRun）'
    }

    Write-Host ''
    Write-Step '收尾：跑 §5 验收门'
    if ($DryRun) {
        Write-Dry 'DryRun 模式跳过验收门；跑 .\setup-env.ps1 -VerifyOnly 真跑'
    } else {
        Invoke-AcceptanceGates
    }
}

Write-Report

# ── 收尾清理 ──────────────────────────────────────────────────────────────────
if (-not $KeepWork -and -not $DryRun) {
    try { Remove-Item -LiteralPath $script:WorkDir -Recurse -Force -ErrorAction SilentlyContinue } catch { }
}

# 退出码：有 FAIL 门 或 有阻塞 → 1，其余 0
$failed = @($script:GateResults | Where-Object { $_.结果 -eq 'FAIL' }).Count
if ($failed -gt 0 -or $script:Blockers.Count -gt 0) { exit 1 } else { exit 0 }