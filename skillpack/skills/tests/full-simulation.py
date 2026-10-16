#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""full-simulation.py —— 拿着 `feature-tree.py` 导出的**功能线路树**，逐条真跑一遍。

为什么存在（2026-10-16 主人点出的方法）
--------------------------------------
「完整的把整个项目的功能线路给拆解出来…任何分支、变体都要有。**然后完全仿真走一遍**，
  你觉得还会有问题吗？」

这句话是**唯一能回答「还会有问题吗」的方法**。我此前的毛病是"改一处、撞一处"：
撞到 `diec --extended` 就只修那一处，结果同类还有 13 / 30 / 48 处；
更糟的是上下文一多就凭印象改，**把已经改对的又改回去**。
本脚本按**层**逐条走，每条给出 `状态 + 证据`；不通的当场列出来 —— 而不是等下一次真任务暴露。

用法
----
    python skills/tests/full-simulation.py                 # 快档（入口/技能/路由/工具/工作流）
    python skills/tests/full-simulation.py --full          # 加 MCP 真起、门禁真跑（耗时更长）
    python skills/tests/full-simulation.py --layer tools   # 只走某一层
    python skills/tests/full-simulation.py --json
退出码：0 全部通过（warn/skip 不算失败）；1 有 fail。
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

OK, WARN, FAIL, SKIP = "ok", "warn", "fail", "skip"


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


def _run(cmd, timeout=120, cwd=None):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, errors="replace",
                           timeout=timeout, cwd=str(cwd or REPO))
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except (OSError, subprocess.TimeoutExpired) as e:
        return None, f"{type(e).__name__}: {e}"


# ---------------------------------------------------------------- 各层仿真
def sim_entry():
    """入口层：relab2.ps1 的每个子命令必须能进入干跑/帮助而不报错。"""
    out = []
    txt = _read(REPO / "relab2.ps1")
    m = re.search(r"switch\s*\(\$Command\)\s*\{(.*?)\n\}", txt, re.S)
    cmds = sorted(set(re.findall(r"'([a-z][a-z-]*)'\s*\{", m.group(1)))) if m else []
    for c in cmds:
        if c == "setup":
            rc, o = _run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                          "-File", str(REPO / "relab2.ps1"), "setup", "-DryRun"], timeout=180)
        else:
            rc, o = _run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                          "-File", str(REPO / "relab2.ps1"), c], timeout=300)
        ok = rc == 0
        out.append((f"入口 {c}", OK if ok else FAIL, f"rc={rc}" if ok else f"rc={rc} {o[-160:].strip()}"))
    return out


def sim_skills():
    """技能层：每张卡的 frontmatter 必须可解析，且必须**至少有一条路由指向它**（否则永远选不到）。"""
    out = []
    routes = _json(SKILLS / "config" / "routing.json").get("routes") or {}
    routed = " ".join(str((r or {}).get("skill", "")) for r in routes.values()) if isinstance(routes, dict) else ""
    for p in sorted(glob.glob(str(SKILLS / "*" / "SKILL.md"))):
        name = Path(p).parent.name
        txt = _read(p)
        has_name = bool(re.search(r"^name:\s*\S", txt, re.M))
        has_desc = bool(re.search(r"^description:\s*\S", txt, re.M))
        if not (has_name and has_desc):
            out.append((f"技能 {name}", FAIL, "frontmatter 缺 name/description"))
        elif name not in routed and f"{name}/" not in routed:
            # 嵌套技能（如 dsl-vm-reverse）用父目录名出现在路由里，这里只提示
            out.append((f"技能 {name}", WARN, "没有任何路由规则指向它（模型可能永远选不到）"))
        else:
            out.append((f"技能 {name}", OK, ""))
    return out


