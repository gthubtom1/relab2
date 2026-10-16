---
name: radio-sdr
description: RF/SDR 信号研究：调制识别、GNU Radio/URH/Inspectrum 解调、屏蔽室重放。用于：非 Wi-Fi 射频（RTL-SDR/HackRF IQ）、ADS-B/遥控/传感器协议。
---

# RF / SDR Security Research

## ACTION REQUIRED（读完后立刻执行）

1. `NOW`: **查经验卡** —— `python skills/scripts/experience-card.py search "<你看到的症状>"`。
   命中就读那张卡的 `invariant` + `decision.action`，并**逐条对照** `scope.appliesWhen`
   与 `scope.stopsWhen`：少一条前提就停用；命中任一停止条件就停。
   历史卡**不替代**当前目标的实测证据。详见 `../experience-cards/INDEX.md`。
2. `NOW`: 频谱纪律：先只收识别（中心频率/调制/带宽），发射（重放/干扰）只在屏蔽室或物理隔离频段做
3. `NOW`: 记录设备与频段；默认先收后发 —— 收全了再决定要不要发射
4. `ACT`: 只接收识别 → 解调分析 → 实验室复现评估

## 适用场景

- 非 Wi-Fi 无线链路：Sub-GHz 遥控、无线传感器、LoRa/FSK 数传、寻呼与广播类信号
- ADS-B 等公开协议信号的接收与解码
- 与 wifi-wireless 分工：本 skill 偏 **SDR 通用 RF**；802.11 攻防走 R29

## 频谱纪律（决定数据可不可信）

- **先收全再谈发射**：发射会污染现场（也会干扰自己的采集），同一时段收发交替做等于自欺。
- **增益不要拉满**：RTL-SDR 增益过载的典型读数就是「凭空多出一片镜像/谐波」，
  先把增益降到能看见噪底再逐步上调，别把过载产物当信号。
- **参数必须跟证据一起落盘**：中心频率、采样率、带宽、增益、天线、时间。
  只留一张频谱截图而不写这几项参数，等于没证据。
- **避开受保护频段**（航空/应急/海事），现场接收先查频段归属。
- **发射一律在屏蔽室或物理隔离频段**，功率最小化；无法屏蔽就改成离线回放验证。

## 识别判据（从读数到调制）

| 频谱/时域读数 | 判定 | 要补的证据 |
|---|---|---|
| 单峰包络、幅度开关、突发宽度约 1 ms 量级 | OOK/ASK（遥控类常见） | inspectrum 量位宽，反推符号率 = 1/位宽 |
| 频谱上对称双峰，间距 = 2×频偏 | FSK：频偏 = 峰间距 / 2，带宽 ≈ 符号率 + 2×频偏 | 用带宽与符号率互相校验，两个数自洽才认 |
| 出现周期性突发但每次包长/间隔不一致 | 传感器偶发上报或自适应速率 | 录 ≥20 次，比对包长、同步字与校验位 |
| 等间隔持续载波且中心频率在跳 | 跳频/扩频 | 把带宽拉到跳频跨度之上重录，画跳频图案 |
| 1090 MHz、56 位长报文、等间隔 | ADS-B（公开协议） | 直接上成熟解码器核对，不要自己猜帧格式 |
| 解出的比特流里前导/同步字固定，但载荷逐帧变化 | 有帧结构，值得还原 | 见「When to Pivot」 |
| 解出全是噪声、星座不收敛 | 参数假设错，不是信号不存在 | 见「When to Pivot」的换参数一行 |

## 工具链

| 工具 | 用途 | 定位方式与关键细节 |
|---|---|---|
| RTL-SDR（`rtl_sdr` / `rtl_fm`） | 收：录 IQ（中心频率/采样率/增益三件套一起给） | 台面设备；采样率决定可看带宽，8-bit IQ 会量化压掉小信号 |
| HackRF（`hackrf_transfer`） | 宽带收发 | 台面设备；先 `-r` 收，`-t` 发射只在屏蔽室/隔离频段 |
| GQRX / SDR# | 实时频谱：定中心频率、切调制假设 | 台面软件；找载波用，出证据要另存 IQ，截图不算证据 |
| Universal Radio Hacker (URH) | 解调、找同步字、判固定码 vs 滚动码 | 台面软件；同一按键按 ≥3 次逐位比对 |
| inspectrum | 从 IQ 看符号率、位宽、占空比 | 台面软件；位宽是符号率的硬来源 |
| GNU Radio | 自定义解调链 + CRC 校验 | 台面软件；只有校验过掉才敢说「解出协议」 |
| `tshark` / `Wireshark` | 设备网关把 RF 事件转成网络报文（UDP/MQTT）时，两侧对照 | 探测 id `tshark`；按时间戳对齐 RF 与网络两条记录 |
| `diec` | 提取物第一刀（固件/配置/固件升级包类型） | 探测 id `diec` |
| `binwalk` | 设备固件递归提取（里面才有编码表与跳频表） | 探测 id `binwalk`；探测不到就按 `../TOOLS.md` 装法补 |
| `rabin2` / `radare2` | 固件里找发送表、按键映射、CRC 表 | 探测 id `rabin2` / `radare2` |
| `Ghidra` + `analyzeHeadless` / `idat` | 反编译 MCU 固件的发送路径与滚动码算法 | 探测 id `ghidra_headless` / `idat`；与 IQ 观测互相印证，单靠静态不下结论 |
| `gdb` | 经 SWD/JTAG 调试模组，直接看调制寄存器 | 探测 id `gdb`；前端引脚面先走 `../hardware-security/` |
| `hashcat` | 固件/配置里的口令 hash 离线破解（为了读配置，不是为了解调） | 探测 id `hashcat`；先认 hash 类型再选模式 |
| `nmap` | 网关/桥接设备的管理面（单机低速） | 探测 id `nmap`；段扫不是本卡的事 |

