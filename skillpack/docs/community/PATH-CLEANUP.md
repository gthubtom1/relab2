# PATH-CLEANUP

> ⚠️ **2026-10-18 复核：本文的路径全部已失效**。
> 它写的是 `skills/community/<source>/` 布局，那个布局已经移到 `skillpack/community-raw/`。
> **本文只是维护记录（provenance），不是执行规则**；不要照抄任何路径。
> 当前布局见 `docs/PROJECT-MAP.md` 与 `skillpack/skills/config/`。

 — APK / Delivery / CTF-Hack 悬空路径与旧框架引用处置记录

状态：maintenance record（T07 + T08 + T09 的**内容修复部分**交付物）
作用：登记 A（悬空路径）/ B（`AI LOAD INSTRUCTION`）/ C（`user-invocable`）三组改动的
provenance、逐条去向与理由，并给出可复跑的只读自证命令。
本文**不是** vendor 留档，不进入 skill 发现面，也不被任何 `SKILL.md` 当作执行规则引用。
分支 `main` · 未提交（本任务禁止 `git add` / `git commit`）· 未联网 · 未执行任何社区脚本。

**行尾标记约定**：`[not-distributed]` 表示该处出现的旧路径是「本仓库不提供」的**说明性文字**，
不是可解析、可执行的引用（规范 17.19 的「显式写成不提供」）。自证命令按这个标记判定残留。

---

## 0. 前后计数（实测，命令见第 5 节）

| 组 | 范围 | 指标 | 修复前 | 修复后 |
|---|---|---|---|---|
| A1 | `skills/community/apk-reverse-source/**` | 字面引用 `skills/apk-reverse/{scripts,references}` | 19 | **0** |
| A1 | 同上 | 适配后目标缺失数（doctor/capabilities/evidence-summary） | 0 | **0** |
| A2 | `skills/community/**` | `bootstrap-project.ps1` 行数 | 15 文件 / 15 行 | 15 文件 / 15 行，全部带 `[not-distributed]`；0 处可执行调用 |
| A2 | `skills/community/ai-fullstack/**` | 「支持自动安装」声明 | 2 | **0** |
| A3 | `skills/community/ai-fullstack/**` | `reverse-skill-private` 出现次数 | 4 文件 / 32 次 | 2 文件 / 5 次，全部带 `[not-distributed]` |
| A3 | 仓库全域 | `reverse-skill-private` 出现次数 | 14 文件 / 104 次 | 12 文件 / 77 次 |
| B | `skills/community/hack-skills/**` | `AI LOAD INSTRUCTION` | 131 文件 / 131 次 | **0** |
| B | 仓库全域（对照） | `AI LOAD INSTRUCTION` | 134 文件 / 142 次 | 3 文件 / 11 次，全在禁止修改的文档/守卫脚本里（见 6.4） |
| C | `skills/community/**` | `user-invocable: "true"` | 3 文件 / 3 次 | **0** |
| C | `skills/community/**` | 重复声明 `user-invocable` 的文件 | 12 | **0**（293 个 raw 技能各 1 次，值均为字符串 `"false"`） |

> 基线口径差异：任务书给出「全域 103 处 `reverse-skill-private`」。本记录用
> `grep -c` 的**出现次数**（同一行多次也计多次）重测为 **104**，差 1；工作树方法与被测提交已在第 5 节命令里固定，可复现。

---

## 1. 范围与边界

允许修改（白名单）与实际触碰：

- `skills/community/apk-reverse-source/**` → 触碰 11 个文件
- `skills/community/ai-fullstack/**` → 触碰 19 个文件
- `skills/community/hack-skills/**` → 触碰 131 个文件
- `skills/community/ctf-super-hub/**` → 触碰 12 个文件
- 新建 `docs/community/PATH-CLEANUP.md`（本文，任务书显式允许）

