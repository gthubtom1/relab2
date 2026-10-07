"""Single-source quarantine: isolate one source without touching the others.

Usage: quarantine-source.py --registry REG --quarantine ID --out OUT --audit AUDIT
  [--actor NAME] [--reason TEXT]
Removes the source from discovery/query/candidate surface, keeps an
audit record (event, time, actor, reason). Other sources pass through
byte-identical (compared in tests).
Exit codes: 0 quarantined | 23 unknown source id | 2 usage error.
Only stdlib. No network. Never deletes the input file.
"""
import copy
import json
import sys
from datetime import datetime, timezone

def main():
    reg_path = qid = out_path = audit_path = actor = reason = None
    argv = sys.argv[1:]
    i = 0
    while i < len(argv):
        key = argv[i]
        if key in ("--registry", "--quarantine", "--out", "--audit", "--actor", "--reason") and i + 1 < len(argv):
            value = argv[i + 1]
            if key == "--registry":
                reg_path = value
            elif key == "--quarantine":
                qid = value
            elif key == "--out":
                out_path = value
            elif key == "--audit":
                audit_path = value
            elif key == "--actor":
                actor = value
            else:
                reason = value
            i += 2
        else:
            print("usage: quarantine-source.py --registry R --quarantine ID --out O --audit A", file=sys.stderr)
            return 2
    if not all([reg_path, qid, out_path, audit_path]):
        print("usage: quarantine-source.py --registry R --quarantine ID --out O --audit A", file=sys.stderr)
        return 2
    registry = json.load(open(reg_path, encoding="utf-8"))
    sources = registry.get("sources", [])
    ids = [s.get("id") for s in sources]
    if qid not in ids:
        print("unknown source id '%s' (known: %s)" % (qid, ",".join(ids)), file=sys.stderr)
        return 23
    removed = next(s for s in sources if s.get("id") == qid)
    narrowed = copy.deepcopy(registry)
    narrowed["sources"] = [s for s in sources if s.get("id") != qid]
    json.dump(narrowed, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2, sort_keys=True)
    audit = {
        "event": "source_quarantined",
        "source_id": qid,
        "license_status": removed.get("license_status"),
        "actor": actor or "coordinator",
        "reason": reason or "quarantine requested",
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "remaining_sources": [s.get("id") for s in narrowed["sources"]],
    }
    json.dump(audit, open(audit_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2, sort_keys=True)
    print("quarantined '%s'; %d source(s) remain discoverable" % (qid, len(narrowed["sources"])))
    return 0

if __name__ == "__main__":
    sys.exit(main())
