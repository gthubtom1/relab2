# MCP 路由手册（MCP Routing Playbook）

> **来源声明**：本文改编自外部仓库 `aoyunyang/spider-king-skill`（MIT License）的 `mcp-routing-playbook.md`。原始内容为英文原文，此处译为中文并按本包六段式规范重排；技术术语保留英文原词并附中文。**工具清单已按本机实测状态重写**（见文末「源文档勘误」）。
>
> **什么时候用**：选「下一个该激活哪个 MCP 家族」时。**它不替代**启动门（Startup Gate）、家族分诊、浏览器交接或交付门。
>

> ★★ **本机 playwright 必须显式指定浏览器**（2026-10-10 实测）：
> `launch()` 默认启动会报 `Executable doesn't exist at %LOCALAPPDATA%\ms-playwright\chromium_headless_shell-1234\...`
> —— python 包期望 1234，本机装的是 **1243**，版本号对不上。
> **可用写法**：`p.chromium.launch(channel="msedge")`（实测能起、能渲染、能读 DOM），
> 或 `launch(executable_path=<显式路径>)`。照抄裸 `launch()` 一定失败。
> 

---

## 适用信号（Recognition signals）

- 你要在多个工具族之间选一个，但选之前没定分支
- 有人建议「把所有 MCP 都开起来」
- 你在纠结「这个目标到底需不需要浏览器」
- 一个历史 case 建议了某个工具，但当前挂载表里根本没有它
- 你想知道「本机 web 侧 MCP 到底有没有」

## 前置（Entry conditions）

1. **先跑启动门的 intake 分支判定**（`live-target` / `artifact-only` / `continuation`），见 `../triage/startup-triage-playbook.md`。
2. **先做能力快照**：读当前 agent 工具注册表，记录 `available_mcp` / `missing_mcp`。
3. **先定指纹压力等级**，再定基线主机。

## 步骤（Working method）

### 本文的目的（Purpose）

把**已安装的 MCP 家族**映射到本包概念上：

- **intake（接入模式）**：`live-target`、`artifact-only`、`continuation`
- **证据角色（evidence roles）**：`fingerprint-baseline`（指纹基线）、`debugger-trace`（调试器追踪）、`cdp-bridge`
- **基线主机（baseline hosts）**：原生 Chromium（源文档默认 `chrome-devtools`）、Camoufox 或托管 profile（**本机无**）
> （★ 本机无 chrome-devtools / Camoufox MCP —— 见 SKILL.md「来源声明」实测记录；本机基线主机是 `playwright` 的 `launch(channel="msedge")`）
- **路线所有者（route owners）**：`evidence-reuse`、`chromium-recon`、`browser-hook`、`static-ast`、`env-patch`、`transport`、`verifier`、`pure-python-rebuild`、`python-collector`
- **浏览器归属（ownership）**：单一 `TARGET_ACTIVE` 家族，顺序交接（sequential handoff）

**MCP 工具只用于取证（evidence gathering）。** 最终的 `compact-replay` 与 `collector` 路径必须**既无浏览器、也无 MCP 运行时**。

### Auto judge（从信号推分支，不要事后找理由）

| 优先级 | 信号 | 自动决策 |
|---|---|---|
| 1 | HAR / 请求文本 / JS / WASM / cookie-token 样本 / 固定向量已经够，且不需要新的线上接受性证明 | `artifact-only`；**不做 Camoufox / Chrome / `js-reverse` 的仪式性动作** |
| 2 | 只有一个裸 URL，或需要当前页面 / 端点 / 会话的证明 | `live-target` |
| 3 | 同目标、同环境、同目标继续 | `continuation`；复用当前 gate，只重开变更面 |
| 4 | 需要线上，且指纹压力低或未知 | 基线主机 = ★ **本机 `playwright` 的 `launch(channel="msedge")`**（上游默认 `chrome-devtools` 本机不存在；裸 `launch()` 亦会失败） |
| 5 | 需要线上，且指纹压力高 | 基线主机 = Camoufox 或托管 profile（**本机无 → 报 host gap**） |
| 6 | 已找到候选业务请求，需要变更点 / initiator | 若有 debug attach 则交接给 `js-reverse`（**本机替代：`frida`**） |
| 7 | 基线成功但无 debug attach 面 | 导出产物，记录 `debugger_attach_gap`，转离线 |
| 8 | 变更点与移动字段可离线重建 | **停掉浏览器主机；只做纯 Python 交付** |

**指纹压力信号（压力强时才升级基线主机）**：

- 干净路径上存在明确的指纹 / 反爬 / 环境风险门
- 原生或自动化标记的浏览器被拒，而普通浏览本应通过
- 同一出口路径上反复出现「被污染的环境」失败
- 用户要求反检测或托管 profile
- 同家族的历史证据表明需要托管主机

