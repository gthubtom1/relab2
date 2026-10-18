# Registry v2 migration — decisions, evidence and open items (T02)

Owner: T02. Consumers: T03, T04, T05, T07-T10, T12, T13, T21, T23, T25.

This document records **why** `skills/community/registry.json` now looks the way it
does, what was measured rather than assumed, and which required fields are still
`null` and who owns them. It is the audit trail for the frozen contract in
`docs/INTEGRATION-IMPLEMENTATION-SPEC.md` section 4 (4.1 SourceRecord, 4.2
SkillRecord, 4.3 WrapperRecord, 4.4/4.5 handoff, 4.6 profiles, 4.7 status).

Nothing here overrides section 4. Where section 4 is ambiguous the resolution is
listed explicitly and mirrored in `schemas/README.md`.

---

## 1. What changed, file by file

| file | change |
|---|---|
| `skills/community/registry.json` | v2: 4 sources gained the 4.1 required fields; a new `wrappers[]` section (4.3) holds the four wrapper records; all 293 skill records gained the 4.2 required fields, migrated `allowed_context`, re-derived `content_type`; contract-external top-level fields moved into `extensions`. Counts unchanged: 4 sources / 293 skills / 55 excluded / `schemaVersion` `1.0`. |
| `schemas/community-handoff-input.json` | new. Draft 2020-12 HandoffInput, camelCase, `additionalProperties: false`, `extensions` slot, `hint` 1-4096, closed enums from 4.4/4.6/4.7, all eight 17.4 auth fields required, `network_profile` deliberately absent. |
| `schemas/community-handoff-output.json` | new. Draft 2020-12 HandoffOutput, all six 4.7 statuses, the eleven 4.7 failure reasons, `next_safe_steps` as typed action objects only, `untrusted_content` entries with record id + path + digest. |
| `schemas/carrier-manifest.json` | new. Draft 2020-12 carrier manifest 1.0 (4.0 table, T23 owner) with the 17.15 bundle members, digests, signature binding and the 17.18 fixture set. |
| `schemas/README.md` | new. What runs today, the validator keyword subset, its documented gaps, and the T02 interpretation decisions. |
| `skills/config/profile-map.json` | new. Machine-readable 4.6 profile table, the frozen legacy-value migration table, the deterministic single-profile resolution rule and the per-row migration evidence. |
| `skills/scripts/community-route.py` | enum validation (fail-closed), profile derivation from `profile-map.json`, wrapper metadata read from `registry.json.wrappers[]` instead of hardcoded paths/downstream lists, `route_explanation`, all six 4.7 statuses with their exit codes. The alias lexicon, tokeniser, scoring, confidence and tie rules are unchanged. |
| `skills/scripts/test-contract-v2.py` | new. Dependency-free draft 2020-12 subset validator plus registry, migration and schema tests. |
| `skills/scripts/test-community-route.py` | exit-code assertions added for the existing cases plus four fail-closed probes. No assertion was removed or weakened. |

Not touched: `skills/config/routing.json`, all wrapper bodies (`skills/community/*/SKILL.md`),
all community bodies, `docs/INTEGRATION-IMPLEMENTATION-SPEC.md`, `README*`,
`AGENTS.md`, `CLAUDE.md`, `.github/**`, `scripts/validate-integration.py`.

No `git add`, no `git commit`, no branch, no push.

---

## 2. SourceRecord (4.1)

The four existing records were completed in place. No source record was added or
removed; the `canonical-base` record is **not** T02's to add (17.15/T21), and the
contract test asserts its absence so T21 can add it deliberately.

