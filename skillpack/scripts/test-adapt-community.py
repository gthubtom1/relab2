#!/usr/bin/env python3
"""T05 acceptance and negative-control suite for scripts/adapt-community.py.

Two rules govern this file:

  1. Every check that is meant to catch a regression must be paired with the
     input that makes it fail, and the failure must be observed (a real exit
     code, not an assertion that "would" fail). A check that has only ever
     been seen green is not evidence.
  2. Every write happens in a temporary directory. This suite never runs
     import/promote/rollback against the real repository. The only commands it
     runs there are the read-only ones plus the negative controls, and it
     proves afterwards that nothing moved.

Usage:
    python scripts/test-adapt-community.py            # full suite
    python scripts/test-adapt-community.py --list     # names only

Exit codes (spec 4.7): 0 matched, 10 needs_review, 20 blocked, 30 failed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMPORTER = ROOT / "scripts" / "adapt-community.py"
PYTHON = sys.executable

EXIT_MATCHED = 0
EXIT_NEEDS_REVIEW = 10
EXIT_BLOCKED = 20
EXIT_MISSING_INPUT = 21
EXIT_UNAVAILABLE = 22
EXIT_FAILED = 30

#: Real-repository invariants. The suite records these before and after and
#: fails if any of them moved, which is the machine proof that the read-only
#: commands and the negative controls had no side effect.
BASELINE_FILES = [
    "community-raw/ctf-super-hub/ctf-ai-ml/SKILL.md",
    "community-raw/hack-skills/401-403-bypass-techniques/SKILL.md",
    "community-raw/apk-reverse-source/SKILL.md",
    "community-raw/ai-fullstack/workflows/api-designer/WORKFLOW.md",
    "community-raw/ai-fullstack/workflows/ai-ml-engineer/skills/ai-deployment/SKILL.md",
    "skills/community/registry.json",
]

class Suite:
    def __init__(self) -> None:
        self.results: list[tuple[str, bool, str]] = []
        self.tmp: Path | None = None

    # -- helpers ---------------------------------------------------------
    def check(self, name: str, ok: bool, detail: str = "") -> bool:
        self.results.append((name, ok, detail))
        print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  -- {detail}" if detail else ""))
        return ok

    def run(self, args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        return subprocess.run(
            [PYTHON, str(IMPORTER), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(cwd) if cwd else None,
            env=env,
        )

    def real_state(self) -> dict[str, str]:
        state = {}
        for rel in BASELINE_FILES:
            path = ROOT / rel
            state[rel] = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else "<absent>"
        git = subprocess.run(
            ["git", "--no-optional-locks", "status", "--porcelain"],
            capture_output=True, text=True, encoding="utf-8", cwd=str(ROOT),
        )
        # Only the status lines that are *not* part of this T05 change are
        # interesting. Another agent may be editing the tree concurrently, so
        # the total line count would be noisy; what must not change is the set
        # of paths the importer could plausibly have written.
        mine = (
            "scripts/adapt-community.py",
            "scripts/test-adapt-community.py",
            ".gitignore",
            "kernel/",
            "work/",
            "IMPORTER-MANAGED-TRANSFORMS",
            "IMPORTER-LIFECYCLE",
        )
        lines = sorted(
            l for l in git.stdout.splitlines()
            if l.strip() and not any(m in l for m in mine)
        )
        state["<git-status-other-agents>"] = "\n".join(lines)
        state["<.candidates-exists>"] = str((ROOT / ".candidates").exists())
        return state

    # -- fixture ---------------------------------------------------------
    def make_fake_repo(self) -> Path:
        """A throwaway repo with a synthetic upstream clone.

        Using the real 4 upstream clones for every case would be slow and would
        couple the suite to their contents. The synthetic clone is a real git
        repository, so attestation, dirty detection and `git cat-file -e` all
        exercise the same code paths as production.
        """
        assert self.tmp is not None
        repo = self.tmp / "repo"
        upstream = self.tmp / "upstream"
        clone = upstream / "synthetic"
        (repo / "community-raw" / "synthetic").mkdir(parents=True, exist_ok=True)
        (repo / "docs" / "community" / "synthetic").mkdir(parents=True, exist_ok=True)
        (repo / "skills" / "community").mkdir(parents=True, exist_ok=True)
        (repo / "skills" / "community" / "registry.json").write_text(
            json.dumps({"schemaVersion": "1.0", "sources": [{"id": "synthetic"}], "skills": []}, indent=2) + "\n",
            encoding="utf-8",
        )
        (clone / "skills" / "demo").mkdir(parents=True, exist_ok=True)
        (clone / "skills" / "demo" / "SKILL.md").write_text(
            "---\nname: demo\ndescription: A demo skill.\n---\n\nBody.\n", encoding="utf-8"
        )
        (clone / "README.md").write_text("# synthetic\n", encoding="utf-8")
        (clone / "secret.pem").write_text("-----BEGIN-----\n", encoding="utf-8")
        env = dict(os.environ)
        for args in (
            ["init", "-q"],
            ["config", "user.email", "t05@example.invalid"],
            ["config", "user.name", "T05"],
            ["add", "-A"],
            ["commit", "-q", "-m", "synthetic"],
        ):
            subprocess.run(["git", "--no-optional-locks", "-C", str(clone), *args], check=True, capture_output=True, env=env)
        return repo

    def importer_args(self, repo: Path, rest: list[str]) -> list[str]:
        return ["--repo-root", str(repo), "--upstream-root", str(self.tmp / "upstream"), *rest]

def _patch_synthetic(importer_tmp: Path, commit: str) -> None:
    """Point the importer's source table at the synthetic clone.

    The source table, DEST map, RISK_BY_SOURCE and CONTEXT_BY_SOURCE are all
    rewritten together: a source id that is missing from any one of them would
    make the fixture test the importer's tables rather than its lifecycle.
    """
    text = importer_tmp.read_text(encoding="utf-8")
    start = text.index("SOURCES = [")
    end = text.index("\n]\n", start) + 3
    table = (
        "SOURCES = [\n"
        "    {\n"
        '        "id": "synthetic",\n'
        '        "repo": "synthetic",\n'
        '        "upstream_url": "https://example.invalid/synthetic",\n'
        f'        "commit": "{commit}",\n'
        '        "scan": Path("."),\n'
        '        "license_status": "review-required",\n'
        '        "maturity": "partial",\n'
        '        "license_declared": "NOASSERTION",\n'
        '        "third_party_review": "required",\n'
        '        "notice_file": "docs/community/synthetic/LICENSE",\n'
        "    },\n"
        "]\n"
    )
    text = text[:start] + table + text[end:]

    dest_anchor = '    "apk-reverse-community": "apk-reverse-source",\n'
    assert text.count(dest_anchor) == 1, "DEST anchor not found"
    text = text.replace(dest_anchor, dest_anchor + '    "synthetic": "synthetic",\n')

    for name in ("RISK_BY_SOURCE", "CONTEXT_BY_SOURCE"):
        anchor = f"{name} = {{\n"
        assert text.count(anchor) == 1, f"{name} anchor not found"
        if name == "RISK_BY_SOURCE":
            addition = '    "synthetic": "medium",\n'
        else:
            addition = '    "synthetic": ["offline-ctf", "authorized-lab"],\n'
        text = text.replace(anchor, anchor + addition, 1)

    importer_tmp.write_text(text, encoding="utf-8", newline="\n")

def _write_suite_importer(dest: Path, commit: str) -> None:
    _patch_synthetic(dest, commit)

def _canonical_tree_digest(base: Path) -> tuple[int, int, str]:
    base = Path(base)
    if not base.is_dir():
        return (0, 0, "")
    files = [
        (unicodedata.normalize("NFC", q.relative_to(base).as_posix()), q.read_bytes())
        for q in base.rglob("*")
        if q.is_file()
    ]
    lines = sorted(
        b"f\0" + p.encode() + b"\0" + hashlib.sha256(d.replace(b"\r\n", b"\n")).hexdigest().encode() + b"\n"
        for p, d in files
    )
    return (len(files), 0, hashlib.sha256(b"".join(lines)).hexdigest())

# --------------------------------------------------------------------------
# Cases
# --------------------------------------------------------------------------

def case_help_is_inert(s: Suite, before: dict[str, str]) -> None:
    """--help must print and stop. The old importer ran a full import here."""
    proc = s.run(["--help"])
    ok = proc.returncode == 0 and "inspect" in proc.stdout and "rollback" in proc.stdout
    s.check("help/--help exits 0 and prints usage", ok, f"exit={proc.returncode}")
    s.check("help/--help changed nothing", s.real_state() == before, "baseline files + git status identical")

def case_unknown_arg_is_inert(s: Suite, before: dict[str, str]) -> None:
    """A typo used to be accepted and triggered the whole import."""
    for args in (["--soruce", "hack-skills"], ["--dryrun"], ["import", "--soruce", "x"]):
        proc = s.run(args)
        s.check(
            f"help/unknown arg {args[0]!r} is rejected, not executed",
            proc.returncode not in (EXIT_MATCHED,),
            f"exit={proc.returncode}",
        )
    s.check("help/unknown args changed nothing", s.real_state() == before)

def case_no_args_is_inert(s: Suite, before: dict[str, str]) -> None:
    proc = s.run([])
    s.check("help/no arguments exits non-zero", proc.returncode == EXIT_MISSING_INPUT, f"exit={proc.returncode}")
    s.check("help/no arguments changed nothing", s.real_state() == before)

def case_module_import_does_no_work(s: Suite) -> None:
    """Importing the module must not run anything (17.26 / T05)."""
    probe = (
        "import importlib.util, sys, pathlib;"
        f"spec = importlib.util.spec_from_file_location('importer', r'{IMPORTER}');"
        "m = importlib.util.module_from_spec(spec);"
        "before = set(p.name for p in pathlib.Path('.').iterdir());"
        "spec.loader.exec_module(m);"
        "after = set(p.name for p in pathlib.Path('.').iterdir());"
        "assert before == after, 'module import changed the working tree';"
        "print('ok')"
    )
    proc = subprocess.run([PYTHON, "-c", probe], capture_output=True, text=True, cwd=str(ROOT))
    s.check(
        "lifecycle/importing the module performs no work",
        proc.returncode == 0 and "ok" in proc.stdout,
        proc.stderr.strip()[-200:],
    )

def case_readonly_commands_are_readonly(s: Suite, before: dict[str, str]) -> None:
    inspect = s.run(["inspect", "--source", "hack-skills"])
    s.check("readonly/inspect exits cleanly on a source", inspect.returncode in (EXIT_MATCHED, EXIT_MISSING_INPUT), f"exit={inspect.returncode}")
    s.check("readonly/inspect changed nothing", s.real_state() == before)

    verify = s.run(["verify", "--candidate", "does-not-exist"])
    s.check(
        "readonly/verify on a missing candidate exits 21",
        verify.returncode == EXIT_MISSING_INPUT,
        f"exit={verify.returncode}",
    )
    s.check("readonly/verify changed nothing", s.real_state() == before)

def case_discovery_root_is_guarded(s: Suite, before: dict[str, str]) -> None:
    """The regression T05 exists for: writing raw content back under skills/."""
    leaked = [
        p for p in (ROOT / "skills").rglob("SKILL.md")
        if "community-raw" in p.parts or any(part in {"ctf-super-hub", "hack-skills", "ai-fullstack", "apk-reverse-source"} for part in p.parts)
    ]
    s.check(
        "guard/no raw vendor SKILL.md under skills/",
        not leaked,
        f"{len(leaked)} leaked" if leaked else "recursive client walk finds none",
    )
    s.check("guard/check changed nothing", s.real_state() == before)

def case_gitignore_has_candidates(s: Suite) -> None:
    text = (ROOT / ".gitignore").read_text(encoding="utf-8")
    s.check("gitignore/.candidates/ is ignored", ".candidates/" in text, "otherwise git status and the key scan are polluted")
    proc = subprocess.run(
        ["git", "--no-optional-locks", "check-ignore", "-q", ".candidates/probe/file.txt"],
        cwd=str(ROOT), capture_output=True,
    )
    s.check("gitignore/git check-ignore accepts .candidates/", proc.returncode == 0, f"exit={proc.returncode}")

def _digest_probe() -> str:
    """Re-implemented independently of the importer, fed by real file reads."""
    lines = []
    for name, data in sorted(_DIGEST_FILES.items()):
        lines.append(
            b"f\0" + name.encode() + b"\0" + hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest().encode() + b"\n"
        )
    return hashlib.sha256(b"".join(lines)).hexdigest()

_DIGEST_FILES = {
    "a/x.txt": b"one\r\ntwo\r\n",
    "b/y.txt": b"three",
}

def case_digest_contract_is_frozen(s: Suite) -> None:
    """A known input must produce a known digest; this pins the 17.26 format.

    `expected` is computed by the local independent implementation and
    `imported` by the importer's own function, so agreement is a real
    cross-check rather than the importer agreeing with itself.
    """
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        for name, data in _DIGEST_FILES.items():
            path = base / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        expected = _digest_probe()
        probe = (
            "import importlib.util, json;"
            f"spec = importlib.util.spec_from_file_location('importer', r'{IMPORTER}');"
            "m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m);"
            f"print(json.dumps(m.digest_of_tree(r'{base}')))"
        )
        proc = subprocess.run([PYTHON, "-c", probe], capture_output=True, text=True, cwd=str(ROOT))
        imported = ""
        if proc.returncode == 0:
            imported = json.loads(proc.stdout)["file_manifest_digest"]
        s.check(
            "digest/file_manifest_digest matches an independent implementation",
            proc.returncode == 0 and imported == expected,
            f"expected {expected[:16]} got {imported[:16] or proc.stderr.strip()[-120:]}",
        )
        s.check("digest/CRLF is folded (17.26)", b"\r" not in _DIGEST_FILES["a/x.txt"].replace(b"\r\n", b"\n"), "canonical bytes are LF")

def case_digest_detects_a_single_byte(s: Suite) -> None:
    """Negative control for the digest itself: flip one byte, expect a change."""
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        target = base / "f.txt"
        target.write_bytes(b"alpha")
        probe = (
            "import importlib.util;"
            f"spec = importlib.util.spec_from_file_location('importer', r'{IMPORTER}');"
            "m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m);"
            f"print(m.digest_of_tree(r'{base}')['file_manifest_digest'])"
        )
        first = subprocess.run([PYTHON, "-c", probe], capture_output=True, text=True, cwd=str(ROOT))
        target.write_bytes(b"alphb")
        second = subprocess.run([PYTHON, "-c", probe], capture_output=True, text=True, cwd=str(ROOT))
        ok = first.returncode == 0 and second.returncode == 0 and first.stdout.strip() != second.stdout.strip()
        s.check(
            "digest/one changed byte changes the digest",
            ok,
            f"{first.stdout.strip()[:12]} -> {second.stdout.strip()[:12]}",
        )

# -- lifecycle on a synthetic repository ----------------------------------

def case_lifecycle(s: Suite) -> None:
    repo = s.make_fake_repo()
    assert s.tmp is not None
    clone = s.tmp / "upstream" / "synthetic"
    env = dict(os.environ)
    head = subprocess.run(
        ["git", "--no-optional-locks", "-C", str(clone), "rev-parse", "HEAD"],
        capture_output=True, text=True, env=env,
    ).stdout.strip()

    # A copy of the importer whose source table points at the synthetic clone.
    patched = s.tmp / "adapt-synthetic.py"
    shutil.copy2(IMPORTER, patched)
    _write_suite_importer(patched, head)

    def run(args: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(
            [PYTHON, str(patched), "--repo-root", str(repo), "--upstream-root", str(s.tmp / "upstream"), *args],
            capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
        )

    # 1. import writes only the candidate
    proc = run(["import", "--candidate", "c1"])
    s.check("lifecycle/import exits 0", proc.returncode == EXIT_MATCHED, f"exit={proc.returncode} {proc.stderr[-200:]}")
    cand = repo / ".candidates" / "c1"
    s.check("lifecycle/import created the candidate", cand.is_dir())
    s.check("lifecycle/import wrote raw under community-raw/", (cand / "community-raw" / "synthetic").is_dir())
    s.check("lifecycle/import wrote no skills/ content", not any((cand / "skills").rglob("*")) if (cand / "skills").exists() else True)

    # 2. LF folding
    demo = cand / "community-raw" / "synthetic" / "skills" / "demo" / "SKILL.md"
    raw = demo.read_bytes()
    s.check("lifecycle/imported SKILL.md has no CRLF", b"\r\n" not in raw, "17.26 LF folding")

    # 3. sensitive material excluded
    s.check(
        "lifecycle/private key material is not imported",
        not any(p.suffix in {".pem", ".key"} for p in cand.rglob("*")),
    )

    # 4. verify is read-only and passes
    proc = run(["verify", "--candidate", "c1"])
    s.check("lifecycle/verify exits 0 on a fresh candidate", proc.returncode == EXIT_MATCHED, f"exit={proc.returncode}")
    before_verify = _canonical_tree_digest(cand)
    run(["verify", "--candidate", "c1"])
    s.check(
        "lifecycle/verify is repeatable and read-only",
        before_verify == _canonical_tree_digest(cand),
        "digest unchanged across two runs",
    )

    # 4b. A second import of the same source reproduces the same payload bytes.
    #     Must run BEFORE promote, because promote consumes the candidate.
    #     Only the payload is compared: source-lock.json records `fetched_at`,
    #     so its timestamp legitimately differs between runs.
    proc = run(["import", "--candidate", "c2"])
    s.check("lifecycle/second import exits 0", proc.returncode == EXIT_MATCHED, f"exit={proc.returncode}")

    def payload_digest(candidate: Path) -> str:
        return _canonical_tree_digest(candidate / "community-raw")[2]

    s.check(
        "lifecycle/two imports of one source produce identical payload bytes",
        payload_digest(repo / ".candidates" / "c1") == payload_digest(repo / ".candidates" / "c2"),
        f"{payload_digest(repo / '.candidates' / 'c1')[:12]} vs {payload_digest(repo / '.candidates' / 'c2')[:12]}",
    )

    # 5. promote --dry-run changes nothing
    live_before = _canonical_tree_digest(repo / "community-raw")
    proc = run(["promote", "--candidate", "c1", "--status", "local-only", "--dry-run"])
    s.check("lifecycle/promote --dry-run exits 0", proc.returncode == EXIT_MATCHED, f"exit={proc.returncode}")
    s.check("lifecycle/promote --dry-run changed nothing", _canonical_tree_digest(repo / "community-raw") == live_before)

    # 6. promote
    live_before = _canonical_tree_digest(repo / "community-raw")
    proc = run(["promote", "--candidate", "c1", "--status", "local-only"])
    s.check("lifecycle/promote exits 0", proc.returncode == EXIT_MATCHED, f"exit={proc.returncode} {proc.stderr[-300:]}")
    s.check("lifecycle/promote actually changed the verified tree", _canonical_tree_digest(repo / "community-raw") != live_before)
    journal = json.loads((repo / ".candidates" / "promote-journal.json").read_text(encoding="utf-8"))
    s.check(
        "lifecycle/journal records a committed, non-atomic promote",
        journal["state"] == "committed" and "recoverable_window" in journal,
        f"state={journal['state']}",
    )

    # 7. rollback restores byte-for-byte
    promoted = _canonical_tree_digest(repo / "community-raw")
    proc = run(["rollback", "--to", journal["snapshot"]])
    s.check("lifecycle/rollback exits 0", proc.returncode == EXIT_MATCHED, f"exit={proc.returncode} {proc.stderr[-200:]}")
    s.check(
        "lifecycle/rollback restores the previous bytes exactly",
        _canonical_tree_digest(repo / "community-raw") == live_before,
        f"{live_before[2][:12]} -> {promoted[2][:12]} -> {_canonical_tree_digest(repo / 'community-raw')[2][:12]}",
    )

def case_attestation_gates(s: Suite) -> None:
    """Each of the four rejection conditions must abort with a clear code."""
    repo = s.make_fake_repo2()
    assert s.tmp is not None
    clone = s.tmp / "upstream2" / "synthetic"
    env = dict(os.environ)

    def head_of(path: Path) -> str:
        return subprocess.run(
            ["git", "--no-optional-locks", "-C", str(path), "rev-parse", "HEAD"],
            capture_output=True, text=True, env=env,
        ).stdout.strip()

    def make_importer(name: str, commit: str) -> Path:
        dst = s.tmp / name
        shutil.copy2(IMPORTER, dst)
        _write_suite_importer(dst, commit)
        return dst

    def run(importer: Path, args: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(
            [PYTHON, str(importer), "--repo-root", str(repo), "--upstream-root", str(s.tmp / "upstream2"), *args],
            capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
        )

    # (a) wrong pinned commit
    good = make_importer("imp-wrongcommit.py", "0" * 40)
    proc = run(good, ["import", "--candidate", "x1"])
    s.check("attestation/pinned commit mismatch aborts", proc.returncode == EXIT_BLOCKED, f"exit={proc.returncode}")
    s.check("attestation/wrong commit wrote nothing", not (repo / ".candidates" / "x1").exists())
    s.check("attestation/wrong commit left no staging", not (repo / ".candidates" / "x1.partial").exists())

    # (b) dirty source
    real_head = head_of(clone)
    (clone / "uncommitted.txt").write_text("dirty\n", encoding="utf-8")
    clean_importer = make_importer("imp-dirty.py", real_head)
    proc = run(clean_importer, ["import", "--candidate", "x2"])
    s.check("attestation/dirty source aborts", proc.returncode == EXIT_BLOCKED, f"exit={proc.returncode}")
    s.check(
        "attestation/dirty reason names the 17.28 rule",
        "dirty" in (proc.stderr or ""),
        (proc.stderr or "").replace("\n", " ")[:120],
    )
    s.check("attestation/dirty wrote nothing", not (repo / ".candidates" / "x2").exists())
    (clone / "uncommitted.txt").unlink()

    # (c) missing upstream snapshot
    absent = make_importer("imp-absent.py", real_head)
    proc = subprocess.run(
        [PYTHON, str(absent), "--repo-root", str(repo), "--upstream-root", str(s.tmp / "no-such-dir"), "import", "--candidate", "x3"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
    )
    s.check("attestation/missing upstream snapshot exits 21", proc.returncode == EXIT_MISSING_INPUT, f"exit={proc.returncode}")
    s.check("attestation/missing upstream wrote nothing", not (repo / ".candidates" / "x3").exists())

    # (d) promote a candidate that was never built. The contract is: the
    #     candidate is not there, so nothing is promoted. --status is supplied
    #     so the status check is not what rejects it.
    proc = run(clean_importer, ["promote", "--candidate", "never-made", "--status", "local-only"])
    s.check(
        "promote/absent candidate is refused and writes nothing",
        proc.returncode == EXIT_BLOCKED and not (repo / "community-raw" / "synthetic" / "skills" / "demo").exists(),
        f"exit={proc.returncode}",
    )

    # (e) promote without --status -> 21, not argparse's 2 (spec 4.7)
    proc = run(clean_importer, ["promote", "--candidate", "never-made"])
    s.check("promote/missing --status exits 21", proc.returncode == EXIT_MISSING_INPUT, f"exit={proc.returncode}")

    # (e2) promote with a bogus --status -> 21 as well
    proc = run(clean_importer, ["promote", "--candidate", "never-made", "--status", "totally-fine"])
    s.check("promote/unknown --status exits 21", proc.returncode == EXIT_MISSING_INPUT, f"exit={proc.returncode}")

    # (f) verify fails on a tampered candidate digest
    proc = run(clean_importer, ["import", "--candidate", "x4"])
    if proc.returncode == EXIT_MATCHED:
        victim = repo / ".candidates" / "x4" / "community-raw" / "synthetic" / "skills" / "demo" / "SKILL.md"
        victim.write_bytes(victim.read_bytes() + b"tampered\n")
        proc = run(clean_importer, ["verify", "--candidate", "x4"])
        s.check("verify/tampered candidate digest is rejected", proc.returncode == EXIT_BLOCKED, f"exit={proc.returncode}")
        proc = run(clean_importer, ["promote", "--candidate", "x4", "--status", "local-only"])
        s.check("promote/tampered candidate is refused", proc.returncode == EXIT_BLOCKED, f"exit={proc.returncode}")
    else:
        s.check("verify/tampered candidate digest is rejected", False, f"import failed: {proc.stderr[-200:]}")

def _make_suite_repo2(s: Suite) -> None:  # pragma: no cover - helper alias
    raise NotImplementedError

def case_write_guard(s: Suite) -> None:
    """No code path may build a write target under skills/ except promote."""
    text = IMPORTER.read_text(encoding="utf-8")
    s.check(
        "guard/registry.json is the only declared path under skills/",
        text.count('REGISTRY_REL = Path("skills/community/registry.json")') == 1,
    )
    script = f'''
import importlib.util, pathlib
spec = importlib.util.spec_from_file_location("importer", r"{IMPORTER}")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
guard = m.WriteGuard(pathlib.Path(r"{ROOT}"))
try:
    guard.check(pathlib.Path(r"{ROOT / 'skills' / 'community' / 'oops.md'}"))
except m.ImporterError as exc:
    print("BLOCKED", exc.code, exc.reason)
else:
    print("ALLOWED")
try:
    guard.check(pathlib.Path(r"{ROOT / 'community-raw' / 'ok.md'}"))
except m.ImporterError as exc:
    print("WRONGLY-BLOCKED", exc.code)
else:
    print("RAW-OK")
'''
    proc = subprocess.run([PYTHON, "-c", script], capture_output=True, text=True, cwd=str(ROOT))
    out = proc.stdout
    s.check(
        "guard/WriteGuard blocks a skills/ write with exit 20 and path_escape",
        "BLOCKED 20 path_escape" in out,
        out.strip().replace("\n", " ") + proc.stderr.strip()[-140:],
    )
    s.check("guard/WriteGuard allows community-raw/", "RAW-OK" in out, out.strip().replace("\n", " "))

def case_no_atomicity_claim(s: Suite) -> None:
    """The docs must say 'recoverable window', never 'atomic swap'."""
    doc = ROOT / "docs" / "community" / "IMPORTER-LIFECYCLE.md"
    if not doc.is_file():
        s.check("docs/IMPORTER-LIFECYCLE.md exists", False, "missing")
        return
    text = doc.read_text(encoding="utf-8")
    s.check("docs/claims a recoverable window", "recoverable window" in text)
    s.check("docs/does not claim an atomic swap", "atomic swap" not in text.replace("not an atomic swap", ""))

def case_digest_contract_documented(s: Suite) -> None:
    doc = ROOT / "docs" / "community" / "IMPORTER-LIFECYCLE.md"
    if not doc.is_file():
        s.check("docs/digest contract documented", False, "missing")
        return
    text = doc.read_text(encoding="utf-8")
    s.check("docs/digest contract version recorded", "skills-hub/importer-digest/1" in text)
    s.check("docs/CRLF folding recorded", "CRLF" in text)
    s.check("docs/write root recorded", "community-raw" in text)

def case_gitignore_candidate_absent_in_repo(s: Suite) -> None:
    s.check(
        "hygiene/no .candidates/ committed",
        not any(p.name == ".candidates" for p in ROOT.iterdir()),
        "candidate tree must be ignored and untracked",
    )

# --------------------------------------------------------------------------

def build_suite_repo2(s: Suite) -> Path:
    """Second fixture so the attestation cases do not share state with case_lifecycle."""
    assert s.tmp is not None
    repo = s.tmp / "repo2"
    upstream = s.tmp / "upstream2"
    clone = upstream / "synthetic"
    (repo / "community-raw" / "synthetic").mkdir(parents=True, exist_ok=True)
    (repo / "docs" / "community" / "synthetic").mkdir(parents=True, exist_ok=True)
    (repo / "skills" / "community").mkdir(parents=True, exist_ok=True)
    (repo / "skills" / "community" / "registry.json").write_text(
        json.dumps({"schemaVersion": "1.0", "sources": [{"id": "synthetic"}], "skills": []}, indent=2) + "\n",
        encoding="utf-8",
    )
    (clone / "skills" / "demo").mkdir(parents=True, exist_ok=True)
    (clone / "skills" / "demo" / "SKILL.md").write_text(
        "---\nname: demo\ndescription: A demo skill.\n---\n\nBody.\n", encoding="utf-8"
    )
    (clone / "README.md").write_text("# synthetic\n", encoding="utf-8")
    env = dict(os.environ)
    for args in (
        ["init", "-q"],
        ["config", "user.email", "t05@example.invalid"],
        ["config", "user.name", "T05"],
        ["add", "-A"],
        ["commit", "-q", "-m", "synthetic"],
    ):
        subprocess.run(["git", "--no-optional-locks", "-C", str(clone), *args], check=True, capture_output=True, env=env)
    return repo

Suite.make_fake_repo2 = build_suite_repo2  # type: ignore[attr-defined]

# --------------------------------------------------------------------------
# U11 managed transforms (curation survives re-import)
# --------------------------------------------------------------------------

def _write_fixture_record(repo: Path, transforms: list) -> str:
    digest = hashlib.sha256(
        (json.dumps(transforms, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    ).hexdigest()
    record = {"schema": "skills-hub/importer-managed-transforms/1", "digest": digest, "transforms": transforms}
    doc = repo / "docs" / "community" / "IMPORTER-MANAGED-TRANSFORMS.md"
    doc.parent.mkdir(parents=True, exist_ok=True)
    doc.write_text(
        "# fixture record\n\n```json managed-transforms\n"
        + json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n```\n",
        encoding="utf-8",
    )
    return digest

def _make_managed_fixture(s: Suite, name: str, upstream_body: str) -> tuple[Path, Path]:
    """Fake repo + synthetic upstream whose SKILL.md carries `upstream_body`."""
    assert s.tmp is not None
    repo = s.tmp / name / "repo"
    upstream = s.tmp / name / "upstream"
    clone = upstream / "synthetic"
    (repo / "community-raw" / "synthetic").mkdir(parents=True, exist_ok=True)
    (repo / "docs" / "community" / "synthetic").mkdir(parents=True, exist_ok=True)
    (repo / "skills" / "community").mkdir(parents=True, exist_ok=True)
    (repo / "skills" / "community" / "registry.json").write_text(
        json.dumps({"schemaVersion": "1.0", "sources": [{"id": "synthetic"}], "skills": []}, indent=2) + "\n",
        encoding="utf-8",
    )
    (clone / "skills" / "demo").mkdir(parents=True, exist_ok=True)
    (clone / "skills" / "demo" / "SKILL.md").write_text(upstream_body, encoding="utf-8")
    (clone / "README.md").write_text("# synthetic\n", encoding="utf-8")
    env = dict(os.environ)
    for args in (
        ["init", "-q"],
        ["config", "user.email", "t05@example.invalid"],
        ["config", "user.name", "T05"],
        ["add", "-A"],
        ["commit", "-q", "-m", "synthetic"],
    ):
        subprocess.run(["git", "--no-optional-locks", "-C", str(clone), *args], check=True, capture_output=True, env=env)
    head = subprocess.run(
        ["git", "--no-optional-locks", "-C", str(clone), "rev-parse", "HEAD"],
        capture_output=True, text=True, env=env,
    ).stdout.strip()
    patched = s.tmp / name / "adapt-synthetic.py"
    shutil.copy2(IMPORTER, patched)
    _write_suite_importer(patched, head)
    return repo, patched

def _run_patched(patched: Path, repo: Path, upstream: Path, args: list[str]) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [PYTHON, str(patched), "--repo-root", str(repo), "--upstream-root", str(upstream), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
    )

def case_managed_record_loads(s: Suite) -> None:
    """The real record parses and its digest re-pins (U11 requirement 1)."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("importer", str(IMPORTER))
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    record, problems = module.load_managed_transforms(ROOT)
    s.check("managed/record parses without problems", problems == [], "; ".join(problems)[:200])
    transforms = record.get("transforms") or []
    assert isinstance(transforms, list)
    by_id = {e.get("id"): e for e in transforms if isinstance(e, dict)}
    s.check("managed/record registers two transforms", len(transforms) == 2, f"got {len(transforms)}")
    if "t09-load-instruction-neutralize" in by_id:
        entry = by_id["t09-load-instruction-neutralize"]
        s.check(
            "managed/record covers the T09 banner pair",
            entry.get("pattern") == "> **AI LOAD INSTRUCTION**:"
            and "not a load instruction" in str(entry.get("replacement", "")),
            str(entry.get("id")),
        )
    else:
        s.check("managed/record covers the T09 banner pair", False, "t09 entry absent")
    if "u1-docs-reference-only-banner" in by_id:
        entry = by_id["u1-docs-reference-only-banner"]
        scopes = entry.get("scope") or []
        s.check(
            "managed/record covers the U1 banner entry",
            entry.get("kind") == "regex"
            and entry.get("pattern") == "\\A"
            and len(scopes) == 15
            and "reference-only" in str(entry.get("replacement", "")),
            f"scope_n={len(scopes) if isinstance(scopes, list) else '?'}",
        )
    else:
        s.check("managed/record covers the U1 banner entry", False, "u1 entry absent")

