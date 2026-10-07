# Community route ranking

How `skills/scripts/community-route.py` decides which adapted community references
answer a hint, and why each part of the model is shaped the way it is.

Written by T26 (work package WP4). It documents the code as shipped on 2026-09-30,
not the design that was proposed. Where the two differ, this document follows the
code and says so.

Defect D9 in `ROUTING-SIGNAL-DEFECTS.md` is the reason this file exists: three
citations inside `skills/scripts/**` named it and no file was ever written. The
citations are:

| citation | location |
| --- | --- |
| module docstring | `skills/scripts/community-route.py:16` |
| ranking-model comment | `skills/scripts/community-route.py:87` |
| test module docstring | `skills/scripts/test-route-ranking.py:6` |

The same path is also cited from `skills/community/routing-signals.json`,
`docs/WORK-BOARD.md`, `docs/INTEGRATION-IMPLEMENTATION-SPEC.md` and
`docs/community/ROUTING-SIGNAL-DEFECTS.md`. Nothing in the repository verifies those
citations: `verify-doc-links.py` scans Markdown documents, and a path written in a
Python comment is not a link it can see.

## Files

| file | role |
| --- | --- |
| `skills/scripts/community-route.py` | the engine. Wrapper metadata comes from `registry.json`, context profiles from `profile-map.json`, layer-1 routes from `routing.json`, and the curated layer from `routing-signals.json`. |
| `skills/community/routing-signals.json` | the curated layer: `token_aliases`, `short_tokens`, `noise[]`, `signals[]`. |
| `schemas/community-routing-signals.json` | the shape contract for that document. |
| `skills/scripts/verify-routing-signals.py` | the gate. Validates the shape, compiles every regex, re-checks every evidence string and every noise justification, and fails closed. |
| `skills/scripts/test-route-ranking.py` | ranking regressions: the recomputability invariant, name-over-description order, and one permanent assertion per defect the layer must close. |
| `skills/tests/community-decoys.json` | the negative control: 30 hints that must **not** lead to a named target, plus 27 positives that must keep working. |
| `skills/scripts/test-community-decoys.py` | runs that corpus and prints the per-case result, the over-trigger rate and the named over-triggers. It prints no over-narrowing cases, because the corpus no longer has any: the single one that existed (`recall-s3-bucket`) was measured to be unjustifiable and was converted into the decoy `absence-s3-bucket`. |
| `docs/community/ROUTING-SIGNAL-DEFECTS.md` | the measured defect register D1-D9 that motivated all of this. |
| `D:\Project\skills-hub\work\p0\*.py` | the coordinator's read-only measurement battery. `p0-measure.py` produces self-recall and the 38 named probes; `p0-acceptance.py` re-scores the corpus independently of the repo's own gates; `p0-proof-deadwidening.py` is the D1 proof; `p0-diagnose*.py` trace each defect to a field. |

## 1. Two layers, and why they are separate

Layer 1 chooses a **wrapper**. `skills/config/routing.json` is the single source of
truth for that; it holds 48 route ids (`R0` through `R49` with `R42` and `R43`
unused), and each of the four community wrappers declares its route id in
`registry.json`:

| wrapper | route id | `routing.json` label |
| --- | --- | --- |
| `wrapper-hack-skills` | `R46` | Web application injection |
| `wrapper-ctf-super-hub` | `R47` | CTF community hub |
| `wrapper-ai-fullstack-delivery` | `R48` | Full-stack delivery workflow |
| `wrapper-apk-reverse-community` | `R49` | APK capability extension |

Layer 2 is `community-route.py`, and it only **narrows the references inside a wrapper
that layer 1 already chose**. It cannot promote a raw community skill into the answer.
Three properties enforce that:

* every match the script emits is a wrapper record read from `registry.json.wrappers[]`,
  and every emitted object carries `"access": "wrapper-only"`;
* every reference listed under it is `discovery: reference-only` — the contract
  rejects a wrapper that points at anything else;
* the vendored bodies live under `community-raw/`, which is physically outside the
  client discovery roots, so there is nothing to invoke directly even if a caller
  wanted to.

The separation is deliberate. Layer 1 answers "which capability family is this task?" on
a 48-entry table that a human maintains. Layer 2 answers "which three of these 293
adapted documents should I actually open?" on token evidence. Letting layer 2 choose a
wrapper would create a second, unreviewed routing table, which is exactly the
"second global rule set" the integration forbids.

It also means a bad hint degrades in a bounded way. Measured today: the hint
`capability` produces **0** candidates and `missing_input` — the word the adapter
injected is in the engine's stopword set. The larger shape of the claim still holds:
a hint can only ever select inside wrappers, never four competing ones.

## 2. The field-aware weight model and the invariant

Three constants, in `community-route.py`:

```python
SIGNAL_HIT_WEIGHT      = 4
NAME_HIT_WEIGHT        = 3
DESCRIPTION_HIT_WEIGHT = 1
REFERENCE_LIMIT        = 3
MIN_CONFIDENCE         = 0.35
NEAR_TIE_DELTA         = 0.20
```

