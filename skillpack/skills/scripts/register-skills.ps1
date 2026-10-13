#Requires -Version 5.1
<#
register-skills.ps1 —— 把本技能包"注册"进宿主，让技能对模型**常驻可见**。

为什么需要它：
  宿主（如 omp）会在启动时把每个技能的 `name` + `description` 预载进系统提示，
  正文按需读 `skill://<name>`。**只有注册过的技能才会出现在那张列表里。**
  不注册 = 模型不知道有这个技能 = 永远不会在节点上想到用它。

  本脚本只做一件事：把这个包根目录写进宿主的 `skills.customDirectories`。
  幂等：重复跑不会重复添加；已有其它 customDirectories 不会被覆盖。

用法：
  powershell -NoProfile -ExecutionPolicy Bypass -File register-skills.ps1
  ... -WhatIf        只看会改什么，不落地
  ... -Revert        从配置里摘掉本包
  ... -Json          机器可读输出

退出码：0 成功（含"本来就已经注册"）／2 找不到技能或宿主
#>
param(
    [string] $RepoRoot = '',
    [string] $SkillsRoot = '',
    [switch] $WhatIf,
    [switch] $Revert,
    [switch] $Json
)

$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }

# --- 1. 定位包根（与 master-route.ps1 同口径：不写死绝对路径）---
function Resolve-PackSkillsRoot {
    param([string] $Root, [string] $Given)
    $cands = New-Object System.Collections.Generic.List[string]
    if ($Given) { [void]$cands.Add($Given) }
    if ($Root) { [void]$cands.Add((Join-Path $Root 'skillpack\skills')) }
    if ($env:REVERSE_SKILL_ROOT) { [void]$cands.Add((Join-Path $env:REVERSE_SKILL_ROOT 'skillpack\skills')) }
    # 从本脚本位置逐级上溯，找含 <父>\skills\<name>\SKILL.md 的那一层
    $d = $PSScriptRoot
    while ($d) {
        [void]$cands.Add($d)                       # scripts/ 的上一级就是 skills/
        $parent = Split-Path -Parent $d
        if (-not $parent -or $parent -eq $d) { break }
        $d = $parent
    }
    [void]$cands.Add('C:\relab2\skillpack\skills')
    foreach ($c in $cands) {
        if (-not $c) { continue }
        if (-not (Test-Path -LiteralPath $c)) { continue }
        $probe = @(Get-ChildItem -LiteralPath $c -Directory -ErrorAction SilentlyContinue |
                   Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'SKILL.md') })
        if ($probe.Count -gt 0) { return (Resolve-Path -LiteralPath $c).Path }
    }
    return $null
}

$skills = Resolve-PackSkillsRoot -Root $RepoRoot -Given $SkillsRoot
if (-not $skills) {
    Write-Host 'ERROR: 找不到技能根（含 <root>\<name>\SKILL.md 的目录）。用 -SkillsRoot 指定。' -ForegroundColor Red
    exit 2
}

$skillDirs = @(Get-ChildItem -LiteralPath $skills -Directory |
               Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'SKILL.md') })
$count = $skillDirs.Count
if ($count -eq 0) {
    Write-Host ("ERROR: {0} 下一个技能都没有。" -f $skills) -ForegroundColor Red
    exit 2
}

# 描述体量：宿主会把 description 预载进系统提示，这里报个总量当预算参考
$descBytes = 0
foreach ($d in $skillDirs) {
    $t = Get-Content -LiteralPath (Join-Path $d.FullName 'SKILL.md') -Raw -Encoding UTF8
    $m = [regex]::Match($t, '(?s)^---\s*\n(.*?)\n---')
    if ($m.Success) {
        $dm = [regex]::Match($m.Groups[1].Value, '(?s)description:\s*(.*?)(?=\n[a-zA-Z_]+:|\z)')
        if ($dm.Success) { $descBytes += [System.Text.Encoding]::UTF8.GetByteCount($dm.Groups[1].Value) }
    }
}

# --- 2. 认宿主 ---
$omp = Get-Command omp -ErrorAction SilentlyContinue
$hostKind = if ($omp) { 'omp' } else { 'unknown' }

