---
name: data-visualization
description: 数据可视化和仪表盘设计时使用。适用于图表选型、仪表盘布局、BI 工具使用。
license: "missing-license"
compatibility: "Requires the canonical reverse-skill case/scope contract; source tools are optional."
allowed-tools: Read Write Edit Glob Grep Bash
metadata:
  integrated: "true"
  integration-source: "ai-fullstack-delivery"
  source-path: "workflows/data-analyst/skills/data-visualization/SKILL.md"
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

# 数据可视化（Data Visualization）

## 适用场景

- 业务仪表盘设计
- 图表选型
- 报告配图
- 实时监控面板

## 核心原则

```text
1. 图表服务于问题
   先有问题再选图表

2. 简洁优先
   不要 3D / 彩虹色 / 动画

3. 受众决定复杂度
   管理层看 KPI 大数字
   分析师看明细交互

4. 对比是可视化之魂
   同比 / 环比 / 基线 / 目标线
```

## 图表选型

| 数据关系 | 推荐图表 |
|---|---|
| 趋势 | 折线图 |
| 对比 | 柱状图 |
| 占比 | 饼图（≤5 类）/ 堆叠柱状 |
| 分布 | 直方图 / 箱线图 |
| 相关 | 散点图 |
| 漏斗 | 漏斗图 |
| 排名 | 水平条形图 |
| 地理 | 地图 |

## 工具

| 工具 | 适合 |
|---|---|
| Metabase | 开源 / 自助 BI |
| Apache Superset | 开源 / 功能全 |
| Grafana | 运维 / 实时 |
| Looker | Google 企业 |
| Tableau | 商业智能标杆 |
| Power BI | 微软生态 |
| ECharts | 前端嵌入 |
| Recharts | React 简单图表 |

## 配套模板

- `templates/dashboard-template.md` — 仪表盘设计模板

## 质量自检

```text
□ 图表服务于问题
□ 选型合适
□ 简洁不花哨
□ 有对比基线
□ 有时间筛选
□ 受众匹配
□ 移动端可看
```

## 常见坑

1. **3D 饼图**——扭曲比例
2. **彩虹色**——无语义
3. **图表太多**——信息过载
4. **无基线**——看不出好坏
5. **指标无定义**——看不懂

## 与其他 skill 的协作

```text
上游：sql-analysis → 数据查询
下游：analysis-report → 配图
```