The three hit classes are **disjoint by construction**, so the score is always a pure
sum over the counts the script reports:

```text
rank_score == SIGNAL_HIT_WEIGHT      * len(signal_hits)
            + NAME_HIT_WEIGHT        * len(name_hits)
            + DESCRIPTION_HIT_WEIGHT * len(description_hits)
```

* `signal_hits` — curated signal ids that fired for this record on this hint.
* `name_hits` — `hint_terms & routing_view(name_text)`.
* `description_hits` — `(hint_terms & routing_view(description_text)) - name_hits`.
  A token that appears in both fields is charged the name weight **once**; the
  subtraction is what makes the classes disjoint and the invariant exact.

`name_text` is `legacy_original_name + path + source_path` (the fields that *name* the
capability). `description_text` is `legacy_description + keywords` (the fields that
*describe* it). Both are noise-stripped first, see section 4.

**The invariant is the contract, not the formula.** Anyone reading a JSON result must
be able to add up the reported lists and land on the reported `rank_score`. That is
what makes the ranking auditable: a number the reader cannot recompute is a number
they have to trust. `test-route-ranking.py` asserts it, and I re-verified it today over
**260** reported references, drawn from the 38 named probes crossed with all five
source filters: **0 violations**. The same run fired **8** distinct curated signals, so
the signal term is exercised, not dead code. (Both numbers are the output of the
reproducible sweep in "Reproducing the numbers in this document" below; an earlier
draft quoted a smaller battery — 29 hints, 11 signals — that I could not reproduce
against the shipped files, so it is replaced rather than carried.)

Ordering inside one wrapper uses the key in `_reference_sort_key`:

```text
(-rank_score, -len(name_hits), 0 if any name hit is an alias_ token else 1, path)
```

The third component was added in T26 and is worth naming because the freeze did not
predict it. The routing-view widening (section 3) creates ties that the old
three-component key broke on `path`, which demoted the correct record in the case
`SSRF metadata endpoint access`. Preferring a name hit that is a canonical `alias_`
token over a plain generic word restores the documented "name match beats description
mention" intent in those new ties. It changes no weight, no `REFERENCE_LIMIT`, no
wrapper score and no confidence.

### What the ranking model does *not* decide

`_score()` is untouched and is still the only input to the wrapper score and to
confidence:

```text
_score(item, hint_terms) = len(hint_terms & tokens(_reference_text(item)))
wrapper score             = max(reference.score) + len(wrapper_alias_hits)
confidence                = min(1.0, best_score / max(1, len(hint_terms)))
```

It measures **evidence breadth** — how many distinct hint tokens a record answers to
anywhere — and nothing else. Two consequences matter when reading output:

1. A record reached **only** through a curated signal has `score = 0` and
   `confidence = 0.0`, which is `needs_review`. Measured today: `lookup("mimikatz")`
   ranks `skills/active-directory-acl-abuse/SKILL.md` and
   `skills/windows-lateral-movement/SKILL.md` at `rank_score = 4` each from signals
   `community-hack-skills-037` and `community-hack-skills-134`, with `score = 0`,
   `confidence = 0.0`, `status = needs_review`, reason `low_confidence`. The signal
   makes the record reachable and correctly ordered; it deliberately does not buy
   confidence, because confidence must stay a statement about token evidence.
2. The 4.7 statuses, the ambiguity rule and the exit-code table are unchanged.
   `MIN_CONFIDENCE` and `NEAR_TIE_DELTA` keep their values, and ambiguity is evaluated
   over **all** wrapper candidates before `--limit` is applied, so a caller cannot
   hide a tie by asking for one result.

## 3. The routing view: one widened view, used for everything

```python
def routing_view(text):
    found = tokens(text)                      # strict token set
    view = set(found)
    for token in found:
        if token.startswith("alias_") and "-" in token:
            view.add(token.split("-", 1)[0])   # drop the alias_ prefix
        view.update(part for part in token.split("-") if part)   # hyphen parts
    return fold_aliases(view)                 # curated token_aliases, both sides
```

A hyphenated slug is **one** token to the tokeniser. `BloodHound-guided` emits
`bloodhound-guided` and never `bloodhound`; `Lattice-based` emits `lattice-based` and
never `lattice`. An aliased slug keeps its prefix: `alias_ssrf-server-side-request-forgery`.
The view adds the hyphen parts, drops the `alias_` prefix, and folds the curated
token aliases, so a hint that a human plainly made reaches the record that carries it.

The same function is used in three places, and that is the whole point:

```python
candidacy:  hint_terms & (routing_view(name_text) | routing_view(description_text))  != {}
            or a curated signal fired
rank:       name_hits        = hint_terms & routing_view(name_text)
            description_hits = (hint_terms & routing_view(description_text)) - name_hits
```

### The defect this fixed (D1)

kq-02 added the widening to `_name_view()` only, and left `lookup()` gating candidacy
on `_score()`, which tokenises the record with the **strict** set. `_name_view()` was
consulted afterwards, inside the ranker. The widening was therefore unreachable code:
a record that only matched through it never became a candidate. The old design even
documented the inconsistency as a feature — "only the name view is widened: the
evidence-breadth score keeps the strict token set" — and that sentence has been
withdrawn.

