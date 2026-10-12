import hashlib
import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "review_case.py"
SPEC = importlib.util.spec_from_file_location("review_case", SCRIPT_PATH)
REVIEW_CASE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REVIEW_CASE)

class ReviewCaseTests(unittest.TestCase):
    def write_case(self, root, include_report=True):
        evidence_dir = root / "evidence"
        report_dir = root / "report"
        evidence_dir.mkdir(parents=True)
        if include_report:
            report_dir.mkdir(parents=True)

        artifact = evidence_dir / "sample.bin"
        artifact.write_bytes(b"reverse-skill case review fixture")
        digest = hashlib.sha256(artifact.read_bytes()).hexdigest()

        (root / "scope.md").write_text(
            """# Case Scope

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
""",
            encoding="utf-8",
        )
        (root / "workitems.md").write_text(
            """# Work Items

| ID | title | role | targets | surface | status | evidence | notes |
|----|-------|------|---------|---------|--------|----------|-------|
| WI-001 | Recover sample behavior | cre | sample.bin | binary | done | E-001 | |
""",
            encoding="utf-8",
        )
        (root / "timeline.md").write_text(
            """# Timeline (append-only)

## 2026-08-02T00:00:00Z | cre | static
- action: inspect local sample
- evidence_ids: [E-001]
""",
            encoding="utf-8",
        )
        (evidence_dir / "E-001.md").write_text(
            """### E-001
- title: Sample hash
- severity: info
- status: observed
- content_hash: sha256:%s
- artifact_path: evidence/sample.bin
- linked_workitem: WI-001
- repro_command: sha256sum evidence/sample.bin
- raw_excerpt: |
    fixture
""" % digest,
            encoding="utf-8",
        )
        if include_report:
            (report_dir / "analysis.md").write_text(
                """### F-001
- title: Sample behavior recovered
- severity: info
- category: reverse_algo
- status: validated
- evidence_ids: [E-001]
- location: sample.bin:0x10
- impact: n/a
- confidence: high
- repro_steps: |
    1. Run the fixture command.
- remediation: n/a

### P-001
- title: Static recovery path
- path_type: callflow
- start: sample.bin
- goal: recovered behavior
- steps: |
    1. Hash the sample with E-001.
- residual_risks: n/a
""",
                encoding="utf-8",
            )

    def test_valid_case_passes_with_hash_verification(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_case(root)
            result = REVIEW_CASE.review_case(root, verify_hashes=True)
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["summary"]["evidence"], 1)
            self.assertEqual(result["summary"]["findings"], 1)
            self.assertEqual(result["summary"]["paths"], 1)

    def test_unknown_report_evidence_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_case(root)
            report = root / "report" / "analysis.md"
            report.write_text(report.read_text(encoding="utf-8").replace("E-001", "E-999"), encoding="utf-8")
            result = REVIEW_CASE.review_case(root)
            self.assertEqual(result["status"], "FAIL")
            self.assertTrue(any(item["code"] == "reference.unknown_evidence" for item in result["issues"]))

    def test_hash_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_case(root)
            (root / "evidence" / "sample.bin").write_bytes(b"changed fixture")
            result = REVIEW_CASE.review_case(root, verify_hashes=True)
            self.assertEqual(result["status"], "FAIL")
            self.assertTrue(any(item["code"] == "artifact.hash_mismatch" for item in result["issues"]))

    def test_markdown_output_contains_traceability_table(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_case(root)
            result = REVIEW_CASE.review_case(root)
            output = REVIEW_CASE.render_markdown(result)
            self.assertIn("## Traceability", output)
            self.assertIn("| E-001 | 1 | 1 | 2 |", output)

    def test_documented_offline_evidence_does_not_require_command(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_case(root)
            (root / "evidence" / "E-002.md").write_text(
                """### E-002
- title: Offline observation
- severity: info
- status: observed
- content_hash: n/a
- repro_command: n/a
- notes: offline-only observation
""",
                encoding="utf-8",
            )
            result = REVIEW_CASE.review_case(root)
            self.assertFalse(any(item["code"] == "evidence.repro_missing" for item in result["issues"]))

    def test_strict_mode_fails_when_report_is_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_case(root, include_report=False)
            result = REVIEW_CASE.review_case(root, strict=True)
            self.assertEqual(result["status"], "FAIL")
            self.assertTrue(any(item["code"] == "report.missing" for item in result["issues"]))

    def test_completed_workitem_status_matches_current_case_convention(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_case(root)
            workitems = root / "workitems.md"
            workitems.write_text(
                workitems.read_text(encoding="utf-8").replace("| done |", "| completed |"),
                encoding="utf-8",
            )
            result = REVIEW_CASE.review_case(root)
            self.assertFalse(any(item["code"] == "workitem.status" for item in result["issues"]))

    def test_windows_drive_path_is_parsed_as_scope_asset(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_case(root)
            scope = root / "scope.md"
            scope.write_text(
                scope.read_text(encoding="utf-8")
                .replace("  - sample.bin", r"  - D:\reverse-skill")
                .replace("- mode: offline", "- mode: lab_only"),
                encoding="utf-8",
            )
            result = REVIEW_CASE.review_case(root)
            self.assertEqual(result["scope"]["assets"], [r"D:\reverse-skill"])
            self.assertFalse(any(item["code"] == "scope.assets_missing" for item in result["issues"]))

    # ------------------------------------------------------------------
    # Rebuild delivery audit (rebuild.md present) — three bad fixtures.
    # A case without rebuild.md must not grow any rebuild.* issue, which the
    # existing tests above already pin down.
    # ------------------------------------------------------------------

    REBUILD_COVERAGE = """
## Coverage
- [x] 功能清单全覆盖 (every functions row has an acceptance row)
- [x] 关键功能状态 (critical functions carry a state + evidence)
- [x] 已知差异已记录 (known deviations recorded)
"""

    # 与 diff-runner 草稿同形的记录：完成态行引用的记录必须带这两段原始 stdout，
    # 1d 判据（字节比对 / 可复现性）读的就是它们。缺这两段只记迁移窗口 warning。
    REBUILD_DIFF_RECORD = """<!-- diff-runner draft — 供人工确认后回填 rebuild.md 的 diff_baseline 表 -->
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

    def write_rebuild_case(self, root, acceptance_state="对照一致", diff_row=True,
                           coverage=None, evidence_cell="diff/F-001.md", diff_record=None):
        self.write_case(root)
        (root / "diff").mkdir()
        (root / "diff" / "F-001.md").write_text(
            diff_record if diff_record is not None else self.REBUILD_DIFF_RECORD,
            encoding="utf-8")
        if coverage is None:
            coverage = self.REBUILD_COVERAGE
        workitems = root / "workitems.md"
        workitems.write_text(workitems.read_text(encoding="utf-8") + coverage, encoding="utf-8")
        diff_block = ""
        if diff_row:
            diff_block = """
## diff_baseline

- baseline_dir: `baseline/`
- diff_dir: `diff/`

| F-ID | 输入条件 | 原程序结果 | 新实现结果 | 是否一致 | 说明 |
|------|----------|------------|------------|----------|------|
| F-001 | --mode a | 2 | 2 | 一致 | ok |
"""
        (root / "rebuild.md").write_text(
            """# Rebuild

## target

- deliverable: `rebuilt-sample`
- form: script

## functions

| ID | 名称 | 入口 | 预期输出 | 验收条件 | 路线 |
|----|------|------|----------|----------|------|
| F-001 | demo | --mode a | 2 | same output | rewrite |

## acceptance

| ID | 状态 | 证据 (E-xxx / diff 记录) | 备注 |
|----|------|--------------------------|------|
| F-001 | %s | %s | |

%s

## out_of_delivery

| 项 | 理由 |
|----|------|
| GUI | out of scope |
""" % (acceptance_state, evidence_cell, diff_block),
            encoding="utf-8",
        )

    def test_rebuild_case_passes_with_full_table(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_rebuild_case(root)
            result = REVIEW_CASE.review_case(root)
            rebuild_errors = [item for item in result["issues"] if item["code"].startswith("rebuild.") and item["level"] == "error"]
            self.assertEqual(rebuild_errors, [])
            self.assertIsNotNone(result.get("rebuild"))
            self.assertEqual(result["rebuild"]["functions"]["F-001"]["state"], "verified")

    def test_rebuild_state_exceeding_evidence_fails(self):
        """坏 fixture 1：标「已测试」却没有对照 Evidence（证据列空）。"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_rebuild_case(root, acceptance_state="已测试", evidence_cell="")
            result = REVIEW_CASE.review_case(root)
            self.assertEqual(result["status"], "FAIL")
            self.assertTrue(any(item["code"] == "rebuild.state_exceeds_evidence" for item in result["issues"]))

    def test_rebuild_missing_diff_row_fails(self):
        """坏 fixture 2：对照表缺行 —— 已测试但没有 diff_baseline 行。"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_rebuild_case(root, diff_row=False)
            result = REVIEW_CASE.review_case(root)
            self.assertEqual(result["status"], "FAIL")
            self.assertTrue(any(item["code"] == "rebuild.diff_row_missing" for item in result["issues"]))

    def test_rebuild_missing_coverage_item_fails(self):
        """坏 fixture 3：Coverage 缺项 —— 三项复刻项缺一。"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_rebuild_case(
                root,
                coverage="""
## Coverage
- [x] 功能清单全覆盖
- [x] Known deviations recorded
""",
            )
            result = REVIEW_CASE.review_case(root)
            self.assertEqual(result["status"], "FAIL")
            self.assertTrue(any(item["code"] == "rebuild.coverage_missing" for item in result["issues"]))

    def test_rebuild_limited_row_needs_reason(self):
        """受限行必须写明原因/影响/替代方案。"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_rebuild_case(root)
            rebuild = (root / "rebuild.md").read_text(encoding="utf-8")
            rebuild = rebuild.replace("| F-001 | 对照一致 | diff/F-001.md | |",
                                      "| F-001 | 受限 | diff/F-001.md | |")
            (root / "rebuild.md").write_text(rebuild, encoding="utf-8")
            result = REVIEW_CASE.review_case(root)
            self.assertEqual(result["status"], "FAIL")
            self.assertTrue(any(item["code"] == "rebuild.limited_note_missing" for item in result["issues"]))

    def test_rebuild_diff_bytes_mismatch_fails(self):
        """表格自称一致，但被引用记录里两段 stdout 真差一字节 → 必须报。

        这是「验自称不验内容」的假绿形状：verdict=一致、文件在、hash 全对。
        """
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            forged = self.REBUILD_DIFF_RECORD.replace(
                "--- rebuilt stdout ---\n2", "--- rebuilt stdout ---\n3")
            self.write_rebuild_case(root, diff_record=forged)
            result = REVIEW_CASE.review_case(root)
            self.assertEqual(result["status"], "FAIL")
            self.assertTrue(any(item["code"] == "rebuild.diff_bytes_mismatch" for item in result["issues"]))

    def test_rebuild_diff_unreproducible_fails(self):
        """记录显示命令没跑起来（exit=ERROR）→ 不可复现的记录不支撑完成态。"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            broken = self.REBUILD_DIFF_RECORD.replace(
                "- rebuilt: exit=0 seconds=0.1",
                "- rebuilt: exit=ERROR seconds=0 error=shell not found")
            self.write_rebuild_case(root, diff_record=broken)
            result = REVIEW_CASE.review_case(root)
            self.assertEqual(result["status"], "FAIL")
            self.assertTrue(any(item["code"] == "rebuild.diff_unreproducible" for item in result["issues"]))

    def test_rebuild_old_format_record_warns_only(self):
        """老格式记录（缺两段原始 stdout）→ 迁移窗口 warning，不硬红。"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_rebuild_case(root, diff_record="input=1 | original=2 | rebuilt=2 | same | note\n")
            result = REVIEW_CASE.review_case(root)
            rebuild_errors = [item for item in result["issues"]
                              if item["code"].startswith("rebuild.") and item["level"] == "error"]
            self.assertEqual(rebuild_errors, [])
            self.assertTrue(any(item["code"] == "rebuild.diff_unparsed" for item in result["issues"]))

    def test_rebuild_absent_case_has_no_rebuild_key(self):
        """无 rebuild.md 时不出现 rebuild 键，输出与改前一致。"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_case(root)
            result = REVIEW_CASE.review_case(root)
            self.assertNotIn("rebuild", result)
            self.assertFalse(any(item["code"].startswith("rebuild.") for item in result["issues"]))
            self.assertNotIn("## Rebuild delivery", REVIEW_CASE.render_markdown(result))

    # ------------------------------------------------------------------
    # Update follow-up audit (update.md present) — four checks.
    # A case without update.md must not grow any update.* issue, which
    # test_rebuild_absent_case_has_no_rebuild_key pins down above.
    # ------------------------------------------------------------------

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

    def write_update_case(self, root, three_lines_we="我们改过 F-001（rewrite）",
                          delta_rows=None, verification_rows=None,
                          fingerprints=None, with_record=True,
                          record_text=None):
        self.write_rebuild_case(root)
        (root / "diff-update").mkdir()
        if with_record:
            (root / "diff-update" / "F-001.md").write_text(
                record_text if record_text is not None else self.UPDATE_RECORD,
                encoding="utf-8")
        if fingerprints is None:
            fingerprints = {
                "old_upstream": "samples/old.exe | 1.0 | sha256:" + "a" * 64,
                "new_upstream": "samples/new.exe | 1.1 | sha256:" + "b" * 64,
                "our_old_build": "build/out.py | sha256:" + "c" * 64,
            }
        if delta_rows is None:
            delta_rows = "| F-001 | 未变 | 仍一致 | keep | diff/F-001.md |"
        if verification_rows is None:
            verification_rows = "| F-001 | --mode a | 2 | 2 | 一致 | ok |"
        (root / "update.md").write_text(
            """# Update

## target

- case: case
- old_upstream: %s
- new_upstream: %s
- our_old_build: %s
- goal: `新版等价复刻`

## three_lines

- we_changed: %s
- upstream_new: 上游把 F-001 的行为保持不变
- portable: F-001 可 keep，无新能力

## function_delta

| F-ID | 上游新版状态 | 我们的复刻是否仍有效 | 动作 | 依据 |
|------|--------------|----------------------|------|------|
%s

## patch_shift

| F-ID | 旧特征码 | 新版命中位置 (VA/offset) | 位移重算 | 结果 |
|------|----------|--------------------------|----------|------|

## verification

| F-ID | 输入 | 新版原程序结果 | 新复刻结果 | 是否一致 | 说明 |
|------|------|----------------|------------|----------|------|
%s

## out_of_update

| 项 | 理由 |
|----|------|
| | |
""" % (fingerprints["old_upstream"], fingerprints["new_upstream"],
       fingerprints["our_old_build"], three_lines_we, delta_rows, verification_rows),
            encoding="utf-8",
        )

    def test_update_case_passes_with_full_table(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_update_case(root)
            result = REVIEW_CASE.review_case(root)
            update_errors = [item for item in result["issues"]
                             if item["code"].startswith("update.") and item["level"] == "error"]
            self.assertEqual(update_errors, [])
            self.assertIsNotNone(result.get("update"))
            self.assertIn("## Update follow-up", REVIEW_CASE.render_markdown(result))

    def test_update_missing_three_line_fails(self):
        """坏 fixture：三句对照缺一句 → 报错（防没写三句就动手）。"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_update_case(root, three_lines_we="")
            result = REVIEW_CASE.review_case(root)
            self.assertEqual(result["status"], "FAIL")
            self.assertTrue(any(item["code"] == "update.three_lines_missing" for item in result["issues"]))

    def test_update_placeholder_three_line_still_counts_missing(self):
        """未填的模板占位（反引号包尖括号）不算「写了」→ 仍报缺。"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_update_case(root, three_lines_we="`<我们改过哪些功能 —— 上一版复刻的功能面与路线（patch/recover/rewrite/keep）>`")
            result = REVIEW_CASE.review_case(root)
            self.assertEqual(result["status"], "FAIL")
            self.assertTrue(any(item["code"] == "update.three_lines_missing" for item in result["issues"]))

    def test_update_delta_missing_fid_fails(self):
        """坏 fixture：function_delta 漏了 rebuild.md 里的 F-ID。"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_update_case(root, delta_rows="")
            result = REVIEW_CASE.review_case(root)
            self.assertEqual(result["status"], "FAIL")
            self.assertTrue(any(item["code"] == "update.delta_missing" for item in result["issues"]))

    def test_update_delta_unknown_fid_fails(self):
        """坏 fixture：function_delta 出现 rebuild.md 之外的 F-ID 且动作非 new。"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_update_case(
                root,
                delta_rows="| F-001 | 未变 | 仍一致 | keep | diff/F-001.md |\n"
                           "| F-002 | 新增替代 | 需重测 | keep | x |")
            result = REVIEW_CASE.review_case(root)
            self.assertEqual(result["status"], "FAIL")
            self.assertTrue(any(item["code"] == "update.delta_unknown" for item in result["issues"]))

    def test_update_delta_new_fid_allowed(self):
        """动作 new 允许引入 rebuild.md 之外的新 F-ID（对应记录也在位即可）。"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_update_case(
                root,
                delta_rows="| F-001 | 未变 | 仍一致 | keep | diff/F-001.md |\n"
                           "| F-002 | 新增替代 | （新能力） | new | E-001 |",
                verification_rows="| F-001 | --mode a | 2 | 2 | 一致 | ok |\n"
                                  "| F-002 | --mode b | 3 | 3 | 一致 | new |")
            (root / "diff-update" / "F-002.md").write_text(
                self.UPDATE_RECORD.replace("F-001", "F-002"), encoding="utf-8")
            result = REVIEW_CASE.review_case(root)
            update_errors = [item for item in result["issues"]
                             if item["code"].startswith("update.") and item["level"] == "error"]
            self.assertEqual(update_errors, [])

    def test_update_verification_missing_record_fails(self):
        """坏 fixture：verification 行标一致但 diff-update 记录不存在。"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_update_case(root, with_record=False)
            result = REVIEW_CASE.review_case(root)
            self.assertEqual(result["status"], "FAIL")
            self.assertTrue(any(item["code"] == "update.verification_record_missing" for item in result["issues"]))

    def test_update_verification_bytes_mismatch_fails(self):
        """verification 标一致，但记录里两段 stdout 逐字节不同 → 必须报。"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            forged = self.UPDATE_RECORD.replace("--- rebuilt stdout ---\n2", "--- rebuilt stdout ---\n3")
            self.write_update_case(root, record_text=forged)
            result = REVIEW_CASE.review_case(root)
            self.assertEqual(result["status"], "FAIL")
            self.assertTrue(any(item["code"] == "update.diff_bytes_mismatch" for item in result["issues"]))

    def test_update_fingerprint_hashless_fails(self):
        """坏 fixture：三处版本指纹有一处没带 64-hex SHA256。"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_update_case(root, fingerprints={
                "old_upstream": "samples/old.exe | 1.0",
                "new_upstream": "samples/new.exe | 1.1 | sha256:" + "b" * 64,
                "our_old_build": "build/out.py | sha256:" + "c" * 64,
            })
            result = REVIEW_CASE.review_case(root)
            self.assertEqual(result["status"], "FAIL")
            self.assertTrue(any(item["code"] == "update.fingerprint_hashless" for item in result["issues"]))

    def test_update_verification_missing_column_fails(self):
        """坏 fixture：verification 五列缺一列。"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_update_case(root, verification_rows="| F-001 | --mode a | 2 |  | 一致 |  |")
            result = REVIEW_CASE.review_case(root)
            self.assertEqual(result["status"], "FAIL")
            self.assertTrue(any(item["code"] == "update.verification_incomplete" for item in result["issues"]))

    def test_update_absent_case_has_no_update_key(self):
        """无 update.md 时不出现 update 键，输出与改前一致。"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_rebuild_case(root)
            result = REVIEW_CASE.review_case(root)
            self.assertNotIn("update", result)
            self.assertFalse(any(item["code"].startswith("update.") for item in result["issues"]))
            self.assertNotIn("## Update follow-up", REVIEW_CASE.render_markdown(result))

    # --- Assault rolling-report audit (assault.md present) — four checks + bad fixtures ---
    ASSAULT_TABLE = """# Assault 滚动报告

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
| GUI | 不做 |
"""

    def write_assault_case(self, root, state="EXECUTE", deliverable="build/rebuilt.exe",
                           fstate="对照一致", fevidence="diff/F-001.md", fnote="",
                           diff_rows="| F-001 | --mode a | 2 | 2 | 一致 | ok |",
                           uquestion="云端行为", uimpact="F-001", unext="抓包", ublock="no",
                           extra_layers="| L4 | 业务层 | 进行中 | E-002 |",
                           make_deliverable=True):
        self.write_case(root)
        build_dir = root / "build"
        build_dir.mkdir()
        if make_deliverable:
            (build_dir / "rebuilt.exe").write_bytes(b"MZ fake rebuilt")
        diff_dir = root / "diff"
        diff_dir.mkdir()
        (diff_dir / "F-001.md").write_text("draft", encoding="utf-8")
        (root / "assault.md").write_text(
            self.ASSAULT_TABLE.format(
                state=state, deliverable=deliverable, extra_layers=extra_layers,
                fstate=fstate, fevidence=fevidence, fnote=fnote,
                uquestion=uquestion, uimpact=uimpact, unext=unext, ublock=ublock,
                diff_rows=diff_rows),
            encoding="utf-8",
        )

    def test_assault_case_passes_with_full_table(self):
        """好 fixture：状态行 / layers / functions / unknowns / deliverable 全齐 → 0 assault 报错。"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_assault_case(root)
            result = REVIEW_CASE.review_case(root)
            assault_errors = [item for item in result["issues"]
                              if item["code"].startswith("assault.") and item["level"] == "error"]
            self.assertEqual(assault_errors, [])
            self.assertIsNotNone(result.get("assault"))
            self.assertEqual(result["assault"]["state"], "EXECUTE")
            self.assertTrue(result["assault"]["deliverable_present"])

    def test_assault_state_line_missing_fails(self):
        """坏 fixture 1：状态行缺 —— current_state 空。"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_assault_case(root)
            assault = (root / "assault.md").read_text(encoding="utf-8")
            (root / "assault.md").write_text(
                assault.replace("- current_state: `EXECUTE`", "- current_state:"), encoding="utf-8")
            result = REVIEW_CASE.review_case(root)
            self.assertEqual(result["status"], "FAIL")
            self.assertTrue(any(item["code"] == "assault.state_line_missing" for item in result["issues"]))

    def test_assault_state_line_invalid_fails(self):
        """坏 fixture 1b：current_state 不在四状态内。"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_assault_case(root, state="DONE")
            result = REVIEW_CASE.review_case(root)
            self.assertEqual(result["status"], "FAIL")
            self.assertTrue(any(item["code"] == "assault.state_line_invalid" for item in result["issues"]))

    def test_assault_layer_without_evidence_fails(self):
        """坏 fixture 2：layers 行缺证据。"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_assault_case(root, extra_layers="| L4 | 业务层 | 进行中 |  |")
            result = REVIEW_CASE.review_case(root)
            self.assertEqual(result["status"], "FAIL")
            self.assertTrue(any(item["code"] == "assault.layer_evidence_missing" for item in result["issues"]))

    def test_assault_blocked_layer_without_reasons_fails(self):
        """坏 fixture 2b：blocked 行没有 原因/影响/替代。"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_assault_case(root, extra_layers="| L4 | 业务层 | blocked | E-002 |")
            result = REVIEW_CASE.review_case(root)
            self.assertEqual(result["status"], "FAIL")
            self.assertTrue(any(item["code"] == "assault.blocked_reason_missing" for item in result["issues"]))

    def test_assault_function_state_exceeds_evidence_fails(self):
        """坏 fixture 3：标「已测试」却没有证据列。"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_assault_case(root, fstate="已测试", fevidence="")
            result = REVIEW_CASE.review_case(root)
            self.assertEqual(result["status"], "FAIL")
            self.assertTrue(any(item["code"] == "assault.state_exceeds_evidence" for item in result["issues"]))

    def test_assault_function_missing_diff_row_fails(self):
        """坏 fixture 3b：完成态没有 diff_baseline 行。"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_assault_case(root, diff_rows="")
            result = REVIEW_CASE.review_case(root)
            self.assertEqual(result["status"], "FAIL")
            self.assertTrue(any(item["code"] == "assault.diff_row_missing" for item in result["issues"]))

    def test_assault_diff_verdict_unproven_fails(self):
        """坏 fixture 3c：完成态但对照行 verdict 未断言一致。"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_assault_case(root, fstate="已测试", fevidence="E-003",
                                    diff_rows="| F-001 | --mode a | 2 | 2 | 待判 | 未对照 |")
            result = REVIEW_CASE.review_case(root)
            self.assertEqual(result["status"], "FAIL")
            self.assertTrue(any(item["code"] == "assault.diff_verdict_unproven" for item in result["issues"]))

    def test_assault_unknown_missing_columns_fails(self):
        """坏 fixture 4：unknowns 缺「下一步 / 是否阻塞」。"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_assault_case(root, unext="", ublock="")
            result = REVIEW_CASE.review_case(root)
            self.assertEqual(result["status"], "FAIL")
            self.assertTrue(any(item["code"] == "assault.unknown_field_missing" for item in result["issues"]))

    def test_assault_deliverable_missing_without_blocked_fails(self):
        """坏 fixture 5：deliverable 指向不存在的文件且未记录 blocked 形态。"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_assault_case(root, deliverable="build/NOPE.exe", make_deliverable=False)
            result = REVIEW_CASE.review_case(root)
            self.assertEqual(result["status"], "FAIL")
            self.assertTrue(any(item["code"] == "assault.deliverable_missing" for item in result["issues"]))

    def test_assault_deliverable_missing_with_blocked_form_fails(self):
        """§2.2 后门已关：整案级 blocked 行不再豁免缺失的 deliverable。

        旧契约里 routes/layers 行写 blocked + 原因/影响/替代 就能让「成品没出来」
        变成可过审状态 —— 那是字面意义的「打不穿可过审」后门。新契约下同一 fixture
        必须 FAIL：完成态功能行在场、deliverable 不在盘，任何 blocked 措辞都不放行。
        """
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_assault_case(
                root, deliverable="build/NOPE.exe", make_deliverable=False,
                extra_layers="| L4 | 业务层 | blocked | E-002 | 原因: 云端样本不可得; 影响: F-001 无法对照; 替代: 本地 mock |")
            result = REVIEW_CASE.review_case(root)
            self.assertEqual(result["status"], "FAIL")
            self.assertTrue(any(item["code"] == "assault.deliverable_missing" for item in result["issues"]))

    def test_assault_limited_function_with_reasons_passes(self):
        """合法的完成形态：功能行 受限 且写明原因/影响/替代、无完成态行 → 放行。"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_assault_case(
                root, deliverable="build/NOPE.exe", make_deliverable=False,
                fstate="受限", fevidence="E-002", fnote="原因: 云端不可达; 影响: F-001; 替代: 本地 mock",
                diff_rows="")
            result = REVIEW_CASE.review_case(root)
            deliverable_errors = [item for item in result["issues"] if item["code"] == "assault.deliverable_missing"]
            self.assertEqual(deliverable_errors, [])

    def test_assault_absent_case_has_no_assault_key(self):
        """无 assault.md 时不出现 assault 键，输出与改前一致。"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_rebuild_case(root)
            result = REVIEW_CASE.review_case(root)
            self.assertNotIn("assault", result)
            self.assertFalse(any(item["code"].startswith("assault.") for item in result["issues"]))
            self.assertNotIn("## Assault report", REVIEW_CASE.render_markdown(result))

if __name__ == "__main__":
    unittest.main()
