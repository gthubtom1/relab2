# 异步导出任务手册（Async Export Job Playbook）

> **来源声明**：改编自 `aoyunyang/spider-king-skill`（MIT License）的 `async-export-job-playbook.md`。英文原文译为中文，术语保留英文原词并附中文，按本包六段式规范重排。
>
> **什么时候用**：业务路径不是一次列表请求，而是一条**异步导出、报表、下载或批处理任务流水线**。
>

> ★★ **本机 playwright 必须显式指定浏览器**（2026-10-10 实测）：
> `launch()` 默认启动会报 `Executable doesn't exist at %LOCALAPPDATA%\ms-playwright\chromium_headless_shell-1234\...`
> —— python 包期望 1234，本机装的是 **1243**，版本号对不上。
> **可用写法**：`p.chromium.launch(channel="msedge")`（实测能起、能渲染、能读 DOM），
> 或 `launch(executable_path=<显式路径>)`。照抄裸 `launch()` 一定失败。
> 

---

## 适用信号（Recognition signals）

- UI 创建了一个后台任务，之后才提供下载
- **创建接口返回 HTTP 200 不代表新任务真的出现了**
- 轮询时**误用了旧的**成功任务
- 首次创建（first-create）与重新生成（regenerate）/ 重试**看起来相似，但不是同一个协议**
- 下载需要一个二次验证码、邮箱密码，或加密压缩包
- **字段不全也能产出一个「看起来可下载」的文件**

## 前置（Entry conditions）

1. **一个有权使用的账号与导出权限**。本文讨论授权账号下的导出流水线协议建模。**不涉及**绕过导出权限或数据范围限制。
2. **状态机的每一级都能独立观测**。本机手段：
   ```powershell
   # 全量流式留存导出流水线
   & (Resolve-ReverseToolSpec -Name 'mitmdump').Command -p 8899 -w export.mitm
   # 离线读：关注 create / poll / download 三段的状态码
   & (Resolve-ReverseToolSpec -Name 'tshark').Command -r export.pcapng -T fields -e frame.number -e http.request.full_uri -e http.response.code -e http.content_disposition
   ```
3. **「创建前历史快照」可获取**。若历史列表可见，这是判据第 4 条的前提；不可见则该判据需换证据，详见「创建前只读探针」段。

## 步骤（Steps）

### 核心规则

**导出采集器是一台状态机，不是一个带签名的 GET。**

> **HTTP 200 不是创建成功。最新的一条历史行不自动等于本次运行的任务。一个能读的文件不自动等于一次完整的导出。**

这三句是本篇全部纪律的来源。

### 默认状态机

**按顺序爬这些阶段。自动化下一个阶段之前，先证明上一个阶段。**

1. **只读探针**：计数、schema 或字段目录、权限检查
2. （可选）**创建前历史快照**：记录已知任务 id
3. **创建或提交导出任务**：确切的 method、query、body、content type
4. **证明新任务 id 存在，且匹配本次运行的过滤条件**
5. **轮询状态**直到终态成功或失败
6. **下载前置检查（download precheck）**
7. **二次验证或异步旁路材料**（当需要时）
8. **下载字节**
9. **解密或解包**（当需要时）
10. **解析记录**
11. **入库前的完整性闸门（completeness gates）**
12. **有界 cookie / 会话刷新 —— 仅在明确的认证失败信号上**

> **不要在活跃账号上直接开跑全链。先验证只读阶段与离线 helper。**

### 四类参数（Four parameter classes）

**在设计签名器或硬编码任何值之前，先把每个可变部分归类。**

1. **业务参数（Business parameters）**
   操作者的过滤与导出选择：日期范围、报表类型、选中字段、文件类型、维度。

2. **静态应用参数（Static application parameters）**
   该产品界面每次都会发送的稳定应用或渠道常量。

3. **服务端或 SDK 下发的参数（Server or SDK issued parameters）**
   token、web id、任务下载 token，或其他由先前端点 / 本地 SDK helper 返回的值。**从它们的写入路径刷新，不要凭空造。**

4. **逐请求动态参数（Per-request dynamic parameters）**
   nonce、时间戳、指纹槽位、每次都变的请求签名。

**判断线索：**

| 现象 | 推断 |
|---|---|
| 页面刷新后仍在 | 可能是会话或应用静态参数 |
| 每次请求都变 | 可能是动态参数或签名 |
| body 一变它就变 | 签名**可能**覆盖 body 序列化 |
| 能从某个先前端点取到 | **不要发明它** |
| 删掉会导致风险提示或认证失败 | 属于准入（admission）或会话材料 |

