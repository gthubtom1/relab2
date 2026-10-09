# 结构化传输手册（Structured Transport Playbook）

> **来源声明**：本文改编自外部仓库 `aoyunyang/spider-king-skill`（MIT License）的 `structured-transport-playbook.md`。原始内容为英文原文，此处译为中文并按本包六段式规范重排；技术术语保留英文原词并附中文。改编中补齐了判据段（本包硬性要求）并删除了失效的脚本引用（见文末「源文档勘误」）。
>
> **什么时候用**：目标的**传输形状本身**就是协议契约的一部分时 —— GraphQL、WebSocket 帧、protobuf/msgpack 二进制信封，或者消息 ID / operationName / channel / opcode 和可见业务字段同等重要。
>
> **平台与本机状态**：`python 3.12.0`（`D:\EXE\python\python.exe`）**本机可用**，`protobuf` / `msgpack` 均可作为纯 Python 解码依赖。抓帧用 `tshark 4.6.8`（`D:\Tools\Wireshark\tshark.exe`）或 `mitmdump 12.2.3`（`D:\EXE\python\Scripts\mitmdump.EXE`）；**本机 `reqable` 无**。`iv8` **本机无**；静态 AST 那套（`esprima`/`acorn`/`@babel/parser`）**本机未装**。

---

## 适用信号（Recognition signals）

- 目标用 **GraphQL** 而不是普通 REST
- 业务契约住在 **WebSocket 帧**里
- body 或帧载荷是 **protobuf、msgpack 或其他二进制信封**
- **消息 ID、operationName、channel、opcode** 和可见业务字段一样重要
- 一个 `200` 或 `grpc-status: 0` 拿到了，但解不出预期的业务消息

## 前置（Entry conditions）

1. **有一份已冻结的可用样本**（一条已知好的请求或一帧）。
2. **知道原始字节从哪来**：`tshark` 从 pcap 抽，或从已授权的 live replay 直接落盘二进制。
3. **落盘位置**按 `../contract/project-artifact-contract.md`：原始字节属于 volatile evidence，放 `<project>/js_reverse_cache/tasks/<task-id>/`，**不要**写进本技能包目录。

## 步骤（Working method）

> **核心规则：传输形状是协议契约的一部分。**

1. **确定传输种类：**
   - GraphQL query 或 mutation
   - WebSocket 请求-响应
   - WebSocket 流
   - HTTP 上的 protobuf 或 msgpack
   - 自定义二进制信封

2. **冻结一份已知好的请求或帧样本**

3. **把四类字段分开：**
   - **envelope fields（信封字段）**
   - **business fields（业务字段）**
   - **sequencing fields（时序字段）**
   - **signature or token fields（签名/token 字段）**

4. **确定哪些是服务端分配的，哪些是客户端必须自己重建的**

5. **在扩展到流或分页之前，先在本地重放一个稳定样本**

### GraphQL 注意事项

- 对比 `operationName`、`variables` 与 persisted-query 哈希
- 留意 wrapper header 或 origin 检查
- 确认到底需要 query 文本、哈希，**还是两者都要**

### WebSocket 注意事项

- **先给消息类型做指纹，再去读单帧内容**
- 识别 auth 帧、subscribe 帧、heartbeat 帧、业务帧
- **当服务端期望一段预热序列时，保留顺序**

### 二进制信封注意事项

- **冻结原始字节**
- 识别字段边界或 parser 函数
- 确认**压缩发生在结构化解码之前还是之后**

### gRPC 与 grpc-web 分帧

**把每一帧都当作一份线上契约：**

1. 字节 0 是帧标志（frame flag）
2. 字节 1 到 4 是**无符号大端**载荷长度
3. 接下来的 `length` 字节**恰好是一条**消息载荷
4. 重复直到 body 或流耗尽

**不要把每个非零标志都当成 `zlib`。** 从 header 与运行时证据解析出 `grpc-encoding` 或当前生效的 grpc-web 契约。对 grpc-web：

- 区分 data 帧与 trailer 帧
- 保留传输编码（`application/grpc-web+proto` vs 文本 / Base64）
- **解析每一帧，而不是只解第一个载荷**

### 本机的帧结构检查

源文档用 `scripts/grpc_frame_inspector.py` 做有界结构检查 —— **该脚本在本包 `web-protocol-reverse/scripts/` 目录中不存在**。本机替代做法（**未在本机对具体目标验证**）：

```powershell
# 1) 用 tshark 直接抽出 grpc-web 帧的十六进制（本机可用）
D:\Tools\Wireshark\tshark.exe -r flow.pcapng -Y "http2.data.data" -T fields -e http2.data.data

# 2) 用 Python 按本文的分帧契约做一次有界检查（只打印 flags/length/offset）
D:\EXE\python\python.exe -c "d=bytes.fromhex(open('frame.hex').read().strip()); i=0
while i+5<=len(d):
    flag=d[i]; ln=int.from_bytes(d[i+1:i+5],'big')
    print('flag',flag,'len',ln,'offset',i)
    assert ln<=len(d)-i-5, 'truncated'
    i+=5+ln"
```

