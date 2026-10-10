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
Set-StrictMode -Version Latest

function Resolve-ReverseProjectRoot {
    [CmdletBinding()]
    param(
        [AllowEmptyString()]
        [string]$RequestedRoot = ''
    )

    $root = if ([string]::IsNullOrWhiteSpace($RequestedRoot)) {
        (Get-Location).ProviderPath
    } else {
        $RequestedRoot
    }

    if ([string]::IsNullOrWhiteSpace($root)) {
        throw 'Unable to resolve the analysis project root.'
    }

    if (-not (Test-Path -LiteralPath $root)) {
        New-Item -ItemType Directory -Force -Path $root | Out-Null
    }
    if (-not (Test-Path -LiteralPath $root -PathType Container)) {
        throw "Project root is not a directory: $root"
    }

    $item = Get-Item -LiteralPath $root
    if ($item.PSProvider.Name -ne 'FileSystem') {
        throw "Project root must use the FileSystem provider: $root"
    }

    return $item.FullName
}
