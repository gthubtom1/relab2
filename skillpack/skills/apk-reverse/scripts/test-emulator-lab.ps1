#Requires -Version 5.1
<#
.SYNOPSIS
  emulator-lab.ps1 的契约测试 —— 含真会失败的反例控制组。

.DESCRIPTION
  这道门禁**不需要任何模拟器**（本包刻意不预装）。它测的是「零安装状态下能力层
  是否自洽」，而不是「模拟器能不能跑起来」：

  1. 端口表契约：同一家内部端口不重复、落在已知量级、厂商档案齐全。
  2. 厂商名解析：大小写/别名/中文都要能落到同一个 profile。
  3. 原生调用契约：退出码与输出必须如实传出（注入假 exe 覆盖 0/1/3/255）。
  4. 按键表与 frida 布局常量不被改坏。
  5. **反例控制组**：把脚本副本改成坏的，确认 selftest 的判据真的会红。
     只跑正例的话，「判据永远返回 PASS」和「判据真在检查」长得一模一样
     （见经验卡 gate-self-must-prove-failure）。

  为什么不用外部脚本 AST 提取函数执行：$script: 绑定在定义它的脚本块上，
  外部永远读到空 —— 见经验卡 powershell-script-scope-does-not-follow-callstack。

  退出码：0 全过 / 1 有失败。
#>
[CmdletBinding()]
param()

$Emulab = Join-Path $PSScriptRoot 'emulator-lab.ps1'

$ErrorActionPreference = 'Stop'
$script:Fail = 0

function Write-Case {
    param([string] $Name, [bool] $Ok, [string] $Detail = '')
    if ($Ok) {
        Write-Host ('  [PASS] {0}' -f $Name)
    } else {
        Write-Host ('  [FAIL] {0}  {1}' -f $Name, $Detail) -ForegroundColor Red
        $script:Fail++
    }
}

function New-FakeExe {
    param([int] $ExitCode)
    $dir = Join-Path $env:TEMP ('fakeemu-' + [guid]::NewGuid().ToString('n').Substring(0, 8))
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
    $bat = Join-Path $dir 'fakeemu.cmd'
    $body = "@echo off`r`n" +
            "echo FAKE-STDOUT`r`n" +
            "echo FAKE-STDERR-DIAG 1>&2`r`n" +
            "exit /b $ExitCode`r`n"
    # 明确按 ASCII 字节写：PowerShell 的 Out-File 默认按 UTF-16LE 存 .cmd，
    # cmd.exe 读到一堆 NUL，脚本会报「'FAKE-STDOUT' 不是内部或外部命令」。
    [System.IO.File]::WriteAllText($bat, $body, [System.Text.Encoding]::ASCII)
    return $bat
}

function Invoke-Selftest {
    param([string] $Sub, [string] $FakeExe = '')
    $prev = $env:EMULAB_FAKE_EXE
    try {
        if ($FakeExe) { $env:EMULAB_FAKE_EXE = $FakeExe } else { Remove-Item Env:\EMULAB_FAKE_EXE -ErrorAction SilentlyContinue }
        $out = & powershell -NoProfile -ExecutionPolicy Bypass -File $Emulab selftest $Sub 2>&1
        return ($out | ForEach-Object { [string]$_ })
    } finally {
        if ($FakeExe) { $env:EMULAB_FAKE_EXE = $prev }
        else { Remove-Item Env:\EMULAB_FAKE_EXE -ErrorAction SilentlyContinue }
    }
}

Write-Host ''
Write-Host '=== emulator-lab.ps1 · 契约测试 ===' -ForegroundColor Cyan
Write-Host '  不需要任何模拟器：测的是零安装状态下能力层是否自洽' -ForegroundColor DarkGray

if (-not (Test-Path -LiteralPath $Emulab)) {
    Write-Host "  [FAIL] 找不到 $Emulab" -ForegroundColor Red
    exit 1
}

# ── 1. 端口表契约 ─────────────────────────────────────────────────
$lines = @(Invoke-Selftest -Sub 'ports')
$kv = @{}
foreach ($l in $lines) {
    if ($l -match '^([A-Z]+)=(.*)$') { $kv[$Matches[1]] = $Matches[2] }
}
Write-Case -Name 'selftest ports 回了 VENDORS' -Ok ($kv.ContainsKey('VENDORS')) `
    -Detail ("实得: " + ($lines -join ' | '))
Write-Case -Name '端口表内无重复' -Ok ($kv['DUPPORTS'] -eq '') `
    -Detail ("重复项: " + $kv['DUPPORTS'])
