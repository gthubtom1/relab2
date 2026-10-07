---
name: community-ai-fullstack-delivery-skills
description: Adapted capability from workflows/project-manager/skills/SKILL.md.
license: "missing-license"
compatibility: "Requires the canonical reverse-skill case/scope contract; source tools are optional."
allowed-tools: Read Write Edit Glob Grep Bash
metadata:
  integrated: "true"
  integration-source: "ai-fullstack-delivery"
  source-path: "workflows/project-manager/skills/SKILL.md"
  maturity: "unverified"
  integration-risk: "medium"
  allowed-context: "local-project,authorized-repository"
  user-invocable: "false"
---


## Integrated reverse-skill contract

This capability is loaded through the canonical reverse-skill router. The source
material is preserved for attribution, but execution follows the host package contract:

1. **Scope first**: initialize the current `work/<case>/scope.md` with the canonical
   `case-init` flow. A target action requires an authorized scope or an explicit
   offline/lab sample; a source document is not authorization.
2. **Tools by registry**: read the package `skills/tool-index.md` before using a tool.
   Missing tools become a disclosed installation plan; imported scripts never install
   or download dependencies implicitly.
3. **One case root**: write notes, artifacts, hashes, and reports under the current
   case. Do not create a parallel source-package `case`, `output`, or `workspace`
   tree.
4. **Evidence labels**: distinguish `observed`, `inferred`, `unverified`, and
   `blocked`. Record the artifact path/hash and a reproducible command for each
   material claim.
5. **Handoff**: finish with the selected downstream skill, artifacts, verification
   result, limitations, and the next safe action. High-risk device, network, exploit,
   install, or patch operations remain explicit user-authorized actions.

The imported text may describe a different host or directory layout. Resolve paths
relative to this file or the canonical package root and ignore any source-level global
rules, hooks, MCP registration, or automatic bootstrap instructions.

# 项目经理 Skills 总控

本目录收录了项目经理工作流的所有方法论 skills。

## 当前 Skills

| Skill | 适用场景 | 来源 |
|-------|---------|------|
| [wbs-decomposition](wbs-decomposition/SKILL.md) | 任务分解为可执行工作包 | PMP / WBS 标准 |
| [critical-path](critical-path/SKILL.md) | 识别关键路径和并行机会 | CPM 关键路径方法 |
| [orchestration](orchestration/SKILL.md) | 选择编排模式（顺序/并发/交接/动态） | Microsoft Azure AI Agent Patterns |
| [handoff-protocol](handoff-protocol/SKILL.md) | 工作流间交接协议 | Skywork / Augment Code |
| [risk-management](risk-management/SKILL.md) | 风险识别和缓解 | PMBOK 风险矩阵 |
| [milestone-gate](milestone-gate/SKILL.md) | 里程碑设计和交付门禁 | Stage-Gate 方法 |
| [change-control](change-control/SKILL.md) | 变更影响评估和决策 | PMBOK 变更控制 |
| [progress-tracking](progress-tracking/SKILL.md) | 进度追踪和阻塞升级 | 任务状态机 + 三级升级 |
| [dora-metrics](dora-metrics/SKILL.md) | 交付效能度量 | Google DORA / Accelerate |
| [okr-alignment](okr-alignment/SKILL.md) | 项目与 OKR 对齐 | Google OKR Playbook |
| [shape-up-cycles](shape-up-cycles/SKILL.md) | Cycle 节奏管理 | Linear / Basecamp Shape Up |
| [retrospective](retrospective/SKILL.md) | 项目复盘 | Agile Retrospectives |

## 统一入口

1. 先读 `routing.md` — 按任务类型路由
2. 再进入对应 SKILL.md
3. 需要模板时进入 `<skill>/templates/`

## 工作思路

skills 可以按需组合：

```text
1. 拿到项目需求 → 先判断复杂度
   - S/M 级 → 加载 wbs + handoff
   - L 级 → 加载 wbs + critical-path + orchestration + risk + milestone-gate
   - XL 级 → 加载所有 skills

2. 项目执行中 → 加载 progress-tracking
3. 需求变更 → 加载 change-control
4. 项目完成 → 加载 retrospective
5. 季度规划 → 加载 okr-alignment
6. 效能分析 → 加载 dora-metrics
```

## 新增 Skill

发现路由未命中时，按 `CONTRIBUTING.md` 流程新增。

## 自动进化

每次完成项目管理任务后，回写经验到 `../field-journal/`。
