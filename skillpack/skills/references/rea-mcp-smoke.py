#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rea-mcp-smoke.py —— 用官方 `mcp` Python SDK 起 REA 的 stdio MCP 服务器，
跑一次 `tools/list` + 一次 `tools/call`，把**原始返回**落到指定目录。

为什么存在（2026-10-16）：
  REA 是独立程序（npm 包 `rea-agents`，bin=rea|rea-agents），MCP 子命令是 `rea mcp`。
  本仓要把它当第 6 条通道注册进宿主，就得先证明「这个 stdio 服务器在本机真的起得来、
  真的能列工具、真的能执行一次调用」——而不是照抄上游 README 的注册片段。
  本脚本就是那条可复核的证据通道（与 `relab2-tools-mcp.py --selftest` 同思路：
  不起宿主、不写宿主配置，直接以 stdio 客户端身份对话）。

用法：
  python rea-mcp-smoke.py [--node <node.exe>] [--rea-mjs <rea-agents/scripts/rea.mjs>]
                          [--out-dir <目录>] [--tool <工具名>] [--args '<JSON>']

默认：node.exe = 与 `npm root -g` 同级的 node.exe；rea.mjs = `<npm root -g>/rea-agents/scripts/rea.mjs`。
输出：<out-dir>/tools-list.json、<out-dir>/call-<tool>.json、<out-dir>/summary.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import pathlib
import shutil
import subprocess
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def npm_global_root() -> pathlib.Path | None:
    """`npm root -g` —— 全局包目录（REA 装在这里）。"""
    npm = shutil.which("npm")
    if not npm:
        return None
    try:
        r = subprocess.run([npm, "root", "-g"], capture_output=True, text=True, timeout=60,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0:
        return None
    p = pathlib.Path(r.stdout.strip())
    return p if p.exists() else None


def find_node(npm_root: pathlib.Path | None) -> pathlib.Path | None:
    """优先「与 npm 全局根同级的 node.exe」（本机 npm 就装在 node 目录里），
    其次 PATH 上的 node/node.exe。返回 .exe —— 宿主 spawn 不一定能直接起 .cmd shim。"""
    cands: list[pathlib.Path] = []
    if npm_root:
        cands.append(npm_root.parent / "node.exe")
    for name in ("node.exe", "node"):
        w = shutil.which(name)
        if w:
            cands.append(pathlib.Path(w))
    for c in cands:
        if c.suffix.lower() == ".exe" and c.exists():
            return c
    return None


async def run(node: pathlib.Path, rea_mjs: pathlib.Path, out_dir: pathlib.Path,
              tool: str, tool_args: dict) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    params = StdioServerParameters(command=str(node), args=[str(rea_mjs), "mcp"], env=None)
    summary: dict = {"command": str(node), "args": [str(rea_mjs), "mcp"]}
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            summary["initialize"] = {
                "serverInfo": init.serverInfo.model_dump(),
                "protocolVersion": init.protocolVersion,
                "capabilities": sorted(init.capabilities.model_dump(exclude_none=True).keys()),
            }
            tools = (await session.list_tools()).tools
            listing = [{"name": t.name, "description": t.description,
                        "inputSchema": t.inputSchema} for t in tools]
            (out_dir / "tools-list.json").write_text(
                json.dumps(listing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            summary["tools_count"] = len(tools)
            summary["tools_first20"] = [t.name for t in tools][:20]

            prompts = (await session.list_prompts()).prompts
            summary["prompts_count"] = len(prompts)
            summary["prompts"] = [p.name for p in prompts]

            res = await session.call_tool(tool, tool_args)
            raw = res.model_dump()
            (out_dir / f"call-{tool}.json").write_text(
                json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            summary["call"] = {"tool": tool, "arguments": tool_args,
                               "isError": raw.get("isError"),
                               "text_head": (raw.get("content") or [{}])[0].get("text", "")[:600]}
    (out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    ap = argparse.ArgumentParser(description="REA MCP stdio 烟雾测试")
    ap.add_argument("--node", default=None, help="node.exe 路径（默认自动探测）")
    ap.add_argument("--rea-mjs", default=None, help="rea-agents/scripts/rea.mjs（默认自动探测）")
    ap.add_argument("--out-dir", default="rea-mcp-smoke-out")
    ap.add_argument("--tool", default="binary_session", help="要 tools/call 的工具名（默认 · 目标无关）")
    ap.add_argument("--args", default="{}", help="该工具的 JSON 参数")
    a = ap.parse_args()

    npm_root = npm_global_root()
    node = pathlib.Path(a.node) if a.node else find_node(npm_root)
    rea_mjs = pathlib.Path(a.rea_mjs) if a.rea_mjs else (
        npm_root / "rea-agents" / "scripts" / "rea.mjs" if npm_root else None)
    if not node or not node.exists():
        print("找不到 node.exe —— 用 --node 指定", file=sys.stderr)
        return 2
    if not rea_mjs or not rea_mjs.exists():
        print(f"找不到 rea.mjs（npm root -g = {npm_root}）—— 先 `npm i -g rea-agents`，或用 --rea-mjs 指定",
              file=sys.stderr)
        return 2

    summary = asyncio.run(run(node, rea_mjs, pathlib.Path(a.out_dir),
                              a.tool, json.loads(a.args)))
    print(json.dumps({k: summary[k] for k in
                      ("command", "args", "tools_count", "tools_first20",
                       "prompts_count", "prompts", "call")},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