合计 **173** 个既有文件被修改，**1** 个新文件。未触碰：`skills/INDEX.md`、`docs/INTEGRATION-IMPLEMENTATION-SPEC.md`、
`docs/WORK-BOARD.md`、`skills/community/registry.json`、`README*`/`AGENTS.md`/`CLAUDE.md`、
`docs/community/**` 的既有 README、`.github/**`、`scripts/**`、`skills/scripts/**`（`verify-doc-links.py`
的改动由 T03 完成，不是本任务）。

**导入器覆盖集风险（CR-002 输入）**：`scripts/adapt-community.py` 单次运行会覆盖 1111 条路径，
其中包含本记录改动的 `skills/community/apk-reverse-source/**`、`skills/community/ctf-super-hub/**`、
`skills/community/hack-skills/**`、`skills/community/ai-fullstack/**` 以及本文件所在的 `docs/community/**`。
因此本记录的全部改写目前都是**导入器之外的独立改动**，下一次导入会静默回退。T05 必须把同样的改写
纳入受管变换（或在导入后重放），否则 A/B/C 三组都会复原。守卫：
`python skills/scripts/verify-community-banner.py` 会立刻暴露 B 组与 C 组的回退。

---

## 2. A 组：悬空路径

### 2.1 A1 — APK（`skills/community/apk-reverse-source/**`）

任务书点名的 3 条（独立实测确认；wrapper `skills/community/apk-extension/SKILL.md` 本身干净）：

| 位置 | 原文 | 处置 |
|---|---|---|
| `SKILL.md:8` | `capability_registry: skills/apk-reverse/scripts/capabilities.py` | 改为 `skills/community/apk-reverse-source/scripts/capabilities.py`（该文件真实存在） |
| `SKILL.md:9` | `evidence_summary: skills/apk-reverse/references/evidence-summary.md` | 改为 `skills/community/apk-reverse-source/references/evidence-summary.md`（真实存在） |
| `SKILL.md:124` | `python skills/apk-reverse/scripts/doctor.py --json` | 改为 `python skills/community/apk-reverse-source/scripts/doctor.py --json`（真实存在） |

同类悬空引用（规范 §11.2 的验收正则 `skills/apk-reverse/scripts\|skills/apk-reverse/references` 同样覆盖），
一并改为适配后路径，共 16 处：

| 位置（修复前的字面引用） | 处置 |
|---|---|
| `references/protocol-reverse.md` ×1（`protobuf_decode_raw.py` 用法） | → `skills/community/apk-reverse-source/scripts/…` |
| `references/rasc-and-droidsaw.md` ×4（`rasc_build.py` 用法/验证） | 同上 |
| `references/split-apk.md` ×3（`repack.py` 用法） | 同上 |
| `scripts/dex_mem_scan.py` ×1（docstring 用法） | 同上 |
| `scripts/kernelsu_syscall_mask.py` ×2（生成头 + 模块 README 模板） | 同上 |
| `scripts/rasc_build.py` ×3（docstring：references 指引 + 路径层级说明） | 路径改为适配后；「three levels up」按实际层级改为 **four**（说明文字与代码一致，代码本身未改） |
| `scripts/vmp_diff_harness.py` ×1（`dexutil.py` 缺失提示） | 同上 |
| `scripts/capabilities.py` ×1（`GATE_FILES['file:scan_leaks.py']`） | → `community/apk-reverse-source/scripts/scan_leaks.py`，**依据**见下 |

`capabilities.py` 的依据（不靠猜，纯路径算术，可复算）：

```
REPO_ROOT = dirname(dirname(SKILL_DIR));  SKILL_DIR = <repo>/skills/community/apk-reverse-source
⇒ REPO_ROOT = <repo>/skills
⇒ join(REPO_ROOT,'skills/apk-reverse/scripts/scan_leaks.py')              isfile=False
⇒ join(REPO_ROOT,'community/apk-reverse-source/scripts/scan_leaks.py')    isfile=True
```

条目旁的注释已写明：若将来把 `REPO_ROOT` 修正为 `<repo>`，此值必须改回
`skills/community/apk-reverse-source/scripts/scan_leaks.py`。

