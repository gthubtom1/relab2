# 工具选型手册（Tool Playbook）

> **来源声明**：本文改编自外部仓库 `aoyunyang/spider-king-skill`（MIT License）的 `tool-playbook.md`。原始内容为英文原文，此处译为中文并按本包六段式规范重排；技术术语保留英文原词并附中文。**本文是本组 11 篇里本机化改动最大的一篇**：源文档通篇围绕一套自带 MCP 浏览器工具链（`chrome-devtools` / `js-reverse` / Camoufox / AdsPower / Reqable / `iv8`），本机不存在这套环境，全表已按本机实际能力重写。
>
> **什么时候用**：拿到一个逆向任务，需要在「先做什么、后做什么、拿哪个工具」之间做选择时。这篇是**任务到工具的快速地图**。
>

---

## 适用信号（Recognition signals）

- 刚接到一个逆向任务，还没决定用哪个工具起手
- 知道要抓包，但不确定是开浏览器、上 `node` 还是直接读已保存的源码
- 需要断点 / hook，但不清楚当前有哪些手段
- 某个工具在源文档里被提到，你要确认**本机到底有没有**
- 需要把「我的代码算对了」升级成「线上真的接受」

## 前置（Entry conditions）

1. **先跑完启动门**：`./startup-triage-playbook.md`。在 intake mode 和家族判定出来之前就选工具，是本技能最常见的返工原因。
2. **确认过本机能力**。直接跑：

```powershell
& (Resolve-ReverseToolSpec -Name 'pyre').Command -c "import importlib.util as u; print({m: bool(u.find_spec(m)) for m in ['frida','playwright','curl_cffi','requests','mitmproxy']})"
& (Resolve-ReverseToolSpec -Name 'node').Command -v
& (Resolve-ReverseToolSpec -Name 'tshark').Command -v
& (Resolve-ReverseToolSpec -Name 'mitmdump').Command --version
```

> ⚠️ **`(Resolve-ReverseToolSpec -Name 'pyre').Command` 实测存在但缺关键模块**（本机实测：`frida` / `playwright` / `curl_cffi` / `mitmproxy` **均不在其中**，只有 `requests`）。本文所有 Python 命令一律用 `(Resolve-ReverseToolSpec -Name 'pyre').Command`。

---

## 本机能力总表（Capability table）

### ✅ 本机可用（实测确认）

| 能力 | 完整路径 | 版本 | 用途 |
|---|---|---|---|
| Python | `(Resolve-ReverseToolSpec -Name 'pyre').Command` | 3.12.0 | 采集器主体、重放、编解码 |
| Node.js | `(Resolve-ReverseToolSpec -Name 'node').Command` | v24.20.0 | 本地 JS helper、`vm`/`node:vm` 宿主 |
| tshark | `(Resolve-ReverseToolSpec -Name 'tshark').Command` | 4.6.8 | **离线**读 pcap，抽 wire 字段 |
| mitmdump | `(Resolve-ReverseToolSpec -Name 'mitmdump').Command` | 随 Python 安装 | 实时 MITM、看/改请求头、落盘 flow |
| frida | Python 模块已装 | — | 运行时 hook，注入到浏览器或目标进程 |
| playwright | Python 模块已装 | — | 真浏览器 + CDP（网络事件、断点、`add_init_script`） |
| curl_cffi | Python 模块已装 | — | 浏览器指纹 impersonation（对应「伪装传输」） |
| requests | Python 模块已装 | — | 普通 HTTP |

### ❌ 本机没有（源文档依赖，改动重点）

