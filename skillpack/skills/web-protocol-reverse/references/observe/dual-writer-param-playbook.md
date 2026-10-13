# 双写入者参数手册（Dual-Writer Param Playbook）

> **来源声明**：本文改编自外部仓库 `aoyunyang/spider-king-skill`（MIT License）的 `dual-writer-param-playbook.md`。原始内容为英文原文，此处译为中文并按本包六段式规范重排；技术术语保留英文原词并附中文。改编中补齐了前置与判据段（本包硬性要求）。
>
> **什么时候用**：**同一个请求字段名可能被多个客户端路径写入**，且**短离线 token 的形状 ≠ 线上成功的形状**。
>

---

## 适用信号（Route here when）

- 同一个 query / header / body key **有时承载短 token，有时承载长 token**
- 离线恢复出某个写入者（hash、LZW、短签名器）成功，**但线上 replay 仍返回挑战页或空壳**
- 调用栈显示**多于一条路径**在动这个字段：open 改写、send 重试、challenge 导航、cookie 投影进 query
- **样本的精确 URL 重放能成功**，但用恢复出的短生成器配新鲜时间戳就失败
- 成功样本上是**会话稳定前缀 + URL 绑定 body**，而研究样本只有紧凑压缩 token

## 前置（Entry conditions）

1. **至少两条成功的线上值**（同一字段）。只成功过一条，就分不出「长度带」。
2. **能取到线上 egress**（出站）证据，而不只是 helper 返回值 —— 见 `./transport-wrapper-playbook.md` 的本机取载荷命令。
3. **能区分两次请求尝试**（首次未命中 vs 重试），否则分不出「challenge rewrite」这一类。

## 步骤（Working method）

### 核心思想

**一个参数名不是单一算法。**

**在深度移植任何候选写入者之前，先证明 wire-success writer（线上成功的写入者）。**
**在次要路径上做的离线自检是研究证据，不是交付证明。**

### 快速执行路径

1. **为同一字段冻结两条或更多成功的线上值。** 每个值记录：
   - 长度
   - 固定前缀 / 会话段
   - 分隔符（`-`、`|`、`_`）
   - 字符集成员
   - URL / 时间戳 / 页面 / body 绑定
   - 是哪一次请求尝试产生的（首次未命中 vs 重试）

2. **对写入者（writer）分类，而不只是对值分类。** 常见类：

   - **short signer（短签名器）**：对 `url|ts|flag` 风格明文的紧凑压缩/哈希
   - **long body（长 body）**：会话或环境前缀 + 高熵或多段 body
   - **challenge rewrite（挑战改写）**：挑战 HTML/JS 导航或以改写后的业务 URL 重试
   - **cookie projection（cookie 投影）**：cookie 物被 open hook 注入进 query

3. **把每一类映射到调用栈。** 优先用**线上** open/send/fetch hook 拿到的 initiator 栈，而不是只看源码的猜测。**同一字段可能在不同门（mode flag 为零/一、captcha 已加载、首次失败 HTML）下被不同类写入。**

4. **只在线上接受的那一类上做交付。**
   - 若短 token **从未出现在成功的线上样本**上，**不要**把短 token 生成器当产品路径交付
   - 若长 token **只在挑战 HTML 之后出现**，先走挑战产物摘取（`../state/challenge-artifact-harvest-playbook.md`）

5. **分别证明绑定关系与刷新路径：**
   - **URL-bound（URL 绑定）**：换时间戳/页面会使 body 失效
   - **session-bound（会话绑定）**：前缀在同一挑战/会话链内稳定
   - **cookie-bound（cookie 绑定）**：需要配套 cookie
   - **echo-bound（回显绑定）**：replay 可能需要原始 URL 被反射到某个额外字段

6. **显式报告双写入者状态。** 点名：
   - 哪个研究写入者被恢复但在线上被拒
   - 哪个交付写入者真正过了门
   - 若仍存在多于一个成功类，剩余的不确定性是什么

## 高价值检查（High-value checks）

- 成功样本共享**同一个长度带**，还是**两个不相交的长度带**？
- 短路径在 SDK 源码里存在，但**只在某个 mode flag 为零/一时才跑**？
- 长路径是否**只在第二次尝试（HTML 挑战之后）出现**？
- 应用层 HMAC/sign **是否排除了 verifier 参数**，同时仍然被浏览器 XHR 要求？
- 挑战路径能否**在没有 app signer 的情况下**成功？反之呢？

## 判据（Verification checklist）

**「双写入者已解决」= 以下全部为真：**

