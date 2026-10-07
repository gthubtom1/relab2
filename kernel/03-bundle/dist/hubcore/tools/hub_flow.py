# -*- coding: utf-8 -*-
"""合同、阶段派生、候选指针、身份核对。"""
import hashlib
import json
import sys
import unicodedata
from pathlib import Path
from hub_io import (
    CANDIDATE_ROLES, CONTRACT_SCHEMA, KIND_TO_KEY, REGISTRY, PRODUCT_TYPES,
    PHYSICAL_RECEIPT_EVENT, PHYSICAL_RECEIPT_REQUIRED_FIELDS,
    PHYSICAL_RECEIPT_VERSION,
    _candidate_manifest_sha, _inside_no_links, _in_product_temp, _scan_candidate_sources,
    _seq, die, hub_of, read_json, _validate_manifest, sha256_file,
)
from hub_wording import _usable_claim, _has_empty_talk, _phrase_hit

# 旧合同可能没有 physical_checks 字段。对高风险阶段采用 fail-closed 默认值，
# 防止旧合同继续沿用“文字写了就算”的老门；显式 [] 只能由新合同用于声明该阶段
# 不需要物理运行（例如纯需求/架构讨论），不能关闭这些默认高风险阶段。
_DEFAULT_PHYSICAL_CHECKS = {
    "exe-rebuild": {
        "1-access": ("core_entry",),
        "3-ui": ("ui_regression",),
        "4-license": ("core_closed", "license_dataflow"),
        "5-pack": ("package_install", "core_closed", "license_dataflow"),
        "6-update": ("update_flow", "core_closed", "license_dataflow"),
        "7-handoff": ("handoff", "core_closed", "license_dataflow"),
    },
    "desktop-product": {
        "2-impl": ("business_flow",),
        "3-build": ("business_flow",),
        "4-package": ("package_install", "business_flow"),
        "5-install": ("clean_install", "business_flow"),
        "6-update": ("update_rollback", "business_flow"),
        "7-handoff": ("handoff", "business_flow"),
    },
    "web-service": {
        "2-impl": ("business_flow",),
        "3-build": ("business_flow",),
        "4-staging": ("staging_business",),
        "5-data": ("migration_backup", "business_flow"),
        "6-release": ("release_rollback", "business_flow"),
        "7-ops": ("handoff", "business_flow"),
    },
    "cli-tool": {
        "2-impl": ("command_flow",),
        "3-build": ("command_flow",),
        "4-package": ("package_install", "command_flow"),
        "5-install": ("clean_install", "command_flow"),
        "6-update": ("update_rollback", "command_flow"),
        "7-handoff": ("handoff", "command_flow"),
    },
    "source-takeover": {
        "1-baseline": ("baseline_repro",),
        "3-safety": ("safety_net",),
        "4-change": ("change_regression",),
        "5-build": ("release_candidate",),
        "6-release": ("release_rollback", "release_candidate"),
        "7-handoff": ("handoff", "release_candidate"),
    },
    "protocol-automation": {
        "1-env-traffic": ("traffic_boundary",),
        "4-protocol-verify": ("causality_proof",),
        "5-automate": ("automation_run",),
        "6-test-regression": ("automation_run",),
        "7-handoff": ("delivery_clean", "handoff"),
    },
}

_REQUIRED_PHASE_ORDER = {
    "desktop-product": ("0-spec", "1-arch", "2-impl", "3-build", "4-package",
                        "5-install", "6-update", "7-handoff"),
    "web-service": ("0-spec", "1-arch", "2-impl", "3-build", "4-staging",
                    "5-data", "6-release", "7-ops"),
    "cli-tool": ("0-spec", "1-arch", "2-impl", "3-build", "4-package",
                 "5-install", "6-update", "7-handoff"),
    "source-takeover": ("0-intake", "1-baseline", "2-map", "3-safety",
                        "4-change", "5-build", "6-release", "7-handoff"),
    "protocol-automation": ("0-spec", "1-env-traffic", "2-discovery", "3-solve-re",
                            "4-protocol-verify", "5-automate", "6-test-regression", "7-handoff"),
    "exe-rebuild": ("0-discover-plan", "1-access", "2-boundary", "3-ui",
                    "4-license", "5-pack", "6-update", "7-handoff"),
}
_LEGACY_EXE_PHASE_ORDER = ("0-discover-plan", "1-access", "2-license", "3-ship")

# A release-role candidate is a shipping candidate, not an arbitrary early
# last-good snapshot.  It may be refreshed after that phase (for example before
# update/release work), but it cannot be blessed before the first shipping
# phase for the known product line.
# 实现/授权/打包类检查不能用 baseline 绿当证明；入口禁令和收据消费必须同一份名单。
NO_BASELINE_GREEN = frozenset({
    "core_closed", "license_dataflow", "package_install",
    "core_entry", "ui_regression",
    "business_flow", "command_flow", "update_flow", "handoff", "clean_install",
    "staging_business", "update_rollback", "migration_backup",
    "release_rollback", "safety_net", "change_regression", "release_candidate",
    "traffic_boundary", "causality_proof", "automation_run", "delivery_clean",
})

# 接了自己的授权后，原创/接手也要机器观察三种基础；这场不接不套。
_LICENSE_WHEN_ASKED = {
    "desktop-product": ("4-package", "5-install", "6-update", "7-handoff"),
    "cli-tool": ("4-package", "5-install", "6-update", "7-handoff"),
    "web-service": ("4-staging", "5-data", "6-release", "7-ops"),
    "source-takeover": ("5-build", "6-release", "7-handoff"),
    "protocol-automation": ("7-handoff",),
}


_RELEASE_ROLE_MIN_PHASE = {
    "exe-rebuild": "5-pack",
    "desktop-product": "3-build",
    "web-service": "3-build",
    "cli-tool": "3-build",
    "source-takeover": "5-build",
    "protocol-automation": "5-automate",
}


def release_role_min_phase(contract, phases):
    phase_id = _RELEASE_ROLE_MIN_PHASE.get((contract or {}).get("type"))
    return next((p for p in phases if p.get("id") == phase_id), None)


