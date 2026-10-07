#!/usr/bin/env python3
"""Verify the community source bundle is portable and self-describing (T12).

A "bundle" is the set of inputs a release or a bare copy needs in order to
re-check provenance without the original machine:

  community-raw/  docs/community/<source-id>/  skills/community/registry.json
  skills/community/source-lock.json  (this lock)

Checks (all offline, all read-only):

  1. input boundary -- every bundle member exists; nothing outside the
     boundary is required for provenance re-checks;
  2. no absolute machine paths in the lock -- `snapshot_rel` must stay
     relative (`upstream/<repo>`); absolute paths would tie the bundle to
     one machine and fail T12 portability;
  3. cache exclusion -- `.gitignore` must cover the importer candidate dir
     (`.candidates/`), python caches and the generated tool index, parsed
     directly from the file so the check also runs with no git;
  4. case/Unicode collisions (17.30, T14) over `community-raw/**` and the
     per-source `docs/community/<id>/` dirs -- a collision blocks;
  5. registry schema + stats (T14) -- `schemaVersion`, the source id set and
     the derived `len(sources)` / `len(excluded)` must equal the lock's
     `registry_expectation`; an old schema, a deprecated/unknown id or a
     count drift blocks (counts are always re-derived from the registry,
     never trusted from the lock alone);
  6. no-git note -- without `.git`, git-dependent claims about the bundle
     itself cannot be machine-checked; that item is named (NEEDS_REVIEW),
     never silently passed -- the same degraded semantics as
     verify-triage-lock.py and the answer to HANDOFF 2.1.

Exit codes (spec 4.7): 0 ok, 10 needs_review, 20 blocked.
Read-only: this script never writes to the repository.

Usage:
    python scripts/verify-community-bundle.py [--root DIR] [--lock REL] [--json]
"""

from __future__ import annotations

import argparse
import json
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve()
DEFAULT_ROOT = HERE.parents[1]

REQUIRED_GITIGNORE_ENTRIES = (".candidates/", "__pycache__/", "`skillpack/skills/TOOLS.md`")

DOCS_BY_SOURCE = {
    "ctf-super-hub": "docs/community/ctf-super-hub",
    "hack-skills": "docs/community/hack-skills",
    "ai-fullstack-delivery": "docs/community/ai-fullstack-delivery",
    "apk-reverse-community": "docs/community/apk-reverse-community",
}

def case_key(rel: str) -> str:
    return unicodedata.normalize("NFC", rel).casefold()

def find_collisions(root: Path) -> list[str]:
    seen: dict[str, str] = {}
    collisions: list[str] = []
    for path in root.rglob("*"):
        try:
            rel = path.relative_to(root).as_posix()
        except ValueError:
            continue
        key = case_key(rel)
        if key in seen and seen[key] != rel:
            collisions.append(f"{seen[key]!r} collides with {rel!r}")
        else:
            seen.setdefault(key, rel)
    return collisions

def gitignore_covers(root: Path, entry: str) -> bool:
    ignore = root / ".gitignore"
    if not ignore.is_file():
        return False
    for line in ignore.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line == entry or line.rstrip("/") == entry.rstrip("/"):
            return True
    return False

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(DEFAULT_ROOT))
    parser.add_argument("--lock", default="skills/community/source-lock.json")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    root = Path(args.root)
    lock_path = root / args.lock
    problems: list[str] = []
    warnings: list[str] = []

    if not lock_path.is_file():
        print(f"FAIL source lock missing: {lock_path}")
        return 20
    try:
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"FAIL source lock is not readable JSON: {exc}")
        return 20

    # 1. input boundary
    members = ["community-raw", "skills/community/registry.json", args.lock]
    for src in lock.get("sources", []):
        docs = DOCS_BY_SOURCE.get(src.get("id", ""))
        if docs:
            members.append(docs)
    for member in members:
        if not (root / member).exists():
            problems.append(f"bundle member missing: {member}")

    # 2. no absolute machine paths in the lock
    for src in lock.get("sources", []):
        rel = str(src.get("snapshot_rel", ""))
        if not rel or Path(rel).is_absolute() or ".." in Path(rel).parts:
            problems.append(
                f"{src.get('id')}: snapshot_rel must be a relative in-bundle path, got {rel!r}")

    # 3. cache exclusion (parsed from the file: works with no git)
    for entry in REQUIRED_GITIGNORE_ENTRIES:
        if not gitignore_covers(root, entry):
            problems.append(f".gitignore does not exclude cache path: {entry}")

    # 4. case/Unicode collisions over the bundle input set
    scan_roots = [root / "community-raw"]
    for src in lock.get("sources", []):
        docs = DOCS_BY_SOURCE.get(src.get("id", ""))
        if docs:
            scan_roots.append(root / docs)
    for scan in scan_roots:
        if not scan.is_dir():
            continue
        for hit in find_collisions(scan):
            problems.append(
                f"case/Unicode path collision in {scan.relative_to(root).as_posix()} (17.30): {hit}")

    # 5. registry schema + stats, always re-derived (T14)
    registry_path = root / "skills/community/registry.json"
    expect = lock.get("registry_expectation", {})
    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        problems.append(f"registry unreadable: {exc}")
        registry = {}
    if registry:
        if registry.get("schemaVersion") != expect.get("schemaVersion"):
            problems.append(
                f"registry schemaVersion {registry.get('schemaVersion')!r} != "
                f"lock expectation {expect.get('schemaVersion')!r} (old schema)")
        reg_ids = [s.get("id") for s in registry.get("sources", [])]
        if set(reg_ids) != set(expect.get("source_ids", [])):
            problems.append(
                f"registry source ids {sorted(reg_ids)} != lock expectation "
                f"{sorted(expect.get('source_ids', []))} (deprecated/unknown id)")
        if len(reg_ids) != expect.get("sources"):
            problems.append(
                f"source count drift: registry={len(reg_ids)} lock={expect.get('sources')}")
        excluded = len(registry.get("excluded", []))
        if excluded != expect.get("excluded"):
            problems.append(
                f"excluded count drift: registry={excluded} lock={expect.get('excluded')}")

    # 6. no-git note
    if not (root / ".git").is_dir():
        warnings.append(
            "no .git in this copy; git-dependent claims about the bundle itself "
            "(bundle commit pin) cannot be machine-checked -- provenance of the "
            "sources above is still fully re-checkable from the lock")

    report = {
        "lock": lock_path.as_posix(),
        "bundle_members": members,
        "registry_sources": len(registry.get("sources", [])) if registry else 0,
        "registry_excluded": len(registry.get("excluded", [])) if registry else 0,
        "problems": problems,
        "warnings": warnings,
    }
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print("=== community source bundle ===")
        print(f"lock                        : {lock_path.as_posix()}")
        print(f"registry                    : {report['registry_sources']} sources / "
              f"{report['registry_excluded']} excluded")
        for p in problems:
            print(f"[BLOCKED] {p}")
        for w in warnings:
            print(f"[REVIEW] {w}")

    if problems:
        print(f"FAIL verify-community-bundle: {len(problems)} defect(s)")
        return 20
    if warnings:
        print(f"NEEDS_REVIEW verify-community-bundle: {len(warnings)} item(s)")
        return 10
    print("PASS verify-community-bundle")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
