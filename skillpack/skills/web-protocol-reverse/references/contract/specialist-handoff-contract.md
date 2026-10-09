# 专员交接契约（Specialist Handoff Contract）

> **来源声明**：本文改编自外部仓库 `aoyunyang/spider-king-skill`（MIT License）的 `specialist-handoff-contract.md`。原始内容为英文原文，此处译为中文并按本包六段式规范重排；技术术语保留英文原词并附中文，AI 检索时中英文均可命中。改编中修正了源文档的若干表述与失效引用（见文末「源文档勘误」）。
>
> **什么时候用**：某条聚焦路线或某个已安装的专员应当接管一个**已被证明存在**的拦路点（blocker）时。交接**收窄**工作范围，它**不放宽**目标 scope、权限、请求预算、运行时访问权或交付要求。
>
> **平台与本机状态**：本文是规程与 JSON schema，不依赖具体本机工具，交接契约本身无需实跑命令。但专员名按本包事实标注：源文档默认的专员家族 `camoufox-js-reverse`、`chrome-devtools`、`js-reverse` **本机均未挂载**，`iv8` **本机无**（社区运行时，PyPI 无发行版），`reqable` **本机无**。因此本机执行交接时，`requestedOwner` 只能填本包内置的聚焦路线（`python-collector` / `transport` / `static-ast` / `env-patch` / `pure-python-rebuild` 等），`fallbackRoute` 必须指向另一条可执行的本包路线 —— 详见 `../observe/local-mcp-environment.md`。

---

## 适用信号（Recognition signals）

出现下列任一情况，说明该走交接路线：

- 当前路线已**定位**一个具体拦路点（如「签名器算对了但 token 取不到」），且该拦路点需要**另一种能力**才能推进
- 需要执行目标方代码（`targetCodeExecution` 目前是 `blocked`），而当前工单尚未授权
- 需要浏览器 reconnaissance（`browserRecon: false` → 需要 `true`）
- 需要实时 replay（`liveReplay: false` → 需要 `true`）
- 需要账号 / 会话状态，而当前工单的 `accountOrSessionUse` 是 `none`
- 需要安装依赖（`dependencyInstall: blocked` → 需要授权）
- 需要可写模式（`writeMode: no-write` → 需要可写，且 `allowedPaths` 需要非空）
- **换所有者**：旧所有者已 `PARKED` / `RELEASED`，新所有者要进入 `TARGET_ACTIVE`
- 反过来：你是被交接方，收到一份 `request` 对象，需要按 `Return Shape` 交付

**不构成交接信号**的情况：当前路线只是「令人沮丧」或「想看看别的路线手册」。那种情况不交接，只在 `./provider-work-order.md` 的「路线规则」里停下并点名拦路点。

## 前置（Entry conditions）

### 交接之前必须完成的五步

1. **确认目标专员存在于当前能力快照（capability snapshot）中**。本机核对方式见 `../observe/local-mcp-environment.md`；若本机没有该专员，**不能**在 `requestedOwner` 里填它的名字。
2. **当专员不存在时，点名一个可执行的 Spider 回退（fallback）**。如果用户明确要求了那个缺失的专员 / 运行时，就把回退方案**摆出来请用户验收**，**不要**默默把它当成等价物 —— 「等价」是用户的判断，不是你的判断。
3. **在下一位所有者进入 `TARGET_ACTIVE` 之前，停放（park）或释放（release）当前同目标所有者。** 同一时刻只有一个家族拥有 `TARGET_ACTIVE`，且两族**绝不**出现在同一个并行工具批次里。
4. **把唯一的、不可重放的状态保存为 `RETAINED_EXCEPTION`**；**不要**为了让清理看起来干净就把它销毁。
5. **只用「任务本地路径 + 哈希」引用秘密**。**绝不**把原始 `Cookie`、`Authorization`、token、key、IV、账号或私有载荷值写进交接文件 —— 这与 `../../SKILL.md` 的证据纪律、`../../../field-journal/_template.md` 的脱敏要求同源。

### 落盘位置（与产物契约一致）

当**当前工单明确授权了这条确切路径**时，把 request 与 result 存进**同一个信封（envelope）**：

```text
<project>/js_reverse_cache/tasks/<task-id>/handoff.json
```

这个路径与 `./project-artifact-contract.md` 的「易失性证据」层级、`./provider-work-order.md` Write Guard 第 4 条完全一致 —— **不得**另起目录或另立命名。

