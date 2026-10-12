# -*- coding: utf-8 -*-
"""review_case.py update 更新审计的负控：证明它真的抓得到坏状态，也真的放行好状态。

★ 为什么必须存在
  与 test-rebuild-audit-negctl.py 同因：门禁「报绿但其实没检查」是本仓最危险的
  失败模式。update 审计挂进 review_case.py 之后，最坏的情况是：
    · update.md 存在，但审计早退（分支写错）→ 坏 case 也报 PASS；
    · 审计跑了，但字段读错（列索引偏一位）→ 永远读不到内容，永远不报错。
  汇总数字上「全部干净」和「什么都没看」长得一模一样。每个检查点都要有一份
  能证明「它确实拦了」的对照。

★ 与单测的分工
  tests/test_review_case.py 直接调 review_case()（同进程，快）；
  本负控**走子进程 CLI**（python review_case.py <case> --format json），验证
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
REVIEW = os.path.abspath(os.path.join(HERE, "..", "case-review", "scripts", "review_case.py"))
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
| WI-001 | Update demo | impl | sample.bin | binary | done | | |

## Coverage
- [x] Recon/analysis complete for in_scope assets
- [x] Critical/High candidates triaged (or N/A for pure RE)
- [x] Validated findings have Evidence (E-*)
- [x] Path documented (attack/call/solve)
- [x] Timeline continuous across major phases
- [x] Report via docs-generator
- [x] field-journal anonymized
- [x] 功能清单全覆盖 (every functions row has an acceptance row)
- [x] 关键功能状态 (critical functions carry a state + evidence)
- [x] 已知差异已记录 (known deviations recorded)
"""

BASE_TIMELINE = """# Timeline (append-only)

## 2026-10-13T00:00:00Z | impl | update
- action: update follow-up demo
- decision_delta: [F-001 kept]
- carry_forward_refs: [rebuild.md, update.md]
"""

REBUILD_MD = """# Rebuild

## target

- deliverable: `rebuilt-demo`
- form: script

## functions

| ID | 名称 | 入口 | 预期输出 | 验收条件 | 路线 |
|----|------|------|----------|----------|------|
| F-001 | demo | --mode a | 2 | same output | rewrite |

## acceptance

| ID | 状态 | 证据 (E-xxx / diff 记录) | 备注 |
|----|------|--------------------------|------|
| F-001 | 对照一致 | diff/F-001.md | |

## diff_baseline

- baseline_dir: `baseline/`
- diff_dir: `diff/`

| F-ID | 输入条件 | 原程序结果 | 新实现结果 | 是否一致 | 说明 |
|------|----------|------------|------------|----------|------|
| F-001 | --mode a | 2 | 2 | 一致 | ok |

## out_of_delivery

| 项 | 理由 |
|----|------|
| GUI | out of scope |
"""

GOOD_DIFF_RECORD = """<!-- diff-runner draft — 供人工确认后回填 rebuild.md 的 diff_baseline 表 -->
# Diff draft: F-001

- case: case
- generated: 2026-01-01T00:00:00
- baseline_command: `echo 2`
- rebuilt_command: `echo 2`
- judged_by: human

## Raw records

### F-001 · case 1 · input: --mode a

- baseline: exit=0 seconds=0.1
- rebuilt: exit=0 seconds=0.1

```text
--- baseline stdout ---
2
--- rebuilt stdout ---
2
```
"""

UPDATE_RECORD = """<!-- diff-runner draft — 供人工确认后回填 update.md 的 verification 表 -->
# Diff draft (update): F-001

- case: case
- generated: 2026-01-01T00:00:00
- baseline_command: `echo 2`
- rebuilt_command: `echo 2`
- judged_by: human

## Raw records

### F-001 · case 1 · input: --mode a

- baseline: exit=0 seconds=0.1
- rebuilt: exit=0 seconds=0.1

```text
--- baseline stdout ---
2
--- rebuilt stdout ---
2
```
"""

BAD_BYTES_UPDATE_RECORD = UPDATE_RECORD.replace("--- rebuilt stdout ---\n2", "--- rebuilt stdout ---\n3")

UNREPRODUCIBLE_UPDATE_RECORD = UPDATE_RECORD.replace(
    "- rebuilt: exit=0 seconds=0.1", "- rebuilt: exit=ERROR seconds=0 error=shell not found")

HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64

