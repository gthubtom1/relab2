# Importer lifecycle — `scripts/adapt-community.py`

Spec: §10 (command shapes), §4.7 (statuses and exit codes), §12.0 (single-writer
table), §17.26 (digest canonicalisation), §17.27 (physical discovery isolation),
§17.28 (source attestation). Task: T05.

This file records what the importer does, what it refuses to do, and what it does
**not** guarantee. Every number quoted here was measured on commit `daf7547`
plus this change; none of them is estimated.

---

## 1. What changed and why

The pre-T05 importer had **no argument parser** and called `main()` on any argv.
`--help`, a typo such as `--soruce`, and a CI argument were all equivalent to a
full import. One run:

| Property | Measured |
|---|---:|
| Paths overwritten | **1111** |
| — `skills/community/**` (now `community-raw/**`) | 1087 |
| — `docs/community/**` | 23 |
| — `skills/community/registry.json` | 1 |
| Deletions | 1 `rmtree` + N `unlink`, unrecoverable |
| Paths written more than once | **310** (293 `SKILL.md` + 17 `WORKFLOW.md`) |

Two of those were independently fatal: the importer wrote raw vendor content
back into `skills/`, which is the client discovery root, undoing the physical
isolation 17.27 requires; and it regenerated `registry.json` from a hard-coded
`SOURCES` table, destroying the v2 curation fields T02 owns.

## 2. The five commands

| Command | Writes | Exit codes |
|---|---|---|
| `inspect` | **nothing** | 0 all sources attested; 10 at least one rejected; 21 unknown id; 22 git unusable |
| `import` | **only** `.candidates/<id>/` | 0 built; 20 attestation rejected; 21 bad arguments; 30 copy failed |
| `verify` | **nothing** | 0 clean; 10 warnings only; 20 digest/attestation/isolation failure; 21 absent candidate |
| `promote` | the verified tree | 0 committed; 20 verify failed; 21 missing/bad `--status`; 30 interrupted (journaled) |
| `rollback` | the verified tree | 0 restored; 20 snapshot outside `.candidates/`; 21 absent/empty snapshot |

Read-only means read-only: `inspect` and `verify` were run against the real
repository and the six baseline hashes, the `git status` line count and the
absence of `.candidates/` were compared before and after. The suite asserts
this on every run.

`--help` is handled by `argparse` before any handler runs. Importing the module
as a library performs no work. Both are asserted.

## 3. Write root

`import` writes to `.candidates/<id>/` and nowhere else. `promote` moves, per
source, two directories:

```
community-raw/<dest>/          <-- source vendor content
docs/community/<source-id>/    <-- upstream support documents
```

plus `skills/community/registry.json`, which is the single path under `skills/`
the importer may write, and only while a promote is active.

**Per-source scope is deliberate.** An earlier revision of this rewrite moved
the whole `docs/community/` tree. Its own diff summary then reported 9
"deletions" — `DISCOVERY-ISOLATION.md`, `LINK-TRIAGE.md`, `ROUTE-RANKING.md` and
six others — because those are hand-written records the importer neither owns
nor carries. Promoting that would have destroyed them. Every path outside
`community-raw/<dest>/**` and `docs/community/<source-id>/**` is untouched by
`import`, `promote` and `rollback` alike.

A machine guard enforces the isolation rather than documenting it: `WriteGuard`
raises `blocked` / `path_escape` for any write target under `skills/` except
`registry.json` during a promote. The suite checks both directions — a
`skills/community/oops.md` target is refused with exit 20, and a
`community-raw/ok.md` target is allowed.

`.candidates/` is in `.gitignore`. Without it, a candidate tree pollutes
`git status` and is swept up by `validate-integration.py`'s
`ROOT.rglob("*")` key-material scan.

## 4. Digest contract (frozen)

`DIGEST_CONTRACT_VERSION = "skills-hub/importer-digest/1"`

```
file line : b"f" NUL <path> NUL <content_sha256_hex> LF
dir  line : b"d" NUL <path> NUL LF

file_manifest_digest = sha256(concat of all file lines, sorted by full-line byte order)
tree_digest          = sha256(concat of the sorted union of file lines and dir lines)
```

`<path>` is the NFC-normalised POSIX-relative path. `<content_sha256_hex>` is
`sha256` of the file bytes with **CRLF folded to LF**; a lone CR is preserved.

Folding is not cosmetic. This repository declares `*.md text eol=lf` and runs
`core.autocrlf=true`, so a CRLF byte written into the worktree is normalised at
commit time. Hashing raw bytes would therefore give different answers for the
worktree, the committed blob, a Linux checkout, a no-git copy and a release
bundle — precisely what 17.26 forbids. The old importer used `shutil.copy2`,
which writes the upstream CRLF verbatim; the rewrite folds on the way in.