Measured at the frozen baseline, in `ROUTING-SIGNAL-DEFECTS.md` and
`DESIGN-FREEZE.md` D1: **293/293** records carried **1748** tokens reachable only
through the widening, **87** records could not become a candidate for a hint built from
their own slug, and `lattice` scored one widening hit against zero references.
Reproduce with `D:\Project\skills-hub\work\p0\p0-proof-deadwidening.py`.

Re-measured against the shipped engine today, those three numbers are **not**
comparable to the baseline, because the baseline itself moved: stopwords are now
stripped before alias substitution (section 4), noise is removed from record text, and
nine short literals are now tokens. What the shipped engine measures is:

| measurement | today |
| --- | --- |
| records whose routing view adds at least one token the strict set lacks | **263/293** |
| tokens reachable only through the widening | **1128** |
| records that cannot become a candidate for their own slug | **19** |
| those 19, re-measured through `lookup()` | **274/293 reachable** |

The 19 are 16 `community-ai-fullstack-delivery-*` records whose `source_path` is
`.../workflows/<slug>/skills/SKILL.md`, plus three real misses named in limitation 10
(`community-ctf-super-hub-011`, `community-ctf-super-hub-031`,
`community-ai-fullstack-delivery-175`). A harness that derives the slug from
`Path(source_path).parent.name` gets the literal word `skills`, which is a stopword and
therefore yields no hint token at all; that accounts for the 16 and is an artifact of
the harness, not a routing defect. The other three are genuine, and the honest figure
is therefore **274/293**, not a round number: 16 are the harness artifact and 3 are
records whose real slug genuinely does not reach them today. `p0-measure.py` reports the
same 274/293 slug self-recall.

`_score` deliberately stays on the strict set. It is a breadth counter and a
confidence input, not a candidacy gate, and widening it would inflate confidence on
incidental hyphen-part matches. Nothing gates anything now: the three quantities are
candidacy, `rank_score` and `_score`, and each is computed from its own inputs.

## 4. Normalisation

All four knobs are applied to the **record side**, except `token_aliases`, which is
symmetric, and the stopword list, which is applied to both.

### `noise[]` — record-side provenance suppression

Six entries ship today. Each is substituted **out of the record's text before
tokenising**, and never out of the hint:

```python
re.sub(pattern, " ", text, flags=re.IGNORECASE)
```

Substituting rather than deleting whole tokens is what lets a noise pattern break a
compound: `skills-hub` becomes `skills hub`, and `skills` is then dropped as a
stopword. The replacement is a space so a removal cannot glue its neighbours into a new
token.

| pattern | scope | why it is admissible |
| --- | --- | --- |
| `community-raw` | any | the vendored snapshot root, in `path` and `source_path` of 293/293 records |
| `skills-hub` | any | host-project name injected into `keywords[]` of 293/293 records |
| `upstream` | any | same importer pass, 293/293 records |
| `ai-fullstack-delivery` | any | source identifier, 154/154 of its own source |
| `hack-skills` | any | source identifier, 103/103 of its own source |
| `ctf-super-hub` | any | source identifier, 35/35 of its own source |

The per-source **≥ 80 %** rule is the admission test, and it is enforced by
`verify-routing-signals.py`, not by review. A word that appears in half of all skills
is not signal; a word that appears in every record of one vendor tree is provably that
tree's boilerplate even when it is 12 % of the registry. `ctf-super-hub` is the case
that forces the rule to be per-source rather than global.

`scope: "any"` covers all five routed fields, because the record text is split into
two views and each noise pattern is applied to both: `any` to the name view
(`legacy_original_name`, `path`, `source_path`) and to the description view
(`legacy_description`, `keywords`). `scope: "description"` is applied to the
description view only.

Where noise is **not** applied, stated because it is surprising: `_score()` reads the
raw `_reference_text()` and is not noise-stripped. That is harmless today only because
the hint side cannot produce any of these six literals as a token — `community-raw`,
`skills-hub` and `upstream` are stopwords, and the three source identifiers are split
by alias substitution before tokenising (section "Known limitations"). A future noise
entry whose literal is reachable from a hint would inflate `_score`, and therefore
confidence, without being neutralised.

### `token_aliases` — curated, symmetric, not a stemmer

Sixteen pairs ship today, folding a plural or a variant onto a canonical token on
**both** sides: the hint is folded in `lookup()`, and each view is folded at the end of
`routing_view()`. Symmetry is structural, not a property anyone has to remember.

This is a lookup table, not stemming. There is no `ies → y`, no `ing` stripping and no
rule that fires on a form nobody put in the file. Two pairs were measured and kept:

| pair | records carrying the plural | records carrying the singular |
| --- | --- | --- |
| `applications → application` | 7/293 | 14/293 |
| `paths → path` | 9/293 | 18/293 |

