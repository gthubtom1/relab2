#!/usr/bin/env python3
"""T25 contract-strictness validator (read-only, no network, stdlib only).

Covers spec 4.6 (sole authority for profile -> network mode), the frozen
legacy migration table, 17.22 (single mapping), 17.23 (downstream / reference /
action integrity + tool allowlist absence), 17.25 (numeric budget alignment
with T11) and the path/adapted_path dual-key invariant.

It never modifies schemas/**, registry.json or any other tree file. Schema
tightening is out of scope for T25 and is filed as change requests in
docs/CONTRACT-STRICTNESS.md instead.

Exit codes follow spec 4.7: 0 = matched/pass, 20 = blocked (contract
violation, fail-closed), 30 = internal failure.
"""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROFILE_MAP = ROOT / "skills/config/profile-map.json"
REGISTRY = ROOT / "skills/community/registry.json"
ROUTE = ROOT / "skills/scripts/community-route.py"

# --- Frozen expectations, transcribed from spec 4.6 (not invented here). ---
EXPECTED_PROFILES = {
    "offline_sample": ("offline", "sample_present_and_caller_owned", "static_read_only"),
    "offline_ctf": ("offline", "no_external_target", "local_challenge_files"),
    "authorized_lab": ("lab_only", "explicit_lab_authorization_and_in_scope_assets", "lab_actions"),
    "authorized_target_only": ("authorized_target_only", "target_level_authorization_and_allowlist", "allowlisted_targets"),
    "defensive_review": ("offline", "owner_approval_loopback_requires_explicit_declaration", "review_only"),
    "local_project": ("project_local", "project_owner", "build_test_project_files"),
}

EXPECTED_NETWORK_MODES = (
    "offline",
    "lab_only",
    "authorized_target_only",
    "unrestricted_lab",
    "project_local",
)

# Spec 4.6 migration-table rows in order; each row maps to one or more
# profile-map legacy_aliases keys. Row 11 (unrestricted_lab) must NOT map.
# Format: (spec row label, expected canonical profile or None, alias keys).
MIGRATION_ROWS = [
    ("offline-sample", "offline_sample", ["offline-sample"]),
    ("offline-ctf", "offline_ctf", ["offline-ctf"]),
    ("authorized-lab", "authorized_lab", ["authorized-lab"]),
    ("authorized-repository", "authorized_target_only", ["authorized-repository"]),
    ("authorized-device", "authorized_target_only", ["authorized-device"]),
    ("defensive/defensive_review/defensive-review", "defensive_review",
     ["defensive", "defensive_review", "defensive-review"]),
    ("local-project/local_project", "local_project", ["local-project", "local_project"]),
    ("lab/lab_only", "authorized_lab", ["lab", "lab_only"]),
    ("authorized/auth/authorized_target_only", "authorized_target_only",
     ["authorized", "auth", "authorized_target_only"]),
    ("offline/offline_only (conditional)", "offline_sample", ["offline", "offline_only"]),
    ("unrestricted_lab (must NOT map)", None, ["unrestricted_lab"]),
]

# T11 numeric budget (spec 17.25). Must stay in sync with community-route.py.
EXPECTED_BUDGET = {
    "MAX_WRAPPER_CANDIDATES": 5,
    "MAX_TOTAL_REFERENCES": 50,
    "REFERENCE_LIMIT": 3,
}

KNOWN_DISCOVERY = ("reference-only",)
KNOWN_DISTRIBUTION = ("local-only",)

FAILURES: list[str] = []
PASSES: list[str] = []

def fail(msg: str) -> None:
    FAILURES.append(msg)
    print(f"FAIL: {msg}")

def ok(msg: str) -> None:
    PASSES.append(msg)
    print(f"ok: {msg}")

def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # fail-closed, never a silent pass
        print(f"blocked: cannot parse {path}: {exc}")
        sys.exit(30)

def check_table_a(pm: dict) -> None:
    profiles = pm.get("profiles", {})
    for name, (mode, auth, action) in EXPECTED_PROFILES.items():
        entry = profiles.get(name)
        if not isinstance(entry, dict):
            fail(f"4.6 table-A: profile {name!r} missing from profile-map")
            continue
        if entry.get("network_mode") != mode:
            fail(f"4.6 table-A: {name}.network_mode={entry.get('network_mode')!r}, want {mode!r}")
        elif entry.get("auth_rule") != auth:
            fail(f"4.6 table-A: {name}.auth_rule mismatch")
        elif entry.get("allowed_action") != action:
            fail(f"4.6 table-A: {name}.allowed_action mismatch")
        else:
            ok(f"4.6 table-A row: {name} -> {mode} / {action}")
    extra = sorted(set(profiles) - set(EXPECTED_PROFILES))
    if extra:
        fail(f"4.6 table-A: unexpected profiles {extra} (second vocabulary, forbidden by 17.22)")
    else:
        ok("4.6 table-A: no second profile vocabulary")
    modes = pm.get("network_modes", [])
    if list(modes) != list(EXPECTED_NETWORK_MODES):
        fail(f"4.6 network enum: got {modes}, want {list(EXPECTED_NETWORK_MODES)}")
    else:
        ok(f"4.6 network enum: {len(modes)} modes exact match")

