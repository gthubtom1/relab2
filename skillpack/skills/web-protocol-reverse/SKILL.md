---
name: web-protocol-reverse
description: 敌意 Web 客户端还原成不依赖浏览器的采集器：sign/token/cookie、challenge、WebSocket/GraphQL/protobuf、WebAssembly。用于：403/412/429、HAR 离线复现、可重放采集器。不要用于：APK→apk-reverse；小程序→mobile-reverse；JS→js-reverse。
---

# Web 协议恢复（Spider King）

## 来源声明

> **改编自** `aoyunyang/spider-king-skill`（MIT License，https://github.com/aoyunyang/spider-king-skill）的 `SKILL.md`（原名 Spider King 7.0）。
> 保留原仓库 MIT 版权声明；本次改编为本技能包的六段式规范 + 本机工具链落地。
> **本机与上游的差异（改编时已知，勿按原文假设）**：
> - 上游 `scripts/`（`env-diagnose.js`、`scaffold_reverse_project.py`、`protocol_diff.py`、`validate_skill.py` 等）与三套 profile 自带的 `scripts/`、`tests/`、`package.json` **未随本次落地**，只有 Markdown 文档在包内。文档里引用这些脚本的地方本包已标注"未落地"，需要时从上游仓库取或自行实现。
> - ★ **本机没有任何浏览器类 MCP**（2026-10-10 实测 `~/.omp/agent/mcp.json`：只注册了
>   `pyghidra-mcp` / `ida-pro-mcp` / `angr-mcp` / `x64dbg-automate-mcp` / `idapro`，**全部是逆向侧**）。
>   `chrome-devtools` / `Camoufox` / `js-reverse` server **本机不存在**。
>   **所以本包文档里"默认基线主机 = chrome-devtools"是上游设定，不是本机事实** ——
> （★ 本机无 chrome-devtools / Camoufox MCP —— 见 SKILL.md「来源声明」实测记录；本机基线主机是 `playwright` 的 `launch(channel="msedge")`）
>   在本机必须换成 `playwright`（见下）。
> - ★ **本机 playwright 必须显式指定浏览器**：`launch()` 默认启动会报
>   `Executable doesn't exist at ...\\chromium_headless_shell-1234\\...`
>   （python 包期望 1234，本机装的是 1243，版本对不上）。
>   **可用写法：`p.chromium.launch(channel="msedge")`**（实测能起、能渲染、能读 DOM），
>   或 `launch(executable_path=<显式路径>)`。照抄裸 `launch()` 一定失败。

## ACTION REQUIRED（读完后立刻执行）

1. `NOW`：读 `../field-journal/precedent-reverse.md`，确认目标在已授权 scope 内。
2. `NOW`: **查经验卡** —— `python skills/scripts/experience-card.py search "<你看到的症状>"`。
   命中就读那张卡的 `invariant` + `decision.action`，并**逐条对照** `scope.appliesWhen`
   与 `scope.stopsWhen`：少一条前提就停用；命中任一停止条件就停。
   历史卡**不替代**当前目标的实测证据。详见 `../experience-cards/INDEX.md`。
3. `NOW`：读本文件「Auto Judge Card」，判定本次 intake 属于 `artifact-only` / `live-target` / `continuation`，**并把判定结果写进任务记录**。禁止先开浏览器再补理由。
4. `NEXT`：载入探测层 `C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1`（不存在则用 `..\..\skills\scripts\lib\Bootstrap.ps1`），用 `Resolve-ReverseToolSpec -Name <id>` 定位工具真实路径后按完整路径调用。`Get-Command` 查空 ≠ 缺工具。
5. `NEXT`：读 `references/triage/startup-triage-playbook.md`，完成 Startup Gate 四步并在报告里显式写出来。
6. `ACT`：按「工作流」Phase 0→Phase 5 执行，**先交付一个真实请求**（真实 URL / method / body / headers / initiator），再谈分页、并发、封装采集器。禁止停在确认状态。

## 适用场景

命中以下任一类信号，且目标是**已授权**的 Web 客户端：

- 请求能发出，但被 `403 / 412 / 429`、偶发成功、只成功第一页、只在某条路由成功
- 页面代码调 A 接口，真实请求却走 B 接口（wrapper / transport 重写）
- 业务层生成了 `sign` / `token` / `m`，发包前又被 transport wrapper 改写
- 响应还要解码：加密响应、二进制 envelope（信封）、字形映射（glyph mapping）、JSONP 拆包、protobuf/msgpack
- 存在 challenge / TDC / bootstrap 链 / 服务端下发 JS 写 Cookie
- 有状态流：WebSocket 会话、E2EE 帧、轮询任务、异步导出 job
- WebAssembly 签名、JSVMP、宿主绑定运行时
- 已有 HAR / PCAP / 抓包 / 请求文本 / 固定向量，只想做 artifact-only 离线证明（**此时不要开浏览器**）

