---
name: diagram-generator
description: 把笔记或代码画成 Mermaid/PlantUML 文本图（流程图、时序图、架构图、ER 图）。用于：帮我画个流程图、时序图怎么画、Mermaid 架构图。
---

# Diagram Generator

## ACTION REQUIRED（读完后立刻执行）

1. `NOW`: **查经验卡** —— `python skills/scripts/experience-card.py search "<你看到的症状>"`。
   命中就读那张卡的 `invariant` + `decision.action`，并**逐条对照** `scope.appliesWhen`
   与 `scope.stopsWhen`：少一条前提就停用；命中任一停止条件就停。
   历史卡**不替代**当前目标的实测证据。详见 `../experience-cards/INDEX.md`。
2. `NOW`：确认当前任务是否命中本 skill 的适用范围
3. `NOW`：读取 `../TOOLS.md`，校验工具可用性和实际路径
4. `NEXT`：缺工具时调用 bootstrap，不要猜路径
5. `ACT`：按本卡的「工作流」挑**当下适用**的那一条动手；不要停在确认状态

## Purpose

Create clear, editable diagrams from messy or structured inputs. Prefer text-based diagram source first so the result can be reviewed, versioned, and refined. Render to files only when the user asks for an image/PDF or when a downloadable artifact would materially help.

## Default workflow

1. Identify the user's intent, audience, and source material.
2. Choose the diagram family and language using the decision table below.
3. Normalize entities, relationships, labels, states, branches, and time/order information before writing diagram code.
4. Generate concise, readable diagram source.
5. Validate the syntax mentally and, when creating files, run `scripts/render_diagram.py`.
6. Return the diagram source plus a short note about assumptions. When files are generated, include links to the output files.

Do not over-ask for clarification. If the request is underspecified, make reasonable assumptions and label them briefly.

## Diagram language decision table

Use Mermaid unless another language is clearly better.

| User wants | Prefer | Why |
|---|---|---|
| process flow, decision tree, simple swimlane | Mermaid flowchart | readable and easy to paste into Markdown |
| sequence of system/user interactions | Mermaid sequenceDiagram or PlantUML sequence | Mermaid for docs; PlantUML for UML formality |
| lifecycle, state machine, transitions | Mermaid stateDiagram-v2 or PlantUML state | compact transition syntax |
| database schema, entities, relationships | Mermaid erDiagram | portable ER notation |
| class/interface/object model | Mermaid classDiagram or PlantUML class | Mermaid for docs; PlantUML for detailed UML |
| project schedule | Mermaid gantt | concise timeline syntax |
| hierarchy, ideas, notes | Mermaid mindmap | good default for idea maps |
| customer/product journey | Mermaid journey | built-in journey notation |
| git history | Mermaid gitGraph | built-in git notation |
| dependency graph, package graph, large network | Graphviz DOT | better layout engines for dense graphs |
| architecture with layers, clusters, boundaries | Mermaid flowchart with subgraphs, Graphviz clusters, or PlantUML C4-style | choose based on requested fidelity |
| weighted flow/sankey-like relationship | Mermaid sankey-beta when supported, otherwise SVG or Graphviz | Mermaid support may vary by renderer |
| custom visual where source languages fit poorly | SVG | precise control over layout and styling |

## Output policy

- Always provide editable source unless the user explicitly asks only for an image.
- Default to a single best diagram. Offer alternatives only when genuinely useful.
- Prefer stable, simple syntax over fancy features that may not render in older Mermaid/PlantUML versions.
- Use short labels. Split long text into notes outside the diagram when needed.
- Avoid ambiguous node IDs. Use ASCII IDs and human-readable labels.
- Preserve user terminology, but standardize capitalization within a diagram.
- For technical diagrams, include boundaries such as client, service, database, queue, external API, and operator/user when they are implied.
- For business-process diagrams, distinguish happy path, decision points, failures, retries, and manual steps when present.
- For diagrams created from uncertain text, include an `Assumptions` section after the code.

## 本技能硬判据（图能不能用）

