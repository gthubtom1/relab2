#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""feature-graph.py —— **功能可达图**：技能 / 工具 / 知识之间的连通关系。

主人 2026-10-16 的原话（本脚本存在的全部理由）
---------------------------------------------
「各个树干和树杈是**互通**的。**树杈是功能**呀！比如做逆向的路线，一路上互相换技能和工具、
  使用工具等等，逆向的时候可能还会用**渗透的技能和工具**，一切都是根据实际项目造成的，
  ai 思考后造成的，**不是死板的**。比如渗透的时候，也会使用协议/逆向/抓包等等技能和工具。
  我的意思就是**所有东西都是可能关联的**。你要把各个功能做的**和 ai 模型的手和四肢一样**。
  这个才是一个树杈呀，就是**不停分支的树状**。」

所以「树杈通」不是「文件有没有入口」（那是零件清单，见 `verify-leaves.py`），而是：
**从任意起点出发，AI 能不能顺手拿到下一步需要的东西** —— 而且是**跨战场**的。

本脚本做的事
-----------
1. 把 63 张技能卡（57 顶层 + 6 嵌套）、33 个能力、209 篇知识正文当成节点；
2. 抽边：卡里的「换技能表 / When to Pivot」指向的卡、正文里点名的**工具**、
   引用的**知识文档**、以及跨卡引用（`../other-skill/`）；
3. 判战场（逆向 / 协议 / 渗透 / 开发 / 安卓 / 固件），统计**跨战场边**；
4. 找**孤岛**：既没有被别的卡指向、也不指向别人 = 模型在别的战场需要它时**伸手够不着**。

用法
----
    python skills/tests/feature-graph.py            # 文本报告
    python skills/tests/feature-graph.py --json
    python skills/tests/feature-graph.py --orphans  # 只看孤岛
    python skills/tests/feature-graph.py --write-doc docs/FEATURE-GRAPH.md   # 本地落档
