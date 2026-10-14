# 工作流总览（Workflow Overview）

> **来源**：改编自 `aoyunyang/spider-king-skill`（MIT License）的 `workflow-overview.md`。原文为英文，本篇为中文改写，**Startup Gate 与 Phase 0–5 的逐条要点全部保留**，未压缩。
> **什么时候用**：**新任务开工的第一篇**。当你要回答「一个新任务按什么顺序走」时，读本篇。它是纯 Web 协议恢复任务的最短端到端地图。

---

## 适用信号

- 你刚接到一个**新任务**，还没决定从哪下手 —— 读本篇定顺序；
- 你已经做了一段时间，但不确定**当前处在哪个阶段**、下一阶段该做什么；
- 你想确认「我这一步算不算越过了阶段边界」；
- 你在决定**要不要开浏览器**、要不要升级运行时；
- 你在 `../../SKILL.md` 读到了「Startup Gate」和「Universal Reverse Loop」的标题，想要一份更短的执行地图；
- 你在准备交付，想确认**交付前必须过的检查点**是否都过了。

## 前置

- 本篇是**流程层**文档，不含任何可执行命令，因此不涉及本机工具版本问题。
- 阶段编号约定：本篇 `Phase 0..5` 与 `../../SKILL.md` 的 Universal Reverse Loop **同编号、同含义**。原文里出现的「五阶段」口语化说法（Observe 观察 → Prove 证明 → Rebuild 重建 → Verify 验证 → Deliver 交付）与本篇 Phase 的对应关系见下文「阶段速查」。
- 三个交付形态标签（`evidence` / `local-proof` / `compact-replay` / `collector`）沿用 `../../SKILL.md` 的 Lightweight Dispatch，本篇不重复定义。
- **本文不涉及**：APK / native app / 小程序的主路径逆向 —— 那不在本技能范围内，不得为这类目标编造 Web 浏览器首轮取证。

## 步骤

### 阶段速查（一句话版）

| 阶段 | 中文名 | 一句话目标 |
|---|---|---|
| Startup Gate | 启动门禁 | 声明 intake 模式、工具能力、最小交付形态，然后才允许动手 |
| Phase 0 | 指纹目标 | 在碰代码之前先给目标分类 |
| Phase 1 | 证明真实请求 | 抓到一条真的返回业务数据的请求 |
| Phase 2 | 隔离变动状态 | 把每一个会变的部分单独拎出来 |
| Phase 3 | 离线重建 | 选最便宜的一条可行路径，一次只升一级 |
| Phase 4 | 验证可重复 | 同一个最小请求至少成功两次 |
| Phase 5 | 交付 | 产出协议采集器 + 一份可审计的交接文档 |

对应口语五阶段：**Observe（观察 = Startup Gate + Phase 0） → Prove（证明 = Phase 1） → Rebuild（重建 = Phase 2 + Phase 3） → Verify（验证 = Phase 4） → Deliver（交付 = Phase 5）**。

---

### Startup Gate（启动门禁）

在进入深度工作**之前**，逐条完成并声明：

- 声明 intake 模式：`live-target` / `artifact-only` / `continuation`；
- 检查本机工具可用性（capability snapshot）；
- 对于 Web `live-target`：记录能力快照，确认两个浏览器工具家族**都在**（但**不要同时**打开目标），然后把初始 `TARGET_ACTIVE` 归属指派给 `chrome-devtools`；
  > ⚠️ **本机状态**：`chrome-devtools` 与 `js-reverse` **均未在本机挂载**。见文首「平台与本机状态」。APK / app / 小程序为主的任务不在本技能范围内，**不得**为它们编造这一对首轮取证。
