# 融合引导手册 — 往本包增量融合新的技能包

**这份文档给谁用**：给**以后要往这个包里加新技能包的智能体或人**。
你不需要读完整套施工规范；照本文的步骤走，每一步都有命令和验收条件。

**一句话**：把新包**只读拉下来 → 侦察 → 定策略 → 物理隔离 → 建记录 → 建通道 → 加路由 → 跑门 → 提交复核**。
本文第 11 节的"坑清单"是本仓库**实际踩过并付出代价**的经验，**不要跳过**。

> 想一句话开工？把 [docs/MERGE-KICKOFF.md](MERGE-KICKOFF.md) 整段复制给 AI 即可。

---

## 0. 你现在在什么地方

```
<开发根>\                     <- 开发根（仓库外）
├── integrated-skill-hub\                  <- 融合包本体（这才是仓库）
│   ├── skills\                            <- 客户端发现根：只有这里的内容会被智能体看到
│   │   ├── <43 个 canonical 技能>\
│   │   └── community\<4 条通道 wrapper>\  <- 社区包的接入点
│   ├── community-raw\<来源>\              <- 上游原文（物理隔离，17.27，客户端看不到）
│   ├── skills\community\registry.json     <- 所有社区技能的登记表
│   ├── skills\config\routing.json         <- 路由唯一事实源（48 条 R 规则）
│   └── scripts\adapt-community.py         <- 融合工具（本文的主角）
├── upstream\                              <- 上游快照（只读；每个包一个 clone）
└── work\                                  <- 工作区（lab、报告、临时产物都放这儿）
```

**当前状态**（截至 2026-10-01）：5 个来源已融合 = **43 canonical + 293 社区 = 336 个技能**。

---

## 1. 三十秒流程总览

| 步 | 做什么 | 关键命令 | 产出 |
|---|---|---|---|
| 1 | 拉新包到 `upstream/`（只读，**必须是 git 仓库**） | `git clone --depth 1 <url> upstream/<name>` | 快照 |
| 2 | 侦察：技能数、许可、成熟度、**有没有夹带重复框架** | 见 §3 | 侦察结论 |
| 3 | **定策略**：canonical 并入 / 社区通道 / 排除 | 见 §4 | 决策记录（落盘位置见 §4 末） |
| 4 | 登记导入器白名单（**必须在 import 之前**） | 改 `scripts/adapt-community.py` 四表 + pin 上游 HEAD | 白名单条目 + pin commit |
| 5 | 建 source 记录 | 改 `registry.json` 的 `sources[]`（17 字段全表见 §5） | 一条 source |
| 6 | 物理隔离原文 | `adapt-community.py import` | `community-raw/<source>/`（**不产出 `skills[]` 记录**） |
| 7 | 提技能记录（**手写**，导入器不产出） | 手写 `skills[]` + 同步 `stats` | N 条 skill |
| 8 | 建通道 wrapper | 手写 `skills/community/<name>/SKILL.md` + `wrappers[]` 条目 | 一个 wrapper（模板见 §6） |
| 9 | 加路由 | 改 `routing.json` 的 R 条目（空号查询见 §7） | 新 R 规则 |
| 10 | 跑门验收（含**融合必红三门**的预期处理） | 见 §9 | 全绿或具名降级 |
| 11 | 提交 + **clone 复核**（lab 版命令见 §10） | 见 §10 | 提交 + 复核记录 |

**顺序铁律**：`import` 一个**未登记**的 source 直接报 `unknown source id(s)` **exit 21**，
半登记（只加 `SOURCES`、漏 `DEST`/`RISK_BY_SOURCE`/`CONTEXT_BY_SOURCE`）报缺表 **exit 21**。
所以**必须先登记四表、再 pin commit、最后 import**——§5 的命令按此顺序排列，照抄即可。

**增量融合的铁律**：**不许破坏已有的 336 个技能**。每步之后都要能跑通 §9 的门。

---

## 2. 第 1 步：把新包拉下来

```powershell
cd <开发根>
git clone --depth 1 <新包仓库URL> upstream\<短名>
```

**注意**：
- 放 `upstream/`（**仓库外**），不要放 `integrated-skill-hub/` 里面。
- **只读**：不提交、不修改、不往里写东西。
- **上游目录必须是 git 仓库**：`import` 前导入器用 `git rev-parse HEAD` 取上游 HEAD 做
  17.28 attestation，非 git 目录报 `cannot resolve HEAD` **exit 22**。本地新建的假包
  也要先 `git init + commit`（实测假包 `upstream/test-new-pack` commit 为 `1acce26f…`）。
- 短名要短且唯一（如 `hack-skills`、`ctf-super-hub`）。它会成为 `source_id`。

---

## 3. 第 2 步：侦察（**这一步决定成败，别急着导入**）

```powershell
$env:PYTHONIOENCODING='utf-8'
$py = '(Resolve-ReverseToolSpec -Name 'pyre').Command'
$new = '<开发根>\upstream\<短名>'

# a) 有多少技能
(Get-ChildItem $new -Recurse -Filter SKILL.md | Measure-Object).Count

# b) 顶层长什么样
Get-ChildItem $new | Select-Object Name, Length

# c) 有没有 README / LICENSE / 规则文件
Get-ChildItem $new -File | Where-Object { $_.Name -match 'README|LICENSE|RULES|AGENTS|CLAUDE' } | Select-Object Name

# d) 【最重要】它有没有夹带一份别的框架的副本？
$py -c "import pathlib; p=pathlib.Path(r'$new'); [print(x) for x in p.rglob('SKILL.md') if 'reverse-skill' in str(x).lower()]"
```

**侦察必须回答的四个问题**：

1. **它是"技能集合"还是"另一个框架"？**
   如果它自己就是一套带路由/规则的框架（像 `reverse-skill` 那样），
   **不能整包并入**——只能取它的技能，或者在它里面**剔除重复框架**。
   > 实测先例：`AI-Fullstack-Delivery-Workflow` 里夹带了一份
   > `workflows/reverse-pentest/reverse-skill-private/CTF-Sandbox-Orchestrator/`，
   > 那是**重复的 reverse-skill 框架**，55 个文件被**有意排除**，
   > 排除理由原文：`vendored second reverse-skill framework; canonical base already provides this capability`。
