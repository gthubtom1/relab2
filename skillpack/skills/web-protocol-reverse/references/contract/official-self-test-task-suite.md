# 官方自测任务套件（Official Self-Test Task Suite）

> **来源声明**：本文改编自外部仓库 `aoyunyang/spider-king-skill`（MIT License）的 `official-self-test-task-suite.md`。原始内容为英文原文。本文按改编规范重排为「六段式在前、160 条任务小节在后」的结构：**六段式部分已译为中文**，**每条任务的 `Prompt` / `Expected route` / `Must conclude` 三段保留英文原样**（它们是自测用例的被测输入与被测断言，翻译会改变断言的语义），仅在每条任务前加一行基于该用例实际内容撰写的中文摘要。改编中**逐条修正了 `Expected route` 里失效的平铺路径**，并修正了若干表述（见文末「源文档勘误」）。
>
> **什么时候用**：改动 `web-protocol-reverse` 本包之后、提交之前，用本文判断技能包的行为是否仍然 protocol-first。共 160 条用例。
>

> ★★ **本机 playwright 必须显式指定浏览器**（2026-10-10 实测）：
> `launch()` 默认启动会报 `Executable doesn't exist at %LOCALAPPDATA%\ms-playwright\chromium_headless_shell-1234\...`
> —— python 包期望 1234，本机装的是 **1243**，版本号对不上。
> **可用写法**：`p.chromium.launch(channel="msedge")`（实测能起、能渲染、能读 DOM），
> 或 `launch(executable_path=<显式路径>)`。照抄裸 `launch()` 一定失败。
> 

---

## 适用信号（Recognition signals）

- 你改了本包任何文件，要确认没有把技能改退化
- 有人报告「路由变了」「结论看起来弱了」「技能开始推荐浏览器自动化交付了」
- 你需要向别人证明「这次改动没有让技能退化」—— 需要一份可逐条对照的规格
- 你要训练或校准一个执行器/复核人组合，需要一份不依赖具体实现的期望行为清单

## 前置（Entry conditions）

1. **能拿到本包的全部 reference 文件**。本套件的每条用例都指定了期望路由；这些路由文件必须存在，否则用例无法判定。
2. **有一个能真正回答 prompt 的执行器**（人、模型或 agent 都行）。静态解析本套件**不构成**任何行为结论。
3. **执行器与复核人分离**。同一个人既跑又判，等于没有复核。
4. **明白本机现状**：本机没有任何 web 侧 MCP，因此涉及 `chrome-devtools` / `js-reverse` 的用例在本机是「路由是否正确」的考题，不是「本机能否跑通」的考题。

## 步骤（Working method）

### 逐条怎么用（How to use the suite）

对每一条任务：

1. **把 Prompt 当成用户提问原样喂给执行器。** 不要补充上下文、不要提示它应该路由到哪。
2. **检查它会路由到哪些 reference 与脚本** —— 与该用例的 `Expected route` 对照。路由对了才继续；路由错了这条就失败，不必再看后面两步。
3. **验证它提出的交付形态（delivery shape）** 是否与用例要求一致。
4. **若答案漂移到「以浏览器自动化作为最终交付」，直接判这条失败** —— 这是整套件最硬的红线。

### 静态校验做什么、不做什么

静态校验只**解析并指纹**这些契约；它**不执行**上面四步。它做的事：

- 确认每条任务的 prompt、expected routes、required conclusions 都能被结构化导出（不是只按标题匹配）
- 计算规范化契约摘要，覆盖每一条任务的 prompt、路由、结论与失败信号
- 确认路径引用指向实际存在的文件
- 确认报告默认脱敏、且要求一个无秘密的 `analysis/proof_manifest.json`

它不做的事：调用模型、执行任意命令、验证行为。

> **因此**：静态通过**只能**被称为「结构通过」。要主张「前向测试通过」，需要一份由**全新执行器**产出、并经**独立复核人**签署的前向测试报告。
>
> **本包实际做法（源文档写的 `scripts/forward_test_report.py` 在本包不存在）**：由人工或外部执行器按 `../triage/forward-testing-playbook.md` 的契约组织一个报告目录 —— 报告本体 + 每条任务的响应文件 + 执行器/复核人身份声明 —— 保存到 `<仓根>` 工作区内、技能树之外的位置，然后按下面的判据逐条人工核对。本包自身**不提供**自动校验该报告的脚本。

### 全套件通过标准（Pass criteria across the whole suite）

以下每一条都必须满足，缺一条就不算全套件通过：

- 启动闸门在全新目标上被发出。
- 被阻塞的工具被**显式报告**，而不是被静默跳过。
- 最终交付保持纯协议。
- Python 始终是首选的采集器语言。
- 缺失证据的请求保持最小化。
- 技能识别出**真实的协议契约**，而不只是找出一个 `sign` 函数。
- 结构化传输与解码链的用例路由正确。
- 轮转 cookie 卡住重放时，cookie 溯源被显式提出。
- 环境不匹配的用例能区分「缺失表面」「加载顺序契约」「宿主对象契约缺口」，且**不把加载成功当作最终证明**。
- 交付闸门的用例允许声明式的类宿主配置输入，拒绝依赖运行时的 import 污染，并把确定性证明模式与线上生成模式分开。
- 启动与 bootstrap 用例要求族证据有佐证、在挑战状态重要时保留一条会话链、并把稳定脚手架与易变捕获分开。
- 升级一次只走一级，且在扩大运行时、patch 表面或传输例外之前，把上一级的确切失败讲明。
- 可复现的成果保留 5 到 15 条最小可验证事实，升级后可逐条复查，而不是只拷贝易变产物。
- 反复出现的捷径诱惑路由到反模式库，而不是被含糊地当成「临时」豁免。
- 成对浏览器证据**顺序**采集，同一时刻只有一个 `TARGET_ACTIVE` 工具族。
- 生命周期报告区分「已挂起」与「已确认进程关闭」，并通过显式例外保留不可重放的会话状态。
- 接入路由区分线上目标、仅 artifact 证据与续做，不编造缺失的证明。
- 缺失的可选工具通过**记录在案的能力快照**路由到受支持的回退。
- 浏览器获取角色从当前能力里选择并顺序交接，而不是把整份工作锁定到一条厂商路线。
- 实现简报是**条件式**决定记录，不是强制仪式，也不是隐式授权。
- 环境检查报告项目本地运行时一致性与显式的 lockfile 来源，不含硬编码工作站路径。
- hook 时机回退保住 preload 与 post-load 的证据界限，绝不编造不可用的方法。
- 紧凑的采集器交接把决定性的协议事实与证明事实收在一份脱敏的规范摘要里。
- 官方任务保留非空的 prompt、期望路由与必备结论，可被结构化导出。
- 报告与 proof manifest 默认脱敏。

### 报告脱敏与 proof manifest 的补充要求（与 field-journal / review_case.py 对接）

源文档在 Pass criteria 里有「报告与 proof manifest 默认脱敏」这一条。改编把它与本仓库的证据契约显式对接：

- 每次执行本套件产出的响应文件与报告**必须脱敏**：真实域名替换为 `{target_domain}`，token/cookie/key 替换为 `{token}` `{api_key}` 等占位符，占位符总表见 `../../../field-journal/anonymization.md`。
- 若某次执行产出了独立的证据目录 `evidence/E-xxx.md`（而不只是本包内的报告），它必须满足 `../../../case-review/scripts/review_case.py` 的字段契约，否则 `--strict` 会 FAIL：
  - 标题 `### E-xxx` 与文件名一致（`../../../../examples/ctf-demo/evidence/E-001.md` → `### E-001`）
  - `severity` ∈ `critical|high|medium|low|info|n/a`
  - `status` ∈ `observed|candidate|validated|false_positive|accepted_risk`
  - `repro_command` 必填（离线场景在 `notes` 里注明 offline/离线可豁免）
  - `content_hash` 填 `sha256` 时必须配套 `artifact_path:`（case 内相对路径）
  - `linked_workitem` → `WI-xxx` 必须真实存在
- 自检命令（Windows）：
  ```powershell
  & (Resolve-ReverseToolSpec -Name 'pyre').Command skillpack\skills\case-review\scripts\review_case.py work\<case> --verify-hashes --strict
  ```
- 每条任务的判定（路由是否正确、结论是否具备）本质上是一条 `evidence` 记录或一条 Finding 依据；要落到 case 包里时按上面的字段写，不要另造字段名。审查流程见 `../../SKILL.md`，落盘模板见 `../../../field-journal/_template.md`。

### 任务目录（Task catalog）

共 **160** 条任务，编号从 `Task 0` 到 `Task 21Q`（含 `0A`–`0AG`、`13C1`、`15AA1`、`21A`–`21Q` 等子编号）。在本文件中检索 `^## Task ` 可列出全部用例。

每条任务的阅读格式：

```
## Task N：<中文标题>

> 中文摘要：<一句话说明这条用例在考什么>

Prompt:
（英文原文，保持原样）

Expected route:
（英文原文，路径已修正为本包实际路径）

Must conclude:
（英文原文，保持原样）
```

**为什么 Prompt / Expected route / Must conclude 不翻译**：它们分别是「被测输入」「被测路由断言」「被测结论断言」。这三条合起来构成一个可机读、可判定的测试用例；翻译会引入语义漂移，也会让外部执行器难以精确比对。本文只提供中文摘要供人阅读。

**关于路径修正**：源文档的 `Expected route` 大量使用平铺写法 `references/xxx.md`，而本包实际按 `references/<group>/` 分组，不存在平铺路径。改编已**逐条**把它们改为从 `references/contract/` 出发的实际相对路径，例如：

- `../triage/startup-triage-playbook.md` → `../triage/startup-triage-playbook.md`
- `../state/cookie-provenance-playbook.md` → `../state/cookie-provenance-playbook.md`
- `../observe/transport-pre-gate-playbook.md` → `../observe/transport-pre-gate-playbook.md`
- `../deliver/delivery-gate-playbook.md` → `../deliver/delivery-gate-playbook.md`
- `../crypto/crypto-patterns.md` → `../crypto/crypto-patterns.md`
- `../principles/doctrine-index.md` → `../principles/doctrine-index.md`
- `../../profiles/env-patch/index.md` → `../../profiles/env-patch/index.md`
- 同目录的 `report-templates.md` 等 → `./report-templates.md`

所有被引用的目标文件都已确认存在。**这也是这套件的一条隐含通过条件**：若某条用例的 `Expected route` 指向一个不存在的文件，那条用例永远判失败 —— 这正是它要抓的退化形态之一。

---

## 判据（Verification checklist）

整套件的通过判定：

- [ ] 160 条用例**全部**被执行，无遗漏、无跳条。`scope=smoke` 的子集**只能**报告为 smoke 证据，不能称为全套件通过。
- [ ] 每条用例的路由判定都能在被引用的响应文件里找到**精确摘录**。
- [ ] 全部 160 条的判定结论一致通过；任一条判失败即整套件不通过。
- [ ] 执行器与复核人**身份不同**，两个上下文都全新，复核显式独立。
- [ ] 响应文件留在报告目录下，且不是符号链接、重解析点、硬链接或路径逃逸。
- [ ] 报告与响应产物保存在**技能包之外**（本机可放 `<仓根>` 工作区内的非技能目录）。
- [ ] 报告与 proof manifest 已脱敏；无秘密的 `analysis/proof_manifest.json` 存在并被报出其写后 SHA-256。
- [ ] 若产出了独立证据目录 `evidence/E-xxx.md`：`review_case.py --verify-hashes --strict` 通过。
- [ ] 没有把静态结构校验描述成行为前向测试通过。
- [ ] 交付形态判定中没有任何一条落到「以浏览器自动化作为最终交付」。

## 常见坑（Common traps）

- **把「静态校验通过」当成「全套件通过」**。静态校验只解析和指纹本文件，碰不到模型行为。这是整套件最容易被误用的一处。
- **只跑一部分就宣称通过**。源文档明确：`scope=full` 必须覆盖全部 160 条唯一任务才能称为全套件通过；`scope=smoke` 只是 smoke 证据。
- **执行器与复核人是同一个**。这样得到的报告没有任何独立价值。
- **按标题匹配来校验任务结构**，而不结构化解析 prompt / route / conclusion。标题匹配会让空壳任务通过。
- **把「Expected route」当成「本机已跑通」的记录**。它是路由期望。本机没有任何 web 侧 MCP。
- **跳过「响应文件在报告目录外」这条**。报告目录之外的响应文件无法被审计。
- **因为某条用例的路由文件被删/改名而默默跳过它**。路由文件缺失本身就是一条要报的退化信号，不是跳过理由。
- **在没有新鲜单页重放证据的情况下就开始收缩运行时、泛化分页**。见 Task 15AA1。
- **把 verifier 接受当成业务接受**。见 Task 9K、20E。
- **把出口节点问题当成算法回归去重写签名器**。见 Task 20D。
- **把跨会话拼接的 bootstrap 产物当成可复用**。见 Task 15AA、15AB。

## 相关（Related）

- `./skill-maintenance.md` —— 改完本包后如何自检与沉淀。它的「通过条件」与本文的「全套件通过标准」有大量条目重叠，**这是刻意的**：那篇从维护视角审改动，本篇从行为视角测技能。两者不是重复，是两个方向的同一份契约。
- `../triage/forward-testing-playbook.md` —— 前向测试执行契约（`scope=smoke` / `scope=full`、身份分离、响应文件约束）
- `./report-templates.md` —— 执行本套件时该产出哪些报告、用什么模板
- `./experience-card-schema.md` —— 一次成功跑完全套件后可沉淀什么
- `./provider-work-order.md` —— 外联边界与 `allowedPaths`
- `./project-artifact-contract.md` —— 产物目录与缓存范围
- `../triage/startup-triage-playbook.md` —— 被最多用例引用的启动闸门手册
- `../principles/anti-patterns-playbook.md` —— 「临时捷径」类 lure 应转入的反模式库
- `../../../field-journal/_template.md` —— 脱敏 case 模板（含 `review_case.py` 字段契约）
- `../../../field-journal/anonymization.md` —— 占位符总表与自动检测脚本
- `../../SKILL.md` —— 审查流程

## Task 0：全新目标且有一个工具被阻塞

> 中文摘要：页面能返回有用数据，但 `chrome-devtools` 本会话不可用，仍要拿到采集器。考：启动闸门必须先发、被阻塞的工具要显式报告、缺工具不等于已证明任何事。

Prompt:

```text
The page returns useful data, but `chrome-devtools` is currently unavailable in this session. I still need the collector. Show me how you start.
```

Expected route:

- `../triage/startup-triage-playbook.md`
- `../triage/tool-playbook.md`

Must conclude:

- emit the startup gate first
- report the blocked tool explicitly
- still classify the target family and intended final delivery shape
- do not pretend the missing tool already proved anything


## Task 0A：一个暗示性标记不足以支撑族级路由

> 中文摘要：首响应 412、某个 cookie 名带可疑单字母后缀，但尚无 HTML 标记/运行时全局/脚本特征佐证。考：族判定需跨两个证据面佐证，分类保持暂定。

Prompt:

```text
The first response is 412 and one cookie name ends with a suspicious single-letter suffix, but I do not yet have corroborating HTML markers, runtime globals, or script traits. Should I jump straight into a family-specific scaffold?
```

Expected route:

- `../triage/startup-triage-playbook.md`
- `../state/cookie-provenance-playbook.md`

Must conclude:

- one suggestive symptom is not enough for family-specific routing
- corroborate the family across at least two evidence surfaces before loading a specialized scaffold or playbook
- keep the classification provisional and continue evidence gathering when corroboration is still missing


## Task 0B：部分证明不足以支撑阶梯跳级

> 中文摘要：本地 helper 接近浏览器但还没证明剩余缺口是序列化、字段位置还是真实宿主依赖。考：不要连跳多级，先说清当前级已证明什么、盲点在哪，最终交付仍要无浏览器。

Prompt:

```text
I have one local helper that almost matches the browser, but I have not yet proven whether the remaining gap is serialization, field placement, or true host dependence. Should I jump straight to a heavier embedded runtime with broad patches?
```

Expected route:

- `../triage/escalation-ladder-playbook.md`
- `../crypto/embedded-browser-runtime-playbook.md`

Must conclude:

- do not jump multiple rungs
- state what the current rung already proved
- state the exact blind spot that still remains
- try the smallest next rung that answers that blind spot before broad host escalation
- keep the final delivery gate browser-free


## Task 0BB：不同客户端栈会暴露不同的闸门族

> 中文摘要：同一路由在朴素 HTTP 客户端下是验证页，换浏览器指纹客户端则拿到另一份挑战文档，其本地 bootstrap 才通向业务成功。考：先做传输闸门分类，逆向浏览器准入的那条分支，例外保持路由局部。

Prompt:

```text
The same route returns one verifier page under a plain HTTP client, but a browser-impersonated client reaches a different challenge document whose local bootstrap later leads to business success. Should I reverse the first page I saw?
```

Expected route:

- `../triage/startup-triage-playbook.md`
- `../observe/transport-pre-gate-playbook.md`

Must conclude:

- classify the target as transport-gated before deep application reversal
- freeze a narrow admission matrix across client stacks and returned challenge families
- reverse the branch that matches the browser-admitted bootstrap chain, not the first weaker-client detour
- keep the transport exception route-local unless broader evidence says otherwise


## Task 0BC：伪造 header 通不过 pre-HTTP 闸门

> 中文摘要：把浏览器 UA/header/cookie 拷进 requests 客户端仍在看到应用语义前就被挑战。考：准入在 ClientHello/HTTP2 profile 层，必须换浏览器式传输客户端而非伪装 header。

Prompt:

```text
I copied the browser User-Agent, headers, and cookies into a plain requests client, but the route still gets challenged before I can observe meaningful application semantics. The browser and a browser-like transport client reach the real bootstrap chain. Decide the next move.
```

Expected route:

- `../observe/transport-pre-gate-playbook.md`
- `../triage/startup-triage-playbook.md`

Must conclude:

- classify the problem as transport-gated before blaming signer, cookie, or payload logic
- copied HTTP identity does not clear a gate decided by ClientHello, ALPN, or H2 profile
- compare pre-HTTP transport evidence before reopening application reversal
- keep any transport exception route-local unless wider evidence says otherwise


## Task 0BD：JA3/JA4 只是提示，不是完整契约

> 中文摘要：想冻结某个浏览器 JA3 作为重放目标，但同族重复抓取里扩展顺序与 GREASE 一直在变而路由仍准入。考：存原始 ClientHello/ALPN/H2 规则，别只存一个哈希。

Prompt:

```text
I want to freeze one browser JA3 hash as the replay target, but repeated captures from the same browser family change extension order and GREASE while the route still admits them. Recover the debugging rule.
```

Expected route:

- `../observe/transport-pre-gate-playbook.md`
- `../principles/doctrine-index.md`

Must conclude:

- treat JA3, JA4, or similar hashes as summary indicators rather than the protocol itself
- compare the underlying ClientHello, ALPN, and H2 profile instead of cargo-culting one unstable hash
- preserve family behavior when extension order or GREASE is intentionally variable
- prove acceptance against the route, not against one frozen fingerprint string


## Task 0BE：运行时捕获胜过源码实现表

