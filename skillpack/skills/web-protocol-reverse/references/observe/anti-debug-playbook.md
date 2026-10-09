# 反调试手册（Anti-Debug Playbook）

> **来源声明**：本文改编自外部仓库 `aoyunyang/spider-king-skill`（MIT License）的 `anti-debug-playbook.md`。原始内容为英文原文，此处译为中文并按本包六段式规范重排；技术术语保留英文原词并附中文。源文档为最短的一篇（27 行），改编**大幅补齐**了前置与判据段（本包硬性要求），并在不改变其立场的前提下补入了本机处置手段。
>
> **什么时候用**：**线上工具变得不稳定，或者页面在抵抗检查（inspection）**的时候。
>
> **平台与本机状态**：`python 3.12.0`（`D:\EXE\python\python.exe`）、`node v24.20.0`（`D:\Tools\Node\node.exe`）本机可用；`tshark 4.6.8`（`D:\Tools\Wireshark\tshark.exe`）本机可读线路。MCP 浏览器家族 `chrome-devtools` / `js-reverse` **本机未挂载**——这一点本身减轻了本文场景的压力（本机不依赖浏览器调试器做取证）。源文档**没有提到 `frida`**，改编按本机事实补入（`frida 17.17.0` 可用）。

---

## 适用信号（Recognition signals）

- **反复的调试器暂停**（debugger pauses）
- DevTools 触发的**时序变化**
- **源码在 load 后消失或自我重写**
- MCP 或浏览器工具**在检查下超时**
- 页面在检测到 devtools 打开后**立刻改变行为**（转向纯离线）
- 调试器一挂上，目标请求就带上了一枚平时不存在的 cookie / header

## 前置（Entry conditions）

1. **先确认它是真反调试，而不是你的工具本身坏了**。判别方法：换一个**完全不同的**观察通道（浏览器内读取 vs 进程级 hook vs 纯抓包），若三条都失败，才判定为反调试。
2. **先保存一条干净基线**（未挂调试器时的请求/响应），否则你无法判断挂上工具后页面变了什么。
3. **确认授权边界**（`../contract/provider-work-order.md`）。本文全部动作都是「取证」，不涉及绕过权限。

## 步骤（Working method）

**核心立场：反调试改变的是**调查路径**，不是**交付目标**。采集器仍然是协议专属的。**

### 响应计划

1. **保存 HTML 与内联脚本**
2. **保存已下载的资产**
3. **把去混淆（deobfuscation）移到离线**
4. **用固定输入**，而不是长时间交互式会话
5. **把运行时检查压缩到最小的一个 hook 或快照**

### 本机补充手段

源文档的响应计划是「通用动作」，本机可以这样落地（**均本机可用；未对具体目标验证**）：

- **保存资产**：`tshark` 抽 HTTP 响应体落盘，或用 `mitmdump`（`D:\EXE\python\Scripts\mitmdump.EXE`）落流。**本机无 `reqable` / `WireMCP`。**
- **最小 hook 优先**：`frida 17.17.0`（`D:\EXE\python\Scripts\frida.exe`）可以做**极窄的**、只读的 hook，比挂调试器对目标的影响面小得多。
- **离线去混淆**：`node v24.20.0` 在本地跑脚本，取固定输入输出。
- **快速判定反调试 vs 工具故障**：若三条通道（浏览器读 DOM / frida 进程级 hook / tshark 纯抓包）表现不一致，那多半是你的工具状态问题，不是页面反调试。

## 判据（Verification checklist）

**「反调试已绕过」= 以下全部为真：**

1. **反调试已被确认为真的**，而非工具故障——通过至少两个独立通道交叉验证。
2. **干净基线在挂工具之前已保存**。
3. **HTML、内联脚本与关键资产均已保存**，不依赖页面继续在线。
4. **去混淆在离线完成**，不依赖实时页面上下文。
5. **调查已切换到固定输入**，而非长交互会话。
6. **运行时检查被压缩到最小**（单个窄 hook 或一次快照）。
7. **最终交付仍是协议专属、无浏览器依赖的** —— 这一点是本文立场的验收。

## 常见坑（Common traps）

- **反调试明显了还在硬刚线上页面**（brute-forcing the live page）
- 因为「页面很烦」就**认定协议不可能逆**
- 把「工具超时」直接当成「页面在反调试」，而没有换通道验证
- 把「挂上调试器后目标行为变了」（观察者效应，Doctrine 10）当成反调试证据
- **本机补充**：以为必须挂浏览器调试器才能取到证据 —— 本机 `frida` 进程级 hook + `tshark` 抓包往往就够了

## 相关（Related）

- `./hook-techniques.md` —— 最小侵入 hook 的完整方法论与本机路径（frida/playwright）
- `../principles/doctrine-index.md` —— **教条 10（观察者效应是真的）** 与本文密切相关
- `../crypto/obfuscation-guide.md` —— 混淆与去混淆手法
- `../crypto/offline-inline-deob-playbook.md` —— 离线去混淆路径
- `../triage/reproducible-evidence-playbook.md` —— 固定输入取代长会话的规程
- `../../../field-journal/precedent-reverse.md` —— 反调试类 case 的授权与处置先例

---

## 源文档勘误（改编时修正）

1. **源文档的 `Recognition signals` 列了四种现象，但没有区分「页面真的在反调试」与「工具本身不稳定」**——两者都表现为「工具超时」，而解法完全相反。源文档的 `Common traps` 只说了「不要因为页面烦就认为不可能逆」，也没说「不要把工具故障误判为反调试」。改编在**前置第 1 条**显式要求用**多个独立通道**交叉验证，并在判据第 1 条把它变成硬要求。这是本篇最容易被误用的地方。
2. **源文档的 `Recognition signals` 有一条「MCP or browser tools time out under inspection」，但源文档同一份技能包的其他篇（如 mcp-routing）里 MCP 工具超时也被列为「控制权丢失」，需要 `capability snapshot` 刷新**。两者在源文档里没有区分，读者容易混淆「工具超时 = 目标反调试」与「工具超时 = 注册表变了」。改编在步骤的「本机补充手段」里把后者（工具状态）单独点出。
3. **源文档第 3 步「move deobfuscation offline」与第 4 步「use fixed inputs instead of long interactive sessions」是同一原则的两种表述**（都指向「把工作从线上会话里搬到离线」）。改编保留两条，但在判据第 4、5 条把它们合并成一条验收（去混淆离线 + 固定输入），避免重复。
4. **源文档的 `Delivery rule`（反调试改变调查路径而非交付目标）写得很好，但**全文没有一处**可检查的判据**。改编补入 7 条判据，并保留该句作为「核心立场」置于开头。
5. **源文档没有提到 `frida`**，而 `frida` 是本机事实上的最小侵入 hook 手段。改编按本机事实补入（并明确标注本机无浏览器调试 MCP，这**减轻**了本文场景压力），但**不改变**源文档的任何立场或优先级。