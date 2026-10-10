#Requires -Version 5.1
<#
.SYNOPSIS
  APK 调试一条龙 —— 全命令行，不依赖模拟器、不需要 WHPX、不碰系统设置。
.DESCRIPTION
  本脚本面向「智能体自动控制」设计：**所有输出都是文本**，不需要 agent 去
  看任何图形界面。

  流程：
    1. 静态拆包    jadx 反编译 / apktool 解包 smali / aapt2 拿权限清单
    2. 装到设备    adb install（自动处理多设备：按 -Serial 或唯一设备）
    3. 动态观察    logcat 实时日志 / dumpsys 状态 / 截图
    4. 动态插桩    frida 挂进程读参数

  为什么不用模拟器：
    · 真机零内存占用、秒开、抗 APP 检测
    · 开 WHPX 会削弱 WinDbg 内核调试能力 —— 直接踩「PC 软件调试 + 游戏辅助测试」
    · 本脚本因此不需要 WHPX，也不需要任何第三方模拟器（雷电/MuMu 常驻 1.5-3GB）

.EXAMPLE
  .\apk-debug.ps1 inspect app.apk
  .\apk-debug.ps1 install app.apk
  .\apk-debug.ps1 run  com.example.app
  .\apk-debug.ps1 log   com.example.app
  .\apk-debug.ps1 shot  out.png
  .\apk-debug.ps1 frida com.example.app -s agent/frida/dump.js
#>
[CmdletBinding()]
param(
  [Parameter(Position = 0)]
  [ValidateSet('devices', 'inspect', 'install', 'uninstall', 'run', 'stop',
               'log', 'clear', 'shot', 'screen', 'frida', 'info', 'doctor')]
  [string] $Action = 'devices',

  [Parameter(Position = 1)]
  [string] $Target,

  # APK 文件路径（inspect / install 用）
  [string] $Apk,

  # 输出目录（inspect 用）
  [string] $Out,

  # 设备序列号（多设备时必填）
  [string] $Serial,

  # frida 脚本
  [string] $Script,

  # 事件/过滤器（log 用），如 "frida:V *:E"
  [string] $Filter,

  # 抓多少行就停（log 用）；0 = 持续输出
  [int] $Lines = 0,

  # inspect 用：jadx 反编译超时（秒）。大包要给够，
  # 默认 30 分钟 —— 宁可慢也别让它无声卡死。
  [int] $JadxTimeoutSec = 1800,

  # inspect 用：apktool 解包超时（秒）。官方 3.0.3 多线程实测 84 MB 包只要 12 秒，
  # 2400s 是留给极端样本的天花板。
  [int] $ApktoolTimeoutSec = 2400
)

$ErrorActionPreference = 'Stop'

# ── PSModulePath 自愈：与仓内其它入口脚本同一套写法（2026-10-10）──────
$__psmpDir = $PSScriptRoot
if (-not $__psmpDir) { $__psmpDir = Split-Path -Parent $MyInvocation.MyCommand.Path }
while ($__psmpDir) {
    $__psmpInit = Join-Path $__psmpDir 'skillpack\skills\scripts\lib\PsModulePathInit.ps1'
    if (Test-Path -LiteralPath $__psmpInit -ErrorAction SilentlyContinue) { . $__psmpInit; break }
    $__psmpParent = Split-Path -Parent $__psmpDir
    if (-not $__psmpParent -or $__psmpParent -eq $__psmpDir) { break }
    $__psmpDir = $__psmpParent
}

# ── 探测层：工具定位的唯一入口 ─────────────────────────────────────────
function Import-Probe {
    param([string]$StartDir)
    # 只负责找路径，**不在函数里 dot-source**。
    #
    # ★ 2026-10-11 修正：原来在函数体内写 `. $p; return $true`。
    #   PowerShell 函数有自己的作用域，dot-source 出来的
    #   Resolve-ReverseToolSpec 只活到函数返回 —— 调用方拿到 True
    #   却用不了那个函数（实测：Import-Probe -> True 但 HasFn=False）。
    $d = $StartDir
    while ($d) {
        foreach ($rel in @('skillpack\skills\scripts\lib\Bootstrap.ps1',
                           '..\..\scripts\lib\Bootstrap.ps1')) {
            $p = Join-Path $d $rel
            if (Test-Path -LiteralPath $p -ErrorAction SilentlyContinue) {
                return (Resolve-Path -LiteralPath $p).Path
            }
        }
        $parent = Split-Path -Parent $d -ErrorAction SilentlyContinue
        if (-not $parent -or $parent -eq $d) { break }
        $d = $parent
    }
    return $null
}

