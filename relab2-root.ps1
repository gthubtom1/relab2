#Requires -Version 5.1
<#
.SYNOPSIS
  零前置依赖地找到技能包根（换机第一入口）。不依赖任何已存在的环境变量。
.DESCRIPTION
  为什么要单独有它：
    换到一台新电脑时，环境变量 REVERSE_SKILL_ROOT 一定还没有；
    而 guest 卡里所有点火命令都写成 `$env:REVERSE_SKILL_ROOT\...`，
    环境变量没设 → 那条命令展开成 `\skillpack\skills\...` → 直接报错，
    链路在「点火」这一步就断了（本机 2026-10-09 实测复现）。

  这个脚本只做一件事：在没有任何线索的情况下，**找到并记住**技能包根。
  它是唯一的「必须先能跑起来」的东西，所以：
    - 只用 PowerShell 内建 cmdlet，不依赖仓内任何其它文件
    - 不依赖环境变量，不依赖 PATH，不依赖注册表
    - 找不到时**如实报错并给出三条处置办法**，而不是猜一个路径继续跑

  探测顺序（命中即停）：
    1. 环境变量 REVERSE_SKILL_ROOT（已 setup 过的情况）
    2. 常见安装位置的候选目录（含中文/空格路径）
    3. 全盘浅层搜索特征文件 TOOL-CHAIN.md（深度受限，避免慢）

.EXAMPLE
  # 交互式：打印结果并缓存到用户级环境变量
  powershell -NoProfile -ExecutionPolicy Bypass -File relab2-root.ps1

.EXAMPLE
  # 在别的脚本里取路径（静默，只输出路径；失败则退出码 1 且不输出）
  $root = & relab2-root.ps1 -Quiet
#>
[CmdletBinding()]
param(
    # 只输出解析出的路径，不打印过程信息
    [switch] $Quiet,

    # 解析成功后是否写入用户级环境变量（默认写；-NoCache 可关闭）
    [switch] $NoCache
)

$ErrorActionPreference = 'Stop'
$here = if ($PSScriptRoot) { $PSScriptRoot }
        else { Split-Path -Parent $MyInvocation.MyCommand.Path }

function Say([string]$m) { if (-not $Quiet) { Write-Host $m -ForegroundColor Cyan } }

# 判定一个候选目录「像不像技能包根」
# 指纹文件：skillpack/skills/scripts/master-route.ps1（点火入口，全包唯一）
function Test-SkillRoot([string]$p) {
    if ([string]::IsNullOrWhiteSpace($p)) { return $false }
    if (-not (Test-Path -LiteralPath $p -PathType Container -ErrorAction SilentlyContinue)) { return $false }
    foreach ($rel in @(
        'skillpack\skills\scripts\master-route.ps1',
        'skills\scripts\master-route.ps1'
    )) {
        if (Test-Path -LiteralPath (Join-Path $p $rel) -PathType Leaf -ErrorAction SilentlyContinue) { return $true }
    }
    return $false
}

Say '=== 技能包根定位（零前置依赖） ==='

# ── 1. 环境变量 ───────────────────────────────────────────────────────────────
$hit = ''
$envVal = [System.Environment]::GetEnvironmentVariable('REVERSE_SKILL_ROOT', 'Process')
if (-not [string]::IsNullOrWhiteSpace($envVal)) {
    $envVal = [System.IO.Path]::GetFullPath($envVal)
    if (Test-SkillRoot $envVal) {
        Say "1. 环境变量 REVERSE_SKILL_ROOT -> $envVal"
        $hit = $envVal
    } else {
        Say "1. 环境变量指向的目录不像技能包根（已忽略）：$envVal"
    }
}

