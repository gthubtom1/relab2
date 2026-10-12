# 交付能力建设 · 权威定稿（2026-10-12）

> **这份文件的性质**：本项目的唯一权威定稿。新对话开工、每阶段开头、遇到争议时，
> 以本文件为准。本文只写「目标、判据、为什么」；具体怎么做由执行方在对应阶段展开。
>
> **配套文件**：`docs/GOAL-PROMPT-2026-10-12.md`（可直接整段复制进 `/goal set` 的目标清单）。
> 两份的分工：
> - 本文件 = 权威定稿，每阶段开头重读 + 完成记录追加在 §10
> - 目标清单 = 纯命令文本，驱动目标模式持续执行
>
> **本文所有事实性陈述都来自 2026-10-12 对 `C:\relab2` 的实查**（文件逐个读过、目录逐个列过、
> 脚本逐行看过）。标 `[推断]` 的是推断，未实跑的一律写「未实测」。

---

## 0. 一句话目标

**让现有体系在「日常单点分析」之外，新增一条「复刻交付」路径：拿到一个目标软件，
能自主完成 调查 → 路线选择 → 实现 → 对照验收 的完整闭环，最终交付一个可运行、
可对账、功能逐项达标的成品。日常使用路径逐字节不变。**

---

## 1. 为什么必须做（用户原话痛点 + 结构性根因）

用户原话归纳（来自 7 段需求 TXT）：

1. 「分析了很多、折腾很久，最后没有得到真正可用的成品」
2. 「希望 AI 从一开始就以最终交付一个真正可用的程序为目标」
3. 「长时间执行中上下文不断增长、压缩后信息丢失、任务逐渐偏离原始目标」
4. 「不要为了增加能力而重复建设」「不要急于重构」

结构性根因（本次调查结论，不是猜的）：

| 痛点 | 结构性原因 | 证据 |
|---|---|---|
| 成品四不像、功能不完整 | 体系终点是「报告」，不是「可运行成品」 | 53 个 SKILL.md 全是分析技能；R20=docs-generator 是终点；R48（交付编排）自己写明「安全/逆向/真实部署动作交还 canonical」——而 canonical 的终点就是报告 |
| 目标漂移、压缩后丢失 | 没有任何文件承载「最终交付目标 + 功能验收条件」 | `ops/scope-contract.md` 的 deliverables 只有 `report/field_journal/diagrams/timeline` 四个布尔；`workitems.md` 的 Coverage 勾到「Report exported」为止 |
| 做了半成品就宣布完成 | 没有区分「已分析 / 已实现 / 已测试 / 对照一致」四态的机制 | `case-review` 审的是 hash 与 Evidence 可追溯性，不是行为等价 |
| 与原程序行为是否一致无人验证 | 没有一个技能做「同输入双程序对照」 | 53 个技能逐个看过，无此能力 |

---

## 2. 现状底册（本次实查，改动前必须以此为基线）

### 2.1 三层结构

| 层 | 位置 | 规模（实测） | 职责 |
|---|---|---|---|
| 规则层 | `RULES.md` / `RULES_zh.md` | 27.4KB / 37.2KB | 激活与行为链唯一事实源 |
| 路由层 | `skills/config/routing.json` | 51 条路由（R0–R52） | 按「任务类型」选 PRIMARY |
| 契约层 | `skills/ops/` | 10 份 | scope（授权门）、Evidence→Finding→Path、timeline/workitems、role-map、ADF 决策框架 |
| 能力层 | `skills/*/SKILL.md` | 53 个（467KB 合计） | 各领域分析方法 |
| 门禁层 | 38 条 | 25 条在 `ci-gates.json`、其余在 ci.yml 裸 run | 回归防线 |

### 2.2 关键事实

- `master-route.ps1` 每条 hint 命中规则计分，priority 数组决胜；未命中回退 R0
- `case-init.ps1/.sh` 三个预设：`offline-sample` / `ctf-public` / `own-system`；
  `-Preset` 传错直接 exit 2