2. **它的技能数与目录数对得上吗？** 递归数出来的 SKILL.md 可能包含嵌套的（example / plugin 里的），
   那些**不参与路由**。要区分"能路由的技能"和"随便一个 SKILL.md"。
3. **许可证是什么？** 看 `LICENSE` 与 README 声明。**本包自用（local-only）**，
   但记录必须如实写 `license_declared` / `license_status`，**不许把来源不明的标成 verified**。
4. **成熟度**：新包的技能是"验证过的"还是"没验证"？记为 `maturity: verified|partial|unverified`。

**新包怎么答这四问**（d 问的 `reverse-skill` 只是历史例子里的字面过滤，不是新包的答案）：
a 问数出 `SKILL.md` 个数即技能数；b/c 问看顶层与 `README`/`LICENSE` 是否存在；
d 问把过滤词换成**本包已有的框架名**（如 `reverse-skill`）在新包里搜——搜到即"夹带了重复框架"，
按第 1 问处理。实测假包 4 个 `SKILL.md`、`README`/`LICENSE` 存在、无夹带，结论即"独立技能集合"。

---

## 4. 第 3 步：定策略（三选一）

| 策略 | 什么时候用 | 做法 |
|---|---|---|
| **A. canonical 并入** | 包本身就是**同类框架**、且与本包主框架**同源**（如 `reverse-skill` 自己） | 直接进 `skills/<name>/`。**极少用**——本包只把主框架自己算 canonical |
| **B. 社区通道**（**默认**） | 绝大多数情况：新包是**独立的技能集合** | 原文进 `community-raw/<source>/`，技能登记进 `registry.json`，经**一条新 wrapper** 暴露 |
| **C. 排除** | 重复框架、无技能价值的脚手架、许可不明且无法补救的部分 | 记进 `registry.json` 的 `excluded[]`，**必须写理由** |

**默认走 B**。本包现有 4 条通道（`ctf-hub` / `hack-hub` / `delivery` / `apk-extension`）都是 B。

**为什么默认 B**：
- 原文在 `community-raw/`（**在 `skills/` 发现根之外**），客户端**看不到**，安全；
- 技能经 wrapper 暴露，要有**路由规则**才会被用到，可控；
- 出问题可以整条 `promote`/`rollback`，不污染 canonical。

**决策记录落盘**：在仓库外 `work/<本次融合名>/DECISION.md` 写一行：
`策略: B | source_id: <短名> | 技能数: <N> | 排除: <有/无, 有则写理由> | 日期: <YYYY-MM-DD>`。
这是融合审计的起点，后续 `excluded[]` 与受管变换登记都要引用它。

---

## 5. 第 4-6 步：用导入器落地

**工具**：`scripts/adapt-community.py`（五个子命令）

> **在 lab 里做**：下面每条命令的 `$repo` 都换成你的 lab 路径
> （如 `work\<卡名>-lab`），且 `import` 必须显式传
> `--upstream-root <开发根>\upstream`——lab 默认的
> `<repo>/../upstream`（即 `work/upstream`）**不存在**，不传就找不到上游。
> 所有实验只许在 lab 副本上跑，真仓库零改动。

### 5.0 先登记导入器白名单（不做这步，`import` 第一步就 exit 21）

新 `source_id` 必须同时进 `scripts/adapt-community.py` 的**四张表**，缺一不可：

| 表 | 加什么 | 例子（仿 `hack-skills` 行） |
|---|---|---|
| `SOURCES[]` | 一条记录：`id` / `repo`（`upstream/` 下目录名）/ `upstream_url` / `commit`（pin，见下）/ `scan`（技能扫描根）/ `license_status` / `maturity` / `license_declared` / `third_party_review` / `notice_file` | `repo: "hack-skills", scan: Path("skills")` |
| `DEST` | `"新id": "community-raw 下的目标目录名"` | `"hack-skills": "hack-skills"` |
| `RISK_BY_SOURCE` | `"新id": "high\|medium"` | `"hack-skills": "high"` |
| `CONTEXT_BY_SOURCE` | `"新id": ["authorized-lab", …]`（合法上下文词） | `"hack-skills": ["authorized-lab", "defensive"]` |

**半登记的真实后果**（lab 实测）：只加 `SOURCES`、漏掉后三表，`import` 报
`KeyError` traceback **exit 1**（违反规范 4.7）；修后报明确缺表信息 **exit 21**。
而 `SOURCES` 里完全没有该 id 时，`inspect`/`import` 报 `unknown source id(s)` **exit 21**。
两种 21 都是"先登记、再导入"这个顺序的 enforcement，不是故障。

### 5.1 pin 上游 HEAD（新 source 的 commit 从这里来）

```powershell
git -C <开发根>\upstream\<短名> rev-parse HEAD
# 把输出的 40 位 commit 填进 SOURCES[] 条目的 "commit" 字段
```

先拿 `commit` 全零或旧值跑 `import` 会被 17.28 拒（`resolved_commit != pinned commit`，exit 20）。
**真顺序是：加四表 → pin 真实 HEAD → import**。

### 5.2 照顺序跑导入器

```powershell
$env:PYTHONIOENCODING='utf-8'
$py = '(Resolve-ReverseToolSpec -Name 'pyre').Command'
$repo = 'C:\relab2'   # lab 里换成 lab 路径
$up = '<开发根>\upstream'

# ① 看现状（只读，安全）
& $py "$repo\scripts\adapt-community.py" --repo-root $repo --upstream-root $up inspect
& $py "$repo\scripts\adapt-community.py" --repo-root $repo --upstream-root $up inspect --source <新source_id> --json

# ② 建候选（只写 .candidates/<id>/，不碰已验证树）
& $py "$repo\scripts\adapt-community.py" --repo-root $repo --upstream-root $up import --source <新source_id> --candidate <候选id>

# ③ 校验候选（只读）
& $py "$repo\scripts\adapt-community.py" --repo-root $repo --upstream-root $up verify --candidate <候选id>

# ④ ★唯一会改已验证树的命令★（先 --dry-run！注意 --status 必填）
& $py "$repo\scripts\adapt-community.py" --repo-root $repo --upstream-root $up promote --candidate <候选id> --status local-only --dry-run
& $py "$repo\scripts\adapt-community.py" --repo-root $repo --upstream-root $up promote --candidate <候选id> --status local-only
```

