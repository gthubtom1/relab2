# Transactional promotion and recovery — T20

Spec: §17.14 + task card T20 (§19). Importer: `scripts/adapt-community.py`
(owned by T05 — **not modified by this card**; importer-side changes go
through a change request). Lab: `work\t20-lab`
(**outside the repo**). Harness: `scripts/t20-transactional-lab.py`,
`scripts/t20-rollback-audit.py`, `scripts/t20-format-gate.py`.
Tests: `tests/t20/test_t20_transactional.py` (29/29).

This card adds **recoverability evidence and crash injection on top of the
existing journaled rename**. It does not rewrite the importer.

---

## 1. Generation model

One generation = data dirs + registry + INDEX + NOTICE + schema, managed as a
single unit (§17.14 ¶1). The lab generation manifest
(`generation-manifest.json`, schema `t20/generation-manifest/1`) carries:

| Field | Meaning |
|---|---|
| `generation` | monotonic integer; rollback appends history, never decrements |
| `tree_digest` | digest of the live tree at this generation (seal sidecars excluded) |
| `history` | promote / recover / rollback events with UTC timestamps |
| `created_at` | seed timestamp |

Lifecycle gates, in order: **sealed candidate** (digest pinned in `seal.json`,
recomputed after seal and before promote — tamper exits 20) → **format gate**
(unknown/absent/unparsable format exits 20, no downgrade) → **single-writer
lock** (`promote.lock`, `O_CREAT|O_EXCL`; held exits 22) → **same-volume
check** (rename degrades to copy across volumes; exits 22) → **two-phase
journal** (`begin` → `snapshotted` → `target-moved-aside` → `committed`,
every step fsynced) → **snapshot retention** (last 3 verified generations).

`rollback` restores the latest snapshot over live, then **re-verifies**:
live tree digest must equal the snapshot payload digest, else exit 30.
A rollback that only replaces files without recovering compatible data does
not count (§17.14 ¶last) — the re-verify line in the lab log is the proof.

## 2. Crash windows (all real renames, all lab-measured)

Promote is a sequence of per-directory `os.replace` calls. The windows are
real; nothing here claims atomicity (same position as `IMPORTER-LIFECYCLE.md`
§6). Crash points injected by `--crash-at`:

| Point | Where | Live-tree state at crash |
|---|---|---|
| A | after journal `begin`, before snapshot | untouched; manifest authoritative |
| B | after snapshot, before first move-aside | untouched; snapshot complete |
| B2 | **between the two renames** (after `data/alpha` moved aside) | `data/alpha` absent from live |
| C | data swapped, tracked files not yet swapped | new data + old registry/INDEX/NOTICE/schema |
| D | after journal `committed`, before manifest update | fully new tree, manifest stale |

## 3. Recovery procedure

`--recover` scans the journal and converges to exactly one known generation:

- **A** (no `snapshot-complete` step): verify live == manifest `tree_digest`;
  nothing was ever moved, so the manifest alone is authoritative.
- **B / B2 / C**: snapshot is the pre-promote generation and always wins.
  Every `aside/` dir is moved back; any missing data dir is re-materialised
  from the snapshot; every tracked file differing from the snapshot is
  reverted. Then live digest must equal the snapshot payload digest.
- **D** (journal `committed`): the swap is complete by construction; the
  manifest is advanced to the committed tree (generation +1).

Measured result (29/29 suite + manual runs): A/B/B2/C recover to the
pre-promote tree `d8675f2a…` (rc 0, byte-equal); D finalises generation 2
(rc 0). Each window prints journal state, step count, generation id and both
digests; see the evidence log pattern in §5.

Cross-volume replacement is guarded, not tested destructively: the harness
checks `st_dev` equality and exits 22 before any rename. True two-volume
rename behaviour is **unverified** (see §6).

## 4. Rollback integrity: what the importer restores vs what it does not

Static scope proof (`t20-rollback-audit.py`, parsed from
`rollback_candidate`): the importer restores **per-source raw/docs dirs +
`skills/community/registry.json` only**. Item-by-item verdict:

| Item | Real-repo witness | Importer rollback restores? | Lab harness restores? |
|---|---|---|---|
| registry | `skills/community/registry.json` | **yes** | yes (re-verified) |
| INDEX | `skills/INDEX.md` | **no** — never in rollback scope | yes (re-verified) |
| NOTICE | `NOTICE` | **no** — never in rollback scope | yes (re-verified) |
| schema | `schemas/` | **no** — never in rollback scope | yes (re-verified) |
| data dirs | per-source raw/docs | yes | yes (re-verified) |

Lab proof: promote swaps all four tracked files (4/4 digests change),
rollback restores all four (4/4 byte-equal) plus the data tree
(`data_tree_restored=true`, `all_restored=true`).

**Change request to the importer owner (reported, not implemented):**
extend `rollback_candidate` to snapshot/restore INDEX, NOTICE and the
`schemas/` files the candidate touched, or record explicitly that they are
out of importer scope and assign the restore duty to the release owner.
Until then, full-generation rollback exists only in this lab harness.

## 5. Reproducing the evidence (repo-outside)

```text
$env:PYTHONIOENCODING='utf-8'
& (Resolve-ReverseToolSpec -Name 'pyre').Command scripts/t20-transactional-lab.py --seed
& (Resolve-ReverseToolSpec -Name 'pyre').Command scripts/t20-transactional-lab.py --promote --crash-at B2
& (Resolve-ReverseToolSpec -Name 'pyre').Command scripts/t20-transactional-lab.py --recover
& (Resolve-ReverseToolSpec -Name 'pyre').Command scripts/t20-transactional-lab.py --promote   # clean -> gen 2
& (Resolve-ReverseToolSpec -Name 'pyre').Command scripts/t20-transactional-lab.py --rollback
& (Resolve-ReverseToolSpec -Name 'pyre').Command scripts/t20-rollback-audit.py
& (Resolve-ReverseToolSpec -Name 'pyre').Command scripts/t20-format-gate.py --self-test
& (Resolve-ReverseToolSpec -Name 'pyre').Command ests/t20/test_t20_transactional.py          # 29/29
```

Evidence log pattern per window (real output): `journal-begin
generation=1 …`, `moved-aside data/alpha (window open…)`, `INTERRUPTED
injected crash B2…`, `recover: journal state=interrupted steps=2`,
`recover: restored data/alpha from aside`, `RECOVER-OK generation=1
tree=d8675f2a…`.

The real repo is never promoted or rolled back: the harness refuses any
`--lab` path inside the checkout (exit 21), the suite asserts no
`.candidates/` exists, and acceptance re-checks `git status --porcelain`
plus the six baseline hashes.

## 6. What is still NOT verified

1. **True OS crash / power loss.** Injection raises between renames in the
   same process; fsync paths are exercised but a kill -9 / power-cut test was
   not run.
2. **Cross-volume rename.** Guarded by `st_dev` check (exit 22); the degraded
   copy path was deliberately not executed.
3. **Concurrent promoters on separate machines.** The lock is a lab-local
   file; NFS/shared-volume semantics were not tested.
4. **Old-data migration / downgrade policy beyond the format gate.** The gate
   blocks (`t99/future/9` → exit 20, live tree byte-identical); versioned
   migration rules and downgrade paths are policy stubs, not implementations.
5. **Importer-side full rollback** (INDEX/NOTICE/schema) — open change
   request in §4.
6. **Retention under disk pressure** (keep-last-3 eviction when the volume is
   full) and **generation-manifest corruption** recovery.
