# -*- coding: utf-8 -*-
"""原创答句、两段账、模块表复验、跨平台份数、制品缺件。"""
import ctypes
from ctypes import wintypes
import json
import os
import re
import subprocess
import sys
import time
import unicodedata
from pathlib import Path
from hub_io import (
    KIND_TO_KEY, ARTIFACT_REQUIRED_FIELDS, CANDIDATE_BOUND_ARTIFACTS,
    PRODUCT_EVIDENCE, SKELETON_FIELDS,
    _inside_no_links, _in_product_temp, _validate_manifest, read_json,
)
from hub_flow import (
    contract_fingerprint, candidate_pointers, _candidate_live, artifact_phase_epoch,
    _mission_complete, physical_checks, phase_physical_checks, physical_receipt_missing, _baseline_drift,
    derive,
)
from hub_wording import (
    _fake_text, _unnegated_hit, _immediate_neg, _LAUNCHER_TAINT, _TRANSPORT,
    _later_use_empty, _later_use_ok, _unwrap_later, _phase_needs_later_use, _tokens,
    _later_unobserved, _later_placeholder, _WRAP, _compact_ws,
    _looks_valid_hedge, _LOOKS_WS, _LOOKS_FILL, _LOOKS_FILL_WORDS,
    _eat_as_customer_update, _UPDATE_COVER_OK, _UPDATE_OFFICIAL_OK,
    _explicit_skip, _phrase_hit, _plat_zip_hit, _UPDATE_HARD, _FAKE_COVER,
    _hard_hit, _taint_hit,
)
def _gate_unobserved(value):
    if _later_placeholder(value):
        return True
    return _later_unobserved(value)
def _substantive(value):
    return isinstance(value, str) and bool(value.strip())
def _no_launcher(entry, fields):
    parts = [str(entry.get(f, "")).lower() for f in fields]
    blob = " ".join(parts)
    if any(t in blob for t in _LAUNCHER_TAINT):
        return False
    return not any(t in _compact_ws(p) for p in parts for t in _LAUNCHER_TAINT)
def _access_ok(entry):
    req = ARTIFACT_REQUIRED_FIELDS["access"]
    if not all(_substantive(entry.get(f)) for f in req):
        return False
    if any(_fake_text(entry.get(f)) for f in req
           if f not in ("evidence_level", "entry_gate", "action_gate")):
        return False
    if str(entry.get("evidence_level", "")).lower() not in PRODUCT_EVIDENCE:
        return False
    if not _no_launcher(entry, ("method", "outcome", "evidence", "direct_launch", "entry_gate", "action_gate")):
        return False
    if not _later_use_ok(entry.get("entry_gate"), 4) or not _later_use_ok(entry.get("action_gate"), 4):
        return False
    entry_txt = _unwrap_later(entry.get("entry_gate"))
    action_txt = _unwrap_later(entry.get("action_gate"))
    if "".join(entry_txt.split()) == "".join(action_txt.split()):
        return False
    return not _gate_unobserved(entry.get("action_gate")) and not _gate_unobserved(entry.get("entry_gate"))
def _artifact_on_disk(product, artifact):
    if _fake_text(artifact):
        return False
    try:
        p = _inside_no_links(product, str(artifact).strip())
    except (ValueError, OSError):
        return False
    if _in_product_temp(product, p):
        return False
    return p.is_file() and p.stat().st_size >= 256
def _packed_release_sha(manifest, fp, epoch, product, phase_id="5-pack"):
    latest = None
    for entry in manifest.get("build", []) or []:
        if (isinstance(entry, dict) and entry.get("fp") == fp
                and entry.get("phase_id") == phase_id and entry.get("epoch", 0) == epoch):
            latest = entry
    if latest is None:
        return ""
    req = ARTIFACT_REQUIRED_FIELDS["build"]
    sha = str(latest.get("candidate_sha") or "")
    if (_fake_text(latest.get("install_receipt")) or _fake_text(sha) or not sha
            or not all(_substantive(latest.get(f)) for f in req)
            or product is None or not _artifact_on_disk(product, latest.get("artifact"))):
        return ""
    return sha
def _rva_only_sites(value):
    """下次重找补丁不能只写这一版地址。"""
    if not isinstance(value, str) or _fake_text(value):
        return True
    s = value.strip()
    low = s.lower()
    has_hex = "0x" in low or "rva" in low
    has_script = any(k in s for k in ("跑一遍", "旧脚本", "直接跑脚本", "上次那个脚本"))
    has_how = any(k in s for k in ("原文", "窗口", "按钮", "命令", "cdk", "请输入", "激活"))
    if has_script:
        return True
    if has_hex and not has_how:
        return True
    compact = re.sub(r"[\s,;]+", "", low)
    if re.fullmatch(r"(0x)?[0-9a-f]+", compact):
        return True
    return False


_COPY_ANSWER = (
    "照抄", "直接按清单", "按清单打", "按清单直接", "不用核对", "不用分析",
    "不用判断", "全部照搬", "抄答案", "清单全都能用", "直接用清单", "按图直接打",
)
_KEEP_VERDICT = ("还能认", "还能搬", "仍能认", "仍是它", "还能用", "再认", "还能按", "还能迁")
_NEW_VERDICT = ("新门", "认不出", "搜不到", "找不到", "大变")
_UPDATE_ANALYZE_PHASES = {
    "exe-rebuild": ("6-update",),
    "desktop-product": ("6-update",),
    "cli-tool": ("6-update",),
    "web-service": ("6-release",),
    "source-takeover": ("6-release",),
    "protocol-automation": ("6-test-regression",),
}
_DATA_MIG_PHASES = {
    "web-service": ("5-data",),
    "desktop-product": ("6-update",),
    "cli-tool": ("6-update",),
}
_LICENSE_BASIC_PHASES = {
    "exe-rebuild": ("4-license", "2-license"),
    "desktop-product": ("3-build", "4-package"),
    "cli-tool": ("3-build", "4-package"),
    "web-service": ("3-build", "4-staging"),
    "source-takeover": ("5-build",),
    "protocol-automation": ("7-handoff",),
}


def _copy_answer_text(value):
    """把清单当答案照抄、声明不用核对。"""
    if not isinstance(value, str) or _fake_text(value):
        return True
    return any(k in value for k in _COPY_ANSWER)


def _no_row_verdict(value):
    """还没同时判断「还能认」和「新门」两边。"""
    if not isinstance(value, str) or _fake_text(value):
        return True
    has_keep = any(k in value for k in _KEEP_VERDICT)
    has_new = any(k in value for k in _NEW_VERDICT)
    return not (has_keep and has_new)


def _update_analyze_lines(product_type, phase_id):
    if phase_id not in _UPDATE_ANALYZE_PHASES.get(product_type, ()):
        return []
    return [
        "跟上新版本：先对照上一份冻本和功能表/改动图，逐条判断还能认还是新门。",
        "变动少就按清单再核对；授权或架构位置大变就当新门重做，不许照抄清单。",
    ]


def _install_lines(product_type, phase_id):
    if phase_id not in _INSTALL_PHASES.get(product_type, ()):
        return []
    return [
        "装上/预发/发布候选必须还是冻住的那一版功能表，不是开发机上后来改过的。",
    ]


def _handoff_lines(product_type, phase_id):
    if phase_id not in _HANDOFF_PHASES.get(product_type, ()):
        return []
    return [
        "交给下一个人：冻本和功能表必须还对得上现在这一版，不能只交一个包。",
    ]


def _data_mig_lines(product_type, phase_id):
    if phase_id not in _DATA_MIG_PHASES.get(product_type, ()):
        return []
    return [
        "数据迁移：对照上一份数据怎么放，逐条判断还能迁还是新门。",
        "不能只换脚本交差。找不到旧字段就当新门，不许照抄旧迁移。",
    ]


