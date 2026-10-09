# 教条总纲（Doctrine Index）

> **来源**：改编自 `aoyunyang/spider-king-skill`（MIT License）的 `doctrine-index.md`。原文为英文，本篇为中文改写，**编号 1–26 共 26 条教条（正文 29 个条目，编号 14 下分 14A/14B/14C）的论证结构逐条保留**，未压缩为摘要。
> **什么时候用**：目标还很宽、失败形态看着眼熟、或者你在加载更细的 playbook 之前需要一套「家族级（family-level）」规则时，先读本篇。这些是**可迁移规则**，不是某个站点的现场笔记。
> **平台与本机状态**：本文是纯方法论，不含任何需要本机执行的命令，因此不涉及工具可用性问题。文中提到的浏览器取证角色 `chrome-devtools` / `js-reverse`（MCP 家族）**在本机 agent 工具注册表中未挂载**（本机已挂载的是 `pyghidra-mcp` / `idapro` / `ida-pro-mcp` / `angr-mcp` / `x64dbg-automate-mcp`），照搬原文的浏览器角色序列前需先确认可用性 —— 见 `../../SKILL.md` 的 Non-Negotiables。文中提到的 `iv8` 运行时**本机无**（社区运行时，PyPI 上不存在），相关 API 形态仅供有该运行时时参考，**未在本机验证**。

---

## 适用信号

命中以下任意一条，就先回来读教条，而不是继续往下挖：

- 你正准备**下结论**，但结论还没落到「线上真实流量（wire）」上；
- 你在**追一个 `sign` 函数**，但已经卡了超过一个阶段；
- 你准备**写死一个会变的值**（cookie / token / header）；
- 你在**换更重的运行时**（Python → JS 运行时 → 全宿主补丁），而且说不清为什么上一级不够；
- 你准备**分页 / 并发 / 规模化**，但单页只成功过一次；
- 你看到页面文案说「需要登录」「需要某个 cookie 参与签名」，准备照做；
- 你已经拿到一份「看起来完整」的抓包，准备直接写 collector；
- verifier（校验器）返回了**语义上的成功**，你准备收工；
- 你在**换站点 / 站点升级**之前，想固化一批可复用的小事实；
- 某条「看起来很快的捷径」反复出现 —— 去 `anti-patterns-playbook.md` 对号入座。

## 前置

- 本篇是**判定层**文档，不产出代码，也不产出工具调用。读完它你应该已经知道下一步该读哪一篇。
- 术语约定：
  - `wire` = 线上真实发出的字节（请求与响应），本文所有「信 wire」都指这一层；
  - `page text` = 页面文案 / DOM 可见文本 / 业务命名；
  - `envelope（信封 / 封套）` = 请求或响应外层的封装结构，含版本字节、字段前缀、校验位、长度规则等；
  - `signer（签名器）` = 生成 `sign` / `token` / `m` 一类字段的代码路径；
  - `bootstrap（引导）` = 页面或接口下发的、用来初始化后续逻辑的 JS / 配置 / 密钥材料；
  - `Playbook（作战手册）` = 本包 `references/` 下的具体操作手册；
  - `Doctrine（教条）` = 本篇的一条家族级规则。
- 本篇与 `../../SKILL.md` 的 Universal Reverse Loop 阶段划分**不是同一套编号**：本篇只给规则，不给阶段顺序。阶段顺序去 `workflow-overview.md`。

## 步骤

本文的正文就是**编号 1–26 共 26 条教条**（其中编号 14 下分 14A / 14B / 14C 三个子条，因此正文共 29 个条目），按编号顺序排列。先按信号定位到具体一条，读完直接回去干活。

### 目录