# ── 2. 常见位置候选 ───────────────────────────────────────────────────────────
if (-not $hit) {
    Say '2. 试常见安装位置...'
    # 脚本自己在仓库根时它自己就是答案（最常见：clone 后直接跑）
    $candidates = New-Object System.Collections.Generic.List[string]
    $candidates.Add($here)
    foreach ($base in @('C:\', 'D:\')) {
        $candidates.Add((Join-Path $base 'relab2'))
        $candidates.Add((Join-Path $base 'Tools\relab2'))
        $candidates.Add((Join-Path $base 'repos\relab2'))
        $candidates.Add((Join-Path $base 'src\relab2'))
        $candidates.Add((Join-Path $base 'Projects\relab2'))
        $candidates.Add((Join-Path $base '项目\relab2'))
        $candidates.Add((Join-Path $base 'Tools\skills-hub'))
    }
    # 用户目录下常见的（桌面/文档/下载里的项目）
    $prof = [Environment]::GetFolderPath('UserProfile')
    if (-not [string]::IsNullOrWhiteSpace($prof)) {
        foreach ($sub in @('Desktop\哇', 'Desktop', 'Documents', 'Downloads')) {
            $candidates.Add((Join-Path $prof $sub))
        }
    }
    foreach ($c in $candidates) {
        if (Test-SkillRoot $c) {
            Say "2. 命中候选：$c"
            $hit = [System.IO.Path]::GetFullPath($c)
            break
        }
    }
    if (-not $hit) { Say '2. 常见位置都没命中' }
}

# ── 3. 浅层全盘搜特征文件 ─────────────────────────────────────────────────────
if (-not $hit) {
    Say '3. 浅层全盘搜特征文件（深度 3，可能十几秒）...'
    $sig = 'TOOL-CHAIN.md'
    $roots = New-Object System.Collections.Generic.List[string]
    foreach ($base in @('C:\', 'D:\')) {
        if (Test-Path -LiteralPath $base) { $roots.Add($base) }
    }
    $prof = [Environment]::GetFolderPath('UserProfile')
    if (-not [string]::IsNullOrWhiteSpace($prof)) { $roots.Add($prof) }

    $sw = [Diagnostics.Stopwatch]::StartNew()
    foreach ($r in $roots) {
        $found = $null
        try {
            $found = Get-ChildItem -LiteralPath $r -Filter $sig -Recurse -Depth 3 -File `
                        -Force -ErrorAction SilentlyContinue | Select-Object -First 1
        } catch { continue }
        if ($found) {
            # TOOL-CHAIN.md 在 skillpack/ 下，所以它的目录的上一级才是包根
            $pkg = Split-Path -Parent $found.Directory.FullName
            if (Test-SkillRoot $pkg) {
                Say ("3. 搜到：{0}（用时 {1:N1}s）" -f $pkg, $sw.Elapsed.TotalSeconds)
                $hit = [System.IO.Path]::GetFullPath($pkg)
                break
            }
        }
    }
    if (-not $hit) { Say '3. 搜索范围内没找到' }
}

# ── 结果 ─────────────────────────────────────────────────────────────────────
if (-not $hit) {
    Write-Host ''
    Write-Host '❌ 没能定位到技能包根。' -ForegroundColor Red
    Write-Host ''
    Write-Host '按下面顺序处理，**不要猜路径**：' -ForegroundColor Yellow
    Write-Host '  (a) 仓库还在，只是位置少见 —— 直接把它的绝对路径告诉我，例如'
    Write-Host '      C:\Users\<你>\Desktop\哇\relab2'
    Write-Host '  (b) 你把仓库挪走了 —— 找到那个目录，cd 进去，再跑一次本脚本（它会自己认出来）'
    Write-Host '  (c) 还没下载 —— 先 git clone 到上面 (a)/(b) 说的位置'
    Write-Host ''
    Write-Host '定位到之后，会自动写入用户级环境变量 REVERSE_SKILL_ROOT，'
    Write-Host '之后所有技能与卡片都能直接用，不需要再手动设。'
    exit 1
}

if (-not $NoCache) {
    try {
        [System.Environment]::SetEnvironmentVariable('REVERSE_SKILL_ROOT', $hit, 'User')
        Say "已缓存到用户级环境变量 REVERSE_SKILL_ROOT = $hit"
    } catch {
        Write-Warning "写用户级环境变量失败（不致命，本进程内已可用）：$_"
    }
}

if ($Quiet) {
    Write-Output $hit          # 唯一一行输出 = 纯路径，便于 $( ) 捕获
} else {
    Write-Host ''
    Write-Host '=== 定位完成 ===' -ForegroundColor Green
    Write-Host "技能包根: $hit" -ForegroundColor Green
    Write-Host ''
    Write-Host '下一步 —— 点火（把 <任务> 换成用户原话）：' -ForegroundColor Cyan
    Write-Host ('  powershell -NoProfile -ExecutionPolicy Bypass -File "{0}\skillpack\skills\scripts\master-route.ps1" -Hint "<任务>"' -f $hit)
    Write-Host '  或先跑一次自检：'
    Write-Host ('  powershell -NoProfile -ExecutionPolicy Bypass -File "{0}\selfcheck.ps1"' -f $hit)
}
exit 0
