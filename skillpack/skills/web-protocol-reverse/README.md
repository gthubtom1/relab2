# Web 协议恢复（Spider King）

> **来源**：改编自 `aoyunyang/spider-king-skill`（MIT License，https://github.com/aoyunyang/spider-king-skill）的 `README.md`。保留原仓库 MIT 版权声明；本 README 为中文改写，并按本技能包（`C:\relab2\skillpack`）的落地情况做了**实情校正**。
> **什么时候用**：把「看起来只能靠浏览器跑」的 Web 目标，还原成可复现、可维护的协议链路或采集器时，先读本 README 建立预期，再进 `SKILL.md`。

---

## 目录

- [一句话定位](#一句话定位)
- [与本包既有技能的分工](#与本包既有技能的分工)
- [本机工具链实测状态](#本机工具链实测状态)
- [本次落地缺了什么](#本次落地缺了什么)
- [核心交付原则](#核心交付原则)
- [方法论主线](#方法论主线)
- [目录结构](#目录结构)
- [阅读顺序](#阅读顺序)
- [适用与不适用](#适用与不适用)
- [交付标准](#交付标准)
- [常见坑](#常见坑)
- [许可](#许可)

---

## 一句话定位

> 它是一套把 hostile web client（带敌意的 Web 客户端）还原成 stable protocol collector（稳定协议采集器）的方法论与执行框架。

它解决的不是"如何自动点击页面"，而是下面这类协议恢复问题：

- 页面代码调的是 A 接口，真实网络请求走的是 B 接口；
- 业务层构造了 `sign` / `token` / `m`，发包前又被 transport wrapper（传输包装层）重写；
- 请求发得出，但响应还要解码：解密、二进制 envelope（信封）、字形映射（glyph mapping）、JSONP 拆包、protobuf 解析；
- 页面能开，但重放不稳：`403` / `412` / `429`、偶发成功、只成功第一页、只在某条路由成功；
- Cookie、challenge（挑战）脚本、WASM、WebSocket 会话、协议包裹、响应侧解码缠在一起，"只找 sign"根本解决不了；
- 看起来是浏览器专属逻辑，实际可以在本地运行时、局部助手或纯 Python 里恢复关键状态。

## 与本包既有技能的分工

这是本技能在本包里最需要说清楚的一件事。**web-protocol-reverse 是"交付形态"技能，不是"工具"技能。**

| 你的问题 | 去哪 | 理由 |
|---|---|---|
| 「这个 sign 函数在哪？调了谁？initiator 是谁？」 | `../js-reverse/` | js-reverse 的能力面是浏览器/CDP/Hook/源码定位，产物是**调用链知识** |
| 「这个 WebSocket 私有帧的布局是什么？」 | `../protocol-reverse/` | 产物是**帧布局与消息字典**，不关心它是不是 web |
| 「最终交付必须是一个脱浏览器的采集器 / 协议重放」 | **本 skill** | 产物是**可运行链路**，含 browser-free 判据与交付门禁 |
| 「目标其实是 APK / 原生 App / 小程序」 | `../apk-reverse/`、`../mobile-reverse/`、`../reverse-engineering/` | 本 skill 明确 out-of-scope |
| 「目标其实是 PE / ELF / SO」 | `../ida-reverse/`、`../reverse-engineering/` | 同上 |
| 「需求本质是 UI 自动化，不要求协议可复现」 | `../browser-automation/` | 本 skill 会拒绝这种交付形态 |

**关键关系是流水线，不是二选一**：

```text
js-reverse  (定位：函数在哪、怎么调的)
     ↓ 产出入口契约 + 固定样本
web-protocol-reverse  (恢复：这条协议链怎么脱离浏览器复现）
     ↓ 需要帧布局时
protocol-reverse  (帧层：布局、状态机、序列化）
```

本 skill 的 `debugger-trace` 阶段默认就交给 `js-reverse` 的工具面，`SKILL.md` 的「不走本 skill」一节明确写了：js-reverse 回答"这段 JS 在哪、怎么调的"，本 skill 回答"这条协议链怎么脱离浏览器复现"。

> ★★ **本机 playwright 必须显式指定浏览器**（2026-10-10 实测）：
> `launch()` 默认启动会报 `Executable doesn't exist at %LOCALAPPDATA%\ms-playwright\chromium_headless_shell-1234\...`
> —— python 包期望 1234，本机装的是 **1243**，版本号对不上。
> **可用写法**：`p.chromium.launch(channel="msedge")`（实测能起、能渲染、能读 DOM），
> 或 `launch(executable_path=<显式路径>)`。照抄裸 `launch()` 一定失败。
> 
| **Reqable** | ❌ **本机无** | 用 tshark / mitmproxy 替代 |
| **iv8** | ❌ **本机无** | 社区运行时，PyPI 上不存在；相关 API 形态仅供有该运行时时参考，未在本机验证 |
| **esprima / acorn / @babel/parser** | ❌ **本机未安装** | Node 可用，但这些 npm 包要先 `npm i`；`profiles/static-ast/` 那套需先装依赖 |
| 技能自带 `scripts/` | ❌ **本次未落地** | 见下一节 |

**用得上的替代方案**：上游文档默认用 Reqable / HAR 做被动抓包存储，本机没有。取 wire 证据用：

```powershell
# 抓包后按字段切片（本机实测可执行）
& (Resolve-ReverseToolSpec -Name 'tshark').Command -r cap.pcapng -T fields -e frame.number -e http.request.method -e http.host -e http.request.uri

# 需要改写/重放中间层时用 mitmproxy（本机实测可执行）
& (Resolve-ReverseToolSpec -Name 'mitmdump').Command --listen-port 8080 --set block_global=false
```

HAR 导出仍可用浏览器 DevTools 完成。本文不写 Reqable 的具体操作步骤（未在本机验证）。

## 本次落地缺了什么

这是改编时必须先讲清的实情，避免后续 agent 照抄上游命令后一头撞墙：

1. **`scripts/` 整个目录未落地**。上游 `SKILL.md` / `README.md` 里提到的 `check_reverse_env.py`、`protocol_diff.py`、`scaffold_reverse_project.py`、`evidence_normalizer.py`、`transcript_diff.py`、`transform_trace_diff.py`、`transport_profile_diff.py`、`crypto_fingerprint.py`、`forward_test_report.py`、`practice_lab.py`、`validate_skill.py`，**在本包里一个都没有**。需要时从上游 MIT 仓库取，或自行实现。
2. **三套 profile 的 `scripts/` 与 `tests/` 未落地**。`profiles/browser-hook-snippets/`、`profiles/static-ast/`、`profiles/env-patch/` 在本包里**只有 Markdown 文档**，没有 `.js`、没有 `package.json`、没有 `node_modules`。文档里出现的 `../scripts/xhr_fetch.js`、`scripts/env-diagnose.js`、`npm test --prefix ...` 等命令**当前跑不了**。
3. **`package-lock.json` 未落地**，所以 `profiles/static-ast/index.md` 的 `npm ci` 流程需要自己重新定依赖版本。
4. **MCP 家族差异**。上游默认依赖 `chrome-devtools` 与 Camoufox 作为基线主机。本机已挂载的 MCP 是 `pyghidra-mcp`、`idapro`、`ida-pro-mcp`、`angr-mcp`、`x64dbg-automate-mcp`，**不含浏览器类 MCP**。所以"默认 live 顺序 = chrome-devtools → js-reverse"这条在本机需要重新用 `js-reverse` 那一侧或本包工具链替代，且要先确认可用性。
> （★ 本机无 chrome-devtools / Camoufox MCP —— 见 SKILL.md「来源声明」实测记录；本机基线主机是 `playwright` 的 `launch(channel="msedge")`）
5. **`LICENSE` 文件未随本次落地复制到本目录**，但 MIT 许可事实以本文与 `SKILL.md` 顶部的来源声明为准（见文末「许可」）。

## 核心交付原则

- 先证据（evidence），后结论
- 必须纯协议交付，浏览器只能用于侦察、不能成为最终依赖
- 先恢复真实动态状态，再谈分页、并发和规模化
- 最终 collector（采集器）优先 Python，仅在必要时保留极小 JS / WASM / 本地 bootstrap 助手

## 方法论主线

最短主线五步：

```text
1. Auto Judge + Startup Gate（先判，再开工具）
2. 按 intake（入口判定）选最小路径；live-target 先基线后调试
3. 找到真实请求与真实动态状态
4. 在本地离线重建这些动态状态
5. 交付脱离浏览器运行的 Python collector
```

### 1. Startup Gate（启动门禁）

四步，每步都要在报告里显式写出来：

- 声明 intake 模式：`live-target` / `artifact-only` / `continuation`
- 快照环境与**当前会话真正挂载**的 MCP
- 打家族标签：`signer-gated` / `verifier-gated` / `decode-gated` / `session-gated`，必要时补 `transport-gated`
- 声明最终交付形态：`evidence` / `local-proof` / `compact-replay` / `collector`

### 2. 轻量双角色侦察（fresh `live-target`）

- `fingerprint-baseline`（★ 本机 = `playwright` 的 `launch(channel="msedge")`；上游默认的 `chrome-devtools` 本机不存在）：页面状态、跳转链、首轮网络视图
- `debugger-trace`（★ 本机 = `playwright` CDP / `frida`；上游默认的 `js-reverse` server 本机未注册）：initiator、源码搜索、wrapper 与 mutation（变异）假设

强调：轻量优先、串行保护易失状态、已有 HAR/抓包/固定向量时优先 `artifact-only`、**不默认上 Camoufox**。详见 `references/triage/startup-triage-playbook.md`。

### 3. 识别真实动态状态

> 真正变化的东西，不一定叫 `sign`。

可能是：旋转 Cookie、页面专属 header、wrapper 字段、服务端引导 JS、动态字体、WASM 导出、响应侧解码链、会话绑定状态、业务上下文激活结果、challenge artifact、transport envelope / 二进制帧状态。

### 4. 离线重建优先级

```text
1. 纯 Python
2. Python + 极小 JS 助手
3. Python + 极小 WASM 助手
4. Python + 本地 embedded runtime / bootstrap executor
5. 继续逆向 —— 而不是退回浏览器自动化
```

### 5. 重复性验证

- 同样逻辑稳定成功 2~3 次
- 分页 / cursor 正确推进
- 关键动态状态可再生
- 固定输入输出可验证
- 最终路径不依赖浏览器自动化

**哪些不算接受**：非空签名、token 长度合理、助手加载成功、一次 HTTP `200`、一个当前 cookie jar、一份过期的浏览器导出。详见 `references/deliver/delivery-gate-playbook.md`。

## 目录结构

本包内实际结构（与上游不同之处已标注）：

```text
web-protocol-reverse/
├── README.md                  ← 本文
├── SKILL.md                   ← 主入口，六段式规范
├── LICENSE                    ← 上游 LICENSE 未随本次落地复制
├── agents/openai.yaml         ← 上游，未落地
├── scripts/*.py|*.js          ← 上游 13 个脚本，未落地
├── tests/                     ← 上游测试，未落地
├── profiles/                  ← ✅ 本次已落地（仅 Markdown）
│   ├── browser-hook-snippets/  ← index.md + references/ × 7
│   ├── static-ast/            ← index.md（依赖 npm 解析器，本机未装）
│   └── env-patch/             ← index.md + references/ × 12
└── references/                ← ✅ 本次已落地（按主题分子目录）
    ├── principles/            ← doctrine-index / workflow-overview / anti-patterns
    ├── triage/                ← startup / tool / escalation / verifier / forward-testing …
    ├── observe/               ← mcp-routing / hook-techniques / transport-wrapper …
    ├── crypto/                ← crypto-patterns / obfuscation / jsvmp / iv8-cheatsheet …
    ├── state/                 ← cookie / session / bootstrap / async-export …
    ├── deliver/               ← delivery-gate / pure-python-rebuild / response-decode …
    ├── contract/              ← report-templates / project-artifact-contract / …
    └── examples/douyin-bdms-pure/
```

> 上游 `references/` 是**扁平**的 60+ 个文件；本包按主题拆成 7 个子目录，**引用路径已全部改写**，见 `SKILL.md` 的「参考路由」。

## 阅读顺序

第一次按这个顺序读：

1. `SKILL.md` — 主入口，先读 ACTION REQUIRED 与 Auto Judge Card
2. `references/triage/startup-triage-playbook.md` — Startup Gate 展开清单
3. `references/principles/workflow-overview.md` — 短执行地图
4. `references/principles/doctrine-index.md` — 26 条教条（改写版）
5. `references/observe/mcp-routing-playbook.md` — MCP 家族选择与 auto-judge

按场景跳转：

| 场景 | 文档 |
|---|---|
| 已知边界贴 Hook | `profiles/browser-hook-snippets/index.md` |
| 结构化还原 JS（需先 `npm i`） | `profiles/static-ast/index.md` |
| 本地补环境 | `profiles/env-patch/index.md` |
| 固定轨迹纯 Python 重写 | `references/deliver/pure-python-rebuild-playbook.md` |
| 不透明多阶段签名 | `references/crypto/opaque-runtime-profile-playbook.md` |
| 传输准入 | `references/observe/transport-pre-gate-playbook.md` |
| 前向验证 | `references/triage/forward-testing-playbook.md` |
| 伪完成排查 | `references/principles/anti-patterns-playbook.md` |
| 技能维护 | `references/contract/skill-maintenance.md` |

## 适用场景

- 需要恢复参数、协议包裹、响应解码或状态流
- 目标存在 challenge、bootstrap、动态 Cookie、WebSocket、GraphQL、protobuf、WASM 或环境绑定逻辑
- 最终目标是可复现、可长期维护的协议采集器
- 已有 HAR / 抓包 / 固定向量，只想做 artifact-only 本地证明
- 已知边界，需要 Hook / static-ast / env-patch / pure rebuild

## 不适用场景

- 需求本质只是标准 UI 自动化
- 只要求一次性浏览器脚本，不关心协议可复现性
- 最终交付允许长期依赖浏览器 profile 或人工点击
- 主目标是 APK / 原生 App / 小程序
- 无 `scope.md` 边界记录

## 交付标准

理想产物：

- 真实接口路径说明
- 动态状态分类结论
- 关键证据与固定样本
- Python collector
- 必要时的极小 JS / WASM / runtime 助手
- Cookie / session / challenge artifact 的来源说明
- 风险与不稳定点说明
- right-click 可运行入口（`main.py` 或等价路径）

合格底线：

- 不依赖浏览器自动化
- 不依赖手工页面操作
- 重放逻辑可重复成功
- 动态状态可解释、可验证、可再生
- browser-free / runtime-free 边界说清楚
- 敏感值未进入公开日志或版本控制

## 常见坑

完整反例见 `references/principles/anti-patterns-playbook.md`。最常见的几条：

1. **先开浏览器再编理由** —— Auto Judge 是硬门，不是仪式。
2. **硬编码"这次能用"的旋转 cookie/token** —— 跑通一次后全线 `403`。
3. **一次侥幸成功就上规模** —— 分页第 3 页开始返回空。
4. **跨级升级运行时** —— 因为当前这格烦人就直接扔进浏览器，先记盲点再一格一格爬。
5. **逆向可见的 helper，而不是 wire 变异点** —— 本地算得出，服务端不认。
6. **因为算法名字匹配就信标准摘要库** —— 固定输入先验证。
7. **把"助手加载成功"当协议成功** —— 只有服务端接受才算。
8. **照抄上游命令** —— 本包缺 `scripts/`，详见「本次落地缺了什么」。

## 许可

本技能包内的文档改编自 [`aoyunyang/spider-king-skill`](https://github.com/aoyunyang/spider-king-skill)，遵循 **MIT License**，版权归原作者所有。本地改编（中文翻译、六段式重构、本机工具链校正、交叉引用改写）同样以 MIT 许可分发。