# RESULT —— protocol-automation 调度矩阵补丁（03-bundle/patches）
> **这是一份带日期的验收快照，反映的是那一天的状态，不是现状。**
> 里面的数字（如文件大小、段数）**不要再引用**——那之后规则又改过好几轮。
> 要看现在是什么，读 [`01-design/当前实测基线.md`](../../01-design/当前实测基线.md)。



生成时间：本次会话。所有命令都是真跑过的，输出是原样贴的。
**目标文件 `02-hubcore/workflows/protocol-automation.md` 全程只读，没有被改动。**
验收一律在副本 `_acceptance/protocol-automation.md` 上做。

## 0. 交付清单

| 文件 | 作用 |
|---|---|
| `matrix.md` | 新系统版调度矩阵（8 阶段 → 能力类别 → 真实方法书路径）。**第二轮已把正文里的裸文件名方法书改成裸书名** |
| `apply_matrix_fix.py` | 幂等补丁器：`--target <workflows/protocol-automation.md>` |
| `verify_matrix_links.py` | 逐条验证 `matrix.md` 里每个相对路径解析到真实文件 |
| `check_dead_refs.py` | **第二轮**：死链/死引用/能力缺口校验器，退出码 0 = 零死链 |
| `_patchlib.py` | **第二轮**：10 个定点修补脚本共用的底座（定点改写 + 幂等 + 归档原文） |
| `apply_protocol_automation_fix.py` | **第二轮**：矩阵修补 + 方法书写法修正（一个脚本两步） |
| `apply_exe_rebuild_fix.py` | **第二轮** |
| `apply_invariants_fix.py` | **第二轮** |
| `apply_reverse_engineering_fix.py` | **第二轮** |
| `apply_review_fix.py` | **第二轮** |
| `apply_browser_automation_fix.py` | **第二轮** |
| `apply_browser_automation_proof_fix.py` | **第二轮** |
| `apply_project_memory_fix.py` | **第二轮** |
| `apply_docs_audits_fix.py` | **第二轮**：一个脚本管三份目标文档 |
| `DEAD-REFS.md` | **第二轮**：判定规则 + 六条线前后表 + 56 处死链逐条 + POST_PATCHES 该加哪几行 |
| `_report_table.py` | **第二轮**：出前后对比表的小工具 |
| `RESULT.md` | 本文件 |
| `_acceptance/protocol-automation.md` | 打过矩阵补丁的副本（第一轮证据） |
| `_acceptance/no-matrix.md` | 「找不到旧段」用例的靶子（验证退出码 3 不瞎改） |
| `_acceptance/hubcore_before/` | **第二轮**：02-hubcore 全树副本（基线，只读） |
| `_acceptance/hubcore_after/` | **第二轮**：打过全部补丁的副本（改后） |
| `_acceptance/fresh-pa.md` | **第二轮**：模拟「全量重建后新矩阵直接成形」的用例 |

`03-bundle/` 和 `03-bundle/patches/` 这轮新建。`hub/`、`work/v0.1.0/`、`.hub/`、`02-hubcore/` 全部只读。

## 1. 实际读到的源文（行号核对）

`hub/.agents/skills/protocol-automation/SKILL.md` 共 191 行，矩阵段是 **176–191 行**，与任务描述一致：

- 176 `## 调度子技能矩阵（工作流管路，技能管能力）`
- 178 那句「表里写的是『要哪一类能力』……**不要照着名字去找一本本机没有的书**」——**只存在于源 SKILL.md，剪过的 02-hubcore 版里已经没了**
- 180–189 旧表 8 行
- 191 `**能让人点就让人点。**` 那段

`work/context-isolation/02-hubcore/workflows/protocol-automation.md`（剪过版）共 189 行，矩阵段是 **176–189 行**，比原文少 2 行（标题后的散文那句 + 表格竖线空格）。另外剪过版的表头没有空格：`| 阶段 / 场景| 要哪一类能力| 目的|`，原文是 `| 阶段 / 场景 | 要哪一类能力 | 目的 |`。补丁器因此用行首正则定位，不用精确字符串。

## 2. 验收 1 —— 副本跑两次，第二次无改动

