#!/usr/bin/env python3
"""Verify the canonical base lock (T21, spec 17.15 / 17.28 / 17.29).

Checks the single source_kind=canonical-base record (id `reverse-skill`) in
skills/community/registry.json against the read-only snapshot and the fusion
repo itself. Also enforces the 17.15 signature rule: a candidate without a
verifiable signature cannot enter a redistributable release.

  default mode            base lock verification (record, commits, snapshot,
                          digests, snapshot cleanliness).
  --require-signatures    additionally assert promotion readiness: the base
                          record must carry a verifiable signature. With no
                          signature implemented this exits 20 on the real
                          tree; that refusal IS the acceptance evidence.
  --root DIR              run the same gate against a fixture tree (negative
                          controls). Snapshot candidates resolve as
                          <root>/<snapshot_root>, else <root>/../<snapshot_root>.
  --json                  one machine-readable report document on stdout.

Exit codes (spec 4.7): 0 ok, 10 needs_review (snapshot absent: digest, HEAD
and dirty claims are named, never silently passed -- same degraded semantics
as verify-source-attestation.py), 20 blocked, 2 usage.
Read-only: never writes, never executes vendored content, never runs the
importer. Git is only used read-only (rev-parse / status --porcelain /
cat-file -e / config --get).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve()
DEFAULT_ROOT = HERE.parents[1]
REGISTRY_REL = Path("skills/community/registry.json")

BASE_ID = "reverse-skill"
BASE_KIND = "canonical-base"
DIGEST_CONTRACT = "skills-hub/importer-digest/1"

EXIT_OK = 0
EXIT_NEEDS_REVIEW = 10
EXIT_BLOCKED = 20
EXIT_USAGE = 2

HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
RFC3339 = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

REQUIRED_RECORD_FIELDS = (
    "id", "source_kind", "source_url", "commit", "tree_digest",
    "source_manifest", "snapshot_root", "source_root", "license_declared",
    "license_status", "third_party_review", "notice_file", "maturity",
    "distribution", "adaptation_status", "importer_version",
    "last_verified_at", "baseline_commit", "integration_commit", "signature",
)

def nfc(path: str) -> str:
    return unicodedata.normalize("NFC", path)

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def canonical_bytes(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")

def collect_files(root: Path) -> tuple[list[tuple[str, bytes]], list[str]]:
    out: list[tuple[str, bytes]] = []
    symlinks: list[str] = []
    for path in root.rglob("*"):
        if path.is_symlink():
            symlinks.append(nfc(path.relative_to(root).as_posix()))
            continue
        if not path.is_file():
            continue
        out.append((nfc(path.relative_to(root).as_posix()), path.read_bytes()))
    out.sort(key=lambda item: item[0].encode("utf-8"))
    return out, symlinks

def digest_of(pairs: list[tuple[str, bytes]]) -> dict[str, object]:
    file_lines = sorted(
        b"f\0" + rel.encode("utf-8") + b"\0"
        + sha256_bytes(canonical_bytes(data)).encode("ascii") + b"\n"
        for rel, data in pairs
    )
    dirs: set[str] = set()
    for rel, _ in pairs:
        parts = rel.split("/")
        for i in range(1, len(parts)):
            dirs.add("/".join(parts[:i]))
    dir_lines = sorted(b"d\0" + d.encode("utf-8") + b"\0\n" for d in dirs)
    return {
        "file_count": len(pairs),
        "dir_count": len(dirs),
        "file_manifest_digest": sha256_bytes(b"".join(file_lines)),
        "tree_digest": sha256_bytes(b"".join(sorted(file_lines + dir_lines))),
    }

def git(repo: Path, *args: str) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True, text=True, timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return 127, ""
    return proc.returncode, (proc.stdout or "").strip()

def check(root: Path, require_signatures: bool) -> tuple[list[str], list[str], dict]:
    blocked: list[str] = []
    review: list[str] = []
    info: dict[str, object] = {"root": root.as_posix()}

    registry_path = root / REGISTRY_REL
    if not registry_path.is_file():
        return ["community registry is missing"], [], info
    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [f"community registry is unreadable: {exc}"], [], info

    sources = registry.get("sources", [])
    base = next((s for s in sources if s.get("id") == BASE_ID), None)
    if base is None:
        blocked.append(
            "canonical base record is missing: no sources[] entry with id "
            f"{BASE_ID!r} (17.15: registry without the base record is incomplete)"
        )
        info["base_present"] = False
    elif base.get("source_kind") != BASE_KIND:
        blocked.append(
            f"canonical base record has wrong source_kind: {base.get('source_kind')!r}"
        )
        info["base_present"] = False
    else:
        info["base_present"] = True
        for field in REQUIRED_RECORD_FIELDS:
            if field not in base:
                blocked.append(f"canonical base record: missing required field {field}")
        top_baseline = (registry.get("baseline") or {}).get("commit", "")
        commit = base.get("commit", "")
        if not HEX40.match(str(commit)):
            blocked.append(f"canonical base record: commit is not 40-hex: {commit!r}")
        if commit != top_baseline:
            blocked.append(
                "canonical base record: commit "
                f"{commit!r} != registry baseline.commit {top_baseline!r}"
            )
        if base.get("baseline_commit") != commit:
            blocked.append(
                "canonical base record: baseline_commit "
                f"{base.get('baseline_commit')!r} != commit {commit!r}"
            )
        integration = base.get("integration_commit", "")
        if not HEX40.match(str(integration)):
            blocked.append(
                "canonical base record: integration_commit is not 40-hex: "
                f"{integration!r}"
            )
        digest = base.get("tree_digest", "")
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", str(digest)):
            blocked.append(
                "canonical base record: tree_digest is not sha256:<64hex>: "
                f"{digest!r}"
            )
        manifest = base.get("source_manifest") or ""
        if manifest and not (root / str(manifest).split("#")[0]).is_file():
            blocked.append(
                "canonical base record: source_manifest pointer does not exist: "
                f"{manifest!r}"
            )
        if base.get("distribution") not in ("local-only", "redistributable"):
            blocked.append(
                "canonical base record: distribution outside the 4.2 enum: "
                f"{base.get('distribution')!r}"
            )
        if base.get("last_verified_at") is not None and not RFC3339.match(
            str(base.get("last_verified_at"))
        ):
            blocked.append("canonical base record: last_verified_at is not UTC RFC 3339")
        info["baseline_commit"] = commit
        info["integration_commit"] = integration
        info["tree_digest"] = digest

        # 17.15 signature rule, enforced in every mode: a redistributable
        # claim without a verifiable signature is refused, never warned past.
        sig = base.get("signature") or {}
        if base.get("distribution") == "redistributable" and not (
            sig.get("present") is True and sig.get("status") == "signed-verified"
            and sig.get("signer") and sig.get("trust_root") and sig.get("key_id")
            and sig.get("signed_at")
        ):
            blocked.append(
                "redistributable claim without a verifiable signature is refused: "
                f"{BASE_ID} (17.15: signature.present={sig.get('present')!r}, "
                f"status={sig.get('status')!r})"
            )
        if require_signatures and not (
            sig.get("present") is True and sig.get("status") == "signed-verified"
            and sig.get("signer") and sig.get("trust_root") and sig.get("key_id")
            and sig.get("signed_at")
        ):
            blocked.append(
                "promotion readiness refused: canonical base record is unsigned "
                f"(signature.present={sig.get('present')!r}, "
                f"status={sig.get('status')!r}); digest-only content stays "
                "local-only (17.15)"
            )
        info["signature_present"] = sig.get("present")
        info["signature_status"] = sig.get("status")

        # Every redistributable source needs the same verifiable signature.
        for source in sources:
            if source.get("id") == BASE_ID:
                continue
            if source.get("distribution") != "redistributable":
                continue
            s = source.get("signature") or {}
            if not (
                s.get("present") is True and s.get("status") == "signed-verified"
                and s.get("signer") and s.get("trust_root") and s.get("key_id")
            ):
                blocked.append(
                    "redistributable claim without a verifiable signature is "
                    f"refused: {source.get('id')} (17.15)"
                )

    # Live snapshot checks (only meaningful when the base record exists).
    if info.get("base_present"):
        candidates = [root / str(base.get("snapshot_root", ""))]
        parent_candidate = root.parent / str(base.get("snapshot_root", ""))
        if parent_candidate not in candidates:
            candidates.append(parent_candidate)
        snapshot = next((c for c in candidates if c.is_dir()), None)
        if snapshot is None:
            review.append(
                "snapshot absent: "
                + ", ".join(c.as_posix() for c in candidates)
                + " -- digest, HEAD, resolvability and dirty cannot be "
                "machine-checked here (17.28 degraded semantics)"
            )
            info["snapshot"] = None
        else:
            info["snapshot"] = snapshot.as_posix()
            if not (snapshot / ".git").is_dir() and not (snapshot / ".git").is_file():
                review.append(
                    f"snapshot has no .git: {snapshot.as_posix()} -- HEAD, "
                    "resolvability and dirty cannot be machine-checked here"
                )
            else:
                code, head = git(snapshot, "rev-parse", "HEAD")
                if code != 0 or not HEX40.match(head):
                    blocked.append(f"snapshot HEAD is unresolvable: {snapshot.as_posix()}")
                elif head != base.get("commit"):
                    blocked.append(
                        f"snapshot HEAD {head} != base commit {base.get('commit')} "
                        "(snapshot drift or tamper)"
                    )
                info["snapshot_head"] = head if code == 0 else None
                code, _ = git(snapshot, "cat-file", "-e", f"{base.get('commit')}^{{commit}}")
                if code != 0:
                    blocked.append(
                        f"base commit does not resolve in the snapshot: {base.get('commit')}"
                    )
                code, porcelain = git(snapshot, "status", "--porcelain")
                if code != 0:
                    blocked.append("snapshot dirty state cannot be established (git failed)")
                elif porcelain:
                    blocked.append(
                        f"dirty snapshot cannot enter a candidate: {snapshot.as_posix()} "
                        f"({len(porcelain.splitlines())} dirty path(s), 17.28)"
                    )
                info["snapshot_dirty"] = bool(porcelain) if code == 0 else None
            if snapshot is not None:
                pairs, symlinks = collect_files(snapshot)
                recomputed = digest_of(pairs)
                recorded = str(base.get("tree_digest", "")).removeprefix("sha256:")
                if recomputed["tree_digest"] != recorded:
                    blocked.append(
                        "base tree_digest mismatch: registry="
                        f"{recorded[:16]}... recomputed="
                        f"{recomputed['tree_digest'][:16]}... "
                        f"({recomputed['file_count']} files, "
                        f"{recomputed['dir_count']} dirs, contract {DIGEST_CONTRACT})"
                    )
                info["recomputed"] = {
                    "file_count": recomputed["file_count"],
                    "dir_count": recomputed["dir_count"],
                    "symlinks": len(symlinks),
                    "tree_digest": "sha256:" + str(recomputed["tree_digest"]),
                    "file_manifest_digest": "sha256:" + str(recomputed["file_manifest_digest"]),
                }

        # The integration commit must resolve where the fusion .git is present.
        if HEX40.match(str(info.get("integration_commit") or "")):
            if (root / ".git").is_dir():
                code, _ = git(
                    root, "cat-file", "-e",
                    f"{info['integration_commit']}^{{commit}}",
                )
                if code != 0:
                    blocked.append(
                        "integration_commit does not resolve in this checkout: "
                        f"{info['integration_commit']}"
                    )
            else:
                review.append(
                    "no .git in this copy: integration_commit resolvability "
                    "cannot be machine-checked here"
                )

    return blocked, review, info

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="verify-canonical-base-lock.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--root", default=str(DEFAULT_ROOT))
    parser.add_argument(
        "--require-signatures", action="store_true",
        help="assert promotion readiness: refuse when the base record has no "
             "verifiable signature (exit 20 on the current unsigned tree).",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    root = Path(args.root)
    blocked, review, info = check(root, args.require_signatures)
    report = {
        "mode": "promotion-readiness" if args.require_signatures else "base-lock",
        "blocked": blocked,
        "needs_review": review,
        "info": info,
    }
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        out = lambda text: print(text, file=sys.stderr)  # noqa: E731
    else:
        out = print
        out("=== canonical base lock (T21) ===")
        out(f"root                        : {root.as_posix()}")
        out(f"base_present                : {info.get('base_present')}")
        if info.get("recomputed"):
            rec = info["recomputed"]
            out(
                f"snapshot                    : {info.get('snapshot')} "
                f"files={rec['file_count']} dirs={rec['dir_count']} "
                f"symlinks={rec['symlinks']}"
            )
            out(f"tree_digest                 : {rec['tree_digest']}")
        for item in blocked:
            out(f"[BLOCKED] {item}")
        for item in review:
            out(f"[REVIEW] {item}")

    if blocked:
        out(f"FAIL verify-canonical-base-lock: {len(blocked)} blocking finding(s)")
        return EXIT_BLOCKED
    if review:
        out(f"NEEDS_REVIEW verify-canonical-base-lock: {len(review)} item(s)")
        return EXIT_NEEDS_REVIEW
    out("PASS verify-canonical-base-lock")
    return EXIT_OK

if __name__ == "__main__":
    raise SystemExit(main())
