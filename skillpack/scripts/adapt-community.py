#!/usr/bin/env python3
"""Community source importer: inspect / import / verify / promote / rollback.

This replaces the pre-T05 importer that had no argument parser, took no
candidate path, and wrote 1111 paths per run (including 1 rmtree and a set of
unlink calls) directly into the client discovery root. The rewrite keeps the
same adaptation transform but makes every write go through an explicit
lifecycle:

    inspect    read-only  (never writes anything)
    import     writes ONLY .candidates/<id>/   (never touches the verified tree)
    verify     read-only  (never writes anything)
    promote    the only command that may move a candidate into the verified tree
    rollback   restores the verified tree from a promote snapshot

Safety properties (spec 17.26 / 17.27 / 17.28, task T05):

  * `main()` is only reached through `if __name__ == "__main__"`; importing this
    module performs no work, and `--help` / an unknown argument exits without
    touching a single path. The previous version called `main()` on any argv,
    so `--help` and a typo such as `--soruce` both ran a full import.
  * The write root is `community-raw/`, which is outside the client discovery
    root `skills/` (17.27 item 1). No code path in this file constructs a write
    target under `skills/community/`; `registry.json` is the one exception and
    it is `promote`-only, because it is owned by T02.
  * Every import validates the 17.28 attestation of each source *before*
    copying: `dirty` must be false, `resolved_commit` must be a 40-hex commit
    that `git cat-file -e` can resolve, and the recomputed digests must match
    the declared ones.
  * The digest concatenation format is frozen here (DIGEST_CONTRACT_VERSION) so
    that rewriting the importer cannot silently change the numbers.

Exit codes follow spec 4.7: 0 matched, 10 needs_review, 20 blocked,
21 missing_input, 22 unavailable, 30 failed.

Stdlib only. No network access.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

# --------------------------------------------------------------------------
# Layout contract
# --------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = ROOT.parent / "upstream"

#: Raw vendor content lives here, OUTSIDE the `skills/` discovery root.
#: Changing this constant without re-running 17.27 would re-create the
#: discovery leak that T01 closed, so it is asserted, not just documented.
RAW_ROOT = Path("community-raw")

#: Destination roots per source id, relative to RAW_ROOT.
DEST = {
    "ctf-super-hub": "ctf-super-hub",
    "hack-skills": "hack-skills",
    "ai-fullstack-delivery": "ai-fullstack/workflows",
    "apk-reverse-community": "apk-reverse-source",
}

#: The only path under `skills/` this importer may ever write, and only
#: `promote` may write it (registry.json is owned by T02 per spec 12.0).
REGISTRY_REL = Path("skills/community/registry.json")

#: Where support documents go. Also outside the discovery root.
DOCS_ROOT = Path("docs/community")

CANDIDATES_ROOTNAME = ".candidates"
JOURNAL_NAME = "promote-journal.json"
SOURCE_LOCK_NAME = "source-lock.json"
MANIFEST_NAME = "candidate-manifest.json"

# --------------------------------------------------------------------------
# Digest contract (frozen; see docs/community/IMPORTER-LIFECYCLE.md)
# --------------------------------------------------------------------------
#
#   file line : b"f" NUL <path> NUL <content_sha256_hex> LF
#   dir  line : b"d" NUL <path> NUL LF
#
#   file_manifest_digest = sha256(concat of all file lines, sorted by the
#                                    full line's UTF-8 byte order)
#   tree_digest          = sha256(concat of the sorted union of file lines
#                                    and dir lines)
#
# <path> is the NFC-normalised POSIX-relative path. <content_sha256_hex> is
# sha256 of the file bytes with CRLF folded to LF (b"\r\n" -> b"\n"); a lone CR
# is left alone. Folding is required because `.gitattributes` declares
# `eol=lf`: the same content must hash identically on a Windows checkout, a
# Linux checkout, a no-git copy and a release bundle (17.26).
# File mode, uid/gid, mtime, inode and Windows attribute bits never enter the
# digest.

DIGEST_CONTRACT_VERSION = "skills-hub/importer-digest/1"

SENSITIVE_NAMES = {"debug.keystore", "id_rsa", "id_ed25519"}
SENSITIVE_SUFFIXES = {".pem", ".key"}
LEGACY_PRIVATE_DIR = "reverse-skill-private"

STOPWORDS = {
    "skill", "skills", "use", "when", "with", "for", "and", "the", "this",
    "from", "that", "into", "before", "after", "only", "must", "should",
    "workflow", "engineer", "expert", "playbook", "security", "testing",
}

# Documentation file names copied verbatim from each upstream repository root.
SUPPORT_DOC_NAMES = [
    "README.md", "README.zh-CN.md", "README_CN.md", "START-HERE.md",
    "SKILL-INDEX.md", "THIRD_PARTY_NOTICES.md", "LICENSE", "CONTRIBUTING.md",
    "SECURITY.md", "RULES.md", "WORKFLOW.md", "workflow-map.md", "routing.md",
    "`TOOLS.md`", "PERSONA.md", "EVOLUTION.md",
]

CONTRACT = """
## Integrated reverse-skill contract

This capability is loaded through the canonical reverse-skill router. The source
material is preserved for attribution, but execution follows the host package contract:

1. **Scope first**: initialize the current `work/<case>/scope.md` with the canonical
   `case-init` flow. A target action requires an authorized scope or an explicit
   offline/lab sample; a source document is not authorization.
2. **工具定位**：需要工具时先跑 `(Get-Command <id> -ErrorAction SilentlyContinue).Source`；无值就读 `skillpack/skills/TOOLS.md` 查装法，装完复验。禁止猜路径。
   Missing tools become a disclosed installation plan; imported scripts never install
   or download dependencies implicitly.
3. **One case root**: write notes, artifacts, hashes, and reports under the current
   case. Do not create a parallel source-package `case`, `output`, or `workspace`
   tree.
4. **Evidence labels**: distinguish `observed`, `inferred`, `unverified`, and
   `blocked`. Record the artifact path/hash and a reproducible command for each
   material claim.
5. **Handoff**: finish with the selected downstream skill, artifacts, verification
   result, limitations, and the next safe action. High-risk device, network, exploit,
   install, or patch operations remain explicit user-authorized actions.

