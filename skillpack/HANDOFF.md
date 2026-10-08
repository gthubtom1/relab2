# 交接文档 — 融合技能包

**给新对话的第一份必读。** 读完本文再动手。

---

## 0. 三十秒版本

仓库：`D:\Project\skills-hub\integrated-skill-hub`
**最新提交、提交总数、工作树状态一律以当场查为准——本文不再写死这些数字**（写死必然过期，
本文是"新会话第一份必读"，过期的数字比没有数字更坏）：

```powershell
git log -1 --format=%h%n%s     # 最新提交
git rev-list --count HEAD       # 总提交数
git status --porcelain          # 空输出 = 工作树干净；有输出 = 有未提交改动（常见于多卡并行期间）
```

每个提交都经独立复算 + clone 到仓库外复核（逐波实测记录见 §2.1）。

**⚡ 先读这条：本仓库有"四把尺子"，别混用**（2026-10-02 05:45 独立复算）

| 尺子 | 文件/入口 | 现在成绩 | 量的是什么 |
|---|---|---|---|
| **官方基准**（182 条，关键词式） | `skills/tests/routing-benchmark.json` | **182/182 = 100%** | 照文档用词能不能路由对 |
| **自然说法基准**（86 条，口语） | `skills/tests/routing-benchmark-natural.json` | **76/86 = 88.4%** | 随口说人话能不能路由对 |
| **300 条大样本**（community 200 + canonical 100，难度均衡） | `work/natural-300/cases.json`（仓库外） | **297/300 = 99.0%**（canonical 100/100、community 197/200） | 最接近真实使用 |
| **读表对照**（模型只读入口文档） | `work/readtable-*`（仓库外） | 第一轮 91.0%（无索引）/97.7%（+索引）；第二轮同段对照 **87.3% → 94.0%**（文档修复后，见 §6） | 把表写厚能不能救回来 |
| **组外新说法**（100 条 hold-out，同技能换说法） | `work/round1-verify/holdout-100.json`（仓库外） | **26.0%**（干净子集 29.6%；canonical 51.3%、community **9.8%**） | **换了说法还认不认得**——99.0% 能不能外推 |

**最容易被误读的一行**：300 条的 99.0% 是**同一批字面**的成绩。同技能的 100 条**新说法**上，
正则路只剩 **26.0%**（读表盲判确认"语义没漂移"的 81 条干净子集上是 29.6%，社区侧 10.6%）。
同一批题上读表判定与答案键的一致率是 **81%** ⇒ **正则路是"同字面快速路径"，读表路才是泛化路径**。

**官方基准的 100% 不能当作"命中率 100%"汇报**——实测它 **178/182（97.8%）的题目直接包含
自己那条路由的 `must` 正则**（照答案问）。真实自然说法侧另有三把尺子。

**新会话开工顺序**：
1. 读本文档 §5 的「派发机制」——那里的规则被实测重写过三次，旧版本都是错的；
2. 跑一行探针测 `subagent` 是否可用（**当前首选项**：`axon/space-bunny-free` + `xhigh`；
   不工作再退 `axon/muse-spark-1.3-contributor-free` + `high`；深探禁令见 §5）；
3. 派单包在 `D:\Project\skills-hub\work\` 下（`wave1`…`wave8-briefs.md`、`dispatch-contract.md`、
   以及本轮 `round1-verify/card*.md`）——仓库外，故意不做 Markdown 链接（链接到仓库外文件会让
   `verify-doc-links.py` 正确判为断链）；
4. **当前状态**：27 张规范任务卡全部已开工并交付；门全绿 ≠ 项目完成——剩余的是
   **需 owner 裁决的登记项**（§6）与**社区路由剩余缺口**（28/300，本轮正在关闭）。

这是一个把 5 个开源技能包融合成一个"技能路由包"的项目。**CI 门全绿**。

> **门数唯一口径（2026-10-02 实测复核；文档里任何别的数字都以此句为准）**：
> `skills/tests/ci-gates.json` 共 **23** 门 = **21** 个 python 门（`run-ci-gates.py --runner python`
> 实跑的 `total=21`）+ **2** 个 `runtime: powershell` 门（`test-routing`、`verify-routing-coherence`，
> CI 里单独跑，**不进** `--runner python`，所以 `total` 永远比清单少 2）。
> 真树实测：`total=21 ok=21 non_blocking=0 skipped=0 blocked=0 failed=0`、exit 0。
> 看到"20 门""22 门"一律按历史残留处理，加/删门后必须回来改这一句。

本会话完成 wave 1–9：**T04/T05/T06/T10/T11/T12/T14/T15/T16/T17/T18/T19/T20/T21/T22/T23/T24/T25**、
**U1/U9/U10/U12 关闭**、**T13 的四条 P1**（P1-1/1-2/1-3 关闭、P1-4 机制就位）、
**U2/U3 与 T19 残留的闭环登记**，以及**社区路由关键词覆盖补齐**（用户点名的"路由完善"方向）。

**最重要的一条纪律（已按版本修正，见 §5.3）**：**禁止对真仓库执行
`scripts/adapt-community.py` 的写子命令**（`import` 非 dry-run / `promote` / `rollback`）。
旧版脚本没有 argparse，任何参数都会触发全量导入 + 删除（1111 条路径、不留备份）；
**重写后**（T05）只读子命令 `--help` / `inspect` / `verify` / `--dry-run` 是安全的。
一切写路径只许在**仓库外** lab 副本上验证。

**新增纪律一**：任何门都不能只看工作树。提交会把 CRLF 规范化成 LF（`.gitattributes eol=lf`），
所以"提交后的东西"和"你刚测的东西"不是同一串字节。最终版本需 clone 到仓库外重跑（见 2.1）。
**本会话这条纪律两次救场**（见 §5.1），且每次提交都照此复核（wave 1–9 全部）。

**新增纪律二**：**环境本身会漂移**。2026-09-30 一天内四起：DSH 重装、profile 由 `desktop`
改为 `web`、provider 由 `newapi` 改名 `axon`、bundled Python 运行时被删除。
2026-10-01 又起一起：**`space-bunny-free` 模型不稳定**（一轮四卡两死在 32–36 分钟处、
无收尾消息），已整体切换为 **`muse-spark-1.3-contributor-free`**（见 §5）。
派发前先验证解释器路径与 provider，**不要相信文档里写死的路径**。

**新增纪律三**：**新增文件在提交前无法被安全门扫到**（该门有 `.git` 时走 `git ls-files -s`，
未跟踪文件不在 index 里）。**已两次致事故**（`SECURITY-SCAN.md` 一次、`CROSS-REVIEW-WAVE12.md` 一次），
两次都是先提交、再被 clone 复核抓回。因此：**每波提交后必须 clone 复核**，
且派单必须带"危险样本掩码"条款。详见 §5.1/§5.2。

---

## 1. 这个项目在做什么

把 5 个上游技能包融合成一个包，让 AI 助手接到安全/逆向任务时能找到对的技能。

| 上游仓库（快照在 `D:\Project\skills-hub\upstream\`） | commit | 贡献 |
|---|---|---|
| `reverse-skill`（母框架） | `cab634bd…` | 43 个核心技能 + 行为链契约 |
| `ctf-super-hub` | `16926d6d…` | 35 个 CTF 技能 |
| `hack-skills` | `6fbf0bc8…` | 103 个 Web/API/AD/云技能 |
| `AI-Fullstack-Delivery-Workflow` | `ab96b897…` | 154 个交付技能 |
| `apk-reverse` | `7b6c6932…` | 1 个 APK 技能 |

融合后规模：**43 个核心技能 + 4 个 wrapper + 293 个社区技能**。

### 架构（关键，别搞错）

```
skills/                          ← 客户端发现根
├── api-security/ … (43 个)      ← 核心技能，可直接调用
├── community/
│   ├── ctf-hub/SKILL.md         ← wrapper（4 个，唯一可发现的社区入口）
│   ├── hack-hub/SKILL.md
│   ├── delivery/SKILL.md
│   └── apk-extension/SKILL.md
└── INDEX.md                     ← 只列 46+4 个

