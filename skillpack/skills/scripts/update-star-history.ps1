#Requires -Version 5.1
<#
.SYNOPSIS
  Regenerate docs/assets/star-history.svg from GitHub stargazers API.

.DESCRIPTION
  Uses git credential manager token (or GH_TOKEN / GITHUB_TOKEN env).
  Requires repo admin/collaborator access (GitHub July 2026 stargazer restriction).
  Writes UTF-8 SVG without BOM. Does not commit.

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File skills/scripts/update-star-history.ps1
#>
param(
    [string]$Owner = 'zhaoxuya520',
    [string]$Repo = 'reverse-skill',
    [string]$OutFile = ''
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

function Get-GitHubToken {
    if ($env:GH_TOKEN) { return $env:GH_TOKEN }
    if ($env:GITHUB_TOKEN) { return $env:GITHUB_TOKEN }
    $input = "protocol=https`nhost=github.com`n`n"
    $cred = $input | git credential fill 2>$null
    $tok = ($cred | Where-Object { $_ -match '^password=' }) -replace '^password=', ''
    if ([string]::IsNullOrWhiteSpace($tok)) {
        throw 'No GitHub token. Set GH_TOKEN or use git credential manager (owner/collaborator required).'
    }
    return $tok
}

$token = Get-GitHubToken
$headers = @{
    Authorization = "Bearer $token"
    Accept        = 'application/vnd.github.v3.star+json'
    'User-Agent'  = 'reverse-skill-star-history'
}

$all = New-Object System.Collections.Generic.List[object]
$page = 1
while ($true) {
    $url = "https://api.github.com/repos/$Owner/$Repo/stargazers?per_page=100&page=$page"
    $resp = Invoke-RestMethod -Uri $url -Headers $headers -Method Get
    if (-not $resp -or @($resp).Count -eq 0) { break }
    foreach ($s in @($resp)) { [void]$all.Add($s) }
    Write-Host ("page={0} batch={1} total={2}" -f $page, @($resp).Count, $all.Count)
    if (@($resp).Count -lt 100) { break }
    $page++
    if ($page -gt 500) { break }
}

if ($all.Count -eq 0) {
    $repoInfo = Invoke-RestMethod -Uri "https://api.github.com/repos/$Owner/$Repo" -Headers @{
        Authorization = "Bearer $token"; 'User-Agent' = 'reverse-skill-star-history'
    }
    $series = @([pscustomobject]@{ Date = (Get-Date).ToUniversalTime().ToString('yyyy-MM-dd'); Stars = [int]$repoInfo.stargazers_count })
}
else {
    $byDay = @{}
    foreach ($s in $all) {
        if (-not $s.starred_at) { continue }
        $day = ([datetime]$s.starred_at).ToUniversalTime().ToString('yyyy-MM-dd')
        if (-not $byDay.ContainsKey($day)) { $byDay[$day] = 0 }
        $byDay[$day]++
    }
    $cum = 0
    $series = foreach ($d in ($byDay.Keys | Sort-Object)) {
        $cum += $byDay[$d]
        [pscustomobject]@{ Date = $d; Stars = $cum }
    }
}

$scriptDir = $PSScriptRoot
$packageRoot = Split-Path (Split-Path $scriptDir -Parent) -Parent
if (-not $OutFile) {
    $OutFile = Join-Path $packageRoot 'docs\assets\star-history.svg'
}
New-Item -ItemType Directory -Force -Path (Split-Path $OutFile -Parent) | Out-Null

$w = 800; $h = 400
$padL = 56; $padR = 24; $padT = 36; $padB = 48
$plotW = $w - $padL - $padR
$plotH = $h - $padT - $padB
$maxY = [Math]::Max(10, [Math]::Ceiling((($series | Measure-Object Stars -Maximum).Maximum) * 1.1))
$n = @($series).Count
$pts = for ($i = 0; $i -lt $n; $i++) {
    $x = if ($n -eq 1) { $padL + $plotW / 2 } else { $padL + ($plotW * $i / ($n - 1)) }
    $y = $padT + $plotH * (1 - ($series[$i].Stars / $maxY))
    '{0:F1},{1:F1}' -f $x, $y
}
$poly = ($pts -join ' ')
$firstDate = $series[0].Date
$lastDate = $series[-1].Date
$maxStars = $series[-1].Stars
$gen = (Get-Date).ToUniversalTime().ToString('yyyy-MM-dd HH:mm') + ' UTC'

$ticks = ''
for ($t = 0; $t -le 4; $t++) {
    $val = [int]($maxY * $t / 4)
    $y = $padT + $plotH * (1 - ($val / $maxY))
    $ticks += "  <line x1=`"$padL`" y1=`"$('{0:F1}' -f $y)`" x2=`"$($w - $padR)`" y2=`"$('{0:F1}' -f $y)`" stroke=`"#e5e7eb`" stroke-width=`"1`"/>`n"
    $ticks += "  <text x=`"$($padL - 8)`" y=`"$('{0:F1}' -f ($y + 4))`" text-anchor=`"end`" font-size=`"11`" fill=`"#6b7280`" font-family=`"system-ui,sans-serif`">$val</text>`n"
}

$fullName = "$Owner/$Repo"
$svg = @"
<svg xmlns="http://www.w3.org/2000/svg" width="$w" height="$h" viewBox="0 0 $w $h" role="img" aria-label="GitHub Star History for $fullName">
  <title>Star History — $fullName</title>
  <rect width="100%" height="100%" fill="#ffffff"/>
  <text x="$($w / 2)" y="22" text-anchor="middle" font-size="15" font-weight="600" fill="#111827" font-family="system-ui,sans-serif">Star History — $fullName</text>
  <text x="$($w / 2)" y="$($h - 10)" text-anchor="middle" font-size="10" fill="#9ca3af" font-family="system-ui,sans-serif">generated $gen · $maxStars stars · $firstDate → $lastDate</text>
$ticks
  <line x1="$padL" y1="$padT" x2="$padL" y2="$($padT + $plotH)" stroke="#9ca3af" stroke-width="1.5"/>
  <line x1="$padL" y1="$($padT + $plotH)" x2="$($w - $padR)" y2="$($padT + $plotH)" stroke="#9ca3af" stroke-width="1.5"/>
  <polyline fill="none" stroke="#2563eb" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round" points="$poly"/>
  <text x="$padL" y="$($padT + $plotH + 28)" font-size="11" fill="#6b7280" font-family="system-ui,sans-serif">$firstDate</text>
  <text x="$($w - $padR)" y="$($padT + $plotH + 28)" text-anchor="end" font-size="11" fill="#6b7280" font-family="system-ui,sans-serif">$lastDate</text>
  <text x="$($w - $padR)" y="$($padT + 14)" text-anchor="end" font-size="12" fill="#2563eb" font-family="system-ui,sans-serif" font-weight="600">$maxStars ★</text>
</svg>
"@

[System.IO.File]::WriteAllText($OutFile, $svg, [System.Text.UTF8Encoding]::new($false))
Write-Host ("Wrote {0} ({1} stars, {2} points)" -f $OutFile, $maxStars, $n) -ForegroundColor Green