**信封的生命周期规则**：初始写 `{"request": {...}, "result": null}`，返回后**只替换 `result` 成员**。
**绝不**追加第二个顶层 JSON 对象；**绝不**覆盖 `request`。

在 `writeMode: no-write` 或 `allowedPaths` 为空的情况下，把**同样的 request / result 字段**放在内存或用户回复里，**不要创建 `handoff.json`**。

## 步骤（Working method）

### 一、Request 形态（Request Shape）

从**当前提供方工单**复制 scope、permissions、budget 与 `allowedPaths`，然后**为专员收窄**它们。下面的取值是「无上游授权时」的保守默认值。**只有在**上游工单**已经授权了**该模式、**且**每个可写路径仍留在继承来的白名单内时，交接才可以把 `no-write` 改成可写模式。

信封的 `request` 成员：

```json
{
  "schemaVersion": 1,
  "taskId": "non-secret task identifier",
  "intakeMode": "live-target | artifact-only | continuation",
  "fromRoute": "current Spider route",
  "requestedOwner": "installed specialist or focused Spider route",
  "fallbackRoute": "executable Spider route",
  "reason": "one proved blocker",
  "scope": {
    "scheme": null,
    "host": null,
    "port": null,
    "routePrefix": "/proved-prefix",
    "allowedArtifacts": []
  },
  "permissions": {
    "browserRecon": false,
    "liveReplay": false,
    "accountOrSessionUse": "none",
    "targetCodeExecution": "blocked",
    "dependencyInstall": "blocked",
    "writeMode": "no-write"
  },
  "budget": {
    "requestsRemaining": 0,
    "retriesRemaining": 0,
    "websocketFramesRemaining": 0,
    "minDelayMs": 0,
    "concurrency": 1
  },
  "allowedPaths": [],
  "provenFacts": [],
  "evidence": [
    {
      "path": "task-relative path",
      "sha256": "64 lowercase hex characters",
      "proves": "one bounded claim",
      "capturedAt": "YYYY-MM-DDTHH:MM:SSZ"
    }
  ],
  "unknowns": [],
  "requestedOutput": "evidence | local-proof | code | blocker",
  "acceptanceTest": "one objective proof",
  "cleanupState": "PARKED | RELEASED | RETAINED_EXCEPTION"
}
```

**收窄规则**（硬性）：

- 未知或省略的权限 = blocked。
- **每一个**布尔、枚举、计数器、延迟、scope 字段与路径，都必须**等于或窄于**上游工单。宽于上游即非法交接。
- 专员只能消耗已记录的预算，只能写已记录的 `allowedPaths`。仅写 `task-cache-only` 而没有非空继承白名单，**不授予任何写权限**。
- `live-target` 模式的专员必须遵守与 Spider King **相同**的串行浏览器所有权与成对证据（paired evidence）规则。

### 二、Return 形态（Return Shape）

所有者返回下列对象，**且仅在获授权时**把它存为信封的 `result` 成员：

```json
{
  "status": "evidence | local-proof | code | blocked",
  "owner": "actual capability owner",
  "result": "bounded result or named blocker",
  "claims": [
    {
      "claim": "one conclusion",
      "evidenceSha256": ["supporting artifact hashes"],
      "verifiedAt": "YYYY-MM-DDTHH:MM:SSZ"
    }
  ],
  "artifacts": [],
  "fixedVector": "passed | failed | not-applicable",
  "liveReplay": "passed | failed | blocked | not-authorized",
  "budgetConsumed": {},
  "runtimeCleanupState": "RELEASED | PARKED | RETAINED_EXCEPTION",
  "residualRisks": [],
  "recommendedNextOwner": "Spider route or none"
}
```

### 三、`evidence[]` 与 field-journal 证据记录的对齐

交接里的 `evidence[]` 数组是**机器可读的证据指针**；`../../../field-journal/_template.md` 的「Evidence 链摘要（脱敏）」表格是**人读的一层**。两者描述同一批东西，必须能一一对上：

