# 版本更新融合 · 目标清单（/goal set 专用）

> **用法**：把本文件**从下一行到文件末尾**整段复制，粘贴进 `/goal set`，然后开启目标模式。
> 本文件自含全部目标、判据、红线与阶段定义，不依赖外部上下文。
> **配套本地文档**：`C:\relab2\docs\UPDATE-GOAL-2026-10-12.md` —— 权威定稿，开工前通读，
> 每阶段开头重读它的 §4 与当前阶段条目，完成后按 §10 追加记录。
> **姊妹篇**（初逆复刻，已完成）：`docs/DELIVERY-GOAL-2026-10-12.md`。本次只做「版本更新」这一环，
> 不重做初逆，不改它已建成的任何东西。

---

## 总目标

把「复刻成品跟着原程序升级」做成复刻 case 的一个 `update` 阶段，**不新建第二套体系**。

用户场景（必须能跑通）：
> 我之前用复刻流程做出了软件 A 的复刻品（原程序 1.1 → 复刻 1.1）。两天后原程序更新到 1.2。
> 我把 1.2 的原程序放进 case 目录，说一句「这个软件更新了，做一次更新式分析」。
> 系统读上一次留下的对账表（rebuild.md）、差异基线（baseline/）、对照记录（diff/）、经验卡，
> 逐行判断每个功能在新版里变成什么样，重跑差异测试，交付复刻 1.2，并留下记录供下次再用。

**四条硬边界**：
1. 日常单点分析路径**逐字节不变**（不传 `-Preset update` 就完全看不到这套东西）。
2. 不新建技能、不改 `routing.json`、不改初逆已建成的 rebuild.md 结构语义（只加两个版本字段）。
3. **不碰 `kernel/` 下任何文件**。kernel 的 `01-敏捷逆向攻坚.md` / `02-二开更新中枢.md` /
   `02-hubcore/workflows/exe-rebuild.md` 只读，把其中可验证的设计（三句对照、补丁位移重算、
   版本指纹）搬进技能包。
4. 不推送远端仓库，只本地 commit。

---

## 为什么做（理解目标，不要只执行）

现状（定稿 §3 有实测依据）：初逆闭环已建成，但「原程序升级之后怎么办」整段是空的——
没有地方记录「这次复刻基于原程序哪个版本」、没有地方记录「新旧版差在哪」、
没有判据回答「我们的复刻还算不算数」。所以现在上游一更新，只能从零重逆。

你要补的就是这一段。做法全部是**挂靠既有资产**（rebuild.md / diff-runner / review_case / impl / ver），
只在 case 里多两个文件（`update.md` + `freeze/`），外加一次脚本扩展。

---

## 七个阶段（阶段 0 必做且先行；判据未达成的阶段不许标记完成）

### 阶段 0 · 前置修复：交付审计器验内容，不验自称（必做，排在所有事之前）

**背景（这是 2026-10-12 主对话实测复现的真漏洞，不是猜的）**：
`review_case.py` 的完成度审计只验「表格自称一致」——verdict 那格写了「一致」、
引用的 diff 文件存在，就 PASS。它**不解析 diff 文件里两条 stdout 是否真的一样**。

主对话的实测复现步骤（你照着重做一次，必须抓到才算修好）：
```
1. python skillpack/skills/scripts/diff-runner.py work/rebuild-sha256sum --function F-009 \
     --input baseline/sample.txt --baseline-cmd 'bash -lc "sha256sum -t {input}"' \
     --rebuilt-cmd 'bash -lc "python build/newsha.py {input}"' --out C:/tmp/f009.md
2. 在 rebuild.md 里给 F-009 编造「对照一致」+ 一条 verdict=一致的对照行
3. review_case.py <该case> --verify-hashes --strict → 竟然 PASS，0 errors
```
同一案例还暴露两个具体真差异（`work/rebuild-sha256sum` 的交付物 `build/newsha.py`）：
- F-003：原程序输出 `\n`，新实现输出 `\r\n`（Git bash 里 Python stdout 是二进制模式），
  报告却写「stdout 逐字节一致」
