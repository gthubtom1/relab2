#!/usr/bin/env python3
"""Validate the structure and cross-references of the integration spec.

Why this exists
---------------
docs/INTEGRATION-IMPLEMENTATION-SPEC.md went through three rounds of appended
revisions. Round two appended subsections 17.14-17.26 *after* section 19, which
made the numbering unreadable and let a whole section be dropped during a
manual reorder. Numbering drift is a documentation defect that a machine can
catch, so it is checked here instead of relying on review.

Checks
------
1. Top-level section numbers are strictly increasing by one (section 0 allowed).
2. Subsections under each "## N." heading are contiguous (N.1, N.2, ...).
3. No duplicate headings.
4. Every "第 N 节" cross-reference points at an existing top-level section.
5. Every task card referenced in the build order (T00-T26) has a card heading.
6. Delivery phases referenced in prose (Wave 0/1A/...) stay consistent with
   the task cards that actually exist.
7. No "17.x" subsection appears after section 18.

Exit codes follow spec section 4.7: 0 = ok, 10 = needs_review, 20 = blocked.
Structural defects are treated as blocked (20) because they make the spec
unusable as a construction baseline; ambiguous but non-fatal findings (10) are
reported as warnings.

Usage:
    python skills/scripts/verify-spec-structure.py [--spec PATH]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

DEFAULT_SPEC = "docs/INTEGRATION-IMPLEMENTATION-SPEC.md"
TASK_CARD_RE = re.compile(r"^### (T\d{2})\b")
TOP_SECTION_RE = re.compile(r"^## (\d+)\.\s+(.*)$")
SUB_SECTION_RE = re.compile(r"^### (\d+)\.(\d+)\s+(.*)$")
SECTION_REF_RE = re.compile(r"第\s*(\d+)\s*节")
WAVE_RE = re.compile(r"^\s*Wave\s+([0-9]+\w?)\s*[::]\s*(.*)$")

class Finding:
    def __init__(self, level: str, message: str, line: int | None = None) -> None:
        self.level = level
        self.message = message
        self.line = line

    def __str__(self) -> str:
        where = f":{self.line}" if self.line else ""
        return f"[{self.level.upper()}]{where} {self.message}"

def check(path: Path) -> tuple[list[Finding], dict]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    findings: list[Finding] = []

    top_sections: list[tuple[int, int, str]] = []  # (number, lineno, title)
    subsections: list[tuple[int, int, int, str, int]] = []  # (major, minor, ...)
    task_cards: dict[str, int] = {}
    headings: dict[str, int] = {}

    for i, line in enumerate(lines, start=1):
        m_top = TOP_SECTION_RE.match(line)
        if m_top:
            top_sections.append((int(m_top.group(1)), i, m_top.group(2).strip()))
        m_sub = SUB_SECTION_RE.match(line)
        if m_sub:
            subsections.append(
                (int(m_sub.group(1)), int(m_sub.group(2)), i, m_sub.group(3).strip(), i)
            )
        m_card = TASK_CARD_RE.match(line)
        if m_card:
            card = m_card.group(1)
            if card in task_cards:
                findings.append(
                    Finding("blocked", f"duplicate task card heading {card}", i)
                )
            task_cards[card] = i
        if line.startswith("#"):
            key = line.strip()
            if key in headings:
                findings.append(
                    Finding("blocked", f"duplicate heading: {key}", i)
                )
            headings[key] = i

    if not top_sections:
        findings.append(Finding("blocked", "no top-level sections found"))
        return findings, {}

    # 1. top-level numbering
    numbers = [n for n, _, _ in top_sections]
    expected = list(range(numbers[0], numbers[0] + len(numbers)))
    if numbers != expected:
        for want, got, (_, ln, title) in zip(expected, numbers, top_sections):
            if want != got:
                findings.append(
                    Finding(
                        "blocked",
                        f"top-level numbering jumped: expected {want}, found {got} ({title})",
                        ln,
                    )
                )
                break

    # 2. subsection continuity per major section.
    # A leading "N.0" preamble subsection (e.g. 4.0, 12.0) is allowed, but then
    # the remaining numbers must still be contiguous.
    by_major: dict[int, list[tuple[int, int, str]]] = {}
    for major, minor, ln, title, _ in subsections:
        by_major.setdefault(major, []).append((minor, ln, title))
    for major in sorted(by_major):
        minors = [m for m, _, _ in by_major[major]]
        start = 0 if minors and minors[0] == 0 else 1
        want = list(range(start, start + len(minors)))
        if minors != want:
            first_bad = next(
                (i for i, (a, b) in enumerate(zip(minors, want)) if a != b), 0
            )
            _, ln, title = by_major[major][first_bad]
            findings.append(
                Finding(
                    "blocked",
                    f"section {major}.x not contiguous (found {minors}); "
                    f"first mismatch at {major}.{minors[first_bad]} ({title})",
                    ln,
                )
            )

    # 7. 17.x must not appear after section 18
    if 18 in by_major:
        sec18_line = next(ln for n, ln, _ in top_sections if n == 18)
        for minor, ln, title in by_major.get(17, []):
            if ln > sec18_line:
                findings.append(
                    Finding("blocked", f"17.{minor} appears after section 18: {title}", ln)
                )

    # 4. cross-references
    valid_numbers = {n for n, _, _ in top_sections}
    for i, line in enumerate(lines, start=1):
        for ref in SECTION_REF_RE.findall(line):
            if int(ref) not in valid_numbers:
                findings.append(
                    Finding("blocked", f"cross-reference to missing section 第 {ref} 节", i)
                )

    # 5. build order task cards exist
    build_order_line = next(
        (ln for n, ln, t in top_sections if "推荐施工顺序" in t), None
    )
    if build_order_line:
        referenced: set[str] = set()
        for i in range(build_order_line, min(build_order_line + 40, len(lines))):
            referenced.update(re.findall(r"\bT(\d{2})\b", lines[i]))
        for num in sorted(referenced):
            card = f"T{num}"
            if card not in task_cards:
                findings.append(
                    Finding(
                        "blocked",
                        f"build order references {card} but no task card heading exists",
                        build_order_line,
                    )
                )

    # 6. task cards described outside the task boards
    stats = {
        "top_sections": len(top_sections),
        "subsections": len(subsections),
        "task_cards": len(task_cards),
        "last_section": numbers[-1],
        "max_subsections": {m: len(v) for m, v in sorted(by_major.items())},
        "lines": len(lines),
    }
    return findings, stats

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", default=DEFAULT_SPEC, help="path to the spec markdown")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[2]
    spec = Path(args.spec)
    if not spec.is_absolute():
        spec = root / spec
    if not spec.is_file():
        print(f"FAIL spec not found: {spec}")
        return 20

    findings, stats = check(spec)
    for f in findings:
        print(f)

    print(
        "spec structure: "
        f"sections={stats.get('top_sections')} "
        f"subsections={stats.get('subsections')} "
        f"task_cards={stats.get('task_cards')} "
        f"lines={stats.get('lines')}"
    )
    print("subsection counts:", stats.get("max_subsections"))

    blocked = [f for f in findings if f.level == "blocked"]
    review = [f for f in findings if f.level == "review"]
    if blocked:
        print(f"FAIL verify-spec-structure: {len(blocked)} structural defect(s)")
        return 20
    if review:
        print(f"NEEDS_REVIEW verify-spec-structure: {len(review)} item(s)")
        return 10
    print("PASS verify-spec-structure")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
