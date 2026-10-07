#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""gen-tool-index.py — 从 toolreg 的实测数据生成 `TOOLS.md` / .json。

为什么存在（便携性关键）：
  原来的生成器 refresh-tool-index.ps1 依赖 lib/ToolDiscovery.ps1，而后者只认
  C:\\HACKER / D:\\HACKER，找不到就 throw —— 「拷到任意电脑 → 生成索引 → 给技能用」
  这条链在任何非 C:\\HACKER 机器上必断，`TOOLS.md` 永远生成不出来。
  本脚本改从 capabilities.json + registry.json 取数据，因为那才是实测路径。

⚠️ 本项目（只含 kernel/ + skillpack/ 两层）**不含 toolreg/ 也不含 adapt/**，
  所以默认数据源在本项目里不存在。本脚本被保留，是为了「将来若重新引入 toolreg 层，
  仍有一条跨机器可用的生成链」。现在直接跑它会明确报错退出，不会写半成品。

用法：
  $env:RELAB_TOOLREG = '<含 capabilities.json 与 registry.json 的目录>'
  python -u gen-tool-index.py                 # 写入 `skillpack/skills/TOOLS.md` + .json
  python -u gen-tool-index.py --check         # 只检查是否存在且新鲜，不写文件
  python -u gen-tool-index.py --out <dir>     # 指定输出目录

数据缺失时不写半成品，直接报错并说明本项目没有 toolreg/adapt 可跑，
以及两条替代路线：设 RELAB_TOOLREG 指向外部数据源，或直接现场探测。

不生成 tool-index 也能干活：本项目默认路线是现场探测
（Get-Command → Test-Path 候选），见 SKILL.md §工具根。
"""
import argparse
import datetime
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILLS = os.path.dirname(HERE)                 # .../skills
PKG = os.path.dirname(os.path.dirname(SKILLS)) # repo root
# 本项目（relab2）只含 kernel/ 与 skillpack/ 两层，**不含 toolreg/ 与 adapt/**。
# 下面的默认值在本项目里不存在，因此允许用环境变量把数据源指到别处：
#   $env:RELAB_TOOLREG   = 含 capabilities.json / registry.json 的目录
#   $env:RELAB_MANIFEST  = 含 golden-manifest.json 的目录（可选，仅用于表格列）
TOOLREG = os.environ.get("RELAB_TOOLREG") or os.path.join(PKG, "toolreg")
CAPS = os.path.join(TOOLREG, "capabilities.json")
REG = os.path.join(TOOLREG, "registry.json")
MANIFEST = os.environ.get("RELAB_MANIFEST") or os.path.join(PKG, "adapt", "golden-manifest.json")

def load(path, default=None):
    try:
        with open(path, encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception as e:
        print("WARN 读不到 %s: %s" % (path, e), file=sys.stderr)
        return default

def tool_skill_map(manifest):
    """id -> 归属 skill 名（从 manifest notes / display 粗提取，供表格用）。"""
    out = {}
    for t in (manifest or {}).get("tools", []):
        tid = t.get("id")
        if not tid:
            continue
        # 优先从 notes 里抓 'xxx/' 形式的 skill 归属
        notes = t.get("notes") or ""
        import re
        m = re.search(r"from skillpack index[^\n]*?\b([a-z0-9\-]+)", notes)
        out[tid] = m.group(1) if m else ""
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=SKILLS, help="输出目录（默认 skills/）")
    ap.add_argument("--check", action="store_true", help="只检查不写")
    a = ap.parse_args()

    caps = load(CAPS)
    if not caps:
        print("ERROR 读不到能力数据：%s" % CAPS, file=sys.stderr)
        print("  本项目只含 kernel/ 与 skillpack/ 两层，**不含 toolreg/ 注册层**，"
              "也不含 adapt/ 自适配层，因此没有 discover / registry build 可跑。", file=sys.stderr)
        print("  要生成 tool-index，请用环境变量 RELAB_TOOLREG 指向一个真实的 toolreg 目录：", file=sys.stderr)
        print("    $env:RELAB_TOOLREG = '<某个含 capabilities.json 与 registry.json 的目录>'", file=sys.stderr)
        print("  或：本项目不需要生成物，直接按 'Get-Command / Test-Path' 现场探测（见 SKILL.md §工具根）。", file=sys.stderr)
        return 2
    reg = load(REG, {}) or {}
    manifest = load(MANIFEST, {}) or {}
    rtools = reg.get("tools") or {}
    cidx = caps.get("capability_index") or {}
    mcps = caps.get("mcp_endpoints") or {}
    skill_of = tool_skill_map(manifest)

    # 汇总每个工具：路径 / 版本 / 就绪 / 能力 / 调用方式
    tools = {}
    for tid, info in rtools.items():
        health = info.get("health")
        path = info.get("path")
        avail = bool(path and health == "ok" and os.path.exists(path))
        # 从 capability_index 反查该工具被哪些能力引用 + 调用方式
        caps_of, hows = [], []
        for cap, lst in cidx.items():
            for item in lst:
                if item.get("tool") == tid:
                    caps_of.append(cap)
                    if item.get("how"):
                        hows.append(item["how"])
        tools[tid] = {
            "tool": tid,
            "skill": skill_of.get(tid, ""),
            "available": avail,
            "path": path if avail else "",
            "version": info.get("version") or "",
            "health": health or "",
            "capabilities": sorted(caps_of),
            "how": hows[0] if hows else "",
            "kind": info.get("kind") or "",
        }

    if a.check:
        p = os.path.join(a.out, "`TOOLS.md`")
        print("`TOOLS.md`: %s" % ("存在" if os.path.exists(p) else "缺失"))
        return 0 if os.path.exists(p) else 1

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ready = [t for t in tools.values() if t["available"]]
    missing = [t for t in tools.values() if not t["available"]]

    L = []
    L.append("# 本机工具索引 / Machine Tool Index")
    L.append("")
    L.append("> ⚠️ **本文件由脚本自动生成，每台机器不同，不要手改、不要入库。**")
    L.append("> 数据源：`%s` 下的 capabilities.json + registry.json（外部实测数据）。" % TOOLREG)
    L.append("> 生成时间：`%s`" % now)
    L.append("")
    L.append("重新生成：`python -u %s`" % os.path.join("skills", "scripts", "gen-tool-index.py"))
    L.append("")
    L.append("## 工具总览 / Tools")
    L.append("")
    L.append("| 工具 | 归属 skill | 可用 | 健康 | 路径 | 版本 | 能力 | 调用方式 |")
    L.append("|---|---|:---:|---|---|---|---|---|")
    for tid in sorted(tools, key=lambda k: (not tools[k]["available"], k)):
        t = tools[tid]
        L.append("| `%s` | %s | %s | %s | `%s` | %s | %s | `%s` |" % (
            t["tool"], t["skill"] or "—", "✓" if t["available"] else "✗",
            t["health"] or "—", t["path"] or "—", t["version"] or "—",
            ", ".join(t["capabilities"][:3]) or "—",
            (t["how"] or "—").replace("|", "\\|")[:60]))
    L.append("")

    L.append("## 能力状态视图 / Capability Status")
    L.append("")
    L.append("| 能力 | 就绪工具 | 调用方式 |")
    L.append("|---|---|---|")
    for cap in sorted(cidx):
        entries = cidx[cap]
        ready_here = [e for e in entries
                      if tools.get(e.get("tool"), {}).get("available")]
        how = (ready_here[0].get("how") if ready_here else
               (entries[0].get("how") if entries else "")) or ""
        L.append("| %s | %s | `%s` |" % (
            cap, ", ".join(e["tool"] for e in ready_here) or "—",
            how.replace("|", "\\|")[:70]))
    L.append("")

    L.append("## MCP 端点 / MCP Endpoints")
    L.append("")
    if mcps:
        L.append("| 名称 | 类型 | 工具数 | 状态 | 端点/命令 | 备注 |")
        L.append("|---|---|:---:|---|---|---|")
        for name, info in mcps.items():
            L.append("| `%s` | %s | %s | %s | `%s` | %s |" % (
                name, info.get("type", "—"), info.get("tools", "—"),
                info.get("status", "—"),
                (info.get("url") or info.get("command") or "—").replace("|", "\\|"),
                (info.get("requires") or "").replace("|", "\\|")[:50]))
    else:
        L.append("（无 MCP 端点登记）")
    L.append("")

    L.append("## 汇总 / Summary")
    L.append("")
    L.append("- 工具总数：%d ｜ 可用：%d ｜ 不可用：%d ｜ 能力项：%d ｜ MCP：%d"
             % (len(tools), len(ready), len(missing), len(cidx), len(mcps)))
    if missing:
        L.append("- 不可用工具（需要时按 registry 的 install 指引补装）：%s"
                 % ", ".join("`%s`" % t["tool"] for t in sorted(missing, key=lambda x: x["tool"])[:20]))
    L.append("")

    md = "\n".join(L) + "\n"
    md_path = os.path.join(a.out, "`TOOLS.md`")
    js_path = os.path.join(a.out, "`TOOLS.md`")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)
    with open(js_path, "w", encoding="utf-8") as f:
        json.dump({"generated": now, "tools": list(tools.values()),
                   "mcp_endpoints": mcps, "capability_index": cidx},
                  f, ensure_ascii=False, indent=1)
    print("WROTE %s" % md_path)
    print("WROTE %s" % js_path)
    print("工具 %d ｜ 可用 %d ｜ 能力 %d ｜ MCP %d"
          % (len(tools), len(ready), len(cidx), len(mcps)))
    return 0

if __name__ == "__main__":
    sys.exit(main())