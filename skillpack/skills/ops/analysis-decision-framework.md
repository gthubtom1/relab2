# Analysis Decision Framework (Issue #77)

> **SSoT role**: Decision-quality / evidence-sufficiency / agent-bias cookbook for reverse-skill agents.
> **Not** a second master analysis workflow. Obey `../reverse-engineering/references/re-agent-workflow.md`, feasibility gate (#73), IAT iron rule (#72), A-T / U-AV cookbooks, and `evidence-finding-path.md` first.
> Rule IDs **R1-R51** keep the reporter numbering (**no R15**; includes **R50/R51**). Do not renumber.
> **Namespace:** these are **ADF-*** overlay IDs. They are **not** `routing.json` PRIMARY ids (R1=APK, R6=IDA, …). Say "ADF-R1" when speaking.
>
> **加载时机（2026-10-14 提主链）**：本文件**不再**是"Synthesis / stuck-loop only"。
> 换阶段前、换技能前、收工前 **MUST** 查 R2 / R31 / R43（见 §0 表）。
> 原因：判据卡若不在主链上，"按证据改路线"就只是口号 —— 节点上没有任何机制要求模型查它。

## 0. How to use

| When | Action |
|------|--------|
| **换阶段前**（进下一阶段/收尾） | **MUST** R2, R31, R43 |
| **换技能前**（命中 skill-pivot-contract 任一信号） | **MUST** R2, R31, R43 |
| Finding promotion / Synthesis | **P0** (R4*, R1, R2, R41) |
| Stage change or stuck loop | R2, R31, R43 |
| Multi-module / anti-analysis | R50, R51 -> anti-analysis + A-T |
| Already covered by ops/CI/skills | **P2** pointer only |

**这三条的判据含义**（不是顺序，是"换之前必须回答"）：
- **R2** 假设驱动阶段退出：陈述当前假设，**continue / switch / stop** 三选一，不许沉默跳过
- **R31** 阶段偏执自检：是否因为"这个环境用熟了"而拒绝切换（Votipka 实测此现象 N=1 明言）
- **R43** 计划死锁重规划：连续 3 个动作无新证据，或 2 次换阶段无证据 → 重规划

**Evidence IDs** (record even on failure):

`E-confidence-low` · `E-hypothesis-confirmed` · `E-hypothesis-rejected` · `E-insufficient-evidence` · `E-negative-evidence` · `E-scope-boundary` · `E-runtime-only` · `E-bias-detected` · `E-over-trust-bias` · `E-module-decoupled` · `E-anti-adversarial` · `ungrounded`

---

## 1. P0 — Full recipes (trigger -> action -> Evidence)

### R1 — Decompile / static confidence band

| | |
|--|--|
| **Trigger** | Static decompile/CFG/types as primary reasoning |
| **Action** | Band `high`/`medium`/`low`. If `low`: MUST schedule dynamic before `validated` |
| **Evidence** | `E-confidence-low` |

### R2 — Hypothesis-driven stage exit

| | |
|--|--|
| **Trigger** | End of triage/static/dynamic or long tool loops |
| **Action** | State hypothesis; **continue / switch / stop** |
| **Evidence** | `E-hypothesis-confirmed` or `E-hypothesis-rejected` |

### R3 — Least surprise

Unverified unusual claims MUST be tagged `speculative`.

### R4* — Finding sufficiency (compatible rewrite)

Does **not** replace "Finding binds >=1 Evidence". Tightens **validated** only:

| status | Evidence bar |
|--------|----------------|
| preliminary / candidate | >=1 (unchanged) |
| **validated** | **SHOULD >=2 independent** Evidence (best 1 static + 1 dynamic). Single Evidence MUST NOT silently promote — residual + human, or stay candidate |
| blocked promotion | `E-insufficient-evidence` |

### R6 — Negative evidence

Checked-absent branch -> `E-negative-evidence`.

### R7 — Analysis boundary

Declare scope limits -> `E-scope-boundary` (align scope-contract).

### R8 — Suspicious != malicious

Default `flavor=null` unless `explicit_malware` / user asks (#71).

### R30 — Runtime back-annotation

Dynamic without static anchor: try relocate; else `E-runtime-only`, Finding <= candidate.

### R31 — Stage bias self-check

Tool/stage fixation -> `E-bias-detected`.

### R41 — Grounded conclusions

Claims MUST map Finding -> Evidence; else `ungrounded`.

### R43 — Plan deadlock -> replan

3 actions with no new Evidence, or 2 stage switches without Evidence -> replan under **feasibility gate**. Aligns RULES Self-Supervision.

### R44 — Single-source high confidence

Cross-check before validated; else `E-over-trust-bias`.

### R50 — Multi-module decoupling

Separate work items -> `E-module-decoupled`.

### R51 — Adversarial effort

Effort band + A-T pointers -> `E-anti-adversarial` (**no** A-T table copy).

---

## 2. P1 — Short rows

| ID | Landing |
|----|---------|
| R5 | content_hash; evidence-finding-path + review_case --verify-hashes |
| R12 | parallel hypotheses via R2 (no heavy case-branch product) |
| R22 | docs-generator executive summary MUST |
| R23 | IOC dual-channel **only** explicit_malware / user IOC; forbidden default ordinary RE |
| R28 | authorized lab; no full weaponized exploit chain in-repo |
| R34 | SHOULD journal stale note; **no** 90-day auto engine |
| R36 | archive feedback one-liner |
| R38-R40 | pointer -> llm-security only |
| R42 | YARA/detections experimental until benign validation |
| R45-R49 | route cloud-k8s / firmware / pentest-pwn / code-audit; limit confidence if missing context |

### Downgrades (not Agent runtime MUST)

| ID | Why |
|----|-----|
| R16/R19 auto-close PR | CI / human maintainer |
| R37 MCP gateway product | no in-repo gateway; runtime tool discovery + human confirm |
| R23 unconditional block | conflicts flavor=null |
| R34 automated stale | no metrics infra |

---

## 3. P2 — Covered elsewhere (index only)

| IDs | SSoT |
|-----|------|
| R9-R11 | timeline-workitem, case-init, case-review |
| R13-R14 + IAT | re-agent-workflow (#67/#72/#73) |
| R16-R19 (sans auto-close) | smoke, verify, CI, case-review |
| R20-R21 | evidence-finding-path, append-evidence |
| R24 | field-journal/anonymization |
| R25-R26 | skill-supply-chain, bootstrap pin (#76) |
| R27/R29 | scope-contract, RULES security |
| R32-R33 | MASTER-ROUTING, role-map |
| R35 | field-journal |
| A-T PE anti-analysis | anti-analysis.md |
| U-AV non-PE | nonpe-format-cookbook.md |

---

## 4. Synthesis checklist

1. R41 grounded claims
2. R4* validated bar
3. R1 low confidence -> dynamic
4. R43 deadlock -> replan under feasibility gate
5. R8/R23 no default malice/IOC

---

## 5. Blindspot appendix (Issue #77 batch 2)

Language runtimes, heavy obfuscation, injection/detect chains, formats, and agent-meta blindspots: see [analysis-blindspot-cookbook.md](analysis-blindspot-cookbook.md) (**R52-R81**). Decision rules R1-R51 in this file remain superior.
