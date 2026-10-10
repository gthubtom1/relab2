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
function Ensure-Pnpm {
    Ensure-NodeRuntime
    $dependency = Get-BootstrapDependency -Name 'pnpm'
    $pnpm = Get-NodeCommandPath -Name 'pnpm'
    $currentVersion = ''
    if ($pnpm) {
        $previousErrorActionPreference = $ErrorActionPreference
        try {
            $ErrorActionPreference = 'Continue'
            $versionOutput = @(& $pnpm --version 2>$null)
            $versionExitCode = $LASTEXITCODE
        }
        finally {
            $ErrorActionPreference = $previousErrorActionPreference
        }
        $versionLine = $versionOutput | Select-Object -First 1
        if ($versionExitCode -eq 0 -and $null -ne $versionLine) {
            $currentVersion = ([string]$versionLine).Trim()
        }
    }
    if ($currentVersion -ne [string]$dependency.version) {
        $npm = Get-NodeCommandPath -Name 'npm'
        if ([string]::IsNullOrWhiteSpace($npm)) {
            throw 'npm is not available after Node.js installation.'
        }
        & $npm install -g ([string]$dependency.package)
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to install pinned pnpm dependency $($dependency.package)."
        }
    }
}

function Assert-GitCheckoutState {
    param(
        [Parameter(Mandatory = $true)][string]$GitPath,
        [Parameter(Mandatory = $true)][string]$CheckoutPath,
        [Parameter(Mandatory = $true)][string]$PinnedCommit
    )

    $previousErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $resolvedOutput = @(& $GitPath -C $CheckoutPath rev-parse HEAD 2>$null)
        $resolveExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
    $resolvedLine = $resolvedOutput | Select-Object -First 1
    $resolvedCommit = if ($null -eq $resolvedLine) { '' } else { ([string]$resolvedLine).Trim() }
    if ($resolveExitCode -ne 0 -or $resolvedCommit -ne $PinnedCommit) {
        throw "Checkout verification failed: expected $PinnedCommit, got $resolvedCommit ($CheckoutPath)"
    }
    try {
        $ErrorActionPreference = 'Continue'
        $status = @(& $GitPath -C $CheckoutPath status --porcelain --untracked-files=all 2>$null)
        $statusExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
    if ($statusExitCode -ne 0) {
        throw "Cannot inspect checkout state: $CheckoutPath"
    }
    if ($status.Count -gt 0) {
        throw "Checkout has local changes; refusing to execute it: $CheckoutPath"
    }
}

function Move-BootstrapDirectory {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination
    )
    [IO.Directory]::Move($Source, $Destination)
}

function Ensure-GitCloneInstall {
    param(
        [Parameter(Mandatory = $true)]$Definition,
        [Parameter(Mandatory = $true)][string]$TargetPath
    )

    $git = Get-FirstCommandPath -Names @('git')
    if ([string]::IsNullOrWhiteSpace($git)) {
        throw 'git is required for git-clone bootstrap definitions.'
    }

    $pinnedCommit = if ($Definition.PSObject.Properties['pinnedCommit']) { [string]$Definition.pinnedCommit } else { '' }
    if ([string]::IsNullOrWhiteSpace($pinnedCommit)) {
        throw "Git capability $($Definition.repo) must define pinnedCommit."
    }

    if ((Test-Path -LiteralPath $TargetPath -PathType Container) -and (Test-Path -LiteralPath (Join-Path $TargetPath '.git'))) {
        Assert-GitCheckoutState -GitPath $git -CheckoutPath $TargetPath -PinnedCommit $pinnedCommit
        return $true
    }
    if (Test-Path -LiteralPath $TargetPath) {
        throw "Install path exists but is not a git checkout: $TargetPath"
    }

    $parent = Split-Path -Path $TargetPath -Parent
    Ensure-DownloadDirectory -Path $parent
    $stagePath = Join-Path $parent ('.reverse-bootstrap-{0}' -f [Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $stagePath | Out-Null
    try {
        & $git init --quiet $stagePath
        if ($LASTEXITCODE -ne 0) { throw 'git init failed' }
        & $git -C $stagePath remote add origin $Definition.repo
        if ($LASTEXITCODE -ne 0) { throw 'git remote add failed' }
        & $git -C $stagePath fetch --depth 1 origin $pinnedCommit
        if ($LASTEXITCODE -ne 0) { throw 'git fetch failed' }
        & $git -C $stagePath checkout --quiet --detach FETCH_HEAD
        if ($LASTEXITCODE -ne 0) { throw 'git checkout failed' }
        Assert-GitCheckoutState -GitPath $git -CheckoutPath $stagePath -PinnedCommit $pinnedCommit
        Move-BootstrapDirectory -Source $stagePath -Destination $TargetPath
        if (-not (Test-Path -LiteralPath (Join-Path $TargetPath '.git') -PathType Container)) {
            throw "Failed to promote staged checkout to $TargetPath"
        }
    }
    finally {
        if (Test-Path -LiteralPath $stagePath) {
            Remove-Item -LiteralPath $stagePath -Recurse -Force
        }
    }

    return $true
}

function Invoke-AnythingAnalyzerPinnedInstall {
    param(
        [Parameter(Mandatory = $true)][string]$RepoDir,
        [Parameter(Mandatory = $true)][string]$PnpmPath,
        [Parameter(Mandatory = $true)][string]$GitPath,
        [Parameter(Mandatory = $true)][string]$PinnedCommit,
        [string]$VsBuildToolsError = ''
    )

    $workspacePath = Join-Path $RepoDir 'pnpm-workspace.yaml'
    $workspaceExisted = Test-Path -LiteralPath $workspacePath -PathType Leaf
    $workspaceBytes = if ($workspaceExisted) { [IO.File]::ReadAllBytes($workspacePath) } else { $null }

    Push-Location $RepoDir
    try {
        Approve-AnythingAnalyzerBuildScripts -RepoDir $RepoDir
        if (-not (Test-AnythingAnalyzerElectronHealthy -RepoDir $RepoDir -PnpmPath $PnpmPath)) {
            $nodeModules = Join-Path $RepoDir 'node_modules'
            Remove-Item -LiteralPath $nodeModules -Recurse -Force -ErrorAction SilentlyContinue
        }

        & $PnpmPath install --frozen-lockfile
        if ($LASTEXITCODE -ne 0) {
            if ($VsBuildToolsError) { throw "pnpm install failed for anything-analyzer. Visual Studio Build Tools auto-install also failed earlier: $VsBuildToolsError" }
            throw 'pnpm install failed for anything-analyzer.'
        }
        & $PnpmPath rebuild electron esbuild better-sqlite3
        if ($LASTEXITCODE -ne 0) {
            if ($VsBuildToolsError) { throw "pnpm rebuild failed for anything-analyzer. Visual Studio Build Tools auto-install also failed earlier: $VsBuildToolsError" }
            throw 'pnpm rebuild failed for anything-analyzer.'
        }
        if (-not (Test-AnythingAnalyzerElectronHealthy -RepoDir $RepoDir -PnpmPath $PnpmPath)) {
            throw 'anything-analyzer Electron dependency is still unhealthy after pnpm rebuild.'
        }
    }
    finally {
        Pop-Location
        if ($workspaceExisted) {
            [IO.File]::WriteAllBytes($workspacePath, $workspaceBytes)
        }
        elseif (Test-Path -LiteralPath $workspacePath) {
            Remove-Item -LiteralPath $workspacePath -Force
        }
    }

    Assert-GitCheckoutState -GitPath $GitPath -CheckoutPath $RepoDir -PinnedCommit $PinnedCommit
}