**未修的同类问题（登记，不猜）**：同一个 `capabilities.py` 的 `REPO_ROOT` 推导使
`os.path.join(REPO_ROOT,'tools','_work',...)`（`rasc` 构建产物探测，约 :568）在适配布局下指向
`<repo>/skills/tools/_work`，而 `rasc_build.py` 实际构建到 `<repo>/tools/_work`；:705 又用
`dirname(REPO_ROOT)` 抵消了一次。这是**脚本路径基准**问题，不是字符串替换问题；改动会同时影响多个调用点，
且本任务被禁止执行社区脚本来验证行为，所以按要求**登记而不猜改**，交由 APK 包 owner 决定是否统一 `REPO_ROOT` 语义。

另外 2 处**保序说明**（不是悬空引用，属于上游安装布局的描述）：`references/evidence-summary.md:5` 与
`evidence/known-limitations.md:3` 保留 `skills/apk-reverse/` 字面量（描述 `npx skills add` 的上游安装位置），
并各加一句括注指出本融合仓库的适配副本在 `skills/community/apk-reverse-source/`。保留理由：这是 provenance
事实，删掉会让读者以为两者是同一目录。

### 2.2 A2 — Delivery：`bootstrap-project.ps1`（15 处）

目标在仓库内**不存在**（`Get-ChildItem -Recurse -Filter bootstrap*.ps1` 无结果；上游
`ai-fullstack-delivery` 带该脚本，融合包有意排除）。

处置：15 个 `workflows/*/WORKFLOW.md` 的「工具自举」段整体改写为
「`scripts/bootstrap-project.ps1` **未随本仓库分发** `[not-distributed]`：上游带该脚本，融合包按规范 §2.4 的
`autoInstall=false` 有意排除，仓库内不存在任何等价脚本，因此没有可调用的自动入口。缺工具时只产出安装计划，
由人工确认后手动执行」+ 4 步人工计划（读 tool-index → 写计划 → 人工确认 → 人工执行后回填）。

同时清理同段内与 `autoInstall=false` 冲突的残留：

- 2 处「支持自动安装：…」（`backend-engineer`、`frontend-engineer`）→ 改为括注「上游脚本声称可自动安装：…；
  本仓库不提供该自动安装路径，按上面的手动计划处理。」
- 16 个文件（含 `reverse-pentest`）的失败处理表 2 行 → `| bootstrap 成功 |` 改为 `| 手动安装计划执行成功 |`，
  `| bootstrap 失败，原因明确 |` 改为 `| 手动安装失败，原因明确 |`（共 32 行）。

**没有**任何一处被改成让代理自动下载/安装；全部指向「只生成计划 + 人工确认」。

### 2.3 A3 — Delivery：`reverse-skill-private/`（单文件 22 处 / 单包 32 处）

`reverse-skill-private` 是被 `scripts/adapt-community.py` **有意排除的第二套框架**
（`registry.json` 的 `excluded[]` 记 55 条，reason 字段原文为
「vendored second reverse-skill framework; canonical base already provides this capability」）。
本记录一律**改写到 canonical 能力或显式标注不提供**，未把任何第二套框架内容重新引入仓库。

32 处的去向（行号是 **HEAD 行号**）：

