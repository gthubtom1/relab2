# Contract strictness and case lifecycle (T25)

Authority: `docs/INTEGRATION-IMPLEMENTATION-SPEC.md` 4.6 (sole table),
4.7 (status/exit codes), 17.22 / 17.23 / 17.24 / 17.25.
Owner files touched by T25 are listed in §6; `schemas/**` and
`skills/community/registry.json` were NOT modified (see §5).

## 1. What T25 proves

- 4.6 profile -> network/auth/action single mapping, asserted row by row
  against `skills/config/profile-map.json` (machine form of the frozen table).
- 4.6 legacy migration table, all 11 spec rows asserted (§2).
- Unknown enums fail closed: unknown profile, unknown legacy value,
  profile/caller network-mode conflict all end in blocked/needs_review,
  never a silent pass.
- Case lease: two holders contend for one case, the loser gets
  `LEASE_DENIED` with exit 20 (spec 17.24).
- Checkpoint/resume: atomic checkpoint, resume token bound to
  case+generation+profile; mismatch is refused (exit 20).
- Idempotent artifacts: repeating the same artifact write is
  `IDEMPOTENT_SKIP` with bytes/mtime untouched; same name with different
  bytes is blocked, not overwritten.
- Numeric budget aligned with T11: `MAX_WRAPPER_CANDIDATES=5`,
  `MAX_TOTAL_REFERENCES=50`, `REFERENCE_LIMIT=3`; over budget stops with
  blocked/budget_exceeded, exit 20 (spec 17.25).

## 2. 4.6 migration-table row coverage (11/11, zero gaps)

Spec row -> alias keys -> evidence:

| # | Spec 4.6 row | Alias keys asserted | Evidence |
|---|---|---|---|
| 1 | `offline-sample` -> `offline_sample` | `offline-sample` | registry record `community-apk-reverse-community-293` (via profile-map `migration_evidence`) + live assertion |
| 2 | `offline-ctf` -> `offline_ctf` | `offline-ctf` | 35 registry records, sample `community-ctf-super-hub-001` |
| 3 | `authorized-lab` -> `authorized_lab` | `authorized-lab` | 139 registry records (all superseded by higher-precedence profiles) |
| 4 | `authorized-repository` -> `authorized_target_only` | `authorized-repository` | 154 registry records, sample `community-ai-fullstack-delivery-139` |
| 5 | `authorized-device` -> `authorized_target_only` | `authorized-device` | 1 registry record, sample `community-apk-reverse-community-293` |
| 6 | `defensive`/`defensive_review`/`defensive-review` -> `defensive_review` | 3 keys | 103 `defensive` registry records + 2 canonical/kebab fixtures |
| 7 | `local-project`/`local_project` -> `local_project` | 2 keys | 154 `local-project` registry records + canonical fixture |
| 8 | `lab`/`lab_only` -> `authorized_lab` | 2 keys | case-guard network-mode-name fixture + shorthand fixture |
| 9 | `authorized`/`auth`/`authorized_target_only` -> `authorized_target_only` | 3 keys | shorthand fixtures + canonical fixture |
| 10 | `offline`/`offline_only` conditional | 2 keys | conditional fixture (sample -> `offline_sample`, else `needs_review`) |
| 11 | `unrestricted_lab` must NOT map | 1 key | unsupported -> `needs_review` fixture |

Plus 6/6 profile->network rows (Table A), the 5-mode network enum
(Table B header), the no-second-vocabulary check (17.22), and the
unlisted-values -> needs_review policy. Total validator assertions on the
real tree: 52 pass / 0 fail. Uncovered spec rows: none.
Note: T02's `skills/scripts/test-contract-v2.py` already covers the same
migration table from the registry side; T25 is an independent second
coverage from the strictness side. Neither file was modified by the other.

## 3. Script -> status/exit map (spec 4.7)

