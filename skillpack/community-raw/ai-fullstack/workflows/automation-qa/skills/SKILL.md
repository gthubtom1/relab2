---
name: community-ai-fullstack-delivery-skills
description: Adapted capability from workflows/automation-qa/skills/SKILL.md.
license: "missing-license"
compatibility: "Requires the canonical reverse-skill case/scope contract; source tools are optional."
allowed-tools: Read Write Edit Glob Grep Bash
metadata:
  integrated: "true"
  integration-source: "ai-fullstack-delivery"
  source-path: "workflows/automation-qa/skills/SKILL.md"
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

# 自动化测试 Skills 总控

## 当前 Skills

| Skill | 适用场景 | 来源 |
|-------|---------|------|
| [unit-testing](unit-testing/SKILL.md) | 单元测试 | Jest / Vitest / pytest / JUnit |
| [integration-testing](integration-testing/SKILL.md) | 集成测试 | Testcontainers / Supertest |
| [e2e-testing](e2e-testing/SKILL.md) | E2E 测试 | Playwright / Cypress |
| [api-contract-testing](api-contract-testing/SKILL.md) | API 契约测试 | Pact / Dredd |
| [ci-test-integration](ci-test-integration/SKILL.md) | CI 测试集成 | GitHub Actions / GitLab CI |
| [coverage-reporting](coverage-reporting/SKILL.md) | 覆盖率报告 | Codecov / Istanbul / JaCoCo |

## 统一入口

1. 先读 `routing.md`
2. 再进入对应 SKILL.md

## 新增 Skill

按 `CONTRIBUTING.md` 流程新增。
