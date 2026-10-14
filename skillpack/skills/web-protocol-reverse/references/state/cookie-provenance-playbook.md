# Cookie 溯源手册（Cookie Provenance Playbook）

> **来源声明**：本文改编自外部仓库 `aoyunyang/spider-king-skill`（MIT License）的 `cookie-provenance-playbook.md`。原始内容为英文原文，此处译为中文并按本包六段式规范重排；技术术语保留英文原词并附中文，AI 检索时中英文均可命中。改编中修正了源文档的若干表述（见文末「源文档勘误」）。
>
> **什么时候用**：replay（重放）依赖某个 cookie，但**它是谁写的、怎么刷新**还不清楚。
>

> ★★ **本机 playwright 必须显式指定浏览器**（2026-10-10 实测）：
> `launch()` 默认启动会报 `Executable doesn't exist at %LOCALAPPDATA%\ms-playwright\chromium_headless_shell-1234\...`
> —— python 包期望 1234，本机装的是 **1243**，版本号对不上。
> **可用写法**：`p.chromium.launch(channel="msedge")`（实测能起、能渲染、能读 DOM），
> 或 `launch(executable_path=<显式路径>)`。照抄裸 `launch()` 一定失败。
> 

---

## 适用信号（Recognition signals）

出现下列任一情况，说明该走 Cookie 溯源路线：

- 从浏览器拷出来的 cookie 直接塞进代码就失效，但不知道它是谁写上去的
- cookie 值会在翻页、验证通过、会话刷新时变化
- 页面文案写着「请先登录」，但 wire 上看不出登录和该请求的关系
- 签名（signer）算对了仍失败，怀疑真正拦路的是 cookie 轮转
- 存储的 cookie jar 看着对，但抓包看到的出站 `Cookie` 头顺序或片段不一样
- 首次响应种下一批 seed cookie，本地执行后又被另一批派生值覆盖
- 多跳登录后 cookie 只保存了一部分，激活阶段还要再拿一批

## 前置（Entry conditions）

1. **至少一条成功的样本请求 + 一条失败的样本请求**。两者都要能重放，否则 diff 无从谈起。参见 `../triage/positive-sample-hygiene-playbook.md`。
2. **wire 可见性**。优先用 mitmproxy 直接看到出站请求头；若走浏览器，用 `tshark` 抓 loopback 或 CDP 代理流量。本机两条路都可用：
   ```powershell
   # 方式一：mitmproxy 实时改写/观察（本机可用）
   & (Resolve-ReverseToolSpec -Name 'mitmdump').Command --listen-port 8899 --save-stream-file flow.mitm
   # 方式二：tshark 离线读已抓的 pcap（本机可用）
   & (Resolve-ReverseToolSpec -Name 'tshark').Command -r flow.pcapng -Y "http.cookie" -T fields -e http.request.full_uri -e http.cookie
   ```
3. **本地执行宿主的定位**。若怀疑是「服务端返回的 JS 写了 cookie」，需要能跑 JS 的宿主。本机现状：
   - `node` 可用 —— 对「只需要 `document.cookie` 赋值」的 bootstrap（引导）脚本，通常够用。
   - `iv8` **本机无**（社区运行时，PyPI 上不存在该发行版）。若你手上已有该运行时，`../crypto/iv8-runtime-cheatsheet.md` 的 API 形态可参考，但**该文档的形态未在本机验证**。
   - 需要真实 DOM/定时器语义时走 `playwright`（本机可用），但它属于「重活」，只在轻量宿主证明不够时才升级。
4. **适用面**：目标是你能直连的 Web 客户端。涉及验证码/风控的部分见 `challenge-state-envelope-playbook.md`，那里的定位是「理解并建模服务端挑战」，不是绕过。

## 步骤（Working method）

### 核心规则

**在证明写入方和刷新路径之前，不要把会轮转的业务 cookie 写死进代码。**

必须区分两类状态：

- **server-issued seed state（服务端下发的种子状态）** —— `Set-Cookie` 给的，通常短命，是「原料」。
- **locally derived replay state（本地派生的重放状态）** —— 页面 JS 算出来的，是「成品」。

并且，当存在 helper 组装（拼装）或 wrapper 改写逻辑时，**最终出站的 `Cookie` 头本身是一等公民证据（first-class artifact）**，而不是 cookie jar 的附属品。

### 可能的写入方（7 类，勿压缩）

一个「拦路 cookie」通常来自下面七处之一。这份清单要完整用，不要凭印象砍掉第 6、7 类 —— 那两类恰恰是最常被误判的：

