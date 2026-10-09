# 片段索引（Browser Hook Snippets）

> **来源**：改编自 `aoyunyang/spider-king-skill`（MIT License）的 `snippets.md`。
> **用途**：按你要盯的对象，**只选一个** Hook 分类文档去读。
> **前置**：本 profile 不依赖 npm 包，Hook 是纯 JS。但上游 `../scripts/` 的受测实现**本包未落地**，见文末。
> **用法**：主题文档已经拆分，**不再内嵌第二套可执行片段**。受测脚本在上游的 `../scripts/`；主题文档只帮助你选择最窄 Hook 点并约束新增脚本。

## 目录

1. `network.md` — XHR、fetch、WebSocket、postMessage、页面上下文注入
2. `storage.md` — cookie、localStorage、sessionStorage、表单值
3. `crypto.md` — atob/btoa、crypto.subtle、getRandomValues、TextEncoder/TextDecoder
4. `dom.md` — createElement、appendChild、insertBefore、MutationObserver、canvas
5. `runtime.md` — JSON、eval、Function、Blob、URL.createObjectURL、Worker

## 选择建议

| 你要盯的 | 先读 |
|---|---|
| 请求和消息链路 | `network.md` |
| token、cookie、缓存、输入框值 | `storage.md` |
| 编码、摘要、签名、随机数 | `crypto.md` |
| 动态节点、脚本插入、canvas 指纹 | `dom.md` |
| 动态执行、worker、blob 资源 | `runtime.md` |

**一次只读一篇。** 五篇都读通常意味着目标还没分诊 —— 回到 `../index.md` 的「触发边界」和 `../../../SKILL.md` 的 Auto Judge Card。

## 不建议默认收录的片段

以下四类**不要**默认提供：

1. 大范围去除 `debugger` 的脚本
2. 替换所有 `console` 方法的脚本
3. 全局清除所有 `setInterval`
4. 粗暴重写 `RegExp`、`Date`、`Function.prototype.constructor`

原因不是"不能用"，而是**副作用通常大于定位收益**，容易把页面行为改坏 —— 而页面行为一旦变了，你观察到的现象就未必是真实的了。

## 本包实情

上游 `../scripts/` 目录（`xhr_fetch.js`、`cookie_header.js`、`crypto_api.js`、`storage.js`）与 `tests/` **未随本包落地**。本文的选点规则仍然有效，但生成新脚本时需要：

- 从上游 MIT 仓库取 `scripts/` 作为结构基准，或
- 按 `network.md` 描述的 filter / cap（事件上限）/ registry / restore 四段结构自行实现

无论哪种，新脚本都必须满足 `../index.md`「判据」一节的全部勾选项。

## 相关

- `../index.md` — profile 入口：触发边界、默认输出、判据
- `hook-output-samples.md` — 输出契约与降噪样本