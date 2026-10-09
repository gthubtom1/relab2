# 经验卡 Schema（Experience Card Schema）

> **来源声明**：本文改编自外部仓库 `aoyunyang/spider-king-skill`（MIT License）的 `experience-card-schema.md`。原始内容为英文原文，此处译为中文并按本包六段式规范重排；技术术语保留英文原词并附中文，AI 检索时中英文均可命中。改编中修正了源文档的若干表述与失效引用（见文末「源文档勘误」）。
>
> **什么时候用**：要把**一条反复出现的决策规则或确定性操作**保存下来时。经验卡（experience card）**不是** case 报告，**不是**某个目标的专用配方，**也不是**「历史产出在当前目标上可信」的许可证。
>
> **平台与本机状态**：本文是 schema 与规程，不依赖具体本机工具。需要本机注意的只有两条：**(1)** 源文档的晋级目标目录 `references/experience-cards/` 在本包**尚未建立**（未创建），因此候选先落 `<project>/js_reverse_cache/tasks/<id>/experience-candidate.json`；**(2)** 经验卡里常被引用的 `iv8-local-runtime` 边界，本机无 iv8（社区运行时，PyPI 无发行版），相关卡片在本机**无法复验**，消费前须按 `./skill-maintenance.md` 的验证命令实跑。本包**没有** `scripts/` 目录，源文档引用的 `../triage/forward-testing-playbook.md` 等扁平路径已改为实际路径。

---

## 适用信号（Recognition signals）

出现下列任一情况，说明该落一张经验卡：

- 同一个不变量（invariant）在**两个独立任务**里复现了
- 某个结构性教训反复出现，但每次的站点、厂商、错误码都不一样（需要抽象成通用模式语言）
- 某个决定（选哪条路线）或某个确定性操作反复被做出，值得固化下来
- 想把「某站点怎么绕的」升级为「这一类协议长什么样」
- 手上有一条候选，但还差若干晋级条件没满足，需要**把缺口显式记下来**

**不构成信号**的情况：

- 只有**一次**成功结果
- 只有「helper 加载成功了」「输出形状像对的」「HTTP 200」这类弱证据
- 只有散文式提示词、拷贝来的线上值、看起来合理的 token 形状
- 目标站点特有的端点细节、厂商 `errorCode`、`sentinel` 名字 —— 那些属于 `../../field-journal/`，不属于经验卡

## 前置（Entry conditions）

### 一、存储生命周期（Storage Lifecycle）

**一份一跳的候选**（one-job candidate）留在任务项目下：

```text
<project>/js_reverse_cache/tasks/<task-id>/experience-candidate.json
```

> **本机现状**：`references/experience-cards/` 目录**在本包尚未建立**。在该目录被创建之前，所有晋级后的卡片**仍以候选形态留在任务本地**，由 `../../../field-journal/KB-INDEX.md` 做检索入口。源文档的晋级目标路径如实保留在文中，但**在目录建立前不可用**。

把一张卡晋级进 `references/experience-cards/<card-id>.json`，只有两个前提同时成立：**正在维护本技能（spider-king）**，且 `./skill-maintenance.md` 的「可复现经验门（Reproducible Experience Gate）」已经通过。

**晋级后的卡及其 fixture 必须无秘密（secret-free）。**
**绝不**把原始任务抓取、目标 URL、账号、cookie、token、key、header 或私有响应拷进技能包。脱敏规范见 `../../../field-journal/anonymization.md`。

### 二、候选与晋级后卡的基本分野

| | 候选（candidate） | 晋级卡（promoted） |
|---|---|---|
| `status` | `candidate` | `promoted` |
| 落点 | 任务本地 `experience-candidate.json` | `references/experience-cards/<card-id>.json`（本机尚未建立该目录） |
| 允许不完整 | **是**，故意允许 | 否 |
| 缺失的证据 | 用 `null`，并逐条列进 `missingPromotionRequirements` | 不允许有 `null` |
| 能否被当作可复用卡消费 | **否** | 是（且须过消费规则） |

## 步骤（Working method）

### 一、Candidate 形态

**一份一跳的候选是被故意允许不完整的。** 记录已知事实，不存在的证据用 `null`，**逐条列出每一个未满足的晋级门**。
**绝不**编造 fixture 路径、oracle、第二次复现、首个分歧点或验证命令。

