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
5. `ACT`：进入"工作流"第一步并执行，不要停在确认状态

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
- 要画的图超出 Mermaid/PlantUML 表达能力（复杂拓扑/3D） → 用 `../docs-generator/SKILL.md`
- 图必须来自真实结构，不许为好看编造节点

## When to Pivot

信号与判据见 `../ops/skill-pivot-contract.md`。本技能去向：

| 触发证据 | 换到 |
|---|---|
| 图里需要嵌入文档正文 | `../docs-generator/SKILL.md` |
| 图表达不了（需要位图/截图） | `../browser-automation/SKILL.md` |
| 需要审图所依据的 case | `../case-review/SKILL.md` |

## 定义完成

本技能产出算「完成」的**外部可观测**条件（不许写形容词）：

- 图源文件（.mmd/.puml）落盘，可再编辑
- 在目标渲染器上能正确渲染（无语法错误）
- 图中每个节点/边可追溯到实际代码或案例事实

## 输出契约

```
FACT:       <观察，带来源：命令 / 文件:行 / Evidence ID>
HYPOTHESIS: <可测试断言 + confidence: high|medium|low>（状态见 `../ops/binary-model.md`）
QUESTION:   <当前最大不确定点>
NEXT:       <继续 | 换技能 | 停止（附成本判据）>
```

## 置信度词表

词表见 `../ops/confidence-vocabulary.md`。本技能特有判据：

- `confirmed`：图渲染通过且节点数与实际结构核对一致
- `low`：仅凭文字描述想象出结构图