UPDATE_MD_TEMPLATE = """# Update

## target

- case: case
- old_upstream: {old}
- new_upstream: {new}
- our_old_build: {build}
- goal: `新版等价复刻`

## three_lines

- we_changed: {we}
- upstream_new: {up}
- portable: {portable}

## function_delta

| F-ID | 上游新版状态 | 我们的复刻是否仍有效 | 动作 | 依据 |
|------|--------------|----------------------|------|------|
{delta}

## patch_shift

| F-ID | 旧特征码 | 新版命中位置 (VA/offset) | 位移重算 | 结果 |
|------|----------|--------------------------|----------|------|

## verification

| F-ID | 输入 | 新版原程序结果 | 新复刻结果 | 是否一致 | 说明 |
|------|------|----------------|------------|----------|------|
{verification}

## out_of_update

| 项 | 理由 |
|----|------|
| | |
"""

GOOD_UPDATE = UPDATE_MD_TEMPLATE.format(
    old="samples/old.exe | 1.0 | sha256:" + HASH_A,
    new="samples/new.exe | 1.1 | sha256:" + HASH_B,
    build="build/out.py | sha256:" + HASH_C,
    we="我们改过 F-001（rewrite）",
    up="上游 F-001 行为不变",
    portable="F-001 可 keep；无新能力",
    delta="| F-001 | 未变 | 仍一致 | keep | diff/F-001.md |",
    verification="| F-001 | --mode a | 2 | 2 | 一致 | ok |",
)

# 三句对照缺一句（we_changed 空）
UPDATE_MISSING_THREE_LINE = UPDATE_MD_TEMPLATE.format(
    old="samples/old.exe | 1.0 | sha256:" + HASH_A,
    new="samples/new.exe | 1.1 | sha256:" + HASH_B,
    build="build/out.py | sha256:" + HASH_C,
    we="",
    up="上游 F-001 行为不变",
    portable="F-001 可 keep；无新能力",
    delta="| F-001 | 未变 | 仍一致 | keep | diff/F-001.md |",
    verification="| F-001 | --mode a | 2 | 2 | 一致 | ok |",
)

# 未填的模板占位不算「写了」
UPDATE_PLACEHOLDER_THREE_LINE = UPDATE_MD_TEMPLATE.format(
    old="samples/old.exe | 1.0 | sha256:" + HASH_A,
    new="samples/new.exe | 1.1 | sha256:" + HASH_B,
    build="build/out.py | sha256:" + HASH_C,
    we="`<我们改过哪些功能 —— 上一版复刻的功能面与路线（patch/recover/rewrite/keep）>`",
    up="上游 F-001 行为不变",
    portable="F-001 可 keep；无新能力",
    delta="| F-001 | 未变 | 仍一致 | keep | diff/F-001.md |",
    verification="| F-001 | --mode a | 2 | 2 | 一致 | ok |",
)

# function_delta 漏 F-ID（空表）
UPDATE_DELTA_MISSING_FID = UPDATE_MD_TEMPLATE.format(
    old="samples/old.exe | 1.0 | sha256:" + HASH_A,
    new="samples/new.exe | 1.1 | sha256:" + HASH_B,
    build="build/out.py | sha256:" + HASH_C,
    we="我们改过 F-001（rewrite）",
    up="上游 F-001 行为不变",
    portable="F-001 可 keep",
    delta="",
    verification="| F-001 | --mode a | 2 | 2 | 一致 | ok |",
)

# verification 标一致但记录文件不存在（with_update_record=False）
UPDATE_VERIFICATION_NO_RECORD = GOOD_UPDATE

# verification 行五列缺一列
UPDATE_VERIFICATION_INCOMPLETE = UPDATE_MD_TEMPLATE.format(
    old="samples/old.exe | 1.0 | sha256:" + HASH_A,
    new="samples/new.exe | 1.1 | sha256:" + HASH_B,
    build="build/out.py | sha256:" + HASH_C,
    we="我们改过 F-001（rewrite）",
    up="上游 F-001 行为不变",
    portable="F-001 可 keep",
    delta="| F-001 | 未变 | 仍一致 | keep | diff/F-001.md |",
    verification="| F-001 | --mode a | 2 |  | 一致 |  |",
)

# 三指纹缺一处 hash
UPDATE_HASHLESS_FINGERPRINT = UPDATE_MD_TEMPLATE.format(
    old="samples/old.exe | 1.0",
    new="samples/new.exe | 1.1 | sha256:" + HASH_B,
    build="build/out.py | sha256:" + HASH_C,
    we="我们改过 F-001（rewrite）",
    up="上游 F-001 行为不变",
    portable="F-001 可 keep",
    delta="| F-001 | 未变 | 仍一致 | keep | diff/F-001.md |",
    verification="| F-001 | --mode a | 2 | 2 | 一致 | ok |",
)