- `case-guard` 不因 `-Force` 放过授权硬门
- `review_case.py` 是只读审查器，查 scope/timeline/workitems/Evidence/Path/hash
- `ops/role-map.md` 有 8 个角色 + lead 强制协议 + 交接表
- `ADF`（`ops/analysis-decision-framework.md`）R4*：Finding 升 validated 需 ≥2 独立证据
- `re-agent-workflow.md` 四阶段（triage→static→dynamic→synthesis）止于 synthesis
- `license-keygen/` 的 L1–L5 验收层级是全包做得最彻底的单点闭环范例
- `timeline-workitem.md` 已定义 `decision_delta` + `carry_forward_refs`（抗漂移正确种子，未强制）
- `experience-card.py` 7 张卡 + 检索 + 晋级门全通
- `ctxiso/` 已有 pack/read/compact 上下文隔离侧车
- kernel 侧 `04-console/cards/base/space-bunny.md` 是破甲卡（406 行），管单次回复纪律

### 2.3 文档门禁口径（写新文档前必须知道，否则一进去就假红）

| 门禁 | 扫描范围 | 新文档放哪安全 |
|---|---|---|
| `check-fences.py` | `skillpack/skills` 下全部 md，查代码围栏配对 | `docs/` 不被扫，随便写 |
| `audit-doc-code.py` | 默认 `skillpack/skills`，逐个编译代码块 | `docs/` 不被扫 |
| `verify-doc-links.py` | `git ls-files` + 未跟踪普通文件；`docs/**` 属 **active**（必须 0 断链） | 文档内 markdown 链接必须指向真实存在文件；用行内代码写路径则不产生链接 |
| `scan-leaks.ps1` | md/txt/json 查敏感信息 | 不写密钥、真实 token |
| `verify-doc-facts.ps1` | 只查 RULES.md / RULES_zh.md / SKILL.md 三处的 capability 清单与端口 | 新文档不在这三个文件就不触发 |

---

## 3. 四个缺口（本项目建设目标）

| # | 缺口 | 后果 | 对应建设项 |
|---|---|---|---|
| G1 | 没有「交付契约」落点 | 目标必漂移，压缩后无锚 | 建 `rebuild.md` 对账表 + `GOAL.md` 目标锚 |
| G2 | 没有「阶段推进器」 | 永远停在分析段 | `role-map` 增 impl / ver 两个编排角色 |
| G3 | 差异测试能力为零 | 成品必然不伦不类 | 差异测试执行器（harness + Evidence 回填） |
| G4 | 抗漂移未接上项目 + 工作区膨胀 | 会话越久垃圾越多 | decision_delta 强制继承 GOAL.md + `work/` 回收 |

---

## 4. 已有资产（不许重复建设，逐条核对过）

| 资产 | 现状 | 本项目的复用方式 |
|---|---|---|
| Evidence→Finding→Path + `append-evidence.ps1` + `review_case.py` | 成熟 | 「功能 F-001 已完成」= 一条 Finding，按 ADF-R4* 绑 ≥2 独立证据 |
| ADF 决策框架 R1–R81 | R4* 已定证据门槛 | 完成状态判定的现成规则源 |
| `license-keygen` 的 L1–L5 验收层级 | 单点闭环最彻底 | 项目级完成度状态机的范例模板 |
| `decision_delta` / `carry_forward_refs` | 已定义未强制 | 抗漂移正确种子 |
| `experience-card` 体系 | 7 张卡 + 晋级门 | 承载「不得把已实现未测试标为完成」类规则 |
| `ctxiso` pack/read | 已工作 | 项目状态包载体 |
| `case-review/review_case.py` | 只读审查器 | **扩展它**读 `rebuild.md`，不新建审查器 |
| `community/delivery`（R48） | 只做编排和验收 | 编排语义的上游参考，动作仍回 canonical |

---

## 5. 设计方案（四件套）

### 5.1 对账表 `rebuild.md`（核心）

case 目录内新增，一行一个功能，**路线每行自选**（补丁 / 源码恢复 / 仿写 / 保留原组件 / 受限）：

