#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""relab2-tools-mcp.py —— 把**本机工具链**暴露成 MCP 工具（stdio）。

为什么存在（2026-10-15）：
  本仓本地有几十个 CLI 工具（diec / floss / capa / pe-sieve / jadx / r2 / nmap / hashcat / frida …），
  现在只能靠模型**自己想起来**去 shell 里敲，还要自己拼路径。REA 的做法是把工具全包成 MCP 工具，
  模型一伸手就有；本仓目前只包了 4 个分析引擎（IDA/Ghidra/x64dbg/angr）。
  本服务器补上这一块，并且**不写死任何路径** —— 工具定位每次实时走探测层
  （`Bootstrap.ps1` 的 `Resolve-ReverseToolSpec`，四级递进），所以**换机自动适配**。

暴露的工具：
  · `local_tools`    —— 本机工具链**实时**清单（可用 / 缺件），永不过期
  · `run_tool`       —— 按 tool id 调用本机任一工具（路径由探测层解析）
  · `triage_target`  —— 一次跑完「第一眼」该跑的那几把刀，返回结构化摘要

用法（宿主 mcp.json 注册成 stdio 服务器）：
  { "command": "<venv python>",
    "args": ["<仓根>/skillpack/skills/scripts/relab2-tools-mcp.py",
             "--skill-root", "<技能包根>", "--tool-root", "<工具根>"] }

日志：%LOCALAPPDATA%\\reverse-skill\\tools-mcp\\tools-mcp.log
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import anyio
import mcp.types as types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

# 常用工具 id —— 覆盖四大战场。「没有的」当场报出来，不去猜。
KNOWN_TOOLS = [
    # 逆向 / 分析
    "diec", "die", "floss", "capa", "pe-sieve", "scyllahide",
    "idat", "ida", "ghidra", "ghidra_headless", "x64dbg", "x32dbg",
    "radare2", "r2", "rabin2", "ROPgadget", "ropper", "gdb", "cdb",
    # 移动
    "jadx", "apktool", "frida", "objection", "apksigner", "scrcpy",
    # 托管
    "dotnet", "de4dot", "ilspycmd",
    # 固件 / 解包
    "binwalk", "unblob", "upx", "7z",
    # 网络 / 抓包
    "nmap", "ncat", "nping", "tshark", "wireshark", "mitmdump", "mitmproxy", "httpx",
    # 口令 / 渗透
    "hashcat", "sqlmap", "nuclei", "ffuf", "burpsuite", "john", "yara",
    # 运行时
    "python", "java", "node", "npm", "go", "gcc", "jq", "ffmpeg", "git", "gh",
]

PROBE_PS = r"""
$ErrorActionPreference='Continue'
. "{bootstrap}"
$ids = @({ids})
$out = @()
foreach ($id in $ids) {{
  $r = $null
  try {{ $r = Resolve-ReverseToolSpec -Name $id -ErrorAction Stop }} catch {{ }}
  if ($r -and $r.Available) {{
    $out += [pscustomobject]@{{ id=$id; ok=$true; via=("" + $r.Via); cmd=("" + $r.Command) }}
  }} else {{
    $out += [pscustomobject]@{{ id=$id; ok=$false; via=''; cmd='' }}
  }}
}}
$out | ConvertTo-Json -Compress
"""


class Ctx:
    def __init__(self, args: argparse.Namespace) -> None:
        self.skill_root = args.skill_root
        self.tool_root = args.tool_root
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        self.state = Path(base) / "reverse-skill" / "tools-mcp"
        self.state.mkdir(parents=True, exist_ok=True)
        self.log_file = self.state / "tools-mcp.log"
        self._cache: tuple[float, dict[str, dict]] | None = None

    def log(self, msg: str) -> None:
        try:
            with self.log_file.open("a", encoding="utf-8") as f:
                f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")
        except OSError:
            pass

    # ------------------------------------------------------------ 探测层
    def _bootstrap(self) -> Path | None:
        for cand in (
            Path(self.skill_root) / "skills" / "scripts" / "lib" / "Bootstrap.ps1",
            Path(self.skill_root) / "skillpack" / "skills" / "scripts" / "lib" / "Bootstrap.ps1",
        ):
            if cand.exists():
                return cand
        return None

    def probe(self, ttl: int = 600) -> dict[str, dict]:
        """实时探测本机工具链。结果带 TTL 缓存，避免每次都跑 5–25 秒的四级递进。"""
        if self._cache and (time.time() - self._cache[0]) < ttl:
            return self._cache[1]
        bs = self._bootstrap()
        if not bs:
            self.log(f"Bootstrap.ps1 not found under {self.skill_root}")
            return {}
        ids = ",".join(f"'{i}'" for i in KNOWN_TOOLS)
        script = PROBE_PS.format(bootstrap=str(bs).replace("\\", "\\\\"), ids=ids)
        try:
            p = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
        except (OSError, subprocess.TimeoutExpired) as e:
            self.log(f"probe failed: {e!r}")
            return {}
        raw = (p.stdout or "").strip()
        try:
            data = json.loads(raw)
        except ValueError:
            self.log(f"probe output not JSON: {raw[:300]!r}")
            return {}
        if isinstance(data, dict):
            data = [data]
        table = {d["id"]: d for d in data if isinstance(d, dict) and d.get("id")}
        self._cache = (time.time(), table)
        ok = sum(1 for d in table.values() if d.get("ok"))
        self.log(f"probe: {ok}/{len(table)} available")
        return table

    # ------------------------------------------------------------ 执行
    def run(self, tool_id: str, argv: list[str], timeout: int) -> dict:
        table = self.probe()
        ent = table.get(tool_id)
        if not ent or not ent.get("ok"):
            return {"ok": False,
                    "error": f"本机没有可用工具 '{tool_id}'。可用清单见 local_tools。",
                    "available": sorted(k for k, v in table.items() if v.get("ok"))}
        cmd = ent["cmd"]
        try:
            p = subprocess.run([cmd, *argv], capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=timeout)
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": f"超时（{timeout}s）", "command": cmd, "argv": argv}
        except OSError as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}", "command": cmd}
        self.log(f"run {tool_id} rc={p.returncode}")
        return {"ok": p.returncode == 0, "exit": p.returncode, "command": cmd, "argv": argv,
                "stdout": (p.stdout or "")[:20000], "stderr": (p.stderr or "")[:4000]}


