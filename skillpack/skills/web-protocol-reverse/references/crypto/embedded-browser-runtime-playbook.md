# 嵌入式浏览器运行时手册（Embedded Browser Runtime Playbook）

> **来源声明**：本文改编自外部仓库 `aoyunyang/spider-king-skill`（MIT License）的 `embedded-browser-runtime-playbook.md`。原文为英文，此处译为中文并按本包六段式规范重排；技术术语保留英文原词并附中文，AI 检索时中英文均可命中。源文档技术内容经核对**未发现错误**，未作技术性修改；仅按本机事实把 `iv8` 具体提及改为「嵌入式宿主」的通用表述 + 本机替代方案。
>
> **什么时候用**：host-bound（宿主绑定）的 JavaScript 需要**浏览器可见的语义**，但目标**并不真的需要**每个请求都跑一个完整浏览器。
>
> ## ⚠️ 本机状态
>
> | 能力 | 本机状态 |
> |---|---|
> | `node v24.20.0`（`(Resolve-ReverseToolSpec -Name 'node').Command`）+ `vm` + 自建 stub | ✅ 可用（**首选轻量宿主**） |
> | `playwright` + <playwright 浏览器> | ✅ 可用（需显式 `executable_path`） |

> ★★ **本机 playwright 必须显式指定浏览器**（2026-10-10 实测）：
> `launch()` 默认启动会报 `Executable doesn't exist at %LOCALAPPDATA%\ms-playwright\chromium_headless_shell-1234\...`
> —— python 包期望 1234，本机装的是 **1243**，版本号对不上。
> **可用写法**：`p.chromium.launch(channel="msedge")`（实测能起、能渲染、能读 DOM），
> 或 `launch(executable_path=<显式路径>)`。照抄裸 `launch()` 一定失败。
> 
> | `python 3.12`（`(Resolve-ReverseToolSpec -Name 'pyre').Command`） | ✅ 可用（**拥有真实 HTTP**） |
> | **`iv8`** | ❌ **本机无**（社区运行时，PyPI 无此发行版） |
>
> 源文档反复以 `iv8` 作为「嵌入式宿主」的**范例**。本机**没有 iv8**，
> 但上面三个本机可用工具**覆盖了同一层能力**，且都实测跑通。
> 需要具体可执行形态时读 `iv8-runtime-cheatsheet.md`（其替代路径 A / B 给出**本机实测**代码）。

---

## 适用信号（Recognition signals）

### 进入判据（Route here when）

- 解码后的字段**不是**一个简单的 Python 重写，且代码读取 `navigator`、`screen`、`location`、`document.cookie`、定时器、或 DOM 生命周期状态
- 目标在业务签名器运行前就探测 `Object.keys`、`Reflect.ownKeys`、描述符、`Function.prototype.toString`、`JSON.stringify`、或 `document.all`
- **页面 HTML + 内联或链接脚本**足以种出一个 cookie、签名 URL 后缀、封装 XHR body、或后续 token
- 一个**被挑战的文档页 + 一个链接的挑战脚本**，就能本地恢复可回放的 `Cookie` 头或 token，**不需要完整浏览器**
- 请求逻辑依赖**解析器顺序、生命周期事件、或定时器调度**
- 你需要**本地观察 XHR / fetch 改写**，而不想启动真浏览器
- 宿主桥接是**同步的**，但运行时也许接受**注入的 cookie / storage / token 状态**，而不是每次调用都回放完整异步 bootstrap
- **即使**注入 cookie / storage / 脚本 / 资源之后，本地输出**仍明显比线上更短、更简单、更重复**

### 不要先进来（Do not route here first when）

- 字段能塌缩成 Base64、hex、JSON、SHA、HMAC、AES 或其他**你能在 Python 手写并验证**的标准链
- 流程**每次请求**都仍需真实渲染、手势、挑战图片、canvas 熵、WebGL 行为、或活的浏览器状态
- 这个运行时会变成**所有 HTTP 的隐藏替身**，而不是一个窄的 bootstrap 或 helper 阶段

### 三条硬性规则

**规则 1：只有当以下三条**全部**成立时，才引入嵌入式宿主**

