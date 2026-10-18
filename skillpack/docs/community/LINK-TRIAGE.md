# LINK-TRIAGE — active / wrapper / provenance 断链分类与处置登记

状态：**T03 交付物**。本文件是 `docs/community/**` 断链的**唯一人读登记清单**；逐条机器记录在同目录的
[`link-triage.json`](link-triage.json)，执行口径在 [`../../skills/scripts/verify-doc-links.py`](../../skills/scripts/verify-doc-links.py)。
按 checker 的分类口径它落在 `docs/community/**`（`class=provenance`、`source=first-party`）：它是本仓库自有的登记资料，
**不是执行规则**，也不进入活跃发现面。

| 项目 | 值 |
|---|---|
| 仓库 | `<仓库根>`（分支 `main`） |
| 基线 commit | `cec3d1328b445f5c1e6281a706c5d0935c7bc113` |
| 基线测量命令 | `python skills/scripts/verify-doc-links.py` |
| 基线结果 | `342 broken internal link(s)`，exit 1（WORK-BOARD 证据 E3 复现一致） |
| 验收命令 | `python skills/scripts/verify-doc-links.py`（退出码约定见第 4 节） |

本任务只做**分类与登记**，不做破坏性改写：没有删除任何链接目标语义（唯一的内容替换是 `solve-challenge` 那条：
按白名单把 8 行“运行上游安装脚本”的命令改写成手动准备步骤，上游安装器的模式名以文字保留，见第 7 节），
也没有放宽任何检查项（跳过大括号模板、inline code、fence、外部链接的既有规则逐条保留）。

---

## 1. 结论摘要

| 类别 | 基线数量 | 验收要求 | 处置后 |
|---|---:|---|---:|
| `active` | 0 | 必须 0 | 0 |
| `wrapper` | 1 | 必须 0 | 0 |
| `provenance` | 341 | 允许存在，但逐条登记 | 341（328 已改路径 + 13 保持并登记） |
| 合计 | 342 | — | 342 |

- provenance 按归属 source：`hack-skills` **334**、`ctf-super-hub` **4**、`ai-fullstack-delivery` **3**。
- 处置决定分布：`rewrite_path` **328**、`upstream_layout_unmappable` **13**、`documented_not_distributed` **1**（wrapper 那条）、
  `needs_human_review` **0**。
