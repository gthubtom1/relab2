# -*- coding: utf-8 -*-
"""Install the per-model kernels into the console card pool.

Layout produced:
  04-console/cards/base/<model>.md        <- zh kernel   (the pool slot the console reads)
  04-console/cards/base/<model>-en.md     <- en kernel   (same slot pool, English sessions)

Originals are copied to 07-kernel-sweep/_backup-cards/ on first run.
Card budget is 40000 B per file (the console refuses bigger tiles).
"""
import io, os, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                      # 07-kernel-sweep
CARDS = os.environ.get("HUBCORE_CARDS") or os.path.join(
    os.path.dirname(ROOT), "04-console", "cards", "base")
BACKUP = os.path.join(ROOT, "_backup-cards")
BUDGET = 40000

# quad file -> card file in the pool
MAP = {
    "zh-gemini.md": "gemini-3.8-flash-high.md",
    "zh-mimo.md": "mimo-2.6.md",
    "zh-muse.md": "muse-1.3.md",
    "zh-spacebunny.md": "space-bunny.md",
    "en-gemini.md": "gemini-3.8-flash-high-en.md",
    "en-mimo.md": "mimo-2.6-en.md",
    "en-muse.md": "muse-1.3-en.md",
    "en-spacebunny.md": "space-bunny-en.md",
}

def header_of(text):
    lines = text.splitlines()
    hdr = [l for l in lines[:4] if l.startswith("#")]
    body = "\n".join(lines[len(hdr):]).lstrip("\n")
    return "\n".join(hdr) + "\n\n", body

def main():
    dry = "--dry-run" in sys.argv
    os.makedirs(BACKUP, exist_ok=True)
    over = []
    for src, dst in sorted(MAP.items()):
        sp = os.path.join(HERE, src)
        text = io.open(sp, encoding="utf-8").read()
        head, body = header_of(text)
        out = head + body.rstrip("\n") + "\n"
        dp = os.path.join(CARDS, dst)
        n = len(out.encode())
        old = len(io.open(dp, "rb").read()) if os.path.exists(dp) else 0
        if n > BUDGET:
            over.append((dst, n))
        print("%-30s -> %-30s %6d -> %6d B  %s" % (
            src, dst, old, n, "OVER BUDGET" if n > BUDGET else "%d left" % (BUDGET - n)))
        if dry:
            continue
        b = os.path.join(BACKUP, dst)
        if os.path.exists(dp) and not os.path.exists(b):
            shutil.copy2(dp, b)
        io.open(dp, "w", encoding="utf-8", newline="\n").write(out)
    if over:
        raise SystemExit("over budget: %s" % over)

if __name__ == "__main__":
    main()
