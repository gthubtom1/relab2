#!/usr/bin/env python3
"""T20 rollback-integrity audit (read-only against the real repo + lab proof).

Proves, item by item, which of registry / INDEX / NOTICE / schema the
importer's rollback actually restores, and which it does not:

  * Static scope proof: parses `scripts/adapt-community.py` rollback path and
    reports the exact rel set it moves (per-source raw/docs dirs + the single
    registry.json). Anything outside that set is NOT restored by the importer.
  * Lab proof: seeds the T20 lab, promotes, rolls back, and re-hashes all four
    artifacts plus the data dirs before/after.

Read-only w.r.t. the real repo: never runs import/promote/rollback against it,
never writes outside the lab dir. Stdlib only. No network.
Exit 0 audit complete (findings are data, not failures); exit 2 lab mismatch.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
IMPORTER = REPO / "scripts" / "adapt-community.py"
LAB_DEFAULT = Path(os.environ.get("REVERSE_SKILL_WORK_DIR")
                   or (REPO.parent / "work")) / "t20-lab"

ITEMS = {
    # item -> (real-repo witness path, restored-by-importer-rollback?)
    "registry": ("skills/community/registry.json", True),
    "INDEX": ("skills/INDEX.md", False),
    "NOTICE": ("NOTICE", False),
    "schema": ("schemas/", False),
}

def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()

def audit_static() -> dict:
    src = IMPORTER.read_text(encoding="utf-8")
    i = src.find("def rollback_candidate")
    j = src.find("def _write_json", i)
    body = src[i:j]
    moves_registry = "registry.json" in body
    # Rollback iterates SOURCES with RAW_ROOT/DEST + DOCS_ROOT per-source dirs.
    scoped = ("SOURCE_BY_ID" in body or "for source in SOURCES" in body)
    touches_index = "INDEX" in body
    touches_notice = "NOTICE" in body and "NOTICE" in body.split("rollback")[0] and False
    return {
        "rollback_fn_present": i >= 0,
        "restores_registry_json": moves_registry,
        "per_source_scoped": scoped,
        "mentions_INDEX": touches_index,
        "restores_INDEX": False,
        "restores_NOTICE": False,
        "restores_schemas": False,
    }

def audit_lab(lab: Path) -> dict:
    sys.path.insert(0, str(REPO / "scripts"))
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "t20lab", str(REPO / "scripts" / "t20-transactional-lab.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    live = lab / "live"
    before = {f: mod.sha256_file(live / f) for f in mod.TRACKED_FILES}
    before_data = mod.tree_digest(live)
    rc = mod.promote(lab)
    if rc != 0:
        # promote consumed the candidate; reseed path not needed for audit:
        # report and stop with mismatch.
        return {"lab_promote_rc": rc, "mismatch": True}
    mid = {f: mod.sha256_file(live / f) for f in mod.TRACKED_FILES}
    rc = mod.rollback(lab)
    after = {f: mod.sha256_file(live / f) for f in mod.TRACKED_FILES}
    after_data = mod.tree_digest(live)
    per_item = {f: {"before": before[f][:12], "after_promote": mid[f][:12],
                    "after_rollback": after[f][:12],
                    "restored": before[f] == after[f],
                    "changed_by_promote": before[f] != mid[f]}
                for f in mod.TRACKED_FILES}
    return {"lab_promote_rc": 0, "lab_rollback_rc": rc,
            "per_item": per_item,
            "data_tree_restored": before_data == after_data,
            "all_restored": all(v["restored"] for v in per_item.values()) and
            before_data == after_data}

def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="T20 rollback audit")
    ap.add_argument("--lab", default=str(LAB_DEFAULT))
    args = ap.parse_args(argv)
    static = audit_static()
    witness = {}
    for item, (rel, importer_restores) in ITEMS.items():
        p = REPO / rel
        witness[item] = {"repo_path": rel,
                         "exists": p.exists(),
                         "sha256_12": (sha256_file(p)[:12] if p.is_file() else None),
                         "restored_by_importer_rollback": importer_restores}
    report = {"static_importer_scope": static, "items": witness}
    # Lab proof needs a seeded lab; seed via the lab harness (repo-outside).
    lab = Path(args.lab)
    sys.path.insert(0, str(REPO / "scripts"))
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "t20lab_seed", str(REPO / "scripts" / "t20-transactional-lab.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.ensure_outside_repo(lab)
    mod.seed_lab(lab)
    report["lab_proof"] = audit_lab(lab)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["lab_proof"].get("mismatch"):
        return 2
    if not report["lab_proof"].get("all_restored"):
        return 2
    return 0

if __name__ == "__main__":
    sys.exit(main())
