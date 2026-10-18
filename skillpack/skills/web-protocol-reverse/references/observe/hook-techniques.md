# Hook 技术手册（Hook Techniques）

> **来源声明**：本文改编自外部仓库 `aoyunyang/spider-king-skill`（MIT License）的 `hook-techniques.md`。原始内容为英文原文，此处译为中文并按本包六段式规范重排；技术术语保留英文原词并附中文。**原方法论保持为主**，改编新增「本机 hook 路径」一节作为替代/补充（见文末「源文档勘误」）。
>
> **什么时候用**：**运行时证明比静态阅读更快**的时候 —— 你已经大致知道在哪，但要确认「谁调了它、传了什么、什么时候改的」。
>
> - `playwright`（`(Resolve-ReverseToolSpec -Name 'pyre').Command -m playwright`，浏览器 `<playwright 浏览器>` 已装于 `%USERPROFILE%\AppData\Local\ms-playwright`）**可用**

> ★★ **本机 playwright 必须显式指定浏览器**（2026-10-10 实测）：
> `launch()` 默认启动会报 `Executable doesn't exist at %LOCALAPPDATA%\ms-playwright\chromium_headless_shell-1234\...`
> —— python 包期望 1234，本机装的是 **1243**，版本号对不上。
> **可用写法**：`p.chromium.launch(channel="msedge")`（实测能起、能渲染、能读 DOM），
> 或 `launch(executable_path=<显式路径>)`。照抄裸 `launch()` 一定失败。
> 
> - `frida 17.17.0`（`(Resolve-ReverseToolSpec -Name 'frida').Command`，Python 包同版本）**可用** —— 本机主力 hook 路径
> - `node v22.23.3`（`(Resolve-ReverseToolSpec -Name 'node').Command`）**可用**，用于把目标 JS 拉到 Node 里做定点改写
> - MCP 浏览器家族 `chrome-devtools` / `js-reverse` **本机 agent 工具注册表中未挂载**（本机挂载的是 `pyghidra-mcp` / `idapro` / `ida-pro-mcp` / `angr-mcp` / `x64dbg-mcp`，**均为逆向侧，无 web 侧**）
> - 因此本文源文档中「MCP 浏览器家族注入 / preload」那一列的**方法论原样保留**，但**本机执行路径改用 `frida` + `playwright`**

---

## 适用信号（Recognition signals）

- 需要知道「哪个函数在写这个 header / cookie / storage」
- 需要在**签名发生前**抓到 preimage（输入串），或**签名发生后**抓到最终载荷
- 需要知道谁调了它（initiator / 调用栈）
- 页面有反调试，DevTools 一开就变行为（见 `./anti-debug-playbook.md`）
- 静态读源码定位不到，因为逻辑在动态拼装的闭包里

## 前置（Entry conditions）

1. **先抓一条干净基线（clean baseline）**，再上任何侵入式 hook。源文档这一条是硬要求（Doctrine 10 观察者效应），本机同样适用 —— hook 会改行为。
2. **选定注入面**（见「步骤」的注入时序矩阵）。
3. **明确本次 hook 是「只观察」还是「实验本身就是变更」**。默认只观察。

## 步骤（Working method）

### 最高价值的 hook 目标

- `fetch`
- `XMLHttpRequest.prototype.open`
- `XMLHttpRequest.prototype.send`
- transport wrapper 函数（传输包装函数）
- bootstrap helper（引导辅助函数）
- signer helper（签名辅助函数）
- 会话状态正在变化时的 storage 读写

### hook 的目标（你要抓到什么）

- 签名前的字符串（pre-sign strings）
- wrapper 改写后的最终载荷
- 响应侧的刷新字段
- 请求之间发生变化的 cookie 或 global（全局量）

### 注入时序与恢复矩阵（Hook timing and recovery matrix）

**把 preload（预加载）当作一种「能力」，而不是一个承诺的方法名。** 上任何受控刷新（controlled reload）或侵入式 hook 之前，先保住一条干净基线。

