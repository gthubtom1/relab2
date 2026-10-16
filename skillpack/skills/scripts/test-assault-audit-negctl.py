# -*- coding: utf-8 -*-
"""review_case.py assault 滚动报告审计的负控：证明它真的抓得到坏状态，也真的放行好状态。

★ 为什么必须存在
  review_case.py 从「检测 rebuild.md 时做交付审计」再扩展出「检测 assault.md 时做
  滚动报告审计」之后，最坏的情况与前两次同形：
    · assault.md 存在，但审计根本没跑（早退分支写错）→ 坏 case 也报 PASS；
    · 审计跑了，但字段读错（列索引偏一位）→ 永远读不到状态，永远不报错。
  汇总数字上「全部干净」和「什么都没看」长得一模一样。每个检查点都要有一份
  能证明「它确实拦了」的对照。

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
| WI-001 | Assault demo | impl | sample.bin | binary | done | | |

## Coverage
- [x] Recon/analysis complete for in_scope assets
"""

BASE_TIMELINE = """# Timeline (append-only)

## 2026-10-13T00:00:00Z | impl | build
- action: assault demo
- carry_forward_refs: [assault.md]
"""

ASSAULT_TEMPLATE = """# Assault 滚动报告

## 0 状态行

- current_state: `{state}`
- since: `2026-10-13 10:00`
- goal_now: `<demo>`

## target

- deliverable: `{deliverable}`
- form: exe

## layers

| 层 | 类型 | 状态 | 证据 |
|----|------|------|------|
| L1 | 壳层 | 已过 | E-001 |
{extra_layers}

## routes

| 候选路线 | 证据 | 预计成本 | 主要风险 | 为什么选/不选 |
|----------|------|----------|----------|----------------|
| patch | E-001 | 低 | 少 | 选 |

- recommended: patch
- rejected_because: rewrite 成本高
- confidence: medium

## functions

| ID | 名称 | 所属层 | 路线 | 状态 | 证据 | 备注 |
|----|------|--------|------|------|------|------|
| F-001 | 校验 | L4 | patch | {fstate} | {fevidence} | {fnote} |

## unknowns

| ID | 问题 | 影响功能 | 已尝试 | 下一步 | 是否阻塞 |
|----|------|----------|--------|--------|----------|
| U-001 | {uquestion} | {uimpact} | 断网 | {unext} | {ublock} |

## diff_baseline

| F-ID | 输入条件 | 原程序结果 | 新实现结果 | 是否一致 | 说明 |
|------|----------|------------|------------|----------|------|
{diff_rows}

## out_of_delivery

| 项 | 理由 |
|----|------|
| GUI | out of scope |
"""

GOOD_DIFF_ROW = "| F-001 | --mode a | 2 | 2 | 一致 | ok |"
BLOCKED_LAYER_OK = "| L4 | 业务层 | blocked | E-002 | 原因: 云端样本不可得; 影响: F-001 无法对照; 替代: 本地 mock |"


def good_assault(state="EXECUTE", deliverable="build/rebuilt.exe", fstate="对照一致",
                 fevidence="diff/F-001.md", fnote="", diff_rows=GOOD_DIFF_ROW,
                 uquestion="云端行为", uimpact="F-001", unext="抓包", ublock="no",
                 extra_layers="| L4 | 业务层 | 进行中 | E-002 |"):
    return ASSAULT_TEMPLATE.format(
        state=state, deliverable=deliverable, extra_layers=extra_layers,
        fstate=fstate, fevidence=fevidence, fnote=fnote,
        uquestion=uquestion, uimpact=uimpact, unext=unext, ublock=ublock,
        diff_rows=diff_rows,
    )


def write_case(root, assault_text=None, make_deliverable=True):
    evidence = os.path.join(root, "evidence")
    report = os.path.join(root, "report")
    diff = os.path.join(root, "diff")
    build = os.path.join(root, "build")
    os.makedirs(evidence)
    os.makedirs(report)
    os.makedirs(diff)
    os.makedirs(build)
    with io.open(os.path.join(root, "scope.md"), "w", encoding="utf-8") as fh:
        fh.write(BASE_SCOPE)
    with io.open(os.path.join(root, "workitems.md"), "w", encoding="utf-8") as fh:
        fh.write(BASE_WORKITEMS)
    with io.open(os.path.join(root, "timeline.md"), "w", encoding="utf-8") as fh:
        fh.write(BASE_TIMELINE)
    if make_deliverable:
        with io.open(os.path.join(build, "rebuilt.exe"), "wb") as fh:
            fh.write(b"MZ fake rebuilt")
    with io.open(os.path.join(diff, "F-001.md"), "w", encoding="utf-8") as fh:
        fh.write("draft")
    if assault_text is not None:
        with io.open(os.path.join(root, "assault.md"), "w", encoding="utf-8") as fh:
            fh.write(assault_text)


