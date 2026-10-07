#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T19: assert no executable auto-install / auto-network inducement in canonical docs.

Scope (write-scope files only, per T19 card):
  docs/ARCHITECTURE.md, root README*.md, RULES*.md (incl. kali/RULES-kali.md),
  kali/README-kali.md, skills/**/SKILL.md,
  docs/community/ai-fullstack-delivery/`TOOLS.md`

A line FAILS only when it contains an inducement pattern AND none of the
exemption tokens on the same line. Exemptions cover: plan+approval gating,
negations ("do not auto-install"), failure handling ("auto-install failed,
stop retrying"), historical/CI narration, and behavior-chain internal calls.
Exit 0 = clean, exit 1 = violations listed.
"""

import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

INDUCEMENT = re.compile(
    "自动安装|自动下载|自动联网|自动尝试安装|自动调用|自动补齐|"
    "缺少工具时自动|缺工具时自动|"
    "读完后"  # split across lines so this detector source never
    "立即执行|"  # carries the contiguous after-read execution shape itself
    "一键安装|一键配齐|一键配置|一键检查|一键全家桶"
)

EXEMPT = re.compile(
    "批准|获批|approval|显式|autoInstall=false|"
    "不要|禁止|不得|不会|不提供|失败|无法完成|不能完成|不是|不构成|"
    "停止重试|不再重试|自动调用本 skill|"
    "fail|Fail|cannot|NOT|without|stop retrying"
)

def scan_files():
    files = [os.path.join(ROOT, "docs", "ARCHITECTURE.md")]
    files += sorted(glob.glob(os.path.join(ROOT, "README*.md")))
    files += sorted(glob.glob(os.path.join(ROOT, "RULES*.md")))
    files += [
        os.path.join(ROOT, "kali", "README-kali.md"),
        os.path.join(ROOT, "kali", "RULES-kali.md"),
    ]
    files += sorted(glob.glob(os.path.join(ROOT, "skills", "**", "SKILL.md"), recursive=True))
    files += [
        os.path.join(
            ROOT, "docs", "community", "ai-fullstack-delivery", "`TOOLS.md`"
        )
    ]
    return [f for f in files if os.path.isfile(f)]

def main():
    extra = sys.argv[1:]
    files = scan_files() + [a for a in extra if os.path.isfile(a)]
    violations = []
    scanned = 0
    for path in files:
        with open(path, encoding="utf-8") as fh:
            for no, line in enumerate(fh, 1):
                text = line.rstrip("\n")
                if INDUCEMENT.search(text) and not EXEMPT.search(text):
                    violations.append(
                        "%s:%d: %s"
                        % (os.path.relpath(path, ROOT), no, text.strip()[:160])
                    )
        scanned += 1
    print("scanned-files=%d violations=%d" % (scanned, len(violations)))
    for v in violations:
        print("VIOLATION " + v)
    return 1 if violations else 0

if __name__ == "__main__":
    sys.exit(main())