def _license_basic_lines(product_type, phase_id):
    if phase_id not in _LICENSE_BASIC_PHASES.get(product_type, ()):
        return []
    if product_type == "cli-tool":
        return [
            "三种基础都要真跑：有效才放行主命令；无效不放行；用到一半过期要停主命令。",
            "还要第四种：卡还没到期，但这台被挤掉或 DEVICE_NOT_BOUND / 解绑后停，旧电脑须再 verify，下一次验证内停主命令。",
            "两套钟不准改混：到期靠 expires_at 本地关，不要改成到期也必须再问才关。挤机必须再 verify，下一次验证内停。expiry 是卡还剩多久，禁止把验证间隔/cache_until/next_verify_at/20 秒/60 秒交给核心或标题栏。测试/验收间隔默认 60 秒，不要 20 秒硬刷。先只有一台等过间隔还开着，再上第二台挤机。测试只用 ceshi1、新发卡，先打测试站。只有一台时超过验证间隔还在，没人挤不会自己关。RATE_LIMITED 不是停机。开着还要周期性验证，只 activate 不算。宽限不是多台同时登录。",
            "不要为过关造页、造窗。购买/联系跟下游原文；更新带版本号问平台，有新版才打开网盘。只写「过期」不算第三种。",
        ]
    if product_type == "web-service":
        return [
            "三种基础都要真跑：有效才提供服务；无效不提供；用到一半过期要停服务。",
            "还要第四种：卡还没到期，但这台被挤掉或 DEVICE_NOT_BOUND / 解绑后停，旧电脑须再 verify，下一次验证内停服务，不要关软件。",
            "两套钟不准改混：到期靠 expires_at 本地关，不要改成到期也必须再问才关。挤机必须再 verify，下一次验证内停。expiry 是卡还剩多久，禁止把验证间隔/cache_until/next_verify_at/20 秒/60 秒交给核心或标题栏。测试/验收间隔默认 60 秒，不要 20 秒硬刷。先只有一台等过间隔还开着，再上第二台挤机。测试只用 ceshi1、新发卡，先打测试站。只有一台时超过验证间隔还在，没人挤不会自己关。RATE_LIMITED 不是停机。开着还要周期性验证，只 activate 不算。宽限不是多台同时登录。",
            "走站点收费门。购买/联系跟下游原文；更新带版本号问平台，有新版才打开网盘。只写「过期」不算第三种。",
        ]
    if product_type == "desktop-product":
        return [
            "三种基础都要真跑：有效才放行程序；无效不放行；用到一半过期要关掉程序。",
            "还要第四种：卡还没到期，但这台被挤掉或 DEVICE_NOT_BOUND / 解绑后停，旧电脑须再 verify，下一次验证内停主程序。",
            "两套钟不准改混：到期靠 expires_at 本地关，不要改成到期也必须再问才关。挤机必须再 verify，下一次验证内停。expiry 是卡还剩多久，禁止把验证间隔/cache_until/next_verify_at/20 秒/60 秒交给核心或标题栏。测试/验收间隔默认 60 秒，不要 20 秒硬刷。先只有一台等过间隔还开着，再上第二台挤机。测试只用 ceshi1、新发卡，先打测试站。只有一台时超过验证间隔还在，没人挤不会自己关。RATE_LIMITED 不是停机。开着还要周期性验证，只 activate 不算。宽限不是多台同时登录。",
            "若接了，先把授权页改成这个产品的样子。购买/联系跟下游原文；更新带版本号问平台，有新版才打开网盘。藏页不能顶第一种。",
        ]
    if product_type == "source-takeover":
        return [
            "三种基础都要真跑，按这个产品的形态：有效才放行后面的程序/服务；无效不放行；用到一半过期则停掉。",
            "还要第四种：卡还没到期，但这台被挤掉或 DEVICE_NOT_BOUND / 解绑后停，旧电脑须再 verify，下一次验证内停。网站停服务，不要关软件。",
            "两套钟不准改混：到期靠 expires_at 本地关，不要改成到期也必须再问才关。挤机必须再 verify，下一次验证内停。expiry 是卡还剩多久，禁止把验证间隔/cache_until/next_verify_at/20 秒/60 秒交给核心或标题栏。测试/验收间隔默认 60 秒，不要 20 秒硬刷。先只有一台等过间隔还开着，再上第二台挤机。测试只用 ceshi1、新发卡，先打测试站。只有一台时超过验证间隔还在，没人挤不会自己关。RATE_LIMITED 不是停机。开着还要周期性验证，只 activate 不算。宽限不是多台同时登录。",
            "若接了：有窗才改授权页再进主页面；没窗不要造窗。更新带版本号问平台，有新版才打开网盘。",
        ]
    return [
        "三种基础都要真跑：有效才开核心；无效不开；用到一半过期要关核心并关掉授权页。",
        "还要第四种：卡还没到期，但这台被挤掉或 DEVICE_NOT_BOUND / 解绑后停，旧电脑须再 verify，下一次验证内关核心。",
        "两套钟不准改混：到期靠 expires_at 本地关，不要改成到期也必须再问才关。挤机必须再 verify，下一次验证内停。expiry 是卡还剩多久，禁止把验证间隔/cache_until/next_verify_at/20 秒/60 秒交给核心或标题栏。测试/验收间隔默认 60 秒，不要 20 秒硬刷。先只有一台等过间隔还开着，再上第二台挤机。测试只用 ceshi1、新发卡，先打测试站。只有一台时超过验证间隔还在，没人挤不会自己关。RATE_LIMITED 不是停机。开着还要周期性验证，只 activate 不算。宽限不是多台同时登录。",
        "须走启动器。只写「过期」不算第三种。藏页不能顶第一种。",
    ]


_DOSSIER_RVA_FIELDS = (
    "auth_chain", "patch_sites", "own_page", "updater_kill",
    "pack_recipe", "entry_gate", "action_gate", "data_roots", "reuse",
    "ours_changed", "upstream_changed", "still_portable",
)
_DOSSIER_THREE = ("ours_changed", "upstream_changed", "still_portable")


def _follow_ok(entry):
    """原创/接手/二开共用：跟上新版本必须判断还能认和新门。"""
    if not isinstance(entry, dict):
        return False
    if any(_fake_text(entry.get(f)) for f in _DOSSIER_THREE):
        return False
    three = [str(entry.get(f) or "").strip() for f in _DOSSIER_THREE]
    if len(set(three)) < 3:
        return False
    if any(_copy_answer_text(entry.get(f)) for f in _DOSSIER_THREE):
        return False
    if _no_row_verdict(entry.get("still_portable")):
        return False
    if any(_rva_only_sites(entry.get(f)) for f in _DOSSIER_THREE):
        return False
    return True


def _dossier_ok(entry):
    req = ARTIFACT_REQUIRED_FIELDS["dossier"]
    if any(_fake_text(entry.get(f)) for f in req if f != "replay_steps"):
        return False
    steps = entry.get("replay_steps")
    if not (isinstance(steps, list) and steps and all(not _fake_text(s) for s in steps)):
        return False
    if any(_rva_only_sites(s) for s in steps):
        return False
    if any(_rva_only_sites(entry.get(field)) for field in _DOSSIER_RVA_FIELDS):
        return False
    if not _follow_ok(entry):
        return False
    return str(entry.get("transport", "")).strip().lower() in _TRANSPORT


_ORIG_COVER_TYPES = frozenset({
    "desktop-product", "cli-tool", "web-service", "source-takeover",
})


def _cover_ok(entry, product_type=None):
    """客户路径。二开：官方更新且（覆盖或本项 SKIP）。原创：必须覆盖做成，SKIP 不能顶。"""
    if not isinstance(entry, dict):
        return False
    req = ARTIFACT_REQUIRED_FIELDS.get("cover") or ("outcome", "evidence")
    if any(_fake_text(entry.get(f)) for f in req):
        return False
    if not all(_substantive(entry.get(f)) for f in req):
        return False
    blob = " ".join(str(entry.get(f) or "") for f in req)
    if _eat_as_customer_update(blob):
        return False
    if _rva_only_sites(blob):
        return False
    if (_plat_zip_hit(blob) or _hard_hit(blob, _UPDATE_HARD)
            or _taint_hit(blob, _UPDATE_HARD)):
        return False
    if _phrase_hit(blob, _FAKE_COVER) or _taint_hit(blob, _FAKE_COVER):
        return False
    official = _phrase_hit(blob, _UPDATE_OFFICIAL_OK)
    overlay = _phrase_hit(blob, _UPDATE_COVER_OK)
    skipped = _explicit_skip(blob) or _phrase_hit(blob, ("本项 SKIP", "本项SKIP"))
    if product_type in _ORIG_COVER_TYPES:
        return bool(overlay and not skipped)
    if product_type == "exe-rebuild":
        return bool(official and (overlay or skipped))
    return False


def _cover_reject_msg(product_type=None):
    if product_type in _ORIG_COVER_TYPES:
        return (
            "客户路径不合格：须覆盖做成（覆盖安装/盖成同一软件/已装软件里点更新/"
            "已装旧命令/生产租户）。本项 SKIP、吃新上游、旧脚本、只写地址、"
            "平台能下 zip、另装文件夹不能顶客户路径。"
        )
    return (
        "客户路径不合格：覆盖做成须同时有覆盖安装/盖成同一软件和官方更新改道或进三条通道；"
        "或本项 SKIP 加官方更新。吃新上游、旧脚本、只写地址、平台能下 zip、另装文件夹不能顶客户路径。"
    )


def _parse_change_map(product):
    """None = 没有文件。否则 (数据行, 怎么找到列号)。"""
    path = Path(product) / "CHANGES.md"
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    how_idx = None
    rows = []
    for line in text.splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not cells or not cells[0]:
            continue
        if set("".join(cells)) <= set("-: "):
            continue
        header = cells[0] in ("编号", "改动名") or (
            how_idx is None and any(c.startswith("怎么找到") and "曾经" not in c for c in cells))
        if header:
            for i, cell in enumerate(cells):
                if cell.startswith("怎么找到") and "曾经" not in cell:
                    how_idx = i
                    break
            continue
        rows.append(cells)
    if how_idx is None:
        how_idx = 4 if (rows and len(rows[0]) > 4) else 3
    return rows, how_idx


def _how_unusable(how):
    if not how or how in ("怎么找到（方法）", "怎么找到", "怎么找到（当前）"):
        return True
    return _rva_only_sites(how)


def _change_map_thin(product):
    """改动图有表但某一刀没写怎么找到。文件不存在不算（避免旧夹具全炸）。"""
    parsed = _parse_change_map(product)
    if parsed is None:
        return None
    rows, how_idx = parsed
    if not rows:
        return None
    for cells in rows:
        how = cells[how_idx] if len(cells) > how_idx else ""
        if _how_unusable(how):
            return "改动图有行但没写怎么找到（下一版会从零找门）"
    return None


def _change_map_gap(product):
    """二开打包/更新闸。None = 过闸。没有图、没有行、没写找法、只写地址/旧脚本都停。"""
    parsed = _parse_change_map(product)
    if parsed is None:
        return "没有改动图（每一刀怎么找到没记下；打包/更新停点不得已就绪）"
    rows, how_idx = parsed
    if not rows:
        return "改动图没有真实行（打包/更新停点不得已就绪）"
    for cells in rows:
        how = cells[how_idx] if len(cells) > how_idx else ""
        if not how or how in ("怎么找到（方法）", "怎么找到", "怎么找到（当前）"):
            return "改动图有行但没写怎么找到（下一版会从零找门）"
        if _rva_only_sites(how):
            return "改动图怎么找到只写了地址或旧脚本，下一版认不出"
    return None


def _gate_needle(value):
    text = _unwrap_later(value) if value else ""
    text = unicodedata.normalize("NFKC", str(text)).strip()
    for mark in "「」『』“”‘’\"'":
        text = text.replace(mark, "")
    return text


def _change_map_misses_gates(product, entry, action, need_action=False):
    """图上的怎么找到对不上刚记下的入口/动作原文。None = 对得上。

    核心可用默认只核入口（找门时动作门文案会变）。更新档案 need_action=True 连动作一起核。
    """
    parsed = _parse_change_map(product)
    if parsed is None:
        return "没有改动图（每一刀怎么找到没记下；核心可用停点不得已就绪）"
    rows, how_idx = parsed
    parts = []
    for cells in rows:
        if len(cells) > how_idx:
            parts.append(cells[how_idx])
        if len(cells) > how_idx + 1:
            parts.append(cells[how_idx + 1])
    hay = unicodedata.normalize("NFKC", " ".join(parts))
    for mark in "「」『』“”‘’\"'":
        hay = hay.replace(mark, "")
    needle = _gate_needle(entry)
    if len(needle) >= 2 and needle not in hay:
        return "改动图怎么找到对不上刚记下的入口原文"
    if need_action:
        needle = _gate_needle(action)
        if len(needle) >= 2 and needle not in hay:
            return "改动图怎么找到对不上刚记下的动作原文"
    return None


def _latest_match(manifest, key, fp, cand_sha, phase_id, epoch):
    latest = None
    for entry in manifest.get(key, []) or []:
        if not isinstance(entry, dict):
            continue
        if entry.get("fp") != fp:
            continue
        if cand_sha is not None and entry.get("cand_sha") != cand_sha:
            continue
        if phase_id is not None and entry.get("phase_id") != phase_id:
            continue
        if entry.get("epoch", 0) != epoch:
            continue
        latest = entry
    return latest
