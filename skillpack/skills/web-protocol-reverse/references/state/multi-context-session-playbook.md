# 多上下文会话手册（Multi-Context Session Playbook）

> **来源声明**：改编自 `aoyunyang/spider-king-skill`（MIT License）的 `multi-context-session-playbook.md`。英文原文译为中文，术语保留英文原词并附中文，按本包六段式规范重排。
>
> **什么时候用**：目标在账号登录之后**还没完** —— 同一个账号仍有可变的业务上下文。
>
> **平台与本机状态**：`python 3.12`、`curl_cffi`（本机可用，会话对象首选）、`playwright`、`mitmdump`、`tshark 4.6.8` 本机可用。`iv8` 本机无。

> ★★ **本机 playwright 必须显式指定浏览器**（2026-10-10 实测）：
> `launch()` 默认启动会报 `Executable doesn't exist at %LOCALAPPDATA%\ms-playwright\chromium_headless_shell-1234\...`
> —— python 包期望 1234，本机装的是 **1243**，版本号对不上。
> **可用写法**：`p.chromium.launch(channel="msedge")`（实测能起、能渲染、能读 DOM），
> 或 `launch(executable_path=<显式路径>)`。照抄裸 `launch()` 一定失败。
> 
>
> **立场声明**：本文是**协议逆向**方法论，讨论「登录态与业务上下文之间的协议分层」。

---

## 适用信号（Recognition signals）

- 登录成功了，但列表或导出数据**属于错误的店铺、租户、供应商、组织或数据范围**
- UI 上选择的中文或本地化标签，**必须先转换成协议代码**才能激活
- 切换（switch）或更新（update）API 返回 HTTP 200 或 `success`，**但最终页面仍显示旧上下文**
- 共享一个会话的并发任务**开始互相读到对方的上下文** —— 数据串号
- 登录成功了，但首页看着对，取出来的数据却不对

## 前置（Entry conditions）

1. **目标账号 + 目标租户/店铺范围**。见 `session-contract-playbook.md` 立场段。
2. **单一会话对象贯穿全链**。本机用 `curl_cffi.requests.Session`，中间不新建客户端。
3. **一个可读取权威身份的「最终面」（authoritative final surface）**。这是 Gate B 的硬前提 —— 你需要一个地方重新读取当前身份，而不是靠推断。常见形态：业务页面 bootstrap blob、session introspection 端点。**若找不到这样的面，本篇的核心纪律无法执行**，应先解决它。
4. **wire 可见性**（判据第 4 条需要）：
   ```powershell
   D:\Tools\Wireshark\tshark.exe -r ctx.pcapng -T fields -e http.request.full_uri -e http.response.code -e http.cookie
   ```

## 步骤（Steps）

### 核心规则

**登录证明账号是谁。业务激活证明这个会话被允许以哪个身份行事。**

这是两个不同的成功门。

> **登录成功 ≠ 业务身份成功。首页能打开 ≠ 目标数据范围已被选中。**

### 身份分层（Identity layers）

把会话建模为**堆叠的可变层**。各产品命名不同，**分层结构不变**：

1. `account`：已认证主体
2. `tenant` 或产品空间：哪个业务世界生效
3. `role` 或商户类型：哪类操作者生效
4. `data-range`：哪个店铺、供应商、仓库、组织单元或受限资源生效

**耐久的采集器必须为每一层命名三件事：它是哪一层、哪个端点设置它、用哪个最终字段验证它。** 少一样，这条链就是不可复现的。

### 两道成功门（Two success gates）

#### Gate A：账号登录

**只**证明账号链走完了：

- 登录表单或 bootstrap 已解析（若为动态）
- 凭据或 token 交换已被接受
- 短命的交接产物（handoff artifact）已在需要时消费
- 账号级 cookie 或 token 现在存在于**同一条会话链**上

**若 Gate B 是必需的，不要在 Gate A 就导出凭据或宣布任务完成。**

#### Gate B：业务身份激活

证明**最终生效的上下文匹配任务配置**：

- 租户 / 产品空间
- 角色 / 商户类型
- 数据范围的**类型与值**（当 API 区分二者时）
- 业务页面实际使用的任何次级作用域