| 文件 | HEAD 行 | 原文要点 | 去向 |
|---|---|---|---|
| `workflows/reverse-pentest/WORKFLOW.md` | 7 | 「本工作流内置 14 个技能模块…技能库位于 `reverse-skill-private/skills/`」 | 改写为「技能库由 canonical `skills/` 提供…上游第二套框架已被 `adapt-community.py` 有意排除 `[not-distributed]`」 |
| 同上 | 113 | 经验索引路径 | → `skills/field-journal/_index.md` |
| 同上 | 115 | 路由矩阵路径 | → `skills/routing.md` |
| 同上 | 142 | 「技能库路径」 | → `skills/`（canonical） |
| 同上 | 165 | 路由读取顺序第 1 条 | → `skills/routing.md` |
| 同上 | 244 | 回写 field-journal 的写入路径 | → `skills/field-journal/` |
| 同上 | 248 | 更新 `_index.md` | → `skills/field-journal/_index.md` |
| 同上 | 257 | 更新系统索引 | → `skills/field-journal/_index.md` |
| 同上 | 268 | 工具索引为准的文件 | → `skillpack/skills/TOOLS.md`（已废弃：工具索引不再生成，改为运行时探测） |
| 同上 | 285 | `bootstrap-reverse.ps1` 调用（**不存在于该路径**） | 删除可复制调用；改为 canonical `skills/scripts/bootstrap-reverse.ps1` 的人工路径 + `autoInstall=false` 说明 |
| 同上 | 293 | `refresh-tool-index.ps1` 调用 | → `skills/scripts/refresh-tool-index.ps1`，并标注为人工步骤 |
| 同上 | 321 | 经验索引（经验复用段） | → `skills/field-journal/_index.md` |
| 同上 | 475 | 质量检查项 | → `（skills/field-journal/）` |
| 同上 | 558 | 「技能库路径」 | → `skills/`（canonical） |
| 同上 | 559 | 上游仓库 URL `zhaoxuya520/reverse-skill-private.git` | 删除；替换为「不得通过 git pull/clone 重新引入」的禁止说明 `[not-distributed]` |
| 同上 | 563 | 新增 skill 的流程文件 | → `skills/CONTRIBUTING.md` |
| 同上 | 564 | 「在 `reverse-skill-private/` 目录中 git pull」 | 删除该动作；改为走 canonical 来源流程（T05 的导入器） |
| 同上 | 568 | 技能总控入口 | → `skills/SKILL.md` |
| 同上 | 569 | 路由矩阵入口 | → `skills/routing.md` |
| 同上 | 570 | 工具索引入口 | → `skillpack/skills/TOOLS.md` |
| 同上 | 571 | 经验索引入口 | → `skills/field-journal/_index.md` |
| 同上 | 572 | 自举脚本入口 | → `skills/scripts/bootstrap-reverse.ps1`（人工执行，需用户显式批准） |
| `workflows/reverse-pentest/routing.md` | 10, 11, 12 | YAML 的 `skill_library` / `skill_routing` / `tool_index` | → `skills/`、`skills/routing.md`、`skillpack/skills/TOOLS.md` |
| 同上 | 31 | 「按 `reverse-skill-private/skills/routing.md` 路由」 | → canonical `skills/routing.md` |
| `workflows/reverse-pentest/`TOOLS.md` | 6 | 「优先使用内置工具链」 | → canonical `skills/` 包内已登记工具链 |
| 同上 | 8 | 工具缺失时检查的文件 | → `skillpack/skills/TOOLS.md` |
| 同上 | 67, 68, 69 | 详细工具矩阵的三个路径 | → `skillpack/skills/TOOLS.md`、`skills/`TOOLS.md`、`skills/pentest-tools/SKILL.md` |
| `workflows/reverse-pentest/pitfalls.md` | 13 | 「先查 tool-index」 | → canonical `skillpack/skills/TOOLS.md` |

同节内的一致性修正（同一缺陷族，避免留下互相矛盾的执行说明）：

- `WORKFLOW.md` 行为链第 5 步「联网搜索方法论」→「用本地已有资料给出方法论（不隐式联网）」；
- 第 7/8 步「调用 bootstrap-reverse.ps1 自动补齐 / 自动补齐失败」→「只输出安装计划，人工执行 / 人工安装失败」；
- 禁止行为「不要反复重试已失败 2 次的自动安装」→「人工安装」，并新增一条「不要隐式安装、下载或改写全局/MCP 配置」；
- 模块表 `game-security/` 行 → 标注 **本仓库不提供独立模块**，并把游戏/反作弊任务指向 canonical
  `reverse-engineering/`（`skills/routing.md` 的 game reverse / anti-cheat 行 + seed-014）；
  `../CTF-Sandbox-Orchestrator/` → `CTF-Sandbox-Orchestrator/`（仓库根，136 个文件已被 git 跟踪）。

