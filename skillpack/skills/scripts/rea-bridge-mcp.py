#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rea-bridge-mcp.py —— 把 REA 的 MCP 服务器**筛过再转**进本仓（stdio 桥）。

为什么要桥，而不是直接把 REA 注册进宿主
----------------------------------------
REA 装了之后 `tools/list` 有 **207 个工具**（+6 个 prompt）。全量注册 = 宿主每次会话
都常驻 207 个工具的描述，**上下文成本按每轮累加**；而本机实测（见 `references/rea-integration.md` §4）
**真正能用的只有 30 组 / 77 个**（其余要 Ghidra 12.1.x / IDA / adb / jadx 等外部 provider，本机没有）。
所以本桥只放行**本机真能用、且与四大战场相关**的那一部分，其余一律不暴露 ——
这就是「融合」的可控形态：能力进来，噪音不进来。

放行清单（DEFAULT_ALLOW）的挑选依据（每条都可在 §4 的能力矩阵里查到出处）
------------------------------------------------------------------------
  · Evidence 模型本体 —— REA 最值得吸收的机制（证据 ID / unknowns / bundle 导出）
  · PE / 产物静态解析（实测 `inspect_pe_resources` 真出 Evidence）
  · .NET 托管静态 —— 对应本仓 `dotnet-reverse` 战场
  · JS / Web 静态 —— 对应 `js-reverse` / `web-protocol-reverse` 战场
  · 抓包文件解析 —— 对应协议战场
  · Frida 运行时组 —— 对应安卓 / 动态战场

用法
----
    python skills/scripts/rea-bridge-mcp.py                 # 作为 stdio MCP 服务器（给宿主注册用）
    python skills/scripts/rea-bridge-mcp.py --list          # 只列出上游 207 个 + 标出哪些放行
    python skills/scripts/rea-bridge-mcp.py --selfcheck     # 起上游、验证筛后 list_tools 与一次调用
    python skills/scripts/rea-bridge-mcp.py --allow-all     # 不做筛选（调试用）
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

import mcp.types as types
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

# 放行清单：本机零 provider 可用 + 与四大战场相关
DEFAULT_ALLOW = [
    # —— Evidence 模型本体（融合的核心） ——
    "binary_session", "open_binary", "close_binary",
    "get_evidence_bundle", "list_unknowns", "record_unknown",
    "export_evidence_bundle", "evaluate_reconstruction_coverage",
    # —— PE / 产物 / 指纹 ——
    "inspect_pe_resources", "inspect_artifact", "extract_artifact",
    "decode_interface_builder", "inspect_keyed_archive",
    "inspect_go_binary", "inspect_rust_binary",
    "identify_flutter_build", "inspect_dart_aot",
    # —— .NET 托管静态 ——
    "inspect_managed_artifact", "inspect_managed_members", "inspect_managed_native_boundaries",
    # —— JS / Web 静态 ——
    "analyze_javascript_application", "analyze_web_bundle", "export_web_scripts",
    "trace_web_module_imports", "observe_javascript_runtime", "inspect_web_network_capture",
    # —— 抓包文件 ——
    "inspect_pcap_capture", "inspect_pcap_client",
    # —— Frida 运行时 ——
    "list_frida_devices", "list_frida_processes", "start_frida_session",
    "instrument_with_frida", "load_frida_script",
]


def find_rea() -> tuple[str, str] | None:
    """定位 `node.exe` 与 `rea-agents/scripts/rea.mjs`。找不到就返回 None（不猜）。

    ★ 2026-10-16 实测教训：**不能靠 `node` / `npm` 这两个名字** —— 本机 PATH 里它们都是
      `.cmd` shim，而 `CreateProcess` 起不了 `.cmd`（子代理装 REA 时踩过同一个坑）。
      所以按「显式 env → PATH 里的 node.exe → 约定 node 目录」三级找**真正的 .exe**，
      再用「全局根 = node 目录」这个本机实测事实去拼 `rea-agents/scripts/rea.mjs`。
    """
    import glob as _glob
    import shutil as _shutil

    mjs_env = os.environ.get("REA_MJS", "")
    nodes: list[str] = []
    if os.environ.get("REA_NODE"):
        nodes.append(os.environ["REA_NODE"])
    for name in ("node.exe", "node"):
        w = _shutil.which(name)
        if w and w.lower().endswith(".exe"):
            nodes.append(w)
    nodes += sorted(_glob.glob(r"D:\Tools\runtime\node\*\node.exe"))
    nodes += sorted(_glob.glob(os.path.expanduser("~") + r"\AppData\Local\**\node.exe")[:2])

    seen = set()
    for node in nodes:
        if not node or node in seen:
            continue
        seen.add(node)
        try:
            r = subprocess.run([node, "-v"], capture_output=True, text=True,
                               errors="replace", timeout=20)
            if r.returncode != 0:
                continue
        except (OSError, subprocess.TimeoutExpired):
            continue
        cands = [mjs_env] if mjs_env else []
        node_dir = Path(node).parent            # 本机实测：npm 全局前缀就是 node 目录
        cands.append(str(node_dir / "node_modules" / "rea-agents" / "scripts" / "rea.mjs"))
        cands.append(str(node_dir / ".." / "node_modules" / "rea-agents" / "scripts" / "rea.mjs"))
        for mjs in cands:
            if mjs and Path(mjs).is_file():
                return node, str(Path(mjs).resolve())
    return None


