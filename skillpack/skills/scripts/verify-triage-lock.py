#!/usr/bin/env python3
"""Lock the link-triage registry to a digest that lives in its own file.

The hole this closes
--------------------
`skills/scripts/verify-doc-links.py` treats `docs/community/link-triage.json` as
the authority that turns a broken provenance link into a *registered* one. If the
registry is the only thing that decides, then whoever can write the registry can
exempt any link -- including links that never existed upstream.

That is not hypothetical. An adversarial test
(`work/gate-selfexempt-test.py`) appended a link that has never existed upstream
to `docs/community/ctf-super-hub/README.md`, registered it as
`upstream_layout_unmappable`, and the gate returned **exit 0**:

    unregistered  -> exit 1  "1 provenance broken link(s) without a registry entry"
    registered    -> exit 0  "all 14 provenance break(s) registered"

The digest lock makes that change visible instead of silent: the registry and the
lock are separate files, so exempting a new link means editing two files, and the
lock records the exact entry count and content digest it was reviewed with. The
full fix still needs a protected review path (spec 17.21 / T24 CODEOWNERS);
this script provides the machine-checkable half.

What it verifies
----------------
1. `docs/community/link-triage.lock.json` exists and is valid JSON.
2. The canonical digest of `docs/community/link-triage.json` matches the lock.
3. The entry count matches the lock.
4. The lock records the spec/checker contract it was made against.
5. When the read-only upstream snapshots are present, every entry claiming
   `upstream_layout_unmappable` must point at a file that really exists there.
   The snapshot location is explicit: `--snapshot-root <dir>` wins, otherwise
   the legacy default `../upstream` (sibling of the repository root) is used.
   When neither exists this degrades to ONE named exit-10 review item that
   states how many claims were left machine-unchecked and the exact re-run
   command -- a clean clone cannot check it, so this MUST stay exit 10
   (spec 4.7 needs_review): exit 0 would be a fake green, exit 20 would keep
   every snapshot-less CI red forever. A forged registry+lock pair is NOT
   caught in that state (digest and count both match); it is caught the moment
   a snapshot is supplied (exit 20, suspect invented exemption), and in CI it
   is a two-file change gated by the CODEOWNERS review path (spec 17.21).

Read-only. Usage:
    python skills/scripts/verify-triage-lock.py [--snapshot-root <dir>] [--json]
    python skills/scripts/verify-triage-lock.py --snapshot-root <dir> [--write-lock]

`--write-lock` regenerates the lock from the current registry; it is the only
mode that writes, and it is meant for the coordinator after an accepted change.

Exit codes (spec 4.7): 0 ok, 10 needs_review, 20 blocked.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "docs" / "community" / "link-triage.json"
LOCK = ROOT / "docs" / "community" / "link-triage.lock.json"
# Legacy default: the read-only snapshots live OUTSIDE the repository, as a
# sibling directory. `--snapshot-root` overrides this explicitly; when neither
# exists the gate degrades to a named exit-10 item (never silent, never red).
DEFAULT_UPSTREAM = ROOT.parent / "upstream"

LOCK_SCHEMA_VERSION = "1.0"
LOCK_SUBJECT = "docs/community/link-triage.json"

def canonical_bytes(path: Path) -> bytes:
    """Canonical form per spec 17.26: NFC, LF, no BOM, no trailing whitespace drift.

    JSON is re-serialised with sorted keys so formatting churn cannot change the
    digest, but any change to a *value* does.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    text = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    text = unicodedata.normalize("NFC", text).replace("\r\n", "\n").replace("\r", "\n")
    return text.encode("utf-8")

def digest_of(path: Path) -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes(path)).hexdigest()

def upstream_exists(rel: str, snapshot_root: Path) -> bool | None:
    """True/False when the snapshots are available, None when they are not."""
    if not snapshot_root.is_dir():
        return None
    candidate = snapshot_root / rel
    if candidate.exists():
        return True
    return False