def physical_checks(contract, phase, *, asked_own_license=False):
    """Return the machine checks required by a phase.

    A missing field is deliberately not treated as “no checks” for known product
    types. Only an explicit empty list on a current contract can describe a
    genuinely non-runtime phase. This is the compatibility trap that prevents
    old contracts from silently retaining the old soft gate.
    """
    p = phase or {}
    ptype = (contract or {}).get("type")
    mandatory = tuple((_DEFAULT_PHYSICAL_CHECKS.get(ptype, {})
                       .get(p.get("id"), ())))
    extra = ()
    if asked_own_license and p.get("id") in _LICENSE_WHEN_ASKED.get(ptype, ()):
        extra = ("license_dataflow",)
    if "physical_checks" in p:
        raw = p.get("physical_checks")
        if not isinstance(raw, list):
            return tuple(dict.fromkeys((*mandatory, *extra)))
        # Known high-risk gates are additive.  A hand-edited contract cannot
        # turn core_closed/license_dataflow/package_install into [] and thereby
        # restore the old report-only path.
        return tuple(dict.fromkeys((*mandatory, *raw, *extra)))
    return tuple(dict.fromkeys((*mandatory, *extra)))


def phase_physical_checks(product, contract, phase):
    """physical_checks plus 接了自己的授权时的三种基础观察。"""
    asked = False
    ptype = (contract or {}).get("type")
    if ptype in _LICENSE_WHEN_ASKED:
        try:
            from hub_ask import _asked_own_license
            man = _validate_manifest(read_json(hub_of(Path(product)) / "manifest.json", {}) or {})
            asked = bool(_asked_own_license(man, contract))
        except (OSError, TypeError, ValueError, KeyError):
            # 读不出有没有接授权时，按接了处理，缺收据不能过门。
            asked = True
    return physical_checks(contract, phase, asked_own_license=asked)


_PHYSICAL_SPEC_REL = Path(".hub") / "physical-gates.json"


