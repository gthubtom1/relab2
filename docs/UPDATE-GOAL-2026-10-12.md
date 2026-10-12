# 版本更新（二开融合）· 权威定稿（2026-10-12）

> **这份文件的性质**：`docs/DELIVERY-GOAL-2026-10-12.md`（初逆复刻）的**姊妹篇**，只管「版本更新」这一环。
> 新对话开工前通读一遍，每阶段开头重读当前阶段条目，完成后按 §10 格式追加记录。
>
> **配套目标清单**：`docs/GOAL-PROMPT-UPDATE-2026-10-12.md`（可直接整段复制进 `/goal set`）。
>
> **本文所有事实性陈述来自 2026-10-12 对 `C:\relab2` 的实查**。标 `[推断]` 的是推断，未实跑的一律写「未实测」。

---

## 0. 一句话目标

**把「复刻成品跟着原程序升级」做成复刻 case 的一个阶段（`update`），不新建第二套体系：**
原程序出 1.1 → 你把新样本放进 case → 系统读上一次的对账表（rebuild.md）、差异基线（baseline/）、
对照记录（diff/）、经验卡，**逐行判断每个功能在上游新版里变成了什么样**，
重跑差异测试，交付新版本的复刻成品，并留下更新记录供下一次再用。

日常单点分析路径**逐字节不变**（不传 `-Preset rebuild` 就完全看不到这套东西）。

---

## 1. 为什么要做（用户原话 + 结构性根因）

用户原话（2026-10-12 归纳）：

1. 「初次逆向和二次更新，都靠这个路由中枢去路由，以后不需要 HUB 卡片了」
2. 「今天逆向的 A 程序是 1.1，两天后它更新 1.2，我把新软件放目录里，提示词写『我们做好的软件更新了，做一次更新式分析』」
3. 「根据之前旧版本的经验、本地的清单，读本地留下来的记录，再分析新程序和旧版本有哪些改变」
4. 「告诉我可不可以更新成功，更新成属于我们自己的复刻版本的更新版本」

结构性根因（本次实查）：

| 痛点 | 现状证据 |
|---|---|
| 更新能力只存在于 kernel 卡片里，技能包路由完全没接 | `routing.json` 51 条路由无一按「项目阶段」路由；R48 delivery 明确「安全/逆向/真实部署动作交还 canonical」，而 canonical 终点是报告 |
| 「本地留下的清单」至今没有标准化 | case-init rebuild 只建 `rebuild.md` + `baseline/` + `diff/`；没有版本快照目录、没有跨版本功能差异表 |
| 更新判据没有 | `review_case.py` 只审单版本对账表，无法回答「新版和旧版差在哪、我们的复刻还算不算数」 |

---

## 2. 现状底册（本次实查）

### 2.1 已有资产（不许重复建设）

| 资产 | 位置 | 本次要复用它做什么 |
|---|---|---|
| 对账表 | `skills/templates/rebuild.md` | 更新时**直接读它**当功能基线，不新建清单 |
| 差异基线 | `work/<case>/baseline/` | 旧版原程序行为样本 = 新旧对比的「旧锚」 |
| 对照记录 | `work/<case>/diff/` | 旧版逐功能对照结论 |
| 闸门 | `skills/ops/rebuild-gates.md` | 更新的完成判定仍走闸门②（对照一致 / 受限+原因） |
| 交付审计 | `case-review/scripts/review_case.py` | 扩展读 `update.md`，不新建审查器 |
| 驱动工具 | `skills/scripts/diff-runner.py` | 新版驱动复用同一工具 |
| 目标锚 | `skills/templates/goal.md` | 更新阶段的目标变更写进 GOAL.md |
| 角色 | `ops/role-map.md` impl / ver | 更新的实现与验收沿用这两个角色 |
| 经验卡 | `skills/experience-cards/` | 「模式漂移」类坑已有卡（`diff-runner-mode-drift`） |

### 2.2 kernel 侧卡片（本次**不动它**，但要把它的设计吃进来）