$vendors = 0
if ($kv['VENDORS'] -match '^\d+$') { $vendors = [int]$kv['VENDORS'] }
Write-Case -Name '厂商档案 >= 5 家（MuMu/雷电/夜神/MEmu/蓝叠/AVD）' `
    -Ok ($vendors -ge 5) -Detail "实得 $vendors"
$portCount = 0
if ($kv['PORTCOUNT'] -match '^\d+$') { $portCount = [int]$kv['PORTCOUNT'] }
Write-Case -Name '候选端口总数 >= 10' -Ok ($portCount -ge 10) -Detail "实得 $portCount"

# ── 2. 厂商名解析 ─────────────────────────────────────────────────
$lookup = @(Invoke-Selftest -Sub 'vendor-lookup')
$expected = @(
    # PowerShell 哈希表键**默认不区分大小写**（mumu 与 MuMu 会合并成一个键），
    # 所以大小写变体改成独立的数组用例来测。
    @('mumu', 'mumu'), @('ldplayer', 'ldplayer'), @('nox', 'nox')
    @('夜神', 'nox'), @('memu', 'memu'), @('MEmu', 'memu')
    @('bluestacks', 'bluestacks'), @('bs', 'bluestacks'), @('avd', 'avd')
)
$got = @{}
foreach ($l in $lookup) {
    if ($l -match '^LOOKUP\[(.+?)\]=(.+)$') { $got[$Matches[1]] = $Matches[2] }
}
foreach ($case in $expected) {
    $k = $case[0]
    $want = $case[1]
    Write-Case -Name ("厂商名解析 {0,-12} -> {1}" -f $k, $want) `
        -Ok ($got[$k] -eq $want) -Detail ("实得 " + $got[$k])
}
Write-Case -Name '认不出的厂商返回 NONE（不瞎猜）' -Ok ($got['nope'] -eq 'NONE') `
    -Detail ("实得 " + $got['nope'])

# ── 3. 原生调用契约（注入假 exe）────────────────────────────────
foreach ($code in @(0, 1, 3, 255)) {
    $fake = New-FakeExe -ExitCode $code
    try {
        $n = @(Invoke-Selftest -Sub 'native' -FakeExe $fake)
        $rc = $null
        $outLine = ''
        foreach ($l in $n) {
            if ($l -match '^RC=(\d+)') { $rc = [int]$Matches[1] }
            if ($l -match '^OUT=(.*)$') { $outLine = $Matches[1] }
        }
        Write-Case -Name ("原生退出码 {0,-3} 如实传出" -f $code) -Ok ($rc -eq $code) `
            -Detail ("实得 " + $rc)
        # 正例 oracle：stdout 文本必须被收到（这一条守住「stderr 诊断导致脚本死掉」
        # 与「输出被吞」两类回归）
        Write-Case -Name ("退出码 {0,-3} 时 stdout 文本仍可读" -f $code) `
            -Ok ($outLine -match 'FAKE-STDOUT') -Detail ("实得: '" + $outLine + "'")
    } finally {
        Remove-Item -LiteralPath (Split-Path -Parent $fake) -Recurse -Force -ErrorAction SilentlyContinue
    }
}

# ── 4. 常量表不被改坏 ─────────────────────────────────────────────
$kl = @(Invoke-Selftest -Sub 'keymap')
$keys = ''
# $HOME 是 PowerShell 的**只读**变量（用户主目录），拿它当局部变量会直接抛
# UnauthorizedAccessException —— 门禁自己因此崩过一次，所以这里改名。
$keyHomeCode = ''
foreach ($l in $kl) {
    if ($l -match '^KEYS=(.*)$') { $keys = $Matches[1] }
    if ($l -match '^HOME=(.*)$') { $keyHomeCode = $Matches[1] }
}
foreach ($k in @('home', 'back', 'app', 'enter')) {
    Write-Case -Name ("按键表含 {0}" -f $k) -Ok ($keys -match ('(^|,)(' + $k + ')(,|$)')) `
        -Detail ("实得: " + $keys)
}
Write-Case -Name 'home 映射到 KEYCODE_HOME' -Ok ($keyHomeCode -eq 'KEYCODE_HOME') `
    -Detail ("实得 " + $keyHomeCode)


$fl = @(Invoke-Selftest -Sub 'frida-layout')
$remote = ''
$port = ''
foreach ($l in $fl) {
    if ($l -match '^REMOTE=(.*)$') { $remote = $Matches[1] }
    if ($l -match '^PORT=(\d+)$') { $port = $Matches[1] }
}
Write-Case -Name 'frida-server 落在 /data/local/tmp（app 不可读目录）' `
    -Ok ($remote -eq '/data/local/tmp/frida-server') -Detail ("实得 " + $remote)
