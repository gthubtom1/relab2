---
name: auth-security-audit
description: 认证鉴权安全审计时使用。适用于越权检测 / IDOR / Token 安全 / 会话管理审计。融合 OWASP Testing Guide + 权限矩阵验证。
license: "missing-license"
compatibility: "Requires the canonical reverse-skill case/scope contract; source tools are optional."
allowed-tools: Read Write Edit Glob Grep Bash
metadata:
  integrated: "true"
  integration-source: "ai-fullstack-delivery"
  source-path: "workflows/security-engineer/skills/auth-security-audit/SKILL.md"
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

# 认证鉴权审计（Auth Security Audit）

## 适用场景

- 越权检测（水平 / 垂直）
- IDOR（不安全的直接对象引用）
- Token 安全（JWT / Session）
- 会话管理
- 密码策略
- 多租户隔离

## 核心原则

```text
1. 每个写操作都测越权
2. 每个读操作都测跨用户
3. Token 必须有过期 + 可撤销
4. 不暴露资源存在性
5. 多租户必须隔离
```

## 测试矩阵

```text
对每个端点：
  □ 无 Token → 401
  □ 过期 Token → 401
  □ 篡改 Token → 401
  □ 低权限角色 → 403
  □ 同角色跨用户 → 403/404
  □ 跨租户 → 403/404
  □ Admin 可访问 → 200
```

## IDOR 检测

```text
方法：
  1. 用 User A 创建资源（ID=123）
  2. 用 User B 的 Token 访问 /resources/123
  3. 预期：403 或 404
  4. 实际：如果 200 = IDOR 漏洞

常见位置：
  - GET /orders/{id}
  - PATCH /users/{id}
  - DELETE /files/{id}
  - GET /invoices/{id}/pdf
```

## 配套模板

- `templates/auth-audit-checklist.md` — 认证鉴权审计清单

## 质量自检

```text
□ 每个端点测越权
□ IDOR 全覆盖
□ Token 安全（过期 / 篡改 / 撤销）
□ 会话管理（并发 / 超时）
□ 密码策略（强度 / 重置）
□ 多租户隔离
□ 不暴露存在性
```

## 常见坑

1. **只测自己角色**——漏跨角色越权
2. **不测 IDOR**——最常见高危
3. **不测跨租户**——数据泄露
4. **Token 不测篡改**——伪造风险
5. **不测密码重置**——账号接管

## 与其他 skill 的协作

```text
上游：
  api-designer auth-permission → 权限矩阵

下游：
  security-report → 发现纳入报告
  backend-engineer → 修复
```