| 文件 | 内容要点 | 融合去处 |
|---|---|---|
| `kernel/04-console/cards/hub/01-敏捷逆向攻坚.md` | 产出契约 `REVERSE-MAP.md`：目标文件 + SHA256 + 架构/版本 + 关键偏移与 16+ 字节特征码 + 算法参数 + 补丁建议 | 「版本指纹」一节：用本仓已有的 hash 机制（`append-evidence.ps1` / review_case `--verify-hashes`），不引入第二套哈希口径 |
| `kernel/04-console/cards/hub/02-二开更新中枢.md` | 阶段 C「版本更新自动化重放」：特征码检索 → 模式匹配定位新 VA → 位移重算 → 补丁重写 → 回归探针 | 「补丁路线行的平移重算」一节：只对 `patch` 路线行生效，公式照搬 |
| `kernel/02-hubcore/workflows/exe-rebuild.md` | 「随上游更新（G）」：新工作目录、先对照冻本与改动图、三句对照（我们改过哪些 / 作者新改了什么 / 哪些还能搬）、`still_portable` 必须同时写「还能认」与「当新门」 | 「三句对照」与 `still_portable` 判据直接成本项目的阶段 2 产出要求 |

**为什么不动 kernel**：它有自己的安装/卸载契约（`03-bundle/install.py` + 12 条 BOTTOM_LINES 自检）
和 27 条断言（`kernel/TASKBOARD.md` 记载）。本次只读不写，把其中**可验证的设计**搬进技能包。

### 2.3 文档门禁口径（写新文档前必须知道）

| 门禁 | 扫描范围 | 新文档放哪安全 |
|---|---|---|
| `check-fences.py` | `skillpack/skills` 下全部 md | `docs/` 不被扫 |
| `audit-doc-code.py` | 默认 `skillpack/skills` | `docs/` 不被扫 |
| `verify-doc-links.py` | `git ls-files` + 未跟踪普通文件；`docs/**` 属 **active**（必须 0 断链） | 相对链接必须指向真实文件；不想产生链接就用行内代码写路径 |
| `scan-leaks.ps1` | md/txt/json 查敏感信息 | 不写密钥、真实 token（已知旧 finding 在 `docs/HANDOFF-2026-10-11.md:38`，**不是本次引入**） |
| `verify-doc-facts.ps1` | 只查 RULES.md / RULES_zh.md / SKILL.md 三处 | 新文档不在这三个文件就不触发 |

---

## 3. 已有体系缺什么（本次唯一要补的缺口）

初逆闭环（`DELIVERY-GOAL-2026-10-12.md`）已经建成：rebuild.md + impl/ver + review_case 交付审计。
**但「原程序升级之后怎么办」整段是空的**：

1. 没有地方记录「这次复刻是基于原程序哪个版本」
2. 没有地方记录「新旧版原程序差在哪」
3. 没有判据回答「我们的复刻还能不能算数、哪些行要重做」
4. `review_case.py` 无法审计更新（它只认 rebuild.md 的单版本结构）

---

## 4. 设计方案：`update` 阶段（四件新增，全部挂在既有 case 上）

### 4.1 新增文件 `update.md`（case 根，更新阶段的唯一状态文件）

```
## target
- case:            <case 名>
- old_upstream:    <旧版原程序 路径 | 版本 | SHA256>
- new_upstream:    <新版原程序 路径 | 版本 | SHA256>
- our_old_build:   <我们的旧复刻产物 路径 | SHA256>
- goal:            <这次更新要交付什么>

## three_lines   ← 三句对照（exe-rebuild G 的判据，缺一句不准进实现）
- we_changed:     <我们改过哪些功能 —— 读 rebuild.md 功能表，不读补丁字节>
- upstream_new:   <作者新改了什么 —— 新旧版原程序对比结论>
- portable:       <哪些还能搬 / 哪些必须重做 / 哪些是新能力要新测>

## function_delta   ← 逐行判断（每个 F-ID 一行）
| F-ID | 上游新版状态 | 我们的复刻是否仍有效 | 动作 | 依据 |
| F-001 | 未变 / 行为变 / 已移除 / 新增替代 | 仍一致 / 需重测 / 已失效 | keep / retest / redo / new | E-xxx 或 diff/ 记录 |

## patch_shift   ← 只对 patch 路线行
| F-ID | 旧特征码 | 新版命中位置 (VA/offset) | 位移重算 | 结果 |

## verification
| F-ID | 输入 | 新版原程序结果 | 新复刻结果 | 是否一致 | 说明 |

## out_of_update   ← 本次不更新的部分与理由
```

