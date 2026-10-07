#!/usr/bin/env python3
"""Negative control for the community routing engine (design-freeze defect D8).

Every other gate in this repository is hits-only. ``skills/scripts/test-routing.ps1``
carries 182 cases and ``skills/scripts/test-route-ranking.py`` carries 13 more, and
all of them assert that a hint REACHES something. Not one of them asserts that a
hint must NOT reach something, which is precisely why an over-broad rule stays
invisible: the reference package scored 49/49 across thirteen rule replacements
while its game-cheat route was answering an ESP32 relay-wiring question.

This runner closes that gap. It loads the real ``skills/scripts/community-route.py``
(importlib, exactly like ``test-route-ranking.py``) and scores
``skills/tests/community-decoys.json`` against the real registry:

* a **DECOY** case fails when a named target is answered. ``strict: true`` means
  the target must not appear anywhere among the shown references; ``strict:
  false`` means it must merely not be the TOP answer;
* a **POSITIVE** case fails when its expected record is not among the shown
  references (or, with ``expect_top``, is not the first one).

The two halves are gated SEPARATELY and both gates must pass. A healthy positives
half must not be able to mask a bad decoy half, which is the whole reason the
positives half exists in the first place: a corpus of negatives alone is
satisfied by making the engine refuse everything.

The default thresholds are pinned just UNDER the measured pass rate, so the known
real failures stay visible case by case and any NEW over-trigger moves the number
and turns the gate red. They are deliberately not 1.0 (that would be permanently
red, or would have to be met by deleting cases - both forbidden by design-freeze
section 4) and deliberately not 0.0 (that would be decorative).

This script is read-only. It writes nothing, deletes nothing and runs no importer.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
ROUTE = ROOT / "skills" / "scripts" / "community-route.py"
CORPUS = ROOT / "skills" / "tests" / "community-decoys.json"

# Pinned just under the measured pass rate of the shipped corpus. Recompute with
# ``python skills/scripts/test-community-decoys.py --report`` and move these two
# numbers only when a case is genuinely closed. See the module docstring.
#
# MEASURED FLOOR, re-measured on this tree after the T26 follow-up wave added the
# short-token-'ai' and strict adapter-boilerplate decoys plus the two
# anti-over-narrowing positives:
#
#     decoy_rate    = 20/29 = 0.6897     (gate 0.50)
#     positive_rate = 27/28 = 0.9643
#     combined_rate = 47/57 = 0.8246     (gate 0.75)
#
# Both gates were left exactly where they were. The floor rose because real cases
# were closed, not because a case was deleted or a threshold was moved, and the
# gates are a floor just under the floor, not a target to chase: raising them to
# meet the new number would be the same mistake in the other direction.
#
# MEASURED FLOOR after the A4 correction of 2026-09-30, which moved ONE case
# across the halves and is the reason the two paragraphs above are not the current
# numbers:
#
#     decoy_rate    = 21/30 = 0.7000     (gate 0.50)
#     positive_rate = 27/27 = 1.0000
#     combined_rate = 48/57 = 0.8421     (gate 0.75)
#
# What moved: the positive ``recall-s3-bucket`` (hint "s3 bucket", expected target
# skills/unauthorized-access-common-services/SKILL.md) was removed and re-asserted
# as the decoy ``absence-s3-bucket``. That expectation was not reachable and not
# reachable-in-principle: 'bucket' and 's3' each occur in 0 of 293 records' routing
# texts and 0 of 293 candidacy views, the named record's own two files contain
# zero occurrences of s3|bucket|aws|object storage, and its registry description
# covers Redis/Rsync/PHP-FPM/AJP/Hadoop YARN/H2 Console - a Java SQL console, not
# object storage. The case was therefore reporting a documented ABSENCE of
# capability as "1 real over-narrowing", which is worse than no case at all. The
# total is therefore unchanged at 57 and the class mix is unchanged; the rate moved
# because one failing expectation was withdrawn and replaced by an assertion that
# holds, not because a defect was closed and not because a threshold was touched.
#
# Note what did NOT move: both gate VALUES are unchanged (0.50 / 0.75), and the same
# nine over-triggers are still red and still named. The positives half is now
# 27/27, so the "one positive fails" signal this file used to carry has moved into
# the decoy half as a permanent absence guard: injecting an unjustified 'bucket'
# signal makes ``absence-s3-bucket`` fail, so the red line survives the correction
# in the only direction it is allowed to move.
DEFAULT_MIN_RATE = 0.75
DEFAULT_DECOY_RATE = 0.50

BUG_CLASSES = (
    "D1-recall", "D2-recall", "D3-plural", "D5-stopword-alias", "D6-provenance",
    "D6-governance", "D7-recall", "D4-short-token", "hypernym", "ranking-order",
)

def fail(message: str) -> int:
    print(f"FAIL test-community-decoys: {message}")
    return 1

def load_route_module():
    spec = importlib.util.spec_from_file_location("community_route_decoys", ROUTE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def load_corpus() -> dict[str, Any]:
    """Load and validate the corpus shape. Fails closed, never guesses."""
    if not CORPUS.is_file():
        raise SystemExit(f"FAIL test-community-decoys: corpus missing: {CORPUS}")
    try:
        document = json.loads(CORPUS.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise SystemExit(f"FAIL test-community-decoys: corpus is not valid JSON: {error}") from None
    if not isinstance(document, dict):
        raise SystemExit("FAIL test-community-decoys: corpus must be a JSON object")
    problems: list[str] = []
    for key in ("meta", "decoys", "positives"):
        if key not in document:
            problems.append(f"missing {key}")
    if problems:
        raise SystemExit(f"FAIL test-community-decoys: corpus shape: {problems}")
    if not isinstance(document["decoys"], list) or not document["decoys"]:
        problems.append("decoys must be a non-empty array")
    if not isinstance(document["positives"], list) or not document["positives"]:
        problems.append("positives must be a non-empty array")
    seen: set[str] = set()
    for kind in ("decoys", "positives"):
        for index, case in enumerate(document[kind]):
            where = f"{kind}[{index}]"
            if not isinstance(case, dict):
                problems.append(f"{where}: not an object")
                continue
            name = case.get("name")
            if not isinstance(name, str) or not name:
                problems.append(f"{where}: name is required")
            elif name in seen:
                problems.append(f"{where}: duplicate case name {name!r}")
            else:
                seen.add(name)
            if not isinstance(case.get("hint"), str) or not case["hint"].strip():
                problems.append(f"{where}: hint is required")
            why = case.get("why")
            if not isinstance(why, str) or len(why) < 40:
                problems.append(f"{where}: why must explain the bug class in prose")
            bug_class = case.get("bug_class")
            if bug_class not in BUG_CLASSES:
                problems.append(f"{where}: bug_class {bug_class!r} not one of {list(BUG_CLASSES)}")
            if kind == "decoys":
                if not isinstance(case.get("strict"), bool):
                    problems.append(f"{where}: strict must be a bool")
                if not case.get("forbidden_source_path") and not case.get("forbidden_wrapper"):
                    problems.append(f"{where}: needs forbidden_source_path or forbidden_wrapper")
            else:
                if not case.get("expect_source_path"):
                    problems.append(f"{where}: expect_source_path is required")
                if "expect_top" in case and not isinstance(case["expect_top"], bool):
                    problems.append(f"{where}: expect_top must be a bool")
    if problems:
        raise SystemExit(f"FAIL test-community-decoys: corpus shape: {problems[:10]}")
    return document

def probe(module, hint: str, source: str | None) -> dict[str, Any]:
    """One real ``lookup()`` call, flattened into what the scorer needs."""
    payload = module.lookup(hint, source)
    matches = payload.get("matches") or []
    shown: list[str] = []
    wrappers: list[str] = []
    for match in matches:
        wrappers.append(match["source"])
        for reference in match.get("references") or []:
            shown.append(reference["source_path"])
    top_match = matches[0] if matches else None
    return {
        "status": payload.get("status"),
        "wrappers": wrappers,
        "shown": shown,
        "top_wrapper": top_match["source"] if top_match else None,
        "top_path": top_match["references"][0]["source_path"]
        if top_match and top_match.get("references") else None,
        "n_shown": len(shown),
    }

def score_decoy(case: dict[str, Any], observed: dict[str, Any]) -> tuple[bool, str, str]:
    forbidden_path = case.get("forbidden_source_path")
    forbidden_wrapper = case.get("forbidden_wrapper")
    strict = bool(case["strict"])
    expected = forbidden_path or forbidden_wrapper
    if strict:
        if forbidden_path and forbidden_path in observed["shown"]:
            return False, expected, f"answered by {forbidden_path} (strict: must not appear at all)"
        if forbidden_wrapper and forbidden_wrapper in observed["wrappers"]:
            paths = [r for r in observed["shown"]]
            return False, expected, (f"wrapper {forbidden_wrapper} answered "
                                     f"({observed['n_shown']} reference(s): {paths[:3]})")
        return True, expected, "not answered"
    if forbidden_path and observed["top_path"] == forbidden_path:
        return False, expected, f"is the TOP reference (strict=false: must not lead)"
    if forbidden_wrapper and observed["top_wrapper"] == forbidden_wrapper:
        return False, expected, (f"is the TOP wrapper (strict=false: must not lead); "
                                 f"top reference {observed['top_path']}")
    return True, expected, "not the top answer"

def score_positive(case: dict[str, Any], observed: dict[str, Any]) -> tuple[bool, str, str]:
    expect = case["expect_source_path"]
    if case.get("expect_top"):
        if observed["top_path"] == expect:
            return True, expect, "is the TOP reference"
        return False, expect, f"top reference is {observed['top_path']}, not {expect}"
    if expect in observed["shown"]:
        return True, expect, f"routed (position {observed['shown'].index(expect) + 1} of {observed['n_shown']})"
    return False, expect, (f"NOT routed; status={observed['status']}, "
                           f"{observed['n_shown']} reference(s): {observed['shown'][:3]}")

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--min-rate", type=float, default=DEFAULT_MIN_RATE,
                        help=f"minimum COMBINED pass rate (default {DEFAULT_MIN_RATE})")
    parser.add_argument("--decoy-rate", type=float, default=DEFAULT_DECOY_RATE,
                        help=f"minimum DECOY-ONLY pass rate (default {DEFAULT_DECOY_RATE})")
    parser.add_argument("--bug-class", action="append", choices=BUG_CLASSES,
                        help="only run these bug classes (repeatable)")
    parser.add_argument("--report", action="store_true",
                        help="print the measured pass rates and exit 0 without gating")
    args = parser.parse_args()

    document = load_corpus()
    module = load_route_module()

    wanted = set(args.bug_class) if args.bug_class else None
    decoys = [c for c in document["decoys"] if wanted is None or c["bug_class"] in wanted]
    positives = [c for c in document["positives"] if wanted is None or c["bug_class"] in wanted]
    if not decoys and not positives:
        return fail("no case matches the requested --bug-class filter")

    rows: list[dict[str, Any]] = []
    for case in decoys:
        observed = probe(module, case["hint"], case.get("source"))
        ok, expected, actual = score_decoy(case, observed)
        rows.append({"kind": "DECOY", "name": case["name"], "hint": case["hint"],
                     "bug_class": case["bug_class"], "ok": ok, "expected": expected,
                     "actual": actual, "why": case["why"], "status": observed["status"]})
    for case in positives:
        observed = probe(module, case["hint"], case.get("source"))
        ok, expected, actual = score_positive(case, observed)
        rows.append({"kind": "POSITIVE", "name": case["name"], "hint": case["hint"],
                     "bug_class": case["bug_class"], "ok": ok, "expected": expected,
                     "actual": actual, "why": case["why"], "status": observed["status"]})

    print("=== community decoy corpus: per-case result (D8 negative control) ===")
    for row in rows:
        mark = "pass" if row["ok"] else "FAIL"
        print(f"[{mark}] {row['kind']:8} {row['name']:32} class={row['bug_class']:20} "
              f"hint={row['hint']!r} status={row['status']}")
        print(f"         expected: {row['expected']}")
        print(f"         actual:   {row['actual']}")
        print(f"         why:      {row['why']}")

    def rate(kind: str) -> tuple[int, int, float]:
        subset = [row for row in rows if row["kind"] == kind]
        passed = sum(1 for row in subset if row["ok"])
        total = len(subset)
        return passed, total, (passed / total if total else 0.0)

    d_pass, d_total, d_rate = rate("DECOY")
    p_pass, p_total, p_rate = rate("POSITIVE")
    # The combined rate is over BOTH halves. It is derived from the two per-kind
    # counts rather than from a third scan, so it can never silently disagree
    # with the numbers printed above it.
    c_pass = d_pass + p_pass
    c_total = len(rows)
    combined = c_pass / c_total if c_total else 0.0

    print("=== rates (the two gates are independent) ===")
    if d_total:
        print(f"decoy cases:    {d_pass}/{d_total} = {d_rate:.4f}   (gate: >= {args.decoy_rate})")
    else:
        print(f"decoy cases:    0 selected by the --bug-class filter, "
              f"decoy gate ({args.decoy_rate}) NOT applied")
    print(f"positive cases: {p_pass}/{p_total} = {p_rate:.4f}")
    print(f"combined:       {c_pass}/{c_total} = {combined:.4f}   (gate: >= {args.min_rate})")

    failures = [row for row in rows if not row["ok"]]
    if failures:
        print(f"=== {len(failures)} real defect(s), named, not tuned away ===")
        for row in failures:
            kind = "OVER-TRIGGER" if row["kind"] == "DECOY" else "OVER-NARROWING"
            print(f"  {kind:14} {row['name']:32} {row['actual']}")

    if args.report:
        print("REPORT ONLY: gates not applied")
        print(f"MEASURED decoy_rate={d_rate:.6f} positive_rate={p_rate:.6f} combined_rate={combined:.6f}")
        return 0

    if d_total and d_rate < args.decoy_rate:
        return fail(f"decoy pass rate {d_rate:.4f} ({d_pass}/{d_total}) is below the "
                    f"decoy gate {args.decoy_rate}: a new over-trigger moved the number")
    if c_total and combined < args.min_rate:
        return fail(f"combined pass rate {combined:.4f} ({c_pass}/{c_total}) is below the "
                    f"gate {args.min_rate}")
    print("PASS test-community-decoys: decoy gate and combined gate both hold")
    return 0

if __name__ == "__main__":
    sys.exit(main())
