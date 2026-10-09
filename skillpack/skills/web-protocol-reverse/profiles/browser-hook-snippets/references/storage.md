# 存储 Hook 选点（Storage Hook Selection）

> **来源**：改编自 `aoyunyang/spider-king-skill`（MIT License）的 `storage.md`。
> **用途**：说明 **storage / cookie 的来源边界**，并规定可执行 Hook 从哪来。
> **前置**：无 npm 依赖，Hook 为纯 JS。上游 `../scripts/cookie_header.js` 与 `../scripts/storage.js` **本包未落地**。
> **用法**：本文件**只说明来源边界**。可执行的 Cookie/storage Hook **只从** `../scripts/cookie_header.js` 和 `../scripts/storage.js` 生成，不从本文复制片段。

## 核心边界：三个来源不能混

| 来源 | 能证明什么 | 不能证明什么 |
|---|---|---|
| `document.cookie` 写 Hook | 页面 **JS** 主动写了 Cookie | 不能证明没有 HTTP `Set-Cookie` 也在写同名 Cookie |
| HTTP `Set-Cookie` 响应头 | 服务端**确实下发了**该 Cookie | 不能证明 JS 读它时会用 |
| `localStorage` / `sessionStorage` | 页面级持久化状态 | 不能证明它参与了签名（除非 wire 证据） |

⚠️ **最常见的误判**：看到 `document.cookie` 被 JS 写了一次，就断定"这个 cookie 是签名的输入"。页面上写着"本 cookie 参与签名"也只是**假设** —— 在 wire 行为确认之前不要据此改补环境。详见 `../../../references/state/cookie-provenance-playbook.md`。

## 选点规则

### cookie

- Hook `document.cookie` 的 **setter**，不是 getter。getter 命中会刷屏且几乎不产出新信息。
- 只记录 `name` 与 `valueLength`，**不记录 value**。
- 需要把 cookie 与具体请求绑定时，改用 `network.md` 的 `cookie_header.js` 路线。

### localStorage / sessionStorage

- Hook `Storage.prototype.setItem` / `removeItem` / `clear`（原型方法，避免逐实例改写）。
- 只记录 `key` 与 `valueLength`。
- `getItem` 高频命中，**只在有明确 key 白名单时才 Hook**。

### 表单值

- 只在证据表明表单值参与提交构造时才 Hook。
- 优先用 `network.md` 的请求侧观察，避免污染表单对象的原生语义。

## 降噪

`storage` 类 Hook 的命中量通常远大于网络类。默认策略：

1. 先加 `key` / `name` 白名单过滤
2. 再设 `maxEvents`（事件上限）
3. 命中一次验证后就恢复

**不要**为了"看全"而关掉上限 —— 那会改变页面时序，且引入观察者效应。

## 本包实情

上游 `../scripts/cookie_header.js` 与 `../scripts/storage.js` 未随包落地。要生成 storage Hook：

- 从上游 MIT 仓库取基准实现，或
- 按 `network.md` 描述的 filter → cap → registry → restore 四段结构自行实现

输出格式参照 `hook-output-samples.md`。

## 相关

- `../index.md` — profile 入口与判据
- `network.md` — 请求侧：把 Cookie/header 与具体请求绑定
- `hook-output-samples.md` — 输出契约
- `../../../references/state/cookie-provenance-playbook.md` — Cookie 来源证明方法论