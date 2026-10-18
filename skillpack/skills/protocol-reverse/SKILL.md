---
name: protocol-reverse
description: 自定义协议逆向：TCP/UDP 帧布局还原、protobuf/gRPC 解码、WebSocket/MQTT 分析、PCAP 还原状态机。用于：有 PCAP 要还协议、未知 protobuf 恢复。
---

# Protocol Reverse Engineering

## ACTION REQUIRED（读完后立刻执行）

1. `NOW`: 读 `../field-journal/precedent-reverse.md` —— 本机做过多轮的常规操作清单，直接照做，不要停在犹豫上
2. `NOW`: **查经验卡** —— `python skillpack/skills/scripts/experience-card.py search "<你看到的症状>"`。
   命中就读那张卡的 `invariant` + `decision.action`，并**逐条对照** `scope.appliesWhen`
   与 `scope.stopsWhen`：少一条前提就停用；命中任一停止条件就停。
   历史卡**不替代**当前目标的实测证据。详见 `../experience-cards/INDEX.md`。
3. `NOW`: 确认任务是否为**协议/流量/序列化格式**逆向（非纯 Web 参数签名 → 转 `js-reverse/`）
4. `NOW`: 若有目标网络交互 → `../scripts/case-init.ps1` 建案（目标、端口、产出物落 `work/<case>/`）
5. `NEXT`: 读取 `../TOOLS.md`；缺工具 bootstrap（tshark/wireshark 等可能需手动）
6. `ACT`: 进入工作流 Phase 1，产出帧布局或消息字典草稿

## 适用场景

- 自定义 TCP/UDP 二进制协议
- Protobuf / gRPC / FlatBuffers / MessagePack
- WebSocket / MQTT / 私有 RPC
- PCAP / PCAPNG 还原字段与状态机
- 客户端-服务端校验、序列号、加密帧头

## 不走本 skill

| 情况 | 去哪 |
|------|------|
| 仅 HTTP 参数签名 / JS 加密 | `js-reverse/` |
| 仅 TLS 证书问题 | `pentest-tools/` 或浏览器代理 |
| 固件内协议栈深挖 + 仿真 | `firmware-pentest/` 后再回本 skill |

## 工作流

### Phase 1 — 采集与分诊

```text
□ 拿到样本：PCAP / 代理导出 / 客户端日志 / 二进制
□ 标记方向：C→S / S→C；是否有握手、心跳、重连
□ 固定头？魔数？长度字段？TLV？定长？
□ 是否压缩（zlib/gzip/lz4）或加密（AES/ChaCha 帧内）
□ tshark -r cap.pcap -T fields -e frame.number -e ip.src -e tcp.payload
```

### Phase 2 — 帧布局还原

```text
□ 对齐多个同类消息，找不变字节 / 自增序列号
□ 长度字段：大端/小端、含头/不含头
□ 校验：CRC16/32、checksum、HMAC 位置
□ 画出状态机：Connect → Auth → Ready → Request/Response → Close
□ 工具：Wireshark 自定义 dissector 草稿 / ImHex / 010 Editor 模板 / Kaitai Struct
```

### Phase 3 — 序列化与加密

```text
□ Protobuf：.proto 恢复（blackboxprotobuf / pbtk / protoc --decode_raw）
□ gRPC：HTTP/2 headers + protobuf body
□ 加密：找密钥派生（客户端 so/dll/JS）→ 联合 ida-reverse / js-reverse / apk-reverse
□ 重放：先无害字段再敏感操作（重放会改服务端状态，先想好回退）
```

### Phase 4 — 产物

```text
MUST 产出：
- 消息类型表（name / opcode / fields）
- 至少 1 条可复现的解码命令或脚本
- Evidence：原始 hex 摘录 + 解码结果（脱敏）
```

## 工具链

| 工具 | 必需 | 用途 | 自举 |
|------|------|------|------|
| tshark / Wireshark | 强烈建议 | PCAP 解析 | 手动 / winget |
| Python3 | 是 | 解码脚本 | 系统 |
| blackboxprotobuf | 可选 | 未知 protobuf | pip |
| ImHex / 010 | 可选 | 结构模板 | 手动 |
| IDA / r2 / Ghidra | 按需 | 客户端序列化函数 | 见对应 skill |

## 参考

- `references/protocol-workflow.md` — 帧布局与 Protobuf 速查
- 相关：`../ida-reverse/` `../js-reverse/` `../firmware-pentest/` `../pentest-tools/`

## 路由上下文