**全局选项**（要放在子命令**前面**）：`--repo-root`、`--upstream-root`（默认 `<repo>/../upstream`，只读）

**退出码**（规范 4.7）：`0` 匹配 / `10` 需复核 / `20` 阻断 / `21` 缺输入 / `22` 不可用 / `30` 失败

**写根**：`community-raw/`（**在 `skills/` 之外**，这是 17.27 物理隔离要求）

### 5.3 `registry.json` 的 `sources[]`：17 字段全表（照抄，逐个填）

以 `ctf-super-hub` 条目为范本（17 个键，一个不许少）。必填/选填与含义：

| 字段 | 必填 | 含义 / 怎么填 |
|---|---|---|
| `id` | 必填 | = 短名，与四表 id 一致 |
| `source_kind` | 必填 | 新包填 `"community"` |
| `source_url` | 必填 | 上游仓库 URL |
| `commit` | 必填 | pin 的 40 位 HEAD（与 SOURCES 一致） |
| `tree_digest` | 必填 | 导入器 attestation 的 `tree_digest`；暂时未知先填 `null`，待 T02 回填（已登记状态，不是 bug） |
| `source_manifest` | 必填 | 同上，未知填 `null`，指向 source-lock 同 id 条目 |
| `snapshot_root` | 必填 | 同上，未知填 `null`（即锁的 `snapshot_rel`） |
| `source_root` | 必填 | 快照内扫描根（如 `"."` / `"skills"`），照抄 SOURCES 的 `scan` |
| `license_declared` | 必填 | 上游声明的许可，未声明填 `"NOASSERTION"`，**不许把来源不明的标成 verified** |
| `license_status` | 必填 | `review-required` / `missing-license` / 明确许可名 |
| `third_party_review` | 必填 | `"required"`（除非已确认为自有代码） |
| `notice_file` | 必填 | `docs/community/<source_id>/THIRD_PARTY_NOTICES.md` 或上游 LICENSE 拷贝路径 |
| `maturity` | 必填 | `verified` / `partial` / `unverified`（§3 结论） |
| `distribution` | 必填 | 新包填 `"local-only"` |
| `adaptation_status` | 必填 | 新包填 `"imported"` |
| `importer_version` | 选填 | 导入器当前无版本常量，填 `null`（T02 定标识后回填） |
| `last_verified_at` | 必填 | 本次融合的 UTC 时间（`YYYY-MM-DDTHH:MM:SSZ`） |

### 5.4 `skills[]` 记录：导入器**不产出**，必须手写

纠正旧文：`import`/`promote` **只产出** `community-raw/` 原文 + 候选 `registry.json`
（attestation 列刷新），**不产出 `skills[]` 记录**。每个新技能手写一条（19 字段，
仿 `community-ctf-super-hub-001`）：`id` / `source` / `source_path`（快照内相对路径）/
`adapted_path` / `path`（= `community-raw/<dest>/…`）/ `entrypoint`（本通道 wrapper 路径）/
`discovery: "reference-only"` / `license_status` / `maturity` / `distribution: "local-only"` /
`allowed_context`（数组，合法上下文词）/ `risk` / `content_type` / `keywords` /
`canonical_downstream`（数组，无则 `[]`）/ `reference_ids`（数组，无则 `[]`）/
`content_hash`（`"sha256:<hex>"`，对适配后文件实测）/ `path_status: "clean"` /
`extensions`（含 `legacy_original_name` / `legacy_description` / `legacy_adapted: true`）。

**`stats` 必须同步**：`stats.adapted_skill_count` = `len(skills[])`（当前 293，加 N 个就 293+N），
否则黄金集报 `registry contract violation`。`stats.excluded_framework_skill_count` 不动（仍 55）。

### 关于 promote 的现状（**重要，别误判**）

`promote` 会拒绝任何**未登记的差异**，并**点名**要回退的路径。这是**特性不是故障**。

**"会被拒"只适用既有 4 源**：实测（2026-10-01）生产记录下四个单源与全量**当前全被拒**——
apk=11 / ctf=13 / hack=141 / ai=137，全量 302 恰为四者之和，**全部是未登记的 modifications**。
要让它们可 promote，需要**各域 owner 决定是否把它们登记为"受管变换"**。
**新 source 首次 promote 在 lab 里并未被拒**（`--dry-run` 与正式均 exit 0）——因为新目录
在已验证树里没有"旧内容"可冲掉。看到"新包 promote 被拒"先查是不是把既有源也圈进了
`--source`（默认全量），而不是怀疑新包本身。

**受管变换机制**见 `docs/community/IMPORTER-MANAGED-TRANSFORMS.md`：
策展编辑优先（curation wins），已登记的变换（如 `t09-load-instruction-neutralize` 131 个文件、
`u1-docs-reference-only-banner`）会在 `import` 物化后自动应用。

**所以：融合一个新包时，若它引入了新的"有意偏离上游"的编辑，必须登记为受管变换，
否则下次重导入会把你的编辑冲掉。**

---

## 6. 第 7 步：建 wrapper（通道文件）

在 `skills/community/<新通道名>/SKILL.md` 建一个文件。**不要只"参考现有的四个"**——
下面是可直接复制的最小模板（正文骨架仿 `delivery/SKILL.md`，frontmatter 只需两行）：

```markdown
---
name: community-<通道名>
description: <一句话：这个通道提供什么能力，什么情况下路由到这里>。
---

# Community <通道名> adapter

## ACTION REQUIRED

1. `NOW`: 明确目标与输入材料，缺少关键输入先列阻塞项，不猜工具或环境。
2. `NEXT`: 从 `community-raw/<dest>/` 读取对应的适配后技能正文；
   这些路径已被适配到当前包，不使用源仓库的全局 hooks、私有嵌套 checkout 或自动 bootstrap。
3. `ACT`: 高风险动作（真实部署、外部发布、逆向利用）必须交还 canonical 路由，
   遵循它自己的 scope/case/授权门；本通道只负责引路和验收。
4. `DONE`: 产出结果、证据路径、风险与回滚说明，未验证的能力标为 `unverified`。

## Canonical boundaries

- 全局安全规则仍由根 `RULES.md` 管理。
- 路由仍由 `skills/config/routing.json` 管理。
- 上游原文在 `community-raw/<dest>/`，客户端经本通道发现根进入，不直读原文。
```

