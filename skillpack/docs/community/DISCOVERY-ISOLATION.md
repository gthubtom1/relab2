# Discovery isolation — implementation record (T01)

Spec: §11.3 (discovery isolation), §17.27 (physical implementation), §2.3 (vendor vs
execution surface), §12.0 (single-writer table).

Status: **implemented and verified**. `audit-discovery-surface.py` goes from
`exit 20` (2 defects) to `exit 0`.

---

## 1. The defect this closes

Measured before the change (`python skills/scripts/audit-discovery-surface.py`,
exit 20):

```text
canonical skills               : 46
canonical wrappers             : 4
registry adapted skills        : 293
expected exposed set           : 50
recursive scan finds           : 343
INDEX.md rows                  : 342
raw vendor files exposed       : 293
vendored skills exposed by INDEX: 293
BLOCKED: 293 raw vendor skill file(s) are reachable by a plain recursive client walk
BLOCKED: INDEX.md exposes 293 vendored skill path(s)
```

All 293 raw `SKILL.md` files already carried `user-invocable: "false"`, and the
registry already recorded them as `discovery: reference-only`. Neither is
isolation: §17.27 is explicit that frontmatter is a hint, and a client that simply
walks `skills/**` for `SKILL.md` does not read frontmatter at all. The isolation
therefore had to be **physical**.

---

## 2. Decision: option (b), physical relocation — and why not (a) / (c)

CR-001 offered three options. Option **(b)** was chosen.

### 2.1 Rejected — option (a), "add a marker only"

Marking cannot satisfy §17.27 item 1. A plain recursive client never inspects
`user-invocable`, `discovery` or any banner; the file being *under the walk root*
is the whole defect. Marking is a transition aid, not isolation.

### 2.2 Rejected — every landing zone inside `skills/`, including `skills/community/_raw/**`

`skills/` **is** the client discovery root in this package (`AGENTS.md`,
`CLAUDE.md`, `skills/SKILL.md` and `skills/config/routing.json` all define it that
way, and `audit-discovery-surface.py` models the client as a walk of `skills/`).
Adding a level inside it changes the *name* of the path, not its reachability:
`skills/community/_raw/<source>/SKILL.md` is still returned by any
`rglob("SKILL.md")` or OS-level recursive scan started at `skills/`.

Depth and naming are not isolation. That is the reason the landing zone had to be
a directory **outside** `skills/`, not a deeper directory inside it.

### 2.3 Rejected — exploiting the audit tool's own skip list

`recursive_scan()` ignores paths whose *first* component under `skills/` is in
`SKIP_TOP = {ops, scripts, config, tests, field-journal, references, docs}`. Moving
the raw trees to e.g. `skills/references/**` would therefore also turn the gate
green — but for the wrong reason. `SKIP_TOP` is the tool's model of "infrastructure,
not discoverable skills"; it is not a property of a client. A real client that walks
`skills/**` would still find all 293 files, which is exactly what §17.27 item 1
("must live outside the client scan root") forbids. Passing the gate that way would
be gaming the gate, so it was not done.

### 2.4 Rejected — symlink / junction shim

Leaving `skills/community/<source>` as a symlink or NTFS junction to the new
location would keep old links resolving, but §17.16/§17.30 require symlinks and
reparse points to be refused, and the walk's behaviour would become
platform- and Python-version-dependent. Rejected.

### 2.5 Rejected — option (c), client manifest only

A carrier manifest only binds clients that voluntarily read it. §17.27 items 3 and
5 still want the manifest (owned elsewhere), but it cannot be the *only* mechanism.

### 2.6 Why the chosen root works, and why it is not another discovery root

`community-raw/` is a **sibling of `skills/` at the repository root**. A walk that
starts at `skills/` cannot enumerate it at any depth — that is a property of the
filesystem tree, not of a skip list. The relocation is therefore provable by
construction, and it is proved empirically in §5.

Two further properties were designed in:

* **depth-preserving.** `skills/community/<source>/…` and `community-raw/<source>/…`
  are both two components from the repository root, so every relative link *inside*
  the moved trees keeps its meaning. Measured: the move creates **0** new broken
  links inside the moved trees (see §4.3).
* **explicitly labelled raw.** The name marks the content as untrusted vendor data
  (§17.31 forbids executing vendor code in CI), so it cannot be mistaken for a
  second skill root. `_raw` under `skills/community/`, by contrast, reads like a
  supported discovery path.

