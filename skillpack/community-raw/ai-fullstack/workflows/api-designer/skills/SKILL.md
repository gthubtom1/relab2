---
name: community-ai-fullstack-delivery-skills
description: Adapted capability from workflows/api-designer/skills/SKILL.md.
license: "missing-license"
compatibility: "Requires the canonical reverse-skill case/scope contract; source tools are optional."
allowed-tools: Read Write Edit Glob Grep Bash
metadata:
  integrated: "true"
  integration-source: "ai-fullstack-delivery"
  source-path: "workflows/api-designer/skills/SKILL.md"
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

# API 设计 Skills 总控

本目录收录 API 设计工作流的所有方法论 skills。

## 当前 Skills

| Skill | 适用场景 | 来源 |
|-------|---------|------|
| [resource-modeling](resource-modeling/SKILL.md) | REST 资源建模 | REST 架构 + Roy Fielding |
| [endpoint-design](endpoint-design/SKILL.md) | 端点设计 | RFC 7231 / GitHub REST Guidelines |
| [request-response](request-response/SKILL.md) | 请求响应结构 | JSON:API / OpenAPI |
| [error-handling](error-handling/SKILL.md) | 错误码设计 | RFC 7807 Problem Details |
| [auth-permission](auth-permission/SKILL.md) | 认证鉴权 | OAuth 2.0 / RBAC |
| [pagination-filtering](pagination-filtering/SKILL.md) | 分页筛选排序 | Stripe / GitHub 风格 |
| [versioning](versioning/SKILL.md) | API 版本管理 | Stripe 版本策略 |
| [idempotency-retry](idempotency-retry/SKILL.md) | 幂等和重试 | Stripe Idempotency |
| [webhook-async](webhook-async/SKILL.md) | Webhook 和异步 | Stripe Webhooks / SVIX |
| [openapi-mock](openapi-mock/SKILL.md) | OpenAPI 契约和 Mock | OpenAPI 3.1 |

## 统一入口

1. 先读 `routing.md` — 按 API 任务路由
2. 再进入对应 SKILL.md
3. 需要模板时进入 `<skill>/templates/`

## 工作思路

skills 可以按需组合：

```text
1. 拿到需求 → 先建模
   - resource-modeling（资源建模）

2. 设计端点 → 列清单
   - endpoint-design（端点设计）
   - request-response（请求响应）

3. 处理错误和权限
   - error-handling（错误码）
   - auth-permission（认证鉴权）

4. 高级功能
   - pagination-filtering（分页筛选）
   - idempotency-retry（幂等重试）
   - webhook-async（异步通信）

5. 输出和演进
   - openapi-mock（OpenAPI + Mock）
   - versioning（版本管理）
```

## 新增 Skill

按 `CONTRIBUTING.md` 流程新增。

## 自动进化

每次完成 API 设计任务后，回写经验到 `../field-journal/`。
