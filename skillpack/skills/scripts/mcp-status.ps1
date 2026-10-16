#Requires -Version 5.1
<#
mcp-status.ps1 —— 一屏看清 MCP 通道：注册了哪些 / 谁在监听 / 怎么起。

为什么需要它：
  HTTP 型 MCP **按需启动、平时不监听是设计**。但"看不到工具"和"没这个工具"是两件事，
  宿主在连不上时只是把工具从工具表里拿掉 —— 模型于是既看不到工具，也看不到"该起服务"。
  本脚本把那张目录**摆到眼前**：动手前跑一次，就知道有哪些通道可挂、要不要先起。

跨宿主：MCP 注册是**每个宿主自己的文件**（这份不通用）。本脚本按各家的真实位置找：
  omp        ~\.omp\agent\mcp.json                               (JSON)
  Claude Code ~\.claude.json （顶层 mcpServers）                   (JSON)
             <cwd>\.mcp.json （项目级）                            (JSON)
  Cursor     ~\.cursor\mcp.json / <cwd>\.cursor\mcp.json           (JSON)
  Codex      ~\.codex\config.toml （[mcp_servers.NAME] 表）        (TOML，最小解析)
找不到的宿主直接跳过 —— 不是故障，"这家没装/没配"。

用法：
  powershell -NoProfile -ExecutionPolicy Bypass -File mcp-status.ps1
  ... -Json        机器可读


退出码：0 总有（这是一份报告，不是门禁）。
#>
param(
    [string] $AgentDir = '',
    [string] $RepoRoot = '',
    [string] $ToolRoot = '',
    [string] $Cwd = '',
    [switch] $Json
)

$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }   # scan-ok: 控制台编码设置失败只影响中文显示，不影响任何判定结果

if (-not $AgentDir) { $AgentDir = if ($env:PI_CODING_AGENT_DIR) { $env:PI_CODING_AGENT_DIR } else { Join-Path $env:USERPROFILE '.omp\agent' } }
if (-not $RepoRoot) { $RepoRoot = if ($env:REVERSE_SKILL_ROOT) { $env:REVERSE_SKILL_ROOT } else { 'C:\relab2' } }
if (-not $ToolRoot) { $ToolRoot = if ($env:REVERSE_TOOL_ROOT) { $env:REVERSE_TOOL_ROOT } else { 'D:\Tools' } }
if (-not $Cwd) { $Cwd = (Get-Location).Path }
$H = $env:USERPROFILE

# --- 各家注册文件的位置（找不到就跳过）---
$sources = @(
    @{ host = 'omp';         path = (Join-Path $AgentDir 'mcp.json');        kind = 'json' },
    @{ host = 'Claude Code'; path = (Join-Path $H '.claude.json');           kind = 'json-claude' },
    @{ host = 'Claude Code'; path = (Join-Path $Cwd '.mcp.json');            kind = 'json' },
    @{ host = 'Cursor';      path = (Join-Path $H '.cursor\mcp.json');       kind = 'json' },
    @{ host = 'Cursor';      path = (Join-Path $Cwd '.cursor\mcp.json');     kind = 'json' },
    @{ host = 'Codex';       path = (Join-Path $H '.codex\config.toml');     kind = 'toml' }
)

function Read-JsonServers {
    param([string] $Path, [string] $Kind)
    $servers = @{}
    try { $o = Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json } catch { return $servers }
    $bag = $null
    if ($Kind -eq 'json-claude') {
        # ~\.claude.json：mcpServers 可能在顶层，也可能在各 project 下
        if ($o.PSObject.Properties.Name -contains 'mcpServers') { $bag = $o.mcpServers }
        elseif ($o.PSObject.Properties.Name -contains 'projects') {
            foreach ($p in $o.projects.PSObject.Properties) {
                if ($p.Value.PSObject.Properties.Name -contains 'mcpServers') {
                    foreach ($s in $p.Value.mcpServers.PSObject.Properties) { $servers[$s.Name] = $s.Value }
                }
            }
            return $servers
        }
    } else {
        if ($o.PSObject.Properties.Name -contains 'mcpServers') { $bag = $o.mcpServers }
        elseif ($o.PSObject.Properties.Name -contains 'servers') { $bag = $o.servers }
    }
    if ($bag) { foreach ($s in $bag.PSObject.Properties) { $servers[$s.Name] = $s.Value } }
    return $servers
}

function Read-TomlServers {
    # 最小解析：只认 [mcp_servers.NAME] 段里的 command / args / url / type
    param([string] $Path)
    $servers = @{}
    $cur = $null
    foreach ($line in (Get-Content -LiteralPath $Path -Encoding UTF8)) {
        $t = $line.Trim()
        if ($t -match '^\[mcp_servers\.([A-Za-z0-9_\-\.]+)\]\s*$') {
            $cur = $Matches[1]
            $servers[$cur] = [pscustomobject]@{ command = $null; args = @(); url = $null; type = $null }
            continue
        }
        if ($t -match '^\[') { $cur = $null; continue }
        if (-not $cur) { continue }
        if ($t -match '^(command|url|type)\s*=\s*"([^"]*)"') {
            $k = $Matches[1]; $v = $Matches[2]
            $servers[$cur].$k = $v
        } elseif ($t -match '^args\s*=\s*\[(.*)\]') {
            $servers[$cur].args = @([regex]::Matches($Matches[1], '"([^"]*)"') | ForEach-Object { $_.Groups[1].Value })
        }
    }
    return $servers
}

