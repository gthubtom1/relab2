# 本机 MCP 环境与能力（Local MCP Environment）

> **来源声明**：本文改编自外部仓库 `aoyunyang/spider-king-skill`（MIT License）的 `local-mcp-environment.md`。原始内容为英文原文，此处译为中文并按本包六段式规范重排；技术术语保留英文原词并附中文。**工具清单已按本机实测状态重写**（见文末「源文档勘误」）。
>
> **什么时候用**：需要知道「这台机器上**现在到底有什么**、哪些没有」的时候。通用路由教条在 `./mcp-routing-playbook.md` 和 `../triage/tool-playbook.md`，本文只回答「本机现状」。
>

---

## 适用信号（Recognition signals）

- 准备开某个工具族，但不确定本机到底挂没挂
- 某条路线文档让你用 `chrome-devtools` / `js-reverse` / `Camoufox` / `AdsPower` / `Reqable` / `WireMCP`，你想先确认它们存在
- 需要填一个占位符（placeholder）却不想把机器私有路径写进技能包
- 挂载表发生了变化（重启、注册表变更、工具掉线）

## 前置（Entry conditions）

1. **先跑 Auto Judge 定分支**，再看本机手段。分支顺序见 `./mcp-routing-playbook.md` 的 Auto judge 表。
2. **区分「磁盘上有源码」与「会话里可用」** —— 后者才是能力。

## 步骤（Working method）

### 本机 MCP 注册表（实测，2026-10）

**本机已挂载的 MCP 全部是逆向侧，没有任何 web 侧 MCP。**

| MCP server | 传输 | 能力 | 本机状态 |
|---|---|---|---|
| `pyghidra-mcp` | stdio | Ghidra 反编译，20 个工具 | ✅ 已实测握手；需 `JAVA_HOME` + `GHIDRA_INSTALL_DIR` |
| `idapro` | http `127.0.0.1:13337/mcp` | IDA，69 工具 | ⚠ 按需启动（用前跑 `start.ps1`）；`idb_open` 需 IDA license（本机为示例许可） |
| `ida-pro-mcp` | stdio | IDA 工具（GUI 内插件侧） | ⚠ 同样需 license |
| `angr-mcp` | stdio | 符号执行 | ✅ 已实测握手 |
| `x64dbg-mcp` | stdio | x64dbg 自动化，48 工具 | ✅ 已实测握手 |

注册位置：`~/.omp/agent/mcp.json`（4 个 stdio + 1 个 http）。
`13337` **按需启动**（2026-10-14 起）：原「每分钟巡检保活」任务 `reverse-skill-ida-mcp` 已按用户要求停用（不用时不后台跑，也避免每分钟闪窗）；需要时跑 `ida-reverse/scripts/start.ps1`（冷启约 9s）。

**源文档里点名的 web 侧 MCP，本机一个都没有**：

| 源文档工具 | 本机状态 | 本机替代 |
|---|---|---|
| `chrome-devtools`（MCP） | ❌ **未挂载** | `playwright`（本机可用，`<playwright 浏览器>` 已装） |

> ★★ **本机 playwright 必须显式指定浏览器**（2026-10-10 实测）：
> `launch()` 默认启动会报 `Executable doesn't exist at %LOCALAPPDATA%\ms-playwright\chromium_headless_shell-1234\...`
> —— python 包期望 1234，本机装的是 **1243**，版本号对不上。
> **可用写法**：`p.chromium.launch(channel="msedge")`（实测能起、能渲染、能读 DOM），
> 或 `launch(executable_path=<显式路径>)`。照抄裸 `launch()` 一定失败。
> 
| `js-reverse`（MCP） | ❌ **未挂载** | `frida 17.17.0`（本机可用）；Node 侧见 `../../profiles/env-patch/index.md` |
| `WireMCP` | ❌ **未挂载** | `tshark 4.6.0`（本机可用） |

**结论（必须记住）**：本包文档里出现的 `chrome-devtools` / `js-reverse` / `Camoufox` / `AdsPower` / `Reqable` / `WireMCP` 序列，**在本机是「目标架构」而非「可执行脚本」**。照抄前先落到上表的替代列。

### 本机已验证的非 MCP 工具链（实测）

