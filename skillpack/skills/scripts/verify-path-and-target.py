#!/usr/bin/env python3
"""Path and target enforcement guard (T22, spec 17.16 / 17.17).

Read-only: this script never writes to the repository. It only reads file
metadata via os.lstat (no file contents are executed) and classifies a given
path / URL / redirect chain / DNS answer sequence as ALLOW or DENY.

Fail-closed: anything uncertain is DENY (exit 20). Exit codes follow spec 4.7:
0 = allow/ok, 20 = deny/blocked, 2 = usage error.

Relationship to existing guards (do not duplicate, do not weaken):
- skills/scripts/verify-repository-security.py `check_symlink_targets` only
  inspects git-index mode-120000 entries (tracked symlink *target strings*).
  This guard covers the *live working tree*: realpath containment of a
  candidate path plus lstat reparse/symlink/hardlink detection on every
  ancestor, which the index check cannot see (e.g. an untracked junction
  planted after checkout).
- scripts/verify-source-attestation.py canonicalizes source paths (NFC +
  casefold collision scan, digest contract). This guard reuses the same
  NFC+casefold idea for case/artifact roots but enforces containment and the
  network target allowlist, which attestation never does.

Usage:
    python skills/scripts/verify-path-and-target.py            # self-test vectors
    python skills/scripts/verify-path-and-target.py --root DIR --check-path P
    python skills/scripts/verify-path-and-target.py --check-url URL --allow-host H [--allow-port N] [--allow-scheme S]
    python skills/scripts/verify-path-and-target.py --redirect-chain U1,U2 [--allow-host H ...]
    python skills/scripts/verify-path-and-target.py --dns-host H --dns-answers A1 --dns-answers A2 [--allow-cidr CIDR]
    python skills/scripts/verify-path-and-target.py --scan-tree DIR   # live reparse/hardlink scan

Standard library only. No network access: DNS answers and redirect chains are
supplied by the caller (offline fixtures), never fetched here.
"""

from __future__ import annotations

import argparse
import ipaddress
import os
import re
import sys
import unicodedata
from pathlib import PureWindowsPath
from urllib.parse import urlsplit

REPARSE_ATTR = 0x400  # FILE_ATTRIBUTE_REPARSE_POINT
MAX_COMPONENT = 255
MAX_TOTAL = 32767
WIN_RESERVED = (
    {"con", "prn", "aux", "nul"}
    | {f"com{i}" for i in range(1, 10)}
    | {f"lpt{i}" for i in range(1, 10)}
)
DEFAULT_SCHEMES = ("https",)
DEFAULT_PORTS = {"https": 443, "http": 80}

_UNC = re.compile(r"^(\\\\|//|\\\\[.?]\\|\\[.?]\\)")
_DRIVE = re.compile(r"^[A-Za-z]:")

def _deny(reason: str) -> tuple[bool, str]:
    return False, f"DENY {reason}"

def _allow(note: str) -> tuple[bool, str]:
    return True, f"ALLOW {note}"

def nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)

def parse_symlink_target_shape(target: str) -> tuple[bool, str]:
    """String-level symlink-target check (same shapes as the git-index check).

    Usable without privileges: no filesystem touch. Absolute targets, drive
    targets and '..' escapes are DENY.
    """
    target = target.strip()
    parts = PureWindowsPath(target.replace("/", "\\")).parts if "\\" in target or _DRIVE.match(target) else target.split("/")
    if target.startswith("/") or target.startswith("\\") or _DRIVE.match(target):
        return _deny(f"symlink-target escapes root: absolute target {target!r}")
    if ".." in (p for p in target.replace("\\", "/").split("/")):
        return _deny(f"symlink-target escapes root: '..' in {target!r}")
    if not target or target in (".",):
        return _deny("symlink-target is empty/self")
    _ = parts
    return _allow(f"symlink-target shape ok: {target!r}")

