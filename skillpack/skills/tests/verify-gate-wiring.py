#!/usr/bin/env python3
"""Prove that every gate in skills/tests/ci-gates.json is really invoked by CI.

The failure this prevents is not hypothetical. T26 landed three gates
(``verify-routing-signals.py``, ``test-routing-signals.py``,
``test-community-decoys.py``) that passed only when a human typed them: no
workflow, no test script and no runner called them (WORK-BOARD U10). A gate that
nothing invokes is indistinguishable from a gate that is green, and the only way
to tell them apart is to cross-check the manifest against the workflow text.

So this script does exactly that cross-check and nothing else:

1. Every gate id's script must appear in at least one workflow under
   ``.github/workflows/``. A script that appears nowhere is reported as
   ``UNWIRED`` and blocks. This is what would have caught U10 on day one.
2. No workflow may invoke a script under ``community-raw/``,
   ``skills/community/`` or ``docs/community/`` (spec 17.31: CI must not execute
   untrusted vendor code).
3. Every workflow must declare read-only ``permissions`` (spec 17.31), and no
   gate job may reference a secret. ``auto-merge-journal.yml`` is the one
   documented exception: it is not a gate job, it holds ``contents: write`` by
   design, and this script clears it only after finding that workflow's own
   write-scope review record in the write-scope review section of
   ``docs/CI-TRUST-BOUNDARY.md``. A missing document, a missing section, or a
   section that does not name this workflow and its scopes is still reported
   as NEEDS_REVIEW, never waived.
4. Every ``uses:`` in every workflow must be pinned to a full 40-hex commit SHA.
   The repository security gate checks this too; repeating it here means the
   wiring check is self-contained and can be run from a worktree with no git.
5. The manifest itself is pinned to a digest in ``ci-gates.lock.json``. Without
   this, check 1 was self-exempting: deleting a gate from the manifest removes it
   from the "declared" list, so the very gate that is no longer called stops
   complaining about it. That is the same defect class as the self-exempting
   triage registry found on 2026-09-29, and it was measured here, not assumed
   (``tests/community/test-ci-negative-controls.py`` control
   ``gate-removed-from-wiring``).

It is deliberately structural, not behavioural: it reads YAML and JSON as text. It
never executes a workflow, never executes vendor code, and never writes except
under the explicit ``--write-lock`` coordinator flag.

Usage::

    python skills/tests/verify-gate-wiring.py
    python skills/tests/verify-gate-wiring.py --write-lock   # coordinator only

Exit codes: 0 ok, 10 needs_review (documented exception present), 20 blocked.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "skills" / "tests" / "ci-gates.json"
LOCK = ROOT / "skills" / "tests" / "ci-gates.lock.json"


def _repo_root() -> Path:
    """往上找带 `.github/workflows` 的那一层 —— 那才是 CI 真正读工作流的地方。

    早先写死 `ROOT / ".github" / "workflows"`，而 ROOT 是 `skillpack/`：
    技能包曾经是独立仓库、`.github` 就在它自己下面。并进主仓之后 `.github`
    上移到了仓库根，于是这里恒定报「workflows directory missing」——
    闸门自己瞎了，却报成别人的目录缺。两边都试，取真的存在的那个。
    """
    for base in (ROOT, *ROOT.parents):
        if (base / ".github" / "workflows").is_dir():
            return base
    return ROOT


REPO_ROOT = _repo_root()
WORKFLOWS = REPO_ROOT / ".github" / "workflows"

# A gate may be invoked directly, or indirectly: CI runs skills/tests/run-ci-gates.py,
# which reads the manifest and runs each gate itself. So "is this gate wired?" has to
# be answered transitively -- otherwise this file would report the very indirection it
# was written to introduce as a defect. Two hops are resolved, which covers the current
# workflow; a gate wired through a third file is reported rather than assumed.
INDIRECT_RUNNERS = ("skills/tests/run-ci-gates.py",)

FORBIDDEN_SCRIPT_PREFIXES = ("community-raw/", "skills/community/", "docs/community/")
USES_RE = re.compile(r"^\s*(?:-\s*)?uses:\s*(\S+)", re.M)
PERMISSIONS_RE = re.compile(r"^permissions:\s*$", re.M)
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
SECRET_RE = re.compile(r"secrets\.[A-Za-z_][A-Za-z0-9_]*")

def canonical_bytes(path: Path) -> bytes:
    """Canonical form, identical to verify-triage-lock.py: sorted keys, no
    whitespace, NFC, LF. Formatting churn must not move the digest; a change to
    the gate list must."""
    data = json.loads(path.read_text(encoding="utf-8"))
    text = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    text = unicodedata.normalize("NFC", text).replace("\r\n", "\n").replace("\r", "\n")
    return text.encode("utf-8")

def manifest_digest() -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes(MANIFEST)).hexdigest()

def check_manifest_lock(gates: list[dict[str, Any]]) -> tuple[list[str], str, str]:
    """Pin the gate list so deleting a gate cannot silently shrink coverage."""
    actual = manifest_digest()
    if not LOCK.is_file():
        return ([f"gate manifest lock missing: {LOCK.relative_to(ROOT).as_posix()} "
                 "(regenerate with --write-lock after an accepted change)"], actual, "")
    try:
        lock = json.loads(LOCK.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        return ([f"gate manifest lock is not valid JSON: {error}"], actual, "")
    problems: list[str] = []
    if lock.get("subject") != MANIFEST.relative_to(ROOT).as_posix():
        problems.append(f"lock subject mismatch: expected "
                        f"{MANIFEST.relative_to(ROOT).as_posix()!r}, got {lock.get('subject')!r}")
    if lock.get("subject_digest") != actual:
        problems.append(
            "gate manifest digest does not match the lock "
            f"(lock={lock.get('subject_digest')}, actual={actual}); the set of gates CI "
            "runs changed without an accepted review -- deleting a gate here is how a "
            "red build is silenced"
        )
    ids = [g.get("id") for g in gates]
    if lock.get("gates_total") != len(ids):
        problems.append(f"gate count drift: lock={lock.get('gates_total')}, manifest={len(ids)}")
    if lock.get("gate_ids") != ids:
        missing = [i for i in (lock.get("gate_ids") or []) if i not in ids]
        added = [i for i in ids if i not in (lock.get("gate_ids") or [])]
        detail = []
        if missing:
            detail.append(f"removed={missing}")
        if added:
            detail.append(f"added={added}")
        if not detail:  # same set, different order -- still a change worth naming
            detail.append("same ids in a different order")
        problems.append("gate id list drift: " + "; ".join(detail))
    return problems, actual, str(lock.get("subject_digest"))

def build_lock(gates: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schemaVersion": "1.0",
        "subject": MANIFEST.relative_to(ROOT).as_posix(),
        "subject_digest": manifest_digest(),
        "gates_total": len(gates),
        "gate_ids": [g.get("id") for g in gates],
        "note": [
            "Digest lock for the CI gate manifest. verify-gate-wiring.py fails when the",
            "manifest and this file disagree, so a gate cannot be dropped from CI by",
            "editing the manifest alone. Regenerate with --write-lock after an accepted",
            "change and require an independent review of both files (spec 17.21 / T24).",
        ],
    }

def load_manifest() -> tuple[list[dict[str, Any]], list[str]]:
    if not MANIFEST.is_file():
        return [], [f"gate manifest missing: {MANIFEST.relative_to(ROOT).as_posix()}"]
    document = json.loads(MANIFEST.read_text(encoding="utf-8"))
    gates = document.get("gates") or []
    problems: list[str] = []
    if not gates:
        problems.append("gate manifest lists no gates")
    for gate in gates:
        if not gate.get("executes_vendor_code", False) is False:
            problems.append(f"gate {gate.get('id')!r} claims executes_vendor_code=true")
    return gates, problems

def script_pattern(script: str) -> re.Pattern[str]:
    """Match the script whether the workflow spells it with / or \\."""
    return re.compile(re.escape(script).replace(r"\/", r"[\\/]"))

def invokers(texts: dict[str, str], script: str) -> list[str]:
    """Workflows that reach `script`, directly or through a known runner."""
    direct = sorted(name for name, text in texts.items() if script_pattern(script).search(text))
    if direct:
        return direct
    runner = next((r for r in INDIRECT_RUNNERS
                   if (ROOT / r).is_file()
                   and script_pattern(r).search("".join(texts.values()))), None)
    if runner is None:
        return []
    # The runner exists and CI invokes it; it runs every gate in the manifest, but
    # say so honestly rather than trusting that: the runner is stdlib-only code
    # whose manifest is this same file, so a gate absent from the manifest cannot
    # be run by it either.
    return [f"{name} (via {runner})" for name, name_text in texts.items()
            if script_pattern(runner).search(name_text)]

def check_wiring(gates: list[dict[str, Any]], texts: dict[str, str]) -> tuple[list[str], list[str]]:
    blocked: list[str] = []
    review: list[str] = []
    for gate in gates:
        where = invokers(texts, gate["script"])
        if not where:
            blocked.append(
                f"UNWIRED gate {gate['id']!r}: no workflow invokes "
                f"{gate['script']} directly or through {', '.join(INDIRECT_RUNNERS)} "
                "(spec T10 / WORK-BOARD U10 -- a gate nothing calls is "
                "indistinguishable from a green gate)"
            )
        else:
            print(f"  wired  {gate['id']:30} -> {', '.join(where)}")
    return blocked, review

def check_vendor_execution(texts: dict[str, str]) -> list[str]:
    blocked: list[str] = []
    for name, text in texts.items():
        for match in re.finditer(r"^\s*(?:-\s*)?run:\s*(.*)$", text, re.M):
            line = match.group(1)
            for prefix in FORBIDDEN_SCRIPT_PREFIXES:
                if prefix in line.replace("\\", "/"):
                    blocked.append(
                        f"{name}: a step's run: line references vendor code ({prefix}): {line.strip()[:120]}"
                    )
    return blocked

WRITE_PERMISSIONS = {"contents", "pull-requests", "id-token", "packages", "issues",
                     "actions", "deployments", "checks", "statuses", "discussions"}

# Documented exception: this workflow merges field-journal PRs and is not a gate
# job. Spec 17.31 still demands an independent review record for its write scope,
# which lives in docs/CI-TRUST-BOUNDARY.md (owner T24). check_permissions() below
# reads that document and only clears the NEEDS_REVIEW item when the workflow's
# own write-scope record is found there -- the file merely existing is not enough.
NON_GATE_WORKFLOWS = {"auto-merge-journal.yml"}

TRUST_BOUNDARY_DOC = ROOT / "docs" / "CI-TRUST-BOUNDARY.md"

def write_scope_review_section() -> str:
    """The write-scope review section of docs/CI-TRUST-BOUNDARY.md, or "".

    The record for a non-gate workflow's write scope is the section headed by
    the write-scope review heading (it contains "独立审查记录"). Only that
    section counts: a workflow filename mentioned anywhere else in the document
    (a table, a pointer, a changelog line) is not a review record.
    """
    try:
        text = TRUST_BOUNDARY_DOC.read_text(encoding="utf-8")
    except OSError:
        return ""
    lines = text.splitlines(keepends=True)
    start: int | None = None
    for index, line in enumerate(lines):
        if line.startswith("##") and "独立审查记录" in line:
            start = index
            break
    if start is None:
        return ""
    end = len(lines)
    for index in range(start + 1, len(lines)):
        if lines[index].startswith("## "):
            end = index
            break
    return "".join(lines[start:end])

def has_write_scope_review(workflow_name: str, writes: list[str]) -> bool:
    """True only when the review section names this workflow and its scopes.

    Both conditions must hold: the workflow's own file name appears in the
    write-scope review section, and every declared write scope (e.g.
    "contents: write") is named there too. A document that exists but reviews
    some other workflow -- or that names this workflow without its scopes --
    does not clear the item.
    """
    section = write_scope_review_section()
    if not section:
        return False
    normalized = section.replace("\\", "/")
    if workflow_name not in normalized:
        return False
    for item in writes:
        scope = item.split(":")[0].strip()
        if not scope:
            return False
        if not re.search(rf"{re.escape(scope)}\s*:\s*write", normalized):
            return False
    return True

def check_permissions(texts: dict[str, str]) -> tuple[list[str], list[str]]:
    """Gate workflows must default to read-only at the top level (17.31)."""
    blocked: list[str] = []
    review: list[str] = []
    for name, text in texts.items():
        if not PERMISSIONS_RE.search(text):
            if name in NON_GATE_WORKFLOWS:
                job_writes = job_write_scopes(text)
                if job_writes and has_write_scope_review(name, job_writes):
                    print(f"  review-record {name} -> "
                          f"{TRUST_BOUNDARY_DOC.relative_to(ROOT).as_posix()} "
                          f"(write-scope record found for {job_writes})")
                    continue
                review.append(
                    f"{name}: no top-level 'permissions:' block and job scope(s) "
                    f"{job_writes or 'unknown'} grant write. This workflow is not a gate "
                    "job, so the read-only default does not apply to it, but spec 17.31 "
                    "requires an independent review record for the write scope and no "
                    "such record for this workflow was found in "
                    "docs/CI-TRUST-BOUNDARY.md (searched the write-scope review "
                    f"section for {name!r}; owner T24)."
                )
                continue
            blocked.append(
                f"{name}: no top-level 'permissions:' block; spec 17.31 requires "
                "'permissions:\\n  contents: read' as the default for every gate workflow"
            )
            continue
        writes = job_write_scopes(text)
        if writes and name in NON_GATE_WORKFLOWS:
            if has_write_scope_review(name, writes):
                print(f"  review-record {name} -> "
                      f"{TRUST_BOUNDARY_DOC.relative_to(ROOT).as_posix()} "
                      f"(write-scope record found for {writes})")
                continue
            review.append(
                f"{name}: write permission(s) {writes} are declared; this workflow is not "
                "a gate job, but spec 17.31 requires an independent review record for them "
                "and no such record for this workflow was found in "
                "docs/CI-TRUST-BOUNDARY.md (searched the write-scope review "
                f"section for {name!r}; owner T24)."
            )
        elif writes:
            blocked.append(
                f"{name}: gate workflow grants write permission(s) {writes}; "
                "spec 17.31 makes any write scope a blocking finding"
            )
    return blocked, review

def job_write_scopes(text: str) -> list[str]:
    """Every 'name: write' in the file, regardless of how deeply it is nested."""
    found = set()
    for scope in re.findall(r"^\s*([a-z][a-z-]*):\s*write\s*$", text, re.M):
        if scope in WRITE_PERMISSIONS:
            found.add(f"{scope}: write")
    return sorted(found)

def check_secrets(texts: dict[str, str]) -> list[str]:
    blocked: list[str] = []
    for name, text in texts.items():
        if name == "auto-merge-journal.yml":
            continue
        found = sorted(set(SECRET_RE.findall(text)))
        if found:
            blocked.append(f"{name}: gate workflow references secret(s) {found} (spec 17.31)")
    return blocked

def check_action_pins(texts: dict[str, str]) -> list[str]:
    blocked: list[str] = []
    for name, text in texts.items():
        for use in USES_RE.findall(text):
            if use.startswith("./"):
                continue
            if "@" not in use or not FULL_SHA.fullmatch(use.rsplit("@", 1)[1]):
                blocked.append(f"{name}: action not pinned to a full commit SHA: {use}")
    return blocked

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--write-lock", action="store_true",
                        help="regenerate the gate manifest lock (coordinator only)")
    args = parser.parse_args()

    if not WORKFLOWS.is_dir():
        print(f"FAIL workflows directory missing: {WORKFLOWS}")
        return 20

    gates, manifest_problems = load_manifest()

    if args.write_lock:
        if manifest_problems:
            print(f"FAIL verify-gate-wiring: refusing to lock a broken manifest: {manifest_problems}")
            return 20
        lock = build_lock(gates)
        LOCK.write_text(json.dumps(lock, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"lock written: {LOCK.relative_to(ROOT).as_posix()}")
        print(f"  subject_digest = {lock['subject_digest']}")
        print(f"  gates_total    = {lock['gates_total']}")
        return 0

    texts = {p.name: p.read_text(encoding="utf-8") for p in sorted(WORKFLOWS.glob("*.y*ml"))}

    blocked: list[str] = list(manifest_problems)
    review: list[str] = []

    print("=== CI gate wiring verification ===")
    print(f"workflows scanned : {len(texts)} -> {sorted(texts)}")
    print(f"gates declared    : {len(gates)}")

    print("--- the manifest itself is pinned to a digest ---")
    lock_problems, actual_digest, locked_digest = check_manifest_lock(gates)
    print(f"  manifest digest : {actual_digest}")
    print(f"  locked digest   : {locked_digest or '(no lock)'}")
    if lock_problems:
        for item in lock_problems:
            print(f"  [BLOCKED] {item}")
        blocked += lock_problems
    else:
        print("  manifest matches the lock")

    print("--- every declared gate is invoked by a workflow ---")
    wiring_blocked, wiring_review = check_wiring(gates, texts)
    blocked += wiring_blocked
    review += wiring_review

    for label, found in (("vendor execution", check_vendor_execution(texts)),
                         ("gate secrets", check_secrets(texts)),
                         ("action pinning", check_action_pins(texts))):
        print(f"--- {label} ---")
        if found:
            for item in found:
                print(f"  [BLOCKED] {item}")
            blocked += found
        else:
            print("  none")

    print("--- workflow permissions ---")
    perm_blocked, perm_review = check_permissions(texts)
    blocked += perm_blocked
    review += perm_review
    for item in perm_blocked + perm_review:
        print(f"  {'[BLOCKED]' if item in perm_blocked else '[NEEDS_REVIEW]'} {item}")

    if args.json:
        print(json.dumps({"blocked": blocked, "needs_review": review},
                         indent=2, ensure_ascii=False))

    print("=== result ===")
    print(f"blocked={len(blocked)} needs_review={len(review)}")
    for item in blocked:
        print(f"[BLOCKED] {item}")
    for item in review:
        print(f"[NEEDS_REVIEW] {item}")
    if blocked:
        print(f"FAIL verify-gate-wiring: {len(blocked)} blocking defect(s)")
        return 20
    if review:
        print(f"NEEDS_REVIEW verify-gate-wiring: {len(review)} item(s)")
        return 10
    print("PASS verify-gate-wiring: every declared gate is invoked by a workflow")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())