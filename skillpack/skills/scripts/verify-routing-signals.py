#!/usr/bin/env python3
"""T26 gate for the curated community routing signal layer.

Verifies ``skills/community/routing-signals.json`` against
``schemas/community-routing-signals.json`` and against the real registry.
Standard library only; it must import nothing from this repository except the
two JSON documents it reads, so it stays a standalone gate.

Why this is fail-closed
-----------------------
The curated layer is the only place in the repository where a human writes a
keyword that a router will trust. Every failure mode that matters is an error
(exit 20), never a warning:

* a schema violation, or a schema keyword outside the bundled validator subset;
* a ``signals[].id`` that is not a registry record id;
* a duplicate ``signals[].id`` (two rules for one record would make the
  ranking weight uncheckable against the recomputed ``rank_score``);
* a regex that ``re.compile`` rejects, in ``must``, ``exclude`` or
  ``noise[].pattern``;
* an empty or too-short ``note`` (a signal nobody can review is a signal
  nobody can delete when it over-triggers);
* an ``evidence`` string that design-freeze 1.2 cannot find;
* a ``noise[].pattern`` that does not match >= 80% of the records of at least
  one source (design-freeze 1.3): a word that appears in half the corpus is
  not boilerplate, it is noise the author liked;
* ``short_tokens`` missing a literal of the measured 2-character blind spot, or
  carrying an extra literal outside it. The extra direction is blocking on
  purpose: every admitted literal widens candidacy, the one that was measured
  harmful (``ai``, a weight-3 name hit in 157/293 routing texts) had to be
  removed on evidence, and exit 10 is the NON-BLOCKING code in this repository,
  so admitting a new literal means editing the measured set deliberately, not
  slipping it past a warning;
* a coverage floor: fewer ``signals[]`` or ``token_aliases`` entries than the
  task card requires, which would let the layer silently degrade to the token
  overlap it exists to improve;
* ``meta.registrySchemaVersion`` disagreeing with the registry's own
  ``schemaVersion``;
* ``meta.owner`` other than ``T26``.

Exit codes follow spec section 4.7: 0 ok, 10 needs_review, 20 invalid.

``--check`` is strictly read-only. This script never writes, never renames and
never deletes anything; the flag exists so a caller can state that intent
explicitly, and the read-only guarantee is asserted by the test that checks the
script's own source for write calls.

Usage:
    python skills/scripts/verify-routing-signals.py [--check] [--json]
                                                     [--signals PATH]
                                                     [--schema PATH]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SIGNALS = ROOT / "skills/community/routing-signals.json"
DEFAULT_SCHEMA = ROOT / "schemas/community-routing-signals.json"
REGISTRY = ROOT / "skills/community/registry.json"

# Frozen owner identity (design-freeze 1).
EXPECTED_OWNER = "T26"

# The measured 2-character tokeniser blind spot (design-freeze D4), minus the one
# literal the post-ship measurement showed to be an OVER-TRIGGER rather than a
# recall fix.
#
# This floor started at nine literals: ad, ai, ci, db, id, io, os, ot, s3. "ai" was
# measured harmful and removed, which makes this a MEASURED CORRECTION and not a
# relaxation of the gate:
#
#   * the routing view hyphen-splits the source identifier "ai-fullstack", so the
#     token "ai" was present in 157 of the 293 records' routing texts;
#   * that gave every one of those 157 records a NAME-level (weight 3) hit for any
#     hint containing "ai";
#   * lookup("ai") therefore returned 3 wrappers at confidence=1.0 and was held
#     back only by the ambiguity rule (review_reason == ["ambiguous_tie"]), so the
#     tie-breaker was the sole thing preventing a wrong routing answer.
#
# design-freeze 1.1 only permits dropping a short token that can be DEMONSTRATED
# harmful, and that is what the 157/293 figure demonstrates. The remaining eight
# are kept on their own measured footing, including os, ot and s3, which occur in
# 0/293 routing texts: a literal that matches nothing is useless but harmless,
# whereas a literal that matches 157 records is harmful. Do not "restore" "ai"
# here without a new measurement that shows it no longer over-triggers.
REQUIRED_SHORT_TOKENS = ("ad", "ci", "db", "id", "io", "os", "ot", "s3")

# Coverage floors from the T26 task card, checked by this gate because the
# frozen schema deliberately stays a shape contract and not a coverage contract.
MIN_NOISE = 4
MIN_ALIASES = 6
MIN_SIGNALS = 20

# design-freeze 1.3: boilerplate must dominate one whole source.
NOISE_PER_SOURCE_FLOOR = 0.80

# Files that are binary or clearly not text are skipped when hunting for
# evidence_kind "raw" evidence. A vendored body is markdown/config text; a
# stray .png must not count as evidence.
BINARY_SUFFIXES = frozenset({
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp", ".pdf", ".zip",
    ".gz", ".bz2", ".xz", ".7z", ".tar", ".exe", ".dll", ".so", ".dylib", ".bin",
    ".jar", ".class", ".pyc", ".pyo", ".o", ".obj", ".mp3", ".mp4", ".avi",
    ".mov", ".wav", ".ttf", ".otf", ".woff", ".woff2", ".sqlite", ".db",
})

# The same tokeniser the routing engine uses. Hyphen-inclusive, so a compound
# such as ``BloodHound-guided`` is ONE token: that is defect D2, and it is why
# a hyphenated frontmatter mention does not count as routability here.
TOKEN_RE = re.compile(r"[a-z][a-z0-9-]{2,}")

# The validator subset, mirrored from skills/scripts/test-contract-v2.py so a
# schema can never quietly use a keyword this gate cannot enforce.
SUPPORTED_KEYWORDS = frozenset({
    "type", "required", "properties", "additionalProperties", "items", "enum",
    "const", "oneOf", "minLength", "maxLength", "minimum", "maximum", "pattern",
    "minItems", "maxItems", "maxProperties",
})
ANNOTATION_KEYWORDS = frozenset({"$schema", "$id", "title", "description"})
TYPE_CHECKS = {
    "object": lambda value: isinstance(value, dict),
    "array": lambda value: isinstance(value, list),
    "string": lambda value: isinstance(value, str),
    "integer": lambda value: isinstance(value, int) and not isinstance(value, bool),
    "number": lambda value: isinstance(value, (int, float)) and not isinstance(value, bool),
    "boolean": lambda value: isinstance(value, bool),
    "null": lambda value: value is None,
}

class UnsupportedKeyword(Exception):
    """Raised instead of ignoring a schema keyword that cannot be enforced."""

# --------------------------------------------------------------------------
# dependency-free draft 2020-12 subset validator
# --------------------------------------------------------------------------

def _check_keywords(schema: dict, path: str) -> None:
    for keyword in schema:
        if keyword in SUPPORTED_KEYWORDS or keyword in ANNOTATION_KEYWORDS:
            continue
        raise UnsupportedKeyword(f"{path}: unsupported schema keyword {keyword!r}")

def _validate(instance: object, schema: dict, path: str, errors: list[str]) -> None:
    if not isinstance(schema, dict):
        raise UnsupportedKeyword(f"{path}: schema node is not an object")
    _check_keywords(schema, path)

    if "const" in schema and instance != schema["const"]:
        errors.append(f"{path}: expected const {schema['const']!r}, got {instance!r}")
    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: {instance!r} not in enum {schema['enum']}")

    if "oneOf" in schema:
        matched = 0
        for branch in schema["oneOf"]:
            branch_errors: list[str] = []
            _validate(instance, branch, path, branch_errors)
            if not branch_errors:
                matched += 1
        if matched != 1:
            errors.append(f"{path}: oneOf matched {matched} branches, expected exactly 1")

    if "type" in schema:
        expected = schema["type"]
        expected_list = expected if isinstance(expected, list) else [expected]
        for name in expected_list:
            if name not in TYPE_CHECKS:
                raise UnsupportedKeyword(f"{path}: unsupported type {name!r}")
        if not any(TYPE_CHECKS[name](instance) for name in expected_list):
            errors.append(f"{path}: expected type {expected!r}, got {type(instance).__name__}")
            return

    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            errors.append(f"{path}: shorter than minLength {schema['minLength']}")
        if "maxLength" in schema and len(instance) > schema["maxLength"]:
            errors.append(f"{path}: longer than maxLength {schema['maxLength']}")
        if "pattern" in schema and not re.search(schema["pattern"], instance):
            errors.append(f"{path}: {instance[:60]!r} does not match pattern {schema['pattern']}")

    if isinstance(instance, bool):
        return

    if isinstance(instance, (int, float)):
        if "minimum" in schema and instance < schema["minimum"]:
            errors.append(f"{path}: below minimum {schema['minimum']}")
        if "maximum" in schema and instance > schema["maximum"]:
            errors.append(f"{path}: above maximum {schema['maximum']}")

    if isinstance(instance, dict):
        for key in schema.get("required", []):
            if key not in instance:
                errors.append(f"{path}: missing required property {key!r}")
        properties = schema.get("properties", {})
        for key, value in instance.items():
            if key in properties:
                _validate(value, properties[key], f"{path}/{key}", errors)
                continue
            extra = schema.get("additionalProperties", True)
            if extra is False:
                errors.append(f"{path}: additional property {key!r} is not allowed")
            elif isinstance(extra, dict):
                _validate(value, extra, f"{path}/{key}", errors)
        if "maxProperties" in schema and len(instance) > schema["maxProperties"]:
            errors.append(f"{path}: more than maxProperties {schema['maxProperties']}")

    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            errors.append(f"{path}: fewer than minItems {schema['minItems']}")
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            errors.append(f"{path}: more than maxItems {schema['maxItems']}")
        if "items" in schema:
            for index, value in enumerate(instance):
                _validate(value, schema["items"], f"{path}/{index}", errors)

def validate(instance: object, schema: dict) -> list[str]:
    errors: list[str] = []
    _validate(instance, schema, "$", errors)
    return errors

def audit_schema_keywords(node: object, path: str) -> None:
    """Walk a whole schema document and reject any keyword outside the subset."""
    if isinstance(node, dict):
        if any(key in node for key in ("type", "properties", "required", "enum", "items", "oneOf")):
            _check_keywords(node, path)
        for key, value in node.items():
            if key in ANNOTATION_KEYWORDS:
                continue
            audit_schema_keywords(value, f"{path}/{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            audit_schema_keywords(value, f"{path}/{index}")

# --------------------------------------------------------------------------
# registry-derived routing text
# --------------------------------------------------------------------------

def legacy(record: dict, key: str, default: object = "") -> object:
    return (record.get("extensions") or {}).get(key, default)

def reference_text(record: dict) -> str:
    """The engine's reference text: name + description + path + source_path + keywords.

    This is the exact text ``community-route._reference_text`` builds, and it is
    also the text a ``noise`` entry with ``scope: any`` is applied to. Measuring
    the noise rule against any other text would measure a different document
    than the one the engine routes on.
    """
    return " ".join(str(value) for value in (
        legacy(record, "legacy_original_name"),
        legacy(record, "legacy_description"),
        record.get("path", ""),
        record.get("source_path", ""),
    )) + " " + " ".join(str(value) for value in record.get("keywords", []))

def description_text(record: dict) -> str:
    """The engine's description text: legacy_description + keywords."""
    return str(legacy(record, "legacy_description")) + " " + \
        " ".join(str(value) for value in record.get("keywords", []))