def check_path_string(root: str, candidate: str) -> tuple[bool, str]:
    """Pure-string containment pre-check (no FS touch)."""
    if "\x00" in candidate:
        return _deny("path contains NUL byte")
    work = candidate.replace("/", "\\")
    if _UNC.match(candidate) or _UNC.match(work):
        return _deny(f"UNC/device path rejected: {candidate!r}")
    # Drive-letter escape: candidate pins a drive different from root's drive.
    cm = _DRIVE.match(work.strip())
    if cm:
        root_drive = _DRIVE.match(root.replace("/", "\\").strip())
        root_d = root_drive.group(0).casefold() if root_drive else ""
        if cm.group(0).casefold() != root_d:
            return _deny(f"drive-letter escape: {candidate!r} vs root drive {root_d!r}")
    parts = [p for p in work.split("\\") if p not in ("", ".")]
    if ".." in parts:
        return _deny(f"path traversal ('..') rejected: {candidate!r}")
    if len(candidate) > MAX_TOTAL:
        return _deny(f"path exceeds {MAX_TOTAL} chars")
    for part in parts:
        if len(part) > MAX_COMPONENT:
            return _deny(f"path component exceeds {MAX_COMPONENT} chars: {part!r}")
        if part != part.strip(" .") and (part.endswith(" ") or part.endswith(".")):
            return _deny(f"trailing dot/space component rejected: {part!r}")
        stem = part.split(".")[0].casefold()
        if stem in WIN_RESERVED:
            return _deny(f"Windows reserved name rejected: {part!r}")
    # Casefold cross-root coverage: containment must hold case-insensitively
    # (Windows NTFS is case-insensitive; a differently-cased root sibling is
    # the same directory). Compare NFC+casefold forms.
    norm_root = nfc(os.path.abspath(root)).casefold()
    norm_cand = nfc(os.path.abspath(os.path.join(root, candidate))).casefold()
    if norm_cand != norm_root and not norm_cand.startswith(norm_root + os.sep.casefold()):
        return _deny(f"realpath escapes root (casefold): {candidate!r}")
    return _allow(f"path string contained: {candidate!r}")

def lstat_flags(path: str) -> tuple[bool, bool, int]:
    """(is_symlink, is_reparse, nlink) for one path; fail-closed on error."""
    try:
        st = os.lstat(path)
    except OSError:
        return False, True, 0  # cannot stat -> treat as reparse (deny)
    is_link = os.path.islink(path)
    is_reparse = False
    attrs = getattr(st, "st_file_attributes", 0) or 0
    if attrs & REPARSE_ATTR:
        is_reparse = True
    tag = getattr(st, "st_reparse_tag", 0) or 0
    if tag:
        is_reparse = True
    return is_link, is_reparse, getattr(st, "st_nlink", 1)

def check_live_path(root: str, candidate: str) -> tuple[bool, str]:
    """String check + live ancestor walk (symlink/junction/reparse/hardlink)."""
    ok, msg = check_path_string(root, candidate)
    if not ok:
        return ok, msg
    abs_root = os.path.abspath(root)
    abs_cand = os.path.abspath(os.path.join(root, candidate))
    # Walk the candidate and every ancestor down to (not above) the root.
    node = abs_cand
    while True:
        is_link, is_reparse, nlink = lstat_flags(node) if os.path.lexists(node) else (False, False, 1)
        if is_link:
            return _deny(f"symlink on path rejected: {node!r}")
        if is_reparse:
            return _deny(f"junction/reparse point on path rejected: {node!r}")
        if os.path.isfile(node) if hasattr(os.path, "isfile") else False:
            pass
        try:
            if os.path.lexists(node) and not os.path.isdir(node) and nlink > 1:
                return _deny(f"hardlink (nlink={nlink}) rejected: {node!r}")
        except OSError:
            return _deny(f"hardlink state unreadable, fail-closed: {node!r}")
        if nfc(node).casefold() == nfc(abs_root).casefold():
            break
        parent = os.path.dirname(node)
        if parent == node or len(parent) < len(abs_root):
            break
        node = parent
    # Realpath (resolves symlinks where the OS supports it) must stay inside.
    try:
        real = nfc(os.path.realpath(abs_cand)).casefold()
        if real != nfc(abs_root).casefold() and not real.startswith(nfc(abs_root).casefold() + os.sep):
            return _deny(f"realpath escapes root: {candidate!r}")
    except OSError:
        return _deny(f"realpath unreadable, fail-closed: {candidate!r}")
    return _allow(f"live path contained: {candidate!r}")

