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


def refs_in(text: str) -> set[str]:
    found: set[str] = set()
    for m in re.finditer(r"run:\s*(?:\|)?\s*(.+)", text):
        line = m.group(1)
        if "http://" in line or "https://" in line:
            continue
        for raw in REF_RE.findall(line):
            p = raw.lstrip("./")
            # 必须含目录分隔符才像仓库内路径（避免 `foo.py` 这种相对当前目录的）
            if "/" not in p:
                continue
            if p.endswith(GENERATED_SUFFIX):
                continue
            found.add(p)
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