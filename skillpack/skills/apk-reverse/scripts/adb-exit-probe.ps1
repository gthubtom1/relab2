#Requires -Version 5.1
# 内联探针（由 test-adb-exit-contract.ps1 逐 case 调用）
# 每个 case 必须独立进程：$LASTEXITCODE 是会话级变量。
param(
    [Parameter(Mandatory = $true)][string] $FakeAdb,
    [Parameter(Mandatory = $true)][string] $ApkDebug
)

$ErrorActionPreference = 'Stop'

function Require-Tool { param([string] $Name) $FakeAdb }
function Get-Device { 'FAKE-DEVICE' }

$src = Get-Content -LiteralPath $ApkDebug -Raw -Encoding UTF8
$tokens = $null
$errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseInput(
    $src, [ref] $tokens, [ref] $errors)
if ($errors -and $errors.Count) {
    Write-Output ('ADBCONTRACT_ERR=' + $errors[0].Message)
    exit 3
}

# 用 AST 取 Adb 函数体，不是正则 —— 测的是脚本里那段真实代码
$fn = $ast.FindAll({
        param($n)
        $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
        $n.Name -eq 'Adb'
    }, $true) | Select-Object -First 1
if (-not $fn) {
    Write-Output 'ADBCONTRACT_ERR=no Adb function'
    exit 3
}

Invoke-Expression $fn.Extent.Text
$null = Adb 'install' '-r' 'dummy.apk'
Write-Output ('ADBCONTRACT=' + $script:AdbRc)