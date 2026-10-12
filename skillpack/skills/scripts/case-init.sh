#!/usr/bin/env bash
# reverse-skill case initializer (bash parity of case-init.ps1 + offline/ctf presets)
# Usage:
#   bash skills/scripts/case-init.sh --hint "apk reverse" --case-name demo
#   bash skills/scripts/case-init.sh --hint "local sample" --preset offline-sample --sample ./app.apk
#   bash skills/scripts/case-init.sh --hint "ctf web" --preset ctf-public --target-url https://chal.example
set -euo pipefail

HINT=""
CASE_NAME=""
PACKAGE_ROOT=""
PROJECT_ROOT=""
PACKAGE_ROOT_BOUND=0
AUTH_STATUS=""
AUTH_GRANTED=0
AUTH_BASIS="unknown"
EVIDENCE_OF_AUTH=""
TARGET_URL=""
NETWORK_PROFILE=""
SAMPLE=""
OLD_UPSTREAM=""
NEW_UPSTREAM=""
OUR_OLD_BUILD=""
PRESET=""
IN_SCOPE_ASSETS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    -Hint|--hint) HINT="${2:-}"; shift 2 ;;
    -CaseName|--case-name) CASE_NAME="${2:-}"; shift 2 ;;
    -PackageRoot|--package-root) PACKAGE_ROOT="${2:-}"; PACKAGE_ROOT_BOUND=1; shift 2 ;;
    -ProjectRoot|--project-root) PROJECT_ROOT="${2:-}"; shift 2 ;;
    -AuthStatus|--auth-status) AUTH_STATUS="${2:-}"; shift 2 ;;
    -AuthGranted|--auth-granted) AUTH_GRANTED=1; shift ;;
    -AuthBasis|--auth-basis) AUTH_BASIS="${2:-}"; shift 2 ;;
    -EvidenceOfAuth|--evidence-of-auth) EVIDENCE_OF_AUTH="${2:-}"; shift 2 ;;
    -TargetUrl|--target-url) TARGET_URL="${2:-}"; shift 2 ;;
    -NetworkProfile|--network-profile) NETWORK_PROFILE="${2:-}"; shift 2 ;;
    -Sample|--sample|--offline-sample) SAMPLE="${2:-}"; shift 2 ;;
    -OldUpstream|--old-upstream) OLD_UPSTREAM="${2:-}"; shift 2 ;;
    -NewUpstream|--new-upstream) NEW_UPSTREAM="${2:-}"; shift 2 ;;
    -OurOldBuild|--our-old-build) OUR_OLD_BUILD="${2:-}"; shift 2 ;;
    -Preset|--preset) PRESET="${2:-}"; shift 2 ;;
    -InScopeAssets|--in-scope-asset) IN_SCOPE_ASSETS+=("${2:-}"); shift 2 ;;
    -h|--help) sed -n '2,8p' "$0"; exit 0 ;;
    *)
      if [[ -z "$HINT" && "$1" != -* ]]; then HINT="$1"; shift
      else echo "Unknown arg: \"$1\"" >&2; exit 2; fi
      ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
if [[ -z "$PACKAGE_ROOT" ]]; then
  PACKAGE_ROOT="$(cd "$SKILLS_ROOT/.." && pwd)"
fi
if [[ -z "$PROJECT_ROOT" ]]; then
  if [[ $PACKAGE_ROOT_BOUND -eq 1 ]]; then
    PROJECT_ROOT="$PACKAGE_ROOT"
  else
    PROJECT_ROOT="$(pwd -P)"
  fi
fi

if [[ -n "$SAMPLE" ]]; then
  if [[ ! -f "$SAMPLE" ]]; then
    echo "Local --sample file not found: $SAMPLE" >&2
    exit 2
  fi
  sample_dir="$(cd "$(dirname "$SAMPLE")" && pwd -P)"
  SAMPLE="$sample_dir/$(basename "$SAMPLE")"
fi

