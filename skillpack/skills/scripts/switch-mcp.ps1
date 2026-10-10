#Requires -Version 5.1
param(
    [ValidateSet('daily', 'full', 'show')]
    [string] $Profile = 'show'
)
$py = 'D:\EXE\python\python.exe'
if (-not (Test-Path -LiteralPath $py)) { $py = 'python' }
& $py (Join-Path $PSScriptRoot 'switch-mcp.py') $Profile
