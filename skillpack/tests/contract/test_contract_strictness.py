#!/usr/bin/env python3
"""T25 contract tests: 4.6 row-by-row coverage, unknown-enum fail-closed,
budget alignment. Exit 0 = all green, 1 = any failure."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = ROOT / "skills/scripts/verify-contract-strictness.py"
ROUTE = ROOT / "skills/scripts/community-route.py"
PY = sys.executable

FAILURES: list[str] = []

def run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8")

def check(cond: bool, msg: str) -> None:
    print(("ok: " if cond else "FAIL: ") + msg)
    if not cond:
        FAILURES.append(msg)

EXPECTED_ROWS = [
    "offline-sample", "offline-ctf", "authorized-lab", "authorized-repository",
    "authorized-device", "defensive/defensive_review/defensive-review",
    "local-project/local_project", "lab/lab_only",
    "authorized/auth/authorized_target_only", "offline/offline_only (conditional)",
    "unrestricted_lab (must NOT map)",
]

def main() -> int:
    r = run([PY, str(VALIDATOR)])
    check(r.returncode == 0, f"validator exits 0 on the real tree (got {r.returncode})")
    for row in EXPECTED_ROWS:
        check(f"4.6 migration row [{row}]" in r.stdout,
              f"4.6 migration table row covered by a real assertion: [{row}]")
    for profile in ("offline_sample", "offline_ctf", "authorized_lab",
                    "authorized_target_only", "defensive_review", "local_project"):
        check(f"4.6 table-A row: {profile} ->" in r.stdout,
              f"4.6 profile->network row asserted: {profile}")
    check("no second profile vocabulary" in r.stdout, "no second profile vocabulary asserted")
    check("unlisted legacy values -> needs_review" in r.stdout, "unknown legacy values fail closed")
    check("17.22 conflict" in r.stdout and "-> blocked" in r.stdout,
          "profile/caller network-mode conflict fails closed")
    check("both present and equal" in r.stdout, "path/adapted_path invariant measured")

    n = run([PY, str(VALIDATOR), "--selftest-unknown"])
    check(n.returncode == 20, f"injected unknown enums rejected with exit 20 (got {n.returncode})")
    check("EVIL_PROFILE_X" in n.stdout, "rejection names the unknown value")

    b = run([PY, str(ROUTE), "--hint", "apk 反编译", "--limit", "2"])
    check(b.returncode == 0, f"real community-route query exits 0 (got {b.returncode})")
    check("budget:" in b.stdout, "real query reports its loading budget")
    check("profile=" in b.stdout and "network=" in b.stdout,
          "real query reports derived profile -> network_profile")

    print(f"---- {'ALL GREEN' if not FAILURES else f'{len(FAILURES)} FAILURES'} ----")
    return 1 if FAILURES else 0

if __name__ == "__main__":
    sys.exit(main())