> **空口硬件装没装，先探再动手。**
> `. C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1` → `Resolve-ReverseToolSpec -Name <id>`，拿到 `Command` 后用它给的完整路径调用；
> `Get-Command` 查空不是缺工具的证据（PATH 快照陷阱，见 `../references/env-selfcheck.md`），四级探测全 `Available=False` 才可报缺，装法见 `../TOOLS.md`。
> RTL-SDR/HackRF/URH/GNU Radio 这类接收链多在实验台而非本机；宿主侧通道用
> `powershell -NoProfile -ExecutionPolicy Bypass -File skillpack\skills\scripts\mcp-status.ps1` 看三列（注册了哪些 / 谁在监听 / 怎么起），**注册不等于在监听**。

## 参考

- `references/sdr-lab-rules.md`
- `../wifi-wireless/` `../ot-ics/` `../hardware-security/`

## 路由上下文

**上游**: MASTER R38  

## 任务完成自检

- [ ] IQ 或解调结果有没有落盘路径与参数（中心频率/带宽/采样率/增益，另附天线与采集时间）？
- [ ] 调制判定有没有依据（星座收敛、位宽、峰间距自洽），还是只看了一眼频谱形状？
- [ ] 解码结果的校验位（CRC/长度/序列号）过掉了吗？
- [ ] 有没有把发射动作与接收记录分开写清（能否离线复现，而不是靠再发一次）？

---

## When NOT to use（近邻负例）

- 目标是 802.11 Wi-Fi（要抓握手、要打 WPA/WPA3）→ 用 `../wifi-wireless/SKILL.md`
- 只要读固件里的无线配置项（信道、功率、配对表），不碰空口 → 用 `../firmware-pentest/SKILL.md`
- 还原的是有线链路上的协议报文（TCP/UDP/私有帧）→ 用 `../protocol-reverse/SKILL.md`
- 目标是 BLE/GATT 应用层（手机侧配对、特征读写）→ 用 `../mobile-reverse/SKILL.md`
- 要从板子上找无线模组的 UART/SWD 引脚，物理接触面才是主战场 → 用 `../hardware-security/SKILL.md`
- 要分析的是无人机地面站或配套 App 客户端本身 → 用 `../thick-client/SKILL.md`
- 拿到的是可疑固件/后门程序，射频只是它的传输外观 → 用 `../malware-analysis/SKILL.md`

## When to Pivot

信号与判据见 `../ops/skill-pivot-contract.md`。本技能去向：

| 触发证据 | 换到 |
|---|---|
| 比特流能过 CRC/结构校验，且出现固定同步字与稳定载荷字段 | `../protocol-reverse/SKILL.md`：还原字段语义与状态机 |
| 同一按键按 3 次，重放比特流逐位相同、没有一位偏差 | 固定码：留本卡评估重放可行性（先写在屏蔽室条件下的复现步骤） |
| 同一按键每次有一小段在变（计数器/滚动码跳变），与固定码假设矛盾 | 固定码假设被否：转固件侧看滚动算法与密钥 → `../firmware-pentest/SKILL.md` |
| 信号来自某设备，静态字符串里出现按键名/信道号，但编码规则只在它的固件里 | `../firmware-pentest/SKILL.md` |
| 抓到的帧出现 802.11 管理帧或握手特征 | `../wifi-wireless/SKILL.md` |
| 同一中心频率上两次解调都失败（输出像噪声、星座不收敛） | 别第三次重调同一参数：改假设（带宽是否盖住频偏、FSK↔OOK↔GFSK 互换、频率偏移是否已超符号率一半） |
| 频谱里突发周期不规律、包长漂移，检测不到稳定前导 | 先确认是否跳频/自适应速率：拉宽带宽重录，别在单频上耗时间 |
| 要验证重放，但当前环境无法与现场隔离 | 停止发射，改为离线回放（GNU Radio 复现链路）并记录差异 |
| 设备侧网关把 RF 事件转发到网络（UDP/MQTT/自研） | `../protocol-reverse/SKILL.md`，网络侧用 `tshark` 对着同一事件看时间戳 |

## 定义完成

本技能产出算「完成」的**外部可观测**条件（不许写形容词）：

- IQ 采样或解调结果有落盘路径与参数（中心频率/带宽/采样率/增益），可被别人重放同一实验
- 调制识别有依据（星座图收敛、位宽、峰间距自洽），不是猜
- 解调出的比特流通过校验（CRC/长度/序列号至少一样），并给出校验方式
- 可重放性评估写明「是否需要发射」；需要发射的，给出隔离条件与离线复现路径

## 输出契约

```
FACT:       <观察，带来源：命令 / 文件:行 / Evidence ID>
HYPOTHESIS: <可测试断言 + confidence: high|medium|low>（状态见 `../ops/binary-model.md`）
QUESTION:   <当前最大不确定点>
NEXT:       <继续 | 换技能 | 停止（附成本判据）>
```

## 置信度词表

词表见 `../ops/confidence-vocabulary.md`。本技能特有判据：

- `confirmed`：解调出的比特流有 CRC/结构校验通过，且同一参数重复采集能复现（不是噪声里挑出来的）
- `medium`：比特流结构清晰但校验位未过，或调制判定只有单一特征（仅峰间距或仅位宽）支持
- `low`：仅凭频谱形状猜测调制方式，或仅凭一次采集的截图下结论