### 4.2 新增 `freeze/<我们的版本>/`（版本冻本，放在 case 内）

更新前，把「当前可交付状态」冻一份：`rebuild.md` 快照 + `diff/` 快照 + 交付物 hash。
冻本不是备份文件，是**下一次更新的旧锚**：三句对照的「我们改过哪些」从它读，不是从聊天记忆读。

### 4.3 `review_case.py` 扩展（改一个脚本，不新建）

检测到 `update.md` 时额外审四项：

1. `three_lines` 三句都非空（缺一句即报错——这正是「没写三句就动手」的防线）
2. `function_delta` 覆盖 rebuild.md 里**每一个** F-ID（漏一行 = 更新范围没定义）
3. `verification` 表逐行五列填齐；状态「对照一致」的行必须有对应对照记录
4. `our_old_build` / `old_upstream` / `new_upstream` 三个 hash 都在位（hash 走既有 `--verify-hashes` 口径）

无 `update.md` 的 case 输出**逐字节不变**（这是回归底线，改造时已有先例：
阶段 4 的做法是「无 rebuild.md 的 case 三格式输出 IDENTICAL」）。

### 4.4 角色与措辞（不加新技能）

- 沿用 `impl`（进入条件 = 三句对照齐 + function_delta 齐）与 `ver`（唯一有权改「对照一致」）
- 措辞纪律同 `rebuild-gates.md`：不写「不允许/不得」，写「施工依据/判定事实」；
  「受限」写成推进旁路（写清原因/影响/替代，其余行照常）

---

## 5. 用户会被问到什么（本方案对痛点的直接回答）

| 用户问题 | 本方案的回答 |
|---|---|
| 「以后还要不要 kernel 那两张卡？」 | **日常分析/初逆复刻不需要**（技能包已覆盖）。更新分析也不需要它们——它们的可验证设计已融进 `update.md` 的三句对照与 patch_shift。kernel 卡片继续作为「单条回复纪律」常驻（那是破甲卡的职责，跟本方案不冲突） |
| 「会不会和现有体系打架？」 | 不会。初逆走 `DELIVERY-GOAL-2026-10-12.md`，更新走本文件，共用同一套 rebuild.md / diff-runner / review_case，只是多一个 `update.md` |
| 「我怎么触发更新？」 | 把新版原程序放进 case 目录，一句「这个软件更新了，跑一次更新式分析」即可。路由层会认 `update` 阶段（见 §7 阶段 1 的路由语义） |
| 「更新失败了怎么办？」 | 冻本在、`update.md` 的 function_delta 在，随时可以只重做出问题的行，不动其他行 |

---

## 6. 与 kernel 体系的关系（先回答这个，避免误判为冲突）

**结论：分工，不冲突，且本次不写 kernel 一个字节。**

| | kernel 卡片/工作流 | 本项目（skillpack 更新阶段） |
|---|---|---|
| 管什么 | 单条回复纪律（破甲卡）+ 无源码商业二开的完整阶段机（state.py 账本、7 格合同、授权生命周期） | 复刻 case 的版本更新（三句对照 + 逐行功能差异 + 补丁平移） |
| 跑在哪 | 宿主机家目录 `hub/`，由 `03-bundle` 安装 | 技能包内 case 目录，由 `case-init -Preset rebuild` 生成 |
| 状态存哪 | 产品根 `.hub/` + `CHANGES.md` | case 根 `rebuild.md` + `update.md` + `freeze/` |

要做**商业二开（接自己的授权、做启动器、给客户装包、客户机点更新）**时，仍然该用 kernel 的 `exe-rebuild`——那是它的主场，本方案不替代它。本方案替代的是「**我只要一个功能等价的复刻品，并且要能跟着上游升级**」这一条。

---

## 7. 分阶段实施清单

每阶段格式：**做什么 / 为什么 / 动哪些文件 / 验收判据 / 风险**。

### 阶段 0 · 前置修复：交付审计器验内容，不验自称（必做，先行）

