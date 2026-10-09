# 网络 Hook 选点（Network Hook Selection）

> **来源**：改编自 `aoyunyang/spider-king-skill`（MIT License）的 `network.md`。
> **用途**：决定**在哪里** Hook 网络边界。
> **前置**：无 npm 依赖，Hook 为纯 JS。上游 `../scripts/xhr_fetch.js` 与 `../scripts/cookie_header.js` **本包未落地**。
> **用法**：本文件**只做 Hook 点选择，不提供另一套可粘贴实现**。XHR/fetch 请求必须从 `../scripts/xhr_fetch.js` 或 `../scripts/cookie_header.js` 生成，避免无过滤、无事件上限、无恢复函数的旧片段漂移回来。

## XHR 与 Fetch

| 需求 | 用哪个 |
|---|---|
| 请求 method、URL、body 长度、响应状态 | `xhr_fetch.js` |
| 把 Cookie / Authorization / x-sign / token 与具体请求绑定 | `cookie_header.js` |

- 修改脚本顶部的 `CONFIG.urlIncludes` 和 header filter **之后**再交付；默认不打印 header/body 值。
- XHR 二进制响应**只记录 `response` 的类型/长度**，不要直接读 `responseText` —— 那会触发一次额外的读取，改变行为。

## WebSocket

**只盯明确 URL 或消息类型。**

新增项目脚本时必须同时满足：

- 保存并可恢复 `WebSocket.prototype.send` 或 message listener
- 发送和接收**各自**有事件上限
- 只输出 opcode、类型和长度

**不得默认输出 frame 内容。**

## jQuery Ajax

**只有证据表明参数在 jQuery 包装层被改写时**才 Hook `jQuery.ajax`。

- 过滤 URL
- 摘要 `data` 与 headers（只给类型/长度）
- 保留原 `this`、返回的 jqXHR 与异常行为
- 在 registry 中登记恢复函数

## postMessage

必须过滤 `targetOrigin`、`event.origin` 或明确消息字段。

- transferable、ArrayBuffer 和对象 payload **只输出类型与长度**
- 添加的 message listener **必须在 restore 中移除**

## 页面上下文

Console 处于 isolated world 时，才把同一受控脚本注入 main world。注入**不改变**过滤、上限、摘要和 restore 契约。

## 转交

用户真正要 initiator 或完整调用链时，**停止扩写 Hook**，按 `../index.md`「触发边界」表的 capability-aware 契约转交（`../../../../js-reverse/SKILL.md`）；专用技能不可用时返回 Spider core loop。

## 本包实情

上游 `../scripts/` 未随包落地。要生成请求 Hook，按上面的四段结构（filter → cap → registry → restore）实现，或从上游仓库取基准实现。输出格式参照 `hook-output-samples.md`。

## 相关

- `../index.md` — profile 入口与判据
- `storage.md` — Cookie / storage 来源边界
- `hook-output-samples.md` — 输出契约与降噪样本