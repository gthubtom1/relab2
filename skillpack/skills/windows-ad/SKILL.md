---
name: windows-ad
description: AD/Windows 身份攻击：Kerberos(Kerberoast/AS-REP)、ADCS ESC1-ESC8、BloodHound、NTLM relay、域内提权。用于：域渗透身份枚举、impacket/certipy/nxc、pass-the-hash。
---

# Windows / Active Directory Security

## ACTION REQUIRED（读完后立刻执行）

1. `NOW`: 读取 `../field-journal/precedent-pentest.md`
2. `NOW`: **查经验卡** —— `python skills/scripts/experience-card.py search "<你看到的症状>"`。
   命中就读那张卡的 `invariant` + `decision.action`，并**逐条对照** `scope.appliesWhen`
   与 `scope.stopsWhen`：少一条前提就停用；命中任一停止条件就停。
   历史卡**不替代**当前目标的实测证据。详见 `../experience-cards/INDEX.md`。
3. `NOW`: 域/AD 测试直接执行（含 DC）；投毒/中继这类主动攻击放在枚举出图之后（先看清路再动手）
4. `NOW`: case-init 建案（目标域、网段、产出物）
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
# 示例 impacket / 内置（喂已取得的域凭据，不喂猜的）
nxc smb <range> -u user -p pass
bloodhound-python -d domain.local -u user -p pass -c All -ns <DC>
```

### 2. 常见路径（先图后枪）

```text
□ Kerberoast / AS-REP → 离线破解
□ ACL 滥用（GenericAll/WriteDacl）
□ 委派（非约束/约束/基于资源）
□ AD CS 模板错误 → Certipy
□ 中继：LLMNR/NBT-NS + ntlmrelayx（先抓自己的靶机验证）
```

### 3. 凭证与横向

```text
□ secretsdump / lsassy / mimikatz（每步留 Evidence；完事清理落地的服务/票据）
□ PtH / PtT / 黄金票：先留一份票据备份再打，断了能回
□ 每步写 Evidence；DCSync/黄金票前先想好怎么撤
```

## 工具链

| 工具 | 用途 | 调用口径（输出一律重定向到 evidence 文件再解读） |
|------|------|------|
| BloodHound GUI + `bloodhound-python` / SharpHound | 路径图 | `bloodhound-python -d <dom> -u <u> -p <p> -c All -ns <DC>`，先落 JSON 再导图 |
| Certipy | AD CS 模板枚举与利用 | `certipy find -u <u>@<dom> -p <p> -dc-ip <DC> -vulnerable -stdout` |
| `impacket` 套件 | 横向与凭据（`secretsdump` / `ntlmrelayx` / `GetUserSPNs` / `getST`） | 一条命令一个动作，票据/哈希先落盘 |
| NetExec（`nxc`）/ CrackMapExec | 批量 SMB/LDAP/WinRM 枚举、PtH | `nxc smb <cidr> -u <u> -p <p> --shares` |
| `nmap` | 圈存活域机与端口（88/389/445/5985/9389） | `nmap -p 88,389,445,636,5985,9389 --open <cidr>`，先定靶再上 `nxc` 批量 |
| `curl` | HTTP 型 AD CS Web Enrollment / 中继到 `/certsrv` | `curl -k -u <u>:<p> https://<CA>/certsrv/` 探通，中继时看 HTTP 端是否收 NTLM |
| `mimikatz` / Rubeus | 票据与 LSASS 凭证 | 取完立即备份票据、记下清理动作 |
| `lsassy` | 远程 LSASS dump 取凭证 | 与 `secretsdump` 交叉验证同一账号两处是否都能取 |
| Coercer / Responder | 强制认证 / LLMNR-NBT-NS 投毒 | 先拿自己的靶机验证触发链，再对目标用 |

**动手前先定位工具与通道**（探测层是本机路径的唯一事实源，别用 `Get-Command` 查空就报缺）：

```powershell
. C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1
Resolve-ReverseToolSpec -Name netexec    # 读返回的 Command / Available / Via
Resolve-ReverseToolSpec -Name certipy
```

MCP 型通道不常驻是天性：内网扫描/逆向相关通道先跑
`powershell -NoProfile -ExecutionPolicy Bypass -File skillpack\skills\scripts\mcp-status.ps1`
看「注册了哪些 / 谁在监听 / 怎么起」；`closed` 就按它给的命令自己起，起完重跑确认 `LISTEN`。
**注册 ≠ 在监听**，HTTP 型平时不监听是设计，不是故障 —— 不要因为端口关着就换一把工具硬试。

## 参考