1. 协议响应上的 `Set-Cookie`
2. 页面 JavaScript 里的 `document.cookie`
3. **服务端返回的 bootstrap（引导）或 challenge（挑战）JS 执行副作用**
4. 本地构造器（builder）由 bootstrap config、指纹数据、类 UUID 状态或其他页面输入算出
5. 重定向包装页（redirect wrapper）、iframe、worker 或 SDK 的副作用
6. **其实是「派生 header 或 token」问题，只是长得像 cookie 问题**
7. **本地 helper 或运行时，从多个来源拼装出最终出站 `Cookie` 头**，其中只有一部分真以 cookie 形式存储

第 6 类的典型误判：盯着一个叫 `__session` 的值挖了半天，实际拦路的是 `x-sign` / `x-token` 这类派生头。
第 7 类的典型误判：从 jar 里读出一个 `m=a|b|c`，以为拼回去就行，实际线上是 `m=c|b|a` 且 `a` 是运行时算的。

### 要记录什么（What to capture）

围绕**那一次具体的请求边界**记录 cookie 迁移：

1. 调用前的请求 cookie
2. 响应头，尤其是 `Set-Cookie`
3. 响应后立刻的 cookie 状态
4. 任何 JS 写入，例如 `document.cookie = ...`
5. 值是否在翻页、验证器（verifier）通过、会话刷新时变化
6. **确切的出站 `Cookie` 头**，含顺序、缺省片段、helper 拼装的分段（前提是浏览器或本地运行时能暴露 request egress 出向流量）
7. 喂给 cookie 的本地输入：config blob、时间戳切片、UUID 变体、指纹向量、兼容性常量
8. 首次响应与最终 replay 使用不同 cookie 形态时，哪些片段属于 bootstrap seed state、哪些属于 replay state
9. 响应侧挑战（response-side challenge）是轮转了 seed tuple、派生 replay cookie，还是两者都轮转，之后重试才成功

**关于 `document.cookie` hook 静默的读法**：hook 没触发，只能证明「在观测窗口内没有写入穿过这个 JS setter 边界」。它**不能**排除 `Set-Cookie`、返回的 bootstrap JS、重定向、worker 或 wrapper 副作用。窄结论，不要读成全结论。

**jar ≠ 出站头**：存储的 cookie jar 与最终出站 `Cookie` header 是相关但不等价的证据。path 规则、顺序、wrapper 改写、helper 拼装，都可能让线上真实头部与 `document.cookie` 或库管理的 jar 不同。replay 仍失败时，抓实际过边界的那条 header。

cookie 出现在重定向或 wrapper 页之后出现时，**把重定向链当作 provenance（来源/出处）故事的一部分**，而不是当作噪声。

**名字不证明出处**：`session` 样、`fingerprint` 样、`telemetry` 样的 cookie 名**不能证明**服务端下发。有些拦路 cookie 完全在客户端用 bootstrap config、紧凑 JSON 指纹、UUID 变体、内嵌兼容性常量铸造（mint）出来，然后本地写入，甚至只出现在最终出站头里。

### 状态迁移表（State transition table）

当 cookie / token / verifier 状态似乎在拦 replay 时，记录**有序状态机**，而不只是最终值。表头固定为：

```text
step | route | outbound state hashes/lengths | response status | state writes | next outbound authority
```

- **一行一个网络边界（network boundary）**。
- 只要参与了同一条链，就都要入表：document 响应、bootstrap 资产、sidecar/遥测请求、verifier 响应、重定向，以及最终的业务请求。

**迁移顺序本身就是协议的一部分。** 一个看起来完全正确的最终 cookie / token / header，如果在错误的步骤被写入、存在错误的 path 下、被下一个请求跳过、或在下游消费者读取前被覆盖，照样是陈旧的（stale）。

### 工作法

1. 抓一条成功请求 + 一条失败请求
2. 在**每个网络步骤**前后 diff cookie 状态
3. 在建模刷新逻辑**之前**，先把 server-issued seed cookie 与 locally derived replay state 分开
4. 在源码里搜 cookie 名和 `document.cookie`
5. 有 egress 证据时，把存储的 cookie 状态与确切出站 `Cookie` 头对比，含顺序与 helper 拼装的片段
6. **判定写入方类别**：
   - 响应头（response header）
   - 内联脚本（inline script）
   - 返回的 challenge JS
   - 本地铸造公式（local minting formula）
   - wrapper 页或 SDK 副作用
7. **证明刷新路径**：
   - 每次都走同一个 endpoint
   - 业务 endpoint 上的响应侧挑战 tuple
   - verifier 步骤
   - 页面暴露的刷新函数
   - session bootstrap
   - 由 config JS、指纹向量、结构化随机 id、兼容性常量作种子的本地公式
8. **之后才选交付形态**：
   - 服务端设置它 → 保留协议响应
   - bootstrap JS 设置它 → 重放本地 JS
   - 页面代码从 config / 指纹 / 会话输入派生 → 精确重建本地铸造配方
   - 它与账号绑定 → 建模成 session contract 的一部分（见 `session-contract-playbook.md`）

