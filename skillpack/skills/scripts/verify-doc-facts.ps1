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
<#
.SYNOPSIS
  Verify doc fact tables (capability lists, MCP ports, Burp tool count)
  against source-of-truth (bootstrap-manifest.json / McpHttpServer.java).

.DESCRIPTION
  P1-4 guard: RULES.md / RULES_zh.md / skills/SKILL.md fact tables must not
  drift from the manifest and the Burp extension source. Exit 1 on mismatch.
#>
$ErrorActionPreference = 'Stop'
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$fail = 0

function Check([string]$Name, [bool]$Ok, [string]$Detail) {
  if ($Ok) { Write-Host "OK   $Name" } else { $script:fail++; Write-Host "FAIL $Name : $Detail" }
}

# --- Source of truth: manifest ---
$manifestPath = Join-Path $Root 'skills\scripts\bootstrap-manifest.json'
$manifest = Get-Content $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
$capNames = @($manifest.capabilities | ForEach-Object { $_.name } | Sort-Object)

# --- Source of truth: Burp getToolList() ---
$javaPath = Join-Path $Root 'burp-mcp-full\src\main\java\com\burpmcp\McpHttpServer.java'
$java = Get-Content $javaPath -Raw
$def = [regex]::Match($java, 'String\s+getToolList\s*\([^)]*\)\s*\{')
if (-not $def.Success) { throw 'getToolList() not found in McpHttpServer.java' }
$endIdx = $java.IndexOf("`n    }", $def.Index)
$body = $java.Substring($def.Index, $endIdx - $def.Index)
$burpTools = @([regex]::Matches($body, '\\"([a-z_0-9]+)\\"') | ForEach-Object { $_.Groups[1].Value } | Sort-Object -Unique)
$burpCount = $burpTools.Count

Write-Host "source-of-truth: $($capNames.Count) capabilities, Burp getToolList = $burpCount tools"

# --- Doc helpers ---
function Get-ListLine([string]$Text, [string]$Marker) {
  $lines = $Text -split "`r?`n"
  for ($i = 0; $i -lt $lines.Count; $i++) {
    if ($lines[$i] -match [regex]::Escape($Marker)) {
      $inline = [regex]::Match($lines[$i], '）：(.+?)\s*$')
      if ($inline.Success) { return $inline.Groups[1].Value }
      if ($i + 1 -lt $lines.Count) { return $lines[$i + 1] }
    }
  }
  return ''
}

function Test-ListHasAll([string]$ListText, [string[]]$Names) {
  $tokens = @($ListText -split '[、,]+' | ForEach-Object { $_.Trim() } | Where-Object { $_ })
  if ($tokens.Count -ne $Names.Count) { return $false }
  foreach ($n in $Names) { if ($tokens -notcontains $n) { return $false } }
  return $true
}

$rulesEn = Get-Content (Join-Path $Root 'RULES.md') -Raw -Encoding UTF8
$rulesZh = Get-Content (Join-Path $Root 'RULES_zh.md') -Raw -Encoding UTF8
$skillMd = Get-Content (Join-Path $Root 'skills\SKILL.md') -Raw -Encoding UTF8

$enList = Get-ListLine $rulesEn 'Supported capability names'
$zhList = Get-ListLine $rulesZh '支持的能力名'
$skList = Get-ListLine $skillMd '支持的能力'

Check 'RULES.md capability list' (Test-ListHasAll $enList $capNames) "expected $($capNames.Count) capabilities: $($capNames -join ', ')"
Check 'RULES_zh.md capability list' (Test-ListHasAll $zhList $capNames) "expected $($capNames.Count) capabilities"
Check 'SKILL.md capability list' (Test-ListHasAll $skList $capNames) "expected $($capNames.Count) capabilities"
Check 'RULES_zh.md count text' ($rulesZh.Contains("共 $($capNames.Count) 项")) "expected 共 $($capNames.Count) 项"

# --- MCP ports from manifest servicePort / servicePortRange ---
foreach ($c in $manifest.capabilities) {
  if (-not $c.PSObject.Properties['servicePort']) { continue }
  $port = [string]$c.servicePort
  Check "RULES.md port $($c.name)=$port" ($rulesEn.Contains($port)) "missing port $port for $($c.name)"
  Check "RULES_zh.md port $($c.name)=$port" ($rulesZh.Contains($port)) "missing port $port for $($c.name)"
  if ($c.PSObject.Properties['servicePortRange']) {
    $range = @($c.servicePortRange) -join '-'
    Check "RULES.md range $($c.name)=$range" ($rulesEn.Contains($range)) "missing range $range for $($c.name)"
    Check "RULES_zh.md range $($c.name)=$range" ($rulesZh.Contains($range)) "missing range $range for $($c.name)"
  }
}

# --- Burp tool count ---
Check 'RULES.md burp tool count' ($rulesEn.Contains("$burpCount-tool")) "expected '$burpCount-tool' in RULES.md"
Check 'RULES_zh.md burp tool count' ($rulesZh.Contains("$burpCount 工具全控制")) "expected '$burpCount 工具全控制' in RULES_zh.md"

Write-Host "verify-doc-facts: $fail failure(s)"
if ($fail -gt 0) { exit 1 }