| field | ctf-super-hub | hack-skills | ai-fullstack-delivery | apk-reverse-community |
|---|---|---|---|---|
| `source_kind` | community | community | community | community |
| `tree_digest` | `null` | `null` | `null` | `null` |
| `source_manifest` | `null` | `null` | `null` | `null` |
| `snapshot_root` | `null` | `null` | `null` | `null` |
| `importer_version` | `null` | `null` | `null` | `null` |
| `source_root` | `.` | `skills` | `workflows` | `skills/apk-reverse` |
| `license_declared` | `NOASSERTION` | `MIT` | `NONE` | `MIT` |
| `license_status` | `review-required` | `review-required` | `missing-license` | `verified` |
| `third_party_review` | required | required | required | not-required |
| `notice_file` | `docs/community/ctf-super-hub/THIRD_PARTY_NOTICES.md` | `docs/community/hack-skills/LICENSE` | `null` | `docs/community/apk-reverse-community/LICENSE` |
| `maturity` | partial | partial | unverified | partial |
| `distribution` | local-only | local-only | local-only | local-only |
| `adaptation_status` | imported | imported | imported | imported |
| `last_verified_at` | generation timestamp | same | same | same |

Evidence used for the license columns (all read locally, no network):

* `docs/community/ctf-super-hub/LICENSE` is literally titled "Mixed License Notice"
  and enumerates original and third-party parts → no single SPDX expression, hence
  `license_declared = NOASSERTION` and `third_party_review = required`.
  `license_status` is `review-required` rather than `mixed` because the third-party
  review is what is actually outstanding, and because 4.1's redistributable
  admission rule treats both values identically.
* `docs/community/hack-skills/LICENSE` is plain MIT text. The pre-T02 value
  `MIT-with-third-party-provenance-review` is not a member of the 4.1 enum, so it
  was migrated to the closest legal value that keeps the review obligation:
  `license_declared = MIT`, `third_party_review = required`,
  `license_status = review-required`. See section 7 for the resulting change in the
  validator warning count.
* `docs/community/ai-fullstack-delivery/` has no LICENSE at all →
  `license_declared = NONE`, `license_status = missing-license`, `notice_file = null`
  (4.1 only demands a real file for `review-required`, and no notice file exists in
  the repository; creating one is T04's allowance, not T02's).
* `docs/community/apk-reverse-community/LICENSE` is MIT, and the upstream tree
  declares "no vendored third-party binaries" in its own README, so
  `third_party_review = not-required` and `license_status = verified`.
  `distribution` is still `local-only` because `maturity = partial` fails the 4.1
  admission rule, so the license verdict does not widen distribution.

`distribution = local-only` for all four sources and all 293 records: no source
satisfies every 4.1 condition (verified license + `not-required` third-party review
+ verified maturity + real notice file), so claiming `redistributable` anywhere would
be an over-claim. The contract test re-checks the admission rule on every run.

### Nulls, with owners

| field | records | why it is `null` | owner |
|---|---|---|---|
| `tree_digest` | 4 | 4.1 defines it against an in-repo `snapshot_root`. The snapshots live outside the repository (`<开发根>/upstream/<repo>`, verified clean at the locked commits), so no digest recorded here could be verified from the repository, which 17.28 forbids. | T12 (snapshot materialisation + canonicalisation), T21 (canonical base) |
| `source_manifest` | 4 | No in-repo per-source manifest file exists. Creating one is not in T02's write allowance; `source-lock.json` belongs to T12. | T12 |
| `snapshot_root` | 4 | Same as `tree_digest`: 4.1 requires a repository-relative path and there is no in-repo snapshot. | T12 |
| `importer_version` | 4 | `scripts/adapt-community.py` declares no version constant, and inventing a semver would be fabrication. T05 must add one and re-import. | T05 |

The contract test prints this null inventory on every run, so it cannot silently
become permanent.

---

## 3. WrapperRecord (4.3) and the stale "hack-hub does not exist" claim

`docs/WORK-BOARD.md` E8 recorded that `skills/community/hack-hub/SKILL.md` does not
exist. **That is wrong.** Measured in this task:

```
Test-Path skills\community\hack-hub\SKILL.md  -> True   (2238 bytes)
git ls-tree -r HEAD --name-only | Select-String community/(hack-hub|ctf-hub|delivery|apk-extension)/
  skills/community/apk-extension/SKILL.md
  skills/community/ctf-hub/SKILL.md
  skills/community/delivery/SKILL.md
  skills/community/hack-hub/SKILL.md
```

