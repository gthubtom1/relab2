#Requires -Version 5.1
<#
relab2.ps1 —— 本仓库的唯一门面（对齐 REA 的 setup / doctor / update 三件套）

为什么存在（2026-10-15）：
  仓库里部署零件齐全（relab2-root / setup / selfcheck / register-skills / switch-mcp /
  kernel 工作台），但没有统一入口、也没有 doctor —— 人得知道要按什么顺序跑哪几个脚本，
  顺序与注意点散在 5 份文档里。这就是「换机很麻烦、没有稳定性、不像开源项目」的真相。
  本文件只做**门面**：解析参数 → 调用既有脚本 → 汇总成一张表。不复制它们的逻辑。

用法：
  powershell -NoProfile -ExecutionPolicy Bypass -File relab2.ps1 doctor
  powershell -NoProfile -ExecutionPolicy Bypass -File relab2.ps1 setup -DryRun
  powershell -NoProfile -ExecutionPolicy Bypass -File relab2.ps1 setup
  powershell -NoProfile -ExecutionPolicy Bypass -File relab2.ps1 update

约定：
  · 本文件不写任何盘符绝对路径（环境初始化.md §10）。仓根一律由 $PSScriptRoot 推导。
  · doctor **不改配置、不改环境变量**；但它会调用 selfcheck / register-skills -Doctor / mcp-status，
    其中会有**机器状态快照**被刷新（如 skillpack\.hub\tools.local.json —— 已 gitignore）。
    ⚠️ 旧版这里写的是「只读，不改任何东西」—— 与事实不符（审计实测），已改。
    退出码 0 = 就绪，1 = 未就绪。
  · setup 幂等，带 -DryRun 预览，不碰用户未授权的机器级状态。
#>
[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet('doctor', 'setup', 'update', 'known', 'help')]
    [string] $Command = 'help',

    [switch] $DryRun,
    [switch] $Json,
    # ★ 2026-10-18：以前 façade 不认 -ToolRoot，而 setup.ps1 默认 D:\Tools ——
    #   只有 C: 盘的新机器跑「一条命令 setup」必然 rc=1（建目录失败），且原因被 Out-Null 吞掉。
    [string] $ToolRoot = ''
)

$ErrorActionPreference = 'Continue'
# ★ 2026-10-15：子进程（powershell 5.1）把 UTF-8 写到管道，父进程若按控制台码页（936）解码，
#   中文会变成乱码（实测：stdio·懒启动 → stdio路鎳掑惎）。先把父进程的解码器钉成 UTF-8。
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }
$OutputEncoding = [System.Text.Encoding]::UTF8
$RepoRoot = $PSScriptRoot
$Results = New-Object System.Collections.Generic.List[object]

function Add-Result([string]$Name, [string]$Status, [string]$Detail) {
    $script:Results.Add([pscustomobject]@{ 项 = $Name; 结果 = $Status; 说明 = $Detail })
    $color = switch ($Status) { 'OK' { 'Green' } 'WARN' { 'Yellow' } 'FAIL' { 'Red' } default { 'Gray' } }
    Write-Host ("  [{0,-4}] {1,-26} {2}" -f $Status, $Name, $Detail) -ForegroundColor $color
}

function Write-Head([string]$t) { Write-Host "`n=== $t ===" -ForegroundColor Cyan }

function Invoke-Step {
    param([string]$File, [string[]]$ArgList, [string]$Label)
    $p = Join-Path $RepoRoot $File
    if (-not (Test-Path -LiteralPath $p)) { Add-Result $Label 'FAIL' "缺少脚本 $File"; return 1 }
    if ($DryRun) { Write-Host ("  [DryRun] 将执行: {0} {1}" -f $File, ($ArgList -join ' ')) -ForegroundColor Yellow; return 0 }
    Write-Host ("  -> {0} {1}" -f $File, ($ArgList -join ' ')) -ForegroundColor DarkGray
    & powershell -NoProfile -ExecutionPolicy Bypass -File $p @ArgList
    return $LASTEXITCODE
}