```
target:          最终交付什么
functions:       F-001… 每行 名称/入口/预期输出/验收条件
acceptance:      每行四态——已分析 / 已实现 / 已测试 / 对照一致
diff_baseline:   原程序行为基线样本位置
out_of_delivery: 明确不做的部分与理由
```

一张表同时解决：目标漂移（进度必须引用行号）、半成品冒充（四态分离）、多路线混合（每行独立）。

### 5.2 两个编排角色（改 role-map，不加新技能）

- **impl**：调查→实现的唯一入口。进入条件 = rebuild.md 的 functions 非空且关键假设已验证
- **ver**：跑差异测试与完成度审计。唯一有权把状态改成「已通过约定测试」的角色

### 5.3 差异测试执行器

`work/<case>/diff/` 目录 + 通用 harness（同输入驱动原程序与新实现，逐项比输出/文件/状态/错误码，
非确定项先约定容差再比）+ 结果回填 rebuild.md 与 Evidence。第一项目现场写，跑完再决定是否抽公共。

### 5.4 抗漂移与工作区治理

- `GOAL.md` 项目目标锚（case 根，≤50 行）：最终交付目标、功能清单、当前阶段、未决重大事项
- `carry_forward_refs` **必须**含 GOAL.md 写成硬门槛
- `master-route` 产物改写入 `work/route/latest` + 历史哈希归档；测试残留按 case 归属

### 5.5 措辞纪律（关键，写规则文字时必须遵守）

现有 kernel 破甲卡的训练方向是「直接做、别停、别审」。因此新规则**禁用许可式措辞**：

| 禁用 | 改用 |
|---|---|
| 「对账表填完之前**不允许**写代码」 | 「实现阶段的入口条件：关键功能行的「分析完」都有证据回填——这是动代码的施工依据，缺哪行先补哪行」 |
| 「未经验证的功能**不得**标记完成」 | 「状态改成「已通过约定测试」的唯一条件是……」 |
| 「**受限** = 拒绝推进」 | 「**受限**不是拒绝：该行验收条件暂时不可达（如依赖服务拿不到），写清原因/影响/替代方案，其余行照常推进」 |

---

## 6. 与 kernel 破甲卡的关系（先回答这个，避免误判为冲突）

**结论：不冲突，管两层不同的事。**

| | 破甲卡（kernel） | 复刻交付（本项目） |
|---|---|---|
| 管什么 | 单条回复长什么样 | 整个项目推进到哪了 |
| 要求 | 每条回复必须有完整交付 | 每个功能必须「对照一致」才算完 |
| 跨度 | 一次生成（约 180 秒） | 几十次回复 |

破甲卡 §7 SCOPE 已含「software engineering and delivery」；§12 交付下限要求每条回复都有真东西。
二者同向：都反对假完成。破甲卡管不到跨回复的账，正是本项目的建设内容。

**硬边界：本项目建设只动 `skillpack/` 与 `docs/`，绝不改 `kernel/` 下任何文件。**

---

## 7. 分阶段实施清单

每阶段格式：**做什么 / 为什么 / 动哪些文件 / 验收判据 / 风险**。

### 阶段 1 · 对账表模板与两道闸门规则（P0，纯文档）

**做什么**：写 `rebuild.md` 模板（含 §5.1 全部字段 + §5.5 措辞纪律）；写两道闸门的规则文字
（①实现入口条件 ②完成状态判定条件）；把「复刻 case」的使用方式写进 `ops/scope-contract.md` 的附录。

**为什么**：这是撬动其余全部的地基；纯文档零风险，先让措辞和字段被确认。

**动哪些文件**：
- 新增 `skills/templates/rebuild.md`
- 新增 `skills/ops/rebuild-gates.md`（两道闸门 + 措辞纪律）
- 改 `skills/ops/scope-contract.md`（加附录，不改原正文任何一行）

**验收判据**：模板字段与 §5.1 逐条对得上；闸门文字无 §5.5 左列措辞；scope-contract 原有内容 diff 为空
（除新增附录）。

**风险**：低。唯一风险是措辞被破甲卡误读为「又要走手续」——按 §5.5 写即可。

### 阶段 2 · `rebuild` 预设（P0，两个脚本各十几行）

