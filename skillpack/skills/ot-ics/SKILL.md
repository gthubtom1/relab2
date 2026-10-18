---
name: ot-ics
description: OT/ICS 工控安全评估：Purdue 分区、PLC/RTU/SCADA 暴露面、Modbus/DNP3/S7/EtherNet/IP 识别、被动优先只读。用于：评估工控环境、镜像流量解析协议。
---

# OT / ICS Security

## ACTION REQUIRED（读完后立刻执行）

1. `NOW`: 读 `../field-journal/precedent-pentest.md` —— 常规操作清单，直接照做；工控环境误操作可致物理危害（见下「动手顺序」）
2. `NOW`: **查经验卡** —— `python skillpack/skills/scripts/experience-card.py search "<你看到的症状>"`。
   命中就读那张卡的 `invariant` + `decision.action`，并**逐条对照** `scope.appliesWhen`
   与 `scope.stopsWhen`：少一条前提就停用；命中任一停止条件就停。
   历史卡**不替代**当前目标的实测证据。详见 `../experience-cards/INDEX.md`。
3. `NOW`: 记录站点拓扑与网段；先被动后主动（见下「动手顺序」）
4. `NOW`: case-init；默认 **passive-first** —— 先镜像流量、离线配置、只读识别
5. `NEXT`: `../TOOLS.md`；多数工控工具需手动与隔离实验网
6. `ACT`: 资产与分区识别 → 暴露面 → 只读验证

## 适用场景

- 工控/SCADA/DCS 安全评估
- Purdue 模型分区与跨区通道
- Modbus/DNP3/S7/EtherNet/IP 等协议暴露
- 工程师站、HMI、历史库、跳板主机
- IT/OT 融合边界（防火墙规则、单向闸）

## 速率与时间窗判据（工艺约束 —— 即上文的「动手顺序」，先读再动）

| 读数/现象 | 判据 | 处置 |
|---|---|---|
| 目标 PLC/RTU 是 2000 年代初机型（CPU 单连接栈、无并发） | SYN 风暴下连接表会耗尽，表现为通讯中断、工艺停车 | 扫描速率压到 ≤10 包/秒，且只在本站维护窗内做 |
| 镜像里看到主站-从站轮询周期稳定（通常 100 ms ~ 1 s） | 该链路在生产中，任何注入都会打断轮询 | 只记录，不在该网段做主动探测 |
| 现场同时有 SIS（安全仪表回路）与过程控制网 | SIS 的可用性优先级高于任何测试收益 | 单独标出 SIS 路径与跨接点，写进报告的边界章节 |
| 手头流量是离线 PCAP | 被动面的信息量 > 任何主动扫描 | 先把 PCAP 榨干（见下「被动面读数」），再谈要不要扫 |
| 主动测试要动到写功能码 | 写操作会改变物理过程 | 写前记当前值、确认有物理回退手段（旁路/急停），否则只做只读位 |

## 被动面读数（镜像流量先榨干）

| 读到的指纹 | 说明什么 | 记什么 |
|---|---|---|
| 502 上的功能码 0x03/0x04 | 只读轮询（读保持寄存器/输入寄存器） | 点表地址范围、轮询周期、主站 IP |
| 502 上出现 0x05/0x06/0x0F/0x10 | 有写操作在链路上（线圈/寄存器） | 写者是谁、写哪些点位；**记录，不回应** |
| 102 上的 0xF0 setup / 0x1A 上传 | S7comm，西门子系；工程组态常走这条 | CPU 型号、机架槽位、工程站 |
| 44818 上的 CIP 显式报文 | EtherNet/IP，CIP 无认证 | 目标设备身份与对象类 |
| 20000 上的 DNP3（FC 0x01/0x02 读、0x10 直接操作） | 电力/水务常见，链路层无认证 | 主站地址、点号范围 |
| 同一网段同时出现 SMB/LDAP/Kerberos | 这个网段不是纯 OT，IT 已跨过来 | 立即标出边界，见「When to Pivot」 |

Purdue 分层不要凭设备名字填：用观察到的通信对（谁跟谁说话、走什么端口）反推层级，
没观察到的跨层通道标「未观测」，不要画一条不存在的箭头。

## 只读命令速查（先被动榨干，再限速只读）