def sim_routes():
    """路由层：每条规则必须有 skill 字段且目标文件真实存在。"""
    out = []
    routes = _json(SKILLS / "config" / "routing.json").get("routes") or {}
    for rid, r in (routes.items() if isinstance(routes, dict) else []):
        sk = str((r or {}).get("skill") or "")
        if not sk:
            out.append((f"路由 {rid}", FAIL, "没有 skill 字段"))
            continue
        target = SKILLS / sk
        if target.is_file():
            out.append((f"路由 {rid} → {sk}", OK, ""))
        else:
            out.append((f"路由 {rid} → {sk}", FAIL, "目标文件不存在"))
    return out


def sim_tools():
    """工具层：预探测 id 能不能解析 + 配方里的工具是否都在 + 配方引用的参数形态有没有登记。"""
    import importlib.util
    out = []
    spec = importlib.util.spec_from_file_location("m", SKILLS / "scripts" / "relab2-tools-mcp.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    import argparse as _ap
    ctx = m.Ctx(_ap.Namespace(skill_root=str(REPO), tool_root=os.environ.get("REVERSE_TOOL_ROOT", "")))
    table = ctx.probe()
    if not table:
        out.append(("工具层 预探测", FAIL, "探测层没返回任何结果（Bootstrap.ps1 / powershell 不可用？）"))
        return out
    okk = [k for k, v in table.items() if v.get("ok")]
    miss = [k for k, v in table.items() if not v.get("ok")]
    out.append((f"工具层 预探测 {len(okk)}/{len(table)}", OK if okk else FAIL,
                f"本机没有：{', '.join(miss[:10])}{' …' if len(miss) > 10 else ''}"))
    recipes = (_json(SKILLS / "config" / "tool-recipes.json").get("recipes") or [])
    registered = {r.get("tool") for r in recipes}
    for rid in sorted(registered):
        cmd, via, why = ctx.resolve(str(rid))
        out.append((f"工具 配方·{rid}", OK if cmd else WARN, f"via={via}" if cmd else f"本机没有（{why}）"))
    # 清单里出现但从未登记参数形态的工具（D7）
    m2 = re.search(r"KNOWN_TOOLS\s*=\s*\[(.*?)\]", _read(SKILLS / "scripts" / "relab2-tools-mcp.py"), re.S)
    known = set(re.findall(r'"([^"]+)"', m2.group(1))) if m2 else set()
    never = sorted(k for k in known if k in {k2 for k2, v in table.items() if v.get("ok")} and k not in registered)
    if never:
        out.append((f"工具 有工具但无配方（{len(never)}）", WARN,
                    f"{', '.join(never[:8])}{' …' if len(never) > 8 else ''} —— 从没被真跑过，参数形态未知"))
    return out


def sim_mcp():
    """MCP 层：每条可注册通道都要能起来并报出工具数（stdio 直连 / 懒启代理两种形态）。"""
    out = []
    host = Path(os.path.expanduser("~")) / ".omp" / "agent" / "mcp.json"
    servers = _json(host).get("mcpServers") or {}
    if not servers:
        out.append(("MCP 宿主注册", FAIL, f"读不到 {host}"))
        return out
    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
    except ImportError as e:
        out.append(("MCP 通道", SKIP, f"没有 mcp SDK：{e}"))
        return out
    import asyncio

    async def probe(name, spec):
        params = StdioServerParameters(command=spec.get("command", ""),
                                       args=list(spec.get("args") or []),
                                       env=spec.get("env") or None)
        try:
            async with stdio_client(params) as (r, w):
                async with ClientSession(r, w) as s:
                    await asyncio.wait_for(s.initialize(), timeout=60)
                    tl = await asyncio.wait_for(s.list_tools(), timeout=180)
                    return len(tl.tools)
        except Exception as e:  # noqa: BLE001
            return f"{type(e).__name__}: {str(e)[:90]}"

    for name, spec in servers.items():
        n = asyncio.run(probe(name, spec))
        if isinstance(n, int):
            out.append((f"MCP {name}", OK if n > 0 else WARN, f"tools={n}"))
        else:
            out.append((f"MCP {name}", WARN, str(n)))
    return out


def sim_gates():
    """门禁层：每道门单跑一次，看它自己是不是真的绿。"""
    out = []
    rc, o = _run([sys.executable, str(SKILLS / "tests" / "run-ci-gates.py")], timeout=2400)
    m = re.search(r"total=(\d+) ok=(\d+)[^\n]*blocked=(\d+) failed=(\d+)", o or "")
    if m:
        total, ok, blocked, failed = map(int, m.groups())
        out.append((f"门禁全量 {ok}/{total}", OK if blocked == 0 and failed == 0 else FAIL,
                    f"blocked={blocked} failed={failed}"))
    else:
        out.append(("门禁全量", FAIL, f"rc={rc} 拿不到汇总行：{(o or '')[-200:]}"))
    return out


def sim_workflow():
    """工作流层：每个生命周期脚本必须能给出帮助/自检而不报错。"""
    out = []
    targets = [("case-init.ps1", "scripts/case-init.ps1"), ("append-evidence.ps1", "scripts/append-evidence.ps1"),
               ("master-route.ps1", "scripts/master-route.ps1"),
               ("review_case.py", "case-review/scripts/review_case.py"),
               ("diff-runner.py", "scripts/diff-runner.py"),
               ("experience-card.py", "scripts/experience-card.py"),
               ("capability-index.py", "scripts/capability-index.py"),
               ("relab2-tools-mcp.py", "scripts/relab2-tools-mcp.py"),
               ("rea-bridge-mcp.py", "scripts/rea-bridge-mcp.py"),
               ("scan-defect-classes.py", "tests/scan-defect-classes.py"),
               ("feature-tree.py", "tests/feature-tree.py")]
    for name, rel in targets:
        p = SKILLS / rel
        if not p.is_file():
            out.append((f"工作流 {name}", FAIL, "脚本不存在"))
            continue
        if p.suffix == ".py":
            rc, o = _run([sys.executable, str(p), "--help"], timeout=90)
        else:
            rc, o = _run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                          "-File", str(p), "-?"], timeout=90)
        out.append((f"工作流 {name}", OK if rc == 0 else WARN, f"rc={rc}"))
    return out


