# 启动分诊手册（Startup Triage Playbook）

> **来源声明**：本文改编自外部仓库 `aoyunyang/spider-king-skill`（MIT License）的 `startup-triage-playbook.md`。原始内容为英文原文，此处译为中文并按本包六段式规范重排；技术术语保留英文原词并附中文，AI 检索时中英文均可命中。源文档大量引用一个**自带 MCP 浏览器工具链（`chrome-devtools` / `js-reverse`）的运行环境**，本机没有这套内置工具，本文已按本机实际能力改写（见文末「源文档勘误」与「本机化改动」）。
>
> **什么时候用**：每一次全新的接入（fresh intake）开始时，或者某个前置结论已经过期（stale）需要重判时。
>

> ★★ **本机 playwright 必须显式指定浏览器**（2026-10-10 实测）：
> `launch()` 默认启动会报 `Executable doesn't exist at %LOCALAPPDATA%\ms-playwright\chromium_headless_shell-1234\...`
> —— python 包期望 1234，本机装的是 **1243**，版本号对不上。
> **可用写法**：`p.chromium.launch(channel="msedge")`（实测能起、能渲染、能读 DOM），
> 或 `launch(executable_path=<显式路径>)`。照抄裸 `launch()` 一定失败。
> 

---

## 适用信号（Recognition signals）

命中下列任一条，就该先跑一遍启动门（startup gate），不要直接开始加载大 bundle 或往页面上撒 hook：

- 用户只给了一个裸 URL / 域名，没给任何抓包或请求样本
- 手上有 HAR、pcap、请求文本、JS/WASM 样本、token、cookie 或响应体 —— 但**不要求**证明「线上现在还这样」
- 上一次逆向的结论已经隔了一段时间，怀疑服务端换实现
- 用户描述的是「脚本还活着但采集器不工作」这类混合症状，家族判断不明
- 需要决定到底是**代码问题**、**传输准入问题**还是**验证门问题**

## 前置（Entry conditions）

启动门本身没有前置。**它产生**的是前置：

1. **intake mode（接入模式）已判定**，三选一：
   - `live-target`（活目标）：需要当前的页面 / 端点证据、当前 wire 行为、当前运行时出处
   - `artifact-only`（仅样本）：输入是已保存的请求、抓包、源码、JS/WASM 样本、token、cookie、响应体
   - `continuation`（续做）：同一目标、同一会话假设、同一交付目标都还成立
   - 规则：`artifact-only` 证据**不能**用来声称「线上已验收」「端点当前行为」「运行时出处」
2. **本机能力快照（capability snapshot）已记录**，至少包含：
   - 是否需要真实浏览器（`playwright` 是本机的浏览器路线）
   - wire 可见性手段是否可用（`tshark` / `mitmdump`）
   - JS 运行时是否可用（`node` 可用；静态 AST 那套 npm 包本机**没有**）
   - 是否需要本地宿主语义（`node` 够不够，不够要不要上 `playwright`）
   - **是否有 `iv8`** —— 本机**没有**
   - 明确的 blockers（阻塞项）
3. **授权边界**：涉及验证码 / 风控的部分，本文定位是「理解并建模服务端挑战」，不是绕过。只在你有权访问的目标上做。

## 步骤（Working method）

### 启动门四问（Startup gate）

每次先把这四条走完：

#### 1. intake mode

见上表。三条硬规则：

- `artifact-only` 阶段**先看本地运行时和已有样本**，不要为了仪式感开浏览器
- `live-target` 阶段**同一时刻只能有一个浏览器拥有目标所有权**（`TARGET_ACTIVE`），不要把两个浏览器族放进同一个并行工具批次
- 如果主目标是 APK / 原生 App / 小程序，直接声明**本技能范围外**（out of scope），不要硬造一个「配对浏览器首过」

#### 2. 环境与工具体检

按本机实际写：

```powershell
# Python 解释器（注意：不要用 (Resolve-ReverseToolSpec -Name 'pyre').Command，实测缺 frida/playwright/curl_cffi/mitmproxy）
& (Resolve-ReverseToolSpec -Name 'pyre').Command -c "import sys; print(sys.version)"

# 关键模块在场性
& (Resolve-ReverseToolSpec -Name 'pyre').Command -c "import importlib.util as u; print({m: bool(u.find_spec(m)) for m in ['frida','playwright','curl_cffi','requests','mitmproxy']})"

# Node（做本地 JS helper 用）
& (Resolve-ReverseToolSpec -Name 'node').Command -v

# wire 可见性
& (Resolve-ReverseToolSpec -Name 'tshark').Command -v
& (Resolve-ReverseToolSpec -Name 'mitmdump').Command --version
```

