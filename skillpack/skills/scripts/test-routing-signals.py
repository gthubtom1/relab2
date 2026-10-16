#!/usr/bin/env python3
"""Negative and positive controls for ``skills/scripts/verify-routing-signals.py``.

A gate that has only ever been seen green is not evidence. This runner drives the
real verifier with deliberately broken documents, through the verifier's own
``--signals`` / ``--schema`` arguments, so **no shipped file is ever written**:
each mutated copy is materialised in a throwaway temporary directory and the real
``skills/community/routing-signals.json`` and ``schemas/community-routing-signals.json``
are read but never touched.

One positive control (the shipped document must exit 0) and twelve fail-closed
controls (each must exit 20) are asserted, covering every failure mode the
verifier's own module docstring claims to enforce: unknown record id, duplicate
id, invalid regex, a too-short note, unfindable evidence, an ``evidence_kind:
"record"`` whose term only occurs in the raw tree, a noise pattern below the 80%
of one source floor, a wrong ``meta.owner``, a ``registrySchemaVersion`` mismatch,
an unmeasured extra ``short_tokens`` literal, ``token_aliases`` below the floor,
and ``signals[]`` below the coverage floor. One extra control drives ``--schema``
so the schema argument itself is exercised.

Why every control is SELF-CHECKING
----------------------------------
A negative control that does not actually mutate anything proves nothing and
looks exactly like a passing control. The first draft of this harness wrote the
*current* eight-literal ``short_tokens`` list where it meant to write the *old*
nine, so the document it fed the verifier was byte-identical to the shipped one,
the verifier correctly exited 0, and the control "passed" the want-20 assertion
only because it was read in a broken way -- it was in fact an undetected no-op
that hid a real gap. So:

* every control is expressed as a mutator that must produce a document **whose
  JSON differs from the shipped document**; a control whose mutated document
  serialises to the same JSON as the shipped one is reported as
  ``NO-OP MUTATION`` and fails the run, loudly, whether or not its exit code
  happens to match;
* the ``short_tokens`` control additionally asserts that the list it writes is
  the *old nine-literal* set and is genuinely different from the shipped list,
  and reports both lists on failure so a same-shaped typo cannot hide;
* the positive control passes ``None`` instead of a document, i.e. it points the
  verifier at the real shipped file and is exempt from the no-op exemption.

Run::

    python skills/scripts/test-routing-signals.py

Exit code ``0`` when every control behaves as required, ``1`` otherwise.
Standard library only; this script is importable (``main()`` returns the code) and
never writes to the repository.
"""

from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[2]
VERIFIER = ROOT / "skills" / "scripts" / "verify-routing-signals.py"
SIGNALS = ROOT / "skills" / "community" / "routing-signals.json"
SCHEMA = ROOT / "schemas" / "community-routing-signals.json"

BLOCKING = 20

# The OLD nine-literal set, i.e. the measured-harmful "ai" restored. It must
# differ from whatever the shipped document carries, and the control asserts
# that it does.
OLD_NINE = ["ad", "ai", "ci", "db", "id", "io", "os", "ot", "s3"]

# --------------------------------------------------------------------------
# harness
# --------------------------------------------------------------------------

def _dump(document: object) -> str:
    return json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2)

def run_verifier(document: dict | None = None,
                 schema_path: Path = SCHEMA) -> tuple[int, str]:
    """Drive the real verifier on a temporary copy. Returns (exit code, last line).

    ``document=None`` points the verifier at the shipped file unchanged, which is
    how the positive control is expressed. Any other document is written to a
    temporary directory and passed via ``--signals``.
    """
    with tempfile.TemporaryDirectory() as work:
        argv = [sys.executable, str(VERIFIER), "--check"]
        if document is not None:
            target = Path(work) / "signals.json"
            target.write_text(_dump(document), encoding="utf-8")
            argv += ["--signals", str(target)]
        argv += ["--schema", str(schema_path)]
        completed = subprocess.run(
            argv, capture_output=True, text=True, encoding="utf-8",
            cwd=ROOT, check=False, timeout=300,
        )
        lines = (completed.stdout or "").strip().splitlines()
        return completed.returncode, (lines[-1] if lines else
                                      (completed.stderr or "").strip())

def _first_signal(document: dict) -> dict:
    signals = document.get("signals") or []
    if len(signals) < 2:
        raise SystemExit(
            "the shipped document no longer has two signals; this harness cannot "
            "address signals[0] and signals[1] and must be updated, not skipped"
        )
    return signals[0]

def _mutate(**changes) -> dict:
    document = copy.deepcopy(SHIPPED)
    document.update(changes)
    return document

# --------------------------------------------------------------------------
# controls
# --------------------------------------------------------------------------

def _unknown_record_id() -> dict:
    document = _mutate()
    _first_signal(document)["id"] = "community-does-not-exist-999"
    return document

def _duplicate_id() -> dict:
    document = _mutate()
    document["signals"][1]["id"] = document["signals"][0]["id"]
    return document

def _invalid_regex() -> dict:
    document = _mutate()
    _first_signal(document)["must"] = ["(unclosed"]
    return document

def _short_note() -> dict:
    document = _mutate()
    _first_signal(document)["note"] = "short"
    return document

def _unfindable_evidence() -> dict:
    document = _mutate()
    _first_signal(document)["evidence"] = "this-string-appears-nowhere-in-that-record-zzz"
    return document

