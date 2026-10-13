# 有状态流端到端加密手册（Stateful Stream E2EE Playbook）

> **来源声明**：改编自 `aoyunyang/spider-king-skill`（MIT License）的 `stateful-stream-e2ee-playbook.md`。英文原文译为中文，术语保留英文原词并附中文，按本包六段式规范重排。
>
> **什么时候用**：目标要经过登录、配对（pairing）、扫码或某种预热握手（warm-up handshake）之后才变得有用；真正的业务契约在一个长连接 WebSocket 或其他有状态流上。
>

> ★★ **本机 playwright 必须显式指定浏览器**（2026-10-10 实测）：
> `launch()` 默认启动会报 `Executable doesn't exist at %LOCALAPPDATA%\ms-playwright\chromium_headless_shell-1234\...`
> —— python 包期望 1234，本机装的是 **1243**，版本号对不上。
> **可用写法**：`p.chromium.launch(channel="msedge")`（实测能起、能渲染、能读 DOM），
> 或 `launch(executable_path=<显式路径>)`。照抄裸 `launch()` 一定失败。
> 
>
> **定位说明**：这是本包中**相对其他技能的一篇增量** —— 它把「有状态会话建立」提升为协议契约的一等部分。通用协议逆向方法见 `../../../protocol-reverse/SKILL.md`。

---

## 适用信号（Recognition signals）

- 目标只有在登录、配对、扫码或另一种预热握手**之后**才变得有用
- 真正的业务契约位于一个长连接 WebSocket 或其他有状态流上
- 早期帧返回的是 ref、公钥、client ID、挑战 blob 或会话种子，**而不是业务数据**
- 后续帧是二进制的、protobuf 的，或其他在恢复 key、counter 或 tag 之前不可读的形式
- 媒体元数据一眼可见，但媒体重放或解密需要一个**单独派生的秘密**

## 前置（Entry conditions）

1. **一份完整的成功 transcript（会话记录）**。这是本篇的第一前提 —— 没有「从首次接触到一条可读业务事件」的完整序列，后面全免谈。本机抓 WebSocket 帧的途径：
   ```powershell
   # 方式一：浏览器侧走 CDP/代理（本机 playwright 可用），导出 ws 帧日志
   # 方式二：mitmproxy 对 WebSocket 有帧级支持（本机可用）
   & (Resolve-ReverseToolSpec -Name 'mitmdump').Command -p 8899 --set websocket=true -w ws.mitm
   ```
   `reqable` 本机无，HAR 导出路径不适用。
2. **Python 流客户端**。本机 `websockets` 库可用，是最终交付的首选。
3. **一条可行的配对/登录路径**（若需要）。涉及账号授权的纪律见 `session-contract-playbook.md`。
4. **一个明确的最小里程碑定义**：什么叫「一条可读的业务帧」。开工前就要说清，否则会无限扩张成「把整个协议实现一遍」。

## 步骤（Working method）

### 核心规则

**有状态会话建立是协议契约的一部分。**

**不要把这一类目标化约成一个假的「sign」字段。** 流协议里没有「一个签名字段」这回事 —— 状态是分布式的、时序的、跨帧的。

### 五条浓缩教训（Distilled lessons）

1. **冻结会话 bootstrap，而不只是载荷。**
   把入口路由、流 URL、upgrade 头、登录或配对帧、auth ack、心跳、以及**一条业务帧**，当作**一份 transcript** 一起抓。

2. **在解析载荷语义之前，先把帧族分开。**
   先归桶：**bootstrap / auth / keepalive / business / receipt / reconnect / media 相关**。不先分桶，你会把心跳当业务数据解。

3. **在责怪解码之前，先恢复 key schedule（密钥编排）。**
   业务帧一直不透明时，先确认问题出在哪一环：密钥派生（key derivation）、counter 漂移、tag 顺序、压缩、protobuf、还是一个真的解析 bug。**这六者要先排除，不要一上来就 debug 解析器。**

4. **把 counter 和 tag 当作一等状态。**
   消息 ID、epoch、counter、ack tag —— **若流在缺它们的情况下会死，它们就不是可选噪声**。

5. **把媒体派生与聊天载荷解码分开。**
   业务消息可能只承载元数据，而下载或解密走的是**另一条**派生路径。

### 工作法

1. **冻结一份成功 transcript。**
   保存从首次接触到**一条可读业务事件**的确切预热序列。

2. **分层记录。**
   分别记录：
   - 传输层 upgrade 与头
   - 登录或配对 bootstrap 产物
   - key schedule 或 secret 更新路径
   - 帧信封（frame envelope）格式
   - 载荷解码链
   - 媒体派生路径

3. **证明最小的本地里程碑。**
   重建**一个**本地会话，不带浏览器，抵达**一条**业务帧。

4. **会话稳定后才扩容。**
   第一个稳定的本地会话**反复成功之后**，才加订阅、分页、重连、回执处理和媒体。

### 必须回答的问题（Questions that must be answered）

- 究竟**哪个 bootstrap 产物**让这条流变得可读？
- 哪些帧是**客户端必须发的**，哪些是**服务器分配的**？
- 哪些 counter、tag 或 epoch **必须在本地推进**？
- 认证状态**可复用**，还是**每会话必须刷新**？
- 载荷解码是压缩、protobuf、自定义二进制、加密，还是**若干层的叠加**？
- 媒体 key 是从消息载荷派生、从一个旁路端点取、还是来自存储的会话状态？