```bash
# npm 侧静态 AST 依赖自检 —— 本机预期为 False，需先装才能走那套路线
& (Resolve-ReverseToolSpec -Name 'node').Command -e "['esprima','acorn','@babel/parser'].forEach(m=>{try{require.resolve(m);console.log(m,'OK')}catch(e){console.log(m,'MISSING')}})"
```

记录完快照后再往下走。**缺工具就早报**，不要假装它不影响结论。

> 源文档提到的 `scripts/check_reverse_env.py` **在本包内不存在**（本包没有 `scripts/` 目录）。上面的命令就是本机的替代体检。

#### 3. 家族分诊（family triage）

给应用契约选**一个主家族**：

| 主家族 | 一句话定义 |
|---|---|
| `signer-gated`（签名门） | 请求字段每次都变，且被服务端校验 |
| `verifier-gated`（验证门） | 业务请求前面挂着一个 challenge（挑战）/ verifier（校验器）/ 预热步骤 |
| `decode-gated`（解码门） | 请求能过，但响应读不懂 |
| `session-gated`（会话门） | 登录 / 配对 / 心跳 / 重连的**顺序**决定成败 |
| `transport-gated`（传输门，**次标签**） | TLS、ALPN、UA、HTTP 版本、路由准入在应用语义之前就把请求挡掉 |

选家族必须**至少在两个证据面上互证**（响应形态、cookie 行为、运行时标记、脚本特征、wire 行为任选二）。只有一个弱提示时，保持「暂定」并继续取证。

**`transport-gated` 是次标签，不是主家族**：只有当它把「干净基线（clean baseline）」挡在应用语义之前时，才加上这个标签，然后**先解决传输准入，再回到正常家族分诊**。

#### 4. 交付意图（delivery intent）

先说清楚最小的可接受交付形态（本包内部标签）：

| 标签 | 交付什么 |
|---|---|
| `evidence` | 真实请求、initiator（发起方）、状态来源、变更点，或明确的阻塞项 |
| `local-proof` | 固定向量（fixed vectors）、解码样本、还原源码、无外联的 helper |
| `compact-replay` | 一个有界、可右键运行的单请求重放 |
| `collector` | 可重复、无浏览器依赖的 Python 采集器 |

**开头就否掉**：浏览器驱动的 replay、绑定 profile 的状态、自动化提交。这三样不是交付物。

### 能力感知的证据角色（Capability-aware evidence roles）

角色描述的是「下一步需要什么样的证明」，不是产品名、不是永久路线、也不是「可以同时开多个浏览器」的许可。

> 源文档的三个角色名是 `fingerprint-baseline` / `debugger-trace` / `cdp-bridge`，并绑定在不存在的 MCP 工具上。**角色本身是有价值的方法论，本机按等价的本机工具重新落实**：

| 证据角色 | 用来证明什么 | 最低证明 | 本机手段 | 本机限制 / 降级 |
|---|---|---|---|---|
| `fingerprint-baseline`（指纹基线） | 风险控制、可见交互、渲染器状态或 observer effect（观察者效应）会改变样本 | 未被插桩的请求与响应、重定向链、页面状态、浏览器/宿主模式、会话清单 | `playwright` 开启页面 + `mitmdump` 或 `tshark` 看 wire | 本机**没有** Camoufox / AdsPower 之类 managed host（托管宿主）。若目标对指纹压力高，**如实记录 role gap（角色缺口）**，不要假装已覆盖；普通低风险目标用 `playwright` 默认配置即可 |
| `debugger-trace`（调试器追踪） | initiator、源码、调用帧、参数、返回值、canonical mutation（规范化变更点）证据 | 把一条 wire 请求和它的调用者 + 决定性变更边界关联起来 | `playwright`（CDP）+ `frida`（运行时 hook）；或直接读已保存源码 + Node 本地执行 | 本机没有 `js-reverse` 那样的一体化调试 MCP；降级顺序 = 已保存源码 → 最早的稳定断点 → 一个窄的行为保持型 hook → 离线本地执行 |
| `wire-visibility`（线可见性，本机替代 `cdp-bridge`） | 看到真正跨越边界的字节 | 记录 wire 的获取方式、与基线的对应关系 | `mitmdump` 实时；`tshark` 离线读 pcap；`playwright` 自带网络事件 | 这是**被动旁证面**，不是第三个浏览器所有者；永远不能取代上面两个角色 |

`live-target` 的典型角色流转：

```text
基线宿主（playwright；本机无 managed host 可升级）
  -> 可选 wire-visibility（同一所有者下并行）
  -> 证据检查点
  -> 保留（parked）或 保留态例外（RETAINED_EXCEPTION）
  -> debugger-trace（frida / CDP 断点）
```