def canon_host(host: str) -> str:
    host = nfc(host.strip().rstrip(".").lower())
    try:
        host = host.encode("idna").decode("ascii")
    except (UnicodeError, ValueError):
        pass  # scan-ok: IDNA 只是把 unicode 域转 punycode；转不了就按原串比 —— allow 集与候选都走本函数，规范化失败对两边对称，不会放宽允许集
    return host

def check_url(url: str, allow_hosts: list[str], allow_ports: list[int] | None = None,
              allow_schemes: list[str] | None = None) -> tuple[bool, str]:
    schemes = tuple(s.lower() for s in (allow_schemes or list(DEFAULT_SCHEMES)))
    try:
        parts = urlsplit(url)
    except ValueError as exc:
        return _deny(f"URL unparsable, fail-closed: {exc}")
    if parts.scheme.lower() not in schemes:
        return _deny(f"scheme not in allowlist: {parts.scheme!r} not in {list(schemes)!r}")
    if "@" in (parts.netloc or "") and parts.username is None and "@" in url.split("://", 1)[-1].split("/")[0]:
        return _deny("userinfo '@' in authority rejected")
    if parts.username or parts.password:
        return _deny("URL userinfo rejected")
    host = canon_host(parts.hostname or "")
    if not host:
        return _deny("empty host rejected")
    allowed = {canon_host(h) for h in allow_hosts}
    if host not in allowed:
        return _deny(f"host not in allowlist: {host!r}")
    port = parts.port
    if port is None:
        port = DEFAULT_PORTS.get(parts.scheme.lower(), -1)
    if allow_ports is not None and port not in allow_ports:
        return _deny(f"port {port} not in allowlist {allow_ports!r}")
    if parts.scheme.lower() == "http" and "http" not in schemes:
        return _deny("cleartext http not in scheme allowlist")
    return _allow(f"target allowed: {host}:{port}")

def check_redirect_chain(chain: list[str], **kw) -> tuple[bool, str]:
    for hop in chain:
        ok, msg = check_url(hop, **kw)
        if not ok:
            return _deny(f"redirect hop escapes allowlist: {hop!r} ({msg})")
    return _allow(f"redirect chain of {len(chain)} hop(s) inside allowlist")

def check_dns_binding(host: str, answers: list[list[str]],
                      allow_cidrs: list[str] | None = None) -> tuple[bool, str]:
    """Offline DNS-rebinding gate: answers are successive lookup results."""
    if not answers or any(not a for a in answers):
        return _deny(f"empty DNS answer for {host!r}, fail-closed")
    first = sorted(answers[0])
    for round_no, answer in enumerate(answers[1:], 2):
        if sorted(answer) != first:
            return _deny(f"DNS rebinding: {host!r} answer changed round 1 -> {round_no}")
    if allow_cidrs:
        nets = []
        for cidr in allow_cidrs:
            try:
                nets.append(ipaddress.ip_network(cidr, strict=False))
            except ValueError:
                return _deny(f"bad allow-cidr {cidr!r}, fail-closed")
        for ip_text in first:
            try:
                ip = ipaddress.ip_address(ip_text)
            except ValueError:
                return _deny(f"unparsable DNS IP {ip_text!r}, fail-closed")
            if not any(ip in net for net in nets):
                return _deny(f"DNS IP {ip_text!r} outside allow-cidrs")
    return _allow(f"DNS binding stable for {host!r}: {','.join(first)}")

def scan_tree(path: str) -> tuple[list[str], list[str]]:
    """Live working-tree scan: reparse/symlink list + hardlink list."""
    bad_links: list[str] = []
    hardlinks: list[str] = []
    for current, dirs, files in os.walk(path, followlinks=False):
        for name in dirs + files:
            full = os.path.join(current, name)
            is_link, is_reparse, nlink = lstat_flags(full)
            if is_link or is_reparse:
                bad_links.append(full)
            elif full and not os.path.isdir(full) and nlink > 1 and os.path.isfile(full):
                hardlinks.append(f"{full} (nlink={nlink})")
    return bad_links, hardlinks

SELF_VECTORS: list[tuple[str, bool]] = [
    # (description, expected_allow)
]

