import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

EVIDENCE_ID = re.compile(r"\bE-[A-Za-z0-9][A-Za-z0-9_-]*\b")
WORKITEM_ID = re.compile(r"\bWI-[A-Za-z0-9][A-Za-z0-9_-]*\b")
FINDING_ID = re.compile(r"\bF-[A-Za-z0-9][A-Za-z0-9_-]*\b")
PATH_ID = re.compile(r"\bP-[A-Za-z0-9][A-Za-z0-9_-]*\b")
FIELD_LINE = re.compile(r"^\s*-\s+([A-Za-z0-9_]+):\s*(.*)$")
SECTION_HEADING = re.compile(r"^#{2,6}\s+(.+?)\s*$")
EVIDENCE_HEADING = re.compile(r"^###\s+(E-[A-Za-z0-9][A-Za-z0-9_-]*)\b", re.MULTILINE)
FINDING_HEADING = re.compile(r"^###\s+(F-[A-Za-z0-9][A-Za-z0-9_-]*)\b", re.MULTILINE)
PATH_HEADING = re.compile(r"^###\s+(P-[A-Za-z0-9][A-Za-z0-9_-]*)\b", re.MULTILINE)

SEVERITIES = {"critical", "high", "medium", "low", "info", "n/a", "n/a_re"}
EVIDENCE_STATUSES = {"observed", "candidate", "validated", "false_positive", "accepted_risk", "superseded"}
WORKITEM_STATUSES = {"pending", "in_progress", "blocked", "done", "completed", "cancelled"}
PATH_TYPES = {"attack", "callflow", "solve"}
NETWORK_MODES = {"offline", "lab_only", "authorized_target_only", "unrestricted_lab"}

# --- rebuild delivery audit (only when work/<case>/rebuild.md exists) ---
# Contract: skills/ops/rebuild-gates.md (two gates) + skills/templates/rebuild.md.
# A case without rebuild.md skips all of this: the plain review stays identical.
FUNCTION_ID = re.compile(r"F-[A-Za-z0-9][A-Za-z0-9_-]*")
REBUILD_STATE_ALIASES = {
    "已分析": "analyzed",
    "已实现": "implemented",
    "已测试": "tested",
    "已通过约定测试": "tested",
    "对照一致": "verified",
    "受限": "limited",
}
REBUILD_STATE_LABELS = {
    "analyzed": "已分析",
    "implemented": "已实现",
    "tested": "已测试",
    "verified": "对照一致",
    "limited": "受限",
}
REBUILD_STATE_ORDER = ("analyzed", "implemented", "tested", "verified", "limited")
REBUILD_COMPLETED_STATES = {"tested", "verified"}
REBUILD_DIFF_COLUMNS = ("输入条件", "原程序结果", "新实现结果", "是否一致", "说明")
REBUILD_NEGATIVE_VERDICT = re.compile(r"[不未](?:能|曾)?一致|不匹配|不(?:相)?同|mismatch|not[\s_-]*same|false\b|^否$|^no$", re.I)
# 「对照一致」的肯定判据：只有对照行明说一致，状态才配叫完成。
# 空串 / 待判 / pending / 认不出的写法都不算 —— 那是「证据还没说话」。
REBUILD_POSITIVE_VERDICT = re.compile(r"一致|相同|匹配|match(?:ed|es)?\b|identical|\bsame\b|^yes\b|^true\b|^是", re.I)
REBUILD_COVERAGE_ITEMS = (
    ("function_list", "功能清单全覆盖", re.compile(r"功能清单|function\s*list", re.I)),
    ("critical_function_status", "关键功能状态", re.compile(r"关键功能|critical\s*function", re.I)),
    ("known_diff", "已知差异已记录", re.compile(r"已知差异|known\s*deviation", re.I)),
)
REBUILD_DIFF_REF = re.compile(r"[A-Za-z0-9_./\\-]*diff[/\\][A-Za-z0-9_.\\/-]+")
# diff-runner 草稿里的两段原始 stdout；一条记录可含多组（--input 可重复）。
# 完成态行引用的记录必须带这两段，且两段**逐字节**一致——这是「验内容不验自称」的
# 判据本体：按 bytes 匹配、不做编码/换行归一化，`\n` vs `\r\n` 这类差异无处藏身。
REBUILD_STDOUT_BLOCK = re.compile(
    rb"--- baseline stdout ---\r?\n(?P<baseline>.*?)\r?\n?--- rebuilt stdout ---\r?\n(?P<rebuilt>.*?)(?=\r?\n?```)",
    re.S,
)
# 记录登记的可复现性：命令字段 + 每次运行的 run 行（exit/error）。
# 没跑起来的命令（shell 缺失 / 超时）不能支撑任何完成态判定。
REBUILD_RUN_LINE = re.compile(rb"(?m)^\s*-\s*(baseline|rebuilt):\s*exit=(\S+)(.*)$")

# --- update follow-up audit (only when work/<case>/update.md exists) ---
# Contract: skills/ops/rebuild-gates.md [更新阶段] + skills/templates/update.md.
# A case without update.md skips all of this: the plain review stays identical.
UPDATE_FINGERPRINT_FIELDS = ("old_upstream", "new_upstream", "our_old_build")
UPDATE_THREE_LINE_FIELDS = ("we_changed", "upstream_new", "portable")
UPDATE_DELTA_ACTIONS = {"keep", "retest", "redo", "new"}
UPDATE_VERIFICATION_COLUMNS = ("输入", "新版原程序结果", "新复刻结果", "是否一致", "说明")
UPDATE_SHA256 = re.compile(r"(?i)\b[0-9a-f]{64}\b")
UPDATE_DIFF_UPDATE_REF = re.compile(r"[A-Za-z0-9_./\\-]*diff-update[/\\][A-Za-z0-9_.\\/-]+")

# --- assault rolling-report audit (only when work/<case>/assault.md exists) ---
# Contract: skills/reverse-engineering/references/assault-entry.md (four-state machine)
# + skills/templates/assault.md. A case without assault.md skips all of this: the
# plain review stays identical.
ASSAULT_STATES = ("SURVEY", "ROUTE", "EXECUTE", "VERIFY")
ASSAULT_LAYER_ID = re.compile(r"L\d+")
ASSAULT_UNKNOWN_ID = re.compile(r"U-[A-Za-z0-9][A-Za-z0-9_-]*")
ASSAULT_BLOCKED = re.compile(r"blocked|受阻|阻塞", re.I)
ASSAULT_BLOCKED_REASON_ALTERNATES = (
    ("原因", re.compile(r"原因|reason", re.I)),
    ("影响", re.compile(r"影响|impact", re.I)),
    ("替代", re.compile(r"替代|fallback|alternate|alternative", re.I)),
)

def field_value(text, name):
    lines = text.splitlines()
    for index, line in enumerate(lines):
        match = FIELD_LINE.match(line)
        if not match or match.group(1) != name:
            continue
        value = match.group(2).strip()
        if value != "|":
            return value
        block = []
        for continuation in lines[index + 1:]:
            if FIELD_LINE.match(continuation):
                break
            if SECTION_HEADING.match(continuation):
                break
            if continuation.strip():
                block.append(continuation.strip())
        return "\n".join(block).strip()
    return ""

def section_text(text, title):
    pattern = re.compile(
        r"(?ms)^##\s+" + re.escape(title) + r"\s*$\n?(.*?)(?=^##\s|\Z)"
    )
    match = pattern.search(text)
    return match.group(1) if match else ""

def ids_in(value, pattern):
    return sorted(set(pattern.findall(value or "")))

def issue(issues, level, code, message, path=""):
    issues.append({"level": level, "code": code, "message": message, "path": path})

def relative_path(root, path):
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)

def split_table_row(line):
    stripped = line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        return []
    return [cell.strip() for cell in stripped[1:-1].split("|")]

def _is_markdown_separator_row(cells):
    return bool(cells) and all(re.fullmatch(r":?-{2,}:?", cell or "-") for cell in cells)

def _iter_table_rows(text):
    """Yield (line_number, cells) for every Markdown table row, headers included."""
    for line_number, line in enumerate(text.splitlines(), 1):
        cells = split_table_row(line)
        if cells:
            yield line_number, cells