**做什么**：`case-init.ps1` / `case-init.sh` 加 `-Preset rebuild`。不传参时行为逐字节不变。

**为什么**：让「复刻 case」有正式入口，而不是靠人手写目录。

**动哪些文件**：
- `skills/scripts/case-init.ps1`（预设分支 + 校验白名单 + scope 的 deliverables 段加 `rebuild: true`）
- `skills/scripts/case-init.sh`（同步）
- `skills/scripts/case-guard.ps1` / `.sh`（若 preset 需过 guard，同步放行 rebuild）

**验收判据**：
- `-Preset rebuild` 建出的 case 含 `rebuild.md` 骨架 + `baseline/` + `diff/` 目录
- 不传 `-Preset` 时 `case-init` 的产物与改前逐字节一致（先在干净副本上跑改前版本留底，再对比）
- `-Preset <错值>` 仍 exit 2
- `bash skills/scripts/test-routing.sh` 与 `skills/scripts/test-routing.ps1 -Quick` 全绿

**风险**：中低。两个脚本必须同步改，漏一个就 Windows/Linux 行为分叉。bash 侧预设白名单改完
要重跑 `test-bash-workflow.sh`（CI 里只有 macOS runner 会跑，本机跑不了——这条如实记为「本机未实测」）。

### 阶段 3 · role-map 增 impl / ver（P0，纯文档）

**做什么**：`ops/role-map.md` 角色表加两行 + 交接表加 `cre→impl`、`impl→ver`、`ver→lead` 三条；
lead 强制协议加一条「复刻 case 必须指定 impl 或 ver」。

**为什么**：现在阶段转换只靠 AI 自觉，每个 PRIMARY 技能路径终点都是报告。

**动哪些文件**：
- `skills/ops/role-map.md`（加，不改原有 8 个角色定义）

**验收判据**：新角色与既有 lead 协议不矛盾；交接条件可判定（有明确进入/退出条件，不是形容词）。

**风险**：低。

### 阶段 4 · review_case.py 扩展成交付审计（P1，改一个脚本）

**做什么**：让 `review_case.py` 在发现 `rebuild.md` 时额外检查：
① 每行完成状态不得高于其证据（标「已测试」但无对照 Evidence → 报错）
② 差异对照表逐行填齐（输入/原程序结果/新实现结果/是否一致/说明）
③ 新增 Coverage 三项：功能清单全覆盖 / 关键功能状态 / 已知差异已记录

**为什么**：这就是「防止做一半就宣布成功」的机制，且完全复展现成只读审查器形态——不新建工具。

**动哪些文件**：
- `skills/case-review/scripts/review_case.py`
- `skills/case-review/tests/`（补 fixture + 用例）
- `skills/case-review/SKILL.md`（ACTION REQUIRED 说明新检查）

**验收判据**：
- 构造三类坏 fixture（状态虚高 / 对照表缺行 / Coverage 缺项）必须被报错
- 好 fixture 必须 0 报错
- `python skills/case-review/tests/test_review_case.py` 全绿
- 既有 case（无 rebuild.md）行为不变——这条是回归底线

**风险**：中。改的是门禁脚本，改错会让 case-review 门禁全线假红或假绿。必须配负控
（照本仓惯例：`test-audit-doc-code-negctl.py` 的做法——先证明它能抓到坏状态）。

### 阶段 5 · 差异测试执行器（P1，新建一个小工具）

**做什么**：`skills/scripts/diff-runner.py`（或放 `case-review/scripts/`）——读 rebuild.md 的
diff_baseline，对指定功能跑原程序与新实现，产出对照表草稿写回 `work/<case>/diff/`。

**为什么**：G3 是能力真空。但**第一版只做「能驱动 + 能记录」**，不做花哨的自动判定。

**动哪些文件**：
- 新增 `skills/scripts/diff-runner.py`
- `skills/AGENTS` 或对应 SKILL.md 登记用法

**验收判据**：用一个真实 case 跑通一次（不是空跑）；产出落在 diff/ 且能被 review_case 读到。

