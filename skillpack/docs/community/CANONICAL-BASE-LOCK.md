# Canonical base lock (T21, spec 17.15 / 17.28 / 17.29)

Owner: T21. Read scope: this document, `skills/community/registry.json` (base
record only), `schemas/canonical-base-lock.json`,
`scripts/verify-canonical-base-lock.py`. No other card's files are touched.

## 1. Base identity

The canonical base is the mother framework `reverse-skill`: 43 canonical
skills under `skills/` in the snapshot. Registry record id `reverse-skill`,
`source_kind` `canonical-base` (the 5th `sources[]` entry; the other four are
community sources owned by T12/T05 and untouched).

```
baseline commit (upstream/reverse-skill HEAD): cab634bd855fc287f6e420c1f36fd1a6b9245960
integration commit (fusion repo HEAD at lock): 7a1d45305869dd33851510908be910b9dedc8ebd
registry baseline.commit:                      cab634bd855fc287f6e420c1f36fd1a6b9245960
```

`commit == baseline_commit == registry baseline.commit` is asserted by the
verifier on every run; `integration_commit` must additionally resolve via
`git cat-file -e` wherever `.git` is present.

## 2. Attestation

Snapshot: `upstream/reverse-skill` (sibling of the fusion repo, read-only;
spec 1.4). Origin URL read from the snapshot remote
(`git config --get remote.origin.url` returned
`https://github.com/zhaoxuya520/reverse-skill.git`): recorded without the
`.git` suffix per registry convention:
`https://github.com/zhaoxuya520/reverse-skill`. No URL was invented; had the
snapshot carried no remote, `source_url` would be null with the gap reported.

17.28 ten-field record (measured 2026-09-30T20:06:36Z, tool
`git 2.55.0.windows.3`):

```
upstream_url:           https://github.com/zhaoxuya520/reverse-skill
resolved_commit:        cab634bd855fc287f6e420c1f36fd1a6b9245960
default_branch_commit:  null (offline; remote HEAD cannot be established without network, not invented)
origin_head_commit:     cab634bd855fc287f6e420c1f36fd1a6b9245960
dirty:                  false (git status --porcelain empty, verified)
tree_digest:            e04b0b454e52c0fe82e9ef19140be21d74fc789ea2495abafb6fd0960787e5c2
file_manifest_digest:   05a9e63c3eef9f3ff2038a509685127ad74eeed1ed44d7277a30bdc7691fb946
file_count / dir_count: 627 / 295, symlinks 0
fetched_at:             2026-09-30T20:06:36Z
fetch_tool_and_version: git 2.55.0.windows.3
attestation_method:     git-commit
```

Digest contract is the frozen `skills-hub/importer-digest/1` (same as
`docs/community/SOURCE-BUNDLE.md` section 2): `f NUL path NUL sha256 LF`,
`d NUL path NUL LF`, NFC POSIX paths, CRLF folded to LF, sorted lines,
`.git` included at scan root `.`. The implementation in
`scripts/verify-canonical-base-lock.py` was proven byte-identical by
recomputing all four T12 lock digests (`03e9f6bf5a95`, `40367cf305f2`,
`3dbbea82d5b1`, `8c7644aed787` — 4/4 match before this record was written).

Record fields that mirror this section: `tree_digest`
(`sha256:`-prefixed), `source_manifest` (pointer here, no second manifest
copy), `snapshot_root` (`upstream/reverse-skill`), `last_verified_at`.
`importer_version` stays null like the four community records (owner T05/T02;
not invented here).

## 3. Signature status (honest: unsigned)

No verifiable signature exists for any candidate in this repository. The
record states `signature.present: false`, `status: unsigned`, `trust_root:
null`, `key_rotation` / `revocation: unimplemented`. Claiming otherwise is
forbidden; the verifier rejects `signed-verified` unless signer, trust root,
key id, timestamp, rotation and revocation are all recorded.

Consequence (17.15): without a verifiable signature no candidate may enter a
`redistributable` release. Enforcement:

```
& (Resolve-ReverseToolSpec -Name 'pyre').Command cripts/verify-canonical-base-lock.py --require-signatures
```

exits 20 on this tree (`base record is unsigned`), and the default mode exits
20 on any fixture whose source claims `distribution = redistributable`
without a verifiable signature. `digest-only local-only` is the only
permitted state today, so the base record is `distribution = local-only`.

## 4. Release bundle format (17.15) and canonicalization (17.26)

Fixed bundle members: `release-manifest.json`, `source-lock.json`,
`registry.json`, `schemas/`, `NOTICE/`, `SBOM/`, `checksums/`,
`signatures/`, `validation/`. The digest manifest fixes file order, LF line
endings, permission/symlink handling, archive format and canonicalization.
A release carries re-checkable content plus notices; digest-without-content
is local-only. `SBOM/`, `signatures/`, CVE scan records and release approval
do not exist yet, so no redistributable bundle can be assembled — the release
gates (`scripts/validate-integration.py --release`,
`scripts/verify-release-gate.py --release`, both exit 20) agree.

## 5. NOTICE status (17.29)

Base license: MIT (upstream `LICENSE`: `MIT License`, Copyright (c)
2026 zhaoxuya520). Record: `license_declared` MIT, `license_status`
verified, `third_party_review` not-required (first-party mother framework),
`maturity` verified (snapshot clean, HEAD == pin, digest-pinned, rechecked by
the verifier), `notice_file` root `NOTICE` (tracked; new-file pointers would
fail the security gate's tracked-file check, and T04's NOTICE is not edited
by this card). Root `NOTICE` already names `reverse-skill` and the baseline
commit, so the release gate's per-source naming check passes; it does not
carry the base `source_url`, which the release gate records as one
provenance finding (same class as the six pre-existing notice gaps). Union of
merged licenses stays `["MIT", "NOASSERTION", "NONE"]`, verdict
`undetermined` — unchanged.

## 6. Verification

```
$env:PYTHONIOENCODING='utf-8'
& (Resolve-ReverseToolSpec -Name 'pyre').Command cripts/verify-canonical-base-lock.py
& (Resolve-ReverseToolSpec -Name 'pyre').Command cripts/verify-canonical-base-lock.py --require-signatures
& (Resolve-ReverseToolSpec -Name 'pyre').Command cripts/verify-canonical-base-lock.py --json
```

Exit codes (spec 4.7): 0 ok, 10 needs_review (snapshot absent: digest,
HEAD and dirty cannot be machine-checked, each named), 20 blocked
(record missing, commit/digest mismatch, dirty snapshot, unresolvable
commit, redistributable-without-signature). Read-only; `--root` runs the
same gate against a fixture tree.

## 7. Known cross-card updates requested (not made; other owners' files)

- T26 `skills/scripts/community-route.py` line 798-801 (every source id must
  own a wrapper record): trips as `source reverse-skill: no wrapper record`.
  The base is the mother framework itself (its 43 skills ARE the canonical
  skills) and must not gain a 5th wrapper (4 wrappers are the frozen 17.27
  contract). Request: exempt `source_kind == canonical-base` from the
  wrapper-coverage rule. Blast radius measured 2026-09-30: 4 CI gates
  `test-contract-v2`, `test-community-route`, `test-route-ranking`,
  `test-community-decoys` go BLOCKED (all via `load_contract`), everything
  else green.
- T02 `skills/scripts/test-contract-v2.py` lines 228 (`== 4 sources`) and
  235 (`canonical-base` presence forbidden): both trip now that the
  spec-mandated 5th record exists. Request: derive the count and allow the
  `canonical-base` kind (enum line 179 already lists it).
- T12 `skills/community/source-lock.json` `registry_expectation` (4 ids):
  `scripts/verify-community-bundle.py` check 5 now reports source-id drift
  (exit 20). Request: extend the expectation with the base id once T12 owns
  the base attestation, or record T21's document as the base manifest.
- Root `NOTICE` source table lists four community sources; the base row is
  left for T04. The per-source naming check still passes (see section 5).