- reference-only 横幅：**4** 个文件（覆盖全部 13 条保持断链的链接）。
- 基线 342 条断链**全部**能在仓库外只读快照 `<开发根>\upstream\<source>\` 中解析到真实路径
  （0 条指向不存在的上游路径）。也就是说：断链是**迁移产物**，不是上游 README 的笔误。

---

## 2. 分类口径（与 checker 同一张表，逐条落码）

判定只看**断链所在文件**，与链接目标无关。规则按顺序第一条命中即生效，最后一条是 fail-closed 兜底：

| 序 | 规则 id | 路径 glob | class | scope_detail | 理由 |
|---:|---|---|---|---|---|
| 1 | `wrapper-entry` | `skills/community/*/SKILL.md` | `wrapper` | `wrapper_entry` | 四个 community wrapper 入口（`ctf-hub`、`hack-hub`、`delivery`、`apk-extension`）是活跃路由唯一允许交接的社区入口，断链等于“下一步”断了 |
| 2 | `community-skill-entry` | `skills/community/**/SKILL.md` | `wrapper` | `community_skill_entry` | 社区 `SKILL.md` 位于客户端发现根 `skills/` 之下，断链处于可被加载的路径上；按 2.3 / 11.3 它们只能是 wrapper-only、永不是 canonical，所以也不归 `active` |
| 3 | `community-archive-skills-root` | `skills/community/**` | `provenance` | `community_archive` | 非入口的 vendor 参考数据，只归档不执行 |
| 4 | `community-archive-docs` | `docs/community/**` | `provenance` | `community_archive` | 上游 README / RULES / workflow 的原样留档，其相对链接按上游仓库布局书写（规范 6.1） |
| 5 | `default-active` | `**` | `active` | `default_active` | 兜底：`RULES.md`、`README*`、`AGENTS.md`、`CLAUDE.md`、`skills/**`（非 community）、`docs/**`（非 community）都会被模型当规则读，未匹配任何规则的路径**不允许被静默忽略** |

`active` 的等价描述：canonical 技能树 + 会被当规则读的入口文件；`wrapper` 的等价描述：四个 wrapper 入口 + 社区
`SKILL.md` 入口文件。**`active` 与 `wrapper` 都必须为 0**。判定规则同时硬编码在
[`../../skills/scripts/verify-doc-links.py`](../../skills/scripts/verify-doc-links.py) 的 `CLASSIFICATION_RULES` 与
[`link-triage.json`](link-triage.json) 的 `classification_rules` 中；checker 会逐字段比对两处是否漂移，不一致直接失败。

`source`（归属）由路径前缀映射：`docs/community/<group>/**` 与 `skills/community/<group>/**` 取 `<group>`，
再经别名表映射到 registry 的 `sources[].id`（`ai-fullstack` → `ai-fullstack-delivery`、`apk-reverse-source` → `apk-reverse-community`）；
其余为 `first-party`。

### 2.1 `solve-challenge` 的归类依据

`skills/community/ctf-super-hub/solve-challenge/SKILL.md` 命中规则 2（`skills/community/**/SKILL.md`），归 **`wrapper`**：
checker 的实际读取路径是“客户端发现根 `skills/` 下的社区入口文件”，与四个 wrapper 同属会被加载的入口面；
它**不是** canonical 技能（规则 5 的 active 面不含 `skills/community/**`），也**不是**留档文档（`provenance` 面只覆盖
`docs/community/**` 与 `skills/community/**` 里的非入口文件）。要求它是 0，本任务已修复。

---

## 3. 处置词汇（checker 强校验）

| disposition | status | 含义 | checker 校验 |
|---|---|---|---|
| `rewrite_path` | `fixed` | 链接目标改写成**真实存在的迁移后路径** | `new_target` 必须仍出现在该文件的链接里，且解析成功；否则报 stale warning |
| `upstream_layout_unmappable` | `registered_open` | 上游确有该路径，但本包未迁移，无可信映射；链接保持上游布局 | 必须有 `file`+`target` 命中的现存断链、必须有 `evidence`、其文件必须带 reference-only 横幅标记 |
| `documented_not_distributed` | `fixed` | 引用的是**本包未分发的上游工具/脚本**，已删除该引用并改写为与仓库事实一致的说明 | 原 `target` **不得**再出现在该文件的链接里；必须有 `evidence` |
| `needs_human_review` | `registered_open` | 证据不足以判定，交给人工 | 同 `registered_open`，并使 checker 返回 exit 10（不会静默通过） |

reference-only 横幅的机器标记是 HTML 注释 `<!-- link-triage: reference-only -->`：任何存在 `registered_open`
条目的文件如果缺少该标记，checker 直接 exit 1。这样“登记了”不是口头声明，而是可验证状态（规范 17.19）。

---

## 4. 退出码契约（含与规范 4.7 的对齐说明）

| 情况 | status | exit |
|---|---|---:|
| `active`/`wrapper` 断链 = 0，且全部 provenance 断链已登记（无待判定条目） | `ok` | **0** |
| 任一 `active`/`wrapper` 断链；或 provenance 断链未登记；或 registry 缺失/JSON 非法/规则漂移/未知枚举/`documented_not_distributed` 的旧链接仍在；或已登记文件缺横幅标记；或文件不可读 | `fail` | **1** |
| 必须修的两类已归零且全部登记，但存在 `needs_human_review` 条目 | `needs_review` | **10** |

**为什么这样定，而不是整体套用第 4.7 节：**

1. 第 4.7 节冻结的是 **handoff / 路由结果**的 `status` 与退出码（`matched` 0 / `needs_review` 10 / `blocked` 20 / `missing_input` 21 /
   `unavailable` 22 / `failed` 30），并且明文规定“退出码是脚本契约：`case-guard` 的 `0/1/2` 与 `case-init` 的 `0/1` 是既有脚本契约，
   T25 必须补一张‘脚本 → status’映射表”。也就是说 4.7 自己就把既有 gate 脚本的布尔退出码排除在强制替换之外。
2. 本脚本是 11.2 的**文档门**：调用方（CI、协调者、后续任务）读的是“过 / 不过”，历史契约是 0/1（改造前就是 0/1，
   WORK-BOARD 证据 E3 记录为 `342 broken，exit 1`）。改成 20/30 之类会静默破坏既有调用方，且无法表达“provenance 已登记但需要人工看一眼”。
3. 因此：**常规通过/失败保持 0/1**；只有当“必须修 = 0 且全部登记、但仍有 `needs_human_review`”这一种新状态出现时，才借用 4.7 的
   `needs_review` → **10**，让不确定性有专门的出口，而不是被吞进 0。当前 registry 的 `needs_human_review` = 0，所以本次验收是 exit 0。
4. 本脚本不产生 4.7 的其余状态（`blocked`/`missing_input`/`unavailable`/`failed`），因此不引入那三个退出码；
   registry 缺失这类“输入缺失”按文档门惯例仍报 exit 1，并在 `failures[]` 里写明原因。

---

## 5. 逐条登记：328 条已改写（`rewrite_path`）

两个 hack-skills 留档 README 的 `./skills/<name>/SKILL.md` 全部指向上游仓库布局，而同一批技能已按原目录名迁移到
`skills/community/hack-skills/<name>/SKILL.md`。映射规则（可机械复核）：

    上游   ./skills/<name>/SKILL.md
    现在   ../../../skills/community/hack-skills/<name>/SKILL.md

- 改写条数：**328**（`docs/community/hack-skills/README.md` 164 条 + `README_CN.md` 164 条）。
- 不同目标数：**103**，与 `skills/community/registry.json` 中 `source = "hack-skills"` 的 103 条记录
  （基线 commit `cec3d13` 实测）、以及上游快照 `upstream/hack-skills/skills/` 的 103 个目录**三方一致**。
- 改写前对每个目标逐一断言：迁移后文件存在（`skills/community/hack-skills/<name>/SKILL.md`），
  否则不改写、转入 `upstream_layout_unmappable`；实际执行时 0 条落入该分支。
- 改写后 342 → 14 条断链（13 条 provenance + 1 条 wrapper）；本登记文件与 `link-triage.json` 落地后，
  工作树只剩 13 条已登记的 provenance 断链，`wrapper` 归零。逐条记录见 [`link-triage.json`](link-triage.json)。
- 每条的 `baseline_line`（基线行号）与 `line`（当前行号，横幅插入后）都在 JSON 中，便于人工比对；
  328 条改写条目的 `line` 已按“同文件同目标的出现序号”逐条复核（0 处不符）。

逐条明细（342 条：文件、行号、目标、分类、归属 source、处置、理由）**全部**在
[`link-triage.json`](link-triage.json) 的 `entries[]` 中，本文件不重复 328 行明细。

---

## 6. 逐条登记：13 条保持断链（`upstream_layout_unmappable`）

行号为当前工作树行号（横幅已插入）；上游证据为仓库外只读快照，**不联网**核对。

| # | 文件:行 | 目标 | 上游证据（只读快照） | 为什么不能改写 |
|---:|---|---|---|---|
| 1 | `docs/community/ai-fullstack-delivery/README.md:252` | `templates/task-input-template.md` | `upstream/AI-Fullstack-Delivery-Workflow/templates/task-input-template.md` 存在 | 本包只采纳上游 `workflows/**`；上游仓库根的 `templates/` 未迁移。仓库内唯一的同名文件在 canonical 技能 `skills/js-reverse/references/task-input-template.md`，与本链接无来源关系，改指过去等于编造映射 |
| 2 | `docs/community/ai-fullstack-delivery/README.md:253` | `templates/delivery-acceptance-criteria.md` | 同上目录存在 | 全仓库无同名文件（`Get-ChildItem -Recurse -Filter` 实测 0 命中） |
| 3 | `docs/community/ai-fullstack-delivery/README.md:254` | `field-journal/_template.md` | `upstream/AI-Fullstack-Delivery-Workflow/field-journal/_template.md` 存在 | 本包只有**按角色**的副本 `skills/community/ai-fullstack/workflows/<role>/field-journal/_template.md`（154 份），不存在上游所指的“仓库根单一模板”，任选一份都是猜测 |
| 4 | `docs/community/ctf-super-hub/README.md:704` | `./docs/USAGE.md` | `upstream/ctf-super-hub/docs/USAGE.md` 存在 | 本包 `docs/community/ctf-super-hub/` 只保留了根文件（README、START-HERE、SKILL-INDEX、SECURITY、CONTRIBUTING、THIRD_PARTY_NOTICES、LICENSE、third_party/），**没有 `docs/` 子目录** |
| 5 | `docs/community/ctf-super-hub/README.md:705` | `./docs/LINUXDO.md` | `upstream/ctf-super-hub/docs/LINUXDO.md` 存在 | 同上 |
| 6 | `docs/community/ctf-super-hub/README.md:706` | `./docs/PUBLISHING.md` | `upstream/ctf-super-hub/docs/PUBLISHING.md` 存在 | 同上 |
| 7 | `docs/community/ctf-super-hub/README.md:707` | `./docs/LOCALIZATION.md` | `upstream/ctf-super-hub/docs/LOCALIZATION.md` 存在 | 同上 |
| 8 | `docs/community/hack-skills/README.md:48` | `./site` | `upstream/hack-skills/site/`（目录）存在 | 本包根目录无 `site/`；上游站点未迁移 |
| 9 | `docs/community/hack-skills/README.md:48` | `./.github/workflows/deploy-pages.yml` | `upstream/hack-skills/.github/workflows/deploy-pages.yml` 存在 | 本包 `.github/workflows/` 只有 `auto-merge-journal.yml`、`ci.yml`、`macos-bash-compat.yml`（owner T10），没有上游 Pages 工作流；不得把上游工作流指到 T10 的文件上 |
| 10 | `docs/community/hack-skills/README.md:406` | `./.github/workflows/upload-hack-skills.yml` | `upstream/hack-skills/.github/workflows/upload-hack-skills.yml` 存在 | 同上 |
| 11 | `docs/community/hack-skills/README_CN.md:45` | `./site` | 同 #8 | 同 #8 |
| 12 | `docs/community/hack-skills/README_CN.md:45` | `./.github/workflows/deploy-pages.yml` | 同 #9 | 同 #9 |
| 13 | `docs/community/hack-skills/README_CN.md:403` | `./.github/workflows/upload-hack-skills.yml` | 同 #10 | 同 #10 |

这 13 条的“保持断链”以**文件顶部横幅**为前提：4 个文件都插入了 reference-only 横幅，说明自己是来源留档、
链接指向原始上游布局、不可当规则执行（规范 17.19）。

---

## 7. `solve-challenge` 那一条的最终处置与依据

| 项目 | 内容 |
|---|---|
| 断链 | `skills/community/ctf-super-hub/solve-challenge/SKILL.md:72`（基线行号） -> `../scripts/install_ctf_tools.sh`（分类 `wrapper`，source `ctf-super-hub`） |
| 处置 | `documented_not_distributed`（status `fixed`）：删除该引用，改写为“该脚本**未随本仓库分发**，需按下列步骤手动准备” |
| 依据 1 | `skills/community/ctf-super-hub/scripts/` 目录**不存在**（`skills/community/ctf-super-hub/` 下只有 35 个技能目录，无 `scripts/`），所以原相对路径在本仓库不可达 |
| 依据 2 | 该脚本只存在于**仓库外**只读快照 `<开发根>\upstream\ctf-super-hub\scripts\install_ctf_tools.sh`（上游 commit `16926d6d4216183995693e9c7936c042eb7f2fae`），不属于本包分发内容，不能作为链接目标 |
| 依据 3 | 规范 `INTEGRATION-IMPLEMENTATION-SPEC.md:526`（7.1 CTF 合同）明确：**不执行 `install_ctf_tools.sh`，不默认联网** |
| 依据 4 | `skills/community/registry.json` → `policy.autoInstall = false`；`AGENTS.md` 要求运行任何仓库脚本前取得用户明确批准 |
| 同时处理 | 同一文件在基线 commit 上共有 **8 处**该引用：第 58、64–69 行 7 条 `bash scripts/install_ctf_tools.sh <mode>` 命令（在代码块内，链接检查器不覆盖）+ 第 72 行那条 Markdown 链接。它们属于同一处错误引用，已一并改为与仓库事实一致的**手动准备步骤**（读 Prerequisites → 从 `skillpack/skills/TOOLS.md` 取真实路径 → 缺失工具写成披露式安装计划并取得批准 → 记录版本）；上游安装器的模式名（`all/python/apt/brew/gems/go/manual`）以文字保留，避免丢失 provenance |
| 未做 | 没有把 `data`、`assets` 之类不存在的本地路径编造成“真实路径”；没有新增任何安装脚本 |

---

## 8. checker 的改造与不变项

### 8.1 新增（分类与登记，不是放宽）

1. 每条断链输出 `[active|wrapper|provenance]` + `source` + 登记状态，并打印分类统计。
2. `--json` / `--report PATH` 输出机器可读报告（`status`、`exit_code`、`counts`、`provenance_by_source`、
   `provenance_by_disposition`、`registry`、`warnings`、`failures`、逐条 `links[]`）。
3. provenance 断链必须命中 `link-triage.json` 的 `registered_open` 条目，否则 exit 1；
   被登记文件必须带 `<!-- link-triage: reference-only -->` 标记，否则 exit 1。
4. registry 缺失、JSON 不可读、`classification_rules` 与代码漂移、未知枚举、
   `documented_not_distributed` 的旧链接仍存在 —— 全部 fail-closed（exit 1）。

### 8.2 校验对象（已披露的行为变化）

- **内容来源**：优先读**工作树**文件，工作树缺失时才回退到 git index blob。
  原因：`git show :path` 看不到未提交的改动，而本任务的交付形态就是未提交的工作树改动
  （任务禁止 `git add` / `git commit`）。回退分支保留了原有“防杀软隔离”的性质。
- **文件集合**：`git ls-files --cached --others --exclude-standard`，即“跟踪文件 + 未忽略的新文件”，
  仍然排除 git-ignored 生成物（如 `skillpack/skills/TOOLS.md`）。这样新增文件在 `git add` 之前就参与校验。
- 上述两点都不降低判定强度：链接仍然必须在树中真实存在。

### 8.3 不变项（未放宽）

外部链接（`http(s)`/`mailto:`/`tel:`/`ftp:`/`data:`/`//`/纯锚点）、fence 内链接、inline code 内链接、
`tool-index` 目标、含 `{}<>`$*|` 的模板目标 —— 与改造前完全一致；目标必须解析到真实存在的文件或目录。

---

## 9. 维护流程（后续任务如何改这张表）

1. 改完 `docs/community/**` 后跑 `python skills/scripts/verify-doc-links.py`。
2. 若出现新的 provenance 断链：先判断能否映射到真实存在的迁移后路径 —— 能则改路径（`rewrite_path`），
   不能则在文件顶部加/保留 reference-only 横幅（`reference_only` 语义由标记承载）并登记
   `upstream_layout_unmappable`；证据不足时登记 `needs_human_review`（checker 会以 exit 10 提醒人工）。
3. 同步更新 [`link-triage.json`](link-triage.json) 的 `entries[]` 与 `counts`，再跑一次验收命令。
4. 不要通过删除正文、删除链接、把目标改成占位符或放宽规则让数字变小（规范 0.9 / 6.1）。

---

## 10. 未覆盖项与需其他 owner 决策（已登记，未擅自修改）

以下项**不在** 342 条 markdown 断链之内（链接检查器只校验 Markdown `[]()`），本任务无权或无法按白名单处置，
在此登记以免被静默忽略：

| # | 位置 | 事实 | 建议 owner |
|---:|---|---|---|
| O1 | `docs/community/hack-skills/README.md:24`、`README_CN.md:21` | HTML `<img src="./assets/readme-hero-banner.jpg">`：上游 `assets/` 未迁移，图片不可渲染。属于 HTML 资源引用，checker 不覆盖 | T09（hack 树）/ T12（来源包） |
| O2 | `docs/community/ctf-super-hub/README.md:716`、`CONTRIBUTING.md:21`（代码块）与 `START-HERE.md:98`、`THIRD_PARTY_NOTICES.md:64-65`、`LICENSE:18-19`（行内代码） | `scripts/validate_skills.py` / `scripts/install_ctf_tools.sh` 的上游引用；两个脚本都未随本包分发。它们不是 Markdown 链接，因此不触发本门；这些文件也**没有**断链，按白名单不能给它们加横幅。目前已由 `ctf-super-hub/README.md` 顶部横幅统一说明“上游工具未随本包分发” | T09 / T19（正文口径清洗） |
| O3 | `docs/community/ctf-super-hub/README.md:677-678` | 上游目录树 ASCII 图里仍列出 `scripts/install_ctf_tools.sh`、`scripts/validate_skills.py`（纯文本，链接检查器不覆盖；作为上游布局留档保留） | T09（如需清洗） |
| O4 | `skills/community/ai-fullstack/workflows/**`（17 个角色目录、154 条 registry 记录） | 本任务只登记 `docs/community/**` 的断链；社区技能正文自身的链接问题按 12.0 owner 表归 T08 | T08 |

---

## 11. 变更请求（不在 T03 白名单内，仅登记）

| 请求 id | 目标文件（owner） | 请求内容 | 状态 |
|---|---|---|---|
| CR-T03-1 | `docs/WORK-BOARD.md`（T00） | 把 T03 状态与证据 E3 的更新（342 → 0 must-fix，见本文件）登记进施工板 | 待 T00 处置 |
| CR-T03-2 | `docs/community/hack-skills/assets/**`（T09/T12） | O1 的横幅图片缺失：要么补迁移 `assets/readme-hero-banner.jpg`，要么删除 `<img>` 引用 | 待定 |
