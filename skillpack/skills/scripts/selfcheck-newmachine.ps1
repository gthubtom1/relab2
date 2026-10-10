#Requires -Version 5.1
<#
.SYNOPSIS
  换机部署自检。跑一遍，全过才算装好。
.DESCRIPTION
  为什么会需要它：全新 Windows 默认 Get-ExecutionPolicy = Restricted，任何 .ps1 都跑不了；
  再加上工具根/技能包根没设、代码页是 936 —— 这三样合起来会产生**大量假 MISSING**
  （「工具不存在」「文件不存在」），而真因其实是环境没通。

  本脚本**只测量、不修改**：不装任何东西，不改环境变量，不改执行策略。
  它自己用 -ExecutionPolicy Bypass 绕策略，所以策略是 Restricted 也能跑。

.EXAMPLE
  # 推荐：走仓库根封装入口（自动解析技能包根/工具根再调本脚本）
  powershell -NoProfile -ExecutionPolicy Bypass -File .\selfcheck.ps1

.EXAMPLE
  # 直接调本脚本（仅在需要显式传根时；相对路径要求 cwd == 仓库根）
  powershell -NoProfile -ExecutionPolicy Bypass -File .\skillpack\skills\scripts\selfcheck-newmachine.ps1
#>
[CmdletBinding()]
param(
  [string] $SkillRoot = '',
  [string] $ToolRoot  = ''
)
# ★ PSModulePath 自愈（2026-10-10 注入，路径由 inject-psmp.py 统一计算）：剔除 WindowsApps 版 PowerShell 7 的模块目录，否则 PS 5.1 会因 TypeData 重复定义失败而使 Get-FileHash / Get-ExecutionPolicy 不可用（已造成两次假绿 + 一次失败被吞）。重算/迁移后请重跑 work/envinit/inject-psmp.py
# ★ 2026-10-10 去掉硬编码 `C:\relab2\...` 绝对路径。
#   原来无条件 dot-source 固定路径：仓库 clone 到别处时它静默失效 ——
#   错误写到 stderr，但 $ErrorActionPreference 在后面才设，主流程照跑，
#   于是「PSModulePath 自愈」悄悄没了，只留一屏红字。
#   现在按本文件位置逐级上溯，找到含 skillpack/skills/scripts/lib/ 的仓根为止。
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
$ErrorActionPreference = 'Continue'
$pass = 0; $fail = 0; $warn = 0
function Ok   ($m) { $script:pass++; Write-Host ("  [OK]   " + $m) -ForegroundColor Green }
function Bad  ($m) { $script:fail++; Write-Host ("  [FAIL] " + $m) -ForegroundColor Red }
function Warn ($m) { $script:warn++; Write-Host ("  [WARN] " + $m) -ForegroundColor Yellow }

# ── 定位技能包根：本文件在 <根>\skillpack\skills\scripts\ 下，往上三层 ──
$here = $PSScriptRoot
if (-not $SkillRoot) { $SkillRoot = (Resolve-Path (Join-Path $here '..\..\..')).Path }
# 固定根：仓库 C:\relab2、工具根 D:\Tools（主人定死，换机不变）。
# 环境变量只是覆盖手段，不是必需 —— 都没设就用下面这两个固定值。
if (-not $ToolRoot) {
  $ToolRoot = if ($env:REVERSE_TOOL_ROOT) { $env:REVERSE_TOOL_ROOT }
             elseif (Test-Path 'D:\Tools')      { 'D:\Tools' }
             else                               { '' }
}

Write-Host ''
Write-Host '=== 换机部署自检（只测量，不修改） ===' -ForegroundColor Cyan
Write-Host ("仓库根  : " + $SkillRoot + "   (固定 C:\relab2，自本文件位置推导)")
Write-Host ("工具根  : " + $(if ($ToolRoot) { $ToolRoot } else { '(未找到)' }))
Write-Host ''

