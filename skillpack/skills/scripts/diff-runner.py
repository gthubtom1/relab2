#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""diff-runner — 复刻交付的差异测试驱动（第一版：能驱动 + 能记录）。

## 干什么
读 `work/<case>/rebuild.md` 的 `## diff_baseline` 段拿到原程序（baseline）与
新实现的驱动命令，对指定功能行（F-xxx）把同一组输入分别喂给两个程序，各自抓
stdout / stderr / exit code / 生成的文件，落一份对照草稿到 `work/<case>/diff/`，
供人确认后再回填 rebuild.md 的对照表。

## 不干什么（第一版的边界，故意不做）
- 不做自动判定：草稿里"是否一致"列一律写 `PENDING`，由人判定；
- 不做模糊匹配 / 容差推断：非确定项（时间、随机数、PID、路径含时间戳）标
  `NONDETERMINISTIC`，由人定容差；
- 不替人改 rebuild.md：只写 `diff/`，回填由人（或 ver 角色）完成。

这是最小可用版。真项目跑完再决定要不要抽公共（见 docs/DELIVERY-GOAL-2026-10-12.md §7 阶段 5）。

## rebuild.md 认得的格式

```
## diff_baseline

- baseline_dir: `baseline/`
- diff_dir: `diff/`
- baseline_command: `./baseline/original --mode a {input}`
- rebuilt_command: `./diff/build/newimpl --mode a {input}`
- cases:
  - F-001 | input=1
  - F-001 | input=2
```

`{input}` 是占位符，被每条 case 的 `input=` 值原样替换。两个 command 都用
shell 执行（Windows 走 powershell，其余走 bash），因此写成命令行即可。

## 用法

```
python skills/scripts/diff-runner.py work/<case> --function F-001 [--case-root ...]
# 或显式：
python skills/scripts/diff-runner.py work/<case> --function F-001 \
  --baseline-cmd "./baseline/original --mode a {input}" \
  --rebuilt-cmd  "./diff/build/newimpl --mode a {input}" \
  --input "input=1" --input "input=2"
```

## 退出码
  0  草稿已生成（不代表通过——判定由人做）
  2  配置缺失（rebuild.md 没有 diff_baseline / 命令行没给驱动命令）
  3  执行错误（命令跑不起来；草稿里如实记 ERROR，仍写盘）