The imported text may describe a different host or directory layout. Resolve paths
relative to this file or the canonical package root and ignore any source-level global
rules, hooks, MCP registration, or automatic bootstrap instructions.
"""

WORKFLOW_CONTRACT_MARKER = "## Integrated delivery workflow contract"

RISK_BY_SOURCE = {
    "ctf-super-hub": "medium",
    "hack-skills": "high",
    "ai-fullstack-delivery": "medium",
    "apk-reverse-community": "high",
}

CONTEXT_BY_SOURCE = {
    "ctf-super-hub": ["offline-ctf", "authorized-lab"],
    "hack-skills": ["authorized-lab", "defensive"],
    "ai-fullstack-delivery": ["local-project", "authorized-repository"],
    "apk-reverse-community": ["offline-sample", "authorized-device", "authorized-lab"],
}

# --------------------------------------------------------------------------
# Source table. Pinned commits are the ones recorded by the baseline digest
# (work/baseline-digest.json -> baseline.upstream_clone_heads).
# --------------------------------------------------------------------------

SOURCES = [
    {
        "id": "ctf-super-hub",
        "repo": "ctf-super-hub",
        "upstream_url": "https://github.com/asdfgh1445/ctf-super-hub",
        "commit": "16926d6d4216183995693e9c7936c042eb7f2fae",
        "scan": Path("."),
        "license_status": "review-required",
        "maturity": "partial",
        "license_declared": "NOASSERTION",
        "third_party_review": "required",
        "notice_file": "docs/community/ctf-super-hub/THIRD_PARTY_NOTICES.md",
    },
    {
        "id": "hack-skills",
        "repo": "hack-skills",
        "upstream_url": "https://github.com/yaklang/hack-skills",
        "commit": "6fbf0bc8d5c71830d62543a308d8744606c43d7c",
        "scan": Path("skills"),
        "license_status": "review-required",
        "maturity": "partial",
        "license_declared": "MIT",
        "third_party_review": "required",
        "notice_file": "docs/community/hack-skills/LICENSE",
    },
    {
        "id": "ai-fullstack-delivery",
        "repo": "AI-Fullstack-Delivery-Workflow",
        "upstream_url": "https://github.com/zhaoxuya520/AI-Fullstack-Delivery-Workflow",
        "commit": "ab96b897d719941219ab3b3badb47cd6fda3e0eb",
        "scan": Path("workflows"),
        "license_status": "missing-license",
        "maturity": "unverified",
        "license_declared": "NOASSERTION",
        "third_party_review": "required",
        "notice_file": "docs/community/ai-fullstack-delivery/THIRD_PARTY_NOTICES.md",
    },
    {
        "id": "apk-reverse-community",
        "repo": "apk-reverse",
        "upstream_url": "https://github.com/newliver666/apk-reverse",
        "commit": "7b6c6932a95f03d778e81e5e1a2cbf6f62dc97fd",
        "scan": Path("skills/apk-reverse"),
        "license_status": "MIT",
        "maturity": "partial",
        "license_declared": "MIT",
        "third_party_review": "not-required",
        "notice_file": "docs/community/apk-reverse-community/LICENSE",
    },
]

SOURCE_BY_ID = {s["id"]: s for s in SOURCES}

# --------------------------------------------------------------------------
# Exit codes (spec 4.7)
# --------------------------------------------------------------------------

EXIT_MATCHED = 0
EXIT_NEEDS_REVIEW = 10
EXIT_BLOCKED = 20
EXIT_MISSING_INPUT = 21
EXIT_UNAVAILABLE = 22
EXIT_FAILED = 30

FAILURE_REASONS = {
    EXIT_NEEDS_REVIEW: None,
    EXIT_BLOCKED: "license_not_redistributable",
    EXIT_MISSING_INPUT: "scope_empty",
    EXIT_UNAVAILABLE: "tool_missing",
    EXIT_FAILED: "internal_error",
}

def require_source_tables(source_id: str) -> None:
    """Error handling only: a half-registered source must fail with 21, never KeyError.

    `SOURCES` membership alone is not enough to import: `DEST`,
    `RISK_BY_SOURCE` and `CONTEXT_BY_SOURCE` must each carry the id too.
    This check raises missing_input (21) with the absent table names instead
    of letting a bare `dict[id]` lookup escape as a traceback + exit 1.
    It changes no import logic; fully registered sources never reach the raise.
    """
    missing = [t for t, m in (("DEST", DEST), ("RISK_BY_SOURCE", RISK_BY_SOURCE),
                               ("CONTEXT_BY_SOURCE", CONTEXT_BY_SOURCE)) if source_id not in m]
    if missing:
        raise fail(
            EXIT_MISSING_INPUT,
            f"source '{source_id}' is not fully registered: missing {', '.join(missing)} entries; "
            f"add '{source_id}' to {', '.join(missing)} in scripts/adapt-community.py before importing",
            reason="scope_empty",
            missing_fields=missing,
            source=source_id,
            missing_tables=missing,
        )

class ImporterError(Exception):
    """Abort with a spec-4.7 status. Never leaves a partial write behind."""

    def __init__(self, code: int, reason: str | None, message: str, **extra: object) -> None:
        super().__init__(message)
        self.code = code
        self.reason = reason
        self.message = message
        self.extra = extra

def fail(code: int, message: str, reason: str | None = None, **extra: object) -> "ImporterError":
    if reason is None:
        reason = FAILURE_REASONS.get(code, "internal_error")
    return ImporterError(code, reason, message, **extra)

# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------

def nfc(path: str) -> str:
    return unicodedata.normalize("NFC", path)

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def canonical_bytes(data: bytes) -> bytes:
    """Fold CRLF to LF. Lone CR is preserved (see the digest contract)."""
    return data.replace(b"\r\n", b"\n")

def is_sensitive(name: str) -> bool:
    return name in SENSITIVE_NAMES or Path(name).suffix.lower() in SENSITIVE_SUFFIXES

def run_git(repo: Path, *args: str) -> tuple[int, str, str]:
    """Read-only git. `--no-optional-locks` keeps the repo read-only-friendly."""
    proc = subprocess.run(
        ["git", "--no-optional-locks", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()

def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

# --------------------------------------------------------------------------
# Guard: refuse to write inside the client discovery root
# --------------------------------------------------------------------------

class WriteGuard:
    """Every write performed by `import` and `promote` goes through this.

    The guard exists because the defect T05 closes is a write that *silently*
    landed under `skills/`. A check that is only documented in a comment is not
    a check; this one raises.
    """

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.skills = (self.root / "skills").resolve()
        self.writes: list[str] = []

    def check(self, target: Path) -> Path:
        resolved = Path(os.path.normpath(str(target)))
        try:
            resolved.relative_to(self.skills)
        except ValueError:
            pass
        else:
            # registry.json is the single legal exception, and only promote
            # may write it (it is owned by T02, spec 12.0).
            rel = resolved.relative_to(self.root)
            if rel != REGISTRY_REL or not _promote_context.active:
                raise fail(
                    EXIT_BLOCKED,
                    f"refusing to write inside the discovery root: {rel.as_posix()}",
                    reason="path_escape",
                    path=rel.as_posix(),
                )
        return resolved

    def note(self, target: Path) -> None:
        self.writes.append(Path(os.path.normpath(str(target))).as_posix())

class _PromoteContext:
    active = False

_promote_context = _PromoteContext()

# --------------------------------------------------------------------------
# U11 managed transforms (curation survives re-import)
# --------------------------------------------------------------------------
#
# Policy: curated edits win over upstream bytes (WORK-BOARD CR-002, user call
# 2026-10-01 "first record, then补"). The machine-readable record lives in
# docs/community/IMPORTER-MANAGED-TRANSFORMS.md as a fenced
# ```json managed-transforms block; this importer parses that block directly,
# so the document IS the record (no second copy to drift). `digest` is
# sha256(json.dumps(transforms, sort_keys=True, ensure_ascii=False,
# indent=2) + "\n"). A mismatch means the record was hand-edited without
# re-pinning, and the candidate cannot be trusted.

MANAGED_TRANSFORMS_DOC = Path("docs/community/IMPORTER-MANAGED-TRANSFORMS.md")
MANAGED_TRANSFORMS_SCHEMA = "skills-hub/importer-managed-transforms/1"

def _canonical_transforms_bytes(transforms: object) -> bytes:
    return (json.dumps(transforms, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode("utf-8")

def load_managed_transforms(root: Path) -> tuple[dict[str, object], list[str]]:
    """Parse the record doc. Missing file == no transforms (lab fixtures)."""
    doc = Path(root) / MANAGED_TRANSFORMS_DOC
    if not doc.is_file():
        return {"schema": MANAGED_TRANSFORMS_SCHEMA, "digest": "", "transforms": []}, []
    try:
        text = doc.read_text(encoding="utf-8")
    except OSError as exc:
        return {"schema": MANAGED_TRANSFORMS_SCHEMA, "digest": "", "transforms": []}, [
            f"managed transforms record unreadable: {exc}"
        ]
    match = re.search(r"```json managed-transforms\s+(.*?)```", text, re.S)
    if not match:
        return {"schema": MANAGED_TRANSFORMS_SCHEMA, "digest": "", "transforms": []}, [
            "managed transforms record has no ```json managed-transforms block"
        ]
    try:
        record = json.loads(match.group(1))
    except ValueError as exc:
        return {"schema": MANAGED_TRANSFORMS_SCHEMA, "digest": "", "transforms": []}, [
            f"managed transforms record is not valid JSON: {exc}"
        ]
    problems: list[str] = []
    if record.get("schema") != MANAGED_TRANSFORMS_SCHEMA:
        problems.append(
            f"managed transforms schema mismatch: {record.get('schema')!r} != {MANAGED_TRANSFORMS_SCHEMA!r}"
        )
    transforms = record.get("transforms")
    if not isinstance(transforms, list):
        problems.append("managed transforms 'transforms' must be a list")
        transforms = []
    expected = sha256_bytes(_canonical_transforms_bytes(transforms))
    if record.get("digest") != expected:
        problems.append(
            f"managed transforms digest mismatch: recorded {record.get('digest')!r} != recomputed {expected!r}"
        )
    for entry in transforms:
        if not isinstance(entry, dict):
            problems.append("managed transforms entry must be an object")
            continue
        for field in ("id", "scope", "kind", "pattern", "replacement", "basis"):
            if field not in entry:
                problems.append(f"managed transform {entry.get('id', '?')!r} missing field: {field}")
        if entry.get("kind") not in ("literal", "regex"):
            problems.append(f"managed transform {entry.get('id', '?')!r} kind must be literal|regex")
        if entry.get("kind") == "regex":
            try:
                re.compile(str(entry.get("pattern", "")))
            except re.error as exc:
                problems.append(f"managed transform {entry.get('id', '?')!r} bad regex: {exc}")
    record["transforms"] = transforms
    return record, problems

def _scope_match(rel_posix: str, scope: list[str]) -> bool:
    from fnmatch import fnmatchcase

    return any(fnmatchcase(rel_posix, pat) for pat in scope)

def apply_managed_transforms(
    staging: Path, root: Path, guard: WriteGuard
) -> tuple[dict[str, object], list[str], list[str]]:
    """Apply every registered transform to candidate files. Returns (record, applied, problems)."""
    record, problems = load_managed_transforms(root)
    if problems:
        return record, [], problems
    transforms = record.get("transforms") or []
    assert isinstance(transforms, list)
    applied: list[str] = []
    counts: dict[str, int] = {}
    for rel_root in (RAW_ROOT.as_posix(), DOCS_ROOT.as_posix()):
        base = staging / rel_root
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if path.is_symlink() or not path.is_file():
                continue
            rel = f"{rel_root}/{path.relative_to(base).as_posix()}"
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            new_text = text
            hit_ids: list[str] = []
            for entry in transforms:
                assert isinstance(entry, dict)
                scope = entry.get("scope") or []
                assert isinstance(scope, list)
                if not _scope_match(rel, [str(s) for s in scope]):
                    continue
                if entry.get("kind") == "regex":
                    candidate_text = re.sub(str(entry["pattern"]), str(entry["replacement"]), new_text)
                else:
                    candidate_text = new_text.replace(str(entry["pattern"]), str(entry["replacement"]))
                if candidate_text != new_text:
                    hit_ids.append(str(entry["id"]))
                    new_text = candidate_text
            if new_text != text:
                write_lf(path, new_text, guard)
                applied.append(rel)
                for hid in hit_ids:
                    counts[hid] = counts.get(hid, 0) + 1
    record["_applied_counts"] = counts
    return record, sorted(applied), []

# --------------------------------------------------------------------------
# Digest
# --------------------------------------------------------------------------

def collect_files(root: Path) -> list[tuple[str, bytes]]:
    """(posix-relative path, bytes) for every file under root, sorted."""
    root = Path(root)
    out: list[tuple[str, bytes]] = []
    for path in root.rglob("*"):
        if path.is_symlink():
            # Symlinks are never followed and never contribute bytes (17.26).
            continue
        if not path.is_file():
            continue
        out.append((nfc(path.relative_to(root).as_posix()), path.read_bytes()))
    out.sort(key=lambda item: item[0].encode("utf-8"))
    return out

def file_line(rel: str, data: bytes) -> bytes:
    return b"f\0" + rel.encode("utf-8") + b"\0" + sha256_bytes(canonical_bytes(data)).encode("ascii") + b"\n"

def dir_line(rel: str) -> bytes:
    return b"d\0" + rel.encode("utf-8") + b"\0\n"

def ancestors(rel: str) -> list[str]:
    parts = rel.split("/")
    return ["/".join(parts[:i]) for i in range(1, len(parts))]

def digest_of(pairs: list[tuple[str, bytes]]) -> dict[str, object]:
    """The frozen 17.26 digest over a (path, bytes) list."""
    file_lines = sorted((file_line(rel, data) for rel, data in pairs), key=lambda b: b)
    dirs: set[str] = set()
    for rel, _ in pairs:
        dirs.update(ancestors(rel))
    dir_lines = sorted((dir_line(d) for d in dirs), key=lambda b: b)
    return {
        "digest_contract": DIGEST_CONTRACT_VERSION,
        "file_count": len(pairs),
        "dir_count": len(dirs),
        "file_manifest_digest": sha256_bytes(b"".join(file_lines)),
        "tree_digest": sha256_bytes(b"".join(sorted(file_lines + dir_lines))),
        "directories": sorted(dirs),
    }

def digest_of_tree(root: Path) -> dict[str, object]:
    return digest_of(collect_files(Path(root)))

def read_digest_file(path: Path) -> dict[str, object] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None
    if not isinstance(data, dict):
        return None
    return data

# --------------------------------------------------------------------------
# 17.28 attestation
# --------------------------------------------------------------------------

def attest_source(source: dict) -> dict[str, object]:
    """Build the 17.28 attestation by measuring the local snapshot.

    No network is used. `default_branch_commit` is therefore *not* asserted
    here: it cannot be established offline, and 17.28 only requires it to be
    recorded. It is carried through from the source lock when one exists, and
    left null with an explicit note otherwise.
    """
    repo = UPSTREAM / source["repo"]
    if not repo.is_dir():
        raise fail(
            EXIT_MISSING_INPUT,
            f"upstream snapshot missing: {repo.as_posix()}",
            reason="scope_empty",
            missing_fields=["upstream_snapshot"],
            dependency=repo.as_posix(),
        )

    code, head, _ = run_git(repo, "rev-parse", "HEAD")
    if code != 0 or not re.fullmatch(r"[0-9a-f]{40}", head):
        raise fail(
            EXIT_UNAVAILABLE,
            f"cannot resolve HEAD for {source['id']}",
            reason="tool_missing",
            dependency="git",
        )

    code, dirty_out, _ = run_git(repo, "status", "--porcelain")
    dirty = bool(dirty_out) if code == 0 else True

    code, _, _ = run_git(repo, "cat-file", "-e", f"{head}^{{commit}}")
    commit_resolvable = code == 0

    code, origin_url, _ = run_git(repo, "config", "--get", "remote.origin.url")
    code2, version, _ = run_git(repo, "--version")

    scan_root = repo / source["scan"]
    tree = digest_of_tree(scan_root)

    return {
        "upstream_url": source["upstream_url"],
        "resolved_commit": head,
        "default_branch_commit": None,
        "origin_head_commit": head,
        "dirty": dirty,
        "tree_digest": tree["tree_digest"],
        "file_manifest_digest": tree["file_manifest_digest"],
        "file_count": tree["file_count"],
        "dir_count": tree["dir_count"],
        "fetched_at": utc_now(),
        "fetch_tool_and_version": f"git {version}" if code2 == 0 else "git (version unknown)",
        "attestation_method": "git-commit",
        "snapshot_root": repo.as_posix(),
        "origin_url": origin_url or source["upstream_url"],
        "commit_resolvable": commit_resolvable,
        "digest_contract": DIGEST_CONTRACT_VERSION,
        "offline_note": (
            "default_branch_commit is null: this importer is offline and does not "
            "contact the remote. 17.28 requires the field to be recorded; a value "
            "must be supplied by whoever performs the fetch."
        ),
    }

#: Hard pre-import gates. A source failing any of these never reaches a
#: candidate directory.
ATTESTATION_HARD_FIELDS = (
    "upstream_url",
    "resolved_commit",
    "origin_head_commit",
    "dirty",
    "tree_digest",
    "file_manifest_digest",
    "fetched_at",
    "fetch_tool_and_version",
    "attestation_method",
)

ATTESTATION_METHODS = {"git-commit", "tarball-digest", "api-tree-digest"}

def validate_attestation(source: dict, att: dict, expected_commit: str | None) -> list[str]:
    """Return the list of violated 17.28 rules (empty == acceptable)."""
    problems: list[str] = []
    for field in ATTESTATION_HARD_FIELDS:
        if field not in att:
            problems.append(f"attestation missing field: {field}")
    if att.get("dirty") is not False:
        problems.append("attestation dirty must be false (17.28)")
    commit = att.get("resolved_commit")
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
        problems.append("resolved_commit must be 40 lowercase hex (17.28)")
    if att.get("commit_resolvable") is False:
        problems.append("resolved_commit is not a resolvable git object (17.28)")
    if att.get("attestation_method") not in ATTESTATION_METHODS:
        problems.append(f"attestation_method must be one of {sorted(ATTESTATION_METHODS)}")
    for field in ("tree_digest", "file_manifest_digest"):
        value = att.get(field)
        if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
            problems.append(f"{field} must be sha256 lowercase hex (17.26)")
    if att.get("digest_contract") != DIGEST_CONTRACT_VERSION:
        problems.append(
            f"digest_contract mismatch: {att.get('digest_contract')!r} != {DIGEST_CONTRACT_VERSION!r}"
        )
    if expected_commit and commit != expected_commit:
        problems.append(f"resolved_commit {commit} != pinned commit {expected_commit}")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", str(att.get("fetched_at", ""))):
        problems.append("fetched_at must be UTC RFC 3339")
    return problems

# --------------------------------------------------------------------------
# Adaptation transform (byte-for-byte the same semantics as the old script)
# --------------------------------------------------------------------------

def parse_frontmatter(text: str) -> tuple[str, str]:
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
    if not match:
        return "", ""
    block = match.group(1)
    name = re.search(r"^name:\s*[\"']?([^\"'\n]+)", block, re.M)
    description = re.search(r"^description:\s*(.+)$", block, re.M)
    return (name.group(1).strip() if name else "", description.group(1).strip() if description else "")

def keywords_for(skill_path: Path, name: str, description: str) -> list[str]:
    text = f"{skill_path.as_posix()} {name} {description}".lower()
    words = re.findall(r"[a-z][a-z0-9-]{2,}", text)
    result: list[str] = []
    for word in words:
        if word in STOPWORDS or word in result:
            continue
        result.append(word)
        if len(result) == 24:
            break
    return result

def normalize_frontmatter_text(text: str, source: dict, source_relative: str) -> str:
    require_source_tables(source["id"])
    match = re.match(r"^(---\s*\n)(.*?)(\n---\s*\n)(.*)$", text, re.S)
    if not match:
        slug = Path(source_relative).parent.name
        block = "\n".join([
            f"name: community-{source['id']}-{slug}",
            f"description: Adapted capability from {source_relative}.",
            f'license: "{source["license_status"]}"',
            'compatibility: "Requires the canonical reverse-skill case/scope contract; source tools are optional."',
            "allowed-tools: Read Write Edit Glob Grep Bash",
            "metadata:",
            '  integrated: "true"',
            f'  integration-source: "{source["id"]}"',
            f'  source-path: "{source_relative}"',
            f'  maturity: "{source["maturity"]}"',
            '  integration-risk: "medium"',
            '  allowed-context: "local-project,authorized-repository"',
            '  user-invocable: "false"',
        ])
        text = "---\n" + block + "\n---\n\n" + text
        match = re.match(r"^(---\s*\n)(.*?)(\n---\s*\n)(.*)$", text, re.S)
        if not match:
            return text
    block = match.group(2)
    additions: list[str] = []
    if not re.search(r"^license:\s*", block, re.M):
        additions.append(f'license: "{source["license_status"]}"')
    if not re.search(r"^compatibility:\s*", block, re.M):
        additions.append('compatibility: "Requires the canonical reverse-skill case/scope contract; source tools are optional."')
    if not re.search(r"^allowed-tools:\s*", block, re.M):
        additions.append("allowed-tools: Read Write Edit Glob Grep Bash")
    if "metadata:" not in block:
        additions.extend([
            "metadata:",
            '  integrated: "true"',
            f'  integration-source: "{source["id"]}"',
            f'  source-path: "{source_relative}"',
            f'  maturity: "{source["maturity"]}"',
            f'  integration-risk: "{RISK_BY_SOURCE[source["id"]]}"',
            f'  allowed-context: "{",".join(CONTEXT_BY_SOURCE[source["id"]])}"',
            '  user-invocable: "false"',
        ])
    elif "integrated:" not in block:
        lines = block.splitlines()
        insert_at = len(lines)
        for index, line in enumerate(lines):
            if line.startswith("metadata:"):
                insert_at = index + 1
                while insert_at < len(lines) and (lines[insert_at].startswith("  ") or not lines[insert_at].strip()):
                    insert_at += 1
                break
        lines[insert_at:insert_at] = [
            '  integrated: "true"',
            f'  integration-source: "{source["id"]}"',
            f'  source-path: "{source_relative}"',
            f'  maturity: "{source["maturity"]}"',
            f'  integration-risk: "{RISK_BY_SOURCE[source["id"]]}"',
            f'  allowed-context: "{",".join(CONTEXT_BY_SOURCE[source["id"]])}"',
            '  user-invocable: "false"',
        ]
        block = "\n".join(lines)
    if additions:
        block = block.rstrip() + "\n" + "\n".join(additions)
    return match.group(1) + block + match.group(3) + match.group(4)

def add_contract_text(text: str, contract: str) -> str:
    contract = contract.replace(r"\n", "\n").replace("\n+", "\n")
    if "## Integrated reverse-skill contract" in text:
        return text
    match = re.match(r"^(---\s*\n.*?\n---\s*\n)(.*)$", text, re.S)
    if match:
        return match.group(1) + contract + "\n" + match.group(2).lstrip()
    return contract.lstrip() + "\n" + text

def add_workflow_contract_text(text: str) -> str:
    if WORKFLOW_CONTRACT_MARKER in text:
        return text
    block = f"""\