# ---------------------------------------------------------------- doctor
function Invoke-Doctor {
    Write-Head 'relab2 doctor —— 本机现在能不能干活'

    # 1 仓根
    if (Test-Path -LiteralPath (Join-Path $RepoRoot 'skillpack\skills\MASTER-ROUTING.md')) {
        Add-Result '仓根' 'OK' $RepoRoot
    }
    else {
        Add-Result '仓根' 'FAIL' "这里不像本仓库根（缺 skillpack\skills\MASTER-ROUTING.md）: $RepoRoot"
        return 1
    }

    # 2 环境变量
    $sk = $env:REVERSE_SKILL_ROOT
    $tk = $env:REVERSE_TOOL_ROOT
    if ($sk) {
        # ★ 2026-10-15：环境变量指向**另一棵树**时必须报出来 —— 否则在异地克隆里跑 doctor，
        #   它会报「仓根 = 这份 clone」，而模型实际用的是环境变量指的那棵树，两边不是一个东西。
        if ($sk.TrimEnd('\') -ieq $RepoRoot.TrimEnd('\')) {
            Add-Result 'REVERSE_SKILL_ROOT' 'OK' $sk
        }
        else {
            Add-Result 'REVERSE_SKILL_ROOT' 'FAIL' "指向另一棵树（$sk），而本脚本在 $RepoRoot —— 模型实际用的是前者。要么改环境变量，要么别在这份 clone 里跑。"
        }
    }
    else { Add-Result 'REVERSE_SKILL_ROOT' 'WARN' '未设置（跑 setup 或 relab2-root.ps1）——此时卡片兑底值为 C:\relab2；若本机不在那个路径下，模型会用错仓库/技能树' }
    if ($tk) { Add-Result 'REVERSE_TOOL_ROOT' 'OK' $tk } else { Add-Result 'REVERSE_TOOL_ROOT' 'WARN' '未设置（跑 setup）' }

    # 3 部署自检（selfcheck 的退出码就是结论）
    $sc = Join-Path $RepoRoot 'selfcheck.ps1'
    if (Test-Path -LiteralPath $sc) {
        $out = & powershell -NoProfile -ExecutionPolicy Bypass -File $sc 2>&1
        if ($LASTEXITCODE -eq 0) { Add-Result '部署自检 selfcheck' 'OK' '退出码 0' }
        else { Add-Result '部署自检 selfcheck' 'FAIL' ("退出码 $LASTEXITCODE —— 见下方原始输出"); $out | Select-Object -Last 25 | ForEach-Object { Write-Host "      $_" -ForegroundColor DarkGray } }
    }
    else { Add-Result '部署自检 selfcheck' 'FAIL' '缺少 selfcheck.ps1' }

    # 6b ★ 2026-10-15 审计 P8：仓内默认别名表的失效 prefer 计数。
    #   本机实测 68 条 prefer 里 53 条指向不存在的文件（只有 15 条命中）。
    #   本机不致命（D:\Tools\_map.json 覆盖层 38 条全部存在），但换一台没有 _map.json 的机器，
    #   这 53 条会静默落到第 4 级 scan（可信度最低）——以前没有任何东西报这件事。
    try {
        . (Join-Path $RepoRoot 'skillpack\skills\scripts\lib\Bootstrap.ps1')
        $tmh = Test-ReverseToolmapHealth
        if ($tmh.ok) {
            Add-Result 'toolmap prefer' 'OK' ("{0} 条全部指得动" -f $tmh.total)
        }
        else {
            Add-Result 'toolmap prefer' 'WARN' ("{0}/{1} 条指向不存在（如 {2}…）——未来换机时会落到第 4 级 scan" -f $tmh.missing, $tmh.total, ($tmh.missingIds -join ', '))
        }
    } catch {
        Add-Result 'toolmap prefer' 'WARN' "探测层载入或该函数不可用：$_"
    }
    # 4 MCP 通道 —— 注册清单 + **真自检**（审计：REA 的 doctor 会分辨「注册对不对 / 真连上没」，
    #   我们原来只有静态清单）。这里至少做到两层：① 命令在不在 ② 它是真能起来的形态。
    $mcp = Join-Path $RepoRoot 'skillpack\skills\scripts\mcp-status.ps1'
    if (Test-Path -LiteralPath $mcp) {
        $lines = & powershell -NoProfile -ExecutionPolicy Bypass -File $mcp 2>&1
        $reg = @($lines | Where-Object { $_ -match '^\s*\S+\s+\S+\s+(stdio|http)' })
        $closed = @($lines | Where-Object { $_ -match 'closed' })
        Add-Result 'MCP 通道' 'OK' ("已注册 {0} 条（{1} 条端点未监听 —— 懒启属正常）" -f $reg.Count, $closed.Count)
        foreach ($l in $reg) { Write-Host ("      " + $l.Trim()) -ForegroundColor DarkGray }

        # 真自检：读宿主 mcp.json，逐条验「命令在不在 / 懒启代理有没有缓存（= 工具是否对模型可见）」
        $hostMcp = Join-Path $env:USERPROFILE '.omp\agent\mcp.json'
        if (Test-Path -LiteralPath $hostMcp) {
            try {
                $cfg = (Get-Content -LiteralPath $hostMcp -Raw -Encoding UTF8 | ConvertFrom-Json).mcpServers
                $cacheDir = Join-Path $env:LOCALAPPDATA 'reverse-skill\mcp-lazy'
                $bad = 0
                $noSeed = 0
                foreach ($nm in $cfg.PSObject.Properties.Name) {
                    $e = $cfg.$nm
                    $cmdOk = $e.command -and (Test-Path -LiteralPath $e.command)
                    $isLazy = ("$($e.args -join ' ')") -match 'mcp-lazy-http'
                    if (-not $cmdOk) {
                        $bad++
                        Write-Host ("      · {0,-14} 命令不存在！{1}" -f $nm, $e.command) -ForegroundColor Red
                        continue
                    }
                    if ($isLazy) {
                        $cf = Join-Path $cacheDir "$nm.json"
                        $seed = Join-Path $RepoRoot "skillpack\skills\references\mcp-lazy-seeds\$nm.json"
                        if ((Test-Path -LiteralPath $cf) -or (Test-Path -LiteralPath $seed)) {
                            Write-Host ("      · {0,-14} 懒启·缓存/种子在位（工具对模型可见）" -f $nm) -ForegroundColor DarkGray
                        }
                        else {
                            # ★ 2026-10-18：这一条以前只打黄字、不进计数 —— 于是同一屏上一行
                            #   「模型看不见它的工具」、下一行 `[OK] MCP 通道自检 命令都在；懒启通道有缓存/种子兜底`。
                            #   审计实测 3 次全复现。现在计入 $noSeed，判 WARN。
                            $noSeed++
                            Write-Host ("      · {0,-14} 懒启·**无缓存也无种子** → 模型看不见它的工具" -f $nm) -ForegroundColor Yellow
                        }
                    }
                    else {
                        Write-Host ("      · {0,-14} stdio（宿主按会话拉起）" -f $nm) -ForegroundColor DarkGray
                    }
                }
                if ($bad -gt 0) { Add-Result 'MCP 通道自检' 'FAIL' "$bad 条的 command 指向不存在的文件" }
                elseif ($noSeed -gt 0) { Add-Result 'MCP 通道自检' 'WARN' "$noSeed 条懒启通道既无缓存也无种子 —— 模型看不见它们的工具（见上面黄字；补 skillpack\skills\references\mcp-lazy-seeds\<名字>.json）" }
                else { Add-Result 'MCP 通道自检' 'OK' '命令都在；懒启通道有缓存/种子兜底' }
            }
            catch { Add-Result 'MCP 通道自检' 'WARN' "解析 $hostMcp 失败：$_" }
        }
    }
    else { Add-Result 'MCP 通道' 'FAIL' '缺少 skills\scripts\mcp-status.ps1' }

    # 4b ★ 知识库（外部来源 + 症状索引）—— 2026-10-15 主人指出「知识库没接上」：
    #    实测 209 篇改编技术正文在（KB-INDEX 可复算），但「现象 → 该读哪一篇」的索引没人指向；而 KB-SOURCES 声称
    #    「原始副本留存于 <工具根>\kb-open-reverselab\」—— 那台机器上**其实是空的**。
    $kbOrig = Join-Path $env:REVERSE_TOOL_ROOT 'kb-open-reverselab'
    $kbIndex = Join-Path $RepoRoot 'skillpack\skills\field-journal\KB-INDEX.md'
    $kbOrigN = if (Test-Path -LiteralPath $kbOrig) { @(Get-ChildItem -LiteralPath $kbOrig -Recurse -Filter *.md -ErrorAction SilentlyContinue).Count } else { -1 }
    if (-not (Test-Path -LiteralPath $kbIndex)) {
        Add-Result '知识库' 'FAIL' '找不到 field-journal\KB-INDEX.md（现象→文档的症状索引）'
    }
    elseif ($kbOrigN -lt 0) {
        Add-Result '知识库' 'WARN' "症状索引在；但原始副本 $kbOrig 不在本机（GPL 溯源会断）—— 见 KB-SOURCES.md 的恢复办法"
    }
    else {
        Add-Result '知识库' 'OK' ("症状索引在；原始副本 $kbOrigN 篇（GPL 溯源可查）")
    }
    # 5 技能挂载（一份实体 N 个 junction）
    $rs = Join-Path $RepoRoot 'skillpack\skills\scripts\register-skills.ps1'
    if (Test-Path -LiteralPath $rs) {
        # ★ 2026-10-17：**必须显式传 -RepoRoot** —— 否则 -Doctor 会拿
        #   `$env:REVERSE_SKILL_ROOT` 指的那棵树当"预期根"，于是：
        #   · 环境变量指别处时，这一项查的是**别人**，本树的挂载错了也报 OK（假绿）；
        #   · 同一份 clone 在不同会话里会给出不同结论（实测出现过一次 OK / 之后稳定 WARN）。
        #   传了之后判据只与"本脚本所在这棵树"有关，与进程环境无关。
        $o = & powershell -NoProfile -ExecutionPolicy Bypass -File $rs -Doctor -RepoRoot $RepoRoot 2>&1
        if ($LASTEXITCODE -eq 0) { Add-Result '技能挂载' 'OK' '各智能体技能目录已挂上' }
        else { Add-Result '技能挂载' 'WARN' ("退出码 $LASTEXITCODE —— 有断链/MISMATCH；跑一次不带参数的 register-skills.ps1 重挂"); $o | Select-Object -Last 12 | ForEach-Object { Write-Host "      $_" -ForegroundColor DarkGray } }
    }
    else { Add-Result '技能挂载' 'FAIL' '缺少 register-skills.ps1' }

    # 6 技能卡与门禁清单
    # ★ 2026-10-16：这里原来只报顶层数（57），而实际 SKILL.md 总数是 63（+4 community wrapper
    #   +2 嵌套）。两个数都对但含义不同 —— 口径不写清，下一个读的人会当成"对不上"。
    #   现在两个数都报，且与 `branch-walk.py` 的复算口径**一致**。
    $skillsRoot = Join-Path $RepoRoot 'skillpack\skills'
    $cards = @(Get-ChildItem -LiteralPath $skillsRoot -Directory -ErrorAction SilentlyContinue |
        Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'SKILL.md') })
    $allCards = @(Get-ChildItem -LiteralPath $skillsRoot -Recurse -Filter SKILL.md -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -eq 'SKILL.md' -and $_.DirectoryName -ne $skillsRoot })
    if ($cards.Count -ge 40) {
        $nested = $allCards.Count - $cards.Count
        Add-Result '技能卡' 'OK' ("$($cards.Count) 张顶层 + $nested 张嵌套/包装 = 共 $($allCards.Count) 个 SKILL.md")
    }
    else { Add-Result '技能卡' 'FAIL' ("顶层只有 $($cards.Count) 张，异常") }

    $gates = Join-Path $RepoRoot 'skillpack\skills\tests\ci-gates.json'
    if (Test-Path -LiteralPath $gates) {
        try { $n = (Get-Content -LiteralPath $gates -Raw -Encoding UTF8 | ConvertFrom-Json).gates.Count; Add-Result '门禁清单' 'OK' "$n 道" }
        catch { Add-Result '门禁清单' 'FAIL' 'ci-gates.json 解析失败' }
    }
    else { Add-Result '门禁清单' 'FAIL' '缺少 ci-gates.json' }

    # 7 破甲卡（铁律：不许含工序 / 工具路径）
    $baseDir = Join-Path $RepoRoot 'kernel\04-console\cards\base'
    if (Test-Path -LiteralPath $baseDir) {
        $baseCards = @(Get-ChildItem -LiteralPath $baseDir -Filter *.md -ErrorAction SilentlyContinue)
        Add-Result '破甲卡' 'OK' ("$($baseCards.Count) 张（工序/工具路径判据见要求门 R1）")
    }
    else { Add-Result '破甲卡' 'WARN' '未找到 kernel\04-console\cards\base' }

    # 7b ★ 装机卡 vs 仓库卡的漂移。
    #   2026-10-15 审计实测：宿主 PERSONALITY.md 比仓库卡旧 6 行，而此前没任何门禁在看。
    # ★ P7（2026-10-15）：改由独立 Python 脚本做，直接 import hosts.py 的 HOSTS。
    #   不再在 relab2.ps1 里复制一份宿主表（PS 剪片把 omp 的 entry_base 解成空翻过车）。
    $py = $null
    foreach ($cand in @((Get-Command python -ErrorAction SilentlyContinue).Source,
                        (Get-Command py -ErrorAction SilentlyContinue).Source)) {
        if ($cand) { $py = $cand; break }
    }
    if ($py) {
        $o = & $py (Join-Path $RepoRoot 'skillpack\skills\scripts\check-card-drift.py') -Json 2>&1
        $rc = $LASTEXITCODE
        if ($rc -eq 0) {
            Add-Result '装机卡漂移' 'OK' '已装宿主入口文件与仓库卡逐行一致'
        }
        elseif ($rc -eq 11) {
            $o | Select-Object -Last 6 | ForEach-Object { Write-Host ('      ' + $_) -ForegroundColor Yellow }
            Add-Result '装机卡漂移' 'WARN' '部分宿主入口形态未核对（不宣称全宿主覆盖）——原回上方行'
        }
        elseif ($rc -eq 10) {
            $o | Select-Object -Last 12 | ForEach-Object { Write-Host ('      ' + $_) -ForegroundColor Yellow }
            Add-Result '装机卡漂移' 'WARN' '部分宿主入口文件与仓库卡不一致（原回上方行）'
        }
        else {
            $o | Select-Object -Last 8 | ForEach-Object { Write-Host ('      ' + $_) -ForegroundColor Red }
            Add-Result '装机卡漂移' 'WARN' "漂移检查本身跑失败（rc=$rc）"
        }
    }
    else {
        Add-Result '装机卡漂移' 'WARN' 'PATH 里没有 python，跳过'
    }

    # 8 要求门（自带控制组）
    $req = Join-Path $RepoRoot 'skillpack\skills\tests\verify-project-requirements.py'
    if (Test-Path -LiteralPath $req) {
        $py = (Get-Command python -ErrorAction SilentlyContinue).Source
        if (-not $py) { $py = (Get-Command py -ErrorAction SilentlyContinue).Source }
        if ($py) {
            $o = & $py $req 2>&1
            if ($LASTEXITCODE -eq 0) { Add-Result '要求门 R1-R13' 'OK' '全过（含控制组）' }
            else { Add-Result '要求门 R1-R13' 'FAIL' ("退出码 $LASTEXITCODE"); $o | Select-Object -Last 15 | ForEach-Object { Write-Host "      $_" -ForegroundColor DarkGray } }
        }
        else { Add-Result '要求门 R1-R13' 'WARN' 'PATH 里没有 python，跳过' }
    }
    else { Add-Result '要求门 R1-R13' 'FAIL' '缺少 verify-project-requirements.py' }

    # 9 行为门实跑台账（★ 2026-10-16）
    #   门禁只验"配置形状"，能力只有实跑能证明。两个行为门在 CI 里从不带 `--run`
    #   （要花钱开新会话），所以"能力就绪"此前没有任何自动证据。这里如实报
    #   「上次实跑是什么时候、过没过」—— 从未跑 / 超期就是 WARN，不装作绿。
    $runs = Join-Path $env:LOCALAPPDATA 'reverse-skill\behavior-runs.jsonl'
    $last = $null
    if (Test-Path -LiteralPath $runs) {
        foreach ($line in (Get-Content -LiteralPath $runs -Encoding UTF8 -ErrorAction SilentlyContinue)) {
            if (-not $line.Trim()) { continue }
            try { $last = $line | ConvertFrom-Json } catch { }
        }
    }
    if ($last) {
        $days = [int]((Get-Date) - [datetime]$last.ts).TotalDays
        if ($last.gate -eq 'test-trigger-rate') {
            $detail = "{0}：{1} 个技能 / {2} 条不过" -f $last.gate, $last.skills, $last.failed
        }
        elseif ($null -eq $last.'pass') {
            # ★ 2026-10-16：台账里 `pass: null` + `verified: false` 表示**本次未验**
            #   （运行失败/超时，见 KNOWN-BOUNDARIES 第 18 条）。原来直接插值成空串，
            #   显示成 `test-assault-behavior：/4`，看上去像"跑了但没结果"。
            $detail = "{0}：**未验**（上次运行失败/超时，不是 0 分）" -f $last.gate
        }
        else {
            $detail = "{0}：{1}/{2}" -f $last.gate, $last.'pass', $last.total
        }
        if ($days -le 30) {
            Add-Result '行为门实跑' 'OK' ("上次 $($last.ts)（$days 天前）· $detail")
        }
        else {
            Add-Result '行为门实跑' 'WARN' ("上次实跑 $($last.ts)（$days 天前，超 30 天）—— 能力证据已过期；跑 python skillpack\skills\tests\test-assault-behavior.py --run")
        }
    }
    else {
        Add-Result '行为门实跑' 'WARN' '从未实跑过 —— 行为门只验了「配置形状」，能力一条都没验；跑 python skillpack\skills\tests\test-assault-behavior.py --run'
    }

    # 9b ★ 2026-10-17：把换机手册里的「步 4 扫死路径」搬进 doctor（原属人工，实测只读）。
    #   换机手册 §11.5 把这一步列为「人工」，但审计实测它**纯只读、无凭据、无交互**
    #   （work/_full-audit/report-newmachine.md §5.2）—— 只是没人把它搬进脚本。
    #   现在 doctor 直接报「用户级环境变量死路径」与「PATH 死段」两个数：
    #   · 用户级变量指向不存在的盘符 → 换机后每个进程都继承这个脏值（本仓踩过 E:\nope-not-here）
    #   · PATH 里的死段 → Get-Command 对真工具返回空，进而让探测层误判「本机缺工具」
    #   只读：不删任何东西，只报数。要清理由人照 环境初始化.md §11.2 做。
    $deadEnv = @()
    try {
        $userEnv = Get-Item -LiteralPath 'HKCU:\Environment' -ErrorAction Stop
        foreach ($n in $userEnv.Property) {
            $v = (Get-ItemProperty -LiteralPath 'HKCU:\Environment' -ErrorAction SilentlyContinue).$n
            if ($v -and ($v -is [string]) -and $v -notmatch ';' -and $v -match '^[A-Za-z]:\\') {
                if (-not (Test-Path -LiteralPath $v)) { $deadEnv += "$n=$v" }
            }
        }
    } catch { }
    $deadPath = @($env:PATH -split ';' | Where-Object { $_ -match '^[A-Za-z]:\\' -and -not (Test-Path -LiteralPath $_) })
    if ($deadEnv.Count -eq 0 -and $deadPath.Count -eq 0) {
        Add-Result '死路径' 'OK' '用户级环境变量死路径 0 条 · PATH 死段 0 段'
    }
    else {
        if ($deadEnv.Count) { Write-Host ('      用户级死变量: ' + ($deadEnv -join ', ')) -ForegroundColor Yellow }
        if ($deadPath.Count) { Write-Host ('      PATH 死段: ' + (($deadPath | Select-Object -First 5) -join ', ')) -ForegroundColor Yellow }
        Add-Result '死路径' 'WARN' ("用户级变量 $($deadEnv.Count) 条 · PATH 死段 $($deadPath.Count) 段 —— 换机后会让探测层误判「缺工具」，见 环境初始化.md §11.2")
    }

    # 9c ★ 2026-10-17：换机手册里另外两步「假人工」（实测均只读、无凭据）也搬进来。
    #   · 步 6「查宿主家目录」：判「哪家宿主真装了」—— 只看目录在不在，不读内容。
    #   · 步 9「清旧状态」：**只清点、不删**（列出会被旧机污染的目录是否存在）。
    #     真删要人照 环境初始化.md §11.2 逐条确认；这里只让"有残留"不再隐形。
    try {
        $hostDirs = @()
        foreach ($h in @('.omp', '.agents', '.config\agents', '.claude', '.copilot', '.codex', '.cursor', '.gemini', '.pi', '.roo', '.openhands')) {
            if (Test-Path -LiteralPath (Join-Path $env:USERPROFILE $h)) { $hostDirs += $h }
        }
        if ($hostDirs.Count -eq 0) {
            Add-Result '宿主家目录' 'WARN' '一个宿主目录都没找到（本机还没接任何智能体？）'
        }
        else {
            Add-Result '宿主家目录' 'OK' ("存在 $($hostDirs.Count) 个：$($hostDirs -join ', ')")
        }
    } catch { Add-Result '宿主家目录' 'WARN' "扫描失败：$_" }

    $stale = @()
    foreach ($rel in @('skillpack\.hub\tools.local.json', 'kernel\state', 'kernel\04-console\TEMP',
                       'kernel\06-verify\TEMP', 'kernel\07-kernel-sweep', 'work', '.candidates',
                       'kernel\safebox', 'kernel\04-console\safebox', 'kernel\04-console\hostlist\custom-hosts.json')) {
        $full = Join-Path $RepoRoot $rel
        if (Test-Path -LiteralPath $full) { $stale += $rel }
    }
    if ($stale.Count -eq 0) {
        Add-Result '旧状态清点' 'OK' '10 个易污染目录一个都没有（干净）'
    }
    else {
        Write-Host ('      存在（换机前应逐条确认是否该清）: ' + ($stale -join ', ')) -ForegroundColor DarkGray
        Add-Result '旧状态清点' 'OK' ("$($stale.Count)/10 个易污染目录存在 —— 换机时照 环境初始化.md §11.2 逐条确认（doctor 只清点、不删）")
    }

    # 10 换机剩余人工项（★ 2026-10-16）
    #   一键路径只代劳 1–3 步 + MCP 注册；凭据与宿主入口文件按设计归人做。
    #   归人做**不等于**可以不报：不报的话 doctor 会把"还差一步"说成全绿。
    #   这里查的是**登没登**，不读任何凭据内容。
    try {
        $ghOut = & gh auth status 2>&1
        if ($LASTEXITCODE -eq 0) { Add-Result 'GitHub CLI 登录' 'OK' 'gh auth status 通过（取 issue/PR/Actions 日志可用）' }
        else { Add-Result 'GitHub CLI 登录' 'WARN' '未登录 —— 跑 gh auth login；否则查 PR/issue/Actions 日志会失败' }
    }
    catch { Add-Result 'GitHub CLI 登录' 'WARN' 'gh 不在 PATH —— 按 环境初始化.md §11.1-E 补凭据' }

    # 汇总
    $fail = @($Results | Where-Object { $_.结果 -eq 'FAIL' }).Count
    $warn = @($Results | Where-Object { $_.结果 -eq 'WARN' }).Count
    Write-Host ''
    if ($fail -eq 0 -and $warn -eq 0) {
        Write-Host ("就绪：全部通过（{0} 项）" -f $Results.Count) -ForegroundColor Green
        Write-Host '注意：doctor 只证明「本机配置就绪」，不证明「能力就绪」。能力只由真实验收证明。' -ForegroundColor DarkGray
        return 0
    }
    if ($fail -eq 0) {
        # ★ 2026-10-15：以前这里也印「全部通过」，等于把 WARN 说成全绿（审计实测：异地克隆里
        #   两个环境变量都没设，仍报「就绪：全部通过（10 项，0 项警告）」退出码 0）。改掉。
        Write-Host ("就绪，但带 {0} 项警告 —— 不是全绿。先看上面 WARN 的那几行。" -f $warn) -ForegroundColor Yellow
        return 0
    }
    Write-Host ("未就绪：{0} 项 FAIL，{1} 项 WARN —— 按上面的 FAIL 项处理后重跑。" -f $fail, $warn) -ForegroundColor Red
    return 1
}

