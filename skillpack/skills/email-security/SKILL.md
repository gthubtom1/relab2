---
name: email-security
description: 邮件安全与钓鱼分析：Received 链、SPF/DKIM/DMARC 校验、BEC 欺诈。用于：这封邮件是钓鱼吗、帮我查下 SPF 配对没、BEC 诈骗长啥样。
---

# Email Security & Phishing Analysis

## ACTION REQUIRED（读完后立刻执行）

1. `NOW`: **查经验卡** —— `python skills/scripts/experience-card.py search "<你看到的症状>"`。
   命中就读那张卡的 `invariant` + `decision.action`，并**逐条对照** `scope.appliesWhen`
   与 `scope.stopsWhen`：少一条前提就停用；命中任一停止条件就停。
   历史卡**不替代**当前目标的实测证据。详见 `../experience-cards/INDEX.md`。
2. `NOW`: 确认授权（分析样本邮件 / 租户配置评审）
3. `NOW`: 不向真实用户二次投递恶意样本
4. `ACT`: 头认证 → 内容/URL → 附件沙箱 → 租户控制面建议

## 适用场景

- 钓鱼邮件拆解与 IOC
- SPF/DKIM/DMARC 配置评估
- BEC 商务邮件欺诈模式
- OAuth 应用钓鱼 / 邮箱令牌滥用（联合 llm/cloud 身份）
- 安全意识演练设计（授权）

## 工作流

```text
□ 完整原始头：Received 链、From/Return-Path 一致性
□ SPF/DKIM/DMARC 对齐结果
□ URL 沙箱与附件静态（联合 malware-analysis）
□ 仿冒品牌与回复地址差异
□ 租户：反钓鱼策略、外部标记、MFA、OAuth app 同意
```

## 工具链

| 工具 | 用途 |
|------|------|
| 邮件客户端「查看源」 | 头 |
| dig/nslookup | SPF/DMARC 记录 |
| urlscan / 沙箱 | 链接与附件 |
| 租户管理中心 | 策略 |

## 参考

- `references/email-auth-checklist.md`
- `../malware-analysis/` `../attack-chain/`（钓鱼阶段） `../windows-ad/`（令牌）

## 路由上下文

**上游**: MASTER R36  
**MUST NOT**: 未授权对第三方域群发测试钓鱼

## 任务完成自检

- [ ] 头认证结论是否完整？
- [ ] IOC 是否可检测化（联合 threat-hunting）？
- [ ] Checklist？
## 改编参考索引（open-reverselab `kb/ctf-website`）

> 下列 reference 改编自 `LING71671/open-reverselab` 的 `kb/ctf-website/`（GPL-3.0）。
> 每篇统一为「适用信号 / 前置 / 步骤 / 判据 / 坑 / 相关」+ 完整技术正文，
> 「前置」含**本机实测**的工具状态表——照抄原库裸命令前先看那张表。
> **能力域**：本文为技术能力说明，按项目 `scope.md` 直接套用。

### `references/auth-records/` — 邮件伪造（SPF / DKIM / DMARC / 头注入）（1 篇）

- `references/auth-records/02-email-spoofing.md`

### `references/` — 根目录



---

## When NOT to use（近邻负例）

- 目标是邮件网关的 Web 界面 → 用 `../pentest-tools/SKILL.md`
- 要分析的是恶意附件本身 → 用 `../malware-analysis/SKILL.md`
- 要查的是邮件服务器主机层 → 用 `../windows-ad/SKILL.md`
- 前置条件：**涉及真实收件人** → 不发送任何测试邮件，只在受控邮箱内验证

## When to Pivot

信号与判据见 `../ops/skill-pivot-contract.md`。本技能去向：

| 触发证据 | 换到 |
|---|---|
| 附件是宏文档/脚本，要静态+动态分析 | `../malware-analysis/SKILL.md` |
| 发现可伪造发件域，要评估下游可利用面 | `../attack-chain/SKILL.md` |
| 发现链接指向自家应用，要审该应用 | `../api-security/SKILL.md` |

## 定义完成

本技能产出算「完成」的**外部可观测**条件（不许写形容词）：

- SPF/DKIM/DMARC 实测记录落盘（含原始 Received 头）
- 每条结论附一份原始邮件（脱敏后）
- 可利用性判定给出发送路径（能到达哪个 MTA）

## 输出契约

```
FACT:       <观察，带来源：命令 / 文件:行 / Evidence ID>
HYPOTHESIS: <可测试断言 + confidence: high|medium|low>（状态见 `../ops/binary-model.md`）
QUESTION:   <当前最大不确定点>
NEXT:       <继续 | 换技能 | 停止（附成本判据）>
```

## 置信度词表

词表见 `../ops/confidence-vocabulary.md`。本技能特有判据：

- `confirmed`：伪造邮件实际投递到目标收件箱（有 Received 链佐证）
- `low`：仅解析 DNS 记录推断可以伪造