Write-Case -Name 'frida 默认端口 27042' -Ok ($port -eq '27042') -Detail ("实得 " + $port)
# ── 5. MuMuManager JSON 解析（唯一能自报端口的厂商 CLI）─────────────
# 真 MuMu 不可能在 CI 里装，所以这条发现路径只能靠 fixture 覆盖。
# fixture 复刻官方 `info -v all` 的 JSON 字段表（见 mumu.163.com 官方文档）。
Write-Host ''
Write-Host '=== MuMuManager JSON 解析（厂商 CLI 自报端口路径） ===' -ForegroundColor Cyan
$mumuFixture = Join-Path (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)) `
                             'scripts\experience-cards\fixtures\fake-mumu-manager.cmd'
Write-Case -Name 'MuMu fixture 存在' -Ok (Test-Path -LiteralPath $mumuFixture) `
    -Detail "找不到 $mumuFixture（厂商 CLI 路径就永远测不到）"

function Invoke-MumuSelftest {
    param([string] $Mode)
    $prev = $env:MUMU_FIXTURE
    try {
        $env:MUMU_FIXTURE = $Mode
        $out = & powershell -NoProfile -ExecutionPolicy Bypass -File $Emulab selftest mumu-json 2>&1
        $kv = @{}
        foreach ($l in $out) {
            $t = [string]$l
            if ($t -match '^([A-Z_]+)=(.*)$') { $kv[$Matches[1]] = $Matches[2] }
        }
        return $kv
    } finally {
        if ($null -ne $prev) { $env:MUMU_FIXTURE = $prev }
        else { Remove-Item Env:\MUMU_FIXTURE -ErrorAction SilentlyContinue }
    }
}

$m = Invoke-MumuSelftest -Mode 'single'
Write-Case -Name 'JSON 解析出 2 个实例' -Ok ($m['MU_INSTANCES'] -eq '2') `
    -Detail ("实得 " + $m['MU_INSTANCES'])
Write-Case -Name '解析出两个 adb 端点（含未启动实例的）' `
    -Ok ($m['MU_SERIALS'] -eq '127.0.0.1:16384,127.0.0.1:16416') `
    -Detail ("实得 '" + $m['MU_SERIALS'] + "'")
Write-Case -Name '已启动实例数 = 1（is_android_started 被读到）' `
    -Ok ($m['MU_BOOTED'] -eq '1') -Detail ("实得 " + $m['MU_BOOTED'])

$me = Invoke-MumuSelftest -Mode 'empty'
Write-Case -Name '空数组 -> 0 实例，不崩' -Ok ($me['MU_INSTANCES'] -eq '0') `
    -Detail ("实得 " + $me['MU_INSTANCES'])

$mb = Invoke-MumuSelftest -Mode 'bare'
Write-Case -Name '老版本只打标题（无 JSON）-> 0 实例，不崩' `
    -Ok ($mb['MU_INSTANCES'] -eq '0') -Detail ("实得 " + $mb['MU_INSTANCES'])

