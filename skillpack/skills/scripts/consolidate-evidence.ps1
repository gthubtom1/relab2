#Requires -Version 5.1
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string] $CaseRoot,
    [Parameter(Mandatory = $true)][string] $EvidenceIds,
    [Parameter(Mandatory = $true)][string] $FindingId,
    [Parameter(Mandatory = $true)][string] $Title,
    [Parameter(Mandatory = $true)][string] $Description,
    [string] $Severity = 'medium',
    [string] $Status = 'validated',
    [string] $Confidence = 'medium',
    [string] $Location = 'see evidence_ids'
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
if (-not (Test-Path -LiteralPath $CaseRoot)) { Write-Error "CaseRoot not found: $CaseRoot" }

$evidenceDir = Join-Path $CaseRoot "evidence"
$reportDir = Join-Path $CaseRoot "report"
if (-not (Test-Path -LiteralPath $reportDir)) { New-Item -ItemType Directory -Path $reportDir -Force | Out-Null }

$idList = @($EvidenceIds -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne '' })
if ($idList.Count -eq 0) { Write-Error "No Evidence IDs provided." }

foreach ($id in $idList) {
    $evidenceFile = Join-Path $evidenceDir "$id.md"
    if (-not (Test-Path -LiteralPath $evidenceFile)) { Write-Error "Evidence file not found: $evidenceFile" }
}

foreach ($id in $idList) {
    $evidenceFile = Join-Path $evidenceDir "$id.md"
    $content = Get-Content -LiteralPath $evidenceFile -Raw -Encoding UTF8
    if ($content -match "(?m)^-\s*status:\s*.*$") {
        $content = [regex]::Replace($content, "(?m)^-\s*status:\s*.*$", "- status: superseded by $FindingId")
    } elseif ($content -match "(?m)^---\s*$") {
        $content = [regex]::Replace($content, "(?m)^---\s*$", "---`r`n- status: superseded by $FindingId", 1)
    } else {
        $content = $content.TrimEnd() + "`r`n- status: superseded by $FindingId`r`n"
    }
    Set-Content -LiteralPath $evidenceFile -Value $content -Encoding UTF8 -NoNewline
}

$timestamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
$joined = ($idList -join ', ')
$findingBlock = @"
### $FindingId
- title: $Title
- severity: $Severity
- status: $Status
- confidence: $Confidence
- location: $Location
- evidence_ids: $joined
- consolidated_at: $timestamp

$Description
"@

$reportFile = Join-Path $reportDir "report.md"
if (Test-Path -LiteralPath $reportFile) {
    $reportContent = Get-Content -LiteralPath $reportFile -Raw -Encoding UTF8
    if ($reportContent -notmatch "(?m)^## Findings") {
        $reportContent = $reportContent.TrimEnd() + "`r`n`r`n## Findings`r`n"
    }
    Set-Content -LiteralPath $reportFile -Value ($reportContent.TrimEnd() + "`r`n`r`n" + $findingBlock + "`r`n") -Encoding UTF8 -NoNewline
} else {
    $initialReport = @"
# Case Report

## Findings

$findingBlock
"@
    Set-Content -LiteralPath $reportFile -Value $initialReport -Encoding UTF8
}