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

$repoRoot = $PSScriptRoot
if (-not $repoRoot) { $repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path }
if (-not $SkillRoot) {
    $SkillRoot = if ($env:REVERSE_SKILL_ROOT) { $env:REVERSE_SKILL_ROOT } else { $repoRoot }
}
if (-not $ToolRoot) {
    $ToolRoot = if ($env:REVERSE_TOOL_ROOT) { $env:REVERSE_TOOL_ROOT }
                elseif (Test-Path 'D:\Tools') { 'D:\Tools' }
                else { '' }
}

# 确保当前会话继承环境变量
if (-not $env:REVERSE_SKILL_ROOT) { $env:REVERSE_SKILL_ROOT = $SkillRoot }
if (-not $env:REVERSE_TOOL_ROOT -and $ToolRoot) { $env:REVERSE_TOOL_ROOT = $ToolRoot }

$targetScript = Join-Path $repoRoot "skillpack\skills\scripts\selfcheck-newmachine.ps1"
if (-not (Test-Path $targetScript)) {
    Write-Error "未找到自检核心脚本: $targetScript"
    exit 1
}

& powershell -NoProfile -ExecutionPolicy Bypass -File $targetScript -SkillRoot $SkillRoot -ToolRoot $ToolRoot
exit $LASTEXITCODE
