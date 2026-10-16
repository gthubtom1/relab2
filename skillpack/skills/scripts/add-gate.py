#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""add-gate.py —— 往 `tests/ci-gates.json` **安全地**加一道门。

为什么有它（2026-10-16，三次真事故）
-----------------------------------
我手工用文本编辑往 `ci-gates.json` 加门时，**三次把它写坏**：
  ① 漏一个逗号 → `Expecting ',' delimiter`
  ② `why` 里写了裸的英文双引号 → JSON 断裂
  ③ 又一次裸引号（`不需要"跑一遍才知道"`）
每次都要花一轮去修。手工编辑 JSON 就是不该做的事 —— 本脚本把它变成一次原子操作：
读 → 追加 → **写回前先验证能解析** → 更新 lock → 打印结果。

用法
    python skills/scripts/add-gate.py --id my-gate --script skills/tests/my_gate.py \\
        --why "它守什么、为什么必须守" [--blocking 1] [--args --selftest]
    python skills/scripts/add-gate.py --id my-gate --remove      # 撤销
    python skills/scripts/add-gate.py --list                     # 看现有门

`why` 里的任何引号/反斜杠都由 json 库负责转义 —— **不会再手工写坏**。
"""
from __future__ import annotations

import argparse
import io
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILLS = HERE.parent          # skillpack/skills
MANIFEST = SKILLS / "tests" / "ci-gates.json"
LOCK_PY = SKILLS / "tests" / "verify-gate-wiring.py"


def load() -> dict:
    return json.loads(io.open(MANIFEST, encoding="utf-8").read())


def save(d: dict) -> None:
    txt = json.dumps(d, ensure_ascii=False, indent=2) + "\n"
    json.loads(txt)                       # ★ 写回前自证：解析不过就不落盘
    io.open(MANIFEST, "w", encoding="utf-8", newline="\n").write(txt)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--id", required=True)
    ap.add_argument("--script", default="")
    ap.add_argument("--why", default="")
    ap.add_argument("--args", nargs="*", default=[])
    ap.add_argument("--blocking", type=int, nargs="*", default=[1])
    ap.add_argument("--non-blocking", type=int, nargs="*", default=[])
    ap.add_argument("--remove", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--no-lock", action="store_true", help="不更新 lock（默认更新）")
    a = ap.parse_args()

    d = load()
    gates = d["gates"]

    if a.list:
        for g in gates:
            print(f"  {g['id']:<34} {g.get('script','')}")
        print(f"共 {len(gates)} 道")
        return 0

    if a.remove:
        before = len(gates)
        d["gates"] = [g for g in gates if g["id"] != a.id]
        if len(d["gates"]) == before:
            print(f"没有这道门：{a.id}")
            return 1
        save(d)
        print(f"已移除 {a.id}（{before} → {len(d['gates'])}）")
    else:
        if not a.script or not a.why:
            print("加门需要 --script 与 --why（why 要写清「它守什么、为什么必须守」）", file=sys.stderr)
            return 2
        if not (SKILLS.parent / a.script).is_file():
            print(f"★ script 路径不存在：{a.script}（相对 skillpack/，如 skills/tests/x.py）", file=sys.stderr)
            return 2
        if any(g["id"] == a.id for g in gates):
            print(f"已有这道门：{a.id}（先 --remove 再改，或直接改它的字段）", file=sys.stderr)
            return 2
        gates.append({
            "id": a.id,
            "script": a.script,
            "args": list(a.args),
            "blocking_exits": list(a.blocking),
            "non_blocking_exits": list(a.non_blocking),
            "executes_vendor_code": False,
            "why": a.why,
        })
        save(d)
        print(f"已加门 {a.id}（现 {len(gates)} 道）")

    if not a.no_lock and LOCK_PY.is_file():
        r = subprocess.run([sys.executable, str(LOCK_PY), "--write-lock"],
                           capture_output=True, text=True, errors="replace", timeout=300)
        tail = (r.stdout or r.stderr or "").strip().splitlines()[-2:]
        print("lock:", " | ".join(tail) if tail else f"rc={r.returncode}")
    print("复核：python skillpack/skills/tests/verify-gate-wiring.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
