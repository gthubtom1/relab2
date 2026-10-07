---
name: reliability-engineering
description: 可靠性工程时使用。适用于 SLO 定义 / 错误预算管理 / Chaos Engineering / 灾备演练。融合 Google SRE SLO + Netflix Chaos Monkey。
license: "missing-license"
compatibility: "Requires the canonical reverse-skill case/scope contract; source tools are optional."
allowed-tools: Read Write Edit Glob Grep Bash
metadata:
  integrated: "true"
  integration-source: "ai-fullstack-delivery"
  source-path: "workflows/sre-operations/skills/reliability-engineering/SKILL.md"
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

# 可靠性工程（Reliability Engineering）

## 适用场景

- SLO / SLI 定义和评审
- 错误预算管理
- Chaos Engineering（故障注入）
- 灾备演练
- 可靠性评审

## 核心原则

```text
1. SLO 是合同
   与 PM / 业务方对齐的可靠性目标

2. 错误预算是杠杆
   预算充足 → 可以快速发布
   预算耗尽 → 冻结发布，专注稳定

3. 主动注入故障
   不等生产出事才知道弱点

4. 100% 可用是错误目标
   追求 100% = 不发布 = 不创新
```

## SLO 框架

```text
SLI（指标）：
  - 可用性 = 成功请求 / 总请求
  - 延迟 = P99 < 500ms 的比例
  - 正确性 = 正确响应 / 总响应

SLO（目标）：
  - 可用性 99.9%（月 43 分钟不可用）
  - 延迟 99% 请求 P99 < 500ms

错误预算：
  - 月预算 = 1 - SLO = 0.1%
  - 消耗 > 50% → 警告
  - 消耗 > 80% → 冻结发布
```

## Chaos Engineering

```text
原则：
  1. 定义稳态（正常指标）
  2. 假设稳态会持续
  3. 注入故障
  4. 观察是否偏离稳态
  5. 修复发现的弱点

常见实验：
  - 杀 Pod（K8s）
  - 网络延迟注入
  - 磁盘满
  - 第三方超时
  - DNS 故障
  - 数据库主从切换

工具：
  - Chaos Monkey（Netflix）
  - Litmus Chaos（K8s）
  - Gremlin（SaaS）
  - Chaos Mesh（K8s）
  - toxiproxy（网络故障）
```

## 配套模板

- `templates/slo-definition-template.md` — SLO 定义 + 错误预算 + Chaos 实验

## 质量自检

```text
□ SLO 与业务方对齐
□ 错误预算跟踪
□ 预算耗尽有动作
□ Chaos 实验定期
□ 灾备演练（季度）
□ 弱点修复跟踪
```

## 常见坑

1. **SLO 100%**——不现实
2. **SLO 不与业务对齐**——技术自嗨
3. **错误预算不跟踪**——形同虚设
4. **不做 Chaos**——生产才发现弱点
5. **Chaos 在生产不敢做**——先从 staging 开始

## 与其他 skill 的协作

```text
上游：
  devops-engineer monitoring-alerting → SLI 数据

下游：
  postmortem → SLO 违反时复盘
  capacity-planning → 可靠性影响容量
  incident-response → SLO 违反触发响应
```