$__probePath = Import-Probe -StartDir $PSScriptRoot
if (-not $__probePath) {
    Write-Error @"
探测层找不到（从 $PSScriptRoot 逐级上溯没找到
skillpack\skills\scripts\lib\Bootstrap.ps1）。

这个脚本必须放在**仓库内**（<仓根>\skillpack\skills\<技能名>\scripts\ 下），
否则它不知道去哪里找工具解析层。
"@
    exit 2
}
# ★ 必须在调用方作用域 dot-source，不能放进函数里（理由见 Import-Probe 注释）
. $__probePath

# ★ 2026-11：开跑前先清掉抢 5037 端口的 adb daemon。
#
#   本机有 **6 个 adb.exe**（AndroidKiller / 搞机工具箱 / 两份 platform-tools /
#   scrcpy 自带），其中两个是旧的 1.0.32。adb daemon 全都监听 5037，
#   版本不同就互相踢 —— 表现为设备在 `adb devices` 里**时有时无**，
#   看着像驱动没装好（我 2026-10-11 误判过一次）。
#
#   解法不是删第三方助手里的 adb（删了会破坏它们），而是：
#     1) 先 kill-server，把所有 daemon 停掉
#     2) 只用本脚本解析到的那一个重新起
#   之后 5037 上只有一个 daemon，冲突不复存在。
$__adbSpec = Resolve-ReverseToolSpec -Name 'adb' -ErrorAction SilentlyContinue
if ($__adbSpec -and $__adbSpec.Available -and $__adbSpec.Command) {
    # daemon 本来没跑时 kill-server 会往 stderr 打 `cannot connect to daemon`，
    # 那是**正常情况**不是故障。局部放宽 ErrorAction + 只重定向 stderr 即可，
    # 不要用 `2>&1`（会把正常 stderr 并进管道，PowerShell 报 NativeCommandError 红字）。
    $ErrorActionPreference='Continue'
    $null = & $__adbSpec.Command 'kill-server' 2>$null
    $ErrorActionPreference='Stop'
    # kill 之后 daemon 要重启 + 跟设备重新握手，这一步**要时间**。
    # 实测只 sleep 800ms 就去查设备 -> 查不到 -> 误报「无设备」。
    # （真机其实是好的，直接 adb devices 一查就有。）
    Start-Sleep -Seconds 3
    $ErrorActionPreference='Continue'
    $null = & $__adbSpec.Command 'start-server' 2>$null
    $ErrorActionPreference='Stop'
    Start-Sleep -Seconds 2
    # 等到设备真正出现为止，最多 15 秒
    for ($__i = 0; $__i -lt 5; $__i++) {
        $__probe = & $__adbSpec.Command devices 2>$null
        if ($__probe -match '^\S+\s+device') { break }
        Start-Sleep -Seconds 3
    }
}

