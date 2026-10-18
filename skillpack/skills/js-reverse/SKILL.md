---
name: js-reverse
description: 前端 JS 逆向：定位签名/加密参数与风控字段、Hook 采样、本地补 Node 环境（js-reverse_*、CDP、jshookmcp）。用于：还原 sign/token、追踪 XHR/Fetch/WebSocket。
---

# MCP 前端 JS 逆向作业规范

## ACTION REQUIRED（读完后立刻执行）

> **手上只有"现象"、不知道该读哪一篇？** 本技能的技术正文有症状索引：先按现象查 [`../field-journal/KB-INDEX.md`](../field-journal/KB-INDEX.md)（现象 → 该读哪一篇技术文档），再读那一篇。**别按目录翻。** **什么时候该回读**（迷茫 / 换完技能 / 文档和本机对不上 …）见 [`../ops/kb-consult-contract.md`](../ops/kb-consult-contract.md) —— 它不是"开局读一次"，是**反复回读**。（来源与改编规则见同目录 `KB-SOURCES.md`）

1. `NOW`: 读 `../field-journal/precedent-reverse.md` —— 本机做过多轮的常规操作清单，直接照做，不要停在犹豫上
2. `NOW`: **查经验卡** —— `python skillpack/skills/scripts/experience-card.py search "<你看到的症状>"`。
   命中就读那张卡的 `invariant` + `decision.action`，并**逐条对照** `scope.appliesWhen`
   与 `scope.stopsWhen`：少一条前提就停用；命中任一停止条件就停。
   历史卡**不替代**当前目标的实测证据。详见 `../experience-cards/INDEX.md`。
3. `NOW`: 确认当前任务是否命中本 skill 的适用范围
5. `NEXT`：**工具定位** —— 先载入探测层 `. <仓根>\skillpack\skills\scripts\lib\Bootstrap.ps1`（**优先用相对路径**：从本卡往上两级 `..\..\skills\scripts\lib\Bootstrap.ps1`；本机 `C:\relab2\...` 只是备选，**别把绝对路径写进新文档**），再 `Resolve-ReverseToolSpec -Name <id>`，按返回的 `Command` 调（完整路径，别依赖 cwd）。**`Get-Command` 返回空 ≠ 本机缺工具**（PATH 快照陷阱，见 `../references/env-selfcheck.md`）；四级探测全部 `Available=False` 才允许报缺。`../TOOLS.md` 是装法说明书，不是路径索引。禁止猜路径。
6. `NEXT`: 缺工具时调用 bootstrap，不要猜路径
7. `ACT`: 按本卡的「工作流」挑**当下适用**的那一条动手；不要停在确认状态

## 适用范围

当任务属于以下场景时优先使用本 skill：

- 定位接口签名、加密参数、风控字段
- 观察页面请求链路与脚本来源
- 在运行时抓取函数入参与返回值
- 追踪某个 XHR/Fetch/WebSocket 的触发点
- 把页面证据带回 Node 做本地复现与补环境

如果目标是二进制、APK、PE、ELF、DLL、SO，请改用 `ida-reverse`、`radare2` 或 `reverse-engineering`。

## 当前环境默认工具映射

本 skill 不假设存在裸工具名，而是默认绑定当前客户端环境里可用的 `js-reverse_*` 工具。

如果当前任务明确提到 `jshookmcp`、`JS hook`、`CDP`、浏览器断点、网络拦截、SourceMap 或 AST 去混淆，也仍然走本 skill；只是把底层 MCP 面切到 `jshookmcp`，而不是把它当成一个新的总入口。

前提条件：`jshookmcp` 不是本地裸命令工具，而是一个要先下载、显式注册并启用的 MCP server。只有在所选客户端（Claude、Codex 等）的 MCP 配置里接入并启用后，相关工具面才真的可调用。

常用映射：

- `list_scripts` -> `js-reverse_list_scripts`
- `get_script_source` -> `js-reverse_get_script_source`
- `search_in_sources` -> `js-reverse_search_in_sources`
- `break_on_xhr` -> `js-reverse_break_on_xhr`
- `evaluate_script` -> `js-reverse_evaluate_script`
- `get_paused_info` -> `js-reverse_get_paused_info`
- `set_breakpoint_on_text` -> `js-reverse_set_breakpoint_on_text`
- `list_network_requests` -> `js-reverse_list_network_requests`
- `get_request_initiator` -> `js-reverse_get_request_initiator`
- `get_websocket_messages` -> `js-reverse_get_websocket_messages`
- `take_screenshot` -> `js-reverse_take_screenshot`
- `new_page` -> `js-reverse_new_page`
- `navigate_page` -> `js-reverse_navigate_page`
- `select_page` -> `js-reverse_select_page`
- `select_frame` -> `js-reverse_select_frame`
- `pause/resume` -> `js-reverse_pause_or_resume`

