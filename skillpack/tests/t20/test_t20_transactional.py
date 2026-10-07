#!/usr/bin/env python3
"""T20 regression tests (lab-only; the real repo is never written).

Run: python tests/t20/test_t20_transactional.py
     (or set REVERSE_SKILL_PYTHON to a specific interpreter)
Exit 0 all pass; exit 1 any failure. Stdlib only.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

def _detect_python():
    """Interpreter probe: REVERSE_SKILL_PYTHON -> sys.executable -> python3 -> python."""
    env = os.environ.get("REVERSE_SKILL_PYTHON")
    if env and os.path.isfile(env):
        return env
    if sys.executable and os.path.isfile(sys.executable):
        return sys.executable
    for name in ("python3", "python"):
        found = shutil.which(name)
        if found:
            return found
    return sys.executable or "python"

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "scripts"
LAB = Path(os.environ.get("REVERSE_SKILL_WORK_DIR")
           or (REPO.parent / "work")) / "t20-lab"
PYTHON = _detect_python()

RESULTS = []

def check(name, ok, detail=""):
    RESULTS.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  -- {detail}" if detail else ""))
    return ok

def load_lab():
    spec = importlib.util.spec_from_file_location(
        "t20lab", str(SCRIPTS / "t20-transactional-lab.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def run_cli(*args):
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run([PYTHON, str(SCRIPTS / "t20-transactional-lab.py"), *args],
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", env=env)

def main() -> int:
    mod = load_lab()
    t20 = load_lab  # silence linters; real handle is `mod`

    # 1. seed builds generation 1 + sealed candidate.
    info = mod.seed_lab(LAB)
    gen = json.loads((LAB / "generation-manifest.json").read_text(encoding="utf-8"))
    check("seed-generation-1", gen["generation"] == 1, f"gen={gen['generation']}")
    check("seed-seal-matches", info["candidate_digest"] == json.loads(
        (LAB / "candidates/gen2/seal.json").read_text(encoding="utf-8"))["candidate_digest"])

    # 2. clean promote reaches generation 2 with all four files swapped.
    live = LAB / "live"
    before = {f: mod.sha256_file(live / f) for f in mod.TRACKED_FILES}
    rc = mod.promote(LAB)
    gen = json.loads((LAB / "generation-manifest.json").read_text(encoding="utf-8"))
    check("clean-promote-rc0", rc == 0, f"rc={rc}")
    check("clean-promote-gen2", gen["generation"] == 2, f"gen={gen['generation']}")
    after = {f: mod.sha256_file(live / f) for f in mod.TRACKED_FILES}
    check("promote-swaps-all-four",
          all(before[f] != after[f] for f in mod.TRACKED_FILES),
          f"swapped={sum(before[f] != after[f] for f in mod.TRACKED_FILES)}/4")

    # 3. rollback restores all four + data (re-verified byte equality).
    rc = mod.rollback(LAB)
    restored = {f: mod.sha256_file(live / f) for f in mod.TRACKED_FILES}
    check("rollback-rc0", rc == 0, f"rc={rc}")
    check("rollback-restores-four",
          all(restored[f] == before[f] for f in mod.TRACKED_FILES),
          f"restored={sum(restored[f] == before[f] for f in mod.TRACKED_FILES)}/4")

    # 4. crash windows: each must recover to the consistent pre-promote generation.
    for window in ("A", "B", "B2", "C"):
        mod.seed_lab(LAB)
        pre = mod.tree_digest(LAB / "live")
        rc = mod.promote(LAB, crash_at=window)
        check(f"crash-{window}-interrupts", rc == 30, f"rc={rc}")
        journal = json.loads((LAB / "promote-journal.json").read_text(encoding="utf-8"))
        check(f"crash-{window}-journal", journal["state"] == "interrupted",
              f"state={journal['state']} steps={len(journal['steps'])}")
        rc = mod.recover(LAB)
        post = mod.tree_digest(LAB / "live")
        check(f"crash-{window}-recover-consistent", rc == 0 and post == pre,
              f"rc={rc} match={post == pre} tree={post[:12]}")

    # 5. crash D (post-commit) finalises the committed generation, not a revert.
    mod.seed_lab(LAB)
    rc = mod.promote(LAB, crash_at="D")
    check("crash-D-interrupts", rc == 30, f"rc={rc}")
    rc = mod.recover(LAB)
    gen = json.loads((LAB / "generation-manifest.json").read_text(encoding="utf-8"))
    check("crash-D-recover-committed", rc == 0 and gen["generation"] == 2,
          f"rc={rc} gen={gen['generation']}")

    # 6. incompatible format hard-blocks (non-zero, no downgrade).
    mod.seed_lab(LAB)
    pre_live = mod.tree_digest(LAB / "live")
    (LAB / "candidates/gen2/schemas/app.json").write_text(
        json.dumps({"format": "t99/future/9"}), encoding="utf-8")
    rc = mod.promote(LAB)
    check("incompatible-format-blocked", rc == 20, f"rc={rc}")
    live_now = mod.tree_digest(LAB / "live")
    check("incompatible-format-live-untouched", live_now == pre_live,
          f"live={live_now[:12]} pre={pre_live[:12]}")
    print(f"INFO  live-after-blocked-promote tree={live_now[:12]}")

    # 7. format gate self-test 4/4.
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    r = subprocess.run([PYTHON, str(SCRIPTS / "t20-format-gate.py"), "--self-test"],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=env)
    check("format-gate-selftest", r.returncode == 0, r.stdout.strip().splitlines()[-1])

    # 8. tampered seal blocks.
    mod.seed_lab(LAB)
    (LAB / "candidates/gen2/data/alpha/SKILL.md").write_text("# tampered\n", encoding="utf-8")
    rc = mod.promote(LAB)
    check("tampered-seal-blocked", rc == 20, f"rc={rc}")

    # 9. lock contention blocks with 22.
    mod.seed_lab(LAB)
    (LAB / "promote.lock").write_text("holder", encoding="utf-8")
    rc = mod.promote(LAB)
    check("lock-held-blocked", rc == 22, f"rc={rc}")
    (LAB / "promote.lock").unlink()

    # 10. lab refuses to run inside the repo checkout.
    r = run_cli("--seed", "--lab", str(REPO / "work" / "t20-evil"))
    check("inside-repo-refused", r.returncode == 21, f"rc={r.returncode}")

    # 11. real repo untouched: no .candidates, git status has no T20 paths.
    r = subprocess.run(["git", "--no-optional-locks", "status", "--porcelain"],
                       capture_output=True, text=True, encoding="utf-8",
                       cwd=str(REPO))
    t20_lines = [l for l in r.stdout.splitlines()
                 if "t20" in l.lower() or "T20" in l or "TRANSACTIONAL" in l]
    # Expected: the 5 new files we intentionally added (untracked). Nothing else.
    check("repo-only-t20-paths-dirty", all(
        ("scripts/t20-" in l or "tests/t20" in l or "TRANSACTIONAL-PROMOTION" in l)
        for l in t20_lines), f"t20-lines={len(t20_lines)}")
    check("no-candidates-dir", not (REPO / ".candidates").exists(), "absent")

    failed = [n for n, ok, _ in RESULTS if not ok]
    print(f"\nT20: {len(RESULTS) - len(failed)}/{len(RESULTS)} passed")
    return 0 if not failed else 1

if __name__ == "__main__":
    sys.exit(main())
