# ★ PSModulePath 自愈（2026-10-10 注入，路径由 inject-psmp.py 统一计算）：剔除 WindowsApps 版 PowerShell 7 的模块目录，否则 PS 5.1 会因 TypeData 重复定义失败而使 Get-FileHash / Get-ExecutionPolicy 不可用（已造成两次假绿 + 一次失败被吞）。重算/迁移后请重跑 work/envinit/inject-psmp.py
. 'C:\relab2\skillpack\skills\scripts\lib\PsModulePathInit.ps1'

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
