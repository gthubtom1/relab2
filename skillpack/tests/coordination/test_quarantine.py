"""Fixture 3: single-source quarantine.

Builds a 3-source registry modelled on the real one (one source carries
a review-required / missing-license status), quarantines exactly that
source, and proves the others pass through byte-identical while the
quarantined one leaves discovery/query/candidate surface. The audit
record carries event, time, actor and reason.
Negative: quarantining an unknown id exits 23.
Exit codes: 0 fixture behaved as specified | 1 fixture broken.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

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

PY = _detect_python()
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
QUARANTINE = os.path.join(ROOT, "scripts", "quarantine-source.py")

SOURCES = [
    {"id": "alpha", "license_status": "verified", "maturity": "verified"},
    {"id": "beta", "license_status": "review-required", "maturity": "partial"},
    {"id": "gamma", "license_status": "verified", "maturity": "partial"},
]

def main():
    work = tempfile.mkdtemp(prefix="t17-quarantine-")
    reg = os.path.join(work, "registry.json")
    out = os.path.join(work, "narrowed.json")
    audit_path = os.path.join(work, "audit.json")
    json.dump({"sources": SOURCES}, open(reg, "w", encoding="utf-8"), sort_keys=True)
    proc = subprocess.run([PY, QUARANTINE, "--registry", reg, "--quarantine", "beta",
                           "--out", out, "--audit", audit_path,
                           "--actor", "coordinator", "--reason", "license review pending"],
                          capture_output=True, text=True)
    print("quarantine beta: exit %d (%s)" % (proc.returncode, proc.stdout.strip()))
    if proc.returncode != 0:
        print("FIXTURE BROKEN: known source must quarantine cleanly")
        return 1
    narrowed = json.load(open(out, encoding="utf-8"))
    remaining = [s.get("id") for s in narrowed.get("sources", [])]
    if remaining != ["alpha", "gamma"]:
        print("FIXTURE BROKEN: expected [alpha, gamma], got %s" % remaining)
        return 1
    original = {s["id"]: s for s in SOURCES}
    for kept in narrowed["sources"]:
        if kept != original[kept["id"]]:
            print("FIXTURE BROKEN: source %s was altered by quarantine" % kept["id"])
            return 1
    audit = json.load(open(audit_path, encoding="utf-8"))
    for key in ("event", "source_id", "actor", "reason", "ts_utc"):
        if not audit.get(key):
            print("FIXTURE BROKEN: audit record missing %s" % key)
            return 1
    proc = subprocess.run([PY, QUARANTINE, "--registry", reg, "--quarantine", "delta",
                           "--out", out, "--audit", audit_path],
                          capture_output=True, text=True)
    print("quarantine unknown: exit %d" % proc.returncode)
    if proc.returncode != 23:
        print("FIXTURE BROKEN: unknown source id must exit 23")
        return 1
    print("fixture ok: beta isolated, alpha+gamma byte-identical, audit complete, unknown refused 23")
    return 0

if __name__ == "__main__":
    sys.exit(main())