**背景（这是 2026-10-12 主对话实查发现的真漏洞，实测复现过）**：
`review_case.py` 的完成度审计只验「表格自称一致」——表格里 verdict 写「一致」、
引用的 diff 文件存在，就 PASS。它**不解析 diff 文件里的两条 stdout 是否真的一样**。

实测证据（主对话用 diff-runner 伪造了一个不存在的 F-009，同样 PASS）：
```
1. python skillpack/skills/scripts/diff-runner.py work/rebuild-sha256sum --function F-009 \
     --input baseline/sample.txt --baseline-cmd 'bash -lc "sha256sum -t {input}"' \
     --rebuilt-cmd 'bash -lc "python build/newsha.py {input}"' --out C:/tmp/f009.md
2. 在 rebuild.md 里给 F-009 编造「对照一致」+ 一条 verdict=一致的对照行
3. python skillpack/skills/case-review/scripts/review_case.py <该case> --verify-hashes --strict
   → status: PASS，0 errors
```
同一案例还暴露两个具体真差异（`work/rebuild-sha256sum` 的交付物）：
- F-003：`sha256sum` 输出 `\n`，`build/newsha.py` 输出 `\r\n`（Git bash 里 Python stdout
  是二进制模式），报告却写「stdout 逐字节一致」
- F-005：按 rebuild.md 登记的 `cd baseline && python ../build/newsha.py {input}` 跑，
  实际报 `No such file or directory`（sums.txt 里的路径是仓根相对的，cd 进去就找不到）

**这件事为什么必须排在版本更新之前**：更新机制的完成判定（闸门②）完全依赖
「对照一致」这四个字。如果审计器不验内容，更新时同样可以虚报。
**先修审计，再建更新**——顺序不能倒。

**做什么**：
1. `review_case.py` 增加 `rebuild.diff_bytes_mismatch` 判据：解析 `diff/<F-ID>.md` 里
   `--- baseline stdout ---` 与 `--- rebuilt stdout ---` 两段，归一化
   `generated` 时间戳后**逐字节比**。不一致 → 报错。
   - 两段都缺失（老格式 diff）→ 记 warning 并升级为 error 前给一次迁移窗口：
     新判据只对含这两段的 diff 生效；老 case 的 diff 由本阶段统一重跑 diff-runner 补齐。
2. 修 `work/rebuild-sha256sum/build/newsha.py` 的 F-003 `\r\n`：
   `sys.stdout.reconfigure(newline="\n")`（Python 3.7+）或写 bytes，二选一，实测消掉 `\r\n`。
3. 修该 case 的 F-005 驱动命令：`{input}` 传**绝对路径**（或 rebuilt_command 不 cd），
   使 rebuild.md 登记的命令可复现；补一条负控——diff 文件里登记的命令不可复现即报错。
4. 修完重跑该 case 的五行对照，rebuild.md 与 diff/ 全部改成真实结果。
5. 负控扩容：`test-rebuild-audit-negctl.py` 加「diff 两段 stdout 不一致必须被抓」用例
   （这是本轮最该补的一条——证明审计器真的在比字节）。

**动哪些文件**：
- `skillpack/skills/case-review/scripts/review_case.py`
- `skillpack/skills/scripts/test-rebuild-audit-negctl.py`（+用例）
- `work/rebuild-sha256sum/build/newsha.py`（运行时产物，gitignored；改完在 §10 记录）
- `work/rebuild-sha256sum/rebuild.md` + `diff/*.md`（重跑后回填真实结果）

**验收判据**：
- 用主对话的 F-009 伪造法重做一次 → **必须**报 `rebuild.diff_bytes_mismatch`，rc≠0
- 构造一个「表格写一致、但 diff 两段 stdout 真差一字节」的 fixture → 必须报错
- 好 case（五行真一致）0 报错
- `python skillpack/skills/case-review/tests/test_review_case.py` 全绿
- `python skillpack/skills/scripts/test-rebuild-audit-negctl.py` 全绿（条数比改前增加）
- 该 case `review_case.py --verify-hashes --strict` PASS，且 F-003/F-005 的
  diff 记录是重跑后的真实字节

**风险**：中高。改的是门禁脚本 + 已经「PASS」的历史 case。
**真相优先于面子**：如果查明该 case 真的不达标，就如实改成未达标并记录原因，
**不许为了让门禁绿而改判据**（`re-agent-workflow.md` §13.5：不得为通过测试而修改错误的标准）。