All four wrapper files are tracked in `HEAD` (commit `93a0a4f`) and contain the
`## ACTION REQUIRED` section that `scripts/validate-integration.py` requires. There
are 297 `SKILL.md` files under `skills/community/`: 293 registry records plus exactly
these four wrappers. No wrapper path had to be invented or corrected; every wrapper
record now points at a real file, and the contract test asserts the file exists so a
future edit cannot silently reintroduce a dangling record.

| wrapper id | path (= `SkillRecord.entrypoint`) | source | route ids | references | context_map |
|---|---|---|---|---|---|
| `wrapper-ctf-super-hub` | `skills/community/ctf-hub/SKILL.md` | ctf-super-hub | R47 | 35 | `offline_ctf -> offline` |
| `wrapper-hack-skills` | `skills/community/hack-hub/SKILL.md` | hack-skills | R46 | 103 | `defensive_review -> offline` |
| `wrapper-ai-fullstack-delivery` | `skills/community/delivery/SKILL.md` | ai-fullstack-delivery | R48 | 154 | `local_project -> project_local` |
| `wrapper-apk-reverse-community` | `skills/community/apk-extension/SKILL.md` | apk-reverse-community | R49 | 1 | `offline_sample -> offline` |

Notes:

* `route_ids` were read from `skills/config/routing.json` (`R46`-`R49` are the four
  community routes) and are re-validated against that file on every contract-test run.
* `allowed_downstream` is the canonical-skill list that used to be hardcoded in
  `community-route.py`. All 20 entries exist as `skills/<id>/SKILL.md`
  (43 canonical skills are present); the contract test fails on any entry that is not.
* `reference_ids` lists the ids of the wrapper's own `discovery: reference-only`
  records, which makes "wrapper -> reference set" machine-readable. Together with
  `allowed_downstream` this removes the "wrapper/downstream hardcoded in the helper"
  blocker recorded in spec 1.4.
* `default_action = review` and `auto_execute = false` for all four (4.3: it must be
  `false` today), `maturity` mirrors the source.

---

## 4. SkillRecord (4.2)

Field values and the rule that produced them. All 293 records exist; no record was
added or removed.

| field | value | rule |
|---|---|---|
| `discovery` | `reference-only` | the adapted bodies are loadable only as references through a wrapper; they are not part of the discovery surface (17.27/T01). No record is `manifest-only` or `disabled` because none is withheld or quarantined. |
| `distribution` | `local-only` | 4.2 requires consistency with the source; all four sources are `local-only`. |
| `license_status` | copied from the source record | 4.2 says "consistent with the source"; `verified` 1, `review-required` 138, `missing-license` 154. |
| `maturity` | unchanged (`partial` 139, `unverified` 154) | already inside the enum. |
| `risk` | unchanged (`medium` 189, `high` 104) | already inside the enum. |
| `canonical_downstream` | filled for 6 records, `[]` for 287 | see below. |
| `reference_ids` | `[]` for all 293 | 4.2 allows an empty array; there is no recorded per-record reference graph, and T02 will not invent one. The wrapper-level relation is in `wrappers[].reference_ids`. |
| `content_hash` | `sha256:<64 hex>` recomputed from the file bytes | digest of the raw bytes of `path` (the importer writes LF, so no newline normalisation is involved). The contract test recomputes all 293 and fails on any drift, so a body edit by another task is detected rather than ignored. |
| `path_status` | `clean` for all 293 | every `path` resolves to an existing file; the contract test re-checks existence, uniqueness and the `clean` claim. Deep-link breakage inside the bodies is T03's `needs-rewrite` scope, not this field. |
| `keywords` | unchanged | the generator verified 1-32 lower-case unique entries before writing; zero records needed repair. |
| `adapted_path` | identical to `path` | see the transitional rule below. |
| `entrypoint` | the source's wrapper path | 4.2 forbids pointing at a raw vendor file; the contract test requires `entrypoint` to equal one of the four wrapper paths. |

### 4.1 Transitional `path` + `adapted_path` duplicate