如果未来工具名前缀变化，先更新本节，不要在执行时临时猜测。

### jshookmcp 的定位

- 角色：`js-reverse` 的增强执行面，不是独立总控
- 适合：浏览器自动化、CDP 调试、JS Hook、网络拦截、SourceMap 重建、AST 辅助理解
- 调用前提：先把 `@jshookmcp/jshook` 下载并注册到 MCP 客户端配置里，然后确保该 server 已启用
- 建议入口：仍然按 `Observe → Capture → Rebuild` 执行，只是在 `Observe/Capture` 阶段优先调用 jshookmcp 的浏览器与 Hook 能力
- 与 anything-analyzer 关系：两者都能做浏览器/网络侧取证；anything-analyzer 更偏抓包与 HTTP 分析，jshookmcp 更偏 JS 运行时、CDP、Hook 和源码理解

## 核心原则

- `Observe-first`
- `Hook-preferred`
- `Breakpoint-last`
- `Rebuild-oriented`
- `Evidence-first`

先页面观察，再最小化采样，再做本地补环境，不要跳过取证直接猜环境。

## 五阶段工作流

### 1. Observe

目标：先确认目标请求、相关脚本、候选函数，不猜环境。

默认动作：

- 用 `js-reverse_new_page` 或 `js-reverse_navigate_page` 打开目标页面
- 用 `js-reverse_list_network_requests` 找目标请求
- 用 `js-reverse_get_request_initiator` 回溯调用来源
- 用 `js-reverse_list_scripts`、`js-reverse_search_in_sources` 缩小脚本范围

必须产出：

- 目标请求 URL 或特征
- initiator 线索
- 可疑脚本 URL
- 初始任务记录

### 2. Capture

目标：对目标请求做最小侵入采样，拿到参数样例、调用顺序、运行时证据。

规则：

- 优先 `js-reverse_break_on_xhr`
- 优先 `js-reverse_evaluate_script` 做轻量运行时观察
- 命中后先看 `js-reverse_get_paused_info`
- 必要时再用 `js-reverse_set_breakpoint_on_text`

### 3. Rebuild

目标：把页面证据整理成本地可迭代的 Node 复现材料。

规则：

- 本地补环境必须以页面观测证据为依据
- 不允许空想式补 `window/document/navigator/crypto/storage`
- 每次只记录一个最小因果补丁决策
- 补环境补到「自研 VMP 风控」量级（瑞数等）时，先读 `references/rs-vmp-env-stub.md`：现成工具
  `rs-reverse`（纯算法，优先）与 `sdenv`（jsdom 补环境）能省掉手写 shim，不要硬啃
- 该章也写明了何时**不该**用这两个（目标是 PE/ELF/APK、自研非瑞数 VMP、普通加密参数）

### 4. Patch

目标：按报错和 first divergence 驱动补环境，直到本地脚本稳定跑出目标参数。

规则：

- 先看缺什么，再补什么
- 一次只做一个最小补丁决策
- 每次补丁后立即复测
- 每次补丁都写入任务记录

### 5. DeepDive

目标：本地跑通后，再做去混淆、控制流还原、业务逻辑提纯。

规则：

- 如果当前任务只是出签名，这一阶段可以降级
- 如果要长期复用算法链路，这一阶段必须做
- Issue #65 混淆旁路（U–AV §4）：JSVMP（AD）→ `E-js-vmp`；CFF+字符串数组（AE）→ `E-js-deobf`；DevTools/debugger 反调试（AF）→ `E-js-anti-debug`。完整触发表见 `../reverse-engineering/references/nonpe-format-cookbook.md`；AST 细节仍用 `references/ast-deobfuscation.md`

## 执行要求