def noise_text(record: dict, scope: str) -> str:
    return reference_text(record) if scope == "any" else description_text(record)

def record_evidence_text(record: dict) -> str:
    """The design-freeze 1.2 ``record`` haystack: name + description + source_path."""
    return " ".join(str(value) for value in (
        legacy(record, "legacy_original_name"),
        legacy(record, "legacy_description"),
        record.get("source_path", ""),
    ))

def record_directory(record: dict) -> Path:
    return ROOT / Path(record.get("path", "")).parent

def is_text_file(path: Path) -> bool:
    if path.suffix.lower() in BINARY_SUFFIXES:
        return False
    try:
        path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    return True

def directory_corpus(record: dict) -> str:
    """All text content inside the record's own directory, case-folded."""
    directory = record_directory(record)
    if not directory.is_dir():
        return ""
    parts: list[str] = []
    for path in sorted(directory.rglob("*")):
        if not path.is_file() or not is_text_file(path):
            continue
        try:
            parts.append(path.read_text(encoding="utf-8", errors="ignore"))
        except OSError:
            continue
    return "\n".join(parts).casefold()

# --------------------------------------------------------------------------
# checks
# --------------------------------------------------------------------------

class Result:
    def __init__(self) -> None:
        self.blocked: list[str] = []
        self.review: list[str] = []
        self.metrics: dict[str, object] = {}
        self.coverage: list[str] = []

