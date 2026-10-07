Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# 进程内缓存槽（StrictMode 下必须先声明，否则读取未初始化变量会抛错）。
$script:ReverseHackerRootCache = $null

function Get-ReverseUserProfilePath {
    [CmdletBinding()]
    param()

    $profilePath = [Environment]::GetFolderPath([Environment+SpecialFolder]::UserProfile)
    if (-not [string]::IsNullOrWhiteSpace($profilePath)) {
        return $profilePath
    }
    if (-not [string]::IsNullOrWhiteSpace($HOME)) {
        return $HOME
    }
    if (-not [string]::IsNullOrWhiteSpace($env:USERPROFILE)) {
        return $env:USERPROFILE
    }
    throw 'Unable to resolve the current user profile path.'
}

function Get-ReverseHackerRoot {
    [CmdletBinding()]
    param()

    # 规则 1（探测优先，声明兜底）：本函数不再返回硬编码字面量。
    #   1) 显式配置：环境变量 REVERSE_HACKER_ROOT —— 设了就用，但仍要 Test-Path 通过
    #   2) 候选列表逐个 Test-Path：C:\HACKER -> D:\HACKER
    #   3) 全失败 -> 抛错明确报错，禁止猜一个盘符继续跑
    # 旧实现（.bak-20261005 :30）是 `return 'D:\HACKER'`：换台没 D 盘的机器会静默全 miss，
    # 索引照样生成、只是每条都「未装」，不报错——这正是规则 1 要消灭的失败模式。
    if ($script:ReverseHackerRootCache) {
        return $script:ReverseHackerRootCache
    }

    $candidates = New-Object System.Collections.Generic.List[string]
    if (-not [string]::IsNullOrWhiteSpace($env:REVERSE_HACKER_ROOT)) {
        $candidates.Add($env:REVERSE_HACKER_ROOT)
    }
    $candidates.Add('C:\HACKER')
    $candidates.Add('D:\HACKER')
    # 便携兜底：规范根全 miss 时，用磁盘发现反推工具根（工具装在第三方
    # 策展包 / 绿色版目录 / 本仓 _tools 时都能找到）。与 detect-env.ps1 同策略：
    # 「位置不是判据，可用性才是」。
    $repoRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
    if ($repoRoot) { $candidates.Add((Join-Path $repoRoot '_tools')) }
    $sigs = @('diec.exe','x64dbg.exe','x96dbg.exe','idat.exe','analyzeHeadless.bat',
              'dnSpy.exe','jadx.bat','capa.exe','floss.exe','radare2.exe')
    $scanRoots = @()
    if ($repoRoot) { $scanRoots += $repoRoot }
    foreach ($d in [System.IO.DriveInfo]::GetDrives()) {
        if ($d.IsReady) { $scanRoots += $d.RootDirectory.FullName }
    }
    foreach ($r in $scanRoots) {
        try {
            $hit = Get-ChildItem -LiteralPath $r -Recurse -Depth 3 -File -Force -ErrorAction SilentlyContinue |
                   Where-Object { $sigs -contains $_.Name } | Select-Object -First 1
            if ($hit) { $candidates.Add($hit.DirectoryName); break }
        } catch { continue }
    }

    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate -PathType Container) {
            $resolved = (Resolve-Path -LiteralPath $candidate).ProviderPath
            $script:ReverseHackerRootCache = $resolved
            if (-not $env:DOTNET_ROOT) {
                $dotnetCandidate = Join-Path $resolved 'dotnet'
                if (Test-Path -LiteralPath $dotnetCandidate -PathType Container) {
                    $env:DOTNET_ROOT = $dotnetCandidate
                }
            }
            if (-not $env:RUSTUP_HOME) {
                $rustupCandidate = Join-Path $resolved 'rustup'
                if (Test-Path -LiteralPath $rustupCandidate -PathType Container) {
                    $env:RUSTUP_HOME = $rustupCandidate
                }
            }
            if (-not $env:CARGO_HOME) {
                $cargoCandidate = Join-Path $resolved 'cargo'
                if (Test-Path -LiteralPath $cargoCandidate -PathType Container) {
                    $env:CARGO_HOME = $cargoCandidate
                }
            }
            if (-not $env:GOROOT) {
                $goCandidate = Join-Path $resolved 'go'
                if (Test-Path -LiteralPath $goCandidate -PathType Container) {
                    $env:GOROOT = $goCandidate
                }
            }
            return $resolved
        }
    }

    throw ("TOOL_ROOT 未解析：本机找不到工具根。已按顺序探测 " + ($candidates -join ' -> ') +
           "（1. 环境变量 REVERSE_HACKER_ROOT  2. C:\HACKER  3. D:\HACKER）。" +
           "处置分支：(a) 工具确实装在别处 -> 设 REVERSE_HACKER_ROOT 后重跑 refresh-tool-index.ps1；" +
           "(b) 本机还没装任何工具 -> 先走 bootstrap，此时索引生成失败属预期，不是脚本 bug。")
}

function Join-ReverseOptionalPath {
    [CmdletBinding()]
    param(
        [AllowNull()]
        [string]$Path,

        [Parameter(Mandatory = $true)]
        [string]$ChildPath
    )

    if ([string]::IsNullOrWhiteSpace($Path)) {
        return ''
    }
    return Join-Path $Path $ChildPath
}