community-raw/                   ← 仓库根，在发现根之外
├── hack-skills/ … (103 个)
├── ai-fullstack/ … (154 个)
├── ctf-super-hub/ (35 个)
└── apk-reverse-source/ (1 个)
```

**为什么 raw 内容在 `community-raw/` 而不是 `skills/community/`**：
客户端会递归扫描 `skills/**`。raw 内容放在里面就等于"助手能看到 343 个技能"，而不是 50 个，
助手会挑到未适配的原始剪报。规范 17.27 要求**物理隔离**，靠 `user-invocable: false`
这类 frontmatter 标记**不算**。

**这个搬迁已经完成并验证**。相关记录见 [DISCOVERY-ISOLATION.md](docs/community/DISCOVERY-ISOLATION.md)。

---

## 2. 当前状态（全部为实测值）

### 门禁

**统一入口**（推荐；它读 `skills/tests/ci-gates.json` 清单，带 digest 锁）：

```powershell
$env:PYTHONIOENCODING='utf-8'
D:\EXE\python\python.exe skills\tests\run-ci-gates.py --runner python
# 真树（有 ../upstream 快照）: total=21 ok=21 non_blocking=0 skipped=0 blocked=0 failed=0, exit 0
# clone 到仓库外（无快照）  : total=21 ok=17 non_blocking=3 skipped=1 blocked=0 failed=0, exit 0
```

（两行的 `total` 都是 21 = 清单 23 门减 2 个 powershell-runtime 门；clone 侧数字是
2026-10-02 在 `work\round1-verify\lab-cardK\clone-fixture` 的一次**实测**，不是推算。
清单增删门后这两行都会变，届时必须重跑、不得只改 `total`。）

`clone` 与真树的差异**全部是已登记的**：三个门（`verify-triage-lock`、`verify-source-attestation`、
`verify-canonical-base-lock`）因缺 `../upstream` 降级为 exit 10（非阻断），
`test-adapt-community` 因 `requires_upstream_snapshot` **响亮跳过**（打印缺哪个目录、计入 skipped）。

| 门 | exit | 说明 |
|---|---|---|
| 规范结构 | 0 | 编号连续性、交叉引用；`task_cards=27` |
| 发现面 | 0 | 递归发现 50 = 期望 50 |
| 登记表锁 | 0 | 防自我豁免；**有 `--snapshot-root`**（无快照时具名降级为 10，见 2.1） |
| 社区横幅 | **0** | U1 已关闭（15 个 vendored 文档补齐且登记为受管变换） |
| **source attestation（新）** | 0 | T12+T14。无快照时 exit 10 具名降级 |
| **community bundle（新）** | 0 | T12+T14。无 `.git` 时 exit 10 |
| **canonical base lock（新）** | 0 | T21。`--require-signatures` 真树 exit 20（无签名拒入 redistributable） |
| 信号层 | 0 | 12 项 fail-closed |
| 信号层负向对照 | 0 | 13 项对照 + no-op 变异自检 |
| 契约 v2 | 0 | registry 合同 + 4.6 迁移 + 3 个 schema |
| 社区路由 | 0 | |
| 排序专项 | 0 | 名字/描述匹配 + 四个缺陷守卫 |
| 社区诱饵 | 0 | 57 用例，双侧独立设阈；**当前 decoy 25/30=0.8333** |
| frontmatter | 0 | 59 断言 |
| 接线自检 | 0 | 交叉校验"清单里每门都被 workflow 调用" |
| 集成校验 | 0 | **sources=5**（含 canonical base）、`skill_scoped=292`（有意） |
| 文档链接 | 0 | active=0 wrapper=0，13 条 provenance 已登记 |
| 仓库安全 | 0 | `secrets=0`、`injection_shapes=9`、`vendored_router_files=70` |
| **release gate（新）** | 0 | T04。`--release` exit 20（设计态，属人工门，**故意不接 CI**） |
| **adapt-community 套件（新）** | 0 | T05。**87/87**；无快照时响亮 SKIP |
| 主路由 | 0 | **182/182** |
| 路由一致性 | 0 | ALL PASSED |

### 2.1 在仓库外复核最终提交（**每波必做**）

提交会把 CRLF 规范化成 LF，所以工作树通过不等于提交内容通过。**这条纪律已多次救场**：
`SECURITY-SCAN.md`（T06）与 `CROSS-REVIEW-WAVE12.md`（T13）都因为把危险样本字面量原样写进文档，
在**提交后**才被安全门抓到——而它们在提交前对门不可见（门走 `git ls-files`，未跟踪文件不在 index 里）。

所以：**每波提交后必须 `git clone` 到仓库外重跑全门，并把差异逐条归因**。
已按此复核 wave 1–17 全部提交。

> **下面 wave 17 / wave 18 的 `total=20 ok=16` 是那两个时间点的历史实测，刻意不改**——
> 改了就等于伪造当时的测量记录。门数在之后加过（`verify-evolution` 入清单，22 → 23 门），
> 同口径下现在的对应数字是 §2 门禁节里的 `total=21 ok=17 non_blocking=3 skipped=1`
> （2026-10-02 clone 实测）。**读历史 wave 记录时按当时口径读，别和当前口径混算。**

**wave 18 实测（`170a5f4` → `work\verify-commit-wave18`）**：

```powershell
git clone --quiet --no-hardlinks D:\Project\skills-hub\integrated-skill-hub <lab>
cd <lab>; D:\EXE\python\python.exe skills\tests\run-ci-gates.py --runner python
# total=20 ok=16 non_blocking=3 skipped=1 blocked=0 failed=0   exit 0
powershell -File skills\scripts\test-routing.ps1         # TOTAL=182 PASS=182   exit 0
powershell -File skills\scripts\test-routing-natural.ps1 # PASS=76  exit 1（脚本语义：有失败即 1）
python <lab>\measure-comm-wave18.py                      # community loose 197/200（与真树逐项一致）
```

**三个 `exit 10` 与一个 `SKIP` 全部是已登记降级**（缺 `../upstream` 快照），在 clone 里出现属预期，不是回归；
LF 规范化不影响任何行为（`routing-signals.json` 64564 字节、无 BOM、197/200 复现）。

**wave 17 实测（`1ca4cc3`）**：

```powershell
run-ci-gates.py --runner python  # total=20 ok=16 non_blocking=3 skipped=1 blocked=0 failed=0  exit 0
test-routing.ps1                 # 182/182  exit 0
test-routing-natural.ps1         # 76/86    exit 1（脚本语义：有失败即 1）
```

三个 `exit 10`（`verify-triage-lock` / `verify-source-attestation` / `verify-canonical-base-lock`）
与一个 `SKIP`（`test-adapt-community`，缺 `../upstream` 快照）**全部是已登记的降级**，
在 clone 里出现属预期，不是回归。

### 2.1.1 一条仍然成立的结论：独立复制不能复核 provenance

`verify-triage-lock` / `verify-source-attestation` / `verify-canonical-base-lock` 三个门在**没有
`../upstream` 快照**时会具名降级为 `exit 10`（脚本自己在文档里写明），`test-adapt-community`
响亮 SKIP。也就是说 **"单独复制 integrated-skill-hub 即可复核 provenance" 当前仍不成立**：
需要那 5 个只读上游快照。任何"克隆即可复核"的说法都必须先过这一关。
这不是回归，是 T12 验收项的直接证据，已如实登记。

### 2.2 核心检索能力（实测抽验）

| 查询 | 结果 |
|---|---|
| `kerberos` | matched → `active-directory-kerberos-attacks` |
| `服务端请求伪造` | matched（带 source 过滤时 `ssrf-server-side-request-forgery` rank 1） |
| `bloodhound` | **matched**（本轮前是 needs_review / 0 引用） |
| `mimikatz` / `certipy` / `dcsync` | **matched**（本轮前 0 引用） |
| `lattice` / `pcaps` / `yaras` | **有引用**（本轮前 0 引用） |
| `workflow` / `adapted` / `capability` / `community-raw` / `skills-hub` | **missing_input**（本轮前是 matched / confidence 1.0） |
| `s3 bucket` | needs_review / 0 引用 —— **正确**：293 条语料里没有任何 S3/对象存储技能 |
| slug 自召回 | 187/293 → **274/293** |
| 38 个命名探针零引用 | 7 → **1** |

---

## 3. 已完成的工作（按提交顺序）

| commit | 内容 |
|---|---|
| `4039716` | 规范章节重排（把 17.14–17.26 从第 19 节之后移回第 17 节） |
| `93a0a4f` | 第 4 节机器合同冻结 + 17.27–17.32 补充 + 12.0 单写者登记表 |
| `b9eba03` | 规范结构校验器 + 发现面证据 |
| `9b1053d` | 发现面审计脚本 + CR-001 迁移方案 |
| `cec3d13` | 按独立实测校正 4 条错误口径 |
| `09739f8` | **堵住断链门的自我豁免漏洞** + 登记表摘要锁 |
| `c9b8303` | 社区回归守卫 |
| `34c7cde` | 消除规范三处自相矛盾 |
| `967e4d1` | **T02**：registry v2 契约 + handoff schema + profile 迁移 |
| `686796d` | **T03**：断链 342 → 13 |
| `37d98a4` | **T07/08/09**：APK 悬空路径、Delivery 旧框架引用、131 处加载指令 |
| `bc89672` `dd7e291` | 协调板 + 守卫修正 |
| `84c8ea1` | 规范 2.3 改为冻结布局 + T05 写入根同步要求 |
| `6fd11ab` | **子代理派发规则**（必须 space-bunny-free） |
| `0a36a65` | **T01 物理隔离 + kq-01 描述解析 + kq-02 排序修复** |
| `44592e9` | 新增本文档 |
| `f043236` | **T26 社区路由信号层**：D1–D9 修复 + 28 条策展信号 + 57 个诱饵用例 + 2 个新门 + 补规范任务卡 |

### 3.1 社区路由攻坚（`1397d7f` → `1ca4cc3`，30 个提交，全部已 clone 复核）

这一段是本项目**能力提升最大**的一段：300 条大样本从 **19.7% → 99.0%**（round-1 收口见 §6）。

| 阶段 | 提交（代表） | 一行 |
|---|---|---|
| 两把尺子 + 缺口结构 | `bbf76c7` `38a3dee` | 官方 182 是"照答案问"；自然 86 只有 54；缺口分 T1–T6 类 |
| 入口文档打通（U18） | `entry-docs2` 系列 | `AGENTS.md`/`CLAUDE.md`/`MASTER-ROUTING.md` 写明"两条路"，`community-route` 提及 0 → 18 |
| 词表 + 症状索引 | `e21f7e6` `13b7ea8` `ebc79f0` | 51 个 ALIASES 键 + 社区症状索引 478→878 行（293 技能全覆盖） |
| signals 层扩容 | `9272d54` `e21f7e6` | signals 28 → 104 → 118（schema maxItems=128） |
| 300 条爬坡 | `b14a9b3` 等 | 19.7% → 56.3% → 68.7% → 90.3% → 90.7% → **99.0%**（canonical 100/100、community 197/200） |
| 边界判据（R46/R47/R49） | `717527f` `a9c9fe4` | `routing.md` +157/−5；19 条误判从 0/19 → 14/19（独立盲读验证） |
| wrapper 平局破法 | `9d4171a` | 平局改用**字段适配**（rank_score/name_hits）而非路径字母序：29 条 top 命中 11→15（净 +4） |
| N267 回归修复 | `8e346bf` | CTF 语境正则（两个 lookahead 同现，40 字窗口），爆炸半径 8 条 → 1 条 |

**关键认知（U27/U29 记录）**：canonical 侧"正则 47% vs 读表 97%"——**不该用正则去模拟"理解"**，
该把表写好让模型读。**但 round-1 之后两条路分开了**：补完数据桥与信号层，**正则侧 297/300 = 99.0%**，
而读表侧 269/300 = 89.7%（失分集中在文档那条 F4 兜底，账见 §6）。

### 三个值得一提的成果（本轮）

**① D1：kq-02 自己加的加宽是死代码。** `lookup()` 用严格令牌集的 `_score()` 决定候选
（`community-route.py:589-591`），而 `_name_view()` 的加宽只在 gate 之后的 `_rank()` 里被查询。
实测：293/293 条记录带 1748 个仅加宽可达的令牌，**87 条记录无法成为自身 slug 的候选**，
`lattice` 加宽命中 1 条而引用 0 条。修法是一个 `routing_view` 同时决定候选与两类命中。

**② D8：这个仓库从来没有负向用例。** 182 个 L1 用例 + 13 个 L2 用例全是"必须命中"型，
所以 D5/D6 这类过宽规则对**所有门**都不可见。实测证据：裸词 `workflow` 曾以
`confidence=1.0` 命中 154/154 条 ai-fullstack 记录；`community-raw` / `skills-hub` 命中 293/293。
本轮引入 57 个诱饵/正向用例，两个门（0.50 / 0.75）**故意压在实测值之下**，因此新过宽规则会让
数字变动，而既有失败逐条具名留在输出里。

**③ 本轮自己引入又自己修掉的两个过宽规则。** `ai` 作为短令牌让路由视图把 `ai-fullstack`
切出 `ai`，成为 weight-3 的**名字级**命中，覆盖 157/293 条；`adapted`/`capability` 因 30 条
合成描述命中 ai-fullstack。两个都是本轮改动引入的，独立复算后移除。详见缺陷记录 E27/E28。

**① 发现隔离（T01）**：raw 内容搬到 `community-raw/`，递归发现从 **343 → 50**。

**② YAML 折叠描述解析（kq-01）**：293 条技能里 **103 条**描述原本是字面的 `>-`
（YAML 折叠指示符没展开），另有 16 条没去引号。修完后指示符残留 **0**、空描述 **0**。
这个问题同时卡死了两种客户端加载方式——没有描述的技能，agent 永远选不中。

**③ 排序缺陷（kq-02）**：修好描述后暴露出来的。hint "服务端请求伪造" 只有 1 个 token，
6 条记录并列 score=1，按路径字典序破平，真正的 SSRF 技能排第 5 被 `references[:3]` 截掉。
**这说明那个测试过去是"靠坏数据通过"的。** 修复引入 field-aware 排序（名字命中权重 3、
描述命中权重 1），并附 8 个"防过度收窄"常驻用例。

---

## 4. 协调板与规范

| 文件 | 作用 |
|---|---|
| [CAPABILITY-REPORT.md](docs/CAPABILITY-REPORT.md) | **对外可引用的能力结论**（四把尺子 + 泛化边界 + 操作命令 + 已知边界）——要给外人看数字时用这份 |
| [WORK-BOARD.md](docs/WORK-BOARD.md) | **必读**。基线、E1–E28 已实测证据、C1–C9 校正、CR-001~004、U1–U33 已登记未修项、冲突登记 |
| [INTEGRATION-IMPLEMENTATION-SPEC.md](docs/INTEGRATION-IMPLEMENTATION-SPEC.md) | 冻结合同 + 任务卡 T00–T26 + 发布门 |
| [docs/community/ROUTING-SIGNAL-DEFECTS.md](docs/community/ROUTING-SIGNAL-DEFECTS.md) | **本轮新增**。D1–D9 缺陷登记 + 前后实测对照 + 仍未关闭项 |
| [docs/community/ROUTE-RANKING.md](docs/community/ROUTE-RANKING.md) | **本轮新增**。排序模型、归一化、信号层契约、诱饵方法论 |

规范结构：0–21 节，17.1–17.32 共 32 个补充硬门，**27 张任务卡**。
用 `verify-spec-structure.py` 校验，改规范后必跑。

---

## 5. 高危事项（务必遵守）

### `scripts/adapt-community.py` 禁止执行

实测：单次运行覆盖 **1111 条路径**（1087 个 skills/community → 现已变 community-raw、
23 个 docs/community、registry.json），以纯净上游原文覆盖，**不留 diff、不备份、无 digest**。

**旧版**没有 argparse：`--help`、拼错参数、CI 误传都会触发全量导入 + 删除。
**T05 已重写**（wave 1）：现在是五子命令（`inspect`/`import`/`verify`/`promote`/`rollback`）+ argparse，
`--help` 纯打印、`inspect`/`verify` 只读、`--dry-run` 实测零写入。
**但禁令仍然成立，只是范围收窄为写子命令**：

> **禁止对真仓库执行 `import`（非 dry-run）/ `promote` / `rollback`。**
> 只读子命令（`--help` / `inspect` / `verify` / `--dry-run`）允许。
> 一切写路径只许在**仓库外** `D:\Project\skills-hub\work\<卡名>-lab\` 的副本上验证，
> 并证明真仓库逐字节未变（`git status --porcelain` 空 + 6 个基线哈希不变）。

**双重风险（旧版）**：它输出的还是 **v1 形状的 registry**，跑一次会同时
(a) 抹掉 T01 的物理隔离（把 raw 内容写回 `skills/`）、(b) 删掉 T02 加的 v2 字段。
**重写版**写入根指向 `community-raw/`，且有受管变换层 + journaled promote/rollback。

守卫能发现回退：`verify-community-banner.py`（横幅与加载指令）、`audit-discovery-surface.py`（隔离）。

### 派发机制（2026-10-01 第二次实测重写；上一版结论也已作废）

**旧规则（两版都作废）**：
- 第一版说「`subagent` 没有 model 参数所以禁止使用」——错，它有 `provider`/`model`/`reasoning_effort`。
- 第二版说「`subagent` 在本环境被 profile 显式禁用」——**也已作废**：它引用的
  `@deepseek-ai/dsh-experimental-agent-team-profile` **在当前 web profile 下已不存在**
  （`node_modules\@deepseek-ai\` 下没有它），那段 `disabled: true` 本会话根本没被加载。

**本会话实测结论（2026-10-01）**：

| 检查 | 结果 |
|---|---|
| `subagent` + `axon/space-bunny-free` 探针 | **通过**，返回预期值 |
| `subagent` + `deepseek-account/deepseek-flash`（负向对照） | **被拒**：`child LLM route ... is not allowed for this Session` |
| 拒绝来源 | `profiles\web\cordis.patch.yml` 的 `subagent-model-selection-settings.allowedModels` |
| 结论 | **`subagent` 可用**，且模型合规由 `allowedModels` **配置强制**（并非靠自觉；派 deepseek 会硬报错，不会静默降级） |

**因此本项目的派发通道 = `subagent`**，每条**必须**显式带 provider / model / reasoning_effort。
**当前顺序（2026-10-02 主人指定）**：① `provider: "axon"`、`model: "space-bunny-free"`、`reasoning_effort: "xhigh"`；
② 不工作时退 `muse-spark-1.3-contributor-free` + `high`。**禁止任何 DeepSeek 模型**（配置强制：
`profiles\web\cordis.patch.yml` 的 `allowedModels` 只列 axon 两个路由，派 deepseek 会硬报错）。

**不要用 `spawn_teammate`（Agent Teams）**：它**没有 `model` 参数**，无法固定模型。
**不要用 `subagent_fork`**：它继承本会话上下文，也就继承了 Lead 的模型。

**模型在会话中途换过一次**：`space-bunny-free` 一轮四卡**两死**（均在 32–36 分钟处、
无收尾消息），当时整体切换为 **`muse-spark-1.3-contributor-free`**。
**2026-10-02 主人指示恢复 `space-bunny-free`/`xhigh` 为首选**，失败即退 2 号（`muse`/`high`），
不在同一模型上反复重试。注意 `muse` 路由的 `reasoningEfforts` 最高档是 `high`
（`xhigh` 是 `space-bunny-free` 独有档）。

**provider 与模型名都是可变的，派发前必须探针。** 2026-09-30 实测 `newapi` → `axon` 改名时，
失败是**静默的**（子代理返回 `null`，不报错、不写文件、`git status` 干净，极易误判成「任务太难」）。
批量派发前先跑一行探针（读一个已知数字）。

**Python 解释器也变过**：旧的 `C:\Users\Toti\.dsh\dsh-runtimes\...\python.exe` **已被删除**。
现在用 `D:\EXE\python\python.exe`（3.12.0）。

**派单包**在 `D:\Project\skills-hub\work\`（仓库外，故意不做 Markdown 链接——链接到仓库外文件会让
`verify-doc-links.py` 正确判为断链）：`wave1-briefs.md` … `wave7-briefs.md`，
另有一份**派发契约** `dispatch-contract.md`（通道 / 六项必带 / 七标题回报 / 三条纪律）。

---

## 6. 下一步工作（2026-10-02 更新）

### 当前主线：300 条大样本剩余缺口（**272/300 → 297/300，剩 3 条**）

**2026-10-02 早间一轮（round 1）把 28 条缺口关到 3 条**：

- 起点（HEAD `1ca4cc3`，协调者独立复算）：canonical 100/100、community 172/200、总 **272/300 = 90.7%**。
- 诊断：28 条里 **24 条 NO-CANDIDATE**（期望记录根本不在候选集）+ 4 条在候选但被 `references[:3]` 截断。
- **卡 A（signals 域）**：给 7 条已有 entry 的记录扩 `must[]`（不占额度）+ 新增 10 条 entry，
  `signals` 118 → **128**（正好用满 schema `maxItems`）；54 条新正则，最长公共连续汉字 **3**（< 6 硬门）。
- **卡 B（数据桥域）**：`community-route.py` 的 `ALIASES` 纯追加 22 组中文说法（blast 全 ≤ 6），
  记录侧靠自身 slug 天然满足双边折叠，**registry.json 零改动**。
- 结果：community 172 → **197/200**，总 **272 → 297/300 = 99.0%**，top1 命中 153 → **170**；
  官方 182/182 与自然 76/86 一条没掉。

**剩余 3 条（已具名登记，不硬塞）**：`N131`（graphql-and-hidden-parameters）、`N180`（xxe）、
`N213`（登录态在网页与接口之间传丢）。卡 B 实测原因：**桥本身已成立**（各自 name view 命中 rank=3），
但同一 wrapper 内另有 4–6 条同 rank 记录，`_reference_sort_key` 的 path 末位把它们压在前面，
`REFERENCE_LIMIT=3` 一截就掉出去 —— 要救只能动 `REFERENCE_LIMIT` 或再加一次命中，**两者都属硬约束禁止项**。

**复测命令**（协调者口径）：
```
D:\EXE\python\python.exe work\round1-verify\measure-comm.py --out <名字>.json   # community 200，约 3–5 分钟
D:\EXE\python\python.exe work\round1-verify\measure300.py                       # 全套 300
```

**下一轮候选**（都有实测支撑，已登记）：
1. `signals` `maxItems` 128 → 更高？**上界实验**：给 28 条各注入一条必然命中的 signal，**28/28 都能进 references**
   （`work/round1-verify/signal_ceiling.py`）。若提额，可再关若干条；改 schema 属机制改动，**需 owner 裁决**。
2. **F4 兜底回归**：读表盲测第二轮，`routing.md` 的「无强锚点 → 改判 R47」把 9 条 hack 题带偏成 ctf
   （第一轮这 9 条是对的）—— 与第一轮修好的 19 条相加，**改回"只标 uncertain 不硬判"可达 150/150**。
3. 文档与答案键的其余冲突（截面上仍是 R0/R6、R44/R11、R17/R46 三组）。

**硬约束不变**：官方 182/182 与自然 ≥76/86 全程不许退化；不许为变绿改测试或降阈值；
不许动 `MIN_CONFIDENCE` 与权重常量（无独立实验支撑且无 owner 裁决时）。

### 泛化边界（hold-out 实测，2026-10-02 round-2）

300 条 297/300 是**同一批字面**的成绩。为回答"能不能外推"，本轮造了一批**组外新说法**
（`work/round1-verify/holdout-100.json`：从 300 条里按 id 均匀取 100 条，**同 expect、题面重写**，
与原题面最长公共连续汉字 ≤ 5、与技能名 ≤ 2），再用**另一张卡盲读入口文档**独立判定（不看答案键）：

| 子集 | 条数 | 正则路命中 | canonical | community |
|---|---|---|---|---|
| 读表盲判与答案键**一致**（语义没漂移） | 81 | **29.6%** | 55.9% | **10.6%** |
| 读表盲判与答案键不一致（争议样本） | 19 | 10.5% | — | — |
| 全集 | 100 | **26.0%** | 51.3% | 9.8% |

**读表盲判与答案键的一致率 81%** —— 即新说法多数没改变语义，**桥不泛化才是主因**。

**结论与纪律**：
1. **报 300 条 99.0% 时必须同时报这个 26.0%**，否则是用训练集成绩冒充能力；
2. **不要为下一批新说法再补一轮词表**——那是把过拟合往后挪一批（本项目已记录"拿考卷当教材"是假收益）；
3. 包里现成的正确协议就是 `AGENTS.md` 的"未命中三步"：正则命中直接用（43ms），
   `low`/`no_match` 就补问、标不确定、或改读表——**hold-out 证明读表路（81%）比正则路（26%）更能认新说法**。

### 融合新包的标准流程（命令级，2026-10-02 实测）

**0. 环境**：`$env:PYTHONIOENCODING='utf-8'`；Python 用 `D:\EXE\python\python.exe`（3.12.0，纯标准库）。

**1. 改之前先冻基线**（五条，全部记录数字；数字必须与当次实跑一致，不许沿用上一轮的）：

```powershell
D:\EXE\python\python.exe skills\tests\run-ci-gates.py --runner python        # 期望 total=21 ok=21（清单 23 门，见 §0「门数唯一口径」）
powershell -NoProfile -ExecutionPolicy Bypass -File skills\scripts\test-routing.ps1          # 182/182
powershell -NoProfile -ExecutionPolicy Bypass -File skills\scripts\extract-summaries.ps1 -Check  # INDEX.md 是生成物：exit 0 才算与 SKILL.md 同步（CI 唯一检查它的一步）
powershell -NoProfile -ExecutionPolicy Bypass -File skills\scripts\test-routing-natural.ps1  # 76/86
D:\EXE\python\python.exe D:\Project\skills-hub\work\round1-verify\measure300.py               # 297/300
```

**2. 按目标改文件（各自是唯一事实源）**：

| 要改的能力 | 改哪里 | 改完必跑 |
|---|---|---|
| 主框架路由（R0–R49） | `skills/config/routing.json` | `verify-routing-coherence.ps1` |
| 社区"说法→记录"的桥 | `skills/scripts/community-route.py` 的 `ALIASES`（**双边折叠**：说法进 ALIASES，canonical 字面必须在记录侧真实存在） | `test-route-ranking.py`、`test-community-decoys.py` |
| 记录级语境正则 | `skills/community/routing-signals.json`（`must`/`exclude`；`maxItems=128` 是硬顶，扩已有 entry 的 `must` 不占额度） | `verify-routing-signals.py --check` |
| 读表侧（模型只读文档） | `skills/routing.md`、`skills/MASTER-ROUTING.md`、`skills/SYMPTOM-INDEX*.md` | `verify-doc-links.py`、`verify-spec-structure.py` |

**3. 新包自检（10 项机器门）**：`python scripts/verify-evolution.py`（默认约 3 分钟；`--full` 追加全量 182 与 smoke）。

**4. 收口**：重跑第 1 步四条 → `git commit` → **clone 到仓库外把第 1 步再跑一遍**
（`.gitattributes` eol=lf 会在提交时把 CRLF 换成 LF，字节变了，行为必须复现）。

**5. 三条硬纪律**：① 任何 JSON 落盘**必须无 BOM**（BOM 会让 `community-route.py` 直接 `blocked`，
实测把社区侧从 172/200 打到 78/200）；② 不删用例、不降阈值、不动 `MIN_CONFIDENCE` 与三个权重常量；
③ 每个数字都要能独立复算——子代理自述不算数（本项目已多次抓到自述与实测不符）。

**6. 三条"看起来像收益其实不是"的操作（已拒绝，别重做）**：调 `MIN_CONFIDENCE`
（净收益 −17）；拿 86 条自然基准当训练集（过拟合）；为凑分破坏 CTF 入口设计。

### 未开工的任务卡：**归零**

27 张规范任务卡**全部已开工并交付**（其中 T13 的四条 P1 与本会话各 wave 的收尾均已闭合）。
本会话新增的两张派生卡（T17/T25 之外的"社区路由覆盖补齐"与"历史遗留收尾"）也已完成。

### 剩余工作全部是"需 owner 裁决"或"已具名登记"，不是没人做

1. **U11 余项 / U14**：生产记录下 `promote` 仍被拒（apk=11 / ctf=13 / hack=141 / ai=137，
   全量 302 恰为四者之和）。需各域 owner 决定这些改动是否登记为受管变换；license 行方向归 T02/T04。
2. **T25 的五条变更请求（CR-T25-01~05）** 待 T02 认领，全部记于
   [`CONTRACT-STRICTNESS.md`](docs/CONTRACT-STRICTNESS.md) §5：
   schema 闭合枚举、downstream 存在性门、tool allowlist schema、**双键去重**
   （实测 `path`/`adapted_path` **293/293 同时存在且全相等**）、预算数值入 schema。
3. **T20 的变更请求**：既有导入器的 `rollback` **不恢复 `INDEX`/`NOTICE`/`schemas/`**（已实证并交 owner）。
4. **T17 的四项"只能描述、无法机器验证"**（[`COORDINATION-CONTRACT.md`](docs/COORDINATION-CONTRACT.md) §7）：
   人工批准的真实意图、真实竞态 wall-clock 串行、lease 签发者身份、retention 日历与删除执行。
5. **U2**：`capabilities.py` 唯一实物在**禁改区** `community-raw/apk-reverse-source/scripts/`；
   wave 7 取证实测结论为"基准正确、备注过时、无处可改"；`scan_leaks` 的相对路径漂移登记给 T07 后续。
6. **社区侧中文 token 缺口（`x-gap-upload`）**：文件上传类中文说法在社区路由侧零 token，
   属 frozen 层，需另立信号卡。
7. **`verify-gate-wiring` 的 write-scope 检查**仍无可自动化回归（需另起直调该门、断言 exit 10 的脚本）。
8. **`verify-doc-auto-install.py` 无参数接口**（连 `--help` 都被忽略），与本项目其他守卫惯例不一致；
   将来若要自动化它的负向对照，需先补一个可指定根的入口。
9. **签名 / trust root / 轮换 / 撤销 / SBOM / CVE / 发布批准**：T21 与 T16 已如实登记为未实现，
   保持"被拒"状态即为正确行为。

### 发布结论

**本仓是 local-only candidate，不可 redistributable。** 这不是缺陷，是 T13 对抗复核与
T16 的 D1–D7（未实现清单）共同支撑的**如实状态**。任何"可发布"的说法在这份文档里都不成立。

### 历史存档（wave 1–8 的派单包，均已完成）

### 下一波：T04 / T05 / T06 / T10（**已完成，保留作历史**）

四张卡写作用域互不重叠，可并行。完整白名单、禁止项、验收命令、负向对照要求见
`D:\Project\skills-hub\work\wave1-briefs.md`（仓库外，故意不做 Markdown 链接——链接到仓库外文件会让
`verify-doc-links.py` 正确判为断链）。

| 卡 | 写作用域 | 一句话 |
|---|---|---|
| T04 | `scripts/validate-integration.py`、新 `scripts/verify-release-gate.py`、许可证矩阵、checklist、NOTICE | release 模式真实阻断 + 关闭 CR-004 + 去掉硬编码统计断言 |
| T05 | `scripts/adapt-community.py`、`.gitignore`、新测试、新文档 | **最高风险**：重写那个会覆盖 1111 条路径的导入器 |
| T06 | `skills/scripts/verify-repository-security.py` + 规则/测试 + 新文档 | vendor trust 扫描，先报缺口再补 |
| T10 | `.github/workflows/**`、`skills/tests/**`、`tests/community/**` | **把 T26 新增的三个门接进 CI**（U10），否则负向对照白建 |

**本轮不要碰**：T12/T14（两者是同一交付物的两个视角，且 T12 要改 `.gitignore` 与 T05 冲突）、
U1 横幅（与导入器耦合，等 T05）、U9 的 9 条过宽规则（需 1.3 之外的机制）。

### P0：路由信号质量 —— **已完成（`f043236` / T26）**

原任务：让 293 个社区技能能被找到。九个缺陷 D1–D9 已修或具名登记，逐条实测数字见
[docs/community/ROUTING-SIGNAL-DEFECTS.md](docs/community/ROUTING-SIGNAL-DEFECTS.md)。

实测：slug 自召回 **187/293 → 274/293**；38 个命名探针零引用 **7 → 1**；`community-raw` /
`skills-hub` 命中 **293/293 → 0**；`tokens("workflow")` 由 `{alias_delivery}` → `∅`；
新增 28 条策展信号（每条 evidence 可机器复核）与 57 个诱饵/正向用例。

**仍未关闭（不声称净改善）**：
1. **9 条过宽规则具名红着**，逐条机制见缺陷记录。最便宜的两条已修（`ai` 短令牌、
   `adapted`/`capability`），其余需要 1.3 之外的机制（例如 `融合` 是 56 条描述里的真实词，
   占比 36%，不满足"单来源 ≥80%"）。
2. **`s3 bucket` 仍是零引用**，且这是**正确**行为：293 条语料里没有 S3/对象存储技能，
   按 1.2 不得为它编造关键词。已改成记录"该能力不存在"的诱饵。
3. **新门没有接进任何入口**（WORK-BOARD U10）：`verify-routing-signals.py` 与
   `test-community-decoys.py` 只在手工跑时生效。在 T10 接线前，不得把"有负向对照"
   表述为"已自动阻止回归"。

### P1：把 3 个新门接进 CI 与仓库入口（T10 的一部分）

T26 新增的 `verify-routing-signals.py`、`test-routing-signals.py`、`test-community-decoys.py`
目前谁都不调用。T10 接 CI 时必须一并接进来，否则下一轮回归无人阻止。

### P1：`scripts/adapt-community.py` 重写（T05）

行为规格已就绪：`D:\Project\skills-hub\work\t05-importer-spec.md`（318 行）。
基线摘要：`D:\Project\skills-hub\work\baseline-digest.json`。

关键要求：五子命令（inspect/import/verify/promote/rollback）、`--help` 零副作用、
candidate + digest + 原子提升 + 回滚、**写入根必须指向 `community-raw/`**、
LF 折叠、`.candidates/` 入 `.gitignore`、先固化 digest 串接格式。

### P1：15 个 vendored 文档补 reference-only 横幅

`verify-community-banner.py` 报 15 项。清单：
`docs/community/{ai-fullstack-delivery,ctf-super-hub,apk-reverse-community}/**`

### P2：其余任务卡

T04（发布门 + 许可证矩阵，需处理 CR-004）、T06（安全扫描）、T10（CI 接线）、
T11（加载预算）、T12（source lock，承接 registry 里 16 个 null 值）、
T21（canonical base record）、T25（`path`/`adapted_path` 双键删除）。

完整清单见规范第 18、19 节与 WORK-BOARD 第 2 节。

---

## 7. 工作方法（已验证有效，建议沿用）

1. **每个门都要有负向对照**。累计抓到 6 个真实问题全靠这个：
   - 重排脚本删掉一整节 → 内容守恒校验抓出
   - 断链门可以自我豁免 → 隔离副本里构造攻击抓出
   - 测试靠坏数据通过 → 修好数据后暴露
   - **T26**：给新 verifier 写负向对照时发现，把有害的 `ai` 重新加回 `short_tokens`
     只返回 exit 10，而本仓库把 10 当**非阻断**——等于那个门根本没拦住它要拦的回归
     （已提升为 exit 20）
   - **T26**：负向对照自己也可以是错的。第一版"多出未测量字面量"用例误写成**当前**的
     八字面量列表，等于没变异，于是"证明"了任何事。现在用例必须自检变异是否真的发生
   - **T26**：提交会把 CRLF 规范化成 LF，所以工作树绿 ≠ 提交内容绿。最终版本需 clone 到
     仓库外重跑（本次 13/14 一致，第 14 个是快照缺失的已文档化降级）

2. **子代理报告里的每个数字都要独立复算**。累计三次发现自述与实测不符：
   漏算 16 条引号问题；说"无冗余写"实际有 310 条重复写；**T26 有子代理断言
   `capability`/`adapted`/`融合` 满足"单来源 ≥80%"并据此建议改 `noise[]`，独立复算为
   19% / 19% / 36%，全部不满足**——照做会往门里塞一条站不住的数据。

3. **不允许为了让测试变绿而放宽断言**。kq-01 遇到测试失败时正确地报告 partial 并把根因
   交回，而不是改测试。T26 沿用同一标准：诱饵门故意压在实测值之下，既有失败逐条具名留在
   输出里，不删用例、不降阈值、不抬 `REFERENCE_LIMIT`。

4. **不要相信"改完了"，要相信"改完之后重新测出来的数"**。T26 有子代理写了 620 行文档，
   内容详实、门也全绿，但它是在 wave 2 与 wave 3 之间写的，wave 3 之后整份文档有 **16 处
   数字过时**（其中 7 处是协调者清单之外自己发现的）。文档准确性必须当作交付物来验收。

5. **不确定就登记，不要猜**。规范第 21 节明确：任何代理都不得输出
   "无遗漏""绝对安全""已可发布"。T26 最终交付**明确不声称精确性侧的净改善**。

---

## 8. 环境信息

> ⚠️ **本仓库大量文档保留了本机路径**（`C:\Users\<本机账号>\`、`D:\Project\skills-hub\`、
> `D:\EXE\python\`）。它们是**历史证据与当时的实测命令**，不是可移植配置；
> 在别的机器上照跑请自行替换为你的路径（Python 解释器可设环境变量
> `REVERSE_SKILL_PYTHON`，题库/产物目录可设 `REVERSE_SKILL_WORK_DIR`）。

| 项 | 值 |
|---|---|
| 仓库根 | `D:\Project\skills-hub\integrated-skill-hub` |
| 分支 | `main` |
| 最新 commit | **`1ca4cc3`**（第 **77** 个提交）。`1397d7f` 之后共 **30** 个提交（U19–U31 攻坚段），全部已 clone 复核 |
| **Python** | **`D:\EXE\python\python.exe`**（3.12.0，只用标准库）。**旧路径 `C:\Users\Toti\.dsh\dsh-runtimes\...\python.exe` 已被删除**，`dsh-runtimes` 整个目录不存在 |
| **活动 profile** | `web`（`desktop` 已不存在）；目录 `C:\Users\Toti\.dsh\profiles\web\` |
| **子代理 provider** | `axon`（旧名 `newapi` 已失效）。**当前派发顺序（2026-10-02 由仓库主人指定）**：① `space-bunny-free` + `xhigh`（首选）；② 不工作时退 `muse-spark-1.3-contributor-free` + `high`。**"不工作"判据**：返回 `null` / 零落盘 / 无收尾消息 / 启动失败 |
| **本轮实验室（仓库外）** | `D:\Project\skills-hub\work\round1-verify\`：`measure300.py`（全套 300 条）、`measure-comm.py`（community 200 条）、`diag28.py`（缺口根因）、`miss28.md`、`cardA-signals.md`、`cardB-alias-keywords.md` |
| 上游快照 | `D:\Project\skills-hub\upstream\`（5 个 clone，全部 clean；**仓库外**，clone 仓库时没有它） |
| 工作区（协调用） | `D:\Project\skills-hub\work\`（**仓库外**；注意仓库内也有一个 `integrated-skill-hub\work\`，那是 `master-route` 等生成物，两者不同） |
| **派单包** | `D:\Project\skills-hub\work\`：`wave1`…`wave7-briefs.md` + **`dispatch-contract.md`**（通道/六项必带/回报格式/三条纪律） |
| **T26 证据脚本** | `D:\Project\skills-hub\work\p0\`（全部只读；`p0-acceptance.py` 是独立验收 harness，`p0-reconcile.py` 复算子代理口径，`p0-negative-control.py` 是 verifier 负向对照） |
| 参考实现（只读） | `D:\Project\临时对话\custom-skill-router` |

**注意**：仓库里 `skills/community/registry.json` 的 4 条 source 记录有 16 个 `null` 值
（`tree_digest`/`source_manifest`/`snapshot_root`/`importer_version`），因为快照在仓库外。
这是**已登记**的状态，owner 是 T12/T05，不要当成 bug 去"修"。

**另一条**：`work/p0/p0-proof-deadwidening.py` 是**历史基线证明**，文件头已加警告。它测量的
是 T26 之前 `lookup()` 的那种比较方式，现在的引擎不再那样比较；引用它的输出描述当前状态会
得到错误结论。当前状态的权威脚本是 `work/p0/p0-acceptance.py`。