| 源文档里的东西 | 本机状态 | 本机替代路线 |
|---|---|---|
| **MCP `chrome-devtools`** | 无该 MCP 工具族 | `playwright`（含 CDP 网络事件、`take_screenshot`、快照） |
| **MCP `js-reverse`** | 无该 MCP 工具族 | `playwright` 的 CDP `Debugger` 域 + `frida` hook |
| **Camoufox / AdsPower**（managed host） | 无 | 无。**如实记 role gap**，不要假装做了指纹基线升级 |
| **iv8**（嵌入式 JS 运行时） | 无（社区运行时，PyPI 上不存在该发行版） | `node`（够用时首选）；需要 DOM/定时器语义时用 `playwright` 跑离线页。`../crypto/iv8-runtime-cheatsheet.md` 的 API 形态**未在本机验证**，仅供有该运行时时参考 |
| **Reqable** | 无 | `mitmdump`（实时）+ `tshark`（离线 pcap）+ 用户提供的 HAR |
| **HAR 导入为「被动 wire store」** | 无 Reqable 的历史库 | `mitmdump --save-stream-file` 或 `tshark` 落盘；HAR 由用户提供则直接读 |
| **esprima / acorn / @babel/parser**（npm） | 未安装 | 静态 AST 路线（`../../profiles/static-ast/`）**需先装依赖**才能跑；否则退回正则搜索 + `node` 执行 + 人工读代码 |
| `scripts/*.py`（check_reverse_env 等） | 本包**没有** `scripts/` 目录 | 用上面「前置」里的四条体检命令替代 |

---

## 步骤（Working method）

### 首选顺序（Preferred order）

1. 抓一条干净的基线请求
2. 找到**真正的**请求（不是页面代码里提到的那个）
3. 追 initiator（发起方栈）
4. diff 那些会变的字段
5. 加**最窄的**、仍能保持样本的运行时证明
6. 复现**一条**稳定请求
7. **只有第一个请求可重复之后**，才谈规模化采集

偏好顺序：干净基线 > initiator 栈 > 窄证明 > 宽 hook。聚焦的源码阅读 > 把巨型 bundle 整个塞进上下文。

### 不同证据面干的是不同的事

不要让一种证明假装替代另一种：

| 证据面 | 它能证明什么 | 它**不能**证明什么 |
|---|---|---|
| initiator 栈 / 读源码 | 变更逻辑**在哪** | 真正跨过边界的是什么 |
| wire 抓包 / 请求外发 | 实际**发出去了什么** | 逻辑为什么会那样算 |
| 环境探针（canvas / descriptor / 定时器 / 原生面） | DOM、BOM、描述符、定时器、原生面的**真相** | 业务是否接受 |
| 下游业务 replay | 恢复的路径**是否真被接受** | —— |

**在局部变量里看到的值、一个安静的 hook、一个看起来很像的环境补丁，都不能盖过 wire 证据或下游业务结果。**

### 角色 → 本机手段映射

`fingerprint-baseline` / `debugger-trace` / wire 可见性三个角色与最低证明要求，见 `./startup-triage-playbook.md`。落到本机：

| 证据角色 | 本机主用手段 | 可用手段不够时的降级链 |
|---|---|---|
| `fingerprint-baseline` | `playwright` 开页 + `mitmdump`/`tshark` 看 wire | 无 managed host 可升级 → **记录 role gap**，保持「普通干净 Chrome 配置」这个诚实基线 |
| `debugger-trace` | `playwright` CDP `Debugger` 域 / `frida` | 已保存源码 → 最早的稳定断点 → 一个窄的行为保持型 hook → 离线本地执行 |
| wire 可见性 | `mitmdump` 实时、`tshark` 离线 | `playwright` 自带网络事件；用户提供的 HAR |

### 网络侦察与抓包（Recon and network capture）

#### 用 `playwright` 拿页面与网络证据

- 页面导航、跟随真实落地 URL
- 监听 `request` / `response` 事件：列出 XHR、Fetch、document、script、preflight 流量
- 按 URL / method 过滤出候选业务请求，展开看完整头与 body
- `page.screenshot()`：留证隐藏面板、验证码门、懒加载区域
- `page.content()` / `page.accessibility.snapshot()`：快速看页面结构
- CDP `Network.getResponseBody`：拿已加载资源的原始 body
- CDP `Debugger.getScriptSource` + `Debugger.setBreakpointByUrl`：追 initiator