```json
{
  "schemaVersion": 1,
  "id": "generic-family-boundary-invariant",
  "status": "candidate",
  "title": "Short structural lesson",
  "invariant": "One provisional binary or measurable statement",
  "scope": {
    "family": "signer-gated | verifier-gated | decode-gated | session-gated | transport-gated",
    "boundary": "request | response | runtime | transport | session | verifier",
    "appliesWhen": ["observed structural condition"],
    "stopsWhen": []
  },
  "reproductions": [
    {
      "jobFingerprint": "sha256 of a non-secret job identity",
      "observedAt": "YYYY-MM-DD",
      "artifactSha256": "64 lowercase hex characters",
      "independent": true
    }
  ],
  "fixture": null,
  "oracles": {
    "positive": null,
    "negative": null
  },
  "firstDivergence": null,
  "decision": {
    "preferredRoute": null,
    "action": "provisional smallest action",
    "fallback": null
  },
  "validation": null,
  "missingPromotionRequirements": [
    "second-independent-reproduction",
    "secret-free-fixture",
    "positive-oracle",
    "negative-control",
    "first-divergence",
    "stops-when-boundary",
    "validation-command"
  ]
}
```

**候选始终是任务本地的，绝不作为可复用卡被消费。** 最低限度上，要保住：**一条无秘密的不变量**、**它被观测到的适用边界**、以及 `reproductions` 里**支撑它的任务产物哈希**；并把每一个缺失的门名放进 `missingPromotionRequirements`。

### 二、Promoted 形态

```json
{
  "schemaVersion": 1,
  "id": "generic-family-boundary-invariant",
  "status": "promoted",
  "title": "Short structural lesson",
  "invariant": "One binary or measurable statement",
  "scope": {
    "family": "signer-gated | verifier-gated | decode-gated | session-gated | transport-gated",
    "boundary": "request | response | runtime | transport | session | verifier",
    "appliesWhen": ["observable structural condition"],
    "stopsWhen": ["counter-condition or unsupported boundary"]
  },
  "reproductions": [
    {
      "jobFingerprint": "sha256 of a non-secret job identity",
      "observedAt": "YYYY-MM-DD",
      "artifactSha256": "64 lowercase hex characters",
      "independent": true
    }
  ],
  "fixture": {
    "path": "skill-relative secret-free fixture path",
    "sha256": "64 lowercase hex characters",
    "generator": "optional deterministic generator path",
    "secretFree": true
  },
  "oracles": {
    "positive": "decisive downstream assertion and command",
    "negative": "one intentional mutation and expected protocol failure"
  },
  "firstDivergence": {
    "stage": "ordered stage name or index",
    "path": "redacted structural path",
    "kind": "missing | value | order | framing | state | transport"
  },
  "decision": {
    "preferredRoute": "Spider route name",
    "action": "smallest reusable action",
    "fallback": "named fallback when the boundary does not hold"
  },
  "validation": {
    "lastVerifiedAt": "YYYY-MM-DD",
    "command": "deterministic local validation command"
  }
}
```

### 三、晋级后如何落一条脱敏 case（对接 field-journal）

经验卡是**通用资产**；脱敏 case 记录是**这次具体任务的现场**。两者并存，不是二选一 —— 晋级为通用经验之后，仍应按 `../../../field-journal/_template.md` 落一份脱敏 case，把这次任务的现场固定下来：

| 经验卡字段 | field-journal / case-review 落点 |
|---|---|
| `id` | case 文件名与「Evidence 链摘要」小节引用的模式名 |
| `invariant` + `title` | 「目标概述」与「Finding / Path 摘要」的 `top_finding` |
| `scope.family` / `scope.boundary` | 「场景分类」（JS 签名 / 抓包分析 / …）与「角色」小节 |
| `reproductions[].jobFingerprint` | 「环境信息」小节中的非秘密任务标识 |
| `reproductions[].artifactSha256` | `- content_hash: sha256:<64 hex>` + `- artifact_path:`，由 `../../case-review/scripts/review_case.py --verify-hashes` 校验 |
| `oracles.positive.command` | `- repro_command:`（**必填**） |
| `oracles.positive` / `negative` 的结论类型 | `- status: observed \| candidate \| validated \| false_positive \| accepted_risk` |
| `firstDivergence` | 「Finding / Path 摘要」与「完整执行链路」中记的弯路 |
| `stopsWhen` | 「踩坑记录」表中「什么时候这条经验不适用」 |
| —（卡中无对应字段） | `- severity: critical \| high \| medium \| low \| info \| n/a` |
| —（卡中无对应字段） | `- linked_workitem: WI-xxx`（须真实存在） |

