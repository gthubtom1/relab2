# ★ PSModulePath 自愈（2026-10-10 注入，路径由 inject-psmp.py 统一计算）：剔除 WindowsApps 版 PowerShell 7 的模块目录，否则 PS 5.1 会因 TypeData 重复定义失败而使 Get-FileHash / Get-ExecutionPolicy 不可用（已造成两次假绿 + 一次失败被吞）。重算/迁移后请重跑 work/envinit/inject-psmp.py
. 'C:\relab2\skillpack\skills\scripts\lib\PsModulePathInit.ps1'

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# Resolves the PowerShell executable to use when a script must launch a child
# PowerShell process (e.g. to run another .ps1 in isolation with -NoProfile).
#
# Why not hard-code "powershell":
#   - Modern Windows machines may install only PowerShell 7+ ("pwsh") and not
#     ship Windows PowerShell 5.1 ("powershell.exe") on PATH.
#   - Conversely, bare "powershell" resolves to 5.1, which mis-parses UTF-8
#     scripts without BOM when nested from pwsh.
# Resolution order (highest confidence first):
#   1. Current process executable (the host that launched this script)
#   2. pwsh on PATH
#   3. powershell on PATH
#   4. %SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe
# Returns the absolute path to the executable. Throws if nothing usable exists.
function Resolve-ReverseHostExe {
    [CmdletBinding()]
    [OutputType([string])]
    param()

    $hostExe = $null

    try {
        $procPath = (Get-Process -Id $PID -ErrorAction Stop).Path
        if ($procPath -and (Test-Path -LiteralPath $procPath)) {
            $hostExe = $procPath
        }
    } catch { }

    if (-not $hostExe) {
        $cmd = Get-Command pwsh -ErrorAction SilentlyContinue
        if ($cmd -and $cmd.Source) {
            $hostExe = $cmd.Source
        }
    }

    if (-not $hostExe) {
        $cmd = Get-Command powershell -ErrorAction SilentlyContinue
        if ($cmd -and $cmd.Source) {
            $hostExe = $cmd.Source
        }
    }

    if (-not $hostExe -and $env:SystemRoot) {
        $fallback = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
        if (Test-Path -LiteralPath $fallback) {
            $hostExe = $fallback
        }
    }

    if (-not $hostExe) {
        throw 'No usable PowerShell host executable found (tried current process, pwsh, powershell, Windows PowerShell fallback).'
    }

    return $hostExe
}