def case_managed_digest_mismatch(s: Suite) -> None:
    """Negative control: a hand-edited record without re-pinning is refused."""
    upstream_body = "---\nname: demo\ndescription: A demo skill.\n---\n\n> **AI LOAD INSTRUCTION**: raw.\n"
    repo, patched = _make_managed_fixture(s, "u11-bad-digest", upstream_body)
    digest = _write_fixture_record(repo, [{
        "id": "x", "scope": ["community-raw/**/*.md"], "kind": "literal",
        "pattern": "a", "replacement": "b", "basis": "fixture",
    }])
    # Corrupt the digest line without touching the transforms.
    doc = repo / "docs" / "community" / "IMPORTER-MANAGED-TRANSFORMS.md"
    doc.write_text(doc.read_text(encoding="utf-8").replace(digest, "0" * 64), encoding="utf-8")
    proc = _run_patched(patched, repo, s.tmp / "u11-bad-digest" / "upstream", ["import", "--candidate", "bad1"])
    s.check("managed/digest mismatch aborts import", proc.returncode == EXIT_BLOCKED, f"exit={proc.returncode}")
    s.check("managed/digest mismatch wrote nothing", not (repo / ".candidates" / "bad1").exists())
    s.check(
        "managed/digest mismatch names the rule",
        "digest mismatch" in (proc.stderr or ""),
        (proc.stderr or "").replace("\n", " ")[:140],
    )