| 能力 | 可执行路径 | 版本 |
|---|---|---|
| Python | `(Resolve-ReverseToolSpec -Name 'pyre').Command` | 3.12.0 |
| Node | `(Resolve-ReverseToolSpec -Name 'node').Command` | v24.20.0 |
| tshark | `(Resolve-ReverseToolSpec -Name 'tshark').Command` | 4.6.8 |
| mitmdump / mitmproxy | `(Resolve-ReverseToolSpec -Name 'mitmdump').Command` | 12.2.3 |
| frida（含 17 个 `frida-*` 辅助工具） | `(Resolve-ReverseToolSpec -Name 'frida').Command` | 17.17.0 |
| playwright | `(Resolve-ReverseToolSpec -Name 'pyre').Command -m playwright` | 1.62.0（浏览器 `<playwright 浏览器>` 已装） |
| curl_cffi | Python 包 | 0.16.3 |
| requests | Python 包 | 2.32.3 |

**本机没有的**（不要照抄涉及它们的流程）：

| 缺失项 | 说明 | 替代 |
|---|---|---|
| `iv8` | 社区运行时，PyPI 上无该发行版 | `node`（轻量）/ `playwright`（重）；`../crypto/iv8-runtime-cheatsheet.md` 的形态**未在本机验证** |
| `reqable` | 未安装 | `tshark`（读 pcap）/ `mitmdump`（实时流） |
| `Camoufox` | 未见安装 | `playwright` + 受控 profile |
| `AdsPower Local API` | 未见安装 | `playwright` 自建持久化 profile |
| `esprima` / `acorn` / `@babel/parser` | npm 未装 | 需先装；见 `../../profiles/static-ast/index.md` |
| `(Resolve-ReverseToolSpec -Name 'pyre').Command` | **空壳，不要用** | 用系统 `(Resolve-ReverseToolSpec -Name 'pyre').Command` |

### Auto Judge 分支 → 本机手段映射

**只有在 Auto Judge 先选定分支之后，才用下面这张表：**

| Auto Judge 分支 | 本机优先手段 |
|---|---|
| `artifact-only` | 只用工作区文件 / `js_reverse_cache/tasks/<id>/` 里的产物；**不为走流程而启动浏览器** |
| 低指纹压力 `live-target` | `playwright` 受控启动 + HAR 落盘 → 顺序交接 → `frida` 取证 |
| 高指纹压力 `live-target` | 本机**无 Camoufox / AdsPower**，这是**能力缺口**：如实报告，回退到 `playwright` + 自建持久化 profile，并记录 host gap |
| 需要 attach 调试器 | `playwright.chromium.connect_over_cdp()` 接已开调试端口的 Chrome；或直接 `frida` 挂进程 |
| 抓包 / wire 可见性 | `tshark` 读 pcap；`mitmdump` 做实时改写与流落盘 |
| 纯离线重建 | `python 3.12` + `node`；静态 AST 需先装解析器 |

### 本机常用端点

**典型默认值**，与实际不符时以运行中的进程或操作者配置为准。

| 服务 | 典型本机值 | 占位符 / 覆盖 |
|---|---|---|
| Chrome 远程调试 | `http://127.0.0.1:9222` | `<chrome-debug-url>` |
| mitmproxy 监听（本机实际做法，**替代 reqable**） | `http://127.0.0.1:8899` | `<mitm-listen-port>` |
| IDA MCP（本机已挂载） | `http://127.0.0.1:13337/mcp` | 已固定，无需占位符 |
| AdsPower Local API | 本机无 | `<adspower-local-api>` / `<adspower-api-key>` |
| Camoufox / 自定义 host 调试 | 本机无 | `<camoufox-debug-endpoint>` |

**本机替代 reqable 的两条命令**（均为本机可用路径）：

```powershell
# 方式一：mitmproxy 实时流落盘
& (Resolve-ReverseToolSpec -Name 'mitmdump').Command --listen-port 8899 --save-stream-file flow.mitm

# 方式二：tshark 离线读 pcap（本机替代 reqable 的 HAR 检索）
& (Resolve-ReverseToolSpec -Name 'tshark').Command -r flow.pcapng -Y "http.cookie" -T fields -e http.request.full_uri -e http.cookie
```

