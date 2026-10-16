# schemas/ — frozen machine contracts (owner: T02)

This directory turns the "planned interface" entries of
`docs/INTEGRATION-IMPLEMENTATION-SPEC.md` section 4.0 into files that exist and are
covered by tests.

| file | contract | version | status before T02 | status after T02 |
|---|---|---|---|---|
| `community-handoff-input.json` | HandoffInput (4.4) | `1.0` | planned | **file exists, validated by `skills/scripts/test-contract-v2.py`** |
| `community-handoff-output.json` | HandoffOutput (4.5) | `1.0` | planned | **file exists, validated by `skills/scripts/test-contract-v2.py`** |
| `carrier-manifest.json` | carrier manifest (4.0 table, T23) | `1.0` | planned | **schema exists; producer and digests are still T23** |

The registry keeps its own frozen version key: `skills/community/registry.json`
→ `schemaVersion: "1.0"` (4.0: the key name may not change and no
`schema_version` synonym may be added).

## Who reads each contract (callers checked against the tree, 2026-10)

This directory is entered from the skill layer by `skills/ops/README.md`
(contract-layer hub, section 机器契约) and `skills/SKILL.md` (关联资源). The column on
the right is the file that actually loads or enforces each contract — every schema here
has a live reader, and no reader depends on a schema that is not in this table.

| file | what it fixes | who reads / who enforces it |
|---|---|---|
| `auth-profile.json` | the shape of `work/<case>/auth-profile.json`: approver, targets, actions, validity window, proof, execution limits | `skills/scripts/verify-auth-profile.py:11-12,192` — the rules are implemented in code; a missing field, an expired window or a placeholder proof exits 20 and no default is ever filled in |
| `case-attestation.json` | the shape of `work/<case>/attestation.json`: the offline-reviewable binding the gate re-verifies | `skills/scripts/verify-auth-profile.py:13-15,292` — recomputes the digest chain (a copied `ready_for_act` line never recomputes) and `--issue-attestation` writes the record |
| `canonical-base-lock.json` | the T21 base-lock fields added to the single `source_kind=canonical-base` SourceRecord | `scripts/verify-canonical-base-lock.py` (`--require-signatures` exits 20 on an unsigned tree); cited by `skills/scripts/test-contract-v2.py:240` |
| `carrier-manifest.json` | the carrier manifest (4.0 table, T23) | `skills/scripts/test-contract-v2.py:564,607` (`load_schema`, plus a negative sample) |
| `community-handoff-input.json` | HandoffInput (4.4) | `skills/scripts/test-contract-v2.py:605`; `skills/scripts/community-route.py:1119`; `input_schema` of the wrappers in `skills/community/registry.json` |
| `community-handoff-output.json` | HandoffOutput (4.5) | `skills/scripts/test-contract-v2.py:606`; `skills/scripts/community-route.py:1121`; `output_schema` of the wrappers in `skills/community/registry.json` |
| `community-routing-signals.json` | the community routing-signal table (T26) | `skills/scripts/verify-routing-signals.py:65`; `skills/scripts/test-routing-signals.py:64` |
| `release-candidate.json` | the release candidate a build produces (the candidate declares this schema itself) | `scripts/build-release-candidate.py:235` (writes `"schema": "schemas/release-candidate.json"`); `scripts/verify-release-approval.py` |
| `release-approval.json` | the human approval record under `release-approvals/` | `.github/workflows/release.yml` (`environment: release-approval` gate); `scripts/verify-release-approval.py` |

`auth-profile.json` and `case-attestation.json` are shape declarations: no script loads
those two schema files, because `skills/scripts/verify-auth-profile.py` implements the
same rules directly — so a schema and its gate cannot drift apart. The other seven are
loaded as data by the scripts named above.

## What actually runs today

* `python skills/scripts/test-contract-v2.py` — loads the real registry, checks every
  4.1/4.2/4.3 required field, recomputes every `content_hash`, resolves every
  `allowed_context` through `skills/config/profile-map.json`, and validates a real
  handoff input/output sample and a carrier-manifest sample against the schemas in
  this directory with the bundled validator.
* `python skills/scripts/community-route.py --hint "..." --json` — fails closed on
  unknown enums and returns a derived `profile`/`network_profile` plus a
  `route_explanation`.

