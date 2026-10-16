#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify-powershell-syntax.py —— 所有 `.ps1` 必须能被 PowerShell 解析器解析。

为什么有这个门（2026-10-16 真事故）
-----------------------------------
我给 `relab2.ps1` 的 doctor 加一行输出时写错了字符串格式（`("{0}…" -f …)` 那处），
**仓库里没有任何门发现它** —— 直到真跑 `relab2.ps1 doctor` 才看到 6 个语法错误、
整个入口直接崩。这类错误完全可以用解析器静态抓住，不需要"跑一遍才知道"。

判据：PowerShell 的语言解析器对每个 `.ps1` 零错误。
    实现细节（必须与代码一致，2026-10-17 修正）：**不用** `[Parser]::ParseFile` ——
    改为 `[System.IO.File]::ReadAllText(<f>, UTF8 无 BOM)` 再 `[Parser]::ParseInput`。
    原因：Windows PowerShell 5.1 的 `ParseFile` 对**无 BOM 的 UTF-8** 文件按系统 ANSI
    码页解码，文件里只要有中文就把字节边界吃穿、整个文件解析出 0 个错误
    （同一文件实测 powershell=0 / pwsh=1）—— 也就是说"能看见错误"只是碰巧带了 BOM。
    显式 UTF-8 + ParseInput 与宿主无关。
排除：禁读区 / `work/` / `_archive` / `_history` / `community-raw`（第三方与归档不参与）。

用法：python skills/tests/verify-powershell-syntax.py [--json]
退出码：0 全部可解析；1 有解析错误（或一个 .ps1 都没扫到、或本机没有 PowerShell 宿主）。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILLS = HERE.parent
REPO = SKILLS.parent.parent

PS_SCRIPT = r"""
$ErrorActionPreference = 'Continue'
# ★ 2026-10-17 修一处**假绿**（在全新 clone 上实测抓到）：原来的 `$skip` 里有 `TEMP`，
#   而 PowerShell 的 `-notmatch` **默认不区分大小写** —— 于是任何路径里含 `Temp` 的仓库
#   （例：clone 到 `%TEMP%\clone-final\`）**所有 .ps1 都被 skip 掉**，门报
#   「扫了 0 个 .ps1，有解析错误的 0 个 ✓」= 绿。这与本仓最恨的「假绿」是同一类。
#   修法：① 该 skip 的是**目录名**而不是子串 —— 用 `\\(TEMP|work|...)\\` 锚定到路径分隔符
#   （`\\TEMP\\` 只匹配名为 TEMP 的目录段，不再误伤 `Temp\clone-final`）；
#   ② 排除项统一**只按目录段**匹配。
$skipDirNames = @('_archive', '_history', '_归档-禁读-历史文档', 'work', 'node_modules', 'community-raw', 'TEMP')
$rootFull = (Resolve-Path -LiteralPath '__ROOT__').Path.TrimEnd([IO.Path]::DirectorySeparatorChar)
$files = @(Get-ChildItem -LiteralPath '__ROOT__' -Recurse -Filter *.ps1 -ErrorAction SilentlyContinue |
           Where-Object {
             # ★ 只按**相对仓库根**的目录段匹配，且区分大小写（`-ccontains`）——
             #   否则 clone 到 `%TEMP%\...`（祖先目录叫 Temp）会把整个仓库误伤掉。
             $rel = $_.FullName.Substring($rootFull.Length).TrimStart([IO.Path]::DirectorySeparatorChar)
             $parts = $rel.Split([IO.Path]::DirectorySeparatorChar)
             -not ($parts | Where-Object { $skipDirNames -ccontains $_ })
           })
$bad = 0
foreach ($f in $files) {
  $e = $null; $t = $null
  # ★ 2026-10-16：必须自己按 UTF-8 读入再 ParseInput。Windows PowerShell 5.1 的
  #   ParseFile 对**无 BOM 的 UTF-8** 文件按 ANSI 码页解码，只要文件里有中文，
  #   就把字节边界吃穿、整个文件解析出 0 个错误（同一文件实测：powershell=0 /
  #   pwsh=1）。本仓 52 个 .ps1 里 48 个含非 ASCII、46 个带 BOM —— 也就是"能看见
  #   错误"只是碰巧带了 BOM，门根本没在判。显式 UTF-8 + ParseInput 与宿主无关。
  $text = [System.IO.File]::ReadAllText($f.FullName, (New-Object System.Text.UTF8Encoding($false)))
  [void][System.Management.Automation.Language.Parser]::ParseInput($text, [ref]$t, [ref]$e)
  if ($e -and $e.Count -gt 0) {
    $bad++
    foreach ($x in $e) { Write-Output ("ERR|{0}|{1}|{2}" -f $f.FullName, $x.Extent.StartLineNumber, $x.Message) }
  }
}
Write-Output ("TOTAL|{0}|{1}" -f $files.Count, $bad)
if ($bad -gt 0) { exit 1 } else { exit 0 }
"""