Two more ship because the freeze names them as its own D3 probes, and their
singulars are corroborated even though their plurals are not: `pcaps → pcap`
(`pcap` in 2/293, `pcaps` in 0/293) and `yaras → yara` (`yara` in 1/293, `yaras` in
0/293). Both now return 1 reference each, up from zero. `verify-routing-signals.py`
prints the corpus count for every alias rather than hiding it.

### `short_tokens` — the measured two-character blind spot

The token regex is `[a-z][a-z0-9-]{2,}`, which requires three characters, so before
this layer `ad`, `os`, `ot`, `ai`, `s3`, `ci`, `db`, `io`, `id` were all invisible and
`ad cs` and `ci cd` both tokenised to the empty set. A literal is added to this list
only when it can be shown **helpful or harmless**; eight ship today and the global
minimum stays at three for everything else. They are added by a separate,
boundary-guarded pattern (`(?<![a-z0-9])…(?![a-z0-9])`) rather than by loosening the
main regex, because lowering the global minimum would admit arbitrary ASCII fragments.

This is the one knob in the layer with a measured precision cost, and it is not zero.
Records carrying each literal as a routing-view token, strict tokeniser versus shipped:

| literal | strict | shipped | `lookup(literal)` | status |
| --- | --- | --- | --- | --- |
| `ad` | 0/293 | 4/293 | 1 reference | `needs_review` |
| `ci` | 0/293 | 4/293 | 3 references | `matched` |
| `db` | 0/293 | 1/293 | 1 reference | `matched` |
| `id` | 0/293 | 2/293 | 2 references | `matched` |
| `io` | 0/293 | 2/293 | 1 reference | `needs_review` |
| `os` | 0/293 | 0/293 | 0 references | `needs_review` |
| `ot` | 0/293 | 0/293 | 0 references | `needs_review` |
| `s3` | 0/293 | 0/293 | 0 references | `needs_review` |

`ai` is the one literal that was admitted and then **removed**, and it is the most
instructive measurement in this section. The list originally carried nine literals
including `ai`. The post-ship measurement showed it was harmful rather than merely
broad: the routing view hyphen-splits the source identifier `ai-fullstack`, so `ai`
was present in the routing text of **156** of 293 records and gave every one of those a
NAME-level (weight-3) hit for any hint containing `ai`. `lookup("ai")` returned three
wrappers at confidence 1.0 — held back from `matched` only by `ambiguous_tie` — so the
ambiguity rule was the only thing standing between a bare two-letter hint and a wrong
routing answer. `ai` is a source-identifier fragment, not a capability word, so it was
dropped; `lookup("ai")` is now `missing_input` and `tokens("ai") == set()`. `os`, `ot`
and `s3` stay even though they occur in 0 of 293 routing texts, because a literal that
matches nothing is useless but harmless, while a literal that matches 156 records is
harmful; design-freeze 1.1 only allows dropping a short token that can be demonstrated
harmful, and that is exactly the distinction being applied. The provenance and the
measurement are recorded in `skills/community/routing-signals.json` under `meta.note`.

The `s3` literal is admitted and still matches nothing, which is exactly why the
surviving zero-reference probe is discussed in limitation 8 below.

### Stopword ordering

`tokens("workflow") == set()` today. Before T26 it returned `{'alias_delivery'}`,
because `normalize()` ran the alias substitution first: `workflow` was rewritten to
`alias_delivery` before the stopword filter could see it, and the filter never saw the
word it was meant to reject. `STOPWORDS ∩ ALIASES-variants == {'workflow'}`, so exactly
one stopword was structurally unstoppable. All 154 ai-fullstack records then answered
`workflow`, `delivery`, `pipeline`, `devops` and `交付` at `matched`, confidence 1.0
(`DESIGN-FREEZE.md` D5).

The rule that fixes it: **stopwords are stripped from the word form first, and the
replacement is a space.**

```python
value = unicodedata.normalize("NFKC", text or "").lower()
value = STOPWORD_RE.sub(" ", value)      # before the alias pass
return ALIAS_RE.sub(lambda m: f" alias_{ALIAS_LOOKUP[m.group(0).casefold()]} ", value)
```

The space matters: `...使用workflow交付...` must not become one new token when
`workflow` is removed. The hyphenated provenance entries are matched as whole literals,
longest first, so `community-raw` is removed as one unit and never partially as
`community`. The same pass runs on the hint and on the record, which is why
`tokens("community-raw")`, `tokens("skills-hub")`, `tokens("upstream")` and
`tokens("workflow")` are all empty and those four hints now return `missing_input`.

## 5. The curated signal layer

Twenty-eight signals ship today, all `evidence_kind: "raw"`, all ids unique, all ids
resolving to a real registry record. They span two sources (`hack-skills` and
`ctf-super-hub`); the other two sources have none. `exclude` is empty on all 28 — the
field is schema-supported and compile-checked, and writing an exclusion nobody can
justify would be decoration.

