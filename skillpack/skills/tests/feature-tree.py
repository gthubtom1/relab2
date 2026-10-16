#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""feature-tree.py —— 把整个项目的**功能线路**拆成一棵树（从真实文件推导，不手写、不凭印象）。

为什么存在（2026-10-16 主人点出的方法）
--------------------------------------
「你要的是完整的把整个项目的功能线路给拆解出来。就像一个树状图一样，任何分支、变体都要有。
  然后完全仿真走一遍，你觉得还会有问题吗？」

我此前的做法是「改一处、撞一处」：于是同一个缺陷类型还有**成片**没修
（`diec --extended` 修完了，同类还有 13 处混流 / 30 处不查退出码 / 48 个登记了从没真跑的工具）；
更糟的是上下文一多我就没印象，**把已经改对的当成错的又改回去**（`C:\\relab2` 约定那次）。
本脚本从实际文件推导**全部线路**（入口 / 技能 / 路由 / 工具 / 配方 / MCP / 门禁 / 案例 / 换机），
交给 `full-simulation.py` 逐条真跑 —— 「还会有问题吗」的答案只能来自这张图 + 逐条实跑。

用法
----
    python skills/tests/feature-tree.py            # 打印树
    python skills/tests/feature-tree.py --json     # 机器可读（给 full-simulation 用）
    python skills/tests/feature-tree.py --count    # 只要每层的数量