**任何时刻至多一个工具族持有目标所有权。** 某个角色交出证明或命名阻塞项后，把证据交给「能回答下一个缺失问题」的角色 —— 不要因为某个角色先被选中就一直待在它上面。

### 全浏览器依赖之前的升级阶梯

用**能解释证据的最小忠实层**：

1. 简单解码或标准算法 → **先手写 Python**
2. 宿主绑定（host-bound）JS 但无真实交互 → 走本地 JS 宿主 / `playwright`，见 `../crypto/embedded-browser-runtime-playbook.md`
3. 真实交互或渲染依赖 → 在浏览器里观察，但交付门依然严格，**不要把「观察」当成「最终采集器」**

完整逐级规则、证明要求和「禁止跳级」契约见 `escalation-ladder-playbook.md`。

### 家族分诊细则

#### `signer-gated`（签名门）

- 症状：一个或多个请求字段每次都变；服务端拒绝陈旧的 `sign` / `m` / `token` / header / wrapper 输出
- 第一步：抓一条好请求 → 追 initiator → 定位 canonical mutation point（规范化变更点）
- 若该字段最终收敛到标准摘要（digest）、紧凑 JSON 或明显的报文格式 → **先手写 Python**，别碰运行时
- 若代码读宿主对象、生命周期状态、定时器或 XHR wrapper → 走 `../crypto/embedded-browser-runtime-playbook.md`

相关：`../observe/transport-wrapper-playbook.md`、`../observe/patched-helper-playbook.md`、`../crypto/crypto-patterns.md`

#### `transport-gated`（传输门，次标签）

- 症状：标准 HTTP 客户端在 H2 reset、TLS EOF、握手超时、早期断连处就挂了，还没到应用语义
- 症状：同一路由在不同 UA 家族 / HTTP 版本 / 客户端栈下表现不同
- 症状：伪装传输（impersonation）或移动端 / App UA 能过，默认桌面或标准库流量过不了
- 症状：被挑战的落地路由失败，但同族的 auth / identity / 业务路由能干净绕过

第一步：冻结一张小的**准入矩阵（admission matrix）**，维度为 路由 × 客户端栈 × UA 家族 × HTTP 版本；找出一个能干净放行的窄 profile；先测路由局部绕过，**再**去加载巨型 bundle。

相关：`../observe/transport-pre-gate-playbook.md`、`../crypto/env-diff-playbook.md`

#### `verifier-gated`（验证门）

- 症状：业务请求只有在 verifier / challenge / 预热步骤之后才工作
- 症状：**页面在装了 hook 或断点之后就开始失败** ← 这条是 observer effect 的强信号，见下节
- 症状：没有有意义的业务 signer，但在某个独立请求之后出现了 token、cookie 或坐标

第一步：**在任何侵入式插桩之前**抓一条干净的未插桩基线 → 先 diff 请求与 verifier 输出 → 然后才加能证明边界的最窄 hook。

相关：`verifier-replay-playbook.md`、`verifier-error-localization-playbook.md`、`troubleshooting-playbook.md`、`../state/cookie-provenance-playbook.md`、`../state/challenge-artifact-harvest-playbook.md`

#### `decode-gated`（解码门）

- 症状：请求成功，但载荷读不懂
- 症状：body 需要字形映射（glyph mapping）、解压、protobuf、Base64 或多层解码

第一步：先冻结原始载荷 → 定位**第一个消费者**（first consumer）→ 在扩大采集之前本地重建解码链。

相关：`../deliver/response-decode-playbook.md`、`../state/side-asset-bootstrap-playbook.md`、`../observe/structured-transport-playbook.md`

#### `session-gated`（会话门）

- 症状：登录、配对、订阅、心跳、重连的**顺序**决定成败
- 症状：认证只出现一次，但后续帧除非计数器、标签或密钥保持有序否则失败
- 症状：媒体下载或解密需要从前序流量派生出的密钥

第一步：冻结一整份成功的 transcript（会话记录）→ 在读载荷语义之前把握手、保活、业务帧分开 → **先**重建一个稳定的本地会话，再谈规模化。

相关：`../state/stateful-stream-e2ee-playbook.md`、`../observe/structured-transport-playbook.md`、`../state/session-contract-playbook.md`

### Observer effect 规则（观察者效应）

如果 hook、断点或 monkey patch 让目标行为变了，**假设是你的工具在改变样本**。

此时：

1. 回到尽可能干净的抓包
2. 存下一对未被触碰的请求与响应
3. 把 hook **向外**移到传输边界
4. 优先用 initiator 栈和请求 diff，而不是大范围全局 monkey patch