def _diff_record_refs(value):
    """Cited diff-record paths in an evidence cell (case-root relative, POSIX style)."""
    return [candidate.replace("\\", "/").lstrip("/")
            for candidate in REBUILD_DIFF_REF.findall(value or "")]

def _stdout_blocks(data):
    """Yield the (baseline, rebuilt) raw stdout byte pairs a record carries.

    A record without any pair predates the raw blocks (old format): the caller
    reports the migration-window warning instead of guessing a verdict.
    """
    for match in REBUILD_STDOUT_BLOCK.finditer(data):
        yield match.group("baseline"), match.group("rebuilt")

def _record_reproducibility_gap(data):
    """Classify why a diff record cannot back a completion claim.

    Returns (level, reason): "error" when a registered command demonstrably did
    not execute (exit=ERROR / exit=TIMEOUT / a recorded error message); "warning"
    when the record predates the command/run fields (migration window: re-run
    diff-runner to register them); None when the record carries executed runs.
    """
    if not (b"baseline_command:" in data and b"rebuilt_command:" in data):
        return ("warning", "no baseline_command/rebuilt_command registered")
    runs = REBUILD_RUN_LINE.findall(data)
    if not runs:
        return ("warning", "no run lines (- baseline: exit=...) recorded")
    for side, exit_code, tail in runs:
        if exit_code in (b"ERROR", b"TIMEOUT"):
            return ("error", "%s command did not execute (exit=%s)" % (side.decode(), exit_code.decode()))
        if b"error=" in tail:
            detail = tail.split(b"error=", 1)[1].strip()
            if detail:
                return ("error", "%s command did not execute (%s)" % (side.decode(), detail.decode("utf-8", "replace")))
    return None

def parse_rebuild(root, issues):
    """Parse rebuild.md against skills/templates/rebuild.md, then audit the delivery.

    Returns None when the file is absent: a non-rebuild case must produce exactly
    the same report as before this audit existed. When present, four checks run:
      1. a row's state may not be higher than its evidence supports;
      2. every diff_baseline row keeps its five columns;
      3. Coverage carries the three rebuild items;
      4. a completed row's cited diff record must show identical stdout for both
         programs (the record is the evidence; the table's claim is not).
    """
    path = root / "rebuild.md"
    if not path.is_file():
        return None

    text = path.read_text(encoding="utf-8-sig")
    result = {
        "present": True,
        "path": "rebuild.md",
        "functions": {},       # F-xxx -> {"state": ..., "evidence": ..., "note": ..., "line": int}
        "diff_rows": [],       # {"id":..., "cells":[...], "line":...}
        "coverage": {},        # key -> (found: bool, checked: bool)
        "target_present": False,
    }

    # --- target: 交付物一行说清 ---
    target_section = section_text(text, "target")
    if target_section and field_value(target_section, "deliverable"):
        result["target_present"] = True
    else:
        issue(issues, "error", "rebuild.target_missing",
              "rebuild.md has no target.deliverable (state what the case delivers)",
              "rebuild.md")

    # --- functions: F-xxx rows carry 名称/入口/预期输出/验收条件/路线 ---
    functions_section = section_text(text, "functions")
    function_lines = {}
    for line_number, cells in _iter_table_rows(functions_section):
        if _is_markdown_separator_row(cells):
            continue
        if not cells or not FUNCTION_ID.fullmatch(cells[0]):
            continue
        if len(cells) < 6:
            issue(issues, "error", "rebuild.function_columns",
                  cells[0] + " row needs 6 columns 名称/入口/预期输出/验收条件/路线",
                  "rebuild.md:" + str(line_number))
            continue
        function_lines[cells[0]] = line_number
        missing = [name for name, value in zip(
            ("名称", "入口", "预期输出", "验收条件", "路线"), cells[1:6]) if not value]
        if missing:
            issue(issues, "error", "rebuild.function_field_missing",
                  cells[0] + " is missing " + "/".join(missing), "rebuild.md:" + str(line_number))

    if not function_lines:
        issue( issues, "error", "rebuild.functions_empty",
              "rebuild.md has no F-xxx function rows (functions table is the delivery contract)",
              "rebuild.md")

    # --- acceptance: state may not exceed evidence ---
    acceptance_section = section_text(text, "acceptance")
    for line_number, cells in _iter_table_rows(acceptance_section):
        if _is_markdown_separator_row(cells):
            continue
        if not cells or not FUNCTION_ID.fullmatch(cells[0]):
            continue
        function_id = cells[0]
        state_raw = cells[1] if len(cells) > 1 else ""
        evidence = cells[2] if len(cells) > 2 else ""
        note = cells[3] if len(cells) > 3 else ""
        state = REBUILD_STATE_ALIASES.get(state_raw.strip())
        if state is None:
            issue(issues, "error", "rebuild.state_invalid",
                  function_id + " has unsupported state: " + (state_raw or "(empty)") +
                  " (allowed: " + "/".join(REBUILD_STATE_LABELS[key] for key in REBUILD_STATE_ORDER) + ")",
                  "rebuild.md:" + str(line_number))
            continue
        result["functions"][function_id] = {
            "state": state, "evidence": evidence, "note": note,
            "line": function_lines.get(function_id, line_number),
        }

    # --- diff_baseline: five columns must be filled per row ---
    diff_section = section_text(text, "diff_baseline")
    for line_number, cells in _iter_table_rows(diff_section):
        if _is_markdown_separator_row(cells):
            continue
        if not cells or not FUNCTION_ID.fullmatch(cells[0]):
            continue
        result["diff_rows"].append({"id": cells[0], "cells": cells, "line": line_number})
        # The five contract columns follow the F-ID column.
        body = cells[1:6]
        if len(body) < 5:
            issue(issues, "error", "rebuild.diff_columns",
                  cells[0] + " diff_baseline row needs 5 columns 输入条件/原程序结果/新实现结果/是否一致/说明",
                  "rebuild.md:" + str(line_number))
            continue
        empty = [name for name, value in zip(REBUILD_DIFF_COLUMNS, body) if not value]
        if empty:
            issue(issues, "error", "rebuild.diff_incomplete",
                  cells[0] + " diff_baseline row leaves column(s) empty: " + "/".join(empty),
                  "rebuild.md:" + str(line_number))

    # --- Coverage: three rebuild items live in workitems.md ---
    # Scan every checkbox line in the file (not only the first "## Coverage"
    # section): a case may append the rebuild items as their own section, and
    # the item wording is distinctive enough to identify them on its own.
    workitems_path = root / "workitems.md"
    workitems_text = workitems_path.read_text(encoding="utf-8-sig") if workitems_path.is_file() else ""
    checkbox_lines = [
        re.match(r"^\s*[-*]\s*\[(?P<mark>[ xX])\]\s*(?P<text>.*)$", line)
        for line in workitems_text.splitlines()
    ]
    for key, label, pattern in REBUILD_COVERAGE_ITEMS:
        found = False
        checked = False
        for item in checkbox_lines:
            if item and pattern.search(item.group("text")):
                found = True
                checked = checked or item.group("mark").lower() == "x"
        result["coverage"][key] = (found, checked)
        if not found:
            issue(issues, "error", "rebuild.coverage_missing",
                  "workitems.md Coverage is missing the rebuild item: " + label, "workitems.md")
        elif not checked:
            issue(issues, "warning", "rebuild.coverage_unchecked",
                  "rebuild Coverage item not yet checked: " + label, "workitems.md")

    # --- cross-check 1: state vs evidence ---
    # Rule: a row's state may not be higher than its evidence supports.
    #   tested / 对照一致 without evidence  -> error (the state-虚高 this gate exists to catch)
    #   analyzed / implemented without evidence -> warning (施工依据缺哪行补哪行; not a stop)
    #   受限 needs the note instead of evidence (cause / impact / fallback)
    for function_id, record in sorted(result["functions"].items()):
        state = record["state"]
        if state == "limited":
            if not record["note"]:
                issue(issues, "error", "rebuild.limited_note_missing",
                      function_id + " is 受限 without a note (record 原因/影响/替代方案)",
                      "rebuild.md:" + str(record["line"]))
            continue
        if record["evidence"]:
            continue
        if state in REBUILD_COMPLETED_STATES:
            issue(issues, "error", "rebuild.state_exceeds_evidence",
                  function_id + " is marked " + REBUILD_STATE_LABELS[state] +
                  " with an empty evidence column; fill the evidence (E-xxx or a diff/ record) first",
                  "rebuild.md:" + str(record["line"]))
        else:
            issue(issues, "warning", "rebuild.evidence_pending",
                  function_id + " is " + REBUILD_STATE_LABELS[state] +
                  " without evidence yet; fill the evidence column before moving it up the ladder",
                  "rebuild.md:" + str(record["line"]))

    # --- cross-check 1b: 功能清单全覆盖 (functions <-> acceptance) ---
    for function_id in sorted(set(function_lines) - set(result["functions"])):
        issue(issues, "error", "rebuild.acceptance_missing",
              function_id + " is in the functions table but has no acceptance row (功能清单全覆盖)",
              "rebuild.md")
    for function_id in sorted(set(result["functions"]) - set(function_lines)):
        issue(issues, "error", "rebuild.function_unknown",
              function_id + " has an acceptance row but no functions row",
              "rebuild.md")

    # --- cross-check 1c: evidence that names a local diff record must exist ---
    for function_id, record in sorted(result["functions"].items()):
        token = (record["evidence"] or "").strip()
        if not token:
            continue
        for relative in _diff_record_refs(token):
            absolute = root / relative
            if not absolute.is_file():
                issue(issues, "error", "rebuild.diff_record_missing",
                      function_id + " cites a comparison record that does not exist: " + relative,
                      "rebuild.md:" + str(record["line"]))

    # --- cross-check 1d: a completed row's record must not contradict its claim ---
    # 完成判定的实质证据 = diff 记录里的两段原始 stdout。判据只对含这两段的记录生效：
    #   · 两段逐字节不同 -> diff_bytes_mismatch（表格自称「一致」不作数，验内容不验自称）；
    #   · 记录显示命令没跑起来（exit=ERROR/TIMEOUT/error）-> diff_unreproducible。
    # 老格式记录（缺原始块 / 缺命令或运行行登记）只记 warning：迁移窗口，重跑
    # diff-runner 即可补齐，不硬红。（generated 时间戳在记录头部、不在这两段内：
    # 段内字节比较天然不受重跑时间影响。）
    for function_id, record in sorted(result["functions"].items()):
        if record["state"] not in REBUILD_COMPLETED_STATES:
            continue
        for relative in dict.fromkeys(_diff_record_refs(record["evidence"])):
            absolute = root / relative
            if not absolute.is_file():
                continue  # cross-check 1c already reported the missing record
            try:
                record_bytes = absolute.read_bytes()
            except OSError:
                continue
            pairs = list(_stdout_blocks(record_bytes))
            if not pairs:
                issue(issues, "warning", "rebuild.diff_unparsed",
                      function_id + " cites " + relative + " without the two raw stdout blocks; "
                      "re-run diff-runner to add them (byte comparison applies only to records that carry them)",
                      relative)
                continue
            if any(baseline != rebuilt for baseline, rebuilt in pairs):
                issue(issues, "error", "rebuild.diff_bytes_mismatch",
                      function_id + " is marked " + REBUILD_STATE_LABELS[record["state"]] +
                      " but its cited record shows differing stdout for the two programs: " + relative,
                      relative)
            gap = _record_reproducibility_gap(record_bytes)
            if gap:
                level, reason = gap
                if level == "error":
                    issue(issues, "error", "rebuild.diff_unreproducible",
                          function_id + " cites " + relative + ": " + reason +
                          " (a completion claim needs runs that actually happened)",
                          relative)
                else:
                    issue(issues, "warning", "rebuild.diff_unparsed",
                          function_id + " cites " + relative + " without registered commands/run lines: " + reason +
                          " (re-run diff-runner to register them; the migration window treats this as a warning)",
                          relative)

    # --- cross-check 2: states >= tested need a matching diff row ---
    diff_by_id = {row["id"]: row for row in result["diff_rows"]}
    for function_id, record in sorted(result["functions"].items()):
        state = record["state"]
        if state not in REBUILD_COMPLETED_STATES:
            continue
        row = diff_by_id.get(function_id)
        if row is None:
            issue(issues, "error", "rebuild.diff_row_missing",
                  function_id + " is marked " + REBUILD_STATE_LABELS[state] +
                  " but has no diff_baseline row (same-input comparison is the completion evidence)",
                  "rebuild.md:" + str(record["line"]))
            continue
        verdict = row["cells"][4] if len(row["cells"]) > 4 else ""
        if REBUILD_NEGATIVE_VERDICT.search(verdict):
            # 对照行明说「不一致 / mismatch」，状态却已进入完成段（已测试 / 对照一致）。
            # 判据来源：rebuild-gates.md 闸门② —— 完成形态只有「对照一致」或「受限+原因」。
            issue(issues, "error", "rebuild.diff_verdict_conflict",
                  function_id + " is marked " + REBUILD_STATE_LABELS[state] +
                  " but its diff row verdict reads: " + verdict,
                  "rebuild.md:" + str(row["line"]))
        elif not REBUILD_POSITIVE_VERDICT.search(verdict):
            # 对照行既非不一致、也非一致（空串 / 待判 / 认不出的写法）—— 这正是
            # 「做一半就宣布成功」的形状：状态写成完成，对照证据却还没说话。
            issue(issues, "error", "rebuild.diff_verdict_unproven",
                  function_id + " is marked " + REBUILD_STATE_LABELS[state] +
                  " but its diff row verdict does not assert 一致 (reads: " +
                  (verdict or "(empty)") + ")",
                  "rebuild.md:" + str(row["line"]))

    return result


