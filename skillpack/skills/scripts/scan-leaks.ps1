<#
.SYNOPSIS
  Scan text/markdown for un-anonymized sensitive info (IP/email/phone/JWT/API keys/tokens).

.DESCRIPTION
  Companion to skills/field-journal/anonymization.md placeholder rules.
  Default behavior: exit 1 when findings exist (CI gate).
  Use -ReportOnly to just report without failing.

.PARAMETER Path
  File or directory to scan (default: skills/field-journal).
  Directory -> recursive *.md/*.txt/*.json; File -> that file only.

.PARAMETER ReportOnly
  Report findings but do not set a failing exit code.
#>
param(
  [string]$Path = "skills/field-journal",
  [switch]$ReportOnly
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

# Allowed sample domains (documentation examples are not leaks)
$allowedDomains = @('example.com','example.org','example.net','example.edu','example.test','test','localhost','local','invalid')

$patterns = @(
  @{ Name = 'Public IPv4'; Regex = '\b(?!(?:10\.|127\.|172\.(?:1[6-9]|2[0-9]|3[01])\.|192\.168\.|169\.254\.|100\.100\.|198\.51\.100\.|203\.0\.113\.|192\.0\.2\.|0\.0\.0\.|224\.|25[0-5]\.))(?:\d{1,3}\.){3}\d{1,3}\b' }
  @{ Name = 'Email'; Regex = '\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b' }
  @{ Name = 'CN mobile'; Regex = '\b1[3-9][0-9]{9}\b' }
  @{ Name = 'JWT'; Regex = 'eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}' }
  @{ Name = 'AWS Access Key'; Regex = '\bAKIA[0-9A-Z]{16}\b' }
  @{ Name = 'OpenAI key'; Regex = '\bsk-(?:proj-)?[A-Za-z0-9]{20,}\b' }
  @{ Name = 'GitHub token'; Regex = '\bgh[pousr]_[A-Za-z0-9]{20,}\b' }
  @{ Name = 'npm token'; Regex = '\bnpm_[A-Za-z0-9]{30,}\b' }
  @{ Name = 'Slack token'; Regex = '\bxox[baprs]-[A-Za-z0-9-]{10,}\b' }
  @{ Name = 'Google API key'; Regex = '\bAIza[A-Za-z0-9_-]{35}\b' }
  @{ Name = 'Stripe live key'; Regex = '\b(?:sk|rk)_live_[A-Za-z0-9]{20,}\b' }
)

function Test-EmailAllowed {
  param([string]$Match)
  $domain = ($Match -split '@')[-1]
  foreach ($d in $allowedDomains) {
    if ($domain -eq $d -or $domain.EndsWith('.' + $d)) { return $true }
  }
  return $false
}

$targets = @()
if (Test-Path $Path -PathType Container) {
  $targets = Get-ChildItem -Path $Path -Recurse -File -Include *.md,*.txt,*.json | Sort-Object FullName
} elseif (Test-Path $Path -PathType Leaf) {
  $targets = @(Get-Item $Path)
} else {
  Write-Error "Path not found: $Path"
  exit 2
}

$findings = 0
foreach ($t in $targets) {
  $lines = Get-Content -Path $t.FullName -Encoding UTF8
  for ($i = 0; $i -lt $lines.Count; $i++) {
    $line = $lines[$i]
    foreach ($p in $patterns) {
      foreach ($m in [regex]::Matches($line, $p.Regex)) {
        if ($p.Name -eq 'Email' -and (Test-EmailAllowed $m.Value)) { continue }
        $findings++
        $kind = if ($ReportOnly) { 'warning' } else { 'error' }
        Write-Host "::$kind file=$($t.FullName),line=$($i + 1)::$($p.Name): $($m.Value -replace "\r","%0D" -replace "\n","%0A")"
      }
    }
  }
}

Write-Host "scan-leaks: scanned $($targets.Count) files, $findings finding(s)"
if ($findings -gt 0 -and -not $ReportOnly) { exit 1 }