`scripts/validate-integration.py` (T04) reads `item["path"]` and requires the file to
exist and to be unique, and `community-route.py` sorts references by `path`. So:

> `path` and `adapted_path` both exist and hold **identical** values. This is a
> declared transitional state, not two spellings of the truth. The duplicate `path`
> key must be deleted once T04's validator and the helper read `adapted_path`; the
> removal is scheduled to **T25** (contract strictness). Until then, any divergence
> between the two keys is a test failure.

4.2's glossary writes `adapted_path = 4.3 entrypoint`, which cannot be reconciled
with 4.2's own requirement that readers trust `adapted_path` alone and that
`entrypoint` is the wrapper entry. T02 resolved it as
`adapted_path == path`, `entrypoint == wrapper path`, and asks T00/T25 to reword 4.2.

### 4.2 Contract-external fields moved into `extensions`

The pre-T02 records carried `original_name`, `description` and `adapted` at the top
level. 4.2 requires deleting them or bringing them into the contract with a
`schemaVersion` bump. T02 may not edit the spec or the version, and
`community-route.py`'s matching lexicon is built from those two strings, so they were
moved into the contracted `extensions` slot as `legacy_original_name`,
`legacy_description` and `legacy_adapted`, next to `legacy_allowed_context`
(section 5). `extensions` is the only extension slot allowed by 4.0 rule 4; keys are
lower snake_case, values are JSON-serialisable, and the largest observed serialized
object is 590 bytes against the 4096-byte bound. The contract test rejects any
top-level field outside the 4.2 set, so the move cannot regress.

### 4.3 `canonical_downstream`

`skills/community/canonical-mapping.json` is the only recorded source-to-canonical
mapping. It was applied where it is evidence: the record's `source_path` top-level
directory equals a mapping key.

* filled: `ctf-reverse`, `ctf-pwn`, `ctf-web`, `ctf-forensics`, `ctf-malware`,
  `ctf-osint` (6 records, each with the mapping's canonical list, all verified to
  exist as `skills/<id>/SKILL.md`);
* empty for the other 287 records, which 4.2 explicitly permits. The alternative
  would have been to copy the wrapper's `allowed_downstream` into every record, which
  would claim a per-record usefulness that no evidence supports. Per-record mapping
  evidence, if it appears, belongs to T07/T08/T09 with T02 re-running the generator.

**Defect found while validating this field:** `canonical-mapping.json` maps
`ai-delivery-security` to `security-engineer`, and **no canonical skill with that id
exists** (43 canonical skills are present; `skills/security-engineer/SKILL.md` is
not one of them). T02 therefore refused to copy it into any record and reports it
here. 17.23 requires every downstream id to exist, so the mapping file needs an
owner. It is not in the 12.0 owner table; T00 must assign it (candidate owners:
T03 for the community metadata files, or T08 for the delivery source).

---

## 5. The 4.6 profile migration

### 5.1 Rule (decidable, fail-closed, machine-readable)

`skills/config/profile-map.json` holds the frozen 4.6 profile table, the frozen
legacy-value table, and the resolution rule:

1. expand every legacy `allowed_context` value through the migration table into a set
   of canonical profiles;
2. if the set has one member, that is the record's profile;
3. if it has more than one, keep the single member with the highest rank in the
   frozen precedence array

   ```
   offline_sample > offline_ctf > defensive_review > local_project > authorized_lab > authorized_target_only
   ```

   whose axis is **narrowest network egress first** (`offline` < `project_local` <
   `lab_only` < `authorized_target_only`), with narrower allowed action as the
   tie-break inside one network mode. No current record collides inside a single
   network mode, so the in-mode tie-break is declared but not exercised by real data;
4. a value that the table lists as unsupported stays `needs_review`
   (`unrestricted_lab`), and a value the table does not list at all is a contract
   violation that is never guessed.

So every record ends with **exactly one** canonical profile, as 4.6 demands, and the
selected value never grants more egress or more action than the values it replaced.

