#!/usr/bin/env python3
"""test-routing-correctness.py —— 路由**正确性**基准（与漂移基准分开）。

为什么要有它：
    `test-routing-natural.ps1` 读的 `routing-benchmark-natural.json` 里
    `primary == expect` **93/93** —— `primary` 是路由器的输出，`expect` 也是。
    那个基准只能证明"路由没变"，**证明不了"路由是对的"**。
    本脚本读 `routing-benchmark-correctness.json`，`expect` 全部人工标注，
    跑真路由比对；红就是红，不许调 expect 去凑绿。

用法：
    python skills/tests/test-routing-correctness.py
    python skills/tests/test-routing-correctness.py --json
退出码：0 全对 / 1 有错（错就是路由该改，不是基准该改）
"""
import argparse, json, os, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILLS = HERE.parent
REPO = SKILLS.parent.parent
BENCH = HERE / "routing-benchmark-correctness.json"
ROUTER = SKILLS / "scripts" / "master-route.ps1"


def run_route(hint):
    out = tempfile.mkdtemp(prefix="routectl-")
    p = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                        "-File", str(ROUTER), "-Hint", hint, "-OutDir", out],
                       capture_output=True, text=True, errors="replace", timeout=180)
    primary, label, conf = None, None, None
    for ln in (p.stdout or "").splitlines():
        s = ln.strip()
        if s.startswith("PRIMARY ->"):
            path = s.split("->", 1)[1].strip()
            primary = Path(path.replace("\\", "/")).parent.name
        elif s.startswith("Label:"):
            parts = s.split("|")
            label = parts[0].replace("Label:", "").strip()
            for q in parts[1:]:
                if "confidence:" in q:
                    conf = q.split("confidence:")[1].strip()
    return primary, label, conf, p.returncode


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    doc = json.loads(BENCH.read_text(encoding="utf-8"))
    cases = doc["cases"]
    rows, bad = [], 0
    for c in cases:
        got, label, conf, rc = run_route(c["hint"])
        ok = (got or "").lower() == c["expect"].lower()
        if not ok:
            bad += 1
        rows.append({"hint": c["hint"], "expect": c["expect"], "got": got,
                     "label": label, "confidence": conf, "ok": ok,
                     "why": c.get("note", "")})
    if a.json:
        print(json.dumps({"total": len(cases), "failed": bad, "rows": rows},
                         ensure_ascii=False, indent=2))
    else:
        print("路由正确性基准：%d 条，对 %d，错 %d" % (len(cases), len(cases) - bad, bad))
        for r in rows:
            print("  [%s] %s" % ("OK  " if r["ok"] else "FAIL", r["hint"]))
            print("        expect=%s  got=%s (%s, %s)" % (r["expect"], r["got"], r["label"], r["confidence"]))
            if not r["ok"]:
                print("        为什么该去 %s：%s" % (r["expect"], r["why"]))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
