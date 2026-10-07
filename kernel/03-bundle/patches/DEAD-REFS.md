# DEAD-REFS —— 02-hubcore 死链 / 死引用 / 能力缺口 全表
> **这是一份带日期的验收快照，反映的是那一天的状态，不是现状。**
> 里面的数字（如文件大小、段数）**不要再引用**——那之后规则又改过好几轮。
> 要看现在是什么，读 [`01-design/当前实测基线.md`](01-design/当前实测基线.md)。



一句话结论：**打补丁前 56 处真死链（路径解析不到 45 + 方法书写法错 11），11 个脚本改完是 0；
六条线没有一条「无书可开」；被移出系统的能力（`github` / `own-skill`）正文里 0 处残留。**

校验器：`check_dead_refs.py`（只读，不改任何东西）。退出码 0 = 零死链。
复跑方式：

```text
python check_dead_refs.py --root <02-hubcore>          # 人看的表
python check_dead_refs.py --root <02-hubcore> --json   # 机器读
```

本轮所有改动都跑在副本上：`_acceptance/hubcore_before`（基线）与 `_acceptance/hubcore_after`（打过补丁）。
**真目标 `02-hubcore/` 全程只读，一个字节都没动。**

## 1. 判定规则（改规则必须同步改这份文档）

| 编号 | 规则 | 理由 / 依据 |
|---|---|---|
| R1 | 只收**行内反引号**里的记号 | 任务书要求「反引号包住的、看起来像路径的」 |
| R1b | markdown 链接 `[文字](目标)` 的目标**一律按解析判**，不给「系统外路径」「裸文件名」留逃生口 | markdown 链接的语义就是相对本文件的路径。`[hunt.md](hunt.md)` 这种不判就是漏 |
| R2 | 落在 `<!-- -->` 里的行不收 | 归档的旧原文不是活引用 |
| R3 | 记号至少有一段是 `名字.ext`（ext 限已知类型：md/py/jsonl/json/bat/cmd/sh/ps1/yaml/yml/txt/log/har/toml/ini/cfg/exe），或以 `/` 结尾且末段非空，才算路径 | `5/6`、`2-impl/3-build: business_flow`、`intent/constraints/rationale/sources`、`.bat/.cmd`、`/`、`/review` 都不是路径；`mission.success`、`arch.decision` 是字段名不是文件 |
| R4 | 含 `< > { } * …` → 占位符，不算死链 | 例 `` `templates/<产品线>.phases.json` `` |
| R5 | 运行期前缀（`TEMP/` `.hub/` `work/vX` `freeze/` `artifacts/` …）与**不带斜杠的裸文件名** → 运行期，不算死链 | hubcore 从不引用自己树里的裸文件名，裸文件名一律是产品侧/运行期的东西 |
| R6 | `tools/` `ctxiso/` `hub/` 开头 → 安装根/运行期脚本，单独列不判死链；首段不属于 `docs/ workflows/ templates/` 的路径 → 系统外路径（下游资料/本机工具/别人的仓库），单独列 | 见 §5、§6 |
| R7 | 本系统内路径：首段是 `docs/ workflows/ templates/`，或以 `../` `./` 开头 → 真去解析。**两个基准任一命中即通过**：B1=该记号所在文件的目录、B2=02-hubcore 根 | B2 的依据是 `AGENTS.md §9.2`：「命令里的路径一律写相对中枢根的」。只认 B1 会把 `docs/ENGINEERING-CONTINUITY.md` 全判成死链 |
| R7b | 围栏代码块里的 `python tools/xxx.py` 只计数不判死链 | 同一个安装根问题，单独列 |
| R8 | 裸书名 `[a-z][a-z0-9]*(-[a-z0-9]+)+`：`docs/methods/<名字>.md` 存在 → 通过；属于旧技能目录里**没搬进来**的名字 → 「本系统故意不带」，单独列 | 「移出名单」由 `build_hubcore.py` 的 `PARKED_REASON` + 旧技能目录实扫得出，不是手写白名单 |
| R9 | 裸 `xxx.md` 且 `xxx` 是本系统真实存在的方法书 → **写法错**（照字面解析不到），算进真死链但单列一类 | 表格里给路径、正文里用裸书名，才是本系统的统一口径 |
| R10 | 某条线指向的方法书数为 0 → 报「无书可开」（最严重） | |

