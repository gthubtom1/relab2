---
name: ctf-sandbox
description: CTF/AWD 靶场入口：case-init 门禁 + sidecar orchestrator 选竞赛子技能。用于：打 CTF、AWD、比赛切题、靶场题、pwn 怎么做、环境跑起来。
---

# CTF sandbox entry (sidecar, not a second router)

## ACTION REQUIRED（读完后立刻执行）

1. `NOW`: **查经验卡** —— `python skills/scripts/experience-card.py search "<你看到的症状>"`。
   命中就读那张卡的 `invariant` + `decision.action`，并**逐条对照** `scope.appliesWhen`
   与 `scope.stopsWhen`：少一条前提就停用；命中任一停止条件就停。
   历史卡**不替代**当前目标的实测证据。详见 `../experience-cards/INDEX.md`。
2. `NOW`: 跑 `../scripts/case-init.ps1` 建案；竞赛/靶场用 `-NetworkProfile lab` 或 `offline`。
3. `NOW`: 打开包根下的 `../../CTF-Sandbox-Orchestrator/ctf-sandbox-orchestrator/SKILL.md`，按它的 sandbox 假设继续。
4. `MUST NOT` 把 40+ 个 `competition-*` 子技能写进 `routing.json`。本入口只是一条 PRIMARY 门闩。
5. `ACT`: 由 orchestrator 选一个 downstream `competition-*`。具体题型已明确时（pwn/ROP、APK、IDA）应已由 `routing.json` 更靠前的规则赢下，不要再抢。

## 为什么单独一层

`CTF-Sandbox-Orchestrator/` 是 **GPL 旁路包**，默认按沙箱内部处理。核心路由包仍是 MIT；任务建档见 `../pentest-tools/templates/scope.md`。本 skill 只做关键词入口，不把竞赛树并进核心。

## 入口层：三个入口各管一段

本卡是**入口层**，不是第二张路由卡。三个入口分工不同，别混：

- `scripts/master-route.ps1 -Hint "<用户原话>" -OutDir <临时目录>` —— 点火 + 立案，产出 `route-scope.md`；里面的 PRIMARY 是**入口**，不是路线，候选全集与下一步也在同一份里。
- `scripts/community-route.py --hint "<原话>"` —— 只在 master-route 已选定 wrapper **之后**，收窄该 wrapper 里的改编参考；weak / ambiguous 一律返回 `needs_review`，它**不会**把社区原始技能当作可调用路径返回。
- `scripts/mcp-status.ps1` —— 动手前的通道目录（三列：注册了哪些 / 谁在监听 / 怎么起）。HTTP 型通道平时 `closed` **是设计不是故障**；要用的通道自己起，起完重跑确认 `LISTEN`。

工具路径一律现场探测，不猜：

```powershell
. <仓根>\skillpack\skills\scripts\lib\Bootstrap.ps1
$r = Resolve-ReverseToolSpec -Name pwntools   # 读 $r.Available / $r.Command / $r.Via
```

单条 `Get-Command` 查空 **≠** 本机缺工具 —— 它只是四级探测里的第 2 级（工具整体迁目录后，已运行的进程仍持有旧 PATH 快照）。

## 本技能硬判据（分类与提交的证据阈值）

- **分类必须落在证据上**：`file` / `diec` 的输出、附件后缀、端口 banner、题面给的 libc/so 版本号。**单题 ≥10 分钟**或**同一分类假设两轮尝试都没有新证据** → 回题面重新归类（重读附件类型与 banner），不硬猜。
- **flag 提交连续两次报错** → 先核格式与字节：大小写、`flag{}` / `FLAG{}` 包裹、尾部不可见字符（`xxd | tail -c 32`）、平台是否要求去包裹。两次都错才怀疑解法本身。
- **环境起不来先分层**：`file` 输出 `ELF 64-bit` 而 `uname -m` 是别的架构时，换镜像/换 qemu 参数是正解，改 exploit 是白费。
- **单题 ≥30 分钟没有新证据** → 换技能或换题，别在同一假设上堆时间。
- 每题在 `route-scope.md` 留一行 `换技能：<旧> → <新>，因为 <证据>`；换技能的理由写证据，不写「感觉不对」。