1. 在固定输入上，**平凡的 Python 重写或一个极小 JS helper 已经不够**
2. 剩下的不匹配**确实依赖宿主可见的语义** —— `navigator`、`document.cookie`、定时器、解析器顺序、或原生表面探针
3. 这个运行时**能把一个具体产物交回 Python** 做真实 HTTP 回放

**任一条为假** → 留在 Python 或一个极小的本地 helper。

**规则 2：拿到一个决定性产物就立刻停**

- cookie 字符串
- token
- 签名后的 URL
- 导航目标 / 重定向 URL
- 封装后的 body
- 解码后的载荷
- 一个稳定的 getter

> **如果这一点之后，流程仍需要真实渲染、手势、或持续的页面状态 —— 嵌入式宿主不是最终路径。**

**规则 3：browser-free ≠ runtime-free**

一个仍然调用嵌入式宿主的 Python 采集器，是 **browser-free 的，但并不自动是 runtime-free 的**。

这个中间形态**仅在**下列条件下可接受：

- 运行时是**本地且窄的**
- **Python 仍拥有真实 HTTP**
- **交接说明里明确写出「仍残留一个嵌入式宿主」**

> **如果任务明确要求「把运行时也去掉」**，
> 那么在第一次活体回放证明之后**必须继续收缩**，
> 而**不是**把 browser-free 的中间态当最终完成交付。

## 前置（Entry conditions）

1. **一条固定输入向量** —— 没有它，「够不够」这个判断无从谈起。
2. **捕获的 HTML / 脚本字节**，且**原始快照已落盘**。
3. **一个本机宿主**，三选一（按代价从低到高）：

   | 宿主 | 代价 | 适用 | 本机命令 |
   |---|---|---|---|
   | `node` + `vm` + 自建 stub | 低 | 定时器、cookie、XHR stub、纯逻辑 | `(Resolve-ReverseToolSpec -Name 'node').Command harness.js` |
   | `playwright` | 高 | 真实 DOM / canvas / 原生 `toString` | 见 `iv8-runtime-cheatsheet.md` B 节 |
   | 嵌入式宿主（源文档范例 `iv8`） | 中 | 生命周期 + 网络注入一体化 | ⚠ **本机无** |

4. **明确的产物清单** —— 你打算从这个宿主里**收割什么**。

---

## 步骤（Working method）

### 决策阶梯（Decision ladder）

> 这条阶梯解释的是「运行时特有的中间层」。
> 关于全技能范围通用的「**不要跨层跳跃**」规则，另读 `../triage/escalation-ladder-playbook.md`。

1. **先解码。**
   证明问题**是否**还只是一个标准算法或紧凑的包格式。

2. **证明便宜就手写 Python。**
   如果固定输入检查**已经匹配**，就停在这里。

3. **只有在需要宿主语义时才升级到嵌入式运行时。**
   当 JavaScript **真的**需要 DOM、定时器、cookie、XHR、或原生表面行为，
   **且**结果仍能被收割进一个 browser-free 的 Python 回放里。

4. **把运行时留在本地。**
   收割显式产物：cookie 字符串 / 出站 `Cookie` 头 / 最终签名 URL / 封装 body / token / 解码载荷。
   **一旦产物稳定到足以在 Python 回放，就停。**

5. **把控制权交回 Python。**
   Python 仍应拥有活体 HTTP、重试、解析、持久化、以及扩缩容。

### 高价值运行时动作（High-value runtime moves）

