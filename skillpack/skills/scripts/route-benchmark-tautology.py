# -*- coding: utf-8 -*-
"""route-benchmark-tautology.py —— 量化「路由基准是不是自己出题自己考」（P6）。

背景：docs/KNOWN-BOUNDARIES.md 第 9 节第 3 条原来写着
  「路由基准 227 条里 223 条（98.24%）的问句就是被测关键词拼的」
这个数字没有任何人给出算法。本轮独立审查用两种可复现定义分别得 24.67% / 60.79%
（修正中文分词后的值；修正则前的旧实现把中文拆成单字后再丢弃，
中文 2-gram 从未生效，那两版数字都作废）。

定义（本脚本唯一口径，改判据就改这里）：
  一条用例 h→R 判为「自证」（tautological），当且仅当：
    h 的 token 里 ≥90% 出现在 R 的 must/mustAll 正则词项表中。
  token 口径：
    · 英文/数字：长度 **≥4** 的连续串（短词如 app / get / cve 判据力太低）
    · 中文：连续中文串切 **2-gram**（单字不构成判据）
  另给一个更宽的口径「any-term」：h 里出现 R 的任一词项即算。
  两个数字都打印，避免单一口径被挑刺。

用法：
  python route-benchmark-tautology.py            # 人类可读
  python route-benchmark-tautology.py --json
退出码：0（这是统计，不是门禁）
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
SKILLS = os.path.dirname(HERE)
BENCH = os.path.join(SKILLS, "tests", "routing-benchmark.json")
ROUTING = os.path.join(SKILLS, "config", "routing.json")

RUN_RE = re.compile(r"[a-z0-9]+|[\u4e00-\u9fff]+")
EN_MIN = 4


def is_cjk(s: str) -> bool:
    return any('\u4e00' <= c <= '\u9fff' for c in s)


def tokens(text: str):
    """英文取 ≥4 的连续串；中文连续串切 2-gram。"""
    out = []
    for w in RUN_RE.findall(text.lower()):
        if is_cjk(w):
            if len(w) < 2:
                continue
            out.extend(w[i:i + 2] for i in range(len(w) - 1))
        elif len(w) >= EN_MIN:
            out.append(w)
    return out


def route_terms(route):
    """把一条路由的全部 must/mustAll 正则拆成词项表（与 token 口径一致）。"""
    terms = set()
    for kw in route.get("keywords", []):
        for key in ("must", "mustAll"):
            v = kw.get(key)
            if not v:
                continue
            for one in (v if isinstance(v, list) else [v]):
                for w in re.split(r"[|()\[\]{}^$*+?.\\<>=\-!]", str(one)):
                    w = w.strip()
                    if not w:
                        continue
                    if is_cjk(w):
                        if len(w) >= 2:
                            terms.add(w.lower())
                            terms.update(w[i:i + 2] for i in range(len(w) - 1))
                    elif len(w) >= EN_MIN:
                        terms.add(w.lower())
    return terms


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    bench = json.load(io.open(BENCH, encoding="utf-8-sig"))
    routing = json.load(io.open(ROUTING, encoding="utf-8-sig"))
    routes = routing["routes"]
    cases = bench["cases"]

    strict = any_term = total = 0
    per_route = {}
    untagged = 0
    for c in cases:
        if c.get("source") == "real-utterance-yg":
            continue
        untagged += 1
        rid = c.get("expect")
        r = routes.get(rid)
        if not r:
            continue
        terms = route_terms(r)
        if not terms:
            continue
        ts = tokens(c.get("hint", ""))
        if not ts:
            continue
        total += 1
        cov = sum(1 for t in ts if t in terms)
        if cov / len(ts) >= 0.90:
            strict += 1
            per_route.setdefault(rid, [0, 0])[0] += 1
        per_route.setdefault(rid, [0, 0])[1] += 1
        if any(t in terms for t in ts):
            any_term += 1

    real = len([c for c in cases if c.get("source") == "real-utterance-yg"])
    out = {
        "benchmark_cases": len(cases),
        "real_utterance_yg": real,
        "non_tagged": untagged,
        "measured": total,
        "strict_coverage_ge_90pct": strict,
        "strict_pct": round(100.0 * strict / total, 2) if total else 0.0,
        "any_term_present": any_term,
        "any_term_pct": round(100.0 * any_term / total, 2) if total else 0.0,
        "worst_routes": [
            {"route": k, "strict": v[0], "total": v[1]}
            for k, v in sorted(per_route.items(),
                               key=lambda kv: -(kv[1][0] / kv[1][1]) if kv[1][1] else 0)
            if v[1] >= 5][:8],
        "definition": "hint tokens (en>=4 chars / CJK 2-grams) with >=90%% in the expected "
                      "route's must/mustAll term table => tautological (own-exam).",
    }
    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print("route benchmark tautology")
        print("  cases             : %d (real-utterance %d, non-tagged %d)"
              % (out["benchmark_cases"], real, untagged))
        print("  measured          : %d" % total)
        print("  strict (>=90%% cov) : %d  = %s%%" % (strict, out["strict_pct"]))
        print("  any-term present  : %d  = %s%%" % (any_term, out["any_term_pct"]))
        print("  definition        : %s" % out["definition"])
        print("  worst routes (>=5 cases):")
        for w in out["worst_routes"]:
            print("    %-6s %d/%d strict" % (w["route"], w["strict"], w["total"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