**默认保守**：不确定时用 `chrome-devtools`，**不是** Camoufox。（**本机**：用 `playwright`，不是「不存在的东西」。）

### 角色绑定（Role binding）

| 角色 / 面 | 源文档首选 | 源文档备选 | 并发规则 |
|---|---|---|---|
| `fingerprint-baseline` ACTIVE | `chrome-devtools` on 原生/可 attach 的 Chromium | 指纹压力高时用 Camoufox/托管 profile 干净基线 | **唯一的浏览器 ACTIVE 所有者** |
| `debugger-trace` ACTIVE | 交接后的 `js-reverse` | **没有第二个并行浏览器** | 只能在基线交接后；需要 debug attach |
| `cdp-bridge` | 当前 ACTIVE 所有者下的 attach/debug 端点 | 同上 | **绝不做第三个并行所有者** |
| 被动线存储（passive wire-store） | `reqable`、HAR 文件、已存的 `network.jsonl` | 同左 | 可与 ACTIVE 共存 |
| wire 可见性 | `WireMCP`、PCAP 文件 | 同左 | 可选；**不证明 signer** |
| ENV / host provider | Camoufox、AdsPower Local API、其他托管 profile 启动器 | 同左 | 只准备 host；**不拥有最终 collector** |
| 离线路线（offline routes） | `static-ast`、`env-patch`、pure-python rebuild | 同左 | **不需要浏览器 MCP** |

**Camoufox 是「基线主机 / ENV 面」，不是 `js-reverse` 的替代，也不是 collector 运行时。**

### 硬顺序 W1（Hard sequence）

用户需要新鲜页面 / 端点证据时的默认 web live 路径：

```text
能力快照（不做双目标预热）
  -> Auto Judge：intake + 指纹压力 + attach 可用性
  -> 可选的 host/ENV 打开（Camoufox 或托管 profile）
     —— 只在压力高或用户明确要求时
  -> fingerprint-baseline TARGET_ACTIVE：
       默认手段：原生 Chromium 干净基线 + 候选业务请求
       升级手段：Camoufox/托管 host 干净基线 + 候选业务请求
  -> 顺序交接（BASELINE_PARKED 或 RETAINED_EXCEPTION）
  -> js-reverse TARGET_ACTIVE（当 debug attach 存在）：
       initiator、变更点、脚本、WS 等
  -> 若无 attach：导出产物 + debugger_attach_gap + 转离线
  -> 可选的被动线存储关联
  -> 离线重建（无浏览器 MCP / 无 Camoufox 运行时）
  -> 固定输入证明 + 重复线上 HTTP replay
  -> 针对声明形态的交付门
```

**不要把基线主机动作和 `js-reverse` 目标动作放进同一个并行工具批次。**

### 分诊表（Triage table）

| 情形 | intake / 路线倾向 | 基线主机 / ACTIVE | 被动 / ENV |
|---|---|---|---|
| HAR、请求文本、cookie/token 样本，或 reqable 历史；要解释或起草重放 | `artifact-only` + `evidence-reuse` | 无 | reqable / 文件（**本机：`network.jsonl` + `tshark`**） |
| JS/WASM 文件还原或固定向量 | `artifact-only` + `static-ast` / `pure-python-rebuild` | 无 | fixtures |
| 裸 URL 或未知站点；低指纹压力 | `live-target` + `chromium-recon` | `chrome-devtools` 优先，再 `js-reverse`（**本机：`playwright` → `frida`**） | 可选 reqable（**本机：mitm**） |
| 裸 URL 或未知站点；高指纹压力 | `live-target` + host 优先基线 | Camoufox/托管 host 基线，再 `js-reverse`（若 attach 存在）（**本机：无 host provider → 报 gap**） | Camoufox/AdsPower（**本机无**） |
| 请求已知；字段轮转或 sign 失败 | 基线之后走 `debugger-trace` | `js-reverse`（**本机：`frida`**） | reqable 看 wire 真相（**本机：mitm**） |
| 已明确存在强多 profile / 反检测需求 | `live-target`，host/ENV 优先 | 判定后的基线主机，再 attach 调试器 | Camoufox 或 AdsPower（**本机无**） |
| 浏览器能跑，stdlib/脚本在应用语义前就死 | `transport` | 通常无 | 可选 wire 可见性（**本机：`tshark`**） |
| 验证器 / 预热 / sidecar 重 | `verifier-gated` live 链 | 先基线再 `js-reverse` 取有序 transcript（**本机：先 `playwright` 再 `frida`**） | reqable 冻结顺序（**本机：mitm 流落盘**） |
| 交付 collector | `python-collector` | 无 | 仅历史证据 |

**URL 与足够的离线产物同时存在时，保持 artifact-led**，直到需要线上接受性、变更点证明或新鲜会话证据。

### 能力与可用性（Capability and availability）