**case 记录本身必须脱敏**（规范见 `../../../field-journal/anonymization.md`）：目标域名换 `{target_domain}`、token 换 `{token}`、账号换 `{username}`。经验卡**无秘密**的硬要求，比 case 脱敏**更严** —— case 允许记录本地私有细节，**经验卡不允许记录任何秘密**。

### 四、消费规则（Consumption Rule）

把一张卡当作**假设加速器**（hypothesis accelerator）来用：

1. 把当前证据与**每一条** `appliesWhen` 条件对照匹配。
2. 运行该卡的 fixture 与**两个** oracle（正、负）。
3. 在**同一边界**上，为当前目标证明**一个**最小事实。
4. **任何一条** `stopsWhen` 条件出现，就停止使用该卡。

**历史卡永不替代当前的 wire 证据、定值向量或下游验收。**
当出现下列任一情况时**退役（retire）**这张卡：fixture 复现不出来、边界变得过宽、或两个独立反例推翻了该不变量。

## 判据（Verification checklist）

### A. 晋级门（Promotion Gate）

一张 `promoted` 卡必须**同时**具备以下 7 条：

1. **≥ 2 次真正独立的复现**，且**任务指纹（job fingerprint）互不相同**。每次复现都标明它支撑的产物哈希；只有在「独立性另有证明、且相同字节本身正是被测不变量」时，哈希才允许相同。
2. **一个最小 fixture 或确定性生成器**，并记录其 SHA-256。
3. **一个 positive oracle**，打到**决定性的下游行为**，而不是「helper 加载成功」或「输出形状看着对」。
4. **一个 negative control**，**因预期的协议原因**失败。
5. **首个分歧的状态迁移**（`firstDivergence`）。
6. **显式的 `appliesWhen` 与 `stopsWhen` 边界**。
7. **一条本地验证命令**，从干净 checkout 或拷贝后的技能目录跑通。

**不构成独立复现的**：只改期望输出、时间戳、nonce 或文件名。
**不满足晋级门的证据**：散文式提示词、拷贝来的线上值、看起来合理的 token 形状、helper 加载成功、一次 HTTP `200`。

### B. 消费前检查（*改编补入*，源文档无独立清单，从消费规则反推）

1. **全部** `appliesWhen` 条件逐条匹配上了当前证据 —— 少一条就停。
2. fixture 跑通，positive oracle 与 negative oracle **都**执行过；negative control 确实以预期的协议原因失败（而不是以别的错误崩掉）。
3. 已在**同一 `boundary`** 上为当前目标证明了一个最小事实。
4. `stopsWhen` 的每一条条件**逐条检查过且均未出现**。
5. `validation.command` 在当前机器上**实跑通过**，且 `lastVerifiedAt` 是这个日期 —— 若该卡涉及 `iv8-local-runtime` 边界而本机无 iv8，**直接判不通过**，不要凭记忆采信。

### C. 无秘密检查（*改编补入*）

1. 卡全文、`fixture` 指向的文件、及其生成器输出中，**没有**目标 URL、账号、cookie、token、key、IV、Authorization 值或私有响应体。
2. `fixture.secretFree` 为 `true`，且**这个声明是核对过的**，不是照抄模板。
3. 卡内所有哈希均为**无密钥 SHA-256**，且只用于公开高熵代码、已公开资产或显式的本地分析产物 —— 含秘密的抓取**不应**出现在无密钥哈希的卡里。

## 常见坑（Common traps）

- 拿**一次**成功结果就落卡，把它当可复用经验
- 把「helper 加载成功」「输出形状合理」「HTTP 200」当成 positive oracle
- 改了 nonce 或时间戳就宣称是第二次独立复现
- 编造 fixture 路径、oracle 或验证命令 —— 源文档明确禁止，且这些是判据里最常被造假的字段
- 候选卡被直接当可复用卡消费，跳过 `appliesWhen` / `stopsWhen` 对照
- 把站点特有的端点、厂商 `errorCode`、`sentinel` 名写进卡，而不是抽象成通用模式语言
- 把原始 cookie、token、目标 URL 写进卡或 fixture
- 卡一直不退役：fixture 早就复现不出来了还在用
- 用历史卡替代当前 wire 证据，跳过定值向量与下游验收
- 把「两端读数一致、cookie 没变」当成通过了验证 —— 停机不等于存活