def _update_field_filled(value):
    """True when a field carries real content, not the template placeholder.

    The template ships values wrapped in backticks with angle brackets
    (`` `<...>` ``): an unfilled skeleton keeps the placeholder, and a
    placeholder must not count as "written" — otherwise 三句对照 passes
    before anyone wrote a single sentence.
    """
    stripped = (value or "").strip()
    if not stripped:
        return False
    inner = stripped.strip("`").strip()
    return not (inner.startswith("<") and inner.endswith(">"))


def parse_update(root, issues, rebuild):
    """Parse update.md against skills/templates/update.md, then audit the follow-up.

    Returns None when the file is absent: a non-update case must produce exactly
    the same report as before this audit existed. When present, four checks run
    (skills/ops/rebuild-gates.md [更新阶段] + docs/UPDATE-GOAL-2026-10-12.md §4.3):
      1. three_lines: all three fields carry real content (缺一句 = 更新范围没定义);
      2. function_delta covers every F-ID in rebuild.md's functions table;
      3. verification rows keep their five columns; a row whose verdict asserts
         一致 must have its diff-update record, and the record is held to the
         same byte-level scale as 初逆 (raw stdout blocks compared byte for byte);
      4. the three version fingerprints carry a 64-hex SHA256 each.
    Also: a recorded 动作 must be keep/retest/redo/new; only action=new may
    introduce an F-ID that rebuild.md does not list.
    """
    path = root / "update.md"
    if not path.is_file():
        return None

    text = path.read_text(encoding="utf-8-sig")
    result = {
        "present": True,
        "path": "update.md",
        "fingerprints": {},    # field -> bool (hash present)
        "three_lines": {},     # field -> bool (real content present)
        "delta_rows": [],      # {"id":..., "action":..., "line":...}
        "verification_rows": [],  # {"id":..., "cells":[...], "line":...}
    }

    # --- check 4: three version fingerprints, each carrying a 64-hex SHA256 ---
    target_section = section_text(text, "target")
    for field in UPDATE_FINGERPRINT_FIELDS:
        value = field_value(target_section, field)
        has_hash = bool(UPDATE_SHA256.search(value or ""))
        result["fingerprints"][field] = has_hash
        if not value:
            issue(issues, "error", "update.fingerprint_missing",
                  "update.md target is missing " + field + " (path | version | sha256:<64hex>)",
                  "update.md")
        elif not has_hash:
            issue(issues, "error", "update.fingerprint_hashless",
                  "update.md target." + field + " has no 64-hex SHA256 (got: " + value + ")",
                  "update.md")

    # --- check 1: three_lines all carry real content ---
    three_lines_section = section_text(text, "three_lines")
    for field in UPDATE_THREE_LINE_FIELDS:
        value = field_value(three_lines_section, field)
        filled = _update_field_filled(value)
        result["three_lines"][field] = filled
        if not filled:
            issue(issues, "error", "update.three_lines_missing",
                  "update.md three_lines." + field + " is empty or still the placeholder "
                  "(缺一句 = 更新范围没定义)",
                  "update.md")

    # --- function_delta: per-F-ID rows with a legal action ---
    delta_section = section_text(text, "function_delta")
    for line_number, cells in _iter_table_rows(delta_section):
        if _is_markdown_separator_row(cells):
            continue
        if not cells or cells[0] == "F-ID" or not FUNCTION_ID.fullmatch(cells[0]):
            continue
        action_raw = cells[3].strip().lower() if len(cells) > 3 else ""
        result["delta_rows"].append({"id": cells[0], "action": action_raw, "line": line_number})
        if action_raw and action_raw not in UPDATE_DELTA_ACTIONS:
            issue(issues, "error", "update.delta_action_invalid",
                  cells[0] + " has unsupported action: " + action_raw +
                  " (allowed: keep/retest/redo/new)",
                  "update.md:" + str(line_number))

    if not result["delta_rows"]:
        issue(issues, "error", "update.delta_empty",
              "update.md function_delta has no F-xxx rows (逐行判定 = 更新范围的定义)",
              "update.md")

    # --- check 2: function_delta covers every F-ID in rebuild.md ---
    # 漏一行 = 更新范围没定义：rebuild.md 功能表里的每个 F-ID 都要有处置。
    if rebuild and rebuild.get("functions"):
        delta_ids = {row["id"] for row in result["delta_rows"]}
        for function_id in sorted(set(rebuild["functions"]) - delta_ids):
            issue(issues, "error", "update.delta_missing",
                  function_id + " is in rebuild.md functions but has no function_delta row "
                  "(every F-ID needs a keep/retest/redo/new decision)",
                  "update.md")
        # 新能力行（动作 new）允许引入 rebuild.md 之外的新 F-ID；其余未知 ID 报错。
        for row in result["delta_rows"]:
            if row["id"] not in rebuild["functions"] and row["action"] != "new":
                issue(issues, "error", "update.delta_unknown",
                      row["id"] + " has a function_delta row but no rebuild.md functions row "
                      "(only action=new may introduce a new F-ID)",
                      "update.md:" + str(row["line"]))

    # --- check 3: verification five columns + 对照一致 held to the same scale ---
    verification_section = section_text(text, "verification")
    for line_number, cells in _iter_table_rows(verification_section):
        if _is_markdown_separator_row(cells):
            continue
        if not cells or cells[0] == "F-ID" or not FUNCTION_ID.fullmatch(cells[0]):
            continue
        result["verification_rows"].append({"id": cells[0], "cells": cells, "line": line_number})
        body = cells[1:6]
        if len(body) < 5:
            issue(issues, "error", "update.verification_columns",
                  cells[0] + " verification row needs 5 columns 输入/新版原程序结果/新复刻结果/是否一致/说明",
                  "update.md:" + str(line_number))
            continue
        empty = [name for name, value in zip(UPDATE_VERIFICATION_COLUMNS, body) if not value]
        if empty:
            issue(issues, "error", "update.verification_incomplete",
                  cells[0] + " verification row leaves column(s) empty: " + "/".join(empty),
                  "update.md:" + str(line_number))
        verdict = body[3]
        if not REBUILD_POSITIVE_VERDICT.search(verdict):
            continue
        # 「对照一致」的行必须有对应的对照记录：行内显式引用优先，
        # 缺省约定为 diff-update/<F-ID>.md。显式路径不存在 → 直接报；
        # 未显式引用 → 缺省记录文件必须在位。
        explicit = []
        for value in list(cells) + [verdict]:
            for candidate in UPDATE_DIFF_UPDATE_REF.findall(value or ""):
                normalized = candidate.replace("\\", "/").lstrip("/")
                if normalized not in explicit:
                    explicit.append(normalized)
        default_ref = "diff-update/" + cells[0] + ".md"
        if explicit:
            candidates = explicit
        else:
            candidates = [default_ref]
        existing = [candidate for candidate in candidates if (root / candidate).is_file()]
        if not existing:
            issue(issues, "error", "update.verification_record_missing",
                  cells[0] + " verification row asserts 一致 but its record does not exist: " +
                  "/".join(candidates) + " (run diff-runner --out-dir diff-update first)",
                  "update.md:" + str(line_number))
            continue
        # 与初逆同一把尺：记录里的两段原始 stdout 逐字节比对 + 可复现性检查。
        for relative in existing:
            try:
                record_bytes = (root / relative).read_bytes()
            except OSError:
                continue
            pairs = list(_stdout_blocks(record_bytes))
            if not pairs:
                issue(issues, "warning", "update.diff_unparsed",
                      cells[0] + " cites " + relative + " without the two raw stdout blocks; "
                      "re-run diff-runner to add them (byte comparison applies only to records that carry them)",
                      relative)
                continue
            if any(baseline != rebuilt for baseline, rebuilt in pairs):
                issue(issues, "error", "update.diff_bytes_mismatch",
                      cells[0] + " asserts 一致 but its record shows differing stdout for the two programs: " + relative,
                      relative)
            gap = _record_reproducibility_gap(record_bytes)
            if gap:
                level, reason = gap
                if level == "error":
                    issue(issues, "error", "update.diff_unreproducible",
                          cells[0] + " cites " + relative + ": " + reason +
                          " (a completion claim needs runs that actually happened)",
                          relative)
                else:
                    issue(issues, "warning", "update.diff_unparsed",
                          cells[0] + " cites " + relative + " without registered commands/run lines: " + reason +
                          " (re-run diff-runner to register them; the migration window treats this as a warning)",
                          relative)

    return result