明确不做（见下节）。

## 不走本 skill

| 情况 | 去哪 |
|---|---|
| 目标只要求定位前端 JS 的签名函数/调用链，产物是"函数在哪、调了谁" | `../js-reverse/SKILL.md`（`js-reverse_*` / `jshookmcp` 那套 Observe→Capture→Rebuild） |
| 自定义 TCP/UDP 协议、Protobuf/gRPC 帧布局、PCAP 字段还原 | `../protocol-reverse/SKILL.md` |
| APK / 原生 App / 小程序为主任务 | `../apk-reverse/SKILL.md`、`../mobile-reverse/SKILL.md`、`../reverse-engineering/SKILL.md` |
| PE / ELF / DLL / SO 二进制逆向 | `../ida-reverse/`、`../reverse-engineering/` |
| 需求本质是标准 UI 自动化、不要求协议可复现 | `../browser-automation/` |
| 只做浏览器/网络抓包取证、不做协议还原 | `../browser-automation/` 或 `../pentest-tools/`；本机可用的 wire 工具见下文「本机化补充」 |
| 目标不在授权 scope 内 | 施工依据是先落 scope：`../scripts/case-init.ps1` 一条命令补上，落完即继续 |

**分工口诀**：`js-reverse` 回答"这段 JS 在哪、怎么调的"；本 skill 回答"这条协议链怎么脱离浏览器复现"。两者是流水线的上下游，不是二选一 —— 本 skill 的 `debugger-trace` 阶段默认就交给 `js-reverse` 的工具面。

## 非协商项（Non-Negotiables）

这些条款不接受"先试试再说"：

1. **先判后开工具**：任何新任务在动手前必须走完本文的 Auto Judge Card 与 `references/observe/mcp-routing-playbook.md`，先定 intake / 要不要浏览器 / 用哪个基线主机 / 是否需要 `js-reverse`。不允许"先打开再解释"。
2. **live-target 的双角色硬顺序**：每个 fresh 的 web `live-target`，在声称"这个线上目标已经看懂"之前，必须按顺序拿到两份证据：`fingerprint-baseline` → `debugger-trace`。★ **本机默认工具面是 `playwright`（`launch(channel="msedge")`），不是 `chrome-devtools`** —— 本机没有任何浏览器类 MCP（见「来源声明」实测记录）。只有当指纹压力（fingerprint pressure）被证明时，基线主机才允许升级到更强的 managed profile；`debugger-trace` 只有在真实存在 debug attach 面、且经过一次实际 handoff 之后才用 debugger。APK / 原生 App / 小程序主任务直接 out-of-scope，不许编造双浏览器证据当仪式。
3. **浏览器取证必须 target-serial（串行）**：同一时刻最多一个工具族处于 `TARGET_ACTIVE`，绝不允许两个浏览器族在同一个并行工具批次里打同一个目标。handoff 门禁见 `references/triage/tool-playbook.md`。易失且不可重放的状态用 `RETAINED_EXCEPTION` 保留，不要为了清理把它毁掉。
4. **交付必须是 browser-free 的 Python 运行路径**：凡是 `compact-replay` / `collector` 交付，不得把浏览器自动化、Playwright、Selenium、CDP 驱动页面、页面上下文里的 fetch、浏览器 profile、人工浏览器状态当作最终重放路径或兜底。
5. **Python 优先**：HTTP、编排、解析、重试、持久化、输出一律用纯 Python。
6. **JS/WASM 只做极小本地助手**：只有在"已验证的 Python 移植当前风险更高"时才保留，且助手不得依赖活的 `window`、`document`、浏览器存储、页面驱动或人工点击。
7. **本地 bootstrap executor 可以模拟宿主语义，但活 HTTP 必须归 Python**，并明确说明交付是"仅 browser-free"还是"完全 runtime-free"。
8. **先恢复一个稳定业务请求**，再谈分页、并发、提交、运行时瘦身。
9. **每个结论都要用它自己声明的证据形态兜底**。只有在声称"当前线上确实接受"时才要求重复 live 重放。敏感值留在本地：凭据、token、个人数据、Cookie 值必须从对话、报告和版本控制里脱敏。
10. **不许在没证明写者、槽位、作用域、过期与刷新路径之前硬编码旋转状态。**
11. **bootstrap 重的流程在证明可跨会话复用之前，保持在同一条会话链上。**
12. **停止条件只有一个**：声明的交付形态通过了它对应的能力门禁，或者证明了真实的外部阻塞。不许把 `evidence` / `local-proof` 包装成 collector，也不许把半成品自动化美化成"临时 collector"。
13. **`compact-replay` / `collector` 交付必须带一个 PyCharm 可右键运行的 Python 入口**，通常是项目根 `main.py` 或 `collector/main.py`，且不要求任何命令行参数。`evidence` / `local-proof` 不强制入口，除非用户要的就是可执行代码。
14. **只路由当前 agent 工具注册表 / schema 里确认存在的 MCP 家族。磁盘上有源码 ≠ 可用。**
15. **被动抓包存储（Reqable / HAR）可以与浏览器 `TARGET_ACTIVE` 共存，但不能替代 web live 首轮证据，也不得成为最终运行路径。**
16. **`compact-replay` / `collector` 必须完全脱离 MCP 浏览器运行时、页面驱动和 profile 绑定操作。**

