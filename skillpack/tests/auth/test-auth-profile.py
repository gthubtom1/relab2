#!/usr/bin/env python3
"""T15 negative controls driver: every authorization defect must be BLOCKED.

Each fixture builds a real case for real (lab lives OUTSIDE the repository at
<repo>/../work/T15-lab, never inside the worktree; override with
``REVERSE_SKILL_WORK_DIR``) and drives the
guard `skills/scripts/verify-auth-profile.py` as a subprocess so the evidence
below carries real exit codes (20 = BLOCKED per spec 4.7, 0 = ALLOW).

Hosts are stored MASKED and DISCONNECTED in fixtures/*.json (labels only);
the real string exists only in process memory at runtime, never on disk in
one piece.

Exit codes: 0 = every negative blocked and the positive allowed (guard held);
1 = at least one escape was ALLOWED or the positive was BLOCKED.
Read-only wrt the repository.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
REPO = HERE.parents[2]
GUARD = REPO / "skills" / "scripts" / "verify-auth-profile.py"
FIXDIR = HERE.parent
LAB = Path(os.environ.get("REVERSE_SKILL_WORK_DIR")
           or (REPO.parent / "work")) / "T15-lab"
PY = sys.executable

FAILURES: list[str] = []

SCOPE_TEMPLATE = """# Case Scope

## meta
- case_id: {case_id}
- created: 2026-09-30T00:00:00Z
- operator: t15-test
- project_root: {lab}
- primary_skill: reverse-engineering/SKILL.md
- lead_role: lead

## auth
- status: granted
- basis: lab_only
- evidence_of_auth: ticket:T15-LAB-001
- MUST NOT proceed if status != granted

## in_scope
- assets:
  - {host}
- surfaces: [network]
- activities: [recon]

## out_of_scope
- assets: []
- activities: [dos, phishing_real_users, unrestricted_exfil]

## network_profile
- mode: authorized_target_only
- notes: |
    lab only

## signoff
- ready_for_act: true
- checklist:
  - [x] auth.status = granted
