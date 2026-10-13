#Requires -Version 5.1
<#
mcp-status.ps1 —— 一屏看清 MCP 通道：注册了哪些 / 谁在监听 / 怎么起。

为什么需要它：
  HTTP 型 MCP **按需启动、平时不监听是设计**。但"看不到工具"和"没这个工具"是两件事，
  宿主在连不上时只是把工具从工具表里拿掉 —— 模型于是既看不到工具，也看不到"该起服务"。
  本脚本把那张目录**摆到眼前**：动手前跑一次，就知道有哪些通道可挂、要不要先起。

用法：
  powershell -NoProfile -ExecutionPolicy Bypass -File mcp-status.ps1
  ... -Json        机器可读
  ... -ProbeOnly   只探端口，不打启动提示

退出码：0 总有（这是一份报告，不是门禁）。
#>
param(
    [string] $AgentDir = '',
    [string] $RepoRoot = '',
    [string] $ToolRoot = '',
    [switch] $Json,
    [switch] $ProbeOnly
)

$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }

# --- 路径解析（不写死）---
if (-not $AgentDir) { $AgentDir = if ($env:PI_CODING_AGENT_DIR) { $env:PI_CODING_AGENT_DIR } else { Join-Path $env:USERPROFILE '.omp\agent' } }
if (-not $RepoRoot) { $RepoRoot = if ($env:REVERSE_SKILL_ROOT) { $env:REVERSE_SKILL_ROOT } else { 'C:\relab2' } }
if (-not $ToolRoot) { $ToolRoot = if ($env:REVERSE_TOOL_ROOT) { $env:REVERSE_TOOL_ROOT } else { 'D:\Tools' } }

$mcpFile = Join-Path $AgentDir 'mcp.json'
if (-not (Test-Path -LiteralPath $mcpFile)) {
    Write-Host ("WARN: 没找到 {0}（宿主可能用别的配置位置）" -f $mcpFile) -ForegroundColor Yellow
    exit 0
}

try { $cfg = Get-Content -LiteralPath $mcpFile -Raw -Encoding UTF8 | ConvertFrom-Json }
catch { Write-Host ("ERROR: mcp.json 解析失败：{0}" -f $_.Exception.Message) -ForegroundColor Red; exit 0 }

# --- 启动方式登记。名字 → 怎么起（只登记方式，不登记"装没装"）---
$startHints = @{
    'idapro'       = @{ kind = 'http'; how = ('powershell -NoProfile -ExecutionPolicy Bypass -File "{0}\skillpack\skills\ida-reverse\scripts\start.ps1"' -f $RepoRoot) }
    'x64dbg-mcp'   = @{ kind = 'http'; how = ('powershell -NoProfile -ExecutionPolicy Bypass -File "{0}\cli\start-x64dbg-mcp.ps1"' -f $ToolRoot) }
    'pyghidra-mcp' = @{ kind = 'stdio-http'; how = 'stdio：宿主按会话自动拉起；HTTP 形态冷启 7–10s（端点见 references/tool-registry.md）' }
    'angr-mcp'     = @{ kind = 'stdio'; how = 'stdio：宿主按会话自动拉起，无需手动起' }
}

function Test-Port {
    param([string] $HostName, [int] $Port, [int] $TimeoutMs = 1000)
    try {
        $c = New-Object System.Net.Sockets.TcpClient
        $iar = $c.BeginConnect($HostName, $Port, $null, $null)
        if ($iar.AsyncWaitHandle.WaitOne($TimeoutMs, $false) -and $c.Connected) { $c.Close(); return $true }
        $c.Close(); return $false
    } catch { return $false }
}

$rows = New-Object System.Collections.Generic.List[object]
foreach ($p in $cfg.mcpServers.PSObject.Properties) {
    $name = $p.Name
    $s = $p.Value
    $transport = if ($s.type) { $s.type } elseif ($s.url) { 'http' } else { 'stdio' }
    $hostName = $null; $port = 0; $listening = $null
    if ($s.url) {
        try {
            $u = [uri]$s.url
            $hostName = $u.Host; $port = $u.Port
            $listening = if ($ProbeOnly -or $true) { Test-Port -HostName $hostName -Port $port } else { $null }
        } catch { }
    }
    $hint = if ($startHints.ContainsKey($name)) { $startHints[$name] } else { $null }
    $rows.Add([ordered]@{
        name       = $name
        transport  = $transport
        endpoint   = if ($s.url) { $s.url } elseif ($s.command) { ('stdio: {0}' -f $s.command) } else { '' }
        listening  = $listening
        start_note = if ($hint) { $hint.how } else { '（未登记启动方式）' }
    })
}

if ($Json) { $rows | ConvertTo-Json -Depth 5; exit 0 }

Write-Host ''
Write-Host '=== MCP 通道目录（注册 / 监听 / 怎么起） ===' -ForegroundColor Cyan
Write-Host ('{0,-16} {1,-12} {2,-10} {3}' -f 'NAME', 'TRANSPORT', 'LISTENING', 'ENDPOINT')
Write-Host ('-' * 100)
foreach ($r in $rows) {
    $l = if ($null -eq $r.listening) { 'n/a' } elseif ($r.listening) { 'LISTEN' } else { 'closed' }
    $color = if ($r.listening -eq $true) { 'Green' } elseif ($r.listening -eq $false) { 'DarkGray' } else { 'Gray' }
    Write-Host (('{0,-16} {1,-12} {2,-10} {3}' -f $r.name, $r.transport, $l, $r.endpoint)) -ForegroundColor $color
}
Write-Host ''
Write-Host '--- 要用的通道没起（closed）→ 按下面起；起完重跑本脚本确认 LISTEN ---' -ForegroundColor Yellow
foreach ($r in $rows) {
    if ($r.listening -eq $false) {
        Write-Host ("  {0}:" -f $r.name) -ForegroundColor Yellow
        Write-Host ("      {0}" -f $r.start_note)
    }
}
Write-Host ''
Write-Host '提醒：HTTP 型 MCP 平时关着是**设计**，不是故障；端点事实源是 references/tool-registry.md。'
Write-Host '      stdio 型（angr / pyghidra）由宿主自动拉起，本脚本只报不催。'
exit 0
