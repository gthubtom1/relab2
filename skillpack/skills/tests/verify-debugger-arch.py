#!/usr/bin/env python3
"""verify-debugger-arch.py —— 门禁：32 位目标必须能走到 x32dbg（9095）。

背景（2026-10-18 实测根因）：
  把 32 位 PE 送进 x64dbg，它只弹「请您用 x32dbg 来调试这个程序」，
  `LoadBinary` 永远 `NO_TARGET`，而错误信息里**不写**"架构不匹配" ——
  于是被误判成 "MCP 坏了"。这条链上有两个结构性缺陷，都在这里钉住：

  A. `x64dbg-reverse/scripts/start.ps1` 必须能**按目标 PE 的 Machine 字段**自动选架构与端口；
     靠人记着传 `-Arch x32` 不算修好。
  B. `register-mcp.py` 必须**同时生成** `x64dbg-mcp`(9094) 与 `x32dbg-mcp`(9095) 两条；
     旧版只生成 x64 一条，x32 只能手工加，换机/重新注册就丢。

退出码：0 = 通过；20 = 阻塞失败。
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILLS = os.path.dirname(HERE)
REPO = os.path.dirname(SKILLS)

START = os.path.join(SKILLS, "x64dbg-reverse", "scripts", "start.ps1")
REG = os.path.join(SKILLS, "scripts", "register-mcp.py")
TOOL_LIFECYCLE = os.path.join(SKILLS, "references", "tool-lifecycle.md")

fails = []


def read(p):
    try:
        with open(p, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


# --- A. start.ps1 自动判位数 ---
src = read(START)
if not src:
    fails.append("start.ps1 不存在: %s" % START)
else:
    if not re.search(r"\[string\]\$Target", src):
        fails.append("start.ps1 缺 -Target 参数（无法按目标自动判位数）")
    if "0x014c" not in src.lower():
        fails.append("start.ps1 缺 IMAGE_FILE_MACHINE_I386(0x014C) 判断")
    if "0x8664" not in src.lower():
        fails.append("start.ps1 缺 IMAGE_FILE_MACHINE_AMD64(0x8664) 判断")
    if not re.search(r"0x3C", src, re.I):
        fails.append("start.ps1 未读 e_lfanew(0x3C)，说明没解析 PE 头")
    if not re.search(r"9095", src):
        fails.append("start.ps1 缺 9095（x32 端口）")
    if not re.search(r"\$PSBoundParameters\.ContainsKey\('Arch'\)", src):
        fails.append("start.ps1 未让显式 -Arch 覆盖 -Target（会互相打架）")

# --- B. register-mcp.py 两条通道都生成 ---
reg = read(REG)
if not reg:
    fails.append("register-mcp.py 不存在: %s" % REG)
else:
    if "x32dbg-mcp" not in reg:
        fails.append("register-mcp.py 不生成 x32dbg-mcp（32 位目标无 MCP 通道）")
    if "x64dbg-mcp" not in reg:
        fails.append("register-mcp.py 不生成 x64dbg-mcp")
    if not re.search(r"9095", reg):
        fails.append("register-mcp.py 缺 9095 端口")
    if "read_x64dbg_token(tool_root, arch)" not in reg:
        fails.append("register-mcp.py 未按 arch 读 token（x32/x64 token 会串）")
    if not re.search(r'x64_start\s*=\s*skills\s*/\s*"x64dbg-reverse"', reg):
        fails.append("register-mcp.py 首选启动器不是随仓库走的 x64dbg-reverse/scripts/start.ps1")

# --- C. 文档必须写出这条坑 ---
doc = read(TOOL_LIFECYCLE)
if doc:
    if "请您用 x32dbg" not in doc and "请使用 x32dbg" not in doc:
        fails.append("tool-lifecycle.md 未记录「32 位目标送进 x64dbg」这条坑")
    if "-Target" not in doc:
        fails.append("tool-lifecycle.md 未记录 start.ps1 -Target 用法")

# --- D. 宿主侧若存在 mcp.json，两条 launcher 必须指向随仓库走的 start.ps1 ---
host = os.path.join(os.path.expanduser("~"), ".omp", "agent", "mcp.json")
if os.path.isfile(host):
    try:
        d = json.load(open(host, encoding="utf-8"))
        s = d.get("mcpServers") or d
        for name, port in (("x64dbg-mcp", "9094"), ("x32dbg-mcp", "9095")):
            e = s.get(name)
            if not e:
                fails.append("宿主 mcp.json 缺 %s（%s 无通道）" % (name, port))
                continue
            args = e.get("args") or []
            joined = " ".join(str(a) for a in args)
            if "--port" in args and port not in args:
                fails.append("宿主 %s 端口不是 %s" % (name, port))
            if "start-x64dbg-mcp.ps1" in joined and "x64dbg-reverse" not in joined:
                fails.append("宿主 %s launcher 仍指向机器专属 cli/start-x64dbg-mcp.ps1" % name)
        if s.get("x32dbg-mcp") and "-Arch x32" not in " ".join(str(a) for a in s["x32dbg-mcp"].get("args") or []):
            fails.append("宿主 x32dbg-mcp launcher 缺 -Arch x32")
    except Exception as exc:  # noqa: BLE001
        fails.append("宿主 mcp.json 解析失败: %s" % exc)

if fails:
    print("verify-debugger-arch: %d 处缺陷" % len(fails))
    for f in fails:
        print("  FAIL %s" % f)
    sys.exit(20)
print("verify-debugger-arch: PASS —— start.ps1 按 PE Machine 自动选架构；"
      "register-mcp.py 同时生成 9094/9095 两条通道")
sys.exit(0)