### 阶段 1 · 版本指纹与冻本约定（纯文档）

**做什么**：在 `skills/ops/rebuild-gates.md` 新增「更新阶段」一节，定义三件事：
① 版本指纹 = `路径 + 版本号 + SHA256`（旧版原程序、新版原程序、我们的旧产物三份）
② 冻本 = case 内 `freeze/<我们的版本>/`，内容 = rebuild.md 快照 + diff/ 快照 + 交付物 hash
③ 三句对照（我们改过哪些 / 作者新改了什么 / 哪些还能搬）缺一句 = 不具备动代码的施工依据

**为什么**：这是整个更新机制的地基。先定字段与判据，不动代码，零风险。

**动哪些文件**：
- `skillpack/skills/ops/rebuild-gates.md`（新增「更新阶段」一节，原正文不改）
- `skillpack/skills/templates/rebuild.md`（在 `## target` 加两个字段：`upstream_version`、`our_version`，供更新时读）

**验收判据**：
- 版本指纹三字段、冻本目录约定、三句对照在文档中齐备且可判定
- `grep -n "不允许\|不得\|禁止" skills/ops/rebuild-gates.md` 仍 0 命中（沿用措辞纪律）
- `git diff` 对 rebuild-gates.md 只显示新增行；rebuild.md 只 target 段新增两行
- `check-fences.py` / `verify-doc-links.py` 全绿

**风险**：低。

### 阶段 2 · `update.md` 模板 + case-init 钩子（文档 + 两个脚本各十几行）

**做什么**：
- 新增 `skillpack/skills/templates/update.md`（§4.1 全字段）
- `case-init.ps1` / `case-init.sh` 的 rebuild 分支**不动**；新增的是：当 case 根已存在 `rebuild.md`
  且命令行带 `-Preset update`（或 `--preset update`）时，校验三份 hash 都填了再生成 `update.md` 骨架，
  并提醒先做冻本

**为什么**：让更新有正式入口。设计成**必须显式传参**才出现，保证日常路径零变化。

**动哪些文件**：
- 新增 `skills/templates/update.md`
- `skills/scripts/case-init.ps1`（预设分支 + 白名单 + 骨架拷贝，参考阶段 2 的 rebuild 写法）
- `skills/scripts/case-init.sh`（同步）
- `skills/MASTER-ROUTING.md` / `skills/routing.md`（如提到预设清单则补一行；不涉及 `routing.json`）

**验收判据**：
- 不带 `-Preset update` 时，`case-init` 产物与改前逐字节一致（用干净副本先留底再对比，沿用阶段 2 的零差异方法）
- `-Preset update` 在有 rebuild.md 的 case 上生成 update.md 骨架；在**没有** rebuild.md 的 case 上明确报错并提示先做初逆
- 错值预设仍 exit 2（bash）/ exit 1（PS），文案列出全部合法值
- `test-routing.ps1 -Quick` 65/65、`test-routing.sh` 205/205、`verify-routing-coherence.ps1` 全绿

**风险**：中低。两个脚本必须同步。`test-bash-workflow.sh` 本机跑不了（python3 是 WindowsApps 占位符）→ 如实记「本机未实测」。

### 阶段 3 · review_case.py 扩展更新审计（改门禁脚本，最需谨慎）

**做什么**：按 §4.3 加四项检查；无 `update.md` 的 case 输出逐字节不变。

**为什么**：这就是「防止没写三句就动手、防止漏功能、防止拿旧对账交差」的机器防线。

**动哪些文件**：
- `skills/case-review/scripts/review_case.py`
- `skills/case-review/tests/`（补 fixture + 用例）
- `skills/case-review/SKILL.md`（ACTION REQUIRED 说明新检查）
- 新增 `skills/scripts/test-update-audit-negctl.py` 并接进 `.github/workflows/ci.yml`
  （照 `test-rebuild-audit-negctl.py` + ci.yml:466 的既有做法）