function Get-ReverseToolCatalog {
    [CmdletBinding()]
    param()

    $userProfile = Get-ReverseUserProfilePath
    $localAppData = [Environment]::GetEnvironmentVariable('LOCALAPPDATA')
    $appData = [Environment]::GetEnvironmentVariable('APPDATA')

    return @(
        [pscustomobject]@{
            Name = 'jadx'
            Skill = 'apk-reverse'
            Purpose = 'Java 反编译'
            FixedVersion = 'v0.5.0'
            VersionArgs = @()
            Fallbacks = @(
                [pscustomobject]@{ Type = 'command'; Value = 'jadx' },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path $userProfile 'Tools\jadx\bin\jadx.bat') }
            )
        }
        [pscustomobject]@{
            Name = 'apktool'
            Skill = 'apk-reverse'
            Purpose = 'APK 解包与重建'
            FixedVersion = 'v0.5.0'
            VersionArgs = @()
            Fallbacks = @(
                [pscustomobject]@{ Type = 'command'; Value = 'apktool' },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path $userProfile 'Tools\apktool\apktool.bat') },
                [pscustomobject]@{ Type = 'java-jar'; Value = (Join-Path $userProfile 'Tools\apktool\apktool.jar') }
            )
        }
        [pscustomobject]@{
            Name = 'adb'
            Skill = 'apk-reverse'
            Purpose = '设备连接与 logcat'
            VersionArgs = @('version')
            Fallbacks = @(
                [pscustomobject]@{ Type = 'command'; Value = 'adb' },
                [pscustomobject]@{ Type = 'path'; Value = (Join-ReverseOptionalPath -Path $localAppData -ChildPath 'Android\Sdk\platform-tools\adb.exe') }
            )
        }
        [pscustomobject]@{
            Name = 'java'
            Skill = 'apk-reverse'
            Purpose = '运行 jar 与 Java 工具链'
            VersionArgs = @('-version')
            Fallbacks = @(
                [pscustomobject]@{ Type = 'command'; Value = 'java' }
            )
        }
        [pscustomobject]@{
            Name = 'apksigner'
            Skill = 'apk-reverse'
            Purpose = 'APK 签名'
            FixedVersion = 'v0.5.0'
            VersionArgs = @()
            Fallbacks = @(
                [pscustomobject]@{ Type = 'command'; Value = 'apksigner' }
            )
        }
        [pscustomobject]@{
            Name = 'zipalign'
            Skill = 'apk-reverse'
            Purpose = 'APK 对齐'
            FixedVersion = 'v0.5.0'
            VersionArgs = @()
            Fallbacks = @(
                [pscustomobject]@{ Type = 'command'; Value = 'zipalign' }
            )
        }
        [pscustomobject]@{
            Name = 'idalib-mcp'
            Skill = 'ida-reverse'
            Purpose = 'IDA Pro idalib MCP HTTP/stdio 服务器'
            FixedVersion = 'v0.5.0'
            VersionArgs = @('--help')
            Fallbacks = @(
                [pscustomobject]@{ Type = 'command'; Value = 'idalib-mcp' },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path $userProfile 'Tools\bin\idalib-mcp.cmd') },
                [pscustomobject]@{ Type = 'path'; Value = (Join-ReverseOptionalPath -Path $localAppData -ChildPath 'Python\pythoncore-3.14-64\Scripts\idalib-mcp.exe') },
                [pscustomobject]@{ Type = 'path'; Value = (Join-ReverseOptionalPath -Path $localAppData -ChildPath 'Programs\Python\Python314\Scripts\idalib-mcp.exe') },
                [pscustomobject]@{ Type = 'path'; Value = (Join-ReverseOptionalPath -Path $localAppData -ChildPath 'Programs\Python\Python312\Scripts\idalib-mcp.exe') },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path $userProfile 'Desktop\IDA Pro 9.4\App\IDA Pro\Python314\Scripts\idalib-mcp.exe') },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path ([Environment]::GetFolderPath('Desktop')) 'IDA Pro 9.4\App\IDA Pro\Python314\Scripts\idalib-mcp.exe') },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path $userProfile 'Tools\IDA Pro 9.4\App\IDA Pro\Python314\Scripts\idalib-mcp.exe') }
            )
        }
        [pscustomobject]@{
            Name = 'ida-pro-mcp'
            Skill = 'ida-reverse'
            Purpose = 'IDA Pro MCP CLI / 插件安装器'
            FixedVersion = 'v0.5.0'
            VersionArgs = @('--help')
            Fallbacks = @(
                [pscustomobject]@{ Type = 'command'; Value = 'ida-pro-mcp' },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path $userProfile 'Tools\bin\ida-pro-mcp.cmd') },
                [pscustomobject]@{ Type = 'path'; Value = (Join-ReverseOptionalPath -Path $localAppData -ChildPath 'Python\pythoncore-3.14-64\Scripts\ida-pro-mcp.exe') },
                [pscustomobject]@{ Type = 'path'; Value = (Join-ReverseOptionalPath -Path $localAppData -ChildPath 'Programs\Python\Python314\Scripts\ida-pro-mcp.exe') },
                [pscustomobject]@{ Type = 'path'; Value = (Join-ReverseOptionalPath -Path $localAppData -ChildPath 'Programs\Python\Python312\Scripts\ida-pro-mcp.exe') },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path $userProfile 'Desktop\IDA Pro 9.4\App\IDA Pro\Python314\Scripts\ida-pro-mcp.exe') },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path ([Environment]::GetFolderPath('Desktop')) 'IDA Pro 9.4\App\IDA Pro\Python314\Scripts\ida-pro-mcp.exe') }
            )
        }
        [pscustomobject]@{
            Name = 'ida'
            Skill = 'ida-reverse'
            Purpose = 'IDA Pro 主程序'
            FixedVersion = '9.4.260713.a97520e5'
            VersionArgs = @()
            Fallbacks = @(
                [pscustomobject]@{ Type = 'command'; Value = 'ida' },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path (Get-ReverseHackerRoot) 'IDA Professional 9.4\ida.exe') },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path (Get-ReverseHackerRoot) 'IDA Professional 9.4\idat.exe') },
                [pscustomobject]@{ Type = 'path'; Value = 'C:\Program Files\IDA Professional 9.4\ida.exe' },
                [pscustomobject]@{ Type = 'path'; Value = 'C:\Program Files\IDA Pro 9.4\ida.exe' },
                [pscustomobject]@{ Type = 'path'; Value = 'C:\Program Files\IDA Pro\ida.exe' },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path $userProfile 'Desktop\IDA Pro 9.4\App\IDA Pro\ida.exe') },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path ([Environment]::GetFolderPath('Desktop')) 'IDA Pro 9.4\App\IDA Pro\ida.exe') },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path $userProfile 'Tools\IDA Pro 9.4\App\IDA Pro\ida.exe') }
            )
        }
        # ── .NET 逆向（dotnet-reverse）：本机此前零登记，本次补齐 ──
        [pscustomobject]@{
            Name = 'dnSpy'
            Skill = 'dotnet-reverse'
            Purpose = 'dnSpy .NET 反编译器 GUI（唯一带 IL 编辑器的面板；会弹窗，禁止经 bash 执行，改用 dnSpy.Console）'
            FixedVersion = '6.6.0'
            VersionArgs = @()
            Fallbacks = @(
                [pscustomobject]@{ Type = 'command'; Value = 'dnSpy' },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path (Get-ReverseHackerRoot) 'dnSpy\dnSpy.exe') },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path $userProfile 'Tools\dnSpy\dnSpy.exe') },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path $userProfile 'Tools\dnSpyEx\dnSpy.exe') },
                [pscustomobject]@{ Type = 'path'; Value = 'C:\Tools\dnSpy\dnSpy.exe' }
            )
        }
        [pscustomobject]@{
            Name = 'dnSpy.Console'
            Skill = 'dotnet-reverse'
            Purpose = 'dnSpy 无头 CLI（批量反编译 .NET 程序，本机 Windows 原生替代 ilspycmd）'
            FixedVersion = '6.6.0'
            VersionArgs = @('--help')
            Fallbacks = @(
                [pscustomobject]@{ Type = 'command'; Value = 'dnSpy.Console' },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path (Get-ReverseHackerRoot) 'dnSpy\dnSpy.Console.exe') },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path $userProfile 'Tools\dnSpy\dnSpy.Console.exe') },
                [pscustomobject]@{ Type = 'path'; Value = 'C:\Tools\dnSpy\dnSpy.Console.exe' }
            )
        }
        [pscustomobject]@{
            Name = 'de4dot'
            Skill = 'dotnet-reverse'
            Purpose = '.NET 脱壳器（自动剥离 ConfuserEx 等主流混淆）'
            VersionArgs = @('--help')
            Fallbacks = @(
                [pscustomobject]@{ Type = 'command'; Value = 'de4dot' },
                # 可执行名带架构后缀，HackerRootProbe 的 <Name>\<Name>.exe 形状命不中，必须显式登记
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path (Get-ReverseHackerRoot) 'de4dot\de4dot-x64.exe') },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path (Get-ReverseHackerRoot) 'de4dot\de4dot-x86.exe') },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path $userProfile 'Tools\de4dot\de4dot-x64.exe') }
            )
        }
        [pscustomobject]@{
            Name = 'ilspycmd'
            Skill = 'dotnet-reverse'
            Purpose = 'ILSpy CLI 无头反编译器（.NET 命令行反编译）'
            VersionArgs = @('--version')
            Fallbacks = @(
                [pscustomobject]@{ Type = 'command'; Value = 'ilspycmd' },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path (Get-ReverseHackerRoot) 'ilspycmd\ilspycmd.exe') }
            )
        }
        [pscustomobject]@{
            Name = 'dotnet'
            Skill = 'dotnet-reverse'
            Purpose = '.NET SDK/Runtime CLI 运行环境'
            VersionArgs = @('--version')
            Fallbacks = @(
                [pscustomobject]@{ Type = 'command'; Value = 'dotnet' },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path (Get-ReverseHackerRoot) 'dotnet\dotnet.exe') }
            )
        }
        # ── C/Go/CMake/Rust 构建工具链 ──
        [pscustomobject]@{
            Name = 'gcc'
            Skill = 'reverse-engineering'
            Purpose = 'MinGW-w64 GCC 本地 C/C++ 编译器'
            VersionArgs = @('--version')
            Fallbacks = @(
                [pscustomobject]@{ Type = 'command'; Value = 'gcc' },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path (Get-ReverseHackerRoot) 'w64devkit\bin\gcc.exe') },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path (Get-ReverseHackerRoot) 'mingw64\bin\gcc.exe') }
            )
        }
        [pscustomobject]@{
            Name = 'make'
            Skill = 'reverse-engineering'
            Purpose = 'GNU Make 构建工具'
            VersionArgs = @('--version')
            Fallbacks = @(
                [pscustomobject]@{ Type = 'command'; Value = 'make' },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path (Get-ReverseHackerRoot) 'w64devkit\bin\make.exe') },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path (Get-ReverseHackerRoot) 'mingw64\bin\make.exe') }
            )
        }
        [pscustomobject]@{
            Name = 'go'
            Skill = 'reverse-engineering'
            Purpose = 'Go 语言便携编译器与构建工具'
            VersionArgs = @('version')
            Fallbacks = @(
                [pscustomobject]@{ Type = 'command'; Value = 'go' },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path (Get-ReverseHackerRoot) 'go\bin\go.exe') }
            )
        }
        [pscustomobject]@{
            Name = 'cmake'
            Skill = 'reverse-engineering'
            Purpose = 'CMake 跨平台构建系统'
            VersionArgs = @('--version')
            Fallbacks = @(
                [pscustomobject]@{ Type = 'command'; Value = 'cmake' },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path (Get-ReverseHackerRoot) 'cmake\bin\cmake.exe') }
            )
        }
        [pscustomobject]@{
            Name = 'rustc'
            Skill = 'reverse-engineering'
            Purpose = 'Rust 编译器'
            VersionArgs = @('--version')
            Fallbacks = @(
                [pscustomobject]@{ Type = 'command'; Value = 'rustc' },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path (Get-ReverseHackerRoot) 'cargo\bin\rustc.exe') }
            )
        }
        [pscustomobject]@{
            Name = 'cargo'
            Skill = 'reverse-engineering'
            Purpose = 'Rust 包管理器与构建工具'
            VersionArgs = @('--version')
            Fallbacks = @(
                [pscustomobject]@{ Type = 'command'; Value = 'cargo' },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path (Get-ReverseHackerRoot) 'cargo\bin\cargo.exe') }
            )
        }
        # ── .NET 逆向 end ──
        [pscustomobject]@{
            Name = 'binaryninja'
            Skill = 'binary-ninja-reverse'
            Purpose = 'Binary Ninja 商业逆向平台（GUI/Python API）'
            FixedVersion = 'manual-license'
            VersionArgs = @('--version')
            Fallbacks = @(
                [pscustomobject]@{ Type = 'command'; Value = 'binaryninja' },
                [pscustomobject]@{ Type = 'command'; Value = 'binaryninja-headless' },
                [pscustomobject]@{ Type = 'path'; Value = 'C:\Program Files\Vector35\BinaryNinja\binaryninja.exe' },
                [pscustomobject]@{ Type = 'path'; Value = (Join-ReverseOptionalPath -Path $localAppData -ChildPath 'Vector35\BinaryNinja\binaryninja.exe') },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path $userProfile 'Tools\BinaryNinja\binaryninja.exe') }
            )
        }
        [pscustomobject]@{
            Name = 'diec'
            Skill = 'reverse-engineering'
            Purpose = 'Detect It Easy CLI（加壳/编译器/熵/签名侦察，禁 GUI 时用这个）'
            VersionArgs = @('--version')
            Fallbacks = @(
                [pscustomobject]@{ Type = 'command'; Value = 'diec' },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path (Get-ReverseHackerRoot) 'DIE\diec.exe') },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path $userProfile 'Tools\DIE\diec.exe') }
            )
        }
        [pscustomobject]@{
            Name = 'die'
            Skill = 'reverse-engineering'
            Purpose = 'Detect It Easy GUI 版（会弹窗等交互，禁止经 bash 执行；改用 diec CLI）'
            FixedVersion = '3.21'
            VersionArgs = @()
            Fallbacks = @(
                [pscustomobject]@{ Type = 'command'; Value = 'die' },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path (Get-ReverseHackerRoot) 'DIE\die.exe') },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path $userProfile 'Tools\DIE\die.exe') }
            )
        }
        [pscustomobject]@{
            Name = 'tshark'
            Skill = 'protocol-reverse'
            Purpose = 'Wireshark CLI（pcap 解析/过滤/字段抽取，禁 GUI 时用这个）'
            VersionArgs = @('--version')
            Fallbacks = @(
                [pscustomobject]@{ Type = 'command'; Value = 'tshark' },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path (Get-ReverseHackerRoot) 'Wireshark\tshark.exe') },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path $userProfile 'Tools\Wireshark\tshark.exe') }
            )
        }
        [pscustomobject]@{
            Name = 'wireshark'
            Skill = 'protocol-reverse'
            Purpose = 'Wireshark GUI 版（会弹窗等交互，禁止经 bash 执行；改用 tshark CLI）'
            FixedVersion = '4.6.8'
            VersionArgs = @()
            Fallbacks = @(
                [pscustomobject]@{ Type = 'command'; Value = 'wireshark' },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path (Get-ReverseHackerRoot) 'Wireshark\Wireshark.exe') },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path $userProfile 'Tools\Wireshark\Wireshark.exe') }
            )
        }
        [pscustomobject]@{
            Name = 'x64dbg-headless'
            Skill = 'reverse-engineering'
            Purpose = 'x64dbg 无头控制台调试器（同引擎 CLI，支持 stdin 管道与 MCP 宿主联动）'
            FixedVersion = '0.0.2.5'
            VersionArgs = @('-help')
            Fallbacks = @(
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path (Get-ReverseHackerRoot) 'x64dbg\release\x64\headless.exe') }
            )
        }
        [pscustomobject]@{
            Name = 'x64dbg'
            Skill = 'reverse-engineering'
            Purpose = 'x64dbg GUI 调试器（仅供人工观察，自动化禁经 bash 执行；无头请用 x64dbg-headless 或 MCP）'
            FixedVersion = '0.0.2.5'
            VersionArgs = @()
            Fallbacks = @(
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path (Get-ReverseHackerRoot) 'x64dbg\release\x64\x64dbg.exe') },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path (Get-ReverseHackerRoot) 'x64dbg\release\x32\x32dbg.exe') }
            )
        }
        [pscustomobject]@{
            Name = 'scylla'
            Skill = 'reverse-engineering'
            Purpose = 'IAT 转储与脱壳修复（Scylla 独立 GUI 版，自动化时禁经 bash 启动）'
            FixedVersion = 'v0.9.8'
            VersionArgs = @()
            Fallbacks = @(
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path (Get-ReverseHackerRoot) 'Scylla\Scylla_x64.exe') },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path (Get-ReverseHackerRoot) 'Scylla\Scylla_x86.exe') }
            )
        }
        [pscustomobject]@{
            Name = 'cdb'
            Skill = 'reverse-engineering'
            Purpose = 'Windows 原生命令行调试器（WinDbg cdb CLI，支持 crash dump / 内核 / 用户态调试）'
            VersionArgs = @('-version')
            Fallbacks = @(
                [pscustomobject]@{ Type = 'command'; Value = 'cdb' },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path (Get-ReverseHackerRoot) 'WinKits\Debuggers\x64\cdb.exe') }
            )
        }
        [pscustomobject]@{
            Name = 'floss'
            Skill = 'reverse-engineering'
            Purpose = '静态与混淆/编码字符串提取（FLOSS v3.1.1，支持 .NET）'
            VersionArgs = @('--version')
            Fallbacks = @(
                [pscustomobject]@{ Type = 'command'; Value = 'floss' },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path (Get-ReverseHackerRoot) 'floss\floss.exe') }
            )
        }
        [pscustomobject]@{
            Name = 'PE-bear'
            Skill = 'reverse-engineering'
            Purpose = 'PE-bear GUI PE 编辑器（会弹窗，禁止经 bash 执行；无官方 CLI 替代）'
            FixedVersion = '0.7.2'
            VersionArgs = @()
            Fallbacks = @(
                [pscustomobject]@{ Type = 'command'; Value = 'PE-bear' },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path (Get-ReverseHackerRoot) 'PE-bear\PE-bear.exe') },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path $userProfile 'Tools\PE-bear\PE-bear.exe') }
            )
        }
        [pscustomobject]@{
            Name = '7z'
            Skill = 'reverse-engineering'
            Purpose = '7-Zip CLI（解包/固件归档/自解压程序拆解，本机可跑）'
            FixedVersion = '26.02'
            VersionArgs = @()
            Fallbacks = @(
                [pscustomobject]@{ Type = 'command'; Value = '7z' },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path (Get-ReverseHackerRoot) '7-Zip\7z.exe') },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path (Get-ReverseHackerRoot) '7z.exe') }
            )
        }
        [pscustomobject]@{
            Name = '7zFM'
            Skill = 'reverse-engineering'
            Purpose = '7-Zip File Manager GUI（会弹窗，禁止经 bash 执行；改用 7z CLI）'
            FixedVersion = '26.02'
            VersionArgs = @()
            Fallbacks = @(
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path (Get-ReverseHackerRoot) '7-Zip\7zFM.exe') }
            )
        }
        [pscustomobject]@{ Name = 'idat'; Skill = 'ida-reverse'; Purpose = 'IDA 文本模式控制台（无 GUI 的 IDA，批处理反编译可用）'; FixedVersion = '9.4.260713.a97520e5'
            VersionArgs = @()
            Fallbacks = @(
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path (Get-ReverseHackerRoot) 'IDA Professional 9.4\idat.exe') }
            )
        }
        [pscustomobject]@{ Name = 'ghidraRun'; Skill = 'ghidra-reverse'; Purpose = 'Ghidra 图形启动器（会弹窗，禁止经 bash；无头用 analyzeHeadless）'; FixedVersion = '12.1.3'
            VersionArgs = @()
            Fallbacks = @(
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path (Get-ReverseHackerRoot) 'Ghidra\ghidraRun.bat') }
            )
        }
        [pscustomobject]@{ Name = 'r2gui'; Skill = 'radare2'; Purpose = 'radare2 图形前端（Windows 版无独立 r2gui.exe，实际用 `r2 -g`；该调用会开窗，禁止经 bash）'
            VersionArgs = @()
            Fallbacks = @(
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path (Get-ReverseHackerRoot) 'radare2\bin\r2gui.exe') }
            )
        }
        [pscustomobject]@{ Name = 'Npcap'; Skill = 'protocol-reverse'; Purpose = 'Npcap 抓包驱动（当前仅有安装包，驱动未安装；装后 tshark 实时抓包才可用）'
            VersionArgs = @()
            Fallbacks = @(
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path (Get-ReverseHackerRoot) 'Npcap\npcap-installer.exe') }
            )
        }
        [pscustomobject]@{
            Name = 'frida'
            Skill = 'apk-reverse'
            Purpose = 'Frida 动态注入'
            FixedVersion = 'v0.5.0'
            VersionArgs = @()
            Fallbacks = @(
                [pscustomobject]@{ Type = 'command'; Value = 'frida' },
                [pscustomobject]@{ Type = 'path'; Value = (Join-ReverseOptionalPath -Path $appData -ChildPath 'Python\Python3xx\Scripts\frida.exe') }
            )
        }
        [pscustomobject]@{
            Name = 'frida-ps'
            Skill = 'apk-reverse'
            Purpose = 'Frida 进程枚举'
            FixedVersion = 'v0.5.0'
            VersionArgs = @()
            Fallbacks = @(
                [pscustomobject]@{ Type = 'command'; Value = 'frida-ps' },
                [pscustomobject]@{ Type = 'path'; Value = (Join-ReverseOptionalPath -Path $appData -ChildPath 'Python\Python3xx\Scripts\frida-ps.exe') }
            )
        }
        [pscustomobject]@{
            Name = 'r2'
            Skill = 'radare2'
            Purpose = 'radare2 主分析器'
            VersionArgs = @('-v')
            Fallbacks = @(
                [pscustomobject]@{ Type = 'command'; Value = 'r2' },
                [pscustomobject]@{ Type = 'command'; Value = 'radare2' },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path $userProfile 'Tools\radare2\bin\r2.bat') },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path $userProfile 'Tools\radare2\bin\radare2.exe') },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path $userProfile 'Tools\radare2\bin\r2.exe') },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path $userProfile 'Tools\radare2\r2.bat') },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path $userProfile 'Tools\radare2\radare2.exe') },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path $userProfile 'Tools\radare2\r2.exe') },
                [pscustomobject]@{ Type = 'path'; Value = 'C:\Tools\radare2\bin\r2.bat' },
                [pscustomobject]@{ Type = 'path'; Value = 'C:\Tools\radare2\bin\radare2.exe' },
                [pscustomobject]@{ Type = 'path'; Value = 'C:\Tools\radare2\bin\r2.exe' }
            )
        }
        [pscustomobject]@{
            Name = 'rabin2'
            Skill = 'radare2'
            Purpose = '二进制侦察'
            VersionArgs = @('-v')
            Fallbacks = @(
                [pscustomobject]@{ Type = 'command'; Value = 'rabin2' },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path $userProfile 'Tools\radare2\bin\rabin2.exe') },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path $userProfile 'Tools\radare2\rabin2.exe') },
                [pscustomobject]@{ Type = 'path'; Value = 'C:\Tools\radare2\bin\rabin2.exe' }
            )
        }
        [pscustomobject]@{
            Name = 'rasm2'
            Skill = 'radare2'
            Purpose = '汇编/反汇编'
            VersionArgs = @('-v')
            Fallbacks = @(
                [pscustomobject]@{ Type = 'command'; Value = 'rasm2' },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path $userProfile 'Tools\radare2\bin\rasm2.exe') },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path $userProfile 'Tools\radare2\rasm2.exe') },
                [pscustomobject]@{ Type = 'path'; Value = 'C:\Tools\radare2\bin\rasm2.exe' }
            )
        }
        [pscustomobject]@{
            Name = 'radiff2'
            Skill = 'radare2'
            Purpose = '二进制差分'
            VersionArgs = @('-v')
            Fallbacks = @(
                [pscustomobject]@{ Type = 'command'; Value = 'radiff2' },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path $userProfile 'Tools\radare2\bin\radiff2.exe') },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path $userProfile 'Tools\radare2\radiff2.exe') },
                [pscustomobject]@{ Type = 'path'; Value = 'C:\Tools\radare2\bin\radiff2.exe' }
            )
        }
        [pscustomobject]@{
            Name = 'rahash2'
            Skill = 'radare2'
            Purpose = '哈希与校验'
            VersionArgs = @('-v')
            Fallbacks = @(
                [pscustomobject]@{ Type = 'command'; Value = 'rahash2' },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path $userProfile 'Tools\radare2\bin\rahash2.exe') },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path $userProfile 'Tools\radare2\rahash2.exe') },
                [pscustomobject]@{ Type = 'path'; Value = 'C:\Tools\radare2\bin\rahash2.exe' }
            )
        }
        [pscustomobject]@{
            Name = 'rax2'
            Skill = 'radare2'
            Purpose = '进制与位运算转换'
            VersionArgs = @('-v')
            Fallbacks = @(
                [pscustomobject]@{ Type = 'command'; Value = 'rax2' },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path $userProfile 'Tools\radare2\bin\rax2.exe') },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path $userProfile 'Tools\radare2\rax2.exe') },
                [pscustomobject]@{ Type = 'path'; Value = 'C:\Tools\radare2\bin\rax2.exe' }
            )
        }
        [pscustomobject]@{
            Name = 'r2pm'
            Skill = 'radare2'
            Purpose = 'radare2 插件管理'
            VersionArgs = @('-v')
            Fallbacks = @(
                [pscustomobject]@{ Type = 'command'; Value = 'r2pm' },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path $userProfile 'Tools\radare2\bin\r2pm.exe') },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path $userProfile 'Tools\radare2\r2pm.exe') },
                [pscustomobject]@{ Type = 'path'; Value = 'C:\Tools\radare2\bin\r2pm.exe' }
            )
        }
        [pscustomobject]@{
            Name = 'r2xsql'
            Skill = 'radare2'
            Purpose = 'radare2 SQL 查询工具'
            VersionArgs = @('--version')
            Fallbacks = @(
                [pscustomobject]@{ Type = 'command'; Value = 'r2xsql' },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path $userProfile 'Tools\radare2\bin\r2xsql.exe') },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path $userProfile 'Tools\radare2\r2xsql.exe') },
                [pscustomobject]@{ Type = 'path'; Value = 'C:\Tools\radare2\bin\r2xsql.exe' }
            )
        }
        [pscustomobject]@{
            Name = 'r2xsql-full'
            Skill = 'radare2'
            Purpose = 'radare2 SQL 查询工具（完整版）'
            VersionArgs = @('--version')
            Fallbacks = @(
                [pscustomobject]@{ Type = 'command'; Value = 'r2xsql-full' },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path $userProfile 'Tools\radare2\bin\r2xsql-full.exe') },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path $userProfile 'Tools\radare2\r2xsql-full.exe') },
                [pscustomobject]@{ Type = 'path'; Value = 'C:\Tools\radare2\bin\r2xsql-full.exe' }
            )
        }
        [pscustomobject]@{
            Name = 'r2mcp'
            Skill = 'radare2'
            Purpose = 'radare2 MCP 协议分析'
            VersionArgs = @('-v')
            Fallbacks = @(
                [pscustomobject]@{ Type = 'command'; Value = 'r2mcp' },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path $userProfile 'Tools\radare2\bin\r2mcp.exe') },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path $userProfile 'Tools\radare2\r2mcp.exe') },
                [pscustomobject]@{ Type = 'path'; Value = 'C:\Tools\radare2\bin\r2mcp.exe' }
            )
        }
        [pscustomobject]@{
            Name = 'radius2'
            Skill = 'radare2'
            Purpose = 'radare2 符号执行与动态分析'
            VersionArgs = @('-v')
            Fallbacks = @(
                [pscustomobject]@{ Type = 'command'; Value = 'radius2' },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path $userProfile 'Tools\radare2\bin\radius2.exe') },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path $userProfile 'Tools\radare2\radius2.exe') },
                [pscustomobject]@{ Type = 'path'; Value = 'C:\Tools\radare2\bin\radius2.exe' }
            )
        }
        [pscustomobject]@{
            Name = 'python'
            Skill = 'reverse-engineering'
            Purpose = '辅助脚本执行'
            FixedVersion = 'v0.5.0'
            VersionArgs = @()
            Fallbacks = @(
                [pscustomobject]@{ Type = 'command'; Value = 'python' },
                [pscustomobject]@{ Type = 'command'; Value = 'python3' }
            )
        }
        [pscustomobject]@{
            Name = 'pip'
            Skill = 'reverse-engineering'
            Purpose = 'Python 包管理'
            FixedVersion = 'v0.5.0'
            VersionArgs = @()
            Fallbacks = @(
                [pscustomobject]@{ Type = 'command'; Value = 'pip' },
                [pscustomobject]@{ Type = 'command'; Value = 'pip3' }
            )
        }
        [pscustomobject]@{
            Name = 'node'
            Skill = 'js-reverse'
            Purpose = '运行 Node 侧 JS 复现与 MCP 客户端'
            FixedVersion = 'v0.5.0'
            VersionArgs = @()
            Fallbacks = @(
                [pscustomobject]@{ Type = 'command'; Value = 'node' }
            )
        }
        [pscustomobject]@{
            Name = 'npx'
            Skill = 'js-reverse'
            Purpose = '运行临时 npm 包与 MCP 入口'
            FixedVersion = 'v0.5.0'
            VersionArgs = @()
            Fallbacks = @(
                [pscustomobject]@{ Type = 'command'; Value = 'npx' }
            )
        }
        [pscustomobject]@{
            Name = 'jshookmcp'
            Skill = 'js-reverse'
            Purpose = '通过 npx 启动 @jshookmcp/jshook MCP（需 MCP 注册；npx 本身不代表该能力已安装）'
            FixedVersion = '@jshookmcp/jshook@0.3.4'
            VersionArgs = @()
            Fallbacks = @()
        }
        [pscustomobject]@{
            Name = 'reqable-mcp'
            Skill = 'pentest-tools'
            Purpose = '通过 npx 启动 Reqable 桌面客户端 MCP（需 MCP 注册与 Reqable；npx 本身不代表该能力已安装）'
            FixedVersion = 'reqable-mcp-server@1.0.1'
            VersionArgs = @()
            Fallbacks = @()
        }
        [pscustomobject]@{
            Name = 'xquik-mcp'
            Skill = 'threat-intelligence'
            Purpose = '公开 X/Twitter 威胁情报采集的远程 MCP（需客户端登记与 OAuth）'
            VersionArgs = @()
            Fallbacks = @()
        }
        [pscustomobject]@{
            Name = 'agent-browser'
            Skill = 'browser-automation'
            Purpose = '浏览器自动化（Playwright）：打开页面、点击、填表、爬取、截图'
            FixedVersion = 'v0.5.0'
            VersionArgs = @()
            Fallbacks = @(
                [pscustomobject]@{ Type = 'command'; Value = 'agent-browser' }
            )
        }
        [pscustomobject]@{
            Name = 'analyzeHeadless'
            Skill = 'reverse-engineering'
            Purpose = 'Ghidra 无头分析（免费 IDA 替代）'
            VersionArgs = @()
            Fallbacks = @(
                [pscustomobject]@{ Type = 'command'; Value = 'analyzeHeadless' },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path (Get-ReverseHackerRoot) 'Ghidra\support\analyzeHeadless.bat') },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path $userProfile 'Tools\ghidra\support\analyzeHeadless.bat') },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path $userProfile 'Tools\ghidra\ghidra_11.3_PUBLIC\support\analyzeHeadless.bat') }
            )
        }
        [pscustomobject]@{
            Name = 'pyghidra-mcp'
            Skill = 'ghidra-reverse'
            Purpose = 'PyGhidra MCP 静态反编译与符号分析（streamable-http 守护 127.0.0.1:9111，20 个工具；先跑 start-ghidra-mcp.bat）'
            FixedVersion = '0.2.7'
            VersionArgs = @()
            Fallbacks = @(
                [pscustomobject]@{ Type = 'command'; Value = 'pyghidra_mcp' }
                # 旧机硬编码 'C:\EXE\python\python.exe' 已移除：绝对路径跨机必错，交给上面的 command 探测负责。
                # 旧机硬编码 'C:\EXE\python\python.exe' 已移除：绝对路径跨机必错，交给 command 探测负责。
            )
        }
        [pscustomobject]@{
            Name = 'jeb-pro'
            Skill = 'apk-reverse'
            Purpose = 'JEB Pro 商业 Android / ARM 反编译器（需用户自备有效许可证）'
            VersionArgs = @()
            Fallbacks = @(
                [pscustomobject]@{ Type = 'command'; Value = 'jeb_wincon' },
                [pscustomobject]@{ Type = 'command'; Value = 'jeb' },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path $userProfile 'Tools\JEB\jeb_wincon.exe') }
            )
        }
        [pscustomobject]@{
            Name = 'playwright'
            Skill = 'browser-automation'
            Purpose = 'Playwright 浏览器引擎'
            FixedVersion = 'v0.5.0'
            VersionArgs = @()
            Fallbacks = @(
                [pscustomobject]@{ Type = 'command'; Value = 'playwright' },
                [pscustomobject]@{ Type = 'path'; Value = (Join-ReverseOptionalPath -Path $appData -ChildPath 'npm\playwright.ps1') }
            )
        }
        [pscustomobject]@{
            Name = 'proxycat'
            Skill = 'pentest-tools'
            Purpose = '代理池管理与轮换'
            FixedVersion = 'v0.5.0'
            VersionArgs = @()
            Fallbacks = @(
                [pscustomobject]@{ Type = 'command'; Value = 'proxycat' }
            )
        }
        [pscustomobject]@{
            Name = 'seclists'
            Skill = 'pentest-tools'
            Purpose = 'Security wordlists'
            VersionArgs = @()
            Fallbacks = @(
                [pscustomobject]@{ Type = 'directory'; Value = (Join-Path $userProfile 'Tools\SecLists') },
                [pscustomobject]@{ Type = 'directory'; Value = 'C:\Tools\SecLists' },
                [pscustomobject]@{ Type = 'directory'; Value = '/usr/share/seclists' }
            )
        }
        [pscustomobject]@{
            Name = 'pentestswarm'
            Skill = 'pentest-tools'
            Purpose = '群体智能自主渗透与 MCP 执行'
            FixedVersion = 'v0.5.0'
            VersionArgs = @()
            Fallbacks = @(
                [pscustomobject]@{ Type = 'command'; Value = 'pentestswarm' }
            )
        }
        [pscustomobject]@{
            Name = 'nmap'
            Skill = 'pentest-tools'
            Purpose = '端口扫描与服务识别'
            FixedVersion = 'v0.5.0'
            VersionArgs = @()
            Fallbacks = @(
                [pscustomobject]@{ Type = 'command'; Value = 'nmap' },
                [pscustomobject]@{ Type = 'path'; Value = 'C:\Program Files (x86)\Nmap\nmap.exe' },
                [pscustomobject]@{ Type = 'path'; Value = 'C:\Program Files\Nmap\nmap.exe' }
            )
        }
        [pscustomobject]@{
            Name = 'binwalk'
            Skill = 'firmware-pentest'
            Purpose = '固件提取与分析'
            VersionArgs = @('--version')
            Fallbacks = @(
                [pscustomobject]@{ Type = 'command'; Value = 'binwalk' }
            )
        }
        [pscustomobject]@{
            Name = 'yara'
            Skill = 'malware-analysis'
            Purpose = '恶意软件规则匹配引擎'
            VersionArgs = @('--version')
            Fallbacks = @(
                [pscustomobject]@{ Type = 'command'; Value = 'yara' },
                [pscustomobject]@{ Type = 'path'; Value = 'C:\Program Files\yara\yara.exe' }
            )
        }
        [pscustomobject]@{
            Name = 'capa'
            Skill = 'malware-analysis'
            Purpose = '恶意能力与特征自动检测（FLARE capa，基于规则匹配）'
            VersionArgs = @('--version')
            Fallbacks = @(
                [pscustomobject]@{ Type = 'command'; Value = 'capa' },
                # 旧机硬编码 'C:\EXE\python\Scripts\capa.exe' 已移除：绝对路径跨机必错，
                # 交给上面的 command 探测与 localAppData 候选负责。
                [pscustomobject]@{ Type = 'path'; Value = (Join-ReverseOptionalPath -Path $localAppData -ChildPath 'Programs\Python\Python312\Scripts\capa.exe') }
            )
        }
        [pscustomobject]@{
            Name = 'pe-sieve'
            Skill = 'malware-analysis'
            Purpose = '进程内存扫描与 inline hook/注入检测（PE-sieve）'
            VersionArgs = @('/version')
            Fallbacks = @(
                [pscustomobject]@{ Type = 'command'; Value = 'pe-sieve' },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path (Get-ReverseHackerRoot) 'pe-sieve\pe-sieve.exe') }
            )
        }
        [pscustomobject]@{
            Name = 'pwntools'
            Skill = 'reverse-engineering'
            Purpose = 'CTF pwn 利用开发框架'
            FixedVersion = 'v0.5.0'
            VersionArgs = @()
            Fallbacks = @(
                [pscustomobject]@{ Type = 'command'; Value = 'pwntools' },
                [pscustomobject]@{ Type = 'command'; Value = 'pwn' }
            )
        }
        [pscustomobject]@{
            Name = 'bkcrack'
            Skill = 'reverse-engineering'
            Purpose = 'CTF ZIP/PKZIP ZipCrypto 已知明文攻击'
            FixedVersion = 'v1.8.1'
            VersionArgs = @('--version')
            Fallbacks = @(
                [pscustomobject]@{ Type = 'command'; Value = 'bkcrack' },
                [pscustomobject]@{ Type = 'path'; Value = (Join-Path $userProfile 'Tools\bkcrack\bkcrack.exe') },
                [pscustomobject]@{ Type = 'path'; Value = 'C:\Tools\bkcrack\bkcrack.exe' }
            )
        }
    )
}

