---
name: hardware-security
description: Hardware interface research — 当用户能摸到板子想找调试口提镜像，或说“这个UART口在哪”“JTAG能连上吗”“Flash怎么dump出来”时使用。Use when UART JTAG discovery, firmware extraction.
---

# Hardware / Embedded Interface Security

## ACTION REQUIRED（读完后立刻执行）

1. `NOW`: **查经验卡** —— `python skills/scripts/experience-card.py search "<你看到的症状>"`。
   命中就读那张卡的 `invariant` + `decision.action`，并**逐条对照** `scope.appliesWhen`
   与 `scope.stopsWhen`：少一条前提就停用；命中任一停止条件就停。
   历史卡**不替代**当前目标的实测证据。详见 `../experience-cards/INDEX.md`。
2. `NOW`: 确认**物理接触授权**与设备归属
3. `NOW`: ESD/电源安全；默认只读探测
4. `NEXT`: 联合 firmware-pentest 做镜像分析
5. `ACT`: 外壳与调试接口识别 →  consoles → 提取

## 适用场景

- UART / JTAG / SWD 调试口发现
- 启动日志、root shell、引导打断
- 配合拆机提取 Flash
- 安全启动/加密 Flash 的可行性评估（非破坏性优先）

## 工作流

```text
□ 拆解授权设备；拍照标注测试点
□ 万用表找 GND/VCC/TX/RX；逻辑电平 1.8/3.3/5V
□ USB-TTL 只读日志；记录波特率
□ JTAG：枚举 IDCODE；评估是否锁定
□ 提取镜像 → 交接 firmware-pentest / ghidra
```

## 工具链

| 工具 | 用途 |
|------|------|
| USB-TTL / logic analyzer | UART |
| J-Link / CMSIS-DAP | 调试 |
| bus pirate / flipper（实验室） | 多协议 |
| binwalk / flashrom | 提取 |

## 参考

- `references/debug-interface-triage.md`
- `../firmware-pentest/` `../ot-ics/`

## 路由上下文

**上游**: MASTER R34  
**MUST NOT**: 未授权拆机/损坏他人设备

## 任务完成自检

- [ ] 是否记录接口电平与引脚图？
- [ ] 镜像是否哈希保全？
- [ ] Checklist？