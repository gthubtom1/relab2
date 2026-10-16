# ★ PSModulePath 自愈（2026-10-10 注入，路径由 inject-psmp.py 统一计算）：剔除 WindowsApps 版 PowerShell 7 的模块目录，否则 PS 5.1 会因 TypeData 重复定义失败而使 Get-FileHash / Get-ExecutionPolicy 不可用（已造成两次假绿 + 一次失败被吞）。重算/迁移后请重跑 work/envinit/inject-psmp.py
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$scratch = Join-Path ([IO.Path]::GetTempPath()) ('reverse-bootstrap-ps-' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $scratch | Out-Null

function Ensure-DownloadDirectory { param([string]$Path) New-Item -ItemType Directory -Path $Path -Force | Out-Null }
function Get-FirstCommandPath { param([string[]]$Names) return (Get-Command $Names[0]).Source }
function Ensure-NodeRuntime {}
function Get-NodeCommandPath { param([string]$Name) $command = Get-Command $Name -ErrorAction SilentlyContinue; if ($command) { return $command.Source } }
function Get-BootstrapDependency { return [pscustomobject]@{ package = 'pnpm@10.24.0'; version = '10.24.0' } }
function Approve-AnythingAnalyzerBuildScripts { param([string]$RepoDir) Set-Content (Join-Path $RepoDir 'pnpm-workspace.yaml') 'generated' }
function Test-AnythingAnalyzerElectronHealthy { return $true }

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
. (Join-Path $PSScriptRoot 'lib/BootstrapSupplyChain.ps1')

function Assert-True { param([bool]$Condition, [string]$Message) if (-not $Condition) { throw $Message } }

# ★ 2026-10-17 路径模板解析回归（Linux CI step6 的真实根因，见 lib/Bootstrap.ps1 的注释）。
#   两条独立缺陷，各自都足以让子进程看不见夹具：
#     ① Get-ReverseUserProfilePath 只认 USERPROFILE，POSIX 上该变量不存在 -> 展开成空
#     ② manifest 的路径模板用 Windows 反斜杠，POSIX 上不归一化 -> 得到带 `\` 的单个文件名
#   断言放在这里（本脚本 CI 两个平台都跑），锁死它们。
. (Join-Path $PSScriptRoot 'lib/Bootstrap.ps1')
$__profile = Get-ReverseUserProfilePath
Assert-True (-not [string]::IsNullOrWhiteSpace($__profile)) 'user profile path resolved to empty (POSIX needs the HOME fallback)'
$__seclists = Get-ReverseBootstrapDefinition -Name 'seclists'
Assert-True (-not [string]::IsNullOrWhiteSpace($__seclists.installDir)) 'seclists installDir expanded to empty'
Assert-True ([System.IO.Path]::IsPathRooted([string]$__seclists.installDir)) ("seclists installDir is not an absolute path: " + $__seclists.installDir)
if (-not (Test-Relab2IsWindows)) {
    Assert-True (-not ([string]$__seclists.installDir).Contains('\')) ("POSIX installDir still carries a backslash separator: " + $__seclists.installDir)
}
Assert-True ((Get-ReverseBootstrapDefinition -Name 'jadx').assetRegex -eq '^jadx-1\.5\.6\.zip$') 'separator normalization corrupted a non-path field (assetRegex)'
Remove-Variable -Name __profile, __seclists -ErrorAction SilentlyContinue
function Invoke-Git { param([string[]]$Arguments) & git @Arguments; if ($LASTEXITCODE -ne 0) { throw "git failed: $Arguments" } }
function Write-UnixExecutable {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Content
    )

    $normalized = ($Content -replace "`r`n", "`n") -replace "`r", "`n"
    if (-not $normalized.EndsWith("`n")) { $normalized += "`n" }
    [IO.File]::WriteAllText($Path, $normalized, [Text.UTF8Encoding]::new($false))
    & chmod +x $Path
}

try {
    $source = Join-Path $scratch 'source'
    New-Item -ItemType Directory -Path $source | Out-Null
    Invoke-Git -Arguments @('-C', $source, 'init', '--quiet')
    Invoke-Git -Arguments @('-C', $source, 'config', 'user.email', 'test@example.invalid')
    Invoke-Git -Arguments @('-C', $source, 'config', 'user.name', 'test')
    Set-Content (Join-Path $source 'package.json') '{}'
    Invoke-Git -Arguments @('-C', $source, 'add', 'package.json')
    Invoke-Git -Arguments @('-C', $source, 'commit', '--quiet', '-m', 'fixture')
    $pin = (& git -C $source rev-parse HEAD).Trim()
    $definition = [pscustomobject]@{ repo = $source; pinnedCommit = $pin }

    $target = Join-Path $scratch 'installed'
    Ensure-GitCloneInstall -Definition $definition -TargetPath $target | Out-Null
    Assert-True ((& git -C $target rev-parse HEAD).Trim() -eq $pin) 'pinned checkout was not promoted'
    Set-Content (Join-Path $target 'package.json') '{"dirty":true}'
    try { Ensure-GitCloneInstall -Definition $definition -TargetPath $target | Out-Null; throw 'dirty checkout accepted' } catch { Assert-True ($_.Exception.Message -match 'local changes') 'dirty rejection reason changed' }

    $failedTarget = Join-Path $scratch 'failed'
    $badDefinition = [pscustomobject]@{ repo = (Join-Path $scratch 'missing'); pinnedCommit = $pin }
    $failedFetchRejected = $false
    try { Ensure-GitCloneInstall -Definition $badDefinition -TargetPath $failedTarget | Out-Null } catch { $failedFetchRejected = $true }
    Assert-True $failedFetchRejected 'failed fetch accepted'
    Assert-True (-not (Test-Path $failedTarget)) 'failed fetch poisoned final path'
    Assert-True (@(Get-ChildItem $scratch -Filter '.reverse-bootstrap-*').Count -eq 0) 'failed fetch left staging path'

    $raceTarget = Join-Path $scratch 'race'
    $raceStage = Join-Path $scratch '.reverse-bootstrap-race'
    New-Item -ItemType Directory -Path $raceTarget, $raceStage | Out-Null
    Set-Content (Join-Path $raceTarget 'owner.txt') owner
    $raceRejected = $false
    try { Move-BootstrapDirectory -Source $raceStage -Destination $raceTarget } catch { $raceRejected = $true }
    Assert-True $raceRejected 'promotion race accepted'
    Assert-True ((Get-Content (Join-Path $raceTarget 'owner.txt')) -eq 'owner') 'promotion race modified concurrent target'
    Remove-Item -LiteralPath $raceStage -Recurse -Force

    $bin = Join-Path $scratch 'bin'
    New-Item -ItemType Directory -Path $bin | Out-Null
    $env:PATH = "$bin$([IO.Path]::PathSeparator)$env:PATH"
    $env:BOOTSTRAP_PS_LOG = Join-Path $scratch 'commands.log'
    $isWindowsHost = [Environment]::OSVersion.Platform -eq [PlatformID]::Win32NT
    $stub = Join-Path $bin ($(if ($isWindowsHost) { 'npm.cmd' } else { 'npm' }))
    if ($isWindowsHost) {
        Set-Content $stub @'
@echo off
echo npm^|%*>>"%BOOTSTRAP_PS_LOG%"
'@
    }
    else {
        Write-UnixExecutable -Path $stub -Content @'
#!/bin/sh
printf "npm|%s\n" "$*" >> "$BOOTSTRAP_PS_LOG"
'@
    }
    $pnpm = Join-Path $bin ($(if ($isWindowsHost) { 'pnpm.cmd' } else { 'pnpm' }))
    if ($isWindowsHost) { Set-Content $pnpm "@echo off`r`necho 0" }
    else { Write-UnixExecutable -Path $pnpm -Content "#!/bin/sh`necho 0" }
    Ensure-Pnpm
    Assert-True ((Get-Content $env:BOOTSTRAP_PS_LOG) -match 'npm\|install -g pnpm@10.24.0') 'pnpm install was not pinned'

    Invoke-Git -Arguments @('-C', $target, 'checkout', '--quiet', '--', 'package.json')
    if ($isWindowsHost) {
        Set-Content $pnpm @'
@echo off
if "%1"=="--version" (echo 10.24.0) else (echo pnpm^|%*>>"%BOOTSTRAP_PS_LOG%")
'@
    }
    else {
        Write-UnixExecutable -Path $pnpm -Content @'
#!/bin/sh
[ "$1" = --version ] && { echo 10.24.0; exit; }
printf "pnpm|%s\n" "$*" >> "$BOOTSTRAP_PS_LOG"
'@
    }
    $commandLogBefore = Get-Content -LiteralPath $env:BOOTSTRAP_PS_LOG -Raw
    Ensure-Pnpm
    $commandLogAfter = Get-Content -LiteralPath $env:BOOTSTRAP_PS_LOG -Raw
    Assert-True ($commandLogAfter -eq $commandLogBefore) 'matching pnpm version triggered reinstall'
    function Approve-AnythingAnalyzerBuildScripts { param([string]$RepoDir) Set-Content (Join-Path $RepoDir 'pnpm-workspace.yaml') 'generated'; Set-Content (Join-Path $RepoDir 'package.json') '{"mutated":true}' }
    $dirtyRejected = $false
    try { Invoke-AnythingAnalyzerPinnedInstall -RepoDir $target -PnpmPath $pnpm -GitPath (Get-Command git).Source -PinnedCommit $pin } catch { $dirtyRejected = $_.Exception.Message -match 'local changes' }
    Assert-True $dirtyRejected 'post-install dirty checkout accepted or rejection reason changed'
    Assert-True (-not (Test-Path (Join-Path $target 'pnpm-workspace.yaml'))) 'generated workspace file was not removed'

    Invoke-Git -Arguments @('-C', $target, 'config', 'user.email', 'test@example.invalid')
    Invoke-Git -Arguments @('-C', $target, 'config', 'user.name', 'test')
    Invoke-Git -Arguments @('-C', $target, 'commit', '--allow-empty', '--quiet', '-m', 'wrong checkout')
    $wrongCommitRejected = $false
    try { Ensure-GitCloneInstall -Definition $definition -TargetPath $target | Out-Null } catch { $wrongCommitRejected = $_.Exception.Message -match 'expected' }
    Assert-True $wrongCommitRejected 'clean wrong-commit checkout accepted'

    $publicProfile = [Environment]::GetFolderPath([Environment+SpecialFolder]::UserProfile)
    $publicTools = Join-Path $publicProfile 'Tools'
    $publicTarget = Join-Path $publicTools 'SecLists'
    if (Test-Path -LiteralPath $publicTarget) {
        Write-Host 'SKIP: public bootstrap exit regression (existing SecLists checkout)'
    }
    else {
        $createdPublicTools = -not (Test-Path -LiteralPath $publicTools)
        try {
            New-Item -ItemType Directory -Path $publicTarget -Force | Out-Null
            Invoke-Git -Arguments @('-C', $publicTarget, 'init', '--quiet')
            Invoke-Git -Arguments @('-C', $publicTarget, 'config', 'user.email', 'test@example.invalid')
            Invoke-Git -Arguments @('-C', $publicTarget, 'config', 'user.name', 'test')
            Set-Content (Join-Path $publicTarget 'fixture.txt') 'wrong checkout'
            Invoke-Git -Arguments @('-C', $publicTarget, 'add', 'fixture.txt')
            Invoke-Git -Arguments @('-C', $publicTarget, 'commit', '--quiet', '-m', 'fixture')

            $powerShellHost = if ($PSVersionTable.PSEdition -eq 'Desktop') { Join-Path $PSHOME 'powershell.exe' } else { Join-Path $PSHOME 'pwsh' }
            # ★ 2026-10-10 修正：原来把 `& $host ... -File child` 的整条管道直接
            #   喂给 ConvertFrom-Json。PowerShell 的 `&` 调用会把子进程的 stderr
            #   （git clone 的 fatal/progress）混进同一个管道，于是报「无效的 JSON
            #   基数」—— 而子进程其实**正确**返回了 failed 状态。实测本机长期 rc=1
            #   （HEAD 上同样红，不是本轮回归）。正确做法：stderr 分流，只解析 stdout。
            $childErrFile = Join-Path $scratch 'child-stderr.txt'
            $warnFile = Join-Path $scratch 'child-warnings.txt'
            # ★ bootstrap-reverse 会用 Write-Host/Write-Warning 往 **stdout** 写人类可读提示
            #   （找不到 manifest 时的警告、跳过安装的 INFO 等）。PowerShell 的 `&` 调用
            #   会把这些混进管道，于是 ConvertFrom-Json 报「无效的 JSON 基数」。
            #   子进程**正确**返回了 failed JSON，是我们的取值方式错了。
            #   正确做法：整条 stdout 落盘，只解析其中**最后一个** { 起始的 JSON 段。
            $childOutFile = Join-Path $scratch 'child-stdout.txt'
            $childOutput = @(& $powerShellHost -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'bootstrap-reverse.ps1') -Capability seclists -SkipRefresh > $childOutFile 2> $childErrFile)
            $childExitCode = $LASTEXITCODE
            $global:LASTEXITCODE = 0
            $childStdout = if (Test-Path -LiteralPath $childOutFile) { Get-Content -LiteralPath $childOutFile -Raw -Encoding UTF8 } else { '' }
            # 从**第一个** '{' 起截取（Write-Host 提示都在 JSON 之前），
            # 再逐字符配平花括号，避免 JSON 里的字符串含有 '{' 时截断。
            $brace = 0; $jsonStart = -1; $jsonEnd = -1
            for ($ci = 0; $ci -lt $childStdout.Length; $ci++) {
                $ch = $childStdout[$ci]
                if ($ch -eq '{') { if ($jsonStart -lt 0) { $jsonStart = $ci }; $brace++ }
                elseif ($ch -eq '}') { $brace--; if ($brace -eq 0 -and $jsonStart -ge 0) { $jsonEnd = $ci; break } }
            }
            $childResult = $null
            if ($jsonStart -ge 0 -and $jsonEnd -gt $jsonStart) {
                $childResult = $childStdout.Substring($jsonStart, $jsonEnd - $jsonStart + 1) | ConvertFrom-Json -ErrorAction Stop
            } else {
                $childErrText = if (Test-Path -LiteralPath $childErrFile) { (Get-Content -LiteralPath $childErrFile -Raw -ErrorAction SilentlyContinue) } else { '' }
                throw ("child produced no JSON object. stdout=<$childStdout> stderr=<$childErrText>")
            }
            Assert-True ($childResult.error -match 'Checkout verification failed') 'failed public bootstrap did not report checkout verification'
        }
        finally {
            Remove-Item -LiteralPath $publicTarget -Recurse -Force -ErrorAction SilentlyContinue
            if ($createdPublicTools -and (Test-Path -LiteralPath $publicTools) -and (@(Get-ChildItem -LiteralPath $publicTools -Force).Count -eq 0)) {
                Remove-Item -LiteralPath $publicTools -Force -ErrorAction SilentlyContinue
            }
        }
    }

    . (Join-Path $PSScriptRoot 'bootstrap-reverse.ps1') -Capability '__test_missing__' -SkipRefresh | Out-Null
    $script:gitCloneDefinition = [pscustomobject]@{
        name = 'test-git-clone'
        bootstrapKind = 'git-clone'
        canAutoInstall = $true
        installDir = (Join-Path $scratch 'test-git-clone')
    }
    $script:gitCloneVerifierCalled = $false
    function Get-ReverseBootstrapDefinition { param([string]$Name) return $script:gitCloneDefinition }
    function Get-ReverseCapabilityState { param([string]$Name) return [pscustomobject]@{ Ready = $true } }
    function Resolve-ReverseToolSpec { param([string]$Name) return [pscustomobject]@{ Available = $true } }
    function Ensure-GitCloneInstall {
        param($Definition, [string]$TargetPath)
        $script:gitCloneVerifierCalled = $true
        return [pscustomobject]@{ Verified = $true }
    }
    $gitCloneResult = Ensure-Capability -Name 'test-git-clone'
    Assert-True $script:gitCloneVerifierCalled 'available git-clone capability skipped checkout verification'
    Assert-True $gitCloneResult.Verified 'git-clone capability did not return checkout verification result'

    $script:serviceCheckoutVerifierCalled = $false
    function Ensure-GitCloneInstall {
        param($Definition, [string]$TargetPath)
        $script:serviceCheckoutVerifierCalled = $true
    }
    function Test-ReverseTcpPort { param([int]$Port) return $true }
    Start-AnythingAnalyzerService -Definition ([pscustomobject]@{
        installDir = (Join-Path $scratch 'anything-analyzer')
        repoUrl = $source
        pinnedCommit = $pin
        servicePort = 23816
    }) -AuthToken 'test-token'
    Assert-True $script:serviceCheckoutVerifierCalled 'running Anything Analyzer service skipped checkout verification'

    Write-Host 'PowerShell bootstrap supply-chain regression passed'
}
finally {
    Remove-Item -LiteralPath $scratch -Recurse -Force -ErrorAction SilentlyContinue
}