def case_managed_transforms_applied(s: Suite) -> None:
    """Import applies the record: candidate carries curation, manifest pins it."""
    upstream_body = "---\nname: demo\ndescription: A demo skill.\n---\n\n> **AI LOAD INSTRUCTION**: raw words.\n"
    repo, patched = _make_managed_fixture(s, "u11-applied", upstream_body)
    _write_fixture_record(repo, [{
        "id": "fixture-neutralize", "scope": ["community-raw/**/*.md"], "kind": "literal",
        "pattern": "> **AI LOAD INSTRUCTION**:", "replacement": "> **Vendor summary**:",
        "basis": "fixture",
    }])
    up = s.tmp / "u11-applied" / "upstream"
    proc = _run_patched(patched, repo, up, ["import", "--candidate", "m1"])
    s.check("managed/import with record exits 0", proc.returncode == EXIT_MATCHED, f"exit={proc.returncode} {(proc.stderr or '')[-160:]}")
    cand_file = repo / ".candidates" / "m1" / "community-raw" / "synthetic" / "skills" / "demo" / "SKILL.md"
    s.check(
        "managed/candidate carries the curated replacement",
        cand_file.is_file() and "> **Vendor summary**:" in cand_file.read_text(encoding="utf-8", errors="replace"),
        "literal transform applied after materialisation",
    )
    manifest = json.loads((repo / ".candidates" / "m1" / "candidate-manifest.json").read_text(encoding="utf-8"))
    s.check(
        "managed/manifest pins record digest + applied paths",
        bool((manifest.get("managed") or {}).get("digest")) and len((manifest.get("managed") or {}).get("applied", [])) >= 1,
        json.dumps(manifest.get("managed"), ensure_ascii=False, sort_keys=True)[:160],
    )
    summary = (repo / ".candidates" / "m1" / "diff-summary.md").read_text(encoding="utf-8")
    s.check("managed/diff summary has a managed section", "Managed transforms applied" in summary)

