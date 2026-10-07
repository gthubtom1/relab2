#!/usr/bin/env python3
"""T20 transactional promotion lab harness (warehouse-outside lab only).

Implements the 17.14 lifecycle ON TOP of the importer's journaled-rename
semantics without touching `scripts/adapt-community.py`:

  sealed candidate -> generation manifest -> single-writer lock ->
  two-phase promote marker -> fsync -> crash-recovery scan ->
  consistent rollback of registry/INDEX/NOTICE/schema -> re-verify ->
  incompatible-format hard block.

Crash injection: --crash-at=A|B|B2|C|D raises between two real renames,
leaving the journal + snapshot behind. --recover then restores a consistent
generation. Every run prints per-step evidence (journal state, generation id,
tree digest) and appends a JSON evidence record under the lab dir.

Lab root default: <repo>/../work/t20-lab (OUTSIDE the repo), override with
``REVERSE_SKILL_WORK_DIR`` or ``--lab``.
This script refuses to run with a lab dir inside the repository checkout.

Stdlib only. No network. Exit codes follow spec 4.7:
0 ok, 20 blocked (seal/format/curation), 21 missing input, 22 unavailable
(lock held / cross-volume), 30 failed (interrupted promote).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
LAB_DEFAULT = Path(os.environ.get("REVERSE_SKILL_WORK_DIR")
                   or (_REPO.parent / "work")) / "t20-lab"
SCHEMA_VERSION = "t20/generation-manifest/1"
SUPPORTED_FORMATS = {"t20/lab-format/1"}
EXIT_OK, EXIT_BLOCKED, EXIT_MISSING, EXIT_UNAVAIL, EXIT_FAILED = 0, 20, 21, 22, 30

# Artifacts managed as ONE generation (17.14): data dirs + these four files.
TRACKED_FILES = ("registry.json", "INDEX.md", "NOTICE", "schemas/app.json")
DATA_DIRS = ("data/alpha", "data/beta")

def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()

# Seal / manifest sidecars are evidence ABOUT the tree, not part of it.
SEAL_EXCLUDE = {"seal.json", "generation-manifest.json", "promote-journal.json",
                "promote.lock"}

def tree_digest(root: Path) -> str:
    lines = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for fn in sorted(filenames):
            fp = Path(dirpath) / fn
            if fp.is_symlink():
                continue
            rel = fp.relative_to(root).as_posix()
            if Path(rel).name in SEAL_EXCLUDE:
                continue
            lines.append(b"f\x00" + rel.encode() + b"\x00" + hashlib.sha256(
                fp.read_bytes().replace(b"\r\n", b"\n")).hexdigest().encode() + b"\n")
    return hashlib.sha256(b"".join(sorted(lines))).hexdigest()

def write_json_fsync(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                   encoding="utf-8")
    with open(tmp, "rb") as fh:
        try:
            os.fsync(fh.fileno())
        except OSError:
            pass
    os.replace(tmp, path)

def fail(code: int, msg: str, **extra) -> int:
    print(json.dumps({"ok": False, "exit": code, "error": msg, **extra},
                     ensure_ascii=False), flush=True)
    return code

def ensure_outside_repo(lab: Path) -> Path:
    probe = lab.resolve()
    c = probe
    while True:
        if (c / "scripts/adapt-community.py").exists():
            print(f"refusing: lab dir {lab} is inside the repository checkout",
                  flush=True)
            sys.exit(EXIT_MISSING)
        if c.parent == c:
            break
        c = c.parent
    return probe

def seed_lab(lab: Path) -> dict:
    """Build a fresh lab: live tree at generation 1 + sealed candidate gen 2."""
    if lab.exists():
        shutil.rmtree(lab)
    live = lab / "live"
    for d in DATA_DIRS:
        (live / d).mkdir(parents=True, exist_ok=True)
        (live / d / "SKILL.md").write_text(f"# live {d} gen1\n", encoding="utf-8")
    (live / "registry.json").write_text(
        json.dumps({"generation": 1, "skills": ["alpha", "beta"]}, indent=2) + "\n",
        encoding="utf-8")
    (live / "INDEX.md").write_text("# INDEX gen1\n", encoding="utf-8")
    (live / "NOTICE").write_text("NOTICE gen1\n", encoding="utf-8")
    (live / "schemas").mkdir(parents=True, exist_ok=True)
    (live / "schemas/app.json").write_text(
        json.dumps({"format": "t20/lab-format/1", "v": 1}, indent=2) + "\n",
        encoding="utf-8")
    gen = {"schema": SCHEMA_VERSION, "generation": 1,
           "tree_digest": tree_digest(live), "created_at": _utcnow(),
           "history": ["seed generation 1"]}
    write_json_fsync(lab / "generation-manifest.json", gen)
    cand = lab / "candidates" / "gen2"
    shutil.copytree(live, cand)
    (cand / "data/alpha/SKILL.md").write_text("# live data/alpha gen2-candidate\n",
                                              encoding="utf-8")
    (cand / "registry.json").write_text(
        json.dumps({"generation": 2, "skills": ["alpha", "beta", "gamma"]}, indent=2) + "\n",
        encoding="utf-8")
    (cand / "INDEX.md").write_text("# INDEX gen2\n", encoding="utf-8")
    (cand / "NOTICE").write_text("NOTICE gen2\n", encoding="utf-8")
    (cand / "schemas/app.json").write_text(
        json.dumps({"format": "t20/lab-format/1", "v": 2}, indent=2) + "\n",
        encoding="utf-8")
    seal = {"candidate": "gen2", "candidate_digest": tree_digest(cand),
            "format": "t20/lab-format/1", "sealed_at": _utcnow()}
    write_json_fsync(cand / "seal.json", seal)
    return {"live_digest": tree_digest(live), "candidate_digest": seal["candidate_digest"]}

def _utcnow() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

def _lock_path(lab: Path) -> Path:
    return lab / "promote.lock"

def acquire_lock(lab: Path) -> bool:
    try:
        fd = os.open(_lock_path(lab), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        return True
    except FileExistsError:
        return False

def release_lock(lab: Path) -> None:
    try:
        _lock_path(lab).unlink()
    except FileNotFoundError:
        pass

def check_format(lab: Path, cand: Path) -> tuple:
    """Incompatible format must hard-block, never silently downgrade."""
    try:
        schema = json.loads((cand / "schemas/app.json").read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        return False, f"candidate schema unreadable: {exc}"
    fmt = schema.get("format", "<absent>")
    if fmt not in SUPPORTED_FORMATS:
        return False, (f"incompatible candidate format {fmt!r}; "
                       f"supported={sorted(SUPPORTED_FORMATS)}; refusing, no downgrade")
    return True, fmt

def promote(lab: Path, crash_at=None) -> int:
    live, cand = lab / "live", lab / "candidates" / "gen2"
    journal_p = lab / "promote-journal.json"
    if not cand.is_dir():
        return fail(EXIT_MISSING, "candidate gen2 absent; run seed first")
    if journal_p.exists():
        st = json.loads(journal_p.read_text(encoding="utf-8")).get("state")
        return fail(EXIT_BLOCKED, f"unfinished journal exists (state={st}); run --recover first")
    if not acquire_lock(lab):
        return fail(EXIT_UNAVAIL, "single-writer lock held; another promote owns the lab")
    try:
        seal = json.loads((cand / "seal.json").read_text(encoding="utf-8"))
        now = tree_digest(cand)
        if now != seal["candidate_digest"]:
            return fail(EXIT_BLOCKED, "candidate digest changed after seal; refusing",
                        sealed=seal["candidate_digest"], current=now)
        print(f"seal-ok candidate_digest={now[:12]}", flush=True)
        ok, fmt = check_format(lab, cand)
        if not ok:
            return fail(EXIT_BLOCKED, fmt)
        print(f"format-ok {fmt}", flush=True)
        try:
            same_vol = os.stat(lab).st_dev == os.stat(live).st_dev
        except OSError:
            same_vol = False
        if not same_vol:
            return fail(EXIT_UNAVAIL, "lab and live tree on different volumes; rename unsafe")
        gen = json.loads((lab / "generation-manifest.json").read_text(encoding="utf-8"))
        stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        snap = lab / "snapshots" / f"generation-{gen['generation']}-{stamp}"
        journal = {"schema": "t20/promote-journal/1", "state": "begin",
                   "generation": gen["generation"], "candidate": "gen2",
                   "candidate_digest": now,
                   "snapshot": snap.relative_to(lab).as_posix(),
                   "steps": [], "started_at": _utcnow()}
        write_json_fsync(journal_p, journal)
        print(f"journal-begin generation={gen['generation']} snapshot={journal['snapshot']}",
              flush=True)
        if crash_at == "A":
            raise RuntimeError("injected crash A: after journal begin, before snapshot")
        snap.mkdir(parents=True, exist_ok=True)
        for d in DATA_DIRS:
            shutil.copytree(live / d, snap / d)
        for f in TRACKED_FILES:
            target = snap / f
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(live / f, target)
        journal["state"] = "snapshotted"
        journal["steps"].append("snapshot-complete")
        write_json_fsync(journal_p, journal)
        print(f"snapshot-ok tree={tree_digest(snap)[:12]}", flush=True)
        if crash_at == "B":
            raise RuntimeError("injected crash B: after snapshot, before move-aside")
        for i, d in enumerate(DATA_DIRS):
            aside = snap / "aside" / d
            aside.parent.mkdir(parents=True, exist_ok=True)
            os.replace(live / d, aside)
            journal["state"] = "target-moved-aside"
            journal["steps"].append(f"moved-aside: {d}")
            write_json_fsync(journal_p, journal)
            print(f"moved-aside {d} (window open: {d} absent from live)", flush=True)
            if crash_at == "B2" and i == 0:
                raise RuntimeError("injected crash B2: between the two renames")
        for d in DATA_DIRS:
            os.replace(cand / d, live / d)
            journal["steps"].append(f"promoted: {d}")
            write_json_fsync(journal_p, journal)
            print(f"promoted {d}", flush=True)
        if crash_at == "C":
            raise RuntimeError("injected crash C: data swapped, registry not yet swapped")
        for f in TRACKED_FILES:
            os.replace(cand / f, live / f)
            journal["steps"].append(f"promoted: {f}")
        journal["state"] = "committed"
        journal["finished_at"] = _utcnow()
        write_json_fsync(journal_p, journal)
        print("journal-committed", flush=True)
        if crash_at == "D":
            # Real post-commit crash: the committed journal is already durable;
            # only the in-memory manifest update is lost. Leave the journal as
            # committed so --recover finalises the generation.
            print("INTERRUPTED injected crash D: after commit, before manifest "
                  "update; rerun with --recover", flush=True)
            return EXIT_FAILED
        gen["generation"] += 1
        gen["tree_digest"] = tree_digest(live)
        gen["history"].append(f"promoted gen2 at {journal['finished_at']}")
        write_json_fsync(lab / "generation-manifest.json", gen)
        snaps = sorted((lab / "snapshots").iterdir())
        for old in snaps[:-3]:
            shutil.rmtree(old, ignore_errors=True)
        journal_p.unlink()
        print(f"promote-ok generation={gen['generation']} tree={gen['tree_digest'][:12]}",
              flush=True)
        return EXIT_OK
    except RuntimeError as exc:
        j = json.loads(journal_p.read_text(encoding="utf-8"))
        j["state"] = "interrupted"
        j["error"] = str(exc)
        write_json_fsync(journal_p, j)
        print(f"INTERRUPTED {exc}; journal=interrupted; rerun with --recover", flush=True)
        return EXIT_FAILED
    finally:
        release_lock(lab)

def _snapshot_payload_digest(snap: Path):
    if not snap or not snap.is_dir():
        return None
    tmp = snap.parent / "_recover_check"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    for d in DATA_DIRS:
        src = snap / d
        if src.is_dir():
            shutil.copytree(src, tmp / d)
    for f in TRACKED_FILES:
        src = snap / f
        if src.is_file():
            dst = tmp / f
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    digest = tree_digest(tmp)
    shutil.rmtree(tmp, ignore_errors=True)
    return digest

def recover(lab: Path) -> int:
    journal_p = lab / "promote-journal.json"
    if not journal_p.exists():
        print("recover: no journal; nothing to do", flush=True)
        return EXIT_OK
    journal = json.loads(journal_p.read_text(encoding="utf-8"))
    state = journal.get("state")
    print(f"recover: journal state={state} steps={len(journal.get('steps', []))}", flush=True)
    live = lab / "live"
    gen = json.loads((lab / "generation-manifest.json").read_text(encoding="utf-8"))
    if state == "committed":
        print("recover: crash D path; live tree is fully swapped, finalising manifest",
              flush=True)
        gen = json.loads((lab / "generation-manifest.json").read_text(encoding="utf-8"))
        if gen["tree_digest"] != tree_digest(live):
            gen["generation"] += 1
            gen["tree_digest"] = tree_digest(live)
            gen["history"].append(f"recovered committed promote at {_utcnow()}")
            write_json_fsync(lab / "generation-manifest.json", gen)
        journal_p.unlink()
        print(f"RECOVER-OK generation={gen['generation']} tree={gen['tree_digest'][:12]}",
              flush=True)
        return EXIT_OK
    snap = lab / journal["snapshot"]
    if "snapshot-complete" not in journal.get("steps", []):
        # Crash A: snapshot never completed, nothing was ever moved. The live
        # tree plus the generation manifest are authoritative by themselves.
        live_digest = tree_digest(live)
        consistent = (live_digest == gen["tree_digest"])
        print(f"recover: pre-snapshot crash; live tree={live_digest[:12]} "
              f"manifest gen={gen['generation']} tree={gen['tree_digest'][:12]} "
              f"consistent={consistent}", flush=True)
        if not consistent:
            return fail(EXIT_FAILED, "live tree diverged before any rename", live=live_digest)
        gen["history"].append(f"recovered pre-snapshot crash at {_utcnow()}")
        write_json_fsync(lab / "generation-manifest.json", gen)
        journal_p.unlink()
        print(f"RECOVER-OK generation={gen['generation']} tree={live_digest[:12]}", flush=True)
        return EXIT_OK
    for d in DATA_DIRS:
        aside = snap / "aside" / d
        if aside.is_dir():
            if (live / d).is_dir():
                shutil.rmtree(live / d)
            os.replace(aside, live / d)
            print(f"recover: restored {d} from aside", flush=True)
    for d in DATA_DIRS:
        if not (live / d).is_dir() and (snap / d).is_dir():
            shutil.copytree(snap / d, live / d)
            print(f"recover: re-materialised missing {d} from snapshot", flush=True)
    for f in TRACKED_FILES:
        if (snap / f).is_file():
            cur = live / f
            if cur.is_file() and sha256_file(cur) != sha256_file(snap / f):
                shutil.copy2(snap / f, cur)
                print(f"recover: reverted {f} to pre-promote bytes", flush=True)
    expected = _snapshot_payload_digest(snap)
    live_digest = tree_digest(live)
    consistent = (expected == live_digest)
    print(f"recover: restored tree={live_digest[:12]} "
          f"expected(pre-promote)={expected[:12] if expected else None} "
          f"consistent={consistent}", flush=True)
    if not consistent:
        return fail(EXIT_FAILED, "recovery did not converge to a consistent generation",
                    live=live_digest, expected=expected)
    gen = json.loads((lab / "generation-manifest.json").read_text(encoding="utf-8"))
    gen["history"].append(f"recovered from {state} at {_utcnow()}")
    write_json_fsync(lab / "generation-manifest.json", gen)
    journal_p.unlink()
    print(f"RECOVER-OK generation={gen['generation']} tree={live_digest[:12]}", flush=True)
    return EXIT_OK

def rollback(lab: Path) -> int:
    snaps = sorted((lab / "snapshots").iterdir()) if (lab / "snapshots").is_dir() else []
    snaps = [s for s in snaps if s.is_dir() and s.name != "_recover_check"]
    if not snaps:
        return fail(EXIT_MISSING, "no snapshot available for rollback")
    snap = snaps[-1]
    live = lab / "live"
    if not acquire_lock(lab):
        return fail(EXIT_UNAVAIL, "lock held; cannot rollback now")
    try:
        restored = []
        for d in DATA_DIRS:
            if (snap / d).is_dir():
                if (live / d).is_dir():
                    shutil.rmtree(live / d)
                shutil.copytree(snap / d, live / d)
                restored.append(d)
        for f in TRACKED_FILES:
            if (snap / f).is_file():
                shutil.copy2(snap / f, live / f)
                restored.append(f)
        gen = json.loads((lab / "generation-manifest.json").read_text(encoding="utf-8"))
        gen["history"].append(f"rollback to {snap.name} at {_utcnow()}")
        gen["tree_digest"] = tree_digest(live)
        write_json_fsync(lab / "generation-manifest.json", gen)
        exp = _snapshot_payload_digest(snap)
        ok = (tree_digest(live) == exp)
        print(f"rollback-ok restored={restored} reverify={ok} tree={gen['tree_digest'][:12]}",
              flush=True)
        return EXIT_OK if ok else fail(EXIT_FAILED, "rollback re-verify mismatch")
    finally:
        release_lock(lab)

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="T20 transactional lab (repo-outside only)")
    ap.add_argument("--lab", default=str(LAB_DEFAULT))
    ap.add_argument("--seed", action="store_true", help="build a fresh lab")
    ap.add_argument("--promote", action="store_true")
    ap.add_argument("--recover", action="store_true")
    ap.add_argument("--rollback", action="store_true")
    ap.add_argument("--crash-at", default=None, choices=["A", "B", "B2", "C", "D"])
    args = ap.parse_args(argv)
    lab = ensure_outside_repo(Path(args.lab))
    if args.seed:
        info = seed_lab(lab)
        print(f"seed-ok live={info['live_digest'][:12]} "
              f"candidate={info['candidate_digest'][:12]}", flush=True)
        return EXIT_OK
    if args.recover:
        return recover(lab)
    if args.rollback:
        return rollback(lab)
    if args.promote:
        return promote(lab, crash_at=args.crash_at)
    ap.print_help()
    return EXIT_MISSING

if __name__ == "__main__":
    sys.exit(main())
