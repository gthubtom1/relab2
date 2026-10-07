#!/usr/bin/env python3
"""Ranking-specific regression checks for community-route.py.

Scope: the order in which adapted references inside one wrapper are offered and
truncated. These assertions were added together with the field-aware weight
model (see docs/community/ROUTE-RANKING.md). They do not touch the 4.7 status,
confidence, profile-derivation or fail-closed rules, which stay owned by
test-community-route.py and test-contract-v2.py.

Three groups of assertions:

* W  weight model: ``rank_score`` is recomputable from the reported hits, and the
  name weight is strictly above the description weight;
* N  name match outranks a description mention that used to tie with it;
* D  description-only routing still works. These are the anti-over-narrowing
   guard: a record whose directory name never contains the queried term must
   still be selected, and must still be selected because of its description.

T26 (design-freeze sections 1-2) added a fourth group of permanent regression
assertions, one per defect the routing signal layer must close, so a later
change cannot silently reopen the hole:

* D1 a record is reachable from its own hyphenated slug (the name widening must
   be reachable, not dead code behind the candidacy gate);
* D2 a hyphen compound in the description widens too (same cause, other field);
* D5 a stopword that is also an alias variant produces NO token
   (``tokens("workflow") == set()``);
* D6 importer provenance matches ZERO records (``community-raw``, ``skills-hub``).

The recomputability assertion in W was UPDATED, not removed, when the curated
signal class was added; it now also subtracts the signal term, so the permanent
invariant is

    rank_score == SIGNAL_HIT_WEIGHT*len(signal_hits)
                + NAME_HIT_WEIGHT*len(name_hits)
                + DESCRIPTION_HIT_WEIGHT*len(description_hits).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROUTE = ROOT / "skills" / "scripts" / "community-route.py"

# (hint, source, expected reference source_path, term that only exists in the
#  description) -- these are the permanent "description still routes" cases.
DESCRIPTION_ONLY_CASES = [
    ("burp suite zap", None,
     "workflows/security-engineer/skills/web-vulnerability/SKILL.md", "zap"),
    ("cloud metadata endpoint", "hack-skills",
     "skills/ssrf-server-side-request-forgery/SKILL.md", "alias_metadata"),
    ("BloodHound DCSync shadow credentials", "hack-skills",
     "skills/active-directory-acl-abuse/SKILL.md", "dcsync"),
    ("AS-REP roasting kerberoasting golden ticket", "hack-skills",
     "skills/active-directory-kerberos-attacks/SKILL.md", "alias_kerberoasting"),
    ("Coppersmith LWE \u683c\u653b\u51fb \u586b\u5145\u9884\u8a00\u673a", "ctf-super-hub",
     "ctf-crypto/SKILL.md", "coppersmith"),
    ("heap exploitation ROP ret2libc seccomp", "ctf-super-hub",
     "ctf-pwn/SKILL.md", "ret2libc"),
    ("\u5730\u7406\u5b9a\u4f4d \u7528\u6237\u540d\u679a\u4e3e \u5386\u53f2\u5feb\u7167", "ctf-super-hub",
     "ctf-osint/SKILL.md", "\u5386\u53f2\u5feb\u7167"),
    ("\u78c1\u76d8\u955c\u50cf \u9690\u5199\u5206\u6790 \u4e8b\u4ef6\u65e5\u5fd7 \u8bc1\u636e\u6062\u590d", "ctf-super-hub",
     "ctf-forensics/SKILL.md", "\u9690\u5199\u5206\u6790"),
]

# (hint, source, expected first reference) -- name match must win the order.
NAME_MATCH_CASES = [
    ("\u670d\u52a1\u7aef\u8bf7\u6c42\u4f2a\u9020", "hack-skills",
     "skills/ssrf-server-side-request-forgery/SKILL.md"),
    ("SSRF metadata endpoint access", "hack-skills",
     "skills/ssrf-server-side-request-forgery/SKILL.md"),
    ("CTF APK smali", "ctf-super-hub", "ctf-reverse/SKILL.md"),
    ("SQL injection login form", "hack-skills", "skills/sqli-sql-injection/SKILL.md"),
    ("websocket hijacking", "hack-skills", "skills/websocket-security/SKILL.md"),
]

def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)

def load_route_module():
    spec = importlib.util.spec_from_file_location("community_route_ranking", ROUTE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def show(payload: dict) -> list[dict]:
    return payload["matches"][0]["references"] if payload["matches"] else []

def check_weight_model(module) -> None:
    require(module.SIGNAL_HIT_WEIGHT > module.NAME_HIT_WEIGHT,
            f"signal weight {module.SIGNAL_HIT_WEIGHT} must outrank name weight "
            f"{module.NAME_HIT_WEIGHT}")
    require(module.NAME_HIT_WEIGHT > module.DESCRIPTION_HIT_WEIGHT,
            f"name weight {module.NAME_HIT_WEIGHT} must outrank description weight "
            f"{module.DESCRIPTION_HIT_WEIGHT}")
    require(module.NAME_HIT_WEIGHT >= 2 * module.DESCRIPTION_HIT_WEIGHT,
            "one name hit must outweigh any single description mention")
    for hint, source, expected, _ in DESCRIPTION_ONLY_CASES:
        for reference in show(module.lookup(hint, source)):
            recomputed = (module.SIGNAL_HIT_WEIGHT * len(reference["signal_hits"])
                          + module.NAME_HIT_WEIGHT * len(reference["name_hits"])
                          + module.DESCRIPTION_HIT_WEIGHT * len(reference["description_hits"]))
            require(recomputed == reference["rank_score"],
                    f"{hint!r} {reference['source_path']}: rank_score {reference['rank_score']} "
                    f"!= {recomputed} recomputed from the reported hits "
                    f"(signal_hits={reference['signal_hits']}, name_hits={reference['name_hits']}, "
                    f"description_hits={reference['description_hits']})")
    payload = module.lookup("\u670d\u52a1\u7aef\u8bf7\u6c42\u4f2a\u9020", "hack-skills")
    require(len(payload["matches"][0]["references"]) == module.REFERENCE_LIMIT,
            "the shown reference count must equal REFERENCE_LIMIT, not a magic literal")
    require(module.REFERENCE_LIMIT == 3,
            f"REFERENCE_LIMIT is a product decision and must stay 3, got {module.REFERENCE_LIMIT}")

def check_slug_self_recall(module) -> None:
    """D1: the name widening must be reachable, not dead code.

    Design-freeze 0/D1 measured 87 records that could not become a candidate for a
    hint built from their own slug, because candidacy was gated on the strict token
    set while the widening was consulted only afterwards inside the ranker. The
    named record is the one the freeze uses: ``llm integration`` must reach
    ``workflows/ai-ml-engineer/skills/llm-integration/SKILL.md``.

    The source filter is part of the assertion and not a weakening: this is a
    statement about ONE record, and the measurement harness
    (``work/p0/p0-measure.py``) makes the same per-source call.
    """
    target = "workflows/ai-ml-engineer/skills/llm-integration/SKILL.md"
    payload = module.lookup("llm integration", "ai-fullstack-delivery")
    references = show(payload)
    paths = [reference["source_path"] for reference in references]
    require(target in paths,
            f"D1: {target} is unreachable from its own hyphenated slug; got {paths}")
    reference = references[paths.index(target)]
    require(reference["name_hits"],
            f"D1: {target} must be reached by a name hit, got {reference['name_hits']}")
    require(payload["status"] in {"matched", "needs_review"},
            f"D1: unexpected status {payload['status']}")

def check_description_hyphen_widening(module) -> None:
    """D2: a hyphen compound in the description must widen.

    ``lattice`` reaches ``skills/lattice-crypto-attacks/SKILL.md``. The record
    says only ``Lattice-based``, which the strict tokeniser emits as one compound
    token, so before the fix this was 1 widening hit and 0 references.

    The source filter names the record under test; without it two wrappers answer
    ``lattice`` (both carry a curated signal for it) and the assertion would be
    about which vendor wins the wrapper-level tie, not about D2.
    """
    target = "skills/lattice-crypto-attacks/SKILL.md"
    references = show(module.lookup("lattice", "hack-skills"))
    paths = [reference["source_path"] for reference in references]
    require(target in paths,
            f"D2: {target} must be reachable from the hint 'lattice'; got {paths}")
    require(any(reference["signal_hits"] or reference["description_hits"] for reference in references),
            "D2: 'lattice' must be carried by a signal hit or a widened description hit")

def check_stopword_alias_is_stopped(module) -> None:
    """D5: a stopword that is also an alias variant must produce no token.

    ``normalize()`` used to rewrite ``workflow`` into ``alias_delivery`` before the
    stopword filter ran, so ``tokens("workflow") == {'alias_delivery'}`` and 154
    ai-fullstack records answered the word at confidence 1.0.
    """
    require(not module.tokens("workflow"),
            f"D5: tokens('workflow') must be empty, got {sorted(module.tokens('workflow'))}")
    payload = module.lookup("workflow")
    require(payload["status"] == "missing_input",
            f"D5: lookup('workflow') must be missing_input, got {payload['status']}")
    require(not payload["matches"],
            f"D5: lookup('workflow') must match nothing, got {len(payload['matches'])} wrapper(s)")

def check_provenance_matches_nothing(module) -> None:
    """D6: adapter provenance must not route to anything.

    ``community-raw`` and ``skills-hub`` were carried by 293/293 records (every
    ``path`` starts with ``community-raw/`` and every keyword list repeats
    ``skills-hub``), so they matched every record and discriminated nothing.
    """
    for hint in ("community-raw", "skills-hub"):
        payload = module.lookup(hint)
        shown = [reference for match in payload["matches"] for reference in match["references"]]
        require(not shown,
                f"D6: {hint!r} must match ZERO records, got {[r['source_path'] for r in shown]}")
        require(payload["status"] in {"missing_input", "needs_review"},
                f"D6: {hint!r} must not be a confident match, got {payload['status']}")

def check_name_outranks_description(module) -> None:
    for hint, source, expected in NAME_MATCH_CASES:
        references = show(module.lookup(hint, source))
        paths = [reference["source_path"] for reference in references]
        require(paths and paths[0] == expected,
                f"{hint!r}: first reference is {paths[:1]}, expected {expected}")
        require(references[0]["name_hits"], f"{hint!r}: winning reference has no name hit")
        require(len(references) == module.REFERENCE_LIMIT or len(paths) == len(set(paths)),
                "references must stay unique")

def check_description_only_still_routes(module) -> None:
    for hint, source, expected, term in DESCRIPTION_ONLY_CASES:
        payload = module.lookup(hint, source)
        references = show(payload)
        paths = [reference["source_path"] for reference in references]
        require(expected in paths,
                f"{hint!r}: description-only reference {expected} was not routed; got {paths}")
        reference = references[paths.index(expected)]
        require(reference["name_hits"] == [],
                f"{hint!r}: {expected} was expected to be a pure description hit, "
                f"got name_hits={reference['name_hits']}")
        require(term in reference["description_hits"],
                f"{hint!r}: {term!r} must be credited to the description of {expected}, "
                f"got {reference['description_hits']}")
        require(reference["rank_score"] >= references[0]["rank_score"],
                f"{hint!r}: routed reference is ranked below the first shown reference")
        require(payload["status"] in {"matched", "needs_review"},
                f"{hint!r}: unexpected status {payload['status']}")

def check_tie_break_is_deterministic(module) -> None:
    payload = module.lookup("crlf injection", "hack-skills")
    references = show(payload)
    require(len(references) >= 2, "CRLF hint must produce more than one reference")
    ranks = [reference["rank_score"] for reference in references]
    require(ranks == sorted(ranks, reverse=True), f"references are not rank-ordered: {ranks}")
    for first, second in zip(references, references[1:]):
        if first["rank_score"] == second["rank_score"] and len(first["name_hits"]) == len(second["name_hits"]):
            require(first["source_path"] < second["source_path"],
                    f"equal rank must fall back to ascending path: "
                    f"{first['source_path']} before {second['source_path']}")

def main() -> int:
    module = load_route_module()
    check_weight_model(module)
    check_name_outranks_description(module)
    check_description_only_still_routes(module)
    check_tie_break_is_deterministic(module)
    check_slug_self_recall(module)
    check_description_hyphen_widening(module)
    check_stopword_alias_is_stopped(module)
    check_provenance_matches_nothing(module)

    print("route ranking checks passed")
    print(f"  weight model: signal x{module.SIGNAL_HIT_WEIGHT} > name x{module.NAME_HIT_WEIGHT} > "
          f"description x{module.DESCRIPTION_HIT_WEIGHT}, REFERENCE_LIMIT={module.REFERENCE_LIMIT}")
    print(f"  name-match cases: {len(NAME_MATCH_CASES)}")
    print(f"  description-only cases (anti over-narrowing): {len(DESCRIPTION_ONLY_CASES)}")
    print("  defect guards: D1 slug self-recall, D2 description hyphen widening, "
          "D5 stopword/alias, D6 provenance")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