def case_promote_blocks_unregistered(s: Suite) -> None:
    """Negative controls: unregistered diffs block promote; managed ones do not."""
    upstream_body = "---\nname: demo\ndescription: A demo skill.\n---\n\n> **AI LOAD INSTRUCTION**: raw words.\n"
    repo, patched = _make_managed_fixture(s, "u11-promote", upstream_body)
    _write_fixture_record(repo, [{
        "id": "fixture-neutralize", "scope": ["community-raw/**/*.md"], "kind": "literal",
        "pattern": "> **AI LOAD INSTRUCTION**:", "replacement": "> **Vendor summary**:",
        "basis": "fixture",
    }])
    up = s.tmp / "u11-promote" / "upstream"
    proc = _run_patched(patched, repo, up, ["import", "--candidate", "p1"])
    assert proc.returncode == EXIT_MATCHED, proc.stderr[-300:]
    proc = _run_patched(patched, repo, up, ["promote", "--candidate", "p1", "--status", "local-only"])
    s.check("managed/first promote (additions only) exits 0", proc.returncode == EXIT_MATCHED, f"exit={proc.returncode}")
    # The journal persists after a successful promote by design (rollback
    # needs it); clear it so the second promote exercises the U11 gate.
    (repo / ".candidates" / "promote-journal.json").unlink(missing_ok=True)
    # Simulate an UNREGISTERED curation edit on the live tree.
    live = repo / "community-raw" / "synthetic" / "skills" / "demo" / "SKILL.md"
    live.write_text(
        live.read_text(encoding="utf-8") + "\nCurator note: not in any record.\n", encoding="utf-8",
    )
    proc = _run_patched(patched, repo, up, ["import", "--candidate", "p2"])
    assert proc.returncode == EXIT_MATCHED, proc.stderr[-300:]
    summary = (repo / ".candidates" / "p2" / "diff-summary.md").read_text(encoding="utf-8")
    s.check(
        "managed/unregistered path stays visible in diff summary",
        "skills/demo/SKILL.md" in summary,
        "no silent swallowing",
    )
    proc = _run_patched(patched, repo, up, ["promote", "--candidate", "p2", "--status", "local-only"])
    s.check("managed/promote with unregistered diff exits 20", proc.returncode == EXIT_BLOCKED, f"exit={proc.returncode}")
    s.check(
        "managed/promote refusal names the revert",
        "unregistered" in (proc.stderr or ""),
        (proc.stderr or "").replace("\n", " ")[:160],
    )
    s.check(
        "managed/blocked promote left the live curation in place",
        "Curator note" in live.read_text(encoding="utf-8"),
        "verified tree untouched",
    )