Everything else that the schemas describe is **shape only**: nothing in this
repository produces a signed release carrier yet (T23), and no canonical
`next_safe_steps` command allowlist exists yet (17.23/T23). A schema that exists is
not a claim that the producer exists.

## Conventions (4.0, frozen)

* registry fields and JSON Schema field names use `snake_case`; the only exception is
  the registry top-level version key `schemaVersion`;
* handoff input/output field names use `camelCase`;
* file and directory names use kebab-case;
* defined enum values are lowercase `snake_case`;
* identifiers are `<scope>-<source>-<slug>`, lowercase, no spaces;
* `additionalProperties: false` everywhere, with `extensions` as the single extension
  slot (lower snake_case keys, JSON-serializable values, ≤ 4096 bytes serialized).

## Validator subset and its limits

The contract test ships a dependency-free draft 2020-12 subset validator (the
repository must not depend on `jsonschema`; it is not installed on the build host).
This table is the whole supported vocabulary, and **any other keyword is reported as
an unsupported-keyword error instead of being ignored**, so a schema can never look
validated while a constraint silently does nothing.

| supported | notes |
|---|---|
| `type` | `object` / `array` / `string` / `integer` / `number` / `boolean` / `null` |
| `required` | object member names |
| `properties` | value schemas |
| `additionalProperties` | `false` or a schema |
| `items` | array element schema |
| `enum`, `const` | closed value sets (unknown values fail closed) |
| `oneOf` | exactly one branch must match |
| `minLength`, `maxLength` | string length in characters |
| `minimum`, `maximum` | numeric bounds |
| `pattern` | ECMA-262 style regular expression, anchored by the schema author |
| `minItems`, `maxItems` | array length |
| `maxProperties` | object member count |

Annotation-only keys that the validator ignores by design: `$schema`, `$id`, `title`,
`description`.

Not used anywhere in this directory, because they are outside the supported subset:
`$ref`/`$defs`, `allOf`/`anyOf`/`not`, `if`/`then`/`else`, `dependentRequired`,
`patternProperties`, `propertyNames`, `uniqueItems`, `format`, `contains`, `prefixItems`,
`unevaluatedProperties`. Cross-field rules of 4.5/4.7 that would need `if`/`then` are
therefore enforced by `skills/scripts/test-contract-v2.py` and must be enforced by the
policy layer as well.

Consequences you must not paper over:

1. `format: date-time` is not available; the schemas use an explicit RFC 3339 `pattern`.
2. The 4096-byte bound and the lower-snake_case key rule for `extensions` cannot be
   expressed in JSON Schema and are checked by the contract test.
3. `carrier-manifest.json` requires `sha256` on `kind: "file"` members only in prose;
   the contract test enforces it.
4. A full draft 2020-12 validator is still required before a redistributable release
   (T10/T23 must add it to CI, and this directory must then pass unmodified).

## Interpretation decisions recorded by T02

These are places where section 4 is ambiguous. Each one is implemented the same way in
code and in the migration document `docs/community/REGISTRY-V2-MIGRATION.md`.

1. `SkillRecord.adapted_path` — 4.2 writes `= 4.3 entrypoint`, while 4.2 also requires
   `entrypoint` to be the wrapper entry and says readers trust `adapted_path` alone.
   T02 resolves this as `adapted_path == path` (the adapted file), `entrypoint ==`
   wrapper path, and keeps `path` as a transitional duplicate. Reconciling the wording
   is a T00/T25 contract edit.
2. `SkillRecord` extra fields — 4.2 requires deleting `original_name`, `description`
   and `adapted` or moving them into the contract with a `schemaVersion` bump. T02 has
   no authority to edit the spec or the version, and `community-route.py` matching
   depends on those values, so they moved into the contracted `extensions` slot as
   `legacy_*` keys.
3. `network_profile` — it is not a handoff property at all, so an input carrying it
   fails schema validation (fail-closed) instead of being compared and rejected later.
4. `execution_profile` — 17.4 lists nine names whose first item is the object name
   itself; the object therefore has those eight properties as required members.

## Owners

* `schemas/**` — T02 (T25 changes the contract through a change request, never in
  parallel).
* `skills/config/profile-map.json` — T02.
* `carrier-manifest.json` producers, digests and fixtures — T23.
* CI wiring and a full draft 2020-12 validator — T10 (with T24 for the trust boundary).