function Get-ReverseSkillRoot {
    [CmdletBinding()]
    param()

    # 规则 1：显式配置优先，否则由脚本自身位置推导。
    # 技能包总是相对自己的位置找资源（bootstrap-manifest.json:180,229 的 %SKILL_ROOT%、
    # ToolDiscovery.ps1:799 拼 manifest 路径），所以 $PSScriptRoot 自推导就是最稳的探测：
    # 不依赖任何必须手写的配置文件，移动目录 / 换机器自动跟随。
    if (-not [string]::IsNullOrWhiteSpace($env:REVERSE_SKILL_ROOT)) {
        $override = [System.IO.Path]::GetFullPath($env:REVERSE_SKILL_ROOT)
        if (Test-Path -LiteralPath $override -PathType Container) {
            return $override
        }
        # 与 Get-ReverseHackerRoot 同口径：显式配置设了但不落地 -> 不采用、不报错，
        # 继续按自推导走（规则 1 第 2 条「其值【实际存在】才用」）。
        Write-Warning "REVERSE_SKILL_ROOT 指向的目录不存在，已忽略并改用自推导：$override"
    }

    $derived = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
    if (Test-Path -LiteralPath $derived -PathType Container) {
        return $derived
    }

    throw ("SKILL_ROOT 未解析：推导路径 $derived 不存在（PSScriptRoot=$PSScriptRoot）。" +
           "处置分支：(a) 技能包目录被移动或裁剪不完整 -> 检查 skills/ 是否齐全；" +
           "(b) 需要指向别处的技能包 -> 设 REVERSE_SKILL_ROOT 后重跑。")
}

