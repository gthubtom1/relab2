# 服务端 JS Cookie 引导手册（Server-JS Cookie Bootstrap Playbook）

> **来源声明**：改编自 `aoyunyang/spider-king-skill`（MIT License）的 `server-js-cookie-bootstrap-playbook.md`。英文原文译为中文，术语保留英文原词并附中文，按本包六段式规范重排。
>
> **什么时候用**：接口第一次返回的不是数据，而是一段要跑一下的 JavaScript。
>

> ★★ **本机 playwright 必须显式指定浏览器**（2026-10-10 实测）：
> `launch()` 默认启动会报 `Executable doesn't exist at %LOCALAPPDATA%\ms-playwright\chromium_headless_shell-1234\...`
> —— python 包期望 1234，本机装的是 **1243**，版本号对不上。
> **可用写法**：`p.chromium.launch(channel="msedge")`（实测能起、能渲染、能读 DOM），
> 或 `launch(executable_path=<显式路径>)`。照抄裸 `launch()` 一定失败。
> 

---

## 适用信号（Recognition signals）

- API 第一次返回 `202` 或其他非终态状态码，且响应体里带 JavaScript 载荷
- `JSON.data` 里装的是可执行 JS，而不是预期的数据数组
- 页面只有在一段返回代码被跑过、生成 `m` 之类的 cookie 之后才成功
- 同一个接口必须调两次：一次拿挑战（challenge），一次拿数据
- 页面脚本暴露一个刷新函数，重跑它能续期 cookie 或请求参数
- 文档路由（document route）首次返回 `412` 之类的非终态 HTML

## 前置（Entry conditions）

1. **能重复触发挑战**。挑战载荷常带 nonce 或时效，必须能在新鲜会话上重放。缺这一条，本手册的所有路径都无从验证。
2. **本地 JS 执行宿主**。本机默认用 `node`：
   - `node` + 少量 API stub 足以应付「只做 `document.cookie = ...`」的载荷。
   - 需要 `window` / `navigator` / `location` / 定时器 / DOM 顺序语义时，`../crypto/iv8-runtime-cheatsheet.md` 有形态参考，但 **`iv8` 本机无、未在本机验证**。
   - 需要真实解析器与脚本执行顺序保真时，用 `playwright`（本机可用）加载空白页注入脚本，或建一个最小 HTML 宿主。
3. **wire 可见性**，用于判据第 6 条。本机用 mitmproxy：
   ```powershell
   & (Resolve-ReverseToolSpec -Name 'mitmdump').Command -p 8899 -w bootstrap.mitm
   ```
4. **适用面**：目标是你能直连的 Web 客户端。本文是协议逆向方法论：目标是理解「服务端返回代码 → 本地执行 → 拿到状态 → 重放」这条链路，**不是**教人绕验证码或风控。

## 步骤（Steps）

### 1. 识别形态

典型流程：

1. 不带派生 cookie/token 调用目标接口
2. 收到挑战响应，常见是 `202`
3. 挑战载荷含可执行 JS
4. 执行载荷设置 `document.cookie`、storage 或某个 token 变量
5. 用新状态重放同一接口
6. 拿到真实数据数组

**站点明显把首次响应当成 bootstrap（引导）步骤时，不要把它当错误。**

变体一（刷新函数在页面上）：

1. 页面加载时从独立脚本端点下载混淆 bootstrap JS
2. 内联页面代码暴露一个函数，例如 `_$KS()`
3. 重跑该函数刷新 cookie 或请求参数
4. 还有一个额外的内存时间戳（例如 `$_zw[23]`）必须一起更新
5. **两样都刷新**之后重放才成功 —— 漏掉其中一样是最常见的失败原因

变体二（挑战 HTML 而非 JSON）：

1. 对文档路由的首次请求返回 `412` 之类非终态 HTML
2. 该 HTML 携带内联 bootstrap 状态 + 一个或多个外链 challenge 脚本
3. 首次响应同时种下一批 cookie，但那些**只是 bootstrap 输入**
4. 本地执行挑战，产出可重放的 cookie 或完整出站 `Cookie` 头
5. 从 Python 重放同一文档 URL，得到真实 HTML 页面

### 2. 要记录什么（What to capture）

以下全部记录，缺一项后面判据就过不了：

1. 首次请求的 URL、method、query、headers、cookies
2. 首次响应状态码
3. 首次响应体形态，含内联 bootstrap 状态与外链 challenge 资产（若存在）
4. **本地执行之前**从首次响应拿到的 seed cookie 状态
5. 执行返回的 JS **之后**被写入的确切 cookie 或 token
6. 重放请求上确切的外发 `Cookie` 头（有 egress 证据时）
7. 第二次请求与第一次的差异
8. 后续页面是否改了 `User-Agent` 之类的 header
9. 页面是否还并行维护了一个必须一起刷新的内存值
10. **语义锚点（semantic anchors）**：证明重放回来的页面是真业务内容，而不是又一层壳

### 3. 最快的稳定路径

原则：**选最小可行路径**，不要一上来就完整反混淆。

基本形态：

1. 请求接口
2. 若 `data` 不是最终数组，就把它当成 challenge JS
3. 在最小沙箱里执行
4. 抽出派生 cookie 或 token
5. 用新状态重放同一请求

这通常比「先完整反混淆再交付」更快。

首次响应是挑战文档页而非 JSON 时：

