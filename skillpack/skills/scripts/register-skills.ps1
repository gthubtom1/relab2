#Requires -Version 5.1
<#
register-skills.ps1 —— 把一个技能包"注册"给**本机上所有智能体**，让技能对模型常驻可见。

思路（这是全项目唯一正确的注册方式）：
  宿主启动时会把每个技能的 `name` + `description` 预载进系统提示，正文按需读
  `skill://<name>`（Claude Code / Codex / Cursor / omp… 都是这套"Agent Skills"规范）。
  **只有被发现目录扫到的技能，才会进那张列表。**

  所以不去挨个改每个宿主的配置 —— 而是**一份实体，N 个目录联接（junction）**：
  把技能包目录挂进各家约定的"通用技能目录"，谁扫到就是谁的。
  换机 / 换智能体都不需要改技能包一个字。

目录事实（2026-10 实测自 vercel-labs/skills 的 Supported Agents 表 + 本机 omp 实测）：
  · 项目级通用： <项目>/.agents/skills/          ← OpenCode / Codex / Cursor / Cline / Amp /
                                                   Kimi CLI / Gemini CLI / GitHub Copilot 原生读
  · 用户级通用： %USERPROFILE%\.agents\skills\   ← Cline 形态；omp(python -m) 实测命中
                 %USERPROFILE%\.config\agents\skills\  ← Amp / Kimi / Replit / "Universal" 形态
  · 各家私有：   ~\.claude\skills\ · ~\.codex\skills\ · ~\.cursor\skills\ · ~\.gemini\skills\
                 ~\.copilot\skills\ · ~\.pi\agent\skills\ · ~\.roo\skills\ · ~\.openhands\skills\ …
                 （仅在"该家的家目录确实存在"时才挂）

用法：
  powershell -NoProfile -ExecutionPolicy Bypass -File register-skills.ps1
      # 干这个：用户级通用目录 + 已装智能体的私有目录，全部挂上
  ... -ProjectRoot "D:\MyProj"      # 额外给这个项目挂 .agents\skills（自包含、跟着项目走）
  ... -WhatIf                       # 只看会挂哪些，不动盘
  ... -Json
  ... -Revert                       # 摘掉所有"指向本技能包"的联接（别家的原样不动）
  ... -SkillsRoot <路径>            # 指定技能根（默认按包根/环境变量/本脚本位置上溯自动找）

退出码：0 成功／2 找不到技能根
#>
param(
    [string] $RepoRoot = '',
    [string] $SkillsRoot = '',
    [string] $ProjectRoot = '',
    [switch] $WhatIf,
    [switch] $Revert,
    [switch] $Json
)

$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }

# ---------------- 1. 定位技能包根（不写死绝对路径）----------------
function Resolve-PackSkillsRoot {
    param([string] $Root, [string] $Given)
    $cands = New-Object System.Collections.Generic.List[string]
    if ($Given) { [void]$cands.Add($Given) }
    if ($Root) { [void]$cands.Add((Join-Path $Root 'skillpack\skills')) }
    if ($env:REVERSE_SKILL_ROOT) { [void]$cands.Add((Join-Path $env:REVERSE_SKILL_ROOT 'skillpack\skills')) }
    $d = $PSScriptRoot
    while ($d) {
        [void]$cands.Add($d)
        $parent = Split-Path -Parent $d
        if (-not $parent -or $parent -eq $d) { break }
        $d = $parent
    }
    foreach ($c in $cands) {
        if (-not $c -or -not (Test-Path -LiteralPath $c)) { continue }
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
if ($skillDirs.Count -eq 0) { Write-Host ("ERROR: {0} 下一个技能都没有。" -f $skills) -ForegroundColor Red; exit 2 }

$descBytes = 0
foreach ($d in $skillDirs) {
    $t = Get-Content -LiteralPath (Join-Path $d.FullName 'SKILL.md') -Raw -Encoding UTF8
    $m = [regex]::Match($t, '(?s)^---\s*\n(.*?)\n---')
    if ($m.Success) {
        $dm = [regex]::Match($m.Groups[1].Value, '(?s)description:\s*(.*?)(?=\n[a-zA-Z_]+:|\z)')
        if ($dm.Success) { $descBytes += [System.Text.Encoding]::UTF8.GetByteCount($dm.Groups[1].Value) }
    }
}

# ---------------- 2. 目标目录表 ----------------
# detect: 该智能体的"家目录"存在才算装了它
$H = $env:USERPROFILE
$agentTable = @(
    # 用户级通用（不需要任何配置就能被读到的两组约定）
    @{ agent = 'universal(Cline形态)'; path = (Join-Path $H '.agents\skills');      detect = $null },
    @{ agent = 'universal(vendor形态)'; path = (Join-Path $H '.config\agents\skills'); detect = $null },
    # 各家私有（仅当已装）
    @{ agent = 'Claude Code'; path = (Join-Path $H '.claude\skills');    detect = (Join-Path $H '.claude') },
    @{ agent = 'Codex';       path = (Join-Path $H '.codex\skills');     detect = (Join-Path $H '.codex') },
    @{ agent = 'Cursor';      path = (Join-Path $H '.cursor\skills');    detect = (Join-Path $H '.cursor') },
    @{ agent = 'Gemini CLI';  path = (Join-Path $H '.gemini\skills');    detect = (Join-Path $H '.gemini') },
    @{ agent = 'GitHub Copilot'; path = (Join-Path $H '.copilot\skills'); detect = (Join-Path $H '.copilot') },
    @{ agent = 'Pi';          path = (Join-Path $H '.pi\agent\skills');  detect = (Join-Path $H '.pi\agent') },
    @{ agent = 'Roo Code';    path = (Join-Path $H '.roo\skills');       detect = (Join-Path $H '.roo') },
    @{ agent = 'OpenHands';   path = (Join-Path $H '.openhands\skills'); detect = (Join-Path $H '.openhands') },
    @{ agent = 'Windsurf';    path = (Join-Path $H '.codeium\windsurf\skills'); detect = (Join-Path $H '.codeium\windsurf') },
    @{ agent = 'Goose';       path = (Join-Path $H '.config\goose\skills'); detect = (Join-Path $H '.config\goose') },
    @{ agent = 'Continue';    path = (Join-Path $H '.continue\skills');  detect = (Join-Path $H '.continue') },
    @{ agent = 'Crush';       path = (Join-Path $H '.config\crush\skills'); detect = (Join-Path $H '.config\crush') },
    @{ agent = 'Droid';       path = (Join-Path $H '.factory\skills');   detect = (Join-Path $H '.factory') },
    @{ agent = 'Qwen Code';   path = (Join-Path $H '.qwen\skills');      detect = (Join-Path $H '.qwen') },
    @{ agent = 'Trae';        path = (Join-Path $H '.trae\skills');      detect = (Join-Path $H '.trae') },
    @{ agent = 'Kiro CLI';    path = (Join-Path $H '.kiro\skills');      detect = (Join-Path $H '.kiro') },
    @{ agent = 'Zencoder';    path = (Join-Path $H '.zencoder\skills');  detect = (Join-Path $H '.zencoder') }
)

$targets = New-Object System.Collections.Generic.List[object]
foreach ($a in $agentTable) {
    $installed = $true
    if ($a.detect) { $installed = Test-Path -LiteralPath $a.detect }
    $targets.Add([pscustomobject]@{ agent = $a.agent; path = $a.path; installed = $installed; scope = 'user' })
}
if ($ProjectRoot) {
    $pr = (Resolve-Path -LiteralPath $ProjectRoot).Path
    $targets.Add([pscustomobject]@{ agent = '项目级通用'; path = (Join-Path $pr '.agents\skills'); installed = $true; scope = 'project' })
}

function Get-LinkTarget {
    param([string] $p)
    $i = Get-Item -LiteralPath $p -Force -ErrorAction SilentlyContinue
    if (-not $i) { return '' }
    if ($i.LinkType) { return ($i.Target | Select-Object -First 1) }
    return ''
}

$norm = { param($p) ($p -replace '/', '\').TrimEnd('\').ToLowerInvariant() }
$mine = & $norm $skills

# ---------------- 3. 执行 ----------------
$report = New-Object System.Collections.Generic.List[object]

if ($Revert) {
    foreach ($t in $targets) {
        if (-not (Test-Path -LiteralPath $t.path)) { continue }
        $tgt = Get-LinkTarget -p $t.path
        if ($tgt -and (& $norm $tgt) -eq $mine) {
            if (-not $WhatIf) { (Get-Item -LiteralPath $t.path -Force).Delete() }
            $report.Add([pscustomobject]@{ agent = $t.agent; path = $t.path; action = 'removed'; ok = $true })
        }
    }
    if ($Json) { $report | ConvertTo-Json -Depth 5 } else { $report | Format-Table -AutoSize | Out-String | Write-Host }
    exit 0
}

foreach ($t in $targets) {
    if (-not $t.installed) {
        $report.Add([pscustomobject]@{ agent = $t.agent; path = $t.path; action = 'skip(未装)'; ok = $true }); continue
    }
    if (Test-Path -LiteralPath $t.path) {
        $tgt = Get-LinkTarget -p $t.path
        if ($tgt -and (& $norm $tgt) -eq $mine) {
            $report.Add([pscustomobject]@{ agent = $t.agent; path = $t.path; action = 'already'; ok = $true }); continue
        }
        if ($tgt) {
            $report.Add([pscustomobject]@{ agent = $t.agent; path = $t.path; action = ("skip(已指向别处: {0})" -f $tgt); ok = $true }); continue
        }
        # 真实同名目录：不覆盖，只报
        $cnt = @(Get-ChildItem -LiteralPath $t.path -Directory -ErrorAction SilentlyContinue).Count
        if ($cnt -gt 0) {
            $report.Add([pscustomobject]@{ agent = $t.agent; path = $t.path; action = ("skip(已有实体目录 {0} 项)" -f $cnt); ok = $true }); continue
        }
        if (-not $WhatIf) { Remove-Item -LiteralPath $t.path -Force -Recurse }
    }
    $parent = Split-Path -Parent $t.path
    if (-not $WhatIf) {
        if (-not (Test-Path -LiteralPath $parent)) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
        New-Item -ItemType Junction -Path $t.path -Target $skills | Out-Null
    }
    $report.Add([pscustomobject]@{ agent = $t.agent; path = $t.path; action = 'linked'; ok = $true })
}

$result = New-Object System.Collections.Specialized.OrderedDictionary
$result.Add('skills_root', $skills)
$result.Add('skill_count', $skillDirs.Count)
$result.Add('description_bytes', $descBytes)
$result.Add('whatif', [bool]$WhatIf)
$result.Add('targets', @($report | ForEach-Object { $_ }))
if ($Json) { $result | ConvertTo-Json -Depth 6; exit 0 }

Write-Host ''
Write-Host '=== 技能注册（一份实体，N 个目录联接）===' -ForegroundColor Cyan
Write-Host ("技能根：{0}    技能数：{1}    description 预载：{2} 字节 ≈ {3} tokens" -f $skills, $skillDirs.Count, $descBytes, [int]($descBytes / 3))
Write-Host ''
Write-Host ('{0,-20} {1,-60} {2}' -f 'AGENT', 'PATH', 'ACTION')
Write-Host ('-' * 110)
foreach ($r in $report) {
    $c = switch -Wildcard ($r.action) { 'linked*' { 'Green' } 'already*' { 'DarkGray' } 'removed*' { 'Yellow' } default { 'Gray' } }
    Write-Host (('{0,-20} {1,-60} {2}' -f $r.agent, $r.path, $r.action)) -ForegroundColor $c
}
Write-Host ''
Write-Host '验证（任一宿主新开会话）：'
Write-Host '  omp -p --no-session "不要调用任何工具。只回答：你的系统提示里列出的 Skill 名称有哪些？"'
Write-Host '  其它宿主：看它有没有把本包的技能名列进自己的技能表/斜杠命令。'
Write-Host ''
Write-Host '不落配置、不常驻、不装服务 —— 只加目录联接；-Revert 一键摘掉（别家的原样不动）。'
exit 0
