"""Positive and negative tests for ``parse-skill-frontmatter``.

Run::

    python skills/scripts/test-frontmatter-parsing.py

Exit code ``0`` when every case passes, ``1`` otherwise.  Standard library only.

Coverage map (the 12 shapes the hub must survive):

===  =========================================================
 1   ``description: plain text``
 2   ``description: "double quoted"``
 3   ``description: 'single quoted'``
 4   ``description: >-``            (folded, strip)
 5   ``description: >``             (folded, keep trailing newline)
 6   ``description: |``             (literal, keep trailing newline)
 7   ``description: |-``            (literal, strip)
 8   ``description: >-2``           (folded, explicit indent)
 9   UTF-8 BOM at the start of the file
10   no frontmatter at all
11   ``\\r\\n`` line endings
12   content containing ``:`` ``#`` quotes, CJK, and a wrapped line
===  =========================================================

Plus the invariant that matters for the registry: a folded scalar and a literal
scalar of the same text must produce **different** values, and no parsed
description may ever be a bare block-scalar indicator.
"""

from __future__ import annotations

import importlib
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
fm = importlib.import_module("parse-skill-frontmatter")

FAILURES = []
CHECKS = 0
NEGATIVE_CHECKS = 0

def check(label, actual, expected):
    global CHECKS
    CHECKS += 1
    if actual != expected:
        FAILURES.append("{}: expected {!r}, got {!r}".format(label, expected, actual))
        print("FAIL  {}: expected {!r}, got {!r}".format(label, expected, actual))
    else:
        print("ok{}   {}".format("   " if label.startswith("  ") else "", label))

def negative(label, actual, forbidden):
    """Assert that *actual* is not one of the values that must never occur."""
    global CHECKS, NEGATIVE_CHECKS
    CHECKS += 1
    NEGATIVE_CHECKS += 1
    values = forbidden if isinstance(forbidden, (list, tuple, set)) else [forbidden]
    if any(actual == bad for bad in values) or (
        isinstance(actual, str) and actual.strip() in values
    ):
        FAILURES.append("{}: produced forbidden value {!r}".format(label, actual))
        print("FAIL  {}: produced forbidden value {!r}".format(label, actual))
    else:
        print("ok    {} (negative guard)".format(label))

def write_temp(content, suffix=".md", newline="\n", bom=False):
    handle = tempfile.NamedTemporaryFile("wb", suffix=suffix, delete=False)
    data = content.encode("utf-8")
    if bom:
        data = b"\xef\xbb\xbf" + data
    if newline == "\r\n":
        data = data.replace(b"\n", b"\r\n")
    handle.write(data)
    handle.close()
    return handle.name

def doc(frontmatter_body, body="# Title\n"):
    return "---\n" + frontmatter_body + "---\n\n" + body

# --------------------------------------------------------------------------- 1
def test_plain_single_line():
    text = doc("name: demo\ndescription: Plain single line description.\n")
    check("1  plain single line", fm.parse_frontmatter(text)["description"],
          "Plain single line description.")
    check("1  plain -> registry line", fm.description_of(text),
          "Plain single line description.")
    negative("1  plain is not an indicator", fm.description_of(text), ">-")

# --------------------------------------------------------------------------- 2
def test_double_quoted():
    text = doc('name: demo\ndescription: "Double quoted description."\n')
    check("2  double quoted is unquoted", fm.description_of(text),
          "Double quoted description.")
    text = doc('description: "escaped \\"quote\\" and \\u4e2d\\u6587"\n')
    check("2  double quoted escapes", fm.description_of(text),
          'escaped "quote" and 中文')
    text = doc('description: "value: with colon # and hash"\n')
    check("2  double quoted keeps : and #", fm.description_of(text),
          "value: with colon # and hash")

# --------------------------------------------------------------------------- 3
def test_single_quoted():
    text = doc("description: 'Single quoted description.'\n")
    check("3  single quoted is unquoted", fm.description_of(text),
          "Single quoted description.")
    text = doc("description: 'it''s escaped' # trailing comment\n")
    check("3  single quoted '' escape", fm.description_of(text), "it's escaped")
    text = doc("description: 'keeps: colon and # hash'\n")
    check("3  single quoted keeps : and #", fm.description_of(text),
          "keeps: colon and # hash")

# --------------------------------------------------------------------------- 4
def test_folded_strip():
    text = doc("description: >-\n  Kerberos attack playbook for AD.\n  Use when targeting AD auth.\n")
    value = fm.parse_frontmatter(text)["description"]
    check("4  folded >- joins with a space", value,
          "Kerberos attack playbook for AD. Use when targeting AD auth.")
    check("4  folded >- has no trailing newline", value.endswith("\n"), False)
    negative("4  folded >- is not the indicator", fm.description_of(text), ">-")
    negative("4  folded >- is not '>'", fm.description_of(text), ">")

