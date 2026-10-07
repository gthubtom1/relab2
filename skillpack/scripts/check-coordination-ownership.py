"""Ownership / lease validator: decides whether an agent wrote outside its files.

Reads docs/coordination/ownership-contract.json plus a claims file:
  {"claims": [{"agent": "A", "card": "A/U11", "wave": "wave2",
               "files": [...], "lease": {"token": ..., "expires_utc": ...}}]}
Exit codes: 0 clean | 10 needs T00 ruling (unknown file) | 20 violation.
Only stdlib. No network, no git writes.
"""
import fnmatch
import json
import sys
from datetime import datetime, timezone

def parse_args(argv):
    out = {"contract": None, "claims": None, "now": None}
    i = 0
    while i < len(argv):
        if argv[i] == "--contract" and i + 1 < len(argv):
            out["contract"] = argv[i + 1]; i += 2
        elif argv[i] == "--claims" and i + 1 < len(argv):
            out["claims"] = argv[i + 1]; i += 2
        elif argv[i] == "--now" and i + 1 < len(argv):
            out["now"] = argv[i + 1]; i += 2
        else:
            print("usage: check-coordination-ownership.py --contract C --claims Q [--now ISO]", file=sys.stderr)
            sys.exit(2)
    if not out["contract"] or not out["claims"]:
        print("usage: check-coordination-ownership.py --contract C --claims Q [--now ISO]", file=sys.stderr)
        sys.exit(2)
    return out

def norm(path):
    return path.replace("\\", "/").lstrip("./")

def owner_of(path, owners):
    """Return the owner entry whose pattern matches, or None. Exact wins over glob."""
    path = norm(path)
    for entry in owners:
        if norm(entry["file"]) == path:
            return entry
    for entry in owners:
        if fnmatch.fnmatchcase(path, norm(entry["file"])):
            return entry
    return None

def scope_of(card, wave, contract):
    for entry in contract.get("wave_scopes", {}).get(wave, []):
        if entry["card"] == card:
            return entry["scope"]
    return None

def main():
    args = parse_args(sys.argv[1:])
    contract = json.load(open(args["contract"], encoding="utf-8"))
    claims_doc = json.load(open(args["claims"], encoding="utf-8"))
    now = args["now"] or datetime.now(timezone.utc).isoformat()
    owners = contract.get("owners", [])
    violations, reviews = [], []
    # 1. lease liveness per claim.
    for claim in claims_doc.get("claims", []):
        lease = claim.get("lease") or {}
        if not lease.get("token") or not lease.get("expires_utc"):
            violations.append("%s/%s: write without a lease token+expiry" % (claim.get("agent"), claim.get("card")))
        elif lease["expires_utc"] <= now:
            violations.append("%s/%s: lease expired at %s" % (claim.get("agent"), claim.get("card"), lease["expires_utc"]))
    # 2. every touched file must be inside the claim's own scope...
    seen = {}
    for claim in claims_doc.get("claims", []):
        scope = scope_of(claim.get("card"), claim.get("wave"), contract)
        if scope is None:
            reviews.append("%s/%s: card not in wave matrix, needs T00 ruling" % (claim.get("agent"), claim.get("card")))
            continue
        for path in claim.get("files", []):
            if path in seen and seen[path] != claim.get("card"):
                violations.append("%s: claimed by both %s and %s" % (path, seen[path], claim.get("card")))
                continue
            seen[path] = claim.get("card")
            if not any(fnmatch.fnmatchcase(norm(path), norm(pattern)) for pattern in scope):
                hit = owner_of(path, owners)
                if hit is not None:
                    violations.append("%s: %s wrote outside scope, owner is %s" % (path, claim.get("card"), hit["owner"]))
                else:
                    reviews.append("%s: %s wrote off-table file, needs T00 ruling" % (path, claim.get("card")))
    # 3. ...and must not belong to another card's scope in the same wave.
    for claim in claims_doc.get("claims", []):
        for other in contract.get("wave_scopes", {}).get(claim.get("wave"), []):
            if other["card"] == claim.get("card"):
                continue
            for path in claim.get("files", []):
                if any(fnmatch.fnmatchcase(norm(path), norm(pattern)) for pattern in other["scope"]):
                    label = "%s: %s touches %s scope" % (path, claim.get("card"), other["card"])
                    if label not in violations:
                        violations.append(label)
    if violations:
        print("OWNERSHIP VIOLATION (%d):" % len(violations))
        for item in violations:
            print("  - " + item)
        return 20
    if reviews:
        print("NEEDS T00 RULING (%d):" % len(reviews))
        for item in reviews:
            print("  - " + item)
        return 10
    print("ownership ok: %d file(s) inside scope, leases live" % len(seen))
    return 0

if __name__ == "__main__":
    sys.exit(main())
