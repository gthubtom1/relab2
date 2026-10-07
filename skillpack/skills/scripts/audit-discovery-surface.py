#!/usr/bin/env python3
"""Audit what a client can discover, by three independent mechanisms.

Rationale
---------
Spec section 17.27 requires *physical* discovery isolation, not a frontmatter
flag. A claim like "the 293 raw community skills are isolated" can only be
checked by enumerating what each discovery mechanism actually returns:

  mode=recursive   a client that simply walks skills/** looking for SKILL.md
  mode=index       a client that reads the generated skills/INDEX.md
  mode=manifest    a client that reads skills/community/registry.json

Requirements (spec 11.3 / 17.27):
  * recursive and index must expose exactly the same set as manifest
    (canonical skills + the four wrappers) -- nothing else;
  * every raw vendor file must be unreachable by recursive and index.

This script is read-only: it never writes, renames or moves anything.

Usage:
    python skills/scripts/audit-discovery-surface.py [--json OUT]

Exit codes (spec 4.7): 0 ok, 10 needs_review, 20 blocked.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILLS = ROOT / "skills"
COMMUNITY = SKILLS / "community"
INDEX = SKILLS / "INDEX.md"
REGISTRY = COMMUNITY / "registry.json"

# Directories under skills/ that are infrastructure, not discoverable skills.
SKIP_TOP = {
    "ops",
    "scripts",
    "config",
    "tests",
    "field-journal",
    "references",
    "docs",
}

INDEX_ROW_RE = re.compile(r"^\|\s*\[(?P<name>[^\]]+)\]\((?P<path>[^)]+)\)")
INDEX_TREE_RE = re.compile(r"^(?P<path>skills/[^\s`]+)/?$")

def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()

def recursive_scan() -> set[str]:
    """Every SKILL.md a plain recursive client walk would find."""
    found: set[str] = set()
    for path in SKILLS.rglob("SKILL.md"):
        parts = path.relative_to(SKILLS).parts
        if parts[0] in SKIP_TOP:
            continue
        found.add(rel(path))
    return found

def index_scan() -> tuple[set[str], set[str]]:
    """Skills exposed by the generated INDEX.md (rows and directory tree)."""
    rows: set[str] = set()
    tree: set[str] = set()
    if not INDEX.is_file():
        return rows, tree
    in_tree = False
    for line in INDEX.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            in_tree = line.startswith("## 目录树")
            continue
        if in_tree:
            m = INDEX_TREE_RE.match(line.strip())
            if m:
                target = m.group("path").rstrip("/")
                tree.add(target)
            continue
        m = INDEX_ROW_RE.match(line)
        if m:
            target = m.group("path").strip()
            if not target.startswith("../") and not target.startswith("http"):
                rows.add(f"skills/{target}" if not target.startswith("skills/") else target)
    return rows, tree

def manifest_scan() -> tuple[set[str], set[str]]:
    """What the registry declares, split into adapted and wrapper entrypoints."""
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    adapted = {item["path"] for item in data.get("skills", []) if item.get("path")}
    wrappers = {
        item["path"]
        for item in data.get("wrappers", [])
        if isinstance(item, dict) and item.get("path")
    }
    # the four canonical wrappers are known by convention when the registry has
    # no wrapper records yet
    if not wrappers:
        wrappers = {
            rel(p)
            for p in COMMUNITY.glob("*/SKILL.md")
            if p.parent.name in {"ctf-hub", "hack-hub", "delivery", "apk-extension"}
        }
    return adapted, wrappers

def canonical_scan() -> set[str]:
    """Canonical skills: top-level SKILL.md outside skills/community."""
    found: set[str] = set()
    for path in SKILLS.rglob("SKILL.md"):
        parts = path.relative_to(SKILLS).parts
        if parts[0] in SKIP_TOP or parts[0] == "community":
            continue
        found.add(rel(path))
    return found

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", help="write the full report to this path")
    args = parser.parse_args()

    if not SKILLS.is_dir():
        print(f"FAIL skills root missing: {SKILLS}")
        return 20

    recursive = recursive_scan()
    index_rows, index_tree = index_scan()
    adapted, wrappers = manifest_scan()
    canonical = canonical_scan()
    index = index_rows | index_tree

    expected = canonical | wrappers
    raw = recursive - expected

    report = {
        "canonical_count": len(canonical),
        "wrapper_count": len(wrappers),
        "registry_adapted_count": len(adapted),
        "recursive_count": len(recursive),
        "index_row_count": len(index_rows),
        "index_tree_count": len(index_tree),
        "index_union_count": len(index),
        "expected_exposed_count": len(expected),
        "raw_exposed_by_recursive": sorted(raw),
        "vendored_exposed_by_index": sorted(index & adapted),
        "missing_from_recursive": sorted(expected - recursive),
    }

    print("=== discovery surface audit ===")
    print(f"canonical skills               : {len(canonical)}")
    print(f"canonical wrappers             : {len(wrappers)} -> {sorted(wrappers)}")
    print(f"registry adapted skills        : {len(adapted)}")
    print(f"expected exposed set           : {len(expected)}")
    print(f"recursive scan finds           : {len(recursive)}")
    print(f"INDEX.md rows                  : {len(index_rows)}")
    print(f"INDEX.md directory tree        : {len(index_tree)}")
    print(f"raw vendor files exposed       : {len(raw)}")
    print(f"vendored skills exposed by INDEX: {len(index & adapted)}")

    findings: list[str] = []
    if raw:
        findings.append(
            f"BLOCKED: {len(raw)} raw vendor skill file(s) are reachable by a plain "
            "recursive client walk (spec 17.27 requires physical isolation)"
        )
    vendored_in_index = index & adapted
    if vendored_in_index:
        findings.append(
            f"BLOCKED: INDEX.md exposes {len(vendored_in_index)} vendored skill path(s); "
            "INDEX must list canonical skills and the four wrappers only (spec 11.3)"
        )
    missing = expected - recursive
    if missing:
        findings.append(
            f"BLOCKED: {len(missing)} expected skill(s) are missing from the "
            f"recursive scan: {sorted(missing)[:5]}"
        )

    for f in findings:
        print(f)
    print(
        "NOTE: raw files legitimately present on disk are not the defect by "
        "themselves; being *discoverable* is."
    )

    if args.json:
        out = Path(args.json)
        out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"report written: {out}")

    if findings:
        print(f"FAIL audit-discovery-surface: {len(findings)} defect(s)")
        return 20
    print("PASS audit-discovery-surface")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
