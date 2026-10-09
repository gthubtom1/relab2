# 静态 AST Profile（Static AST Profile）

> **来源**：改编自 `aoyunyang/spider-king-skill`（MIT License）的 `index.md`。原文英文，本篇中文改写。
> **用途**：当一份现成的 JavaScript 资源文件本身已经是证据产物、下一步目标是让其中的签名器（signer）、序列化器（serializer）或解码器（decoder）边界变得可读时，走这条 profile。
> **前置（本机实测，2026-10-10）**：
> - Node ✅ `D:\Tools\Node\node.exe` v24.20.0（npm 11.19.0 随附）
> - **npm 解析器包 ❌ 本机未安装**：`esprima` / `acorn` / `@babel/parser` / `@babel/traverse` / `@babel/generator` / `acorn-walk` 用 `require.resolve()` 逐个验证，全部 MISSING。要用本文流程，**必须先 `npm i`**（建议装到任务目录，不要装进 skill 树）。
> - **profile 自带脚本 ❌ 未落地**：本文提到的 `package.json`、`package-lock.json`、`scripts/run-pipeline.js`、`tests/` **都不在本包里**。要用得先从上游 MIT 仓库取，或自行实现等价管线。
> - 本篇的流程、检测家族与改写范围描述的是上游管线的能力边界，**未在本机端到端跑通**。

---

## 安全契约（Safety contract）

- 结构化地解析与改写源码；**绝不执行目标源码**。
- 原始文件与每一个中间文件都保留在任务工程的 `js_reverse_cache/tasks/<task-id>/` 目录里。
- 只用通用、保守的管线。站点专用或家族专用适配器需要独立 fixture（固定样本）才能加入。
- 把 `eval`、`Function`、WebAssembly、宿主对象读取、不透明 decoder 调用视为"观测点"，它们需要 `env-patch` 或另一条本地运行时路线。
- `node:vm` 不是隔离边界。本 profile 不用它。
- 报告只包含文件名基名、哈希、计数和有界的错误元数据，**不含源码文本、token、cookie 或环境值**。
- 输入路径不得与下文列出的任何生成文件名冲突。非法 UTF-8 在解析前就中止；`00_source.js` 与 `final.js` 保留输入的逐字节原样。

## 准入条件（Entry conditions）

只做结构检测与保守还原时，**给定输入文件 + 一个有界的检查目标**就够了。

但在下列动作之前，必须先拿到固定请求或运行时样本：

- 声称算法等价
- 评估还原后的边界
- 执行目标代码
- 升级到动态路线

如果用户目标需要入口/调用链，但它仍然未知 —— 回到 Spider core loop（`../../SKILL.md` 的「工作流」），不要一上来就做大范围脱混淆。

## 用法（Usage）

Babel 依赖图在上游 `package-lock.json` 里锁定。**绝不要在 skill 目录里安装依赖。** 在依赖安装与任务缓存路径获得批准后：

1. 在 `allowedPaths` 内创建 `<project>/js_reverse_cache/tasks/<task-id>/tools/static-ast/`。
2. 把本 profile 的 `package.json`、`package-lock.json`、`scripts/`、`tests/` 复制进那个任务本地工具目录，**不要复制 `node_modules`**。
3. 记录复制过来的 package-lock 与脚本哈希，然后从任务本地副本运行：

```text
npm ci --ignore-scripts
npm test
```

> ⚠️ **本包实情**：上游的 `package.json` / `package-lock.json` / `scripts/` / `tests/` 未随包落地。你需要先从上游仓库取这些文件，或者自己定义一套等价的 Babel 管线并锁版本。`npm ci` 依赖 lock 文件；没有 lock 文件就用 `npm i @babel/parser @babel/traverse @babel/generator` 自己锁定，但要在报告里注明"锁文件由本机自建，非上游版本"。

不要在 skill 目录里跑 `npm ci`。任务本地的 `node_modules` 保持 gitignore，排除在证据包与稳定交付之外；除非已批准的任务缓存保留策略要求留下，否则清理时删掉。

然后运行管线：

```text
node <task-local-static-ast>/scripts/run-pipeline.js <input.js> <task-output-dir> [hint]
```

管线输出：

- `00_source.js` — 逐字节的源码副本
- `01_safe_rewrite.js` — 保守改写结果
- `detection.json` — 结构家族与原始源码中的证据计数
- `metrics.json` — 最后一个良好产物的残留指标
- `pipeline-report.json` — 状态、哈希、各步耗时、最后一个良好文件
- `final.js` — 最后一个可解析的产物，即使后面某步失败

**这个 profile 是可读性辅助，不是算法证明。** 在把还原出的边界交给"能力快照里已确认安装的签名器专用技能"之前，必须先用固定向量与 wire 证据证明它；否则走 Spider 的纯 Python 路线（`../../references/deliver/pure-python-rebuild-playbook.md`）。

## 支持的静态观测（Supported static observations）

- 字符串数组（string-array）与 decoder 形态结构
- dispatcher（分发器）形态对象
- loop/switch 控制流平坦化（control-flow flattening）
- opcode 风格字面量比较
- 计算成员访问（computed member access）
- `_0x` 风格标识符
- 动态执行与 WebAssembly 标记

检测是结构性的，**有意不选择站点专用适配器**。有歧义的证据一律停在 `generic-static-safe`。

## 改写范围（Rewrite scope）

第一遍改写只做两件事：

1. 把带合法字符串标识符的计算成员访问（`obj['run']`）转成普通成员访问（`obj.run`）
2. 移除测试条件已经是布尔字面量的 `if`，同时保留被选中的语句块；**含 `var` 或函数声明的分支要保留**，以维持提升（hoisting）语义

不求值任何调用。不折叠别名、字符串表、控制流状态机、getter、proxy 或依赖宿主的表达式。新增改写规则时，必须有一个同时证明正向行为与负向边界的 fixture。

## 升级路径（Upgrade path）

如果报告标记了 `dynamic_execution`、`wasm` 或依赖宿主的代码，**停止静态路线**，交给：

- `../env-patch/index.md`（本地 Node/VM 补环境）
- `../../references/crypto/offline-inline-deob-playbook.md`（离线内联脱混淆）
- 或某个专用运行时技能（见 `../../SKILL.md` 的「不走本 skill」）

最终采集器仍然是 Python 拥有。

## 相关

- `../../SKILL.md` — 主入口与 Auto Judge Card
- `../env-patch/index.md` — 动态执行路线的接手方
- `../browser-hook-snippets/index.md` — 兄弟 profile：需要在运行时观察而非静态还原时
- `../../references/crypto/obfuscation-guide.md` — 字符串表/混淆器识别
- `../../references/crypto/offline-inline-deob-playbook.md` — 两遍改写恢复 decoder
- `../../../js-reverse/SKILL.md` — 上游技能：需要运行时定位调用链时（本篇纯静态，不涉及浏览器）