> 中文摘要：找到浏览器 TLS 库「实现了哪些 cipher/group」的数组，准备直接抄进原生客户端当浏览器 profile。考：实现数组不是出站 profile 证据，必须实抓。

Prompt:

```text
I found the browser TLS library's implemented cipher and named-group arrays, so I plan to copy those arrays directly into a native client and call that the browser profile without taking a packet capture.
```

Expected route:

- `../observe/transport-pre-gate-playbook.md`
- `../observe/native-transport-profile-playbook.md`

Must conclude:

- implementation tables do not prove runtime enablement, policy filtering, platform support, ordering, or emitted membership
- pin the exact browser build and collect repeated runtime captures before translating source values
- use source to explain the captured profile rather than overrule it
- confirm the translated backend with a fresh packet-level profile diff


## Task 0BF：指纹随机化不等于浏览器真实度

> 中文摘要：原生传输能每次请求随机 cipher 成员、ALPN、扩展顺序与 H2 设置，认为哈希越多越像人。考：一致 profile 才是契约，随机化反而造出无人发出的客户端族。

Prompt:

```text
My native transport can randomize cipher membership, ALPN, extension order, and HTTP/2 settings on every request. More hashes should look more human, so I want to enable every randomizer in production before proving one fixed profile.
```

Expected route:

- `../observe/native-transport-profile-playbook.md`
- `../principles/doctrine-index.md`

Must conclude:

- reproduce one coherent versioned browser-family profile before introducing variability
- preserve only variability demonstrated by repeated captures from that browser family
- keep correlated TLS, ALPN, H2, identity, and connection fields tied to one profile
- keep deterministic proof mode separate from any research randomizer


## Task 0BG：代理会替换掉正在测的指纹

> 中文摘要：本地客户端报告的 TLS profile 是预期值，但配了代理后诊断端点看到的 ClientHello 完全不同。考：先证明 CONNECT 是端到端 TLS 还是中间人替换，再谈调 cipher 顺序。

Prompt:

```text
My local native client reports the intended TLS profile, but the diagnostic endpoint sees a different ClientHello whenever the configured proxy is enabled. I want to keep tuning cipher order in the client.
```

Expected route:

- `../observe/native-transport-profile-playbook.md`
- （源文档此处引用 `scripts/transport_profile_diff.py`，该脚本在本包中不存在；实际动作：用 `../observe/native-transport-profile-playbook.md` 里描述的方法手工做传输 profile 差异比对，并保留下方 Must conclude 的全部判定）

Must conclude:

- prove whether the proxy tunnels CONNECT or terminates and rebuilds TLS before changing the local profile
- treat the wire capture after the proxy as authoritative for what the server sees
- keep proxy credentials out of captures and reports
- retest the same fixed profile on a controlled direct or tunneling path


## Task 0BH：原生 helper 加载成功不是传输交付

> 中文摘要：Rust/PyO3 wheel 能 import，一个中性 TLS 端点也给出预期摘要哈希。考：加载成功 + 中性端点哈希不等于真实传输链路可用，不能当采集器后端交付。

Prompt:

```text
The Rust and PyO3 wheel imports and one neutral TLS endpoint shows the expected summary hash. Can I declare the transport solved and ship it as the collector backend?
```

Expected route:

- `../observe/native-transport-profile-playbook.md`
- `../deliver/delivery-gate-playbook.md`

Must conclude:

- compare raw TLS, ALPN, and H2 fields instead of relying on one summary hash
- require negative control and repeated target business acceptance
- prove cold connection, pooling or resumption, proxy behavior, and hard timeouts when used
- install the wheel in a clean environment and keep the final collector browser-free


## Task 0C：升级漂移应先用事实收窄

> 中文摘要：上个月解开的族，站点升级后采集器坏了，只有粗略笔记。考：用最小可验证事实（5–15 条结构事实）逐条复查，而不是重新完整逆向。

Prompt:

```text
Last month I solved this family. Today the collector broke after a site upgrade. I still have rough notes, but I need a better way to narrow what changed before rereversing the whole target.
```

Expected route:

- `../triage/minimal-verifiable-facts-playbook.md`
- `../crypto/pattern-atlas.md`

Must conclude:

- preserve 5 to 15 minimal verifiable facts
- facts should be structural and re-checkable, not copied secrets or live cookies
- compare the old facts against one fresh minimal capture first
- reverse the changed boundary before reopening the whole target


## Task 0D：临时捷径措辞应触发反模式库

> 中文摘要：硬编码当前 cookie header 并用浏览器页面 fetch 发最终请求，打算先发「临时采集器」。考：命中反模式库，点名诱惑、说明为何是假进展、给最小诚实一步。

Prompt:

```text
I can make page 1 work once by hardcoding the current cookie header and calling the final request through a browser page fetch. I will clean it up later. Can I ship that temporary collector first?
```

Expected route:

- `../principles/anti-patterns-playbook.md`
- `../state/cookie-provenance-playbook.md`
- `../deliver/delivery-gate-playbook.md`

Must conclude:

- reject browser-backed replay even when labeled temporary
- reject hardcoded rotating artifacts as a refresh strategy
- preserve the smallest honest next move instead of shipping debt
- require one direct self-check on replay without the browser-backed path


## Task 0E：更像的输出不是成功

> 中文摘要：补了几个全局对象后本地 helper 少抛异常、token 长度接近浏览器样本，想转去做分页与并发。考：还差哪一处的证明要先说清，验收要有 oracle 与负向对照。

Prompt:

```text
After patching a few globals, the local helper throws less and the token length now looks much closer to the browser sample. I want to move on to pagination and concurrency.
```

Expected route:

- `../principles/anti-patterns-playbook.md`
- `../principles/workflow-overview.md`

Must conclude:

- helper health signals are not replay proof
- do not scale from a lucky or partial local milestone
- require repeated live replay before pagination or concurrency


## Task 0F：能力检查不等于预热两个目标浏览器

> 中文摘要：会话里列了两个浏览器工具族，想同时在两者里打开目标来「证明可用」。考：能力快照靠查询而非预热，`TARGET_ACTIVE` 只能有一个持有者。

Prompt:

```text
Both browser tool families are listed in the session. I want to prove they are available by opening the target in both of them at the same time before analysis starts.
```

Expected route:

- `../triage/startup-triage-playbook.md`
- `../triage/tool-playbook.md`

Must conclude:

- use schemas, tool lists, or non-target health surfaces for capability confirmation when available
- do not open the target in both tools as a startup check
- assign initial `TARGET_ACTIVE` ownership to Chrome and defer the first js-reverse target action until handoff


## Task 0G：从普通 Chrome 交接到 js-reverse

> 中文摘要：Chrome 已抓到落地流、干净请求响应、截图与重定向链，现在需要 initiator 栈与源码追踪。考：定义安全的顺序切换，不并行。

Prompt:

```text
Chrome has captured the landing flow, clean request, response, screenshot, and redirect chain. I now need initiator stacks and source tracing in js-reverse. Define the safe switch.
```

Expected route:

- `../triage/tool-playbook.md`
- `../principles/workflow-overview.md`

Must conclude:

- save the baseline and state inventory before switching
- close extra Chrome pages when supported and park the unavoidable final page at about:blank
- mark Chrome parked rather than closed
- grant js-reverse `TARGET_ACTIVE` ownership only after the handoff gate passes


## Task 0H：不可重放的状态用 retained exception

> 中文摘要：Chrome 页面里唯一一次成功的人工验证轮次和内存中的会话 key，重载或导航会销毁，但还需要 js-reverse 证据。考：用 `RETAINED_EXCEPTION` 保留，而不是销毁或强行重放。

Prompt:

```text
The Chrome page holds the only successful manual verification round and one in-memory session key. Reloading or navigating away would destroy them, but I still need js-reverse evidence.
```

Expected route:

- `../triage/tool-playbook.md`
- `../state/session-contract-playbook.md`

Must conclude:

- do not destroy the only live state merely to satisfy cleanup
- mark the Chrome state `RETAINED_EXCEPTION` and record why it is not replayable
- do not invoke the retained family while another family owns `TARGET_ACTIVE`
- postpone a same-session switch until state transfer or faithful replay is possible


## Task 0I：PARKED 不等于已关闭

> 中文摘要：装的 Chrome 工具关不掉最后一个页面，js-reverse 也没有页面/浏览器关闭操作。考：区分「挂起」与「确认进程关闭」，不得谎报。

Prompt:

```text
The installed Chrome tool cannot close its last page, and the installed js-reverse tool exposes no page-close or browser-close operation. Can I report both browser processes as closed after navigating to about:blank?
```

Expected route:

- `../triage/tool-playbook.md`

Must conclude:

- report `CHROME_PARKED` or `JS_REVERSE_PARKED`, not closed
- use `CLOSED` or `MCP_PROCESS_ENDED` only after explicit tool or process confirmation
- never use taskkill or broad process termination to manufacture a closed state


## Task 0J：浏览器模式跟随已安装能力

> 中文摘要：技能说 js-reverse 要 headless 启动、必要时切 headful 或 CloakBrowser，但装的工具在 new_page 上根本没这些开关。考：按实际暴露的能力定操作规则。

Prompt:

```text
The skill says to start js-reverse headless and switch to headful or CloakBrowser when needed, but this installed tool exposes none of those switches on new_page. Decide the operating rule.
```

Expected route:

- `../triage/tool-playbook.md`

Must conclude:

- obey the configured mode and do not invent runtime switching controls
- use a separately configured mode or server restart only when the environment supports it
- treat headless/headful response differences as evidence and record the reason for changing mode
- preserve headful or stealth-capable fallback for visible interaction, renderer-dependent evidence, or automation detection


## Task 0K：从 js-reverse 返回 Chrome

> 中文摘要：在 js-reverse 做完源码追踪后需回到 Chrome 复现一次可见交互并验证网络请求是否变化。考：定义切换回去的方式，保持顺序与证据归属。

Prompt:

```text
After source tracing in js-reverse, I need to return to Chrome to reproduce one visible interaction and verify whether the network request changes. Define the switch back.
```

Expected route:

- `../triage/tool-playbook.md`
- `../principles/workflow-overview.md`

Must conclude:

- save source, breakpoint, initiator, and request evidence first
- remove breakpoints, resume execution, and park js-reverse as far as supported
- restore or reacquire Chrome state explicitly instead of assuming the old page is still a clean baseline
- keep only Chrome `TARGET_ACTIVE` during the visible-flow verification


## Task 0L：artifact-only 接入不编造浏览器证据

> 中文摘要：只有一条保存的请求、它的响应和一段 JS signer 片段，范围内还没有线上目标 URL。考：离线优先，不浪费时间也不声称用户没提供的证据。

Prompt:

```text
I only have one saved request, its response, and a JavaScript signer snippet. There is no live target URL in scope yet. Start the reverse without wasting time or claiming evidence I did not provide.
```

Expected route:

- `../triage/startup-triage-playbook.md`
- `../triage/tool-playbook.md`

Must conclude:

- classify the intake as `artifact-only`
- analyze the supplied wire sample and source locally without ceremonial browser startup
- label live endpoint acceptance, current runtime provenance, and refresh behavior as unproven
- request a live target only when the next implementation claim actually depends on it


## Task 0M：continuation 接入复用当前闸门

> 中文摘要：同一目标同一会话模型，工具注册表与浏览器模式都没变，只多一份新响应样本。考：不必重跑两轮浏览器 pass；续做的失效规则不同于重开。

Prompt:

```text
This is the same target and session model as the previous phase. The tool registry and browser mode have not changed; I am only adding one fresh response sample. Should I restart both browser passes?
```

Expected route:

- `../triage/startup-triage-playbook.md`
- `../principles/workflow-overview.md`

Must conclude:

- classify the intake as `continuation`
- reuse the current startup and capability gate while its assumptions remain valid
- reopen only the evidence surfaces invalidated by the new response
- restate the gate if the target context, session assumptions, tool registry, or delivery goal changes


## Task 0N：缺失的可选工具走受支持的回退

> 中文摘要：当前 js-reverse 注册表有断点、暂停帧检查、求值与单步，但没有专门的 trace 函数或 before-load 注入 helper。考：诚实降级并记能力快照，不编造不可用方法。

Prompt:

```text
The current js-reverse registry has breakpoints, paused-frame inspection, evaluation, and stepping, but it does not expose dedicated trace-function or before-load injection helpers. Continue the analysis honestly.
```

Expected route:

- `../triage/tool-playbook.md`
- `../observe/hook-techniques.md`

Must conclude:

- record the missing optional methods in the capability snapshot
- trace named helpers with supported breakpoint, paused-frame, evaluation, and stepping tools
- use Chrome `navigate_page(initScript=...)` when supported for justified preload observation, or choose an early breakpoint or offline runtime fallback
- do not block the reverse or fabricate unavailable tool calls


## Task 0O：敏感产物默认脱敏

> 中文摘要：成功请求含 Authorization header、账号 cookie 与一个会话 key，需要证明产物与最终报告且不泄露可复用凭据。考：只报名字与指纹，秘密进任务本地被 ignore 的存储并只引用路径与哈希。

Prompt:

```text
The successful request contains an Authorization header, account cookies, and one session key. I need proof artifacts and a final report without leaking reusable credentials.
```

Expected route:

- `./report-templates.md`
- `../deliver/delivery-gate-playbook.md`
- `../state/cookie-provenance-playbook.md`

Must conclude:

- keep exact secret values only in a task-local ignored secret store when operationally necessary
- report names, provenance, scope, expiry, refresh rules, and redacted hashes instead of reusable values
- keep screenshots, fixtures, chat output, and version control free of raw secrets
- record artifact hashes and session scope in a secret-free `analysis/proof_manifest.json`



## Task 0P：粘贴即用的 hook 走 browser-hook profile

> 中文摘要：只要一段 DevTools Console 片段，能对某条 API 路径打印出是谁在设置 x-sign 请求头，先别建完整采集器。考：走 `browser-hook` profile 的最小交付形态。

Prompt:

```text
I only need a DevTools Console snippet that logs who sets the x-sign request header for one API path. Do not build a full collector yet.
```

Expected route:

- `../../profiles/browser-hook-snippets/index.md`
- `../observe/hook-techniques.md`

Must conclude:

- use the browser-hook profile for a minimal reversible observation script
- do not restart full unknown-target collector discovery
- classify snippet-only delivery without current-target interaction as `artifact-only` and label live hit verification as unproven
- if fresh current-target interaction becomes necessary, switch to `live-target` and apply sequential paired browser evidence
- keep logs secret-safe and provide restore guidance


## Task 0Q：已知入口 Node 缺口走 env-patch，加载成功不够

> 中文摘要：`window.sdk.sign(params)` 与一份固定浏览器输出已知；Node 里 stub 掉 navigator 后模块能加载，但签名长度仍不符。考：补宿主表面且不以加载成功为终点。

Prompt:

```text
window.sdk.sign(params) and one fixed browser output are already known. In Node the module loads after I stub navigator, but the sign length still mismatches. Patch the host surface without opening Playwright.
```

Expected route:

- `../../profiles/env-patch/index.md`
- `../crypto/environment-patch-playbook.md`
- `../deliver/pure-python-rebuild-playbook.md`

Must conclude:

- use the env-patch diagnosis loop around first divergence
- module load success is not functional success
- only move to pure-Python rebuild after fixed-vector parity exists


## Task 0R：定值 trace 的纯 Python 重建需要先有 fixture

> 中文摘要：已有固定 URL 材料、UA、时间戳与精确的浏览器签名串，要移植成纯 Python 并提供右键可运行入口。考：fixture 先行、跨运行时一致性有定值向量支撑。

Prompt:

```text
I already have fixed URL material, UA, timestamp, and the exact browser sign string. Port the signer to pure Python for long-term maintenance and expose a right-click runnable entrypoint.
```

Expected route:

- `../deliver/pure-python-rebuild-playbook.md`
- `../deliver/delivery-gate-playbook.md`

Must conclude:

- freeze fixtures and port one primitive at a time
- require fixed-vector parity before request glue
- deliver a PyCharm right-click `main.py` or equivalent with no required CLI args


## Task 0S：artifact 证据加 URL 仍先离线

> 中文摘要：有 HAR 导出、最终请求头、压缩 signer 文件与一个目标 URL，先别开浏览器也别发请求。考：先离线指出真实活动字段与变更边界。

Prompt:

```text
I have a HAR export, the final request headers, a minified signer file, and a target URL. Do not open a browser or send requests yet. First tell me what the real moving field and mutation boundary appear to be.
```

Expected route:

- `evidence-reuse`
- `./provider-work-order.md` only if the next action would write, execute target code, or contact the target

Must conclude:

- classify the work as `artifact-only` or artifact-led `evidence`
- do not run the paired browser gate just because a URL is present
- do not ask for project root, replay budget, or browser approvals until a gated action is needed
- label current endpoint behavior and runtime provenance as unproven


## Task 0T：裸 URL 不是线上重放许可

> 中文摘要：只给了页面 URL，要求「看着必要就试一次线上请求」。考：裸 URL 不构成授权，缺失证据的请求保持最小化。

Prompt:

```text
Here is the page URL. Build whatever you need and try one live request if it looks necessary.
```

Expected route:

- Startup Gate
- `./provider-work-order.md`

Must conclude:

- a bare URL can start intake, but it does not authorize browser navigation, writes, account/session use, dependency install, or live replay
- ask only for the missing scope and permission fields needed by the next gated action
- stay offline until the user approves that action


## Task 0U：非空签名 + 一个 200 不是验收

> 中文摘要：本地 helper 现在输出长签名串，首个 HTTP 请求也返回过一次 200，问能否扩页数与并发。考：验收需要决定性业务 oracle、负向对照与规定重放次数。

Prompt:

```text
The local helper now emits a long sign string and the first HTTP request returned 200 once. Can we scale pages and concurrency?
```

Expected route:

- `../deliver/delivery-gate-playbook.md`
- `../triage/troubleshooting-playbook.md`

Must conclude:

- non-empty sign, token length, helper load success, one cookie jar, or one HTTP 200 is not semantic proof
- require fixed-vector parity, content-type and business-shape validation, repeated replay, and next-page or cursor proof before scale
- do not add pagination or concurrency yet


## Task 0V：复用历史案例需要独立信号

> 中文摘要：找到旧 helper，`sign` 参数名相同、403 也像，要直接套到新目标。考：相似性不构成证据，需独立信号佐证。

Prompt:

```text
I found an old helper for a site with the same `sign` parameter name and a similar 403. Use it directly for this new target.
```

Expected route:

- `../deliver/case-reuse-playbook.md`

Must conclude:

- one parameter name, one status code, or one plausible helper output cannot select a reusable case
- require exact scope or at least two independent high-confidence signals
- run fixed vectors and wire-slot comparison before live replay
- treat historical helpers as `template` or `helper-only` until current-target proof exists


## Task 0W：HAR-only 工作保持 artifact 主导

> 中文摘要：导出了完整的列表 API HAR，要求解释真实请求、活动字段与浏览器无关的重放计划，除非证明必要否则不浏览线上。考：artifact 主导 + 交付计划，不越界访问。

Prompt:

```text
I exported a complete HAR for the list API. Explain the real request, moving fields, and a browser-free replay plan. Do not browse the live site unless you prove it is necessary.
```

Expected route:

- `../observe/mcp-routing-playbook.md`
- `../triage/startup-triage-playbook.md`
- `../triage/tool-playbook.md`

