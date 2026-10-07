# Coordination contract (T17)

Authority for who owns what stays in `docs/WORK-BOARD.md` (coordinator file,
not touched by this card). This document only describes the machine-testable
half: contracts, leases, DAG, quarantine, telemetry. Anything here that
conflicts with WORK-BOARD or the spec loses.

## 1. Ownership / lease contract

Machine file: `docs/coordination/ownership-contract.json` (transcribed from
spec 12.0 plus the wave2-6 scope matrices in `work/wave*-briefs.md`).

Claim format (one entry per agent):

```json
{"agent": "C", "card": "C/T11", "wave": "wave2",
 "files": ["skills/scripts/community-route.py"],
 "lease": {"token": "wave2-lease", "expires_utc": "2099-01-01T00:00:00+00:00"}}
```

Checker: `scripts/check-coordination-ownership.py --contract C --claims Q`.
Exit 0 clean, 10 unknown file (needs T00 ruling, fail-closed toward review),
20 violation (cross-scope write, double claim, missing or expired lease).
Lease rule follows 17.10: write only with a live lease; a failed or vanished
agent's lease is released and its candidate stays sealed, never overwriting
the verified tree.

## 2. Merge DAG

Machine file: `docs/coordination/merge-dag.json`. Real edges from the briefs:
T12+T14 merged into one card (same files, must not split); T21 after T12+T14;
T18 after U9 (same routing domain); T23 after T16 (needs the release bundle).
Same-wave cards run parallel only when their matrix scopes are disjoint.

Checker: `scripts/check-merge-order.py --dag D --order A,B,C`.
Exit 0 respected, 21 rejected (illegal sequence or unknown node, fail-closed).
Proven: `T12+T14,T21,U9,T18,T16,T23` exits 0;
`T21,T12+T14,T18,U9` exits 21 naming both broken edges.

## 3. Quarantine

Per 17.11, per source / wrapper / capability. Tool:
`scripts/quarantine-source.py --registry R --quarantine ID --out O --audit A`.
Exit 0 quarantined, 23 unknown id. The narrowed registry keeps every other
source byte-identical; the audit record carries event, time, actor, reason.
Isolation target in this project is the physical `community-raw/**` area plus
registry `sources[]` trust fields such as `license_status=review-required`
(real carrier, e.g. the missing-license source). Recovery is re-validation
followed by re-inclusion, never a whole-framework rollback.

## 4. Telemetry (frozen per 17.32)

Field set: `docs/coordination/telemetry-schema.json` (17.12 metrics minus
everything sensitive). Tool: `scripts/coordination-telemetry.py`:

- `emit`: default off (env `COORD_TELEMETRY`, default `0`). Disabled mode
  performs the wrapped operation identically and writes nothing; proven by
  diffing disabled vs enabled stdout. Unknown fields are dropped, counted in
  the counter file, never persisted. Enabled mode appends hash-chained
  records; `verify` exits 0 intact, 24 on any truncation or rewrite (reported,
  never silently rebuilt).
- `upload`: exits 22 unless a recorded approval artifact (`approved_by` +
  `reason`) is supplied; even then the payload is only staged to a local
  outbox. No network code exists in the file by design, so remote upload
  cannot be switched on by accident or by a remote party.

Retention and export redaction follow 17.8 (see section 6).

## 5. Sensitive-output scan

No duplicate rule set: `scripts/redact-output.py` imports `SECRET_PATTERNS`
(and only that set) from the T06-owned
`skills/scripts/verify-repository-security.py` and replaces every hit with
`[REDACTED]`. Proven: a runtime-assembled sample trips 3 of the scanner's own
patterns and 0 survive redaction while benign text is untouched. Dangerous
samples are never written literally into docs or fixtures: they are assembled
by concatenation at runtime (e.g. `AK` + `IA` + 16 chars, key-block header in
two halves), so the security gate sees no new literals.

## 6. Retention / redaction rules (per 17.8)

Token, cookie, password, PII, customer data and real target material are
redacted at the telemetry boundary (unknown/sensitive fields never persist).
Raw artifacts are not retained in the repo; quarantine keeps a non-executable
audit snapshot only. Case export redaction and deletion responsibility follow
the owning card's lifecycle; this contract defines the mechanism (drop+count,
stage-only upload), not the calendar.

## 7. What is only described, not machine-verified

- Human approval for release and for telemetry upload: the harness checks
  that an approval artifact exists and is shaped correctly, not that the
  human meant it. That judgment lives with the coordinator.
- Cross-agent wall-clock serialization (who merges first in a real race):
  the DAG refuses illegal orders but does not schedule agents.
- Lease issuance identity: token+expiry shape is verified, the issuer is not.
- Full retention calendar and deletion enforcement: mechanism only (see 6).
- Why off is the default: collection without consent turns the observer
  into a leak surface (17.32 sits beside `autoInstall=false`); a default-on
  switch could be flipped remotely, a default-off one cannot. So the code
  path that sends data simply does not exist until a recorded approval plus
  an explicit transport are both present.

## 8. Fixtures (all in `tests/coordination/`, all exit 0)

| Fixture | Proves |
|---|---|
| `test_ownership_conflict.py` | disjoint claims 0, cross-scope claim 20 |
| `test_failure_recovery.py` | disturbed tree 30, isolated rerun 0, stale lease 20, renewed 0, tree intact |
| `test_quarantine.py` | one source isolated, rest byte-identical, unknown id 23 |
| `test_telemetry.py` | off-by-default with identical results, drop+count, tamper 24, upload 22 |
| `test_sensitive_scan.py` | 3 scanner hits in, 0 out, benign text intact |

Suggested WORK-BOARD note for the coordinator (not written by this card):
T17 harness exists under `scripts/check-coordination-ownership.py`,
`scripts/check-merge-order.py`, `scripts/quarantine-source.py`,
`scripts/coordination-telemetry.py`, `scripts/redact-output.py` with contracts
in `docs/coordination/`; wiring them into `skills/tests/ci-gates.json` needs
the T10 owner's decision.