# ---------------------------------------------------------------- setup / update
function Invoke-Setup {
    Write-Head 'relab2 setup —— 一键接入（幂等，可 -DryRun 预览）'
    $rc = 0

    Invoke-Step -File 'relab2-root.ps1' -ArgList @() -Label '仓根定位' | Out-Host
    if ($LASTEXITCODE -ne 0 -and -not $DryRun) { $rc = 1 }

    $a = @()
    if ($DryRun) { $a += '-DryRun' }
    # ★ 2026-10-18：转发 -ToolRoot（façade 以前不认这个参数，只有 C: 盘的新机必然失败）
    if ($ToolRoot) { $a += @('-ToolRoot', $ToolRoot) }
    Invoke-Step -File 'setup.ps1' -ArgList $a -Label '环境变量 + 自检' | Out-Host
    if ($LASTEXITCODE -ne 0 -and -not $DryRun) { $rc = 1 }

    $b = @()
    if ($DryRun) { $b += '-WhatIf' }
    # ★ 2026-10-17（换机真空实测抓到的真缺陷）：**必须显式传 -RepoRoot**。
    #   register-skills.ps1 的根解析顺序是「-Given → -RepoRoot\skillpack\skills →
    #   $env:REVERSE_SKILL_ROOT\skillpack\skills → 脚本自身位置上溯」。
    #   不传 -RepoRoot 时，只要环境变量指向**另一棵树**（换机/两份 clone/同机移动仓库），
    #   它就把技能联接挂到那**另一棵树**上 —— 而 setup 刚刚才把变量写成这棵树。
    #   实测：在 C:\relab2_clean_test 里跑 setup（进程里 REVERSE_SKILL_ROOT 仍是 C:\relab2），
    #   跑完 252 处联接全部 MISMATCH 指向 C:\relab2，而 `doctor` 那一项也报不出来。
    #   （MCP 注册本来就传了 --skill-root $RepoRoot，所以 MCP 路径一直是对的 —— 两者不一致。）
    $b += @('-RepoRoot', $RepoRoot)
    Invoke-Step -File 'skillpack\skills\scripts\register-skills.ps1' -ArgList $b -Label '技能挂载（一份实体 N 个联接）' | Out-Host
    if ($LASTEXITCODE -ne 0 -and -not $DryRun) { $rc = 1 }

    # ---- MCP 一键注册（幂等 + 备份 + 干跑）----
    $mcpReg = Join-Path $RepoRoot 'skillpack\skills\scripts\register-mcp.py'
    if (Test-Path -LiteralPath $mcpReg) {
        $py = $null
        foreach ($cand in @(
                (Join-Path $env:REVERSE_TOOL_ROOT 'runtime\python-venv\Scripts\python.exe'),
                (Join-Path $env:REVERSE_TOOL_ROOT 'runtime\angr-mcp-venv\Scripts\python.exe'))) {
            if ($cand -and (Test-Path -LiteralPath $cand)) { $py = $cand; break }
        }
        if (-not $py) { $py = (Get-Command python -ErrorAction SilentlyContinue).Source }
        if ($py) {
            $mcpArgs = @($mcpReg, '--skill-root', $RepoRoot)
            if ($DryRun) { $mcpArgs += '--dry-run' }
            Write-Host '  MCP 注册（6 条通道，幂等 + 自动备份）' -ForegroundColor DarkGray
            # ★ 显式捕获再打印：直接 `& $py @args` 的输出在这个 PowerShell 里会被吞掉
            #   （2026-10-15 实测：调用方看不到任何输出，等于静默失败）。捕获 + 原样回显，错误也看得见。
            $mcpOut = & $py @mcpArgs 2>&1 | Out-String
            $mcpRc = $LASTEXITCODE
            if ($mcpOut.Trim()) { Write-Host $mcpOut.TrimEnd() }
            if ($mcpRc -ne 0 -and -not $DryRun) {
                Add-Result 'MCP 注册' 'WARN' "register-mcp.py 退出码 $mcpRc —— 见上方输出"
            }
        }
        else {
            Add-Result 'MCP 注册' 'WARN' 'PATH 与工具根里都没找到 python，跳过（见 环境初始化.md §11.1-B 第 10 条）'
        }
    }
    else {
        Add-Result 'MCP 注册' 'WARN' "缺少 $mcpReg，跳过"
    }

    Write-Host ''
    Write-Host '  ── 换机剩下的（本脚本不代做，因为写的是「你的机器状态」）──────────────' -ForegroundColor Yellow
    Write-Host '  □ 1. 载入卡片：开 kernel\04-console\start-console.bat → 选智能体 → 勾三段 → 载入' -ForegroundColor Gray
    Write-Host '        （它会把中枢标记块 / 底模卡 / 客套指引卡写进宿主的入口文件，并留备份）' -ForegroundColor DarkGray
    Write-Host '  □ 2. 凭据：ssh 私钥 / API key / 商业 license —— 按 环境初始化.md §11.1-E 逐条补' -ForegroundColor Gray
    Write-Host '  □ 3. 清旧状态：删掉会被旧机污染的目录（见 环境初始化.md §11.2）' -ForegroundColor Gray
    Write-Host '  □ 4. 登 GitHub CLI：gh auth status 不自证就 gh auth login' -ForegroundColor Gray
    Write-Host '  □ 5. 确认新机上没有上一台留下的计划任务/开机自启（环境初始化.md §11 的 D 组）' -ForegroundColor Gray
    Write-Host '  ────────────────────────────────────────────────────────────────' -ForegroundColor Yellow

    if (-not $DryRun) {
        Write-Host ''
        Write-Host '  跑完请重跑一次 doctor 确认：' -ForegroundColor Cyan
        Write-Host '    powershell -NoProfile -ExecutionPolicy Bypass -File relab2.ps1 doctor' -ForegroundColor Cyan
    }
    return $rc
}

