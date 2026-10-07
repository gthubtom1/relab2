# Community skill description parsing

How `skills/community/registry.json` derives
`extensions.legacy_description` and `extensions.legacy_original_name` from the
upstream `SKILL.md` frontmatter, which YAML shapes are supported, what is
deliberately not supported, and how to recompute the fields.

## Why this document exists

The original importer read **one line** of frontmatter: it located the
`description:` key and took the rest of that line as the value. For a skill
whose frontmatter uses a YAML block scalar, that line holds the *indicator*,
not the text:

```yaml
description: >-
  Kerberos attack playbook for Active Directory. Use when targeting AD
  authentication via AS-REP roasting, Kerberoasting, golden/silver tickets.
```

The importer stored the literal two-character string `>-`. In this repository
**103 of 293** registry records carried `>-` as their description, which is why
`legacy_description` was useless for search and for anything that displayed it.

## Files

| File | Role |
| --- | --- |
| `skills/scripts/parse-skill-frontmatter.py` | The parser. Dependency-free (standard library only), importable, also runnable as a CLI for manual inspection. |
| `skills/scripts/fix-registry-descriptions.py` | Recomputes and rewrites the two `legacy_*` fields. `--check` is read-only, `--apply` writes. |
| `skills/scripts/test-frontmatter-parsing.py` | Positive and negative tests for every supported YAML shape, plus live registry invariants. |

## Recomputing

```text
python skills/scripts/fix-registry-descriptions.py --check    # read-only, exit 1 if out of sync
python skills/scripts/fix-registry-descriptions.py --apply    # rewrite in place
python skills/scripts/test-frontmatter-parsing.py             # must exit 0
```

`--check` prints how many records are already correct, how many need fixing,
which fields drift, and every value that still looks suspicious. `--apply`
refuses to write (exit 2) while any record has no usable description at all, so
a partial parse can never be committed as if it were complete.

Only `extensions.legacy_description` and `extensions.legacy_original_name` are
written. Every other key is re-serialised byte-for-byte identically, because
the file's existing format is exactly
`json.dumps(data, ensure_ascii=False, indent=2) + "\n"`.

`scripts/adapt-community.py` also writes the registry. It is a different
importer with a different blast radius (it rewrites 1111 paths) and must not be
used to fix descriptions.

## Supported YAML shapes

All of these are covered by `test-frontmatter-parsing.py`.

| # | Source | Stored description |
| --- | --- | --- |
| 1 | `description: Plain text.` | `Plain text.` |
| 2 | `description: "Quoted text."` | `Quoted text.` — quotes are YAML syntax, not content |
| 3 | `description: 'Quoted text.'` | `Quoted text.`; `''` is an escaped `'` |
| 4 | `description: >-` | folded, trailing newline stripped |
| 5 | `description: >` | folded, one trailing newline (clip) |
| 6 | `description: |` | literal, newlines preserved |
| 7 | `description: \|-` | literal, trailing newline stripped |
| 8 | `description: >-2` | folded with an explicit indentation indicator |
| 9 | file starts with a UTF-8 BOM | BOM dropped, frontmatter still found |
| 10 | no `---` frontmatter at all | empty mapping, description `""` — never an indicator |
| 11 | `\r\n` line endings | normalized to `\n` before parsing |
| 12 | content with `:`, `#`, quotes, CJK, and a wrapped line | preserved verbatim |

Beyond `description` the same parser is used for `name`, which becomes
`legacy_original_name`. Nested mappings and sequences are recognised well
enough to be skipped without corrupting the next top-level key.

## Folded vs literal: the distinction that matters

The two block styles are **not** interchangeable, and the parser keeps them
apart:

* **Folded (`>`)** — a line break between two equally-indented, non-blank lines
  becomes **one space**. A blank line keeps a **paragraph break**. A
  more-indented line keeps its own line breaks.
* **Literal (`|`)** — every line break is kept **verbatim**.

```yaml
description: >-
  alpha beta
  gamma delta
```
→ `alpha beta gamma delta` (one line, spaces)

```yaml
description: |-
  alpha beta
  gamma delta
```
→ `alpha beta\ngamma delta` (two lines)

Chomping indicators are honoured: `-` removes all trailing newlines, the default
clip keeps exactly one, `+` keeps them all. Because the registry stores
descriptions as index metadata, `fix-registry-descriptions.py` flattens the
result to a single line via `normalize_description()` before writing; the
parser itself returns the faithful YAML value, trailing newline and all.

## Known limitations

These are real gaps, not silent successes:

1. **Multi-line plain scalars are not supported.** A description written as
   `description: some very long text` continued on the next line is truncated at
   the end of the first line. No such file exists in the 293 registered skills,
   but an upstream file may one day use it.
2. **Quoted scalars that span lines are not supported.** `description: "text`
   continued on the next line is treated as unbalanced quoting and kept raw.
3. **Flow collections are not parsed.** `description: [a, b]` and
   `description: {a: b}` are returned as their raw text, which is already close
   to the source. No registered file uses them.
4. **Only top-level keys are extracted.** `metadata.description` is ignored on
   purpose.
5. **Tabs are not treated as indentation.** YAML forbids tabs in indentation;
   such a block is read as content.
6. **The first occurrence of a duplicated key wins**, as in YAML.
7. **Explicit indentation indicators are relative to column 0.** A top-level
   `>-2` with a four-space body makes those lines "more indented", so their line
   breaks are not folded and the two extra spaces are kept as content. That is
   YAML behaviour, and `test-frontmatter-parsing.py` pins it.

## What "suspicious" means in the tool output

`fix-registry-descriptions.py` flags, rather than silently accepts:

* `empty` — no description in the frontmatter, or an empty value;
* `block-scalar indicator` — the value is still `>`, `>-`, `|`, `|-`, …;
* `shorter than 20 chars`;
* `slug-like, not prose` — matches `^[A-Za-z0-9][A-Za-z0-9._/:\-]*$`, i.e. a
  bare name or path fragment rather than a sentence;
* `no alphanumeric characters`.

A record with a *hard* problem (empty description) also blocks `--apply`.
