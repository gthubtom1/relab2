---
name: docs-changelog
description: 让代码改动与 README、文档、changelog 保持同步，避免文档 stale 或留下孤儿说明。用于：改了接口要不要更新文档、补个 changelog、文档跟代码对不上了。
---

# 文档与变更记录同步

本技能管**改动落地时文档侧的收尾**：哪些改动必须同步文档、changelog 写什么、旧内容怎么删。目标是让仓库里不留 stale 说明，也不留没人维护的孤儿段落。

本技能只管"同步"这件事；要写一份完整的报告 / README 正文，归 `../docs-generator/SKILL.md`。

## 判据（本技能的核心）

- 若改动涉及 **build / test 命令 / 接口签名 / 配置项 / 发布流程** → 对应文档 MUST 同步更新；只改代码不改文档，等于把文档变成错误信息。
- 若改动**删除或弃用了代码 / 接口 / 选项** → 其文档一并处理：删除、或改成明确的弃用说明；**不留孤儿说明**（描述已不存在的东西是纯负债）。
- 若 changelog 写成 **commit 列表的复述**（"重命名 X""修 typo"） → 改写成**用户可感知的变化**：新能力、行为变更、破坏性变更、迁移步骤；内部重构通常不进 changelog。
- 若文档里**复制了代码 / 配置全文** → 改为引用文件（相对路径 / 链接），只保留必要的说明与最小示例；复制的副本必然会 stale。
- 若文档已经很长 → 精简。太长的文档会被读者跳过（有现实的字符上限与注意力上限），把关键信息放在前面，其余按需拆分或删掉。
- 若**不存在对应文档** → 不要凭空造一份大而全的；按需加最小的一节（或在新接口处加简短说明），或明确记录"当前无此文档"这一事实。
- 若文档与代码已经**不一致**（改了代码但漏了上一次的同步） → 先修正不一致，再补本次改动，不要在同一段落上叠新的错误。
- 若改动**面向内部、无外部可观测影响** → 不必强行进 changelog；但若它改变了开发者的用法（如构建命令），仍需更新开发者文档。

## When NOT to use（近邻负例）

- 要写一份完整报告 / 渗透测试报告 / writeup → 用 `../docs-generator/SKILL.md`
- 要画图表（流程图 / 架构图 / 时序图）→ 用 `../diagram-generator/SKILL.md`
- 要审 case 包完整性（证据链、哈希）→ 用 `../case-review/SKILL.md`
- 前置条件：代码改动本身尚未定稿 → 先 `../code-review/SKILL.md` 或 `../verify-done/SKILL.md`，别同步一份还会变的说明

## When to Pivot

信号与判据见 `../ops/skill-pivot-contract.md`。本技能去向：

| 触发证据 | 换到 |
|---|---|
| 文档需要结构化的图表才能说清 | `../diagram-generator/SKILL.md` |
| 用户要的其实是一份完整交付文档 | `../docs-generator/SKILL.md` |
| 发现文档里的接口说明与实现矛盾，怀疑是 bug | `../code-audit/SKILL.md` |
| 改动还没定稿就急着写文档 | `../code-review/SKILL.md` |
| 发布链 / 依赖清单文档与 SBOM 不符 | `../supply-chain-security/SKILL.md` |

## 定义完成

本技能产出算「完成」的**外部可观测**条件（不许写形容词）：

- 受本次改动影响的文档文件均已更新，且与代码一致（能指出每一处文档改动对应的代码改动）
- changelog 中已加入本次条目，措辞为面向用户的可感知变化，并附必要迁移说明
- 仓库内不存在描述已删除功能的孤儿段落（grep 旧名字只剩历史 changelog 条目）

## 输出契约

```
FACT:       <观察，带来源：命令 / 文件:行 / Evidence ID>
HYPOTHESIS: <可测试断言 + confidence: high|medium|low>（状态见 ../ops/binary-model.md）
QUESTION:   <当前最大不确定点>
NEXT:       <继续 | 换技能 | 停止（附成本判据）>
```

## 置信度词表

词表见 `../ops/confidence-vocabulary.md`。本技能特有判据：

- `confirmed`：逐条核对了本次代码改动所触及的文档引用点，并 grep 过被删功能名确认无孤儿说明
- `low`：只更新了 changelog，未检查 README / 接口文档是否随之失效
