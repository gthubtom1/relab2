# -*- coding: utf-8 -*-
"""宿主识别：认出各智能体的家目录、入口文件名、有没有正在跑。

活进程检测只认 tasklist 的进程名，不 import psutil、不过度声称：
只匹配同名的可执行文件，node 承载的那几家会在 notes 里如实说明检测不到。

只读本机家目录。不写任何文件。
"""
from __future__ import annotations

import argparse
import csv
import io
import os
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path

try:
    from . import _bundle_lib  # 装进包后作为包内模块使用
except ImportError:
    import _bundle_lib  # 独立运行


@dataclass
class HostSpec:
    id: str
    display: str
    rel: str                                   # 相对 %USERPROFILE% 的家目录
    entry: str                                 # 主入口文件名
    processes: tuple = ()# tasklist 里同名的可执行名（不带 .exe）
    alternates: tuple = ()                     # 其它也认的入口文件名
    note: str = ""
    # ★ 2026-10-14：有的宿主**把底模和规则分开放**，不是一份入口文件塞三段。
    #   omp 就是：人设 → PERSONALITY.md，规则 → RULES.md。
    #   非空时表示「底模卡写到这个文件，其余（中枢段 + 指引卡）仍写 entry」。
    entry_base: str = ""


# 每家的入口文件名按它实际会读的那份来。alternates 是「这家也认」的兜底。
HOSTS = (
    HostSpec("codex", "OpenAI Codex", ".codex", "AGENTS.md", ("codex",)),
    HostSpec("claude", "Claude Code", ".claude", "CLAUDE.md", ("claude",),
             note="npm 装的版本进程名是 node.exe，只按同名认会漏；见 running_hint。"),
    HostSpec("cursor", "Cursor", ".cursor", "AGENTS.md", ("cursor",),
             alternates=("rules/hubcore.mdc",)),
    HostSpec("grok", "Grok CLI", ".grok", "AGENTS.md", ("grok",)),
    HostSpec("gemini", "Gemini CLI", ".gemini", "GEMINI.md", ("gemini",)),
    HostSpec("deepseek", "DeepSeek", ".deepseek", "DEEPSEEK.md", ("deepseek",)),
    HostSpec("hermes", "Hermes", ".hermes", "SOUL.md", ("hermes",)),
    HostSpec("pi", "Pi", ".pi/agent", "AGENTS.md", ("pi",),
             note="Pi 的全局入口在 ~/.pi/agent/AGENTS.md。"),
    HostSpec("omp", "omp", ".omp/agent", "RULES.md", (),
             alternates=("AGENTS.md",),
             entry_base="PERSONALITY.md",
             note="★ 两文件形态（全项目唯一一家）：人设 → PERSONALITY.md，规则 → RULES.md。"
                  "没有 AGENTS.md，也不需要把三段融成一份。"),
    HostSpec("dsh", "DSH", ".dsh", "AGENTS.md", ("dsh",), alternates=("FUSION.md",)),
    HostSpec("zcode", "ZCode", ".zcode", "AGENTS.md", ("zcode",)),
    HostSpec("opencode", "opencode", ".config/opencode", "AGENTS.md", ("opencode",)),
    HostSpec("windsurf", "Windsurf", ".windsurf", "AGENTS.md", ("windsurf",)),
    HostSpec("aider", "Aider", ".aider", "AGENTS.md", ("aider",), alternates=("CONVENTIONS.md",)),
)

BY_ID = {h.id: h for h in HOSTS}


# ---------------------------------------------------------------- 活进程

