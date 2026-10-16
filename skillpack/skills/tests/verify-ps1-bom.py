#!/usr/bin/env python3
"""verify-ps1-bom.py —— 非 ASCII 的 .ps1 必须带 UTF-8 BOM。

★ 2026-10-16 新建。为什么必须有这道门（真实事故，见 docs/KNOWN-BOUNDARIES.md 第 21 条）：

  Windows PowerShell 5.1 加载 `.ps1` 时，**没有 BOM 就按系统 ANSI 码页解码**。
  本机是 936(GBK)，于是含中文/破折号的脚本被解错字节边界，直接抛
  `ParserError: MissingEqualsInHashLiteral`。后果是**换机第一步就是死的**：
  HEAD(0e0d338) 上 4 个非 ASCII 的 .ps1 缺 BOM（`relab2.ps1` / `master-route.ps1` /
  `switch-mcp.ps1` / `experience-cards/fixtures/scope-probe.ps1`），
  干净 clone 后 `relab2.ps1 doctor` 与 `setup -DryRun` **都 exit 1**，
  而 `selfcheck` 还报「通过 6 / 失败 0」——新机上的 agent 会以为配好了。

  为什么已有的 `verify-powershell-syntax.py` 拦不住它：
  那道门为了让 PS5.1 能"看见"错误，**显式按 UTF-8 读入再 `ParseInput`**
  （见该文件注释）——这恰恰绕开了"PS5.1 自己加载时会怎样"这个问题。
  实测：把无 BOM 的 `relab2.ps1` 喂给它，报 0 错误。
  → 所以 BOM 必须由**独立**的门来查，不能指望解析器门。

  判据与 CI 的 `Non-ASCII .ps1 must carry a UTF-8 BOM` 步骤**完全一致**（同一逻辑，
  这里只是把它做成仓库内的门，本地也能跑、不依赖 CI step 顺序）。

用法：
    python skillpack/skills/tests/verify-ps1-bom.py [--json]
退出码：0 全部合规 / 1 有文件缺 BOM
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
# ★ 2026-10-16：原来写 `parents[1]` —— 那是 `skillpack/`，不是仓根（`parents[2]`）。
#   后果：所有 `REPO/rel` 都指错，`read_bytes` 抛 OSError 被当成"读不到"，
#   而反例控制组里被去掉 BOM 的那个文件**根本没被读到** → 门漏判（实测：去掉
#   `relab2.ps1` 的 BOM 后仍报"全部合规"）。这类"路径算错一层"的 bug 在本仓
#   已出现过多次（经验卡 `powershell-script-scope-…` 记的是同类）。
REPO = HERE.parents[2]           # skillpack/skills/tests -> repo root


def tracked_ps1() -> list[str]:
    """优先用 git 索引（与 CI 一致：只查被跟踪的文件）；不在 git 仓库时退化为全盘扫。"""
    try:
        p = subprocess.run(["git", "-C", str(REPO), "ls-files", "*.ps1"],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=120)
        if p.returncode == 0 and (p.stdout or "").strip():
            return [x for x in p.stdout.splitlines() if x.strip()]
    except (OSError, subprocess.TimeoutExpired):
        pass
    out = []
    for d, dirs, files in os.walk(REPO):
        dirs[:] = [x for x in dirs if x not in
                   ("_archive", "_history", "_归档-禁读-历史文档", "work", "node_modules",
                    "community-raw", "TEMP", ".git")]
        for f in files:
            if f.endswith(".ps1"):
                out.append(str(Path(d, f).relative_to(REPO)).replace("\\", "/"))
    return sorted(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    files = tracked_ps1()
    bad, ok, ascii_only, missing = [], [], 0, []
    for rel in files:
        p = REPO / rel
        if not p.is_file():
            # 索引里有、工作树没有 = 未提交的 rename/move 中间态（例：先 `git mv`
            # 到 docs/_history/ 但还没提交）。那不是「缺 BOM」，本门不该管，
            # 也不该判红 —— 报出来供人核对即可。
            missing.append(rel)
            continue
        try:
            b = p.read_bytes()
        except OSError as e:
            bad.append({"file": rel, "why": f"读不到：{e}"})
            continue
        if not any(x >= 0x80 for x in b):
            ascii_only += 1
            continue                      # 纯 ASCII：无 BOM 也安全
        if b[:3] == b"\xef\xbb\xbf":
            ok.append(rel)
        else:
            bad.append({"file": rel, "why": "含非 ASCII 但缺 UTF-8 BOM（PS 5.1 会按 ANSI 码页解码）"})

    if a.json:
        print(json.dumps({"total": len(files), "ascii_only": ascii_only,
                          "bom_ok": len(ok), "not_in_worktree": missing,
                          "bad": bad}, ensure_ascii=False, indent=1))
    else:
        print(f"PS1 BOM 核验：被跟踪 .ps1 {len(files)} 个（纯 ASCII {ascii_only} · 含非 ASCII 且有 BOM {len(ok)}）")
        if missing:
            print(f"  （{len(missing)} 个在索引里但工作树不存在 —— 未提交的 rename/move，跳过：{', '.join(missing[:5])}"
                  f"{' …' if len(missing) > 5 else ''}）")
        if bad:
            print(f"  ★ {len(bad)} 个含非 ASCII 却缺 BOM：")
            for x in bad:
                print(f"      {x['file']} —— {x['why']}")
            print("  修法：把文件重存为「UTF-8 with BOM」（PowerShell: "
                  "`$c=Get-Content -Raw $f; [IO.File]::WriteAllText($f,$c,(New-Object Text.UTF8Encoding $true))`）")
            return 1
        print("  全部合规 ✓（含非 ASCII 的 .ps1 都带 UTF-8 BOM）")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