def _artifact_current(manifest, key, fp, cand_sha, phase_id=None, epoch=0, product=None,
                      product_type=None):
    required = ARTIFACT_REQUIRED_FIELDS.get(key)
    latest = _latest_match(manifest, key, fp, cand_sha, phase_id, epoch)
    if latest is None:
        return False
    entry = latest
    if key == "access":
        return _access_ok(entry)
    if key == "anchors":
        return _later_use_ok(entry.get("how"))
    if key == "function_map":
        bounds = entry.get("authorization_boundaries")
        fns = entry.get("functions")
        return bool(isinstance(fns, list) and fns
                    and all(_substantive(x) and not _fake_text(x) for x in fns)
                    and isinstance(bounds, dict)
                    and all(k in bounds for k in ("entry", "action", "public", "prereq"))
                    and all(_substantive(bounds.get(k)) and not _fake_text(bounds.get(k))
                            for k in ("entry", "action", "public", "prereq")))
    if key in ("tests", "license") and required:
        if any(_fake_text(entry.get(f)) for f in required if f != "evidence_level"):
            return False
        lvl_ok = str(entry.get("evidence_level", "")).lower() in PRODUCT_EVIDENCE
        return bool(lvl_ok and all(_substantive(entry.get(f)) for f in required)
                    and _no_launcher(entry, required))
    if key == "ui":
        mapping = entry.get("mapping")
        return not (_fake_text(entry.get("outcome")) or not _substantive(entry.get("outcome"))
                    or not isinstance(mapping, list) or not mapping
                    or any(_fake_text(x) or not _substantive(x) for x in mapping))
    if key == "build":
        if _fake_text(entry.get("install_receipt")):
            return False
        if cand_sha and str(entry.get("candidate_sha", "")) != cand_sha:
            return False
        if not (required and all(_substantive(entry.get(f)) for f in required)):
            return False
        return product is not None and _artifact_on_disk(product, entry.get("artifact"))
    if key == "dossier":
        return _dossier_ok(entry)
    if key == "follow":
        return _follow_ok(entry)
    if key == "cover":
        return _cover_ok(entry, product_type=product_type)
    if required:
        if any(_fake_text(entry.get(f)) for f in required):
            return False
        return all(_substantive(entry.get(f)) for f in required)
    return any(k not in SKELETON_FIELDS and _substantive(v) for k, v in entry.items())
_PACK_ASK_STOPS = frozenset({
    "安装包确认", "预发环境冒烟确认", "分发包与跨平台确认", "发布候选确认",
    "上线回滚演练确认", "更新回滚演练确认", "发布回滚演练确认",
    "交付验收确认",
})
_ORIG_ASK_HOLD = {
    "desktop-product": "3-build",
    "web-service": "3-build",
    "cli-tool": "3-build",
    "source-takeover": "5-build",
    "protocol-automation": "5-automate",
}
_IMPL_STOPS = frozenset({
    "核心功能实现确认", "核心接口与页面实现确认", "核心命令实现确认", "改造实现确认",
})
_ASK_NEGS = (
    "尚未接自己的授权",
    "还未接自己的授权",
    "还没当面问接自己的授权",
    "还没问接自己的授权",
    "尚未问接自己的授权",
    "没有问接自己的授权",
    "未问接自己的授权",
    "没问接自己的授权",
    "不问接自己的授权",
    "还没决定接自己的授权",
    "尚未决定接自己的授权",
    "没有决定接自己的授权",
    "未决定接自己的授权",
    "以后再说接自己的授权",
    "以后再接自己的授权",
    "以后接自己的授权",
    "是否接自己的授权",
    "未当面写下接自己的授权",
    "还没接自己的授权",
    "没有接自己的授权",
    "不要接自己的授权",
    "不必接自己的授权",
    "不用接自己的授权",
    "无需接自己的授权",
    "不需要接自己的授权",
    "不会接自己的授权",
    "不接自己的授权",
    "未接自己的授权",
    "没接自己的授权",
    "拒绝接自己的授权",
    "禁止接自己的授权",
)
_ASK_TAIL = "接自己的授权"
_ASK_NEG_PREFIXES = tuple(n[:-len(_ASK_TAIL)] for n in _ASK_NEGS if n.endswith(_ASK_TAIL))
_ASK_QUOTES = "「」『』\"'\u201c\u201d"
_ASK_GAPS = "、：:。，,；;.．"
_ASK_WS = frozenset(" \t\r\n\u3000\xa0\u200b")
_XIAN_GAPS = _ASK_WS | frozenset(_ASK_GAPS)
_SKIP_PHRASE = "这场不接"
_SKIP_Q = set("吗吧呢嘛么?？")
_SKIP_PARTICLE = set("了啊")
_SKIP_STOP = set(_ASK_GAPS) | set("!！")
_SKIP_JSON_TAIL = set("},")
_SKIP_WRITE_NEGS = ("还没", "尚未", "没有", "没", "未")
def _skip_write_neg(s, j):
    if j >= 2 and s[j - 2:j] in ("写下", "写过"):
        k = j - 2
    elif j >= 1 and s[j - 1] in ("写", "问"):
        k = j - 1
    else:
        return False
    if k >= 2 and s[k - 2:k] == "当面":
        k -= 2
    return any(k >= len(p) and s[k - len(p):k] == p for p in _SKIP_WRITE_NEGS)
def _after_ask_fill(s, n):
    k = n
    while k < len(s) and s[k] in _WRAP:
        k += 1
    while k < len(s) and s[k] in _SKIP_PARTICLE:
        k += 1
    while k < len(s) and s[k] in _WRAP:
        k += 1
    while k < len(s) and s[k] in _ASK_WS:
        k += 1
    return k
def _q_after_stop(s, k):
    if k >= len(s) or not (s[k] in _SKIP_STOP or s[k] in _SKIP_JSON_TAIL):
        return False
    j = k + 1
    while j < len(s) and (s[j] in _WRAP or s[j] in _ASK_WS
                          or s[j] in _SKIP_STOP or s[j] in _SKIP_JSON_TAIL):
        j += 1
    return j < len(s) and s[j] in _SKIP_Q
def _q_before_stop(s, k):
    j = k
    while j < len(s) and s[j] not in _SKIP_STOP and s[j] not in _SKIP_JSON_TAIL:
        if s[j] in _SKIP_Q:
            return True
        j += 1
    return False
def _skip_boundary(s, n):
    if n >= len(s):
        return True
    k = _after_ask_fill(s, n)
    if k < len(s) and s[k] in _SKIP_Q:
        return False
    if k >= len(s):
        return True
    if _q_after_stop(s, k):
        return False
    return s[k] in _SKIP_STOP or s[k] in _SKIP_JSON_TAIL
def _strip_ask_negs(blob):
    cleaned = str(blob or "")
    for ch in _ASK_QUOTES + _ASK_GAPS:
        cleaned = cleaned.replace(ch, "")
    cleaned = re.sub(r"\s+", "", cleaned)
    for neg in _ASK_NEGS:
        cleaned = cleaned.replace(neg, "")
    return cleaned
def _compact_ask(blob, strip_quotes=False):
    s = re.sub(r"\s+", "", str(blob or ""))
    if strip_quotes:
        for ch in _ASK_QUOTES:
            s = s.replace(ch, "")
    return s
def _unnegated_ask(s, phrase, prefixes=(), boundary_ok=None, prefix_fn=None):
    start = 0
    step = len(phrase)
    while True:
        i = s.find(phrase, start)
        if i < 0:
            return False
        j = i
        while j > 0 and s[j - 1] in _WRAP:
            j -= 1
        j_gap = j
        while j > 0 and s[j - 1] in _ASK_GAPS:
            j -= 1
        while j > 0 and s[j - 1] in _WRAP:
            j -= 1
        if (j >= 1 and s[j - 1] in "非无") or _immediate_neg(s, j, True):
            start = i + step
            continue
        if prefix_fn and prefix_fn(s, j_gap):
            start = i + step
            continue
        if any(p and j >= len(p) and s[j - len(p):j] == p for p in prefixes):
            start = i + step
            continue
        if boundary_ok is not None:
            n = i + step
            if callable(boundary_ok):
                if not boundary_ok(s, n):
                    start = i + step
                    continue
            elif n < len(s) and s[n] not in boundary_ok:
                start = i + step
                continue
        return True
def _ask_connect_ok(s, n):
    k = _after_ask_fill(s, n)
    if k < len(s) and s[k] in _SKIP_Q:
        return False
    if _q_after_stop(s, k):
        return False
    if _q_before_stop(s, k):
        return False
    return True
def _connect_ask_in(blob):
    return _unnegated_ask(
        _compact_ask(_fold_ask_breaks(blob), True), _ASK_TAIL, _ASK_NEG_PREFIXES,
        boundary_ok=_ask_connect_ok)
_ASK_NOT_YET = (
    "还没问", "尚未问", "没有问", "未问", "没问", "不问",
    "还没当面问", "未当面问", "尚未当面问",
)
def _ask_not_yet(blob):
    s = _compact_ask(blob, True)
    return any(_unnegated_hit(s, p, True) for p in _ASK_NOT_YET)
def _fold_ask_breaks(s):
    out = str(s or "")
    for a, b in (("\r\n", "。"), ("\n", "。"), ("\r", "。"),
                 ("\t", "。"), ("\v", "。"), ("\f", "。"), ("\b", "。"),
                 ("\x00", "。")):
        out = out.replace(a, b)
    return out
def _skip_ask_in(blob):
    s = _fold_ask_breaks(blob)
    s = _compact_ask(s).replace("非这场不接", "").replace("无这场不接", "")
    return _unnegated_ask(s, _SKIP_PHRASE, boundary_ok=_skip_boundary, prefix_fn=_skip_write_neg)
def _ask_conflict(blob):
    return _skip_ask_in(blob) and _connect_ask_in(blob)
def _blob_has_pack_ask(blob):
    if _skip_ask_in(blob):
        return True
    return _connect_ask_in(blob)
def _ask_from(contract):
    hold = _ORIG_ASK_HOLD.get((contract or {}).get("type"))
    ids = [p.get("id") for p in (contract or {}).get("phases") or []]
    return set(ids[ids.index(hold):]) if hold in ids else (None if not hold else set())
def _ask_entry_blob(e):
    if not isinstance(e, dict):
        return ""
    vals = []
    for v in e.values():
        if isinstance(v, str):
            vals.append(_fold_ask_breaks(v))
    return json.dumps(vals, ensure_ascii=False)