**任何必需层缺失、含糊或陈旧，都 fail closed（失败即停）。**

### 静默的不完整激活（Silent incomplete activation）

**某些平台接受部分更新而不报硬错误。** 典型形态：

- 租户看着对
- 角色看着对
- 数据范围的类型或值**被漏传或只传了一半**
- 最终会话里仍是空的、默认的、或上一个数据范围

**把这当成一等失败模式，而不是「大概没事」。**

工作法：

1. **冻结成功 UI 路径发出的那份确切激活载荷（activation payload）**
2. **把类型字段与值字段分开** —— 两者可能都必需
3. **不要只信切换 API 的响应信封**
4. **从一个权威最终面重新读取身份**，例如业务页面 bootstrap blob、session introspection 端点，或等价物
5. **保存 cookie 或开始采集之前**，把每个必需层与任务配置逐一比对

### UI 标签不是协议 ID

**显示名是给人看的。协议激活通常需要代码、资源 ID 或授权值。**

工作法：

1. 操作界面的标签**只用于**在一个实时的授权（authorization）或枚举响应里定位候选
2. **提交那个实时响应返回的协议 ID**
3. **要求匹配数恰好为 1**（无歧义）
4. **匹配数为 0 就停**：通常是缺授权，或标签被改名了
5. **匹配数 > 1 就停**：**绝不静默取第一行**

**绝不抄另一个账号的资源值或历史 ID**，除非当前授权响应仍然为这个账号返回它。

### 交接产物 vs 耐久 cookie

登录响应可能返回短命的转移材料：

- 一次性票据（one-time ticket）
- 二次 token
- 异步续传 URL
- 父级或跨域重定向

这些是**会话交接产物（session handoff artifacts）**。规则：

- **在将要持有最终 jar 的那条会话链上消费它们**
- **只跟随 wire 所必需的最小重定向集与异步同步集**
- **不要**把交接产物存成长期采集器凭据
- **只**从最终已校验的会话状态导出 cookie

### 单一会话链，最终 jar 导出

最终 cookie 通常是许多步骤的累加：

1. 登录页 seed cookie
2. 登录 POST cookie
3. 异步或跨域同步 cookie
4. 业务代理或自动登录 cookie
5. 会话更新 cookie
6. 最终业务页面 cookie

因此：

- 把**登录、交接、激活、最终身份重读**保持在**同一个 HTTP 会话对象**上
- 除非你**有意**分叉上下文，否则**不要为每一跳新建空客户端**
- **在 Gate B 通过之后**才从最终 cookie jar 导出
- 若支持本地 cookie 复用，**复用时要重新校验身份**，而不是假定文件仍对应预期上下文

### 采集前身份探针（Pre-collection identity probe）

在复用会话上做第一次业务抓取或导出**之前**：

1. 跑一次**廉价**的身份检查
2. 把租户、角色、数据范围与任务配置逐项确认
3. **不匹配就立即停**
4. **不要**继续跑，然后靠载荷内容去猜数据属于谁

**采集代码应当消费一个已被校验的上下文，而不该在运行中途静默「修复」错误的店铺。**

### 并发纪律（Concurrency rule）

**一个会话一个可变业务上下文。**

若任务必须覆盖多个店铺、供应商或数据范围：

- **每个上下文一个会话**
- **独立**激活并校验每个会话
- **不要**把一个 jar 在多个 worker 之间共享，并在其下方来回切上下文

> **共享式切换是数据串号的bug 制造机。**

### 失败分类（Failure classes）

对停止条件分类，而不是无限重试：

| 类别 | 处理 |
|---|---|
| `network_error` | 有限次退避重试可以接受 |
| `captcha` 或交互式挑战 | **停止**，转专用验证路径或人工处理 |
| `need_verify:*` | 停止并报告所需的验证模式 |
| `protocol_activation_failed:*` | 复查授权与激活载荷；**不要**高频重放 |
| `identity_mismatch` | **拒绝导出或抓取** |
| `cookie_export_invalid` | 若刷新候选通不过校验，**保留上一份耐久文件** |