def _deliverable_candidates(value):
    """Path-like tokens from the assault deliverable field (backticked spans first).

    The contract (templates/assault.md) wants a file path + form, not prose; a
    placeholder skeleton (`<...>`) never counts as a written deliverable.
    """
    text = value or ""
    spans = re.findall(r"`([^`]+)`", text)
    pool = spans if spans else re.split(r"[\s()（）,，;；]+", text)
    candidates = []
    for candidate in pool:
        token = candidate.strip().strip("`").strip().strip("。；;，,.)）]】")
        if token.startswith("./") or token.startswith(".\\"):
            token = token[2:]
        if not token or token.startswith("<") or token.endswith(">"):
            continue
        if not (re.search(r"[\\/]", token) or re.search(r"\.\w{1,8}$", token)):
            continue
        candidates.append(token)
    return candidates


def _deliverable_on_disk(root, candidate):
    try:
        path = Path(candidate)
        if path.is_absolute():
            return path.exists()
        return (root / candidate).exists()
    except (OSError, ValueError):
        return False


def _assault_blocked_outcome(text):
    """True when the report records a blocked outcome with 原因/影响/替代."""
    def complete(segment):
        if not ASSAULT_BLOCKED.search(segment):
            return False
        return all(pattern.search(segment) for _label, pattern in ASSAULT_BLOCKED_REASON_ALTERNATES)

    if complete(section_text(text, "routes")):
        return True
    for title in ("layers", "functions"):
        for _line_number, cells in _iter_table_rows(section_text(text, title)):
            if _is_markdown_separator_row(cells):
                continue
            if complete(" ".join(cells)):
                return True
    return False


