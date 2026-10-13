# 传输层前置门手册（Transport Pre-Gate Playbook）

> **来源声明**：本文改编自外部仓库 `aoyunyang/spider-king-skill`（MIT License）的 `transport-pre-gate-playbook.md`。原始内容为英文原文，此处译为中文并按本包六段式规范重排；技术术语保留英文原词并附中文。改编中补入了本机 `curl_cffi` 落地路径并删除了失效的脚本引用（见文末「源文档勘误」）。
>
> **什么时候用**：**干净基线在有意义的应用语义出现之前就死掉**的时候。
>

---

## 适用信号（Route here when）

- 标准 HTTP 客户端在 **H2 reset / TLS EOF / 握手超时 / 早期断开**上死掉
- 同一条路由在不同 UA 家族、HTTP 版本、ALPN 或客户端栈上表现不同
- 抄了浏览器 header 和 cookie 之后 stdlib 客户端**仍然**失败，而类浏览器传输却走到了另一个分支
- 模拟传输 / 移动或 app UA 能过，而默认桌面或 stdlib 流量失败
- 一条被挑战的落地路由失败，**但**兄弟的 auth、identity 或业务路由仍然可用
- 同一份实现在不同代理出口或网络路径上**时好时坏**

## 前置（Entry conditions）

1. **先确认失败发生在应用语义之前**。如果签名/cookie/解码逻辑都还没出现，就还没有进入本文的场景。
2. **有一条成功的浏览器基线**（或至少一次成功的类浏览器传输）作为对照，否则你无法判断「被拒」还是「本来就这样」。
3. **抓包手段**（本机两条都可用）：
   - `curl_cffi` 抓不到 ClientHello，**包级证据要靠 `tshark`**：
     ```powershell
     # 本机可用：抓 ClientHello 与 ALPN
     & (Resolve-ReverseToolSpec -Name 'tshark').Command -r flow.pcapng -Y "tls.handshake.type == 1" -V
     ```
   - 本机无 `reqable`；实时改写/流落盘用 `mitmdump`：
     ```powershell
     & (Resolve-ReverseToolSpec -Name 'mitmdump').Command --listen-port 8899 --save-stream-file flow.mitm
     ```
4. **授权边界已记录**（见 `../contract/provider-work-order.md`）。本文会触发真实外联，必须先有 egress 授权。

## 步骤（Working method）

### 核心思想（Core idea）

**传输层准入（transport admission）是一套独立契约，与 signer、cookie、payload 逻辑无关。** 这套契约可能在普通 HTTP 语义存在之前就已决定。

**把准入 profile 当成一个整体来看：**

- TLS ClientHello 家族
- ALPN 与协商出的 HTTP 版本
- HTTP/2 SETTINGS、伪头顺序（pseudo-header order），以及 H2 生效时的早期请求顺序
- 声明的身份，如 UA 家族
- Client Hints、语言、时区、运行时 navigator 身份、以及在被 verifier 或遥测载荷反射时的代理出口

**在一请求被干净准入、足以观察真实语义之前，不要去逆向应用层。**
**JA3 和 JA4 是摘要指标，不是协议本身；权威证据是产生它们的那份底层传输 profile。**

### 身份一致性（Identity coherence）

保持声明的身份在各层之间**内部自洽**：

```text
传输模拟家族
  HTTP 版本与 ALPN
  User-Agent 大版本
  Client Hints brands 与版本
  运行时 navigator.userAgent / platform
  语言、时区、screen、设备类（当被采集时）
  代理出口与会话节奏
```

**不要**把 A 家族的传输 profile、B 家族的 header、C 家族的运行时指纹数据混在一起，除非线上捕获证明目标容忍这种混合。**一个组合不自洽的元组可能让根页面通过，却在后续路由、sidecar 或业务请求上失败。**

### 快速执行路径（Fast execution path）

1. **冻结一张小的准入矩阵（admission matrix）。** 记录：
   - 路由
   - 方法
   - 客户端栈
   - UA 家族
   - HTTP 版本
   - ALPN 与可见时的传输指纹家族
   - 结果类：通过 / H2 reset / 超时 / 重定向循环 / 被挑战 HTML

2. **在做大 bundle 工作之前，先做包级传输对比。** 若有 pcap、包跟踪或握手捕获，diff：
   - 密码套件集合与顺序
   - 扩展集合与顺序
   - GREASE 行为
   - supported groups、key share、签名算法
   - ALPN 提供列表
   - HTTP/2 SETTINGS 与伪头顺序
   - 传输层立即流水线化后续流量时的**首请求顺序**