def _two_step_blob(e):
    if not isinstance(e, dict):
        return str(e or "")
    vals = []
    for v in e.values():
        if isinstance(v, str):
            vals.append(_fold_ask_breaks(v))
    return "。".join(vals)
def _skip_wrap_fwd(s, j):
    while j < len(s):
        if s[j] == "\\" and j + 1 < len(s) and s[j + 1] in _WRAP:
            j += 2
            continue
        if s[j] in _WRAP:
            j += 1
            continue
        break
    return j
def _spec_arch_entries(manifest, key, asked=False, contract=None):
    items = [e for e in (manifest.get(key) or []) if isinstance(e, dict)]
    allow = _ask_from(contract) if asked else None
    if allow is None:
        return items
    return [e for e in items if e.get("phase_id") in allow]
def _spec_arch_blob(manifest, asked=False, contract=None):
    return json.dumps(_spec_arch_entries(manifest, "spec", asked, contract), ensure_ascii=False) + json.dumps(
        _spec_arch_entries(manifest, "arch", asked, contract), ensure_ascii=False)
def _kind_latest(manifest, key, asked=False, contract=None):
    items = _spec_arch_entries(manifest, key, asked, contract)
    return items[-1] if items else None
def _phase_rank(contract, phase_id):
    ids = [p.get("id") for p in (contract or {}).get("phases") or []]
    try:
        return ids.index(phase_id)
    except ValueError:
        return -1
def _latest_ask_blob(manifest, asked=False, contract=None):
    spec = _kind_latest(manifest, "spec", asked, contract)
    arch = _kind_latest(manifest, "arch", asked, contract)
    if spec and arch:
        spec_rank = _phase_rank(contract, spec.get("phase_id"))
        arch_rank = _phase_rank(contract, arch.get("phase_id"))
        if spec_rank > arch_rank:
            return _ask_entry_blob(spec)
        if arch_rank > spec_rank:
            return _ask_entry_blob(arch)
        return _ask_entry_blob(spec) + "。" + _ask_entry_blob(arch)
    if spec:
        return _ask_entry_blob(spec)
    if arch:
        return _ask_entry_blob(arch)
    return ""
def _latest_spec_arch_blob(manifest, asked=False, contract=None):
    parts = []
    for key in ("spec", "arch"):
        e = _kind_latest(manifest, key, asked, contract)
        if e:
            parts.append(json.dumps(e, ensure_ascii=False))
    return "".join(parts)
def _latest_ask_conflict(contract, manifest):
    return _ask_conflict(_latest_ask_blob(manifest, True, contract))
def _orig_asked(contract, manifest):
    if (contract or {}).get("type") not in _ORIG_ASK_HOLD:
        return True
    latest = _latest_ask_blob(manifest, True, contract)
    if _ask_conflict(latest) or _ask_not_yet(latest):
        return False
    return _blob_has_pack_ask(latest)
def _asked_own_license(manifest, contract):
    latest = _latest_ask_blob(manifest, True, contract)
    return bool(_connect_ask_in(latest) and not _skip_ask_in(latest))
def _xian_ce_mark(blob):
    s = str(blob or "")
    start = 0
    while True:
        i = s.find("先测", start)
        if i < 0:
            return False
        j = i + 2
        if j < len(s) and s[j] == "试":
            start = i + 2
            continue
        if _immediate_neg(s, _peel_xian_back(s, i), True):
            start = i + 2
            continue
        while j < len(s) and s[j] in _XIAN_GAPS:
            j += 1
        while True:
            while j < len(s) and s[j] in _XIAN_GAPS:
                j += 1
            nj = _skip_wrap_fwd(s, j)
            if nj != j:
                j = nj
                continue
            if s.startswith("一下", j):
                j += 2
            elif j < len(s) and s[j] in "了下":
                j += 1
            else:
                break
        j = _skip_wrap_fwd(s, j)
        rest = "".join(ch for ch in s[j:] if ch not in _XIAN_GAPS)
        if rest.startswith(("登录", "页面", "窗口", "升级", "回滚", "覆盖更新", "官方更新", "覆盖", "更新")):
            start = i + 2
            continue
        return True
def _pack_ask_phase_ids(contract):
    return {
        p.get("id") for p in (contract or {}).get("phases") or []
        if (p or {}).get("stop_point") in _PACK_ASK_STOPS
    }
def _latest_pack_ask_entry(manifest, key, allow):
    items = [e for e in (manifest.get(key) or []) if isinstance(e, dict)]
    if allow is not None:
        items = [e for e in items if e.get("phase_id") in allow]
    return items[-1] if items else None
def _peel_xian_back(s, i):
    k = i
    while k > 0:
        ch = s[k - 1]
        if ch in _WRAP or ch in _XIAN_GAPS:
            if k >= 2 and s[k - 2] == "\\" and ch in _WRAP:
                k -= 2
            else:
                k -= 1
            continue
        break
    return k
def _later_link_skip(s, i):
    k = _peel_xian_back(s, i)
    return k >= 3 and s[k - 3:k] == "以后再"
def _prod_linked(blob):
    s = str(blob or "")
    start = 0
    while True:
        i = s.find("连正式", start)
        if i < 0:
            return False
        if _later_link_skip(s, i) or _immediate_neg(s, _peel_xian_back(s, i), True):
            start = i + 3
            continue
        return True
def _connect_two_step_ok(manifest, phase=None, contract=None):
    twin = prod = False
    pid = (phase or {}).get("id")
    pack_ids = _pack_ask_phase_ids(contract)
    allow = pack_ids if pack_ids else _ask_from(contract)
    blobs = []
    for key in ("spec", "arch"):
        e = (_latest_pack_ask_entry(manifest, key, pack_ids)
             if pack_ids else _kind_latest(manifest, key, True, contract))
        if e:
            blobs.append(_two_step_blob(e))
    for e in manifest.get("tests") or []:
        if not isinstance(e, dict):
            continue
        epid = e.get("phase_id")
        if allow is not None:
            if epid not in allow:
                continue
        elif pid and epid != pid:
            continue
        blobs.append(_two_step_blob(e))
    for b in blobs:
        compact = _strip_ask_negs(b)
        for neg in ("非孪生", "无孪生", "非测试分身", "无测试分身"):
            compact = compact.replace(neg, "")
        marked = (_unnegated_hit(compact, "孪生", True)
                  or _unnegated_hit(compact, "测试分身", True)
                  or _xian_ce_mark(b))
        linked = _prod_linked(b)
        if marked and not linked:
            twin = True
        if linked:
            prod = True
    return twin and prod
def _pack_ask_gap(phase, contract, manifest):
    if (contract or {}).get("type") == "exe-rebuild":
        if (phase or {}).get("id") not in ("4-license", "5-pack", "6-update", "3-ship"):
            return None
        latest = _latest_ask_blob(manifest, True, contract)
        if _skip_ask_in(latest):
            return "二开没有「可以不接」，走授权页启动器；写成这场不接不能点这一格"
        return None
    if (phase or {}).get("id") in ("4-license", "5-pack", "2-license", "3-ship"):
        return None
    if (phase or {}).get("stop_point") not in _PACK_ASK_STOPS:
        return None
    latest = _latest_ask_blob(manifest, True, contract)
    if _ask_conflict(latest):
        return "答句互相打架：同一条里不能既写「这场不接」又写「接自己的授权」"
    if _ask_not_yet(latest):
        return "还没当面问过接不接自己的授权，不能把这一格点绿"
    if not _blob_has_pack_ask(latest):
        return "须有主人当面写下的「接自己的授权」或「这场不接」才能点这一格"
    if _skip_ask_in(latest):
        return None
    if _connect_two_step_ok(manifest, phase, contract):
        return None
    return "若接自己的授权：须一段孪生/测试分身/先测（未连正式），另记已连正式；一次接正式不能过这一格"
_SKIN_LOOK = ("主人已经看过", "主人已经看见", "主人看过", "主人看见")
_SKIN_NOUN = {
    "cli-tool": ("命令体验",),
    "desktop-product": ("界面",),
    "web-service": ("页面", "界面"),
    "source-takeover": ("界面", "命令体验"),
}
_SKIN_PRODUCT = "这个产品"
_SKIN_UNDO = {
    "cli-tool": (
        "还没改命令体验", "未改命令体验", "没改命令体验", "没有改命令体验",
    ),
    "desktop-product": (
        "还没改界面", "未改界面", "没改界面", "没有改界面",
    ),
    "web-service": (
        "还没改界面", "未改界面", "没改界面", "没有改界面",
        "还没改页面", "未改页面", "没改页面", "没有改页面",
    ),
    "source-takeover": (
        "还没改界面", "未改界面", "没改界面", "没有改界面",
        "还没改命令体验", "未改命令体验", "没改命令体验", "没有改命令体验",
    ),
}
_SKIN_PLAN = ("准备", "计划")
_SKIN_THIS_IS = "这是"
_SKIN_WRAP = _WRAP | set("《》〈〉")
_SKIN_PAIRS = (("《", "》"), ("〈", "〉"))
_SKIN_WS = " \t\r\n\u3000\xa0：:"
def _skin_peel_ws_wrap(s, j):
    while True:
        n = j
        while j > 0 and s[j - 1] in _SKIN_WS:
            j -= 1
        skipped = False
        for a, b in _SKIN_PAIRS:
            if j > 0 and s[j - 1] == b:
                k = s.rfind(a, 0, j - 1)
                if k >= 0:
                    j = k
                    skipped = True
                    break
        if not skipped:
            while j > 0 and s[j - 1] in _SKIN_WRAP:
                j -= 1
        if j == n:
            return j
def _skin_peel_this_is(s, j):
    while True:
        n = j
        j = _skin_peel_ws_wrap(s, j)
        w = len(_SKIN_THIS_IS)
        if j >= w and s[j - w:j] == _SKIN_THIS_IS:
            j -= w
            continue
        if j == n:
            return j
def _skin_try_peel_fill(s, k):
    for word in _LOOKS_FILL_WORDS:
        wn = len(word)
        if k >= wn and s[k - wn:k] == word:
            return k - wn
    if k >= 2 and s[k - 2:k] == "已经":
        return k - 2
    if k > 0 and s[k - 1] == "已":
        return k - 1
    if k > 0 and s[k - 1] == "改":
        return k - 1
    if k > 0 and s[k - 1] in _LOOKS_FILL:
        return k - 1
    return k
def _skin_peel_prefix(s, j):
    while True:
        n = j
        j = _skin_peel_this_is(s, j)
        j = _skin_try_peel_fill(s, j)
        if j == n:
            return j