**没有为了让校验器变绿而放宽任何规则**：改过三次判定逻辑，每次都是往严的方向（已知扩展名白名单、markdown 链接不许走逃生口、LOOSE_METHOD 独立成类），并且每改一次都重跑了基线数字。

## 2. 六条线：改前 / 改后

「引用」= 该文件里被收集到的记号总数；「指向书」= 其中能解析到本系统真实方法书的个数（**数的是"引用"，不是"该开哪本"**——正文里点名「别为了凑数打开」的那几本也会计进去）。

| 线 | 前 引用 | 前 通过 | 前 指向书 | 前 死链 | 前 写错 | ‖ | 后 引用 | 后 通过 | 后 指向书 | 后 死链 | 后 写错 | 无书可开 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| desktop-product | 94 | 14 | 11 | 0 | 0 | ‖ | 94 | 14 | 11 | **0** | 0 | 否 |
| web-service | 87 | 17 | 12 | 0 | 0 | ‖ | 87 | 17 | 12 | **0** | 0 | 否 |
| cli-tool | 81 | 12 | 9 | 0 | 0 | ‖ | 81 | 12 | 9 | **0** | 0 | 否 |
| source-takeover | 94 | 18 | 12 | 0 | 0 | ‖ | 94 | 18 | 12 | **0** | 0 | 否 |
| exe-rebuild | 186 | 11 | 5 | **3** | 0 | ‖ | 188 | 14 | 6 | **0** | 0 | 否 |
| protocol-automation | 142 | 22 | 13 | 0 | **11** | ‖ | 142 | 31 | 17 | **0** | 0 | 否 |
| **全树合计** | **1730** | **223** | **179** | **45** | **11** | ‖ | **1729** | **270** | **224** | **0** | **0** | 0 条 |

（45 处路径死链的分布：`workflows/` 侧 3 处（exe-rebuild）、`docs/**` 侧 42 处 = A 组 29 + B 组 4 + C 组 5 + D 组 4；另有 11 处写法错全在 `workflows/protocol-automation.md`。）

## 3. 逐个死链：56 处，按成因分 6 组

### A 组 · 目录式方法书主书里的附录链接全断（29 处）

`build_hubcore.py` 把目录式技能的 `SKILL.md` 拍平成 `docs/methods/<书名>.md`，附录进了 `docs/methods/<书名>/` 子目录，但主书里的相对链接没跟着改。

| 文件 | 行 | 死链 | 修法 |
|---|---|---|---|
| `docs/methods/review.md` | 20(×3) 42 73 75 76 | `[hunt.md](hunt.md)` `[review-table.md](review-table.md)` `[runtime-skins.md](runtime-skins.md)` | 加子目录前缀 → `](review/hunt.md)` 等，7 处 |
| `docs/methods/browser-automation.md` | 22 26 30 31 46 62 82–94 100 | 13 份附录的 `](catalog.md)` 等 | 加子目录前缀 → `](browser-automation/catalog.md)` 等，22 处 |

脚本：`apply_review_fix.py`、`apply_browser_automation_fix.py`

### B 组 · `../INVARIANTS.md` 指空（6 处）

真身是 `docs/methods/INVARIANTS.md`。原文按「同级」写，上跳一级到的是 `02-hubcore/` 根或 `docs/`，两处都没有这个文件。生成器的 `SUB_RULES` 只改写了 `<hub>/docs/...` 和 `<hub>/templates/...` 前缀，没管 `../INVARIANTS.md`。