def running_images():
    """当前运行的进程镜像名（小写）。tasklist 认不到就返回空集，不假装。"""
    try:
        proc = subprocess.run(
            ["tasklist", "/FO", "CSV", "/NH"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return set(), "tasklist 调不起来，进程状态未知"
    if proc.returncode != 0:
        return set(), "tasklist 返回码 %d，进程状态未知" % proc.returncode
    # 中文 Windows 上 tasklist 可能是 GBK。镜像名都是 ASCII，容错解码足够。
    text = proc.stdout.decode("utf-8", "replace")
    names = set()
    for row in csv.reader(io.StringIO(text)):
        if row:
            names.add(row[0].strip().lower())
    return names, None


# ---------------------------------------------------------------- 宿主解析

@dataclass
class HostInfo:
    id: str
    display: str
    home: str
    entry: str
    entry_path: str
    exists: bool
    entry_exists: bool
    installed: bool
    running: bool
    running_known: bool = True
    running_detail: str = ""
    running_hint: str = ""
    note: str = ""
    alternates: tuple = field(default_factory=tuple)

    def to_dict(self):
        d = asdict(self)
        d["alternates"] = list(self.alternates)
        return d


def user_home() -> Path:
    return Path(os.environ.get("USERPROFILE") or Path.home())


def _installed_marker(home: Path) -> bool:
    return (home / _bundle_lib.PKG_DIRNAME / _bundle_lib.MANIFEST_NAME).is_file()


def _resolve_entry(home: Path, spec: HostSpec) -> str:
    for name in (spec.entry,) + spec.alternates:
        if (home / name).is_file():
            return name
    return spec.entry


def detect(home: Path, spec: HostSpec, images=None) -> HostInfo:
    home = Path(home)
    exists = home.is_dir()
    entry = _resolve_entry(home, spec) if exists else spec.entry
    err = None
    if images is None:
        images, err = running_images()
        running_detail = err or ""
    else:
        running_detail = ""
    running = bool(exists and any(p + ".exe" in images for p in spec.processes))
    node_host = spec.id in {"claude", "cursor", "gemini", "opencode", "windsurf", "aider", "pi"}
    known = not bool(err) and not (node_host and "node.exe" in images)
    hits = [p + ".exe" for p in spec.processes if p + ".exe" in images]
    return HostInfo(
        id=spec.id, display=spec.display, home=str(home), entry=entry,
        entry_path=str(home / entry), exists=exists,
        entry_exists=(home / entry).is_file(), installed=_installed_marker(home),
        running=running,
        running_known=known,
        running_detail=running_detail or ("同名进程：%s" % "、".join(hits) if hits else "未发现同名进程"),
        running_hint=spec.note, note=spec.note, alternates=spec.alternates,
    )


def scan(base: Path = None):
    """扫全部已知宿主。base 默认 %USERPROFILE%。"""
    base = Path(base) if base else user_home()
    images, err = running_images()
    out = []
    for spec in HOSTS:
        info = detect(base / Path(spec.rel), spec, images)
        if err:
            info.running_detail = err
        out.append(info)
    return out


def resolve_host(home: Path):
    """给定一个家目录路径，判断它是哪一家；不是已知宿主就返回 None。"""
    home = Path(home).resolve()
    for spec in HOSTS:
        if (user_home() / Path(spec.rel)).resolve() == home:
            return spec
    return None


def two_file_host_shape(home: Path):
    """按**目录形状**认「两文件形态」的家（omp：PERSONALITY.md + RULES.md）。

    `resolve_host` 只认 `USERPROFILE/<rel>`；验收用的假家（TEMP/FAKE-UA/.claude…）
    一律被判成 custom。但两文件形态的宿主**装错文件名的代价很大**（底模卡写进
    规则文件、而且卸不干净），所以给它一个「只看最后两级目录名」的识别，
    专门给 install.py 的前置拒绝用。

    ★ 只返回 `entry_base` 非空的 spec —— 对其他宿主零影响，不存在误判。
    """
    home = Path(home).resolve()
    parts = [p.lower() for p in home.parts]
    tail2 = "\\".join(parts[-2:])
    for spec in HOSTS:
        if not spec.entry_base:
            continue
        rel = str(spec.rel).replace("/", "\\").strip("\\").lower()
        if rel == tail2 or parts[-1] == rel or tail2.endswith("\\" + rel) or rel.endswith("\\" + tail2):
            return spec
    return None


def host_id_for(home: Path) -> str:
    spec = resolve_host(home)
    return spec.id if spec else "custom"


def entry_name_for(home: Path) -> str:
    spec = resolve_host(home)
    return _resolve_entry(Path(home), spec) if spec else "AGENTS.md"


# ---------------------------------------------------------------- CLI

def _print_table(rows):
    print("%-11s %-14s %-7s %-6s %-6s %-6s  %s" %
          ("ID", "显示名", "存在", "入口", "已装", "在跑", "家目录"))
    for r in rows:
        print("%-11s %-14s %-7s %-6s %-6s %-6s  %s" % (
            r["id"], r["display"], "是" if r["exists"] else "否",
            r["entry"], "是" if r["installed"] else "否",
            "是" if r["running"] else "否", r["home"]))


def main(argv=None):
    ap = argparse.ArgumentParser(prog="hosts.py", description="认出各家智能体的家目录与活进程")
    ap.add_argument("--id", help="只看某一家")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    rows = [r.to_dict() for r in scan()]
    if args.id:
        rows = [r for r in rows if r["id"] == args.id]
        if not rows:
            print("没有这家宿主：%s" % args.id, file=sys.stderr)
            return 2
    if args.json:
        import json
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0
    _print_table(rows)
    miss = [r for r in rows if r["running"]]
    if miss:
        print("\n正在跑（装之前必须先关掉）：%s" % "、".join(r["id"] for r in miss))
    hint = [r for r in rows if r["note"] and r["exists"]]
    if hint:
        print("\n进程名检测的已知盲区：")
        for r in hint:
            print("  %-11s %s" % (r["id"], r["note"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
