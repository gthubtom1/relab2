#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test-doc-resolve-negctl.py —— `test-doc-resolve.py` 的负控（控制组）。

为什么必须有
------------
ASSESS 的任务书把「负控 = 故意注入一个坏样本，必须判红，否则本关的绿不算数」写成了硬规矩
（`docs/ASSESS-全量验收任务书-2026-10-17.md` §3 ⑥-9「负控」）。一条只会判绿的门等于没门，
而且本仓真踩过这个坑（`e873a01 修两处门假绿：扫到 0 个文件仍报绿`）。
所以这里把四类坏样本**逐条注入**，每一条都要求 `test-doc-resolve.py` **在对应的那一项上判红**。

怎么注入（绝不写仓库内任何文件）
--------------------------------
每个用例都在系统临时目录（`%TEMP%/assess-doc-resolve-negctl/`）里搭一棵**最小假仓**：
把真文档读进内存、替换成坏形态、写到临时树里，再让同一个检查器跑 `--repo-root/--handoff/
--project-map/--gates` 指向这些临时件。跑完删临时树。仓库一个字节都不改。

五条用例
--------
  N1  D1：把正本按**修复前**的位置放（`<tmp>/docs/_history/HANDOFF-…`），声明路径不落地 → D1 红
  N2  D2：声明路径能落地（`<tmp>/docs/HANDOFF-…` 存在），但正本实际件仍在 `docs/_history/` 下 → D2 红
          （同时 D1 绿 —— 证明 D1/D2 是两条可分辨的判据，不是同一条重算两遍）
  N3  D3：把 `全量 42 门` 改回 `全量 32 门` → D3 红（其余绿）
  N4  D4：把路由路径改回 `config/routing.json`（按仓根相对打不开）→ D4 红（其余绿）
  N5  D4：把 routing 路径 token 整条删掉 → D4 红（fail-closed：扫到 0 条也判红，不许静默放行）

退出码：0 五条全部如期判红；1 有任一条被放过（或本脚本自身失败）。
标准库 only；只写系统临时目录。
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHECKER = HERE / "test-doc-resolve.py"
REPO = HERE.parent.parent.parent                 # skillpack/skills/tests -> 仓根
HANDOFF_NAME = "HANDOFF-终极交接与施工任务书-全AI通用.md"
REAL_HANDOFF = REPO / "docs" / HANDOFF_NAME
REAL_PROJECT_MAP = REPO / "docs" / "PROJECT-MAP.md"
REAL_GATES = HERE / "ci-gates.json"


def run_checker(repo: Path, handoff: Path, project_map: Path) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(CHECKER), "--repo-root", str(repo),
         "--handoff", str(handoff), "--project-map", str(project_map),
         "--gates", str(REAL_GATES)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def _seed_routing(repo: Path) -> None:
    """在假仓里放一份 routing.json 桩，让 D4 在这些用例里保持绿 ——
    这样每条用例里**只有被注入的那一项**判红，负控才证明得了「判据互相分辨」。"""
    p = repo / "skillpack" / "skills" / "config" / "routing.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{}", encoding="utf-8")


def verdicts(out: str) -> dict[str, str]:
    """把检查器 stdout 里的 `[PASS]/[FAIL] Dx` 解析成 {'D1': 'PASS'|'FAIL'}。"""
    return {m.group(2): m.group(1) for m in re.finditer(r"^\[(PASS|FAIL)\]\s+(D\d)", out, re.M)}