| 文件 | 行 | 修法 |
|---|---|---|
| `workflows/exe-rebuild.md` | 71 139 | `` `../INVARIANTS.md` `` → `` `../docs/methods/INVARIANTS.md` ``（2 处） |
| `docs/methods/reverse-engineering.md` | 12 24 100 120 | `` `../INVARIANTS.md` `` → `` `docs/methods/INVARIANTS.md` ``（4 处，与 AGENTS.md §16 口径一致） |

脚本：`apply_exe_rebuild_fix.py`（只管前两条）、`apply_reverse_engineering_fix.py`（只管后四条）

### C 组 · 指向只存在于旧仓库的资产（6 处，全是「诚实的缺口说明」而不是换个假链接）

| 文件:行 | 死链 | 事实 | 修法 |
|---|---|---|---|
| `docs/methods/INVARIANTS.md:60` | `workflows/review/SKILL.md` | 生成器的路径改写规则只覆盖六条线，`review` 不在其中，原文照抄成了一条不存在的路径 | → `docs/methods/review.md`；同一句的旧词「活技能」→「活方法书」（AGENTS.md §9.2.7 本系统不读技能目录） |
| `docs/methods/reverse-engineering.md:51` | `../README.md`「没有匹配的 skill」 | 那是旧中枢外部库的能力对照表，随外部库一起移出了本系统 | 改成诚实说明：本系统没有这张表 → 先调查、写假设、做区分性实验 → 未知类型记进账本，不许套最近一行当已解决 |
| `docs/methods/browser-automation.md:56`、`docs/methods/browser-automation/proof.md:9` | `计票抄 [scripts/proof.py](scripts/proof.py)` | 原件 `hub/.agents/skills/browser-automation/scripts/proof.py` 确实存在（2178 字节），但生成器搬目录式技能时只 `glob('*.md')`，`scripts/` 整个没跟过来 | 改成诚实说明：计票脚本属于旧中枢、本系统没带，按下面这份规则自己写一份 |
| `workflows/exe-rebuild.md:246` | 模板见 `templates/memory-tree/CHANGES.md` | 原件存在（1781 字节），但生成器只 `copy2` `templates/` 根下一层 | 改成诚实说明：模板没带过来，上面那七项就是最低要求 |
| `docs/PROJECT-MEMORY.md:50` | `见 [变更示例](../templates/memory-tree/change.example.json)` | 原件存在（571 字节），同上没跟过来 | 改成诚实说明：示例文件没带过来，按同一句后面已写全的必填字段写齐 |

### D 组 · 指向旧项目的审计记录（4 处）

`hub/docs/audits/` 下原件都在（`REPORT.md` 23129、`BEHAVIOR.md` 5425、`VALIDATION.md` 11730 字节），但生成器只搬 `REQUIRED_DOCS` 那 6 份，`audits/` 整个没跟过来。`AGENTS.md §17` 明写本系统不背别的项目的包袱，所以**不搬、改成诚实说明**是正确处理。

| 文件:行 | 死链 | 修法 |
|---|---|---|
| `docs/OPERATING-MODEL.md:261` | `audits/20260913-redesign/BEHAVIOR.md` | 旧项目行为记录，本系统里以当前这次跑出来的实物与行为证据为准 |
| `docs/OPERATING-MODEL.md:265` | `audits/20260913-redesign/VALIDATION.md` | 同上 |
| `docs/ENGINEERING-CONTINUITY.md:3` | `audits/20260913/REPORT.md` | 那是旧项目的审计报告；旧需求与历史总结要查回旧仓库 |
| `docs/RESPONSIBILITY-PROTOCOL.md:3` | `audits/20260913-redesign/VALIDATION.md` | 同上 |

脚本：`apply_docs_audits_fix.py`（一个脚本三份目标，按文件名选规则）

### E 组 · 矩阵正文里的方法书写成了裸文件名（11 处）