1. 请求一次文档 URL
2. 若响应是非终态 HTML（如 `412`），把内联 bootstrap 状态、外链 challenge JS、seed cookie **冻结在同一条会话链上**
3. 在最小沙箱里本地执行挑战
4. 抽出**最终可重放的 cookie 或完整出站 `Cookie` 头**，而不只是某一个 cookie 名
5. 从 Python 重放同一文档 URL
6. **在扩分页之前**先验证返回 HTML 的语义锚点

bootstrap 逻辑已经在页面上时：

1. 调用暴露的刷新函数
2. 更新页面作为请求参数传出的时间戳槽位
3. 从同一浏览器上下文重放

相关形态（全局请求钩子）：

1. 页面装了全局请求钩子，例如 `$.ajaxSetup(beforeSend)`
2. 业务代码看起来在发普通表单数据
3. 钩子把 body 改写成加密载荷并加上签名头
4. 响应外层 JSON 可读，但只对 `data` 字段加密
5. 恢复需要**同时**移植钩子期的请求改写与响应字段解密 —— 只做一半必然失败

### 4. 最小沙箱清单

多数 bootstrap 载荷只需要一小撮浏览器 API：

- `window`
- `document.cookie`
- `navigator.userAgent`
- `location.href`
- `Date` / `Math`
- `setTimeout` / `setInterval`
- `atob` / `btoa`
- `encodeURIComponent` / `decodeURIComponent`
- 足够的解析器与脚本执行顺序保真度，以便在顺序有影响时先跑内联 bootstrap 状态、再跑外链 challenge 脚本

**从最小集合起步，只在运行时报错证明需要时才加。** 一上来补齐上百个指纹字段是典型的过早优化。

本机落地：`node` 侧写一个 stub 文件先映射上述成员；需要执行顺序保真时改用 `playwright` 加载 `about:blank` 后 `add_script_tag`。

### 5. 解析结果

执行完返回的 JS 后：

1. 读最终 `document.cookie`
2. 抽出目标 cookie 的值
3. 忽略 `path=/` 之类附加属性，除非它对重放有影响

**永远不要盲信整条原始 cookie 字符串**，只抽取重放真正需要的那一个值。

### 6. 交付建议（Delivery recommendation）

推荐结构：

- `extract_cookie.js`（或 `extract_m.js`）—— 本地 helper
- `fetch_all.py`（或 `.js`）—— 采集器
- `../../README.md` —— 说明

helper 负责：

1. 接收返回的 JS 载荷
2. 在沙箱里执行
3. 返回派生 cookie / token，或完整可重放 `Cookie` 头

采集器负责：

1. 取挑战载荷
2. 调 helper
3. 重放接口
4. 聚合结果

## 判据（Verification checklist）

满足以下**全部 6 条**才算完成：

1. helper **稳定**地抽出 cookie / token / 完整可重放的 `Cookie` 头（多次调用结果一致，不是偶然跑通一次）
2. 重放返回**真实数据**，不是又一个挑战载荷或壳页面
3. 语义锚点（预期的 DOM 块、分页标记）证明重放回来的页面是真实目标内容
4. 所有请求的页面都成功
5. 任何页面专属的 header 规则、或用户明确给出的时序限制，**都已写进文档**
6. 最终脚本**直接打印或保存**所要求的输出

## 常见坑（Common traps）

- 把首次响应当错误处理，而不是当 bootstrap 步骤
- 刷新了 cookie 却忘了同步更新并行的内存时间戳槽位（或反之）
- 只抽了单个 cookie 名，忽略运行时实际拼装出的完整出发 `Cookie` 头
- 从挑战页抽状态时，把 seed cookie 与派生 replay cookie 混为一谈
- 用一个纯净的新客户端重放，而挑战状态是在另一条会话链上产生的
- 沙箱里补了过多 API，掩盖了「到底哪个 API 被读到」这个真正要回答的问题
- 只移植了全局钩子的请求改写，忘了响应侧字段解密（或反之）
- 语义锚点没验就开始翻页，把壳页面当成数据源
- 盲信整条 cookie 字符串，把 `path`、`expires` 等属性当成值的一部分
- 只在浏览器里验证成功就交付，最终路径仍依赖浏览器

## 相关（Related）

- `cookie-provenance-playbook.md` —— 完整的 cookie 写入方分类与状态迁移表，本文的上游方法论
- `side-asset-bootstrap-playbook.md` —— 载荷来自独立小资产而非响应体的邻近形态
- `challenge-state-envelope-playbook.md` —— 挑战输出作为协议状态、跨字段共用一个信封族
- `challenge-artifact-harvest-playbook.md` —— 不想重建、只想就地摘取产物时的路线
- `../crypto/local-challenge-executor-playbook.md` —— 本地挑战执行宿主的搭建细节
- `../crypto/environment-patch-playbook.md` —— 沙箱报缺 API 时的最小补丁规程
- `../triage/verifier-replay-playbook.md` —— 判据第 1 条「稳定」的验证方法
- `../deliver/pure-python-rebuild-playbook.md` —— 无浏览器最终交付形态

---

## 源文档勘误（改编时修正）

源文档本身内容正确，无事实性错误。仅两处适配性调整：

1. 源文档第 4 节只列了最小 API 集合，没有指明运行时来源。本文按本机现状补了 `node` / `playwright` 的分工，并显式标注 `iv8` 本机不可用。
2. 源文档「Delivery recommendation」小节用英文编号标题，与其余小节的英文风格一致；本文统一并入「步骤」段，交付形态本身未改动。