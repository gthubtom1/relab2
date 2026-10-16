---
name: browser-automation
description: 浏览器/桌面 GUI 自动化：Playwright/agent-browser 点击/填表/截图/登录；OpenReverse 操作 Windows GUI。用于：填表、爬页面、登录截图、提交 payload。
---

# 自动化操作 (Desktop & Browser Automation)

## ACTION REQUIRED（读完后立刻执行）

1. `NOW`: **查经验卡** —— `python skills/scripts/experience-card.py search "<你看到的症状>"`。
   命中就读那张卡的 `invariant` + `decision.action`，并**逐条对照** `scope.appliesWhen`
   与 `scope.stopsWhen`：少一条前提就停用；命中任一停止条件就停。
   历史卡**不替代**当前目标的实测证据。详见 `../experience-cards/INDEX.md`。
2. `NOW`：确认当前任务是否命中本 skill 的适用范围
3. `NOW`：读取 `../TOOLS.md`，校验工具可用性和实际路径
4. `NEXT`：缺工具时调用 bootstrap，不要猜路径
5. `ACT`：按本卡的「工作流」挑**当下适用**的那一条动手；不要停在确认状态

## 适用范围

当任务属于以下场景时使用本 skill：

### 浏览器场景（Playwright / agent-browser）
- 打开网页并操作页面元素（点击、填表、提交）
- 爬取页面内容或截图
- 自动化登录流程
- 渗透测试中与 Web 页面交互（提交 payload、触发 XSS）
- 验证码页面的自动化处理
- 批量表单提交

### 桌面应用场景（OpenReverse）
- 操作 Windows 桌面应用（IDA Pro、x64dbg、Wireshark 等）
- 需要视觉驱动交互（CUA 模式）
- 需要结构化 UI 操作（UIA 模式）
- 桌面应用的网络流量观察（内置 mitmproxy）
- 自动化逆向工具的 GUI 操作
- 黑盒测试桌面软件

### 与其他工具的分工

| 场景 | 用什么 |
|------|--------|
| 操作网页（浏览器内） | **Playwright / agent-browser** |
| 操作桌面应用（Windows GUI） | **OpenReverse** |
| 抓包分析、HTTP 请求捕获 | anything-analyzer 或 OpenReverse network lane |
| JS 断点、Hook、CDP 调试 | jshookmcp |
| 定位签名算法、补环境复现 | js-reverse |

简单判断：
- 目标是网页 → Playwright
- 目标是 Windows 桌面应用 → OpenReverse
- 两者都需要 → 组合使用

---

## Part 1: 浏览器自动化（Playwright / agent-browser）

### 核心工作流

```bash
# 1. 打开页面
agent-browser open <url>

# 2. 获取可交互元素（返回 @e1, @e2... 引用）
agent-browser snapshot -i

# 3. 用引用操作元素
agent-browser click @e1
agent-browser fill @e2 "text"

# 4. 完成后关闭
agent-browser close
```

### 命令参考

> 下面的 30 行是高频子集；**完整命令速查（导航/快照/交互/信息获取/等待策略/渗透常用模式 + 桌面 CUA 面）**见 `references/playwright-cheatsheet.md`。

```bash
# 导航
agent-browser open <url>
agent-browser close

# 页面快照
agent-browser snapshot        # 完整无障碍树
agent-browser snapshot -i     # 仅可交互元素（推荐）

# 交互操作
agent-browser click @e1
agent-browser fill @e2 "text"
agent-browser type @e2 "text"
agent-browser press Enter
agent-browser scroll down 500

# 获取信息
agent-browser get text @e1
agent-browser get title
agent-browser get url

# 等待
agent-browser wait @e1
agent-browser wait 2000
agent-browser wait --load networkidle
```

### 注意事项
- 必须执行 `agent-browser close`，否则进程泄漏
- 操作前先 snapshot，不要猜元素引用
- 提交表单后用 `wait --load networkidle` 等页面稳定

---

## Part 2: 桌面应用自动化（OpenReverse）

### 概述