#### 用 `mitmdump` 做实时改写与观察

```powershell
# 启动代理并把整条流落盘（-p 与 --listen-port 等价；-w 与 --save-stream-file 等价）
# 实测：这两个 flag 在本机 mitmproxy 10.3.0 上存在
& (Resolve-ReverseToolSpec -Name 'mitmdump').Command --listen-port 8899 --save-stream-file flow.mitm

# 改写请求头：用 -s 加载一个自定义 addon 脚本
& (Resolve-ReverseToolSpec -Name 'mitmdump').Command -p 8899 -w flow.mitm -s rewrite_addon.py
```

> ⚠️ **不要写 `--set flow_detail=1`** —— 本机实测 `mitmproxy.options.Options()` 中**没有** `flow_detail` 这个键（该 flag 是旧版 mitmdump 的），写了会直接报错。

定位：这是**实时、可改写**的 wire 证据面。改写脚本本身是「本地重放的原型」。

#### 用 `tshark` 离线读 pcap

```powershell
# 列出所有 HTTP 请求的 URI 与方法
& (Resolve-ReverseToolSpec -Name 'tshark').Command -r flow.pcapng -Y "http.request" -T fields -e frame.number -e http.request.method -e http.request.full_uri

# 只看 cookie 头的出现与变化
& (Resolve-ReverseToolSpec -Name 'tshark').Command -r flow.pcapng -Y "http.cookie" -T fields -e frame.number -e http.cookie

# TLS 握手失败定位（对应 transport-gated）
& (Resolve-ReverseToolSpec -Name 'tshark').Command -r flow.pcapng -Y "tls.handshake" -T fields -e frame.number -e tls.handshake.type
```

限制：tshark 是**离线**的，只对你已经抓到的 pcap 有效；它不解 TLS，所以 HTTPS 场景下只有元数据可见 —— 密文内容要走 `mitmdump` 或浏览器侧证据。

### 被动 wire store（Passive wire stores）

源文档用 Reqable / HAR / `network.jsonl`。本机对应物：

| 源文档 | 本机 | 说明 |
|---|---|---|
| Reqable 历史库 | **无** | 用 `mitmdump --save-stream-file` 或 `tshark -w` 落盘 |
| 导入的 HAR | 用户提供则直接读 | 需要 HAR→JSONL 转换时自己写，不要指望现成工具 |
| 任务局部 `network.jsonl` | 可以自己维护 | 建议在项目下 `js_reverse_cache/tasks/<task-id>/network.jsonl` |

规则：

- 用户已经给了完整抓包、且**不要求**线上验收 → 优先 `evidence-reuse`（证据复用），不要开浏览器
- 被动抓包与浏览器外发冲突时 → **信活的 wire 外发**
- 被动 store **永远不是**目标所有权，也**永远不是**采集器运行时

### 静态 JS 分析（Static JS analysis）

本机能力边界：

- ✅ `playwright` CDP `Debugger.getScriptSource`：从活页面 dump 源码

> ★★ **本机 playwright 必须显式指定浏览器**（2026-10-10 实测）：
> `launch()` 默认启动会报 `Executable doesn't exist at %LOCALAPPDATA%\ms-playwright\chromium_headless_shell-1234\...`
> —— python 包期望 1234，本机装的是 **1243**，版本号对不上。
> **可用写法**：`p.chromium.launch(channel="msedge")`（实测能起、能渲染、能读 DOM），
> 或 `launch(executable_path=<显式路径>)`。照抄裸 `launch()` 一定失败。
> 
- ✅ `node`：本地执行 JS、读 helper
- ✅ 文本/正则搜索：自己写
- ❌ **`esprima` / `acorn` / `@babel/parser` 本机未装** → `../../profiles/static-ast/` 那套 Babel AST 流程**开箱即用不了**