# --------------------------------------------------------------------------- 5
def test_folded_keep():
    text = doc("description: >\n  Folded but keeps the final newline.\n")
    value = fm.parse_frontmatter(text)["description"]
    check("5  folded > keeps one trailing newline", value,
          "Folded but keeps the final newline.\n")
    check("5  folded > registry line drops it", fm.description_of(text),
          "Folded but keeps the final newline.")
    negative("5  folded > is not the indicator", fm.description_of(text), ">")

# --------------------------------------------------------------------------- 6
def test_literal_keep():
    text = doc("description: |\n  First literal line.\n  Second literal line.\n")
    value = fm.parse_frontmatter(text)["description"]
    check("6  literal | preserves newlines", value,
          "First literal line.\nSecond literal line.\n")
    negative("6  literal | is not the indicator", fm.description_of(text), "|")

# --------------------------------------------------------------------------- 7
def test_literal_strip():
    text = doc("description: |-\n  First literal line.\n  Second literal line.\n")
    value = fm.parse_frontmatter(text)["description"]
    check("7  literal |- strips trailing newline", value,
          "First literal line.\nSecond literal line.")
    negative("7  literal |- is not the indicator", fm.description_of(text), "|-")

# ------------------------------------------------------- folded vs literal core
def test_folded_vs_literal_differ():
    body = "  alpha beta\n  gamma delta\n"
    folded = fm.parse_frontmatter(doc("description: >-\n" + body))["description"]
    literal = fm.parse_frontmatter(doc("description: |-\n" + body))["description"]
    check("8  folded vs literal differ", folded != literal, True)
    check("8  folded joins lines", folded, "alpha beta gamma delta")
    check("8  literal keeps lines", literal, "alpha beta\ngamma delta")
    check("8  folded has no newline", "\n" in folded, False)
    check("8  literal has a newline", "\n" in literal, True)

# --------------------------------------------------------------------------- 8
def test_folded_explicit_indent():
    text = doc("description: >-2\n  explicit indent keeps a space join.\n  Second line.\n")
    check("8  folded >-2 explicit indent", fm.parse_frontmatter(text)["description"],
          "explicit indent keeps a space join. Second line.")
    text = doc("description: >-2\n    four space body\n    second body\n")
    # An explicit indentation indicator disables auto-detection: the body is
    # indented by exactly 2, so the extra 2 spaces make these "more indented"
    # lines and their line breaks are NOT folded.
    check("8  folded >-2 four space body stays more-indented",
          fm.parse_frontmatter(text)["description"],
          "  four space body\n  second body")

# --------------------------------------------------------------------------- 9
def test_bom():
    path = write_temp(doc("name: demo\ndescription: BOM prefixed description.\n"), bom=True)
    try:
        data = fm.parse_file(path)
        check("9  BOM file name", data.get("name"), "demo")
        check("9  BOM file description", fm.normalize_description(data.get("description")),
              "BOM prefixed description.")
    finally:
        Path(path).unlink()
    text = "\ufeff" + doc("name: demo\ndescription: BOM inline.\n")
    check("9  BOM in a string is stripped", fm.description_of(text), "BOM inline.")

# -------------------------------------------------------------------------- 10
def test_no_frontmatter():
    text = "# Just a heading\n\nNo frontmatter here at all.\n"
    check("10 no frontmatter -> empty mapping", fm.parse_frontmatter(text), {})
    check("10 no frontmatter -> empty description", fm.description_of(text), "")
    negative("10 no frontmatter yields no indicator", fm.description_of(text), ">-")
    text = "---\nname: demo\ndescription: never closed\n\n# body\n"
    check("10 unterminated frontmatter -> empty mapping", fm.parse_frontmatter(text), {})

# -------------------------------------------------------------------------- 11
def test_crlf():
    path = write_temp(
        doc("name: demo\ndescription: >-\n  Windows origin description.\n  Second line.\n"),
        newline="\r\n",
    )
    try:
        check("11 CRLF folded description", fm.description_of(fm.read_document(path)),
              "Windows origin description. Second line.")
    finally:
        Path(path).unlink()
    text = "---\r\ndescription: |\r\n  one\r\n  two\r\n---\r\n\r\nbody\r\n"
    check("11 CRLF literal keeps one newline per line",
          fm.parse_frontmatter(text)["description"], "one\ntwo\n")