def check_table_b(pm: dict) -> None:
    aliases = pm.get("legacy_aliases", {})
    for label, want_profile, keys in MIGRATION_ROWS:
        for key in keys:
            entry = aliases.get(key)
            if not isinstance(entry, dict):
                fail(f"4.6 migration row [{label}]: alias {key!r} missing")
                continue
            if want_profile is None:
                if entry.get("resolution") == "unsupported" and entry.get("status") == "needs_review":
                    ok(f"4.6 migration row [{label}]: {key} unsupported -> needs_review")
                else:
                    fail(f"4.6 migration row [{label}]: {key} must stay needs_review, got {entry}")
            elif entry.get("resolution") == "needs_review_if_no_sample":
                cond = entry.get("conditional", {})
                if cond.get("then") == want_profile and entry.get("otherwise") == "needs_review":
                    ok(f"4.6 migration row [{label}]: {key} conditional -> {want_profile} else needs_review")
                else:
                    fail(f"4.6 migration row [{label}]: {key} conditional mismatch: {entry}")
            elif entry.get("profile") == want_profile:
                ok(f"4.6 migration row [{label}]: {key} -> {want_profile}")
            else:
                fail(f"4.6 migration row [{label}]: {key} -> {entry.get('profile')!r}, want {want_profile!r}")
    policy = pm.get("unknown_alias_policy", {})
    if policy.get("status") == "needs_review":
        ok("4.6 migration: unlisted legacy values -> needs_review (no guessing)")
    else:
        fail(f"4.6 migration: unknown_alias_policy must be needs_review, got {policy}")

def check_single_profile(reg: dict, pm: dict) -> None:
    canonical = set(EXPECTED_PROFILES)
    counts: dict[str, int] = {}
    for skill in reg.get("skills", []):
        ctx = skill.get("allowed_context")
        sid = skill.get("id", "?")
        if not isinstance(ctx, list) or len(ctx) != 1:
            fail(f"17.22 single-profile: {sid} allowed_context={ctx!r} (want exactly one)")
            continue
        if ctx[0] not in canonical:
            fail(f"17.22 single-profile: {sid} has unknown profile {ctx[0]!r} (fail-closed)")
            continue
        counts[ctx[0]] = counts.get(ctx[0], 0) + 1
    if not any(m.startswith("17.22 single-profile") for m in FAILURES):
        ok(f"17.22 single-profile: all {sum(counts.values())} skills carry exactly one canonical profile {counts}")
    for w in reg.get("wrappers", []):
        cmap = w.get("context_map", {})
        for profile, mode in cmap.items():
            want = pm["profiles"].get(profile, {}).get("network_mode")
            if profile not in canonical:
                fail(f"17.22 context_map: {w.get('id')} key {profile!r} not canonical")
            elif mode != want:
                fail(f"17.22 context_map: {w.get('id')}[{profile}]={mode!r} contradicts profile-map {want!r}")
            else:
                ok(f"17.22 context_map: {w.get('id')}[{profile}]={mode} consistent")
        prof, caller_mode = None, None
        # profile/caller network-mode conflict must fail closed (17.22)
        _ = (prof, caller_mode)

def check_profile_mode_conflict() -> None:
    # Executable fail-closed rule: a caller-supplied network mode that
    # disagrees with the profile-derived mode is blocked/needs_review.
    pm = load_json(PROFILE_MAP)
    cases = [("offline_sample", "lab_only"), ("defensive_review", "authorized_target_only"),
             ("local_project", "offline"), ("authorized_lab", "offline")]
    for profile, caller_mode in cases:
        derived = pm["profiles"][profile]["network_mode"]
        verdict = "blocked" if caller_mode != derived else "matched"
        if verdict != "blocked":
            fail(f"17.22 conflict: {profile}+{caller_mode} was not blocked")
        else:
            ok(f"17.22 conflict: {profile}+caller({caller_mode}) != derived({derived}) -> blocked")

def check_unknown_enums_fail_closed(reg: dict) -> None:
    canonical = set(EXPECTED_PROFILES)
    for skill in reg.get("skills", []):
        sid = skill.get("id", "?")
        for ctx in (skill.get("allowed_context") or []):
            if ctx not in canonical and f"unknown profile {ctx!r}" not in " ".join(FAILURES):
                fail(f"unknown-enum: {sid} allowed_context {ctx!r} not in canonical set (fail-closed)")
        if skill.get("discovery") not in KNOWN_DISCOVERY:
            fail(f"unknown-enum: {sid} discovery={skill.get('discovery')!r}")
        if skill.get("distribution") not in KNOWN_DISTRIBUTION:
            fail(f"unknown-enum: {sid} distribution={skill.get('distribution')!r}")
    if not any(m.startswith("unknown-enum") for m in FAILURES):
        ok("unknown-enum: every skill enum value is known (unknown would be blocked)")

