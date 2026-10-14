#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""register-mcp.py —— 把本包的 5 条 MCP 通道**一键注册**进宿主（幂等 + 备份 + 干跑）。

为什么存在（2026-10-15，独立审计实测）：
  审计判定「换机 = 一条命令」不满足：`relab2.ps1 setup` 只代劳了 10 步里的 3 步，
  第 8 步「重写 MCP 注册」还得人手工逐条改。于是把它自动化。

出厂 5 条通道（两类形态，见 环境初始化.md §11.1-B 第 10 条）：
  ① 直连 stdio   pyghidra-mcp / angr-mcp / relab2-tools   —— 宿主按会话自动拉起
  ② stdio·懒启   idapro / x64dbg-mcp                        —— 走 mcp-lazy-http.py，后端被调用时才起

本脚本不猜路径：Python 解释器靠**实测 import** 认（哪个 venv 里真有 pyghidra_mcp / angr 就用哪个），
x64dbg 的 Bearer token 靠**读它自己的实例配置**拿。找不到就跳过并报出来，绝不写一个假路径。

用法：
  python register-mcp.py --skill-root <技能包根>                 # 真写（自动备份）
  python register-mcp.py --skill-root <技能包根> --dry-run        # 只打印将要做的事
  python register-mcp.py --skill-root <技能包根> --host omp --json
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import time

HOME = pathlib.Path(os.path.expanduser("~"))

# 宿主家目录 → 注册表位置（只列本包实测过的；其余宿主留给工作台）
HOST_TARGETS = {
    "omp": HOME / ".omp" / "agent" / "mcp.json",
}


def log(msg: str, quiet: bool = False) -> None:
    if not quiet:
        print(msg)


