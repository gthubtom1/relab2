#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify-powershell-syntax.py —— 所有 `.ps1` 必须能被 PowerShell 解析器解析。

为什么有这个门（2026-10-16 真事故）
-----------------------------------
我给 `relab2.ps1` 的 doctor 加一行输出时写错了字符串格式（`("{0}…" -f …)` 那处），
**仓库里没有任何门发现它** —— 直到真跑 `relab2.ps1 doctor` 才看到 6 个语法错误、
整个入口直接崩。这类错误完全可以用解析器静态抓住，不需要"跑一遍才知道"。

判据：PowerShell 的语言解析器（`[Parser]::ParseFile`）对每个 `.ps1` 零错误。
排除：禁读区 / `work/` / `_archive` / `_history` / `community-raw`（第三方与归档不参与）。

用法：python skills/tests/verify-powershell-syntax.py [--json]
退出码：0 全部可解析；1 有解析错误。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILLS = HERE.parent
REPO = SKILLS.parent.parent

PS_SCRIPT = r"""
$ErrorActionPreference = 'Continue'
$skip = '\\(_archive|_history|_归档-禁读-历史文档|work|node_modules|community-raw|TEMP)\\'
$files = @(Get-ChildItem -LiteralPath '__ROOT__' -Recurse -Filter *.ps1 -ErrorAction SilentlyContinue |
           Where-Object { $_.FullName -notmatch $skip })
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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    root = str(REPO).replace("\\", "\\\\")
    try:
        p = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                            "-Command", PS_SCRIPT.replace("__ROOT__", root)],
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

    if a.json:
        print(json.dumps({"total": int(total), "bad": int(bad), "errors": errs},
                         ensure_ascii=False, indent=2))
    else:
        print(f"PowerShell 语法核验：扫了 {total} 个 .ps1，有解析错误的 {bad} 个")
        for e in errs:
            print(f"  [FAIL] {e['file']}:{e['line']} {e['message']}")
        if not errs:
            print("  全部可被 PowerShell 解析器解析 ✓")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
