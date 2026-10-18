"""Coordination telemetry: frozen field set, hash-chained log, upload default off.

Subcommands:
  emit   --schema S --log L [--counter C] --event E [--field k=v ...]
         (--enabled 0/1, default from COORD_TELEMETRY env, default off)
  verify --schema S --log L            -> 0 intact | 24 tamper detected
  upload --schema S --payload P [--approval A] [--outbox DIR]
         -> 22 refused (default off); with a valid approval artifact the
            payload is only staged to a local outbox, never sent (no
            network code exists in this file by design).
Unknown fields are dropped and counted in the counter file, never persisted.
Disabled mode performs the wrapped operation identically and writes nothing.
Only stdlib. No network.
"""
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

GENESIS = "GENESIS"

def load_json(path, default):
    try:
        return json.load(open(path, encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return default

def parse_args(argv):
    if not argv:
        return None, {}
    cmd = argv[0]
    opts = {"field": []}
    i = 1
    while i < len(argv):
        key = argv[i]
        if key == "--field" and i + 1 < len(argv):
            opts["field"].append(argv[i + 1]); i += 2
        elif key.startswith("--") and i + 1 < len(argv):
            opts[key[2:].replace("-", "_")] = argv[i + 1]; i += 2
        else:
            print("bad arg: %s" % key, file=sys.stderr)
            return None, {}
    return cmd, opts

def chain_digest(prev_hash, record):
    body = prev_hash + json.dumps(record, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()

def cmd_emit(opts):
    schema = json.load(open(opts["schema"], encoding="utf-8"))
    allowed = set(schema["envelope"]) | set(schema["metrics"])
    enabled = opts.get("enabled", os.environ.get("COORD_TELEMETRY", "0"))
    enabled = str(enabled).strip().lower() in ("1", "true", "yes", "on")
    fields, dropped = {}, 0
    for item in opts.get("field", []):
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        if key in allowed:
            fields[key] = value
        else:
            dropped += 1
    # The wrapped operation result is identical either way (no degradation).
    result = {"status": "operation_complete", "event": opts.get("event", "op")}
    if dropped:
        counter_path = opts.get("counter")
        counter = load_json(counter_path, {"dropped_unknown": 0}) if counter_path else {"dropped_unknown": 0}
        counter["dropped_unknown"] = counter.get("dropped_unknown", 0) + dropped
        if counter_path:
            json.dump(counter, open(counter_path, "w", encoding="utf-8"), ensure_ascii=False, sort_keys=True)
    if not enabled:
        print(json.dumps(result, ensure_ascii=False))
        return 0
    log_path = opts["log"]
    prior = load_json(log_path, [])
    prev_hash = prior[-1]["digest"] if prior else GENESIS
    record = {
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "event": opts.get("event", "op"),
        "card": opts.get("card", "unknown"),
        "run_id": opts.get("run_id", "local"),
        "fields": fields,
        "prev_hash": prev_hash,
    }
    record["digest"] = chain_digest(prev_hash, {k: v for k, v in record.items() if k != "digest"})
    prior.append(record)
    json.dump(prior, open(log_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1, sort_keys=True)
    print(json.dumps(result, ensure_ascii=False))
    return 0

def cmd_verify(opts):
    entries = load_json(opts["log"], None)
    if not isinstance(entries, list):
        print("log unreadable or corrupt, refusing to rebuild")
        return 24
    prev = GENESIS
    for index, entry in enumerate(entries):
        if entry.get("prev_hash") != prev:
            print("tamper at entry %d: chain link broken" % index)
            return 24
        expect = chain_digest(prev, {k: v for k, v in entry.items() if k != "digest"})
        if entry.get("digest") != expect:
            print("tamper at entry %d: digest mismatch" % index)
            return 24
        prev = entry["digest"]
    print("telemetry log intact: %d entr(ies)" % len(entries))
    return 0

def cmd_upload(opts):
    approval = load_json(opts["approval"], None) if opts.get("approval") else None
    if not approval or not approval.get("approved_by") or not approval.get("reason"):
        print("remote upload disabled by default; a recorded approval artifact is required")
        return 22
    outbox = opts.get("outbox")
    if not outbox:
        print("approval present but no transport is configured in this environment; nothing sent")
        return 22
    os.makedirs(outbox, exist_ok=True)
    payload = load_json(opts["payload"], {})
    staged = os.path.join(outbox, "telemetry-staged.json")
    json.dump({"approval": approval, "payload": payload}, open(staged, "w", encoding="utf-8"), ensure_ascii=False, indent=1, sort_keys=True)
    print("approval accepted; payload staged locally (no network transport), nothing sent")
    return 0

def main():
    if any(a in ("-h", "--help") for a in sys.argv[1:]):
        print("usage: coordination-telemetry.py (emit|verify|upload) ...\n\n" + __doc__.strip())
        return 0
    cmd, opts = parse_args(sys.argv[1:])
    if cmd == "emit" and opts.get("schema") and opts.get("log") is not None:
        return cmd_emit(opts)
    if cmd == "verify" and opts.get("schema") and opts.get("log"):
        return cmd_verify(opts)
    if cmd == "upload" and opts.get("schema") and opts.get("payload"):
        return cmd_upload(opts)
    print("usage: coordination-telemetry.py (emit|verify|upload) ...", file=sys.stderr)
    return 2

if __name__ == "__main__":
    sys.exit(main())