- F-005：按 rebuild.md 登记的 `cd baseline && python ../build/newsha.py {input}` 跑，
  实际 `No such file or directory`（sums.txt 里是仓根相对路径，cd 进去就找不到）

**为什么排第一**：更新机制的完成判定（闸门②）完全靠「对照一致」四个字。
审计器不验内容，更新时同样能虚报。**先修审计，再建更新**，顺序不能倒。

**做什么**
1. `review_case.py` 新增 `rebuild.diff_bytes_mismatch` 判据：解析 `diff/<F-ID>.md` 里
   `--- baseline stdout ---` 与 `--- rebuilt stdout ---` 两段，归一化 `generated` 时间戳后
   **逐字节比**。不一致 → 报错。
2. 修 `work/rebuild-sha256sum/build/newsha.py` 的 F-003 `\r\n`
   （`sys.stdout.reconfigure(newline="\n")` 或写 bytes，二选一，实测消掉）。
3. 修该 case 的 F-005 驱动命令：`{input}` 传绝对路径（或 rebuilt_command 不 cd），
   让 rebuild.md 登记的命令可复现。
4. 重跑该 case 五行对照，rebuild.md 与 `diff/` 全部改成**真实结果**。
5. 负控扩容：`test-rebuild-audit-negctl.py` 加「diff 两段 stdout 不一致必须被抓」用例。

**动哪些文件**
- `skillpack/skills/case-review/scripts/review_case.py`
- `skillpack/skills/scripts/test-rebuild-audit-negctl.py`（+用例）
- `work/rebuild-sha256sum/`（gitignored 运行时产物：`build/newsha.py`、`rebuild.md`、`diff/*`）

**验收判据**
- 用上面的 F-009 伪造法重做一次 → **必须**报 `rebuild.diff_bytes_mismatch`，rc≠0
- 再造一个 fixture：表格写「一致」但 diff 两段 stdout 真差一字节 → 必须报错
- 好 case（五行真一致）0 报错
- `python skillpack/skills/case-review/tests/test_review_case.py` 全绿
- `python skillpack/skills/scripts/test-rebuild-audit-negctl.py` 全绿（条数比改前多）
- 该 case `review_case.py --verify-hashes --strict` PASS，且 F-003/F-005 的 diff 是重跑后的真字节

**风险**：中高。改门禁脚本 + 动一个已经「PASS」的历史 case。
**真相优先于面子**：查明它真的不达标，就如实改成未达标并记原因，
**不许为了让门禁绿而改判据**。

### 阶段 1 · 版本指纹与冻本约定（纯文档）

**做什么**
在 `skillpack/skills/ops/rebuild-gates.md` 文末新增「更新阶段」一节，定义三件事：
1. **版本指纹** = `路径 + 版本号 + SHA256`，固定三份：旧版原程序、新版原程序、我们的旧复刻产物。
2. **冻本** = `work/<case>/freeze/<我们的版本>/`，内容 = `rebuild.md` 快照 + `diff/` 快照 + 交付物 hash。
   冻本不是备份，是**下一次更新的旧锚**：三句对照的「我们改过哪些」从它读，不从聊天记忆读。
3. **三句对照**（缺一句 = 不具备动代码的施工依据）：
   - 我们改过哪些功能（读 rebuild.md 功能表，不读补丁字节）
   - 作者新改了什么（新旧版原程序对比结论）
   - 哪些还能搬 / 哪些必须重做 / 哪些是新能力要新测

同时在 `skillpack/skills/templates/rebuild.md` 的 `## target` 段加两个字段：`upstream_version`、`our_version`。

**为什么**：地基。先定字段与判据，零代码零风险。

**动哪些文件**
- `skillpack/skills/ops/rebuild-gates.md`（只新增，原正文一行不改）
- `skillpack/skills/templates/rebuild.md`（只 target 段加两行）

