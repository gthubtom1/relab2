#Requires -Version 5.1
<#
.SYNOPSIS
  relab2 根目录一键自检入口
.DESCRIPTION
  自动加载持久化环境变量并运行换机部署自检，验证执行策略、编码、探测层与路由器状态。
#>
[CmdletBinding()]
param(
  [string] $SkillRoot = '',
  [string] $ToolRoot  = ''
)
# $repoRoot 必须**先**算出来：下一行要用它定位 PsModulePathInit.ps1。
$repoRoot = $PSScriptRoot
if (-not $repoRoot) { $repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path }

# ★ PSModulePath 自愈（2026-10-10 注入）：剔除 WindowsApps 版 PowerShell 7 的模块目录，
#   否则 PS 5.1 会因 TypeData 重复定义失败而使 Get-FileHash / Get-ExecutionPolicy
#   不可用（已造成两次假绿 + 一次失败被吞）。模块本体见 skillpack\skills\scripts\lib\PsModulePathInit.ps1。
#
# ★ 2026-10-10 修正硬编码路径：本行原来无条件 dot-source `<仓根>\...`，
#   导致把仓库 clone 到任何别的位置（AI-INSTALL.md 明确建议用 `~/reverse-skill`）
#   的用户在第一步自检就炸在「找不到 PsModulePathInit.ps1」。
#   现在按 $repoRoot 定位；本机原位时行为不变，换机时按仓内相对路径走。
$psModulePathInit = Join-Path $repoRoot 'skillpack\skills\scripts\lib\PsModulePathInit.ps1'
if (Test-Path -LiteralPath $psModulePathInit) {
    . $psModulePathInit
}

# ★ 2026-10-10 修正优先级倒置：原来用 `if (-not $env:X) { $env:X = ... }`，
#   也就是**已存在的进程环境变量会压过显式传入的参数**。后果实测：
#     powershell -File selfcheck.ps1 -ToolRoot 'E:\no-such-toolroot'
#   同一次运行里会同时打印「工具根: E:\no-such-toolroot」（参数）
#   和「工具根（探测层求得）= D:\Tools」（实际探测用的环境变量）——
#   参数只影响显示、不影响探测，等于没有这个参数。
#   正确顺序：**显式参数 > 环境变量 > 默认探测**，用 $PSBoundParameters 区分
#   「用户传了」和「用了默认值」。这也顺带修掉了「进程里残留一个陈旧/错误
#   REVERSE_* 值就再也传不进正确值」的问题（本机实测 Process 级残留
#   E:\nope-not-here 时，每次 selfcheck 第 3 项都 FAIL）。
$skillRootExplicit = $PSBoundParameters.ContainsKey('SkillRoot')
$toolRootExplicit  = $PSBoundParameters.ContainsKey('ToolRoot')

if (-not $skillRootExplicit) {
    # 环境变量只在它指向**真实存在**的目录时才采信。
    # 实测踩过的坑：Process 级残留一个陈旧的 E:\nope-not-here，
    # User 级明明是对的 <仓根>，但脚本优先读了 Process 级 ——
    # 于是每次 selfcheck 第 3 项都 FAIL，而真正的原因（路径不存在）
    # 跟显示出来的症状（找不到 START-HERE.md）对不上号。
    if ($env:REVERSE_SKILL_ROOT -and (Test-Path -LiteralPath $env:REVERSE_SKILL_ROOT -PathType Container)) {
        $SkillRoot = $env:REVERSE_SKILL_ROOT
    } else {
        if ($env:REVERSE_SKILL_ROOT) {
            Write-Warning ("进程级 REVERSE_SKILL_ROOT 指向不存在的路径（{0}），已忽略并用自推导值 {1}。User 级变量未受影响。" -f $env:REVERSE_SKILL_ROOT, $repoRoot)
        }
        $SkillRoot = $repoRoot
    }
}
if (-not $toolRootExplicit) {
    if ($env:REVERSE_TOOL_ROOT -and (Test-Path -LiteralPath $env:REVERSE_TOOL_ROOT -PathType Container)) {
        $ToolRoot = $env:REVERSE_TOOL_ROOT
    } elseif (Test-Path -LiteralPath 'D:\Tools' -PathType Container) {
        $ToolRoot = 'D:\Tools'
    } else {
        $ToolRoot = ''
    }
}

# 进程级残留值已在上方被否决，但子进程仍会继承到这个脏值
# （PowerShell 的子进程默认继承父进程环境块）。必须把纠正后的值写回去，
# 否则 selfcheck-newmachine.ps1 读到的还是 E:\nope-not-here。
if (-not $skillRootExplicit -and $env:REVERSE_SKILL_ROOT -ne $SkillRoot) {
    $env:REVERSE_SKILL_ROOT = $SkillRoot
}

# 确保子进程继承：显式参数优先（无条件写），否则只在为空时补
if ($skillRootExplicit -or -not $env:REVERSE_SKILL_ROOT) { $env:REVERSE_SKILL_ROOT = $SkillRoot }
if ($toolRootExplicit  -or (-not $env:REVERSE_TOOL_ROOT -and $ToolRoot)) { $env:REVERSE_TOOL_ROOT = $ToolRoot }

$targetScript = Join-Path $repoRoot "skillpack\skills\scripts\selfcheck-newmachine.ps1"
if (-not (Test-Path $targetScript)) {
    Write-Error "未找到自检核心脚本: $targetScript"
    exit 1
}

& powershell -NoProfile -ExecutionPolicy Bypass -File $targetScript -SkillRoot $SkillRoot -ToolRoot $ToolRoot
exit $LASTEXITCODE
