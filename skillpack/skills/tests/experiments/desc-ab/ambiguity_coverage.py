#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""B1/§7.1 度量：anti-example 到底覆盖了多少"真实歧义"。

方法（全部确定性、可复跑）：
  1. 用 routing.json 的同一套语义（小写化 / must / mustAll / exclude / priority 取最高分）
     重放 93 条自然说法 → 每条得到 PRIMARY + 候选全集。
  2. 只保留「候选 ≥2」的用例 —— 这些才是真实歧义样本。
  3. 对每条，看 PRIMARY 技能的 description 里「不要用于：」是否**点名**了其余候选技能。
  4. 输出三个数：
     - 歧义样本数
     - 邻居覆盖率 = 被点名的邻居 / 全部邻居（reviewer 用的就是这个口径）
     - **混淆加权覆盖率** = 按"该邻居在多少条样本里出现"加权（真正常见的混淆才重要）
     - 去重后的歧义对覆盖率 = 被点名的去重 pair / 全部去重 pair
"""
from __future__ import annotations

import io
import json
import os
import re
from collections import Counter

SK = r"C:\relab2\skillpack\skills"
ROUTING = os.path.join(SK, "config", "routing.json")
BENCH = os.path.join(SK, "tests", "routing-benchmark-natural.json")


def desc_of(skill_name: str) -> str:
    p = os.path.join(SK, skill_name, "SKILL.md")
    if not os.path.isfile(p):
        return ""
    t = io.open(p, encoding="utf-8-sig").read()
    m = re.match(r"^---\s*\n(.*?)\n---", t, re.S)
    if not m:
        return ""
    dm = re.search(r"^description:[ \t]*(.*)$", m.group(1), re.M)
    return dm.group(1).strip() if dm else ""


def route(cfg, hint: str):
    t = hint.lower()
    scores: Counter = Counter()
    order: list[str] = []
    for rid, r in cfg["routes"].items():
        for kw in r.get("keywords", []):
            hit = False
            if kw.get("must") and re.search(kw["must"], t):
                hit = True
            if hit and kw.get("mustAll"):
                for m in kw["mustAll"]:
                    if not re.search(m, t):
                        hit = False
                        break
            if hit and kw.get("exclude") and re.search(kw["exclude"], t):
                hit = False
            if hit:
                scores[rid] += 1
                if rid not in order:
                    order.append(rid)
    primary = None
    best = -1
    for p in cfg["priority"]:
        if scores.get(p, 0) > best:
            best = scores.get(p, 0)
            primary = p
    if not order:
        primary = cfg["meta"]["fallbackId"]
    return primary, order


def main() -> int:
    cfg = json.load(io.open(ROUTING, encoding="utf-8-sig"))
    cases = json.load(io.open(BENCH, encoding="utf-8-sig"))["cases"]
    r2s = {rid: r["skill"].split("/")[0] for rid, r in cfg["routes"].items()}
    desc_cache: dict[str, str] = {}

    ambiguous = 0
    neighbor_total = 0
    neighbor_named = 0
    weighted_total = 0
    weighted_named = 0
    pairs: Counter = Counter()
    pairs_named: Counter = Counter()
    examples = []

    for c in cases:
        primary, order = route(cfg, c["hint"])
        if len(order) < 2:
            continue
        ambiguous += 1
        pskill = r2s.get(primary, "?")
        if pskill not in desc_cache:
            desc_cache[pskill] = desc_of(pskill)
        d = desc_cache[pskill]
        for rid in order:
            if rid == primary:
                continue
            nskill = r2s.get(rid, "?")
            if nskill == "?" or nskill == pskill:
                continue
            pair = (pskill, nskill)
            pairs[pair] += 1
            neighbor_total += 1
            weighted_total += 1
            named = nskill in d
            if named:
                neighbor_named += 1
                weighted_named += 1
                pairs_named[pair] += 1
            elif len(examples) < 12:
                examples.append((c["hint"], pskill, nskill))

    print(f"自然用例总数        : {len(cases)}")
    print(f"歧义用例(候选>=2)   : {ambiguous}")
    print(f"邻居出现次数(含重复) : {neighbor_total}")
    print(f"邻居被点名次数       : {neighbor_named}  -> 逐条覆盖率 {neighbor_named/max(neighbor_total,1):.1%}")
    print(f"去重歧义对           : {len(pairs)}")
    print(f"去重歧义对(已覆盖)   : {len(pairs_named)}  -> 覆盖率 {len(pairs_named)/max(len(pairs),1):.1%}")
    print()
    print("=== 未被点名的去重歧义对（按出现次数降序，前 20）===")
    for (a, b), n in pairs.most_common():
        if (a, b) not in pairs_named:
            print(f"  {n:>3}x  {a}  <-- 未点名 -->  {b}")
    print()
    print("=== 已点名的去重歧义对（前 10）===")
    for (a, b), n in pairs_named.most_common(10):
        print(f"  {n:>3}x  {a}  -->  {b}")
    print()
    print("=== 未覆盖样本举例 ===")
    for hint, p, n in examples[:6]:
        print(f"  {p} 应排除 {n} | {hint}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