def _skin_hedged(s, i):
    k = _skin_peel_this_is(s, i)
    while True:
        if _looks_valid_hedge(s, k, True):
            return True
        for look in _SKIN_PLAN:
            n = len(look)
            if k >= n and s[k - n:k] == look:
                return True
        nxt = _skin_try_peel_fill(s, k)
        if nxt == k:
            return False
        k = _skin_peel_this_is(s, nxt)
def _skin_clean_hit(s, n):
    blob = str(s or "")
    start, step = 0, len(n)
    while True:
        i = blob.find(n, start)
        if i < 0:
            return False
        if not _immediate_neg(blob, _skin_peel_prefix(blob, i), True) and not _skin_hedged(blob, i):
            return True
        start = i + step
def _skin_receipt_in(outcome, nouns):
    s = str(outcome or "")
    if not _skin_clean_hit(s, _SKIN_PRODUCT):
        return False
    if not any(_skin_clean_hit(s, n) for n in nouns):
        return False
    return any(_skin_clean_hit(s, look) for look in _SKIN_LOOK)
def _skin_undone(outcome, kind):
    undos = _SKIN_UNDO.get(kind) or ()
    blob = str(outcome or "")
    return any(_unnegated_hit(blob, u, True) for u in undos)
def _skin_hold_tests(manifest, contract):
    kind = (contract or {}).get("type")
    want = _ORIG_ASK_HOLD.get(kind)
    tests = [e for e in (manifest.get("tests") or []) if isinstance(e, dict)]
    if want:
        tests = [e for e in tests if e.get("phase_id") == want]
    return kind, tests
def _skin_seen(manifest, contract):
    kind, tests = _skin_hold_tests(manifest, contract)
    nouns = _SKIN_NOUN.get(kind)
    if not nouns or not tests:
        return False
    latest = str((tests[-1] or {}).get("outcome") or "")
    if _skin_undone(latest, kind):
        return False
    return any(_skin_receipt_in(t.get("outcome"), nouns) for t in tests)
def _skin_missing(kind):
    if kind == "cli-tool":
        return "还没看见命令体验已经改过，不能只拿答句过这一格"
    if kind == "web-service":
        return "还没看见页面已经改过，不能只拿答句过这一格"
    if kind == "source-takeover":
        return "还没看见界面或命令体验已经改过，不能只拿答句过这一格"
    return "还没看见界面已经改过，不能只拿答句过这一格"
def _ui_ask_hold(contract, manifest, phase):
    want = _ORIG_ASK_HOLD.get((contract or {}).get("type"))
    if not want or (phase or {}).get("id") != want:
        return False
    if not _orig_asked(contract, manifest):
        return True
    return not _skin_seen(manifest, contract)
_FEATURE_POISON = ("已验证", "5 分钟", "5分钟", "清单很完善")
# 作用列假完成套话。只比对作用列整格（去空白），不扫「现在人看见」。
_FAKE_PURPOSE = frozenset((
    "让人用主程序",
    "能进主界面",
    "进入主界面",
    "打开主界面",
    "能打开主界面",
    "能进入主界面",
    "能打开",
    "窗口亮了",
    "窗口亮",
    "主功能可用",
    "能用",
    "可用",
    "进入主程序",
    "打开主程序",
    "用主程序",
    "能进主程序",
    "主程序可用",
))


_ZW = {ord(c): None for c in "\u200b\u200c\u200d\ufeff\u2060"}


def _purpose_key(value):
    s = unicodedata.normalize("NFKC", str(value or ""))
    s = s.translate(_ZW)
    s = "".join(s.split())
    return s.strip("".join(_WRAP) + "。．.，,；;：:！!？?、")


def _feature_table_rows(product):
    feat = Path(product) / "FEATURES.md"
    if not feat.is_file():
        return []
    try:
        text = feat.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError):
        return []
    rows = []
    for line in text.split("\n"):
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if not cells or set("".join(cells)) <= set("-: "):
            continue
        if cells[0] in ("功能名",):
            continue
        rows.append(cells)
    return rows


def _delivered_copy_still_opens_main(product):
    """客户已装那一份若还在，工作拷贝关掉核心不能当授权做成。"""
    cores = list(_core_candidates(Path(product) / "installed"))
    opened = [p.name for p in cores if _naked_start_opens_main(p)]
    if opened:
        return "已经发给用户的那一份核心还能进主功能（工作拷贝关掉了不算）"
    return None


_NAKED_WAIT_SEC = 8
_TH32CS_SNAPPROCESS = 0x2


def _naked_start_report(path):
    """state: True=进了主功能，False=没进，None=真跑了仍没法判断。attempted=是否真去拉起。"""
    path = Path(path)
    if not path.is_file():
        return {"state": None, "attempted": False, "detail": "missing"}
    suf = path.suffix.casefold()
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    if suf == ".py":
        cmd = [sys.executable, "-B", str(path)]
    elif suf in (".bat", ".cmd") and os.name == "nt":
        cmd = ["cmd.exe", "/d", "/c", str(path)]
    elif suf == ".exe" and os.name == "nt":
        try:
            head = path.read_bytes()[:2]
        except OSError:
            return {"state": None, "attempted": False, "detail": "unreadable"}
        if head != b"MZ":
            return {"state": False, "attempted": False, "detail": "not_pe"}
        return _observe_naked_exe(path, flags)
    elif suf == ".exe":
        return {"state": None, "attempted": False, "detail": "not_windows"}
    else:
        return {"state": False, "attempted": False, "detail": "skipped_suffix"}
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=str(path.parent), timeout=_NAKED_WAIT_SEC, shell=False, creationflags=flags,
        )
        blob = (proc.stdout or "") + (proc.stderr or "")
    except subprocess.TimeoutExpired:
        return {"state": None, "attempted": True, "detail": "timeout"}
    except OSError:
        return {"state": False, "attempted": True, "detail": "launch_error"}
    if "MAIN_OPENED" in blob:
        return {"state": True, "attempted": True, "detail": "script_opened"}
    return {"state": False, "attempted": True, "detail": "script_closed"}


def _observe_naked_exe(path, flags):
    try:
        proc = subprocess.Popen(
            [str(path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(path.parent),
            shell=False,
            creationflags=flags,
        )
    except OSError:
        return {"state": None, "attempted": False, "detail": "launch_error"}
    seen_pids = {proc.pid}
    job = _win_job_attach(proc)
    saw_window = False
    deadline = time.monotonic() + _NAKED_WAIT_SEC
    try:
        while time.monotonic() < deadline:
            seen_pids |= _win_job_pids(job) | _win_tree_from(seen_pids)
            if _win_visible_windows_for(seen_pids):
                saw_window = True
                break
            live = _win_live_pids()
            parent_dead = proc.poll() is not None
            others_live = bool((seen_pids - {proc.pid}) & live)
            if parent_dead and not others_live:
                time.sleep(0.3)
                seen_pids |= _win_job_pids(job) | _win_tree_from(seen_pids)
                live = _win_live_pids()
                others_live = bool((seen_pids - {proc.pid}) & live)
                if _win_visible_windows_for(seen_pids):
                    saw_window = True
                    break
                if not others_live:
                    break
            time.sleep(0.1)
        if saw_window:
            return {"state": True, "attempted": True, "detail": "window"}
        live = _win_live_pids()
        still = (proc.poll() is None) or bool((seen_pids - {proc.pid}) & live)
        if still:
            return {"state": None, "attempted": True, "detail": "timeout"}
        out, err = ("", "")
        try:
            out, err = proc.communicate(timeout=2)
        except (subprocess.TimeoutExpired, OSError, ValueError):
            pass
        blob = _pipe_text(out) + _pipe_text(err)
        if "MAIN_OPENED" in blob:
            return {"state": True, "attempted": True, "detail": "script_opened"}
        return {"state": False, "attempted": True, "detail": "exited"}
    finally:
        _win_job_kill(job)
        _stop_pids(seen_pids)
        _stop_proc_tree(proc)


def _pipe_text(blob):
    if blob is None:
        return ""
    if isinstance(blob, bytes):
        return blob.decode("utf-8", "replace")
    return str(blob)


def _stop_proc_tree(proc):
    if proc is None:
        return
    try:
        pid = proc.pid
    except OSError:
        return
    _stop_pids({pid})
    try:
        if proc.poll() is None:
            proc.kill()
    except OSError:
        pass


def _stop_pids(pids):
    if os.name != "nt":
        return
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    for pid in set(pids or ()):
        if not pid:
            continue
        try:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(int(pid))],
                capture_output=True, timeout=5, creationflags=flags,
            )
        except (OSError, subprocess.TimeoutExpired, subprocess.SubprocessError, ValueError):
            continue


def _win_tree_from(pids):
    out = set(pids or ())
    if os.name != "nt":
        return out
    for pid in list(out):
        out |= _win_descendants(pid)
    return out


def _win_job_attach(proc):
    if os.name != "nt" or proc is None:
        return None
    handle = getattr(proc, "_handle", None)
    if not handle:
        return None
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        return None
    class _Basic(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]
    class _Io(ctypes.Structure):
        _fields_ = [("c", ctypes.c_uint64) for _ in range(6)]
    class _Ext(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", _Basic),
            ("IoInfo", _Io),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]
    info = _Ext()
    info.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    kernel32.SetInformationJobObject.argtypes = [
        wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    if not kernel32.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info)):
        kernel32.CloseHandle(job)
        return None
    kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    if not kernel32.AssignProcessToJobObject(job, wintypes.HANDLE(int(handle))):
        kernel32.CloseHandle(job)
        return None
    return job


def _win_job_pids(job):
    out = set()
    if not job or os.name != "nt":
        return out
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    class _List(ctypes.Structure):
        _fields_ = [
            ("NumberOfAssignedProcesses", wintypes.DWORD),
            ("NumberOfProcessIdsInList", wintypes.DWORD),
            ("ProcessIdList", ctypes.c_void_p * 256),
        ]
    buf = _List()
    needed = wintypes.DWORD(0)
    kernel32.QueryInformationJobObject.argtypes = [
        wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD)]
    if not kernel32.QueryInformationJobObject(
            job, 3, ctypes.byref(buf), ctypes.sizeof(buf), ctypes.byref(needed)):
        return out
    n = min(int(buf.NumberOfProcessIdsInList), 256)
    for i in range(n):
        pid = int(buf.ProcessIdList[i] or 0)
        if pid:
            out.add(pid)
    return out