**未修（登记，T02 owner）**：`skills/community/registry.json` 仍有 55 处 `reverse-skill-private`，
全部位于 `excluded[].source_path`，记录的是**被排除内容在上游的位置**，不是本仓库可解析路径。
本任务禁止修改该文件，故只登记、不改；是否改写措辞由 T02 决定。

### 2.4 CTF：`install_ctf_tools.sh`（1 处 wrapper 断链）

`skills/community/ctf-super-hub/solve-challenge/SKILL.md:72` 曾以
`[scripts/install_ctf_tools.sh](../scripts/install_ctf_tools.sh)` 链接一个**未随本仓库分发**的上游脚本
（上游 `ctf-super-hub/scripts/install_ctf_tools.sh` 存在，但 `adapt-community.py` 只搬技能正文）。
这是 `verify-doc-links` 里**唯一**的 `wrapper` 类断链。

处置：该段已在工作树中被改写为「上游有该脚本但未分发 + 手动准备 4 步 + 显式引用 `autoInstall=false`
与 `AGENTS.md` 的批准要求」，符合规范 §7.1「不执行 install_ctf_tools.sh，不默认联网」。
**归属说明**：这次改写不是本代理写的（本代理读到的原始正文仍是安装器调用，随后读同一文件时已是改写版）；
本代理对该文件的写入只有 `user-invocable` 归一化（见 4.1）。现状态 wrapper 断链 = 0。

---

## 3. B 组：`AI LOAD INSTRUCTION`（131 处 → 0）

这 131 处是 vendor 正文里的**二级加载指令**，与主路由竞争（规范 17.19）。实测分布：
**95 个 `SKILL.md` + 36 个辅助文档**，每个文件恰好 1 处。

统一处置（选项「改写成不可执行的来源摘要」）：

1. 标签替换：`**AI LOAD INSTRUCTION**:` → `**Vendor source summary (reference-only; not a load instruction)**:`
2. 同一段内的祈使「加载」措辞去指令化，全部在**同一段**内完成，不改动 vendor 的技术内容：
   - `Load this for / when you need …` → `Reference for …`
   - `Load this when you've …` → `Reference for cases where you've …`
   - `Load this when exploiting …` → `Reference for exploiting …`
   - `Use this skill (first) when …` → `Applies when … / First-choice reference when …`
   - `Assumes the main [SKILL.md](…) is (already) loaded for X.` → `Companion to [SKILL.md](…), which covers X.`
   - `, load the companion [SCENARIOS.md](…)` → `, see the companion [SCENARIOS.md](…)`
   - `load [X](…)` / `), load [` / `load [` → `see [X](…)` / `), see [` / ` see [`
   - `cross-load` → `cross-reference`；`Do NOT load this if` → `It is not needed when`
3. 3 处残留的 `Assumes …` 描述句改为陈述句（`prototype-pollution`、`request-smuggling`、`sqli-sql-injection`），
   避免 `Assumes` 读成前置加载条件。
4. 2 个跨行 blockquote（`ghost-bits-cast-attack/PAYLOAD_COOKBOOK.md` 的 7 行段、
   `ghost-bits-cast-attack/SKILL.md` 的 13 行段，含 `Source:` 段）按段重排，段落结构与 `Source:` 归属保留。

逐文件机械核对结果：转换后**没有任何** `AI LOAD INSTRUCTION` 残留，且新标签行不含
`Load this` / `Load the` / `load [` / `load the companion` / `cross-load` / `LOAD FIRST` / `Use this skill` /
`Assumes ` 等祈使标记（扫描结果 0）。

36 个**辅助文档**（原任务描述容易漏掉的部分）：