function Resolve-ReversePathTemplate {
    [CmdletBinding()]
    param(
        [AllowNull()]
        [string]$Value
    )

    if ([string]::IsNullOrWhiteSpace($Value)) {
        return $Value
    }

    $resolved = $Value
    $replacements = @{
        '%USERPROFILE%' = (Get-ReverseUserProfilePath)
        '%LOCALAPPDATA%' = [string]([Environment]::GetEnvironmentVariable('LOCALAPPDATA'))
        '%APPDATA%' = [string]([Environment]::GetEnvironmentVariable('APPDATA'))
        '%TEMP%' = [string]([Environment]::GetEnvironmentVariable('TEMP'))
        '%SKILL_ROOT%' = Get-ReverseSkillRoot
    }

    foreach ($key in $replacements.Keys) {
        $resolved = $resolved.Replace($key, $replacements[$key])
    }

    return $resolved
}

function ConvertTo-ReverseHashtable {
    [CmdletBinding()]
    param(
        [AllowNull()]
        $InputObject
    )

    if ($null -eq $InputObject) {
        return $null
    }
    if ($InputObject -is [string] -or $InputObject.GetType().IsPrimitive -or $InputObject -is [decimal]) {
        return $InputObject
    }
    if ($InputObject -is [System.Collections.IDictionary]) {
        $map = [ordered]@{}
        foreach ($key in $InputObject.Keys) {
            $map[[string]$key] = ConvertTo-ReverseHashtable -InputObject $InputObject[$key]
        }
        return $map
    }
    if ($InputObject -is [System.Management.Automation.PSCustomObject]) {
        $map = [ordered]@{}
        foreach ($property in $InputObject.PSObject.Properties) {
            $map[$property.Name] = ConvertTo-ReverseHashtable -InputObject $property.Value
        }
        return $map
    }
    if ($InputObject -is [System.Collections.IEnumerable] -and -not ($InputObject -is [string])) {
        $items = @()
        foreach ($item in $InputObject) {
            $items += ,(ConvertTo-ReverseHashtable -InputObject $item)
        }
        return $items
    }

    return $InputObject
}

