---
name: identity-federation
description: 联邦身份与 SSO 鉴权测试：SAML 断言篡改、OIDC/OAuth2 错配、redirect_uri/state/PKCE 缺陷、token 混淆。用于：测 SSO、SAML 签名、IdP/SP 元数据。
---

# Identity Federation (SAML / OIDC / OAuth)

## ACTION REQUIRED（读完后立刻执行）

> **手上只有"现象"、不知道该读哪一篇？** 本技能的技术正文有症状索引：先按现象查 [`../field-journal/KB-INDEX.md`](../field-journal/KB-INDEX.md)（现象 → 该读哪一篇技术文档），再读那一篇。**别按目录翻。** **什么时候该回读**（迷茫 / 换完技能 / 文档和本机对不上 …）见 [`../ops/kb-consult-contract.md`](../ops/kb-consult-contract.md) —— 它不是"开局读一次"，是**反复回读**。（来源与改编规则见同目录 `KB-SOURCES.md`）

1. `NOW`: 读 `../field-journal/precedent-pentest.md`；SSO 链路从一份公开元数据（`/.well-known/openid-configuration`）开始
2. `NOW`: **查经验卡** —— `python skillpack/skills/scripts/experience-card.py search "<你看到的症状>"`。
   命中就读那张卡的 `invariant` + `decision.action`，并**逐条对照** `scope.appliesWhen`
   与 `scope.stopsWhen`：少一条前提就停用；命中任一停止条件就停。
   历史卡**不替代**当前目标的实测证据。详见 `../experience-cards/INDEX.md`。
3. `NOW`: 口令尝试只打自建测试账号；对真实用户账户做锁定/爆破会把 SSO 链路整条打瘫（自伤）
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

| 工具 | 干什么 | 真实调用口径 |
|------|--------|--------------|
| `Burp`（+ SAML Raider / OAuth 插件） | 断言编辑、重放、重定向链 | 抓 `SAMLResponse` 后改 `NameID`/`AttributeStatement` 再重放，看 SP 是否新建会话 |
| `curl` | 拉公开元数据做基线 | `curl -s https://<idp>/.well-known/openid-configuration` 与 SAML metadata 各存一份 |
| `jwt_tool` | JWT/OIDC token 段 | `jwt_tool <jwt> -T` 试 alg 混淆与 `kid` 注入，先试再改 |
| `hashcat` | 对称签名密钥/弱 sig 爆破 | `hashcat -m 16500 <jwt> <wl>`；HS256 命中即证明可自签 |
| `ffuf` | IdP / SP 端点枚举 | 对 issuer 下枚举 `/saml/`、`/oauth/authorize`、`/adfs/ls` |
| `mitmdump` | 脚本化批量改重定向参数 | `mitmdump -s redirect_mutate.py` 跑 `redirect_uri`/`state` 变体 |
| `reqable` | 桌面端 SSO 客户端的 HTTP 抓包 | 客户端无浏览器 DevTools 时用它取证 |
| `nmap` | IdP 端点与端口存活 | 只做可达性确认，不做口令爆破 |

探测层（唯一路径入口）：`. C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1` → `Resolve-ReverseToolSpec -Name Burp`。
`Get-Command` 查空 ≠ 缺工具（四级递进：env → PATH → `_map.json` → 工具根扫描）。

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
- 目标是 OAuth 客户端源码里的逻辑缺陷 → 用 `../code-audit/SKILL.md`
- 目标是 SSO 之后业务应用的越权（IDOR/BOLA） → 用 `../api-security/SKILL.md`
- 目标是云厂商控制台联合登录到云资源面 → 用 `../cloud-k8s/SKILL.md`
- 目标是邮件客户端/OAuth 应用同意钓鱼 → 用 `../email-security/SKILL.md`

## When to Pivot

信号与判据见 `../ops/skill-pivot-contract.md`。本技能去向：

| 触发证据 | 换到 |
|---|---|
| 改 `NameID`/属性后重放，SP 返回新会话且断言签名校验被跳过（响应 302 带 `Set-Cookie`） | `../api-security/SKILL.md` 评估拿到会话后的权限面 |
| 自签或未知 CA 的证书被 SP 接受（元数据 `SigningCertificate` 与实测签名公钥对不上） | `../attack-chain/SKILL.md` 构造伪造断言链 |
| 断言 `AttributeStatement` 里带 `admin`/高权角色，SP 直接映射成高权会话 | 评估下游 API 面，转 `../api-security/SKILL.md` |
| IdP 元数据里发现多租户共用 issuer，且 `audience` 未严格绑定 | 逐租户验证断言串用，跨租户能进则转 `../attack-chain/SKILL.md` |
| `redirect_uri` 通配 / `state` 未绑定 / PKCE 缺失，连续两次（间隔 >1 分钟）重放都能返回 code | 授权码劫持面转 `../api-security/SKILL.md` |
| JWT 用 `alg:none` 或弱 HS256，且 `hashcat -m 16500` 在 5 分钟内命中密钥 | `../api-security/SKILL.md` 的 JWT 段 |
| 抓到的报文里没有标准 SAML/OIDC 字段（加密或私有二进制 SSO 协议） | `../protocol-reverse/SKILL.md` 做字段还原 |

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
- 硬判据：SSO 每一跳都要写清信任假设（谁签、谁验、绑没绑 audience）；缺任一端实测报文的跨跳结论只能记 `low`
- `low`：仅从元数据里看到签名算法为 none/弱算法
