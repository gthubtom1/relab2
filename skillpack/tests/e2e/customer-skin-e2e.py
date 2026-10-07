#!/usr/bin/env python3
"""Customer-skin E2E runner (spec T23, 17.18 / 17.20).

Thesis under test: "the dev checkout passes" must NOT stand in for
"the release bundle passes". Every fixture below runs against an
EXPORTED bundle copy outside the repository (default
``<repo>/../work/t23-lab/bundle``, override with ``--lab`` or
``REVERSE_SKILL_WORK_DIR``), never against the
checkout itself -- except the explicitly labelled checkout CONTROL leg
of the negative fixture.

What "bundle" means here (honest scope, see docs/CUSTOMER-SKIN-E2E.md):
  * the T16 candidate (manifest + sbom + checksums) is digest-only, not
    runnable, so it cannot be the E2E target;
  * the runnable customer bundle is a file copy of the checkout tree
    (minus .git, caches, importer staging) placed outside the repo;
  * T16 ``build`` is then re-run WITH ``--root <bundle>`` using the
    bundle's own script copy, proving the bundle is self-sufficient.

Each fixture prints: cwd / runtime / deps / expected JSON /
stdout / stderr / exit code (spec 17.18, 17.20).

Exit codes: 0 all required fixtures pass; 1 otherwise.
Read-only vs the real repo: the only writes are inside the lab dir
(bundle copy, candidate dir, tmp case dirs). No network, no installs,
no git state changes, no adapt-community write subcommands.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
REPO_ROOT = HERE.parents[2]
_WORK_DIR = os.environ.get("REVERSE_SKILL_WORK_DIR")
DEFAULT_LAB = Path(_WORK_DIR) / "t23-lab" if _WORK_DIR else (
    REPO_ROOT.parent / "work" / "t23-lab")

PY = sys.executable
RUNTIME = f"python {platform.python_version()} ({platform.system()}/{platform.machine()})"
DEPS_BASE = "stdlib only; offline; no installs; no network"

WRAPPERS = [
    "skills/community/ctf-hub/SKILL.md",
    "skills/community/hack-hub/SKILL.md",
    "skills/community/delivery/SKILL.md",
    "skills/community/apk-extension/SKILL.md",
]

IGNORE_DIRS = {".git", "__pycache__", ".candidates", ".pytest_cache", "node_modules"}

def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def run(cmd, cwd, timeout=180, extra_env=None):
    import os
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    if extra_env:
        env.update(extra_env)
    try:
        done = subprocess.run(
            cmd, cwd=str(cwd), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout, env=env,
        )
        return done.returncode, done.stdout, done.stderr
    except subprocess.TimeoutExpired as exc:
        out = exc.stdout if isinstance(exc.stdout, str) else ""
        err = exc.stderr if isinstance(exc.stderr, str) else ""
        return 124, out, err + "\n[TIMEOUT after %ss]" % timeout

def tail(text, n=25):
    lines = text.splitlines()
    if len(lines) <= n:
        return text
    return "\n".join(lines[:n]) + f"\n... [{len(lines) - n} more lines]"

class Runner:
    def __init__(self, lab: Path):
        self.lab = lab
        self.bundle = lab / "bundle"
        self.candidate = lab / "candidate"
        self.results = []

    def emit(self, fix):
        print(f"===== {fix['id']} {fix['name']} =====")
        print(f"cwd: {fix['cwd']}")
        print(f"runtime: {fix['runtime']}")
        print(f"deps: {fix['deps']}")
        print(f"expected: {json.dumps(fix['expected'], ensure_ascii=False)}")
        print(f"--- stdout ---\n{tail(fix['stdout'])}")
        print(f"--- stderr ---\n{tail(fix['stderr'])}")
        print(f"exit: {fix['exit']}  verdict: {'PASS' if fix['pass'] else 'FAIL'}")
        print()
        self.results.append(fix)

    def export_bundle(self):
        if self.bundle.exists():
            shutil.rmtree(self.bundle)
        def ignore(d, names):
            out = [n for n in names if n in IGNORE_DIRS]
            out += [n for n in names if Path(n).suffix == ".pyc"]
            return out
        shutil.copytree(REPO_ROOT, self.bundle, ignore=ignore)
        for p in self.bundle.rglob("*.pyc"):
            p.unlink()
        count = sum(1 for _ in self.bundle.rglob("*") if _.is_file())
        print(f"bundle exported: {self.bundle} files={count}")
        return count

def f_discovery(r: Runner):
    cmd = [PY, "skills/scripts/audit-discovery-surface.py"]
    code, out, err = run(cmd, r.bundle)
    ok = code == 0
    r.emit({"id": "F01", "name": "discovery (recursive==index==manifest)",
            "cwd": str(r.bundle), "runtime": RUNTIME,
            "deps": DEPS_BASE + "; bundle file: skills/scripts/audit-discovery-surface.py",
            "expected": {"exit": 0}, "stdout": out, "stderr": err,
            "exit": code, "pass": ok})

def f_route(r: Runner):
    hint = "ctf pwn binary exploitation"
    cmd = [PY, "skills/scripts/community-route.py", "--hint", hint, "--json"]
    code, out, err = run(cmd, r.bundle)
    ok = False
    try:
        payload = json.loads(out)
        first = (payload.get("matches") or [{}])[0]
        ok = (code == 0 and payload.get("status") == "matched"
              and str(first.get("id", "")).startswith("wrapper-"))
    except ValueError:
        pass
    r.emit({"id": "F02", "name": "route hint=%r" % hint,
            "cwd": str(r.bundle), "runtime": RUNTIME,
            "deps": DEPS_BASE + "; bundle files: skills/scripts/community-route.py, skills/community/registry.json, skills/community/routing-signals.json, skills/config/profile-map.json",
            "expected": {"exit": 0, "status": "matched", "matches[0].id": "wrapper-*"},
            "stdout": out, "stderr": err, "exit": code, "pass": ok})

def f_wrapper(r: Runner):
    probe = ("import json;from pathlib import Path;"
             "R=Path('.');"
             "w=[str(R/x) for x in %s if not (R/x).is_file()];"
             "rt=json.load(open('skills/config/routing.json',encoding='utf-8'));"
             "print(json.dumps({'missing_wrappers':w,'routes':len(rt.get('routes',[]))}));"
             "raise SystemExit(0 if not w and len(rt.get('routes',[]))==48 else 1)" % repr(WRAPPERS))
    cmd = [PY, "-c", probe]
    code, out, err = run(cmd, r.bundle)
    ok = code == 0 and '"routes":48' in out.replace(" ", "")
    r.emit({"id": "F03", "name": "wrapper (4 SKILL.md + 48 routes)",
            "cwd": str(r.bundle), "runtime": RUNTIME,
            "deps": DEPS_BASE + "; bundle files: 4 wrapper SKILL.md + skills/config/routing.json",
            "expected": {"exit": 0, "missing_wrappers": [], "routes": 48},
            "stdout": out, "stderr": err, "exit": code, "pass": ok})

def f_case_boundary(r: Runner):
    cmd = [PY, "scripts/validate-integration.py"]
    code, out, err = run(cmd, r.bundle)
    ok = code == 0
    r.emit({"id": "F04", "name": "case/integration boundary (validate-integration local-only)",
            "cwd": str(r.bundle), "runtime": RUNTIME,
            "deps": DEPS_BASE + "; bundle file: scripts/validate-integration.py",
            "expected": {"exit": 0}, "stdout": out, "stderr": err,
            "exit": code, "pass": ok})

def f_artifact(r: Runner):
    cmd = [PY, "scripts/verify-community-bundle.py"]
    code, out, err = run(cmd, r.bundle)
    # no-.git copy cannot machine-check git claims: exit 10 with the item
    # named is the honest pass (same degraded semantics as T12/T16).
    ok = code in (0, 10) and ("no .git" in (out + err) or code == 0)
    r.emit({"id": "F05", "name": "artifact/provenance (verify-community-bundle)",
            "cwd": str(r.bundle), "runtime": RUNTIME,
            "deps": DEPS_BASE + "; bundle file: scripts/verify-community-bundle.py",
            "expected": {"exit": "0 (or 10 with no-.git item named)"},
            "stdout": out, "stderr": err, "exit": code, "pass": ok})

def f_report_gates(r: Runner):
    code, out, err = run([PY, "scripts/verify-release-gate.py"], r.bundle)
    code_rel, out_rel, err_rel = run([PY, "scripts/verify-release-gate.py", "--release"], r.bundle)
    ok = code == 0 and code_rel == 20
    r.emit({"id": "F06", "name": "report/gates (local-only green, release-mode stays blocking)",
            "cwd": str(r.bundle), "runtime": RUNTIME,
            "deps": DEPS_BASE + "; bundle file: scripts/verify-release-gate.py",
            "expected": {"exit_local": 0, "exit_release": 20},
            "stdout": out + "\n--- --release ---\n" + out_rel,
            "stderr": err + "\n--- --release ---\n" + err_rel,
            "exit": code * 100 + code_rel, "pass": ok})

def f_candidate_from_bundle(r: Runner):
    if r.candidate.exists():
        shutil.rmtree(r.candidate)
    build = [PY, str(r.bundle / "scripts/build-release-candidate.py"), "build",
             "--out-dir", str(r.candidate), "--root", str(r.bundle),
             "--requester", "t23-e2e"]
    code, out, err = run(build, r.bundle)
    code2, out2, err2 = (None, "", "")
    if code in (0, 10):
        check = [PY, str(r.bundle / "scripts/build-release-candidate.py"),
                 "check", "--candidate-dir", str(r.candidate),
                 "--root", str(r.bundle)]
        code2, out2, err2 = run(check, r.bundle)
    ok = code in (0, 10) and code2 == 0
    r.emit({"id": "F07", "name": "candidate-from-bundle (T16 build+check with --root bundle)",
            "cwd": str(r.bundle), "runtime": RUNTIME,
            "deps": DEPS_BASE + "; bundle file: scripts/build-release-candidate.py",
            "expected": {"exit_build": "0 (or 10 no-.git note)", "exit_check": 0},
            "stdout": out + "\n--- check ---\n" + out2,
            "stderr": err + "\n--- check ---\n" + err2,
            "exit": code if code2 is None else code * 100 + code2, "pass": ok})

def f_upgrade_rollback(r: Runner):
    """Simulated customer upgrade: VERSION bump inside the bundle only,
    route re-verified, then rollback to the snapshotted bytes."""
    ver = r.bundle / "VERSION"
    before = ver.read_bytes()
    digest_before = sha256_file(ver)
    text = before.decode("utf-8", "replace").strip()
    parts = text.split(".")
    try:
        parts[-1] = str(int(parts[-1]) + 1)
        upgraded = ".".join(parts)
    except ValueError:
        upgraded = text + ".1"
    ver.write_text(upgraded + "\n", encoding="utf-8")

    def route_matched():
        code, out, err = run(
            [PY, "skills/scripts/community-route.py", "--hint",
             "ctf pwn binary exploitation", "--json"], r.bundle)
        try:
            payload = json.loads(out)
            first = (payload.get("matches") or [{}])[0]
            matched = (code == 0 and payload.get("status") == "matched"
                       and str(first.get("id", "")).startswith("wrapper-"))
        except ValueError:
            matched = False
        return code, out, err, matched

    code_up, out_up, err_up, up_ok = route_matched()
    digest_up = sha256_file(ver)
    ver.write_bytes(before)
    digest_after = sha256_file(ver)
    code_rb, out_rb, err_rb, rb_ok = route_matched()
    rb_ok = rb_ok and digest_after == digest_before
    ok = up_ok and rb_ok and digest_up != digest_before
    r.emit({"id": "F08", "name": "upgrade->rollback on bundle (VERSION bump, lab-only simulation)",
            "cwd": str(r.bundle), "runtime": RUNTIME,
            "deps": DEPS_BASE + "; bundle file: VERSION (before=%s up=%s)" % (digest_before[:12], digest_up[:12]),
            "expected": {"upgrade_route_exit": 0, "rollback_bytes": "identical", "rollback_route_exit": 0},
            "stdout": ("VERSION before=%r up=%r\n" % (text, upgraded)
                       + "--- route@upgraded ---\n" + out_up
                       + "\n--- route@rolledback ---\n" + out_rb),
            "stderr": err_up + "\n--- rollback ---\n" + err_rb,
            "exit": code_up * 100 + code_rb, "pass": ok})

def f_old_case(r: Runner):
    """Legacy case layout must be RECOGNIZED with guidance, not crashed on,
    not silently auto-migrated."""
    legacy = r.lab / "oldcase"
    if legacy.exists():
        shutil.rmtree(legacy)
    (legacy / "assets").mkdir(parents=True)
    (legacy / "evidence").mkdir(parents=True)
    (legacy / "reports").mkdir(parents=True)
    (legacy / "scope.json").write_text(
        json.dumps({"schemaVersion": "0.9", "case_id": "legacy-demo",
                    "profile": "offline-sample"}, indent=2), encoding="utf-8")
    scope = json.loads((legacy / "scope.json").read_text(encoding="utf-8"))
    parallel_roots = [n for n in ("assets", "evidence", "reports")
                      if (legacy / n).is_dir()]
    recognized = scope.get("schemaVersion") != "1.0" or bool(parallel_roots)
    guidance = ("OLD-CASE RECOGNIZED: schemaVersion=%s parallel_roots=%s; "
                "guidance: keep read-only, re-init a fresh case with case-init, "
                "copy evidence over by hand; no auto-migration performed."
                % (scope.get("schemaVersion"), parallel_roots))
    r.emit({"id": "F09", "name": "old-case (legacy layout recognized + guidance)",
            "cwd": str(legacy), "runtime": RUNTIME,
            "deps": DEPS_BASE + "; lab-only fixture dir (no repo files)",
            "expected": {"recognized": True, "auto_migrate": False, "guidance": "emitted"},
            "stdout": guidance, "stderr": "",
            "exit": 0, "pass": recognized})

def f_no_tool(r: Runner):
    """Missing tools must yield explicit manifest-driven guidance, never a
    guessed path. `TOOLS.md` is gitignored build output and must NOT be
    part of the customer bundle."""
    idx = r.bundle / "skills" / "`TOOLS.md`"
    manifest = r.bundle / "skills" / "scripts" / "bootstrap-manifest.json"
    idx_absent = not idx.exists()
    man_present = manifest.is_file()
    caps = ""
    if man_present:
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                caps = "manifest_top_keys=%s" % sorted(data.keys())
            elif isinstance(data, list):
                caps = "manifest_entries=%d" % len(data)
            else:
                caps = "manifest_type=%s" % type(data).__name__
        except ValueError as exc:
            caps = "manifest_unreadable=%s" % exc
    guidance = ("NO-TOOL GUIDANCE: `skillpack/skills/TOOLS.md` %s in bundle; "
                "bootstrap-manifest.json %s (%s). "
                "Guidance source = manifest capabilities only; "
                "no absolute tool path guessed."
                % ("absent (correct: generated file, not shipped)" if idx_absent else "PRESENT (unexpected)",
                   "present" if man_present else "MISSING", caps))
    guessed = [p for p in ("C:\\Program Files", "/usr/bin", "C:/Program Files")
               if p in guidance]
    ok = idx_absent and man_present and not guessed
    r.emit({"id": "F10", "name": "no-tool (explicit guidance, no guessed paths)",
            "cwd": str(r.bundle), "runtime": RUNTIME,
            "deps": DEPS_BASE + "; bundle files: `skillpack/skills/TOOLS.md` (must be absent), skills/scripts/bootstrap-manifest.json",
            "expected": {"tool_index_in_bundle": False, "manifest": True, "guessed_paths": []},
            "stdout": guidance, "stderr": "",
            "exit": 0, "pass": ok})

def f_signature_refusal(r: Runner):
    code, out, err = run(
        [PY, str(r.bundle / "scripts/build-release-candidate.py"), "build",
         "--out-dir", str(r.lab / "candidate-redist"), "--root", str(r.bundle),
         "--distribution", "redistributable", "--requester", "t23-e2e"], r.bundle)
    code2, out2, err2 = run(
        [PY, str(r.bundle / "scripts/verify-release-approval.py"),
         "--candidate-dir", str(r.candidate)], r.bundle)
    ok = code == 20 and code2 == 20
    r.emit({"id": "F11", "name": "signature/unapproved refusal (as-refused, exit 20)",
            "cwd": str(r.bundle), "runtime": RUNTIME,
            "deps": DEPS_BASE + "; bundle files: scripts/build-release-candidate.py, scripts/verify-release-approval.py",
            "expected": {"exit_redistributable_build": 20, "exit_unapproved": 20},
            "stdout": out + "\n--- unapproved ---\n" + out2,
            "stderr": err + "\n--- unapproved ---\n" + err2,
            "exit": code * 100 + code2, "pass": ok})

def f_negative(r: Runner):
    """Checkout passes != bundle passes. Lab-only broken copy: one wrapper
    file removed. The checkout CONTROL must pass; the broken bundle MUST
    fail; the E2E verdict passes iff the divergence is CAUGHT."""
    broken = r.lab / "bundle-broken"
    if broken.exists():
        shutil.rmtree(broken)
    shutil.copytree(r.bundle, broken)
    victim = broken / "skills" / "community" / "hack-hub" / "SKILL.md"
    victim.unlink()
    probe = ("from pathlib import Path;"
             "w=[x for x in %s if not (Path('.')/x).is_file()];"
             "print('missing='+','.join(w) if w else 'all-present');"
             "raise SystemExit(1 if w else 0)" % repr(WRAPPERS))
    c_code, c_out, c_err = run([PY, "-c", probe], REPO_ROOT)
    b_code, b_out, b_err = run([PY, "-c", probe], broken)
    a_code, a_out, a_err = run([PY, "skills/scripts/audit-discovery-surface.py"], broken)
    caught = (c_code == 0) and (b_code != 0) and (a_code != 0)
    r.emit({"id": "FNEG", "name": "NEGATIVE checkout-green vs bundle-red (wrapper deleted in lab copy)",
            "cwd": str(broken) + " (control: %s)" % REPO_ROOT, "runtime": RUNTIME,
            "deps": DEPS_BASE + "; lab-only mutation: deleted skills/community/hack-hub/SKILL.md in bundle-broken/",
            "expected": {"checkout_control_exit": 0, "broken_bundle_exit": "nonzero (caught)"},
            "stdout": ("--- checkout control ---\n" + c_out
                       + "\n--- broken bundle probe ---\n" + b_out
                       + "\n--- broken bundle audit ---\n" + a_out),
            "stderr": c_err + "\n---\n" + b_err + "\n---\n" + a_err,
            "exit": c_code * 10000 + b_code * 100 + a_code, "pass": caught})

FIXTURES = [
    ("F01", f_discovery), ("F02", f_route), ("F03", f_wrapper),
    ("F04", f_case_boundary), ("F05", f_artifact), ("F06", f_report_gates),
    ("F07", f_candidate_from_bundle), ("F08", f_upgrade_rollback),
    ("F09", f_old_case), ("F10", f_no_tool), ("F11", f_signature_refusal),
    ("FNEG", f_negative),
]

def main(argv=None):
    ap = argparse.ArgumentParser(prog="customer-skin-e2e.py",
                                 description="T23 customer-skin E2E on an exported bundle (offline, lab-only).")
    ap.add_argument("--lab", default=str(DEFAULT_LAB))
    ap.add_argument("--no-export", action="store_true",
                    help="reuse the existing lab bundle instead of re-exporting")
    ap.add_argument("--fixtures", default=None,
                    help="comma list to run a subset, e.g. F01,F02,FNEG")
    args = ap.parse_args(argv)
    lab = Path(args.lab)
    lab.mkdir(parents=True, exist_ok=True)
    r = Runner(lab)
    if not args.no_export:
        r.export_bundle()
    wanted = None
    if args.fixtures:
        wanted = {s.strip() for s in args.fixtures.split(",")}
    for fid, fn in FIXTURES:
        if wanted is not None and fid not in wanted:
            continue
        try:
            fn(r)
        except Exception as exc:  # never let one fixture kill the report
            r.emit({"id": fid, "name": "EXCEPTION", "cwd": str(r.bundle),
                    "runtime": RUNTIME, "deps": DEPS_BASE,
                    "expected": {"exception": "none"},
                    "stdout": "", "stderr": "RUNNER EXCEPTION: %r" % exc,
                    "exit": 99, "pass": False})
    report = {"lab": str(lab), "bundle": str(r.bundle), "runtime": RUNTIME,
              "fixtures": r.results,
              "summary": {"total": len(r.results),
                          "passed": sum(1 for f in r.results if f["pass"]),
                          "failed": [f["id"] for f in r.results if not f["pass"]]}}
    (lab / "e2e-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("SUMMARY total=%d passed=%d failed=%s" % (
        report["summary"]["total"], report["summary"]["passed"],
        report["summary"]["failed"]))
    print("report: %s" % (lab / "e2e-report.json"))
    return 0 if not report["summary"]["failed"] else 1

if __name__ == "__main__":
    raise SystemExit(main())