def run_self_test() -> int:
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    cases: list[tuple[str, bool, tuple[bool, str]]] = []
    cases.append(("traversal", False, check_path_string(root, "..\\..\\Windows\\System32")))
    cases.append(("unc", False, check_path_string(root, "\\\\server\\share\\x")))
    cases.append(("drive-escape", False, check_path_string(root, "C:\\Windows")))
    cases.append(("reserved", False, check_path_string(root, "case\\CON.txt")))
    cases.append(("ok-relative", True, check_path_string(root, "work\\case1\\scope.md")))
    cases.append(("symlink-shape-abs", False, parse_symlink_target_shape("/etc/passwd")))
    cases.append(("symlink-shape-dotdot", False, parse_symlink_target_shape("../../evil")))
    cases.append(("symlink-shape-ok", True, parse_symlink_target_shape("assets/icon.png")))
    cases.append(("url-allow", True, check_url("https://allowed.example/", ["allowed.example"])))
    cases.append(("url-evil-host", False, check_url("https://evil.example/", ["allowed.example"])))
    cases.append(("url-userinfo", False, check_url("https://user@allowed.example/", ["allowed.example"])))
    cases.append(("url-bad-port", False, check_url("https://allowed.example:8443/", ["allowed.example"], allow_ports=[443])))
    cases.append(("redirect-escape", False, check_redirect_chain(
        ["https://allowed.example/a", "https://evil.example/b"], allow_hosts=["allowed.example"])))
    cases.append(("dns-rebind", False, check_dns_binding(
        "h", [["10.0.0.1"], ["10.0.0.2"]], allow_cidrs=["10.0.0.0/8"])))
    cases.append(("dns-stable", True, check_dns_binding(
        "h", [["10.0.0.5"], ["10.0.0.5"]], allow_cidrs=["10.0.0.0/8"])))
    failures = 0
    for name, expected, (got, msg) in cases:
        status = "ok" if got == expected else "MISMATCH"
        if got != expected:
            failures += 1
        print(f"[{status}] {name}: expected={'ALLOW' if expected else 'DENY'} got={msg}")
    if failures:
        print(f"FAIL verify-path-and-target self-test: {failures} mismatch(es)")
        return 20
    print(f"OK verify-path-and-target self-test: {len(cases)} vectors")
    return 0

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None)
    parser.add_argument("--check-path", default=None)
    parser.add_argument("--check-url", default=None)
    parser.add_argument("--allow-host", action="append", default=[])
    parser.add_argument("--allow-port", action="append", type=int, default=None)
    parser.add_argument("--allow-scheme", action="append", default=None)
    parser.add_argument("--redirect-chain", default=None)
    parser.add_argument("--dns-host", default=None)
    parser.add_argument("--dns-answers", action="append", default=[])
    parser.add_argument("--allow-cidr", action="append", default=[])
    parser.add_argument("--scan-tree", default=None)
    args = parser.parse_args(argv)

    if args.scan_tree:
        bad, hard = scan_tree(args.scan_tree)
        for item in bad:
            print(f"[BLOCKED] link/reparse: {item}")
        for item in hard:
            print(f"[BLOCKED] hardlink: {item}")
        if bad or hard:
            print(f"FAIL verify-path-and-target scan: {len(bad)} link(s), {len(hard)} hardlink(s)")
            return 20
        print(f"OK verify-path-and-target scan: no links/hardlinks under {args.scan_tree}")
        return 0
    if args.check_path is not None:
        root = args.root or os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        ok, msg = check_live_path(root, args.check_path)
        print(msg)
        return 0 if ok else 20
    if args.check_url is not None:
        ok, msg = check_url(args.check_url, args.allow_host or ["allowed.example"],
                            args.allow_port, args.allow_scheme)
        print(msg)
        return 0 if ok else 20
    if args.redirect_chain is not None:
        chain = [u for u in args.redirect_chain.split(",") if u]
        ok, msg = check_redirect_chain(chain, allow_hosts=args.allow_host or ["allowed.example"],
                                       allow_ports=args.allow_port,
                                       allow_schemes=args.allow_scheme)
        print(msg)
        return 0 if ok else 20
    if args.dns_host is not None:
        answers = [a.split("+") for a in args.dns_answers]
        ok, msg = check_dns_binding(args.dns_host, answers, args.allow_cidr or None)
        print(msg)
        return 0 if ok else 20
    return run_self_test()

if __name__ == "__main__":
    raise SystemExit(main())
