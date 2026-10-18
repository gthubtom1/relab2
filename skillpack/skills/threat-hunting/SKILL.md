---
name: threat-hunting
description: 威胁狩猎与检测工程：SIEM/EDR 假说查询、Sysmon 事件关联、Sigma/YARA 规则。用于：找 LOTL 横向、IOC 落地检测规则、验证规则。
---

# Threat Hunting & Detection Engineering

## ACTION REQUIRED（读完后立刻执行）

1. `NOW`: **查经验卡** —— `python skillpack/skills/scripts/experience-card.py search "<你看到的症状>"`。
   命中就读那张卡的 `invariant` + `decision.action`，并**逐条对照** `scope.appliesWhen`
   与 `scope.stopsWhen`：少一条前提就停用；命中任一停止条件就停。
   历史卡**不替代**当前目标的实测证据。详见 `../experience-cards/INDEX.md`。
2. `NOW`: 确认蓝队/狩猎授权与数据源范围（SIEM、EDR 导出）
3. `NOW`: 明确假说（hypothesis）再查数，避免无脑刷告警
4. `NEXT`: 工具与数据接入方式
5. `ACT`: 假说 → 查询 → 验证 → 规则化

## 适用场景

- 威胁狩猎（hypothesis-driven）
- Sigma / YARA 检测工程
- 告警调优、误报分析
- 与 `malware-analysis/`：样本侧 IOC → 本 skill 落地检测
- 与 `digital-forensics/`：案件伪影 → 横向狩猎

## 工作流

### 1. 建假说

```text
例：攻击者用 living-off-the-land 做横向
→ 数据源：Sysmon 1/3/10、Windows Security 4624/4648
→ 成功标准：发现异常父进程或罕见账户日志源
```

### 2. 查询与堆叠

```text
□ 基线：正常管理员行为时段与主机
□ 异常：新服务、编码 PowerShell、异常出站
□ 关联：同账号多主机短时登录
```

### 3. 规则化

```yaml
# Sigma 骨架见 malware-analysis；本 skill 强调：
# - 误报面
# - 数据源字段映射
# - 响应 playbook 链接
```

### 4. 验证

```text
□ 原子测试（Atomic Red Team）先在本机/lab 跑，确认日志看得见再上生产
□ 回放历史日志验证召回
```

## 工具链

| 工具 | 干什么 | 真实调用口径 / 判据 |
|------|--------|----------------------|
| `sigma` | 把假说落成可移植规则（Sigma CLI / pySigma 转后端） | `sigma convert -t <backend> rule.yml`；规则里必须写明字段映射与误报面 |
| `yara` | 落地文件 / 内存 IOC 匹配 | `yara -r rules_index.yar <dir>`；单文件吃规则，整库靠 `*_index.yar` 串 |
| `tshark` / `Wireshark` | 从 PCAP / netflow 旁证出站与横向 | `tshark -r x.pcap -Y 'dns or tls' -T fields -e ip.dst` |
| `Volatility` / `vol3` | 只读内存侧核对（进程树、网络连接） | `vol3 -f mem.dmp windows.pslist`；与磁盘侧不一致时先对齐采集时刻 |
| `nmap` | 出站目标与内网暴露面核对 | 只扫授权范围；生产网不做扫描试验场 |
| `curl` | 富化前先看外部源可达性与返回码 | `curl -sSI <url>`；外部源不通记依赖不可用，不伪造结论 |

探测层（唯一路径入口）：`. <仓根>\skillpack\skills\scripts\lib\Bootstrap.ps1` → `Resolve-ReverseToolSpec -Name sigma`（同理可查 `yara` / `tshark`）。
本机另跑 `mcp-status.ps1` 看 MCP 通道谁在监听；注册 ≠ 在监听。

数据源口径：Sysmon EID 1/3/11/13 是主链，Windows Security 4624/4648 是旁链；EDR 导出与 Zeek 网络流是**换源方向**，不是并列刷。