失败形态的反面案例见 `references/principles/anti-patterns-playbook.md`。打包产物前，只应用 `references/deliver/delivery-gate-playbook.md` 里与当前能力匹配的那一道门禁。

## Lightweight Dispatch

这些标签用来让**第一步尽量小**，内部使用即可；不要在正常回复里强行输出机器式表头。

| 形态（Shape） | 交付物 |
|---|---|
| `evidence` | 真实请求、initiator、状态来源、变异点，或一个精确的阻塞说明 |
| `local-proof` | 固定向量、解码样本、还原后的源码，或无外网出口的可调用助手 |
| `compact-replay` | 针对一个已证明请求的、有边界的、right-click 可运行重放 |
| `collector` | 带边界（页数/字段/限速）的、可重复的 browser-free Python 采集器 |

默认取能回答用户问题的最小形态。用户给了 HAR、抓包、请求文本、JS/WASM、cookie/token 样本、固定向量或既有工程产物 —— 从 `evidence` 或 `local-proof` 起步，**不要为了满足 live-target 仪式而开浏览器**。裸 URL 不带 scope 字段 —— `case-init` 一条命令补上，然后照常推进。

路由名（route name）描述的是当前能力归属方，不是门禁家族：`evidence-reuse`、`chromium-recon`、`browser-hook`、`static-ast`、`env-patch`、`iv8-local-runtime`、`verifier`、`transport`、`pure-python-rebuild`、`python-collector`。一次只跑一条 route，直到它返回证据或一个具名阻塞。若两条 route 都说得通，先挑更小的离线 route，并记录"什么证据才值得升级"。

在任何 route 要写文件、发外网、执行目标提供的代码、使用账号/会话状态、安装依赖或改变运行时状态之前，先套 `references/contract/provider-work-order.md` 里的紧凑契约。

## Auto Judge Card（信号驱动）

工具选择之前先跑这张卡。它不放宽任何交付门禁。完整信号表与主机升级规则见 `references/observe/mcp-routing-playbook.md` 与 `references/triage/startup-triage-playbook.md`。

按顺序判定，并在第一个针对目标的动作之前记录所选分支：

1. **Intake（入口判定）**：离线样本够、且不需要当前线上接受 → `artifact-only`；裸 URL 或需要新鲜页面/会话证据 → web `live-target`；同目标同环境同目标 → `continuation`；APK/App/小程序主任务 → out-of-scope。
2. **需要浏览器吗**：纯离线解释/还原/固定向量 → 不需要；需要当前请求、页面、线路证据 → 基线主机；只在已知边界调试 → 确认 attach 归属方之后再用 debugger。
3. **基线主机**：★ **本机默认 `playwright` 的 `launch(channel="msedge")`**
   （实测可跑；裸 `launch()` 会失败，见「来源声明」）。只有指纹压力成立或干净基线失败才升级更强的 managed host；
   普通低风险工作**绝不**默认上重型反检测方案。
4. **Debugger**：候选业务请求已存在且 attach 可用时，串行 handoff 给 debugger（本机 `playwright` CDP / `frida`）；
   attach 缺失则导出产物、记录 `debugger_attach_gap`，转离线。
5. **尽早离开浏览器**：真实请求、变异点、重建路径都证明之后，退出浏览器面，用纯 Python 收尾。

### 默认 live 顺序（本机版）