```
active-directory-acl-abuse/BLOODHOUND_PATHS.md, active-directory-certificate-services/ADCS_ESC_MATRIX.md,
active-directory-kerberos-attacks/KERBEROS_ATTACK_CHAINS.md, android-pentesting-tricks/FRIDA_SCRIPTS.md,
anti-debugging-techniques/ANTI_DEBUG_MATRIX.md, binary-protection-bypass/PROTECTION_BYPASS_MATRIX.md,
browser-exploitation-v8/V8_EXPLOITATION_PATTERNS.md, container-escape-techniques/DOCKER_ESCAPE_CHAINS.md,
deserialization-insecure/JAVA_GADGET_CHAINS.md, ghost-bits-cast-attack/PAYLOAD_COOKBOOK.md,
heap-exploitation/HOUSE_OF_TECHNIQUES.md, heap-exploitation/IO_FILE_EXPLOITATION.md,
ios-pentesting-tricks/IOS_RUNTIME_TRICKS.md, kernel-exploitation/KERNEL_HEAP_TECHNIQUES.md,
kernel-exploitation/KERNEL_MITIGATION_BYPASS.md, linux-privilege-escalation/KERNEL_EXPLOITS_CHECKLIST.md,
linux-privilege-escalation/SUID_CAPABILITIES_TRICKS.md, macos-process-injection/DYLIB_XPC_TECHNIQUES.md,
macos-security-bypass/TCC_BYPASS_MATRIX.md, ntlm-relay-coercion/COERCION_METHODS.md,
prototype-pollution-advanced/KNOWN_GADGETS.md, request-smuggling/H2_SMUGGLING_VARIANTS.md,
rsa-attack-techniques/RSA_ATTACK_CATALOG.md, sandbox-escape-techniques/PYTHON_SANDBOX_ESCAPE.md,
sandbox-escape-techniques/SECCOMP_BYPASS.md, sqli-sql-injection/SQLMAP_ADVANCED.md,
ssrf-server-side-request-forgery/URL_PARSER_TRICKS.md, stack-overflow-and-rop/ROP_ADVANCED_TECHNIQUES.md,
symbolic-execution-tools/ANGR_COOKBOOK.md, symmetric-cipher-attacks/BLOCK_CIPHER_ATTACKS.md,
waf-bypass-techniques/WAF_PRODUCT_MATRIX.md, web-cache-deception/CACHE_POISONING_TECHNIQUES.md,
windows-av-evasion/AMSI_BYPASS_TECHNIQUES.md, windows-lateral-movement/CREDENTIAL_DUMPING.md,
windows-privilege-escalation/TOKEN_POTATO_TRICKS.md, windows-privilege-escalation/UAC_BYPASS_METHODS.md
```

其余 95 个是 `skills/community/hack-skills/*/SKILL.md`。完整 131 条清单可用
`git diff --numstat -- skills/community/hack-skills` 直接取（129 个文件 +1/−1，2 个跨行段文件为 +5/−7 与 +9/−12）。

**登记为残留（不在本白名单）**：`skills/community/hack-skills/` 下计数为 0；仓库剩下的 3 个文件是
`docs/INTEGRATION-IMPLEMENTATION-SPEC.md`（5）、`docs/WORK-BOARD.md`（2）、
`skills/scripts/verify-community-banner.py`（4，守卫常量）。三者都是**反向说明**（描述缺陷本身），
且分别属 T00 与 T00 的守卫脚本，本任务禁止修改。

**同类但未纳入本次范围的观察（登记给 T19）**：hack-skills 的 `SKILL.md` 里仍有不含该字面量的二级路由段，
例如 `prototype-pollution-advanced/SKILL.md` 的 `## 0. RELATED ROUTING` 中的 `**LOAD FIRST**`、
`ssti-*/SKILL.md` 的 `cross-load`、`race-condition/SKILL.md` 的 `Routing note: … cross-load`。
它们与 17.19 的「二级路由」同类，但不在本任务「131 处 `AI LOAD INSTRUCTION`」的计量口径内，
故只登记、不改，交由 T19 的全库扫描统一处置。

---

## 4. C 组：`user-invocable`（12 个文件 → 0）

### 4.1 自相矛盾（3 个）：统一为 `"false"`

`skills/community/ctf-super-hub/` 下的 `ctf-beginner-hub`、`ctf-writeup`、`solve-challenge`
各自先声明 `user-invocable: "true"` 再声明 `user-invocable: "false"`（同一 frontmatter 内）。