## 参考

- `references/hunting-loop.md`
- `../malware-analysis/references/yara-sigma-rules.md`
- `../digital-forensics/`

## 路由上下文

**上游**: MASTER R27  
**下游**: 确认入侵 → forensics；恶意样本 → malware-analysis  
**提醒**: 攻击模拟默认在本机 / lab 跑；生产环境验证先做检测面可见性（Sysmon/EDR 日志到不到），别拿生产当试验场

## 任务完成自检

- [ ] 是否有明确假说与结论？
- [ ] 规则是否注明误报与数据源？
- [ ] Checklist？

---

## When NOT to use（近邻负例）

- 要分析的是样本本体（静态 / 动态 / 家族） → 用 `../malware-analysis/SKILL.md`
- 要做的是磁盘 / 内存取证与证据保全 → 用 `../digital-forensics/SKILL.md`
- 要收集的是外部威胁情报与归属 → 用 `../threat-intelligence/SKILL.md`
- 要评估的是规则落点后的域内身份与权限面 → 用 `../windows-ad/SKILL.md`
- 要的是完整攻击路径的影响面评估 → 用 `../attack-chain/SKILL.md`
- 要写的是规则配套的对外报告 → 用 `../docs-generator/SKILL.md`

> **工程前提**：查询生产 SIEM 前先确认查询范围与配额，避免拖垮日志平台；攻击模拟默认在本机 / lab，先确认检测面日志到得到，别拿生产当试验场。

## When to Pivot

信号与判据见 `../ops/skill-pivot-contract.md`。本技能去向：

| 触发证据 | 换到 |
|---|---|
| Sysmon EID 1/3 与 EID 11 在同主机 10 分钟内形成投递→执行链闭环，假说命中 | `../malware-analysis/SKILL.md` 做样本确认 |
| 假说命中且确认外部 C2 通联，需要保留易失证据（内存 / 活动连接） | `../digital-forensics/SKILL.md` 固定易失面 |
| Sysmon EID 3 出站目标的域名 / 哈希在本地情报里为空，需要外部归属 | `../threat-intelligence/SKILL.md` |
| 发现 PsExec / wmiexec / mimikatz 等横向工具落地（EID 1 + 4624 类型 3） | `../windows-ad/SKILL.md`；已构成完整攻击路径则 `../attack-chain/SKILL.md` |
| 同一假说连续两轮（每轮约 30 分钟）零命中 | 换数据源（EDR → Sysmon → Zeek 网络流），不是改查询语硬凑命中 |
| 单批次日志 >500 行未收敛、告警率 >80% 是已知基线行为 | 先做基线统计（按主机 / 账号分桶）再下结论，别直接调检测阈值 |

## 定义完成

本技能产出算「完成」的**外部可观测**条件（不许写形容词）：

- 假设清单 + 对应查询语句 + 结果落盘
- 每条检测规则在实际数据上验证过「能触发且不误报」
- 规则文件路径 + 触发样本证据

## 输出契约

```
FACT:       <观察，带来源：命令 / 文件:行 / Evidence ID>
HYPOTHESIS: <可测试断言 + confidence: high|medium|low>（状态见 `../ops/binary-model.md`）
QUESTION:   <当前最大不确定点>
NEXT:       <继续 | 换技能 | 停止（附成本判据）>
```

## 置信度词表

词表见 `../ops/confidence-vocabulary.md`。本技能特有判据：

- `confirmed`：规则在真实数据上实测触发，且控制组不误报
- 硬判据：假说结论必须落到具体 EID + 字段值（例：EID 1 `ParentImage` 指向非常规办公进程），或落到规则的 FP/FN 计数；只写「看起来可疑」一律记 `low`
- `low`：规则只在理论上能匹配，未跑过数据
- 反例：改阈值把告警压到 0、或删掉命中样本让规则「变干净」，都不算验证通过
