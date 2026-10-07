#!/usr/bin/env python3
"""Build (or re-verify) a release candidate bundle (spec T16, 17.15 / 17.29).

What this script does:
  * reads the registry, the source lock and the on-disk tree (read-only);
  * writes a candidate directory OUTSIDE the repository containing:
      candidate-manifest.json   member list + sha256 + registry/source digests
                                + distribution verdict + rollback target
      sbom.json                 minimal CycloneDX-style component inventory
                                derived from the registry (no network)
      checksums.sha256          sorted sha256 lines over the bundle files
  * --check re-reads a candidate directory and fails (exit 20) on any
    one-byte tamper.

What this script refuses (exit 20, never a warning):
  * marking the candidate `redistributable`: there is no verifiable
    signature anywhere in this repository (T21 records unsigned), so
    17.15 forbids any redistributable claim. Only `local-only` is emitted.
  * writing the bundle inside the repository tree (the real checkout stays
    read-only; the lab/official build dir must be outside the repo).

Exit codes follow the frozen spec 4.7 table:
  0 ok | 10 needs_review (no .git: rollback commit not machine-checkable,
     each item named) | 20 blocked (tamper, redistributable claim,
     unreadable registry) | 2 usage (argparse).

Read-only vs the repo: this script never writes, moves or deletes anything
under the repository root, and it never executes vendored content.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT = Path(__file__).resolve()
DEFAULT_ROOT = SCRIPT.parents[1]

CANDIDATE_SCHEMA_VERSION = "1.0"
SBOM_SPEC = "CycloneDX/1.5-minimal"

EXIT_OK = 0
EXIT_NEEDS_REVIEW = 10
EXIT_BLOCKED = 20
EXIT_USAGE = 2

# Files whose digests pin the release decision (17.21: a PR that edits a gate
# after the approval was cut must not be able to ride on that approval).
GATE_PIN_FILES = [
    "scripts/verify-release-gate.py",
    "scripts/validate-integration.py",
    "scripts/verify-canonical-base-lock.py",
    "scripts/build-release-candidate.py",
    "scripts/verify-release-approval.py",
]

def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )

def git_head(root: Path) -> tuple[str | None, str | None]:
    """Return (head_commit, note). No network, no writes, read-only probe."""
    if not (root / ".git").exists():
        return None, "no .git: integration commit not machine-checkable"
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return None, f"git probe failed: {exc}"
    head = out.stdout.strip()
    if out.returncode != 0 or len(head) != 40:
        return None, "git rev-parse did not return a 40-hex HEAD"
    return head, None

def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"FAIL unreadable JSON: {path}: {exc}", file=sys.stderr)
        raise SystemExit(EXIT_BLOCKED)

def build_components(registry: dict) -> list[dict]:
    """SBOM components derived from registry records only (17.29(1)-(3)).

    License text is NOT re-parsed here: the component license field repeats
    the registry's own declaration, or NOASSERTION when the registry has no
    usable SPDX value. Anything the registry cannot assert stays unasserted;
    this inventory can therefore never launder a local-only tree into a
    redistributable one.
    """
    components: list[dict] = []
    for source in registry.get("sources", []):
        declared = source.get("license_declared")
        components.append(
            {
                "type": "library",
                "group": "sources",
                "name": source.get("id", "<no-id>"),
                "version": (source.get("commit") or "")[:12] or "unknown",
                "licenses": (
                    [{"license": {"id": declared}}]
                    if declared not in (None, "", "NOASSERTION", "NONE")
                    else [{"license": {"id": "NOASSERTION"}}]
                ),
                "properties": [
                    {"name": "t16:license_status",
                     "value": str(source.get("license_status"))},
                    {"name": "t16:maturity",
                     "value": str(source.get("maturity"))},
                    {"name": "t16:distribution",
                     "value": str(source.get("distribution"))},
                    {"name": "t16:tree_digest",
                     "value": str(source.get("tree_digest") or "absent")},
                ],
            }
        )
    for item in registry.get("skills", []):
        declared = item.get("license_declared") or item.get("license_status")
        components.append(
            {
                "type": "library",
                "group": "skills",
                "name": item.get("path") or item.get("id", "<no-id>"),
                "version": (item.get("content_hash") or "")[-12:]
                or "unknown",
                "licenses": (
                    [{"license": {"id": "NOASSERTION"}}]
                    if declared in (None, "", "NOASSERTION", "NONE",
                                    "missing-license", "review-required",
                                    "mixed", "unverified")
                    else [{"license": {"id": str(declared)}}]
                ),
                "properties": [
                    {"name": "t16:source",
                     "value": str(item.get("source"))},
                    {"name": "t16:license_status",
                     "value": str(item.get("license_status"))},
                ],
            }
        )
    components.sort(key=lambda c: (c["group"], c["name"]))
    return components

def cmd_build(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    out = Path(args.out_dir).resolve()
    try:
        out.relative_to(root)
        inside = True
    except ValueError:
        inside = False
    if inside and not args.allow_in_tree:
        print(
            "FAIL refused: --out-dir resolves inside the repository tree; "
            "the real checkout stays read-only "
            "(pass --allow-in-tree only for a throwaway lab fixture)",
            file=sys.stderr,
        )
        return EXIT_BLOCKED
    if args.distribution != "local-only":
        # 17.15: no verifiable signature exists (T21: unsigned), so a
        # redistributable candidate cannot be built. This is a refusal,
        # not a degraded success.
        print(
            "FAIL refused: distribution=redistributable requires a verifiable "
            "signature (17.15); this repository records signature.present=false "
            "(see docs/community/CANONICAL-BASE-LOCK.md section 3). "
            "Only local-only candidates can be built.",
            file=sys.stderr,
        )
        return EXIT_BLOCKED

    registry_path = root / "skills/community/registry.json"
    lock_path = root / "skills/community/source-lock.json"
    notice_path = root / "NOTICE"
    if not registry_path.is_file():
        print("FAIL community registry is missing", file=sys.stderr)
        return EXIT_BLOCKED
    registry = load_json(registry_path)
    lock = load_json(lock_path) if lock_path.is_file() else None

    registry_digest = sha256_file(registry_path)
    head, head_note = git_head(root)
    gate_pins = {}
    for rel in GATE_PIN_FILES:
        p = root / rel
        gate_pins[rel] = (
            "sha256:" + sha256_file(p) if p.is_file() else "absent:" + rel
        )

    member_relpaths = [
        "skills/community/registry.json",
        "skills/community/source-lock.json",
        "NOTICE",
        "LICENSE",
        "VERSION",
    ]
    members = []
    for rel in member_relpaths:
        p = root / rel
        if p.is_file():
            members.append(
                {"path": rel, "sha256": sha256_file(p),
                 "bytes": p.stat().st_size}
            )
        else:
            members.append({"path": rel, "sha256": None,
                            "bytes": None, "note": "absent on disk"})
    members.sort(key=lambda m: m["path"])

    rollback: dict = {"type": "git-commit", "commit": head,
                      "prior_version": None, "note": head_note}
    version_path = root / "VERSION"
    if version_path.is_file():
        rollback["prior_version"] = version_path.read_text(
            encoding="utf-8", errors="replace").strip()

    manifest = {
        "schemaVersion": CANDIDATE_SCHEMA_VERSION,
        "schema": "schemas/release-candidate.json",
        "created_at": utc_now(),
        "builder": {
            "script": "scripts/build-release-candidate.py",
            "python": platform.python_version(),
        },
        "repository": {"integration_commit": head,
                       "integration_commit_note": head_note},
        "distribution": "local-only",
        "distribution_note": (
            "digest-only local-only (17.15): no verifiable signature; "
            "CVE scan unimplemented (offline). See docs/RELEASE-ARTIFACT.md."
        ),
        "registry_digest": "sha256:" + registry_digest,
        "registry_counts": {
            "sources": len(registry.get("sources", [])),
            "skills": len(registry.get("skills", [])),
            "excluded": len(registry.get("excluded", [])),
        },
        "source_lock_digest": (
            "sha256:" + sha256_file(lock_path)
            if lock is not None else None
        ),
        "source_lock_schema": (lock.get("schemaVersion") if lock else None),
        "notice_present": notice_path.is_file(),
        "members": members,
        "gate_pins": gate_pins,
        "rollback_target": rollback,
        "requester": args.requester,
    }

    components = build_components(registry)
    sbom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "version": 1,
        "metadata": {
            "timestamp": manifest["created_at"],
            "tools": [{"name": "scripts/build-release-candidate.py",
                       "version": CANDIDATE_SCHEMA_VERSION}],
            "properties": [
                {"name": "t16:distribution", "value": "local-only"},
                {"name": "t16:cve-scan",
                 "value": "unimplemented (offline; no network)"},
                {"name": "t16:signature",
                 "value": "absent (unsigned; see T21 record)"},
            ],
        },
        "components": components,
        "vulnerabilities": [],
        "vulnerabilities_note": (
            "No CVE scan record exists: scanning needs network access, which "
            "is forbidden in this environment. The empty list means "
            "'not scanned', never 'no CVEs'. See DEVIATIONS."
        ),
    }

    out.mkdir(parents=True, exist_ok=True)
    # content_id: the timestamp-independent identity the approval binds to.
    # Two builds of the same tree (different wall clocks / interpreters)
    # produce the same content_id, so an approver can review one build and
    # the gate can re-verify a rebuild. Byte-level tamper is still caught
    # by checksums.sha256 over the files (see cmd_check).
    content_canonical = json.dumps(
        {
            "schema": manifest["schemaVersion"],
            "distribution": manifest["distribution"],
            "registry_digest": manifest["registry_digest"],
            "registry_counts": manifest["registry_counts"],
            "members": [
                {"path": m["path"], "sha256": m["sha256"]}
                for m in members
            ],
            "gate_pins": gate_pins,
            "source_lock_digest": manifest["source_lock_digest"],
            "rollback_commit": rollback["commit"],
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    manifest["content_id"] = "sha256:" + hashlib.sha256(
        content_canonical.encode("ascii")).hexdigest()
    manifest_path = out / "candidate-manifest.json"
    sbom_path = out / "sbom.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    sbom_path.write_text(
        json.dumps(sbom, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    lines = []
    for name in ("candidate-manifest.json", "sbom.json"):
        lines.append(
            f"{sha256_file(out / name)}  {name}"
        )
    (out / "checksums.sha256").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )

    manifest_digest = sha256_file(manifest_path)
    print(f"candidate_dir={out}")
    print(f"content_id={manifest['content_id']}")
    print(f"manifest_digest=sha256:{manifest_digest}")
    print(f"registry_digest=sha256:{registry_digest}")
    print(f"sources={manifest['registry_counts']['sources']} "
          f"skills={manifest['registry_counts']['skills']} "
          f"components={len(components)}")
    print("distribution=local-only (only emittable value; "
          "redistributable is refused with exit 20)")
    if head_note is not None:
        print(f"NEEDS_REVIEW rollback commit: {head_note}")
        return EXIT_NEEDS_REVIEW
    print(f"CANDIDATE BUILT (mode=local-only) rollback={head}")
    return EXIT_OK

def cmd_check(args: argparse.Namespace) -> int:
    candidate = Path(args.candidate_dir).resolve()
    manifest_path = candidate / "candidate-manifest.json"
    if not manifest_path.is_file():
        print("FAIL candidate-manifest.json is missing", file=sys.stderr)
        return EXIT_BLOCKED
    manifest = load_json(manifest_path)
    problems: list[str] = []

    # 1. checksums file must match both payload files byte for byte.
    sums_path = candidate / "checksums.sha256"
    if not sums_path.is_file():
        problems.append("checksums.sha256 is missing")
    else:
        recorded: dict[str, str] = {}
        for line in sums_path.read_text(encoding="utf-8").splitlines():
            parts = line.split()
            if len(parts) == 2:
                recorded[parts[1]] = parts[0]
        for name in ("candidate-manifest.json", "sbom.json"):
            p = candidate / name
            if not p.is_file():
                problems.append(f"{name} is missing from the candidate dir")
                continue
            actual = sha256_file(p)
            if recorded.get(name) != actual:
                problems.append(
                    f"{name}: checksum mismatch (recorded="
                    f"{recorded.get(name)} actual={actual})"
                )

    # 2. members must still hash to the manifest values (one-byte tamper).
    root = Path(args.root).resolve()
    for member in manifest.get("members", []):
        rel = member.get("path", "")
        p = root / rel
        want = member.get("sha256")
        if want is None or not p.is_file():
            continue
        actual = sha256_file(p)
        if actual != want:
            problems.append(
                f"member {rel}: manifest={want} actual={actual}"
            )

    # 3. registry digest must still match (registry edited after build).
    reg_digest = manifest.get("registry_digest", "")
    reg_path = root / "skills/community/registry.json"
    if reg_path.is_file():
        actual_reg = "sha256:" + sha256_file(reg_path)
        if actual_reg != reg_digest:
            problems.append(
                f"registry drift: manifest={reg_digest} actual={actual_reg}"
            )

    # 4. a redistributable manifest without signature proof is refused.
    if manifest.get("distribution") == "redistributable":
        problems.append(
            "distribution=redistributable without verifiable signature "
            "proof (17.15 refusal)"
        )

    if problems:
        for problem in problems[:20]:
            print(f"FAIL {problem}", file=sys.stderr)
        if len(problems) > 20:
            print(f"FAIL ... {len(problems) - 20} more", file=sys.stderr)
        return EXIT_BLOCKED
    print(f"CANDIDATE CHECK PASSED dir={candidate} "
          f"members={len(manifest.get('members', []))}")
    return EXIT_OK

def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="build-release-candidate.py",
        description="Build or re-verify a local-only release candidate "
                    "(spec T16). Unknown arguments are an error.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build", help="assemble a candidate directory")
    build.add_argument("--out-dir", required=True,
                       help="candidate output directory (must be outside "
                            "the repository tree)")
    build.add_argument("--root", default=str(DEFAULT_ROOT),
                       help="repository root to read (default: checkout)")
    build.add_argument("--distribution", default="local-only",
                       help="only 'local-only' is emittable; anything else "
                            "is refused with exit 20")
    build.add_argument("--requester", default=None,
                       help="handle of the human requesting the release "
                            "(recorded; must differ from the approver)")
    build.add_argument("--allow-in-tree", action="store_true",
                       help="lab-fixture escape hatch for in-tree output; "
                            "never used for a real candidate")

    check = sub.add_parser("check", help="re-verify a candidate directory")
    check.add_argument("--candidate-dir", required=True)
    check.add_argument("--root", default=str(DEFAULT_ROOT))
    return parser.parse_args(argv)

def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.command == "build":
        return cmd_build(args)
    return cmd_check(args)

if __name__ == "__main__":
    raise SystemExit(main())