- **在升级到更重的宿主之前**，先测「一个版本锁定的本地 JS 引擎 + 打过补丁的 VM context + 原站 bundle」是否已经产出决定性产物。
- **生命周期事件、内联脚本或 XHR hook 重要时**，用「离线整页 bootstrap」形态。
- **只需要解析、不需要执行脚本时**，用纯 DOM 插入。
- **当定时器、微任务、或自发 XHR / fetch 调用必须触发时，优先 DOM 或脚本插入**，而不是阻塞式 `vm` 求值。
- **在升级之前**，先测「一个薄 DOM 运行时 + 几个原生形态补丁」是否已经足够支撑解析器顺序、`document.cookie` 和一个链接的挑战脚本。
- **当原生函数表面、内建可用性、或宿主对象枚举跨版本不同时，把本地引擎版本锁定**；记录「交付用哪个版本」和「仅诊断用哪个版本」。
- **当解析器预算或事件顺序会改变行为时，锁定 UA 主版本号。**
- **用逻辑时间推进定时器和排队工作**，而不是等墙钟。
- **入口 HTML 引用了链接的 bootstrap 资产或 runner 脚本时**，用**发现它们的那套 session、那个有效 origin、以及相关 headers** 去拉取；脱离上下文的下载会**分叉出另一条 bootstrap 链**。
- **业务路由本身返回机器挑战载荷时**，在 Python 里解析那个 tuple，**只**为派生的刷新产物调用本地运行时，然后重试同一请求族。
- **如果一个 bootstrap 运行时在同步 init 之后暴露一个稳定 getter，先收割那个产物**，再去试图完成后面每一个定时器回调。
- **如果一个薄 DOM 或嵌入式运行时在完整页面对齐之前就发出了最终导航目标或同路由重定向 URL**，把那个 URL 当作**一等产物**，**立刻**把回放交回 Python。
- **如果运行时在本地记录了打算发出的网络请求而不真的发出**，按这个模式驱动它：
  **观察计划请求 → 在 Python 里发完全相同的 HTTP → 注入响应 → 推进队列**，
  而**不是**先重建整个调度器。
- **如果宿主桥接是同步的**，先测运行时是否**只消费**来自 `document.cookie`、storage、或某个缓存对象的**已签发状态**。若是，注入一个已验证的样本，**把完整刷新路径的逆向推迟**到回放证据说明确有必要为止。
- **当本地运行时自发发出决定性请求时**，在本地拦截 body 与 headers，并返回让它继续所需的**最小假成功响应**。
- **如果回调报成功、但决定性字段仍然为空**，去追那个**真正填充该值的响应或状态写入**，而不是保住脆弱的回调编排。
- **打补丁之前先观察 API 探针**，这样你才知道缺失的表面究竟是 identity、enumeration、timing、cookie 状态、还是原生形态函数边界。
- **如果 cookie / storage / 脚本 / 资源映射几乎不改变产物**，停止回放更多 bootstrap，去追**究竟哪些原生表面被探测**。
- **把 `canvas`、WebGL、`getComputedStyle`、布局度量、以及原生描述符 identity 当作一等宿主表面**；先用**窄的本地适配器或 stub 桥接**，再考虑更宽的模拟。
- **读本地的 net-log 风格产物** —— 当运行时能在 bootstrap 之后显示最终 URL、body、headers、出站 `Cookie`、或其他被 wrapper 改写过的请求字段。
- **如果 `document.cookie` 或 session jar 看着正确、回放却仍失败** —— 优先相信**请求出网时看到的出站 `Cookie` 头**，而不是对存储状态的猜测。

### 必留证据（Evidence to record）

- 使用的**确切 HTML 或 bootstrap 响应**
- 当 cookie 回放是决定性产物时：**种子 cookie 输入**，以及**最终收割到的出站 `Cookie` 头**
- 离线资源映射或脚本 bundle 映射
- **环境覆盖项，以及被省略的默认值**
- 每次补丁**前后**的结构性度量：产物长度、字段是否存在、重复块、或熵的变化
- **本地引擎版本**
- **UA 主版本号**
- **定时器模式**，以及**每一次显式的 event-loop 推进**
- **从运行时里提取出的最终产物**
- 决定性产物究竟是 **cookie 增量**、**重定向 URL**、还是**两者兼有**
- **证明运行时输出与线上样本匹配的固定输入检查**

## 判据（Verification checklist）

只有满足以下**全部 5 条**，才可以说「嵌入式运行时这一层搞定了」：

1. **三条硬性规则在进入时就已全部成立**，且**有记录**（不是事后追认）
2. **决定性产物已收割，且在固定输入上与线上样本逐字节一致**
3. **Python 拥有全部真实 HTTP** —— 运行时**没有**发出任何真实业务请求
4. **交付形态已如实分类**（browser-free / runtime-free / 两者之间），且**如实说明了是否仍残留宿主**
5. **最小本地补丁面已显式记录** —— 补了什么、**故意没补什么**、以及为什么

> ⚠ **不构成完成**的典型情形：
> - 「helper 加载不报错了」 —— 见 `environment-patch-playbook.md`：**加载成功只是里程碑**
> - 「token 形状看起来对」 —— 不是回放证据
> - 「browser-free 了」 但**仍在每次请求调用嵌入式宿主**，而任务明确要求去掉运行时
> - 为了继续打补丁，**把那条唯一的新鲜成功链耗光**

