#!/usr/bin/env python3
"""verify-evidence-gate.py —— 证据门（ADF-R4* / assault.md 铁律的强制执行）

背景：
    「结论必须由 ≥2 条独立证据支撑」「状态列只能升到证据列支撑的高度」这两条
    写在 ops/ 与 templates/assault.md 里，但**从来没有任何门检查**。
    结果：单条证据可以静默升级成 validated/对照一致，报告看起来很实，其实是推断。

本门支持项目里实际存在的**两种**记录格式：

A. 表格格式（templates/assault.md 及其真实实例，主流）
     ## functions  | ID | 名称 | 所属层 | 路线 | 状态 | 证据 | 备注 |
     ## findings   | ID | 结论 | 类型 | 证据 |
   → 「对照一致」需证据列含 `diff/<F-ID>.md`（同输入对照证据）
   → 任一行的证据列引用的 `E-nnn` 必须在该文件里出现过

B. 块格式（ops/evidence-finding-path.md 的字段契约）
     ### F-{nnn}  - status: validated  - confidence: low  - evidence_ids: [E-001, E-002]
   → validated 需 evidence_ids ≥2；confidence=low 需 residual/待人工确认

用法：
    python skills/tests/verify-evidence-gate.py <case-dir|file> [...]
    python skills/tests/verify-evidence-gate.py --root <dir>
退出码：0 通过 / 1 有违规 / 2 用法错误

设计约束：只读；不依赖 YAML 库；**找不到任何可检查记录时返回 SKIP(10) 并明说 "no input" —— 不返回 PASS（P11：无输入≠审过）**
（不假装通过 —— 输出里会写明检查了几个文件）。
"""
from __future__ import annotations

import argparse
import io
import os
import re
import sys

# ---- 表格格式 ---------------------------------------------------------------
TABLE_HEADER_RE = re.compile(r"^\|\s*ID\s*\|(.+)\|\s*$", re.MULTILINE)
SECTION_RE = re.compile(r"^##\s+(functions|findings)\s*$", re.MULTILINE | re.IGNORECASE)

# 状态列里代表「已验证级别」的值（assault.md：对照一致 = 已测试的最高态）
VERIFIED_STATES = {"对照一致", "已测试", "validated"}

# ---- 块格式 -----------------------------------------------------------------
BLOCK_FINDING_RE = re.compile(r"^###\s+(F-\d+.*?)$", re.MULTILINE)
FIELD_RE = re.compile(r"^\s*-\s*\*{0,2}([a-z_]+)\*{0,2}\s*[:：]\s*(.*)$",
                       re.IGNORECASE | re.MULTILINE)
EVIDENCE_DEF_RE = re.compile(r"^###\s+(E-\d+)", re.MULTILINE)


def normalize_path(p: str) -> str:
    """把 msys/git-bash 风格 /c/foo 还原成 Windows 路径。"""
    if re.match(r"^/[a-zA-Z]/", p):
        return p[1].upper() + ":" + p[2:]
    return p