**验收判据**
- 版本指纹三字段 / 冻本约定 / 三句对照在文档中齐备且可判定（不是形容词）
- `grep -n "不允许\|不得\|禁止" skillpack/skills/ops/rebuild-gates.md` **0 命中**（措辞纪律）
- `git diff --stat` rebuild-gates.md 只有新增行；rebuild.md 只 target 段 +2 行
- `python skillpack/skills/scripts/check-fences.py` exit 0
- `python skillpack/skills/scripts/verify-doc-links.py` exit 0（active=0）

**风险**：低。

### 阶段 2 · `update.md` 模板 + `-Preset update` 入口

**做什么**
- 新增 `skillpack/skills/templates/update.md`，字段（完整照定稿 §4.1）：
  `## target`（case / old_upstream / new_upstream / our_old_build / goal，前四项都带 hash）、
  `## three_lines`（三句对照）、
  `## function_delta`（`| F-ID | 上游新版状态 | 我们的复刻是否仍有效 | 动作 | 依据 |`，
  上游新版状态 ∈ {未变, 行为变, 已移除, 新增替代}；我们的复刻 ∈ {仍一致, 需重测, 已失效}；
  动作 ∈ {keep, retest, redo, new}）、
  `## patch_shift`（只对 patch 路线行：`| F-ID | 旧特征码 | 新版命中 VA/offset | 位移重算 | 结果 |`）、
  `## verification`（`| F-ID | 输入 | 新版原程序结果 | 新复刻结果 | 是否一致 | 说明 |`）、
  `## out_of_update`（本次不更新的部分与理由）。
- `skillpack/skills/scripts/case-init.ps1` 与 `case-init.sh`：加 `update` 预设。
  行为：case 根**必须有** `rebuild.md`，否则明确报错并提示先做初逆；有则生成 `update.md` 骨架
  （从 templates/update.md 拷贝）+ 建 `freeze/` 与 `diff-update/` 空目录。
  授权档与 rebuild 预设同档（owner-operated 本地样本 + offline）。
  预设白名单同步加 `update`，错值仍 exit 2（bash）/ exit 1（PS）。

**为什么**：让更新有正式入口；设计成必须显式传参才出现，保证日常路径零变化。

**动哪些文件**
- 新增 `skillpack/skills/templates/update.md`
- `skillpack/skills/scripts/case-init.ps1`（+预设分支 +白名单 +目录 +骨架拷贝）
- `skillpack/skills/scripts/case-init.sh`（同步）
- `skillpack/skills/MASTER-ROUTING.md`（若列了预设清单则补一行；**不动 `config/routing.json`**）

**验收判据**
- 不带 `-Preset update` 时 `case-init` 产物与改前**逐字节一致**：
  先在干净副本上用 `git show 28bbb89:<脚本>` 的旧版跑三组（plain / offline-sample / rebuild）留底，
  改后同参数同目录再跑，只许 `created` 时间戳不同
- `-Preset update` 在 rebuild case 上生成 update.md + freeze/ + diff-update/；
  在**无** rebuild.md 的目录上明确报错（不许静默生成）
- 错值预设仍 exit 2 / exit 1，文案列出全部合法值
- `powershell -File skillpack\skills\scripts\test-routing.ps1 -Quick` 65/65
- `bash skillpack/skills/scripts/test-routing.sh` 205/205
- `powershell -File skillpack\skills\scripts\verify-routing-coherence.ps1` 全绿

**风险**：中低。两脚本必须同步。`test-bash-workflow.sh` 本机跑不了（python3 是 WindowsApps 占位符）→
**如实记「本机未实测」，不许写成通过**。

### 阶段 3 · review_case.py 扩展更新审计（改门禁脚本）

**做什么**：`review_case.py` 检测到 `update.md` 时加四项检查（定稿 §4.3）：
1. `three_lines` 三句全非空（缺一句报错——防「没写三句就动手」）
2. `function_delta` 覆盖 rebuild.md 里**每一个** F-ID（漏一行 = 更新范围没定义）
3. `verification` 表逐行五列填齐；状态「对照一致」的行必须有对应对照记录文件存在
4. `old_upstream` / `new_upstream` / `our_old_build` 三个 hash 都在位