**风险**：中。最大风险是「过度设计」——先做最小可用版，跑完一个真项目再决定要不要抽公共。

### 阶段 6 · 抗漂移三件套（P1）

**做什么**：
① `GOAL.md` 模板（≤50 行，字段：最终交付目标/功能清单/当前阶段/未决重大事项/上次 commit）
② `timeline-workitem.md` 的 decision delta boundary 加硬门槛：「复刻 case 的 `carry_forward_refs`
   必须含 GOAL.md」
③ `master-route.ps1` / `.sh` 产物目录治理：默认写 `work/route/latest/`，历史归档到 `work/route/<hash>/`

**为什么**：直接对应用户痛点 3（上下文压缩后丢失）。GOAL.md 是压缩后第一个回读的锚。

**动哪些文件**：
- 新增 `skills/templates/goal.md`
- 改 `skills/ops/timeline-workitem.md`（加硬门槛段）
- 改 `skills/scripts/master-route.ps1` + `.sh`（输出目录逻辑）
- 可能牵连：`verify-routing-coherence.ps1:349-371` 有两处**按 `master-route-*` 目录存在且唯一**
  判 OK 的逻辑——改目录结构必须同步改这两处，否则该门禁假红

**验收判据**：
- `verify-routing-coherence.ps1` 全绿（这是改目录结构后最容易踩的雷，已提前标出）
- `test-routing.ps1` / `test-routing.sh` 全绿（`test-routing.sh:102` 也 glob `master-route-*/route-scope.md`）
- 老目录里的历史 route-scope 不被删（归档而非清理）

**风险**：高（本阶段最高）。两处门禁脚本按旧目录名断言，漏改任一处 = 假红。

### 阶段 7 · 真项目试跑与固化（P2，证据驱动）

**做什么**：挑一个用户真想复刻的软件，从 case-init -Preset rebuild 走完整流程。
跑完再决定：闸门要不要脚本化 / diff 要不要抽公共 / 哪些经验该沉淀成 experience-card。

**为什么**：前 6 阶段都是设计，只有真跑过才知道哪里多余、哪里还缺。

**验收判据**：产出一个含 rebuild.md 全表 + 对照测试记录 + 最终交付的 case。
未达标项如实写「未达标 + 原因」，不许粉饰。

**风险**：低（这是验证阶段，不是生产阶段）。但必须如实记录失败。

---

## 8. 三道红线（违反即回退）

1. **不推送仓库**。只在本地 commit。远端仓库是存档基线，污染了回退成本极高。
2. **不动 `kernel/` 下任何文件**。破甲卡是既有资产，改它有 27 条断言会响（见 kernel TASKBOARD 记载）。
3. **开工前先本地 commit 一次**，备注写清楚「交付能力建设 · 开工基线 <日期>」；
   完成后 commit 一次，备注写清楚「交付能力建设 · 完成」。两次 commit 就是回退点。

---

## 9. 判据口径（防虚构，本仓铁律）

- 未实跑的不许写「已实测」。本机跑不了的（如 `test-bash-workflow.sh` 只在 macOS runner 跑）
  必须写「本机未实测」。
- 「门禁绿」只代表该门禁这一次的结果，不代表功能达成。本仓 `AUDIT-2026-10-10-FINAL.md`
  记着 6 个「从未真正工作过」的门禁——报绿但内部没检查东西比报红危险得多。
- 任何「已通过」必须能说出：用的什么命令、看到什么输出、产物在哪。
- 判据不许用「日志里出现我自己写的标记」（见经验卡 `gate-self-must-prove-failure`）。

---

## 10. 完成记录（追加，勿改历史）

> 每完成一个阶段，在此追加一段。格式固定，便于任何人接手时一眼看到进度。

```
### 阶段 N · <名称> · <YYYY-MM-DD HH:mm>
- 做了什么: <一段话>
- 改了哪些文件: <列表>
- 验收命令与结果: <命令 + 真实输出摘要>
- 门禁结果: <跑了哪些、绿/红、红的原因>
- commit: <hash + message>
- 未达标/遗留: <如实写，没有就写「无」
```

（以下为记录区，暂空）
