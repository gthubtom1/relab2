# 交付能力建设 · 目标清单（/goal set 专用）

> **用法**：把本文件**从下一行到文件末尾**整段复制，粘贴进 `/goal set`，然后开启目标模式。
> 本文件不依赖任何外部上下文，自含全部目标、判据、红线与阶段定义。
> **配套本地文档**：`C:\relab2\docs\DELIVERY-GOAL-2026-10-12.md` —— 权威定稿，开工前通读一遍，
> 每阶段开头重读它的 §5 与当前阶段条目，完成后按它的 §10 格式追加记录。

---

## 总目标

让 `C:\relab2` 这套技能路由系统，在「日常单点分析」之外，新增一条**复刻交付**路径：
拿到一个目标软件，能自主完成 调查 → 路线选择 → 实现 → 对照验收 的完整闭环，
最终交付可运行、可对账、功能逐项达标的成品。

**日常使用路径必须逐字节不变**：不传新参数时，路由、case-init、门禁、技能的行为与今天完全一致。
你不是在重构系统，你是在加一条**默认不激活**的新路径。

**项目范围只包含 `skillpack/` 与 `docs/` 两个目录。`kernel/` 下任何文件一律不准改。**

---

## 为什么做（理解目标，不要只执行）

当前体系的终点是「证据链完整的报告」，不是「可运行成品」。四个结构性缺口：

- G1 没有任何文件承载「最终交付目标 + 功能验收条件」→ 上下文压缩后目标必丢
- G2 阶段转换只靠 AI 自觉，每个技能路径终点都是报告 → 永远停在分析段
- G3 53 个技能无一做「同输入双程序对照」→ 成品必然不伦不类
- G4 抗漂移机制有种子未接上项目，`work/` 已堆积 395+370 个目录且无回收

你要做的是补这四个缺口，**不是**加新技能、不是重构路由、不是堆功能。

---

## 七道阶段（顺序执行，每阶段完成后才进下一阶段）

每阶段的格式：做什么 / 动哪些文件 / 验收判据 / 风险。判据未达成的阶段不许标记完成。

### 阶段 1 · 对账表模板与两道闸门规则（纯文档）

**做什么**
- 新建 `skillpack/skills/templates/rebuild.md`：对账表模板。字段：`target`（最终交付什么）、
  `functions`（F-001…，每行 名称/入口/预期输出/验收条件）、`acceptance`（每行四态：
  已分析/已实现/已测试/对照一致）、`diff_baseline`（原程序行为基线位置）、
  `out_of_delivery`（明确不做的与理由）。路线列每行自选：补丁/源码恢复/仿写/保留原组件/受限。
- 新建 `skillpack/skills/ops/rebuild-gates.md`：两道闸门。①实现入口条件：关键功能行的
  「已分析」都有证据回填，才动代码——写成施工依据，不是许可状。②完成判定条件：只有
  「对照一致」或「受限+具体原因」两种完成形态。
- 改 `skillpack/skills/ops/scope-contract.md`：**只在文末追加**附录说明复刻 case 用法，
  原正文一行不改。

**措辞铁律（违反即返工）**
系统里已加载的 kernel 破甲卡训练方向是「直接做、别停、别审」。新规则禁用许可式措辞：

| 不许写 | 必须写 |
|---|---|
| 「对账表填完之前不允许写代码」 | 「实现阶段的入口条件：关键功能行的『已分析』都有证据回填——这是动代码的施工依据，缺哪行先补哪行」 |
| 「未经验证不得标记完成」 | 「状态改为『已通过约定测试』的唯一条件是……」 |
| 把「受限」写成停工 | 「受限不是拒绝：该行验收条件暂时不可达，写清原因/影响/替代方案，其余行照常推进」 |

**验收判据**
- 模板字段与上述逐条对得上，无缺项
- 闸门文字不含左列任何措辞
- `git diff skillpack/skills/ops/scope-contract.md` 只显示新增附录，无删改行