**路由之前：**

1. 检查当前 agent 工具注册表 / schema
2. 记录浏览器与可选家族的 `available_mcp` / `missing_mcp`
3. 记录浏览器模式：`launch` / `attach` / `unavailable`
4. 记录基线主机选项：原生 Chromium / Camoufox / 托管 profile / 无
5. 记录是否已知一个可调试端点
6. 只从**已确认可用**的手段里选（`available_mcp` + 实际可达的本机 host provider）

规则：

- **磁盘上有源码树 ≠ 可用。**
- **本地 Python 环境里有脚本 ≠ MCP 插件可用。**
- 若某个必需的角色无法由任何可用手段满足，**在宣称理解该 live 目标之前报告阻塞项**。
- **缺 Camoufox 不阻塞**能用 `chrome-devtools` 的低压力 live 工作。
- 在只有 Camoufox 基线、缺 attach 的情况下，缺的是 `debugger_attach_gap`，**不是**静默的成对成功。
- 只在注册表、浏览器模式或目标上下文变化时刷新快照。

### 被动线存储（Passive wire stores）

**何时用 reqable 或 HAR**（本机形态见括号）：

- 流量已被捕获，或正在本地摄取
- 浏览器跑完之后，需要对 HTTP/WS 做有序检索
- 用户明确要求以 artifact 为主分析

**不要用被动存储来：**

- 在 intake 确实是 `live-target` 时跳过 web live 首轮证据
- 替代 initiator 或变更点证明
- 充当最终 collector 运行时

**当浏览器状态与捕获的出站数据冲突时，信 wire 出站数据。**

### 环境提供方（Environment providers）

用 Camoufox、AdsPower 或其他 profile / host 管理器，**只为**造一个目标兼容的基线环境。

**当还需要调试器工作时，必要的桥接：**

```text
打开 host/profile（Camoufox 或托管 profile）
  -> 当该 host 拥有 fingerprint-baseline 时，收集干净基线请求
  -> 可用时取得可调试端点或浏览器 URL
  -> 只做 js-reverse / chrome-devtools 的 attach
  -> 禁止为同一任务再启第二个匿名浏览器
```

规则：

- host/profile 启动本身**不是协议证明**，**也不是** collector 交付
- 若拿不到可调试端点，保留干净基线产物，记录 `debugger_attach_gap` 或 ENV 阻塞项，**转离线**，而不是编造 initiator 证据
- Camoufox 即使在后期调试 attach 不可用时，仍可在高压力目标上满足 `fingerprint-baseline`；但**仍不得在没有 attach 证据的情况下宣称完整的成对调试理解**
- 可移植的本机端点与启动占位符属于 `./local-mcp-environment.md`；机器私有路径留在共享技能包之外

### Wire 可见性（Wire visibility）

**用 WireMCP 或 PCAP 做**（本机用 `tshark`）：

- 抓包审查
- 粗粒度的会话 / 协议层级
- 支撑一个传输层怀疑

**不要把 WireMCP 成功当成：**

- 单凭它就构成 JA3 或完整传输 profile 证明
- signer 还原
- 业务接受

**本机 `tshark` 示例**（路径本机可用）：

```powershell
& (Resolve-ReverseToolSpec -Name 'tshark').Command -r flow.pcapng -Y "http.request" -T fields -e http.host -e http.request.uri
```

传输层准入相关的工作走 `./transport-pre-gate-playbook.md` 与相关传输参考。

### 停止规则（Stop rules）

**当以下条件成立时，停掉浏览器 MCP 与 host：**

- 规范化变更点与移动字段已知到足够离线重建
- 已存在固定输入向量，只剩 Python parity

**拒绝标注 `collector` 当：**

- 成功仍需实时页面驱动、手动点击、Camoufox/Chrome profile 状态、或 MCP 浏览器状态
- 只有一次幸运的浏览器支撑的成功
- helper 加载成功是唯一证据

**永远允许的停止形态**：诚实的 `evidence`、`local-proof`，或一个具名的外部阻塞项。

### 范围外的平台（Out of scope platforms）

本包是纯 web。以下不在主范围内：

- Android / 原生 app 逆向家族，如 `jadx`、`ida`、`frida`
- 小程序解包器，如 `wedecode`

**若用户主要目标是 APK、原生 app 或小程序：**

- 不要编造 web 成对浏览器首轮证据作为仪式
- 不要假装平台 MCP 成功就是本包的 web collector 路径
- 报告范围外或约束未满足的阻塞项，**不要**强推 web live 序列

只有当真实业务路径仍是 web / H5 / 浏览器发起的协议问题时，才继续用本包。

## 判据（Verification checklist）

**「路由决策成立」= 以下全部为真：**