上述脚本**默认只输出 flags / kind / length / offset**，不打印载荷字节、不选择压缩 codec、不解码 protobuf 字段 —— 遵循源文档「不做过度自动化」的意图。**敏感载荷的 SHA-256 默认关闭**；只在任务本地做关联时才启用，因为敏感载荷的稳定哈希不适合公开。

## 判据（Verification checklist）

**「结构化传输已解决」= 以下全部为真：**

1. **原始字节已冻结落盘**，可重放出同样的哈希。
2. **信封 / 业务 / 时序 / 签名四类字段被显式区分**，不是只留最后一类。
3. **传输种类已明确命名**（GraphQL / WS / protobuf / msgpack / gRPC / 自定义信封）。
4. **gRPC 分帧门全部通过**：
   - 拒绝被截断的 5 字节头，以及超出可用字节的载荷长度
   - 用固定字节证明单帧与多帧解析都正确
   - schema 不完整时**保留未知 protobuf 字段或原始载荷字节**
   - **解码后的消息**与**重新编码后的帧字节**分别比对（两者是不同层次）
   - 有一个**篡改了长度、标志或 trailer 边界**的负对照
5. **HTTP `200` 或 `grpc-status: 0` 之前，必须已解码并消费掉预期的业务消息** —— 否则不算成功。
6. **压缩 / 加密 / 签名的确切顺序已记录**，不是「大概是 先解帧再解压」。
7. **最终交付仍是本地协议代码**：HTTP + GraphQL body、WebSocket 客户端 + 本地帧构造/解析、或 Python + 本地 protobuf/msgpack 解码器 —— **不含浏览器运行时**。

## 常见坑（Common traps）

- 把每个非零帧标志都当成 `zlib`
- 只解第一帧就宣布成功
- 把 trailer 帧当 data 帧解析
- 跳过信封层直接解业务字段
- 解码后的消息对了，但**重新编码的帧字节**不对（分隔符、字段顺序、压缩、长度前缀任一不一致）
- 序列字段错了（消息 ID 单调性、heartbeat 缺失、预热顺序）
- 在扩展到流或分页之前没有先在本地重放一个稳定样本
- 本机**没有 `reqable`**，却去找 HAR 历史 —— 本机用 `tshark` / `mitmdump`
- 本机**没有 `iv8`**，但源码里的 gRPC 客户端需要浏览器语义才能跑 —— 那说明这条不该走运行时，见 `../crypto/iv8-runtime-cheatsheet.md`（形态未在本机验证）

## 相关（Related）

- `./transport-pre-gate-playbook.md` —— 传输层准入没过时，帧层根本看不到
- `./transport-wrapper-playbook.md` —— 「解码对了但 slot 放错」
- `./dual-writer-param-playbook.md` —— 同一个帧里有多个写入者
- `../deliver/response-decode-playbook.md` —— 解码链的通用步骤
- `../state/stateful-stream-e2ee-playbook.md` —— 有状态流与端到端加密
- `../principles/doctrine-index.md` —— 教条 9（有状态流是协议）、教条 12（包封装与密码学是两套契约）
- `../deliver/delivery-gate-playbook.md` —— 第 5 条「decode 路径本地化」的验收位置

---

## 源文档勘误（改编时修正）

1. **源文档的 `Verification gates`（gRPC 分帧那 6 条）被放在 `gRPC and grpc-web framing` 小节内部，没有独立标题**，与前面的 `GraphQL notes` / `WebSocket notes` 结构不对称，读者容易把它当成只对 gRPC 生效的附属条款。改编把它提升为判据第 4 条的一组子门，与其他传输种类并列。
2. **源文档引用 `scripts/grpc_frame_inspector.py`（以及它提到的 `--include-payload-sha256` 开关），但本包 `web-protocol-reverse/scripts/` 目录不存在，该脚本全仓库也搜不到。** 改编**删除该脚本引用**，给出本机 `tshark` + `python` 的实际等价做法（只打印 flags/length/offset，不打印载荷），并保留源文档「敏感载荷哈希默认关闭」的安全意图。
3. **源文档的 `Acceptable handoff` 段与 `Working method` 第 5 步重复**（都在说「先在本地重放一个稳定样本」）。改编保留第 5 步为步骤、判据第 5 条为验收条件，把 `Acceptable handoff` 的内容并入判据第 7 条（最终交付仍是本地协议代码），**不再单列小节**，避免同一事实出现两遍而让读者以为是两条独立要求。
4. **源文档「Working method」第 4 步写「确定哪些是服务端分配的，哪些是客户端必须自己重建的」，但没有把它落进任何验收条件。** 改编在判据第 2 条要求「四类字段被显式区分」，正是把这一步变成可检查项。
5. **源文档的 `Binary envelope notes` 说「确认压缩发生在结构化解码之前还是之后」，而 gRPC 小节说「常见形状是 解帧 → 解压 → protobuf，但捕获字节与生效的 parser 才是权威」。** 两处口径一致，但源文档没点明这是同一条原则。改编在判据第 6 条把它合并成一条「顺序以捕获字节与生效 parser 为准」的显式要求。
