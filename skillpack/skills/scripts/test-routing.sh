#!/usr/bin/env bash
# Run the shared routing benchmark through the Bash structured router.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BENCHMARK="$SCRIPT_DIR/../tests/routing-benchmark.json"
ROUTER="$SCRIPT_DIR/master-route.sh"

PYTHON=""
# ★ 同 master-route.sh：Windows 上 python3 可能是 0 字节 Microsoft Store stub
#   （%LOCALAPPDATA%\Microsoft\WindowsApps\python3.exe），它不跑代码而是开商店。
#   所以真 python 优先，且必须真执行一次验证——光 command -v 不够（stub 也在 PATH 上）。
#   本处 2026-10-13 实测：旧写法（python3 优先、不验证）会让本脚本零输出 + rc=0 假绿。
for candidate in python python3; do
  if command -v "$candidate" >/dev/null 2>&1; then
    if "$candidate" -c 'import sys; sys.stdout.write("ok")' 2>/dev/null | grep -q '^ok$'; then
      PYTHON="$candidate"
      break
    fi
  fi
done
if [[ -z "$PYTHON" ]]; then
  echo 'ERROR: no usable Python 3 interpreter found.' >&2
  echo "HINT: on Windows, 'python3' may be the 0-byte Microsoft Store stub that opens the" >&2
  echo '      Store instead of running code. Point PATH at a real interpreter.' >&2
  exit 2
fi

"$PYTHON" - "$BENCHMARK" "$ROUTER" <<'PY'
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

benchmark_path = pathlib.Path(sys.argv[1])
router_path = pathlib.Path(sys.argv[2])
benchmark = json.loads(benchmark_path.read_text(encoding="utf-8-sig"))
cases = benchmark["cases"]

failures = []
passed = 0
print(f"=== Bash routing benchmark | {len(cases)} cases ===")

with tempfile.TemporaryDirectory(prefix="rs-routing-bash-") as scratch:
    root = pathlib.Path(scratch)
    for index, case in enumerate(cases):
        hint = case["hint"]
        expected = case["expect"]
        out_dir = root / str(index)
        result = subprocess.run(
            ["bash", str(router_path), "--hint", hint, "--out-dir", str(out_dir)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        got = "ERR"
        scope_path = out_dir / "route-scope.md"
        if result.returncode == 0 and scope_path.is_file():
            match = re.search(
                r"(?m)^- primary:[ \t]*(\S+)[ \t]*$",
                scope_path.read_text(encoding="utf-8"),
            )
            if match:
                got = match.group(1)

        if got == expected:
            passed += 1
        else:
            failures.append(
                f"hint={hint!r} expect={expected} got={got} exit={result.returncode}"
            )

    # Regression: when neither --project-root nor --out-dir is supplied, the
    # Bash router must behave like the PowerShell router and write under the
    # caller's current project, not under the installed reverse-skill package.
    source_skills = router_path.parent.parent
    source_config = source_skills / "config" / "routing.json"
    config = json.loads(source_config.read_text(encoding="utf-8-sig"))
    default_case = cases[0]
    default_skill_rel = pathlib.PurePosixPath(
        config["routes"][default_case["expect"]]["skill"]
    )

    fixture_package = root / "package"
    fixture_router = fixture_package / "skills" / "scripts" / "master-route.sh"
    fixture_config = fixture_package / "skills" / "config" / "routing.json"
    fixture_skill = fixture_package / "skills" / pathlib.Path(*default_skill_rel.parts)
    fixture_router.parent.mkdir(parents=True, exist_ok=True)
    fixture_config.parent.mkdir(parents=True, exist_ok=True)
    fixture_skill.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(router_path, fixture_router)
    shutil.copy2(source_config, fixture_config)
    shutil.copy2(source_skills / pathlib.Path(*default_skill_rel.parts), fixture_skill)

    caller_root = root / "caller-project"
    caller_root.mkdir()
    default_result = subprocess.run(
        ["bash", str(fixture_router), "--hint", default_case["hint"]],
        cwd=caller_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    default_scope_path = caller_root / "work" / "route" / "latest" / "route-scope.md"
    if default_result.returncode != 0:
        failures.append(
            "default-root router failed: "
            f"exit={default_result.returncode} stderr={default_result.stderr.strip()!r}"
        )
    elif not default_scope_path.is_file():
        failures.append(
            "default-root router did not write route-scope under work/route/latest: "
            f"found={list((caller_root / 'work').rglob('route-scope.md'))}"
        )
    else:
        default_scope = default_scope_path.read_text(encoding="utf-8")
        project_match = re.search(
            r"(?m)^- project_root:[ \t]*(.+?)[ \t]*$",
            default_scope,
        )
        if not project_match:
            failures.append("default-root route-scope missing project_root")
        elif pathlib.Path(project_match.group(1)).resolve() != caller_root.resolve():
            failures.append(
                "default-root project_root mismatch: "
                f"got={project_match.group(1)!r} expect={str(caller_root.resolve())!r}"
            )
        else:
            print("[PASS] default root -> caller project")

print(f"TOTAL={len(cases)} PASS={passed} FAIL={len(failures)}")
if failures:
    for failure in failures:
        print(f"[FAIL] {failure}", file=sys.stderr)
    raise SystemExit(1)

print(f"OVERALL: ALL PASS ({passed} routing cases + default-root regression)")
PY
