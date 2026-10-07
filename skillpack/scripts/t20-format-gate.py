#!/usr/bin/env python3
"""T20 format gate: incompatible data format must hard-block, never downgrade.

Checks a candidate's declared format against the supported set. Any unknown,
absent, or explicitly newer-major format exits non-zero with a message naming
the expected set. There is no fallback, no coercion, no silent downgrade.

Usage:
  python scripts/t20-format-gate.py --candidate <dir> [--supported fmt ...]
  python scripts/t20-format-gate.py --self-test   # lab-only negative control

Stdlib only. No network. Exit 0 compatible; exit 20 blocked.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

DEFAULT_SUPPORTED = ["t20/lab-format/1"]
EXIT_OK, EXIT_BLOCKED, EXIT_MISSING = 0, 20, 21

def check(candidate: Path, supported: list) -> tuple:
    schema_file = candidate / "schemas" / "app.json"
    if not schema_file.is_file():
        # Also accept a flat manifest for minimal candidates.
        schema_file = candidate / "format.json"
    if not schema_file.is_file():
        return False, "format declaration absent; refusing (no silent default)"
    try:
        doc = json.loads(schema_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return False, f"format declaration unparsable: {exc}; refusing"
    fmt = doc.get("format", "<absent>")
    if fmt not in supported:
        return False, (f"incompatible format {fmt!r}; supported={supported}; "
                       "refusing, no downgrade performed")
    return True, f"compatible format {fmt!r}"

def self_test() -> int:
    failures = 0
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        good = base / "good"
        (good / "schemas").mkdir(parents=True)
        (good / "schemas/app.json").write_text(
            json.dumps({"format": "t20/lab-format/1"}), encoding="utf-8")
        ok, msg = check(good, DEFAULT_SUPPORTED)
        print(f"{'PASS' if ok else 'FAIL'} compatible-accepted -- {msg}")
        failures += 0 if ok else 1

        bad = base / "bad"
        (bad / "schemas").mkdir(parents=True)
        (bad / "schemas/app.json").write_text(
            json.dumps({"format": "t99/future/9"}), encoding="utf-8")
        ok, msg = check(bad, DEFAULT_SUPPORTED)
        print(f"{'PASS' if not ok else 'FAIL'} incompatible-blocked -- {msg}")
        failures += 0 if not ok else 1

        missing = base / "missing"
        missing.mkdir()
        ok, msg = check(missing, DEFAULT_SUPPORTED)
        print(f"{'PASS' if not ok else 'FAIL'} absent-blocked -- {msg}")
        failures += 0 if not ok else 1

        corrupt = base / "corrupt"
        (corrupt / "schemas").mkdir(parents=True)
        (corrupt / "schemas/app.json").write_text("{not json", encoding="utf-8")
        ok, msg = check(corrupt, DEFAULT_SUPPORTED)
        print(f"{'PASS' if not ok else 'FAIL'} corrupt-blocked -- {msg}")
        failures += 0 if not ok else 1
    print(f"self-test: {'4/4' if failures == 0 else f'{4 - failures}/4'}")
    return 0 if failures == 0 else 1

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="T20 incompatible-format hard gate")
    ap.add_argument("--candidate", default=None)
    ap.add_argument("--supported", nargs="*", default=DEFAULT_SUPPORTED)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)
    if args.self_test:
        return self_test()
    if not args.candidate:
        print("missing --candidate (or use --self-test)")
        return EXIT_MISSING
    ok, msg = check(Path(args.candidate), args.supported)
    print(msg)
    return EXIT_OK if ok else EXIT_BLOCKED

if __name__ == "__main__":
    sys.exit(main())
