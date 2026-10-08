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
  [string] $ToolRoot  = 'D:\Tools'
)

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

try {
    [System.Environment]::SetEnvironmentVariable("REVERSE_SKILL_ROOT", $SkillRoot, [System.EnvironmentVariableTarget]::Machine)
    [System.Environment]::SetEnvironmentVariable("REVERSE_TOOL_ROOT", $ToolRoot, [System.EnvironmentVariableTarget]::Machine)
} catch {
    Write-Warning "写入系统(Machine)环境变量需要管理员权限，已仅完成当前用户(User)环境变量写入。"
}

$env:REVERSE_SKILL_ROOT = $SkillRoot
$env:REVERSE_TOOL_ROOT  = $ToolRoot

# 3. 运行自检
Write-Host "运行部署自检..." -ForegroundColor Cyan
& (Join-Path $repoRoot "selfcheck.ps1") -SkillRoot $SkillRoot -ToolRoot $ToolRoot

Write-Host ""
Write-Host "=== 初始化配置完成 ===" -ForegroundColor Green