```json
{
  "id": "community-hack-skills-037",
  "must": ["\\bbloodhound\\b", "\\bmimikatz\\b", "\\bkerberoast(ing)?\\b", "\\bgpo\\b", "\\bdcsync\\b"],
  "exclude": [],
  "evidence": "mimikatz",
  "evidence_kind": "raw",
  "note": "<why a human should believe this>"
}
```

* `must` / `exclude` are ECMAScript-style regexes, `re.search`, case-insensitive,
  matched against the `lower()`-cased hint. That is the same convention
  `skills/config/routing.json` already uses, so both layers speak one language.
* A signal **fires** iff at least one `must` matches and **no** `exclude` matches.
* `id` names a registry record. A signal can only ever make *that* record reachable;
  it is a per-record assertion, not a global rule.
* `note` is reported verbatim in `signal_notes` and inside `route_explanation`, so a
  human reads why a record won rather than only a number.

The layer is a third fail-closed input, handled exactly like the registry and the
profile map: a missing file is `unavailable`, a malformed one is `blocked` with
`schema_invalid`, and an unknown scope or an uncompilable regex is a violation rather
than something to ignore. An **empty-but-valid** document is not an error — it is the
state the skeleton shipped in, and the ranking model must survive it, which is why the
engine treats every array as optional at the matching level and mandatory at the
validation level.

### The evidence rule: why "mined from the real description" is provable

The claim "these keywords were mined from the real descriptions, not invented" is
worth nothing as an assertion. It is worth something as a check the verifier runs on
every change:

* `evidence_kind: "record"` — `evidence.casefold()` must be a substring of that
  record's own `legacy_original_name + legacy_description + source_path`. Use this when
  the term is already in the frontmatter and the problem is that it is unreachable
  (for example because it is buried in a hyphen compound).
* `evidence_kind: "raw"` — `evidence.casefold()` must be a substring of at least one
  text file **inside the named record's own directory**
  (`Path(record["path"]).parent.rglob("*")`). Use this when the term is absent from
  the frontmatter entirely and only the vendored body can justify it.

A signal whose evidence cannot be found is **invalid** and the verifier fails closed.
This is the mechanism that stops the layer degenerating into invented keywords: a
curator cannot add "the corpus clearly needs a `bucket` signal" and have it merge. If
`bucket` appears nowhere under a record's own directory, there is no evidence to cite,
and the correct action is to leave the hole named rather than fill it.

The comparison is case-insensitive on both sides. A case-sensitive reading would
reject a term that appears as `BloodHound_PATHS.md` or `ECDSA.recover` and would let
capitalisation pass as evidence, which it is not.

### Reading the reported output

```
reference order: curated signal x4 > name match x3 > description mention x1, top 2 of 2 shown
```

and, when signals fired:

```
curated signal x4: community-hack-skills-037, community-hack-skills-134 (<their notes>)
```

Every reference carries `rank_score`, `signal_hits`, `signal_notes`, `name_hits` and
`description_hits`, which is exactly the data the invariant in section 2 needs. If a
reader cannot recompute a score from those lists, that is a bug in the engine and
`test-route-ranking.py` should fail.

## 6. `REFERENCE_LIMIT = 3` is a product decision

Three adapted references per wrapper is what a caller can read before it has to
re-query. Measured today: the hint `security testing` produces **38** candidates
inside `hack-skills` and 22 inside `ai-fullstack-delivery`, and both wrappers show 3,
ordered `skills/ai-ml-security/SKILL.md`, `skills/linux-security-bypass/SKILL.md`,
`skills/macos-security-bypass/SKILL.md`, each at `rank_score = 3` from the single name
hit `security`.

It is a **presentation** cap and it deliberately stays at 3. Raising it would convert a
ranking defect into a longer list. If reference 4 is wrong, a cap of 10 does not fix
the ordering — it just makes the defect harder to notice, because the caller has no way
to tell which of the ten the engine actually believed. The cap is therefore only ever
changed together with an argued ranking change, and never as a way to make a case look
better.

Note that the cap applies to **shown** references, not to the candidate set and not to
the ambiguity check: `needs_review` for a near-tie is computed over every wrapper
candidate, before `--limit` is applied.

## 7. What is deliberately not done

* **No general stemmer.** `token_aliases` is a hand-measured table of sixteen pairs.
  A stemmer would fold forms nobody measured, and its errors are invisible: a wrong
  fold creates matches, and this repository has no test that could see them.
* **No global lowering of the token minimum.** `short_tokens` admits eight named
  literals. Lowering the main regex to two characters would admit arbitrary ASCII
  fragments across all 293 records with no per-literal justification.
* **No rewriting of `registry.json`.** Recall is fixed in code and in
  `routing-signals.json`, not by editing the registry. The registry is the fact source
  for wrappers, profiles and paths.
* **No rewriting of `skills/config/routing.json` or `profile-map.json`.** Those are
  layer 1 and the context-profile contract; this layer does not touch them.
* **No rewriting of `community-raw/**`.** The vendored sources stay as upstream
  published them. The evidence rule reads them; it never edits them.
* **No re-running of `scripts/adapt-community.py`.** It rewrites 1111 paths with no
  backup and is hard-blocked (WORK-BOARD CR-002).
