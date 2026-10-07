#!/usr/bin/env python3
"""Run the CI gate set declared in skills/tests/ci-gates.json, exactly once each.

Why this file exists
--------------------
T26 added three gates (``verify-routing-signals.py``, ``test-routing-signals.py``
and ``test-community-decoys.py``) that no entrypoint called: they were green only
when a human remembered to type them (WORK-BOARD U10). T10 wires them, and this
runner is the single place where "what CI runs" is written down, so the wiring can
itself be checked instead of asserted.

What it guarantees
------------------
1. Every gate listed in the manifest is invoked exactly once, with the argv the
   manifest declares. A gate whose script is missing fails instead of being
   skipped -- an absent path must never read as a pass.
2. Exit codes are classified against the manifest. Spec 4.7 splits them into
   0 ok / 10 needs_review / 20 blocked, and several gates document 10 as
   non-blocking on purpose. An exit code in ``blocking_exits`` fails the run, an
   exit code in ``non_blocking_exits`` passes **and is printed loudly**, and any
   other non-zero code (a Python traceback is 1, a crash is 2, ...) fails as an
   unclassified code rather than being waved through.
3. Nothing here executes vendored content. Community files are read as data by
   the gates; this runner never invokes anything under ``community-raw/`` or
   ``skills/community/`` and refuses to run a manifest entry that points there
   (spec 17.31).
4. A gate may declare ``requires_upstream_snapshot: true``. The read-only
   upstream clones live outside the repository, so a clean checkout has no
   ``../upstream`` directory. When it is absent the gate is SKIPPED loudly
   (printed, counted, never silent) instead of being executed to a certain
   environmental failure; when it is present the gate runs and its blocking
   codes block exactly as declared.

Usage::

    python skills/tests/run-ci-gates.py
    python skills/tests/run-ci-gates.py --only audit-discovery-surface
    python skills/tests/run-ci-gates.py --manifest <other.json>   # controls

Exit codes: 0 all gates ok, 1 at least one gate blocked or failed, 2 the runner
itself could not be trusted (bad manifest, missing file, unusable interpreter).

Standard library only. Read-only with respect to the repository: temporary files
are created under the platform temp directory and removed on exit.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / "skills" / "tests" / "ci-gates.json"

# A gate must never be able to run vendored content (spec 17.31). These are
# checked against the declared script path, before anything is executed.
FORBIDDEN_SCRIPT_PREFIXES = ("community-raw/", "skills/community/", "docs/community/")

RUNNER_SELF_ERROR = 2

class ManifestError(Exception):
    """The manifest cannot be trusted, so no gate result may be believed."""

def load_manifest(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ManifestError(f"manifest missing: {path}")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ManifestError(f"manifest is not valid JSON: {error}") from None
    if not isinstance(document, dict):
        raise ManifestError("manifest must be a JSON object")
    gates = document.get("gates")
    if not isinstance(gates, list) or not gates:
        raise ManifestError("manifest needs a non-empty 'gates' array")
    seen: set[str] = set()
    for index, gate in enumerate(gates):
        where = f"gates[{index}]"
        if not isinstance(gate, dict):
            raise ManifestError(f"{where}: not an object")
        if not isinstance(gate.get("id"), str) or not gate["id"]:
            raise ManifestError(f"{where}: 'id' must be a non-empty string")
        if gate["id"] in seen:
            raise ManifestError(f"{where}: duplicate gate id {gate['id']!r}")
        seen.add(gate["id"])
        if not isinstance(gate.get("script"), str) or not gate["script"]:
            raise ManifestError(f"{where}: 'script' must be a non-empty string")
        args = gate.get("args", [])
        if not isinstance(args, list) or not all(isinstance(a, str) for a in args):
            raise ManifestError(f"{where}: 'args' must be an array of strings")
        for key in ("non_blocking_exits", "blocking_exits"):
            codes = gate.get(key, [])
            if not isinstance(codes, list) or not all(isinstance(c, int) for c in codes):
                raise ManifestError(f"{where}: '{key}' must be an array of ints")
            if 0 in codes:
                raise ManifestError(f"{where}: '{key}' must not contain 0, which is always 'ok'")
        overlap = set(gate.get("blocking_exits", [])) & set(gate.get("non_blocking_exits", []))
        if overlap:
            raise ManifestError(f"{where}: exit code(s) {sorted(overlap)} declared both "
                                "blocking and non-blocking")
        script = gate["script"].replace("\\", "/")
        if not script.startswith("skills/") and not script.startswith("scripts/"):
            raise ManifestError(f"{where}: script must live under skills/ or scripts/, got {script!r}")
        for prefix in FORBIDDEN_SCRIPT_PREFIXES:
            if script.startswith(prefix):
                raise ManifestError(
                    f"{where}: refusing to run vendor code (spec 17.31): {script!r} is under {prefix!r}"
                )
        if gate.get("executes_vendor_code"):
            raise ManifestError(f"{where}: 'executes_vendor_code' must be false for every CI gate")
        if "requires_upstream_snapshot" in gate and not isinstance(
                gate["requires_upstream_snapshot"], bool):
            raise ManifestError(f"{where}: 'requires_upstream_snapshot' must be a boolean")
    return document

def powershell_command() -> list[str]:
    for name in ("pwsh", "powershell"):
        found = shutil.which(name)
        if found:
            return [found, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File"]
    raise ManifestError("no powershell/pwsh interpreter is available for the PowerShell gates")

def command_for(gate: dict[str, Any], pwsh: list[str]) -> list[str]:
    script = gate["script"]
    if gate.get("runtime") == "powershell":
        return [*pwsh, script, *gate.get("args", [])]
    return [sys.executable, script, *gate.get("args", [])]

def classify(gate: dict[str, Any], code: int) -> tuple[str, str]:
    """Return (verdict, reason). Verdicts: ok, non_blocking, blocked, failed."""
    gid = gate["id"]
    if code == 0:
        return "ok", "exit 0"
    if code in gate.get("blocking_exits", []):
        return "blocked", f"exit {code} is a blocking code for this gate"
    if code in gate.get("non_blocking_exits", []):
        return "non_blocking", f"exit {code} is registered non-blocking for this gate"
    return "failed", f"exit {code} is not a code this gate documents; treating as failure"

def skip_reason_for(gate: dict[str, Any]) -> str:
    """Why this gate must not be executed here, or "" when it may run.

    A gate with ``requires_upstream_snapshot: true`` reads the read-only
    upstream clones at ``<repo>/../upstream``. That directory lives outside the
    repository: present beside a dev checkout, absent beside a clean CI clone.
    Running the gate without it turns one environmental check red with
    certainty (measured: test-adapt-community goes 86/87, exit 30, on exactly
    ``readonly/inspect exits 0 on a clean source``), which would keep CI red
    for a reason no patch can fix. Skipping loudly is the honest alternative;
    the skip names the missing directory so it can never be mistaken for a pass.
    """
    if gate.get("requires_upstream_snapshot"):
        snapshot = ROOT.parent / "upstream"
        if not snapshot.is_dir():
            return (f"../upstream snapshot absent ({snapshot.as_posix()} is not a "
                    f"directory); {gate['id']} needs the read-only upstream clones "
                    f"for one check and would fail environmentally without them")
    return ""

DECISION_MARKERS = ("FAIL", "[BLOCKED]", "NEEDS_REVIEW", "Traceback", "Error")

def diagnosis(text: str) -> str:
    """The one line that explains a failure.

    A CI log that says only "exit 1 is a blocking code" makes the reader go and
    reproduce it by hand. Prefer the gate's own verdict line, then its `[BLOCKED]`
    items, then the tail.
    """
    lines = [line.strip() for line in (text or "").strip().splitlines() if line.strip()]
    for line in lines:
        if line.startswith(("FAIL", "NEEDS_REVIEW")):
            return line[:400]
    for line in lines:
        if line.startswith("[BLOCKED]"):
            return line[:400]
    for line in reversed(lines):
        if line.startswith(("Traceback", "Error")):
            return line[:400]
    return " | ".join(lines[-3:])[:400]

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST),
                        help="gate manifest to run (default skills/tests/ci-gates.json)")
    parser.add_argument("--only", action="append",
                        help="run only these gate ids (repeatable)")
    parser.add_argument("--runner", choices=["python", "powershell"],
                        help="run only the gates whose declared runner matches; the CI "
                             "integration-gates job uses --runner python because the "
                             "PowerShell gates are covered by the routing-tests matrix")
    parser.add_argument("--list", action="store_true",
                        help="print the gate ids and exit 0 without running anything")
    args = parser.parse_args(argv)

    manifest_path = Path(args.manifest).resolve()
    try:
        document = load_manifest(manifest_path)
    except ManifestError as error:
        print(f"FAIL run-ci-gates: {error}")
        return RUNNER_SELF_ERROR

    gates = document["gates"]
    if args.only:
        wanted = set(args.only)
        unknown = wanted - {g["id"] for g in gates}
        if unknown:
            print(f"FAIL run-ci-gates: unknown gate id(s): {sorted(unknown)}")
            return RUNNER_SELF_ERROR
        gates = [g for g in gates if g["id"] in wanted]

    if args.runner:
        def runner_of(gate: dict[str, Any]) -> str:
            return "powershell" if gate.get("runtime") == "powershell" else "python"
        gates = [g for g in gates if runner_of(g) == args.runner]
        if not gates:
            print(f"FAIL run-ci-gates: --runner {args.runner} selected no gate")
            return RUNNER_SELF_ERROR

    if args.list:
        for gate in gates:
            print(f"{gate['id']:30} {gate['script']} {' '.join(gate.get('args', []))}")
        return 0

    try:
        pwsh = powershell_command()
    except ManifestError as error:
        print(f"FAIL run-ci-gates: {error}")
        return RUNNER_SELF_ERROR

    print("=== CI gate run (manifest: "
          f"{manifest_path.relative_to(ROOT).as_posix() if manifest_path.is_relative_to(ROOT) else manifest_path}"
          f", gates: {len(gates)}) ===")
    print(f"python : {sys.executable}")
    print(f"shell  : {pwsh[0]}")

    rows: list[tuple[str, str, int, str]] = []
    with tempfile.TemporaryDirectory(prefix="ci-gates-") as scratch:
        for gate in gates:
            script = ROOT / gate["script"]
            if not script.is_file():
                # A missing gate is a failure. It must never read as "nothing
                # to do", which is exactly how the three T26 gates stayed
                # unwired for a whole round.
                print(f"[FAIL]   {gate['id']:30} script missing: {gate['script']}")
                rows.append((gate["id"], "failed", 1, f"script missing: {gate['script']}"))
                continue
            skipped = skip_reason_for(gate)
            if skipped:
                print(f"[SKIP]   {gate['id']:30} {skipped}")
                rows.append((gate["id"], "skipped", 0, skipped))
                continue
            argv_run = command_for(gate, pwsh)
            completed = subprocess.run(
                argv_run, cwd=str(ROOT), capture_output=True, text=True,
                encoding="utf-8", errors="replace", check=False,
                env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8",
                     "PYTHONDONTWRITEBYTECODE": "1", "TEMP": scratch, "TMP": scratch},
            )
            verdict, reason = classify(gate, completed.returncode)
            rows.append((gate["id"], verdict, completed.returncode, reason))
            if verdict == "ok":
                print(f"[PASS]   {gate['id']:30} {reason}")
            elif verdict == "non_blocking":
                print(f"[WARN]   {gate['id']:30} {reason}")
                print(f"         {diagnosis(completed.stdout)}")
            else:
                print(f"[{verdict.upper():6}] {gate['id']:30} {reason}")
                print(f"         {diagnosis(completed.stdout)}")
                if completed.stderr:
                    print(f"         stderr: {diagnosis(completed.stderr)}")

    blocked = [r for r in rows if r[1] == "blocked"]
    failed = [r for r in rows if r[1] == "failed"]
    non_blocking = [r for r in rows if r[1] == "non_blocking"]
    skipped = [r for r in rows if r[1] == "skipped"]

    print("=== summary ===")
    print(f"total={len(rows)} ok={len(rows) - len(blocked) - len(failed) - len(non_blocking) - len(skipped)} "
          f"non_blocking={len(non_blocking)} skipped={len(skipped)} "
          f"blocked={len(blocked)} failed={len(failed)}")
    for gid, verdict, code, reason in non_blocking:
        print(f"NON-BLOCKING {gid}: {reason} -- registered on purpose, see the manifest's ci_note")
    for gid, verdict, code, reason in skipped:
        print(f"SKIPPED {gid}: {reason}")
    if blocked or failed:
        for gid, verdict, code, reason in blocked + failed:
            print(f"{verdict.upper()} {gid}: exit {code} ({reason})")
        print(f"FAIL run-ci-gates: {len(blocked)} blocked, {len(failed)} failed")
        return 1
    print("PASS run-ci-gates: every gate is ok, a registered non-blocking item, or a loud skip")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())