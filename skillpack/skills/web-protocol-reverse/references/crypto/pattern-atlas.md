# 模式图谱（Pattern Atlas）

> **来源声明**：本文改编自外部仓库 `aoyunyang/spider-king-skill`（MIT License）的 `pattern-atlas.md`。原文为英文，此处译为中文并按本包六段式规范重排；技术术语保留英文原词并附中文，AI 检索时中英文均可命中。源文档全部 26 个 Pattern 的技术内容经逐条核对，**未发现编造的常量或错误的算法描述**，未作技术性修改。
>
> **什么时候用**：目标**已经**像某个复现过的模式，并且你想知道**最短的、已被验证的第一手**是什么。
>

> ★★ **本机 playwright 必须显式指定浏览器**（2026-10-10 实测）：
> `launch()` 默认启动会报 `Executable doesn't exist at %LOCALAPPDATA%\ms-playwright\chromium_headless_shell-1234\...`
> —— python 包期望 1234，本机装的是 **1243**，版本号对不上。
> **可用写法**：`p.chromium.launch(channel="msedge")`（实测能起、能渲染、能读 DOM），
> 或 `launch(executable_path=<显式路径>)`。照抄裸 `launch()` 一定失败。
> 

---

## 适用信号（Recognition signals）

本文不是「症状大全」，而是**「我认出这个形状了，然后呢」**的速查表。

先做三件事，再往下查：

1. 找到**真实网络请求**（不是页面里写的那个）
2. 找到**真实回放时的失败点**
3. 确认**是否存在挑战 / 包装层**（Pattern D / I / I2 / Z）

然后按字母匹配下面的 Pattern。

### 目录