def _resolve_ps() -> list[str] | None:
    """找到可用的 PowerShell 宿主（含宿主参数）。

    ★ 2026-10-17：原来硬编码 `powershell`。GitHub 的 ubuntu runner **只装了 pwsh**
    —— `powershell` 这个命令名只有 Windows 才有 —— 于是这道门在 CI 的
    integration gates 里以 `FileNotFoundError: 'powershell'` exit 2 永久红，
    而 exit 2 不是清单登记的退出码，run-ci-gates 直接判 FAILED。
    顺序：Windows PowerShell（`powershell`，本机 PS 5.1 原生）→ PowerShell 7（`pwsh`）。
    `-ExecutionPolicy` 只在 Windows PowerShell 上传（非 Windows 的 pwsh 不需要它）。
    """
    exe = shutil.which("powershell")
    if exe:
        return [exe, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command"]
    exe = shutil.which("pwsh")
    if exe:
        return [exe, "-NoProfile", "-Command"]
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    ps = _resolve_ps()
    if ps is None:
        print("FAIL：本机既没有 powershell 也没有 pwsh —— 无法解析 .ps1。"
              "这道门需要一个 PowerShell 宿主（CI 的 ubuntu runner 预装 pwsh）。",
              file=sys.stderr)
        return 1

    root = str(REPO).replace("\\", "\\\\")
    try:
        p = subprocess.run(ps + [PS_SCRIPT.replace("__ROOT__", root)],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=900)
    except (OSError, subprocess.TimeoutExpired) as e:
        print(f"跑解析器失败：{type(e).__name__}: {e}", file=sys.stderr)
        return 2

    out = (p.stdout or "") + (p.stderr or "")
    errs = []
    total = bad = 0
    for line in out.splitlines():
        if line.startswith("ERR|"):
            _, f, ln, msg = line.split("|", 3)
            try:
                rel = str(Path(f).relative_to(REPO)).replace("\\", "/")
            except ValueError:
                rel = f
            errs.append({"file": rel, "line": int(ln), "message": msg.strip()})
        elif line.startswith("TOTAL|"):
            _, total, bad = line.split("|")
    # ★ 2026-10-17：`line.split("|")` 给的是**字符串**，`"0" == 0` 为 False ——
    #   原来若直接 `if total == 0` 会漏判。这里显式转 int（解析失败也当 0，同样判红）。
    try:
        total_n = int(total)
        bad_n = int(bad)
    except (TypeError, ValueError):
        total_n = 0
        bad_n = 0

    if a.json:
        print(json.dumps({"total": total_n, "bad": bad_n, "errors": errs},
                         ensure_ascii=False, indent=2))
    else:
        print(f"PowerShell 语法核验：扫了 {total_n} 个 .ps1，有解析错误的 {bad_n} 个")
        for e in errs:
            print(f"  [FAIL] {e['file']}:{e['line']} {e['message']}")
        if not errs:
            print("  全部可被 PowerShell 解析器解析 ✓")
    # ★ 2026-10-17：扫到 0 个 .ps1 **必须判红**。原实现只在「有 errs」时返回 1，
    #   于是「一个文件都没扫到」（路径算错 / skip 规则误伤 / 仓库布局变了）会静默报绿 ——
    #   这正是本仓反复出现的一类假绿（门早就不检查了，但汇总数字一样）。一个仓库
    #   不可能没有 .ps1（本仓 52 个），所以 total==0 只可能是门自己坏了。
    if total_n == 0:
        print("FAIL：一个 .ps1 都没扫到 —— 本仓不可能没有 .ps1，说明根路径或排除规则算错了", file=sys.stderr)
        return 1
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