"""

from __future__ import annotations

import argparse
import datetime
import os
import re
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------- rebuild 解析

FIELD = re.compile(r"^\s*-\s+([A-Za-z0-9_]+):\s*(.*)$")
SECTION = re.compile(r"(?ms)^##\s+(.+?)\s*$")
FUNCTION_ID = re.compile(r"\bF-[A-Za-z0-9][A-Za-z0-9_-]*\b")
CASE_LINE = re.compile(r"^\s*-\s*("+FUNCTION_ID.pattern+r")\s*\|\s*(.+?)\s*$")
# 非确定信号：输出里出现这些就当 NONDETERMINISTIC 标出来（只标不判）
NONDET = re.compile(
    r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}|"
    r"\b\d{10,13}\b|"            # unix 时间戳
    r"\b(?:pid|uuid|guid|nonce|salt)\b|"
    r"\b0x[0-9a-fA-F]{8,}\b|"   # 指针/堆地址
    r"[A-Za-z]:\\[^\s]*Temp|/tmp/",
    re.I,
)


def section_text(text: str, title: str) -> str:
    pattern = re.compile(r"(?ms)^##\s+" + re.escape(title) + r"\s*$\n?(.*?)(?=^##\s|\Z)")
    match = pattern.search(text)
    return match.group(1) if match else ""


def field_value(text: str, name: str) -> str:
    for line in text.splitlines():
        match = FIELD.match(line)
        if match and match.group(1) == name:
            return match.group(2).strip().strip("`").strip()
    return ""


def parse_rebuild(case_root: Path):
    path = case_root / "rebuild.md"
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8-sig")
    diff = section_text(text, "diff_baseline")
    cases = []
    for line in diff.splitlines():
        match = CASE_LINE.match(line)
        if match:
            cases.append((match.group(1), match.group(2)))
    return {
        "baseline_dir": field_value(diff, "baseline_dir"),
        "diff_dir": field_value(diff, "diff_dir"),
        "baseline_command": field_value(diff, "baseline_command"),
        "rebuilt_command": field_value(diff, "rebuilt_command"),
        "harness": field_value(diff, "harness"),
        "cases": cases,
    }


# ---------------------------------------------------------------- 驱动

def shell_for(platform: str):
    if platform == "nt":
        return ["powershell", "-NoProfile", "-Command"]
    return ["bash", "-lc"]


def run_command(command: str, cwd: Path, timeout: int):
    """Run one command, capture everything a human needs for a verdict."""
    shell = shell_for(os.name)
    started = datetime.datetime.now()
    try:
        proc = subprocess.run(
            shell + [command], cwd=str(cwd),
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout,
        )
        return {
            "exit": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "error": "",
            "seconds": round((datetime.datetime.now() - started).total_seconds(), 3),
        }
    except subprocess.TimeoutExpired:
        return {
            "exit": "TIMEOUT",
            "stdout": "",
            "stderr": "",
            "error": "timed out after %ss" % timeout,
            "seconds": timeout,
        }
    except FileNotFoundError as exc:
        return {
            "exit": "ERROR",
            "stdout": "",
            "stderr": "",
            "error": "shell not found: %s" % exc,
            "seconds": 0,
        }


def first_lines(text: str, limit: int = 12) -> str:
    cleaned = text.strip()
    if not cleaned:
        return "(empty)"
    lines = cleaned.splitlines()
    shown = lines[:limit]
    if len(lines) > limit:
        shown.append("... (%d more lines)" % (len(lines) - limit))
    return "\n".join(shown)


def nondeterministic_note(*outputs: str) -> str:
    hits = []
    for output in outputs:
        for match in NONDET.finditer(output or ""):
            token = match.group(0)
            if token not in hits:
                hits.append(token)
    if not hits:
        return ""
    return "NONDETERMINISTIC: " + ", ".join(hits[:5]) + (" ..." if len(hits) > 5 else "")


# ---------------------------------------------------------------- 草稿

def render_draft(case_id: str, function_id: str, entries, stamp: str,
                 baseline_cmd: str, rebuilt_cmd: str) -> str:
    lines = [
        "<!-- diff-runner draft — 供人工确认后回填 rebuild.md 的 diff_baseline 表 -->",
        "# Diff draft: %s" % function_id,
        "",
        "- case: %s" % case_id,
        "- generated: %s" % stamp,
        "- baseline_command: `%s`" % baseline_cmd,
        "- rebuilt_command: `%s`" % rebuilt_cmd,
        "- judged_by: human (PENDING 由人判定；非确定项由人定容差)",
        "",
        "| F-ID | 输入条件 | 原程序结果 | 新实现结果 | 是否一致 | 说明 |",
        "|------|----------|------------|------------|----------|------|",
    ]
    for entry in entries:
        baseline = entry["baseline"]
        rebuilt = entry["rebuilt"]
        note_bits = []
        if entry["note"]:
            note_bits.append(entry["note"])
        if baseline["exit"] != rebuilt["exit"]:
            note_bits.append("exit %s vs %s" % (baseline["exit"], rebuilt["exit"]))
        if baseline["error"] or rebuilt["error"]:
            note_bits.append("execution error")
        note = "; ".join(note_bits) or "对比 stdout/stderr/exit 后人工判定"
        lines.append("| %s | %s | %s | %s | PENDING | %s |" % (
            function_id,
            entry["input"].replace("|", "\\|"),
            first_lines(baseline["stdout"] or baseline["stderr"] or "(no output)").replace("|", "\\|").replace("\n", "<br>"),
            first_lines(rebuilt["stdout"] or rebuilt["stderr"] or "(no output)").replace("|", "\\|").replace("\n", "<br>"),
            note.replace("|", "\\|"),
        ))
    lines.extend(["", "## Raw records", ""])
    for index, entry in enumerate(entries, 1):
        lines.append("### %s · case %d · input: %s" % (function_id, index, entry["input"]))
        lines.append("")
        lines.append("- baseline: exit=%s seconds=%s%s" % (
            entry["baseline"]["exit"], entry["baseline"]["seconds"],
            (" error=" + entry["baseline"]["error"]) if entry["baseline"]["error"] else ""))
        lines.append("- rebuilt: exit=%s seconds=%s%s" % (
            entry["rebuilt"]["exit"], entry["rebuilt"]["seconds"],
            (" error=" + entry["rebuilt"]["error"]) if entry["rebuilt"]["error"] else ""))
        lines.append("")
        lines.append("```text")
        lines.append("--- baseline stdout ---")
        lines.append(first_lines(entry["baseline"]["stdout"], 40))
        lines.append("--- rebuilt stdout ---")
        lines.append(first_lines(entry["rebuilt"]["stdout"], 40))
        lines.append("```")
        lines.append("")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- main

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Drive the original and the rebuilt program with the same input and write a diff draft.")
    parser.add_argument("case_root", help="work/<case> directory (must contain rebuild.md)")
    parser.add_argument("--function", required=True, help="function id to compare, e.g. F-001")
    parser.add_argument("--baseline-cmd", default="", help="command for the original program; {input} is replaced")
    parser.add_argument("--rebuilt-cmd", default="", help="command for the new implementation; {input} is replaced")
    parser.add_argument("--input", action="append", default=[], help="one input value (repeatable)")
    parser.add_argument("--timeout", type=int, default=60, help="per-command timeout in seconds")
    parser.add_argument("--out", default="", help="override the draft path (default: <case>/diff/<F-ID>.md)")
    args = parser.parse_args(argv)

    case_root = Path(args.case_root).expanduser().resolve()
    if not case_root.is_dir():
        print("ERROR: case root not found: %s" % case_root, file=sys.stderr)
        return 2

    config = parse_rebuild(case_root)
    if config is None:
        print("ERROR: %s has no rebuild.md — diff-runner only runs on rebuild cases" % case_root, file=sys.stderr)
        return 2

    baseline_cmd = args.baseline_cmd or config["baseline_command"]
    rebuilt_cmd = args.rebuilt_cmd or config["rebuilt_command"]
    if not baseline_cmd or not rebuilt_cmd:
        print("ERROR: need both --baseline-cmd and --rebuilt-cmd (or baseline_command/rebuilt_command in rebuild.md)",
              file=sys.stderr)
        return 2

    inputs = list(args.input)
    if not inputs:
        inputs = [value for function_id, value in config["cases"] if function_id == args.function]
    if not inputs:
        print("ERROR: no input given and rebuild.md lists none for %s" % args.function, file=sys.stderr)
        return 2

    entries = []
    for value in inputs:
        baseline_result = run_command(baseline_cmd.replace("{input}", value), case_root, args.timeout)
        rebuilt_result = run_command(rebuilt_cmd.replace("{input}", value), case_root, args.timeout)
        note = nondeterministic_note(baseline_result["stdout"], baseline_result["stderr"],
                                     rebuilt_result["stdout"], rebuilt_result["stderr"])
        entries.append({
            "input": value,
            "baseline": baseline_result,
            "rebuilt": rebuilt_result,
            "note": note,
        })

    stamp = datetime.datetime.now().isoformat(timespec="seconds")
    draft_dir = Path(args.out).resolve().parent if args.out else (case_root / "diff")
    draft_dir.mkdir(parents=True, exist_ok=True)
    draft_path = Path(args.out).resolve() if args.out else (draft_dir / ("%s.md" % args.function))
    draft_path.write_text(
        render_draft(case_root.name, args.function, entries, stamp, baseline_cmd, rebuilt_cmd),
        encoding="utf-8",
    )

    print("DRAFT -> %s" % draft_path)
    print("inputs=%d function=%s" % (len(entries), args.function))
    if any(entry["baseline"]["error"] or entry["rebuilt"]["error"] for entry in entries):
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
