# 会话契约手册（Session Contract Playbook）

> **来源声明**：改编自 `aoyunyang/spider-king-skill`（MIT License）的 `session-contract-playbook.md`。英文原文译为中文，术语保留英文原词并附中文，按本包六段式规范重排。
>
> **什么时候用**：页面提到 `sessionid`、登录，或结果与用户账号相关；查询和提交看起来需要同一份账号状态。
>
> **平台与本机状态**：`python 3.12`、`curl_cffi`（本机可用，是带会话与 TLS 指纹的 HTTP 客户端首选）、`mitmdump`、`tshark 4.6.8`、`playwright` 本机可用。`iv8` 本机无。

> ★★ **本机 playwright 必须显式指定浏览器**（2026-10-10 实测）：
> `launch()` 默认启动会报 `Executable doesn't exist at %LOCALAPPDATA%\ms-playwright\chromium_headless_shell-1234\...`
> —— python 包期望 1234，本机装的是 **1243**，版本号对不上。
> **可用写法**：`p.chromium.launch(channel="msedge")`（实测能起、能渲染、能读 DOM），
> 或 `launch(executable_path=<显式路径>)`。照抄裸 `launch()` 一定失败。
> 

---

## 适用信号（Recognition signals）

- 页面文案提到 `sessionid`、登录，或「按用户可见」的答案
- fetch（查询）与 submit（提交）看起来需要同一账号状态
- 一个请求匿名可通，另一个没登录就失败
- **一个已认证的会话仍能在不重新登录的前提下切换当前租户（tenant）、店铺（shop）、组织（org）、语言（locale）、供应商（supplier）或工作区（workspace）上下文**
- 登录成功了，但业务数据仍依赖一次额外的激活（activation）或范围选择（scope selection）

## 前置（Entry conditions）

1. **目标账号 / 已获取的会话**。本文做协议契约建模。
2. **单一会话对象**。从第一条请求到最后一次导出，中间**不新建客户端**。本机用 `curl_cffi.requests.Session`：
   ```python
   import curl_cffi.requests as rq
   s = rq.Session(impersonate="chrome")   # 仅限已授权目标
   ```
   换会话对象就等于丢掉累积的 cookie —— 这是本篇最常见的自伤。
3. **wire 可见性**，用于「页面文案只是假设」这一判据：
   ```powershell
   D:\Tools\Wireshark\tshark.exe -r auth.pcapng -Y "http.cookie" -T fields -e http.request.full_uri -e http.cookie
   ```

## 步骤（Working method）

### 核心规则

**会话状态是一份协议契约，不是一种浏览器便利。**

三条推论：

1. **页面文字不是「cookie 进入签名原像（preimage）」的证明。** 页面上写着「需要登录」，不代表那个 cookie 参与了签名；要证明得看 wire。
2. **账号登录不自动等同于业务上下文激活那道门。**
3. 匿名可通 ≠ 业务可通。

### 工作法

1. **判定依赖范围**：数据请求依赖登录、提交依赖登录、还是**两者都**依赖。这一步决定了后面是双链路还是可拆链路。
2. **页面关于 `sessionid` 或登录的警告只当假设**，必须从 wire 行为证明。
3. **对同一条业务路由，分别抓「带」与「不带」所声称的那个 cookie/header 的样本**，做对照。
4. **记录答案是否与账号绑定（account-bound）**。这决定采集器能否匿名化。
5. 若账号登录后仍能切换租户、角色、店铺、供应商或数据范围 → 转 `multi-context-session-playbook.md`。
6. **当答案或权限与账号绑定时，把 fetch 与 submit 保持在同一条显式会话链上。**
7. **把所需会话输入暴露在采集器里**，不要把它们藏进一个浏览器 profile 里。藏起来等于把协议契约变成不可复现的黑箱。
8. **当 wire 显示出列表/详情采集与提交账号要求分离时，把这个边界显式记录下来**，不要混着做。
9. **复用持久 cookie 时，在采集前重新校验当前业务身份** —— 文件里的 cookie 可能对应另一个租户/店铺。

