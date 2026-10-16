#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""description 触发质量 A/B：同一批自然说法 hint，两份技能菜单，让模型盲选。

- Menu A = 改前的 description（git 9f74253^ 快照）
- Menu B = 改后的 description（当前盘上）
两份菜单**技能集合相同**（各 46 个，排除改后才出现的 x64dbg-reverse），只换 description 文本。

评分口径：把 routing.json 的 expect(route id) 映射到 skill 名，比较"模型选的 skill"。
（同一 skill 对应多条 route 时，选到该 skill 即算对。）

用法：python ab_runner.py <menuA|menuB|both> [batches]
"""
from __future__ import annotations

import io
import json
import os
import re
import subprocess
import sys
import tempfile

ROOT = r"C:\relab2"
SK = os.path.join(ROOT, "skillpack", "skills")
BENCH = os.path.join(SK, "tests", "routing-benchmark-natural.json")
ROUTING = os.path.join(SK, "config", "routing.json")
OUT = r"C:\Windows\Temp\descab"
BATCH = 12
OLD_REF = "9f74253^"


def skill_dirs() -> list[str]:
    return sorted(
        d for d in os.listdir(SK)
        if os.path.isfile(os.path.join(SK, d, "SKILL.md"))
    )


def parse_desc(text: str) -> str:
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.S)
    if not m:
        return ""
    dm = re.search(r"^description:[ \t]*(.*)$", m.group(1), re.M)
    if not dm:
        return ""
    val = dm.group(1).strip()
    if val in ("|", ">", "|-", ">-"):
        # 块标量：抓缩进正文
        body = []
        for line in m.group(1).splitlines():
            if line.startswith("description:"):
                continue
            body.append(line.strip())
        return " ".join(x for x in body if x)
    return val


def menus():
    dirs = skill_dirs()
    new = {}
    for d in dirs:
        if d == "x64dbg-reverse":
            continue  # 改前不存在，A/B 公平起见两侧都排除
        new[d] = parse_desc(io.open(os.path.join(SK, d, "SKILL.md"), encoding="utf-8-sig").read())
    old = {}
    for d in new:
        p = f"{OLD_REF}:skillpack/skills/{d}/SKILL.md"
        r = subprocess.run(["git", "-C", ROOT, "show", p], capture_output=True, timeout=60)
        if r.returncode != 0:
            continue
        old[d] = parse_desc(r.stdout.decode("utf-8-sig", "replace"))
    return old, new


def route_to_skill():
    cfg = json.load(io.open(ROUTING, encoding="utf-8-sig"))
    out = {}
    for rid, r in cfg["routes"].items():
        out[rid] = r["skill"].split("/")[0]
    return out


def build_prompt(menu: dict[str, str], cases: list[dict]) -> str:
    lines = ["下面是一张技能菜单（名字 + 描述）。"]
    lines.append("")
    for name, desc in sorted(menu.items()):
        lines.append(f"- {name}: {desc}")
    lines.append("")
    lines.append("现在有若干条【任务描述】。对每一条，只从上面的菜单里选 **一个** 最合适的技能名。")
    lines.append('只输出一个 JSON 数组，元素形如 {"i":序号,"skill":"技能名"}，不要任何解释、不要 markdown 代码块。')
    lines.append("")
    for i, c in enumerate(cases):
        lines.append(f"{i}. {c['hint']}")
    return "\n".join(lines)


def run_omp(prompt: str) -> str:
    os.makedirs(OUT, exist_ok=True)
    fd, path = tempfile.mkstemp(suffix=".txt", dir=OUT)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(prompt)
    try:
        r = subprocess.run(["omp", "-p", "--no-session", "@" + path],
                           capture_output=True, timeout=600)
        return r.stdout.decode("utf-8", "replace")
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def extract_json(out: str):
    m = re.search(r"\[.*\]", out, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        # 去掉尾逗号再试
        s = re.sub(r",\s*]", "]", m.group(0))
        try:
            return json.loads(s)
        except Exception:
            return None


def evaluate(tag: str, menu: dict[str, str], cases: list[dict], r2s: dict[str, str]):
    res, raw_bad = [], 0
    for b in range(0, len(cases), BATCH):
        chunk = cases[b:b + BATCH]
        out = run_omp(build_prompt(menu, chunk))
        picks = extract_json(out)
        if picks is None:
            raw_bad += len(chunk)
            print(f"  [{tag}] batch {b//BATCH}: 解析失败")
            continue
        by_i = {}
        for p in picks:
            try:
                by_i[int(p["i"])] = str(p.get("skill", "")).strip()
            except Exception:
                pass  # scan-ok: 坏条目**不会**算成功——下面 by_i.get(i, "<missing>") 会把它记成未命中并判 ok=False，raw_bad 另记解析失败
        for i, c in enumerate(chunk):
            want = r2s.get(c["expect"], "?")
            got = by_i.get(i, "<missing>")
            res.append({"hint": c["hint"], "route_expect": c["expect"], "want": want, "got": got, "ok": got == want})
        print(f"  [{tag}] batch {b//BATCH}: {sum(1 for x in res[-len(chunk):] if x['ok'])}/{len(chunk)}")
    return res, raw_bad


def main() -> int:
    which = sys.argv[1] if len(sys.argv) > 1 else "both"
    old, new = menus()
    cases = json.load(io.open(BENCH, encoding="utf-8-sig"))["cases"]
    r2s = route_to_skill()
    os.makedirs(OUT, exist_ok=True)
    report = {}
    for tag, menu in (("A_old", old), ("B_new", new)):
        if which != "both" and which != tag:
            continue
        print(f"== Menu {tag}（{len(menu)} 技能）==")
        res, bad = evaluate(tag, menu, cases, r2s)
        ok = sum(1 for x in res if x["ok"])
        acc = ok / len(res) if res else 0
        report[tag] = {"n": len(res), "ok": ok, "acc": acc, "unparsed": bad, "detail": res}
        print(f"  => {tag}: {ok}/{len(res)} = {acc:.1%}")
    io.open(os.path.join(OUT, "report.json"), "w", encoding="utf-8").write(
        json.dumps(report, ensure_ascii=False, indent=2))
    print("report ->", os.path.join(OUT, "report.json"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