- 对于 `artifact-only`：直接从给定的文件或抓包开始，并把 **live acceptance（线上接受度）标记为未证明**；
- 对于 `continuation`：复用当前门禁，**只重新打开被新输入证伪的那些证据面**，不要全量重做；
- 把目标归类为：`signer-gated`（签名门禁）/ `verifier-gated`（校验器门禁）/ `decode-gated`（解码门禁）/ `session-gated`（会话门禁）；
- 说明**最小的可接受的无浏览器交付形态**是什么；
- 区分「现在就是 browser-free（无浏览器）」与「目标是 runtime-free（无运行时）」 —— 当你正在考虑内嵌宿主时，这两件事不是一回事；
- 如果**下一步动作会扩大运行时、patch 面积或传输 profile**，**先读** `../triage/escalation-ladder-playbook.md`；
- 在实现一个**含糊的、或者会扩大外联面的** `compact-replay` / `collector` 之前，记录 `../contract/provider-work-order.md` 里的条件式实施纲要（conditional implementation brief）；但**不要**把这套纲要强加给有界的 `evidence`、`local-proof`，或明确声明不写盘的分析任务。

### 浏览器交接检查点（Browser handoff checkpoints）

> ⚠️ **本机状态**：本节依赖 `chrome-devtools` / `js-reverse` 两个 MCP 家族，**本机未挂载**，因此该序列**在本机不可执行、未在本机验证**。保留本节是因为它定义了**角色所有权**的语义；当本机或后续环境确实挂载了浏览器 MCP 时，语义可直接沿用。

- **先**抓 Chrome 的干净基线（clean baseline）；
- 在启用 `js-reverse` **之前**，保存基线证据，并套用 `../triage/tool-playbook.md` 里的交接门禁（handoff gate）；
- 把上一个家族标记为 `PARKED`；当清理动作会**摧毁唯一一份不可重放的会话或 verifier 状态**时，改用 `RETAINED_EXCEPTION`；
- 回到 Chrome 时，**先 park `js-reverse`**，并显式地重新获取或恢复 Chrome 的证据状态；
- 只有在已安装的工具**确认进程终止**之后，才使用 `CLOSED`。

### Phase 0：给目标做指纹（Fingerprint the target）

在碰任何代码之前，先给目标分类：

- 诱饵端点（decoy endpoint）还是真实端点；
- wrapper 重写还是可见参数；
- 被 patch 过的 helper 还是标准 helper；
- `signer-gated` / `verifier-gated` / `decode-gated` / `session-gated`；
- 会话绑定还是匿名可达；
- bootstrap 资产还是直连数据 API；
- 单页特例还是整条流程的特例；
- 「先抓干净基线」/「先追 trace」/「先解码」/「先冻结记录」；
- JSVMP / 重度混淆，还是普通的打包 bundle。

**为什么这一步不能跳**：分类决定了后面所有阶段的默认路径。跳过它，你会在一个诱饵端点上花掉整个 Phase 1。

### Phase 1：证明真实请求（Prove the real request）

- 抓到那个**真的返回有用数据**的请求；
- 记录它的 initiator（发起栈/来源）；
- 记录确切的 query、body、headers、cookies 和响应形状；
- 把新抓的样本存进**任务本地缓存**，与稳定 helper 代码、用户维护的 fixture **分开**。

### Phase 2：隔离变动状态（Isolate the moving state）

把每一个会动的部分**当成独立的东西**对待：

- 时间戳
- 随机片段
- 轮换的 cookie
- 响应侧的 refresh 元组或 challenge subcode 载荷
- 传输层 wrapper 字段
- 页面专属请求头
- 会话契约
- bootstrap 输出
- cookie 来源（provenance）

**为什么必须隔离**：它们每一个都需要各自的证据。合并处理会导致「A 好了但 B 没验证」。

### Phase 3：离线重建（Rebuild offline）

选**最便宜的一条可行路径**，按这个顺序试：

1. 纯 Python
2. Python + 一个极小的 JS helper
3. Python + 一个极小的 WASM helper
4. Python + 一个本地 bootstrap executor（本地引导执行器）

对于 `verifier-gated` 或「挑战 bootstrap 型」目标：

- 在**一条会话链上一次新鲜的、单页的 live replay 成功**之前，**不要**去扩大宿主 patch 或做「去运行时化」的工作；
- 当同一条业务路由**先返回机器挑战、本地刷新之后成功**时，把这个 `fail → refresh → success` 的循环**留在同一条会话链上**并证明它，**然后**再去找替代端点；
- **一次只升一级**，并在升级前**记录为什么更轻的那一级失败了**；
- 下一步动作有争议时，用 `../triage/escalation-ladder-playbook.md`。