def _win_job_kill(job):
    if not job or os.name != "nt":
        return
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    try:
        kernel32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
        kernel32.TerminateJobObject(job, 1)
    except OSError:
        pass
    try:
        kernel32.CloseHandle(job)
    except OSError:
        pass


def _win_live_pids():
    if os.name != "nt":
        return set()
    kids = _win_child_map()
    return {int(p) for p in kids.get("_live", [])}


def _win_descendants(pid):
    out = {pid}
    if os.name != "nt" or not pid:
        return out
    kids = _win_child_map()
    stack = [pid]
    while stack:
        cur = stack.pop()
        for child in kids.get(cur, []):
            if child not in out:
                out.add(child)
                stack.append(child)
    return out


def _win_child_map():
    if os.name != "nt":
        return {}
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    class _PE(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.c_void_p),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", ctypes.c_long),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", ctypes.c_char * 260),
        ]

    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel32.Process32First.argtypes = [wintypes.HANDLE, ctypes.POINTER(_PE)]
    kernel32.Process32Next.argtypes = [wintypes.HANDLE, ctypes.POINTER(_PE)]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    snap = kernel32.CreateToolhelp32Snapshot(_TH32CS_SNAPPROCESS, 0)
    if not snap or snap == wintypes.HANDLE(-1).value:
        return {}
    kids = {}
    try:
        entry = _PE()
        entry.dwSize = ctypes.sizeof(_PE)
        if not kernel32.Process32First(snap, ctypes.byref(entry)):
            return {}
        while True:
            pid = int(entry.th32ProcessID)
            kids.setdefault(int(entry.th32ParentProcessID), []).append(pid)
            kids.setdefault("_live", []).append(pid)
            if not kernel32.Process32Next(snap, ctypes.byref(entry)):
                break
        return kids
    except OSError:
        return {}
    finally:
        kernel32.CloseHandle(snap)


def _win_visible_windows_for(pids):
    if os.name != "nt" or not pids:
        return False
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    found = ctypes.c_int(0)
    pid_set = {int(p) for p in pids}

    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    @WNDENUMPROC
    def _cb(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        proc_id = wintypes.DWORD(0)
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(proc_id))
        if int(proc_id.value) in pid_set:
            found.value = 1
            return False
        return True

    try:
        user32.EnumWindows(_cb, 0)
    except OSError:
        return False
    return bool(found.value)


def _naked_start_state(path):
    """True=进了主功能，False=没进，None=真跑了仍没法判断。"""
    return _naked_start_report(path)["state"]


def _naked_start_opens_main(path):
    """双击/裸跑这份核心会不会进主功能。"""
    return _naked_start_state(path) is True


def _naked_start_unverified(path):
    return _naked_start_state(path) is None


def _python_prints_main_opened(path):
    return _naked_start_opens_main(path)


def _core_candidates(folder):
    folder = Path(folder)
    for name in ("core.py", "core.bat", "core.cmd", "core.exe"):
        path = folder / name
        if path.is_file():
            yield path


def _shell_without_closed_core(product):
    """启动器/授权壳在、核心还能进：J2 代理 A 那种报喜。"""
    root = Path(product)
    shells = ("launcher.py", "license_platform.py")
    has_shell = any((root / name).is_file() or (root / "installed" / name).is_file()
                    for name in shells)
    if not has_shell:
        return None
    opened = []
    if any(_naked_start_opens_main(p) for p in _core_candidates(root)):
        opened.append("工作拷贝")
    if any(_naked_start_opens_main(p) for p in _core_candidates(root / "installed")):
        opened.append("已发给用户的那一份")
    if opened:
        return "启动器或授权壳有了，核心还能进主功能（" + "、".join(opened) + "）"
    return None


def _customer_copy_not_this_version(product):
    """工作拷贝改了不算已装用户已升到这一版。"""
    root = Path(product)
    pairs = []
    for name in ("core.py", "core.bat", "core.cmd", "core.exe"):
        work = root / name
        inst = root / "installed" / name
        if work.is_file() and inst.is_file():
            pairs.append((work, inst))
    if not pairs:
        return None
    try:
        if all(w.read_bytes() == i.read_bytes() for w, i in pairs):
            return None
    except OSError:
        return None
    return "已经装好的那一份还不是这一版（工作拷贝改了不算）"


def _unfrozen_build_on_live_channel(product):
    """1.0 没冻住时，客户会下到的地址上不许已有下一版。"""
    channel = Path(product) / "channel"
    if not channel.is_dir():
        return None
    try:
        has_next = any(channel.iterdir())
    except OSError:
        return None
    if not has_next:
        return None
    if freeze_unready_reason(product) is None:
        return None
    return "1.0 还没冻住，客户会下到的地址上已经有下一版（半成品串线）"


def _edited_before_plan(product, contract, phase, ledger=None):
    """方案没点头就改了 baseline 文件。拦不住编辑器，但停点不能装成还在讨论。

    已经点过头再改上游，走 confirm --ack-drift，不算这一条。
    """
    if (phase or {}).get("id") not in ("0-discover-plan", "0-spec", "0-intake"):
        return None
    pid = phase.get("id")
    for event in ledger or []:
        if (isinstance(event, dict) and event.get("kind") == "confirm"
                and event.get("phase_id") == pid):
            return None
    drift = _baseline_drift(contract or {}, product)
    if not drift:
        return None
    return "方案还没点头就改了程序文件：" + "、".join(drift)


def _kept_demo_broken(product):
    """夹具约定：play.py 存在时，改别处之后还必须能 PLAY_OK。"""
    play = Path(product) / "play.py"
    if not play.is_file():
        return None
    try:
        proc = subprocess.run(
            [sys.executable, "-B", str(play)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=str(Path(product)), timeout=8, shell=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0,
        )
        blob = (proc.stdout or "") + (proc.stderr or "")
    except (OSError, subprocess.TimeoutExpired):
        return "已经能用的播放功能跑不起来（改这一处把别处弄坏了）"
    if "PLAY_OK" not in blob:
        return "已经能用的播放功能不在了（改这一处把别处弄坏了）"
    return None


def _owner_claim_text(product):
    chunks = []
    for name in ("AGENT-RESULT.txt", "CLAIM.txt"):
        path = Path(product) / name
        if not path.is_file():
            continue
        try:
            chunks.append(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError):
            continue
    return "\n".join(chunks)


def _claimed_done_without_customer_path(product):
    text = _owner_claim_text(product)
    if not any(w in text for w in ("做好了", "已完成", "已经做成")):
        return None
    if _delivered_copy_still_opens_main(product) or _customer_copy_not_this_version(product):
        return "说做好了，但客户会碰到的那一份还没对上"
    return None


def _asked_owner_to_qa(product):
    text = _owner_claim_text(product)
    if any(w in text for w in (
            "请你看", "请你自己试", "你自己试试看", "请主人看窗", "你不会自己测试吗",
            "回我「可以」", '回我"可以"', "回我可以", "请你点头", "现状盘点确认")):
        return "请主人当质检员（看窗之前自己必须先走过）"
    return None


def _is_hub_selftest(product):
    text = str(Path(product).resolve()).casefold()
    return any(mark in text for mark in (
        "hub-gold-", "hub-field-tests", "\\gold-", "/gold-", "hub-lean - 副本\\测试",
    ))


def _paperwork_before_run(product):
    """主程序还能进，却已经在填中枢表。"""
    opened = any(_naked_start_opens_main(p) for p in _core_candidates(Path(product)))
    if not opened:
        return None
    hub = Path(product) / ".hub"
    if not (hub / "contract.json").is_file():
        return None
    ledger = hub / "ledger.jsonl"
    n = 0
    if ledger.is_file():
        try:
            n = sum(1 for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip())
        except OSError:
            n = 0
    if n < 3:
        return None
    return "主程序还能进，却先填了中枢表（先跑软件再填表）"


_CLI_LICENSE_PAGE_BAN = (
    "不要为过关造授权页", "不要造授权页", "不为过关造授权页",
    "禁止造授权页", "不准造授权页", "不要做授权页",
)
_CLI_GUI_NEEDLES = ("tkinter", "PyQt5", "PyQt6", "wx.App", "MessageBox")


def _cli_text_forges_license_page(text):
    """真写了授权页才算造窗。说明书禁令、注释反例、断言里「没有授权页」不算。"""
    kept = []
    for line in str(text or "").splitlines():
        t = line.lstrip()
        if t.startswith("#") and "授权页" in line and any(
            b in line for b in ("不要", "禁止", "不准", "不为", "别造")
        ):
            continue
        kept.append(line)
    body = "\n".join(kept)
    for ban in _CLI_LICENSE_PAGE_BAN:
        body = body.replace(ban, "")
    body = re.sub(r"""["']授权页["']\s*not\s+in""", "", body, flags=re.I)
    return "授权页" in body


def _cli_forged_gui(product):
    """命令行产品不要为授权造窗。"""
    root = Path(product)
    try:
        files = list(root.rglob("*.py"))
    except OSError:
        return None
    for path in files:
        try:
            rel = path.relative_to(root)
        except ValueError:
            continue
        if ".hub" in rel.parts or "TEMP" in rel.parts:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if any(n in text for n in _CLI_GUI_NEEDLES) or _cli_text_forges_license_page(text):
            return "命令行产品造了窗口过授权门（不要为过关造窗）"
    return None


def _copied_rebuild_shell(product):
    """原创线不要抄二开核心载荷加启动器。"""
    root = Path(product)
    launcher = root / "launcher.py"
    core = root / "core.py"
    if not launcher.is_file() or not core.is_file():
        return None
    try:
        text = launcher.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    text = "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("#")
    )
    payload = ("core.py" in text) or ("core.exe" in text)
    runner = (
        "runpy" in text or "run_path" in text
        or "subprocess" in text or "Popen" in text or "os.system" in text
    )
    if payload and runner:
        return "原创产品抄了二开的核心载荷加启动器壳"
    return None


def _web_desktop_license_gate(product):
    """网站收费走页面，不要关软件、不要造桌面授权窗。"""
    root = Path(product)
    needles = ("tkinter", "PyQt5", "PyQt6", "wx.App", "MessageBox")
    try:
        files = list(root.rglob("*.py"))
    except OSError:
        return None
    for path in files:
        try:
            rel = path.relative_to(root)
        except ValueError:
            continue
        if ".hub" in rel.parts or "TEMP" in rel.parts:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if any(n in text for n in needles):
            return "网站用桌面窗或关软件过收费门（不要关软件）"
    return None


