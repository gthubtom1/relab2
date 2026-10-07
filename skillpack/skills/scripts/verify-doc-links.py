#!/usr/bin/env python3
"""Verify internal (relative) Markdown links and classify every broken one.

Why this gate classifies instead of counting
-------------------------------------------
`docs/community/**` keeps upstream READMEs verbatim as *provenance*. Their
relative links address the **upstream** repository layout, so most of them can
never resolve inside the integrated package. A single "N broken links" number
cannot distinguish a real regression (an active rule file pointing at a file
that no longer exists) from a registered archive link that is expected to stay
broken. This gate therefore

1. classifies every broken link as `active`, `wrapper` or `provenance` using the
   frozen table below (no manual, out-of-band agreement);
2. fails when a must-fix (`active` / `wrapper`) link is broken;
3. refuses to pass for `provenance` links until each one carries a registered
   disposition in `docs/community/link-triage.json` (file + target + reason),
   so "ignore the whole class" is impossible;
4. verifies that every file holding an open provenance break carries the
   reference-only banner marker, so a registration cannot be claimed without
   marking the document (spec 17.19).

No check was relaxed to make the numbers go down: the skip rules, the link
regex, the fence/inline-code handling and the "target must exist in the tree"
requirement are unchanged from the original checker.

What is checked
---------------
Only *local* links in Markdown: `http(s)`, `mailto:`, `tel:`, `ftp:`, `data:`,
protocol-relative, and pure `#anchor` links are ignored, as are links inside
fenced code blocks (``` / ~~~), inline code spans, and `TOOLS.md` targets.
Targets containing `{}<>`$*|` are skipped because they are templates, not paths.
Link targets are resolved relative to the containing file and matched against
the tree's file/directory set (UTF-8 paths, so CJK filenames compare correctly).

Which tree is validated
-----------------------
The **working tree** is authoritative: a gate must describe what would be
committed, and `git show :path` cannot see uncommitted edits. The git index blob
is used only as a fallback when a tracked file is absent from the working tree
(e.g. quarantined by antivirus), which keeps the original anti-quarantine
property. The file set is `git ls-files --cached --others --exclude-standard`,
i.e. tracked files plus new not-yet-staged files, minus git-ignored artifacts
(such as the generated `skillpack/skills/TOOLS.md`). When the package is copied
without `.git`, the check falls back to walking the working tree.

Classification rules (frozen, mirrored in `link-triage.json`)
------------------------------------------------------------
    skills/community/*/SKILL.md    -> wrapper     (the 4 community wrapper entrypoints)
    skills/community/**/SKILL.md   -> wrapper     (community entries in the discovery root)
    skills/community/**            -> provenance  (vendor reference data)
    docs/community/**              -> provenance  (upstream archive, spec 6.1)
    everything else                -> active      (fail-closed default)

`active` = canonical `skills/**` (outside `skills/community`), `skills/MASTER-ROUTING.md`,
`skills/routing.md`, `skills/INDEX.md`, `RULES.md`, `README*`, `AGENTS.md`,
`CLAUDE.md`, `docs/**` outside `docs/community/**`. `active` and `wrapper` must be 0.
`provenance` breaks are allowed to exist but every one of them must be registered.

Registry contract (`docs/community/link-triage.json`)
-----------------------------------------------------
`entries[]` holds one record per broken link measured at the triage baseline:
`file`, `line`, `target`, `class`, `source`, `disposition`, `status`, `reason`
(plus `evidence`, and `new_target` for rewritten links).

    status       `fixed`            link rewritten to a path that resolves now
                 `registered_open`  link kept; its file must carry the banner
    disposition  `rewrite_path` | `upstream_layout_unmappable` | `needs_human_review`

The live provenance breaks are joined to `registered_open` entries by
`(file, target)`; a live break without an entry fails the gate, and a
`registered_open` file without the banner marker fails it too. A registered
`line` that no longer matches the live line is reported as a warning (the join
is by file+target so an unrelated insertion above the link is not a failure).

Exit codes
----------    0   no active/wrapper break; every provenance break registered (and marked)
    1   active/wrapper break, unregistered provenance break, missing/drifted
        registry, unreadable file, or a registered file missing its banner
    10  must-fix is clean and everything is registered, but at least one entry is
        explicitly parked as `needs_human_review` (aligned with spec 4.7
        `needs_review` -> 10; the routine pass/fail contract stays 0/1 because
        spec 11.2 invokes this gate as a boolean document gate)

Usage
-----
    python skills/scripts/verify-doc-links.py                 # human report
    python skills/scripts/verify-doc-links.py --json          # machine-readable report
    python skills/scripts/verify-doc-links.py --report PATH   # write that report to PATH
    python skills/scripts/verify-doc-links.py --triage PATH   # use another registry
"""
import argparse
import json
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TRIAGE_REL = "docs/community/link-triage.json"
BANNER_MARKER = "<!-- link-triage: reference-only -->"