def build_lock() -> dict:
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    return {
        "schemaVersion": LOCK_SCHEMA_VERSION,
        "subject": LOCK_SUBJECT,
        "subject_digest": digest_of(REGISTRY),
        "entries_total": len(data.get("entries", [])),
        "counts": data.get("counts", {}),
        "note": (
            "Digest lock for the link-triage registry. Changing the registry "
            "without regenerating this lock fails verify-triage-lock.py. "
            "Regenerate with --write-lock after an accepted change, and require "
            "an independent review for both files (spec 17.21 / T24 CODEOWNERS)."
        ),
    }

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write-lock",
        action="store_true",
        help="regenerate the lock from the current registry (coordinator only)",
    )
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument(
        "--snapshot-root",
        default=None,
        help=(
            "read-only upstream snapshot directory used to machine-verify "
            "upstream_layout_unmappable claims; defaults to ../upstream "
            "(sibling of the repository root). Absent snapshots degrade to "
            "a named exit-10 review item instead of blocking."
        ),
    )
    args = parser.parse_args()

    snapshot_root = Path(args.snapshot_root) if args.snapshot_root else DEFAULT_UPSTREAM
    snapshot_present = snapshot_root.is_dir()

    if not REGISTRY.is_file():
        print(f"FAIL triage registry missing: {REGISTRY.relative_to(ROOT).as_posix()}")
        return 20

    if args.write_lock:
        lock = build_lock()
        LOCK.write_text(
            json.dumps(lock, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(f"lock written: {LOCK.relative_to(ROOT).as_posix()}")
        print(f"  subject_digest = {lock['subject_digest']}")
        print(f"  entries_total  = {lock['entries_total']}")
        return 0

    problems: list[str] = []
    warnings: list[str] = []

    if not LOCK.is_file():
        problems.append(
            f"lock missing: {LOCK.relative_to(ROOT).as_posix()} "
            "(regenerate with --write-lock)"
        )
        lock: dict = {}
    else:
        try:
            lock = json.loads(LOCK.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            problems.append(f"lock is not readable JSON: {exc}")
            lock = {}

    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    entries = registry.get("entries", [])
    actual_digest = digest_of(REGISTRY)

    if lock:
        if lock.get("subject") != LOCK_SUBJECT:
            problems.append(
                f"lock subject mismatch: expected {LOCK_SUBJECT!r}, got {lock.get('subject')!r}"
            )
        if lock.get("subject_digest") != actual_digest:
            problems.append(
                "triage registry digest does not match the lock "
                f"(lock={lock.get('subject_digest')}, actual={actual_digest}); "
                "the registry changed without an accepted review"
            )
        if lock.get("entries_total") != len(entries):
            problems.append(
                f"entry count drift: lock={lock.get('entries_total')}, registry={len(entries)}"
            )
        if lock.get("counts") and lock["counts"] != registry.get("counts", {}):
            problems.append(
                f"counts drift: lock={lock.get('counts')}, registry={registry.get('counts')}"
            )

    # machine-verify the one claim the gate cannot check on its own
    unmappable = [e for e in entries if e.get("disposition") == "upstream_layout_unmappable"]
    checked = 0
    for entry in unmappable:
        rel = entry.get("upstream_path")
        if not rel:
            problems.append(
                f"upstream_layout_unmappable without upstream_path: "
                f"{entry.get('file')}:{entry.get('line')}"
            )
            continue
        rel = rel.replace("upstream/", "", 1) if rel.startswith("upstream/") else rel
        exists = upstream_exists(rel, snapshot_root)
        if exists is None:
            warnings.append(
                "upstream snapshots not present "
                f"(snapshot_root={snapshot_root}, exists=false); "
                f"{len(unmappable) - checked} of {len(unmappable)} "
                "upstream_layout_unmappable claim(s) left machine-unchecked; "
                "re-run with --snapshot-root <dir> pointing at the read-only "
                "upstream snapshots to machine-verify them"
            )
            break
        checked += 1
        if not exists:
            problems.append(
                "upstream_layout_unmappable claims a path absent from the snapshot "
                f"(suspect invented exemption): {entry.get('file')}:{entry.get('line')} "
                f"-> {entry.get('upstream_path')}"
            )

    report = {
        "registry": REGISTRY.relative_to(ROOT).as_posix(),
        "lock": LOCK.relative_to(ROOT).as_posix(),
        "subject_digest": actual_digest,
        "entries_total": len(entries),
        "unmappable_entries": len(unmappable),
        "unmappable_machine_checked": checked,
        "snapshot_root": str(snapshot_root),
        "snapshot_present": snapshot_present,
        "problems": problems,
        "warnings": warnings,
    }
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print("=== triage registry lock ===")
        print(f"registry entries                : {len(entries)}")
        print(f"subject digest                  : {actual_digest}")
        print(f"snapshot root                   : {snapshot_root} "
              f"({'present' if snapshot_present else 'absent'})")
        print(f"upstream_layout_unmappable      : {len(unmappable)} (machine-checked {checked})")
        for p in problems:
            print(f"[BLOCKED] {p}")
        for w in warnings:
            print(f"[REVIEW] {w}")

    if problems:
        print(f"FAIL verify-triage-lock: {len(problems)} defect(s)")
        return 20
    if warnings:
        print(f"NEEDS_REVIEW verify-triage-lock: {len(warnings)} item(s)")
        return 10
    print("PASS verify-triage-lock")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