def parse_assault(root, issues):
    """Parse assault.md against skills/templates/assault.md, then audit the rolling report.

    Returns None when the file is absent: a non-assault case must produce exactly
    the same report as before this audit existed. When present, four checks run
    (GOAL-PROMPT-ASSAULT 阶段4 + assault-entry.md four-state machine):
      1. the state line is filled and current_state is one of SURVEY/ROUTE/EXECUTE/VERIFY;
      2. every layers row carries a status + evidence; a blocked row records 原因/影响/替代;
      3. every function row carries route + state, and no state outruns its evidence
         (a completed row needs its diff row whose verdict asserts 一致);
      4. every unknowns item carries 影响/下一步/是否阻塞; and the completion form
         holds: the deliverable product exists on disk, or the report records a
         blocked outcome with cause/impact/fallback.
    """
    path = root / "assault.md"
    if not path.is_file():
        return None

    text = path.read_text(encoding="utf-8-sig")
    result = {
        "present": True,
        "path": "assault.md",
        "state": "",
        "layers": {},      # L# -> {"status":..., "evidence":..., "line":...}
        "functions": {},   # F-xxx -> {"state":..., "evidence":..., "note":..., "line":...}
        "diff_rows": [],   # {"id":..., "cells":[...], "line":...}
        "unknowns": {},    # U-xxx -> {"cells":[...], "line":...}
        "deliverable": "",
        "deliverable_present": False,
    }

    # --- check 1: state line ---
    state_section = section_text(text, "0 状态行")
    current_state = field_value(state_section, "current_state").strip().strip("`").strip()
    if not state_section or not current_state:
        issue(issues, "error", "assault.state_line_missing",
              "assault.md has no filled ## 0 状态行 / current_state (the report must say where it stands)",
              "assault.md")
    elif current_state.upper() not in ASSAULT_STATES:
        issue(issues, "error", "assault.state_line_invalid",
              "current_state is not one of SURVEY/ROUTE/EXECUTE/VERIFY: " + current_state,
              "assault.md")
    else:
        result["state"] = current_state.upper()

    # --- check 2: layers rows carry status + evidence; blocked rows carry reasons ---
    layers_section = section_text(text, "layers")
    for line_number, cells in _iter_table_rows(layers_section):
        if _is_markdown_separator_row(cells):
            continue
        if not cells or not ASSAULT_LAYER_ID.fullmatch(cells[0]):
            continue
        status = cells[2] if len(cells) > 2 else ""
        evidence = cells[3] if len(cells) > 3 else ""
        result["layers"][cells[0]] = {"status": status, "evidence": evidence, "line": line_number}
        if not status or not evidence:
            issue(issues, "error", "assault.layer_evidence_missing",
                  cells[0] + " layer row needs a status and an evidence cell",
                  "assault.md:" + str(line_number))
        row_text = " ".join(cells)
        if ASSAULT_BLOCKED.search(row_text):
            missing = [label for label, pattern in ASSAULT_BLOCKED_REASON_ALTERNATES
                       if not pattern.search(row_text)]
            if missing:
                issue(issues, "error", "assault.blocked_reason_missing",
                      cells[0] + " is blocked without " + "/".join(missing) + " (record 原因/影响/替代)",
                      "assault.md:" + str(line_number))

    # --- check 3a: functions rows carry route + state ---
    functions_section = section_text(text, "functions")
    function_lines = {}
    for line_number, cells in _iter_table_rows(functions_section):
        if _is_markdown_separator_row(cells):
            continue
        if not cells or not FUNCTION_ID.fullmatch(cells[0]):
            continue
        if len(cells) < 6:
            issue(issues, "error", "assault.function_columns",
                  cells[0] + " row needs at least 6 columns 名称/所属层/路线/状态/证据",
                  "assault.md:" + str(line_number))
            continue
        function_lines[cells[0]] = line_number
        missing = [name for name, value in zip(("名称", "所属层", "路线", "状态"), cells[1:5]) if not value]
        if missing:
            issue(issues, "error", "assault.function_field_missing",
                  cells[0] + " is missing " + "/".join(missing), "assault.md:" + str(line_number))
        state = REBUILD_STATE_ALIASES.get(cells[4].strip())
        if state is None:
            issue(issues, "error", "assault.function_state_invalid",
                  cells[0] + " has unsupported state: " + (cells[4].strip() or "(empty)") +
                  " (allowed: " + "/".join(REBUILD_STATE_LABELS[key] for key in REBUILD_STATE_ORDER) + ")",
                  "assault.md:" + str(line_number))
            continue
        result["functions"][cells[0]] = {
            "state": state,
            "evidence": cells[5].strip() if len(cells) > 5 else "",
            "note": cells[6].strip() if len(cells) > 6 else "",
            "line": line_number,
        }

    if not function_lines:
        issue(issues, "error", "assault.functions_empty",
              "assault.md has no F-xxx function rows (the functions table is the EXECUTE ledger)",
              "assault.md")

    # --- check 3b: a row's state may not be higher than its evidence supports ---
    for function_id, record in sorted(result["functions"].items()):
        state = record["state"]
        if state == "limited":
            if not record["note"]:
                issue(issues, "error", "assault.limited_note_missing",
                      function_id + " is 受限 without a note (record 原因/影响/替代方案)",
                      "assault.md:" + str(record["line"]))
            continue
        if record["evidence"]:
            continue
        if state in REBUILD_COMPLETED_STATES:
            issue(issues, "error", "assault.state_exceeds_evidence",
                  function_id + " is marked " + REBUILD_STATE_LABELS[state] +
                  " with an empty evidence column; fill the evidence (E-xxx or a diff/ record) first",
                  "assault.md:" + str(record["line"]))
        else:
            issue(issues, "warning", "assault.evidence_pending",
                  function_id + " is " + REBUILD_STATE_LABELS[state] +
                  " without evidence yet; fill the evidence column before moving it up the ladder",
                  "assault.md:" + str(record["line"]))

    # --- check 3c: diff_baseline rows keep their five columns ---
    diff_section = section_text(text, "diff_baseline")
    for line_number, cells in _iter_table_rows(diff_section):
        if _is_markdown_separator_row(cells):
            continue
        if not cells or not FUNCTION_ID.fullmatch(cells[0]):
            continue
        result["diff_rows"].append({"id": cells[0], "cells": cells, "line": line_number})
        body = cells[1:6]
        if len(body) < 5:
            issue(issues, "error", "assault.diff_columns",
                  cells[0] + " diff_baseline row needs 5 columns 输入条件/原程序结果/新实现结果/是否一致/说明",
                  "assault.md:" + str(line_number))
            continue
        empty = [name for name, value in zip(REBUILD_DIFF_COLUMNS, body) if not value]
        if empty:
            issue(issues, "error", "assault.diff_incomplete",
                  cells[0] + " diff_baseline row leaves column(s) empty: " + "/".join(empty),
                  "assault.md:" + str(line_number))

    # --- check 3d: completed rows need a matching diff row whose verdict asserts 一致 ---
    diff_by_id = {row["id"]: row for row in result["diff_rows"]}
    for function_id, record in sorted(result["functions"].items()):
        if record["state"] not in REBUILD_COMPLETED_STATES:
            continue
        row = diff_by_id.get(function_id)
        if row is None:
            issue(issues, "error", "assault.diff_row_missing",
                  function_id + " is marked " + REBUILD_STATE_LABELS[record["state"]] +
                  " but has no diff_baseline row (same-input comparison is the completion evidence)",
                  "assault.md:" + str(record["line"]))
            continue
        verdict = row["cells"][4] if len(row["cells"]) > 4 else ""
        if REBUILD_NEGATIVE_VERDICT.search(verdict):
            issue(issues, "error", "assault.diff_verdict_conflict",
                  function_id + " is marked " + REBUILD_STATE_LABELS[record["state"]] +
                  " but its diff row verdict reads: " + verdict,
                  "assault.md:" + str(row["line"]))
        elif not REBUILD_POSITIVE_VERDICT.search(verdict):
            issue(issues, "error", "assault.diff_verdict_unproven",
                  function_id + " is marked " + REBUILD_STATE_LABELS[record["state"]] +
                  " but its diff row verdict does not assert 一致 (reads: " +
                  (verdict or "(empty)") + ")",
                  "assault.md:" + str(row["line"]))

    # --- check 3e: evidence that names a local diff record must exist ---
    for function_id, record in sorted(result["functions"].items()):
        token = (record["evidence"] or "").strip()
        if not token:
            continue
        for relative in _diff_record_refs(token):
            absolute = root / relative
            if not absolute.is_file():
                issue(issues, "error", "assault.diff_record_missing",
                      function_id + " cites a comparison record that does not exist: " + relative,
                      "assault.md:" + str(record["line"]))

    # --- check 3f: a completed row's cited record must not contradict its claim ---
    # 与 rebuild 审计同一把尺子（复用既有判据）：记录里的两段原始 stdout 逐字节比较，
    # 表格自称「一致」不作数；命令没跑起来的记录（exit=ERROR/TIMEOUT）不支撑完成态。
    # 老格式记录（缺原始块）只记 warning：迁移窗口，重跑 diff-runner 即补齐。
    for function_id, record in sorted(result["functions"].items()):
        if record["state"] not in REBUILD_COMPLETED_STATES:
            continue
        for relative in dict.fromkeys(_diff_record_refs(record["evidence"] or "")):
            absolute = root / relative
            if not absolute.is_file():
                continue  # check 3e already reported the missing record
            try:
                record_bytes = absolute.read_bytes()
            except OSError:
                continue
            pairs = list(_stdout_blocks(record_bytes))
            if not pairs:
                issue(issues, "warning", "assault.diff_unparsed",
                      function_id + " cites " + relative + " without the two raw stdout blocks; "
                      "re-run diff-runner to add them (byte comparison applies only to records that carry them)",
                      relative)
                continue
            if any(baseline != rebuilt for baseline, rebuilt in pairs):
                issue(issues, "error", "assault.diff_bytes_mismatch",
                      function_id + " is marked " + REBUILD_STATE_LABELS[record["state"]] +
                      " but its cited record shows differing stdout for the two programs: " + relative,
                      relative)
            gap = _record_reproducibility_gap(record_bytes)
            if gap:
                level, reason = gap
                if level == "error":
                    issue(issues, "error", "assault.diff_unreproducible",
                          function_id + " cites " + relative + ": " + reason +
                          " (a completion claim needs runs that actually happened)",
                          relative)
                else:
                    issue(issues, "warning", "assault.diff_unparsed",
                          function_id + " cites " + relative + " without registered commands/run lines: " + reason +
                          " (re-run diff-runner to register them; the migration window treats this as a warning)",
                          relative)

    # --- check 4a: unknowns items carry 影响/下一步/是否阻塞 ---
    unknowns_section = section_text(text, "unknowns")
    for line_number, cells in _iter_table_rows(unknowns_section):
        if _is_markdown_separator_row(cells):
            continue
        if not cells or not ASSAULT_UNKNOWN_ID.fullmatch(cells[0]):
            continue
        result["unknowns"][cells[0]] = {"cells": cells, "line": line_number}
        if len(cells) < 6:
            issue(issues, "error", "assault.unknown_columns",
                  cells[0] + " row needs 6 columns 问题/影响功能/已尝试/下一步/是否阻塞",
                  "assault.md:" + str(line_number))
            continue
        missing = [name for name, value in
                   zip(("影响功能", "下一步", "是否阻塞"), (cells[2], cells[4], cells[5])) if not value]
        if missing:
            issue(issues, "error", "assault.unknown_field_missing",
                  cells[0] + " is missing " + "/".join(missing), "assault.md:" + str(line_number))

    # --- check 4b: completion form — deliverable on disk, or blocked with reasons ---
    target_section = section_text(text, "target")
    deliverable = field_value(target_section, "deliverable")
    result["deliverable"] = deliverable
    candidates = _deliverable_candidates(deliverable)
    if not candidates:
        issue(issues, "error", "assault.deliverable_unfilled",
              "assault.md deliverable does not name a path (write the final artifact path, not prose)",
              "assault.md")
    else:
        present = any(_deliverable_on_disk(root, candidate) for candidate in candidates)
        result["deliverable_present"] = present
        if not present and not _assault_blocked_outcome(text):
            issue(issues, "error", "assault.deliverable_missing",
                  "assault.md deliverable does not exist on disk and no blocked form "
                  "(原因/影响/替代) is recorded: " + candidates[0],
                  "assault.md")

    return result