## 判据（Evidence checklist / Verification）

以下**全部**成立，才算这一类目标走通：

1. **一份完整的成功会话 transcript**
2. **一条原始的加密或二进制业务帧**
3. **一条解码后的业务帧，且能与上面那条原始帧一一对应**（不是另一次抓取的另一条帧 —— 对应关系是这一条最容易被糊弄过去的判据）
4. **任何恢复出来的 key schedule helper，都有一次定输入（fixed-input）验证**
5. **一份把帧族映射到各自角色的说明**
6. **一份说明媒体处理是否在范围内、以及它的 key 路径如何工作的文档**
7. **最小本地里程碑达成**：一个不带浏览器的本地会话抵达一条业务帧，且**可重复**
8. **最终采集器仍是本地协议代码**：
   - Python + 本地 WebSocket / 流客户端
   - 本地握手 bootstrap
   - 本地帧构造器或解析器
   - 本地 protobuf / 压缩 / 二进制信封解码器
   - 仅当「已验证的移植」成本更高时，才引入最小隔离的 JS 或 WASM helper

### 不可接受的交付（Not acceptable）

- **留着浏览器开着**以维持登录态
- **把页面上下文重放或 CDP 作为最终路径**
- **在 key schedule、tag 规则和媒体派生都检查过之前**，就宣称这个目标「只能浏览器」

第 3 条是本文最重要的一条纪律 —— 「浏览器专属」是一个需要**举证**的结论，不是放弃的借口。

## 常见坑（Common traps）

- 把「登录了」当成「流可读了」—— 中间还有整个预热序列
- 不分帧族就解载荷，把心跳/回执帧当业务数据
- 业务帧不透明时，直接去 debug 解析器，而没先排除 key 派生、counter 漂移、tag 顺序
- 把 counter / epoch / ack tag 当噪声丢掉，然后困惑于「流为什么会死」
- 用聊天载荷的 key 去解媒体，或反之
- 第一个本地会话还没稳定就急着加订阅和重连
- 拿「A 时刻抓的原始帧」去对「B 时刻解出的明文帧」，声称对上了
- 恢复出 key schedule helper 后没做定输入验证
- 留着浏览器当最终路径，只是「先用浏览器跑通」就一直没换掉
- 没检查媒体派生路径就宣称目标已完成

## 相关（Related）

- `../../../protocol-reverse/SKILL.md` —— **本篇的上位技能**：通用协议逆向方法；本文是其「有状态流」子类
- `session-contract-playbook.md` —— 流建立之前的登录/会话契约分层
- `multi-context-session-playbook.md` —— 配对/登录涉及可变业务上下文时
- `async-export-job-playbook.md` —— 有状态流之外的另一类异步业务流（轮询式导出）
- `../crypto/pattern-atlas.md` —— protobuf、自定义二进制信封、key schedule 常见模式索引
- `../crypto/offline-inline-deob-playbook.md` —— 客户端侧 key 派生逻辑的离线拆解
- `../observe/hook-techniques.md` —— 流建立阶段的请求/帧钩子
- `../deliver/pure-python-rebuild-playbook.md` —— 判据第 8 条「仍是本地协议代码」的交付规程
- `../contract/report-templates.md` —— 判据第 5、6 条的落盘模板

---

## 源文档勘误（改编时修正）

1. **源文档 `Acceptable handoff` 节的 `Not acceptable` 第 3 条**（calling the target "browser-only" before key schedule, tag rules, and media derivation are checked）是全篇**最重要**的一条纪律，却被放在「不可接受交付」的末尾，容易被略读。本文把它提升为「不可接受交付」列表的第 3 条并加粗，同时在核心规则处重申。
2. **源文档的 `Evidence checklist` 有 6 条，但 `Acceptable handoff` 是独立的第 7 组**。源文档没有说明这两者如何合成验收 —— 实际上「Evidence checklist」管证据齐不齐，「Acceptable handoff」管交付形态可不可接受。本文把后者拆成判据第 7、8 条合入同一张清单，并明确判据第 3 条「原始帧与解码帧必须一一对应」是源文档隐含但未写出的关键要求（源文档只并列列出 `one raw ... frame` 与 `one decoded ... frame tied to the raw frame above` —— 原文其实**有** `tied to the raw frame above` 这半句，本文把它显式化为可检验的对应关系判据）。
3. **源文档 `Distilled lessons` 第 3 条**列了 6 个可能原因（key derivation, counter drift, tag ordering, compression, protobuf, or a real parser bug），但 `Questions that must be answered` 第 5 条又问「whether payload decode is compression, protobuf, custom binary, encryption, or a stack of several layers」—— **两处清单不一致**（前者无「encryption」「stack of layers」，后者无「counter drift」「tag ordering」）。这是源文档的真实不一致，本文按原文分别保留于对应段落，并在两处都标注为「需逐项排除的清单」，而非合并成一份权威清单，避免替源文档做裁定。
4. **源文档无「适用信号」独立段落**（信号混在导语的 `Use this reference when:` 列表里）。本文按本包六段式规范将其独立为「适用信号」。