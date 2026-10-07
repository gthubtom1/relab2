#!/usr/bin/env python3
"""T25 case-lifecycle lab (spec 17.24 + 17.25): lease, checkpoint/resume,
idempotent artifacts and numeric budget. Test fixture only: operates on a
given --dir (defaults to the OS temp dir), never on work/<case> or any repo
path.

Lease file: <dir>/<case>.lease.json (atomic O_CREAT|O_EXCL acquire).
Checkpoint: <dir>/<case>.checkpoint.json (tmp + fsync + os.replace).
Artifacts: <dir>/<case>.artifacts/<sha256(name)>.bin + .meta.json.
Artifact id is content-addressed; repeating the same write is a no-op
(IDEMPOTENT_SKIP, mtime untouched). A different payload under the same name
is rejected (blocked) instead of overwriting evidence.

Exit codes follow spec 4.7: 0 ok, 20 blocked (lease denied / token mismatch /
budget exceeded), 30 internal failure.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

BUDGET_MAX_ITEMS = 50  # mirrors T11 MAX_TOTAL_REFERENCES

def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

def atomic_write(path: Path, data: bytes) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)

def case_paths(root: Path, case: str) -> dict[str, Path]:
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in case) or "case"
    art = root / f"{safe}.artifacts"
    return {
        "lease": root / f"{safe}.lease.json",
        "checkpoint": root / f"{safe}.checkpoint.json",
        "artifacts": art,
    }

def read_lease(p: Path) -> dict | None:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except Exception as exc:
        print(f"failed: unreadable lease file: {exc}")
        sys.exit(30)

def lease_valid(lease: dict) -> bool:
    try:
        exp = datetime.fromisoformat(lease["lease_expires_at"].replace("Z", "+00:00"))
        return exp > datetime.now(timezone.utc)
    except Exception:
        return False

def cmd_acquire(a: argparse.Namespace) -> int:
    paths = case_paths(a.dir, a.case)
    lease_id = hashlib.sha256(f"{a.case}|{a.owner}|{time.time_ns()}".encode()).hexdigest()[:16]
    doc = {
        "case_id": a.case,
        "owner": a.owner,
        "lease_id": lease_id,
        "lease_expires_at": datetime.fromtimestamp(
            time.time() + a.ttl, tz=timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "generation": 1,
    }
    existing = read_lease(paths["lease"])
    if existing is not None and lease_valid(existing) and existing.get("owner") != a.owner:
        print(f"LEASE_DENIED: case {a.case!r} held by {existing.get('owner')!r} "
              f"until {existing.get('lease_expires_at')} (generation {existing.get('generation')})")
        return 20
    if existing is not None and lease_valid(existing):
        print(f"LEASE_REACQUIRED: same owner {a.owner!r} keeps lease {existing.get('lease_id')}")
        return 0
    if existing is not None:
        doc["generation"] = int(existing.get("generation", 1)) + 1
        print(f"LEASE_TAKEOVER: expired lease of {existing.get('owner')!r} superseded "
              f"(generation {doc['generation']})")
    try:
        fd = os.open(str(paths["lease"]), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        # Lost the race: someone else holds it now.
        rival = read_lease(paths["lease"])
        print(f"LEASE_DENIED: concurrent acquire won by {rival.get('owner') if rival else '?'}")
        return 20
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False)
        fh.flush()
        os.fsync(fh.fileno())
    print(f"LEASE_ACQUIRED: case={a.case} owner={a.owner} lease={lease_id} generation={doc['generation']}")
    return 0

def require_lease(paths: dict[str, Path], case: str, lease_id: str) -> dict:
    lease = read_lease(paths["lease"])
    if lease is None or not lease_valid(lease) or lease.get("lease_id") != lease_id:
        have = lease.get("lease_id") if lease else None
        print(f"LEASE_DENIED: write to case {case!r} refused "
              f"(want lease {lease_id!r}, have {have!r}; expired or foreign)")
        sys.exit(20)
    return lease

def cmd_write(a: argparse.Namespace) -> int:
    paths = case_paths(a.dir, a.case)
    lease = require_lease(paths, a.case, a.lease_id)
    paths["artifacts"].mkdir(parents=True, exist_ok=True)
    aid = hashlib.sha256(a.artifact.encode("utf-8")).hexdigest()[:16]
    blob = paths["artifacts"] / f"{aid}.bin"
    meta = paths["artifacts"] / f"{aid}.meta.json"
    payload = a.data.encode("utf-8")
    if blob.exists():
        if blob.read_bytes() == payload:
            print(f"IDEMPOTENT_SKIP: artifact {a.artifact!r} (id {aid}) already present, "
                  f"no second side effect (generation stays {lease.get('generation')})")
            return 0
        print(f"blocked: artifact {a.artifact!r} (id {aid}) exists with different bytes; "
              f"refusing to overwrite evidence")
        return 20
    atomic_write(blob, payload)
    atomic_write(meta, json.dumps({"artifact": a.artifact, "id": aid,
                                   "sha256": hashlib.sha256(payload).hexdigest(),
                                   "lease_id": a.lease_id, "at": utcnow()},
                                  ensure_ascii=False).encode("utf-8"))
    lease["generation"] = int(lease.get("generation", 1)) + 1
    atomic_write(paths["lease"], json.dumps(lease, ensure_ascii=False).encode("utf-8"))
    print(f"ARTIFACT_WRITTEN: {a.artifact!r} id={aid} generation={lease['generation']}")
    return 0

def cmd_release(a: argparse.Namespace) -> int:
    paths = case_paths(a.dir, a.case)
    lease = read_lease(paths["lease"])
    if lease is None or lease.get("lease_id") != a.lease_id:
        print(f"LEASE_DENIED: release refused (foreign or missing lease)")
        return 20
    paths["lease"].unlink()
    print(f"LEASE_RELEASED: case={a.case} lease={a.lease_id}")
    return 0

def resume_token(case: str, generation: int, profile: str) -> str:
    return hashlib.sha256(f"{case}|{generation}|{profile}".encode()).hexdigest()[:16]

def cmd_checkpoint(a: argparse.Namespace) -> int:
    paths = case_paths(a.dir, a.case)
    lease = require_lease(paths, a.case, a.lease_id)
    doc = {
        "case_id": a.case,
        "generation": int(lease.get("generation", 1)),
        "profile": a.profile,
        "checkpoint_id": hashlib.sha256(f"{a.case}|{time.time_ns()}".encode()).hexdigest()[:16],
        "resume_token": resume_token(a.case, int(lease.get("generation", 1)), a.profile),
        "at": utcnow(),
    }
    atomic_write(paths["checkpoint"], json.dumps(doc, ensure_ascii=False).encode("utf-8"))
    print(f"CHECKPOINT_WRITTEN: id={doc['checkpoint_id']} generation={doc['generation']} "
          f"resume_token={doc['resume_token']}")
    return 0

def cmd_resume(a: argparse.Namespace) -> int:
    paths = case_paths(a.dir, a.case)
    try:
        doc = json.loads(paths["checkpoint"].read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"blocked: no checkpoint for case {a.case!r}")
        return 20
    want = resume_token(doc.get("case_id", ""), int(doc.get("generation", -1)), doc.get("profile", ""))
    if a.token != want or doc.get("case_id") != a.case:
        print(f"RESUME_DENIED: token/case/generation/profile mismatch for case {a.case!r} "
              f"(checkpoint generation {doc.get('generation')}); refusing, back to review")
        return 20
    print(f"RESUMED: case={a.case} generation={doc.get('generation')} profile={doc.get('profile')}")
    return 0

def cmd_budget(a: argparse.Namespace) -> int:
    if a.items > BUDGET_MAX_ITEMS:
        print(f"blocked: loading budget exceeded: {a.items} items > {BUDGET_MAX_ITEMS}; "
              f"stopped and reported (failure_reason=budget_exceeded)")
        return 20
    print(f"ok: budget {a.items}/{BUDGET_MAX_ITEMS} items within limits")
    return 0

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="T25 case-lifecycle lab fixture")
    ap.add_argument("--dir", default=None, help="lab root (default: OS temp dir)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("acquire")
    p.add_argument("--case", required=True)
    p.add_argument("--owner", required=True)
    p.add_argument("--ttl", type=int, default=600)
    p = sub.add_parser("write")
    p.add_argument("--case", required=True)
    p.add_argument("--lease-id", required=True)
    p.add_argument("--artifact", required=True)
    p.add_argument("--data", required=True)
    p = sub.add_parser("release")
    p.add_argument("--case", required=True)
    p.add_argument("--lease-id", required=True)
    p = sub.add_parser("checkpoint")
    p.add_argument("--case", required=True)
    p.add_argument("--lease-id", required=True)
    p.add_argument("--profile", required=True)
    p = sub.add_parser("resume")
    p.add_argument("--case", required=True)
    p.add_argument("--token", required=True)
    p = sub.add_parser("budget")
    p.add_argument("--items", type=int, required=True)
    a = ap.parse_args(argv)
    import tempfile
    a.dir = Path(a.dir) if a.dir else Path(tempfile.gettempdir()) / "t25-lab"
    a.dir.mkdir(parents=True, exist_ok=True)
    try:
        if a.cmd == "acquire":
            return cmd_acquire(a)
        if a.cmd == "write":
            return cmd_write(a)
        if a.cmd == "release":
            return cmd_release(a)
        if a.cmd == "checkpoint":
            return cmd_checkpoint(a)
        if a.cmd == "resume":
            return cmd_resume(a)
        if a.cmd == "budget":
            return cmd_budget(a)
    except SystemExit as e:
        return int(e.code or 0)
    except Exception as exc:  # fail-closed
        print(f"failed: internal error: {exc}")
        return 30
    return 30

if __name__ == "__main__":
    sys.exit(main())