def parse_workitems(root, issues):
    path = root / "workitems.md"
    records = {}
    references = []
    if not path.is_file():
        issue(issues, "error", "workitems.missing", "workitems.md is missing", "workitems.md")
        return records, references

    for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        cells = split_table_row(line)
        if len(cells) < 8 or not WORKITEM_ID.fullmatch(cells[0]):
            continue
        workitem_id = cells[0]
        status = cells[5].lower()
        if status not in WORKITEM_STATUSES:
            issue(
                issues,
                "error",
                "workitem.status",
                "unsupported work item status: " + status,
                "workitems.md:" + str(line_number),
            )
        evidence_ids = ids_in(cells[6], EVIDENCE_ID)
        records[workitem_id] = {"status": status, "evidence_ids": evidence_ids}
        references.extend((evidence_id, "workitems.md:" + str(line_number)) for evidence_id in evidence_ids)

    if not records:
        issue(issues, "warning", "workitems.empty", "no work item rows were found", "workitems.md")
    return records, references

def parse_timeline(root, issues):
    path = root / "timeline.md"
    references = []
    events = 0
    if not path.is_file():
        issue(issues, "error", "timeline.missing", "timeline.md is missing", "timeline.md")
        return events, references

    lines = path.read_text(encoding="utf-8-sig").splitlines()
    for index, line in enumerate(lines):
        if not line.startswith("## ") or "|" not in line:
            continue
        events += 1
        end = len(lines)
        for next_index in range(index + 1, len(lines)):
            if lines[next_index].startswith("## "):
                end = next_index
                break
        body = "\n".join(lines[index:end])
        evidence_ids = ids_in(field_value(body, "evidence_ids"), EVIDENCE_ID)
        references.extend((evidence_id, "timeline.md:" + str(index + 1)) for evidence_id in evidence_ids)

    if events == 0:
        issue(issues, "warning", "timeline.empty", "no append-only timeline events were found", "timeline.md")
    return events, references

def parse_scope(root, issues, strict):
    path = root / "scope.md"
    result = {"auth_status": "", "network_mode": "", "ready_for_act": "", "assets": []}
    if not path.is_file():
        issue(issues, "error", "scope.missing", "scope.md is missing", "scope.md")
        return result

    text = path.read_text(encoding="utf-8-sig")
    auth = section_text(text, "auth")
    scope_section = section_text(text, "in_scope")
    network = section_text(text, "network_profile")
    signoff = section_text(text, "signoff")
    result["auth_status"] = field_value(auth, "status").lower()
    result["network_mode"] = field_value(network, "mode").lower()
    result["ready_for_act"] = field_value(signoff, "ready_for_act").lower()

    # Only a top-level "- field:" ends the assets block. Indented Windows
    # paths such as "  - D:\\repo" contain a colon but are asset values.
    assets_match = re.search(r"(?ms)^\s*-\s+assets:\s*\n(?P<body>.*?)(?=^-\s+[A-Za-z0-9_]+:|\Z)", scope_section)
    if assets_match:
        result["assets"] = [
            line.strip()[2:].strip()
            for line in assets_match.group("body").splitlines()
            if re.match(r"^\s+-\s+\S+", line) and line.strip()[2:].strip() != "[]"
        ]

    if not result["auth_status"]:
        issue(issues, "error", "scope.auth_missing", "auth.status is missing", "scope.md")
    elif result["auth_status"] not in {"pending", "granted", "denied", "unknown"}:
        issue(issues, "error", "scope.auth_invalid", "unsupported auth.status: " + result["auth_status"], "scope.md")

    if not result["network_mode"]:
        issue(issues, "error", "scope.network_missing", "network_profile.mode is missing", "scope.md")
    elif result["network_mode"] not in NETWORK_MODES:
        issue(issues, "error", "scope.network_invalid", "unsupported network mode: " + result["network_mode"], "scope.md")

    if not result["ready_for_act"]:
        issue(issues, "error", "scope.ready_missing", "signoff.ready_for_act is missing", "scope.md")
    elif result["ready_for_act"] not in {"true", "false"}:
        issue(issues, "error", "scope.ready_invalid", "ready_for_act must be true or false", "scope.md")

    if result["network_mode"] != "offline" and not result["assets"]:
        issue(issues, "error", "scope.assets_missing", "in_scope.assets is empty for a network case", "scope.md")

    if result["auth_status"] != "granted" or result["ready_for_act"] != "true":
        message = "scope is not ready for target ACT"
        if strict and result["network_mode"] != "offline":
            issue(issues, "error", "scope.not_ready", message, "scope.md")
        else:
            issue(issues, "warning", "scope.not_ready", message, "scope.md")
    return result