1. **长度带已分类**：成功样本的长度分布被判定为「一带」还是「两带」，并有证据。
2. **写入者类已枚举**，每类有调用栈或线上证据支撑，**不是**只看源码。
3. **wire-success 类被明确点名**，且该类在**新鲜 URL / 新鲜时间戳**上能重新生成（不是只重放样本）。
4. **被拒的研究写入者被明确标注为误导性**，且不在最终交付路径里。
5. **绑定关系被分别证明**：URL / 会话 / cookie / 回显，各自明确或明确标注为未证明。
6. **app signer 门与 verifier 门被分别列出**，各自给出必要性证明。
7. **最终交付明确 Python 拥有线上 HTTP**；本地 helper（若存在）只返回 `redirectUrl` 和/或 `cookieString`，Python 负责重放并校验业务 JSON/HTML 锚点。
8. **分页在成功类被证明之后才做**（顺序：识别成功类 → 在新鲜 URL 上摘取/重生成该类 → 才分页）。

## 常见坑（Common traps）

- 把**唯一被完整反编译出来的**写入者当成唯一真实写入者
- 把一个已知的会话前缀**拼接到短 body 上**，然后称之为「长 token 恢复」
- 样本精确重放成功后，就宣布协议自动化完成
- 挑战 helper 已经吐出改写后的 URL 了，还在继续挖加密
- 把 app signer 恢复和 verifier 恢复**混成一个未完成的工单**
- 看到 SDK 源码里有短路径就假设它是产品路径 —— 它可能只在某个从未触发的 flag 下运行
- 把「第二次尝试才出现的长 token」当成第一个 bug 去修 signer
- 混淆「值对」与「slot 对」—— 长 token 值对但放错字段位仍会失败（见 `./transport-wrapper-playbook.md`）

## 交付建议（Delivery guidance）

**偏好顺序：**

1. 识别 **wire-success 类**
2. 在**新鲜 URL** 上摘取或重新生成该类
3. **然后才**分页
4. 把被拒的写入者**留在分析笔记里**作为误导信号

**当成功类是 challenge rewrite 时，helper 的 I/O 契约：**

- Python 拥有线上 HTTP
- 本地 helper 返回 `redirectUrl` 和/或 `cookieString`
- Python 负责重放并校验业务 JSON / HTML 锚点

## 相关（Related）

- `./transport-wrapper-playbook.md` —— slot 位置与 wrapper 改写
- `../state/challenge-artifact-harvest-playbook.md` —— 挑战 helper 已产出改写 URL 时走这条
- `../state/challenge-state-envelope-playbook.md` —— 挑战输出作为协议状态
- `../crypto/local-challenge-executor-playbook.md` —— 本地挑战执行器的最小宿主契约
- `../principles/doctrine-index.md` —— 教条 18（在最近的稳定边界上摘取挑战产物）、教条 20（按失败面拆分验证器目标）
- `../deliver/delivery-gate-playbook.md` —— X1/X4/X6 附加项的验收位置
- `../../../field-journal/seed-004_js-sign-webpack.md` —— 本包已有的「短 signer 恢复后线上仍失败」类问题的实战参照

---

## 源文档勘误（改编时修正）

1. **源文档的 `High-value checks` 与 `Minimal handoff notes` 高度重叠** —— 前者问「是否两带、是否 flag 门控、是否第二次尝试才出现」，后者要求报告「长度带、写入者类、哪个被线上接受、绑定是什么」。两者其实是**同一组事实的问法与答法**。改编把前者保留为「要验证的问题」（并入「步骤」的检查清单），把后者转成**判据**，角色分开，不重复陈述。
2. **源文档第 4 步写「Live-accept only the class present on successful business responses」，但没有要求在**新鲜 URL 上**重新生成该类。** 只在已捕获样本上验证，会漏掉「这个类其实是样本专属」的情况。改编在判据第 3 条显式加上「新鲜 URL / 新鲜时间戳」这一要求。
3. **源文档第 2 步列的四类写入者里，`cookie projection` 的描述是「cookie 物被 open hook 注入进 query」，措辞不完整**（原文 "cookie material injected into query by an open hook"）。这实际是 `../state/cookie-provenance-playbook.md` 里第 7 类（本地 helper 拼装出站 `Cookie` 头）的镜像形态。改编保留该类并在相关段建立交叉引用，避免两处各说一半。
4. **源文档第 3 步提到「mode flag（`kn`-式）」这一具体厂商风格标记，但整篇方法论是通用的**（未在该文档其他任何地方依赖该厂商）。改编保留其作为**举例**，在判据第 2 条要求「每类有调用栈或线上证据支撑」，避免读者把「找到 `kn` flag」当成通用做法。
5. **源文档的 `Delivery guidance` 第 3 步「only then paginate」是一条排序纪律，但没有判据支撑** —— 跳过分页前先摘取成功类，是本文最容易被违反的顺序。改编把它提为判据第 8 条，使顺序变成可检查项。