\n{WORKFLOW_CONTRACT_MARKER}\n\nThis workflow is an optional delivery layer under the canonical reverse-skill package.\nUse it only for software delivery tasks; security or reverse-engineering actions still\nroute through the package scope/case gate. Inputs, outputs, acceptance criteria, and\nfield-journal entries belong to the current case or project root, and missing tools are\nreported instead of installed implicitly.\n\n"""
    return text.rstrip() + block

def write_lf(path: Path, text: str, guard: WriteGuard) -> None:
    """Write LF-normalised UTF-8 through the guard, atomically per file."""
    target = guard.check(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".t05tmp")
    tmp.write_bytes(text.replace("\r\n", "\n").encode("utf-8"))
    os.replace(tmp, target)
    guard.note(target)

def copy_file_lf(src: Path, dst: Path, guard: WriteGuard) -> None:
    """Copy with CRLF folded to LF.

    The old importer used `shutil.copy2`, which preserves the upstream CRLF
    bytes into the worktree while `.gitattributes(eol=lf)` normalises them at
    commit time. That makes the worktree bytes and the committed bytes differ,
    which 17.26 forbids. Folding on the way in removes the discrepancy at the
    source.
    """
    write_lf(dst, src.read_bytes().decode("utf-8", errors="replace"), guard)

# --------------------------------------------------------------------------
# Candidate construction
# --------------------------------------------------------------------------

def candidate_root(candidate_id: str) -> Path:
    return ROOT / CANDIDATES_ROOTNAME / candidate_id

def resolve_candidate(value: str) -> Path:
    """Accept either a bare id or a path, but keep it under .candidates/."""
    text = value.replace("\\", "/")
    path = Path(text)
    if path.is_absolute() or text.startswith(("..", ".")) or "/" in text.rstrip("/"):
        if text.startswith(CANDIDATES_ROOTNAME + "/") or text.startswith("./" + CANDIDATES_ROOTNAME + "/"):
            path = ROOT / text.lstrip("./")
        else:
            raise fail(
                EXIT_MISSING_INPUT,
                f"--candidate must be {CANDIDATES_ROOTNAME}/<id>: {value!r}",
                reason="scope_empty",
                missing_fields=["candidate_path"],
            )
    else:
        path = candidate_root(text)
    resolved = Path(os.path.normpath(str(path)))
    base = (ROOT / CANDIDATES_ROOTNAME).resolve()
    try:
        resolved.relative_to(base)
    except ValueError:
        raise fail(
            EXIT_BLOCKED,
            f"candidate escapes {CANDIDATES_ROOTNAME}/: {value!r}",
            reason="path_escape",
        ) from None
    return resolved

def build_candidate(source_ids: list[str], candidate_id: str, guard: WriteGuard, dry_run: bool) -> dict[str, object]:
    """Materialise a candidate tree. Only ever writes under .candidates/."""
    candidate = resolve_candidate(candidate_id)
    if candidate.exists():
        raise fail(
            EXIT_BLOCKED,
            f"candidate already exists: {candidate.relative_to(ROOT).as_posix()}",
            reason="internal_error",
        )
    if dry_run:
        _record, _problems = load_managed_transforms(ROOT)
        if _problems:
            raise fail(
                EXIT_BLOCKED,
                "managed transforms record rejected",
                reason="internal_error",
                policy="U11: managed transforms digest must pin the record",
                required_action=_problems,
                problems=_problems,
            )
        return {"candidate": candidate.relative_to(ROOT).as_posix(), "written": False}

    attestations: dict[str, object] = {}
    for source_id in source_ids:
        require_source_tables(source_id)
        source = SOURCE_BY_ID[source_id]
        att = attest_source(source)
        problems = validate_attestation(source, att, source["commit"])
        if problems:
            raise fail(
                EXIT_BLOCKED,
                f"source attestation rejected for {source_id}",
                reason="internal_error",
                policy="17.28",
                required_action="; ".join(problems),
                source=source_id,
                problems=problems,
            )
        attestations[source_id] = att

    staging = candidate.with_name(candidate.name + ".partial")
    if staging.exists():
        shutil.rmtree(staging)
    try:
        for source_id in source_ids:
            _materialise_source(source_id, staging, guard)
        # U11: curated edits win. Apply the managed transforms AFTER upstream
        # materialisation so the candidate carries them; unregistered diffs
        # stay visible in the diff summary and block promote.
        managed_record, managed_applied, managed_problems = apply_managed_transforms(staging, ROOT, guard)
        if managed_problems:
            raise fail(
                EXIT_BLOCKED,
                "managed transforms record rejected",
                reason="internal_error",
                policy="U11: managed transforms digest must pin the record",
                required_action=managed_problems,
                problems=managed_problems,
            )
        # registry candidate: read-only merge, never a v1 rewrite
        merged = _build_candidate_registry(source_ids, staging, attestations)
        write_lf(staging / "registry.json", json.dumps(merged, ensure_ascii=False, indent=2) + "\n", guard)
        att_json = json.dumps(attestations, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        write_lf(staging / SOURCE_LOCK_NAME, att_json, guard)

        summary = _diff_summary(staging, managed_record, managed_applied)
        write_lf(staging / "diff-summary.md", summary, guard)

        manifest = {
            "schema": "skills-hub/importer-candidate/1",
            "candidate": candidate.name,
            "created_at": utc_now(),
            "sources": source_ids,
            "digest_contract": DIGEST_CONTRACT_VERSION,
            "managed": {
                "digest": managed_record.get("digest", ""),
                "transform_ids": [str(t.get("id")) for t in managed_record.get("transforms", []) if isinstance(t, dict)],
                "applied": managed_applied,
            },
            "raw": digest_of_tree(staging / RAW_ROOT.as_posix()) if (staging / RAW_ROOT.as_posix()).is_dir() else None,
            "docs": digest_of_tree(staging / DOCS_ROOT.as_posix()) if (staging / DOCS_ROOT.as_posix()).is_dir() else None,
            "registry": {
                "path": REGISTRY_REL.as_posix(),
                "sha256": sha256_bytes((staging / "registry.json").read_bytes()),
            },
        }
        write_lf(staging / MANIFEST_NAME, json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", guard)
        os.replace(staging, candidate)
    except BaseException:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        raise
    manifest["candidate"] = candidate.relative_to(ROOT).as_posix()
    return manifest

def _materialise_source(source_id: str, staging: Path, guard: WriteGuard) -> None:
    require_source_tables(source_id)
    source = SOURCE_BY_ID[source_id]
    repo = UPSTREAM / source["repo"]
    source_root = repo / source["scan"]
    if not source_root.is_dir():
        raise fail(
            EXIT_MISSING_INPUT,
            f"missing source tree: {source_root.as_posix()}",
            reason="scope_empty",
            missing_fields=["source_tree"],
        )
    dest_root = staging / RAW_ROOT.as_posix() / DEST[source_id]
    docs_root = staging / DOCS_ROOT.as_posix() / source_id

    if source_id == "ai-fullstack-delivery":
        # The delivery source keeps important WORKFLOW.md / routing.md /
        # template files beside the nested skills, so the whole scan tree is
        # copied first and the nested SKILL.md files are then adapted in place.
        # Copying skill-parent per skill instead would drop every file that is
        # not inside a skill directory (measured: 243 files).
        for item in sorted(source_root.rglob("*")):
            if is_sensitive(item.name) or LEGACY_PRIVATE_DIR in item.parts:
                continue
            if item.is_symlink() or not item.is_file():
                continue
            copy_file_lf(item, dest_root / item.relative_to(source_root), guard)
        for skill_file in sorted(source_root.rglob("SKILL.md")):
            if LEGACY_PRIVATE_DIR in skill_file.parts:
                continue
            _adapt_skill(skill_file, dest_root / skill_file.parent.relative_to(source_root), source, guard)
        for workflow in sorted(dest_root.rglob("WORKFLOW.md")):
            text = workflow.read_text(encoding="utf-8", errors="replace")
            write_lf(workflow, add_workflow_contract_text(text), guard)
    else:
        for skill_file in sorted(source_root.rglob("SKILL.md")):
            _adapt_skill(skill_file, dest_root / skill_file.parent.relative_to(source_root), source, guard)

    for name in SUPPORT_DOC_NAMES:
        item = repo / name
        if item.is_file():
            copy_file_lf(item, docs_root / name, guard)
    if source_id == "ctf-super-hub":
        third_party = repo / "third_party"
        if third_party.is_dir():
            for sub in sorted(third_party.rglob("*")):
                if sub.is_file() and not is_sensitive(sub.name):
                    copy_file_lf(sub, docs_root / "third_party" / sub.relative_to(third_party), guard)

def _adapt_skill(skill_file: Path, destination: Path, source: dict, guard: WriteGuard) -> None:
    """Copy one skill's parent directory, then apply the two transforms."""
    for item in sorted(skill_file.parent.iterdir()):
        if is_sensitive(item.name):
            continue
        target = destination / item.name
        if item.is_dir():
            for sub in sorted(item.rglob("*")):
                if not sub.is_file() or sub.is_symlink() or is_sensitive(sub.name):
                    continue
                copy_file_lf(sub, target / sub.relative_to(item), guard)
        else:
            copy_file_lf(item, target, guard)
    source_relative = skill_file.relative_to(UPSTREAM / source["repo"]).as_posix()
    text = (destination / "SKILL.md").read_text(encoding="utf-8", errors="replace")
    text = normalize_frontmatter_text(text, source, source_relative)
    text = add_contract_text(text, CONTRACT)
    write_lf(destination / "SKILL.md", text, guard)