def report_sections(text, heading_pattern):
    matches = list(heading_pattern.finditer(text))
    sections = []
    for index, match in enumerate(matches):
        end = len(text)
        for next_match in re.finditer(r"(?m)^#{1,3}\s+", text[match.end():]):
            end = match.end() + next_match.start()
            break
        sections.append((match.group(1), text[match.start():end]))
    return sections

def parse_reports(root, issues):
    finding_records = []
    path_records = []
    references = []
    report_root = root / "report"
    report_files = sorted(report_root.rglob("*.md")) if report_root.is_dir() else []
    if not report_files:
        issue(issues, "warning", "report.missing", "no Markdown report was found", "report")
        return finding_records, path_records, references

    for report_path in report_files:
        text = report_path.read_text(encoding="utf-8-sig")
        for finding_id, body in report_sections(text, FINDING_HEADING):
            status = field_value(body, "status").lower()
            confidence = field_value(body, "confidence").lower()
            evidence_ids = ids_in(field_value(body, "evidence_ids"), EVIDENCE_ID)
            required = ("severity", "evidence_ids", "confidence", "location", "status")
            for field in required:
                if not field_value(body, field):
                    issue(issues, "error", "finding.field_missing", finding_id + " is missing " + field, relative_path(root, report_path))
            if status not in {"candidate", "validated", "false_positive", "accepted_risk", "superseded"}:
                issue(issues, "error", "finding.status", finding_id + " has unsupported status", relative_path(root, report_path))
            if status == "validated" and confidence == "low":
                issue(issues, "error", "finding.confidence", finding_id + " is validated with low confidence", relative_path(root, report_path))
            if not evidence_ids:
                issue(issues, "error", "finding.evidence_missing", finding_id + " has no evidence_ids", relative_path(root, report_path))
            references.extend((evidence_id, relative_path(root, report_path)) for evidence_id in evidence_ids)
            finding_records.append({"id": finding_id, "status": status, "evidence_ids": evidence_ids, "path": relative_path(root, report_path)})

        for path_id, body in report_sections(text, PATH_HEADING):
            path_type = field_value(body, "path_type").lower()
            evidence_ids = ids_in(body, EVIDENCE_ID)
            if path_type not in PATH_TYPES:
                issue(issues, "error", "path.type", path_id + " has unsupported path_type", relative_path(root, report_path))
            if not evidence_ids:
                issue(issues, "error", "path.evidence_missing", path_id + " has no evidence reference", relative_path(root, report_path))
            references.extend((evidence_id, relative_path(root, report_path)) for evidence_id in evidence_ids)
            path_records.append({"id": path_id, "path_type": path_type, "evidence_ids": evidence_ids, "path": relative_path(root, report_path)})
    return finding_records, path_records, references

def normalize_hash(value):
    normalized = value.strip().lower()
    if normalized.startswith("sha256:"):
        normalized = normalized[7:]
    if re.fullmatch(r"[0-9a-f]{64}", normalized):
        return normalized
    return ""

def is_within(root, path):
    try:
        return os.path.commonpath([str(root), str(path)]) == str(root)
    except ValueError:
        return False

def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def verify_artifact(root, artifact_path, expected_hash, issues, display_path):
    if not artifact_path:
        issue(issues, "warning", "artifact.path_missing", "content_hash is recorded without artifact_path", display_path)
        return
    candidate = Path(artifact_path)
    if not candidate.is_absolute():
        candidate = root / candidate
    candidate = candidate.resolve()
    if not is_within(root.resolve(), candidate):
        issue(issues, "warning", "artifact.outside_case", "artifact_path points outside the case root", display_path)
        return
    if not candidate.is_file():
        issue(issues, "error", "artifact.missing", "artifact_path does not exist", display_path)
        return
    digest = sha256_file(candidate)
    if digest != expected_hash:
        issue(issues, "error", "artifact.hash_mismatch", "artifact SHA-256 does not match content_hash", display_path)

def parse_evidence(root, workitems, issues, verify_hashes):
    evidence_root = root / "evidence"
    records = {}
    references = []
    if not evidence_root.is_dir():
        issue(issues, "error", "evidence.dir_missing", "evidence directory is missing", "evidence")
        return records, references

    evidence_files = sorted(path for path in evidence_root.glob("E-*.md") if path.name != "INDEX.md")
    if not evidence_files:
        issue(issues, "warning", "evidence.empty", "no Evidence records were found", "evidence")

    for path in evidence_files:
        evidence_id = path.stem
        text = path.read_text(encoding="utf-8-sig")
        heading = EVIDENCE_HEADING.search(text)
        if not heading:
            issue(issues, "error", "evidence.heading_missing", "Evidence record has no matching heading", relative_path(root, path))
        elif heading.group(1) != evidence_id:
            issue(issues, "error", "evidence.heading_mismatch", "Evidence heading does not match its filename", relative_path(root, path))

        severity = field_value(text, "severity").lower()
        status = field_value(text, "status").lower()
        if status.startswith("superseded by"):
            status = "superseded"
        repro_command = field_value(text, "repro_command")
        notes = field_value(text, "notes").lower()
        linked_workitems = ids_in(field_value(text, "linked_workitem"), WORKITEM_ID)
        content_hash_value = field_value(text, "content_hash")
        artifact_path = field_value(text, "artifact_path")
        if severity not in SEVERITIES:
            issue(issues, "error", "evidence.severity", "unsupported severity: " + severity, relative_path(root, path))
        if status not in EVIDENCE_STATUSES:
            issue(issues, "error", "evidence.status", "unsupported status: " + status, relative_path(root, path))
        offline_note = any(marker in notes for marker in ("offline", "离线", "not applicable"))
        if not repro_command or (repro_command.lower() in {"n/a", "n/a_re"} and not offline_note):
            issue(issues, "error", "evidence.repro_missing", "Evidence requires a reproducible command or documented offline limitation", relative_path(root, path))
        expected_hash = normalize_hash(content_hash_value) if content_hash_value.lower() != "n/a" else ""
        if content_hash_value.lower() != "n/a" and not expected_hash:
            issue(issues, "error", "evidence.hash_invalid", "content_hash must be SHA-256", relative_path(root, path))
        if verify_hashes and expected_hash:
            verify_artifact(root, artifact_path, expected_hash, issues, relative_path(root, path))
        for workitem_id in linked_workitems:
            if workitem_id not in workitems:
                issue(issues, "error", "evidence.workitem_missing", "linked work item does not exist: " + workitem_id, relative_path(root, path))
        records[evidence_id] = {"severity": severity, "status": status, "artifact_path": artifact_path}

    return records, references

def build_traceability(evidence_ids, references):
    graph = {evidence_id: {"workitems": 0, "timeline": 0, "reports": 0} for evidence_id in sorted(evidence_ids)}
    for evidence_id, source in references:
        if evidence_id not in graph:
            continue
        if source.startswith("workitems.md:"):
            graph[evidence_id]["workitems"] += 1
        elif source.startswith("timeline.md:"):
            graph[evidence_id]["timeline"] += 1
        else:
            graph[evidence_id]["reports"] += 1
    return graph

