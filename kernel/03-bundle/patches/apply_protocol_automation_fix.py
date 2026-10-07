#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
apply_protocol_automation_fix.py —— 修 workflows/protocol-automation.md 的死链。

两步，都幂等：
  1) 先调 apply_matrix_fix.py，把旧矩阵换成 matrix.md（已打过补丁的文件会报「无改动」）。
  2) 再把矩阵正文里写成裸文件名的方法书改成裸书名（与另外五条线同一个口径）。

第 2 步修的死链（check_dead_refs.py 判 LOOSE_METHOD，11 处）：
  L214 `reverse-engineering.md` `mobile-reverse.md`
  L215 `browser-automation.md` `mobile-reverse.md`
  L216 `planning.md`
  L217 `project-init.md` `ui-design.md` `packaging.md`
       `performance-optimization.md` `windows-environment.md`（两次）
  成因：上一轮我写 matrix.md 时，正文里把这几本写成了裸文件名。
  照字面解析，workflows/ 下并没有 `reverse-engineering.md` 这个文件——
  写「哪本书」应该用另外五条线一直在用的裸书名（`reverse-engineering`），
  路径只在矩阵表格第三列给。表格里的 `../docs/methods/xxx.md` 不受影响
  （规则要求反引号紧贴书名，表格里反引号后面是 `../`）。

用法：python apply_protocol_automation_fix.py --target <02-hubcore/workflows/protocol-automation.md>
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from _patchlib import Rule, apply_rules   # noqa: E402

SCRIPT_REL = "03-bundle/patches/apply_protocol_automation_fix.py"
BOOKS = ("reverse-engineering", "mobile-reverse", "browser-automation", "planning",
         "project-init", "ui-design", "packaging", "performance-optimization",
         "windows-environment")

RULES = [
    # expect 留空：全量重建时新版矩阵本来就不带裸文件名，命中 0 次是正常结果。
    # 真正的漂移闸门是 check_dead_refs.py 的 LOOSE_METHOD 计数（应为 0）。
    Rule("矩阵正文里的裸文件名方法书 → 裸书名",
         r"`(" + "|".join(BOOKS) + r")\.md`", r"`\1`",
         # FIX-17：expect 留空不代表可判。验收模式要求矩阵正文里至少出现一个
         # 裸书名（改写后的形态），否则「已是新版」和「源文漂移」分不开。
         verify=re.compile(r"`(" + "|".join(BOOKS) + r")`")),
]


def run_matrix_fix(target: Path, dry_run: bool) -> int:
    cmd = [sys.executable, str(HERE / "apply_matrix_fix.py"), "--target", str(target)]
    if dry_run:
        cmd.append("--dry-run")
    proc = subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    print("[步骤1] apply_matrix_fix.py：")
    for line in (proc.stdout or "").splitlines():
        print("    " + line)
    if proc.returncode not in (0, 3):
        print(f"[错误] apply_matrix_fix.py 退出码 {proc.returncode}", file=sys.stderr)
        print((proc.stderr or ""), file=sys.stderr)
        return proc.returncode
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    target = Path(a.target)
    if not target.is_file():
        print(f"[错误] 目标文件不存在：{target}", file=sys.stderr)
        return 2
    rc = run_matrix_fix(target, a.dry_run)
    if rc:
        return rc
    print("[步骤2] 方法书写法：")
    return apply_rules(target, SCRIPT_REL, RULES, a.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