当抓到的目标代码、HTML 或运行时 blob 是**易失的**时，从新鲜缓存**生成临时的本地 runner**，**默认不要**去覆盖稳定脚手架（stable scaffolding）。

### Phase 4：验证可重复性（Verify repeatability）

- helper 输出与固定测试向量一致；
- **本地 helper 能加载成功、异常变少、或者产物形状更像浏览器 —— 这些都不算成功**，除非真实请求能**反复**重放；
- `verifier-gated` 目标在你**移除大范围 hook 之后仍然工作**；
- 第 1 页**至少重放两次**；
- 在做分页规模化或「瘦身运行时」之前，**单页 live replay 已经证明**；
- 分页或游标能工作；
- 已知的例外被**窄范围**地编码；
- 「bootstrap 密集型」目标保持**一条会话链完整**，除非跨会话复用被明确证明过。

### Phase 5：交付（Deliver）

交付物清单：

- 纯协议的 collector；
- 一份来自 `../contract/report-templates.md` 的**紧凑协议交接文档**，作为**唯一的**复跑与审计摘要 —— **不要**把同样的事实复制到多份项目文档里；
- 保存下来的样本；
- 脱敏报告；若有原始凭据 / token / cookie 值必须保留，配一个**仅本地**的密钥库；
- `analysis/proof_manifest.json`，包含：能力快照、产物哈希、会话作用域、helper 版本、固定向量、live replay 次数；
- 关于 headers、cookies 和不稳定点的清晰说明；
- 当这个家族**很可能复发**时，保留 **5 到 15 条最小可验证事实**；
- 用 `../triage/minimal-verifiable-facts-playbook.md` 让这些事实保持**结构性且可复检**。

## 判据

「做到哪一步算完成」——本篇是流程文档，所以判据按阶段给，每一条都必须是**外部可观测**的。

### 分阶段判据

| 阶段 | 通过判据（可外部观测） |
|---|---|
| Startup Gate | intake 模式已声明；能力快照已落盘；`TARGET_ACTIVE` 归属唯一；门禁家族已归类；最小交付形态已写明 |
| Phase 0 | 上面 10 条分类**每一条都有明确答案**（不是「看起来是」），且有一条书面判断记录 |
| Phase 1 | 存在**一条**落在真实业务路径上的请求，含 initiator、完整 query/body/headers/Cookie 头、响应形状；新样本进了任务本地缓存 |
| Phase 2 | 变动状态清单**逐项**标注：静态 / 服务端下发 / 本地计算 / 未定；cookie 有明确 provenance |
| Phase 3 | 本地路径能跑通真实请求；**若发生升级**，升级日志写清了「上一级还好的部分 / 确切盲点 / 为什么下一级是最小一级」 |
| Phase 4 | 同一条最小请求**连续成功 ≥2 次**（新会话或新时间戳）；下一页 / 游标用**同一套 collector 逻辑**通过；已知例外已窄范围编码 |
| Phase 5 | 浏览器 MCP 与页面驱动**全部退出**运行路径；`main.py` 或 `collector/main.py` 可直接右键运行且**不带必填命令行参数**；`analysis/proof_manifest.json` 存在；敏感值已从报告与版本库脱敏 |

### 整体完成的判据（Phase 5 的硬门槛）

满足**全部**以下才算交付完成：

1. **无浏览器运行**：断掉浏览器 MCP、删掉浏览器 profile 之后，`main.py` 仍然成功；
2. **无占位符成功**：token 长度「看起来对」、helper 「能加载」、HTTP 200、cookie jar 非空 —— 这些单独存在时**都不构成接受**；
3. **会话链完整**：bootstrap 密集型流程在一条会话链上完成，除非已证明可跨会话；
4. **事实不重复**：`../contract/report-templates.md` 的紧凑交接文档是唯一事实源，没有第二份重复叙述；
5. **能力声明诚实**：没有在浏览器 MCP 时，报告里写的是「未证明」，不是「已理解」。