* **`noise[]` is not applied to the hint.** The freeze fixes it as record-side only.
  That keeps a hint like "hack-skills" honest rather than silently rewriting what the
  caller typed; the cost is listed under Known limitations.

## 8. Negative controls: the corpus, the rate, and the threshold

`skills/tests/community-decoys.json` and `skills/scripts/test-community-decoys.py`
**did not exist when this document was first drafted on 2026-09-30**; they landed from
WP3 later the same day, and this section was rewritten against the real corpus rather
than left as a placeholder. Everything below is measured, not projected:

```text
python skills/scripts/test-community-decoys.py     # exit 0
```

### The problem it solves (D8)

Every other test in this repository asserts that a hint *reaches* something. The 182
L1 benchmark cases and the 13 L2 ranking cases are all hits-only. A hits-only corpus
scores perfectly against an over-broad rule — the rule reaches the right records *and*
the wrong ones, and nothing counts the wrong ones. That is how D5 and D6 stayed
invisible through several rounds.

A negative control asserts the opposite direction: a hint that must **not** be answered
by a named wrapper or a named reference.

### Corpus shape, measured today

| | count |
| --- | --- |
| decoy cases ("must not lead") | 30 |
| positive cases ("must keep working") | 27 |
| decoy bug classes | `D6-provenance` 8, `D6-governance` 8, `D5-stopword-alias` 5, `D4-short-token` 4, `hypernym` 4, `D7-recall` 1 |

The positive half is not optional. A corpus of negatives alone can be satisfied by
making the engine arbitrarily narrow, so 27 positives pin the recall the signal layer
exists to restore. They are the 13 cases `test-route-ranking.py` already pins
(8 description-only + 5 name-match, verified by reading that file's
`DESCRIPTION_ONLY_CASES` and `NAME_MATCH_CASES`), the twelve hints that were broken
before T26 and that a curated signal can now restore (`bloodhound`, `mimikatz`,
`certipy`, `BloodHound DCSync shadow credentials`, `lattice`, `pcaps`, `yaras`,
`frida`, `rubeus`, `sliver`, `hashcat` and `llm integration`), and the two
guards added in the follow-up wave that keep the fixes from being over-applied:
`recall-ai-word-still-routes` and `recall-capability-word-still-routes`. The `s3 bucket`
hint is deliberately **not** in this half — see limitation 8.

Note what is *not* on that list: `capability` and `adapted`. An earlier draft named
them as "hints that were broken before T26". They were, and they are fixed differently
from the rest: rather than being made reachable, both words are now in the engine's
`STOPWORDS` constant and return `missing_input`, so they appear in the corpus as the
decoys `governance-capability` / `governance-adapted` and their strict forms, and in the
positives only as `recall-capability-word-still-routes`, which pins that a multi-word
hint containing the stopped word still routes on its other terms.

### The two rates, and the threshold

```text
decoy cases:    21/30 = 0.7000   (gate: >= 0.50)
positive cases: 27/27 = 1.0000
combined:       48/57 = 0.8421   (gate: >= 0.75)
PASS test-community-decoys: decoy gate and combined gate both hold
```

Both gates sit **just under the measured floor**. That is the whole construction. A
threshold of 1.0 would be permanently red and would pressure anyone into deleting cases
to reach green; pinning it under the floor means any *new* over-trigger moves the
number immediately, while the known failures stay visible per case. A gate that is
green because its cases were deleted is not a gate.

**Nine** over-triggers fail today, and no over-narrowing case fails at all. All nine
are named in the run output, not hidden:

`governance-fusion-cjk`, `governance-word-governance`, `governance-word-wrapper`,
`alias-delivery-word`, `alias-pipeline-word`, `alias-devops-word`,
`alias-delivery-cjk`, `hypernym-endpoint-top`, `hypernym-application-top`.

Every one of them maps to a limitation listed below. Two facts about this list are worth
stating plainly, because both are the corpus doing its job. First, the decoys that
closed are closed because the engine changed, not because the case was deleted:
`governance-capability` and `governance-adapted` now pass because those words are in
`STOPWORDS`, and all four `short-token-ai-*` cases pass because `ai` was dropped from
`short_tokens`. The negative-control rows for both are still in the corpus and still
report their state, so a regression in either direction goes red. Second, the runner
prints **no** over-narrowing section any more, and that is the honest output rather than
a silent omission: the one over-narrowing case that existed, `recall-s3-bucket`, was
measured against the record it named and found to be unsatisfiable by any record in the
corpus, so reporting it as over-narrowing would have named a non-existent capability as a
defect. It is now the decoy `absence-s3-bucket`, which passes, and the evidence is kept
in that case's `why` field.

The `D6-provenance` hints that **pass** (`community-raw`, `skills-hub`, `upstream`,
`project`, `source` — all `missing_input`) are the measured form of the D6 target:
293/293 records before, 0 after.

### What the corpus does not cover yet

