# Node/VM 环境补丁 Profile（Environment Patch Profile）

> **来源**：改编自 `aoyunyang/spider-king-skill`（MIT License）的 `index.md`。原文主体已中文化，本次改编补齐来源声明、本机化标注与交叉引用校正。
> **用途**：接收**已确认的 JS 入口**和**浏览器样本**，完成 `Rebuild → Patch → Consolidate`（重建 → 打补丁 → 固化）。
> **前置（本机实测，2026-10-10）**：
> - Node ✅ `(Resolve-ReverseToolSpec -Name 'node').Command` v24.20.0
> - **profile 自带脚本 ❌ 未落地**：本文提到的 `scripts/env-diagnose.js`、`scripts/analyze-gap-log.js`、`scripts/collect-browser-env.js`、`scripts/env_core.js`、`scripts/webpack_runtime.js`、`env/` 模块树与 `tests/` **都不在本包里**。要用得先从上游 MIT 仓库取，或自行实现等价物。
> - **iv8 ❌ 本机无**：社区运行时，PyPI 上不存在；`../../references/crypto/iv8-runtime-cheatsheet.md` 里的 API 形态仅供有该运行时时参考，**未在本机验证**。

---

## 目录

- [唯一职责](#唯一职责)
- [准入条件](#准入条件)
- [工具与目录](#工具与目录)
- [核心循环](#核心循环)
- [浏览器 Seed](#浏览器-seed)
- [高级路径准入](#高级路径准入)
- [Failure Modes](#failure-modes)
- [Reference Router](#reference-router)
- [判据](#判据)

## 唯一职责

接收**已确认的 JS 入口**和**浏览器样本**，完成 `Rebuild → Patch → Consolidate`。

**本 profile 不负责**从未知站点寻找入口；完整协议编排仍由 Spider core loop（`../../SKILL.md` 的「工作流」）拥有。

共享阶段与 handoff（交接）字段由 `../../SKILL.md`、`../../references/principles/workflow-overview.md` 与任务目录 `js_reverse_cache/tasks/<task-id>/` 约定定义。

## 准入条件

开始前必须具备：

1. 本地目标脚本或明确的模块 ID。
2. 入口函数、init/setup 参数或触发方式。
3. 至少一组**真实输入**和**预期输出/格式证据**。

开始分流前先读能力快照，**不得假设外部技能已经安装**：

| 当前缺口 | 首选路由 | 专用能力不可用时 |
|---|---|---|
| 缺少入口或调用链 | 已安装的专用 JS 逆向技能（本包内为 `../../../js-reverse/`） | 返回 Spider core loop，用 `chrome-devtools` / `js-reverse` 的 initiator 证据定位 |
| 只需观察 Hook | `../browser-hook-snippets/index.md` | 直接使用本技能内置 profile |
| 整文件 AST 还原 | `../static-ast/index.md`（**需先 `npm i` 解析器，本机未装**） | 用 `../../references/crypto/offline-inline-deob-playbook.md` 与 `../../references/crypto/obfuscation-guide.md` 本地恢复 |
| 明确要 Python + iv8 | 已安装的 iv8 专用技能 | **本机无 iv8**。报告能力缺失；只有用户接受替代后，才改走 env-patch 或最小 local helper 边界 |
| CAPTCHA/TDC 采集、行为数据或 verify | 已安装的匹配 specialist（专用） | 返回 Spider core loop；本 profile 只保留 Node/VM 作为 secondary backend |
| 多层协议或最终采集器 | Spider core loop | 退出本 profile，不在补环境层扩张协议职责 |

> 原文里这三处写的是 `index.md`、`index.md`、`../../references/crypto/offline-inline-deob-playbook.md` 等**上游扁平路径**；本包 `references/` 已按主题拆成 7 个子目录，上表已改为实际落地路径。

瑞数入口 runtime 已确认且目标是 Node.js/VM 补环境时，本 profile 可以继续；**入口尚未定位时执行上表的调用链路由**。

## 工具与目录

先设置 profile 根目录。以下命令用 `$ENV_PROFILE` 表示它：

```bash
ENV_PROFILE="<skill-dir>/profiles/env-patch"
```

```powershell
$ENV_PROFILE = Join-Path $SKILL_DIR "profiles\env-patch"
```

> 原文写的是 `$SKILL_DIR/references/profiles/env-patch`；**本包路径没有中间的 `references/`**。

本 profile 的工具为（⚠️ **全部未随包落地**）：

- `$ENV_PROFILE/scripts/env-diagnose.js` — 默认诊断器
- `$ENV_PROFILE/scripts/analyze-gap-log.js` — 缺口归因
- `$ENV_PROFILE/scripts/collect-browser-env.js` — 浏览器 seed 采集
- `$ENV_PROFILE/scripts/env_core.js` — 高级手写环境引擎
- `$ENV_PROFILE/scripts/webpack_runtime.js` — 最小 webpack runtime
- `$ENV_PROFILE/env/` — 可组合环境模块
- `$ENV_PROFILE/env/webapi/runtime-contracts.js` — opt-in 的 `MessageChannel` 与 webpack chunk 契约

### 安全边界（必读）

`node:vm` **只是兼容执行上下文，不是安全边界**。

未知、混淆或第三方目标脚本必须先放入**无凭据、最小文件挂载、默认断网**的临时 OS/container sandbox。profile 里的确认开关只防误执行，**不提供隔离**。

可用容器时，先把目标和明确需要的 custom patch 复制到一个**不含 `.env`、Cookie、SSH key 或其它项目文件**的专用 staging 目录，并设置 `SANDBOX_INPUT` 指向它。诊断进程至少使用 `--network none`、只读最小 mount、内存/CPU 限制、非 root 用户和空 secrets/env。确认参数**只能**出现在这样的隔离进程内：

```bash
docker run --rm --network none --read-only --memory 512m --cpus 1 \
  --user node -v "$ENV_PROFILE:/profile:ro" -v "$SANDBOX_INPUT:/work:ro" node:22-alpine \
  node /profile/scripts/env-diagnose.js --external-sandbox-confirmed /work/target.js
```

**没有等价外部隔离能力时，不执行未知目标**，停在源码、Hook/trace 和 handoff 证据。

迁移、打包或修改诊断器后先运行（本包无 `tests/`，跑不了）：

```bash
node "$ENV_PROFILE/tests/test-env-diagnose.js"
```

任务补丁、诊断和样本写入项目的 `js_reverse_cache/tasks/<task-id>/env/`，**不写入 skill 目录**，不修改目标原始源码。每个任务使用独立 `<task-id>`，**不得跨任务复用可写 patch、样本或 `run.js`**。

## 核心循环

### 0. 固定入口契约

独立 SDK 先确认 init/setup 参数、URL 匹配规则和触发顺序。

⚠️ **缺失 init 参数可能让 SDK 静默跳过签名** —— 绝不能用"加载成功"代替入口验证。

### 1. 空环境诊断

```bash
node $ENV_PROFILE/scripts/env-diagnose.js --external-sandbox-confirmed <target.js>
```

保存已脱敏的 error 分类、`undefinedPaths`、descriptor/prototype access 和调用异常作为基线。默认 `consoleOutput` **只保留值类型与长度**，不回显目标字符串、对象内容或异常正文。

### 2. 选择最小模块

按 `references/env-modules.md` 做路径前缀匹配，并按 `references/loading-order.md` 排序。**每轮只增加能解释当前 first divergence 的模块。**

### 3. 重新诊断

```bash
node $ENV_PROFILE/scripts/env-diagnose.js \
  --external-sandbox-confirmed \
  --env bom/navigator.js,bom/location.js,dom/document.js \
  <target.js>
```

比较**缺失路径是否减少**、错误是否前移、目标输出是否更接近浏览器样本。

### 4. 处理剩余缺口

优先级**固定**为：

1. 修正模块加载顺序或依赖。
2. 用 `analyze-gap-log.js` 归因到已有模块。
3. 在 `js_reverse_cache/tasks/<task-id>/env/ai-generated/` 写一个**最小** custom patch。
4. **只有真实值参与分支或输出时**，才把 `collect-browser-env.js` 复制到任务目录，在项目副本的 allowlist 中加入**单一字段**并采集一个 baseline；Cookie、storage、query/hash 和 canvas **默认不采集**。
5. 模块树**无法表达** native 外形、webpack 模块或长期 patch plan 时，才启用 `env_core.js`。

Custom patch 使用 IIFE 和 `Object.defineProperty`，保持稳定语义文件名；**不要自动扫描或偷偷加载**任务补丁。

### 5. 循环与退出

**继续条件**：缺失路径减少、first divergence 前移，或错误变化且有明确因果解释。

**停止条件**（满足任一即停）：

- 连续两轮缺失路径和 first divergence **完全相同**。
- 剩余依赖超出 Node/VM 可诚实模拟的宿主能力。
- 入口契约或浏览器样本被证明不完整，需要回到上游取证。

### 6. 功能验证

⚠️ `success: true` **只代表脚本加载**，不代表签名、Cookie 或加密功能可用。

必须在 `js_reverse_cache/tasks/<task-id>/env/run.js` 中按**真实调用顺序**触发入口，并与固定样本比较**长度、段数、编码、前缀、关键中间值和最终输出**。

Hook 型 SDK 的常见顺序是：

```text
env → fake transport → target JS → capture hook → init → trigger
```

### 7. 请求验证与收口

固定输入通过后再封装 `sign.js` 或本地 HTTP 中间层，并沿用同一请求契约验证服务端。

⚠️ **HTTP 200 但业务码、字段或数据为空，仍算失败。**

🔴 **CHECKPOINT**：真实请求前报告 `run.js` 输出、浏览器对照、baseline/session 来源和签名结构；**缺任一项不做可用结论**。

## 浏览器 Seed

只有目标**确实读取真实环境值**时才采集：

1. 一条复现链选择一个 baseline，**不混拼** UA、Cookie、storage、screen、canvas 或 TLS 来源。
2. 记录 URL、时间、session、未采集字段和输出路径。
3. 原始快照**只写任务目录**，不进入公开 case。
4. 被风控阻断且需要反检测基线时，使用能力快照中可用的专用浏览器逆向技能采证；不可用时返回 Spider core loop，执行 `chrome-devtools` / `js-reverse` 取证后再交回。

🔴 **CHECKPOINT**：写入 seed 前声明唯一 baseline、session 关联和目标 patch；**来源冲突时先停**。

## 高级路径准入

只有满足**一项**才启用 `env_core.js` 或 `webpack_runtime.js`：

- 需要 native `toString`、构造器外形或 `Symbol.toStringTag` 契约。
- 模块化环境能加载，但固定输入在**明确位置**分歧。
- 已知 webpack 模块 ID，需要最小 runtime 调用。
- 项目需要长期维护集中式 patch plan。

**高级路径仍不能跳过 fixed fixture 和服务端验证。**

`env_core.js` 会在 host Node realm 中运行代码，**风险高于诊断器**。只允许在上述外部隔离环境中使用，并要求设置 `SPIDER_EXTERNAL_SANDBOX_CONFIRMED=1`；执行完成**必须在 `finally` 调用 `env.restore()`**。

## Failure Modes

| 触发条件 | 处理动作 | 兜底 |
|---|---|---|
| 入口或 init 参数缺失 | 停止补环境 | 转上游补齐调用链证据 |
| parse/load 失败 | 记录**第一条**真实错误 | 不一次加载全部 env 模块 |
| 两轮没有推进 | 回查 first divergence 和加载顺序 | 升级高级路径或报告边界 |
| 浏览器 seed 冲突 | 保留**一个** baseline | 其它样本只作诊断对照 |
| load 成功但输出不一致 | 比较固定输入和关键中间值 | **不封装请求层** |
| 服务端拒绝 | 检查 session、序列化、时间和 transport | 必要时退出 profile，由 Spider core loop 协调协议层 |

## Reference Router

- `references/env-modules.md` — undefined 路径前缀 → 模块映射表
- `references/loading-order.md` — 模块加载顺序与最小加载集
- `references/architecture.md` — 诊断器架构与运行时行为
- `references/module-contracts.md` — 手写补丁模块的统一输入/输出契约
- `references/env-core-advanced.md` — 高级手写环境引擎路径
- `references/browser-stubs.md` — 按诊断报告取用的存根代码
- `references/path-upgrade-checklist.md` — 何时该升级到 vm / 高级 DOM / WASM
- `references/node-detection.md` — Node.js 特征检测与对策
- `references/webpack.md` — webpack 模块提取
- `references/runtime-contracts.md` — MessageChannel / Image / chunk 捕获契约
- `references/verification-and-replay.md` — 功能验证与 HTTP 重放
- `references/limitations.md` — 已知天花板

修改或迁移 profile 后运行（**本包无 `tests/`，跑不了**）：

```bash
npm test --prefix "$ENV_PROFILE"
```

## 判据（做到哪算完成）

完成报告**必须包含**这 6 项（缺一项不算完成）：

- [ ] **入口契约** —— 确认过的 init/setup 参数、URL 匹配规则、触发顺序
- [ ] **加载模块** —— 最终的 `--env` 列表及其排序理由（哪些是本轮新增的、为了解释哪个 first divergence）
- [ ] **first divergence 修复** —— 定位到第一个分歧点并给出因果解释，不是"试了很多模块"
- [ ] **fixture 结果** —— 固定输入下的输出与浏览器样本在**长度 / 段数 / 编码 / 前缀 / 关键中间值 / 最终输出**上的对比
- [ ] **请求验证** —— 真实请求的服务端响应；**只有 HTTP 200 不算**，要看业务码与数据
- [ ] **剩余宿主边界** —— 明确写出哪些浏览器能力仍然无法被 Node/VM 诚实模拟

补充自检：

- [ ] 补丁全部写在任务目录 `js_reverse_cache/tasks/<task-id>/env/`，**skill 目录零写入**
- [ ] 未知目标脚本在**真实隔离环境**里执行，`node:vm` 没有被当成安全边界
- [ ] 敏感值（Cookie、token、storage、canvas）未进入任何日志或公开 case
- [ ] browser seed 只用**一个** baseline，没有混拼来源
- [ ] 若触发停止条件，已明确说出停在哪个条件上，以及下一步该退回 Spider core loop 还是升级路径

**不算完成**：`success: true`；只贴了一串加载成功的日志；HTTP 200 但响应为空/业务码失败；没做 fixture 对比就宣称"补好了"。

## 相关

- `../../SKILL.md` — 主入口与 Auto Judge Card
- `../static-ast/index.md` — 上游路线：静态还原（需先 `npm i`）
- `../browser-hook-snippets/index.md` — 兄弟 profile：运行时观察取证
- `../../references/crypto/environment-patch-playbook.md` — 补环境方法论（包级视角）
- `../../references/crypto/env-diff-playbook.md` — 环境差异与补丁分析
- `../../references/triage/escalation-ladder-playbook.md` — 升级阶梯（何时离开本 profile）
- `../../../js-reverse/SKILL.md` — 需要运行时定位调用链时的上游技能