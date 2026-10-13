# 提供方工单（Provider Work Order）

> **来源声明**：本文改编自外部仓库 `aoyunyang/spider-king-skill`（MIT License）的 `provider-work-order.md`。原始内容为英文原文，此处译为中文并按本包六段式规范重排；技术术语保留英文原词并附中文，AI 检索时中英文均可命中。改编中修正了源文档的若干表述与失效引用（见文末「源文档勘误」）。
>
> **什么时候用**：在把工作交给某条聚焦路线（focused route）之前、下一步动作被门禁（gate）挡住时，先落一份这份轻量契约。它比完整项目管理 schema 故意轻得多，目的是**在不让正常逆向流程变慢的前提下，阻止范围无声膨胀**。
>

> ★★ **本机 playwright 必须显式指定浏览器**（2026-10-10 实测）：
> `launch()` 默认启动会报 `Executable doesn't exist at %LOCALAPPDATA%\ms-playwright\chromium_headless_shell-1234\...`
> —— python 包期望 1234，本机装的是 **1243**，版本号对不上。
> **可用写法**：`p.chromium.launch(channel="msedge")`（实测能起、能渲染、能读 DOM），
> 或 `launch(executable_path=<显式路径>)`。照抄裸 `launch()` 一定失败。
> 

---

## 适用信号（Recognition signals）

出现下列任一情况，说明必须在动作前落一份工单：

- 浏览器导航（navigation）或对当前目标的交互
- 实时 HTTP 请求、重试、WebSocket 握手，或发送帧（sent frame）
- 使用账号 / 会话状态
- 执行目标方提供的 JS、WASM、HTML 或不透明 helper（opaque helper）
- 安装依赖
- 写入任务证据或生成代码
- **从一条实现路线切换到另一条实现路线**

以下动作可以保持轻量，不要求工单：只读产物评审（read-only artifact review）、定值向量变换（fixed-vector transform）、静态源码检视（static source inspection）、以及内联 hook 建议 —— 只要它们**不写文件、不接触目标、不执行目标代码、不消耗账号状态**。

一句话定位：**「会写、会发、会跑、会用号」四类动作开工前，先落契约；其余保持轻量。**

## 前置（Entry conditions）

1. **先有判据，再有动作**。工单里的 `acceptanceTest` 字段必须能在动作之前写出来。若写不出来，说明目标尚未收敛到可验证的粒度，此时不该开工单，而该先做 `../triage/minimal-verifiable-facts-playbook.md` 的事。
2. **授权与范围已由用户给定**。本工单不产生授权，它只是**转录**既有授权。所有 `permissions` 字段只能取用户已明确给出的值；本文不涉及授权如何获取（见 `../../../field-journal/_template.md` 的「Scope 摘要（脱敏）」段落：把 `auth_basis` / `network_profile` / `asset_types` 以脱敏形式先固化下来，工单的 `scope` 与 `permissions` 是它的机器可读投影）。
3. **预算可计量**。`budget` 里四类计数器（请求、重试、WebSocket 帧）必须是整数而非「大概几十次」，否则 Egress Guard 无法在出站前判定。
4. **写权限先落地**。若 `writeMode` 为 `no-write` 或 `allowedPaths` 为空，则 `task.json` 本身**不落盘**，工单只在内存或对话中记录。这与 `../../../field-journal/_template.md` 的定位一致：脱敏 case 记录是要留痕的产物，未授权写入时它也应当降级为对话内记录。

## 步骤（Working method）

### 一、最小契约（Minimal Contract）

在笔记、报告里，或**在文件写入已获批准时**的 `js_reverse_cache/tasks/<task-id>/task.json` 里记录以下字段：

```json
{
  "shape": "evidence | local-proof | compact-replay | collector",
  "route": "evidence-reuse | chromium-recon | browser-hook | static-ast | env-patch | iv8-local-runtime | verifier | transport | pure-python-rebuild | python-collector",
  "gateFamily": "signer-gated | verifier-gated | decode-gated | session-gated",
  "secondaryGateTags": ["transport-gated"],
  "scope": {
    "scheme": "https",
    "host": "example.com",
    "port": 443,
    "routePrefix": "/api"
  },
  "permissions": {
    "browserRecon": false,
    "liveReplay": false,
    "accountOrSessionUse": "none",
    "targetCodeExecution": "blocked",
    "dependencyInstall": "blocked",
    "writeMode": "no-write"
  },
  "budget": {
    "requestsRemaining": 0,
    "retriesRemaining": 0,
    "websocketFramesRemaining": 0,
    "minDelayMs": 0,
    "concurrency": 1
  },
  "inputs": [],
  "allowedPaths": [],
  "acceptanceTest": "one objective proof for this route"
}
```