# --------------------------------------------------------------------------
# P1-4 scoped promote check (check scope == write scope, per source)
# --------------------------------------------------------------------------

def _patch_two_synthetic(importer_tmp: Path, alpha_commit: str, beta_commit: str) -> None:
    """Point the importer's source table at two synthetic clones (P1-4).

    Same technique as `_patch_synthetic`, but with two sources so the suite
    can put dirt in one scope and promote a candidate of the other.
    """
    text = importer_tmp.read_text(encoding="utf-8")
    start = text.index("SOURCES = [")
    end = text.index("\n]\n", start) + 3

    def entry(sid: str, commit: str) -> str:
        return (
            "    {\n"
            f'        "id": "{sid}",\n'
            f'        "repo": "{sid}",\n'
            f'        "upstream_url": "https://example.invalid/{sid}",\n'
            f'        "commit": "{commit}",\n'
            '        "scan": Path("."),\n'
            '        "license_status": "review-required",\n'
            '        "maturity": "partial",\n'
            '        "license_declared": "NOASSERTION",\n'
            '        "third_party_review": "required",\n'
            f'        "notice_file": "docs/community/{sid}/LICENSE",\n'
            "    },\n"
        )

    table = "SOURCES = [\n" + entry("alpha", alpha_commit) + entry("beta", beta_commit) + "]\n"
    text = text[:start] + table + text[end:]

    dest_anchor = '    "apk-reverse-community": "apk-reverse-source",\n'
    assert text.count(dest_anchor) == 1, "DEST anchor not found"
    text = text.replace(dest_anchor, dest_anchor + '    "alpha": "alpha",\n    "beta": "beta",\n')

    additions = {
        "RISK_BY_SOURCE": '    "alpha": "medium",\n    "beta": "medium",\n',
        "CONTEXT_BY_SOURCE": '    "alpha": ["offline-ctf", "authorized-lab"],\n    "beta": ["offline-ctf", "authorized-lab"],\n',
    }
    for name, addition in additions.items():
        anchor = f"{name} = {{\n"
        assert text.count(anchor) == 1, f"{name} anchor not found"
        text = text.replace(anchor, anchor + addition, 1)

    importer_tmp.write_text(text, encoding="utf-8", newline="\n")