```text
===== 第一次 =====
[定位] 旧矩阵：第 176 行 → 第 189 行（共 14 行）
[结果] 替换了 14 行 → 51 行
[统计] 字节 14742 → 20594（+5852）
[统计] 总行 189 → 226（+37）
[已写] _acceptance\protocol-automation.md
EXIT=0
SHA256 run1 = 2EC623A274675F9D36D267DE7E5E738798EDF3E0FA75D4EB70DB7CB42BF9586A
===== 第二次 =====
[无改动] protocol-automation.md 已是新版矩阵（含 <!-- hubcore: matrix-replaced-by 标记），本次不写任何字节。
        字节 20594，行 226，未变。
EXIT=0
SHA256 run2 = 2EC623A274675F9D36D267DE7E5E738798EDF3E0FA75D4EB70DB7CB42BF9586A
两次 SHA256 相同 -> 幂等成立
===== 第三次 =====
[无改动] protocol-automation.md 已是新版矩阵（含 <!-- hubcore: matrix-replaced-by 标记），本次不写任何字节。
        字节 20594，行 226，未变。
EXIT=0
SHA256 run3 = 2EC623A274675F9D36D267DE7E5E738798EDF3E0FA75D4EB70DB7CB42BF9586A
```

**踩过的坑（已修）**：第一版补丁器的次级锚点用的是纯字面 `要哪一类能力`，而新版正文里有一句散文「表里写的是「要哪一类能力」……」也含这 6 个字，第二次跑就把这句散文当成旧表头又替换了一遍，SHA256 变了。修法两处：兜底锚点收紧成表格行正则 `^\|.*要哪一类能力.*\|`；检测到 `<!-- hubcore: matrix-replaced-by` 标记后彻底禁用兜底锚点，只认一级锚点（章节标题）。另外注释块内的行全部被 mask，归档原文里的特征串不会误触发。

**退出码 3 路径也验了**（目标里既没有旧矩阵、也没有标记）：

```text
[未找到] 未找到旧矩阵，可能是已经改过或源文变了。
          没有改动目标文件。
EXIT=3
该文件未被改动 -> 符合「不要瞎改」
```

## 3. 验收 2 —— 禁用词扫描（`Select-String`）

```text
===== 验收2：禁用词扫描（目标文件 = 打过补丁的副本） =====
副插件              命中 0 处
控制台              命中 0 处
不要照着名字        命中 0 处
skills              命中 0 处
user-skills         命中 0 处
===== 对照：同样的词扫 matrix.md =====
副插件              命中 0 处
控制台              命中 0 处
不要照着名字        命中 0 处
skills              命中 0 处
user-skills         命中 0 处
```

改之前的原文件同样是 5 个词各 0 命中（基线就是干净的），所以补丁没有引入新词。

## 4. 验收 3 —— matrix.md 每条相对路径逐条验证

```text
matrix = ...\03-bundle\patches\matrix.md
base   = ...\02-hubcore\workflows
根边界  = ...\02-hubcore（解析结果不允许跑出这个目录）
------------------------------------------------------------------------------------------------------------
OK   matrix.md:5   ../docs/methods/INVARIANTS.md              -> 02-hubcore/docs\methods\INVARIANTS.md  [8020 字节]
OK   matrix.md:9   ../docs/methods/planning.md                -> 02-hubcore/docs\methods\planning.md  [3286 字节]
OK   matrix.md:10  ../docs/methods/browser-automation.md      -> 02-hubcore/docs\methods\browser-automation.md  [8098 字节]
OK   matrix.md:10  ../docs/methods/reverse-engineering.md     -> 02-hubcore/docs\methods\reverse-engineering.md  [10680 字节]
OK   matrix.md:11  ../docs/methods/reverse-engineering.md     -> 02-hubcore/docs\methods\reverse-engineering.md  [10680 字节]
OK   matrix.md:12  ../docs/methods/reverse-engineering.md     -> 02-hubcore/docs\methods\reverse-engineering.md  [10680 字节]
OK   matrix.md:12  ../docs/methods/mobile-reverse.md          -> 02-hubcore/docs\methods\mobile-reverse.md  [5019 字节]
OK   matrix.md:12  ../docs/methods/research-reuse.md          -> 02-hubcore/docs\methods\research-reuse.md  [1749 字节]
OK   matrix.md:13  ../docs/methods/reverse-engineering.md     -> 02-hubcore/docs\methods\reverse-engineering.md  [10680 字节]
OK   matrix.md:13  ../docs/methods/debugging-troubleshooting.md -> 02-hubcore/docs\methods\debugging-troubleshooting.md  [1903 字节]
OK   matrix.md:14  ../docs/methods/software-integration.md    -> 02-hubcore/docs\methods\software-integration.md  [2549 字节]
OK   matrix.md:14  ../docs/methods/browser-automation.md      -> 02-hubcore/docs\methods\browser-automation.md  [8098 字节]
OK   matrix.md:14  ../docs/methods/project-integration.md     -> 02-hubcore/docs\methods\project-integration.md  [1823 字节]
OK   matrix.md:15  ../docs/methods/debugging-troubleshooting.md -> 02-hubcore/docs\methods\debugging-troubleshooting.md  [1903 字节]
OK   matrix.md:15  ../docs/methods/review.md                  -> 02-hubcore/docs\methods\review.md  [16452 字节]
OK   matrix.md:16  ../docs/methods/release-readiness.md       -> 02-hubcore/docs\methods\release-readiness.md  [7055 字节]
OK   matrix.md:16  ../docs/methods/security-audit.md          -> 02-hubcore/docs\methods\security-audit.md  [5623 字节]
OK   matrix.md:16  ../docs/methods/data-storage.md            -> 02-hubcore/docs\methods\data-storage.md  [2966 字节]
------------------------------------------------------------------------------------------------------------
引用 18 条，去重后 13 个不同文件，通过 18 条，失败 0 条。
阶段覆盖：8/8，齐全
EXIT=0
```

