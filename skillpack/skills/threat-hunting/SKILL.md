---
name: threat-hunting
description: 威胁狩猎与检测工程：SIEM/EDR 假说查询、Sysmon 事件关联、Sigma/YARA 规则。用于：找 LOTL 横向、IOC 落地检测规则、验证规则。
---

# Threat Hunting & Detection Engineering

## ACTION REQUIRED（读完后立刻执行）

1. `NOW`: **查经验卡** —— `python skills/scripts/experience-card.py search "<你看到的症状>"`。
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
□ 原子测试（Atomic Red Team）仅在授权实验室
□ 回放历史日志验证召回
```

## 工具链

| 工具 | 用途 |
|------|------|
| Sigma CLI / sigmac | 规则转换 |
| YARA | 文件/内存 |
| SIEM（ELK/Splunk 等） | 查询 |
| osquery | 端点狩猎 |
| Atomic Red Team | 检测验证（实验室） |

## 参考

- `references/hunting-loop.md`
- `../malware-analysis/references/yara-sigma-rules.md`
- `../digital-forensics/`

## 路由上下文

**上游**: MASTER R27  
**下游**: 确认入侵 → forensics；恶意样本 → malware-analysis  
**MUST NOT**: 对本机 / lab 以外的生产环境跑攻击模拟（本卡研究默认在隔离 lab）

## 任务完成自检

- [ ] 是否有明确假说与结论？
- [ ] 规则是否注明误报与数据源？
- [ ] Checklist？

---

## When NOT to use（近邻负例）

- 要分析的是样本本体（静态/动态） → 用 `../malware-analysis/SKILL.md`
- 要做的是磁盘/内存取证 → 用 `../digital-forensics/SKILL.md`
- 要收集的是外部威胁情报 → 用 `../threat-intelligence/SKILL.md`
- 前置条件：查询生产 SIEM 前先确认查询范围与配额，避免拖垮日志平台

## When to Pivot

信号与判据见 `../ops/skill-pivot-contract.md`。本技能去向：

| 触发证据 | 换到 |
|---|---|
| 假设命中，需要样本确认 | `../malware-analysis/SKILL.md` |
| 需要落盘检测规则 | `../reverse-engineering/references/re-agent-workflow.md` |
| 需要外部 IOC 富化 | `../threat-intelligence/SKILL.md` |

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
- `low`：规则只在理论上能匹配，未跑过数据