| 交接 `evidence[]` 字段 | field-journal / case-review 对应项 |
|---|---|
| `path` | `- artifact_path:`（case 内相对路径），或 `../../../field-journal/_template.md` 证据表里的「可复用命令模式」 |
| `sha256`（64 位小写十六进制） | `- content_hash: sha256:<64 hex>`，由 `../../case-review/scripts/review_case.py --verify-hashes` 校验 |
| `proves` | `- status: observed \| candidate \| validated \| false_positive \| accepted_risk` 中所声明的结论强度 |
| `capturedAt` | 证据表的时间列 |
| —（交接中无对应字段） | `- severity: critical \| high \| medium \| low \| info \| n/a` |
| —（交接中无对应字段） | `- repro_command:`（**必填**；离线场景须在 notes 中注明 offline） |
| `reason`（一个已证明的拦路点） | `- linked_workitem: WI-xxx`（须真实存在）—— **改编补入的映射** |

**具体做法**：当这次交接产出了需要独立留痕的证据目录（如 `../../../../examples/ctf-demo/evidence/E-001.md`）时，除了在 `evidence[]` 里写指针，还要按 `../../../field-journal/_template.md` 的契约块补一份 E-id 记录，并用下面的命令复核（`../../SKILL.md` 的 Phase 3 / Phase 4）：

```bash
# 本机 Python 3.12 可用；该脚本只读、无第三方依赖
D:\EXE\python\python.exe skillpack/skills/case-review/scripts/review_case.py work/<case> --verify-hashes --strict
```

字段不合规时 `--strict` 会 FAIL，此时**先修字段，再重跑**，不要先宣称交接完成。

## 判据（Verification checklist）

交接受入时，以下**全部**满足才算合格。前 5 条源文档有直接依据，标注 *（改编补入）* 的为改编时从硬性规则反推的量化判据。

1. `requestedOwner` 填的是**能力快照里真实存在**的专员 / 聚焦路线，不是臆想的名字；本机若确实没有该专员，`fallbackRoute` 已填一条**可执行**的本包路线。
2. *（改编补入）* `request` 的**每一个** scope / permission / budget / path 字段都**逐项 ≤ 上游工单**，不存在任何一项放宽；逐项 diff 可验证。
3. *（改编补入）* `writeMode` 从 `no-write` 改为可写时，能指出上游工单里**授权该模式的那一条**；`allowedPaths` 非空，且每一项仍在上游白名单内。
4. `evidence[]` 中**每条**都有 `path` 与 64 位小写 `sha256`，且 `proves` 是**一个有界的单项主张**，不是「整体搞定了」这类说法。
5. *（改编补入）* 信封结构合法：`request` 与 `result` 是**同一个** JSON 对象的两个成员；没有第二个顶层对象；`request` 未被覆盖；`result` 初始为 `null`、返回后才被整体替换。
6. `cleanupState` 取值 ∈ `PARKED | RELEASED | RETAINED_EXCEPTION`，且旧所有者确已 `PARKED` 或 `RELEASED` 之后新所有者才进入 `TARGET_ACTIVE`。
7. *（改编补入）* 若产出了独立证据目录，`review_case.py --strict` 退出码为 0，且每条 E-id 记录的 `repro_command` 已填（离线场景在 notes 注明）；`content_hash` 与 `artifact_path` 成对出现。
8. `result.status` 与实际交付物一致：`requestedOutput: blocker` 时不得报 `code`；`requestedOutput: evidence` 时不得报 `code`。
9. 每条技术性 `claims` 都引用了存在的 `evidenceSha256`；不存在「有结论无哈希」。
10. `runtimeCleanupState` 与 `request.cleanupState` 相容：若请求方要求 `RELEASED`，返回不得是 `PARKED` 而无说明。
11. *（改编补入）* 全文扫描无原始秘密值：无明文 `Cookie`、`Authorization`、token、key、IV、账号、私有载荷；秘密只以「路径 + 哈希」形式出现。
12. `liveReplay` 字段与授权一致：未授权时必须为 `not-authorized` 或 `blocked`，**不得**为 `passed`。

## 常见坑（Common traps）

- **把交接当成放宽**：以为「换个专员」就能顺便把 scope、预算、权限一起放大。交接只收窄。
- 专员不存在时，默默拿回退方案当等价物交差，而不请用户验收
- 往 `handoff.json` 里**追加**第二个顶层 JSON 对象，或返回时顺手覆盖了 `request`
- `writeMode: no-write` 状态下仍然创建了 `handoff.json`
- 摘要表里 `sha256` 写成大写十六进制、或长度不足 64 位（`review_case.py` 校验失败）
- `proves` 写成「已经完整还原了算法」这类无界主张
- 把原始 cookie / token / Authorization 值抄进信封、报告、fixture 或技能目录
- 旧所有者还没 `PARKED`，就让新所有者进 `TARGET_ACTIVE`；或两族同时出现在一个并行工具批次里
- 为了让清理表好看，销毁了唯一且不可重放的状态，而没有记 `RETAINED_EXCEPTION`
- 交接回来的结果用「helper 加载成功」「输出形状像」「HTTP 200」替代了请求的 oracle
- 把专员完成当成协议完成，跳过 Spider King 的最终交付门禁