### 创建前的只读探针（Read-only probes before create）

在任何创建调用**之前**：

1. **证明定义了业务切片的过滤查询**
2. 若产品支持自定义列，**取到可用的导出字段或 schema**
3. **检查当前是否允许导出**
4. 历史可见时，**快照当前历史任务 id**

**若过滤后的计数为零，直接短路，不要创建任务。**

### 创建成功判据（Create-success criteria）

只有**至少一条硬证据**成立才接受创建：

1. 创建响应返回了**新的任务 id**，或
2. 历史中出现了一个**创建前快照里不存在**的任务 id

**并且**被接受的任务必须匹配本次运行的业务条件：

- 时间范围
- 报表类型或维度
- 文件类型
- 选中字段集

**拒绝以下假阳性：**

- HTTP 200 但没有新任务
- 空的 success 信封
- 用 regenerate / retry 路径的证据当作首次创建证据
- 针对与线上请求不同的 method 或 body 做签名

### 任务隔离（Task isolation）

**绝不靠「第一行」或「最近一次成功」来选任务。**

选择优先级：

1. 创建响应返回的**任务 id**
2. 否则，**创建前集合中不存在**的任务 id
3. **要求**条件匹配本次运行的过滤条件与字段集

**禁止：**

- 因为方便就复用创建前就存在的成功任务
- 接受过滤条件或字段集不一致的任务
- 把「重新生成旧任务」当作首次创建协议的证据

### 创建 vs 重新生成（Create versus regenerate）

首次创建、重新生成、重试、下载**可能共享一个路径族**，但仍可能在这些方面不同：

- method
- 过滤条件在 query、JSON body 还是 form body
- 签名器覆盖哪些字段
- 是否需要先有 `task_id`

**首次创建要单独采集。在 wire 证据显示两者相同之前，不要把 regenerate 流量提升为创建契约的一部分。**

> **若首次创建的 method 或 body 位置仍未证明，在报告里把该边界保持为「未证明」。一条跑通的 regenerate 历史路径不够。**

### 签名与序列化（Signing and serialization）

当本地 helper 铸造风控或签名参数时：

1. **Python 拥有活的业务 HTTP**
2. **helper 只返回它必须产出的动态参数或改写后的 URL 材料**
3. **定输入检查覆盖与 wire 相同的 method 和序列化后的 body 或 query**
4. **host 与 path 不得跨 helper 边界漂移**
5. 缺失必需的会话指纹或 cookie 槽位时，**必须响亮失败**

> 若创建带着看似合理的签名仍以风控措辞失败，**先重新 diff method、content-type、body 位置，以及签名器实际覆盖的那段确切字符串** —— 而不是加签名复杂度。

### 轮询（Polling）

**带显式上限地轮询：**

- 最大尝试次数
- sleep 间隔
- 终态成功码与失败码

**全程使用那个被隔离的任务 id。不要在等待中途重新查历史并悄悄换成另一行。**

### 下载、旁路通道与产物闸门

**下载前置检查可能返回：**

- 直接的文件元数据
- 一个二次验证挑战
- 一个伪装成 200 的认证页或风控页

**对邮箱 / 短信这类异步旁路通道：**

1. **触发发送之前**记录游标（cursor）、最新消息 id 或时间戳基线
2. 触发该产品专属的发送端点
3. **只接受基线之后的新消息**
4. **区分场景专属的验证码形态** —— 登录验证码的长度或发送方**不自动**适用于下载场景

**字节到达之后：**

1. **校验该产物族预期的 magic number 或 content type**
2. 用**绑定本次运行**的材料解密或解包
3. 在本地解析记录
4. **入库前**应用完整性闸门

### 完整性闸门（Completeness gates）

**至少比较：**

- 若请求了自定义字段：**请求的字段数 vs 下载文件的列数**
- **必需业务键是否存在**
- 若前面有可用探针：**行数是否与之相符**

> **文件能读但比请求的更薄时，fail closed，不入库。**

这能抓到三类问题：

- create 序列化时**丢掉了字段数组**
- **拿错了历史文件**
- **回落到默认列**

### Cookie 失效边界（Cookie invalidation boundary）

**正常的导出不应当以驱动登录 UI 开始。**

**仅在明确的认证失败信号上：**

