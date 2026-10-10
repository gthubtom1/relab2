# PSModulePath 自愈 —— 所有入口脚本在顶部 dot-source 本文件。
#
# 背景（本机 2026-10-10 实测）：
#   进程级 PSModulePath 会混入其它 PowerShell 版本（尤其 WindowsApps/Store 版
#   PowerShell 7）的模块目录。PS 5.1 加载同名模块时 TypeData 重复定义失败，
#   于是整个 Microsoft.PowerShell.Utility / .Security 不可用：
#       Get-FileHash       -> 无法识别
#       Get-ExecutionPolicy -> 无法加载模块
#   本包已因此产生过两次「假绿」（selfcheck 第 1 项空值记 PASS）
#   与一次「失败被吞」（test-p0-friction 连 SUMMARY 都不输出）。
#
# 规整规则：保留 Machine 级干净值 + 用户自定义目录，剔除 WindowsApps 路径。
# 幂等：Machine 级本来就干净时不做任何修改。
# ★ 2026-10-10 修正：原来直接写 `if (-not $script:PSModulePathHealed)`。
#   在 `Set-StrictMode -Version Latest` 下，**读一个从未定义过的变量会抛错**
#   （VariableIsUndefined），而不是返回 $null —— 于是任何开了 StrictMode 的
#   调用方（bootstrap-reverse.ps1 / test-client-neutral-bootstrap.ps1）
#   一 dot-source 本文件就崩。实测 test-client-neutral-bootstrap.ps1 因此常红。
#   正确写法：用 Get-Variable 显式探测存在性。
if (-not (Get-Variable -Name PSModulePathHealed -Scope Script -ErrorAction SilentlyContinue)) {
    $script:PSModulePathHealed = $true
    try {
        $machinePP = [Environment]::GetEnvironmentVariable('PSModulePath', 'Machine')
        if ($machinePP) {
            $healthy = @()
            foreach ($seg in ($machinePP -split ';')) {
                if ($seg.Trim()) { $healthy += $seg.Trim() }
            }
            $custom = @()
            foreach ($seg in ($env:PSModulePath -split ';')) {
                $s = $seg.Trim()
                if (-not $s) { continue }
                if ($s -in $healthy) { continue }
                if ($s -match '(?i)\\windowsapps\\.*microsoft\.powershell_') { continue }
                $custom += $s
            }
            $want = (@($custom) + @($healthy)) -join ';'
            if ($env:PSModulePath -and ($env:PSModulePath -ne $want)) {
                $env:PSModulePath = $want
            }
        }
    } catch { }
}