```text
capability snapshot（先查 ~/.omp/agent/mcp.json，本机只有逆向侧 MCP）
  -> Auto Judge（先判）
  -> fingerprint-baseline（playwright launch(channel="msedge")）
  -> sequential handoff（串行交接）
  -> debugger（playwright CDP / frida，前提：attach 面存在）
  -> offline rebuild（离线重建） + delivery gate（交付门禁）
```

## Startup Gate

深入分析之前必须完成并汇报这张门禁。展开版清单见 `references/triage/startup-triage-playbook.md`。

### 0. Intake mode

使用工具前先声明一种模式：

- `live-target`：当前页面/端点需要新鲜的浏览器与线路证据 → 走角色串行顺序
- `artifact-only`：只有已保存的请求/源码/token/样本 → 明确标注"线上接受度未验证"
- `continuation`：同目标同环境同目标 → 复用当前门禁，只重开变化的面

### 1. 环境与工具

快照当前挂载的 MCP 家族、attach/debug 可用性、可选的被动抓包存储。只路由确认可用的工具。可选家族缺失是"缺口"，不是"要补的仪式"。

### 2. 家族分流

从当前证据里打一个最小的主导门禁家族标签：`signer-gated`（签名门）、`transport-gated`（传输门）、`verifier-gated`（校验门）、`decode-gated`（解码门）、`session-gated`（会话门），然后只打开那一条路径。

### 3. 交付意图

声明交付形态（`evidence` / `local-proof` / `compact-replay` / `collector`）并停在该门禁前。禁止把没做完的自动化包装成临时 collector。

## 工作流

短执行地图见 `references/principles/workflow-overview.md`，工具选择见 `references/triage/tool-playbook.md`。

### Phase 0 — 指纹（Fingerprint）

- 在铺开大范围 hook 之前先取干净基线，因为观察者效应（observer effect）可能污染结果。
- 区分：诱饵接口 vs 真实接口、传输门 vs 应用门、可见参数 vs wrapper 改写、bootstrap 静态资源 vs 数据接口、单次请求 vs 有状态 transcript。
- 尽早识别：纯 JSON、GraphQL、WebSocket、protobuf、二进制 envelope、加密响应、字形映射、JSVMP、宿主绑定运行时。
- 选**最小的下一个证明**，不要一上来倒一整包。

### Phase 1 — 证明真实请求

- 跟随重定向，以及 wrapper 页 / 兼容页。
- 分开映射 entry、bootstrap、list、detail、submit、verifier、warm-up、telemetry、download、风控、异步导出/报表 job 这些路由。
- 抓准：完整 URL、method、query、body 字节、headers、出站 Cookie header、响应形态、initiator。
- 分页 pivot 和被挑战的文档重放，也属于协议契约的一部分。

**本阶段交付物**：真实业务路径上一个已确认的请求。

### Phase 2 — 隔离会动的状态

把每一个变化的部分归类：时间戳、nonce、被签名的 query/body、旋转 header/cookie、wrapper 字段、operation 名、cursor、bootstrap 产物、解码密钥、字形映射、会话 secret、profile 基线、稀疏增量、计数器、心跳、耗时依赖、媒体密钥、页面异常、账号状态、宿主语义。

当目标是导出类或开放平台签名 API 时，还要把字段分成业务类、静态应用类、服务端下发类、每请求动态类，再设计再生逻辑。

证明 Cookie 的来源，区分服务端下发的产物和本地凭空造的填充物。页面上说"这个 cookie 参与签名"在 wire 行为确认前只是假设。当登录只是第一道门时，在导出前用一次最终身份复读验证 tenant、role、数据范围，见 `references/state/multi-context-session-playbook.md`。存储的 cookie jar 与实际出站的 Cookie header 不一致时，以出站 header 为准。

### Phase 3 — 定位规范化变异点（canonical mutation point）

按这个顺序追：

1. 传输 wrapper、拦截器、`beforeSend`、fetch、Ajax、XHR、worker、message 边界
2. bootstrap 脚本与内联 payload
3. 暴露的助手函数与其返回的子对象
4. WASM 导出或内部 serializer、packer、signer、decoder 原语
5. 服务端下发的 challenge 与响应侧刷新字段
6. 帧 serializer、protobuf parser、握手 transcript、key schedule（密钥调度）

规范化变异点是**线格式 payload 真正发生变化的地方**，不是业务代码造占位符的地方。

出现具名摘要算法（named digest）时，先在固定输入上证明它，再信任标准库。优先按"环境选出来的摘要常量 + 浏览器分支"判断，而不是按 UI 或函数名判断。转 `references/crypto/crypto-patterns.md`。

### Phase 4 — 离线重建

