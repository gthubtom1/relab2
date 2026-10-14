# 挑战状态信封手册（Challenge State Envelope Playbook）

> **来源声明**：改编自 `aoyunyang/spider-king-skill`（MIT License）的 `challenge-state-envelope-playbook.md`。英文原文译为中文，术语保留英文原词并附中文，按本包六段式规范重排。
>
> **什么时候用**：入口 HTML 与挑战 JS 在业务 replay 能工作**之前**就种下环境绑定状态；或业务响应自身返回一个机器可读的刷新契约（refresh contract），必须在重试前消费；或多个后续字段看起来共用同一个编码信封族（envelope family）。
>

> ★★ **本机 playwright 必须显式指定浏览器**（2026-10-10 实测）：
> `launch()` 默认启动会报 `Executable doesn't exist at %LOCALAPPDATA%\ms-playwright\chromium_headless_shell-1234\...`
> —— python 包期望 1234，本机装的是 **1243**，版本号对不上。
> **可用写法**：`p.chromium.launch(channel="msedge")`（实测能起、能渲染、能读 DOM），
> 或 `launch(executable_path=<显式路径>)`。照抄裸 `launch()` 一定失败。
> 
>
> **立场声明**：本文是**协议逆向与风控机制研究**方法论。目标是理解「服务端如何用挑战产物门控业务请求、状态如何跨字段传播」，并在**授权前提下**把该状态建模成可复现协议契约。本文**不涉及**绕过验证码、绕过风控或规避厂商检测手段。

---

## 适用信号（When to route here）

出现下列任一症状，走挑战状态信封路线：

- 首屏 HTML + challenge JS 必须先跑，token 或业务请求才稳定
- 业务端点返回机器挑战（machine challenge）、subcode 或刷新 tuple，**必须在重试同一请求族之前先消费**
- 挑战执行后出现一个派生 cookie、storage 项或 preflight token，**门控后续请求**
- URL query、表单 body、响应 body、cookie 看起来**结构上相关**
- 同一目标在多个字段上使用**版本标记、校验和、自定义字母表、动态前缀或内层加密载荷**
- 业务 preflight / token 端点返回**与后续业务端点相同的编码族**
- 解开一个字段还不够，另一个字段仍需要当前状态字节、storage 状态或挑战输出

### 变体：API 体返回挑战 HTML

下列情况**也**走这里：

- 业务 JSON API 返回 `Content-Type: text/html`，带内联 bootstrap 状态、meta 标签和外链 challenge 脚本
- 首次请求没有长 verifier 参数而失败；第二次请求带了一个长的 URL 绑定参数而成功
- 应用层请求签名**可能并行存在**，但**不自动等同于** HTML 挑战这道门

该变体下优先：

1. 同会话挑战采集（challenge harvest）
2. 必要时上本地挑战执行器
3. 从 Python 重放被改写的 URL 或派生 cookie

**不要仅因为某个无关的短签名器写了长得相似的参数名，就从深度逆它开始。**

## 前置（Entry conditions）

1. **一条新鲜的两阶段 trace（two-stage trace）**。这是本篇的硬前提 —— 没有新鲜的两阶段证据，后面七层证明都是空中楼阁。采集手段（本机可用）：
   ```powershell
   # 方式一：mitmproxy 全量流式留存
   & (Resolve-ReverseToolSpec -Name 'mitmdump').Command -p 8899 -w chain.mitm
   # 方式二：tshark 离线读 pcap
   & (Resolve-ReverseToolSpec -Name 'tshark').Command -r chain.pcapng -T fields -e frame.number -e http.request.full_uri -e http.response.code
   ```
   `reqable` 本机无，HAR 路径不适用。
2. **本地挑战执行宿主**。`playwright`（本机可用）保留定时器/微任务语义，是执行 challenge 的首选；纯计算的挑战逻辑用 `node v24`。`iv8` 本机无，`../crypto/iv8-runtime-cheatsheet.md` 的形态未在本机验证。
3. **会话链纪律**：本文反复强调「所有产物保持在同一条会话链上」。采集时不要跨会话拼接。
4. **适用面**：目标是你能直连的 Web 客户端。

## 步骤（Steps）

### 核心思想

**挑战输出是协议状态，不是装饰。**

响应侧的刷新 tuple 也是协议状态的一部分，**不是通用错误载荷**。

当一个目标在 URL、body、响应、cookie 上复用同一信封族时，**把包分帧（packet framing）与内层加密（inner crypto）分开，两者都要证明**。绝大多数失败来自「内层解对了，外层分帧还错着」。