**这 11 处是我上一轮自己写进去的**：`matrix.md` 正文里把方法书写成了 `` `reverse-engineering.md` `` 这种裸文件名，照字面解析，`workflows/` 下并没有这个文件。矩阵表格第三列已经给了相对路径，正文里说「哪本书」应该用另外五条线一直在用的裸书名（`reverse-engineering`）。

| 文件:行 | 死链 | 修法 |
|---|---|---|
| `workflows/protocol-automation.md` 214 | `reverse-engineering.md` `mobile-reverse.md` | 去掉 `.md`，用裸书名 |
| 215 | `browser-automation.md` `mobile-reverse.md` | 同上 |
| 216 | `planning.md` | 同上 |
| 217 | `project-init.md` `ui-design.md` `packaging.md` `performance-optimization.md` `windows-environment.md`（两次） | 同上 |

**双管齐下**：`matrix.md` 本身已改成裸书名（以后全量重建直接就是对的），再由 `apply_protocol_automation_fix.py` 修已经打过补丁的真文件。

### F 组 · 校验器自身的一个假阳性（记录在案，因为它差点造出一条假结论）

`check_dead_refs.py` 早期版本在 `--root` 传相对路径时，`resolve()` 拿绝对路径去和未解析的 `--root` 比，`relative_to` 失败 → 所有方法书链接的 `hit` 变成绝对路径 → 「指向书」全线计 0 → **凭空报出「protocol-automation 无书可开」**。是拿真树和副本两次结果对拍才发现的（真树 87 本 / 副本 0 本）。已修：`main()` 与 `resolve()` 都 `resolve()` 到绝对路径。修完真树与副本逐文件差异 = 0。**记录这条是因为：没有对拍，这个假缺口会被当成真缺口写进报告。**

## 4. 修法统计（副本上跑出来的真实数字）

| 脚本 | 目标 | 命中 | 字节 | 行 |
|---|---|---|---|---|
| `apply_protocol_automation_fix.py` | `workflows/protocol-automation.md` | 11 | 20594 → 22399 (+1805) | 226 → 234 |
| `apply_exe_rebuild_fix.py` | `workflows/exe-rebuild.md` | 3 | 42749 → 44405 (+1656) | 283 → 290 |
| `apply_invariants_fix.py` | `docs/methods/INVARIANTS.md` | 2 | 8020 → 8594 (+574) | 70 → 76 |
| `apply_reverse_engineering_fix.py` | `docs/methods/reverse-engineering.md` | 5 | 10680 → 11974 (+1294) | 132 → 141 |
| `apply_review_fix.py` | `docs/methods/review.md` | 7 | 16452 → 17509 (+1057) | 164 → 173 |
| `apply_browser_automation_fix.py` | `docs/methods/browser-automation.md` | 23 | 8098 → 11174 (+3076) | 124 → 149 |
| `apply_browser_automation_proof_fix.py` | `docs/methods/browser-automation/proof.md` | 1 | 3528 → 4029 (+501) | 80 → 85 |
| `apply_project_memory_fix.py` | `docs/PROJECT-MEMORY.md` | 1 | 8228 → 8915 (+687) | 84 → 89 |
| `apply_docs_audits_fix.py` | `docs/OPERATING-MODEL.md` | 2 | 28863 → 29979 (+1116) | 277 → 283 |
| `apply_docs_audits_fix.py` | `docs/ENGINEERING-CONTINUITY.md` | 1 | 12581 → 13304 (+723) | 99 → 104 |
| `apply_docs_audits_fix.py` | `docs/RESPONSIBILITY-PROTOCOL.md` | 1 | 9258 → 9853 (+595) | 88 → 93 |

合计改写 57 处（56 处死链 + INVARIANTS.md 同一行上的 1 处口径词），涉及 46 行。
**每个脚本都把改写前的原文逐字归档进目标文件末尾的 `<!-- hubcore: deadrefs-fixed-by ... -->` 注释块**，注释块内的行不参与改写，所以第二次跑零改动。

幂等复跑：11 次调用全部输出「无改动」，全树 SHA256 逐文件比对一致。

