---
name: docs-generator
description: 把逆向/渗透/CTF 结论写成技术文档并落盘（渗透测试报告、CTF writeup、README、API 文档）。用于：帮我写份渗透测试报告、出个 writeup、补个 README。
---

# Technical Documentation

## ACTION REQUIRED（读完后立刻执行）

1. `NOW`: **查经验卡** —— `python skillpack/skills/scripts/experience-card.py search "<你看到的症状>"`。
   命中就读那张卡的 `invariant` + `decision.action`，并**逐条对照** `scope.appliesWhen`
   与 `scope.stopsWhen`：少一条前提就停用；命中任一停止条件就停。
   历史卡**不替代**当前目标的实测证据。详见 `../experience-cards/INDEX.md`。
2. `NOW`：确认当前任务是否命中本 skill 的适用范围
3. `NOW`：读取 `../TOOLS.md`，校验工具可用性和实际路径
4. `NEXT`：缺工具时调用 bootstrap，不要猜路径
5. `ACT`：按本卡的「工作流」挑**当下适用**的那一条动手；不要停在确认状态

For writing style, tone, and voice guidance, follow the in-repo rules in `references/vendor-report-rules.md` and the templates in `references/security-report-templates.md`.

## 安全/逆向任务文档输出

当逆向/渗透/CTF/安全分析任务完成后，本 skill 负责在**用户项目目录**生成正式技术文档。

### 触发时机

1. 逆向任务完成，已产出核心结论（算法还原、签名破解、绕过方案等）
2. 渗透测试完成，已发现并验证漏洞
3. CTF 题目解出，已拿到 flag
4. 用户明确要求"写一份报告/文档/writeup"

### 模板选择

| 任务类型 | 使用模板 |
|---------|---------|
| APK/二进制/so 逆向 | `references/security-report-templates.md` → 逆向工程报告 |
| 渗透测试/漏洞挖掘 | `references/security-report-templates.md` → 渗透测试报告 |
| CTF 解题 | `references/security-report-templates.md` → CTF Writeup |
| JS/Web 签名逆向 | `references/security-report-templates.md` → 签名逆向报告 |
| 恶意软件 / APT / 病毒分析报告 | `references/security-report-templates.md` + **`references/vendor-report-rules.md`** |
| 通用技术文档 | `references/templates.md` → README / API 文档 |

### 厂商报告结构（Issue #65）

安全类正式报告 **MUST** 读取 `references/vendor-report-rules.md`（只取结构，不抄厂商原文）。仅在任务证据或用户明确要求时选择厂商 flavor；普通逆向和其他任务使用 `flavor = null`。

| Flavor / Overlay | 何时用 | 主参考骨架 |
|------------------|--------|------------|
| `malware` | 明确恶意样本、木马、白加黑、钓鱼投毒 | 火绒式：概述→流程→样本分析→应急处置→IOC |
| `apt` | APT/战役/团伙/多阶段感染链/行业定向 | 卡巴斯基 Securelist 式：摘要→感染链→调查叙事→Interesting findings→技术分析→检测缓解→IOC |
| `flavor = null` | 普通 APK/ELF/PE/Mach-O 逆向、算法/固件分析、渗透 / CTF / JS 签名 | 原任务模板 + Base 通用元素；不套 malware/APT 专属章节 |
| thin `vuln` | 用户明确要求漏洞/补丁/CVE 技术分析 | 概述→影响/复现→崩溃与补丁分析→防护建议（叠加在 null 上，非第 3 默认全文 flavor） |

原则：**模板在精不在多** —— 仅 2 个厂商全文 flavor；`vuln` 仅为可选 thin overlay，不另建第三套默认全文模板。
与 §0 Evidence→Finding→Path **同时生效**；冲突时 Evidence 契约优先。

### 输出规范

- **输出位置**：用户当前项目目录（不是 skill 包目录）
- **文件名格式**：`YYYY-MM-DD_[类型]-[目标简称]-report.md`
- **如果项目有 `docs/` 目录**：优先放在 `docs/` 下
- **编码**：UTF-8
- **语言**：跟随用户对话语言（中文对话出中文报告，英文对话出英文报告）