## 工具通道（按识别信号决定起哪个）

| 识别信号 | 主工具 / 通道 | 起法 |
|---|---|---|
| ELF/PE，`diec` 报出编译器或壳，`checksec` 出 NX+PIE | `pwntools` 写 exp，`gdb` 跟崩溃点 | 探测 `Resolve-ReverseToolSpec -Name pwntools` |
| 要还原算法/协议 | `rabin2`、`radare2`（`afl` / `pdf`）、`Ghidra`（`analyzeHeadless` 批处理）、`IDA`（`idat`） | `idapro` 通道 `13337` 按需起；Ghidra 先 `save` 再释放端口 |
| Windows 用户态调试 | `x64dbg` + `x64dbg-mcp`（x64 `9094` / x32 `9095`） | 插件活在调试进程里：进程不在，端口就不在 |
| APK / 移动题 | `jadx`、`apktool` 解包；`frida` / `objection` 动调 | 设备侧链路见 `../mobile-reverse/SKILL.md` |
| Web / API 题 | `curl` 复现原始请求、`ffuf` 爆路径、`sqlmap` 验注入、`nuclei` 扫已知面、`Burp` 改包重放 | 扫描器命中先降级为「待验证」，能还原成一条 `curl` 才算数 |
| 固件 / IoT | `binwalk` 提文件系统，`qemu` 跑起来 | 转 `../firmware-pentest/SKILL.md` |
| 流量包 | `tshark` / `Wireshark`（`--export-objects` 提取对象） | 先把会话表与导出对象捞出来，再谈算法 |
| 口令 / crypto | `hashcat`（先判哈希类型再选模式） | 先确认平台限速，别把时间烧在无谓的爆破上 |

## 任务完成自检（声称完成前 MUST 通过）

- [ ] 我是否先建案（case-init）并定下网络档（lab/offline）？
- [ ] 我是否打开了 sidecar orchestrator，而不是把 40 个子技能当 PRIMARY？
- [ ] 若任务其实是 pwn/APK/IDA，我是否让更具体的 PRIMARY 接手？

## 改编参考索引（open-reverselab `kb/ctf-website`）

> 下列 reference 改编自 `LING71671/open-reverselab` 的 `kb/ctf-website/`（GPL-3.0）。
> 每篇统一为「适用信号 / 前置 / 步骤 / 判据 / 坑 / 相关」+ 完整技术正文，
> 「前置」含**本机实测**的工具状态表——照抄原库裸命令前先看那张表。
> **能力域**：本文为技术能力说明，按项目 `scope.md` 直接套用。

### `references/` — （2 篇）

- `references/index.md`
- `references/attack-network.md`

### `references/checklists/` — Web CTF 检查清单（前 30 分钟、攻击矩阵、Evidence 标准）（4 篇）

- `references/checklists/index.md`
- `references/checklists/attack-matrix.md`
- `references/checklists/evidence.md`
- `references/checklists/web-ctf-first-30-min.md`

### `references/kb-index/` — kb 总索引（1 篇）

- `references/kb-index/index.md`

### `references/payloads/` — Payload 种子库（2 篇）

- `references/payloads/index.md`
- `references/payloads/web-payload-seeds.md`

### `references/paywall/` — Paywall 检测与绕过（内容/头部/规则拦截/DOM-CSS）（5 篇）

- `references/paywall/01-paywall-detection-bypass.md`
- `references/paywall/02-http-header-manipulation.md`
- `references/paywall/03-network-rule-blocking.md`
- `references/paywall/04-content-extraction.md`
- `references/paywall/05-dom-css-manipulation.md`

### `references/workflow/` — 24h 攻防循环编排（1 篇）

- `references/workflow/24h-loop-orchestration.md`


---