用**精确布尔值**，不要用含糊的词。**未知权限 = 该动作先按离线形态做（定值向量 / 静态检视 / 本地复现）；要发出站再把那一个字段补上。**

> 本机路线映射：`chromium-recon` / `browser-hook` 类路线在本机**没有** `chrome-devtools`、`js-reverse`、`camoufox-js-reverse` 专员可调用；`iv8-local-runtime` 路线本机无运行时。改走 `python-collector`（`python 3.12` + `curl_cffi`）、`transport`（`tshark 4.6.8` / `mitmdump 12.2.3`）或 `pure-python-rebuild`（`../deliver/pure-python-rebuild-playbook.md`）。

### 二、条件性实现简报（Conditional Implementation Brief）

**仅当**声明的 `shape` 是 `compact-replay` 或 `collector`，**且**至少还有一项实质选择未定时，才准备一份紧凑的实现简报（implementation brief）。触发现场包括：

- 存在一种以上可行实现形态，例如纯 Python 对比窄范围的 JS / WASM / bootstrap / decoder / transport helper
- 下一步会**扩大运行时或打补丁的面积**
- 依赖选择或安装授权尚未落定
- 证据、生成代码、fixture、产物或状态的**持久路径、保留规则或可写范围**尚未落定
- 某个有意义的权限选择会改变出站（egress）、账号 / 会话使用、目标代码执行，或可写范围

**不**为 `evidence`、`local-proof` 或明确的 no-write 分析要求这份简报。若某个实现形态已经被证明、且所有受门禁动作已被当前工单覆盖，一段简明的路线备注就够。

简报是**决策记录**，不是自动的用户审批门。它**从不授予权限**，也**不替代、不放宽** `permissions`、`budget`、scope 或 `allowedPaths`。只有在既有权限门禁要求新增授权、或某个真正实质的实现选择无法从当前证据解决时，才停下来等用户输入。

简报要紧凑且已脱敏，记录：

- 触发简报的原因与声明的交付形态
- 真实端点：scheme、host、port、route；方法；content type；**省略 userinfo 与原始 query 值**
- 每个动态字段：其写入方（writer）、wire 槽位（slot）、作用域、有效期、刷新路径
- 决定性证据与定值向量结果
- 可行的实现形态、各自的运行时与权限影响，以及为何选中该形态
- 选定的边界：Python 拥有实时 HTTP 与编排，对比任何窄范围本地 helper 的职责
- 必需的会话链、身份 / 上下文作用域、刷新契约
- 验收 oracle（判定器）、negative control（反向对照）、必需的 replay 次数
- 计划中的持久路径，受 Write Guard 约束
- 残余风险，以及什么样的证据能消解该风险

使用 `./report-templates.md` 中对应的模板；**只在 Write Guard 通过后**才落盘。

### 三、路线规则（Route Rules）

- **一条路线一次只拥有一个拦路点。**
- 路线可以返回证据、代码或拦路点；**它不重新定义最终目标**。
- 不要因为当前路线令人沮丧就去翻兄弟路线的手册或宽泛 playbook。
- 若某路线需要另一种能力，**先写下当前拦路点（一句）再切换**——这是交接记录的一部分，不是停点；所有权变更时返回 `./specialist-handoff-contract.md` 的 request / result 字段。**只有在当前工单明确授权了那条确切交接路径时**才落盘。
- **提供方完成 ≠ 任务完成。** Spider King 只按记录下来的 `acceptanceTest` 与所声明结果形态对应的门禁来验收。

### 四、出站门禁（Egress Guard）

**每次出站尝试之前**，逐条核对：

1. 目的地与记录的 scope 匹配。
2. 动作类别被允许：导航、请求、重试、WebSocket 握手，或发送帧。
3. 剩余预算**恰好覆盖**本次尝试。
4. 延迟与并发约束能被满足。
5. 若使用账号 / 会话状态，它被显式纳入 scope。

**紧邻尝试之前扣预算**：一次导航、一次初始 HTTP 请求、或一次 WebSocket 握手消耗 1 个 `requestsRemaining`；一次重试消耗 1 个 `requestsRemaining` 与 1 个 `retriesRemaining`；一次发送的 WebSocket 帧消耗 1 个 `websocketFramesRemaining`。**传输层早期失败不退还单位。**

### 五、执行门禁（Execution Guard）

在**有意**执行已保存的目标方代码或不透明 helper 之前：

1. 记录已评审字节的**确切本地路径与 SHA-256**。
2. 说明为什么静态检视或定值向量解析不足。
3. 除非明确需要且已批准，运行时**拒绝网络、文件系统与进程访问**。
4. 最终 replay 的出站保留在 Python 一侧；JS / WASM / iv8 只能返回一个窄范围产物。