- **节点/边必须来自真实数据源，且点名产生它的工具**：调用图来自 `Ghidra` / `IDA` 导出的函数表，或 `radare2` / `rabin2` 的符号输出（节点数与源文件行数对得上才算 `confirmed`）；拓扑图来自 `nmap` 的服务表或 `tshark` 的会话表；固件分区图来自 `binwalk` 的输出；运行时序列图来自 `frida` 的 trace；利用链图里的偏移/地址来自 `pwntools` / `gdb` 的实际输出。对不上 → 图上标 `unknown`，宁缺不编。
- **先本地渲染、再贴进交付文档**：Mermaid 走 `mmdc -i x.mmd -o x.svg`，DOT 走 `dot -Tsvg`，PlantUML 要 JDK + 植物/UML jar。同一张图**两次**渲染都报语法错 → 换等价写法（别用新版才支持的语法），仍不行就降级成保守模板或纯文本表。没渲染通过的源码不许贴进交付物。
- **节点 ≥30 个或边接近全连** → 换 Graphviz（`rankdir` / `cluster` / `splines`）；Mermaid 在这个密度下糊成一团，这不是审美问题，是读不出来。
- **脱敏**：图里出现真实目标信息（IP、域名、主机名、token、用户名）→ 一律换 `{target}` / `{host}` 占位，交付前用 IP 正则 `grep` 一遍；节点 ID 只用 ASCII 语义名。
- **图与正文同版本**：图里每条边都应在正文找到对应结论；正文改了图没改就是过期图，重画而不是留着。

## 工具链与工具联动

| 环节 | 本机怎么调 | 输出接到哪 |
|---|---|---|
| 渲染器探测 | `. <仓根>\skillpack\skills\scripts\lib\Bootstrap.ps1` → `Resolve-ReverseToolSpec -Name mmdc` / `-Name dot`；通道状态 `powershell -NoProfile -ExecutionPolicy Bypass -File skillpack\skills\scripts\mcp-status.ps1` | 探测不到就只交图源并写明；别声称「已渲染」 |
| 调用图数据源 | `Ghidra`（`analyzeHeadless` 批量导函数表）、`IDA`（`idat`）、`radare2`、`rabin2`（符号/导入表） | 节点数必须与导出文件行数对得上 |
| 拓扑 / 流量图数据源 | `nmap -sV` 的服务表、`tshark` / `Wireshark` 的会话与协议分层 | 手画 IP 一律不允许 |
| 固件 / 分区图数据源 | `binwalk` 的提取结果 | 分区偏移写进图注 |
| 运行时序列图数据源 | `frida` 的 trace / hook 日志 | 消息顺序照日志排，不按想象排 |
| 利用链图数据源 | `pwntools` 的 exp 脚本、`gdb` 里的偏移与寄存器 | 偏移/地址逐字对上脚本 |
| 渲染与嵌入 | 本卡 `scripts/render_diagram.py`（按扩展名分派）；成品交给 `../docs-generator/SKILL.md` 嵌进报告 | 嵌入前先在目标渲染器渲一次 |

## Mermaid generation rules

Consult `references/diagram-patterns.md` for compact templates.

General Mermaid rules:
- Start with the correct diagram directive, for example `flowchart TD`, `sequenceDiagram`, `erDiagram`, `gantt`, `mindmap`, or `journey`.
- For flowcharts, use `flowchart TD` unless the user asks for left-to-right; use `flowchart LR` for architecture and pipelines.
- Use subgraphs for swimlanes or architecture layers. Name subgraphs with readable labels.
- Keep node IDs stable and ASCII-only, for example `ingest_service[Ingest Service]`.
- Quote labels that contain punctuation likely to confuse the parser.
- Use decision diamonds for branching: `decision{Condition?}`.
- Use consistent edge labels: `-- yes -->`, `-- no -->`, `-. async .->`, or `== critical ==>` only when meaningful.
- In sequence diagrams, declare participants before messages. Use `actor` for humans and `participant` for systems.
- Use `alt/else/end`, `opt/end`, `loop/end`, and `par/and/end` blocks for conditional, optional, repeated, and parallel flows.