def review_case(case_root, strict=False, verify_hashes=False):
    root = Path(case_root).expanduser().resolve()
    issues = []
    if not root.is_dir():
        issue(issues, "error", "case.missing", "case root does not exist", str(root))
        return {
            "status": "FAIL",
            "case_root": str(root),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": {"errors": 1, "warnings": 0, "evidence": 0, "workitems": 0, "timeline_events": 0, "findings": 0, "paths": 0},
            "issues": issues,
            "traceability": {},
        }

    workitems, workitem_refs = parse_workitems(root, issues)
    timeline_events, timeline_refs = parse_timeline(root, issues)
    scope = parse_scope(root, issues, strict)
    evidence, evidence_refs = parse_evidence(root, workitems, issues, verify_hashes)
    findings, paths, report_refs = parse_reports(root, issues)
    references = workitem_refs + timeline_refs + evidence_refs + report_refs

    # Rebuild delivery audit: only for cases that actually carry rebuild.md.
    # A case without it keeps byte-identical output (the function returns None
    # before touching any issue list).
    rebuild = parse_rebuild(root, issues)

    # Update follow-up audit: only for cases that actually carry update.md.
    # Same discipline: no update.md -> no new key, no new issues.
    update = parse_update(root, issues, rebuild)

    # Assault rolling-report audit: only for cases that actually carry assault.md.
    # Same discipline: no assault.md -> no new key, no new issues.
    assault = parse_assault(root, issues)

    for evidence_id, source in references:
        if evidence_id not in evidence:
            issue(issues, "error", "reference.unknown_evidence", "reference points to missing Evidence: " + evidence_id, source)

    traceability = build_traceability(evidence, references)
    for evidence_id, links in traceability.items():
        if not any(links.values()):
            issue(issues, "warning", "evidence.unlinked", "Evidence is not referenced by a work item, timeline, or report", "evidence/" + evidence_id + ".md")

    errors = sum(1 for item in issues if item["level"] == "error")
    warnings = sum(1 for item in issues if item["level"] == "warning")
    status = "FAIL" if errors or (strict and warnings) else "WARN" if warnings else "PASS"
    report = {
        "status": status,
        "case_root": str(root),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": scope,
        "summary": {
            "errors": errors,
            "warnings": warnings,
            "evidence": len(evidence),
            "workitems": len(workitems),
            "timeline_events": timeline_events,
            "findings": len(findings),
            "paths": len(paths),
        },
        "issues": issues,
        "traceability": traceability,
    }
    # Only a rebuild case grows a new key; a plain case serializes exactly as before.
    if rebuild is not None:
        report["rebuild"] = rebuild
    # Same for the update follow-up: the key appears only when update.md exists.
    if update is not None:
        report["update"] = update
    # Same for the assault rolling report: key appears only when assault.md exists.
    if assault is not None:
        report["assault"] = assault
    return report

def render_markdown(report):
    summary = report["summary"]
    lines = [
        "# Case review",
        "",
        "- status: " + report["status"],
        "- case_root: " + report["case_root"],
        "- generated_at: " + report["generated_at"],
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|---|---:|",
    ]
    for key in ("errors", "warnings", "evidence", "workitems", "timeline_events", "findings", "paths"):
        lines.append("| " + key + " | " + str(summary[key]) + " |")

    lines.extend(["", "## Checks", "", "| Level | Code | Location | Detail |", "|---|---|---|---|"])
    if report["issues"]:
        for item in report["issues"]:
            location = item["path"].replace("|", "\\|")
            detail = item["message"].replace("|", "\\|")
            lines.append("| " + item["level"] + " | " + item["code"] + " | " + location + " | " + detail + " |")
    else:
        lines.append("| pass | none | n/a | No review issues found |")

    lines.extend(["", "## Traceability", "", "| Evidence | Work items | Timeline | Reports |", "|---|---:|---:|---:|"])
    if report["traceability"]:
        for evidence_id, links in report["traceability"].items():
            lines.append(
                "| " + evidence_id + " | " + str(links["workitems"]) + " | " + str(links["timeline"]) + " | " + str(links["reports"]) + " |"
            )
    else:
        lines.append("| n/a | 0 | 0 | 0 |")

    # Rebuild delivery table appears only for cases that carry rebuild.md.
    # A plain case produces exactly the Markdown it produced before this audit.
    rebuild = report.get("rebuild")
    if rebuild:
        lines.extend(["", "## Rebuild delivery", "",
                      "| Function | State | Evidence | Note |", "|---|---|---|---|"])
        if rebuild["functions"]:
            for function_id, record in sorted(rebuild["functions"].items()):
                lines.append("| " + function_id + " | " + REBUILD_STATE_LABELS[record["state"]] +
                             " | " + (record["evidence"] or "").replace("|", "\\|") +
                             " | " + (record["note"] or "").replace("|", "\\|") + " |")
        else:
            lines.append("| n/a | | | no function rows |")
        lines.extend(["", "| Coverage item | Present | Checked |", "|---|---|---|"])
        for key, label, _pattern in REBUILD_COVERAGE_ITEMS:
            found, checked = rebuild["coverage"].get(key, (False, False))
            lines.append("| " + label + " | " + ("yes" if found else "no") +
                         " | " + ("yes" if checked else "no") + " |")

    # Update follow-up table appears only for cases that carry update.md.
    # A case without update.md produces exactly the Markdown it produced before.
    update = report.get("update")
    if update:
        lines.extend(["", "## Update follow-up", "",
                      "| Fingerprint | Hash present |", "|---|---|"])
        for field in UPDATE_FINGERPRINT_FIELDS:
            lines.append("| " + field + " | " +
                         ("yes" if update["fingerprints"].get(field) else "no") + " |")
        lines.extend(["", "| Three line | Present |", "|---|---|"])
        for field in UPDATE_THREE_LINE_FIELDS:
            lines.append("| " + field + " | " +
                         ("yes" if update["three_lines"].get(field) else "no") + " |")
        lines.extend(["", "| Function | Action |", "|---|---|"])
        if update["delta_rows"]:
            for row in update["delta_rows"]:
                lines.append("| " + row["id"] + " | " + (row["action"] or "(empty)") + " |")
        else:
            lines.append("| n/a | no function_delta rows |")

    # Assault rolling-report table appears only for cases that carry assault.md.
    # A case without assault.md produces exactly the Markdown it produced before.
    assault = report.get("assault")
    if assault:
        lines.extend(["", "## Assault report", "",
                      "- current_state: " + (assault["state"] or "(not set)"),
                      "- deliverable: " + (assault["deliverable"] or "(not set)"),
                      "- deliverable_present: " + ("yes" if assault["deliverable_present"] else "no"), ""])
        lines.extend(["| Layer | Status | Evidence |", "|---|---|---|"])
        if assault["layers"]:
            for layer_id, record in sorted(assault["layers"].items()):
                lines.append("| " + layer_id + " | " + record["status"].replace("|", "\\|") +
                             " | " + record["evidence"].replace("|", "\\|") + " |")
        else:
            lines.append("| n/a | | no layer rows |")
        lines.extend(["", "| Function | State | Evidence |", "|---|---|---|"])
        if assault["functions"]:
            for function_id, record in sorted(assault["functions"].items()):
                lines.append("| " + function_id + " | " + REBUILD_STATE_LABELS[record["state"]] +
                             " | " + (record["evidence"] or "").replace("|", "\\|") + " |")
        else:
            lines.append("| n/a | | no function rows |")
        lines.extend(["", "| Unknown | Blocking |", "|---|---|"])
        if assault["unknowns"]:
            for unknown_id, record in sorted(assault["unknowns"].items()):
                blocking = record["cells"][5] if len(record["cells"]) > 5 else ""
                lines.append("| " + unknown_id + " | " + blocking.replace("|", "\\|") + " |")
        else:
            lines.append("| n/a | no unknown rows |")
    return "\n".join(lines) + "\n"

def main(argv=None):
    parser = argparse.ArgumentParser(description="Review a reverse-skill case for scope and Evidence graph integrity")
    parser.add_argument("case_root", help="Path to a work/<case> directory")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as a failed review")
    parser.add_argument("--verify-hashes", action="store_true", help="Verify SHA-256 content_hash values against artifact_path")
    args = parser.parse_args(argv)
    report = review_case(args.case_root, strict=args.strict, verify_hashes=args.verify_hashes)
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(report), end="")
    return 1 if report["status"] == "FAIL" else 0

if __name__ == "__main__":
    sys.exit(main())