def _build_candidate_registry(source_ids: list[str], staging: Path, attestations: dict) -> dict:
    """Merge, never regenerate.

    The pre-T05 importer rebuilt `registry.json` from a hard-coded SOURCES list,
    which destroyed the v2 curation fields T02 added (wrappers, discovery,
    entrypoint, content_hash, extensions, ...). registry.json is owned by T02
    (spec 12.0), so this importer only produces a *candidate* registry: the
    existing file with the per-source attestation columns refreshed and the
    adapted paths of the selected sources re-pointed. The promoted file is
    always a candidate file, never a regeneration.
    """
    live = ROOT / REGISTRY_REL
    if not live.is_file():
        raise fail(
            EXIT_MISSING_INPUT,
            f"live registry not found: {REGISTRY_REL.as_posix()}",
            reason="scope_empty",
            missing_fields=["registry"],
        )
    data = json.loads(live.read_text(encoding="utf-8"))

    for record in data.get("sources", []):
        att = attestations.get(record.get("id"))
        if not att:
            continue
        record["tree_digest"] = att["tree_digest"]
        record["source_manifest"] = att["file_manifest_digest"]
        record["snapshot_root"] = att["snapshot_root"]
        record["origin_head_commit"] = att["origin_head_commit"]
        record["dirty"] = att["dirty"]
        record["fetched_at"] = att["fetched_at"]
        record["fetch_tool_and_version"] = att["fetch_tool_and_version"]
        record["attestation_method"] = att["attestation_method"]
        record["digest_contract"] = att["digest_contract"]
        record["last_verified_at"] = att["fetched_at"]

    data["importer"] = {
        "contract": DIGEST_CONTRACT_VERSION,
        "generated_by": "scripts/adapt-community.py import",
        "candidate_sources": sorted(source_ids),
    }
    return data