def check_schema(document: object, schema: dict, result: Result) -> None:
    try:
        audit_schema_keywords(schema, "$")
    except UnsupportedKeyword as error:
        result.blocked.append(f"schema: {error}")
        return
    errors = validate(document, schema)
    for error in errors:
        result.blocked.append(f"schema: {error}")
    result.metrics["schema_errors"] = len(errors)

def check_meta(document: dict, registry: dict, result: Result) -> None:
    meta = document.get("meta") or {}
    owner = meta.get("owner")
    if owner != EXPECTED_OWNER:
        result.blocked.append(
            f"meta.owner is {owner!r}, expected {EXPECTED_OWNER!r}: the curated layer "
            "may only be changed by its owner"
        )
    declared = meta.get("registrySchemaVersion")
    actual = registry.get("schemaVersion")
    if declared != actual:
        result.blocked.append(
            f"meta.registrySchemaVersion {declared!r} != registry.json schemaVersion "
            f"{actual!r}: the signals are pinned to a registry contract they do not match"
        )
    result.metrics["meta_owner"] = owner
    result.metrics["meta_registry_schema_version"] = declared

def compile_patterns(patterns, where: str, result: Result) -> list[re.Pattern[str]]:
    compiled: list[re.Pattern[str]] = []
    for index, pattern in enumerate(patterns):
        try:
            compiled.append(re.compile(pattern))
        except re.error as error:
            result.blocked.append(f"{where}[{index}]: regex {pattern!r} does not compile: {error}")
    return compiled

