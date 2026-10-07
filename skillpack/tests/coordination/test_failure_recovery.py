"""Fixture 2: failure recovery, modelled on the real wave6 incident.

Wave 6: test-adapt-community snapshots `git status --porcelain` for its
"true tree unchanged" assertion while another agent was writing files,
so it misfired exit 30; an isolated rerun was 0.
Step 1: snapshot a fixture tree, let a concurrent writer disturb it
        mid-check -> detector reports dirty, exit 30 (reproduces it).
Step 2: rerun the same check on an isolated copy with no writer ->
        exit 0 (quarantine rerun recovers).
Step 3: an expired lease blocks writes (exit 20); the coordinator
        releases it and a renewed lease passes (exit 0) while the
        verified tree file is byte-identical throughout.
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
VALIDATOR = os.path.join(ROOT, "scripts", "check-coordination-ownership.py")
CONTRACT = os.path.join(ROOT, "docs", "coordination", "ownership-contract.json")

DETECTOR = (
    "import os, sys\n"
    "base = sys.argv[1]\n"
    "before = sorted(os.listdir(base))\n"
    "marker = os.path.join(base, '.concurrent-write')\n"
    "if os.path.exists(marker):\n"
    "    open(os.path.join(base, 'intruder.txt'), 'w').write('x')\n"
    "after = sorted(os.listdir(base))\n"
    "if before != after:\n"
    "    print('FAIL suite/real repository state is unchanged -- tree moved mid-check')\n"
    "    sys.exit(30)\n"
    "print('tree unchanged')\n"
)

def run_detector(tree):
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as handle:
        handle.write(DETECTOR)
        script = handle.name
    proc = subprocess.run([PY, script, tree], capture_output=True, text=True)
    os.unlink(script)
    return proc

def run_claims(claims):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as handle:
        json.dump({"claims": claims}, handle)
        path = handle.name
    proc = subprocess.run([PY, VALIDATOR, "--contract", CONTRACT, "--claims", path,
                           "--now", "2026-10-01T12:00:00+00:00"], capture_output=True, text=True)
    os.unlink(path)
    return proc

def main():
    work = tempfile.mkdtemp(prefix="t17-recovery-")
    try:
        tree = os.path.join(work, "tree")
        os.mkdir(tree)
        open(os.path.join(tree, "verified.txt"), "w").write("verified content")
        before = open(os.path.join(tree, "verified.txt"), "rb").read()
        # Step 1: concurrent writer disturbs the check.
        open(os.path.join(tree, ".concurrent-write"), "w").write("another agent is writing")
        proc = run_detector(tree)
        print("disturbed check: exit %d" % proc.returncode)
        if proc.returncode != 30:
            print("FIXTURE BROKEN: disturbed tree must exit 30")
            return 1
        # Step 2: isolated rerun recovers.
        quiet = os.path.join(work, "quiet")
        shutil.copytree(tree, quiet, ignore=shutil.ignore_patterns(".concurrent-write", "intruder.txt"))
        proc = run_detector(quiet)
        print("isolated rerun: exit %d" % proc.returncode)
        if proc.returncode != 0:
            print("FIXTURE BROKEN: isolated rerun must exit 0")
            return 1
        # Step 3: expired lease blocks, release + renew recovers.
        stale = [{"agent": "B", "card": "B/T12+T14", "wave": "wave2",
                  "files": ["docs/community/SOURCE-BUNDLE.md"],
                  "lease": {"token": "old", "expires_utc": "2020-01-01T00:00:00+00:00"}}]
        proc = run_claims(stale)
        print("expired lease: exit %d" % proc.returncode)
        if proc.returncode != 20:
            print("FIXTURE BROKEN: expired lease must exit 20")
            return 1
        renewed = [{"agent": "B", "card": "B/T12+T14", "wave": "wave2",
                    "files": ["docs/community/SOURCE-BUNDLE.md"],
                    "lease": {"token": "new", "expires_utc": "2099-01-01T00:00:00+00:00"}}]
        proc = run_claims(renewed)
        print("renewed lease: exit %d" % proc.returncode)
        if proc.returncode != 0:
            print("FIXTURE BROKEN: renewed lease must exit 0")
            return 1
        if open(os.path.join(tree, "verified.txt"), "rb").read() != before:
            print("FIXTURE BROKEN: verified tree was touched")
            return 1
        print("fixture ok: 30 -> isolated 0; stale lease 20 -> renewed 0; verified tree intact")
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)

if __name__ == "__main__":
    sys.exit(main())
