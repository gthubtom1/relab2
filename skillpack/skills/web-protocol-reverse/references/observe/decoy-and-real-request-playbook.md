# 诱饵与真实请求手册（Decoy and Real Request Playbook）

> **来源声明**：本文改编自外部仓库 `aoyunyang/spider-king-skill`（MIT License）的 `decoy-and-real-request-playbook.md`。原始内容为英文原文，此处译为中文并按本包六段式规范重排；技术术语保留英文原词并附中文。源文档为短篇，改编补齐了前置与判据段（本包硬性要求）。
>
> **什么时候用**：**页面代码指向一个端点，而线路上走的是另一个**的时候。
>
> **平台与本机状态**：本文是纯方法论，不含必须在本机执行的命令。取证手段见 `./local-mcp-environment.md`（本机 `tshark 4.6.8` 读线路、`mitmdump 12.2.3` 实时观察、`frida 17.17.0` 抓 initiator 栈）。**本机 `reqable` 无**；MCP 浏览器家族 `chrome-devtools` / `js-reverse` **本机未挂载**。

---

## 适用信号（Recognition signals）

- 页面代码 hook 的是 `/api/match/...`，但**网络上发的是 `/api/question/...`**
- 第一个可见请求是**诱饵**，真实请求由一个 wrapper 触发
- 路径在**重定向、wrapper、或兼容页之后**发生变化
- 页面上可见的表单提交**不是**线路上的真实业务请求
- 旧笔记、截图、代码片段与**新鲜的网络流量**互相矛盾
- 页面 HTML 里写着一个路由，但 XHR 面板里根本没有它

## 前置（Entry conditions）

1. **有新鲜的网络流量证据**。只有页面文本、旧笔记或截图，不足以判定谁是诱饵 —— 判据全部建立在线路上。
2. **能记录 initiator（发起方）**。手段见下。

**本机取线路证据的两条路**（均本机可用）：

```powershell
# 方式一：tshark 列出真实出站请求（本机可用）
D:\Tools\Wireshark\tshark.exe -r flow.pcapng -Y "http.request" -T fields -e http.request.method -e http.host -e http.request.uri

# 方式二：mitmproxy 实时观察（本机可用）
D:\EXE\python\Scripts\mitmdump.EXE --listen-port 8899 --save-stream-file flow.mitm
```

## 步骤（Working method）

> **核心规则：信线路，不信页面文案。**

1. **捕获那条真正返回有用数据的网络请求**
2. **记录 method、path、query、headers、cookies 和 initiator**
3. **把 initiator 回溯到规范化变更点**（见 `./transport-wrapper-playbook.md`）
4. **显式记录诱饵路径**，使它不会泄漏进交付代码
5. **只对已验证的线上路径编码**

## 判据（Verification checklist）

**「真实请求已确认」= 以下全部为真：**

1. **真实请求的完整六元组已记录**：method / path / query / headers / cookies / initiator。
2. **诱饵路径被显式写进分析笔记**，且**不出现在最终 collector 的任何请求构造里**。
3. **initiator 已回溯到规范化变更点**（不只是记了一个函数名）。
4. **collector 只对已验证的线上路径编码**，没有「以防万一」的死路径。
5. **旧笔记与新鲜流量的矛盾已被裁决**，并在笔记中记录了以哪一方为准。

## 常见坑（Common traps）

- **比新鲜网络证据更相信**页面内联代码
- 在 collector 里「以防万一」保留**死掉的请求路径**
- 因为页面**仍然提到**某个旧端点，就假设它仍然重要
- 把页面文案、README 声明、过期截图当成线路真相
- 只记了真实路径，没记诱饵路径 —— 后来者会重新踩同一个坑
- 只记了路径，没追 initiator —— 下次换个 wrapper 你仍然定位不到

## 相关（Related）

- `./transport-wrapper-playbook.md` —— 「业务造一个、线上发另一个」的字段级版本
- `./pagination-route-pivot-playbook.md` —— 路由在序列中途切换的版本
- `../principles/doctrine-index.md` —— **教条 1（信线路，不信页面文案）**，本文是它的最短落地形态
- `../principles/doctrine-index.md` 教条 14（原始源码可能胜过解析后的 DOM）—— 诱饵也可能藏在原始 HTML 里
- `../triage/startup-triage-playbook.md` —— 新目标接入时的第一轮分诊

---

## 源文档勘误（改编时修正）

1. **源文档全文只有 36 行、五个小节**，其中 `Core rule` 只有一句「Trust the wire, not the page text」。作为一份独立手册，它缺前置（拿不到新鲜流量时怎么办）与判据（怎样才算「真实请求已确认」）。改编补入前置 2 条与判据 5 条 —— 其中判据第 2 条「诱饵路径被写进笔记但不在交付代码里」直接来自源文档 `Delivery rule` 的后半句，只是把它变成了可检查项。
2. **源文档 `Working method` 第 4 步「document the decoy path explicitly so it does not leak into delivery code」与 `Delivery rule`（「collector should mention the decoy path in notes, but never depend on it」）是同一件事的两种说法**，分处两个小节。改编合并为判据第 2 条。
3. **源文档的 `Recognition signals` 第 4 条「the visible form submit is not the real business request on the wire」实际属于「表单提交」这个独立症状**，与前三条（代码路径不符、首个请求是诱饵、重定向后路径变化）不属于同一层。改编保留该条，但把它归入「诱饵可能发生在多个层次（路径 / 请求 / 提交动作）」这一事实，并在相关段指向字段级手册 `./transport-wrapper-playbook.md`，避免读者只修路径而漏掉字段与提交动作。
4. **源文档没有说明「怎么确认线路是新鲜的」**，而整篇的核心规则就是「信线路」—— 若线路证据本身是旧的，规则会误导。改编在「前置」第 1 条显式要求「**新鲜**的网络流量证据」，并把「旧笔记与新鲜流量矛盾时以哪方为准」提为判据第 5 条。
