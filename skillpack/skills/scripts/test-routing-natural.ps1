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