- **一格一格地爬**：固定输入对等 → 窄边界观察 → 纯本地复现 → 窄宿主 bootstrap → 有证据支撑的宿主面补丁。
- 升级前记录：最后一个已证产物、精确盲点、为什么下一格是最小的、browser-free 交付如何保持完整。
- 扩大运行时、补丁面或传输 profile 前读 `references/triage/escalation-ladder-playbook.md`。
- 传输证据证明"最接近的维护型后端表达不了这个已承认的浏览器画像"时，读 `references/observe/native-transport-profile-playbook.md` 再造路由内的原生适配器。
- 不透明的阶段性产物仍依赖运行时输入时，读 `references/crypto/opaque-runtime-profile-playbook.md`：保持一次原子运行，逐阶段移植，区分"算法生成"与"快照驱动生成/池化重放"。
- 保留精确的序列化、字段槽位、帧封装、JSONP callback、分隔符、压缩、密码套件、解码顺序。
- 把 JS 摘要算法移植到 Python 时，在冻结的 preimage 上先验 uint32 截断、`ROTL` 边界与逐字节打包掩码，再上 live 重放。
- 字符串表密集的 bundle：先用非执行的 `profiles/static-ast/index.md` 检测器加保守改写，然后用两遍改写离线恢复 decoder，再做深度 beautify。见 `references/crypto/obfuscation-guide.md` 与 `references/crypto/offline-inline-deob-playbook.md`。
- 当页面、关键字、body、referer、时间戳或会话状态会改变请求形态的产物时，在**请求循环内部**再生它们。

### Phase 5 — 证明可重复性与规模

- 用固定输入或固定 payload 向量验证助手与解码器。
- 在扩容或瘦身运行时之前，先在一条会话链上证明一次 fresh 单页重放。
- 要求至少 2~3 次重复 live 重放；"助手能加载"、"token 长度合理"都不是接受。
- verifier-gated（校验门）流程：要在一整轮里证明必需的 sidecar、共享状态一致性、真实请求时序、最终 verifier 语义，以及第一个下游消费者。保持上述硬顺序；在放大重试次数之前记录消融矩阵（ablation matrix）与本地错误语义图。
- verifier-gated 流程还要证明正样本卫生（positive-sample hygiene）：干净的成功样本比被污染的自动化失败更有说服力。环境风险（出口 IP、自动化标记、连续失败）是与"赛道质量"分开的另一个失败面。
- 证明下一页 / 下一个 cursor、路由 pivot、刷新行为、字段完整性，以及相关的权限边界。
- 异步导出：用"创建前 task-id 快照 + 条件匹配"证明 create，隔离被轮询的 task；当下载列比请求字段更窄时阻断持久化。见 `references/state/async-export-job-playbook.md`。
- 尽早保存原始样本，对意料之外的响应形态**响亮地失败**。

## 实施契约（Implementation Contract）

- 按关注点拆分：client、settings、bootstrap、headers/cookies、sign、envelope、decode、extraction、retries、storage、tests。
- 写代码前先绑定一个任务工程；动态证据放在 `js_reverse_cache/tasks/<task-id>/`。**不要**用 OS 临时目录、桌面随手建的文件夹、skill 目录或隐藏浏览器 profile 当主存储。
- 稳定脚手架与易失抓取、生成的运行时 blob 分开存放。
- 服务端下发状态与本地计算状态分开编目。
- bootstrap 重的采集与重放保持单会话链，直到复用被证明。
- 当 wire 出站与中间 getter、回调或 cookie jar 不一致时，以 wire 为准。
- 流量死在应用语义之前时，把"传输准入"当作独立问题测。
- 确定性证明模式与线上生成模式分开。
- 每个最终助手自包含，不 import 带运行时依赖的前代实现。
- 复用既有已解助手只走 `references/deliver/case-reuse-playbook.md`：按精确作用域或多个独立信号匹配，先跑固定向量，绝不把复制来的 secret 或历史笔记当作当前证明。

> 上游 `scripts/scaffold_reverse_project.py` / `protocol_diff.py` / `transport_profile_diff.py` / `transform_trace_diff.py` / `crypto_fingerprint.py` / `evidence_normalizer.py` / `transcript_diff.py` / `practice_lab.py` **本次未随包落地**，需要时从上游 MIT 仓库取或自行实现；不要以为 `python scripts/xxx.py` 能跑。

关于可复用证据见 `references/triage/reproducible-evidence-playbook.md`。

上游提到的"skill 自带 loopback 练习场（practice lab）"**也未落地**，不要去找本地端口。

## 判据（做到哪算完成）

未通过与声明形态相关的全部门禁之前，不许标记完成：