# function_delta 出现 rebuild.md 之外、动作又非 new 的 F-ID
UPDATE_UNKNOWN_FID = UPDATE_MD_TEMPLATE.format(
    old="samples/old.exe | 1.0 | sha256:" + HASH_A,
    new="samples/new.exe | 1.1 | sha256:" + HASH_B,
    build="build/out.py | sha256:" + HASH_C,
    we="我们改过 F-001（rewrite）",
    up="上游 F-001 行为不变",
    portable="F-001 可 keep",
    delta="| F-001 | 未变 | 仍一致 | keep | diff/F-001.md |\n| F-002 | 新增替代 | 需重测 | keep | x |",
    verification="| F-001 | --mode a | 2 | 2 | 一致 | ok |",
)

# 动作值非法
UPDATE_BAD_ACTION = UPDATE_MD_TEMPLATE.format(
    old="samples/old.exe | 1.0 | sha256:" + HASH_A,
    new="samples/new.exe | 1.1 | sha256:" + HASH_B,
    build="build/out.py | sha256:" + HASH_C,
    we="我们改过 F-001（rewrite）",
    up="上游 F-001 行为不变",
    portable="F-001 可 keep",
    delta="| F-001 | 未变 | 仍一致 | freeze | diff/F-001.md |",
    verification="| F-001 | --mode a | 2 | 2 | 一致 | ok |",
)


def write_case(root, update_text=None, with_update_record=True, update_record_text=None,
               with_rebuild=True, rebuild_text=None):
    evidence = os.path.join(root, "evidence")
    report = os.path.join(root, "report")
    diff = os.path.join(root, "diff")
    diff_update = os.path.join(root, "diff-update")
    os.makedirs(evidence)
    os.makedirs(report)
    os.makedirs(diff)
    os.makedirs(diff_update)
    with io.open(os.path.join(root, "scope.md"), "w", encoding="utf-8") as fh:
        fh.write(BASE_SCOPE)
    with io.open(os.path.join(root, "workitems.md"), "w", encoding="utf-8") as fh:
        fh.write(BASE_WORKITEMS)
    with io.open(os.path.join(root, "timeline.md"), "w", encoding="utf-8") as fh:
        fh.write(BASE_TIMELINE)
    with io.open(os.path.join(diff, "F-001.md"), "w", encoding="utf-8") as fh:
        fh.write(GOOD_DIFF_RECORD)
    if with_rebuild:
        with io.open(os.path.join(root, "rebuild.md"), "w", encoding="utf-8") as fh:
            fh.write(rebuild_text if rebuild_text is not None else REBUILD_MD)
    if with_update_record:
        with io.open(os.path.join(diff_update, "F-001.md"), "w", encoding="utf-8") as fh:
            fh.write(update_record_text if update_record_text is not None else UPDATE_RECORD)
    if update_text is not None:
        with io.open(os.path.join(root, "update.md"), "w", encoding="utf-8") as fh:
            fh.write(update_text)


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