---

## 常见坑（Common traps）

- 在试过平凡的 Python 重写**之前**就用嵌入式运行时
- 诊断用一个 JS 引擎版本、交付用另一个版本，**且没有重跑固定输入对齐检查**
- 喂了错误的 UA 版本，然后**把事件顺序问题归咎于 crypto**
- 静态 DOM 解析就够的时候，用了完整页 bootstrap
- 用**与入口链不同的 session、origin 或 header 画像**脱离带外地下载链接的 bootstrap 资产
- 把「业务响应挑战 tuple」当作「你找错端点了」的证明 —— 而同一条路由可能只是需要**本地刷新 + 重试**
- **把 Node / jsdom / 薄 shim 下的失败，当作「VM 在更真实的本地引擎或嵌入式宿主里也跑不了」的证明**
- 在运行时**只需要一个已签发的 cookie / storage 值 / token** 时，坚持要求完整异步 bootstrap 回放
- 假定「必须先做完整反混淆或更重的宿主」，而不先测「一个薄 DOM 运行时是否已经能产出同 URL 回放所需的决定性 cookie 头」
- 因为「决定性产物已经发出之后运行时还有后续 notice」，就**丢弃一个已恢复的重定向或导航目标**
- 在**权威值已经出现在本地响应或状态写入里之后**，还在重建回调时序
- **把那条唯一的新鲜成功链耗光**，只为了继续打补丁、而没有证明出最小的活体回放路径
- 永远在回放 cookie / storage / 脚本 / 资源映射，而真正的缺口其实是 `canvas`、WebGL、或布局 API 这样的**空值或假原生表面**
- **让运行时发出真实业务 HTTP**，而其实只需要本地改写证据
- 在查清**究竟是哪个 API 探针**产生分支之前，就打了**几十个 globals**
- 把**明显更短的验证器 sidecar** 误判成「答案质量问题」，而不是**宿主保真度缺口**
- 把「异常变少」「加载成功」「cookie 或 token 形状合理」当作回放成功
- 相信 `document.cookie` 或客户端 jar，而不与**真正越过请求边界的出站 `Cookie` 头**对比
- 已经锁定**那一个**必须恢复的字段之后，还**留着宽泛的 helper**
- 把 browser-free 路径当「完成」，而**嵌入式运行时仍在重新生成决定性产物**，且「移除运行时」本就是目标的一部分
- 拿到**一个产物**就够交回 Python 了，却**还留着宿主**

---

## 源文档改编说明

源文档通篇以 `iv8` 作为**唯一**的嵌入式宿主范例。改编时：

1. **顶部加了本机状态表**，明确 `iv8` 本机无，并给出本机实测可用的替代（`node` + `vm` 自建 stub 作为轻量首选、`playwright` 作为真浏览器）。
2. **正文把「iv8 选择规则 / iv8 退出规则」改为通用「三条硬性规则」**，源文档的判断**逐字保留**，只是不再绑定特定品牌。
3. **「升级到 `iv8`」等表述**改为「升级到更重的宿主」，具体形态指向 `iv8-runtime-cheatsheet.md`。
4. 源文档的技术判断（阶梯、「先收割再逆」、出网头优先于 jar、版本锁定、逻辑时间等）**全部保留**，经核对**未发现错误**。

---

## 相关（Related）

- `iv8-runtime-cheatsheet.md` —— **本机可执行的替代路径**（`node` + `vm` / `playwright`，均附本机实测输出）
- `environment-patch-playbook.md` —— 补宿主的详细 15 步方法与边界选择规则
- `env-diff-playbook.md` —— 输出对不上时的分层与收缩路径
- `jsvmp-analysis-playbook.md` —— 「本地执行 vs 全量反虚拟化」的取舍
- `local-challenge-executor-playbook.md` —— 把宿主能力**契约化**用于挑战型目标
- `opaque-runtime-profile-playbook.md` —— 当本地产物依赖捕获的环境 / 不透明块时
- `../triage/escalation-ladder-playbook.md` —— 「不要跨层跳跃」的全局规则
- `../deliver/delivery-gate-playbook.md` —— browser-free vs runtime-free 的交付门判定