#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mcp-lazy-http.py —— 把「HTTP 型 MCP 通道」包成 stdio MCP 服务器，后端按需拉起。

为什么存在（2026-10-15）：
  本机注册的 6 条 MCP 通道里，pyghidra / angr 是**直连 stdio** —— 宿主自动拉起，模型随时看得见、调得动；
  而 idapro(13337) / x64dbg-mcp(9094) 的**后端**是 http —— **默认是关的**，模型不一定会想起来去按开关。
  这就是「拿着枪却不会用」的机械原因。REA 的做法是它的桥**自己拉起 provider**
  （"REA starts Hopper when an operation needs it"）。本脚本把这一能力补齐。

行为（三条铁律）：
  1. **启动本进程绝不启动后端** —— 否则每开一次宿主就弹一次 x64dbg / 起一次 IDA。
  2. `tools/list`：后端在 → 取实时清单并刷新本地缓存；后端不在 → 直接回缓存清单，
     所以**工具对模型永远可见**（这是「永远在手边」的关键）。
  3. `tools/call`：后端不在 → 跑 launcher、等端口 LISTEN、再转发；超时或失败 → 回一条
     明确的错误文本（写明试过什么、下一步该敲什么），**绝不挂死、绝不静默**。

用法（在宿主 mcp.json 里注册成 stdio 服务器）：
  {
    "command": "<venv python 绝对路径>",
    "args": ["<仓根>/skillpack/skills/scripts/mcp-lazy-http.py",
             "--name", "idapro",
             "--url",  "http://127.0.0.1:13337/mcp",
             "--port", "13337",
             "--launcher", "powershell -NoProfile -ExecutionPolicy Bypass -File <仓根>/skillpack/skills/ida-reverse/scripts/start.ps1"]
  }