### 多跳登录与激活链（Multi-hop login and activation chains）

当 cookie 在登录、重定向交接（redirect handoff）、异步同步、业务代理、会话更新这些调用之间累积时：

1. **整条链保持在同一个 session 对象上**
2. 给每个产物分类：seed cookie / handoff ticket（交接票据）/ async sync cookie / activation cookie（激活 cookie）/ final business cookie
3. 短命的 handoff ticket 和 async URL **立即消费**；不要把它们提升（promote）成持久凭据文件
4. **只有在最终业务身份被重新读取（reread）并被接受之后**才导出
5. 刷新出的候选 jar 若通不过身份校验，**拒绝覆盖**上一份持久文件

对多上下文后台系统来说，单个响应的 `Set-Cookie` 极少是全部故事。身份分层见 `multi-context-session-playbook.md`。

## 判据（Verification checklist）

只有满足以下**全部 7 条**，才可以说「cookie 问题搞懂了」：

1. **写入方已被定位** —— 归到上面 7 类中的哪一类，有证据，不是猜的
2. **刷新触发条件已知** —— 什么事件让它轮转，说得清
3. **本地铸造的 cookie（如果有）结构、输入、写入路径均已证明** —— 不是「跑出来一个值」就算，是能重建
4. **helper 拼装 / wrapper 改写的出站 `Cookie` 头已被证明**，包括顺序在有意义时的顺序；**不是**仅从 jar 反推出来的
5. 若响应侧挑战会轮转一个 tuple，采集器在重试前**一致地更新整个 tuple**，而不是只更新其中一个成员
6. 采集器**不依赖浏览器自动化**就能重新生成或保存该 cookie 路径
7. 用恢复出的 cookie 路径，**replay 至少成功两次**

## 常见坑（Common traps）

- 没证明谁写的，就把浏览器 cookie 拷进代码
- 真正的问题是 cookie 轮转，却在骂 signer（签名器）
- 只读了最终 cookie 字符串，没读产生它的写入路径
- 把 `document.cookie` 或客户端 jar 当成完整的 wire 真相，而实际出站 `Cookie` 头不同
- 假定两个 cookie jar 重放等价，而线上出站头的顺序或拼装方式不同
- 去刷新整个浏览器页面，而不是在本地重建最小的 cookie 刷新契约
- 把 `session` 样 / `fingerprint` 样的 cookie 名当成 `Set-Cookie` 出处的证明
- 用任意随机 UUID、随机 hex 或占位摘要替换掉一个**有结构的本地 id**
- 客户端序列化的是**一份确切的指纹向量和确定的条目顺序**，你却对「语义等价」的 JSON 重算摘要
- 把 server-issued seed cookie 当成已经完成的最终 replay 产物
- 路由实际轮转的是「seed tuple + 一个本地派生 replay 值」，你却只刷新了一个 cookie 名
- 把 helper 副作用 cookie 盲目并进主会话，而没检查决定性产物其实是被拼装出来的出站 `Cookie` 头
- 只保存了 login POST 的 cookie，把后续激活阶段的 cookie 丢了
- 把一次性交接票据（one-time handoff ticket）当成长期会话 cookie
- 业务身份校验还没过就导出了 jar

## 相关（Related）

- `session-contract-playbook.md` —— cookie 与账号绑定时的会话契约分层
- `multi-context-session-playbook.md` —— 多跳登录与业务上下文激活
- `server-js-cookie-bootstrap-playbook.md` —— 「服务端返回 JS、执行后拿到 cookie」这一具体形态
- `side-asset-bootstrap-playbook.md` —— cookie 由旁路小资产铸造的情况
- `challenge-state-envelope-playbook.md` —— 挑战输出作为协议状态时的迁移
- `../observe/transport-pre-gate-playbook.md` —— 传输层 wrapper 与前置门（拿到出站头证据）
- `../triage/verifier-replay-playbook.md` —— 判据第 7 条「replay 成功两次」的验证规程
- `../deliver/pure-python-rebuild-playbook.md` —— 判据第 6 条的无浏览器交付形态

---

## 源文档勘误（改编时修正）

1. 源文档 `## Possible writers` 一节标题为复数但正文写成 `A blocking cookie usually comes from one of these places`（单数）。7 类清单本身正确，改编时统一为「7 类」。
2. 源文档状态迁移表表头写 `outbound state hashes/lengths`，而本文任务描述里的简写形式是 `outbound state`。两者语义相同；本文保留源文档的完整表头，因为**长/哈希比原值更适合作为可复现证据**（原值可能本身就是秘密或超长）。
3. 源文档正文用 `multi-context-session-playbook.md` 风格路径，但该文件实际就在 `references/state/` 同级目录，原路径写法会指向不存在的 `references/references/`。已改为同目录相对引用。