- [ ] Startup Gate 是当前的（本轮任务内做过的）。
- [ ] 声称线上结论时，真实端点、规范化变异点、变动状态都已证明。
- [ ] fresh web `live-target` 的两份首轮工具证据都已记录；`artifact-only` 明确写了这两个面"未验证"；非 web 主目标是 out-of-scope 而不是编造 web 证据。
- [ ] 相关时已处理干净基线与观察者效应风险。
- [ ] 助手/解码器的固定输入校验通过。
- [ ] 以下都**不算**接受：非空签名、token 长度合理、助手加载成功、一次 HTTP `200`、一个当前的 cookie jar、一份过期的浏览器导出。
- [ ] 适用时，Cookie 来源、槽位位置、会话链完整性、传输、envelope、decode、流、分页、权限规则都已写进文档。
- [ ] `compact-replay` / `collector` 的重复 live 重放成功（除非用户明确接受一个有边界的离线重放，并标注线上接受度未验证）。
- [ ] 任何最终重放或采集器都不依赖浏览器自动化与浏览器 profile。
- [ ] 输出按要求的格式落盘。
- [ ] 敏感产物在任务内 secret store 之外已脱敏。持久化的归一化证据包使用 `references/contract/project-artifact-contract.md` 里的证据专用 manifest schema；可运行的重放/采集器 manifest 还要记录能力、会话作用域、助手与重放证据，且不复制 secret。纯对话式的 evidence 结果不需要 manifest 文件。

每个有意义的阶段之后，用 `references/contract/report-templates.md` 的精简 phase-delta 格式；完整模板只用于重大决策与最终交付。`compact-replay` / `collector` 以其紧凑协议交接摘要收尾，不要再写冗余工程文档。始终汇报：家族选择、每个可用证据面证明了什么、真实端点、变动部分、误导性信号、固定输入证明、最终协议路径、采集器/助手拆分、落盘路径、browser-free 状态、剩余不稳定点。仅在相关时追加 Cookie、观察者效应、同级 route、envelope 家族、decode、会话、分页、最小可验证事实的细节。

出现可复用的家族规律时，用 `references/triage/minimal-verifiable-facts-playbook.md` 保留 5~15 条结构事实。单次任务的教训留在任务目录里；独立复现两次之后，用 `references/contract/experience-card-schema.md` 只提升不变量、fixture、正/负 oracle 与适用边界。

## 常见坑

反面案例完整版见 `references/principles/anti-patterns-playbook.md`（Anti-pattern 1–N）。最常踩的几条：

| 坑 | 表现 | 正确做法 |
|---|---|---|
| 把浏览器支撑的重放美化成临时 collector | 交付里藏着 Playwright/profile | 交付前 grep 一遍依赖，无浏览器依赖才算过 |
| 硬编码当前那个"能用一次"的旋转 cookie/token/header | 跑通一次后全线 403 | 先证明写者、槽位、作用域、过期与刷新路径 |
| 一次侥幸成功就上规模 | 分页第 3 页开始空 | 2~3 次重复 live 重放后再谈并发 |
| 因为当前这格烦人就跨级 | 直接扔进 `node:vm` 或浏览器 | 一次只升一格，升之前写清盲点 |
| 没取干净基线就铺开大范围 hook | 请求消失/签名降级/完整性检测告警 | 先基线，再逐个最窄 Hook 点 |
| 逆向可见的 helper 或可见参数，而不是 wire 变异点 | 本地能算，服务端不认 | 定位到 payload 真正变化的位置 |
| 认为标准摘要库因为名字匹配就算完成 | 长度对、值全错 | 固定输入先验证；注意 uint32 端口和逐字节掩码 |
| 拿"助手加载成功 / 异常变少 / 输出像浏览器"当协议成功 | 假阳性 | 只有服务端接受才算 |
| 用稳定脚手架覆盖易失抓取 | 下次跑不起来 | 稳定与易失分目录 |
| 相信页面文案说 cookie/session 参与签名 | 补丁越加越多 | 以 wire 行为为准，文案只是假设 |
| 编码来源不明的"字段名像服务端下发" | 硬编码了本地 mint 的值 | 用 wire 证据区分下发与本地造 |
| 只路由磁盘上有的 MCP | 调一个不存在的工具族 | 只路由当前注册表确认存在的 |
| 装了一堆 npm 依赖到 skill 目录 | skill 树被污染 | 依赖装到任务目录 `js_reverse_cache/tasks/<task-id>/`，skill 树只留文档 |

## 快速路线与归属（Fast Routes and Ownership）

目标已经明确时用专注路线，不要为这些场景重启完整的未知目标发现流程。

