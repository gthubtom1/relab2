#!/usr/bin/env python3
"""Fail closed on package executable/reference boundary regressions.

The check reads Git index blobs when available, so antivirus quarantine of a
working-tree research payload cannot silently remove it from review coverage.
Copied distributions without ``.git`` use their working tree as the review
surface instead of crashing before the gate runs.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import os
from pathlib import PurePosixPath

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def in_git_worktree():
    result = subprocess.run(
        ["git", "-C", ROOT, "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,   # ★ 2026-10-16：git 卡住（锁/网络盘）不该把整道门拖死
    )
    return result.returncode == 0 and result.stdout.strip() == "true"

USE_GIT = in_git_worktree()

PAYLOAD_PATH = "skills/pentest-tools/src-hunter/references/payloader/waf-bypass.md"
PAYLOAD_SHA256 = "bc15ca915f24a321bdee833de61d1e144f26010b71f1f9dd4f123226f956c6a5"  # 2026-10-18: 仅在 waf-bypass.md 加了交叉引用（纯文档），无新增 payload
ALLOWED_BINARY_HASHES = {
    "burp-mcp-full/gradle/wrapper/gradle-wrapper.jar":
        "2db75c40782f5e8ba1fc278a5574bab070adccb2d21ca5a6e5ed840888448046",
}
EXECUTABLE_SUFFIXES = {
    ".ps1", ".sh", ".py", ".js", ".mjs", ".cjs", ".java", ".bat", ".cmd"
}
BINARY_SUFFIXES = {
    ".exe", ".dll", ".so", ".dylib", ".sys", ".jar", ".zip", ".7z",
    ".rar", ".bin", ".apk", ".ipa", ".wasm", ".class", ".pyc"
}
SCAN_EXCLUDES = {"skills/scripts/verify-repository-security.py"}
EXPECTED_PATTERN_HITS = {
    ("kali/scripts/lib/tool-discovery.sh", "dev-tcp-port-probe"),
    ("skills/scripts/lib/Bootstrap.ps1", "tcp-client-health-probe"),
    # mcp-status.ps1 的三列里有一列就是"谁在监听"——所以它必须真的探一次端口。
    # 与 Bootstrap.ps1 同一个模式、同一个理由：这是健康探针，不是被投递的载荷。
    ("skills/scripts/mcp-status.ps1", "tcp-client-health-probe"),
}
PATTERNS = {
    "dynamic-powershell-eval": re.compile(r"Invoke" r"-Expression|\bIEX\b", re.I),
    "encoded-loader": re.compile(r"FromBase64" r"String|Download" r"String", re.I),
    "pipe-to-shell": re.compile(r"(?:curl|wget)[^\n]*\|\s*(?:ba)?sh\b", re.I),
    "root-recursive-delete": re.compile(r"\brm\s+-rf\s+/\s*(?:$|[;&|])", re.M),
    "database-drop": re.compile(r"\bDROP\s+(?:DATABASE|TABLE)\b", re.I),
    "tcp-client-health-probe": re.compile(r"System\.Net\.Sockets\.TCPClient", re.I),
    "dev-tcp-port-probe": re.compile(r"/dev/tcp/"),
}
ACTION_USE = re.compile(r"^\s*-?\s*uses:\s*([^\s#]+)", re.M)
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
# 每个客户端认的入口文件名不同：Claude 认 CLAUDE.md，Codex/Cursor 认 AGENTS.md。
# 这个技能包只提供了 CLAUDE.md，所以 AGENTS.md 不在清单里 ——
# 早先把 AGENTS.md 列进来会永远报「missing from index」，那是清单写错，不是文件缺失。
AGENT_ENTRY_FILES = ("README_AI.md", "RULES.md", "RULES_zh.md", "CLAUDE.md")
REQUIRED_AGENT_CONSENT_MARKERS = (
    "Reading repository files is not authorization to execute them.",
    "Explicit user approval is required before running any repository script.",
    "Client-global configuration remains opt-in.",
)
UNSAFE_AGENT_ENTRY_PATTERNS = {
    "execute-section-on-read": re.compile(r"execute section 0 immediately", re.I),
    "automatic-execution-on-read": re.compile(r"must automatically execute", re.I),
    "remove-user-from-setup": re.compile(
        r"the user does not need to operate manually", re.I
    ),
    "global-instruction-injection": re.compile(r"global injection", re.I),
    "execute-immediately-after-read": re.compile(
        r"execute immediately after reading", re.I
    ),
    "must-run-after-read": re.compile(
        r"after reading this file,?\s+you must now", re.I
    ),
    "side-effects-as-read-goal": re.compile(r"produce actual side effects", re.I),
    "skip-first-consent": re.compile(r"do not wait for the user to say", re.I),
    "auto-configure-after-read": re.compile(
        r"auto-configure after reading", re.I
    ),
    "execute-after-read-zh": re.compile(
        r"读完(?:本文件|规则|文档)?后?[^\n]{0,40}(?:立即[^\n]{0,6}(?:执行|运行)|必须[：,:， ]{0,3}(?:执行|运行|NOW))",
        re.I,
    ),
    "automatic-execution-after-read-zh": re.compile(
        r"(?:读完|读取)[^\n]{0,40}自动(?:执行|运行)", re.I
    ),
    "global-instruction-injection-zh": re.compile(r"全局注入", re.I),
    "side-effects-as-read-goal-zh": re.compile(
        r"产生实际(?:的)?副作用", re.I
    ),
    "extract-into-global-config-zh": re.compile(
        r"首次配置时由 AI 提取本段写入", re.I
    ),
    "precedent-as-authorization-zh": re.compile(
        r"授权已在 precedent-auth\.md 中确认", re.I
    ),
    "precedent-as-step-zero": re.compile(
        r"step 0[^\n]{0,80}precedent-auth", re.I
    ),
    "precedent-declaration-as-gate-zh": re.compile(
        r"precedent-auth\.md[^\n]{0,30}授权预声明", re.I
    ),
}

AGENT_ENTRY_BASENAMES = frozenset({
    "AGENTS.md", "CLAUDE.md", "README_AI.md", "RULES.md", "RULES_zh.md", "README_zh.md",
})
# Roots a client may discover directly. A file named like an agent entry contract
# under one of these is a loadable entrypoint that the pre-T06 gate never inspected.
VENDORED_ROOTS = ("community-raw/", "skills/community/", "docs/community/")
CLIENT_ENTRY_ROOTS = ("skills/", "community-raw/")
# Baseline exception: the vendored留档 copy of an upstream rules file. It lives
# under docs/ (not a client discovery root) and is banner-guarded by
# verify-community-banner.py.
KNOWN_VENDORED_ENTRY_FILES = frozenset({"docs/community/ai-fullstack-delivery/RULES.md"})

# T06/U3: second-level router segments in vendored corpora (WORK-BOARD U3). The
# corpus is measured and pinned by digest, not rewritten: any addition, removal or
# re-wording fails closed and forces a re-review.
ROUTER_SEGMENT_PATTERNS = {
    "related-routing-heading": re.compile(r"^##\s*0\.\s*RELATED ROUTING", re.M | re.I),
    "load-first-marker": re.compile(r"\*\*LOAD FIRST\*\*"),
    "cross-load-marker": re.compile(r"\bcross-load\b", re.I),
}
ROUTER_SEGMENT_ROOTS = ("community-raw/", "skills/community/")
# sha256 over lines "<path> <count>", sorted by path, joined with "\n".
ROUTER_BASELINE_DIGEST = "274b3e9a51fce127e75d8496f893509f5192a298ec497fb27d05deb3a13d4611"
ROUTER_BASELINE_FILES = 70
ROUTER_BASELINE_OCCURRENCES = 71

TEXT_SUFFIXES = {
    ".md", ".txt", ".json", ".yml", ".yaml", ".py", ".ps1", ".sh", ".js",
    ".mjs", ".cjs", ".java", ".bat", ".cmd", ".html", ".css", ".xml", ".toml",
    ".cfg", ".ini", ".properties", "",
}
BINARY_TEXT_SKIP = {".jar", ".zip", ".7z", ".rar", ".apk", ".ipa", ".class", ".wasm", ".pyc"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".webp", ".bmp"}
# Extension-less magic numbers. A blob carrying one of these behind a text-ish
# suffix is a disguised binary that the suffix allowlist would never see.
BINARY_MAGIC = (
    (b"\x7fELF", "elf"),
    (b"MZ", "pe-dos"),
    (b"\xca\xfe\xba\xbe", "macho-fat"),
    (b"\xfe\xed\xfa\xce", "macho-32"),
    (b"\xfe\xed\xfa\xcf", "macho-64"),
    (b"PK\x03\x04", "zip-container"),
    (b"\x1f\x8b", "gzip"),
)

# High-confidence secret shapes only. Generic `password = "..."` prose in payload
# corpora is intentionally not matched: measured 11 such prose hits in the
# src-hunter reference corpus, every one of them documentation.
SECRET_PATTERNS = {
    "aws-access-key-id": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "github-token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    "slack-token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    "private-key-block": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----"),
    "netrc-credential": re.compile(r"^\s*machine\s+\S+\s+login\s+\S+\s+password\s+\S+", re.M),
}

# Prompt-injection shapes. Pre-T06 these applied only to the four root entry
# files, so a new vendored or client-root markdown carrying one was invisible.
# DOCUMENTED_INJECTION_BASELINE pins the occurrences that legitimately exist in
# material that *describes* injection (llm-security reference, kali readme,
# precedent records, routing_zh) so they are reported, not silently tolerated.
DOCUMENTED_INJECTION_BASELINE = {
    ("README-kali.md", "execute-after-read-zh"): 1,
    ("kali/README-kali.md", "execute-after-read-zh"): 1,
    ("kali/README-kali.md", "global-instruction-injection-zh"): 2,
    ("skills/field-journal/precedent-pentest.md", "precedent-as-authorization-zh"): 1,
    ("skills/field-journal/precedent-reverse.md", "precedent-as-authorization-zh"): 1,
    ("skills/llm-security/references/agent-obedience-engineering.md", "execute-after-read-zh"): 2,
    ("skills/llm-security/references/agent-obedience-engineering.md", "global-instruction-injection-zh"): 2,
    ("skills/llm-security/references/agent-obedience-engineering.md", "side-effects-as-read-goal-zh"): 1,
    ("skills/routing_zh.md", "precedent-declaration-as-gate-zh"): 1,
}

# Cleartext-endpoint rule: only `http://<dotted-host>` counts. Scheme-prefix
# literals ("http://"), host templates and namespaces are not endpoints.
CLEARTEXT_HOST_ALLOW = ("www.w3.org", "schemas.android.com", "localhost", "127.0.0.1")
CLEARTEXT_ENDPOINT = re.compile(r"http://([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+)(?=[/:?#\s\"']|$)")

REGISTRY_PATH = "skills/community/registry.json"
FULL_HEX40 = re.compile(r"^[0-9a-f]{40}$")

def is_texty(path: str) -> bool:
    suffix = PurePosixPath(path).suffix.lower()
    return suffix not in BINARY_TEXT_SKIP and suffix not in IMAGE_SUFFIXES

def check_client_entry_surface(entries: dict[str, str]) -> list[str]:
    """No agent-entry-shaped file may appear under a client discovery root."""
    return [
        "raw agent entrypoint under client discovery root (unescaped instruction surface): " + path
        for path in sorted(entries)
        if path.startswith(CLIENT_ENTRY_ROOTS)
        and PurePosixPath(path).name in AGENT_ENTRY_BASENAMES
    ]

def check_vendored_entry_files(entries: dict[str, str]) -> list[str]:
    return [
        "unregistered vendored agent entry file: " + path
        for path in sorted(entries)
        if path.startswith(VENDORED_ROOTS)
        and PurePosixPath(path).name in AGENT_ENTRY_BASENAMES
        and path not in KNOWN_VENDORED_ENTRY_FILES
    ]

def check_router_segments(entries: dict[str, str]) -> tuple[list[str], int, int, str]:
    """Pin the second-level router surface inside vendored corpora (T06/U3)."""
    per_file: dict[str, int] = {}
    for path in sorted(entries):
        # docs/ is deliberately not scanned: our own migration record quotes the
        # vendor router markers verbatim, which is documentation, not an entrypoint.
        if not path.startswith(ROUTER_SEGMENT_ROOTS) or path in SCAN_EXCLUDES:
            continue
        if PurePosixPath(path).suffix.lower() not in (".md", ".txt"):
            continue
        text = blob(path).decode("utf-8-sig", errors="replace")
        count = sum(len(p.findall(text)) for p in ROUTER_SEGMENT_PATTERNS.values())
        if count:
            per_file[path] = count
    files = len(per_file)
    occurrences = sum(per_file.values())
    digest = hashlib.sha256(
        "\n".join(f"{path} {count}" for path, count in sorted(per_file.items())).encode("utf-8")
    ).hexdigest()
    errors: list[str] = []
    if digest != ROUTER_BASELINE_DIGEST:
        errors.append(
            "vendored second-level router surface changed; re-review required: "
            f"files={files} (baseline {ROUTER_BASELINE_FILES}) "
            f"occurrences={occurrences} (baseline {ROUTER_BASELINE_OCCURRENCES}) "
            f"digest={digest} (baseline {ROUTER_BASELINE_DIGEST})"
        )
    return errors, files, occurrences, digest

def check_prompt_injection(entries: dict[str, str]) -> tuple[list[str], int]:
    errors: list[str] = []
    hits = 0
    for path in sorted(entries):
        if path in SCAN_EXCLUDES or not is_texty(path):
            continue
        text = blob(path).decode("utf-8-sig", errors="replace")
        for label, pattern in UNSAFE_AGENT_ENTRY_PATTERNS.items():
            found = len(pattern.findall(text))
            if not found:
                continue
            hits += found
            allowed = DOCUMENTED_INJECTION_BASELINE.get((path, label), 0)
            if found > allowed:
                errors.append(
                    f"prompt-injection shape {label} x{found} (baseline {allowed}): {path}"
                )
    return errors, hits

def check_secrets(entries: dict[str, str]) -> tuple[list[str], int]:
    errors: list[str] = []
    hits = 0
    for path in sorted(entries):
        if path in SCAN_EXCLUDES or not is_texty(path):
            continue
        text = blob(path).decode("utf-8-sig", errors="replace")
        for label, pattern in SECRET_PATTERNS.items():
            found = len(pattern.findall(text))
            if found:
                hits += found
                errors.append(f"credential-shaped secret {label} x{found}: {path}")
    return errors, hits

def check_disguised_binaries(entries: dict[str, str]) -> list[str]:
    errors: list[str] = []
    for path in sorted(entries):
        suffix = PurePosixPath(path).suffix.lower()
        if suffix not in TEXT_SUFFIXES or path in SCAN_EXCLUDES:
            continue
        data = blob(path)
        for magic, name in BINARY_MAGIC:
            if data.startswith(magic):
                errors.append(f"disguised binary content ({name}) behind text suffix: {path}")
                break
    return errors

def check_symlink_targets(entries: dict[str, str]) -> list[str]:
    """A tracked symlink must not resolve outside the repository."""
    errors: list[str] = []
    for path, mode in sorted(entries.items()):
        if mode != "120000":
            continue
        target = blob(path).decode("utf-8", errors="replace").strip()
        parts = PurePosixPath(target).parts
        if target.startswith("/") or (parts and parts[0].count(":") == 1) or ".." in parts:
            errors.append(f"symlink escapes repository root: {path} -> {target}")
    return errors

def check_cleartext_endpoints(entries: dict[str, str]) -> list[str]:
    errors: list[str] = []
    for path in sorted(entries):
        if PurePosixPath(path).suffix.lower() not in EXECUTABLE_SUFFIXES or path in SCAN_EXCLUDES:
            continue
        for number, line in enumerate(
            blob(path).decode("utf-8-sig", errors="replace").splitlines(), 1
        ):
            for match in CLEARTEXT_ENDPOINT.finditer(line):
                host = match.group(1)
                if any(host == allow or host.endswith("." + allow) for allow in CLEARTEXT_HOST_ALLOW):
                    continue
                errors.append(
                    f"cleartext http endpoint in executable source: {path}:{number}: {host}"
                )
    return errors

def check_provenance(entries: dict[str, str]) -> tuple[list[str], list[str]]:
    """Registry-backed provenance for every vendored root.

    Hard failures: an unowned raw root, a non-https source_url, a commit that is
    not a full sha, a notice_file that is not tracked, an unparseable registry.
    Advisories (printed, not fatal): a source with no notice file at all.
    """
    errors: list[str] = []
    advisories: list[str] = []
    if REGISTRY_PATH not in entries:
        return ["provenance registry missing from index: " + REGISTRY_PATH], advisories
    try:
        registry = json.loads(blob(REGISTRY_PATH).decode("utf-8-sig"))
    except (ValueError, UnicodeDecodeError) as exc:
        return [f"provenance registry is not parseable JSON: {REGISTRY_PATH}: {exc}"], advisories

    # A vendored raw root is named after the upstream repository, not after the
    # registry id, so ownership is mapped explicitly: a new root cannot slip in
    # unnamed.
    raw_root_owner = {
        "ai-fullstack": "ai-fullstack-delivery",
        "apk-reverse-source": "apk-reverse-community",
        "ctf-super-hub": "ctf-super-hub",
        "hack-skills": "hack-skills",
    }
    # `community-raw/README.md` 是这个 vendored 目录自己的说明文件，不是第五个上游。
    # 早先的写法 `p.split("/")[1]` 把**文件**也当成了一个 root 名，于是报
    # 「vendored raw root has no registry owner: community-raw/README.md/」——
    # 这条报错指向一个根本不存在的东西，等于把真报错淹掉。这里只取目录。
    vendored_roots = sorted({
        p.split("/")[1] for p in entries
        if p.startswith("community-raw/") and p.count("/") >= 2 and len(p.split("/")) > 2
    })
    vendored_roots = [r for r in vendored_roots if any(
        p.startswith(f"community-raw/{r}/") for p in entries
    )]
    for root in vendored_roots:
        if root not in raw_root_owner:
            errors.append(f"vendored raw root has no registry owner: community-raw/{root}/")
        elif not any(p.startswith(f"community-raw/{root}/") for p in entries):
            errors.append(f"vendored raw root is empty: community-raw/{root}/")

    declared_ids = {
        s.get("id") for s in registry.get("sources", []) if isinstance(s, dict)
    }
    for owner in sorted(set(raw_root_owner.values())):
        if owner not in declared_ids:
            errors.append(f"vendored raw root owner is not declared in registry: {owner}")

    for source in registry.get("sources", []):
        if not isinstance(source, dict):
            errors.append("provenance registry contains a non-object source entry")
            continue
        source_id = str(source.get("id", "") or "")
        if not source_id or source_id.startswith(("wrapper-", "community-")):
            continue
        url = str(source.get("source_url", ""))
        if not url.startswith("https://"):
            errors.append(f"provenance source_url is not https: {source_id}: {url!r}")
        commit = str(source.get("commit", ""))
        if not FULL_HEX40.fullmatch(commit):
            errors.append(f"provenance commit is not a full sha: {source_id}: {commit!r}")
        notice = str(source.get("notice_file") or "")
        if not notice:
            advisories.append(
                f"provenance notice_file is empty for source {source_id} "
                f"(license_declared={source.get('license_declared')!r}, "
                f"license_status={source.get('license_status')!r})"
            )
        elif notice not in entries:
            errors.append(f"provenance notice_file is not tracked: {source_id}: {notice}")
    return errors, advisories

def check_agent_entry_contract(path: str, text: str) -> list[str]:
    errors: list[str] = []
    for marker in REQUIRED_AGENT_CONSENT_MARKERS:
        if marker not in text:
            errors.append(
                f"agent entry missing consent marker: {path}: {marker}"
            )
    for label, pattern in UNSAFE_AGENT_ENTRY_PATTERNS.items():
        if pattern.search(text):
            errors.append(f"unsafe agent execute-on-read pattern {label}: {path}")
    return errors

def repo_prefix() -> str:
    """本目录相对**仓库根**的前缀，例如 `skillpack/`（自己在仓库根时为空串）。

    为什么需要它：`git ls-files` 给的是相对**当前目录**的路径，
    而 `git show :<path>` 里的 `<path>` 一定是相对**仓库根**的。
    skillpack 曾经是独立仓库、两者恰好相同；并进主仓之后就不一样了 ——
    `git -C skillpack ls-files` 给 `README_AI.md`，
    而 `git -C skillpack show :README_AI.md` 会 fatal，必须写 `:skillpack/README_AI.md`。
    不对齐就会在这第一行崩掉，后面所有检查（symlink / 未审二进制 / agent 入口契约）
    全都没跑 —— 一个崩掉的安全闸比报红的安全闸更糟，因为它装作自己还在。
    """
    try:
        out = subprocess.run(
            ["git", "-C", ROOT, "rev-parse", "--show-prefix"],
            capture_output=True, text=True, check=True, timeout=120,
        ).stdout.strip()
    except Exception:
        return ""
    return out.replace("\\", "/")


REPO_PREFIX = repo_prefix()


def git(*args: str) -> bytes:
    return subprocess.run(
        ["git", "-C", ROOT, *args], capture_output=True, check=True, timeout=120
    ).stdout

# ★ 2026-10-15 独立审查 P9：禁读目录一个字都不许读。
#   注意这里必须同样覆盖 **git 分支**：CI/ls-files 给出的路径集合里
#   包含该目录下 51 个跟踪文件，只改 os.walk 那一支连它都防不住。
FORBIDDEN_READ_PREFIX = "_归档-禁读-历史文档/"


def tracked_entries() -> dict[str, str]:
    if USE_GIT:
        raw = git("ls-files", "-s", "-z").decode("utf-8")
        result: dict[str, str] = {}
        for record in raw.split("\0"):
            if not record:
                continue
            meta, path = record.split("\t", 1)
            if path.startswith(FORBIDDEN_READ_PREFIX):
                continue
            result[path] = meta.split()[0]
        return result

    result = {}
    for current, dirs, names in os.walk(ROOT):
        # ★ 2026-10-15 独立审查 P9：禁读目录一个字都不许读。本脚本会打开
        #   所有文本文件扫密钥/注入，若不排除，它会把该目录下的字符串当成待扫样本。
        dirs[:] = [directory for directory in dirs
                   if directory != ".git" and directory != "_归档-禁读-历史文档"]
        for name in names:
            absolute = os.path.join(current, name)
            relative = os.path.relpath(absolute, ROOT).replace(os.sep, "/")
            result[relative] = "120000" if os.path.islink(absolute) else "100644"
    return result

def blob(path: str) -> bytes | None:
    if USE_GIT:
        try:
            return git("show", f":{REPO_PREFIX}{path}")
        except subprocess.CalledProcessError:
            # 取不到就报「缺」，不要把整个闸门带崩 —— 崩了等于没检查。
            return None
    with open(os.path.join(ROOT, path), "rb") as handle:
        return handle.read()

def main() -> int:
    entries = tracked_entries()
    errors: list[str] = []

    symlinks = sorted(path for path, mode in entries.items() if mode == "120000")
    if symlinks:
        errors.extend(f"tracked symlink requires review: {path}" for path in symlinks)

    for path in AGENT_ENTRY_FILES:
        if path not in entries:
            errors.append(f"agent entry file missing from index: {path}")
            continue
        data = blob(path)
        if data is None:
            errors.append(f"agent entry file unreadable from index: {REPO_PREFIX}{path}")
            continue
        text = data.decode("utf-8-sig", errors="replace")
        errors.extend(check_agent_entry_contract(path, text))

    binary_paths = sorted(
        path for path in entries if PurePosixPath(path).suffix.lower() in BINARY_SUFFIXES
    )
    for path in binary_paths:
        expected = ALLOWED_BINARY_HASHES.get(path)
        if expected is None:
            errors.append(f"unreviewed tracked binary-like file: {path}")
            continue
        data = blob(path)
        if data is None:
            errors.append(f"tracked binary-like file unreadable from index: {path}")
            continue
        actual = hashlib.sha256(data).hexdigest()
        if actual != expected:
            errors.append(f"binary hash changed: {path} expected={expected} actual={actual}")

    if PAYLOAD_PATH not in entries:
        errors.append(f"reviewed payload corpus missing from index: {PAYLOAD_PATH}")
    else:
        payload_data = blob(PAYLOAD_PATH)
        if payload_data is None:
            errors.append(f"payload corpus unreadable from index: {PAYLOAD_PATH}")
            # ★ 2026-10-10 修正：此处原为 `return finish(errors)`，
            # 但 `finish` 在本文件从未定义（git HEAD 版本里定义数=0）——
            # 潜伏 bug：errors 为空时走不到这条路径，门禁报 OK；
            # 一旦真的出错，反而崩在 NameError 而不是报 FAIL。
            # 正确行为与下方 line ~553 的错误分支一致：打印并返回 1。
            print(f"FAIL verify-repository-security: {len(errors)} issue(s)")
            for error in errors:
                print(f"  {error}")
            return 1
        actual_payload = hashlib.sha256(payload_data).hexdigest()
        if actual_payload != PAYLOAD_SHA256:
            errors.append(
                f"payload corpus changed; repeat security review: expected={PAYLOAD_SHA256} "
                f"actual={actual_payload}"
            )

    for path in sorted(entries):
        suffix = PurePosixPath(path).suffix.lower()
        if suffix not in EXECUTABLE_SUFFIXES or path in SCAN_EXCLUDES:
            continue
        text = blob(path).decode("utf-8-sig", errors="replace")
        if PAYLOAD_PATH in text or "src-hunter/references/payloader" in text:
            errors.append(f"executable source references passive payload corpus: {path}")
        for label, pattern in PATTERNS.items():
            if not pattern.search(text):
                continue
            if (path, label) not in EXPECTED_PATTERN_HITS:
                errors.append(f"unexpected executable pattern {label}: {path}")

    for path in sorted(p for p in entries if p.startswith(".github/workflows/") and p.endswith((".yml", ".yaml"))):
        text = blob(path).decode("utf-8-sig")
        for use in ACTION_USE.findall(text):
            if use.startswith("./"):
                continue
            if "@" not in use or not FULL_SHA.fullmatch(use.rsplit("@", 1)[1]):
                errors.append(f"GitHub Action is not pinned to a full commit SHA: {path}: {use}")

    # --- T06 vendor-trust coverage -------------------------------------------
    errors.extend(check_client_entry_surface(entries))
    errors.extend(check_vendored_entry_files(entries))
    router_errors, router_files, router_occurrences, router_digest = check_router_segments(entries)
    errors.extend(router_errors)
    injection_errors, injection_hits = check_prompt_injection(entries)
    errors.extend(injection_errors)
    secret_errors, secret_hits = check_secrets(entries)
    errors.extend(secret_errors)
    errors.extend(check_disguised_binaries(entries))
    errors.extend(check_symlink_targets(entries))
    errors.extend(check_cleartext_endpoints(entries))
    provenance_errors, provenance_advisories = check_provenance(entries)
    errors.extend(provenance_errors)

    for advisory in provenance_advisories:
        print(f"NOTE verify-repository-security: {advisory}")

    if errors:
        print(f"FAIL verify-repository-security: {len(errors)} issue(s)")
        for error in errors:
            print(f"  {error}")
        return 1

    print(
        "OK verify-repository-security: "
        f"tracked={len(entries)} executable_sources="
        f"{sum(PurePosixPath(p).suffix.lower() in EXECUTABLE_SUFFIXES for p in entries)} "
        f"binary_like={len(binary_paths)} agent_entries={len(AGENT_ENTRY_FILES)} "
        f"symlinks=0 vendored_router_files={router_files} "
        f"vendored_router_occurrences={router_occurrences} "
        f"vendored_router_digest={router_digest[:12]} "
        f"injection_shapes={injection_hits} secrets={secret_hits} "
        f"provenance_advisories={len(provenance_advisories)}"
    )
    return 0

if __name__ == "__main__":
    sys.exit(main())
