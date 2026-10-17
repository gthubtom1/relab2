#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test-doc-resolve.py —— 文档可解析回归测试（ASSESS ⑥-9 / ⑥-7 的 D1–D4）。

为什么存在
----------
ASSESS ⑥-9 的四条断言（D1–D4）原本只有人工命令，没有一条会被复跑的门守住 ——
`work/_assess-2026-10-17/evidence/09-doc-resolve.json` 是**一次性的只读取证**：
证完就散，下次谁把 HANDOFF 挪回 `_history/`、把门数写回 32、把路由路径写短，没人会知道。
本脚本把同一组判据变成可复跑的回归测试（先红后绿，见同目录
`test-doc-resolve-negctl.py` 的负控）。

四条判据（每条都自己报数，扫到 0 条 token 也判红 —— 不静默放行）
----------------------------------------------------------------
  D1  施工总令（HANDOFF）自己 Tier 1 表里声明的 Step 1 路径，按**仓根相对**必须能解析到文件。
  D2  该正本文件的**实际位置**不得落在它自己 Tier 3 黑名单宣布废弃的目录里
      （不许「正本躲在被自己宣布废弃的目录里」这种权威自相矛盾）；
      同时 Tier 1 表里每一条路径都不得落在黑名单前缀下。
  D3  HANDOFF「唯一验收标准」里写的门数 == `ci-gates.json` 的 `gates` 数组长度
      （数字腐烂的典型：曾经写 32，实测 42）。
  D4  `docs/PROJECT-MAP.md` 里被反引号包住、含 `routing` 且以 `.json` 结尾的路径 token，
      按**仓根相对**必须能打开文件。

用法
----
    python skillpack/skills/tests/test-doc-resolve.py
    python skillpack/skills/tests/test-doc-resolve.py --json
    # 负控用：把候选文档/仓库根换成临时副本，验证同一套判据会判红
    python skillpack/skills/tests/test-doc-resolve.py --repo-root <tmp> --handoff <tmp>/x.md \
        --project-map <tmp>/PROJECT-MAP.md --gates <repo>/ci-gates.json

退出码：0 四条全过；1 任一条不达期望（含 token 数 = 0 的 fail-closed 分支）。
标准库 only；**只读**：一个字节都不写（负控的变异件由 negctl 写在系统临时目录里）。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent          # skillpack/skills/tests
SKILLS = HERE.parent                            # skillpack/skills
SKILLPACK = SKILLS.parent                       # skillpack
REPO = SKILLPACK.parent                         # 仓根

HANDOFF_NAME = "HANDOFF-终极交接与施工任务书-全AI通用.md"

BACKTICK_TOKEN_RE = re.compile(r"`([^`\n]+)`")
TIER3_HEAD_RE = re.compile(r"^###\s*3\.\s*严重污染")
TIER1_HEAD_RE = re.compile(r"^###\s*1\.\s*唯一最高权威白名单")
HEAD_RE = re.compile(r"^#{1,6}\s")
# 黑名单目录 token：`docs/xxx/`（以 / 结尾、docs 开头的目录）
BLACKLIST_DIR_RE = re.compile(r"^docs/[^\s`]*/$")
# Tier 1 表里的文档路径 token：`docs/xxx.md`
TIER1_DOC_RE = re.compile(r"^docs/[^\s`]+\.md$")
GATE_COUNT_RE = re.compile(r"(\d+)\s*门")
# 本文档**主张**的门数只有两处，都用确定的形态抓（引文里的「31门全绿」这种历史引用
# 是两个旧模型报告的转述，不是本仓现状，故不纳入 —— 判据抓错对象比抓不到更坏）：
#   A  `全量 N 门`（§七「唯一验收标准」零改动条）
#   B  `CI 门禁套件` 那一行表格里的 `N 门`
CLAIM_A_RE = re.compile(r"全量\s*(\d+)\s*门")
CLAIM_B_ROW = "CI 门禁套件"


def _read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return ""


def _rel(p: Path, root: Path) -> str:
    try:
        return p.resolve().relative_to(root.resolve()).as_posix()
    except (ValueError, OSError):
        return p.as_posix()