**Rejected alternative:** widest-egress-first would have mapped the 103 hack-skills
records to `authorized_lab` and the 154 delivery records to `authorized_target_only`.
That widens the declared context of untrusted vendor references without per-record
evidence, which is exactly the "guess in order to let it through" that 4.6 forbids.
If T09's Hack chain later needs lab-context references, that is a contract change to
be made by T25 in `profile-map.json` and the registry together, not by guessing here.

### 5.2 Row-by-row evidence

Counts were measured on the pre-T02 registry (293 records) and are **recomputed** by
`test-contract-v2.py` from `extensions.legacy_allowed_context`, so they cannot drift.
Rows with zero real records are covered by executable fixtures, as 17.22 allows.

| 4.6 legacy value | canonical profile | records affected | real sample (registry) / fixture | note |
|---|---|---:|---|---|
| `offline-sample` | `offline_sample` | 1 | `community-apk-reverse-community-293` | |
| `offline-ctf` | `offline_ctf` | 35 | `community-ctf-super-hub-001` | selected for all 35 CTF records |
| `authorized-lab` | `authorized_lab` | 139 | `community-ctf-super-hub-001` | 35 ctf + 103 hack + 1 apk; every one of them resolved to a narrower profile, so no record carries `authorized_lab` after migration |
| `authorized-repository` | `authorized_target_only` | 154 | `community-ai-fullstack-delivery-139` | target kind: repository allowlist |
| `authorized-device` | `authorized_target_only` | 1 | `community-apk-reverse-community-293` | target kind: device identifier |
| `defensive` | `defensive_review` | 103 | `community-hack-skills-036` | selected for all 103 hack-skills records |
| `local-project` | `local_project` | 154 | `community-ai-fullstack-delivery-139` | selected for all 154 delivery records |
| `defensive_review` | `defensive_review` | 0 | fixture `alias_is_already_canonical` | |
| `defensive-review` | `defensive_review` | 0 | fixture `kebab_variant_of_defensive_review` | |
| `local_project` | `local_project` | 0 | fixture `alias_is_already_canonical` | |
| `lab` | `authorized_lab` | 0 | fixture `lab_shorthand_maps_to_authorized_lab` | |
| `lab_only` | `authorized_lab` | 0 | fixture `case_guard_network_mode_name` | |
| `authorized` | `authorized_target_only` | 0 | fixture `authorized_shorthand` | |
| `auth` | `authorized_target_only` | 0 | fixture `auth_shorthand` | |
| `authorized_target_only` | `authorized_target_only` | 0 | fixture `alias_is_already_canonical` | |
| `offline` | sample present → `offline_sample`, else `needs_review` | 0 | fixture `sample_present_yields_offline_sample_else_needs_review` | both branches asserted |
| `offline_only` | sample present → `offline_sample`, else `needs_review` | 0 | fixture `sample_present_yields_offline_sample_else_needs_review` | both branches asserted |
| `unrestricted_lab` | **not mapped** | 0 | fixture `unsupported_must_report_needs_review` | registered as `unsupported`; the resolver returns `needs_review` and never `authorized_lab` |

### 5.3 Result per source

| source | records | legacy values | selected profile |
|---|---:|---|---|
| ctf-super-hub | 35 | `offline-ctf`, `authorized-lab` | `offline_ctf` (35) |
| hack-skills | 103 | `authorized-lab`, `defensive` | `defensive_review` (103) |
| ai-fullstack-delivery | 154 | `local-project`, `authorized-repository` | `local_project` (154) |
| apk-reverse-community | 1 | `offline-sample`, `authorized-device`, `authorized-lab` | `offline_sample` (1) |

### 5.4 Nothing was dropped silently

All 293 records carried more than one legacy value (292 with two, one with three), so a
single-value rule had to drop something. No information is lost:

* the raw pre-migration list is preserved per record in
  `extensions.legacy_allowed_context`;
* the full legacy→canonical expansion is in `profile-map.json`;
* this table states, per row, how many records carried the value and how many records
  still carry the mapped canonical profile (for `authorized_lab`,
  `authorized-repository`, `authorized-device` and `local-project`-with-repository:
  none, because a higher-precedence value won);
