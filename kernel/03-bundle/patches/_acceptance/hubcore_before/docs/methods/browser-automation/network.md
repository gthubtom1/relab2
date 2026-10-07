# 网络与等待

先勾 [catalog.md](catalog.md) F1–F4、I1、I2。

## 主等待（按优先级）

1. 合同里的页面保险点（元素、URL、可点）。
2. `waitForResponse` / `waitForRequest` 等 **指定** 接口。
3. `waitForURL`。
4. `waitForFunction` 等某个计算变真。

禁止当主等待：`waitForTimeout`、`networkidle`（心跳/WebSocket 永远不闲）、`load` / `domcontentloaded` 单独用（SPA 数据还没到）。

hash / `history.pushState` / Next 客户端路由是**同文档导航**，常常没有 `load`。等合同 URL 或页上标记。后退可能走 bfcache，生命周期事件不齐：回来也当新快照认状态，不要死等 load。

## Service Worker

第三方 PWA 可能用 SW 喂旧缓存。抽取核唯一 ID/时间戳，不要信「列表又出现了」。`response.fromServiceWorker()` 为真时更要核新鲜度。自己开的测试浏览器才能 block SW；主人已开的窗口不要擅自关对方的 SW。

## 等接口

- 先听再点：和 popup 同一纪律，否则接口已经飞过。
- 保险点仍要回到页面：接口 200 但页上没渲染 = 没做成。
- 匹配 URL 写具体路径，不要 `**/*` 配到埋点。

## WebSocket / 心跳

- 进度、站内信、协同编辑可能走 WS。用页上数字当指纹，不要等 networkidle。
- 需要听 WS 时 `waitForEvent('websocket')` 或 `routeWebSocket`。第三方站默认只读页上结果，不要改对方包。

## 限流

429 / 「操作太频繁」进环境桶，不要标材料坏。退避后同一对象可再试；连续仍 429 就停。

## 上传下载进度

进度走页上原文或进度接口。指纹变了 = 还在动。冻住才算卡。见 [files.md](files.md)。

## 拦截 / 改请求

只对自己有权改的环境做 mock。别人的生产站不要 `route` 改业务结果来「测绿」。HAR 回放只给自己的测试页。

## 失败信号

`requestfailed`、控制台 error、HTTP 5xx 记进现场，但最终仍看页面保险点。接口失败 + 页上却显示成功 = UNKNOWN，不要计数。
