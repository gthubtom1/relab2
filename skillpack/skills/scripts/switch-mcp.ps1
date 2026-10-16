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
} catch { }   # scan-ok: 探测 pyre 解释器只是"尽量用真解释器"；失败就退回 'python'，判据是下一行 & $py 的退出码
& $py (Join-Path $PSScriptRoot 'switch-mcp.py') $Profile
# ★ 2026-10-16（D4）：不转发子进程退出码 = 脚本永远 exit 0 —— 切换失败会被当成成功。
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
