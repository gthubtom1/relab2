#Requires -Version 5.1
# next-evidence-id.ps1 —— 只读助手：算出「下一个该用的证据号」。
#
# ★ 它**不发号、不占号、不写任何文件**。
#   只是把人工要找的那个数算出来（扫 <CaseRoot>/evidence/E-*.md，取最小未占用）。
#   真正的写入仍由 `append-evidence.ps1 -Id` 完成 —— 那边用 CreateNew 语义，
#   已存在的文件**不可能被覆盖**（重复用号会直接抛错）。
#   所以本脚本与 append-evidence 之间不存在竞争：算错了最坏结果只是 append 抛错。
#
# 为什么需要它（K4）：
#   证据号是人工填的。删过一条、或分几次追加之后，「下一个」不再等于「条数 + 1」，
#   人得自己翻 evidence/ 目录数号 —— 数错就撞号，撞号又只在 append 时才暴露。
#
# Usage:
#   powershell -File skills/scripts/next-evidence-id.ps1 -CaseRoot work\my-case
#   powershell -File skills/scripts/next-evidence-id.ps1 -CaseRoot work\my-case -Json
#
# 输出（非 -Json）：E-004
# 输出（-Json）   ：{"next":"E-004","used":["E-001","E-002","E-003"]}
#
# 退出码：0 成功（含目录不存在 / 目录为空 —— 都是 E-001）；1 参数不合法。
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string] $CaseRoot,

    [switch] $Json
)
# ★ PSModulePath 自愈（2026-10-10 注入，路径由 inject-psmp.py 统一计算）：剔除 WindowsApps 版 PowerShell 7 的模块目录，否则 PS 5.1 会因 TypeData 重复定义失败而使 Get-FileHash / Get-ExecutionPolicy 不可用（已造成两次假绿 + 一次失败被吞）。重算/迁移后请重跑 work/envinit/inject-psmp.py
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

$evDir = Join-Path $CaseRoot 'evidence'

# 用到的号 = evidence 目录里 E-<数字>.md 的数字部分（补零宽度无所谓，按数值比）。
$usedNumbers = New-Object System.Collections.Generic.List[int]
$usedIds = New-Object System.Collections.Generic.List[string]
if (Test-Path -LiteralPath $evDir -PathType Container) {
    foreach ($f in @(Get-ChildItem -LiteralPath $evDir -Filter 'E-*.md' -File -ErrorAction SilentlyContinue)) {
        $m = [regex]::Match($f.Name, '^E-(\d+)\.md$')
        if (-not $m.Success) { continue }
        $usedNumbers.Add([int]$m.Groups[1].Value)
        $usedIds.Add([System.IO.Path]::GetFileNameWithoutExtension($f.Name))
    }
}

# 最小未占用。宽度：至少 3 位；超过 999 时自然加宽（E-1000）。
$next = 1
$taken = @{}
foreach ($n in $usedNumbers) { $taken[$n] = $true }
while ($taken.ContainsKey($next)) { $next++ }
$width = [Math]::Max(3, ([string]$next).Length)
$nextId = 'E-' + ([string]$next).PadLeft($width, '0')

$sortedUsed = @($usedIds | Sort-Object)

if ($Json) {
    [pscustomobject]@{
        next = $nextId
        used = $sortedUsed
    } | ConvertTo-Json -Compress
}
else {
    Write-Output $nextId
}
exit 0