**验收判据**：
- 坏 fixture 必须被报错：三种 hash 缺一 / 三句缺一句 / function_delta 漏 F-ID / verification 行状态虚高
- 好 fixture 0 报错
- **回归底线**：不含 update.md 的既有 case（含 `work/rebuild-sha256sum` 与 `skillpack/examples/ctf-demo`）
  markdown/json/plain 三格式输出与改前逐字一致
- `python skills/case-review/tests/test_review_case.py` 全绿
- `python skills/scripts/test-update-audit-negctl.py` 全绿（条数 ≥ 8）

**风险**：中。这是门禁脚本，本仓 `AUDIT-2026-10-10-FINAL.md` 记着 6 个假绿案例——
所以负控不是可选项，是必须。

### 阶段 4 · diff-runner 的更新驱动（改一个脚本）

**做什么**：让 `diff-runner.py` 支持「把同一输入分别喂给**新版原程序**与**新复刻**」，
产出草稿落 `diff-update/<F-ID>.md`（与初逆的 `diff/` 分开，不动旧证据）。
参数形态：`--baseline-dir` / `--upstream-version new` 或直接透传两条命令（保持现有 `--baseline-cmd` / `--rebuilt-cmd` 用法不变）。

**为什么**：更新的验证必须用**新版原程序**当基线；旧 `diff/` 是旧锚，不能覆盖。

**动哪些文件**：
- `skills/scripts/diff-runner.py`
- `skills/templates/update.md`（补驱动命令字段）
- `skills/ops/rebuild-gates.md`（更新阶段的驱动说明）

**验收判据**：
- 对同一输入，能产出「新版原程序 vs 新复刻」的草稿，落在 `diff-update/`
- 旧 `diff/` 内容零改动（`git status` 或 hash 对比证明）
- 现有 diff-runner 用法（初逆）行为不变

**风险**：中低。最大风险是过度设计——保持「能驱动 + 能记录」，不加热自动判定。

### 阶段 5 · 真更新试跑（P2，证据驱动）

**做什么**：拿 `work/rebuild-sha256sum` 当素材做一次**真实的新版升级演练**：
把 `build/newsha.py` 复刻的 `sha256sum` 行为面当成「旧上游」，
构造一个「新版」= 行为面有增删改的受控样本（例：新增 `--ignore-missing` 开关、
改 `--tag` 输出格式、移除某个开关），走完整更新流程：
冻本 → 三句对照 → function_delta → 逐行 keep/retest/redo/new → 更新驱动 → review_case strict。

**为什么**：前四阶段都是设计，只有真跑过才知道哪里多余。

**验收判据**：
- 产出含 `freeze/` + `update.md` 全表 + `diff-update/` 记录 + 更新后的交付物
- `review_case.py --verify-hashes --strict` PASS
- 未达标项如实写「未达标 + 原因」，不许粉饰

**风险**：低。这是验证阶段。但必须如实记录失败。

### 阶段 6 · 措辞优化：把「许可状/刹车」改写成「施工依据」（纯文档）

**背景（2026-10-12 主对话实查）**：用户在另一个项目（网盘）的对话里看到模型输出
「红线要求尊重对方 + 逆向成本不划算」。全仓精确搜索这三个短语**零命中**
（skillpack / kernel / 三家宿主入口 / community-raw 都查过），我们自己的「红线」
在 `docs/GOAL-PROMPT-*.md` 与 `环境建设.md` 里，全是工程纪律（不推仓库、不碰 kernel、
不猜路径之类），与「尊重对方」无关。

但体系里确实有 4 处措辞对模型构成「刹车」信号，容易让它合成一个「这事有风险/不划算」的判断：

| # | 位置 | 现在 | 为什么是问题 |
|---|---|---|---|
| 1 | `web-protocol-reverse/SKILL.md:63` | 「目标不在授权 scope 内 \| **不做**。先走 case-init」 | 硬拒绝句式 |
| 2 | `web-protocol-reverse/SKILL.md:101` | 「一个裸 URL 本身**不构成**……授权」 | 同上 |
| 3 | `provider-work-order.md` | 「未知或省略的权限一律意味着该动作 blocked / offline」「先停下并点名拦路点」 | 契约本身 fail-closed 是对的，但对模型是持续压力源 |
| 4 | `RULES.md:140-145` Security Boundaries | 「MUST be within user's authorized scope」「MUST confirm legal authorization」 | RFC 2119 + 法律词 |