- 所有重要步骤都要写入本地 task artifact
- 如果无法解释为什么调用某个工具，就不要调用
- 优先使用 `js-reverse_*` 或 jshookmcp 的现成 MCP 能力直接取证，不要先写脚本重造能力
- 失败时按 `references/fallbacks.md` 回退
- 输出遵循 `references/output-contract.md`

## 必读引用

- 自动化入口：`references/automation-entry.md`
- 参数默认值：`references/tool-defaults.md`
- 任务输入模板：`references/task-input-template.md`
- MCP 专用任务编排：`references/mcp-task-template.md`
- 任务产物：`references/task-artifacts.md`
- 本地复现：`references/local-rebuild.md`
- 补环境：`references/env-patching.md`
- Node 复现：`references/node-env-rebuild.md`
- 瑞数 VMP / 补环境工具链：`references/rs-vmp-env-stub.md`（`rs-reverse` 纯算法、`sdenv` jsdom 补环境）
- 插桩：`references/instrumentation.md`
- AST 去混淆：`references/ast-deobfuscation.md`
- 非 PE/JS 混淆菜谱 U–AV：`../reverse-engineering/references/nonpe-format-cookbook.md`（AD/AE/AF）
- 回退：`references/fallbacks.md`
- 输出契约：`references/output-contract.md`

---

## 路由上下文

**上游入口**: `SKILL.md`（总控）、`../routing.md`
**上游备选**:
- anything-analyzer MCP（端口 23816）的浏览器工具可作为替代或补充
- jshookmcp 可作为更强的浏览器/CDP/Hook/Network/SourceMap/AST 执行面
- `SKILL.md`（如果目标不是前端 JS）

**下游出口**:
- 需补环境 → `references/env-patching.md`
- 需本地复现 → `references/local-rebuild.md` / `references/node-env-rebuild.md`
- 需去混淆 → `references/ast-deobfuscation.md`
- 补环境撞上自研 VMP 风控 → `references/rs-vmp-env-stub.md`
- 走不通时回退 → `references/fallbacks.md`

**同级关联模块**: anything-analyzer MCP（浏览器自动化和 HTTP 捕获能力可以互补）

---

## 按需自举（On-Demand Bootstrap）

本 skill 依赖的 MCP 能力可通过统一自举系统安装；MCP 客户端注册必须显式选择目标，默认不会写任何客户端全局配置。

### 自动化能力边界

| 能力 | 批准后可注册 | 方式 | 说明 |
|------|-----------|------|------|
| jshookmcp | ✓ | npm-mcp（npx 启动） | 显式选择 Claude / Codex / Both 后注册 |
| anything-analyzer | ✓ | local-http-mcp | 可自动启动服务；客户端注册须显式选择 |
| Node.js | ✓ | winget 安装 | 运行时依赖 |

### 自举方式（计划模板：须先披露副作用并获用户显式批准后才执行）

```powershell
# 安装并注册 jshookmcp；Codex 可替换为 Claude 或 Both
powershell -File "<skill-root>\scripts\bootstrap-reverse.ps1" -Capability @('jshookmcp') -McpHostTarget Codex

# 注册并启动 anything-analyzer
powershell -File "<skill-root>\scripts\bootstrap-reverse.ps1" -Capability @('anything-analyzer') -StartServices -McpHostTarget Codex
```

### 注意事项

- `jshookmcp` 注册后仍需在 AI 客户端中**启用**该 MCP server 才能调用
- 不传 `-McpHostTarget` 时只安装/准备能力并返回 registration-required，不修改 Claude 或 Codex 配置
- `anything-analyzer` 需要 pnpm 和项目源码，bootstrap 经批准后才会 clone 并安装依赖
- 如果 Node.js 未安装，bootstrap 在获批准后才通过 winget 安装 Node.js 22

<br><br>## 任务完成自检（声称完成前 MUST 通过）

- [ ] 我是否执行了工作流中的每一步（而不是只阅读）？
- [ ] 我是否走了**探测层四级递进**（`Resolve-ReverseToolSpec`）定位实际路径（而不是只跑一条 `Get-Command` 查空就报缺工具、也不是拿 `../TOOLS.md` 里的装法当路径猜）？
- [ ] 我是否产出了可复现证据（命令/脚本/截图/报告）？
- [ ] 我是否完成并回写了 RULES 要求的 Checklist 项？

## 改编参考索引（open-reverselab `kb/ctf-website`）

