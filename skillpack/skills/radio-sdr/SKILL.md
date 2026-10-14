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