"""
from __future__ import annotations

import argparse
import glob
import io
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILLS = HERE.parent
REPO = SKILLS.parent.parent


def _read(p) -> str:
    try:
        return io.open(p, encoding="utf-8-sig", errors="replace").read()
    except OSError:
        return ""


def _json(p, default=None):
    try:
        return json.loads(io.open(p, encoding="utf-8-sig").read())
    except (OSError, ValueError):
        return default if default is not None else {}


def _run(cmd, timeout=90):
    """跑一条只读命令，返回 (rc, 文本)。rc=None 表示起不来/超时。"""
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, errors="replace",
                           timeout=timeout, cwd=str(REPO))
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except (OSError, subprocess.TimeoutExpired) as e:
        return None, f"{type(e).__name__}: {e}"


# ---------------------------------------------------------------- 各层清点
def layer_entrypoints():
    """入口层：只取 `switch ($Command)` 里真正对外分发的子命令。

    ★ 2026-10-16 修正：原来按 `^function Invoke-*` 推导，把**内部辅助**（`Invoke-Step`，它要
      `-File/-ArgList`）也当成了子命令 → 仿真时裸调 `relab2.ps1 step` 报参数错误，被我误记成
      "入口线路 FAIL"。**那是仿真器的错，不是项目缺陷** —— 判据要认真正的分发点。
    """
    txt = _read(REPO / "relab2.ps1")
    m = re.search(r"switch\s*\(\$Command\)\s*\{(.*?)\n\}", txt, re.S)
    if not m:
        return []
    return sorted(set(re.findall(r"'([a-z][a-z-]*)'\s*\{", m.group(1))))


def layer_skills():
    """技能层：每张 SKILL.md 的 name + description 首句。"""
    out = []
    for p in sorted(glob.glob(str(SKILLS / "*" / "SKILL.md"))):
        txt = _read(p)
        name = ""
        m = re.search(r"^name:\s*(.+)$", txt, re.M)
        if m:
            name = m.group(1).strip()
        if not name:
            name = Path(p).parent.name
        d = ""
        m = re.search(r"^description:\s*(.+)$", txt, re.M)
        if m:
            d = m.group(1).strip()[:60]
        out.append({"name": name, "path": str(Path(p).parent.relative_to(REPO)).replace("\\", "/"), "desc": d})
    return out


def layer_routes():
    """路由层：routing.json 的每条规则 → 目标技能。"""
    d = _json(SKILLS / "config" / "routing.json")
    routes = d.get("routes") or {}
    out = []
    for rid, r in (routes.items() if isinstance(routes, dict) else []):
        out.append({"id": rid, "label": r.get("label", ""), "skill": r.get("skill", "")})
    return out


def layer_tools():
    """工具层：预探测 id / 能力 / 已登记配方 三条来源。"""
    tb = _read(SKILLS / "scripts" / "relab2-tools-mcp.py")
    m = re.search(r"KNOWN_TOOLS\s*=\s*\[(.*?)\]", tb, re.S)
    known = re.findall(r'"([^"]+)"', m.group(1)) if m else []
    recipes = _json(SKILLS / "config" / "tool-recipes.json").get("recipes") or []
    ci = _read(SKILLS / "scripts" / "capability-index.py")
    caps = re.findall(r'^\s{4}"([a-z0-9-]+)":\s*\(', ci, re.M)
    return {"known_ids": known, "recipes": [r["id"] for r in recipes],
            "capabilities": sorted(set(caps)), "tool_recipes_file": "skills/config/tool-recipes.json"}


def layer_mcp():
    """MCP 层：宿主注册了几条 + 注册脚本会造几条。"""
    host = Path(os.path.expanduser("~")) / ".omp" / "agent" / "mcp.json"
    reg = list((_json(host).get("mcpServers") or {}).keys())
    txt = _read(SKILLS / "scripts" / "register-mcp.py")
    buildable = sorted(set(re.findall(r'entries\["([\w-]+)"\]', txt)))
    return {"registered_in_host": reg, "registrable": buildable}


def layer_gates():
    """门禁层：ci-gates.json 的每道门（id + 脚本 + 阻塞码）。"""
    d = _json(SKILLS / "tests" / "ci-gates.json")
    return [{"id": g.get("id"), "script": g.get("script"), "blocking": g.get("blocking_exits")}
            for g in (d.get("gates") or [])]


def layer_workflow():
    """工作流层：案例生命周期脚本（case-init → append-evidence → review）。"""
    out = []
    for pat in ("case-init.ps1", "append-evidence.ps1", "master-route.ps1",
                "review_case.py", "diff-runner.py", "experience-card.py"):
        for p in glob.glob(str(SKILLS / "**" / pat), recursive=True):
            out.append({"name": pat, "path": str(Path(p).relative_to(REPO)).replace("\\", "/")})
    return out


def layer_migration():
    """换机层：环境初始化.md §11 的分组（A–E + 11.2–11.7）。"""
    txt = _read(REPO / "环境初始化.md")
    groups = re.findall(r"^###?\s*§?(11\.\d|\d+\.\d)?\s*.{0,4}([ABCDE])\s*[·．.]\s*(.+)$", txt, re.M)
    steps = re.findall(r"^\s*\d+\.\s+\*\*(.+?)\*\*", txt, re.M)
    return {"groups": [g[1] + " " + g[2][:40] for g in groups][:10],
            "numbered_steps": steps[:14], "has_migration_section": "换机适配面" in txt}


def layer_knowledge():
    """知识库层：KB-INDEX 的症状索引入口 + 各板块正文数（这是"按现象找文档"的那一层）。"""
    idx = REPO / "docs" / "docs-placeholder"  # 占位，避免误用
    kb = SKILLS / "field-journal" / "KB-INDEX.md"
    txt = _read(kb)
    boards = []
    for m in re.finditer(r"\|\s*([^|]+?)\s*\|\s*`\.\./([^/`]+)/`\s*\|\s*(\d+)\s*\|", txt):
        boards.append({"board": m.group(1).strip(), "dir": m.group(2).strip(), "docs": int(m.group(3))})
    sources = _read(SKILLS / "field-journal" / "KB-SOURCES.md")
    entry = SKILLS / "ops" / "kb-consult-contract.md"
    return {
        "index": "skillpack/skills/field-journal/KB-INDEX.md",
        "index_exists": kb.is_file(),
        "consult_contract": "skillpack/skills/ops/kb-consult-contract.md",
        "consult_contract_exists": entry.is_file(),
        "sources_exists": (SKILLS / "field-journal" / "KB-SOURCES.md").is_file(),
        "upstream_repo": (re.search(r"LING71671/\S+", sources) or [""])[0] if sources else "",
        "boards": boards,
        "total_docs": sum(b["docs"] for b in boards),
        "journal_notes": len(glob.glob(str(SKILLS / "field-journal" / "*.md"))),
    }


def layer_kernel():
    """kernel 行为层：中枢本体（卡片 / 工作台 / 自检 / 验证 / 隔离运行）。"""
    out = []
    for d in sorted(glob.glob(str(REPO / "kernel" / "*"))):
        p = Path(d)
        if not p.is_dir():
            continue
        readme = p / "README.md"
        n = len([f for f in glob.glob(str(p / "**" / "*"), recursive=True) if Path(f).is_file()])
        title = ""
        if readme.is_file():
            m = re.search(r"^#\s+(.+)$", _read(readme), re.M)
            if m:
                title = m.group(1).strip()[:48]
        out.append({"module": p.name, "files": n, "title": title})
    return out


def layer_experience():
    """经验卡层：仓级共享经验（跨技能），每个是一次真实踩坑的沉淀。"""
    cards = sorted(glob.glob(str(SKILLS / "experience-cards" / "*.json")))
    return {"dir": "skillpack/skills/experience-cards", "count": len(cards),
            "cards": [Path(c).stem for c in cards][:20],
            "reader": "skillpack/skills/scripts/experience-card.py",
            "reader_exists": (SKILLS / "scripts" / "experience-card.py").is_file()}


def layer_community():
    """社区层：vendored 第三方技能源 + 我们的 wrapper。"""
    raw_dir = REPO / "skillpack" / "community-raw"      # ★ 在 skillpack/ 下，不在 skills/ 下
    raw = len([f for f in glob.glob(str(raw_dir / "**" / "*"), recursive=True)
               if Path(f).is_file()])
    wrappers = sorted(Path(p).parent.name for p in glob.glob(str(SKILLS / "community" / "*" / "SKILL.md")))
    orch = [Path(x).name for x in glob.glob(str(REPO / "skillpack" / "CTF-Sandbox-Orchestrator"))
            + glob.glob(str(REPO / "skillpack" / "burp-mcp-full"))]
    return {"community_raw_files": raw, "wrappers": wrappers, "orchestrators": orch}


def layer_extensions():
    """扩展层：宿主侧加固（目前只有 pi 的 cmd-guard）。"""
    out = []
    for p in sorted(glob.glob(str(REPO / "extensions" / "*" / "*"))):
        out.append(str(Path(p).relative_to(REPO)).replace("\\", "/"))
    return out


def layer_contracts():
    """契约/模板/方法层：跨技能共用的模板、schema 与方法论。"""
    def _ls(rel):
        d = SKILLS / rel
        return sorted(x.name for x in d.iterdir()) if d.is_dir() else []
    return {"templates": _ls("templates"), "schemas": _ls("../schemas"),
            "ops": _ls("ops"), "references": _ls("references")}


def layer_deps():
    """依赖层：跑这些脚本真正要的运行时与包（缺了就会"明明写了却跑不起来"）。"""
    out = {}
    for name, probe in (
        ("python(系统)", [sys.executable, "-c", "import sys;print(sys.version.split()[0])"]),
        ("mcp SDK", [sys.executable, "-c",
                      "import importlib.metadata as m, mcp;print(m.version('mcp'))"]),
    ):
        rc, o = _run(probe, timeout=60)
        out[name] = (o or "").strip().splitlines()[-1][:60] if rc == 0 else f"MISSING(rc={rc})"
    # ★ node 不能用 `node` 这个名字：本机 PATH 里是 .cmd，CreateProcess 起不来 → 找真正的 node.exe
    nodes = sorted(glob.glob(r"D:\Tools\runtime\node\*\node.exe"))
    if nodes:
        rc, o = _run([nodes[0], "-v"], timeout=60)
        out["node.exe"] = (o or "").strip()[:20] if rc == 0 else f"MISSING(rc={rc})"
    else:
        out["node.exe"] = "未找到（D:\\Tools\\runtime\\node\\*）"
    venv = Path(r"D:\Tools\runtime\python-venv\Scripts\python.exe")
    if venv.is_file():
        rc, o = _run([str(venv), "-c", "import mcp;print('mcp', mcp.__name__ and 'ok')"], timeout=120)
        out["工具根 venv"] = "mcp ok" if rc == 0 else "缺包"
    else:
        out["工具根 venv"] = "不存在"
    # ★ 本机有两个 mcp 版本 —— 这点必须报出来（桥曾因此起不来）
    for tag, py in (("mcp@python-venv", venv),
                    ("mcp@angr-mcp-venv", Path(r"D:\Tools\runtime\angr-mcp-venv\Scripts\python.exe"))):
        if py.is_file():
            rc, o = _run([str(py), "-c",
                          "import importlib.metadata as m;from mcp.server.lowlevel import Server;"
                          "print(m.version('mcp'), 'list_tools' if hasattr(Server,'list_tools') else 'NO-list_tools')"],
                         timeout=120)
            out[tag] = (o or "").strip().splitlines()[-1][:40] if rc == 0 else "读不到"
    return out


def build_tree() -> dict:
    return {
        "入口层": layer_entrypoints(),
        "技能层": layer_skills(),
        "路由层": layer_routes(),
        "工具层": layer_tools(),
        "MCP层": layer_mcp(),
        "门禁层": layer_gates(),
        "工作流层": layer_workflow(),
        "换机层": layer_migration(),
        "知识库层": layer_knowledge(),
        "kernel行为层": layer_kernel(),
        "经验卡层": layer_experience(),
        "社区层": layer_community(),
        "扩展层": layer_extensions(),
        "契约模板层": layer_contracts(),
        "依赖层": layer_deps(),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    # ★ 2026-10-16 加 `--write-doc`（照 feature-graph.py:369 那几行）：
    #   此前要落档只能靠 shell 重定向，而 **Windows PowerShell 5.1 的裸 `>` 写出的是 UTF-16LE**
    #   —— 会把 `docs/_snapshots/*.md` 这种 UTF-8/LF 文件毁掉。让脚本自己按 UTF-8/LF 写字节，
    #   是这个坑唯一的干净修法（DocConverge2 实测确认过 4 份快照都是 UTF-8/LF）。
    ap.add_argument("--write-doc", default="", metavar="PATH",
                    help="把正文写入该文件（UTF-8/LF），而不是打印到 stdout")
    ap.add_argument("--count", action="store_true")
    a = ap.parse_args()
    t = build_tree()

    if a.json:
        print(json.dumps(t, ensure_ascii=False, indent=1))
        return 0

    if a.count:
        for k, v in t.items():
            n = len(v) if isinstance(v, (list, dict)) else 1
            print(f"{k:<8} {n}")
        return 0

    # ★ --write-doc：让脚本自己按 UTF-8/LF 写字节（绕开 PS 5.1 裸 `>` 的 UTF-16LE）。
    _old_stdout, _fh = None, None
    if a.write_doc:
        _out = Path(a.write_doc)
        _out.parent.mkdir(parents=True, exist_ok=True)
        _fh = io.open(_out, "w", encoding="utf-8", newline="\n")
        _old_stdout, sys.stdout = sys.stdout, _fh

    print("relab2 · 功能线路树（从真实文件推导）")
    print("=" * 72)
    print(f"├─ 入口层（relab2.ps1 子命令 {len(t['入口层'])} 个）")
    print("│    " + " · ".join(t["入口层"]))
    sk = t["技能层"]
    print(f"├─ 技能层（{len(sk)} 张卡）")
    for s in sk[:6]:
        print(f"│    {s['name']:<26} {s['desc']}")
    print(f"│    … 其余 {max(0, len(sk)-6)} 张")
    rt = t["路由层"]
    print(f"├─ 路由层（{len(rt)} 条规则）")
    for r in rt[:4]:
        print(f"│    {r['id']:<4} → {r['skill']:<40} {r['label']}")
    print(f"│    … 其余 {max(0, len(rt)-4)} 条")
    tl = t["工具层"]
    print(f"├─ 工具层（预探测 id {len(tl['known_ids'])} · 能力 {len(tl['capabilities'])} · 配方 {len(tl['recipes'])}）")
    print(f"│    配方: {', '.join(tl['recipes'])}")
    mc = t["MCP层"]
    print(f"├─ MCP 层（宿主已注册 {len(mc['registered_in_host'])} · 可注册 {len(mc['registrable'])}）")
    print(f"│    已注册: {', '.join(mc['registered_in_host'])}")
    print(f"│    可注册: {', '.join(mc['registrable'])}")
    gt = t["门禁层"]
    print(f"├─ 门禁层（{len(gt)} 道）")
    for g in gt[:4]:
        print(f"│    {g['id']:<32} {g['script']}")
    print(f"│    … 其余 {max(0, len(gt)-4)} 道")
    wf = t["工作流层"]
    print(f"├─ 工作流层（{len(wf)} 个生命周期脚本）")
    for w in wf:
        print(f"│    {w['name']:<22} {w['path']}")
    mg = t["换机层"]
    print(f"├─ 换机层（适配面 {mg['has_migration_section']} · 编号步骤 {len(mg['numbered_steps'])} 条）")
    for s in mg["numbered_steps"][:5]:
        print(f"│    {s[:70]}")
    kb = t["知识库层"]
    print(f"├─ 知识库层（症状索引 {kb['index_exists']} · 契约 {kb['consult_contract_exists']} · "
          f"板块 {len(kb['boards'])} · 技术正文 {kb['total_docs']} 篇 · 本仓札记 {kb['journal_notes']} 篇）")
    for b in kb["boards"][:6]:
        print(f"│    {b['board']:<24} {b['docs']:>3} 篇  → {b['dir']}")
    print(f"│    上游: {kb['upstream_repo']}")
    kn = t["kernel行为层"]
    print(f"├─ kernel 行为层（{len(kn)} 个模块）")
    for m in kn[:8]:
        print(f"│    {m['module']:<20} {m['files']:>4} 文件  {m['title']}")
    ex = t["经验卡层"]
    print(f"├─ 经验卡层（{ex['count']} 张 · 读取器 {ex['reader_exists']}）")
    for c in ex["cards"][:5]:
        print(f"│    {c}")
    cm = t["社区层"]
    print(f"├─ 社区层（vendored {cm['community_raw_files']} 文件 · wrapper {len(cm['wrappers'])} 个）")
    print(f"│    wrapper: {', '.join(cm['wrappers'])}")
    ext = t["扩展层"]
    print(f"├─ 扩展层（{len(ext)} 个文件）")
    for e in ext[:5]:
        print(f"│    {e}")
    ct = t["契约模板层"]
    print(f"├─ 契约/模板层（templates {len(ct['templates'])} · schemas {len(ct['schemas'])} · "
          f"ops {len(ct['ops'])} · references {len(ct['references'])}）")
    dp = t["依赖层"]
    print(f"└─ 依赖层")
    for k, v in dp.items():
        print(f"     {k:<14} {v}")

    if _fh is not None:
        _fh.close()
        sys.stdout = _old_stdout
        print(f"已落档：{a.write_doc}（UTF-8/LF）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