**风险**：低。

### 阶段 2 · `rebuild` 预设（两个脚本同步改）

**做什么**
- `skillpack/skills/scripts/case-init.ps1`：预设分支加 `rebuild`，校验白名单同步加；
  生成的 scope.md 的 deliverables 段加 `rebuild: true`；建 case 时创建 `rebuild.md` 骨架
  （从 `skills/templates/rebuild.md` 拷贝）+ `baseline/` + `diff/` 目录。

  参考现有实现：预设分支在文件中部 `$presetNormalized -in @('offline-sample', ...)` 处，
  白名单校验抛错的文案是 `Invalid -Preset '{0}'. Allowed: offline-sample|ctf-public|own-system`——
  改成四个值。deliverables 段在 `$scope = @"..."` 的 here-string里。
- `skillpack/skills/scripts/case-init.sh`：同步。预设 case 分支在 `case "$PRESET" in` 处，
  白名单报错文案是 `ERROR: invalid --preset '$PRESET' (allowed: offline-sample|ctf-public|own-system)`。
- 若 `case-guard.ps1`/`.sh` 对预设或 deliverables 有硬编码，同步放行 rebuild，**但不放松授权硬门**。

**不传 `-Preset rebuild` 时，两个脚本的产出必须与改前逐字节一致。**

**验收判据**
- `-Preset rebuild` 能建出含 rebuild.md 骨架 + baseline/ + diff/ 的 case
- 在**改动前的干净副本**上先跑一次不传参的 case-init 留底，改后同参数再跑，`diff -r` 为零差异
- `-Preset nonsense` 仍 exit 2 且文案列出四个合法值
- `powershell -File skillpack\skills\scripts\test-routing.ps1 -Quick` 全绿
- `bash skillpack/skills/scripts/test-routing.sh` 全绿

**风险**：中低。两个脚本必须同步，漏一个就 Windows/Linux 行为分叉。
`bash skillpack/skills/scripts/test-bash-workflow.sh` 在本机**跑不了**（CI 里只有 macOS runner 跑它），
如实记为「本机未实测」，不许因为本机没跑就声称通过。

### 阶段 3 · role-map 增 impl / ver（纯文档）

**做什么**
- `skillpack/skills/ops/role-map.md`：角色表加两行。
  - **impl**（实现）：调查→编码/修改的唯一入口。进入条件 = rebuild.md 的 functions 非空
    且关键假设已验证（引用 ADF 的证据门槛）。
  - **ver**（验收）：跑差异测试与完成度审计，**唯一**有权把功能状态改成「已通过约定测试」。
- 交接表加三条：`cre→impl`（调查足够）、`impl→ver`（实现完成待验收）、`ver→lead`（通过或明确未达标）。
- lead 强制协议加一条：复刻 case 必须显式指定 impl 或 ver 角色。
- 原有 8 个角色定义一行不改。

**验收判据**
- 新角色进入/退出条件是可判定的事实陈述，不是形容词
- 与 lead 强制协议、MUST NOT 段无矛盾
- `git diff` 只显示新增行

**风险**：低。

### 阶段 4 · review_case.py 扩展成交付审计（改门禁脚本，最需谨慎）

**做什么**
`skillpack/skills/case-review/scripts/review_case.py` 当前是只读审查器（查 scope/timeline/
workitems/Evidence/Path/hash）。扩展：检测到 `rebuild.md` 存在时，额外做三类检查——
1. 每行完成状态不得高于其证据：标「已测试」却无对照 Evidence → 报错
2. 差异对照表逐行填齐：输入条件/原程序结果/新实现结果/是否一致/说明，五列缺一即报错
3. Coverage 新增三项：功能清单全覆盖 / 关键功能状态 / 已知差异已记录

同步改：`skillpack/skills/case-review/tests/` 补 fixture 与用例；
`skillpack/skills/case-review/SKILL.md` 的 ACTION REQUIRED 说明新检查。