## Graphviz DOT generation rules

Use Graphviz for large, dense, or layout-sensitive relationship diagrams.

- Prefer `digraph G` for directed relationships and `graph G` for undirected networks.
- Set layout-friendly graph attributes at the top: `rankdir=LR`, `nodesep`, `ranksep`, and `splines=true` when helpful.
- Use `subgraph cluster_name` for boundaries and subsystems.
- Use plain labels and restrained styling.
- Use edge labels only when they add meaning.
- For many nodes, group by domain with clusters and avoid crossing-heavy all-to-all edges.

## PlantUML generation rules

Use PlantUML when the user asks for UML or needs formal UML notation.

- Wrap diagrams with `@startuml` and `@enduml`.
- Use `actor`, `participant`, `database`, `queue`, `collections`, or `component` stereotypes when useful.
- Use `package`, `rectangle`, or `node` for architecture boundaries.
- For class diagrams, include only important fields/methods unless the user asks for exhaustive detail.
- For activity diagrams, use clear start/end markers and explicit branch labels.

## SVG generation rules

Use SVG only when text diagram languages cannot express the requested visual reliably.

- Keep SVG simple, accessible, and editable.
- Include `<title>` and meaningful text labels.
- Prefer rectangles, lines, arrows, and groups over complex paths.
- Do not embed external fonts or remote images.

## Rendering files

When the user asks for PNG/SVG/PDF, create a source file and run:

```bash
python "<SKILL_ROOT>/diagram-generator/scripts/render_diagram.py" input.mmd --format svg --out output.svg
python "<SKILL_ROOT>/diagram-generator/scripts/render_diagram.py" input.dot --format png --out output.png
python "<SKILL_ROOT>/diagram-generator/scripts/render_diagram.py" input.puml --format svg --out output.svg
```

> `<SKILL_ROOT>` 是本包 `skills/` 目录的实际路径，AI 应自动检测。

The renderer is intentionally dependency-tolerant. It tries common local tools and reports actionable installation hints if a renderer is unavailable. Do not claim an image was rendered unless the script completed successfully and the output file exists.

## Validation checklist

Before finalizing:

- The diagram type matches the user's task.
- The source is syntactically plausible for the chosen language.
- Labels are short enough to fit.
- Edges and message order reflect the input accurately.
- Assumptions are called out when the input was incomplete.
- For generated files, the output exists and opens or has nonzero size.

## Common response template

Use this structure for most diagram answers:

````markdown
下面是可编辑的 [language] 版本：

```[language]
[source]
```

Assumptions:
- [only if needed]

Rendered file: [link] [only if generated]
````

For English user requests, respond in English. For Chinese user requests, respond in Chinese unless they ask otherwise.

---

## 按需自举（On-Demand Bootstrap）

> 缺工具时只生成安装计划，获用户显式批准后才安装；不得自动安装或自动联网（`autoInstall=false`）。

### 自动化能力边界

| 工具 | 批准后可安装 | 安装方式 | 说明 |
|------|-----------|---------|------|
| Mermaid CLI (mmdc) | ✓ | npm install -g @mermaid-js/mermaid-cli | 渲染 Mermaid 为 PNG/SVG |
| Graphviz (dot) | ✗ | 手动安装 | https://graphviz.org/download/ |
| PlantUML | ✗ | 需要 Java + plantuml.jar | https://plantuml.com/download |
| Python (render script) | ✓ | 已在 bootstrap 中 | `scripts/render_diagram.py` 依赖 |

### 说明

本 skill 主要输出文本格式的图表源码（Mermaid/DOT/PlantUML），不一定需要本地渲染工具。只有当用户明确要求生成 PNG/SVG/PDF 文件时才需要对应的渲染器。

如果渲染器不可用，`scripts/render_diagram.py` 会输出安装提示而不是报错。

---

## 路由上下文

