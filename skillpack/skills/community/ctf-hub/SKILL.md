---
name: community-ctf-hub
description: CTF 任务的友好分诊与教学适配层。把自动分流、头脑风暴、比赛和题解输出接到 reverse-skill 的 scope、case、证据和 CTF sandbox 流程。
---

# Community CTF hub adapter

## ACTION REQUIRED

1. `NOW`: 先按 canonical package 的 `case-init` 初始化当前 case。默认使用
   `offline-sample` 或 `lab`；用户说“CTF”不等于允许访问真实外网。
2. `NEXT`: 根据题面、附件、目标类型和用户模式选择 `auto` 或 `brainstorm`，再决定
   `teaching`、`competition`、`hints-only` 输出风格。
3. `NEXT`: 读取 `skills/community/registry.json`，选择一个 CTF 下游；优先复用
   `reverse-skill` 已有的 `ctf-sandbox`、`pwn-chain`、`apk-reverse`、
   `digital-forensics`、`malware-analysis`、`threat-intelligence` 等 canonical skill。
4. `ACT`: 只有 scope/case 就绪后才进入题目操作。工具路径只认
   `../../TOOLS.md`，不要运行上游安装脚本或隐式下载工具。
5. `DONE`: 按统一 Evidence→Finding→Path 记录样本、命令、产物 hash、置信度、
   失败分支和下一步；完成题解时转 `docs-generator` 或题解适配内容。

## Downstream map

| 题型 | canonical downstream | 社区参考 |
|---|---|---|
| Reverse / APK / WASM / 固件 | `reverse-engineering`, `apk-reverse`, `firmware-pentest` | `skillpack/community-raw/ctf-super-hub/ctf-reverse/` |
| Pwn / ROP / heap | `pwn-chain` | `skillpack/community-raw/ctf-super-hub/ctf-pwn/` |
| Web / API | `api-security`, `pentest-tools`, `browser-automation` | `ctf-web` 与 `strix-*` |
| Crypto | CTF sandbox 或本地 Python/Sage 能力 | `ctf-crypto` |
| Forensics / PCAP | `digital-forensics`, `protocol-reverse` | `ctf-forensics` |
| Malware | `malware-analysis` | `ctf-malware` |
| OSINT | `threat-intelligence` | `ctf-osint` |
| 复盘写作 | `docs-generator` | `ctf-writeup` |

上游 `ctf-*`、`strix-*` 目录是知识参考和适配输入，不是第二套全局 router；它们的
原始路径、工具安装和 scope 假设不得覆盖 canonical package。

需要机器辅助初筛时，可只读运行：

```text
python skills/scripts/community-route.py --hint "<题面或附件描述>" --source ctf-super-hub --json
```

## Loading budget（T11 / 规范 17.25）

- 单次初筛最多返回 5 个 wrapper（`--limit` 取值 1..5，越界直接 exit 2）。
- 单次查询命中的 adapted reference 总数上限 50；超预算时停止并报告
  `blocked` / `budget_exceeded`（exit 20），不静默截断。
- 每个 wrapper 初次只展示 3 个 reference（`REFERENCE_LIMIT=3`，产品决策，不得单方面调大）；
  第 4 个起是二级加载：用 `--source` 重查、逐条人工确认后再读正文。
- 置信度 `confidence = best_score / hint 词数`，低于 0.35 为 `low_confidence`；
  首尾 wrapper 分差 ≤20% 为 `ambiguous_tie`，两者都进 `needs_review`。
- 超预算后的确认格式：报出收窄后的 hint 与 `--source` 取值，等人工确认后再查。
- 完整数字与 policy manifest 变更请求见 `../../../docs/community/LOADING-BUDGET.md`（本包未落地）。

## Unified output

```text
mode / current read / why this route
next 1-3 safe steps
evidence ids + artifact hashes
failure branch + pivot
confidence / remaining limits
```