# 反例：把 fixture 换成只输出一半的 JSON，解析必须**拿不到**实例而不是硬凑一个
$brokenDir = Join-Path (Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))) `
                       'scripts\work'
# ★ 2026-10-15 换机实测修：scripts\work\ 是 gitignore 的机器状态目录，干净 clone 里**不存在**——
#   原来直接 WriteAllText 会炸在 "Could not find a part of the path"（阶段 5 干净目录实测抓到的真缺陷）。
if (-not (Test-Path -LiteralPath $brokenDir)) {
    New-Item -ItemType Directory -Path $brokenDir -Force | Out-Null
}
$brokenMumu = Join-Path $brokenDir 'fake-mumu-broken.cmd'
try {
    [System.IO.File]::WriteAllText($brokenMumu,
        "@echo off`r`necho [`r`necho   { `"index`": `"0`", `"adb_port`": 16384 }`r`n",
        [System.Text.Encoding]::ASCII)
    $prevMu = $env:EMULAB_MUMU_FIXTURE
    try {
        $env:EMULAB_MUMU_FIXTURE = $brokenMumu
        $outMu = & powershell -NoProfile -ExecutionPolicy Bypass -File $Emulab selftest mumu-json 2>&1
        $mbk = @{}
        foreach ($l in $outMu) {
            $t = [string]$l
            if ($t -match '^([A-Z_]+)=(.*)$') { $mbk[$Matches[1]] = $Matches[2] }
        }
        Write-Case -Name '反例：残缺 JSON -> 0 实例（不硬凑、不崩）' `
            -Ok ($mbk['MU_INSTANCES'] -eq '0') `
            -Detail ("实得 " + $mbk['MU_INSTANCES'] + "（非 0 说明会把坏数据当好数据）")
    } finally {
        if ($null -ne $prevMu) { $env:EMULAB_MUMU_FIXTURE = $prevMu }
        else { Remove-Item Env:\EMULAB_MUMU_FIXTURE -ErrorAction SilentlyContinue }
    }
} finally {
    Remove-Item -LiteralPath $brokenMumu -Force -ErrorAction SilentlyContinue
}

# ── 5. 反例控制组：判据自己必须会红 ──────────────────────────────
# 把脚本副本改成坏的，再跑同一条 selftest，确认输出真的变了。
# 这是本门禁成立的前提：不这么做，上面的 PASS 只说明「脚本没崩」。
#
# 副本必须放在**仓内**（/work/ 已被 .gitignore 忽略），不能放 %TEMP%：
#   探测层靠从脚本位置逐级上溯找 Bootstrap.ps1。放到仓外时
#   `..\..\scripts\lib\Bootstrap.ps1` 会解析成 `C:\..\..\...` —— 引用了
#   基路径 C: 之外的项，脚本 exit 2，反例控制组变成同义反复（2026-10-11 实测）。
$negDir = Join-Path (Join-Path (Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))) 'scripts') 'work'
$negDir = Join-Path $negDir ('emulab-neg-' + [guid]::NewGuid().ToString('n').Substring(0, 8))
New-Item -ItemType Directory -Path $negDir -Force | Out-Null
$copy = Join-Path $negDir 'emulator-lab.ps1'
$text = Get-Content -LiteralPath $Emulab -Raw -Encoding UTF8
try {
    # 反例 A：把厂商档案换成两个端口重叠的假档案
    $brokenA = $text -replace "(?m)^\`$script:VendorProfiles = @\(", @"
`$script:VendorProfiles = @(
    [pscustomobject]@{ Id = 'x'; Label = 'x'; Key = 'x'; Ports = @(1, 1); ExecName = 'x.exe'; ExecGlobs = @(); Cli = 'x'; Fdaemon = @('x.exe') },
    [pscustomobject]@{ Id = 'y'; Label = 'y'; Key = 'y'; Ports = @(1); ExecName = 'y.exe'; ExecGlobs = @(); Cli = 'y'; Fdaemon = @('y.exe') }
"@
    [System.IO.File]::WriteAllText($copy, $brokenA, [System.Text.UTF8Encoding]::new($true))
    $outA = (& powershell -NoProfile -ExecutionPolicy Bypass -File $copy selftest ports 2>&1 |
              ForEach-Object { [string]$_ })
    $aKv = @{}
    foreach ($l in $outA) { if ($l -match '^([A-Z]+)=(.*)$') { $aKv[$Matches[1]] = $Matches[2] } }
    Write-Case -Name '反例：档案被改坏 -> 厂商数变化' `
        -Ok ($aKv['VENDORS'] -ne "$vendors") `
        -Detail ("改坏后 VENDORS=" + $aKv['VENDORS'] + "，原值 $vendors")
    Write-Case -Name '反例：端口重复 -> DUPPORTS 非空（判据真的会红）' `
        -Ok ($aKv['DUPPORTS'] -ne '') `
        -Detail ("改坏后 DUPPORTS='" + $aKv['DUPPORTS'] + "'（为空说明判据坏了）")
} finally {
    Remove-Item -LiteralPath $negDir -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host ''
if ($script:Fail -eq 0) {
    Write-Host '结论：全部通过 —— 端口表/厂商解析/原生退出码/常量表自洽，且反例证明判据会红。' -ForegroundColor Green
    exit 0
} else {
    Write-Host ("结论：{0} 项失败。" -f $script:Fail) -ForegroundColor Red
    exit 1
}