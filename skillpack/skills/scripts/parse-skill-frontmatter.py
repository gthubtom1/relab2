"""Reusable YAML frontmatter parser for SKILL.md documents.

The hub imports upstream community skills whose ``SKILL.md`` frontmatter is
hand-written by many different authors, so the ``description`` field shows up in
every YAML shape a human realistically writes:

* ``description: plain text``
* ``description: "double quoted text"``
* ``description: 'single quoted text'``
* ``description: >-``  /  ``>``  /  ``>-2``  (folded block scalar)
* ``description: |-``  /  ``|``  /  ``|+``  (literal block scalar)

A parser that only reads the ``description:`` line stores the block-scalar
*indicator* (``>-``) instead of the description text.  This module implements
the YAML block-scalar semantics properly so the two styles stay distinguishable:

* folded (``>``)  -> line breaks between equally-indented, non-empty lines
  become a single space; a blank line keeps a paragraph break; more-indented
  lines keep their newlines.
* literal (``|``)  -> every line break is preserved verbatim.

Chomping indicators are honoured too: ``-`` strips all trailing newlines, the
default (clip) keeps exactly one, ``+`` keeps them all.

The module is dependency-free (standard library only) and importable::

    import importlib, pathlib, sys
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    fm = importlib.import_module("parse-skill-frontmatter")
    data = fm.parse_file("community-raw/example/SKILL.md")

Known limitations are listed in ``docs/community/DESCRIPTION-PARSING.md``.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

__all__ = [
    "BLOCK_INDICATORS",
    "description_of",
    "field_of",
    "is_block_indicator",
    "normalize_description",
    "parse_block_scalar",
    "parse_document",
    "parse_file",
    "parse_frontmatter",
    "parse_scalar",
    "read_document",
    "split_frontmatter",
]

#: Characters that can start a block scalar header.
BLOCK_INDICATORS = ">|"

_KEY_RE = re.compile(r"^(?P<key>[A-Za-z0-9_][A-Za-z0-9_.\-]*)[ \t]*:(?P<rest>.*)$")
_BLOCK_HEADER_RE = re.compile(
    r"^(?P<style>[|>])(?P<chomp>[-+]?)(?P<indent>[1-9]?)(?:[ \t]+#.*)?$"
)
_DOUBLE_ESCAPES = {
    "0": "\0",
    "a": "\a",
    "b": "\b",
    "t": "\t",
    "\t": "\t",
    "n": "\n",
    "v": "\v",
    "f": "\f",
    "r": "\r",
    "e": "\x1b",
    " ": " ",
    '"': '"',
    "/": "/",
    "\\": "\\",
    "N": "\x85",
    "_": "\xa0",
    "L": " ",
    "P": " ",
}

def read_document(path: Any) -> str:
    """Read *path* as text with a UTF-8 BOM removed and line endings normalized.

    Reading bytes and decoding with ``utf-8-sig`` drops the BOM that some
    upstream files carry; normalizing ``\\r\\n`` and ``\\r`` to ``\\n`` makes
    Windows-origin files indistinguishable from Unix ones, so the block-scalar
    scanner only ever has to reason about ``\\n``.
    """
    with open(str(path), "rb") as handle:
        raw = handle.read()
    return raw.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")

def _normalize(text: str) -> str:
    """Drop a leading BOM and normalize CRLF/CR to LF, whatever the entry point."""
    if text.startswith("﻿"):  # UTF-8 BOM decoded as U+FEFF
        text = text[1:]
    if "\r" in text:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text

def split_frontmatter(text: str) -> Tuple[Optional[str], str]:
    """Split *text* into the raw frontmatter block and the remaining body.

    Returns ``(None, text)`` when the document has no ``---`` delimited
    frontmatter at all, or when the opening ``---`` is never closed.
    """
    text = _normalize(text)
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return None, text
    for index in range(1, len(lines)):
        if lines[index].strip() in ("---", "..."):
            return "\n".join(lines[1:index]), "\n".join(lines[index + 1:])
    return None, text

def _strip_comment(text: str) -> str:
    """Drop a trailing ``#`` comment, which YAML only honours after whitespace."""
    out: List[str] = []
    quote: Optional[str] = None
    escaped = False
    previous = ""
    for char in text:
        if quote:
            out.append(char)
            if char == quote and not escaped:
                quote = None
        elif char in "\"'":
            quote = char
            out.append(char)
        elif char == "#" and previous in ("", " ", "\t"):
            break
        else:
            out.append(char)
        escaped = char == "\\" and not escaped
        if char != "\\":
            escaped = False
        previous = char
    return "".join(out).rstrip()

def _unescape_double(value: str) -> str:
    out: List[str] = []
    index = 0
    while index < len(value):
        char = value[index]
        if char == "\\" and index + 1 < len(value):
            nxt = value[index + 1]
            if nxt == "u" and index + 6 <= len(value):
                try:
                    out.append(chr(int(value[index + 2:index + 6], 16)))
                    index += 6
                    continue
                except ValueError:
                    pass
            if nxt == "x" and index + 4 <= len(value):
                try:
                    out.append(chr(int(value[index + 2:index + 4], 16)))
                    index += 4
                    continue
                except ValueError:
                    pass
            out.append(_DOUBLE_ESCAPES.get(nxt, nxt))
            index += 2
            continue
        out.append(char)
        index += 1
    return "".join(out)

def parse_scalar(raw: str) -> Optional[str]:
    """Parse a single-line YAML scalar (``plain`` / ``"double"`` / ``'single'``).

    Returns ``None`` for an empty value, which the caller reads as "this key has
    no inline value here".
    """
    text = _strip_comment(raw).strip()
    if text == "":
        return None
    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        return _unescape_double(text[1:-1])
    if len(text) >= 2 and text[0] == "'" and text[-1] == "'":
        return text[1:-1].replace("''", "'")
    if text[0] in "\"'":
        # Unbalanced quoting: keep the raw text rather than guessing.
        return text
    return text

