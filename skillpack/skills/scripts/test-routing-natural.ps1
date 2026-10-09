#Requires -Version 5.1
# 自然说法路由回归测试器：跑 routing-benchmark-natural.json 全部用例，比对 PRIMARY 期望。
# 用法：
#   powershell -NoProfile -ExecutionPolicy Bypass -File skills/scripts/test-routing-natural.ps1
#   powershell -File skills/scripts/test-routing-natural.ps1 -Benchmark <path> -LogDir <dir>
# 退出码：0 全绿 / 1 有用例失败（failures 详情写入 LogDir）
param(
    [string] $Benchmark = '',
    [string] $LogDir = '',
    [string] $PackageRoot = ''
)
# ★ PSModulePath 自愈（2026-10-10 注入，路径由 inject-psmp.py 统一计算）：剔除 WindowsApps 版 PowerShell 7 的模块目录，否则 PS 5.1 会因 TypeData 重复定义失败而使 Get-FileHash / Get-ExecutionPolicy 不可用（已造成两次假绿 + 一次失败被吞）。重算/迁移后请重跑 work/envinit/inject-psmp.py
. 'C:\relab2\skillpack\skills\scripts\lib\PsModulePathInit.ps1'

$ErrorActionPreference = 'Stop'

$scriptDir = $PSScriptRoot
. (Join-Path $scriptDir 'lib/RouteScope.ps1')
if (-not $scriptDir) { $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path }
$skillsRoot = Split-Path -Parent $scriptDir
if (-not $PackageRoot) { $PackageRoot = Split-Path -Parent $skillsRoot }

. (Join-Path (Join-Path $scriptDir 'lib') 'HostRuntime.ps1')
$HostExe = Resolve-ReverseHostExe

if ([string]::IsNullOrWhiteSpace($Benchmark)) {
    $Benchmark = Join-Path $skillsRoot 'tests/routing-benchmark-natural.json'
}
if (-not (Test-Path -LiteralPath $Benchmark)) {
    Write-Host ("ERROR: benchmark not found: {0}" -f $Benchmark) -ForegroundColor Red
    exit 2
}
$bm = Get-Content -LiteralPath $Benchmark -Raw -Encoding UTF8 | ConvertFrom-Json

# $env:TEMP 在 Linux/macOS runner 上可能未设置，统一用 GetTempPath fallback
$tmpBase = if ($env:TEMP) { $env:TEMP } else { [System.IO.Path]::GetTempPath() }

if ([string]::IsNullOrWhiteSpace($LogDir)) {
    $LogDir = Join-Path $tmpBase ("rs-routing-natural-{0}" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
}
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$masterRoute = Join-Path $scriptDir 'master-route.ps1'
$cases = @($bm.cases)

$fail = New-Object System.Collections.Generic.List[string]
$pass = 0
$failCount = 0
$detail = New-Object System.Collections.Generic.List[string]

Write-Host ("=== test-routing-natural | {0} cases ===" -f $cases.Count)

foreach ($c in $cases) {
    # 兼容 primary / expect 两种字段名
    $exp = $c.primary
    if ([string]::IsNullOrWhiteSpace($exp)) { $exp = $c.expect }
    $tmp = Join-Path $tmpBase ("rs-rtn-{0}" -f [guid]::NewGuid().ToString('n'))
    $got = 'ERR'
    try {
        $null = & $HostExe -NoProfile -ExecutionPolicy Bypass -File $masterRoute -Hint $c.hint -OutDir $tmp 2>&1
        $scope = Join-Path $tmp 'route-scope.md'
        if (Test-Path -LiteralPath $scope) {
            $text = Get-Content -LiteralPath $scope -Raw -Encoding UTF8
            $parsed = Get-ReverseRouteScopeFields -Text $text
            if ($parsed.Id) { $got = $parsed.Id }
        }
    } catch {
        $got = 'EXC:' + $_.Exception.Message
    } finally {
        Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
    }

    if ($got -eq $exp) {
        $pass++
        [void]$detail.Add(("PASS {0} -> {1}" -f $exp, $c.hint))
    } else {
        $failCount++
        $msg = ("FAIL hint='{0}' expect={1} got={2}" -f $c.hint, $exp, $got)
        Write-Host ("[FAIL] {0}" -f $msg) -ForegroundColor Red
        [void]$fail.Add($msg)
        [void]$detail.Add($msg)
    }
}

$detail -join [Environment]::NewLine | Set-Content -LiteralPath (Join-Path $LogDir 'cases.txt') -Encoding UTF8

$summary = @(
    "TOTAL=$($cases.Count)",
    "PASS=$pass",
    "FAIL=$failCount",
    "LogDir=$LogDir"
)
$summary -join [Environment]::NewLine | Set-Content -LiteralPath (Join-Path $LogDir 'SUMMARY.txt') -Encoding UTF8
Write-Host ('=== NATURAL ROUTING TEST SUMMARY ===')
$summary | ForEach-Object { Write-Host $_ }
if ($failCount -gt 0) {
    $fail | Set-Content -LiteralPath (Join-Path $LogDir 'failures.txt') -Encoding UTF8
    Write-Host "OVERALL: FAIL ($failCount)" -ForegroundColor Red
    exit 1
}
Write-Host "OVERALL: ALL PASS ($pass)" -ForegroundColor Green
exit 0
