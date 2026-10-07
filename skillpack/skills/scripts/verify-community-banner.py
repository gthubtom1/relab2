#!/usr/bin/env python3
"""Guard the community tree against silent regression from re-import.

Why this exists
---------------
`scripts/adapt-community.py` overwrites 1111 paths per run (1087 under
`skills/community/**`, 23 under `docs/community/**`, plus `registry.json`) with
clean upstream text -- no diff, no backup, no digest.  See WORK-BOARD CR-002.

That makes every hand edit inside that write set temporary: the next import
silently reverts it.  This script does not prevent the import (that needs the
T05 rewrite); it makes the *regression* visible immediately, by asserting the
marks that upstream text does NOT carry:

  1. every vendored reference doc under docs/community/** carries a
     reference-only banner (spec 17.19);
  2. every raw community SKILL.md carries the integration contract marker
     (the importer adds it, so its absence means a pre-contract copy);
  3. raw community SKILL.md declares `user-invocable: "false"` exactly once
     (spec 17.27 -- frontmatter is not isolation, but a missing/duplicated key
     is still a defect);
  4. no `AI LOAD INSTRUCTION` survives in the vendored `hack-skills` raw tree
     (spec 17.19; the raw tree lives under `community-raw/` since 17.27);
  5. the four wrappers exist and carry `## ACTION REQUIRED`.

Read-only: this script never writes anything.

Usage:
    python skills/scripts/verify-community-banner.py [--json OUT]

Exit codes (spec 4.7): 0 ok, 10 needs_review, 20 blocked.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILLS = ROOT / "skills"
COMMUNITY = SKILLS / "community"
DOCS_COMMUNITY = ROOT / "docs" / "community"
REGISTRY = COMMUNITY / "registry.json"
# Spec 17.27: the raw vendor trees live *outside* the client discovery root
# `skills/`, so the raw-side checks below range over this root.  `COMMUNITY` is
# still scanned as well: a re-import that writes the raw tree back under
# `skills/community/<source>/` must not slip past this guard unnoticed.
RAW = ROOT / "community-raw"
RAW_ROOTS = (COMMUNITY, RAW)

WRAPPERS = {
    "ctf-hub": COMMUNITY / "ctf-hub" / "SKILL.md",
    "hack-hub": COMMUNITY / "hack-hub" / "SKILL.md",
    "delivery": COMMUNITY / "delivery" / "SKILL.md",
    "apk-extension": COMMUNITY / "apk-extension" / "SKILL.md",
}

CONTRACT_MARKER = "## Integrated reverse-skill contract"
ACTION_MARKER = "## ACTION REQUIRED"
LOAD_INSTRUCTION = "AI LOAD INSTRUCTION"
USER_INVOCABLE_RE = re.compile(r'^\s*user-invocable\s*:', re.M)

# Banner markers accepted for vendored reference docs. A doc is compliant when
# at least one of these appears in the first 40 lines.
BANNER_MARKERS = (
    "reference-only",
    "来源留档",
    "不可当规则执行",
    "provenance",
    "PROVENANCE",
    "Reference-only",
)
BANNER_SCAN_LINES = 40

def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")

def vendored_source_ids() -> set[str]:
    """Source ids that are actually vendored from an upstream repository.

    `docs/community/<id>/` mirrors the upstream tree for that source, so every
    markdown file inside it is vendored and needs the reference-only banner.
    Directories that hold our own documents (for example a migration record)
    must NOT be treated as vendored, otherwise the guard reports a false
    positive on files this repository authored.
    """
    ids: set[str] = set()
    if not REGISTRY.is_file():
        return ids
    try:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ids
    for source in data.get("sources", []):
        sid = source.get("id")
        if sid and (DOCS_COMMUNITY / sid).is_dir():
            ids.add(sid)
    return ids

def check_docs_banners(vendored: set[str]) -> tuple[list[str], int, int]:
    """Return (problems, vendored_total, skipped_non_vendored)."""
    problems: list[str] = []
    total = 0
    skipped = 0
    if not DOCS_COMMUNITY.is_dir():
        return problems, total, skipped
    for path in sorted(DOCS_COMMUNITY.rglob("*.md")):
        rel = path.relative_to(DOCS_COMMUNITY)
        if rel.parts[0] not in vendored:
            skipped += 1
            continue
        total += 1
        head = "\n".join(read(path).splitlines()[:BANNER_SCAN_LINES])
        if not any(marker in head for marker in BANNER_MARKERS):
            problems.append(f"missing reference-only banner: {path.relative_to(ROOT).as_posix()}")
    return problems, total, skipped

def check_raw_skills() -> tuple[list[str], dict]:
    """Raw community SKILL.md, wherever the raw tree currently lives.

    The rule is unchanged (`## Integrated reverse-skill contract` present, and
    `user-invocable: "false"` declared exactly once); only the roots it ranges
    over follow the spec 17.27 move.
    """
    missing_contract: list[str] = []
    bad_user_invocable: list[str] = []
    total = 0
    for base in RAW_ROOTS:
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("SKILL.md")):
            if path.parent.name in WRAPPERS:
                continue  # wrapper, checked separately
            total += 1
            text = read(path)
            rel = path.relative_to(ROOT).as_posix()
            if CONTRACT_MARKER not in text:
                missing_contract.append(rel)
            occurrences = USER_INVOCABLE_RE.findall(text)
            if len(occurrences) != 1 or 'user-invocable: "false"' not in text:
                bad_user_invocable.append(f"{rel} (count={len(occurrences)})")
    return [*missing_contract, *bad_user_invocable], {
        "raw_skills": total,
        "missing_contract": missing_contract,
        "bad_user_invocable": bad_user_invocable,
    }

def check_load_instructions() -> tuple[list[str], int]:
    problems: list[str] = []
    count = 0
    for base in (base / "hack-skills" for base in RAW_ROOTS):
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            try:
                text = read(path)
            except OSError:
                continue
            n = text.count(LOAD_INSTRUCTION)
            if n:
                count += n
                problems.append(
                    f"AI LOAD INSTRUCTION x{n}: {path.relative_to(ROOT).as_posix()}"
                )
    return problems, count

def check_wrappers() -> list[str]:
    problems: list[str] = []
    for name, path in WRAPPERS.items():
        if not path.is_file():
            problems.append(f"wrapper missing: {name} -> {path.relative_to(ROOT).as_posix()}")
            continue
        if ACTION_MARKER not in read(path):
            problems.append(f"wrapper missing '{ACTION_MARKER}': {path.relative_to(ROOT).as_posix()}")
    return problems

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", help="write the full report to this path")
    args = parser.parse_args()

    if not COMMUNITY.is_dir():
        print(f"FAIL community root missing: {COMMUNITY}")
        return 20

    vendored = vendored_source_ids()
    docs_problems, docs_total, docs_skipped = check_docs_banners(vendored)
    raw_problems, raw_stats = check_raw_skills()
    load_problems, load_count = check_load_instructions()
    wrapper_problems = check_wrappers()

    blocked = [*wrapper_problems, *load_problems]
    review = [*docs_problems, *raw_problems]

    report = {
        "vendored_source_ids": sorted(vendored),
        "docs_vendored_md_files": docs_total,
        "docs_non_vendored_skipped": docs_skipped,
        "docs_missing_banner": docs_problems,
        "raw_skill_stats": raw_stats,
        "load_instruction_count": load_count,
        "load_instruction_files": load_problems,
        "wrapper_problems": wrapper_problems,
    }

    print("=== community banner / regression guard ===")
    print(f"vendored source ids                : {len(vendored)} -> {sorted(vendored)}")
    print(f"vendored docs markdown files       : {docs_total}")
    print(f"  missing reference-only banner    : {len(docs_problems)}")
    print(f"  non-vendored docs skipped        : {docs_skipped}")
    print(f"raw community SKILL.md             : {raw_stats['raw_skills']}")
    print(f"  missing integration contract     : {len(raw_stats['missing_contract'])}")
    print(f"  user-invocable not exactly false : {len(raw_stats['bad_user_invocable'])}")
    print(f"AI LOAD INSTRUCTION under hack-skills: {load_count}")
    print(f"wrapper problems                   : {len(wrapper_problems)}")

    for p in blocked[:20]:
        print(f"[BLOCKED] {p}")
    for p in review[:20]:
        print(f"[REVIEW] {p}")
    if len(blocked) + len(review) > 40:
        print(f"... {len(blocked) + len(review) - 40} more")

    if args.json:
        out = Path(args.json)
        out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"report written: {out}")

    if blocked:
        print(f"FAIL verify-community-banner: {len(blocked)} blocking defect(s)")
        return 20
    if review:
        print(f"NEEDS_REVIEW verify-community-banner: {len(review)} item(s)")
        return 10
    print("PASS verify-community-banner")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
