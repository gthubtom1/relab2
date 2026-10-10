#Requires -Version 5.1
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
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = (Resolve-Path (Join-Path $here "..\..")).Path
$scratch = Join-Path $env:TEMP ("rs-consol-" + [guid]::NewGuid().ToString("N").Substring(0,8))
New-Item -ItemType Directory -Path (Join-Path $scratch "evidence") | Out-Null
Copy-Item (Join-Path $root "examples\ctf-demo\evidence\E-001.md") (Join-Path $scratch "evidence\E-001.md")
Copy-Item (Join-Path $root "examples\ctf-demo\evidence\E-002.md") (Join-Path $scratch "evidence\E-002.md")

function Assert-FindingFields([string]$report) {
    foreach ($f in @("confidence:","location:","evidence_ids:","status:")) {
        if ($report -notmatch [regex]::Escape($f)) { throw "missing field $f" }
    }
    if ($report -match "evidence_refs:") { throw "legacy evidence_refs leaked" }
}

# Python path
python (Join-Path $root "skills\scripts\consolidate_evidence.py") --case-root $scratch --evidence-ids "E-001,E-002" --finding-id F-CONSOL-1 --title "triage merge" --description "merged two triage notes" --severity info --status validated --confidence medium --location "see E-001 E-002" | Out-Null
$r1 = Get-Content (Join-Path $scratch "report\report.md") -Raw
Assert-FindingFields $r1
$e1 = Get-Content (Join-Path $scratch "evidence\E-001.md") -Raw
if ($e1 -notmatch "superseded by F-CONSOL-1") { throw "py did not mark superseded" }

# reset for ps1
Remove-Item (Join-Path $scratch "report") -Recurse -Force
Copy-Item (Join-Path $root "examples\ctf-demo\evidence\E-001.md") (Join-Path $scratch "evidence\E-001.md") -Force
Copy-Item (Join-Path $root "examples\ctf-demo\evidence\E-002.md") (Join-Path $scratch "evidence\E-002.md") -Force
& (Join-Path $root "skills\scripts\consolidate-evidence.ps1") -CaseRoot $scratch -EvidenceIds "E-001,E-002" -FindingId F-CONSOL-2 -Title "triage merge ps1" -Description "merged two triage notes" -Severity info -Status validated -Confidence medium -Location "see E-001 E-002"
$r2 = Get-Content (Join-Path $scratch "report\report.md") -Raw
Assert-FindingFields $r2
$e2 = Get-Content (Join-Path $scratch "evidence\E-001.md") -Raw
if ($e2 -notmatch "superseded by F-CONSOL-2") { throw "ps1 did not mark superseded" }

# review_case accepts superseded
$demo = Join-Path $scratch "ctf"
Copy-Item (Join-Path $root "examples\ctf-demo") $demo -Recurse
python (Join-Path $root "skills\scripts\consolidate_evidence.py") --case-root $demo --evidence-ids "E-001" --finding-id F-001 --title "keep contract" --description "ok" --severity info --status validated --confidence medium --location "E-001" | Out-Null
# F-001 already exists in ctf-demo report; just check the case still PARSES with
# superseded evidence. --verify-hashes cannot pass here by design: consolidation
# rewrites E-001.md (adds the superseded marker), which changes its SHA-256.
$review = python (Join-Path $root "skills\case-review\scripts\review_case.py") $demo 2>&1 | Select-Object -Last 8
if ($LASTEXITCODE -ne 0) { throw "review_case failed to parse consolidated case:`n$($review -join [Environment]::NewLine)" }
Write-Host "CONSOLIDATE_ALIGN_OK"
Remove-Item $scratch -Recurse -Force