Excluded from the digest: file mode, uid/gid, mtime/ctime/atime, inode, Windows
attribute bits. Symlinks are not followed and contribute no bytes. `tree_digest`
differs from `file_manifest_digest` because it also covers directory entries.

The suite recomputes `file_manifest_digest` for a fixed two-file input with an
implementation written independently of the importer, and requires the two to
agree. It then flips one byte and requires the digest to change.

Cross-check against the pre-existing baseline: for the same 1111 overwrite
paths at commit `c9b8303`, the frozen format yields
`file_manifest_digest = 6f57b141…f17` and `tree_digest = d258ddc0…a30b`, which
are the values recorded in `work/baseline-digest.json`.

## 5. Attestation (17.28), checked before any copy

`import` refuses to start until every selected source passes:

- `dirty` must be `false` — a dirty source is investigation material, not a
  candidate input;
- `resolved_commit` must be 40 lowercase hex **and** resolvable by
  `git cat-file -e <commit>^{commit}`; a string copied out of the registry is
  not evidence;
- it must equal the pinned commit;
- `tree_digest` / `file_manifest_digest` must be 64 hex and match the frozen
  contract version;
- `fetched_at` must be UTC RFC 3339; `attestation_method` must be one of
  `git-commit | tarball-digest | api-tree-digest`.

On rejection the command exits 20, names the violated rules, and **no directory
is created** — the candidate path and its `.partial` staging are both absent
afterwards. The suite asserts that.

`default_branch_commit` is recorded as `null` with an explicit note. The
importer is offline and cannot establish the remote HEAD; 17.28 requires the
field to be recorded, and inventing a value would be worse than recording the
gap. 17.28 also requires the attestation to be verifiable offline, which it is:
the digests are recomputed from the local snapshot.

## 6. Promote is a recoverable window, not an atomic swap

Windows cannot replace a non-empty directory with a single syscall:
`os.replace` on a directory fails when the target exists and is non-empty.
Promote is therefore a sequence of per-directory renames:

1. copy `registry.json` into the snapshot;
2. for each source: `os.replace(live_dir, snapshot/…/live_dir)` — atomic,
   because the destination does not exist;
3. `os.replace(candidate_dir, live_dir)` — atomic, same reason;
4. `os.replace(candidate/registry.json, skills/community/registry.json)`.

**Between steps 2 and 3 a source is absent from the verified tree.** That window
is real. Nothing here claims atomicity, and `promote` will not start while a
journal from a previous attempt exists.

`.candidates/promote-journal.json` records the state (`begin` →
`target-moved-aside` → `committed`, or `interrupted`), every step performed,
every source/target pair, and the snapshot path. A crash between two renames
leaves the journal pointing at exactly what is in the snapshot and what is not.

The journal also names the same-volume requirement: if `.candidates/` and the
verified tree are on different volumes, rename degrades to copy and the
recovery property is lost, so promote exits 22 instead.

`rollback --to .candidates/snapshots/verified-<stamp>` restores each per-source
directory and `registry.json` from the snapshot. Verified in the lab: after
promote and rollback the tree was **byte-identical** to its pre-promote state
(composite digest `2b4b33ef…1d08` before, during and after).

## 7. Measured outcome, and what U11 closed

Importing all four sources into a candidate produced a path set **identical to
the verified tree**: 1087 files, 0 missing, 0 extra. Content differs on 298
files, and that is not a defect in the rewrite.

The verified `community-raw/` tree has been edited since the last full import.
T08 and T09 rewrote the `> **AI LOAD INSTRUCTION**:` line in the raw tree into
`> **Vendor source summary (reference-only; not a load instruction)**:`. A
faithful re-import from upstream would revert all of that. The diff summary
names every affected path, which is what it is for.

**U11 resolution (this change).** The 131-file banner neutralisation is now a
registered managed transform
(`docs/community/IMPORTER-MANAGED-TRANSFORMS.md`, id
`t09-load-instruction-neutralize`, curation-wins policy). `import` applies it
after materialisation: lab-measured, the candidate carries the transform on
131 files and retains **0** `AI LOAD INSTRUCTION` instances in the managed
scope. The manifest pins the record digest plus the applied path list; the
diff summary carries a `Managed transforms applied` section while every
remaining (unregistered) diff stays listed; `verify` rejects a digest
mismatch or a stale candidate; and `promote` refuses with exit 20 whenever
any modification/deletion **inside the candidate's own source scope** remains —
each one is, by construction, an unregistered diff that promotion would revert.
Pure additions never block. The honest boundary: the transform guarantees
the *registered class*, not byte equality — lab-measured, the 131 managed
files still differ from the verified tree on other unregistered drift
(80 license-line-only, rest delivery/frontmatter drift), so they stay
promote-blocking until those get their own reviewed entries.