**在你排除掉自己的插桩之前，不许把目标叫成「只能在浏览器里跑」。**

### 续做时的同类扫描（Continuation sibling scan）

在 `continuation` 接入时、重启一次长逆向之前：

- 搜工作区里是否已有同 host 或同端点家族的采集器、challenge helper 或笔记
- 目标与环境未变时，复用已证明的纯协议路径
- **只**重开那些被新证据真正推翻的浏览器面或深度逆向面

## 判据（Completion criteria）

只有同时满足以下全部 6 条，才算「启动门做完了」：

1. **intake mode 已显式写出**，并且如果它是 `artifact-only`，报告里没有任何「线上已验收」类断言
2. **本机能力快照已落到文字**：实际用了哪些工具、哪些缺、缺的那些有没有造成缺口
3. **主家族已定，且至少两个独立证据面互证**；若仍是暂定，报告里必须写明「暂定」和「缺哪个面」
4. **`transport-gated` 若成立，已附一张准入矩阵**（至少 2 个路由 × 2 个客户端栈），而不是一句「被挡了」
5. **交付形态已声明**，且明确否掉了「浏览器驱动 replay / profile 绑定状态 / 自动化提交」
6. **每个缺口都点名报告了**，而不是静默降级 —— 特别是 `iv8` 缺失和本机无 managed host 这两条

反例（**以下情况算没做**）：

- 只说「我打开浏览器看了一眼」而没写家族判定
- 家族判定只有一条弱提示却当成结论往下推
- 遇到 `403` / TLS 失败就直��去改签名算法，而没有准入矩阵

## 常见坑（Common traps）

- 把 `artifact-only` 的样本当成「线上现在也这样」的证据
- **把两个浏览器族塞进同一个并行工具批次**，两边同时持有目标
- 因为缺工具就跳过能力快照，凭印象假设工具存在
- 只在一个证据面上确认家族就推进
- 装了 hook 之后页面开始失败，还以为是「目标变难了」——先怀疑自己
- 把「需要渲染」当成结论，而没先排除 observer effect
- 在传输准入都没过的时候就去逆向应用层签名算法
- `continuation` 时把已有结论全部推翻重来，而不是先扫一遍有没有可复用的旧产物

## 相关（Related）

- `escalation-ladder-playbook.md` —— 「禁止跳级」的完整阶梯与升级四问
- `tool-playbook.md` —— 按本机实际能力写的工具选型表
- `symptom-heuristics.md` —— 「用户会说的话」到家族的快速匹配
- `troubleshooting-playbook.md` —— 已经做完了但仍失败时的症状路由
- `verifier-replay-playbook.md` / `verifier-error-localization-playbook.md` —— 验证门家族的完整方法论
- `positive-sample-hygiene-playbook.md` —— 拿到样本后先分级
- `../observe/mcp-routing-playbook.md` —— 源文档的 MCP 路由手册；**本机无对应 MCP 工具族，读它只为理解分诊逻辑，不要照抄其中的工具名**
- `../../SKILL.md` —— 非可谈判项与轻量分派表

---

## 源文档勘误与本机化改动

1. **交叉引用路径失效**：源文档全文用 `references/xxx.md` 风格路径。落到本包后这些文件实际分散在 `references/{triage,observe,crypto,state,deliver}/`。已全部改写为实际相对路径（同级 `./xxx.md`，跨目录 `../<cat>/xxx.md`）。
2. **工具前提在本机不成立**：源文档假定一个提供 `chrome-devtools`、`js-reverse`、Camoufox、AdsPower 的 MCP 运行环境，并有 `--self-test`、`--print-contract` 等工具服务器能力。**本机没有这套 MCP 浏览器工具族**。已把「工具列表」改写为「角色 → 本机手段」的映射，并保留角色定义本身（这部分方法论与工具无关）。
3. **`../observe/mcp-routing-playbook.md` 的定位已修正**：源文档用它做「自动在多种 MCP 族之间裁决」的依据。在本机它只剩分诊逻辑参考价值。
4. **不存在的脚本**：`scripts/check_reverse_env.py` 在本包内不存在（无 `scripts/` 目录）。已替换为本机可实跑的四条体检命令。
5. **源文档的家族命名不一致**：`transport-gated` 在「家族分诊」一节被明确标为次标签（secondary tag），但在「Escalation ladder」和 `tool-playbook` 的失败路由里又与其它家族平级。本文统一：主家族四选一，`transport-gated` 只作次标签。
6. **`iv8` 与 `reqable`**：源文档多处依赖。本机**两者皆无**。本文不作能力假设，凡涉及处指向本机可用的 `node` / `playwright` / `mitmdump` / `tshark` 路线。