# Presets: reduce "AI refuses to work" friction for legitimate local/CTF work.
REBUILD_MODE=0
UPDATE_MODE=0
ASSAULT_MODE=0
case "$PRESET" in
  "" ) ;;
  offline-sample|own-sample|local-sample)
    AUTH_GRANTED=1
    AUTH_STATUS="granted"
    AUTH_BASIS="own_system"
    NETWORK_PROFILE="${NETWORK_PROFILE:-offline}"
    EVIDENCE_OF_AUTH="${EVIDENCE_OF_AUTH:-preset:offline-sample (owner-operated local file)}"
    if [[ -n "$SAMPLE" ]]; then IN_SCOPE_ASSETS+=("$SAMPLE"); fi
    ;;
  ctf-public|ctf)
    AUTH_GRANTED=1
    AUTH_STATUS="granted"
    AUTH_BASIS="ctf_public"
    NETWORK_PROFILE="${NETWORK_PROFILE:-authorized_target_only}"
    EVIDENCE_OF_AUTH="${EVIDENCE_OF_AUTH:-preset:ctf-public}"
    ;;
  own-system|lab-only)
    AUTH_GRANTED=1
    AUTH_STATUS="granted"
    AUTH_BASIS="own_system"
    NETWORK_PROFILE="${NETWORK_PROFILE:-lab_only}"
    EVIDENCE_OF_AUTH="${EVIDENCE_OF_AUTH:-preset:own-system/lab}"
    ;;
  rebuild)
    # 复刻交付路径：与 offline-sample 同档（owner-operated 本地样本），但额外落
    # rebuild.md 对账表 + baseline/ + diff/ 三样。授权门与 offline-sample 一致。
    AUTH_GRANTED=1
    AUTH_STATUS="granted"
    AUTH_BASIS="own_system"
    REBUILD_MODE=1
    NETWORK_PROFILE="${NETWORK_PROFILE:-offline}"
    EVIDENCE_OF_AUTH="${EVIDENCE_OF_AUTH:-preset:rebuild (owner-operated local sample; rebuild delivery case)}"
    if [[ -n "$SAMPLE" ]]; then IN_SCOPE_ASSETS+=("$SAMPLE"); fi
    ;;
  update)
    # 复刻更新路径：在已存在的 rebuild case 上开更新阶段。授权档与 rebuild 同档
    # （owner-operated 本地样本 + offline）。必须显式传 --preset update 才出现。
    AUTH_GRANTED=1
    AUTH_STATUS="granted"
    AUTH_BASIS="own_system"
    UPDATE_MODE=1
    NETWORK_PROFILE="${NETWORK_PROFILE:-offline}"
    EVIDENCE_OF_AUTH="${EVIDENCE_OF_AUTH:-preset:update (owner-operated local sample; rebuild update case)}"
    ;;
  assault)
    # 攻坚交付路径：与 offline-sample 同档（owner-operated 本地样本），额外落
    # assault.md 滚动报告骨架 + diff/ 目录。授权门与 offline-sample 一致。
    AUTH_GRANTED=1
    AUTH_STATUS="granted"
    AUTH_BASIS="own_system"
    ASSAULT_MODE=1
    NETWORK_PROFILE="${NETWORK_PROFILE:-offline}"
    EVIDENCE_OF_AUTH="${EVIDENCE_OF_AUTH:-preset:assault (owner-operated local sample; protected-target assault case)}"
    if [[ -n "$SAMPLE" ]]; then IN_SCOPE_ASSETS+=("$SAMPLE"); fi
    ;;
  *)
    echo "ERROR: invalid --preset '$PRESET' (allowed: offline-sample|ctf-public|own-system|rebuild|update|assault)" >&2
    exit 2
    ;;
esac

if [[ -z "$CASE_NAME" ]]; then
  slug="$(printf '%s' "$HINT" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//; s/^$/case/' | cut -c1-40)"
  CASE_NAME="$(date +%Y%m%d-%H%M%S)-${slug}"
fi