| 组 | Pattern |
|---|---|
| 端点/参数层 | [A 页面上的端点是假的](#pattern-a页面上的端点是假的) · [B 业务参数是诱饵](#pattern-b业务参数是诱饵) · [V 显示标签不是协议 id](#pattern-v显示标签不是协议-id) |
| 封装层 | [C 标准 helper 被 patch](#pattern-c标准-helper-被-patch) · [D 首个响应不是数据而是 bootstrap](#pattern-d首个响应不是数据而是-bootstrap) · [J 响应数据被编码/压缩/拆分](#pattern-j响应数据被编码压缩或拆分) · [L 公开页仍藏 bootstrap 封套](#pattern-l公开页仍藏-bootstrap-封套) · [N 挑战生成的状态把守共享封套族](#pattern-n挑战生成的状态把守共享封套族) |
| 会话/状态层 | [E 只有一页坏](#pattern-e只有一页坏) · [F 答案或数据绑定账号](#pattern-f答案或数据绑定账号) · [G 极小的旁路资产承载整个 signer](#pattern-g极小的旁路资产承载整个-signer) · [T 登录态与业务上下文是两个状态](#pattern-t登录态与业务上下文是两个状态) |
| 传输层 | [K 传输是 GraphQL / WebSocket / 二进制封套](#pattern-k传输是-graphql--websocket-或二进制封套) · [M 有状态的 WebSocket 会话 + 加密业务帧](#pattern-m有状态的-websocket-会话-加密业务帧) · [Q 传输前置门挡住了干净基线](#pattern-q传输前置门挡住了干净基线) |
| 挑战/验证层 | [I 一次性验证器/验证码/点选挑战](#pattern-i一次性验证器验证码点选挑战) · [I2 云验证器多阶段转录](#pattern-i2云验证器多阶段转录) · [R 挑战运行时已经知道答案](#pattern-r挑战运行时已经知道答案) · [Z 挑战重写业务 URL](#pattern-z挑战重写业务-url) |
| 隐藏载荷层 | [H 动态字体藏载荷](#pattern-h动态字体藏载荷) · [W 创建成功但无新导出任务](#pattern-w创建成功但无新导出任务) |
| 分页/重放契约层 | [O 分页路由中途换族](#pattern-o分页路由中途换族) · [P 解析后的属性对回放关键路由撒谎](#pattern-p解析后的属性对回放关键路由撒谎) · [S 业务响应是一个刷新契约](#pattern-s业务响应是一个刷新契约) · [X 轮询复用了历史成功任务](#pattern-x轮询复用了历史成功任务) · [Y 首次创建与重新生成是不同的契约](#pattern-y首次创建与重新生成是不同的契约) · [U 激活看着成功但数据范围是陈旧的](#pattern-u激活看着成功但数据范围是陈旧的) |

---

## 前置（Entry conditions）

1. **至少一条成功样本 + 一条失败样本**。没有 diff 基线，Pattern 无法验证。见 `../triage/positive-sample-hygiene-playbook.md`。
2. **wire 可见性**。本机两条路都可用：
   ```powershell
   # 方式一：mitmproxy 实时改写/观察（本机可用）
   & (Resolve-ReverseToolSpec -Name 'mitmdump').Command --listen-port 8899 --save-stream-file flow.mitm
   # 方式二：tshark 离线读已抓的 pcap（本机可用）
   & (Resolve-ReverseToolSpec -Name 'tshark').Command -r flow.pcapng -Y "http.request" -T fields -e http.request.full_uri -e http.request.method
   ```
   ⚠ 源文档提到的 `reqable` **本机无**，抓包一律用上面两条。
3. **一份可写死的「最短第一手」判据**。见下面「判据」段 —— 这份图谱的价值全在判据上。

---

## 步骤（Working method）

### Pattern A：页面上的端点是假的（The endpoint on the page is fake）

**症状**：
- 页面代码 hook 了 `/api/match/...`
- wire 上实际走的是 `/api/question/...` 或别的路径
- 浏览器里请求成功，但回放可见的那个路径失败

**动作**：
- **信任网络路径**，不信任源码里的字符串
- 追踪请求发起者（request initiator）
- 把诱饵路径记录下来（**作为文档，不作为代码**）
- **只对真实路径编码**

---

### Pattern B：业务参数是诱饵（The business param is a decoy）

**症状**：
- 页面代码构造 `token`
- wire 上实际发的是 `m`、`f` 或另一个字段
- 请求 wrapper（包装器）在发送前改写了数据

**动作**：
- **先逆 wrapper**，再逆参数
- 把业务层参数与最终 payload 做 diff
- **重建 wrapper 逻辑，而不是那个诱饵字段**

---

### Pattern C：标准 helper 被 patch（Standard helper is patched）

**症状**：
- 存在 `md5`、`btoa`、`atob`、`sha1` 或类似名字
- 用标准库在本地复现，**和浏览器输出对不上**

**动作**：
- 冻结固定测试向量
- 移植**那个确切的实现**，不是标准算法
- **在把 helper 用进请求之前**，先验证 helper 输出

详见 `crypto-patterns.md` 的「标准摘要家族被魔改」一节。

---

### Pattern D：首个响应不是数据，而是 bootstrap（First response is not data, but bootstrap）

**症状**：
- 首个请求返回 JS、`Set-Cookie`、offset 脚本、或挑战 token
- 首个请求返回非终态 HTML（如 `412`）+ 内联 bootstrap 状态 + 一个或多个链接的挑战资产
- 只有处理完 bootstrap 响应之后回放才生效
- 同一个文档 URL，要等挑战状态重建后**再过一次**才返回真实 HTML

**动作**：
- **把 bootstrap 当作协议契约的一部分**
- 测试「被挑战的文档路由本身是不是真实业务路径」
- 本地执行或模拟它
- 把产出的 cookie / globals 带进下一个请求
- **用语义锚点验证回放，而不是只看 status**

---

### Pattern E：只有一页坏（Only one page breaks）

**症状**：
- 第 1 到 4 页正常
- 第 5 页失败，或返回线索、字符串、或反爬信号

**动作**：
- 逐页 diff headers 与 cookies
- 测试页级 `User-Agent`、referer、或顺序规则
- **把例外窄化编码**（只对这一页特判，不要全局特判）

---

### Pattern F：答案或数据绑定账号（Answer or data is account-bound）

**症状**：
- 页面文案提到 `sessionid`
- 不同账号产生不同的和值或答案
- 只有采集数据的**同一个会话**能提交成功
- **或相反的陷阱**：页面文案声称 session 参与签名，但列表路由**已经匿名返回全量数据**

**动作**：
- **先从 wire 行为证明这个说法**，再把 session 材料写死进 signer
- 只对**确实需要**的链路把 session 输入显式化
- 答案绑定账号时，**采集与提交必须同账号**
- wire 显示有分裂时，**把匿名采集与「仅登录可提交」分开**
- **先确认是同一个 session，再去怀疑 signer 逻辑**

---

### Pattern G：极小的旁路资产承载整个 signer（Tiny side assets carry the whole signer）

**症状**：
- `.wasm`、`/offset`、挑战 JS、或字体文件看起来很「轻」
- 主 bundle 很吵，但**旁路资产的变化对输出有决定性影响**

**动作**：
- **尽早**检查旁路资产
- 本地 instantiate WASM
- 本地执行 bootstrap JS
- 本地解码字体

---

### Pattern H：动态字体藏载荷（Dynamic fonts hide the payload）

**症状**：
- 数值以字形（glyph）或无意义文本形式出现
- 响应中包含字体 URL 或内嵌字体数据

**动作**：
- 拉取字体资产
- 推导 码位→数字（codepoint-to-digit）映射
- 本地解码载荷

---

### Pattern I：一次性验证器、验证码或点选挑战（One-shot verifier, captcha, or click challenge）

**症状**：
- 下一次请求只有在一个验证步骤之后才生效
- 业务 API **没有**有意义的 JS signer

**动作**：
- **把验证器输出当作真正的动态参数**
- **以协议形式**求解并回放该验证器
- **最终方案里不要模拟点击**

---

### Pattern I2：云验证器多阶段转录（Cloud verifier multi-stage transcript）

**症状**：
- 最终 verify 只是更长有序链中的一步
- 接受之前，device / warm-up / log / telemetry 主机先被触发
- 完整的 profile 基线与之后的稀疏包或增量包**必须一致**
- HTTP 200 或 sidecar 上传成功，**仍然**以「风险类拒绝」告终
- 业务 URL 只有在附上**同一轮**的 grant 之后才接受

**动作**：
- 把 `init -> sidecars -> verify -> 首个下游消费者` **冻结为一条完整转录**
- **在**调答案或轨道参数**之前**，先建**单变量消融矩阵**（ablation matrix）
- 强制共享基线与稀疏增量一致性
- 把 结构 / sidecar / 时间线 / 答案 / 环境 五个风险面**分开**
- 双运行时 helper 只作为本地计算打包，**HTTP 仍由 Python 拥有**

**本包内相关文档**：
`../triage/verifier-replay-playbook.md` · `../triage/verifier-error-localization-playbook.md` · `../triage/positive-sample-hygiene-playbook.md`

---

### Pattern J：响应数据被编码、压缩或拆分（Response data is encoded, compressed, or split）

**症状**：
- HTTP 状态正常，但 payload 看起来像乱码、数字汤、转义代码、字形、或二进制
- 业务数据只有经过 decode helper、字体映射、protobuf 解析器、或压缩层之后才出现
- 响应体的形状是**在本地 decode 之后**变的，**不是**再发一次请求之后变的

**动作**：
- **先冻结原始 payload**
- 追踪原始 payload 的**第一个消费者**
- 识别 decode 顺序、密钥、映射、或解析器
- 本地重建 decoder
- **在规模化之前**，先在**那条确切抓到的 payload** 上验证本地 decode

---

### Pattern K：传输是 GraphQL、WebSocket、或二进制封套（Transport is GraphQL, WebSocket, or a binary envelope）

**症状**：
- URL 稳定，但 `operationName`、帧类型、或二进制 opcode 在变
- 请求体带嵌套 `variables`、消息 ID、或通道名
- 真实契约在**封套结构**里，而不只是某一个可见参数

**动作**：
- **显式记录传输种类**
- 冻结一条已知良好的消息或请求体样本
- 把封套字段与业务字段**分开**
- 识别哪些字段是被签名的、有序的、或服务端分配的
- **在尝试全流采集之前**，先本地回放一条稳定消息

---

### Pattern L：公开页仍藏 bootstrap 封套（Public page still hides a bootstrap envelope）

**症状**：
- 页面或首页公开可见
- 某个早期端点返回公钥、config blob、nonce seed、或短字符串，**而不是业务数据**
- 真实业务请求 post 的是一个 wrapper，如 `{"param":"..."}`，而非可见表单字段
- 紧凑 JSON、摘要、时间戳、以及加密或编码**按某个特定顺序**施加
- 列表 API 能用，但详情或提交 API 可能仍受权限限制

**动作**：
- 打一次真实入口路由，**抓下界定公开会话的 cookies**
- 冻结一份 bootstrap 响应与一条成功的业务请求
- **精确证明封套构建顺序**：原始 payload → 紧凑序列化 → 签名输入 → 时间戳/nonce 注入 → 最终 wrapper 对象 → 加密或编码 → 外层传输字段名
- RSA 或类似分组密码封装载荷时，**验证长消息分块规则**
- **让 category / mode / page 参数显式化**，不要信 UI 默认值或空值
- **分别记录列表访问与详情访问**，避免把「公开列表」误当成「完全公开数据」

---

### Pattern M：有状态的 WebSocket 会话 + 加密业务帧（Stateful WebSocket session with encrypted business frames）

**症状**：
- 目标大部分时间空闲，直到 login / pairing / 或一段短的 warm-up 交换完成
- 一条或多条早期消息带 ref、公钥、client ID、secret seed、或挑战 blob
- 后续帧是二进制或 protobuf，在派生出会话密钥或计数器之前**读不懂**
- 流除非保留 auth、ack、心跳、重连、或消息 tag 规则，否则会断
- 媒体元数据可见，但**媒体下载或解密需要与消息载荷分开推导**

**动作**：
- **冻结一条完整的成功转录**：bootstrap、login 或 pairing、auth ack、心跳、以及一条业务帧
- **读载荷语义之前**先把帧族分开：bootstrap、auth、keepalive、business、receipt、media
- **在怀疑 protobuf 或压缩之前**，先恢复精确的 key schedule（密钥编排）或会话密钥更新路径
- **显式记录**消息 tag、计数器、重放边界
- **先证明一条稳定的本地会话**，然后再加流采集、重连、或媒体处理

---

### Pattern N：挑战生成的状态把守共享封套族（Challenge-generated state gates a shared envelope family）

**症状**：
- 入口 HTML 与挑战 JS 必须先跑，业务回放才稳定
- 一个派生 cookie、storage 项、或 preflight token 把 session、页面挑战、与环境模型绑在一起
- 业务路由同时依赖若干协同字段，例如 cookie、URL query、header token、以及编码后的 body
- URL query、body、response、有时还有 cookie，**看起来是同一包族的变体**，而非互不相关的格式
- 包分帧（framing）除内层密码外，还含字段前缀、版本标记、校验字节、自定义字母表、动态前缀、或状态派生切片
- preflight token 请求返回同一编码族，并为后面的 header 或请求字段**播种**

**动作**：
- **冻结一条新的两阶段转录**：入口 HTML、挑战 JS、派生 cookie 或 storage 状态、preflight token 请求与响应、以及一条业务请求与响应
- **把问题拆成若干「证明」**：环境模型 → 状态迁移 → 包分帧 → 密钥归一化 → 内层密码 → 业务明文
- **一次**把共享封套族映射到 URL、body、response、cookie 之上，记录哪些字段是**精确的兄弟**，哪些是**字段特定的变体**
- 证明**业务明文本身**是否足够，还是构建后续字段时**还需要当前状态字节**
- **保持验证检查点显式**：cookie 形状或长度、token 形状或长度、校验成功、解码后前缀长度、期望的 JSON 锚点或 schema 字段
- **把最终采集器交付为显式的分阶段流水线**，例如：
  `entry -> 本地 challenge/bootstrap -> token preflight -> 业务请求 -> 本地响应解码`

---

### Pattern O：分页路由中途换族（Pagination route pivots mid-sequence）

**症状**：
- 早期页能通过一族干净的 URL 回放，但后期页码 404 或返回错误内容
- 可见的分页器看起来统一，但**尾页链接指向另一族端点**（如 `/ui`、Ajax、或隐藏模板路由）
- 从首页 URL 猜页码，短暂有效之后就崩
- 真正的下一页藏在 inline handler、隐藏模板、或分页器元数据里，**而不是一个普通 `href`**

**动作**：
- **把分页当作协议契约的一部分**，而不是文件名算术
- **抓下路由族切换的那个截止页码**
- 从**实时分页器或原始源码**提取下一页目标，而不是外推一个 URL 模式
- **让采集器逻辑「对路由敏感」**，使早期页与尾页可以共存，**不需要浏览器兜底**

---

### Pattern P：解析后的属性对回放关键路由撒谎（Parsed attributes lie about replay-critical routes）

**症状**：
- inline handler 或元数据属性带 query 串、`&`、实体样文本、或自定义分隔符
- **解析后的 DOM 值已经和源字节对不上了**
- 基于 `onclick`、`tagname` 等 DOM 属性构建的回放失败，而**原始 HTML 片段**指向正确路由
- 美化或重新解析会**改变路由或参数名**

**动作**：
- **在解析或美化之前**，先保存原始标签片段
- 在**同一页**上对比 原始源码 / DOM 解码值 / wire 行为 三者
- **从原始 HTML** 提取回放关键路由数据，因为实体解码或修复逻辑会改写它
- **显式归一化实体处理**，不要信解析器默认值

---

### Pattern Q：传输前置门挡住了干净基线（Transport pre-gate blocks the clean baseline）

**症状**：
- 标准 HTTP 客户端在出现有意义的应用数据**之前**就死于 H2 reset、TLS EOF、握手超时、或提前断连
- 同一条路由在不同 UA 族、ALPN、或 HTTP 版本上表现不同
- 移动端 / app UA、伪造 TLS、或 HTTP/1.1 通过，而默认桌面端或 stdlib 流量失败
- **某个同级 auth / identity / 业务路由，绕过了一个被挑战的落地页路由**

**动作**：
- **把传输准入与 signer / cookie / 载荷逻辑分开**
- **在加载巨型 bundle 之前**，先画一个窄矩阵：路由 × 客户端栈 × UA 族 × HTTP 版本
- 任何通过的配置，**只对需要它的那个被挡路由族生效**
- **只有在存在一条干净的准入基线之后**，才继续应用层逆向

详见 `../observe/transport-pre-gate-playbook.md`。

---

### Pattern R：挑战运行时已经知道答案（Challenge runtime already knows the answer）

**症状**：
- bootstrap 或挑战脚本在 init 之后**暴露了一个 getter**
- 或它**自发发出 XHR / fetch**，带着决定性的封装载荷
- 后期的定时器回调抛错，但**在完整 DOM 对齐之前**就已存在一个可用产物
- 阻塞式 `vm` 执行**死锁**，而 DOM 或脚本执行能保住定时器或请求 hook
- 完整理解 VM 很贵，但**一个出站载荷、cookie、或 header 集合就足以继续**

**动作**：
- **先分类产物路径**：暴露的 getter / 拦截的出网 / 备选路由绕过
- **保住调度器语义**，并拦截**最近的稳定边界**
- 拦截之后，**只 stub 运行时期待的最小成功响应**
- 若运行时出网已暴露权威出站 `Cookie` 头，**先收割那一个确切 header**，再去逐个逆 cookie writer
- **把收割到的产物交回 Python** 做真实 HTTP 回放；若挑战 bundle 每轮版本随机化，**用新鲜 bootstrap 重试**

本机可用的「收割产物」手段见 `../observe/hook-techniques.md`。

---

### Pattern S：业务响应是一个刷新契约（Business response is a refresh contract）

**症状**：
- 业务端点返回 HTTP 200 或应用子码，**外加** seed、timestamp、name、nonce、或 refresh offset 等字段
- 把这些响应字段与**一个本地派生的 token / cookie / header** 合并之后，重试同一族 URL 就生效
- 本地 cookie jar 看着很接近，但**确切的出站 `Cookie` 头或 header bundle 仍决定成败**
- helper 更多依赖**原站 JS + 窄的 host patch**，而不是业务载荷语义

**动作**：
- **把响应载荷当作刷新状态**，而不是通用失败
- 在**一条会话链**上冻结一组 `失败 -> 刷新 -> 成功` 三元组
- **在寻找备用端点之前**，先重试同一业务路由
- **把服务端下发的 seed 字段与本地派生的回放字段当作一个 bundle 一起更新**
- **把请求出网产物（尤其是完整出站 `Cookie` 头）与存储的 jar 对比**
- 保持任何本地运行时**窄、有版本锁定、自包含**

详见 `../state/cookie-provenance-playbook.md`。

> ⚠ **本机反复出现的变体**：同一路径两次访问、登录状态相同时，`Cookie` 头**值可能相同但顺序不同**，而顺序决定成败。
> 排查动作与 Pattern S 相同（比对完整出站头），但归因走 `../state/cookie-provenance-playbook.md` 的「同名 cookie 折叠顺序」一节。

---

### Pattern T：登录态与业务上下文是两个状态（Login and business context are separate states）

**症状**：
- 账号登录成功
- 首页能打开
- **数据仍属于错误的租户 / 店铺 / 供应商 / 组织**

**动作**：
- **把账号认证与业务上下文激活分开**
- 在导出或采集之前，**验证每一层必需的身份**

详见 `../state/multi-context-session-playbook.md`。

---

### Pattern U：激活看着成功但数据范围是陈旧的（Activation looks successful but the data-range is stale）

**症状**：
- switch / update-session 返回 200 或成功
- 租户或角色看着对
- **但限定范围的数据仍然反映的是旧的或空的区间**

**动作**：
- **对比完整的激活载荷**，含 type 与 value 字段
- **从权威的最终界面重读身份**
- **把「静默的不完整激活」当作失败**

---

### Pattern V：显示标签不是协议 id（Display labels are not protocol ids）

**症状**：
- 操作员选择一个人类可读的名称
- wire 请求需要的是 code、资源 id、或授权值
- 名称解析错误或歧义会**造出一个错误上下文的会话**

**动作**：
- **只用标签去实时授权响应里定位行**
- **提交协议 id，而不是展示文本**
- **要求恰好一个匹配**；零个或多个都停下

---

### Pattern W：创建成功但没有新导出任务（Create returns success but no new export task）

**症状**：
- create 或 submit 返回 HTTP 200
- 历史里**没有新的任务 id**
- 后面的代码却仍「找到」了一个成功行

**动作**：
- **在 create 之前给任务 id 拍快照**
- **要求出现新 id，或 create 显式返回的 id**
- 重新 diff method、body 放置、content-type、以及 signer 覆盖范围

详见 `../state/async-export-job-playbook.md`。

---

### Pattern X：轮询复用了历史成功任务（Polling reuses a historical successful task）

**症状**：
- 导出完成得太快
- 时间范围或字段**属于一次更早的运行**
- create 之前的历史里**就已经有**所选的那个任务 id

**动作**：
- **绝不把历史第 0 行当作本次运行**
- **优先用 create 返回的 id**，否则只用 create 之后出现的新 id
- **要求过滤条件与字段集匹配**

---

### Pattern Y：首次创建与重新生成是不同的契约（First-create and regenerate are different contracts）

**症状**：
- regenerate 或 retry 用某一种 method / body 形态就能工作
- **首次 create 仍然失败，或什么都没创建**
- signer 是从**错误的样本**构建的

**动作**：
- **首次 create 与 regenerate 分开抓取**
- 让 method、query、body、与 signer 输入**留在同一个已证明的样本上**
- **在首次 create 未被证明之前，宁可留空**，也不要提升「regenerate 的民间偏方」

---

### Pattern Z：挑战重写业务 URL（Challenge rewrites the business URL）

**症状**：
- 业务 JSON API **首次返回挑战 HTML 而不是数据**
- 成功的重试用**同一路由 + 一个很长的 verifier query 参数**
- 对同名参数，短生命周期的离线 token **线上失败**
- helper 或运行时在业务 JSON 出现**之前**导航到一个被重写的 URL

**动作**：
- 在**一条会话链**上冻结 `失败 -> 挑战资产 -> 成功`
- **在深度加密逆向前**，先收割重定向或导航 URL
- 需要时用**本地挑战执行器**
- 证明**在重写之后**，应用 signer header 是否仍然必需

详见 `../state/challenge-artifact-harvest-playbook.md` 与 `local-challenge-executor-playbook.md`。

---

## 判据（Verification checklist）

**这份图谱本身不产生「完成」**。它的产出是一个**可被后续 playbook 验证**的 Pattern 匹配结论。

一个 Pattern 匹配算**成立**，当且仅当**全部 3 条**满足：

1. **症状有 wire 证据** —— 不是「源码里看起来像」，而是**抓包或本地复现**确认的
2. **动作已执行且留有产物** —— 比如「信任网络路径」的产物是**一个能回放的真实路径**，不是一段笔记
3. **该 Pattern 指向的具体 playbook 已被读取并执行** —— 图谱只给路由，判断由 playbook 给

**不算成立**的典型情形：
- 只凭源码静态阅读就下结论（「页面里写的就是真的」）
- 症状描述对上了，但动作没做，或做了没留产物

> ⚠ **使用顺序**：先确认**左侧证据形态**，再匹配字母。
> 跳过证据确认直接对字母，会产生「分类看起来正确、但证据从未被捕获」的假进展。

---

## 常见坑（Common traps）

- 源码里写的端点就当成真实端点（Pattern A / B）
- 摘要函数名匹配就当成标准算法（Pattern C → `crypto-patterns.md`）
- 把分页当成文件名算术（Pattern O）
- 基于 DOM 解析后的属性构建回放，而原始 HTML 其实是对的（Pattern P）
- 把「HTTP 200」当作回放成功（Pattern D / L / S / Z —— 这几个都要求**语义锚点**）
- 把 cookie jar 内容当作完整的 wire 真相（Pattern S）
- 把一次性挑战的输出当作可复用的静态参数（Pattern I）
- **先**调答案 / 轨道参数，**后**建消融矩阵（Pattern I2 的顺序被颠倒了）
- 对 Pattern R 的产物**过度逆**，而不是**先收割**（Pattern R）

---

## 源文档勘误（改编时修正）

1. **【交叉引用路径已修正】** 源文档多处引用形如 `../triage/verifier-replay-playbook.md` 的路径。这批 playbook 实际位于本包的 `references/triage/` / `references/state/` / `references/observe/` 之下，原路径写法会指向不存在的 `references/references/`。改编时统一改为**同包实际相对路径**。

2. **【目录遗漏已修正】** 源文档「Contents」列出了 A–Z（含 I2）共 26 个 Pattern，**但 Pattern N 与 Pattern O 之间的部分条目未在目录中完整呈现**，且目录里 W/X/Y/Z 的锚点大小写与正文标题不一致。改编时按六个组重新整理目录，并统一锚点。

3. **【内容归属澄清，未改结论】** 源文档 Pattern S 的症状里包含「本地 cookie jar 看着接近，但确切的出站 `Cookie` 头或 header bundle 仍决定成败」这一条 —— 它讲的是**会话桥接导致 cookie 头变化**，与 Pattern S 主线（响应是刷新契约）不是同一件事。
   改编时**保留其原位置与全部结论**，仅在其后加了一段「变体」说明，指出归因路径是 `../state/cookie-provenance-playbook.md`。**未改动源文档任何技术结论。**

> 本文其余 26 个 Pattern 的技术内容经逐条核对，**未发现编造的常量或错误的算法描述**。

---

## 相关（Related）

- `crypto-patterns.md` —— Pattern C 的完整算法核对流程
- `obfuscation-guide.md` —— Pattern G / H 背后的混淆还原
- `offline-inline-deob-playbook.md` —— Pattern D 内联 payload 的还原
- `local-challenge-executor-playbook.md` —— Pattern D / I / R / Z 的本地执行路径
- `../triage/escalation-ladder-playbook.md` —— 「不要跨层跳跃」的全局规则
- `../triage/symptom-heuristics.md` —— 症状到 Playbook 的路由
- `../deliver/delivery-gate-playbook.md` —— 判据段「指向的 playbook 已被执行」的判定