**核心思路：只改措辞，不改判据**。门还在、证据要求没松，但把「要先过一道门」
翻译成「一条命令就能过，过完继续干」。这正是 `rebuild-gates.md` 已在用的措辞纪律。

**改法对照表（照此执行，不改语义）**：

| 位置 | 原文 | 改为 |
|---|---|---|
| R50 SKILL.md:63 | 「目标不在授权 scope 内 \| 不做。先走 `case-init.ps1`」 | 「目标不在授权 scope 内 \| 施工依据是先落 scope：`case-init --preset rebuild` 一条命令补上，落完即继续」 |
| R50 SKILL.md:101 | 「一个裸 URL 本身不构成……的授权」 | 「裸 URL 不带 scope 字段 —— `case-init` 一条命令补上，然后照常推进」 |
| provider-work-order.md:80 | 「未知或省略的权限一律意味着该动作 blocked / offline」 | 「未知权限 = 该动作先按离线形态做（定值向量 / 静态检视 / 本地复现）；要发出站再把那一个字段补上」 |
| provider-work-order.md:118 | 「先停下并点名拦路点再切换」 | 「切换路线前先写下当前拦路点（一句），这是交接记录的一部分，不是停点」 |
| RULES.md Security Boundaries | 「All operations MUST be within user's authorized scope」 | 「Scope 走 `case-init`：owner-operated 本地样本三行命令内 granted，granted 后本包不重复询问」 |

**保留不动的**（这些是真判据，不是措辞）：
- `case-init` 的授权硬门与 `-Force` 不绕过的语义
- `review_case.py` 的全部判据
- provider-work-order 的 Egress Guard / Execution Guard / Write Guard 六条**检查逻辑**
- `RULES.md` 的 activation 门（用户批准后才动宿主机配置）

**动哪些文件**：
- `skillpack/skills/web-protocol-reverse/SKILL.md`（第 63 行表格 + 第 101 行句）
- `skillpack/skills/web-protocol-reverse/references/contract/provider-work-order.md`（第 80、118 行等）
- `skillpack/RULES.md` + `skillpack/RULES_zh.md`（Security Boundaries 段，**两边同步改**）

**验收判据**：
- 上表每一行的「改为」都落地，且原判据语义未变（用 `git diff` 逐条核：只许措辞变，
  不许 gate 条件消失）
- RULES.md 与 RULES_zh.md 两处同步（`verify-doc-facts.ps1` 会查这两份的 capability 清单，
  改错会假红——跑它确认）
- 措辞纪律扫描：改完的文件里 `grep -n "不做\|不构成\|一律意味着\|先停下"` 在**本次改动的行**上 0 命中
- 全量回归：`python skillpack/scripts/verify-evolution.py` 10/10 全绿
- `check-fences.py` / `verify-doc-links.py` 全绿

**风险**：中。RULES.md / RULES_zh.md 是 `verify-doc-facts.ps1` 与
`verify-canonical-base-lock.py` 的检查对象，改不好会假红。**只动 Security Boundaries 那 5 行，
其余一行不碰。**

---

## 8. 三道红线（阶段 6 起再加一条）

1. **不推送仓库**，只在本地 commit。开工前 commit（`版本更新融合 · 开工基线 2026-10-12`），
   完成后 commit（`版本更新融合 · 完成`）。
2. **不碰 `kernel/`**。只读它的设计，不写它的文件。
3. **日常路径零变化**：不传 `-Preset update` 时，case-init / diff-runner / review_case / 全部门禁
   行为与开工前一致。任何影响日常行为的改动即缺陷，回退重做。
4. **阶段 6 只许改措辞，不许改判据**：`git diff` 逐条核——只许措辞变，
   不许 gate 条件消失。特别是 RULES.md / RULES_zh.md 只动 Security Boundaries 那 5 行，
   其余一行不碰；`case-init` 授权硬门、`-Force` 不绕过、`review_case.py` 全部判据原样保留。

---

## 9. 判据口径（全程有效）

- 未实跑不许写「已实测」。本机跑不了的必须写「本机未实测」（已知：`test-bash-workflow.sh`、
  bash 侧默认目录治理——本机 `python3` 是 WindowsApps 占位符 exit 49）。
