# 页面专属例外手册（Page-Specific Exception Playbook）

> **来源声明**：本文改编自外部仓库 `aoyunyang/spider-king-skill`（MIT License）的 `page-specific-exception-playbook.md`。原始内容为英文原文，此处译为中文并按本包六段式规范重排；技术术语保留英文原词并附中文。源文档为短篇，改编补齐了前置与判据段（本包硬性要求）。
>
> **什么时候用**：**大部分页面都正常，只有某一个页面失败**；或者只有某一个请求需要一条特殊的 header、cookie 或顺序规则。
>
> **平台与本机状态**：本文是纯方法论，不含必须在本机执行的命令。取证手段见 `./local-mcp-environment.md`（本机 `tshark 4.6.8` 比对请求头、`mitmdump 12.2.3` 实时观察、`frida 17.17.0` 抓调用上下文）。MCP 浏览器家族**本机未挂载**。

---

## 适用信号（Recognition signals）

- 第 1 到 4 页正常，**某**一页失败
- 最后一页返回**提示、字符串、或反爬标记**
- **只有一条**请求需要一个特殊 header、cookie 或请求顺序
- 「签名器坏了」的直觉出现，但**只有一页**行为异常
- 采集跑到一半成功率骤降，且降的不是页码而是**特定路由**

## 前置（Entry conditions）

1. **至少一页成功 + 至少一页失败**，两者都记录了完整请求规格。否则「diff 成功页 vs 失败页」无从做起。
2. **失败页的失败是稳定的**（可重复），不是一次网络抖动。不可重复的失败请走 `../triage/reproducible-evidence-playbook.md`。
3. **确认失败面**：是「签名被拒」还是「传输层被拒」还是「权限被拒」？三者的修法完全不同。若连抓包都在 TLS 层就断了，先走 `./transport-pre-gate-playbook.md`。

## 步骤（Working method）

> **核心规则：保持例外的狭窄。**

1. **把成功页与失败页做 diff**
2. **逐项比较 headers、cookies、referer、user agent，以及请求顺序**
3. **一次只测一个窄改动**
4. **把已验证的例外编码进 per-page 或 per-request 设置**
5. **collector 的其余部分保持不变**

**典型的窄例外：**

- 最后一页或单一路由的 `User-Agent` 覆盖
- 单一路由的 referer 或 origin 要求
- 单一路由的额外 header，而成功兄弟请求并不发送它

**「一次只测一个窄改动」是本文的核心纪律。** 同时改 UA 和 referer，即使结果变好了，你也不知道是哪一个生效 —— 那会在后续升级时以另一种形态复发。

## 判据（Verification checklist）

**「窄例外已确认」= 以下全部为真：**

1. **例外被写进文档**，有明确的作用域（哪条路由 / 哪个页码 / 哪个请求）。
2. **有 before-and-after 响应证据**：改动前失败、改动后成功，两次响应都被记录。
3. **例外只作用于它被证明需要的范围** —— collector 的其余请求路径未被污染。
4. **例外以配置形式存在**（per-page / per-route settings），而不是散落在业务逻辑里的 `if`。
5. **签名的通用逻辑未被修改**来「顺便兼容」这一页。

## 常见坑（Common traps）

- **假设 signer 坏了**，而真实问题只是**一个 header**
- 把一个页面的 workaround **扩散到整条流水线**
- 因为**一页行为不同**就宣称目标「只能靠浏览器」
- 一次改多个变量，然后不知道是哪一个起了作用
- 把「最后一页」当成天然的特殊页 —— 它可能只是恰好是那个路由家族的分界点（见 `./pagination-route-pivot-playbook.md`）
- 例外的作用域写得太宽（「所有 GET」），实际只需要一条路由

## 相关（Related）

- `./pagination-route-pivot-playbook.md` —— 「最后一页特殊」往往实为路由家族切换
- `./transport-wrapper-playbook.md` —— 例外可能来自 wrapper 的 per-route 分支
- `./dual-writer-param-playbook.md` —— 「某一页特殊」有时是「第二次尝试走了另一写入者」
- `./transport-pre-gate-playbook.md` —— 先排除传输层准入，再谈页面级例外
- `../principles/doctrine-index.md` —— **教条 4（窄例外保持狭窄）**，本文是它的落地形态

---

## 源文档勘误（改编时修正）

1. **源文档全文只有 35 行、五个小节**，其中 `Core rule` 只有一句「Keep narrow exceptions narrow」。它缺前置与判据 —— 而「怎样才算例外已验证」正是本文最容易糊弄过去的地方。改编补入前置 3 条与判据 5 条，其中判据第 2 条「有 before-and-after 响应证据」直接来自源文档 `Delivery rule`（「prove it with before-and-after responses」），只是把它从一句原则变成可检查项。
2. **源文档第 3 步「test one narrow change at a time」是一条纪律，但源文档没有说明不遵守会怎样**，读者容易当成可有可无的风格建议。改编在「步骤」里把它标为**核心纪律**并给出具体后果（后续升级会以另一种形态复发）。
3. **源文档的 `Common traps` 第 3 条「declaring the target browser-only because one page behaves differently」与本文的核心规则重叠，但源文档没有指出它其实是教条 4 的一个具体失败形态。** 改编在相关段显式指向 `../principles/doctrine-index.md` 教条 4，让本文成为那条教条的具体落地，而不是又一条并列规则。
4. **源文档没有区分「这一页特殊」的两种成因**：真正的 per-page 例外，和**路由家族在某个页码切换**（后者见 pagination handbook）。改编在常见坑里显式点名「最后一页可能只是路由分界点」，避免读者把路由切换当成页级特例硬编码。
5. **源文档第 2 步的对比清单里没有「请求顺序」的可操作性说明**，而顺序恰恰是只有单页失败时最常见的原因。改编保留该项，并在前置第 3 条要求先确定失败面（签名 / 传输 / 权限），因为三者的顺序问题修法完全不同。