MUST_FIX_CLASSES = ("active", "wrapper")
CLASS_ORDER = ("active", "wrapper", "provenance")
# Dispositions a `registered_open` entry may carry: the link stays broken and
# needs the reference-only banner in its file.
OPEN_DISPOSITIONS = (
    "upstream_layout_unmappable",
    "needs_human_review",
)
# Dispositions a `fixed` entry may carry: `rewrite_path` retargeted the link at a
# migrated path; `documented_not_distributed` removed a reference to upstream
# tooling that this package does not ship and replaced it with accurate text.
FIXED_DISPOSITIONS = ("rewrite_path", "documented_not_distributed")
DISPOSITIONS = OPEN_DISPOSITIONS + FIXED_DISPOSITIONS
ENTRY_STATUSES = ("fixed", "registered_open")

# Frozen classification table. `class` decides the gate; `scope_detail` is a
# reporting refinement of the same decision and never changes pass/fail.
CLASSIFICATION_RULES = [
    {
        "id": "wrapper-entry",
        "glob": "skills/community/*/SKILL.md",
        "class": "wrapper",
        "scope_detail": "wrapper_entry",
        "rationale": (
            "the four community wrapper entrypoints (ctf-hub, hack-hub, delivery, "
            "apk-extension) are the only community files an active router hands off to; "
            "a break here breaks the documented next step (spec 4.3, 6.1)"
        ),
    },
    {
        "id": "community-skill-entry",
        "glob": "skills/community/**/SKILL.md",
        "class": "wrapper",
        "scope_detail": "community_skill_entry",
        "rationale": (
            "community SKILL.md files sit in the client discovery root skills/, so a break "
            "is reachable from an active load path; they stay wrapper-only and never "
            "canonical (spec 2.3, 11.3), which is why they are not 'active' either"
        ),
    },
    {
        "id": "community-archive-skills-root",
        "glob": "skills/community/**",
        "class": "provenance",
        "scope_detail": "community_archive",
        "rationale": (
            "vendor reference data kept under skills/community outside the SKILL.md "
            "entrypoints: archived, not executable, registered only"
        ),
    },
    {
        "id": "community-archive-docs",
        "glob": "docs/community/**",
        "class": "provenance",
        "scope_detail": "community_archive",
        "rationale": (
            "upstream README / RULES / workflow copies kept as the source archive; their "
            "relative links address the upstream repository layout (spec 6.1)"
        ),
    },
    {
        "id": "default-active",
        "glob": "**",
        "class": "active",
        "scope_detail": "default_active",
        "rationale": (
            "fail-closed default: RULES.md, README*, AGENTS.md, CLAUDE.md, canonical "
            "skills/** and docs/** outside docs/community are read as rules by a model, so "
            "an unmatched path is never silently ignored"
        ),
    },
]

# Repository path prefix -> registry `sources[].id`. Groups without an upstream
# source (the four wrappers) are first-party. Raw vendor trees moved out of the
# discovery root to `community-raw/<group>/` (spec 17.27); attribution follows
# them so a live break inside vendor content is still reported against its
# source instead of being mislabelled first-party. The classification table
# above is deliberately NOT changed.
SOURCE_BY_GROUP = {
    "hack-skills": "hack-skills",
    "ctf-super-hub": "ctf-super-hub",
    "ai-fullstack-delivery": "ai-fullstack-delivery",
    "ai-fullstack": "ai-fullstack-delivery",
    "apk-reverse-community": "apk-reverse-community",
    "apk-reverse-source": "apk-reverse-community",
}
RAW_ROOT = "community-raw"

LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
INLINE_CODE = re.compile(r"`[^`]*`")
FENCE = re.compile(r"^\s*(```|~~~)")
SKIP_PREFIX = ("http://", "https://", "mailto:", "tel:", "ftp:", "data:", "//", "#")
SKIP_CHARS = set("{}<>`$*|")

def in_git_worktree():
    result = subprocess.run(
        ["git", "-C", ROOT, "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0 and result.stdout.strip() == "true"

USE_GIT = in_git_worktree()

def glob_to_regex(pattern):
    """Translate a repo-relative glob into a regex.

    `**` crosses `/`, `*` and `?` do not, so the rule table reads the way a
    reviewer expects.
    """
    out = []
    i = 0
    while i < len(pattern):
        char = pattern[i]
        if char == "*" and pattern[i : i + 2] == "**":
            out.append(".*")
            i += 2
            continue
        if char == "*":
            out.append("[^/]*")
        elif char == "?":
            out.append("[^/]")
        else:
            out.append(re.escape(char))
        i += 1
    return re.compile("^" + "".join(out) + "$")

COMPILED_RULES = [(rule, glob_to_regex(rule["glob"])) for rule in CLASSIFICATION_RULES]

def classify(path):
    """Return the frozen rule that decides this path (last rule is fail-closed)."""
    for rule, regex in COMPILED_RULES:
        if regex.match(path):
            return rule
    raise RuntimeError(f"no classification rule matched {path}")

def attribute_source(path):
    """Map a repo path to the upstream source id it came from."""
    parts = path.split("/")
    if len(parts) >= 3 and parts[0] in ("docs", "skills") and parts[1] == "community":
        return SOURCE_BY_GROUP.get(parts[2], f"community:{parts[2]}")
    if len(parts) >= 2 and parts[0] == RAW_ROOT:
        return SOURCE_BY_GROUP.get(parts[1], f"community:{parts[1]}")
    return "first-party"

def snapshot_paths():
    """Return (files, dirs) for the tree that would be committed."""
    if USE_GIT:
        out = subprocess.run(
            [
                "git",
                "-C",
                ROOT,
                "-c",
                "core.quotePath=false",
                "ls-files",
                "-z",
                "--cached",
                "--others",
                "--exclude-standard",
            ],
            capture_output=True,
            check=True,
        ).stdout.decode("utf-8")
        files = {os.path.normpath(p).replace(os.sep, "/") for p in out.split("\0") if p}
    else:
        files = set()
        for current, dirs_on_disk, names in os.walk(ROOT):
            dirs_on_disk[:] = [d for d in dirs_on_disk if d != ".git"]
            for name in names:
                absolute = os.path.join(current, name)
                relative = os.path.relpath(absolute, ROOT)
                files.add(os.path.normpath(relative).replace(os.sep, "/"))
    dirs = set()
    for f in files:
        d = os.path.dirname(f)
        while d and d not in dirs:
            dirs.add(d)
            d = os.path.dirname(d)
    return files, dirs

def read_text(path):
    """Working tree first, git index blob as fallback (see module docstring)."""
    absolute = os.path.join(ROOT, path)
    if os.path.isfile(absolute):
        with open(absolute, "r", encoding="utf-8-sig", newline="") as handle:
            return handle.read()
    if USE_GIT:
        result = subprocess.run(
            ["git", "-C", ROOT, "show", f":{path}"], capture_output=True, check=False
        )
        if result.returncode == 0:
            return result.stdout.decode("utf-8-sig")
    raise RuntimeError(f"cannot read Markdown file: {path}")

def links_in(text):
    """Yield (lineno, target) for local links outside fenced code blocks."""
    in_fence = False
    for lineno, line in enumerate(text.splitlines(), 1):
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        for m in LINK.finditer(INLINE_CODE.sub("", line)):
            raw = m.group(1).strip().strip("<>")
            if not raw:
                continue
            target = raw.split()[0].split("#")[0].split("?")[0]
            if not target:
                continue
            if target.lower().startswith(SKIP_PREFIX):
                continue
            if "`TOOLS.md`" in target or SKIP_CHARS & set(target):
                continue
            yield lineno, target

def resolve(md, target):
    if target.startswith("/"):
        base = target.lstrip("/")
    else:
        base = os.path.join(os.path.dirname(md), target)
    return os.path.normpath(base).replace(os.sep, "/")

def collect(files, dirs):
    """Return (broken, all_targets, unreadable) for every Markdown file."""
    broken = []
    all_targets = {}
    unreadable = []
    for md in sorted(p for p in files if p.endswith(".md")):
        try:
            text = read_text(md)
        except RuntimeError as exc:
            unreadable.append(str(exc))
            continue
        targets = []
        for lineno, target in links_in(text):
            resolved = resolve(md, target)
            targets.append(target)
            if resolved in files or resolved in dirs:
                continue
            rule = classify(md)
            broken.append(
                {
                    "file": md,
                    "line": lineno,
                    "target": target,
                    "resolved": resolved,
                    "class": rule["class"],
                    "scope_detail": rule["scope_detail"],
                    "rule_id": rule["id"],
                    "source": attribute_source(md),
                }
            )
        all_targets[md] = targets
    return broken, all_targets, unreadable

def display_path(path):
    """Repo-relative POSIX path for messages; absolute when on another drive."""
    try:
        return os.path.relpath(path, ROOT).replace(os.sep, "/")
    except ValueError:
        return os.path.abspath(path).replace(os.sep, "/")

def load_triage(path):
    """Load the registration registry; return (data, problems)."""
    if not os.path.isfile(path):
        return None, [f"triage registry missing: {display_path(path)}"]
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError) as exc:
        return None, [f"triage registry is not readable JSON: {exc}"]

    problems = []
    if data.get("classification_rules") != CLASSIFICATION_RULES:
        problems.append(
            "triage registry classification_rules drifted from the checker rule table"
        )
    entries = data.get("entries")
    if not isinstance(entries, list):
        return None, problems + ["triage registry has no entries[] list"]

    required = ("file", "line", "target", "class", "source", "disposition", "status", "reason")
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            problems.append(f"entry #{index} is not an object")
            continue
        missing = [key for key in required if key not in entry]
        if missing:
            problems.append(f"entry #{index} ({entry.get('file', '?')}) missing {missing}")
            continue
        if entry["class"] not in CLASS_ORDER:
            problems.append(f"entry #{index} has unknown class {entry['class']!r}")
        if entry["disposition"] not in DISPOSITIONS:
            problems.append(f"entry #{index} has unknown disposition {entry['disposition']!r}")
        if entry["status"] not in ENTRY_STATUSES:
            problems.append(f"entry #{index} has unknown status {entry['status']!r}")
        if entry["status"] == "registered_open" and entry["disposition"] not in OPEN_DISPOSITIONS:
            problems.append(
                f"entry #{index} is registered_open with non-open disposition {entry['disposition']!r}"
            )
        if entry["status"] == "fixed" and entry["disposition"] not in FIXED_DISPOSITIONS:
            problems.append(
                f"entry #{index} is fixed with non-fixed disposition {entry['disposition']!r}"
            )
        if entry["disposition"] == "rewrite_path" and not entry.get("new_target"):
            problems.append(f"entry #{index} is rewrite_path but has no new_target")
        if entry["disposition"] == "documented_not_distributed" and not entry.get("evidence"):
            problems.append(f"entry #{index} is documented_not_distributed but has no evidence")
        if entry["status"] == "registered_open" and not entry.get("evidence"):
            problems.append(f"entry #{index} is registered_open but has no evidence")
    return data, problems

def check_registry(data, files, dirs, all_targets, broken):
    """Join live breaks with the registry; return (state, problems, warnings)."""
    problems = []
    warnings = []
    entries = data.get("entries", [])

    open_map = {}
    fixed = []
    for entry in entries:
        if entry.get("status") == "registered_open":
            key = (entry["file"], entry["target"])
            if key in open_map:
                problems.append(f"duplicate registered_open entry for {entry['file']} -> {entry['target']}")
                continue
            open_map[key] = entry
        elif entry.get("status") == "fixed":
            fixed.append(entry)

    registered = 0
    needs_human = 0
    unregistered = []
    banner_files = set()
    for link in broken:
        if link["class"] in MUST_FIX_CLASSES:
            continue
        entry = open_map.get((link["file"], link["target"]))
        if entry is None:
            unregistered.append(link)
            continue
        link["disposition"] = entry["disposition"]
        link["entry_status"] = entry["status"]
        registered += 1
        banner_files.add(link["file"])
        if entry.get("line") != link["line"]:
            warnings.append(
                f"triage line drift: {link['file']} -> {link['target']} registered at line"
                f" {entry.get('line')}, now at line {link['line']} (join is by file+target)"
            )
        if entry["disposition"] == "needs_human_review":
            needs_human += 1

    for path in sorted(banner_files):
        try:
            text = read_text(path)
        except RuntimeError as exc:
            problems.append(str(exc))
            continue
        if BANNER_MARKER not in text:
            problems.append(
                f"registered file without reference-only banner marker: {path} "
                f"(expected {BANNER_MARKER!r})"
            )

    stale = 0
    for entry in fixed:
        targets = all_targets.get(entry["file"])
        if targets is None:
            problems.append(f"fixed entry points at an unknown file: {entry['file']}")
            continue
        if entry["disposition"] == "documented_not_distributed":
            if entry["target"] in targets:
                problems.append(
                    f"entry claims the misleading reference was removed, but"
                    f" {entry['file']} still links {entry['target']}"
                )
            continue
        if entry["new_target"] not in targets:
            stale += 1
            warnings.append(
                f"stale triage: {entry['file']}:{entry['line']} no longer links {entry['new_target']}"
            )
            continue
        if resolve(entry["file"], entry["new_target"]) not in files and resolve(
            entry["file"], entry["new_target"]
        ) not in dirs:
            stale += 1
            warnings.append(
                f"stale triage: rewritten target does not resolve: {entry['file']} -> {entry['new_target']}"
            )

    dispositions = {}
    for entry in entries:
        if isinstance(entry, dict) and entry.get("disposition"):
            key = entry["disposition"]
            dispositions[key] = dispositions.get(key, 0) + 1

    state = {
        "registered": registered,
        "unregistered": unregistered,
        "needs_human_review": needs_human,
        "banner_files": sorted(banner_files),
        "entries_total": len(entries),
        "entries_fixed": len(fixed),
        "entries_open": len(open_map),
        "entries_by_disposition": dict(sorted(dispositions.items())),
        "stale": stale,
    }
    return state, problems, warnings

def by_class(broken):
    return {name: [link for link in broken if link["class"] == name] for name in CLASS_ORDER}

def by_source(links):
    counts = {}
    for link in links:
        counts[link["source"]] = counts.get(link["source"], 0) + 1
    return dict(sorted(counts.items()))

def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Verify internal Markdown links, classified active/wrapper/provenance."
    )
    parser.add_argument("--json", action="store_true", help="print a machine-readable report")
    parser.add_argument(
        "--report",
        default=None,
        help="write the machine-readable report to this path (UTF-8, also printed with --json)",
    )
    parser.add_argument(
        "--triage",
        default=TRIAGE_REL,
        help=f"triage registry, relative to the repo root (default: {TRIAGE_REL})",
    )
    args = parser.parse_args(argv)

    triage_path = args.triage if os.path.isabs(args.triage) else os.path.join(ROOT, args.triage)

    try:
        files, dirs = snapshot_paths()
        broken, all_targets, unreadable = collect(files, dirs)
    except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
        print(f"FAIL verify-doc-links: cannot scan the tree: {exc}")
        return 1

    groups = by_class(broken)
    must_fix = groups["active"] + groups["wrapper"]

    data, registry_problems = load_triage(triage_path)
    registry_state = None
    warnings = []
    if data is not None:
        registry_state, join_problems, warnings = check_registry(
            data, files, dirs, all_targets, broken
        )
        registry_problems += join_problems
        groups = by_class(broken)
        must_fix = groups["active"] + groups["wrapper"]

    failure_reasons = list(registry_problems) + unreadable
    if must_fix:
        failure_reasons.append(
            f"{len(must_fix)} must-fix (active/wrapper) broken link(s); must be 0"
        )
    if registry_state and registry_state["unregistered"]:
        failure_reasons.append(
            f"{len(registry_state['unregistered'])} provenance broken link(s) without a registry entry"
        )

    if failure_reasons:
        exit_code = 1
        status = "fail"
    elif registry_state and registry_state["needs_human_review"]:
        exit_code = 10
        status = "needs_review"
    else:
        exit_code = 0
        status = "ok"

    if args.json or args.report:
        dispositions = {}
        for link in groups["provenance"]:
            key = link.get("disposition", "unregistered")
            dispositions[key] = dispositions.get(key, 0) + 1
        report = {
            "tool": "skills/scripts/verify-doc-links.py",
            "status": status,
            "exit_code": exit_code,
            "scanned_markdown_files": len([p for p in files if p.endswith(".md")]),
            "broken_total": len(broken),
            "counts": {name: len(groups[name]) for name in CLASS_ORDER},
            "must_fix": len(must_fix),
            "provenance_by_source": by_source(groups["provenance"]),
            "provenance_by_disposition": dict(sorted(dispositions.items())),
            "triage_registry": display_path(triage_path),
            "registry": registry_state,
            "classification_rules": CLASSIFICATION_RULES,
            "warnings": warnings,
            "failures": failure_reasons,
            "links": broken,
        }
        if args.report:
            try:
                with open(args.report, "w", encoding="utf-8", newline="\n") as handle:
                    json.dump(report, handle, ensure_ascii=False, indent=2)
                    handle.write("\n")
            except OSError as exc:
                print(f"FAIL verify-doc-links: cannot write report: {exc}")
                return 1
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return exit_code

    print(
        f"verify-doc-links: {len(broken)} broken internal link(s) in "
        f"{len([p for p in files if p.endswith('.md')])} Markdown file(s)"
        f" — active={len(groups['active'])} wrapper={len(groups['wrapper'])}"
        f" provenance={len(groups['provenance'])}"
    )
    for name in CLASS_ORDER:
        links = groups[name]
        print(f"-- {name} ({len(links)}) --")
        for link in links:
            if name == "provenance":
                state = (
                    f"registered: {link['disposition']}"
                    if link.get("disposition")
                    else "UNREGISTERED"
                )
            else:
                state = "must-fix"
            print(
                f"  [{name}] {link['file']}:{link['line']} -> {link['target']}"
                f" {{source={link['source']}, {state}}}"
            )

    if registry_state:
        print(
            f"verify-doc-links: live provenance breaks registered"
            f" {registry_state['registered']}/{len(groups['provenance'])}; banner files"
            f" {len(registry_state['banner_files'])}; registry entries"
            f" {registry_state['entries_total']} (fixed={registry_state['entries_fixed']},"
            f" open={registry_state['entries_open']}, stale={registry_state['stale']})"
        )
        print(
            "verify-doc-links: registry dispositions "
            + ", ".join(
                f"{k}={v}" for k, v in registry_state["entries_by_disposition"].items()
            )
        )
        print(
            f"verify-doc-links: live provenance by source "
            + ", ".join(f"{k}={v}" for k, v in by_source(groups["provenance"]).items())
        )
        counts = {}
        for link in groups["provenance"]:
            key = link.get("disposition", "unregistered")
            counts[key] = counts.get(key, 0) + 1
        print(
            "verify-doc-links: live provenance dispositions "
            + ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
        )
    for warning in warnings:
        print(f"WARN verify-doc-links: {warning}")
    for reason in failure_reasons:
        print(f"FAIL verify-doc-links: {reason}")
    if exit_code == 1:
        return 1
    if exit_code == 10:
        print(
            f"NEEDS-REVIEW verify-doc-links: active=0 wrapper=0;"
            f" {registry_state['needs_human_review']} provenance entry/entries parked as"
            f" needs_human_review in {display_path(triage_path)}"
        )
        return 10
    print(
        f"OK verify-doc-links: active=0 wrapper=0; all {len(groups['provenance'])}"
        f" provenance break(s) registered in"
        f" {display_path(triage_path)}"
    )
    return 0

if __name__ == "__main__":
    sys.exit(main())