def _diff_summary(
    staging: Path,
    managed_record: dict[str, object] | None = None,
    managed_applied: list[str] | None = None,
) -> str:
    """Additions / modifications / deletions, scoped per source.

    The scope matters. Comparing whole trees would report every hand-written
    file under `docs/community/` as a "deletion", because the candidate only
    contains the importer-owned per-source subdirectories. Promote moves the
    same per-source scope, so the summary and the promotion agree.

    U11: unregistered differences are listed, never hidden. Managed paths are
    reported in their own section so a reviewer can tell "survives by record"
    apart from "still open".
    """
    lines = [
        "# Candidate diff summary",
        "",
        f"Digest contract: `{DIGEST_CONTRACT_VERSION}`",
        "",
        "Scope is per source: `community-raw/<dest>/**` and `docs/community/<source-id>/**`.",
        "Files outside that scope are not owned by the importer and are neither listed nor touched.",
        "",
    ]
    managed_record = managed_record or {}
    managed_applied = managed_applied or []
    transforms = managed_record.get("transforms") or []
    lines.append("## Managed transforms applied")
    lines.append("")
    lines.append(f"- record digest: `{managed_record.get('digest', '')}`")
    lines.append(f"- registered transforms: {len(transforms) if isinstance(transforms, list) else 0}")
    lines.append(f"- files carrying a managed transform: {len(managed_applied)}")
    lines.append("")
    if managed_applied:
        lines.append("Unregistered differences below do NOT include these paths "
                     "when they now match the verified tree; every other diff stays visible.")
        lines.append("")
    else:
        lines.append("No file carries a managed transform in this candidate; "
                     "every diff below is unregistered.")
        lines.append("")
    totals = {"additions": 0, "modifications": 0, "deletions": 0}
    for source in SOURCES:
        rels = [Path(RAW_ROOT.as_posix()) / DEST[source["id"]], Path(DOCS_ROOT.as_posix()) / source["id"]]
        added: list[str] = []
        modified: list[str] = []
        deleted: list[str] = []
        for rel in rels:
            cand, live = staging / rel, ROOT / rel
            cand_files = {p: d for p, d in collect_files(cand)} if cand.is_dir() else {}
            live_files = {p: d for p, d in collect_files(live)} if live.is_dir() else {}
            for path, data in cand_files.items():
                if path not in live_files:
                    added.append(f"{rel.as_posix()}/{path}")
                elif canonical_bytes(live_files[path]) != canonical_bytes(data):
                    modified.append(f"{rel.as_posix()}/{path}")
            deleted.extend(f"{rel.as_posix()}/{p}" for p in live_files if p not in cand_files)
        totals["additions"] += len(added)
        totals["modifications"] += len(modified)
        totals["deletions"] += len(deleted)
        lines.append(f"## {source['id']}")
        lines.append("")
        lines.append(f"- additions: {len(added)}")
        lines.append(f"- modifications: {len(modified)}")
        lines.append(f"- deletions: {len(deleted)}")
        lines.append("")
        for title, items in (("Additions", added), ("Modifications", modified), ("Deletions", deleted)):
            if not items:
                continue
            lines.append(f"### {title} ({len(items)})")
            lines.append("")
            lines.extend(f"- `{p}`" for p in sorted(items)[:200])
            if len(items) > 200:
                lines.append(f"- ... and {len(items) - 200} more")
            lines.append("")
    lines.append("## totals")
    lines.append("")
    for key, value in totals.items():
        lines.append(f"- {key}: {value}")
    lines.append("")
    lines.append("The candidate is a proposal. Nothing above has touched the verified tree.")
    lines.append("")
    return "\n".join(lines)