An earlier draft of this section claimed there was **no `short_tokens` case** and that
`ai` was unprobed. Both halves of that are now false, and the correction is worth
stating rather than quietly deleting. The class `D4-short-token` exists and carries
four decoy cases (`short-token-ai-delivery`, `short-token-ai-ctf`, `short-token-ai-hack`,
`short-token-ai-record`) plus one positive (`recall-ai-word-still-routes`); all four
decoys now pass because `ai` is out of `short_tokens`, and they are the cases that would
catch it being re-admitted. `p0-acceptance.py` independently pins the same fact.

What is genuinely still unprobed is narrower, and should be stated as such:
`ctf-super-hub`, `apk-reverse-community` and `ai-fullstack-delivery` as literal hints are
still not corpus cases, and no case covers a short token other than `ai`. Until those
exist, the combined rate of 0.8421 says nothing about them — it is a rate over the
cases that were written, not a claim about the hint space.

## Known limitations

1. **`ai` was an over-trigger surface, and T26 closed it by dropping the literal.**
   The evidence is kept here because the limitation was real, not because it is still
   open. `ai` reached **156/293** records as a token, because the routing view splits
   `ai-fullstack-delivery`, `ai-ml-security`, `ai-deployment` into hyphen parts, and it
   did so at NAME weight, not as an incidental description mention. The measured harm:
   `lookup("ai")` returned **3 wrappers at confidence 1.0**, held back from `matched`
   only by `ambiguous_tie`. A two-letter source-identifier fragment was one ambiguity
   check away from a wrong routing answer. `ai` is no longer a token; `lookup("ai")` is
   `missing_input` with 0 wrappers, and four `D4-short-token` decoy cases hold that
   state. The limitation that remains is narrower: the fix is *removal*, so a caller
   who genuinely means the word "ai" as a capability word gets nothing from the bare
   hint — which is why `recall-ai-word-still-routes` exists, pinning that
   `ai deployment strategy` still routes and still ranks `ai-deployment` first. That
   arrangement is a deliberate trade, not a clean win: the corpus now contains no
   `short_tokens` case for any literal other than `ai`, so the other seven admitted
   literals are unprobed.
2. **A source identifier used as a hint still routes.** `noise[]` is record-side by
   freeze, and alias substitution runs before tokenising, so a hint splits instead of
   matching the noise literal. Measured candidate counts today: `hack-skills` 0,
   `apk-reverse-community` 5, `ctf-super-hub` 20, `ai-fullstack-delivery` 29 — the
   last one via the `fullstack`/`delivery` alias fold rather than via the identifier as
   such. `community-raw`, `skills-hub` and `upstream` are 0 because they are also
   stopwords on the hint side. This one is unchanged and still open; the one
   over-trigger surface it used to share with `ai` is gone, because `ai` is no longer a
   token.
3. **`alias_delivery` still reaches 29 records, and that is a named failure.** The
   stopword strip stopped `workflow`; `delivery`, `pipeline`, `devops` and `交付` are
   genuine alias variants and still fold to it. The decoy corpus measures this rather
   than assuming it: `alias-delivery-word`, `alias-pipeline-word`,
   `alias-devops-word` and `alias-delivery-cjk` are four of the nine open over-triggers.
   Measured today: all four hints return 29 candidates and the byte-identical top-three
   reference list, led by the RAG pipeline record, which is not what any of the four
   words means.
4. **Governance vocabulary still routes, in three of its five words.** Of the five
   importer adjectives, `capability` and `adapted` are now closed — both are in the
   engine's `STOPWORDS` constant, `tokens()` returns the empty set for each, and
   `lookup` returns `missing_input` with 0 candidates, down from 30 at `matched`. The
   stopword route was chosen deliberately over a `noise[]` entry: each word is carried
   by 30 of 154 records of one source, i.e. 19%, which is below the per-source ≥ 80 %
   admission rule, so the words are rejected as *capability vocabulary* rather than
   measured as *vendor boilerplate*. Three over-triggers remain. Measured today:
   `融合` 42 candidates at `matched` confidence 1.0, and `governance` and `wrapper` reach
   only 1 candidate each — but that candidate is the top result, which is what the
   decoy cases `governance-fusion-cjk`, `governance-word-governance` and
   `governance-word-wrapper` assert against. `融合` is a sense error, not just a
   frequency one: its top result is `workflows/backend-engineer/skills/api-implementation/SKILL.md`.
5. **`_score()` is not noise-stripped.** Harmless for the six literals that ship
   today, for the reason given in section 4. It is a trap for the seventh.
6. **`exclude` is unused.** No signal needed one that could be justified with
   evidence. The field is validated and compiled, but a schema-supported feature with
   no user is not a working feature.
