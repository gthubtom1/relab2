# 传输包装手册（Transport Wrapper Playbook）

> **来源声明**：本文改编自外部仓库 `aoyunyang/spider-king-skill`（MIT License）的 `transport-wrapper-playbook.md`。原始内容为英文原文，此处译为中文并按本包六段式规范重排；技术术语保留英文原词并附中文。改编中补齐了前置与判据段（本包硬性要求）。
>
> **什么时候用**：**业务代码造的是一个参数，线上发的是另一个**的时候。
>
> **平台与本机状态**：本文是纯方法论，不含必须在本机执行的命令，因此不涉及工具可用性问题。取证手段见 `./local-mcp-environment.md`（本机 `frida 17.17.0` 可用于抓 wrapper 边界，`tshark 4.6.8` 可用于读出站 header）。文中提到的 `js-reverse` / `chrome-devtools` MCP 家族**本机未挂载**。

---

## 适用信号（Recognition signals）

- UI 代码构造了 `token`，但**网络上发的是 `m`**
- query 参数或 body 字段**只在 wrapper 执行之后才出现**
- header 在 `beforeSend` 或 fetch middleware 里被注入
- 请求序列化结果**与可见的输入对象不同**
- 候选 blob **看着是对的**，但只有把它挪到另一个 header / cookie 回显 / query 参数 / wrapper 拥有的字段里才 replay 成功
- 同一个值在 helper 返回值里是对的，在线路上却无效

## 前置（Entry conditions）

1. **有两条可比样本**：一条最终载荷已知的成功请求，和一条要对比的请求。没有 diff 就没有结论。
2. **能看到最终线上载荷**（不只是 helper 的返回值）—— 手段见「前置」下的本机路径。
3. **已知业务代码的输入对象**。否则「diff 业务层参数 vs 最终载荷」无从下手。

**本机取最终载荷的两条路**（均本机可用）：

```powershell
# 方式一：tshark 从 pcap 读出站 query / body（本机可用）
D:\Tools\Wireshark\tshark.exe -r flow.pcapng -Y "http.request" -T fields -e http.request.full_uri -e http.request.line

# 方式二：mitmproxy 实时观察改写（本机可用）
D:\EXE\python\Scripts\mitmdump.EXE --listen-port 8899 --save-stream-file flow.mitm
```

> **本机无 `reqable`**；本机 `frida 17.17.0` 可用于在 wrapper ingress/egress 处抓「改写前 vs 改写后」。

## 步骤（Working method）

> **核心规则：规范化变更点是「线上载荷发生变化」的那个位置，不是业务代码第一次造出占位符的那个位置。**

1. **diff 业务层参数 vs 最终线上载荷**
2. **先看 wrapper，再往业务代码深处挖**
3. **精确记录 wrapper 增加了、改写了、删除了、或搬移了哪些字段**
4. **证明每个决定性产物的最终传输 slot（传输槽位），不只是它的值形状**
5. **在本地重建 wrapper 逻辑**
6. **验证最终序列化后的载荷，不只是中间对象**

## 判据（Verification checklist）

**「传输包装已解决」= 以下全部为真：**

1. **有一份明确 diff**：业务层参数 ↔ 最终线上载荷，逐字段列出。
2. **每个决定性产物的最终 slot 已证明**（query / body / header / cookie / 回显字段），**不是**只验证了它的值形状。
3. **wrapper 的四类动作被显式记录**：增加、改写、删除、搬移。
4. **最终序列化载荷在本地可重建**，且与线上逐字节（或按契约逐字段）一致。
5. **诱饵（decoy）字段被排除在最终 collector 之外** —— 它可以留在分析笔记里，但不在交付路径里。
6. **重复 replay 成功**，而不是一次侥幸（规程见 `../triage/verifier-replay-playbook.md`）。

## 常见坑（Common traps）

- 去逆向一个**根本不会上线路**的诱饵参数
- **站点签的是 URL 编码后的值，你签了已解码的值**
- 假定可见的 JSON 就是被签名的载荷
- 一个「看起来合理」的 blob 被放**在错误的传输 slot** 里，就宣称完成
- 只验了 helper 的返回值，没验它在线路上的位置
- 把 cookie jar 里读出的值当成完整的 wire 真相（实际出站 `Cookie` 头顺序或拼装方式可能不同，见 `../state/cookie-provenance-playbook.md`）
- 在 wrapper 层没看完就去改业务代码

## 相关（Related）

- `./dual-writer-param-playbook.md` —— 同一字段有两个写入者时，先判哪个是 wire-success
- `./structured-transport-playbook.md` —— 二进制信封里的 slot 问题
- `./decoy-and-real-request-playbook.md` —— 诱饵不只是字段，也可能是整条路由
- `../state/cookie-provenance-playbook.md` —— 「值对、位置错」的经典形态
- `../principles/doctrine-index.md` —— 教条 2（动态参数不总是签名）、教条 1（信 wire 不信页面文案）
- `../deliver/delivery-gate-playbook.md` —— 交付时「移动部件已显式命名」这一条

---

## 源文档勘误（改编时修正）

1. **源文档只有 `Recognition signals` / `Working method` / `Common traps` / `Delivery rule` 四段，缺前置与判据。** 改编补入前置（两条可比样本 + 能看到最终载荷 + 本机两条取载荷命令）与判据 6 条。其中「诱饵字段被排除在最终 collector 之外」是从源文档 `Delivery rule`（「keep the decoy field out of the final collector」）提炼而来 —— 源文档把它写成了交付原则，但没有可检查的判据。
2. **源文档的 `Delivery rule` 与 `Common traps` 第 4 条（诱饵参数）表述重叠**，读者容易以为是两条独立风险。改编把它收敛到「诱饵」这一条事实：常见坑描述失败形态，判据第 5 条描述完成条件。
3. **源文档的 `Recognition signals` 第 5 条把「候选 blob 看着对但只有换 slot 才 work」写成一个信号，而 `Common traps` 第 4 条写的是同一件事的失败面。** 改编在判据第 2 条把它变成硬要求（「证明每个决定性产物的最终传输 slot，不只是值形状」），这是全文最容易被跳过、也最致命的一步。
4. **源文档第 2 步写「inspect wrappers before digging deeper into business code」，但没说清为什么。** 改编保留该顺序，并在「核心规则」上方保留一句因果（规范化变更点在 wire 侧），使顺序不再是经验之谈。
5. **源文档没有说明「最终线上载荷」的获取手段**，默认读者已有 HAR 或浏览器网络面板。改编补入本机两条实际命令并标注 `reqable` 本机无。
