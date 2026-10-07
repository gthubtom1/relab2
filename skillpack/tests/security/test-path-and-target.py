#!/usr/bin/env python3
"""T22 negative controls driver: every escape morphology must be DENIED.

Each fixture builds the escape for real (lab lives OUTSIDE the repository at
<repo>/../work/T22-lab, never inside the worktree; override with
``REVERSE_SKILL_WORK_DIR``) and drives the
guard `skills/scripts/verify-path-and-target.py` as a subprocess so the
evidence below carries real exit codes (20 = DENY per spec 4.7).

Dangerous samples are stored MASKED and DISCONNECTED in fixtures/*.json
(host split into labels, scheme split); the real string exists only in
process memory at runtime, never on disk in one piece.

Exit codes: 0 = every negative was blocked (guard held); 1 = at least one
escape was ALLOWED (guard failure). Read-only wrt the repository.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
REPO = HERE.parents[2]
GUARD = REPO / "skills" / "scripts" / "verify-path-and-target.py"
FIXDIR = HERE.parent / "fixtures"
LAB = Path(os.environ.get("REVERSE_SKILL_WORK_DIR")
           or (REPO.parent / "work")) / "T22-lab"
PY = sys.executable

FAILURES: list[str] = []

def load_guard():
    spec = importlib.util.spec_from_file_location("t22_guard", GUARD)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def join_host(labels: list[str]) -> str:
    return ".".join(labels)

def run_cli(*args: str) -> tuple[int, str]:
    proc = subprocess.run([PY, str(GUARD), *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", cwd=str(REPO))
    return proc.returncode, (proc.stdout + proc.stderr).strip()

def expect_deny(fid: str, code: int, out: str) -> None:
    if code == 20 and "DENY" in out:
        print(f"NEGATIVE {fid}: exit=20 {out[:160]}")
    else:
        FAILURES.append(fid)
        print(f"GUARD-HOLE {fid}: exit={code} {out[:160]}")

def fresh_lab() -> Path:
    if LAB.exists():
        shutil.rmtree(LAB, ignore_errors=True)
    (LAB / "case").mkdir(parents=True)
    return LAB

def main() -> int:
    guard = load_guard()
    print(f"guard : {GUARD.as_posix()}")
    print(f"lab   : {LAB.as_posix()} (outside repo)")
    print(f"fixtures: {len(list(FIXDIR.glob('*.json')))} files")

    lab = fresh_lab()
    root = str(lab / "case")

    # F1 path traversal (real string through live checker)
    code, out = run_cli("--root", root, "--check-path", "..\\..\\Windows\\System32\\calc.exe")
    expect_deny("F1-traversal", code, out)

    # F2 symlink target shape (string level; live symlink needs privilege, see DEVIATIONS)
    fix = json.loads((FIXDIR / "t22-f02-symlink-shape.json").read_text(encoding="utf-8"))
    target = "/".join(fix["target_parts"])
    ok, msg = guard.parse_symlink_target_shape(target)
    expect_deny("F2-symlink-shape", 20 if not ok else 0, msg)
    probe = lab / "symprobe"
    try:
        os.symlink(str(lab / "case"), str(probe))
        print(f"NOTE F2-live: symlink creation unexpectedly succeeded: {probe}")
        code, out = run_cli("--root", root, "--check-path", "..\\symprobe\\scope.md")
        expect_deny("F2-live-symlink", code, out)
    except OSError as exc:
        print(f"NOTE F2-live: symlink not constructible here ({exc}); recorded UNVERIFIED")

    # F3 junction escape (really built with mklink /J, no privilege needed)
    outside = lab / "outside"
    outside.mkdir(exist_ok=True)
    (outside / "secret.txt").write_text("outside", encoding="utf-8")
    junction = Path(root) / "link"
    subprocess.run(["cmd", "/c", "mklink", "/J", str(junction), str(outside)],
                   capture_output=True, text=True)
    if os.path.exists(str(junction)):
        code, out = run_cli("--root", root, "--check-path", "link\\secret.txt")
        expect_deny("F3-junction", code, out)
    else:
        FAILURES.append("F3-junction-setup")
        print("GUARD-HOLE F3-junction-setup: mklink /J failed")

    # F4 hardlink (really built with os.link)
    src = outside / "orig.bin"
    src.write_bytes(b"payload-bytes")
    hard = Path(root) / "hard.bin"
    os.link(str(src), str(hard))
    code, out = run_cli("--root", root, "--check-path", "hard.bin")
    expect_deny("F4-hardlink", code, out)

    # F5 UNC device path
    fix = json.loads((FIXDIR / "t22-f05-unc.json").read_text(encoding="utf-8"))
    unc = "".join(fix["prefix_parts"]) + join_host(fix["server_labels"]) + "\\" + fix["share"]
    code, out = run_cli("--root", root, "--check-path", unc)
    expect_deny("F5-unc", code, out)

    # F6 drive-letter escape
    code, out = run_cli("--root", root, "--check-path", "C:\\Windows\\System32")
    expect_deny("F6-drive", code, out)

    # F7 case-cloaked reserved name (case-sensitive allowlists would miss CoN)
    code, out = run_cli("--root", root, "--check-path", "case\\CoN.txt")
    expect_deny("F7-casefold", code, out)

    # F8 DNS rebinding (offline answers, no sockets)
    fix = json.loads((FIXDIR / "t22-f08-dns-rebind.json").read_text(encoding="utf-8"))
    host = join_host(fix["host_labels"])
    ok, msg = guard.check_dns_binding(host, fix["answers_rounds"], fix["allow_cidrs"])
    expect_deny("F8-dns-rebind", 20 if not ok else 0, msg)

    # F9 redirect chain stepping off allowlist
    fix = json.loads((FIXDIR / "t22-f09-redirect.json").read_text(encoding="utf-8"))
    scheme = "".join(fix["scheme_parts"])
    chain = [scheme + join_host(h) + p for h, p in
             zip(fix["chain_host_labels"], fix["chain_paths"])]
    ok, msg = guard.check_redirect_chain(chain, allow_hosts=[join_host(fix["allow_host_labels"])])
    expect_deny("F9-redirect", 20 if not ok else 0, msg)

    # F10 port / protocol scope violation
    fix = json.loads((FIXDIR / "t22-f10-port.json").read_text(encoding="utf-8"))
    scheme = "".join(fix["scheme_parts"])
    url = scheme + join_host(fix["host_labels"]) + ":" + str(fix["port"]) + "/"
    code, out = run_cli("--check-url", url, "--allow-host", join_host(fix["allow_host_labels"]),
                        "--allow-port", "443", "--allow-scheme", "https")
    expect_deny("F10-port", code, out)

    # Positive control: benign relative artifact must stay ALLOW
    code, out = run_cli("--root", root, "--check-path", "work\\scope.md")
    if code == 0 and "ALLOW" in out:
        print(f"POSITIVE benign-relative: exit=0 {out[:120]}")
    else:
        FAILURES.append("POSITIVE-benign")
        print(f"GUARD-HOLE POSITIVE-benign: exit={code} {out[:120]}")

    print(f"lab left at: {LAB.as_posix()}")
    if FAILURES:
        print(f"FAIL test-path-and-target: {len(FAILURES)} hole(s): {FAILURES}")
        return 1
    print("PASS test-path-and-target: every negative blocked, positive allowed")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
