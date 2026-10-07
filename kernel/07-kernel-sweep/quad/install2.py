# -*- coding: utf-8 -*-
"""Install the pure English kernels as the live pool, park everything else.

Deliverable layout after this runs:
  04-console/cards/base/<model>.md      the pure-prompt kernel (English, activation `你是谁`)
  04-console/cards/_park/*              every previous card (zh / old en / v7) moved out of the pool

Usage: python quad/install2.py [--dry-run]
"""
import io, os, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CARDS_ROOT = os.environ.get("HUBCORE_CARDS") or os.path.join(
    os.path.dirname(ROOT), "04-console", "cards")
BASE = os.path.join(CARDS_ROOT, "base")
PARK = os.path.join(CARDS_ROOT, "_park")
BUDGET = 40000

MAP = {
    "en2-gemini.md": "gemini-3.8-flash-high.md",
    "en2-mimo.md": "mimo-2.6.md",
    "en2-muse.md": "muse-1.3.md",
    "en2-spacebunny.md": "space-bunny.md",
}

# pool entries that are superseded by this install
PARK_OLD = [
    "gemini-3.8-flash-high-en.md", "mimo-2.6-en.md", "muse-1.3-en.md", "space-bunny-en.md",
    "claude-4.6.md", "deepseek-flash+v4-pro.md",
]

def header_of(text):
    lines = text.splitlines()
    hdr = [l for l in lines[:4] if l.startswith("#")]
    body = "\n".join(lines[len(hdr):]).lstrip("\n")
    return "\n".join(hdr) + "\n\n", body

def main():
    dry = "--dry-run" in sys.argv
    os.makedirs(PARK, exist_ok=True)
    over = []
    for src, dst in sorted(MAP.items()):
        text = io.open(os.path.join(HERE, src), encoding="utf-8").read()
        head, body = header_of(text)
        out = head + body.rstrip("\n") + "\n"
        n = len(out.encode())
        if n > BUDGET:
            over.append((dst, n))
        print("%-22s -> base/%-28s %6d B  %s" % (
            src, dst, n, "OVER BUDGET" if n > BUDGET else "%d left" % (BUDGET - n)))
        if not dry:
            io.open(os.path.join(BASE, dst), "w", encoding="utf-8", newline="\n").write(out)
    if not dry:
        for name in PARK_OLD:
            p = os.path.join(BASE, name)
            if os.path.exists(p):
                shutil.move(p, os.path.join(PARK, name))
                print("parked  %s" % name)
    if over:
        raise SystemExit("over budget: %s" % over)

if __name__ == "__main__":
    main()