### 层次清单（Layer checklist）

当登录只是第一道门时，把这些层**逐一显式命名**：

1. 账号认证（account authentication）
2. 租户或产品空间（tenant / product space）
3. 角色或商户类型（role / merchant type）
4. 数据范围或资源作用域（data-range / resource scope）

**首页能打开，不证明所有必需层都匹配任务要求。** 这是本文最常被跳过的一步。

## 判据（Verification criteria）

采集器可交付，当且仅当：

1. **依赖范围已判定**：数据请求是否依赖登录、提交是否依赖登录、两者分别有 wire 证据（不是页面文案）
2. **答案是否与账号绑定，已记录** —— 且这个结论有「带/不带 cookie」的对照样本支撑
3. **若存在账号绑定**：fetch 与 submit 共用**同一条会话链**，且会话输入在采集器中显式可见（不是藏在 profile 里）
4. **若存在多张门**：上面 4 层（账号 / 租户 / 角色 / 数据范围）**每一层都被显式命名**，并各自有设置它的端点和校验它的字段
5. **若列表与提交要求分离**：该分离在代码与文档中**显式编码**，而不是靠注释说明
6. **若复用持久 cookie**：存在**采集前的身份再校验**，不匹配就停
7. 文档中明确写出：**结果是否与账号绑定**

第 6 条对应工作法第 9 步；第 7 条对应源文档的 `Delivery rule`。

## 常见坑（Common traps）

- 因为某个端点曾经免登录跑通过一次，就认定登录无关
- 因为页面文字这么说，就认定每个请求都需要登录
- 把账号 cookie 当成**每个业务页面通用的万能钥匙**
- 没做定样本证明，就把一个会轮转的会话 cookie 写死进签名原像
- 把匿名采集和与账号绑定的提交混在一起，**却不记录这个边界**
- 实际缺的只是提交时用的账号链，却在骂 signer（签名器）
- 登录后就导出 cookie，**但业务上下文还没校验**
- 让多个并发任务共享一个会话，而那个会话的上下文是可变的
- 复用一个持久 cookie 文件，**不重新校验它当前对应哪个租户/店铺** —— 最容易造成数据串号的坑

## 相关（Related）

- `multi-context-session-playbook.md` —— **本文的第 5 步的直接下游**：多上下文会话与 Gate A / Gate B 双门
- `cookie-provenance-playbook.md` —— 会话 cookie 是谁写的、怎么刷新
- `async-export-job-playbook.md` —— 需要账号态的异步导出流水线的边界处理
- `stateful-stream-e2ee-playbook.md` —— 会话建立/配对之上的有状态流
- `../observe/transport-pre-gate-playbook.md` —— 「页面文案 vs wire 真相」的证据分层
- `../triage/minimal-verifiable-facts-playbook.md` —— 判据第 1、2 条的「最小可验证事实」方法
- `../deliver/pure-python-rebuild-playbook.md` —— 判据第 3、7 条「会话输入显式、无浏览器依赖」
- `../contract/report-templates.md` —— 判据第 7 条的落盘格式

---

## 源文档勘误（改编时修正）

源文档内容正确精炼，无事实性错误。改编时做了两处补强：

1. **源文档的 `Core rule` 三句话是并列陈述的祈使句，没有编号**，本文为每句加了推论标注（「三条推论」），避免读者把它们读成三条平行规则而不理解其层次。
2. **源文档无独立的 Verification 章节**，只有 `Delivery rule` 三句散文。本文把它展开为 7 条判据，其中第 4 条（每层都有设置端点与校验字段）是从源文档 `Layer checklist`「A home page that loads is not proof that every required layer matches the task」这句警告推出的可执行形式。
3. **源文档 `Common traps` 缺一条**：它列了「sharing one session across concurrent context switches」，但没有对应的并发纪律段落（并发规则在 `multi-context-session-playbook.md` 里）。本文在「相关」段显式指向该篇，避免读者在本篇找不到并发解法。