## 5. 「本系统故意不带的能力」 vs 「真死链」——分开列

### 5.1 明确移出、正文里已无残留（0 处）

`build_hubcore.py` 的 `PARKED_REASON` 只明写两个：`github`（云端发布工具，本系统不联网）、`own-skill`（技能系统，本任务排除）。旧技能目录实扫后，没搬进来的名字正好就是这两个。全树扫 `github` / `own-skill` 的行内引用：**0 处**（六条线原来点名 `github` 的那几行，在生成阶段就被 `LINE_FIXUPS` 换成了「本系统不联网、不代发」）。

### 5.2 修不掉的缺口：改成诚实说明，不硬塞不相干的书（共 5 类 10 处）

这些不是「引用写错了」，而是**本系统确实没有那个东西**。处理范本就是上一轮 `3-solve-re` 的做法：**这一格停在方法书能给的位置，未知量记进账本，不许写成已解决。**

| 缺什么 | 涉及处数 | 现在的说法 |
|---|---|---|
| 外部库「能力 → 深库」对照表 | 1（`reverse-engineering.md:51`） | 本系统没有这张表；先调查、写假设、做区分性实验，未知类型记进账本 |
| 计票脚本 `scripts/proof.py` | 2 | 属旧中枢，本系统没带；按本书这份规则自己写一份 |
| 改动图模板 `templates/memory-tree/CHANGES.md` | 1 | 模板没带过来；正文那七项就是最低要求 |
| 变更示例 `templates/memory-tree/change.example.json` | 1 | 示例没带过来；按同一句已写全的必填字段写齐 |
| 旧项目审计记录 `audits/**` | 4 | 属旧项目，本系统不背它的账；以当前这次跑出来的实物证据为准 |
| **矩阵里点名但这条线用不上的 5 本**（`project-init` `ui-design` `packaging` `performance-optimization` `windows-environment`） | 不算缺口 | 矩阵「矩阵的边界」里已点名说明「别为了凑数打开」，不是死链 |

## 6. 安装根 / 运行期脚本引用（不是本树死链，待主人拍板）

`02-hubcore/` **没有 `tools/` 目录**，`build_hubcore.py` 也只搬 `workflows / docs / templates / parked` 四处，从不搬 `tools/`。而 `AGENTS.md §9.2` 把「中枢根」定义为智能体家目录里的 `hub/`。所以下面这些引用在本树内解析不到，但不是死链：

| 记号 | 次数 | 位置 |
|---|---|---|
| `tools/state.py` | 行内 2 + 围栏 35 | 六条线的命令块 + AGENTS.md |
| `tools/map_show.py` | 围栏 6 | AGENTS.md |
| `tools/feature_set.py` | 围栏 2 | AGENTS.md |
| `tools/shift.py` | 行内 1 | AGENTS.md |
| `tools/hub_work.py` `tools/hub_assertions.py` `tools/hub_cmds.py` `tools/hub_flow.py` | 各 1 | `docs/RESPONSIBILITY-PROTOCOL.md:3` |
| `hub/` | 1 | `AGENTS.md:135`（说明中枢根就是家目录里的 hub/） |

**这 54 处要主人拍板一件事**：谁负责把 `tools/` 装进中枢根。装了就自动成立；不装，那这些命令在独立系统里就是跑不了的，AGENTS.md §9.2 得改成「本系统不带运行核脚本，命令占位等主人提供」。**本轮没有替主人做这个决定，也没有假装它成立。**

同类还有 `ctxiso/cli.py`（AGENTS.md §9.2.1 的 `pack` 命令），本树也没有 `ctxiso/`。

## 7. 系统外路径（下游资料 / 本机工具 / 别人的仓库，6 处，不是死链）

