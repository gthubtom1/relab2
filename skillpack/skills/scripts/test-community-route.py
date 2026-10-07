#!/usr/bin/env python3
"""Executable regression checks for community-route.py.

The matching, confidence and tie assertions below were already present before T02.
T02 added the frozen 4.7 status/exit-code assertions and the fail-closed assertions
(unknown enum, unsupported profile alias, registry that points at a missing wrapper
file). No existing assertion was removed or weakened.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROUTE = ROOT / "skills" / "scripts" / "community-route.py"
GOLDEN = ROOT / "skills" / "tests" / "golden-route.json"
EXIT = {"matched": 0, "needs_review": 10, "blocked": 20, "missing_input": 21, "unavailable": 22, "failed": 30}

def run(hint: str, source: str | None = None, limit: int | None = None, expect_exit: int | None = None) -> dict:
    command = [sys.executable, str(ROUTE), "--hint", hint, "--json"]
    if source:
        command.extend(["--source", source])
    if limit is not None:
        command.extend(["--limit", str(limit)])
    completed = subprocess.run(command, cwd=ROOT, check=False, capture_output=True, text=True, encoding="utf-8")
    payload = json.loads(completed.stdout)
    if expect_exit is not None:
        require(completed.returncode == expect_exit,
                f"exit code for {hint!r} was {completed.returncode}, expected {expect_exit} ({payload.get('status')})")
    return payload

def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)

def load_route_module():
    spec = importlib.util.spec_from_file_location("community_route_module", ROUTE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def fail_closed_checks() -> None:
    """T02: unknown enums and stale registry references must fail closed."""
    module = load_route_module()
    real_registry = module.REGISTRY
    real_profile_map = module.PROFILE_MAP
    original = real_registry.read_text(encoding="utf-8")

    with tempfile.TemporaryDirectory() as work:
        work_path = Path(work)

        # 1. unknown enum value in a required enum field
        probe = json.loads(original)
        probe["skills"][0]["discovery"] = "sometimes"
        unknown_enum = work_path / "registry-unknown-enum.json"
        unknown_enum.write_text(json.dumps(probe, ensure_ascii=False), encoding="utf-8")

        # 2. allowed_context that only holds a listed-but-unsupported alias
        probe = json.loads(original)
        probe["skills"][0]["allowed_context"] = ["unrestricted_lab"]
        unsupported = work_path / "registry-unsupported.json"
        unsupported.write_text(json.dumps(probe, ensure_ascii=False), encoding="utf-8")

        # 3. wrapper record pointing at a file that does not exist
        probe = json.loads(original)
        for wrapper in probe["wrappers"]:
            if wrapper["source"] == "hack-skills":
                wrapper["path"] = "skills/community/hack-hub/MISSING.md"
        missing_wrapper = work_path / "registry-missing-wrapper.json"
        missing_wrapper.write_text(json.dumps(probe, ensure_ascii=False), encoding="utf-8")

        # 4. allowed_context value that the frozen migration table does not list
        probe = json.loads(original)
        probe["skills"][0]["allowed_context"] = ["totally-new-context"]
        unknown_alias = work_path / "registry-unknown-alias.json"
        unknown_alias.write_text(json.dumps(probe, ensure_ascii=False), encoding="utf-8")

        try:
            for path, label in ((unknown_enum, "unknown enum"),
                                (missing_wrapper, "wrapper file missing"),
                                (unknown_alias, "unlisted allowed_context")):
                module.REGISTRY = path
                try:
                    module.load_contract()
                except module.RegistryError as error:
                    require(error.status == "blocked", f"{label} must be blocked, got {error.status}")
                    require(error.failure_reason == "schema_invalid",
                            f"{label} must report schema_invalid, got {error.failure_reason}")
                    require(error.extra.get("violations"), f"{label} must list the violating field")
                else:
                    raise AssertionError(f"{label} did not fail closed")

            module.REGISTRY = unsupported
            contract = module.load_contract()
            resolved, review, unknown = contract.resolve_profiles(["unrestricted_lab"])
            require(resolved == [], "unrestricted_lab must not resolve to a canonical profile")
            require(review and not unknown, "unrestricted_lab is listed as unsupported, not unknown")
        finally:
            module.REGISTRY = real_registry
            module.PROFILE_MAP = real_profile_map

        # 5. the real registry must still load after the probes
        module.load_contract()
        require(json.loads(original)["schemaVersion"] == "1.0", "registry schemaVersion must stay 1.0")

def golden_u9_pins() -> None:
    """T18 (additive, existing assertions untouched): pin the U9 register.

    docs/community/ROUTING-SIGNAL-U9.md registered 5 rules as UNFIXABLE and
    fixed the reference layer of alias-delivery-cjk to 215. These pins assert
    that behaviour as EXPECTED, so whoever 'fixes' one of them gets a red
    gate here and must amend U9 consciously. The s3 absence guard pins the
    correct behaviour that no bucket keyword may be invented.
    Full 26-case golden evaluation lives in test-golden-route.py; this gate
    only carries the 6 pins so CI (total gate count unchanged) enforces them.
    """
    document = json.loads(GOLDEN.read_text(encoding="utf-8"))
    pins = [case for case in document["cases"] if case.get("pin_u9")]
    require(len(pins) == 6, f"U9 pin count moved ({len(pins)} != 6): amend U9 consciously")
    for case in pins:
        payload = run(case["hint"], case.get("source"), expect_exit=case["expect"]["exit"])
        require(payload.get("status") == case["expect"]["status"],
                f"U9 pin {case['name']!r} status moved to {payload.get('status')!r}")
        expect = case["expect"]
        if "over_trigger_top" in expect:
            top = payload["matches"][0]["references"][0]["source_path"]
            require(top == expect["over_trigger_top"],
                    f"U9 pin {case['name']!r} top moved to {top!r}: amend U9, do not just edit the pin")
        if "reference_top" in expect:
            top = payload["matches"][0]["references"][0]["source_path"]
            require(top == expect["reference_top"],
                    f"U9 reference fix for {case['name']!r} moved to {top!r}")
        if "wrapper_top" in expect:
            require(payload["matches"][0]["source"] == expect["wrapper_top"],
                    f"U9 wrapper pin for {case['name']!r} moved")
        if expect.get("zero_wrappers"):
            require(not payload.get("matches"), f"s3 absence guard broken: {case['name']!r} now routes")

def main() -> int:
    jwt = run("JWT authentication", "hack-skills", expect_exit=EXIT["matched"])
    require(jwt["matches"], "JWT must produce a wrapper match")
    require(jwt["matches"][0]["source"] == "hack-skills", "JWT source must remain hack-skills")
    require(jwt["matches"][0]["path"] == "skills/community/hack-hub/SKILL.md", "raw JWT skill leaked as entrypoint")
    require(jwt["status"] == "matched" and jwt["failure_reason"] is None, "matched handoff must not carry a failure_reason")
    require(jwt["route_explanation"], "matched handoff must carry a route_explanation (4.7)")
    require(jwt["matches"][0]["profile"] in {"offline_sample", "offline_ctf", "authorized_lab",
                                            "authorized_target_only", "defensive_review", "local_project"},
            "matched reference must expose a canonical profile")
    require(jwt["matches"][0]["network_profile"] == "offline", "defensive_review must derive network mode offline")

    ssrf = run("服务端请求伪造", "hack-skills", expect_exit=EXIT["matched"])
    require(ssrf["matches"], "Chinese SSRF phrase must produce a match")
    require(any("ssrf" in reference["source_path"] for reference in ssrf["matches"][0]["references"]), "SSRF query selected no SSRF reference")

    ctf_apk = run("CTF APK smali", "ctf-super-hub", expect_exit=EXIT["matched"])
    require(ctf_apk["matches"], "CTF APK query must produce a match")
    require(ctf_apk["matches"][0]["source"] == "ctf-super-hub", "CTF APK query left the CTF wrapper")
    require(any("ctf-reverse" in reference["source_path"] for reference in ctf_apk["matches"][0]["references"]), "CTF APK query selected no reverse reference")

    ambiguous = run("JWT", expect_exit=EXIT["needs_review"])
    require(ambiguous["needs_review"], "cross-source JWT tie must require review")
    require(ambiguous["status"] == "needs_review" and ambiguous["failure_reason"] is None,
            "needs_review must not be reported as failed/blocked")
    require(ambiguous.get("candidates") and "confidence" in ambiguous and ambiguous.get("reason"),
            "needs_review must carry candidates, confidence and reason (4.7)")
    require(run("JWT", limit=1, expect_exit=EXIT["needs_review"])["needs_review"], "--limit must not hide a cross-source tie")
    for match in ambiguous["matches"]:
        require(match["access"] == "wrapper-only", "catalog returned a raw executable entry")

    blank = run("   ", expect_exit=EXIT["missing_input"])
    require(blank["status"] == "missing_input", "blank hint must be missing_input")
    require(blank["missing_fields"] == ["hint"], "missing_input must name the missing field (4.7)")

    fail_closed_checks()

    golden_u9_pins()

    print("community-route regression checks passed")
    print("  statuses covered: matched(0) needs_review(10) missing_input(21); blocked(20) covered by fail-closed probes")
    print("  fail-closed probes: unknown enum, unlisted allowed_context, missing wrapper file, unsupported profile alias")
    print("  T18 U9 pins: 5 registered-unfixable over-triggers + s3 absence guard (see skills/tests/golden-route.json)")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