function Read-ReverseJsonAsHashtable {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        return $null
    }

    $json = Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json
    return ConvertTo-ReverseHashtable -InputObject $json
}

function Get-ReverseBootstrapManifestPath {
    [CmdletBinding()]
    param()

    return Join-Path (Get-ReverseSkillRoot) 'scripts\bootstrap-manifest.json'
}

function Get-ReverseBootstrapCatalog {
    [CmdletBinding()]
    param()

    if ((Get-Variable -Name 'ReverseBootstrapCatalog' -Scope Script -ErrorAction SilentlyContinue) -and $script:ReverseBootstrapCatalog) {
        return $script:ReverseBootstrapCatalog
    }

    $path = Get-ReverseBootstrapManifestPath
    if (-not (Test-Path -LiteralPath $path)) {
        $script:ReverseBootstrapCatalog = @()
        return $script:ReverseBootstrapCatalog
    }

    $json = Get-Content -LiteralPath $path -Raw -Encoding UTF8 | ConvertFrom-Json
    $catalog = @()
    foreach ($capability in @($json.capabilities)) {
        $clone = [pscustomobject]@{}
        foreach ($property in $capability.PSObject.Properties) {
            $value = $property.Value
            if ($value -is [string]) {
                $value = Resolve-ReversePathTemplate -Value $value
            }
            elseif ($value -is [System.Collections.IEnumerable] -and -not ($value -is [string])) {
                $items = @()
                foreach ($item in $value) {
                    if ($item -is [string]) {
                        $items += Resolve-ReversePathTemplate -Value $item
                    }
                    else {
                        $items += $item
                    }
                }
                $value = $items
            }
            elseif ($null -ne $value -and $value -is [System.Management.Automation.PSCustomObject]) {
                $propCount = @($value.PSObject.Properties).Count
                if ($propCount -gt 0) {
                    $map = [ordered]@{}
                    foreach ($subProperty in $value.PSObject.Properties) {
                        $subValue = $subProperty.Value
                        if ($subValue -is [string]) {
                            $subValue = Resolve-ReversePathTemplate -Value $subValue
                        }
                        $map[$subProperty.Name] = $subValue
                    }
                    $value = [pscustomobject]$map
                }
            }
            Add-Member -InputObject $clone -NotePropertyName $property.Name -NotePropertyValue $value
        }
        $catalog += $clone
    }

    $script:ReverseBootstrapCatalog = $catalog
    return $script:ReverseBootstrapCatalog
}

