# 报告模板（Report Templates）

> **来源声明**：本文改编自外部仓库 `aoyunyang/spider-king-skill`（MIT License）的 `report-templates.md`。原始内容为英文原文，此处译为中文并按本包六段式规范重排；Markdown 模板内部的英文标签（它们是要被填写的字段名）与 JSON schema 保持原样不译，只在模板之外用中文说明。改编中修正了源文档的若干表述与失效引用（见文末「源文档勘误」）。
>
> **什么时候用**：任何一次协议逆向调查要落报告时 —— 阶段推进、勘测、动态验证、实现决策、交付、proof manifest（证明清单），都用这里的固定标题，保证不同项目的产出可横向对比。
>
> **平台与本机状态**：本文是纯文档规范，不含可执行脚本，不依赖任何工具。涉及的 `analysis/` `collector/` 目录树按本文推荐布局落地；`review_case.py` 校验用的是本机 `D:\EXE\python\python.exe` 3.12.0（`../../../case-review/scripts/review_case.py`，本机存在）。文中所有目录与文件均为**约定名**，不代表本机已存在任何实体。

---

## 适用信号（Recognition signals）

出现下列任一情况，就该套用本文模板：

- 要把一个阶段的进展写成可交接、可比对的文本（而非「我搞定了」）
- 要区分「已证明」「已否定」「未比较」——三者在报告里必须分得开
- 交付一个 `compact-replay`（紧凑重放）或 `collector`（采集器）实现
- 声明了 `evidence`（仅取证）或 `local-proof`（本地证明）形态，需要说明边界
- 要写 `analysis/proof_manifest.json` 并报它的哈希
- 报告要跨人、跨项目传阅 —— 此时脱敏规则是硬性的（见下方「敏感数据规则」）

## 前置（Entry conditions）

1. **先有 intake mode（接入模式）判定**：`live-target` / `artifact-only` / `continuation` 三选一。模板里的字段按这个前提填写，`artifact-only` 不要凭空写浏览器证据。参见 `./provider-work-order.md`。
2. **先有可写的证据包**：至少一个证据包目录与它的 SHA-256，否则 `Evidence package path and SHA-256` 这一行只能写「无」。
3. **授权边界已确认**：`Implementation Brief` 模板里的权限字段只有在 `./provider-work-order.md` 的授权闸门通过后才有意义。模板本身不构成授权。
4. **若本任务产出了独立证据目录 `evidence/E-xxx.md`**：每条证据必须满足 `../../../field-journal/_template.md` 中「契约对齐（review_case.py）」一节列出的字段契约（`severity` / `status` / `repro_command` / `content_hash` + `artifact_path` / `linked_workitem`），否则 `--strict` 校验会 FAIL。详见本文「判据」段。

## 步骤（Working method）

### 敏感数据规则（全局，默认生效）

**报告默认脱敏（redacted by default）。** 这不是可选项。

具体规则：

- **要报告**：credential / token / header / cookie 的**名字**，加上其来源（provenance）、作用范围（scope）、有效期（expiry），以及一个短哈希或指纹（fingerprint）。
- **不要**：把原始秘密值粘进对话、报告、截图、fixture 或版本库。
- 运维上确实需要原始值时：把它放在**任务本地的、被 gitignore 的 secret store** 里，报告里只引用**路径与哈希**。
- 除非该 payload 已被证明是公开且非敏感的，否则原始 payload 样本一律脱敏。
- 端点只写**不含 userinfo、不含原始 query 值**的形式；只保留 query 字段名和复现协议所需的其他结构信息。

#### 与 `field-journal` / `review_case.py` 的对接（必须做到）

若本次任务产出了独立证据目录 `evidence/E-xxx.md`（而不是只有本包内的报告），那么：