def check_short_tokens(document: dict, result: Result) -> None:
    short = list(document.get("short_tokens") or [])
    present = list(short)
    missing = [token for token in REQUIRED_SHORT_TOKENS if token not in present]
    if missing:
        result.blocked.append(
            f"short_tokens is missing the measured 2-character blind spot {missing}: "
            "these are the literals the tokeniser's >= 3 character minimum hides"
        )
    extra = [token for token in present if token not in REQUIRED_SHORT_TOKENS]
    if extra:
        result.blocked.append(
            f"short_tokens carries unmeasured extra literals {extra}: the admitted set is "
            "part of the frozen contract, not a suggestion, and a literal outside it has "
            "no measurement behind it -- every admitted literal widens candidacy, so an "
            "unmeasured one is the exact regression this gate exists to stop. This is an "
            "error, not a warning, because exit 10 is the non-blocking code in this "
            "repository (verify-community-banner.py has carried it as a registered "
            "baseline), so a review warning here would let a re-admitted short literal "
            "through. Admitting a genuinely measured literal means editing "
            "REQUIRED_SHORT_TOKENS deliberately, with its measurement recorded in the "
            "comment above it, as part of a contract change -- not smuggling the literal "
            "in through a review warning."
        )
    result.metrics["short_tokens"] = len(present)
    result.metrics["short_tokens_missing"] = missing
    result.coverage.append(
        f"short_tokens: {len(present)} literal(s); measured blind spot required = "
        f"{len(REQUIRED_SHORT_TOKENS)}, present = {len(REQUIRED_SHORT_TOKENS) - len(missing)}"
    )

def check_token_aliases(document: dict, records: list[dict], result: Result) -> None:
    aliases = dict(document.get("token_aliases") or {})
    if len(aliases) < MIN_ALIASES:
        result.blocked.append(
            f"token_aliases holds {len(aliases)} pair(s), floor is {MIN_ALIASES}: "
            "D3 measured pcaps/yaras as unroutable plurals"
        )
    for plural in ("pcaps", "yaras"):
        if plural not in aliases:
            result.blocked.append(
                f"token_aliases is missing the frozen pair {plural!r}: the D3 probes "
                "are the reason this table exists"
            )
    for plural, singular in aliases.items():
        if plural == singular:
            result.blocked.append(f"token_aliases[{plural!r}] is a self-mapping and does nothing")
    # Print the corpus frequency of both sides so the table is auditable data,
    # not an assertion: a fold whose singular appears nowhere cannot route.
    document_frequency = Counter()
    for record in records:
        for token in set(TOKEN_RE.findall(reference_text(record).casefold())):
            document_frequency[token] += 1
    for plural, singular in sorted(aliases.items()):
        result.coverage.append(
            f"alias {plural} -> {singular}: records carrying the plural = "
            f"{document_frequency.get(plural, 0)}/{len(records)}, carrying the singular = "
            f"{document_frequency.get(singular, 0)}/{len(records)}"
        )
    result.metrics["token_aliases"] = len(aliases)

