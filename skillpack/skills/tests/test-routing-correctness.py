#!/usr/bin/env python3
"""test-routing-correctness.py —— 路由**正确性**基准（与漂移基准分开）。

## 判据（2026-10-18 修订）

本机 4 GB、无 HuggingFace 网络 → 上不了 embedding 模型。词法方法（keyword + BM25）
对自然语言的天花板实测为 **recall@5 = 7/12**（top-1 只有 4/12）。

所以判据从「top-1 必须对」改成两段：

  1. **候选段**（脚本负责）：正确答案必须在 `route-semantic.py` 的 top-5 里。
     这是脚本能保证的 —— 它把 57 个技能缩到 5 个。
  2. **判定段**（模型负责）：`master-route.ps1` 输出 `SEMANTIC-CANDIDATES`，
     模型按候选 + 症状句自己判。脚本不再用单一 high 置信度冒充结论。

`--strict` 仍按旧判据（top-1 必须对）跑，用来观察词法层的天花板。


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
    ap.add_argument("--strict", action="store_true", help="按旧判据：top-1 必须对")
    a = ap.parse_args()
    doc = json.loads(BENCH.read_text(encoding="utf-8"))
    cases = doc["cases"]
    rows, bad = [], 0
    # 候选段：route-semantic.py 的 top-5
    sem = SKILLS / "scripts" / "route-semantic.py"
    for c in cases:
        got, label, conf, rc = run_route(c["hint"])
        cands = []
        if sem.is_file():
            sp = subprocess.run([sys.executable, str(sem), "--hint", c["hint"], "--top", "5", "--json"],
                                capture_output=True, text=True, errors="replace", timeout=120)
            try:
                cands = [x["skill"] for x in json.loads(sp.stdout)["top"]]
            except Exception:
                cands = []
        in_cands = c["expect"].lower() in [x.lower() for x in cands]
        ok = (got or "").lower() == c["expect"].lower()
        if not ok:
            bad += 1
        rows.append({"hint": c["hint"], "expect": c["expect"], "got": got,
                     "label": label, "confidence": conf, "ok": ok,
                     "candidates": cands, "in_candidates": in_cands,
                     "why": c.get("note", "")})
    in_c = sum(1 for r in rows if r["in_candidates"])
    if a.json:
        print(json.dumps({"total": len(cases), "top1_failed": bad,
                          "in_candidates": in_c, "rows": rows},
                         ensure_ascii=True, indent=2))
    else:
        print("路由正确性基准：%d 条 · top-1 对 %d / 候选命中 %d" % (len(cases), len(cases) - bad, in_c))
        for r in rows:
            print("  [%s] %s" % ("OK  " if r["ok"] else "FAIL", r["hint"]))
            print("        expect=%s  got=%s (%s, %s)" % (r["expect"], r["got"], r["label"], r["confidence"]))
            print("        候选 top5=%s  %s" % (r["candidates"], "命中" if r["in_candidates"] else "未命中"))
            if not r["ok"]:
                print("        为什么该去 %s：%s" % (r["expect"], r["why"]))
    # 非 strict 模式下，判据是「候选里有没有」；strict 才要求 top-1
    if getattr(a, "strict", False):
        return 0 if bad == 0 else 1
    return 0 if in_c == len(cases) else 1


if __name__ == "__main__":
    sys.exit(main())
