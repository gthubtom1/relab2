#!/usr/bin/env python3
"""Release / provenance gate for the community integration (spec 17.29).

This is the *second* gate. `validate-integration.py` answers "is the adapter
boundary structurally sound?"; this script answers the separate question
"may this tree be redistributed?", which spec 17.29 says a per-source
`license_status` is not enough to answer.

Two modes, and the exit code always matches the mode:

  local-only   (default)   every finding is a warning. This is the mode the
                          current tree is allowed to sit in: 17.29(6) forces
                          `mixed`/`NOASSERTION` to local-only, and 17.28
                          forces digest-only sources to local-only. The tree
                          has no verified, attested, notice-complete source
                          set, so it is a local-only integration candidate.
  release      (--release) every finding blocks and the script exits 20.
                          There is deliberately no way to reach exit 0 in
                          release mode with the current registry: the gate
                          does not have a "warn and pass" release path, and
                          it must not grow one to make a release look green.

Exit codes follow the frozen table in spec 4.7:
  0   ok            (local-only, no structural error)
  10  needs_review  (not emitted; reserved so callers can key off the table)
  20  blocked       (structural error in any mode, or any finding in release)
  2   usage         (argparse; an unknown argument is an error, never a no-op)

Read-only: this script never writes, moves or deletes anything, and it never
executes vendored content (spec 17.31 forbids running untrusted vendor code in
a gate). Untrusted text is only parsed and compared.

Every number printed is derived from the registry and the filesystem. The
script contains no hardcoded source count, no hardcoded skill count and no
hardcoded license-state total, so T12 (source lock) and T21 (canonical base
record) can change the registry without this gate lying about it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = ROOT / "skills/community/registry.json"
NOTICE = "NOTICE"

# 4.1 legal license_status enum. Anything outside this set is itself a finding.
LICENSE_STATUS_ENUM = frozenset({"verified", "review-required", "missing-license", "mixed"})
DISTRIBUTION_ENUM = frozenset({"local-only", "redistributable"})
MATURITY_ENUM = frozenset({"verified", "partial", "unverified"})

# 17.29 states that block redistribution.
BLOCKING_STATUS = frozenset({"missing-license", "review-required", "mixed"})
BLOCKING_DECLARED = frozenset({"NOASSERTION", "NONE", "NOASSERTION OR MIT"})

# The distribution license of this repository, read from the root LICENSE.
# 17.29(2): the union of every merged license must be compatible with it.
PERMISSIVE_COMPATIBLE = frozenset(
    {
        "MIT",
        "MIT-0",
        "0BSD",
        "Apache-2.0",
        "BSD-2-Clause",
        "BSD-3-Clause",
        "ISC",
        "Zlib",
        "Unlicense",
        "CC0-1.0",
        "Python-2.0",
        "0bsd",
    }
)
# Copyleft that cannot be merged into an MIT-licensed combined work without
# relicensing the whole package; 17.29(2) then requires splitting the bundle or
# downgrading to local-only.
COPYLEFT_INCOMPATIBLE = frozenset(
    {
        "GPL-1.0-only",
        "GPL-2.0-only",
        "GPL-3.0-only",
        "GPL-1.0-or-later",
        "GPL-2.0-or-later",
        "GPL-3.0-or-later",
        "AGPL-3.0-only",
        "AGPL-3.0-or-later",
        "SSPL-1.0",
        "OSL-3.0",
        "EUPL-1.2",
        "CC-BY-SA-4.0",
        "CDDL-1.0",
        "MPL-2.0",
    }
)

# 17.29(3): vendored content classes that need an independent license record.
TRANSITIVE_CLASSES = {
    "binary": frozenset({".exe", ".dll", ".so", ".dylib", ".bin", ".jar", ".war", ".apk", ".a", ".o", ".wasm"}),
    "archive": frozenset({".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".whl"}),
    "image": frozenset({".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico", ".tiff"}),
    "font": frozenset({".ttf", ".otf", ".woff", ".woff2", ".eot"}),
    "media": frozenset({".mp3", ".mp4", ".wav", ".mov", ".avi", ".ogg"}),
    "dataset": frozenset({".csv", ".tsv", ".parquet", ".jsonl", ".npy", ".npz", ".pkl", ".h5"}),
    "package": frozenset({".whl", ".egg", ".gem", ".crate"}),
    "submodule": frozenset({".gitmodules", ".gitmodule"}),
}
CLASS_BY_SUFFIX: dict[str, str] = {
    suffix: name for name, suffixes in TRANSITIVE_CLASSES.items() for suffix in suffixes
}

# Sources whose third-party inventory this gate enumerates explicitly.
# Not a hardcoded count -- the list selects *what to itemise*, and the counts
# inside come from the registry and the tree.
INVENTORY_SOURCES = ("hack-skills", "ctf-super-hub")

EXIT_OK = 0
EXIT_NEEDS_REVIEW = 10
EXIT_BLOCKED = 20
EXIT_USAGE = 2

HEX40 = re.compile(r"^[0-9a-f]{40}$")

# Severity classes. Only `structural` corruption blocks in *every* mode: a
# registry whose enums, digests or file references do not line up is broken
# data, not a licensing question, and reading a "pass" out of it would be a
# false green. The license/provenance classes are exactly the ones 17.29 wants
# to block *for redistribution*, so they are warnings under local-only and hard
# failures under --release.
STRUCTURAL_CHECKS = frozenset(
    {
        "R01",  # sources[] missing/empty
        "R02",  # commit is not a 40-hex object id
        "R03",  # license_status outside the 4.1 enum
        "R04",  # distribution outside the 4.2 enum
        "R05",  # maturity outside the 4.1 enum
        "R06",  # 4.1 admission: redistributable requires verified
        "R07",  # skill record without a path
        "R08",  # duplicate / missing registry path
        "R09",  # notice_file recorded but dangling
        "R11",  # stats disagree with the arrays they count
        "R12",  # content_hash drift
        "R20",  # a named inventory source has no snapshot at all
    }
)
# R09P is the same check with the *absence* of a notice rather than a dangling
# pointer: absence blocks redistribution (17.29(4)) but is not broken data.
PROVENANCE_CHECKS = frozenset(
    {"R09P", "R10", "R13", "R14", "R15", "R16", "R17", "R18", "R19"}
)

class Finding:
    """One gate result. `check` is stable so negative controls can cite it."""

    __slots__ = ("check", "scope", "message")

    def __init__(self, check: str, scope: str, message: str) -> None:
        self.check = check
        self.scope = scope
        self.message = message

    def as_dict(self) -> dict:
        return {
            "check": self.check,
            "scope": self.scope,
            "severity": "structural" if self.check in STRUCTURAL_CHECKS else "provenance",
            "message": self.message,
        }

    def text(self) -> str:
        return f"[{self.check}] {self.scope}: {self.message}"

def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def aggregate_digest(paths: list[Path]) -> str:
    """Order-independent-by-sort aggregate sha256 over (relpath, filehash) pairs.

    Used to give the transitive-dependency inventory a real digest even when
    the registry carries no per-file record for those files (17.29(3)).
    """
    accumulator = hashlib.sha256()
    for path in sorted(paths, key=lambda p: p.as_posix()):
        accumulator.update(path.as_posix().encode("utf-8"))
        accumulator.update(b"\0")
        accumulator.update(sha256_file(path).encode("ascii"))
        accumulator.update(b"\n")
    return accumulator.hexdigest()

def read_root_license_id(root: Path) -> tuple[str | None, str | None]:
    """Identify the distribution license from the root LICENSE (17.29(2))."""
    path = root / "LICENSE"
    if not path.is_file():
        return None, "root LICENSE is missing"
    text = path.read_text(encoding="utf-8", errors="replace")
    if "Apache License" in text and "Version 2.0" in text:
        return "Apache-2.0", None
    if "GNU AFFERO" in text.upper():
        return "AGPL-3.0", None
    if "GNU GENERAL PUBLIC LICENSE" in text.upper():
        return "GPL", None
    if "MIT License" in text or "Permission is hereby granted, free of charge" in text:
        return "MIT", None
    return None, "root LICENSE text is not one of the recognised licenses"

def snapshot_map(skills: list[dict], root: Path) -> dict[str, dict]:
    """Map each `community-raw/<dir>` to the source id that owns it.

    Derived from the registry, not from a hardcoded directory list: the owner
    is the source id that owns the most adapted paths under that directory.
    """
    owners: dict[str, dict[str, int]] = {}
    for item in skills:
        path_value = item.get("path") or item.get("adapted_path") or ""
        parts = path_value.split("/")
        if len(parts) < 3 or parts[0] != "community-raw":
            continue
        directory = parts[1]
        owners.setdefault(directory, {})
        source_id = item.get("source", "<no-source>")
        owners[directory][source_id] = owners[directory].get(source_id, 0) + 1
    result: dict[str, dict] = {}
    for directory, tally in owners.items():
        winner = max(tally.items(), key=lambda kv: (kv[1], kv[0]))
        result[directory] = {
            "source": winner[0],
            "skill_count": winner[1],
            "ambiguous": len(tally) > 1,
            "path": root / "community-raw" / directory,
        }
    return result

def collateral_inventory(skills: list[dict], root: Path) -> dict[str, dict]:
    """Transitive dependency inventory (17.29(3)).

    Collateral = every file under `community-raw/<dir>/` that is *not* the
    adapted path of a registry skill. These are the vendored scripts,
    references, templates, sample code, binaries, images and datasets that
    ride along inside a snapshot without their own registry license record.
    """
    adapted: dict[str, set[str]] = {}
    for item in skills:
        path_value = item.get("path") or item.get("adapted_path") or ""
        parts = path_value.split("/")
        if len(parts) >= 3 and parts[0] == "community-raw":
            adapted.setdefault(parts[1], set()).add("/".join(parts[2:]))

    inventory: dict[str, dict] = {}
    for directory, info in snapshot_map(skills, root).items():
        base: Path = info["path"]
        known = adapted.get(directory, set())
        files = [f for f in base.rglob("*") if f.is_file()] if base.is_dir() else []
        extra = [f for f in files if f.relative_to(base).as_posix() not in known]
        classes: dict[str, int] = {}
        for path in extra:
            class_name = CLASS_BY_SUFFIX.get(path.suffix.lower())
            if class_name is None and path.name in {".gitmodules"}:
                class_name = "submodule"
            if class_name:
                classes[class_name] = classes.get(class_name, 0) + 1
        inventory[directory] = {
            "source": info["source"],
            "skill_count": info["skill_count"],
            "total_files": len(files),
            "collateral_files": len(extra),
            "registered_classes": classes,
            "collateral_digest": aggregate_digest(extra) if extra else None,
            "examples": [
                f.relative_to(root).as_posix() for f in sorted(extra, key=lambda p: p.as_posix())[:5]
            ],
        }
    return inventory

def notice_agreement(root: Path, source: dict) -> list[tuple[str, str]]:
    """Field-by-field agreement between a notice file and the registry (17.29(4)).

    Returns (code, message) pairs so the caller keeps the finding code and the
    message stays free of the code label.
    """
    problems: list[tuple[str, str]] = []
    notice_value = source.get("notice_file")
    sid = source.get("id", "<no-id>")
    if not notice_value:
        # A null notice_file is a well-formed record of "no notice exists yet".
        # 17.29(4) only requires a notice for `redistributable` sources, so this
        # is a redistribution blocker (provenance), not broken data.
        return [("R09P", f"{sid}: notice_file is null, 17.29(4) requires a notice per redistributable source")]
    notice_path = root / notice_value
    if not notice_path.is_file():
        # A notice_file that points at a path which is not on disk is a lying
        # record. That is corruption, and it fails in both modes.
        return [("R09", f"{sid}: notice_file {notice_value} is recorded but does not exist on disk")]
    text = notice_path.read_text(encoding="utf-8", errors="replace")
    declared = source.get("license_declared")
    if declared in PERMISSIVE_COMPATIBLE:
        # "MIT" is not a substring of "Apache License 2.0", so this is a real
        # cross-check rather than a no-op.
        if declared.upper() not in text.upper():
            problems.append(
                (
                    "R10",
                    f"{sid}: notice {notice_value} does not mention declared "
                    f"license {declared!r}",
                )
            )
    url = source.get("source_url") or ""
    if url and url not in text:
        problems.append(
            ("R10", f"{sid}: notice {notice_value} does not carry source_url {url}")
        )
    commit = source.get("commit") or ""
    if commit and commit not in text:
        problems.append(
            (
                "R10",
                f"{sid}: notice {notice_value} does not carry resolved commit "
                f"{commit} (17.28)",
            )
        )
    return problems

def check_registry(data: dict, findings: list[Finding]) -> dict:
    """Structural / enum checks. Independent of mode."""
    sources = data.get("sources")
    if not isinstance(sources, list) or not sources:
        findings.append(Finding("R01", "registry", "sources[] is missing or empty"))
        return {"sources": [], "skills": [], "excluded": [], "stats": {}}
    for source in sources:
        sid = source.get("id", "<no-id>")
        if not HEX40.match(source.get("commit") or ""):
            findings.append(
                Finding("R02", f"source:{sid}", f"commit is not a 40-hex object id: {source.get('commit')!r}")
            )
        if source.get("license_status") not in LICENSE_STATUS_ENUM:
            findings.append(
                Finding(
                    "R03",
                    f"source:{sid}",
                    f"license_status {source.get('license_status')!r} is outside the 4.1 enum",
                )
            )
        if source.get("distribution") not in DISTRIBUTION_ENUM:
            findings.append(
                Finding(
                    "R04",
                    f"source:{sid}",
                    f"distribution {source.get('distribution')!r} is outside the 4.2 enum",
                )
            )
        if source.get("maturity") not in MATURITY_ENUM:
            findings.append(
                Finding(
                    "R05",
                    f"source:{sid}",
                    f"maturity {source.get('maturity')!r} is outside the 4.1 enum",
                )
            )
        # 4.1 admission rule: redistributable requires a verified license.
        if source.get("distribution") == "redistributable" and source.get("license_status") != "verified":
            findings.append(
                Finding(
                    "R06",
                    f"source:{sid}",
                    f"distribution=redistributable with license_status="
                    f"{source.get('license_status')!r}",
                )
            )
        for code, problem in notice_agreement(ROOT, source):
            findings.append(Finding(code, "notice", problem))
    skills = data.get("skills", [])
    seen: set[str] = set()
    for item in skills:
        path_value = item.get("path") or item.get("adapted_path")
        label = path_value or item.get("id", "<no-id>")
        if not path_value:
            findings.append(Finding("R07", "skills", f"registry entry without path: {item.get('id')}"))
            continue
        if path_value in seen:
            findings.append(Finding("R08", "skills", f"duplicate registry path: {path_value}"))
        seen.add(path_value)
        if not (ROOT / path_value).is_file():
            findings.append(Finding("R08", "skills", f"registry path missing on disk: {label}"))
    stats = data.get("stats", {})
    if stats.get("adapted_skill_count") != len(skills):
        findings.append(
            Finding(
                "R11",
                "registry",
                f"stats.adapted_skill_count={stats.get('adapted_skill_count')!r} "
                f"!= len(skills)={len(skills)}",
            )
        )
    excluded = data.get("excluded", [])
    if stats.get("excluded_framework_skill_count") != len(excluded):
        findings.append(
            Finding(
                "R11",
                "registry",
                f"stats.excluded_framework_skill_count="
                f"{stats.get('excluded_framework_skill_count')!r} != len(excluded)={len(excluded)}",
            )
        )
    return {"sources": sources, "skills": skills, "excluded": excluded, "stats": stats}

def check_content_hashes(skills: list[dict], findings: list[Finding]) -> dict:
    """17.29 digest record: every adapted path must still hash to its record."""
    verified = 0
    for item in skills:
        path_value = item.get("path") or item.get("adapted_path")
        if not path_value:
            continue
        path = ROOT / path_value
        if not path.is_file():
            continue
        recorded = item.get("content_hash") or ""
        actual = "sha256:" + sha256_file(path)
        if not recorded.startswith("sha256:"):
            findings.append(
                Finding("R12", f"skill:{path_value}", f"content_hash is not a sha256 record: {recorded!r}")
            )
            continue
        if recorded != actual:
            findings.append(
                Finding(
                    "R12",
                    f"skill:{path_value}",
                    f"content_hash drift: registry={recorded} actual={actual}",
                )
            )
            continue
        verified += 1
    return {"verified": verified, "total": len(skills)}

def check_combined_license(sources: list[dict], findings: list[Finding], root_license: str) -> dict:
    """17.29(2) combined compatibility: union of merged licenses vs the target."""
    union = sorted({s.get("license_declared") or "<undeclared>" for s in sources})
    incompatible: list[str] = []
    unknown: list[str] = []
    for item in union:
        if item in COPYLEFT_INCOMPATIBLE:
            incompatible.append(item)
            findings.append(
                Finding(
                    "R13",
                    "combined-license",
                    f"{item} is copyleft and cannot be merged into an "
                    f"{root_license}-licensed bundle; 17.29(2) requires a split "
                    "bundle or local-only",
                )
            )
        elif item not in PERMISSIVE_COMPATIBLE:
            unknown.append(item)
            findings.append(
                Finding(
                    "R13",
                    "combined-license",
                    f"{item} has no compatibility verdict against the "
                    f"{root_license} distribution license; treated as "
                    "NOASSERTION per 17.29(1)",
                )
            )
    return {
        "target": root_license,
        "union": union,
        "incompatible": incompatible,
        "undetermined": unknown,
        "verdict": "incompatible" if incompatible else ("undetermined" if unknown else "compatible"),
    }

def check_release_blockers(
    sources: list[dict], skills: list[dict], findings: list[Finding]
) -> dict:
    """17.29(6) + 17.28: what forbids redistribution for each source."""
    per_source: dict[str, dict] = {}
    for source in sources:
        sid = source.get("id", "<no-id>")
        status = source.get("license_status")
        declared = source.get("license_declared")
        maturity = source.get("maturity")
        reasons: list[str] = []
        if status in BLOCKING_STATUS:
            reasons.append(f"license_status={status}")
        if declared in BLOCKING_DECLARED or declared not in PERMISSIVE_COMPATIBLE:
            reasons.append(f"license_declared={declared}")
        if maturity == "unverified":
            reasons.append("maturity=unverified")
        # 17.28: a locked commit is not proof of content. tree_digest /
        # source_manifest are the offline-verifiable attestation; all are null.
        if not source.get("tree_digest") or not source.get("source_manifest"):
            reasons.append("no source_manifest/tree_digest (17.28 attestation absent)")
        if not source.get("notice_file"):
            reasons.append("no notice_file (17.29(4))")
        per_source[sid] = {
            "reasons": reasons,
            "skill_count": sum(1 for s in skills if s.get("source") == sid),
        }
        for reason in reasons:
            findings.append(Finding("R14", f"source:{sid}", f"redistribution blocked: {reason}"))

    skill_blockers: dict[str, int] = {}
    for item in skills:
        status = item.get("license_status")
        maturity = item.get("maturity")
        if status in BLOCKING_STATUS:
            skill_blockers[status] = skill_blockers.get(status, 0) + 1
            findings.append(
                Finding("R15", f"skill:{item.get('path')}", f"license_status={status} blocks redistribution")
            )
        # 17.29(6)/4.1: an unverified maturity is not releasable content either.
        if maturity == "unverified":
            skill_blockers["unverified"] = skill_blockers.get("unverified", 0) + 1
            findings.append(
                Finding("R15", f"skill:{item.get('path')}", "maturity=unverified blocks redistribution")
            )
        if item.get("distribution") == "redistributable" and status != "verified":
            findings.append(
                Finding(
                    "R15",
                    f"skill:{item.get('path')}",
                    f"distribution=redistributable with license_status={status!r}",
                )
            )
    return {"per_source": per_source, "skill_blockers": skill_blockers}

def check_attestation_and_scanning(sources: list[dict], findings: list[Finding]) -> dict:
    """17.28(offline attestation) + 17.29(5) known-CVE scan record."""
    attested: list[str] = []
    unattested: list[str] = []
    for source in sources:
        sid = source.get("id", "<no-id>")
        if source.get("tree_digest") and source.get("source_manifest"):
            attested.append(sid)
        else:
            unattested.append(sid)
    if unattested:
        findings.append(
            Finding(
                "R16",
                "attestation",
                f"no offline-verifiable source attestation for {len(unattested)} source(s): "
                + ", ".join(sorted(unattested))
                + " (17.28: digest-only -> local-only)",
            )
        )
    # 17.29(5) requires the release manifest to record the scanning tool and
    # library version. No such record exists in this repository, and this gate
    # performs no network access, so the condition is reported as unmet rather
    # than assumed satisfied.
    findings.append(
        Finding(
            "R17",
            "cve-scan",
            "no known-CVE scan record (tool + library version) is present in the "
            "release manifest; 17.29(5) unmet",
        )
    )
    return {"attested": sorted(attested), "unattested": sorted(unattested), "cve_scan_record": None}

def check_root_notice(sources: list[dict], findings: list[Finding], registry_digest: str) -> dict:
    """Root NOTICE must exist and name every source id it covers (17.29(4))."""
    path = ROOT / NOTICE
    if not path.is_file():
        findings.append(Finding("R18", "notice", f"{NOTICE} is missing at the repository root"))
        return {"present": False, "referenced_sources": []}
    text = path.read_text(encoding="utf-8", errors="replace")
    referenced = [s.get("id") for s in sources if s.get("id") and s.get("id") in text]
    missing = [s.get("id") for s in sources if s.get("id") and s.get("id") not in text]
    for sid in missing:
        findings.append(Finding("R18", "notice", f"{NOTICE} does not name source id {sid}"))
    return {"present": True, "referenced_sources": sorted(referenced), "unreferenced": sorted(missing)}

def check_inventory_coverage(inventory: dict[str, dict], findings: list[Finding]) -> dict:
    """17.29(3): collateral classes need an independent license record.

    The registry schema (T02 owns it) has no per-file license field, so the
    recorded coverage is zero for every class that is actually present. That is
    reported as a finding rather than assumed.
    """
    summary: dict[str, dict] = {}
    for directory, info in sorted(inventory.items()):
        classes = info["registered_classes"]
        recorded = {name: 0 for name in classes}
        summary[directory] = {
            "source": info["source"],
            "collateral_files": info["collateral_files"],
            "classes": classes,
            "records": recorded,
        }
        if info["collateral_files"]:
            findings.append(
                Finding(
                    "R19",
                    f"transitive:{directory}",
                    f"{info['collateral_files']} collateral file(s) outside the "
                    f"registry skill records have no independent license record "
                    f"(17.29(3)); digest="
                    f"{(info['collateral_digest'] or '')[:16]}",
                )
            )
        for class_name, count in sorted(classes.items()):
            if recorded[class_name] < count:
                findings.append(
                    Finding(
                        "R19",
                        f"transitive:{directory}",
                        f"class {class_name}: {count} file(s), "
                        f"{recorded[class_name]} independent license record(s)",
                    )
                )
    return summary

def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="verify-release-gate.py",
        description="Redistribution / provenance gate (spec 17.29). local-only warns, "
                    "--release blocks. An unknown argument is an error.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--release",
        action="store_true",
        help="release mode: every 17.29 finding blocks and the script exits 20",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="emit the full report as JSON on stdout",
    )
    parser.add_argument(
        "--root",
        default=None,
        help="repository root to evaluate (default: the checkout this script "
        "lives in). Exists so a negative control can run the *same* gate "
        "against a mutated fixture tree; it cannot make a real tree pass, "
        "because every check still reads that root's own files.",
    )
    return parser.parse_args(argv)

def main(argv: list[str] | None = None) -> int:
    global ROOT, DEFAULT_REGISTRY
    args = parse_args(sys.argv[1:] if argv is None else argv)
    mode = "release" if args.release else "local-only"

    if args.root:
        ROOT = Path(args.root).resolve()
        DEFAULT_REGISTRY = ROOT / "skills/community/registry.json"

    if not DEFAULT_REGISTRY.is_file():
        print("FAIL community registry is missing", file=sys.stderr)
        return EXIT_BLOCKED
    try:
        data = json.loads(DEFAULT_REGISTRY.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"FAIL community registry is unreadable: {exc}", file=sys.stderr)
        return EXIT_BLOCKED

    registry_digest = sha256_file(DEFAULT_REGISTRY)
    findings: list[Finding] = []

    # Structural findings are errors in every mode: an unreadable enum or a
    # broken notice reference is not a "needs review" condition.
    structural = check_registry(data, findings)
    sources = structural["sources"]
    skills = structural["skills"]

    root_license, license_problem = read_root_license_id(ROOT)
    if root_license is None:
        findings.append(Finding("R13", "combined-license", license_problem or "unknown root license"))
        root_license = "UNKNOWN"

    hashes = check_content_hashes(skills, findings)
    combined = check_combined_license(sources, findings, root_license)
    blockers = check_release_blockers(sources, skills, findings)
    attestation = check_attestation_and_scanning(sources, findings)
    notice = check_root_notice(sources, findings, registry_digest)
    inventory = collateral_inventory(skills, ROOT)
    inventory_summary = check_inventory_coverage(inventory, findings)

    # Everything the report asserts about the hack-skills and CTF snapshots.
    itemised = {
        directory: summary
        for directory, summary in inventory_summary.items()
        if summary["source"] in INVENTORY_SOURCES
    }
    for wanted in INVENTORY_SOURCES:
        if not any(summary["source"] == wanted for summary in inventory_summary.values()):
            findings.append(
                Finding("R20", "inventory", f"{wanted} has no community-raw snapshot to itemise")
            )

    by_check: dict[str, int] = {}
    by_severity = {"structural": 0, "provenance": 0}
    for finding in findings:
        by_check[finding.check] = by_check.get(finding.check, 0) + 1
        by_severity["structural" if finding.check in STRUCTURAL_CHECKS else "provenance"] += 1
    structural_count = by_severity["structural"]
    provenance_count = by_severity["provenance"]

    report = {
        "mode": mode,
        "registry_digest": "sha256:" + registry_digest,
        "counts": {
            "sources": len(sources),
            "skills": len(skills),
            "excluded": len(structural["excluded"]),
            "findings": len(findings),
            "findings_structural": structural_count,
            "findings_provenance": provenance_count,
            "findings_by_check": dict(sorted(by_check.items())),
        },
        "content_hashes": hashes,
        "combined_license": combined,
        "release_blockers": blockers,
        "attestation": attestation,
        "root_notice": notice,
        "transitive_inventory": inventory_summary,
        "itemised_sources": sorted(itemised),
        "findings": [f.as_dict() for f in findings],
    }

    if args.as_json:
        # stdout must be exactly one parseable JSON document, so every human
        # line goes to stderr. A --json mode that interleaves prose is not a
        # machine-readable mode.
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        out = lambda text: print(text, file=sys.stderr)  # noqa: E731
    else:
        out = print
        print(f"mode={mode}")
        print(
            f"sources={len(sources)} skills={len(skills)} "
            f"excluded={len(structural['excluded'])} findings={len(findings)}"
        )
        print(f"registry_digest=sha256:{registry_digest}")
        print(
            f"content_hash: verified={hashes['verified']}/{hashes['total']} "
            "(sha256 over each adapted path)"
        )
        print(
            f"combined_license: target={combined['target']} "
            f"union={json.dumps(combined['union'], ensure_ascii=False)} "
            f"verdict={combined['verdict']}"
        )
        print(
            f"attestation: attested={len(attestation['attested'])} "
            f"unattested={len(attestation['unattested'])} cve_scan_record="
            f"{attestation['cve_scan_record']}"
        )
        print(
            f"root_notice: present={notice['present']} "
            f"referenced={len(notice.get('referenced_sources', []))}/{len(sources)}"
        )
        print("transitive_inventory (17.29(3)):")
        for directory, summary in sorted(inventory_summary.items()):
            print(
                f"  {directory}: source={summary['source']} "
                f"collateral={summary['collateral_files']} "
                f"classes={json.dumps(summary['classes'], sort_keys=True)} "
                f"digest={(inventory[directory]['collateral_digest'] or '-')[:16]}"
            )
        print(
            "third_party_inventory (itemised sources): "
            + (", ".join(sorted(itemised)) or "none")
        )
        blocking = structural_count > 0 or args.release
        prefix = "FAIL" if blocking else "WARN"
        for finding in findings[:15]:
            out(f"{prefix} {finding.text()}")
        if len(findings) > 15:
            out(f"{prefix} ... {len(findings) - 15} more")

    if not findings:
        out(
            f"RELEASE GATE: no 17.29 finding (mode={mode})"
            if not args.release
            else f"RELEASE GATE: no blocking finding (mode={mode})"
        )
        return EXIT_OK

    if structural_count:
        # Broken data blocks regardless of mode: a registry whose enums, digests
        # or file references do not line up cannot be reasoned about at all.
        out(
            f"BLOCKED: {structural_count} structural finding(s) across "
            f"{len({f.check for f in findings if f.check in STRUCTURAL_CHECKS})} "
            f"check(s); these are not license questions and fail in both modes "
            f"(spec 4.7 exit {EXIT_BLOCKED})"
        )
        return EXIT_BLOCKED
    if args.release:
        out(
            f"BLOCKED release mode: {provenance_count} 17.29 redistribution/"
            f"provenance finding(s) across {len(by_check)} check(s) "
            f"(spec 4.7 exit {EXIT_BLOCKED})"
        )
        return EXIT_BLOCKED
    out(
        f"RELEASE GATE: {len(findings)} provenance finding(s) recorded, "
        f"non-blocking in local-only mode (spec 17.29(6): mixed/NOASSERTION "
        f"-> local-only)"
    )
    return EXIT_OK

if __name__ == "__main__":
    raise SystemExit(main())
