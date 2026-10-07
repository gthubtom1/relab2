"""Fixture 4: telemetry per 17.32.

a) Off by default: emit with no flag and no env writes nothing, yet the
   wrapped operation result is identical to the enabled run (no degradation).
b) Unknown fields are dropped and counted, never persisted.
c) Append-only hash chain verifies (exit 0); a one-byte tamper is
   reported, not silently rebuilt (exit 24).
d) Remote upload is default off: no approval -> exit 22; approval plus
   outbox stages locally without any network transport.
Exit codes: 0 fixture behaved as specified | 1 fixture broken.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

def _detect_python():
    """Interpreter probe: REVERSE_SKILL_PYTHON -> sys.executable -> python3 -> python."""
    env = os.environ.get("REVERSE_SKILL_PYTHON")
    if env and os.path.isfile(env):
        return env
    if sys.executable and os.path.isfile(sys.executable):
        return sys.executable
    for name in ("python3", "python"):
        found = shutil.which(name)
        if found:
            return found
    return sys.executable or "python"

PY = _detect_python()
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TELEMETRY = os.path.join(ROOT, "scripts", "coordination-telemetry.py")
SCHEMA = os.path.join(ROOT, "docs", "coordination", "telemetry-schema.json")

def emit(work, extra=(), enabled=None, log="t.json", counter="c.json"):
    env = dict(os.environ)
    env.pop("COORD_TELEMETRY", None)
    cmd = [PY, TELEMETRY, "emit", "--schema", SCHEMA,
           "--log", os.path.join(work, log), "--counter", os.path.join(work, counter),
           "--event", "route", "--card", "C/T11", "--field", "route_hit=3"]
    for item in extra:
        cmd += ["--field", item]
    if enabled is not None:
        cmd += ["--enabled", enabled]
    return subprocess.run(cmd, capture_output=True, text=True, env=env)

def main():
    work = tempfile.mkdtemp(prefix="t17-telemetry-")
    # a) default off: nothing written, same operation result.
    proc_off = emit(work)
    off_log = os.path.join(work, "t.json")
    if proc_off.returncode != 0 or os.path.exists(off_log):
        print("FIXTURE BROKEN: default-off emit must exit 0 and write nothing")
        return 1
    proc_on = emit(work, enabled="1")
    if proc_on.returncode != 0 or not os.path.exists(off_log):
        print("FIXTURE BROKEN: enabled emit must persist one entry")
        return 1
    if proc_off.stdout.strip() != proc_on.stdout.strip():
        print("FIXTURE BROKEN: disabled mode changed the operation result")
        return 1
    print("default-off proven: same result %s, log untouched until enabled" % proc_off.stdout.strip())
    # b) unknown fields dropped and counted.
    counter_path = os.path.join(work, "c.json")
    before = json.load(open(counter_path, encoding="utf-8")).get("dropped_unknown", 0) if os.path.exists(counter_path) else 0
    proc = emit(work, extra=("target_url=x", "route_hit=4"), enabled="1")
    if proc.returncode != 0:
        print("FIXTURE BROKEN: superset emit must still exit 0")
        return 1
    after = json.load(open(counter_path, encoding="utf-8")).get("dropped_unknown", 0)
    entries = json.load(open(off_log, encoding="utf-8"))
    if after != before + 1:
        print("FIXTURE BROKEN: dropped counter must grow by 1 (%s -> %s)" % (before, after))
        return 1
    if any("target_url" in entry.get("fields", {}) for entry in entries):
        print("FIXTURE BROKEN: out-of-schema field reached the log")
        return 1
    print("superset proven: 1 field dropped, counter %d -> %d" % (before, after))
    # c) integrity: intact verifies, tamper is reported.
    proc = subprocess.run([PY, TELEMETRY, "verify", "--schema", SCHEMA, "--log", off_log],
                          capture_output=True, text=True)
    if proc.returncode != 0:
        print("FIXTURE BROKEN: intact log must verify")
        return 1
    with open(off_log, "r+", encoding="utf-8") as handle:
        body = handle.read()
        handle.seek(0)
        handle.write(" " + body[1:] if body.startswith("{") else body[:-1] + " ")
    proc = subprocess.run([PY, TELEMETRY, "verify", "--schema", SCHEMA, "--log", off_log],
                          capture_output=True, text=True)
    print("tampered verify: exit %d (%s)" % (proc.returncode, proc.stdout.strip()))
    if proc.returncode != 24:
        print("FIXTURE BROKEN: tamper must exit 24")
        return 1
    # d) upload default off.
    payload = os.path.join(work, "payload.json")
    json.dump({"entries": 1}, open(payload, "w", encoding="utf-8"))
    proc = subprocess.run([PY, TELEMETRY, "upload", "--schema", SCHEMA, "--payload", payload],
                          capture_output=True, text=True)
    print("upload without approval: exit %d" % proc.returncode)
    if proc.returncode != 22:
        print("FIXTURE BROKEN: unapproved upload must exit 22")
        return 1
    approval = os.path.join(work, "approval.json")
    json.dump({"approved_by": "user", "reason": "lab review"}, open(approval, "w", encoding="utf-8"))
    outbox = os.path.join(work, "outbox")
    proc = subprocess.run([PY, TELEMETRY, "upload", "--schema", SCHEMA, "--payload", payload,
                           "--approval", approval, "--outbox", outbox], capture_output=True, text=True)
    staged = os.path.join(outbox, "telemetry-staged.json")
    if proc.returncode != 0 or not os.path.exists(staged):
        print("FIXTURE BROKEN: approved payload must stage locally")
        return 1
    print("fixture ok: off-by-default, drop+count, tamper 24, upload 22 without approval")
    return 0

if __name__ == "__main__":
    sys.exit(main())
