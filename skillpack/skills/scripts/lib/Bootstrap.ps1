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

    # 技能包相对自己的位置找资源：支持直接传入技能包根或仓库根，自动解析出 skills/ 目录
    if (-not [string]::IsNullOrWhiteSpace($env:REVERSE_SKILL_ROOT)) {
        $override = [System.IO.Path]::GetFullPath($env:REVERSE_SKILL_ROOT)
        if (Test-Path -LiteralPath (Join-Path $override 'scripts\bootstrap-manifest.json')) {
            return $override
        }
        $subSkills = Join-Path $override 'skillpack\skills'
        if (Test-Path -LiteralPath (Join-Path $subSkills 'scripts\bootstrap-manifest.json')) {
            return [System.IO.Path]::GetFullPath($subSkills)
        }
        if (Test-Path -LiteralPath $override -PathType Container) { return $override }
        Write-Warning "REVERSE_SKILL_ROOT 指向的目录不存在，已忽略并改用自推导：$override"
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

function Get-ReverseToolMap {
    [CmdletBinding()]
    param()

    if ((Get-Variable -Name 'ReverseToolMap' -Scope Script -ErrorAction SilentlyContinue)) {
        return $script:ReverseToolMap
    }

    $script:ReverseToolMap = $null

    # 先验证根目录再用 —— 对不存在的盘符调 Join-Path 会往错误流写「找不到驱动器」，
    # 在目标机没有 D 盘（或 REVERSE_TOOL_ROOT 填错）时污染调用方输出，
    # 新 AI 会把这段噪声误读成故障。查不到就安静返回 null。
    $root = Get-ReverseToolRoot
    if ([string]::IsNullOrWhiteSpace($root)) { return $null }
    if (-not (Test-Path -LiteralPath $root -PathType Container -ErrorAction SilentlyContinue)) {
        return $null
    }

    $path = Join-Path $root '_map.json'
    if (-not (Test-Path -LiteralPath $path -PathType Leaf -ErrorAction SilentlyContinue)) {
        return $null
    }

    try {
        $script:ReverseToolMap = Get-Content -LiteralPath $path -Raw -Encoding UTF8 | ConvertFrom-Json
    }
    catch {
        # 解析失败要看得见 —— 这是真故障，不能静默吞掉
        Write-Warning "_map.json 解析失败，已忽略别名表（工具仍可走 PATH 与递归兜底）：$path"
        Write-Warning ("  原因: " + $_.Exception.Message)
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

function New-ReverseToolSpec {
    param([string]$Name, [string]$Command, [string]$Via)
    return [pscustomobject]@{
        Name = $Name; Available = $true; Command = $Command; Via = $Via; PrefixArgs = @()
    }
}

function New-ReverseUnavailableSpec {
    param([string]$Name)
    return [pscustomobject]@{
        Name = $Name; Available = $false; Command = $null; Via = $null; PrefixArgs = @()
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

    # 4) 工具根递归兜底（同名可执行文件）。这是**最低可信度**的一级：
    #    命中多份时由 Select-ReverseNewestHit 按「浅→新→长」挑，调用方应把 Via=scan
    #    当作待确认信号（实跑一次版本输出）。
    foreach ($ext in @('exe', 'bat', 'cmd')) {
        $hits = @(Get-ChildItem -LiteralPath $root -Recurse -Filter "$Name.$ext" -File -ErrorAction SilentlyContinue |
                Where-Object { -not (Test-ReverseToolDenied -ToolId $Name -FullPath $_.FullName) })
        if ($hits.Count -gt 0) {
            $pick = Select-ReverseNewestHit -Hits $hits
            $via = if ($hits.Count -gt 1) { 'scan-ambiguous' } else { 'scan' }
            return New-ReverseToolSpec -Name $Name -Command $pick.FullName -Via $via
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