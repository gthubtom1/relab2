---
name: ctf-sandbox
description: CTF/AWD 靶场入口：case-init 门禁 + sidecar orchestrator 选竞赛子技能。用于：打 CTF、AWD、比赛切题、靶场题、pwn 怎么做、环境跑起来。
---

# CTF sandbox entry (sidecar, not a second router)

## ACTION REQUIRED（读完后立刻执行）

1. `NOW`: **查经验卡** —— `python skills/scripts/experience-card.py search "<你看到的症状>"`。
   命中就读那张卡的 `invariant` + `decision.action`，并**逐条对照** `scope.appliesWhen`
   与 `scope.stopsWhen`：少一条前提就停用；命中任一停止条件就停。
   历史卡**不替代**当前目标的实测证据。详见 `../experience-cards/INDEX.md`。
2. `NOW`: 跑 `../scripts/case-init.ps1`；`auth.status=granted` 前禁止对真实外网 ACT。竞赛/靶场用 `-NetworkProfile lab` 或 `offline`。
3. `NOW`: 打开包根下的 `../../CTF-Sandbox-Orchestrator/ctf-sandbox-orchestrator/SKILL.md`，按它的 sandbox 假设继续。
4. `MUST NOT` 把 40+ 个 `competition-*` 子技能写进 `routing.json`。本入口只是一条 PRIMARY 门闩。
5. `ACT`: 由 orchestrator 选一个 downstream `competition-*`。具体题型已明确时（pwn/ROP、APK、IDA）应已由 `routing.json` 更靠前的规则赢下，不要再抢。

## 为什么单独一层

`CTF-Sandbox-Orchestrator/` 是 **GPL 旁路包**，授权默认是沙箱内部。核心路由包仍是 MIT + `../pentest-tools/templates/scope.md` 门禁。本 skill 只做关键词入口，不把竞赛树并进核心。

## 任务完成自检（声称完成前 MUST 通过）

- [ ] 我是否先走了 case-init / scope，而不是把“用户说了 CTF”当成已授权外网？
- [ ] 我是否打开了 sidecar orchestrator，而不是把 40 个子技能当 PRIMARY？
- [ ] 若任务其实是 pwn/APK/IDA，我是否让更具体的 PRIMARY 接手？

## 改编参考索引（open-reverselab `kb/ctf-website`）

> 下列 reference 改编自 `LING71671/open-reverselab` 的 `kb/ctf-website/`（GPL-3.0）。
> 每篇统一为「适用信号 / 前置 / 步骤 / 判据 / 坑 / 相关」+ 完整技术正文，
> 「前置」含**本机实测**的工具状态表——照抄原库裸命令前先看那张表。
> **能力域**：本文为技术能力说明，按项目 `scope.md` 直接套用。

### `references/` — （2 篇）

- `references/index.md`
- `references/attack-network.md`

### `references/checklists/` — Web CTF 检查清单（前 30 分钟、攻击矩阵、Evidence 标准）（4 篇）

- `references/checklists/index.md`
- `references/checklists/attack-matrix.md`
- `references/checklists/evidence.md`
- `references/checklists/web-ctf-first-30-min.md`

### `references/kb-index/` — kb 总索引（1 篇）

- `references/kb-index/index.md`

### `references/payloads/` — Payload 种子库（2 篇）

- `references/payloads/index.md`
- `references/payloads/web-payload-seeds.md`

### `references/paywall/` — Paywall 检测与绕过（内容/头部/规则拦截/DOM-CSS）（5 篇）

- `references/paywall/01-paywall-detection-bypass.md`
- `references/paywall/02-http-header-manipulation.md`
- `references/paywall/03-network-rule-blocking.md`
- `references/paywall/04-content-extraction.md`
- `references/paywall/05-dom-css-manipulation.md`

### `references/workflow/` — 24h 攻防循环编排（1 篇）

- `references/workflow/24h-loop-orchestration.md`


---

## When NOT to use（近邻负例）

- 目标是真实生产系统/真实客户资产 → 用 `../attack-chain/SKILL.md`
- 任务是长期项目而非单次解题 → 用 `../docs-generator/SKILL.md`
- 只是要审一段代码 → 用 `../code-audit/SKILL.md`
- 前置条件：比赛/靶场环境；真实目标必须走 `../ops/scope-contract.md` 授权门

## When to Pivot

信号与判据见 `../ops/skill-pivot-contract.md`。本技能去向：

| 触发证据 | 换到 |
|---|---|
| 题目归类为 pwn | `../pwn-chain/SKILL.md` |
| 题目归类为逆向 | `../reverse-engineering/SKILL.md` |
| 题目要求写 writeup 交付 | `../docs-generator/SKILL.md` |

## 定义完成

本技能产出算「完成」的**外部可观测**条件（不许写形容词）：

- flag/预期解 落盘；解题步骤记录到 `timeline`
- 每题的技能选择在 route-scope 里有记录
- writeup 落盘（若需要交付）

## 输出契约

```
FACT:       <观察，带来源：命令 / 文件:行 / Evidence ID>
HYPOTHESIS: <可测试断言 + confidence: high|medium|low>（状态见 `../ops/binary-model.md`）
QUESTION:   <当前最大不确定点>
NEXT:       <继续 | 换技能 | 停止（附成本判据）>
```

## 置信度词表

词表见 `../ops/confidence-vocabulary.md`。本技能特有判据：

- `confirmed`：flag 已取得并有原始输出证据
- `low`：仅推断出解法但未实际跑通