def find_repo_root() -> str:
    """从本文件位置向上找到含 skillpack/skills 的仓根。"""
    d = os.path.dirname(os.path.abspath(__file__))
    for _ in range(8):
        if os.path.isdir(os.path.join(d, "skillpack", "skills")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return os.getcwd()


def resolve_root(root: str) -> tuple[str, bool]:
    """把 --root 解析成真实存在的目录。返回 (路径, 是否成功)。

    为什么需要：门运行器从 skills/tests 启动，相对路径 `skillpack/examples` 会指向
    不存在的 skills/tests/skillpack/examples → 静默变成 "nothing to check"。
    静默降级比报错更坏，所以这里做两级兜底，并在都失败时由调用方 loudly 报出。
    """
    root = normalize_path(root)
    if os.path.isdir(root):
        return root, True
    cand = os.path.join(find_repo_root(), root.replace("/", os.sep))
    if os.path.isdir(cand):
        return cand, True
    return root, False


def split_row(line: str) -> list[str]:
    """拆 markdown 表格行 -> 单元格列表。"""
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def is_separator(cells: list[str]) -> bool:
    return all(re.fullmatch(r":?-{2,}:?", c or "") for c in cells) and bool(cells)


def parse_tables(text: str) -> dict[str, list[dict]]:
    """按 ## 小节抽取表格 -> {section: [ {header: value} ]}。"""
    result: dict[str, list[dict]] = {}
    # 找出每节的起止
    marks = [(m.start(), m.group(1).lower()) for m in SECTION_RE.finditer(text)]
    for i, (pos, name) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(text)
        chunk = text[pos:end]
        lines = chunk.split("\n")
        header: list[str] | None = None
        rows: list[dict] = []
        for ln in lines:
            if not ln.strip().startswith("|"):
                if header and rows:
                    break
                continue
            cells = split_row(ln)
            if header is None:
                if is_separator(cells):
                    continue
                header = [c.lower() for c in cells]
                continue
            if is_separator(cells):
                continue
            if len(cells) < 2:
                continue
            row = {header[j]: (cells[j] if j < len(cells) else "") for j in range(len(header))}
            if not any(row.values()):
                continue
            rows.append(row)
        if rows:
            result.setdefault(name, []).extend(rows)
    return result


def parse_block_findings(text: str) -> list[dict]:
    """块格式：### F-nnn 后跟 - field: value。"""
    out: list[dict] = []
    marks = list(BLOCK_FINDING_RE.finditer(text))
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        chunk = text[m.start():end]
        fields: dict[str, str] = {"_title": m.group(1).strip()}
        for fm in FIELD_RE.finditer(chunk):
            fields.setdefault(fm.group(1).lower(), fm.group(2).strip())
        out.append(fields)
    return out


def has_residual(fields: dict) -> bool:
    markers = ("residual", "待确认", "待人工", "人工确认", "human confirm",
               "unresolved", "残余", "未静默", "显式声明")
    for key in ("residual_risks", "residual_risk", "residual", "note", "remediation", "备注"):
        v = (fields.get(key, "") or "").lower()
        if any(m in v for m in markers):
            return True
    return False


def find_cell(row: dict, *names: str) -> str:
    for n in names:
        for k, v in row.items():
            if n in k:
                return v
    return ""


def collect_defined_evidence(path: str, text: str) -> set[str] | None:
    """收集该案例里"已定义"的 Evidence ID。

    来源（任一存在即启用存在性检查）：
      1. 本文件里的 `### E-nnn` 块
      2. 本文件里的 `- id: E-nnn` 字段
      3. 同目录或 ../evidence/ 下的 E-*.md 文件名
    返回 None 表示该案例没有任何证据清单 —— 此时不做存在性检查（避免误报）。
    """
    defined = set(EVIDENCE_DEF_RE.findall(text))
    defined |= set(re.findall(r"^\s*-\s*id:\s*(E-\d+)", text, re.MULTILINE | re.IGNORECASE))

    case_dir = os.path.dirname(os.path.abspath(path))
    for cand in (case_dir, os.path.join(case_dir, "evidence"),
                 os.path.join(os.path.dirname(case_dir), "evidence")):
        if not os.path.isdir(cand):
            continue
        for fn in os.listdir(cand):
            m = re.match(r"^(E-\d+)", fn)
            if m:
                defined.add(m.group(1))
    return defined or None


def check_file(text: str, path: str) -> tuple[list[str], int]:
    """返回 (错误列表, 检查的记录数)。"""
    errs: list[str] = []
    checked = 0

    referenced_e_known = collect_defined_evidence(path, text)

    tables = parse_tables(text)

    # ---- functions 表 ----
    for row in tables.get("functions", []):
        checked += 1
        fid = find_cell(row, "id") or "<no-id>"
        state = find_cell(row, "状态", "status")
        ev = find_cell(row, "证据", "evidence")
        if not state:
            continue
        if state.strip() in VERIFIED_STATES:
            if not ev.strip():
                errs.append(f"{path} :: functions/{fid} :: 状态={state} 但证据列为空"
                            f"（assault.md：状态列只能升到证据列支撑的高度）")
            else:
                if "diff/" not in ev and "E-" not in ev:
                    errs.append(f"{path} :: functions/{fid} :: 状态={state} 但证据列既无 diff/ 也无 E- 引用：{ev!r}")
                if state.strip() == "对照一致" and "diff/" not in ev:
                    errs.append(f"{path} :: functions/{fid} :: 状态=对照一致 但证据列无 `diff/<F-ID>.md`"
                                f"（assault.md §diff_baseline 要求同输入对照证据）")

    # ---- findings 表 ----
    for row in tables.get("findings", []):
        checked += 1
        aid = find_cell(row, "id") or "<no-id>"
        ev = find_cell(row, "证据", "evidence")
        if not ev.strip():
            errs.append(f"{path} :: findings/{aid} :: 证据列为空（ADF-R41：每条 Finding 必须映射到 Evidence）")
            continue
        for e in re.findall(r"E-\d+", ev):
            if referenced_e_known is not None and e not in referenced_e_known:
                errs.append(f"{path} :: findings/{aid} :: 引用了本文件未定义的 Evidence {e}")

    # ---- 块格式 ----
    for f in parse_block_findings(text):
        checked += 1
        name = f.get("_title", "<unnamed>")
        status = (f.get("status", "") or "").lower()
        if status not in ("validated", "对照一致"):
            continue
        eids = re.findall(r"E-\d+", f.get("evidence_ids", "") or f.get("evidence", ""))
        conf = (f.get("confidence", "") or "").lower()
        if len(eids) < 2:
            if has_residual(f):
                # ADF-R4* 允许的出口：单条证据 + 显式 residual_risk + 人工确认
                pass
            else:
                errs.append(
                    f"{path} :: {name} :: status={status} 但 evidence_ids={eids or '未填'}"
                    f"（ADF-R4*：validated SHOULD ≥2 条独立证据；单条须显式写 "
                    f"residual_risk + 人工确认，否则不许静默升级）"
                )
        if conf == "low" and not has_residual(f):
            errs.append(f"{path} :: {name} :: status={status} 且 confidence=low，"
                        f"但未见 residual_risk / 待人工确认 字段（ADF-R4*）")
        if referenced_e_known is not None:
            for e in eids:
                if e not in referenced_e_known:
                    errs.append(f"{path} :: {name} :: 引用了本文件未定义的 Evidence {e}")

    return errs, checked


def iter_case_files(root: str) -> list[str]:
    hits = []
    for dirpath, _dirs, files in os.walk(root):
        for fn in files:
            if not fn.lower().endswith(".md"):
                continue
            low = fn.lower()
            if low in ("assault.md", "report.md", "findings.md"):
                hits.append(os.path.join(dirpath, fn))
    return hits


# ---- 自检控制组 -------------------------------------------------------------
# 为什么需要：真实案例在用户项目目录里，不在仓库中。若只扫仓库，这道门会
# 永远输出 "nothing to check -> PASS"，等于一道永远不会红的门 —— 那是最坏的
# 情况（虚假安全感）。所以本门自带控制组：正例必须 PASS、反例必须 FAIL。
# 项目已有同样惯例：经验卡用反例控制组证明坏卡会转红。

_SELFTEST_GOOD = """\
## functions
| ID | 名称 | 所属层 | 路线 | 状态 | 证据 | 备注 |
|----|------|--------|------|------|------|------|
| F-001 | 合规 | L4 | rewrite | 对照一致 | E-001, diff/F-001.md | ok |

## findings
| ID | 结论 | 类型 | 证据 |
|----|------|------|------|
| A-001 | 合规 | reverse_algo | E-001 |
"""

_SELFTEST_BAD = [
    ("functions 状态升到对照一致但证据空", """\
## functions
| ID | 名称 | 所属层 | 路线 | 状态 | 证据 | 备注 |
|----|------|--------|------|------|------|------|
| F-002 | 无证据 | L4 | rewrite | 对照一致 |  | bad |
"""),
    ("对照一致但无 diff/ 证据", """\
## functions
| ID | 名称 | 所属层 | 路线 | 状态 | 证据 | 备注 |
|----|------|--------|------|------|------|------|
| F-003 | 缺 diff | L4 | rewrite | 对照一致 | E-001 | bad |
"""),
    ("findings 证据列为空", """\
## findings
| ID | 结论 | 类型 | 证据 |
|----|------|------|------|
| A-002 | 空证据 | proto |  |
"""),
    ("引用不存在的 Evidence", """\
### E-001

## findings

| ID | 结论 | 类型 | 证据 |
|----|------|------|------|
| A-003 | 悬空 | key | E-999 |
"""),
    ("块格式 validated 但单证据", """\
### E-001
### F-005
- status: validated
- confidence: high
- evidence_ids: [E-001]
"""),
]


def run_selftest() -> list[str]:
    """正例必须 PASS、每个反例必须 FAIL。返回失败说明列表（空 = 自检通过）。"""
    fails: list[str] = []

    errs, n = check_file(_SELFTEST_GOOD, "<selftest-good>")
    if errs:
        fails.append(f"自检正例本应 PASS，却报了 {len(errs)} 条：{errs[:2]}")
    if n < 2:
        fails.append(f"自检正例只解析到 {n} 条记录（应 ≥2）—— 解析器可能失效")

    for name, body in _SELFTEST_BAD:
        # 给反例一个假的 evidence 目录，触发存在性检查路径
        errs, _n = check_file(body, "<selftest-bad>")
        if not errs:
            fails.append(f"自检反例未转红：「{name}」")
    return fails


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cases", nargs="*", help="案例目录或文件")
    ap.add_argument("--root", default="", help="递归扫描该目录下所有案例")
    ap.add_argument("--no-selftest", action="store_true", help="跳过自检控制组（不建议）")
    ap.add_argument("--selftest-only", action="store_true", help="只跑自检控制组")
    args = ap.parse_args()

    exit_code = 0

    # 1) 自检控制组 —— 保证这道门有开火能力
    if not args.no_selftest:
        st = run_selftest()
        if st:
            print(f"verify-evidence-gate: FAIL（自检控制组未通过：{len(st)} 项）")
            for s in st:
                print("  " + s)
            return 1
        print("verify-evidence-gate: 自检控制组 PASS（正例通过 / 5 个反例全部转红）")

    if args.selftest_only:
        return 0

    # 2) 真实案例
    targets: list[str] = []
    if args.root:
        resolved, ok = resolve_root(args.root)
        if not ok:
            # 静默降级比报错更坏 —— 明确报出并失败，让人去修路径
            print(f"verify-evidence-gate: FAIL（--root 指向不存在的目录：{args.root}"
                  f"（尝试解析为 {resolved}））")
            return 1
        targets.extend(iter_case_files(resolved))
    for c in args.cases:
        c = normalize_path(c)
        if os.path.isdir(c):
            targets.extend(iter_case_files(c))
        elif os.path.isfile(c):
            targets.append(c)

    if not targets:
        # ★ 2026-10-15 独立审查 P11：「没有可审的对象」与「审过了且全过」曾经都输出 PASS。
        #   本仓已有四个「假绿」前科全是这个形态（run-ci-gates 的 docstring 自己写着
        #   "an absent path must never read as a pass"；check-fences.py 也曾因扫到 0 个
        #   文件报绿被记为故障）。这里拆开：无输入 = SKIP + 退出码 10（ci-gates.json 已把
        #   10 登记为 non_blocking_exits，会被响亮地报出来而不是静默通过）。
        print("verify-evidence-gate: SKIP (no input —— 未找到 assault.md/REPORT.md；"
              "本次什么也没审，这不是「审过且通过」)")
        return 10

    all_errs: list[str] = []
    files_checked = 0
    records_checked = 0
    for p in targets:
        try:
            with io.open(p, encoding="utf-8-sig", errors="replace") as f:
                txt = f.read()
        except OSError as exc:
            all_errs.append(f"{p} :: 读取失败: {exc}")
            continue
        files_checked += 1
        errs, n = check_file(txt, p)
        records_checked += n
        all_errs.extend(errs)

    if all_errs:
        print(f"verify-evidence-gate: FAIL（{len(all_errs)} 条违规 / {files_checked} 文件 / {records_checked} 条记录）")
        for e in all_errs:
            print("  " + e)
        return 1
    print(f"verify-evidence-gate: PASS（{files_checked} 文件 / {records_checked} 条记录，无违规）")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
