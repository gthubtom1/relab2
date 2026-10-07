---
name: sql-analysis
description: SQL 数据分析时使用。适用于业务指标查询、漏斗分析、留存计算、窗口函数、CTE 递归。
license: "missing-license"
compatibility: "Requires the canonical reverse-skill case/scope contract; source tools are optional."
allowed-tools: Read Write Edit Glob Grep Bash
metadata:
  integrated: "true"
  integration-source: "ai-fullstack-delivery"
  source-path: "workflows/data-analyst/skills/sql-analysis/SKILL.md"
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

# SQL 数据分析（SQL Analysis）

## 适用场景

- 业务指标查询（GMV / DAU / 转化率）
- 漏斗分析
- 留存分析（N 日留存）
- 同比环比
- 窗口函数（排名 / 累计 / 移动平均）
- CTE 递归（层级 / 链路）

## 核心原则

```text
1. 先明确问题再写 SQL
2. 用 CTE 分步骤（可读）
3. 注意时区和日期边界
4. 排除测试数据 / 异常值
5. 大表注意性能（索引 / 分区）
6. 结果必须可解释
```

## 常用模式

### 漏斗分析

```sql
WITH funnel AS (
  SELECT
    COUNT(DISTINCT CASE WHEN event = 'view' THEN user_id END) AS step1_view,
    COUNT(DISTINCT CASE WHEN event = 'add_cart' THEN user_id END) AS step2_cart,
    COUNT(DISTINCT CASE WHEN event = 'checkout' THEN user_id END) AS step3_checkout,
    COUNT(DISTINCT CASE WHEN event = 'payment' THEN user_id END) AS step4_payment
  FROM events
  WHERE created_at BETWEEN '2026-05-01' AND '2026-05-31'
)
SELECT
  step1_view,
  step2_cart,
  ROUND(step2_cart * 100.0 / step1_view, 1) AS cart_rate,
  step3_checkout,
  ROUND(step3_checkout * 100.0 / step2_cart, 1) AS checkout_rate,
  step4_payment,
  ROUND(step4_payment * 100.0 / step3_checkout, 1) AS payment_rate
FROM funnel;
```

### N 日留存

```sql
WITH first_day AS (
  SELECT user_id, MIN(DATE(created_at)) AS first_date
  FROM events
  GROUP BY user_id
),
retention AS (
  SELECT
    f.first_date,
    DATE(e.created_at) - f.first_date AS day_n,
    COUNT(DISTINCT e.user_id) AS retained
  FROM events e
  JOIN first_day f ON e.user_id = f.user_id
  GROUP BY f.first_date, day_n
)
SELECT
  first_date,
  MAX(CASE WHEN day_n = 0 THEN retained END) AS d0,
  MAX(CASE WHEN day_n = 1 THEN retained END) AS d1,
  MAX(CASE WHEN day_n = 7 THEN retained END) AS d7,
  MAX(CASE WHEN day_n = 30 THEN retained END) AS d30
FROM retention
GROUP BY first_date
ORDER BY first_date;
```

### 窗口函数

```sql
-- 排名
SELECT user_id, amount,
  RANK() OVER (ORDER BY amount DESC) AS rank
FROM orders;

-- 累计
SELECT date, revenue,
  SUM(revenue) OVER (ORDER BY date) AS cumulative
FROM daily_revenue;

-- 移动平均（7日）
SELECT date, revenue,
  AVG(revenue) OVER (ORDER BY date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS ma7
FROM daily_revenue;
```

## 配套模板

- `templates/sql-analysis-template.md` — SQL 分析记录模板

## 质量自检

```text
□ 问题明确
□ 数据源正确
□ 时区处理
□ 排除异常
□ 性能可接受
□ 结果可解释
□ CTE 可读
```

## 常见坑

1. **时区不一致**——UTC vs Local 差 8 小时
2. **不排除测试数据**——指标失真
3. **COUNT vs COUNT DISTINCT**——去重遗漏
4. **NULL 参与计算**——结果偏差
5. **大表全扫**——超时

## 与其他 skill 的协作

```text
上游：metric-design → 指标定义
下游：data-visualization → 图表展示
下游：analysis-report → 纳入报告
```
