---
name: community-hack-hub
description: Web、API、主机和应用安全专题适配层。将 hack-skills 的分类和深度 playbook 接到 reverse-skill 的可执行路由、授权 scope、case 证据和报告合同。
---

# Community Hack Skills adapter

## ACTION REQUIRED

1. `NOW`: 先读取 `skills/ops/scope-contract.md` 并完成 `case-init`；固定 URL、仓库、
   设备或组织名只定义目标，不自动授予扫描、利用或凭证操作权限。
2. `NEXT`: 先画攻击面并确认角色（red-team、code-audit、blue、IR），再按观察到的
   行为选择 API、auth、injection、file、business-logic、recon 或主机方向。
3. `NEXT`: 先查 canonical route 和 `skills/community/registry.json` 的 provenance、
   maturity、license_status；重复主题优先使用现有 `api-security`、`windows-ad`、
   `cloud-k8s`、`pwn-chain`、`supply-chain-security` 等模块。
4. `ACT`: 只读副本、低影响验证和授权对象优先。破坏性写入、批量请求、RCE、反弹
   shell、凭证提取、AD/EDR 绕过、容器/内核逃逸必须有明确 scope 和 lab/authorized
   network profile，不能从导入 playbook 直接执行。
5. `DONE`: 每个结论必须有 Evidence→Finding→Path、会话归因、秘密 liveness、复现
   命令、影响、修复和限制；没有完整链路就标为 hypothesis 或 unverified。

## Topic mapping

| 社区主题 | canonical route |
|---|---|
| recon / attack surface | `pentest-tools` / `attack-chain` |
| REST / GraphQL / BOLA / JWT | `api-security` / `identity-federation` |
| injection / file / logic | `pentest-tools` / `code-audit` |
| AD / Kerberos / ACL / ADCS | `windows-ad` / `attack-chain` |
| cloud / container / K8s | `cloud-k8s` |
| Android / iOS | `apk-reverse` / `mobile-reverse` |
| binary / anti-debug / pwn | `reverse-engineering` / `pwn-chain` |
| LLM / AI-ML | `llm-security` |

`skills/community/hack-skills/` 只保存适配后的参考正文和 provenance；其 `hack` 主
入口、Yak 安装流程和类别索引不作为第二套 router。

需要机器辅助初筛时，可只读运行：

```text
python skills/scripts/community-route.py --hint "<观察到的行为>" --source hack-skills --json
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
- 完整数字与 policy manifest 变更请求见 `docs/community/LOADING-BUDGET.md`。
