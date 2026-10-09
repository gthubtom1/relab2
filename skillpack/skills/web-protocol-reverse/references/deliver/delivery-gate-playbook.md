# 交付门手册（Delivery Gate Playbook）

> **来源声明**：本文改编自外部仓库 `aoyunyang/spider-king-skill`（MIT License）的 `delivery-gate-playbook.md`。原始内容为英文原文，此处译为中文并按本包六段式规范重排；技术术语保留英文原词并附中文。改编中修正了源文档的表述并删除了失效的脚本引用（见文末「源文档勘误」）。
>
> **什么时候用**：要**验收**一个已声明形态（declared shape）的结果时。重点是：**不要把一个更小的结果悄悄当成 collector，也不要把半个 collector 当成完整的**。
>
> **平台与本机状态**：本文是**纯验收规程**，不含必须在本机执行的命令，因此不涉及工具可用性问题。文中提到的 MCP 浏览器家族 `chrome-devtools` / `js-reverse` **在本机 agent 工具注册表中未挂载**（本机挂载的是逆向侧的 `pyghidra-mcp` / `idapro` / `ida-pro-mcp` / `angr-mcp` / `x64dbg-automate-mcp`），交付门本身不依赖它们。源文档引用的 `scripts/` 目录在本包中**不存在**，相关引用已在改编中移除。

---

## 适用信号（Recognition signals）

- 你准备宣告「做完了」，需要先确认这个结果**到底属于哪一档**
- 一个「能跑」的脚本只 replay 过一次，或者只在浏览器里跑
- 有人（包括你自己）把 `evidence` / `local-proof` 形态的结果描述成了「采集器」
- 交付里混着快照驱动的（snapshot-driven）产物，但描述成了「纯算法生成」
- 有人在最终路径里留了浏览器 profile、页面 `fetch`、手动 cookie 导出

## 前置（Entry conditions）

1. **必须先声明形态**，再开始验收。声明之后**只跑一个主 gate**：
   - `evidence`（证据）
   - `local-proof`（本地证明）
   - `compact-replay`（紧凑重放）
   - `collector`（采集器）
2. **必须先声明 intake mode（接入模式）**：`live-target` / `artifact-only` / `continuation`。三者对「线上接受性」的要求完全不同。
3. **会话、工具、预算边界已经记录**（见 `../contract/provider-work-order.md`）。未记录的部分按「blocked / offline」处理。

## 步骤（Working method）

### 核心规则

**如果一个可运行的 replay 或 collector 仍然依赖实时页面上下文，它就没做完。**

`evidence` 可以描述浏览器观察，但**不得**把这些观察说成「无浏览器重放」。显式配置输入可以接受，实时页面读取不可以。

浏览器形状的值（UA、platform、viewport、screen metrics）如果只作为 signer 的**输入**存在，它们可以作为**声明过的配置**留在最终 collector 里。**但这不构成让浏览器、内嵌运行时或页面上下文调用为了每次重读它们而继续活着的理由。**

### 可接受的可运行交付形态

- 纯 Python HTTP collector
- Python + 隔离的本地 JS helper
- Python + 本地 WASM helper
- Python + 本地 bootstrap executor（引导执行器）
- Python + 本地 decoder（字体、protobuf、msgpack、压缩载荷）

### 生成真实性标签（Generation truth labels）

不透明的 signer 交付或 profile 支撑的交付，必须打上以下标签之一：

| 标签 | 含义 | 执行期是否无浏览器 |
|---|---|---|
| `algorithmic`（算法生成） | 决定性变换与新输入全部本地重新生成，不依赖捕获的最终产物、也不依赖捕获的运行时 profile | 是 |
| `snapshot-driven`（快照驱动） | 变换本地跑，但仍有一份完整捕获的运行时 profile 在提供不透明或环境输入 | 是 |
| `pool-backed`（池支撑） | 从一个池里挑选此前已被接受的最终产物 | 是 |

**三者执行期都可以无浏览器，但它们不等价。** `snapshot-driven` 必须声明**捕获新鲜度（capture freshness）与作用域（scope）**。`pool-backed` 重放是**诊断手段**，或被明确接受的**有界兜底**，**绝不是签发或生成能力已被拿回的证明**。

### 不可接受的交付形态

- 拿浏览器自动化当 collector
- 拿 CDP 或页面上下文的 `fetch` 当稳态路径
- 把手动导出 cookie 当作运行前提
- 「只在我这个浏览器 profile 下能用」的交付
- 用隐藏的验证点击冒充协议重放
- import 那些「运行时支撑的前序模块」—— 它们的 import 副作用仍在打全局补丁、读 cookie 或依赖浏览器/宿主状态
- 为了给已经理解成显式输入的字段「补货」而去做实时浏览器/宿主运行时读取
- **把 `snapshot-driven` 生成或预校验的产物池重放称作完全算法化（fully algorithmic）**

### 通用门（Common gate）

所有形态都必须通过：

