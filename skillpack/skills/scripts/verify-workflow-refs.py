#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CI workflow 引用的仓库内文件必须真实存在。

★ 为什么需要这道门禁
  2026-10-10 全项目审查扫 CI 时抓到三处**指向空气的命令**：

      ci.yml:227   bash skillpack/kali/scripts/test-pwntools-discovery.sh
      ci.yml:231   bash skillpack/skills/scripts/test-client-neutral-bootstrap.sh
      macos-bash-compat.yml:42  /bin/bash .../test-client-neutral-bootstrap.sh

  这三个脚本在本仓库**从未存在过**（`git log --all -- <path>` 无任何记录），
  只有 PS 孪生。它们之所以一直没被发现，是因为那些 step 带
  `if: runner.os == 'Linux'` / 只在 macOS runner 上跑 —— Windows 上根本执行不到。
  一句话：**CI 引用一个不存在的文件时，本地什么都看不出来，只有 runner 会红。**

  本门禁把这件事挪到本地：不需要 runner，扫一遍就能发现。

用法
    python verify-workflow-refs.py                # 扫 .github/workflows/*.yml
    python verify-workflow-refs.py --json         # 机读

退出码
    0  全部引用都存在
    1  有引用指向不存在的文件
    2  扫描根不存在
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
# scripts/ -> skills/ -> skillpack/ -> <仓根>
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
WORKFLOWS = os.path.join(REPO, ".github", "workflows")

# run: 行里出现的仓库内脚本/清单；排除 URL 与纯参数
REF_RE = re.compile(r"[\w./-]+\.(?:py|ps1|sh|json|yml|yaml|md|toml|ini|cfg)")

# 这些后缀在 workflow 里是**产物或缓存**，不是仓库里的源文件
GENERATED_SUFFIX = (
    ".log",
    ".out",
    ".tmp",
)


# ★ 2026-10-15 独立审查 P9：`_归档-禁读-历史文档/` 一个字都不许读。
#   本脚本只把这份集合当“路径存在性表”用（不打开正文），但即使如此，
#   把禁读文件的路径当成“可引用目标”也是一种暴露。
#   这里在集合层就剔掉，路径都不取。
FORBIDDEN_PREFIXES = ("_归档-禁读-历史文档/",)