def check_noise(document: dict, records: list[dict], result: Result) -> None:
    noise = list(document.get("noise") or [])
    if len(noise) < MIN_NOISE:
        result.blocked.append(
            f"noise holds {len(noise)} entry/entries, floor is {MIN_NOISE}"
        )
    per_source_total = Counter(record.get("source") for record in records)
    for index, entry in enumerate(noise):
        pattern = entry.get("pattern", "")
        scope = entry.get("scope", "any")
        note = str(entry.get("note", ""))
        if not note.strip() or len(note.strip()) < 20:
            result.blocked.append(
                f"noise[{index}]: note is empty or too short to justify the pattern"
            )
        if scope not in ("any", "description"):
            result.blocked.append(f"noise[{index}]: scope {scope!r} is not any|description")
            continue
        try:
            compiled = re.compile(pattern, re.IGNORECASE)
        except re.error as error:
            result.blocked.append(f"noise[{index}]: pattern {pattern!r} does not compile: {error}")
            continue
        matched = Counter()
        for record in records:
            if compiled.search(noise_text(record, scope)):
                matched[record.get("source")] += 1
        best_source, best_count = ("", 0)
        best_fraction = 0.0
        for source, total in per_source_total.items():
            fraction = matched.get(source, 0) / total if total else 0.0
            if fraction > best_fraction:
                best_source, best_count, best_fraction = source, matched.get(source, 0), fraction
        if best_fraction < NOISE_PER_SOURCE_FLOOR:
            result.blocked.append(
                f"noise[{index}]: {pattern!r} matches {best_count}/{per_source_total.get(best_source, 0)} "
                f"records of its best source {best_source!r} = {best_fraction:.0%}, below the "
                f"{NOISE_PER_SOURCE_FLOOR:.0%} per-source floor; a word in "
                f"{sum(matched.values())}/{len(records)} records is not source boilerplate"
            )
        result.coverage.append(
            f"noise {pattern!r} scope={scope}: "
            + " ".join(
                f"{source}={matched.get(source, 0)}/{per_source_total[source]}"
                for source in sorted(per_source_total)
            )
            + f" | best {best_source} {best_count}/{per_source_total.get(best_source, 0)} "
            f"= {best_fraction:.1%}"
        )
    result.metrics["noise"] = len(noise)

