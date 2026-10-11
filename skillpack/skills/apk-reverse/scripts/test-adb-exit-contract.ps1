#Requires -Version 5.1
<#
  apk-debug.ps1 的 Adb 退出码契约测试。

  测什么：`if ($script:AdbRc -ne 0)` 这个判据，在子进程退出码 0 / 非 0 时
  是否如实分支。

  为什么不用真机：真机不在时 install 会死在 Get-Device（没设备可枚举），
  根本走不到判据那一行。而判据本身是纯逻辑，用一个退出码可控的假 adb
  就能覆盖成功/失败两条路。

  为什么不用外部脚本去 AST 提取 Adb 函数再执行（2026-10-11 走过三条弯路）：
  1. Invoke-Expression       -> 撞 verify-repository-security 的
                                 dynamic-powershell-eval 规则（有意规则，不申请白名单）
  2. [scriptblock]::Create +
     Set-Item function:global: -> $script:AdbRc 写进 global 作用域，探针读自己的
                                 $script: 永远是空
  3. 同上但 function:script:  -> ScriptBlock 内的 $script: 指向它自己的 script 作用域
  作用域语义绕不过去。最终解法：让 apk-debug.ps1 自己跑自己的 Adb
  （selftest-adb 动作），零作用域问题，测的仍然是真代码路径。

  ★ $LASTEXITCODE 是**会话级**变量，同一个 PowerShell 进程里连跑多个 case
    会串位（实测「case 1 读到 0、case 3 读到 1、case 255 读到 3」）。
    所以每个 case 起一个全新进程。
#>
[CmdletBinding()]
param()

$ApkDebug = Join-Path $PSScriptRoot 'apk-debug.ps1'

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

function New-FakeAdb {
    param([int] $ExitCode)
    $dir = Join-Path $env:TEMP ('fakeadb-' + [guid]::NewGuid().ToString('n').Substring(0, 8))
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
    $bat = Join-Path $dir 'fakeadb.cmd'
    $body = "@echo off`r`n" +
            "echo Installing...`r`n" +
            "echo Success`r`n" +
            "exit /b $ExitCode`r`n"
    # 明确按 ASCII 字节写：PowerShell 的 Out-File 默认会按 UTF-16LE 存 .cmd，
    # cmd.exe 读到的是一堆 NUL，脚本会报「'Success' 不是内部或外部命令」。
    [System.IO.File]::WriteAllText($bat, $body, [System.Text.Encoding]::ASCII)
    return $bat
}

Write-Host ''
Write-Host '=== apk-debug.ps1 · Adb 退出码契约 ===' -ForegroundColor Cyan
Write-Host '  走 apk-debug.ps1 自带的 selftest-adb 动作，测的是脚本真代码' -ForegroundColor DarkGray

foreach ($case in @(
        @{ Code = 0; Expect = 0; Label = '退出码 0   -> 成功分支' },
        @{ Code = 1; Expect = 1; Label = '退出码 1   -> 失败分支' },
        @{ Code = 3; Expect = 3; Label = '退出码 3   -> 失败分支（不被当成成功）' },
        @{ Code = 255; Expect = 255; Label = '退出码 255 -> 失败分支' }
    )) {

    $fake = New-FakeAdb -ExitCode $case.Code
    try {
        $env:APKDEBUG_SELFTEST_ADB = $fake
        $out = & powershell -NoProfile -ExecutionPolicy Bypass -File $ApkDebug selftest-adb 2>&1
        $line = @($out | Where-Object { $_ -match 'ADBCONTRACT=' })[-1]
        $got = $null
        if ($line) { $got = [int](($line -split 'ADBCONTRACT=')[-1]).Trim() }
        $expectBranch = if ($case.Code -eq 0) { '成功' } else { '失败' }
        $gotBranch = if ($got -eq 0) { '成功' } else { '失败' }
        $ok = ($got -eq $case.Code) -and ($gotBranch -eq $expectBranch)

        $detail = ''
        if (-not $ok) {
            $detail = "期望 AdbRc=$($case.Code)（$expectBranch 分支），实得 $got（$gotBranch 分支）"
        }
        Write-Case -Name ("{0}  (AdbRc={1})" -f $case.Label, $got) -Ok $ok -Detail $detail
    } finally {
        Remove-Item Env:\APKDEBUG_SELFTEST_ADB -ErrorAction SilentlyContinue
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