# CaseName is a directory name, never a path. Match the PowerShell guard while
# keeping localized letters available under UTF-8 locales.
case_name_length="$(printf '%s' "$CASE_NAME" | wc -m | tr -d '[:space:]')"
if [[ -z "$CASE_NAME" || "$case_name_length" -gt 80 ||
      ! "$CASE_NAME" =~ ^[[:alnum:]] ||
      "$CASE_NAME" =~ [/:\\*?\"\<\>\|] ||
      "$CASE_NAME" =~ [[:cntrl:]] ||
      "$CASE_NAME" =~ [\.[:space:]]$ ]]; then
  echo "Invalid --case-name '$CASE_NAME'. Use a 1-80 character directory name beginning with a letter or number; path separators, trailing dots/spaces, control characters, and wildcard characters are not allowed." >&2
  exit 2
fi
if [[ -n "$NETWORK_PROFILE" ]]; then
  network_profile_normalized="$(printf '%s' "$NETWORK_PROFILE" | tr '[:upper:]' '[:lower:]')"
  case "$network_profile_normalized" in
    offline|lab_only|authorized_target_only|unrestricted_lab|lab|authorized|auth|offline_only) ;;
    *)
      echo "Invalid --network-profile '$NETWORK_PROFILE'. Allowed: offline, lab_only, authorized_target_only, unrestricted_lab (aliases: lab, authorized, auth, offline_only)." >&2
      exit 2
      ;;
  esac
fi

CASE_ROOT="$PROJECT_ROOT/work/$CASE_NAME"

# -Preset update：只在已存在的 rebuild case 上开更新阶段。case 根必须有 rebuild.md
# （初逆的对账表），否则明确报错 —— 不许静默生成。update 模式不重写
# scope/timeline/workitems/README：那是既有 case 的状态，不是新 case。
if [[ "$UPDATE_MODE" -eq 1 ]]; then
  rebuild_contract="$CASE_ROOT/rebuild.md"
  if [[ ! -f "$rebuild_contract" ]]; then
    echo "ERROR: --preset update requires an existing rebuild case: $rebuild_contract not found. Run initial rebuild first (case-init --preset rebuild), then re-run with --case-name <case> --preset update." >&2
    exit 2
  fi
  for fp_pair in "old-upstream:$OLD_UPSTREAM" "new-upstream:$NEW_UPSTREAM" "our-old-build:$OUR_OLD_BUILD"; do
    fp_name="${fp_pair%%:*}"
    fp_val="${fp_pair#*:}"
    if [[ ! "$fp_val" =~ [0-9a-fA-F]{64} ]]; then
      echo "ERROR: --preset update requires all three version fingerprints (path | version | sha256:<64hex>): --$fp_name missing or hash-less (got '$fp_val')" >&2
      exit 2
    fi
  done
  update_template="$SKILLS_ROOT/templates/update.md"
  if [[ ! -f "$update_template" ]]; then
    echo "ERROR: update template missing: $update_template" >&2
    exit 2
  fi
  mkdir -p "$CASE_ROOT/freeze" "$CASE_ROOT/diff-update"
  # 骨架 + 已校验的三份指纹直接落进 target 段。awk 走 ENVIRON（不做转义处理），
  # 指纹里的 ' | ' 与路径字符原样落地。
  UP_CASE="$CASE_NAME" UP_OLD="$OLD_UPSTREAM" UP_NEW="$NEW_UPSTREAM" UP_BUILD="$OUR_OLD_BUILD" \
  awk 'BEGIN { c=ENVIRON["UP_CASE"]; o=ENVIRON["UP_OLD"]; n=ENVIRON["UP_NEW"]; b=ENVIRON["UP_BUILD"] }
    /^- case:/ { print "- case: " c; next }
    /^- old_upstream:/ { print "- old_upstream: " o; next }
    /^- new_upstream:/ { print "- new_upstream: " n; next }
    /^- our_old_build:/ { print "- our_old_build: " b; next }
    { print }' "$update_template" > "$CASE_ROOT/update.md"
  echo "UPDATE -> $CASE_ROOT"
  echo "update.md written; freeze/ + diff-update/ ready; fingerprints validated"
  echo "NEXT: freeze first — snapshot rebuild.md + diff/ + deliverable sha256 into freeze/<our_version>/; then fill three_lines + function_delta; gate detail: skills/ops/rebuild-gates.md [更新阶段]"
  exit 0