def _indent_of(line: str) -> int:
    return len(line) - len(line.lstrip(" "))

def is_block_indicator(header: str) -> bool:
    """True when *header* introduces a block scalar rather than inline text."""
    text = header.strip()
    if not text or text[0] not in BLOCK_INDICATORS:
        return False
    return _BLOCK_HEADER_RE.match(text) is not None

def _fold_lines(content: List[str]) -> str:
    """Apply YAML folding rules to block-scalar *content* lines.

    A break between two plain, non-blank lines becomes a space.  ``k`` blank
    lines between two lines become ``k`` newlines.  More-indented lines keep
    their line breaks verbatim.
    """
    segments: List[str] = []
    pending_blanks = 0
    previous = "start"
    for line in content:
        if line.strip() == "":
            pending_blanks += 1
            continue
        kind = "more" if _indent_of(line) > 0 else "plain"
        if previous == "start":
            segments.append(line)
        elif previous == "plain" and kind == "plain":
            segments.append(" " if pending_blanks == 0 else "\n" * pending_blanks)
            segments.append(line)
        else:
            segments.append("\n" * max(pending_blanks, 1))
            segments.append(line)
        pending_blanks = 0
        previous = kind
    return "".join(segments)

def parse_block_scalar(lines: List[str], start: int, header: str) -> Tuple[str, int]:
    """Parse a block scalar body beginning at *lines*[*start*].

    *header* is the text that followed the ``:`` on the key line, e.g. ``">-"``.
    Returns ``(value, next_index)`` where *value* is chomped according to the
    header's chomping indicator and *next_index* is the first line after the
    scalar.
    """
    match = _BLOCK_HEADER_RE.match(header.strip())
    if not match:
        return header.strip(), start
    style, chomp, explicit = match.group("style"), match.group("chomp"), match.group("indent")

    probe = start
    while probe < len(lines) and lines[probe].strip() == "":
        probe += 1
    if explicit:
        block_indent = int(explicit)
    elif probe >= len(lines):
        block_indent = None
    else:
        block_indent = _indent_of(lines[probe])
        if block_indent == 0:
            # A block scalar body must be more indented than its key.
            return "", start

    if block_indent is None:
        if chomp == "+":
            return "\n" * (probe - start), start
        return "", start

    raw: List[str] = []
    index = start
    while index < len(lines):
        line = lines[index]
        if line.strip() == "":
            raw.append("")
            index += 1
            continue
        if _indent_of(line) < block_indent:
            break
        raw.append(line[block_indent:])
        index += 1

    trailing_blanks = 0
    while raw and raw[-1] == "":
        raw.pop()
        trailing_blanks += 1

    body = "\n".join(raw) if style == "|" else _fold_lines(raw)
    if not body:
        return ("\n" * trailing_blanks) if chomp == "+" else "", index
    if chomp == "-":
        return body, index
    if chomp == "+":
        return body + "\n" * (trailing_blanks + 1), index
    return body + "\n", index

def parse_frontmatter(text: str) -> Dict[str, Any]:
    """Parse the frontmatter of *text* into a flat mapping of top-level keys.

    Only keys at column 0 are returned.  Nested mappings and sequences are
    recognised well enough to be skipped without corrupting later top-level
    keys, which is all the hub needs from these documents.  When the document
    has no frontmatter the result is an empty mapping rather than an error.
    """
    block, _ = split_frontmatter(text)
    data: Dict[str, Any] = {}
    if block is None:
        return data
    lines = block.split("\n")
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.strip() == "" or line.lstrip().startswith("#"):
            index += 1
            continue
        if _indent_of(line) > 0 or line.lstrip().startswith("-"):
            index += 1
            continue
        match = _KEY_RE.match(line)
        if not match:
            index += 1
            continue
        key, rest = match.group("key"), match.group("rest")
        if is_block_indicator(rest):
            value, index = parse_block_scalar(lines, index + 1, rest)
        else:
            value = parse_scalar(rest)
            index += 1
        if key not in data:
            data[key] = value
    return data

def parse_document(text: str) -> Dict[str, Any]:
    """Alias of :func:`parse_frontmatter`, for readable call sites."""
    return parse_frontmatter(text)

def parse_file(path: Any) -> Dict[str, Any]:
    """Read *path* (BOM/CRLF tolerant) and return its frontmatter mapping."""
    return parse_frontmatter(read_document(path))

def normalize_description(value: Optional[str]) -> str:
    """Flatten a parsed ``description`` into the single line stored in the registry.

    A description is index metadata, so even a multi-paragraph folded scalar is
    joined into one line; the registry never stores a leading or trailing space
    and never stores a trailing newline.
    """
    if not value:
        return ""
    parts = [chunk.strip() for chunk in re.split(r"\n+", value)]
    return " ".join(part for part in parts if part).strip()

def field_of(text: str, field: str = "description") -> Optional[str]:
    """Return the faithful YAML value of *field* in *text* (may contain newlines)."""
    return parse_frontmatter(text).get(field)

def description_of(text: str) -> str:
    """Return the registry-ready single-line ``description`` of *text*."""
    return normalize_description(parse_frontmatter(text).get("description"))

if __name__ == "__main__":  # pragma: no cover - manual inspection helper
    import sys

    for argument in sys.argv[1:]:
        print(argument)
        for key, value in sorted(parse_file(argument).items()):
            print("  {}: {!r}".format(key, value))