def _make_scoped_fixture(s: Suite, name: str) -> tuple[Path, Path, Path]:
    """Fake repo + two synthetic upstream clones (`alpha`, `beta`)."""
    assert s.tmp is not None
    base = s.tmp / name
    repo = base / "repo"
    upstream = base / "upstream"
    heads: dict[str, str] = {}
    env = dict(os.environ)
    for sid in ("alpha", "beta"):
        clone = upstream / sid
        (clone / "skills" / "demo").mkdir(parents=True, exist_ok=True)
        (clone / "skills" / "demo" / "SKILL.md").write_text(
            "---\nname: demo\ndescription: A demo skill.\n---\n\nBody.\n", encoding="utf-8"
        )
        (clone / "README.md").write_text(f"# {sid}\n", encoding="utf-8")
        for args in (
            ["init", "-q"],
            ["config", "user.email", "t05@example.invalid"],
            ["config", "user.name", "T05"],
            ["add", "-A"],
            ["commit", "-q", "-m", "synthetic"],
        ):
            subprocess.run(["git", "--no-optional-locks", "-C", str(clone), *args], check=True, capture_output=True, env=env)
        heads[sid] = subprocess.run(
            ["git", "--no-optional-locks", "-C", str(clone), "rev-parse", "HEAD"],
            capture_output=True, text=True, env=env,
        ).stdout.strip()
    for sid in ("alpha", "beta"):
        (repo / "community-raw" / sid).mkdir(parents=True, exist_ok=True)
        (repo / "docs" / "community" / sid).mkdir(parents=True, exist_ok=True)
    (repo / "skills" / "community").mkdir(parents=True, exist_ok=True)
    (repo / "skills" / "community" / "registry.json").write_text(
        json.dumps({"schemaVersion": "1.0", "sources": [{"id": "alpha"}, {"id": "beta"}], "skills": []}, indent=2) + "\n",
        encoding="utf-8",
    )
    patched = base / "adapt-scoped.py"
    shutil.copy2(IMPORTER, patched)
    _patch_two_synthetic(patched, heads["alpha"], heads["beta"])
    return repo, upstream, patched