## 相关（Related）

- `./provider-work-order.md` —— 交接的授权来源；scope / permissions / budget / allowedPaths 的上游定义
- `./project-artifact-contract.md` —— `handoff.json` 所在的产物层级与落盘红线
- `./experience-card-schema.md` —— 同属任务本地产物（`experience-candidate.json`）的 schema 风格，可对照
- `./report-templates.md` —— 交接结果最终进入报告时的模板
- `../observe/local-mcp-environment.md` —— 判据第 1 条的能力快照来源：本机有哪些专员 / 路线真实可用
- `../deliver/delivery-gate-playbook.md` —— Spider King 侧的最终验收门禁
- `../deliver/case-reuse-playbook.md` —— 判断某次交接结论是否值得沉淀
- `../triage/reproducible-evidence-playbook.md` —— `evidence[]` 条目的最低可复现标准
- `../triage/escalation-ladder-playbook.md` —— 「停下并点名拦路点」的标准做法
- `../principles/anti-patterns-playbook.md` —— 本文「常见坑」段的原则级对照
- `../state/session-contract-playbook.md` —— `accountOrSessionUse` 非 `none` 时的会话分层
- `../../../field-journal/_template.md` —— 脱敏 case 记录模板与 Evidence 链摘要表
- `../../../field-journal/anonymization.md` —— 交接材料落盘前的脱敏规范
- `../../SKILL.md` —— 证据字段契约与 `--strict` 审查流程

---

## 源文档勘误（改编时修正）

1. **源文档 `## Contents` 目录块指向英文锚点**。已删除，改为中文六段式结构下的自然导航。
2. **源文档未指明 `handoff.json` 属于哪一层产物**，读者容易另立目录。本文明确指向 `./project-artifact-contract.md` 的 `<project>/js_reverse_cache/tasks/<task-id>/` 易失性证据层，与 `./provider-work-order.md` 的 Write Guard 第 4 条对齐。
3. **源文档 `## Request Shape` 与 `## Return Shape` 引用 `experience-card-schema.md` 风格路径之外，无交叉引用**，但同批的 `./provider-work-order.md` 原文写的是扁平 `specialist-handoff-contract.md`。这类扁平写法会指向不存在的 `references/references/`。本文全部改为同目录 `./xxx.md`。
4. **源文档默认专员家族在本机不存在**。`camoufox-js-reverse`、`chrome-devtools`、`js-reverse` 本机一个都没挂载，`iv8` 本机无，源文档从未声明这些是必需项，其隐含前提是「存在一份已安装专员快照」。已在顶部与「前置」第 1、2 条就地标注，并要求 `fallbackRoute` 填一条本包内可执行路线。**枚举值本身保持原样未改**。
5. **源文档的 `evidence[]` 结构与本包 `../../case-review/scripts/review_case.py` 的证据字段契约不对齐**：交接侧有 `path`/`sha256`/`proves`/`capturedAt`，但**没有** `repro_command`（该脚本要求必填）、**没有** `severity`、**没有** `linked_workitem`。本文在「步骤」第三节补了一张对齐映射表，并明确标注 `reason → linked_workitem` 这一映射为**改编补入**（源文档未建立此联系，也未声称建立）。
6. **源文档把「同一时刻只有一个家族拥有 `TARGET_ACTIVE`」写在 `## Request Shape` 段末的一句从句里**，而这是全文最强的一条并发硬约束，位置极不显眼。本文将其提升为「前置」第 3 步的独立硬性步骤。
7. **源文档「验收」段的 6 条驳回条件**其实是全篇唯一的验收清单，但排在最后且以否定式罗列。本文在「判据」段把它转成 12 条可逐项核对的正向清单，其中源文档直接给出的驳回条件仍全部保留（第 2、3、4、9、11、12 条对应之）。
8. **源文档未提 `scripts/` 缺失问题**。本文**未引用任何 `scripts/*` 工具**（源文档这份文件本来也没引），避免留下失效路径。