function Invoke-Update {
    Write-Head 'relab2 update —— 换机 / 升级同一条'
    if ($DryRun) { Write-Host '  [DryRun] git -C <仓根> pull --ff-only' -ForegroundColor Yellow }
    else {
        & git -C $RepoRoot pull --ff-only
        if ($LASTEXITCODE -ne 0) { Write-Host '  git pull 未成功（离线或有本地改动）—— 继续跑 setup。' -ForegroundColor Yellow }
    }
    return (Invoke-Setup)
}

function Show-Help {
    Write-Host @'
relab2 —— 本仓库唯一门面

  relab2 doctor          本机现在能不能干活（不改配置；会刷新机器状态快照。退出码 0 = 就绪）
  relab2 setup           一键接入：仓根定位 → 环境变量 → 技能挂载（幂等）
  relab2 setup -DryRun   只打印将要执行的每一行，不改任何东西
  relab2 update          换机/升级：git pull → 重跑 setup
  relab2 known           看「已知边界」：本机/本项目的已知缺陷与待办（读 docs\KNOWN-BOUNDARIES.md）

就绪之后：
  · 干活入口看 START-HERE.md
  · 卡片融合 / 跨智能体接入 开 kernel\04-console\start-console.bat
  · 想知道「到底做完没」→ 跑门禁与核验（入口见 docs\PROJECT-MAP.md）
  · 想确认某件事是不是已知问题 → relab2 known（不要靠猜、不要靠记忆）
'@
}

