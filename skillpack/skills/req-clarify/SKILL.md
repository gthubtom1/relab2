---
name: req-clarify
description: 把模糊需求收敛成可判定的验收标准（Given-When-Then、含负例与边界），信息不足先问不猜。用于：需求含糊、验收写不出、开工前定 spec。
---

# 需求澄清（Requirement Clarification）

本技能只做一件事：把「用户嘴里的一句话」变成「别人能照着判定通过/不通过的验收标准」，并在信息不足时把问题问回去而不是替用户脑补。它不写实现、不写架构、不写测试代码——产出是 SPEC 与验收标准文本。判断入口永远是同一个问题：**我现在能不能写出一条可判定的验收标准？** 不能，就先澄清。

## 判据（本技能的核心）

- 若写不出一条**可判定**的验收标准（给定输入 → 期望输出/状态，且能被一条命令或一次点击观察到）→ 需求还没澄清完，停下来问，不许开工。
- 若任务小且清晰（一句话能说清改动落点与验收点）→ **不写 spec，直接做**（转 `../implement-feature/SKILL.md`）；给小任务补一套 spec 是净成本。
- 若是大 feature（跨文件/跨接口/带 UI/用户自己没想清）→ 先由模型对用户做一次 **interview**：把实现口味、UI 形态、边界条件、tradeoff（快 vs 简单、通用 vs 够用）逐条问出来，再落成 **self-contained SPEC**（点名文件与接口 + 声明 out-of-scope + 结尾一条 end-to-end 验证步骤），然后**开新会话执行**。同一会话里既写 spec 又实现，等于自己给自己判卷。
- 凡信息缺失（范围、数据来源、失败态、兼容目标、性能预算）→ 不许猜；能问就问。确需假设才能推进时，该条显式标 `speculative` 并进 SPEC 的待确认清单。
- 验收标准一律写成 Given-When-Then（或「前提 - 动作 - 期望」）；每个功能点至少三条：happy path 一条 + **负例一条**（非法输入/无权限/超限）+ 边界一条（空/满/并发/临界值）。只有 happy path 的验收 = 没有验收。
- 若拿到的是口号（「要快」「要好用」「稳定点」）→ 换成带数字或可观察行为的判据（「首屏 < 1s」「点保存后列表出现新行且不刷新页面」）；换不出来 → 退回上一条，继续问。
- 若需求自带矛盾（两个约束无法同时满足，如「实时同步」+「离线可用」不加冲突策略）→ 把矛盾摊开让用户选；不许自行取舍后静默交付。
- 若用户已经给出验收标准与 out-of-scope → 跳过澄清，直接进 `../design-slice/SKILL.md` 或 `../implement-feature/SKILL.md`。

## When NOT to use（近邻负例）

- 需求已定，要的是「从哪切第一刀、怎么端到端跑通」 → 用 `../design-slice/SKILL.md`
- 需求清楚的小改动，要的是动手写代码 → 用 `../implement-feature/SKILL.md`
- 要的是给已有功能补测试/验收脚本 → 用 `../write-tests/SKILL.md`
- 要审的是已写好的 SPEC/交付文档本身 → 用 `../code-review/SKILL.md` / `../case-review/SKILL.md`
- 只是要把模糊原话记下来留档（不准备开工） → 用 `../field-journal/` 的日报，不要套 SPEC 流程
- 前置条件型：用户无法回答且无旁证（无原型、无既有系统、无对端文档）→ 停下说明缺口，不要用「先做出来再确认」蒙混

## When to Pivot

信号与判据见 `../ops/skill-pivot-contract.md`。本技能去向：

| 触发证据 | 换到 |
|---|---|
| 验收标准已成文，且每条可判定 | `../design-slice/SKILL.md`（要切片）或 `../implement-feature/SKILL.md`（小改动） |
| 同一问题问了两遍、用户都回「你定就行」，而代价不可逆（数据迁移/对外接口/收费） | 不再追问第三遍：按**保守默认**写进 SPEC，逐条标 `speculative`，并在回复里点名等确认 |
| 15 分钟内写不出 3 条验收（happy + 负例 + 边界）且澄清不出原因 | 判定「需求未定」：退回并列出缺口清单（缺什么信息、谁能给），不许开工 |
| 发现真正的分歧不在需求而在实现方案 | `../design-slice/SKILL.md` |
| 澄清过程中发现现有系统行为未知，才是真正的不确定点 | `../code-audit/SKILL.md`（读源码拿事实） |
| SPEC 写到第 2 页还没收口（背景/取舍越写越长） | 砍背景、留判据：验收标准 + out-of-scope + 一条端到端验证，其余移进附录 |
| SPEC 要写成正式文档交付 | `../docs-generator/SKILL.md` |

## 真实用例（本仓做过的）

- `../field-journal/2026-08-01_nextjs-cdk-contract-faithful-local-reconstruction.md` —— 契约复刻：验收点写成「与原实现的输入输出逐项一致」，而不是「看起来一样」。
- `../field-journal/2026-09-03_issue-pr-security-boundary-integration.md` —— 边界先写清（哪些不做），再谈实现。

## 落地载体

- SPEC/验收标准落盘：`work/<case>/spec.md` 或 issue 正文（能 diff、能引用行号）
- 版本锚点：`git add spec.md && git commit`（后续实现对照的是这个版本）
- 交接：实现方拿 SPEC 在新会话里开跑，避免「自己写卷子自己判卷」

## 定义完成

本技能产出算「完成」的**外部可观测**条件（不许写形容词）：

- 验收标准落盘（SPEC 或 issue 正文），含 **≥3 条 Given-When-Then**，其中至少 **1 条负例**、1 条边界
- 显式列出 **out-of-scope** 清单（哪些明确不做）
- 大 feature：产出自包含 SPEC —— 点名要改的**文件与接口**、写明 out-of-scope、结尾给出**一条 end-to-end 验证步骤**，并在**新会话**开跑
- 小任务：不落 SPEC，直接给出「改动落点 + 验收点」两句话
- 未决假设全部带 `speculative` 标记并可被检索

## 输出契约

```
FACT:       <观察，带来源：命令 / 文件:行 / Evidence ID>
HYPOTHESIS: <可测试断言 + confidence: high|medium|low>（状态见 ../ops/binary-model.md）
QUESTION:   <当前最大不确定点>
NEXT:       <继续 | 换技能 | 停止（附成本判据）>
```

## 置信度词表

词表见 `../ops/confidence-vocabulary.md`。本技能特有判据：

- `confirmed`：每条验收标准都能被一条命令或一次点击观察到，**且**需求方在原对话（或 issue）里逐条回声确认过
- `high`：验收标准可判定，但需求方只整体点头、未逐条看
- `low`：验收标准是我单方转写，需求方未回声；或用户原话本身含糊（口号型需求）
- `speculative`：为了推进而自行补的范围/边界/失败态假设