- 已声明形态与 intake mode
- 每条结论都被具名证据或精确阻塞项约束
- 未观察到的线上行为、端点时效性、账号作用域、运行时来源，都明确标记为**未证明**
- 报告与落盘产物中**不含**原始凭据、token、会话密钥、cookie 值、个人数据，或无密钥的低熵秘密指纹
- 没有任何任务产物写在批准的项目路径之外，或写进本技能包目录
- 运行时归属、清理状态、残余风险都如实

### `evidence` 门

用于请求样本、initiator（发起方）、状态写入方、变更点、结构性观察，或一个明确的阻塞项：

- 保留结论所需的 provenance（来源链）、顺序、方法、路由形状、字段名、类型、长度，以及带密钥的指纹
- 区分 **wire / 源码 / 浏览器 / 环境 / 下游接受** 五类证据
- 当授权结果就是「不落盘的对话式证据」时，**不要求**线上 replay、Python 入口、依赖安装或持久化 manifest
- 需要落盘证据包时，放在已批准的任务项目下，并记录一份**无秘密**的 proof manifest
- **不得**在没有通过更高一档 gate 的情况下把 `evidence` 升格为 `local-proof` / `compact-replay` / `collector`

### `local-proof` 门

用于固定向量、解码样本、还原源码，或一个可调用的离线 helper：

- 记录精确的**非秘密**输入、输出或检查点，以及**一个负面边界**
- 除非单独获得了线上外联授权，否则保持离线
- 显式标注运行时与依赖要求
- 除非用户要求可执行打包，否则**不要求**线上端点、重复请求或右键入口
- 明确声明：**当前线上接受性与会话兼容性未证明**

### `compact-replay` 与 `collector` 门

以下检查对两种可运行形态都适用；其中分页、断点续跑、去重、持久化、扩容检查**只在承诺为 `collector` 时适用**：

1. 真实端点已确认
2. 移动部件（moving parts）已显式命名
3. signer 或 decoder 有固定样本证明
4. 请求**重复**成功（不是一次侥幸）
5. 适用时，decode / parser 路径是本地的
6. 必需的会话状态是显式的
7. 最终运行路径**无浏览器依赖**
8. 只是被当作**值**消费的类宿主 signer 输入，是**显式配置**
9. 确定性证明模式与线上生成模式**分离**（当随机、时间戳抖动或填充噪声有影响时）
10. 不透明的阶段性移植能指出**第一个分歧阶段**，并保留完整 profile provenance
11. 涉及捕获 profile 或产物时，交付被标注为 `algorithmic` / `snapshot-driven` / `pool-backed`
12. `pool-backed` 路径有明确的**耗尽策略**和一次**无池测试（no-pool test）**
13. 最终 helper 代码**自包含**，无运行时支撑的 import 副作用
14. `analysis/proof_manifest.json` 记录：intake mode、能力快照、带密钥的产物指纹、会话作用域、helper 版本、固定向量、重放次数，以及任何运行时 profile 依赖 —— **且不复制任何秘密**
15. 异步导出 / 报告类任务证明了 create 的任务隔离，保持「首次创建边界」的诚实，并在落盘前强制校验产物格式与**精确的请求字段完整性**
16. 存在 IDE 右键可运行的入口（`main.py` 或 `collector/main.py`），默认配置**不需要 CLI 参数**
17. 调查期缓存留在 `js_reverse_cache/`，交付证明留在项目根的 `analysis/`
18. 验证器（verifier）、预热、遥测或类采集器 sidecar，在**下游业务路由接受并返回可解析的目标数据或请求的产物之前，都不算最终成功**
19. 任何残余的出口（exit）/IP/代理/传输信誉依赖，都被显式标注为 `egress-gated` 或路由本地传输风险，**而不是**被描述成「实现不稳定」
20. `collector` 要证明它承诺的**全部**边界：分页、刷新、去重、断点续跑、持久化、输出规则 —— 超出紧凑重放的部分

### 挑战 / 双写入者附加项

当 `compact-replay` 或 `collector` 被挑战或验证器卡住时，额外要求：

- **X1**：识别出 **wire-success**（线上成功）的 token 或参数类；被拒的短类或仅研究用的写入者必须标注为**误导性**
- **X2**：在线上生成能在**新鲜时间戳、新页面或等价可变输入**上工作
- **X3**：若使用本地挑战执行器，它返回的是**可被 Python 重放的产物**，而不是 Playwright / CDP 页面驱动
- **X4**：应用层 signer 门与挑战验证器门**分别列出**，并各自给出必要性证明
- **X5**：当 replay 证据需要时，包含**原始 URL 回显字段**
- **X6**：存在 **sidecar 消融矩阵（ablation matrix）**，显示哪些阶段是必需的
- **X7**：共享 baseline 与稀疏/增量包在**同一轮**做过一致性检查
- **X8**：最终接受同时用**平台验证器语义**和**第一个下游消费方通过**
- **X9**：任何人类或浏览器 oracle 都记录了**正样本卫生等级（positive-sample hygiene grade）**
- **X10**：当拒绝码（reject codes）参与过调试时，存在任务本地的**错误语义图**
- **X11**：若残留一个极小的 JS 或 WASM helper，安装步骤与基线产物文件要**打包且无秘密**