**在范围内的一次基线浏览器导航属于证据收集，不等于批准把每个抓到的脚本都抽出来当本地 helper 重跑。** 它需要 `browserRecon`、目标 scope 与请求预算；但页面自动加载的资源**不需要**事先存在本地路径与哈希。要在证据浏览器之外有意重放任何目标资产，必须先保存并哈希确切字节。

**成功加载一个 helper 是运行时健康，不是协议证明。**

### 六、写入门禁（Write Guard）

写入之前：

1. 要求有可写的 `permissions.writeMode`；`no-write`、未知或省略都意味着 blocked。
2. 要求有**非空且继承而来**的 `allowedPaths`，并确认解析后的目的地**等于或低于**其中一个允许路径。
3. 套用 `./project-artifact-contract.md`；拒绝符号链接（symlink）、联接点（junction）、reparse point、硬链接别名、**技能目录**（skill directory）、操作系统临时目录，以及绑定项目之外的路径。
4. 易失性抓取（volatile captures）只写在**显式允许的** `js_reverse_cache/tasks/<task-id>/` 路径下。
5. 只有经过验证的稳定代码或 fixture 才提升（promote）到**显式允许的**稳定路径。
6. **未经针对该确切路径的明确授权，绝不覆盖用户维护的 collector、fixture、helper 或输入文件。**

### 七、结果形态（Result Shape）

返回或记录：

- 路线与拦路点 / 结果
- 决定性证据或产物路径
- 适用时的定值向量结果
- **仅在获批时**的实时 replay 结果
- 已消耗与剩余的预算
- 运行时清理状态（runtime cleanup state）
- 残余风险

**只要任务自有的浏览器、hook、profiler、worker、租约（lease）或本地运行时仍处于活跃状态，就不得宣称完成**，除非有明确记录的 retained exception（保留例外）。

## 判据（Verification checklist）

以下 12 条**全部**满足，才可以说「这份工单立住了」。标注 *（改编补入）* 的条目，是从源文档硬性规则反推的量化判据，源文档本身没有单列验收清单。

1. *（改编补入）* `task.json` 里 `shape`、`route`、`gateFamily` **三字段均已填**，且 `route` 取值落在源文档枚举内；**任一为空即视为未落契约**。
2. `permissions` 六个子字段全部是精确布尔或枚举字面量，**没有一个是自然语言描述**。
3. *（改编补入）* 每个 `permissions` 字段要么是显式值，要么**明确缺失**；不存在「暂时忘了填」这种情况。缺失即按 blocked / offline 执行。
4. `budget` 四类计数器均为**非负整数**，且 `concurrency ≥ 1`。
5. *（改编补入）* `acceptanceTest` 是**一句可判定的陈述**，能回答「什么结果算通过」；「看看情况」「验证一下」这类描述不合格。
6. `allowedPaths` 非空时，其中每个条目都能覆盖本次全部预期写入；为空时 `writeMode` 必为 `no-write`。
7. `scope` 四元组（scheme / host / port / routePrefix）足以唯一定位目标端点，且不含 userinfo 与原始 query 值。
8. `shape` 为 `compact-replay` 或 `collector` 且仍有实质未决选择时，**条件性实现简报已写**；否则**明确记录「不需要简报」及其理由**。
9. 每次实际出站前，Egress Guard 五条逐条核对过；消耗单位与实际动作类别**一一对应**（导航 / 首请求 / 握手各记 1 请求，重试记 1 请求 + 1 重试，发送帧记 1 帧）。
10. 有意执行目标代码前，**本地路径与 SHA-256 已记录**，且执行时网络 / 文件系统 / 进程权限按需关闭。
11. 每次写入前 Write Guard 六条通过；产物落在 `./project-artifact-contract.md` 规定的层级里，且**没有任何 symlink / junction / reparse point / 硬链接别名**参与路径。
12. 收尾时**无任何任务自有的活跃运行时残留**，或每一项都有明确的 retained exception 记录。

另有一条**边界一致性检查**（改编补入）：工单里的 `scope.host` / `permissions` 与 `../../../field-journal/_template.md`「Scope 摘要（脱敏）」里记录的 `network_profile` / `asset_types` **不矛盾**。两者是同一件事的两种写法（一份给人看、一份给机器读），出现分歧时以用户给出的授权为准并立刻修正工单。

## 常见坑（Common traps）

