---
name: hardware-security
description: 硬件/嵌入式接口安全：UART/JTAG/SWD 调试口发现、root shell 获取、拆机提取 SPI/NOR Flash。用于：UART 口在哪、JTAG 能连上吗、Flash 怎么 dump。
---

# Hardware / Embedded Interface Security

## ACTION REQUIRED（读完后立刻执行）

1. `NOW`: **查经验卡** —— `python skillpack/skills/scripts/experience-card.py search "<你看到的症状>"`。
   命中就读那张卡的 `invariant` + `decision.action`，并**逐条对照** `scope.appliesWhen`
   与 `scope.stopsWhen`：少一条前提就停用；命中任一停止条件就停。
   历史卡**不替代**当前目标的实测证据。详见 `../experience-cards/INDEX.md`。
2. `NOW`: 确认设备归属与物理接触面（拆机前拍照记型号/丝印）
3. `NOW`: ESD/电源安全；默认只读探测
4. `NEXT`: 联合 firmware-pentest 做镜像分析
5. `ACT`: 外壳与调试接口识别 →  consoles → 提取

## 适用场景

- UART / JTAG / SWD 调试口发现与电平判定
- 引导打断、启动日志、root shell、引导参数
- 配合拆机提取 SPI/NOR/eMMC 镜像（优先非破坏、可回退）
- 调试口被锁（读保护/安全启动）时的可行性判定 —— 先判「锁了什么」，再决定动不动烙铁

## 引脚与电平判据（先量再接）

| 读到的现象 | 判据 | 处置 |
|---|---|---|
| 与地铜箔/屏蔽罩通断为 0 Ω | 该脚是 GND | 先定地，其余脚都以它为参考 |
| 上电后稳在 3.3/1.8 V，掉电立刻消失 | VCC | **不要接**自己的 USB-TTL 供电脚：双电源对打先烧的是转换器 |
| 上电瞬间跳变最密的那只脚 | TX（设备在说话） | 接转换器的 RX，单线即可收日志 |
| 上电后基本不动、只在收到数据时抖 | RX | 先只收；要打断引导再考虑接 TX |
| 串口整片乱码或全 0x00 | 波特率或电平不对 | 逐档试 115200 / 57600 / 38400 / 9600，各只试一次；仍乱码就用逻辑分析仪量最短脉宽反推 |
| 目标 IO 是 1.8 V 而适配器是 3.3 V | 电平不匹配 | 先分压或换 1.8 V 适配器；直怼属于长期可靠性事故，不是「能用就行」 |

串口打断的窗口：U-Boot 提示符出现前通常只有 1–2 秒，敲键要连发而不是单次。
打断成功后**先 `printenv` 只读**：`saveenv` 会把设备写脏，改任何环境变量前先整份 dump 出来。

## 提取判据（正常读数 vs 异常读数）

| 通道 | 正常读数 | 异常读数 → 先怀疑什么 |
|---|---|---|
| SPI NOR（flashrom + CH341A/CH347/minipro） | 连读 3 次哈希一致、ID 有确定厂商码 | ID 全 `0xFF` → 读保护位（RDP/CRP/BP）或未上电；ID 全 `0x00` → SO/CS 虚接、目标没供电 |
| 在线夹取（板子在跑时读） | 偶尔能读出但每次内容不同 | 内容随机变化 = MCU 总线争用，不是 Flash 坏了；断电夹取重读 |
| JTAG/SWD（OpenOCD `scan_chain`） | 返回确定的 IDCODE，两次相同 | 全 0/全 1 或两次不同 → 先把时钟降到 ≤1 MHz、核对 VREF 与 TDI/TDO 是否接反；仍不对再怀疑该脚被复用成 GPIO |
| eMMC/BGA | 有 eMMC 分区表特征 | 焊球无法夹取时不要硬上热风：先看板上是否有测试点，或从运行中的系统侧读回 |
| 芯片丝印读不到/被打磨 | — | 用封装尺寸 + 引脚数 + 供电脚位置反查同封装系列，别靠猜型号去配算法 |

## 工具链