### 快速执行路径

#### 1. 冻结一条新鲜的两阶段 trace

保存：

- 入口 HTML
- challenge 脚本 URL 或内联 challenge 代码
- 关联的 config JS 或加密 bootstrap blob（若存在）
- 初始 cookies
- 挑战后的 cookie 与 storage 状态
- 一个带刷新字段的失败业务响应（若存在）
- 一次 preflight token 请求与响应（若存在）
- 一次业务请求与响应

**纪律**：

- **除非另行证明可复用，否则所有这些产物保持在同一条会话链上。**
- **不要**因为形状看起来还兼容，就把邻近会话的入口 HTML、初始 cookie、challenge 脚本、生成的 cookie 状态、preflight token 和业务 replay 拼到一起。
- 失败页指向某个 config 资产或加密 bootstrap 变量时，**把该资产也冻结在同一条会话链上**，而不是因为 URL 看起来是静态的、稍后用一个脱链客户端重新下载。
- 同一业务路由先返回机器挑战、本地刷新后成功时，**先冻结这个 失败 → 刷新 → 成功 三元组**，再去找替代端点。
- 在做大规模环境补丁、分页扩容或运行时瘦身**之前**，先在那条确切的新鲜链上证明**一次最小业务 replay**。

#### 2. 分开七个证明层

把它们当成七个**互相独立**的问题：

1. bootstrap-config 解码
2. 环境模型（environment model）
3. 状态迁移（state transition）
4. 包分帧（packet framing）
5. 密钥归一化（key normalization）
6. 内层密码（inner cipher）
7. 业务明文或解码后的 JSON

七层混着做，是这一类目标最常见的返工来源。

#### 3. 一次映射整个信封族

对每个相关字段，记录：

- 线上字段名（wire field name）
- 版本标记或固定前缀
- 校验和覆盖范围
- 字母表或字节重映射
- 状态派生的前缀或切片
- 内层加密段
- 载荷锚点（payload anchor）或解析规则

#### 4. 显式证明状态依赖

检查该 URL 参数、body 字段或 cookie 是否**只靠业务明文**就能重建，还是**还需要**当前状态字节、storage 状态、挑战输出，或**紧邻上一次失败响应侧的刷新 tuple**。

#### 5. 用小检查点验证这个族

用精确检查而非「看起来对」：

- cookie 长度或分段数
- token 长度或格式
- 校验和通过
- 期望的前缀长度
- 找到 JSON 锚点
- 期望的 schema 键存在

### 高价值检查项

- 多个字段是否**共用一个自定义字母表或包前缀**，而不是各自独立的编码器？
- 业务响应自身**是不是刷新预言机（refresh oracle）**：同一 URL 失败并返回机器挑战 → 本地刷新消费那个 tuple → 同一 URL 成功？
- 校验和覆盖的是明文、密文、分帧体，还是整个外层包？
- 响应载荷是**从第 0 字节开始**，还是在一个固定的/状态派生的前缀之后？
- 外链 config JS 或短 bootstrap blob 是否**藏了加密配置**，后续展开成 key、iv、salt、cookie 名或兼容性常量？
- 表面上的 AES key / iv 是**直接使用**，还是切片、拼接、包装、XOR 掩码、长度装饰或其他归一化后才用？
- preflight token 响应是否与后续业务响应**用同一套解码链**？
- 环境绑定 cookie 只是一个存储 token，还是**带若干类型化分段的二进制结构化包**？
- 服务端是否**只下发种子字段**，而决定性的 replay token 仍是本地派生的，必须合并回同一个 cookie 或 header 束？
- session 样 / fingerprint 样的 cookie 是否其实是**从 UUID 变体、指纹向量或配置派生常量本地铸造**的，而非服务端下发的不可见值？
- 一个被接受的 bundle 哈希、版本标签或兼容性 token，是**内嵌常量**，还是你刚本地取到的那个文件的摘要？

### 双门说明（Dual gate note）

**应用签名器门与挑战验证器门可以是相互独立的：**

- 浏览器 XHR **可能两道门都要**
- 挑战重试 replay **可能只需要验证器产物**
- **恢复出一道门，永远不证明另一道门**

交接说明里**两道门分开记录**。

## 判据（Verification criteria / Minimal handoff notes）

以下 10 项**全部**要在交接说明里显式写出来：

