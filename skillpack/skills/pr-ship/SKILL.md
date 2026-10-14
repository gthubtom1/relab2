---
name: pr-ship
description: 用最小、可审的 PR 交付改动，并附作者自己的验证证据与完整描述。用于：帮我把这个改动提成 PR、要开 PR 了、把这个 feature 交付出去。
---

# 交付（Ship a PR）

本技能管**把一份已完成且已自审的改动交付出去**：切小、写描述、附证据、确认 CI 与部署状态。它管的是"交付形态是否可审、可复现"，不是"代码写得好不好"——后者归 `../code-review/SKILL.md`。

## 判据（本技能的核心）

- 若 PR 大到 reviewer 无法一次读完（多件事混在一起、夹带无关重构） → 拆成多个 PR 再交；小到能高效审，是交付的硬要求，不是礼貌。
- 若描述只写了"改了什么"而没写**更高层目标** → 补上目标，并链接相关 issue / spec / 设计文档；reviewer 需要知道你为何做这件事。
- 若描述里没有**"我如何验证"**的证据 → 补：截图、录屏、手测记录、命令与输出、测试运行结果。没有证据的"我测过了"不算。
- 若这段代码是 agent / 工具**生成但你自己没读过** → **不要提 PR**。把未经自己阅读的生成代码变成 PR，是把真正的工作（读懂改动）转嫁给 reviewer，属于反模式；要么自己读懂并担责，要么先别交。
- 若 PR 描述**你自己没读过** → 先读再交；描述与代码不一致时以代码为准，改描述。
- 若 CI 未绿 → 不交；红着的构建不是"小问题"，它会阻塞别人。
- 若只有"开发者说 done" → 不算 done。done = **已部署**，或已推到可部署到 production-like 状态（构建产物 / 镜像 / 可跑的发布路径存在且经手验证）。
- 若这次交付依赖**尚未合并/未发布**的前置改动 → 在描述里显式写明依赖与顺序，不隐性假设。

## When NOT to use（近邻负例）

- 要写的是变更说明文档 / release notes 正文 → 用 `../docs-generator/SKILL.md`
- 要审的是 case 证据包 → 用 `../case-review/SKILL.md`
- 要评审的是代码本身的设计与正确性 → 用 `../code-review/SKILL.md`
- 前置条件：改动尚未自审 / 未跑通 → 先 `../verify-done/SKILL.md`

## When to Pivot

信号与判据见 `../ops/skill-pivot-contract.md`。本技能去向：

| 触发证据 | 换到 |
|---|---|
| 改动未自审、不确定是否真的工作 | `../verify-done/SKILL.md` |
| 改动需要同步 README / changelog | `../docs-changelog/SKILL.md` |
| PR 描述要引用的图（架构 / 流程）还没画 | `../diagram-generator/SKILL.md` |
| CI 在构建 / 依赖链上失败且原因不明 | `../supply-chain-security/SKILL.md` |
| 交付后要补一份正式说明报告 | `../docs-generator/SKILL.md` |

## 定义完成

本技能产出算「完成」的**外部可观测**条件（不许写形容词）：

- PR 链接存在，CI 全绿（贴出最近的运行结论）
- 描述含：更高层目标 + 相关 issue / spec 链接 + "我如何验证"一节（附截图 / 录屏 / 手测或命令记录）
- 作者已**亲自读过**最终代码与最终描述（能指出描述里每一句对应的改动）
- 部署状态明确：已部署，或已给出可复现的部署路径与验证过的那一步

## 输出契约

```
FACT:       <观察，带来源：命令 / 文件:行 / Evidence ID>
HYPOTHESIS: <可测试断言 + confidence: high|medium|low>（状态见 ../ops/binary-model.md）
QUESTION:   <当前最大不确定点>
NEXT:       <继续 | 换技能 | 停止（附成本判据）>
```

## 置信度词表

词表见 `../ops/confidence-vocabulary.md`。本技能特有判据：

- `confirmed`：CI 运行记录与部署/可部署证据都在手，描述中每条主张都能指到 diff 中的行或一条命令
- `low`：只有作者口述"done"，没有 CI 结果、没有可复现的验证步骤
