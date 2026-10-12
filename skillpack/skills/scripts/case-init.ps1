#Requires -Version 5.1
# Initialize work/<case>/ with scope, timeline, workitems (reverse-skill ops contract).
# Bare invocation keeps pending/offline defaults.
# Ready-to-act example:
#   powershell -File skills/scripts/case-init.ps1 -Hint "web pentest" -CaseName my-case `
#     -AuthGranted -TargetUrl "https://app.example/" -NetworkProfile authorized_target_only
# Offline sample ready-to-act example:
#   powershell -File skills/scripts/case-init.ps1 -Hint "offline apk" -CaseName my-sample `
#     -Preset offline-sample -Sample ".\app.apk"
param(
    [string] $Hint = '',
    [string] $CaseName = '',
    [string] $PackageRoot = '',
    [AllowEmptyString()]
    [string] $ProjectRoot = '',
    [switch] $AuthGranted,
    [string] $AuthStatus = '',
    [string] $AuthBasis = 'own_system',
    [string] $EvidenceOfAuth = '',
    [string] $TargetUrl = '',
    [string] $Sample = '',
    [string] $OldUpstream = '',
    [string] $NewUpstream = '',
    [string] $OurOldBuild = '',
    [string] $Preset = '',
    [string[]] $InScopeAssets = @(),
    [string] $NetworkProfile = '',
    [switch] $ReadyForAct
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

$scriptDir = $PSScriptRoot
if (-not $scriptDir) { $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path }
$skillsRoot = Split-Path -Parent $scriptDir
if (-not $PackageRoot) { $PackageRoot = Split-Path -Parent $skillsRoot }
. (Join-Path (Join-Path $scriptDir 'lib') 'WorkRoot.ps1')
. (Join-Path (Join-Path $scriptDir 'lib') 'HostRuntime.ps1')
$HostExe = Resolve-ReverseHostExe
$requestedProjectRoot = if (-not [string]::IsNullOrWhiteSpace($ProjectRoot)) {
    $ProjectRoot
} elseif ($PSBoundParameters.ContainsKey('PackageRoot')) {
    $PackageRoot
} else {
    ''
}
$projectRoot = Resolve-ReverseProjectRoot -RequestedRoot $requestedProjectRoot

if (-not [string]::IsNullOrWhiteSpace($Sample)) {
    try {
        $Sample = [System.IO.Path]::GetFullPath($Sample)
    } catch {
        throw "Invalid -Sample path '$Sample': $($_.Exception.Message)"
    }
    if (-not (Test-Path -LiteralPath $Sample -PathType Leaf)) {
        throw "Local -Sample file not found: $Sample"
    }
}

# Cross-platform case presets. Keep semantics aligned with case-init.sh.
$rebuildMode = $false
$updateMode = $false
$presetNormalized = $Preset.Trim().ToLowerInvariant()
if ($presetNormalized -in @('offline-sample', 'own-sample', 'local-sample')) {
    $AuthGranted = $true
    $AuthStatus = 'granted'
    $AuthBasis = 'own_system'
    if ([string]::IsNullOrWhiteSpace($NetworkProfile)) { $NetworkProfile = 'offline' }
    if ([string]::IsNullOrWhiteSpace($EvidenceOfAuth)) {
        $EvidenceOfAuth = 'preset:offline-sample (owner-operated local file)'
    }
} elseif ($presetNormalized -in @('ctf-public', 'ctf')) {
    $AuthGranted = $true
    $AuthStatus = 'granted'
    $AuthBasis = 'ctf_public'
    if ([string]::IsNullOrWhiteSpace($NetworkProfile)) { $NetworkProfile = 'authorized_target_only' }
    if ([string]::IsNullOrWhiteSpace($EvidenceOfAuth)) { $EvidenceOfAuth = 'preset:ctf-public' }
} elseif ($presetNormalized -in @('own-system', 'lab-only')) {
    $AuthGranted = $true
    $AuthStatus = 'granted'
    $AuthBasis = 'own_system'
    if ([string]::IsNullOrWhiteSpace($NetworkProfile)) { $NetworkProfile = 'lab_only' }
    if ([string]::IsNullOrWhiteSpace($EvidenceOfAuth)) { $EvidenceOfAuth = 'preset:own-system/lab' }
} elseif ($presetNormalized -eq 'rebuild') {
    # 复刻交付路径：与 offline-sample 同档（owner-operated 本地样本），但额外落 rebuild.md
    # 对账表 + baseline/ + diff/ 三样。授权门与 offline-sample 一致，不放松任何硬门。
    $AuthGranted = $true
    $AuthStatus = 'granted'
    $AuthBasis = 'own_system'
    $rebuildMode = $true
    if ([string]::IsNullOrWhiteSpace($NetworkProfile)) { $NetworkProfile = 'offline' }
    if ([string]::IsNullOrWhiteSpace($EvidenceOfAuth)) {
        $EvidenceOfAuth = 'preset:rebuild (owner-operated local sample; rebuild delivery case)'
    }
} elseif ($presetNormalized -eq 'update') {
    # 复刻更新路径：在已存在的 rebuild case 上开更新阶段。授权档与 rebuild 同档
    # （owner-operated 本地样本 + offline）。必须显式传 -Preset update 才出现。
    # 无 rebuild.md 的目录明确报错（不许静默生成）；三份指纹 hash 全填才落 update.md。
    $AuthGranted = $true
    $AuthStatus = 'granted'
    $AuthBasis = 'own_system'
    $updateMode = $true
    if ([string]::IsNullOrWhiteSpace($NetworkProfile)) { $NetworkProfile = 'offline' }
    if ([string]::IsNullOrWhiteSpace($EvidenceOfAuth)) {
        $EvidenceOfAuth = 'preset:update (owner-operated local sample; rebuild update case)'
    }
} elseif (-not [string]::IsNullOrWhiteSpace($Preset)) {
    throw ("Invalid -Preset '{0}'. Allowed: offline-sample|ctf-public|own-system|rebuild|update" -f $Preset)
}

if (-not $CaseName) {
    $slug = if ($Hint) {
        ($Hint.ToLowerInvariant() -replace '[^a-z0-9]+', '-').Trim('-')
    } else { 'case' }
    if ($slug.Length -gt 32) { $slug = $slug.Substring(0, 32).TrimEnd('-') }
    $CaseName = '{0}-{1}' -f (Get-Date -Format 'yyyyMMdd-HHmmss'), $slug
}

# CaseName is a directory name, not a path. Keep every case under projectRoot/work.
# The pattern allows localized names but excludes Windows path syntax and names that
# Windows would normalize into a dot segment (for example, '.. ' or 'case.').
if ([string]::IsNullOrWhiteSpace($CaseName) -or
    $CaseName -notmatch '^[\p{L}\p{N}][\p{L}\p{N}._ -]{0,79}$' -or
    $CaseName -match '[.\s]$') {
    throw "Invalid -CaseName '$CaseName'. Use a 1-80 character directory name beginning with a letter or number; path separators, dot segments, trailing dots/spaces, control characters, and wildcard characters are not allowed."
}
if (-not [string]::IsNullOrWhiteSpace($NetworkProfile) -and
    $NetworkProfile.Trim().ToLowerInvariant() -notin @('offline', 'lab_only', 'authorized_target_only', 'unrestricted_lab', 'lab', 'authorized', 'auth', 'offline_only')) {
    throw "Invalid -NetworkProfile '$NetworkProfile'. Allowed: offline, lab_only, authorized_target_only, unrestricted_lab (aliases: lab, authorized, auth, offline_only)."
}

$workRoot = Join-Path $projectRoot 'work'
$caseRoot = Join-Path $workRoot $CaseName

# -Preset update：只在已存在的 rebuild case 上开更新阶段。case 根必须有 rebuild.md
# （初逆的对账表），否则明确报错 —— 不许静默生成一个空 update case。
# update 模式不重写 scope/timeline/workitems/README：那是既有 case 的状态，不是新 case。
if ($updateMode) {
    $rebuildContract = Join-Path $caseRoot 'rebuild.md'
    if (-not (Test-Path -LiteralPath $rebuildContract -PathType Leaf)) {
        throw ("-Preset update requires an existing rebuild case: {0} not found. Run initial rebuild first (case-init -Preset rebuild), then re-run with -CaseName <case> -Preset update." -f $rebuildContract)
    }
    # 版本指纹三份都要填，且各带 64-hex SHA256 —— 这是更新阶段的旧锚/新锚/冻锚。
    foreach ($fingerprint in @(
        @('OldUpstream', $OldUpstream),
        @('NewUpstream', $NewUpstream),
        @('OurOldBuild', $OurOldBuild)
    )) {
        $fpName = $fingerprint[0]
        $fpVal = $fingerprint[1]
        if ([string]::IsNullOrWhiteSpace($fpVal) -or $fpVal -notmatch '(?i)[0-9a-f]{64}') {
            throw ("-Preset update requires all three version fingerprints (path | version | sha256:<64hex>): -{0} missing or hash-less (got '{1}')" -f $fpName, $fpVal)
        }
    }
    $updateTemplate = Join-Path (Join-Path $skillsRoot 'templates') 'update.md'
    if (-not (Test-Path -LiteralPath $updateTemplate -PathType Leaf)) {
        throw ("update template missing: {0}" -f $updateTemplate)
    }
    [void](New-Item -ItemType Directory -Force -Path (Join-Path $caseRoot 'freeze'))
    [void](New-Item -ItemType Directory -Force -Path (Join-Path $caseRoot 'diff-update'))
    # 骨架 + 已校验的三份指纹直接落进 target 段；three_lines / function_delta 留给 impl 填。
    # ReadAllText/WriteAllText + 正则替换：模板换行原样保留（不引入 CRLF 漂移）。
    $tplText = [System.IO.File]::ReadAllText($updateTemplate, [System.Text.Encoding]::UTF8)
    $tplText = $tplText -replace '(?m)^- case:.*$', ("- case: " + $CaseName)
    $tplText = $tplText -replace '(?m)^- old_upstream:.*$', ("- old_upstream: " + $OldUpstream)
    $tplText = $tplText -replace '(?m)^- new_upstream:.*$', ("- new_upstream: " + $NewUpstream)
    $tplText = $tplText -replace '(?m)^- our_old_build:.*$', ("- our_old_build: " + $OurOldBuild)
    $utf8NoBom = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllText((Join-Path $caseRoot 'update.md'), $tplText, $utf8NoBom)
    Write-Host ("UPDATE -> {0}" -f $caseRoot) -ForegroundColor Green
    Write-Host 'update.md written; freeze/ + diff-update/ ready; fingerprints validated'
    Write-Host 'NEXT: freeze first — snapshot rebuild.md + diff/ + deliverable sha256 into freeze/<our_version>/; then fill three_lines + function_delta; gate detail: skills/ops/rebuild-gates.md [更新阶段]'
    exit 0
}

$dirs = @('evidence', 'notes', 'report')
if ($rebuildMode) { $dirs += @('baseline', 'diff') }
New-Item -ItemType Directory -Force -Path $caseRoot | Out-Null
foreach ($d in $dirs) {
    New-Item -ItemType Directory -Force -Path (Join-Path $caseRoot $d) | Out-Null
}

# Resolve auth / network / assets
# Priority: explicit -AuthStatus (only if bound) > -AuthGranted > pending.
# Never let a stray positional string overwrite AuthGranted.
$authStatusResolved = 'pending'
if ($AuthGranted) { $authStatusResolved = 'granted' }
if ($PSBoundParameters.ContainsKey('AuthStatus') -and -not [string]::IsNullOrWhiteSpace($AuthStatus)) {
    $candidate = $AuthStatus.Trim().ToLowerInvariant()
    $allowedAuth = @('pending', 'granted', 'denied', 'unknown')
    if ($allowedAuth -contains $candidate) {
        $authStatusResolved = $candidate
    } else {
        Write-Host ("WARN: ignoring invalid -AuthStatus '{0}' (allowed: pending|granted|denied|unknown)" -f $AuthStatus) -ForegroundColor Yellow
        # if user also passed AuthGranted, keep granted; else stay pending
    }
}

$evidenceAuth = if (-not [string]::IsNullOrWhiteSpace($EvidenceOfAuth)) {
    $EvidenceOfAuth
} elseif ($AuthGranted -or $authStatusResolved -eq 'granted') {
    'cli-flag AuthGranted or AuthStatus=granted'
} else {
    'FILL_ME'
}

$assets = New-Object System.Collections.Generic.List[string]
if (-not [string]::IsNullOrWhiteSpace($TargetUrl)) { [void]$assets.Add($TargetUrl.Trim()) }
if (-not [string]::IsNullOrWhiteSpace($Sample) -and -not $assets.Contains($Sample.Trim())) {
    [void]$assets.Add($Sample.Trim())
}
foreach ($a in @($InScopeAssets)) {
    if (-not [string]::IsNullOrWhiteSpace($a) -and -not $assets.Contains($a.Trim())) {
        [void]$assets.Add($a.Trim())
    }
}
# Also accept host-only tokens that look like domains/IPs from TargetUrl leftovers
if ($assets.Count -eq 0 -and $Hint -match 'https?://([^\s/]+)') {
    [void]$assets.Add(('https://{0}/' -f $Matches[1]))
}

$networkMode = 'offline'
if (-not [string]::IsNullOrWhiteSpace($NetworkProfile)) {
    $networkMode = $NetworkProfile.Trim()
} elseif ($assets.Count -gt 0 -and $authStatusResolved -eq 'granted' -and [string]::IsNullOrWhiteSpace($Sample)) {
    # Authorized network targets default to target-only. Explicit local samples remain offline.
    $networkMode = 'authorized_target_only'
}
# normalize common aliases
$netAliases = @{
    'lab' = 'lab_only'
    'authorized' = 'authorized_target_only'
    'auth' = 'authorized_target_only'
    'offline_only' = 'offline'
}
if ($netAliases.ContainsKey($networkMode.ToLowerInvariant())) {
    $networkMode = $netAliases[$networkMode.ToLowerInvariant()]
}
$allowedNetworkModes = @('offline', 'lab_only', 'authorized_target_only', 'unrestricted_lab')
if ($networkMode -notin $allowedNetworkModes) {
    throw "Invalid -NetworkProfile '$NetworkProfile'. Allowed: offline, lab_only, authorized_target_only, unrestricted_lab (aliases: lab, authorized, auth, offline_only)."
}

# ready_for_act requires auth granted + assets. Network targets need a non-offline
# profile; an explicit local sample is valid in offline mode. -ReadyForAct never
# bypasses auth or scope.
$ready = $false
$netAllowsAct = ($networkMode -ne 'offline' -and -not [string]::IsNullOrWhiteSpace($networkMode))
$offlineSampleReady = ($networkMode -eq 'offline' -and -not [string]::IsNullOrWhiteSpace($Sample) -and $assets.Count -gt 0)
if ($authStatusResolved -eq 'granted' -and $assets.Count -gt 0 -and ($netAllowsAct -or $offlineSampleReady)) {
    $ready = $true
} elseif ($ReadyForAct) {
    if ($authStatusResolved -ne 'granted') {
        Write-Host 'WARN: -ReadyForAct ignored because auth.status is not granted' -ForegroundColor Yellow
    } elseif ($assets.Count -eq 0) {
        Write-Host 'WARN: -ReadyForAct ignored because in_scope.assets is empty' -ForegroundColor Yellow
    } elseif (-not $netAllowsAct -and -not $offlineSampleReady) {
        Write-Host 'WARN: -ReadyForAct ignored because offline mode requires an explicit -Sample' -ForegroundColor Yellow
    }
}

# Optional master-route for primary skill
$primary = 'reverse-engineering/SKILL.md'
$primaryId = 'R0'
$routeScript = Join-Path $scriptDir 'master-route.ps1'
if ((Test-Path $routeScript) -and $Hint) {
    $tmpBase = if ($env:TEMP) { $env:TEMP } else { [System.IO.Path]::GetTempPath() }
    $tmp = Join-Path $tmpBase ("case-init-route-" + [guid]::NewGuid().ToString('n'))
    try {
        & $HostExe -NoProfile -ExecutionPolicy Bypass -File $routeScript -Hint $Hint -OutDir $tmp 2>$null | Out-Null
        $scopeRoute = Join-Path $tmp 'route-scope.md'
        if (Test-Path $scopeRoute) {
            . (Join-Path $scriptDir 'lib/RouteScope.ps1')
            $rt = Get-Content $scopeRoute -Raw -Encoding UTF8
            $parsed = Get-ReverseRouteScopeFields -Text $rt
            if ($parsed.Skill) { $primary = $parsed.Skill }
            if ($parsed.Id) { $primaryId = $parsed.Id }
        }
    } finally {
        Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
    }
}

$created = Get-Date -Format 'o'
if ($assets.Count -gt 0) {
    $assetsBlock = ($assets | ForEach-Object { "  - $_" }) -join [Environment]::NewLine
} else {
    $assetsBlock = '  []'
}

$checkAuth = if ($authStatusResolved -eq 'granted') { '[x]' } else { '[ ]' }
$checkScope = if ($assets.Count -gt 0) { '[x]' } else { '[ ]' }
$checkNet = if ($networkMode -and $networkMode -ne '') { '[x]' } else { '[ ]' }
$readyStr = if ($ready) { 'true' } else { 'false' }
$timelineNext = if ($ready) {
    'open PRIMARY SKILL.md and ACT within scope'
} else {
    'fill scope auth + in_scope; set ready_for_act'
}
$timelineSummary = if ($ready) {
    'case directory created; scope ready_for_act=true'
} else {
    'case directory created; scope pending auth'
}

$scope = @"
# Case Scope

## meta
- case_id: $CaseName
- created: $created
- operator: local
- project_root: $projectRoot
- primary_skill: $primary
- primary_id: $primaryId
- lead_role: lead
- specialist_roles: []
- hint: $Hint
- preset: $(if ([string]::IsNullOrWhiteSpace($Preset)) { 'none' } else { $Preset })

## auth
- status: $authStatusResolved
- basis: $AuthBasis
- evidence_of_auth: $evidenceAuth
- MUST NOT proceed if status != granted

## in_scope
- assets:
$assetsBlock
- surfaces: []
- activities: []

## out_of_scope
- assets: []
- activities: [dos, phishing_real_users, unrestricted_exfil]

## network_profile
- mode: $networkMode
- notes: |
    offline | lab_only | authorized_target_only | unrestricted_lab
    Change mode only after auth.status = granted.

## deliverables
- report: true
- field_journal: true
- diagrams: true
- timeline: true

## constraints
- timebox: {}
- stealth: low
- data_handling: anonymize

## signoff
- ready_for_act: $readyStr
- checklist:
  - $checkAuth auth.status = granted
  - $checkScope in_scope.assets non-empty OR offline sample path set
  - $checkNet network_profile.mode chosen
  - [ ] out_of_scope reviewed
  - [ ] roles assigned (see skills/ops/role-map.md)

## ops_refs
- skills/ops/scope-contract.md
- skills/ops/evidence-finding-path.md
- skills/ops/role-map.md
- skills/ops/timeline-workitem.md
- skills/ops/IDENTITY.md
"@

# -Preset rebuild 时 deliverables 段多一行标记。插在 here-string 之后，行尾沿用
# 文档自身的换行（CRLF 或 LF 都行），保证不传该预设时 scope.md 与改前逐字节一致。
if ($rebuildMode) {
    $scope = $scope -replace '(?m)^(- timeline: true)(\r?\n)', '${1}${2}- rebuild: true${2}'
}

$timeline = @"
# Timeline (append-only)

## $created | lead | init
- action: case-init
- command_or_ref: skills/scripts/case-init.ps1
- result_summary: $timelineSummary
- artifacts: [scope.md, workitems.md]
- evidence_ids: []
- decision_delta: [case_initialized]
- carry_forward_refs: [scope.md]
- next: $timelineNext
"@

$workitems = @"
# Work Items

| ID | title | role | targets | surface | status | evidence | notes |
|----|-------|------|---------|---------|--------|----------|-------|
| WI-001 | Establish scope and auth | lead | case | process | in_progress | | |

## Coverage
- [ ] Recon/analysis complete for in_scope assets
- [ ] Critical/High candidates triaged (or N/A for pure RE)
- [ ] Validated findings have Evidence (E-*)
- [ ] Path documented (attack/call/solve)
- [ ] Timeline continuous across major phases
- [ ] Report via docs-generator
- [ ] field-journal anonymized

## Refs
- skills/ops/timeline-workitem.md
- skills/ops/evidence-finding-path.md
"@

$utf8 = New-Object System.Text.UTF8Encoding $true
[System.IO.File]::WriteAllText((Join-Path $caseRoot 'scope.md'), $scope, $utf8)
[System.IO.File]::WriteAllText((Join-Path $caseRoot 'timeline.md'), $timeline, $utf8)
[System.IO.File]::WriteAllText((Join-Path $caseRoot 'workitems.md'), $workitems, $utf8)

# -Preset rebuild：从 skills/templates/rebuild.md 拷对账表骨架进 case。
# 只读模板、写 case；不传该预设时本块不执行。
if ($rebuildMode) {
    $rebuildTemplate = Join-Path (Join-Path $skillsRoot 'templates') 'rebuild.md'
    if (Test-Path -LiteralPath $rebuildTemplate) {
        Copy-Item -LiteralPath $rebuildTemplate -Destination (Join-Path $caseRoot 'rebuild.md') -Force
    } else {
        Write-Host ("WARN: rebuild template missing: {0}" -f $rebuildTemplate) -ForegroundColor Yellow
    }
}

$readmeNext = if ($ready) {
    @"
1. Scope is ready_for_act=true (auth granted + in_scope set)
2. Open primary skill: skills/$primary
3. Append ``timeline.md``; update ``workitems.md``
4. Append Evidence: ``skills/scripts/append-evidence.ps1 -CaseRoot <this dir> ...``
5. Promote findings with Evidence chain (skills/ops/evidence-finding-path.md)
6. Report via docs-generator; journal via field-journal
"@
} else {
    @"
1. Edit ``scope.md`` — set auth.status=granted and in_scope
   - network target: re-run with ``-AuthGranted -TargetUrl <url>``
   - local sample: re-run with ``-Preset offline-sample -Sample <path>``
2. Set ready_for_act when checklist complete
3. Open primary skill: skills/$primary
4. Append ``timeline.md``; update ``workitems.md``
5. Promote findings with Evidence chain (skills/ops/evidence-finding-path.md)
6. Report via docs-generator; journal via field-journal
"@
}

$readme = @"
# Case $CaseName

$readmeNext
"@
[System.IO.File]::WriteAllText((Join-Path $caseRoot 'README.md'), $readme, $utf8)

Write-Host ("CASE -> {0}" -f $caseRoot) -ForegroundColor Green
Write-Host ("PROJECT -> {0}" -f $projectRoot)
Write-Host ("PRIMARY skill: skills/{0} ({1})" -f $primary, $primaryId)
Write-Host ("auth.status={0} network_profile={1} ready_for_act={2}" -f $authStatusResolved, $networkMode, $readyStr)
if ($ready) {
    Write-Host 'NEXT: open PRIMARY SKILL.md and ACT within scope' -ForegroundColor Green
} else {
    Write-Host 'NEXT: fill scope.md auth + in_scope; then open PRIMARY SKILL.md'
}