Residual, recorded honestly: a client that scans the **repository root** instead of
`skills/` would still see these 293 files — and it already sees 42 further
`SKILL.md` files under `CTF-Sandbox-Orchestrator/` and 1 under `plugins/`, which are
outside this task's scope. That case is a *client configuration / carrier-manifest*
concern (§17.27 items 2–3, owned by T23/T24), not something physical relocation of
the community tree can fix on its own. The client contract must remain
"discovery root = `skills/`, manifest = `skills/community/registry.json`".

---

## 3. Authoritative layout after the move

```text
<repo>/skills/                                  # THE client discovery root
<repo>/skills/SKILL.md                          # 1 canonical root skill
<repo>/skills/<canonical>/SKILL.md              # 45 canonical skills
<repo>/skills/community/registry.json           # the only discovery manifest
<repo>/skills/community/canonical-mapping.json
<repo>/skills/community/README.md
<repo>/skills/community/ctf-hub/SKILL.md        # the only 4 discoverable community entries
<repo>/skills/community/hack-hub/SKILL.md
<repo>/skills/community/delivery/SKILL.md
<repo>/skills/community/apk-extension/SKILL.md

<repo>/community-raw/ctf-super-hub/**           # raw vendor bodies (reference-only)
<repo>/community-raw/hack-skills/**
<repo>/community-raw/ai-fullstack/**
<repo>/community-raw/apk-reverse-source/**
```

### 3.1 Mapping rule (one line, mechanical)

```text
skills/community/<source>/<rest>   ->   community-raw/<source>/<rest>
for <source> in {ctf-super-hub, hack-skills, ai-fullstack, apk-reverse-source}
```

Same depth, same leaf name, same bytes. No file was renamed, added or deleted.

### 3.2 What deliberately did not move

* the 4 wrappers `ctf-hub`, `hack-hub`, `delivery`, `apk-extension` — **paths
  unchanged**, verified by an empty `git diff` and by the audit tool still
  reporting exactly those four as `canonical wrappers`;
* `skills/community/registry.json`, `canonical-mapping.json`, `README.md`;
* `docs/community/**` (the upstream README archive) — untouched apart from the
  link re-points listed in §4.4.

---

## 4. Migration record

### 4.1 Files and directories

| source | files relocated | raw `SKILL.md` | registry records |
|---|---:|---:|---:|
| `ctf-super-hub` | 164 | 35 | 35 |
| `hack-skills` | 166 | 103 | 103 |
| `ai-fullstack` | 643 | 154 | 154 |
| `apk-reverse-source` | 114 | 1 | 1 |
| **total** | **1087** | **293** | **293** |

562 directories were created under `community-raw/` (excluding the root itself).
No file was left behind and no file went missing: 1087 index paths map onto 1087
existing files (verified, §5.3).

### 4.2 Registry

Exactly **586** path fields changed (`path` + `adapted_path` for each of 293
records). Unchanged, on purpose:

* `source_path` (upstream-relative, e.g. `brainstorming/SKILL.md`);
* `entrypoint` (all 293 still point at the four wrapper paths under `skills/community/`);
* `wrappers[].path` (all four unchanged);
* every profile, enum, license, risk, maturity, keyword, `content_hash`,
  `canonical_downstream` and `reference_ids` value;
* `sources[]`, `excluded[]` (55 records) and `stats`.

The edit was byte-level, so nothing but the 586 prefixes changed (`463155` →
`461397` bytes = exactly 586 × −3).

### 4.3 Generated index

`skills/INDEX.md` was regenerated by `skills/scripts/extract-summaries.ps1`:
**342 → 49** rows and 49 directory-tree entries (45 canonical + the 4 wrappers;
`skills/SKILL.md` is excluded by the generator by design). Zero vendored paths.

The generator now excludes the raw tree **explicitly** rather than incidentally
(§17.27 item 4):

* `community-raw/**/SKILL.md` is added to the `git ls-files` candidate set and then
  rejected by an explicit `$rawRoots` / `$rawSourceDirs` filter, so the exclusion is
  applied to real candidates instead of relying on the pathspec never matching;
* `$rawSourceDirs` also excludes `skills/community/{ctf-super-hub,hack-skills,ai-fullstack,apk-reverse-source}/**`,
  so a future importer that writes the raw tree back into the discovery root still
  cannot reach `INDEX.md`;
* a hard self-assertion fails the generator (`exit 1`) if any raw path ever reaches
  the row set — a failure, not a warning.