```bash
# 先确认 npm 侧依赖在不在（本机预期 MISSING）
& (Resolve-ReverseToolSpec -Name 'node').Command -e "['esprima','acorn','@babel/parser'].forEach(m=>{try{require.resolve(m);console.log(m,'OK')}catch(e){console.log(m,'MISSING')}})"
```

**没装之前不要承诺 AST 路线。** 降级方案：

1. 正则/字符串搜索定位候选函数名 → 手工读那一小段
2. `node` 直接执行可疑函数，用固定输入比对输出（fixed vectors）
3. `frida` / CDP 断点在线上看运行时真实形态

缺工具时的替换配方：

| 你想要的 | 本机替代 |
|---|---|
| 在 bundle 里找函数 | CDP `Debugger.searchInContent`（有该能力时）或先 dump 到本地再 grep |
| 自动代码摘要 | 读 initiator 栈 → 读变更点周围最小的源码切片 |
| 自动 crypto 检测 | 搜辅助函数名 + 比对固定输入 → `../crypto/crypto-patterns.md` |
| 自动反混淆 | 先 dump + `node` 执行 → `../crypto/obfuscation-guide.md`、`../crypto/offline-inline-deob-playbook.md`。**不要凭空造一个「自动反混淆工具」** |

已保存源码的操作注意：

- 单行巨型文件 → 先 beautify 一份工作副本，再依赖行号
- 用 `json.dumps` 落盘的 JS → 先 `json.loads` 再当源码读
- 优先 dump 后离线分析，活的插桩噪声很大

关键词包（照抄即可，用于 grep）：

- 请求路径：`"/api/"`、`"graphql"`、`"fetch("`、`"axios"`、`"XMLHttpRequest"`
- signer：`"sign"`、`"token"`、`"nonce"`、`"timestamp"`、`"trace"`、`"x-sign"`、`"beforeSend"`、`"ajaxSetup"`、`"requestId"`
- crypto：`"md5"`、`"sha"`、`"sm3"`、`"hmac"`、`"aes"`、`"rsa"`、`"crypto.subtle"`、`"native code"`
- 环境：`"navigator"`、`"canvas"`、`"webgl"`、`"performance"`、`"webdriver"`
- 探针链：`"Object.keys"`、`"Reflect.ownKeys"`、`"getOwnPropertyDescriptor"`、`"toString"`、`"document.all"`、`"JSON.stringify"`

### 动态验证（Dynamic validation）

先要一条干净基线，再用 initiator 栈和请求 diff。**知道你为什么插桩之后**，才加运行时证明。

#### 基线优先的证明流程

1. 抓一对干净的请求 / 响应
2. 用 CDP 或 `frida` 从请求跳回调用者栈
3. 读变更点周围最小的相关代码
4. 在已知的辅助函数处下断点（`playwright` CDP `Debugger.setBreakpointByUrl` 或 `frida` 的 `Interceptor.attach`），**前提是不会毒化样本**
5. 需要停在精确请求边界时，断在 XHR / fetch 上
6. 需要 before-load 观察时：`playwright` 的 `context.add_init_script()`（源文档的 `navigate_page(initScript=...)` 在本机的等价物）
7. hook 时记录：目标、事件、方法、URL、字段、调用者、决定性方法的参数、返回的子对象形状 —— **让每个捕获值都能归因到一次具体的请求边界**
8. hook 一直安静 → 这只证明**那个边界**没有，别急着下「字段不存在」的结论，先排除并发写入方或替代传输通道
9. 目标对行为敏感 → 一旦行为变化，立刻撤掉侵入式插桩重抓干净基线

#### 断点工具映射