同步：`skills/case-review/tests/` 补 fixture 与用例；`skills/case-review/SKILL.md` 的 ACTION REQUIRED
说明新检查；新增 `skills/scripts/test-update-audit-negctl.py` 并接进 `.github/workflows/ci.yml`
（照 `test-rebuild-audit-negctl.py` 与 ci.yml:466 的既有写法）。

**为什么**：这是更新机制的机器防线。它拦的是「拿旧对账交差」和「漏功能」。

**动哪些文件**
- `skillpack/skills/case-review/scripts/review_case.py`
- `skillpack/skills/case-review/tests/`
- `skillpack/skills/case-review/SKILL.md`
- 新增 `skillpack/skills/scripts/test-update-audit-negctl.py`
- `.github/workflows/ci.yml`（+一个负控 step）

**验收判据**
- 坏 fixture 每个都必须被报错：三 hash 缺一 / 三句缺一句 / function_delta 漏 F-ID /
  verification 行状态虚高（标一致但无对照记录）/ 对照记录文件不存在
- 好 fixture 0 报错
- **回归底线**：不含 update.md 的既有 case（至少 `work/rebuild-sha256sum` 与
  `skillpack/examples/ctf-demo`）markdown / json / plain 三格式输出与改前**逐字一致**
- `python skillpack/skills/case-review/tests/test_review_case.py` 全绿
- `python skillpack/skills/scripts/test-update-audit-negctl.py` 全绿（≥8 条）
- 改完必须跑一次全量：`python skillpack/scripts/verify-evolution.py`（基线 10/10）

**风险**：中。这是门禁脚本。本仓有 6 个「从未真正工作过」的门禁前科
（`docs/AUDIT-2026-10-10-FINAL.md`）——**负控不是可选项**。

### 阶段 4 · diff-runner 的更新驱动

**做什么**：让 `diff-runner.py` 能把同一输入分别喂给**新版原程序**与**新复刻**，
草稿落 `diff-update/<F-ID>.md`。参数保持向后兼容：继续支持
`--baseline-cmd` / `--rebuilt-cmd`（初逆用法不变），新增 `--out-dir diff-update` 之类的落点控制。

**为什么**：更新的验证必须用新版原程序当基线；旧 `diff/` 是旧锚，不能覆盖、不能混。

**动哪些文件**
- `skillpack/skills/scripts/diff-runner.py`
- `skillpack/skills/templates/update.md`（补驱动命令字段）
- `skillpack/skills/ops/rebuild-gates.md`（更新阶段驱动说明）

**验收判据**
- 对同一输入能产出「新版原程序 vs 新复刻」草稿，落 `diff-update/`
- 旧 `diff/` 内容零改动（跑前跑后 hash 一致）
- 初逆既有用法（`--function F-001` 那套）行为不变
- 复习：`python skillpack/skills/case-review/tests/test_review_case.py` 全绿

**风险**：中低。最大风险是过度设计——保持「能驱动 + 能记录」，不加热自动判定。

### 阶段 5 · 真更新试跑（P2）

**做什么**：拿 `work/rebuild-sha256sum` 当素材做一次真实升级演练。
构造「新版」= 行为面有增删改的受控样本（这是本仓自己造的 fixture，不是去动系统里的 sha256sum）：
至少覆盖三种变化——某功能**行为变**、某开关**新增替代**、某功能**已移除**。
然后走完整流程：冻本 → 三句对照 → function_delta 逐行判定 → 更新驱动 → review_case strict。

**为什么**：前四阶段都是设计，只有真跑过才知道哪里多余、哪里还缺。

**验收判据**
- 产出含 `freeze/<版本>/` + `update.md` 全表 + `diff-update/` 记录 + 更新后的交付物
- `python skillpack/skills/case-review/scripts/review_case.py work/<case> --verify-hashes --strict` PASS
- 三种变化都真的在 function_delta 里判定对了（keep / retest / redo / new 各至少出现一次）
- 未达标项**如实**写「未达标 + 原因」，不许粉饰

**风险**：低。这是验证阶段。但失败记录和成功记录同等价值。