**在激活失败或验证失败之后高频重试，只会加大风险，不会补上协议缺口。**

## 判据（Delivery checklist）

只有当以下**全部 9 条**都成立，才可以说多上下文登录流完成：

1. **Gate A 与 Gate B 都通过**
2. **每一个必需身份层都在代码和报告中显式存在**（含设置端点与校验字段）
3. **最终身份是「重读」得来的**，不是仅从切换响应推断的
4. **UI 标签是通过实时授权解析的，且匹配数唯一**
5. **交接产物保持短命**（没有被存成长期凭据）
6. **耐久 cookie 从一条已校验的会话链导出**
7. **复用路径上存在采集前身份探针**
8. **并发假设已写进文档**（一个上下文一个会话）
9. **交付保持无浏览器依赖** —— 本地 helper 可以铸造登录安全参数，但**活的 HTTP 必须由 Python 拥有**

> 关于验证码类失败：源文档把 `captcha` 归入「停止并转专用验证路径」。本文保留该纪律 —— **验证码不绕过，而是停下来走该目标提供的正当流程**。对服务端挑战的**协议理解**见 `challenge-state-envelope-playbook.md`。

## 常见坑（Common traps）

- 登录成功就当作全部完成，跳过 Gate B
- 数据看着「差不多对」就采了，没做采集前身份探针
- 只信切换 API 返回 200 / `success`，不从权威最终面重读
- 类型字段传了、值字段漏了（静默不完整激活）
- UI 标签匹配到多行时，静默取了第一行
- 直接抄了历史 ID 或别的账号的资源值
- 把一次性交接票据存成了长期凭据
- 每一跳都新建一个客户端，cookie 累积全丢
- 在 Gate B 之前就导出了 jar
- 让刷新候选覆盖了上一份通过校验的耐久文件
- 多个并发 worker 共享一个可变上下文的会话 —— **数据串号**
- 激活失败后高频重试

## 相关（Related）

- `session-contract-playbook.md` —— **本文的上游**：会话契约与 4 层身份清单的引入
- `cookie-provenance-playbook.md` —— 第 4 步「多跳登录与激活链」即本文交接产物的 cookie 视角
- `async-export-job-playbook.md` —— Gate B 之后的导出流水线；其「cookie 失效边界」是本文并发纪律的下游
- `stateful-stream-e2ee-playbook.md` —— 会话建立之上的长连接业务流
- `../triage/minimal-verifiable-facts-playbook.md` —— 判据第 3 条「重读而非推断」的取证规程
- `../contract/report-templates.md` —— 判据第 2、8 条的落盘格式
- `../deliver/pure-python-rebuild-playbook.md` —— 判据第 9 条的无浏览器交付形态

---

## 源文档勘误（改编时修正）

1. **源文档的 `Delivery checklist` 与 `Failure classes` 之间存在一处张力**：前者第 9 条要求「交付保持无浏览器（browser-free）」，后者把 `captcha` 归为「转专用验证路径或人工处理」。若「专用验证路径」意味着自动化浏览器，则与第 9 条冲突。本文消解为：**自动化浏览器不是「验证路径」的同义词** —— 验证码类失败应当**停止**并走该目标提供的正当人工/授权流程；本地 helper 只被允许铸造登录安全参数。这与源文档判据第 9 条括注「local helpers may mint login security params, but Python owns live HTTP」一致。
2. **源文档 `Identity layers` 说「Names vary by product; the layering does not」，但 `Layer checklist` 那一节实际在 `session-contract-playbook.md` 里**，本文引用了 `session-contract-playbook.md` 的同名清单，两篇保持术语一致。
3. **源文档 `Two success gates` 里 Gate A 的四条与 Gate B 的四条视觉上完全对称**，容易让读者以为两门同构。本文在 Gate B 加了「fail closed」的显式要求（源文档原文有 `Fail closed if any required layer is missing, ambiguous, or stale.` 但被放在 Gate B 末尾的散文里），以突出两门的不对称性。
4. **源文档 `Failure classes` 是纯列表无表格**，本文改为表格以突出「处理」列；内容逐条对应，未增删。