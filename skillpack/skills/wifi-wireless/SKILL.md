---
name: wifi-wireless
description: Wi-Fi 安全评估：监听模式、WPA/WPA2 握手/PMKID、aircrack/hashcat 口令评估、流氓 AP 检测。用于：airmon-ng/airodump-ng 抓包、802.11 管理帧。
---

# Wi-Fi / Wireless Security

## ACTION REQUIRED（读完后立刻执行）

1. `NOW`: 读取 precedent-pentest；无线攻击按 `scope.md` 直接执行，注明物理范围
2. `NOW`: **查经验卡** —— `python skillpack/skills/scripts/experience-card.py search "<你看到的症状>"`。
   命中就读那张卡的 `invariant` + `decision.action`，并**逐条对照** `scope.appliesWhen`
   与 `scope.stopsWhen`：少一条前提就停用；命中任一停止条件就停。
   历史卡**不替代**当前目标的实测证据。详见 `../experience-cards/INDEX.md`。
3. `NOW`: 锁定目标 SSID/BSSID；扫整片频段会把邻居网络和自己的采集搅在一起（锁定 BSSID 是精度问题）
4. `NEXT`: 确认适配器监听模式能力
5. `ACT`: 侦察 → 采集 → 分析（实验室优先）

## 适用场景

- Wi-Fi 安全评估
- WPA/WPA2 握手采集与离线评估
- 流氓 AP / 钓鱼热点检测研究
- 企业无线隔离与门户安全

## 工作流

```text
□ iwconfig / airmon-ng 进入 monitor
□ airodump-ng 锁定目标 BSSID 频道
□ 握手或 PMKID 采集（仅目标）
□ hashcat/aircrack 离线评估口令策略
□ 报告：加密类型、隔离、门户绕过、建议
```

## 工具链

| 工具 | 干什么 | 真实调用口径 / 判据 |
|------|--------|----------------------|
| `airmon-ng` / `iw` | 切监听模式、回读信道与带宽 | `airmon-ng start wlan0` 后必须 `iw dev <mon> info` 回读；`type monitor` 不出现 = 没切成功，别急着抓 |
| `airodump-ng` / `aireplay-ng` | 锁定 BSSID 抓握手、定向 deauth | `airodump-ng -c <ch> --bssid <mac> -w cap <mon>`；deauth 只对已锁 BSSID 发 |
| `hcxdumptool` / `hcxtools` | PMKID 与握手导出为 22000 / 16800 | `hcxpcapngtool -o hs.22000 cap.pcapng`；导出文件为空 = 该窗口没拿到 PMKID |
| `hashcat` | 22000（EAPOL）/ 16800（PMKID）离线口令评估 | `hashcat -m 22000 hs.22000 <dict>`；结论看 `Status: Cracked` 还是 `Exhausted` |
| `tshark` / `Wireshark` | EAPOL / EAP 帧级核对、判 SAE / PMF | `tshark -r cap.pcapng -Y eapol`；GUI 只用于核对，脚本面一律 `tshark` |
| `nmap` / `curl` | 有线侧端口、captive portal 取页 | `curl -i http://<gw>/portal` 看跳转字段；门户 Web 面漏洞不属本技能 |
| `sigma` | 流氓 AP / 异常 beacon 的 WIDS 检测规则 | 同 SSID 双 BSSID、异常 OUI；规则交 `../threat-hunting/` 落地 |

探测层（唯一路径入口）：`. <仓根>\skillpack\skills\scripts\lib\Bootstrap.ps1` → `Resolve-ReverseToolSpec -Name tshark`。
`Get-Command` 查空 ≠ 缺工具（四级递进：env → PATH → `_map.json` → 工具根扫描）；MCP 通道是否在监听用 `mcp-status.ps1` 看，注册 ≠ 在监听。

## 参考

- `references/wireless-lab-rules.md`
- `../pentest-tools/` `../attack-chain/`（近源章节）

## 路由上下文

**上游**: MASTER R29  
**提醒**: deauth 对非目标 BSSID 发射会污染自己的采集（丢包、重传、客户端漫游）——锁定 BSSID 再打

## 任务完成自检

- [ ] 是否严格锁定目标 BSSID？
- [ ] 是否在报告中给出加固建议？
- [ ] Checklist？

---

## When NOT to use（近邻负例）

- 目标是非 Wi-Fi 射频（遥控 / ADS-B / LoRa 传感器） → 用 `../radio-sdr/SKILL.md`
- 目标是网卡固件 / 驱动本身（改 band、加 monitor 支持） → 用 `../firmware-pentest/SKILL.md`
- 目标是抓到凭据后在域内横向 → 用 `../windows-ad/SKILL.md`
- 目标是企业 802.1X / EAP / 证书面与内网中继链 → 用 `../attack-chain/SKILL.md`
- 目标是门户页 / 跳转链里的 Web 应用漏洞 → 用 `../pentest-tools/SKILL.md`

> **工程前提**：监听会把别人的流量一并收进来 —— 只抓自建网络或已隔离的实验网；报告外传前对真实客户端 MAC 打码（见 `references/wireless-lab-rules.md`）。

## When to Pivot

信号与判据见 `../ops/skill-pivot-contract.md`。本技能去向：

| 触发证据 | 换到 |
|---|---|
| `hcxpcapngtool` 导出 22000 / 16800 成功，但 `hashcat` 连续两次换字典跑完仍 `Exhausted`、无口令命中 | `../pentest-tools/SKILL.md` 换生成式词表；别重复抓同一批握手 |
| 两次被动窗口（合计约 5 分钟）采集为空 —— 无客户端重连 EAPOL | 改用 PMKID 主动请求，或对已锁 BSSID 做定向 deauth 提高命中；仍为空再回侦察 |
| 抓包出现 EAP / 证书交换（企业 802.1X 面） | `../attack-chain/SKILL.md`；若目标是拿 NTLM 中继则 `../windows-ad/SKILL.md` |
| `tshark` 显示 beacon 的 RSN 同时含 SAE 与 PSK（WPA3 transition mode） | 先判 PMF 是否 required：过渡模式才可降级打 WPA2 握手，否则本技能不适用 |
| 抓包 ≥30 秒只有 beacon、数据帧为空，或 `iw dev` 回读接口非 `type monitor` | 网卡 / 驱动能力不足 → `../firmware-pentest/SKILL.md`（`binwalk` 拆固件核 band/monitor），或先换适配器，不是反复重跑同一命令 |
| 门户页 `curl -i` 返回跳转且字段指向内部接口 | `../pentest-tools/SKILL.md` 评估门户 Web 面 |

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

- `confirmed`：`hashcat` 以 22000 / 16800 复原出口令，或该口令能被握手包重放验证
- 硬判据：握手捕获结论必须落到 `hcxpcapngtool` 导出文件的非零行数，或 `tshark -Y eapol` 帧计数 ≥1；只有 `airodump-ng` 右上角显示 "WPA handshake" 字样一律记 `low`
- `low`：仅捕获到流量（beacon / 无关数据帧），未形成可验证结论
- 反例：把邻居网络的握手混进采集、或对未锁 BSSID 发 deauth 得到的包，不计入证据