## 相关（Related）

- `./skill-maintenance.md` —— 「可复现经验门」与沉积规则（Deposition Rules）；卡晋级前的必过项
- `./provider-work-order.md` —— 经验卡沉淀来源的任务契约（scope / permissions / 脱敏边界）
- `./project-artifact-contract.md` —— `experience-candidate.json` 所在的产物层级
- `./specialist-handoff-contract.md` —— 同属任务本地产物的 schema 风格对照
- `../deliver/case-reuse-playbook.md` —— 判断某次任务结论是否已具备可复用价值
- `../triage/reproducible-evidence-playbook.md` —— `reproductions[].artifactSha256` 的最低标准
- `../triage/minimal-verifiable-facts-playbook.md` —— 把叙述压成 5–15 条结构化事实的方法
- `../principles/anti-patterns-playbook.md` —— 「常见 tempting shortcut 为什么是假进展」的原则级对应
- `../principles/doctrine-index.md` —— 本包全部 doctrine 的索引入口
- `../crypto/iv8-runtime-cheatsheet.md` —— `iv8-local-runtime` 边界的参考（**本机无 iv8，该文档形态未在本机验证**）
- `../../../field-journal/_template.md` —— 晋级为通用经验后落脱敏 case 的模板
- `../../../field-journal/anonymization.md` —— 脱敏占位符总表与自动检测脚本
- `../../../field-journal/KB-INDEX.md` —— 已沉淀经验的检索入口（`references/experience-cards/` 建立前的实际入口）
- `../../SKILL.md` —— `content_hash` / `repro_command` 等证据字段的校验流程

---

## 源文档勘误（改编时修正）

1. **源文档 `## Contents` 目录块指向英文锚点**。已删除，改为中文六段式结构下的自然导航。
2. **源文档的晋级目标目录 `references/experience-cards/` 在本包不存在**（未创建）。源文档把它写成既成事实，容易让读者以为落盘即可完成。已在「存储生命周期」处明确标注「该目录尚未建立」，并指明在建立前候选留在 `js_reverse_cache/tasks/<id>/experience-candidate.json`、检索走 `../../../field-journal/KB-INDEX.md`。
3. **源文档引用 `skill-maintenance.md`** 为扁平路径，实际该文件在同目录 `references/contract/`。已改为 `./skill-maintenance.md`。
4. **源文档 `## Promoted Shape` 的 `decision.preferredRoute` 写 "Spider route name"**，而本包已不复用 Spider King 的路线命名体系。JSON 占位说明属 schema 内文本，**保持原样**（它是字段语义说明而非枚举取值），中文译文相应改为「Spider 路线名」并在此注明。
5. **源文档 `## Consumption Rule` 第 4 条只写了停止条件，没有定义「退役」的判据数量**。本文把紧随其后的最后一句（「Retire a card when its fixture cannot be reproduced…」）显式提升为独立小节，因为它是硬性退役判据而非使用规则。
6. **源文档把「独立复现」的定义藏在 `## Promotion Gate` 第 1 条的长句里**，且「哈希可以相同的例外条件」极易被跳过。本文将其拆为独立编号条目并在「常见坑」中重复一次。
7. **源文档未提 `../triage/forward-testing-playbook.md` 等其它文件的路径**，但同批文档存在扁平 `references/xxx.md` 写法习惯。本文已全部改用实际目录相对路径，并核实目标文件存在后再写。
8. **源文档未与 `../../field-journal/`、`../../case-review/` 建立任何联系**。改编按任务要求补了「步骤」第三节的对齐映射表（经验卡字段 → E-id 证据字段、`content_hash`、`repro_command`、`severity`、`linked_workitem`），并**逐条标注哪些映射是改编补入**。`severity` 与 `linked_workitem` 在经验卡 schema 中**没有对应字段**，映射表中已如实标明「卡中无对应字段」，未虚构 schema 字段。
9. **源文档 `validation.command` 要求「从干净 checkout 或拷贝后的技能目录跑通」，但本包没有 `scripts/` 目录可供这样的命令调用**。本文未编造任何验证命令，只保留了这条要求本身，并说明涉及 `iv8-local-runtime` 的卡在本机无法复验。
10. **源文档全文无一处提及 `scripts/*` 工具**，故本文也未引用；但同批其它文档确有引用不存在的 `scripts/` 工具的情况，已在其它篇处理。