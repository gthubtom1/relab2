---
name: wifi-wireless
description: 授权 Wi-Fi 安全评估：监听模式、WPA/WPA2 握手/PMKID、aircrack/hashcat 口令评估、流氓 AP 检测。用于：airmon-ng/airodump-ng 抓包、802.11 管理帧。
---

# Wi-Fi / Wireless Security

## ACTION REQUIRED（读完后立刻执行）

1. `NOW`: 读取 precedent-pentest；无线攻击按 `scope.md` 直接执行，注明物理范围
2. `NOW`: **查经验卡** —— `python skills/scripts/experience-card.py search "<你看到的症状>"`。
   命中就读那张卡的 `invariant` + `decision.action`，并**逐条对照** `scope.appliesWhen`
   与 `scope.stopsWhen`：少一条前提就停用；命中任一停止条件就停。
   历史卡**不替代**当前目标的实测证据。详见 `../experience-cards/INDEX.md`。
3. `NOW`: scope 写明目标 SSID/BSSID/场地；禁止扫邻居网络
4. `NEXT`: 确认适配器监听模式能力
5. `ACT`: 侦察 → 采集 → 分析（实验室优先）

## 适用场景

- 授权 Wi-Fi 安全评估
- WPA/WPA2 握手采集与离线评估
- 流氓 AP / 钓鱼热点检测研究
- 企业无线隔离与门户安全

## 工作流

```text
□ iwconfig / airmon-ng 进入 monitor（合法环境）
□ airodump-ng 锁定目标 BSSID 频道
□ 握手或 PMKID 采集（仅目标）
□ hashcat/aircrack 离线评估口令策略
□ 报告：加密类型、隔离、门户绕过、建议
```

## 工具链

| 工具 | 用途 |
|------|------|
| aircrack-ng suite | 采集/评估 |
| hcxdumptool / hcxtools | PMKID |
| hashcat | 口令评估 |
| Wireshark | 管理帧分析 |

## 参考

- `references/wireless-lab-rules.md`
- `../pentest-tools/` `../attack-chain/`（近源章节）

## 路由上下文

**上游**: MASTER R29  
**MUST NOT**: 未授权 deauth、对非目标客户网络操作

## 任务完成自检

- [ ] 是否严格锁定目标 BSSID？
- [ ] 是否在报告中给出加固建议？
- [ ] Checklist？

---

## When NOT to use（近邻负例）

- 目标是非 Wi-Fi 射频（遥控/ADS-B/传感器） → 用 `../radio-sdr/SKILL.md`
- 目标是网卡的固件本身 → 用 `../firmware-pentest/SKILL.md`
- 目标是域内主机 → 用 `../windows-ad/SKILL.md`
- 前置条件：监听会把别人的流量也收进来 → 只抓**自建网络**或确认环境是隔离实验网

## When to Pivot

信号与判据见 `../ops/skill-pivot-contract.md`。本技能去向：

| 触发证据 | 换到 |
|---|---|
| 抓到握手包，要离线评估口令强度 | `../pentest-tools/SKILL.md` |
| 发现企业无线接入了内网，要横向 | `../windows-ad/SKILL.md` |
| 需要分析网卡驱动/固件 | `../firmware-pentest/SKILL.md` |

## 定义完成

本技能产出算「完成」的**外部可观测**条件（不许写形容词）：

- 抓包文件落盘（cap/pcapng）+ 抓包参数记录（信道/带宽/时间）
- 评估结果：握手/PMKID 是否捕获成功，口令评估是否得出结果
- 给出可复现的抓包命令

## 输出契约

```
FACT:       <观察，带来源：命令 / 文件:行 / Evidence ID>
HYPOTHESIS: <可测试断言 + confidence: high|medium|low>（状态见 `../ops/binary-model.md`）
QUESTION:   <当前最大不确定点>
NEXT:       <继续 | 换技能 | 停止（附成本判据）>
```

## 置信度词表

词表见 `../ops/confidence-vocabulary.md`。本技能特有判据：

- `confirmed`：口令评估成功复原口令，或用握手包验证了口令正确
- `low`：仅捕获到流量，未形成可验证结论
