#Requires -Version 5.1
<#
relab2.ps1 —— 本仓库的唯一门面（对齐 REA 的 setup / doctor / update 三件套）

为什么存在（2026-10-15）：
  仓库里部署零件齐全（relab2-root / setup / selfcheck / register-skills / switch-mcp /
  kernel 工作台），但没有统一入口、也没有 doctor —— 人得知道要按什么顺序跑哪几个脚本，
  顺序与注意点散在 5 份文档里。这就是「换机很麻烦、没有稳定性、不像开源项目」的真相。
  本文件只做**门面**：解析参数 → 调用既有脚本 → 汇总成一张表。不复制它们的逻辑。

用法：
  powershell -NoProfile -ExecutionPolicy Bypass -File relab2.ps1 doctor
  powershell -NoProfile -ExecutionPolicy Bypass -File relab2.ps1 setup -DryRun
  powershell -NoProfile -ExecutionPolicy Bypass -File relab2.ps1 setup
  powershell -NoProfile -ExecutionPolicy Bypass -File relab2.ps1 update

约定：
  · 本文件不写任何盘符绝对路径（环境初始化.md §10）。仓根一律由 $PSScriptRoot 推导。
  · doctor 只读，不改任何东西；退出码 0 = 就绪，1 = 未就绪。
  · setup 幂等，带 -DryRun 预览，不碰用户未授权的机器级状态。
#>
[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet('doctor', 'setup', 'update', 'help')]
    [string] $Command = 'help',

    [switch] $DryRun,
    [switch] $Json
)

$ErrorActionPreference = 'Continue'
# ★ 2026-10-15：子进程（powershell 5.1）把 UTF-8 写到管道，父进程若按控制台码页（936）解码，
#   中文会变成乱码（实测：stdio·懒启动 → stdio路鎳掑惎）。先把父进程的解码器钉成 UTF-8。
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }
$OutputEncoding = [System.Text.Encoding]::UTF8
$RepoRoot = $PSScriptRoot
$Results = New-Object System.Collections.Generic.List[object]

function Add-Result([string]$Name, [string]$Status, [string]$Detail) {
    $script:Results.Add([pscustomobject]@{ 项 = $Name; 结果 = $Status; 说明 = $Detail })
    $color = switch ($Status) { 'OK' { 'Green' } 'WARN' { 'Yellow' } 'FAIL' { 'Red' } default { 'Gray' } }
    Write-Host ("  [{0,-4}] {1,-26} {2}" -f $Status, $Name, $Detail) -ForegroundColor $color
}

function Write-Head([string]$t) { Write-Host "`n=== $t ===" -ForegroundColor Cyan }

function Invoke-Step {
    param([string]$File, [string[]]$ArgList, [string]$Label)
    $p = Join-Path $RepoRoot $File
    if (-not (Test-Path -LiteralPath $p)) { Add-Result $Label 'FAIL' "缺少脚本 $File"; return 1 }
    if ($DryRun) { Write-Host ("  [DryRun] 将执行: {0} {1}" -f $File, ($ArgList -join ' ')) -ForegroundColor Yellow; return 0 }
    Write-Host ("  -> {0} {1}" -f $File, ($ArgList -join ' ')) -ForegroundColor DarkGray
    & powershell -NoProfile -ExecutionPolicy Bypass -File $p @ArgList
    return $LASTEXITCODE
}