* the contract test recomputes every count from the registry.

---

## 6. `content_type` re-derivation

The pre-T02 values were a blanket rule of the importer
(`"workflow" if source == "ai-fullstack-delivery" else "methodology"`), which the task
explicitly forbids keeping. T02 re-derived all 293 values from the adapted bodies
using the worked-out rule below; the value is data, so the rule and its evidence are
recorded here rather than hidden in the generator.

Definitions used (the spec fixes the enum but not the boundaries):

* `tooling` — the document is a single-tool command playbook;
* `workflow` — the document dispatches to other capabilities or defines a staged
  process (hub/router/scheduler/testing mode);
* `reference` — the document is a lookup catalogue rather than a procedure;
* `methodology` — the document explains how to do the work (technique, principles,
  checklist, implementation guide).

Rule, applied to the body after removing the injected
`## Integrated reverse-skill contract` section (first match wins):

1. `tooling` if the H1 matches `CLI Playbook$` or `^<single token> 用法$`;
2. `workflow` if the H1, the record's original name or an H2 named `Skill Map` /
   `Recommended Flow` / `统一入口` carries a dispatch marker
   (`总控|入口|分流|总览|调度|工作流|Router|Hub|Mode|Workflow|Skill Map`, Latin markers
   word-bounded so that `GitHub` and `Modeling` do not match);
3. `reference` if an H1/H2 carries a catalogue marker
   (`参考|Reference|速查|Cheat|索引|Index|矩阵|Matrix|对照表|大全`) **and** table rows are
   at least 40% of the non-blank lines;
4. otherwise `methodology`.

Result: `methodology` 259, `workflow` 29, `tooling` 5, `reference` 0. 156 records
changed value (all from the blanket values).

Every non-`methodology` decision and its trigger:

| record | from → to | trigger |
|---|---|---|
| `community-ctf-super-hub-003` | methodology → workflow | H1 `CTF 新手入口` |
| `community-ctf-super-hub-011` | methodology → workflow | H1 `CTF 超级总控` |
| `community-ctf-super-hub-014` | methodology → workflow | original name `CTF•挑战调度器` |
| `community-ctf-super-hub-016` | methodology → workflow | H1 `Strix 新手入口` |
| `community-ctf-super-hub-020` | methodology → tooling | H1 `ffuf CLI Playbook` |
| `community-ctf-super-hub-021` | methodology → tooling | H1 `httpx CLI Playbook` |
| `community-ctf-super-hub-025` | methodology → tooling | H1 `Katana CLI Playbook` |
| `community-ctf-super-hub-026` | methodology → tooling | H1 `Nuclei CLI Playbook` |
| `community-ctf-super-hub-029` | methodology → workflow | H1 `Quick Testing Mode` |
| `community-ctf-super-hub-032` | methodology → tooling | H1 `sqlmap CLI Playbook` |
| `community-ctf-super-hub-034` | methodology → workflow | H1 `Standard Testing Mode` |
| `community-hack-skills-046` | methodology → workflow | H1 `API Security Router` |
| `community-hack-skills-049` | methodology → workflow | H1 `Authentication and Authorization Router` |
| `community-hack-skills-053` | methodology → workflow | H1 `Business Logic Router` |
| `community-hack-skills-072` | methodology → workflow | H1 `File Access Router` |
| `community-hack-skills-076` | methodology → workflow | manual adjudication: hack-skills master router (`Role Routing`, `Task Start Gate`), the only record with no H1 marker |
| `community-hack-skills-083` | methodology → workflow | H1 `Injection Testing Router` |
| `community-hack-skills-109` | methodology → workflow | H1 `Recon and Methodology Router` |
| `community-ai-fullstack-delivery-144` | workflow → workflow | H1 `AI/算法工程师 Skills 总控` |
| `community-ai-fullstack-delivery-153` | workflow → workflow | H1 `API 设计 Skills 总控` |
| `community-ai-fullstack-delivery-161` | workflow → workflow | H1 `自动化测试 Skills 总控` |
| `community-ai-fullstack-delivery-173` | workflow → workflow | H1 `后端工程师 Skills 总控` |
| `community-ai-fullstack-delivery-179` | workflow → workflow | H1 `数据分析师 Skills 总控` |
| `community-ai-fullstack-delivery-187` | workflow → workflow | H1 `数据库工程师 Skills 总控` |
| `community-ai-fullstack-delivery-197` | workflow → workflow | H1 `DevOps 工程师 Skills 总控` |
| `community-ai-fullstack-delivery-207` | workflow → workflow | H1 `前端工程师 Skills 总控` |
| `community-ai-fullstack-delivery-217` | workflow → workflow | H1 `全栈工程师 Skills 总控` |
| `community-ai-fullstack-delivery-229` | workflow → workflow | H1 `产品经理 Skills 总控` |
| `community-ai-fullstack-delivery-234` | workflow → workflow | H1 `工作流交接协议` |
| `community-ai-fullstack-delivery-242` | workflow → workflow | H1 `项目经理 Skills 总控` |
| `community-ai-fullstack-delivery-252` | workflow → workflow | H1 `测试工程师 Skills 总控` |
| `community-ai-fullstack-delivery-261` | workflow → workflow | H1 `安全工程师 Skills 总控` |
| `community-ai-fullstack-delivery-271` | workflow → workflow | H1 `SRE/运维 Skills 总控` |
| `community-ai-fullstack-delivery-289` | workflow → workflow | H1 `UI/UX 设计 Skills 总控` |

