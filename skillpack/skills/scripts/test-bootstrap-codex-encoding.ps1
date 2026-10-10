#Requires -Version 5.1
param(
    [string]$ScratchDir = ''
)
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
$scriptDir = $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($ScratchDir)) {
    $ScratchDir = Join-Path ([System.IO.Path]::GetTempPath()) ('reverse-skill-codex-encoding-' + [guid]::NewGuid().ToString('N'))
}
New-Item -ItemType Directory -Path $ScratchDir -Force | Out-Null

. (Join-Path $scriptDir 'lib\Bootstrap.ps1')

# Load only the functions under test; do not execute bootstrap installation code.
$bootstrapPath = Join-Path $scriptDir 'bootstrap-reverse.ps1'
$tokens = $null
$errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($bootstrapPath, [ref]$tokens, [ref]$errors)
if ($errors.Count -gt 0) {
    throw "bootstrap-reverse.ps1 parse failed: $($errors[0].Message)"
}
foreach ($name in @('ConvertTo-TomlLiteral', 'Remove-CodexMcpServerBlocks', 'Set-CodexMcpServer')) {
    $functionAst = $ast.Find({
        param($node)
        $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq $name
    }, $true)
    if ($null -eq $functionAst) {
        throw "Function not found: $name"
    }
    . ([scriptblock]::Create($functionAst.Extent.Text))
}

function Assert-True {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) {
        throw "ASSERTION FAILED: $Message"
    }
    Write-Host "[OK] $Message" -ForegroundColor Green
}

function Test-CodexConfigRoundTrip {
    param(
        [string]$Name,
        [bool]$WithBom,
        [string]$Newline
    )

    $path = Join-Path $ScratchDir "$Name.toml"
    $original = @(
        "[projects.'e:\codex目录\blender脚本管理器']",
        'trust_level = "trusted"',
        '',
        '[mcp_servers.existing]',
        'command = "existing"'
    ) -join $Newline
    $original += $Newline
    [System.IO.File]::WriteAllText($path, $original, [System.Text.UTF8Encoding]::new($WithBom))

    $oldConfigPath = $env:CODEX_CONFIG_PATH
    try {
        $env:CODEX_CONFIG_PATH = $path
        Set-CodexMcpServer -ServerName 'encoding-test' -ServerDefinition @{
            type = 'stdio'
            command = 'cmd'
            args = @('/c', 'echo', '中文参数')
        }
        Set-CodexMcpServer -ServerName 'encoding-test' -ServerDefinition @{
            type = 'stdio'
            command = 'cmd'
            args = @('/c', 'echo', '中文参数')
        }
    }
    finally {
        $env:CODEX_CONFIG_PATH = $oldConfigPath
    }

    $bytes = [System.IO.File]::ReadAllBytes($path)
    $hasBom = $bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF
    Assert-True ($hasBom -eq $WithBom) "$Name preserves UTF-8 BOM state"

    $text = [System.Text.Encoding]::UTF8.GetString($bytes)
    if ($text.Length -gt 0 -and $text[0] -eq [char]0xFEFF) {
        $text = $text.Substring(1)
    }
    Assert-True ($text.Contains("[projects.'e:\codex目录\blender脚本管理器']")) "$Name preserves Chinese TOML path and closing quote"
    Assert-True ($text.Contains('[mcp_servers.encoding-test]')) "$Name adds MCP server"
    Assert-True (([regex]::Matches($text, '(?m)^\[mcp_servers\.encoding-test\]\r?$')).Count -eq 1) "$Name updates MCP server idempotently"
    Assert-True ($text.Contains('中文参数')) "$Name preserves new Chinese values"
    if ($Newline -eq "`r`n") {
        Assert-True (-not ($text -replace "`r`n", '').Contains("`n")) "$Name preserves CRLF newlines"
    }
}

Test-CodexConfigRoundTrip -Name 'utf8-no-bom-crlf' -WithBom $false -Newline "`r`n"
Test-CodexConfigRoundTrip -Name 'utf8-bom-lf' -WithBom $true -Newline "`n"

$newPath = Join-Path $ScratchDir 'new-config.toml'
$oldConfigPath = $env:CODEX_CONFIG_PATH
try {
    $env:CODEX_CONFIG_PATH = $newPath
    Set-CodexMcpServer -ServerName 'new-config-test' -ServerDefinition @{ command = '中文命令' }
}
finally {
    $env:CODEX_CONFIG_PATH = $oldConfigPath
}
$newBytes = [System.IO.File]::ReadAllBytes($newPath)
$newHasBom = $newBytes.Length -ge 3 -and $newBytes[0] -eq 0xEF -and $newBytes[1] -eq 0xBB -and $newBytes[2] -eq 0xBF
Assert-True (-not $newHasBom) 'new config uses UTF-8 without BOM'
$newText = [System.Text.Encoding]::UTF8.GetString($newBytes)
Assert-True ($newText.Contains('[mcp_servers.new-config-test]')) 'new config contains MCP server block'
Assert-True ($newText.Contains('中文命令')) 'new config preserves Chinese values'

$invalidPath = Join-Path $ScratchDir 'invalid-utf8.toml'
[System.IO.File]::WriteAllBytes($invalidPath, [byte[]](0x5B, 0x80, 0x5D))
$oldConfigPath = $env:CODEX_CONFIG_PATH
$threw = $false
try {
    $env:CODEX_CONFIG_PATH = $invalidPath
    Set-CodexMcpServer -ServerName 'must-not-write' -ServerDefinition @{ command = 'x' }
}
catch [System.Text.DecoderFallbackException] {
    $threw = $true
}
finally {
    $env:CODEX_CONFIG_PATH = $oldConfigPath
}
Assert-True $threw 'invalid UTF-8 fails closed instead of rewriting the file'
$invalidBytes = [System.IO.File]::ReadAllBytes($invalidPath)
Assert-True ($invalidBytes.Length -eq 3 -and $invalidBytes[1] -eq 0x80) 'invalid UTF-8 file remains unchanged'

Write-Host 'OVERALL: ALL PASS' -ForegroundColor Green
