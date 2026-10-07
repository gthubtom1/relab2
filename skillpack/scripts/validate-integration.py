#!/usr/bin/env python3
"""Validate the community adapter boundary without running imported code.

Two modes (spec 4.7 exit codes, task card T04):

  local-only   (default)  structural + integration-contract checks;
                           license-review items are reported as warnings.
  release      (--release) additionally *blocks* on every license state that
                           17.29 forbids for redistribution: missing-license,
                           review-required, mixed, NOASSERTION, NONE, unverified.

`--release` is real: it changes the verdict, not just the wording. An unknown
argument is a hard error (argparse exits 2) instead of being ignored, which is
defect C4 in WORK-BOARD 3.2 -- the previous revision had no argparse and no
`sys.argv` read at all, so `--release` and `--bogus` both exited 0.

Every count that used to be hardcoded is now derived from the registry itself
(defect E9): the source count and the excluded count come from `sources[]` /
`excluded[]`, so T21 adding a canonical base record, or T12 changing the
excluded set, cannot make this gate lie.

Read-only: this script never writes to the repository.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "skills/community/registry.json"

# The four wrapper entrypoints are the only discoverable community files
# (spec 17.27). Their names are a frozen contract (spec 4.3), so they stay as a
# literal -- unlike the source/excluded statistics, they are not a *count*.
WRAPPERS = [
    "skills/community/ctf-hub/SKILL.md",
    "skills/community/hack-hub/SKILL.md",
    "skills/community/delivery/SKILL.md",
    "skills/community/apk-extension/SKILL.md",
]

REQUIRED_FRONTMATTER = ("license:", "compatibility:", "allowed-tools:", "metadata:")

# 17.29: redistribution-blocking license states.
LICENSE_BLOCKING_STATUS = frozenset({"missing-license", "review-required", "mixed"})
LICENSE_BLOCKING_DECLARED = frozenset({"NOASSERTION", "NONE"})
LICENSE_BLOCKING_MATURITY = frozenset({"unverified"})

# Exit codes (spec 4.7). 0 ok, 10 needs_review, 20 blocked.
EXIT_OK = 0
EXIT_NEEDS_REVIEW = 10
EXIT_BLOCKED = 20
EXIT_USAGE = 2

UNSAFE_KEY_NAMES = frozenset({"debug.keystore", "id_rsa", "id_ed25519"})
UNSAFE_KEY_SUFFIXES = frozenset({".pem", ".key"})

def frontmatter(text: str) -> str | None:
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
    return match.group(1) if match else None

def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="validate-integration.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--release",
        action="store_true",
        help="release mode: block on missing/review-required/mixed license, "
             "NOASSERTION/NONE declarations and unverified maturity",
    )
    return parser.parse_args(argv)

def summarize(data: dict) -> dict:
    """Every number the report prints, derived from the registry payload.

    Nothing here is a literal. `stats` is cross-checked against the arrays, but
    it is *not* treated as the source of truth -- that is the whole point of
    closing E9.
    """
    sources = data.get("sources", [])
    skills = data.get("skills", [])
    excluded = data.get("excluded", [])
    stats = data.get("stats", {})
    license_counts: dict[str, int] = {}
    maturity_counts: dict[str, int] = {}
    skill_findings = 0
    for item in skills:
        status = item.get("license_status")
        license_counts[status] = license_counts.get(status, 0) + 1
        maturity = item.get("maturity")
        maturity_counts[maturity] = maturity_counts.get(maturity, 0) + 1
        if status in LICENSE_BLOCKING_STATUS or maturity == "unverified":
            skill_findings += 1
    return {
        "sources": len(sources),
        "skills": len(skills),
        "excluded": len(excluded),
        "stats": stats,
        "license_counts": license_counts,
        "maturity_counts": maturity_counts,
        "skill_findings": skill_findings,
    }

def check_stats_against_arrays(data: dict, summary: dict) -> list[str]:
    """The only remaining 'statistics' checks are array-vs-stats agreement.

    E9 removed the `== 4 sources` / `== 55 excluded` literals. What survives is
    a coherence check between `stats` and the arrays it claims to count, which
    is derived on both sides and therefore survives T21 (canonical base) and
    T12 (source lock) without a code change.
    """
    errors: list[str] = []
    stats = summary["stats"]
    if stats.get("adapted_skill_count") != summary["skills"]:
        errors.append(
            "registry stats do not match adapted skill count: "
            f"stats={stats.get('adapted_skill_count')!r} skills[]={summary['skills']}"
        )
    if stats.get("excluded_framework_skill_count") != summary["excluded"]:
        errors.append(
            "registry stats do not match excluded framework count: "
            f"stats={stats.get('excluded_framework_skill_count')!r} "
            f"excluded[]={summary['excluded']}"
        )
    return errors

def check_license_state(data: dict, release: bool) -> tuple[list[str], list[str], list[str], list[str]]:
    """Return (source_blocking, skill_blocking, source_warning, skill_warning).

    Findings are kept scope-separated on purpose: the recorded baseline for this
    gate is the *skill*-scoped count (292), and a coordinator recomputing that
    number must not have to subtract source findings out of a total.

    In local-only mode nothing blocks; the items are still reported so the
    warning count stays a real measurement (CR-004: 189 -> 292 is intentional
    tightening and must stay visible).
    """
    source_blocking: list[str] = []
    source_warning: list[str] = []
    skill_blocking: list[str] = []
    skill_warning: list[str] = []

    def route(finding: str, sink: str) -> None:
        if release:
            (source_blocking if sink == "source" else skill_blocking).append(finding)
        else:
            (source_warning if sink == "source" else skill_warning).append(finding)

    for source in data.get("sources", []):
        sid = source.get("id", "<no-id>")
        status = source.get("license_status")
        declared = source.get("license_declared")
        notice = source.get("notice_file")
        if status in LICENSE_BLOCKING_STATUS:
            route(f"source license_status={status}: {sid}", "source")
        if declared in LICENSE_BLOCKING_DECLARED:
            route(f"source license_declared={declared}: {sid}", "source")
        if source.get("maturity") == "unverified":
            route(f"source maturity=unverified: {sid}", "source")
        # 4.1 admission rule: redistributable requires verified + not-required +
        # verified maturity + a real notice file. Also 17.29(4).
        if status != "verified" and source.get("distribution") == "redistributable":
            route(
                f"admission violation: {sid} is redistributable with "
                f"license_status={status}",
                "source",
            )
        if status == "review-required" and not notice:
            route(
                f"4.1 violation: review-required source without notice_file: {sid}",
                "source",
            )
    for item in data.get("skills", []):
        status = item.get("license_status")
        label = item.get("path", item.get("id"))
        if status in LICENSE_BLOCKING_STATUS:
            route(f"license review required: {label}", "skill")
        if release and item.get("maturity") == "unverified":
            route(f"unverified skill: {label}", "skill")
    return source_blocking, skill_blocking, source_warning, skill_warning

def collect_errors(data: dict, summary: dict) -> tuple[list[str], list[str]]:
    """Structural checks. Returns (errors, warnings) -- both mode-independent."""
    errors: list[str] = []
    warnings: list[str] = []
    skills = data.get("skills", [])
    seen: set[str] = set()
    for item in skills:
        path_value = item.get("path") or item.get("adapted_path")
        if not path_value:
            errors.append(f"registry entry without path: {item.get('id')}")
            continue
        path = ROOT / path_value
        if path_value in seen:
            errors.append(f"duplicate registry path: {path_value}")
        seen.add(path_value)
        if not path.is_file():
            errors.append(f"registry path missing: {path_value}")
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        fm = frontmatter(text)
        if fm is None:
            errors.append(f"missing frontmatter: {path_value}")
        else:
            for key in REQUIRED_FRONTMATTER:
                if key not in fm:
                    errors.append(f"{path_value} missing {key}")
        if "## Integrated reverse-skill contract" not in text:
            errors.append(f"missing integration contract: {path_value}")
        if item.get("distribution") not in {"local-only", "redistributable"}:
            errors.append(
                f"4.2 violation: unknown distribution {item.get('distribution')!r}: "
                f"{path_value}"
            )
    for wrapper in WRAPPERS:
        path = ROOT / wrapper
        if not path.is_file():
            errors.append(f"wrapper missing: {wrapper}")
        elif "## ACTION REQUIRED" not in path.read_text(encoding="utf-8", errors="replace"):
            errors.append(f"wrapper missing ACTION REQUIRED: {wrapper}")
    unsafe = []
    for path in ROOT.rglob("*"):
        if path.is_file() and (
            path.name in UNSAFE_KEY_NAMES
            or path.suffix.lower() in UNSAFE_KEY_SUFFIXES
        ):
            unsafe.append(path)
    if unsafe:
        errors.extend(
            f"unsafe key material: {path.relative_to(ROOT).as_posix()}" for path in unsafe
        )
    return errors, warnings

def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    mode = "release" if args.release else "local-only"
    errors: list[str] = []
    warnings: list[str] = []

    if not REGISTRY.is_file():
        print("FAIL community registry is missing")
        return EXIT_BLOCKED
    try:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"FAIL community registry is unreadable: {exc}")
        return EXIT_BLOCKED

    summary = summarize(data)
    errors.extend(check_stats_against_arrays(data, summary))
    structural, structural_warnings = collect_errors(data, summary)
    errors.extend(structural)
    warnings.extend(structural_warnings)

    source_blocking, skill_blocking, source_warning, skill_warning = check_license_state(
        data, args.release
    )
    if args.release:
        errors.extend(source_blocking)
        errors.extend(skill_blocking)
        source_findings, skill_findings = len(source_blocking), len(skill_blocking)
    else:
        warnings.extend(source_warning)
        warnings.extend(skill_warning)
        source_findings, skill_findings = len(source_warning), len(skill_warning)

    print(f"mode={mode}")
    print(
        f"sources={summary['sources']} skills={summary['skills']} "
        f"excluded={summary['excluded']} errors={len(errors)} warnings={len(warnings)}"
    )
    print(
        "license_status="
        + json.dumps(summary["license_counts"], sort_keys=True, ensure_ascii=False)
    )
    print(
        "maturity=" + json.dumps(summary["maturity_counts"], sort_keys=True, ensure_ascii=False)
    )
    # Findings are reported scope-separated so a coordinator can recompute the
    # recorded baseline (292, skill-scoped) without subtracting source findings
    # out of a combined total. `source_scoped` counts sources[] findings,
    # `skill_scoped` counts skills[] findings.
    print(
        f"findings: source_scoped={source_findings} skill_scoped={skill_findings} "
        f"total={source_findings + skill_findings}"
    )
    if args.release and (source_findings or skill_findings):
        print(
            f"FAIL release mode: {source_findings + skill_findings} "
            "redistribution-blocking license/provenance finding(s) (spec 17.29)"
        )
    for warning in warnings[:10]:
        print(f"WARN {warning}")
    if len(warnings) > 10:
        print(f"WARN ... {len(warnings) - 10} more license-review entries")
    if errors:
        for error in errors[:20]:
            print(f"FAIL {error}")
        if len(errors) > 20:
            print(f"FAIL ... {len(errors) - 20} more")
        print(f"FAIL validate-integration: {len(errors)} error(s) in mode={mode}")
        return EXIT_BLOCKED
    if warnings:
        # Deliberately NOT an exit code. The recorded baseline for this gate is
        # `exit 0` with 292 license-review warnings (WORK-BOARD CR-004 records
        # 189 -> 292 as intentional tightening). Spec 4.7 maps 10 to
        # needs_review, and this repository already treats 10 as non-blocking,
        # so promoting warnings to 10 would change a recorded gate result
        # without adding any blocking power. The blocking power lives in
        # --release, which returns 20. See docs/COMMUNITY-LICENSE-MATRIX.md.
        print(
            f"REVIEW validate-integration: {len(warnings)} license-review "
            f"entry/entries in mode={mode} (non-blocking in {mode})"
        )
    print(f"INTEGRATION VALIDATION PASSED (mode={mode})")
    return EXIT_OK

if __name__ == "__main__":
    raise SystemExit(main())