7. **Signals cover two of four sources.** All 28 target `hack-skills` or
   `ctf-super-hub`. `ai-fullstack-delivery` (154 records) and
   `apk-reverse-community` (1 record) have none, so their recall still depends on token
   overlap alone.
 8. **The `s3 bucket` survivor is real, named, and is no longer an over-narrowing
   case.** An earlier draft called this "the single over-narrowing case in the decoy
   corpus". The underlying fact is unchanged and still true, so it is kept in full:
   `tokens("s3 bucket")` is exactly `{'bucket', 's3'}`; `s3` is admitted by
   `short_tokens` and works; `bucket` appears in **0** of 293 routing views and 0 of 293
   candidacy views, so no candidate can exist and no signal may be invented for it,
   because the evidence rule would reject one. No record in the 293-skill corpus owns S3
   or object storage. It is 1 of the 38 named probes still at zero references; the other
   37 resolve. What changed is the classification. The case was a *positive*
   (`recall-s3-bucket`) whose `expect_source_path` nothing in the corpus can evidence —
   the record it named, `community-hack-skills-127`, holds only `SKILL.md` and
   `PORT_SERVICE_MATRIX.md`, and a case-insensitive search for
   `s3|bucket|aws|object storage` across both returns zero matches. A positive whose
   expectation nothing can evidence is not a gate, it is a red line a reader learns to
   ignore. It is now the decoy `absence-s3-bucket`, asserting the correct state — the
   hint must reach nothing, must not be answered by `hack-skills` at all, and must not be
   answered by the record the withdrawn positive expected — and it **passes**. A curator
   who adds an unjustified `bucket` signal or a `bucket→…` alias turns it red
   immediately. Measured today with the probe battery shape of `p0-measure.py`.
 9. **No net improvement is claimed.** The corpus exists and its rates are measured
   (section 8), and two limitations moved from open to closed during T26 — the `ai`
   over-trigger and the `capability` / `adapted` governance over-triggers. That is not a
   net improvement, it is two named defects that are now named accurately instead of
   being invisible. **Nine** over-triggers are still open, every one a real wrong answer
   rather than a missing one, and a whole class of hint — the three source identifiers,
   and seven of the eight admitted short tokens — is still unprobed. The recall numbers
   in this document are therefore stated as recall numbers, not as a verdict, and the
   precision side is the one that is still red.
 10. **19 of 293 records do not match their own slug.** 16 are the
     `.../skills/SKILL.md` harness artifact described in section 3; the remaining three
     are `community-ctf-super-hub-011` (`ctf-super-hub`, which its own noise entry
     removes), `community-ctf-super-hub-031` (`strix-sql-injection`) and
     `community-ai-fullstack-delivery-175` (`ab-testing`). Measured today through
     `lookup()` and cross-checked against `p0-measure.py`, which reports the same
     274/293. Section 3 previously reported 16 misses and full 293/293 reachability;
     both were wrong and are corrected there.

## Reproducing the numbers in this document

Every figure above comes either from a measurement I ran against the shipped files on
2026-09-30 or from `D:\Project\skills-hub\work\p0\DESIGN-FREEZE.md`, and this document
labels which is which. The measurements import the real engine:

```text
$env:PYTHONIOENCODING='utf-8'
python -c "import importlib.util,pathlib; s=importlib.util.spec_from_file_location('cr','skills/scripts/community-route.py'); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); m.load_contract(); print(sorted(m.tokens('workflow')))"
```

The corpus counts, the two rates and the named over-triggers in section 8 are the
literal output of:

```text
python skills/scripts/test-community-decoys.py --report
```

The recomputability sweep in section 2 (260 reported references, 0 violations, 8
distinct signals) is `p0-measure.py`'s 38 named probes crossed with all five source
filters — `None` plus the four community sources — recomputing
`4*len(signal_hits) + 3*len(name_hits) + 1*len(description_hits)` against each reported
`rank_score`.

The coordinator's battery, which writes its report outside this repository:

```text
python D:\Project\skills-hub\work\p0\p0-measure.py
python D:\Project\skills-hub\work\p0\p0-proof-deadwidening.py
python D:\Project\skills-hub\work\p0\p0-acceptance.py
```

`p0-acceptance.py` is worth singling out because it deliberately does not import the
engine's own verifier or the decoy runner: it recomputes the corpus, the signal counts
and the short-token exclusion from the registry and the signals file through the public
`lookup()` interface, so a mistake in an implementer's own gate cannot certify itself.
It independently reproduces 30 decoys / 27 positives, 21/30, 27/27 and 48/57, and it
pins the `ai` exclusion. Where this document and that harness disagree, the harness and
`lookup()` are right.

One caution for anyone re-running `p0-proof-deadwidening.py`: its section A still
compares `_name_view` against `tokens(_reference_text)`, which is the **pre-D1**
name-only comparison, and it therefore reports a different pair of numbers from the
symmetric `routing_view` measurement in section 3 of this document. The script is a
historical proof of the original defect and is kept for that reason; it is not the
measurement behind the section-3 table.

The gates that must hold for anything in this document to stay true:

```text
python skills/scripts/verify-routing-signals.py
python skills/scripts/test-route-ranking.py
python skills/scripts/test-community-route.py
python skills/scripts/test-community-decoys.py
```

See also: `ROUTING-SIGNAL-DEFECTS.md` (the measured defect register) and
`DESCRIPTION-PARSING.md` (where `legacy_description` comes from).
