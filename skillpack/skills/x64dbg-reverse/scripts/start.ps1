#Requires -Version 5.1
<#
start.ps1 —— 幂等起 x64dbg，让 x64dbg-MCP(9094) 可用。

为什么要有这个包装：工具根路径不许写死；而且"已在监听"要直接成功返回，
不要重复起实例（多开会把 9094/9095 搅乱，并留下僵尸进程）。

用法：
  powershell -NoProfile -ExecutionPolicy Bypass -File start.ps1
  ... -WaitSeconds 40        等更久（慢机器 / 大盘首启）

退出码：0 已监听（新起或本来就在）／2 找不到可用的启动器
#>
[CmdletBinding()]
param(
    [string]$ToolRoot = '',
    [int]$Port = 9094,
    [int]$WaitSeconds = 25
)

$ErrorActionPreference = 'Continue'
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }

function Test-Listening([int]$p) {
    $c = Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue
    return $null -ne $c
}

if (Test-Listening $Port) {
    Write-Host ("x64dbg MCP already listening on {0}" -f $Port)
    exit 0
}

# --- 工具根：环境变量优先，约定值兜底（与全仓一致，不写死）---
$roots = New-Object System.Collections.Generic.List[string]
if ($ToolRoot) { [void]$roots.Add($ToolRoot) }
if ($env:REVERSE_TOOL_ROOT) { [void]$roots.Add($env:REVERSE_TOOL_ROOT) }
[void]$roots.Add('D:\Tools')

$starter = $null
foreach ($r in $roots) {
    if (-not $r) { continue }
    $cand = Join-Path $r 'cli\start-x64dbg-mcp.ps1'
    if (Test-Path -LiteralPath $cand) { $starter = $cand; break }
}
if (-not $starter) {
    Write-Host 'ERROR: 找不到 x64dbg 的启动器（<工具根>\cli\start-x64dbg-mcp.ps1）。' -ForegroundColor Red
    Write-Host '  用探测层确认工具根：' -ForegroundColor Yellow
    Write-Host '    . <技能包>\skillpack\skills\scripts\lib\Bootstrap.ps1' -ForegroundColor Yellow
    Write-Host "    (Resolve-ReverseToolSpec -Name 'x64dbg').Command" -ForegroundColor Yellow
    Write-Host '  也可用 -ToolRoot 指定，或设 $env:REVERSE_TOOL_ROOT。' -ForegroundColor Yellow
    exit 2
}

Write-Host ("starting x64dbg via {0}" -f $starter)
& $starter -Port $Port -WaitSeconds $WaitSeconds

for ($i = 0; $i -lt $WaitSeconds; $i++) {
    if (Test-Listening $Port) { Write-Host ("LISTEN on {0}" -f $Port) -ForegroundColor Green; exit 0 }
    Start-Sleep -Seconds 1
}
Write-Host ("ERROR: {0} 秒内 9094 未监听 —— 检查 x64dbg 是否真的起来了。" -f $WaitSeconds) -ForegroundColor Red
exit 2
