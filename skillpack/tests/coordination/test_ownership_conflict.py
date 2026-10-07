"""Fixture 1: concurrent write conflict. Two cards claim the same file.

Positive: disjoint wave2 claims -> validator exit 0.
Negative: card C claims a file owned by card A scope -> exit 20.
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

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PY = _detect_python()
VALIDATOR = os.path.join(ROOT, "scripts", "check-coordination-ownership.py")
CONTRACT = os.path.join(ROOT, "docs", "coordination", "ownership-contract.json")
LEASE = {"token": "wave2-lease", "expires_utc": "2099-01-01T00:00:00+00:00"}

def run_claims(claims):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as handle:
        json.dump({"claims": claims}, handle)
        path = handle.name
    proc = subprocess.run([PY, VALIDATOR, "--contract", CONTRACT, "--claims", path],
                          capture_output=True, text=True)
    os.unlink(path)
    return proc

def main():
    clean = [
        {"agent": "A", "card": "A/U11", "wave": "wave2",
         "files": ["scripts/adapt-community.py"], "lease": LEASE},
        {"agent": "C", "card": "C/T11", "wave": "wave2",
         "files": ["skills/scripts/community-route.py"], "lease": LEASE},
    ]
    proc = run_claims(clean)
    print("clean claims: exit %d (%s)" % (proc.returncode, proc.stdout.strip()))
    if proc.returncode != 0:
        print("FIXTURE BROKEN: disjoint scopes must pass")
        return 1
    clash = [
        {"agent": "A", "card": "A/U11", "wave": "wave2",
         "files": ["scripts/adapt-community.py"], "lease": LEASE},
        {"agent": "C", "card": "C/T11", "wave": "wave2",
         "files": ["scripts/adapt-community.py"], "lease": LEASE},
    ]
    proc = run_claims(clash)
    print("clashing claims: exit %d (%s)" % (proc.returncode, proc.stdout.strip().splitlines()[0] if proc.stdout.strip() else ""))
    if proc.returncode != 20:
        print("FIXTURE BROKEN: cross-scope write must exit 20")
        return 1
    print("fixture ok: conflict refused with exit 20, clean pair passes with exit 0")
    return 0

if __name__ == "__main__":
    sys.exit(main())
