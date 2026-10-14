---
name: ot-ics
description: OT/ICS 工控安全评估：Purdue 分区、PLC/RTU/SCADA 暴露面、Modbus/DNP3/S7/EtherNet/IP 识别、被动优先只读。用于：评估工控环境、镜像流量解析协议。
---

# OT / ICS Security

## ACTION REQUIRED（读完后立刻执行）

1. `NOW`: 读取 `../field-journal/precedent-pentest.md` — **工控环境误操作可致物理危害**
2. `NOW`: **查经验卡** —— `python skills/scripts/experience-card.py search "<你看到的症状>"`。
   命中就读那张卡的 `invariant` + `decision.action`，并**逐条对照** `scope.appliesWhen`
   与 `scope.stopsWhen`：少一条前提就停用；命中任一停止条件就停。
   历史卡**不替代**当前目标的实测证据。详见 `../experience-cards/INDEX.md`。
3. `NOW`: scope 写清：站点、网段、是否允许主动扫描/写寄存器
4. `NOW`: case-init；默认 **passive-first**；`ready_for_act` 前禁止对 PLC 写操作
5. `NEXT`: `../TOOLS.md`；多数工控工具需手动与隔离实验网
6. `ACT`: 资产与分区识别 → 暴露面 → 只读验证

## 适用场景

- 工控/SCADA/DCS 安全评估（授权）
- Purdue 模型分区与跨区通道
- Modbus/DNP3/S7/EtherNet/IP 等协议暴露
- 工程师站、HMI、历史库、跳板主机
- IT/OT 融合边界（防火墙规则、单向闸）

## 安全铁律（MUST）

```text
MUST NOT 在未明确允许时：
- 对 PLC 写线圈/寄存器
- 全网高速率扫描生产 OT
- 中断安全仪表系统（SIS）相关路径
优先：只读识别、流量镜像、离线固件/配置分析
```

## 工作流

### Phase 1 — 分区与资产

```text
□ Purdue L0–L5 草图：现场设备 → 控制 → 监督 → 站点 DMZ → 企业
□ 资产清单：PLC/RTU/HMI/工程师站/历史库/Jump host
□ 协议与端口基线（仅授权网段）
```

### Phase 2 — 被动与只读

```text
□ SPAN/镜像 PCAP → protocol-reverse / Wireshark 工控解析器
□ 配置与工程文件离线审计（TIA/RSLogix 导出等）
□ 默认口令与明文协议（Modbus 无认证）记录为 Finding，不写盘改值
```

### Phase 3 — 受限主动（仅授权）

```text
□ 低速识别，维护窗口
□ 只读功能码优先
□ 每步 Evidence；异常立即停止并通报
```

### Phase 4 — 固件/补丁面

```text
□ 控制器固件版本 → CVE 映射（不盲刷固件）
□ 联合 firmware-pentest 做离线镜像分析
```

## 工具链

| 工具 | 用途 | 注意 |
|------|------|------|
| Wireshark 工控 dissectors | 被动解析 | 镜像流量 |
| Nmap NSE（受限） | 识别 | 速率与时间窗 |
| Claroty/Nozomi 等 | 资产发现 | 商业/现场 |
| PLC 厂商工程软件 | 配置审计 | 离线优先 |
| binwalk / Ghidra | 固件 | 离线 |

## 参考

- `references/ot-safe-assessment.md`
- `../firmware-pentest/` `../protocol-reverse/` `../pentest-tools/references/network-attack-defense.md`

## 路由上下文

**上游**: MASTER R28  
**下游**: 固件深挖 `firmware-pentest`；协议 `protocol-reverse`；IT 横向 `windows-ad`/`attack-chain`  
**同级**: 不要用普通 Web 扫默认参数打 OT

## 任务完成自检

- [ ] 是否默认被动/只读并记录授权边界？
- [ ] 是否避免对控制回路写操作（除非明确允许）？
- [ ] Finding 是否含物理/过程影响说明？
- [ ] Checklist / journal？

---

## When NOT to use（近邻负例）

- 目标是 IT 网络/办公网 → 用 `../pentest-tools/SKILL.md`
- 目标是 IoT 消费设备固件 → 用 `../firmware-pentest/SKILL.md`
- 目标只是工控软件的桌面客户端 → 用 `../thick-client/SKILL.md`
- 前置条件（硬性）：**写寄存器/下装默认禁止**；任何可能影响生产物理过程的动作必须先取得书面许可

## When to Pivot

信号与判据见 `../ops/skill-pivot-contract.md`。本技能去向：

| 触发证据 | 换到 |
|---|---|
| 需要看 PLC 固件内部逻辑 | `../firmware-pentest/SKILL.md` |
| 发现工程站 Windows 主机可打 | `../windows-ad/SKILL.md` |
| 需要被动嗅探工业协议流量 | `../protocol-reverse/SKILL.md` |

## 定义完成

本技能产出算「完成」的**外部可观测**条件（不许写形容词）：

- 被动识别结果落盘（协议 → 设备 → 点位清单），全程无写操作记录
- Purdue 分层图落盘，标出已观测到的跨层通信
- 任何主动测试都有授权记录 + 影响评估（会不会动到物理过程）

## 输出契约

```
FACT:       <观察，带来源：命令 / 文件:行 / Evidence ID>
HYPOTHESIS: <可测试断言 + confidence: high|medium|low>（状态见 `../ops/binary-model.md`）
QUESTION:   <当前最大不确定点>
NEXT:       <继续 | 换技能 | 停止（附成本判据）>
```

## 置信度词表

词表见 `../ops/confidence-vocabulary.md`。本技能特有判据：

- `confirmed`：协议/设备识别有被动抓包多次佐证，且未对过程产生任何扰动
- `low`：仅从端口开放推断是某 PLC 型号