### 升级规则（Escalation rule）

**如果声明形态的 gate 没过，就不要按那个形态打包。** 继续做到通过，或者返回一个**自己独立过了自己 gate 的更低形态**，并显式陈述更高形态的阻塞项。

## 判据（Verification checklist）

**「交付完成」= 以下全部为真：**

1. **形态唯一且已声明**，并且只跑了它对应的那一个 gate。
2. **通用门全过**：结论有证据、秘密已脱敏、产物路径合规、运行时清理状态诚实。
3. **形态专属门全过**：
   - `evidence` → provenance 完整、五类证据区分清楚
   - `local-proof` → 有非秘密输入 + 输出/检查点 + 一个负面边界，且线上接受性声明为未证明
   - `compact-replay` / `collector` → 上文 20 条全部适用项通过
4. **真实性标签已打**，且 `snapshot-driven` 声明了捕获新鲜度与作用域；`pool-backed` 完成了耗尽策略与无池测试。
5. **最终路径无浏览器依赖**（浏览器自动化、页面 `fetch`、浏览器 profile、手动状态一律不得作为运行前提）。
6. **IDE 右键入口存在且无必填 CLI 参数**。
7. **门没过时，交付形态被下调**，并在结论里显式写明更高形态的阻塞项 —— 而不是把它悄悄留在原形态上。

## 常见坑（Common traps）

- 把「helper 能加载」「形状对」「HTTP 200」当作验收证据
- 把 `local-proof` 说成「采集器跑通了」
- 把一次成功 replay 写成「重复成功」
- 把 `snapshot-driven` / `pool-backed` 包装成「纯算法生成」
- 把「浏览器形状的值作为配置输入」误解成「所以浏览器可以留在运行路径里」
- 在最终交付里 import 那些 import 副作用仍在打补丁的前序模块
- 挑战验证器通过了就宣告成功，而下游业务路由还没验
- 把 `egress-gated`（出口信誉受限）当成代码不稳定去改算法
- **源文档副作用（改编后已移除）**：它引用了 `scripts/` 下多个脚本用于 profile diff 与证据规范化 —— 这些脚本在落地包中不存在，照抄会直接报错

## 相关（Related）

- `./pure-python-rebuild-playbook.md` —— 「纯 Python 重建」形态的**加严八条**判据，与本文 gate 同时生效
- `./response-decode-playbook.md` —— 第 5 条「decode 路径本地化」的对应手册
- `./case-reuse-playbook.md` —— 复用类（`template` / `fixture-proof` / `current-proof` / `helper-only`）与本文真实性标签的对应
- `../contract/provider-work-order.md` —— 形态声明、权限、预算的来源
- `../contract/project-artifact-contract.md` —— 第 14/16/17 条的目录与 manifest 契约
- `../contract/report-templates.md` —— 通过 gate 后该写什么
- `../principles/doctrine-index.md` —— 教条 7（交付门高于便利）
- `../observe/transport-pre-gate-playbook.md` —— 第 19 条 `egress-gated` 标签的判定依据
- `../triage/escalation-ladder-playbook.md` —— 门没过时「一级一级升」而非一步跳到浏览器
- `../../../case-review/SKILL.md` —— 需要把整个 case 包交付复核时的本包审查流程

---

## 源文档勘误（改编时修正）

1. **源文档把「Acceptable runnable delivery shapes」列为五个可接受形态（含 Python + 本地 JS helper），同时在其他地方要求「最终不依赖浏览器」。** 字面无冲突，但两处分散，容易让读者以为本地 JS helper 是终点。本文在步骤段开头明确加了一段「本地 helper ≠ 浏览器依赖」的显式说明，与 `./pure-python-rebuild-playbook.md` 的判据第 7 条建立分层关系。
2. **源文档引用了 `scripts/evidence_normalizer.py`、`scripts/forward_test_report.py` 等脚本路径。** 本包 `web-protocol-reverse/` 下**不存在 `scripts/` 目录**，全仓库也搜不到这些文件。改编时在 `../triage/reproducible-evidence-playbook.md` 等处沿用其**做法描述**，但在本文移除不可执行的路径引用，避免读者照抄即错。
3. **源文档的 `Compact replay and collector gate` 第 14 条与 `../contract/project-artifact-contract.md` 里的 manifest schema（camelCase 版本）字段名不完全一致** —— 一处写 `capability` / `artifactFingerprints` / `fixedVectorProof`，一处写 `intake_mode` / `artifact_hashes` / `fixed_vectors`（snake_case）。源文档同时给了两套。改编保留两者的**实质字段要求**，但在相关段指向 `../contract/project-artifact-contract.md` 作为**唯一 schema 权威**，避免同一项目里出现两种 manifest 字段命名。
4. **源文档没有区分「没跑到」和「跑挂了」。** 改编在判据里明确：授权缺失的检查项记为 `not-requested` / `blocked`，**不得**默认成通过，也不得默认成失败。
