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

if __name__ == "__main__":
    unittest.main()