- 判据必须是外部可观测事实：文件真被创建、字节真被改、命令真回显预期输出。
  不许用「日志里出现我自己写的标记」（经验卡 `gate-self-must-prove-failure`）。
- **真相优先于门禁绿**：查明历史 case 真的不达标，就如实改成未达标并记录原因，
  不许为了让门禁绿而改判据（`re-agent-workflow.md` §13.5）。
- 同一方法连败两次 → 换方法。

---

## 10. 完成记录（追加，勿改历史）

```
### 阶段 N · <名称> · <YYYY-MM-DD HH:mm>
- 做了什么: <一段话>
- 改了哪些文件: <列表>
- 验收命令与结果: <命令 + 真实输出摘要>
- 门禁结果: <跑了哪些、绿/红、红的原因>
- commit: <hash + message>
- 未达标/遗留: <如实写，没有就写「无」>
```

（以下为记录区，勿改历史）

### 阶段 0 · 前置修复：交付审计器验内容，不验自称 · 2026-10-12 23:35
- 做了什么: `review_case.py` 完成度审计新增「读记录内容」判据——完成态行引用的 diff 记录
  必须带两段原始 stdout，且两段**逐字节**一致（`rebuild.diff_bytes_mismatch`，bytes 级、
  不做换行归一化）；记录显示命令没跑起来（exit=ERROR/TIMEOUT/error）→
  `rebuild.diff_unreproducible`；老格式记录（缺原始块/缺命令登记）只记迁移窗口 warning
  （`rebuild.diff_unparsed`）。同时修 `work/rebuild-sha256sum` 两个真缺陷：newsha.py 关闭
  Windows stdout 换行翻译（F-003 `\r\n` 消除，od -c 实测对齐）、rebuild.md 的 rebuilt_command
  去掉 `cd baseline`（F-005 可复现，rc=0 两行 OK），五行对照全部重跑、判定表与 hash 同步真实结果。
- 改了哪些文件: `skillpack/skills/case-review/scripts/review_case.py`（+100 行）、
  `skillpack/skills/scripts/test-rebuild-audit-negctl.py`（+90 行，13→16 条）、
  `skillpack/skills/case-review/tests/test_review_case.py`（+69 行，14→17 用例）、
  `skillpack/skills/case-review/SKILL.md`（scope 段 + ACTION REQUIRED 说明）；
  运行时产物（gitignored）：`work/rebuild-sha256sum/{build/newsha.py,rebuild.md,diff/*,evidence/*,timeline.md}`、
  `work/sha256-rebuild-demo/{diff/F-001.md,evidence/E-001.md}`。
- 验收命令与结果:
  - F-009 伪造法重做（`python work/tmp-stage0/forge.py`，可重跑）→ 旧检查器（HEAD 版）
    rc=0 PASS、新检查器 rc=1 FAIL `rebuild.diff_bytes_mismatch`——漏洞复现 + 修复生效双铁证
    （存 `work/tmp-stage0/f009-forgery-proof.txt`）
  - `python skillpack/skills/scripts/test-rebuild-audit-negctl.py` → 16/16 controls honoured
    （新增：bad-diff-bytes-mismatch / bad-diff-unreproducible / old-format-record-warns）
  - `python skillpack/skills/case-review/tests/test_review_case.py` → Ran 17 tests, OK
  - `python .../review_case.py work/rebuild-sha256sum --verify-hashes --strict` → PASS（rc=0）
  - 同命令 `work/sha256-rebuild-demo` → PASS（rc=0，记录已重跑带命令登记）
  - 回归底线：ctf-demo markdown/json/strict 三格式输出（剥时间戳）与改前逐字 IDENTICAL ×4
- 门禁结果: `check-fences.py` rc=0、`verify-doc-links.py` rc=0、`audit-doc-code.py` rc=0、
  `verify-evolution.py` 10/10 ALL GREEN（含双 benchmark 65/65 + 93/86）
- commit: （本段提交）版本更新融合 · 阶段0 审计器验内容
- 未达标/遗留: 无。注：`work/tmp-stage0/`（伪造证据 + 旧检查器副本）为 gitignored 临时取证目录，
  保留供复查，不随提交入库。