def build_server(ctx: Ctx) -> Server:
    server: Server = Server("relab2-tools")

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return [
            types.Tool(
                name="local_tools",
                description=("本机工具链的**实时**清单（可用 / 缺件 + 实际路径 + 从哪找到的）。"
                             "任何「本机有没有 X 工具」的问题都走这里 —— 不要猜、不要读缓存表。"),
                inputSchema={"type": "object", "properties": {
                    "refresh": {"type": "boolean", "description": "true = 忽略缓存重新探测（约 5–25s）"}}},
            ),
            types.Tool(
                name="run_tool",
                description=("调用本机任一已登记工具。路径由探测层实时解析（换机自动适配），"
                             "不需要也不允许自己拼路径。示例：tool_id='diec', args=['--extended','C:/x.exe']。"),
                inputSchema={"type": "object", "properties": {
                    "tool_id": {"type": "string", "description": "工具 id，如 diec / floss / capa / jadx / r2 / nmap"},
                    "args": {"type": "array", "items": {"type": "string"}, "description": "命令行参数数组"},
                    "timeout_s": {"type": "integer", "description": "超时秒数，默认 180"}},
                    "required": ["tool_id"]},
            ),
            types.Tool(
                name="triage_target",
                description=("对目标做「第一眼」三连：格式/壳（diec）→ 关键字符串（floss）→ 能力命中（capa）。"
                             "本机缺哪把刀就跳过哪一步并在结果里注明，不报错。"),
                inputSchema={"type": "object", "properties": {
                    "path": {"type": "string", "description": "目标文件绝对路径"},
                    "timeout_s": {"type": "integer", "description": "每步超时秒数，默认 180"}},
                    "required": ["path"]},
            ),
            types.Tool(
                name="find_capability",
                description=("按**能力**找本机工具 —— 「谁能解固件」「谁能抓包」「谁能反编译」。"
                             "能力索引是运行时扫描出来的（按规则 + help 关键词归类），"
                             "所以**换机、装了我们没见过的同类新工具，也能被认出来**；不看工具名清单。"
                             "capability 留空 = 列出本机所有已识别能力及数量。"),
                inputSchema={"type": "object", "properties": {
                    "capability": {"type": "string",
                                   "description": "能力 id，如 firmware-unpack / static-decompile / portscan / websql / capture / crack / apk / hook / dynamic-debug"},
                    "rescan": {"type": "boolean", "description": "true = 先重新扫描本机（首次或换机后跑一次）"}}},
            ),
        ]

    def _cap_index(args: list[str], timeout: int = 300) -> tuple[int, str]:
        """在同一目录下直接 import capability-index.py，**不起子进程** ——
        子进程会把 stdio 管道一起带进去，在 MCP 服务器里极易把调用拖住（2026-10-15 实测）。
        找不到索引时按需重建。"""
        try:
            import importlib.util
            here = Path(__file__).resolve().parent
            spec = importlib.util.spec_from_file_location("capindex", here / "capability-index.py")
            mod = importlib.util.module_from_spec(spec)          # type: ignore[arg-type]
            spec.loader.exec_module(mod)                         # type: ignore[union-attr]
        except Exception as e:                                   # noqa: BLE001
            return 2, f"加载 capability-index 失败：{e}"

        want_scan = "--scan" in args
        find = None
        if "--find" in args:
            i = args.index("--find")
            find = args[i + 1] if i + 1 < len(args) else None
        if want_scan or mod.load() is None:
            idx = mod.build(probe_help=False)
            mod.state_dir().joinpath("capabilities.json").write_text(
                json.dumps(idx, ensure_ascii=False, indent=1), encoding="utf-8")
        else:
            idx = mod.load()
        if find is None:
            lines = [f"扫描 {idx['candidates']} 个候选，未知 {idx['unknown_count']} 个"]
            for c, lst in idx["capabilities"].items():
                lines.append(f"  {c:18s} {len(lst):3d} 个  e.g. "
                             + ", ".join(x["tool"] for x in lst[:4]))
            return 0, "\n".join(lines)
        lst = idx["capabilities"].get(find) or []
        if not lst:
            return 1, f"本机没有能做「{find}」的工具。"
        return 0, "\n".join(f"  {x['tool']:22s} {x['why']:26s} {x['path']}" for x in lst)

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> types.CallToolResult:
        if name == "local_tools":
            table = await anyio.to_thread.run_sync(
                lambda: ctx.probe(ttl=0 if arguments.get("refresh") else 600))
            ok = sorted(k for k, v in table.items() if v.get("ok"))
            no = sorted(k for k, v in table.items() if not v.get("ok"))
            body = {
                "可用": [{"id": k, "via": table[k]["via"], "cmd": table[k]["cmd"]} for k in ok],
                "缺件": no,
                "统计": f"{len(ok)}/{len(table)} 可用",
                "定位方式": "Bootstrap.ps1 → Resolve-ReverseToolSpec（env → PATH → 别名表 → 工具根递归）",
            }
            return types.CallToolResult(content=[types.TextContent(
                type="text", text=json.dumps(body, ensure_ascii=False, indent=1))])

        if name == "run_tool":
            res = await anyio.to_thread.run_sync(
                lambda: ctx.run(arguments.get("tool_id", ""), list(arguments.get("args") or []),
                                int(arguments.get("timeout_s") or 180)))
            return types.CallToolResult(
                isError=not res.get("ok"),
                content=[types.TextContent(type="text",
                                           text=json.dumps(res, ensure_ascii=False, indent=1)[:24000])])

        if name == "triage_target":
            path = arguments.get("path", "")
            tmo = int(arguments.get("timeout_s") or 180)
            steps = [("diec", ["--extended", path]), ("floss", [path])]
            out: dict = {"target": path, "steps": []}
            for tid, argv in steps:
                r = await anyio.to_thread.run_sync(lambda t=tid, a=argv: ctx.run(t, a, tmo))
                out["steps"].append({"tool": tid, "ok": r.get("ok"),
                                     "error": r.get("error"),
                                     "stdout": (r.get("stdout") or "")[:6000]})
            r = await anyio.to_thread.run_sync(lambda: ctx.run("capa", [path], tmo))
            out["steps"].append({"tool": "capa", "ok": r.get("ok"), "error": r.get("error"),
                                 "stdout": (r.get("stdout") or "")[:6000]})
            out["读法"] = ("壳/编译器/diec 输出是线索不是结论；缺哪一步看 error 字段。"
                           "下一步按信号选刀，见 reverse-engineering/references/signal-to-tool-decision.md")
            return types.CallToolResult(content=[types.TextContent(
                type="text", text=json.dumps(out, ensure_ascii=False, indent=1)[:24000])])

        if name == "find_capability":
            cap = (arguments.get("capability") or "").strip()
            if arguments.get("rescan") or not cap:
                rc, out = await anyio.to_thread.run_sync(
                    lambda: _cap_index(["--scan", "--no-help-probe"]))
                if rc != 0 and not cap:
                    return types.CallToolResult(isError=True, content=[types.TextContent(
                        type="text", text=f"扫描失败：{out[:2000]}")])
                if not cap:
                    return types.CallToolResult(content=[types.TextContent(type="text", text=out[:8000])])
            rc, out = await anyio.to_thread.run_sync(lambda: _cap_index(["--find", cap]))
            return types.CallToolResult(
                isError=(rc != 0),
                content=[types.TextContent(type="text", text=out[:8000] or f"本机没有能做「{cap}」的工具。")])

        return types.CallToolResult(isError=True, content=[types.TextContent(
            type="text", text=f"未知工具名：{name}")])

    return server


async def _serve(server: Server) -> None:
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


def main() -> int:
    ap = argparse.ArgumentParser(description="把本机工具链暴露成 MCP 工具")
    ap.add_argument("--skill-root", default=os.environ.get("REVERSE_SKILL_ROOT", ""),
                    help="技能包根（含 skills/scripts/lib/Bootstrap.ps1）")
    ap.add_argument("--tool-root", default=os.environ.get("REVERSE_TOOL_ROOT", ""))
    a = ap.parse_args()
    ctx = Ctx(a)
    ctx.log(f"start skill_root={ctx.skill_root!r} tool_root={ctx.tool_root!r}")
    try:
        anyio.run(_serve, build_server(ctx))
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