### 质量要求

- 所有代码块必须可直接运行或有明确上下文
- 不要有 placeholder/TODO
- 关键发现必须有证据支撑
- 复现步骤必须让第三方能独立重现
- 敏感信息（真实 token、密码、内部 URL）用占位符替代
- **MUST** 包含 Evidence → Finding → Path 链（见 `../ops/evidence-finding-path.md` 与模板 §0）
- **MUST** 读取 `references/vendor-report-rules.md`：选定 `malware` / `apt` 或 `flavor = null`（漏洞任务可叠加 thin `vuln`）；无 flavor 时只输出原任务模板和适用的 Base 元素，不强制 IOC/ATT&CK
- **SHOULD** 引用 case `../pentest-tools/templates/scope.md` / `../../examples/ctf-demo/timeline.md`（`../scripts/case-init.ps1`）

### 图表集成

生成报告时，应在适当位置调用 `diagram-generator` skill 生成可视化图表：

| 报告类型 | 建议图表 | 图表类型 |
|---------|---------|---------|
| 逆向工程报告 | 函数调用关系图、数据流图 | Mermaid flowchart / sequenceDiagram |
| 渗透测试报告 | 攻击路径图、网络拓扑图 | Mermaid flowchart / Graphviz |
| CTF Writeup | 解题思路流程图 | Mermaid flowchart |
| JS 签名逆向报告 | 请求链路时序图、算法流程图 | Mermaid sequenceDiagram / flowchart |

图表以 Mermaid 代码块形式嵌入报告 markdown 中，确保可在 GitHub/GitLab 直接渲染。

## 本技能硬判据（报告可交的阈值）

- **每条技术结论必须挂在 Evidence 上**：能指到 case 里的 E-ID 或命令原文才算数。指不到 → 退回 `observed` / `unknown`，并写清**缺的是什么**（缺哪台机器的回显、哪份样本、哪个版本号），不许留在结论句里当事实。
- **产生证据的工具必须点名**：报告里每张图、每个关键结论都要写清由哪个工具产出（见下表工具列）。工具名要能被探测层解析到；解析不到就写实际用的替代工具与版本，而不是笼统写「用某工具分析」。
- **模板 flavor 与素材必须对得上**：素材里有样本行为/IOC 才用 `malware`，有团伙与多阶段链才用 `apt`，否则 `flavor = null`。对不上的典型症状是报告里**出现空的 IOC 表、空的 ATT&CK 映射**——这时换模板，不硬套。
- **链接与引用**：仓库内相对路径跑 `verify-doc-links.py`（断链必须为 0）；外部 URL 用 `curl -sI` 看状态码，4xx/5xx 不许留在「参考」里。
- **数字要能回溯**：Executive Summary 里每个数字都要能在 Findings 里找到来源行；找不到的数字删掉或改写。
- **交接前**：`review_case.py --verify-hashes --strict` error = 0，报告才叫可交。

## 工具链与工具联动