- 每份证据文件的标题须为 `### E-xxx`，且与文件名一致（`../../../../examples/ctf-demo/evidence/E-001.md` → `### E-001`）。
- 字段必须齐：`severity` ∈ `critical|high|medium|low|info|n/a`；`status` ∈ `observed|candidate|validated|false_positive|accepted_risk`；`repro_command` 必填（离线场景在 `notes` 里注明 offline/离线）；填了 `content_hash: sha256` 就必须配套 `artifact_path:`（case 内相对路径）。
- 自检命令（Windows）：
  ```powershell
  D:\EXE\python\python.exe skillpack\skills\case-review\scripts\review_case.py work\<case> --verify-hashes --strict
  ```
- 脱敏 case 的落盘模板见 `../../../field-journal/_template.md`，其 `## 脱敏要求` 一节给出的占位符表（`{target_domain}` `{token}` `{user_email}` …）与本文上面的「敏感数据规则」是同一套约束；两者冲突时以 `../../../field-journal/anonymization.md` 的正则检测为准。

### 阶段增量报告（Phase delta report）

每个阶段收尾写一份。**中文说明**：这个模板的用途是让「这一轮比上一轮多了什么」一目了然 —— 新证据、假设变化、能力变化、第一处分歧、下一步最小的证明。

```markdown
Phase Delta
- New evidence:
- Changed hypothesis:
- Capability or intake-mode change:
- Evidence package path and SHA-256:
- First divergence: step / path / kind / or not yet compared
- Proof manifest artifact hash: SHA-256 computed after the manifest is written
- Saved artifact paths and hashes:
- Next smallest proof:
```

### 勘测报告（Recon report）

**中文说明**：动手改之前的一份事实盘点。核心是「真实请求候选」清单，以及明确列出那些**误导信号（misleading signals）** —— 页面上的诱饵。

```markdown
Recon
- Target URL:
- Final landing URL:
- Page type: SSR / CSR / SPA / MPA / hybrid
- Useful data source: HTML / XHR / Fetch / GraphQL / WebSocket / asset / binary / other

Real request candidates
- Request 1:
  - URL:
  - Method:
  - Purpose:
  - Transport kind:
  - Paging fields:
  - Key headers: names / provenance / redacted fingerprints
  - Key cookies: names / writer / scope / expiry / redacted fingerprints
  - Decode needed:

Misleading signals
- 1.
- 2.

Next hypothesis
- 1.
- 2.
```

### 动态验证报告（Dynamic validation report）

**中文说明**：一次 hook / diff / replay / 定值助手测试之后的结论。注意 `Raw payload sample` 一行允许写「脱敏摘录」**或**「本地路径 + 哈希」二选一 —— 后者优先。

```markdown
Dynamic Validation
- Target function or request:
- Validation method: hook / diff / replay / fixed-input helper test
- Inputs:
- Observed outputs:
- Raw payload sample: redacted excerpt or local path plus hash
- Evidence package path and SHA-256:
- First divergence: step / path / kind / or no divergence

What changed on the wire
- Query:
- Body:
- Headers: names, changed slots, and redacted fingerprints
- Cookies: names, writers, scopes, and redacted fingerprints

Conclusion
- Verified helper or protocol rule:
- Verified decode or parser rule:
- Remaining unknowns:
```

### 条件式实现简报（Conditional implementation brief）

**中文说明**：只在**声明形态是 `compact-replay` 或 `collector`** 且**至少还存在一个实质性的实现选择或授权选择**时才写。典型的「实质性选择」包括：几种互相竞争的实现形态、尚未确定的运行时升级、依赖选择或安装授权、持久化路径或保留范围、线上还是会话态权限。

**不要**为这些情况硬凑一份简报：`evidence`、`local-proof`、明确声明的不写入分析、或者路线已经被证明且其受控动作已被既有闸门完全覆盖 —— 后者写一段简短的 route note 就够了。

**这一份记录的是「决定」，不是「批准」。** 它不能扩大范围、预算、权限或 `allowedPaths`，也不在 `./provider-work-order.md` 已有的权限闸门之外新增任何「需要用户确认」的停顿点。