依据：其余 290 个 raw 技能全部为 `"false"`；规范 17.27 与 WORK-BOARD C2 要求 raw 技能不可被直接发现；
保留 `"true"` 会让 3 个 raw 技能成为可发现入口，与 wrapper-only 冲突。处置：**保留首个键并置为 `"false"`，
删除后一个重复键**。

### 4.2 重复但一致（9 个）：去重为一个键

`ctf-ai-ml`、`ctf-crypto`、`ctf-forensics`、`ctf-malware`、`ctf-misc`、`ctf-osint`、`ctf-pwn`、
`ctf-reverse`、`ctf-web`：两个键都是 `"false"`，保留首个、删除第二个。

### 4.3 全量核对

`skills/community` 下 297 个 `SKILL.md` = **293 个 raw（每个恰好 1 次 `user-invocable: "false"`）**
\+ 4 个 wrapper（`apk-extension`、`ctf-hub`、`delivery`、`hack-hub`，按设计**不含**该键，它们是可调用入口）。
值分布：`"false"` 293 次、`"true"` 0 次；`user-invocable` 出现在 frontmatter 之外的次数为 0。

---

## 5. 自证命令（只读，A/B/C 同时归零则 exit 0）

在仓库根运行（纯 ASCII 载荷，`$check | python -` 避开 PowerShell 5.1 原生命令引号/代码页问题）：

```powershell
cd C:\relab2
$check = @'
import pathlib,re,sys
C=pathlib.Path('skills/community')
WRAP={'apk-extension','ctf-hub','delivery','hack-hub'}
tags=('bootstrap-project.ps1','reverse-skill-private')
legacy=('skills/apk-reverse/scripts','skills/apk-reverse/references')
a1=[(p.as_posix(),k) for p in C.rglob('*') if p.is_file() and p.suffix in('.md','.py','.json','.js','.ps1','.sh') for k in legacy if k in p.read_text(encoding='utf-8',errors='replace')]
a2=[t for t in('skills/community/apk-reverse-source/scripts/doctor.py','skills/community/apk-reverse-source/scripts/capabilities.py','skills/community/apk-reverse-source/references/evidence-summary.md') if not pathlib.Path(t).is_file()]
a3=[f'{p.as_posix()}:{i}' for p in C.rglob('*.md') for i,l in enumerate(p.read_text(encoding='utf-8',errors='replace').splitlines(),1) if any(t in l for t in tags) and '[not-distributed]' not in l]
reg=(C/'registry.json').read_text(encoding='utf-8').count('reverse-skill-private')
b=sum(p.read_text(encoding='utf-8',errors='replace').count('AI LOAD INSTRUCTION') for p in (C/'hack-skills').rglob('*') if p.is_file())
raw=[p for p in C.rglob('SKILL.md') if p.parent.name not in WRAP]
c=[p.as_posix() for p in raw if re.findall(r'^[ \t]*user-invocable[ \t]*:[ \t]*(\S+)[ \t]*$',p.read_text(encoding='utf-8'),re.M)!=['"false"']]
print(f'A1 dangling source-repo path refs : {len(a1)} {a1}')
print(f'A1 adapted targets missing        : {len(a2)} {a2}')
print(f'A2/A3 untagged legacy path refs   : {len(a3)} {a3}')
print(f'A  registry excluded-provenance   : {reg}  (registry.json excluded[].source_path, T02-owned, not a resolvable path)')
print(f'B  AI LOAD INSTRUCTION            : {b}')
print(f'C  raw skills / non-conforming    : {len(raw)} / {len(c)} {c}')
sys.exit(1 if (a1 or a2 or a3 or b or c or len(raw)!=293) else 0)
'@
$OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$check | <python> -
```

实测输出（exit 0）：

