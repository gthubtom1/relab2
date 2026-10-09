# 浏览器 Hook 片段 Profile（Browser Hook Snippets Profile）

> **来源**：改编自 `aoyunyang/spider-king-skill`（MIT License）的 `index.md`。原文主体已中文化，本次改编补齐中文标题、来源声明与本机化标注。
> **用途**：围绕**用户已知的观察点**，交付一段最小、可恢复、低噪声的浏览器 Hook。
> **前置**：本 profile **不依赖任何 npm 包**，Hook 片段是纯 JS，贴进 DevTools Console / Snippets 即可运行。Node `D:\Tools\Node\node.exe` v24.20.0 仅在你想在 Node 里跑片段时需要。
> **⚠️ 本包实情**：本 profile 自带的 `scripts/`（`xhr_fetch.js`、`cookie_header.js`、`crypto_api.js`、`storage.js`）与 `tests/` **未随包落地**。下方「资源路由」里对这些脚本的引用是**上游路径**，本包内没有对应文件 —— 要用得先从上游 MIT 仓库取，或按 `references/` 里的结构约束自行实现。所有 `references/*.md` 只规定 Hook 点选择与交付约束，**不内嵌第二套可粘贴实现**。

---

## 目录

- [唯一职责](#唯一职责)
- [触发边界](#触发边界)
- [默认输出](#默认输出)
- [工作流](#工作流)
- [数据与请求绑定](#数据与请求绑定)
- [安全与降噪](#安全与降噪)
- [Failure Modes](#failure-modes)
- [资源路由](#资源路由)
- [判据](#判据)

## 唯一职责

围绕用户已知的观察点，交付一个最小、可恢复、低噪声的浏览器 Hook。

**本 profile 不负责**找到最终函数位置，**也不负责**把采样代码迁移到本地运行时。

阶段协议沿用 `../../SKILL.md` 主入口与 `../../references/principles/workflow-overview.md`；本 profile 主要承担 Capture（观察取证）。本文件中的 `scripts/` 和 `references/` 路径均相对于 `$HOOK_PROFILE = <skill>/profiles/browser-hook-snippets`（原文写的是 `$SKILL_DIR/references/profiles/browser-hook-snippets`，本包路径不同）。

## 触发边界

**应该触发**：

1. 「给我一段能直接贴到 DevTools 的 hook」。
2. 「临时看看谁写了 cookie / token / header / storage」。
3. 「只过滤某个 URL，观察 fetch / xhr / WebSocket / worker / crypto / canvas」。
4. 「先采样参数和调用栈，暂时不需要函数定位」。

**不应触发**：

| 用户真正要的结果 | 转交 |
|---|---|
| 脚本 URL、函数位置、initiator 或完整调用链 | 能力快照里有专用 JS 逆向技能就转交（本包内为 `../../../js-reverse/`）；否则返回 Spider core loop，用 `chrome-devtools` / `js-reverse` 的 initiator 证据定位 |
| 整份源码的结构化还原 | AST profile 存在就转交（`../static-ast/index.md`）；否则用 `../../references/crypto/offline-inline-deob-playbook.md` 与 `../../references/crypto/obfuscation-guide.md` 做本地静态恢复 |
| 已知入口在 Node.js / VM 中运行 | `../env-patch/index.md` |
| 明确要 Python + iv8 脚本 | **本机无 iv8**（社区运行时，PyPI 上没有）。如实报告约束未满足；只有用户接受替代后，才使用 env-patch 或 Spider 的 local-helper 边界 |
| 多层协议和最终采集器 | 退出 profile，返回 Spider core loop |

所有外部转交都先读能力快照。不得假设某个技能存在；专用技能不可用时必须执行表中的 Spider fallback。

## 默认输出

**始终给出**：

1. 一段可直接执行的最小脚本。
2. 注入位置和时机。
3. 触发动作与预期日志。
4. 副作用、恢复函数，或刷新恢复说明。

用户目标明确时再说明为什么选择该 Hook 点。**不要同时堆多个大脚本。**

🔴 **CHECKPOINT**：改写原型链、全局对象、构造器或返回值之前，先声明 Hook 点、页面上下文、恢复方式和可检测风险。用户未要求篡改行为时**只做观察**。

## 工作流

1. 判断目标是属性、方法、构造器还是请求边界。
2. 选择最窄的 Hook 点和 URL/字段过滤条件。
3. 保存原始 descriptor 或函数引用，保持 `this`、参数、返回值和异常语义。
4. 默认只记录类型、长度、去 query/hash 的 URL、时间和调用栈；高频调用加去重或计数。
5. 明确触发动作，验证一次命中。
6. 提供恢复方式；需要落地日志时写入执行工程的 `js_reverse_cache/`。

先声明 intake mode：

- `artifact-only`，或用户未要求检查当前页面 → 直接交付 Console/Snippets 脚本，并标记**现场命中未验证**；
- 需要与当前目标发生新交互 → 改为 `live-target`，执行 `../../SKILL.md` 规定的串行双工具取证顺序。

只有用户要求直接注入时才修改页面；其他 `live-target` 场景在完成证据采集后交付脚本，不擅自注入。

## 数据与请求绑定

观察请求字段时，尽量输出：

- `target`：fetch / xhr / websocket / form / beacon
- `event`：open / send / setRequestHeader / response / message
- method、URL、命中的字段名
- 类型和长度；URL 去掉 query/hash
- 可选 `console.trace()` 或一次性 `debugger`

⚠️ `document.cookie` Hook **只能证明 JS 写入**；HTTP `Set-Cookie` 必须结合响应头判断，两者不能混为同一来源。

## 安全与降噪

1. Cookie、Authorization、token、storage value、body 和响应内容**默认只记录类型/长度**，不输出片段。
2. ArrayBuffer、Blob、canvas data URL 和 WebSocket 消息只打印类型和长度。
3. 页面存在完整性检测、native 检测或 JSVMP 环境探测时，**先说明 JS Hook 可能改变行为**。
4. Hook 后请求消失、签名降级或页面异常时，**立即恢复并缩小 Hook 点**，不要继续叠加 Proxy。
5. 不提供持久 `FULL_LOG` 开关；用户明确需要现场值时，用一次性 `debugger` 暂停检查，**不把值写入 Console 或公开案例**。

## Failure Modes

| 触发条件 | 处理动作 | 兜底 |
|---|---|---|
| 属性不可配置 | Hook 外围调用点或原型方法 | 不强行覆盖 descriptor |
| 页面行为改变 | 恢复原对象并缩小范围 | 改用条件断点、initiator 或引擎 trace |
| 日志刷屏 | 加 URL、字段、次数和长度过滤 | 默认关闭完整值 |
| 用户转而要函数位置或调用链 | 停止扩写 Hook | 按上方「转交」表处理；专用技能不可用时返回 Spider core loop |
| 用户转而要本地执行 | 固定样本和入口线索 | 已知 Node/VM 入口转 `../env-patch/index.md`；明确 iv8 时按上表处理 |

## 资源路由

按目标只读一个分类，必要时再补第二个。`references/` 只解释 Hook 点和扩展约束；**可执行片段必须从 `scripts/` 的受测实现生成**，不能从 reference 文档恢复旧的全值日志：

| 文件 | 覆盖范围 |
|---|---|
| `references/network.md` | XHR、fetch、WebSocket、postMessage、页面上下文注入 |
| `references/storage.md` | cookie、localStorage、sessionStorage、表单值 |
| `references/crypto.md` | WebCrypto、CryptoJS、随机数、编码 |
| `references/dom.md` | DOM 注入、MutationObserver、canvas |
| `references/runtime.md` | JSON、eval、Function、Blob、URL.createObjectURL、Worker |
| `references/snippets.md` | 片段索引与选择建议 |
| `references/hook-output-samples.md` | 输出契约与降噪样本 |

上游预置脚本（本包内**未落地**）：

- `scripts/xhr_fetch.js`
- `scripts/cookie_header.js`
- `scripts/crypto_api.js`
- `scripts/storage.js`

修改或迁移 profile 后运行（**本包无 `tests/`，跑不了**）：

```bash
npm test --prefix "$HOOK_PROFILE"
```

## 判据（做到哪算完成）

本 profile 的完成标准 —— 用户能**直接执行脚本**、**触发一次有效日志**、**恢复页面状态**，并知道**何时该升级**到调用链定位或本地复现。

具体可勾选：

- [ ] 脚本零外部依赖，贴进 Console 即运行；或已说明它依赖哪个未落地的 `scripts/` 文件并给出获取方式
- [ ] 有明确的注入位置与时机说明
- [ ] 有明确的一次触发动作，并且**实际验证过至少一次命中**
- [ ] 有恢复函数 `restore()` 或等效的刷新恢复说明，且验证过恢复后页面正常
- [ ] 日志只含类型/长度/去 query 的 URL，**没有真实 secret 值**
- [ ] 贴出 `window.__spiderHooks.<name>.restore()` 的用法
- [ ] 若目标其实是函数定位 / 本地复现，已按「触发边界」表转交或明确说明了为何留在本 profile
- [ ] 已声明 intake mode；若是 `artifact-only`，已标注"现场命中未验证"

**不算完成**：只贴一大段脚本没有说明；声称"应该能命中"但没验证过；为了看真实值打开了全量日志。

## 相关

- `../../SKILL.md` — 主入口与 Auto Judge Card
- `../static-ast/index.md` — 兄弟 profile：静态还原（需先 `npm i` 解析器）
- `../env-patch/index.md` — 兄弟 profile：把观察到的入口搬到 Node/VM 本地跑
- `../../../js-reverse/SKILL.md` — 需要 initiator / 调用链定位时的转交目标
- `../../references/observe/hook-techniques.md` — Hook 技法总览
- `../../references/observe/anti-debug-playbook.md` — 目标有反调试时的应对