## 常见坑

按最常见程度排序：

1. **跳过 Startup Gate 直接开浏览器**。原文把它放在最前面是有原因的 —— 不知道 intake 模式就取证，很容易给一个 `artifact-only` 的任务编造出一堆「浏览器首轮取证」结论（对应 `anti-patterns-playbook.md` 第 25 条）。
2. **把 Phase 3 的四级路径当成「优先选最快的」**。原文的排序是**成本排序**：纯 Python → 小 JS → 小 WASM → 本地 bootstrap executor。跳到第 4 级是最常见的浪费（对应第 4、29 条）。
3. **Phase 4 的「helper 能加载」陷阱**。原文专门用一行强调「异常变少 / 形状更像浏览器不算成功」，因为这是最容易被自己骗过去的信号（对应第 7 条）。
4. **Phase 3 的 `fail → refresh → success` 循环被提前放弃**。很多人在第一次拿到机器挑战时就去找替代端点，结果丢掉了唯一正确的路径 —— 正确做法是**留在同一条会话链上**证明这个循环。
5. **Phase 5 的报告冗余**。原文写「不要把同样的事实复制到额外的项目文档里」，因为多份文档必然互相矛盾，且审计时无法确定哪份权威。
6. **用易失抓包覆盖稳定脚手架**（Phase 3 最后一句）。后果是下一次 diff 不可读、升级分析失去干净基线（对应第 8 条）。
7. **Phase 0 的分类给了「大概」**。分类的目的是**排除路线**，不是描述目标；每一项都必须是能排除某条路的明确判断。
8. **`continuation` 模式做全量重做**。原文明确说「只重新打开被新输入证伪的那些证据面」—— 全量重做在实践中通常意味着重犯上次犯的错。
9. **误用本机的能力前提**：本机没有 `chrome-devtools` / `js-reverse` / `Reqable`（见文首）。照抄原文命令会得到「工具不存在」，那**不是**目标环境的问题，是本机能力缺口 —— 应报告缺口，而不是把它当成「这个站只能浏览器跑」的证据。
10. **把 Phase 1 抓到的第一条请求当成真实请求**。诱饵端点、兼容页、包装页都会返回 200；Phase 0 分类就是为了过滤它们。

## 相关

- `../../SKILL.md` —— 权威版：Non-Negotiables、Auto Judge Card、Universal Reverse Loop、Verification and Reporting。本篇是它的**短版执行地图**，冲突时以 `../../SKILL.md` 为准。
- `doctrine-index.md` —— 规则底座（本篇的每个阶段背后都有对应教条）。
- `anti-patterns-playbook.md` —— 本篇「常见坑」第 3、4、6、1 条的完整反模式条目。

### 本篇引用到的手册（已改为本包实际路径）

| 原文引用 | 本包实际路径 |
|---|---|
| `../triage/escalation-ladder-playbook.md` | `../triage/escalation-ladder-playbook.md` |
| `../triage/tool-playbook.md` | `../triage/tool-playbook.md` |
| `../contract/provider-work-order.md` | `../contract/provider-work-order.md` |
| `../contract/report-templates.md` | `../contract/report-templates.md` |
| `../triage/minimal-verifiable-facts-playbook.md` | `../triage/minimal-verifiable-facts-playbook.md` |

### 其他常用手册

- `../triage/startup-triage-playbook.md` —— Startup Gate 的展开清单
- `../observe/mcp-routing-playbook.md` —— 信号驱动的工具/宿主选择表
- `../deliver/delivery-gate-playbook.md` —— 各交付形态的验收门禁
- `../deliver/pure-python-rebuild-playbook.md` —— Phase 3 各级路径的具体做法
- `../deliver/response-decode-playbook.md` —— 响应侧解码
- `../state/async-export-job-playbook.md` —— Phase 5 中异步导出任务的验收
- `../contract/project-artifact-contract.md` —— 落盘产物与 `analysis/proof_manifest.json` 的契约
- `../observe/local-mcp-environment.md` —— 本地 MCP attach 端口 / debug profile 排障