---
name: digital-forensics
description: 数字取证与应急响应（IR）：内存转储 Volatility、E01 磁盘时间线、PCAP 溯源、IOC 提炼。用于：看 mem.dmp、电脑中招怎么溯源、PCAP 有啥异常。
---

# Digital Forensics & IR Artifacts

## ACTION REQUIRED（读完后立刻执行）

1. `NOW`: 读取 `../field-journal/precedent-pentest.md` 或组织 IR 授权说明
2. `NOW`: **查经验卡** —— `python skills/scripts/experience-card.py search "<你看到的症状>"`。
   命中就读那张卡的 `invariant` + `decision.action`，并**逐条对照** `scope.appliesWhen`
   与 `scope.stopsWhen`：少一条前提就停用；命中任一停止条件就停。
   历史卡**不替代**当前目标的实测证据。详见 `../experience-cards/INDEX.md`。
3. `NOW`: 确认是**取证/溯源**而非进攻性扫描
4. `NOW`: 建立 case；证据只读副本优先（原始介质写保护）
5. `NEXT`: `../TOOLS.md`；Volatility 等常手动
6. `ACT`: 保全哈希 → 时间线 → 关键伪影

## 适用场景

- 内存转储分析（Volatility 2/3）
- 磁盘/ E01 / 落地文件时间线
- PCAP 溯源与协议还原（可联合 `protocol-reverse/`）
- 主机伪影：Prefetch、Shimcache、Event Log、浏览器历史
- 应急响应 IOC 提炼（联合 `malware-analysis/` / `threat-hunting/`）

## 工作流

### 1. 保全

```text
□ 计算 SHA256；记录时区与采集命令
□ 工作在副本上；原始只读
□ chain of custody 备注写入 timeline
```

### 2. 内存

```bash
vol -f mem.dmp windows.info
vol -f mem.dmp windows.pslist
vol -f mem.dmp windows.netscan
vol -f mem.dmp windows.cmdline
```

### 3. 主机伪影

```text
□ 事件日志：Security / PowerShell / Sysmon
□ 持久化：Run 键、服务、计划任务、WMI
□ 执行痕迹：Amcache、Prefetch、BAM
```

### 4. 网络

```text
□ tshark 统计会话与 DNS
□ 导出可疑流 → protocol-reverse 或 malware C2 分析
```

## 工具链

| 工具 | 用途 |
|------|------|
| Volatility 3 | 内存 |
| Timeline Explorer / Plaso | 超级时间线 |
| tshark | PCAP |
| Eric Zimmerman 工具集 | Windows 伪影 |
| Autopsy / FTK Imager | 磁盘 |

## 参考

- `references/forensics-triage.md`
- `../malware-analysis/` `../threat-hunting/` `../protocol-reverse/`

## 路由上下文

**上游**: MASTER R25  
**下游**: 恶意样本深挖 → malware-analysis；规则 → threat-hunting

## 任务完成自检

- [ ] 是否保全哈希与副本策略？
- [ ] 时间线是否可复核？
- [ ] IOC 是否脱敏分级？
- [ ] Checklist？

---

## When NOT to use（近邻负例）

- 要分析的是样本本身的行为与能力 → 用 `../malware-analysis/SKILL.md`
- 要做的是主动检测规则 → 用 `../threat-hunting/SKILL.md`
- 要收集的是外部情报 → 用 `../threat-intelligence/SKILL.md`
- 前置条件（硬性）：**不改变原始证据**；镜像前先做只读挂载或写阻止

## When to Pivot

信号与判据见 `../ops/skill-pivot-contract.md`。本技能去向：

| 触发证据 | 换到 |
|---|---|
| 转储里发现可疑样本，要分析 | `../malware-analysis/SKILL.md` |
| PCAP 里发现异常协议 | `../protocol-reverse/SKILL.md` |
| 需要落检测规则防复发 | `../threat-hunting/SKILL.md` |

## 定义完成

本技能产出算「完成」的**外部可观测**条件（不许写形容词）：

- 镜像/转储有 SHA-256 与封存路径；分析全程在副本上
- 时间线文件落盘（事件 → 时间 → 来源证据）
- `review_case.py --verify-hashes --strict` PASS

## 输出契约

```
FACT:       <观察，带来源：命令 / 文件:行 / Evidence ID>
HYPOTHESIS: <可测试断言 + confidence: high|medium|low>（状态见 `../ops/binary-model.md`）
QUESTION:   <当前最大不确定点>
NEXT:       <继续 | 换技能 | 停止（附成本判据）>
```

## 置信度词表

词表见 `../ops/confidence-vocabulary.md`。本技能特有判据：

- `confirmed`：时间线事件有 ≥2 类独立来源佐证（磁盘 + 内存 / 日志 + 流量）
- `low`：仅靠单一日志来源推断事件顺序
