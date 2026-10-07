#!/usr/bin/env python3
"""Human release-approval gate (spec T16, 17.15 / 17.21 / 17.29).

A candidate built by scripts/build-release-candidate.py becomes releasable
(local-only) only when ALL of these hold:

  1. the candidate directory is intact (checksums + member digests recompute;
     a one-byte tamper exits 20);
  2. a machine-readable approval record exists, is schema-conformant and says
     decision=approved for THIS candidate content_id (missing/foreign/stale
     approval exits 20 -- unapproved can never publish);
  3. requester != approver (self-approval exits 20);
  4. the gate scripts pinned in the approval still hash to their pinned
     digests (a PR that edits a gate after the approval was cut exits 20 --
     the self-serving-gate path is infeasible);
  5. distribution=redistributable additionally requires a verifiable
     signature record (signer + trust root + key id + timestamp + rotation +
     revocation). None exists today (T21: unsigned), so that claim exits 20;
  6. the rollback target commit resolves in git where .git is present
     (unresolvable exits 20; no .git exits 10 with the item named).

Exit codes follow the frozen spec 4.7 table:
  0 approved-and-valid (local-only only, today) | 10 needs_review |
  20 blocked | 2 usage (argparse).

Read-only: this script never writes to the repository or the candidate dir,
and it never executes vendored content.

Approval records are NOT committed to the repository: they live with the
release process (tag / environment) and are passed via --approval. The
release workflow fails closed when the record is absent.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve()
DEFAULT_ROOT = SCRIPT.parents[1]

APPROVAL_SCHEMA_VERSION = "1.0"

EXIT_OK = 0
EXIT_NEEDS_REVIEW = 10
EXIT_BLOCKED = 20
EXIT_USAGE = 2

REQUIRED_APPROVAL_FIELDS = (
    "schemaVersion",
    "content_id",
    "decision",
    "requester",
    "approver",
    "approved_at",
    "distribution",
    "rollback_target",
    "gate_pins",
)

def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def recompute_content_id(manifest: dict) -> str | None:
    """Recompute the timestamp-independent content id from manifest fields.

    Returns None when the manifest lacks the fields (then the byte-level
    checksum path is the only integrity evidence, and the approval cannot
    match).
    """
    try:
        members = manifest["members"]
        gate_pins = manifest["gate_pins"]
        canonical = json.dumps(
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
                "source_lock_digest": manifest.get("source_lock_digest"),
                "rollback_commit": manifest.get("rollback_target", {}).get(
                    "commit"),
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
    except (KeyError, TypeError):
        return None
    return "sha256:" + hashlib.sha256(canonical.encode("ascii")).hexdigest()

def load_json(path: Path, label: str) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"FAIL {label} unreadable: {path}: {exc}", file=sys.stderr)
        raise SystemExit(EXIT_BLOCKED)
    if not isinstance(data, dict):
        print(f"FAIL {label} is not a JSON object: {path}", file=sys.stderr)
        raise SystemExit(EXIT_BLOCKED)
    return data

def git_resolves(root: Path, commit: str | None) -> tuple[str, str | None]:
    """Check a rollback commit resolves. Returns (state, note)."""
    if not commit:
        return "missing", "rollback_target.commit is empty"
    if not (root / ".git").exists():
        return "unknown", f"no .git: cannot machine-check {commit[:12]}"
    try:
        out = subprocess.run(
            ["git", "cat-file", "-e", commit],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return "error", f"git probe failed: {exc}"
    if out.returncode != 0:
        return "missing", f"rollback commit does not resolve: {commit[:12]}"
    return "ok", None

def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="verify-release-approval.py",
        description="Human release-approval gate (spec T16). Unapproved, "
                    "tampered, self-approved or gate-drifted releases exit "
                    "20. An unknown argument is an error.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--candidate-dir", required=True,
                        help="candidate directory built by "
                             "build-release-candidate.py")
    parser.add_argument("--approval", default=None,
                        help="approval record JSON (absent = unapproved)")
    parser.add_argument("--root", default=str(DEFAULT_ROOT),
                        help="repository root the candidate was built from")
    parser.add_argument("--json", action="store_true", dest="as_json",
                        help="emit the verdict report as JSON on stdout")
    return parser.parse_args(argv)

def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    root = Path(args.root).resolve()
    candidate = Path(args.candidate_dir).resolve()

    blocked: list[str] = []
    review: list[str] = []

    # --- 1. candidate integrity (same checks as build check) ---
    manifest_path = candidate / "candidate-manifest.json"
    if not manifest_path.is_file():
        blocked.append("candidate-manifest.json is missing")
        manifest: dict = {}
    else:
        manifest = load_json(manifest_path, "candidate manifest")
        sums_path = candidate / "checksums.sha256"
        if not sums_path.is_file():
            blocked.append("checksums.sha256 is missing")
        else:
            recorded: dict[str, str] = {}
            for line in sums_path.read_text(encoding="utf-8").splitlines():
                parts = line.split()
                if len(parts) == 2:
                    recorded[parts[1]] = parts[0]
            for name in ("candidate-manifest.json", "sbom.json"):
                p = candidate / name
                if not p.is_file():
                    blocked.append(f"{name} is missing from candidate dir")
                elif recorded.get(name) != sha256_file(p):
                    blocked.append(
                        f"{name}: checksum mismatch "
                        f"(recorded={recorded.get(name)} "
                        f"actual={sha256_file(p)})"
                    )
        for member in manifest.get("members", []):
            rel = member.get("path", "")
            want = member.get("sha256")
            p = root / rel
            if want is None or not p.is_file():
                continue
            if sha256_file(p) != want:
                blocked.append(f"member {rel}: digest mismatch (tampered)")
        reg_path = root / "skills/community/registry.json"
        if reg_path.is_file() and manifest.get("registry_digest"):
            actual_reg = "sha256:" + sha256_file(reg_path)
            if actual_reg != manifest["registry_digest"]:
                blocked.append(
                    f"registry drift: manifest={manifest['registry_digest']} "
                    f"actual={actual_reg}"
                )

    manifest_digest = (
        "sha256:" + sha256_file(manifest_path)
        if manifest_path.is_file() else "missing"
    )

    # --- 2/3. approval record: present, conformant, approved, non-self ---
    if not args.approval:
        blocked.append(
            "no approval record was supplied (--approval absent): "
            "unapproved releases cannot publish"
        )
        approval: dict = {}
    else:
        approval_path = Path(args.approval)
        if not approval_path.is_file():
            blocked.append(f"approval record does not exist: {approval_path}")
            approval = {}
        else:
            approval = load_json(approval_path, "approval record")
            for field in REQUIRED_APPROVAL_FIELDS:
                if field not in approval:
                    blocked.append(
                        f"approval record is missing field {field!r}")
            if approval.get("schemaVersion") != APPROVAL_SCHEMA_VERSION:
                blocked.append(
                    "approval schemaVersion="
                    f"{approval.get('schemaVersion')!r} is not "
                    f"{APPROVAL_SCHEMA_VERSION!r}")
            if approval.get("decision") != "approved":
                blocked.append(
                    "approval decision="
                    f"{approval.get('decision')!r} is not 'approved'")
            content_id = recompute_content_id(manifest)
            if content_id is None:
                blocked.append(
                    "candidate manifest lacks the fields needed to "
                    "recompute its content_id")
            else:
                if manifest.get("content_id") != content_id:
                    blocked.append(
                        "candidate manifest content_id does not recompute "
                        f"(stored={manifest.get('content_id')} "
                        f"recomputed={content_id}): manifest edited after "
                        "build")
                if approval.get("content_id") != content_id:
                    blocked.append(
                        "approval content_id does not match this candidate "
                        f"(approval={approval.get('content_id')} "
                        f"candidate={content_id}): stale or foreign approval")
            requester = approval.get("requester")
            approver = approval.get("approver")
            if not requester or not approver:
                blocked.append(
                    "approval must name both requester and approver")
            elif requester == approver:
                blocked.append(
                    f"self-approval is forbidden (requester == approver == "
                    f"{requester!r}): a second human must approve")

    # --- 4. gate pins: the approval must pin the gates, and they must match.
    if approval and isinstance(approval.get("gate_pins"), dict):
        for rel, want in approval["gate_pins"].items():
            p = root / rel
            actual = ("sha256:" + sha256_file(p)) if p.is_file() else "absent"
            if actual != want:
                blocked.append(
                    f"gate drift: {rel} changed after approval "
                    f"(pinned={str(want)[:19]} actual={actual[:19]}): "
                    "a PR that edits a gate cannot ride on this approval")
    elif args.approval:
        blocked.append("approval carries no gate_pins: cannot rule out "
                       "gate self-modification")

    # --- 5. signature: redistributable without proof is refused. ---
    distribution = (approval.get("distribution")
                    or manifest.get("distribution") or "local-only")
    if distribution == "redistributable":
        blocked.append(
            "distribution=redistributable requires a verifiable signature "
            "(signer + trust root + key id + timestamp + rotation + "
            "revocation); this repository records signature.present=false "
            "(T21 unsigned). Refused per 17.15.")

    # --- 6. rollback target must resolve (where checkable). ---
    rollback = approval.get("rollback_target") or manifest.get(
        "rollback_target", {})
    state, note = git_resolves(root, rollback.get("commit"))
    if state == "missing" or state == "error":
        blocked.append(f"rollback target unverifiable: {note}")
    elif state == "unknown":
        review.append(f"rollback target: {note}")

    report = {
        "content_id": manifest.get("content_id"),
        "manifest_digest": manifest_digest,
        "distribution": manifest.get("distribution"),
        "decision": approval.get("decision") if approval else None,
        "requester": approval.get("requester") if approval else None,
        "approver": approval.get("approver") if approval else None,
        "rollback_state": state,
        "rollback_note": note,
        "blocked": blocked,
        "needs_review": review,
    }
    if args.as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2,
                         sort_keys=True))
    else:
        print(f"content={str(manifest.get('content_id'))[:19]} "
              f"distribution={manifest.get('distribution')}")
        print(f"decision={report['decision']} "
              f"requester={report['requester']} approver={report['approver']}")
        print(f"rollback={state}: {note}")
        for item in blocked:
            print(f"FAIL {item}")
        for item in review:
            print(f"REVIEW {item}")

    if blocked:
        if not args.as_json:
            print(f"BLOCKED release approval gate: {len(blocked)} "
                  "blocking item(s) (spec 4.7 exit 20)")
        return EXIT_BLOCKED
    if review:
        if not args.as_json:
            print(f"NEEDS_REVIEW release approval gate: {len(review)} "
                  "open item(s) (spec 4.7 exit 10)")
        return EXIT_NEEDS_REVIEW
    if not args.as_json:
        print("RELEASE APPROVED (local-only): candidate intact, approval "
              "valid, gates pinned, rollback resolves")
    return EXIT_OK

if __name__ == "__main__":
    raise SystemExit(main())