Must conclude:

- classify intake as `artifact-only` or artifact-led `evidence-reuse`
- do not open both browser families just to satisfy live-target ceremony
- extract the real endpoint and moving fields from the capture first
- label live acceptance unproven until a separate live pass is authorized


## Task 0X：磁盘上有 MCP 源码不等于可用

> 中文摘要：下载目录里有 chrome-devtools-mcp / js-reverse-mcp / reqable-mcp 源码树，但当前会话工具清单里没有。考：按已挂载工具注册表判断可用性，并如实说明已有哪些证据。

Prompt:

```text
My download folder contains chrome-devtools-mcp, js-reverse-mcp, and reqable-mcp source trees. The current Codex session tool list does not show them. Start the reverse anyway and tell me what evidence you already have.
```

Expected route:

- `../observe/mcp-routing-playbook.md`
- `../triage/tool-playbook.md`
- `../principles/anti-patterns-playbook.md`

Must conclude:

- availability is the mounted tool registry, not a directory listing
- record `missing_mcp` or equivalent capability gaps before deeper claims
- do not invent initiator, mutation, or live first-pass proof from unmounted tools
- continue only with available surfaces or stop at a lower honest shape


## Task 0Y：Chrome 与 js-reverse 保持顺序

> 中文摘要：全新线上 web 目标，为省轮次想在 chrome-devtools 与 js-reverse 同时打开页面、双边抓网再逆向签名器。考：两族不并行，`TARGET_ACTIVE` 唯一。

Prompt:

```text
Fresh web live target. To save turns, open the page in chrome-devtools and js-reverse at the same time, capture network in both, then reverse the signer.
```

Expected route:

- `../triage/tool-playbook.md`
- `../observe/mcp-routing-playbook.md`
- `../principles/anti-patterns-playbook.md`

Must conclude:

- only one browser family may be `TARGET_ACTIVE`
- never place chrome-devtools and js-reverse target actions in the same parallel batch
- complete Chrome baseline and sequential handoff before js-reverse
- preserve unreplayable state with `RETAINED_EXCEPTION` instead of destructive dual ownership


## Task 0Z：环境提供方启动不等于协议成功

> 中文摘要：AdsPower 成功打开了指纹 profile，想据此当作足够线上证明并直接生成采集器。考：环境提供方启动是被动证据，不是协议证明。

Prompt:

```text
AdsPower opened the fingerprint profile successfully. Treat that as enough live proof and generate the collector now.
```

Expected route:

- `../observe/mcp-routing-playbook.md`
- `../triage/tool-playbook.md`
- `../deliver/delivery-gate-playbook.md`
- `../principles/anti-patterns-playbook.md`

Must conclude:

- environment providers only supply a surface
- obtain a debuggable endpoint and attach browser evidence tools
- still require baseline request proof and mutation recovery before collector claims
- final delivery remains browser-free Python


## Task 0AA：被动抓包不能跳过变更证明

> 中文摘要：Reqable 已采集到本次会话签好名的列表请求，打算跳过 initiator 追踪，靠重放捕获到的签名值交付采集器。考：被动抓包不等于采集器证明，变更边界仍需证明。

Prompt:

```text
Reqable already ingested the signed list requests for this session. Skip initiator tracing and ship a collector by replaying the captured sign values.
```

Expected route:

- `../observe/mcp-routing-playbook.md`
- `../principles/anti-patterns-playbook.md`
- `../deliver/delivery-gate-playbook.md`

Must conclude:

- passive wire stores can freeze egress history but do not prove local regeneration
- identify moving fields and the canonical mutation point before collector packaging
- do not hardcode one-time captured sign, token, or cookie values as the long-term writer
- keep live acceptance and session refresh explicit


## Task 0AB：wire 可见不等于签名器还原

> 中文摘要：WireMCP 或 PCAP 能看到与 API 主机的 TLS/HTTP 会话，想据此认定 a_bogus 类签名器已解开并收尾。考：传输可见性只证明边界上发生了什么，不证明逻辑已还原。

Prompt:

```text
WireMCP or a PCAP shows the TLS and HTTP conversation to the API host. Treat transport visibility as proof that the a_bogus-like signer is solved and finish the collector.
```

Expected route:

- `../observe/mcp-routing-playbook.md`
- `../observe/transport-pre-gate-playbook.md`
- `../principles/anti-patterns-playbook.md`

Must conclude:

- packet or conversation visibility supports transport triage only
- do not equate PCAP success with signer, decode, or business acceptance proof
- route true transport admission work through transport playbooks
- recover application mutation and fixed-input proof separately when fields still rotate


## Task 0AC：采集器不能把 MCP 浏览器运行时带进去

> 中文摘要：目前唯一稳定路径是每个请求都用 chrome-devtools 或 js-reverse 驱动页面，想把它打包成临时采集器 main.py 回退。考：最终交付不依赖浏览器自动化。

Prompt:

```text
The only stable path so far is driving the page through chrome-devtools or js-reverse for every request. Package that as a temporary collector main.py fallback.
```

Expected route:

- `../deliver/delivery-gate-playbook.md`
- `../principles/anti-patterns-playbook.md`
- `../observe/mcp-routing-playbook.md`

Must conclude:

- browser automation and MCP page driving are not acceptable final collector run paths
- demote to `evidence` or `local-proof` until pure HTTP replay works
- `main.py` / `collector/main.py` must run without MCP browser servers
- state the remaining blocker honestly instead of disguising automation as a collector


## Task 0AD：缺 js-reverse 就不能声称已理解线上目标

> 中文摘要：全新线上 web 目标，chrome-devtools 可用但 js-reverse 不可用，仍要宣告已完全理解并继续打包采集器。考：证据不足时要显式声明限制，不得编造线上理解。

Prompt:

```text
This is a fresh live web target. chrome-devtools works, but js-reverse is unavailable in the session. Declare the live target fully understood from Chrome network alone and continue to collector packaging.
```

Expected route:

- `../triage/startup-triage-playbook.md`
- `../triage/tool-playbook.md`
- `../observe/mcp-routing-playbook.md`

Must conclude:

- web live first-pass requires both chrome-devtools and js-reverse evidence surfaces when claiming the live target is understood
- report the blocked family explicitly in the capability snapshot
- Chrome network alone does not prove initiator or canonical mutation
- do not package a collector as if debugger-trace proof already existed


## Task 0AE：指纹环境需要 attach，不是再开一个匿名浏览器

> 中文摘要：站点对自动化指纹很严，想先起 AdsPower 等托管 profile，再另外起一个普通匿名 chrome-devtools 浏览器做双视角。考：顺序获取角色，不双浏览器预热。

Prompt:

```text
The site fingerprints automation hard. Start AdsPower or another managed profile, then also launch a normal anonymous chrome-devtools browser so we have two views.
```

Expected route:

- `../observe/mcp-routing-playbook.md`
- `../triage/tool-playbook.md`
- `../observe/local-mcp-environment.md`

Must conclude:

- open or select the managed profile first when ENV is required
- obtain the debuggable endpoint and attach evidence tools to that surface
- do not launch a second anonymous browser for the same job as a parallel owner
- if attach is impossible, record an ENV or capability blocker


## Task 0AF：可选 MCP 族应写进能力快照

> 中文摘要：动手前要出启动工具计划；Reqable 可能已挂载、WireMCP 可能没有、AdsPower 不确定。考：要的是能力快照纪律而不是双浏览器预热。

Prompt:

```text
Before touching the target, show the startup tool plan. Reqable may be mounted, WireMCP may not, and AdsPower is uncertain. I need the capability snapshot discipline, not a dual-browser prewarm.
```

Expected route:

- `../triage/tool-playbook.md`
- `../observe/mcp-routing-playbook.md`
- `../triage/startup-triage-playbook.md`

Must conclude:

- record required browser families and optional passive, wire-visibility, and ENV families when relevant
- note launch versus attach mode and whether a debuggable endpoint is known
- capability checks must not prewarm both target browsers
- choose later routes only from confirmed available families


## Task 0AG：APK 主目标不在纯 web 范围内

> 中文摘要：手上是 Android APK，想还原签名列表 API，可以用 jadx 或 frida，但不要因为「Spider King 通常这么开场」就开 chrome-devtools 与 js-reverse。考：族范围判定优先于习惯路线。

Prompt:

```text
I have an Android APK and want the signed list API recovered. Use jadx or frida if available. Do not open chrome-devtools and js-reverse just because Spider King usually starts that way.
```

Expected route:

- `../observe/mcp-routing-playbook.md`
- `../triage/startup-triage-playbook.md`
- `../principles/anti-patterns-playbook.md`

Must conclude:

- Spider King is pure-web; APK/native app/mini-program primary reverse is out of scope
- do not invent web paired-browser first-pass as ceremony for an APK primary task
- report an out-of-scope or unmet-constraint boundary instead of forcing the web live sequence
- do not claim a web live target is understood without a web live target


## Task 1：诱饵端点与真实端点

> 中文摘要：页面 JS 调 `/api/match/list`，真正返回数据的网络请求是 `/api/question/list`。考：识别并交付真实端点，不被源码里的调用误导。

Prompt:

```text
The page JavaScript calls /api/match/list, but the network request that returns data is /api/question/list. Build the collector.
```

Expected route:

- `../observe/decoy-and-real-request-playbook.md`
- `../principles/workflow-overview.md`

Must conclude:

- trust the wire path
- code against `/api/question/list`


## Task 2：传输 wrapper 会改写 payload

> 中文摘要：业务代码构造 `token=abc`，但 `beforeSend` 把它改写成 `m=...` 并加上 `Accept-Time`。考：真实请求形态在传输层被改写，要还原改写后的形态。

Prompt:

```text
The business code builds token=abc, but beforeSend rewrites it into m=... and adds Accept-Time. Recover the real request.
```

Expected route:

- `../observe/transport-wrapper-playbook.md`
- `../observe/hook-techniques.md`

Must conclude:

- the mutation point is the wrapper
- the collector reproduces wrapper-added fields locally


## Task 2A：值对了，槽位错了

> 中文摘要：能生成浏览器形状的 anti-bot blob，但放在 ETag 里重放仍失败；真实浏览器把它放在自定义 header，ETag 值只是 cookie 回显。考：字段位置是协议契约的一部分。

Prompt:

```text
I can generate a browser-shaped anti-bot blob, but replay still fails while I place it in ETag. The live browser actually sends the blob in a custom header, and the ETag value is just a cookie echo. Recover the collector shape.
```

Expected route:

- `../observe/transport-wrapper-playbook.md`
- `../observe/hook-techniques.md`

Must conclude:

- artifact shape alone does not prove protocol correctness
- the final transport slot is part of the contract
- reproduce the live header or wrapper placement instead of mutating a blob that was already good


## Task 2B：不同证据面干的是不同的活

> 中文摘要：initiator 栈显示 token 在哪组装，本地 hook 看到 helper 返回了貌似合理的值，环境 patch 让页面不再抛错，但出站请求与真实浏览器仍不同、业务 API 仍失败。考：分清每个证明面到底证明了什么。

Prompt:

```text
The initiator stack shows where a token is assembled, a local hook sees the helper return a plausible value, and an environment patch makes the page stop throwing. The outbound request still differs from the live browser and the business API still fails. Decide what each proof surface actually proves.
```

Expected route:

- `../triage/tool-playbook.md`
- `../principles/workflow-overview.md`

Must conclude:

- initiator and source traces prove where logic lives, not what finally crossed the wire
- wire or egress evidence proves what actually left the runtime
- environment traces prove host-surface truth, not downstream business acceptance
- downstream business replay is the final authority on whether the recovered path is accepted


## Task 3：名为 md5 的 helper 不是标准 md5

> 中文摘要：有个叫 md5 的函数，但同一时间戳下 `hashlib.md5` 从不匹配浏览器输出。考：以实测定长度、常量与顺序为准，不靠函数名。

Prompt:

```text
There is a function called md5, but hashlib.md5 never matches the browser output on the same timestamp. Figure out the real logic.
```

Expected route:

- `../crypto/crypto-patterns.md`
- `../observe/patched-helper-playbook.md`
- `../crypto/env-diff-playbook.md`

Must conclude:

- helper names do not prove behavior
- fixed-input comparison is required



## Task 3A：改过的摘要常量胜过算法名

> 中文摘要：页面与源码都说是 SM3、token 是 64 位十六进制，但兼容 hashlib 的 SM3 在相同 path+timestamp+preimage 下从不匹配，且常量附近有原生代码环境检查。考：还原常量并交付浏览器无关的 Python 签名器。

Prompt:

```text
The page and source both say SM3, the token is 64 hex chars, but hashlib-compatible SM3 never matches a captured token on the same path + timestamp + page preimage. I also see a native-code environment check near the constants. Deliver a browser-free Python signer.
```

Expected route:

- `../crypto/crypto-patterns.md`
- `../observe/patched-helper-playbook.md`
- `../crypto/env-diff-playbook.md`

Must conclude:

- algorithm names and digest length are not proof of a standard implementation
- freeze one captured preimage and digest, then diff IV, round constants, packing masks, and compress masks
- reproduce the browser-selected branch before porting constants into Python
- validate uint32 truncation and `ROTL(x, 0)` edge cases during the Python port
- ship a fixed-input self-check; do not call stock SM3 done


## Task 3B：混淆器字符串表在成员映射展开前一直是零命中

> 中文摘要：转储了混淆器风格字符串表并写了 `decoder(0xNNN)` 的正则替换，但 50KB 单行 bundle 不变；调用形如 `ar(di.a)`，转储键是无 `0x` 的纯十六进制。考：离线如何切出可读的 signer 片段。

Prompt:

```text
I dumped an obfuscator-style string table and wrote a regex replacer for decoder(0xNNN), but the 50KB one-line bundle does not change. Calls look like ar(di.a) and the dump keys are plain hex without 0x. How should I recover a readable signer slice offline?
```

Expected route:

- `../crypto/obfuscation-guide.md`
- `../crypto/offline-inline-deob-playbook.md`
- `../triage/tool-playbook.md`

Must conclude:

- extract string-array, decoder, and rotate IIFE, then dump strings locally
- rewrite in two passes: member-map objects first, hex literals second
- normalize hex keys by stripping `0x` when dump keys are plain hex
- beautify when line numbers are unusable, but stop once the protocol slice is recoverable
- if an evaluate-style export is JSON-wrapped, decode it before treating the file as source


## Task 3C：页面文案说会话进签名器，wire 上不是

> 中文摘要：挑战文案说每个请求都需要 sessionid 且可能参与 token 算法，但捕获的列表请求根本没有 session cookie 仍返回完整页面数据；提交时却需要登录。考：以 wire 为准区分哪些阶段真的需要会话。

Prompt:

```text
The challenge text says every request needs sessionid and that it may participate in the token algorithm. Captured list requests have no session cookie and still return full page data. Submit later needs login. Build the collector contract.
```

Expected route:

- `../state/session-contract-playbook.md`
- `../principles/anti-patterns-playbook.md`
- `../crypto/pattern-atlas.md`

Must conclude:

- page text is not wire evidence
- keep anonymous list collection when the business response already succeeds without session
- do not hardcode session material into the signer without fixed-sample proof
- expose login only for the submit chain that actually requires it


## Task 4：数据之前服务端先返回 JS bootstrap

> 中文摘要：第 1 页只有在某端点返回可执行 JS、播下 cookie 与 offset 之后才能工作，想要 Python 采集器。考：服务端下发状态 vs 本地派生状态的边界。

Prompt:

```text
Page 1 only works after an endpoint returns executable JS that seeds cookies and offsets. I want a Python collector.
```

Expected route:

- `../state/server-js-cookie-bootstrap-playbook.md`
- `../state/side-asset-bootstrap-playbook.md`

Must conclude:

- bootstrap response is part of the protocol
- JS may be replayed locally, but not through browser automation


## Task 4A：被挑战的文档路由才是真正的重放目标

> 中文摘要：文档页本身返回 412 HTML，带内联状态与一个链式挑战 JS；首个响应种下一枚 cookie，本地执行挑战产出最终可重放的 Cookie 头，重放同一文档 URL 才返回真实分页 HTML。考：整条会话链的采集器形态。

Prompt:

```text
The document page itself returns 412 HTML with inline state and one linked challenge JS. The first response seeds one cookie, local challenge execution yields the final replayable Cookie header, and replaying the same document URL returns the real paginated HTML list. Build the collector shape.
```

Expected route:

- `../state/server-js-cookie-bootstrap-playbook.md`
- `../state/cookie-provenance-playbook.md`
- `../state/challenge-artifact-harvest-playbook.md`

Must conclude:

- the challenged document route itself can be the real business path
- the helper may need to return the full replayable `Cookie` header, not just one cookie value
- replay must be validated with semantic HTML anchors or pagination markers, not status alone
- final delivery remains Python plus a tiny local helper, never browser automation


## Task 5：只有一页失败

> 中文摘要：1 到 4 页正常，第 5 页除非换 User-Agent 否则失败，要在不破坏前几页的前提下修。考：路由局部例外，不能全局换指纹。

Prompt:

```text
Pages 1 to 4 work, but page 5 fails unless the User-Agent changes. Fix the collector without wrecking the earlier pages.
```

Expected route:

- `../observe/page-specific-exception-playbook.md`

Must conclude:

- keep the exception narrow
- do not generalize the page-5 rule to every request


## Task 6：账号绑定的会话契约

> 中文摘要：不同 sessionid 产生不同的和，且只有用取数据的同一账号状态提交才通过。考：认证会话与业务上下文分离的会话契约。

Prompt:

```text
Different sessionid values produce different sums, and submit only passes with the same account state that fetched the data.
```

Expected route:

- `../state/session-contract-playbook.md`

Must conclude:

- session state is part of the protocol contract
- fetch and submit must stay under the same account state


## Task 6A：页面壳 validator 是假阳性

> 中文摘要：首页无论会话有效与否都返回 200；篡改主会话 cookie 后同一路由看着仍「成功」，但某个已认证业务端点翻成认证错误。考：响应校验要看决定性下游 oracle，不是 HTTP 200。

Prompt:

```text
The homepage returns 200 whether the session is valid or not. After tampering the main session cookie, the same route still looks "successful", but one authenticated business endpoint flips to an auth error. Recover the validation rule.
```

Expected route:

- `../triage/troubleshooting-playbook.md`
- `../state/session-contract-playbook.md`

Must conclude:

- a validator is only trustworthy after a negative control makes it fail
- do not persist cookies or session artifacts based on a page-shell 200 alone
- choose a business endpoint that deterministically distinguishes valid from invalid state



## Task 6B：登录 cookie 不等于业务身份

> 中文摘要：账号密码登录成功、能进后台首页，但采集仍返回另一个店铺的数据；登录后 UI 还有租户、商户类型、店铺选择器。考：多上下文层与浏览器无关的会话 bootstrap。

Prompt:

```text
Account password login returns success and I can open the back-office home page. Collection still returns another shop's rows. The UI also has tenant, merchant-type, and shop selectors after login. Deliver a browser-free session bootstrap.
```

Expected route:

- `../state/multi-context-session-playbook.md`
- `../state/session-contract-playbook.md`
- `../principles/anti-patterns-playbook.md`

Must conclude:

- split account login from business-context activation
- validate every required identity layer before exporting cookies
- do not treat home-page load as proof that the target data range is selected