# ---------------------------------------------------------------- doctor
function Invoke-Doctor {
    Write-Head 'relab2 doctor —— 本机现在能不能干活'

    # 1 仓根
    if (Test-Path -LiteralPath (Join-Path $RepoRoot 'skillpack\skills\MASTER-ROUTING.md')) {
        Add-Result '仓根' 'OK' $RepoRoot
    }
    else {
        Add-Result '仓根' 'FAIL' "这里不像本仓库根（缺 skillpack\skills\MASTER-ROUTING.md）: $RepoRoot"
        return 1
    }

    # 2 环境变量
    $sk = $env:REVERSE_SKILL_ROOT
    $tk = $env:REVERSE_TOOL_ROOT
    if ($sk) {
        # ★ 2026-10-15：环境变量指向**另一棵树**时必须报出来 —— 否则在异地克隆里跑 doctor，
        #   它会报「仓根 = 这份 clone」，而模型实际用的是环境变量指的那棵树，两边不是一个东西。
        if ($sk.TrimEnd('\') -ieq $RepoRoot.TrimEnd('\')) {
            Add-Result 'REVERSE_SKILL_ROOT' 'OK' $sk
        }
        else {
            Add-Result 'REVERSE_SKILL_ROOT' 'FAIL' "指向另一棵树（$sk），而本脚本在 $RepoRoot —— 模型实际用的是前者。要么改环境变量，要么别在这份 clone 里跑。"
        }
    }
    else { Add-Result 'REVERSE_SKILL_ROOT' 'WARN' '未设置（跑 setup 或 relab2-root.ps1）' }
    if ($tk) { Add-Result 'REVERSE_TOOL_ROOT' 'OK' $tk } else { Add-Result 'REVERSE_TOOL_ROOT' 'WARN' '未设置（跑 setup）' }

    # 3 部署自检（selfcheck 的退出码就是结论）
    $sc = Join-Path $RepoRoot 'selfcheck.ps1'
    if (Test-Path -LiteralPath $sc) {
        $out = & powershell -NoProfile -ExecutionPolicy Bypass -File $sc 2>&1
        if ($LASTEXITCODE -eq 0) { Add-Result '部署自检 selfcheck' 'OK' '退出码 0' }
        else { Add-Result '部署自检 selfcheck' 'FAIL' ("退出码 $LASTEXITCODE —— 见下方原始输出"); $out | Select-Object -Last 25 | ForEach-Object { Write-Host "      $_" -ForegroundColor DarkGray } }
    }
    else { Add-Result '部署自检 selfcheck' 'FAIL' '缺少 selfcheck.ps1' }

    # 4 MCP 通道
    $mcp = Join-Path $RepoRoot 'skillpack\skills\scripts\mcp-status.ps1'
    if (Test-Path -LiteralPath $mcp) {
        $lines = & powershell -NoProfile -ExecutionPolicy Bypass -File $mcp 2>&1
        $reg = @($lines | Where-Object { $_ -match '^\s*\S+\s+\S+\s+(stdio|http)' })
        $closed = @($reg | Where-Object { $_ -match 'closed' })
        Add-Result 'MCP 通道' 'OK' ("已注册 {0} 条（{1} 条 http 待按需启动）" -f $reg.Count, $closed.Count)
        foreach ($l in $reg) { Write-Host ("      " + $l.Trim()) -ForegroundColor DarkGray }
    }
    else { Add-Result 'MCP 通道' 'FAIL' '缺少 skills\scripts\mcp-status.ps1' }

    # 5 技能挂载（一份实体 N 个 junction）
    $rs = Join-Path $RepoRoot 'skillpack\skills\scripts\register-skills.ps1'
    if (Test-Path -LiteralPath $rs) {
        $o = & powershell -NoProfile -ExecutionPolicy Bypass -File $rs -Doctor 2>&1
        if ($LASTEXITCODE -eq 0) { Add-Result '技能挂载' 'OK' '各智能体技能目录已挂上' }
        else { Add-Result '技能挂载' 'WARN' ("退出码 $LASTEXITCODE（未装智能体的目录会被跳过，属正常）"); $o | Select-Object -Last 12 | ForEach-Object { Write-Host "      $_" -ForegroundColor DarkGray } }
    }
    else { Add-Result '技能挂载' 'FAIL' '缺少 register-skills.ps1' }

    # 6 技能卡与门禁清单
    $cards = @(Get-ChildItem -LiteralPath (Join-Path $RepoRoot 'skillpack\skills') -Directory -ErrorAction SilentlyContinue |
        Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'SKILL.md') })
    if ($cards.Count -ge 40) { Add-Result '技能卡' 'OK' ("$($cards.Count) 张") } else { Add-Result '技能卡' 'FAIL' ("只有 $($cards.Count) 张，异常") }

    $gates = Join-Path $RepoRoot 'skillpack\skills\tests\ci-gates.json'
    if (Test-Path -LiteralPath $gates) {
        try { $n = (Get-Content -LiteralPath $gates -Raw -Encoding UTF8 | ConvertFrom-Json).gates.Count; Add-Result '门禁清单' 'OK' "$n 道" }
        catch { Add-Result '门禁清单' 'FAIL' 'ci-gates.json 解析失败' }
    }
    else { Add-Result '门禁清单' 'FAIL' '缺少 ci-gates.json' }

    # 7 破甲卡（铁律：不许含工序 / 工具路径）
    $baseDir = Join-Path $RepoRoot 'kernel\04-console\cards\base'
    if (Test-Path -LiteralPath $baseDir) {
        $baseCards = @(Get-ChildItem -LiteralPath $baseDir -Filter *.md -ErrorAction SilentlyContinue)
        Add-Result '破甲卡' 'OK' ("$($baseCards.Count) 张（工序/工具路径判据见要求门 R1）")
    }
    else { Add-Result '破甲卡' 'WARN' '未找到 kernel\04-console\cards\base' }

    # 8 要求门（自带控制组）
    $req = Join-Path $RepoRoot 'skillpack\skills\tests\verify-project-requirements.py'
    if (Test-Path -LiteralPath $req) {
        $py = (Get-Command python -ErrorAction SilentlyContinue).Source
        if (-not $py) { $py = (Get-Command py -ErrorAction SilentlyContinue).Source }
        if ($py) {
            $o = & $py $req 2>&1
            if ($LASTEXITCODE -eq 0) { Add-Result '要求门 R1-R13' 'OK' '全过（含控制组）' }
            else { Add-Result '要求门 R1-R13' 'FAIL' ("退出码 $LASTEXITCODE"); $o | Select-Object -Last 15 | ForEach-Object { Write-Host "      $_" -ForegroundColor DarkGray } }
        }
        else { Add-Result '要求门 R1-R13' 'WARN' 'PATH 里没有 python，跳过' }
    }
    else { Add-Result '要求门 R1-R13' 'FAIL' '缺少 verify-project-requirements.py' }

    # 汇总
    $fail = @($Results | Where-Object { $_.结果 -eq 'FAIL' }).Count
    $warn = @($Results | Where-Object { $_.结果 -eq 'WARN' }).Count
    Write-Host ''
    if ($fail -eq 0 -and $warn -eq 0) {
        Write-Host ("就绪：全部通过（{0} 项）" -f $Results.Count) -ForegroundColor Green
        Write-Host '注意：doctor 只证明「本机配置就绪」，不证明「能力就绪」。能力只由真实验收证明。' -ForegroundColor DarkGray
        return 0
    }
    if ($fail -eq 0) {
        # ★ 2026-10-15：以前这里也印「全部通过」，等于把 WARN 说成全绿（审计实测：异地克隆里
        #   两个环境变量都没设，仍报「就绪：全部通过（10 项，0 项警告）」退出码 0）。改掉。
        Write-Host ("就绪，但带 {0} 项警告 —— 不是全绿。先看上面 WARN 的那几行。" -f $warn) -ForegroundColor Yellow
        return 0
    }
    Write-Host ("未就绪：{0} 项 FAIL，{1} 项 WARN —— 按上面的 FAIL 项处理后重跑。" -f $fail, $warn) -ForegroundColor Red
    return 1
}