<!-- TOC:BEGIN -->
- [教条 1：信 wire，不信页面文案（Trust the wire, not the page text）](#教条-1信-wire不信页面文案trust-the-wire-not-the-page-text)
- [教条 2：那个会变的参数，未必是签名（The dynamic parameter is not always a signature）](#教条-2那个会变的参数未必是签名the-dynamic-parameter-is-not-always-a-signature)
- [教条 3：定输入验证胜过函数命名（Fixed-input validation beats naming）](#教条-3定输入验证胜过函数命名fixedinput-validation-beats-naming)
- [教条 4：窄例外就保持窄（Narrow exceptions stay narrow）](#教条-4窄例外就保持窄narrow-exceptions-stay-narrow)
- [教条 5：自动化不是可接受的拐杖（Automation is not an acceptable crutch）](#教条-5自动化不是可接受的拐杖automation-is-not-an-acceptable-crutch)
- [教条 6：环境不匹配就是证据（Environment mismatch is evidence）](#教条-6环境不匹配就是证据environment-mismatch-is-evidence)
- [教条 7：交付门禁高于便利（Delivery gates outrank convenience）](#教条-7交付门禁高于便利delivery-gates-outrank-convenience)
- [教条 8：公开不等于无签名（Public does not mean unsigned）](#教条-8公开不等于无签名public-does-not-mean-unsigned)
- [教条 9：有状态流是协议，不是浏览器魔法（Stateful streams are protocol, not browser magic）](#教条-9有状态流是协议不是浏览器魔法stateful-streams-are-protocol-not-browser-magic)
- [教条 10：观察者效应是真的（Observer effect is real）](#教条-10观察者效应是真的observer-effect-is-real)
- [教条 11：cookie 来源胜过 cookie 迷信（Cookie provenance beats cookie superstition）](#教条-11cookie-来源胜过-cookie-迷信cookie-provenance-beats-cookie-superstition)
- [教条 12：包封装与密码学是两套独立契约（Packet framing and crypto are separate contracts）](#教条-12包封装与密码学是两套独立契约packet-framing-and-crypto-are-separate-contracts)
- [教条 13：分页是一个协议面（Pagination is a protocol surface）](#教条-13分页是一个协议面pagination-is-a-protocol-surface)
- [教条 14：原始源码可能胜过解析后的 DOM（Raw source can beat parsed DOM）](#教条-14原始源码可能胜过解析后的-domraw-source-can-beat-parsed-dom)
- [教条 14A：长得像服务端的字段名，不证明是服务端下发的（Server-looking field names do not prove server issuance）](#教条-14a长得像服务端的字段名不证明是服务端下发的serverlooking-field-names-do-not-prove-server-issuance)
- [教条 14B：铸出来的 session 不等于被准入的 session（Minted session is not admitted session）](#教条-14b铸出来的-session-不等于被准入的-sessionminted-session-is-not-admitted-session)
- [教条 14C：枚举与水合是两套独立契约（Enumeration and hydration are separate contracts）](#教条-14c枚举与水合是两套独立契约enumeration-and-hydration-are-separate-contracts)
- [教条 15：内嵌运行时是手术刀，不是第二个浏览器（Embedded runtimes are scalpels, not a second browser）](#教条-15内嵌运行时是手术刀不是第二个浏览器embedded-runtimes-are-scalpels-not-a-second-browser)
- [教条 16：探针链会暴露缺失的那一面（Probe chains reveal the missing surface）](#教条-16探针链会暴露缺失的那一面probe-chains-reveal-the-missing-surface)
- [教条 17：传输准入是一套独立契约（Transport admission is a separate contract）](#教条-17传输准入是一套独立契约transport-admission-is-a-separate-contract)
- [教条 18：在最近的那个稳定边界上收割挑战产物（Harvest challenge artifacts at the nearest stable boundary）](#教条-18在最近的那个稳定边界上收割挑战产物harvest-challenge-artifacts-at-the-nearest-stable-boundary)
- [教条 19：服务端下发的状态胜过本地臆造（Server-issued state beats local invention）](#教条-19服务端下发的状态胜过本地臆造serverissued-state-beats-local-invention)
- [教条 20：按失败面拆分 verifier 目标（Split verifier targets by failure surface）](#教条-20按失败面拆分-verifier-目标split-verifier-targets-by-failure-surface)
- [教条 21：弱校验是证据，不是赦免（Weak enforcement is evidence, not absolution）](#教条-21弱校验是证据不是赦免weak-enforcement-is-evidence-not-absolution)
- [教条 22：一次只升一级（Escalate one rung at a time）](#教条-22一次只升一级escalate-one-rung-at-a-time)
- [教条 23：小事实比大总结更耐老化（Small facts age better than big summaries）](#教条-23小事实比大总结更耐老化small-facts-age-better-than-big-summaries)
- [教条 24：反例比口号更能约束行为（Counterexamples constrain better than slogans）](#教条-24反例比口号更能约束行为counterexamples-constrain-better-than-slogans)
- [教条 25：正样本卫生胜过轨迹调参（Positive-sample hygiene beats track tuning）](#教条-25正样本卫生胜过轨迹调参positivesample-hygiene-beats-track-tuning)
- [教条 26：环境风险是它自己独立的一个失败面（Environment risk is its own failure surface）](#教条-26环境风险是它自己独立的一个失败面environment-risk-is-its-own-failure-surface)
<!-- TOC:END -->

### 教条 1：信 wire，不信页面文案（Trust the wire, not the page text）

页面会骗人，字节不会。按可信度从高到低：

- **真实请求路径**胜过页面上的接口提示。
- **真实请求头**胜过业务代码里能看见的部分。
- **真实 cookie**胜过你猜出来的「token 故事」。
- **真实响应形状**胜过你归档下来的旧笔记。
- 一个 `200 OK` 的文档、一个加载中的占位符（loading placeholder）、一个渲染出来的空壳（rendered shell），**都不能证明业务载荷在 HTML 里**。

判别方法：任何时候你手上有一个「页面说的」和一个「线上抓到的」，冲突时**一律以线上为准**，并且回头去解释页面为什么在说谎（通常是一个 wrapper rewrite 或一个 bootstrap 资产）。

### 教条 2：那个会变的参数，未必是签名（The dynamic parameter is not always a signature）

看起来在变的东西，真正变的东西可能是下面**任意一个**：

- 一个 cookie
- 一个页面专属的请求头
- 一个传输层 `envelope（信封）`
- 一个服务端下发的 JS `bootstrap（引导）`
- 一个动态字体
- 一个 WebAssembly 导出
- 一次传输层 wrapper 的重写
- 一个**响应侧**的解码器
- 一个与账号绑定的会话契约

**红线（Do not）**：不要默认「只要目标够硬，就一定能靠找一个 `sign` 函数解决」。

### 教条 3：定输入验证胜过函数命名（Fixed-input validation beats naming）

如果某个页面 helper（辅助函数）叫 `md5` 或 `btoa`，**在固定输入上证明它**之后再相信这个名字。

对可疑 helper 的最低验证标准：

1. 选一个固定输入，比如 `"abc"`，或者一个抓下来的时间戳；
2. 记录浏览器侧的输出；
3. 记录本地的输出；
4. 比较**中间值**，不只是最终输出。

为什么强调中间值：标准库和魔改实现的最终输出可能因为数据碰巧而一致，但 IV（初始向量）、轮常量、字节打包顺序一旦不同，换一个输入就分叉。只比最终输出等于没比。

### 教条 4：窄例外就保持窄（Narrow exceptions stay narrow）

如果只有一个页面需要特殊的 `User-Agent`，或者只有一个请求需要轮换的 cookie，就把这个例外**显式编码**出来。

**红线（Do not）**：不要因为一个特例，就给整个 collector 下一个「只能浏览器跑」的结论 —— 那是把一次观测推广成了一条架构判断。

### 教条 5：自动化不是可接受的拐杖（Automation is not an acceptable crutch）

卡住的时候，做**更多协议侧的工作**，而不是换工具：

- diff 请求
- 抽取内联脚本
- 在本地跑 bootstrap JS
- 把 helper 逻辑移植过来
- 在本地实例化 WASM
- 在本地解码字体

**红线（Do not）**：不要把浏览器自动化当作交付形态。浏览器是取证工具，不是产品依赖。

### 教条 6：环境不匹配就是证据（Environment mismatch is evidence）

本地输出和线上输出对不上时，**把不匹配本身当证据**，然后：

- 比对固定输入
- 比对旁挂资产（side assets）
- 比对被 patch 过的 helper
- 比对环境分支（environment branches）

**红线（Do not）**：不要用一句「大概只能浏览器跑」把不匹配挥手带过。每一个不匹配都对应一个具体的、你还没找到的环境依赖。

### 教条 7：交付门禁高于便利（Delivery gates outrank convenience）

如果**唯一已知**的路径仍然依赖活的页面上下文，这个任务就没做完：

- 一个浏览器 profile **不是**协议产物；
- 一个藏起来的「刷新」点击**不是** collector；
- 一个没人解释的解码器**不是**可接受的交接。

继续逆，直到所有会动的东西都是**本地的、显式的、可测的**。

### 教条 8：公开不等于无签名（Public does not mean unsigned）

匿名页面照样有协议契约：

- 一个公开列表可能仍然需要**入口路由的 cookie**；
- 一个公开路由可能仍然需要**页面播种的状态 + 请求域的签名材料**，两者都在匿名链上；
- 一个 bootstrap 接口可能仍然在返回 key、config 或 `envelope（信封）` 种子；
- **列表可见不证明详情可见，列表可见也不证明提交可见**；
- 如果存在一条干净的匿名路径，**先证明它**，再去用带登录态的 cookie 或账号状态污染基线。

**把三件事当三个独立问题**：匿名可达性、`envelope（信封）` 的构造方式、权限边界。

### 教条 9：有状态流是协议，不是浏览器魔法（Stateful streams are protocol, not browser magic）

如果目标只有在登录、配对（pairing）、或者一次预热 WebSocket 交换之后才可读，那么**那段会话记录本身就是协议的一部分**：

- 配对 / 登录的 bootstrap **不是** UI 装饰；
- 握手输出是**协议产物**；
- 心跳、ack 帧、计数器、重连规则**都是 collector 的一部分**。

**红线（Do not）**：不要把一个有状态流的问题，压缩成一个假的「单请求签名」故事 —— 那样你交付的采集器在真实链路上必然断。

### 教条 10：观察者效应是真的（Observer effect is real）

有些目标**你一碰它就变难**：

- 有 verifier 门禁（verifier-gated）或者对行为敏感的链路，在装了 hook、断点、monkey patch 之后行为会变；
- 在做侵入式插桩（instrumentation）**之前**，先抓一条干净的基线请求和响应；
- 优先用 initiator 栈、请求 diff、窄边界 hook，而不是大范围的全局 hook；
- 如果装 hook 之后失败形态变了，**把它当成「你的工具正在扰动目标」的证据**。

**红线（Do not）**：不要把「hook 导致的坏掉」误当成「这个站只能浏览器跑」的证明。

### 教条 11：cookie 来源胜过 cookie 迷信（Cookie provenance beats cookie superstition）

cookie 卡住了重放时，先证明它从哪来：

- 协议响应上的 `Set-Cookie`
- 页面代码里的 `document.cookie`
- 服务端下发的挑战 / bootstrap JS
- 重定向包装、iframe、worker 或 SDK 的副作用
- 或者 —— 一个长得像 cookie 问题的**派生请求头 / token**

**红线（Do not）**：在证明写入者（writer）和刷新路径之前，不要写死一个会轮换的业务 cookie。

### 教条 12：包封装与密码学是两套独立契约（Packet framing and crypto are separate contracts）

当同一族页面同时用编码 URL 参数、编码表单体、加密响应、或者与环境绑定的 cookie 时，**不要把所有东西塌缩成「那个 AES」或者「那个 sign」**。

- 把**外层包封装**和**内层密码学**分开：版本字节、字段前缀、校验和、自定义字母表、长度规则、状态派生的切片，这些和密码算法本身一样有约束力；
- 如果签名器消费的是 `fullUrl` 或某个规范化请求串，那么**参数顺序、空字段的处理、URL 编码方式**都属于协议契约；
- 要证明 URL、body、响应、cookie 到底是四种互不相关的格式，还是**一个共享的 `envelope（信封）` 家族 + 少量字段级变体**；
- 要证明后续请求是否还需要当前的会话状态字节、storage state 或挑战输出，而不只是业务明文；
- 如果解密后的响应**不是从第 0 字节开始**，那么前缀剥离和载荷定位属于协议本身，不是解析器的清杂物；
- 如果 key 看起来是间接的、被包裹的、被掩码的，先把 **key 归一化**这一步恢复出来，再去怪 AES 模式或 padding。

**红线（Do not）**：在封装、状态依赖、载荷抽取三者**都**能在本地复现之前，不要宣布「密码学已解决」。

### 教条 13：分页是一个协议面（Pagination is a protocol surface）

分页不只是 UI 的装饰，它**可能是协议契约的一部分**：

- 第 1 页看起来是静态的，后面几页可能就换成了另一个端点家族；
- 一个能用的文件名规律**不证明**整个列表都用这个规律；
- 一个可见的分页器后面，可能藏着一个**路由截断点**：静态页之后就变成 `/ui`、Ajax 或别的端点家族；
- 一旦怀疑有路由拐点（route pivot），collector 应该优先去抓**真实的下一页目标**，而不是去猜页码算术。

**红线（Do not）**：在后续页能用**同一套 collector 逻辑**重放之前，不要宣布分页已解决。

### 教条 14：原始源码可能胜过解析后的 DOM（Raw source can beat parsed DOM）

当对重放关键的路由数据藏在**内联事件处理器或遗留属性**里时，解析后的 DOM 值可能**不是规范形式**：

- 未转义的 `&`、损坏的实体、遗留模板、或者修复逻辑，都会改写查询串和参数名；
- 浏览器 getter、HTML 解析器、beautifier（美化工具）都可能把**真正影响重放的那些字节**规整掉；
- 当内联属性携带下一页路由时，**把原始标签片段冻结下来**，先和解析后的值比对，再决定信哪个。

**红线（Do not）**：不要因为一个属性「读起来正常」，就认为 DOM 解码后的值可以安全重放。

### 教条 14A：长得像服务端的字段名，不证明是服务端下发的（Server-looking field names do not prove server issuance）

像 `__RequestVerificationToken`、`pageId`、request id、nonce、trace id、session cookie、fingerprint cookie 这些名字**都可能是误导**：

- 证明**谁在写**这个字段：页面代码、包装代码、bootstrap 响应，还是服务端；
- 在**同一个已知良好的会话**下，用多个**新生成的本地值**测它的容忍度；
- 长得像 session / fingerprint 的 cookie 名**不能证明**存在 `Set-Cookie`；有些就是由 bootstrap 配置、指纹向量或结构化 UUID 变体在本地铸出来的（locally minted）；
- 如果一个本地铸造的字段能扛住多个新的、合规的值，那就**保留它的精确结构**：插入前缀、定长分段、紧凑 JSON 的字段顺序、摘要链（digest chaining）、key 归一化步骤；
- **定输入下的跨运行时一致性（cross-runtime parity）**，胜过「随机数看起来差不多」的近似匹配；
- 如果多个新的合规值下重放都稳定，就把该字段从「硬门禁」**降级为本地填充（local filler）**。

**红线（Do not）**：不要仅仅因为字段名听起来很重要，就花几个小时去逆一段装饰性的随机数。

### 教条 14B：铸出来的 session 不等于被准入的 session（Minted session is not admitted session）

来自公开预热接口、current-user 接口或 bootstrap 路由的一个新 cookie，可能**只证明了传输层和匿名外壳还活着**。

- 把**铸造 session** 和**业务准入**分成两件事；
- 如果抓到的业务 cookie 能重放、而新铸的匿名 cookie 不能，那就把它当成证据：**请求契约已经解决了，缺的那一块是 session bootstrap 或者权限状态**；
- 当失败形态是「某条路由的权限拒绝」时，**不要继续怪签名器**。

**红线（Do not）**：不要把「我有一个新 session」等同于「这个 session 被授权去调我要的那个业务方法」。

### 教条 14C：枚举与水合是两套独立契约（Enumeration and hydration are separate contracts）

列表、详情、下载、导出这几类路由，通常共享同一个 `envelope（信封）` 家族，但在标识符、权限边界和**成本**上都不同。

- 先解一条路由，然后去探测兄弟路由，看包装器和解码器能否复用；
- 从**便宜的枚举阶段**持久化稳定 id；
- 同时持久化**归一化输出**和**原始解码载荷**，这样后续的全文回填或基于规则的补采，不必重跑整轮爬取。

**红线（Do not）**：不要把昂贵的详情水合（hydration）焊死在 collector 唯一的通路上 —— 分阶段的设计更便宜也更安全。

### 教条 15：内嵌运行时是手术刀，不是第二个浏览器（Embedded runtimes are scalpels, not a second browser）

像 `iv8` 这样的内嵌浏览器式运行时，只用在**确实还需要宿主语义的那一小块**上。

> ⚠️ **本机状态**：`iv8` 在本机**没有安装**（社区运行时，PyPI 上不存在）。以下形态描述的是「拥有该运行时时的 API 形态」，**未在本机验证**。本机的替代路线是 `../../profiles/env-patch/index.md`（Node/VM 环境补丁）与 `../../profiles/browser-hook-snippets/index.md`（浏览器内取证），二者都不能替代 iv8 的浏览器可见语义。

- 固定输入验证成本低时，**先在 Python 里解码并手写简单公式**；
- 只有当 JS 依赖浏览器可见的宿主语义时才切到内嵌运行时，比如 `navigator`、`screen`、`location`、DOM 生命周期、定时器、`document.cookie`、XHR 包装、对原生面的反射；
- 运行时保持**本地且窄**：取回一个 token / cookie / URL 后缀 / 被包裹的 body / 解码后的载荷，然后**把控制权交回 Python**；
- 如果目标**每个请求**都还需要完整渲染、手势、canvas 噪声或活的浏览器状态，那这个运行时**仍然是分析仪器**，不是「交付已解决」的证明。

**红线（Do not）**：不要让一个本地运行时悄悄地退化成「标签页更少的浏览器自动化」。

### 教条 16：探针链会暴露缺失的那一面（Probe chains reveal the missing surface）

现代目标经常在**任何签名器运行之前**就先检查环境。

- 观察在乱 patch 随机全局对象**之前**，到底哪个 API 被读取、枚举、字符串化或反射；
- 把 `Object.keys`、`Reflect.ownKeys`、descriptor 读取、`Function.prototype.toString`、`JSON.stringify`、`document.all` 当成**一等证据面**；
- 如果确实需要临时 patch，就让它的**反射出来的形状**尽可能贴近预期；
- 用探针证据去决定该修哪一项：身份语义、枚举顺序、时序、cookie 状态，还是**缺一个看起来像原生的边界**。

**红线（Do not）**：不要把「静默的环境探针分支」塌缩成含糊的「JS 混淆」四个字。

### 教条 17：传输准入是一套独立契约（Transport admission is a separate contract）

有些目标在你还没看到签名器、cookie 或解码逻辑**之前**，就把干净基线挡掉了。

- TLS 指纹、ALPN、HTTP 版本、UA 家族、路由选择，都可能决定应用层契约**到底能不能被触达**；
- 复制 HTTP 请求头**清不掉**一个由 ClientHello 或 HTTP/2 profile 在「正常请求语义存在之前」就决定了的门；
- JA3 / JA4 只是**汇总指标**：在照抄某一个哈希值之前，先比对底层的 ClientHello、ALPN 和 H2 行为；
- 当某个浏览器家族会随机化扩展顺序或 GREASE 时，**保留该家族的行为或原始字段轮廓**，而不是冻结一个不稳定的汇总值；
- 如果标准库客户端死在 H2 reset / 超时 / 提前断开，而一个「冒充了传输层」的客户端能过，**先解决准入**，并且把例外保持得很窄；
- 一条落地路由可能被挑战，但**兄弟路由**（auth 或 data）仍然可用 —— 先验证路由局部策略，别去打错的仗；
- 优先选**最接近的传输家族或一个窄适配器**，而不是去手工一个个字段地 patch 一个相距很远的默认栈。

**红线（Do not）**：不要把「流量根本没通过传输准入」归咎到签名器或 cookie 逻辑上。

### 教条 18：在最近的那个稳定边界上收割挑战产物（Harvest challenge artifacts at the nearest stable boundary）

**不要**在「只要一个显式产物就够」的时候，去完整求解一个充满敌意的运行时。

- 如果一个 bootstrap 运行时在同步初始化后暴露了一个稳定的 getter，**先调它**，而不是去 patch 后面每一个定时器或 DOM 缺口；
- 如果脚本是通过 XHR / fetch 自我提交的，**在本地拦下它的出站 body 和请求头**，而不是去模拟每一条指令；
- 保留调度语义（scheduler semantics）：选择能让定时器、微任务（microtask）和请求钩子都保持存活的执行路径；
- 只 patch **最小的忠实边界**，并让结构性错误自然抛出 —— 一个掩盖递归或状态损坏的 catch-all 是破坏，不是保护。

**红线（Do not）**：当一个显式产物就足以让 Python 重放时，不要把「完整执行整个挑战」当成目标。

补充（原文中这三条紧跟其后，逻辑上属于同一个「最近稳定边界」的推论）：

- 优先**收割导航或重定向 URL**，然后才轮到逐个 cookie 逆 —— 运行时往往已经改写了业务 URL；
- 把「业务 JSON 路由返回了挑战 HTML」当成**挑战 bootstrap**，不是死端点；
- 如果某个字段同时有一个**短的科研写入者**和一个**长的线上成功写入者**，**只交付线上被接受的那一类**。

### 教条 19：服务端下发的状态胜过本地臆造（Server-issued state beats local invention）

在本地重建任何东西之前，先**盘点服务端已经白送给你的东西**：

- 把 session id、工作量因子（work factors）、资产 URL、答案 schema、移动边界、wrapper、过期窗口**分别列出**，和本地计算的值分开记账；
- 保留每个下发产物的**作用域和生命周期**：页面域、请求域、路由域、还是会话域；
- **除非刷新逻辑或绑定规则逼着你这么做，否则不要浪费时间在本地重新推导服务端乐意直接下发的东西。**

**红线（Do not）**：当真正的问题是「怎么正确携带、刷新或绑定它」时，不要去逆向一个服务端下发的产物。

### 教条 20：按失败面拆分 verifier 目标（Split verifier targets by failure surface）

当一个 verifier 把请求、哈希、图像和行为混在一起时，**强制把问题拆成一个个面（surface）**：

- **协议面（protocol surface）**：端点链、wrapper、会话状态、载荷形状；
- **计算面（compute surface）**：哈希、PoW、编码、打包、规范化；
- **感知面（perception surface）**：图像预处理、透明度、坐标映射、匹配置信度；
- **行为面（behavior surface）**：轨迹、时序、手势旁挂载荷（gesture sidecars）、遥测 blob；
- 在把「最后那个 verify 请求」当成全部契约**之前**，先冻结**完整的、有序的 verifier 记录（transcript）**，包括预热路由和遥测路由；
- 用**单变量 block / omit / restore**（阻断 / 省略 / 恢复）对照，证明某个旁挂载荷是否真的改变最终的语义接受；
- 把「完整 profile 基线 + 稀疏增量」建模成**一份共享的状态契约**，而不是一堆各自独立成立的包；
- 当记录里声称有「经过的真实交互时长」时，保留**实际的墙钟顺序**；
- 在把一条动态路径当成「新算法」之前，先比对活跃资产的哈希、helper 边界和固定向量；
- **给每一个面挂一份独立的证明**：原始响应、定输入测试、视觉 QA、重放证明。

**红线（Do not）**：不要让感知面或行为面的失败，冒充成签名器的 bug。

### 教条 21：弱校验是证据，不是赦免（Weak enforcement is evidence, not absolution）

如果一个空的、桩掉的（stubbed）或者被简化的字段**通过了一次**，把这个容忍度**准确地记下来**：

- 记录这个宽松字段被接受时的**确切路由、环境和响应**；
- **除非有重复证据证明它对你关心的那一族路由无关**，否则把这个字段留在协议模型里；
- 假设**更严格的生产路由可能强制校验**这个字段，哪怕一个公开或 demo 路由没有；

**红线（Do not）**：不要仅仅因为一条宽松路径接受了它，就把一个字段从协议叙事里删掉。

### 教条 22：一次只升一级（Escalate one rung at a time）

当前证明失败时，只有当你**能说清楚下面三件事**，才允许往上一层走：

- 什么还在正常工作；
- 还剩下**哪一个确切的盲点**；
- 为什么更重的这一层是**能回答那个盲点的最小一层**。

**红线（Do not）**：不要从「Python 一致性还没做全」直接跳到「广泛的宿主模拟」；也不要从「本地运行时能加载了」直接跳到「分页或规模化」。

阶梯模型见 `../triage/escalation-ladder-playbook.md`。

### 教条 23：小事实比大总结更耐老化（Small facts age better than big summaries）

当一个目标家族或一条升级路径看起来可复用时，保留 **5 到 15 条最小可验证事实**：

- 路由拐点（route pivots）
- 字段槽位（field slots）
- 产物形状（artifact shapes）
- 解码顺序（decode order）
- 会话链规则（session-chain rules）
- 接受检查点（acceptance checkpoints）

**优先保留可复检的结构性事实**，而不是抄下来的 cookie、密钥或长篇叙述。

见 `../triage/minimal-verifiable-facts-playbook.md`。

### 教条 24：反例比口号更能约束行为（Counterexamples constrain better than slogans）

当同一个坏动作反复出现时，把它**提升为一条可复用的反模式**：

- 命名那个「诱人的捷径」；
- 解释它为什么制造**假进展**；
- 说出**最小的诚实下一步**；
- 以**一个直接的自检**收尾。

用 `anti-patterns-playbook.md` 承载这些反例。

### 教条 25：正样本卫生胜过轨迹调参（Positive-sample hygiene beats track tuning）

当 verifier 拒绝一个「对行为敏感的证明」时：

- 把**干净的成功样本**当成比「被自动化污染的失败样本」**更高权威**的证据；
- 产出正样本 oracle（正向判据）时，优先用**普通浏览器抓取**或**无插桩的监听**，而不是挂着 hook 的自动化 profile；
- **不要**把一次失败的自动化手动划动，升级成「这一族轨迹算法是错的」的证据；
- 给样本分级：干净成功 / 污染失败 / 部分记录；
- 读 `../triage/positive-sample-hygiene-playbook.md`。

**红线（Do not）**：当唯一的负样本全部来自一个被污染的环境时，不要拿下一个小时去变异轨迹。

### 教条 26：环境风险是它自己独立的一个失败面（Environment risk is its own failure surface）

把 verifier 的失败面**显式**拆开：

- 协议与共享状态的一致性
- 计算 / 打包 helper
- 感知 / 答案抽取
- 行为轨迹
- 遥测旁挂
- 会话新鲜度
- 传输准入
- **环境风险**：出口信誉、自动化标记、连续拒绝次数、profile 年龄

一份**结构上完全合法**的记录，仍然可能在环境评分崩塌之后失败。**要有意去改环境面**；不要把这份工作藏进轨迹搜索里。

## 判据

「做到哪一步算完成」——本篇是判定层文档，所以它的完成判据是**判定本身**：

### 本篇读完就算完成的判据（可外部观测）

- 你能对当前手上的失败形态，**指名一条具体的教条编号**，而不是说「感觉哪里不对」；
- 你能说出**这一条教条对应的下一步该读哪个 playbook**（`../references/` 下的具体文件路径）；
- 你至少能对**当前最痛的那一条教条**，回答它的 `Do not`（红线）是什么 —— 也就是明确说出「我现在正在做的、正是这条教条禁止的事」或「我没有在做」；
- 你能对**教条 22** 回答出「更重的那一层为什么是最小的一层」，如果当前正处在升级决策点；
- 你能对**教条 1** 说出一条「页面说的」与「线上抓到的」的具体冲突项，并已按线上为准修正。

### 交付类任务真正的完成判据（对应教条 7 / 12 / 13）

本篇不产出交付物，但下面这些判据**贯穿全流程**，交付前必须逐条满足（与 `../deliver/delivery-gate-playbook.md` 一致）：

- 会动的一切都是**本地的、显式的、可测的** —— 没有浏览器 profile、没有手工点击依赖、没有未解释的解码器；
- **纯 Python 路径**能在没有浏览器 MCP、没有页面驱动的情况下跑通真实业务请求；
- 固定输入向量通过（helper / 解码器 / 摘要实现），且**中间值**可比对，而不只是最终输出长度对；
- 同一个最小请求**至少连续重放两次成功**，且第二次用的是新会话或新时间戳；
- 分页 / 游标的**下一页**用**同一套 collector 逻辑**跑通；
- `envelope（信封）` 封装、状态依赖、载荷抽取三者都在本地可复现；
- 已知的例外都被**显式、窄范围**地编码，没有被推广成全局结论；
- 敏感值留在任务本地密钥库，报告与版本库里已脱敏。

## 常见坑

按「最容易被违反」排序：

1. **把教条当口号读，不当判据读**。29 个条目里 **22 个**带显式 `红线（Do not）`。只记住正面陈述（「要信 wire」）而跳过红线（「不要把 hook 导致的失败当成浏览器专属证明」），等于没读。
2. **教条 2 的最大误用**：看到参数在变，就默认它是 `sign`。先跑一遍教条 2 的 9 项清单。
3. **教条 3 只比最终输出**。定输入验证的价值全在中间值；只比输出长度等于没验证（`anti-patterns-playbook.md` 第 10 条）。
4. **教条 6 被用来给自己找台阶**：「环境不匹配」是证据这句话，反过来也成立 —— 有人说「这明显是环境差异」却不指出差在哪个具体 API 上，这是在滥用教条 6。
5. **教条 11 与教条 2 混用**：cookie 门禁重放失败时，要先分清「这是个 cookie 问题」还是「这是个长得像 cookie 的派生请求头」（教条 11 最后一条）。
6. **教条 17 顺序错误**：传输准入没过的时候，你看到的每一个「签名不对」的判断都不可信。先确认 ClientHello / ALPN / H2 profile 这一层。
7. **教条 20 的面拆得不干净**：把感知面（点选没对准）当成协议面（参数错了）去修，会烧掉大量时间。修之前先做单变量 block/omit/restore 对照。
8. **教条 21 被反向使用**：把「宽松路径接受了一次」当成「这字段可以删」的许可证 —— 这是教条 21 明确禁止的方向。
9. **教条 26 被漏掉**：结构上合法的记录仍然被拒时，先查环境面（出口 IP、连续失败次数），不要继续调轨迹。
10. **教条 15 在本机会卡住**：本机无 `iv8`。照抄原文的 iv8 路线前，先看 `../../profiles/env-patch/index.md`；但注意 env-patch **不等于**浏览器可见语义，用它时交付形态仍是「本地 bootstrap executor」而不是「runtime-free」。
11. **教条 25 的前提没满足就开调**：如果连一个「非自动化浏览器路径的成功样本」都没有，就不要开始调轨迹。
12. **同时违反两条**：最常见的组合是「教条 5 + 教条 22」（用自动化绕开本该做的协议工作），以及「教条 3 + 教条 12」（只证明了密码算法，没证明封装）。

## 相关

### 上一级

- `../../SKILL.md` —— 阶段顺序（Universal Reverse Loop）、交付门禁、非协商项，以本文为规则底座。

### 本目录

- `workflow-overview.md` —— 阶段顺序（Startup Gate → Phase 0..5），本文只给规则不给顺序。
- `anti-patterns-playbook.md` —— 教条 24 的落点：29 条「诱惑 → 假进展 → 最小诚实下一步 → 自检」。

### 教条落到的具体手册

| 教条 | 对应手册 |
|---|---|
| 2, 12 | `../crypto/crypto-patterns.md`、`../observe/transport-wrapper-playbook.md` |
| 3 | `../crypto/crypto-patterns.md`、`../observe/patched-helper-playbook.md` |
| 5, 15 | `../deliver/pure-python-rebuild-playbook.md`、`../crypto/embedded-browser-runtime-playbook.md`、`../../profiles/env-patch/index.md` |
| 8 | `../state/public-bootstrap-envelope-playbook.md` |
| 9 | `../state/stateful-stream-e2ee-playbook.md` |
| 10 | `../observe/hook-techniques.md`、`../observe/anti-debug-playbook.md` |
| 11 | `../state/cookie-provenance-playbook.md` |
| 13 | `../observe/pagination-route-pivot-playbook.md` |
| 14 | `../observe/decoy-and-real-request-playbook.md` |
| 16, 26 | `../triage/symptom-heuristics.md` |
| 17 | `../observe/transport-pre-gate-playbook.md`、`../observe/native-transport-profile-playbook.md`、`../observe/structured-transport-playbook.md` |
| 18 | `../state/challenge-artifact-harvest-playbook.md`、`../crypto/local-challenge-executor-playbook.md` |
| 19 | `../state/side-asset-bootstrap-playbook.md`、`../state/server-js-cookie-bootstrap-playbook.md` |
| 20, 22 | `../triage/verifier-error-localization-playbook.md`、`../triage/verifier-replay-playbook.md` |
| 21 | `../state/async-export-job-playbook.md`、`../state/multi-context-session-playbook.md` |
| 23 | `../triage/minimal-verifiable-facts-playbook.md`、`../contract/experience-card-schema.md` |
| 25 | `../triage/positive-sample-hygiene-playbook.md` |

### 原文提到、但本包未收录的两篇

原文末尾的 `Related references added for dual writers and local challenge executors` 对应本包中的两篇实际落地路径：

- `../observe/dual-writer-param-playbook.md`（原文 `../observe/dual-writer-param-playbook.md`）
- `../crypto/local-challenge-executor-playbook.md`（原文 `../crypto/local-challenge-executor-playbook.md`）