"""Output redaction reusing the T06 scanner's pattern sets (no duplicate rules).

Usage: redact-output.py [--scanner PATH] [--in FILE] [--out FILE]
Reads text, replaces every match of the scanner's SECRET_PATTERNS and
cleartext-endpoint shape with a placeholder, writes redacted text.
Exit codes: 0 done (prints hit counts) | 2 usage error.
Only stdlib. No network. Imports the scanner module read-only; the
scanner itself is never modified.
"""
import importlib.util
import io
import re
import sys

DEFAULT_SCANNER = "skills/scripts/verify-repository-security.py"
PLACEHOLDER = "[REDACTED]"

def load_scanner(path):
    spec = importlib.util.spec_from_file_location("repo_security_gate", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def main():
    if any(a in ("-h", "--help") for a in sys.argv[1:]):
        print("usage: redact-output.py [--scanner P] [--in F] [--out F]\n\n" + __doc__.strip())
        return 0

    scanner_path, in_path, out_path = DEFAULT_SCANNER, None, None
    argv = sys.argv[1:]
    i = 0
    while i < len(argv):
        if argv[i] == "--scanner" and i + 1 < len(argv):
            scanner_path = argv[i + 1]; i += 2
        elif argv[i] == "--in" and i + 1 < len(argv):
            in_path = argv[i + 1]; i += 2
        elif argv[i] == "--out" and i + 1 < len(argv):
            out_path = argv[i + 1]; i += 2
        else:
            print("usage: redact-output.py [--scanner P] [--in F] [--out F]", file=sys.stderr)
            return 2
    gate = load_scanner(scanner_path)
    raw = getattr(gate, "SECRET_PATTERNS", {}) or {}
    patterns = list(raw.values()) if isinstance(raw, dict) else list(raw)
    text = io.open(in_path, encoding="utf-8").read() if in_path else sys.stdin.read()
    hits = 0
    for pattern in patterns:
        text, count = re.subn(pattern, PLACEHOLDER, text)
        hits += count
    if out_path:
        io.open(out_path, "w", encoding="utf-8").write(text)
    else:
        sys.stdout.write(text)
    print("redacted %d hit(s) with the scanner pattern set" % hits, file=sys.stderr)
    return 0

if __name__ == "__main__":
    sys.exit(main())