"""

def join_host(labels: list[str]) -> str:
    return ".".join(labels)

def base_auth(case_id: str, host: str) -> dict:
    return {
        "schemaVersion": "1.0",
        "case_id": case_id,
        "approver": "t15-approver",
        "issued_at": "2026-01-01T00:00:00Z",
        "expires_at": "2030-01-01T00:00:00Z",
        "target_allowlist": [host],
        "allowed_actions": ["recon", "active_scan"],
        "evidence_reference": "ticket:T15-LAB-001",
        "revocation_status": "active",
        "execution_profile": {
            "filesystem_allowlist": ["case/evidence", "case/report"],
            "network_egress_allowlist": [host],
            "credential_policy": "no-credentials-in-repo",
            "max_runtime_s": 3600,
            "max_retries": 2,
            "max_requests": 100,
            "max_artifact_bytes": 1048576,
            "requires_human_confirmation": True,
        },
        "human_confirmations": {
            "active_scan": {"by": "t15-approver", "at": "2026-02-01T00:00:00Z"},
        },
    }

def run_cli(*args: str) -> tuple[int, str]:
    proc = subprocess.run([PY, str(GUARD), *args], capture_output=True,
                          text=True, encoding="utf-8", errors="replace",
                          cwd=str(REPO))
    return proc.returncode, (proc.stdout + proc.stderr).strip()

def expect_blocked(fid: str, code: int, out: str) -> None:
    if code == 20 and "BLOCKED" in out:
        print(f"NEGATIVE {fid}: exit=20 {out.splitlines()[0][:150]}")
    else:
        FAILURES.append(fid)
        print(f"GUARD-HOLE {fid}: exit={code} {out[:150]}")

def expect_allowed(fid: str, code: int, out: str) -> None:
    if code == 0 and "ALLOW" in out:
        print(f"POSITIVE {fid}: exit=0 {out.splitlines()[0][:150]}")
    else:
        FAILURES.append(fid)
        print(f"GUARD-HOLE {fid}: exit={code} {out[:150]}")

def build_case(name: str, host: str, mutate_auth=None,
               omit: str | None = None) -> Path:
    case = LAB / name
    if case.exists():
        shutil.rmtree(case, ignore_errors=True)
    case.mkdir(parents=True)
    (case / "scope.md").write_text(
        SCOPE_TEMPLATE.format(case_id=name, lab=LAB.as_posix(), host=host),
        encoding="utf-8")
    if omit != "auth-profile.json":
        auth = base_auth(name, host)
        if mutate_auth:
            mutate_auth(auth)
        (case / "auth-profile.json").write_text(
            json.dumps(auth, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
    return case

def issue(case: Path, risk: str = "medium") -> tuple[int, str]:
    return run_cli("--case-root", str(case), "--issue-attestation",
                   "--risk", risk)

def main() -> int:
    print(f"guard : {GUARD.as_posix()}")
    print(f"lab   : {LAB.as_posix()} (outside repo)")
    if LAB.exists():
        shutil.rmtree(LAB, ignore_errors=True)
    LAB.mkdir(parents=True)

    # F1 expired authorization
    fix = json.loads((FIXDIR / "t15-f01-expired.json").read_text(encoding="utf-8"))
    host = join_host(fix["allow_host_labels"])
    case = build_case("t15-f01", host,
                      mutate_auth=lambda a: a.update({"expires_at": fix["expires_at"]}))
    issue(case)
    expect_blocked("F1-expired", *run_cli("--case-root", str(case), "--action", "recon"))

    # F2 blank target allowlist
    fix = json.loads((FIXDIR / "t15-f02-empty-allowlist.json").read_text(encoding="utf-8"))
    host = join_host(fix["allow_host_labels"])
    case = build_case("t15-f02", host,
                      mutate_auth=lambda a: a.update(
                          {"target_allowlist": fix["force_allowlist"],
                           "execution_profile": {**a["execution_profile"],
                                                 "network_egress_allowlist": []}}))
    issue(case)
    expect_blocked("F2-empty-allowlist", *run_cli("--case-root", str(case)))

    # F3 out-of-scope action
    fix = json.loads((FIXDIR / "t15-f03-action-out-of-scope.json").read_text(encoding="utf-8"))
    host = join_host(fix["allow_host_labels"])
    case = build_case("t15-f03", host)
    issue(case)
    expect_blocked("F3-action-out-of-scope",
                   *run_cli("--case-root", str(case), "--action", fix["action"]))

    # F4 dangerous action without human confirmation
    fix = json.loads((FIXDIR / "t15-f04-dangerous-unapproved.json").read_text(encoding="utf-8"))
    host = join_host(fix["allow_host_labels"])
    def mutate_f4(auth: dict) -> None:
        auth.update({"allowed_actions": fix["allowed_actions"],
                     "human_confirmations": {}})
    case = build_case("t15-f04", host, mutate_auth=mutate_f4)
    issue(case)
    expect_blocked("F4-dangerous-unapproved",
                   *run_cli("--case-root", str(case), "--action", fix["action"]))

    # F5 missing auth proof (issue itself must also refuse)
    fix = json.loads((FIXDIR / "t15-f05-missing-proof.json").read_text(encoding="utf-8"))
    host = join_host(fix["allow_host_labels"])
    case = build_case("t15-f05", host, omit=fix["omit"])
    icode, iout = issue(case)
    if icode == 20:
        print(f"NEGATIVE F5-issue-refused: exit=20 {iout.splitlines()[0][:150]}")
    else:
        FAILURES.append("F5-issue-refused")
        print(f"GUARD-HOLE F5-issue-refused: exit={icode} {iout[:150]}")
    expect_blocked("F5-missing-proof", *run_cli("--case-root", str(case)))

    # F6 ready_for_act text alone (valid proof + scope, no attestation)
    fix = json.loads((FIXDIR / "t15-f06-ready-text-only.json").read_text(encoding="utf-8"))
    host = join_host(fix["allow_host_labels"])
    case = build_case("t15-f06", host)
    issue(case)
    (case / "attestation.json").unlink()
    expect_blocked("F6-ready-text-only", *run_cli("--case-root", str(case)))
    # --force must not bypass either
    code, out = run_cli("--case-root", str(case), "--force")
    expect_blocked("F6-force-no-bypass", code, out)

    # POSITIVE: fully-bound case allows a listed, confirmed action
    host = "target-00.t15.local"
    case = build_case("t15-ok", host)
    issue(case)
    expect_allowed("P0-valid-recon",
                   *run_cli("--case-root", str(case), "--action", "recon"))
    expect_allowed("P1-valid-dangerous-confirmed",
                   *run_cli("--case-root", str(case), "--action", "active_scan"))

    print(f"lab left at: {LAB.as_posix()}")
    if FAILURES:
        print(f"FAIL test-auth-profile: {len(FAILURES)} hole(s): {FAILURES}")
        return 1
    print("PASS test-auth-profile: every negative blocked, positives allowed")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