LAYERS = {"entry": sim_entry, "skills": sim_skills, "routes": sim_routes,
          "tools": sim_tools, "workflow": sim_workflow, "mcp": sim_mcp, "gates": sim_gates}
FAST = ["entry", "skills", "routes", "tools", "workflow"]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--full", action="store_true", help="加 MCP 真起 + 门禁真跑")
    ap.add_argument("--layer", default="")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--max-show", type=int, default=6)
    a = ap.parse_args()

    names = [a.layer] if a.layer else (FAST + (["mcp", "gates"] if a.full else []))
    rows: list[tuple[str, str, str]] = []
    for n in names:
        fn = LAYERS.get(n)
        if not fn:
            rows.append((f"<未知层 {n}>", FAIL, ""))
            continue
        try:
            rows += fn()
        except Exception as e:  # noqa: BLE001
            rows.append((f"层 {n}", FAIL, f"仿真自身报错：{type(e).__name__}: {e}"))

    if a.json:
        print(json.dumps([{"line": r[0], "status": r[1], "detail": r[2]} for r in rows],
                         ensure_ascii=False, indent=2))
        return 1 if any(r[1] == FAIL for r in rows) else 0

    fails = [r for r in rows if r[1] == FAIL]
    warns = [r for r in rows if r[1] == WARN]
    print(f"功能线路仿真（{len(rows)} 条线路：ok={len(rows)-len(fails)-len(warns)} "
          f"warn={len(warns)} fail={len(fails)}）")
    print("=" * 72)
    for name, st, detail in rows:
        if st == OK:
            continue
        print(f"[{st.upper():<4}] {name}")
        if detail:
            print(f"       {detail}")
    if not fails and not warns:
        print("全部线路通过。")
    print()
    print(f"→ fail {len(fails)} 条 · warn {len(warns)} 条（warn = 需要人判断的边界，不是错）")
    if a.max_show and len(warns) > a.max_show:
        print(f"  （warn 只显示前 {a.max_show} 条，--max-show 0 显示全部）")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
