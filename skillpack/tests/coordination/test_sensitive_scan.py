"""Fixture 5: sensitive-output scan reusing the T06 scanner pattern set.

Dangerous samples are assembled at runtime (concatenation), so no
literal ever sits in this file. The fixture proves the scanner's own
patterns catch the sample, and that redact-output.py (which imports
that exact pattern set) removes every hit.
Exit codes: 0 fixture behaved as specified | 1 fixture broken.
"""
import importlib.util
import os
import re
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
SCANNER = os.path.join(ROOT, "skills", "scripts", "verify-repository-security.py")
REDACT = os.path.join(ROOT, "scripts", "redact-output.py")

def build_samples():
    key_id = "AK" + "IA" + "0" * 16
    token = "gh" + "p_" + "a" * 32
    key_block = "-----BEGIN " + "RSA PRIVATE KEY-----"
    return "deploy key %s and token %s\n%s\nplain line\n" % (key_id, token, key_block)

def main():
    spec = importlib.util.spec_from_file_location("repo_security_gate", SCANNER)
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)
    patterns = list((gate.SECRET_PATTERNS or {}).values())
    sample = build_samples()
    raw_hits = sum(len(re.findall(pattern, sample)) for pattern in patterns)
    print("scanner patterns on raw sample: %d hit(s)" % raw_hits)
    if raw_hits < 3:
        print("FIXTURE BROKEN: sample must trip at least 3 scanner patterns")
        return 1
    work = tempfile.mkdtemp(prefix="t17-redact-")
    raw_path = os.path.join(work, "raw.txt")
    clean_path = os.path.join(work, "clean.txt")
    open(raw_path, "w", encoding="utf-8").write(sample)
    proc = subprocess.run([PY, REDACT, "--scanner", SCANNER, "--in", raw_path, "--out", clean_path],
                          capture_output=True, text=True)
    if proc.returncode != 0:
        print("FIXTURE BROKEN: redaction failed: %s" % proc.stderr.strip())
        return 1
    clean = open(clean_path, encoding="utf-8").read()
    left = sum(len(re.findall(pattern, clean)) for pattern in patterns)
    if left != 0:
        print("FIXTURE BROKEN: %d hit(s) survived redaction" % left)
        return 1
    if "[REDACTED]" not in clean or "plain line" not in clean:
        print("FIXTURE BROKEN: placeholder missing or benign text altered")
        return 1
    print("fixture ok: %d raw hits -> 0 after redact, benign text intact (%s)" % (raw_hits, proc.stderr.strip()))
    return 0

if __name__ == "__main__":
    sys.exit(main())