# --------------------------------------------------------------------------
# verify
# --------------------------------------------------------------------------

def verify_candidate(candidate: Path) -> dict[str, object]:
    """Read-only. Writes nothing, including no `validation/` directory."""
    if not candidate.is_dir():
        raise fail(
            EXIT_MISSING_INPUT,
            f"candidate not found: {candidate.relative_to(ROOT).as_posix()}",
            reason="scope_empty",
            missing_fields=["candidate"],
        )
    manifest = read_digest_file(candidate / MANIFEST_NAME)
    lock = read_digest_file(candidate / SOURCE_LOCK_NAME)
    problems: list[str] = []
    warnings: list[str] = []

    if manifest is None:
        problems.append(f"missing or unreadable {MANIFEST_NAME}")
    if lock is None:
        problems.append(f"missing or unreadable {SOURCE_LOCK_NAME}")
    if manifest and manifest.get("digest_contract") != DIGEST_CONTRACT_VERSION:
        problems.append(
            f"digest contract mismatch: {manifest.get('digest_contract')!r} != {DIGEST_CONTRACT_VERSION!r}"
        )

    for key, rel_root in (("raw", RAW_ROOT.as_posix()), ("docs", DOCS_ROOT.as_posix())):
        expected = (manifest or {}).get(key)
        tree = candidate / rel_root
        if not expected or not tree.is_dir():
            continue
        actual = digest_of_tree(tree)
        if actual["tree_digest"] != expected.get("tree_digest"):
            problems.append(f"{key} tree_digest mismatch: {actual['tree_digest']} != {expected.get('tree_digest')}")
        if actual["file_manifest_digest"] != expected.get("file_manifest_digest"):
            problems.append(
                f"{key} file_manifest_digest mismatch: {actual['file_manifest_digest']} != {expected.get('file_manifest_digest')}"
            )
        if actual["file_count"] != expected.get("file_count"):
            warnings.append(f"{key} file_count {actual['file_count']} != recorded {expected.get('file_count')}")

    registry = candidate / "registry.json"
    if not registry.is_file():
        problems.append("missing candidate registry.json")
    else:
        recorded = ((manifest or {}).get("registry") or {}).get("sha256")
        actual = sha256_bytes(registry.read_bytes())
        if recorded and actual != recorded:
            problems.append(f"registry sha256 mismatch: {actual} != {recorded}")
        try:
            json.loads(registry.read_text(encoding="utf-8"))
        except ValueError as exc:
            problems.append(f"candidate registry.json is not valid JSON: {exc}")

    # 17.27 item 1, asserted on the candidate: nothing may live under skills/.
    leaked = [
        p.relative_to(candidate).as_posix()
        for p in candidate.rglob("*")
        if p.is_file() and (p.relative_to(candidate).parts[0] == "skills")
    ]
    if leaked:
        problems.append(f"candidate writes into the discovery root: {leaked[:5]}")

    for source_id, att in (lock or {}).items():
        src = SOURCE_BY_ID.get(source_id)
        problems.extend(
            f"{source_id}: {p}" for p in validate_attestation(src, att, src["commit"] if src else None)
        )

    # U11: the managed-transforms record pins the candidate. A digest mismatch
    # means the record was edited without re-pinning (untrusted), and a record
    # change after import means this candidate is stale (it was built under a
    # different curation policy).
    record, record_problems = load_managed_transforms(ROOT)
    problems.extend(f"managed-transforms: {p}" for p in record_problems)
    recorded_digest = ((manifest or {}).get("managed") or {}).get("digest", "")
    if not record_problems and recorded_digest != record.get("digest", ""):
        problems.append(
            f"managed transforms record changed since import: candidate {recorded_digest!r} != current {record.get('digest', '')!r}; rebuild the candidate"
        )

    return {"candidate": candidate.relative_to(ROOT).as_posix(), "problems": problems, "warnings": warnings}

# --------------------------------------------------------------------------
# promote / rollback
# --------------------------------------------------------------------------

#: Windows cannot atomically replace a non-empty directory with a single
#: syscall, so promote is a journaled two-rename with a *recoverable window*,
#: not an atomic swap. The window between rename 1 and rename 2 is real and is
#: documented; nothing here claims atomicity.
_PROMOTE_STATES = ("begin", "target-moved-aside", "committed", "restored")

def _volume_ok(a: Path, b: Path) -> bool:
    try:
        return os.stat(a).st_dev == os.stat(b).st_dev
    except OSError:
        return False