function Get-ReverseBootstrapDefinition {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    return Get-ReverseBootstrapCatalog | Where-Object { $_.name -eq $Name } | Select-Object -First 1
}

function Get-ClaudeMcpConfigPath {
    [CmdletBinding()]
    param()

    if (-not [string]::IsNullOrWhiteSpace($env:CLAUDE_MCP_CONFIG)) {
        return $env:CLAUDE_MCP_CONFIG
    }
    $profilePath = Get-ReverseUserProfilePath
    return Join-Path (Join-Path $profilePath '.claude') 'mcp.json'
}

function Get-CodexConfigPath {
    [CmdletBinding()]
    param()

    if (-not [string]::IsNullOrWhiteSpace($env:CODEX_CONFIG_PATH)) {
        return $env:CODEX_CONFIG_PATH
    }
    $profilePath = Get-ReverseUserProfilePath
    return Join-Path (Join-Path $profilePath '.codex') 'config.toml'
}

function Get-ClaudeMcpServerNames {
    [CmdletBinding()]
    param()

    $configPath = Get-ClaudeMcpConfigPath
    if (-not (Test-Path -LiteralPath $configPath)) {
        return @()
    }

    try {
        $json = Get-Content -LiteralPath $configPath -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($null -eq $json.mcpServers) {
            return @()
        }
        return @($json.mcpServers.PSObject.Properties.Name)
    }
    catch {
        return @()
    }
}

