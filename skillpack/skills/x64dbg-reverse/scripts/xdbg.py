#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""xdbg.py —— x64dbg MCP 客户端（HTTP / JSON-RPC 2.0）。

token 是**每个 x64dbg 实例自己的**，从它的 mcp_config.json 读（不写死、不猜）。

用法：
    python xdbg.py <Tool> ['<json-args>']      # 调一个 MCP 工具
    python xdbg.py --list                      # 列出可用工具（名字 + 一行说明）
    python xdbg.py --raw <method> ['<json>']   # 直接发 JSON-RPC（如 tools/list）

环境变量：
    X64DBG_MCP_URL    默认 http://127.0.0.1:9094/mcp
    X64DBG_MCP_TOKEN  指定则优先；否则去 mcp_config.json 里找

退出码：0 成功／1 调用出错／2 连不上或取不到 token
"""
from __future__ import annotations

import glob
import json
import os
import sys
import urllib.error
import urllib.request

DEFAULT_URL = os.environ.get("X64DBG_MCP_URL", "http://127.0.0.1:9094/mcp")
TOKEN_GLOBS = [
    os.path.join(os.environ.get("REVERSE_TOOL_ROOT", r"D:\Tools"), "disasm", "x64dbg", "release", "x64", "mcp_config.json"),
    os.path.join(os.environ.get("REVERSE_TOOL_ROOT", r"D:\Tools"), "disasm", "x64dbg", "release", "x32", "mcp_config.json"),
]


def find_token() -> str:
    tok = os.environ.get("X64DBG_MCP_TOKEN")
    if tok:
        return tok.strip()
    for pat in TOKEN_GLOBS:
        for p in glob.glob(pat):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
            except Exception:
                continue
            for k in ("AuthToken", "authToken", "token"):
                if cfg.get(k):
                    return str(cfg[k]).strip()
    return ""


def rpc(method: str, params=None, rid: int = 1, timeout: int = 60):
    token = find_token()
    if not token:
        print("ERROR: 取不到 token —— 设 X64DBG_MCP_TOKEN，或让 mcp_config.json 可读。", file=sys.stderr)
        sys.exit(2)
    body = json.dumps({"jsonrpc": "2.0", "id": rid, "method": method, "params": params or {}}).encode()
    req = urllib.request.Request(
        DEFAULT_URL, data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json",
                 "Authorization": "Bearer " + token},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        print(f"ERROR: HTTP {e.code} —— token 不对，或 x64dbg 没在跑。", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(f"ERROR: 连不上 {DEFAULT_URL} —— {e}。先跑 scripts/start.ps1，再跑 ../scripts/mcp-status.ps1 确认 LISTEN。", file=sys.stderr)
        sys.exit(2)


def call_tool(name: str, args: dict):
    out = rpc("tools/call", {"name": name, "arguments": args})
    res = out.get("result", out)
    for c in (res.get("content") or []):
        if c.get("type") == "text":
            print(c["text"])
    sc = res.get("structuredContent")
    if sc:
        print(json.dumps(sc, ensure_ascii=False, indent=2))
    if out.get("error"):
        print("ERROR: " + json.dumps(out["error"], ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


def main() -> int:
    argv = sys.argv[1:]
    if not argv:
        print(__doc__)
        return 0
    if argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    if argv[0] == "--list":
        out = rpc("tools/list")
        for t in (out.get("result") or out).get("tools", []):
            print(f"{t['name']:<28} {(t.get('description') or '').splitlines()[0][:90]}")
        return 0
    if argv[0] == "--raw":
        method = argv[1] if len(argv) > 1 else "tools/list"
        params = json.loads(argv[2]) if len(argv) > 2 else {}
        print(json.dumps(rpc(method, params), ensure_ascii=False, indent=2))
        return 0
    name = argv[0]
    args = json.loads(argv[1]) if len(argv) > 1 else {}
    call_tool(name, args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
