# 运行时 Hook 选点（Runtime Hook Selection）

> **来源**：改编自 `aoyunyang/spider-king-skill`（MIT License）的 `runtime.md`。
> **用途**：决定观察动态执行、Blob、Worker、timer 时**在哪**埋点，以及交付时的红线。
> **前置**：无 npm 依赖，Hook 为纯 JS。上游 `../scripts/xhr_fetch.js`（作为结构基准）**本包未落地**。
> **用法**：动态代码、Blob、Worker 和 timer 的 Hook **破坏面较大**。本文件只规定选择和交付约束；生成新脚本时复用 `../scripts/xhr_fetch.js` 的 `filter` / `cap` / `registry` / `restore` 结构，**不使用无生命周期的历史片段**。

## JSON

只有**明确字段、URL 或调用栈特征**时才观察 `JSON.parse` / `JSON.stringify`。

- 字符串和对象只输出类型/长度
- **全站 JSON Hook 必须有很低的事件上限，并尽快恢复**

## eval 与 Function

**优先使用 debugger / 源码插桩，而不是 Hook。** 确需 Hook 时：

- 只摘要 source 的长度和 hash
- 保持 direct / indirect eval 语义，并在交付时**明确声明风险**（构造器替换可被检测）
- 命中异常立即恢复

## Blob 与 Object URL

- 记录 Blob part 的**类型、总字节数和 MIME**，不打印完整脚本/二进制
- `URL.createObjectURL` 只关联 Blob metadata
- 构造器 prototype、static 属性、`new` 语义和 restore **都必须验证**

## Worker

- 过滤明确的 script URL
- constructor、`postMessage` 和 message listener **分别限流**
- payload 只摘要类型/长度
- restore 时还原构造器并移除 listener

⚠️ Worker 在 Hook 安装**之前**就创建时，改从**创建调用栈**取证 —— 事后 Hook 拦不到。

## Timers

- 只观察 source 命中**特定 token** 的 callback
- **不取消、不改 delay、不清空所有 timer**
- 记录 delay、callback 类型和一次 stack
- restore 之后原 timer API 必须保持**引用一致**

## 转交

未知动态入口，或需要完整函数位置时，按 `../index.md`「触发边界」表的 capability-aware 契约转交（`../../../../js-reverse/SKILL.md`）；专用技能不可用时返回 Spider core loop。

**本 profile 不通过扩大 Runtime Hook 来代替调用链取证。** 这是本篇最重要的一条：Hook 只能告诉你"某处调了"，告诉不了你"整条链是怎么走的"。

## 本包实情

上游 `../scripts/xhr_fetch.js` 未随包落地，它是 filter → cap → registry → restore 四段结构的参照。要生成 runtime Hook：

- 从上游 MIT 仓库取该脚本作为结构模板，或
- 直接按上面各节的约束实现

输出格式参照 `hook-output-samples.md`。

## 相关

- `../index.md` — profile 入口与判据
- `crypto.md` — 编码与摘要
- `dom.md` — 动态节点与脚本插入
- `hook-output-samples.md` — 输出契约
- `../../../references/observe/anti-debug-playbook.md` — 目标有反调试时的应对