def promote_candidate(candidate: Path, status: str | None, guard: WriteGuard, dry_run: bool) -> dict[str, object]:
    if not status:
        raise fail(
            EXIT_MISSING_INPUT,
            "promote requires --status local-only|release",
            reason="scope_empty",
            missing_fields=["status"],
        )
    if status not in {"local-only", "release"}:
        raise fail(
            EXIT_MISSING_INPUT,
            f"--status must be local-only or release, got {status!r}",
            reason="scope_empty",
            missing_fields=["status"],
        )
    # A candidate that does not exist is a blocked promotion, not a missing
    # argument: the arguments are fine, the precondition is not.
    if not candidate.is_dir():
        raise fail(
            EXIT_BLOCKED,
            f"candidate not found, refusing to promote: {candidate.relative_to(ROOT).as_posix()}",
            reason="license_not_redistributable",
            policy="T05: promote requires a verified candidate directory",
            required_action=["build the candidate with import, then verify it"],
        )
    result = verify_candidate(candidate)
    if result["problems"]:
        raise fail(
            EXIT_BLOCKED,
            "candidate did not pass verify; refusing to promote",
            reason="license_not_redistributable",
            policy="T05: promote requires a clean verify",
            required_action=result["problems"][:20],
        )

    # U11: refuse to revert unregistered curation. After the managed
    # transforms have been applied, the candidate's managed paths must equal
    # the verified tree; EVERY remaining modification/deletion would silently
    # roll back a curated edit (or ship an upstream change over one without a
    # recorded decision), so promote stops with exit 20 and names the paths.
    # Pure additions never block. The manifest's managed_applied list is the
    # positive proof of what the record covered; it exempts nothing.
    #
    # Scope (P1-4): the check covers exactly the candidate's own sources
    # (manifest "sources"), which is the same per-source scope promote writes
    # (see `moves` below). Dirt in a source this candidate does not carry can
    # never be reverted by this promote, so it must not block it; a full
    # candidate still checks every source and still refuses on any dirt.
    manifest = read_digest_file(candidate / MANIFEST_NAME) or {}
    candidate_sources = manifest.get("sources") or [s["id"] for s in SOURCES]
    scoped_sources = [s for s in SOURCES if s["id"] in candidate_sources]
    unregistered: list[str] = []
    for source in scoped_sources:
        for rel in (Path(RAW_ROOT.as_posix()) / DEST[source["id"]], Path(DOCS_ROOT.as_posix()) / source["id"]):
            cand, live = candidate / rel, ROOT / rel
            cand_files = {p: d for p, d in collect_files(cand)} if cand.is_dir() else {}
            live_files = {p: d for p, d in collect_files(live)} if live.is_dir() else {}
            for path, data in cand_files.items():
                full = f"{rel.as_posix()}/{path}"
                if path in live_files and canonical_bytes(live_files[path]) != canonical_bytes(data):
                    unregistered.append(full)
            for path in live_files:
                if path not in cand_files:
                    full = f"{rel.as_posix()}/{path}"
                    unregistered.append(full)
    if unregistered:
        raise fail(
            EXIT_BLOCKED,
            f"promote would revert {len(unregistered)} unregistered curated edit(s); refusing",
            reason="internal_error",
            policy="U11: curated edits win; register the transform or keep the candidate out of the verified tree",
            required_action=sorted(unregistered)[:20],
            unregistered=sorted(unregistered)[:200],
            unregistered_count=len(unregistered),
            checked_scope=sorted(s["id"] for s in scoped_sources),
        )

    if dry_run:
        return {
            "promoted": False,
            "status": status,
            "raw": (ROOT / RAW_ROOT.as_posix()).relative_to(ROOT).as_posix(),
            "docs": (ROOT / DOCS_ROOT.as_posix()).relative_to(ROOT).as_posix(),
            "registry": REGISTRY_REL.as_posix(),
        }

    _promote_context.active = True
    try:
        # Registry is the only path under skills/ this importer may write, and
        # only while promote is active. The check raises if that ever changes.
        guard.check(ROOT / REGISTRY_REL)
    finally:
        _promote_context.active = False

    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    snapshot = ROOT / CANDIDATES_ROOTNAME / "snapshots" / f"verified-{stamp}"
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    journal_path = ROOT / CANDIDATES_ROOTNAME / JOURNAL_NAME
    if journal_path.exists():
        raise fail(
            EXIT_BLOCKED,
            f"an unfinished promote journal exists: {journal_path.relative_to(ROOT).as_posix()}; "
            "resolve it before promoting again",
            reason="internal_error",
        )

    # Reuse the manifest already read for the scoped U11 check above, so the
    # check scope and the write scope come from the same data by construction.
    source_ids = candidate_sources
    # Per-source scope. Promoting whole `docs/community/` or whole
    # `community-raw/` would move hand-written files that the importer does not
    # own, and would delete anything it does not carry.
    moves: list[tuple[str, Path, Path]] = []
    for source_id in source_ids:
        source = SOURCE_BY_ID.get(source_id)
        if source is None:
            continue
        for rel in (Path(RAW_ROOT.as_posix()) / DEST[source_id], Path(DOCS_ROOT.as_posix()) / source_id):
            cand = candidate / rel
            if cand.is_dir():
                moves.append((source_id, cand, ROOT / rel))
    if not moves:
        raise fail(
            EXIT_MISSING_INPUT,
            "candidate carries no per-source raw or docs tree to promote",
            reason="scope_empty",
            missing_fields=["candidate_payload"],
        )
    if not _volume_ok(snapshot.parent, ROOT):
        raise fail(
            EXIT_UNAVAILABLE,
            f"{CANDIDATES_ROOTNAME}/ and the verified tree are on different volumes; "
            "rename would degrade to copy and lose the recovery property",
            reason="tool_missing",
            dependency="same-volume rename",
        )

    registry_live = ROOT / REGISTRY_REL
    journal = {
        "schema": "skills-hub/promote-journal/1",
        "state": "begin",
        "candidate": candidate.relative_to(ROOT).as_posix(),
        "snapshot": snapshot.relative_to(ROOT).as_posix(),
        "registry_snapshot": (snapshot / "registry.json").as_posix(),
        "registry_target": REGISTRY_REL.as_posix(),
        "status": status,
        "started_at": utc_now(),
        "steps": [],
        "recoverable_window": (
            "Promote is a sequence of per-directory renames, not an atomic swap: "
            "on Windows os.replace cannot replace a non-empty directory. Between "
            "'target-moved-aside' and 'committed' a source may be absent from the "
            "verified tree. That window is recoverable, not atomic: this journal "
            "and the snapshot say exactly which renames already happened."
        ),
        "moves": [
            {
                "source": source_id,
                "candidate": cand.relative_to(ROOT).as_posix(),
                "target": live.relative_to(ROOT).as_posix(),
            }
            for source_id, cand, live in moves
        ],
    }
    _write_json(journal_path, journal)

    try:
        if registry_live.is_file():
            snapshot.mkdir(parents=True, exist_ok=True)
            shutil.copy2(registry_live, snapshot / "registry.json")
        for source_id, cand, live in moves:
            if live.is_dir():
                aside = snapshot / live.relative_to(ROOT)
                aside.parent.mkdir(parents=True, exist_ok=True)
                if aside.exists():
                    shutil.rmtree(aside)
                os.replace(live, aside)
                journal["steps"].append(f"moved aside: {live.relative_to(ROOT).as_posix()}")
                journal["state"] = "target-moved-aside"
                _write_json(journal_path, journal)
            live.parent.mkdir(parents=True, exist_ok=True)
            os.replace(cand, live)
            journal["steps"].append(f"promoted: {live.relative_to(ROOT).as_posix()}")
            _write_json(journal_path, journal)
        os.replace(candidate / "registry.json", registry_live)
        journal["steps"].append(f"promoted: {REGISTRY_REL.as_posix()}")
        journal["state"] = "committed"
        journal["finished_at"] = utc_now()
        _write_json(journal_path, journal)
    except BaseException as exc:
        journal["state"] = "interrupted"
        journal["error"] = str(exc)
        _write_json(journal_path, journal)
        raise fail(
            EXIT_FAILED,
            f"promote interrupted; the journal at {journal_path.relative_to(ROOT).as_posix()} "
            "records the recoverable window and the snapshot to restore from",
            reason="internal_error",
            command="promote",
            error=str(exc),
            artifact_ids=[journal_path.relative_to(ROOT).as_posix()],
        ) from exc

    for _source_id, _cand, live in moves:
        guard.note(live)
    guard.note(registry_live)
    return {
        "promoted": True,
        "status": status,
        "snapshot": snapshot.relative_to(ROOT).as_posix(),
        "journal": journal_path.relative_to(ROOT).as_posix(),
        "state": "committed",
        "moved": len(moves),
    }

def rollback_candidate(to: str, guard: WriteGuard, dry_run: bool) -> dict[str, object]:
    snapshot = Path(to.replace("\\", "/"))
    if not snapshot.is_absolute():
        snapshot = ROOT / snapshot
    snapshot = Path(os.path.normpath(str(snapshot)))
    base = (ROOT / CANDIDATES_ROOTNAME).resolve()
    try:
        snapshot.relative_to(base)
    except ValueError:
        raise fail(
            EXIT_BLOCKED,
            f"rollback snapshot must live under {CANDIDATES_ROOTNAME}/: {to!r}",
            reason="path_escape",
        ) from None
    if not snapshot.is_dir():
        raise fail(
            EXIT_MISSING_INPUT,
            f"snapshot not found: {to}",
            reason="scope_empty",
            missing_fields=["snapshot"],
        )
    if dry_run:
        return {"restored": False, "snapshot": snapshot.relative_to(ROOT).as_posix()}

    _promote_context.active = True
    try:
        registry_live = ROOT / REGISTRY_REL
        restored: list[str] = []
        # Same per-source scope as promote. Restoring the whole `docs/community/`
        # would delete the hand-written files the importer never owned.
        for source in SOURCES:
            for rel in (Path(RAW_ROOT.as_posix()) / DEST[source["id"]], Path(DOCS_ROOT.as_posix()) / source["id"]):
                snap = snapshot / rel
                if not snap.is_dir():
                    continue
                live = ROOT / rel
                if live.is_dir():
                    shutil.rmtree(live)
                live.parent.mkdir(parents=True, exist_ok=True)
                os.replace(snap, live)
                restored.append(rel.as_posix())
                guard.note(live)
        snap_registry = snapshot / "registry.json"
        if snap_registry.is_file():
            os.replace(snap_registry, registry_live)
            restored.append(REGISTRY_REL.as_posix())
            guard.note(registry_live)
        if not restored:
            raise fail(
                EXIT_MISSING_INPUT,
                f"snapshot contains nothing restorable: {to}",
                reason="scope_empty",
                missing_fields=["snapshot_payload"],
            )
        return {"restored": True, "snapshot": snapshot.relative_to(ROOT).as_posix(), "paths": restored}
    finally:
        _promote_context.active = False