| 当前目标 | 路线 |
|---|---|
| 在已知边界要一段可直接贴的浏览器观察 Hook | `profiles/browser-hook-snippets/index.md` |
| 对给定 JS 文件做结构化 AST 还原 | `profiles/static-ast/index.md` |
| 已知入口 + 已知调用方式 + 有固定浏览器输出，在 Node/VM 里跑 | `profiles/env-patch/index.md` |
| 固定轨迹的纯 Python signer/decoder 重写或回归 | `references/deliver/pure-python-rebuild-playbook.md` |
| 未知或多层的端到端采集器 | 继续走下面的 Startup Gate + 通用逆向循环 |
| 只要入口/调用链位置 | 有专用逆向技能就用；否则用 `chrome-devtools` / `js-reverse` 的 initiator 证据 |
| 明确要 Python + iv8 运行时 | 本机**无 iv8**（社区运行时，PyPI 上没有）。如实报告约束未满足；只有用户接受替代后，才走 env-patch 或本地助手边界 |
| 确认是 CAPTCHA/TDC 或有专用协议的家族 | 用对应专用技能；本 skill 只做次级运行时帮助 |
| 已有 HAR、Reqable history 或请求文本要解释/起草重放 | `evidence-reuse`；开浏览器前先读 `references/observe/mcp-routing-playbook.md` |
| 取证前就需要指纹或 managed profile | Auto Judge 判定高指纹压力 → Camoufox/managed host 基线；debug 端点存在时再 attach/`js-reverse` handoff |
| 样本够且不需要新的线上证明 | `artifact-only` / `evidence-reuse`；不要为仪式打开 Camoufox、Chrome 或 `js-reverse` |

**本机化补充**：上游默认的被动抓包存储是 Reqable，本机**没有装**。需要 wire 证据时用：

- `(Resolve-ReverseToolSpec -Name 'tshark').Command`（Wireshark 自带 CLI，抓包后直接切字段）
- `(Resolve-ReverseToolSpec -Name 'mitmdump').Command`（mitmproxy，改写/重放中间层）

HAR 导出仍可用浏览器 DevTools 完成；本文不提供 Reqable 的具体操作步骤（未在本机验证）。

profile 细则：

- browser-hook / static-ast / env-patch 路线可以跳过完整的未知目标 Startup Gate 仪式，但仅限 `artifact-only` 或已证明的已知边界工作；即便如此，改动仍须可逆、日志仍须脱敏。只做结构检测的 static AST 可以仅凭给定文件开始；但在声称算法等价、评估还原后的边界、执行目标代码或升级到动态路线之前，必须先有固定样本。如果该路线需要与当前目标发生新交互，就分类为 `live-target`，并适用上面的串行规则。
- 如果某个 profile 暴露出缺失的 bootstrap、会话、传输、decode 或分页状态，退出 profile，回到通用逆向循环。
- 过程产物落在执行工程的 `js_reverse_cache/tasks/<task-id>/`（`task.json`、`network.jsonl`、`runtime-evidence.jsonl`、`handoff.json`、`fixtures/`、`../../examples/ctf-demo/report/report.md`）。交付证明留在 `analysis/proof_manifest.json` 及相关 analysis 文件。**绝不要把任务 secret 写进本 skill 目录。**首次保存或提升前先套 `references/contract/project-artifact-contract.md`。

## 参考路由（Reference Router）

只加载与当前证据匹配的文件，但每条路线都要能在这里被发现。

**注意**：本包内 `references/` 已按主题分子目录，下面的路径是**实际落地路径**。

### 核心流程与维护

- 专注路线：见上文「快速路线与归属」
- `profiles/browser-hook-snippets/index.md`、`profiles/static-ast/index.md`、`profiles/env-patch/index.md`
- `references/deliver/pure-python-rebuild-playbook.md` — 固定轨迹纯 Python 重写
- `references/triage/startup-triage-playbook.md` — Startup Gate 展开清单
- `references/principles/workflow-overview.md` — 短执行地图
- `references/triage/tool-playbook.md` — 工具选择与 handoff 门禁
- `references/observe/mcp-routing-playbook.md` — MCP 家族选择与信号驱动 auto-judge（artifact-only / Camoufox / managed host / chrome-devtools / js-reverse / 被动抓包存储 / wire 可见性 / 环境供给方）
- `references/observe/local-mcp-environment.md` — 本机 attach 端口与 debug profile 路径问题
- `references/triage/escalation-ladder-playbook.md` — 升级阶梯
- `references/deliver/delivery-gate-playbook.md` — 各能力门禁
- `references/principles/anti-patterns-playbook.md` — 失败形态反例
- `references/contract/report-templates.md` — 报告模板
- `references/principles/doctrine-index.md` — 26 条 Doctrine 索引
- `references/triage/symptom-heuristics.md`、`references/crypto/pattern-atlas.md`
- `references/triage/minimal-verifiable-facts-playbook.md`、`references/triage/reproducible-evidence-playbook.md`
- `references/contract/provider-work-order.md`、`references/contract/specialist-handoff-contract.md`
- `references/contract/project-artifact-contract.md`、`references/deliver/case-reuse-playbook.md`
- `references/contract/experience-card-schema.md`