function Invoke-Known {
    # ★ 2026-10-16：主人两次问过「怎么看已知边界」。答案应当是**一条命令**，不是"去翻文档"。
    #   本命令只读、不改任何东西：打印 KNOWN-BOUNDARIES.md 的每条编号条目（缺陷/边界/约定），
    #   并给出全文路径。--Json 时输出结构化清单。
    $p = Join-Path $RepoRoot 'docs\KNOWN-BOUNDARIES.md'
    if (-not (Test-Path -LiteralPath $p)) {
        # ★ 2026-10-16：这里**不能**用 `return 2` —— PowerShell 的 `return 2` 会把 `2` 打进
        #   **输出流**（消费者会读到一个孤零零的 `2`）。要退码就直接 `exit`。
        Write-Host "找不到 $p（仓库不完整？）" -ForegroundColor Red
        exit 2
    }
    $lines = Get-Content -LiteralPath $p -Encoding UTF8
    # 条目行形如： | 13 | **标题** | 证据 | 现状 |
    $items = @($lines | Where-Object { $_ -match '^\|\s*\d+\s*\|' })
    if ($Json) {
        $out = @()
        foreach ($l in $items) {
            $c = $l.Trim('|').Split('|')
            if ($c.Count -ge 2) {
                $out += [pscustomobject]@{ n = $c[0].Trim(); title = ($c[1] -replace '\*\*', '').Trim() }
            }
        }
        $out | ConvertTo-Json -Depth 3
        return                                   # ★ 不写 `return 0`（会把 0 打进输出流）
    }
    Write-Head "已知边界（docs\KNOWN-BOUNDARIES.md）"
    Write-Host ("  共 {0} 条编号条目。" -f $items.Count) -ForegroundColor Gray
    Write-Host "  每条的完整证据与现状见文件正文；下面只列编号 + 标题。" -ForegroundColor DarkGray
    Write-Host ""
    foreach ($l in $items) {
        $c = $l.Trim('|').Split('|')
        if ($c.Count -ge 2) {
            $n = $c[0].Trim().PadLeft(3)
            $t = ($c[1] -replace '\*\*', '').Trim()
            if ($t.Length -gt 88) { $t = $t.Substring(0, 88) + '…' }
            Write-Host ("  {0}. {1}" -f $n, $t)
        }
    }
    Write-Host ""
    Write-Host ("  全文： {0}" -f $p) -ForegroundColor Cyan
    Write-Host "  ★ 遇到「是不是已知问题」先查这里，别猜、别凭记忆。" -ForegroundColor Yellow
    # 自然结束即可；**不写 `return 0`**（会把 0 打进输出流，污染 `known -Json` 的 JSON）。
}

switch ($Command) {
    'doctor' { exit (Invoke-Doctor) }
    # ★ 2026-10-16：**不能**写成 `exit (Invoke-Known)` —— `(…)` 会把函数的**输出流**捕获成
    #   `exit` 的参数，于是 `known -Json` 的 `ConvertTo-Json` 结果被整段吞掉（实测：输出为空）。
    #   `doctor` 没暴露这问题，是因为它只走 `Write-Host`（不经管道）。这里改成先跑完再 exit。
    'known' { Invoke-Known; exit 0 }
    'setup' { exit (Invoke-Setup) }
    'update' { exit (Invoke-Update) }
    default { Show-Help; exit 0 }
}