The remaining 138 delivery records moved `workflow → methodology`: their H1 is a topic
title (`领域建模（Domain Modeling）`, `缓存策略（Caching Strategy）`, ...) and their bodies
are `适用场景 / 核心原则 / 实现` guides, i.e. methodology rather than orchestration. The
blanket `workflow` label came from the name of the upstream package
(`AI-Fullstack-Delivery-Workflow`), not from the content.

Honest limits of this rule:

* `reference` ends up unused. The closest candidates were documents with 30-40% table
  rows (`hack-skills/binary-protection-bypass` 86/224, `hack-skills/heap-exploitation`
  58/163, `hack-skills/type-juggling` 69/213) that also carry a full technique narrative,
  so they stayed `methodology`. If T13 wants a different boundary it must change the
  threshold in the rule and re-run, not flip individual values.
* This is a structural heuristic, not a semantic reading of all 293 documents. The
  trigger for every changed or non-default value is listed above so a reviewer can
  check the decisions that matter. The 138 bulk moves are homogeneous and described by
  the rule.

---

## 7. Validator warning count: 189 → 292 (deliberate)

`scripts/validate-integration.py` warns for every skill record whose
`license_status` is `missing-license` or `review-required`. The pre-T02 registry had
189 such records (35 ctf + 154 delivery); migrating hack-skills'
`MIT-with-third-party-provenance-review` (not a legal enum value) to
`review-required` adds its 103 records, so the count becomes 292. The script still
prints `INTEGRATION VALIDATION PASSED` and exits 0:

```
sources=4 skills=293 warnings=292
INTEGRATION VALIDATION PASSED
```

This is a **strengthening**, not a weakened gate: the only alternative legal enum for
hack-skills was `mixed`, which would have *hidden* 103 review obligations to keep the
old number. `docs/COMMUNITY-LICENSE-MATRIX.md` still carries the old wording and is
T04's file; T04 must restate hack-skills as "MIT declared + third-party review
required" and re-check the matrix against the registry.

---

## 8. What the schemas now make real