1. **Auto Judge 的分支已记录**，且**在第一次目标动作之前**（不是事后补理由）。
2. **能力快照已做**：`available_mcp` / `missing_mcp` / 浏览器模式 / 基线主机选项 / 已知调试端点。
3. **选中的手段全部在快照的可用列表里** —— 没有任何一项是「磁盘上有」或「应该有」。
4. **至多一个浏览器家族 `TARGET_ACTIVE`**，且基线主机动作与调试器动作**不在同一并行批次**。
5. **`artifact-only` 路线没有启动浏览器**；`out-of-scope`（APK / app / 小程序）路线没有编造 web 成对首轮证据。
6. **高指纹压力下缺 host provider 时报了 host gap**，而不是静默降级假装干净基线存在。
7. **缺 attach 时记录了 `debugger_attach_gap`**，而不是宣称成对调试成功。
8. **任何缺失的 web 侧 MCP 都已在本机替代列中定位**，或已明确报出能力阻塞项。
9. **被动线存储没有被当成最终 collector 运行时**。
10. **停止形态诚实**：最终交付不含浏览器依赖；不足时降级为 `evidence` / `local-proof` 或具名阻塞项。

## 常见坑（Common traps）

见 `../principles/anti-patterns-playbook.md` 中关于 MCP 误用的条目。**以下为直接禁止：**

- 一次性开所有 MCP 家族
- 并行跑基线主机动作和 `js-reverse` 目标动作
- 在纯 HAR / artifact 任务、或范围外的 APK/app/小程序任务上强行双浏览器首轮证据
- 在低风险或 `artifact-only` 工作上默认用 Camoufox
- 把 Camoufox/ENV 启动或被动捕获当成 collector 交付
- 把 Camoufox 当成 `js-reverse` 的替代
- 只有非 attach 主机基线时宣称成对调试成功
- 缺失 MCP 面之后编造 initiator、变更点或线上接受性
- **本机特有**：照抄 `chrome-devtools` / `js-reverse` / `Camoufox` / `AdsPower` / `reqable` / `WireMCP` —— **本机一个都没有**（详见本文顶部与 `./local-mcp-environment.md`）

## 相关（Related）

- `./local-mcp-environment.md` —— **本机到底有什么/没有什么**（先查这份，再回来选路线）
- `./hook-techniques.md` —— 本机 hook 路径（frida / playwright）
- `../triage/startup-triage-playbook.md` —— 启动门与 intake 判定
- `../triage/tool-playbook.md` —— 能力快照与生命周期语义的规程
- `../principles/anti-patterns-playbook.md` —— 反模式库
- `../principles/doctrine-index.md` —— 教条 7（交付门高于便利）、教条 10（观察者效应）
- `./transport-pre-gate-playbook.md` —— 「浏览器能跑但 stdlib 在应用语义前就死」时的路线
- `../deliver/delivery-gate-playbook.md` —— 停止形态的验收
- `../../../field-journal/KB-SOURCES.md` —— 本包知识库来源与改编约定

---

## 源文档勘误（改编时修正）

1. **源文档整篇以 `chrome-devtools` / `js-reverse` 两个 MCP 家族为默认手段**，并把它们写进「角色绑定」表的「首选」列。**本机 agent 工具注册表未挂载任何 web 侧 MCP**（已挂载的 `pyghidra-mcp` / `idapro` / `ida-pro-mcp` / `angr-mcp` / `x64dbg-automate-mcp` 全是逆向侧）。源文档照抄会在「按挂载表选工具」这一步直接空转。改编保留了**全部方法论与角色结构**，把每个角色的工具列改为「源文档首选（本机不可用）+ 本机替代」双列，并在文首与常见坑中显式声明这一差异。
2. **源文档的「Wire visibility」段只讲 WireMCP / PCAP，不给具体命令**，读者即使有 PCAP 也不知道怎么用。改编补入本机 `tshark` 的两条实际命令。
3. **源文档的「Capability and availability」第 2 条要求记录 `available_mcp` / `missing_mcp`，但没给「本机应该有什么」的基线**，读者无从判断某项缺失是否正常。改编在顶部补入本机已挂载 MCP 的完整清单，使「缺失」这一判断可执行。
4. **源文档的「Passive wire stores」把 reqable 列为默认被动存储**。本机未安装 reqable。改编在相关位置一律给出本机替代（工作区 `network.jsonl` + `tshark` / `mitmdump`），但**保留 reqable 作为「如果装了就用它」的上游能力描述**，因为它是方法论的一部分而非本机事实。
5. **源文档没有区分「web 侧 MCP 缺失」与「整个 skill 不可用」。** 改编在判据第 8 条明确：web 侧 MCP 缺失时，必须先在本机替代列中定位，找不到才报能力阻塞项 —— 避免读者把「没有浏览器 MCP」误读成「这条路全断了」，而错过本机可用的 `playwright` / `frida` 路径。