#Requires -Version 5.1
# reverse-skill PRIMARY router.
# 规则单一事实源：skills/config/routing.json（勿在本脚本内硬编码路由表）。
# CLI 兼容旧版：-Hint / -OutDir；输出 route-scope.md；退出码 0 成功 / 2 配置或技能缺失。
# 读取 UTF-8 BOM 源以保证 Windows PowerShell 5.1 下 CJK 正常。
param(
    [string] $Hint = '',
    [string] $OutDir = '',
    [string] $ProjectRoot = ''
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
$ErrorActionPreference = 'Stop'

# Lowercase for Latin tokens; CJK unchanged by ToLowerInvariant.
$t = if ($Hint) { $Hint.ToLowerInvariant() } else { '' }

$scriptDir = $PSScriptRoot
if (-not $scriptDir) { $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path }
$skillsRoot = Split-Path -Parent $scriptDir
$packageRoot = Split-Path -Parent $skillsRoot
$configPath = Join-Path $skillsRoot 'config/routing.json'

# --- 读取路由配置（单一事实源） ---
if (-not (Test-Path -LiteralPath $configPath)) {
    Write-Host ("ERROR: routing config missing: {0}" -f $configPath) -ForegroundColor Red
    Write-Host 'Restore skills/config/routing.json (git checkout / git pull) and retry.' -ForegroundColor Yellow
    exit 2
}
try {
    $cfg = Get-Content -LiteralPath $configPath -Raw -Encoding UTF8 | ConvertFrom-Json
} catch {
    Write-Host ("ERROR: routing config is not valid JSON: {0}" -f $_.Exception.Message) -ForegroundColor Red
    exit 2
}

# --- 规则匹配：每条 keyword 规则命中则计入候选集（与旧版逐条 if 行为一致） ---
$sel = New-Object System.Collections.Generic.List[string]
foreach ($route in $cfg.routes.PSObject.Properties) {
    $id = $route.Name
    foreach ($kw in $route.Value.keywords) {
        $hit = $false
        if ($null -ne $kw.must -and $t -match $kw.must) { $hit = $true }
        # mustAll：全部子正则都匹配才成立
        if ($hit -and $null -ne $kw.mustAll) {
            foreach ($m in $kw.mustAll) {
                if ($t -notmatch $m) { $hit = $false; break }
            }
        }
        # exclude：命中则本条规则不触发（防误伤，如 越狱/LLM 语境、域控/攻击链）
        if ($hit -and $null -ne $kw.exclude -and $t -match $kw.exclude) { $hit = $false }
        if ($hit) { [void]$sel.Add($id) }
    }
}

# --- 计分：同 id 多规则命中则加分（与旧版一致） ---
$scores = [ordered]@{}
foreach ($item in $sel) {
    if (-not $scores.Contains($item)) { $scores[$item] = 0 }
    $scores[$item] = $scores[$item] + 1
}

$uniq = New-Object System.Collections.Generic.List[string]
foreach ($d in $scores.Keys) { [void]$uniq.Add($d) }

# --- priority 自检：路由表与 priority 必须一一对应，防新增路由漏加优先级 ---
$routeIds = @($cfg.routes.PSObject.Properties | ForEach-Object { $_.Name })
$missingInPriority = @($routeIds | Where-Object { $_ -notin @($cfg.priority) })
$extraInPriority = @($cfg.priority | Where-Object { $_ -notin $routeIds })
if ($missingInPriority.Count -gt 0 -or $extraInPriority.Count -gt 0) {
    Write-Host 'WARN: routing.json routes/priority mismatch:' -ForegroundColor Yellow
    if ($missingInPriority.Count -gt 0) { Write-Host ("  routes not in priority: {0}" -f ($missingInPriority -join ', ')) -ForegroundColor Yellow }
    if ($extraInPriority.Count -gt 0) { Write-Host ("  priority not in routes: {0}" -f ($extraInPriority -join ', ')) -ForegroundColor Yellow }
}

# --- 按 priority 顺序取分数最高者为 PRIMARY（并列时 priority 靠前者胜出） ---
$priority = @($cfg.priority)
$fallbackId = $cfg.meta.fallbackId
$primary = $null
$maxScore = -1
foreach ($p in $priority) {
    if ($scores.Contains($p)) {
        $score = $scores[$p]
        if ($score -gt $maxScore) {
            $maxScore = $score
            $primary = $p
        }
    }
}

$notes = New-Object System.Collections.Generic.List[string]
$confidence = 'low'
if ($null -eq $primary) {
    $primary = $fallbackId
    if ($t) { [void]$notes.Add('No strong keyword hit; open routing.md full matrix') }
    else { [void]$notes.Add('Empty hint; provide task text') }
} else {
    $confidence = if ($uniq.Count -eq 1) { 'high' } else { 'medium' }
}

# ★ 零基础主人的日常工程任务（做软件/网站/工具、接手仓库、二开、采集协议、加参数/修 bug）
# 在 routing.json 里没有对应技能路由（六条业务线在 kernel，不在本包路由表），常落到 R0 兜底 ——
# 而 R0 指向 reverse-engineering，会让 AI 拿逆向工序去跑一个空项目。这里只加一条**指路 NOTE**
# （advisory，永不改 PRIMARY、不改 routing.json；改 routing.json 是红线⑤禁止的），
# 不论当前 PRIMARY 是兜底还是某条真实路由，只要 hint 命中日常工程语就提示去 Q0 人话表 + kernel 六线。
if ($t -match '(帮我做|我想做|做个|做一个|搞个|弄个|写个|建个|搭个).{0,8}(网站|软件|工具|程序|app|应用|服务|脚本|命令行|接口|后端|前端|系统|平台)|接手|二开|二次开发|采集.{0,6}(数据|接口|协议|app)|抓.{0,4}(协议|接口|包)|自动化.{0,6}(脚本|流程|任务)|加.{0,3}参数|修.{0,3}(个)?(bug|缺陷)|改.{0,3}(个)?(bug|缺陷)|(?<![a-z])部署(?![a-z])|上线|写.{0,4}文档') {
    [void]$notes.Add('日常工程/开发任务（Q0=A）：走 kernel 六条业务线（desktop-product / web-service / cli-tool / source-takeover / exe-rebuild / protocol-automation），入口 kernel/04-console/cards/hub/04-全能工程中枢.md；人话对照见 reverse-engineering/references/assault-entry.md Q0 人话表。不是逆向任务时勿套逆向工序。')
}

# 防御：priority 若含 routes 之外的幽灵 id（配置错误），回退到 fallback 而非崩溃
if ($routeIds -notcontains $primary) {
    Write-Host ("WARN: primary id '{0}' not in routes; falling back to {1}" -f $primary, $fallbackId) -ForegroundColor Yellow
    $primary = $fallbackId
}

# 复用当前主线的项目工作根解析，避免把路由产物写进 skill 包。
$scriptDir = $PSScriptRoot
if (-not $scriptDir) { $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path }
$skillsRoot = Split-Path -Parent $scriptDir
$packageRoot = Split-Path -Parent $skillsRoot
. (Join-Path (Join-Path $scriptDir 'lib') 'WorkRoot.ps1')
$projectRoot = Resolve-ReverseProjectRoot -RequestedRoot $ProjectRoot

# --- 默认产物目录（2026-10-12 目录治理）---
# 默认写 <project>/work/route/latest/route-scope.md；写之前把上一份 latest 归档到
# <project>/work/route/<sha12>/route-scope.md（归档不删除）。-OutDir 显式给出时完全跳过
# 本机制：显式路径的语义与行为与治理前逐字节一致。
$usingDefaultOutDir = $false
if ([string]::IsNullOrWhiteSpace($OutDir)) {
    $workRoot = Join-Path $projectRoot 'work'
    $routeRoot = Join-Path $workRoot 'route'
    $OutDir = Join-Path $routeRoot 'latest'
    $usingDefaultOutDir = $true
}

# --- R0 融合晋升 (fuse-promote): votes>=3 才把 PRIMARY 改成融合建议,写 scope 之前生效 ---
# 非 R0 路径零开销(本块直接跳过,不调 python); 失败/超时(3s)静默跳过,维持 R0。
$fusePromoted = $false
$fuseCache = $null
if ($primary -eq $fallbackId -and (($Hint -replace '\s+', '').Length -ge 10)) {
    try {
        $fusePath = Join-Path $packageRoot 'scripts/route-fuse.py'
        # Python 解释器多候选探测（换机器可移植）：环境变量覆盖 -> 本机已知绝对候选 -> python3 -> python。
        # 路径型候选用 Test-Path；字面量名用 Get-Command 且必须实跑一次可用性探针——
        # Windows 上 python/python3 常是 Microsoft Store 占位符（Get-Command 能命中但 exit 9009）。
        # 全部不可用时 $pyExe 为空，整块静默跳过（维持 R0，不抛错、不改 3s 超时）。
        $pyExe = ''
        foreach ($cand in @($env:REVERSE_SKILL_PYTHON)) {   # 只认主人显式指定的；其余交给下面的探测
            if (-not $cand) { continue }
            if (Test-Path -LiteralPath $cand) { $pyExe = $cand; break }
            $c = Get-Command $cand -ErrorAction SilentlyContinue
            if ($c -and $c.Source) { $pyExe = $c.Source; break }
        }
        if (-not $pyExe) {
            foreach ($name in @('python3', 'python')) {
                $c = Get-Command $name -ErrorAction SilentlyContinue
                if (-not ($c -and $c.Source)) { continue }
                $null = & $c.Source -c 'import sys' 2>$null
                if ($LASTEXITCODE -eq 0) { $pyExe = $c.Source; break }
            }
        }
        if (-not $pyExe) { throw 'no usable python interpreter candidate' }
        if (Test-Path -LiteralPath $fusePath) {
            $env:FUSE_HINT = $Hint; $env:FUSE_FUSE = $fusePath; $env:FUSE_CFG = $configPath
            $pyCode = @"
import runpy,json,os
x = runpy.run_path(os.environ.get('FUSE_FUSE'), run_name='fuse1')
g = x['load_json'](os.environ.get('FUSE_CFG'))
r = x['FuseRouter'](g, {}, True)
o = r.route(os.environ.get('FUSE_HINT', ''), False, 10)
print('FUSE_JSON:' + json.dumps({'final': o['final'], 'why': o['why'], 'votes': o['votes_top'], 'label': g['routes'][o['final']].get('label', '')}))
"@
            $psi = New-Object System.Diagnostics.ProcessStartInfo($pyExe, ('-c "' + $pyCode + '"'))
            $psi.UseShellExecute = $false; $psi.RedirectStandardOutput = $true; $psi.RedirectStandardError = $true
            $p = [System.Diagnostics.Process]::Start($psi)
            if ($p.WaitForExit(3000)) {
                $fj = ($p.StandardOutput.ReadToEnd() -split "`n" | Where-Object { $_ -match '^FUSE_JSON:' } | Select-Object -First 1) -replace '^FUSE_JSON:', ''
                if ($fj) {
                    $fo = $fj | ConvertFrom-Json
                    $fuseCache = $fo
                    if ($fo.final -ne $fallbackId -and $fo.why -eq 'fuse-rescue' -and ([int]$fo.votes) -ge 3 -and ($routeIds -contains $fo.final)) {
                        $primary = $fo.final
                        $fusePromoted = $true
                        $confidence = 'medium'
                        [void]$notes.Add(("fuse-promote: {0} votes={1} (fuse-rescue; 已晋升 PRIMARY)" -f $fo.final, $fo.votes))
                    }
                }
            } else { try { $p.Kill() } catch { } }
            Remove-Item Env:\FUSE_HINT -ErrorAction SilentlyContinue; Remove-Item Env:\FUSE_FUSE -ErrorAction SilentlyContinue; Remove-Item Env:\FUSE_CFG -ErrorAction SilentlyContinue
        }
    } catch { }
}

$primaryPath = $cfg.routes.$primary.skill
$primaryLabel = $cfg.routes.$primary.label
$skillAbs = Join-Path $skillsRoot ($primaryPath -replace '/', [IO.Path]::DirectorySeparatorChar)
if (-not (Test-Path -LiteralPath $skillAbs)) {
    Write-Host ("ERROR: PRIMARY skill missing: {0}" -f $skillAbs) -ForegroundColor Red
    exit 2
}

# --- 输出目录（默认已在上面定为 <调用方项目>\work\route\latest；显式 -OutDir 原样使用）---
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

# --- 默认目录治理：先把上一份 latest 归档，再覆盖写 ---
# 归档不删除：<project>/work/route/<sha12>/route-scope.md。
# ★ 指纹不含 `- created:` 行：该行每跑一变，含它就导致同内容永远去不了重
#   （实测同 hint 跑 N 次会新增 N-1 个目录，治理目标落空）。
#   归档内容本身仍是原始字节（含它自己的 created），只有指纹做归一化。
if ($usingDefaultOutDir) {
    try {
        $latestScope = Join-Path $OutDir 'route-scope.md'
        if (Test-Path -LiteralPath $latestScope) {
            $routeRoot = Split-Path -Parent $OutDir
            # ★ 两侧同口径（与 master-route.sh 逐字对齐）：以**字节**为起点自处理 BOM，
            #   不用 Get-Content -Raw（实测它会剥 BOM 却在行首留残渣，导致与 bash 侧
            #   指纹不同 —— 同一份内容两侧归档到两个目录）。顺序：读字节 → 去 BOM →
            #   CRLF 归 LF → 剔除 `- created:` 行 → LF 连接 → SHA-256 前 12 位。
            $rawBytes = [System.IO.File]::ReadAllBytes($latestScope)
            $text = [System.Text.Encoding]::UTF8.GetString($rawBytes)
            if ($text.Length -gt 0 -and [int]$text[0] -eq 0xFEFF) { $text = $text.Substring(1) }
            $normalized = $text -replace "`r`n", "`n" -replace "`r", "`n"
            $kept = @($normalized -split "`n" | Where-Object { -not $_.StartsWith('- created:') })
            $fingerprint = $kept -join "`n"
            $sha = [System.Security.Cryptography.SHA256]::Create()
            try {
                $hashBytes = $sha.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($fingerprint))
            } finally { $sha.Dispose() }
            $hashHex = -join ($hashBytes | ForEach-Object { $_.ToString('x2') })
            $archiveDir = Join-Path $routeRoot $hashHex.Substring(0, 12)
            $archiveScope = Join-Path $archiveDir 'route-scope.md'
            if (-not (Test-Path -LiteralPath $archiveScope)) {
                New-Item -ItemType Directory -Force -Path $archiveDir | Out-Null
                Copy-Item -LiteralPath $latestScope -Destination $archiveScope -Force
                Write-Host ("ARCHIVED -> {0}" -f $archiveScope)
            }
        }
    } catch {
        Write-Host ("WARN: route archive skipped: {0}" -f $_.Exception.Message) -ForegroundColor Yellow
    }
}

