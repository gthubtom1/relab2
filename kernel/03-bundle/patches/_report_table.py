#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_report_table.py —— 生成六条线的前后对比表（DEAD-REFS.md / RESULT.md 用）。"""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WF = ["desktop-product", "web-service", "cli-tool", "source-takeover",
      "exe-rebuild", "protocol-automation"]


def run(root: str) -> dict:
    r = subprocess.run([sys.executable, str(HERE / "check_dead_refs.py"),
                        "--root", root, "--json"],
                       capture_output=True, text=True, encoding="utf-8")
    return json.loads(r.stdout)


def main() -> int:
    b = run(str(HERE / "_acceptance" / "hubcore_before"))
    a = run(str(HERE / "_acceptance" / "hubcore_after"))
    hdr = (f"{'线':<21}|{'前 引用':>7}{'前 通过':>7}{'前 指向书':>9}{'前 死链':>7}{'前 写错':>7}"
           f" || {'后 引用':>7}{'后 通过':>7}{'后 指向书':>9}{'后 死链':>7}{'后 写错':>7}")
    print(hdr)
    print("-" * len(hdr))
    for wf in WF:
        f = f"workflows/{wf}.md"
        x = next(r for r in b["per_file"] if r["file"] == f)
        y = next(r for r in a["per_file"] if r["file"] == f)
        print(f"{wf:<21}|{x['total']:>7}{x['ok']:>7}{len(x['methods']):>9}"
              f"{x['dead_link']:>7}{x['loose_method']:>7}"
              f" || {y['total']:>7}{y['ok']:>7}{len(y['methods']):>9}"
              f"{y['dead_link']:>7}{y['loose_method']:>7}")
    print("-" * len(hdr))
    print("前 合计:", b["totals"])
    print("后 合计:", a["totals"])
    print("无书可开  前:", b["gaps"], " 后:", a["gaps"])
    print()
    print("各线指向的方法书（打补丁后）：")
    for wf in WF:
        y = next(r for r in a["per_file"] if r["file"] == f"workflows/{wf}.md")
        print(f"  {wf:<20} ({len(y['methods'])} 本) {', '.join(y['methods'])}")
    print()
    print("docs/ 侧死链（打补丁后应为 0）：")
    docd = [r for r in a["per_file"] if r["file"].startswith("docs/") and r["dead_link"]]
    docl = [r for r in a["per_file"] if r["file"].startswith("docs/") and r["loose_method"]]
    print("  DEAD_LINK:", docd or "无", " LOOSE_METHOD:", docl or "无")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