def _section(lines: list[str], head_re: re.Pattern) -> list[str]:
    """取某个 `### …` 小节到下一个 `#{1,6} ` 标题之前的行（含标题行）。"""
    out: list[str] = []
    inside = False
    for ln in lines:
        if head_re.match(ln):
            inside = True
            out.append(ln)
            continue
        if inside and HEAD_RE.match(ln):
            break
        if inside:
            out.append(ln)
    return out


def _tokens(lines: list[str]) -> list[str]:
    toks: list[str] = []
    for ln in lines:
        toks.extend(BACKTICK_TOKEN_RE.findall(ln))
    return toks


# ---------------------------------------------------------------- D1
def check_d1(repo: Path, handoff: Path) -> dict:
    """Tier 1 表声明的 Step 1 路径必须能解析到文件。"""
    lines = _read(handoff).splitlines()
    tier1 = _section(lines, TIER1_HEAD_RE)
    declared = None
    for ln in tier1:
        if "Step 1" in ln:
            toks = [t.strip() for t in BACKTICK_TOKEN_RE.findall(ln)]
            for t in toks:
                if TIER1_DOC_RE.match(t):
                    declared = t
                    break
            if declared:
                break
    if not declared:
        return {"check": "D1", "ok": False, "tokens": 0,
                "detail": "Tier 1 表里找不到 Step 1 的 `docs/*.md` 路径（fail-closed）",
                "declared": None, "resolved": None}
    target = repo / declared
    ok = target.is_file()
    return {"check": "D1", "ok": ok, "tokens": 1, "declared": declared,
            "resolved": _rel(target, repo),
            "detail": "" if ok else f"声明的路径按仓根相对打不开：{declared}"}


# ---------------------------------------------------------------- D2
def check_d2(repo: Path, handoff: Path) -> dict:
    """正本不得落在 Tier 3 黑名单目录里；Tier 1 的每条路径也不得落在黑名单前缀下。"""
    lines = _read(handoff).splitlines()
    tier3 = _section(lines, TIER3_HEAD_RE)
    tier1 = _section(lines, TIER1_HEAD_RE)
    black = sorted({t.strip() for t in _tokens(tier3) if BLACKLIST_DIR_RE.match(t.strip())})
    rel_handoff = _rel(handoff, repo)

    violations: list[str] = []
    if any(rel_handoff == b.rstrip("/") or rel_handoff.startswith(b) for b in black):
        violations.append(f"正本实际位置 `{rel_handoff}` 落在黑名单目录 {black} 之下")

    tier1_docs = sorted({t.strip() for t in _tokens(tier1) if TIER1_DOC_RE.match(t.strip())})
    for d in tier1_docs:
        if any(d == b.rstrip("/") or d.startswith(b) for b in black):
            violations.append(f"Tier 1 的 `{d}` 落在黑名单目录之下")

    ok = not violations and bool(black) and bool(tier1_docs)
    if not black:
        violations.append("Tier 3 段里一条黑名单目录 token 都没抽到（fail-closed）")
    if not tier1_docs:
        violations.append("Tier 1 段里一条 `docs/*.md` token 都没抽到（fail-closed）")
    return {"check": "D2", "ok": ok, "tokens": len(black) + len(tier1_docs),
            "blacklist_dirs": black, "tier1_docs": tier1_docs,
            "handoff_location": rel_handoff,
            "detail": "；".join(violations) if violations else ""}


