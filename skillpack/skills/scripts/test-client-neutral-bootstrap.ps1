#requires -Version 5

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
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$bootstrap = Join-Path $scriptDir 'bootstrap-reverse.ps1'
$bootstrapLib = Join-Path $scriptDir 'lib\Bootstrap.ps1'
$scratch = Join-Path ([System.IO.Path]::GetTempPath()) ('reverse-client-neutral-' + [guid]::NewGuid().ToString('n'))
$binDir = Join-Path $scratch 'bin'
$clientDir = Join-Path $scratch 'client'
$claudeConfig = Join-Path $clientDir 'claude.json'
$codexConfig = Join-Path $clientDir 'codex.toml'

New-Item -ItemType Directory -Force -Path $binDir, $clientDir | Out-Null
try {
    foreach ($name in @('node', 'npm', 'npx')) {
        $cmdPath = Join-Path $binDir ($name + '.cmd')
        @('@echo off', 'if "%1"=="--version" echo 1.0.0', 'exit /b 0') | Set-Content -LiteralPath $cmdPath -Encoding ascii
    }

    $oldPath = $env:PATH
    $oldClaudeConfig = $env:CLAUDE_MCP_CONFIG
    $oldCodexConfig = $env:CODEX_CONFIG_PATH
    $env:PATH = "$binDir;$oldPath"
    $env:CLAUDE_MCP_CONFIG = $claudeConfig
    $env:CODEX_CONFIG_PATH = $codexConfig

    $defaultOutput = (& $bootstrap -Capability jshookmcp -SkipRefresh | Out-String)
    if (Test-Path -LiteralPath $claudeConfig) { throw 'default bootstrap wrote Claude global config' }
    if (Test-Path -LiteralPath $codexConfig) { throw 'default bootstrap wrote Codex global config' }
    if ($defaultOutput -notmatch '"status"') { throw 'default bootstrap produced no per-capability status report' }

    $codexOutput = (& $bootstrap -Capability jshookmcp -SkipRefresh -McpHostTarget Codex | Out-String)
    if (Test-Path -LiteralPath $claudeConfig) { throw 'Codex-only bootstrap wrote Claude config' }
    if (-not (Test-Path -LiteralPath $codexConfig)) { throw 'Codex-only bootstrap did not write Codex config' }
    if ((Get-Content -LiteralPath $codexConfig -Raw) -notmatch '(?m)^\[mcp_servers\.jshook\]\r?$') { throw 'Codex config missing jshook MCP block' }
    if ($codexOutput -notmatch '"status"\s*:\s*"(installed|installed-not-locatable)"') { throw 'Codex-only bootstrap did not report a measured status' }

    # 回归守卫：npx 存在不等于 jshookmcp 存在 —— 测量层不得把运行时误报成能力本体。
    . $bootstrapLib
    $tool = Resolve-ReverseToolSpec -Name 'jshookmcp'
    if ($tool.Available) { throw 'npx must not masquerade as jshookmcp tool availability' }
    $measured = Measure-ReverseCapability -Name 'jshookmcp'
    if ($null -eq $measured) { throw 'jshookmcp has no capability definition in the manifest' }
    if ($null -eq $measured.RuntimeAvailable) { throw 'npm-mcp capability should report npx runtime availability' }
    if ($measured.ToolPath) { throw 'jshookmcp must not resolve to a local executable before registration' }

    Remove-Item -LiteralPath $codexConfig -Force
    $claudeOutput = (& $bootstrap -Capability jshookmcp -SkipRefresh -McpHostTarget Claude | Out-String)
    if (-not (Test-Path -LiteralPath $claudeConfig)) { throw 'Claude-only bootstrap did not write Claude config' }
    if (Test-Path -LiteralPath $codexConfig) { throw 'Claude-only bootstrap wrote Codex config' }
    $json = Get-Content -LiteralPath $claudeConfig -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($null -eq $json.mcpServers.jshook) { throw 'Claude config missing jshook MCP server' }
    if ($claudeOutput -notmatch '"status"\s*:\s*"(installed|installed-not-locatable)"') { throw 'Claude-only bootstrap did not report a measured status' }

    Write-Host 'client-neutral PowerShell bootstrap/discovery regression passed'
}
finally {
    if ($null -ne $oldPath) { $env:PATH = $oldPath }
    $env:CLAUDE_MCP_CONFIG = $oldClaudeConfig
    $env:CODEX_CONFIG_PATH = $oldCodexConfig
    Remove-Item -LiteralPath $scratch -Recurse -Force -ErrorAction SilentlyContinue
}
