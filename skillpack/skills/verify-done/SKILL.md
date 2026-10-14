---
name: verify-done
description: 给 agent 一个自己可跑、返回 pass/fail 的 check，并用独立 context 复核需求。用于：怎么确认改好了、做完了没有、跑一遍验证、核对需求逐条。
---

# 验证做完了（Verify Done）

本技能回答一个问题：**凭什么说这件事做完了**。它管的是「拿证据还是下结论」「谁来复核」「哪些 gap 必须补」。核心判据只有一条：若没有 agent 自己可跑、返回 pass/fail 的 check，「看起来做完了」就是唯一信号，人就被迫变成验证回路 —— 这正是「每次说改好了、下次又出问题」的机制。

## 判据（本技能的核心）

- 收工前先确认存在一个**可执行、返回 pass/fail** 的 check：测试套件、`build` 退出码、linter、类型检查、截图 diff、契约比对。没有 → 先造一个最小的，再造之前不谈完成。
- 报告完成时给**证据**而不是**结论**：贴测试输出、命令 + 退出码、截图。结论（「应该没问题了」）不是证据。
- 绿了还不够：要能对上**每条需求**。用 fresh-context subagent（独立上下文、不看你的推理过程）按需求逐条核对 diff —— 避免自己被自己写下的上下文说服。
- 复核只采纳影响**正确性或需求**的 gap；风格、命名、可选加固标 `optional`，不当阻塞项（防止 over-engineering 把交付拖垮）。
- done 是三元不是一件：`verified`（有证据且能跑绿）+ `reviewed`（人看过并理解）+ `deployable/shipped`（能部署或已上线）。缺哪个就如实说缺哪个。
- check 必须**对需求**，不是**对你写的代码**：只测自己实现的那部分，会漏掉需求里根本没做的那一条（那条不在你的测试里）。
- 环境/配置类改动没有自动 check → 用可观察状态快照当 check（端口在听、进程存活、日志出现某行、截图前后一致），仍然要给出 pass/fail。
- check 红了而你认为「不影响」 → 不许口头豁免；要么修，要么把该风险写进交付说明并标 `low` + 具体原因。
- 一个 check 无法覆盖全部需求 → 明确列出未覆盖项与它们各自的替代 check，不允许「其余同理」这种省略。

## When NOT to use（近邻负例）

- 要写的是测试本身（测行为不测实现） → 用 `../write-tests/SKILL.md`
- 要审的是别人的代码质量或安全，不是自己的需求达成 → 用 `../code-review/SKILL.md`
- 要修的是已知 bug 的根因 → 用 `../fix-bug/SKILL.md`
- 要把结论沉淀成正式交付文档 → 用 `../docs-generator/SKILL.md`

## When to Pivot

信号与判据见 `../ops/skill-pivot-contract.md`。本技能去向：

| 触发证据 | 换到 |
|---|---|
| check 需要端到端跑浏览器/GUI 才有意义 | `../browser-automation/SKILL.md` |
| 验证对象是安全性质（越权/注入/绕过） | `../code-audit/SKILL.md` |
| 验证必须跑在容器/K8s/云环境 | `../cloud-k8s/SKILL.md` |
| 结论要变成可交付报告 | `../docs-generator/SKILL.md` |

## 定义完成

本技能产出算「完成」的**外部可观测**条件：

- check 的命令 + 退出码（绿）落盘
- 「需求逐条 → 对应 check / 证据」对照表
- fresh-context subagent 的复核报告（由独立上下文产出，非自述）
- 未覆盖项显式标 `optional` 或 `low` + 原因

## 输出契约

```
FACT:       <观察，带来源：命令 / 文件:行 / Evidence ID>
HYPOTHESIS: <可测试断言 + confidence: high|medium|low>（状态见 ../ops/binary-model.md）
QUESTION:   <当前最大不确定点>
NEXT:       <继续 | 换技能 | 停止（附成本判据）>
```

## 置信度词表

词表见 `../ops/confidence-vocabulary.md`。本技能特有判据：

- `confirmed`：check 在干净环境复现为绿，且独立 context 复核逐条对上需求
- `low`：只有自测绿、没有独立复核，或 check 只覆盖了自己实现的那一部分