### 4.4 Path literals re-pointed outside the moved tree

T03's commit `686796d` had rewritten 328 upstream-relative links in two provenance
copies to point at the *live* tree, and registered them in `docs/community/link-triage.json`
as `status: fixed, disposition: rewrite_path`. Those literals had to follow the move;
the change was authorised by T00 for exactly three files.

| file | change |
|---|---|
| `docs/community/hack-skills/README.md` | 164 links `../../../skills/community/hack-skills/…` → `../../../community-raw/hack-skills/…`; 1 banner path literal |
| `docs/community/hack-skills/README_CN.md` | same, 164 links + 1 banner path literal |
| `docs/community/link-triage.json` | 328 × `new_target`, 328 × `resolves_to`, 1 × `file` (the `documented_not_distributed` entry whose source file moved), 3 × prose path literals inside `reason`/`evidence` |

Deliberately **not** touched: dispositions, statuses, entry count, any exemption,
`classification_rules`, and `docs/community/link-triage.lock.json` (owned by T00).
Post-change the registry still holds **342** entries with the same **329 fixed / 13
registered_open** split, all 329 `fixed` targets still resolve, and
`verify-doc-links.py` reports the same `active=0 wrapper=0 provenance=13` as before
the move.

---

## 5. Verification

### 5.1 The eight acceptance commands

| command | before | after |
|---|---|---|
| `skills/scripts/audit-discovery-surface.py` | **20** (2 defects) | **0** |
| `skills/scripts/test-contract-v2.py` | 0 | **0** |
| `skills/scripts/test-community-route.py` | 0 | **0** |
| `skills/scripts/verify-doc-links.py` | 0 | **0** |
| `skills/scripts/verify-community-banner.py` | 10 (15 banners) | **10** (byte-identical output) |
| `scripts/validate-integration.py` | 0 | **0** |
| `skills/scripts/test-routing.ps1` | 182/182 | **182/182** |
| `skills/scripts/verify-routing-coherence.ps1` | ALL PASSED | **ALL PASSED** |

No judgement was relaxed: the audit tool, the triage registry's rule table and the
link classifier were all left exactly as they were.

### 5.2 Negative controls (the gate is not vacuously green)

**N1 — a raw-looking `SKILL.md` placed back in the discovery root**
(`skills/community/hack-skills/zz-negative-control/SKILL.md`, temporary):

```text
recursive scan finds           : 51      (was 50)
raw vendor files exposed       : 1
BLOCKED: 1 raw vendor skill file(s) are reachable by a plain recursive client walk
FAIL audit-discovery-surface: 1 defect(s)      exit 20
```

Also, during N1 `extract-summaries.ps1 -Check` still exited **0**, i.e. the new
`$rawSourceDirs` guard kept the file out of `INDEX.md` even though it was sitting in
the discovery root.

**N2 — the same file placed inside `community-raw/hack-skills/`**: the audit stays
**green** (`recursive scan finds : 50`, `raw vendor files exposed : 0`, exit 0). This
is the positive proof that the isolation is structural: a plain `skills/**` walk
genuinely cannot reach the raw root, so the tool is not merely "counting files that
happen to live elsewhere".

Both probes were deleted; `git status` entry count was identical before and after,
and no `zz-negative-control` directory remains.

### 5.3 Post-commit equivalence (the gates were run on an uncommitted tree)

After a filesystem move that is not yet committed, `git ls-files --cached` still
lists the *old* paths and `verify-doc-links.py` can still read them through its
`git show :path` fallback — so the live run sees the tree twice (1475 → 2472
Markdown files). A green result in that state is not automatically a green result
after committing.

The gate was therefore re-run against the exact snapshot the tree will have once
the move is committed (index paths remapped to the new location, 1738 files / 1475
Markdown — the same figures as the pre-move baseline):

```text
verify-doc-links: 13 broken internal link(s) in 1475 Markdown file(s) — active=0 wrapper=0 provenance=13
verify-doc-links: live provenance breaks registered 13/13; registry entries 342 (fixed=329, open=13, stale=0)
OK verify-doc-links: active=0 wrapper=0; all 13 provenance break(s) registered
exit = 0
```

### 5.4 Independent client-level test (§17.27 item 5)

A registry-blind, frontmatter-blind `os.walk`-style recursion over `skills/`, sharing
no code with the audit tool, finds **50** `SKILL.md`: 46 canonical + the 4 wrappers,
with **zero** intersection with the registry's 293 raw records. That is the
"client-level negative test" §17.27 item 5 asks for, and it is now reproducible.