def run_review(root):
    """Run the CLI a user would run; return (exit_code, parsed_json_or_None)."""
    proc = subprocess.run(
        [PY, REVIEW, root, "--format", "json"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300,
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


# (用例名, kind, assault_text, make_deliverable, 期望 codes, 期望 exit, 说明)
#   kind: must_fail（必须出现期望的 assault.* error，exit 1）/
#         must_pass（不得出现 assault.* error，exit 0）/
#         plain（无 assault.md：不得出现 assault.* 与 assault 键）
CASES = [
    # ---------- 好 fixture：必须放行 ----------
    ("good-full-report", "must_pass",
     good_assault(), True, [], 0,
     "状态行/layers/functions/unknowns/deliverable 全齐 → 0 assault 报错，exit 0"),

    # ---------- 坏 fixture 1：状态行 ----------
    ("bad-state-line-missing", "must_fail",
     good_assault().replace("- current_state: `EXECUTE`", "- current_state:"), True,
     ["assault.state_line_missing"], 1, "状态行缺 → 报告说不清「现在到哪」"),

    ("bad-state-line-invalid", "must_fail",
     good_assault(state="DONE"), True,
     ["assault.state_line_invalid"], 1, "current_state 不在四状态内"),

    # ---------- 坏 fixture 2：layers ----------
    ("bad-layer-no-evidence", "must_fail",
     good_assault(extra_layers="| L4 | 业务层 | 进行中 |  |"), True,
     ["assault.layer_evidence_missing"], 1, "layers 行缺证据"),

    ("bad-blocked-no-reasons", "must_fail",
     good_assault(extra_layers="| L4 | 业务层 | blocked | E-002 |"), True,
     ["assault.blocked_reason_missing"], 1, "blocked 行没写原因/影响/替代"),

    # ---------- 坏 fixture 3：functions 状态虚高 ----------
    ("bad-state-exceeds-evidence", "must_fail",
     good_assault(fstate="已测试", fevidence=""), True,
     ["assault.state_exceeds_evidence"], 1, "标「已测试」但证据列空 → 状态高于证据"),

    ("bad-diff-row-missing", "must_fail",
     good_assault(diff_rows=""), True,
     ["assault.diff_row_missing"], 1, "完成态却没有 diff_baseline 行"),

    ("bad-verdict-unproven", "must_fail",
     good_assault(fstate="已测试", fevidence="E-003",
                  diff_rows="| F-001 | --mode a | 2 | 2 | 待判 | 未对照 |"), True,
     ["assault.diff_verdict_unproven"], 1, "完成态但 verdict 未断言一致（待判）"),

    ("bad-verdict-conflict", "must_fail",
     good_assault(diff_rows="| F-001 | --mode a | 2 | 3 | 不一致 | 值不同 |"), True,
     ["assault.diff_verdict_conflict"], 1, "完成态但 verdict 明说不一致"),

    # ---------- 坏 fixture 4：unknowns ----------
    ("bad-unknown-missing-columns", "must_fail",
     good_assault(unext="", ublock=""), True,
     ["assault.unknown_field_missing"], 1, "unknowns 缺「下一步 / 是否阻塞」"),

    # ---------- 坏 fixture 5：完成形态（§2.2 后门已收窄） ----------
    ("bad-deliverable-missing-file", "must_fail",
     good_assault(deliverable="build/NOPE.exe"), False,
     ["assault.deliverable_missing"], 1, "deliverable 指向的文件不存在且无受限功能行"),

    # 旧契约：routes/layers 行随便写 blocked+三词就能豁免整案 → 这正是「打不穿可过审」后门。
    # 新契约：整案级豁免被关闭；只有「功能行 受限 + 无完成态行」才成立。
    ("bad-blocked-layer-no-longer-waives", "must_fail",
     good_assault(deliverable="build/NOPE.exe", extra_layers=BLOCKED_LAYER_OK, fstate="已分析"),
     False, ["assault.deliverable_missing"], 1,
     "整案级 blocked 行（layer/routes）不再豁免缺失的 deliverable —— 后门已关"),

    ("bad-blocked-with-completed-function", "must_fail",
     good_assault(deliverable="build/NOPE.exe", fstate="对照一致", fevidence="diff/F-001.md"),
     False, ["assault.deliverable_missing"], 1,
     "有完成态功能行 + deliverable 不在盘 → 必须 error（连受限豁免也不放行）"),

    ("good-deliverable-missing-with-limited-functions", "must_pass",
     good_assault(deliverable="build/NOPE.exe", fstate="受限",
                  fevidence="E-002", fnote="原因: 云端不可达; 影响: F-001; 替代: 本地 mock",
                  diff_rows=""),
     False, [], 0,
     "功能行 受限 且写明原因/影响/替代、无完成态行 → 完成形态成立（合法受限）"),

    ("bad-limited-missing-reasons", "must_fail",
     good_assault(deliverable="build/NOPE.exe", fstate="受限",
                  fevidence="E-002", fnote="受阻", diff_rows=""),
     False, ["assault.deliverable_missing"], 1,
     "功能行 受限 但备注没写原因/影响/替代 → 不构成完成形态"),

    # ---------- 边界：证据文字提到 blocked 但状态列非 blocked → 不触发（收窄后的误报防护） ----------
    ("good-blocked-word-in-evidence-only", "must_pass",
     good_assault(extra_layers="| L4 | 业务层 | 进行中 | E-002 (upstream mentions blocked, layer itself active) |"),
     True, [], 0, "状态列非 blocked 时，证据文字出现 blocked 不触发 blocked_reason_missing"),

    # ---------- 迁移窗口/边界：完成态行的 diff 行 verdict 为英文一致 ----------
    ("good-english-verdict", "must_pass",
     good_assault(diff_rows="| F-001 | --mode a | 2 | 2 | match | ok |"), True,
     [], 0, "verdict 用 match 也认（既有判据口径）"),

    # ---------- 必须放行：无 assault.md 的老 case（回归底线） ----------
    ("plain-case-no-assault", "plain",
     None, True, [], 0, "无 assault.md：不出现 assault.* 与 assault 键，exit 0"),
]


def run_case(name, kind, assault_text, make_deliverable, expect_codes, expect_exit, note):
    with tempfile.TemporaryDirectory(prefix="assault-negctl-") as scratch:
        root = os.path.join(scratch, "case")
        write_case(root, assault_text=assault_text, make_deliverable=make_deliverable)
        exit_code, payload = run_review(root)

        problems = []
        if payload is None:
            problems.append("CLI produced no parseable JSON (exit %s)" % exit_code)
        else:
            seen = codes(payload)
            if kind != "plain" and not payload.get("assault"):
                problems.append("payload has no 'assault' key although assault.md exists (audit never ran)")
            if kind == "plain" and "assault" in payload:
                problems.append("plain case grew an 'assault' key (output changed for non-assault cases)")
            for expected in expect_codes:
                if expected not in seen:
                    problems.append("expected code missing: %s (seen: %s)" % (expected, ",".join(seen) or "(none)"))
            if kind == "must_pass":
                assault_errors = [item["code"] for item in payload.get("issues", [])
                                  if item["code"].startswith("assault.") and item["level"] == "error"]
                if assault_errors:
                    problems.append("good fixture reported assault errors: %s" % ",".join(assault_errors))
            if kind == "plain":
                unexpected = [code for code in seen if code.startswith("assault.")]
                if unexpected:
                    problems.append("plain case reported assault issues: %s" % ",".join(unexpected))
        if exit_code != expect_exit:
            problems.append("exit code %s, expected %s" % (exit_code, expect_exit))
        return problems


def main():
    failures = 0
    total = 0
    for name, kind, assault_text, make_deliverable, expect_codes, expect_exit, note in CASES:
        total += 1
        problems = run_case(name, kind, assault_text, make_deliverable, expect_codes, expect_exit, note)
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
