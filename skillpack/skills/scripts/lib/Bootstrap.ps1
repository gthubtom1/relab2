#requires -Version 5

<#
  Bootstrap.ps1 —— 安装器依赖的最小工具集（取代旧的 lib/ToolDiscovery.ps1，72 KB → 本文件）。

  设计纪律（不要在后续修改中破坏）：
  1. 本文件只做两件事：**测量**（工具在不在、在哪）与**读取随包 manifest**（机器无关的安装说明）。
  2. 本文件**不产出绿/红结论**，不缓存本机状态到磁盘，不维护工具候选路径表。
     「装好了没有」由调用方根据测量结果自己判断，不要在这里合并成一个 Ready 布尔值。
  3. 工具定位是四级递进，**命中即停**：env → PATH → _map.json 别名 → 工具根递归兜底。
     工具根默认 D:\Tools\（可用 REVERSE_TOOL_ROOT 覆盖）。找不到就是没装，
     返回空值让调用方报错，**绝不伪造路径、绝不猜**。
  4. 装法说明以 skillpack/skills/TOOLS.md 为准；bootstrap-manifest.json 是它的机器可读副本。
#>

# --------------------------------------------------------------------------
# 进程环境自愈（不重启也能用）
# --------------------------------------------------------------------------
# 事故背景 2026-10-08：本机工具整体从 D:\HACKER\ 迁移到 D:\Tools\，注册表 User PATH
# 已更新，但**已运行的进程树仍持有启动时的旧快照**（38 条 D:\HACKER\ 死条目，目录
# 已不存在）。于是 Get-Command 对 diec/r2/idat/ghidraRun 全部返回空，而四级探测的
# 第 2 级正是靠 Get-Command —— 智能体据此误判「本机缺工具」并直接停手。
# 语义纪律：
#   1) 只增不减：已在进程 PATH 里的条目保持原序在前（保住调用方刻意的临时覆盖），
#      注册表新增的追加在后；不存在的目录直接丢弃（它不可能命中任何 exe）。
#   2) 幂等：同进程只做一次，-Force 可强制重跑。
#   3) 永不抛异常：本文件所有探测函数都受这条约束。
#   4) 不写注册表：只改当前进程内存环境，不碰持久化配置。
function Sync-ReverseProcessPath {
    [CmdletBinding()]
    param([switch]$Force)

    if ($script:ReversePathSynced -and -not $Force) { return $false }
    $script:ReversePathSynced = $true

    try {
        $current = @($env:PATH -split ';' | Where-Object { $_ })
        $seen = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
        foreach ($e in $current) { [void]$seen.Add($e.TrimEnd('\')) }

        $merged = New-Object 'System.Collections.Generic.List[string]'
        foreach ($e in $current) {
            if (Test-Path -LiteralPath $e -PathType Container -ErrorAction SilentlyContinue) {
                $merged.Add($e)
            }
        }

        foreach ($scope in @('Machine', 'User')) {
            $registryPath = [Environment]::GetEnvironmentVariable('PATH', $scope)
            if ([string]::IsNullOrWhiteSpace($registryPath)) { continue }
            foreach ($e in ($registryPath -split ';')) {
                if ([string]::IsNullOrWhiteSpace($e)) { continue }
                $trimmed = $e.Trim().TrimEnd('\')
                if ($seen.Contains($trimmed)) { continue }
                [void]$seen.Add($trimmed)
                if (Test-Path -LiteralPath $trimmed -PathType Container -ErrorAction SilentlyContinue) {
                    $merged.Add($trimmed)
                }
            }
        }

        if ($merged.Count -eq 0) { return $false }
        $env:PATH = ($merged -join ';')
        return $true
    } catch {
        return $false
    }
}

# DOTNET_ROOT 自愈：SDK 装在非默认位置（本机 D:\Tools\runtime\dotnet8）时，
# dotnet tool install -g 装出的 apphost（ilspycmd.exe）找不到 runtime，直接报
# "You must install .NET to run this application." —— 工具本身是好的。
# 必须探测式取值（Get-Command dotnet 的所在目录），禁止写死任何盘符路径。
function Sync-ReverseDotnetRoot {
    [CmdletBinding()]
    param([switch]$Force)

    if ($script:ReverseDotnetRootDone -and -not $Force) { return $false }
    $script:ReverseDotnetRootDone = $true

    try {
        if ($env:DOTNET_ROOT -and (Test-Path -LiteralPath $env:DOTNET_ROOT -PathType Container -ErrorAction SilentlyContinue)) {
            return $false
        }
        $dotnet = Get-Command dotnet -ErrorAction SilentlyContinue | Select-Object -First 1
        if (-not ($dotnet -and $dotnet.Source)) { return $false }
        $root = [System.IO.Path]::GetDirectoryName($dotnet.Source)
        if (-not (Test-Path -LiteralPath $root -PathType Container -ErrorAction SilentlyContinue)) { return $false }
        $env:DOTNET_ROOT = $root
        return $true
    } catch {
        return $false
    }
}

# 统一入口：探测层定位工具前调它，调用方无需关心环境是否刷新过。
function Sync-ReverseEnvironment {
    [CmdletBinding()]
    param()
    $pathFixed = Sync-ReverseProcessPath
    $dotnetFixed = Sync-ReverseDotnetRoot
    return [PSCustomObject]@{
        PathSynced       = $pathFixed
        DotnetRootSynced = $dotnetFixed
    }
}

function Get-ReverseUserProfilePath {
    [CmdletBinding()]
    param()
    $p = [Environment]::GetEnvironmentVariable('USERPROFILE')
    if (-not [string]::IsNullOrWhiteSpace($p) -and (Test-Path -LiteralPath $p -PathType Container)) {
        return $p
    }
    return $env:USERPROFILE
}

function Get-ReverseSkillRoot {
    [CmdletBinding()]
    param()

    # 返回的目录必须**真的含 scripts\bootstrap-manifest.json** —— 这是唯一的判据。
    # 环境变量允许指向三种位置，逐个试：
    #   ① skills 根（…\skills）            -> 直接命中
    #   ② 包根 / 仓库根（…\ 、…\skillpack） -> 再试 <它>\skills
    # 全都不含 manifest 时**不许**退回「只要目录存在就返回」——
    # 那会让 Get-ReverseBootstrapManifestPath 拼出一个不存在的路径，
    # 能力清单静默解析失败（2026-10-09 实测：REVERSE_SKILL_ROOT=<包根> 时踩到）。
    if (-not [string]::IsNullOrWhiteSpace($env:REVERSE_SKILL_ROOT)) {
        $override = [System.IO.Path]::GetFullPath($env:REVERSE_SKILL_ROOT)
        foreach ($cand in @($override,
                            (Join-Path $override 'skills'),
                            (Join-Path $override 'skillpack\skills'))) {
            if (Test-Path -LiteralPath (Join-Path $cand 'scripts\bootstrap-manifest.json')) {
                return [System.IO.Path]::GetFullPath($cand)
            }
        }
        Write-Warning ("REVERSE_SKILL_ROOT=$override 下面找不到 scripts\bootstrap-manifest.json，" +
                       "已忽略并改用自推导（设成 skills 根、包根或仓库根都可以）。")
    }

    $derived = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
    if (Test-Path -LiteralPath $derived -PathType Container) { return $derived }

    throw ("SKILL_ROOT 未解析：推导路径 $derived 不存在（PSScriptRoot=$PSScriptRoot）。" +
           "处置：检查 skills/ 是否齐全；或设 REVERSE_SKILL_ROOT 指向正确位置后重跑。")
}

function Resolve-ReversePathTemplate {
    [CmdletBinding()]
    param([AllowNull()][string]$Value)

    if ([string]::IsNullOrWhiteSpace($Value)) { return $Value }

    $resolved = $Value
    $replacements = @{
        '%USERPROFILE%' = (Get-ReverseUserProfilePath)
        '%LOCALAPPDATA%' = [string]([Environment]::GetEnvironmentVariable('LOCALAPPDATA'))
        '%APPDATA%'      = [string]([Environment]::GetEnvironmentVariable('APPDATA'))
        '%TEMP%'         = [string]([Environment]::GetEnvironmentVariable('TEMP'))
        '%SKILL_ROOT%'   = (Get-ReverseSkillRoot)
    }
    foreach ($key in $replacements.Keys) { $resolved = $resolved.Replace($key, $replacements[$key]) }
    return $resolved
}

# ── 工具根与别名表 ────────────────────────────────────────────────────────────

function Get-ReverseToolRoot {
    [CmdletBinding()]
    param()
    if (-not [string]::IsNullOrWhiteSpace($env:REVERSE_TOOL_ROOT)) { return $env:REVERSE_TOOL_ROOT }
    return 'D:\Tools'
}

# ── 运行期环境自愈（防止继承父进程遗留的死路径污染） ─────────────────────────
$toolRootCurrent = Get-ReverseToolRoot
if (Test-Path -LiteralPath $toolRootCurrent -PathType Container) {
    # 1. 修复 JAVA_HOME
    $jdkCandidate = Join-Path $toolRootCurrent 'runtime\jdk21\jdk-21.0.12.1+1'
    if ((-not $env:JAVA_HOME -or -not (Test-Path -LiteralPath $env:JAVA_HOME -PathType Container)) -and (Test-Path -LiteralPath $jdkCandidate)) {
        $env:JAVA_HOME = $jdkCandidate
    }
    # 2. 修复 DOTNET_ROOT
    $dotnetCandidate = Join-Path $toolRootCurrent 'runtime\dotnet8'
    if ((-not $env:DOTNET_ROOT -or -not (Test-Path -LiteralPath $env:DOTNET_ROOT -PathType Container)) -and (Test-Path -LiteralPath $dotnetCandidate)) {
        $env:DOTNET_ROOT = $dotnetCandidate
    }
    # 3. 修复 GOROOT
    $goCandidate = Join-Path $toolRootCurrent 'runtime\go\go'
    if ((-not $env:GOROOT -or -not (Test-Path -LiteralPath $env:GOROOT -PathType Container)) -and (Test-Path -LiteralPath $goCandidate)) {
        $env:GOROOT = $goCandidate
    }
    # 4. 确保 D:\Tools\cli 在会话 PATH 前端
    $cliCandidate = Join-Path $toolRootCurrent 'cli'
    if (Test-Path -LiteralPath $cliCandidate) {
        $pathList = $env:PATH -split ';'
        if ($pathList -notcontains $cliCandidate) {
            $env:PATH = "$cliCandidate;$($env:PATH)"
        }
    }
}

function Get-ReverseToolMap {
    [CmdletBinding()]
    param()

    if ((Get-Variable -Name 'ReverseToolMap' -Scope Script -ErrorAction SilentlyContinue)) {
        return $script:ReverseToolMap
    }

    $script:ReverseToolMap = $null

    # 1. 优先加载本地工具根下的 _map.json（本机覆盖层）
    $root = Get-ReverseToolRoot
    $localMap = $null
    if (-not [string]::IsNullOrWhiteSpace($root) -and (Test-Path -LiteralPath $root -PathType Container -ErrorAction SilentlyContinue)) {
        $localPath = Join-Path $root '_map.json'
        if (Test-Path -LiteralPath $localPath -PathType Leaf -ErrorAction SilentlyContinue) {
            try {
                $localMap = Get-Content -LiteralPath $localPath -Raw -Encoding UTF8 | ConvertFrom-Json
            } catch {
                Write-Warning "_map.json 本地覆盖表解析失败: $localPath"
            }
        }
    }

    # 2. 仓内默认知识库 toolmap.default.json
    $defaultPath = Join-Path $PSScriptRoot 'toolmap.default.json'
    $defaultMap = $null
    if (Test-Path -LiteralPath $defaultPath -PathType Leaf -ErrorAction SilentlyContinue) {
        try {
            $defaultMap = Get-Content -LiteralPath $defaultPath -Raw -Encoding UTF8 | ConvertFrom-Json
        } catch { }
    }

    # 3. 合并或择优：本地有则以本地为准（保留其 aliases/deny），默认垫底补充 twins 等知识
    if ($null -ne $localMap) {
        $script:ReverseToolMap = $localMap
        if ($defaultMap -and $defaultMap.PSObject.Properties['twins'] -and -not $script:ReverseToolMap.PSObject.Properties['twins']) {
            Add-Member -InputObject $script:ReverseToolMap -NotePropertyName 'twins' -NotePropertyValue $defaultMap.twins
        }
    } elseif ($null -ne $defaultMap) {
        $script:ReverseToolMap = $defaultMap
    }

    return $script:ReverseToolMap
}

# deny 规则：某工具 id 在某路径上是否禁止使用（防误命中捆绑运行时，例如 IDA 自带的裸 Python）
function Test-ReverseToolDenied {
    [CmdletBinding()]
    param([string]$ToolId, [string]$FullPath)

    $map = Get-ReverseToolMap
    if ($null -eq $map -or -not $map.PSObject.Properties['deny']) { return $false }

    $root = (Get-ReverseToolRoot).TrimEnd('\') + '\'
    $rel = if ($FullPath.StartsWith($root, [StringComparison]::OrdinalIgnoreCase)) {
        $FullPath.Substring($root.Length)
    } else { $FullPath }

    foreach ($rule in @($map.deny)) {
        if (-not ($rule.toolIds -contains $ToolId)) { continue }
        foreach ($pat in @($rule.pathPatterns)) {
            if ($rel -like $pat -or $FullPath -like $pat) { return $true }
        }
    }
    return $false
}

<#
  从命令路径推断版本提示 —— **不启动任何进程**。

  为什么需要：换机时拿到 `idat` 只知道路径里写着「IDA Pro 9.3」，
  但 `Available/Command/Via` 三个字段都无法表达「这是 8.3 还是 9.3」。
  2026-10-10 的 9.4 → 9.3 换版就是这个坑的实例：
  文档里所有写 `IDA Professional 9.4` 的别名全部指向已删目录，却报Available=True。

  判据顺序（都不执行目标程序）：
    1. 路径里的显式版本串：IDA Pro 9.3 / x64dbg-2024 / python-3.12
    2. 路径里的大版本号目录：\9.3\、\v8.3\
    3. 拿不到就返回 $null —— **绝不猜**，调用方据此知道「版本未知，需实跑 --version」
#>
function Get-ReverseToolVersionHint {
    param([string]$Command)
    if (-not $Command) { return $null }
    $p = $Command -replace '/', '\'

    # 形如 "IDA Pro 9.3" / "IDA Pro 9.4" / "x64dbg v8.3" / "python-3.12"
    $m = [regex]::Match($p, '(?i)(?<name>[\w\.\-\s]{2,24}?)[-\s]?v?(?<ver>\d+\.\d+(?:\.\d+)?)(?=[\\\._]|$)')
    if ($m.Success) {
        return ('{0} {1}' -f $m.Groups['name'].Value.Trim(), $m.Groups['ver'].Value)
    }
    # 路径里独立的大版本目录：\9.3\ / \v8.3\
    $m2 = [regex]::Match($p, '\\v?(?<ver>\d+\.\d+(?:\.\d+)?)(\\|$)')
    if ($m2.Success) { return $m2.Groups['ver'].Value }
    return $null
}

function New-ReverseToolSpec {
    param([string]$Name, [string]$Command, [string]$Via)
    return [pscustomobject]@{
        Name = $Name; Available = $true; Command = $Command; Via = $Via; PrefixArgs = @()
        VersionHint = (Get-ReverseToolVersionHint -Command $Command)
    }
}

function New-ReverseUnavailableSpec {
    param([string]$Name)
    return [pscustomobject]@{
        Name = $Name; Available = $false; Command = $null; Via = $null; PrefixArgs = @()
        VersionHint = $null
    }
}

<#
  多命中时选哪一个。

  不能按路径字母序选 ——「IDA 8.3」与「IDA 9.4」深度相同，字母序会选中 8.3（旧的）。
  策略：同深度优先取**修改时间最新**的（解压时间越晚通常是越新的版本）；
  再同深度同时间则取文件名最长的（版本号更长的一般更新）。
  仍无法区分时，调用方应把 Via=scan 当作低可信度处理。
#>
function Select-ReverseNewestHit {
    param([object[]]$Hits)

    if (-not $Hits -or $Hits.Count -eq 0) { return $null }
    if ($Hits.Count -eq 1) { return $Hits[0] }

    $root = (Get-ReverseToolRoot).TrimEnd('\') + '\'
    return ($Hits | Sort-Object -Property `
        @{ Expression = { $d = $_.FullName; if ($d.StartsWith($root, [StringComparison]::OrdinalIgnoreCase)) { $d.Substring($root.Length) } else { $d } } },
        @{ Expression = { ($_.FullName -split '\\').Count } },
        @{ Expression = { $_.LastWriteTimeUtc } ; Descending = $true },
        @{ Expression = { $_.Name.Length } ; Descending = $true } |
        Select-Object -First 1)
}

<#
  工具定位 —— 纯测量。四级递进，命中即停：

    1. 环境变量：同名大写变量指向全路径，且文件真实存在
    2. PATH：问操作系统。系统安装优先于工具根里的捆绑副本
    3. _map.json 显式别名：解决「目录名 ≠ 工具名」「同名多份要指定哪份」
    4. 工具根递归查找同名可执行文件：兜底，浅路径优先，受 deny 规则约束

  Via 字段说明命中来源，便于判断可信度：env / PATH / map / map-exec / scan。
  仍找不到 = 没装，返回 Available=$false —— 调用方负责报错。
#>
function Resolve-ReverseToolSpec {
    [CmdletBinding()]
    param([Parameter(Mandatory = $true)][string]$Name)

    # 本函数必须**永不抛异常**：调用方（recon.ps1 / decode.ps1 / bootstrap-reverse.ps1）
    # 全都设了 $ErrorActionPreference='Stop'，一次非终止错误就会冲出整个脚本。
    # 任何探测失败一律降级成 Available=$false，由调用方报错。
    #
    # 0) 环境自愈：进程可能持有启动时的旧 PATH 快照（本机 2026-10-08 事故：工具从
    #    D:\HACKER\ 迁到 D:\Tools\，注册表已改但进程未刷新）。不刷新的话下面第 2 级
    #    Get-Command 会全部返回空，进而让调用方误判「本机缺工具」。幂等且不抛异常。
    try { [void](Sync-ReverseEnvironment) } catch { }

    # 1) 环境变量显式指定（设了但文件不在 -> 忽略，不静默沿用）
    $envKey = $Name.ToUpperInvariant().Replace('-', '_')
    $envPath = [Environment]::GetEnvironmentVariable($envKey)
    if ($envPath -and (Test-Path -LiteralPath $envPath -PathType Leaf -ErrorAction SilentlyContinue)) {
        return New-ReverseToolSpec -Name $Name -Command $envPath -Via 'env'
    }

    # 2) PATH —— 系统安装优先。deny 规则同样适用（否则捆绑运行时能绕过 deny）。
    foreach ($n in @($Name, "$Name.exe", "$Name.bat", "$Name.cmd", "$Name.ps1")) {
        $c = Get-Command $n -ErrorAction SilentlyContinue | Select-Object -First 1
        if (-not ($c -and $c.Source)) { continue }

        # 排除 Windows 应用执行别名（微软商店 stub）：
        # 那是个真实存在但一运行就弹商店、退出码非零的 0 字节占位符。
        # 命中它 = 「绿 + 一个跑不起来的路径」，比报缺失更糟。
        if ($c.Source -like '*\WindowsApps\*') { continue }
        try {
            if ((Get-Item -LiteralPath $c.Source -ErrorAction SilentlyContinue).Length -eq 0) { continue }
        } catch { continue }
        if (Test-ReverseToolDenied -ToolId $Name -FullPath $c.Source) { continue }

        return New-ReverseToolSpec -Name $Name -Command $c.Source -Via 'PATH'
    }

    $root = Get-ReverseToolRoot
    if ([string]::IsNullOrWhiteSpace($root)) { return New-ReverseUnavailableSpec -Name $Name }
    if (-not (Test-Path -LiteralPath $root -PathType Container -ErrorAction SilentlyContinue)) {
        return New-ReverseUnavailableSpec -Name $Name
    }
    $map = Get-ReverseToolMap

    # 3) _map.json 显式别名
    if ($map -and $map.PSObject.Properties['aliases']) {
        $entry = $map.aliases.PSObject.Properties[$Name]
        if ($entry) {
            $alias = $entry.Value
            foreach ($rel in @($alias.prefer)) {
                if (-not $rel) { continue }
                $full = Join-Path $root $rel
                if ((Test-Path -LiteralPath $full -PathType Leaf -ErrorAction SilentlyContinue) -and
                    -not (Test-ReverseToolDenied -ToolId $Name -FullPath $full)) {
                    return New-ReverseToolSpec -Name $Name -Command $full -Via 'map'
                }
            }
            # 别名声明了 exec 但没给可用路径 -> 在工具根里找那个 exe
            if ($alias.PSObject.Properties['exec'] -and $alias.exec) {
                $hits = @(Get-ChildItem -LiteralPath $root -Recurse -Filter $alias.exec -File -ErrorAction SilentlyContinue |
                        Where-Object { -not (Test-ReverseToolDenied -ToolId $Name -FullPath $_.FullName) })
                if ($hits.Count -gt 0) {
                    $pick = Select-ReverseNewestHit -Hits $hits
                    return New-ReverseToolSpec -Name $Name -Command $pick.FullName -Via 'map-exec'
                }
            }
        }
    }
    # 4) 工具根递归兜底（同名可执行文件）
    foreach ($ext in @('exe', 'bat', 'cmd')) {
        $hits = @(Get-ChildItem -LiteralPath $root -Recurse -Filter "$Name.$ext" -File -ErrorAction SilentlyContinue |
                Where-Object { -not (Test-ReverseToolDenied -ToolId $Name -FullPath $_.FullName) })
        if ($hits.Count -gt 0) {
            $pick = Select-ReverseNewestHit -Hits $hits
            $via = if ($hits.Count -gt 1) { 'scan-ambiguous' } else { 'scan' }
            return New-ReverseToolSpec -Name $Name -Command $pick.FullName -Via $via
        }
    }

    # 5) 孪生推导兜底（知识库驱动）：如果查的是主程序/GUI 名，自动查其已知的 CLI/无头孪生
    if ($map -and $map.PSObject.Properties['twins']) {
        $twinEntry = $map.twins.PSObject.Properties[$Name.ToLowerInvariant()]
        if ($twinEntry -and $twinEntry.Value.cliTwin -and ($twinEntry.Value.cliTwin -ne $Name)) {
            $twinSpec = Resolve-ReverseToolSpec -Name $twinEntry.Value.cliTwin
            if ($twinSpec.Available) {
                return New-ReverseToolSpec -Name $Name -Command $twinSpec.Command -Via ('twin->' + $twinSpec.Via)
            }
        }
    }

    return New-ReverseUnavailableSpec -Name $Name
}

# ── 随包 manifest 读取（机器无关） ────────────────────────────────────────────

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
        Write-Warning "bootstrap-manifest.json 不存在：$path —— 无法解析能力清单。"
        $script:ReverseBootstrapCatalog = @()
        return $script:ReverseBootstrapCatalog
    }

    $json = Get-Content -LiteralPath $path -Raw -Encoding UTF8 | ConvertFrom-Json
    $catalog = @()
    foreach ($capability in @($json.capabilities)) {
        $clone = [ordered]@{}
        foreach ($property in $capability.PSObject.Properties) {
            $value = $property.Value
            if ($value -is [string]) {
                $value = Resolve-ReversePathTemplate -Value $value
            }
            elseif ($value -is [System.Collections.IEnumerable] -and -not ($value -is [string])) {
                $value = @($value | ForEach-Object {
                    if ($_ -is [string]) { Resolve-ReversePathTemplate -Value $_ } else { $_ }
                })
            }
            $clone[$property.Name] = $value
        }
        $catalog += [pscustomobject]$clone
    }

    $script:ReverseBootstrapCatalog = $catalog
    return $script:ReverseBootstrapCatalog
}

function Get-ReverseBootstrapDefinition {
    [CmdletBinding()]
    param([Parameter(Mandatory = $true)][string]$Name)
    return Get-ReverseBootstrapCatalog | Where-Object { $_.name -eq $Name } | Select-Object -First 1
}

<#
  能力现状 —— 返回**事实**，不返回结论。
  调用方拿到这些字段自己决定怎么表述；本函数不生成 Ready 绿/红判定。
#>
function Measure-ReverseCapability {
    [CmdletBinding()]
    param([Parameter(Mandatory = $true)][string]$Name)

    $definition = Get-ReverseBootstrapDefinition -Name $Name
    if ($null -eq $definition) {
        Write-Warning "manifest 中没有能力 '$Name' —— 无从测量，请检查 bootstrap-manifest.json。"
        return $null
    }

    $toolPath = $null
    try {
        $spec = Resolve-ReverseToolSpec -Name $Name
        $toolPath = $spec.Command
    }
    catch {
        $toolPath = $null
    }

    $runtimeAvailable = $null
    if ($definition.PSObject.Properties['bootstrapKind'] -and $definition.bootstrapKind -eq 'npm-mcp') {
        try {
            $runtimeSpec = Resolve-ReverseToolSpec -Name 'npx'
            $runtimeAvailable = [bool]$runtimeSpec.Available
        }
        catch {
            $runtimeAvailable = $false
        }
    }

    return [pscustomobject]@{
        Name             = $definition.name
        BootstrapKind    = $definition.bootstrapKind
        CanAutoInstall   = [bool]$definition.canAutoInstall
        DocsUrl          = [string]$definition.docsUrl
        ToolPath         = $toolPath          # 有值=已装且定位到了；空=没装
        RuntimeAvailable = $runtimeAvailable  # npm 类能力才有意义
        VerificationMode = if ($definition.PSObject.Properties['verificationMode']) { [string]$definition.verificationMode } else { '' }
    }
}

# ── MCP 宿主与通道 ────────────────────────────────────────────────────────────

<#
  MCP 宿主配置文件定位 —— 环境变量优先（便于测试隔离），否则用各宿主默认位置。
  不猜测、不创建目录：路径解析与实际写入是调用方的事。
#>
function Get-ClaudeMcpConfigPath {
    [CmdletBinding()]
    param()
    if (-not [string]::IsNullOrWhiteSpace($env:CLAUDE_MCP_CONFIG)) { return $env:CLAUDE_MCP_CONFIG }
    return Join-Path (Join-Path (Get-ReverseUserProfilePath) '.claude') 'mcp.json'
}

function Get-CodexConfigPath {
    [CmdletBinding()]
    param()
    if (-not [string]::IsNullOrWhiteSpace($env:CODEX_CONFIG_PATH)) { return $env:CODEX_CONFIG_PATH }
    return Join-Path (Join-Path (Get-ReverseUserProfilePath) '.codex') 'config.toml'
}

function Get-PiMcpConfigPath {
    [CmdletBinding()]
    param()
    if (-not [string]::IsNullOrWhiteSpace($env:PI_AGENT_DIR)) { return Join-Path $env:PI_AGENT_DIR 'mcp.json' }
    if (-not [string]::IsNullOrWhiteSpace($env:PI_HOME)) { return Join-Path (Join-Path $env:PI_HOME 'agent') 'mcp.json' }
    return Join-Path (Join-Path (Get-ReverseUserProfilePath) '.pi\agent') 'mcp.json'
}
function Get-OmpMcpConfigPath {
    [CmdletBinding()]
    param()
    if (-not [string]::IsNullOrWhiteSpace($env:OMP_AGENT_DIR)) { return Join-Path $env:OMP_AGENT_DIR 'mcp.json' }
    return Join-Path (Join-Path (Get-ReverseUserProfilePath) '.omp\agent') 'mcp.json'
}

<#
  JSON -> 有序字典。用于读宿主 MCP 配置时保留字段顺序（回写时不打乱用户的文件）。
#>
function ConvertTo-ReverseHashtable {
    [CmdletBinding()]
    param([AllowNull()]$InputObject)

    if ($null -eq $InputObject) { return $null }
    if ($InputObject -is [string] -or $InputObject.GetType().IsPrimitive -or $InputObject -is [decimal]) { return $InputObject }

    if ($InputObject -is [System.Collections.IDictionary]) {
        $map = [ordered]@{}
        foreach ($key in $InputObject.Keys) { $map[[string]$key] = ConvertTo-ReverseHashtable -InputObject $InputObject[$key] }
        return $map
    }
    if ($InputObject -is [System.Management.Automation.PSCustomObject]) {
        $map = [ordered]@{}
        foreach ($property in $InputObject.PSObject.Properties) { $map[$property.Name] = ConvertTo-ReverseHashtable -InputObject $property.Value }
        return $map
    }
    if ($InputObject -is [System.Collections.IEnumerable] -and -not ($InputObject -is [string])) {
        $items = @()
        foreach ($item in $InputObject) { $items += ,(ConvertTo-ReverseHashtable -InputObject $item) }
        return $items
    }
    return $InputObject
}

function Read-ReverseJsonAsHashtable {
    [CmdletBinding()]
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) { return $null }
    $json = Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json
    return ConvertTo-ReverseHashtable -InputObject $json
}

<#
  本机回环端口探活 —— 纯测量。
  「这个 MCP 服务起没起」是事实，不是结论：返回 $true/$false，调用方自己决定怎么表述。
  1 秒超时，绝不阻塞等待（等端口会挂死整条会话）。
#>
function Test-ReverseTcpPort {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][int]$Port,
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

<#
  全机逆向环境快照生成器（自适应与自愈枢纽）
  扫描本机常用逆向工具可用性、CLI 孪生状态、MCP 服务探活状态，
  输出结构化对象，并可选落盘保存为缓存。换机跑一次即可知晓全盘就绪度。
#>
function Export-ReverseEnvironmentSnapshot {
    [CmdletBinding()]
    param(
        [string]$OutFile = '',
        [string[]]$ToolList = @(
            'ida', 'idat', 'ghidra', 'analyzeHeadless', 'x64dbg', 'x32dbg',
            'die', 'diec', 'r2', 'radare2', 'wireshark', 'tshark',
            'dnSpy', 'dnSpy.Console', 'de4dot', 'ilspycmd', 'upx',
            'java', 'javac', 'dotnet', 'go', 'git', 'python', 'npm', 'npx'
        )
    )

    $tools = [ordered]@{}
    foreach ($t in $ToolList) {
        $spec = Resolve-ReverseToolSpec -Name $t
        $tools[$t] = [ordered]@{
            Available = [bool]$spec.Available
            Command   = $spec.Command
            Via       = $spec.Via
        }
    }

    $mcpStates = [ordered]@{}
    $mcpChecks = @(
        @{ Name = 'pyghidra-mcp'; Port = 9111 },
        @{ Name = 'idalib-mcp';  Port = 13337 }
    )
    foreach ($m in $mcpChecks) {
        $online = Test-ReverseTcpPort -Port $m.Port
        $mcpStates[$m.Name] = [ordered]@{
            Port   = $m.Port
            Online = $online
        }
    }

    $snapshot = [ordered]@{
        GeneratedAt = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
        ToolRoot    = Get-ReverseToolRoot
        SkillRoot   = Get-ReverseSkillRoot
        Tools       = $tools
        Mcp         = $mcpStates
    }

    if ($OutFile) {
        $dir = Split-Path $OutFile -Parent
        if ($dir -and -not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
        $snapshot | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $OutFile -Encoding UTF8
    }

    return [pscustomobject]$snapshot
}