function Get-OmpCustomDirs {
    if (-not $omp) { return @() }
    $raw = (& $omp.Source config get skills.customDirectories 2>$null) | Out-String
    $raw = $raw.Trim()
    if (-not $raw) { return @() }
    try { return @($raw | ConvertFrom-Json) } catch { return @() }
}

$target = $skills
$existing = @()
if ($hostKind -eq 'omp') {
    $existing = @(Get-OmpCustomDirs | Where-Object { $_ -and $_.Trim() })
}

$norm = { param($p) ($p -replace '/', '\').TrimEnd('\').ToLowerInvariant() }
$want = New-Object System.Collections.Generic.List[string]
foreach ($e in $existing) { [void]$want.Add($e.ToString()) }
$alreadyThere = $false
foreach ($e in $want) { if ((& $norm $e) -eq (& $norm $target)) { $alreadyThere = $true } }

if ($Revert) {
    $kept = @($want | Where-Object { (& $norm $_) -ne (& $norm $target) })
    $action = if ($kept.Count -eq $want.Count) { 'noop' } else { 'revert' }
    $final = $kept
} elseif ($alreadyThere) {
    $action = 'already'
    $final = @($want)
} else {
    $action = 'add'
    [void]$want.Add($target)
    $final = @($want)
}

$result = [ordered]@{
    host            = $hostKind
    skills_root     = $target
    skill_count     = $count
    description_bytes = $descBytes
    action          = $action
    customDirectories = $final
    whatif          = [bool]$WhatIf
}

if ($Json) { $result | ConvertTo-Json -Depth 5 }

if ($hostKind -ne 'omp') {
    Write-Host '未检测到 omp CLI —— 下面是各宿主的手工注册片段：' -ForegroundColor Yellow
    Write-Host ''
    Write-Host '# omp:  ~/.omp/agent/config.yml'
    Write-Host 'skills:'
    Write-Host '  customDirectories:'
    Write-Host ("    - {0}" -f $target)
    Write-Host ''
    Write-Host '# Claude Code: 建一个软链到它的 skills 根（<skills-root>/<name>/SKILL.md 布局一致）'
    Write-Host ("#   mklink /J `"%USERPROFILE%\.claude\skills`" `"{0}`"" -f $target)
    Write-Host ''
    Write-Host '# 其它宿主：把上面那两行写进它的 skills.customDirectories 等价项即可'
    exit 0
}

if ($WhatIf) {
    Write-Host ("[whatif] {0}：{1} 个技能 → skills.customDirectories 将变为：" -f $action, $count)
    foreach ($f in $final) { Write-Host ("    - {0}" -f $f) }
    exit 0
}

if ($action -eq 'already') {
    Write-Host ("[ok] 已注册（{0} 个技能）：{1}" -f $count, $target) -ForegroundColor Green
} else {
    $jsonArr = ConvertTo-Json -InputObject @($final) -Compress
    $out = (& $omp.Source config set skills.customDirectories $jsonArr 2>&1) | Out-String
    Write-Host $out.Trim()
    $back = (Get-OmpCustomDirs)
    $hit = $false
    foreach ($e in $back) { if ((& $norm $e) -eq (& $norm $target)) { $hit = $true } }
    if (-not $hit) {
        Write-Host 'ERROR: 写入后回读不到本路径，请检查 config.yml。' -ForegroundColor Red
        exit 2
    }
    Write-Host ("[{0}] {1} 个技能已注册：{2}" -f $action, $count, $target) -ForegroundColor Green
}

Write-Host ''
Write-Host '验证（新开会话，或跑一条）：'
Write-Host '  omp -p --no-session "不要调用任何工具。只回答：你的系统提示里列出的 Skill 名称有哪些？"'
Write-Host ("description 预载预算：{0} 字节 ≈ {1} tokens（全部技能合计）" -f $descBytes, [int]($descBytes / 3))
Write-Host '看不到技能列表 → 检查宿主是否支持 skills.customDirectories；本包的布局是 <root>/<name>/SKILL.md（单层，非递归）。'
exit 0