| 工具 | 用途 | 定位方式 |
|---|---|---|
| 万用表（通断/电压档） | 定 GND/VCC/TX/RX、判断目标是否上电 | 台面工具；判错脚序的代价是往 SoC 灌流，先量后接 |
| USB-TTL（CP2102/FT232） | 串口日志与控制台 | 台面工具；只接 TX/GND，记下实际波特率 |
| 逻辑分析仪（sigrok + PulseView） | 量位宽反推波特率、看 SPI 时序 | 台面工具；波特率盲试失败时的唯一硬证据 |
| `minicom` / `picocom`（Linux 侧）/ PuTTY | 交互式串口终端 | 台面/宿主工具；打断 U-Boot 用连发按键 |
| flashrom + CH341A/CH347/minipro | SPI NOR 全片读（`-p ch341a_spi -r dump.bin`） | 编程器侧工具；读三份比哈希，一致才算稳 |
| OpenOCD（配 `gdb` 做 gdb-multiarch 后端） | JTAG/SWD 扫描链、寄存器级读写 | 探测 id `gdb` 拿调试后端；OpenOCD 走探测层，缺则按 `../TOOLS.md` 装完复验 |
| JTAGulator / Bus Pirate / `esptool` | 未知引脚暴力枚举、ESP 系串口协议 | 台面工具；枚举会驱动引脚，目标在跑关键流程时不要上 |
| `diec` | 拿到 dump 第一刀：文件类型/熵/压缩头 | 探测 id `diec` |
| `binwalk` | 固件递归提取（squashfs/JFFS2/UBI/U-Boot 头） | 探测 id `binwalk`；探测不到就按 `../TOOLS.md` 的装法补 |
| `rabin2` / `radare2` | 从提取物里挑 ELF/内核，看节区与字符串 | 探测 id `rabin2` / `radare2` |
| `Ghidra` + `analyzeHeadless` / `idat` | 反编译 bootloader：签名校验点、`saveenv`、升级路径 | 探测 id `ghidra_headless` / `idat`；批量导出一次跑完，别逐函数点 |
| `tshark` / `Wireshark` | 设备起来后的网口面（DHCP/TFTP/升级端口） | 探测 id `tshark`；与串口日志按时间对齐看 |
| `nmap` | 拿到 shell 后的本机服务面 | 探测 id `nmap`；单机低速，段扫留给 `../pentest-tools/` |
| `hashcat` | 提取出的 `/etc/shadow`、配置口令 hash 离线 | 探测 id `hashcat`；先确认 hash 类型再选模式，别盲跑字典 |

> **探针与通道都要现场定位（这条不许凭记忆）。**
> 先 `. <仓根>\skillpack\skills\scripts\lib\Bootstrap.ps1`，再 `Resolve-ReverseToolSpec -Name <id>`：`Command` 给的是完整路径，直接用它调，别依赖 cwd；
> `Get-Command` 返回空只说明第 2 级没命中（PATH 快照陷阱，见 `../references/env-selfcheck.md`），要走完四级再判缺，缺了照 `../TOOLS.md` 装。
> 台面外的家伙（调试器、编程器、串口工具）在本机常常没有：先探测、再声明缺什么；通道另用
> `powershell -NoProfile -ExecutionPolicy Bypass -File skillpack\skills\scripts\mcp-status.ps1` 看三列（注册了哪些 / 谁在监听 / 怎么起），**注册 ≠ 在监听**。

## 参考

- `references/debug-interface-triage.md`
- `../reverse-engineering/platforms-hardware.md`（OpenOCD/JTAG 命令面）
- `../firmware-pentest/references/extraction-methodology.md`（SPI/在线读的对照做法）
- `../firmware-pentest/` `../ot-ics/`

## 路由上下文

**上游**: MASTER R34  

## 任务完成自检

- [ ] 引脚结论有实测支撑吗（万用表读数/波形/成功读写），还是照丝印猜的？
- [ ] 镜像有没有多读几份比哈希，落盘路径 + SHA-256 齐了吗？
- [ ] 动手改任何东西之前，有没有先留下可恢复的快照（Flash dump、环境变量 dump、焊点照片）？
- [ ] 报「读不出来」之前，有没有先排除读保护、供电、接线这三个可判定的原因？

