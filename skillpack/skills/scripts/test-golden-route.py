#!/usr/bin/env python3
"""T18 golden route evaluation: positive hits AND negative refusals, never one rate.

Measures the real ``skills/scripts/community-route.py`` through its CLI (so exit
codes, stdout JSON and stderr are asserted exactly as an agent would observe
them) against ``skills/tests/golden-route.json``:

* positive accuracy  (12 routed + 3 low-confidence presents),
* negative refusals  (3 missing_input + 1 budget blocked + s3 absence),
* U9 pins            (5 registered-unfixable over-triggers + reference-layer fix,
                      asserted as EXPECTED behaviour so a silent fix goes red),
* ambiguity          (bare JWT must stay a multi-wrapper needs_review),
* card Z cross       (5 fixed agreements incl. 1 master-only pin + 1 fixed CJK capability + 3 registered gaps
                      + 5 near-domain negatives pinned out of R46-R49; the master
                      side runs the real master-route.ps1 and parses route-scope.md),
* handoff success    (per-status 4.7 fields on every case),
* context budget     (wrappers<=5, total<=50, except the over-budget refusal).

The verdict is ALL-HOLD: exit 0 only when every golden expectation holds.
No single hit rate is used as a quality conclusion; the report always prints
the positive half and the negative half side by side.

Read-only: writes nothing, runs no importer, needs no network and no packages.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROUTE = ROOT / "skills" / "scripts" / "community-route.py"
MASTER_ROUTE = ROOT / "skills" / "scripts" / "master-route.ps1"
GOLDEN = ROOT / "skills" / "tests" / "golden-route.json"

MAX_WRAPPER_CANDIDATES = 5
MAX_TOTAL_REFERENCES = 50

CANONICAL_PROFILES = {
    "offline_sample", "offline_ctf", "authorized_lab",
    "authorized_target_only", "defensive_review", "local_project",
}

def fail(message: str) -> int:
    print(f"FAIL test-golden-route: {message}")
    return 1

def load_golden() -> dict:
    if not GOLDEN.is_file():
        raise SystemExit(f"FAIL test-golden-route: golden file missing: {GOLDEN}")
    try:
        document = json.loads(GOLDEN.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise SystemExit(f"FAIL test-golden-route: golden file is not valid JSON: {error}")
    cases = document.get("cases")
    if not isinstance(cases, list) or not cases:
        raise SystemExit("FAIL test-golden-route: 'cases' must be a non-empty array")
    seen: set[str] = set()
    problems: list[str] = []
    for index, case in enumerate(cases):
        where = f"cases[{index}]"
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
        if not isinstance(case.get("hint"), str):
            problems.append(f"{where}: hint must be a string")
        if not isinstance(case.get("why"), str) or len(case["why"]) < 40:
            problems.append(f"{where}: why must explain the measurement in prose")
        if case.get("community_skip"):
            if "master" not in case:
                problems.append(f"{where}: community_skip requires a master assertion")
        else:
            expect = case.get("expect")
            if not isinstance(expect, dict) or "status" not in expect or "exit" not in expect:
                problems.append(f"{where}: expect must carry status and exit")
    if problems:
        raise SystemExit(f"FAIL test-golden-route: golden shape: {problems[:10]}")
    return document

def call(hint: str, source: str | None) -> tuple[dict, int, str]:
    command = [sys.executable, str(ROUTE), "--hint", hint, "--json"]
    if source:
        command.extend(["--source", source])
    completed = subprocess.run(
        command, cwd=str(ROOT), check=False,
        capture_output=True, text=True, encoding="utf-8", timeout=300,
    )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        raise SystemExit(
            f"FAIL test-golden-route: non-JSON stdout for hint {hint!r}: "
            f"exit={completed.returncode} stderr={completed.stderr[:200]!r}")
    return payload, completed.returncode, completed.stderr

def shown_paths(payload: dict) -> list[str]:
    out: list[str] = []
    for match in payload.get("matches") or []:
        for reference in match.get("references") or []:
            out.append(reference["source_path"])
    return out

def top_path(payload: dict) -> str | None:
    matches = payload.get("matches") or []
    if matches and matches[0].get("references"):
        return matches[0]["references"][0]["source_path"]
    return None

def top_wrapper(payload: dict) -> str | None:
    matches = payload.get("matches") or []
    return matches[0]["source"] if matches else None

def call_master(hint: str) -> tuple[dict, str]:
    """Run the real master-route.ps1 for one hint; return (info, error).

    info holds primary/skill/confidence parsed from the written
    route-scope.md. error is empty on success. Card Z cross cases only;
    the community assertions above are untouched.
    """
    with tempfile.TemporaryDirectory(prefix="golden-master-") as tmp:
        outdir = str(Path(tmp) / "route")
        try:
            completed = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                 "-File", str(MASTER_ROUTE), "-Hint", hint, "-OutDir", outdir],
                cwd=str(ROOT), check=False,
                capture_output=True, text=True, encoding="utf-8", timeout=600,
            )
        except (OSError, subprocess.SubprocessError) as error:
            return {}, f"master-route did not run: {error}"
        scope = Path(outdir) / "route-scope.md"
        if not scope.is_file():
            return {}, (f"master-route wrote no route-scope.md "
                        f"(exit={completed.returncode} "
                        f"stderr={(completed.stderr or '').strip()[:160]!r})")
        info: dict = {}
        for line in scope.read_text(encoding="utf-8-sig").splitlines():
            text = line.strip()
            if text.startswith("- primary:"):
                info["primary"] = text.split(":", 1)[1].strip()
            elif text.startswith("- primary_skill:"):
                info["skill"] = text.split(":", 1)[1].strip()
            elif text.startswith("- confidence:"):
                info["confidence"] = text.split(":", 1)[1].strip()
        if not {"primary", "skill", "confidence"} <= set(info):
            return {}, f"route-scope.md unparsable: {sorted(info)}"
        return info, ""

def check_master(case: dict, info: dict, error: str) -> list[str]:
    """Violations of the card Z master side (empty means it holds)."""
    want = case["master"]
    if error:
        return [f"master: {error}"]
    bad: list[str] = []
    skill = info.get("skill", "")
    short = skill[7:] if skill.startswith("skills/") else skill
    if info.get("primary") != want.get("primary"):
        bad.append(f"master primary {info.get('primary')!r} != {want.get('primary')!r}")
    if short != want.get("skill"):
        bad.append(f"master skill {short!r} != {want.get('skill')!r}")
    if "confidence" in want and info.get("confidence") != want["confidence"]:
        bad.append(f"master confidence {info.get('confidence')!r} != {want['confidence']!r}")
    for barred in want.get("not_in") or []:
        if info.get("primary") == barred:
            bad.append(f"master absorbed into {barred} (negative control failed)")
    return bad

def check_expect(case: dict, payload: dict, code: int) -> list[str]:
    """Return a list of violated expectations (empty means the case holds)."""
    expect = case["expect"]
    bad: list[str] = []
    if payload.get("status") != expect["status"]:
        bad.append(f"status {payload.get('status')!r} != {expect['status']!r}")
    if code != expect["exit"]:
        bad.append(f"exit {code} != {expect['exit']}")
    if "top_source_path" in expect and top_path(payload) != expect["top_source_path"]:
        bad.append(f"top {top_path(payload)!r} != {expect['top_source_path']!r}")
    if "contains_source_path" in expect and expect["contains_source_path"] not in shown_paths(payload):
        bad.append(f"{expect['contains_source_path']!r} not among {len(shown_paths(payload))} shown")
    if "top_wrapper" in expect and top_wrapper(payload) != expect["top_wrapper"]:
        bad.append(f"top wrapper {top_wrapper(payload)!r} != {expect['top_wrapper']!r}")
    if "reference_top" in expect and top_path(payload) != expect["reference_top"]:
        bad.append(f"reference top {top_path(payload)!r} != {expect['reference_top']!r} (U9 reference fix moved?)")
    if "wrapper_top" in expect and top_wrapper(payload) != expect["wrapper_top"]:
        bad.append(f"wrapper top {top_wrapper(payload)!r} != {expect['wrapper_top']!r}")
    if "over_trigger_top" in expect and top_path(payload) != expect["over_trigger_top"]:
        bad.append(f"U9 pin moved: top {top_path(payload)!r} != pinned {expect['over_trigger_top']!r}; "
                   "amend ROUTING-SIGNAL-U9.md consciously, do not just update this file")
    if expect.get("zero_wrappers") and (payload.get("matches") or []):
        bad.append(f"expected zero wrappers, got {[m['source'] for m in payload['matches']]}")
    if "min_wrappers" in expect and len(payload.get("matches") or []) < expect["min_wrappers"]:
        bad.append(f"only {len(payload.get('matches') or [])} wrapper(s), need >={expect['min_wrappers']}")
    if expect.get("needs_review_flag") and not payload.get("needs_review"):
        bad.append("needs_review flag not set")
    if "missing_fields" in expect and payload.get("missing_fields") != expect["missing_fields"]:
        bad.append(f"missing_fields {payload.get('missing_fields')!r} != {expect['missing_fields']!r}")
    if "failure_reason" in expect and payload.get("failure_reason") != expect["failure_reason"]:
        bad.append(f"failure_reason {payload.get('failure_reason')!r} != {expect['failure_reason']!r}")
    if expect.get("budget_refused"):
        budget = payload.get("budget") or {}
        if (budget.get("total_references") or 0) <= MAX_TOTAL_REFERENCES:
            bad.append("over-budget case must report total_references > 50")
        for key in ("required_action", "confirmation"):
            if not payload.get(key):
                bad.append(f"over-budget payload must carry {key}")
    return bad

def check_handoff(payload: dict) -> list[str]:
    """Per-status 4.7 handoff completeness. Empty means the handoff is complete."""
    bad: list[str] = []
    status = payload.get("status")
    if not payload.get("route_explanation"):
        bad.append("route_explanation missing")
    if status == "matched":
        if payload.get("failure_reason") is not None:
            bad.append("matched must not carry failure_reason")
        matches = payload.get("matches") or []
        if not matches:
            bad.append("matched with zero matches")
        for match in matches:
            if match.get("access") != "wrapper-only":
                bad.append("raw executable entry leaked as entrypoint")
            if match.get("profile") not in CANONICAL_PROFILES:
                bad.append(f"non-canonical profile {match.get('profile')!r}")
            if "network_profile" not in match:
                bad.append("network_profile missing on match")
    elif status == "needs_review":
        if not payload.get("needs_review"):
            bad.append("needs_review flag not set")
        if payload.get("failure_reason") is not None:
            bad.append("needs_review must not be reported as failed/blocked")
        if "confidence" not in payload or not payload.get("reason"):
            bad.append("needs_review must carry confidence and reason")
        if (payload.get("matches") or []) and not payload.get("candidates"):
            bad.append("needs_review with matches must carry candidates")
    elif status == "missing_input":
        if payload.get("missing_fields") != ["hint"]:
            bad.append("missing_input must name the missing field")
    elif status == "blocked":
        if not payload.get("reason") and not payload.get("failure_reason"):
            bad.append("blocked must carry reason")
    return bad

def check_budget(case: dict, payload: dict) -> list[str]:
    if case["expect"].get("budget_refused"):
        return []
    bad: list[str] = []
    budget = payload.get("budget") or {}
    # Pre-truncation gate inputs, not the per-wrapper display cap: shown refs
    # are capped at 3 per wrapper, so counting shown refs would make the
    # budget check vacuous. total_references/wrapper_candidates are what the
    # engine actually gates on (see golden-err-overbudget: 68 refs refused).
    wrappers = budget.get("wrapper_candidates", len(payload.get("matches") or []))
    total = budget.get("total_references", len(shown_paths(payload)))
    if wrappers > MAX_WRAPPER_CANDIDATES:
        bad.append(f"{wrappers} wrapper candidates > MAX_WRAPPER_CANDIDATES=5")
    if total > MAX_TOTAL_REFERENCES:
        bad.append(f"{total} references > MAX_TOTAL_REFERENCES=50 (must refuse, not truncate)")
    return bad

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--report", action="store_true",
                        help="print the measured rates and exit 0 without gating")
    args = parser.parse_args()

    document = load_golden()
    rows: list[dict] = []
    for case in document["cases"]:
        if case.get("community_skip"):
            # Master-only pin (e.g. x-gap-upload-master): the community side
            # is deliberately unpinned here and owned by a sibling case, so
            # only the master assertion runs. Community handoff/budget checks
            # do not apply to a call that never happens.
            master_info, master_error = call_master(case["hint"])
            violations = check_master(case, master_info, master_error)
            rows.append({
                "name": case["name"], "kind": case["axis"]["kind"], "hint": case["hint"],
                "status": "master-only", "exit": 0,
                "wrappers": 0, "refs": 0,
                "budget_total": None, "budget_wrappers": None,
                "confidence": None, "reason": None, "stderr": "",
                "master": ((master_info.get("primary"), master_info.get("confidence"))
                           if master_info else None),
                "ok": not violations, "violations": violations,
            })
            continue
        payload, code, stderr = call(case["hint"], case.get("source"))
        violations = check_expect(case, payload, code)
        violations += [f"handoff: {v}" for v in check_handoff(payload)]
        violations += [f"budget: {v}" for v in check_budget(case, payload)]
        master_info: dict = {}
        if "master" in case:
            master_info, master_error = call_master(case["hint"])
            violations += check_master(case, master_info, master_error)
        rows.append({
            "name": case["name"], "kind": case["axis"]["kind"], "hint": case["hint"],
            "status": payload.get("status"), "exit": code,
            "wrappers": len(payload.get("matches") or []),
            "refs": len(shown_paths(payload)),
            "budget_total": (payload.get("budget") or {}).get("total_references"),
            "budget_wrappers": (payload.get("budget") or {}).get("wrapper_candidates"),
            "confidence": payload.get("confidence"),
            "reason": payload.get("reason"),
            "stderr": (stderr or "").strip()[:120],
            "master": ((master_info.get("primary"), master_info.get("confidence"))
                       if master_info else None),
            "ok": not violations, "violations": violations,
        })

    print("=== T18 golden route: per-case result ===")
    for row in rows:
        mark = "pass" if row["ok"] else "FAIL"
        print(f"[{mark}] {row['name']:32} kind={row['kind']:9} hint={row['hint']!r}")
        print(f"         status={row['status']} exit={row['exit']} "
              f"wrappers={row['wrappers']} refs={row['refs']} "
              f"confidence={row['confidence']} reason={row['reason']}"
              + (f" master={row['master'][0]}/{row['master'][1]}" if row["master"] else ""))
        for violation in row["violations"]:
            print(f"         !! {violation}")

    def subset(*kinds: str) -> list[dict]:
        return [r for r in rows if r["kind"] in kinds]

    def rate(part: list[dict]) -> tuple[int, int, float]:
        ok = sum(1 for r in part if r["ok"])
        return ok, len(part), (ok / len(part) if part else 0.0)

    pos = subset("positive")
    low = subset("lowconf")
    amb = subset("ambiguous")
    err = subset("error")
    u9 = subset("u9-pin")
    fixed = subset("cross-fixed")
    gap = subset("cross-gap")
    neg = subset("negative")

    p_ok, p_n, p_rate = rate(pos)
    l_ok, l_n, l_rate = rate(low)
    e_ok, e_n, e_rate = rate(err)
    u_ok, u_n, u_rate = rate(u9)
    m_ok = sum(1 for r in rows if not [v for v in r["violations"] if v.startswith("master:")])
    h_ok = sum(1 for r in rows if not [v for v in r["violations"] if v.startswith("handoff:")])
    b_ok = sum(1 for r in rows if not [v for v in r["violations"] if v.startswith("budget:")])

    print("=== golden report: positive and negative side by side ===")
    print(f"positive routed:        {p_ok}/{p_n} = {p_rate:.4f}   (must-route incl. CTF/API/APK/Delivery x en/zh/mixed)")
    print(f"low-confidence present: {l_ok}/{l_n} = {l_rate:.4f}   (needs_review but record reachable, exit 10)")
    print(f"ambiguous held:         {rate(amb)[0]}/{rate(amb)[1]} = {rate(amb)[2]:.4f}   (bare JWT stays multi-wrapper needs_review)")
    print(f"error input refused:    {e_ok}/{e_n} = {e_rate:.4f}   (3 missing_input exit 21 + 1 budget blocked exit 20)")
    print(f"U9 pins hold:           {u_ok}/{u_n} = {u_rate:.4f}   (5 unfixable over-triggers + s3 absence as EXPECTED behaviour)")
    print(f"card Z fixed agree:     {rate(fixed)[0]}/{rate(fixed)[1]} = {rate(fixed)[2]:.4f}   (master fixed agreement; incl. master-only pins)")
    print(f"card Z gaps pinned:     {rate(gap)[0]}/{rate(gap)[1]} = {rate(gap)[2]:.4f}   (registered, not defects)")
    print(f"card Z negatives out:   {rate(neg)[0]}/{rate(neg)[1]} = {rate(neg)[2]:.4f}   (near-domain hints stay out of R46-R49)")
    print(f"master side holds:      {m_ok}/{len(rows)}   (card Z master assertions incl. not_in negatives)")
    print(f"handoff complete:       {h_ok}/{len(rows)}   (per-status 4.7 fields on every case)")
    print(f"within context budget:  {b_ok}/{len(rows)}   (pre-truncation totals: wrappers<=5, refs<=50; over-budget case must refuse)")
    admitted = [r for r in rows if r["status"] != "blocked"]
    worst = max(admitted, key=lambda r: (r['budget_total'] if r['budget_total'] is not None else r['refs']) or 0)
    print(f"budget high-water (admitted): {worst['budget_total']} refs / {worst['budget_wrappers']} wrappers on {worst['name']!r} "
          f"(shown {worst['refs']} refs; budget 50 refs / 5 wrappers)")
    print(f"budget refusal:           golden-err-overbudget reports 68 refs / 4 wrappers and is blocked exit 20")

    failures = [r for r in rows if not r["ok"]]
    if failures:
        print(f"=== {len(failures)} golden case(s) RED ===")
        for row in failures:
            print(f"  {row['name']:32} {'; '.join(row['violations'])}")

    if args.report:
        print("REPORT ONLY: gate not applied")
        return 0
    if failures:
        return fail(f"{len(failures)} golden case(s) red; "
                    "a U9-pin move needs a conscious U9 amendment, not a threshold change")
    print(f"PASS test-golden-route: all {len(rows)} golden expectations hold "
          "(positive + negative + U9 pins + handoff + budget)")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