> 下列 reference 改编自 `LING71671/open-reverselab` 的 `kb/ctf-website/`（GPL-3.0）。
> 每篇统一为「适用信号 / 前置 / 步骤 / 判据 / 坑 / 相关」+ 完整技术正文，
> 「前置」含**本机实测**的工具状态表——照抄原库裸命令前先看那张表。
> **能力域**：本文为技术能力说明，按项目 `scope.md` 直接套用。

### `references/web-runtime/` — 浏览器 JS 运行时与 Web Crypto 滥用（2 篇）

- `references/web-runtime/js-runtime.md`
- `references/web-runtime/web-crypto-abuse.md`

### `references/` — 根目录



---

## When NOT to use（近邻负例）

- 目标是 PE/ELF/APK/`.so`/WebAssembly 模块里的签名逻辑（无浏览器页面）→ `../ida-reverse/`、`../radare2/`、`../reverse-engineering/`
- 目标是 APK 内的 JS 桥 / WebView / Flutter/Dart 产物 → `../apk-reverse/`、`../reverse-engineering/languages-platforms.md`
- 任务要的是 **browser-free 可重放采集器**（已定位到变异点、要脱离浏览器复现）→ `../web-protocol-reverse/SKILL.md`（Observe→Capture→Rebuild 之后交棒）
- 目标是自定义二进制协议 / protobuf / PCAP 帧布局 → `../protocol-reverse/SKILL.md`
- 目标是浏览器扩展（crx/xpi、service_worker、manifest 权限）→ `../browser-extension-reverse/SKILL.md`
- 只是要 UI 自动化点选/填报，不要求协议可复现 → `../browser-automation/`
- 补环境撞上自研 VMP 而现成工具不覆盖 → 仍在本 skill，读 `references/rs-vmp-env-stub.md` 的"何时不该用"，不要退回猜环境

## When to Pivot

信号与判据见 `../ops/skill-pivot-contract.md`。本技能去向：

| 触发证据 | 换到 |
|---|---|
| 变异点已定位，需求变成"脱离浏览器稳定重放/采集" | `../web-protocol-reverse/SKILL.md` |
| 签名逻辑不在页面 JS 里（WASM 导出、native、service_worker 之外） | `../ida-reverse/` / `../reverse-engineering/references/assault-entry.md` |
| 目标协议是二进制帧 / protobuf / WebSocket 私有格式的字段还原 | `../protocol-reverse/SKILL.md` |
| 页面由浏览器扩展注入脚本驱动 | `../browser-extension-reverse/SKILL.md` |
| APK WebView 承载同一套签名 | `../apk-reverse/SKILL.md` |
| 服务端 challenge/TDC 需要专用家族工具 | `../web-protocol-reverse/SKILL.md`（次级运行时帮助） |

## 定义完成

本技能产出算"完成"的**外部可观测**条件（不许写形容词）：

- 采集器/复现脚本落盘（如 `js_reverse_cache/tasks/<task-id>/…` 下的 `replay.js` / `main.py`），一条固定命令可重跑
- 在 **HAR 或真实抓包** 的至少 3 条同型请求上复现出与 wire 字节一致的 sign/token（比对脚本也落盘；不一致写"受限 + 具体原因"）
- 每个补环境补丁对应一条页面观测证据（`window/document/navigator/crypto` 的实测值），无空想补丁
- `## 相关` 上游证据齐备：initiator 栈、可疑脚本 URL、断点命中位置各一条可引用记录
- 已交付 Tree 中的三态之一：Observe/Capture/Rebuild 任一阶段产出，而不是"看完源码"的口头结论

## 输出契约

```
FACT:       <观察，带来源（命令 / 文件:行 / Evidence ID）>
HYPOTHESIS: <可测试断言 + confidence: high|medium|low>  （状态见 ../ops/binary-model.md）
QUESTION:   <当前最大不确定点>
NEXT:       <继续 | 换技能 | 停止（附成本判据）>
```

## 置信度词表

词表见 `../ops/confidence-vocabulary.md`。本技能特有判据：

- `confirmed`：本地复现输出与 **wire 实际出站字节**逐字节一致（≥3 条样本），且固定输入助手跑通；或 Hook 采样到同一次调用里参数与返回值自洽
- `low`：仅静态读 JS 推断算法（同名函数/命名像摘要库都不算证据）；或本地跑通但从未与真实请求比对（长度对、值全错的典型假阳性）
