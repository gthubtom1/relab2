#Requires -Version 5.1
param(
    [ValidateSet('daily', 'full', 'show')]
    [string] $Profile = 'show'
)
# 解释器现查，不写死路径：优先探测层别名 pyre，退回 PATH 上的 python
$py = 'python'
try {
    . (Join-Path $PSScriptRoot 'lib\Bootstrap.ps1')
    $r = Resolve-ReverseToolSpec -Name 'pyre'
    if ($r.Available -and $r.Command) { $py = $r.Command }
} catch { }
& $py (Join-Path $PSScriptRoot 'switch-mcp.py') $Profile