**P1-4 scope alignment (this change).** The U11 refusal check used to cover
the whole tree while `promote` only writes the candidate's own sources, so a
single-source candidate was refused for dirt it could never revert (lab-measured:
an `apk-reverse-community`-only candidate was refused with 1004 unregistered
paths, of which only 11 sit inside its own scope; after the fix the same
candidate is refused with exactly those 11, and the full re-import with 302 —
the exact sum of the four single-source counts 11 + 13 + 141 + 137). The check now covers
exactly the manifest's `sources` — the same per-source scope the rename
sequence writes — and the refusal payload reports it as `checked_scope`.
Strength is unchanged: same modification/deletion rule, same exit 20, same
per-path naming. What changed is only *which* paths are examined.

Measured boundary after this change (lab copy, `import --source <id>` +
`promote --dry-run`, real exit codes):

| Candidate scope | Result | Unregistered in scope |
|---|---|---:|
| `apk-reverse-community` only | refused, exit 20 | **11** modifications, all T03 fused-path curation rewrites (`skills/apk-reverse/` → `skills/community/apk-reverse-source/`), none registered |
| `ctf-super-hub` only | refused, exit 20 | **13** modifications |
| `hack-skills` only | refused, exit 20 | **141** modifications |
| `ai-fullstack-delivery` only | refused, exit 20 | **137** modifications |
| all four (full re-import) | refused, exit 20 | **302** total (11 + 13 + 141 + 137 — exactly the sum of the four scopes) |

So today every scope is still refused, and each refusal is the feature
working — it names the exact paths that would otherwise be reverted. The
path to a passing single-source promote is registration, not relaxation:
in the lab, extending the (lab-only) transforms record to cover the 11 apk
fused-path rewrites made `import → verify → promote` exit 0 with the target
byte-identical to the candidate, while one further unregistered edit in the
same scope still exited 20 naming the path. The real record keeps its 2
entries; registering the apk path-rewrite class there is a curation decision
for its owner, not something this change assumes.

What this means in practice: **no promote passes today without a new
registration decision**, and that refusal is the feature working — it names
the exact paths that would otherwise be reverted. A single-source promote
*can* pass once its scope's drift is registered; a full re-import is refused
as long as any scope carries unregistered drift.

## 8. Coverage of the acceptance criteria

| Criterion (task card) | Status |
|---|---|
| five subcommands | met |
| `--help` prints only, no work | met, asserted with before/after hashes |
| 17.28 attestation checked before import | met, four rejection paths asserted |
| source digest | met, contract frozen and cross-checked |
| candidate | met, `.candidates/<id>/`, ignored by git |
| atomic promote | **partially met, and not claimed** — journaled rename with a recoverable window; see §6 |
| dry-run | met on `import`, `promote`, `rollback` |
| write root is `community-raw/`, never `skills/` | met, machine-enforced |
| digest contract frozen first | met, §4 |
| LF folding implemented | met, asserted |
| `.candidates/` in `.gitignore` | met, `git check-ignore` asserted |
| repeated run leaves the verified tree unchanged | met — `import` cannot write outside `.candidates/`; verified by hash comparison |
| digest mismatch fails | met, tampered candidate → exit 20 |
| rollback restores | met, byte-identical |
| `audit-discovery-surface.py` still exit 0 | see the acceptance report |

## 9. Not claimed

- Promote is not atomic. §6 describes the window; it is recoverable, not
  invisible.
- The importer does not decide whether an **unregistered** diff should survive:
  it blocks promote and lists the paths. The block is scoped: a candidate is
  judged only on the sources it carries (`checked_scope` in the refusal
  payload), because those are the only directories its promote would move.
  Dirt elsewhere cannot be reverted by this promote, so it does not block it —
  but a full re-import carries every scope, so any unregistered drift anywhere
  still refuses the full candidate. Registering a new curation decision
  is a one-entry change to `IMPORTER-MANAGED-TRANSFORMS.md` (§4 there);
  until then the candidate stays out of the verified tree.
- `import` does not prune. A file removed upstream stays until promote replaces
  the whole per-source directory, which it does — by rename, so pruning is
  implicit in the swap and explicit in the diff summary.
- No claim is made about downstream consumers of `registry.json` beyond the fact
  that the candidate registry is a *merge* of the live file, not a
  regeneration, and that promoting it remains T02's call.
