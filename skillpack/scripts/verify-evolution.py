#!/usr/bin/env python3
"""Machine-enforced gate for docs/EVOLUTION-CHECKLIST.md (10 items, one command).

Why this exists: the checklist gives a verify command per item, but commands
only work when someone remembers to run them. This script runs all 10 in one
go, with a real pass/fail criterion per item and no shell stubs: every check
either executes an existing gate/probe or reads and validates the real files.
Anything that still needs a human is labeled MANUAL in the output, never faked.

Exit codes follow spec section 4.7:
    0   all automated checks pass (MANUAL items, if any, are listed only)
    20  blocked: at least one check failed, fix the listed item
    21  missing input: a required file/benchmark/tool is absent
    30  execution failure: a sub-check crashed or timed out

Usage:
    python scripts/verify-evolution.py [--full] [--json] [--hint TEXT]
    --full    also run the complete 182-case benchmark and smoke.ps1
              (default: official -Quick subset of 48 + full natural 86)
    --json    print machine-readable results after the human report
    --hint    override the representative probe hint for checks 3 and 4
    --sample  sample size per benchmark in default mode (default 8)

Only reads the tree, except temp dirs under the OS temp area. Never writes to
the repository. Wired into ci-gates.json as the ``verify-evolution`` gate
(round-2, 2026-10-02); the entry's blocking_exits are 20/21/30, so a red check
now blocks the integration gate set instead of waiting for someone to remember.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import py_compile
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

EXIT_OK = 0
EXIT_BLOCKED = 20
EXIT_MISSING = 21
EXIT_ERROR = 30

REPO = Path(__file__).resolve().parent.parent
SKILLS = REPO / "skills"
SCRIPTS = SKILLS / "scripts"
TESTS = SKILLS / "tests"
CONFIG = SKILLS / "config"

DEFAULT_HINT = "apk reverse frida"
PWSH = shutil.which("powershell") or shutil.which("pwsh")

Result = tuple  # (status, summary, fix): status in pass|fail|manual|error:<kind>

def run(cmd, timeout=300):
    """Run cmd list in REPO, return (rc, tail). Missing binary -> (None, msg)."""
    try:
        p = subprocess.run(
            cmd, cwd=str(REPO), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
        )
    except FileNotFoundError as e:
        return None, "binary not found: %s" % e
    except subprocess.TimeoutExpired:
        return -1, "timed out after %ss: %s" % (timeout, " ".join(cmd))
    tail = (p.stdout + p.stderr)[-3000:]
    return p.returncode, tail.strip()

def py(args, timeout=300):
    return run([sys.executable] + args, timeout)

def check_doc_links():
    """Checklist 1+6: no broken doc chain (templates/references included)."""
    script = SCRIPTS / "verify-doc-links.py"
    if not script.exists():
        return ("error:missing", "verify-doc-links.py absent", "restore skills/scripts/verify-doc-links.py")
    rc, out = py([str(script), "--json"], timeout=600)
    if rc is None:
        return ("error:missing", out, "python cannot launch subprocesses here; run the command by hand")
    if rc == 0:
        return ("pass", "verify-doc-links.py exit 0 (active/wrapper clean, provenance registered)", "")
    return ("fail",
            "verify-doc-links.py exit %s; tail: %s" % (rc, out[-800:]),
            "fix the listed broken link or register it in docs/community/link-triage.json, then re-run")

def check_signals():
    """Checklist 2: signal layer fail-closed, no silent pass-through."""
    script = SCRIPTS / "verify-routing-signals.py"
    if not script.exists():
        return ("error:missing", "verify-routing-signals.py absent", "restore skills/scripts/verify-routing-signals.py")
    rc, out = py([str(script), "--check"], timeout=300)
    if rc is None:
        return ("error:missing", out, "run skills/scripts/verify-routing-signals.py --check by hand")
    if rc == 0:
        return ("pass", "verify-routing-signals.py --check exit 0", "")
    return ("fail",
            "verify-routing-signals.py --check exit %s; tail: %s" % (rc, out[-800:]),
            "read the reported signal defect (id/regex/evidence/note) and fix skills/community/routing-signals.json")

def master_probe(hint):
    """Run master-route.ps1 once, return (rc, primary_or_msg)."""
    if not PWSH:
        return None, "no powershell/pwsh on PATH"
    tmp = Path(tempfile.mkdtemp(prefix="evo-probe-"))
    try:
        rc, out = run([PWSH, "-NoProfile", "-ExecutionPolicy", "Bypass",
                       "-File", str(SCRIPTS / "master-route.ps1"),
                       "-Hint", hint, "-OutDir", str(tmp)], timeout=120)
        if rc != 0:
            return rc, "master-route.ps1 exit %s: %s" % (rc, out[-400:])
        scope = tmp / "route-scope.md"
        if not scope.exists():
            return rc, "no route-scope.md emitted"
        m = re.search(r"^-\s*primary:\s*(\S+)", scope.read_text(encoding="utf-8"), re.M)
        if not m:
            return rc, "route-scope.md has no primary line"
        return 0, m.group(1)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

def check_route_entry(hint):
    """Checklist 3: routing.json is the single source of truth and probes hit it."""
    rj = CONFIG / "routing.json"
    if not rj.exists():
        return ("error:missing", "skills/config/routing.json absent", "restore skills/config/routing.json from git")
    try:
        data = json.loads(rj.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        return ("fail", "routing.json unparsable: %s" % e, "fix the JSON syntax, keep {routes, priority}")
    routes = data.get("routes", [])
    prio = data.get("priority", [])
    if not routes or not prio:
        return ("fail", "routing.json has %d routes / %d priority entries" % (len(routes), len(prio)),
                "routes and priority must both be non-empty; restore from git if unsure")
    rc, got = master_probe(hint)
    if rc is None:
        return ("error:missing", got, "install powershell or probe master-route.ps1 by hand")
    if rc == 0 and got and got != "R0":
        return ("pass", "routing.json ok (%d routes); probe hint hit PRIMARY=%s" % (len(routes), got), "")
    return ("fail", "routing.json parses (%d routes) but probe hint got '%s'" % (len(routes), got),
            "do the no-force-fit triage: ask for missing input, judge edge vs new type, propose skills/<new>/SKILL.md")

def check_community_reachable(hint):
    """Checklist 4: community layer answers the representative phrasing."""
    script = SCRIPTS / "community-route.py"
    if not script.exists():
        return ("error:missing", "community-route.py absent", "restore skills/scripts/community-route.py")
    rc, out = py([str(script), "--hint", hint], timeout=120)
    if rc is None:
        return ("error:missing", out, "run community-route.py --hint by hand")
    if rc == 0:
        first = next((l for l in out.splitlines() if "confidence" in l), out[:200])
        return ("pass", "community-route.py matched (exit 0): %s" % first[:160], "")
    if rc == 10:
        return ("fail", "community needs_review (exit 10); tail: %s" % out[-500:],
                "narrow the hint (one word) or split with --source; Chinese no_match -> retry in English")
    return ("fail", "community-route.py exit %s; tail: %s" % (rc, out[-500:]),
            "exit 20 means budget_exceeded: narrow to one word per query")

def check_tool_manifest():
    """Checklist 5: tool manifest and doc facts agree."""
    if not PWSH:
        return ("error:missing", "no powershell/pwsh on PATH", "run skills/scripts/verify-doc-facts.ps1 by hand")
    mf = SCRIPTS / "bootstrap-manifest.json"
    if not mf.exists():
        return ("error:missing", "bootstrap-manifest.json absent", "restore skills/scripts/bootstrap-manifest.json")
    try:
        data = json.loads(mf.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        return ("fail", "bootstrap-manifest.json unparsable: %s" % e, "fix the JSON syntax")
    rc, out = run([PWSH, "-NoProfile", "-ExecutionPolicy", "Bypass",
                   "-File", str(SCRIPTS / "verify-doc-facts.ps1")], timeout=300)
    if rc == 0:
        caps = len(data.get("capabilities", data)) if isinstance(data, dict) else len(data)
        return ("pass", "verify-doc-facts.ps1 exit 0 (manifest parses, %s entries)" % caps, "")
    if rc is None:
        return ("error:missing", out, "run verify-doc-facts.ps1 by hand")
    return ("fail", "verify-doc-facts.ps1 exit %s; tail: %s" % (rc, out[-600:]),
            "sync `skillpack/skills/TOOLS.md` with bootstrap-manifest.json (index is generated, fix the source)")

def check_registry_consistency():
    """Checklist 6 (+apk check_routing.py core): registry rows match the tree.

    Every skills[] record's adapted_path must exist and its content_hash must
    equal the file's sha256; every wrappers[] entrypoint must exist.
    """
    reg = SKILLS / "community" / "registry.json"
    if not reg.exists():
        return ("error:missing", "skills/community/registry.json absent", "restore it from git")
    try:
        data = json.loads(reg.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        return ("fail", "registry.json unparsable: %s" % e, "fix the JSON syntax")
    records = data.get("skills", [])
    if not records:
        return ("fail", "registry.json has 0 skills[] records", "restore registry.json from git")
    bad = []
    for r in records:
        rid = r.get("id", "?")
        ap = r.get("adapted_path") or r.get("path", "")
        p = REPO / ap
        if not ap or not p.is_file():
            bad.append("%s: adapted_path missing: %s" % (rid, ap))
            continue
        ep = r.get("entrypoint") or ""
        if ep and not (REPO / ep).is_file():
            bad.append("%s: entrypoint missing: %s" % (rid, ep))
        want = (r.get("content_hash") or "").strip()
        if want:
            algo, _, digest = want.partition(":")
            try:
                got = hashlib.new(algo or "sha256", p.read_bytes()).hexdigest()
            except (ValueError, OSError) as e:
                bad.append("%s: cannot hash: %s" % (rid, e))
                continue
            if got != digest:
                bad.append("%s: content_hash drift: %s" % (rid, ap))
    ids = {r.get("id") for r in records}
    for w in data.get("wrappers", []):
        wid = w.get("id", "?")
        wp = REPO / (w.get("path") or "")
        if not w.get("path") or not wp.is_file():
            bad.append("wrapper missing file: %s -> %s" % (wid, w.get("path")))
        for ref in w.get("reference_ids", []):
            if ref not in ids:
                bad.append("wrapper %s points at unknown record %s" % (wid, ref))
                break
    if bad:
        shown = "; ".join(bad[:8])
        extra = "" if len(bad) <= 8 else " (+%d more)" % (len(bad) - 8)
        return ("fail", "%d/%d registry rows inconsistent: %s%s" % (len(bad), len(records), shown, extra),
                "re-run the adapt step or fix adapted_path/content_hash; never hand-edit the hash")
    return ("pass", "registry consistent: %d skills[] paths exist, hashes match; wrappers present" % len(records), "")

def check_scripts_inventory(full):
    """Checklist 7: automatable steps are scripted and loadable."""
    if not (SCRIPTS / "smoke.ps1").exists():
        return ("error:missing", "skills/scripts/smoke.ps1 absent", "restore skills/scripts/smoke.ps1")
    pys = sorted(SCRIPTS.glob("*.py"))
    if not pys:
        return ("fail", "skills/scripts/*.py is empty", "restore the scripts directory from git")
    broken = []
    for f in pys:
        try:
            py_compile.compile(str(f), doraise=True)
        except py_compile.PyCompileError as e:
            broken.append("%s: %s" % (f.name, e))
    if broken:
        return ("fail", "%d script(s) do not compile: %s" % (len(broken), "; ".join(broken[:5])),
                "fix the syntax error in the listed script")
    if full:
        if not PWSH:
            return ("error:missing", "no powershell for smoke.ps1", "run skills/scripts/smoke.ps1 by hand")
        rc, out = run([PWSH, "-NoProfile", "-ExecutionPolicy", "Bypass",
                       "-File", str(SCRIPTS / "smoke.ps1")], timeout=900)
        if rc == 0:
            return ("pass", "smoke.ps1 exit 0 (%d py scripts compile)" % len(pys), "")
        if rc is None:
            return ("error:missing", out, "run smoke.ps1 by hand")
        return ("fail", "smoke.ps1 exit %s; tail: %s" % (rc, out[-600:]),
                "read the failing smoke stage (verify/parse/quick-route) and fix that layer")
    return ("pass", "%d py scripts compile; smoke.ps1 present (full run only with --full)" % len(pys), "")

def check_coherence():
    """Checklist 8: tables and JSON have not drifted."""
    if not PWSH:
        return ("error:missing", "no powershell/pwsh on PATH", "run verify-routing-coherence.ps1 by hand")
    rc, out = run([PWSH, "-NoProfile", "-ExecutionPolicy", "Bypass",
                   "-File", str(SCRIPTS / "verify-routing-coherence.ps1")], timeout=600)
    if rc is None:
        return ("error:missing", out, "run verify-routing-coherence.ps1 by hand")
    if rc == 0:
        return ("pass", "verify-routing-coherence.ps1 exit 0 (tables match JSON)", "")
    return ("fail", "verify-routing-coherence.ps1 exit %s; tail: %s" % (rc, out[-600:]),
            "JSON wins on conflict: regenerate the md view from skills/config/routing.json, never patch JSON to fit md")

def check_spec():
    """Checklist 9: spec numbering and cross-references still legal."""
    script = SCRIPTS / "verify-spec-structure.py"
    if not script.exists():
        return ("error:missing", "verify-spec-structure.py absent", "restore skills/scripts/verify-spec-structure.py")
    rc, out = py([str(script)], timeout=300)
    if rc is None:
        return ("error:missing", out, "run verify-spec-structure.py by hand")
    if rc == 0:
        return ("pass", "verify-spec-structure.py exit 0", "")
    return ("fail", "verify-spec-structure.py exit %s; tail: %s" % (rc, out[-600:]),
            "fix section numbering / duplicate headings / dangling cross-references in the spec")

def run_official_benchmark(ps1, extra_args=(), timeout=1200):
    """Run an official test-routing.ps1 script into a temp LogDir; parse SUMMARY.txt.

    Returns (total, passed, failed) or (None, error_text). Reading the runner's
    own result file keeps one definition of pass/fail instead of reimplementing it.
    """
    logdir = Path(tempfile.mkdtemp(prefix="evo-bench-"))
    try:
        rc, out = run([PWSH, "-NoProfile", "-ExecutionPolicy", "Bypass",
                       "-File", str(SCRIPTS / ps1),
                       "-LogDir", str(logdir)] + list(extra_args), timeout=timeout)
        summ = logdir / "SUMMARY.txt"
        if not summ.exists():
            return None, "%s left no SUMMARY.txt (exit %s): %s" % (ps1, rc, out[-400:])
        vals = {}
        for ln in summ.read_text(encoding="utf-8-sig").splitlines():
            if "=" in ln:
                k, _, v = ln.partition("=")
                vals[k.strip()] = v.strip()
        try:
            return int(vals["TOTAL"]), int(vals["PASS"]), int(vals["FAIL"])
        except (KeyError, ValueError):
            return None, "%s SUMMARY.txt unparsable: %s" % (ps1, vals)
    finally:
        shutil.rmtree(logdir, ignore_errors=True)

NATURAL_FLOOR = 76  # task card: natural baseline must not regress below 76/86
# ★ 2026-10-10：official 用例数改为**下限**而非精确值。
#   benchmark meta 明写「新增路由场景请同步添加用例」，按规矩加用例却被这道门禁判红，
#   修法提示还是「restore from git」—— 那等于删掉新用例、把新技能退回不可路由。
#   正确语义：只增不减（加用例是规矩，删用例是覆盖退化）。
OFFICIAL_FLOOR = 182  # 2026-08-02 基线；只增不减

def check_dual_benchmark(full):
    """Checklist 10: official 182/182, natural >= 76/86, via the official runners."""
    bo = TESTS / "routing-benchmark.json"
    bn = TESTS / "routing-benchmark-natural.json"
    if not bo.exists() or not bn.exists():
        missing = [p.name for p in (bo, bn) if not p.exists()]
        return ("error:missing", "benchmark file(s) absent: %s" % ", ".join(missing),
                "restore skills/tests/routing-benchmark*.json from git")
    try:
        n_off = len(json.loads(bo.read_text(encoding="utf-8")).get("cases", []))
        n_nat = len(json.loads(bn.read_text(encoding="utf-8")).get("cases", []))
    except (json.JSONDecodeError, OSError) as e:
        return ("fail", "benchmark JSON unparsable: %s" % e, "restore the benchmark file from git")
    # ★ 2026-10-10 修正：原来硬编码 `n_off != 182 or n_nat != 86`，把用例数**冻结**成精确值。
    #   但 benchmark 自己的 meta 写着「修改路由规则后必须保持此基准全绿；
    #   **新增路由场景请同步添加用例**」—— 按规矩加了用例反而会被这道门禁判红。
    #   2026-10-10 补 R50(web-protocol-reverse) / R51(game-reverse) /
    #   R52(kernel-exploit) 共 24 条用例后，本检查持续 FAIL，
    #   而修法提示「restore from git」等于**删掉新用例、把技能退回不可路由**。
    #
    #   正确语义：**只增不减**。新增路由必须加用例（这是规矩），
    #   所以下限检查；删用例才应该拦（那是覆盖退化）。
    #   ★ 同时保留「不能少于基线」以防有人为绕过而删用例。
    if n_off < OFFICIAL_FLOOR or n_nat < NATURAL_FLOOR:
        return ("fail",
                "benchmark shrank below floor: official %d (floor %d), "
                "natural %d (floor %d)"
                % (n_off, OFFICIAL_FLOOR, n_nat, NATURAL_FLOOR),
                "restore skills/tests/routing-benchmark*.json from git; "
                "adding new cases is allowed (and expected), removing them is not")
    if n_off > OFFICIAL_FLOOR or n_nat > NATURAL_FLOOR:
        print("[INFO] benchmark grew beyond recorded floor: official %d>%d, "
              "natural %d>%d (allowed)"
              % (n_off, OFFICIAL_FLOOR, n_nat, NATURAL_FLOOR))
    if n_off != OFFICIAL_FLOOR or n_nat != NATURAL_FLOOR:
        pass  # 增长是正常路径，无需额外输出（上面的 print 已提示）
    if not PWSH:
        return ("error:missing", "no powershell for test-routing runners", "run both test-routing scripts by hand")
    # Official gate is strict 182/182; default mode uses its -Quick subset (48),
    # full mode runs all 182. Natural always runs all 86 against the 76 floor.
    if full:
        res = run_official_benchmark("test-routing.ps1")
        if res[0] is None:
            return ("error:crash", res[1], "re-run test-routing.ps1 by hand and inspect")
        total, passed, failed = res
        if failed:
            return ("fail", "official benchmark regressed: %d/%d pass" % (passed, total),
                    "fix the package, never edit benchmark expectations to fit")
    else:
        res = run_official_benchmark("test-routing.ps1", ("-Quick",))
        if res[0] is None:
            return ("error:crash", res[1], "re-run test-routing.ps1 -Quick by hand and inspect")
        total, passed, failed = res
        if failed:
            return ("fail", "official quick subset regressed: %d/%d pass" % (passed, total),
                    "run test-routing.ps1 fully to scope it; fix the package, not the expectations")
    res = run_official_benchmark("test-routing-natural.ps1")
    if res[0] is None:
        return ("error:crash", res[1], "re-run test-routing-natural.ps1 by hand and inspect")
    _, nat_pass, _ = res
    if nat_pass < NATURAL_FLOOR:
        return ("fail", "natural baseline regressed below floor: %d/86 (floor %d)" % (nat_pass, NATURAL_FLOOR),
                "fix the package, never edit benchmark expectations to fit "
                "(natural hints avoid keywords on purpose)")
    mode = "full" if full else "quick+floor"
    return ("pass",
            "benchmarks ok [%s]: official %d/%d, natural %d/86 (floor %d)" % (mode, passed, total, nat_pass, NATURAL_FLOOR),
            "")

CHECKS = [
    ("[1] doc-links (experience archived)", check_doc_links),
    ("[2] signals fail-closed", check_signals),
    ("[3] route entry", check_route_entry),
    ("[4] community reachable", check_community_reachable),
    ("[5] tool manifest", check_tool_manifest),
    ("[6] registry consistency", check_registry_consistency),
    ("[7] scripts inventory", check_scripts_inventory),
    ("[8] routing coherence", check_coherence),
    ("[9] spec structure", check_spec),
    ("[10] dual benchmark", check_dual_benchmark),
]

def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Run all 10 EVOLUTION-CHECKLIST checks in one command. "
                    "Exit 0 all green, 20 blocked, 21 missing input, 30 execution failure.")
    ap.add_argument("--full", action="store_true", help="run full 182 benchmark and smoke.ps1 (slow)")
    ap.add_argument("--json", action="store_true", help="append machine-readable JSON results")
    ap.add_argument("--hint", default=DEFAULT_HINT, help="representative probe phrasing for checks 3-4")
    args = ap.parse_args(argv)

    results = []
    for title, fn in CHECKS:
        try:
            if fn in (check_route_entry, check_community_reachable):
                status, summary, fix = fn(args.hint)
            elif fn is check_dual_benchmark:
                status, summary, fix = fn(args.full)
            elif fn is check_scripts_inventory:
                status, summary, fix = fn(args.full)
            else:
                status, summary, fix = fn()
        except Exception as e:  # never let one check kill the whole gate
            status, summary, fix = ("error:crash", "%s raised %r" % (title, e),
                                   "this is a gate bug or a broken interpreter: re-run with --json and inspect")
        results.append({"check": title, "status": status, "summary": summary, "fix": fix})
        mark = {"pass": "PASS", "fail": "FAIL", "manual": "MANUAL"}.get(status, "ERROR")
        print("%s %s: %s" % (mark, title, summary))
        if status == "fail":
            print("      fix: %s" % fix)
        elif status.startswith("error"):
            print("      input/bug: %s | remedy: %s" % (summary, fix))
        elif status == "manual":
            print("      needs a human: %s" % fix)

    fails = [r for r in results if r["status"] == "fail"]
    missing = [r for r in results if r["status"] == "error:missing"]
    crashed = [r for r in results if r["status"].startswith("error") and r not in missing]
    manuals = [r for r in results if r["status"] == "manual"]

    if args.json:
        print(json.dumps({"results": results}, ensure_ascii=False, indent=2))

    if manuals and not (fails or missing or crashed):
        print("MANUAL items need a human (not blocking): %s" % ", ".join(r["check"] for r in manuals))
    if fails:
        print("BLOCKED: %d check(s) failed; fix the items above, keep expectations frozen." % len(fails))
        return EXIT_BLOCKED
    if missing:
        print("MISSING INPUT: %d check(s) lack required files/tools." % len(missing))
        return EXIT_MISSING
    if crashed:
        print("FAILURE: %d check(s) crashed." % len(crashed))
        return EXIT_ERROR
    print("ALL GREEN: 10/10 automated checks pass%s."
          % ("; --full for 182 + smoke" if not args.full else " (full mode)"))
    return EXIT_OK

if __name__ == "__main__":
    sys.exit(main())