`registry.json` 的 `wrappers[]` 里登记一条（**12 字段全表**，仿 `wrapper-ctf-super-hub`，
`context_map` 口径见下，一行不许少）：

```json
{
  "id": "wrapper-<source_id>",
  "path": "skills/community/<通道名>/SKILL.md",
  "source": "<source_id>",
  "route_ids": ["R<新编号>"],
  "reference_ids": ["<该 source 的 skill id, 逐条列全>"],
  "allowed_downstream": ["<canonical 技能名, 如 ctf-sandbox>"],
  "input_schema": "schemas/community-handoff-input.json",
  "output_schema": "schemas/community-handoff-output.json",
  "context_map": { "<合法上下文词>": "<对应网络模式>" },
  "default_action": "review",
  "auto_execute": false,
  "maturity": "<verified|partial|unverified, 与 source 一致>"
}
```

**`context_map` 口径**（不照抄必被契约门打回）：**非空**；键必须是 `profile-map`
里的合法上下文词（如 `offline_ctf` / `defensive_review` / `local_project` /
`offline_sample`）；值必须等于该上下文对应的网络模式（如 `offline_ctf → offline`、
`local_project → project_local`，以现有四条记录为准）。`allowed_downstream` 填真实存在的
canonical 技能名；`reference_ids` 必须与手写的 `skills[]` id 一一对应。

---

## 7. 第 8 步：加路由（**最容易做错的一步**）

改 `skills/config/routing.json`（**路由唯一事实源**，48 条 R 规则：R1–R49 + R0，缺 R42/R43）。

### 7.0 先找空号（当前可用：R42、R43）

```powershell
$env:PYTHONIOENCODING='utf-8'
& '(Resolve-ReverseToolSpec -Name 'pyre').Command' -c "import json; r=json.load(open(r'$repo\skills\config\routing.json',encoding='utf-8')); print('routes:',len(r['routes'])); print('missing:',[k for k in ['R'+str(i) for i in range(0,50)] if k not in r['routes']])"
# 实测输出：routes: 48，missing: ['R42', 'R43']——取最小的 R42
```

### 7.1 加一条路由要同步四处（缺一则一致性门挂）

| # | 位置 | 改什么 |
|---|---|---|
| 1 | `skills/config/routing.json` 的 `routes` | 新增 `"R42": {...}` 条目（格式见下） |
| 2 | 同文件的 `priority[]` 数组 | **同步插入** `"R42"`（顺序影响并列裁决；新路由放同类路由附近，仿 R46–R49 的相对位置） |
| 3 | `skills/MASTER-ROUTING.md` 优先级表 | 加一行 `| **R42** | <一句话> | `community/<通道>/` |`，**与 `priority[]` 同序** |
| 4 | `skills/tests/routing-benchmark.json` 的 `cases` | 至少加一条正向用例（`hint` 命中 R42）+ 两条负向对照用例 |

```json
"R<新编号>": {
  "label": "<一句话描述>",
  "skill": "community/<通道名>/SKILL.md",
  "keywords": [
    { "must": "<正则>", "note": "<为什么这么写、语料依据是什么>" }
  ]
}
```

### 三条铁律（**踩过血的教训**）

1. **不许"多塞词"提高命中率。**
   实测先例：`融合` 是 56/154 条描述里的**框式连接词**（占比 36%），
   一旦当关键词加进去，会把**所有**该类查询全吸过来。**这类词已经被 STOPWORDS 移除。**
   **判据**：一个词如果要靠"占比高"来命中，它就没有区分度，**不能用**。
2. **每个新增说法都要有语料依据**——写明它在 `registry.json` 的哪条记录/哪个 wrapper 里出现、几次。
   没有依据的说法不要加。
3. **要能证明"没有过度吸收"**——必须跑**负向对照**：造几条**贴近但不同域**的 hint，
   断言它们**不会**落到你新加的路由上。
   **"合格对照"判据**：对照 hint 自身必须先命中目标既有路由——先用该既有路由单独验证。
   反例：`redis安全加固方案`自身落到 R0（无 R35 强关键词），拿它当"不会被 R42 吸走"的对照
   是**不合格**的（它连 R35 都没命中，证明不了 R42 的克制）；而`数据库安全 redis 未授权核查`
   自身命中 R35、`java反序列化漏洞检测`自身命中 R46，再断言不被 R42 吸走，才是合格对照。

### 如果新路由会抢走既有路由的查询

**用 `mustAll` 加语境约束**（这是既有机制，`master-route.ps1` 从 L42 起实现）：

```json
{ "must": "头脑风暴|brainstorm", "mustAll": ["ctf|strix|夺旗|解题|靶场|题解|writeup|新手|分流"],
  "note": "社区分诊 UX；必须同时出现 CTF 语境词，否则通用产品头脑风暴会被误吸" }
```

