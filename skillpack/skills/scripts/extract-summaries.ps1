#Requires -Version 5.1
# 生成 skills/INDEX.md：从各模块 SKILL.md 的 frontmatter 提取 name+description，生成导航索引。
# 幂等：重复运行输出一致（CI 用 git diff 校验防 drift）。
# 用法：
#   powershell -NoProfile -ExecutionPolicy Bypass -File skills/scripts/extract-summaries.ps1
#   powershell -File skills/scripts/extract-summaries.ps1 -Check   # 只校验不写（CI 模式，不一致 exit 1）
param(
    [switch] $Check
)
# ★ PSModulePath 自愈（2026-10-10 注入，路径由 inject-psmp.py 统一计算）：剔除 WindowsApps 版 PowerShell 7 的模块目录，否则 PS 5.1 会因 TypeData 重复定义失败而使 Get-FileHash / Get-ExecutionPolicy 不可用（已造成两次假绿 + 一次失败被吞）。重算/迁移后请重跑 work/envinit/inject-psmp.py
. 'C:\relab2\skillpack\skills\scripts\lib\PsModulePathInit.ps1'

$ErrorActionPreference = 'Stop'

$scriptDir = $PSScriptRoot
if (-not $scriptDir) { $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path }
$skillsRoot = Split-Path -Parent $scriptDir
$indexPath = Join-Path $skillsRoot 'INDEX.md'

