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
  [switch] $WriteMachine
)
# ★ PSModulePath 自愈（2026-10-10 注入，路径由 inject-psmp.py 统一计算）：剔除 WindowsApps 版 PowerShell 7 的模块目录，否则 PS 5.1 会因 TypeData 重复定义失败而使 Get-FileHash / Get-ExecutionPolicy 不可用（已造成两次假绿 + 一次失败被吞）。重算/迁移后请重跑 work/envinit/inject-psmp.py
. 'C:\relab2\skillpack\skills\scripts\lib\PsModulePathInit.ps1'


$ErrorActionPreference = 'Stop'
$repoRoot = $PSScriptRoot
if (-not $repoRoot) { $repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path }
if (-not $SkillRoot) { $SkillRoot = $repoRoot }

Write-Host "=== relab2 新机环境初始化 ===" -ForegroundColor Cyan
Write-Host "技能包根目标: $SkillRoot"
Write-Host "工具根目标  : $ToolRoot"

# 1. 确保 D:\Tools 存在
if (-not (Test-Path $ToolRoot)) {
    Write-Host "创建工具根目录: $ToolRoot" -ForegroundColor Yellow
    New-Item -ItemType Directory -Path $ToolRoot -Force | Out-Null
}

# 2. 持久化设置用户与系统环境变量
Write-Host "写入持久化环境变量..." -ForegroundColor Yellow
[System.Environment]::SetEnvironmentVariable("REVERSE_SKILL_ROOT", $SkillRoot, [System.EnvironmentVariableTarget]::User)
[System.Environment]::SetEnvironmentVariable("REVERSE_TOOL_ROOT", $ToolRoot, [System.EnvironmentVariableTarget]::User)

# ★ 2026-10-10 修正：原实现在这里 try 写 Machine 级环境变量。
#   这违反 环境初始化.md §0 红线 R2（「不写 Machine 级环境变量 ——
#   影响这台机器上所有人，你无权替主人做这个决定」）。
#   文档只写「会尝试，有权限就真写」，但这是换机入口第一步的命令，
#   而本机默认是管理员 —— 等于默认破线。
#   探测层不需要 Machine 级变量（它从 User 级读）。
#   现在只写 User 级；确需 Machine 级请显式加 -WriteMachine 并先问主人。
if ($WriteMachine) {
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

Write-Host ""
Write-Host "=== 初始化配置完成 ===" -ForegroundColor Green