# --- 写 route-scope.md（格式与旧版一致，下游脚本解析 primary_skill / primary） ---
$sb = New-Object System.Text.StringBuilder
[void]$sb.AppendLine('# reverse-skill Master route (PRIMARY)')
[void]$sb.AppendLine(("- created: {0}" -f (Get-Date -Format 'o')))
[void]$sb.AppendLine(("- package: reverse-skill"))
$hintOneLine = (($Hint -replace '[\r\n]+', ' ').Trim())
[void]$sb.AppendLine(("- hint: {0}" -f $hintOneLine))
[void]$sb.AppendLine(("- primary: {0}" -f $primary))
[void]$sb.AppendLine(("- primary_label: {0}" -f $primaryLabel))
[void]$sb.AppendLine(("- primary_skill: skills/{0}" -f $primaryPath))
[void]$sb.AppendLine(("- confidence: {0}" -f $confidence))
[void]$sb.AppendLine(("- project_root: {0}" -f $projectRoot))
$sec = New-Object System.Collections.Generic.List[string]
foreach ($d in $uniq) {
    if ($d -ne $primary) { [void]$sec.Add(("skills/{0}" -f $cfg.routes.$d.skill)) }
}
$secText = if ($sec.Count -gt 0) { ($sec -join ', ') } else { '(none)' }
[void]$sb.AppendLine(("- secondary: {0}" -f $secText))
[void]$sb.AppendLine('')
[void]$sb.AppendLine('## MUST open next')
[void]$sb.AppendLine('')
[void]$sb.AppendLine('1. skills/MASTER-ROUTING.md')
[void]$sb.AppendLine(("2. skills/{0}" -f $primaryPath))
[void]$sb.AppendLine('')
[void]$sb.AppendLine('## Notes')
if ($notes.Count -eq 0) { [void]$sb.AppendLine('- (none)') }
foreach ($n in $notes) { [void]$sb.AppendLine(("- {0}" -f $n)) }

