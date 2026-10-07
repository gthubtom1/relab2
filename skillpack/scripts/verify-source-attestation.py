#!/usr/bin/env python3
"""Verify community source attestations offline (T12+T14, spec 17.28).

Reads `skills/community/source-lock.json` and checks every source:

  static (always checked, snapshot or not)
    - all ten 17.28 fields present (`default_branch_commit` may be null, but
      the key must exist with an explicit note -- recording the gap, not
      inventing a value);
    - `resolved_commit` is 40 lowercase hex and equals the pinned commit;
    - `dirty` is false (a dirty source is investigation material, 17.28);
    - both digests are 64 lowercase hex; counts are non-negative ints;
    - `attestation_method` is one of git-commit | tarball-digest |
      api-tree-digest; `fetched_at` is UTC RFC 3339.

  live (only when the read-only snapshot is present)
    - snapshot directory exists; HEAD equals `resolved_commit`;
    - `git cat-file -e <commit>^{commit}` resolves (the commit is real, not a
      copied string); worktree is clean;
    - recomputed `tree_digest` / `file_manifest_digest` (frozen contract
      `skills-hub/importer-digest/1`) match the lock.

When the snapshot is absent -- a clean clone, or the T12 lab copy sitting
where no `../upstream` exists -- the live claims cannot be machine-checked.
That is reported as NEEDS_REVIEW naming exactly which claim and why
(HANDOFF 2.1: the lock digest still verifies, only "does the claimed
upstream path really exist" cannot be checked). It is never silently passed.

Case/Unicode conflicts (17.30, T14): every scanned tree (snapshot scan root
when present, otherwise `community-raw/<dest>` in this repo) is checked for
two distinct relative paths that collide after NFC + casefold. A collision
is BLOCKED. Symlinks are reported (17.26 records them as type=symlink with
the link target; they contribute no bytes).

Exit codes (spec 4.7): 0 ok, 10 needs_review, 20 blocked.
Read-only: this script never writes to the repository.

Usage:
    python scripts/verify-source-attestation.py [--root DIR]
        [--snapshot-root DIR] [--lock REL] [--json]
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

DIGEST_CONTRACT_VERSION = "skills-hub/importer-digest/1"
LOCK_SCHEMA_VERSION = "1.0"

# Read-only reference to the importer layout (scripts/adapt-community.py
# DEST). Duplicated here so this verifier keeps working even while card A
# rewrites the importer; the fallback tree is the verified community-raw/.
RAW_DEST = {
    "ctf-super-hub": "ctf-super-hub",
    "hack-skills": "hack-skills",
    "ai-fullstack-delivery": "ai-fullstack/workflows",
    "apk-reverse-community": "apk-reverse-source",
}

ATTESTATION_FIELDS = (
    "upstream_url",
    "resolved_commit",
    "default_branch_commit",
    "origin_head_commit",
    "dirty",
    "tree_digest",
    "file_manifest_digest",
    "fetched_at",
    "fetch_tool_and_version",
    "attestation_method",
)
ATTESTATION_METHODS = {"git-commit", "tarball-digest", "api-tree-digest"}

HEX40 = re.compile(r"[0-9a-f]{40}")
HEX64 = re.compile(r"[0-9a-f]{64}")
RFC3339 = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")

def nfc(path: str) -> str:
    return unicodedata.normalize("NFC", path)

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def canonical_bytes(data: bytes) -> bytes:
    """Fold CRLF to LF. A lone CR is preserved (frozen contract)."""
    return data.replace(b"\r\n", b"\n")

def collect_files(root: Path) -> tuple[list[tuple[str, bytes]], list[str]]:
    """(posix-relative path, bytes) for every file, plus symlink records."""
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

def file_line(rel: str, data: bytes) -> bytes:
    return b"f\0" + rel.encode("utf-8") + b"\0" + sha256_bytes(canonical_bytes(data)).encode("ascii") + b"\n"

def dir_line(rel: str) -> bytes:
    return b"d\0" + rel.encode("utf-8") + b"\0\n"

def ancestors(rel: str) -> list[str]:
    parts = rel.split("/")
    return ["/".join(parts[:i]) for i in range(1, len(parts))]

def digest_of(pairs: list[tuple[str, bytes]]) -> dict:
    file_lines = sorted((file_line(rel, data) for rel, data in pairs), key=lambda b: b)
    dirs: set[str] = set()
    for rel, _ in pairs:
        dirs.update(ancestors(rel))
    dir_lines = sorted((dir_line(d) for d in dirs), key=lambda b: b)
    return {
        "file_count": len(pairs),
        "dir_count": len(dirs),
        "file_manifest_digest": sha256_bytes(b"".join(file_lines)),
        "tree_digest": sha256_bytes(b"".join(sorted(file_lines + dir_lines))),
    }

def run_git(repo: Path, *args: str) -> tuple[int, str, str]:
    proc = subprocess.run(
        ["git", "--no-optional-locks", "-C", str(repo), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()

def case_key(rel: str) -> str:
    return nfc(rel).casefold()

def find_collisions(root: Path) -> list[str]:
    """Distinct paths colliding after NFC + casefold (17.30)."""
    seen: dict[str, str] = {}
    collisions: list[str] = []
    for path in root.rglob("*"):
        try:
            rel = path.relative_to(root).as_posix()
        except ValueError:
            continue
        key = case_key(rel)
        if key in seen and seen[key] != rel:
            collisions.append(f"{seen[key]!r} collides with {rel!r}")
        else:
            seen.setdefault(key, rel)
    return collisions

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(DEFAULT_ROOT))
    parser.add_argument("--snapshot-root", default=None,
                        help="override for <root>/../upstream (lab use)")
    parser.add_argument("--lock", default="skills/community/source-lock.json")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    root = Path(args.root)
    lock_path = root / args.lock
    snap_root = Path(args.snapshot_root) if args.snapshot_root else root.parent / "upstream"

    problems: list[str] = []
    warnings: list[str] = []
    checked_live = 0

    if not lock_path.is_file():
        print(f"FAIL source lock missing: {lock_path}")
        return 20
    try:
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"FAIL source lock is not readable JSON: {exc}")
        return 20

    if lock.get("schemaVersion") != LOCK_SCHEMA_VERSION:
        problems.append(
            f"lock schemaVersion {lock.get('schemaVersion')!r} != {LOCK_SCHEMA_VERSION!r} (old schema)")
    if lock.get("digest_contract") != DIGEST_CONTRACT_VERSION:
        problems.append(
            f"lock digest_contract {lock.get('digest_contract')!r} != {DIGEST_CONTRACT_VERSION!r}")

    sources = lock.get("sources", [])
    if not isinstance(sources, list) or not sources:
        problems.append("lock has no sources[] to verify")

    for src in sources:
        sid = src.get("id", "<unknown>")
        for field in ATTESTATION_FIELDS:
            if field not in src:
                problems.append(f"{sid}: attestation missing field: {field}")
        commit = src.get("resolved_commit")
        if not isinstance(commit, str) or not HEX40.fullmatch(commit):
            problems.append(f"{sid}: resolved_commit must be 40 lowercase hex (17.28)")
        if src.get("pinned_commit") and commit != src.get("pinned_commit"):
            problems.append(f"{sid}: resolved_commit {commit} != pinned commit {src.get('pinned_commit')}")
        if src.get("dirty") is not False:
            problems.append(f"{sid}: attestation dirty must be false (17.28)")
        for field in ("tree_digest", "file_manifest_digest"):
            value = src.get(field)
            if not isinstance(value, str) or not HEX64.fullmatch(value):
                problems.append(f"{sid}: {field} must be sha256 lowercase hex (17.26)")
        if src.get("attestation_method") not in ATTESTATION_METHODS:
            problems.append(f"{sid}: attestation_method must be one of {sorted(ATTESTATION_METHODS)}")
        if not RFC3339.fullmatch(str(src.get("fetched_at", ""))):
            problems.append(f"{sid}: fetched_at must be UTC RFC 3339")
        for field in ("file_count", "dir_count"):
            value = src.get(field)
            if not isinstance(value, int) or value < 0:
                problems.append(f"{sid}: {field} must be a non-negative int")

        # Conflict scan target: live snapshot when present, else the
        # verified community-raw/ tree (so the check also runs no-upstream).
        repo_dir = snap_root / str(src.get("snapshot_repo", ""))
        scan: Path | None = None
        if repo_dir.is_dir():
            scan = repo_dir / str(src.get("scan", "."))
            code, head, _ = run_git(repo_dir, "rev-parse", "HEAD")
            if code != 0 or head != commit:
                problems.append(
                    f"{sid}: snapshot HEAD {head!r} != resolved_commit {commit!r}")
            else:
                code, _, _ = run_git(repo_dir, "cat-file", "-e", f"{head}^{{commit}}")
                if code != 0:
                    problems.append(
                        f"{sid}: resolved_commit is not a resolvable git object (17.28)")
            code, dirty_out, _ = run_git(repo_dir, "status", "--porcelain")
            if code != 0 or dirty_out:
                problems.append(f"{sid}: snapshot worktree is dirty (17.28)")
            if scan.is_dir():
                live = digest_of(collect_files(scan)[0])
                for field in ("tree_digest", "file_manifest_digest"):
                    if live[field] != src.get(field):
                        problems.append(
                            f"{sid}: {field} mismatch: lock={src.get(field)} recomputed={live[field]}")
                for field in ("file_count", "dir_count"):
                    if live[field] != src.get(field):
                        problems.append(
                            f"{sid}: {field} drift: lock={src.get(field)} recomputed={live[field]}")
                checked_live += 1
            else:
                problems.append(f"{sid}: scan subdir missing in snapshot: {scan}")
        else:
            warnings.append(
                f"{sid}: snapshot absent ({repo_dir.as_posix()}); cannot machine-check "
                "snapshot existence, HEAD resolvability, dirty state, or digest "
                "recompute for this source -- static lock claims only")
            fallback = root / "community-raw" / RAW_DEST.get(sid, "")
            if fallback.is_dir():
                scan = fallback

        if scan is not None and scan.is_dir():
            for hit in find_collisions(scan):
                problems.append(f"{sid}: case/Unicode path collision (17.30): {hit}")
            _, symlinks = collect_files(scan)
            for link in symlinks:
                warnings.append(f"{sid}: symlink present (recorded, contributes no bytes): {link}")

    report = {
        "lock": lock_path.as_posix(),
        "sources_total": len(sources),
        "sources_live_checked": checked_live,
        "snapshot_root": snap_root.as_posix(),
        "snapshot_root_present": snap_root.is_dir(),
        "problems": problems,
        "warnings": warnings,
    }
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print("=== source attestation ===")
        print(f"lock                        : {lock_path.as_posix()}")
        print(f"sources                     : {len(sources)} (live-checked {checked_live})")
        print(f"snapshot root               : {snap_root.as_posix()} "
              f"({'present' if snap_root.is_dir() else 'ABSENT'})")
        for p in problems:
            print(f"[BLOCKED] {p}")
        for w in warnings:
            print(f"[REVIEW] {w}")

    if problems:
        print(f"FAIL verify-source-attestation: {len(problems)} defect(s)")
        return 20
    if warnings:
        print(f"NEEDS_REVIEW verify-source-attestation: {len(warnings)} item(s)")
        return 10
    print("PASS verify-source-attestation")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