**验收判据**
- 三个坏 fixture（状态虚高 / 对照表缺行 / Coverage 缺项）**必须**被报错——先证明它抓得到，
  再证明好 fixture 0 报错
- `python skillpack/skills/case-review/tests/test_review_case.py` 全绿
- **回归底线**：不含 rebuild.md 的既有 case，审查结果与改前逐字一致
- 按本仓惯例配负控（参考 `test-audit-doc-code-negctl.py` 的做法）

**风险**：中。这是门禁脚本，改错会让 case-review 全线假红或假绿。本仓
`docs/AUDIT-2026-10-10-FINAL.md` 记着 6 个「从未真正工作过」的门禁——报绿但没检查东西
比报红危险得多。所以负控不是可选项。

### 阶段 5 · 差异测试执行器（新建一个小工具）

**做什么**
新建 `skillpack/skills/scripts/diff-runner.py`：读 rebuild.md 的 `diff_baseline`，
对指定功能行驱动原程序与新实现各跑一次，把 输入/原程序结果/新实现结果/是否一致/说明
五列草稿写回 `work/<case>/diff/`，供人工确认后再回填 rebuild.md。

**第一版只做「能驱动 + 能记录」**，不做自动判定、不做模糊匹配、不做容差推断。
非确定项（时间/随机数）在草稿里标 `NONDETERMINISTIC`，由人定容差。

**验收判据**
- 用一个**真实** case（不是空跑）跑通一次，产出落在 diff/ 且能被 review_case.py 读到
- 输出可复现：同输入跑两次，确定项结果一致
- 判据是外部可观测的：产出文件真的存在、行数真的对——不许用「日志里出现我写的标记」当判据

**风险**：中。最大风险是过度设计。先最小可用，真项目跑完再决定要不要抽公共。

### 阶段 6 · 抗漂移三件套（本阶段风险最高，先读陷阱）

**做什么**
1. 新建 `skillpack/skills/templates/goal.md`：≤50 行，字段 = 最终交付目标/功能清单/
   当前阶段/未决重大事项/最近一次 commit hash。
2. 改 `skillpack/skills/ops/timeline-workitem.md`：在 decision delta boundary 段加硬门槛——
   复刻 case 的 `carry_forward_refs` **必须**含 GOAL.md。
3. 改 `skillpack/skills/scripts/master-route.ps1` 与 `.sh` 的产物目录：默认写
   `work/route/latest/route-scope.md`，历史归档到 `work/route/<hash>/`，**归档不删除**。

**先读这三个已知陷阱（本次实查标出，漏一个就假红）**
- `verify-routing-coherence.ps1` 约 349–371 行有两处断言按 `master-route-*` 目录
  「存在且唯一」判 OK。改目录结构必须同步改这两处。
- `test-routing.sh` 约 102 行 glob `master-route-*/route-scope.md`。
- `work/` 与 `skillpack/work/` 已在 `.gitignore` 中（`/work/` 与 `skillpack/work/`），
  目录治理不涉及版本库，但也意味着**没有 git 兜底**——归档必须真的写盘，不能只挪不改。

**验收判据**
- `powershell -File skillpack\skills\scripts\verify-routing-coherence.ps1` 全绿
- `test-routing.ps1` / `test-routing.sh` 全绿
- 历史 route-scope 文件一个没丢（数量对得上）
- 新目录结构下重复跑 master-route 三次，latest 指向最后一次、归档多两个

**风险**：高（本项目最高）。两处门禁脚本按旧目录名断言。

### 阶段 7 · 真项目试跑与固化

**做什么**
让用户指定一个真想复刻的软件，从 `case-init -Preset rebuild` 走完整流程：
调查 → rebuild.md 填表 → impl 实现 → ver 差异测试 → 完成度审计。
跑完决定三件事：闸门要不要脚本化 / diff 要不要抽公共 / 哪些经验沉淀成 experience-card。