1. **停止**当前业务尝试
2. 在多 worker 场景下，**持锁**调用外部登录或 cookie 刷新路径**一次**
3. **重新加载**耐久 cookie
4. **有界次**重试当前单元

**不要把完整的登录自动化并进导出采集器的常态。**

## 判据（Delivery checklist）

只有当以下**全部 10 条**都成立，才算异步导出采集器完成：

1. **状态机端到端显式**（上面 12 个阶段都有对应代码路径）
2. **四类参数都被命名，且各自从正确的写入方重新生成**
3. **首次创建的 method 与 body 位置已被证明** —— 或**显式标注为未证明**（不能沉默地按 regenerate 实现）
4. **创建成功使用「新任务证据 + 条件匹配」双重判据**
5. **轮询逻辑不可能选中历史污染任务**（全程锁定任务 id）
6. **签名器覆盖范围与真实 method 和序列化一致**（定输入验证过）
7. **旁路通道有基线，防止复用陈旧验证码**
8. **产物格式闸门与字段完整性闸门能拦住坏文件**
9. **cookie 刷新是带外（out of band）且有界的**（不是采集器常态）
10. **交付保持无浏览器依赖** —— 本地 helper 只允许铸造请求参数

## 常见坑（Common traps）

- 把 HTTP 200 当成创建成功
- 轮询时重新查历史，悄悄换成了另一行任务
- 复用创建前就存在的成功任务，只因为它方便
- 接受过滤条件或字段集与本次运行不一致的任务
- 用 regenerate 的成功路径冒充首次创建的协议
- 首次创建的 method / body 位置未证明，却不报告
- 签名针对了与线上不同的 method 或序列化
- 用 pretty JSON 而非 wire 实际用的紧凑序列化
- 旁路通道没有基线，复用了旧验证码
- 把登录验证码当成下载验证码
- 文件能读就入库，不查字段完整性
- 把完整登录自动化并进导出采集器的常态
- 认证失败后无限重试
- 缺必需 cookie / 指纹槽位时静默填默认值，而不是响亮失败

## 相关（Related）

- `session-contract-playbook.md` —— 导出需要账号态时的会话契约；本文判据第 9 条的上游
- `multi-context-session-playbook.md` —— 导出涉及租户/店铺上下文时的 Gate B
- `cookie-provenance-playbook.md` —— 第 9 步「cookie 刷新路径」的溯源方法
- `stateful-stream-e2ee-playbook.md` —— 另一类异步业务流（长连接 vs 轮询）
- `../observe/pagination-route-pivot-playbook.md` —— 只读探针阶段分页路由的确定
- `../observe/dual-writer-param-playbook.md` —— 第 3、4 类参数的写入方选择
- `../crypto/pattern-atlas.md` —— 签名覆盖范围、序列化形态的模式索引
- `../deliver/delivery-gate-playbook.md` —— 判据第 8 条产物闸门的通用形态
- `../deliver/pure-python-rebuild-playbook.md` —— 判据第 10 条的无浏览器交付形态
- `../contract/report-templates.md` —— 判据第 3 条「显式标注未证明」的报告要求

---

## 源文档勘误（改编时修正）

1. **源文档 `Core rule` 的引用块三句**（HTTP 200 is not create success / The newest historical row... / A readable file...）是全篇的纲，但源文档把它放在 `## Core rule` 之后的引用块里，且**与 `Create-success criteria`、`Task isolation`、`Completeness gates` 三节内容重复**。改编时保留引用块（它是有效的纲），并把三句分别锚定到对应小节，避免读者只读纲就以为已经掌握全部。
2. **源文档 `Default state machine` 的第 12 步「bounded cookie or session refresh only on explicit auth failure」与 `Cookie invalidation boundary` 一节内容完全重复**（后者是前者的展开）。本文保留 12 阶段状态机中的这一行（它是状态机的一部分），并保留展开节，但明确二者是「状态机节点」与「该节点的执行规程」的关系。
3. **源文档 `Four parameter classes` 的 1、2 两项在原文里用 Markdown 粗体 + 两个尾随空格的换行格式排版**，渲染后在某些查看器里会挤成一行。本文改为列表项并保留编号层级。
4. **源文档无独立的 Verification 章节**，`Delivery checklist` 10 条兼作验收，本文直接沿用为判据，未增删。
5. **源文档 `Create versus regenerate` 结尾有一句「A working historical regenerate path is not enough.」是散文警告**，容易被略读。本文把它加粗为引用块，与 `Core rule` 的引用块风格一致。