function Get-CodexMcpServerNames {
    [CmdletBinding()]
    param()

    $configPath = Get-CodexConfigPath
    if (-not (Test-Path -LiteralPath $configPath)) {
        return @()
    }

    $pattern = '^\[mcp_servers\.([^\].]+)\]\s*$'
    $names = @()
    foreach ($match in Select-String -LiteralPath $configPath -Pattern $pattern) {
        if ($match.Matches.Count -gt 0) {
            $names += $match.Matches[0].Groups[1].Value
        }
    }

    return @($names | Sort-Object -Unique)
}

function Get-PiMcpConfigPath {
    [CmdletBinding()]
    param()

    if (-not [string]::IsNullOrWhiteSpace($env:PI_AGENT_DIR)) {
        return Join-Path $env:PI_AGENT_DIR 'mcp.json'
    }
    if (-not [string]::IsNullOrWhiteSpace($env:PI_HOME)) {
        return Join-Path (Join-Path $env:PI_HOME 'agent') 'mcp.json'
    }
    $profilePath = Get-ReverseUserProfilePath
    return Join-Path (Join-Path $profilePath '.pi\agent') 'mcp.json'
}

function Get-PiMcpServerNames {
    [CmdletBinding()]
    param()

    $configPath = Get-PiMcpConfigPath
    if (-not (Test-Path -LiteralPath $configPath)) {
        return @()
    }

    try {
        $json = Get-Content -LiteralPath $configPath -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($null -eq $json.mcpServers) {
            return @()
        }
        return @($json.mcpServers.PSObject.Properties.Name)
    }
    catch {
        return @()
    }
}

function Get-ReverseMcpServerDetail {
    [CmdletBinding()]
    param()

    $details = @()
    foreach ($source in @(
            [pscustomobject]@{ Host = 'claude'; Names = @(Get-ClaudeMcpServerNames) },
            [pscustomobject]@{ Host = 'codex'; Names = @(Get-CodexMcpServerNames) },
            [pscustomobject]@{ Host = 'pi'; Names = @(Get-PiMcpServerNames) })) {
        foreach ($name in $source.Names) {
            $details += [pscustomobject]@{ Host = $source.Host; Name = $name }
        }
    }
    return @($details)
}

function Get-ReverseMcpServerNames {
    [CmdletBinding()]
    param()

    return @((Get-ReverseMcpServerDetail).Name | Sort-Object -Unique)
}

function Test-ReverseTcpPort {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [int]$Port,
        [string]$TargetHost = '127.0.0.1'
    )

    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $async = $client.BeginConnect($TargetHost, $Port, $null, $null)
        $connected = $async.AsyncWaitHandle.WaitOne(1000, $false)
        if (-not $connected) {
            $client.Close()
            return $false
        }
        $client.EndConnect($async)
        $client.Close()
        return $true
    }
    catch {
        return $false
    }
}

function Test-ReverseMcpHttp {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [int]$Port,

        [string]$TargetHost = '127.0.0.1',

        [int]$TimeoutMs = 3000
    )

    try {
        $body = '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
        $uri = "http://${TargetHost}:$Port/mcp"
        $req = [System.Net.HttpWebRequest]::Create($uri)
        $req.Method = 'POST'
        $req.ContentType = 'application/json'
        $req.Timeout = $TimeoutMs
        $req.ReadWriteTimeout = $TimeoutMs
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($body)
        $req.ContentLength = $bytes.Length
        $reqStream = $req.GetRequestStream()
        $reqStream.Write($bytes, 0, $bytes.Length)
        $reqStream.Close()
        $resp = $req.GetResponse()
        $statusCode = [int]$resp.StatusCode
        $resp.Close()
        return $statusCode -eq 200
    }
    catch {
        return $false
    }
}

function Add-ReverseProcessPath {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    if ([string]::IsNullOrWhiteSpace($Path) -or -not (Test-Path -LiteralPath $Path -PathType Container)) {
        return
    }

    $separator = [System.IO.Path]::PathSeparator
    $entries = @($env:PATH -split [regex]::Escape([string]$separator)) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
    if ($entries -contains $Path) {
        return
    }

    if ([string]::IsNullOrWhiteSpace($env:PATH)) {
        $env:PATH = $Path
    }
    else {
        $env:PATH = "$Path$separator$env:PATH"
    }
}

function Resolve-ReverseCommandCandidate {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    $commands = @(Get-Command -Name $Name -All -ErrorAction SilentlyContinue)
    if ($commands.Count -eq 0) {
        return $null
    }

    if ($Name -in @('npm', 'npx', 'pnpm', 'yarn', 'corepack')) {
        $cmdShim = $commands | Where-Object { $_.CommandType -eq 'Application' -and $_.Source -match '\.cmd$' } | Select-Object -First 1
        if ($cmdShim) {
            return $cmdShim
        }

        $application = $commands | Where-Object { $_.CommandType -eq 'Application' } | Select-Object -First 1
        if ($application) {
            return $application
        }
    }

    return ($commands | Select-Object -First 1)
}

function Get-ReverseCapabilityState {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    $definition = Get-ReverseBootstrapDefinition -Name $Name
    if ($null -eq $definition) {
        return $null
    }

    $registered = $false
    if ($definition.PSObject.Properties['mcpNames']) {
        $registeredNames = Get-ReverseMcpServerNames
        foreach ($candidate in @($definition.mcpNames)) {
            if ($registeredNames -contains $candidate) {
                $registered = $true
                break
            }
        }
    }

    $serviceOnline = $false
    $mcpHttpVerified = $false
    if ($definition.PSObject.Properties['servicePort'] -and $definition.servicePort) {
        $serviceOnline = Test-ReverseTcpPort -Port ([int]$definition.servicePort)
        # If TCP passes, attempt HTTP MCP protocol-level handshake for higher confidence
        if ($serviceOnline) {
            $mcpHttpVerified = Test-ReverseMcpHttp -Port ([int]$definition.servicePort)
        }
    }

    $toolReady = $false
    try {
        $toolSpec = Resolve-ReverseToolSpec -Name $Name
        $toolReady = [bool]$toolSpec.Available
    }
    catch {
        $toolReady = $false
    }

    $runtimeReady = $toolReady
    if ($definition.bootstrapKind -eq 'npm-mcp') {
        try {
            $runtimeSpec = Resolve-ReverseToolSpec -Name 'npx'
            $runtimeReady = [bool]$runtimeSpec.Available
        }
        catch {
            $runtimeReady = $false
        }
    }

    $verificationMode = if ($definition.PSObject.Properties['verificationMode']) { [string]$definition.verificationMode } else { '' }
    $ready = $toolReady
    if ($definition.PSObject.Properties['mcpNames']) {
        switch ($verificationMode) {
            'registration-only' {
                $ready = $registered
            }
            'service-and-registration' {
                $ready = $registered -and $serviceOnline
            }
            'service-or-registration' {
                $ready = $registered -or $serviceOnline
            }
            default {
                if ($definition.bootstrapKind -eq 'npm-mcp') {
                    $ready = $registered -and $runtimeReady
                }
                else {
                    $ready = $registered -or $toolReady
                }
            }
        }
    }

    return [pscustomobject]@{
        Name = $definition.name
        BootstrapKind = $definition.bootstrapKind
        CanAutoInstall = [bool]$definition.canAutoInstall
        DocsUrl = [string]$definition.docsUrl
        Ready = $ready
        Registered = $registered
        RuntimeAvailable = $runtimeReady
        ServiceOnline = $serviceOnline
        McpHttpVerified = $mcpHttpVerified
    }
}

function Get-ReverseToolDefinition {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    $definition = Get-ReverseToolCatalog | Where-Object { $_.Name -eq $Name } | Select-Object -First 1
    if ($null -eq $definition) {
        throw "Unknown reverse tool: $Name"
    }

    $bootstrap = Get-ReverseBootstrapDefinition -Name $Name
    if ($null -ne $bootstrap) {
        foreach ($property in $bootstrap.PSObject.Properties) {
            if (-not $definition.PSObject.Properties[$property.Name]) {
                Add-Member -InputObject $definition -NotePropertyName $property.Name -NotePropertyValue $property.Value
            }
        }
    }

    return $definition
}