def check_signals(document: dict, records: list[dict], result: Result) -> None:
    signals = list(document.get("signals") or [])
    if len(signals) < MIN_SIGNALS:
        result.blocked.append(f"signals holds {len(signals)} entry/entries, floor is {MIN_SIGNALS}")
    by_id = {record["id"]: record for record in records}
    seen: set[str] = set()
    corpus_cache: dict[str, str] = {}
    by_kind = Counter()
    for index, signal in enumerate(signals):
        sid = signal.get("id")
        where = f"signals[{index}]"
        if sid in seen:
            result.blocked.append(
                f"{where}: duplicate id {sid!r}; one curated rule per record keeps the "
                "recomputed rank_score checkable"
            )
            continue
        seen.add(sid)
        record = by_id.get(sid)
        if record is None:
            result.blocked.append(
                f"{where}: id {sid!r} is not a skills[].id in registry.json; a curated "
                "signal may only point at a record that exists"
            )
            continue
        by_kind[signal.get("evidence_kind")] += 1

        must = list(signal.get("must") or [])
        if not must:
            result.blocked.append(f"{where} ({sid}): must is empty; a signal with no must can never fire")
        compile_patterns(must, f"{where} ({sid}).must", result)
        compile_patterns(list(signal.get("exclude") or []), f"{where} ({sid}).exclude", result)

        note = str(signal.get("note", ""))
        if not note.strip() or len(note.strip()) < 15:
            result.blocked.append(
                f"{where} ({sid}): note is empty or under 15 characters; a rule no reader "
                "can review is a rule nobody can remove when it over-triggers"
            )

        evidence = str(signal.get("evidence", ""))
        kind = signal.get("evidence_kind")
        needle = evidence.casefold()
        if not needle:
            result.blocked.append(f"{where} ({sid}): evidence is empty")
            continue
        if kind == "record":
            haystack = record_evidence_text(record).casefold()
            if needle not in haystack:
                result.blocked.append(
                    f"{where} ({sid}): evidence {evidence!r} is not a substring of the "
                    "record's legacy_original_name + legacy_description + source_path"
                )
        elif kind == "raw":
            if sid not in corpus_cache:
                corpus_cache[sid] = directory_corpus(record)
            if needle not in corpus_cache[sid]:
                result.blocked.append(
                    f"{where} ({sid}): evidence {evidence!r} does not occur in any text file "
                    f"inside the record's own directory ({record_directory(record).as_posix()}); "
                    "an unverifiable signal is an invented keyword"
                )
        else:
            result.blocked.append(f"{where} ({sid}): evidence_kind {kind!r} is not record|raw")
            continue
        result.coverage.append(
            f"signal {sid}: evidence_kind={kind} evidence={evidence!r} "
            f"must={len(must)} exclude={len(signal.get('exclude') or [])}"
        )
    result.metrics["signals"] = len(signals)
    result.metrics["signals_by_evidence_kind"] = dict(by_kind)
    result.metrics["signal_ids_unique"] = len(seen)

# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def verify(signals_path: Path = DEFAULT_SIGNALS, schema_path: Path = DEFAULT_SCHEMA) -> Result:
    result = Result()
    for path, label in ((signals_path, "routing-signals"), (schema_path, "schema"),
                        (REGISTRY, "registry")):
        if not path.is_file():
            result.blocked.append(f"{label} document missing: {path}")
            return result
    try:
        document = json.loads(signals_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        result.blocked.append(f"routing-signals is not valid JSON: {error}")
        return result
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        result.blocked.append(f"schema is not valid JSON: {error}")
        return result
    try:
        registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        result.blocked.append(f"registry is not valid JSON: {error}")
        return result
    records = list(registry.get("skills") or [])
    result.metrics["registry_records"] = len(records)

    check_schema(document, schema, result)
    check_meta(document, registry, result)
    check_short_tokens(document, result)
    check_token_aliases(document, records, result)
    check_noise(document, records, result)
    check_signals(document, records, result)
    return result

def report(result: Result, as_json: bool) -> None:
    if as_json:
        print(json.dumps({
            "exit_class": "invalid" if result.blocked else ("needs_review" if result.review else "ok"),
            "blocked": result.blocked,
            "needs_review": result.review,
            "metrics": result.metrics,
            "coverage": result.coverage,
        }, indent=2, ensure_ascii=False))
        return
    print("=== routing signals verification (T26) ===")
    for line in result.coverage:
        print(f"  {line}")
    for metric in ("registry_records", "noise", "token_aliases", "short_tokens", "signals",
                   "signal_ids_unique", "signals_by_evidence_kind", "schema_errors"):
        if metric in result.metrics:
            print(f"{metric}: {result.metrics[metric]}")
    for line in result.review:
        print(f"[NEEDS_REVIEW] {line}")
    for line in result.blocked:
        print(f"[BLOCKED] {line}")

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--check", action="store_true",
                        help="read-only verification mode (this script never writes)")
    parser.add_argument("--json", dest="as_json", action="store_true",
                        help="print a machine-readable report")
    parser.add_argument("--signals", default=str(DEFAULT_SIGNALS))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    args = parser.parse_args(argv)

    result = verify(Path(args.signals), Path(args.schema))
    report(result, args.as_json)
    if result.blocked:
        print(f"FAIL verify-routing-signals: {len(result.blocked)} blocking defect(s)")
        return 20
    if result.review:
        print(f"NEEDS_REVIEW verify-routing-signals: {len(result.review)} item(s)")
        return 10
    print("PASS verify-routing-signals")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
