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

def parse_rebuild(root, issues):
    """Parse rebuild.md against skills/templates/rebuild.md, then audit the delivery.

    Returns None when the file is absent: a non-rebuild case must produce exactly
    the same report as before this audit existed. When present, three checks run:
      1. a row's state may not be higher than its evidence supports;
      2. every diff_baseline row keeps its five columns;
      3. Coverage carries the three rebuild items.
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
        for candidate in re.findall(r"[A-Za-z0-9_./\\-]*diff[/\\][A-Za-z0-9_.\\/-]+", token):
            relative = candidate.replace("\\", "/").lstrip("/")
            absolute = root / relative
            if not absolute.is_file():
                issue(issues, "error", "rebuild.diff_record_missing",
                      function_id + " cites a comparison record that does not exist: " + relative,
                      "rebuild.md:" + str(record["line"]))

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