| 想要的 | 本机用 |
|---|---|
| bundle 已压缩时按文本下断点 | `playwright` CDP `Debugger.setBreakpointByUrl`；`frida` 用 `Interceptor.attach` 按地址/符号 |
| 查看局部变量与作用域 | CDP `Debugger.evaluateOnCallFrame`；`frida` 的 `this.context` |
| 在挂起帧里打印精确的签名前字符串 / key / iv / payload | CDP `Debugger.evaluateOnCallFrame` |
| 恢复执行 | CDP `Debugger.resume`；`frida` 自动继续 |

### 会话与环境处理（Session and environment handling）

```powershell
# 取 cookie（浏览器上下文内）
# playwright: await page.context.cookies()

# 取页面自有全局（webpack cache / SDK 对象 / bootstrap helper）
# playwright: await page.evaluate("Object.keys(window).filter(k=>k.includes('Sdk'))")
```

- 如果控制台探针或隔离世界（isolated world）找不到页面自有的 wrapper / 构造器 / 全局，**在页面自有世界里重做一次证明**，再放弃这条路
- 可疑 bundle 落盘留证，便于离线 diff
- **不要**把浏览器 cookie 直接持久化成采集器凭据，除非已经证明 cookie 溯源契约，见 `../state/cookie-provenance-playbook.md`

### 本地 JS 宿主（Embedded runtime routing）

> ⚠️ **本机没有 `iv8`。** 源文档用它跑离线页 bootstrap、推进逻辑时间、观察 API 探针链。本机对应路线：

| 需要 | 本机走法 |
|---|---|
| 只需要 `document.cookie` 赋值、`navigator` / `screen` / `location` 这类**可桩化的宿主语义** | `node` + `vm` 构造最小桩，或用 `../../profiles/env-patch/` 的架构 |
| 需要真实 DOM 生命周期、定时器顺序、XHR wrapper 语义 | `playwright` 跑离线页（`page.set_content()` / 本地文件），**但它属于重活**，只在轻量桩证明不够时才上 |
| 需要完全离线、无浏览器的产物 | **本机没有这条路**。`../crypto/iv8-runtime-cheatsheet.md` 的 API 形态仅供有该运行时的环境参考，**未在本机验证** |

无论走哪条：**Python 必须拥有真实 HTTP 重放**。不要让 JS 宿主变成一个活的 HTTP 客户端，也不要让它悄悄变成「无头浏览器依赖」。

### 失败路由（Failure routing）

| 症状 | 去哪 |
|---|---|
| H2 reset / TLS EOF / 握手超时 / 浏览器过了但标准库不过 | `../observe/transport-pre-gate-playbook.md` |
| `403` / `412` / `429` | 比头、cookie、签名新鲜度、请求节奏 → `./troubleshooting-playbook.md` |
| `200` 但业务报错 | 比载荷组装顺序与时间戳精度 |
| `200` 之后解密失败 | 检查 key / iv 是否经过 digit-pair-to-char 之类的变换 |
| 数据为空 | 查分页、过滤、referer、登录态、游标演进 |
| 偶尔成功 | 查一次性 token、会话刷新、并发请求耦合 |
| 首请求成功但立刻重放失败 | 比 cookie 变更、内存时间戳槽、是否每次都要先跑刷新函数 |
| 响应乱码 | 搜解密路径、压缩、protobuf、msgpack → `../deliver/response-decode-playbook.md` |
| hook 的页面失败、干净页面成功 | observer effect，撤 hook 重抓基线 |
| 本机运行时初始化后定时器失败，但有一个 getter 或出站请求边界可见 | `../state/challenge-artifact-harvest-playbook.md` |
| **本机无 `iv8` 而任务假定有它** | **记为前置缺失（unmet constraint）**，改走 `node` / `playwright`；换路线前**告知用户**这是替代方案 |
| **npm 侧 AST 依赖缺失** | 记录为缺口，退回 grep + `node` 执行 + 人工读码 |
| 某工具没装 | 记 `missing_tool`，只用已有手段，**不要给出需要那个工具才成立的结论** |

### 聚焦的内部路线（Focused profile tools）

目标已经明确时，不要重开完整的目标发现：