---

## When NOT to use（近邻负例）

- 手上只有固件文件、没有板子（厂商站下载或别人 dump 的镜像）→ 用 `../firmware-pentest/SKILL.md`
- 目标是软件层调试接口（用户态进程、内核驱动、反调试）→ 用 `../x64dbg-reverse/SKILL.md`
- 目标是射频信号本身（要解调、要判滚动码、要重放）→ 用 `../radio-sdr/SKILL.md`
- 目标是移动设备整机面（adb/USB、锁屏、App 数据），不是引脚面 → 用 `../mobile-reverse/SKILL.md`
- 设备是现场在跑的工控/过程控制节点，写错一个位就是物理后果 → 用 `../ot-ics/SKILL.md`
- 只要一份 IoT 设备的默认口令与 Web 管理面清单，不打算拆机 → 用 `../pentest-tools/SKILL.md`
- 要逆的是设备上跑的那个可疑进程，硬件只是入口 → 用 `../malware-analysis/SKILL.md`

## When to Pivot

信号与判据见 `../ops/skill-pivot-contract.md`。本技能去向：

| 触发证据 | 换到 |
|---|---|
| flashrom 读出完整镜像（非全 `0xFF`，熵图上能看到文件系统头） | `../firmware-pentest/SKILL.md` 做离线提取与文件系统审计 |
| 串口拿到 shell（出现 `#` 且能跑 `uname`），目标转为系统内进程与后门 | `../reverse-engineering/SKILL.md` |
| 板上另有独立无线芯片/BT 模组（丝印带天线馈点，或 `dmesg` 出现 RF 驱动） | `../radio-sdr/SKILL.md` |
| Flash ID 读回全 `0xFF`，换过线序两次还是这样 | 别第三次重试：先查 RDP/CRP/BP 读保护位与供电，确认保护后再谈旁路（从运行态读回） |
| JTAG `scan_chain` 两次检测到的 IDCODE 不同或全 0/全 1 | 先把时钟降到 ≤1 MHz 并核 VREF/TDI-TDO，仍不对再判该脚被复用或锁死，改走 UART/离线 dump |
| 串口每档波特率试完仍显示乱码（整片 `0x00` 或随机字节） | 换测量手段：逻辑分析仪量最短脉宽反推真实波特率，停止盲试 |
| 能读写寄存器但 `halt` 后立刻复位（看门狗在咬） | 先处理看门狗/复位脚，或改走离线通道：整片 dump → `../firmware-pentest/SKILL.md` |
| 设备起来后暴露 Web 升级面（`upgrade.cgi`、TFTP 拉固件） | `../pentest-tools/SKILL.md`：问题已从引脚面变成服务端漏洞 |

## 定义完成

本技能产出算「完成」的**外部可观测**条件（不许写形容词）：

- 接口识别结果落盘（引脚 → 信号 → 实际波特率/时序实测值），并注明是用什么量出来的
- 提取的镜像/固件有落盘路径与 SHA-256；多次读取时给出各次哈希的比对结果
- 可重复：给出下一个人照着做能复现的接线图与命令（含电平、波特率、探针位置）
- 若判定为「读保护/锁死」，给出支撑该判定的读数（ID 原始值、扫描链回读值）

## 输出契约

```
FACT:       <观察，带来源：命令 / 文件:行 / Evidence ID>
HYPOTHESIS: <可测试断言 + confidence: high|medium|low>（状态见 `../ops/binary-model.md`）
QUESTION:   <当前最大不确定点>
NEXT:       <继续 | 换技能 | 停止（附成本判据）>
```

## 置信度词表

词表见 `../ops/confidence-vocabulary.md`。本技能特有判据：

- `confirmed`：接口用途有实测数据支撑（逻辑分析仪抓到的波形、成功的读写返回、多次一致的镜像哈希）
- `medium`：按丝印/封装/参考设计推断的引脚或芯片型号，尚未实测
- `low`：仅凭引脚排布或丝印猜测 UART TX/RX，或仅凭封装猜 Flash 型号
