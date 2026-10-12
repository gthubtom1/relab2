# -*- coding: utf-8 -*-
"""review_case.py rebuild 交付审计的负控：证明它真的抓得到坏状态，也真的放行好状态。

★ 为什么必须存在
  这是本仓最危险的失败模式：门禁「报绿但其实没检查」。review_case.py 从只读证据图
  审查扩展为「检测到 rebuild.md 时做交付审计」之后，最坏的情况是：
    · rebuild.md 存在，但审计根本没跑（早退分支写错）→ 坏 case 也报 PASS；
    · 审计跑了，但字段读错（列索引偏一位）→ 永远读不到状态，永远不报错。
  汇总数字上「全部干净」和「什么都没看」长得一模一样，靠肉眼看 review_case.py 源码
  区分不了。所以每个检查点都要有一份能证明「它确实拦了」的对照。

★ 与单测的分工
  tests/test_review_case.py 直接调 review_case()（同进程，快）；
  本负控**走子进程 CLI**（python review_case.py <case> --format json），验证的是
  「用户实际会跑的那条命令」的退出码 —— 单测全绿而 CLI 早退，是另一类假绿。

退出码
  0  全部符合期望
  1  有漏报、误报，或门禁已被绕过
"""
import io
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REVIEW = os.path.join(HERE, "..", "case-review", "scripts", "review_case.py")
REVIEW = os.path.abspath(REVIEW)
PY = sys.executable

# ---------------------------------------------------------------- fixtures

BASE_SCOPE = """# Case Scope

## auth
- status: granted
- basis: lab_only

## in_scope
- assets:
  - sample.bin

## network_profile
- mode: offline

## signoff
- ready_for_act: true
"""

BASE_WORKITEMS = """# Work Items

| ID | title | role | targets | surface | status | evidence | notes |
|----|-------|------|---------|---------|--------|----------|-------|
| WI-001 | Rebuild demo | impl | sample.bin | binary | done | | |

## Coverage
- [x] Recon/analysis complete for in_scope assets
- [x] Critical/High candidates triaged (or N/A for pure RE)
- [x] Validated findings have Evidence (E-*)
- [x] Path documented (attack/call/solve)
- [x] Timeline continuous across major phases
- [x] Report via docs-generator
- [x] field-journal anonymized
"""

BASE_TIMELINE = """# Timeline (append-only)

## 2026-10-12T00:00:00Z | impl | build
- action: rebuild demo
- decision_delta: [F-001 implemented]
- carry_forward_refs: [rebuild.md, GOAL.md]
"""

REBUILD_TEMPLATE = """# Rebuild

## target

- deliverable: `{deliverable}`
- form: script

## functions

| ID | 名称 | 入口 | 预期输出 | 验收条件 | 路线 |
|----|------|------|----------|----------|------|
| F-001 | demo | --mode a | 2 | same output | rewrite |
{extra_functions}

## acceptance

| ID | 状态 | 证据 (E-xxx / diff 记录) | 备注 |
|----|------|--------------------------|------|
| F-001 | {state} | {evidence} | {note} |
{extra_acceptance}

## diff_baseline

- baseline_dir: `baseline/`
- diff_dir: `diff/`

| F-ID | 输入条件 | 原程序结果 | 新实现结果 | 是否一致 | 说明 |
|------|----------|------------|------------|----------|------|
{diff_rows}

## out_of_delivery

| 项 | 理由 |
|----|------|
| GUI | out of scope |
"""

GOOD_DIFF_ROW = "| F-001 | --mode a | 2 | 2 | 一致 | ok |"

COVERAGE_WITH_REBUILD = """## Coverage (rebuild)
- [x] 功能清单全覆盖 (every functions row has an acceptance row)
- [x] 关键功能状态 (critical functions carry a state + evidence)
- [x] 已知差异已记录 (known deviations recorded)
"""


