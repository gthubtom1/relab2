#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""换智能体时的留班/接班。尺只认项目夹，不认聊天记录。"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HUB_ROOT = Path(__file__).resolve().parent.parent
TICKET_REL = Path(".hub") / "shift-ticket.json"
PAPER_NAME = "SHIFT.md"


def _die(msg: str, code: int = 2) -> None:
    print(msg)
    raise SystemExit(code)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _product(raw: str) -> Path:
    path = Path(raw).expanduser()
    try:
        path = path.resolve()
    except OSError as exc:
        _die(f"项目夹路径无效：{exc}")
    if not path.is_dir():
        _die("先给出真正的项目文件夹。")
    if path == HUB_ROOT or path == HUB_ROOT.parent / "hub":
        _die("不要把配套夹当成项目夹。")
    return path


def _git(product: Path, *args: str) -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", str(product), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return (proc.stdout or "").strip()


def _exists(product: Path, rel: str) -> bool:
    return (product / rel).exists()


def _snapshot(product: Path, nxt: str) -> dict:
    status = _git(product, "status", "--short")
    return {
        "when": _now(),
        "product": str(product),
        "git": {
            "branch": _git(product, "branch", "--show-current"),
            "head": _git(product, "log", "-1", "--oneline"),
            "dirty": bool(status),
            "status": status[:4000],
            "diff_stat": _git(product, "diff", "--stat")[:2000],
        },
        "has_handoff": _exists(product, "WORK-HANDOFF.md"),
        "has_ledger": (product / ".hub" / "ledger.jsonl").is_file(),
        "has_gates": _exists(product, ".hub/physical-gates.json"),
        "has_map": _exists(product, "PROJECT-MEMORY.jsonl"),
        "has_changes": _exists(product, "CHANGES.md"),
        "next": (nxt or "").strip(),
        "rule": "下一班禁止另起门禁表和打包清单。尺只认这个项目夹。没写进项目夹的话等于没发生。",
    }


def _paper(data: dict) -> str:
    git = data.get("git") or {}
    dirty = "有未提交改动" if git.get("dirty") else "工作区干净"
    nxt = data.get("next") or "看项目根 WORK-HANDOFF.md 当前工作包"
    def yn(key: str) -> str:
        return "有" if data.get(key) else "没有"
    return "\n".join([
        "# 接班纸",
        "",
        "人换了，活还是这一摊。下一班先读这张纸和 WORK-HANDOFF.md，禁止另起门禁表、地图和打包清单。",
        "",
        f"- 留下时间：{data.get('when') or '—'}",
        f"- 项目夹：{data.get('product') or '—'}",
        f"- 分支：{git.get('branch') or '—'}",
        f"- 最近一次提交：{git.get('head') or '—'}",
        f"- 源码：{dirty}",
        f"- 交接纸 WORK-HANDOFF.md：{yn('has_handoff')}",
        f"- 账本 .hub：{yn('has_ledger')}",
        f"- 门禁声明：{yn('has_gates')}",
        f"- 地图：{yn('has_map')}",
        f"- 改动图 CHANGES.md：{yn('has_changes')}",
        f"- 下一刀：{nxt}",
        "- 规矩：尺只认这个项目夹。没写进项目夹的话，换谁都接不上。",
        "",
    ])


def cmd_leave(product: Path, nxt: str) -> None:
    data = _snapshot(product, nxt)
    ticket = product / TICKET_REL
    ticket.parent.mkdir(parents=True, exist_ok=True)
    ticket.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    paper = product / PAPER_NAME
    paper.write_text(_paper(data), encoding="utf-8")
    lines = [
        "已留班。班在这个项目夹里，不在聊天里。",
        f"接班纸：{paper}",
        "请同时更新项目根 WORK-HANDOFF.md 的当前工作包。",
    ]
    if not data["has_handoff"]:
        lines.append("现在还没有 WORK-HANDOFF.md。下一班只能看到这张接班纸，接得住的更少。")
    print("\n".join(lines))


def cmd_take(product: Path) -> None:
    ticket_path = product / TICKET_REL
    paper_path = product / PAPER_NAME
    handoff = product / "WORK-HANDOFF.md"
    changes = product / "CHANGES.md"
    has_git = (product / ".git").exists()
    has_hub = (product / ".hub" / "ledger.jsonl").is_file()
    if not any(
        (
            ticket_path.is_file(),
            paper_path.is_file(),
            handoff.is_file(),
            changes.is_file(),
            has_git,
            has_hub,
        )
    ):
        _die(
            "这个项目夹几乎是空的，接不上上一班。"
            "先从 git、原话纸和源码把班补回来，禁止另起一份门禁表或打包清单。"
        )
    data = {}
    if ticket_path.is_file():
        try:
            raw = json.loads(ticket_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                data = raw
        except (OSError, json.JSONDecodeError):
            print("接班票读不动，改看项目夹里已有的纸。")
    print("接班。人换了，活还是这一摊。主人只说换班了就够，不用对上一班说话。")
    if paper_path.is_file():
        print(paper_path.read_text(encoding="utf-8"))
    elif data:
        print(_paper(data))
    else:
        print("没有接班纸。上一班可能突然没了。按项目夹里已有的交接纸、改动图、账本、git 接。禁止另起门禁表和打包清单。")
    print("接着做：")
    print("1. 读项目根 WORK-HANDOFF.md 当前工作包（没有就看 CHANGES.md）")
    print("2. git status --short；git branch --show-current；git log -1 --oneline；git diff --stat")
    if has_hub:
        print(f"3. python {HUB_ROOT / 'tools' / 'state.py'} status --product {product}")
        print("4. 有地图再 map_show，不要整仓重读")
    else:
        print("3. 这个项目还没有账本。不要假装昨天的门禁已经点过绿。")
    print("禁止凭聊天记忆重列门禁、地图、打包清单。对不上就说班没留下，去补记录或复验。")


def main(argv: list[str] | None = None) -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(prog="shift.py", description="换智能体时留班、接班")
    sub = ap.add_subparsers(dest="cmd", required=True)
    leave = sub.add_parser("leave", help="下班留班")
    leave.add_argument("--product", required=True)
    leave.add_argument("--next", default="", dest="nxt", help="下一刀，人话")
    take = sub.add_parser("take", help="上班接班")
    take.add_argument("--product", required=True)
    args = ap.parse_args(argv)
    product = _product(args.product)
    if args.cmd == "leave":
        cmd_leave(product, args.nxt)
        return
    cmd_take(product)


if __name__ == "__main__":
    main()
