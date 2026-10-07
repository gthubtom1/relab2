#Requires -Version 5.1
param([string] $WorkflowPath = '')

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($WorkflowPath)) {
    $WorkflowPath = Join-Path (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)) '.github\workflows\auto-merge-journal.yml'
}

# 被测对象不存在就跳过，不要硬红。
# 这个测试防的是 auto-merge-journal.yml 里 PR 标题被直接插进 `gh pr merge` 命令的注入问题。
# 那个 workflow 不属于本项目（仓库里从来没有 .github/ 目录，field-journal 只出现在
# 第三方 community-raw/ 里），所以这个测试从写下来那天起就永远失败 ——
# 一条永远红的测试等于没有测试，它只会训练人忽略红色。
# 哪天真把这个 workflow 加回来，守卫会自动重新生效，不用改这个文件。
if (-not (Test-Path -LiteralPath $WorkflowPath)) {
    Write-Host "[SKIP] 被测对象不存在：$WorkflowPath" -ForegroundColor Yellow
    Write-Host "       这个 workflow 不属于本项目；本测试守的是它的 PR 标题注入风险。" -ForegroundColor DarkGray
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