fi

mkdir -p "$CASE_ROOT/evidence" "$CASE_ROOT/notes" "$CASE_ROOT/report"
if [[ "$REBUILD_MODE" -eq 1 ]]; then mkdir -p "$CASE_ROOT/baseline" "$CASE_ROOT/diff"; fi
if [[ "$ASSAULT_MODE" -eq 1 ]]; then mkdir -p "$CASE_ROOT/diff"; fi

auth_status_resolved="pending"
if [[ $AUTH_GRANTED -eq 1 ]]; then auth_status_resolved="granted"; fi
if [[ -n "$AUTH_STATUS" ]]; then
  candidate="$(printf '%s' "$AUTH_STATUS" | tr '[:upper:]' '[:lower:]' | tr -d '[:space:]')"
  case "$candidate" in
    pending|granted|denied|unknown) auth_status_resolved="$candidate" ;;
    *) echo "WARN: ignoring invalid --auth-status '$AUTH_STATUS'" >&2 ;;
  esac
fi

if [[ -n "$EVIDENCE_OF_AUTH" ]]; then
  evidence_auth="$EVIDENCE_OF_AUTH"
elif [[ $AUTH_GRANTED -eq 1 || "$auth_status_resolved" == "granted" ]]; then
  evidence_auth="cli-flag AuthGranted or AuthStatus=granted"
else
  evidence_auth="FILL_ME"
fi

ASSETS=()
[[ -n "$TARGET_URL" ]] && ASSETS+=("$TARGET_URL")
[[ -n "$SAMPLE" ]] && ASSETS+=("$SAMPLE")
for a in "${IN_SCOPE_ASSETS[@]:-}"; do
  [[ -n "$a" ]] || continue
  dup=0
  for e in "${ASSETS[@]:-}"; do [[ "$e" == "$a" ]] && dup=1 && break; done
  [[ $dup -eq 0 ]] && ASSETS+=("$a")
