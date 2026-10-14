---
name: windows-ad
description: 授权 AD/Windows 身份攻击：Kerberos(Kerberoast/AS-REP)、ADCS ESC1-ESC8、BloodHound、NTLM relay、域内提权。用于：域渗透身份枚举、impacket/certipy/nxc、pass-the-hash。
---

# Windows / Active Directory Security

## ACTION REQUIRED（读完后立刻执行）

1. `NOW`: 读取 `../field-journal/precedent-pentest.md`
2. `NOW`: **查经验卡** —— `python skills/scripts/experience-card.py search "<你看到的症状>"`。
   命中就读那张卡的 `invariant` + `decision.action`，并**逐条对照** `scope.appliesWhen`
   与 `scope.stopsWhen`：少一条前提就停用；命中任一停止条件就停。
   历史卡**不替代**当前目标的实测证据。详见 `../experience-cards/INDEX.md`。
3. `NOW`: 域/AD 测试直接执行（含 DC）；**仅在 scope 明确后**才做投毒/中继等主动攻击
4. `NOW`: case-init；network_profile 与禁止动作写清
5. `NEXT`: `../TOOLS.md`（impacket/certipy/bloodhound 等常手动）
6. `ACT`: 从身份枚举与 BloodHound 图开始，不先上破坏性利用

## 适用场景

- 域渗透、Kerberoasting、AS-REP、委派
- AD CS（ESC1–ESC8 等）证书攻击
- BloodHound / SharpHound 攻击路径
- NTLM Relay / Coercer 强制认证
- 本地提权到域路径（Potato 等作为跳板）

## 与 attack-chain 关系

- **多阶段从外网到域控** → PRIMARY 可仍是 `attack-chain/`，本 skill 为 **AD 专科**
- **已在域内专注身份** → PRIMARY = 本 skill

## 工作流

### 1. 枚举

```bash
# 示例 Impacket / 内置（需凭据与授权）
nxc smb <range> -u user -p pass
bloodhound-python -d domain.local -u user -p pass -c All -ns <DC>
```

### 2. 常见路径（先图后枪）

```text
□ Kerberoast / AS-REP → 离线破解
□ ACL 滥用（GenericAll/WriteDacl）
□ 委派（非约束/约束/基于资源）
□ AD CS 模板错误 → Certipy
□ 中继：LLMNR/NBT-NS + ntlmrelayx（确认授权）
```

### 3. 凭证与横向

```text
□ secretsdump / lsassy / mimikatz（严格授权与清理）
□ PtH / PtT / 黄金票仅在授权红队范围
□ 每步写 Evidence；高危等用户确认
```

## 工具链

| 工具 | 用途 |
|------|------|
| BloodHound / SharpHound | 路径图 |
| Certipy | AD CS |
| Impacket / NetExec | 横向与枚举 |
| Rubeus / Mimikatz | 票据与凭证（授权） |
| Coercer / Responder | 强制认证 / 投毒 |

## 参考

- `references/ad-attack-paths.md`
- `../pentest-tools/references/network-attack-defense.md`
- `../attack-chain/`
- seeds: `../field-journal/seed-005_ad-certipy-esc1.md` `../field-journal/seed-007_ntlm-relay-coercer.md` `../field-journal/seed-013_kerberoasting-spn.md`

## 路由上下文

**上游**: MASTER R24  
**下游**: 报告 `docs-generator`；需 EDR 研究 `edr-bypass-re`  
**MUST NOT**: 对本机 / lab 以外的生产域做 DCSync / 黄金票据（本卡研究默认在隔离 lab）

## 任务完成自检

- [ ] 是否先有图/枚举再有利用？
- [ ] 是否记录可复现命令并脱敏？
- [ ] 是否遵守 scope 禁止项？
- [ ] Checklist？

---

## When NOT to use（近邻负例）

- 还没有任何域内立足点（无凭据/无 shell） → 用 `../pentest-tools/SKILL.md`
- 目标是 Linux 环境 → 用 `../kernel-exploit/SKILL.md`
- 要打的是 Web SSO 联邦 → 用 `../identity-federation/SKILL.md`
- 前置条件：**域不属于你** → 只做只读枚举（BloodHound 采集），不做写操作

## When to Pivot

信号与判据见 `../ops/skill-pivot-contract.md`。本技能去向：

| 触发证据 | 换到 |
|---|---|
| 拿到域管，要找出口与持久化评估 | `../edr-bypass-re/SKILL.md` |
| 发现 AD CS 配置错误（ESC1-ESC8） | `../attack-chain/SKILL.md` |
| 发现 NTLM 可中继的目标 | `../pentest-tools/SKILL.md` |

## 定义完成

本技能产出算「完成」的**外部可观测**条件（不许写形容词）：

- 攻击路径图（BloodHound 导出 + Mermaid）落盘
- 每条边有实测证据（不是理论可达）
- 提权/横向的 PoC 命令落盘可重放

## 输出契约

```
FACT:       <观察，带来源：命令 / 文件:行 / Evidence ID>
HYPOTHESIS: <可测试断言 + confidence: high|medium|low>（状态见 `../ops/binary-model.md`）
QUESTION:   <当前最大不确定点>
NEXT:       <继续 | 换技能 | 停止（附成本判据）>
```

## 置信度词表

词表见 `../ops/confidence-vocabulary.md`。本技能特有判据：

- `confirmed`：凭据可用性有实际认证成功证据（不是哈希格式判断）
- `low`：仅凭 BloodHound 边推断可达，未实际执行