def write_case(root, rebuild_text=None, workitems_text=None, with_diff_record=True):
    evidence = os.path.join(root, "evidence")
    report = os.path.join(root, "report")
    diff = os.path.join(root, "diff")
    os.makedirs(evidence)
    os.makedirs(report)
    os.makedirs(diff)
    with io.open(os.path.join(root, "scope.md"), "w", encoding="utf-8") as fh:
        fh.write(BASE_SCOPE)
    with io.open(os.path.join(root, "workitems.md"), "w", encoding="utf-8") as fh:
        fh.write(workitems_text if workitems_text is not None else BASE_WORKITEMS)
    with io.open(os.path.join(root, "timeline.md"), "w", encoding="utf-8") as fh:
        fh.write(BASE_TIMELINE)
    if with_diff_record:
        with io.open(os.path.join(diff, "F-001.md"), "w", encoding="utf-8") as fh:
            fh.write("input=--mode a\noriginal=2\nrebuilt=2\nsame=yes\n")
    if rebuild_text is not None:
        with io.open(os.path.join(root, "rebuild.md"), "w", encoding="utf-8") as fh:
            fh.write(rebuild_text)


def run_review(root):
    """Run the CLI a user would run; return (exit_code, parsed_json_or_None)."""
    proc = subprocess.run(
        [PY, REVIEW, root, "--format", "json"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    payload = None
    if proc.stdout.strip():
        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError:
            payload = None
    return proc.returncode, payload


def codes(payload):
    if not payload:
        return []
    return [item["code"] for item in payload.get("issues", [])]


# (用例名, kind, rebuild_text, workitems_text, with_diff_record, 期望 codes 必须出现, 期望 exit, 说明)
#   kind: must_pass（0 rebuild.* 报错，exit 0）/ must_fail（必须出现期望 code）/ plain（无 rebuild.md）
#   workitems_text: None = 默认（含三项复刻 Coverage）；字符串 = 覆盖
def good_rebuild(state="对照一致", evidence="diff/F-001.md", note="", diff_rows=GOOD_DIFF_ROW,
                 extra_functions="", extra_acceptance=""):
    return REBUILD_TEMPLATE.format(
        deliverable="rebuilt-demo", state=state, evidence=evidence, note=note,
        extra_functions=extra_functions, extra_acceptance=extra_acceptance, diff_rows=diff_rows,
    )


def workitems_with_rebuild():
    return BASE_WORKITEMS + "\n" + COVERAGE_WITH_REBUILD


CASES = [
    # ---------- 好 fixture：必须放行 ----------
    ("good-full-table", "must_pass",
     good_rebuild(), workitems_with_rebuild(), True,
     [], 0, "完整对账表 + 三项 Coverage：0 报错，exit 0"),

    # ---------- 坏 fixture 1：状态虚高 ----------
    ("bad-state-exceeds-evidence", "must_fail",
     good_rebuild(state="已测试", evidence=""), workitems_with_rebuild(), True,
     ["rebuild.state_exceeds_evidence"], 1, "标「已测试」但证据列空 → 状态高于证据"),

    # ---------- 坏 fixture 2：对照表缺行 ----------
    ("bad-diff-row-missing", "must_fail",
     good_rebuild(diff_rows=""), workitems_with_rebuild(), True,
     ["rebuild.diff_row_missing"], 1, "标「对照一致」但 diff_baseline 无该行 → 缺对照证据"),

    # 坏 fixture 2b：对照表行存在但五列没填齐
    ("bad-diff-incomplete", "must_fail",
     good_rebuild(state="已测试", diff_rows="| F-001 | --mode a | 2 |  | 一致 |  |"),
     workitems_with_rebuild(), True,
     ["rebuild.diff_incomplete"], 1, "对照行五列缺两列 → 未填齐"),

    # ---------- 坏 fixture 3：Coverage 缺项 ----------
    ("bad-coverage-missing", "must_fail",
     good_rebuild(), BASE_WORKITEMS, True,
     ["rebuild.coverage_missing"], 1, "workitems Coverage 缺「三项复刻项」→ 报缺项"),

    # ---------- 附加：受限无原因 ----------
    ("bad-limited-no-note", "must_fail",
     good_rebuild(state="受限", evidence="", note="", diff_rows=""), workitems_with_rebuild(), True,
     ["rebuild.limited_note_missing"], 1, "受限行未写原因/影响/替代方案"),

    # ---------- 附加：证据指向不存在的 diff 记录 ----------
    ("bad-diff-record-missing", "must_fail",
     good_rebuild(state="已测试", evidence="diff/NOPE.md"), workitems_with_rebuild(), True,
     ["rebuild.diff_record_missing"], 1, "证据列引用的 diff 记录文件不存在"),

    # ---------- 附加：functions 与 acceptance 未 1:1 ----------
    ("bad-acceptance-missing", "must_fail",
     good_rebuild(extra_acceptance="| F-002 | 已分析 | ev | |"), workitems_with_rebuild(), True,
     ["rebuild.function_unknown"], 1, "acceptance 有 F-002 而 functions 没有 → 清单未对齐"),

    # ---------- 附加：状态「对照一致」但对照行还没说话 ----------
    ("bad-verdict-unproven", "must_fail",
     good_rebuild(state="对照一致", diff_rows="| F-001 | --mode a | 2 | 2 | 待判 | 未对照 |"),
     workitems_with_rebuild(), True,
     ["rebuild.diff_verdict_unproven"], 1, "状态写成对照一致、对照行 verdict=「待判」→ 宣布成功但证据没说话"),

    ("bad-verdict-empty", "must_fail",
     good_rebuild(state="已测试", diff_rows="| F-001 | --mode a | 2 | 2 | | 空 verdict |"),
     workitems_with_rebuild(), True,
     ["rebuild.diff_verdict_unproven"], 1, "verdict 空串同样不配完成态"),

    ("bad-verdict-conflict", "must_fail",
     good_rebuild(state="对照一致", diff_rows="| F-001 | --mode a | 2 | 3 | 不一致 | 值不同 |"),
     workitems_with_rebuild(), True,
     ["rebuild.diff_verdict_conflict"], 1, "状态对照一致、对照行明说不一致 → 冲突"),

    ("bad-verdict-notyet", "must_fail",
     good_rebuild(state="对照一致", diff_rows="| F-001 | --mode a | 2 | 2 | 尚未一致 | 未跑完 |"),
     workitems_with_rebuild(), True,
     ["rebuild.diff_verdict_conflict"], 1, "「尚未一致」必须被拦（归 conflict，绝不配完成态）"),

    # ---------- 必须放行：无 rebuild.md 的老 case（回归底线） ----------
    ("plain-case-no-rebuild", "plain",
     None, BASE_WORKITEMS, True,
     [], 0, "无 rebuild.md：不出现 rebuild.*，exit 0"),
]


def run_case(name, kind, rebuild_text, workitems_text, with_diff_record, expect_codes, expect_exit, note):
    with tempfile.TemporaryDirectory(prefix="rebuild-negctl-") as scratch:
        root = os.path.join(scratch, "case")
        if kind == "plain":
            write_case(root, rebuild_text=None, workitems_text=workitems_text,
                       with_diff_record=with_diff_record)
        else:
            write_case(root, rebuild_text=rebuild_text, workitems_text=workitems_text,
                       with_diff_record=with_diff_record)
        exit_code, payload = run_review(root)

        problems = []
        if payload is None and kind != "plain":
            problems.append("CLI produced no parseable JSON (exit %s)" % exit_code)
        if payload is not None:
            seen = codes(payload)
            if kind != "plain" and not payload.get("rebuild"):
                problems.append("payload has no 'rebuild' key although rebuild.md exists (audit never ran)")
            if kind == "plain" and "rebuild" in payload:
                problems.append("plain case grew a 'rebuild' key (output changed for non-rebuild cases)")
            for expected in expect_codes:
                if expected not in seen:
                    problems.append("expected code missing: %s (seen: %s)" % (expected, ",".join(seen) or "(none)"))
            if kind != "plain" and not expect_codes:
                unexpected = [code for code in seen if code.startswith("rebuild.")]
                if unexpected:
                    problems.append("good fixture reported rebuild issues: %s" % ",".join(unexpected))
        if exit_code != expect_exit:
            problems.append("exit code %s, expected %s" % (exit_code, expect_exit))
        return problems


def main():
    failures = 0
    total = 0
    for name, kind, rebuild_text, workitems_text, with_diff_record, expect_codes, expect_exit, note in CASES:
        total += 1
        problems = run_case(name, kind, rebuild_text, workitems_text, with_diff_record,
                            expect_codes, expect_exit, note)
        if problems:
            failures += 1
            print("FAIL %s: %s" % (name, note))
            for problem in problems:
                print("      - %s" % problem)
        else:
            print("OK   %s: %s" % (name, note))
    print("\n%d/%d controls honoured" % (total - failures, total))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