3. **在做大 bundle 工作之前，先测窄的传输变化。** 常见变化：
   - stdlib 客户端 vs 模拟 TLS 客户端
   - HTTP/2 vs HTTP/1.1
   - 桌面浏览器 UA vs 移动或 app UA
   - 被挑战的落地路由 vs 兄弟 auth 或数据路由
   - 朴素客户端栈 vs 浏览器式模拟（当返回的挑战家族本身变了）
   - **最接近的浏览器家族传输后端** vs 一个需要逐字段手打补丁的**远处**默认栈

   **本机形态**（`curl_cffi` 可用，**未对具体目标验证**）：
   ```python
   from curl_cffi import requests as cf
   # impersonate 直接给出浏览器家族的 TLS/JA3/JA4/H2 profile
   r = cf.get(url, impersonate="chrome")
   ```

4. **保持例外狭窄。** 若只有一族路由需要特殊传输 profile，就限定在那里，**不要污染整个 collector**。

5. **把准入和后续门分开。** 一旦某条路由被准入，继续对 signer、verifier、decode 或 session 逻辑做常规分诊。

6. **优先走路由绕行，而不是硬啃挑战。** 若某个兄弟身份、auth 或数据路由能干净地绕开被挑战的落地路径，**先用它取证**，再决定是否值得在错误的门上花几小时。

7. **把出口信誉与实现失败分开。**
   - 当一条**此前已被接受**的协议链突然返回访问拒绝体、硬重置或滥用页面时，**先用同一出口、真实浏览器（或本机最接近的浏览器式基线）测同一条路由**，**再**去改 signer、表单或 verifier 逻辑
   - 若浏览器在该出口上也失败：标记状态为 `egress-gated`（出口受限），**换出口或冷却，然后重跑整条链**
   - 若浏览器成功但协议客户端失败：这时才去查传输一致性、sidecar 数量、cookie 迁移和序列化

### 原生（native）升级检查点

**不要仅仅因为「模拟客户端还是失败」就自建 TLS 后端。** 只有在**重复的浏览器与候选捕获**证明存在一个**决定性的传输不匹配**，且**最接近的、仍在维护的后端无法表达**它时，才升级。

**升级前冻结：**

- 确切的浏览器 build、操作系统、路由、网络路径、捕获哈希
- **至少 3 次浏览器冷连接样本**，以便把稳定字段与 GREASE 或已证明的顺序可变性区分开
- 一份来自失败客户端的**负对照（negative-control）捕获**，和一份来自最接近的候选后端的捕获
- ClientHello、ALPN、H2 SETTINGS、伪头顺序或连接行为中**确切无法表达的那个字段**
- 代理是**端到端隧道**还是**终止并替换**了客户端指纹

然后读 `./native-transport-profile-playbook.md`。**优先方案是「Python collector + 一个路由本地的原生包」**，暴露足够的诊断以证明后端与连接状态，并把**确定性证明**与任何研究用随机化器分开。

## 高价值检查（High-value checks）

- 失败发生在 header 之前、TLS 之后，还是仅在 body 字节开始流动之后？
- HTTP header 看起来像浏览器，**但 pre-HTTP 的 ClientHello 家族仍然明显不同**？
- 重定向或备用 host 是否改变了策略？
- JA3 / JA4 或其他摘要指纹**只是线索**，而真正的不匹配在原始扩展顺序、GREASE、ALPN 或 H2 SETTINGS 里？
- 目标浏览器家族**本身随机化**扩展顺序或 GREASE，导致把某个 JA3 硬冻成成功目标是坏主意？
- 移动或 app UA 改变了返回的 **HTML 形状**，而不只是通过 / 失败状态？
- ALPN、HTTP 版本、H2 SETTINGS 是否与你想重放的那个分支一致？
- UA、Client Hints、运行时 navigator 身份与采集到的 profile 字段，是否描述了**同一代客户端**？
- 两个客户端栈在同一路由上进入了**不同的挑战家族**，还是同一家族的不同成功率？
- 该路由是否需要与邻居路由**相同的**传输 profile，还是一个孤立的例外？
- 「浏览器成功」样本是真正的应用成功，还是只是**换了一条传输准入路径**？
- 「类浏览器模拟是观察浏览器所见 bootstrap 链的前提」这个判断**诚实成立吗**？
- **仅**换出口就能恢复一个已知良好实现 —— 这说明是残余出口风险，**不是算法回归**

## 判据（Verification checklist）

**「传输层准入已解决」= 以下全部为真：**

