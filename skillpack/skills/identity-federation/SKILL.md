---
name: identity-federation
description: 联邦身份与 SSO 授权测试：SAML 断言篡改、OIDC/OAuth2 错配、redirect_uri/state/PKCE 缺陷、token 混淆。用于：测 SSO、SAML 签名、IdP/SP 元数据。
---

# Identity Federation (SAML / OIDC / OAuth)

## ACTION REQUIRED（读完后立刻执行）

1. `NOW`: 读取 precedent-pentest；SSO 测试账号与 IdP/SP 范围入 scope
2. `NOW`: **查经验卡** —— `python skills/scripts/experience-card.py search "<你看到的症状>"`。
   命中就读那张卡的 `invariant` + `decision.action`，并**逐条对照** `scope.appliesWhen`
   与 `scope.stopsWhen`：少一条前提就停用；命中任一停止条件就停。
   历史卡**不替代**当前目标的实测证据。详见 `../experience-cards/INDEX.md`。
3. `NOW`: 禁止锁定真实用户账户的暴力尝试
4. `NEXT`: 抓包工具与文档（元数据 URL）
5. `ACT`: 协议流映射 → 常见错配 → 验证

## 适用场景

- SAML Response 签名/断言篡改面（经典缺陷模式）
- OIDC 隐式/授权码 + PKCE 缺失
- redirect_uri / state / nonce 问题
- IdP 与 SP 元数据、多租户 issuer 混淆
- 与 `api-security` JWT 攻击互补（本 skill 偏联邦与 SSO 流）

## 工作流

```text
□ 画清：User → SP → IdP → Token → SP
□ 收集：/.well-known/openid-configuration、SAML metadata
□ 检查：redirect_uri 精确匹配、state 绑定、PKCE
□ 检查：SAML 签名覆盖范围、algorithm 降级
□ 会话固定与登出失效
```

## 工具链

| 工具 | 用途 |
|------|------|
| Burp + SAML Raider 等 | 断言编辑（授权） |
| jwt_tool | JWT 段 |
| 浏览器 DevTools | 重定向链 |
| IdP 管理日志 | 审计 |

## 参考

- `references/sso-flow-checklist.md`
- `../api-security/` `../windows-ad/`（企业 IdP）

## 路由上下文

**上游**: MASTER R37  
**下游**: 纯 API JWT → api-security；云 IdP → cloud-k8s

## 任务完成自检

- [ ] 是否映射完整 SSO 流？
- [ ] 每个 Finding 是否有复现与影响？
- [ ] Checklist？
## 改编参考索引（open-reverselab `kb/ctf-website`）

> 下列 reference 改编自 `LING71671/open-reverselab` 的 `kb/ctf-website/`（GPL-3.0）。
> 每篇统一为「适用信号 / 前置 / 步骤 / 判据 / 坑 / 相关」+ 完整技术正文，
> 「前置」含**本机实测**的工具状态表——照抄原库裸命令前先看那张表。
> **能力域**：本文为技术能力说明，按项目 `scope.md` 直接套用。

### `references/oauth-saml/` — OAuth / OIDC / SAML / Session 固定与 SSO 劫持（4 篇）

- `references/oauth-saml/oauth-sso.md`
- `references/oauth-saml/saml-attacks.md`
- `references/oauth-saml/01-oauth-attack-chains.md`
- `references/oauth-saml/02-session-fixation-attacks.md`

### `references/` — 根目录



---

## When NOT to use（近邻负例）

- 目标是本地 JWT 校验，不涉及 IdP 联邦 → 用 `../api-security/SKILL.md`
- 目标是 Windows 域内 Kerberos/NTLM（不是 Web SSO） → 用 `../windows-ad/SKILL.md`
- 目标是 OAuth 客户端本身而非 IdP 配置 → 用 `../code-audit/SKILL.md`
- 前置条件：IdP 属于第三方组织 → 只做配置观察与公开元数据检查

## When to Pivot

信号与判据见 `../ops/skill-pivot-contract.md`。本技能去向：

| 触发证据 | 换到 |
|---|---|
| 发现 assertion 可被篡改/重放 | `../api-security/SKILL.md` |
| 发现签名证书可控（自签被接受） | `../attack-chain/SKILL.md` |
| SAML 断言里带高权角色，要评估下游影响 | `../api-security/SKILL.md` |

## 定义完成

本技能产出算「完成」的**外部可观测**条件（不许写形容词）：

- 联邦流程逐跳落盘（IdP → SP → 会话），标注每跳的信任假设
- 每条缺陷有实际构造的 assertion/请求与响应
- 修复对应到具体配置（不是「加强校验」）

## 输出契约

```
FACT:       <观察，带来源：命令 / 文件:行 / Evidence ID>
HYPOTHESIS: <可测试断言 + confidence: high|medium|low>（状态见 `../ops/binary-model.md`）
QUESTION:   <当前最大不确定点>
NEXT:       <继续 | 换技能 | 停止（附成本判据）>
```

## 置信度词表

词表见 `../ops/confidence-vocabulary.md`。本技能特有判据：

- `confirmed`：构造的 assertion 被 SP 接受且有会话建立实测
- `low`：仅从元数据里看到签名算法为 none/弱算法