### 阶段 6 · 措辞优化：把「许可状/刹车」改写成「施工依据」（纯文档）

**背景（2026-10-12 主对话实查）**：用户在另一个项目（网盘）的对话里看到模型输出
「红线要求尊重对方 + 逆向成本不划算」。全仓精确搜索这三个短语**零命中**
（skillpack / kernel / 三家宿主入口 / community-raw 全查过）。我们自己的「红线」
在 `docs/GOAL-PROMPT-*.md` 与 `环境建设.md` 里，全是工程纪律（不推仓库 / 不碰 kernel /
不猜路径），与「尊重对方」无关。

但体系里确实有 4 处措辞对模型构成「刹车」信号：
① `web-protocol-reverse/SKILL.md:63`「目标不在授权 scope 内 → **不做**」
② `web-protocol-reverse/SKILL.md:101`「一个裸 URL 本身**不构成**……授权」
③ `provider-work-order.md`「未知或省略的权限一律意味着 blocked / offline」「先停下」
④ `RULES.md` / `RULES_zh.md` 的 Security Boundaries 段「MUST be within user's authorized scope」

**核心思路：只改措辞，不改判据。** 门还在、证据要求没松，只把「要先过一道门」
翻译成「一条命令就能过，过完继续干」。

**改法对照表（照此执行）**：

| 位置 | 改为 |
|---|---|
| R50 SKILL.md:63 | 「目标不在授权 scope 内 \| 施工依据是先落 scope：`case-init --preset rebuild` 一条命令补上，落完即继续」 |
| R50 SKILL.md:101 | 「裸 URL 不带 scope 字段 —— `case-init` 一条命令补上，然后照常推进」 |
| provider-work-order.md:80 | 「未知权限 = 该动作先按离线形态做（定值向量 / 静态检视 / 本地复现）；要发出站再把那一个字段补上」 |
| provider-work-order.md:118 | 「切换路线前先写下当前拦路点（一句），这是交接记录的一部分，不是停点」 |
| RULES.md / RULES_zh.md | 「Scope 走 `case-init`：owner-operated 本地样本三行命令内 granted，granted 后本包不重复询问」 |

**保留不动**（这些是真判据，不是措辞）：`case-init` 授权硬门与 `-Force` 不绕过的语义、
`review_case.py` 全部判据、provider-work-order 三道 Guard 的**检查逻辑**、RULES.md 的 activation 门。

**动哪些文件**
- `skillpack/skills/web-protocol-reverse/SKILL.md`（第 63 行 + 第 101 行）
- `skillpack/skills/web-protocol-reverse/references/contract/provider-work-order.md`（第 80、118 行等）
- `skillpack/RULES.md` + `skillpack/RULES_zh.md`（Security Boundaries 段，**两边同步**）

**验收判据**
- 上表每一行都落地，且原判据语义未变（`git diff` 逐条核：只许措辞变，不许 gate 条件消失）
- RULES.md 与 RULES_zh.md 同步改完，`powershell -File skillpack\skills\scripts\verify-doc-facts.ps1` exit 0
- 改动的行上 `grep -n "不做\|不构成\|一律意味着\|先停下"` 0 命中
- `python skillpack/scripts/verify-evolution.py` 10/10 全绿
- `check-fences.py` / `verify-doc-links.py` 全绿

**风险**：中。RULES.md / RULES_zh.md 是 `verify-doc-facts.ps1` 与
`verify-canonical-base-lock.py` 的检查对象，改不好会假红。
**只动 Security Boundaries 那 5 行，其余一行不碰。**

---

## 全程红线（每阶段开工前自检）

1. **不推送远端**。只在本地 commit。开工前 commit（`版本更新融合 · 开工基线 2026-10-12`），
   完成后再 commit（`版本更新融合 · 完成`）。
2. **不碰 `kernel/`**。只读它的设计。kernel 有 27 条断言钉在自己的文件上。
3. **日常路径零变化**：不传 `-Preset update` 时，case-init / diff-runner / review_case / 门禁
   行为与开工前一致。任何影响日常行为的改动即缺陷，回退重做。