1. **一张冻结的准入矩阵**存在，每行含路由 / 方法 / 客户端栈 / UA 家族 / HTTP 版本 / ALPN / 结果类。
2. **有包级对比证据**（本机用 `tshark`）—— 至少比对了密码套件、扩展、ALPN、H2 SETTINGS 里的若干项，**不是**只比了一个摘要哈希。
3. **至少一个窄的候选被证明能干净准入**，且该结论**在同一条路由、同一类应用请求上**成立。
4. **有负对照**：已知失败的朴素栈在同一条件下仍失败 —— 证明你的候选是**起作用了**，而不是环境自己变了。
5. **准入之后有真实业务语义被观察**，**不是**只有另一个挑战家族或状态码变化。
6. **例外是路由局部的**（route-local），并已显式声明作用域。
7. **摘要指纹（JA3/JA4）的角色被诚实标注** —— 是线索还是被证明的接受条件。
8. **出口信誉被单独判定**：失败被标为 `egress-gated` 或路由本地传输风险，**而不是**「实现不稳定」。
9. **最终交付路径不含浏览器依赖**（见 `../deliver/delivery-gate-playbook.md` 第 19 条）。

## 常见坑（Common traps）

- **为从未通过传输层准入的流量**去怪罪 cookie 或签名
- 只改 `User-Agent` 或 HTTP header，而门其实由 ClientHello 或 H2 profile 在请求语义存在之前就决定了
- 把 JA3 / JA4 相等当成唯一目标，而不是匹配路由**实际检查的**底层传输行为
- 硬冻某个浏览器指纹哈希，而该浏览器家族其实在请求间随机化扩展顺序或 GREASE
- 只有一条路由需要一个特殊 UA，却在**整个** collector 里硬写一个「魔法 UA」
- 把「模拟 TLS」当成最终胜利，而不是应用层逆向的**起点**
- 因为用了较弱的客户端栈被静默分到**另一个门家族**，于是去逆向错误的 verifier 或挑战页
- 在测过更接近的传输家族或窄的路由本地适配器之前，就去逐字段手打一个**远处默认 TLS 栈**的补丁
- 假定被挑战的落地页是唯一值得测的入口路由
- **本机补充**：以为「有 `curl_cffi` 就等于解决了准入」—— `impersonate=` 只是换了一个已知浏览器 profile，**它并不表达任意自定义 ClientHello**；需要更细粒度控制时才升级到 `./native-transport-profile-playbook.md`
- **本机补充**：本机**没有** `WireMCP`，包级证据走 `tshark`；本机**没有** `reqable`

## 相关（Related）

- `./native-transport-profile-playbook.md` —— 仅在本文证明「路由传输受限且最接近的后端无法表达」之后才读
- `./structured-transport-playbook.md` —— 准入过了之后的 GraphQL / WebSocket / protobuf / gRPC 层
- `./dual-writer-param-playbook.md` —— 「不同客户端栈进入不同挑战家族」的下游表现
- `./local-mcp-environment.md` —— 本机工具与挂载表现状（**web 侧 MCP 本机未挂载**）
- `../deliver/delivery-gate-playbook.md` —— 第 19 条 `egress-gated` 标签的验收位置
- `../principles/doctrine-index.md` —— 教条 17（传输层准入是一套独立契约）
- `../contract/provider-work-order.md` —— 外联授权与请求预算

---

## 源文档勘误（改编时修正）

1. **源文档第 7 步（把出口信誉与实现失败分开）写得很长但埋在「快速执行路径」末尾**，位置偏低，读者容易在前六步就把出口问题误判成算法回归。改编把它保留在第 7 步的同时，在判据第 8 条与常见坑里**各点名一次**，并与 `../deliver/delivery-gate-playbook.md` 第 19 条的 `egress-gated` 标签建立显式链接 —— 源文档两篇文档之间没有任何交叉引用。
2. **源文档引用 `scripts/transport_profile_diff.py` 来比较结构化浏览器与候选 profile，但本包 `web-protocol-reverse/scripts/` 目录不存在，该脚本在全仓库也搜不到。** 改编**删除该脚本引用**，改为给出本机可执行的 `tshark` 命令作为包级对比的实际做法。这是落地时的真实缺口，不是改编引入的问题。
3. **源文档第 3 步列出的变化项里没有点名任何具体客户端库**，读者无法照做。改编补入本机 `curl_cffi` 的实际接入形态（明确标注「未对具体目标验证」），因为 `curl_cffi` 正是覆盖该列表前四项的本机现成手段。
4. **源文档说「传输层模拟家族」而不给任何一致性检查清单**，`Identity coherence` 一段只列了维度名。改编在判据第 7 条明确要求「摘要指纹的角色被诚实标注」，把源文档散落在 `Core idea` 里的一句话变成可检查项。
5. **源文档的 `Route here when` 与 `High-value checks` 有明显重叠**（H2 reset、UA 家族差异等各出现两次）。改编保留 `Route here when` 作为路由触发条件，把 `High-value checks` 收缩为**「要问的问题清单」**（两者角色不同），并在源文档同一文件的 `Common traps` 里保留了对应的否定面 —— 避免同一事实出现三遍而让读者以为是三条独立风险。