# --- 启动方式登记（只登记方式，不登记"装没装"）---
$startHints = @{
    'idapro'       = ('powershell -NoProfile -ExecutionPolicy Bypass -File "{0}\skillpack\skills\ida-reverse\scripts\start.ps1"' -f $RepoRoot)
    'x64dbg-mcp'   = ('powershell -NoProfile -ExecutionPolicy Bypass -File "{0}\cli\start-x64dbg-mcp.ps1"' -f $ToolRoot)
    'pyghidra-mcp' = 'stdio：宿主按会话自动拉起；HTTP 形态冷启 7–10s（端点见 references/tool-registry.md）'
    'angr-mcp'     = 'stdio：宿主按会话自动拉起，无需手动起'
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
$seenSources = New-Object System.Collections.Generic.List[string]
foreach ($src in $sources) {
    if (-not (Test-Path -LiteralPath $src.path)) { continue }
    $seenSources.Add(("{0} -> {1}" -f $src.host, $src.path))
    $bag = if ($src.kind -eq 'toml') { Read-TomlServers -Path $src.path } else { Read-JsonServers -Path $src.path -Kind $src.kind }
    foreach ($name in $bag.Keys) {
        $s = $bag[$name]
        $url = if ($s.url) { [string]$s.url } else { $null }
        if (-not $url -and $s.command -and "$($s.command) $($s.args -join ' ')" -match '(https?://[^\s"]+)') { $url = $Matches[1] }
        # ★ 2026-10-15：懒启动代理（mcp-lazy-http.py）是 stdio 形态，args 里那个 http:// 只是
        #   它**要去拉起**的后端端点，不是宿主到它的传输方式。以前这里一律报 http/closed，
        #   会让后来人误判「通道没起 = 没接线」，实际工具已经常驻可见、后端被调用时才起。
        $isLazy = ("$($s.command) $($s.args -join ' ')" -match 'mcp-lazy-http\.py')
        $transport = if ($isLazy) { 'stdio·懒启' } elseif ($s.type) { [string]$s.type } elseif ($url) { 'http' } else { 'stdio' }
        $hostName = $null; $port = 0; $listening = $null
        if ($url) {
            try { $u = [uri]$url; $hostName = $u.Host; $port = $u.Port; $listening = Test-Port -HostName $hostName -Port $port } catch { }   # scan-ok: 解析/探测失败=>该行 host/port 留空、listening 未知（下一步 $isLazy 分支本就把它置 $null）；不会冒充"在监听"
        }
        if ($isLazy) { $listening = $null }   # 懒启动：后端在不在都不影响可用性
        $rows.Add([pscustomobject]@{
            host       = $src.host
            name       = $name
            transport  = $transport
            endpoint   = $(if ($isLazy) { 'stdio·懒启: 后端 ' + $url } elseif ($url) { $url } elseif ($s.command) { 'stdio: ' + $s.command } else { '' })
            listening  = $listening
            start_note = $(if ($isLazy) { '工具常驻可见；后端由代理在被调用时自动拉起，无需人工' } elseif ($startHints.ContainsKey($name)) { $startHints[$name] } else { '（未登记启动方式）' })
        })
    }
}

if ($Json) {
    [pscustomobject]@{ sources = @($seenSources); servers = @($rows) } | ConvertTo-Json -Depth 6
    exit 0
}

Write-Host ''
Write-Host '=== MCP 通道目录（注册 / 监听 / 怎么起）===' -ForegroundColor Cyan
if ($seenSources.Count -eq 0) {
    Write-Host ('本机没找到任何宿主的 MCP 注册文件（找过：omp / Claude Code / Cursor / Codex）。') -ForegroundColor Yellow
    Write-Host ('  这不算故障 —— 只是"这家没装或没配"。' ) -ForegroundColor Gray
} else {
    Write-Host '注册来源：'
    foreach ($s in $seenSources) { Write-Host ("  - {0}" -f $s) -ForegroundColor DarkGray }
    Write-Host ''
    Write-Host ('{0,-14} {1,-16} {2,-12} {3,-10} {4}' -f 'HOST', 'NAME', 'TRANSPORT', 'LISTENING', 'ENDPOINT')
    Write-Host ('-' * 118)
    foreach ($r in $rows) {
        $l = if ($null -eq $r.listening) { 'n/a' } elseif ($r.listening) { 'LISTEN' } else { 'closed' }
        $color = if ($r.listening -eq $true) { 'Green' } elseif ($r.listening -eq $false) { 'DarkGray' } else { 'Gray' }
        Write-Host (('{0,-14} {1,-16} {2,-12} {3,-10} {4}' -f $r.host, $r.name, $r.transport, $l, $r.endpoint)) -ForegroundColor $color
    }
    $down = @($rows | Where-Object { $_.listening -eq $false })
    if ($down.Count -gt 0) {
        Write-Host ''
        Write-Host '--- 要用的通道没起（closed）→ 按下面起；起完重跑本脚本确认 LISTEN ---' -ForegroundColor Yellow
        foreach ($r in $down) { Write-Host ("  {0}:" -f $r.name) -ForegroundColor Yellow; Write-Host ("      {0}" -f $r.start_note) }
    }
}
Write-Host ''
Write-Host '提醒：HTTP 型 MCP 平时关着是**设计**，不是故障；端点事实源是 references/tool-registry.md。'
Write-Host '      stdio 型（angr / pyghidra）由宿主自动拉起，本脚本只报不催。'
exit 0