Write-Host '--- 1. 执行策略 ---' -ForegroundColor Cyan
# ★ 2026-10-10 修正：原实现直接 `(Get-ExecutionPolicy)`，模块加载失败时
#   抛异常被 $ErrorActionPreference='Continue' 吞成 $null，
#   于是走到 else 分支打印「当前策略 = （空）」并 **$pass++ 记成通过** ——
#   「读不到策略」被当成「策略没问题」。这正是本项目最想消灭的那类假绿。
#   2026-10-10 实测可复现：PSModulePath 混入 WindowsApps 版 PowerShell 7 的
#   模块目录时，PS 5.1 加载 Microsoft.PowerShell.Security 因 TypeData 重复定义失败，
#   Get-ExecutionPolicy 直接 CommandNotFoundException。
$ep = $null
$epErr = $null
try {
  $ep = (Get-ExecutionPolicy -ErrorAction Stop)
} catch {
  $epErr = $_.Exception.Message
}
if ($null -eq $ep) {
  Bad "读不到执行策略（模块载入失败）: $epErr"
  Bad "本脚本靠 -ExecutionPolicy Bypass 仍可跑；通常是 PSModulePath 混入了其它 PowerShell 版本的模块目录"
} elseif ($ep -eq 'Restricted') {
  Warn ("当前策略 = Restricted。本脚本靠 -ExecutionPolicy Bypass 绕过了，")
  Warn ("但你直接跑别的 .ps1 会失败 —— 调用时一律加 -ExecutionPolicy Bypass。")
  $pass++
} else {
  Ok ("当前策略 = " + $ep)
}

Write-Host '--- 2. 环境变量 ---' -ForegroundColor Cyan
if ($env:REVERSE_SKILL_ROOT) {
  Ok ("REVERSE_SKILL_ROOT = " + $env:REVERSE_SKILL_ROOT)
} else {
  Ok "REVERSE_SKILL_ROOT 未设 —— 技能包位置由探测层相对自身推导，不必设（设了只是更快）"
}
if ($env:REVERSE_TOOL_ROOT) {
  Ok ("REVERSE_TOOL_ROOT = " + $env:REVERSE_TOOL_ROOT)
} else {
  Ok "REVERSE_TOOL_ROOT 未设 —— 探测层用固定默认值 D:\Tools，不必设；设了只是换个工具根时用"
}

Write-Host '--- 3. 编码（936 机器读 UTF-8 不加参数会读出乱码）---' -ForegroundColor Cyan
$probe = Join-Path $SkillRoot 'START-HERE.md'
if (Test-Path $probe) {
  $raw = Get-Content $probe -Raw -ErrorAction SilentlyContinue
  $u8  = Get-Content $probe -Raw -Encoding UTF8 -ErrorAction SilentlyContinue
  if ($u8 -match 'START-HERE') { Ok '加 -Encoding UTF8 能读出正确内容' }
  elseif ($raw -match 'START-HERE') { Warn '本机默认编码恰好是 UTF-8，但建议仍显式加 -Encoding UTF8' }
  else { Bad "读 START-HERE.md 两种读法都不对 —— 先解决编码再往下走" }
} else {
  Bad ("找不到 START-HERE.md（试了 " + $probe + "）")
}

Write-Host '--- 4. 探测层（一次验证策略+路径+探测层本身）---' -ForegroundColor Cyan
$boot = Join-Path $here 'lib\Bootstrap.ps1'   # 本文件就在 scripts\ 下，探测层在同级 lib\，不依赖任何盘符或目录名
if (-not (Test-Path $boot)) {
  Bad ("找不到探测层: " + $boot)
} else {
  try {
    # 在本进程里载入；同进程已载入则直接调
    if (-not (Get-Command Resolve-ReverseToolSpec -ErrorAction SilentlyContinue)) {
      . $boot
    }
    $r = Resolve-ReverseToolSpec -Name 'idat'
    # ★ 2026-10-10：工具根指错时不能报「IDA 可能没装」。
    #   探测层此时直接早退，idat 与任何工具一样找不到 —— 这跟装没装 IDA 无关。
    $toolRootEarly = ($r.Via -eq 'tool-root-missing')
    if ($r.Available) {
      Ok ("探测层可用，且能找到 idat（Via=" + $r.Via + "）")
    } elseif ($toolRootEarly) {
      Warn "探测层能跑，但工具根不可用 —— idat 未探测，不是 IDA 没装"
    } else {
      Warn "探测层能跑，但 idat 没找到 —— IDA 可能没装；装法见包根 TOOL-CHAIN.md"
    }

    # ★ 验证 -Name 'xxx.exe' 的假缺失行为（这是探测层的既定契约，不是缺陷）。
    #   GUI 交互式程序（die.exe / ida.exe / Wireshark.exe）一律被 deny 规则挡住，
    #   「不带扩展名找得到、带扩展名找不到」是**正确行为**，因此不再报 WARN。
    $r2 = Resolve-ReverseToolSpec -Name 'idat.exe'
    if ($r.Available -and -not $r2.Available) {
      Write-Host ("      - 确认：'idat' 可用、'idat.exe' 不可用 —— GUI 孪生被 deny 规则挡住，属预期。用 'idat'。") -ForegroundColor Gray
    }
    # 工具根可能不是环境变量给的 —— 载入探测层后就知道真实值了，补报一次
    try {
      $realToolRoot = Get-ReverseToolRoot
      if ($realToolRoot -and $realToolRoot -ne $ToolRoot) {
        Ok ("工具根（探测层求得）= " + $realToolRoot)
      }
    } catch { }
  } catch {
    Bad ("探测层载入失败: " + $_.Exception.Message)
    Bad "若报「禁止运行脚本」，是执行策略 —— 用 -ExecutionPolicy Bypass 启动本脚本"
  }
}

