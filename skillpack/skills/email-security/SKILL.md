---
name: email-security
description: Email security review — 当用户收到可疑邮件或要查域名邮箱配置，或说“这封邮件是钓鱼吗”“帮我查下SPF配对没”“BEC诈骗长啥样”时使用。Use when phishing analysis, SPF/DKIM/DMARC check.
---

# Email Security & Phishing Analysis

## ACTION REQUIRED（读完后立刻执行）

1. `NOW`: 确认授权（分析样本邮件 / 租户配置评审）
2. `NOW`: 不向真实用户二次投递恶意样本
3. `ACT`: 头认证 → 内容/URL → 附件沙箱 → 租户控制面建议

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
> **仅限 CTF 靶场 / AWD 赛场 / 已授权环境**。

### `references/auth-records/` — 邮件伪造（SPF / DKIM / DMARC / 头注入）（1 篇）

- `references/auth-records/02-email-spoofing.md`

### `references/` — 根目录