### Chrome 调试 profile 约定（源文档的通用要求，本机同样适用）

用一个**专用调试 profile 目录**，不要用日常浏览 profile。

```text
<mcp-host-root>/
  ChromeDebug/                 # attach-only Chrome 的 user-data-dir
  start_chrome_debug.bat
```

```text
chrome.exe --remote-debugging-port=9222 --user-data-dir="<chrome-debug-user-data-dir>"
```

规则：

1. `<chrome-debug-user-data-dir>` **必须在 attach 之前就存在**
2. 启动器必须解析到**同一个**目录。启动器还指向过时的绝对路径时，attach 环境即为损坏，直到路径被修正
3. 绝对路径优先用环境变量或本地 overlay，例如 `SPIDER_KING_CHROME_USER_DATA_DIR` / `SPIDER_KING_CHROME_DEBUG_URL`
4. 启动后，只用 `/json/version` 或工具 schema 里确认过的浏览器 URL / WebSocket 端点去 attach
5. **绝不**把操作者专属的绝对路径写进本共享技能文件

### Camoufox 主机说明（源文档要求，本机为缺口）

Camoufox 是高指纹压力下的可选本机容量，**既不是常开默认，也不是 MCP 家族**。

源文档要求的使用纪律本机**继续适用**，但执行前提不同：

1. **本机未安装 Camoufox。** 只有当 Auto Judge 选定高压力基线主机、或用户明确要求时，才需要它 —— 那时如实报**能力缺口**，回退到 `playwright` + 自建持久化 profile，并记录 `host gap`
2. 用它做干净基线流量、页面状态、会话清点
3. 记录它是否暴露了可供 attach 的调试面，作为 `<camoufox-debug-endpoint>`
4. 若 attach 不可用，导出请求 / HAR / 脚本并转离线；**不要**编造调试器证据
5. **绝不**让 Camoufox 进入 `compact-replay` 或 `collector` 交付

### 本地 overlay 约定（源文档要求，本机同样适用）

保持共享技能文档可移植。机器私有值用以下之一：

1. 环境变量：`SPIDER_KING_CHROME_USER_DATA_DIR`、`SPIDER_KING_CHROME_DEBUG_URL`、`SPIDER_KING_MITM_LISTEN_PORT`（**本文把原文的 `SPIDER_KING_REQABLE_REPORT_URL` 换成本机实际使用的 mitm 端口**）、`SPIDER_KING_CAMOUFOX_DEBUG_ENDPOINT`
2. 技能树**之外**的文件，例如 `<workspace>/spider-king.local.md`
3. 单次会话里的操作者口述

**绝不**把 `local-mcp-environment.local.md`（本包未落地）（上游文件，未随本包落地） 里的秘密、API key、cookie 或家目录路径写进共享包。

## 判据（Verification checklist）

**「attach 模式可用」= 预检全部通过：**

1. **启动器引用的调试 profile 目录确实存在。**
2. **配置的调试端点确实应答**（`http://127.0.0.1:9222/json/version`）。
3. **当前 agent 会话的挂载表里确实列出了你要用的工具** —— 不是磁盘上有源码。
4. **只有当 Auto Judge 分支选定了那个主机时**，才确认 Camoufox 的启动 / attach。
5. **只有当被动存储路由真的依赖它时**，才确认 Reqable ingest。**本机做法**：确认 `tshark` 的 pcap 路径或 `mitmdump` 的监听端口可用。
6. **失败时**：记录一个**能力阻塞项（capability blocker）**，并回退到可用模式或更低的交付形态 —— **不得**继续假装该能力存在。

**额外（针对本机 web 侧 MCP 全缺）**：

7. **凡是要开 `chrome-devtools` / `js-reverse` / `Camoufox` / `AdsPower` / `Reqable` / `WireMCP` 的路线，都已在「本机替代」列里找到对应物**，或已如实报出 host gap。
8. **挂载表发生变化时，重新做了一次能力快照**，没有沿用旧快照推断 `TARGET_ACTIVE` 归属。

## 常见坑（Common traps）

