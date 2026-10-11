#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""子进程捕获：管道 vs 落盘。2026-10-11 验收挂死回归的门禁。

实测背景
--------
验收脚本用 ``subprocess.run(capture_output=True)`` 跑 ``apk-debug.ps1``，
进程永远不返回。诊断现场是::

    CPU user=0.0s sys=0.0s · 线程数 3 · 子进程一个都没有

子进程**早就退出了**，父进程却卡在读管道。原因不是超时、不是死锁、
不是 adb 抢端口：``capture_output=True`` 用匿名管道，
``subprocess.run`` 要等管道的**所有写端句柄都关闭**才认为读到 EOF。
而 Windows 上 PowerShell 拉起的 adb daemon / conhost 会继承并持有
管道写端不放 —— 它们不在子进程表里（psutil 看不到），句柄却还在，
于是 EOF 永远不来。

同一台机器上实测的对照::

    doctor   pipe  -> HANG (>90s)
    doctor   file  -> rc=0  36.6s
    devices  pipe  -> rc=1   9.6s
    devices  file  -> rc=0  23.8s

harness 唯一的修法是落盘捕获。这道门禁钉死它，别再退回管道。

Exit codes: 0 全过，1 有用例失败。
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
import time

# REPO 要上溯 3 层：本文件在 <repo>/skillpack/skills/scripts/ 下。
# ★ 2026-10-11 这里一度写成 parents[2]，于是 REPO 指向 skillpack/，
#   扫不到 apk-debug.ps1，两个真复现用例全部「跳过」变成假绿。
REPO = Path(__file__).resolve().parents[3]
SELF = Path(__file__).resolve()
APK_DEBUG = REPO / "skillpack/skills/apk-reverse/scripts/apk-debug.ps1"
PS = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File"]


def _decode(path: Path) -> str:
    """PowerShell 在中文 Windows 上按 936(GBK) 写文件，不是 UTF-8。"""
    blob = path.read_bytes()
    try:
        return blob.decode("utf-8")
    except UnicodeDecodeError:
        return blob.decode("gbk", "replace")


def case_capture_hangs() -> tuple[bool, str]:
    """用真实命令复现：管道捕获必须会挂（否则这条门禁就证明不了什么）。

    这不是同义反复：它是**控制组**。如果哪天 pipe 也不挂了，
    说明根因不是管道（比如是 adb 抢端口），那这条门禁的前提就变了，
    必须重写而不是继续 PASS。
    """
    if not APK_DEBUG.exists():
        return True, f"（{APK_DEBUG.name} 不在，跳过）"
    started = time.time()
    try:
        subprocess.run(PS + [str(APK_DEBUG), "doctor"],
                       capture_output=True, timeout=75)
        return (False,
                "管道模式 75s 内就返回了 —— 根因可能不是管道捕获，"
                "这条门禁的前提需要重新确认（别让它继续 PASS）")
    except subprocess.TimeoutExpired:
        return True, f"管道模式 75s 未返回（已复现挂死，用时 {time.time() - started:.0f}s）"


def case_file_capture_works() -> tuple[bool, str]:
    """落盘捕获在同样条件下必须按时返回 —— 这才是 harness 该用的姿势。"""
    if not APK_DEBUG.exists():
        return True, f"（{APK_DEBUG.name} 不在，跳过）"
    with tempfile.TemporaryDirectory(prefix="capture-file-") as td:
        tmp = Path(td)
        out_f, err_f = tmp / "o.txt", tmp / "e.txt"
        started = time.time()
        try:
            with open(out_f, "wb") as fo, open(err_f, "wb") as fe:
                rc = subprocess.run(PS + [str(APK_DEBUG), "doctor"],
                                    stdout=fo, stderr=fe, timeout=180).returncode
        except subprocess.TimeoutExpired:
            return False, "落盘模式 180s 仍未返回（落盘本该绕开这个问题）"
        took = time.time() - started
        text = _decode(out_f) + _decode(err_f)
        ok = rc == 0 and "APK" in text
        return ok, f"落盘模式 {took:.1f}s 返回 rc={rc}，中文解码正常={text.count('自检') > 0}"


def case_harnesses_use_files() -> tuple[bool, str]:
    """仓库内所有跑 apk-debug.ps1 的 Python harness 都必须落盘捕获。"""
    problems: list[str] = []
    checked = 0
    for path in REPO.rglob("*.py"):
        if path.resolve() == SELF:
            continue  # 这道门禁的文档字符串里就写着 capture_output=True，别扫自己
        s = str(path).replace("\\", "/")
        if "/.git/" in s or "/node_modules/" in s:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if "apk-debug" not in text:
            continue
        checked += 1
        for m in re.finditer(r"capture_output\s*=\s*True", text):
            line = text[: m.start()].count("\n") + 1
            problems.append(f"{path.relative_to(REPO)}:{line} 用了管道捕获")
    if problems:
        return False, "；".join(problems)
    return True, f"扫了 {checked} 个调用 apk-debug 的 harness，无一使用管道捕获"


def main() -> int:
    print("=" * 74)
    print("子进程捕获：管道 vs 落盘（2026-10-11 验收挂死回归）")
    print("=" * 74)
    cases = [
        ("控制组：管道捕获会挂死（证明根因）", case_capture_hangs),
        ("落盘捕获按时返回（harness 该用的姿势）", case_file_capture_works),
        ("仓库内 harness 全部落盘捕获", case_harnesses_use_files),
    ]
    failed = 0
    for name, fn in cases:
        try:
            ok, detail = fn()
        except Exception as exc:  # noqa: BLE001 - 门禁自身不能崩
            ok, detail = False, f"用例自身抛异常: {exc!r}"
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
        print(f"         {detail}")
        if not ok:
            failed += 1
    print("=" * 74)
    if failed:
        print(f"结论：{failed} 项失败")
        return 1
    print("结论：全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())