依赖：`mcp`（Python SDK）+ `anyio`（都在本机 python-venv 里）。
日志：%LOCALAPPDATA%\\reverse-skill\\mcp-lazy\\<name>.log —— stdio 型服务器看不到 stderr，所以必须落盘。
"""
from __future__ import annotations

import argparse
import io
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import anyio
import mcp.types as types
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

# ---------------------------------------------------------------- 基础设施

def _state_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    d = Path(base) / "reverse-skill" / "mcp-lazy"
    d.mkdir(parents=True, exist_ok=True)
    return d


def parse_headers(items: list[str]) -> dict[str, str]:
    """把 ['Authorization: Bearer xxx', 'X-Foo: y'] 解析成 dict。
    有些 http 通道（x64dbg-mcp）带 Bearer token，转发时必须原样带上。"""
    out: dict[str, str] = {}
    for it in items:
        if ":" in it:
            k, v = it.split(":", 1)
            out[k.strip()] = v.strip()
    return out


class Ctx:
    def __init__(self, args: argparse.Namespace) -> None:
        self.name: str = args.name
        self.url: str = args.url
        self.host: str = args.host
        self.port: int = args.port
        self.launcher: str | None = args.launcher
        self.wait: int = args.wait
        self.headers: dict[str, str] = parse_headers(args.header or [])
        self.state = _state_dir()
        self.cache_file = self.state / f"{self.name}.json"
        self.log_file = self.state / f"{self.name}.log"
        # ★ 2026-10-15（审计实测后的补丁）：新机器上本机缓存是空的 → tools/list 回空表 →
        #   模型**第一会话看不见任何工具**，等于这套机制白做。所以仓库里带一份**种子清单**
        #   （工具 schema 是 MCP 服务器给的，与机器无关），兜底顺序：实时 → 本机缓存 → 种子 → 空。
        self.seed_file: Path | None = None
        if args.seed:
            self.seed_file = Path(args.seed)
        else:
            # __file__ = <仓根>/skillpack/skills/scripts/mcp-lazy-http.py
            # parents[1] = <仓根>/skillpack/skills  ← 种子在它的 references/ 下
            cand = Path(__file__).resolve().parents[1] / "references" / "mcp-lazy-seeds" / f"{self.name}.json"
            if cand.exists():
                self.seed_file = cand

    def log(self, msg: str) -> None:
        line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
        try:
            with self.log_file.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            pass

    # -- 端口 --
    def port_open(self, timeout: float = 1.0) -> bool:
        try:
            with socket.create_connection((self.host, self.port), timeout=timeout):
                return True
        except OSError:
            return False

    # -- 缓存 --
    def load_cache(self) -> list[dict]:
        """兜底顺序：本机缓存 → 仓库种子 → 空。返回空时**必须记日志**，否则
        『新机第一会话看不见工具』会以静默失败的形式复现（2026-10-15 审计实测就是这样）。"""
        try:
            return json.loads(self.cache_file.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            # 本函数 docstring 的硬要求：返回空之前**必须**留下理由，否则
            # 「新机第一会话看不见工具」会再次静默复现（2026-10-15 审计实测）。
            self.log(f"cache read failed: {e}（回落种子/空表）")
        if self.seed_file and self.seed_file.exists():
            try:
                data = json.loads(self.seed_file.read_text(encoding="utf-8"))
                self.log(f"cache miss -> 用仓库种子 {self.seed_file.name}（{len(data)} 个工具）")
                return data
            except (OSError, ValueError) as e:
                self.log(f"seed read failed: {e}")
        self.log("cache miss 且无种子 -> 回空表（模型将看不见本通道的工具）")
        return []

    def save_cache(self, tools: list[types.Tool]) -> None:
        try:
            self.cache_file.write_text(
                json.dumps([t.model_dump(by_alias=True, exclude_none=True) for t in tools],
                           ensure_ascii=False, indent=1),
                encoding="utf-8")
        except OSError as e:
            self.log(f"cache write failed: {e}")

    # -- 拉起后端（阻塞，调用方放线程里跑）--
    def ensure_up(self) -> tuple[bool, str]:
        if self.port_open():
            return True, "already listening"
        if not self.launcher:
            return False, "没有配置 --launcher，无法自动拉起"
        self.log(f"port {self.port} closed -> launch: {self.launcher}")
        # ★ 绝不能 capture_output=True：启动器会把后端子进程 detach 出去，
        #   孙进程继承了管道写端 → subprocess.run 会一直等 EOF 而挂死
        #   （2026-10-15 实测：整条调用被拖到超时，端口一直没起来）。
        #   改成「发射后不管 + 自己轮询端口」：日志落文件，句柄不进管道。
        launch_log = self.state / f"{self.name}.launch.log"
        try:
            with launch_log.open("ab") as lf:
                lf.write(f"\n--- {time.strftime('%Y-%m-%d %H:%M:%S')} {self.launcher}\n".encode())
                lf.flush()
                subprocess.Popen(
                    self.launcher, shell=True,
                    stdin=subprocess.DEVNULL, stdout=lf, stderr=lf,
                    creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                    | getattr(subprocess, "DETACHED_PROCESS", 0),
                    # scan-ok: 刻意「发射后不管」——不能带 timeout（Popen 的参数只作用于子进程本身，
                    # 这里的后端子进程会被启动器 detach，等它会挂死，见上面 145-148 行）；
                    # 挂死上限由**下面**的端口轮询 deadline 强制：到期就返回 False。
                )
        except OSError as e:
            self.log(f"launcher OSError: {e}")
            return False, f"启动器无法执行：{e}"

        deadline = time.time() + self.wait
        while time.time() < deadline:
            if self.port_open():
                self.log(f"port {self.port} is listening")
                return True, "started"
            time.sleep(0.5)
        self.log(f"port {self.port} still closed after {self.wait}s")
        return False, f"启动器已执行，但 {self.wait}s 内 {self.host}:{self.port} 仍未监听"


# ---------------------------------------------------------------- HTTP 侧

async def remote_tools(ctx: Ctx) -> list[types.Tool]:
    async with streamablehttp_client(ctx.url, headers=ctx.headers or None, timeout=20) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.list_tools()
            return list(result.tools)


async def remote_call(ctx: Ctx, name: str, arguments: dict) -> types.CallToolResult:
    async with streamablehttp_client(ctx.url, headers=ctx.headers or None,
                                     timeout=600, sse_read_timeout=600) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await session.call_tool(name, arguments)


# ---------------------------------------------------------------- 主程序

def build_server(ctx: Ctx) -> Server:
    server: Server = Server(f"{ctx.name}-lazy-proxy")

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        if ctx.port_open():
            try:
                tools = await remote_tools(ctx)
                ctx.save_cache(tools)
                ctx.log(f"tools/list live: {len(tools)}")
                return tools
            except Exception as e:                      # noqa: BLE001
                ctx.log(f"live tools/list failed: {e!r} -> fallback to cache")
        cached = ctx.load_cache()
        ctx.log(f"tools/list from cache: {len(cached)}")
        out: list[types.Tool] = []
        for t in cached:
            try:
                out.append(types.Tool(**t))
            except Exception:                           # noqa: BLE001
                continue
        return out

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> types.CallToolResult:
        ok, why = await anyio.to_thread.run_sync(ctx.ensure_up)
        if not ok:
            # ★ 必须回 CallToolResult（带 isError），不能只回 ContentBlock 列表：
            #   上游工具若声明了 outputSchema，只回 content 会在客户端触发
            #   "outputSchema defined but no structured output returned"（2026-10-15 实测）。
            return types.CallToolResult(
                isError=True,
                content=[types.TextContent(
                    type="text",
                    text=(f"[{ctx.name}] 后端未就绪：{why}\n"
                          f"手动拉起：{ctx.launcher or '(未配置启动器)'}\n"
                          f"详情见日志：{ctx.log_file}"))])
        try:
            result = await remote_call(ctx, name, arguments)
        except Exception as e:                          # noqa: BLE001
            ctx.log(f"call {name} failed: {e!r}")
            return types.CallToolResult(
                isError=True,
                content=[types.TextContent(
                    type="text",
                    text=(f"[{ctx.name}] 调用 {name} 失败：{type(e).__name__}: {e}\n"
                          f"端口 {ctx.host}:{ctx.port} 当前{'在监听' if ctx.port_open() else '已关闭'}；"
                          f"日志：{ctx.log_file}"))])
        ctx.log(f"call {name} ok (isError={result.isError})")
        # 原样转发：content / structuredContent / isError 一个都不丢（SDK 支持直接回 CallToolResult）。
        return result

    return server


async def _serve(server: Server) -> None:
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


def main() -> int:
    ap = argparse.ArgumentParser(description="HTTP 型 MCP 通道的 stdio 懒启动代理")
    ap.add_argument("--name", required=True, help="通道名（只用于日志/缓存文件命名）")
    ap.add_argument("--url", required=True, help="形如 http://127.0.0.1:13337/mcp")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--launcher", default=None, help="后端未监听时执行的命令行（幂等启动器）")
    ap.add_argument("--header", action="append", default=[],
                    help="转发时附加的 HTTP 头，形如 'Authorization: Bearer xxx'；可重复")
    ap.add_argument("--seed", default=None,
                    help="工具清单种子文件（本机无缓存时的兜底；默认自动找 "
                         "<仓根>/skillpack/skills/references/mcp-lazy-seeds/<name>.json）")
    ap.add_argument("--wait", type=int, default=40, help="拉起后等待监听的最长秒数")
    args = ap.parse_args()

    ctx = Ctx(args)
    ctx.log(f"proxy start: url={ctx.url} port={ctx.port} launcher={'yes' if ctx.launcher else 'no'}")
    server = build_server(ctx)
    try:
        anyio.run(_serve, server)
    except KeyboardInterrupt:
        pass
    except BaseException as e:                          # noqa: BLE001
        ctx.log(f"fatal: {e!r}")
        raise
    return 0


if __name__ == "__main__":
    sys.exit(main())