def main() -> int:
    tmp_root = Path(tempfile.mkdtemp(prefix="assess-doc-resolve-negctl-"))
    cases: list[tuple[str, str, str, str, str]] = []   # (用例名, repo, handoff, project_map, 期望红的项)
    fails: list[str] = []
    try:
        handoff_src = REAL_HANDOFF.read_text(encoding="utf-8")
        pm_src = REAL_PROJECT_MAP.read_text(encoding="utf-8")
        if "全量 42 门" not in handoff_src:
            print("[FATAL] 真 HANDOFF 里找不到 `全量 42 门` —— 修好后的基线形态变了，先对齐本脚本")
            return 1
        if "skillpack/skills/config/routing.json" not in pm_src:
            print("[FATAL] 真 PROJECT-MAP 里找不到修好后的路由路径 —— 先对齐本脚本")
            return 1

        # ---- N1: 修复前的正本位置（docs/_history/），声明路径不落地 → D1 红 ----
        n1 = tmp_root / "n1"
        (n1 / "docs" / "_history").mkdir(parents=True)
        (n1 / "docs" / "_history" / HANDOFF_NAME).write_text(handoff_src, encoding="utf-8")
        (n1 / "docs" / "PROJECT-MAP.md").write_text(pm_src, encoding="utf-8")
        _seed_routing(n1)
        cases.append(("N1 D1（修复前形态：声明路径不落地 + 正本在 _history）",
                      str(n1), str(n1 / "docs" / "_history" / HANDOFF_NAME),
                      str(n1 / "docs" / "PROJECT-MAP.md"), "D1"))

        # ---- N2: 声明路径能落地，但正本实际件在 _history 下 → D2 红、D1 绿 ----
        n2 = tmp_root / "n2"
        (n2 / "docs" / "_history").mkdir(parents=True)
        (n2 / "docs" / "_history" / HANDOFF_NAME).write_text(handoff_src, encoding="utf-8")
        (n2 / "docs" / HANDOFF_NAME).write_text(handoff_src, encoding="utf-8")
        (n2 / "docs" / "PROJECT-MAP.md").write_text(pm_src, encoding="utf-8")
        _seed_routing(n2)
        cases.append(("N2 D2 正本躲在黑名单目录里",
                      str(n2), str(n2 / "docs" / "_history" / HANDOFF_NAME),
                      str(n2 / "docs" / "PROJECT-MAP.md"), "D2"))

        # ---- N3: 门数写回 32 → D3 红 ----
        n3 = tmp_root / "n3"
        (n3 / "docs").mkdir(parents=True)
        (n3 / "docs" / HANDOFF_NAME).write_text(
            handoff_src.replace("全量 42 门", "全量 32 门")
                       .replace("| 42 门全绿（2026-10-17", "| 32 门全绿（2026-10-17"),
            encoding="utf-8")
        (n3 / "docs" / "PROJECT-MAP.md").write_text(pm_src, encoding="utf-8")
        _seed_routing(n3)
        cases.append(("N3 D3 门数腐烂（32 ≠ 42）",
                      str(n3), str(n3 / "docs" / HANDOFF_NAME),
                      str(n3 / "docs" / "PROJECT-MAP.md"), "D3"))

        # ---- N4: 路由路径改回打不开的短写法 → D4 红 ----
        n4 = tmp_root / "n4"
        (n4 / "docs").mkdir(parents=True)
        (n4 / "docs" / HANDOFF_NAME).write_text(handoff_src, encoding="utf-8")
        (n4 / "docs" / "PROJECT-MAP.md").write_text(
            pm_src.replace("`skillpack/skills/config/routing.json`", "`config/routing.json`"),
            encoding="utf-8")
        cases.append(("N4 D4 文档路径打不开",
                      str(n4), str(n4 / "docs" / HANDOFF_NAME),
                      str(n4 / "docs" / "PROJECT-MAP.md"), "D4"))

        # ---- N5: routing token 整条消失 → D4 红（fail-closed） ----
        n5 = tmp_root / "n5"
        (n5 / "docs").mkdir(parents=True)
        (n5 / "docs" / HANDOFF_NAME).write_text(handoff_src, encoding="utf-8")
        (n5 / "docs" / "PROJECT-MAP.md").write_text(
            pm_src.replace("`skillpack/skills/config/routing.json`", "`路由配置文件`"),
            encoding="utf-8")
        cases.append(("N5 D4 token 数 = 0（fail-closed）",
                      str(n5), str(n5 / "docs" / HANDOFF_NAME),
                      str(n5 / "docs" / "PROJECT-MAP.md"), "D4"))

        print(f"checker = {CHECKER}")
        print(f"tmp     = {tmp_root}\n")
        for name, repo, handoff, project_map, want_red in cases:
            rc, out = run_checker(Path(repo), Path(handoff), Path(project_map))
            v = verdicts(out)
            red = sorted(k for k, s in v.items() if s == "FAIL")
            got_red = v.get(want_red) == "FAIL"
            ok = got_red and rc == 1
            print(f"===== {name} =====")
            print(f"  rc={rc} verdicts={v}")
            print(f"  期望 `{want_red}` 判红：{'RED ok' if got_red else 'NOT RED ✗'}"
                  f"（实际判红的项：{red or '无'}）")
            print(f"  → {'ok' if ok else 'NG'}\n")
            if not ok:
                fails.append(name)
                print(out)

        # ---- 正例对照：真仓必须全绿（同一套判据，三态可分辨） ----
        rc, out = run_checker(REPO, REAL_HANDOFF, REAL_PROJECT_MAP)
        v = verdicts(out)
        print("===== 正例对照：真仓 =====")
        print(f"  rc={rc} verdicts={v}")
        green_ok = rc == 0 and all(s == "PASS" for s in v.values()) and len(v) == 4
        print(f"  → {'ok' if green_ok else 'NG'}\n")
        if not green_ok:
            fails.append("正例对照（真仓应全绿）")
            print(out)
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)

    print(f"cases={len(cases) + 1} ng={len(fails)}")
    if fails:
        print("NG: " + "、".join(fails))
        return 1
    print("ALL NEGATIVE CONTROLS BEHAVED AS EXPECTED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