| Script | 0 | 10 | 20 | 21/22 | 30 |
|---|---|---|---|---|---|
| `verify-contract-strictness.py` | matched (holds) | n/a | blocked (any violation) | n/a | failed (unparsable input) |
| `--selftest-unknown` | n/a | n/a | blocked (injection rejected, expected) | n/a | failed (injection slipped through) |
| `t25-case-lifecycle-lab.py` | ok | n/a | blocked (`LEASE_DENIED` / `RESUME_DENIED` / `budget_exceeded`) | n/a | failed (internal error) |
| `tests/contract/*.py` | all green | n/a | n/a | n/a | n/a (1 = test failure, plain convention) |

Legacy contracts are untouched: `case-guard` keeps `0/1/2`, `case-init`
keeps `0/1`; the new scripts use only the 4.7 table above.

## 4. `path` / `adapted_path` dual-key finding (T02 legacy)

Measured on the real `skills/community/registry.json` (293 skills):

- both keys present: 293/293
- `path == adapted_path`: 293/293 (zero divergences)
- sample: `community-ctf-super-hub-001`:
  both = `community-raw/ctf-super-hub/brainstorming/SKILL.md`

Conclusion: the keys are fully redundant today; no record distinguishes
them. Recommendation: delete one key (keep `adapted_path`, which names the
post-import location) or, if import history needs both, pin the
both-present-and-equal invariant in a machine gate. Either way the edit
belongs to T02 (registry owner); filed as CR-T25-04 below. T25 did not
touch the registry and asserts the current invariant instead of "fixing"
the data to look better.

## 5. Change requests (T25 may NOT apply these; `schemas/**` belongs to T02)

- CR-T25-01: tighten `schemas/**` with closed profile / network-mode /
  status / failure_reason enums mirroring 4.6+4.7. Reason: only code asserts
  them today. Impact: any document with a non-canonical value turns red.
  Migration: add enums as `additionalProperties: false`-compatible
  constraints behind a schema minor bump; keep `extensions` open per 4.x.
- CR-T25-02: machine gate for downstream-ID existence against the canonical
  skill registry. Reason: T25 checks uniqueness and no-wrapper->wrapper
  edges, but existence needs the canonical registry T02 owns. Impact:
  dangling downstream IDs block. Migration: T02 publishes the canonical ID
  list; gate warns for one release, then blocks.
- CR-T25-03: `tool_requirements` schema (capability ID + version + exit
  code + timeout + output cap) with a canonical allowlist. Reason: the
  registry currently carries no such field, so "commands must come from the
  allowlist" (17.23) is enforced only as absence. Impact: future tool
  fields without allowlist entries block. Migration: additive field first,
  enforcement second.
- CR-T25-04: `path`/`adapted_path` dedup (see §4). Reason: 293/293
  redundant. Impact: readers of either key. Migration: T02 deletes one key
  (or pins the equality gate), import pipeline updated in the same change.
- CR-T25-05: numeric budgets (5 / 50 / 3, plus per-reference char cap,
  per-script timeouts, artifact/log caps) into a schema or policy manifest.
  Reason: 17.25 requires budgets to live in schema/policy, today they live
  in code constants + `docs/community/LOADING-BUDGET.md`. Impact: budget
  drift blocks instead of going unnoticed. Migration: T02 adds a
  `budgets` section; T25 validator cross-checks it.

## 6. Files added by T25 (nothing else touched)

- `skills/scripts/verify-contract-strictness.py` (validator, read-only)
- `skills/scripts/t25-case-lifecycle-lab.py` (lease/checkpoint/artifact/budget lab, temp-dir only)
- `tests/contract/test_contract_strictness.py` (28 assertions, exit 0)
- `tests/contract/test_case_lifecycle.py` (17 assertions, exit 0)
- `docs/CONTRACT-STRICTNESS.md` (this file)

Not modified: `skills/scripts/community-route.py` (its fail-closed profile
logic was read, verified, and left intact), `schemas/**`,
`skills/community/registry.json`, `skills/config/*.json`, CI wiring,
coordination docs. No thresholds were loosened; no assertions deleted.