```markdown
Implementation Brief
- Trigger: competing implementation forms / runtime escalation / dependency install / durable writes / permission choice
- Delivery shape: compact-replay / collector
- Real request: scheme + host + port + route | method | content type
- Dynamic fields: name | writer | wire slot | scope | expiry | refresh path
- Evidence and fixed vectors: source/path + keyed fingerprint | expected | observed
- Candidate forms: form | evidence fit | runtime/dependency/authority impact | select/reject reason
- Chosen boundary: Python owns live HTTP/orchestration; helper type and narrow responsibility, or none
- Session contract: issuance | chain | identity/context scope | refresh; no raw secret values
- Acceptance: decisive oracle | negative control | required replay count
- Planned durable paths: only destinations covered by writable mode and inherited allowedPaths
- Permission status: existing authority used | new authority genuinely required
- Residual risk: risk | current evidence | retirement proof
```

### 紧凑协议交接件（Compact protocol handoff）

**中文说明**：`compact-replay` 或 `collector` 在对应能力闸门通过之后的**默认最终摘要**。它总结的是「证明」，**不替代**那个闸门。若结果是 `evidence` 或 `local-proof`，只有在紧凑协议摘要确实有用时才用它，并且要把线上验收与重放次数标为 `unproven`，不得暗示交付可运行。

```markdown
Protocol Handoff
- Capability: compact-replay / collector / explicitly bounded evidence or local-proof
- Real request: scheme + host + port + route | method | content type
- Protocol order: bootstrap/issuance -> refresh -> sign/envelope -> request -> decode -> first downstream consumer, omitting absent stages
- Dynamic fields: name | writer | wire slot | scope | expiry | refresh path
- Evidence: decisive source/path + keyed fingerprint
- Fixed vectors: input/reference | expected | observed | pass/fail
- Python/helper boundary: Python-owned HTTP/orchestration | helper kind, inputs, outputs, and runtime pin, or none
- Session: issuance | required chain | identity/context scope | expiry/refresh | cross-session status
- Acceptance: decisive business oracle | negative control | live/offline replay count
- Saved paths: collector/entrypoint | output | evidence package + SHA-256 | proof manifest + post-write SHA-256
- Browser-free status: yes/no; runtime-free status: yes/no
- Residual risk: remaining dependency or unproved boundary | impact | retirement proof
```

### 最终交付报告（Final delivery report）

**中文说明**：紧凑交接件不够用、需要展开能力细节或调查细节时用这一份。

**与 `field-journal` / `review_case.py` 的对接**：本模板中的 `Verification` 段与 `Known instability` / `Residual risk` 段，应能一一映射到 `../../../field-journal/_template.md` 的字段 —— `Verification` 对应「完整执行链路」与「Evidence 链摘要」，`Known instability` 对应「踩坑记录」表，`Residual risk` 对应 `accepted_risk` 状态的证据条目。若本任务同时产出了独立证据目录 `evidence/E-xxx.md`，必须先让该目录通过 `--strict` 字段契约（字段清单见本文「敏感数据规则」小节末尾），再写这份最终交付报告。

```markdown
Final Delivery
- Collector path:
- Output path:
- Intake mode:
- Capability snapshot:
- Proof manifest: analysis/proof_manifest.json
- Proof manifest artifact hash: SHA-256 computed after the manifest is written
- Evidence package path and SHA-256:
- First divergence: step / path / kind / or no divergence
- Real endpoint: scheme + host + port + route, without userinfo or raw query values
- Method and content type:
- Final protocol order:
- Real moving parts: name / writer / wire slot / scope / expiry / refresh path
- Transport kind:
- Decode chain:
- Python/helper boundary:
- Session contract:

Verification
- Acceptance oracle:
- Negative control:
- Repeat runs: live / offline
- Pagination confirmed:
- Fixed-input self-checks:
- No browser dependency:

Minimal verifiable facts
- 1.
- 2.
- 3.

Known instability
- 1.
- 2.

Residual risk
- Risk / impact / retirement proof:
```

