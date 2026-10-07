---
name: community-ai-fullstack-delivery-postmortem-doc
description: Adapted capability from workflows/technical-writer/skills/postmortem-doc/SKILL.md.
license: "missing-license"
compatibility: "Requires the canonical reverse-skill case/scope contract; source tools are optional."
allowed-tools: Read Write Edit Glob Grep Bash
metadata:
  integrated: "true"
  integration-source: "ai-fullstack-delivery"
  source-path: "workflows/technical-writer/skills/postmortem-doc/SKILL.md"
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

﻿---
name: postmortem-doc
description: 复盘文档编写时使用。适用于事故复盘 / 时间线 / 根因 / 改进项。
---

# postmortem-doc

## 适用场景

- 复盘文档编写时使用。适用于事故复盘 / 时间线 / 根因 / 改进项。

## 核心原则

```text
1. 读者优先（不是作者方便）
2. 可搜索 / 可导航
3. 保持更新（过期文档 = 误导）
4. 示例 > 描述
5. 图表辅助理解
```n
## 配套模板

- `templates/postmortem-doc-template.md`

## 质量自检

```text
[] 读者明确
[] 结构清晰
[] 示例完整
[] 可搜索
[] 保持更新
```n
## 常见坑

1. 写完不更新
2. 没有示例
3. 太长没导航
4. 术语不一致
5. 敏感信息泄露

## 与其他 skill 的协作

```text
上游：各工作流 → 技术输入
下游：用户 / 团队 → 消费文档
```n