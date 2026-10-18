---
name: email-security
description: 邮件安全与钓鱼分析：Received 链、SPF/DKIM/DMARC 校验、BEC 欺诈。用于：这封邮件是钓鱼吗、帮我查下 SPF 配对没、BEC 诈骗长啥样。
---

# Email Security & Phishing Analysis

## ACTION REQUIRED（读完后立刻执行）

> **手上只有"现象"、不知道该读哪一篇？** 本技能的技术正文有症状索引：先按现象查 [`../field-journal/KB-INDEX.md`](../field-journal/KB-INDEX.md)（现象 → 该读哪一篇技术文档），再读那一篇。**别按目录翻。** **什么时候该回读**（迷茫 / 换完技能 / 文档和本机对不上 …）见 [`../ops/kb-consult-contract.md`](../ops/kb-consult-contract.md) —— 它不是"开局读一次"，是**反复回读**。（来源与改编规则见同目录 `KB-SOURCES.md`）

1. `NOW`: **查经验卡** —— `python skillpack/skills/scripts/experience-card.py search "<你看到的症状>"`。
   命中就读那张卡的 `invariant` + `decision.action`，并**逐条对照** `scope.appliesWhen`
   与 `scope.stopsWhen`：少一条前提就停用；命中任一停止条件就停。
   历史卡**不替代**当前目标的实测证据。详见 `../experience-cards/INDEX.md`。
2. `NOW`: 先分清两条路 —— 分析样本邮件 / 租户配置评审
3. `NOW`: 样本只在自建测试邮箱里重放（投给真实用户会污染分析面与收件人）
4. `ACT`: 头认证 → 内容/URL → 附件沙箱 → 租户控制面建议

## 适用场景

- 钓鱼邮件拆解与 IOC
- SPF/DKIM/DMARC 配置评估
- BEC 商务邮件欺诈模式
- OAuth 应用钓鱼 / 邮箱令牌滥用（联合 llm/cloud 身份）
- 安全意识演练设计

## 工作流

```text
□ 完整原始头：Received 链、From/Return-Path 一致性
□ SPF/DKIM/DMARC 对齐结果
□ URL 沙箱与附件静态（联合 malware-analysis）
□ 仿冒品牌与回复地址差异
□ 租户：反钓鱼策略、外部标记、MFA、OAuth app 同意
```

## 工具链

| 工具 | 干什么 | 真实调用口径 |
|------|--------|--------------|
| 邮件客户端「查看源」/ `curl` | 取完整原始头 | 对存盘的 `.eml` 做头解析；`curl` 只用于拉取邮件里 URL 的静态响应 |
| `nmap` | 收件/发件 MTA 端口与 banner | `nmap -p 25,587,465 --script smtp-commands <mta>` |
| `tshark` | SMTP 会话抓包与头字段提取 | `tshark -r mail.pcap -Y smtp -T fields -e smtp.req.parameter` |
| `yara` | 附件（宏/OLE）静态规则与 IOC 匹配 | 先对附件过一遍宏/OLE 规则，命中再交 `../malware-analysis/SKILL.md` |
| `sigma` | IOC 可检测化（网关/终端规则） | 把发件域、URL、附件哈希写成 sigma 规则交 `../threat-hunting/SKILL.md` |
| `Burp` | 邮件里链接指向的自家应用取证 | 只读重放跳转链，不主动打点 |
| `mitmdump` | 链接落地页/重定向链脚本化记录 | `mitmdump -w mail_urls.flow` |

探测层（唯一路径入口）：`. <仓根>\skillpack\skills\scripts\lib\Bootstrap.ps1` → `Resolve-ReverseToolSpec -Name tshark`。
`Get-Command` 查空 ≠ 缺工具（四级递进：env → PATH → `_map.json` → 工具根扫描）。

## 参考

- `references/email-auth-checklist.md`
- `../malware-analysis/` `../attack-chain/`（钓鱼阶段） `../windows-ad/`（令牌）

## 路由上下文

**上游**: MASTER R36  
**提醒**: 测试邮件优先打自己的自建 MX 与测试账号；对外群发会进对方反垃圾/威胁情报系统，污染自己的 IOC 归因

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

- 目标是邮件网关/OWA 的 Web 界面漏洞 → 用 `../pentest-tools/SKILL.md`
- 要分析的是恶意附件本体（免杀、行为、家族） → 用 `../malware-analysis/SKILL.md`
- 目标是邮件服务器主机的 OS/域层问题 → 用 `../windows-ad/SKILL.md`
- 目标是钓鱼背后的攻击者基础设施与归因 → 用 `../threat-intelligence/SKILL.md`
- 目标是邮箱账号被盗后的云身份/令牌滥用 → 用 `../identity-federation/SKILL.md`
- 目标是把 IOC 变成 SIEM/EDR 检测规则 → 用 `../threat-hunting/SKILL.md`

## When to Pivot

信号与判据见 `../ops/skill-pivot-contract.md`。本技能去向：

| 触发证据 | 换到 |
|---|---|
| 附件是真宏文档/脚本（`olevba`/`yara` 命中 >2 条 `AutoOpen`/`WScript.Shell` 规则） | `../malware-analysis/SKILL.md` |
| 发件域 SPF 为 `~all` 或缺失、DKIM 无签名，发信实测返回 250 并落到目标收件箱 | 评估伪造链后转 `../attack-chain/SKILL.md` |
| 邮件里的 URL 落到自家域名/应用，且带跟踪参数指向内部接口 | `../api-security/SKILL.md` |
| `Received` 链里出现 X/Twitter/Telegram 等平台中转，或线索指向外部平台账号 | `../threat-intelligence/SKILL.md` |
| 同一发件人 30 分钟内两次投递，第二次 `Authentication-Results` 返回 `pass`（配置在改） | 重取样本头做差集；差异指向内部 MTA 配置则转 `../pentest-tools/SKILL.md` |
| 邮箱 OAuth 应用同意被滥用（恶意 app 拿到 `Mail.Read`） | `../identity-federation/SKILL.md` |
| 需要把 IOC 落成网关/EDR 规则 | `../threat-hunting/SKILL.md` |

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
- 硬判据：SPF/DKIM/DMARC 结论必须落到具体 `v=spf1`/`p=`/`_dmarc` TXT 的实测解析结果；只凭"看上去配了"一律记 `low`
- `low`：仅解析 DNS 记录推断可以伪造
