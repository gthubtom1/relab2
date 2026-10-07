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

$r2 = Get-RequiredToolSpec -Name 'r2'

# 将输入路径规范化成绝对路径，避免 r2 在相对路径下歧义解析。
$resolvedPath = Resolve-Path -LiteralPath $TargetPath
$target = $resolvedPath.Path

"目标文件: $target"

# 注意：Windows 下 rabin2.exe 与 radare2.exe 为同一多路复用二进制且缺少 argv[0] 分发，
# 调用 rabin2 -I 会直接执行目标！因此全面使用 r2 -q -c '...' 安全调用。
Write-Section -Title '基本信息'
& $r2.Command @($r2.PrefixArgs + @('-q', '-c', 'iI', '--', $target))

Write-Section -Title '节区'
& $r2.Command @($r2.PrefixArgs + @('-q', '-c', 'iS', '--', $target))

Write-Section -Title '导入'
& $r2.Command @($r2.PrefixArgs + @('-q', '-c', 'ii', '--', $target)) | Select-Object -First $ImportsLimit

Write-Section -Title '导出'
& $r2.Command @($r2.PrefixArgs + @('-q', '-c', 'iE', '--', $target))

Write-Section -Title '字符串'
& $r2.Command @($r2.PrefixArgs + @('-q', '-c', 'iz', '--', $target)) | Select-Object -First $StringsLimit

if ($RunAnalysis) {
    Write-Section -Title '函数与入口分析'
    & $r2.Command @($r2.PrefixArgs + @('-A', '-q', '-c', 's entry0;afl;iz;ii;q', '--', $target))
}