| 记号 | 位置 | 说明 |
|---|---|---|
| `接入说明/00-先读我.md` | `workflows/exe-rebuild.md:63` | 社区授权平台自己的下游资料，不在本系统内 |
| `browser-automation/scripts/setup.ps1`、`ida-reverse/scripts/install-autostart.ps1`、`kali/scripts/quick-setup.sh`、`bootstrap-reverse.ps1/.sh` | `docs/methods/reverse-engineering.md:43` | 同一句明写「**不跑** vendor 安装脚本」，是禁令里的名字，不是活指针 |
| `..._unprotected/` | `docs/methods/anti-crack-build.md:33` | 加壳留原件的目录约定，本系统没这个脚本在跑 |

## 8. 该在 `02-hubcore/build_hubcore.py` 的 `POST_PATCHES` 里加哪几行

那个字典是主人的，我只给行。**注意：`workflows/protocol-automation.md` 这个键已经存在，要把原来那行换掉**——字典不能一个目标两个键，而矩阵修补和写法修补都得对同一个文件跑（`apply_protocol_automation_fix.py` 内部第一步就调 `apply_matrix_fix.py`）。

```python
POST_PATCHES = {
    "workflows/protocol-automation.md":
        "03-bundle/patches/apply_protocol_automation_fix.py",   # ← 换掉原来的 apply_matrix_fix.py
    "workflows/exe-rebuild.md":
        "03-bundle/patches/apply_exe_rebuild_fix.py",
    "docs/methods/INVARIANTS.md":
        "03-bundle/patches/apply_invariants_fix.py",
    "docs/methods/reverse-engineering.md":
        "03-bundle/patches/apply_reverse_engineering_fix.py",
    "docs/methods/review.md":
        "03-bundle/patches/apply_review_fix.py",
    "docs/methods/browser-automation.md":
        "03-bundle/patches/apply_browser_automation_fix.py",
    "docs/methods/browser-automation/proof.md":
        "03-bundle/patches/apply_browser_automation_proof_fix.py",
    "docs/PROJECT-MEMORY.md":
        "03-bundle/patches/apply_project_memory_fix.py",
    "docs/OPERATING-MODEL.md":
        "03-bundle/patches/apply_docs_audits_fix.py",
    "docs/ENGINEERING-CONTINUITY.md":
        "03-bundle/patches/apply_docs_audits_fix.py",
    "docs/RESPONSIBILITY-PROTOCOL.md":
        "03-bundle/patches/apply_docs_audits_fix.py",
}
```

`_patchlib.py` 是这 10 个脚本的底座，必须和脚本放在同一目录（脚本用 `sys.path.insert(0, __file__.parent)` 导入它）。`_report_table.py` 只是出表用的，不进 POST_PATCHES。

## 9. 需要主人拍板 / 仍未确认

1. **§6 的 54 处 `tools/` 引用**：谁负责把运行核装进中枢根。这决定 AGENTS.md §9.2 那段要不要改口径。
2. `docs/methods/` 下 20 本里，`anti-crack-build` 六条线正文一次都没点名（它是 on-demand）。要不要在某条线上补一句，主人定；本轮**没有**为了「覆盖率」硬塞。
3. 方法书 front-matter 的 `phase:` 枚举基本没列 `protocol-automation`（只有 `mobile-reverse.md` 列了）。矩阵按能力类别指向、不改 front-matter，功能不受影响，但这是个待拍板的不一致。
4. `docs/methods/INVARIANTS.md` 里还有别的旧词残留（例如 INVARIANTS 正文提到「技能」的地方）。本轮只改了和死链同一行的那一处口径词，没有全文换词——那属于改内容不是改死链，要单独点头。
5. `02-hubcore/CORE.md`（2988 字节，6:53 新增）与被改过的 `build_hubcore.py`（6:54）是主人在我这一轮进行期间改的。本轮所有基线数字都是在**那之后**重跑的，副本与真树逐文件差异 0；但如果主人还在改树，重跑一次 `check_dead_refs.py` 再决定。
6. `02-hubcore/tools/`、`ctxiso/` 不存在这件事，**本轮一个字节都没往 `02-hubcore/` 写**。所有补丁脚本都还等着主人挂进 POST_PATCHES。