```text
A1 dangling source-repo path refs : 0 []
A1 adapted targets missing        : 0 []
A2/A3 untagged legacy path refs   : 0 []
A  registry excluded-provenance   : 55  (registry.json excluded[].source_path, T02-owned, not a resolvable path)
B  AI LOAD INSTRUCTION            : 0
C  raw skills / non-conforming    : 293 / 0 []
```

配套的既有门（同一口径的上游守卫）：

```powershell
python skills/scripts/verify-community-banner.py     # B=0，C=0，wrapper problems=0（剩 15 项 docs/community banner 属 T03）
python skills/scripts/verify-doc-links.py            # active=0 wrapper=0；341→13 条 provenance 已登记 link-triage
powershell -NoProfile -ExecutionPolicy Bypass -File skills/scripts/verify-routing-coherence.ps1
```

---

## 6. 登记为「本仓库不提供 / 需其他 owner」的条目

| # | 条目 | 现状 | 依据 | 需要谁 |
|---|---|---|---|---|
| 6.1 | `workflows/reverse-pentest` 的 `game-security/` 模块 | 本仓库不提供独立模块；游戏/反作弊走 canonical `reverse-engineering/` | `skills/game-security` 不存在；`registry.json` `excluded[]` 记为上游 `reverse-skill-private/skills/game-security/SKILL.md`（第二套框架）；`skills/routing.md:30/37/109/188/241/242` 把 game reverse / anti-cheat 指向 `reverse-engineering` | 已按 canonical 改写，无需追加动作 |
| 6.2 | `scripts/bootstrap-project.ps1` | 本仓库不提供；已写成「未随本仓库分发 + 人工安装计划」 | 全仓库 `-Filter bootstrap*.ps1` 无结果；15 处引用全部带 `[not-distributed]` | 已处置 |
| 6.3 | `reverse-skill-private/`（第二套框架） | 本仓库不含，且禁止重新引入；`git pull` 指引已删除 | `adapt-community.py` 有意排除；`registry.json` 55 条 `excluded[]` | 已处置；`registry.json` 措辞归 T02 |
| 6.4 | `AI LOAD INSTRUCTION` 残余 11 处 | `docs/INTEGRATION-IMPLEMENTATION-SPEC.md`(5)、`docs/WORK-BOARD.md`(2)、`skills/scripts/verify-community-banner.py`(4)，均为反向说明 | 三处都不在允许修改白名单 | T00 |
| 6.5 | `capabilities.py` 的 `REPO_ROOT`/`tools/_work` 路径基准 | 未改（会同时影响多个调用点，且不能执行脚本验证） | 见 2.1 的路径算术 | APK 包 owner / T07 |
| 6.6 | hack-skills 的 `## 0. RELATED ROUTING` / `LOAD FIRST` / `cross-load` 二级路由段 | 未改（不在「131 处」计量口径内） | `prototype-pollution-advanced/SKILL.md` 等 | T19 全库扫描 |
| 6.7 | `docs/community/**` 15 个文件缺 reference-only banner | 未改（T03 范围） | `verify-community-banner.py` 输出 15 项 | T03 |
| 6.8 | 导入器会回退本记录的全部改写 | 已登记为 CR-002 输入 | `adapt-community.py` 覆盖 1111 条路径，含本记录全部文件 | T05 |

---

## 7. 未触碰与并发观察

- 本代理未执行 `git add` / `git commit`；未联网；未运行任何社区脚本、安装脚本、bootstrap；
  未新增脚本文件（自证检查是本文档内的命令片段）。
- 编辑过程中修正过一次自造的**行尾回归**：`workflows/reverse-pentest/{routing.md,`TOOLS.md`,pitfalls.md}`
  曾从 LF 变成 CRLF（3 文件），已归一化回 LF，`git diff` 无整文件重写。
- 并发观察：`skills/community/ctf-super-hub/solve-challenge/SKILL.md` 的 `## Environment Setup` 段
  在本代理作业期间由**其他写入者**改写（见 2.4）。本代理对该文件的唯一写入是 frontmatter 的
  `user-invocable` 归一化。若 12.0 的「一个目录只能一个 owner」被严格执行，这条需要 T00 登记。