done
if [[ ${#ASSETS[@]} -eq 0 && "$HINT" =~ https?://([^[:space:]/]+) ]]; then
  ASSETS+=("https://${BASH_REMATCH[1]}/")
fi

if [[ -n "$NETWORK_PROFILE" ]]; then
  network_mode="$NETWORK_PROFILE"
elif [[ "$auth_status_resolved" == "granted" && ${#ASSETS[@]} -gt 0 && -z "$SAMPLE" ]]; then
  # Authorized network targets follow the PowerShell default. Offline is
  # reserved for an explicit local sample, never for a URL by accident.
  network_mode="authorized_target_only"
else
  network_mode="offline"
fi
network_mode="$(printf '%s' "$network_mode" | tr '[:upper:]' '[:lower:]')"
case "$network_mode" in
  lab) network_mode="lab_only" ;;
  authorized|auth) network_mode="authorized_target_only" ;;
  offline_only) network_mode="offline" ;;
  offline|lab_only|authorized_target_only|unrestricted_lab) ;;
  *)
    echo "Invalid --network-profile '$network_mode'. Allowed: offline, lab_only, authorized_target_only, unrestricted_lab (aliases: lab, authorized, auth, offline_only)." >&2
    exit 2
    ;;
esac

# Route PRIMARY via bash master-route
ROUTE_TMP="$(mktemp -d "${TMPDIR:-/tmp}/rs-case-route.XXXXXX")"
primary="reverse-engineering/SKILL.md"
primary_id="R0"
if [[ -f "$SCRIPT_DIR/master-route.sh" ]]; then
  set +e
  bash "$SCRIPT_DIR/master-route.sh" --hint "$HINT" --project-root "$PROJECT_ROOT" --out-dir "$ROUTE_TMP" >/dev/null 2>&1
  set -e
  if [[ -f "$ROUTE_TMP/route-scope.md" ]]; then
    rt="$(cat "$ROUTE_TMP/route-scope.md")"
    if printf '%s\n' "$rt" | grep -Eq '^[[:space:]]*-[[:space:]]*primary_skill:[[:space:]]*skills/'; then
      primary="$(printf '%s\n' "$rt" | grep -E '^[[:space:]]*-[[:space:]]*primary_skill:[[:space:]]*skills/' | head -1 | sed -E 's/.*skills\///' | tr -d '\r')"
    fi
    if printf '%s\n' "$rt" | grep -Eq '^[[:space:]]*-[[:space:]]*primary:[[:space:]]*'; then
      primary_id="$(printf '%s\n' "$rt" | grep -E '^[[:space:]]*-[[:space:]]*primary:[[:space:]]*' | head -1 | sed -E 's/.*primary:[[:space:]]*//' | tr -d '\r')"
    fi
  fi
fi
rm -rf "$ROUTE_TMP"

created="$(date -Iseconds 2>/dev/null || date +%Y-%m-%dT%H:%M:%S%z)"
if [[ ${#ASSETS[@]} -gt 0 ]]; then
  assets_block="$(printf '  - %s\n' "${ASSETS[@]}")"
else
  assets_block="  []"
fi

ready=false
if [[ "$auth_status_resolved" == "granted" ]]; then
  if [[ "$network_mode" == "offline" ]]; then
    if [[ -n "$SAMPLE" && ${#ASSETS[@]} -gt 0 ]]; then ready=true; fi
  elif [[ ${#ASSETS[@]} -gt 0 ]]; then
    ready=true
  fi
fi

check_auth="[ ]"; [[ "$auth_status_resolved" == "granted" ]] && check_auth="[x]"
check_scope="[ ]"; [[ ${#ASSETS[@]} -gt 0 || "$network_mode" == "offline" ]] && check_scope="[x]"
check_net="[ ]"; [[ -n "$network_mode" ]] && check_net="[x]"
ready_str="false"; [[ "$ready" == true ]] && ready_str="true"

if [[ "$ready" == true ]]; then
  timeline_next="open PRIMARY SKILL.md and ACT within scope"
  timeline_summary="case directory created; scope ready_for_act=true"
else
  timeline_next="fill scope auth + in_scope; set ready_for_act"
  timeline_summary="case directory created; scope pending auth"
fi

cat > "$CASE_ROOT/scope.md" <<EOF
# Case Scope

## meta
- case_id: $CASE_NAME
- created: $created
- operator: local
- project_root: $PROJECT_ROOT
- primary_skill: $primary
- primary_id: $primary_id
- lead_role: lead
- specialist_roles: []
- hint: $HINT
- preset: ${PRESET:-none}

## auth
- status: $auth_status_resolved
- basis: $AUTH_BASIS
- evidence_of_auth: $evidence_auth
- MUST NOT proceed if status != granted

## in_scope
- assets:
$assets_block
- surfaces: []
- activities: []

## out_of_scope
- assets: []
- activities: [dos, phishing_real_users, unrestricted_exfil]

## network_profile
- mode: $network_mode
- notes: |
    offline | lab_only | authorized_target_only | unrestricted_lab
    Change mode only after auth.status = granted.
    Presets: offline-sample | ctf-public | own-system

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
- ready_for_act: $ready_str
- checklist:
  - $check_auth auth.status = granted
  - $check_scope in_scope.assets non-empty OR offline sample path set
  - $check_net network_profile.mode chosen
  - [ ] out_of_scope reviewed
  - [ ] roles assigned (see skills/ops/role-map.md)

## ops_refs
- skills/ops/scope-contract.md
- skills/ops/evidence-finding-path.md
- skills/ops/role-map.md
- skills/ops/timeline-workitem.md
- skills/ops/IDENTITY.md
EOF

# -Preset rebuild：deliverables 段尾插一行标记。不传该预设时不执行本块 →
# scope.md 与改前逐字节一致（awk 插行，GNU/BSD 通用）。
if [[ "$REBUILD_MODE" -eq 1 ]]; then
  scope_tmp="$CASE_ROOT/scope.md.tmp"
  awk '1; /^- timeline: true$/ { print "- rebuild: true" }' "$CASE_ROOT/scope.md" > "$scope_tmp"
  mv "$scope_tmp" "$CASE_ROOT/scope.md"
fi

# -Preset assault 同理：deliverables 段尾插 assault: true 标记；不传该预设时不执行。
if [[ "$ASSAULT_MODE" -eq 1 ]]; then
  scope_tmp="$CASE_ROOT/scope.md.tmp"
  awk '1; /^- timeline: true$/ { print "- assault: true" }' "$CASE_ROOT/scope.md" > "$scope_tmp"
  mv "$scope_tmp" "$CASE_ROOT/scope.md"
fi

cat > "$CASE_ROOT/timeline.md" <<EOF
# Timeline (append-only)

## $created | lead | init
- action: case-init
- command_or_ref: skills/scripts/case-init.sh
- result_summary: $timeline_summary
- artifacts: [scope.md, workitems.md]
- evidence_ids: []
- decision_delta: [case_initialized]
- carry_forward_refs: [scope.md]
- next: $timeline_next
EOF

cat > "$CASE_ROOT/workitems.md" <<'EOF'
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
EOF

# -Preset rebuild：从 skills/templates/rebuild.md 拷对账表骨架进 case。
# 只读模板、写 case；不传该预设时本块不执行。
if [[ "$REBUILD_MODE" -eq 1 ]]; then
  rebuild_template="$SKILLS_ROOT/templates/rebuild.md"
  if [[ -f "$rebuild_template" ]]; then
    cp "$rebuild_template" "$CASE_ROOT/rebuild.md"
  else
    echo "WARN: rebuild template missing: $rebuild_template" >&2
  fi
fi

# -Preset assault：从 skills/templates/assault.md 拷滚动报告骨架进 case。
# 只读模板、写 case；不传该预设时本块不执行。
if [[ "$ASSAULT_MODE" -eq 1 ]]; then
  assault_template="$SKILLS_ROOT/templates/assault.md"
  if [[ -f "$assault_template" ]]; then
    cp "$assault_template" "$CASE_ROOT/assault.md"
  else
    echo "WARN: assault template missing: $assault_template" >&2
  fi
fi

if [[ "$ready" == true ]]; then
  cat > "$CASE_ROOT/README.md" <<EOF
# Case $CASE_NAME

1. Scope is ready_for_act=true (auth granted + in_scope set)
2. Open primary skill: skills/$primary
3. Append \`timeline.md\`; update \`workitems.md\`
4. Append Evidence under \`evidence/\`
5. Promote findings with Evidence chain (skills/ops/evidence-finding-path.md)
6. Report via docs-generator; journal via field-journal
EOF
else
  cat > "$CASE_ROOT/README.md" <<EOF
# Case $CASE_NAME

1. Edit \`scope.md\` — set auth.status=granted and in_scope
   - or re-run: \`bash skills/scripts/case-init.sh --hint "..." --preset offline-sample --sample ./sample.apk\`
   - or: \`--preset ctf-public --target-url https://...\`
2. Set ready_for_act when checklist complete
3. Open primary skill: skills/$primary
4. Append \`timeline.md\`; update \`workitems.md\`
5. Promote findings with Evidence chain (skills/ops/evidence-finding-path.md)
6. Report via docs-generator; journal via field-journal
EOF
fi

echo "CASE -> $CASE_ROOT"
echo "PRIMARY skill: skills/$primary ($primary_id)"
echo "auth.status=$auth_status_resolved network_profile=$network_mode ready_for_act=$ready_str"
if [[ "$ready" == true ]]; then
  echo "NEXT: open PRIMARY SKILL.md and ACT within scope"
else
  echo "NEXT: fill scope.md auth + in_scope; then open PRIMARY SKILL.md"
  echo "HINT: try --preset offline-sample|--preset ctf-public|--preset own-system"
fi