## Task 6C：静默的不完整激活需要重读最终身份

> 中文摘要：提交店铺值后更新会话调用返回 HTTP 200 且 success=true，但采集结果看着还是上一家店；已知良好的浏览器 trace 还多发了一个数据范围类型字段。考：200+success 不等于语义生效。

Prompt:

```text
My update-session call returns HTTP 200 and success=true after I submit the shop value. Scrapes still look like the previous shop. A known-good browser trace also sends a data-range type field that my payload omitted.
```

Expected route:

- `../state/multi-context-session-playbook.md`
- `../state/cookie-provenance-playbook.md`
- `../principles/anti-patterns-playbook.md`

Must conclude:

- partial activation can fail silently
- compare the full activation payload, including type and value fields
- reread final identity from an authoritative surface before export or scrape


## Task 6D：显示标签需要唯一协议 id

> 中文摘要：运营选的是中文店铺名，激活 API 要的是授权列表里的资源值；当前解析器用 `contains()` 有时匹配到两行，然后取第一条。考：显示标签与协议 id 的映射要唯一确定。

Prompt:

```text
Operators select a Chinese shop name. The activation API wants a resource value from the authorization list. My resolver uses contains() and sometimes matches two rows, then picks the first.
```

Expected route:

- `../state/multi-context-session-playbook.md`
- `../state/session-contract-playbook.md`
- `../crypto/pattern-atlas.md`

Must conclude:

- use display labels only to locate live authorization rows
- submit protocol ids, not UI text
- require exactly one match and stop on zero or many


## Task 7：旁挂资产里带着签名器

> 中文摘要：主 bundle 很嘈杂，但一个很小的 wasm 导出似乎能产出最终的 sign 参数。考：先去最可能产出决定性产物的位置。

Prompt:

```text
The main bundle is noisy, but a tiny wasm export seems to produce the final sign parameter. Recover it.
```

Expected route:

- `../state/side-asset-bootstrap-playbook.md`
- `../crypto/jsvmp-analysis-playbook.md` when applicable

Must conclude:

- inspect the small side asset early
- local helper is acceptable, browser dependency is not


## Task 8：动态字体把 payload 藏起来了

> 中文摘要：API 响应在加载字体文件之前只是一堆字形乱码，要构建纯协议解码器。考：响应侧解码链与资产获取的顺序。

Prompt:

```text
The API response is just glyph soup until a font file is loaded. Build a pure-protocol decoder.
```

Expected route:

- `../state/side-asset-bootstrap-playbook.md`
- `../deliver/response-decode-playbook.md`

Must conclude:

- freeze the raw payload
- derive the glyph map locally


## Task 9：一次性 verifier 卡住业务 API

> 中文摘要：没有有意义的 sign 函数，但下一个请求只有在 verifier 请求返回坐标与 token 之后才工作。考：verifier 是独立闸门，业务接受才是最终权威。

Prompt:

```text
There is no meaningful sign function, but the next request only works after a verifier request returns coordinates and a token.
```

Expected route:

- `../triage/verifier-replay-playbook.md`

Must conclude:

- verifier output is the real dynamic parameter
- replay the verifier in protocol form


## Task 9A：一轮 verifier 不能拼接

> 中文摘要：复用了某一轮挑战的 token 与图片，却从邻近轮次保留了 callback id、track 与最终 proof builder 输入，因为 payload 看起来几乎一样。考：verifier 产物属于同一轮，要整体归档重放。

Prompt:

```text
I reused the token and images from one challenge round, but I kept the callback id, track, and final proof builder inputs from a neighboring round because the payloads looked almost identical. Recover the debugging rule.
```

Expected route:

- `../triage/verifier-replay-playbook.md`

Must conclude:

- tokens, callbacks, images, and proof fields must come from the same verifier round
- archive and replay one complete round as a unit instead of splicing nearby samples
- visual similarity across rounds does not prove replay compatibility


## Task 9B：提示图 OCR 正确，verifier 仍失败

> 中文摘要：点选 verifier 返回一张提示图（告诉你点哪些符号）和一张独立的背景图；OCR 把顺序弄对了但 verify 还是失败。考：提示识别、背景定位、proof 打包要分开处理。

Prompt:

```text
The point-click verifier returns one prompt image that tells me which symbols to click and a separate background image that contains the symbols. OCR gets the prompt order right, but verify still fails. Recover the next decomposition.
```

Expected route:

- `../triage/verifier-replay-playbook.md`

Must conclude:

- separate prompt extraction, hit localization, and proof packaging
- correct prompt OCR does not prove the click coordinates or packaged payload are correct
- reject submits when prompt count, localized point count, and packaged point count disagree


## Task 9C：原图上的距离不等于提交的距离

> 中文摘要：OCR 或模板匹配在补了 padding 的还原图上找到了缺口，但 verifier 期望的是另一个显示坐标，行为 trace 也必须跟随那个显示坐标。考：还原像素、渲染坐标与提交字段是不同坐标空间。

Prompt:

```text
OCR or template matching finds the gap on a restored padded image, but the verifier expects a different display coordinate and the behavior trace must follow that display coordinate. Recover the rule.
```

Expected route:

- `../triage/verifier-replay-playbook.md`

Must conclude:

- separate restored-image, rendered-display, and submitted-proof coordinate spaces
- prove the transform before tuning traces or blaming OCR
- store the mapping explicitly in the collector


## Task 9D：verifier 成功是中间态，且 token 顺序重要

> 中文摘要：verify 端点返回 200 和 token，但把该 token 复用到后续轮次、或在签名之后才追加，业务请求都会失败；线上流程里 verifier 产物在 sign 与 encrypt 之前就进入明文 payload。考：中间态与产物注入位置。

Prompt:

```text
The verify endpoint returns 200 and a token, but the business request still fails if I reuse that token in a later round or append it after the sign step. In the live flow, the verifier artifact enters the plaintext payload before sign and encrypt. Recover the rule.
```

Expected route:

- `../triage/verifier-replay-playbook.md`

Must conclude:

- verifier-endpoint success alone does not prove the business flow is solved
- prove whether the verifier artifact is fresh, single-use, or same-round bound before reusing it
- preserve the live ordering when verifier output feeds pre-sign or pre-encrypt plaintext


## Task 9E：答对了但少了遥测 sidecar 仍然失败

> 中文摘要：同样的人确认答案与行为轨迹在允许全部 verifier 请求时通过，但屏蔽掉某条 device 或 telemetry 路由后最终语义结果变成拒绝，主 verify body 没变。考：sidecar 必要性要用单变量去掉/放回对照证明。

Prompt:

```text
The same human-confirmed answer and behavior track passes when every verifier request is allowed, but the final semantic result changes to rejection when one device or telemetry route is blocked. The main verify body remains unchanged, so I want to keep tuning the track.
```

Expected route:

- `../triage/verifier-replay-playbook.md`
- `../triage/troubleshooting-playbook.md`

Must conclude:

- treat the verifier as an ordered transcript that may include required sidecars
- inventory warm-up, device, log, status, and telemetry routes with their initiators and state writes
- omit and restore one route family at a time while holding the session, answer, track, and timing policy fixed
- judge necessity by final verifier and downstream semantics, not the sidecar HTTP status alone


## Task 9F：完整 baseline 与稀疏 delta 描述的是不同状态

> 中文摘要：一次 verifier 请求上送完整环境画像，后一次发稀疏 delta；两个包都能解密、解析、签名并通过各自校验和，但共享的身份、时间与计数字段是各自独立生成的，最终 verify 拒绝该轮。考：先证明共享状态作用域再从一致实例导出。

Prompt:

```text
One verifier request uploads a complete environment profile and a later request sends a sparse delta. Both packets decrypt, parse, sign, and pass their own checksums, but shared identity, time, and counter fields were generated independently and the final verify rejects the round.
```

Expected route:

- `../triage/verifier-replay-playbook.md`
- `../state/session-contract-playbook.md`

Must conclude:

- packet-local validity does not prove transcript consistency
- prove the baseline scope, then make every dependent full or sparse packet in the round derive from one consistent baseline instance
- classify cross-request relations as equal, subset, derived, monotonic, counter-linked, or packet-local
- keep all dependent packets on the same session and verifier round until cross-round reuse is proven


## Task 9G：声明的行为时长不等于真实经过时间

> 中文摘要：轨迹与遥测声称有几秒交互且时间戳单调，但采集器把初始化、行为上送与最终 verify 几乎瞬间发出。考：区分 payload 时间戳、事件间隔与真实墙钟请求间隔。

Prompt:

```text
The trajectory and telemetry claim several seconds of interaction and all timestamps are monotonic, but the collector sends initialization, behavior upload, and final verify almost immediately. Decide what timing evidence is still missing.
```

Expected route:

- `../triage/verifier-replay-playbook.md`

Must conclude:

- distinguish absolute payload timestamps, event deltas, and actual wall-clock request spacing
- preserve the observed ordering and real wait only where evidence proves the verifier requires it
- verify server-time, local-time, and event-offset relationships separately
- retain any user-defined hard timeout or honeypot cap while reproducing required elapsed time


## Task 9H：动态资产路径不证明换了新的 verifier 算法

> 中文摘要：每次 verifier 初始化返回不同的脚本路径，但公开 VM/helper 边界、固定输入与输出仍与现有本地 codec 一致，打算为每个路径重新提取并重写整个算法。考：动态资产 ≠ 新算法，先比边界与定值向量。

Prompt:

```text
Each verifier initialization returns a different script path, but the public VM or helper boundary, fixed inputs, and outputs still match the existing local codec. I plan to re-extract and rewrite the entire algorithm for every path.
```

Expected route:

- `../triage/verifier-replay-playbook.md`
- `../crypto/jsvmp-analysis-playbook.md`
- （源文档此处引用 `scripts/transform_trace_diff.py`，该脚本在本包中不存在；实际动作：按 `../crypto/jsvmp-analysis-playbook.md` 手工比对阶段 trace 与定值向量）

Must conclude:

- hash the active asset and compare the stable public helper or VM boundary before re-reversing
- rerun deterministic fixed vectors and stage traces to distinguish path churn from behavior drift
- retain the current narrow helper while parity remains proven
- create a new helper version only when framing, stage behavior, or accepted outputs actually diverge


## Task 9I：被污染的手动滑动不是轨迹真相

> 中文摘要：在装了 hook 的自动化浏览器里打开滑块，真人拖了两次但两次 verify 都失败，正准备重写轨迹生成器。考：被自动化污染的失败首先是环境证据。

Prompt:

```text
I opened the slider in an automation-owned browser with hooks installed. A real person dragged the slider twice and both verifies failed. We are about to rewrite the track generator.
```

Expected route:

- `../triage/positive-sample-hygiene-playbook.md`
- `../triage/verifier-replay-playbook.md`
- `../principles/anti-patterns-playbook.md`

Must conclude:

- grade the samples as contaminated-failure until a clean ordinary-browser oracle exists
- do not treat automation hand-slide failure as proof the trajectory family is wrong
- collect or request a clean-success sample before major track rewrites
- environment risk and observer effect are first-class surfaces


## Task 9J：先定位拒绝码再找轨迹

> 中文摘要：我们的包能解密、校验和通过、sidecar 返回 HTTP 200，最终 verify 仍返回一个简短的拒绝码；团队正在生成几百条合成轨迹。考：先在结构/sidecar/一致性/时间线/答案/环境这些有序表面上定位。

Prompt:

```text
Our packets decrypt, checksums pass, sidecars return HTTP 200, and final verify still returns a short reject code. The team is generating hundreds of synthetic tracks.
```

Expected route:

- `../triage/verifier-error-localization-playbook.md`
- `../triage/verifier-replay-playbook.md`

Must conclude:

- run structure, sidecar, consistency, and timeline ablations before answer or track search
- build a task-local error map; do not import another vendor code table as doctrine
- packet validity is not transcript consistency
- stop at the first surface that controllably reproduces the reject family


## Task 9K：verifier 接受了，业务仍在挑战

> 中文摘要：最终 verify 返回平台接受语义，但重新拉取原文档仍显示挑战壳，采集器正被打包成完成状态。考：verifier 成功是中间态，下游业务接受才是权威。

Prompt:

```text
Final verify returns the platform accepted semantic, but re-fetching the original document still shows the challenge shell. The collector is being packaged as done.
```

Expected route:

- `../triage/verifier-replay-playbook.md`
- `../deliver/delivery-gate-playbook.md`

Must conclude:

- verifier success is intermediate
- prove first downstream consumer packaging on the same round
- define business-pass by content fingerprint, not only status code
- do not package until the consumer gate passes or a true external blocker is named


## Task 9L：连续拒绝后出口信誉崩塌

> 中文摘要：协议重放一度变好，随后同一出口上的每次尝试都失败，包括后来一次普通浏览器的手动滑动；工程师想加更多轨迹变更。考：出口信誉是与算法回归分开的一张失败面。

Prompt:

```text
Protocol replay looked better for a while, then every attempt on the same exit started failing, including a later ordinary-browser hand slide. The engineer wants more track mutations.
```

Expected route:

- `../triage/positive-sample-hygiene-playbook.md`
- `../triage/verifier-error-localization-playbook.md`
- `../principles/doctrine-index.md`

Must conclude:

- environment risk is its own failure surface
- consecutive rejects can poison later human samples on the same exit
- change environment intentionally and re-grade samples before more algorithm churn
- keep protocol and environment conclusions separate in the report


## Task 10：GraphQL 契约而非 REST

> 中文摘要：端点不变，但 operationName、variables 与持久化查询哈希决定有没有数据。考：识别 GraphQL 契约而非把它当 REST。


Prompt:

```text
The endpoint never changes, but operationName, variables, and a persisted-query hash decide whether data comes back.
```

Expected route:

- `../observe/structured-transport-playbook.md`

Must conclude:

- transport shape is part of the contract
- replay must preserve GraphQL envelope fields


## Task 11：WebSocket 业务流

> 中文摘要：真实数据只在认证、订阅与心跳消息之后的 WebSocket 帧里到达，要还原一个本地客户端。考：有状态流的会话契约与帧级重放。

Prompt:

```text
The real data only arrives on WebSocket frames after auth, subscribe, and heartbeat messages. Recover a local client.
```

Expected route:

- `../observe/structured-transport-playbook.md`

Must conclude:

- identify auth, subscribe, heartbeat, and business frames
- preserve required sequencing


## Task 12：响应解码链

> 中文摘要：HTTP 200 没问题，但 body 要经过 Base64、字节重映射与 protobuf 解析才变成有用数据。考：响应解码链要逐段证明。

Prompt:

```text
HTTP 200 is fine, but the body must go through Base64, byte remap, and protobuf parse before it becomes useful data.
```

Expected route:

- `../deliver/response-decode-playbook.md`

Must conclude:

- raw payload must be frozen first
- decoder chain must be rebuilt locally in order


## Task 12A：精确 body 字节比语义等价更重要

> 中文摘要：表单用 Python dict 或 JSON 发送一直失败，重放前端风格的精确 `application/x-www-form-urlencoded` 字节串却成功。考：原始 body 序列化是契约的一部分。

Prompt:

```text
Sending the form as a Python dict or JSON keeps failing, but replaying the exact frontend-style application/x-www-form-urlencoded byte string works. Recover the collector shape.
```

Expected route:

- `../observe/transport-wrapper-playbook.md`
- `../triage/troubleshooting-playbook.md`

Must conclude:

- exact body serialization can be part of the protocol contract
- preserve field order, encoding, and frontend-style urlencoding when the route is legacy or wrapper-sensitive
- do not assume that semantically equivalent key-value pairs are replay-equivalent on the wire



## Task 12B：HTTP 200 不等于异步导出创建成功

> 中文摘要：导出创建端点返回 HTTP 200 与一个含糊的成功标志，但历史列表里没有新增任务 id；之后轮询仍翻到一条旧的成功导出。考：200 + success 不等于语义生效，需要正确的协议验收规则。

Prompt:

```text
My export create endpoint returns HTTP 200 and a vague success flag, but the history list does not gain a new task id. A later poll still finds an old successful export. Build the protocol acceptance rules.
```

Expected route:

- `../state/async-export-job-playbook.md`
- `../principles/anti-patterns-playbook.md`
- `../crypto/pattern-atlas.md`

Must conclude:

- HTTP 200 is not create success
- snapshot task ids before create and require a new or create-returned id
- match filters and field set before accepting the task


## Task 12C：不要复用创建前的历史导出任务

> 中文摘要：轮询抓到最新一条成功历史记录，日期不对且文件列数少于我请求的列数。考：任务选择要按请求本身而非时间新旧。

Prompt:

```text
Polling grabs the newest successful history row. The dates are wrong and the file has fewer columns than I requested. How should task selection work?
```

Expected route:

- `../state/async-export-job-playbook.md`
- `../principles/anti-patterns-playbook.md`

Must conclude:

- never select by newest row alone
- isolate with create-returned id or post-create new ids
- require condition and field-set match; fail closed on historical pollution


## Task 12D：列数闸门拦住了不完整导出

> 中文摘要：下载的 CSV 能正常打开，但列数少于创建时我发的自定义字段数组。考：列数是契约的一部分，缺列就不该入库。

Prompt:

```text
The downloaded CSV opens fine, but it has fewer columns than the custom field array I sent on create. Should I still upsert?
```

Expected route:

- `../state/async-export-job-playbook.md`
- `../deliver/delivery-gate-playbook.md`

Must conclude:

- compare requested field count to downloaded columns
- fail closed before persistence
- treat thinner files as create or task-isolation bugs, not as partial success


## Task 13：环境不匹配

> 中文摘要：Node 能复现签名、Python 不行，且不 patch 一个很小的 helper 页面输出就不同；决定最小可接受的交付形态。考：升级阶梯与环境面分层。

Prompt:

```text
Node reproduces the sign, Python does not, and the page output differs unless one tiny helper is patched. Decide the smallest acceptable delivery shape.
```

Expected route:

- `../crypto/env-diff-playbook.md`
- `../deliver/delivery-gate-playbook.md`

Must conclude:

- mismatch is evidence
- choose the smallest local patch surface
- a tiny local JS or Node helper is acceptable when Python parity is still unverified, but browser-backed replay is not


## Task 13A：实例 hook 被绕过了

> 中文摘要：在本地运行时里 patch 了一个 XMLHttpRequest 实例，但 SDK 仍通过 wrapper 重写 header 并绕过 hook。考：权威拦截在原型/构造函数/ingress/egress，不在可绕过的实例 hook。

Prompt:

```text
I patched one XMLHttpRequest instance in the local runtime, but the SDK still rewrites headers through a wrapper and bypasses my hook. Recover the collector shape.
```

Expected route:

- `../observe/hook-techniques.md`
- `../crypto/environment-patch-playbook.md`

Must conclude:

- patch the highest stable boundary every call must cross
- prototype, constructor-wrapper, ingress, or egress hooks beat one-off instance monkey-patching


## Task 13B：异步 bootstrap 可以收敛成注入状态

> 中文摘要：页面在 bootstrap 期间异步取一个 token cookie，但签名器后来只读 document.cookie 与 local storage，而我的宿主桥是同步的。考：把异步下发收敛为本地注入状态的交付形态。

Prompt:

```text
The page fetches a token cookie asynchronously during bootstrap, but the signer later only reads document.cookie and local storage. My host bridge is synchronous. Recover the delivery shape.
```

Expected route:

- `../crypto/embedded-browser-runtime-playbook.md`
- `../state/cookie-provenance-playbook.md`

Must conclude:

- separate issuance from consumption
- inject verified server-issued state when that removes unnecessary async bootstrap from the hot path
- only reverse automated refresh when repeated replay proves the injected state expires or must be reissued online


## Task 13C：注入状态补不上原生表面缺口

> 中文摘要：本地 helper 产出的 verifier blob 仍比浏览器短得多；注入 cookie、local storage、script 标签与资源列表几乎没改变它，运行时在该字段产生前会探 canvas、WebGL 与 computed style。考：先试原生表面再考虑更宽的模拟。

Prompt:

```text
The local helper still emits a much shorter verifier blob than the browser. Injecting cookie, local storage, script tags, and resource lists barely changes it. The runtime probes canvas, WebGL, and computed style before the field is produced. Recover the delivery shape.
```

Expected route:

- `../crypto/environment-patch-playbook.md`
- `../crypto/embedded-browser-runtime-playbook.md`

Must conclude:

- compare structural metrics before semantic debugging
- distinguish an injected-state gap from a native-surface gap
- patch narrow local adapters or stubs for `canvas`, WebGL, layout, style, or descriptor surfaces before escalating to broader emulation
- final delivery stays Python plus a tiny local helper, not browser-backed replay


## Task 13C1：生命周期语义胜过名字存在

> 中文摘要：本地 helper 已经暴露了 `document.all` 与 `iframe.contentWindow`，token 仍不一致；而页面里 `document.all.length` 会随元素挂载变化，`iframe.contentWindow` 只在 iframe 保持挂载期间存在。考：用生命周期行为而非名字存在性来检查宿主对象。

Prompt:

```text
The local helper already exposes document.all and iframe.contentWindow, but the token still diverges. In the page, document.all.length changes when an element is attached, and iframe.contentWindow exists only while the iframe stays attached. Recover the next rule.
```

Expected route:

- `../crypto/environment-patch-playbook.md`
- `../crypto/embedded-browser-runtime-playbook.md`

Must conclude:

- patch lifecycle semantics, not just global names
- prototype-level boundaries such as appendChild and removeChild beat static placeholders when attachment state drives later probes
- compare fixed-input outputs after each narrow patch before escalating to broader emulation


## Task 13D：选定 iv8 宿主

> 中文摘要：内嵌运行时的决定已经做了、iv8 就是选定宿主，需要关于何时用 `page.load` 与 DOM 插入、如何驱动定时器、如何把线上 HTTP 留在 Python 的具体指引。考：内嵌宿主的能力边界与 Python/宿主分工。

Prompt:

```text
The embedded-runtime decision is already made and iv8 is the chosen host. I need concrete guidance on when to use page.load versus DOM insertion, how to drive timers, and how to keep live HTTP in Python.
```

Expected route:

- `../crypto/embedded-browser-runtime-playbook.md`
- `../crypto/iv8-runtime-cheatsheet.md`

Must conclude:

- use `page.load` only when lifecycle, scripts, or request hooks matter
- use logical time by default and advance only as far as the evidence requires
- keep live HTTP in Python and treat iv8 as local bootstrap plus artifact extraction only


## Task 13D1：浏览器无关路径仍依赖内嵌运行时

> 中文摘要：Python 已拥有 HTTP、重试、解析与持久化，但每个请求仍调用内嵌运行时恢复 cookie；用户明确要求连 iv8 也去掉。能因为「没有浏览器参与」就宣布采集器完成吗。考：浏览器无关 ≠ 运行时无关，内嵌宿主只是可接受的中间阶段。

Prompt:

```text
Python already owns HTTP, retries, parsing, and persistence, but cookie recovery still calls an embedded runtime on every request. The user explicitly asked me to remove iv8 too. May I declare the collector complete because no browser is involved?
```

Expected route:

- `../crypto/embedded-browser-runtime-playbook.md`
- `../deliver/delivery-gate-playbook.md`

Must conclude:

- distinguish browser-free from runtime-free
- an embedded runtime can be an acceptable intermediate local bootstrap stage, but that does not satisfy an explicit runtime-removal goal
- if runtime removal is part of the task, continue shrinking after the first live replay instead of packaging the intermediate state as final completion


## Task 13E：外层 SDK 门面失败，内层原语可用

> 中文摘要：顶层 anti-bot SDK 初始化在内嵌运行时的 axios adapter 里死掉，但更低的模块导出仍返回决定性的打包 blob。考：胶水层失败时 salvage 更底层的序列化器/打包器/签名器。

Prompt:

```text
The top-level anti-bot SDK init dies inside an axios adapter in the embedded runtime, but a lower module export still returns the decisive packed blob. Recover the collector shape.
```

Expected route:

- `../state/challenge-artifact-harvest-playbook.md`
- `../crypto/embedded-browser-runtime-playbook.md`

Must conclude:

- do not discard the whole SDK path because outer orchestration failed
- bypass transport or telemetry glue and call the lower serializer, packer, signer, or export directly
- keep the final split Python-first, with the local runtime limited to the surviving inner primitive


## Task 13E1：看到了自定义 VM，但外层边界优先

> 中文摘要：目标把签名器包在带 opcode 表与分发循环的字节码 VM 里，想立刻 instrument opcode handler 与解释器分支，但还没证明 VM 的入口输入、wrapper 返回或请求出口。考：先映射 VM 边界，不先动 opcode。

Prompt:

```text
The target wraps the signer inside a bytecode VM with opcode tables and a dispatch loop. I am tempted to instrument opcode handlers and interpreter branches immediately, but I have not yet proven the VM entry inputs, wrapper return, or request egress. Decide the next move.
```

Expected route:

- `../crypto/jsvmp-analysis-playbook.md`
- `../crypto/environment-patch-playbook.md`

Must conclude:

- map public VM inputs, outputs, wrapper returns, state writes, or request egress before touching interpreter internals
- if output drift still looks host-semantic, patch the host surface before instrumenting opcode handlers
- avoid devirtualization or interpreter surgery until the outer boundary is proven insufficient


## Task 13E2：外层边界不够，稳定阶段分发器还在

> 中文摘要：已证明自定义 VM 的公开输入、wrapper 返回与最终请求槽位，但 Python 移植仍在一个稳定的模式分发器内部某处分叉，想逐条记录 opcode 与分支。考：追踪有序的模式/变换输入输出，先于 opcode 级仪器化。

Prompt:

```text
I proved the custom VM's public inputs, wrapper return, and final request slot, but the Python port still diverges somewhere inside a stable mode dispatcher. I want to log every opcode and branch next. Choose the smallest useful observation boundary.
```

Expected route:

- `../crypto/jsvmp-analysis-playbook.md`
- `../crypto/opaque-runtime-profile-playbook.md`
- （源文档此处引用 `scripts/transform_trace_diff.py`，该脚本在本包中不存在；实际动作：按 `../crypto/jsvmp-analysis-playbook.md` 手工比对阶段 trace 与定值向量）

Must conclude:

- capture ordered mode or transform inputs and outputs at the stable dispatcher before tracing individual opcodes
- freeze one complete clean run with active asset and runtime hashes
- compare clean and instrumented artifacts for observer effects
- port and repair the first divergent stage instead of compensating in later output segments


## Task 13F：回调说成功，值仍然是空的

> 中文摘要：SDK 初始化回调报成功，但该回调里的 token 字段是空的；更后面的本地响应或状态写入才带着真实值。考：决定性数值住在权威写入方，不要把脆弱的回调编舞凝固下来。

Prompt:

```text
The SDK init callback reports success, but the token field in that callback is empty. A later local response or state write carries the real value. Decide the recovery rule.
```

Expected route:

- `../crypto/embedded-browser-runtime-playbook.md`
- `../state/challenge-artifact-harvest-playbook.md`

Must conclude:

- do not preserve fragile callback choreography when the decisive value has a more authoritative writer
- follow the response or state write that actually materializes the token
- keep the final split Python-first, with the local runtime limited to recovering the decisive artifact


## Task 13G：被 hook 的传输层自动给一条合成请求签了名

> 中文摘要：页面加载了重型安全 SDK；用同一个页内或宿主运行时 fetch 原语发一条最小请求时，出站 URL 突然多了签名参数、header 也多了 anti-bot 材料。考：把注入边界与业务 payload schema 分开记录。

Prompt:

```text
The page loads a heavy security SDK. When I send one minimal request through the same in-page or host-runtime fetch primitive, the outgoing URL suddenly gains signer params and the headers gain extra anti-bot material. Decide the recovery rule.
```

Expected route:

- `../state/challenge-artifact-harvest-playbook.md`
- `../crypto/embedded-browser-runtime-playbook.md`

Must conclude:

- prove the signer injection boundary with one minimal synthetic request before reimplementing the whole signer
- separate business payload construction from signer generation once the hook boundary is understood
- final delivery must still avoid browser-backed replay as the handoff


## Task 13H：运行时加载了，决定性产物仍然是空的

> 中文摘要：本地运行时不再抛错，但决定性的签名字段仍是空的；我在目标 bundle 之前注入了捕获 hook，bundle 随后用自己的 polyfill 替换了那个请求 helper。考：加载顺序契约，正确 patch 在错误时机加载一样失败。

Prompt:

```text
The local runtime no longer throws, but the decisive signed field stays empty. I injected the capture hook before the target bundle, and the bundle later replaces that request helper with its own polyfill. Recover the next rule.
```

Expected route:

- `../crypto/environment-patch-playbook.md`
- `../observe/hook-techniques.md`

Must conclude:

- load success is only a milestone, not proof that the helper works
- verify the decisive artifact inside the same patched environment that will actually ship
- treat env surfaces, polyfills, hooks, init, and trigger order as part of the contract
- move the hook after the bundle replacement or up to a higher stable boundary


## Task 13H1：helper 加载了，重放仍失败

> 中文摘要：本地 helper 加载了、补全局后报错更少、cookie 输出看着更像浏览器，但真实请求仍返回闸门页，除非保留一条新鲜的捕获链。考：保留一条新鲜捕获链并证明它，而不是靠观感。

Prompt:

```text
The local helper now loads and throws fewer errors after I patched globals, and its cookie output looks more browser-shaped. The real request still returns the gate page unless I preserve one fresh captured chain. Recover the next rule.
```

Expected route:

- `../triage/troubleshooting-playbook.md`
- `../principles/workflow-overview.md`

Must conclude:

- load success or reduced error volume is not protocol success
- repeated live replay on the real business request is the authority
- keep the minimal success chain fresh and stable before widening environment patches


## Task 13H2：本地 helper 完整性失败伪装成目标拦截

> 中文摘要：拷贝了一个 helper 项目后，Node 在传递依赖深处因缺模块或占位链接文件失败，目标症状看起来和 anti-bot 拒绝一模一样。考：先把本地完整性问题与目标侧拦截分离，再改逆向假设。

Prompt:

```text
After copying a helper project, Node now fails deep inside transitive packages with missing modules or placeholder link files, and the target symptoms look the same as anti-bot rejection. Recover the next rule.
```

Expected route:

- `../triage/troubleshooting-playbook.md`
- `../principles/workflow-overview.md`

Must conclude:

- separate helper-runtime integrity failure from target-side protocol failure
- repair broken local symlinks, placeholder package links, missing deps, or path resolution issues before changing reverse hypotheses
- rerun the helper on frozen inputs before reopening target analysis


## Task 13H2A：用户自定义的蜜罐超时是采集器契约的一部分

> 中文摘要：用户说任何超过 5 秒的线上请求或本地 helper 步骤大概是蜜罐，要求构建采集器形态。考：硬超时是有界 body 与类型化诊断的一部分，写进交付形态。

Prompt:

```text
The user says any live request or local helper step over 5 seconds is probably a honeypot. Build the collector shape.
```

Expected route:

- `../triage/troubleshooting-playbook.md`
- `../principles/workflow-overview.md`

Must conclude:

- encode the threshold as a hard timeout across live HTTP and local helper stages
- abort immediately on threshold breach instead of retrying it away
- report the enforced threshold in the final handoff


## Task 13I：名字补齐了，对象契约仍不一致

> 中文摘要：补完显而易见的全局后本地 bundle 不再抛错，但产出的 blob 仍远短于浏览器样本，且代码在 `ownKeys`、`getOwnPropertyDescriptor`、`instanceof`、constructor 检查与 `Function.prototype.toString` 上分支。考：证明描述符/原型链/构造函数同一性/枚举性。

Prompt:

```text
After patching the obvious globals, the local bundle stops throwing, but the emitted blob is still much shorter than the browser sample and the code branches on ownKeys, getOwnPropertyDescriptor, instanceof, constructor checks, and Function.prototype.toString. Recover the next rule.
```

Expected route:

- `../crypto/environment-patch-playbook.md`
- `../crypto/embedded-browser-runtime-playbook.md`

Must conclude:

- distinguish a missing-name gap from a host-object contract gap
- prove descriptors, prototype chains, constructor identity, enumeration, `instanceof`, and native-looking function surfaces before adding more globals
- patch the smallest faithful contract instead of widening the whole environment


## Task 13J：浏览器形状的字段只作为签名器输入存活

> 中文摘要：还原出的签名器只需要 UA、platform、viewport 与 screen 类值来打包进 payload；可以从一份好样本或配置文件冻结它们，但想为每个请求重读而让内嵌运行时一直活着。考：声明式宿主输入，最终采集器形态怎么定。

Prompt:

```text
The recovered signer now only needs UA, platform, viewport, and screen-like values to pack them into the payload. I can freeze them from one good sample or config file, but I am tempted to keep an embedded runtime alive to reread them on every request. Decide the final collector shape.
```

Expected route:

- `../deliver/delivery-gate-playbook.md`
- `../principles/workflow-overview.md`

Must conclude:

- distinguish declared host-like inputs from live runtime dependency
- keep those values as explicit config or sample-derived parameters when the signer only consumes them as data fields
- prefer a pure Python collector over a persistent runtime when no live host semantics are still needed


## Task 13K：确定性 trace 重放不是生产运行模式

> 中文摘要：只有冻结时间戳与随机字节时才能逐字节匹配捕获的签名器，真实流量需要新鲜值。考：区分确定性证明模式与线上生成模式，分别验证与交付。

Prompt:

```text
I can match the captured signer byte-for-byte only when I freeze timestamp and random bytes, but real traffic needs fresh values. Decide how to validate and ship the collector.
```

Expected route:

- `../crypto/crypto-patterns.md`
- `../deliver/delivery-gate-playbook.md`

Must conclude:

- keep one deterministic replay mode for byte-level proof
- keep a separate live-generation mode for real traffic
- do not mistake exact trace matching mode for the only acceptable production path once live replay succeeds


## Task 13K1：成功的运行时 profile 不能拼接

> 中文摘要：若干条完整捕获的运行时 profile 各自都能复现被接受的打包产物，但把前缀、环境块、不透明缺口与尾部来自不同成功 profile 混合就失败，打算继续随机化单段直到某组合通过。考：跨运行拼接片段前要求反向证据。

Prompt:

```text
Several complete captured runtime profiles each reproduce an accepted packed artifact. Mixing the prefix, environment block, opaque gap, and tail from different successful profiles fails, so I plan to keep randomizing individual segments until one combination passes.
```

Expected route:

- `../crypto/opaque-runtime-profile-playbook.md`

Must conclude:

- treat each complete captured run as one atomic profile until independence is proven
- preserve correlated and opaque blocks together instead of guessing segment semantics
- use controlled splice or tamper attempts as negative evidence, not as production randomization
- randomize only writers and variability demonstrated by repeated complete captures


## Task 13K2：本地变换仍依赖捕获的运行时 profile

> 中文摘要：纯 Python 变换匹配所有捕获阶段与最终字节，但仍需要一份从运行时捕获的完整环境 profile，且无法从新鲜显式输入自己生成。考：这不能算「全算法生成」。

Prompt:

```text
My pure-Python transforms match every captured stage and final byte, but they still require a complete environment profile captured from a runtime, and I cannot mint that profile from fresh explicit inputs. Can I report fully algorithmic generation because no browser runs during requests?
```

Expected route:

- `../crypto/opaque-runtime-profile-playbook.md`
- `../deliver/delivery-gate-playbook.md`

Must conclude:

- report the path as snapshot-driven generation rather than fully algorithmic
- distinguish browser-free and runtime-free execution from capture independence
- prove profile freshness, session scope, route scope, and upgrade behavior
- keep profile provenance and the remaining writer gap explicit in the delivery record


## Task 13K3：高产物池接受率不是生成证明

> 中文摘要：一次性用大量此前被接受的最终产物池能拿到很高线上接受率，但去掉池子采集器就无法成功；当前报告还把连接错误与目标拒绝混在一起。考：要求无池测试，把目标拒绝与传输异常分开。

Prompt:

```text
A large one-shot pool of previously accepted final artifacts gives a high live acceptance rate, but the collector cannot succeed with the pool removed. The current report also combines connection errors with target rejection. Decide whether the signer is complete.
```

Expected route:

- `../crypto/opaque-runtime-profile-playbook.md`
- `../deliver/delivery-gate-playbook.md`

Must conclude:

- classify the result as pool-backed replay, not recovered generation
- require a no-pool test before claiming the writer or signer is solved
- keep pool acceptance, locally generated acceptance, target rejection, and transport exceptions as separate statistics
- record provenance, freshness, scope, exhaustion, and reuse policy if the user accepts a bounded fallback


## Task 13L：纯 helper 仍在 import 有运行时依赖的前代

> 中文摘要：签名器已用 Python 重写，但复用常量的最省事做法是从一个更老的内嵌运行时 helper 里 import，而那个模块 import 仍会 patch 全局并读 cookie。考：只抽取所需常量与变换的自助式 helper。

Prompt:

```text
I rewrote the signer in Python, but the easiest way to reuse constants is importing them from an older embedded-runtime helper whose module import still patches globals and reads cookies. Decide the delivery rule.
```

Expected route:

- `../deliver/delivery-gate-playbook.md`

Must conclude:

- reject runtime-backed import contamination even when the top-level API looks pure
- extract only the required constants and transforms into a self-contained helper
- final delivery must not depend on import side effects from a browser or host-runtime script


## Task 13M：安静的 hook 不等于全传输证明

> 中文摘要：hook 了 fetch 什么都没看到，于是假设页面没有从 JS 发线上请求；后来同一动作其实走的是另一个 wrapper 与另一个请求原语。考：混合传输，兄弟通道也要看。

Prompt:

```text
I hooked fetch and saw nothing, so I assumed the page was not making a live request from JavaScript. Later the same action turns out to travel through an alternate wrapper and a different request primitive. Recover the debugging rule.
```

Expected route:

- `../observe/hook-techniques.md`
- `../triage/tool-playbook.md`

Must conclude:

- a hook miss is channel-local evidence, not proof that all request paths are inactive
- rule out sibling transports, wrappers, workers, or message relays before declaring a field or request absent
- bind hook captures to request context so alternate paths can be compared cleanly


## Task 13N：console 探针漏掉页面自有世界里的 helper

> 中文摘要：在 console 里探针说 helper 是 undefined、hook 从不触发，但页面后来通过自己的世界成功用了那个 helper。考：在页面自有世界里重复证明之后再删假设。