[OpenReverse](https://github.com/zhexulong/openreverse) 是面向 AI Agent 的桌面交互与证据采集框架，支持：
- **UIA 模式**：Windows UI Automation，结构化桌面控件操作
- **CUA 模式**：视觉驱动交互（Computer Use Agent），适合复杂 GUI
- **网络观察**：内置 mitmproxy 代理 + 本地抓取

### 交互模式选择

| 模式 | 适合场景 | 底层 |
|------|---------|------|
| UIA | 目标应用有标准 Windows 控件（按钮、文本框、列表） | Windows UI Automation API |
| CUA | 目标应用 UI 复杂或非标准控件（IDA 的反汇编视图、自定义渲染界面） | 视觉识别 + 鼠标键盘 |

### 网络观察模式

| 模式 | 适合场景 |
|------|---------|
| Proxy Lane | 目标应用可以配置代理（推荐） |
| Local Lane | 目标应用无法走代理，需要本地抓取 |

### 安装与配置

```bash
# 1. Clone 项目
git clone https://github.com/zhexulong/openreverse.git
cd openreverse

# 2. 安装依赖
npm install

# 3. 接入 Agent 宿主（Claude Code / Codex / Zed）
npm run init:agents -- --target=all /path/to/project

# 4. 安装 CUA runtime（如果需要视觉驱动模式）
npm run install:cua-runtime
npm run doctor:cua-runtime

# 5. 安装网络观察依赖（如果需要抓包）
npm run install:mitmproxy
npm run doctor:network
```

### 常见组合

| 需求 | 配置 |
|------|------|
| 只操作桌面应用 | UIA 或 CUA，不接网络 lane |
| 操作桌面应用 + 抓包 | UIA/CUA + proxy lane |
| 操作桌面应用 + 本地抓取 | UIA/CUA + local lane |

### 逆向场景示例

```text
场景：自动化操作 IDA Pro 进行批量分析

1. 用 OpenReverse CUA 模式打开 IDA Pro
2. 自动加载目标二进制
3. 等待分析完成
4. 通过 UI 操作导出函数列表
5. 同时用 network lane 观察 IDA 的网络行为（如 Lumina 请求）
```

```text
场景：自动化操作 x64dbg 调试

1. 用 OpenReverse UIA 模式启动 x64dbg
2. 加载目标程序
3. 设置断点
4. 运行并观察寄存器/内存变化
5. 截图保存证据
```

---

## 按需自举（On-Demand Bootstrap）

> 缺工具时只生成安装计划，获用户显式批准后才安装；不得自动安装或自动联网（`autoInstall=false`）。

### 自动化能力边界

| 工具 | 批准后可安装 | 安装方式 | 说明 |
|------|-----------|---------|------|
| Playwright | ✓ | npm + npx playwright install | 浏览器自动化引擎 |
| agent-browser CLI | ✓ | npm install -g agent-browser | 浏览器操作 CLI |
| Node.js | ✓ | winget | 前置依赖 |
| OpenReverse | ✗ | 手动 clone + npm install | 实验阶段，依赖较重 |
| mitmproxy | ✗ | 手动安装 | OpenReverse 网络观察依赖 |

### 自举触发

- 浏览器操作缺 Playwright → 生成计划，获批准后 bootstrap
- 桌面操作需要 OpenReverse → 引导用户手动安装（给出完整步骤）

### OpenReverse 手动安装引导

如果 AI 检测到需要桌面应用自动化但 OpenReverse 未安装：

```markdown
⚠️ **需要 OpenReverse 进行桌面应用自动化**

**安装步骤**：
1. `git clone https://github.com/zhexulong/openreverse.git`
2. `cd openreverse && npm install`
3. `npm run init:agents -- --target=all <你的项目路径>`
4. 如需视觉模式：`npm run install:cua-runtime`
5. 如需网络观察：`npm run install:mitmproxy`

**验证**：`npm run doctor:cua-runtime` 和 `npm run doctor:network`
```

---

## 路由上下文

**上游入口**: `SKILL.md`（总控）、`../routing.md`
**适用场景**: 任何需要自动化操作浏览器或桌面应用的任务
**下游出口**:
- 抓到的请求需要分析 → `anything-analyzer` 或 `js-reverse`
- 需要 JS 调试/Hook → `jshookmcp`
- 需要还原签名算法 → `js-reverse`
- 桌面应用是逆向工具 → `ida-reverse/`

**同级关联模块**: `js-reverse`（浏览器操作后可能需要分析 JS）、`ida-reverse`（OpenReverse 可以自动化操作 IDA GUI）

## 任务完成自检（声称完成前 MUST 通过）

- [ ] 我是否执行了工作流中的每一步（而不是只阅读）？
- [ ] 我是否走了**探测层四级递进**（`Resolve-ReverseToolSpec`）定位实际路径（而不是只跑一条 `Get-Command` 查空就报缺工具、也不是拿 `../TOOLS.md` 里的装法当路径猜）？
- [ ] 我是否产出了可复现证据（命令/脚本/截图/报告）？
- [ ] 我是否完成并回写了 RULES 要求的 Checklist 项？

---

## When NOT to use（近邻负例）

- 要做的是还原站点签名/加密算法（不是驱动界面） → 用 `../web-protocol-reverse/SKILL.md`
- 目标没有 UI，只有 API → 用 `../api-security/SKILL.md`
- 要逆向的是扩展代码本身 → 用 `../browser-extension-reverse/SKILL.md`
- 只是取静态 HTML（无登录、无 JS 渲染）→ 用 `curl`/`requests` 直接取；要成体系抓站/复现协议再进 `../web-protocol-reverse/SKILL.md`
- 目标是移动端 App 界面（adb/frida 能看到进程）→ 用 `../mobile-reverse/SKILL.md`
- 前置条件：脚本要能在**干净会话**里重复跑通（依赖手动状态的脚本不算资产）

## When to Pivot

信号与判据见 `../ops/skill-pivot-contract.md`。本技能去向：

| 触发证据 | 换到 |
|---|---|
| `snapshot -i` 里目标控件不在无障碍树（canvas/WebGL/自定义渲染），点击坐标点不准 | 转桌面 CUA 面（本卡 Part 2）或从运行时取状态 `../js-reverse/SKILL.md` |
| 页面能开但请求被 403/412/429 打回，或响应里的 sign/challenge 是 JS 现场算的 | `../web-protocol-reverse/SKILL.md` |
| 同一操作连续 2 次 `wait --load networkidle` 后 DOM 仍在变（轮询/长连接渲染） | 改用元素条件等待（`wait @e1`）；仍抖 → 抓包面 `../web-protocol-reverse/` |
| 驱动页面的是浏览器扩展注入的脚本（页面本体干净） | `../browser-extension-reverse/SKILL.md` |
| 需要的其实是调试协议（CDP 断点 / Hook / 篡改运行时），不是点选填表 | `jshook` 通道（见工具链表）/ `../js-reverse/SKILL.md` |
| 操作对象是 Windows 原生 GUI（IDA/x64dbg/Wireshark）且只能走界面 | 本卡 Part 2（OpenReverse UIA/CUA）；**能走 CLI/MCP 就不要动 GUI** |
| Playwright 冷启动两次都起不来浏览器（缺内核） | 先 `npx playwright install chromium`（一次性）再复跑，不要改脚本绕 |
| `adb devices` / `frida-ps -U` 能看到目标，那是移动端不是浏览器 | `../mobile-reverse/SKILL.md` / `../apk-reverse/SKILL.md` |

## 工具链与通道（真调用口径）

| 能力 | 通道 | 怎么起 |
|---|---|---|
| 浏览器点选/填表/截图/断言 | `agent-browser` CLI（本卡 Part 1）或 `playwright-mcp`（stdio npx） | CLI 直接调；MCP 由宿主按会话拉起，首次 `npx playwright install chromium` |
| DOM/网络/性能/CDP 断点 | `chrome-devtools`（stdio npx） | 宿主拉起；断点场景与 `jshook` 二选一，不要同时挂两个匿名浏览器 |
| Hook / 深度调试 | `jshook`（stdio npx，按 domain 激活） | 宿主拉起 |
| 改包/落流 | `reqable-mcp`（stdio，需 Reqable 桌面端）或 `mitmdump` | 见 `../web-protocol-reverse/references/triage/tool-playbook.md` |
| 本地 HTTP 分析器 | `anything-analyzer`（local-http `http://localhost:23816/mcp`） | 需手动起服务（`pnpm dev`） |
| 桌面 GUI 自动化 | OpenReverse（手动 clone + npm，见下文自举段） | 手动装；先 UIA，控件非标再 CUA |
| **通道目录** | `powershell -NoProfile -ExecutionPolicy Bypass -File skillpack\skills\scripts\mcp-status.ps1` | 三列「谁注册 / 谁在 LISTEN / 怎么起」；**要用某个通道时再看**（不做事前自检） |

**注册 ≠ 在监听**：stdio 型由宿主按会话拉起；HTTP 型冷启是设计不是故障。工具路径唯一入口是探测层
`. C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1` → `Resolve-ReverseToolSpec -Name <id>`；
`Get-Command` 查空 ≠ 缺工具。**动 GUI 前先问一句：有没有 CLI/MCP 孪生？**（GUI 是同步阻塞的，
命令不返回模型就不会有下一个 token。）

## 定义完成

本技能产出算「完成」的**外部可观测**条件（不许写形容词）：

- 脚本落盘 + 可重复运行（同一输入同一结果）
- 关键步骤有截图或 DOM 快照留档
- 失败路径也有记录（哪一步不可自动化、为什么、替代动作是什么）

硬判据：

- 脚本里出现**固定睡眠**（`wait 5000` 一类）→ 最多 `medium`：固定睡眠是 flake 的主要来源，改成元素条件/网络条件等待
- `confirmed` 的门槛是**冷启动算一次**：≥3 次完整跑通里至少一次是干净会话（无残留 cookie/profile）
- 证据要能指出「这一步靠什么稳定下来」（元素 ref、网络 idle、还是显式条件），说不出来就是靠运气

## 输出契约

```
FACT:       <观察，带来源：命令 / 文件:行 / Evidence ID>
HYPOTHESIS: <可测试断言 + confidence: high|medium|low>（状态见 `../ops/binary-model.md`）
QUESTION:   <当前最大不确定点>
NEXT:       <继续 | 换技能 | 停止（附成本判据）>
```

## 置信度词表

词表见 `../ops/confidence-vocabulary.md`。本技能特有判据：

- `confirmed`：流程在干净会话中 ≥3 次完整跑通（含一次冷启动），且无固定睡眠
- `low`：单次跑通，依赖了当时的手动状态；或脚本靠 `wait <ms>` 硬撑
