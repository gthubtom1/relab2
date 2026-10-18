---
name: case-review
description: case 包只读审查：scope 就绪度、Evidence 链可追溯、artifact SHA-256、rebuild/update 表核对。用于：交报告前审 case、证据链全不全、复核哈希。
---

# Evidence Graph Review

Use this skill when a reverse engineering, forensics, CTF, or authorized security case needs a defensible handoff. It audits the existing `work/<case>/` package without changing the case or touching a target.

## Scope

This skill covers:

- Scope metadata and target-activity readiness
- Evidence record structure and reproducibility fields
- References from work items and timeline entries to Evidence
- Structured Findings and Paths in report Markdown
- Optional SHA-256 verification for case-local artifacts
- A Markdown or JSON review result for a report handoff
- **Rebuild delivery audit** — when `work/<case>/rebuild.md` exists, the review
  additionally checks that every function row's state is backed by evidence, that
  every `diff_baseline` row keeps its five columns, that Coverage carries the
  three rebuild items (功能清单全覆盖 / 关键功能状态 / 已知差异已记录), and that a
  completed row's cited diff record really shows identical stdout bytes for both
  programs (the record is verified, not the table's claim).
  A case without `rebuild.md` produces exactly the same report as before.
- **Update follow-up audit** — when `work/<case>/update.md` exists, the review
  additionally checks the four update-stage facts: all three `three_lines` fields
  carry real content (template placeholders do not count), `function_delta`
  covers every F-ID in `rebuild.md` (only action=new may add a new F-ID), each
  `verification` row keeps its five columns and a row asserting 一致 has its
  `diff-update/` record on disk — held to the same byte-level scale as 初逆
  (raw stdout blocks compared byte for byte, plus reproducibility) — and the
  three version fingerprints each carry a 64-hex SHA256.
  A case without `update.md` produces exactly the same report as before.
- **Assault rolling-report audit** — when `work/<case>/assault.md` exists, the review
  additionally checks the four assault-stage facts (GOAL-PROMPT-ASSAULT 阶段4):
  the `## 0 状态行` is filled and `current_state` is one of
  SURVEY/ROUTE/EXECUTE/VERIFY; every `layers` row carries a status + evidence
  (a blocked row records 原因/影响/替代); every `functions` row carries route + state
  and no state outruns its evidence (a completed row needs its diff_baseline row
  whose verdict asserts 一致); every `unknowns` item keeps its 影响/下一步/是否阻塞
  columns; and the completion form holds — the `deliverable` product exists on disk,
  or the report records a blocked outcome with cause/impact/fallback.
  A case without `assault.md` produces exactly the same report as before.

It MUST NOT perform reconnaissance, exploitation, dynamic instrumentation, or target changes. Those actions belong to the routed analysis skill, working inside the case's `scope.md` record.

## ACTION REQUIRED

1. `NOW`: read `../field-journal/precedent-reverse.md` — routine operations done many times on this machine; follow them directly.
2. `NOW`: **查经验卡** —— `python skillpack/skills/scripts/experience-card.py search "<你看到的症状>"`。
   命中就读那张卡的 `invariant` + `decision.action`，并**逐条对照** `scope.appliesWhen`
   与 `scope.stopsWhen`：少一条前提就停用；命中任一停止条件就停。
   历史卡**不替代**当前目标的实测证据。详见 `../experience-cards/INDEX.md`。
3. `NOW`: confirm the case path and choose read-only review mode.
4. `NEXT`: read `../TOOLS.md`; this skill uses only Python 3 standard library and does not require bootstrap.
5. `NEXT`: run `python skillpack/skills/case-review/scripts/review_case.py <case-root> --format markdown` (Windows; on Linux/macOS/Kali use `python3`).
6. `ACT`: resolve every error, then rerun the review before claiming a handoff is complete.
   When the case carries `rebuild.md`, the audit's rebuild checks follow
   `../ops/rebuild-gates.md`: a row marked 已测试/对照一致 without evidence, a diff row
   missing its five columns, or a missing Coverage item is an error — fix the table,
   do not lower the check.
   The audit also reads the cited diff record's content: a completed row whose record
   shows differing stdout bytes for the two programs (`rebuild.diff_bytes_mismatch`)
   or whose registered commands did not execute (`rebuild.diff_unreproducible`) is an
   error — the table's claim never substitutes for the record. Records predating the
   raw stdout blocks only warn (`rebuild.diff_unparsed`, migration window): re-run
   `diff-runner.py` to add them.
   Negative controls for this audit: `python skillpack/skills/scripts/test-rebuild-audit-negctl.py`
   (proves the audit catches 状态虚高 / 对照表缺行 / Coverage 缺项 / 记录字节不一致 /
   命令不可复现 / 老格式记录 warning, and still passes a complete table and a case without `rebuild.md`).
   When the case carries `update.md`, the update checks follow the same gates file
   (`../ops/rebuild-gates.md` [更新阶段]) and the same table template
   (`../templates/update.md` — the sections this audit parses, produced by
   `case-init -Preset update`): a three_lines field that is empty or still
   the template placeholder, a `function_delta` that misses any F-ID from
   `rebuild.md` (or invents one without action=new), a `verification` row that
   leaves a column empty, a row asserting 一致 whose `diff-update/` record is
   missing or whose record shows differing stdout bytes, and a version fingerprint
   without a 64-hex SHA256 are all errors — fix the table or produce the record,
   do not lower the check.
   Negative controls: `python skillpack/skills/scripts/test-update-audit-negctl.py`.
   When the case carries `assault.md` (protected-target assault case, `-Preset assault`),
   the assault checks follow `../reverse-engineering/references/assault-entry.md`
   (four-state machine) + `../templates/assault.md`: an unfilled/invalid state line,
   a layers row without status+evidence, a blocked row without 原因/影响/替代, a
   function row whose state outruns its evidence (including a 已测试/对照一致 row
   whose diff_baseline verdict does not assert 一致), an unknowns item missing
   影响/下一步/是否阻塞, and a deliverable that does not exist on disk without a
   recorded blocked form are all errors — fix the table or produce the artifact,
   do not lower the check.
   Negative controls: `python skillpack/skills/scripts/test-assault-audit-negctl.py`.

## 本技能硬判据（可交 / 不可交的阈值）

- **哈希不一致不是警告**：`--verify-hashes --strict` 报某条 artifact 的 `content_hash` 对不上时，先查证据是否被改写 —— `git log -p -- evidence/<file>`、文件 mtime、工作副本与归档副本的字节差。查清之前**不许**当成通过，也不许把该检查降级成 warn。
- **两轮结论矛盾时以带哈希的原文为准**：同一 case 第一轮 Findings 引了 E-ID、第二轮为空（或反之）时，逐字节核对被引用的原文，按 **原文 + 哈希** 重判；不按「更新的那份结论」判。
- **`repro_command` 里的工具名必须能被探测层解析到**：`Resolve-ReverseToolSpec -Name <工具>` 返回 `Available=False` 时，该 Evidence 是「不可复现值」而不是「本机缺工具」—— 先排除工具只是换了目录（四级探测里第 2 级 `Get-Command` 查空不算数）。
- **引用完整性**：引用不存在的 E-ID、或 Finding 的 `evidence_ids` 为空 → error；Evidence 没有被任何 Finding / Workitem / Timeline 引用 → 未链接，strict 下按 error 计。
- **边界与格式**：`artifact_path` 落在 case root 之外，或 `content_hash` 不是 `sha256:` + 64 位十六进制 → error。
- **只读边界**：审查不改 case 内容；真要补证据或修表，先打快照（`git stash` / 复制一份），改完回本卡重跑 strict，不在审查侧放宽。
- **「可交」的数字面**：`--strict` 的 error 计数为 0，且 review 输出原文贴回，才算可交。

## 工具链与工具联动

| 环节 | 本机怎么调 | 输出接到哪 |
|---|---|---|
| 审查主体 | `python skillpack\skills\case-review\scripts\review_case.py <case> --verify-hashes --strict`（Linux/macOS/Kali 用 `python3`） | 输出原样贴回；error>0 → 不可交 |
| 哈希固定 | `sha256sum evidence\<file>`（或 PowerShell `Get-FileHash -Algorithm SHA256`），与记录里的 `content_hash` 逐字符比 | 不一致 → 先查改写来源，见上节第一条 |
| 改动溯源 | `git log -p -- evidence/<file>`、`git diff --stat work/<case>` | 判「证据是否被改写」的唯一凭据 |
| 证据产生工具 | 逆向类应点名 `IDA` / `Ghidra` / `rabin2` / `radare2` / `x64dbg`；移动类 `jadx` / `apktool` / `frida`；固件类 `binwalk`；网络类 `nmap` / `nuclei` / `sqlmap` / `curl` / `Burp`；流量类 `tshark` / `Wireshark`；样本类 `yara`；口令类 `hashcat` | 用探测层解析工具名；解析不到 → 该记录不可复现，回产生它的卡重跑 |
| 路径探测 / 通道 | `. <仓根>\skillpack\skills\scripts\lib\Bootstrap.ps1` → `Resolve-ReverseToolSpec -Name tshark`；通道状态 `powershell -NoProfile -ExecutionPolicy Bypass -File skillpack\skills\scripts\mcp-status.ps1` | `Get-Command` 查空 ≠ 缺工具；HTTP 型 MCP 平时 `closed` 是设计 |
| 报告链接口径 | `python skillpack\skills\scripts\verify-doc-links.py`（报告里出现的仓库内相对路径） | 断链数不为 0 → 交 `../docs-generator/SKILL.md` 之前必须先修 |

## Tool dependencies

| Tool | Required | Purpose | Auto-bootstrap |
|------|----------|---------|---------------|
| Python 3.9+ | Yes | Runs the read-only case review script | No, use the platform Python installation |

No network access or third-party package is required.

**Interpreter name:** `python` = Windows, `python3` = Linux / macOS / Kali. On Windows `python3` is usually a Microsoft Store alias stub that exits 9009, so every command below lists both. Pick the line that matches the current platform; both run the same read-only script.

## Workflow

### Phase 1: Intake

Run the review against the existing case directory:

```bash
python skillpack/skills/case-review/scripts/review_case.py work/<case> --format markdown   # Windows
python3 skillpack/skills/case-review/scripts/review_case.py work/<case> --format markdown  # Linux / macOS / Kali
```

Confirm that `../pentest-tools/templates/scope.md`, `../../examples/ctf-demo/timeline.md`, `../../examples/ctf-demo/workitems.md`, and `evidence/` are present. A non-strict review reports scope warnings while a strict review treats warnings as handoff blockers.

## 建议下一步（选一个编号）

1. 修复 scope.md 里的目标、范围或 network_profile 字段
2. 继续检查 Evidence 记录的可复现命令和来源
3. 导出当前 review 结果并附到阶段性报告
4. 换 JSON 输出接入 CI 或其他审查工具
5. 暂停，先确认审查范围

### Phase 2: Traceability

Review the checks for:

- Evidence IDs that do not exist
- Findings without `evidence_ids`
- Paths without an allowed `path_type` or Evidence reference
- Work items and timeline entries pointing to unknown Evidence
- Unlinked Evidence records
- Validated Findings with low confidence

An offline observation may use `repro_command: n/a` only when its `notes` field explicitly documents the offline limitation.

Use JSON when another tool needs stable fields:

```bash
python skillpack/skills/case-review/scripts/review_case.py work/<case> --format json   # Windows
python3 skillpack/skills/case-review/scripts/review_case.py work/<case> --format json  # Linux / macOS / Kali
```

## 建议下一步（选一个编号）

1. 补写缺失的 Evidence，并保留原始命令
2. 将候选 Finding 绑定到 Evidence 后重新审查
3. 为调用链或攻击链补充 P-id 和 Path 步骤
4. 生成 Markdown handoff summary
5. 换回 PRIMARY skill 继续分析

### Phase 3: Fixity verification

When an Evidence record contains both `content_hash` and `artifact_path`, verify the case-local artifact:

```bash
python skillpack/skills/case-review/scripts/review_case.py work/<case> --verify-hashes --strict   # Windows（Linux/macOS/Kali 用 python3）
```

The script accepts `sha256:<64 hex characters>` and checks that the artifact remains inside the case root. A hash mismatch is a hard failure.

The PowerShell Evidence helper can record a hash while appending a record:

```powershell
powershell -File skillpack/skills/scripts/append-evidence.ps1 -CaseRoot work\<case> -Id E-001 -Title "Sample hash" -ReproCommand "sha256sum evidence/sample.bin" -ArtifactPath "evidence\sample.bin"
```

## 建议下一步（选一个编号）

1. 修复 hash mismatch 或替换已污染的工作副本
2. 为未固定的原始文件补充 SHA-256 和 artifact_path
3. 继续进入报告生成阶段
4. 导出 JSON 结果供 CI 保存
5. 暂停并请求人工复核

### Phase 4: Handoff

Use strict mode before a final report or specialist handoff:

```bash
python skillpack/skills/case-review/scripts/review_case.py work/<case> --strict --format markdown > work/<case>/report/case-review.md   # Windows（Linux/macOS/Kali 用 python3）
```

The command is read-only with respect to the case unless shell redirection is explicitly used to save its output. The review is not legal advice and does not replace organizational evidence handling procedures.

## 建议下一步（选一个编号）

1. 将通过的 review 结果交给 `docs-generator/` 生成正式报告
2. 回到 PRIMARY skill 补齐新的分析证据
3. 归档 Markdown 和 JSON review 结果
4. 暂停并请求人工复核

## Language behavior contract

- Internal reasoning, tool selection, and phase control: English.
- User-visible messages, section labels, reports, and next-step menus: Chinese unless the user requests another language.
- Default bilingual labels place Chinese first and English second, separated by `/`.

## Bootstrap boundary

This skill has no third-party dependency. If Python 3 is unavailable, the only allowed recovery action is the repository bootstrap path when a Python capability is registered for the current platform. If no such capability is registered, stop and report the missing runtime. Do not guess executable paths, download packages, or perform a manual install from inside this skill.

## Routing context

**Upstream entry**: any reverse, forensics, CTF, or authorized security skill that has produced a case package.

**Downstream exit**: `docs-generator/` for a formal report, or the original PRIMARY skill when the graph is incomplete.

**Related modules**: `../ops/evidence-finding-path.md`, `../ops/timeline-workitem.md`, `digital-forensics/`, `reverse-engineering/`, and `docs-generator/`.

## References

- [NIST SP 800-86: Guide to Integrating Forensic Techniques into Incident Response](https://csrc.nist.gov/pubs/sp/800/86/final)
- [SWGDE Best Practices for Computer Forensic Acquisitions](https://www.swgde.org/documents/published-complete-listing/17-f-002-2-1/)
- [SWGDE Best Practices for Archiving Digital and Multimedia Evidence](https://www.swgde.org/documents/published-complete-listing/19-f-003-best-practices-for-archiving-digital-and-multimedia-evidence/)

## 任务完成自检

- [ ] 我是否审查了 scope.md、timeline.md、workitems.md 和 evidence/？
- [ ] 所有 Finding 是否引用了现存 Evidence？
- [ ] 所有 Path 是否包含合法 path_type 和 Evidence 引用？
- [ ] 是否执行了 hash verification，或记录了未执行原因？
- [ ] 是否以 strict 模式重新运行并保存了 review 结果？

---

## When NOT to use（近邻负例）

- 要新建一个 case（不是审已完成的） → 用 `../ops/scope-contract.md`
- 要写报告正文 → 用 `../docs-generator/SKILL.md`
- 要画图 → 用 `../diagram-generator/SKILL.md`
- 审的是源码/PR 而不是 case 包 → 用 `../code-review/SKILL.md`
- 发现证据链断裂，要补证据 → 用 `../ops/evidence-finding-path.md`
- 证据来自内存镜像/磁盘/流量，要重建时间线 → 用 `../digital-forensics/SKILL.md`
- 本技能是**只读**审查：不修 case 内容，只报缺陷

## When to Pivot

信号与判据见 `../ops/skill-pivot-contract.md`。本技能去向：

| 触发证据 | 换到 |
|---|---|
| `review_case.py --verify-hashes --strict` 报某条 artifact **哈希不一致** | 先判证据是否被改写（`git log -- evidence/`、mtime）；确认改写后回产生它的分析卡重出证据：`../ops/evidence-finding-path.md`（**不许**把 mismatch 降级为 warn 放行） |
| 同一 case **两轮**审查结论矛盾（Findings 的 E-ID 一轮有一条、一轮为空） | 以带哈希的原文为准重判；仍矛盾 → 判「不可交」并把缺口清单落盘 |
| scope.md 缺 `network_profile` / target 字段，或 `timeline` 为空 | `../ops/scope-contract.md` |
| Findings 有 **≥2 条**没有 `evidence_ids`，或引用了不存在的 E-ID | `../ops/evidence-finding-path.md`（在产生侧补绑定，不是在审查侧放宽） |
| `repro_command` 为空且 `notes` 没写离线限制 | 回产生该证据的卡重跑一遍命令：抓包类 `../digital-forensics/SKILL.md`，二进制类 `../reverse-engineering/SKILL.md` |
| 审的是源码/PR，根本没有 `work/<case>/` 目录 | `../code-review/SKILL.md` |
| 审查通过，要出正式报告 | `../docs-generator/SKILL.md` |
| 报告里要放攻击链图或时间线图 | `../diagram-generator/SKILL.md` |
| `rebuild.md` / `update.md` 的表格与磁盘记录对不上（表格声称一致、记录里 stdout 字节不同） | 先按 `../ops/rebuild-gates.md` 修表或产记录，再回本卡重跑 strict |

## 定义完成

本技能产出算「完成」的**外部可观测**条件（不许写形容词）：

- 审查报告落盘：每条缺陷 → case 里的具体文件与行
- `review_case.py --verify-hashes --strict` 的原始输出贴回，error 计数为 0 才叫「可交」
- 给出「可交 / 不可交」的明确判定与缺口清单（缺哪条证据、该由哪张卡补）
- 判「不可交」时写清哪个检查项是硬失败，以及已排除哪些「只是工具没装」的可能

## 输出契约

```
FACT:       <观察，带来源：命令 / 文件:行 / Evidence ID>
HYPOTHESIS: <可测试断言 + confidence: high|medium|low>（状态见 `../ops/binary-model.md`）
QUESTION:   <当前最大不确定点>
NEXT:       <继续 | 换技能 | 停止（附成本判据）>
```

## 置信度词表

词表见 `../ops/confidence-vocabulary.md`。本技能特有判据：

- `confirmed`：哈希与证据链全部核对过（strict error = 0），且审查结论有具体行号支撑
- `medium`：结构检查通过，但未跑 `--verify-hashes`（case 里没有 `artifact_path` 或未联网取原文）
- `low`：仅通读了报告文本，未跑哈希校验，或结论建立在表格自己的声称上