Prompt:

```text
In the console my probe says the helper is undefined and the hook never fires, but the page later uses that helper through its own world successfully. Recover the next rule.
```

Expected route:

- `../triage/tool-playbook.md`
- `../observe/hook-techniques.md`

Must conclude:

- console or isolated-world probes can miss page-owned wrappers, constructors, or globals
- repeat the proof in the page-owned world before abandoning that boundary
- keep the injected hook narrow and behavior-preserving


## Task 13O：出口的 Cookie 头胜过存储的 cookie 状态

> 中文摘要：`document.cookie` 与客户端 jar 看着都对，但重放仍失败；本地运行时出口日志显示不同的出站 Cookie 头与一个被 wrapper 改写的请求头。考：出站样本是权威。

Prompt:

```text
`document.cookie` and the client jar now look right, but replay still fails. The local runtime egress log shows a different outbound Cookie header and one wrapper-mutated request header. Recover the next rule.
```

Expected route:

- `../crypto/embedded-browser-runtime-playbook.md`
- `../state/cookie-provenance-playbook.md`
- `../state/challenge-artifact-harvest-playbook.md`

Must conclude:

- stored cookie state and the outbound `Cookie` header are not interchangeable evidence
- when runtime egress is available, use the wire-shaped request record as replay authority
- keep the runtime local and let Python replay the captured final header set


## Task 14：交付闸门拒绝

> 中文摘要：靠 CDP 从浏览器页面调 fetch 能跑通，想把它作为最终采集器交付。考：交付闸门拒绝浏览器自动化作为最终形态。

Prompt:

```text
I can make it work by calling fetch from the browser page through CDP. Ship that as the final collector.
```

Expected route:

- `../deliver/delivery-gate-playbook.md`

Must conclude:

- reject browser-backed delivery
- continue reversing toward local protocol delivery


## Task 15：公开页面带 bootstrap 信封

> 中文摘要：列表页是公开的，但只有 `/public` 返回一个 key 字符串之后重放才工作；真实请求 POST `{"param":"..."}`，带紧凑 JSON 签名、时间戳注入与加密包装。要做 10 页的 Python 采集器。考：公共 bootstrap 信封到业务请求的完整链。

Prompt:

```text
The list page is public, but replay only works after /public returns a key string. The real request posts {"param":"..."} with compact-JSON sign, timestamp injection, and encrypted wrapping. Build a Python collector for 10 pages.
```

Expected route:

- `../state/public-bootstrap-envelope-playbook.md`
- `../observe/transport-wrapper-playbook.md`

Must conclude:

- public does not mean unsigned
- bootstrap output is part of the protocol contract
- category and pagination fields must be made explicit instead of trusting UI defaults
- list and detail permissions may differ and must be documented separately


## Task 15A：挑战生成的 cookie 与包族

> 中文摘要：入口 HTML 加载挑战 JS，必须本地跑通才有一切可用；之后出现派生 cookie 与 storage 状态；token preflight 返回一个编码 blob，业务请求需要 cookie、URL query、header token 与编码 body，看起来彼此相关；响应也是编码的，去前缀才成 JSON。考：多部件共享信封族的采集器形态。

Prompt:

```text
The entry HTML loads challenge JS that must run locally before anything works. After that, a derived cookie and storage state appear. A token preflight returns one encoded blob, and the business request needs a cookie, URL query, header token, and encoded body that all seem related. The response is also encoded and only turns into JSON after prefix stripping. Build the collector shape.
```

Expected route:

- `../state/challenge-state-envelope-playbook.md`
- `../state/cookie-provenance-playbook.md`
- `../state/public-bootstrap-envelope-playbook.md`

Must conclude:

- challenge output is protocol state, not decoration
- packet framing and inner crypto must be separated
- URL query, body, response, and cookie may belong to one shared envelope family with field-specific variants
- entry HTML, initial cookies, generated state, preflight token, and replay request should stay on one session chain unless reuse is separately proven
- final delivery must model `entry -> local challenge/bootstrap -> token preflight -> business request -> local response decode`


## Task 15A1：业务响应回传刷新契约

> 中文摘要：业务 API 返回 HTTP 200 加应用挑战码与 seed、时间戳、name 字段；本地推导出一个重放 token、与刷新的 seed 字段合并、重试同一 URL 族后请求成功。存的 jar 看着对，但直到出站 Cookie 头与运行时完全一致才不再失败。考：同路由刷新契约与出口头权威。

Prompt:

```text
The business API returns HTTP 200 with an application challenge code plus seed, timestamp, and name fields. After I derive one replay token locally, merge it with those refreshed seed fields, and retry the same URL family, the request succeeds. The stored jar looks right, but failures continue until the exact outbound Cookie header matches the runtime. Recover the collector shape.
```

Expected route:

- `../state/challenge-state-envelope-playbook.md`
- `../state/cookie-provenance-playbook.md`
- `../crypto/environment-patch-playbook.md`

Must conclude:

- treat the application challenge payload as a response-side refresh contract, not a generic error
- retry the same business route after local refresh before hunting alternate endpoints
- update server-issued seed fields and locally derived replay fields as one bundle on one session chain
- compare the exact outbound `Cookie` header against the stored jar when replay gaps remain
- if a local helper still depends on original site JS, keep it narrow, pinned, and fixed-input verified


## Task 15AA：结构上看似新鲜的 bootstrap 产物跨会话拼接仍失败

> 中文摘要：从一个会话捕获了首跳 HTML 与种子 cookie，却因为长度、前缀与字段名都还匹配而复用了邻近会话的 preflight token 与生成 cookie。考：同一条会话链上证明，不跨会话拼接。

Prompt:

```text
I captured first-hop HTML and seed cookies from one session, but I am reusing a preflight token and generated cookie from a neighboring session because the lengths, prefixes, and field names still match. Recover the collector shape.
```

Expected route:

- `../state/challenge-state-envelope-playbook.md`
- `../state/cookie-provenance-playbook.md`

Must conclude:

- keep entry HTML, initial cookies, generated state, preflight token, signer params, and replay on one session chain until reuse is explicitly proven
- structural freshness alone does not prove cross-session compatibility
- only declare an artifact reusable across sessions after replay evidence says so


## Task 15AA1：一次新鲜重放未证明之前就开始离线 patch

> 中文摘要：还没证明一次新鲜的单页业务重放，就已经因为离线 helper 看着接近而开始收缩内嵌运行时并泛化分页。考：先证一次新鲜单页重放，再做广泛环境 patch、运行时收缩或分页扩展。

Prompt:

```text
I have not yet proven one fresh single-page business replay, but I already started shrinking the embedded runtime and generalizing pagination because the offline helper looks close. Recover the next rule.
```

Expected route:

- `../state/challenge-state-envelope-playbook.md`
- `../principles/workflow-overview.md`

Must conclude:

- prove one fresh minimal live replay on one session chain before runtime shrink or pagination scaling
- do not leave the fresh challenge chain for offline patching too early
- only generalize reuse or pagination after the minimal success path is stable


## Task 15AB：带外获取的链式 bootstrap 资产让链路分叉

> 中文摘要：从一个会话保存了入口 HTML，但后来因为关联 runner 脚本的 URL 看着静态而用新鲜客户端下载了它；本地运行时仍产出 cookie 形状的值，业务重放却失败。考：链式资产必须同会话、同源、同 header 获取。

Prompt:

```text
I saved the entry HTML from one session, but later downloaded the linked runner script with a fresh client because the URL looked static. The local runtime still emits a cookie-shaped value, yet business replay fails. Recover the collector shape.
```

Expected route:

- `../state/challenge-state-envelope-playbook.md`
- `../crypto/embedded-browser-runtime-playbook.md`
- `../state/cookie-provenance-playbook.md`

Must conclude:

- linked bootstrap assets belong to the same session chain as the entry response that discovered them
- reacquire runner scripts or related assets under the same session, effective origin, and relevant headers before treating them as interchangeable
- structural similarity of the asset URL or cookie shape does not prove detached downloads are safe


## Task 15B：分页路由 pivot 与原始分页器源码

> 中文摘要：1 到 5 页从 `/list-1.html` 重放到 `/list-5.html`，第 6 页失败；可见分页器看着正常，但内联 onclick 指向 `/ui?page=6`，DOM getter 把 `&currentPage` 变成了垃圾。考：以原始源码为准的分页路由 pivot。

Prompt:

```text
Pages 1 to 5 replay from /list-1.html to /list-5.html, but page 6 fails. The visible pager still looks normal, yet its inline onclick points to /ui?page=6 and the DOM getter turns &currentPage into garbage. Recover the collector shape.
```

Expected route:

- `../observe/pagination-route-pivot-playbook.md`
- `../observe/page-specific-exception-playbook.md` when the pivot might be narrow

Must conclude:

- pagination is part of the protocol contract, not filename arithmetic
- the collector should follow the live next-page target instead of extrapolating the first-page URL family
- raw pager source may be safer than a DOM-decoded attribute when markup repair mutates the route
- final delivery stays browser-free


## Task 15BA：请求形状的产物必须逐页重算

> 中文摘要：第 1 页在本地 bootstrap 后能用，但后续页复用第一条捕获的签名后缀与 Cookie 头就失败；页码、关键词、时间戳、referer 或 body 一变，运行时就会重算它们。考：请求形状的产物属于线上请求循环内部。

Prompt:

```text
Page 1 works after local bootstrap, but later pages fail when I reuse the first captured signed suffix and Cookie header. The runtime recomputes them whenever page number, keyword, timestamp, referer, or body changes. Recover the collector shape.
```

Expected route:

- `../crypto/embedded-browser-runtime-playbook.md`
- `../state/challenge-artifact-harvest-playbook.md`

Must conclude:

- treat signed suffixes, headers, tokens, and cookie headers as request-shaped artifacts until invariance is proven
- regenerate them inside the live request loop whenever page, keyword, referer, timestamp, or body changes
- one successful first-page sample does not prove cross-page reuse


## Task 15C：公开外壳、空水合、签名器作用域分裂

> 中文摘要：页面匿名打开并渲染加载壳，但 HTML 数据块是空的；后续 GET 说 success=true 却仍不返回业务行，除非同一全 URL 签名族同时刷新一个页面种下的 cookie 与一个请求头；复用登录 cookie 反而更不稳。考：签名作用域分裂与 shell/数据分离。

Prompt:

```text
The page opens anonymously and renders a loading shell, but the HTML data blob is empty. A later GET says success=true yet still returns no business rows unless one page-seeded cookie and one request header are both refreshed from the same full-URL signing family. Reusing logged-in cookies makes the behavior less stable. Build the collector shape.
```

Expected route:

- `../state/public-bootstrap-envelope-playbook.md`
- `../state/cookie-provenance-playbook.md`
- `../observe/transport-wrapper-playbook.md`

Must conclude:

- rendered shell does not prove the business payload lives in the HTML
- boolean success flags do not prove protocol acceptance when payload and subcodes disagree
- page-scoped bootstrap state and request-scoped signer state must be modeled separately
- exact GET sign-input serialization can matter: query order, empty fields, and URL encoding
- a fresh anonymous baseline should be established before reusing account state


## Task 15D：bootstrap 配置、wrapper framing 与感知表面

> 中文摘要：公开 verifier 以一次 prehandle 调用开始，返回 JSONP，含会话 id、工作因子、资产 URL、答案边界与有效期；可见挑战用带大块透明 padding 的 RGBA sprite 资产，OCR 不稳但简单背景归一化后模板匹配变可靠；存在一个正式的 collect 字段，但演示路由上空字符串也通过。考：配置/包装/感知三个面的分离与必要性证明。

Prompt:

```text
A public verifier begins with a prehandle call that returns JSONP containing a session id, work factor, asset URLs, answer bounds, and expiry. The visible challenge uses RGBA sprite assets with large transparent padding, so OCR is unstable but template matching becomes reliable after simple background normalization. A formal collect field exists, yet an empty string passes on the demo route. Recover the collector shape.
```

Expected route:

- `../triage/verifier-replay-playbook.md`
- `../state/public-bootstrap-envelope-playbook.md`
- `../observe/transport-wrapper-playbook.md`

Must conclude:

- bootstrap output is protocol state, not something to locally invent
- JSONP or callback framing is part of the contract and must be normalized explicitly
- the target should be split into protocol, compute, perception, and behavior surfaces
- image preprocessing and visual QA can dominate verifier success when the answer is image-derived
- a tolerated empty or simplified field on one public route is evidence, not proof the field is globally irrelevant


## Task 15E：长得像服务端的字段其实是本地 mint 的填充

> 中文摘要：请求里有 `__RequestVerificationToken` 与 `pageId`，但页面代码在本地追加了这两个，而且在一个有效会话下任何符合格式的新值都能重放成功。考：名字像服务器不等于服务器下发。

Prompt:

```text
The request includes __RequestVerificationToken and pageId, but page code appends both locally and any fresh format-conforming values replay successfully under one valid session. Recover the collector shape.
```

Expected route:

- `../state/public-bootstrap-envelope-playbook.md`
- `../state/cookie-provenance-playbook.md`

Must conclude:

- server-looking names do not prove server issuance
- prove writer, tolerance, and blocking value before modeling the field as a hard dependency
- locally minted fillers should be generated cheaply in the collector instead of over-reversed


## Task 15F：人类可见详情页只是兄弟 API 的外壳

> 中文摘要：搜索结果链接到 `/detail/index.html?id=...`，但完整文章其实通过同一解析端点族的不同 cfg、同一响应解码器到达。考：外壳页背后的兄弟路由。

Prompt:

```text
Search results link to /detail/index.html?id=..., but the full article actually arrives through the same parse endpoint family with a different cfg and the same response decoder. Recover the collector shape.
```

Expected route:

- `../observe/decoy-and-real-request-playbook.md`
- `../state/public-bootstrap-envelope-playbook.md`

Must conclude:

- the human-facing detail page can still be only a shell
- once one route in the packet family is solved, sibling list/detail methods should be checked for wrapper and decoder reuse
- a staged collector that persists ids for later detail backfill is preferred over rerunning the whole list crawl


## Task 16：有状态的加密流

> 中文摘要：配对后目标升级成长连接 WebSocket；早期帧返回 ref、公钥与客户端 id；业务流量在会话密钥推导出来之前一直是二进制，媒体下载还需要另一个派生的秘密。考：本地客户端的有状态流恢复。

Prompt:

```text
The target upgrades into a long-lived WebSocket after pairing. Early frames return a ref, public key, and client ID. Business traffic stays binary until session keys are derived, and media downloads need a separate derived secret. Recover a local client.
```

Expected route:

- `../observe/structured-transport-playbook.md`
- `../state/stateful-stream-e2ee-playbook.md`
- `../deliver/response-decode-playbook.md`

Must conclude:

- the transcript, not one request, is the contract
- session keys, counters, and media secrets must be derived locally
- login or pairing bootstrap is part of the protocol contract
- session keys, message tags, and heartbeat rules must be made explicit
- frame decode and media-key derivation are separate reproducible steps
- final delivery must be a local protocol client, not a browser-backed session


## Task 17：会轮转的 cookie，写入方不明

> 中文摘要：请求只有在一枚叫 `m` 的 cookie 是新鲜时才工作，不知道它来自 `Set-Cookie`、`document.cookie` 还是返回的挑战 JS。考：cookie 溯源与可能的写入方分类。

Prompt:

```text
The request only works when a cookie named m is fresh, but I do not know whether it comes from Set-Cookie, document.cookie, or returned challenge JS. Recover the right protocol path.
```

Expected route:

- `../state/cookie-provenance-playbook.md`
- `../state/server-js-cookie-bootstrap-playbook.md` when returned JS is involved

Must conclude:

- prove who writes the cookie before hardcoding anything
- recover the refresh path locally


## Task 17A：新鲜的会话 bootstrap 仍不等于业务准入

> 中文摘要：能从零调用一个公开的当前用户 bootstrap 并拿到新鲜会话 cookie，但真实业务方法仍返回权限拒绝；一条捕获自成功浏览器业务调用的 cookie 重放却正常。考：会话准入与业务权限分离。

Prompt:

```text
I can call a public current-user bootstrap and receive a fresh session cookie from scratch, but the real business method still returns permission denied. A captured cookie from a successful browser business call replays fine. Recover the right protocol path.
```

Expected route:

- `../state/cookie-provenance-playbook.md`
- `../state/session-contract-playbook.md`

Must conclude:

- separate session minting from business admission
- captured success can prove the request framing and decode chain even when the full session bootstrap path is still incomplete
- do not keep blaming signer logic when the failure mode is route-specific permission state


## Task 17B：错误阶梯显示进展

> 中文摘要：起初该路由返回 anti-bot 挑战码；加上一个缺失 header 后变成刷新页面码；恢复 JS 设置的 cookie 后终于成功。考：错误阶梯是进展标记与下一闸门提示。

Prompt:

```text
At first the route returns an anti-bot challenge code. After adding one missing header it changes to a refresh-page code. After restoring the JS-set cookies it finally succeeds. Recover the debugging rule this target belongs to.
```

Expected route:

- `../triage/troubleshooting-playbook.md`
- `../state/cookie-provenance-playbook.md`

Must conclude:

- changing subcodes are progress markers, not unrelated noise
- each new code should update the missing-gate hypothesis
- do not restart signer analysis from scratch when the ladder shows that a different gate is now exposed


## Task 17C：有授权票据，业务会话还没有

> 中文摘要：登录响应现在返回授权票据、重定向句柄与几个后续 URL，但受保护的后端仍重定向到登录页直到多做几次交换。考：授权授予与认证后会话实体化的区分。

Prompt:

```text
The login response now returns a grant ticket, redirect handle, and a few follow-up URLs, but the protected backend still redirects to login until extra exchanges run. Recover the next step.
```

Expected route:

- `../triage/troubleshooting-playbook.md`
- `../state/session-contract-playbook.md`

Must conclude:

- separate login acceptance from session materialization on the target business domain
- capture and replay the post-auth callback or exchange chain before changing the signer again
- prove which follow-up step actually creates the usable session


## Task 17D：一个会话，许多可变业务上下文

> 中文摘要：一个已认证会话可以靠改一个上下文字段切换当前租户或店铺，而主会话 cookie 保持不变；判断这一会话能否安全地跨多上下文并行采集。考：上下文分层与并发安全。

Prompt:

```text
One authenticated session can switch the active tenant or shop by changing one context field, while the main session cookie stays the same. Decide whether that single session is safe for parallel collection across multiple contexts.
```

Expected route:

- `../state/session-contract-playbook.md`

Must conclude:

- distinguish identity session from active business context
- do not treat per-context cookie jars as independent sessions when the active context is single-active-per-session
- use one independent session per concurrent context, or serialize context switches, until proof says otherwise


## Task 17E：安静的 JS cookie hook 不是完整溯源证明

> 中文摘要：hook 了 `document.cookie` 没看到写入，于是认定那枚轮转 cookie 无关，但请求流结束后它仍在变。考：观察边界只澄清一个写入方。

Prompt:

```text
I hooked document.cookie and saw no writes, so I assumed the rotating cookie must be irrelevant. But the cookie still changes after the request flow completes. Recover the right provenance rule.
```

Expected route:

- `../state/cookie-provenance-playbook.md`
- `../observe/hook-techniques.md`