- 把「磁盘上有 MCP 源码目录」当成「会话里挂载了」
- 本地 Python 环境里有某个脚本，就认为对应 MCP 插件可用
- 照抄源文档的 `Reqable` 端点（`127.0.0.1:18765/...`）—— **本机没装 Reqable**，那个端口不会有服务
- 照抄 `Camoufox` / `AdsPower` 流程 —— **本机未安装**
- 期待 `iv8` 可用 —— **本机无**
- 用了 `(Resolve-ReverseToolSpec -Name 'pyre').Command` —— **它是空壳**
- 把调试 profile 指向日常浏览 profile
- 启动器指向已失效的绝对路径，却把 attach 失败归因于目标防护
- 把机器私有绝对路径或 API key 提交进技能包

**本机 MCP 特有的坑**：

- **stdio 型 MCP server 永不退出** —— 探测时用 `ReadToEnd()` 会永远卡住，表现为「超时、零输出、像没装」。必须逐行读（`StreamReader.ReadLine()`）。
- **`idapro` 走的是 HTTP `13337`，不是 stdio** —— 配错形态的表现是「握手一直 TIMEOUT」。
- **GUI 孪生一律禁拉** —— `die.exe`→`diec`、`ida.exe`→`idat`、`Wireshark.exe`→`tshark`、`x64dbg.exe`→`headless`、`dnSpy.exe`→`dnSpy.Console`。

## 相关（Related）

- `./mcp-routing-playbook.md` —— 「该开哪个工具族」的判定（**先看那里的 Auto judge，再回本文查本机有没有**）
- `./hook-techniques.md` —— 本机 hook 路径（frida / playwright）
- `../triage/tool-playbook.md` —— 能力快照与生命周期语义的规程
- `../triage/startup-triage-playbook.md` —— 预检在启动门中的位置
- `../principles/doctrine-index.md` —— 教条 10（观察者效应）
- `../crypto/iv8-runtime-cheatsheet.md` —— **iv8 本机无**，该文档形态未在本机验证
- `../../../../TOOL-CHAIN.md` —— 本包更上层的工具链总览

---

## 源文档勘误（改编时修正）

1. **源文档的「Expected local roles」与「Common endpoints」两张表全部指向本机不存在的组件**：`Camoufox`、`AdsPower Local API`（`127.0.0.1:50325`）、`Reqable MCP ingest`（`127.0.0.1:18765/report`）、`WireMCP`。源文档自己声明这些是「典型默认值，需按实际覆盖」，但**照抄会让人以为这些服务应该已经在那儿**。改编把工具清单整体替换为本机实测表，并把 `reqable` 那一行换成 `mitmdump 8899` 的实际命令。
2. **源文档通篇以 `chrome-devtools` / `js-reverse` 两个 MCP 家族为默认手段**，并把它们列为「本机手段（local means）」。**本机 agent 工具注册表未挂载任何 web 侧 MCP。** 改编把「本机手段」一列整体替换为本机实测可用的 `playwright` / `frida` / `tshark` / `mitmdump`，并在多处显式提醒：文档里出现的 web 侧 MCP 序列是**目标架构**而非可执行脚本。
3. **源文档的 `Auto-judge local means` 表把「高压力 live-target」映射到「先启 Camoufox」，本机无法执行。** 改编把这一行改写为「如实报能力缺口并回退」，而不是删掉高压力分支 —— 因为「高指纹压力」这个**信号**本身仍然需要被识别并上报。
4. **源文档没有给出抓包的替代命令。** 它假设「Reqable 已配置」是既定前提。本机补入 `tshark -r ... -T fields` 与 `mitmdump --save-stream-file` 两条实际可跑命令。
5. **源文档的环境变量清单里有 `SPIDER_KING_REQABLE_REPORT_URL`，而本机不用 Reqable。** 改编替换为 `SPIDER_KING_MITM_LISTEN_PORT`，其余变量名保持不变。
6. **源文档 `Preflight checks` 第 3 条「确认 agent 会话确实列出了 `chrome-devtools` / `js-reverse` 工具」在本机恒为失败。** 改编保留这条检查的**精神**（以挂载表为准，不以磁盘为准），但把被检查的对象换成本机实际可能使用的家族，并在判据第 3 条重申该原则。