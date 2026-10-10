#Requires -Version 5.1
# Lightweight scope gate before ACT. Exit 0 = ok, 2 = not ready, 1 = usage/error.
# Usage:
#   powershell -File skills/scripts/case-guard.ps1 -CaseRoot work\my-case
#   powershell -File skills/scripts/case-guard.ps1 -CaseRoot work\my-case -Force   # compatibility flag; never bypasses scope hard gates
param(
    [Parameter(Mandatory = $true)]
    [string] $CaseRoot,

    [switch] $Force,
    [switch] $Quiet
)
# ★ PSModulePath 自愈（2026-10-10 注入，路径由 inject-psmp.py 统一计算）：剔除 WindowsApps 版 PowerShell 7 的模块目录，否则 PS 5.1 会因 TypeData 重复定义失败而使 Get-FileHash / Get-ExecutionPolicy 不可用（已造成两次假绿 + 一次失败被吞）。重算/迁移后请重跑 work/envinit/inject-psmp.py
# ★ 2026-10-10 去掉硬编码 `C:\relab2\...` 绝对路径。
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
$ErrorActionPreference = 'Stop'

function Write-Info([string] $m) {
    if (-not $Quiet) { Write-Host $m }
}

if (-not (Test-Path -LiteralPath $CaseRoot)) {
    Write-Host ("ERROR: CaseRoot missing: {0}" -f $CaseRoot) -ForegroundColor Red
    exit 1
}

$scopePath = Join-Path $CaseRoot 'scope.md'
if (-not (Test-Path -LiteralPath $scopePath)) {
    Write-Host ("ERROR: scope.md missing under {0}" -f $CaseRoot) -ForegroundColor Red
    exit 1
}

$scope = Get-Content -LiteralPath $scopePath -Raw -Encoding UTF8
$issues = New-Object System.Collections.Generic.List[string]

function Get-ScopeSection([string] $Text, [string] $Name) {
    $pattern = '(?ms)^##\s*' + [regex]::Escape($Name) + '\s*\r?\n(?<body>.*?)(?=^##\s|\z)'
    $match = [regex]::Match($Text, $pattern)
    if ($match.Success) { return $match.Groups['body'].Value }
    return ''
}

function Get-SectionField([string] $Section, [string] $Name) {
    $pattern = '(?m)^\s*-\s*' + [regex]::Escape($Name) + ':\s*(?<value>.*?)\s*$'
    $match = [regex]::Match($Section, $pattern)
    if ($match.Success) { return $match.Groups['value'].Value.Trim() }
    return ''
}

$authSection = Get-ScopeSection -Text $scope -Name 'auth'
$networkSection = Get-ScopeSection -Text $scope -Name 'network_profile'
$signoffSection = Get-ScopeSection -Text $scope -Name 'signoff'

# auth.status
$authGranted = (Get-SectionField -Section $authSection -Name 'status') -eq 'granted'
if (-not $authGranted) { [void]$issues.Add('auth.status is not granted') }

# network_profile.mode
$netMode = Get-SectionField -Section $networkSection -Name 'mode'
$allowedNetworkModes = @('offline', 'lab_only', 'authorized_target_only', 'unrestricted_lab')
if ([string]::IsNullOrWhiteSpace($netMode)) {
    [void]$issues.Add('network_profile.mode missing')
} elseif ($netMode -notin $allowedNetworkModes) {
    [void]$issues.Add("network_profile.mode is unsupported: $netMode")
} elseif ($netMode -eq 'offline') {
    # offline is only OK if sample path mentioned in assets/notes — soft note
    if ($scope -notmatch 'sample|offline.?path|本地.?样本|\.apk\b|\.bin\b|\.exe\b') {
        [void]$issues.Add('network_profile.mode is offline without offline sample cue')
    }
}

# in_scope assets: only list items under "- assets:" inside ## in_scope
# Do NOT treat "- assets:" itself, ops_refs, or evidence_of_auth URLs as assets.
$hasAsset = $false
$inScopeSection = Get-ScopeSection -Text $scope -Name 'in_scope'
if ($inScopeSection -and $inScopeSection -match '(?ms)-\s*assets:\s*\r?\n(?<body>(?:\s+.+\r?\n?|\s+\r?\n?)*)') {
    $assetBody = $Matches['body']
    # Require indented list entries: "  - value" where value is not empty [] marker
    if ($assetBody -match '(?m)^\s+-\s+(?!\[\s*\])\S+') {
        $hasAsset = $true
    }
}
if (-not $hasAsset -and $netMode -ne 'offline') {
    [void]$issues.Add('in_scope.assets appears empty')
}

# ready_for_act
$ready = (Get-SectionField -Section $signoffSection -Name 'ready_for_act') -eq 'true'
if (-not $ready) { [void]$issues.Add('ready_for_act is not true') }

if ($issues.Count -eq 0) {
    Write-Info ("CASE-GUARD OK: {0}" -f $CaseRoot)
    exit 0
}

Write-Host ("CASE-GUARD NOT READY: {0}" -f $CaseRoot) -ForegroundColor Yellow
foreach ($i in $issues) { Write-Host (" - {0}" -f $i) -ForegroundColor Yellow }

if ($Force) {
    Write-Host 'CASE-GUARD: -Force does not bypass scope hard gates.' -ForegroundColor Yellow
}

Write-Host 'Fix scope (or re-run case-init -AuthGranted -TargetUrl ...).' -ForegroundColor Yellow
exit 2