# ---------------------------------------------------------------- setup / update
function Invoke-Setup {
    Write-Head 'relab2 setup —— 一键接入（幂等，可 -DryRun 预览）'
    $rc = 0

    Invoke-Step -File 'relab2-root.ps1' -ArgList @() -Label '仓根定位' | Out-Null
    if ($LASTEXITCODE -ne 0 -and -not $DryRun) { $rc = 1 }

    $a = @()
    if ($DryRun) { $a += '-DryRun' }
    Invoke-Step -File 'setup.ps1' -ArgList $a -Label '环境变量 + 自检' | Out-Null
    if ($LASTEXITCODE -ne 0 -and -not $DryRun) { $rc = 1 }

    $b = @()
    if ($DryRun) { $b += '-WhatIf' }
    Invoke-Step -File 'skillpack\skills\scripts\register-skills.ps1' -ArgList $b -Label '技能挂载（一份实体 N 个联接）' | Out-Null
    if ($LASTEXITCODE -ne 0 -and -not $DryRun) { $rc = 1 }

    # ---- MCP 一键注册（幂等 + 备份 + 干跑）----
    $mcpReg = Join-Path $RepoRoot 'skillpack\skills\scripts\register-mcp.py'
    if (Test-Path -LiteralPath $mcpReg) {
        $py = $null
        foreach ($cand in @(
                (Join-Path $env:REVERSE_TOOL_ROOT 'runtime\python-venv\Scripts\python.exe'),
                (Join-Path $env:REVERSE_TOOL_ROOT 'runtime\angr-mcp-venv\Scripts\python.exe'))) {
            if ($cand -and (Test-Path -LiteralPath $cand)) { $py = $cand; break }
        }
        if (-not $py) { $py = (Get-Command python -ErrorAction SilentlyContinue).Source }
        if ($py) {
            $mcpArgs = @($mcpReg, '--skill-root', $RepoRoot)
            if ($DryRun) { $mcpArgs += '--dry-run' }
            Write-Host '  MCP 注册（5 条通道，幂等 + 自动备份）' -ForegroundColor DarkGray
            # ★ 显式捕获再打印：直接 `& $py @args` 的输出在这个 PowerShell 里会被吞掉
            #   （2026-10-15 实测：调用方看不到任何输出，等于静默失败）。捕获 + 原样回显，错误也看得见。
            $mcpOut = & $py @mcpArgs 2>&1 | Out-String
            $mcpRc = $LASTEXITCODE
            if ($mcpOut.Trim()) { Write-Host $mcpOut.TrimEnd() }
            if ($mcpRc -ne 0 -and -not $DryRun) {
                Add-Result 'MCP 注册' 'WARN' "register-mcp.py 退出码 $mcpRc —— 见上方输出"
            }
        }
        else {
            Add-Result 'MCP 注册' 'WARN' 'PATH 与工具根里都没找到 python，跳过（见 环境初始化.md §11.1-B 第 10 条）'
        }
    }
    else {
        Add-Result 'MCP 注册' 'WARN' "缺少 $mcpReg，跳过"
    }

    Write-Host ''
    Write-Host '  还差最后一步（本脚本不代做）：把卡片载进宿主 —— 开 kernel\04-console\start-console.bat，' -ForegroundColor Yellow
    Write-Host '  选智能体 → 勾三段（中枢标记块 / 底模卡 / 客套指引卡）→ 载入。它会写你的入口文件、并留备份。' -ForegroundColor DarkGray

    if (-not $DryRun) {
        Write-Host ''
        Write-Host '  跑完请重跑一次 doctor 确认：' -ForegroundColor Cyan
        Write-Host '    powershell -NoProfile -ExecutionPolicy Bypass -File relab2.ps1 doctor' -ForegroundColor Cyan
    }
    return $rc
}

