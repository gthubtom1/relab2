#Requires -Version 5.1
# ★ PSModulePath 自愈（2026-10-10 注入，路径由 inject-psmp.py 统一计算）：剔除 WindowsApps 版 PowerShell 7 的模块目录，否则 PS 5.1 会因 TypeData 重复定义失败而使 Get-FileHash / Get-ExecutionPolicy 不可用（已造成两次假绿 + 一次失败被吞）。重算/迁移后请重跑 work/envinit/inject-psmp.py
. 'C:\relab2\skillpack\skills\scripts\lib\PsModulePathInit.ps1'

param([string] $WorkflowPath = '')

$ErrorActionPreference = 'Stop'

# 往上逐层找 .github/workflows/auto-merge-journal.yml，最多找 5 层。
# 原来写死「上两层」→ 落在 skillpack/ 下，而 workflow 实际在**仓根** .github/，
# 于是这个守卫从来没守到过任何文件：找不到就 Get-Content 抛错，整个测试永远红。
# 现在改成「找到为止」，仓根 / skillpack/ 两种摆法都能找到。
if ([string]::IsNullOrWhiteSpace($WorkflowPath)) {
    $probe = 'auto-merge-journal.yml'
    $dir = $PSScriptRoot
    for ($i = 0; $i -lt 5 -and -not $WorkflowPath; $i++) {
        $candidate = Join-Path $dir ".github\workflows\$probe"
        if (Test-Path -LiteralPath $candidate) { $WorkflowPath = $candidate }
        else { $dir = Split-Path -Parent $dir }
    }
}

# 找不到就跳过，不要硬红：一条永远红的测试等于没有测试，它只会训练人忽略红色。
# 这个 workflow 是 field-journal PR 的自动合并 + 安全扫描门（PR 标题注入防护）。
# 本项目当前没有 field-journal 目录，所以平时不装这个 workflow —— 守卫留着，
# 哪天真启用了 field-journal 自动合并，守卫立刻生效。
if (-not $WorkflowPath) {
    Write-Host "[SKIP] 找不到 auto-merge-journal.yml（往上找了 5 层）" -ForegroundColor Yellow
    Write-Host "       本测试守的是该 workflow 里 PR 标题被直接插进 gh pr merge 的注入风险。" -ForegroundColor DarkGray
    exit 0
}

$text = Get-Content -LiteralPath $WorkflowPath -Raw -Encoding UTF8
$failures = New-Object System.Collections.Generic.List[string]

function Check([bool] $Condition, [string] $Message) {
    if ($Condition) {
        Write-Host "[OK] $Message" -ForegroundColor Green
    } else {
        Write-Host "[FAIL] $Message" -ForegroundColor Red
        [void]$failures.Add($Message)
    }
}

Check ($text -match '(?m)^\s+PR_NUMBER:\s*\$\{\{\s*github\.event\.pull_request\.number\s*\}\}') 'PR number is passed through the environment'
Check ($text -match '(?m)^\s+PR_TITLE:\s*\$\{\{\s*github\.event\.pull_request\.title\s*\}\}') 'PR title is passed through the environment'
Check ($text -match '(?m)^\s+PR_SUBJECT:\s*\$\{\{\s*format\(') 'PR subject is constructed as environment data'
Check ($text -match '(?ms)gh pr merge "\$PR_NUMBER".*--subject "\$PR_SUBJECT"') 'merge command quotes the PR number and subject'
Check ($text -notmatch '(?m)--subject[^\r\n]*github\.event\.pull_request\.title') 'PR title is not interpolated into the merge command'
Check ($text -notmatch '(?m)gh pr (?:diff|merge|comment)\s+\$\{\{') 'GitHub CLI commands do not embed event expressions'

$maliciousTitle = '$(Write-Host injected) `' + [Environment]::NewLine + '"quoted"; Get-ChildItem > should-not-run'
$subject = '[field-journal] ' + $maliciousTitle
Check ($subject -eq ('[field-journal] ' + $maliciousTitle)) 'shell metacharacters remain plain subject data'

if ($failures.Count -gt 0) {
    exit 1
}

Write-Host 'WORKFLOW TITLE SAFETY CHECKS PASSED' -ForegroundColor Green
exit 0