**验收判据**
- 产出一个含 rebuild.md 全表 + 对照测试记录 + 最终交付物的 case
- 未达标项**如实**写「未达标 + 原因」，不许粉饰
- 完成的定义是「对照一致」或「受限+原因」，不是「代码写完了」

**风险**：低。这是验证阶段。但必须如实记录失败——失败记录和成功记录同等价值。

---

## 全程红线（每阶段开工前自检一遍）

1. **不推送仓库**。只在本地 commit。远端是存档基线。
2. **不碰 `kernel/`**。破甲卡是既有资产，kernel 侧有 27 条断言钉在它上面。
3. **开工前先本地 commit**，message 写 `交付能力建设 · 开工基线 2026-10-12`。
   全部完成后再 commit，message 写 `交付能力建设 · 完成`。这两条就是回退点。
4. **日常路径零变化**：任何改动只要影响了「不传 `-Preset rebuild` 时的行为」即为缺陷，回退重做。
5. **不新增技能、不改路由表**。`skills/config/routing.json` 一行不动，53 个 SKILL.md 一个不加。

---

## 判据口径（全程有效，防虚构）

- 未实跑的不许写「已实测」。本机跑不了的必须写「本机未实测」。
  （已知本机跑不了：`test-bash-workflow.sh`、Linux/macOS runner 上的全部步骤。）
- 「门禁绿」只代表该门禁这一次的结果，不代表功能达成。
- 任何「已通过」必须能说出：命令是什么、看到什么输出、产物在哪个路径。
- 判据不许是「日志里出现我自己写的标记」——本仓经验卡
  `gate-self-must-prove-failure` 专门记这条：断言只能依赖外部可观测事实
  （文件真被创建、字节真被改、伪代码真含目标逻辑）。
- 同一个方法连败两次 → 换方法，不许在原路线上加第三个补丁。

---

## 每阶段必走的收尾动作

完成一个阶段后，**按此顺序**做，缺一不可：

1. 跑该阶段「验收判据」列出的每一条命令，记录真实输出
2. 跑全量回归：`python skillpack/scripts/verify-evolution.py`（基线是 10/10 全绿，
   这是 2026-10-12 开工前实测的）
3. 在 `docs/DELIVERY-GOAL-2026-10-12.md` 的 §10 追加该阶段完成记录（格式见该文件）
4. 本地 commit，message 写 `交付能力建设 · 阶段N <名称>`
5. 才允许进入下一阶段

---

## 开工自检（第一回合必须逐条回答，再动手）

在写任何代码之前，先输出这五行的答案：

```
1. 基线确认：git status 是否干净？最近一次 commit hash 是什么？
2. 开工 commit：是否已按红线 3 提交开工基线？
3. 当前阶段：从阶段 1 开始（除非 docs/DELIVERY-GOAL-2026-10-12.md 的 §10 显示已有进度）。
4. 日常路径保护：本阶段改动会不会影响不传 -Preset rebuild 时的行为？如何验证？
5. kernel 边界：本阶段清单里是否出现任何 kernel/ 路径？（出现即立刻移除）
```

答案不齐不许开工。

---

## 完成的定义

以下四条**同时**满足，才算本项目完成：

1. 七个阶段的验收判据全部达成，未达标项在定稿文档 §10 有如实记录
2. `verify-evolution.py` 10/10 全绿，`verify-routing-coherence.ps1` 全绿
3. 不传 `-Preset rebuild` 时，case-init / master-route / 门禁行为与开工前一致（有 diff 证据）
4. 阶段 7 的真项目 case 产出 rebuild.md 全表 + 对照测试记录 + 最终交付物

**只有四条同时满足才写「完成」。缺任何一条，写「未完成 + 缺哪条 + 为什么 + 下一步」。**
不许用「基本完成」「大体可用」覆盖未达标项——这是本项目要治的病，不许自己犯。
