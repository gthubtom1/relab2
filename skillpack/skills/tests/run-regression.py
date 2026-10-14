#!/usr/bin/env python3
"""run-regression.py —— 失败→技能回归表（L2.1）的门

背景：
    本包此前 26 个门全是格式/一致性门，**0 个行为门**。结果是「每次说改好了、
    下次真实做又出问题」—— 因为「改好了」只能验形状，不能验行为。
    这张表是打破循环的机械核心：每个真实项目留一条 case，记录
    「期望链路」与「这次实际卡在哪」。

本门做四件事（都不需要模型调用，所以能进 CI）：
    1. 每条 case 的必填字段是否齐全
    2. `expect_chain` 里引用的技能/文档是否真实存在（防悬空承诺）
    3. `known_failures` 是否为空 —— 空的必须显式写"正控/无"的说明（防假填）
    4. 统计 open / resolved，报出未收敛的失败数

模型驱动的行为门（`test-routing-e2e` / `test-trigger-rate` / `test-assault-behavior`）
在 L2.2，它们要花模型调用，挂 non-blocking 先跑数。

用法：
    python skills/tests/run-regression.py [--json] [--strict]
退出码：0 通过 / 1 有违规（--strict 时 open case 也算违规）
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

CASES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cases")
REQUIRED = ("id", "date", "domain", "task_verbatim", "expect_chain",
            "expect_deliverable", "known_failures", "status")
VALID_STATUS = ("open", "resolved")
# 允许 known_failures 为空的显式声明（防假填）
EMPTY_OK_RE = re.compile(r"无（|无\s*$|正控|示例案例|positive control")


def find_repo_root() -> str:
    d = os.path.dirname(os.path.abspath(__file__))
    for _ in range(8):
        if os.path.isdir(os.path.join(d, "skillpack", "skills")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return os.getcwd()


def chain_entry_exists(entry: str, repo_root: str, skills_root: str) -> bool:
    """expect_chain 的一条是否指向真实存在的技能目录或文档。"""
    e = entry.strip()
    if not e:
        return False
    if e in ("ctf-sandbox", "pwn-chain", "docs-generator", "case-review",
             "reverse-engineering", "x64dbg-reverse", "ida-reverse",
             "ghidra-reverse", "radare2", "apk-reverse", "malware-analysis"):
        if os.path.isfile(os.path.join(skills_root, e, "SKILL.md")):
            return True
    for base in (skills_root, repo_root, os.path.join(repo_root, "skillpack")):
        if os.path.exists(os.path.join(base, e.replace("/", os.sep))):
            return True
    # 纯技能名（无斜杠）也接受
    if "/" not in e and os.path.isfile(os.path.join(skills_root, e, "SKILL.md")):
        return True
    return False


def load_cases() -> tuple[list[dict], list[str]]:
    cases, errs = [], []
    if not os.path.isdir(CASES_DIR):
        return cases, [f"cases 目录不存在: {CASES_DIR}"]
    for fn in sorted(os.listdir(CASES_DIR)):
        if not fn.endswith((".yaml", ".yml")):
            continue
        p = os.path.join(CASES_DIR, fn)
        if yaml is None:
            errs.append(f"{fn} :: 需要 PyYAML（pip install pyyaml）")
            continue
        try:
            with open(p, encoding="utf-8-sig") as f:
                doc = yaml.safe_load(f)
        except Exception as exc:  # noqa: BLE001
            errs.append(f"{fn} :: YAML 解析失败: {exc}")
            continue
        if not isinstance(doc, dict):
            errs.append(f"{fn} :: 顶层不是映射")
            continue
        doc["_file"] = fn
        cases.append(doc)
    return cases, errs


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true",
                    help="open case 也判为违规（用于「彻底完成」验收时刻）")
    args = ap.parse_args()

    repo_root = find_repo_root()
    skills_root = os.path.join(repo_root, "skillpack", "skills")

    cases, errs = load_cases()
    if not cases and not errs:
        print("run-regression: FAIL（cases/ 里一条 case 都没有 —— 回归表是空的，等于没有）")
        return 1

    for c in cases:
        fn = c.get("_file", "?")
        for k in REQUIRED:
            if k not in c or c[k] in (None, "", []):
                if k == "known_failures" and k in c:
                    pass  # 单独判
                else:
                    errs.append(f"{fn} :: 缺必填字段 `{k}`")

        st = str(c.get("status", "")).strip()
        if st and st not in VALID_STATUS:
            errs.append(f"{fn} :: status={st!r} 不在 {VALID_STATUS}")

        chain = c.get("expect_chain") or []
        if not isinstance(chain, list):
            errs.append(f"{fn} :: expect_chain 必须是列表")
        else:
            for e in chain:
                if not chain_entry_exists(str(e), repo_root, skills_root):
                    errs.append(f"{fn} :: expect_chain 引用了不存在的目标：{e!r}（悬空承诺）")

        kf = c.get("known_failures") or []
        if not isinstance(kf, list):
            errs.append(f"{fn} :: known_failures 必须是列表")
            kf = []
        if not kf:
            blob = json.dumps(c, ensure_ascii=False)
            if not EMPTY_OK_RE.search(str(c.get("note", "")) + str(c.get("expect_deliverable", ""))):
                errs.append(f"{fn} :: known_failures 为空且未显式声明「无/正控」—— "
                            f"防假填（真实项目几乎不可能零失败）")

        for f in kf:
            if not isinstance(f, str) or len(str(f).strip()) < 8:
                errs.append(f"{fn} :: known_failures 有一条过短（<8 字符），像占位符：{f!r}")

    open_cases = [c for c in cases if str(c.get("status", "")).strip() == "open"]
    n_open_fail = sum(len(c.get("known_failures") or []) for c in open_cases)
    if args.strict:
        for c in open_cases:
            errs.append(f"{c.get('_file')} :: status=open（--strict 下视为未收敛）")

    summary = {
        "cases_total": len(cases),
        "open": len(open_cases),
        "resolved": len(cases) - len(open_cases),
        "open_failures": n_open_fail,
        "errors": errs,
    }

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"run-regression: cases={len(cases)} open={len(open_cases)} "
              f"resolved={summary['resolved']} open_failures={n_open_fail}")
        if errs:
            print(f"  FAIL（{len(errs)} 条）")
            for e in errs:
                print("    " + e)
        else:
            print("  PASS（字段齐全 / 无悬空引用 / 无假填）")
        if open_cases and not args.strict:
            print("  未收敛的 case（不算失败，但必须在解决后改 status）：")
            for c in open_cases:
                print(f"    - {c.get('_file')}  failures={len(c.get('known_failures') or [])}")

    return 1 if errs else 0


if __name__ == "__main__":
    raise SystemExit(main())