## 5. 验收 4 —— 替换前后字节 / 行数

```text
替换前(源文件): protocol-automation.md  字节=14742  行=189  CRLF=189  BOM=False
替换后(副本):   protocol-automation.md  字节=20594  行=226  CRLF=226  BOM=False
```

矩阵段本身：**14 行 / 1398 字节 → 51 行 / 7250 字节**（净 **+37 行 / +5852 字节**）。
51 行 = 归档注释块 18 行（1599 字节，其中旧段原文 1398 字节逐字保留）+ 空行 1 行（2 字节）+ 新矩阵 32 行（5649 字节，`matrix.md` 32 行按目标文件 CRLF 重排）。
换行风格 CRLF、BOM 无，原样保留。

## 6. 差异说明（与任务描述不一致的地方，以我实际读到的为准）

1. **方法书目录不是 `02-hubcore/methods/`，是 `02-hubcore/docs/methods/`。** `02-hubcore/methods` 不存在（`Get-ChildItem` 报路径不存在）。所以矩阵里的相对路径是 `../docs/methods/x.md`，不是示例里的 `../methods/x.md`。
2. **真实清单是 20 个 `.md` + 2 个子目录，比任务给的 16 本多 4 本**：`anti-crack-build.md`、`browser-automation.md`、`mobile-reverse.md`、`planning.md`；另有 `browser-automation/`（13 个分册）和 `review/`（3 个分册）两个目录。
3. **矩阵里用到了 3 本计划外的书**（都是 `ls` 验证过的真实文件，不是编的）：`planning.md`（`0-spec` 规划类）、`browser-automation.md`（`1-env-traffic` / `5-automate` 浏览器自动化类，CDP 监听、登录保持、填表点击都在里面）、`mobile-reverse.md`（`3-solve-re` 移动 App 侧）。原 16 本里没有能覆盖这三格的。任务给的 16 本里，`INVARIANTS.md` 当公共品质在开头引一次，其余 12 本（`release-readiness` `review` `security-audit` `data-storage` `packaging` `software-integration` `debugging-troubleshooting` `performance-optimization` `reverse-engineering` `browser-testing` `windows-environment` `project-integration` `research-reuse` `project-init` `ui-design`）里，`packaging` `performance-optimization` `project-init` `ui-design` `browser-testing` 在这条线上没有对应格——我在矩阵「矩阵的边界」里点名说明了「别为了凑数打开」，而不是硬塞进表格。
4. **`3-solve-re` 的诚实处理**（按要求写进了矩阵）：原文那一格是「逆向类（JS / APK / 原生 / 反调试）」，靠外部库兜底。本系统只有 `reverse-engineering.md`（无源码 Windows 二进制的层判定、控制流、授权门/校验门定位、最小可回退探针候选）和 `mobile-reverse.md`（安卓抓包脱壳、mitmproxy 明文、过 SSL Pinning、Frida Hook）。**前端 JS 混淆还原、反调试/反虚拟机、动态 Hook 追踪具体参数没有方法书。** 矩阵写明这一格停在两本能给的位置，未知量进 `EXPERIMENTS.jsonl` 的 `remaining_unknowns`，**不许把「方法书没覆盖」写成「已解决」**；文件开头也放了要求的那句原文。
5. **有价值的正文没有掏空**：流量边界（`TEMP/traffic/<session_id>/`、`artifacts/`、`traffic_ok`）、因果对照（RED/GREEN、`causality_ok`）、发现优先（Observed→Hypothesis→Candidate→Validated→Final）、无硬编码凭据（`delivery_clean` / `clean_ok`、探针不许写死 true）、`能让人点就让人点` 那段，全部保留在矩阵正文里（`能让人点就让人点` 那段在旧段被归档的同时又在新矩阵末尾写了一遍，因为替换区间包含它）。
6. **归档注释会带进禁用词（只在源 SKILL.md 上用才会发生）**：要求是「旧段原文逐字存档」，所以若把补丁器用在**未剪的源 SKILL.md** 上，归档注释里会原样留下「控制台 / 副插件 / 不要照着名字」三行，验收 2 的扫描会命中。剪过版上跑就没有这问题（那两句本来就已经被剪掉了）。补丁器不做脱敏，这是设计取舍，报给主人定。
7. **方法书 front-matter 的 `phase:` 基本没列 `protocol-automation`**：只有 `mobile-reverse.md` 写的是 `phase: reverse-engineering, protocol-automation`；`reverse-engineering.md` 写的是 `phase: exe-rebuild`，`data-storage.md`、`release-readiness.md`、`review.md` 等也都只列了其他四条线。矩阵是按「能力类别」指向文件、不改 front-matter，所以功能上不受影响，但这是个待拍板的不一致。