# 扫描版本库中的模块 SKILL.md（排除本地 ignored/private trees，保证 clean clone 与开发机幂等）。
$skipDirs = @('ops', 'scripts', 'config', 'tests', 'field-journal', 'references')
# 发现隔离（规范 17.27）：raw vendor 正文物理位于客户端发现根 skills/ 之外。
# 下面两组是 INDEX 的硬排除面，任何一条命中都不得进入 INDEX.md：
#   1. $rawRoots       当前 raw 根（仓库根下的独立目录，不在 skills/ 内）；
#   2. $rawSourceDirs  若导入器再次把 raw 写回 skills/community/<source>/，同样必须排除。
$rawRoots = @('community-raw')
$rawSourceDirs = @('ai-fullstack', 'apk-reverse-source', 'ctf-super-hub', 'hack-skills')
$packageRoot = Split-Path -Parent $skillsRoot
$trackedSkillFiles = @()
$git = Get-Command git -ErrorAction SilentlyContinue
if ($git) {
    # raw 根显式列入候选，再由下面的过滤器排除：排除是被证明的，不是靠路径巧合。
    $trackedPaths = @(& $git.Source -C $packageRoot ls-files -- 'skills/**/SKILL.md' 'community-raw/**/SKILL.md')
    if ($LASTEXITCODE -eq 0) {
        $trackedSkillFiles = @($trackedPaths | ForEach-Object {
            $fullPath = Join-Path $packageRoot ($_ -replace '/', [IO.Path]::DirectorySeparatorChar)
            if (Test-Path -LiteralPath $fullPath -PathType Leaf) { Get-Item -LiteralPath $fullPath }
        })
    }
}
$candidateSkillFiles = if ($trackedSkillFiles.Count -gt 0) {
    $trackedSkillFiles
} else {
    @(Get-ChildItem -Path $skillsRoot -Recurse -Filter 'SKILL.md')
}
$skillFiles = $candidateSkillFiles | Where-Object {
    $rel = $_.FullName.Substring($skillsRoot.Length + 1)
    $repoRel = ($_.FullName.Substring($packageRoot.Length + 1)) -replace '\\', '/'
    $isRaw = $false
    foreach ($root in $rawRoots) { if ($repoRel.StartsWith($root + '/')) { $isRaw = $true } }
    foreach ($src in $rawSourceDirs) { if ($repoRel.StartsWith('skills/community/' + $src + '/')) { $isRaw = $true } }
    -not $isRaw -and $rel -ne 'SKILL.md' -and
        -not ($skipDirs | Where-Object { $rel.StartsWith($_ + '\') -or $rel.StartsWith($_ + '/') })
} | Sort-Object { $_.FullName.Substring($skillsRoot.Length + 1) }

$rows = New-Object System.Collections.ArrayList
foreach ($sf in $skillFiles) {
    $rel = $sf.FullName.Substring($skillsRoot.Length + 1)
    # 兼容 Windows（\）与 Linux/macOS（/）两种路径分隔符
    $dir = $rel.Split(@('\', '/'))[0]
    $head = Get-Content -LiteralPath $sf.FullName -TotalCount 15 -Encoding UTF8
    $name = ''; $desc = ''; $blockMode = $false; $inFm = $false
    foreach ($line in $head) {
        if ($line -match '^---') {
            if ($inFm) { break }   # 第二个 --- 结束 frontmatter
            $inFm = $true; continue
        }
        if (-not $inFm) { continue }
        if ($line -match '^name:\s*(.+)$') { $name = $Matches[1].Trim(); continue }
        if ($line -match '^description:\s*\|') { $blockMode = $true; continue }
        if ($line -match '^description:\s*(.+)$') { $desc = $Matches[1].Trim(); continue }
        if ($blockMode) {
            # YAML 块：缩进的文本行拼接（取首行，超长截断）
            if ($line -match '^\s{2,}(.+)$') {
                if (-not $desc) { $desc = $Matches[1].Trim() }
            } elseif ($line -match '^\S') { $blockMode = $false }
        }
    }
    if (-not $name) { $name = $dir }
    if (-not $desc) { $desc = '(无摘要)' }
    if ($desc.Length -gt 160) { $desc = $desc.Substring(0, 157) + '...' }
    [void]$rows.Add([pscustomobject]@{
        Dir  = $dir
        Name = $name
        Desc = $desc
        Path = $rel
    })
}

# 自证（17.27）：行集里绝不允许出现 raw 条目，出现即失败，而不是 warning。
$rawLeak = @($rows | Where-Object {
    $p = ($_.Path -replace '\\', '/')
    ($rawRoots | Where-Object { $p.StartsWith($_ + '/') }) -or
        ($rawSourceDirs | Where-Object { $p.StartsWith('community/' + $_ + '/') })
})
if ($rawLeak.Count -gt 0) {
    Write-Host ('[FAIL] raw vendor entr(ies) would reach INDEX.md: ' + (($rawLeak | ForEach-Object { $_.Path }) -join ', ')) -ForegroundColor Red
    exit 1
}

$sb = New-Object System.Text.StringBuilder
[void]$sb.AppendLine('# reverse-skill 技能导航索引')
[void]$sb.AppendLine('')
[void]$sb.AppendLine('> 本文件由 `skills/scripts/extract-summaries.ps1` 自动生成，**请勿手改**。')
[void]$sb.AppendLine('> 修改摘要请编辑对应模块 `SKILL.md` 的 frontmatter `description`，然后重跑脚本。')
[void]$sb.AppendLine('')
[void]$sb.AppendLine('## 模块总览')
[void]$sb.AppendLine('')
[void]$sb.AppendLine('| 模块 | 摘要 |')
[void]$sb.AppendLine('|------|------|')
foreach ($r in $rows) {
    $esc = $r.Desc -replace '\|', '\|'
    [void]$sb.AppendLine(("| [{0}]({1}) | {2} |" -f $r.Name, ($r.Path -replace '\\', '/'), $esc))
}
[void]$sb.AppendLine('')
[void]$sb.AppendLine('## 目录树')
[void]$sb.AppendLine('')
[void]$sb.AppendLine('```')
foreach ($r in $rows) {
    [void]$sb.AppendLine(("skills/{0}/" -f ($r.Path -replace '\\', '/')))
}
[void]$sb.AppendLine('```')
[void]$sb.AppendLine('')
[void]$sb.AppendLine('## 路由')
[void]$sb.AppendLine('')
[void]$sb.AppendLine('PRIMARY 路由由 `skills/config/routing.json`（唯一事实源）驱动，用 `master-route.ps1 -Hint "<任务>"` 分诊。')
[void]$sb.AppendLine('歧义场景读 `skills/routing.md` 全矩阵；CTF 多类型任务走 `CTF-Sandbox-Orchestrator/`。')
[void]$sb.AppendLine('')
[void]$sb.AppendLine('## 症状 / 知识库索引')
[void]$sb.AppendLine('')
[void]$sb.AppendLine('上面这张表按**模块**查。遇到「用户描述了一个现象，不知道该读哪篇技术文档」，用这两张表：')
[void]$sb.AppendLine('')
[void]$sb.AppendLine('| 表 | 用途 | 什么时候读 |')
[void]$sb.AppendLine('|---|---|---|')
[void]$sb.AppendLine('| [SYMPTOM-INDEX.md](SYMPTOM-INDEX.md) | 用户口述的现象 → 进哪个技能 | `master-route` 报 `confidence: low` / PRIMARY=R0 / "No strong keyword hit" |')
[void]$sb.AppendLine('| [field-journal/KB-INDEX.md](field-journal/KB-INDEX.md) | 现象 → 读哪篇技术文档（153 篇） | 已进技能，但不确定该读 `references/` 里的哪一篇 |')
[void]$sb.AppendLine('')
[void]$sb.AppendLine('知识库来源、改编规则、以及「源文档被本机实测推翻」的 27 条清单见 [field-journal/KB-SOURCES.md](field-journal/KB-SOURCES.md)。')

$newContent = $sb.ToString()
# 统一 LF 行尾：与 .gitattributes (*.md eol=lf) 保持一致，保证 clone 后 -Check 幂等
$newContent = $newContent -replace "`r`n", "`n"
$utf8 = New-Object System.Text.UTF8Encoding $true

if ($Check) {
    if (-not (Test-Path -LiteralPath $indexPath)) {
        Write-Host '[CHECK] INDEX.md missing' -ForegroundColor Red
        exit 1
    }
    # 行尾免疫：autocrlf=true 的机器上 worktree 可能是 CRLF，normalize 后再比
    $old = ([System.IO.File]::ReadAllText($indexPath)) -replace "`r`n", "`n"
    if ($old -eq $newContent) {
        Write-Host '[CHECK] INDEX.md up to date' -ForegroundColor Green
        exit 0
    }
    Write-Host '[CHECK] INDEX.md out of date (run extract-summaries.ps1)' -ForegroundColor Red
    exit 1
}

[System.IO.File]::WriteAllText($indexPath, $newContent, $utf8)
Write-Host ("INDEX.md regenerated: {0} modules" -f $rows.Count) -ForegroundColor Green