| before T02 | after T02 |
|---|---|
| `schemas/*` did not exist; 4.0 called them a planned interface | three draft 2020-12 documents exist and are validated on every contract-test run |
| nothing validated a handoff document | a real HandoffInput and a real HandoffOutput (built from the actual registry and the actual route output) validate; 12 negative documents are rejected |
| `network_profile` could be passed alongside `profile` | it is not a property of the input schema, so passing it fails validation (fail-closed) |
| `community-route.py` could not express `blocked`/`missing_input`/`unavailable`/`failed` | all six 4.7 statuses exist with their exit codes (`0/10/20/21/22/30`) and their required fields |
| wrapper paths and downstream lists were hardcoded in the helper | they come from `registry.json.wrappers[]` and are validated against `routing.json` and the 43 canonical skills |
| an unknown enum in the registry was passed through | an unknown enum, an unlisted `allowed_context` value or a wrapper path that does not exist gives `status=blocked`, `failure_reason=schema_invalid`, exit 20 |
| `unrestricted_lab` had no defined behaviour | it is registered as `unsupported`; the resolver reports `needs_review` and never maps it to `authorized_lab` |

Still **not** implemented, and not claimed:

* no producer emits a signed release carrier (`carrier-manifest.json` is a schema with
  a sample fixture only) — T23;
* no canonical `next_safe_steps` command allowlist exists, so
  `run_allowlisted_command` is shape-validated only — T23/T25;
* `jsonschema` is not installed and must not become a dependency; the bundled subset
  validator refuses to ignore any keyword it cannot enforce, and a full draft 2020-12
  validator is still required in CI — T10.

---

## 9. Dependencies this task hands to others

| item | owner | what is needed |
|---|---|---|
| `canonical-base` source record (5th source) | T21 | 4.1/17.15 require it; the contract test asserts T02 did not add it |
| `tree_digest`, `source_manifest`, `snapshot_root` | T12 (+T21) | materialise in-repo snapshots and the canonical digest algorithm, then re-run the generator |
| `importer_version` | T05 | add a version constant to `scripts/adapt-community.py` |
| `scripts/adapt-community.py` still writes a v1-shaped registry | T05 | a re-run today would delete `wrappers[]`, the 4.2 fields and the profile migration. The importer must emit v2 before it is run again. |
| NOTICE files for the missing-license source | T04 | `notice_file` is `null` for `ai-fullstack-delivery` |
| license matrix wording for hack-skills | T04 | see section 7 |
| `canonical-mapping.json` → `security-engineer` | unassigned | the target skill does not exist (see 4.3); 12.0 has no owner for that file |
| `content_hash` regeneration after body edits | T05 / whoever edits `skills/community/**` | any edit to an adapted body invalidates its digest; the contract test fails loudly instead of tolerating drift. During T02 another task was editing those bodies (frontmatter `user-invocable` removals, plus `docs/community/**` and `verify-doc-links.py` work), which is why the registry is regenerated after body work stops. |
| `content_type` after a body banner is added | T03/T19 + T02 re-run | the classification reads the body's first level-1 heading. 17.19 allows T19 to prepend a reference-only banner, which would become the new H1 and could change `content_type` for the affected record. Re-run the classification after any such banner lands. |
| removal of the transitional duplicate `path` key | T25 | see 4.1 |
| reword `adapted_path = 4.3 entrypoint` | T00/T25 | see 4.1 |
| full draft 2020-12 validation and CI wiring | T10/T23 | see section 8 |
| per-record `canonical_downstream` evidence | T07/T08/T09 | 287 records are legitimately empty today |
| `content_type` boundary review | T13 | section 6, honest limits |

## 10. Reproducing this migration

```powershell
cd <repo-root>
<python> skills\scripts\test-community-route.py
<python> skills\scripts\test-contract-v2.py
<python> scripts\validate-integration.py
powershell -NoProfile -ExecutionPolicy Bypass -File skills\scripts\verify-routing-coherence.ps1
```

Rollback: the pre-migration registry is a single file (`skills/community/registry.json`)
and every other new file is additive (`schemas/**`, `skills/config/profile-map.json`,
`docs/community/REGISTRY-V2-MIGRATION.md`) or confined to the T02-owned helper and its
two tests. The pre-migration copy used during this task is outside the repository, so
`git checkout -- skills/community/registry.json` (T00's decision, not T02's) restores
v1; the schemas, the profile map and the helper then have to go together, because the
helper validates the v2 contract and will fail closed on a v1 registry.
