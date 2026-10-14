#!/usr/bin/env python3
"""test-routing-e2e.py —— 端到端路由回归（L2.2 行为门之二）

背景：
    已有的 `test-routing` 跑的是 224 条 (hint, expect) 关键词用例 —— 它验的是
    "路由规则没退化"。它**不验**「一个真实项目的原始请求，会不会被送到正确的入口」。
    这两件事不同：关键词用例是人挑的短句，真实请求是用户原话。

本门拿 `tests/cases/*.yaml` 里的 `task_verbatim`（**用户原话，不改写**）走一遍
`master-route`，检查 PRIMARY（或 `entry_menu`）是否落在该 case 的 `expect_chain` 上。

**不需要模型调用** —— 纯脚本门，可进 CI。

用法：
    python skills/tests/test-routing-e2e.py [--json] [--verbose]
退出码：0 全部命中 / 1 有未命中
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

HERE = os.path.dirname(os.path.abspath(__file__))
SKILLS_ROOT = os.path.dirname(HERE)
CASES_DIR = os.path.join(HERE, "cases")


def find_repo_root() -> str:
    d = HERE
    for _ in range(8):
        if os.path.isdir(os.path.join(d, "skillpack", "skills")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return os.getcwd()


def run_master_route(hint: str) -> dict:
    """跑 master-route，返回解析后的字段。"""
    out = tempfile.mkdtemp(prefix="rs-e2e-")
    try:
        ps = os.path.join(SKILLS_ROOT, "scripts", "master-route.ps1")
        subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps,
             "-Hint", hint, "-OutDir", out],
            capture_output=True, text=True, timeout=180, cwd=SKILLS_ROOT)
        f = os.path.join(out, "route-scope.md")
        if not os.path.isfile(f):
            return {}
        with open(f, encoding="utf-8-sig", errors="replace") as fh:
            txt = fh.read()
        d: dict = {}
        for key in ("primary", "primary_skill", "confidence", "candidates_skills", "entry_menu"):
            m = re.search(rf"^-\s*{key}:\s*(.*)$", txt, re.MULTILINE)
            if m:
                d[key] = m.group(1).strip()
        return d
    finally:
        shutil.rmtree(out, ignore_errors=True)


def chain_targets(case: dict) -> list[str]:
    """把 expect_chain 归一成一组「可接受的技能名」用于宽松匹配。"""
    out = []
    for e in (case.get("expect_chain") or []):
        s = str(e).strip()
        out.append(s)
        out.append(s.split("/")[0])
    return out


def matches(route: dict, case: dict) -> tuple[bool, str]:
    """PRIMARY 或 entry_menu 里任一项命中 expect_chain 即算命中（宽松）。"""
    targets = chain_targets(case)
    primary = (route.get("primary_skill") or "").replace("skills/", "")
    if primary and any(primary == t or primary.startswith(t + "/") or t in primary for t in targets if t):
        return True, f"PRIMARY={primary}"
    for field in ("candidates_skills", "entry_menu"):
        v = route.get(field) or ""
        for item in [x.strip().replace("skills/", "") for x in v.split(",") if x.strip()]:
            if any(item == t or item.startswith(t + "/") or t in item for t in targets if t):
                return True, f"{field} 含 {item}"
    return False, f"PRIMARY={primary or '(none)'} 都不在 expect_chain"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    if yaml is None:
        print("test-routing-e2e: FAIL（需要 PyYAML）")
        return 1
    if not os.path.isdir(CASES_DIR):
        print("test-routing-e2e: PASS (nothing to check —— cases/ 不存在)")
        return 0

    cases = []
    for fn in sorted(os.listdir(CASES_DIR)):
        if fn.endswith((".yaml", ".yml")):
            with open(os.path.join(CASES_DIR, fn), encoding="utf-8-sig") as f:
                doc = yaml.safe_load(f)
            if isinstance(doc, dict):
                doc["_file"] = fn
                cases.append(doc)

    if not cases:
        print("test-routing-e2e: PASS (nothing to check —— cases/ 里没有 case)")
        return 0

    rows, miss = [], []
    for c in cases:
        hint = str(c.get("task_verbatim") or c.get("task") or "")
        if not hint.strip():
            miss.append((c["_file"], "case 没有 task_verbatim"))
            continue
        route = run_master_route(hint)
        if not route:
            miss.append((c["_file"], "master-route 未产出 route-scope.md"))
            continue
        ok, why = matches(route, c)
        rows.append({"case": c["_file"], "ok": ok, "why": why,
                     "primary": route.get("primary"), "confidence": route.get("confidence")})
        if not ok:
            miss.append((c["_file"], why))

    ok_n = sum(1 for r in rows if r["ok"])
    total = len(rows) + len([m for m in miss if "没有 task_verbatim" in m[1] or "未产出" in m[1]])

    if args.json:
        print(json.dumps({"total": total, "ok": ok_n, "misses": miss, "rows": rows},
                         ensure_ascii=False, indent=2))
    else:
        print(f"test-routing-e2e: {ok_n}/{len(rows)} 命中")
        for r in rows:
            if args.verbose or not r["ok"]:
                print(f"  {'PASS' if r['ok'] else 'FAIL'} {r['case']} :: {r['why']}"
                      f"  [primary={r['primary']} conf={r['confidence']}]")
        for f, why in miss:
            if "task_verbatim" in why or "未产出" in why:
                print(f"  ERROR {f} :: {why}")

    return 1 if miss else 0


if __name__ == "__main__":
    raise SystemExit(main())