function Invoke-Probe {
    # ★ 2026-10-11：取版本串的失败姿势与正解。
    #
    #   aapt2 把**正常的版本输出写 stderr**。三种失败姿势实测：
    #     · `& $exe version`          -> NativeCommandError 红字，成功的自检被报成失败
    #     · `2>$null`                 -> 拦不住（那是原生 exe 自己的错误流）
    #     · `cmd /c ... 2^>nul`      -> 拦不住，且引入 cmd.exe 转义这一层脆弱依赖
    #   正解：`Start-Process` + stdout/stderr **两个不同文件**重定向，
    #   PowerShell 只读文件。两个流写同一个文件会被 Start-Process 直接拒
    #   （"RedirectStandardOutput 和 RedirectStandardError 相同"）。
    #   实测 aapt2：exit=0，stdout 空、stderr 是 51 字节版本串。
    param([string]$Exe, [string[]]$ProbeArgs, [switch]$Last)

    $outFile = [IO.Path]::GetTempFileName()
    $errFile = [IO.Path]::GetTempFileName()
    try {
        $startArgs = @{ }
        if ($ProbeArgs) { $startArgs['ArgumentList'] = $ProbeArgs }
        $null = Start-Process -FilePath $Exe @startArgs `
                              -RedirectStandardOutput $outFile `
                              -RedirectStandardError $errFile `
                              -WindowStyle Hidden -PassThru -Wait
        # 原生工具的版本串常在 stderr，但两流都收，谁先有内容用谁
        $lines = @()
        foreach ($f in @($outFile, $errFile)) {
            $t = @(Get-Content -LiteralPath $f -Encoding UTF8 -ErrorAction SilentlyContinue |
                   Where-Object { $_.Trim() })
            if ($t.Count) { $lines = $t; break }
        }
        if ($lines.Count -eq 0) { return '' }
        $pick = if ($Last) { $lines[-1] } else { $lines[0] }
        return $pick.Trim()
    } catch {
        return ''
    } finally {
        Remove-Item -LiteralPath $outFile, $errFile -Force -ErrorAction SilentlyContinue
    }
}

function Say  { param([string]$m) Write-Host $m }
function Step  { param([string]$m) Write-Host "`n=== $m ===" -ForegroundColor Cyan }
function Ok    { param([string]$m) Write-Host "  [OK] $m" }
function Warn2 { param([string]$m) Write-Host "  [!!] $m" -ForegroundColor Yellow }
function Die   { param([string]$m) Write-Host "  [XX] $m" -ForegroundColor Red; exit 1 }

function Tool {
    param([string]$Name)
    $spec = Resolve-ReverseToolSpec -Name $Name
    if ($spec.Available) { return $spec.Command }
    return $null
}

function Require-Tool {
    param([string]$Name, [string]$Hint)
    $c = Tool $Name
    if (-not $c) { Die "缺工具 '$Name'。$Hint" }
    return $c
}

# ── 设备选择：多设备时必须显式，不猜 ───────────────────────────────────
function Get-Device {
    $adb = Require-Tool 'adb' '装法见 skillpack/skills/TOOLS.md（platform-tools）。'
    # ★ 2026-11：`2>&1` 会把 adb 的正常 stderr（`* daemon not running;
    #   starting now`）也当成错误对象，PowerShell 打红字，还可能让
    #   Select-String 匹配不到设备行。走文件取纯 stdout。
    $ErrorActionPreference = 'Continue'
    $raw = & $adb devices 2>$null
    $ErrorActionPreference = 'Stop'
    $list = @($raw | Select-String -Pattern '^(\S+)\s+device$' |
              ForEach-Object { $_.Matches[0].Groups[1].Value })
    if ($Serial) {
        if ($list -notcontains $Serial) {
            Die "指定的设备 '$Serial' 不在 adb devices 里。当前：$($list -join ', ')"
        }
        return $Serial
    }
    if ($list.Count -eq 0) {
        Die @"
没有可用设备。检查三件事：
  1. 手机插了 USB 吗？
  2. 手机上「开发者选项 → USB 调试」开了吗？
  3. 手机上弹的「允许 USB 调试」点了允许吗？（选「一直允许」）

当前 adb devices：
$($raw -join [Environment]::NewLine)
"@
    }
    if ($list.Count -gt 1) {
        Die @"
检测到 $($list.Count) 台设备：$($list -join ', ')
多设备时本脚本**不猜**。加 -Serial 指定：
  .\apk-debug.ps1 $Action -Serial <序列号> ...
序列号从上面 'adb devices' 的输出里取。
"@
    }
    return $list[0]
}

function Adb {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Args_)
    $adb = Require-Tool 'adb' ''
    $dev = Get-Device
    & $adb '-s' $dev @Args_ 2>&1
    # ★ 2026-10-11 退出码走独立变量，不混进返回值。
    #   原因：函数返回值里既有 stdout 文本又有退出码时，`$rc = Adb ...`
    #   拿到的是数组，`$rc -ne 0` 恒为真 —— install 会永远走「安装失败」分支。
    #   这里把退出码放进脚本作用域，调用点显式读 $script:AdbRc。
    $script:AdbRc = $LASTEXITCODE
}

# ── 从 APK 猜包名：优先 aapt2，其次读 manifest 文本 ───────────────────
function Get-PackageName {
    param([string]$ApkPath)
    $aapt2 = Tool 'aapt2'
    if ($aapt2) {
        $o = & $aapt2 'dump' 'badging' $ApkPath 2>&1
        $m = $o | Select-String -Pattern "^package:\s+name='([^']+)'" |
             Select-Object -First 1
        if ($m) { return $m.Matches[0].Groups[1].Value }
    }
    # 兜底：从解包出的 AndroidManifest 里找
    $mf = Join-Path (Split-Path -Parent $ApkPath) 'AndroidManifest.xml'
    if (Test-Path $mf) {
        $raw = Get-Content $mf -Raw -Encoding UTF8 -ErrorAction SilentlyContinue
        $m = [regex]::Match($raw, 'package="([^"]+)"')
        if ($m.Success) { return $m.Groups[1].Value }
    }
    return $null
}

switch ($Action) {

    'devices' {
        Step 'adb 设备'
        $adb = Require-Tool 'adb' ''
        & $adb devices -l
        break
    }

    'doctor' {
        Step 'APK 调试链路自检（每项都是实跑，不只是「装没装」）'
        $rows = @(
            @{ Id = 'adb';        Note = '真机通道' },
            @{ Id = 'aapt2';      Note = '包信息/权限' },
            @{ Id = 'apktool';    Note = '解包 smali' },
            @{ Id = 'jadx';       Note = '反编译源码' },
            @{ Id = 'apksigner';  Note = '签名校验' },
            @{ Id = 'frida';      Note = '动态插桩' },
            @{ Id = 'frida-ps';   Note = '进程枚举' },
            @{ Id = 'objection';  Note = 'Frida 增强' },
            @{ Id = 'bundletool'; Note = 'AAB/APKS' },
            @{ Id = 'keytool';    Note = '证书' }
        )
        foreach ($r in $rows) {
            $spec = Resolve-ReverseToolSpec -Name $r.Id
            if (-not $spec.Available) {
                Warn2 ("{0,-12} {1,-14} 缺失" -f $r.Id, $r.Note)
                continue
            }
            $probe = $null
            switch ($r.Id) {
                'aapt2'      { $probe = Invoke-Probe $spec.Command @('version') }
                'apktool'    { $probe = Invoke-Probe $spec.Command @('--version') }
                'jadx'       { $probe = Invoke-Probe $spec.Command @('--version') }
                'frida'      { $probe = Invoke-Probe $spec.Command @('--version') }
                'objection'  { $probe = Invoke-Probe $spec.Command @('version') -Last }
                'bundletool' { $probe = Invoke-Probe $spec.Command @('version') }
                'keytool'    { $probe = Invoke-Probe $spec.Command @('-help') }
                'adb'        { $probe = Invoke-Probe $spec.Command @('version') }
                default       { $probe = '（无 --version 探针）' }
            }
            Ok ("{0,-12} via={1,-8} {2}" -f $r.Id, $spec.Via, ($probe -replace '\s+', ' '))
        }
        Step '设备'
        $ErrorActionPreference = 'Continue'
        $__rawDev = & (Tool 'adb') devices 2>$null
        $ErrorActionPreference = 'Stop'
        $devs = @($__rawDev |
                  Select-String -Pattern '^(\S+)\s+device$' |
                  ForEach-Object { $_.Matches[0].Groups[1].Value })
        if ($devs.Count) { Ok "已连接 $($devs.Count) 台：$($devs -join ', ')" }
        else { Warn2 '无设备（真机没插或 USB 调试没开）——静态链路可用，动态链路不可用' }
        break
    }

    'inspect' {
        if (-not $Apk) { Die '用法：apk-debug.ps1 inspect -Apk <path> [-Out <dir>]' }
        if (-not (Test-Path -LiteralPath $Apk)) { Die "文件不存在: $Apk" }
        if (-not $Out) {
            $Out = Join-Path (Split-Path -Parent (Resolve-Path $Apk)) `
                                 ('unpack_' + [IO.Path]::GetFileNameWithoutExtension($Apk))
        }
        New-Item -ItemType Directory -Path $Out -Force | Out-Null
        $apkSize = [math]::Round((Get-Item -LiteralPath $Apk).Length / 1MB, 1)
        Say ("APK   : {0}  ({1} MB)" -f (Resolve-Path $Apk).Path, $apkSize)
        Say "输出目录: $Out"

        # ★ 2026-10-11 修正步骤顺序与超时。
        #   原来顺序是 aapt2 -> apktool -> jadx，apktool 排在 jadx 前面。
        #   对 84 MB 的包（709 个二进制 XML + 184 张图 + 3 个 dex）实测：
        #     · aapt2  0.1 秒
        #     · jadx   约 60-90 秒（8179 个 .java）
        #     · apktool 取决于**哪个 apktool**：指向 AndroidKiller 里的
        #       ShakaApktool 2.5.0 单线程魔改版时读不动 Android 16 (API 36)
        #       的资源格式，会在 framework 循环里打转 20 分钟以上；
        #       官方 Apktool 3.0.3 多线程只要 12 秒。
        #   卡在 apktool 上，后面真正需要的 jadx 根本跑不到 ——
        #   整个 inspect 因此「看起来像卡死」。
        #
        #   改法：
        #     · jadx 提到最前（逆向主用途，先拿到能读的源码）
        #     · 每步都有独立超时 + 进度提示，不再无声挂死
        #     · apktool 用官方 3.0.3（已登记进 toolmap.default.json）
        $ErrorActionPreference = 'Continue'

        Step '1/4 aapt2 —— 包信息与权限（秒级）'
        $aapt2 = Tool 'aapt2'
        if ($aapt2) {
            $null = & $aapt2 'dump' 'badging' $Apk 2>$null |
                Select-String -Pattern "^(package:|uses-permission:|application-label:|launchable-activity:|sdkVersion:|targetSdkVersion:|native-code:)" |
                ForEach-Object { '  ' + $_.Line.Trim() }
        } else { Warn2 'aapt2 缺失' }

        Step '2/4 签名信息（秒级）'
        $keytool = Tool 'keytool'
        if ($keytool) {
            $null = & $keytool '-printcert' '-jarfile' $Apk 2>$null |
                Select-Object -First 6 | ForEach-Object { '  ' + $_ }
        }

        Step '3/4 jadx —— 反编译源码（大包约 1-3 分钟）'
        $jadx = Tool 'jadx'
        if ($jadx) {
            $srcDir = Join-Path $Out 'jadx'
            Say '  正在反编译源码（日志见 -Out\jadx.log）…'
            $jadxLog = Join-Path $Out 'jadx.log'
            $jadxErr = Join-Path $Out 'jadx.err'
            # --no-res：源码逆向不需要还原资源，大幅提升速度
            $proc = Start-Process -FilePath $jadx `
                                  -ArgumentList @('-d', $srcDir, '--no-res', $Apk) `
                                  -RedirectStandardOutput $jadxLog `
                                  -RedirectStandardError $jadxErr `
                                  -WindowStyle Hidden -PassThru -ErrorAction SilentlyContinue
            $secs = 0
            while ($proc -and -not $proc.HasExited -and $secs -lt $JadxTimeoutSec) {
                Start-Sleep -Seconds 3
                $secs += 3
                $pct = ''
                if (Test-Path -LiteralPath $jadxLog) {
                    $m = Select-String -Path $jadxLog -Pattern 'progress:\s*(\d+) of (\d+)' |
                         Select-Object -Last 1
                    if ($m -and $m.Matches[0].Groups[2].Value -ne '0') {
                        $pct = (' {0}%' -f [math]::Round(
                            100 * [int]$m.Matches[0].Groups[1].Value /
                            [int]$m.Matches[0].Groups[2].Value))
                    }
                }
                Write-Host ("  [{0,4}s]{1}" -f $secs, $pct) -NoNewline
                Write-Host "`r" -NoNewline
            }
            Write-Host ''
            if ($proc -and -not $proc.HasExited) {
                Warn2 ("jadx 超时 {0}s，已保留已解出的部分。" -f $JadxTimeoutSec)
                try { $proc.Kill() } catch { }
            }
            $javaCount = @(Get-ChildItem -LiteralPath $srcDir -Recurse `
                           -Filter '*.java' -ErrorAction SilentlyContinue).Count
            if ($javaCount) {
                Ok ("源码: {0}  （{1} 个 .java）" -f $srcDir, $javaCount)
            } else {
                Die 'jadx 未产出 .java 文件，请查看 jadx.log / jadx.err'
            }
        } else { Warn2 'jadx 缺失' }

        # 4/4 apktool：官方 3.0.3 实测仅需 10 秒解出全量资源与 smali
        Step '4/4 apktool —— 解包 smali + 资源'
        $apktool = Tool 'apktool'
        if ($apktool) {
            $apktoolOut = Join-Path $Out 'apktool'
            $apktoolLog = Join-Path $Out 'apktool.log'
            $apktoolErr = Join-Path $Out 'apktool.err'
            Say '  正在解包 smali 与资源（官方 3.0.3 多线程）…'
            $proc = Start-Process -FilePath $apktool `
                                  -ArgumentList @('d', '-f', '-o', $apktoolOut, $Apk) `
                                  -RedirectStandardOutput $apktoolLog `
                                  -RedirectStandardError $apktoolErr `
                                  -WindowStyle Hidden -PassThru -ErrorAction SilentlyContinue
            $secs = 0
            while ($proc -and -not $proc.HasExited -and $secs -lt $ApktoolTimeoutSec) {
                Start-Sleep -Seconds 3
                $secs += 3
                Write-Host ("  [{0,4}s] apktool 解包中…" -f $secs) -NoNewline
                Write-Host "`r" -NoNewline
            }
            Write-Host ''
            if ($proc -and -not $proc.HasExited) {
                Warn2 ("apktool 超时 {0}s。" -f $ApktoolTimeoutSec)
                try { $proc.Kill() } catch { }
            }
            $smali = @(Get-ChildItem -LiteralPath $apktoolOut -Recurse -Directory `
                       -Filter 'smali*' -ErrorAction SilentlyContinue).Count
            if ($smali) {
                Ok ("smali 与资源: {0}  （{1} 个 smali 目录）" -f $apktoolOut, $smali)
            } else {
                Warn2 '未找到 smali 目录，请查看 apktool.log / apktool.err'
            }
        } else { Warn2 'apktool 缺失' }

        $ErrorActionPreference = 'Stop'
        Step '完成'
        Ok "全部产物在 $Out"
        break
    }

    'install' {
        if (-not $Apk) { Die '用法：apk-debug.ps1 install -Apk <path>' }
        if (-not (Test-Path -LiteralPath $Apk)) { Die "文件不存在: $Apk" }
        $apkFull = (Resolve-Path $Apk).Path
        # 装了会掉签名的话先说清楚
        $pk = Get-PackageName -ApkPath $apkFull
        if ($pk) { Say "包名: $pk" }
        Step "安装到真机"
        $null = Adb 'install' '-r' '-d' $apkFull
        if ($script:AdbRc -ne 0) {
            Warn2 '常规安装失败，试试卸载后重装（会清掉该 app 的数据）'
            if ($pk) {
                Say "  adb uninstall $pk"
                Say "  adb install $apkFull"
            }
            exit $script:AdbRc
        }
        Ok "已安装: $apkFull"
        break
    }

    'uninstall' {
        if (-not $Target) { Die '用法：apk-debug.ps1 uninstall <包名>' }
        Adb 'uninstall' $Target | ForEach-Object { '  ' + $_ }
        break
    }

    'run' {
        if (-not $Target) {
            $Target = Get-PackageName -ApkPath $Apk
            if (-not $Target) { Die '给包名，或用 -Apk 让脚本从 APK 推断' }
        }
        Step "启动 $Target"
        # 先试 monkey（通用），再试 am start（需要精确 activity）
        $null = Adb 'shell' 'monkey' '-p' $Target '-c' 'android.intent.category.LAUNCHER' '1'
        if ($script:AdbRc -ne 0) {
            Warn2 'monkey 启动失败。该 app 可能没有 LAUNCHER activity（库/服务型）'
            Say '  用 aapt2 dump badging <apk> 看 launchable-activity 后用 am start -n <pkg>/<activity>'
        } else { Ok "已启动 $Target" }
        break
    }

    'stop' {
        if (-not $Target) { Die '用法：apk-debug.ps1 stop <包名>' }
        Adb 'force-stop' $Target | ForEach-Object { '  ' + $_ }
        Ok "已停止 $Target"
        break
    }

    'log' {
        if (-not $Filter) { $Filter = "$Target`:V *:S" }
        Step "logcat 过滤 $Filter"
        Say 'Ctrl+C 停止'
        if ($Lines -gt 0) {
            Adb 'logcat' '-d' '-v' 'brief' $Filter | Select-Object -Last $Lines |
                ForEach-Object { '  ' + $_ }
        } else {
            Adb 'logcat' '-v' 'brief' $Filter | ForEach-Object { '  ' + $_ }
        }
        break
    }

    'clear' {
        Adb 'logcat' '-c' | ForEach-Object { '  ' + $_ }
        Ok '日志已清空'
        break
    }

    'shot' {
        $out = if ($Target) { $Target } else { "shot_$(Get-Date -Format yyyyMMdd_HHmmss)" }
        if (-not $out.EndsWith('.png')) { $out += '.png' }
        $remote = '/sdcard/_apkdebug.png'
        Step "截图 -> $out"
        $null = Adb 'shell' 'screencap' '-p' $remote
        $null = Adb 'pull' $remote $out
        $null = Adb 'shell' 'rm' $remote
        if (Test-Path $out) { Ok "已保存 $out ($([math]::Round((Get-Item $out).Length/1KB,1)) KB)" }
        else { Die "截图失败：$out 没生成" }
        break
    }

    'screen' {
        # scrcpy 投屏：有就投，没有就说明为什么不能用
        $scrcpy = Tool 'scrcpy'
        if (-not $scrcpy) {
            Die @"
scrcpy 没装。它是**投屏**用的（把手机画面投到电脑窗口，人看）。

注意：智能体**不需要** scrcpy —— agent 读的是文本输出（logcat / dumpsys / frida），
截图用 '.\apk-debug.ps1 shot out.png' 就行。
scrcpy 只在**你本人**想看着手机操作时有用。
装法：winget install Genymobile.scrcpy
"@
        }
        $dev = Get-Device
        Step "scrcpy 投屏 $dev"
        & $scrcpy '-s' $dev
        break
    }

    'frida' {
        if (-not $Target) { Die '用法：apk-debug.ps1 frida <包名> [-Script x.js]' }
        $dev = Get-Device
        $frida = Require-Tool 'frida' ''
        $fridaPs = Tool 'frida-ps'
        Step "frida 附加 $Target"
        if (-not $fridaPs) { Warn2 'frida-ps 缺失，无法确认进程是否存在' }
        else {
            $hit = & $fridaPs '-Uai' 2>&1 | Select-String -Pattern [regex]::Escape($Target)
            if (-not $hit) {
                Die @"
设备上找不到 $Target 的进程。

Frida 挂的是**运行中的进程**，所以顺序必须是：
  1. .\apk-debug.ps1 run $Target     ← 先跑起来
  2. .\apk-debug.ps1 frida $Target    ← 再挂
"@
            }
            Ok '进程在，可以挂'
        }
        if ($Script) {
            if (-not (Test-Path -LiteralPath $Script)) { Die "脚本不存在: $Script" }
            Say "加载脚本: $Script"
            & $frida '-U' '-p' $Target '-l' $Script
        } else {
            Say '无 -Script，进入交互 REPL（Ctrl+D 退出）'
            & $frida '-U' '-p' $Target
        }
        break
    }

    'info' {
        if (-not $Target) { Die '用法：apk-debug.ps1 info <包名>' }
        Step "dumpsys $Target"
        @(Adb 'shell' 'dumpsys' 'package' $Target) |
            Select-String -Pattern 'versionName|versionCode|firstInstallTime|lastUpdateTime|targetSdk|minSdk|granted=true' |
            Select-Object -First 20 | ForEach-Object { '  ' + $_.Line.Trim() }
        Step "进程状态"
        @(Adb 'shell' 'dumpsys' 'activity' 'processes') |
            Select-String -SimpleMatch $Target |
            Select-Object -First 5 | ForEach-Object { '  ' + $_.Line.Trim() }
        break
    }
}

exit 0