1. **哪个挑战输出成为了协议状态**
2. **哪个响应侧刷新 tuple（若有）必须在重试同一路由前被消费**
3. **哪些 bootstrap 配置字段或归一化常量**驱动了 key、iv、校验和或被铸造的 cookie 结构
4. **哪个 cookie / storage 项 / token / header**由该状态派生
5. **哪些字段属于同一个信封族**
6. **信封族的确切顺序**：version、checksum、alphabet、prefix、cipher、payload anchor
7. **哪些后续字段仍依赖当前状态字节**
8. **哪些产物（若有）已被证明可跨会话复用**
9. **哪些固定检查点证明了本地重建是正确的**
10. **两道门（应用签名器门 / 挑战验证器门）各自的恢复状态**，分开写

外加两条可执行判据：

11. **在那条确切的新鲜会话链上，最小业务 replay 成功**（不是从邻会话拼出来的链）
12. **最终路径无浏览器依赖**

## 常见坑（Common traps）

- 把 cookie 当成从浏览器拷来的值，而不是可复现的协议产物
- 把应用层的挑战 subcode 当成通用失败，**在用刷新状态重试同一路由之前**就去找新端点
- 因为每个产物**单独看**都还新鲜，就把入口 HTML、cookie、challenge 代码、生成状态、preflight token 跨会话混用
- 离开新鲜挑战链去追离线环境补丁，**在证明一次最小在线 replay 之前**
- 只证明了内层密码，**漏掉外层 version、checksum 或 alphabet 层**
- 假定 URL 参数与 body 字段无关，而它们其实是同一个包族里的兄弟字段
- 解密出字节就立刻当 JSON 解析，而真实载荷是在某个前缀之后
- 假定业务明文就能重建请求，而**隐藏状态字节仍在影响外层信封**
- 只更新了派生 token，却把它的种子、时间戳、版本或名字字段留成陈旧；**或**反过来更新了种子字段却没重新生成依赖它的 replay 产物
- 熵（entropy）的**类别**对了但**结构**不对，比如客户端会插入校验位、前缀或定宽分段，你却塞了一个裸 UUID
- 用本地资产字节重算兼容性哈希，而运行时实际用的是**内嵌 id 或归一化常量**

## 相关（Related）

- `challenge-artifact-harvest-playbook.md` —— 姊妹篇：不就地摘取，而是选择拦截边界直接取产物
- `public-bootstrap-envelope-playbook.md` —— 非挑战驱动的公开引导信封
- `server-js-cookie-bootstrap-playbook.md` —— 挑战以可执行 JS 返回时的执行路径
- `cookie-provenance-playbook.md` —— 「服务端只下发种子、决定性值本地派生」这一形态的写入方溯源
- `../crypto/local-challenge-executor-playbook.md` —— 本地挑战执行宿主搭建
- `../crypto/environment-patch-playbook.md` —— 环境模型层（第 2 层）的补丁规程
- `../crypto/pattern-atlas.md` —— 字母表重映射、分帧、信封族等常见模式索引
- `../deliver/pure-python-rebuild-playbook.md` —— 判据第 12 条的无浏览器交付形态
- `../contract/report-templates.md` —— 10 项交接说明的落盘模板

---

## 源文档勘误（改编时修正）

1. **源文档标题下的导语把三个触发条件压成了一句极长的英文**（三句话挤在一行，且第三句「several later fields appear to share one encoded envelope family」与后面的 `Core idea` 内容重复）。本文拆成清晰的中文导语，并把第三句下沉到「核心思想」。
2. **源文档第 1 步的三条纪律（不要跨会话拼接 / 失败页的 config 资产同链冻结 / 失败→刷新→成功三元组先冻结）与第 2 步的「七层证明」在原文中同级并列**，但前者是**采集纪律**、后者是**分析结构**。混在一起会让读者以为七层是采集时就要分的。本文明确切分为两个编号小节。
3. **源文档无独立的 `Verification` 章节**，「Minimal handoff notes」10 条兼作验收。本文保留这 10 条，补 2 条可执行判据，并按源文档 `Dual gate note` 的显式要求，把「两道门分开记录」**提升为交接说明第 10 条** —— 原文只在正文提了一句「Record both gates separately in handoff notes」，但 handoff notes 清单里并没有对应条目，属于源文档的自相矛盾，已修正。
4. **源文档 `Common traps` 里「dual gate」的缺失**：原文 `Dual gate note` 强调两门独立，但 `Common traps` 完全没有对应条目（没有「只恢复签名器就以为挑战也过了」这类陷阱）。本文在「双门说明」段保留该警告，未擅自往「常见坑」里新增条目（避免编造源文档内容）。