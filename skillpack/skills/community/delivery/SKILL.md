---
name: community-delivery-workflow
description: 全栈软件交付编排适配层。按目标、输入、角色工作流、验收和文档沉淀推进项目，并在安全/逆向阶段交还 canonical reverse-skill 路由。
---

# Community delivery workflow adapter

## ACTION REQUIRED

1. `NOW`: 明确交付目标、项目根、输入材料、成功标准、非目标和验收产物。缺少
   关键输入先列出阻塞项，不猜工具或环境。
2. `NEXT`: 选择单一 role workflow 或有序协同链（产品→计划→设计→API/数据→实现→
   QA→安全→DevOps/SRE→文档），记录每次 handoff 的输入和输出。
3. `NEXT`: 从 `skillpack/community-raw/ai-fullstack/workflows/` 读取对应 `../../../docs/community/ai-fullstack-delivery/WORKFLOW.md`、
   templates、`../../TOOLS.md` 和 pitfalls；这些路径已被适配到当前包，不使用源仓库的
   全局 hooks、private nested checkout 或自动 bootstrap。
4. `ACT`: 安全、逆向、渗透、真实部署和外部发布动作必须交给 canonical route，遵循
   它自己的 scope/case 建档；交付工作流只负责编排和验收。
5. `DONE`: 产出验收标准、实现/测试证据、风险和回滚说明，并把可复用经验写入当前
   项目的 field-journal；未验证的模板能力标为 `unverified`。

## Canonical boundaries

- 全局安全规则仍由根 `../../../RULES.md`（上游文件，未随本包落地） 管理。
- 路由仍由 `skills/config/routing.json` 管理。
- 项目产物放在项目自己的工作根；安全 case 产物放在 `work/<case>`。
- 上游仓库没有 LICENSE，当前适配仅用于本地融合，发布前必须补授权或移除内容。

## Loading budget（T11 / 规范 17.25）

- 单次初筛最多返回 5 个 wrapper（`--limit` 取值 1..5，越界直接 exit 2）。
- 单次查询命中的 adapted reference 总数上限 50；超预算时停止并报告
  `blocked` / `budget_exceeded`（exit 20），不静默截断。
- 每个 wrapper 初次只展示 3 个 reference（`REFERENCE_LIMIT=3`，产品决策，不得单方面调大）；
  第 4 个起是二级加载：用 `--source ai-fullstack-delivery` 重查、逐条人工确认后再读正文。
- 置信度 `confidence = best_score / hint 词数`，低于 0.35 为 `low_confidence`；
  首尾 wrapper 分差 ≤20% 为 `ambiguous_tie`，两者都进 `needs_review`。
- 超预算后的确认格式：报出收窄后的 hint 与 `--source` 取值，等人工确认后再查。
- 完整数字与 policy manifest 变更请求见 `../../../docs/community/LOADING-BUDGET.md`（本包未落地）。