### 加了路由之后的必跑回归

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "$repo\skills\scripts\test-routing.ps1"                      # 期望 182/182 + 你新增的用例数（实测加 3 例后为 185/185）
powershell -NoProfile -ExecutionPolicy Bypass -File "$repo\skills\scripts\verify-routing-coherence.ps1"          # 期望 ALL PASSED
& $py "$repo\skills\scripts\test-golden-route.py"                                                                # 期望 39/39
```

**这三条有任何一条退化，就是你把既有路由弄坏了**——回退重做，不要"顺手调阈值"。
注意一致性门用 `git ls-files` 判定：新文件**提交后**才可见，提交前挂 `untracked` 一项是预期的
（先做 §10 的本地提交再重跑，不要为此改门）。

---

## 8. 别破坏的结构约束

| 约束 | 为什么 |
|---|---|
| **canonical 的 43 个技能一个都不能少** | 它们是主框架本体；实测与原版**逐目录零差异** |
| **`RULES.md` / `skills/routing.md` 视为冻结** | 实测与原版**字节完全相同**；要改必须先证明必要性 |
| **原文必须物理隔离在 `community-raw/`** | 17.27；客户端发现根是 `skills/`，隔离区在它之外 |
| **不许建第二套**全局规则 / router / `tool-index` / case 根目录 | 一个包只有一套，否则智能体会读到互相矛盾的规则 |
| **`skillpack/skills/TOOLS.md` 是生成物**（gitignored） | fresh clone 里没有它，只有 `.template`；**这是设计如此**，不是缺文件 |
| **`.github/workflows/**` 与 `skills/tests/ci-gates.json` 是接线层** | 加新门要同步改三处（manifest + lock + workflow），否则接线自检会红 |

---

## 9. 第 9 步：跑门验收

**统一入口**（推荐）：

```powershell
$env:PYTHONIOENCODING='utf-8'
& '(Resolve-ReverseToolSpec -Name 'pyre').Command' "$repo\skills\tests\run-ci-gates.py" --runner python
```

**门数口径（唯一真值，2026-10-02 实测复核）**：`skills/tests/ci-gates.json` 共 **23** 门 =
**21** 个 python 门（`--runner python` 实跑的就是这 21 个）+ **2** 个 `runtime: powershell` 门
（`test-routing`、`verify-routing-coherence`，CI 里单独跑，不进 `--runner python`）。
所以 `--runner python` 的 `total` 恒等于 23 − 2 = **21**；文档里出现的"20 门""22 门"是加门前的历史残留。
加门/删门后请同步改这一句，别让两个口径并存。

**期望**（真树）：`total=21 ok=21 non_blocking=0 skipped=0 blocked=0 failed=0`，exit 0。

**clone 到仓库外**（无 `../upstream` 快照）时允许的差异：三个门（`verify-triage-lock`、
`verify-source-attestation`、`verify-canonical-base-lock`）因缺快照降级为 exit 10（非阻断），
`test-adapt-community` 因 `requires_upstream_snapshot` **响亮跳过**（计入 skipped）。
**这些是已登记的降级，不是失败。**

**融合后至少要额外跑**：

```powershell
& $py "$repo\scripts\validate-integration.py"            # 集成校验
& $py "$repo\skills\scripts\audit-discovery-surface.py"  # 发现面（确认没把原文漏进 skills/）
& $py "$repo\skills\scripts\verify-community-banner.py"  # 社区文件横幅
& $py "$repo\skills\tests\verify-gate-wiring.py"         # 接线自检
```

### 9.1 融合必红三门（预期内会红，别被吓到，也别为绿改门）

实测一次完整融合后全门 `total=20 ok=10 non_blocking=4 skipped=1 blocked=5`（**该次实测时清单还是
20 门**；加 `verify-evolution` 后清单为 23 门、`--runner python` 为 21 门），其中 3 个 blocked
是**每次融合都会红**的（另 2 个与本次无关：lab 缺 `../upstream` 的 SKIP 是已登记降级；
`verify-release-gate` 的缺陷属既有 notice 问题）。三门的名字、红的原因、合法处理：

| 门 | 为什么红 | 合法同步处理（不是"为绿改门"） |
|---|---|---|
| `test-contract-v2` | 把技能数 **293 硬编码了 3 处**（`check_registry` 两处 + 迁移断言一处）：`stats.adapted_skill_count == 293` / `len(skills) == 293`；加技能必然红 | 把 3 处 `293` 同步改为 `293+N`（N=本次新增技能数），并同步 `stats.adapted_skill_count`。定位命令见下 |
| `test-frontmatter-parsing` | `test_registry_invariants` 断言记录数 `== 293`（1 处）；同上，加技能必然红 | 同上，把该处 `293` 改为 `293+N` |
| `verify-community-bundle` | 要求 `registry` 的 source id 集合 `== source-lock.json` 的锁（当前 5 个）；新 source 不进锁就 blocked | 按 §9.2 把新 source 同步进锁 |

**"涨数"与"为绿改门"的边界**："为绿改门"指删断言、降阈值、放宽匹配让本该红的变绿；
而这里是**被计数对象本身变了**（293→293+N），断言的期望值必须跟着事实走，且 `stats`、
`len(skills)`、锁三处互相校验——只改一处、改错数字，别的门照样红。这叫"合法涨数"，
前提是 N 与你手写的 `skills[]` 条数完全一致。

定位硬编码的命令（加第 6 个源要同步改的逐条清单）：

```powershell
# 4 处 293（contract-v2 ×3，frontmatter ×1）
Select-String -Path "$repo\skills\scripts\test-contract-v2.py" -Pattern '293'
Select-String -Path "$repo\skills\scripts\test-frontmatter-parsing.py" -Pattern '293'
# registry 计数
& $py -c "import json; d=json.load(open(r'$repo\skills\community\registry.json',encoding='utf-8')); print(len(d['skills']), d['stats'])"
```

### 9.2 加第 6 个源要同步改的逐条清单

1. `skills/community/registry.json`：`sources[]` +1（§5.3 全表）、`skills[]` +N（§5.4）、
   `wrappers[]` +1（§6）、`stats.adapted_skill_count` 293→293+N。
2. `skills/community/source-lock.json`：`sources[]` 加一条新 source 的 17.28 attestation
   （字段见 `docs/community/SOURCE-BUNDLE.md` §3：十字段 + `pinned_commit` / `file_count` /
   `dir_count` / `snapshot_rel` 等），`registry_expectation` 的 `sources` 5→6、
   `source_ids` 加新 id。**没有一键生成命令**：锁是 T12 手工维护的，填值方法——
   `resolved_commit` 取 §5.1 的 HEAD，`tree_digest` / `file_manifest_digest` /
   `file_count` / `dir_count` 用导入器 `inspect --source <新id> --json` 的 attestation 输出照抄。
3. `skills/scripts/test-contract-v2.py`：3 处 `293`→`293+N`。
4. `skills/scripts/test-frontmatter-parsing.py`：1 处 `293`→`293+N`。
5. 改完用两脚本自证：`scripts/verify-source-attestation.py` 与
   `scripts/verify-community-bundle.py`（用法见 `docs/community/SOURCE-BUNDLE.md` §4），
   有快照时 exit 0；仓库外复制体 exit 10（具名降级，属预期）。

---

## 10. 第 10 步：提交 + **clone 复核（不可跳过）**

```powershell
cd $repo
git add -A
git commit -m "<改了什么>"

# ★必须★：clone 到仓库外重跑全门
cd work
Remove-Item verify-merge -Recurse -Force -EA SilentlyContinue
git clone $repo verify-merge
& '(Resolve-ReverseToolSpec -Name 'pyre').Command' verify-merge\skills\tests\run-ci-gates.py --runner python
```

**为什么不可跳过**：见 §11 坑 #2——**提交前看不出来的红**。

### 10.1 lab 版（融合演练时用这套，命令逐条可复制）

```powershell
$lab = 'work\<卡名>-lab'   # lab 副本路径
cd $lab
git add -A
git commit -m "<改了什么>"

# 最小可验证的 clone 复核：clone 刚提交的 lab，再跑门
cd work
Remove-Item verify-merge -Recurse -Force -EA SilentlyContinue
git clone $lab verify-merge
$env:PYTHONIOENCODING='utf-8'
& '(Resolve-ReverseToolSpec -Name 'pyre').Command' verify-merge\skills\tests\run-ci-gates.py --runner python
```

lab 里允许的差异与真树一致（§9：无 `../upstream` 的复制体 `ok=16 non_blocking=3 skipped=1`，
`test-adapt-community` 响亮跳过）。本次 lab clone 复核（最小可验证版本）走通：clone 成功，
`verify-community-bundle` exit 0、`verify-source-attestation` exit 10（5 项快照缺席具名降级，
属预期）——§10 的写法可执行。全量 `run-ci-gates.py` 在真树上另跑（见 §9 期望）。

---

## 11. 坑清单（**本仓库实际踩过并付出代价的经验**）

### 坑 #1 · 危险样本字面量会让安全门报红（**已两次致事故**）

文档/fixture 里**原样写**云密钥形状、私钥、注入句、PE/ELF 魔数、明文端点、symlink 目标，
安全门会把它判为问题。

**做法**：**掩码断开**（`AKIA…EXAMPLE`、拆 label、拆 scheme、跨行拼接）。
**写文档时**：描述"有这么个东西"即可，**不要贴完整字面量**。

### 坑 #2 · ★新文件在提交前对安全门不可见★（**已两次致事故**）

`verify-repository-security.py` 有 `.git` 时走 `git ls-files -s`，**只扫 index 里已跟踪的文件**。
**未跟踪的新文件在提交前完全看不见，一提交立刻命中。**

**所以**：交付前用这个自检：

```powershell
$env:GIT_DIR='D:\__no_such_git_dir__'
& '(Resolve-ReverseToolSpec -Name 'pyre').Command' "$repo\skills\scripts\verify-repository-security.py"
Remove-Item Env:\GIT_DIR
```

`GIT_DIR` 指向不存在的路径 → 门走 `os.walk` 回退 → **扫整个工作树（含未跟踪文件）**。
噪音判读：`__pycache__/*.pyc` 之类用 `git check-ignore -v <path>` 确认是 gitignored；
**只有将要 `git add` 的路径命中，才是真问题。**

### 坑 #3 · 提交会把 CRLF 规范化成 LF

`.gitattributes` 里 `*.md|py|json|yml text eol=lf`。所以**工作树通过 ≠ 提交内容通过**。
→ 这就是 §10 必须 clone 复核的原因。

### 坑 #4 · 并发落盘会让某个门误报

`test-adapt-community` 会快照 `git status --porcelain` 做"真仓库未变"断言。
**另一个代理正在落盘时**，前后快照不一致 → 误报 `exit 30`。**隔离重跑即 0**。

**做法**：跑门时确认没有其他写者；看到 `exit 30` 先查是不是并发。

### 坑 #5 · subagent 派发：模型与通道

- 用 `subagent` + `provider:"axon"` + `model:"muse-spark-1.3-contributor-free"` + `reasoning_effort:"high"`
- **不要**用 `spawn_teammate`（没有 model 参数）；**不要**用 `subagent_fork`（继承 Lead 的模型）
- 派发前**先跑一行探针**：provider 改名 / 模型下线时**失败是静默的**（返回 null、不报错、不写文件）
- `space-bunny-free` 曾一轮四卡两死（32–36 分钟处、无收尾消息）→ 已停用

### 坑 #6 · 子代理会静默失败，也会报错事实

已实测到的情况：代理跑 32–36 分钟后**无收尾消息**；也有代理**把存在的文件报成缺失**。
**做法**：以**工作树与 lab 痕迹**判断它做到哪一步，**不要凭它的自述下结论**；
回报必须用七标题，**每个数字协调者要能独立复算**。

### 坑 #7 · `adapt-community.py` 的禁令要按版本区分

旧版**没有 argparse**：`--help`、拼错参数都会触发**全量导入 + 删除**（1111 条路径、不留备份）。
**重写后**（T05）：`--help` / `inspect` / `verify` / `--dry-run` 是**安全只读**的；
**写子命令 `import`（非 dry-run）/ `promote` / `rollback` 只许在仓库外 lab 副本上跑**。

### 坑 #8 · lab 必须在仓库外

`work\<卡名>-lab\`。
曾经在仓库内的 `work/` 建 lab——那会被 `git status` 看见、被门扫到。

### 坑 #9 · 关键词"多塞词" → 过宽（见 §7 三条铁律）

### 坑 #10 · 不是所有守卫都支持指定根目录

例：`skills/scripts/verify-doc-auto-install.py` **完全不接受参数**（连 `--help` 都被忽略，固定扫仓库）。
给这类脚本写自动化负向对照前，要先确认它的接口。

### 坑 #11 · 门数会变，别拿旧数字对账

`skills/tests/ci-gates.json` 是**声明层**，`ci-gates.lock.json` 是**锁**（含 digest）。
加门要改 manifest 并 `--write-lock` 重生成锁；`verify-gate-wiring.py` 会交叉校验"每门都被 workflow 调用"。
**当前：manifest 23 门 = 21 个 python 门 + 2 个 powershell 门；`--runner python` 跑 21 门
（`total` 恒 = 清单 − 2）。** 这是本卡的第 #11 号坑本身——门数一变，下面这句和 HANDOFF 的
「门数唯一口径」都必须同步改，否则会再次出现"20/22/23"三个口径并存。
本仓最近一次变动：`verify-evolution` 接进清单（22 → 23 门），所以旧文档里的"22 门（20+2）"已作废。

### 坑 #12 · 导入器只认"四表齐全"的 source（半登记必被 21 拦下）

`SOURCES[]` 有、`DEST` / `RISK_BY_SOURCE` / `CONTEXT_BY_SOURCE` 缺——旧版直接
`KeyError` traceback + exit 1（违反规范 4.7）；现版报缺表名 + **exit 21**。
看到 `not fully registered: missing …` 就把缺的表补上（§5.0），不要绕过去。

> 以下 #13–#17 是 **2026-10-02 round-1/round-2 实战**追加的，数字均可复算，来源见文末「事实来源」。

### 坑 #13 · 写 JSON 丢了 BOM，会让**引擎整层 blocked**（2026-10-02 实测事故）

卡 A 用 PowerShell 落盘 `skills/community/routing-signals.json` 时**写出了 BOM**，
`community-route.py` 的严格 utf-8 解码直接报 `not valid JSON`，
**社区侧 172/200 掉到 78/200（120 条 blocked）**。

- **修法**：落盘一律无 BOM：
  `[System.IO.File]::WriteAllText(p, t, (New-Object System.Text.UTF8Encoding $false))`
- **关键**：**改完必须复测，不能只跑门**——当时本地 21 门**全绿**，是复测（重跑社区侧大样本）
  才抓到的。门抓不到这一类。

### 坑 #14 · CI 里有"本地门永远看不见"的检查（**两条都必须单独跑**）

1. `extract-summaries.ps1 -Check`（`skills/INDEX.md` 新鲜度）：一次实测 **exit 1 红了很久，
   而本地 21 门全绿**。
2. 非 ASCII 的 `.ps1` 必须带 UTF-8 BOM（`ci.yml:367`）——**重写 `master-route.ps1` 时丢了 BOM，
   本地 21 门照样全绿**。

⇒ 收尾时**必须单独跑这两条**（命令见 §12.5 第 3 步；BOM 自检的一行 python 见下面坑 #14 附注）。

```powershell
# 非 ASCII .ps1 的 BOM 自检（2026-10-02 加的负向对照脚本，缺 BOM 即 exit 1）
& $py -c "import pathlib; bad=[p.as_posix() for p in pathlib.Path('skills').rglob('*.ps1') if (not p.read_bytes().isascii()) and (p.read_bytes()[:3] != bytes([0xEF,0xBB,0xBF]))]; print('MISSING BOM: ' + ','.join(bad) if bad else 'BOM OK'); raise SystemExit(1 if bad else 0)"
```

### 坑 #15 · 改文档口径要**同步"复述它的地方"**

撤掉 F4 兜底的默认方向时，`skills/routing.md` 的**正段** + **速查表行** +
`skills/MASTER-ROUTING.md` 的**附注**——**三处都要改**；只改一处会留下自相矛盾的活文档，
而它是客户端真正会读到的那一份。

### 坑 #16 · 并行子代理会**互相污染测量**

同一轮里两张卡都改引擎/信号层时，`before`/`after` 数字会混——本仓库实际发生过：
**卡 A 的 before 测量混进了卡 B 的改动**。

⇒ **测量类动作要么串行，要么在隔离副本里做**（卡 B 的做法：`shadow-A-head` / `shadow-B-cardB` 两份副本）。
每张卡的报告里**必须写清"这个数字是在谁的地盘上量的"**。

### 坑 #17 · 别把"调优集成绩"当能力

300 条大样本 **297/300** 看着漂亮，但同一批技能**换 100 条新说法**
（同 `expect`、题面重写，与原题面最长公共连续汉字 LCS ≤ 5）**掉到 26/100**；
再用另一张卡**盲读入口文档**做因果分离（把"题面语义漂移"从"桥不泛化"里剔出去），
干净子集（81 条与答案键一致，占 100 条的 81%）的**社区侧只剩 10.6%**。

⇒ **融合后的验收必须包含一组"没调过的题"，否则等于用考卷当教材。**
可移植的量法见 §12.5 第 5 步与 `docs/CAPABILITY-REPORT.md`。

---

## 12. 融完之后的收尾（增量融合每次都做）

1. **更新 `docs/WORK-BOARD.md`**：把新来源、新技能数、新路由记进去。
2. **如果引入新的"有意编辑"**：登记为受管变换（`docs/community/IMPORTER-MANAGED-TRANSFORMS.md`），
   否则重导入会冲掉。
3. **如果新包引入新的发布相关物**：同步 `docs/RELEASE-ARTIFACT.md` 的清单。
4. **在 `work/` 存一份本轮的派单包与报告**（仓库外），供下次参考。
5. **跑一次全门 + clone 复核**，把结果写进提交信息。

---

## 12.5 融合后的验证协议（2026-10-02 增补，**按这个顺序跑，每步贴 exit 与关键行**）

```
任何一次融合收尾时，按这个顺序跑（每步贴 exit 与关键行）：

1. 双基准：test-routing.ps1（182/182）与 test-routing-natural.ps1（≥76/86）——不许退化
2. 全门：run-ci-gates.py --runner python → total=21 ok=21 failed=0
3. CI-only 两项（本地门看不见，必须单独跑）：
     powershell -NoProfile -ExecutionPolicy Bypass -File skills/scripts/extract-summaries.ps1 -Check   → exit 0
     # 非 ASCII .ps1 的 BOM 自检（一行 python，见 §11 坑 #14）
4. 大样本（有题库时）：measure300.py（当前 297/300）
5. 组外新说法（有 hold-out 集时）：holdout-measure.py（当前 26/100）——没有就自己造一批，
   题面重写、与原题面最长公共连续汉字 < 6
6. 提交 + clone 到仓库外把 1–3 重跑一遍
7. 可选但强烈建议：按 §12.6 的"四张审查卡"跑一轮独立审查
```

**第 3 步为什么必须单列**：`extract-summaries.ps1 -Check` 与 `.ps1` 的 BOM 自检**都不在
`--runner python` 的 21 门里**，本地全绿不代表 CI 绿（§11 坑 #14 两次都栽在这儿）。

**第 5 步为什么不能省**：297/300 是"同一批字面"的成绩，26/100（干净子集整体 29.6%、
其中**社区侧 10.6%**）才是它对**没调过的说法**的真实水平（§11 坑 #17）。
**只报第 4 步等于用考卷当教材。**

**第 6 步之外的额外要求**：任何写操作（`import` 非 dry-run / `promote` / `rollback`）
**只在仓库外 lab 副本上做**（§5、坑 #7、坑 #8）。

---

## 12.6 四张独立审查卡（融合后跑一轮）

2026-10-02 这一轮实际派过四类审查，建议固化为**每次融合收尾的标准动作**。
四张卡**互相独立**（X1 拿不到 X2/X3 的上下文，X4 在修完之后才跑）：

| 卡 | 审什么 | 典型产出 |
|---|---|---|
| **X1 一致性** | 文档里的数字/路径/命令逐条对真树；找过时陈述、交叉矛盾、死链 | 本次 **18 条**，其中 **9 条"会误导使用者"** |
| **X2 可安装性** | 从 README 第一屏起演"只会照文档做的 AI"，逐步骤找卡点 | 本次 **9 条**断点（**8 条会误导**） |
| **X3 安全/许可** | 秘密、vendor 隔离、许可证一致性、workflow 写权限 | 本次 **3 条 HIGH**（其中"中文提示注入可绕过自动合并门"是**实测 PoC**） |
| **X4 复演** | 修完之后**再走一遍**同一条路径，逐条给"已消除/部分/仍存在/新引入" | 本次 **9 条 → 已消除 5、部分 3、仍 1** |

**跑法要点**：

1. **写的人不能给自己过**：审查卡的写作用域与施工卡**不重叠**，且只读当前工作树。
2. **X4 必须排在最后**，且必须**逐条对照 X2 的原始清单**——它的产出是四张卡里唯一能量化
   "修没修好"的（本次 9 条逐条给了"已消除/部分/仍存在/新引入"四档）。
3. **报告落仓库外**（`work/<轮次>/review/`），因为报告本身会引用**只在工作树里**的中间状态。

---

## 13. 这一节是给"以后那个智能体"的话

- **不要相信文档里写死的路径和版本**——解释器换过、provider 改名过、模型下过线。
  每步**先验证环境**，再动手。
- **不要"为了绿而改门"**。测试失败时保留现场与日志，**不许删测试/放宽阈值/跳过文件**。
  解不了就**如实报告**，那比假绿有价值得多。
- **不要假装完成**。未实现的东西**具名登记**（本仓库有 `D1–D7`、`CR-T25-01~05` 这类清单做先例），
  比含糊带过强。
- **不许自行触碰禁区**：协调者文件（`HANDOFF.md`、`docs/WORK-BOARD.md`、
  `docs/INTEGRATION-IMPLEMENTATION-SPEC.md`）、既有 `schemas/**`（收紧需经 T02）、
  `.github/workflows/**`、`skills/community/registry.json`（除按本文流程登记新来源）。
  需要改就**提变更请求**。
- **每一步都落盘**。本仓库的执行者是会静默失败的；**没落盘的工作等于没做**。

### 2026-10-02 追加（这一轮真正咬人的三条）

- **先跑探针再批量派发**。子代理会**静默失败**：本次一轮里 **2 张卡无收尾消息、1 张卡中途死**。
  判据是"**零落盘 / 无收尾消息 / 返回 null**"——**不许从"没有消息"推断任务太难**；
  要**查它的 lab 目录看做到哪一步**。探针（一次一行的小任务）不绿就别投放大批次。
- **每个数字都要独立复算**。本次抓到多起"自述与实测不符"，**含把存在的文件报成缺失**。
  协调者不采用子代理的数字，除非能在真树或 lab 里**复现出同一个数**。
- **私有库场景的变化**。这台仓库是**私有自用**，所以"公开分发的许可处理"可以降级；
  但这三类**一条都不能省**：
  1. **功能正确性**（双基准 + 全门不许退化）；
  2. **可移植性**（换机器能跑：路径不能写死、`.ps1` 的 BOM、CRLF/LF）；
  3. **CI-only 检查**（本地 21 门看不见的那些，见 §12.5 第 3 步）。

---

## 附：本文提到的关键文件索引

| 文件 | 作用 |
|---|---|
| `docs/INTEGRATION-IMPLEMENTATION-SPEC.md` | 总施工规范（92 KB，全部要求的来源） |
| `docs/MERGE-KICKOFF.md` | **开工词**：整段复制给 AI 即可开一次融合（硬约束 + 回报格式 + 先做什么） |
| `HANDOFF.md` | 交接文档：当前状态 + 剩余 owner 裁决项 + 三条纪律 |
| `docs/WORK-BOARD.md` | 协调板：U 项表 + 27 张任务卡状态 |
| `skills/community/registry.json` | 所有社区技能与来源的登记表 |
| `skills/config/routing.json` | 路由唯一事实源 |
| `scripts/adapt-community.py` | 融合工具（inspect/import/verify/promote/rollback） |
| `docs/community/IMPORTER-LIFECYCLE.md` | 导入器生命周期与 promote 窗口语义 |
| `docs/community/IMPORTER-MANAGED-TRANSFORMS.md` | 受管变换（策展编辑如何不被冲掉） |
| `docs/community/SECURITY-SCAN.md` | 安全扫描口径 + §7 提交前自检 |
| `docs/community/ROUTE-COVERAGE.md` | 路由关键词覆盖的写法范例（含"拒绝加什么词"） |
| `docs/community/DISCOVERY-ISOLATION.md` | 物理隔离（17.27）的说明 |
| `skills/MASTER-ROUTING.md` | 客户端路由入口（人读版） |

---

## 附二：2026-10-02 那批数字的**事实来源**（都可复算）

| 数字 | 出处 |
|---|---|
| 172/200 → 78/200（BOM 事故，120 条 blocked） | `docs/WORK-BOARD.md` **U32**「BOM 事故」段 |
| 297/300 = 99.0% | `docs/WORK-BOARD.md` **U32**；`work/round1-verify/ROUND1-NOTES.md` §1 wave 18 |
| 26/100 = 26.0%、干净子集社区侧 **10.6%**（5/47，81 条一致） | `docs/WORK-BOARD.md` **U33**；`ROUND1-NOTES.md` §1.2 / §1.3 |
| X1 **18 条 / 9 条会误导**、X2 **9 条断点 / 8 条会误导**、X3 **3 条 HIGH**、X4 **9 → 5/3/1** | `work/round1-verify/review/X1.md`、`X2.md`、`X3.md`、`X4-install-replay.md`（仓库外） |
| 「2 张卡无收尾消息、1 张卡中途死」 | `ROUND1-NOTES.md` 末尾卡 C 记录 + AGENTS.md 派发条款 |
