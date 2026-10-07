# -*- coding: utf-8 -*-
"""state.py 的各条子命令。不是第二套命令行。"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from hub_assertions import validate_assertions, evaluate_assertions
from hub_flow import (
    valid_regression_basis, _owner_seen_covers, _owner_seen_quote_ok, _owner_seen_needed,
    _owner_seen_reason, _owner_seen_blocked, _OWNER_WAIVE_RED, _latest_check_receipt,
    _is_static_expiry, _expiry_seconds_value,
    _card_remaining_expiry_ok, _kick_closed_ok,
)
from hub_work import (work_gaps, work_view, engineering_next, probe_work_bindings, validate_decision_source,
                      requirements as work_requirements)
from pathlib import Path
from hub_io import (
    CANDIDATE_ROLES, CONTRACT_SCHEMA, KIND_TO_KEY, MANIFEST_KEYS, MANIFEST_LABELS,
    RECORD_KINDS, REGISTRY, TEMPLATES_DIR,
    _candidate_content_shas, _candidate_file_entries, _candidate_label,
    _candidate_manifest_sha, _empty_manifest, _file_lock, _inside_no_links,
    _in_product_temp, _ledger_has_events, _linklike, _load_registry_for_write, _registry_upsert, _resolve_inside, _scan_candidate_sources,
    now_iso, read_json, read_ledger, read_text_utf8, sha256_file, write_json, die, append_ledger,
    _validate_manifest,
)
from hub_gates import (
    CANDIDATE_BOUND_ARTIFACTS, _baseline_drift, _candidate_paths, _physical_spec_binding, _candidate_live, _contract_schema, _guard_identity, _identity_check, _missing_required_artifacts, _mission_complete,
    _mission_data, _mission_revision, _usable_claim, _require_claim, _validate_phases, active_block,
    candidate_pointers, confirm_multi_stop, confirm_wording_error, test_record_error,
    road_stop_lines,
    contract_fingerprint,
    derive, load_contract, loop_warnings, norm_key, phase_epoch, artifact_phase_epoch, _confirm_usable,
    _explicit_skip, _phase_receipt_text, _strip_independent_skip, _ui_ask_hold,
    _orig_asked,
    _latest_ask_conflict,
    is_legacy_four_exe, legacy_four_void_phase,
    physical_checks, phase_physical_checks, physical_receipt_missing, physical_receipt_missing_before,
    physical_receipts_for, release_role_min_phase, _red_receipt_for, NO_BASELINE_GREEN,
)
from hub_io import (
    PHYSICAL_CHECK_KINDS, PHYSICAL_RECEIPT_EVENT, PHYSICAL_RECEIPT_VERSION,
)
def _is_hub_tree(path):
    cur = Path(path).resolve()
    seen = set()
    while True:
        key = str(cur)
        if key in seen:
            break
        seen.add(key)
        if (cur / "tools" / "hub_cmds.py").is_file() and (cur / "tools" / "state.py").is_file():
            return True
        parent = cur.parent
        if parent == cur:
            break
        cur = parent
    return False
def _no_hub():
    die("这个目录还没有产品合同。先跟人讨论这是哪类产品、方案能不能推进；不要先 init，不要 init --force。", 2)
_HUB_NOT_PRODUCT = (
    "这是中枢仓库，不是产品。不要在这里 init，也不要在它里面的子文件夹 init。"
    "要卖新产品：另开一个夹，不要开在这份中枢里面。"
    "只有主人要改这份中枢时才读中枢说明。"
)
def _need_contract(product, contract):
    if _is_hub_tree(product):
        die(_HUB_NOT_PRODUCT, 2)
    if not contract:
        _no_hub()


def _print_change_map_how(product):
    from hub_ask import _parse_change_map
    parsed = _parse_change_map(product)
    if not parsed:
        return
    rows, how_idx = parsed
    shown = 0
    for cells in rows:
        how = cells[how_idx] if len(cells) > how_idx else ""
        name = cells[1] if len(cells) > 1 else cells[0]
        if not how:
            continue
        stale = cells[how_idx + 1] if len(cells) > how_idx + 1 else ""
        if stale.startswith("曾经") or stale in ("", "曾经这样找（已失效，勿删）"):
            stale = ""
        if stale:
            print(f"  {name}：{how}（曾经：{stale}，已失效勿用）")
        else:
            print(f"  {name}：{how}")
        shown += 1
        if shown >= 5:
            break


def _git_kw():
    kw = dict(capture_output=True, text=True, timeout=4,
              encoding="utf-8", errors="replace")
    if os.name == "nt":
        kw["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    env = os.environ.copy()
    for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_INDEX_FILE",
                "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES"):
        env.pop(key, None)
    kw["env"] = env
    return kw
def _path_in_product(product, path):
    if path is None:
        return False
    try:
        path.relative_to(product)
        return True
    except ValueError:
        return False
def _pin_in_home(home, path):
    if path is None or _linklike(path):
        return False
    try:
        return _path_in_product(home, path.resolve())
    except OSError:
        return False
def _git_objects_borrow(git_home, objects):
    try:
        kids = list(objects.iterdir())
    except OSError:
        return True
    for kid in kids:
        if not _pin_in_home(git_home, kid):
            return True
        if (not kid.is_dir()) or _linklike(kid):
            continue
        try:
            grands = list(kid.iterdir())
        except OSError:
            return True
        for grand in grands:
            if not _pin_in_home(git_home, grand):
                return True
    info = objects / "info"
    http_alt = info / "http-alternates"
    if http_alt.exists():
        return True
    alt = info / "alternates"
    if not alt.exists():
        return False
    if not _pin_in_home(git_home, alt):
        return True
    try:
        raw = alt.read_bytes()
    except OSError:
        return True
    text = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n").decode(
        "utf-8", errors="replace")
    for line in text.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        return True
    return False
def _git_common_dir(git, product, git_dir):
    raw = ""
    abs_p = git("rev-parse", "--path-format=absolute", "--git-common-dir")
    if abs_p.returncode == 0:
        raw = (abs_p.stdout or "").strip()
    if not raw:
        raw = (git("rev-parse", "--git-common-dir").stdout or "").strip()
    if not raw:
        return git_dir
    p = Path(raw)
    try:
        if not p.is_absolute():
            p = product / p
        return p.resolve()
    except OSError:
        return None
def _source_pin_line(product):
    """人话一行：git 最新定档。没有仓库就明说，避免 AI 拿聊天里的旧代码当档。"""
    product = Path(product).resolve()
    kw = _git_kw()
    def git(*args):
        return subprocess.run(["git", "-C", str(product), *args], **kw)
    try:
        inside = git("rev-parse", "--is-inside-work-tree")
        if inside.returncode != 0 or (inside.stdout or "").strip() != "true":
            return "源码档：这个文件夹还不是 git 仓库（源码靠 git 定档；打好的包靠下面的候选）"
        top_raw = (git("rev-parse", "--show-toplevel").stdout or "").strip()
        try:
            top = Path(top_raw).resolve() if top_raw else None
        except OSError:
            top = None
        if not top or top != product:
            return "源码档：这个产品文件夹自己还没有 git（源码靠 git 定档；打好的包靠下面的候选）"
        git_dir_raw = (git("rev-parse", "--absolute-git-dir").stdout or "").strip()
        try:
            git_dir = Path(git_dir_raw).resolve() if git_dir_raw else None
        except OSError:
            git_dir = None
        if not git_dir:
            return "源码档：这个文件夹的 git 读失败（不要凭聊天记忆；打好的包靠下面的候选）"
        common = _git_common_dir(git, product, git_dir)
        git_link = product / ".git"
        if (not git_link.exists()) or git_link.is_file() or _linklike(git_link):
            return "源码档：这个产品文件夹自己还没有 git（源码靠 git 定档；打好的包靠下面的候选）"
        try:
            git_home = git_link.resolve()
        except OSError:
            git_home = None
        if (not git_home) or (not _path_in_product(product, git_home)):
            return "源码档：这个产品文件夹自己还没有 git（源码靠 git 定档；打好的包靠下面的候选）"
        if not _path_in_product(git_home, git_dir) or not _path_in_product(git_home, common):
            return "源码档：这个产品文件夹自己还没有 git（源码靠 git 定档；打好的包靠下面的候选）"
        objects = git_home / "objects"
        if (not objects.exists()) or _linklike(objects):
            return "源码档：这个产品文件夹自己还没有 git（源码靠 git 定档；打好的包靠下面的候选）"
        try:
            obj_home = objects.resolve()
        except OSError:
            obj_home = None
        if (not obj_home) or (not _path_in_product(git_home, obj_home)):
            return "源码档：这个产品文件夹自己还没有 git（源码靠 git 定档；打好的包靠下面的候选）"
        if _git_objects_borrow(git_home, objects):
            return "源码档：这个产品文件夹自己还没有 git（源码靠 git 定档；打好的包靠下面的候选）"
        log = git("log", "-1", "--format=%h %s")
        st = git("status", "--porcelain")
        if st.returncode != 0:
            return "源码档：这个文件夹的 git 读失败（不要凭聊天记忆；打好的包靠下面的候选）"
        dirty = (st.stdout or "").strip()
        if log.returncode != 0:
            # 当前这条线还没有任何提交（刚建仓 / 空的新线）：说人话，不要说 git 坏了。
            # 别处已经有提交不算读失败。对象真读不出来才说读失败。
            on_branch = git("symbolic-ref", "-q", "HEAD")
            head_ok = git("rev-parse", "-q", "--verify", "HEAD")
            if on_branch.returncode == 0 and head_ok.returncode != 0:
                extra = "有未提交改动，提醒定档" if dirty else "工作区干净"
                return "源码档：（还没有提交）（" + extra + "）"
            return "源码档：这个文件夹的 git 读失败（不要凭聊天记忆；打好的包靠下面的候选）"
        head = (log.stdout or "").strip() or "（还没有提交）"
        tag = (git("describe", "--tags", "--exact-match").stdout or "").strip()
        extra = []
        if tag:
            extra.append("标签 " + tag)
        extra.append("有未提交改动，提醒定档" if dirty else "工作区干净")
        return "源码档：" + head + "（" + "；".join(extra) + "）"
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return "源码档：没有 git（源码靠 git 定档；打好的包靠下面的候选）"
def _stored_rel(product, fp):
    return Path(fp).resolve().relative_to(Path(product).resolve()).as_posix()
def _ensure_product_gitignore(product):
    p = Path(product) / ".gitignore"
    want = (".hub/", ".env", "/TEMP/", "测试/")
    unanchored_temp = {"TEMP/", "TEMP", "temp/", "temp"}

    def active_line(raw):
        return str(raw or "").split("#", 1)[0].strip()

    def read_gi():
        try:
            return p.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            die("产品 .gitignore 不是 UTF-8，读不了。先把该文件存成 UTF-8 再跑。", 3)

    if not p.exists():
        p.write_text("\n".join(want) + "\n", encoding="utf-8")
        return
    text = read_gi()
    lines = text.splitlines()
    new_lines = []
    replaced_temp = False
    for raw in lines:
        key = active_line(raw)
        if key in unanchored_temp:
            if not replaced_temp:
                new_lines.append("/TEMP/")
                replaced_temp = True
            continue
        new_lines.append(raw)
    have = {active_line(raw) for raw in new_lines if active_line(raw)}
    add = [line for line in want if line not in have and line.rstrip("/") not in have]
    if not add and not replaced_temp:
        return
    if add:
        new_lines.extend(add)
    p.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


_PHYSICAL_SPEC_REL = Path(".hub") / "physical-gates.json"
_PROBE_OUTPUT_LIMIT = 128 * 1024
# Hard boolean observations: config must assert field=true; a probe that only
# prints result=pass is not enough. Runtime fails unless the field is true.
_REQUIRED_TRUE_JSON = {
    "package_install": "installed",
    "update_flow": "updated",
    "handoff": "handed_off",
    "business_flow": "business_ok",
    "command_flow": "command_ok",
    "clean_install": "clean_installed",
    "update_rollback": "rollback_ok",
    "staging_business": "staging_ok",
    "migration_backup": "migration_ok",
    "safety_net": "safety_ok",
    "change_regression": "regression_ok",
    "release_candidate": "candidate_ok",
    "release_rollback": "release_rolled_back",
    "baseline_repro": "baseline_ok",
    "traffic_boundary": "traffic_ok",
    "causality_proof": "causality_ok",
    "automation_run": "automation_ok",
    "delivery_clean": "clean_ok",
}


def _probe_hash(value, command_path):
    payload = {"argv": value, "file_sha256": sha256_file(command_path)}
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _json_subset(actual, expected):
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(
            key in actual and _json_subset(actual[key], value)
            for key, value in expected.items()
        )
    if isinstance(expected, list):
        return isinstance(actual, list) and len(actual) == len(expected) and all(
            _json_subset(a, e) for a, e in zip(actual, expected))
    return type(actual) is type(expected) and actual == expected


def _strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('JSON 有重复字段')
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError('JSON 不接受非有限数字')


def _probe_spec(product, hub, check_id, product_type=None):
    path = _resolve_inside(product, _PHYSICAL_SPEC_REL, "物理探针配置")
    if not path.is_file():
        die(f"缺少物理探针配置：{path}\n"
            "先在当前产品的 .hub/physical-gates.json 配置机器检查；"
            "不能用 --evidence 或手写 manifest 代替。", 3)
    try:
        raw = path.read_text(encoding="utf-8-sig")
        data = json.loads(raw, object_pairs_hook=_strict_object, parse_constant=_reject_constant)
    except (OSError, UnicodeDecodeError, ValueError) as e:
        die(f"物理探针配置读不了或不是合法 JSON：{path}\n  {e}", 2)
    if not isinstance(data, dict) or data.get("version") != 1:
        die(f"物理探针配置版本不支持：{path}（要求 version=1）。", 2)
    checks = data.get("checks")
    if not isinstance(checks, dict) or check_id not in checks:
        die(f"物理探针配置没有当前阶段要求的 check「{check_id}」：{path}", 3)
    spec = checks[check_id]
    if not isinstance(spec, dict):
        die(f"物理探针 check「{check_id}」必须是对象。", 2)
    if 'assertions' in spec:
        try:
            validate_assertions(spec['assertions'])
        except ValueError as error:
            die(f'具名断言配置无效：{error}', 3)
    kind = spec.get("kind")
    if kind not in PHYSICAL_CHECK_KINDS:
        die(f"物理探针 check「{check_id}」的 kind 不支持：{kind!r}。", 2)
    command = spec.get("command")
    if not isinstance(command, list) or not command or any(not isinstance(x, str) or not x for x in command):
        die(f"物理探针 check「{check_id}」必须提供非空 command 字符串数组。", 2)
    expect = spec.get("expect")
    if not isinstance(expect, dict) or not expect:
        die(f"物理探针 check「{check_id}」必须提供 expect 对象；"
            "没有机器断言的脚本不能生成通过收据。", 2)
    allowed = {
        "exit_code", "stdout_contains", "stdout_not_contains", "stderr_contains",
        "stderr_not_contains", "json", "json_not", "files",
    }
    unknown = sorted(set(expect) - allowed)
    if unknown:
        die(f"物理探针 check「{check_id}」含未知 expect 字段：{unknown}。", 2)
    for key in ("stdout_contains", "stdout_not_contains", "stderr_contains", "stderr_not_contains"):
        if key in expect and (not isinstance(expect[key], list)
                              or any(not isinstance(x, str) for x in expect[key])):
            die(f"物理探针 check「{check_id}」的 {key} 必须是字符串数组。", 2)
    if "json" not in expect or not isinstance(expect.get("json"), dict):
        die(f"物理探针 check「{check_id}」必须用 json 对象输出结构化观察；"
            "只有退出码/文字断言的固定脚本不能生成通过收据。", 3)
    for key in ("json", "json_not"):
        if key in expect and not isinstance(expect[key], (dict, list, str, int, float, bool)):
            die(f"物理探针 check「{check_id}」的 {key} 断言类型不支持。", 2)
    if "json_not" in expect and not isinstance(expect["json_not"], dict):
        die(f"物理探针 check「{check_id}」的 json_not 必须是对象，便于拒绝危险字段。", 2)
    # These two checks are the cross-product hard gates for the GodSkin class
    # of failure.  They must emit a normalized machine observation; a free-form
    # success string is not enough to prove a closed core or data injection.
    if check_id == "core_entry":
        want = expect.get("json")
        if not isinstance(want, dict) or want.get("main_opened") is not True:
            die("core_entry 必须用 json 断言 main_opened=true；不能用文字报告代替真进主功能。", 3)
    if check_id == "ui_regression":
        want = expect.get("json")
        if not isinstance(want, dict) or want.get("ui_ok") is not True:
            die("ui_regression 必须用 json 断言 ui_ok=true；不能用文字报告代替界面回归。", 3)
    if check_id == "core_closed":
        want = expect.get("json")
        if not isinstance(want, dict) or want.get("main_opened") is not False:
            die("core_closed 必须用 json 断言 main_opened=false；不能用文字报告代替裸跑常闭检查。", 3)
    if check_id == "license_dataflow":
        want = expect.get("json")
        orig = product_type in (
            "desktop-product", "cli-tool", "web-service", "source-takeover", "protocol-automation")
        lic_msg = (
            "license_dataflow 必须用 json 断言 dynamic=true、"
            "expiry_seconds（卡还剩多久，禁止 cache_until/next_verify_at/20 秒/60 秒再问间隔）、"
            "verify_interval_seconds（再问间隔，必须小于卡剩余；测试/验收默认 60 秒）、"
            "mid_run_closed=true（真卡过期才停，本地 expires_at 倒计时关，不能缩短核心到期冒充）、"
            "kicked_closed/kick_closed=true（被挤掉/DEVICE_NOT_BOUND 后，下一次 verify 内核心退出）、"
            "solo_still_open=true（只有一台时超过验证间隔还在）、"
            "rate_limited_closed=false（RATE_LIMITED/暂时失败不是停机）、"
            "periodic_verify=true；不能只报“授权成功”或到期秒数。"
        )
        if (not isinstance(want, dict) or want.get("dynamic") is not True
                or isinstance(want.get("expiry_seconds"), bool)
                or not isinstance(want.get("expiry_seconds"), (int, float))
                or want.get("mid_run_closed") is not True
                or not _kick_closed_ok(want)
                or want.get("periodic_verify") is not True
                or want.get("solo_still_open") is not True
                or want.get("rate_limited_closed") is not False
                or _expiry_seconds_value(want.get("verify_interval_seconds")) is None
                or not _card_remaining_expiry_ok(want.get("expiry_seconds"), want)):
            die(lic_msg, 3)
        if not orig and (not isinstance(want.get("device_code"), str) or not want.get("device_code")):
            die(lic_msg, 3)
        if _is_static_expiry(want.get("expiry_seconds")):
            die("license_dataflow 的 expiry_seconds 必须是卡还剩多久，"
                "不能写硬编码 365 天。", 3)
    required_true = _REQUIRED_TRUE_JSON.get(check_id)
    if required_true is not None:
        want = expect.get("json")
        if not isinstance(want, dict) or want.get(required_true) is not True:
            die(f"{check_id} 必须用 json 断言 {required_true}=true；不能只报 pass。", 3)
    files = expect.get("files", [])
    if not isinstance(files, list):
        die(f"物理探针 check「{check_id}」的 files 必须是数组。", 2)
    for item in files:
        if isinstance(item, str):
            continue
        if not isinstance(item, dict) or not isinstance(item.get("path"), str) or not item.get("path"):
            die(f"物理探针 check「{check_id}」的 files 项必须是路径字符串或带 path 的对象。", 2)
        if "exists" in item and not isinstance(item["exists"], bool):
            die(f"物理探针 check「{check_id}」的 files.exists 必须是布尔值。", 2)
        if "min_size" in item and (isinstance(item["min_size"], bool)
                                    or not isinstance(item["min_size"], int)
                                    or item["min_size"] < 0):
            die(f"物理探针 check「{check_id}」的 files.min_size 必须是非负整数。", 2)
        if "sha256" in item and (not isinstance(item["sha256"], str)
                                  or len(item["sha256"]) != 64
                                  or any(c not in "0123456789abcdefABCDEF" for c in item["sha256"])):
            die(f"物理探针 check「{check_id}」的 files.sha256 必须是 64 位十六进制。", 2)
    timeout = spec.get("timeout_sec", 15)
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 0.1 <= timeout <= 120:
        die(f"物理探针 check「{check_id}」的 timeout_sec 必须在 0.1 到 120 秒之间。", 2)
    cwd = spec.get("cwd", ".")
    if not isinstance(cwd, str):
        die(f"物理探针 check「{check_id}」的 cwd 必须是字符串。", 2)
    cwd_path = _resolve_inside(product, cwd, "物理探针工作目录")
    if not cwd_path.is_dir():
        die(f"物理探针工作目录不存在：{cwd_path}", 2)
    command_path = _resolve_inside(product, command[0], "物理探针命令")
    if not command_path.is_file():
        die(f"物理探针命令不存在或不是普通文件：{command_path}", 2)
    if _in_product_temp(product, command_path):
        die("物理探针命令不能放在产品根 TEMP/（临时夹）。", 3)
    if command_path.suffix.casefold() == ".py":
        argv = [sys.executable, str(command_path), *command[1:]]
    else:
        argv = [str(command_path), *command[1:]]
    stdin = spec.get("stdin", "")
    if not isinstance(stdin, str):
        die(f"物理探针 check「{check_id}」的 stdin 必须是字符串。", 2)
    return path, spec, expect, cwd_path, argv, stdin


def _probe_file_observations(product, expectations):
    observed = []
    ok = True
    for item in expectations:
        rule = {"path": item} if isinstance(item, str) else dict(item)
        target = _resolve_inside(product, rule["path"], "物理探针文件断言")
        exists = target.is_file()
        want_exists = rule.get("exists", True)
        row = {"path": _stored_rel(product, target), "exists": exists}
        if exists:
            row["size"] = target.stat().st_size
            row["sha256"] = sha256_file(target)
        observed.append(row)
        if exists != want_exists:
            ok = False
        if exists and "min_size" in rule and row["size"] < rule["min_size"]:
            ok = False
        if exists and rule.get("sha256") and row["sha256"].casefold() != rule["sha256"].casefold():
            ok = False
    return ok, observed


def _candidate_naked_bundle(product, candidate_paths):
    from hub_ask import _naked_start_report
    opened = []
    unverified = []
    attempted = False
    details = {}
    for rel in candidate_paths or []:
        try:
            path = _resolve_inside(product, rel, "核心常闭直跑")
        except ValueError:
            continue
        report = _naked_start_report(path)
        details[rel] = report.get("detail") or ""
        if report.get("attempted"):
            attempted = True
        if report.get("state") is True:
            opened.append(rel)
        elif report.get("state") is None:
            unverified.append(rel)
    return opened, unverified, attempted, details


def _candidate_still_opens_main(product, candidate_paths):
    """Naked-start candidates. MAIN_OPENED means main still opens without a card."""
    opened, _, _, _ = _candidate_naked_bundle(product, candidate_paths)
    return opened


def _candidate_naked_unverified(product, candidate_paths):
    _, unverified, _, _ = _candidate_naked_bundle(product, candidate_paths)
    return unverified


def _candidate_still_matches(product, candidate_sha, candidate_paths, *, file_manifest=False):
    try:
        entries = []
        for rel in sorted(candidate_paths):
            path = _resolve_inside(product, rel, "物理探针候选")
            if not path.is_file():
                return False
            entries.append({"path": rel, "sha256": sha256_file(path), "size": path.stat().st_size})
        actual = (_candidate_manifest_sha(entries) if file_manifest or len(entries) != 1
                  else entries[0]["sha256"])
        return actual == candidate_sha
    except (OSError, ValueError):
        return False


def _run_physical_probe(product, check_id, spec, expect, cwd_path, argv, stdin,
                        candidate_sha="", candidate_paths=None, probe_nonce=None,
                        probe_stage="green", *, file_manifest=False):
    candidate_paths = list(candidate_paths or [])
    probe_nonce = probe_nonce or uuid.uuid4().hex
    started = time.monotonic()
    sandbox_id = uuid.uuid4().hex
    sandbox_root = Path(tempfile.mkdtemp(prefix="hub-physical-probe-"))
    sandbox_dirs = {
        "APPDATA": sandbox_root / "AppData" / "Roaming",
        "LOCALAPPDATA": sandbox_root / "AppData" / "Local",
        "USERPROFILE": sandbox_root / "UserProfile",
        "HOME": sandbox_root / "Home",
        "TEMP": sandbox_root / "Temp",
        "TMP": sandbox_root / "Temp",
        "XDG_CONFIG_HOME": sandbox_root / "Home" / ".config",
        "XDG_DATA_HOME": sandbox_root / "Home" / ".local" / "share",
        "XDG_CACHE_HOME": sandbox_root / "Home" / ".cache",
    }
    for directory in sandbox_dirs.values():
        directory.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    for key in list(env):
        upper = key.upper()
        if (upper.startswith("HUB_") or upper in {
                "GIT_DIR", "GIT_WORK_TREE", "GIT_OBJECT_DIRECTORY",
                "GIT_ALTERNATE_OBJECT_DIRECTORIES"}
                or any(word in upper for word in (
                    "TOKEN", "SECRET", "PASSWORD", "API_KEY",
                    "PRIVATE_KEY", "CREDENTIAL", "AUTHORIZATION",
                    "LICENSE", "CDK", "KAMI", "CARD_KEY", "LICENSE_KEY",
                ))):
            env.pop(key, None)
    for key, directory in sandbox_dirs.items():
        env[key] = str(directory)
    env.update({
        "HUB_PROBE_CHECK": check_id,
        "HUB_PROBE_CANDIDATE_SHA": candidate_sha,
        "HUB_PROBE_CANDIDATE_PATHS": json.dumps(candidate_paths, ensure_ascii=False),
        "HUB_PROBE_NONCE": probe_nonce,
        "HUB_PROBE_STAGE": probe_stage,
        "HUB_PROBE_SANDBOX_ID": sandbox_id,
        "HUB_PROBE_INPUT_SHA256": hashlib.sha256(stdin.encode("utf-8")).hexdigest(),
    })
    timed_out = False
    launch_error = None
    try:
        proc = subprocess.run(
            argv, input=stdin, capture_output=True, text=True, encoding="utf-8",
            errors="replace", cwd=str(cwd_path), timeout=float(spec.get("timeout_sec", 15)),
            shell=False, env=env,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0,
        )
        returncode = proc.returncode
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
    except subprocess.TimeoutExpired as e:
        timed_out = True
        returncode = None
        stdout = e.stdout.decode("utf-8", "replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        stderr = e.stderr.decode("utf-8", "replace") if isinstance(e.stderr, bytes) else (e.stderr or "")
    except OSError as e:
        returncode = None
        stdout = ""
        stderr = ""
        launch_error = e
    finally:
        shutil.rmtree(sandbox_root, ignore_errors=True)
    candidate_unchanged = _candidate_still_matches(
        product, candidate_sha, candidate_paths, file_manifest=file_manifest)
    elapsed_ms = int((time.monotonic() - started) * 1000)
    stdout_full = stdout[:_PROBE_OUTPUT_LIMIT]
    stderr_full = stderr[:_PROBE_OUTPUT_LIMIT]
    output_oversized = (len(stdout.encode('utf-8')) > _PROBE_OUTPUT_LIMIT
                        or len(stderr.encode('utf-8')) > _PROBE_OUTPUT_LIMIT)
    passed = False
    if launch_error or timed_out:
        passed = False
    else:
        expected_code = expect.get("exit_code", 0)
        codes = expected_code if isinstance(expected_code, list) else [expected_code]
        passed = isinstance(returncode, int) and returncode in codes
    for needle in expect.get("stdout_contains", []):
        passed = passed and needle in stdout_full
    for needle in expect.get("stdout_not_contains", []):
        passed = passed and needle not in stdout_full
    for needle in expect.get("stderr_contains", []):
        passed = passed and needle in stderr_full
    for needle in expect.get("stderr_not_contains", []):
        passed = passed and needle not in stderr_full
    parsed_json = None
    protocol = {
        "version": 1,
        "context_ok": False,
        "candidate_sha_match": False,
        "candidate_paths_match": False,
        "nonce_match": False,
        "observed_from_candidate": False,
    }
    try:
        parsed_json = json.loads(stdout_full, object_pairs_hook=_strict_object, parse_constant=_reject_constant)
        if not isinstance(parsed_json, dict):
            raise ValueError("物理探针 JSON 顶层必须是对象")
        if "json" in expect:
            passed = passed and _json_subset(parsed_json, expect["json"])
        if "json_not" in expect and _json_subset(parsed_json, expect["json_not"]):
            passed = False
        context = parsed_json.get("probe_context")
        if isinstance(context, dict):
            protocol["context_ok"] = (
                context.get("version") == 1
                and context.get("check") == check_id
                and context.get("candidate_sha") == candidate_sha
                and context.get("candidate_paths") == candidate_paths
                and context.get("nonce") == probe_nonce
                and context.get("sandbox_id") == sandbox_id
            )
            protocol["candidate_sha_match"] = context.get("candidate_sha") == candidate_sha
            protocol["candidate_paths_match"] = context.get("candidate_paths") == candidate_paths
            protocol["nonce_match"] = context.get("nonce") == probe_nonce
            protocol["observed_from_candidate"] = context.get("observed_from_candidate") is True
        passed = passed and protocol["context_ok"] and protocol["observed_from_candidate"]
        # The EXE authorization gate uses seconds as its normalized unit.
        # A dynamic flag cannot launder the old hard-coded 365-day probe.
        if check_id == "license_dataflow" and not _card_remaining_expiry_ok(
                parsed_json.get("expiry_seconds"), parsed_json):
            passed = False
        if check_id == "license_dataflow" and parsed_json.get("mid_run_closed") is not True:
            passed = False
        if check_id == "license_dataflow" and not _kick_closed_ok(parsed_json):
            passed = False
        if check_id == "license_dataflow" and parsed_json.get("periodic_verify") is not True:
            passed = False
        if check_id == "license_dataflow" and parsed_json.get("solo_still_open") is not True:
            passed = False
        if check_id == "license_dataflow" and parsed_json.get("rate_limited_closed") is not False:
            passed = False
        if check_id == "core_entry" and parsed_json.get("main_opened") is not True:
            passed = False
        if check_id == "ui_regression" and parsed_json.get("ui_ok") is not True:
            passed = False
        required_true = _REQUIRED_TRUE_JSON.get(check_id)
        if required_true is not None and parsed_json.get(required_true) is not True:
            passed = False
    except (TypeError, ValueError, RecursionError):
        passed = False
        parsed_json = None
    assertion_results = []
    if 'assertions' in spec:
        try:
            assertion_results = evaluate_assertions(parsed_json, spec['assertions'])
            passed = passed and all(row['passed'] for row in assertion_results)
        except ValueError:
            passed = False
    files_ok, file_rows = _probe_file_observations(product, expect.get("files", []))
    passed = passed and files_ok and candidate_unchanged and not output_oversized
    assertions_ok = passed
    opened_main = []
    unverified_main = []
    attempted_naked = False
    naked_detail = {}
    if check_id == "core_closed":
        opened_main, unverified_main, attempted_naked, naked_detail = _candidate_naked_bundle(
            product, candidate_paths)
        if opened_main or unverified_main:
            passed = False
    # Keep only a machine-safe subset. Raw stdout/stderr and arbitrary JSON are
    # deliberately excluded so a probe cannot put keys, tokens, or responses in
    # the ledger. The hashes still allow an independent operator to compare runs.
    safe_fields = {
        "check", "result", "main_opened", "ui_ok", "dynamic", "device_code", "expiry_seconds",
        "verify_interval_seconds", "cache_until", "cache_until_seconds", "cache_seconds",
        "next_verify_at",
        "mid_run_closed", "kicked_closed", "kick_closed", "periodic_verify",
        "solo_still_open", "rate_limited_closed",
        *_REQUIRED_TRUE_JSON.values(),
        "browser_opened", "clipboard_copied", "uac_error",
        "process_exited", "status",
    }
    safe_json = {}
    if isinstance(parsed_json, dict):
        for key in safe_fields:
            value = parsed_json.get(key)
            if isinstance(value, bool) or value is None:
                safe_json[key] = value
            elif key in (
                'expiry_seconds', 'verify_interval_seconds', 'cache_until',
                'cache_until_seconds', 'cache_seconds', 'next_verify_at',
            ):
                coerced = _expiry_seconds_value(value)
                if (coerced is not None and type(coerced) in (int, float)
                        and not isinstance(coerced, bool)
                        and 0 <= coerced <= 315576000):
                    safe_json[key] = int(coerced) if float(coerced).is_integer() else coerced
            elif key in ('result', 'status') and value in ('pass', 'fail', 'pending', 'blocked'):
                safe_json[key] = value
            elif key == 'device_code' and isinstance(value, str):
                safe_json['device_code_sha256'] = hashlib.sha256(value.encode('utf-8')).hexdigest()
    observed = {
        "returncode": returncode,
        "timed_out": timed_out,
        "elapsed_ms": elapsed_ms,
        "stdout_sha256": hashlib.sha256(stdout.encode("utf-8")).hexdigest(),
        "stderr_sha256": hashlib.sha256(stderr.encode("utf-8")).hexdigest(),
        "stdout_length": len(stdout),
        "stderr_length": len(stderr),
        "output_oversized": output_oversized,
        "json_keys": sorted(set(parsed_json) & safe_fields) if isinstance(parsed_json, dict) else [],
        "json": safe_json,
        "probe_protocol": protocol,
        "sandboxed": True,
        "sandbox_id": sandbox_id,
        "candidate_unchanged": candidate_unchanged,
        "files": file_rows,
        "assertions": assertion_results,
        "candidate_main_opened": opened_main,
        "candidate_main_unverified": unverified_main,
        "naked_start_attempted": bool(attempted_naked) if check_id == "core_closed" else False,
        "probe_assertions_ok": bool(assertions_ok),
        "naked_start_detail": naked_detail,
    }
    if launch_error:
        observed["launch_error_type"] = type(launch_error).__name__
    return passed, observed


_NO_BASELINE_GREEN = NO_BASELINE_GREEN


def cmd_probe(args):
    mode = getattr(args, 'mode', 'change')
    if args.red and mode != 'change':
        die('--red 只用于 change；基线和回归不能制造失败来过流程', 3)
    if mode == "baseline" and args.check in _NO_BASELINE_GREEN:
        die("授权、打包、进核心、界面回归、业务/命令实现不能用 baseline 模式交差；须 change 先红再绿。", 3)
    hub, contract = load_contract(args.product)
    _need_contract(args.product, contract)
    _guard_identity(args.product, contract)
    product = Path(args.product).resolve()
    ledger = read_ledger(hub)
    phases, _, _, cur, _, _ = derive(contract, ledger)
    phase = next((p for p in phases if p.get("id") == args.phase), None)
    if phase is None:
        die(f"未知物理探针阶段：{args.phase}。可用：" + "、".join(p["id"] for p in phases), 2)
    if cur >= len(phases) or phases[cur].get("id") != args.phase:
        die(f"物理探针只能在当前阶段运行；当前阶段是 {phases[cur].get('id') if cur < len(phases) else '已完成'}，不是 {args.phase}。", 3)
    checks = phase_physical_checks(product, contract, phase)
    if args.check not in checks:
        die(f"check「{args.check}」不是阶段 {args.phase} 声明的物理检查。要求：{', '.join(checks) or '无'}", 3)
    current, _ = candidate_pointers(ledger)
    cand_state, _ = _candidate_live(product, current)
    if cand_state != "ok" or not current:
        die("当前候选不存在、已被改动、在 TEMP/ 或哈希不一致；先修好候选，再运行物理探针。", 3)
    spec_path, spec, expect, cwd_path, argv, stdin = _probe_spec(
        product, hub, args.check, product_type=contract.get("type"))
    cand_sha = current.get("sha256")
    candidate_paths = _candidate_paths(current)
    if not candidate_paths:
        die("当前候选没有可绑定的文件路径，不能运行物理探针。", 3)
    epoch = phase_epoch(contract, ledger, args.phase)
    probe_stage = "red" if args.red else "green"
    probe_nonce = uuid.uuid4().hex
    spec_sha = sha256_file(spec_path)
    try:
        work_before = probe_work_bindings(product, hub, contract, args.check, args.phase, ledger)
    except (ValueError, TypeError, KeyError) as error:
        die(f'探针无法绑定责任：{error}', 3)
    command_sha = _probe_hash(argv, _resolve_inside(product, spec["command"][0], "物理探针命令"))
    prior_pass = None
    if mode == 'regression':
        prior_pass = valid_regression_basis(ledger, product, contract, args.check, spec_sha, command_sha)
        if prior_pass is None:
            die('回归缺少可核验的历史通过依据；没有运行探针。先建立真实基线或按修复模式取证。', 3)
    passed, observed = _run_physical_probe(
        product, args.check, spec, expect, cwd_path, argv, stdin,
        cand_sha, candidate_paths, probe_nonce, probe_stage,
        file_manifest=isinstance(current.get("files"), list))
    binding_after = _physical_spec_binding(product, args.check)
    binding_unchanged = binding_after == (spec_sha, command_sha, spec.get("kind"))
    try:
        work_after = probe_work_bindings(product, hub, contract, args.check, args.phase)
        binding_unchanged = binding_unchanged and work_before == work_after
    except (ValueError, TypeError, KeyError):
        binding_unchanged = False
    if not binding_unchanged:
        passed = False
        observed["binding_unchanged"] = False
    else:
        observed["binding_unchanged"] = True
    red_receipt = None
    latest_probe = None
    if args.red:
        timed_out = observed.get("timed_out") is True
        launch_err = "launch_error_type" in observed
        protocol = observed.get("probe_protocol") or {}
        if timed_out and not launch_err:
            red_valid = bool(not passed
                             and observed.get("candidate_unchanged") is True
                             and binding_unchanged)
        else:
            red_valid = bool(not passed and not timed_out and not launch_err
                             and observed.get("candidate_unchanged") is True
                             and protocol.get("context_ok") is True
                             and protocol.get("observed_from_candidate") is True
                             and binding_unchanged)
        observed["red_valid"] = red_valid
        if passed:
            observed["already_passing"] = True
            observed["red_required_failure"] = True
            passed = False
    elif getattr(args, 'mode', 'change') == 'change':
        red_receipt = _red_receipt_for(
            ledger, product, contract, phase, args.check, cand_sha, epoch,
            candidate_paths, spec_sha, command_sha)
        latest_probe = _latest_check_receipt(
            ledger, product, contract, args.phase, cand_sha, epoch, args.check)
        if red_receipt is None:
            latest_obs = (latest_probe or {}).get("observed") or {}
            if latest_obs.get("already_passing") is True and "launch_error_type" not in observed:
                if (passed
                        or observed.get("timed_out") is True
                        or bool(observed.get("candidate_main_unverified"))
                        or bool(observed.get("candidate_main_opened"))):
                    observed["already_passing"] = True
            pending_basis = {
                "n": 2 ** 31 - 1,
                "check_id": args.check,
                "observed": observed,
                "cand_sha": cand_sha,
                "epoch": epoch,
                "fp": contract_fingerprint(contract),
                "phase_id": args.phase,
            }
            reason = _owner_seen_reason(observed, args.check)
            if reason in _OWNER_WAIVE_RED and _owner_seen_covers(ledger, pending_basis):
                observed["owner_seen_accepted"] = True
                passed = True
                red_receipt = latest_probe
            else:
                observed["red_required"] = True
                passed = False
    if (not args.red and not passed
            and observed.get("candidate_unchanged") is True
            and observed.get("binding_unchanged") is True
            and not observed.get("red_required")
            and ((getattr(args, "mode", "change") == "change" and red_receipt is not None)
                 or (getattr(args, "mode", "change") == "regression" and prior_pass is not None)
                 or getattr(args, "mode", "change") == "baseline")):
        pending = {
            "n": 2 ** 31 - 1,
            "check_id": args.check,
            "observed": observed,
            "cand_sha": cand_sha,
            "epoch": epoch,
            "fp": contract_fingerprint(contract),
            "phase_id": args.phase,
        }
        if _owner_seen_covers(ledger, pending):
            passed = True
            observed["owner_seen_accepted"] = True
            if args.check == "core_closed" and (observed.get("candidate_main_unverified") or []):
                observed["owner_closed_accepted"] = True
    event = {
        "kind": PHYSICAL_RECEIPT_EVENT,
        "receipt_version": PHYSICAL_RECEIPT_VERSION,
        "check_id": args.check,
        "probe_kind": spec.get("kind"),
        "product_root": str(product),
        "fp": contract_fingerprint(contract),
        "phase_id": args.phase,
        "epoch": epoch,
        "cand_sha": cand_sha,
        "candidate_paths": candidate_paths,
        "result": "pass" if passed else "fail",
        "stage": probe_stage,
        "observed": observed,
        "spec_sha": spec_sha,
        "command_sha": command_sha,
        "probe_nonce": probe_nonce,
        "sandbox_id": observed.get("sandbox_id", ""),
        "nonce": uuid.uuid4().hex,
        "generated_by": "state",
        "verification_mode": mode,
        "work_bindings": work_before,
    }
    if red_receipt is not None:
        event["red_receipt_n"] = red_receipt["n"]
    if prior_pass is not None:
        event['regression_receipt_n'] = prior_pass['n']
    append_ledger(hub, event)
    if passed:
        print(f"物理探针通过：{args.phase}:{args.check}（候选 {cand_sha[:16]}…）")
        if observed.get("owner_closed_accepted"):
            print("这次常闭是机器真跑后仍没法自动判断，按主人看见关上了记下。其他机器门没有跳过。")
        elif observed.get("owner_seen_accepted"):
            print("这次中枢没看成、误判了或控不了电脑，按主人亲手看见的结果记下。只覆盖这一项检查，其他机器门没有跳过。")
        print("已生成机器收据；confirm 不再接受单独的文字复述。")
        return
    print(f"拒绝：物理探针失败：{args.phase}:{args.check}（候选 {cand_sha[:16]}…）")
    opened_main = observed.get("candidate_main_opened") or []
    unverified_main = observed.get("candidate_main_unverified") or []
    if opened_main:
        print("候选直接运行仍会进主功能：" + "、".join(opened_main))
        print("若你亲手看见的只是闪屏、报错窗，不是主程序，这可能是中枢误判。")
        print("把你看见的告诉我。不要写「符合要求」「可以打包」。")
        print("下一步由这边用 accept-closed 登记这一项，再测。不要把命令甩给主人。")
        print("其他机器门不能一起跳过。")
    elif unverified_main:
        print("机器已经对着候选真跑过，但仍没法自动判断有没有进主功能："
              + "、".join(unverified_main))
        print("这不是没测过。关没关上、有没有主窗口、进程是不是马上退，把看见的告诉我。")
        print("不要写「符合要求」。下一步由这边用 accept-closed 登记这一项，再测。")
        print("其他机器门也不能一起跳过。")
    elif not args.red and observed.get("already_passing"):
        print("这次红探针其实已经通过了：程序可能已经是对的，不是还没做。中枢不能假装它失败过。")
        print("把你亲手看见的这一项告诉我。不要写「符合要求」「可以打包」。")
        print("下一步由这边用 accept-seen 登记这一项，再测。")
    elif not args.red and observed.get("red_required") and latest_probe is None:
        print("还没有对着这一项跑过红探针。先跑红探针，再按你看见的往下。")
    elif not args.red and "launch_error_type" in observed:
        print("这次探针命令没跑起来。能修好命令就先修。")
        print("若你已经亲手测过这一项，把看见的告诉我，不要让坏探针把整单卡死。")
        print("不要写「符合要求」。下一步由这边用 accept-seen 登记这一项，再测。")
    elif not args.red and not observed.get("red_required") and _owner_seen_needed(observed, args.check):
        print("机器没看成、超时了、自动化没点到，或可能误判。这不是没测过。")
        print("把你亲手看见的这一项告诉我。不要写「符合要求」「可以打包」。")
        print("下一步由这边用 accept-seen 登记这一项，再测。硬编码 365 天、验证间隔当到期、单机自己关、RATE_LIMITED 当停不能洗白。其他检查要一项一项来。")
    elif args.red and observed.get("already_passing"):
        print("这次红探针其实已经通过了：程序可能已经是对的，不是还没做。")
        print("把你亲手看见的这一项告诉我。不要写「符合要求」。下一步由这边用 accept-seen 登记，再跑普通探针。")
    print("这次失败收据已记账；修复后必须重新运行探针，不能用 --evidence 洗白。")
    sys.exit(3)


def cmd_accept_closed(args):
    args.check = "core_closed"
    return cmd_accept_seen(args)


def cmd_accept_seen(args):
    hub, contract = load_contract(args.product)
    _need_contract(args.product, contract)
    _guard_identity(args.product, contract)
    product = Path(args.product).resolve()
    ledger = read_ledger(hub)
    phases, _, _, cur, _, _ = derive(contract, ledger)
    if cur >= len(phases) or phases[cur].get("id") != args.phase:
        current = phases[cur].get("id") if cur < len(phases) else "已完成"
        die(f"只能在当前阶段登记主人观察；当前是 {current}，不是 {args.phase}。", 3)
    phase = phases[cur]
    checks = phase_physical_checks(product, contract, phase)
    check_id = (getattr(args, "check", None) or "").strip()
    if check_id not in checks:
        die(f"当前阶段没有检查「{check_id}」，不能登记这个观察。要求：{', '.join(checks) or '无'}", 3)
    quote = (args.quote or "").strip()
    if not _owner_seen_quote_ok(quote, check_id):
        die("拒绝：这不是主人亲手看见的结果。不要写「符合要求」「通过」「可以打包」。"
            "要写主人看见了什么：比如双击没反应、主流程点完有结果、三种卡密测过。", 2)
    current, _ = candidate_pointers(ledger)
    cand_state, _ = _candidate_live(product, current)
    if cand_state != "ok" or not current:
        die("当前候选不存在、已被改动或在 TEMP/；先修好候选再登记观察。", 3)
    cand_sha = current.get("sha256")
    epoch = phase_epoch(contract, ledger, args.phase)
    latest = _latest_check_receipt(
        ledger, product, contract, args.phase, cand_sha, epoch, check_id)
    if latest is None:
        die(f"还没有对当前候选跑过 {check_id} 探针。先真跑一次，不能用空话过门。", 3)
    observed = latest.get("observed") or {}
    if observed.get("red_required") is True:
        prior_rows = [e for e in ledger if (e.get("n") or 0) < (latest.get("n") or 0)]
        prev = _latest_check_receipt(
            prior_rows, product, contract, args.phase, cand_sha, epoch, check_id)
        if prev is None:
            die("还没有一次对着这一项跑过的探针。先跑 state probe --red（真失败或已经测过），不能用点头代替。", 3)
        latest = prev
        observed = latest.get("observed") or {}
    if observed.get("red_required") is True:
        die("还没有一次对着这一项跑过的探针。先跑 state probe --red（真失败或已经测过），不能用点头代替。", 3)
    if _owner_seen_blocked(observed, check_id):
        die("机器看见的是硬编码 365 天、验证间隔当到期、单机自己关或 RATE_LIMITED 当停，不能靠点头洗白。", 3)
    if not _owner_seen_needed(observed, check_id):
        die("机器已经能判断这一项，不需要这条登记。", 3)
    unverified = list(observed.get("candidate_main_unverified") or [])
    opened = bool(observed.get("candidate_main_opened"))
    if check_id == "core_closed" and unverified and not opened:
        kind = "owner_closed_observation"
        extra = {"unverified_paths": unverified}
    else:
        kind = "owner_seen_observation"
        extra = {}
    payload = {
        "kind": kind,
        "phase_id": args.phase,
        "check_id": check_id,
        "fp": contract_fingerprint(contract),
        "cand_sha": cand_sha,
        "epoch": epoch,
        "quote": quote,
        "quote_sha256": hashlib.sha256(quote.encode("utf-8")).hexdigest(),
        "probe_n": latest.get("n"),
        "cover_reason": _owner_seen_reason(observed, check_id),
        "generated_by": "state",
    }
    payload.update(extra)
    append_ledger(hub, payload)
    print(f"已记下主人亲手看见的结果。这只覆盖这一项检查（{check_id}），不是跳过其他机器门。")
    print("下一步：再跑这一项探针。不要把命令甩给主人。")


def cmd_init(args):
    product = Path(args.product).resolve()
    if not product.exists():
        die(f"产品目录不存在：{product}", 2)
    if _is_hub_tree(product):
        die(_HUB_NOT_PRODUCT, 2)
    _load_registry_for_write()
    hub = product / ".hub"
    contract_path = hub / "contract.json"
    contract_present = contract_path.exists()
    if contract_present and not args.force:
        die(f"合同已存在：{contract_path}（内容异常也算存在；确要重建加 --force，会先归档旧文件）", 2)
    existing = None
    if contract_present:
        try:
            parsed = json.loads(contract_path.read_text(encoding="utf-8-sig"))
            if isinstance(parsed, dict):
                existing = parsed
        except (json.JSONDecodeError, UnicodeDecodeError, OSError):
            existing = None
    tpl = read_json(TEMPLATES_DIR / f"{args.type}.phases.json")
    if not tpl:
        die(f"找不到阶段模板：{TEMPLATES_DIR / (args.type + '.phases.json')}", 2)
    _validate_phases(tpl.get("phases", []), args.type)
    if contract_present and args.force and existing and is_legacy_four_exe(existing):
        phases_old, _, _, cur_old, _, _ = derive(existing, read_ledger(hub))
        if cur_old < len(phases_old) and legacy_four_void_phase(existing, phases_old[cur_old]["id"]):
            die("拒绝：旧四格合同停在授权/出货，禁止 init --force 换成七格。", 3)
    baseline = []
    for raw in (args.baseline or []):
        fp = _resolve_inside(product, raw, "baseline 文件")
        if not fp.exists():
            die(f"baseline 文件不存在：{fp}", 2)
        if _in_product_temp(product, fp):
            die("产品根 TEMP/ 是临时夹，不能当原件/baseline。", 3)
        baseline.append({"path": _stored_rel(product, fp), "sha256": sha256_file(fp), "size": fp.stat().st_size})
    initial_goal = (args.primary_flow or "").strip()
    initial_success = (getattr(args, "success", None) or "").strip()
    initial_route = (getattr(args, "route", None) or "").strip()
    initial_mission_ready = min(map(len, (initial_goal, initial_success, initial_route))) >= 8
    contract = {
        "schema_version": CONTRACT_SCHEMA,
        "product_id": args.product_id or product.name,
        "product_uuid": (existing or {}).get("product_uuid") or uuid.uuid4().hex,
        "root": str(product),
        "type": args.type,
        "flow": tpl.get("flow", args.type),
        "created": now_iso(),
        "primary_flow": initial_goal,
        "mission": {
            "goal": initial_goal,
            "success": initial_success,
            "route": initial_route,
            "revision": 1 if initial_mission_ready else 0,
        },
        "upstream": {"version": args.upstream_version or "", "baseline": baseline},
        "phases": tpl["phases"],
    }
    hub.mkdir(parents=True, exist_ok=True)
    _ensure_product_gitignore(product)
    forced_existing = contract_present and args.force
    orphan_ledger = (not forced_existing) and (not args.adopt_ledger) and _ledger_has_events(hub)
    reset = forced_existing or orphan_ledger
    arch = None
    if reset:
        arch = hub / ("archive-" + now_iso().replace(":", "").replace("-", "").replace("Z", "").replace("+", ""))
        arch.mkdir(parents=True, exist_ok=True)
        for fn in ("contract.json", "ledger.jsonl", "manifest.json"):
            if (hub / fn).exists():
                shutil.copy2(hub / fn, arch / fn)
    write_json(hub / "contract.json", contract)
    if reset or not (hub / "ledger.jsonl").exists():
        (hub / "ledger.jsonl").write_text("", encoding="utf-8")
    if reset or not (hub / "manifest.json").exists():
        write_json(hub / "manifest.json", _empty_manifest())
    _registry_upsert(contract["product_id"], str(product), args.type, contract["product_uuid"])
    print(f"已初始化：{contract['product_id']}（{args.type}，{len(contract['phases'])} 个阶段）")
    if forced_existing:
        print(f"（--force：旧合同/账本/清单已归档到 .hub/{arch.name}/ 并重置，防旧确认顶掉新流程）")
    elif orphan_ledger:
        print(f"（发现遗留账本但没有合同——已把旧账本/清单归档到 .hub/{arch.name}/ 并重置，"
              f"不静默继承旧确认；确要继承旧账本请加 --adopt-ledger 重跑 init）")
    print(f"合同：{hub / 'contract.json'}")
    if baseline:
        print(f"已锁 baseline 哈希：{len(baseline)} 个文件")
    print("下一步：python state.py status --product " + str(product))
def cmd_plan(args):
    hub, contract = load_contract(args.product)
    _need_contract(args.product, contract)
    _guard_identity(args.product, contract)
    if _contract_schema(contract) < 2:
        die("这是旧版合同（schema v1），不能静默套用新使命/阶段。请先预览后用 `init --force` 归档重建，或等待受控迁移。", 3)
    goal = (args.goal or "").strip()
    success = (args.success or "").strip()
    route = (args.route or "").strip()
    if not (_usable_claim(goal) and _usable_claim(success) and _usable_claim(route)):
        die("plan 的 --goal / --success / --route 都要写成具体一句话，不能用空值或占位符。", 2)
    old = dict(_mission_data(contract))
    old_ready = _mission_complete(contract)
    changed = any(old.get(k, "") != v for k, v in (("goal", goal), ("success", success), ("route", route)))
    if old_ready and not changed:
        print(f"mission 未变化（revision {old.get('revision', 0)}），无需重复写入。")
        return
    reason = (args.reason or "").strip()
    if old_ready and len(reason) < 8:
        die("修改已锁定 mission 必须带 --reason，写清新证据为何推翻/调整旧目标或路线。", 2)
    phases = contract.get("phases", [])
    if args.reopen_from and args.reopen_from not in {p["id"] for p in phases}:
        die(f"未知 reopen 阶段：{args.reopen_from}。可用：" + "、".join(p["id"] for p in phases), 2)
    old_fp = contract_fingerprint(contract)
    revision = _mission_revision(contract) + 1
    contract["mission"] = {"goal": goal, "success": success, "route": route, "revision": revision}
    contract["primary_flow"] = goal  # 兼容旧文档/读取者；v2 真源是 mission
    write_json(hub / "contract.json", contract)
    append_ledger(hub, {
        "kind": "plan", "revision": revision, "goal": goal, "success": success,
        "route": route, "reason": reason, "old_fp": old_fp,
        "new_fp": contract_fingerprint(contract),
    })
    if args.reopen_from:
        append_ledger(hub, {"kind": "reopen", "from_phase": args.reopen_from,
                            "reason": reason or "mission 初次锁定"})
    print(f"已锁定 mission revision {revision}：")
    print(f"  目标：{goal}")
    print(f"  成功：{success}")
    print(f"  路线：{route}")
    if old_ready:
        print("mission 已变化：旧确认因合同指纹变化全部失效，须按新目标重新确认（不静默继承）。")
    print("下一步：python state.py status --product " + str(Path(args.product).resolve()))
def cmd_reopen(args):
    hub, contract = load_contract(args.product)
    _need_contract(args.product, contract)
    _guard_identity(args.product, contract)
    phases = contract.get("phases", [])
    ids = {p["id"] for p in phases}
    if args.from_phase not in ids:
        die(f"未知阶段 id：{args.from_phase}。可用：" + "、".join(p["id"] for p in phases), 2)
    reason = (args.reason or "").strip()
    if len(reason) < 8:
        die("reopen 的 --reason 太短：写清哪条新证据推翻了旧路线。", 2)
    append_ledger(hub, {"kind": "reopen", "from_phase": args.from_phase, "reason": reason})
    print(f"已从阶段 {args.from_phase} 重开：该阶段及其后续旧确认已失效。")
    print(f"原因：{reason}")
    print("下一步：python state.py status --product " + str(Path(args.product).resolve()))


def _feature_text_has_rows(text):
    """有真实行才算有表。标题、空表头不算记得。"""
    for line in str(text or "").splitlines():
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if not cells or cells[0] in ("功能名", "功能") or set("".join(cells)) <= set("-: "):
            continue
        if cells[0]:
            return True
    return False


def _feature_bill_present(product):
    """产品根 FEATURES.md 或 features/ 下有真实行。空表头不算。不是 .hub 账本。"""
    root = Path(product)
    feat = root / "FEATURES.md"
    if feat.is_file():
        try:
            if _feature_text_has_rows(feat.read_text(encoding="utf-8-sig")):
                return True
        except (OSError, UnicodeError):
            pass
    folder = root / "features"
    if folder.is_dir():
        try:
            for child in folder.iterdir():
                if child.is_file() and child.suffix.lower() in {".md", ".txt"}:
                    try:
                        if _feature_text_has_rows(child.read_text(encoding="utf-8-sig")):
                            return True
                    except (OSError, UnicodeError):
                        continue
        except OSError:
            pass
    return False


def _feature_memory_gap(product, man):
    """旧场已经记过授权分界，但没有当前功能表：压缩后不准装记得。"""
    if _feature_bill_present(product):
        return False
    return bool(man.get("function_map"))


def _print_feature_memory(product, man, *, engineering=False):
    print("功能记忆：本命令不负责记得现在人看见哪些功能。")
    if man.get("function_map"):
        print("有授权分界记录（不是功能对照清单；条数不等于记得功能）")
    if _feature_memory_gap(product, man):
        print("功能对照清单缺失：工程方先从原话、Git、源码与实物恢复；无法恢复的业务取舍才问用户。")
        return True
    if _feature_bill_present(product):
        print("功能对照清单：产品根有表文件；本命令不展开正文，有文件≠已验证。")
        return False
    print("功能对照清单：还没有。新产品先讨论方案，不要向主人要功能表。")
    return False


def cmd_status(args):
    hub, contract = load_contract(args.product)
    _need_contract(args.product, contract)
    ledger = read_ledger(hub)
    phases, confirms, confirmed, cur, stale, invalidated = derive(contract, ledger)
    product = Path(args.product).resolve()
    id_issues = _identity_check(args.product, contract)
    id_has_block = any(lvl == "block" for lvl, _ in id_issues)
    if not id_has_block:
        _ensure_product_gitignore(product)
    print("-"*40)
    print(f"产品：{contract.get('product_id')}　类型：{contract.get('type')}")
    print(f"路径：{product}")
    from hub_ask import _is_hub_selftest
    if _is_hub_selftest(product):
        print("中枢自测：不要请主人点「可以」。看盘交差。")
    schema = _contract_schema(contract)
    uses_work = schema >= 3 or any(e.get('kind') == 'work_define' for e in ledger)
    mission = _mission_data(contract)
    if schema >= 2:
        print(f"MISSION r{mission.get('revision', 0)}：{mission.get('goal') or '(尚未锁定)'}")
        print(f"可观察成功：{mission.get('success') or '(尚未锁定)'}")
        print(f"当前路线：{mission.get('route') or '(尚未锁定)'}")
    elif contract.get("primary_flow"):
        print(f"PRIMARY_FLOW（旧合同）：{contract['primary_flow']}")
    up = contract.get("upstream", {})
    if up.get("version") or up.get("baseline"):
        print(f"上游 baseline：{up.get('version') or '(未填版本)'}　锁定 {len(up.get('baseline', []))} 个文件")
    print(_source_pin_line(product))
    current, last_good = candidate_pointers(ledger)
    cand_state, cand_disk = _candidate_live(product, current)
    if current:
        note = ("　" + current.get("note")) if current.get("note") else ""
        tag = {"missing": "　⚠ 文件不见了",
               "mismatch": "　✋ 文件已被改动、与登记哈希不符",
               "temp": "　✋ 当前候选在产品根 TEMP/（临时夹，不能当活候选）"}.get(cand_state, "")
        print(f"当前候选[{current.get('role', 'working')}]：{_candidate_label(current)}"
              f"（{current.get('sha256', '')[:16]}…）{note}{tag}")
    else:
        print("当前候选：还没登记")
    if last_good:
        same = current and last_good.get("sha256") == current.get("sha256")
        snap = "，有快照可 `state restore` 回退" if (hub / "last-good" / "last-good.json").exists() else ""
        print(f"last-good[{last_good.get('role', 'working')}]：{_candidate_label(last_good)}"
              f"（{last_good.get('sha256', '')[:16]}…）"
              + ("=当前" if same else "≠当前") + snap)
    man = _validate_manifest(read_json(hub / "manifest.json", {}) or {})
    memory_gap = _print_feature_memory(product, man, engineering=uses_work)
    summary = [f"{lbl}×{len(man[k])}" for k, lbl in MANIFEST_LABELS.items()
               if man.get(k) and k != "function_map"]
    if summary:
        print("已记清单：" + "、".join(summary) + "")
    print("-"*40)
    done = cur >= len(phases)
    memory_gap = bool(memory_gap) and not done
    final_work_gaps = work_gaps(product, hub, contract, mandatory=done)
    if final_work_gaps is not None:
        print('整单责任：' + ('证据齐备（不等于已交付）' if not final_work_gaps else '仍有未完成项；state work 查看'))
    frozen = (not done) and legacy_four_void_phase(contract, phases[cur]["id"])
    phase_need, phase_block = [], None
    if done:
        print("现在做到：账本点齐了，还没卖出去，也还没发 Release。")
        print("已确认：" + "、".join(p["stop_point"] for p in phases))
        print("确认齐≠业务成功")
    else:
        p = phases[cur]
        print(f"现在做到：阶段 {p['id']}（{p['name']}）")
        if frozen:
            print("　目标：作废（含 dossier / 官方更新的旧目标句不要当交差）")
        else:
            print(f"　目标：{p.get('goal', '')}")
        done_sp = [ph["stop_point"] for ph in phases[:cur]
                   if not legacy_four_void_phase(contract, ph["id"])]
        print("已确认：" + ("、".join(done_sp) if done_sp else "无"))
        if frozen:
            print("还没确认：旧四格授权/出货已作废，不要当下一格去补")
        else:
            print(f"还没确认：{p['stop_point']}")
        if not frozen:
            from hub_ask import (
                _data_mig_lines, _handoff_lines, _install_lines, _license_basic_lines,
                _update_analyze_lines,
            )
            for line in _update_analyze_lines(contract.get("type"), p["id"]):
                print(line)
            for line in _data_mig_lines(contract.get("type"), p["id"]):
                print(line)
            for line in _install_lines(contract.get("type"), p["id"]):
                print(line)
            for line in _handoff_lines(contract.get("type"), p["id"]):
                print(line)
            for line in _license_basic_lines(contract.get("type"), p["id"]):
                print(line)
        if (contract.get("type") == "exe-rebuild"
                and p["id"] == "6-update"
                and not frozen):
            print("这一格两件事，不能合成一句交差：")
            print("1. 客户已装那份软件里点更新（覆盖或本项 SKIP）。")
            print("2. 吃新上游：我们跟上原作者新版本（档案和改动图；不是客户点更新）。")
            print("先读产品根 CHANGES.md 和上一份发给客户的冻本。")
            print("靠「怎么找到」再认；搜不到当新门，不要跑旧脚本。")
            _print_change_map_how(product)
        checks = phase_physical_checks(product, contract, p)
        if checks:
            print("机器物理门：" + "、".join(checks))
        phase_need = _missing_required_artifacts(p, contract, ledger, hub, product)
        checklist_need = _checklist_gap(hub, contract, p, man)
        for item in checklist_need:
            if item not in phase_need:
                phase_need.append(item)
        phase_block = active_block(ledger, p["id"])
        if phase_block:
            print(f"BLOCKED：{phase_block.get('result', '')}")
        if frozen:
            print("停点制品：作废，不要为过门去补")
        elif phase_need:
            print("停点制品：未就绪（可以继续做；不能请你确认这一步做成了、进入下一阶段）")
            for item in phase_need:
                print(f"  - {item}")
            for line in road_stop_lines(contract.get("type"), p.get("id"), phase_need):
                print(line)
        elif memory_gap:
            print("停点制品：功能对照清单缺失，不能请你确认这一步做成了、进入下一阶段")
        else:
            print('停点制品：已齐备，工程方仍须核对实际使用过程，再展示需要用户判断的体验。'
                  if uses_work else "停点制品：已就绪，等待用户验收/确认")
    engineering = None
    if uses_work:
        focus_error = None
        try:
            focus_view = work_view(product, hub, contract, phase=None if done else phases[cur]['id'], ledger=ledger)
        except (ValueError, TypeError, KeyError) as error:
            focus_view = None
            focus_error = str(error)
        engineering = engineering_next(contract, focus_view, None if done else phases[cur]['id'],
            memory_gap=memory_gap, blocked=bool(phase_block), identity_issue=id_has_block,
            candidate_issue=cand_state in ('mismatch', 'missing', 'temp'), view_error=focus_error)
    from hub_memory import memory_context
    project_memory = memory_context(product, ((engineering or {}).get('focus') or {}).get('id'))
    if project_memory:
        if project_memory.get('error'):
            print('项目理解需恢复：' + project_memory['error'])
        else:
            print(f"项目理解：{project_memory['project']['name']}；记忆 revision={project_memory['revision']}")
            if project_memory['needs_reconcile']:
                print('先核对受影响分支：' + '、'.join(project_memory['needs_reconcile']))
            if project_memory['projection_gaps']:
                print('派生地图不同步：' + '、'.join(project_memory['projection_gaps']))
        print('恢复项目理解入口：' + project_memory['read'])
    derived_next = (engineering['action'] if engineering else
                    "核对整单未完成责任" if done and final_work_gaps else "出口复核" if done else "提交 BLOCKED 决策卡" if phase_block
                    else "继续本阶段调查" if phase_need
                    else "工程方先恢复功能对照清单，不要装记得、不要 confirm" if memory_gap
                    else "等待用户验收后 confirm")
    resume = read_json(hub / "resume.json", None)
    if isinstance(resume, dict):
        live_phase = None if done else phases[cur]["id"]
        stale_resume = (resume.get("phase_id") != live_phase) or (
            resume.get("next") not in (None, "", derived_next))
        ts = resume.get("ts") or ""
        pid = resume.get("phase_id") or "已完成"
        tag = "（已过期，以本次 status 为准）" if stale_resume else ""
        print(f"恢复卡：{ts} 阶段 {pid}{tag}")
    if stale:
        print(f"⚠ 有 {len(stale)} 条确认属于旧合同指纹（上游/mission/阶段合同变过），已作废。")
    id_msgs = [("✋ " + m) if lvl == "block" else ("⚠ " + m) for lvl, m in id_issues]
    warns = []
    if schema < 2:
        warns.append("这是旧版合同（schema v1）：可只读续接，但没有 mission/候选角色/重开语义；"
                     "不静默迁移，先预览后归档重建。")
    for sp, pid, ncnt in invalidated:
        warns.append(f"阶段「{pid}」的确认「{sp}」在其之后有 {ncnt} 个新尝试/重开事件——旧确认已失效；"
                     f"问题解决后用 `confirm --stop-point \"{sp}\" --reconfirm --evidence \"...\"` 重新确认")
    if not done:
        warns = loop_warnings(ledger, phases[cur]["id"]) + warns
    drift_now = _baseline_drift(contract, product)
    if drift_now:
        warns = [f"baseline 当前与合同不符（{'、'.join(drift_now)}）——别把上一版结论用到已改动文件上；"
                 f"要在漂移态确认须显式 confirm --ack-drift。"] + warns
    cand_blocked = cand_state in ("mismatch", "missing", "temp")
    if cand_state == "mismatch":
        warns = [f"当前候选已被改动、与登记哈希对不上（{_candidate_label(current)}）——"
                 f"确认前先复原或重新登记，别在被换过的候选上继续。"] + warns
    elif cand_state == "missing":
        warns = [f"当前候选文件不见了（{_candidate_label(current)}）——重新登记或复原再继续。"] + warns
    elif cand_state == "temp":
        warns = [f"当前候选在产品根 TEMP/（{_candidate_label(current)}）——拷到工作拷贝再登记。"] + warns
    print("-"*40)
    print('开工核对产品/源码档/路径；本次已经确认且身份未变时复用，不重复索确认。'
          if uses_work else "开工前复述产品/源码档/路径给用户确认。源码档看上一行 git，不是候选包。")
    if id_has_block:
        why = "不能——项目身份对不上，先解决："
    elif cand_blocked:
        why = "不能——当前候选被改动或缺失，先复原或重新登记："
    elif phase_block:
        why = "不能——当前阶段已有 BLOCKED 决策卡；获得新证据后记一次新 attempt 才恢复调查"
    elif frozen:
        why = "不能——旧四格停在授权/出货；机器不打 confirm，禁止 init --force"
    elif warns or id_msgs:
        why = "需要先处理下面的问题——"
    elif phase_need:
        why = "可以继续做；还不能请你确认这一步做成了"
    elif memory_gap:
        why = "可以继续做；功能对照清单缺失，不能请你确认这一步做成了"
    elif done:
        why = '账本点齐了，整单责任仍未完成' if final_work_gaps else '账本点齐了，等待出口复核'
    else:
        why = ('声明材料齐备，继续工程判断与实际使用复核' if uses_work
               else "停点制品已就绪，等待用户验收")
    print("能否继续：" + why)
    if why.startswith("不能") or why.startswith("需要"):
        for m in id_msgs:
            print(f"  {m}")
        for w in warns:
            print(f"  ⚠ {w}")
    if engineering:
        if engineering['focus']:
            focus = engineering['focus']
            print(f"工程焦点（建议）：{focus['id']} → {focus['outcome']}；实际消费者：{focus['consumer']}")
        print('工程下一步：' + engineering['action'])
        print('专项结束返回：' + engineering['return_to'] + '；账本缺口约束出口，不代替工程判断。')
    elif done and final_work_gaps:
        print('唯一下一步：state work 查看仍未完成或失效的责任，不能用阶段确认齐备替代交付。')
    elif done:
        print("唯一下一步：换加载 review 做出口复核（四顶帽子仍是这一本，不要开审查子代理）。装/升/退清单只嵌，不要自动换成 github。列出已验证 / 未验证 / 残余风险。")
    elif phase_block:
        print("唯一下一步：向用户提交 BLOCKED 决策卡（证据、两条不同路线、推荐、停止原因）。")
    elif frozen:
        print("唯一下一步：对人问产品边界。不要 confirm 出货，不要为过门去补，不要 init --force 换七格。")
    elif _ui_ask_hold(contract, read_json(hub / "manifest.json", {}) or {}, phases[cur]):
        kind = (contract or {}).get("type")
        man = read_json(hub / "manifest.json", {}) or {}
        asked = _orig_asked(contract, man)
        if kind == "cli-tool":
            head = "先把命令体验改成能卖的"
        elif kind == "source-takeover":
            head = "先把界面或命令体验改成能卖的（没窗口不要造窗）"
        else:
            head = "先把样子改成能卖的"
        if asked:
            print("唯一下一步：" + head
                  + "。答句已经有了，不要再催授权，不要先构建、不要打 zip、不要 gh release。")
        else:
            print("唯一下一步：" + head
                  + "，当面问要不要自己的卡密。不要先构建、不要打 zip、不要 gh release。")
    elif phase_need:
        print("唯一下一步：继续当前阶段，边做边留下以后还能用的记录；未就绪前不运行 confirm。")
    elif memory_gap:
        print("唯一下一步：工程方先从原话、Git、源码与实物恢复功能对照清单。无法恢复的业务取舍才问用户。不要 confirm，不要凭聊天装记得。")
    else:
        p = phases[cur]
        print("唯一下一步：把上述证据给用户看并取得明确点头后，跑：")
        print(f"  python state.py confirm --product \"{product}\" --stop-point \"{p['stop_point']}\"")
    print("-"*40)
    if id_has_block or cand_blocked or phase_block:
        sys.exit(3)
def cmd_gate(args):
    hub, contract = load_contract(args.product)
    _need_contract(args.product, contract)
    _guard_identity(args.product, contract)
    manifest = _validate_manifest(read_json(hub / "manifest.json", {}) or {})
    ledger = read_ledger(hub)
    phases, _, confirmed, cur, _, _ = derive(contract, ledger)
    scope = getattr(args, 'scope', 'package')
    package_phase = next((p['id'] for p in phases if p['id'] in ('3-build', '5-build', '4-license')), phases[-1]['id'])
    responsibility_gaps = work_gaps(Path(args.product).resolve(), hub, contract,
        None if scope == 'delivery' else package_phase, mandatory=True)
    def responsibility_gate():
        if responsibility_gaps:
            die('责任出口未完成：' + '；'.join(responsibility_gaps), 3)
        if scope == 'delivery' and cur < len(phases):
            die('责任核验通过不等于交付；当前仍有未确认的产品阶段。', 3)
    # Re-evaluate every already-confirmed physical gate here.  This catches a
    # changed probe spec, command, candidate, or phase epoch even when someone
    # tries to call gate directly instead of going through confirm again.
    confirmed_gaps = physical_receipt_missing_before(
        Path(args.product).resolve(), contract, phases, ledger, min(cur, len(phases)))
    if confirmed_gaps:
        die("已经确认的阶段存在失效/缺失物理收据：" + "、".join(confirmed_gaps)
            + "。不要打包；先按当前阶段重跑机器探针并重新确认。", 3)
    if (contract or {}).get("type") == "exe-rebuild":
        lic = next((p for p in phases if p.get("id") == "4-license"), None)
        sp = (lic or {}).get("stop_point")
        if not sp or sp not in confirmed:
            die("授权格还没点头：不要打 zip，不要 gh release。"
                "二开走授权页启动器确认，不走原创答句门。"
                "机器拦账本，拦不住终端直接敲的 gh。", 3)
        print("二开走自己的授权格，不走这条原创答句门。授权格已经点头。")
        print("已确认阶段的物理收据均绑定当前探针配置、合同、阶段 epoch 和候选哈希。")
        print("后续打包仍须在客户包阶段重新验收；gh 二进制机器拦不住。")
        from hub_ask import _gate_memory_gaps
        mem = _gate_memory_gaps(
            Path(args.product).resolve(), contract, phases, cur, confirmed)
        if mem:
            die("发货出口：冻本/功能表/改动图已经对不上当前文件。不要打 zip，不要 gh release。"
                + "；".join(mem), 3)
        responsibility_gate()
        return
    build_idx = next((i for i, p in enumerate(phases)
                      if p.get("id") in ("3-build", "5-build", "5-pack")), None)
    if build_idx is not None and cur < build_idx:
        die(f"还没到构建阶段（当前是 {phases[cur].get('id') if cur < len(phases) else '已完成'}）。"
            "不要提前打包。", 3)
    if _latest_ask_conflict(contract, manifest):
        die("答句互相打架：同一条里不能既写「这场不接」又写「接自己的授权」。"
            "不要打 zip，不要 gh release。"
            "机器拦账本，拦不住终端直接敲的 gh。", 3)
    if not _orig_asked(contract, manifest):
        die("没有当面答句：不要打 zip，不要 gh release。"
            "开场/架构格里的「这场不接」不算已问。"
            "机器拦账本，拦不住终端直接敲的 gh。", 3)
    print("答句已记在实现后的阶段。")
    print("机器拦账本和这道门，拦不住你在终端直接敲 gh，也拦不住磁盘上自己打的 zip。"
          "发 Release / 打 tag 仍须对应发布或打包格已经主人点头。")
    from hub_ask import _gate_memory_gaps
    mem = _gate_memory_gaps(
        Path(args.product).resolve(), contract, phases, cur, confirmed)
    if mem:
        die("发货出口：冻本/功能表已经对不上当前文件。不要打 zip，不要 gh release。"
            + "；".join(mem), 3)
    responsibility_gate()


def cmd_confirm(args):
    hub, contract = load_contract(args.product)
    _need_contract(args.product, contract)
    _guard_identity(args.product, contract)
    raw = args.stop_point
    if isinstance(raw, (list, tuple)):
        if len(raw) != 1:
            die("一次只能确认一个停点。", 2)
        raw = raw[0]
    args.stop_point = raw
    product = Path(args.product).resolve()
    ledger = read_ledger(hub)
    phases, confirms, confirmed, _, _, invalidated = derive(contract, ledger)
    if confirm_multi_stop(args.stop_point, phases):
        die("一次只能确认一个停点。", 2)
    invalidated_sps = {sp for sp, _, _ in invalidated}
    idx = next((i for i, p in enumerate(phases) if p.get("stop_point") == args.stop_point), None)
    if idx is None:
        names = [f"  - {p['stop_point']}（阶段 {p['id']} {p['name']}）" for p in phases if p.get("stop_point")]
        print("未知停点：" + args.stop_point + "\n这条流程的停点有：\n" + "\n".join(names))
        sys.exit(2)
    if legacy_four_void_phase(contract, phases[idx]["id"]):
        die("拒绝：旧四格合同的授权/出货停点已作废。不要 confirm，不要为过门去补制品，不要 init --force 换七格。", 3)
    if args.stop_point in confirmed and not args.reconfirm:
        print(f"「{args.stop_point}」之前已确认过，无需重复（确要重新确认加 --reconfirm）。")
        return
    if args.stop_point in invalidated_sps and not args.reconfirm:
        print(f"拒绝：「{args.stop_point}」之前确认过，但之后有新尝试或阶段重开——旧确认已失效。")
        print("确认问题已解决、要重新确认，请加 --reconfirm，并用 --evidence 写清这次到底验证了什么。")
        sys.exit(3)
    if active_block(ledger, phases[idx]["id"]):
        die("拒绝：该阶段当前是 BLOCKED；先取得新证据并记新的 attempt，不能直接确认。", 3)
    stuck = loop_warnings(ledger, phases[idx]["id"])
    if stuck:
        die("拒绝：" + stuck[0] + " 不能确认。", 3)
    missing = [phases[k]["stop_point"] for k in range(idx)
               if phases[k].get("stop_point") not in confirmed
               and not legacy_four_void_phase(contract, phases[k]["id"])]
    if missing:
        print("拒绝：不能跳过前面的停点。还没确认——")
        for m in missing:
            print(f"  - {m}")
        print("这就是防跳流程：先把前面的阶段做完并确认，再确认这一个。")
        sys.exit(3)
    need = _missing_required_artifacts(phases[idx], contract, ledger, hub, product)
    if need:
        print("拒绝：这个停点要求先有对应制品，不能空手确认——缺：")
        for m in need:
            print(f"  - {m}")
        print("这就是制品耦合：没有前一步的真实产物，这一步没东西可确认（不是走过场）。")
        sys.exit(3)
    if (contract.get("type") == "exe-rebuild"
            and phases[idx].get("id") == "1-access"):
        from hub_ask import _access_ok, _change_map_misses_gates, _latest_match
        man = _validate_manifest(read_json(hub / "manifest.json", {}) or {})
        fp = contract_fingerprint(contract)
        current_cand, _ = candidate_pointers(ledger)
        epoch = artifact_phase_epoch(contract, ledger, phases[idx]["id"])
        acc = _latest_match(
            man, "access", fp, (current_cand or {}).get("sha256"),
            phases[idx]["id"], epoch)
        if acc and _access_ok(acc):
            miss = _change_map_misses_gates(
                product, acc.get("entry_gate"), acc.get("action_gate"))
            if miss:
                die(miss, 3)
    checklist_gap = _checklist_gap(hub, contract, phases[idx])
    if checklist_gap:
        print("拒绝：需求防丢清单未完成，不能只靠文字确认——")
        for item in checklist_gap:
            print(f"  - {item}")
        print('schema 3 使用 state work 查看和维护累积责任；旧 checklist 不能手填完成来过门。')
        sys.exit(3)
    if not _confirm_usable(args.evidence, phases[idx]):
        die("confirm 的 --evidence 太短或是占位符：写清这一步到底验证了什么（具体、可复核，至少一句话）。占位符不算。", 2)
    if (args.note or "").strip() and not _confirm_usable(args.note, phases[idx]):
        die("confirm 的 --note 太短或是占位符：备注里不能写 UNVERIFIED / 未验证 这类占位。占位符不算。", 2)
    manifest = _validate_manifest(read_json(hub / "manifest.json", {}) or {})
    fp = contract_fingerprint(contract)
    current_cand, _ = candidate_pointers(ledger)
    cand_sha = current_cand.get("sha256") if current_cand else None
    epoch = artifact_phase_epoch(contract, ledger, phases[idx]["id"])
    receipt = _phase_receipt_text(
        phases[idx], args.evidence, args.note, manifest, fp, cand_sha, epoch)
    from hub_ask import _asked_own_license
    wording = confirm_wording_error(
        phases[idx], receipt, evidence=args.evidence,
        asked_own_license=_asked_own_license(manifest, contract),
        note=args.note, product_type=contract.get("type"))
    if wording:
        die(wording, 2)
    drift = _baseline_drift(contract, product)
    ack = (args.ack_drift or "").strip()
    if drift and not ack:
        print("拒绝：baseline 已改动，不能在漂移状态下确认——")
        for m in drift:
            print(f"  - {m}")
        print("要么恢复文件，要么加 --ack-drift \"<已知漂移的原因>\" 显式声明知情（会记进账本、status 持续显红）。")
        sys.exit(3)
    if drift and (not _usable_claim(ack) or (
            _explicit_skip(ack) and not _usable_claim(
                _strip_independent_skip(ack)))):
        die("confirm 的 --ack-drift 太短或是占位符：写清已知漂移的原因。占位符不算。", 2)
    cand_state, _ = _candidate_live(product, candidate_pointers(ledger)[0])
    if cand_state in ("mismatch", "missing", "temp"):
        print("拒绝：当前候选文件被改动、缺失，或落在产品根 TEMP/——不能在不完整/被换过的候选上确认。")
        print("先复原，或把要留下的拷到工作拷贝再重新登记。")
        sys.exit(3)
    event = {"kind": "confirm", "phase_id": phases[idx]["id"], "stop_point": args.stop_point,
             "fp": contract_fingerprint(contract), "evidence": args.evidence, "note": args.note or "",
             "reconfirm": bool(args.reconfirm), "cand_sha": cand_sha}
    required_checks = phase_physical_checks(product, contract, phases[idx])
    if required_checks:
        receipts = physical_receipts_for(
            product, hub, contract, phases[idx], ledger, cand_sha)
        # _missing_required_artifacts already rejects a missing receipt.  Keep a
        # second defensive check immediately before writing the confirm event so
        # the event can never be recorded without explicit receipt references.
        if len(receipts) != len(required_checks):
            die("拒绝：确认事件缺少当前候选的物理收据引用；不能只靠文字证据。", 3)
        event["physical_receipt_ns"] = {
            check_id: receipts[check_id].get("n") for check_id in required_checks
        }
    if drift:
        event["baseline_drift"] = drift
        event["drift_ack"] = ack
    append_ledger(hub, event)
    verb = "重新确认" if args.reconfirm else "确认"
    print(f"已记录{verb}：{args.stop_point}（阶段 {phases[idx]['id']}）")
    print("注意：这是 AI 登记的人工停点——真正的点头要你在对话里给出；order 是机器强制的，但\"证据是否成立\"要靠人/独立复核，state 不替你判业务成功。")
    print("下一步：python state.py status --product " + str(product))
def cmd_attempt(args):
    hub, contract = load_contract(args.product)
    _need_contract(args.product, contract)
    _guard_identity(args.product, contract)
    phases = contract.get("phases", [])
    if args.phase not in {p["id"] for p in phases}:
        print(f"未知阶段 id：{args.phase}。可用：" + "、".join(p["id"] for p in phases))
        sys.exit(2)
    key = args.hypothesis_key or norm_key(args.hypothesis)
    if args.blocked and len((args.result or "").strip()) < 20:
        die("--blocked 的 --result 必须是一张具体决策卡，不能只写“做不了”。", 2)
    if args.blocked:
        routes = (getattr(args, "routes", None) or "").strip()
        if routes.count("|") < 1 and "；" not in routes and ";" not in routes:
            die("--blocked 必须用 --routes 给出至少两条不同路线（用 | 或 ；分隔）。", 2)
    if args.new_evidence and not _usable_claim(args.evidence or ""):
        die("--new-evidence 必须同时用 --evidence 写明新增的可复核证据，不能只勾一个标志。", 2)
    append_ledger(hub, {
        "kind": "attempt", "phase_id": args.phase,
        "hypothesis": args.hypothesis, "hypothesis_key": key,
        "result": args.result, "evidence": args.evidence or "",
        "new_evidence": bool(args.new_evidence),
        "blocked": bool(args.blocked),
        "routes": (getattr(args, "routes", None) or "").strip(),
    })
    print(f"已记一次尝试（阶段 {args.phase}，假设键「{key}」，"
          f"{'BLOCKED 决策卡' if args.blocked else ('有' if args.new_evidence else '无') + '新证据'}）")
    for w in loop_warnings(read_ledger(hub), args.phase):
        print(f"  ⚠ {w}")
def _requirement_rows(hub):
    path = hub / "requirements.jsonl"
    if not path.exists():
        return []
    rows = []
    for line_no, line in enumerate(read_text_utf8(path, "需求账本").splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            die(f"需求账本第 {line_no} 行不是合法 JSON，不能建立防丢清单。", 3)
        if not isinstance(row, dict) or not isinstance(row.get("requirement_id"), str):
            die(f"需求账本第 {line_no} 行缺少 requirement_id，不能建立防丢清单。", 3)
        if row.get("status", "captured") not in {"captured", "verified", "retired"}:
            die(f"需求账本第 {line_no} 行状态不支持：{row.get('status')!r}。", 3)
        if row.get("status", "captured") != "retired":
            rows.append(row)
    return rows


def _validate_checklist_data(data, requirement_rows, phase_id, contract=None):
    if not isinstance(data, dict) or not isinstance(data.get("items"), list) or not data["items"]:
        return "checklist 必须是包含非空 items 数组的对象。"
    valid_phase_ids = {p.get("id") for p in (contract or {}).get("phases", []) if p.get("id")}
    seen = set()
    covered = set()
    for item in data["items"]:
        if not isinstance(item, dict):
            return "checklist.items 每项必须是对象。"
        item_id = item.get("item_id")
        req_id = item.get("requirement_id")
        files = item.get("files")
        checks = item.get("checks")
        status = item.get("status", "planned")
        item_phase = item.get("phase_id")
        if not isinstance(item_id, str) or not item_id.strip() or item_id in seen:
            return "checklist.items 的 item_id 必须非空且唯一。"
        if not isinstance(req_id, str) or not req_id.strip():
            return f"checklist 项 {item_id} 缺少 requirement_id。"
        if not any(row.get("requirement_id") == req_id for row in requirement_rows):
            return f"checklist 项 {item_id} 引用了不存在的需求 {req_id}。"
        if not _usable_claim(item.get("verbatim_intent")):
            return f"checklist 项 {item_id} 必须保留主人原话 verbatim_intent。"
        if (not isinstance(files, list) or not files
                or any(not isinstance(x, str) or not x.strip() for x in files)):
            return f"checklist 项 {item_id} 必须列出落地文件 files。"
        if (not isinstance(checks, list) or not checks
                or any(not isinstance(x, str) or not x.strip() for x in checks)):
            return f"checklist 项 {item_id} 必须列出物理检查 checks。"
        if status not in {"planned", "verified", "deferred"}:
            return f"checklist 项 {item_id} 的 status 只能是 planned/verified/deferred。"
        if status == "deferred" and not _usable_claim(item.get("reason")):
            return f"checklist 项 {item_id} 延后时必须写 reason。"
        if item_phase not in valid_phase_ids:
            return f"checklist 项 {item_id} 的 phase_id 必须是合同中的阶段。"
        phase_spec = next((p for p in (contract or {}).get("phases", [])
                           if p.get("id") == item_phase), {})
        phase_checks = phase_physical_checks(Path(contract.get("root") or "."), contract, phase_spec)
        receipt_refs = item.get("receipt_refs")
        if status == "verified" and phase_checks:
            if (not isinstance(receipt_refs, dict)
                    or any(not isinstance(receipt_refs.get(check), int)
                           or isinstance(receipt_refs.get(check), bool)
                           or receipt_refs.get(check) <= 0 for check in phase_checks)):
                return f"checklist 项 {item_id} 已验证但缺少每个物理门的 receipt_refs。"
        seen.add(item_id)
        covered.add(req_id)
    required = {row["requirement_id"] for row in requirement_rows}
    missing = sorted(required - covered)
    if missing:
        return "checklist 尚未覆盖需求原话：" + ", ".join(missing)
    return None


def _checklist_gap(hub, contract, phase, manifest=None):
    gaps = work_gaps(Path(contract['root']), hub, contract, phase.get('id'))
    if gaps is not None:
        return gaps
    requirements = _requirement_rows(hub)
    if not requirements:
        return []
    manifest = manifest if manifest is not None else _validate_manifest(
        read_json(hub / "manifest.json", {}) or {})
    fp = contract_fingerprint(contract)
    epoch = artifact_phase_epoch(contract, read_ledger(hub), phase.get("id"))
    rows = [entry for entry in manifest.get("checklists", []) or []
            if isinstance(entry, dict) and entry.get("fp") == fp
            and entry.get("phase_id") == phase.get("id") and entry.get("epoch", 0) == epoch]
    if not rows:
        return ["缺少当前阶段的 checklist；每项必须绑定主人原话、落地文件和物理检查。"]
    latest = rows[-1]
    items = latest.get("items")
    if not isinstance(items, list):
        return ["当前阶段 checklist.items 缺失或不是数组。"]
    covered = {item.get("requirement_id") for item in items if isinstance(item, dict)}
    missing = sorted({row["requirement_id"] for row in requirements} - covered)
    if missing:
        return ["checklist 尚未覆盖需求原话：" + ", ".join(missing)]
    # Planning/architecture stages may carry a planned checklist. Runtime and
    # implementation stages must close the items assigned to that phase.
    if not phase_physical_checks(Path(contract.get("root") or "."), contract, phase):
        return []
    current_items = [item for item in items if isinstance(item, dict)
                     and item.get("phase_id") == phase.get("id")]
    if not current_items:
        return [f"checklist 没有分配给当前阶段 {phase.get('id')} 的需求项。"]
    receipts = {}
    root = Path(contract.get("root") or ".")
    if phase_physical_checks(root, contract, phase):
        current_cand, _ = candidate_pointers(read_ledger(hub))
        receipts = physical_receipts_for(
            root, hub, contract, phase,
            read_ledger(hub), current_cand.get("sha256") if current_cand else None)
    unfinished = []
    for item in current_items:
        if item.get("status") == "deferred":
            if not _usable_claim(item.get("reason")):
                unfinished.append(str(item.get("item_id", "?")) + "(缺延后原因)")
            continue
        if item.get("status") != "verified":
            unfinished.append(str(item.get("item_id", "?")))
            continue
        if phase_physical_checks(root, contract, phase):
            refs = item.get("receipt_refs")
            if (not isinstance(refs, dict)
                    or any(refs.get(check) != receipt.get("n")
                           for check, receipt in receipts.items())
                    or set(refs) != set(receipts)):
                unfinished.append(str(item.get("item_id", "?")) + "(物理收据引用失效)")
    if unfinished:
        return ["checklist 仍有当前阶段未验证项：" + ", ".join(unfinished)
                + "；完成后重新 record --kind checklist，或记录主人明确延后的 reason。"]
    return []


def cmd_record(args):
    hub, contract = load_contract(args.product)
    _need_contract(args.product, contract)
    _guard_identity(args.product, contract)
    phase_ids = {p["id"] for p in contract.get("phases", [])}
    if args.phase and args.phase not in phase_ids:
        die(f"record 的 --phase 未知：{args.phase}。可用：" + "、".join(phase_ids), 2)
    phases, _, _, cur, _, _ = derive(contract, read_ledger(hub))
    if cur < len(phases) and legacy_four_void_phase(contract, phases[cur]["id"]):
        die("拒绝：旧四格合同的授权/出货停点已作废。不要 record 补制品，不要 confirm，不要 init --force 换七格。", 3)
    if args.phase and legacy_four_void_phase(contract, args.phase):
        die("拒绝：旧四格合同的授权/出货停点已作废。不要 record 补制品，不要 confirm，不要 init --force 换七格。", 3)
    key_for_kind = KIND_TO_KEY.get(args.kind)
    if _contract_schema(contract) >= 2:
        current_phase = phases[cur]["id"] if cur < len(phases) else None
        if (contract.get("type") == "exe-rebuild"
                and key_for_kind in CANDIDATE_BOUND_ARTIFACTS and not args.phase):
            die(f"EXE 流程的 {args.kind} 记录必须带 --phase，防止跨阶段复用旧证据。", 2)
        if key_for_kind in CANDIDATE_BOUND_ARTIFACTS and current_phase is None:
            die("全部停点已确认后不能继续追加候选绑定制品；先 reopen 对应阶段。", 3)
        if not args.phase:
            args.phase = current_phase
        if args.phase and args.phase != current_phase:
            die(f"拒绝预填/错填阶段制品：当前阶段是 {current_phase or '已完成'}，"
                f"不能把记录写成 {args.phase}。", 3)
    if args.data_file:
        raw = read_text_utf8(args.data_file, "data-file")
    elif args.data is not None:
        raw = args.data
    else:
        die("record 需要 --data 或 --data-file 其一。", 2)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        die(f"JSON 不合法：{e}（Windows PowerShell 传内嵌引号很容易踩坑，复杂 JSON 建议用 --data-file）", 2)
    if args.kind == "checklist":
        err = _validate_checklist_data(data, _requirement_rows(hub), args.phase, contract)
        if err:
            die(err, 3)
    if args.kind == "test":
        ph = next((p for p in phases if p["id"] == args.phase), None)
        if ph is None and cur < len(phases):
            ph = phases[cur]
        err = test_record_error(ph, data)
        if err:
            die(err, 2)
    if args.kind == "build" and _latest_ask_conflict(
            contract, read_json(hub / "manifest.json", {}) or {}):
        die("答句互相打架：同一条里不能既写「这场不接」又写「接自己的授权」。"
            "不要记分发包。", 3)
    if args.kind == "build" and not _orig_asked(
            contract, read_json(hub / "manifest.json", {}) or {}):
        die("没当面问接不接不要记分发包，不要打 zip 当过门。", 3)
    if args.kind == "build":
        target = next((p for p in phases if p.get("id") == args.phase), None)
        target_idx = next((i for i, p in enumerate(phases) if p.get("id") == args.phase), None)
        if target is not None and target_idx is not None:
            current_cand, _ = candidate_pointers(read_ledger(hub))
            cand_state, _ = _candidate_live(Path(args.product).resolve(), current_cand)
            if cand_state != "ok" or not current_cand:
                die("构建记录前当前候选必须存在且哈希一致。", 3)
            gaps = physical_receipt_missing_before(
                Path(args.product).resolve(), contract, phases, read_ledger(hub), target_idx)
            if gaps:
                die("构建前置物理门未通过：" + "、".join(gaps)
                    + "。先运行对应阶段的 `state probe`，不能用文字收据代替。", 3)
    if (contract.get("type") == "exe-rebuild"
            and args.kind in ("ui", "license", "patch")):
        from hub_ask import _change_map_gap
        gap = _change_map_gap(args.product)
        if gap:
            die(gap + "。先把这一刀写进产品根 CHANGES.md（怎么找到），再 record。", 3)
    if args.kind == "ui":
        from hub_ask import _rva_only_sites
        mapping = data.get("mapping") if isinstance(data, dict) else None
        if isinstance(mapping, list) and any(_rva_only_sites(x) for x in mapping):
            die("界面映射不能只写地址或旧脚本。", 3)
    if args.kind == "follow":
        from hub_ask import _follow_ok
        payload = data if isinstance(data, dict) else {}
        if not _follow_ok(payload):
            die("跟上判断不合格：必须写下我们改过哪些、这一版新改了什么、哪些还能认哪些是新门。不许照抄清单。", 3)
    if args.kind == "dossier":
        from hub_ask import _change_map_misses_gates, _dossier_ok
        payload = data if isinstance(data, dict) else {}
        if not _dossier_ok(payload):
            die("档案不合格：下次重找必须能再认出窗口原文或命令名，不能只写地址、旧脚本或占位。", 3)
        if contract.get("type") == "exe-rebuild":
            miss = _change_map_misses_gates(
                args.product, payload.get("entry_gate"), payload.get("action_gate"),
                need_action=True)
            if miss:
                die(miss + "。先把档案里的入口/动作原文写进 CHANGES.md 怎么找到。", 3)
    if args.kind == "cover":
        from hub_ask import _cover_ok, _cover_reject_msg
        payload = data if isinstance(data, dict) else {}
        ptype = contract.get("type")
        if not _cover_ok(payload, product_type=ptype):
            die(_cover_reject_msg(ptype), 3)
    mpath = hub / "manifest.json"
    with _file_lock(mpath):
        manifest = _validate_manifest(read_json(mpath, _empty_manifest()))
        for key in MANIFEST_KEYS:
            manifest.setdefault(key, [])
        if args.kind == "replay-order":
            if not isinstance(data, list):
                die("replay-order 的 --data 必须是 JSON 数组。这是整表覆盖不是追加，"
                    "例如 '[\"1-access\",\"2-boundary\",\"3-ui\",\"4-license\",\"5-pack\",\"6-update\"]'", 2)
            old_n = len(manifest.get("replay_order") or [])
            manifest["replay_order"] = data
            msg = (f"已整表覆盖 replay_order（旧 {old_n} 步 → 新 {len(data)} 步；"
                   f"不是追加。二开下次怎么重做写 dossier.replay_steps）")
        else:
            keyname = KIND_TO_KEY[args.kind]
            base = {"value": data} if not isinstance(data, dict) else dict(data)
            ledger_now = read_ledger(hub)
            current_cand, _ = candidate_pointers(ledger_now)
            stamp = {"fp": contract_fingerprint(contract), "phase_id": args.phase or "",
                     "epoch": artifact_phase_epoch(contract, ledger_now, args.phase) if args.phase else 0}
            if current_cand:
                stamp["cand_sha"] = current_cand.get("sha256")
            entry = {"ts": now_iso(), **base, **stamp}
            manifest.setdefault(keyname, []).append(entry)
            msg = f"已记入 manifest.{keyname}（现在 {len(manifest[keyname])} 条）"
        write_json(mpath, manifest)
    print(msg)
    if args.kind == "anchor":
        print("提醒：记下以后还用得上的原文（窗口、源码或命令里当时那几个字），不要抄说明书。")
    if args.kind in ("ui", "license", "patch", "access"):
        print("这一刀写进产品根 CHANGES.md：怎么找到、大约在哪（会漂）、改成了什么。不要等第 6 格。")
        cmap = Path(args.product) / "CHANGES.md"
        if not cmap.is_file():
            print("现在还没有改动图。下一版上游会从零找门。")
def cmd_require(args):
    hub, contract = load_contract(args.product)
    _need_contract(args.product, contract)
    _guard_identity(args.product, contract)
    path = hub / "requirements.jsonl"
    listing = bool(getattr(args, "list_rows", False))
    text = (getattr(args, "append", None) or "").strip()
    if listing and not text:
        if not path.exists():
            print("还没有需求账本（.hub/requirements.jsonl）。")
            return
        print(read_text_utf8(path, "需求账本"), end="")
        return
    if not text:
        die("require 要 --append \"原话\" 或 --list。", 2)
    source = (getattr(args, "source", None) or "").strip()
    kind = getattr(args, "kind", "requirement")
    # A short continuation such as “继续” is still a real owner decision when
    # it is bound to the exact OWNER-SPEECH event. The source hash below remains
    # mandatory; unbound short filler is still rejected.
    short_bound_decision = kind == "decision" and source.startswith("speech:")
    if not _require_claim(text) and not short_bound_decision:
        die("require --append 要写主人原话，不能占位符或无信息字母串。", 2)
    with _file_lock(path):
        try:
            existing_rows = work_requirements(hub)
        except ValueError as error:
            die(f'需求账本拒绝：{error}', 3)
        ids = {r['requirement_id'] for r in existing_rows}
        n = len(existing_rows) + 1
        while f'REQ-{n:03d}' in ids:
            n += 1
        rid = (getattr(args, 'req_id', None) or '').strip() or f'REQ-{n:03d}'
        if rid in ids:
            die(f'需求身份 {rid} 已存在；原话只能追加，新消息用新身份。', 3)
        row = {'requirement_id': rid, 'verbatim_intent': text, 'status': 'captured', 'ts': now_iso(),
               'kind': kind, 'source': source or None}
        if row['kind'] == 'decision' or str(row.get('source', '')).startswith('speech:'):
            try:
                validate_decision_source(hub, row)
            except ValueError as error:
                die(f'决定来源拒绝：{error}', 3)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"已追加 {rid}：{text}")
def cmd_verify(args):
    hub, contract = load_contract(args.product)
    _need_contract(args.product, contract)
    _guard_identity(args.product, contract)
    product = Path(args.product).resolve()
    baseline = contract.get("upstream", {}).get("baseline", [])
    if not baseline:
        print("合同里没有 baseline 文件可核对（init 时可用 --baseline 指定）。UNVERIFIED")
        sys.exit(1)
    drift = _baseline_drift(contract, product)
    for b in baseline:
        try:
            fp = _inside_no_links(product, b["path"])
            status = "缺失" if not fp.exists() else ("一致" if sha256_file(fp) == b["sha256"] else "已改动")
        except (ValueError, OSError):
            status = "不安全路径"
        print(f"  {status}   {b['path']}")
    if drift:
        print(f"verify：{len(drift)} 个文件与 baseline 不符——别把上一版的偏移/结论用到已改动的文件上。")
        sys.exit(1)
    print("verify：全部与 baseline 一致。")
def _commit_last_good(hub, product, event):
    lg = hub / "last-good"
    if lg.exists() and not lg.is_dir():
        raise OSError(f"{lg} 已存在但不是目录")
    stage = hub / f".last-good-stage-{os.getpid()}-{uuid.uuid4().hex[:8]}"
    backup = hub / f".last-good-old-{os.getpid()}-{uuid.uuid4().hex[:8]}"
    stage.mkdir(parents=True)
    try:
        if isinstance(event.get("files"), list):
            copied = []
            for item in event["files"]:
                src = _resolve_inside(Path(product).resolve(), item["path"], "last-good 候选文件")
                if _in_product_temp(Path(product).resolve(), src):
                    raise OSError("产品根 TEMP/ 是临时夹，不能存成 last-good")
                dst = stage / "files" / Path(item["path"])
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                if sha256_file(dst) != item["sha256"]:
                    raise OSError(f"快照复制后哈希不一致：{item['path']}")
                copied.append(dict(item))
            if _candidate_manifest_sha(copied) != event["sha256"]:
                raise OSError("候选文件集清单哈希不一致")
            meta = {
                "files": copied, "sha256": event["sha256"], "role": event.get("role", "working"),
                "sources": event.get("sources", []), "ts": now_iso(),
            }
        else:
            src = _resolve_inside(Path(product).resolve(), event["path"], "last-good 候选文件")
            if _in_product_temp(Path(product).resolve(), src):
                raise OSError("产品根 TEMP/ 是临时夹，不能存成 last-good")
            dst = stage / src.name
            shutil.copy2(src, dst)
            if sha256_file(dst) != event["sha256"]:
                raise OSError("快照复制后哈希与源文件不一致（复制被破坏？）")
            meta = {
                "path": event["path"], "file": src.name, "sha256": event["sha256"],
                "role": event.get("role", "working"), "ts": now_iso(),
            }
        write_json(stage / "last-good.json", meta)
        if lg.exists():
            os.replace(lg, backup)
        try:
            os.replace(stage, lg)
        except OSError:
            if backup.exists() and not lg.exists():
                os.replace(backup, lg)
            raise
        if backup.exists():
            shutil.rmtree(backup)
    finally:
        if stage.exists():
            shutil.rmtree(stage, ignore_errors=True)
        if backup.exists() and lg.exists():
            shutil.rmtree(backup, ignore_errors=True)
def cmd_candidate(args):
    hub, contract = load_contract(args.product)
    _need_contract(args.product, contract)
    _guard_identity(args.product, contract)
    product = Path(args.product).resolve()
    _ensure_product_gitignore(product)
    ledger = read_ledger(hub)
    if args.show or (not args.set_path and not args.set_files):
        current, last_good = candidate_pointers(ledger)
        if current:
            state, disk = _candidate_live(product, current)
            tag = {"ok": "（文件哈希一致）", "missing": "（⚠ 文件不见了）",
                   "mismatch": f"（✋ 文件已被改动，实际 {(disk or '')[:16]}…）",
                   "temp": "（✋ 在产品根 TEMP/，不能当活候选）"}.get(state, "")
            print(f"当前候选[{current.get('role', 'working')}]：{_candidate_label(current)}"
                  f"（{current.get('sha256', '')[:16]}…）{current.get('note', '')}{tag}")
            if current.get("parent_sha"):
                print(f"  parent：{current['parent_sha'][:16]}…")
            if current.get("revert"):
                print(f"  revert：{current['revert'][:120]}")
        else:
            print("还没登记任何候选。")
        if last_good:
            print(f"last-good[{last_good.get('role', 'working')}]：{_candidate_label(last_good)}"
                  f"（{last_good.get('sha256', '')[:16]}…）")
        return
    phases, _, _, cur, _, _ = derive(contract, ledger)
    if cur >= len(phases):
        die(f"全部停点已确认后不能直接换候选；先 `state reopen --from {phases[-1]['id']} --reason ...`，"
            "让最终验收失效后再登记新候选。", 3)
    if args.set_path and args.set_files:
        die("candidate 的 --set 与 --set-files 只能选一个。", 2)
    current, _ = candidate_pointers(ledger)
    role = args.role or "working"
    if role not in CANDIDATE_ROLES:
        die("未知候选角色：" + role, 2)
    if role == "release":
        min_phase = release_role_min_phase(contract, phases)
        min_idx = phases.index(min_phase) if min_phase in phases else None
        if min_idx is not None and cur < min_idx:
            die(f"拒绝：release 候选不能在 {min_phase.get('id')} 之前登记；"
                "先完成前置阶段和物理门，不能用 release 角色提前解锁打包。", 3)
        gaps = physical_receipt_missing_before(
            product, contract, phases, ledger, min_idx if min_idx is not None else cur)
        if gaps:
            die("拒绝：release 候选登记前置物理门未通过：" + "、".join(gaps)
                + "。先按前置阶段运行机器探针并确认，不能用候选登记绕过打包门。", 3)
    parent_sha = (args.parent_sha or (current or {}).get("sha256") or "").strip()
    if role not in ("upstream", "working") and not parent_sha:
        die(f"角色 {role} 必须有父候选血缘：先登记 upstream/working，或显式传 --parent-sha。", 3)
    revert = (getattr(args, "revert", None) or "").strip()
    if role not in ("upstream", "working") and len(revert) < 8:
        die(f"角色 {role} 必须用 --revert 写明可回退步骤（≥8字），否则不能登记。", 3)
    known_shas = {e.get("sha256") for e in ledger if e.get("kind") == "candidate" and e.get("sha256")}
    if parent_sha and parent_sha not in known_shas:
        die("parent_sha 不对应账本里的任何历史候选，拒绝伪造血缘。", 3)
    if args.set_files:
        files, sources = _candidate_file_entries(product, args.set_files)
        ev_data = {"files": files, "sources": sources, "sha256": _candidate_manifest_sha(files)}
        display = f"{len(files)} 个文件"
    else:
        fp = _resolve_inside(product, args.set_path, "候选文件")
        if _in_product_temp(product, fp):
            die("产品根 TEMP/ 是临时夹，不能登记成候选。改过的程序放在工作拷贝里。", 3)
        if not fp.is_file():
            die(f"候选文件不存在或不是普通文件：{fp}", 2)
        stored = _stored_rel(product, fp)
        ev_data = {"path": stored, "sha256": sha256_file(fp)}
        display = stored
    upstream_content = {b.get("sha256") for b in contract.get("upstream", {}).get("baseline", [])}
    for old in ledger:
        if old.get("kind") == "candidate" and old.get("role") == "upstream":
            upstream_content |= _candidate_content_shas(old)
    if role not in ("upstream", "working") and (parent_sha == ev_data["sha256"]
                             or not (_candidate_content_shas(ev_data) - upstream_content)):
        die(f"{role} 候选必须包含 baseline/历史 upstream 之外的新内容；不能换哈希形式或绕路重贴原件。", 3)
    if role == "release":
        probe = set()
        for old in ledger:
            if old.get("kind") == "candidate" and old.get("role") == "access":
                probe |= _candidate_content_shas(old)
        if probe and (_candidate_content_shas(ev_data) & probe):
            die("release 候选不能复用 access 探针原字节；出货前换成正式候选。", 3)
    event = {
        "kind": "candidate", **ev_data, "role": role, "parent_sha": parent_sha,
        "note": args.note or "", "revert": revert, "bless": False,
    }
    blessed = False
    if args.bless:
        if role == "release":
            min_phase = release_role_min_phase(contract, phases)
            min_idx = phases.index(min_phase) if min_phase in phases else None
            if min_idx is not None and cur < min_idx:
                die(f"拒绝：release 候选不能在 {min_phase.get('id')} 之前 bless；"
                    "先完成前置阶段和物理门，不能用 release 角色提前解锁打包。", 3)
            gaps = physical_receipt_missing_before(
                product, contract, phases, ledger, cur)
            if gaps:
                die("release 候选不能先 bless：前置物理门未通过：" + "、".join(gaps)
                    + "。先按当前阶段运行机器探针并确认，不能用 last-good 提前解锁打包。", 3)
        try:
            _commit_last_good(hub, product, event)
            blessed = True
        except OSError as e:
            append_ledger(hub, event)
            die(f"候选已登记，但 last-good 快照没做成（{e}）——未记 bless、未生成回退点。", 2)
    event["bless"] = blessed
    ev = append_ledger(hub, event)
    tag = "，并存为 last-good 候选快照" if blessed else ""
    print(f"已登记当前候选[{role}]：{display}（{ev['sha256'][:16]}…）{tag}")
    if parent_sha:
        print(f"  parent：{parent_sha[:16]}…")
    if blessed:
        print("注意：last-good 只覆盖已登记的候选文件集；源码历史和用户数据仍靠 Git/数据备份。")
def cmd_baseline(args):
    hub, contract = load_contract(args.product)
    _need_contract(args.product, contract)
    _guard_identity(args.product, contract)
    product = Path(args.product).resolve()
    up = dict(contract.get("upstream", {}) or {})
    old_fp = contract_fingerprint(contract)
    old_ver = up.get("version", "")
    changed = False
    if args.set_path is not None:
        baseline = []
        for raw in args.set_path:
            f = _resolve_inside(product, raw, "baseline 文件")
            if not f.exists():
                die(f"baseline 文件不存在：{f}", 2)
            if _in_product_temp(product, f):
                die("产品根 TEMP/ 是临时夹，不能当原件/baseline。", 3)
            baseline.append({"path": _stored_rel(product, f), "sha256": sha256_file(f), "size": f.stat().st_size})
        up["baseline"] = baseline
        changed = True
    if args.upstream_version is not None:
        up["version"] = args.upstream_version
        changed = True
    if not changed:
        die("baseline 命令需要 --set <文件...> 或 --upstream-version 其一（要锁 baseline 或换上游版本）。", 2)
    contract["upstream"] = up
    new_fp = contract_fingerprint(contract)
    write_json(hub / "contract.json", contract)  # 原子写：失败则旧合同不变，可回滚
    n_old = len([e for e in read_ledger(hub) if e.get("kind") == "confirm" and e.get("fp") == old_fp])
    append_ledger(hub, {"kind": "baseline", "old_fp": old_fp, "new_fp": new_fp,
                        "old_version": old_ver, "new_version": up.get("version", ""),
                        "baseline_files": len(up.get("baseline", [])), "note": args.note or ""})
    print(f"已更新上游身份：版本「{old_ver or '(空)'}」→「{up.get('version', '') or '(空)'}」，baseline 锁定 {len(up.get('baseline', []))} 个文件。")
    if new_fp != old_fp:
        print(f"版本指纹变化（{old_fp}→{new_fp}）：此前 {n_old} 条确认属于旧指纹、已自动作废，需在新版本下重新确认。")
        print("manifest 重放清单（anchors/patches/ui/build/dossier/replay_order）保留原样，但换版本后须逐条复验、重放。")
    else:
        print("版本指纹未变，既有确认继续有效。")
    print("下一步：python state.py status --product " + str(product))
def cmd_rebind(args):
    hub, contract = load_contract(args.product)
    _need_contract(args.product, contract)
    product = Path(args.product).resolve()
    reg = _load_registry_for_write()
    match = next((r for r in reg.get("products", []) if r.get("path") == str(product)), None)
    if match and match.get("product_id") != contract.get("product_id") and not args.force_identity:
        die(f"拒绝 rebind：登记表说这路径是「{match.get('product_id')}」，合同却是「{contract.get('product_id')}」。"
            f"这是身份冲突，不是普通搬家。确认要抹平就加 --force-identity（会记进账本）。", 3)
    old = contract.get("root")
    contract["root"] = str(product)
    write_json(hub / "contract.json", contract)
    _registry_upsert(contract["product_id"], str(product), contract.get("type", ""), contract.get("product_uuid"))
    append_ledger(hub, {"kind": "rebind", "old_root": old or "", "new_root": str(product),
                        "forced_identity": bool(args.force_identity)})
    if old and old != str(product):
        print(f"已更新登记路径：\n  旧 {old}\n  新 {product}")
    else:
        print(f"已确认登记路径：{product}")
    if match and args.force_identity:
        print(f"（已抹平身份冲突：{match.get('product_id')} → {contract.get('product_id')}，已记入账本）")
    print("身份已对齐，可以继续。")
def cmd_recover(args):
    hub, contract = load_contract(args.product)
    _need_contract(args.product, contract)
    _guard_identity(args.product, contract)
    product = Path(args.product).resolve()
    ledger = read_ledger(hub)
    phases, _, _, cur, _, _ = derive(contract, ledger)
    current, last_good = candidate_pointers(ledger)
    cand_state, _ = _candidate_live(product, current)
    done = cur >= len(phases)
    phase = None if done else phases[cur]
    block = active_block(ledger, phase["id"]) if phase else None
    need = _missing_required_artifacts(phase, contract, ledger, hub, product) if phase else []
    responsibilities = None
    responsibility_error = None
    if done or _contract_schema(contract) >= 3 or any(e.get('kind') == 'work_define' for e in ledger):
        try:
            responsibilities = work_view(product, hub, contract, phase=phase['id'] if phase else None, ledger=ledger)
            need = list(need) + responsibilities['gaps']
        except (ValueError, TypeError, KeyError) as error:
            need = list(need) + [f'责任账无法核验：{error}']
            responsibility_error = str(error)
    man = _validate_manifest(read_json(hub / "manifest.json", {}) or {})
    memory_gap = (not done) and _feature_memory_gap(product, man)
    if memory_gap:
        miss = "功能对照清单缺失；工程方先恢复现场事实，不能用旧总结假装记得"
        if miss not in need:
            need = list(need) + [miss]
    engineering = None
    if _contract_schema(contract) >= 3 or any(e.get('kind') == 'work_define' for e in ledger):
        engineering = engineering_next(contract, responsibilities, phase['id'] if phase else None,
            memory_gap=bool(memory_gap), blocked=bool(block),
            candidate_issue=cand_state in ('mismatch', 'missing', 'temp'), view_error=responsibility_error)
    nxt = (engineering['action'] if engineering else
           "核对整单未完成责任" if done and need else "出口复核" if done else "提交 BLOCKED 决策卡" if block
           else "工程方先恢复功能对照清单，不要装记得、不要 confirm" if memory_gap
           else "继续本阶段调查" if need
           else "等待用户验收后 confirm")
    from hub_memory import memory_context
    project_memory = memory_context(product, ((engineering or {}).get('focus') or {}).get('id'))
    cand = {"label": _candidate_label(current) if current else None, "live": cand_state}
    if current:
        for k in ("role", "sha256", "parent_sha", "revert"):
            cand[k] = current.get(k)
    write_json(hub / "resume.json", {
        "ts": now_iso(), "product_id": contract.get("product_id"), "type": contract.get("type"),
        "path": str(product), "mission": _mission_data(contract),
        "phase_id": None if done else phase["id"], "stop_point": None if done else phase.get("stop_point"),
        "ready": not need and not block, "missing": need,
        "responsibilities": responsibilities, "engineering": engineering, "project_memory": project_memory,
        "blocked": (block or {}).get("result") if block else None,
        "candidate": cand, "last_good_sha": (last_good or {}).get("sha256"), "next": nxt,
    })
    print(f"已写入 {hub / 'resume.json'}；下一动作：{nxt}")
    if phase and not done:
        from hub_ask import (
            _data_mig_lines, _handoff_lines, _install_lines, _license_basic_lines,
            _update_analyze_lines,
        )
        for line in _update_analyze_lines(contract.get("type"), phase.get("id")):
            print(line)
        for line in _data_mig_lines(contract.get("type"), phase.get("id")):
            print(line)
        for line in _install_lines(contract.get("type"), phase.get("id")):
            print(line)
        for line in _handoff_lines(contract.get("type"), phase.get("id")):
            print(line)
        for line in _license_basic_lines(contract.get("type"), phase.get("id")):
            print(line)
    if (contract.get("type") == "exe-rebuild"
            and phase and phase.get("id") == "6-update"):
        print("这一格两件事，不能合成一句交差：")
        print("1. 客户已装那份软件里点更新（覆盖或本项 SKIP）。")
        print("2. 吃新上游：我们跟上原作者新版本（档案和改动图；不是客户点更新）。")
        print("先读产品根 CHANGES.md 和上一份发给客户的冻本。")
        print("靠「怎么找到」再认；搜不到当新门，不要跑旧脚本。")
        _print_change_map_how(product)
    if memory_gap and not engineering:
        print("功能记忆：本命令不负责记得现在人看见哪些功能。")
        print("功能对照清单缺失：工程方先从原话、Git、源码与实物恢复。不要 confirm。")
def cmd_restore(args):
    hub, contract = load_contract(args.product)
    _need_contract(args.product, contract)
    _guard_identity(args.product, contract)
    product = Path(args.product).resolve()
    lg = hub / "last-good"
    meta = read_json(lg / "last-good.json")
    if not meta:
        die("还没有 last-good 快照——先 `state candidate --set <文件> --bless` 存一个。", 2)
    if isinstance(meta.get("files"), list):
        actual = []
        for item in meta["files"]:
            if not isinstance(item, dict) or not item.get("path"):
                die("last-good 文件集元数据损坏。", 2)
            try:
                src = _inside_no_links(hub, Path("last-good") / "files" / Path(item["path"]))
            except (ValueError, OSError):
                die(f"last-good 快照路径不安全：{item['path']}", 2)
            if not src.is_file():
                die(f"last-good 快照文件不见了：{src}", 2)
            got = sha256_file(src)
            if got != item.get("sha256"):
                die(f"拒绝：last-good 快照已损坏：{item['path']}", 2)
            actual.append({"path": item["path"], "sha256": got, "size": src.stat().st_size})
        got_manifest = _candidate_manifest_sha(actual)
        if got_manifest != meta.get("sha256"):
            die("拒绝：last-good 文件集清单哈希不一致，不能恢复。", 2)
        changed = []
        for item in actual:
            dst = _resolve_inside(product, item["path"], "恢复目标")
            if _in_product_temp(product, dst):
                die("产品根 TEMP/ 是临时夹，不能把 last-good 写回去。", 3)
            if dst.exists() and (not dst.is_file() or sha256_file(dst) != item["sha256"]):
                changed.append((item, dst))
        expected_paths = {item["path"] for item in actual}
        present_sources = []
        for source in meta.get("sources", []):
            if not isinstance(source, dict) or not source.get("path"):
                die("last-good sources 元数据损坏。", 2)
            sp = product / source.get("path", "")
            if sp.exists():
                present_sources.append(source.get("path", ""))
        extras = []
        if present_sources:
            try:
                current_files, _ = _scan_candidate_sources(product, present_sources)
                extras = [product / item["path"] for item in current_files if item["path"] not in expected_paths]
            except (FileNotFoundError, ValueError, OSError) as e:
                die(f"恢复前无法安全扫描当前候选文件集：{e}", 3)
        if changed or extras:
            bak = hub / "pre-restore" / (now_iso().replace(":", "").replace("-", "").replace("Z", "")
                                          + "-" + uuid.uuid4().hex[:6])
            for item, dst in changed:
                if dst.is_file():
                    bdst = bak / Path(item["path"])
                    bdst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(dst, bdst)
                elif dst.is_dir():
                    shutil.copytree(dst, bak / Path(item["path"]))
            for extra in extras:
                if extra.is_file():
                    bdst = bak / extra.relative_to(product)
                    bdst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(extra, bdst)
            if not args.yes:
                die(f"当前候选有 {len(changed)} 个文件不同、{len(extras)} 个额外文件；已备份到 {bak}\\。"
                    f"覆盖已登记文件加 --yes；删除快照外文件还要加 --delete-extras。", 3)
            print(f"（覆盖前已备份当前成果到 {bak}\\）")
        for item in actual:
            src = lg / "files" / Path(item["path"])
            dst = _resolve_inside(product, item["path"], "恢复目标")
            if dst.is_dir():
                shutil.rmtree(dst)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        if extras and not getattr(args, "delete_extras", False):
            print(f"额外 {len(extras)} 个文件未删（要删须 --yes --delete-extras）。")
        elif extras:
            for extra in extras:
                if extra.is_file():
                    extra.unlink()
            print(f"已按 --delete-extras 删除快照外 {len(extras)} 个文件。")
        print(f"已恢复 last-good 文件集：{len(actual)} 个文件（清单 {got_manifest[:16]}…）")
        print("务必复验功能——文件回来不等于业务恢复。")
        return
    try:
        src = _inside_no_links(hub, Path("last-good") / meta["file"])
    except (ValueError, OSError):
        die("last-good 快照路径不安全。", 2)
    if not src.is_file():
        die(f"last-good 快照文件不见了：{src}", 2)
    want = meta.get("sha256", "")
    got = sha256_file(src)
    if want and got != want:
        die(f"拒绝：last-good 快照已损坏——记录 sha {want[:16]}… / 实际 {got[:16]}…。不能用坏快照覆盖成果。", 2)
    dst = _resolve_inside(product, meta["path"], "恢复目标")  # 越界/软链拒绝
    if _in_product_temp(product, dst):
        die("产品根 TEMP/ 是临时夹，不能把 last-good 写回去。", 3)
    if dst.exists():
        cur = sha256_file(dst) if dst.is_file() else None
        if cur != got:
            bak = hub / "pre-restore" / (now_iso().replace(":", "").replace("-", "").replace("Z", "")
                                          + "-" + uuid.uuid4().hex[:6])
            bak.mkdir(parents=True, exist_ok=True)
            if dst.is_dir():
                shutil.copytree(dst, bak / dst.name, dirs_exist_ok=True)
            else:
                shutil.copy2(dst, bak / dst.name)
            if not args.yes:
                die(f"当前 {dst.name} 与 last-good 不同（可能是更新的成果）。已备份到 {bak}\\。确认要覆盖回退就加 --yes。", 3)
            print(f"（覆盖前已备份当前成果到 {bak}\\）")
            if dst.is_dir():
                shutil.rmtree(dst)
    shutil.copy2(src, dst)
    print(f"已把 last-good 恢复到：{dst}（sha {got[:16]}… 已校验一致）")
    print("务必复验功能——回滚不算数，除非它真的又能跑（§20.3：不能只看文件回来了）。")