## 7. 未确认的问题

1. 真目标文件 `02-hubcore/workflows/protocol-automation.md` **没被打上补丁**（只读约束）。要不要真打、什么时候打，由主人一句话决定，命令是：
   `python 03-bundle/patches/apply_matrix_fix.py --target work/context-isolation/02-hubcore/workflows/protocol-automation.md`
2. 上面第 6.2 条那 4 本计划外的方法书是否正式纳入 hubcore 的方法书清单，需要主人拍板。
3. `mobile-reverse.md` 的 `needs` 写明要「真机或模拟器 + adb + frida + mitmproxy」，本系统默认不联网、不装工具；这台机器上这本能不能真跑通，**未验证**。
4. `browser-automation.md` / `mobile-reverse.md` / `planning.md` 要不要补进 hubcore 的某个 manifest 或索引——我没动任何索引文件，只在矩阵里引用。
5. `INVARIANTS.md` 原文写的是「所有 skill 默认遵守的公共品质」，我在矩阵里改写成「方法书」。有没有别处依赖原文措辞，未查。
6. 补丁器保留了 CRLF 与无 BOM；别的编辑器再保存一次会不会改行尾，未验证。
7. `apply_matrix_fix.py` 只在 `protocol-automation` 这一份工作流上验过。另外五条产品线的工作流本轮没碰，不在这次范围内。

---

# 第二轮：六条线死链 / 死引用 / 能力缺口全检 + 定点修补

**结论：打补丁前 56 处真死链（路径解析不到 45 + 方法书写法错 11），11 次脚本调用改完是 0。六条线没有一条「无书可开」。被移出系统的能力（`github` / `own-skill`）正文里 0 处残留。**

详细规则表、逐条死链、POST_PATCHES 行，全部在 **`DEAD-REFS.md`**。这一节只放真跑出来的输出。

## 8. 校验器基线（真树，只读，退出码 1 = 有死链）

```text
基线合计：总 1730 / 通过 223 / 指向书 179 / 死链 45 / 写法错 11 / 移出书 0
无书可开：0 条
EXTERNAL(行内) tools/state.py ×2  tools/shift.py ×1  tools/hub_work.py ×1
            tools/hub_assertions.py ×1  tools/hub_cmds.py ×1  tools/hub_flow.py ×1  hub/ ×1
EXTERNAL(围栏) tools/state.py ×35  tools/map_show.py ×6  tools/feature_set.py ×2
```

## 9. 六条线前后对比表（`_report_table.py` 的真输出）

```text
线                    |   前 引用   前 通过    前 指向书   前 死链   前 写错 ||    后 引用   后 通过    后 指向书   后 死链   后 写错
----------------------------------------------------------------------------------------------------
desktop-product      |     94     14       11      0      0 ||      94     14       11      0      0
web-service          |     87     17       12      0      0 ||      87     17       12      0      0
cli-tool             |     81     12        9      0      0 ||      81     12        9      0      0
source-takeover      |     94     18       12      0      0 ||      94     18       12      0      0
exe-rebuild          |    186     11        5      3      0 ||     188     14        6      0      0
protocol-automation  |    142     22       13      0     11 ||     142     31       17      0      0
----------------------------------------------------------------------------------------------------
前 合计: refs 1730, ok 223, method 179, dead_link 45, loose_method 11, removed_book 0
后 合计: refs 1729, ok 270, method 224, dead_link 0,  loose_method 0,  removed_book 0
无书可开  前: []  后: []
docs/ 侧死链（打补丁后）: DEAD_LINK 无  LOOSE_METHOD 无
```