Write-Host '--- 5. 路由器 ---' -ForegroundColor Cyan
$route = Join-Path $here 'master-route.ps1'   # 路由器与本文件同级
if (-not (Test-Path $route)) {
  Bad ("找不到路由器: " + $route)
} else {
  $tmp = Join-Path ([System.IO.Path]::GetTempPath()) ('selfcheck-' + [guid]::NewGuid().ToString('n'))
  try {
    # 不解析 stdout —— master-route 用 Write-Host 输出（信息流，不进 2>&1）。
    # 直接读它真正产出的 route-scope.md，这才是判据。
    $null = & $route -Hint 'APK 闪退' -OutDir $tmp 2>&1
    $scope = Join-Path $tmp 'route-scope.md'
    if (Test-Path $scope) {
      $m = [regex]::Match((Get-Content $scope -Raw -Encoding UTF8), '(?m)^- primary:\s*(\S+)')
      if ($m.Success) { Ok ("路由器可用，选中 " + $m.Groups[1].Value) }
      else { Bad ("route-scope.md 生成但读不出 primary 字段: " + $scope) }
    } else {
      Bad ("路由器没产出 route-scope.md（试了 " + $scope + "）")
    }
  } finally {
    Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
  }
}

Write-Host '--- 6. 全机工具链就绪度与 MCP 探活扫描 ---' -ForegroundColor Cyan
try {
  if (-not (Get-Command Export-ReverseEnvironmentSnapshot -ErrorAction SilentlyContinue)) {
    . $boot
  }
  # ★ 2026-10-10 修正：原写 `$snapFile = Join-Path $SkillRoot '.hub\tools.local.json'`。
  #   $SkillRoot 来自 REVERSE_SKILL_ROOT —— 若它指向一个**不存在**的目录，
  #   Export-ReverseEnvironmentSnapshot 会**建出那个目录**并写文件。
  #   这与「本脚本只测量、不修改」的自述矛盾（selfcheck-newmachine.ps1 头部声明），
  #   也让「模拟换机」把快照落到任意路径。
  #   快照属于**本仓库**的工具清单，应当写在仓库根下，不受 REVERSE_SKILL_ROOT 影响。
  $repoSelf = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
  $hubDir   = Join-Path $repoSelf '.hub'
  if (-not (Test-Path -LiteralPath $hubDir)) {
    # 仓库自己的 .hub 缺失才建（这是本包的正常布局），绝不按 $SkillRoot 建
    New-Item -ItemType Directory -Path $hubDir -Force | Out-Null
  }
  $snapFile = Join-Path $hubDir 'tools.local.json'
  $snap = Export-ReverseEnvironmentSnapshot -OutFile $snapFile
  # ★ Tools 是 OrderedDictionary，不是 PSCustomObject。
  #   早先写成 $snap.Tools.PSObject.Properties，数到的是字典自身的
  #   Count/Keys/Values/SyncRoot... 那 7 个属性，而不是工具数 ——
  #   于是 24/25 就绪的机器被报成「1 / 7」，凭空造出一个不存在的假 MISSING。
  $toolMap = $snap.Tools
  $entries = @{}
  if ($toolMap -is [System.Collections.IDictionary]) {
    foreach ($k in $toolMap.Keys) { $entries[[string]$k] = $toolMap[$k] }
  } else {
    foreach ($p in $toolMap.PSObject.Properties) { $entries[$p.Name] = $p.Value }
  }
  $totalCount = $entries.Count
  # ★ 2026-10-10：工具根指错时，全部 25 条都会带 Via='tool-root-missing'。
  #   旧代码把这种情况统计成「工具没就绪」，报出 9/25 就绪 —— 与「工具真没装」
  #   完全无法区分，主人只能自己去猜到底缺了什么。
  #   现在先把工具根校验摆在最前面，指错就直说指错了，别拿工具数背锅。
  $toolRoot = Get-ReverseToolRoot
  # ★ 2026-10-10 修正文案：原来只判「存在且是目录」，两类坏情况都报
  #   「路径不存在」—— 但「路径存在、只是它是文件」是完全不同的错误
  #   （实测把 REVERSE_TOOL_ROOT 指到 D:\Tools\README.md 时就是这么报的）。
  #   诊断信息指错方向，主人会照着去查一个并不存在的问题。
  $toolRootMissing = -not ($toolRoot -and (Test-Path -LiteralPath $toolRoot -ErrorAction SilentlyContinue))
  $toolRootNotDir  = ($toolRoot -and -not $toolRootMissing -and
                      -not (Test-Path -LiteralPath $toolRoot -PathType Container -ErrorAction SilentlyContinue))
  $toolRootExists  = -not ($toolRootMissing -or $toolRootNotDir)
  if ($toolRootMissing) {
    $rootShown = if ($toolRoot) { $toolRoot } else { '(未设置)' }
    Warn "工具根不可用: $rootShown —— 路径不存在，工具探测已全部跳过"
    Warn '  这一项报的是**工具根指错**，不是「工具没装」。设对再重跑：'
    Warn '  $env:REVERSE_TOOL_ROOT = ''D:\Tools'''
  } elseif ($toolRootNotDir) {
    Warn "工具根不可用: $toolRoot —— 路径存在，但它是个**文件**，不是工具根目录"
    Warn '  工具根必须是一个目录（里面放各工具的子目录）。指向一个文件时，'
    Warn '  四级探测的第 3/4 级（map 别名 + 工具根递归）都无从下手。'
    Warn '  典型成因：把某个文件（如 README.md）当成了工具根。'
  }
  $missing = @($entries.GetEnumerator() | Where-Object { $_.Value.Available -ne $true } | ForEach-Object { $_.Key })
  $availCount = $totalCount - $missing.Count
  if ($toolRootExists) {
    Ok ("核心逆向工具就绪: $availCount / $totalCount（已缓存至 $snapFile）")
  } else {
    Warn ("核心逆向工具就绪: $availCount / $totalCount —— **该数字无效**，工具根指错导致探测未真正执行")
  }
  if ($missing.Count -and $toolRootExists) {
    Write-Host ("      - 未就绪: " + ($missing -join ', ')) -ForegroundColor Yellow
    Write-Host '        逐条核实：四级探测全失败才算真缺，见 references/env-selfcheck.md' -ForegroundColor Gray
  }
  foreach ($k in $snap.Mcp.Keys) {
    $entry = $snap.Mcp[$k]
    $status = if ($entry.Online) { '监听中 (READY)' } else { '未监听 (按需拉起)' }
    Write-Host ("      - MCP $k [port $($entry.Port)]: $status") -ForegroundColor Gray
  }
} catch {
  Warn ("工具链扫描警告: " + $_.Exception.Message)
}

Write-Host ''
Write-Host ("=== 通过 $pass / 失败 $fail / 提醒 $warn ===") -ForegroundColor Cyan
if ($fail -gt 0) {
  Write-Host '有 FAIL —— 按上面的提示逐条处理，处理完重跑本脚本。' -ForegroundColor Red
  exit 1
}
if ($warn -gt 0) {
  Write-Host '无 FAIL，但有 WARN —— 按提示看一眼即可，都不是拦路的。' -ForegroundColor Yellow
  exit 0
}
Write-Host '全部通过。' -ForegroundColor Green
exit 0