- `references/ad-attack-paths.md`
- `../pentest-tools/references/network-attack-defense.md`
- `../attack-chain/`
- seeds: `../field-journal/seed-005_ad-certipy-esc1.md` `../field-journal/seed-007_ntlm-relay-coercer.md` `../field-journal/seed-013_kerberoasting-spn.md`

## 路由上下文

**上游**: MASTER R24  
**下游**: 报告 `docs-generator`；需 EDR 研究 `edr-bypass-re`  

## 任务完成自检

- [ ] 是否先有图/枚举再有利用？
- [ ] 是否记录可复现命令并脱敏？
- [ ] 是否给每条写操作路径写了回滚/清理动作？
- [ ] Checklist？

---

## When NOT to use（近邻负例）

- 还没有任何域内立足点（无凭据、无 shell、无机器账号） → 用 `../pentest-tools/SKILL.md` 先拿初始立足点
- 目标是 Linux 主机的本地提权（sudo/SUID/内核） → 用 `../kernel-exploit/SKILL.md`
- 打的是 Web SSO / SAML / OIDC 联邦信任链 → 用 `../identity-federation/SKILL.md`
- 初始访问靠钓鱼邮件或附件，人还没进内网 → 用 `../email-security/SKILL.md`
- 要逆向 Rubeus / SharpHound 这类 .NET 工具本体（改 banner、去特征） → 用 `../dotnet-reverse/SKILL.md`
- 目标是云侧身份（Entra ID / 工作负载身份 / 实例元数据） → 用 `../cloud-k8s/SKILL.md`
- 已拿到域管，卡点是落地免杀与驻留存活 → 用 `../edr-bypass-re/SKILL.md`
- 要做的是把外网到域控串成一条完整链（不专注身份面） → 用 `../attack-chain/SKILL.md`

## When to Pivot

信号与判据见 `../ops/skill-pivot-contract.md`。本技能去向：

| 触发证据 | 换到 |
|---|---|
| `certipy find -vulnerable` 输出里出现 ESC1/ESC8，且模板 `Enrollment Rights` 含 `Domain Users` 这类非特权主体 | 走本卡 AD CS 分支申请票据并留取证；完整链交 `../attack-chain/SKILL.md` |
| LLMNR/NBT-NS 抓到响应，但 `ntlmrelayx` 连续 2 次被 `STATUS_ACCESS_DENIED` / `SMB signing required` 挡回 | 该协议面已被签名/EPA 封死，不硬试第 3 次；转 `../pentest-tools/SKILL.md` 换协议面（HTTP/LDAPS/DNS）与中继目标 |
| `secretsdump` 只吐出本地 SAM/LSA hash，没有域管凭据，PtH 试过的机器全返回 `STATUS_LOGON_FAILURE` | 本地凭据面已尽，用 PtH 结果枚举可达面后交 `../attack-chain/SKILL.md` |
| 落地的 loader/服务在目标机 2 分钟内被杀（进程消失、无回连、EDR 日志里有查杀记录） | `../edr-bypass-re/SKILL.md`（先解决落地存活，不要再试第二条攻击路径） |
| `bloodhound-python -c All` 跑了 2 轮、换过 `-ns` 与凭据，图里仍只有 `MemberOf`/`CanRDP` 读边，无 `GenericAll`/`WriteDacl`/`AddKeyCredentialLink` | ACL 面已穷尽，转 `../identity-federation/SKILL.md` 把联邦/云身份当新面，或回 `../pentest-tools/SKILL.md` 找新立足点 |
| Kerberoast 拿到 SPN 票据 hash，`hashcat -m 13100` 用常见字典 + 规则跑 2 小时未出 | 停离线爆破，转 AS-REP/委派面（本卡）或直接用票据走 `../attack-chain/SKILL.md` |
| DC 上 `nxc smb --shares` 读得到 SYSVOL 但没有写权限，且 `certipy find` 报 CA 未启用 `EDITF_ATTRIBUTESUBJECTALTNAME2` | ADCS 走不通，回 `../pentest-tools/SKILL.md` 找别的中继/委托面 |

## 定义完成

本技能产出算「完成」的**外部可观测**条件（不许写形容词）：

- 攻击路径图（BloodHound 导出 + Mermaid）落盘
- 每条边有实测证据（不是理论可达）：写清「哪条命令、返回什么」；只有 BloodHound 边推断的边记 `low`，不进 `confirmed`
- 提权/横向的 PoC 命令落盘可重放，且在同一 OS build / 同一 CA 模板上**连续 3 次命中**；两次命中不算 confirmed
- 每条写操作路径（改 ACL、发证书、DCSync、黄金票）都配了一条回滚/清理动作：撤销的证书申请、删掉落地的服务、清掉的票据缓存路径 —— 没有清理动作的攻击路径不算交付

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