4. **不重做初逆闭环**：rebuild.md 只加 `upstream_version` / `our_version` 两个字段，
   不改它的四态阶梯、不改闸门①②、不改 role-map 的 impl/ver 定义。
   （例外：**阶段 0** 允许改 `review_case.py` 与历史 case 内容——那是修 bug，
   判据只加强不放松，动完必须在定稿 §10 写清改了哪条判据、为什么。）
5. **不新增技能、不改 `routing.json`**。
6. **阶段 6 只许改措辞，不许改判据**：`git diff` 逐条核——只许措辞变，
   不许 gate 条件消失。RULES.md / RULES_zh.md 只动 Security Boundaries 那 5 行；
   `case-init` 授权硬门、`-Force` 不绕过、`review_case.py` 全部判据原样保留。

---

## 判据口径（全程有效）

- 未实跑不许写「已实测」。本机跑不了的必须写「本机未实测」
  （已知：`test-bash-workflow.sh`、bash 侧默认目录治理——本机 `python3` 是 WindowsApps 占位符 exit 49）。
- 判据必须是外部可观测事实：文件真被创建、字节真被改、命令真回显预期输出。
  不许用「日志里出现我自己写的标记」（经验卡 `gate-self-must-prove-failure`）。
- 「门禁绿」只代表该门禁这一次的结果，不代表功能达成。
- **真相优先于门禁绿**：查明历史 case 真的不达标，就如实改成未达标并记原因，
  不许为了让门禁绿而改判据。
- 同一方法连败两次 → 换方法，不许在原路线上加第三个补丁。

---

## 每阶段必走的收尾动作

1. 跑该阶段「验收判据」列出的**每一条**命令，记录真实输出
2. 跑全量回归：`python skillpack/scripts/verify-evolution.py`（基线 10/10，开工前实测）
3. 在 `docs/UPDATE-GOAL-2026-10-12.md` §10 追加该阶段完成记录（格式见该文件）
4. 本地 commit，message 写 `版本更新融合 · 阶段N <名称>`
5. 才允许进入下一阶段

---

## 开工自检（第一回合必须逐条回答，再动手）

```
1. 基线确认：git status 是否干净？最近一次 commit hash 是什么？
2. 开工 commit：是否已按红线 1 提交开工基线？
3. 当前阶段：从阶段 0 开始（除非 docs/UPDATE-GOAL-2026-10-12.md 的 §10 显示已有进度）。
4. 日常路径保护：本阶段改动会不会影响不传 -Preset update 时的行为？如何验证？
5. kernel 边界：本阶段清单里是否出现任何 kernel/ 路径？（出现即立刻移除）
6. 初逆闭环保护：本阶段是否动了 rebuild.md 的既有语义 / 闸门①② / impl-ver 定义？
   （只许加两个版本字段；阶段 0 修 bug 是唯一例外，见红线 4）
```

答案不齐不许开工。

---

## 完成的定义

以下六条**同时**满足才算本项目完成：

1. 七个阶段（0–6）验收判据全部达成，未达标项在定稿 §10 有如实记录
2. `verify-evolution.py` 10/10 全绿；`verify-routing-coherence.ps1` 全绿
3. 不传 `-Preset update` 时，case-init / diff-runner / review_case / 门禁行为与开工前一致（有 diff 证据）
4. 含 update.md 的 case 能被严格审查通过；不含 update.md 的既有 case 输出逐字不变
5. 阶段 5 的真更新试跑产出 `freeze/` + `update.md` 全表 + `diff-update/` + 更新后交付物，
   且三种变化（行为变 / 新增替代 / 已移除）都被正确判定
6. **阶段 0 审计器真的在比字节**：伪造的「表格一致但 stdout 差一字节」fixture 必须被拦住；
   `test-rebuild-audit-negctl.py` 比改前多至少 1 条且全绿

**只有六条同时满足才写「完成」。缺任何一条，写「未完成 + 缺哪条 + 为什么 + 下一步」。**
不许用「基本完成」「大体可用」覆盖未达标项——这个项目本身要治的就是这个病。