### Proof manifest（证明清单）

保存为 `analysis/proof_manifest.json`，**不含任何线上秘密值**。字段如下（JSON schema 保持源文档原样）：

```json
{
  "intake_mode": "live-target | artifact-only | continuation",
  "tool_capabilities": {},
  "artifact_hashes": [],
  "evidence_packages": [
    {
      "path": "analysis/evidence.json",
      "sha256": "<64 lowercase hex characters>"
    }
  ],
  "first_divergence": {
    "step_index": 0,
    "path": "<redacted structural path>",
    "kind": "<difference kind>"
  },
  "session_scope": {},
  "helper_versions": {},
  "fixed_vectors": [],
  "live_replay_count": 0,
  "redacted": true
}
```

**写完文件之后**，把该文件**自身**的 SHA-256 报在它旁边。**不要**把这个自哈希写进 manifest 内部 —— 那会产生递归值。

### 推荐采集器目录树（Recommended collector tree）

**中文说明**：推荐的落地布局。`analysis/` 放调查产物与证明，`collector/` 放实现，`output/` 放产出，`logs/` 放运行日志，`tests/` 只放最小冒烟。

```text
<project-root>/
  analysis/
    deobfuscated.js
    fixed_inputs.md
    key_logic.js
    notes.md
    proof_manifest.json
  collector/
    client.py
    decode.py
    main.py
    pipeline.py
    settings.py
    sign.py
    storage.py
  logs/
  output/
  tests/
    test_smoke.py
  README.md
  requirements.txt
```

### 运行路径与缓存（Run path and cache）

**中文说明**：三个必须写清楚的位置 —— 入口在哪、调查缓存在哪、交付证明在哪。

需要写明：

- PyCharm 入口：`main.py` 或 `collector/main.py`
- 调查缓存：`js_reverse_cache/tasks/<task-id>/`
- 交付证明：`analysis/proof_manifest.json`

## 判据（Verification checklist）

写完报告后逐条对照。**任何一条不满足，报告就不算完成。**

- [ ] 报告里出现的所有 secret 类字段（token / cookie / header / password）都是**名字 + 指纹**，没有裸值。
- [ ] 端点写法不含 userinfo、不含原始 query 值，只保留 query 字段名。
- [ ] `first divergence` 一行要么写明具体 step/path/kind，要么明确写 `not yet compared` / `no divergence` —— **不允许留空**。
- [ ] `Proof manifest artifact hash` 是在 manifest 写完之后计算的，且**不在 manifest 内部**。
- [ ] 交付形态声明明确：`compact-replay` / `collector` / `evidence` / `local-proof`，没有含混表述。
- [ ] 若形态是 `evidence` 或 `local-proof`：线上验收与重放次数标为 `unproven`，没有暗示可运行交付。
- [ ] `Implementation Brief`（若写了）没有扩大范围、预算、权限或 `allowedPaths`，也没有新增用户确认点。
- [ ] `Conditional implementation brief` 只在确有实质选择时出现 —— 不是每次交付都走一遍仪式。
- [ ] `Protocol Handoff` 只在对应能力闸门通过后出现（或在 `evidence` 形态下被明确标注为 `unproven`）。
- [ ] `Required replay count` 与 `Negative control` 都有实际结果，不是空字段。
- [ ] 若产出了独立证据目录 `evidence/E-xxx.md`：`review_case.py --verify-hashes --strict` 通过（`severity` / `status` 取值合法、`repro_command` 非空、`content_hash` 与 `artifact_path` 配套、`linked_workitem` 指向真实存在的 `WI-xxx`）。
- [ ] 落盘的脱敏 case（若写入了 `field-journal`）已对照 `../../../field-journal/anonymization.md` 末尾的 checklist 跑过占位符扫描。

## 常见坑（Common traps）