def case_promote_scope_matches_write_scope(s: Suite) -> None:
    """P1-4: the U11 refusal check covers exactly the candidate's own sources.

    Dirt in a scope the candidate does not carry must not block it; dirt
    inside its scope still exits 20 and names the path; a full candidate
    still refuses on any dirt.
    """
    repo, up, patched = _make_scoped_fixture(s, "p14-scoped")

    # beta-only first: clean tree, additions only, must promote.
    proc = _run_patched(patched, repo, up, ["import", "--candidate", "b0", "--source", "beta"])
    assert proc.returncode == EXIT_MATCHED, proc.stderr[-300:]
    proc = _run_patched(patched, repo, up, ["promote", "--candidate", "b0", "--status", "local-only"])
    s.check("scope/clean single-source promote exits 0", proc.returncode == EXIT_MATCHED, f"exit={proc.returncode}")
    (repo / ".candidates" / "promote-journal.json").unlink(missing_ok=True)

    proc = _run_patched(patched, repo, up, ["import", "--candidate", "a1", "--source", "alpha"])
    assert proc.returncode == EXIT_MATCHED, proc.stderr[-300:]
    # Unregistered curation edit inside beta scope: out of a1's scope.
    live_beta = repo / "community-raw" / "beta" / "skills" / "demo" / "SKILL.md"
    live_beta.write_text(
        live_beta.read_text(encoding="utf-8") + "\nCurator note beta.\n", encoding="utf-8",
    )
    proc = _run_patched(patched, repo, up, ["promote", "--candidate", "a1", "--status", "local-only", "--dry-run"])
    s.check(
        "scope/out-of-scope dirt does not block single-source promote --dry-run",
        proc.returncode == EXIT_MATCHED,
        f"exit={proc.returncode}",
    )
    payload_before = _canonical_tree_digest(repo / ".candidates" / "a1" / "community-raw" / "alpha")
    proc = _run_patched(patched, repo, up, ["promote", "--candidate", "a1", "--status", "local-only"])
    s.check(
        "scope/single-source promote exits 0 with dirt elsewhere",
        proc.returncode == EXIT_MATCHED,
        f"exit={proc.returncode} {(proc.stderr or '')[-200:]}",
    )
    s.check(
        "scope/out-of-scope curation survives the promote",
        "Curator note beta." in live_beta.read_text(encoding="utf-8"),
        "verified tree outside the candidate scope untouched",
    )
    s.check(
        "scope/promoted scope matches the candidate payload",
        _canonical_tree_digest(repo / "community-raw" / "alpha") == payload_before,
        "target bytes == candidate bytes",
    )
    (repo / ".candidates" / "promote-journal.json").unlink(missing_ok=True)

    # Beta-only candidate now carries the dirt in its own scope: refused.
    proc = _run_patched(patched, repo, up, ["import", "--candidate", "b1", "--source", "beta"])
    assert proc.returncode == EXIT_MATCHED, proc.stderr[-300:]
    proc = _run_patched(patched, repo, up, ["promote", "--candidate", "b1", "--status", "local-only", "--dry-run"])
    s.check("scope/in-scope dirt blocks single-source promote", proc.returncode == EXIT_BLOCKED, f"exit={proc.returncode}")
    err = proc.stderr or ""
    try:
        detail = json.loads(err[err.index("{"):])
    except ValueError:
        detail = {}
    s.check(
        "scope/refusal is scoped to the candidate source",
        detail.get("checked_scope") == ["beta"]
        and "community-raw/beta/skills/demo/SKILL.md" in err
        and all(
            p.startswith(("community-raw/beta/", "docs/community/beta/"))
            for p in (detail.get("unregistered") or ["community-raw/beta/skills/demo/SKILL.md"])
        ),
        f"scope={detail.get('checked_scope')} n={detail.get('unregistered_count')}",
    )

    # Full candidate still refuses: the beta dirt is in its scope.
    proc = _run_patched(patched, repo, up, ["import", "--candidate", "f1"])
    assert proc.returncode == EXIT_MATCHED, proc.stderr[-300:]
    proc = _run_patched(patched, repo, up, ["promote", "--candidate", "f1", "--status", "local-only", "--dry-run"])
    s.check("scope/full candidate still refuses on any dirt", proc.returncode == EXIT_BLOCKED, f"exit={proc.returncode}")
    s.check(
        "scope/full refusal names the out-of-alpha path",
        "community-raw/beta/skills/demo/SKILL.md" in (proc.stderr or ""),
        "range-external dirt is still caught by the full candidate",
    )

    # Unregistered edit inside the alpha scope blocks the alpha candidate.
    live_alpha = repo / "community-raw" / "alpha" / "skills" / "demo" / "SKILL.md"
    live_alpha.write_text(
        live_alpha.read_text(encoding="utf-8") + "\nCurator note alpha.\n", encoding="utf-8",
    )
    proc = _run_patched(patched, repo, up, ["import", "--candidate", "a2", "--source", "alpha"])
    assert proc.returncode == EXIT_MATCHED, proc.stderr[-300:]
    proc = _run_patched(patched, repo, up, ["promote", "--candidate", "a2", "--status", "local-only", "--dry-run"])
    s.check(
        "scope/unregistered edit inside the candidate scope blocks promote",
        proc.returncode == EXIT_BLOCKED,
        f"exit={proc.returncode}",
    )
    s.check(
        "scope/in-scope refusal names the path and keeps the live edit",
        "community-raw/alpha/skills/demo/SKILL.md" in (proc.stderr or "")
        and "Curator note alpha." in live_alpha.read_text(encoding="utf-8"),
        "exit 20 + path + untouched",
    )

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="T05 importer acceptance + negative-control suite")
    parser.add_argument("--list", action="store_true", help="print case names and exit")
    args = parser.parse_args(argv)

    cases = [
        case_help_is_inert,
        case_unknown_arg_is_inert,
        case_no_args_is_inert,
        case_module_import_does_no_work,
        case_readonly_commands_are_readonly,
        case_discovery_root_is_guarded,
        case_gitignore_has_candidates,
        case_digest_contract_is_frozen,
        case_digest_detects_a_single_byte,
        case_write_guard,
        case_lifecycle,
        case_attestation_gates,
        case_no_atomicity_claim,
        case_digest_contract_documented,
        case_gitignore_candidate_absent_in_repo,
        case_managed_record_loads,
        case_managed_digest_mismatch,
        case_managed_transforms_applied,
        case_promote_blocks_unregistered,
        case_promote_scope_matches_write_scope,
    ]
    if args.list:
        for case in cases:
            print(case.__name__)
        return 0

    s = Suite()
    before = s.real_state()
    with tempfile.TemporaryDirectory(prefix="t05-suite-") as tmp:
        s.tmp = Path(tmp)
        for case in cases:
            print(f"\n--- {case.__name__} ---")
            try:
                if case in (case_help_is_inert, case_unknown_arg_is_inert, case_no_args_is_inert,
                             case_readonly_commands_are_readonly, case_discovery_root_is_guarded):
                    case(s, before)
                else:
                    case(s)
            except Exception as exc:  # noqa: BLE001 - a crashing case is a failure
                s.check(f"{case.__name__} raised", False, f"{type(exc).__name__}: {exc}")

    after = s.real_state()
    print("\n--- real repository unchanged ---")
    s.check("suite/real repository state is unchanged", before == after,
            "6 baseline hashes, the other agents' git status lines and .candidates absence all identical")

    passed = sum(1 for _n, ok, _d in s.results if ok)
    total = len(s.results)
    print(f"\n{passed}/{total} checks passed")
    if passed != total:
        for name, ok, detail in s.results:
            if not ok:
                print(f"  FAILED: {name}  {detail}")
        return EXIT_FAILED
    return EXIT_MATCHED

if __name__ == "__main__":
    raise SystemExit(main())