### 5.5 Content integrity of the relocation

* `git hash-object --path=<old path> <new path>` equals the old index blob for all
  **1087/1087** relocated files;
* the only raw-byte difference is the repository-wide CRLF/LF normalisation
  (`.gitattributes` `*.md text eol=lf` + `core.autocrlf=true`): 496 moved files differ
  from their blob only by CRLF, and a control set of never-moved
  `skills/community/*` files shows the same phenomenon — it is pre-existing
  (WORK-BOARD E16), not caused by the move;
* `test-contract-v2.py` re-hashes all 293 raw `SKILL.md` bodies from raw worktree
  bytes against the registry `content_hash` and passes;
* `git diff` over the four wrapper files is empty.

No community body byte was edited. The only content edits anywhere in the repository
are path literals (§4.4) and the documentation/code files listed in §6.

---

## 6. Touched files (T01 manifest)

See the task report for the per-file rationale. Summary:

| area | files |
|---|---|
| physical move | 1087 files relocated under `community-raw/` (4 trees) |
| manifest | `skills/community/registry.json` (586 path fields only) |
| generated | `skills/INDEX.md` (regenerated) |
| generator + guards | `skills/scripts/extract-summaries.ps1`, `skills/scripts/verify-community-banner.py`, `skills/scripts/verify-doc-links.py`, `skills/scripts/test-contract-v2.py` |
| entry docs | `AGENTS.md`, `skills/community/README.md` |
| link re-point (T00-authorised) | `docs/community/hack-skills/README.md`, `docs/community/hack-skills/README_CN.md`, `docs/community/link-triage.json` |
| new | `docs/community/DISCOVERY-ISOLATION.md` (this file) |

`.gitignore` needed no new entry: `community-raw/` is committed content, not an
ignored or generated tree.

---

## 7. Residual risks and follow-ups owned by other tasks

1. **`scripts/adapt-community.py` (T05, P0).** Its four `"dest"` roots still point at
   `skills/community/<source>` and its write set covers 1087 paths there. **Any run
   re-creates the discovery leak.** The write root must move to
   `community-raw/<source>` in the same change. Not touched here (CR-002 forbids it).
2. **Spec §2.3 is now stale (T00).** Lines 155–172 still prescribe
   `skills/community/<source>/ # vendor/reference, 默认不可发现`; §17.27 supersedes it.
3. **`docs/community/link-triage.json` `classification_rules` rationale (T03/T00).**
   The rule *globs* stay correct for the wrappers, but the rationale text still says
   vendor data is "kept under `skills/community`". The table is a frozen contract
   compared field-by-field against `verify-doc-links.py`, so it cannot be edited from
   one side only — and `link-triage.lock.json` is T00's.
4. **Classification drift for the new root (T03).** Markdown under `community-raw/**`
   now falls through to the frozen `default-active` rule, so a future broken link in
   vendor content would be a must-fix instead of a registerable `provenance` break.
   Today there are **0** such breaks (verified), so nothing is red — but adding
   `community-raw/** -> provenance` to `CLASSIFICATION_RULES` **and** to the mirrored
   `classification_rules` in `link-triage.json` (with a re-lock) is the right
   follow-up. It was deliberately not done here: it is not a path-prefix adaptation,
   and it would have altered the frozen classification contract.
5. **Stale prose path literals (T02/T03).** `docs/community/LINK-TRIAGE.md`,
   `docs/community/PATH-CLEANUP.md` and `docs/community/REGISTRY-V2-MIGRATION.md`
   quote `skills/community/<source>/…` paths in prose (e.g. the documented mapping in
   `LINK-TRIAGE.md`). They are unlinked code spans, so no gate is affected, but the
   text is now factually stale. Outside this task's whitelist.
6. **`skills/scripts/verify-triage-lock.py` is intentionally red** after this change
   (`digest does not match the lock`, `registry entries: 342`). T00 regenerates
   `docs/community/link-triage.lock.json`; per instruction this task neither edited
   the lock nor ran `--write-lock`.
7. **Repository-root scan residual.** 43 `SKILL.md` files live outside `skills/` and
   `community-raw/` (42 under `CTF-Sandbox-Orchestrator/`, 1 under `plugins/`).
   Pre-existing; out of scope for T01 but relevant to any future "no second discovery
   root" claim.