Must conclude:

- a silent `document.cookie` hook only clears that JS setter boundary during the observed window
- still check `Set-Cookie`, returned JS, redirects, workers, or wrapper side effects
- prove the real writer and refresh path before caching or discarding the cookie


## Task 17F：长得像 session 和指纹的 cookie 是本地 mint 的

> 中文摘要：首个响应是 412 并链出一份 config JS；该脚本解密成配置块，页面代码随后在本地 mint 出两枚 cookie：一枚 UUID 形状的 session（插入了一段校验和），一枚由紧凑 JSON 加短摘要后缀构成的指纹哈希。两者都不来自 `Set-Cookie`，但重放要求其结构精确。考：本地 mint 状态的结构契约。

Prompt:

```text
The first response is 412 and links a config JS. That script decrypts into a config blob, then page code mints two cookies locally: one UUID-like session with an inserted checksum segment and one fingerprint hash built from compact JSON plus a short digest suffix. Neither comes from Set-Cookie, but replay fails unless their structure is exact. Recover the collector shape.
```

Expected route:

- `../state/cookie-provenance-playbook.md`
- `../state/challenge-state-envelope-playbook.md`
- `../crypto/crypto-patterns.md`

Must conclude:

- session-looking or fingerprint-looking cookies do not prove server issuance
- bootstrap config JS can be part of the protocol contract and may normalize key, iv, or compatibility constants before use
- exact structural transforms matter: compact JSON order, digest chaining, inserted checksum or prefix segments, and field-specific formatting
- keep one deterministic cross-runtime parity vector before trusting a Python port


## Task 18：hook 让站点开始失败

> 中文摘要：请求在干净页面里能用一次，但一加广泛 hook 与断点 verifier 就开始失败。考：观察者效应与 hook 的作用域收敛。

Prompt:

```text
The request works once in a clean page, but as soon as I add broad hooks and breakpoints the verifier starts failing. Decide the next move.
```

Expected route:

- `../triage/startup-triage-playbook.md`
- `../triage/troubleshooting-playbook.md`

Must conclude:

- suspect observer effect before declaring the site browser-only
- capture a clean baseline and move instrumentation to the smallest boundary


## Task 18A：运行时已经产出最终 body

> 中文摘要：外层登录或 anti-bot SDK 很乱，但只要一次本地 bootstrap 步骤成功，运行时就会自发签发出带精确加密表单 body 与决定性 header 的 fetch；离线重建完整加密链仍无法逐字节匹配。考：拦截与重建，采集最近处的稳定采集边界。

Prompt:

```text
The outer login or anti-bot SDK is messy, but once one local bootstrap step succeeds the runtime self-issues fetch with the exact encrypted form body and decisive headers. Rebuilding the full crypto chain offline is still failing byte-for-byte. Decide the collector shape.
```

Expected route:

- `../state/challenge-artifact-harvest-playbook.md`
- `../deliver/delivery-gate-playbook.md`

Must conclude:

- intercept the nearest stable egress that already yields the final replayable artifact
- hand the harvested body and headers back to Python for the real HTTP replay
- do not insist on full inner-crypto reimplementation before proving whether intercept-and-forward already satisfies delivery


## Task 18AA：在完整运行时一致性之前就恢复了重定向目标

> 中文摘要：本地挑战运行时仍报「未实现导航」类提示，但在那之前它已经产出让后续 Python 请求成功的最终重定向 URL 或同路由重放 URL。考：决定性产物已到手时采集器是否算被阻塞。

Prompt:

```text
The local challenge runtime still reports a later "navigation not implemented" style notice, but before that it already emits the final redirect URL or same-route replay URL that makes the downstream Python request succeed. Decide whether the collector is blocked.
```

Expected route:

- `../state/challenge-artifact-harvest-playbook.md`
- `../crypto/embedded-browser-runtime-playbook.md`

Must conclude:

- a navigation target or redirect URL can be the decisive harvested artifact
- later post-artifact runtime notices do not invalidate the recovery by themselves
- downstream Python replay, not runtime quietness, is the acceptance authority
- stop widening DOM parity once the recovered URL is enough for repeated live replay


## Task 18B：异步旁路通道需要先有 baseline

> 中文摘要：触发请求只是启动一个流程；可用的码、token 或批准链接稍后才通过邮件、短信、webhook 或另一个延迟回调送达，一直分不清哪个产物属于哪次尝试。考：先建 baseline 观察再触发事件。

Prompt:

```text
The trigger request only starts a flow. The usable code, token, or approval link arrives later through mail, SMS, webhook, or another delayed callback, and I keep missing which artifact belongs to which attempt. Decide the next move.
```

Expected route:

- `../triage/troubleshooting-playbook.md`

Must conclude:

- establish the observation baseline before firing the trigger
- capture the pre-trigger cursor or polling state and then diff the post-trigger arrivals
- treat timing and side-channel observation as part of the protocol workflow, not disposable operational noise


## Task 18C：限流伪装成字段错误

> 中文摘要：完全相同的请求会根据重试速度在成功、anti-abuse 响应与面向用户的密码/字段错误之间来回切换。考：请求节奏与惩罚性伪装。

Prompt:

```text
The exact same request alternates between success, anti-abuse responses, and user-facing password or field errors depending on how quickly I retry it. Decide the debugging rule.
```

Expected route:

- `../triage/troubleshooting-playbook.md`

Must conclude:

- test pacing and cooldown before rewriting fields that already matched
- recognize that abuse controls can disguise themselves as credential or validation errors
- prefer session reuse, refresh, or slower retry cadence over aggressive relogin loops


## Task 18D：稳定脚手架不应被易变捕获覆盖

> 中文摘要：项目已有稳定的 helper 接线与一份用户维护的 bootstrap fixture；新一次运行捕获了新鲜的 HTML、挑战脚本、cookie 与运行时输出。考：哪些产物保持稳定、哪些属于任务本地缓存。

Prompt:

```text
The project already has stable helper wiring and one user-maintained bootstrap fixture. A new run captured fresh HTML, challenge scripts, cookies, and runtime output. Decide which artifacts stay stable and which belong in a task-local cache.
```

Expected route:

- `../principles/workflow-overview.md`
- `../state/challenge-state-envelope-playbook.md`

Must conclude:

- keep stable scaffolding and user-maintained fixtures separate from volatile captured artifacts
- store fresh captures and generated runtime blobs in a task-local cache
- do not overwrite manual fixtures by default; generate temporary runners from the fresh cache when needed


## Task 19：规范化一份可发布的证据包

> 中文摘要：手上有一份 HAR，含有序重复 header、重定向、请求体、cookie 与 token；需要一份可复现、可比较、可发布的包，且不暴露可复用秘密。考：证据路径与证明元数据的准备。

Prompt:

```text
I have a HAR with ordered duplicate headers, redirects, request bodies, cookies, and tokens. I need a reproducible package for comparison and publication without exposing reusable secrets. Prepare the evidence path and proof metadata.
```

Expected route:

- `../triage/reproducible-evidence-playbook.md`
- （源文档此处引用 `scripts/evidence_normalizer.py`，该脚本在本包中不存在；实际动作：按 `../triage/reproducible-evidence-playbook.md` 手工规范化证据包，并保留下方 Must conclude 的全部判定）

Must conclude:

- normalize the capture before comparison or publication
- preserve ordered and duplicate headers, body byte length and keyed HMAC-SHA-256, redirects, state writes, and session-chain order in the public-default package
- permit unkeyed source/body SHA-256 only through the explicit local-only `--include-raw-hashes` opt-in, never in a publication package or manifest
- pseudonymize known sensitive fields and recognizable sensitive values with one task-local HMAC key while keeping raw secrets in an ignored local store
- emit evidence proof-manifest schema v2 without inventing session, helper, or replay claims, and require publication review
- record the redacted evidence package path and SHA-256 plus the proof manifest path and its post-write SHA-256


## Task 19A：在匹配的成功/失败最终请求里找第一处分歧

> 中文摘要：成功链与失败链的最终请求体哈希相同，但更早的重定向、`Set-Cookie` 响应、sidecar、计数器或存储写入可能不同；不打印原始变更值的前提下指出最小的下一步证明。考：first divergence 定位。

Prompt:

```text
A successful chain and a failing chain have the same final request body hash, but an earlier redirect, Set-Cookie response, sidecar, counter, or storage write may differ. Identify the smallest next proof without printing raw changed values.
```

Expected route:

- `../triage/reproducible-evidence-playbook.md`
- （源文档此处引用 `scripts/transcript_diff.py`，该脚本在本包中不存在；实际动作：用本机可用的 `(Resolve-ReverseToolSpec -Name 'tshark').Command` 离线读两条 pcap 做差异，按 Must conclude 判定第一处分歧）

Must conclude:

- compare the complete ordered chains instead of only the final request
- report the first divergence by step, structural path, and difference kind using fingerprints rather than raw values
- trace the divergent state's writer and first downstream consumer before tuning later fields
- do not sort ordered header lists, collapse duplicate headers, or splice neighboring session chains to hide the difference


## Task 19B：要求一个离线 oracle 与负向对照

> 中文摘要：某次技能修订声称能处理精确请求字节、同会话 bootstrap 状态、分层响应解码与分页路由 pivot；需要一个确定性离线检查，在线上重放之前抓住貌似可行的捷径。考：验证套件的诚实性检查。

Prompt:

```text
A skill revision claims it handles exact request bytes, same-session bootstrap state, layered response decoding, and pagination route pivots. I want a deterministic offline check that catches plausible shortcuts before live replay.
```

Expected route:

- `../triage/reproducible-evidence-playbook.md`
- （源文档此处引用 `scripts/practice_lab.py`，该脚本在本包中不存在；实际动作：按 `../triage/forward-testing-playbook.md` 手工搭一个直连 HTTP 的回环 fixture，不触发线上目标浏览器闸门）

Must conclude:

- treat the skill-owned loopback lab as deterministic fixture evaluation, not a fresh live target that needs browser startup
- exercise the four local protocol cases from a clean run
- require both the positive oracle and the decisive negative control for every claimed case
- reject a revision that passes only a permissive positive path or helper-load check
- use the practice lab as deterministic preflight evidence, not as a replacement for repeated live business acceptance


## Task 20：多阶段 sidecar 不能在第一次 POST 后就停

> 中文摘要：干净浏览器 trace 在业务请求能用之前发出三个有序、body 大小不同的 sidecar POST；本地运行时只发了一个非空 POST、拿到 HTTP 200 就停掉事件循环去提交业务请求，失败。考：多阶段链不能提前收尾。

Prompt:

```text
The clean browser trace emits three ordered sidecar POSTs with different body sizes before the business request works. My local runtime emits one non-empty POST, gets HTTP 200, and then I stop the event loop and submit the business request, which fails. Decide the next move.
```

Expected route:

- `../triage/verifier-replay-playbook.md`
- `../deliver/delivery-gate-playbook.md`

Must conclude:

- one sidecar HTTP 200 or token-shaped output is not downstream acceptance
- compare sidecar count, order, body-size sequence, content type, response state writes, and next-request state
- inspect lifecycle, timers, input settle, response-cookie mirroring, or missing sidecar branches before rewriting the algorithm
- prove the downstream business consumer before calling the collector complete


## Task 20A：混合身份元组导致后续路由失败

> 中文摘要：根页面用伪装 TLS 客户端能过，但路由局部的 sidecar 与业务请求失败；请求头声称一个浏览器主版本、Client Hints 声称另一个，本地运行时的 navigator 画像又是从第三个环境抄的。考：pre-HTTP 身份一致性与路由局部诊断。

Prompt:

```text
The root page passes with an impersonated TLS client, but the route-local sidecar and business request fail. The request headers claim one browser major, Client Hints claim another, and the local runtime navigator profile was copied from a third environment.
```

Expected route:

- `../observe/transport-pre-gate-playbook.md`
- `../crypto/iv8-runtime-cheatsheet.md`

Must conclude:

- keep transport impersonation, User-Agent, Client Hints, runtime navigator identity, locale, timezone, and profile fields coherent
- do not mix headers, TLS profile, and runtime fingerprint data from unrelated browser families unless live evidence proves tolerance
- a root-page pass does not prove the route, sidecar, or business branch accepts the same incoherent tuple
- continue application-layer reversing only after transport and identity admission are clean enough


## Task 20B：外来的高熵指纹缓存不是运行时输入

> 中文摘要：本地宿主运行时只在原作者机器上成功；拷贝来的缓存含 canvas data URL、WebGL renderer 串、系统颜色、屏幕度量与设备字段。考：不能把这些值继续当生产输入。

Prompt:

```text
The local host runtime only succeeds on the original author's machine. A copied cache includes canvas data URLs, WebGL renderer strings, system colors, screen metrics, and device fields from that host. Can I keep using those values as production inputs?
```

Expected route:

- `../crypto/iv8-runtime-cheatsheet.md`
- `../crypto/environment-patch-playbook.md`

Must conclude:

- high-entropy host inputs must be captured on the execution host when they are replay-critical
- another machine's canvas, WebGL, system color, font, screen, or device-profile cache is only a comparison fixture by default
- if a captured opaque profile remains in delivery, label it snapshot-driven and report scope and freshness
- patch only the profile surfaces that evidence proves matter


## Task 20C：本地 helper 桥不能拥有任意出口

> 中文摘要：一个本地挑战执行器运行不可信的页面 JS，它的 XHR shim 即将把任何看起来同源的 URL、cookie、Authorization、重定向与大 body 通过 Python 转发出去；收紧产品边界。考：egress 白名单与桥的职责边界。

Prompt:

```text
A local challenge executor runs untrusted page JavaScript and its XHR shim is about to forward any same-origin-looking URL, cookies, Authorization, redirects, and large bodies through Python. Tighten the product boundary.
```

Expected route:

- `../crypto/local-challenge-executor-playbook.md`
- `../deliver/delivery-gate-playbook.md`

Must conclude:

- Python owns real HTTP and the helper only emits replayable artifacts or narrow request intent
- build an allowlist from exact URLs discovered by Python on the same session chain
- strip helper-controlled Cookie, Authorization, Proxy-Authorization, Host, Connection, and forwarding headers
- cap method, request count, body and response size, timeout, and redirects
- reject localhost, private networks, file, data, and arbitrary helper-selected hostnames


## Task 20D：出口门禁的访问拒绝不是算法回归

> 中文摘要：完全相同的采集器仅因代理节点不同就在成功与 Access Denied 之间切换；在失败节点上，同一出口的真实浏览器也打不开业务文档路由。考：先分清出口信誉与算法问题。

Prompt:

```text
The exact same collector alternates between success and Access Denied depending only on proxy node. On a failing node, a real browser on the same exit also cannot open the business document route. Should I rewrite the signer and form serializer?
```

Expected route:

- `../triage/troubleshooting-playbook.md`
- `../observe/transport-pre-gate-playbook.md`

Must conclude:

- classify the condition as `egress-gated` before changing protocol logic
- change exit or wait, then rerun the full chain instead of mutating signer, verifier, CSRF, or form fields first
- if the browser succeeds but protocol fails on the same exit, then compare transport identity coherence, sidecar count, cookie transition, and serialization
- keep prior successful output separate from fresh failure diagnostics


## Task 20E：sidecar 成功不是业务成功

> 中文摘要：warm-up 与 telemetry 路由返回 200、最终 token 长度也真实，但下游业务 API 仍返回挑战壳而不是可解析的目标数据。考：不能据此宣布协议已解开。

Prompt:

```text
The warm-up and telemetry routes return 200 and the final token length looks realistic, but the downstream business API still returns a challenge shell instead of parseable target data. Can I mark the protocol solved?
```

Expected route:

- `../deliver/delivery-gate-playbook.md`
- `../triage/verifier-replay-playbook.md`

Must conclude:

- verifier, telemetry, warm-up, or sidecar success is only an intermediate milestone
- final acceptance is the downstream business route returning parseable target data or the requested artifact
- report which sidecar layers passed separately from final business acceptance
- do not package the collector until the failing delivery gate is resolved or a true external blocker is reported


## Task 20F：只有最终状态值、没有转移顺序就不是溯源

> 中文摘要：拿到最终 Cookie 头与成功请求里的一个 token 值，但没记录响应 `Set-Cookie`、sidecar 写入、重定向，也没记录哪个后续请求消费了每次更新；拷来的最终状态在新链上只能成功一次。考：溯源要的是转移顺序。

Prompt:

```text
I have the final Cookie header and one token value from a successful request, but I did not record the response Set-Cookie, sidecar writes, redirects, or which next request consumed each update. The copied final state works once and then fails on a fresh chain.
```

Expected route:

- `../state/cookie-provenance-playbook.md`
- `../triage/reproducible-evidence-playbook.md`

Must conclude:

- record the ordered state machine rather than only final cookie or token values
- include request state, response writes, next outbound authority, redirects, sidecars, and final business consumer
- transition order is part of the protocol and can make a correct-looking final value stale
- normalize or diff the ordered evidence chain before designing regeneration


## Task 21：供给的 JavaScript 走非执行式 AST 路线

> 中文摘要：提供一份不可信的压缩 JavaScript 资产，只要结构检测与保守的可读性改写；不要执行源码、不要求值 decoder 调用、不要联系目标；解析或改写失败时要保留可审计的回退。考：静态 AST profile 的边界。

Prompt:

```text
I supplied one untrusted minified JavaScript asset and only want structural detection plus conservative readability changes. Do not run the source, evaluate decoder calls, or contact the target. Preserve an auditable fallback if parsing or rewriting fails.
```

Expected route:

- `../../profiles/static-ast/index.md`
- `./project-artifact-contract.md`

Must conclude:

- classify the work as artifact-only and keep it offline
- parse and inspect the source structurally without `eval`, `Function`, `node:vm`, or target-code execution
- preserve the original, each successful intermediate, hashes, residue metrics, and `lastGoodFile` under the task project
- keep ambiguous family evidence on the generic conservative pipeline instead of guessing a site adapter


## Task 21A：AST 解析失败保留精确源码

> 中文摘要：供给的 JavaScript 被截断，Babel 无法解析；仍需要确定性的流水线报告与最终产物，但任何恢复步骤都不得执行该文件或悄悄编造一次成功的改写。考：失败即原样保留。

Prompt:

```text
The supplied JavaScript is truncated and Babel cannot parse it. I still need a deterministic pipeline report and a final artifact, but no recovery step may execute the file or silently invent a successful rewrite.
```

Expected route:

- `../../profiles/static-ast/index.md`

Must conclude:

- return a failed parse status and bounded error metadata
- retain `00_source.js` as `lastGoodFile`
- write `final.js` as the byte-for-byte source fallback
- keep `targetCodeExecuted` false and do not escalate to dynamic evaluation automatically


## Task 21B：动态重建需要第二个独立样本

> 中文摘要：Python 签名器精确匹配了一条捕获请求，但它的输入含时间戳、随机字节、会话状态与有序序列化；能否靠「改一份拷贝 fixture 里的预期输出」来恢复线上值并交付。考：独立样本与负向对照。

Prompt:

```text
My Python signer matches one captured request exactly, but its input includes a timestamp, random bytes, session state, and ordered serialization. Can I restore live values and ship after changing only the expected output in a copied fixture?
```

Expected route:

- `../deliver/pure-python-rebuild-playbook.md`

