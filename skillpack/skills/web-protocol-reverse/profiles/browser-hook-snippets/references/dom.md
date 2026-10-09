# DOM Hook 选点（DOM Hook Selection）

> **来源**：改编自 `aoyunyang/spider-king-skill`（MIT License）的 `dom.md`。
> **用途**：决定观察 DOM / Canvas 时**在哪**埋点。
> **前置**：无 npm 依赖，Hook 为纯 JS。上游 `../scripts/xhr_fetch.js`（作为结构基准）**本包未落地**。
> **用法**：DOM / Canvas **没有通用的"全开"安全脚本**。先确定**一个** tag、selector、method 或 canvas operation，再在任务工程里按 `../scripts/xhr_fetch.js` 的 lifecycle 结构生成专用脚本。

## 元素创建与插入（Element Creation And Insertion）

- `createElement` **只过滤** `script`、`iframe` 或用户指定 tag。
- `appendChild` / `insertBefore` 只记录 tag、src 是否存在、父节点类型；**不打印完整 node/HTML**。
- 保存原函数，保持 receiver、参数、返回值与异常；restore 时**条件式写回**。

## MutationObserver

**优先用 observer，而不是改写原型。**

- 限制 root、subtree 范围、tag/selector 和事件数
- 日志只给节点类型和受控属性
- restore 必须 `disconnect()` 并删除 registry 项

## Canvas

只观察**已确认**的 `getContext`、`fillText` 或 `toDataURL` 边界。

- 文本**只给长度**
- data URL **只给 MIME + 长度**
- WebGL 参数**只给明确的 pname**

⚠️ Canvas Hook 可以显著改变指纹路径 —— 目标可能因为你多调了一次 `getContext` 就换了一套渲染结果。命中异常时**立即恢复并转引擎级 trace**。

## 交付契约（Delivery Contract）

新 DOM 脚本必须具备：

1. `CONFIG` 过滤器（tag / selector / operation）
2. `maxEvents`（事件上限）
3. 摘要函数（只出类型/长度）
4. `window.__spiderHooks.<name>.restore()`
5. 一次可信的触发验证

**缺少 selector / tag 时先补证据，不生成全局原型 Hook。** 全局原型 Hook 的副作用远大于定位收益。

## 本包实情

上游 `../scripts/xhr_fetch.js` 未随包落地，它是"lifecycle 结构"的参照基准。要生成 DOM Hook：

- 从上游 MIT 仓库取该脚本作为结构模板，或
- 直接按上面「交付契约」的 5 条实现

输出格式参照 `hook-output-samples.md`。

## 相关

- `../index.md` — profile 入口与判据
- `runtime.md` — 动态执行、Blob、Worker
- `hook-output-samples.md` — 输出契约
- `../../../references/observe/hook-techniques.md` — Hook 技法总览