## When NOT to use（近邻负例）

- 目标是真实生产系统/真实客户资产 → 用 `../attack-chain/SKILL.md`
- 题目就是单个二进制/单道 pwn，不需要整场调度 → 用 `../pwn-chain/SKILL.md`
- 只做逆向不涉及利用 → 用 `../reverse-engineering/SKILL.md`
- 只是要审一段代码 → 用 `../code-audit/SKILL.md`
- 要交 writeup 或报告 → 用 `../docs-generator/SKILL.md`
- 要审已有 case 包完整性 → 用 `../case-review/SKILL.md`
- 要画解题流程图/攻击路径图 → 用 `../diagram-generator/SKILL.md`
- 前置条件：长期项目走 `../reverse-engineering/references/assault-entry.md`；本卡只管比赛/靶场的**单次编排**

## When to Pivot

信号与判据见 `../ops/skill-pivot-contract.md`。本技能去向：

| 触发证据 | 换到 |
|---|---|
| 附件 `file` **显示** ELF，`checksec` 报 NX+PIE+Canary 全开，题面附 libc | `../pwn-chain/SKILL.md` |
| 二进制要还原算法/协议（`diec` 报出编译器与壳，`rabin2` 字符串里**出现**密钥/URL 线索） | `../reverse-engineering/SKILL.md` |
| 附件是 `.apk`/`.ipa`，或 `jadx` 能出 Java 层代码 | `../mobile-reverse/SKILL.md` |
| 题面/流量里**出现** HTTP 请求与 JSON 字段，`curl` 复现出 401/403 | `../api-security/SKILL.md` |
| `binwalk` 输出里**出现** squashfs / UBI / JFFS2 魔数 | `../firmware-pentest/SKILL.md` |
| 题面给 UART/JTAG 引脚、串口日志或逻辑分析仪波形 | `../hardware-security/SKILL.md` |
| pcap 里**出现**非 HTTP 的二进制协议，且字段长度/魔数对不上现有解析 | `../protocol-reverse/SKILL.md` |
| Web 题卡在混淆 JS 的签名参数上（只有 `frida` 或浏览器断点能采到运行时值） | `../js-reverse/SKILL.md` |
| 单题 **≥10 分钟**或同一分类假设**两轮**没有新证据 | 回题面重新归类（本卡），别硬猜 |
| flag 平台**两次**报错（含换过大小写与包裹格式之后） | 先核字节与格式（本卡判据），再回解法面 |
| 题目环境不在靶场/CTF 平台（出现真实域名或客户资产） | `../attack-chain/SKILL.md` |
| 题解完成，要交 writeup 或出报告 | `../docs-generator/SKILL.md` |

## 定义完成

本技能产出算「完成」的**外部可观测**条件（不许写形容词）：

- flag/预期解 落盘：**原始回显**（含平台接受回执）或本地校验脚本的输出原文，不是二手转述
- 每题在 `route-scope.md` 里有 PRIMARY + 至少一行 `换技能：<旧> → <新>，因为 <证据>`
- 环境指纹落盘（镜像/架构/`uname -m`、依赖版本），跨机器复现时能指出是哪一项对不上
- writeup 落盘（若需要交付），且其中每条结论能指回对应的原始输出

## 输出契约

```
FACT:       <观察，带来源：命令 / 文件:行 / Evidence ID>
HYPOTHESIS: <可测试断言 + confidence: high|medium|low>（状态见 `../ops/binary-model.md`）
QUESTION:   <当前最大不确定点>
NEXT:       <继续 | 换技能 | 停止（附成本判据）>
```

## 置信度词表

词表见 `../ops/confidence-vocabulary.md`。本技能特有判据：

- `confirmed`：flag 已取得并有原始输出证据，且平台**接受了**该 flag（不是本地猜的格式）
- `medium`：解法在本地靶场跑通，但目标环境版本/架构与之不符
- `low`：仅推断出解法但未实际跑通，或题目分类仍有两轮无证据的假设