def _listed_safety_missing(product):
    """夹具列出的安全网文件缺了。"""
    listed = Path(product) / "SAFETY.NET"
    if not listed.is_file():
        return None
    try:
        names = [ln.strip() for ln in listed.read_text(encoding="utf-8").splitlines() if ln.strip()]
    except OSError:
        return None
    missing = [name for name in names if not (Path(product) / name).is_file()]
    if not missing:
        return None
    return "接手安全网缺了：" + "、".join(missing)


def _feature_show_gap(product):
    """打包/更新闸失败原因。None = 过闸。不过「现在人看见」。"""
    from hub_memory import memory_gate_gap
    memory_issue = memory_gate_gap(product)
    if memory_issue:
        return memory_issue
    feat = Path(product) / "FEATURES.md"
    if not feat.is_file():
        return "当前功能表没有真实行（function_map 不够；打包/更新停点不得已就绪）"
    rows = _feature_table_rows(product)
    if not rows:
        return "当前功能表没有真实行（function_map 不够；打包/更新停点不得已就绪）"
    blob = " ".join(c for row in rows for c in row)
    if any(p in blob for p in _FEATURE_POISON):
        return "当前功能表含已验证一类毒词，不能当打包/更新就绪"
    for row in rows:
        name = (row[0] if row else "").strip()
        purpose = (row[1] if len(row) > 1 else "").strip()
        if not name or not purpose:
            return "当前功能表有行但功能名或作用是空的"
        if _purpose_key(purpose) in _FAKE_PURPOSE:
            return "当前功能表作用列是套话（能进主界面/让人用主程序一类），不是作用是什么"
        compact = _purpose_key(purpose).lower()
        if compact.startswith("0x") or compact.startswith("rva") or "偏移" in purpose:
            return "当前功能表作用列只写了地址/偏移，不是作用是什么"
    return None


def _feature_show_ok(product):
    return _feature_show_gap(product) is None


def _contrast_filled(text):
    for line in text.split("\n"):
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if not cells or set("".join(cells)) <= set("-: "):
            continue
        name = cells[0]
        if not name or name in ("功能名", "功能"):
            continue
        now = cells[2] if len(cells) > 2 else ""
        if name and now:
            return True
    return False


def _read_feature_card(root, row):
    from hub_memory import load_memory, projections
    model = load_memory(root)
    name, use, now = row[:3]
    card = row[3] if len(row) > 3 else ""
    relative = card or f"features/{name}.md"
    if ":" in relative or Path(relative).is_absolute():
        raise ValueError(f"功能「{name}」卡片必须用普通相对路径，不能使用驱动器或数据流")
    path = _inside_no_links(root, relative)
    if not path.is_file():
        raise ValueError(f"功能「{name}」的卡片缺失：{path.name}")
    body = path.read_text(encoding="utf-8-sig")
    if model is not None:
        relative = path.relative_to(Path(root).resolve()).as_posix()
        if projections(model).get(relative) != body:
            raise ValueError(f'功能「{name}」卡片不符合持久记忆；先核对差异后重建视图')
    fields = {"now": [], "use": [], "name": []}
    for line in body.split("\n"):
        plain = line.strip()
        if plain.startswith("- "):
            plain = plain[2:]
        if plain.startswith("# "):
            plain = plain[2:]
        if plain.startswith("**"):
            end = plain.find("**", 2)
            if end < 0:
                continue
            label, value = plain[2:end], plain[end + 2:].strip()
            if label.endswith(("：", ":")):
                label = label[:-1]
            elif value.startswith(("：", ":")):
                value = value[1:].strip()
            else:
                continue
        else:
            parts = re.split(r"[：:]", plain, maxsplit=1)
            if len(parts) != 2:
                continue
            label, value = parts[0], parts[1].strip()
        if re.fullmatch(r"现在人看见(?:[（(][^）)]*[）)])?", label):
            fields["now"].append(value)
        elif label == "作用是什么":
            fields["use"].append(value)
        elif label == "功能名":
            fields["name"].append(value)
    if (fields["now"] != [now] or not now
            or fields["use"] and fields["use"] != [use]
            or fields["name"] and fields["name"] != [name]):
        raise ValueError(f"功能「{name}」总表与卡片的名称、作用或当前描述不一致；先核对实际程序，再同步记录")
    return path, body


def freeze_unready_reason(product):
    """Only a matching memory snapshot with complete comparisons is ready.

    This checks the memory baseline, not code reproducibility or business truth.
    Legacy snapshots may omit snapshot.json; their actual files still must match.
    """
    root = Path(product)
    frozen = root / "frozen"
    gap = "这一版还没冻住，不许让旧用户去下下一版（冻本对照还是空白、漏项或与当前文件不一致）"
    try:
        from hub_memory import load_memory, memory_gate_gap, JOURNAL, projections
        model = load_memory(root)
        if memory_gate_gap(root):
            return gap
        _inside_no_links(root, "frozen")
        current_rows = _feature_table_rows(root)
        if not frozen.is_dir() or not current_rows:
            return gap
        expected = {row[0]: row[2] for row in current_rows if len(row) >= 3 and row[0] and row[2]}
        if len(expected) != len(current_rows):
            return gap
        relatives = ["FEATURES.md"]
        if model is not None:
            relatives += [JOURNAL, *projections(model)]
        mmap = _inside_no_links(root, "MAP.md")
        if mmap.exists():
            relatives.append("MAP.md")
        if (root / "CHANGES.md").is_file():
            relatives.append("CHANGES.md")
        for row in current_rows:
            card, _ = _read_feature_card(root, row)
            relatives.append(card.relative_to(root.resolve()).as_posix())
        current_files = {rel: _inside_no_links(root, rel).read_bytes() for rel in relatives}
        for directory in frozen.iterdir():
            _inside_no_links(root, directory)
            if not directory.is_dir():
                continue
            try:
                if (directory / "MAP.md").exists() != mmap.exists():
                    continue
                if any(_inside_no_links(directory, rel).read_bytes() != data
                       for rel, data in current_files.items()):
                    continue
                comparison = _inside_no_links(directory, "对照-我们的vs原件.md")
                covered = {}
                for line in comparison.read_text(encoding="utf-8-sig").split("\n"):
                    if not line.strip().startswith("|"):
                        continue
                    cells = [c.strip() for c in line.strip().strip("|").split("|")]
                    if len(cells) >= 4 and all(cells[:4]) and cells[0] in expected:
                        if cells[0] in covered:
                            covered[cells[0]] = None
                        else:
                            covered[cells[0]] = cells[2]
                if covered == expected:
                    return None
            except (OSError, UnicodeError, ValueError):
                continue
    except (OSError, UnicodeError, ValueError):
        return gap
    return gap


# 打包/首次安装/更新/交付锁功能表和冻本。
_FEATURE_PACK_UPDATE = {
    "exe-rebuild": ("5-pack", "6-update", "3-ship", "7-handoff"),
    "desktop-product": ("4-package", "5-install", "6-update", "7-handoff"),
    "cli-tool": ("4-package", "5-install", "6-update", "7-handoff"),
    "web-service": ("4-staging", "5-data", "6-release", "7-ops"),
    "source-takeover": ("5-build", "6-release", "7-handoff"),
    "protocol-automation": ("7-handoff",),
}
_HANDOFF_PHASES = {
    "exe-rebuild": ("7-handoff",),
    "desktop-product": ("7-handoff",),
    "cli-tool": ("7-handoff",),
    "web-service": ("7-ops",),
    "source-takeover": ("7-handoff",),
    "protocol-automation": ("7-handoff",),
}
_INSTALL_PHASES = {
    "desktop-product": ("5-install",),
    "cli-tool": ("5-install",),
    "web-service": ("4-staging",),
    "source-takeover": ("5-build",),
}


def _gate_memory_gaps(product, contract, phases, cur, confirmed=None):
    """发货出口：只要打过包/磁盘上有冻本，退回前面格子也要再对冻本。"""
    locked = _FEATURE_PACK_UPDATE.get((contract or {}).get("type"), ())
    if not locked:
        return []
    root = Path(product)
    frozen = root / "frozen"
    try:
        has_freeze = frozen.is_dir() and any(frozen.iterdir())
    except OSError:
        has_freeze = False
    billed_confirmed = False
    for phase in phases or []:
        if phase.get("id") in locked and phase.get("stop_point") in (confirmed or ()):
            billed_confirmed = True
            break
    ids = [phase.get("id") for phase in phases or []]
    first = next((i for i, pid in enumerate(ids) if pid in locked), None)
    past = first is not None and (cur >= len(phases or []) or cur > first)
    if not (has_freeze or billed_confirmed or past):
        return []
    gaps = []
    gap = _feature_show_gap(product)
    if gap:
        gaps.append(gap)
    freeze = freeze_unready_reason(product)
    if freeze:
        gaps.append(freeze)
    if (contract or {}).get("type") == "exe-rebuild":
        cmap = _change_map_gap(product)
        if cmap:
            gaps.append(cmap)
    return gaps