**上游入口**: `SKILL.md`（总控）、`../routing.md`
**触发条件**: 用户说"画图"、"流程图"、"架构图"、"攻击路径图"、"时序图"、"Mermaid"、"Graphviz"、"PlantUML"
**下游出口**:
- 生成的图表可嵌入 `docs-generator/` 的报告中
- 攻击路径图可配合 `pentest-tools/` 的渗透报告

**同级关联模块**: `docs-generator/`（报告中嵌入图表）

## 任务完成自检（声称完成前 MUST 通过）

- [ ] 我是否执行了工作流中的每一步（而不是只阅读）？
- [ ] 我是否走了**探测层四级递进**（`Resolve-ReverseToolSpec`）定位实际路径（而不是只跑一条 `Get-Command` 查空就报缺工具、也不是拿 `../TOOLS.md` 里的装法当路径猜）？
- [ ] 我是否产出了可复现证据（命令/脚本/截图/报告）？
- [ ] 我是否完成并回写了 RULES 要求的 Checklist 项？

---

## When NOT to use（近邻负例）

- 要写的是大段文字文档 → 用 `../docs-generator/SKILL.md`
- 要审 case 完整性 → 用 `../case-review/SKILL.md`
- 需要位图/截图/浏览器渲染才能表达（复杂拓扑、3D、真实页面标注） → 用 `../browser-automation/SKILL.md`
- 要画调用图但还没反编译、手上没有函数表 → 用 `../reverse-engineering/SKILL.md`
- 要画扫描出来的网络拓扑，但还没做过扫描 → 用 `../pentest-tools/SKILL.md`
- 图必须来自真实结构，不许为好看编造节点

## When to Pivot

信号与判据见 `../ops/skill-pivot-contract.md`。本技能去向：

| 触发证据 | 换到 |
|---|---|
| 图要嵌进文档或报告正文 | `../docs-generator/SKILL.md` |
| 图表达不了，需要位图/截图（画布标注、真实页面） | `../browser-automation/SKILL.md` |
| 图的节点来源可疑，要核它依据的 case 与哈希 | `../case-review/SKILL.md` |
| 同一张图**两次**渲染失败且报的是同一条语法 | 降级：换成保守模板（`references/diagram-patterns.md`）或纯文本表（本卡） |
| 节点数 **≥30** 或边接近全连，Mermaid 已经看不清 | 换 Graphviz DOT（本卡 Graphviz rules） |
| 要画调用图，但手上没有函数表/符号输出 | 回 `../reverse-engineering/SKILL.md` 采数据后再画 |
| 拓扑图的数据来自端口扫描或流量，且还没采 | `../pentest-tools/SKILL.md` |
| 时间线图的数据来自内存/磁盘取证 | `../digital-forensics/SKILL.md` |
| 图里含真实目标信息且要对外交付 | 先脱敏（本卡判据）再走报告口径 `../docs-generator/SKILL.md` |

## 定义完成

本技能产出算「完成」的**外部可观测**条件（不许写形容词）：

- 图源文件（.mmd / .dot / .puml）落盘，可再编辑
- 在目标渲染器上**渲染通过一次**（输出文件存在且非零字节），或在交付物里明确标注「仅提供图源」
- 图中每个节点/边可追溯到实际代码或案例事实，并写明来源工具与文件
- 对外交付版跑过脱敏检查：IP/域名/token 正则 `grep` 无命中

## 输出契约

```
FACT:       <观察，带来源：命令 / 文件:行 / Evidence ID>
HYPOTHESIS: <可测试断言 + confidence: high|medium|low>（状态见 `../ops/binary-model.md`）
QUESTION:   <当前最大不确定点>
NEXT:       <继续 | 换技能 | 停止（附成本判据）>
```

## 置信度词表

词表见 `../ops/confidence-vocabulary.md`。本技能特有判据：

- `confirmed`：图渲染通过，且节点数与实际结构（函数表/会话表/binwalk 输出）核对一致
- `medium`：图渲染通过，但部分节点来自二手描述，未核行数
- `low`：仅凭文字描述想象出结构图，没有任何数据源