```bash
# 被动：离线 PCAP 先榨干（只读、零注入，改任何字节都算越界）
tshark -r plant.pcapng -Y "modbus.func_code == 6" -T fields -e ip.src -e modbus.reference_num -e modbus.value
tshark -r plant.pcapng -Y "dnp3.al.func == 1" -T fields -e dnp3.al.src -e dnp3.al.dst -e dnp3.al.obj
tshark -r plant.pcapng -Y "s7comm" -T fields -e s7comm.param.func -e s7comm.cpu_model

# 只读主动：只在维护窗做，限速到 ≤10 包/秒、单端口、NSE 只做识别
nmap -Pn -sT -p 502 --max-rate 10 --script modbus-discover 10.10.20.31

# 固件 / 工程文件一律离线分诊（隔离机里做，别连现场控制器）
binwalk -Me controller-fw.bin
rabin2 -zz gateway-fw.bin | grep -i -e plant -e station
```

> 上面的 `10.10.20.31` 只是示例从站地址，换成你自己站点里观察到的从站 IP；`--max-rate`、端口、时间窗三样缺一不许发包。

## 工具链

| 工具 | 用途 | 定位方式与关键细节 |
|---|---|---|
| `tshark` / `Wireshark` | 工控 dissector 离线解析（502/102/44818/20000） | 探测 id `tshark`（Wireshark 的 CLI 孪生）；用 `-Y` 过滤功能码比翻包快 |
| `nmap` | 只读识别（NSE `modbus-discover` 之类） | 探测 id `nmap`；必须显式限速与限时，默认参数打 OT 等于事故 |
| Zeek（现场已部署时） | 协议会话日志、资产基线 | 现场侧部署；只读旁路口，不要为它临时改镜像口配置 |
| 厂商工程软件（TIA Portal / RSLogix / EcoStruxure 等） | 离线读工程文件、点表与联锁逻辑 | 现场侧提供的工程文件副本，在隔离机里开，别连现场控制器 |
| `binwalk` | 控制器固件离线提取（squashfs/UBI/裸内核） | 探测 id `binwalk`；未命中按 `../TOOLS.md` 装法 |
| `Ghidra` + `analyzeHeadless` / `idat` | 固件里协议处理与升级校验的反编译 | 探测 id `ghidra_headless` / `idat`；结论与固件版本号绑定 |
| `radare2` / `rabin2` / `diec` | 固件/工程文件快速分诊（类型、壳、字符串） | 探测 id `radare2` / `rabin2` / `diec`；先分诊再决定上哪个反编译器 |
| `hashcat` | 工程文件/固件里取到的口令 hash 离线破解 | 探测 id `hashcat`；先认出 hash 类型（S7 旧口令哈希与通用格式不同），别盲跑 |
| `curl` | HMI/工程站的 Web 面只读探测（状态页、诊断页） | 探测 id `curl`；只 GET，带副作用的接口一律不下手 |
| `gdb` | 固件仿真环境里的调试 | 探测 id `gdb`；配仿真后端用，别对现场设备下断点 |
| **反例：`masscan`** | 全速率扫描器 | 在 OT 网段**禁用**：它的探测包密度会在秒级打瘫老控制器 |

> **工具与通道先定位，再谈动作（OT 现场没有试错预算）。**
> 载入探测层 `. C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1` 后跑 `Resolve-ReverseToolSpec -Name <id>`，返回的 `Command` 才是可直接调用的完整路径；
> 单条 `Get-Command` 查空不算缺工具（PATH 快照陷阱见 `../references/env-selfcheck.md`），四级探测全 `Available=False` 才算缺，装法看 `../TOOLS.md`。
> 现场侧工具（厂商工程软件、单向闸管理口）多半只能现场取；宿主侧通道清单用
> `powershell -NoProfile -ExecutionPolicy Bypass -File skillpack\skills\scripts\mcp-status.ps1` 现查（注册了哪些 / 谁在监听 / 怎么起），**注册不等于在监听**。

## 参考

- `references/ot-safe-assessment.md`
- `../firmware-pentest/` `../protocol-reverse/` `../pentest-tools/references/network-attack-defense.md`

## 路由上下文

**上游**: MASTER R28  
**下游**: 固件深挖 `firmware-pentest`；协议 `protocol-reverse`；IT 横向 `windows-ad`/`attack-chain`  
**同级**: 不要用普通 Web 扫默认参数打 OT