# -------------------------------------------------------------------------- 12
def test_rich_content():
    text = doc(
        "description: >-\n"
        "  用于中文用户: when a description contains 冒号, 引号 \"q\", '#hash',\n"
        "  and is wrapped across several source lines.\n"
    )
    value = fm.description_of(text)
    check("12 CJK + : + # + quotes + wrap", value,
          '用于中文用户: when a description contains 冒号, 引号 "q", \'#hash\', '
          'and is wrapped across several source lines.')
    negative("12 rich content is not an indicator", value, [">-", ">", "|", "|-"])
    text = doc("description: \"\"\"not supported triple quote\"\"\"\n")
    negative("12 unsupported triple quote is not silently an indicator",
             fm.description_of(text), ">-")

# ------------------------------------------------------- negative / degenerate
def test_negative_cases():
    text = doc("name: demo\ndescription: >-\n")
    check("N  folded with no body -> empty", fm.parse_frontmatter(text)["description"], "")
    text = doc("name: demo\ndescription: >x\n  not an indicator\n")
    check("N  invalid indicator >x is plain text", fm.description_of(text), ">x")
    text = doc("name: demo\ndescription: abc#def\n")
    check("N  '#' without leading space is kept", fm.description_of(text), "abc#def")
    text = doc("name: demo\ndescription: text # a comment\n")
    check("N  '#' after a space is a comment", fm.description_of(text), "text")
    text = "---\ndescription: >-\n  body\n...\n"
    check("N  '...' also closes frontmatter", fm.description_of(text), "body")
    text = doc("metadata:\n  nested: 'x'\ndescription: after a nested block\n")
    check("N  nested keys do not break the top level", fm.description_of(text),
          "after a nested block")
    text = doc("allowed-tools:\n  - Read\n  - Write\ndescription: after a sequence\n")
    check("N  sequence items do not break the top level", fm.description_of(text),
          "after a sequence")
    text = doc("description: >-\n  para one line one\n\n  para two line one\n  para two line two\n")
    check("N  folded blank line keeps a paragraph break",
          fm.parse_frontmatter(text)["description"],
          "para one line one\npara two line one para two line two")
    text = doc("description: >-\n  plain line\n    more indented stays\n  back to plain\n")
    check("N  folded more-indented lines keep newlines",
          fm.parse_frontmatter(text)["description"],
          "plain line\n  more indented stays\nback to plain")
    for header in (">-", ">", "|", "|-", "|+"):
        text = doc("description: {}\n".format(header))
        negative("N  bare indicator {} never survives".format(header),
                 fm.description_of(text), [">", ">-", ">", "|", "|-", "|+"])

# --------------------------------------------------- live registry invariants
def test_registry_invariants():
    registry_path = ROOT / "skills" / "community" / "registry.json"
    if not registry_path.is_file():
        FAILURES.append("registry missing: {}".format(registry_path))
        return
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    records = registry.get("skills") or []
    check("R  registry record count", len(records), 293)
    indicators = {">", ">-", ">+", "|", "|-", "|+", ">-2"}
    empty = []
    bad = []
    mismatched = []
    for record in records:
        value = (record.get("extensions") or {}).get("legacy_description") or ""
        if not value.strip():
            empty.append(record["id"])
        if value.strip() in indicators or value[:1] in ">|":
            bad.append((record["id"], value))
        source = ROOT / record["path"]
        if source.is_file():
            if fm.description_of(fm.read_document(source)) != value:
                mismatched.append(record["id"])
    check("R  no empty legacy_description", empty, [])
    check("R  no block-scalar indicator in legacy_description", bad, [])
    check("R  every legacy_description matches its source file", mismatched, [])

    # The known-bad source must really parse to prose, not to its indicator.
    sample = ROOT / "community-raw" / "hack-skills" / "active-directory-kerberos-attacks" / "SKILL.md"
    if sample.is_file():
        value = fm.description_of(fm.read_document(sample))
        check("R  known >- sample parses to prose", value.startswith("Kerberos attack playbook"), True)
        negative("R  known >- sample is not the indicator", value, ">-")

def main():
    for test in (
        test_plain_single_line,
        test_double_quoted,
        test_single_quoted,
        test_folded_strip,
        test_folded_keep,
        test_literal_keep,
        test_literal_strip,
        test_folded_vs_literal_differ,
        test_folded_explicit_indent,
        test_bom,
        test_no_frontmatter,
        test_crlf,
        test_rich_content,
        test_negative_cases,
        test_registry_invariants,
    ):
        print("-- {}".format(test.__name__))
        test()
    print()
    print("checks: {} ({} of them negative guards)".format(CHECKS, NEGATIVE_CHECKS))
    if FAILURES:
        print("FRONTMATTER PARSING FAILED: {} failing check(s)".format(len(FAILURES)))
        for failure in FAILURES:
            print("  - {}".format(failure))
        return 1
    print("FRONTMATTER PARSING PASSED")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