def find_python_with(module: str, tool_root: pathlib.Path, extra: list[pathlib.Path]) -> pathlib.Path | None:
    """在本机找「import <module> 真的成功」的 python。宁可不注册，也不写一个假路径。
    ★ 2026-10-15 实测教训：`python-venv` 里也有 angr（9.2.213），而专用的 `angr-mcp-venv` 是 10.0.3。
      不加偏好就会**把 angr 从 10.0.3 降级到 9.2.213**。所以：**路径里带模块名的 venv 优先**。"""
    cands: list[pathlib.Path] = []
    for pat in ("runtime/*venv*/Scripts/python.exe", "runtime/*/Scripts/python.exe",
                "runtime/python*/python.exe", "*venv*/Scripts/python.exe"):
        cands += list(tool_root.glob(pat))
    cands += [p for p in extra if p.exists()]
    cands += [pathlib.Path(sys.executable)]
    # 去重 + 排序：路径里带模块名 / 带 mcp 专用 venv 的排前面
    seen: set[str] = set()
    uniq: list[pathlib.Path] = []
    for py in cands:
        k = str(py).lower()
        if k in seen or not py.exists():
            continue
        seen.add(k)
        uniq.append(py)

    def score(p: pathlib.Path) -> tuple:
        s = str(p).lower()
        return (0 if module.replace("_", "-") in s or module in s else 1,
                0 if "mcp" in s else 1,
                len(s))

    for py in sorted(uniq, key=score):
        try:
            r = subprocess.run([str(py), "-c", f"import {module}"],
                               capture_output=True, timeout=60,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if r.returncode == 0:
                return py
        except (OSError, subprocess.TimeoutExpired):
            continue
    return None


def read_x64dbg_token(tool_root: pathlib.Path) -> str | None:
    """x64dbg 的 Bearer token 是**每个实例自己的**，写在它自己的 mcp_config.json 里。"""
    for pat in ("disasm/x64dbg/release/x64/mcp_config.json", "**/x64dbg/**/mcp_config.json"):
        for f in tool_root.glob(pat):
            try:
                d = json.loads(f.read_text(encoding="utf-8", errors="replace"))
            except Exception:  # noqa: BLE001
                continue
            for key in ("AuthToken", "authToken", "token", "Token"):
                if isinstance(d.get(key), str) and d[key]:
                    return d[key]
    return None


def build_entries(skill_root: pathlib.Path, tool_root: pathlib.Path,
                  quiet: bool = False, existing: dict | None = None) -> tuple[dict, list[str]]:
    """造出 5 条注册项。返回 (entries, 缺件说明)。
    ★ 已存在的宿主配置里那些**本机专属 env**（JAVA_HOME / GHIDRA_INSTALL_DIR…）要保下来 ——
      它们可能只写在 mcp.json 里、而不在进程环境里；直接覆盖会**把能跑的配置改坏**。"""
    existing = existing or {}
    notes: list[str] = []
    skills = skill_root / "skillpack" / "skills"
    if not skills.exists():
        skills = skill_root / "skills"
    lazy = skills / "scripts" / "mcp-lazy-http.py"
    toolbox = skills / "scripts" / "relab2-tools-mcp.py"
    entries: dict[str, dict] = {}

    # ① pyghidra-mcp（直连 stdio）
    py_g = find_python_with("pyghidra_mcp", tool_root, [])
    if py_g:
        env = dict((existing.get("pyghidra-mcp") or {}).get("env") or {})
        if os.environ.get("JAVA_HOME"):
            env["JAVA_HOME"] = os.environ["JAVA_HOME"]
        if os.environ.get("GHIDRA_INSTALL_DIR"):
            env["GHIDRA_INSTALL_DIR"] = os.environ["GHIDRA_INSTALL_DIR"]
        env.setdefault("PYTHONUNBUFFERED", "1")
        e = {"command": str(py_g),
             "args": ["-m", "pyghidra_mcp", "--project-path",
                      str(skill_root / "work" / "pyghidra-mcp-projects")]}
        if env:
            e["env"] = env
        entries["pyghidra-mcp"] = e
    else:
        notes.append("pyghidra-mcp：找不到能 import pyghidra_mcp 的 python —— 跳过（没装）")

    # ② angr-mcp（直连 stdio）
    py_a = find_python_with("angr", tool_root, [])
    if py_a:
        entries["angr-mcp"] = {"command": str(py_a), "args": ["-m", "angr.mcp"]}
    else:
        notes.append("angr-mcp：找不到能 import angr 的 python —— 跳过（没装）")

    # ③ relab2-tools（直连 stdio，工具箱 MCP）
    if toolbox.exists():
        py_t = py_g or py_a or find_python_with("mcp", tool_root, [])
        if py_t:
            entries["relab2-tools"] = {"command": str(py_t),
                                       "args": [str(toolbox), "--skill-root", str(skill_root)]}
        else:
            notes.append("relab2-tools：找不到能 import mcp 的 python —— 跳过")
    else:
        notes.append(f"relab2-tools：找不到 {toolbox} —— 跳过")

    # ④ idapro（stdio·懒启）
    ida_start = skills / "ida-reverse" / "scripts" / "start.ps1"
    if lazy.exists() and ida_start.exists() and (py_g or py_a):
        entries["idapro"] = {
            "command": str(py_g or py_a),
            "args": [str(lazy), "--name", "idapro",
                     "--url", "http://127.0.0.1:13337/mcp", "--port", "13337",
                     "--launcher", f'powershell -NoProfile -ExecutionPolicy Bypass -File "{ida_start}"',
                     "--wait", "60"],
        }
    else:
        notes.append(f"idapro：缺 {lazy} 或 {ida_start} —— 跳过")

    # ⑤ x64dbg-mcp（stdio·懒启）
    x64_start = tool_root / "cli" / "start-x64dbg-mcp.ps1"
    token = read_x64dbg_token(tool_root)
    if lazy.exists() and x64_start.exists() and (py_g or py_a):
        args = [str(lazy), "--name", "x64dbg-mcp",
                "--url", "http://127.0.0.1:9094/mcp", "--port", "9094",
                "--launcher", f'powershell -NoProfile -ExecutionPolicy Bypass -File "{x64_start}"',
                "--wait", "60"]
        if token:
            args += ["--header", f"Authorization: Bearer {token}"]
        else:
            notes.append("x64dbg-mcp：读不到 Bearer token（它自己的 mcp_config.json）—— 先注册，"
                         "等 x64dbg 起来后再补 --header")
        entries["x64dbg-mcp"] = {"command": str(py_g or py_a), "args": args}
    else:
        notes.append(f"x64dbg-mcp：缺 {lazy} 或 {x64_start} —— 跳过")

    return entries, notes


def _same_entry(a: dict | None, b: dict) -> bool:
    """功能等价就算「不用改」——**参数顺序不同不算差异**（否则每次跑都会无意义地重写配置，
    还会平白留下一堆 .bak）。"""
    if not a:
        return False
    if a.get("command") != b.get("command") or a.get("type") != b.get("type"):
        return False
    if sorted(a.get("args") or []) != sorted(b.get("args") or []):
        return False
    if (a.get("env") or {}) != (b.get("env") or {}):
        return False
    if (a.get("headers") or {}) != (b.get("headers") or {}):
        return False
    if a.get("url") != b.get("url"):
        return False
    return True


def merge_into(path: pathlib.Path, entries: dict, dry: bool, quiet: bool) -> None:
    schema = None
    data: dict = {}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            schema = data.get("$schema")
        except ValueError:
            log(f"  ！{path} 不是合法 JSON，跳过", quiet)
            return
    servers = data.setdefault("mcpServers", {})
    changed = []
    for name, e in entries.items():
        if not _same_entry(servers.get(name), e):
            servers[name] = e
            changed.append(name)
    if not changed:
        log(f"  {path}：{len(entries)} 条已在位（功能等价），无需改动", quiet)
        return
    if dry:
        log(f"  [干跑] {path} 将更新：{changed}", quiet)
        return
    if path.exists():
        bak = path.with_suffix(path.suffix + f".bak-regmcp-{time.strftime('%Y%m%d%H%M%S')}")
        shutil.copy2(path, bak)
        log(f"  备份 → {bak.name}", quiet)
    path.parent.mkdir(parents=True, exist_ok=True)
    out = {"$schema": schema} if schema else {}
    out["mcpServers"] = servers
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    log(f"  写入 {path}（更新 {len(changed)} 条：{changed}）；重启宿主后生效", quiet)


def main() -> int:
    ap = argparse.ArgumentParser(description="把本包 5 条 MCP 通道一键注册进宿主")
    ap.add_argument("--skill-root", default=os.environ.get("REVERSE_SKILL_ROOT") or ".",
                    help="技能包根/仓根（含 skillpack/skills）")
    ap.add_argument("--tool-root", default=os.environ.get("REVERSE_TOOL_ROOT") or r"D:\Tools")
    ap.add_argument("--host", default="omp", choices=sorted(HOST_TARGETS))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    skill_root = pathlib.Path(a.skill_root).resolve()
    tool_root = pathlib.Path(a.tool_root)
    target = HOST_TARGETS[a.host]
    existing: dict = {}
    if target.exists():
        try:
            existing = (json.loads(target.read_text(encoding="utf-8")).get("mcpServers") or {})
        except ValueError:
            existing = {}
    entries, notes = build_entries(skill_root, tool_root, a.quiet, existing)

    if a.json:
        print(json.dumps({"entries": list(entries), "notes": notes}, ensure_ascii=False))
        return 0

    log(f"=== 注册 MCP 通道（宿主 {a.host}）===", a.quiet)
    log(f"  技能包根 {skill_root}\n  工具根   {tool_root}", a.quiet)
    for n in entries:
        log(f"    · {n}", a.quiet)
    for n in notes:
        log(f"    ！{n}", a.quiet)
    if not entries:
        log("  没有一条可注册 —— 先装 Python 侧依赖（pyghidra_mcp / angr / mcp）", a.quiet)
        return 1
    merge_into(HOST_TARGETS[a.host], entries, a.dry_run, a.quiet)
    return 0


if __name__ == "__main__":
    sys.exit(main())