| 环节 | 本机怎么调 | 输出接到哪 |
|---|---|---|
| 模板与 flavor | `references/security-report-templates.md` 按任务类型选；`references/vendor-report-rules.md` 定 `malware` / `apt` / `flavor = null` | flavor 与素材对不上 → 换模板，见上节第三条 |
| 证据链 | `../ops/evidence-finding-path.md` 的 Evidence → Finding → Path 契约 | 每条结论挂 E-ID；挂不上的退回 `unknown` |
| 交接前审查 | `python skillpack\skills\case-review\scripts\review_case.py <case> --verify-hashes --strict` | error 计数必须为 0 |
| 工具点名 | 逆向类 `Ghidra` / `IDA` / `radare2` / `rabin2` / `diec`；移动类 `jadx` / `apktool` / `frida`；固件类 `binwalk`；网络类 `nmap` / `nuclei` / `sqlmap` / `curl` / `Burp`；流量类 `tshark` / `Wireshark`；样本类 `yara`；口令类 `hashcat` | 报告里写清哪段结论/哪张图由哪个工具产出 |
| 链接与引用 | `python skillpack\skills\scripts\verify-doc-links.py`；外部 URL 用 `curl -sI` 看状态码 | 断链或 4xx/5xx → 修或删，不留死链 |
| 图表渲染 | 图源先本地渲一次再嵌：Mermaid 走 `mmdc`，DOT 走 `dot -Tsvg`（`../diagram-generator/scripts/render_diagram.py` 会按扩展名分派） | 没渲过的图源不许贴进交付文档；渲染器探测不到就只交图源并写明 |
| 路径探测 / 通道 | `. <仓根>\skillpack\skills\scripts\lib\Bootstrap.ps1` → `Resolve-ReverseToolSpec -Name mmdc`；通道状态 `powershell -NoProfile -ExecutionPolicy Bypass -File skillpack\skills\scripts\mcp-status.ps1` | `Get-Command` 查空 ≠ 缺工具（四级探测第 2 级而已） |

---

## Core Principles

### 1. Progressive Disclosure

Reveal information in layers:

| Layer | Content | User Question |
|-------|---------|---------------|
| 1 | One-sentence description | What is it? |
| 2 | Quick start code block | How do I use it? |
| 3 | Full API reference | What are my options? |
| 4 | Architecture deep dive | How does it work? |

**Warnings, breaking changes, and prerequisites go at the TOP.**

### 2. Task-Oriented Writing

```markdown
<!-- Bad: Feature-oriented -->
## AuthService Class
The AuthService class provides authentication methods...

<!-- Good: Task-oriented -->
## Authenticating Users
To authenticate a user, call login() with credentials:
```

### 3. Show, Don't Tell

Every concept needs a concrete example.

## Formatting Standards

- **Sentence case headings**: "Getting started" not "Getting Started"
- **Max 3 heading levels**: Deeper means split the doc
- **Always specify language** in code blocks
- **Relative paths** for internal links
- **Tables** for structured data with 3+ attributes

## Quality Checklist

- [ ] Code examples tested and runnable
- [ ] No placeholder text or TODOs
- [ ] Matches actual code behavior
- [ ] Scannable without reading everything
- [ ] Reader knows what to do next

## Anti-Patterns

| Problem | Fix |
|---------|-----|
| Wall of text | Break up with headings, bullets, code, tables |
| Buried critical info | Warnings/breaking changes at TOP |
| Missing error docs | Always document what can go wrong |

## Templates

For README, API endpoint, and file organization templates, see [references/templates.md](references/templates.md).

## Related Skills

- `references/vendor-report-rules.md` - Writing style, tone, and voice rules
- `../diagram-generator/` - Architecture and flow diagrams (Mermaid)

---

## 按需自举（On-Demand Bootstrap）

本 skill 不依赖外部工具，纯文本生成。无需 bootstrap。

如果需要渲染图表嵌入报告，会调用 `diagram-generator/` skill。

---

## 路由上下文

**上游入口**: 所有安全/逆向 skill 在任务完成后自动调用本 skill
**触发方式**:
- 自动：任务完成后作为行为链第 9 步执行
- 手动：用户说"写报告"、"出文档"、"writeup"

**同级关联模块**:
- `apk-reverse/` — APK 逆向完成后生成逆向报告
- `ida-reverse/` — 二进制分析完成后生成逆向报告
- `radare2/` — CLI 分析完成后生成逆向报告
- `js-reverse/` — JS 签名逆向完成后生成签名报告
- `reverse-engineering/` — 通用逆向完成后生成逆向报告
- `field-journal/` — 报告内容同时作为进化日志的数据来源

**安全报告模板**: `references/security-report-templates.md`
**厂商报告规则**: `references/vendor-report-rules.md`（flavor: malware | apt | null；optional overlay: vuln）
**通用文档模板**: `references/templates.md`

