# Shared parsers for master-route route-scope.md.
# Line-anchored so a hint containing "primary: R11" cannot steal the real PRIMARY.
# ★ PSModulePath 自愈（2026-10-10 注入，路径由 inject-psmp.py 统一计算）：剔除 WindowsApps 版 PowerShell 7 的模块目录，否则 PS 5.1 会因 TypeData 重复定义失败而使 Get-FileHash / Get-ExecutionPolicy 不可用（已造成两次假绿 + 一次失败被吞）。重算/迁移后请重跑 work/envinit/inject-psmp.py
. 'C:\relab2\skillpack\skills\scripts\lib\PsModulePathInit.ps1'

function Get-ReverseRouteScopeFields {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$Text
    )
    $id = $null
    $skill = $null
    $idHits = [regex]::Matches($Text, '(?m)^- primary:\s*(\S+)\s*$')
    if ($idHits.Count -gt 0) { $id = $idHits[$idHits.Count - 1].Groups[1].Value }
    $skillHits = [regex]::Matches($Text, '(?m)^- primary_skill:\s*skills/(\S+)\s*$')
    if ($skillHits.Count -gt 0) { $skill = $skillHits[$skillHits.Count - 1].Groups[1].Value }
    return [pscustomobject]@{
        Id    = $id
        Skill = $skill
    }
}
