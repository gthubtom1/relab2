---
name: radio-sdr
description: 授权 RF/SDR 信号研究：调制识别、GNU Radio/URH/Inspectrum 解调、屏蔽室重放。用于：非 Wi-Fi 射频（RTL-SDR/HackRF IQ）、ADS-B/遥控/传感器协议。
---

# RF / SDR Security Research

## ACTION REQUIRED（读完后立刻执行）

1. `NOW`: **查经验卡** —— `python skills/scripts/experience-card.py search "<你看到的症状>"`。
   命中就读那张卡的 `invariant` + `decision.action`，并**逐条对照** `scope.appliesWhen`
   与 `scope.stopsWhen`：少一条前提就停用；命中任一停止条件就停。
   历史卡**不替代**当前目标的实测证据。详见 `../experience-cards/INDEX.md`。
2. `NOW`: **频谱与发射受法律严格管制**；仅授权频段/屏蔽室/实验目标
3. `NOW`: scope 写明设备、频段、是否允许发射（默认只收）
4. `ACT`: 只接收识别 → 解调分析 → 实验室复现评估

## 适用场景

- 无线遥控/传感器等非 Wi-Fi RF（授权）
- ADS-B/遥控等协议研究（合法接收）
- 与 wifi-wireless 分工：本 skill 偏 **SDR 通用 RF**；Wi-Fi 攻防走 R29

## 工作流

```text
□ 法规与许可确认
□ 只收：识别中心频率与调制
□ GNU Radio / URH 分析
□ 重放仅屏蔽室且书面允许
□ 结论侧重：是否可未授权控制 / 加固建议
```

## 工具链

| 工具 | 用途 |
|------|------|
| RTL-SDR / HackRF（合规） | 收发硬件 |
| URH / GNU Radio | 分析 |
| Inspectrum | 信号 |

## 参考

- `references/sdr-lab-rules.md`
- `../wifi-wireless/` `../ot-ics/` `../hardware-security/`

## 路由上下文

**上游**: MASTER R38  
**MUST NOT**: 干扰公共通信、未授权发射

## 任务完成自检

- [ ] 是否默认只收并记录法规边界？
- [ ] Checklist？

---

## When NOT to use（近邻负例）

- 目标是 Wi-Fi（802.11） → 用 `../wifi-wireless/SKILL.md`
- 目标是固件里的无线配置 → 用 `../firmware-pentest/SKILL.md`
- 目标是蓝牙以外的普通网络协议 → 用 `../protocol-reverse/SKILL.md`
- 前置条件：**默认只收不发**；发射（重放/干扰）会污染现场 → 只在屏蔽室或物理隔离环境做

## When to Pivot

信号与判据见 `../ops/skill-pivot-contract.md`。本技能去向：

| 触发证据 | 换到 |
|---|---|
| 识别出具体协议，需要还原报文结构 | `../protocol-reverse/SKILL.md` |
| 信号来自某设备，需要看其固件 | `../firmware-pentest/SKILL.md` |
| 目标是 Wi-Fi 握手 | `../wifi-wireless/SKILL.md` |

## 定义完成

本技能产出算「完成」的**外部可观测**条件（不许写形容词）：

- IQ 采样或解调结果有落盘路径与参数（中心频率/带宽/采样率）
- 调制识别有依据（星座图/频谱特征），不是猜
- 可重放性评估写明「是否需要发射」以及是否已获授权

## 输出契约

```
FACT:       <观察，带来源：命令 / 文件:行 / Evidence ID>
HYPOTHESIS: <可测试断言 + confidence: high|medium|low>（状态见 `../ops/binary-model.md`）
QUESTION:   <当前最大不确定点>
NEXT:       <继续 | 换技能 | 停止（附成本判据）>
```

## 置信度词表

词表见 `../ops/confidence-vocabulary.md`。本技能特有判据：

- `confirmed`：解调出的比特流有 CRC/结构校验通过（不是噪声里挑出来的）
- `low`：仅凭频谱形状猜测调制方式