# UTF-8 with BOM for route-scope (Windows notepad-friendly)
$utf8 = New-Object System.Text.UTF8Encoding $true
[System.IO.File]::WriteAllText((Join-Path $OutDir 'route-scope.md'), $sb.ToString(), $utf8)

Write-Host ("PRIMARY -> skills/{0}" -f $primaryPath) -ForegroundColor Green
Write-Host ("Label: {0} | confidence: {1}" -f $primaryLabel, $confidence)
foreach ($n in $notes) { Write-Host ("NOTE: {0}" -f $n) -ForegroundColor Yellow }
Write-Host ("Wrote {0}\route-scope.md" -f $OutDir)
Write-Host 'ACTION: Open PRIMARY SKILL.md now and execute ACTION REQUIRED.' -ForegroundColor Yellow

# --- R0 影子档 (fuse-shadow): 未晋升且 PRIMARY=R0 时复用晋升阶段的融合结果,只读打一行 ---
# 约束: 晋升后不再打 SHADOW; votes<3 维持 R0 + SHADOW 行; route-scope.md/PRIMARY/confidence 以晋升后的为准; 失败静默跳过。
# 注: 融合 python 调用已在晋升阶段完成(同为 R0+hint>=10 门控),本块不再为非 R0 或已晋升路径调 python,零额外开销。
if ((-not $fusePromoted) -and ($primary -eq $fallbackId) -and (($Hint -replace '\s+', '').Length -ge 10)) {
    try {
        if ($null -ne $fuseCache -and $fuseCache.final -ne $fallbackId -and $fuseCache.why -eq 'fuse-rescue') {
            Write-Host ("SHADOW -> {0} {1} (fuse-rescue votes={2}; 影子建议,非 PRIMARY)" -f $fuseCache.final, $fuseCache.label, $fuseCache.votes) -ForegroundColor Cyan
        }
    } catch { }
}
