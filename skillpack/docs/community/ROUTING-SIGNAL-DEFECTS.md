# Community routing signal defects (T26 evidence record)

Measured defect register for the community routing layer, with the exact reproduction
command for every number. Owner: T26. Baseline commit: `44592e9`, working tree clean.

This document exists because `HANDOFF.md` recorded one symptom — `bloodhound` returning
`needs_review` with zero references — and the measured cause is a set of nine defects
that trade against each other. Five of them are recall defects and four are precision
defects, so no fix may be accepted on the evidence of one side alone.

Everything below was produced by read-only scripts in `work\p0\`
(outside this repository, so the tree stays clean):

| script | what it measures |
| --- | --- |
| `p0-measure.py` | keyword inventory, slug/description self-recall, token document frequency, 38 named probes |
| `p0-diagnose.py` | field-level origin of each defect |
| `p0-diagnose2.py` | hyphen-compound tokenisation, keyword boilerplate share, the 52-record profile |
| `p0-diagnose3.py` | the over-trigger (precision) side |
| `p0-diagnose4.py` | per-record audit of the unreachable-records claim |
| `p0-diagnose5.py` | path/evidence-source shapes |
| `p0-proof-deadwidening.py` | the D1 proof |

Reproduce any row with:

```text
$env:PYTHONIOENCODING='utf-8'
python work\p0\p0-measure.py
python work\p0\p0-proof-deadwidening.py
```

## The register

| id | class | defect | measurement | mechanism |
| --- | --- | --- | --- | --- |
| D1 | recall / code | the kq-02 `_name_view` widening is unreachable | 293/293 records carry **1748** tokens reachable only through the widening; **87** records cannot become a candidate for a hint built from their own slug; `lattice` produces 1 widening hit and 0 references | `lookup()` gates candidacy on `_score()`, which uses the strict token set (`skills/scripts/community-route.py:589-591`); `_name_view()` is only consulted inside `_rank()`, i.e. *after* the gate |
| D2 | recall / normalisation | the description view is never widened for hyphen compounds | `bloodhound` → the description holds `BloodHound-guided`; `lattice` → `Lattice-based` | `_description_text()` is tokenised with the strict `tokens()` |
| D3 | recall / normalisation | no plural handling | `pcaps` ≠ `pcap`, `yaras` ≠ `yara`; both return 0 references | the tokeniser has no stemming and no plural aliases |
| D4 | recall / normalisation | every 2-character token is invisible | `tokens(x) == ∅` for `ad`, `os`, `ot`, `ai`, `s3`, `ci`, `db`, `io`, `id`; `ad cs` → ∅; `ci cd` → ∅ | token regex `[a-z][a-z0-9-]{2,}` requires ≥ 3 characters |
| D5 | precision / stopwords | the stopword list is applied after alias substitution, so one alias variant can never be stopped | `tokens("workflow") == {'alias_delivery'}` although `workflow` is in `STOPWORDS`; **154/154** ai-fullstack records answer `workflow`, `delivery`, `pipeline`, `devops`, `交付` at `status=matched confidence=1.0` | `normalize()` rewrites `workflow` → `alias_delivery` before the stopword filter runs; `STOPWORDS ∩ ALIASES-variants == {'workflow'}` |
| D6 | precision / provenance | adapter provenance pollutes the routing text | `community-raw` matches **293/293** records, `skills-hub` **293/293**, `alias_delivery` **155/293**; `capability`, `adapted`, `融合` all return `matched confidence=1.0`; **1415 of 2594 (54.5 %)** keyword entries are provenance/governance boilerplate | the legacy importer injected `project`, `skills-hub`, `upstream` and the source identifiers into every record's `keywords[]`, and every record's `path` begins with `community-raw/` |
| D7 | recall / data | genuine domain terms are absent from the routing text | `mimikatz` and `certipy` appear in 0 records, `bucket` in 0, and `bloodhound` only inside the compound `bloodhound-guided` | matching is pure token overlap; there is no curated signal layer |
| D8 | precision / process | no negative control exists anywhere in the repo | 182 L1 benchmark cases and 13 L2 ranking cases are all hits-only; no case anywhere asserts that a hint must **not** reach a skill | — |
| D9 | docs | `docs/community/ROUTE-RANKING.md` is cited but does not exist | 3 citations (`community-route.py` module docstring, `community-route.py` ranking-model comment, `test-route-ranking.py` module docstring), 0 files; no gate catches it | kq-02 added the citations and the weight model but shipped no document. **Closed by T26**: the document now exists and all three citations resolve |

## Outcome after T26

Every number below was recomputed by the coordinator with an independent harness
(`work/p0/p0-acceptance.py`) that does not import any implementer's verifier or runner,
so an implementer's own gate cannot certify itself.

| metric | baseline `44592e9` | after T26 | how |
| --- | --- | --- | --- |
| records that cannot be a candidate for their own slug | **87** | **0** | one routing view used for candidacy and both hit classes (D1) |
| slug self-recall | 187/293 | **274/293** | D1 + D2 + D3 + D4; the residual 19 = 16 records whose `source_path` is `…/skills/SKILL.md` (slug reduces to the stopword `skills`) + 3 crowded out of the 3-reference cap |
| zero-reference probes (38 named) | **7** | **1** (`s3 bucket`) | see the survivor note below |
| records matched by `community-raw` | 293/293 | **0** | D6, in code and in `noise[]` |
| records matched by `skills-hub` | 293/293 | **0** | same |
| `tokens("workflow")` | `{'alias_delivery'}` | **`∅`** | D5: stopwords are stripped before alias substitution |
| `lookup("workflow")` / `("adapted")` / `("capability")` / `("ai")` | `matched` | **`missing_input`** | D6 and the `ai` short-token correction |
| curated signals, every one machine-evidence-checked | 0 | **28** | `routing-signals.json` |
| `noise[]` entries, each ≥80 % of one source | 0 | **6** | measured, not asserted |
| negative-control cases in the repo | **0** | **57** (29 decoys + 28 positives) | D8 |
| decoy pass rate | not measurable | **20/29 = 0.6897** | gates pinned at 0.50 / 0.75, deliberately below the floor |
| positive pass rate | not measurable | **27/28 = 0.9643** | |

### The single surviving zero-reference probe is correct behaviour

`s3 bucket` reaches nothing because **no record in the corpus owns S3 or object storage**.
Measured: the token `bucket` occurs in 0 of 293 routing texts and `s3` in 0 of 293; the
record that a corpus case had nominated for it
(`community-hack-skills-127`, `unauthorized-access-common-services`, domain Redis / Rsync /
PHP-FPM / AJP / Hadoop YARN / H2 Console) contains **zero** occurrences of `s3`, `bucket`,
`aws` or `object storage` across both of its files. Per the frozen evidence rule, a keyword
that no record's own directory can evidence must not be invented, so the probe stays at
zero references and the corpus records it as a documented absence rather than an engine
defect.

### What is deliberately still open

Ten corpus cases still fail after T26, and they are the honest residue rather than a
to-do that was skipped. Naming them matters more than the count:

1. `governance-fusion-cjk` — the Chinese word for "blend/integrate" leads the delivery
   wrapper. It is a real word in 56 descriptions (36 % of ai-fullstack), so rule 1.3
   (≥80 % of one source) forbids treating it as boilerplate. Closing it needs a mechanism
   the frozen contract does not have.
2. `governance-word-governance` — `governance` alone is answered by an on-chain-governance
   record. A genuine sense collision, not a tokenisation defect.
3. `governance-word-wrapper` — the engine's own vocabulary word is answered by a
   path-traversal record (PHP stream wrappers). Arguably *correct* domain behaviour; the
   case encodes a stricter standard than "wrong".
4–7. `alias-delivery-word` / `alias-pipeline-word` / `alias-devops-word` /
   `alias-delivery-cjk` — the alias siblings of the stopped word `workflow`. All four
   return a byte-identical reference list led by the RAG-pipeline record. The wrapper
   answer is defensible; the intra-wrapper *leader* is arbitrary, and the status is
   `matched` at confidence 1.0 rather than `needs_review`.
8–9. `hypernym-endpoint-top` / `hypernym-application-top` — bare hypernyms led by an
   arbitrary sub-case record.
10. See the survivor note above.

No claim is made that these are safe, and no claim is made of a net improvement on the
precision side alone. The recall side moved materially and is measured; the precision side
moved by exactly three named over-triggers and is measured too.

## Why D8 matters more than it looks

A positive-only corpus cannot detect an over-broad rule. The reference package
`D:\Project\临时对话\custom-skill-router` records the measured consequence in its own
runner docstring: its 49-case benchmark scored 49/49 before and after 13 rule
replacements, and 49/49 again while a duplicate was removed from 16 routes — while its
`game-cheat` route was answering `ESP32 用 Arduino 控制继电器怎么接线` and its
`finance-movement` route was answering `operating system kernel panic`.

The same shape exists here. D5 and D6 are both invisible to every gate in this
repository, because all of them assert hits and none asserts a forbidden target.

## Corrections this measurement forced on the source handoff

`HANDOFF.md` section 6 says the fix is to mine keywords from the real descriptions. That
is necessary but not sufficient, and two of its stated premises did not survive
measurement:

1. **"关键词从真实描述挖掘" is not the main lever.** 87 records are unreachable purely
   because of D1, a code defect, with no data change involved. Mining keywords first
   would have added data on top of a broken gate and hidden the real cause.
2. **Removing `path` from the routing text does not change recall.** Measured: 190/293
   records match their own slug tokens with `path` in the text and 190/293 without it.
   `path` is a *precision* hazard (D6), not a recall one. An earlier hypothesis in this
   session asserted the opposite and was wrong.

Also recorded: the 52 records that cannot be reached from their own slug are **51
ai-fullstack-delivery + 1 ctf-super-hub**, and the dominant cause is that their upstream
slug is English while their description is Chinese — a cross-lingual gap that token
overlap cannot bridge on its own.

## Contract frozen from this register

The interface, the ranking model and the acceptance targets are frozen in the T26 task
card (`docs/INTEGRATION-IMPLEMENTATION-SPEC.md` section 19). The shipped model is
documented in [ROUTE-RANKING.md](ROUTE-RANKING.md).

Note on D9: while T26 was in flight this path was written as a code span rather than a
Markdown link, because a link to a document that did not exist yet made
`verify-doc-links.py` fail — correctly. That is the honest illustration of D9 itself: the
same missing file had been cited three times from `skills/scripts/**` Python comments,
where no gate looks, so it went unnoticed for a whole commit.

## Known limitations

1. Every number here is a measurement of commit `44592e9`. It is not a claim about the
   state after T26 is implemented — the after-numbers are recorded in the T26 report.
2. D7 is **not** fully closable. Curated signals can only cover terms that are present in
   a record's own directory; a term that appears nowhere in the vendored material cannot
   be justified and must not be invented.
3. The 80 %-per-source rule that justifies `noise[]` entries is a heuristic. It is
   machine-checked, but it is a policy choice, not a theorem.
4. No gate currently detects D9-style broken citations from `skills/scripts/**` into
   `docs/**`. `verify-doc-links.py` scans `docs/community/**` and community `SKILL.md`
   files, not Python sources.
