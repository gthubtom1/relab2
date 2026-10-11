#Requires -Version 5.1
<#
  apk-debug.ps1 的 Adb 退出码契约测试。

  测什么：`if ($script:AdbRc -ne 0)` 这个判据，在子进程退出码 0 / 非 0 时
  是否如实分支。

  为什么不用真机：真机不在的时候，install 会死在 Get-Device（没设备可枚举），
  根本走不到判据那一行。而判据本身是纯逻辑，用一个退出码可控的假 adb
  就能覆盖成功/失败两条路。

  怎么绕过探测层：Adb 里的工具来自 Require-Tool，本测试先把 Require-Tool
  重定义成返回假 adb，再从 apk-debug.ps1 里抽出 Adb 函数体单独执行 ——
  这样测的是**脚本里那段真实代码**，不是复制品。

  回归背景（2026-10-11）：Adb 曾把 `return $LASTEXITCODE` 与 stdout 混在
  同一个返回值里，`$rc = Adb ...` 拿到数组，`$rc -ne 0` 恒为真，
  install 永远走失败分支。退出码改走 $script:AdbRc 之后必须证明两条路都对。
#>

[CmdletBinding()]
param()

$ApkDebug = Join-Path $PSScriptRoot 'apk-debug.ps1'

# 探针必须落盘单独跑：内联 -Command 传多行脚本会因引号转义打碎（实测报
# 「所在位置 … 字符: 32」），而且 $LASTEXITCODE 是会话级的，
# 同一进程里连跑多个 case 会出现退出码串位。两个问题都靠独立进程解决。
$ProbeScript = Join-Path $PSScriptRoot 'adb-exit-probe.ps1'

$ErrorActionPreference = 'Stop'
$script:Fail = 0

function Write-Case {
    param([string] $Name, [bool] $Ok, [string] $Detail = '')
    if ($Ok) {
        Write-Host ('  [PASS] {0}' -f $Name) -ForegroundColor Green
    } else {
        Write-Host ('  [FAIL] {0}  {1}' -f $Name, $Detail) -ForegroundColor Red
        $script:Fail++
    }
}

# ── 造一个退出码可控的假 adb ────────────────────────────────────────────
function New-FakeAdb {
    param([int] $ExitCode)
    $dir = Join-Path $env:TEMP ('fakeadb-' + [guid]::NewGuid().ToString('n').Substring(0, 8))
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
    $bat = Join-Path $dir 'fakeadb.cmd'
    $body = "@echo off`r`n" +
            "echo Installing...`r`n" +
            "echo Success`r`n" +
            "exit /b $ExitCode`r`n"
    [System.IO.File]::WriteAllText($bat, $body, [System.Text.Encoding]::ASCII)
    return $bat
}

# ── 从 apk-debug.ps1 里按 AST 抽出 Adb 函数（不用正则，避免误匹配）──────
function Get-AdbFunctionSource {
    param([string] $Path)
    $tokens = $null
    $errors = $null
    $ast = [System.Management.Automation.Language.Parser]::ParseFile(
        (Resolve-Path $Path), [ref] $tokens, [ref] $errors)
    if ($errors -and $errors.Count) { throw "解析 $Path 失败: $($errors[0].Message)" }
    $fn = $ast.FindAll({
            param($n)
            $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
            $n.Name -eq 'Adb'
        }, $true) | Select-Object -First 1
    if (-not $fn) { throw "在 $Path 里找不到 function Adb" }
    return $fn.Extent.Text
}

$adbSrc = Get-AdbFunctionSource -Path $ApkDebug

Write-Host ''
Write-Host '=== apk-debug.ps1 · Adb 退出码契约 ===' -ForegroundColor Cyan
Write-Host ('  被测源码行数: {0}' -f ($adbSrc -split "`n").Count) -ForegroundColor DarkGray

foreach ($case in @(
        @{ Code = 0; Expect = 'success'; Label = '退出码 0 -> 成功分支' },
        @{ Code = 1; Expect = 'fail';    Label = '退出码 1 -> 失败分支' },
        @{ Code = 3; Expect = 'fail';    Label = '退出码 3 -> 失败分支（不被当成成功）' },
        @{ Code = 255; Expect = 'fail';  Label = '退出码 255 -> 失败分支' }
    )) {

    $fake = New-FakeAdb -ExitCode $case.Code
    try {
        # ★ 2026-10-11 关键：`$LASTEXITCODE` 是**会话级**变量。
        #   在同一个 PowerShell 进程里连跑多个 case 时，上一个 case 的
        #   退出码会泄漏到下一个 —— 第一次跑就出现「case 1 读到 0、
        #   case 3 读到 1、case 255 读到 3」的串位。
        #   所以每个 case 必须起一个全新的 powershell 进程。
        $out = & powershell -NoProfile -ExecutionPolicy Bypass -File $ProbeScript `
                          -FakeAdb $fake -ApkDebug $ApkDebug 2>&1
        $line = @($out | Where-Object { $_ -match 'ADBCONTRACT=' })[-1]
        $rc = $null
        if ($line) {
            $rc = [int](($line -split 'ADBCONTRACT=')[-1]).Trim()
        }

        $branch = if ($null -eq $rc) {
            'unset'
        } elseif ($rc -eq 0) {
            'success'
        } else {
            'fail'
        }

        $ok = ($branch -eq $case.Expect)
        $detail = ''
        if (-not $ok) {
            $detail = "期望 $($case.Expect) 得到 $branch (AdbRc=$rc)"
            if ($out) { $detail += ' | ' + (($out | Select-Object -First 2) -join ' / ') }
        }
        Write-Case -Name ("{0}  (AdbRc={1})" -f $case.Label, $rc) -Ok $ok -Detail $detail
    } finally {
        Remove-Item -LiteralPath (Split-Path -Parent $fake) -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Write-Host ''
if ($script:Fail -eq 0) {
    Write-Host '结论：全部通过 —— $script:AdbRc 如实反映子进程退出码。' -ForegroundColor Green
    exit 0
} else {
    Write-Host ("结论：{0} 项失败 —— 退出码契约被破坏（这会让 install 恒走错误分支）。" -f $script:Fail) -ForegroundColor Red
    exit 1
}