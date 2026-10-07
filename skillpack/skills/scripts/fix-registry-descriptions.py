"""Recompute ``extensions.legacy_description`` / ``legacy_original_name`` in the registry.

The community registry stores, per skill, the description and original name that
were parsed out of the upstream ``SKILL.md`` frontmatter.  The original importer
only read the ``description:`` line, so every upstream file that uses a YAML
block scalar contributed its *indicator* (``>-``) instead of the description
text.  This script re-derives both fields with
:mod:`parse-skill-frontmatter` and reports or writes the result.

Usage::

    python skills/scripts/fix-registry-descriptions.py --check
    python skills/scripts/fix-registry-descriptions.py --apply

Exit codes: ``0`` registry already in sync (or the write succeeded),
``1`` the registry is out of sync / problems were found, ``2`` the registry or
one of its source files could not be read.

Only ``extensions.legacy_description`` and ``extensions.legacy_original_name``
are ever written; every other key is re-serialised byte-for-byte identically
(``json.dumps(..., ensure_ascii=False, indent=2) + "\\n"`` is the format the
file already uses, verified by round-trip).
"""

from __future__ import annotations

import argparse
import importlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
REGISTRY = ROOT / "skills" / "community" / "registry.json"

sys.path.insert(0, str(HERE))
frontmatter = importlib.import_module("parse-skill-frontmatter")

#: Literal block-scalar / indicator tokens that must never survive as a value.
INDICATOR_VALUES = {">", ">-", ">+", "|", "|-", "|+", ">- ", ">2", "|-2", ">1", "|1"}
#: A value that is only a slug or a bare path fragment is not a description.
SLUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/:\-]*$")
SHORT_SUSPICIOUS = 20

def load_registry(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))

def serialize(registry: Dict[str, Any]) -> str:
    return json.dumps(registry, ensure_ascii=False, indent=2) + "\n"

def is_suspicious(value: str) -> str:
    """Return a reason string when *value* does not look like a description."""
    if not value:
        return "empty"
    if value in INDICATOR_VALUES or value.strip() in INDICATOR_VALUES:
        return "block-scalar indicator"
    if len(value) < SHORT_SUSPICIOUS:
        return "shorter than {} chars".format(SHORT_SUSPICIOUS)
    if SLUG_RE.match(value):
        return "slug-like, not prose"
    if not any(char.isalnum() for char in value):
        return "no alphanumeric characters"
    return ""

def analyse(record: Dict[str, Any], root: Path) -> Tuple[str, str, str]:
    """Return ``(description, name, problem)`` for one registry record."""
    rel = record.get("path") or ""
    source = root / rel
    if not source.is_file():
        return "", "", "source file missing: {}".format(rel)
    data = frontmatter.parse_file(source)
    description = frontmatter.normalize_description(data.get("description"))
    name = frontmatter.normalize_description(data.get("name"))
    problem = ""
    if not description:
        problem = is_suspicious(description) or "no description in frontmatter"
    return description, name, problem

def run(registry_path: Path, apply_changes: bool) -> int:
    registry = load_registry(registry_path)
    records = registry.get("skills") or []
    root = registry_path.parent.parent.parent

    drift: List[Dict[str, Any]] = []
    problems: List[Tuple[str, str]] = []
    suspicious: List[Tuple[str, str, str]] = []
    computed: Dict[str, Tuple[str, str]] = {}
    unchanged = 0

    for record in records:
        rid = record.get("id", "<no id>")
        extensions = record.setdefault("extensions", {})
        description, name, problem = analyse(record, root)
        computed[rid] = (description, name)
        if problem:
            problems.append((rid, problem))
            suspicious.append((rid, description or "<empty>", problem))
        elif is_suspicious(description):
            suspicious.append((rid, description, is_suspicious(description)))

        old_description = extensions.get("legacy_description")
        old_name = extensions.get("legacy_original_name")
        changed = old_description != description or old_name != name
        if changed:
            drift.append({
                "id": rid,
                "path": record.get("path"),
                "field": "legacy_description" if old_description != description else "legacy_original_name",
                "old": old_description,
                "new": description,
                "old_name": old_name,
                "new_name": name,
            })
        else:
            unchanged += 1

    print("registry: {}".format(registry_path.relative_to(root)))
    print("records: {}".format(len(records)))
    print("already correct: {}".format(unchanged))
    print("need fixing:    {}".format(len(drift)))
    print("suspicious:     {}".format(len(suspicious)))
    print("hard problems:  {}".format(len(problems)))

    if drift:
        buckets = {}
        for item in drift:
            buckets[item["field"]] = buckets.get(item["field"], 0) + 1
        print("drift by field: {}".format(buckets))
        for item in drift[:5]:
            print("  - {} {}".format(item["id"], item["field"]))
            print("      old: {!r}".format((item["old"] or "")[:100]))
            print("      new: {!r}".format((item["new"] or "")[:100]))
        if len(drift) > 5:
            print("  ... {} more".format(len(drift) - 5))

    if suspicious:
        print("suspicious entries (count / id / value / reason):")
        for rid, value, reason in suspicious[:20]:
            print("  {} | {} | {!r}".format(rid, reason, value[:80]))
        if len(suspicious) > 20:
            print("  ... {} more".format(len(suspicious) - 20))

    if problems and apply_changes:
        print("refusing to --apply while {} record(s) have no usable description".format(len(problems)))
        return 2

    if not apply_changes:
        if drift:
            print("CHECK: registry is OUT OF SYNC ({} record(s) differ)".format(len(drift)))
            return 1
        print("CHECK: registry is IN SYNC")
        return 0

    if not drift:
        print("APPLY: no change needed")
        return 0

    for record in records:
        description, name = computed[record.get("id", "<no id>")]
        extensions = record["extensions"]
        extensions["legacy_description"] = description
        extensions["legacy_original_name"] = name

    before = registry_path.read_text(encoding="utf-8")
    after = serialize(registry)
    if before == after:
        print("APPLY: no change needed")
        return 0
    registry_path.write_text(after, encoding="utf-8", newline="\n")
    print("APPLY: rewrote {} record field(s) in {}".format(len(drift), registry_path.name))
    return 0

def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="read-only: report drift and exit 1 if any")
    mode.add_argument("--apply", action="store_true", help="rewrite the two legacy fields in place")
    parser.add_argument("--registry", default=str(REGISTRY), help="registry path (default: %(default)s)")
    args = parser.parse_args(argv)
    path = Path(args.registry).resolve()
    if not path.is_file():
        print("registry not found: {}".format(path), file=sys.stderr)
        return 2
    return run(path, apply_changes=args.apply)

if __name__ == "__main__":
    raise SystemExit(main())