退出码：0（它是**分析器**）。要把某条结论升级成会红的门，由人决定。
"""
from __future__ import annotations

import argparse
import glob
import io
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILLS = HERE.parent
REPO = SKILLS.parent.parent

# 战场判定（按卡名 + description 关键词；一个卡可属多域，取首个命中）
BATTLEFIELD = [
    # ★ 关键词必须是**词**不是字母片段：原来逆向那组里放了 `re`，于是 `api-security`
    #   因为含 "secuRE" 被判成逆向 —— 战场分布整个失真（曾出现"逆向 46"）。
    ("开发", ("implement", "fix-bug", "code-review", "code-audit", "write-tests", "spike", "pr-ship",
             "design-slice", "req-clarify", "verify-done", "docs-changelog", "docs-generator",
             "diagram", "browser-automation")),
    ("协议", ("protocol", "web-protocol", "packet", "pcap", "js-reverse", "radio", "sdr", "wifi", "ot-ics")),
    ("渗透", ("pentest", "attack-chain", "exploit", "web-protocol", "api-security", "database-security",
             "identity-federation", "cloud-k8s", "supply-chain", "email-security", "ctf", "src-hunter",
             "vuln", "injection", "hack-hub")),
    ("固件", ("firmware", "hardware", "embedded")),
    ("逆向", ("reverse-engineering", "ida-reverse", "ghidra-reverse", "radare2", "binary-ninja", "binary-diff",
             "x64dbg-reverse", "dotnet-reverse", "apk-reverse", "mobile-reverse", "game-reverse",
             "kernel-exploit", "pwn-chain", "patch-diff-exploit", "malware-analysis", "thick-client",
             "browser-extension-reverse", "dsl-vm-reverse", "go-rust-reverse", "macos-reverse", "frida",
             "unpack", "case-review", "eldr", "edr-bypass-re", "llm-security", "digital-forensics",
             "code-audit", "unpack", "crack")),
]


def _read(p) -> str:
    try:
        return io.open(p, encoding="utf-8-sig", errors="replace").read()
    except OSError:
        return ""


def battlefield_of(name: str, desc: str) -> str:
    blob = (name + " " + desc).lower()
    for bf, kws in BATTLEFIELD:
        if any(k in blob for k in kws):
            return bf
    return "其它"


def skills() -> list[dict]:
    out = []
    for p in sorted(glob.glob(str(SKILLS / "*" / "SKILL.md"))) + \
             sorted(glob.glob(str(SKILLS / "*" / "*" / "SKILL.md"))):
        d = Path(p).parent
        name = d.name
        txt = _read(p)
        m = re.search(r"^description:\s*(.+)$", txt, re.M)
        desc = m.group(1).strip() if m else ""
        out.append({"name": name, "path": p, "rel": str(d.relative_to(SKILLS)).replace("\\", "/"),
                    "battlefield": battlefield_of(name, desc), "text": txt})
    # 去重（嵌套技能可能与父同名）
    seen, uniq = set(), []
    for s in out:
        k = s["rel"]
        if k in seen:
            continue
        seen.add(k)
        uniq.append(s)
    return uniq


TOOL_IDS = None


def tool_ids() -> set[str]:
    global TOOL_IDS
    if TOOL_IDS is not None:
        return TOOL_IDS
    txt = _read(SKILLS / "scripts" / "relab2-tools-mcp.py")
    m = re.search(r"KNOWN_TOOLS\s*=\s*\[(.*?)\]", txt, re.S)
    ids = set(re.findall(r'"([^"]+)"', m.group(1))) if m else set()
    ci = _read(SKILLS / "scripts" / "capability-index.py")
    ids |= set(re.findall(r'^\s{4}"([a-z0-9-]+)":\s*\(', ci, re.M))
    TOOL_IDS = ids
    return ids


def edges_from(card: dict, names: set[str], tools: set[str]) -> dict:
    """抽一张卡的出边：指向的技能 / 点名的工具 / 引用的知识文档。"""
    txt, out = card["text"], {"skills": [], "tools": [], "knowledge": []}
    # ① 跨卡引用：`../other-skill/`、`../other-skill/SKILL.md`
    for m in re.finditer(r"\.\./([a-z0-9][a-z0-9-]*)/", txt):
        t = m.group(1)
        if t in names and t != card["name"]:
            out["skills"].append(t)
    # ② 换技能表：表行里出现的技能名（含反引号）
    for m in re.finditer(r"`\.\./([a-z0-9][a-z0-9-]*)", txt):
        t = m.group(1)
        if t in names and t != card["name"]:
            out["skills"].append(t)
    # ③ 点名的工具 id（按词边界）
    for t in tools:
        if len(t) < 3:
            continue
        if re.search(rf"(?<![\w-]){re.escape(t)}(?![\w-])", txt, re.I):
            out["tools"].append(t)
    # ④ 引用的知识正文（references/*.md）
    for m in re.finditer(r"\]\(([^)\s]*references/[^)\s]+\.md)\)", txt):
        out["knowledge"].append(m.group(1))
    # ⑤ markdown 形式的技能链接：`[x](src-hunter/SKILL.md)` / `[y](../other/SKILL.md)`
    #    （community wrapper 与嵌套技能常这么互指；只认 `../x/` 会漏掉同目录引用）
    for m in re.finditer(r"\]\(([^)\s]*?SKILL\.md)\)", txt):
        parts = [p for p in m.group(1).replace("\\", "/").split("/") if p not in ("", ".", "..")]
        if len(parts) >= 2 and parts[-1] == "SKILL.md":
            cand = parts[-2]
            if cand in names and cand != card["name"]:
                out["skills"].append(cand)
    for k in ("skills", "tools", "knowledge"):
        out[k] = sorted(set(out[k]))
    return out


def build() -> dict:
    cards = skills()
    names = {c["name"] for c in cards}
    tools = tool_ids()
    graph = {}
    for c in cards:
        graph[c["name"]] = {"battlefield": c["battlefield"], "rel": c["rel"],
                            "out": edges_from(c, names, tools)}
    # 入度
    ind = {n: [] for n in graph}
    for src, d in graph.items():
        for dst in d["out"]["skills"]:
            ind.setdefault(dst, []).append(src)
    cross = []
    for src, d in graph.items():
        for dst in d["out"]["skills"]:
            bf1 = d["battlefield"]
            bf2 = (graph.get(dst) or {}).get("battlefield", "?")
            if bf1 != bf2:
                cross.append((src, bf1, dst, bf2))
    total_edges = sum(len(d["out"]["skills"]) for d in graph.values())
    islands = [n for n, d in graph.items()
               if not ind.get(n) and not d["out"]["skills"]]
    return {"nodes": len(graph), "edges": total_edges, "graph": graph,
            "indegree": {k: sorted(set(v)) for k, v in ind.items()},
            "cross_edges": sorted(set(cross)), "islands": sorted(islands),
            "battlefield_counts": {bf: sum(1 for d in graph.values() if d["battlefield"] == bf)
                                   for bf, _ in BATTLEFIELD}}


# ---------------------------------------------------------------- 全类型身体图
# 复用 verify-leaves.py 的引用抽取（不重复造：那套已经过三轮降噪）
import importlib.util as _ilu

_spec = _ilu.spec_from_file_location("verify_leaves", HERE / "verify-leaves.py")
_vl = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_vl)          # type: ignore[union-attr]
referenced_targets = _vl.referenced_targets
resolve_rel = _vl.resolve_rel
_rel = _vl._rel

# 主人 2026-10-16 追加：「不仅仅是技能/工具，还有知识库、经验卡，你之前查到的**所有东西**，
#   都是互通的，都是 **AI 模型的身体的一部分**，都是随意使用、合理使用、合理互通的。」
# 所以身体图要把**每一类节点**都放进来，并抽出**跨类型**的边（技能→经验卡、技能→知识、
# 知识→工具、经验卡→技能、门禁→脚本…），再找孤岛 —— 孤岛 = 那块身体断开了、AI 伸不过去。
NODE_KINDS = {
    "技能": ["skillpack/skills/*/SKILL.md", "skillpack/skills/*/*/SKILL.md"],
    "知识": ["skillpack/skills/**/references/**/*.md"],
    "经验卡": ["skillpack/skills/experience-cards/*.json"],
    "契约": ["skillpack/skills/templates/**/*", "skillpack/schemas/**/*", "skillpack/skills/ops/**/*.md"],
    "脚本": ["skillpack/skills/**/scripts/*.py", "skillpack/skills/**/scripts/*.ps1"],
    "kernel": ["kernel/*/README.md", "kernel/04-console/cards/*/*.md"],
    "门禁": ["skillpack/skills/tests/ci-gates.json"],
}


def _kind_of(rel: str) -> str | None:
    for k, pats in NODE_KINDS.items():
        for pat in pats:
            import fnmatch
            if fnmatch.fnmatch(rel, pat):
                return k
    return None


def body_graph() -> dict:
    """全类型节点 + 跨类型边。返回 {nodes, edges, kinds, cross, islands}。"""
    import fnmatch
    # ① 节点：文件型 + 名字型（工具 / 能力）
    files = []
    for pats in NODE_KINDS.values():
        for pat in pats:
            for f in glob.glob(str(REPO / pat), recursive=True):
                if any(s in f for s in ("_归档-禁读-历史文档", os.sep + "work" + os.sep,
                                        "community-raw", "__pycache__", ".git")):
                    continue
                if Path(f).is_file():
                    files.append(Path(f))
    files = sorted(set(files))
    nodes = {_rel(f): _kind_of(_rel(f)) or "其它" for f in files}
    tools = sorted(tool_ids())
    for t in tools:
        nodes[f"tool:{t}"] = "工具"

    # ② 边：从每个源文件抽它引用/点名的节点
    names = {Path(f).parent.name for f in files if f.name == "SKILL.md"}
    edges: list[tuple[str, str, str]] = []
    for f in files:
        rel = _rel(f)
        txt = _read(f)
        if not txt:
            continue
        for t, _ln in referenced_targets(f):
            rp = resolve_rel(f, t)
            if rp is not None and _rel(rp) in nodes:
                edges.append((rel, _rel(rp), f"{nodes[rel]}→{nodes[_rel(rp)]}"))
        # 技能卡之间的链接
        for m in re.finditer(r"\]\(([^)\s]*?SKILL\.md)\)", txt):
            parts = [p for p in m.group(1).replace("\\", "/").split("/") if p not in ("", ".", "..")]
            if len(parts) >= 2 and parts[-2] in names:
                for f2 in files:
                    if f2.parent.name == parts[-2] and f2.name == "SKILL.md":
                        edges.append((rel, _rel(f2), "技能→技能"))
                        break
        # 点名工具（短名如 r2/7z/go/gh/jq 只认反引号里的形态，避免匹配英文单词）
        for t in tools:
            if len(t) >= 3:
                if re.search(rf"(?<![\w-]){re.escape(t)}(?![\w-])", txt, re.I):
                    edges.append((rel, f"tool:{t}", f"{nodes[rel]}→工具"))
            elif re.search(rf"`{re.escape(t)}`", txt):
                edges.append((rel, f"tool:{t}", f"{nodes[rel]}→工具"))
        # 门禁清单里的 script 字段 = 门禁→脚本 的边（字段是**相对 skillpack/**，不是相对 skills/）
        if f.name == "ci-gates.json":
            try:
                for g in json.loads(txt).get("gates", []):
                    p = SKILLS.parent / str(g.get("script") or "")     # ★ skillpack/<script>
                    if p.is_file() and _rel(p) in nodes:
                        edges.append((rel, _rel(p), "门禁→脚本"))
            except ValueError as e:
                # ★ 2026-10-16（D5）：ci-gates.json 解析失败原来静默 —— 图的边会**少一截**，
                #   而"边少"与"本来就没这条边"看上去一样（图是给人看连通性的）。
                print(f"[warn] {f.name} 解析失败，门禁→脚本 的边未收录：{e}", file=sys.stderr)
    edges = sorted(set(edges))

    indeg = {n: 0 for n in nodes}
    for _s, d, _k in edges:
        if d in indeg:
            indeg[d] += 1
    outdeg = {n: 0 for n in nodes}
    for s, _d, _k in edges:
        if s in outdeg:
            outdeg[s] += 1
    islands = sorted(n for n in nodes if indeg.get(n, 0) == 0 and outdeg.get(n, 0) == 0)
    kinds = {}
    for n, k in nodes.items():
        kinds[k] = kinds.get(k, 0) + 1
    cross = sorted({k for k in (e[2] for e in edges) if "→" in k and k.split("→")[0] != k.split("→")[1]})
    return {"nodes": len(nodes), "edges": len(edges), "kinds": kinds,
            "cross_kinds": cross, "islands": islands,
            "islands_by_kind": {k: sum(1 for n in islands if nodes[n] == k) for k in kinds},
            "edge_kinds": sorted({e[2] for e in edges})}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--orphans", action="store_true")
    ap.add_argument("--write-doc", default="")
    ap.add_argument("--max-show", type=int, default=20)
    ap.add_argument("--body", action="store_true",
                    help="全类型身体图：技能/知识/经验卡/契约/脚本/kernel/门禁/工具 一起看互通")
    a = ap.parse_args()
    if a.body:
        b = body_graph()
        print("AI 身体图 —— 所有类型节点 + 跨类型边（身体各部分该是通的）")
        print("=" * 72)
        print(f"  节点 {b['nodes']} · 边 {b['edges']}")
        print(f"  各类节点: {b['kinds']}")
        print(f"  跨类型边种类: {', '.join(b['cross_kinds'])}")
        print(f"  孤岛 {len(b['islands'])} 个（断开的部分）: {b['islands_by_kind']}")
        for n in b["islands"][:30]:
            print(f"    {n}")
        if len(b["islands"]) > 30:
            print(f"    … 另有 {len(b['islands']) - 30} 个")
        return 0
    g = build()

    if a.json:
        print(json.dumps(g, ensure_ascii=False, indent=1))
        return 0

    lines = []
    lines.append("# 功能可达图（技能 × 工具 × 知识）")
    lines.append("")
    lines.append("> 主人 2026-10-16：「各个树干和树杈是**互通**的。**树杈是功能**呀！…")
    lines.append("> 逆向的时候可能还会用**渗透的技能和工具**…所有东西都是可能关联的。")
    lines.append("> 你要把各个功能做的**和 ai 模型的手和四肢一样**。这个才是一个树杈，就是**不停分支的树状**。」")
    lines.append(">")
    lines.append("> 所以本图查的不是「文件有没有入口」，而是**从任意起点能不能顺手拿到下一步需要的东西**。")
    lines.append("")
    lines.append(f"- 技能节点 **{g['nodes']}** · 指向边 **{g['edges']}** · **跨战场边 {len(g['cross_edges'])}** · 孤岛 **{len(g['islands'])}**")
    lines.append(f"- 战场分布：{g['battlefield_counts']}")
    lines.append("")
    lines.append("## 跨战场边（模型换战场的那只手）")
    lines.append("")
    lines.append("| 从 | 战场 | 到 | 战场 |")
    lines.append("|---|---|---|---|")
    for src, bf1, dst, bf2 in g["cross_edges"][:a.max_show]:
        lines.append(f"| `{src}` | {bf1} | `{dst}` | {bf2} |")
    if len(g["cross_edges"]) > a.max_show:
        lines.append(f"| … | | 另有 {len(g['cross_edges']) - a.max_show} 条 | |")
    lines.append("")
    lines.append("## 孤岛（别的战场需要它时伸手够不着）")
    lines.append("")
    for n in g["islands"]:
        lines.append(f"- `{n}`（{g['graph'][n]['battlefield']}）")
    if not g["islands"]:
        lines.append("- 无")
    lines.append("")
    lines.append("## 每个技能伸得出去的手（前 40 个节点）")
    lines.append("")
    lines.append("| 技能 | 战场 | 指向技能 | 点名工具 |")
    lines.append("|---|---|---|---|")
    for n, d in list(g["graph"].items())[:40]:
        t = ", ".join(d["out"]["tools"][:6]) or "—"
        s = ", ".join(f"`{x}`" for x in d["out"]["skills"][:4]) or "—"
        lines.append(f"| `{n}` | {d['battlefield']} | {s} | {t} |")
    lines.append("")

    text = "\n".join(lines)
    if a.orphans:
        text = "\n".join(l for l in lines if "孤岛" in l or l.startswith("- `"))
    if a.write_doc:
        out = REPO / a.write_doc
        out.parent.mkdir(parents=True, exist_ok=True)
        io.open(out, "w", encoding="utf-8", newline="\n").write(text)
        print(f"已落档：{a.write_doc}（{len(text)} 字节）")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