function Resolve-ReverseToolSpec {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    $definition = Get-ReverseToolDefinition -Name $Name
    $fixedVersion = if ($definition.PSObject.Properties['FixedVersion']) { [string]$definition.FixedVersion } else { '' }

    foreach ($candidate in $definition.Fallbacks) {
        if (-not $candidate.PSObject.Properties['Value'] -or [string]::IsNullOrWhiteSpace([string]$candidate.Value)) {
            continue
        }

        switch ($candidate.Type) {
            'command' {
                $cmd = Resolve-ReverseCommandCandidate -Name $candidate.Value
                if ($null -ne $cmd) {
                    return [pscustomobject]@{
                        Name = $definition.Name
                        Skill = $definition.Skill
                        Purpose = $definition.Purpose
                        Available = $true
                        IsExecutable = $true
                        IsDirectory = $false
                        Source = 'Get-Command'
                        ResolvedPath = $cmd.Source
                        Command = $cmd.Source
                        PrefixArgs = @()
                        VersionArgs = $definition.VersionArgs
                        FixedVersion = $fixedVersion
                    }
                }
            }
            'path' {
                if (Test-Path -LiteralPath $candidate.Value) {
                    Add-ReverseProcessPath -Path (Split-Path -Path $candidate.Value -Parent)
                    return [pscustomobject]@{
                        Name = $definition.Name
                        Skill = $definition.Skill
                        Purpose = $definition.Purpose
                        Available = $true
                        IsExecutable = $true
                        IsDirectory = $false
                        Source = 'FallbackPath'
                        ResolvedPath = $candidate.Value
                        Command = $candidate.Value
                        PrefixArgs = @()
                        VersionArgs = $definition.VersionArgs
                        FixedVersion = $fixedVersion
                    }
                }
            }
            'directory' {
                if (Test-Path -LiteralPath $candidate.Value -PathType Container) {
                    return [pscustomobject]@{
                        Name = $definition.Name
                        Skill = $definition.Skill
                        Purpose = $definition.Purpose
                        Available = $true
                        IsExecutable = $false
                        IsDirectory = $true
                        Source = 'FallbackDirectory'
                        ResolvedPath = $candidate.Value
                        Command = ''
                        PrefixArgs = @()
                        VersionArgs = @()
                        FixedVersion = $fixedVersion
                    }
                }
            }
            'java-jar' {
                if (Test-Path -LiteralPath $candidate.Value) {
                    $java = Resolve-ReverseToolSpec -Name 'java'
                    if (-not $java.Available -or [string]::IsNullOrWhiteSpace([string]$java.Command)) {
                        continue
                    }
                    return [pscustomobject]@{
                        Name = $definition.Name
                        Skill = $definition.Skill
                        Purpose = $definition.Purpose
                        Available = $true
                        IsExecutable = $true
                        IsDirectory = $false
                        Source = 'FallbackJavaJar'
                        ResolvedPath = $candidate.Value
                        Command = $java.Command
                        PrefixArgs = @('-jar', $candidate.Value)
                        VersionArgs = @('-jar', $candidate.Value, '--version')
                        FixedVersion = $fixedVersion
                    }
                }
            }
        }
    }

    # 统一fallback根：D:\HACKER。写在所有显式候选之后，优先级最低，
    # 目的是救回「旧条目盘符写错」的漏网情况（BUG-01：ida 七条候选全指 C:\Program Files）。
    $hackerRoot = Get-ReverseHackerRoot
    if (-not [string]::IsNullOrWhiteSpace($hackerRoot)) {
        foreach ($shape in @(
                (Join-Path (Join-Path $hackerRoot $definition.Name) ($definition.Name + '.exe')),
                (Join-Path (Join-Path $hackerRoot $definition.Name) ($definition.Name + '.bat')),
                (Join-Path (Join-Path (Join-Path $hackerRoot $definition.Name) 'bin') ($definition.Name + '.exe')),
                (Join-Path $hackerRoot ($definition.Name + '.exe')))) {
            if (-not (Test-Path -LiteralPath $shape)) {
                continue
            }
            Add-ReverseProcessPath -Path (Split-Path -Path $shape -Parent)
            return [pscustomobject]@{
                Name = $definition.Name
                Skill = $definition.Skill
                Purpose = $definition.Purpose
                Available = $true
                IsExecutable = $true
                IsDirectory = $false
                Source = 'HackerRootProbe'
                ResolvedPath = $shape
                Command = $shape
                PrefixArgs = @()
                VersionArgs = $definition.VersionArgs
                FixedVersion = $fixedVersion
            }
        }
    }

    return [pscustomobject]@{
        Name = $definition.Name
        Skill = $definition.Skill
        Purpose = $definition.Purpose
        Available = $false
        IsExecutable = $false
        IsDirectory = $false
        Source = 'Missing'
        ResolvedPath = ''
        Command = ''
        PrefixArgs = @()
        VersionArgs = $definition.VersionArgs
        FixedVersion = $fixedVersion
    }
}

function Get-ReverseToolVersion {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [pscustomobject]$Spec
    )

    if (-not $Spec.Available) {
        return ''
    }
    # FixedVersion 是已实测的固定事实，优先于 VersionArgs 探测。
    # 否则 GUI 类条目（VersionArgs 为空，因为跑 --version 会弹窗）永远拿不到版本号。
    if ($Spec.PSObject.Properties['FixedVersion'] -and -not [string]::IsNullOrWhiteSpace([string]$Spec.FixedVersion)) {
        return [string]$Spec.FixedVersion
    }
    if ([string]::IsNullOrWhiteSpace([string]$Spec.Command) -or @($Spec.VersionArgs).Count -eq 0) {
        return ''
    }

    try {
        $rawLines = & $Spec.Command @($Spec.VersionArgs) 2>&1 | Select-Object -First 10
        foreach ($line in $rawLines) {
            $text = ([string]$line).Trim()
            if ($text -and $text -notmatch '^Module manifest file error' -and $text -notmatch '^\s*->\s*Invalid line') {
                return $text
            }
        }
        return ''
    }
    catch {
        return ''
    }
}

function Invoke-ReverseTool {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,

        [Parameter()]
        [string[]]$Arguments = @()
    )

    $spec = Resolve-ReverseToolSpec -Name $Name
    if (-not $spec.Available) {
        throw "Missing required CLI tool: $Name"
    }
    if ($spec.PSObject.Properties['IsExecutable'] -and -not [bool]$spec.IsExecutable) {
        throw "Tool '$Name' is available at '$($spec.ResolvedPath)' but is not an executable command."
    }
    if ([string]::IsNullOrWhiteSpace([string]$spec.Command)) {
        throw "Tool '$Name' is available but does not expose an executable command."
    }

    & $spec.Command @($spec.PrefixArgs + $Arguments)
    return $LASTEXITCODE
}

function Get-ReverseToolReport {
    [CmdletBinding()]
    param(
        [string[]]$Names
    )

    $selectedNames = if ($null -ne $Names -and @($Names).Count -gt 0) { $Names } else { (Get-ReverseToolCatalog).Name }

    foreach ($name in $selectedNames) {
        $spec = Resolve-ReverseToolSpec -Name $name
        $capabilityState = Get-ReverseCapabilityState -Name $name
        [pscustomobject]@{
            Name = $spec.Name
            Skill = $spec.Skill
            Purpose = $spec.Purpose
            Available = $spec.Available
            IsExecutable = if ($spec.PSObject.Properties['IsExecutable']) { $spec.IsExecutable } else { -not [string]::IsNullOrWhiteSpace([string]$spec.Command) }
            IsDirectory = if ($spec.PSObject.Properties['IsDirectory']) { $spec.IsDirectory } else { $false }
            ResolvedPath = $spec.ResolvedPath
            Source = $spec.Source
            Version = Get-ReverseToolVersion -Spec $spec
            BootstrapKind = if ($capabilityState) { $capabilityState.BootstrapKind } else { '' }
            CanAutoInstall = if ($capabilityState) { $capabilityState.CanAutoInstall } else { $false }
            DocsUrl = if ($capabilityState) { $capabilityState.DocsUrl } else { '' }
            Ready = if ($capabilityState) { $capabilityState.Ready } else { $spec.Available }
            McpRegistered = if ($capabilityState) { $capabilityState.Registered } else { $false }
            ServiceOnline = if ($capabilityState) { $capabilityState.ServiceOnline } else { $false }
            McpHttpVerified = if ($capabilityState) { $capabilityState.McpHttpVerified } else { $false }
        }
    }
}
