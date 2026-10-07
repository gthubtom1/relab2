# -*- coding: utf-8 -*-
"""卡片归位：把 cards/ 根目录（或 _park/）里卡头合法的卡，按 `# kind:` 挪进 hub/ base/ guest/。

    python 卡片归位.py            真挪，挪完把结果列出来
    python 卡片归位.py --dry-run  只报要挪什么，一个文件都不动

规则和 server.py 一致：只有三个子夹会被控制台读，池子外面全是停车位。
卡头认不出来的留在原地（不动主人的文件），只报给你看。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CARDS = HERE / "cards"
POOLS = ("hub", "base", "guest")

def kind_of(text: str) -> str:
    for line in text.replace("\r\n", "\n").split("\n")[:4]:
        m = re.match(r"^#\s*kind\s*:\s*(\S+)\s*$", line.strip())
        if m:
            return m.group(1).strip().lower()
    return ""

def sweep(dry_run: bool) -> int:
    if not CARDS.is_dir():
        print("没有 cards/ 目录：%s" % CARDS)
        return 1
    plan = []
    for src in sorted(list(CARDS.glob("*.md")) + list((CARDS / "_park").glob("*.md"))):
        try:
            kind = kind_of(src.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError) as exc:
            print("跳过（读不出来）：%s（%s）" % (src.name, exc))
            continue
        if kind not in POOLS:
            print("留在原地（卡头认不出是哪一层）：%s" % src.name)
            continue
        dst = CARDS / kind / src.name
        if dst.exists():
            print("留在原地（%s/ 里已经有同名的了）：%s" % (kind, src.name))
            continue
        plan.append((src, dst, kind))
    if not plan:
        print("没有要挪的卡。三个池子：hub/ base/ guest/。")
        return 0
    for src, dst, kind in plan:
        if dry_run:
            print("[试运行] %s  ->  %s/%s" % (src.name, kind, src.name))
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            src.replace(dst)
            print("%s  ->  %s/%s" % (src.name, kind, src.name))
    print("---- %s %d 张" % ("会挪" if dry_run else "挪完", len(plan)))
    return 0

if __name__ == "__main__":
    sys.exit(sweep("--dry-run" in sys.argv[1:]))