| 当前目标 | 本机路线 |
|---|---|
| 已知道边界的粘贴即用浏览器 hook | `../../profiles/browser-hook-snippets/index.md` + 其 `references/*.md` |
| 需要 Node / VM 宿主面的已知入口 | `../../profiles/env-patch/index.md` |
| 固定轨迹的纯 Python 重建 | `../deliver/pure-python-rebuild-playbook.md` |
| 已给 JS 文件的结构化 AST 还原 | `../../profiles/static-ast/index.md` —— **⚠️ 本机 npm 依赖未装，开跑前先确认** |

这些路线**不能**替代未知多层采集器的 wire 证据。

### 本包内的脚本

**本包没有 `scripts/` 目录。** 源文档提到的：

- `scripts/check_reverse_env.py` → 用本文「前置」的四条命令替代
- `scripts/crypto_fingerprint.py` → 用 `../crypto/crypto-patterns.md` 的手工比对流程
- `scripts/protocol_diff.py` → 见 `./reproducible-evidence-playbook.md` 的 transcript diff 方法
- `scripts/scaffold_reverse_project.py` → 手工建目录（本包约定见 `../contract/project-artifact-contract.md`）

需要这些能力时，自己写一个小脚本落到任务目录 `js_reverse_cache/tasks/<task-id>/` 下，**不要**在本技能目录里造工具。

---

## 判据（Completion criteria）

选完工具之后，必须能回答这 6 条，才算「工具选型做完了」：

1. **每一类证据面都指名了本机的具体可执行文件或模块**，不是产品名
2. **每一个缺口都点名了**（`iv8` / `reqable` / managed host / npm AST 依赖），并写明它造成的是「记录缺口」还是「必须换路线」
3. **wire 证据路径已验证存在**（`mitmdump` 或 `tshark` 至少一个能实际跑起来）
4. **降级链已写好**：首选手段不可用时，下一步是什么
5. **交付路径不含浏览器自动化** —— `playwright` / `frida` 只出现在取证阶段，不在最终重放路径上
6. **没有编造实测**：凡是没在本机跑过的命令或能力，都标了「未在本机验证」

自检反例（**以下情况算没做**）：

- 直接照抄源文档的工具名（`js-reverse`、`list_scripts`、`save_script_source` 等）而不确认本机有没有
- 声称用了 `iv8` 或 Camoufox
- 把「本机没有的 npm 包」当成已装直接跑 AST 路线
- 在 `(Resolve-ReverseToolSpec -Name 'pyre').Command` 里跑 `frida` / `playwright` / `curl_cffi` —— 实测那些模块不在那个 venv 里
- 声称「实测通过」但其实没跑

## 常见坑（Common traps）

- **以为有 MCP 工具族**。本机没有 `chrome-devtools` / `js-reverse`，照抄源文档会一路找不到工具
- **以为 npm 包已装**。`esprima`/`acorn`/`@babel/parser` 本机没有，AST 路线开箱不可用
- **以为 `iv8` 能装**。社区运行时，PyPI 上不存在该发行版
- **用 `python-venv` 当主解释器**。它实测缺 `frida` / `playwright` / `curl_cffi` / `mitmproxy`，只有 `requests`。
- **拿 tshark 当实时工具**。它只读已有 pcap，不抓包
- **拿被动 store 当活证据**。HAR/pcap 与浏览器外发冲突时信活的
- **把 hook 安静当字段不存在**。先排除并发写入方
- **让浏览器进了交付路径**。取证用，交付不用
- **拿局部变量或环境补丁当最终结论**。盖不过 wire 与下游业务结果

## 相关（Related）