| 观察到的状态 | 最小下一步 | 结论边界与恢复 |
|---|---|---|
| `preload 可用` 且页面尚未初始化 | 通过 schema（schema）确认的「文档前（before-document）」能力装上窄的 observe-only hook，然后导航一次 | 记录注入顺序，并证明原参数、`this`、返回值和 promise 都被保留 |
| `preload 不可用` | 用最早期的稳定断点、带 bundle 后稳定边界的受控刷新，或离线本地运行时 | **不得**声称观察到了构造器、bootstrap 写入或早期请求；在快照里记录缺失能力 |
| `页面已初始化` | 迟到的 hook 只作为**后续事件**的证据；在决定刷新是否可重放前先保存当前状态 | 若刷新会销毁唯一状态，用 `RETAINED_EXCEPTION` 并改走源码 / 断点 / 出站证据 |
| `hook 未命中` | 核对安装时机、目标 frame、执行世界（execution world）、替换顺序，以及 prototype / constructor wrapper / ingress / egress 中哪个更权威 | 一次未命中**只否定该时段的那一个边界**，不要删假设 |
| console 或 isolated world 探针在 `page-owned world` 未命中 | 当已装能力支持时，在 page-owned world 里重做窄证明 | 若仍不行，改用源码、调用帧或 wire 出站证据，并记录 world gap |
| `兄弟传输通道（sibling transport）` 仍有可能 | 逐个通道检查 XHR、fetch、wrapper、beacon、WebSocket、worker、service-worker、message relay | 把每次命中关联到 method / URL / field / caller / request id；一个通道静默不等于全传输静默 |
| 工具断连、重启或注册表变化 | 停止对目标的任何动作，持久化已获证据，做一次 capability snapshot（能力快照）刷新 | 记录最后确认的生命周期状态 + 控制权丢失；**绝不可**据此推断 `PARKED` / `CLOSED` 或已恢复 `TARGET_ACTIVE` 归属，然后再通过顺序交接恢复 |

**一次只改一个时序 / 世界 / 传输变量。** 如果 hook 改变了目标行为，**先恢复干净基线**，并把该失败当作**观察者效应证据**，然后再考虑升级。

### 证据解读（Evidence interpretation）

- **静默的 hook 只否定那一个确切边界**
- 静默的 `document.cookie` hook **不能**否定 `Set-Cookie`、返回的 JS、重定向 wrapper、worker 或其他写入方
- 静默的 storage setter hook **不能**否定直接属性赋值或兄弟状态写入方
- 静默的 `fetch` hook **不能**否定 XHR、wrapper、worker 或基于消息的传输
- 若 console / isolated world 探针漏掉了一个 page-owned helper，**在放弃这条线索之前先在 page-owned world 里重做证明**

### 日志形状（Logging shape）

- 尽量把捕获绑定到 target / event / method / URL / field，加一个简短的 caller 提示
- **一行绑定到请求的日志，胜过一次裸值 dump**

### hook 顺序（Hooking order）

1. wire 层 hook
2. wrapper 层 hook
3. helper 层 hook
4. 只有 hook 仍留有歧义时，才用局部变量断点（local-variable breakpoints）

**规则**：如果实例级 hook 被替换或被跳过，就**上移到每个调用都必须穿过的共享边界** —— 比如 prototype、constructor wrapper，或 transport egress。

### 行为安全（Behavior safety）

- 默认 hook **只观察**
- 转发原始参数，保留 `this`，返回原始结果或 promise
- 若某个 hook 改变了行为，把新的失败形态当作**可能的观察者效应**，直到被证明不是

---

## 本机 hook 路径（frida + playwright）

源文档的方法论建立在「MCP 浏览器家族 + 页面内注入」之上。**本机没有这套 MCP**，所以下面是等价能力的本机实现路径。

### 路径 A：frida（首选，本机可用）

`frida 17.17.0` 既能挂浏览器进程（`frida` + `frida-ps`），也能挂 Node/自建宿主。这是本机主力 hook 手段。