# ---------------------------------------------------------------- D3
def check_d3(handoff: Path, gates: Path) -> dict:
    """HANDOFF 里写的门数必须等于 ci-gates.json 的 gates 数组长度。"""
    try:
        manifest = json.loads(_read(gates))
        gate_total = len(manifest["gates"])
    except (OSError, ValueError, KeyError, TypeError) as e:
        return {"check": "D3", "ok": False, "tokens": 0,
                "detail": f"读不到门禁清单 {gates}：{e!r}（fail-closed）"}

    lines = _read(handoff).splitlines()
    claimed: list[tuple[int, str]] = []
    # A `全量 N 门` —— §七「唯一验收标准」零改动条的主张形态
    for ln in lines:
        for m in CLAIM_A_RE.finditer(ln):
            claimed.append((int(m.group(1)), "主张 A（§七「唯一验收标准」零改动条 `全量 N 门`）"))
    # B `CI 门禁套件` 表格行的 `N 门`
    for ln in lines:
        if CLAIM_B_ROW in ln:
            for m in GATE_COUNT_RE.finditer(ln):
                claimed.append((int(m.group(1)), "主张 B（家底盘点表 `CI 门禁套件` 行的 `N 门`）"))

    ok = bool(claimed) and all(n == gate_total for n, _ in claimed)
    tag_a = sum(1 for _, w in claimed if w.startswith("主张 A"))
    tag_b = sum(1 for _, w in claimed if w.startswith("主张 B"))
    bad = [f"{n}（{where}）" for n, where in claimed if n != gate_total]
    return {"check": "D3", "ok": ok, "tokens": len(claimed), "gate_total": gate_total,
            "claimed": [n for n, _ in claimed], "claims_A": tag_a, "claims_B": tag_b,
            "detail": "" if ok else (f"与 gates 数组长度 {gate_total} 不一致：" + "、".join(bad)
                                     if claimed else "文档里一处门数都没抽到（fail-closed）")}


# ---------------------------------------------------------------- D4
def check_d4(repo: Path, project_map: Path) -> dict:
    """PROJECT-MAP 里 `…routing…json` 的路径 token 必须按仓根相对能打开。"""
    lines = _read(project_map).splitlines()
    toks: list[str] = []
    for ln in lines:
        for t in BACKTICK_TOKEN_RE.findall(ln):
            t = t.strip()
            if "routing" in t and t.endswith(".json"):
                toks.append(t)
    toks = sorted(set(toks))
    if not toks:
        return {"check": "D4", "ok": False, "tokens": 0,
                "detail": "PROJECT-MAP 里抽不到 routing 路径 token（fail-closed，不许静默放行）"}
    bad = [t for t in toks if not (repo / t).is_file()]
    return {"check": "D4", "ok": not bad, "tokens": len(toks), "tokens_found": toks,
            "unresolved": bad,
            "detail": "" if not bad else "按仓根相对打不开：" + "、".join(bad)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo-root", default=str(REPO))
    ap.add_argument("--handoff", default="")
    ap.add_argument("--project-map", default="")
    ap.add_argument("--gates", default="")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    repo = Path(args.repo_root)
    handoff = Path(args.handoff) if args.handoff else repo / "docs" / HANDOFF_NAME
    project_map = Path(args.project_map) if args.project_map else repo / "docs" / "PROJECT-MAP.md"
    gates = Path(args.gates) if args.gates else HERE / "ci-gates.json"

    results = [
        check_d1(repo, handoff),
        check_d2(repo, handoff),
        check_d3(handoff, gates),
        check_d4(repo, project_map),
    ]
    fails = [r for r in results if not r["ok"]]
    payload = {"repo_root": str(repo), "handoff": str(handoff),
               "project_map": str(project_map), "gates": str(gates),
               "checks": len(results), "fail": len(fails), "results": results}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"repo_root = {repo}")
        print(f"handoff   = {handoff}")
        for r in results:
            mark = "PASS" if r["ok"] else "FAIL"
            print(f"[{mark}] {r['check']} tokens={r['tokens']}"
                  + (f" :: {r['detail']}" if r["detail"] else ""))
            if r["check"] == "D1":
                print(f"          declared={r.get('declared')} resolved={r.get('resolved')}")
            if r["check"] == "D2":
                print(f"          handoff_location={r.get('handoff_location')} "
                      f"blacklist={r.get('blacklist_dirs')}")
            if r["check"] == "D3":
                print(f"          gate_total={r.get('gate_total')} claimed={r.get('claimed')}")
            if r["check"] == "D4":
                print(f"          tokens_found={r.get('tokens_found')} "
                      f"unresolved={r.get('unresolved')}")
        print(f"checks={len(results)} fail={len(fails)}")
        print("RESULT: " + ("ALL PASS" if not fails else "RED"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