## 任务完成自检

- [ ] 被动面是不是先榨干了（点表、写者、轮询周期有数）？
- [ ] 每次主动动作有没有记录速率上限、时间窗与影响评估（会不会动到物理过程）？
- [ ] 写操作前有没有留下当前值快照与物理回退手段？
- [ ] Finding 有没有写清物理/过程影响，而不只是「端口开放」？
- [ ] Purdue 图上有没有标「未观测」而不是凭设备名推断？

---

## When NOT to use（近邻负例）

- 目标是纯 IT 办公网/互联网资产，现场没有任何工控设备 → 用 `../pentest-tools/SKILL.md`
- 手上只有消费级 IoT 的固件文件，谈不到过程控制与分区 → 用 `../firmware-pentest/SKILL.md`
- 要逆的是工控软件的桌面客户端本身（组态软件、HMI 客户端二进制）→ 用 `../thick-client/SKILL.md`
- 目标只有一段抓到但看不懂的工控 PCAP，任务是还原报文字段语义 → 用 `../protocol-reverse/SKILL.md`
- 工程站已拿下，下一步是域内横向与域控路径 → 用 `../attack-chain/SKILL.md`
- 目标是射频链路本身（遥控/传感器信号）→ 用 `../radio-sdr/SKILL.md`
- 目标是拆机看调试引脚而不是评估在跑的工艺系统 → 用 `../hardware-security/SKILL.md`

## When to Pivot

信号与判据见 `../ops/skill-pivot-contract.md`。本技能去向：

| 触发证据 | 换到 |
|---|---|
| 需要看 PLC/RTU 固件内部实现（协议私有扩展、固件版本与 CVE 对不上） | `../firmware-pentest/SKILL.md` |
| PCAP 里出现 SMB/LDAP/Kerberos，或域账户在 OT 网段做认证 | `../attack-chain/SKILL.md`：边界已经破了，按 IT 横向路径编排 |
| 工程站/历史库是 Windows，且 445/3389 有可打的服务面与落后补丁 | `../windows-ad/SKILL.md` |
| Modbus 写单个寄存器两次都没有回显或读回值不变 | 别再写第三次：换只读面（读回确认是否为只读从站），或走离线配置审计确认点位映射 |
| 扫描期间老 PLC 掉线、CPU 灯停摆、ICMP 丢包 >20% | 立即停扫并退回镜像流量：这是低速+维护窗的技术约束，不是重试能解决的 |
| 现场有 SIS 回路与过程控制同网 | 先划边界、把 SIS 路径单列，再评估其余暴露面 |
| 协议是厂商私有/加密，明文点位看不到 | `../protocol-reverse/SKILL.md`：先还原报文结构再谈利用 |
| 发现设备本身是带 Linux 的网关/协议转换器 | `../firmware-pentest/SKILL.md`：固件是攻击面，不是扫描器能回答的问题 |

## 定义完成

本技能产出算「完成」的**外部可观测**条件（不许写形容词）：

- 被动识别结果落盘（协议 → 设备 → 点位清单），并附一张「全程零写操作」的比对记录
- Purdue 分层图落盘，标出已观测到的跨层通信，未观测到的标「未观测」
- 每次主动测试都留下时间窗、速率上限与过程影响评估（会不会动到物理过程）
- 交付里区分「可远程利用」与「需物理接触才能利用」两类，不混着写

## 输出契约

```
FACT:       <观察，带来源：命令 / 文件:行 / Evidence ID>
HYPOTHESIS: <可测试断言 + confidence: high|medium|low>（状态见 `../ops/binary-model.md`）
QUESTION:   <当前最大不确定点>
NEXT:       <继续 | 换技能 | 停止（附成本判据）>
```

## 置信度词表

词表见 `../ops/confidence-vocabulary.md`。本技能特有判据：

- `confirmed`：协议/设备识别有被动抓包多次佐证，且过程量（点位值、轮询周期）在观测窗内未受扰动
- `medium`：只有单次抓包或单侧流量支持，或设备型号来自工程文件名而非流量指纹
- `low`：仅从端口开放推断是某 PLC 型号，或仅凭设备命名/IP 段猜 Purdue 层级