```powershell
# 列出本机可用设备（确认浏览器/进程可见）
& (Resolve-ReverseToolSpec -Name 'frida-ps').Command -Uai

# 启动一个带 hook 脚本的浏览器进程（示例形态，未对具体目标验证）
& (Resolve-ReverseToolSpec -Name 'frida').Command -f <exe> -l hook.js --no-pause
```

frida 相比页面内注入的关键优势，正好覆盖了上面矩阵里最痛的三行：

- **`page-owned world` 那一行不再是问题** —— frida 脚本运行在目标进程自己的世界里，不存在 isolated world 漏采。
- **`preload 不可用` 那一行不再是问题** —— 不依赖任何「文档前」能力，进程起来就挂得上，早期请求、构造器、bootstrap 写入都能看到。
- **`hook 未命中` 那行变成可诊断** —— 因为你在进程里，命中与否不是时序问题，而是选对了 prototype 还是实例的问题。

**frida hook 的两条纪律**（与上面方法论一致，不冲突）：

1. 用 `Interceptor.attach(fn, { onEnter(args) {...} })` 时，`onEnter` 里只读不写；要做变更才写 `args[i]`，并明确标注本次是「实验」。
2. hook 到的是 prototype 还是实例，直接决定抗重绑定能力 —— 与上面「上移到共享边界」是同一条规则。

**局限（诚实声明）**：目标若在浏览器里运行，frida 挂浏览器进程本身仍是「对目标施加了东西」，**Doctrine 10 观察者效应照常适用**。本文所有关于「先抓干净基线」的要求对 frida 一样有效。

### 路径 B：playwright（本机可用）

`playwright` + 已装的 `<playwright 浏览器>` 适合两种场景：

- **干净基线采集**：起一个受控浏览器，把请求/响应/HAR 落盘，**不加任何 hook**。这正是「先抓 clean baseline」那一步的本机实现。
- **CDP attach**：`playwright.chromium.connect_over_cdp()` 接到一个已开着的 Chrome 调试端口，然后在其上下文里做窄观察。

### 本机能力对照表

| 源文档里的能力 | 本机是否具备 | 本机替代/补足 |
|---|---|---|
| MCP 浏览器家族注入（`chrome-devtools` / `js-reverse`） | **未挂载** | `frida`（首选）/ `playwright` |
| preload / 文档前注入 | 不适用（无该 MCP） | `frida -f` 进程级挂载，覆盖同等早期面 |
| page-owned world 证明 | 通过 MCP 能力 | `frida` 天然在目标进程内，无需分 world |
| 干净基线采集 | 通过 MCP 能力 | `playwright` 受控启动 + HAR 落盘 |
| 静态 AST 定位 | `esprima` / `acorn` / `@babel/parser` **本机未装** | 需先装；见 `../../profiles/static-ast/index.md` |
| 本地运行时改写 | `node v22.23.3` **可用**；`iv8` **本机无** | `../../profiles/env-patch/index.md`（Node 路径已适配）；`iv8` 形态见 `../crypto/iv8-runtime-cheatsheet.md`（**未在本机验证**） |

## 判据（Verification checklist）

**「hook 取证完成」= 以下全部为真：**

1. **干净基线已先行保存**，且带 hook 的运行是**另一次**运行 —— 两者可区分。
2. **命中的是共享边界**（prototype / constructor wrapper / transport egress / wrapper ingress），不是某个易被替换的实例。
3. **每条日志绑定到了 target / event / method / URL / field / caller**，不是裸值 dump。
4. **hook 保持只观察**：原参数转发、`this` 保留、返回原结果或 promise —— 这一点被实际验证过（对比 hook 前后的请求行为）。
5. **未命中的通道被逐一排查过**，没有被一句「静默 = 不存在」带过（fetch / XHR / wrapper / beacon / WS / worker / service-worker / message relay）。
6. **执行世界已确认**：若在 isolated world / console 里做的证明有遗漏，已在 page-owned world 重做。
7. **改写类 hook 单独标注为「实验」**，且其结果与只观察结果分开记录。
8. **hook 没有把最终交付拖回浏览器**：hook 只用于取证，交付路径仍按 `../deliver/pure-python-rebuild-playbook.md` 与 `../deliver/delivery-gate-playbook.md` 走。