## 任务完成自检（声称完成前 MUST 通过）

- [ ] 我是否执行了工作流中的每一步（而不是只阅读）？
- [ ] 我是否走了**探测层四级递进**（`Resolve-ReverseToolSpec`）定位实际路径（而不是只跑一条 `Get-Command` 查空就报缺工具、也不是拿 `../TOOLS.md` 里的装法当路径猜）？
- [ ] 我是否产出了可复现证据（命令/脚本/截图/报告）？
- [ ] 报告是否含 Evidence / Finding / Path（ops 契约）？
- [ ] 是否完成并回写了 RULES 要求的 Checklist 项？

---

## When NOT to use（近邻负例）

- 要画的是图不是文 → 用 `../diagram-generator/SKILL.md`
- 要审 case 完整性而不是写文档 → 用 `../case-review/SKILL.md`
- 技术证据还没采到（case 里没有 Evidence）就想要报告 → 用 `../ops/evidence-finding-path.md`
- 要的是执行而不是文档（打靶、利用编排、漏洞验证） → 用 `../pentest-tools/SKILL.md`
- 要出的是 changelog / 提交说明，不是安全报告 → 用 `../docs-changelog/SKILL.md`
- 要写的是代码里的注释或代码本身 → 用 `../code-audit/SKILL.md`
- 前置条件：报告里的技术结论必须来自 case 的 Evidence，不许自创

## When to Pivot

信号与判据见 `../ops/skill-pivot-contract.md`。本技能去向：

| 触发证据 | 换到 |
|---|---|
| 报告里要插图（调用关系、攻击路径、请求时序），图还没有 | `../diagram-generator/SKILL.md` |
| 要交出去之前，`review_case.py --strict` 报 **≥1 条** error | `../case-review/SKILL.md` |
| 有结论指不到 Evidence（哪怕只有 **1 条**） | `../ops/evidence-finding-path.md` |
| 模板 flavor 与素材对不上（没有样本行为却套 `malware`，IOC 表只能填占位） | 换模板：`references/security-report-templates.md` + `references/vendor-report-rules.md`；不硬套 |
| 素材是抓包/内存/磁盘镜像，报告要写复现命令 | `../digital-forensics/SKILL.md` |
| 报告要覆盖的攻击链超出 case 已证实范围 | `../case-review/SKILL.md`（先判缺口，再决定补证据还是缩叙述） |
| 目标平台是 APK / iOS，报告要补技术证据 | `../mobile-reverse/SKILL.md` |
| 报告的图在 GitHub/GitLab 渲染**两次**都报语法错 | 回 `../diagram-generator/SKILL.md` 本地渲一次再贴，或降级为文本表 |

## 定义完成

本技能产出算「完成」的**外部可观测**条件（不许写形容词）：

- 文档落盘路径存在，含 Scope / Evidence / Findings / **≥1 条** Path
- 每条结论可追到 Evidence ID；无来源结论数为 **0**
- `verify-doc-links.py` 断链为 0；外部 URL 无 4xx/5xx
- Executive Summary 面向非技术读者，无术语堆砌，且其中每个数字都能在 Findings 找到来源
- 报告里嵌入的图都本地渲染过一次（或明确标注「仅提供图源」）

## 输出契约

```
FACT:       <观察，带来源：命令 / 文件:行 / Evidence ID>
HYPOTHESIS: <可测试断言 + confidence: high|medium|low>（状态见 `../ops/binary-model.md`）
QUESTION:   <当前最大不确定点>
NEXT:       <继续 | 换技能 | 停止（附成本判据）>
```

## 置信度词表

词表见 `../ops/confidence-vocabulary.md`。本技能特有判据：

- `confirmed`：报告中每条技术主张都能在 Evidence 里找到对应，且该 case 已过 `--strict` 审查
- `medium`：结论有 Evidence 支撑，但报告尚未过 case-review strict，或部分图表只交了图源
- `low`：报告中出现无法追溯的结论（**≥1 条**即降到这一档）