function Invoke-Update {
    Write-Head 'relab2 update —— 换机 / 升级同一条'
    if ($DryRun) { Write-Host '  [DryRun] git -C <仓根> pull --ff-only' -ForegroundColor Yellow }
    else {
        & git -C $RepoRoot pull --ff-only
        if ($LASTEXITCODE -ne 0) { Write-Host '  git pull 未成功（离线或有本地改动）—— 继续跑 setup。' -ForegroundColor Yellow }
    }
    return (Invoke-Setup)
}

function Show-Help {
    Write-Host @'
relab2 —— 本仓库唯一门面

  relab2 doctor          本机现在能不能干活（只读，退出码 0 = 就绪）
  relab2 setup           一键接入：仓根定位 → 环境变量 → 技能挂载（幂等）
  relab2 setup -DryRun   只打印将要执行的每一行，不改任何东西
  relab2 update          换机/升级：git pull → 重跑 setup

就绪之后：
  · 干活入口看 START-HERE.md
  · 卡片融合 / 跨智能体接入 开 kernel\04-console\start-console.bat
  · 完工台账看 docs\FINAL-彻底完工交接-2026-10-15.md
'@
}

switch ($Command) {
    'doctor' { exit (Invoke-Doctor) }
    'setup' { exit (Invoke-Setup) }
    'update' { exit (Invoke-Update) }
    default { Show-Help; exit 0 }
}