### 请求路径、签名与混淆

- `references/crypto/crypto-patterns.md` — 被魔改的标准摘要、uint32 端口、固定样本加密
- `references/crypto/obfuscation-guide.md`、`references/crypto/offline-inline-deob-playbook.md` — 字符串表/混淆器式恢复
- `references/observe/decoy-and-real-request-playbook.md`
- `references/observe/transport-wrapper-playbook.md`
- `references/observe/patched-helper-playbook.md`
- `references/crypto/jsvmp-analysis-playbook.md`
- `references/crypto/opaque-runtime-profile-playbook.md`

### Cookie、bootstrap 状态与会话

- `references/state/multi-context-session-playbook.md` — 登录后的多层业务身份
- `references/state/cookie-provenance-playbook.md`、`references/state/session-contract-playbook.md`
- `references/state/public-bootstrap-envelope-playbook.md`、`references/state/challenge-state-envelope-playbook.md`
- `references/observe/dual-writer-param-playbook.md` — 同一参数名的双写者
- `references/crypto/local-challenge-executor-playbook.md`
- `references/state/server-js-cookie-bootstrap-playbook.md`、`references/state/side-asset-bootstrap-playbook.md`

### 宿主绑定运行时与观察

- `references/crypto/environment-patch-playbook.md`、`references/crypto/env-diff-playbook.md`
- `references/crypto/embedded-browser-runtime-playbook.md`
- `references/crypto/iv8-runtime-cheatsheet.md` — **本机无 iv8**，该文件仅供有该运行时时参考，**未在本机验证**
- `references/state/challenge-artifact-harvest-playbook.md`
- `references/observe/hook-techniques.md`、`references/observe/anti-debug-playbook.md`

### 传输、解码与结构化协议

- `references/state/async-export-job-playbook.md` — 异步导出、报表下载、任务隔离
- `references/observe/transport-pre-gate-playbook.md`
- `references/observe/native-transport-profile-playbook.md`
- `references/deliver/response-decode-playbook.md`
- `references/observe/structured-transport-playbook.md`
- `references/state/stateful-stream-e2ee-playbook.md`

### 校验器、分页、异常与恢复

- `references/triage/verifier-replay-playbook.md`、`references/triage/verifier-error-localization-playbook.md`
- `references/triage/positive-sample-hygiene-playbook.md`
- `references/observe/pagination-route-pivot-playbook.md`
- `references/observe/page-specific-exception-playbook.md`
- `references/triage/troubleshooting-playbook.md`

### 技能自维护

- `references/contract/skill-maintenance.md`
- `references/contract/official-self-test-task-suite.md`
- `references/triage/forward-testing-playbook.md` — 行为前向测试与独立复核

> 上游 `scripts/validate_skill.py`、`scripts/forward_test_report.py` 与 `tests/` **未随包落地**，本文不提供其调用方式；需要时从上游 MIT 仓库取。

## 维护本技能

可复用的细节放最具体的那篇 reference。本文保持为"协议优先的执行路径 + 路由器"。保留通用事实与固定向量，**绝不**保留线上 secret、复制的 cookie、账号 token 或站点八卦。

## 相关

- `../js-reverse/SKILL.md` — 本 skill 的上游：定位前端 JS 的签名函数、调用链、initiator
- `../protocol-reverse/SKILL.md` — 自定义协议帧 / Protobuf / PCAP 字段还原
- `../reverse-engineering/SKILL.md` — 非 web 目标总入口
- `../field-journal/precedent-reverse.md` — 授权先例
- `../references/env-selfcheck.md` — 本机工具自检
- 上游项目：`https://github.com/aoyunyang/spider-king-skill`（MIT License）

## Bottom Line

当一个站点看起来"只能用浏览器"时，问三个问题：

1. 真实请求是什么？
2. 真正在动的状态是什么？
3. 那个状态能在本地重建吗？

这三个问题一旦用 wire 证据和可重复的重放回答了，大部分目标就塌了。