## 常见坑（Common traps）

- 挂了业务层函数，却漏掉了 transport wrapper
- 挂在某个「顺手拿到」的对象实例上，而运行时一直在重绑定或克隆真正的调用方
- 用断点停得太早，淹死在噪声里
- 只抓最终哈希，没抓**产生它的输入串**
- 把「hook 未命中」当成「这条路径不存在」
- 把 hook 造成的行为变化当成「目标只能靠浏览器」
- 在 isolated world 里探不到就放弃，而没在 page-owned world 重试

**本机补充**：

- 看到 frida 的 Scripts 目录下有 17 个 `frida-*` 工具就觉得需要全用 —— 先用 `frida` / `frida-ps`，其余按需
- 静态 AST 定位需要 `esprima` / `acorn` / `@babel/parser`，**本机未装**，先装再用；未装时不要卡在「必须先有 AST 工具」而跳过 hook 取证
- 期待 `iv8` 可用 —— **本机无**

## 相关（Related）

- `../../profiles/browser-hook-snippets/index.md` —— 已知观察边界时，直接取粘贴即用的 hook 片段
- `./anti-debug-playbook.md` —— 页面反调试时的应对
- `./mcp-routing-playbook.md` —— 「什么时候该开哪个工具族」的判定（**注意本机 web 侧 MCP 未挂载**）
- `./local-mcp-environment.md` —— 本机环境与占位符约定
- `../principles/doctrine-index.md` —— 教条 10（观察者效应是真的）、教条 11（cookie 溯源）
- `../triage/tool-playbook.md` —— 工具能力快照规程
- `../deliver/pure-python-rebuild-playbook.md` —— hook 抓到之后的下一步：拿固定输入做纯 Python 重建
- `../../../field-journal/seed-004_js-sign-webpack.md` —— 本包已有的「initiator 回溯定位签名函数」实战案例

---

## 源文档勘误（改编时修正）

1. **源文档整篇假定「MCP 浏览器家族（`chrome-devtools` / `js-reverse`）在本会话已挂载」**，其注入时序矩阵里的「schema 确认的文档前能力」「受控刷新」等说法都依赖这些工具存在。**本机 agent 工具注册表未挂载任何 web 侧 MCP**（挂载的是逆向侧的 `pyghidra-mcp` / `idapro` / `ida-pro-mcp` / `angr-mcp` / `x64dbg-mcp`）。源文档照抄会直接卡死在「schema 确认」这一步。改编保留全部方法论，但补入 frida/playwright 的本机实现路径，并显式说明**矩阵中哪几行在本机因 frida 而不再是问题**。
2. **源文档的矩阵最后一行提到「工具断连、重启或注册表变化」，但没有说清为什么重要** —— 原文只写「never infer PARKED/CLOSED」，读者容易当成一句套话。改编保留了结论，但把它归因明确为「控制权丢失 ≠ 进程已退出」，这是本包 `../triage/tool-playbook.md` 生命周期语义的同一原则。
3. **源文档 `Hooking order` 第 4 步「local-variable breakpoints」隐含需要调试器**。本机调试器侧可用的是 `x64dbg-mcp`（挂载了）和 IDA 系，**不是浏览器 JS 调试器**。改编在判据中把该步的依赖降级为「hook 仍留歧义时」，并明确它不是本机默认手段。
4. **源文档 `Logging shape` 只说「绑定到 target、event、method、URL、field、caller」**，没给具体格式。改编在判据第 3 条把它变成可检查项（每一行都要能回答这六问），否则无法验收。
5. **源文档没有区分「hook 类工具本身改变了目标行为」与「目标反调试」两种失败形态**，两者都会表现为「hook 后行为变了」。改编在步骤的矩阵末尾与「判据」第 4 条分别点名，避免误诊。