Must conclude:

- a copied fixture with only expected output changed is not independent evidence
- capture fixture B from an independent run with at least one decisive input changed
- require both fixtures before restoring live time, randomness, session, or serialization paths
- for a textbook primitive, require one public known-answer vector plus one captured application vector


## Task 21C：CryptoJS cipher hook 只能产出元数据

> 中文摘要：页面把 `CryptoJS.AES.encrypt`/`decrypt` 当对象方法而非顶层函数使用；需要一个可逆的观察 hook，但日志绝不能含明文、口令、Key、IV、Cookie、token 或原始密文。考：可逆观察 hook 的日志脱敏。

Prompt:

```text
The page uses CryptoJS.AES.encrypt and decrypt as object methods rather than top-level functions. I need a reversible observation hook, but logs must never include plaintext, passphrases, Key, IV, Cookie, token, or raw ciphertext.
```

Expected route:

- `../../profiles/browser-hook-snippets/index.md`

Must conclude:

- wrap nested AES, DES, TripleDES, and RC4 encrypt/decrypt methods when they exist
- log only bounded method, type, and length metadata
- preserve the original call, return value, `this` binding, and promise or synchronous behavior
- provide `restore()` and refuse raw argument, key, IV, result, or stack logging by default


## Task 21D：gRPC 分帧需要长度与 trailer 的负向对照

> 中文摘要：手上有一段 grpc-web 响应，含多个帧、一个压缩标志、未知 protobuf 字段与末尾 trailer 帧；现有解析器假定任何非零 flag 都是 zlib 且只读第一个 payload。考：解码业务数据之前需要什么证明。

Prompt:

```text
I have a grpc-web response with several frames, a compression flag, unknown protobuf fields, and a final trailer frame. One parser assumes every nonzero flag means zlib and reads only the first payload. Define the proof needed before decoding business data.
```

Expected route:

- `../observe/structured-transport-playbook.md`
- （源文档此处引用 `scripts/grpc_frame_inspector.py`，该脚本在本包中不存在；实际动作：用 `../observe/structured-transport-playbook.md` 的分帧规则手工验证长度与 trailer，并做 Must conclude 要求的负向对照）

Must conclude:

- parse every five-byte frame header as flag plus unsigned big-endian length
- resolve compression from `grpc-encoding` or active grpc-web evidence rather than assuming zlib
- distinguish data and trailer frames and preserve unknown fields or raw payload bytes
- reject truncated headers, oversized lengths, and a tampered flag or trailer boundary before accepting decoded business data


## Task 21E：crypto 原语名不定义 wire 格式

> 中文摘要：客户端提到 SM2、ECDSA、ECDH、xxHash 与混合信封；草案实现把 SM2 签名整数与 C1C3C2 密文混在一起、把 ECDSA DER 当成裸 r||s，并漏掉哈希种子与字节序。考：定下验证契约。

Prompt:

```text
The client mentions SM2, ECDSA, ECDH, xxHash, and a hybrid envelope. A draft implementation mixes SM2 signature integers with C1C3C2 ciphertext, treats ECDSA DER as raw r||s, and omits the hash seed and byte order. Decide the validation contract.
```

Expected route:

- `../crypto/crypto-patterns.md`

Must conclude:

- distinguish primitive identity from signature, key, ciphertext, and envelope encoding
- record SM2 component order, ECDSA DER versus fixed-width raw form, ECDH point encoding and KDF, and checksum seed, width, and byte order
- verify primitive output separately from KDF, nonce or IV, authenticated data, component ordering, and final framing
- keep keys and captured ciphertext task-local while promoting only secret-free layout and verification rules


## Task 21F：窄环境运行时契约保持显式且有界

> 中文摘要：一个已知的本地 fixture 需要链式 MessageChannel 投递、两种 Image 加载回调风格、一个具名 webpack chunk 数组，以及浏览器兼容的 Latin1 btoa；不想要宽泛的浏览器模拟或全局扫描。考：窄契约优于宽模拟。

Prompt:

```text
A known local fixture needs linked MessageChannel delivery, both Image load handler styles, one named webpack chunk array, and browser-compatible Latin1 btoa. I do not want a broad browser emulator or a global scan.
```

Expected route:

- `../../profiles/env-patch/index.md`
- `../../profiles/env-patch/references/runtime-contracts.md`

Must conclude:

- use linked asynchronous ports rather than no-op MessageChannel stubs
- dispatch one Image load event to both `onload` and `addEventListener('load', ...)`
- capture bounded chunk and module IDs only from an explicitly evidenced array name, then restore `push`
- verify `btoa("\x00\xffAz") === "AP9Beg=="` and reject code units above `0xff` instead of silently UTF-8 encoding


## Task 21G：一次成功任务仍只是经验候选

> 中文摘要：一个目标教会了一条有用的逆向规则，想永久加进 Spider King；但只有一次成功运行、没有负向对照，笔记里还含宿主、Cookie 值与拷贝来的响应体。考：可复现经验闸门与脱敏。

Prompt:

```text
One target taught a useful reverse rule and I want to add it permanently to Spider King. I have only one successful run, no negative control, and my note currently includes the host, Cookie value, and a copied response body.
```

Expected route:

- `./skill-maintenance.md`
- `./experience-card-schema.md`

Must conclude:

- keep the one-job lesson in task-local `experience-candidate.json`
- require two independent reproductions, a secret-free fixture hash, positive oracle, negative control, first divergence, and applicability boundary before promotion
- strip target identifiers, cookies, tokens, keys, private responses, and endpoint folklore
- use a promoted card only as a hypothesis accelerator and re-prove one current-target fact


## Task 21H：专家交接不能扩权

> 中文摘要：当前路由发现一个归 verifier 所有的拦路点，可能有已安装的专家工具能帮；准备交接，但不允许并发控制同一目标的浏览器、隐藏重试、更宽的路径、依赖安装或原始会话值。考：交接只转移工作，不转移授权。

Prompt:

```text
The current route found a verifier-owned blocker and an installed specialist may help. Prepare the handoff without allowing concurrent same-target browser control, hidden request retries, broader paths, dependency installs, or raw session values.
```

Expected route:

- `./provider-work-order.md`
- `./specialist-handoff-contract.md`

Must conclude:

- confirm the specialist in the capability snapshot and name an executable Spider fallback
- park or release current same-target ownership before transferring `TARGET_ACTIVE`
- pass only proven facts, artifact paths and hashes, explicit permissions, remaining budget, unknowns, and one acceptance test
- treat omitted permission as blocked, reference secrets by local path and hash only, and have Spider accept the returned evidence against final delivery gates


## Task 21I：证据有自己的完成闸门

> 中文摘要：只提供了一条保存的请求，只问哪个字段会变更；不要联系目标、不要写文件；报告已证明的变更点与这份离线证据的边界。考：证据层的完成标准与交付层不同。

Prompt:

```text
I supplied one saved request and asked only which field mutates. Do not contact the target and do not write files. Report the proved mutation point and the limits of this offline evidence.
```

Expected route:

- `../deliver/delivery-gate-playbook.md`
- `./provider-work-order.md`

Must conclude:

- classify the result as artifact-only `evidence`
- require provenance, a bounded claim, redaction, and explicit unproven live behavior
- do not require a live endpoint, repeated replay, proof-manifest file, dependency install, or `main.py`
- do not promote the evidence to local-proof, compact-replay, or collector


## Task 21J：provider 写入路径是强制白名单

> 中文摘要：工单只允许在某一个确切 fixture 目录下写任务缓存；某条路由想写另一个项目内路径，因为它仍在项目里面。考：包含关系检查与重解析点拒绝。

Prompt:

```text
The work order permits task-cache writes only under one exact fixture directory. A route wants to write another project-local path because it is still inside the project.
```

Expected route:

- `./provider-work-order.md`
- `./project-artifact-contract.md`

Must conclude:

- reject `no-write`, unknown write mode, and an empty allowlist
- resolve the destination and require containment under both the project and one inherited `allowedPaths` entry
- reject symlinks, junctions, reparse points, hard-link aliases, skill paths, and OS temp
- require separate path-specific authorization before overwriting stable user files


## Task 21K：静态 AST 依赖保持任务本地

> 中文摘要：从一个干净的技能安装运行供给的静态 AST profile；Babel 未安装且已批准在任务缓存里装依赖，但任何任务都不得写进技能目录。考：依赖只装在任务本地副本。

Prompt:

```text
Run the supplied static AST profile from a clean skill installation. Babel is not installed and task-cache dependency installation is approved, but no task may write into the skill directory.
```

Expected route:

- `../../profiles/static-ast/index.md`
- `./project-artifact-contract.md`

Must conclude:

- copy the pinned package files, scripts, and tests into an allowed task-local tool directory
- run `npm ci --ignore-scripts` and the profile tests only from that task-local copy
- keep `node_modules` out of stable delivery and evidence packages
- never install dependencies from the skill profile root


## Task 21L：静态校验不执行候选代码

> 中文摘要：校验一个可能含不可信 Python 脚本的候选技能目录；未授权执行它的自检。考：默认可信自检从不执行候选脚本。

Prompt:

```text
Validate a candidate Spider King directory that may contain untrusted Python scripts. I did not authorize executing its self-tests.
```

Expected route:

- `./skill-maintenance.md`
- （源文档此处引用 `scripts/validate_skill.py`，该脚本在本包中不存在；实际动作：人工执行等价检查 —— 语法、结构、路由与套件一致性核对，全程不执行候选脚本）

Must conclude:

- default to syntax, structure, routing, and suite validation without subprocess execution
- require explicit `--run-trusted-self-tests` for the trusted current root
- isolate trusted self-tests from user site packages and arbitrary environment secrets
- state that the trusted self-test mode is not an operating-system sandbox


## Task 21M：浏览器获取角色是能力感知的

> 中文摘要：一个全新目标需要指纹保护的干净 baseline，然后 initiator 与源码追踪；当前注册表还暴露一个可选的 CDP 桥。是必须永远选定一条产品路线，还是同时激活所有浏览器表面。考：顺序获取角色，不是厂商路线锁定。

Prompt:

```text
A fresh target needs a fingerprint-protected clean baseline, then initiator and source tracing. The current registry also exposes an optional CDP bridge. Must I choose one product route forever, or activate every browser surface at once?
```

Expected route:

- `../triage/startup-triage-playbook.md`
- `../triage/tool-playbook.md`

Must conclude:

- classify fingerprint baseline, debugger trace, and CDP bridge as evidence roles selected from the current capability snapshot, not permanent vendor routes
- use only the roles justified by the next proof and record unavailable methods or fallbacks
- transfer `TARGET_ACTIVE` ownership sequentially and never drive the same target through multiple browser families concurrently
- keep every browser or CDP role evidence-only and retain a browser-free Python final path


## Task 21N：实现简报是条件式的

> 中文摘要：一个 artifact-only 解码器我已选定纯 Python 并要求现在实现；另一个采集器仍有纯 Python 与本地 JS 的未决选项，下一步会装依赖并做线上重放。判断何时一份正式实现简报才有用。考：条件式决定记录，不是强制仪式。

Prompt:

```text
For one artifact-only decoder I already chose pure Python and asked for implementation now. A different collector still has unresolved pure-Python versus local-JS options, and the next step would install dependencies and perform live replay. Decide when a formal implementation brief is useful.
```

Expected route:

- `./provider-work-order.md`
- `./report-templates.md`

Must conclude:

- do not impose a mandatory plan or approval ceremony on bounded evidence, local-proof, or an implementation choice the user already made
- create a compact implementation brief when `compact-replay` or `collector` work has material implementation ambiguity or would widen runtime, dependency, write, or live authority
- record the real endpoint, dynamic fields and writers, evidence, candidate forms, chosen boundary, acceptance test, and unresolved risks
- treat the brief as a decision record; it never grants omitted write, install, execution, account, or egress permission


## Task 21O：项目运行时一致性是显式的

> 中文摘要：这个采集器项目需要自己的 .venv，当前 shell 可能用的是全局解释器，Node 在 PATH 某处，并希望在 helper 运行前记录供给的 package-lock 指纹；诊断环境且不假定某台工作站路径。考：项目根、venv 一致性、lockfile 来源。

Prompt:

```text
This collector project requires its own .venv. The current shell may be using a global interpreter, Node is somewhere on PATH, and I want the supplied package-lock fingerprint recorded before a helper runs. Diagnose the environment without assuming one workstation path.
```

Expected route:

- （源文档此处引用 `scripts/check_reverse_env.py`，该脚本在本包中不存在；实际动作：人工执行等价诊断 —— 报告项目根、venv 一致性、`python -V` 与 `node -v` 版本，以及按需记录的 `package-lock.json` 指纹，不硬编码工作站路径）
- `./project-artifact-contract.md`

Must conclude:

- resolve and report the selected project root, interpreter, virtual-environment state, project-local environment coherence, and bounded runtime versions
- fingerprint only explicitly supplied lockfiles and report a path relative to the bound project without reading arbitrary files
- warn by default when the interpreter is outside the project environment, and fail only when the user or project explicitly requires that gate
- never hardcode a drive, profile id, global interpreter ban, or reusable secret into the skill


## Task 21P：hook 时机回退要保住证据界限

> 中文摘要：目标页面已经初始化完，装好的浏览器工具没有 preload helper，加载后 fetch hook 什么都没记录；继续推进但不声称该请求或变更不存在。考：区分 preload 与 post-load 的认知界限。

Prompt:

```text
The target page is already initialized, the installed browser tool has no preload helper, and a post-load fetch hook records nothing. Continue without claiming the request or mutation is absent.
```

Expected route:

- `../triage/tool-playbook.md`
- `../observe/hook-techniques.md`

Must conclude:

- record preload support and missing optional methods in the capability snapshot instead of fabricating an injection call
- prefer an early supported breakpoint or an explicitly authorized controlled reload when initialization-time evidence is required
- label post-load observation as proving only later activity and keep the clean baseline separate from instrumented runs
- check sibling transports, wrappers, workers, message relays, and the page-owned world before declaring the boundary inactive


## Task 21Q：采集器交接保持紧凑且可审计

> 中文摘要：浏览器无关的采集器完成了；给一份简洁的技术交接，足以重跑与审计，又不要为同一批事实造 README、计划、笔记文件和重复报告。考：交接摘要不分 proliferate 项目文档。

Prompt:

```text
The browser-free collector is complete. Give me one concise technical handoff that is enough to rerun and audit it without creating a README, plan, notes file, and duplicate reports for the same facts.
```

Expected route:

- `./report-templates.md`
- `../deliver/delivery-gate-playbook.md`

Must conclude:

- summarize the real endpoint, dynamic field writer and wire slot, session issuance or refresh, and final protocol order
- record fixed-vector and negative-control results, live replay count when claimed, and the downstream business acceptance oracle
- state the Python and helper boundary, browser-free and runtime-free truth, saved artifact paths, hashes, and remaining risks
- redact reusable secrets and keep one canonical compact handoff instead of proliferating duplicate project documents

## Failure signals（失败信号）

以下任一情形发生，**立即判定这次技能修订失败**，不再继续评审：

- 接受「以浏览器自动化作为最终交付」。
- 把每个困难目标都当成「只是签名还原问题」。
- 忽略传输信封（transport envelope）或解码链（decode chain）。
- 要求用户做大规模人工材料检查，而不是把目标收窄。
- 给出含糊的成功结论，没有重放证明。
- **根据磁盘上是否存在 MCP 源码来判断 MCP 工具可用**（应依据已挂载的工具注册表）。
- 在**同一个并行工具批次**里同时打开 chrome-devtools 与 js-reverse 的目标动作。
- 把「环境提供方启动」「被动抓包」或「PCAP 可见性」当作采集器证明。
- 把 MCP 浏览器运行时或页面驱动保留在最终采集器路径里。
- 对超出范围的 APK / app / 小程序主任务，或纯 artifact 工作，编造「先 chrome-devtools 加 js-reverse 一次过」的开场。

### 本机补充的失败信号（本机特有）

以下几条是改编时依据本机实际情况补充的，不在源文档里：

- 声称本机存在 `iv8`、`reqable`、Camoufox、AdsPower、WireMCP、esprima/acorn/@babel/parser 中的任意一个 —— **本机全部没有**。
- 声称本机挂载了 chrome-devtools 或 js-reverse —— **本机一个 web 侧 MCP 都没挂载**；此时相关用例只能记为「未在本机验证」。
- 引用 `scripts/forward_test_report.py`、`scripts/validate_skill.py`、`scripts/evidence_normalizer.py`、`scripts/transcript_diff.py`、`scripts/practice_lab.py` 等路径 —— **本包没有 `scripts/` 目录**，全部不存在。
- 引用平铺的 `references/xxx.md` 路径 —— 本包按 `references/<group>/` 分组，平铺路径不存在。


---

## 源文档勘误（改编时修正）
1. **源文档的 `Expected route` 大量使用失效的平铺路径。** 源文档写 `../triage/startup-triage-playbook.md`，而本包实际把该文件放在 `../triage/startup-triage-playbook.md`；照抄源文档会指向 160 条用例里绝大多数都不存在的文件。改编已**逐条**修正全部 `Expected route` 中的路径，共涉及 52 个 reference 文件与 4 个 profile 文件，全部改成本包实际存在的相对路径。
2. **源文档引用了本包不存在的脚本。** `scripts/forward_test_report.py` 与 `scripts/validate_skill.py` 在 `web-protocol-reverse/` 下**不存在** —— 该包没有 `scripts/` 目录。改编删除了这两处路径引用，把检查项改写为「由人工或外部执行器按 `../triage/forward-testing-playbook.md` 契约产出的报告」，并明确本包自身不提供该校验脚本。
3. **源文档的 `## Contents` 目录块按改编规范删除**，改为六段式 + 「任务目录」段。
4. **源文档要求「静态校验通过」与「行为通过」的区分，但没有给出没有校验器时的做法。** 改编补上了本机可实际执行的人工流程（报告目录结构 + 身份分离 + 精确摘录 + 响应文件约束 + 逐条人工核对）。
5. **源文档的 Pass criteria 与 `./skill-maintenance.md` 的 Pass conditions 高度重叠且互不提及**，读者容易误以为是重复错误。改编在两篇的「相关」段都显式说明了两者的分工（行为视角 vs 维护视角）。
6. **源文档只说「报告与 proof manifest 默认脱敏」，没说明与外部证据契约的接口。** 改编在 Pass criteria 段补上了与 `../../../field-journal/_template.md` 占位符规范及 `../../../case-review/scripts/review_case.py` 字段契约的对接，并给出 `--verify-hashes --strict` 自检命令。
7. **源文档没有说明「本机没有 web 侧 MCP」这一前提如何影响本套件的可执行性。** 改编在顶部声明块与「Failure signals」里都明确：本机未挂载任何 web 侧 MCP，相关用例只能记为「未在本机验证」。
8. **源文档把每条用例的断言写成纯英文。** 改编按分工保留 `Prompt` / `Expected route` / `Must conclude` 三段英文原样（它们是被测输入与被测断言，翻译会引入语义漂移），另加一行基于该用例实际内容撰写的中文摘要；`## Task` 编号 160 条**一个未丢**。
9. **源文档没有给出 `Expected route` 路径修正的说明，读者无法判断路径被改过。** 改编在「任务目录」段给出了修正规则的示例清单。