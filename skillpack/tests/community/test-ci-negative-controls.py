#!/usr/bin/env python3
"""Negative controls for the T10 CI wiring: prove each gate really turns the build red.

Why this file exists
--------------------
A CI step that has only ever been seen passing is not a gate. The three gates T26
added went green for a whole round while nothing called them (WORK-BOARD U10), and
the only reason anyone noticed is that a human noticed. Spec T10 requires the
opposite evidence: "raw discovery, license, active links, handoff mismatch can make
CI fail".

So each control below takes a *known-good* checkout, copies it to a scratch
directory outside the repository, injects exactly one realistic defect, and then
runs the same entrypoint CI runs (``skills/tests/run-ci-gates.py``). A control
passes only when that entrypoint exits non-zero **and** the failing gate is the
one the defect targets -- a control that made some *other* gate red would prove
nothing about the gate it names.

Two properties keep the controls honest:

* **Isolation.** Every mutation happens in a throwaway copy. Nothing under the real
  repository is modified, and ``scripts/adapt-community.py`` is never executed, in
  any form, with any argument -- it overwrites 1111 paths with no backup and no diff.
* **Self-check.** Each control declares the gate it expects to fail and the exit
  code that gate documents. If the observed failure is a different gate, or the
  whole run somehow passes, the control fails loudly instead of quietly counting.

Spec 17.18 fixture discipline: every control records cwd, runtime, input, expected
exit code and observed stdout, and none of them touches the network.

Usage::

    python tests/community/test-ci-negative-controls.py
    python tests/community/test-ci-negative-controls.py --only broken-link
    python tests/community/test-ci-negative-controls.py --list

Exit codes: 0 every control failed the build as required, 1 a control did not.

Standard library only.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

# ★ 2026-10-10 修正：原来写 `parents[2]`。本文件在
#   <仓根>/skillpack/tests/community/ 下，`parents[2]` 只上溯到 **skillpack/**，
#   于是 ROOT=C:\relab2\skillpack —— 副本里根本没有 `.github/workflows/ci.yml`，
#   `unpinned-action` 这条负控每次都在 `path.read_text()` 上抛
#   FileNotFoundError（实测 traceback 指向 unpinned-action\.github\workflows\ci.yml）。
#   也就是说**这条负控从来没有真正验证过 SHA pin 门禁**。
#   正解是上溯 3 层到仓根。RUNNER/WIRING 也要跟着改（它们在 skillpack/ 之下）。
ROOT = Path(__file__).resolve().parents[3]
SKILLPACK = ROOT / "skillpack"
RUNNER = SKILLPACK / "skills" / "tests" / "run-ci-gates.py"
WIRING = SKILLPACK / "skills" / "tests" / "verify-gate-wiring.py"

# Copy everything except .git: this is the release-bundle run-skin of spec 17.18,
# not a partial tree. An earlier version copied a hand-picked subset of directories
# and the untouched baseline came out red, because several gates read community-raw/
# and other trees the list did not mention -- a control harness that starts red
# proves nothing about the defect it injects.
# ★ 2026-10-10 追加排除本机运行时目录。
#   原因一（崩溃）：work/ 下有 240 个 master-route-<时间戳>/ 目录，
#     _audit_tmp/、pyghidra_mcp_projects/ 同理。copytree 会把它们全复制到
#     副本里，路径一深就撞 Windows 的 MAX_PATH，copytree 直接抛异常 ——
#     实测负控在 unpinned_action 这一步 traceback 崩掉。
#   原因二（耗时）：它们全是运行时垃圾，复制一遍要几百秒
#     （实测整个负控 355 秒，绝大部分花在复制上）。
#   这些目录都在 .gitignore 里，**不在版本库中**，所以排除它们
#   不改变「release-bundle run-skin」的性质 —— 客户拿到手的东西本来就没有它们。
EXCLUDE = shutil.ignore_patterns(
    ".git", "__pycache__", "*.pyc", ".candidates", ".worktrees",
    "work", "_audit_tmp", "pyghidra_mcp_projects", ".hub",
    "node_modules", "unpacking")

def make_copy(destination: Path, label: str) -> Path:
    """A no-git copy of the checkout: the customer run-skin, not the dev tree."""
    destination.mkdir(parents=True, exist_ok=True)
    for entry in sorted(ROOT.iterdir(), key=lambda p: p.name):
        if entry.name == ".git":
            continue
        target = destination / entry.name
        if entry.is_dir():
            shutil.copytree(entry, target, dirs_exist_ok=True, ignore=EXCLUDE)
        elif entry.is_file():
            shutil.copy2(entry, target)
    # A copy without .git is exactly what a release bundle looks like, and it is
    # what proves these gates do not secretly depend on the git index.
    assert not (destination / ".git").exists(), f"control {label}: copy must not carry .git"
    return destination

def run_gates(copy_root: Path) -> tuple[int, str]:
    """Run CI's entrypoint *inside the copy*.

    The runner derives ROOT from its own ``__file__``, so invoking the copy's
    runner is what makes the control real. An earlier version passed the original
    runner path with cwd=copy_root; every gate then read the untouched checkout and
    all six controls reported a false green. This is the same failure mode as a
    control that asserts nothing, so it is worth stating plainly.
    """
    # ★ ROOT 现在是仓根（2026-10-10 修正），副本里的 runner 在 skillpack/ 之下。
    #   原来写 copy_root/"skills"/... 少了 skillpack 这一层。
    runner = copy_root / "skillpack" / "skills" / "tests" / "run-ci-gates.py"
    if not runner.is_file():
        raise FileNotFoundError(f"copied CI entrypoint missing: {runner}")
    completed = subprocess.run(
        [sys.executable, str(runner), "--runner", "python"],
        cwd=str(copy_root), capture_output=True, text=True, encoding="utf-8",
        errors="replace", check=False,
        env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"},
    )
    return completed.returncode, (completed.stdout or "") + (completed.stderr or "")

# --------------------------------------------------------------------------
# controls
# --------------------------------------------------------------------------

def broken_active_link(copy_root: Path) -> str:
    """Spec T10 acceptance: an *active* document link must break the build.

    Injected into a curated (non-vendored) document so the failure cannot be
    registered in docs/community/link-triage.json -- that registry is for
    upstream provenance breaks, and an unregistered active break is the exact
    case verify-doc-links.py is required to reject.
    """
    target = copy_root / "skillpack" / "docs" / "community" / "ROUTE-RANKING.md"
    if not target.is_file():
        target = copy_root / "skillpack" / "skills" / "MASTER-ROUTING.md"
    text = target.read_text(encoding="utf-8")
    injection = "\n\n[active-link-negative-control](t10-invented-active-link-xyz.md)\n"
    target.write_text(text + injection, encoding="utf-8")
    return f"appended an active markdown link to {target.relative_to(copy_root).as_posix()}"

def broken_kernel_active_link(copy_root: Path) -> str:
    """A broken link inside kernel/ must break the build **as class=active**.

    Why this exists
    ---------------
    verify-doc-links.py used to resolve ROOT one level too shallow, so every
    rule-table glob (``skills/community/**``, ``docs/community/**``) matched
    nothing and 164 real broken links went unreported while the gate stayed
    green.

    Why the class is asserted, not just the exit code
    ----------------------------------------------
    An earlier version of this control only asserted "the build goes red".
    That is **not discriminating**: classify() ends with a catch-all rule
    (``default-active``, glob ``**``) that classifies *any* repo-relative path
    as active. So the control passed with the correct ROOT **and** with the
    broken ROOT — it could not tell the two states apart, and a control that
    holds in both states is not a control (2026-10-10 review finding).

    So the injected link must be reported with the class the rule table
    derives from the *correct* ROOT. When ROOT is one level shallow the
    kernel path no longer resolves the way the rule table expects, and the
    gate's own output stops matching this assertion.
    """
    target = copy_root / "kernel" / "02-hubcore" / "docs" / "ENGINEERING-CONTINUITY.md"
    if not target.is_file():
        return ""
    text = target.read_text(encoding="utf-8")
    injection = "\n\n[kernel-active-link-negctl](t10-invented-kernel-link-xyz.md)\n"
    target.write_text(text + injection, encoding="utf-8")
    return "appended an active markdown link to kernel/02-hubcore/docs/ENGINEERING-CONTINUITY.md"


def handoff_mismatch(copy_root: Path) -> str:
    """Spec T10 acceptance: a handoff mismatch must break the build.

    Two candidates were measured before this one was written. Rewriting a
    ``downstream_skill`` inside ``schemas/community-handoff-output.json`` proved
    nothing: the sample document is *built in code* by build_output_sample(), and
    the schema file carries no sample, so the rewrite was invisible to every gate.
    That is the "control proves nothing" failure mode, so it is recorded here
    instead of being quietly swapped out.

    What is actually checkable: a registry whose ``baseline.commit`` names a
    commit that does not exist is a provenance handoff mismatch, and the contract
    gate recomputes content hashes from it. Both edits below are values a
    plausible mistake produces.
    """
    path = copy_root / "skillpack" / "skills" / "community" / "registry.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    skills = document.get("skills") or []
    if not skills:
        return ""
    before = skills[0].get("content_hash")
    skills[0]["content_hash"] = "sha256:" + "0" * 64
    path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return (f"changed the first registry record's content_hash "
            f"({before} -> sha256:{'0' * 64}); the handoff carries this digest, "
            f"so the output no longer matches the registry")

def raw_entrypoint(copy_root: Path) -> str:
    """Spec T10 acceptance: raw discovery must break the build.

    Reproduces exactly the CR-002 regression: a raw vendor SKILL.md is written
    back under the client discovery root, where a plain recursive walk finds it.
    """
    raw = copy_root / "skillpack" / "skills" / "community" / "t10-leaked-raw-skill"
    raw.mkdir(parents=True, exist_ok=True)
    (raw / "SKILL.md").write_text(
        "---\n"
        "name: t10-leaked-raw-skill\n"
        "description: A raw vendor skill that the importer wrote back into the discovery root.\n"
        "user-invocable: \"false\"\n"
        "---\n\n"
        "This file exists only to prove the discovery isolation gate fails closed.\n",
        encoding="utf-8",
    )
    return "wrote a raw vendor SKILL.md back under skills/community/ (CR-002 regression)"

def routing_signal_regression(copy_root: Path) -> str:
    """The T26 signal layer must block a widened token list.

    Re-inserts ``ai``, the literal T26 measured to be an over-trigger hitting 157
    of 293 records. If routing-signals verification were not wired into CI, this
    regression would pass the build silently.
    """
    path = copy_root / "skillpack" / "skills" / "community" / "routing-signals.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    present = list(document.get("short_tokens") or [])
    if "ai" not in present:
        present.append("ai")
        present.sort()
    document["short_tokens"] = present
    path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return "re-added the measured-harmful 'ai' short token to routing-signals.json"

def unpinned_action(copy_root: Path) -> str:
    """Supply chain: an Action that is not SHA-pinned must break the build."""
    path = copy_root / ".github" / "workflows" / "ci.yml"
    text = path.read_text(encoding="utf-8")
    needle = "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"
    if needle not in text:
        return ""  # nothing to unpin; the caller reports this control as skipped
    path.write_text(text.replace(needle, "actions/checkout@v7", 1), encoding="utf-8")
    return "replaced one SHA-pinned action with the floating tag actions/checkout@v7"

def gate_removed_from_wiring(copy_root: Path) -> str:
    """The wiring gate itself: dropping a gate from the manifest must be red.

    Without this control, someone could "fix" a red build by deleting the gate
    from skills/tests/ci-gates.json, which is the same class of defect as the
    self-exempting triage registry found on 2026-09-29.
    """
    path = copy_root / "skillpack" / "skills" / "tests" / "ci-gates.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    gates = document.get("gates") or []
    removed = [g.get("id") for g in gates if g.get("id") == "test-community-decoys"]
    if not removed:
        return ""
    document["gates"] = [g for g in gates if g.get("id") != "test-community-decoys"]
    path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return "deleted the test-community-decoys gate from skills/tests/ci-gates.json"

CONTROLS: dict[str, dict[str, Any]] = {
    "broken-active-link": {
        "mutate": broken_active_link,
        "expect_gate": "verify-doc-links",
        "spec": "T10 acceptance: active links",
        "why": "A registered-provenance link is allowed to break; an *active* link "
               "is not, and it must not be registrable.",
    },
    "broken-kernel-active-link": {
        "mutate": broken_kernel_active_link,
        "expect_gate": "verify-doc-links",
        # ★ 2026-10-10：只断言"变红"不具区分度（`default-active` 的 `**`
        #   兜底会吸收任何路径，ROOT 坏掉时它照样红）。
        #   断言点选在 runner **确实保留**的那一行：`run-ci-gates.py` 只转发
        #   9 空格缩进的 FAIL / [BLOCKED] 行，`verify-doc-links` 自己的
        #   `[active] <file>` 明细行不在这个通道里（实测断言它必然不匹配）。
        #   "1 must-fix (active/wrapper) broken link(s)" 只有在确实存在
        #   must-fix 断链时才会出现 —— 而 must-fix 只来自 active/wrapper 类，
        #   也就是规则表在正确 ROOT 下解析出来的结果。
        "expect_output": "1 must-fix (active/wrapper) broken link(s)",
        "spec": "2026-10-10: the doc-links rule table must actually match kernel/",
        "why": "ROOT was one level too shallow, so every classification glob matched "
               "nothing and 164 real broken links went unverified while the gate "
               "reported green. A gate whose rule table matches nothing looks exactly "
               "like a gate that found nothing.",
    },
    "handoff-mismatch": {
        "mutate": handoff_mismatch,
        "expect_gate": "test-contract-v2",
        "spec": "T10 acceptance: handoff mismatch",
        "why": "The handoff output names a downstream skill; a name that is not one "
               "of the canonical skills must fail the contract, not pass silently.",
    },
    "raw-entrypoint": {
        "mutate": raw_entrypoint,
        "expect_gate": "audit-discovery-surface",
        "spec": "T10 acceptance: raw discovery; also the CR-002 regression",
        "why": "A raw vendor SKILL.md reachable by a plain recursive skills/** walk "
               "re-creates the discovery leak T01 closed.",
    },
    "routing-signal-regression": {
        "mutate": routing_signal_regression,
        "expect_gate": "verify-routing-signals",
        "spec": "WORK-BOARD U10: the T26 gates must actually stop a regression",
        "why": "The 'ai' literal was measured to over-trigger 157/293 records. If this "
               "control ever passes, the T26 gate is not running in CI.",
    },
    "unpinned-action": {
        "mutate": unpinned_action,
        "expect_gate": "verify-gate-wiring",
        "spec": "spec 17.31: third-party Actions pinned to an immutable ref",
        "why": "A floating tag is a mutable code path into the gate job.",
    },
    "gate-removed-from-wiring": {
        "mutate": gate_removed_from_wiring,
        "expect_gate": "verify-gate-wiring",
        "spec": "U10's failure mode: a gate that is no longer called",
        "why": "Removing a gate from the manifest is how a red build gets 'fixed' "
               "without fixing anything. It must be red.",
    },
}

def observed_gate(output: str) -> list[str]:
    """Gate ids that the run reported as blocked or failed, in report order.

    The runner pads ids for alignment, so the id is the first whitespace-delimited
    token of the line, not everything before the first colon.
    """
    found: list[str] = []
    for line in output.splitlines():
        stripped = line.strip()
        if stripped.startswith(("[BLOCKED] ", "[FAILED] ")):
            found.append(stripped.split()[1])
        elif stripped.startswith(("BLOCKED ", "FAILED ")):
            found.append(stripped.split()[1].split(":")[0])
    # Preserve order, drop repeats from the two summary sections.
    seen: set[str] = set()
    ordered = [g for g in found if not (g in seen or seen.add(g))]
    return ordered

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--only", action="append", help="run only these controls (repeatable)")
    parser.add_argument("--list", action="store_true", help="list controls and exit 0")
    args = parser.parse_args(argv)

    if not RUNNER.is_file():
        print(f"FAIL test-ci-negative-controls: CI entrypoint missing: {RUNNER}")
        return 1

    if args.list:
        for name, control in CONTROLS.items():
            print(f"{name:28} expects {control['expect_gate']:26} {control['spec']}")
        return 0

    selected = [n for n in CONTROLS if not args.only or n in set(args.only)]
    unknown = set(args.only or []) - set(CONTROLS)
    if unknown:
        print(f"FAIL test-ci-negative-controls: unknown control(s): {sorted(unknown)}")
        return 1

    print("=" * 78)
    print("T10 CI negative controls: each injected defect must turn the build red")
    print("=" * 78)
    print(f"source checkout : {ROOT}")
    print(f"CI entrypoint   : {RUNNER.as_posix()}")

    failures: list[str] = []
    skipped: list[str] = []
    with tempfile.TemporaryDirectory(prefix="t10-negative-") as workspace:
        # Control 0: the untouched copy must be green, otherwise every control
        # below would "pass" for the wrong reason.
        print("\n--- baseline: an untouched no-git copy must be GREEN ---")
        baseline_root = make_copy(Path(workspace) / "baseline", "baseline")
        code, output = run_gates(baseline_root)
        red = observed_gate(output)
        status = "green" if code == 0 else f"ALREADY RED (exit {code})"
        print(f"[{status}] baseline exit {code}")
        print(f"    baseline failing gates: {red or 'none'}")
        for line in output.splitlines():
            if line.strip().startswith(("PASS run-ci-gates", "FAIL run-ci-gates")):
                print(f"    {line.strip()}")
            if line.startswith(" " * 9) and line.strip().startswith(("FAIL", "[BLOCKED]")):
                print(f"      -> {line.strip()[:200]}")
        if red:
            # Concurrent agents edit this tree. A red baseline usually means
            # somebody's file is half-written, not that these controls are
            # broken -- so name the gates instead of leaving a bare exit code.
            print("    NOTE: the baseline copies the live working tree. If it is red, "
                  "a gate listed above is failing right now in the real checkout; "
                  "re-run before drawing conclusions about the controls.")
        baseline_green = code == 0

        for name in selected:
            control = CONTROLS[name]
            print(f"\n--- control {name} ---")
            print(f"spec : {control['spec']}")
            print(f"why  : {control['why']}")
            copy_root = make_copy(Path(workspace) / name, name)
            described = control["mutate"](copy_root)
            if not described:
                skipped.append(name)
                print("SKIPPED: the mutation found nothing to change; the control is "
                      "not proven either way and must be fixed, not ignored")
                failures.append(f"{name}: control mutated nothing")
                continue
            print(f"input: {described}")
            code, output = run_gates(copy_root)
            failing = observed_gate(output)
            ok = code != 0 and control["expect_gate"] in failing
            # 可选的输出断言：门禁**红了**还不够，它必须是因为**对的原因**红的。
            # 只断言退出码的负控在两种相反状态下都成立（2026-10-10 审查发现
            # broken-kernel-active-link 就是这样），那样的负控证明不了任何东西。
            need = control.get("expect_output")
            if ok and need:
                if need not in output:
                    ok = False
                    print(f"    expected output to contain: {need!r}")
                else:
                    print(f"    output assertion matched: {need!r}")
            print(f"expected gate to fail: {control['expect_gate']}")
            print(f"observed exit code   : {code}")
            print(f"observed failing gates: {failing}")
            for line in output.splitlines():
                stripped = line.strip()
                # Show the runner's per-gate block plus the gate's own verdict line,
                # so the log proves which defect was caught, not just that something
                # went red. Continuation lines start with 9 spaces in the runner output.
                if stripped.startswith(("[BLOCKED]", "[FAILED]", "BLOCKED ", "FAILED ",
                                        "FAIL run-ci-gates")):
                    print(f"    {stripped[:220]}")
                elif line.startswith(" " * 9) and stripped and not stripped.startswith(("[PASS]", "[WARN]")):
                    print(f"      -> {stripped[:200]}")
            if not ok:
                if code == 0:
                    failures.append(f"{name}: build stayed GREEN (exit 0) after injecting "
                                    f"{described} -- this gate is not actually enforced by CI")
                else:
                    if need and code != 0 and control["expect_gate"] in failing:
                        failures.append(f"{name}: build went red for the right gate but "
                                        f"the output does not contain {need!r} -- it is red "
                                        f"for a different reason than the one under test")
                    else:
                        failures.append(f"{name}: build went red on {failing}, but "
                                        f"{control['expect_gate']!r} is not among them")
            print(f"[{'PASS' if ok else 'FAIL'}] {name}")

    print("\n" + "=" * 78)
    print(f"controls run: {len(selected)}   failed: {len(failures)}   skipped: {len(skipped)}")
    print(f"baseline (no-git copy) green: {baseline_green}")
    if not baseline_green:
        failures.append("baseline: an untouched no-git copy is not green, so no control "
                        "in this file can prove anything")
    for failure in failures:
        print(f"  FAIL {failure}")
    if failures:
        print("RESULT: at least one negative control did NOT fail the build")
        return 1
    print("RESULT: every injected defect turned the CI build red on the named gate")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())