- **把「Provider 完成」当成「任务完成」**，没按 `acceptanceTest` 验收就宣布收工
- 省略或含糊写 `permissions`，然后凭直觉当成「应该是允许的」
- 预算写了模糊数字，结果出站前才发现不够，或者用不完就浪费
- 传输层早期失败了却退还预算单位，导致反复重试撞墙
- 一次「范围内的浏览器导航」被当成批准，把页面上的每个脚本都抽成 helper 重跑
- 加载 helper 成功就宣称协议搞懂了
- Write Guard 只检查了「路径在允许列表里」，**没检查解析后的真实落点**（symlink / junction 可以绕出去）
- 覆盖了用户维护的 collector / fixture / helper，导致对方的工作被冲掉
- 路线卡住就横向翻遍所有 playbook，范围无声膨胀
- 交接了所有权却没有返回 request / result 字段，或在没有授权的路径上落了 `handoff.json`
- 把 `no-write` 工单的结果偷偷写进项目目录
- 宣称完成时，任务自有的浏览器 / hook / worker 还开着

## 相关（Related）

- `./project-artifact-contract.md` —— Write Guard 第 3 条引用的产物落盘契约；产物层级与脱敏红线
- `./specialist-handoff-contract.md` —— 所有权变更时的 request / result 字段格式
- `./skill-maintenance.md` —— 工单相关条款的持续校验清单与沉积规则
- `./report-templates.md` —— 条件性实现简报与报告所用的模板
- `../observe/local-mcp-environment.md` —— 本机实际可用工具与已挂载 MCP 的现状（判断某条路线能否执行）
- `../deliver/delivery-gate-playbook.md` —— `shape` 从 `evidence` / `local-proof` 升到 `compact-replay` / `collector` 时的交付门禁
- `../deliver/pure-python-rebuild-playbook.md` —— `pure-python-rebuild` 路线的执行方法
- `../triage/reproducible-evidence-playbook.md` —— 决定性证据的最低标准
- `../state/session-contract-playbook.md` —— `accountOrSessionUse` 非 `none` 时的会话契约分层
- `../principles/anti-patterns-playbook.md` —— 本文「常见坑」段的原则级对照
- `../principles/doctrine-index.md` —— 本包全部 doctrine 的索引入口
- `../../../field-journal/_template.md` —— 授权与范围的脱敏 case 记录格式（`Scope 摘要（脱敏）` 段）
- `../../../field-journal/KB-INDEX.md` —— 沉淀后的经验卡与历史 case 检索入口
- `../../SKILL.md` —— 工单收尾时对 case 包做只读审查的流程

---

## 源文档勘误（改编时修正）

1. **源文档 `## Contents` 目录块指向的锚点全是英文标题**。本文按要求删除，改为中文六段式结构下的自然导航；未保留任何指向英文锚点的目录。
2. **源文档正文引用 `report-templates.md`、`specialist-handoff-contract.md`、`project-artifact-contract.md`**，写作「扁平 `references/` 下」。实际这三个文件在 `references/contract/` 子目录，同级。已全部改为同目录相对引用（`./xxx.md`），避免生成指向不存在的 `references/references/` 的路径。
3. **源文档路线枚举含 `camoufox-js-reverse`、`chrome-devtools`、`js-reverse` 三个专员技能**，本机**一个都没有挂载**；源文档也从未声明这些是必需项，其隐含前提是「已安装的专员快照」。已在「平台与本机状态」与路线映射处就地标注，并给出本机实际可走的替代路线（`python-collector` / `transport` / `pure-python-rebuild`）。枚举值本身**保持原样未改**，以免破坏 schema 兼容性。
4. **源文档 `route` 枚举含 `iv8-local-runtime`**，本机无 iv8（社区运行时，PyPI 无发行版）。同上：枚举保留、可用性就地标注，不擅自删除合法取值。
5. **源文档「判据」缺位**。原文档全篇是规则描述，没有一处单列的验收清单 —— 规则散落在 `Route Rules`、`Egress Guard`、`Execution Guard`、`Write Guard`、`Result Shape` 各节。已把这些硬性规则反推为 12 条可逐项核对的判据，并**明确标注哪几条是「改编补入」**，不谎称源文档原本就有清单。
6. **源文档 `## Result Shape` 最后一句**（「Do not claim complete while task-owned browsers…remain live」）在英文里没有把「例外」写成可记录的字段名。改编时统一为 `RETAINED_EXCEPTION`，与 `./specialist-handoff-contract.md` 的 `cleanupState` 枚举、以及 `./skill-maintenance.md` 的生命周期措辞要求保持一致 —— 源文档三处各说各话，这里做了本包内的术语统一。
7. **源文档未提脱敏落盘要求**。本文在「前置」与「判据」各补一条：`scope.host`、`permissions` 与 `../../../field-journal/_template.md` 的「Scope 摘要（脱敏）」不得矛盾，且该文档的字段契约由 `../../case-review/scripts/review_case.py` 校验。已标注为改编补入。
8. **源文档未提 `scripts/` 缺失问题**。本文**未引用任何 `scripts/*` 工具**（源文档的这份文件本来也没引），避免留下失效路径。