def _raw_only_term_as_record() -> dict:
    """``evidence_kind: "record"`` but the term only exists in the raw tree.

    "mimikatz" occurs inside the record's own directory but is not part of that
    record's legacy_original_name + legacy_description + source_path, so design-
    freeze 1.2's record haystack cannot find it.
    """
    document = _mutate()
    _first_signal(document)["evidence_kind"] = "record"
    _first_signal(document)["evidence"] = "mimikatz"
    return document

def _noise_below_source_floor() -> dict:
    document = _mutate()
    document["noise"] = [{
        "pattern": "zzz-never-matches-anything",
        "scope": "any",
        "note": "Not boilerplate: matches 0% of every source, so rule 1.3 rejects it.",
    }]
    return document

def _wrong_owner() -> dict:
    document = _mutate()
    document["meta"]["owner"] = "T99"
    return document

def _registry_version_mismatch() -> dict:
    document = _mutate()
    document["meta"]["registrySchemaVersion"] = "9.9"
    return document

def _short_tokens_extra_literal() -> dict:
    """Restore the OLD nine-literal set, i.e. put the harmful "ai" back.

    A previous version of this control wrote the *current* eight-literal list
    where it meant to write this one, so it mutated nothing and proved nothing.
    Two assertions guard against a repeat: the list must differ from the shipped
    list, and it must be the nine-literal set, not an eight-literal one.
    """
    shipped = list(SHIPPED.get("short_tokens") or [])
    if OLD_NINE == shipped:
        raise SystemExit(
            "the shipped short_tokens already IS the old nine-literal set; this "
            "control would be a no-op and must be rewritten, not skipped"
        )
    if len(OLD_NINE) != 9 or "ai" not in OLD_NINE:
        raise SystemExit(
            f"OLD_NINE must be the nine-literal set including 'ai', got {OLD_NINE!r}"
        )
    if set(OLD_NINE) - set(shipped) == set():
        raise SystemExit(
            f"OLD_NINE is a subset of the shipped {shipped!r}, so the mutation "
            "would not be visible to the gate; the control is broken"
        )
    return _mutate(short_tokens=OLD_NINE)

def _token_aliases_below_floor() -> dict:
    return _mutate(token_aliases={})

def _signals_below_floor() -> dict:
    return _mutate(signals=copy.deepcopy(SHIPPED["signals"][:5]))

CONTROLS: list[tuple[str, Callable[[], dict], int]] = [
    ("shipped document (positive control)", lambda: None, 0),
    ("unknown record id", _unknown_record_id, BLOCKING),
    ("duplicate signals[].id", _duplicate_id, BLOCKING),
    ("invalid regex in must", _invalid_regex, BLOCKING),
    ("note below the length floor", _short_note, BLOCKING),
    ("unfindable evidence", _unfindable_evidence, BLOCKING),
    ("evidence_kind record but term is raw-only", _raw_only_term_as_record, BLOCKING),
    ("noise pattern below 80% of one source", _noise_below_source_floor, BLOCKING),
    ("wrong meta.owner", _wrong_owner, BLOCKING),
    ("registrySchemaVersion mismatch", _registry_version_mismatch, BLOCKING),
    ("short_tokens carries an unmeasured extra literal", _short_tokens_extra_literal, BLOCKING),
    ("token_aliases below the floor", _token_aliases_below_floor, BLOCKING),
    ("signals[] below the coverage floor", _signals_below_floor, BLOCKING),
]

# --------------------------------------------------------------------------
# runner
# --------------------------------------------------------------------------

def main() -> int:
    global SHIPPED
    for path, label in ((VERIFIER, "verifier"), (SIGNALS, "routing-signals"),
                        (SCHEMA, "schema")):
        if not path.is_file():
            print(f"test-routing-signals: {label} document missing: {path}")
            return 1

    SHIPPED = json.loads(SIGNALS.read_text(encoding="utf-8"))
    shipped_repr = _dump(SHIPPED)
    no_ops: list[str] = []

    print("=" * 78)
    print("negative and positive controls: verify-routing-signals.py")
    print("=" * 78)

    unexpected = 0
    for label, build, want in CONTROLS:
        try:
            document = build()
        except SystemExit as error:  # a control that cannot build its mutation
            print(f"  [FAIL] {label:52} control is broken: {error}")
            unexpected += 1
            continue

        # Self-check: a negative control that does not mutate is worse than no
        # control, so refuse to score it as a pass.
        if document is not None and _dump(document) == shipped_repr:
            print(f"  [FAIL] {label:52} NO-OP MUTATION: the mutated document is "
                  "identical to the shipped one; this control proves nothing")
            no_ops.append(label)
            unexpected += 1
            continue

        code, last_line = run_verifier(document)
        ok = code == want
        unexpected += 0 if ok else 1
        print(f"  [{'PASS' if ok else 'FAIL'}] {label:52} want exit {want:<3} got {code}")
        if not ok:
            print(f"         last line: {last_line}")

    print()
    print(f"controls run: {len(CONTROLS)}   unexpected: {unexpected}   "
          f"no-op mutations: {len(no_ops)}")
    if no_ops:
        print("RESULT: NEGATIVE CONTROL FAILED -- at least one control mutated nothing")
        return 1
    print("RESULT:", "all controls behave as required" if unexpected == 0
          else "NEGATIVE CONTROL FAILED")
    return 0 if unexpected == 0 else 1

if __name__ == "__main__":
    raise SystemExit(main())