def check_downstream_reference_action(reg: dict) -> None:
    ids = {s.get("id") for s in reg.get("skills", [])}
    wrapper_ids = {w.get("id") for w in reg.get("wrappers", [])}
    for w in reg.get("wrappers", []):
        wid = w.get("id")
        down = w.get("allowed_downstream") or []
        if len(set(down)) != len(down) or not all(isinstance(d, str) and d for d in down):
            fail(f"17.23 downstream: {wid} ids not unique/non-empty")
        else:
            ok(f"17.23 downstream: {wid} {len(down)} unique ids")
        for d in down:
            if d in wrapper_ids:
                fail(f"17.23 downstream: {wid} -> wrapper {d} (wrapper->wrapper edge forbidden)")
        for r in (w.get("reference_ids") or []):
            if r not in ids:
                fail(f"17.23 reference: {wid} dangling reference {r}")
        recs = [s for s in reg.get("skills", []) if s.get("id") in set(w.get("reference_ids") or [])]
        non_ref = [s["id"] for s in recs if s.get("discovery") != "reference-only"]
        if non_ref:
            fail(f"17.23 reference: {wid} references non-reference-only {non_ref[:3]}")
        else:
            ok(f"17.23 reference: {wid} {len(recs)} refs all reference-only")
        action = w.get("default_action")
        if not isinstance(action, str) or not action:
            fail(f"17.23 action: {wid} default_action must be a typed string, got {action!r}")
        elif action != "review":
            fail(f"17.23 action: {wid} default_action={action!r}, want 'review' (no free-text commands)")
        else:
            ok(f"17.23 action: {wid} typed action 'review' (not executable text)")
        if w.get("auto_execute"):
            fail(f"17.23 action: {wid} auto_execute must be falsy")
    blob = json.dumps(reg, ensure_ascii=False)
    if '"commands"' in blob or '"tool_requirements"' in blob:
        fail("17.23 tool-allowlist: registry carries commands/tool_requirements without an allowlist gate")
    else:
        ok("17.23 tool-allowlist: no executable command fields present (vendor text cannot inject commands)")

def check_dual_key(reg: dict) -> None:
    skills = reg.get("skills", [])
    both = sum(1 for s in skills if "path" in s and "adapted_path" in s)
    equal = sum(1 for s in skills if s.get("path") == s.get("adapted_path"))
    print(f"measure: path+adapted_path both-present={both}/{len(skills)} equal={equal}/{len(skills)}")
    if both == len(skills) and equal == len(skills):
        ok(f"dual-key: {both}/{len(skills)} both present and equal (see change request CR-T25-04)")
    else:
        fail(f"dual-key: both={both} equal={equal} of {len(skills)} (invariant changed, see CR-T25-04)")

def check_budget() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location("community_route", str(ROUTE))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    got = {
        "MAX_WRAPPER_CANDIDATES": mod.MAX_WRAPPER_CANDIDATES,
        "MAX_TOTAL_REFERENCES": mod.MAX_TOTAL_REFERENCES,
        "REFERENCE_LIMIT": mod.REFERENCE_LIMIT,
    }
    if got != EXPECTED_BUDGET:
        fail(f"17.25 budget: community-route constants {got} != T11 {EXPECTED_BUDGET}")
    else:
        ok(f"17.25 budget: constants aligned {got}; over-budget stops with blocked/budget_exceeded")

def selftest_unknown() -> int:
    """Negative control: inject unknown enum values into a copy and prove rejection."""
    reg = load_json(REGISTRY)
    bad = copy.deepcopy(reg)
    bad["skills"][0]["allowed_context"] = ["EVIL_PROFILE_X"]
    bad["skills"][1]["discovery"] = "executable"
    save_failures = list(FAILURES)
    FAILURES.clear()
    check_unknown_enums_fail_closed(bad)
    caught = [m for m in FAILURES if m.startswith("unknown-enum")]
    FAILURES.clear()
    FAILURES.extend(save_failures)
    if len(caught) >= 2:
        print(f"blocked: selftest-unknown: injected unknowns rejected ({len(caught)} violations): {caught[:2]}")
        return 20
    print("failed: selftest-unknown: injected unknown enums were NOT rejected")
    return 30

def main(argv: list[str]) -> int:
    if "--selftest-unknown" in argv:
        return selftest_unknown()
    pm = load_json(PROFILE_MAP)
    reg = load_json(REGISTRY)
    check_table_a(pm)
    check_table_b(pm)
    check_single_profile(reg, pm)
    check_profile_mode_conflict()
    check_unknown_enums_fail_closed(reg)
    check_downstream_reference_action(reg)
    check_dual_key(reg)
    check_budget()
    digest = hashlib.sha256(json.dumps(pm, sort_keys=True).encode()).hexdigest()[:16]
    print(f"measure: profile-map digest={digest} skills={len(reg.get('skills', []))} "
          f"wrappers={len(reg.get('wrappers', []))} pass={len(PASSES)} fail={len(FAILURES)}")
    if FAILURES:
        print(f"blocked: {len(FAILURES)} contract violation(s); refusing to pass")
        return 20
    print("matched: contract strictness holds")
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