# (用例名, kind, update_text, with_update_record, 期望 codes 必须出现, 期望 exit, 说明[, update_record_text])
#   kind: must_pass（0 update.* 报错，exit 0）/ must_fail（必须出现期望 code）/
#         must_warn（必须出现期望 warning code 且 0 error，exit 0）/ no_update（无 update.md）
CASES = [
    # ---------- 好 fixture：必须放行 ----------
    ("good-update-full-table", "must_pass",
     GOOD_UPDATE, True,
     [], 0, "完整 update.md + 记录在位 + 三指纹齐：0 报错，exit 0"),

    # ---------- 坏 fixture 1：三句对照缺一句 ----------
    ("bad-three-lines-missing", "must_fail",
     UPDATE_MISSING_THREE_LINE, True,
     ["update.three_lines_missing"], 1, "we_changed 空 → 三句缺一句，防没写三句就动手"),

    # ---------- 坏 fixture 1b：未填的模板占位不算「写了」 ----------
    ("bad-three-lines-placeholder", "must_fail",
     UPDATE_PLACEHOLDER_THREE_LINE, True,
     ["update.three_lines_missing"], 1, "three_lines 仍是模板占位（反引号尖括号）→ 按缺句处理"),

    # ---------- 坏 fixture 2：function_delta 漏 F-ID ----------
    ("bad-delta-missing-fid", "must_fail",
     UPDATE_DELTA_MISSING_FID, True,
     ["update.delta_missing"], 1, "rebuild.md 的 F-001 没有 function_delta 行 → 更新范围没定义"),

    # ---------- 坏 fixture 3：verification 标一致但记录文件不存在 ----------
    ("bad-verification-no-record", "must_fail",
     UPDATE_VERIFICATION_NO_RECORD, False,
     ["update.verification_record_missing"], 1, "标「对照一致」但 diff-update/F-001.md 不存在"),

    # ---------- 坏 fixture 3b：verification 五列缺一列 ----------
    ("bad-verification-incomplete", "must_fail",
     UPDATE_VERIFICATION_INCOMPLETE, True,
     ["update.verification_incomplete"], 1, "verification 行五列缺两列 → 未填齐"),

    # ---------- 坏 fixture 4：三 hash 缺一 ----------
    ("bad-fingerprint-hashless", "must_fail",
     UPDATE_HASHLESS_FINGERPRINT, True,
     ["update.fingerprint_hashless"], 1, "old_upstream 无 64-hex SHA256 → 指纹不全"),

    # ---------- 附加：未知 F-ID 且动作非 new ----------
    ("bad-delta-unknown-fid", "must_fail",
     UPDATE_UNKNOWN_FID, True,
     ["update.delta_unknown"], 1, "F-002 不在 rebuild.md 功能表且动作非 new"),

    # ---------- 附加：动作值非法 ----------
    ("bad-delta-action-invalid", "must_fail",
     UPDATE_BAD_ACTION, True,
     ["update.delta_action_invalid"], 1, "动作 freeze 不在 keep/retest/redo/new 内"),

    # ---------- 附加：表格自称一致、记录里两段 stdout 差一字节 ----------
    ("bad-update-bytes-mismatch", "must_fail",
     GOOD_UPDATE, True,
     ["update.diff_bytes_mismatch"], 1,
     "记录里两段 stdout 逐字节不同 → 必须报（与初逆同一把尺）",
     BAD_BYTES_UPDATE_RECORD),

    # ---------- 附加：记录里命令没跑起来 ----------
    ("bad-update-unreproducible", "must_fail",
     GOOD_UPDATE, True,
     ["update.diff_unreproducible"], 1,
     "记录显示 rebuilt 命令未执行（exit=ERROR）→ 不支撑「一致」",
     UNREPRODUCIBLE_UPDATE_RECORD),

    # ---------- 迁移窗口：记录缺原始块只记 warning ----------
    ("old-format-update-record-warns", "must_warn",
     GOOD_UPDATE, True,
     ["update.diff_unparsed"], 0,
     "update 记录缺两段原始 stdout → warning（迁移窗口）",
     "input=1 | original=2 | rebuilt=2 | same | note\n"),

    # ---------- 必须放行：无 update.md 的既有 case（回归底线） ----------
    ("no-update-md", "no_update",
     None, True,
     [], 0, "无 update.md：不出现 update.*，exit 0"),
]


def run_case(name, kind, update_text, with_update_record, expect_codes, expect_exit, note,
             update_record_text=None):
    with tempfile.TemporaryDirectory(prefix="update-negctl-") as scratch:
        root = os.path.join(scratch, "case")
        write_case(root, update_text=update_text, with_update_record=with_update_record,
                   update_record_text=update_record_text)
        exit_code, payload = run_review(root)

        problems = []
        if payload is None:
            problems.append("CLI produced no parseable JSON (exit %s)" % exit_code)
        if payload is not None:
            seen = codes(payload)
            if kind != "no_update" and not payload.get("update"):
                problems.append("payload has no 'update' key although update.md exists (audit never ran)")
            if kind == "no_update" and "update" in payload:
                problems.append("case without update.md grew an 'update' key (output changed)")
            for expected in expect_codes:
                if expected not in seen:
                    problems.append("expected code missing: %s (seen: %s)" % (expected, ",".join(seen) or "(none)"))
            if kind == "must_warn":
                errors = [item["code"] for item in payload.get("issues", []) if item["level"] == "error"]
                if errors:
                    problems.append("warning fixture reported errors: %s" % ",".join(errors))
            if kind in ("must_pass", "no_update") and not expect_codes:
                unexpected = [code for code in seen if code.startswith("update.")]
                if unexpected:
                    problems.append("good fixture reported update issues: %s" % ",".join(unexpected))
        if exit_code != expect_exit:
            problems.append("exit code %s, expected %s" % (exit_code, expect_exit))
        return problems


def main():
    failures = 0
    total = 0
    for entry in CASES:
        name, kind, update_text, with_update_record, expect_codes, expect_exit, note = entry[:7]
        update_record_text = entry[7] if len(entry) > 7 else None
        total += 1
        problems = run_case(name, kind, update_text, with_update_record,
                            expect_codes, expect_exit, note, update_record_text)
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