def _physical_spec_binding(product, check_id):
    """Return the current config/file/command binding for a check.

    A receipt is evidence for one exact probe definition, not a permanent PASS
    flag.  If the product changes physical-gates.json or its command, the old
    receipt must stop satisfying the gate.
    """
    try:
        spec_path = _inside_no_links(product, _PHYSICAL_SPEC_REL)
        if not spec_path.is_file():
            return None
        data = json.loads(spec_path.read_text(encoding="utf-8-sig"))
        spec = data.get("checks", {}).get(check_id)
        command = spec.get("command") if isinstance(spec, dict) else None
        if not isinstance(command, list) or not command or any(
                not isinstance(x, str) or not x for x in command):
            return None
        command_path = _inside_no_links(product, command[0])
        if not command_path.is_file() or _in_product_temp(product, command_path):
            return None
        argv = ([sys.executable, str(command_path), *command[1:]]
                if command_path.suffix.casefold() == ".py"
                else [str(command_path), *command[1:]])
        command_payload = {"argv": argv, "file_sha256": sha256_file(command_path)}
        command_raw = json.dumps(command_payload, ensure_ascii=False, sort_keys=True,
                                 separators=(",", ":"))
        return (sha256_file(spec_path), hashlib.sha256(command_raw.encode("utf-8")).hexdigest(),
                spec.get("kind"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, AttributeError, TypeError, ValueError):
        return None


def _candidate_paths(candidate):
    if not isinstance(candidate, dict):
        return []
    files = candidate.get("files")
    if isinstance(files, list):
        return sorted({str(x.get("path")) for x in files
                       if isinstance(x, dict) and isinstance(x.get("path"), str)})
    path = candidate.get("path")
    return [path] if isinstance(path, str) and path else []


def _red_receipt_for(ledger, product, contract, phase, check_id, cand_sha,
                     epoch, candidate_paths, spec_sha, command_sha):
    # TDD fixes change bytes. Follow registered predecessors backwards instead
    # of demanding that the fixed candidate had already exhibited the defect.
    # Each link must refer to an earlier event; unrelated branches cannot lend RED.
    registrations = [e for e in ledger if e.get("kind") == "candidate"]
    ancestors = []
    parent_sha = cand_sha
    for index in range(len(registrations) - 1, -1, -1):
        entry = registrations[index]
        if entry.get("sha256") != parent_sha:
            continue
        entry_paths = _candidate_paths(entry)
        if not entry_paths or (not ancestors and entry_paths != candidate_paths):
            break
        # A hash can occur on multiple branches or be registered repeatedly.
        # Only observations made while this registration was current belong
        # to it. A later reuse of the bytes cannot lend evidence backwards.
        end = registrations[index + 1]["n"] if index + 1 < len(registrations) else float("inf")
        ancestors.append((parent_sha, entry["n"], end, entry_paths))
        parent_sha = entry.get("parent_sha")
        if not parent_sha:
            break
    for event in reversed(ledger):
        if (event.get("kind") == PHYSICAL_RECEIPT_EVENT
                and event.get("receipt_version") == PHYSICAL_RECEIPT_VERSION
                and all(key in event for key in PHYSICAL_RECEIPT_REQUIRED_FIELDS)
                and event.get("generated_by") == "state"
                and event.get("probe_nonce") and event.get("nonce") and event.get("sandbox_id")
                and event.get("check_id") == check_id
                and event.get("phase_id") == phase.get("id")
                and event.get("product_root") == str(Path(product).resolve())
                and event.get("fp") == contract_fingerprint(contract)
                and event.get("epoch") == epoch
                and any(event.get("cand_sha") == sha and start < event.get("n", 0) < end
                        and event.get("candidate_paths") == paths
                        for sha, start, end, paths in ancestors)
                and event.get("stage") == "red"
                and event.get("result") == "fail"
                and event.get("spec_sha") == spec_sha
                and event.get("command_sha") == command_sha
                and isinstance(event.get("observed"), dict)
                and _red_observation_ok(event["observed"])):
            return event
    return None


def _red_observation_ok(observed):
    """超时也算一次真失败；探针命令没拉起来不算。"""
    if not isinstance(observed, dict):
        return False
    if observed.get("candidate_unchanged") is not True:
        return False
    if observed.get("binding_unchanged") is not True:
        return False
    if observed.get("red_valid") is not True:
        return False
    if "launch_error_type" in observed:
        return False
    if observed.get("timed_out") is True:
        return True
    protocol = observed.get("probe_protocol")
    return (
        isinstance(protocol, dict)
        and protocol.get("context_ok") is True
        and protocol.get("observed_from_candidate") is True
    )


OWNER_CLOSED_EVENT = "owner_closed_observation"
OWNER_SEEN_EVENT = "owner_seen_observation"
_OWNER_CLOSED_MARK = (
    "关上", "关掉", "没进", "进不了", "没有主窗", "没有窗口", "无窗口",
    "没反应", "马上退", "马上退出", "立刻退出", "立刻退", "双击没有",
    "双击没", "进程退了", "进程退出", "无换肤窗口", "没有换肤",
    "没有主界面", "进不了主功能", "没有主功能",
    "不是主窗", "不是主程序", "不是换肤", "闪屏", "闪了一下",
    "报错窗", "错误窗", "误判",
)
_OWNER_SEEN_MARK = _OWNER_CLOSED_MARK + (
    "看见", "看到", "双击", "点了", "点完", "打开", "过期", "装上", "装完",
    "安装", "界面", "窗口", "进程", "退出", "报错", "能用", "结果",
    "主流程", "放行", "卡密", "皮肤", "按钮", "停了", "关了", "测过",
    "试过", "手动", "命令", "页面", "更新", "回滚", "交货",
)
_OWNER_CLOSED_STAMP = (
    "符合要求", "符合预期", "可以继续", "核对无误", "已经通过",
    "全部通过", "没问题", "可以打包", "可以发布", "主人看过", "用户点头",
    "用户确认", "看起来没有",
)
_OWNER_SEEN_STAMP = _OWNER_CLOSED_STAMP
_STATIC_EXPIRY = (365, 365 * 24 * 60 * 60)
_VERIFY_INTERVAL_SECONDS = frozenset({20, 60})
_NEAR_INTERVAL_SECONDS = 2
_INTERVAL_KEYS = (
    "verify_interval_seconds", "cache_until", "cache_until_seconds", "cache_seconds",
    "next_verify_at",
)


_LICENSE_SEEN_MARK = (
    "过期", "放行", "不放行", "卡密", "关上", "关掉", "停了", "停掉",
    "设备码", "三种", "关核心", "授权页",
    "挤掉", "解绑", "DEVICE_NOT_BOUND", "没人挤", "间隔还在",
)


def _fold_quote(s):
    """压掉空白、标点、零宽和合字音标，再比过门章。"""
    text = unicodedata.normalize("NFKC", str(s or ""))
    out = []
    for ch in text:
        cat = unicodedata.category(ch)
        if cat in ("Cf", "Mn", "Me") or ch in ("\ufe0f", "\ufe0e"):
            continue
        if ch.isspace() or cat.startswith("P"):
            continue
        out.append(ch)
    return "".join(out)


def _stamp_in_quote(quote, stamps):
    s = str(quote or "")
    if _has_empty_talk(s) or _phrase_hit(s, stamps):
        return True
    compact = _fold_quote(s)
    return any(p and _fold_quote(p) in compact for p in stamps)


def _owner_closed_quote_ok(quote):
    """主人原话必须是看见关上了，不能是「符合要求」这种过门章。"""
    s = str(quote or "").strip()
    if not _usable_claim(s, min_len=12):
        return False
    if _stamp_in_quote(s, _OWNER_CLOSED_STAMP):
        return False
    return bool(_phrase_hit(s, _OWNER_CLOSED_MARK))


def _owner_seen_quote_ok(quote, check_id=""):
    """主人原话必须是亲手看见的结果，不能是「符合要求」这种过门章。"""
    if check_id == "core_closed":
        return _owner_closed_quote_ok(quote)
    s = str(quote or "").strip()
    if not _usable_claim(s, min_len=12):
        return False
    if _stamp_in_quote(s, _OWNER_SEEN_STAMP):
        return False
    if check_id == "license_dataflow":
        return (
            bool(_phrase_hit(s, ("没人挤",)))
            and bool(_phrase_hit(s, ("挤掉", "解绑", "DEVICE_NOT_BOUND")))
        )
    return bool(_phrase_hit(s, _OWNER_SEEN_MARK))


def _owner_seen_protocol_ok(observed):
    protocol = (observed or {}).get("probe_protocol")
    return (
        isinstance(protocol, dict)
        and protocol.get("context_ok") is True
        and protocol.get("observed_from_candidate") is True
        and observed.get("timed_out") is False
    )


def _owner_seen_reason(observed, check_id=""):
    """这一次机器没看成或可能误判的原因。不同原因的点头不能互相盖住。"""
    if not isinstance(observed, dict) or _owner_seen_blocked(observed, check_id):
        return None
    if observed.get("already_passing") is True or observed.get("red_required_failure") is True:
        return "already_passing"
    if "launch_error_type" in observed:
        return "launch_error"
    if observed.get("candidate_main_opened"):
        return "opened"
    if observed.get("timed_out") is True:
        return "timeout"
    if check_id == "core_closed" and (observed.get("candidate_main_unverified") or []):
        return "unverified"
    if not _owner_seen_protocol_ok(observed):
        return "no_protocol"
    if observed.get("probe_assertions_ok") is False:
        return "assertion"
    return None


def _expiry_seconds_value(raw):
    if isinstance(raw, bool) or raw is None:
        return None
    if type(raw) in (int, float):
        if isinstance(raw, float) and not raw.is_integer():
            return raw
        return int(raw)
    if isinstance(raw, str):
        text = raw.strip()
        if text.isdigit() or (text.startswith("-") and text[1:].isdigit()):
            return int(text)
    return None


def _is_static_expiry(raw):
    """硬编码整年，不是卡还剩多久。"""
    value = _expiry_seconds_value(raw)
    return value in _STATIC_EXPIRY


def _interval_seconds_value(js):
    values = _all_interval_values(js)
    return values[0] if values else None


def _all_interval_values(js):
    if not isinstance(js, dict):
        return []
    out = []
    for key in _INTERVAL_KEYS:
        value = _expiry_seconds_value(js.get(key))
        if value is not None:
            out.append(value)
    return out


def _verify_interval_value(js):
    if not isinstance(js, dict):
        return None
    return _expiry_seconds_value(js.get("verify_interval_seconds"))


def _is_near_interval(value, interval):
    if value is None or interval is None:
        return False
    return abs(value - interval) <= _NEAR_INTERVAL_SECONDS


def _is_verify_interval_expiry(raw, js=None):
    """20/60 秒再问间隔、cache_until / next_verify_at，或贴近间隔的缩短到期。"""
    value = _expiry_seconds_value(raw)
    if value is None:
        return False
    if value in _VERIFY_INTERVAL_SECONDS:
        return True
    for interval in _all_interval_values(js or {}):
        if value == interval or _is_near_interval(value, interval):
            return True
    return False


def _card_remaining_expiry_ok(raw, js=None):
    """核心 expiry_seconds 必须是卡还剩多久，且大于每一个再问/缓存间隔。"""
    value = _expiry_seconds_value(raw)
    js = js if isinstance(js, dict) else {}
    if value is None or _is_static_expiry(raw) or _is_verify_interval_expiry(raw, js):
        return False
    if _verify_interval_value(js) is None:
        return False
    intervals = _all_interval_values(js)
    if not intervals:
        return False
    return all(value > interval for interval in intervals)


def _kick_closed_ok(js):
    if not isinstance(js, dict):
        return False
    kicked = js.get("kicked_closed")
    kick = js.get("kick_closed")
    if kicked is False and kick is True:
        return False
    return kicked is True or kick is True


def _owner_seen_blocked(observed, check_id=""):
    """硬编码年、间隔当到期、自己关当挤机、限流当停，不能点头洗白。"""
    if not isinstance(observed, dict):
        return True
    js = observed.get("json") or {}
    if not isinstance(js, dict):
        js = {}
    expiry = js.get("expiry_seconds")
    if _is_static_expiry(expiry):
        return True
    if expiry is not None and not _card_remaining_expiry_ok(expiry, js):
        return True
    if js.get("rate_limited_closed") is True:
        return True
    if js.get("solo_still_open") is False:
        return True
    if ((js.get("kicked_closed") is False or js.get("kick_closed") is False)
            and not _kick_closed_ok(js)):
        return True
    if js.get("mid_run_closed") is False:
        return True
    if js.get("periodic_verify") is False:
        return True
    if check_id == "license_dataflow":
        if js.get("solo_still_open") is not True:
            return True
        if not _kick_closed_ok(js):
            return True
        if js.get("rate_limited_closed") is not False:
            return True
        if js.get("mid_run_closed") is not True:
            return True
        if js.get("periodic_verify") is not True:
            return True
        if not _card_remaining_expiry_ok(expiry, js):
            return True
    return False


_OWNER_WAIVE_RED = frozenset({
    "launch_error", "already_passing", "no_protocol", "opened",
})


def _owner_waives_fail_red(ledger, event):
    """探针没拉起来、或已经是对的所以红不了：主人点头可代替失败红。"""
    if not isinstance(event, dict) or not isinstance(ledger, list):
        return False
    if event.get("observed", {}).get("owner_seen_accepted") is not True:
        return False
    reason = _owner_seen_reason(event.get("observed") or {}, event.get("check_id"))
    if reason not in _OWNER_WAIVE_RED:
        return False
    return _owner_seen_covers(ledger, event)


def _owner_seen_needed(observed, check_id=""):
    """机器没看成、超时、误判，或自动化没点到时，才需要主人这一项观察。"""
    return _owner_seen_reason(observed, check_id) is not None


def _owner_closed_covers(ledger, receipt_event):
    """GREEN 收据里仍是没能证明时，须先有主人针对这一次观察的点头。"""
    if not isinstance(receipt_event, dict) or not isinstance(ledger, list):
        return False
    observed = receipt_event.get("observed") or {}
    if not isinstance(observed, dict):
        return False
    if observed.get("candidate_main_opened"):
        return False
    unverified = observed.get("candidate_main_unverified") or []
    if not unverified or observed.get("naked_start_attempted") is not True:
        return False
    receipt_n = receipt_event.get("n")
    if isinstance(receipt_n, bool) or not isinstance(receipt_n, int) or receipt_n <= 0:
        return False
    want = (
        receipt_event.get("cand_sha"),
        receipt_event.get("epoch"),
        receipt_event.get("fp"),
        receipt_event.get("phase_id"),
    )
    paths = list(unverified)
    for event in ledger:
        if event.get("kind") != OWNER_CLOSED_EVENT:
            continue
        n = event.get("n")
        if isinstance(n, bool) or not isinstance(n, int) or n <= 0 or n >= receipt_n:
            continue
        if event.get("check_id") != "core_closed":
            continue
        if (event.get("cand_sha"), event.get("epoch"), event.get("fp"),
                event.get("phase_id")) != want:
            continue
        if list(event.get("unverified_paths") or []) != paths:
            continue
        if not _owner_closed_quote_ok(event.get("quote")):
            continue
        return True
    return False


def _owner_seen_covers(ledger, receipt_event):
    """GREEN 仍没看成时，须先有主人针对这一项检查的观察。"""
    if not isinstance(receipt_event, dict) or not isinstance(ledger, list):
        return False
    observed = receipt_event.get("observed") or {}
    check_id = receipt_event.get("check_id")
    if _owner_seen_blocked(observed, check_id):
        return False
    reason = _owner_seen_reason(observed, check_id)
    if not check_id or not reason:
        return False
    if check_id == "core_closed" and (observed.get("candidate_main_unverified") or []):
        if observed.get("naked_start_attempted") is True and _owner_closed_covers(ledger, receipt_event):
            return True
    receipt_n = receipt_event.get("n")
    if isinstance(receipt_n, bool) or not isinstance(receipt_n, int) or receipt_n <= 0:
        return False
    want = (
        receipt_event.get("cand_sha"),
        receipt_event.get("epoch"),
        receipt_event.get("fp"),
        receipt_event.get("phase_id"),
        check_id,
    )
    for event in ledger:
        if event.get("kind") != OWNER_SEEN_EVENT:
            continue
        n = event.get("n")
        if isinstance(n, bool) or not isinstance(n, int) or n <= 0 or n >= receipt_n:
            continue
        if (event.get("cand_sha"), event.get("epoch"), event.get("fp"),
                event.get("phase_id"), event.get("check_id")) != want:
            continue
        if event.get("cover_reason") != reason:
            continue
        if not _owner_seen_quote_ok(event.get("quote"), check_id):
            continue
        return True
    return False


def _latest_check_receipt(ledger, product, contract, phase_id, cand_sha, epoch, check_id):
    product_root = str(Path(product).resolve())
    fp = contract_fingerprint(contract)
    for event in reversed(ledger or []):
        if (event.get("kind") == PHYSICAL_RECEIPT_EVENT
                and event.get("check_id") == check_id
                and event.get("phase_id") == phase_id
                and event.get("cand_sha") == cand_sha
                and event.get("epoch") == epoch
                and event.get("fp") == fp
                and event.get("product_root") == product_root):
            return event
    return None


def _latest_core_closed_receipt(ledger, product, contract, phase_id, cand_sha, epoch):
    return _latest_check_receipt(
        ledger, product, contract, phase_id, cand_sha, epoch, "core_closed")


def _physical_receipt_valid(event, product, contract, phase, check_id, cand_sha, epoch,
                            binding=None, candidate_paths=None, ledger=None):
    if not isinstance(event, dict):
        return False
    if event.get("kind") != PHYSICAL_RECEIPT_EVENT:
        return False
    if event.get("receipt_version") != PHYSICAL_RECEIPT_VERSION:
        return False
    if event.get("generated_by") != "state":
        return False
    if event.get("check_id") != check_id or event.get("phase_id") != phase.get("id"):
        return False
    if event.get("product_root") != str(Path(product).resolve()):
        return False
    if event.get("fp") != contract_fingerprint(contract):
        return False
    if event.get("epoch", -1) != epoch or event.get("cand_sha") != cand_sha:
        return False
    if candidate_paths is None or event.get("candidate_paths") != candidate_paths:
        return False
    if (isinstance(event.get("n"), bool) or not isinstance(event.get("n"), int)
            or event.get("n") <= 0):
        return False
    if event.get("result") != "pass" or event.get("stage") != "green" or not event.get("nonce"):
        return False
    if not isinstance(event.get("probe_nonce"), str) or not event.get("probe_nonce"):
        return False
    if not isinstance(event.get("sandbox_id"), str) or not event.get("sandbox_id"):
        return False
    if not isinstance(event.get("observed"), dict):
        return False
    observed = event['observed']
    if (observed.get('candidate_unchanged') is not True
            or observed.get('binding_unchanged') is not True
            or observed.get('output_oversized') is True):
        return False
    protocol = observed.get('probe_protocol')
    protocol_ok = (
        isinstance(protocol, dict)
        and protocol.get('context_ok') is True
        and protocol.get('observed_from_candidate') is True
        and observed.get('timed_out') is False
    )
    unverified = bool(check_id == "core_closed" and (observed.get("candidate_main_unverified") or []))
    needs_owner = (
        observed.get("timed_out") is True
        or unverified
        or not protocol_ok
        or observed.get("probe_assertions_ok") is False
        or bool(observed.get("candidate_main_opened"))
        or "launch_error_type" in observed
        or observed.get("already_passing") is True
    )
    if needs_owner:
        if not _owner_seen_covers(ledger, event):
            return False
    elif not protocol_ok:
        return False
    if not event.get("spec_sha") or not event.get("command_sha"):
        return False
    if not all(k in event for k in PHYSICAL_RECEIPT_REQUIRED_FIELDS):
        return False
    if binding is None:
        binding = _physical_spec_binding(product, check_id)
    if binding is None:
        return False
    spec_sha, command_sha, probe_kind = binding
    return (event.get("spec_sha") == spec_sha
            and event.get("command_sha") == command_sha
            and event.get("probe_kind") == probe_kind)


def valid_regression_basis(rows, product, contract, check_id, spec_sha, command_sha):
    """Validate historical execution and its proof chain before lending a baseline."""
    valid = {}
    phases = {p['id']: p for p in contract['phases']}
    for index, event in enumerate(rows):
        phase = phases.get(event.get('phase_id'))
        if (not phase or event.get('check_id') != check_id
                or event.get('spec_sha') != spec_sha or event.get('command_sha') != command_sha):
            continue
        before = rows[:index]
        candidate, _ = candidate_pointers(before)
        if not candidate or candidate.get('sha256') != event.get('cand_sha'):
            continue
        if not _physical_receipt_valid(event, product, contract, phase, check_id,
                event['cand_sha'], phase_epoch(contract, rows, phase['id']),
                (spec_sha, command_sha, event.get('probe_kind')), _candidate_paths(candidate),
                ledger=before):
            continue
        mode = event.get('verification_mode', 'change')
        proven = False
        if mode == 'baseline':
            proven = check_id not in NO_BASELINE_GREEN
        elif mode == 'change':
            red = _red_receipt_for(before, product, contract, phase, check_id,
                event['cand_sha'], event['epoch'], _candidate_paths(candidate), spec_sha, command_sha)
            proven = bool(red and event.get('red_receipt_n') == red['n'])
            if not proven:
                proven = _owner_waives_fail_red(before, event)
        elif mode == 'regression':
            proven = event.get('regression_receipt_n') in valid
        if proven:
            valid[event['n']] = event
    return valid[max(valid)] if valid else None


def physical_receipts_for(product, hub, contract, phase, ledger=None, cand_sha=None):
    """Return valid current receipts keyed by check id for a phase."""
    checks = phase_physical_checks(product, contract, phase)
    if not checks or not cand_sha:
        return {}
    rows = ledger if ledger is not None else []
    candidate = None
    for entry in reversed(rows):
        if entry.get("kind") == "candidate" and entry.get("sha256") == cand_sha:
            candidate = entry
            break
    expected_paths = _candidate_paths(candidate)
    if not expected_paths:
        return {}
    epoch = phase_epoch(contract, rows, (phase or {}).get("id"))
    out = {}
    for check_id in checks:
        binding = _physical_spec_binding(product, check_id)
        for event in reversed(rows):
            # The latest observation for this subject wins, including failures.
            # Never skip a failed retry to resurrect an older successful run.
            if not (event.get("kind") == PHYSICAL_RECEIPT_EVENT
                    and event.get("check_id") == check_id
                    and event.get("phase_id") == phase.get("id")
                    and event.get("product_root") == str(Path(product).resolve())
                    and event.get("fp") == contract_fingerprint(contract)
                    and event.get("epoch") == epoch
                    and event.get("cand_sha") == cand_sha
                    and event.get("candidate_paths") == expected_paths):
                continue
            if _physical_receipt_valid(event, product, contract, phase, check_id,
                                       cand_sha, epoch, binding, expected_paths,
                                       ledger=rows):
                # Resolve the RED at the time GREEN was issued, not using
                # later observations or registrations. Broken references fail.
                previous = [e for e in rows if e.get("n", 0) < event["n"]]
                mode = event.get('verification_mode', 'change')
                mode_ok = False
                if mode == 'baseline':
                    # A baseline establishes current behavior, not a proven fix.
                    mode_ok = check_id not in NO_BASELINE_GREEN
                elif mode == 'regression':
                    basis = valid_regression_basis(previous, product, contract, check_id,
                                                   event['spec_sha'], event['command_sha'])
                    mode_ok = bool(basis and basis['n'] == event.get('regression_receipt_n'))
                elif mode == 'change':
                    red = _red_receipt_for(previous, product, contract, phase, check_id,
                                           cand_sha, epoch, expected_paths,
                                           event['spec_sha'], event['command_sha'])
                    mode_ok = bool(red and event.get('red_receipt_n') == red['n'])
                    if not mode_ok:
                        mode_ok = _owner_waives_fail_red(previous, event)
                observation = event.get('observed', {})
                if (mode_ok and observation.get('candidate_unchanged') is True
                        and observation.get('binding_unchanged') is True):
                    out[check_id] = event
            break
    return out


def physical_receipt_missing(product, hub, contract, phase, ledger=None, cand_sha=None):
    """Return missing physical checks for the exact current candidate/phase epoch."""
    checks = phase_physical_checks(product, contract, phase)
    if not checks:
        return []
    if not cand_sha:
        return list(checks)
    receipts = physical_receipts_for(product, hub, contract, phase, ledger, cand_sha)
    return [check_id for check_id in checks if check_id not in receipts]


def physical_receipt_missing_before(product, contract, phases, ledger, phase_index):
    """Check physical gates before a target phase using each phase's confirmed candidate.

    Besides checking that a valid receipt exists, require the confirm event to
    point at the exact receipt sequence numbers it relied on.  This prevents an
    old report-only confirm from being laundered by a later, unrelated probe.
    """
    out = []
    fp = contract_fingerprint(contract)
    for p in phases[:phase_index]:
        phase_sha = None
        confirm_event = None
        for event in reversed(ledger):
            if (event.get("kind") == "confirm" and event.get("fp") == fp
                    and event.get("phase_id") == p.get("id")
                    and event.get("stop_point") == p.get("stop_point")
                    and event.get("cand_sha")):
                phase_sha = event.get("cand_sha")
                confirm_event = event
                break
        checks = phase_physical_checks(product, contract, p)
        if not checks:
            continue
        receipts = (physical_receipts_for(product, hub_of(product), contract, p,
                                          ledger, phase_sha)
                    if phase_sha else {})
        for check_id in checks:
            if check_id not in receipts:
                out.append(f"{p.get('id')}:{check_id}")
        if not confirm_event:
            continue
        refs = confirm_event.get("physical_receipt_ns")
        if not isinstance(refs, dict):
            out.extend(f"{p.get('id')}:{check_id}:confirm-ref" for check_id in checks
                       if check_id in receipts)
            continue
        for check_id, receipt in receipts.items():
            ref = refs.get(check_id)
            if (isinstance(ref, bool) or not isinstance(ref, int)
                    or ref != receipt.get("n")):
                out.append(f"{p.get('id')}:{check_id}:confirm-ref")
    return out
def load_contract(product):
    hub = hub_of(product)
    c = read_json(hub / "contract.json")
    if c is not None:
        _validate_phases(c.get("phases", []), c.get("type"))  # 空/缺 phases 也要拦，否则 status 谎报完成
    return hub, c
def norm_key(text):
    return hashlib.sha256(" ".join((text or "").lower().split()).encode("utf-8")).hexdigest()[:12]
def _contract_schema(contract):
    raw = contract.get("schema_version", 1)
    if isinstance(raw, bool):
        die("合同 schema_version 类型不对。", 2)
    try:
        value = int(raw or 1)
    except (TypeError, ValueError):
        die(f"合同 schema_version 不合法：{raw!r}", 2)
    if value < 1 or value > CONTRACT_SCHEMA:
        die(f"不支持的合同 schema_version：{value}（当前最多 {CONTRACT_SCHEMA}）。", 2)
    return value
def _mission_data(contract):
    mission = contract.get("mission", {})
    if mission is None:
        return {}
    if not isinstance(mission, dict):
        die(f"合同 mission 类型不对：应为对象，实际 {type(mission).__name__}。", 2)
    return mission
def _mission_revision(contract):
    raw = _mission_data(contract).get("revision", 0)
    if isinstance(raw, bool):
        die("mission.revision 类型不对。", 2)
    try:
        value = int(raw or 0)
    except (TypeError, ValueError):
        die(f"mission.revision 不合法：{raw!r}", 2)
    if value < 0:
        die("mission.revision 不能小于 0。", 2)
    return value
def contract_fingerprint(contract):
    up = contract.get("upstream", {})
    if _contract_schema(contract) >= 2:
        payload = {"type": contract.get("type"), "upstream": up, "mission": _mission_data(contract),
                   "phases": contract.get("phases", []),
                   "schema_version": _contract_schema(contract)}
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    else:
        raw = "|".join([up.get("version", "")]
                       + sorted(b.get("sha256", "") for b in up.get("baseline", [])))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
def _mission_complete(contract):
    mission = _mission_data(contract)
    values = [mission.get(k) for k in ("goal", "success", "route")]
    return (_contract_schema(contract) >= 2 and _mission_revision(contract) >= 1
            and all(isinstance(v, str) and _usable_claim(v) for v in values))
def _validate_phases(phases, contract_type=None):
    if not phases:
        die("阶段定义为空——合同没有任何阶段。拒绝（防止空合同被 status 谎报为'已完成'）。", 2)
    if contract_type is not None and contract_type not in PRODUCT_TYPES:
        die(f"合同 product type 不支持：{contract_type!r}。不能改成未知类型来关闭默认物理门。", 3)
    seen = set()
    seen_ids = set()
    ids = []
    for ph in phases:
        if not ph.get("id") or not ph.get("stop_point"):
            die(f"阶段定义不合法：每个阶段必须有 id 和 stop_point（问题阶段：{ph.get('id') or ph}）。", 2)
        if ph["id"] in seen_ids:
            die(f"阶段定义不合法：阶段 id 重复「{ph['id']}」——会导致物理门和确认串位，请保留唯一阶段身份。", 3)
        seen_ids.add(ph["id"])
        ids.append(ph["id"])
        if ph["stop_point"] in seen:
            die(f"阶段定义不合法：stop_point 名重复「{ph['stop_point']}」——会导致确认串位/跳过阶段，请改成唯一。", 2)
        seen.add(ph["stop_point"])
    if contract_type in PRODUCT_TYPES:
        expected = _REQUIRED_PHASE_ORDER[contract_type]
        if (contract_type == "exe-rebuild"
                and "2-license" in ids and "3-ship" in ids
                and "2-boundary" not in ids):
            expected = _LEGACY_EXE_PHASE_ORDER
        elif (contract_type == "exe-rebuild" and "7-handoff" not in ids
              and ids == list(_REQUIRED_PHASE_ORDER["exe-rebuild"][:-1])):
            expected = _REQUIRED_PHASE_ORDER["exe-rebuild"][:-1]
        missing = [phase_id for phase_id in expected if phase_id not in ids]
        if missing:
            die(f"已知产品线 {contract_type} 缺少不可关闭的标准阶段：{', '.join(missing)}。"
                "不能通过删除/改名阶段绕过默认物理门。", 3)
        positions = [ids.index(phase_id) for phase_id in expected]
        if positions != sorted(positions):
            die(f"已知产品线 {contract_type} 的标准阶段顺序被改动：{', '.join(expected)}。"
                "不能通过重排阶段绕过前置物理门。", 3)
    for ph in phases:
        reqs = ph.get("requires", [])
        if not isinstance(reqs, list):
            die(f"阶段定义不合法：{ph['id']} 的 requires 必须是数组。", 2)
        if not reqs:
            die(f"阶段定义不合法：{ph['id']} 的 requires 不能为空（空确认会合法过门）。", 2)
        known = set(KIND_TO_KEY) | set(KIND_TO_KEY.values()) | {"mission", "baseline", "candidate"}
        unknown = [r for r in reqs if r not in known]
        if unknown:
            die(f"阶段定义不合法：{ph['id']} 有未知 requires：{unknown}", 2)
        if ph.get("candidate_role") and ph["candidate_role"] not in CANDIDATE_ROLES:
            die(f"阶段定义不合法：{ph['id']} 的 candidate_role 未知：{ph['candidate_role']}", 2)
        if "artifact_phase" in ph and not isinstance(ph["artifact_phase"], bool):
            die(f"阶段定义不合法：{ph['id']} 的 artifact_phase 必须是布尔值。", 2)
        if "require_bless" in ph and not isinstance(ph["require_bless"], bool):
            die(f"阶段定义不合法：{ph['id']} 的 require_bless 必须是布尔值。", 2)
        if "require_new_candidate" in ph and not isinstance(ph["require_new_candidate"], bool):
            die(f"阶段定义不合法：{ph['id']} 的 require_new_candidate 必须是布尔值。", 2)
        mandatory = tuple((_DEFAULT_PHYSICAL_CHECKS.get(contract_type, {})
                           .get(ph.get("id"), ())))
        if "physical_checks" in ph:
            checks = ph.get("physical_checks")
            if not isinstance(checks, list):
                die(f"阶段定义不合法：{ph['id']} 的 physical_checks 必须是数组。", 2)
            if any(not isinstance(x, str) or not x.strip() for x in checks):
                die(f"阶段定义不合法：{ph['id']} 的 physical_checks 只能包含非空名称。", 2)
            if len(set(checks)) != len(checks):
                die(f"阶段定义不合法：{ph['id']} 的 physical_checks 有重复名称。", 2)
            missing = [x for x in mandatory if x not in checks]
            if missing:
                die(f"阶段定义不合法：{ph['id']} 试图关闭必需物理门：{', '.join(missing)}。"
                    "已知高风险阶段不能用 physical_checks=[] 或删门绕过。", 3)
def derive(contract, ledger):
    phases = contract.get("phases", [])
    fp = contract_fingerprint(contract)
    sp_to_phase = {p["stop_point"]: p["id"] for p in phases if p.get("stop_point")}
    phase_index = {p["id"]: i for i, p in enumerate(phases)}
    all_confirms = [e for e in ledger if e.get("kind") == "confirm"]
    fp_confirms = [e for e in all_confirms if e.get("fp") == fp]
    stale = [e for e in all_confirms if e.get("fp") != fp]
    attempts = [e for e in ledger if e.get("kind") == "attempt"]
    reopens = [e for e in ledger if e.get("kind") == "reopen" and e.get("from_phase") in phase_index]
    latest = {}
    for e in fp_confirms:
        sp = e.get("stop_point")
        if sp not in latest or _seq(e) > _seq(latest[sp]):
            latest[sp] = e
    confirmed = set()
    confirms = []
    invalidated = []
    for sp, ce in latest.items():
        pid = sp_to_phase.get(sp)
        later = [a for a in attempts if a.get("phase_id") == pid and _seq(a) > _seq(ce)]
        pidx = phase_index.get(pid, len(phases))
        later_reopens = [
            r for r in reopens
            if _seq(r) > _seq(ce) and phase_index.get(r.get("from_phase"), len(phases)) <= pidx
        ]
        if later or later_reopens:
            invalidated.append((sp, pid, len(later) + len(later_reopens)))
        elif is_legacy_four_exe(contract) and pid == "3-ship":
            continue
        else:
            confirmed.add(sp)
            confirms.append(ce)
    cur = len(phases)
    skip_void_legacy = not is_legacy_four_exe(contract)
    for i, p in enumerate(phases):
        if p.get("stop_point") not in confirmed:
            if skip_void_legacy and legacy_four_void_phase(contract, p.get("id")):
                continue
            cur = i
            break
    return phases, confirms, confirmed, cur, stale, invalidated
def loop_warnings(ledger, phase_id):
    atts = [e for e in ledger if e.get("kind") == "attempt" and e.get("phase_id") == phase_id]
    by_key = {}
    for e in atts:
        by_key.setdefault(e.get("hypothesis_key", "?"), []).append(e)
    warns = []
    for key, lst in by_key.items():
        lst = sorted(lst, key=lambda e: (_seq(e), e.get("ts", "")))
        if len(lst) >= 2 and all(not x.get("new_evidence") for x in lst[-2:]):
            warns.append(f"假设「{key}」已记录 {len(lst)} 次、最近两次无新证据——停下换路线或出决策卡（EFF-04）")
    return warns
def active_block(ledger, phase_id):
    rows = sorted((e for e in ledger if e.get("kind") == "attempt"
                   and e.get("phase_id") == phase_id), key=_seq)
    for event in reversed(rows):
        if event.get("blocked"):
            return event
        if event.get("new_evidence"):
            return None
    return None
def phase_epoch(contract, ledger, phase_id):
    """Return the physical-evidence epoch for a phase.

    A new attempt is enough to invalidate a previous machine receipt: the
    product must be probed again after the new observation.  Manifest
    artifacts use artifact_phase_epoch() instead, because an attempt does
    not by itself change an already-bound candidate or its recorded facts.
    """
    order = {p["id"]: i for i, p in enumerate(contract.get("phases", []))}
    idx = order.get(phase_id, -1)
    return max((_seq(e) for e in ledger if (
        (e.get("kind") == "reopen"
         and order.get(e.get("from_phase"), len(order)) <= idx)
        or (e.get("kind") == "attempt"
            and order.get(e.get("phase_id"), len(order)) <= idx)
    )), default=0)


def artifact_phase_epoch(contract, ledger, phase_id):
    """Return the manifest-artifact epoch for a phase.

    Attempts invalidate confirmations and physical receipts, but they do
    not erase unchanged access/function-map/test facts.  Requiring those
    facts to be re-recorded after every investigative attempt makes
    --reconfirm unusable without adding evidence, while candidate and
    contract bindings already provide the relevant invalidation.
    """
    order = {p["id"]: i for i, p in enumerate(contract.get("phases", []))}
    idx = order.get(phase_id, -1)
    return max((_seq(e) for e in ledger if (
        e.get("kind") == "reopen"
        and order.get(e.get("from_phase"), len(order)) <= idx
    )), default=0)

def _candidate_live(product, current):
    if not current:
        return "none", None
    files = current.get("files")
    if isinstance(files, list):
        sources = current.get("sources")
        if isinstance(sources, list) and sources:
            if not all(isinstance(s, dict) and s.get("path") for s in sources):
                return "mismatch", None
            try:
                actual, _ = _scan_candidate_sources(product, [s.get("path", "") for s in sources])
            except FileNotFoundError:
                return "missing", None
            except ValueError as e:
                if "TEMP" in str(e):
                    return "temp", None
                return "mismatch", None
            except OSError:
                return "mismatch", None
            if any(_in_product_temp(product, Path(product) / item.get("path", ""))
                   for item in actual):
                return "temp", None
            disk = _candidate_manifest_sha(actual)
            return ("ok" if disk == current.get("sha256", "") else "mismatch"), disk
        actual = []
        product = Path(product).resolve()
        for item in files:
            if not isinstance(item, dict) or not item.get("path"):
                return "mismatch", None
            p = product / item["path"]
            if p.is_symlink():
                return "mismatch", None
            try:
                rp = p.resolve()
                rp.relative_to(product)
            except (OSError, ValueError):
                return "mismatch", None
            if _in_product_temp(product, rp):
                return "temp", None
            if not rp.is_file():
                return "missing", None
            actual.append({"path": item["path"], "sha256": sha256_file(rp), "size": rp.stat().st_size})
        disk = _candidate_manifest_sha(actual)
        return ("ok" if disk == current.get("sha256", "") else "mismatch"), disk
    p = Path(current.get("path", ""))
    try:
        p = _inside_no_links(product, p)
    except (ValueError, OSError):
        return "mismatch", None
    if _in_product_temp(product, p):
        return "temp", None
    if not p.is_file():
        return "missing", None
    disk = sha256_file(p)
    return ("ok" if disk == current.get("sha256", "") else "mismatch"), disk
def candidate_pointers(ledger):
    cands = sorted([e for e in ledger if e.get("kind") == "candidate"], key=_seq)
    current = cands[-1] if cands else None
    blessed = [e for e in cands if e.get("bless")]
    last_good = blessed[-1] if blessed else None
    return current, last_good
def _read_registry_status():
    if not REGISTRY.exists():
        return {"products": []}, False
    try:
        data = json.loads(REGISTRY.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        return {"products": []}, True
    if not isinstance(data, dict):
        return {"products": []}, True
    if "products" in data and not isinstance(data.get("products"), list):
        return {"products": []}, True
    return data, False
def _identity_check(product, contract):
    issues = []
    current = str(Path(product).resolve())
    root = contract.get("root")
    if not root:
        issues.append(("block",
            "合同没有登记路径，身份无法核对——先 `state rebind` 写回当前产品根。"))
    elif root != current:
        issues.append(("block",
            f"登记路径与当前路径不一致——登记：{root}；当前：{current}。"
            "很可能是副本 / 搬了位置 / 指错了项目。确认无误就跑 `state rebind` 更新，否则别在这动手。"))
    reg, reg_corrupt = _read_registry_status()
    if reg_corrupt:
        issues.append(("block",
            "项目登记表（registry.json）损坏，身份无法核对——不在身份不明时动手。"
            "先修好它，或删掉这个坏文件后再 `state rebind`（坏文件还在时 rebind/init 也会拒，避免把别人的登记盖成空表）。"))
        return issues
    match = next((r for r in reg.get("products", []) if r.get("path") == current), None)
    if match is None:
        issues.append(("warn", "当前路径不在项目登记表里（没 init 过？或登记表没同步）。"))
    elif match.get("product_id") != contract.get("product_id"):
        issues.append(("block",
            f"身份冲突——登记表说这路径是「{match.get('product_id')}」，合同却写「{contract.get('product_id')}」，先查清再动手。"))
    uuidv = contract.get("product_uuid")
    if uuidv:
        others = [r.get("path") for r in reg.get("products", [])
                  if r.get("product_uuid") == uuidv and r.get("path") != current
                  and (Path(r.get("path", "")) / ".hub" / "contract.json").exists()]
        if others:
            issues.append(("warn",
                "同一产品还有别的活副本在：" + "、".join(others)
                + "——两处各记各的账会串候选/串版本，建议只在一处工作。"))
    return issues
def _guard_identity(product, contract):
    issues = _identity_check(product, contract)
    for lvl, msg in issues:
        if lvl == "warn":
            print(f"  ⚠ {msg}")
    blocks = [m for lvl, m in issues if lvl == "block"]
    if blocks:
        print("拒绝：项目身份对不上，不在错的项目/副本上动手——")
        for b in blocks:
            print(f"  ✋ {b}")
        sys.exit(3)
def _baseline_drift(contract, product):
    out = []
    for b in contract.get("upstream", {}).get("baseline", []):
        try:
            fp = _inside_no_links(product, b["path"])
        except (ValueError, OSError):
            out.append(f"不安全路径 {b['path']}")
            continue
        if not fp.exists():
            out.append(f"缺失 {b['path']}")
        elif sha256_file(fp) != b["sha256"]:
            out.append(f"已改动 {b['path']}")
    return out
def is_legacy_four_exe(contract):
    ids = [p.get("id") for p in (contract.get("phases") or [])]
    if "2-license" not in ids or "3-ship" not in ids or "2-boundary" in ids:
        return False
    try:
        i = ids.index("1-access")
    except ValueError:
        return False
    return i + 1 < len(ids) and ids[i + 1] == "2-license"
def legacy_four_void_phase(contract, phase_id):
    if not phase_id or phase_id not in ("2-license", "3-ship"):
        return False
    if is_legacy_four_exe(contract):
        return True
    ids = [p.get("id") for p in (contract.get("phases") or [])]
    return "2-boundary" in ids and phase_id in ids
