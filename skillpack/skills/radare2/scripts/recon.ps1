param(
    [Parameter(Mandatory = $true)]
    [string]$TargetPath,

    [int]$StringsLimit = 40,

    [int]$ImportsLimit = 80,

    [switch]$RunAnalysis
)

# 强制当前脚本使用 UTF-8 输出，尽量减少中文标题乱码。
[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$ErrorActionPreference = 'Stop'

# 工具定位统一走探测层：env -> PATH -> D:\Tools\_map.json 别名 -> 工具根递归。
# 只测量，不判定、不缓存；查不到就是没装，由调用方报错。见 skills/scripts/lib/Bootstrap.ps1。
. (Join-Path $PSScriptRoot '..\..\scripts\lib\Bootstrap.ps1')

$bootstrapScript = Join-Path $PSScriptRoot '..\..\scripts\bootstrap-reverse.ps1'

function Get-RequiredToolSpec {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    $spec = Resolve-ReverseToolSpec -Name $Name
    if (-not $spec.Available) {
        # Attempt auto-bootstrap
        if (Test-Path -LiteralPath $bootstrapScript) {
            Write-Output "INFO: $Name not found, attempting auto-bootstrap..."
            & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $bootstrapScript -Capability @($Name) -SkipRefresh
            $spec = Resolve-ReverseToolSpec -Name $Name
        }
        if (-not $spec.Available) {
            throw "缺少命令：$Name — 自动安装失败，请手动安装。参考: https://github.com/radareorg/radare2"
        }
    }
    return $spec
}

function Write-Section {
    param(
        [Parameter(Mandatory = $true)]
    [string]$Title
    )

    # 用固定分段标题，方便人看，也方便后续 grep。
    ""
    "=== $Title ==="
}

function Invoke-R2Section {
    param(
        [Parameter(Mandatory = $true)][string]$Title,
        [Parameter(Mandatory = $true)][string]$Command,
        [int]$Limit = 0,
        [switch]$Analyze,
        # 这一段「有内容」本身就是判据（基本信息段必须非空，见下面 ★ 说明）。
        [switch]$MustBeNonEmpty
    )

    Write-Section -Title $Title
    $r2Args = @($r2.PrefixArgs)
    if ($Analyze) { $r2Args += '-A' }
    # ★ 2026-10-16：**不要**在目标前加 `--`。本机实测（r2 6.2.4）radare2 把 `--` 当成
    #   文件名本身：`r2 -q -c ij -- notepad.exe` 给 `{}`、`iI` 一个字都不输出，而退出码
    #   仍是 0（-q 下打不开目标是静默的）。旧写法产出的"侦察报告"因此是**空壳却报成功**，
    #   比报错更坏。去掉 `--` 后同一条命令给出真实 PE 信息。
    #   代价是失去"目标名像选项"的防护 —— 可接受：$target 经 Resolve-Path 规范化成绝对
    #   路径，一定以盘符开头，不可能被当成选项。
    $r2Args += @('-q', '-c', $Command, $target)
    $out = @(& $r2.Command $r2Args)
    # ★ 2026-10-16（D4）：旧写法调完 r2 直接往下走，**不查退出码** ——
    #   r2 起不来 / 目标读不了 时，报告只是"少打印几段"，人看到的仍是"成功"。
    #   失败被当成成功是这一族缺陷里最坏的一类，所以这里显式判并当场抛。
    $rc = $LASTEXITCODE
    if ($rc -ne 0) {
        throw "r2 调用失败（exit $rc）：$Command —— 侦察报告不完整，不再往下走"
    }
    # ★ 退出码还不够：目标**没被打开**时 r2 也是 rc=0 + 零输出（实测见上）。基本信息段
    #   （iI）在打开任何文件时都必然有内容，所以拿「零输出」当功能性判据，堵住静默空报告。
    if ($MustBeNonEmpty -and $out.Count -eq 0) {
        throw "r2 对 '$Command' 零输出（exit 0）—— 目标没被真正打开：这不是'空结果'，是'没跑成'"
    }
    if ($Limit -gt 0) { $out | Select-Object -First $Limit } else { $out }
}

$r2 = Get-RequiredToolSpec -Name 'r2'

# 将输入路径规范化成绝对路径，避免 r2 在相对路径下歧义解析。
$resolvedPath = Resolve-Path -LiteralPath $TargetPath
$target = $resolvedPath.Path

"目标文件: $target"

# 注意：Windows 下 rabin2.exe 与 radare2.exe 为同一多路复用二进制且缺少 argv[0] 分发，
# 调用 rabin2 -I 会直接执行目标！因此全面使用 r2 -q -c '...' 安全调用。
Invoke-R2Section -Title '基本信息' -Command 'iI' -MustBeNonEmpty
Invoke-R2Section -Title '节区' -Command 'iS'
Invoke-R2Section -Title '导入' -Command 'ii' -Limit $ImportsLimit
Invoke-R2Section -Title '导出' -Command 'iE'
Invoke-R2Section -Title '字符串' -Command 'iz' -Limit $StringsLimit

if ($RunAnalysis) {
    Invoke-R2Section -Title '函数与入口分析' -Command 's entry0;afl;iz;ii;q' -Analyze
}