def _missing_required_artifacts(phase, contract, ledger, hub, product):
    reqs = phase.get("requires", [])
    if not reqs:
        return []
    manifest = _validate_manifest(read_json(hub / "manifest.json", {}) or {})
    fp = contract_fingerprint(contract)
    current_cand, last_good = candidate_pointers(ledger)
    cand_state, _ = _candidate_live(product, current_cand)
    required_phase = phase.get("id")
    epoch = artifact_phase_epoch(contract, ledger, phase.get("id"))
    ptype = (contract or {}).get("type")
    missing = []
    expected_role = phase.get("candidate_role")
    if expected_role:
        if cand_state != "ok":
            missing.append(f"已登记且未被改动的 {expected_role} 候选")
        elif current_cand.get("role", "working") != expected_role:
            missing.append(
                f"当前候选角色应为 {expected_role}（实际 {current_cand.get('role', 'working')}；"
                f"用 `state candidate --set/--set-files ... --role {expected_role}` 登记对应阶段候选）"
            )
        elif expected_role not in ("upstream", "working") and not current_cand.get("parent_sha"):
            missing.append(f"{expected_role} 候选缺少 parent_sha 血缘，不能证明它从哪个候选产生")
    checks = phase_physical_checks(product, contract, phase)
    if checks:
        if cand_state != "ok" or not current_cand:
            missing.append("本阶段要求机器物理探针；当前候选未就绪，不能生成物理收据")
        else:
            absent = physical_receipt_missing(
                product, hub, contract, phase, ledger, current_cand.get("sha256"))
            if absent:
                missing.append("缺少当前候选的机器物理收据：" + "、".join(absent)
                               + "（不能用 --evidence 或手写 manifest 冒充）")
    for r in reqs:
        if r == "mission":
            if not _mission_complete(contract):
                missing.append("已锁定的 mission（先 `state plan --goal ... --success ... --route ...`）")
        elif r == "baseline":
            if not contract.get("upstream", {}).get("baseline"):
                missing.append("已锁定的 baseline（先 `state baseline --set <上游文件...>`）")
        elif r == "candidate":
            if cand_state == "none":
                missing.append("已登记的候选（先 `state candidate --set <文件>`）")
            elif cand_state == "missing":
                missing.append("当前候选文件不见了——重新登记：`state candidate --set <文件>`")
            elif cand_state == "mismatch":
                missing.append("当前候选文件被改动过、与登记哈希对不上——重新登记：`state candidate --set <文件>`")
            elif cand_state == "temp":
                missing.append("当前候选在产品根 TEMP/——拷到工作拷贝再 `state candidate --set <文件>`")
        elif r == "build":
            if cand_state != "ok":
                missing.append("已登记且未被改动的候选（build 必须对应当前候选字节；先修好候选）")
            elif not _artifact_current(manifest, "build", fp, current_cand.get("sha256"),
                                      required_phase, epoch, product, product_type=ptype):
                missing.append("manifest.build 需对应当前候选，且 artifact 必须是产品目录里已有的文件"
                               "（磁盘上没有安装包不能出货；换候选/换版本后旧记录失效）")
        else:
            key = KIND_TO_KEY.get(r, r)
            bind_sha = current_cand.get("sha256") if (
                key in CANDIDATE_BOUND_ARTIFACTS and cand_state == "ok"
            ) else None
            if key in CANDIDATE_BOUND_ARTIFACTS and cand_state != "ok":
                missing.append(f"manifest.{key} 需要先有未被改动的当前候选")
                continue
            if not _artifact_current(manifest, key, fp, bind_sha, required_phase, epoch, product,
                                    product_type=ptype):
                req = ARTIFACT_REQUIRED_FIELDS.get(key)
                extra = f"，且必须写清 {'/'.join(req)}" if req else "，要有实质内容、空对象不算"
                bind = "并绑定当前候选" if key in CANDIDATE_BOUND_ARTIFACTS else ""
                missing.append(f"manifest.{key}（先 `state record --kind {r} ...`；须属于当前版本{bind}{extra}）")
    if phase.get("require_bless"):
        if cand_state != "ok":
            missing.append("当前候选尚未 --bless 为 last-good（先登记未被改动的候选再 `candidate --bless`）")
        elif not last_good or last_good.get("sha256") != current_cand.get("sha256"):
            missing.append("当前候选尚未 --bless 为 last-good（先 `state candidate --set <文件> --bless`）")
    if phase.get("require_new_candidate"):
        if cand_state == "ok" and not last_good:
            missing.append("改造后须有 last-good 对照，且当前候选哈希须不同")
        elif cand_state == "ok" and last_good.get("sha256") == current_cand.get("sha256"):
            missing.append("改造后须重新登记与 last-good 不同的候选（先构建再 candidate --set）")
        elif (cand_state == "ok" and (contract or {}).get("type") == "source-takeover"
              and phase.get("id") == "4-change"):
            cur = _latest_match(manifest, "tests", fp, current_cand.get("sha256"),
                                phase.get("id"), epoch)
            if cur:
                b = json.dumps(cur, ensure_ascii=False)
                if not (_unnegated_hit(b, "安全网", True) and _unnegated_hit(b, "对照", True)):
                    missing.append("改造后须重跑安全网对照，不能只换几个字就算完成")
                else:
                    old = _latest_match(
                        manifest, "tests", fp, last_good.get("sha256"), "3-safety",
                        artifact_phase_epoch(contract, ledger, "3-safety"))
                    if old and (old.get("outcome"), old.get("evidence")) == (
                            cur.get("outcome"), cur.get("evidence")):
                        missing.append("不能沿用安全网旧证据，须重跑对照")
    phases = contract.get("phases") or []
    pack_id = None
    if phase.get("id") == "6-update" and any(p.get("id") == "5-pack" for p in phases):
        pack_id = "5-pack"
    elif (phase.get("id") == "7-handoff"
          and (contract or {}).get("type") == "exe-rebuild"
          and any(p.get("id") == "5-pack" for p in phases)):
        pack_id = "5-pack"
    elif (phase.get("id") == "7-handoff"
          and (contract or {}).get("type") in ("desktop-product", "cli-tool")
          and any(p.get("id") == "6-update" for p in phases)):
        pack_id = "6-update"
    elif (phase.get("id") == "7-ops"
          and (contract or {}).get("type") == "web-service"
          and any(p.get("id") == "6-release" for p in phases)):
        pack_id = "6-release"
    elif (phase.get("id") == "7-handoff"
          and (contract or {}).get("type") == "source-takeover"
          and any(p.get("id") == "6-release" for p in phases)):
        pack_id = "6-release"
    elif phase.get("id") == "5-install" and any(p.get("id") == "4-package" for p in phases):
        pack_id = "4-package"
    elif phase.get("id") == "5-data" and any(p.get("id") == "4-staging" for p in phases):
        pack_id = "4-staging"
    if (phase.get("id") in ("6-release", "7-handoff")
            and (contract or {}).get("type") == "source-takeover"):
        want = ""
        _, confirms, _, _, _, _ = derive(contract, ledger)
        for e in confirms:
            if (isinstance(e, dict) and e.get("phase_id") == "5-build"
                    and e.get("fp") == fp):
                want = str(e.get("cand_sha") or "")
        if (not want or cand_state != "ok" or current_cand.get("sha256") != want
                or not last_good or last_good.get("sha256") != want):
            missing.append("当前候选和 last-good 必须仍是发布候选那份哈希；换了没发布的字节不能点这一格")
    if pack_id:
        packed = _packed_release_sha(
            manifest, fp, artifact_phase_epoch(contract, ledger, pack_id), product, pack_id)
        if not packed:
            missing.append("上一格安装包须有还在磁盘上的包文件")
        elif cand_state != "ok" or current_cand.get("sha256") != packed:
            missing.append("当前候选必须仍是刚打进包的那份哈希；换了没打包的字节不能点这一格")
    ask = _pack_ask_gap(phase, contract, manifest)
    if ask:
        missing.append(ask)
    if _ui_ask_hold(contract, manifest, phase):
        if not _orig_asked(contract, manifest):
            missing.append("须有主人当面写下的「接自己的授权」或「这场不接」才能点这一格")
        else:
            missing.append(_skin_missing((contract or {}).get("type")))
    sp = (phase or {}).get("stop_point")
    if sp in _IMPL_STOPS:
        names = [str(m.get("name")) for m in (manifest.get("modules") or [])
                 if isinstance(m, dict) and m.get("name")]
        blob = json.dumps([t for t in (manifest.get("tests") or [])
                           if isinstance(t, dict) and t.get("phase_id") == phase.get("id")],
                          ensure_ascii=False)
        miss = [n for n in names if n not in blob]
        if miss:
            missing.append("须按模块表复验旧项还在：" + "、".join(miss))
    if sp == "分发包与跨平台确认":
        blob = _latest_spec_arch_blob(manifest)
        if any(k in blob for k in ("跨平台", "Linux", "macOS", "Darwin")):
            arts = [b.get("artifact") for b in (manifest.get("build") or [])
                    if isinstance(b, dict) and b.get("artifact")]
            n = len({a for a in arts if a and (product / str(a)).is_file()})
            if n < 2:
                missing.append("声称跨平台时磁盘须有不止一份分发包；一份本机包不能点绿")
    if _phase_needs_later_use(phase) and "anchor" not in reqs:
        has_later = _artifact_current(
            manifest, "anchors", fp, None, required_phase, epoch, product,
            product_type=ptype)
        if not has_later and "access" in reqs and cand_state == "ok":
            has_later = _artifact_current(
                manifest, "access", fp, current_cand.get("sha256"),
                required_phase, epoch, product, product_type=ptype)
        if not has_later:
            missing.append("账本里还没有「以后还能用」的记录（边做边记 `state record --kind anchor`，"
                           "how 须是当时那件事以后还用得上的原文，说明书套话不算）")
    locked = _FEATURE_PACK_UPDATE.get((contract or {}).get("type"), ())
    if phase.get("id") in locked:
        gap = _feature_show_gap(product)
        if gap:
            missing.append(gap)
        freeze = freeze_unready_reason(product)
        if freeze:
            missing.append(freeze)
        if (contract or {}).get("type") == "exe-rebuild":
            cmap = _change_map_gap(product)
            if cmap:
                missing.append(cmap)
    if ((contract or {}).get("type") == "exe-rebuild"
            and phase.get("id") == "1-access"):
        cmap = _change_map_gap(product)
        if cmap:
            missing.append(cmap)
    # 人能看见功能的那天必须有功能表。1-access 还在做，不拦。
    if ((contract or {}).get("type") == "exe-rebuild"
            and phase.get("id") == "3-ui"):
        gap = _feature_show_gap(product)
        if gap:
            missing.append(gap)
    if ((contract or {}).get("type") == "exe-rebuild"
            and phase.get("id") in ("4-license", "5-pack", "6-update", "3-ship")):
        delivered = _delivered_copy_still_opens_main(product)
        if delivered:
            missing.append(delivered)
        shell = _shell_without_closed_core(product)
        if shell:
            missing.append(shell)
        if phase.get("id") in ("5-pack", "6-update", "3-ship"):
            stale = _customer_copy_not_this_version(product)
            if stale:
                missing.append(stale)
            leaked = _unfrozen_build_on_live_channel(product)
            if leaked:
                missing.append(leaked)
    early = _edited_before_plan(product, contract, phase, ledger)
    if early:
        missing.append(early)
    kept = _kept_demo_broken(product)
    if kept:
        missing.append(kept)
    claimed = _claimed_done_without_customer_path(product)
    if claimed:
        missing.append(claimed)
    quizzed = _asked_owner_to_qa(product)
    if quizzed:
        missing.append(quizzed)
    if (contract or {}).get("type") == "cli-tool":
        forged = _cli_forged_gui(product)
        if forged:
            missing.append(forged)
    if (contract or {}).get("type") in ("desktop-product", "cli-tool"):
        copied = _copied_rebuild_shell(product)
        if copied:
            missing.append(copied)
    if (contract or {}).get("type") == "web-service":
        web = _web_desktop_license_gate(product)
        if web:
            missing.append(web)
    safety = _listed_safety_missing(product)
    if safety:
        missing.append(safety)
    paper = _paperwork_before_run(product)
    if paper:
        missing.append(paper)
    return missing