**上游**: `MASTER-ROUTING` R21 · `../routing.md`  
**下游**: 需客户端算法 → `ida-reverse`/`js-reverse`；需利用重放 → `pentest-tools`/`api-security`  
**同级**: `malware-analysis`（C2 协议）、`digital-forensics`（流量取证）


## 出口（结论回填）

回填位置：滚动报告 `assault.md`（`-Preset assault` 生成）的对应表。

- 消息布局 / 状态机还原结论 → `## findings`（类型 `proto`）
- 可复现解码命令 → `## findings` 证据列（原样写命令，不许写「已解码」）
- 对应功能行 → `## functions`（如协议还原是某功能的前提）
- 未还原的消息 / 未知字段 → `## unknowns`

判定：协议还原的成品形态是「输入 → 输出契约可复现」，不是贴一堆 hex。

## 任务完成自检

- [ ] 是否还原了消息布局或状态机（而非只贴 hex）？
- [ ] 是否有可复现解码命令？
- [ ] 是否遵守 scope / 脱敏？
- [ ] 是否回写 field-journal / 报告 Checklist？
---

## When NOT to use（近邻负例）

- 只还原 HTTP 参数签名 / JS 加密字段（sign/token 在页面 JS 里）→ `../js-reverse/`
- 目标是 browser-free 采集器 / 403/412 风控 bypass → `../web-protocol-reverse/SKILL.md`
- 只是 TLS 证书链问题（过期、自签名、固定证书）→ `../pentest-tools/` 或浏览器代理，本 skill 不处理 PKI 本身
- 固件内协议栈深挖（要先解包 / 仿真固件才能看到服务端）→ `../firmware-pentest/`，拿到可执行体后再回本 skill
- 目标是 APK/`.so` 里的序列化函数（帧结构已知，要逆算法）→ `../ida-reverse/`、`../apk-reverse/`
- 目标是游戏封包的通用规则（心跳/分片/序号）→ `../game-reverse/` 先按游戏场景分流，再回本 skill 做帧
- 已有 PCAP 但需求是数字取证（谁在什么时候发了什么）→ `../digital-forensics/`

## When to Pivot

信号与判据见 `../ops/skill-pivot-contract.md`。本技能去向：

| 触发证据 | 换到 |
|---|---|
| 帧里出现加密/压缩且密钥派生在客户端 native 里 | `../ida-reverse/` / `../apk-reverse/` 定位密钥例程，回来后继续 |
| 密钥/签名逻辑在浏览器 JS | `../js-reverse/`，回来后继续 |
| 目标协议宿主是固件 / IoT 设备 | `../firmware-pentest/`（Stage 6+ 仿真），回来后继续 |
| 需求转成对还原后协议的利用 / 重放攻击 | `../pentest-tools/`、`../api-security/` |
| PCAP 本身是取证对象（时间线、入侵溯源） | `../digital-forensics/` |
| C2 协议 + 恶意样本主体 | `../malware-analysis/SKILL.md` |

## 定义完成

本技能产出算"完成"的**外部可观测**条件（不许写形容词）：

- 消息类型表落盘：`name / opcode / fields`（字段含类型、长度、字节序），至少覆盖握手 + 一条业务消息
- 至少 1 条**可复现**的解码命令或脚本（原样贴命令，输出与本文件中的 hex 摘录对得上）
- Evidence 落盘：原始 hex 摘录 + 解码结果（脱敏），位置在 PCAP 或日志里可回溯（帧号 / offset）
- 状态机画成 `Connect → Auth → Ready → … → Close` 的可引用图，且至少有一条完整握手序列被实际观测到
- 未还原的消息 / 未知字段显式进 `## unknowns`，不许留空白
- `assault.md` 回填写实：布局结论 → `## findings`（类型 `proto`），可复现命令 → 证据列

## 输出契约

```
FACT:       <观察，带来源（命令 / 文件:行 / Evidence ID）>
HYPOTHESIS: <可测试断言 + confidence: high|medium|low>  （状态见 ../ops/binary-model.md）
QUESTION:   <当前最大不确定点>
NEXT:       <继续 | 换技能 | 停止（附成本判据）>
```

## 置信度词表

词表见 `../ops/confidence-vocabulary.md`。本技能特有判据：

- `confirmed`：同一字段位置在**多条同类消息**上对齐成立（自增序号 / 长度字段随 payload 变化），且用同一份解码脚本对 ≥3 帧输出结构一致
- `low`：只从单条消息猜出的字段语义（尤其是定长字段边界、含头/不含头的长度字段）；或"高熵 = 加密"未排除压缩可能