## 10. 11 次补丁调用的真输出（副本 `_acceptance/hubcore_after`）

```text
apply_protocol_automation_fix.py      规则「矩阵正文里的裸文件名方法书 → 裸书名」命中 11 次
  步骤1 apply_matrix_fix.py：[无改动] 已是新版矩阵   步骤2 改写 11 处涉及 4 行  20594→22399  226→234
apply_exe_rebuild_fix.py             2+1 命中  改写 3 处涉及 3 行    42749→44405   283→290
apply_invariants_fix.py              1+1 命中  改写 2 处涉及 2 行     8020→8594     70→76
apply_reverse_engineering_fix.py     4+1 命中  改写 5 处涉及 5 行    10680→11974   132→141
apply_review_fix.py                  7   命中  改写 7 处涉及 5 行    16452→17509   164→173
apply_browser_automation_fix.py      22+1 命中 改写 23 处涉及 21 行   8098→11174   124→149
apply_browser_automation_proof_fix.py 1   命中  改写 1 处涉及 1 行     3528→4029     80→85
apply_project_memory_fix.py          1   命中  改写 1 处涉及 1 行     8228→8915     84→89
apply_docs_audits_fix.py (OPERATING-MODEL)     1+1 命中 改写 2 处涉及 2 行 28863→29979 277→283
apply_docs_audits_fix.py (ENGINEERING-CONTINUITY) 1 命中 改写 1 处涉及 1 行 12581→13304  99→104
apply_docs_audits_fix.py (RESPONSIBILITY-PROTOCOL) 1 命中 改写 1 处涉及 1 行  9258→9853  88→93
```

**幂等复跑**：11 次调用全部输出「无改动」，全树 SHA256 逐文件比对一致 → 幂等成立。
**全量重建路径也验了**：造一个只含新版 `matrix.md` 的文件，`apply_protocol_automation_fix.py` 步骤 2 命中 0 次、文件零改动 → 新版 `matrix.md` 本身就不带裸文件名，重建路径安全。
**打补丁后的副本退出码**：`python check_dead_refs.py --root _acceptance/hubcore_after` → **EXIT=0**，真死链 0 处。

## 11. 这一轮我自己的两个错，记在案

1. **校验器早期版本在 `--root` 传相对路径时会凭空报「protocol-automation 无书可开」**——`resolve()` 拿绝对路径和未解析的 `--root` 比，`relative_to` 失败，方法书链接的 `hit` 变成绝对路径，「指向书」全线计 0。拿真树和副本对拍才发现（真树 87 本 / 副本 0 本）。已修（`main()` 与 `resolve()` 都 `resolve()`），修完逐文件差异 0。**没有这次对拍，这个假缺口会被当真的写进报告。**
2. **11 处「方法书写成裸文件名」是我上一轮自己写进去的**（`matrix.md` 正文里写成 `` `reverse-engineering.md` ``）。`matrix.md` 本身已改成裸书名，另外用 `apply_protocol_automation_fix.py` 修已经打过补丁的真文件，两头都堵。

## 12. 这一轮仍未确认 / 要主人拍板

1. **54 处 `tools/` 安装根引用**（`tools/state.py` 37、`tools/map_show.py` 6、`tools/feature_set.py` 2、`tools/shift.py` 1、`tools/hub_*.py` 4、`hub/` 1）：`02-hubcore/` 没有 `tools/`，`build_hubcore.py` 也从不搬它。谁负责装进中枢根，主人定；不装的话 AGENTS.md §9.2 的命令口径要改。**本轮没替主人决定，也没假装它成立。**
2. `POST_PATCHES` 是主人的字典，我没改 `02-hubcore/`。要加的 11 行（含替换 `workflows/protocol-automation.md` 那一行）见 `DEAD-REFS.md §8`。
3. `anti-crack-build` 六条线一次都没点名（on-demand）。要不要在某条线上补一句，主人定；本轮**没有**为了覆盖率硬塞。
4. `docs/methods/INVARIANTS.md` 还有别的旧词（「技能」）残留。本轮只改了和死链同一行的那一处口径词，没有全文换词——那属于改内容不是改死链。
5. 主人在这轮进行期间新增了 `02-hubcore/CORE.md`（6:53）并改了 `build_hubcore.py`（6:54）。本轮基线数字是在那之后重跑的，副本与真树逐文件差异 0；若主人还在改树，重跑一次 `check_dead_refs.py` 再决定。