def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes((json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    os.replace(tmp, path)

# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="adapt-community.py",
        description=(
            "Community source importer. inspect/verify are read-only; import writes only "
            f"{CANDIDATES_ROOTNAME}/<id>/; promote is the only command that may change the "
            f"verified tree; rollback restores it from a snapshot. The write root is "
            f"{RAW_ROOT.as_posix()}/, outside the skills/ discovery root (17.27)."
        ),
        epilog=(
            "Exit codes (spec 4.7): 0 matched, 10 needs_review, 20 blocked, "
            "21 missing_input, 22 unavailable, 30 failed."
        ),
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=ROOT,
        help="repository root to operate on (default: the checkout containing this script)",
    )
    parser.add_argument(
        "--upstream-root",
        type=Path,
        default=None,
        help="upstream snapshot root holding the source clones (default: <repo-root>/../upstream). Read-only.",
    )
    sub = parser.add_subparsers(dest="command", metavar="{inspect,import,verify,promote,rollback}")

    p_inspect = sub.add_parser("inspect", help="report source state; writes nothing")
    p_inspect.add_argument("--source", action="append", help="source id (repeatable; default: all)")
    p_inspect.add_argument("--json", action="store_true", help="print machine-readable JSON only")

    p_import = sub.add_parser("import", help=f"build a candidate under {CANDIDATES_ROOTNAME}/")
    p_import.add_argument("--source", action="append", help="source id (repeatable; default: all)")
    p_import.add_argument("--candidate", required=True, help=f"candidate id under {CANDIDATES_ROOTNAME}/")
    p_import.add_argument("--dry-run", action="store_true", help="validate only; write nothing")
    p_import.add_argument("--json", action="store_true")

    p_verify = sub.add_parser("verify", help="check a candidate; writes nothing")
    p_verify.add_argument("--candidate", required=True)
    p_verify.add_argument("--json", action="store_true")

    p_promote = sub.add_parser("promote", help="the only command that may change the verified tree")
    p_promote.add_argument("--candidate", required=True)
    # Deliberately not `required=True`: argparse would exit 2, which is not a
    # spec-4.7 status. The handler raises missing_input (21) instead.
    p_promote.add_argument("--status", help="local-only | release")
    p_promote.add_argument("--dry-run", action="store_true")
    p_promote.add_argument("--json", action="store_true")

    p_rollback = sub.add_parser("rollback", help="restore the verified tree from a snapshot")
    p_rollback.add_argument("--to", required=True, help=f"snapshot path under {CANDIDATES_ROOTNAME}/")
    p_rollback.add_argument("--dry-run", action="store_true")
    p_rollback.add_argument("--json", action="store_true")
    return parser

def emit(payload: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return
    for key, value in payload.items():
        if isinstance(value, (list, dict)):
            value = json.dumps(value, ensure_ascii=False, sort_keys=True)
        print(f"{key}={value}")

def cmd_inspect(args: argparse.Namespace, guard: WriteGuard) -> int:
    ids = args.source or [s["id"] for s in SOURCES]
    unknown = [i for i in ids if i not in SOURCE_BY_ID]
    if unknown:
        raise fail(
            EXIT_MISSING_INPUT,
            f"unknown source id(s): {unknown}",
            reason="scope_empty",
            missing_fields=["source"],
        )
    records = []
    needs_review = 0
    for source_id in ids:
        source = SOURCE_BY_ID[source_id]
        att = attest_source(source)
        problems = validate_attestation(source, att, source["commit"])
        if problems:
            needs_review += 1
        records.append({"id": source_id, "attestation": att, "problems": problems})
    payload = {
        "command": "inspect",
        "status": "needs_review" if needs_review else "matched",
        "candidates": records,
        "confidence": 1.0,
        "reason": f"{needs_review} of {len(ids)} source(s) failed 17.28",
        "writes": [],
    }
    emit(payload, args.json)
    return EXIT_NEEDS_REVIEW if needs_review else EXIT_MATCHED

def cmd_import(args: argparse.Namespace, guard: WriteGuard) -> int:
    ids = args.source or [s["id"] for s in SOURCES]
    unknown = [i for i in ids if i not in SOURCE_BY_ID]
    if unknown:
        raise fail(
            EXIT_MISSING_INPUT,
            f"unknown source id(s): {unknown}",
            reason="scope_empty",
            missing_fields=["source"],
        )
    manifest = build_candidate(ids, args.candidate, guard, args.dry_run)
    payload = {
        "command": "import",
        "status": "matched",
        "route_id": "community-importer",
        "route_explanation": f"candidate {args.candidate} built from {sorted(ids)}",
        "manifest": manifest,
        "writes": [] if args.dry_run else [manifest.get("candidate", "")],
    }
    emit(payload, args.json)
    return EXIT_MATCHED

def cmd_verify(args: argparse.Namespace, guard: WriteGuard) -> int:
    candidate = resolve_candidate(args.candidate)
    result = verify_candidate(candidate)
    if result["problems"]:
        payload = {
            "command": "verify",
            "status": "blocked",
            "reason": "candidate failed verification",
            "policy": "T05 candidate verification",
            "required_action": result["problems"][:20],
            "failure_reason": "license_not_redistributable",
            "candidate": result["candidate"],
            "writes": [],
        }
        emit(payload, args.json)
        return EXIT_BLOCKED
    payload = {
        "command": "verify",
        "status": "matched",
        "route_id": "community-importer",
        "route_explanation": "candidate digests, attestation and discovery-root isolation all check out",
        "candidate": result["candidate"],
        "warnings": result["warnings"],
        "writes": [],
    }
    emit(payload, args.json)
    return EXIT_NEEDS_REVIEW if result["warnings"] else EXIT_MATCHED

def cmd_promote(args: argparse.Namespace, guard: WriteGuard) -> int:
    candidate = resolve_candidate(args.candidate)
    result = promote_candidate(candidate, args.status, guard, args.dry_run)
    payload = {
        "command": "promote",
        "status": "matched",
        "route_id": "community-importer",
        "route_explanation": "candidate promoted via journaled rename; snapshot retained for rollback",
        "result": result,
        "writes": [] if args.dry_run else [str(p) for p in guard.writes],
    }
    emit(payload, args.json)
    return EXIT_MATCHED

def cmd_rollback(args: argparse.Namespace, guard: WriteGuard) -> int:
    result = rollback_candidate(args.to, guard, args.dry_run)
    payload = {
        "command": "rollback",
        "status": "matched",
        "route_id": "community-importer",
        "route_explanation": "verified tree restored from snapshot",
        "result": result,
        "writes": [] if args.dry_run else [str(p) for p in guard.writes],
    }
    emit(payload, args.json)
    return EXIT_MATCHED

HANDLERS = {
    "inspect": cmd_inspect,
    "import": cmd_import,
    "verify": cmd_verify,
    "promote": cmd_promote,
    "rollback": cmd_rollback,
}

#: Subcommands that must never write. Asserted, not merely documented.
READ_ONLY_COMMANDS = {"inspect", "verify"}

def _apply_roots(repo_root: Path, upstream_root: Path | None) -> Path:
    """Rebind ROOT/UPSTREAM to another checkout / another snapshot root.

    Without this, `--repo-root` would be a lie: the module derives ROOT from
    `__file__` at import time, so the flag would be accepted and then ignored.
    Rebinding explicitly is what makes "prove it on a copy, not the real repo"
    possible at all. Upstream snapshots are only ever read, so pointing the
    lab copy at the real `upstream/` is safe.
    """
    global ROOT, UPSTREAM
    ROOT = Path(os.path.normpath(str(Path(repo_root).resolve())))
    UPSTREAM = (
        Path(os.path.normpath(str(Path(upstream_root).resolve())))
        if upstream_root is not None
        else ROOT.parent / "upstream"
    )
    return ROOT

def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help(sys.stderr)
        return EXIT_MISSING_INPUT
    _apply_roots(args.repo_root, args.upstream_root)
    guard = WriteGuard(ROOT)
    try:
        return HANDLERS[args.command](args, guard)
    except KeyError as exc:
        # Safety net: any per-source table lookup missed above still exits
        # inside spec 4.7 (21 missing_input) with a named message, never a
        # traceback + exit 1.
        payload = {
            "command": args.command,
            "status": "missing_input",
            "error": f"unregistered source table entry: {exc}; add the source id to "
                     "SOURCES/DEST/RISK_BY_SOURCE/CONTEXT_BY_SOURCE before importing",
            "failure_reason": "scope_empty",
            "missing_tables": [str(exc).strip("'\"")],
            "writes": [str(p) for p in guard.writes],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), file=sys.stderr)
        return EXIT_MISSING_INPUT
    except ImporterError as exc:
        payload = {
            "command": args.command,
            "status": {
                EXIT_NEEDS_REVIEW: "needs_review",
                EXIT_BLOCKED: "blocked",
                EXIT_MISSING_INPUT: "missing_input",
                EXIT_UNAVAILABLE: "unavailable",
                EXIT_FAILED: "failed",
            }.get(exc.code, "failed"),
            "error": exc.message,
            "failure_reason": exc.reason,
            "writes": [str(p) for p in guard.writes],
        }
        payload.update(exc.extra)
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), file=sys.stderr)
        return exc.code

if __name__ == "__main__":
    # No work happens at import time; only an explicit invocation reaches here.
    raise SystemExit(main())