def git_tracked(repo: str) -> set[str]:
    try:
        out = subprocess.run(
            ["git", "-C", repo, "ls-files", "-z"],
            capture_output=True, timeout=120, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return set()
    return {p.decode("utf-8") for p in out.stdout.split(b"\0") if p
            and not p.decode("utf-8").startswith(FORBIDDEN_PREFIXES)}


# ★ 2026-10-17：`run:` 里的**块标量**（`run: |` / `run: >`）以前一个字都没被扫。
#   旧实现用 `re.finditer(r"run:\s*(?:\|)?\s*(.+)", text)`，`(.+)` 只吃同一行 ——
#   于是 ci.yml 里 8 处 `run: |` 块内的引用全部漏检。三条指向
#   `$GITHUB_WORKSPACE/skills/...`（仓库根根本没有 `skills/` 目录）的错路径
#   就是这样长期躺在 CI 里、本地门禁还报绿的。
#   现在按行遍历：命中 `run: |` 就把它后面**缩进更深**的连续行拼成整块一起扫。
_BLOCK_SCALAR_RE = re.compile(r"^(\s*)run:\s*[|>][-+]?\s*$")
_INLINE_RUN_RE = re.compile(r"^\s*run:\s*(?!\|)(?!>)(.+)$")

# `$GITHUB_WORKSPACE/` 在 runner 上就是仓库根，判存在性前必须剥掉。
_WS_PREFIXES = ("${GITHUB_WORKSPACE}/", "$GITHUB_WORKSPACE/", "GITHUB_WORKSPACE/")

# ★ 2026-10-17：块标量一扫，运行期临时路径也进来了。两类**不是仓库引用**的必须剔掉，
#   否则门禁会把 `$scratch/work/x/scope.md` 这种产物断言报成「引用不存在」。
#   ① 前缀是 `$` 的 shell 变量展开（`$scratch/...`、`$caller/...`）——
#      REF_RE 的字符类不含 `$`，所以匹配到的是变量名之后的半截，必须看**匹配位置前一个字符**。
#   ② 仓库根 `work/`（含 `skillpack/work/`）—— 已在 .gitignore，按定义不是源文件；
#      `test ! -e "$GITHUB_WORKSPACE/work/caller-default"` 这类**产物路径断言**就属此列。
_RUNTIME_PREFIXES = ("work/",)


def _collect_line_refs(line: str, found: set[str]) -> None:
    """把一行文本里的仓库内路径引用收进 found（URL 行直接跳过）。"""
    if "http://" in line or "https://" in line:
        return
    for m in REF_RE.finditer(line):
        raw = m.group(0)
        # ① `$var/...`：匹配位置前一个字符是 `$`，且它不是已知的仓库根前缀
        if m.start() > 0 and line[m.start() - 1] == "$" \
                and not raw.startswith(_WS_PREFIXES):
            continue
        p = raw
        for pre in _WS_PREFIXES:
            if p.startswith(pre):
                p = p[len(pre):]
                break
        p = p.lstrip("./")
        # 必须含目录分隔符才像仓库内路径（避免 `foo.py` 这种相对当前目录的）
        if "/" not in p:
            continue
        if p.endswith(GENERATED_SUFFIX):
            continue
        # ② 运行期产物目录
        if p.startswith(_RUNTIME_PREFIXES):
            continue
        found.add(p)


def refs_in(text: str) -> set[str]:
    found: set[str] = set()
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        block = _BLOCK_SCALAR_RE.match(line)
        if block:
            base_indent = len(block.group(1))
            i += 1
            while i < len(lines):
                nxt = lines[i]
                if not nxt.strip():
                    i += 1
                    continue
                indent = len(nxt) - len(nxt.lstrip(" "))
                if indent <= base_indent:
                    break
                _collect_line_refs(nxt, found)
                i += 1
            continue
        inline = _INLINE_RUN_RE.match(line)
        if inline:
            _collect_line_refs(inline.group(1), found)
        i += 1
    return found


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=REPO)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    root = os.path.abspath(args.root)
    wf_dir = os.path.join(root, ".github", "workflows")
    if not os.path.isdir(wf_dir):
        print("FAIL verify-workflow-refs: workflow dir missing: %s" % wf_dir)
        return 2

    tracked = git_tracked(root)
    findings: list[dict[str, str]] = []
    total_refs = 0

    for name in sorted(os.listdir(wf_dir)):
        if not name.endswith((".yml", ".yaml")):
            continue
        wf = os.path.join(wf_dir, name)
        try:
            with open(wf, "r", encoding="utf-8") as handle:
                text = handle.read()
        except OSError as exc:
            findings.append({"workflow": name, "ref": "", "why": str(exc)})
            continue
        for ref in sorted(refs_in(text)):
            total_refs += 1
            norm = ref.replace("\\", "/")
            if norm in tracked:
                continue
            if os.path.isfile(os.path.join(root, norm.replace("/", os.sep))):
                continue
            findings.append({"workflow": name, "ref": norm, "why": "文件不存在"})

    if args.json:
        print(json.dumps({"refs_checked": total_refs,
                          "missing": findings},
                         ensure_ascii=False, indent=1))
        return 1 if findings else 0

    print("verify-workflow-refs: 检查 %d 个 workflow 里的 %d 个仓库内引用"
          % (len([n for n in os.listdir(wf_dir)
                  if n.endswith((".yml", ".yaml"))]), total_refs))
    for f in findings:
        print("  [FAIL] %s -> %s （%s）" % (f["workflow"], f["ref"], f["why"]))
    if findings:
        print("FAIL verify-workflow-refs: %d 个引用指向不存在的文件" % len(findings))
        print("  CI 在本机跑不到这些 step（它们多带 runner.os 条件），")
        print("  只有 runner 会红 —— 所以必须在提交前发现。")
        return 1
    print("OK verify-workflow-refs: 所有引用的文件都存在")
    return 0


if __name__ == "__main__":
    sys.exit(main())