#Requires -Version 5.1
<#
  经验卡 fixture：验证 $script: 作用域不可跨脚本块搬运这条规则。

  这个文件**故意**由外部测试调用，用法有三种：

    A. 直接执行 selftest-internal   -> 函数在自己的 script 作用域里跑，读得到
    B. 被当字符串 eval / ScriptBlock 注入别的进程 -> 读不到 $script:ProbeValue
    C. dot-source 到调用方            -> 调用方的 $script: 与本文件不是同一个槽

  经验卡断言的是：**只有 A 读得到**。B/C 读不到不是 bug，是 PowerShell 作用域语义。
#>
[CmdletBinding()]
param(
  [ValidateSet('selftest-internal', 'selftest-external')]
  [string] $Action = 'selftest-internal'
)

$ErrorActionPreference = 'Stop'

# 这个变量绑定在**定义它的脚本块**上。
$script:ProbeValue = 'INTERNAL-SCOPE-OK'

function Get-Probe {
    # 函数里写的 $script: 指向的是本文件所属的 script 作用域。
    $script:ProbeValue = 'SET-BY-FUNCTION'
    return $script:ProbeValue
}

switch ($Action) {
    'selftest-internal' {
        $r = Get-Probe
        Write-Output ("PROBE=" + $r)
        Write-Output ("SCOPE_SLOTS=" + ($script:ProbeValue))
        break
    }
    'selftest-external' {
        # 这里模拟「外部探针」：它自己的 $script:ProbeValue 是另一个槽。
        Write-Output ("EXTERNAL_SEES=" + $script:ProbeValue)
        break
    }
}

exit 0