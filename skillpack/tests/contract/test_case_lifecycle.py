#!/usr/bin/env python3
"""T25 case-lifecycle tests: lease contention, checkpoint/resume binding,
idempotent artifacts, numeric budget. Exit 0 = all green, 1 = any failure."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LAB = ROOT / "skills/scripts/t25-case-lifecycle-lab.py"
PY = sys.executable

FAILURES: list[str] = []
LABDIR = Path(tempfile.mkdtemp(prefix="t25-"))
CASE = "t25-demo"

def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([PY, str(LAB), "--dir", str(LABDIR), *args],
                          capture_output=True, text=True, encoding="utf-8")

def check(cond: bool, msg: str) -> None:
    print(("ok: " if cond else "FAIL: ") + msg)
    if not cond:
        FAILURES.append(msg)

def lease_of(out: str) -> str:
    for tok in out.split():
        if tok.startswith("lease="):
            return tok.split("=", 1)[1]
    return ""

def main() -> int:
    a = run("acquire", "--case", CASE, "--owner", "agent-A")
    check(a.returncode == 0 and "LEASE_ACQUIRED" in a.stdout, "holder A acquires the lease")
    lease_a = lease_of(a.stdout)
    check(bool(lease_a), "acquire prints the lease id")

    b = run("acquire", "--case", CASE, "--owner", "agent-B")
    check(b.returncode == 20, f"concurrent holder B refused with exit 20 (got {b.returncode})")
    check("LEASE_DENIED" in b.stdout and "agent-A" in b.stdout,
          "refusal names the case and the current holder")

    w = run("write", "--case", CASE, "--lease-id", "bogus-lease", "--artifact", "note", "--data", "x")
    check(w.returncode == 20 and "LEASE_DENIED" in w.stdout,
          "write with a foreign lease is refused")

    w1 = run("write", "--case", CASE, "--lease-id", lease_a, "--artifact", "evidence-1", "--data", "bytes-1")
    check(w1.returncode == 0 and "ARTIFACT_WRITTEN" in w1.stdout, "first artifact write lands")
    blobs = list((LABDIR / f"{CASE}.artifacts").glob("*.bin"))
    check(len(blobs) == 1, "exactly one artifact blob on disk")
    mtime = blobs[0].stat().st_mtime_ns if blobs else 0
    time.sleep(0.05)
    w2 = run("write", "--case", CASE, "--lease-id", lease_a, "--artifact", "evidence-1", "--data", "bytes-1")
    check(w2.returncode == 0 and "IDEMPOTENT_SKIP" in w2.stdout,
          "repeating the same artifact write is a no-op")
    check(blobs and blobs[0].stat().st_mtime_ns == mtime, "repeat write leaves bytes/mtime untouched")
    w3 = run("write", "--case", CASE, "--lease-id", lease_a, "--artifact", "evidence-1", "--data", "DIFFERENT")
    check(w3.returncode == 20 and "refusing to overwrite evidence" in w3.stdout,
          "same name with different bytes is blocked, not overwritten")

    c = run("checkpoint", "--case", CASE, "--lease-id", lease_a, "--profile", "offline_sample")
    check(c.returncode == 0 and "CHECKPOINT_WRITTEN" in c.stdout, "checkpoint writes atomically")
    token = ""
    for tok in c.stdout.split():
        if tok.startswith("resume_token="):
            token = tok.split("=", 1)[1]
    r_bad = run("resume", "--case", CASE, "--token", "deadbeefdeadbeef")
    check(r_bad.returncode == 20 and "RESUME_DENIED" in r_bad.stdout,
          "resume with a mismatched token is refused")
    r = run("resume", "--case", CASE, "--token", token)
    check(r.returncode == 0 and "RESUMED" in r.stdout, "resume with the bound token succeeds")

    rel_bad = run("release", "--case", CASE, "--lease-id", "bogus-lease")
    check(rel_bad.returncode == 20, "release with a foreign lease is refused")
    rel = run("release", "--case", CASE, "--lease-id", lease_a)
    check(rel.returncode == 0 and "LEASE_RELEASED" in rel.stdout, "owner releases the lease")

    g_ok = run("budget", "--items", "50")
    check(g_ok.returncode == 0, "50 items fits the budget")
    g_over = run("budget", "--items", "51")
    check(g_over.returncode == 20 and "budget_exceeded" in g_over.stdout,
          "51 items stops and reports budget_exceeded with exit 20")

    print(f"---- {'ALL GREEN' if not FAILURES else f'{len(FAILURES)} FAILURES'} ----")
    return 1 if FAILURES else 0

if __name__ == "__main__":
    sys.exit(main())
