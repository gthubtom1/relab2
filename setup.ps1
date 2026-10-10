#Requires -Version 5.1
<#
.SYNOPSIS
  relab2 新机一键初始化配置入口
.DESCRIPTION
  按照《环境初始化.md》规范，自动配置 Windows 执行策略、持久化设置技能包根与工具根环境变量，并完成落地自检。
#>
[CmdletBinding()]
param(
  [string] $SkillRoot = '',
  [string] $ToolRoot  = 'D:\Tools',
  # ★ 2026-10-10 新增：Machine 级环境变量写入必须显式开启（红线 R2）。
  #   探测层从 User 级读变量，不需要 Machine 级。
  [switch] $WriteMachine,
  # ★ 2026-10-10 新增：不写任何持久化状态，只跑自检。
  #   原实现无条件把 -SkillRoot 写进 User 级环境变量，于是**一次测试调用**
  #   （比如 `-SkillRoot 'E:\nope-not-here'`）就把机器状态永久改成假路径 ——
  #   本机实测：跑完测试后 User 级 REVERSE_SKILL_ROOT 变成 E:\nope-not-here，
  #   之后每次 selfcheck 第 3 项都 FAIL（找不到 START-HERE.md）。
  #   一次性试跑必须显式 -DryRun。
  [switch] $DryRun
)
# ★ PSModulePath 自愈（2026-10-10 注入，路径由 inject-psmp.py 统一计算）：剔除 WindowsApps
#   版 PowerShell 7 的模块目录，否则 PS 5.1 会因 TypeData 重复定义失败而使
#   Get-FileHash / Get-ExecutionPolicy 不可用（已造成两次假绿 + 一次失败被吞）。
#   重算/迁移后请重跑 work/envinit/inject-psmp.py
#
# ★ 2026-10-10 修正硬编码：本行原来是无条件 `. 'C:\relab2\...'`。
#   本文件是新机第一个要跑的入口，仓库 clone 到别处（AI-INSTALL.md 建议
#   `~/reverse-skill`）时它必然找不到 —— 错误写到 stderr，而
#   `$ErrorActionPreference = 'Stop'` 要到下一行才设，于是脚本照跑，
#   结果是「PSModulePath 自愈静默失效 + 刷一屏红字」。
#   实测复现：把 lib/PsModulePathInit.ps1 临时改名后，本脚本报
#   CommandNotFoundException 仍 rc=0。
#   现在按 $PSScriptRoot 逐级上溯，与其余 29 个入口脚本同一套写法。
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


$ErrorActionPreference = 'Stop'
$repoRoot = $PSScriptRoot
if (-not $repoRoot) { $repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path }
if (-not $SkillRoot) { $SkillRoot = $repoRoot }

Write-Host "=== relab2 新机环境初始化 ===" -ForegroundColor Cyan
Write-Host "技能包根目标: $SkillRoot"
Write-Host "工具根目标  : $ToolRoot"

# 1. 确保工具根存在
if (-not (Test-Path $ToolRoot)) {
    if ($DryRun) {
        Write-Host "[DryRun] 工具根不存在，本该创建: $ToolRoot" -ForegroundColor Yellow
    } else {
        Write-Host "创建工具根目录: $ToolRoot" -ForegroundColor Yellow
        New-Item -ItemType Directory -Path $ToolRoot -Force | Out-Null
    }
}

# 2. 持久化设置用户级环境变量（-DryRun 跳过 —— 见 param 里的说明）
if ($DryRun) {
    Write-Host "[DryRun] 跳过持久化环境变量写入（User 级）" -ForegroundColor Yellow
} else {
    Write-Host "写入持久化环境变量..." -ForegroundColor Yellow
    [System.Environment]::SetEnvironmentVariable("REVERSE_SKILL_ROOT", $SkillRoot, [System.EnvironmentVariableTarget]::User)
    [System.Environment]::SetEnvironmentVariable("REVERSE_TOOL_ROOT", $ToolRoot, [System.EnvironmentVariableTarget]::User)
}

# ★ 2026-10-10 修正：原实现在这里 try 写 Machine 级环境变量。
#   这违反 环境初始化.md §0 红线 R2（「不写 Machine 级环境变量 ——
#   影响这台机器上所有人，你无权替主人做这个决定」）。
#   文档只写「会尝试，有权限就真写」，但这是换机入口第一步的命令，
#   而本机默认是管理员 —— 等于默认破线。
#   探测层不需要 Machine 级变量（它从 User 级读）。
#   现在只写 User 级；确需 Machine 级请显式加 -WriteMachine 并先问主人。
if ($WriteMachine -and -not $DryRun) {
    try {
        [System.Environment]::SetEnvironmentVariable("REVERSE_SKILL_ROOT", $SkillRoot, [System.EnvironmentVariableTarget]::Machine)
        [System.Environment]::SetEnvironmentVariable("REVERSE_TOOL_ROOT", $ToolRoot, [System.EnvironmentVariableTarget]::Machine)
        Write-Host "已写 Machine 级环境变量（-WriteMachine）" -ForegroundColor Yellow
    } catch {
        Write-Warning "写入 Machine 级环境变量失败，已仅完成 User 级写入。"
    }
}

$env:REVERSE_SKILL_ROOT = $SkillRoot
$env:REVERSE_TOOL_ROOT  = $ToolRoot

# 3. 运行自检
Write-Host "运行部署自检..." -ForegroundColor Cyan
& (Join-Path $repoRoot "selfcheck.ps1") -SkillRoot $SkillRoot -ToolRoot $ToolRoot
$selfcheckExit = $LASTEXITCODE

if ($selfcheckExit -ne 0) {
    # ★ 2026-10-10 修正：原来不检查自检退出码也不 exit，于是自检 FAIL 时
    #   照样打印绿色的「初始化配置完成」，调用方拿到 rc=0。
    #   实测 -SkillRoot 指向不存在目录时 selfcheck rc=1，setup.ps1 仍 rc=0。
    Write-Host ""
    Write-Host "=== 初始化配置未完成：自检返回 $selfcheckExit ===" -ForegroundColor Red
    Write-Host "按上面的 FAIL 项处理完重跑本脚本。" -ForegroundColor Yellow
    exit $selfcheckExit
}

Write-Host ""
Write-Host "=== 初始化配置完成 ===" -ForegroundColor Green