def upstream_params(node: str, mjs: str) -> StdioServerParameters:
    return StdioServerParameters(command=node, args=[mjs, "mcp"], env=None)


class Bridge:
    def __init__(self, session: ClientSession, allow: set[str] | None):
        self.session = session
        self.allow = allow

    async def list_tools(self) -> list[types.Tool]:
        res = await self.session.list_tools()
        tools = list(res.tools)
        if self.allow is None:
            return tools
        return [t for t in tools if t.name in self.allow]

    async def call(self, name: str, arguments: dict) -> types.CallToolResult:
        if self.allow is not None and name not in self.allow:
            return types.CallToolResult(
                isError=True,
                content=[types.TextContent(type="text", text=json.dumps(
                    {"error": {"code": "not_exposed",
                               "message": f"`{name}` 不在本桥的放行清单里（REA 有 207 个工具，"
                                          f"本桥只转本机真能用的那一部分）。要全量用，跑 "
                                          f"`rea-bridge-mcp.py --allow-all` 或直接调 REA。",
                               "allowed_hint": "python skills/scripts/rea-bridge-mcp.py --list"}},
                    ensure_ascii=False))])
        return await self.session.call_tool(name, arguments)


def build_server(bridge: Bridge) -> Server:
    server: Server = Server("rea-bridge")

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return await bridge.list_tools()

    @server.list_prompts()
    async def list_prompts() -> list[types.Prompt]:
        res = await bridge.session.list_prompts()
        return list(res.prompts)

    @server.get_prompt()
    async def get_prompt(name: str, arguments: dict | None) -> types.GetPromptResult:
        return await bridge.session.get_prompt(name, arguments or {})

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> types.CallToolResult:
        return await bridge.call(name, arguments or {})

    return server


async def _selfcheck(node: str, mjs: str, allow: set[str], allow_all: bool) -> int:
    fails: list[str] = []
    async with stdio_client(upstream_params(node, mjs)) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            all_tools = list((await s.list_tools()).tools)
            chosen = all_tools if allow_all else [t for t in all_tools if t.name in allow]
            print(f"上游 REA 工具数: {len(all_tools)}   本桥放行: {len(chosen)}")
            missing = [n for n in allow if n not in {t.name for t in all_tools}]
            if not allow_all and missing:
                fails.append(f"放行清单里有 {len(missing)} 个名字上游没有（可能要改版本）: {missing[:5]}")
            # 真调一次：binary_session 是目标无关的，最稳
            bridge = Bridge(s, None if allow_all else allow)
            res = await bridge.call("binary_session", {})
            txt = res.content[0].text if res.content else ""
            print(f"binary_session -> isError={res.isError} bytes={len(txt)}")
            if res.isError:
                fails.append(f"binary_session 调用失败：{txt[:160]}")
            # 放行清单外的工具必须被本桥挡住
            if not allow_all:
                blocked = await bridge.call("decompile_function", {"path": "x"})
                if not blocked.isError:
                    fails.append("清单外的工具没有被拦住")
                else:
                    print("清单外工具 -> 已拦截 ✓")
    print()
    print("rea-bridge 自检:", "PASS" if not fails else "FAIL")
    for f in fails:
        print("  x", f)
    return 1 if fails else 0


async def _serve(node: str, mjs: str, allow: set[str] | None) -> None:
    async with stdio_client(upstream_params(node, mjs)) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            server = build_server(Bridge(s, allow))
            async with stdio_server() as (sr, sw):
                await server.run(sr, sw, server.create_initialization_options())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--node", default=os.environ.get("REA_NODE", ""))
    ap.add_argument("--rea-mjs", default="")
    ap.add_argument("--allow-all", action="store_true", help="不筛选（调试用）")
    ap.add_argument("--list", action="store_true", help="列出上游工具并标出放行情况")
    ap.add_argument("--selfcheck", action="store_true", help="自检：起上游 + 验证筛选 + 一次真调用")
    a = ap.parse_args()

    found = find_rea() if not (a.node and a.rea_mjs) else (a.node, a.rea_mjs)
    if not found:
        print("找不到 REA（node.exe + npm 全局里的 rea-agents/scripts/rea.mjs）。"
              "装法：npm i -g rea-agents；也可用 --node/--rea-mjs 或 REA_NODE 显式指定。",
              file=sys.stderr)
        return 2
    node, mjs = found
    allow = set(DEFAULT_ALLOW)

    if a.list:
        async def _l() -> int:
            async with stdio_client(upstream_params(node, mjs)) as (r, w):
                async with ClientSession(r, w) as s:
                    await s.initialize()
                    tools = list((await s.list_tools()).tools)
                    for t in tools:
                        print(("  [放行] " if t.name in allow else "  [隐藏] ") + t.name)
                    print(f"\n共 {len(tools)} 个；放行 {sum(1 for t in tools if t.name in allow)} 个")
            return 0
        return asyncio.run(_l())

    if a.selfcheck:
        return asyncio.run(_selfcheck(node, mjs, allow, a.allow_all))

    try:
        asyncio.run(_serve(node, mjs, None if a.allow_all else allow))
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
