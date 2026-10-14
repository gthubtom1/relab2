---
name: hardware-security
description: 硬件/嵌入式接口安全：UART/JTAG/SWD 调试口发现、root shell 获取、拆机提取 SPI/NOR Flash。用于：UART 口在哪、JTAG 能连上吗、Flash 怎么 dump。
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

---

## When NOT to use（近邻负例）

- 目标只有固件文件，没有物理板子 → 用 `../firmware-pentest/SKILL.md`
- 目标是软件层的调试接口（不是 JTAG/SWD/UART） → 用 `../x64dbg-reverse/SKILL.md`
- 目标是无线射频信号 → 用 `../radio-sdr/SKILL.md`
- 前置条件：物理接触可能不可逆 → 动手前先留**可恢复的备份/快照**（Flash 读数、焊点照片）

## When to Pivot

信号与判据见 `../ops/skill-pivot-contract.md`。本技能去向：

| 触发证据 | 换到 |
|---|---|
| 从 Flash 提取到固件镜像 | `../firmware-pentest/SKILL.md` |
| 从串口拿到 shell，要分析系统内进程 | `../reverse-engineering/SKILL.md` |
| 发现无线芯片，要分析射频协议 | `../radio-sdr/SKILL.md` |

## 定义完成

本技能产出算「完成」的**外部可观测**条件（不许写形容词）：

- 接口识别结果落盘（引脚 → 信号 → 波特率/时序实测值）
- 提取的镜像/固件有 SHA-256 与落盘路径
- 可重复：给出下一个人照着做能复现的接线与命令

## 输出契约

```
FACT:       <观察，带来源：命令 / 文件:行 / Evidence ID>
HYPOTHESIS: <可测试断言 + confidence: high|medium|low>（状态见 `../ops/binary-model.md`）
QUESTION:   <当前最大不确定点>
NEXT:       <继续 | 换技能 | 停止（附成本判据）>
```

## 置信度词表

词表见 `../ops/confidence-vocabulary.md`。本技能特有判据：

- `confirmed`：接口用途有实测数据（示波器/逻辑分析仪抓到的波形或成功读写）
- `low`：仅凭引脚排布猜测 UART TX/RX