- `./startup-triage-playbook.md` —— 选工具前必须先过的启动门与证据角色定义
- `./symptom-heuristics.md` —— 症状到家族的快速匹配
- `./escalation-ladder-playbook.md` —— 什么时候才允许升级到重运行时
- `./troubleshooting-playbook.md` —— 已经做完了但仍失败
- `./reproducible-evidence-playbook.md` —— 把证据规范化、可复现、可审计
- `../crypto/iv8-runtime-cheatsheet.md` —— **`iv8` 本机无，此文 API 形态未在本机验证**
- `../crypto/embedded-browser-runtime-playbook.md` —— 本地宿主语义的重建路线
- `../../profiles/env-patch/index.md` / `../../profiles/browser-hook-snippets/index.md` / `../../profiles/static-ast/index.md`
- `../contract/project-artifact-contract.md` —— 产物落在哪、命名约定

---

## 源文档勘误与本机化改动

1. **工具前提在本机整体失效**。源文档的「Preferred order」「Recon and network capture」「Static JS analysis」「Dynamic validation」「Browser lifecycle and handoff」全部建立在 `chrome-devtools` / `js-reverse` / Camoufox / AdsPower / Reqable 之上。**本机这套 MCP 工具族不存在**。已把每一个都映射到本机真实可执行路径。
2. **`iv8` 本机无**（社区运行时，PyPI 无发行版）。源文档的 `Embedded runtime routing` 一节假定它在位，并配套 `../crypto/iv8-runtime-cheatsheet.md`。本文改为「`node` 优先、`playwright` 兜底、完全离线无浏览器那条路本机不存在」的三级说明。
3. **Reqable / HAR 历史库本机无**。改为 `mitmdump --save-stream-file` + `tshark -w` + 用户 HAR。
4. **静态 AST 依赖本机未装**。源文档把 AST 路线当既有能力；本机 `esprima`/`acorn`/`@babel/parser` 均缺，已标注并给出降级链。
5. **不存在的脚本**。源文档「Local helper scripts」列出 4 个 `scripts/*.py`；**本包没有 `scripts/` 目录**，四个全部无法执行。已逐条给出手工替代。
6. **源文档第 56 行被截断**：原文最后一句 `…then js-reverse a…` 未写完（疑似上游文件损坏）。改编时不臆补，改为按本机手段陈述。
7. **`python-venv` 陷阱（实测修正）**：任务简报把 `(Resolve-ReverseToolSpec -Name 'pyre').Command` 描述为「空壳」。本机实测**不是空壳** —— 它有解释器（3.12.0，`base_prefix` 指向 `(Resolve-ReverseToolSpec -Name 'pyre').Command`）、42 个 Scripts 条目、208 个 site-packages 条目。但**关键模块确实缺失**：`frida` / `playwright` / `curl_cffi` / `mitmproxy` 全部 `False`。本文按实测事实写为「缺关键模块」而非「空壳」。
8. **保留未本地化的部分**：关键词包、基线优先证明流程、角色与证据面的关系判断、「不同证据面干的是不同的事」这张表 —— 这些与工具无关，是方法论核心，原样保留（译为中文）。
9. **本文命令的校验范围**：已在本机实跑校验的是**工具存在性与 flag 合法性** —— `python -V` / `node -v` / `tshark -v` / `mitmdump --version` / `importlib.util` 模块探测 / `mitmdump --help` 的 `-p`、`-w`、`--listen-port`、`--save-stream-file`、`-s` / `tshark -G fields` 的 `http.request.full_uri`、`http.cookie`、`tls.handshake.type`、`frame.number`。**未实跑、需要真实目标或 pcap 的命令**（`tshark -r <文件>`、各 `playwright` / `frida` 调用）**只保证语法与字段名正确，不保证在你的目标上生效**。用户自写脚本（`normalize_evidence.py`、`practice_lab.py`）已标注「未在本机验证」。
10. **写作过程中自查出并修正的两处错误**（记录在案，避免再次发生）：① 最初按任务简报把 `python-venv` 写成「空壳」，实测证伪，已改为「缺关键模块」；② 最初给出的 `--set flow_detail=1` 在本机 mitmproxy 10.3.0 上不存在，已删除并在正文加警告。