- **把 proof manifest 的自哈希写进 manifest 自己** —— 递归值，哈希永远对不上。写在文件旁边。
- **把「加载成功」写成「证明完成」**。helper 跑起来了不等于 wire 上对了；`First divergence` 那一栏就是防这个的。
- **在 `evidence` 形态的报告里暗示 collector 可运行**。读者会拿它当交付。标 `unproven`。
- **把 payload 原文贴进报告**。除非证明是公开非敏感的，否则一律脱敏摘录或写路径+哈希。
- **在 `Implementation Brief` 里顺手批准自己**。简报是决定记录，不是授权。
- **给每一单都写实现简报**。源文档的判定是「条件式」：路线已证明且受控动作全覆盖时，一句 route note 就够。仪式化会让这份文档失去信号。
- **把 `Resume` 式的续做当成新任务**，或者反过来：续做时重跑全部启动闸门。`continuation` 有自己的失效规则。
- **报告里 `Known instability` 空着**。真的有就写；确实没有就写「无」，别留白。
- **把 `Minimal verifiable facts` 写成叙述性总结**。这一栏要的是 5 到 15 条**结构性事实**，升级后能逐条复查。
- **独立证据目录字段不合契约**。`severity` 写 `High`、`status` 写 `verified` 这类自造取值会让 `--strict` FAIL；取值集合是封闭的。

## 相关（Related）

- `./provider-work-order.md` —— 工单、接入模式、权限闸门、`allowedPaths`
- `./project-artifact-contract.md` —— 产物目录与写入范围契约
- `./skill-maintenance.md` —— 改完本包后如何自检、维护与沉淀
- `./official-self-test-task-suite.md` —— 160 条自测任务，其中多条直接考本文模板的字段填写
- `./experience-card-schema.md` —— 经验卡结构，本文「阶段增量报告」是它的输入
- `../triage/reproducible-evidence-playbook.md` —— 证据包规范与 `first divergence` 的判定
- `../deliver/delivery-gate-playbook.md` —— 交付闸门，决定哪些模板必填
- `../deliver/response-decode-playbook.md` —— `Decode chain` 一行的具体填法
- `../../../field-journal/_template.md` —— 脱敏 case 模板，含 `review_case.py` 字段契约说明
- `../../../field-journal/anonymization.md` —— 占位符总表与自动检测脚本
- `../../SKILL.md` —— 审查流程与四条 phase

---

## 源文档勘误（改编时修正）

1. 源文档 `## Contents` 目录块按改编规范删除。
2. 源文档「Sensitive data rule」一条也没指向本包的证据字段契约，读者无法判断「报告」与「证据目录」是同一套校验。改编补上了与 `../../../field-journal/_template.md` 及 `../../../case-review/scripts/review_case.py` 的对接，并写明 `--strict` 字段取值集合。
3. 源文档「Final delivery report」模板本身没有说明它的 `Verification` / `Known instability` / `Residual risk` 三段如何映射到脱敏 case 的字段。改编补上了映射关系与「先过 `--strict` 再写最终报告」的顺序约束。
4. 源文档通篇以 `references/xxx.md` 平铺路径引用同包文件；本包实际按 `references/<group>/` 分组。本文是 `references/contract/` 下的文件，所有交叉引用已改为实际相对路径，并逐一确认目标文件存在。
5. 源文档只说「不要把裸秘密写进报告」，没有给出**必须报告什么**的正向清单。改编把「名字 + 来源 + 范围 + 有效期 + 指纹」明确写成正向要求，避免脱敏过头导致无法交接。
6. 源文档的模板代码块里未区分「要填写的字段名」与「说明文字」。改编保持模板内部英文标签原样（它们是字段名），把说明全部移到模板外的中文段落，避免使用者误把说明当作字段。
7. 源文档 `Run path and cache` 提到 `js_reverse_cache/tasks/<task-id>/`，但没有说明该目录是否需要纳入 gitignore 或保留策略。改编补了「调查缓存」与「交付证明」的定位说明；缓存的保留范围仍由 `./project-artifact-contract.md` 决定，本文不重复规定。