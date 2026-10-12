# GOAL.md 目标锚（复刻 case 用）

> 复刻 case 根的 `GOAL.md`，≤50 行。这是**上下文压缩后第一个回读的文件**：
> 压缩丢的是对话，不是文件；先读本文件，再读 `scope.md` 与 `rebuild.md`。
> 每次决策边界（transition）把本文件连同 `scope.md` 一起放进 `carry_forward_refs`。
> 模板从 `skills/templates/goal.md` 拷贝，字段保持英文键名便于脚本/人检索。

## final_goal

> 最终交付什么：产物形态 + 落点 + 判定它"交出来了"的那一句话。

- `<一句话：交付物、落点路径、对照验收的通过标准>`

## functions

> 功能清单：与 `rebuild.md` 的 functions 表同源，这里只放摘要（ID + 名称），
> 明细（入口/预期输出/验收条件/路线/状态）一律以 rebuild.md 为准，不在此复制。

- F-001 `<名称>`
- F-002 `<名称>`

## stage

> 当前阶段：从 rebuild-gates 的状态阶梯取一个，写"下一步"。

- now: `<调查 / 实现 / 对照 / 完成>`
- next: `<下一步要做的具体动作>`

## open_questions

> 未决重大事项：会改变路线或验收条件的未定项。没有就写 `(none)`。

- `<未决项 + 卡在哪 + 谁/什么能解决它>`

## last_commit

> 最近一次 commit hash（本 case 相关变更的本地提交）。

- `<hash + 一句 message>`（还没提交就写 `none`）
