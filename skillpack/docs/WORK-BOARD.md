# WORK-BOARD — 融合施工协调板

本文件是 T00 的协调资源，也是任务状态、lease、变更请求和冲突登记的唯一位置。
施工前必读：`docs/INTEGRATION-IMPLEMENTATION-SPEC.md` 第 0、4、12（含 12.0）节。

## 1. 基线（T00 建立，续跑时先核对是否漂移）

| 项目 | 值 |
|---|---|
| 仓库根 | `C:\relab2` |
| 分支 | `main` |
| 集成 commit（本板建立时） | `4039716cf20267152b76096b76063144c1bd3421` |
| 该 commit 的 tree | `47c2e45feb830bcf8562fe55a7fe73a03b98179f` |
| **T26 施工 commit** | `f04323638d1df5de38fb12860daa5823338feecb`（社区路由信号层） |
| registry `schemaVersion` | `1.0` |
| 社区技能条目 | 293 |
| 排除条目 | 55 |
| source record 数 | 4（**不含** canonical base，见 17.15） |

### 1.1 上游快照（位于仓库**外部**，见规范 1.4 与 17.28）

| source | snapshot 路径 | commit | 工作树 |
|---|---|---|---|
| reverse-skill（母框架 / canonical base） | `<开发根>\upstream\reverse-skill` | `cab634bd855fc287f6e420c1f36fd1a6b9245960` | clean |
| ctf-super-hub | `<开发根>\upstream\ctf-super-hub` | `16926d6d4216183995693e9c7936c042eb7f2fae` | clean |
| AI-Fullstack-Delivery-Workflow | `<开发根>\upstream\AI-Fullstack-Delivery-Workflow` | `ab96b897d719941219ab3b3badb47cd6fda3e0eb` | clean |
| apk-reverse | `<开发根>\upstream\apk-reverse` | `7b6c6932a95f03d778e81e5e1a2cbf6f62dc97fd` | clean |
| hack-skills | `<开发根>\upstream\hack-skills` | `6fbf0bc8d5c71830d62543a308d8744606c43d7c` | clean |

快照在融合仓库之外，所以“单独复制 integrated-skill-hub 即可复核 provenance”当前**不成立**；这是 T12 的验收项，不是既成事实。

### 1.2 运行环境基线

| 工具 | 版本 |
|---|---|
| Python（本会话使用） | 3.12.14 |
| Windows PowerShell | 5.1.28000.2704 |
| git | 2.55.0.windows.3 |
| PowerShell 7 / pwsh | 本会话未验证 |
| Linux / macOS | 本会话未验证 |

平台声明必须与真实 CI job 对应（17.30）。上表未验证的平台，文档中不得列为“受支持”。

## 2. 任务状态

状态取值：`not-started` / `in-progress` / `blocked` / `done` / `frozen`（owner 未启动或失败，文件冻结）。

| 任务 | owner 资源 | 状态 | 备注 |
|---|---|---|---|
| 施工前冻结（文档侧） | — | done | commit `4039716`：章节重排 + 第 4 节冻结合同 + 发现隔离/attestation/许可证/macOS/CI/遥测补充 + 12.0 owner 登记表 |
| T00 | WORK-BOARD、规范 | done | 本板即产出；另交付 5 个门与自我豁免漏洞修复 |
| T01 | INDEX 生成、发现隔离 | **done（已合入 `0a36a65`）** | raw 内容搬到 `community-raw/`；`audit-discovery-surface.py` exit 20 → **0**；递归发现 343 → **50**；INDEX 暴露 vendored 路径 293 → **0** |
| T02 | registry.json、schemas/** | **done（已合入 `967e4d1`）** | 4.1/4.2/4.3 全字段、`wrappers[]`、3 个 JSON Schema、`profile-map.json`、4.6 逐行测试、`community-route.py` fail-closed。遗留：16 个 null 值（owner T12/T05）、`canonical_downstream` 仅 6 条有证据 |
| T03 | docs/community/**、链接分类 | **done（已合入 `686796d`）** | 342 → 13 断链，active=0/wrapper=0，exit 0；328 条改写 + 13 条登记 + 4 个横幅 |
| T04 | validate-integration.py、verify-release-gate.py | **done（wave 1）** | argparse + `--release` 真实阻断（exit 20）+ 未知参数 exit 2；去掉硬编码 `== 4 sources`/`== 55 excluded` 改为从 registry 数组推导（关闭 E9）；新建 `verify-release-gate.py`、根 `NOTICE`、`docs/RELEASE-GATE-CHECKLIST.md`；**CR-004 已关闭**。仍未清零：R10（notice 逐字段一致性，改 `docs/community/*` 不在其白名单）、R16（attestation，wave 2 已产出工具）、R17（CVE 需联网）、R19（per-file license 字段 owner T02） |
| T05 | scripts/adapt-community.py | **done（wave 1）；wave 2 由 U11 续建受管变换层** | 403 行 → 五子命令（inspect/import/verify/promote/rollback）；`--help` 纯打印；inspect/verify/dry-run 零写入（实测 `writes=[]`）；promote 是 journaled rename，**明确不声称原子**；写入根指向 `community-raw/`；digest 契约冻结于 `IMPORTER-LIFECYCLE.md` §4；用例 60/60 → **75/75** |
| T06 | verify-repository-security.py | **done（wave 1）** | 9 KB → 23.4 KB；覆盖 raw entrypoint / 秘密 / 二进制伪装 / symlink / 明文端点 / 二级路由 digest / provenance；**8 类负向对照全部真实非零退出**。实测 `vendored_router_files=70`（与 U3 独立复算吻合）。已知边界见 `SECURITY-SCAN.md` §2：`SCAN_EXCLUDES` 为精确路径匹配（带前缀复制体会自我命中）、U3 正则漏 `## 6.` 级 2 个文件 |
| T07 | APK 树与 wrapper | **done（已合入 `37d98a4`）** | 19 处 `skills/apk-reverse/{scripts,references}` → 0，全部指向真实适配路径 |
| T08 | Delivery 树与 wrapper | **done（已合入 `37d98a4`）** | 15 处 bootstrap 调用 → 0（改为"未分发 + 人工计划"）；单包 private 32 → 5 处（全为"不提供"说明） |
| T09 | CTF/Hack 树与 wrapper | **done（已合入 `37d98a4`）** | `AI LOAD INSTRUCTION` 131 → 0（含 36 个易漏的辅助文档）；`user-invocable` 矛盾/重复 12 → 0 |
| kq-01 | registry 描述解析 | **done（已合入 `0a36a65`）** | 103 条字面 `>-` + 16 条带引号（共 119 条坏值）→ **0**；新增 frontmatter 解析模块 + 59 断言（15 个负向守卫） |
| kq-02 | 路由排序 | **done（已合入 `0a36a65`）** | 修好描述后暴露并列排序缺陷；引入 field-aware 排序（名字命中 ×3 > 描述命中 ×1）；SSRF rank 5 → **1**；附 8 个防过度收窄用例 |
| T10 | .github/workflows、tests | **done（wave 1）** | **17 门全部接线**：`skills/tests/ci-gates.json` 声明每门的退出码语义、`run-ci-gates.py` 为 CI 单入口、`verify-gate-wiring.py` 交叉校验接线本身（manifest 带 digest 锁，堵死"从清单删门即自豁免"）；`ci.yml` 补 `permissions: contents: read`；6 条负向对照证明注入缺陷会让构建转红。**U10 已关闭**。未验证边界：workflow 从未在真实 runner 执行；Linux/macOS 按 17.30 仍 unverified |
| T11 | 加载预算与读取逻辑 | **done（wave 2）** | 预算数值化：`MAX_WRAPPER_CANDIDATES=5`、`MAX_TOTAL_REFERENCES=50`；超预算 `blocked`/`budget_exceeded`（**exit 20**）不再静默截断；`--limit` 钳制 1..5（越界 exit 2）；wrapper 加载指令段加 Loading budget 段；`docs/community/LOADING-BUDGET.md`。改前实测：有 hint 命中 30 条只展示 3 条、**27 条静默丢失且 exit 0**。`REFERENCE_LIMIT=3`、置信度与歧义规则未动；57 个既有用例最大命中 42，故 50 不碰任何守卫 |
| T12 | source lock、bundle | **done（wave 2，与 T14 合并为一张卡）** | 新建 `skills/community/source-lock.json`（4 条 17.28 attestation）、`scripts/verify-source-attestation.py`、`scripts/verify-community-bundle.py`、`docs/community/SOURCE-BUNDLE.md`。真仓双脚本 exit 0；**无 `.git`、无 `../upstream` 的复制体 exit 10 且逐条具名**——HANDOFF §2.1 记的"单独复制不可复核"落点。5 类阻断对照全 exit 20。16 个 `null` 的字段需求已交 T02，**未擅自写 registry** |
| T13 | 对抗交叉复核 | **done（wave 3 卡 E）** | 由独立代理 clone 到仓库外重新走链路（**不接受"文件存在"作为证据**）：四条 dry-run（CTF/Hack/APK matched、Delivery needs_review）、三条负向测试（安全门 exit 1 / 预算 exit 2 与 20 / provenance exit 20 与 10）、许可证三处口径逐数一致。产出 **P0 无、P1×4** 与 release 结论（local-only candidate，不是可发布物）；**同时证伪了若干疑点**（banner 确是纯文档、预算单次不可绕、U3/17.19 解释成立），报告见 [`docs/community/CROSS-REVIEW-WAVE12.md`](community/CROSS-REVIEW-WAVE12.md)。四条 P1 的处置见 U9 与"T13 P1 整改"提交 |
| T14–T25 | 见规范第 18、19 节 | **大部完成** | **T14 已随 T12 合并完成（wave 2）**。**T21 done（wave 3 卡 G）**：第 5 条 canonical base 记录（`reverse-skill`，baseline `cab634bd…` + 集成 `7a1d453`）、`schemas/canonical-base-lock.json`、`scripts/verify-canonical-base-lock.py`（`--require-signatures` 真树 exit 20 = 无签名拒入 redistributable）、`docs/community/CANONICAL-BASE-LOCK.md`；签名/trust root/轮换/撤销**如实登记为未实现**。**T24 done（wave 2 卡 D + CR-T24-01）**：`permissions: contents: read`、job 级 write 配审查记录、`.github/CODEOWNERS`、17.19 清洗、平台矩阵标注 unverified；接线门文案滞后已由 CR-T24-01 修正（U12 关闭）。**T16 done（wave 5 卡 M）**：`scripts/build-release-candidate.py`（build/check，只发 local-only、out-dir 禁在树内）、`scripts/verify-release-approval.py`（完整性+审批+**双人**+门 pin+签名+回滚，缺省即拒）、`schemas/release-candidate.json` + `release-approval.json`、`.github/workflows/release.yml`（workflow_dispatch + environment 批准、只读、无 secret、全 SHA pin）、`docs/RELEASE-ARTIFACT.md`；实测候选 sources=5/skills=293/**SBOM components=298**、7 条负向对照全真实非零（未批准/自批准/篡改一位/门漂移/redistributable 各 exit 20），PR 自改 gate 不可行＝门 pin + CODEOWNERS/required-checks/environment 三层。**有意未实现已具名（D1–D7）**：签名/trust root/轮换/撤销、redistributable 不可发、**CVE 扫描未实现且不伪造**（SBOM 空数组＝未扫描）、逐文件许可记录缺 T02 字段、跨机复核降级、组合许可 undetermined、**release 流程未在真实 runner 验证（静态合规而已）**。**T18 done（wave 6 卡 N）**：`skills/tests/golden-route.json`（**26 用例**：13 正向 ×CTF/API/APK/Delivery×en/zh/mixed、2 低置信、1 歧义、**4 错误输入**、**6 U9 pin**）+ `skills/scripts/test-golden-route.py` + `docs/community/GOLDEN-ROUTE.md`；**把 U9 的 5 条"不可修"固化为期望行为**（谁顺手改好一条，门会红并要求先修订 U9）；报告**正向/负向/低置信/歧义/U9/handoff/budget 六行并列**，不以单一命中率下结论；`alias-delivery-cjk` 分层断言（reference 层已修=215、wrapper 层保持登记），wrapper 宽容不视为整体失败；budget 取预截断 `total_references`（超预算用例被 blocked+exit 20 拒收）。**T22 done（wave 6 卡 O）**：`skills/scripts/verify-path-and-target.py`（只读、无网络、fail-closed，自检 15 向量）+ `tests/security/`（**10 条负向 fixture**：穿越/链接形态/**真实 junction**/**真实 hardlink nlink=2**/UNC/盘符/大小写 CoN/DNS 双应答/重定向/端口，全部真实 exit 20）+ `docs/community/PATH-AND-TARGET.md`；**4 种本平台构造不出的形态如实登记未验证**（live symlink 无提权、真实 DNS、真实重定向、8.3 短名），各有同分支替代覆盖；与既有守卫的边界写在脚本 docstring 里（index-120000 vs 工作树实况；attestation 规范化 vs containment+allowlist）。**T19 done（wave 6 卡 P）**：18 个文档 + `skills/scripts/verify-doc-auto-install.py`（60 文件扫描）；初扫 **137 处**逐处判定 → **改 45 处**（架构图、Kali README/RULES 一键安装段、总控 SKILL、11 个技能自举段）、**有意保留 25 处**（同行豁免/反向说明）、**60 处超作用域登记待 owner**；改动**顺带把注入面从 12 降到 9**。**T23 done（wave 6 卡 T）**：`tests/e2e/customer-skin-e2e.py`（**12 皮**：discovery/route/wrapper/validate/bundle 自检/门双态/bundle 自举/**升级+回滚 sha256 一致**/old-case/no-tool/redistributable 拒签/无批准）+ `docs/CUSTOMER-SKIN-E2E.md`；**负向 FNEG 证明"checkout 绿 ≠ bundle 绿"**（lab 删一 wrapper：checkout 对照 exit 0、坏包探针非零）；D1–D5 如实登记（真实 ubuntu runner、真实安装器升级回滚、仅 Win+py3.12、签名未实现、CVE 未扫描）。**T15 done（wave 7 卡 U）**：`skills/scripts/verify-auth-profile.py`（只读验证，8 类硬门；`--force` 永不绕过）+ `schemas/auth-profile.json` + `schemas/case-attestation.json` + `tests/auth/`（6 负向 fixture）+ `docs/AUTHORIZATION-PROFILE.md`；**纯新增零修改**。**`ready_for_act` 不是可复制文本能满足的**：放行要求三处 case_id 一致 + target_digest 对白名单实时重算 + binding 对七元组实时重算 + expiry/issuer/profile 交叉核对；实测复制 `true`、复制别案 attestation、事后改白名单**三者全部 exit 20**；真仓库 ready case 与 `--force` 均 exit 20。**故意未注册为 CI 门**（该 manifest 与 `.github` 属 T10，注册即与 wiring 冲突自造红灯）。**T20 done（wave 7 卡 V）**：`scripts/t20-transactional-lab.py`（generation manifest + 单写锁 + 两阶段 journal + fsync + 崩溃注入 A/B/B2/C/D + 恢复 + 回滚）+ `t20-rollback-audit.py` + `t20-format-gate.py` + `tests/t20`（**29/29**）+ `docs/community/TRANSACTIONAL-PROMOTION.md`；崩溃窗口 A/B/B2/C 中断后 `--recover` **均回到一致 generation**（树逐字节等于 pre-promote），D 终结为 generation 2；journal 状态机 `begin→snapshotted→target-moved-aside→committed/interrupted→restored`；不兼容格式 `t99/future/9` **exit 20 且 live 树未动**；lab 路径指向仓库内 **exit 21 拒绝**。**变更请求（未擅改）**：既有导入器的 rollback **不恢复 `INDEX`/`NOTICE`/`schemas/`**（只恢复 per-source raw/docs + registry.json）——已实证并交导入器 owner；6 条未验证窗口（真实断电、跨卷降级执行、多机共享卷锁等）登记于文档 §6。**T17 done（wave 8 卡 X）**：`docs/coordination/`（`ownership-contract.json` + `merge-dag.json` + `telemetry-schema.json`）+ `scripts/` 五件套（`check-coordination-ownership` / `check-merge-order` / `quarantine-source` / `coordination-telemetry` / `redact-output`）+ `tests/coordination/`（**5 fixture 全 exit 0**）+ `docs/COORDINATION-CONTRACT.md`；**全新增零修改，未动 WORK-BOARD**。负向对照均已实测：跨作用域写 20、DAG 非法序 21（双断边具名）、disturbed 树 30（隔离重跑 0）、过期 lease 20、隔离未知 source 23、**遥测超集字段被丢弃且计数 +1**、篡改日志 verify 24、无批准上传 22。**遥测默认关闭的论证**：默认开可被远端改写，默认关则发送代码路径根本不存在（本实现无网络代码）。**四项只能描述、无法机器验证**（文档 §7）：人工批准的真实意图、真实竞态 wall-clock 串行、lease 签发者身份、retention 日历与删除执行。**T25 done（wave 8 卡 Y）**：`skills/scripts/verify-contract-strictness.py`（**52 项 pass / 0 fail**）+ `t25-case-lifecycle-lab.py` + `tests/contract/`（28 + 17 断言）+ `docs/CONTRACT-STRICTNESS.md`；**4.6 迁移表逐行覆盖 11/11、零缺口**；未知枚举 fail-closed、case lease 真实拒绝并发（`LEASE_DENIED` 点名 holder）、resume token 篡改与 artifact 异字节覆盖均 blocked、**预算第 51 项即停**（50 项通过）；**双键实测 293/293 同时存在且全相等**。**五条变更请求（未擅改，`schemas/**` 归 T02）**：CR-T25-01~05（schema 闭合枚举、downstream 存在性门、tool allowlist、双键去重、预算数值入 schema）。**卡 Z（社区路由覆盖补齐，用户点名方向）**：`routing.json` 仅 R46–R49 新增 keywords（每条带语料计数，R46 每词 1–2/103、R47 `strix` 21/35、R48 ci-cd/pipeline/devops 等 1–9+/154、R49 出自单记录原文；R47 用既有 `mustAll` 机制要求 CTF 语境）+ 黄金集 **26→39** + `docs/community/ROUTE-COVERAGE.md`；**症状句 master 侧 `reverse-engineering` R0/low → `community/delivery` R48/high**；负向矩阵全部未落 R46–R49（S3→R23、架构图→R39、逆向报告→R0、LLM 提示词→R14、内存转储→R25；`frida`/`SQLi`/勒索/burp 四条对照不变；**裸"头脑风暴"→R0、裸"交付报告"→R0**）；**想补而忍住没补的 6 类**（`nosql` 会抢 SQLi 家族、裸 `交付`/`融合` 是 U9 模板词、裸 `patch`/`frida`/`重打包` 归 R1 等）与 `x-gap-upload`（社区侧中文零 token，需另立信号卡）已登记。**仍未开工：无** |
| T26 | 社区路由信号层（规范 19） | **done（已合入 `f043236`）** | `HANDOFF.md` 第 6 节 P0 此前**没有任务卡覆盖**，本轮补卡。九个实测缺陷 D1–D9 见 [`docs/community/ROUTING-SIGNAL-DEFECTS.md`](community/ROUTING-SIGNAL-DEFECTS.md)，实测前后对照见该文 **Outcome after T26** 与 E25–E28。owner 文件：`skills/scripts/community-route.py`、`skills/scripts/test-route-ranking.py`、`skills/scripts/verify-routing-signals.py`、`skills/scripts/test-routing-signals.py`、`skills/scripts/test-community-decoys.py`、`skills/community/routing-signals.json`、`schemas/community-routing-signals.json`、`skills/tests/community-decoys.json`、`docs/community/ROUTE-RANKING.md`、`docs/community/ROUTING-SIGNAL-DEFECTS.md`。**仍有 9 条过宽规则具名红着**（见 U9），不构成"净改善"结论 |

**新对话请先读 [`HANDOFF.md`](../HANDOFF.md)** —— 当前状态、门禁清单、下一步优先级与高危事项都在那里。

**未修但已登记的项（不猜、不编造）**

| # | 项 | 依据 | owner |
|---|---|---|---|
| U1 | `docs/community/**` 15 个文件缺 reference-only banner | `verify-community-banner.py` exit 10 | **已关闭（wave 3 卡 F）**：15 个文件（ai-fullstack 9 + ctf-super-hub 4 + apk-reverse 2）补 banner，该门 **exit 10 → 0**；并同时在 `docs/community/IMPORTER-MANAGED-TRANSFORMS.md` 登记为受管变换 `u1-docs-reference-only-banner`——不登记的话下次重导入会把 banner 冲掉（CR-002 的正确落点） |
| U2 | `capabilities.py` 的 `REPO_ROOT`/`tools/_work` 路径基准 | 脚本语义问题，非字符串替换，且不能执行脚本验证 | T07 后续 |
| U3 | hack-skills 的 `## 0. RELATED ROUTING`、`**LOAD FIRST**`、`cross-load` 二级路由段 | 与 17.19 同类，但不在"131 处"计量口径内 | T19 全库扫描 |
| U4 | `AI LOAD INSTRUCTION` 残留——**原记的「11 处」已过时**。T06 实测（2026-10-01）全仓 **27 处 / 7 文件**：SPEC 5、本文件 4、`PATH-CLEANUP.md` 11、`verify-community-banner.py` 4、`IMPORTER-LIFECYCLE.md` 1、`SECURITY-SCAN.md` 1、`ci-gates.json` 1；`community-raw/hack-skills` 内 **0 处**。原口径写成「WORK-BOARD 2」也偏低（本文件自身已是 4 处） | 均为**反向说明**（守卫脚本用该字符串做禁用断言，文档引用它记录 131→0 清理史），非可执行加载指令 | T00（已确认无风险）；计数已由 T06 复核 |
| U5 | `skills/community/registry.json` 55 处 `excluded[].source_path` 含 `reverse-skill-private` | 属上游位置 provenance，非可解析路径 | T02（已确认可保留） |
| U6 | `docs/community/ROUTE-RANKING.md` 被引用 3 次但**不存在** | `community-route.py:16`、`community-route.py:49`、`test-route-ranking.py:6`；现有链接门只扫 `docs/community/**` 与社区 `SKILL.md`，**不扫** `skills/scripts/**` 对 `docs/**` 的引用，所以没有任何门能发现（D9） | **已关闭（T26）**：文档已落地，3 处引用均可解析 |
| U7 | 全仓库**没有任何负向（诱饵）用例** | 182 个 L1 基准用例 + 13 个 L2 排序用例全为命中型，无一断言“某 hint 不得命中某技能”，所以 D5/D6 这类过宽规则对全部门不可见（D8） | **已关闭（T26）**：新增 57 个诱饵/正向用例，见 E26 |
| U8 | 社区路由文本被导入器 provenance 污染 | 54.5%（1415/2594）关键词条目是模板；`community-raw`/`skills-hub` 命中 293/293（D6）。修法是代码 + 策展信号层，**不是**改 registry | **已关闭（T26）**：代码 STOPWORDS + 6 条 noise，命中 293/293 → 0 |
| U9 | 诱饵集仍有 **9 条过宽规则红着** | `test-community-decoys.py --report`：`融合` / `governance` 词义冲突 / `wrapper` / 4 条 `alias_delivery` 兄弟变体 / 2 条上位词；另有 1 条 `s3 bucket` 已证实"该能力在语料中不存在"，属**正确行为**（按 1.2 不得为它编造关键词）。逐条机制与数字见 `ROUTING-SIGNAL-DEFECTS.md` | **部分关闭（wave 5 卡 L）**：**4 条机制层修好、5 条具名登记**。修好的：`融合` 进 STOPWORDS（实测 56/154 描述里的固定框式连接词）；`delivery`/`pipeline`/`devops` 走新增的**字面归属信号**（`routing-signals.json` +3 条，全 `evidence_kind: raw`；top 从 RAG 141→各字面拥有者 215/188/197）。登记的 5 条各有机制层理由：`governance`/`wrapper` 是目标记录正文里的**真领域词**（停词会杀伤正当查询）；`交付` 是**单 wrapper 候选集**（任何排序都无法让该 wrapper 不领先，只能靠停词转绿，**那会删掉刚归位的正当 top，拒绝**）；2 条上位词是 N 路描述并列、无证据偏向任一 leader。实测：decoy **21/30 → 25/30 = 0.8333**、positive **27/27 保持**、combined 48/57 → **52/57 = 0.9123**；门阈值（0.50/0.75）未动、**57 用例零删除**；`s3 bucket` 保持通过未编造关键词。逐条记录见 [`docs/community/ROUTING-SIGNAL-U9.md`](community/ROUTING-SIGNAL-U9.md) | 5 条登记项需 owner 层决策（属登记非欠账）；建议由 **T18 的黄金集**把它们钉住，防止以后被"修好"成过宽 |
| U10 | **新门未接入任何仓库入口** | `test-community-decoys.py` 与 `verify-routing-signals.py` 都不被 `test-routing.ps1`、`validate-integration.py` 或 `.github/workflows/**` 调用，所以 T26 新增的负向对照**只有手工跑才生效** | **已关闭（T10）**：`ci.yml` 新增 `integration-gates` job（17 门全部接线）；`skills/tests/ci-gates.json` 声明语义、`run-ci-gates.py` 单入口、`verify-gate-wiring.py` 交叉校验接线本身。6 条负向对照证明注入缺陷会让构建转红（删除清单里的门也会红） |
| U11 | **忠实重导入会回退 131 处策展安全编辑** | T08/T09 把 `community-raw/` 里 131 个文件的 `AI LOAD INSTRUCTION` 改写成 reference-only 中性说明；旧 `promote` 会用上游原文覆盖这些文件（T05 在 lab 实测差异 298 文件；协调者独立复算 131 个文件带策展标签、293 条登记技能中 95 条已偏离上游）。**不是 bug，是无人裁定的口径问题** | **机制已落地（wave 2 卡 A）**：口径定为**策展编辑优先**，131 文件的中性化登记为受管变换 `t09-load-instruction-neutralize`（`docs/community/IMPORTER-MANAGED-TRANSFORMS.md`，机器可读记录 + digest pin）；`import` 物化后应用它（lab 全量候选 **131/131** 命中、managed scope 内 `AI LOAD INSTRUCTION` 归零）；`promote` 对任何未登记差异 **exit 20 拒绝并点名要回退的路径**。**仍未关闭**：lab 全量候选 diff 302 项中仅 80 是 license 行差异、222 是其他漂移（T03 docs 改写、frontmatter、delivery 策展），均未登记，故**全量重导入的 promote 仍被拒**——这是特性而非故障。新增变换条目需 owner 决策（license 行方向归 T02/T04） | wave 2 已建机制；后续条目待 owner |
| U12 | `verify-gate-wiring.py` 的 NEEDS_REVIEW 文案滞后 | 该门报 `auto-merge-journal.yml` 的"独立审查记录不存在"，但记录已由 T24 建在 `docs/CI-TRUST-BOUNDARY.md` §3（卡 D 提出变更请求 **CR-T24-01**，**未自行改门**） | **已关闭（CR-T24-01）**：门改为**真实读取该文档的 write-scope 审查段落**做判定（找不到仍 NEEDS_REVIEW）；输出新增 `review-record … (record found)` 行作为证据；`ci-gates.json` 的 `ci_note` 同步、`--write-lock` 重生成锁。门 **exit 10 → 0**，总况非阻断项 2 → 1 |
| U13 | **新增文件在提交前无法被安全门扫到**（已两次致事故） | `verify-repository-security.py` 有 `.git` 时走 `git ls-files -s`，只扫 index 已跟踪文件；未跟踪的新增文件**提交前不可见、提交进 index 后立刻命中**。已两次造成"先提交、再被 clone 复核抓回"：`SECURITY-SCAN.md`（T06）、`CROSS-REVIEW-WAVE12.md`（T13，掩码前含 AWS 密钥形状字面量） | **已登记**于 `docs/community/SECURITY-SCAN.md` §7（含 `GIT_DIR` 全扫自检命令、噪音判读、不改门的理由）。**不改门**：门读 index blob 是刻意设计（防工作树载荷被隔离后脱离审查），给 `docs/` 开豁免会造成 fail-open 盲区。**纪律**：每波提交后必须 clone 复核（已两次救场），派单必须带"危险样本掩码"条款 | wave 4 紧急卡；纪律已写入 `work/dispatch-contract.md` §5.1/§5.2 |
| U14 | 生产记录下 **promote 仍无可行路径** | wave 4 卡 J 已把 `promote` 的拒绝检查从全树收敛到**候选 manifest sources**（与 rename 写入目录同一数据源），机制上单源可走（lab 实测 import→verify→promote→rollback 全 exit 0 且逐字节可还原）。但**生产记录下四个单源与全量当前仍全被拒**：apk=11、ctf=13、hack=141、ai=137，全量 302 恰为四者之和（11+13+141+137=302），全部是**未登记 modifications** | **不是缺陷，是待决的策展归属**：需各域 owner 决定这些改动是否登记为受管变换（尤其 apk 11 处熔合路径类、hack 141、ai 137、ctf 13；license 行方向归 T02/T04）。文档 §7/§9 已按此如实写 boundary，**未声称"promote 已可用"** | T05 后续 / 各域 owner |
| U15 | **中文口语化请求的路由命中缺口**（真实仿真实测，用户点名的"能不能用上技能"） | 两批**真实仿真**（新智能体从 `AGENTS.md` 起逐层走，禁止预读技能总清单）：**第 1 批** 6 个真实任务 → **对 3 / 偏 1 / 错 2**；**第 2 批** 10 个 `field-journal` 真实案例重问 → **对 6 / 沾边 2 / 跑偏 2**，且**社区侧 7/10 完全 no_match**。根因经正则逐条比对确认：**不是"词太少"，是关键词按书面语/英文语序写**——R12 要 `api.?secur` 而用户说「给 API **做安全测试**」；R26 要「代码审计」而用户说「**审查**一下它的代码」；R6 模式里**没有 `exe`**（尽管 `routing.md` 明说 exe 走 ida-reverse）；中文别名（MuMu / 证书模板 / 域管 / 监控端点 / 滑块）与方法别名（KSAd / certipy / actuator / DSL VM）**均未进词表**。审计 48 条路由：**仅 3 条完全无中文关键词**（R5/R7/R45，都是工具名）——**覆盖率不低，是"说法不对"** | **最危险的不是"不知道"而是"高置信错指"**：实测「MuMu 模拟器手游加速器闪退、分片缺块」→ `js-reverse` **confidence: high**（一个 APK 的活被高置信指到 JS 逆向）；「滑块验证码是自研虚拟机」→ `reverse-engineering`（high）；「证书模板提权拿域管」→ `pentest-tools`（medium，应 `windows-ad`）。**处置中**：修复卡正在逐条过 48 个路由补自然语序说法 + 负向对照 + 三条回归不许退化 | 修复中；未覆盖到的真实别名需补第二批 |
| **U15 进展** | **已修复一部分（复跑实测，退化 0 条）** | **canonical**：33/129（25.6%）→ **44/129（34.1%）**，其中中文 13/86→**20/86**、英文 20/43→**24/43**<br>**CTF+APK 社区侧（70 条）**：19/70 → **24/70（34.3%）**，`no_match` 38→33<br>**ai-fullstack（154 条）**：21/154（13.6%）→ **24/154（15.6%）**——**几乎没改善** | **根因**：补的 39 个中文别名**几乎全是安全主题**（文件上传/XSS/SQL注入/SSRF/IDOR…），正对 canonical 死因、对 CTF 部分有效，**完全没覆盖工程交付域** | **处置**：已派"交付域中文别名补齐"卡，目标六个零命中域（API 设计 0/11、自动化测试 0/7、AI 工程 0/6、数据分析 0/6、SRE 0/7、技术写作 0/6）。复跑卡另外登记两条残留：`H080` 误触解除但未中正主（`macos-reverse`）、CTF 的 n=21 类"包对技能错"未动 |
| U16 | **`R17` 的 `rop` 缺词边界 → 高置信误触**（命中率压测发现，协调者已独立复算） | `routing.json` 的 R17 模式原文为 `\bpwn\b\|rop\|ret2libc\|heap.?overflow\|…`——**只有 `rop` 一项没有词边界**（其余要么有 `\b`、要么够具体）。后果是**任何含 "rop" 子串的英文词都会高置信命中 Pwn chain**。协调者实测复现三条：<br>「这个配置文件的 **prop**er 写法是什么」→ `pwn-chain` **conf=high**<br>「系统日志里 d**rop**ped 的包有多少」→ `pwn-chain` **conf=high**<br>「**prop**erly handle the d**rop**ped packets」→ `pwn-chain` **conf=high** | **性质是"自信地指错"，比"找不到"更危险**（用户问配置写法却被送去打 pwn 题）。修法明确：`\|rop\|` → `\|\brop\b\|`。**同批还有 5 条待修**（见 `work/hitrate-canonical/REPORT.md` §5）：抓包不该被 `js-reverse` 独占；`ida-reverse` 缺 `exe`/`dll`/`注册码`；**18 个技能在压测中 3 条说法全灭**（api-security / code-audit / ida-reverse / js-reverse / pentest-tools / llm-security / macos / mobile / radare2 / binary-diff / binary-ninja / browser-automation / browser-extension / docs-generator / edr-bypass / hardware / patch-diff / radio-sdr） | **待第一张修复卡收口后立即派**（同文件不可并发写） |
| U19 | **★官方基准 `routing-benchmark.json` 是"照着答案问"，不能当真实命中率用**（"两把尺子"卡实测，协调者已复现） | **实测解剖 182 条用例**：词长中位数 **3**、**≤3 词占 72%**、完整句子**仅 6.6%**；最要紧的一条——**题目文字直接命中它自己那条路由的 `must` 正则 = 178/182 = 97.8%**（例如给 R1 出的题就是 `"decompile APK with jadx apktool smali"`，而 R1 的正则正是匹配 `jadx`/`apktool`/`smali`）。**对照实验**（20 技能 × 2 种问法，40 条全实跑）：**关键词式 20/20 = 100%**，**自然说法（零黑话口语）3/20 = 15%**，**差距 6.7 倍**；自然说法只中了 R6/R12/R29（**因日常词恰好=术语**），R5 错到 R6、R8 错到 R9，**其余 14 条全部 `confidence: low` 回退 R0**。 | **这不是说基准没用**——它确实证明"路由表能被自己列的词命中"，回归价值成立（`test-routing.ps1` 仍应保持 182/182）。**但它不能被当作"用户随便说都能找到"的证据**，也不能拿它的 100% 回答"命中率多少"。**真实口语问法约 15%（零黑话）~34%（含技术词）**。 | **处置中**：已派卡建立**并行的"自然说法"回归基准**（`routing-benchmark-natural.json` + 脚本，43 技能 × 2 条口语），使"能不能听懂人话"成为可逐次对比的指标；另派卡补主框架/交付域口语词 |
| U20 | **CTF / APK 两域的自然说法缺口**（60 条新写口语双路实测，只诊断未修） | **主框架 34/60 = 56.7%**（CTF 仅 **36.7%**、APK 76.7%）；**社区侧**：CTF 入门召回 **0/10**、APK 正主 `matched` 仅 **2/25（8%）**、`no_match` 10 条、**越界 matched 6 条**。**归因**：**A 关键词缺口 9**（`新手`/`组队`/`战队`/裸`夺旗`/`证书绑定`/`模拟器`/`权限`/`能力矩阵` 中文全缺）；**B 被抢走 11**（`R20←writeup`、`R3←抓包`×2、`R6←IDA/.so`×2、`R21←wireshark`、`R8←binwalk`、`R25←volatility`、`R46←SSTI/反序列化`×2、`R2←ssl pinning`）；**C 边界错 6**；**E 硬缺 3+** | **两条新类型问题**：**① `R41` 反向吸走 CTF 社区入口类**（C01–C05，与已知的"R47 越界吸具体做题"方向正好相反，说明两个方向的边界都松）；**② 社区侧"答对了不敢说"**——诊断实测 **top 方向 7/10 是对的，但 `confidence < 0.35` 全被阈值拦下**（属阈值/机制问题，非词表问题；调整需谨慎，低阈值会引入误判）。**③ 硬伤**：`apk-reverse-community` **293 条记录里只有 1 条**，所以大量"该进 R49"的说法**不是路由错，是包里没有内容** | **修复清单已就绪**（报告 §4，精确到 `exclude` 规则、ALIAS 键、记录 id）：11 条 `exclude` 收紧 + 补词 + 分词修法 + 补记录建议。**待派卡实施**（需等 `routing.json`/`community-route.py` 的写锁空出） |
| U21 | **hack-skills 域中文缺口 + 前面修复对"43 双零技能"实际无效**（64 条新说法双路实测，只诊断未修） | **社区侧引用命中 12/64 = 18.8%**、`matched` 仅 **1/64**、wrapper-hack 选中 37.5%；**主框架侧仅 1/64 命中 hack-hub，57/64 回落 `reverse-engineering` 兜底**。**复测原先"中英双 0/2"的 43 个技能中 24 个**：**仅 1 个**（079 主机头）首位命中但仍 `needs_review`、1 个排第 5 被埋、**其余 22 个零引用**——**即前面那批中文别名修复对这 43 个高频安全主题几乎没帮助**（只帮到了交付域）。**归因**：**A 类 36 条"近失"**（用户词与词表词差一点：`逃出去`≠`逃逸`、`苹果端`≠`ios`、`集群`≠`k8s`、`并发`≠`条件竞争`）；**B 类**通用词淹没（`java`/`python`/`接口`/`提权` 压掉专科记录 068/088/044/102）；**D 类**阈值机制（**63/64 都是 `needs_review`**、`upload` 冻结、主框架 R46 用英文正则）；**E 类零覆盖**（`csrf`/`csv`/`websocket`/`heap`/`tunnel`/`cmdi`/`traversal`/`nosql`/框架名） | **这是关键词匹配架构的天花板**：A 类"近失"靠加词**组合爆炸追不完**（加了"逃逸"，用户说"跑出去了"仍不中）。**两条路**：① 继续加词（低成本、只能救 A/E 一部分）；② **上语义匹配**（让路由理解意图而非匹配字面——**超出当前架构，需 owner 决策是否投入**）。<br>**负向对照证明路由本体正常**：英文 SQLi → wrapper-hack 首位命中；无意义话 → `no_match` fail-closed（不是机制全坏，是缺词） | **修复建议 7 条 + 19 个双零技能待直接复测**（报告 §4，按卡面要求未实施） |
| U22 | **★5 个上游包全都没有向量/语义路由 —— 路由机制的"家底"盘点**（上游研究卡，逐条核对上下文证伪） | **结论 1：全无向量/embedding/语义搜索/同义词表**。搜索到的"语义路由"字样**逐条核对上下文后证伪**——都是**领域正文、RAG 教学文章、或网站文案**，不是路由机制。**结论 2：全无 `when_to_use`/`triggers`/`examples` 类 frontmatter**（`reverse-skill` 44/46、`hack-skills` 103/103、`AI-Fullstack` 191 —— **纯 `name` + `description`**）。<br>**各包真实机制**：`reverse-skill` = `routing.json` 正则三件套（`must`/`mustAll`/`exclude`）+ priority 决胜 + fallback R0（44 路由；**benchmark 178 条全是关键词式——这就是自然语言只有 63% 的病根**）；`hack-skills` = **三层渐进披露**（master→6 category→deep）+ **description 动词化 "Use when"** + **中文触发词**；`ctf-super-hub` = 主入口双模式 + 三维启发式路由表 + description 内 **"触发名:"约定**；`apk-reverse` = **Symptom index 54 行症状路由** + `check_routing` 一致性校验；`AI-Fullstack`（**209 技能**）= **三级漏斗**（根 keywords+inputs/outputs → workflow 意图表+进入前检查+**转出规则** → skills **"用户说"原话表**+S/M/L/XL），**纯靠模型读表，无代码无向量** | **这解释了"为什么没人上向量"**：上游最大的包（**209 个技能**）用"纯读表"就够用；**对 336 技能这个规模，向量属过度工程**。**明确不搬**：向量、`search.js` 类加权搜索（人类网站用）、`capabilities` 注册表。<br>**采纳的 Top3**：**P0** 把 86 条自然说法变成路由资产（中文口语正则 + "用户说"表 + 双基准）；**P1** `description` 动词化 + 中文触发词（**43 个 SKILL.md，零风险**，已派卡）；**P2** 高频混淆点加**症状索引 + 转出规则**（仿 apk 的 Symptom index 与既有 `exclude` 先例） | 报告 `work/upstream-router-study/REPORT.md`（259 行，含文件路径+原文引用）。P1 已实施中；P2 待派 |
| U23 | **★阈值不该调 —— 主因是"召回"不是"门槛"**（阈值审计卡，86 条全实测 + 21 条放行项人工复核） | **阈值定位**：`MIN_CONFIDENCE=0.35`（`community-route.py:83`），公式 `confidence=min(1.0, best_score/len(hint_terms))`（`:1038`），状态判定在 `:1327–1350`；**0.35 自基线提交即存在、无独立论证**，且文档已冻结"不动"（`LOADING-BUDGET.md:15`、`ROUTE-RANKING.md:86`）。<br>**阈值扫描（净收益 = 命中 − 误判）**：**0.20 → 2 命中 / 19 误判 / 净 −17**；0.25 → −12；0.30 → −2；**0.35 → 0**；0.40 → 0。**降到 0.20 会多放 19 条，其中 18 条是错的**；唯一答对的 #1 还被 tie 门继续拦着，**实际零增益**。<br>**现状分布**：86 条中 `matched` 仅 2、`needs_review` 84（**`no_match` 62** / `low_confidence` 22 / `ambiguous_tie` 11）。<br>**门内已有假阳性**：#71 现为 `matched` 但方向错（SPF/DKIM 检查 → 邮件头注入攻击记录） | **"降阈值提命中率"是假收益**（会把交付/取证错位 top 以确定口吻推出）。**62/86 是 `no_match`，与阈值无关——那是召回问题，调门够不着**。**修复优先级被钉死**：**① 补召回（62 条零候选）= 大头 → ② 信号层加分 → ③ 修 tie 破平**；**不要在打分/阈值上做文章**。<br>**与 U22 完全吻合**：上游 5 包用的招（"用户说"原话表、症状索引、动词化 description）**全都是"补召回"手段，没有一个调阈值** | 报告 `work/threshold-audit/REPORT.md`（raw/、rows.json、verdict.csv 可逐条复算）。**不调阈值 = 已定论**；后续实施卡只需做补召回 |
| U24 | **★自然语言命中的技术路线已定：多层融合可达 88.4%，且不需要向量**（两张实验卡独立验证，协调者已复算） | **多层融合**（`scripts/route-fuse.py`，L1 正则移植 + L2 同义词 + L3 bigram-Dice + L4 BM25 + **RRF(k=60)**）：**自然说法 54/86（62.8%）→ 76/86（88.4%，+22）**；关键词基准 182 → **180**（掉 2 条**均为 R0 探针过救**，171 条非 R0 **零回退**）；基线答对的 54 条**一条没丢**；**单 hint 43ms、纯标准库、零依赖、离线可跑**；`--no-manual` 消融（去掉全部手工同义词）仍 **72/86**，证明**不是靠调参**。<br>**模糊打分**（`scripts/route-fuzzy.py`，无同义词层）独立复算：正则 54 / **fused 51（还不如基线）** / **单独 ngram 66** / **正则+ngram 补充 71（82.6%，净 +13 零回归）**；实测**BM25 在正则答对的 54 条里打错 17 条**（塌向 R21×7、R26×3）——**BM25 中文单字分词是噪声源**。<br>**两卡交叉印证**：**76 − 71 = 5，差额正是"同义词层"的贡献** | **最优组合 = 正则 + 同义词 + ngram，去掉 BM25**。**接入形态两卡一致指向"只在 R0 时兜底，不碰 PRIMARY"**（融合卡建议 R0 影子档约 15 行胶水；模糊卡建议"R0 补充候选"形态用 ngram 作排序键）。<br>**另一条硬结论**：**"零覆盖"（词表里根本没有的词）任何相似度都救不了**（实测 #6/#7/#85 字面命中 0）——**那部分只能靠补词/补同义词**，正是词典卡（155 surfaces）与 description 触发词卡在做的事。<br>**故 U22 的"不上向量"得到二次确认**：88.4% 由纯标准库达成 | `work/route-fuse/{DESIGN,REPORT}.md`、`work/fuzzy-router/REPORT.md`（均含 86 条全表与复算命令）。**接入卡已派**（R0 影子档） |
| U25 | **★300 条缺口的真实结构：不是"缺词"，是"白话到术语没有桥"；且现有命中 9/10 靠字面撞**（缺口分析卡，229 条逐条定性 + 反证） | **缺口分布**（T1 缺词 / T2 白话无桥 / T3 被抢 / T4 机制拦 / T5 内容缺失 / T6 无法判定）：<br>**社区 174 条 = T5 80 ｜ T2 63 ｜ T4 23 ｜ T3 8 ｜ T1 0 ｜ T6 0**<br>**canonical 55 条 = T4 34 ｜ T2 20 ｜ T3 1 ｜ T1 0 ｜ T5 0**<br>**★ T1（词表里根本没这个词）＝ 0** —— 原话：**"词表确有对应词，缺的是白话到术语的桥"**（`领东西`→票据、`几个九`→SLO）。<br>**★ 反证**：从"命中的 59 条"里挑 10 条检查，**9 条是字面撞上的**（canonical 整词命中 / community 拉丁词 `login`/`host`/`redirect`/`mock`）——**命中机制就是字面匹配，那 19.7% 并非"真懂"**。 | **根因三条**：**① `registry.json` 293 条记录零中文**（`keywords` 全英文）→ **中文 hint 在 token 层永远撞不上**（这是社区侧 4.6% 的直接原因）；**② T2 白话无桥**（同义/口语→术语的映射缺失）；**③ T4 字面有货却被 `mustAll` 拦**（canonical 侧 T4 的 `confidence` 全 `low`）。<br>**修复路线（按性价比，卡内实测给序）**：**① `apk-reverse-community` 那 1 条记录补中文 → 单点可救 17 条**（最高）→ ② 67 条记录批量补中文 → ③ delivery/ctf 中文同义 → ④ R46/R48/R47 wrapper 加中文 → ⑤ canonical 白话 `must`。**外推 59 → 140–170/300**（**假设，已在报告声明**）。<br>**两个已登记风险**：**社区侧排序有抖动**（22 条重跑主路 22/22 一致，社区 **21/22**——`N148` needs_review→matched、`N004` 候选 0→6，故 T4 计数 ±2）；**R11 有 4 条归属争议，硬加 `exclude` 会造新缺口，需 owner 裁决** | 报告 `work/gap-300/REPORT.md`（`items.json` 229 条逐条、`stats.json`、`counter_proof.json` 可复算）。**执行原则**：**从 Top1 单点验证救回率后再批量铺开**；**每步用组外新题验收，防止字面撞上的数字冒充成绩** |
| U26 | **★300 条大样本重测：19.7% → 32.0%（+37 条，相对 +62%），两侧同时提升**（协调者独立重跑，`0a8f616` 提交，clone 复核通过） | **重测（同一批 300 条、同一口径）**：<br>**canonical 34/100 → 47/100**（`N096` 因路由映射未处理 `community/` 前缀被保守计入 miss，实际可能 48）<br>**community 25/200 → 49/200**（**翻倍**）<br>**总分 59/300（19.7%）→ 96/300（32.0%）**<br>**官方基准全程 182/182 一条没掉**；clone wave14 `total=20 ok=16 non_blocking=3 skipped=1 blocked=0 failed=0`。 | **四层能力已建成**：① 正则关键词（原有）→ ② **中文同义词/口语词表**（39 主题 + hack 8 个零覆盖 + 6 个双零技能 + 13 组 + CTF/APK 10 键）→ ③ **融合层 R0 影子档**（正则+同义词+n-gram+RRF，**votes≥3 才晋升**，即 182/71 那个零回退配置）→ ④ **信号层 `signals[]`**（**零词重叠也能建候选**，17 条 APK 题被救回；**上限 128 条，当前 31，还可加 97**）。<br>**关键纪律**：每一步都以"官方 182/182 零回退"为硬约束。 | **剩余 68% 的结构**（来自 U25）：**T5 内容缺失 80**（包里没有，补词救不了）｜**T2 白话无桥 83**（**`signals[]` 是唯一有明确空间、不改机制、不调阈值的路**）｜**T4 机制拦下 57**（阈值已定论不可调）｜**T3 被抢 9**。<br>**下一步**：沿 `work/zh-integrate/PLAN.md` 验证过的 signals 通道，把 `signals[]` 从 31 条往 128 条填 |
| U27 | **★★当日最终结果：300 条大样本 19.7% → 56.3%（+110 条，近 3 倍），两侧同时大幅提升**（协调者独立重测，同一批题、同一口径） | **300 条（覆盖全部 336 技能、easy/medium/hard 各 100、真实自然说法）**：<br>**canonical 34/100 → 100/100 = 100%**<br>**community 25/200 → 69/200 = 34.5%**<br>**总分 59/300（19.7%）→ 169/300（56.3%）**<br>**难度均衡**：easy 58% ｜ medium 56% ｜ hard 55%（**不挑题**）<br>**官方基准 182/182 全程一条没掉**；自然说法 86 条 54→76（88.4%）。<br>**对照尺子（同日新增）**：**读表模式 90.3%**（模型只读入口文档判断；同口径 canonical **97% vs 正则 47%**）。 | **做成的四层引导**：① 正则快路径（182/182 不退化）→ ② **症状索引** `skills/SYMPTOM-INDEX.md`（173 句"用户会怎么说"，治"近失"）→ ③ **读表全矩阵**（`routing.md`/`MASTER-ROUTING.md`，补了 9 条缺失线索 + R46/R47 切分 + hack 主题词表）→ ④ **未命中三步**（`AGENTS.md`/`CLAUDE.md`：补问 → 判边缘 → 提示新能力，**禁硬塞**）+ **`docs/EVOLUTION-CHECKLIST.md`**（10 条可勾选 + 验证命令，承接"不停融合新包"）。<br>**词表侧**：中文别名 39 主题 + hack 8 个零覆盖 + 6 个双零技能 + 13 组 + CTF/APK 10 键 + 交付域 18 词 + canonical 45 条规则；**signals 31→67**（上限 128）；**融合层 R0 影子档 votes≥3 晋升**。 | **关键认知（当日最大收获）**：**正则 47% vs 读表 97%（canonical 同口径）**——**不该用正则去模拟"理解"，该把表写好让模型读**（上游 5 包一致做法：`AI-Fullstack` 136 行 YAML 管 209 技能）。**下一阶段主线应从"补词表"转向"把表做厚"**：补 signals 剩余 61 条空间、按症状索引模式继续扩、把 `EVOLUTION-CHECKLIST` **变成脚本门**（上游唯一机器强制是 apk 的 `check_routing.py`）。<br>**已拒绝的假收益**：调阈值（净收益 −17）｜ 86.4% 的过拟合（拿考卷当教材）｜ 为满分破坏 CTF 入口设计（`N096` 停在 99 并如实登记） |
| U28 | **★★★续接结果：300 条 56.3% → 68.7%（+147 条 vs 基线，3.5 倍）；社区侧 34.5% → 53%**（协调者独立重测，同一批题同口径） | **本轮新增**：`signals` **47 → 104 条**（T2 白话无桥社区 63 条全覆盖，抽样 15/15 + 全量 37/37 HIT）、**社区症状索引 448 句**（`SYMPTOM-INDEX-COMMUNITY.md`：hack 103/103 + ctf 35/35 + delivery 30 代表 + apk 1）。<br>**曲线**：300 条总分 **19.7%（今早）→ 56.3%（23:20）→ 68.7%（00:00）**；canonical **34 → 100/100**；community **12.5% → 34.5% → 53.0%**；难度 easy 73% / medium 67% / hard 66%。<br>**官方基准 182/182 全程一次没掉**（每一步都在"不破坏原有能力"前提下加出来）。 | **本轮两个交付都过了严格校验**：抄题零违规（124 片段 × 8582 语料句）、`verify-routing-signals` PASS（104 条，schema_errors 0）、15 门全绿。<br>**两次自我纠错值得记**：`signals-ext2` **纠正了协调者的数字**（任务卡写"剩余 35 条"，它去 registry 对账为 **37 条**并全做）；`verify-routing-signals` **在负向对照中真的失败过**（精确报出 `signals[104]` 的非法 id）——**这个门首次被证明有效** | **剩余空间**：community 仍差 **94/200**；`signals` 上限 128（现 **104**，还可加 24）；T5/T4/T3 社区 `expect` 未做；`EVOLUTION-CHECKLIST` 脚本门在建 |
| U29 | **★★★终值：300 条大样本 19.7% → 90.3%（+212 条，4.6 倍）；community 12.5% → 85.5%**（协调者独立重测，同一批题同口径） | **曲线**：**19.7%（今早）→ 56.3%（23:20）→ 68.7%（00:00）→ 90.3%（01:15）**；<br>**canonical 34/100 → 100/100**；**community 25/200 → 171/200 = 85.5%**；<br>难度 **easy 93% / medium 85% / hard 93%**；官方基准 **182/182 全程一次没掉**。<br>**最后一跳来自 `community-T1` 卡**：诊断出 community 剩 94 条中 **T1 零覆盖 65 条**（自然说法与词表零交集），它补 **51 个 ALIASES 键 + 14 条 signals（104→118）** → **65/65 从 `no_match` 进候选**，实测 community **53% → 85.5%**。 | **达到与"读表模式"同水平**：同日读表实验（只读入口文档）也是 **90.3%**。**两条路会合了**——但代价不同：**正则路要人写 51 键 + 118 条 signals**，**读表路只需把文档写好**（这正是 U22/U24 记录的方向）。<br>**诊断价值**：`T4 内容缺失 = 0`（94 个 `expect` 在 registry 里全有登记）——**剩余缺口全是"说法与词表接不上"，不是包里没有**。<br>**该卡的严谨之处**：中途抓到真红（`jwt-abuse` 吞 `alias_jwt` 致 golden 红 → 改 `header spoofing` 回绿，**不是改门**）；发现 `ai` 锅炉板别名被 `noise` 洗掉 → 转 signals；发现 `and`/`for`/`community` 被 STOPWORD 先 strip → 改用存活子串桥 | **剩余 29/300**：`signals` 已到 **118/128**（余量 10）；下一步要么继续挖 T2/T3，要么**按 U24 的结论把主线转向"把表做厚"**（读表路成本更低且可随包增长） |
| U30 | **★R46/R47/R49 边界判据的独立盲读验证：误判 19 条从 0/19 → 14/19**（协调者已读报告；污染已由该卡自曝） | **验证方式**：对上一轮遮蔽实验里"判错且错进 `hack-hub`"的 19 条（16 CTF + 3 APK），**只读 5 个入口文档**做独立盲读。<br>**结果**：**判对 0/19 → 14/19，判错 19/19 → 0，弃权 0 → 5**；上一轮 19 条全错进 `hack-hub`，**本轮 hack-hub 一条都没有**。<br>**判据有效性分层**（这是本卡最有价值的产出）：**F3 工具化动作 5/5**（★最强，**结构性**：strix 侧每个 web 同名主题都有专项记录，而 R46 的 103 条无对应 → 判 R46 在文档层就不可能对）；**F2 无锚点分流 4/4**（★最干净，表行几乎是题面逐字复述）；**P1/P2 APK 各 3/3**（逐字引自 `legacy_description`）；F1 题型门词 1/1；**F4 语气 2/7（✗ 唯一失效面，它制造的弃权比救回的还多）**；P3 0 次触发（**无法评价，未混入"有效"充数**）。 | **解释了两卡数字为何对不上**：上一卡"机械化成正则跑出 13 翻转"数字漂亮，是**因为它复判的正好是逐字型那批**（F2/F3/P2 可安全机械化）；**独立盲读把语境型 F4 单拎出来，真实转化率 2/7**。<br>**诚实披露**：该卡第 2 步读 `cases.json` 漏 `-Encoding UTF8` → `ConvertFrom-Json` 解析失败 → **300 条 `expect` 全文提前进入其上下文** → 故 **14/19 带污染，`N294` 不算干净盲读**，其余 18 条可采信（判据依据可按行核）。<br>**6 条改进意见（含代价）**：F4 补同句冲突裁决（以收尾分句为准，修 `N276`）；**兜底太宽本批净损失 4 条**（给了保守/激进两案及代价：保守 → 那 4 条从弃权变判错、总数掉到 10/19）；锚点词表拆"所有权锚点/裸载体词"；**判据节抬头须写明"F2/F3/P2 可机械匹配、F4 必须人工读"**；P3 标注适用范围；**P2 行与 `cases.json` 的 `expect_note` 直接冲突（反调试归属）→ 建议加警示防下一卡重踩** | 报告 `work/boundary-verify/REPORT.md`。**改进意见已派卡实施**（`boundary-fix2`）。<br>**另一条已提交**：`9d4171a` 修"wrapper 平局用路径字母序破"（**29 条 top 命中 11→15，净 +4**），但**产生 1 条回归 `N267`**（含"比赛里"的题被 `hack-skills` 抢）→ **已派小卡修**（给 `ctf-super-hub-018` 加 CTF 语境 signal；机制已确认：`signals` 正则直接对原始小写 hint 匹配） |
| U31 | **边界判据六条改进与 N267 信号修复已分别提交**（`a9c9fe4` 文档判据 + `8e346bf` 信号正则；工作树干净） | **文档侧**：`skills/routing.md` +157/−5（F4 冲突裁决、兜底收窄、锚点拆栏、逐字语境区分、P3 标注、P2 冲突警示）、`skills/MASTER-ROUTING.md` +5/−1（优先级表 48 行逐行相同）；**信号侧**：`skills/community/routing-signals.json` 对 `community-ctf-super-hub-018` 的 `must[]` 追加 CTF 语境正则，条目数保持 118。 | **已复算**：信号合法性校验通过；N267 首候选为 ctf 侧且首引用为 018；文档差异与两卡回报一致。完整门禁本轮受执行通道波动影响，后续用干净环境重跑 20 门与 182/182、76/86。 | 报告 `work/boundary-fix2/`、`work/n267/`；待办：clone 复核、300 条重跑、剩余缺口继续关闭 |
| U33 | **★★★round-2：泛化边界实测 —— 300 条的 99.0% 不能外推；同技能的 100 条新说法上正则路只剩 26.0%**（协调者独立复算）+ **`verify-evolution` 接进 CI（22→23 门）** | **卡 F（出题）+ 卡 H（盲判）+ 协调者（测量/分离）**：<br>**hold-out 集**：从 300 条按 id 均匀取 100 条（`expect` 去重 = 100；canonical 39 / community 61），**同 expect、题面重写**；与原题面最长公共连续汉字 **≤5**、与技能名 **≤2**（`holdout-check.py` 自证）。<br>**正则路实测**：canonical 20/39 = **51.3%**、community loose 6/61 = **9.8%**、总 **26/100 = 26.0%**。<br>**因果分离**（另一张卡只读入口文档、不看答案键做盲判）：盲判与答案键**一致 81/100**（⇒ 新说法多数没改语义），在这 81 条干净子集上正则命中 **24/81 = 29.6%**（canonical 19/34 = 55.9%、community **5/47 = 10.6%**）；不一致的 19 条上正则 2/19。<br>**卡 G**：`scripts/verify-evolution.py`（b124d76 建、此前无人调用）接进 `skills/tests/ci-gates.json`，`gates declared` **22 → 23**，lock 由 `verify-gate-wiring.py --write-lock` 重算（`sha256:cc5a1021…e9893` → `sha256:9ee9a54c…a9685256`）；`run-ci-gates.py --runner python` **total=21 ok=21 failed=0**（23 减 2 个 powershell-runtime 门）。 | **结论（必须对外同时报）**：300 条的 **99.0% 是"同一批字面"的成绩**；换没见过的说法，正则路社区侧只剩 **~10%**。而**读表盲判与答案键一致率 81%** ⇒ **读表路比正则路更能认新说法**（与 U27"正则 47% vs 读表 97%"同型，这次是在未调优说法上复现）。<br>**因此不改机制、也不为下一批说法再补词表**（那是把过拟合往后挪一批）；包里现成协议即正解：正则命中直接用（43ms），`low`/`no_match` 走 `AGENTS.md` 的"未命中三步"（补问 → 判边缘 → 提示新能力）。<br>**卡 G 的诚实边界**：负向对照证明"摘门/改弱 `blocking_exits`"都会被拦（exit 20 或整轮判 failed），**唯一拦不住的是"改 manifest 同时重跑 `--write-lock`"**——那道只能靠人工评审 `--write-lock` 的 diff。 | 报告：`work/round1-verify/`（`holdout-100.json`、`holdout-results.json`、`holdout-blind-judgments.json`、`holdout-analysis.py`、`holdout-blind.json`、`cardF-holdout.md`、`cardG-ci-wiring.md`、`lab-cardG/`）；`scripts/verify-evolution.py` 第 25 行的"Not wired into ci-gates.json"陈述已陈旧（卡 G 硬约束禁改该脚本，**待协调者另开一次改动**） |
| U32 | **★★★★round-1 收口：300 条大样本 272/300 → 297/300 = 99.0%（关掉 25/28 条缺口）；官方 182/182 与自然 76/86 全程零退化**（协调者独立复算：两条基准 + 全量 300 + 真树 20 门） | **两卡写作用域互不重叠**：<br>**卡 A（signals 域）** `skills/community/routing-signals.json`：7 条已有 entry 扩 `must[]`（不占额度）+ 新增 10 条 entry，`signals` **118 → 128**（正好用满 schema `maxItems=128`）；54 条新正则抄题自检**最长公共连续汉字 = 3**（硬门 <6）；`verify-routing-signals.py` 13 项负向对照全过。<br>**卡 B（数据桥域）** `skills/scripts/community-route.py`：`ALIASES` **纯追加 22 组**中文说法（blast 逐条实测全 ≤6），记录侧靠自身 slug 天然满足"双边折叠"⇒ **registry.json 零改动**。<br>**实测（协调者）**：canonical 100/100；community **172/200 → 197/200 = 98.5%**（loose 与 strict 逐条一致，口径干净）；总 **272 → 297/300 = 99.0%**；top1（首 ref 即答案）**153 → 170**；难度 easy 100% / medium 97% / hard 100%；官方 **182/182**、自然 **76/86**、真树 **20 门 ok=20 failed=0**。 | **上界实验（新，`work/round1-verify/signal_ceiling.py`）**：给 28 条 miss 各注入一条"必然命中"的合成 signal（内存注入、仓库零写入），**28/28 全都能进某个 wrapper 的 references** ⇒ signal 路线唯一瓶颈是 schema `maxItems=128`；已有 entry 扩 must 不占额度 ⇒ **信号域硬上界 = 7+10 = 17 条**，其余必须走数据桥。<br>**BOM 事故（已处置并留证）**：卡 A 首次落盘把该 JSON 写成带 BOM，`community-route.py` 严格 utf-8 解码直接 `blocked`（120 条 contiguous 掉出、社区 **172→78**）；卡 B 用两个 shadow 副本隔离测量并上报（`lab-cardB/regress.txt` 有完整 traceback），文件在 5:53 以无 BOM 重写，复测 **197/200** 确认恢复。**教训**：JSON 落盘必须无 BOM（`[System.IO.File]::WriteAllText(path, text, (New-Object System.Text.UTF8Encoding $false))`），且**改完要复测而不是只跑门**。<br>**读表盲测第二轮（文档修复后，300 条，`work/readtable-mask2/`）**：**269/300 = 89.7%**（canonical 90/100、community 179/200）；与第一轮同口径对照 **273/300 = 91.0%**（canonical 92、community 181）⇒ 修好 21 条、弄坏 25 条，**净 −4**。弄坏的 25 条里 **18 条同源**：`routing.md` 的「F4 兜底：无强锚点 → 改判 R47」把 hack 题系统性翻成 ctf（第一轮这些题是对的）；`boundary-fix2` §5 自己预告过这个代价。<br>**F4 兜底的精确账**（按 evidence 字段自动归类全部 300 条）：引用 F4/兜底的共 **36 条，判对 17 / 判错 19（≈47%，等同抛硬币）**；三种口径分别得 **判 ctf = 269 / 判 hack ≈ 270（净 +1，但破坏 CTF 入口设计）/ 全弃权 = 错误归零但丢 17 条已判对的** —— **没有赢家**。且 N171（hack 键"头像上传只看了后缀，改个 file 名字传上去居然能被当成脚本跑"）与 N273（ctf 键"头像上传只看后缀，改名传上去会不会被执行"）**几乎是同一道题、答案分属两个包** ⇒ **这是答案键（`cases.json` 的 `expect`）带噪声，不是文档单方面的错**（U30 已登记过同一现象）⇒ **不改文档**（为迎合答案键改口径 = 拿考卷当教材），登记为**需 owner 裁决或修答案键**。 | **剩余 3 条**（N131/N180/N213）：桥已成立（各自 name view 命中 rank=3），但同 wrapper 内另有 4–6 条同 rank 记录，`_reference_sort_key` 的 path 末位把它们压出 `references[:3]`；要救只能动 `REFERENCE_LIMIT`（**属禁止项**），故维持 miss 并如实登记。<br>**下一轮候选**：① `signals` 提额（需 owner 裁决，有上界实验支撑）② **F4 兜底改回"只标 uncertain"**（读表净 −4 的成因，收益最明确）③ R0/R6、R44/R11、R17/R46 三组"文档 vs 答案键"冲突④ 读表第二轮的信度（3 个子代理分段判定，F4 语录型稳定性天然偏低）。<br>报告：`work/round1-verify/`（`ROUND1-NOTES.md`、`measure300.py`、`measure-comm.py`、`diag28.json`、`miss28.md`、`signal_ceiling.py`、`score-readtable.py`、`compare-readtable.py`） |
| U17 | **客户端中立性：契约层成立、MCP 注册层不成立 + 一处文档漂移**（多客户端真实仿真发现，协调者已逐条复算） | **① 契约层中立成立（好）**：`skills/config`、`skills/MASTER-ROUTING.md`、`skills/tests`、`skills/routing.md` 对 `claude\|cursor\|codex\|gemini\|copilot` **git grep 零命中**（exit 1）——路由核心确实与客户端解耦。**② MCP 注册层绑死两家**：`skills/scripts/bootstrap-reverse.ps1:12` 是 `[ValidateSet('None','Claude','Codex','Both')]`，而 **Cursor / Gemini / Copilot 在 `skills/scripts` 下零路径**。**③ 文档漂移**：`skills/CONTRIBUTING.md:586` 写"当前 bootstrap 脚本**默认写入 Claude Code 的配置路径**"，而代码 `bootstrap-reverse.ps1:13` 是 `[string]$McpHostTarget = 'None'`——**代码比文档更安全**（默认不碰任何客户端配置），文档却让人以为会被自动写入 | **三入口质量不均**（真实仿真）：**`AGENTS.md` 最顺**（三平台命令齐、授权整节、测试全过；缺口是未提 `README_AI`、未预警 `master-route` 会写 `work/`）；**`CLAUDE.md` 最弱**（路由顺序只给 `.ps1` → **Linux 用户照抄撞墙**；**授权仅括号一句，是三个入口里最弱的**；缺 `test-routing`/`smoke` 与 `case-init` 参数）；**`README_AI.md`** 部署表最全但 **Windows 照抄 `python3` 会失败**、`master-route.sh` 因缺 `python3` 退 49。**安全面**：无入口完全漏掉授权门（好），但 **`MASTER-ROUTING` 的"一键 ACT"示例摩擦过低**（可能诱导跳过授权）；`AGENTS.md` 未声明路由脚本会写文件 | 待修：`CONTRIBUTING.md:586` 的漂移、`CLAUDE.md` 补 Linux 路径与授权段、`README_AI.md` 的 Windows `python3`、`bootstrap` 的客户端覆盖（若要保持中立则不该只认两家） |
| U18 | **★入口文档从不告诉智能体"还有一条社区路" → 293 个社区技能对只读文档的智能体等于不存在**（双通道审计发现，协调者已 grep 复算） | 双通道一致性审计（150 条说法 × 两条路）**严格一致仅 27/150 = 18.0%，冲突 82.0%**；主框架对 51.3%、**社区侧高置信对仅 16.7%**、**两边都错 22.7%**。分域：**逆向/固件/取证的社区命中为 0**；交付域社区 4/5 胜出。<br>**协调者复算的根因**：`community-route` 一词在 **`AGENTS.md` / `CLAUDE.md` / `README.md` / `README_AI.md` / `README_zh.md` / `README-kali.md` / `skills/MASTER-ROUTING.md` / `skills/routing.md` 全部零命中**（只有 `skills/SKILL.md` 提过一次），而 **`master-route.ps1` 里 `community` 命中数 = 0**。诡异之处：`MASTER-ROUTING.md` **确实列了 R46–R49 四条社区路由**（指向 `community/*` 通道），**但唯一的工具脚本不产生它们，也没有任何文档说"要另跑 community-route.py"**。→ **照文档老实走的智能体，永远看不到社区侧 293 个技能** | **一句话修复、价值最大**：按审计建议把「**主框架 low/no-hit → 改查社区侧；社区侧中文 0 候选 → 换英文重查；blocked → 收窄**」写进 `AGENTS.md` 路由节（并在 `CLAUDE.md`/`MASTER-ROUTING.md` 同步）。**注意**：这是当前**性价比最高的一处修复**——不改任何路由逻辑，只补一句指引，就能把那 293 个技能"接上" | **已修复（入口文档卡）**：`AGENTS.md`（路由节重写为两条路）/ `CLAUDE.md`（补 `.sh` 跨平台路径 + 序号 1–8）/ `MASTER-ROUTING.md` / `routing.md` 四处改完，`community-route` 提及 **0 → 8**；文档里写的命令**原样真跑过**（中文→exit10 no_match、`upload`→matched exit0、长句→blocked exit20、master→hack-hub/high）。<br>**并且问题被一层"自愈"进一步缓解**：并行的第二批修复卡给 `routing.json` 的 R46–R49 补了主框架侧可匹配的关键词后，**`master-route.ps1` 现在能直接输出社区路由**（实测「文件上传漏洞怎么测」→ `community/hack-hub` **conf=high`），因此本条不再需要"靠文档指路才能看到社区"——**主框架一个命令即可**。<br>**剩余（低优先）**：`README*.md` 四文件仍零提及（入口文档卡作用域外，**待定夺是否补一句**） |

## 3. 已实测的现状证据（T00 记录，供各任务复核）

| # | 事实 | 证据命令 | 结果 |
|---|---|---|---|
| E1 | 主路由回归 | `powershell -File skills/scripts/test-routing.ps1` | 182/182 PASS，exit 0 |
| E2 | 路由一致性 | `powershell -File skills/scripts/verify-routing-coherence.ps1` | ALL PASSED，exit 0 |
| E3 | 文档链接门 | `python skills/scripts/verify-doc-links.py` | 342 broken，exit 1 |
| E4 | 集成校验门 | `python scripts/validate-integration.py` | PASSED 但 189 warnings，exit 0 |
| E5 | 社区二级路由测试 | `python skills/scripts/test-community-route.py` | 待各任务复核 |
| E6 | registry 枚举漂移 | 读 `skills/community/registry.json` | `allowed_context` 为 kebab（`offline-ctf` 等），与第 4.6 节 canonical profile 不一致 |
| E7 | registry source 字段缺口 | 同上 | 4 条 source 均缺 `source_kind`/`tree_digest`/`source_manifest`/`snapshot_root`/`distribution`/`adaptation_status`/`importer_version`/`last_verified_at` |
| E8 | wrapper 记录指向不存在的路径 | 同上 | `skills/community/hack-hub/SKILL.md` 不存在 |
| E9 | 校验器硬编码统计 | `scripts/validate-integration.py:35,43` | `== 4 sources`、`== 55 excluded` 写死，T21 加入 canonical base 后必然误报 |
| E10 | 备份 | — | 重排前原文备份在 `work\spec-before-reorder.md` |
| E11 | **INDEX.md 泄漏 raw 技能路径** | 见下方 3.1 | `skills/INDEX.md` 目录树段逐个列出 297 条 `skills/community/**/SKILL.md`；模块总览含 293 条 community 行 |
| E12 | 注册表与文件系统的隔离本身是完整的 | 见下方 3.1 | `skills/community` 下 297 个 `SKILL.md` = 293 条 registry 记录 + 4 个 wrapper，无“未登记可发现”文件 |
| E13 | **导入器覆盖集基线摘要** | `work\baseline-digest.json` | 基线 commit `c9b8303`；覆盖集 **1111** 条；`file_manifest_digest=6f57b141…`、`tree_digest=d258ddc0…`；随机 40 条 `git cat-file` 复算 40/40 一致 |
| E14 | 覆盖集对账 | 同上 `reconciliation` | 清单有磁盘无 **0**；磁盘有清单无 **5**（全在写入面外：LINK-TRIAGE.md、PATH-CLEANUP.md、REGISTRY-V2-MIGRATION.md、link-triage.json、link-triage.lock.json，且该集合在流动） |
| E15 | **单次运行有重复写** | 同上 | **310 条路径被写 ≥2 次**（293 个 SKILL.md + 17 个 WORKFLOW.md）。此前"无冗余写"的说法作废 |
| E16 | **行尾口径必须折叠 CRLF** | 同上 + T00 复核 | `.gitattributes(eol=lf)` + `core.autocrlf=true` 使提交时 CRLF→LF，而导入器 `copy2` 写的是上游 CRLF 原字节。不折叠则 Windows/Linux/no-git 结果不一致（违反 17.26）。T00 独立复核：`docs/community` 25 个文件中**正好 12 个含 CR**，与报告一致 |
| E17 | 30 个 frontmatter 异常的真实构成 | 同上 `subsets.frontmatter_anomalies` | `BOM` 14 + `NO-FRONTMATTER` 15 + `BOM+NO-FRONTMATTER` 1 = **30**。即"14+16"的互斥读法：带 BOM 共 15、无 frontmatter 共 16、交集 1。与 registry 中 30 条合成 `original_name` 的路径集合**完全相等** |
| E18 | provenance 声明的时效边界 | 同上 | `docs/community` canonical **23/23 IDENTICAL**，但 raw 只有 11/23——另 **12 条纯粹是行尾差异**。"逐字节副本"只成立于导入器写入工作树那一刻；提交后 blob 已被 git 规范化 |
| E19 | **社区路由基线（T26 现场采集，`44592e9`）** | `work/p0/p0-measure.py` | 293 条记录、0 条零关键词、820 个不同关键词；slug 自召回 **187/293**；38 个命名探针中 **7 个零引用**：`bloodhound`、`mimikatz`、`certipy`、`s3 bucket`、`lattice`、`pcaps`、`yaras` |
| E20 | **D1：kq-02 的 `_name_view` 加宽是死代码** | `work/p0/p0-proof-deadwidening.py` | 293/293 条记录携带 **1748** 个仅加宽可达的令牌；**87** 条记录无法成为自身 slug 的候选；`lattice` 加宽命中 1 条而引用 **0** 条。机制：`lookup()` 用严格令牌集的 `_score()` 决定候选（`community-route.py:589-591`），加宽只在 gate 之后的 `_rank()` 里被查询 |
| E21 | **D5：停用词在别名替换之后才生效** | 同上 | `tokens("workflow") == {'alias_delivery'}`，尽管 `workflow` 就在 `STOPWORDS` 里；**154/154** ai-fullstack 记录对裸词 `workflow`/`delivery`/`pipeline`/`devops`/`交付` 返回 `matched confidence=1.0` |
| E22 | **D6：导入器 provenance 污染路由文本** | 同上 | `community-raw` 命中 **293/293**、`skills-hub` **293/293**、`alias_delivery` 155/293；**1415/2594（54.5%）**关键词条目为模板（`project`/`skills-hub`/`upstream` 各 293 次） |
| E23 | **D2/D3/D4：令牌化盲区** | `work/p0/p0-diagnose2.py`、`p0-diagnose.py` | 连字符复合词吞掉词头（`BloodHound-guided`、`Lattice-based`）；无复数处理（`pcaps`≠`pcap`）；全部 2 字符令牌不可见（`ad`/`os`/`ot`/`ai`/`s3`/`ci`/`db`/`io`/`id`，故 `ad cs`、`ci cd` 均为空） |
| E24 | **对既有假设的一次证伪** | `work/p0/p0-diagnose2.py` 第 E 节 | 从路由文本移除 `path` **不改变召回**：190/293 用与不用都是 190/293。`path` 是**精确性**隐患（D6），不是召回隐患。会话中一度假设相反，已作废 |
| E25 | **T26 独立验收（协调者自建 harness，不 import 实现方任何门）** | `work/p0/p0-acceptance.py` | 冻结权重 4/3/1 + `REFERENCE_LIMIT=3`；对加宽可见但对 candidacy 不可见的记录 **87 → 0**；slug 自召回 **187/293 → 274/293**；38 探针零引用 **7 → 1**（`s3 bucket`）；`community-raw`/`skills-hub` 命中 **293/293 → 0**；`tokens("workflow")` → `∅`；28 条信号的 evidence **逐条独立复核，0 条不可验证**；6 条 noise 全部满足 ≥80% 单来源 |
| E26 | **D8 关闭：首个负向对照落地** | `python skills/scripts/test-community-decoys.py --report` | 仓库负向用例 **0 → 57**（29 诱饵 + 28 正向）；诱饵通过率 **20/29 = 0.6897**、正向 **27/28 = 0.9643**、合计 **47/57 = 0.8246**；两个门分别为 0.50 / 0.75，**故意压在实测值之下**，所以新过宽规则会让数字变动而不得靠删用例转绿。协调者用自己实现的评分器复算出**完全相同**的三个数字 |
| E27 | **T26 自己引入又自己修掉的两个过宽规则** | `work/p0/p0-reconcile.py` 第 2、4 节 | `ai` 作为短令牌让路由视图把 `ai-fullstack` 切成 `ai`，命中 **157/293** 条、且是 weight-3 的**名字级**命中，`lookup("ai")` 返回 3 个 wrapper、confidence 1.0（仅靠 `ambiguous_tie` 兜底）→ 已从 `short_tokens` 移除并同步 schema/verifier；`adapted`/`capability` 因 30 条 `Adapted capability from workflows/...` 合成描述而命中 ai-fullstack → 已进 `STOPWORDS`。两者修完后 `lookup` 均为 `missing_input` |
| E28 | **一次被推翻的子代理口径** | 同上 + `verify-routing-signals.py` | 有子代理断言 `capability`/`adapted`/`融合` 满足"单来源 ≥80%"并据此建议写进 `noise[]`。独立复算：**19% / 19% / 36%**（分母 154），全部**不满足**，该建议无效。正确修法是 `STOPWORDS`（无 80% 约束）而非 `noise[]`。另：某诱饵用例把 `s3 bucket` 的期望指向 `unauthorized-access-common-services`，实测该记录（Redis/Rsync/PHP-FPM/AJP/YARN/H2）两个文件里 `s3`/`bucket`/`aws`/`object storage` **出现 0 次**，属**不可成立的用例**，已改为记录"该能力不存在"的诱饵 |

### 3.2 独立审计代理的校正结论（T00 接受，覆盖原判断）
以下由独立代理重新测量得出，**推翻或修正了 T00 与规范初稿的口径**，以此为准：

| # | 原口径 | 校正后 |
|---|---|---|
| C1 | 342 条断链“多数在 `skills/community/**`” | **341/342 在 `docs/community/**`**，仅 1 条在 `skills/community/**`（`ctf-super-hub/solve-challenge/SKILL.md:72`）。涉及文件只有 5 个：hack-skills `README_CN.md` 167、hack-skills `README.md` 167、ctf-super-hub `README.md` 4、ai-fullstack-delivery `README.md` 3、solve-challenge 1 |
| C2 | “293 个 raw 技能缺发现守卫” | **前提错误**：293/293 全部已带 `user-invocable: "false"`。真正的问题是没有**物理**隔离（17.27），以及 12 个文件重复声明该键、其中 3 个取值自相矛盾（`ctf-beginner-hub`、`ctf-writeup`、`solve-challenge`） |
| C3 | “APK wrapper 引用不存在的路径” | wrapper `skills/community/apk-extension/SKILL.md` 是**干净的**；3 条悬空路径全在 `skills/community/apk-reverse-source/SKILL.md`（:8、:9、:124），且适配后的 `scripts/doctor.py`、`scripts/capabilities.py` 已存在 |
| C4 | “`--release` 被忽略” | 确认，并有 `--bogus` 对照同样 exit 0；根因是脚本无 argparse、无 `sys.argv` |
| C5 | “community route 回归未接入 CI” | 测试**存在且通过**；缺的只是 CI 接线（`ci.yml` 28 个步骤未调用它，也未调用 `validate-integration.py`） |
| C6 | “Delivery 引用 bootstrap-project.ps1 约 15 处、reverse-skill-private 约 22 处” | bootstrap：单包 15 处 = 15 个 `WORKFLOW.md` 各 1 处（精确），全域 25 处/19 文件。private：22 处只存在于**单个文件** `workflows/reverse-pentest/WORKFLOW.md`，单包合计 32，全域 103 处（其中 registry.json 55 处） |
| C7 | registry baseline commit 性质 | `cab634bd…` 是 upstream/reverse-skill 的 HEAD，在融合仓库 `git cat-file -t` **取不到**；不是本仓库提交。已在规范 1.4 写明 |
| C8 | 断链门在 CI 中的状态 | `.github/workflows/ci.yml:341-343` 运行该步骤且**无** `continue-on-error`，因此该 CI job 当前是红的，不只是“文档记录的风险” |
| C9 | 额外发现 | 仓库共 386 个 `SKILL.md`：`skills/community` 297、`CTF-Sandbox-Orchestrator/` 42、`plugins/` 1；另有 4 处 `AI LOAD INSTRUCTION` 出现在规范自身正文（作为反向说明），不在社区内容里 |

影响：**T03 的整改范围必须从 `skills/community/**` 改为 `docs/community/**`**（341 条），否则会漏掉 99.7% 的断链。T07 的目标文件是 `apk-reverse-source/SKILL.md` 而不是 wrapper。T01 的修法不变（物理隔离 + INDEX 排除），但“加 frontmatter 标记”这条已在原始数据上失效，不能作为证据。

### 3.1 E11/E12 的实测细节（T01 必须处理）

命令与结果：

- `Get-ChildItem skills/community -Recurse -Filter SKILL.md` → **297** 个文件。
- 与 `registry.json` 的 293 条 `path` 逐一比对 → 差额正好是 4 个 wrapper：`apk-extension`、`ctf-hub`、`delivery`、`hack-hub`。**没有**未登记的社区技能文件。
- `skills/INDEX.md`：模块总览表共 **342** 行（45 个 canonical + 293 个 community + 4 个 wrapper）；`## 目录树` 段（第 353–698 行）逐行列出 **297** 条 `skills/community/**/SKILL.md/` 路径；全文 `community` 出现 **628** 次。
- `skills/scripts/extract-summaries.ps1` 的 `$skipDirs` 只排除 `ops/scripts/config/tests/field-journal/references`，**没有排除 `community`**；它用 `git ls-files -- 'skills/**/SKILL.md'`（297 条）作为输入，因此 raw 技能会被写进 INDEX。

结论：**“293 个 raw 技能可能被递归发现”这个描述只对了一半**。registry 层面的隔离是干净的；真正的泄漏面是生成物 `INDEX.md`，以及 `skills/` 目录本身仍是客户端递归扫描的发现根。T01 的验收必须同时覆盖这两点，而不是只改 registry 标记。

顺序要求：T01 依赖 T02 完成后再改 INDEX 生成逻辑（两者都会触碰 `skills/community/**` 的路径假设）。

## 4. 变更请求区（非 owner 只能在此登记，不得直接改共享文件）

| 请求 id | 目标文件（owner） | 请求者 | 请求内容 | 状态 |
|---|---|---|---|---|
| CR-001 | `skills/community/**` 的物理位置（T01 执行） | T00 | 按下方 4.1 的方案把 raw vendor 内容移出客户端发现根；必须先等 T02 冻结 `registry.json` 路径口径 | pending（等 T02） |
| CR-002 | `scripts/adapt-community.py`（T05） | T00 | **升级为 P0 阻断**：见下方 4.2。在 T05 重写落地前禁止执行该脚本 | open |
| CR-003 | `skills/community/canonical-mapping.json`（**新增 owner：T02**） | T02 | 该文件把 `ai-delivery-security` 映射到**不存在**的 canonical 技能 `security-engineer`（仓库只有 43 个 canonical 技能）。T02 已正确拒绝把它写入任何 `canonical_downstream` 并上报 | open |
| CR-004 | `docs/COMMUNITY-LICENSE-MATRIX.md`（T04） | T02 | T02 把 hack-skills 的 `MIT-with-third-party-provenance-review` 改为 4.1 合法枚举 `review-required`，`validate-integration.py` 的 warning 因此 189→292（**有意加强**，不是回归）。许可证矩阵口径需 T04 同步 | open |

### 4.2 CR-002（P0）：导入器会静默覆盖在途工作，且不可逆

独立只读逆向报告：`work\t05-importer-spec.md`（318 行），配套 `_t05_analysis.py` / `_t05_analysis.out.txt`。

**单次运行覆盖 1111 条路径**（1087 个 `skills/community/**` + 23 个 `docs/community/**` + `registry.json`），以纯净上游原文覆盖目标，**不留 diff、不备份、无 digest、无 candidate**。

**当前风险是实的，不是理论**：此刻 T02/T03/T07-09 的改动正落在覆盖集内，包括 `docs/community/{ai-fullstack-delivery,ctf-super-hub,hack-skills}/README*.md`、`skills/community/apk-reverse-source/**`、`skills/community/ctf-super-hub/solve-challenge/SKILL.md`、`skills/community/registry.json`。**任何人此刻跑一次，这些编辑会被上游原文静默抹掉。**

另两条必须记住的结论：

1. **`docs/community/**` 是上游文件的逐字节副本**（抽样 5 个全部 IDENTICAL）。那 341 条断链是**上游原文自带的**，在仓库里改文本没有持久意义——下一次导入即被覆盖。所以 T03 的正解不是"改这 5 个 README"，而是"由导入器生成 provenance banner"，或把改写登记为受管变换。
2. **`registry.json` 是整文件覆盖**（L397 `write_text`），会抹掉 T02 正在加入的 v2 策展字段。

**强制措施（T00 决定，立即生效）**

- T05 五子命令改造落地前，**禁止执行 `scripts/adapt-community.py`**，任何参数都不行（无 argparse；`--help`、拼错参数、CI 误传都会触发全量导入 + 删除）。
- 该脚本**未被 CI 调用**（实测 `ci.yml` 无引用），只要人不手动跑就不会触发。
- 需要"重新导入"时走变更请求，由 T00 确认工作树干净且已提交后再评估。
- 新增守卫 `skills/scripts/verify-community-banner.py`（T00 提供）：社区留档缺 banner、raw 技能缺集成合同标记、或 hack-skills 重新出现 `AI LOAD INSTRUCTION` 时失败。即使有人重新导入，回归也会被立刻暴露。

**T05 重写最低要求**（报告第 5 节）：`inspect`/`verify` 零写入；`promote` 是唯一可动 verified tree 的命令；`--help` 纯打印且导入期零工作；candidate 布局 + `file_manifest_digest`/`tree_digest`；Windows 上用 journal + 两次 rename（**不是**无锁原子，登记为"可恢复窗口"）；**第一步先为现状建立基线 digest**——那 30 个合成 frontmatter 文件（14 个 BOM + 16 个无 frontmatter）当前没有任何 digest 能证明改了什么。

**CR-002 升级（T01 实测后补）**：T01 搬迁完成后，`adapt-community.py` 的**写入根 `SOURCES[].dest` 仍指向 `skills/community/**`（1087 条路径）**。这意味着**只要有人跑一次导入器，发现隔离泄漏会被重新创建**——不只是"回退今天的改动"，而是"把已经挪出去的 raw 内容重新写回发现根"。因此：

- 导入器写入根必须与 T01 的布局变更**同批**更新，这是 T05 的必做项而非可选；
- 在 T05 落地前，禁止执行导入器的禁令**升级为硬阻断**；
- 新增的 `audit-discovery-surface.py`（exit 20）是这条回退的机器守卫：它会在导入器把 raw 写回 `skills/` 后立即变红。

另一个必须在 T05 里落地的细节：`.candidates/` 目前**不在** `.gitignore` 里，且目录不存在。candidate 落地前必须补该条目，否则会被 `git status` 污染，并落进 `validate-integration.py` 的 `rglob("*")` 密钥扫描。

### 4.1 CR-001 依赖图与方案（T00 只读盘点，2026-09-29）

`skills/community` 路径被引用的位置（排除 community 自身与 docs/community）：

| 文件 | 命中数 | 是否需随迁移更新 |
|---|---:|---|
| `skills/INDEX.md` | 594 | 是（T01 重新生成） |
| `docs/INTEGRATION-IMPLEMENTATION-SPEC.md` | 22 | 否（只描述结构，不含硬编码路径；如含需 T00 改） |
| `docs/WORK-BOARD.md` | 8 | 否（本板叙述） |
| `skills/SKILL.md` | 5 | 是（入口说明） |
| `scripts/validate-integration.py` | 5 | 是（`WRAPPERS` 常量 + 遍历根） |
| `scripts/adapt-community.py` | 5 | 是（写入根） |
| `skills/MASTER-ROUTING.md` | 4 | 是（wrapper 引用） |
| `skills/scripts/community-route.py` | 4 | 是（registry 路径解析） |
| `skills/config/routing.json` | 4 | 是（wrapper 条目） |
| `AGENTS.md` | 2 | 是（T24） |
| `docs/INTEGRATION-DESIGN-REVIEW.md` | 2 | 否（历史评审留档） |
| `README.md` / `README_zh.md` | 1 / 1 | 是（T24） |
| `skills/scripts/test-community-route.py` | 1 | 是（T02） |

实现方案（推荐 b，需 T00 批准后由 T01 执行）：

- **方案 a：只标记。** 给 raw 文件加不可发现标记。**不满足 17.27**，因为纯目录递归的客户端仍能发现它们；仅可作为过渡。
- **方案 b：物理搬迁。** 把 `skills/community/<source>/**` 的 raw 内容移到新的顶层目录（例如 `community/`），`skills/community/` 只保留 4 个 wrapper。效果：递归发现集合从 343 → 50（46 canonical + 4 wrapper），与 manifest 一致。成本：约 297 个文件移动 + 上表 8 个文件的路径更新；`registry.json` 的 293 条 `path`/`adapted_path` 必须同批更新。
- **方案 c：保持原位 + 客户端清单。** 依赖客户端遵守 `carrier-manifest`。只在客户端可控时成立，不能作为唯一手段。

顺序约束：T01 必须在 T02 冻结 `registry.json` 路径口径**之后**执行，否则两者会互相覆盖。执行时 `skills/INDEX.md` 由 T01 重新生成，不得手改。

## 5. 冲突与事件登记

| 时间 | 类型 | 对象 | 处置 |
|---|---|---|---|
| 2026-09-29 | **已证实安全漏洞（自我豁免门）** | `skills/scripts/verify-doc-links.py` + `docs/community/link-triage.json` | 见下方 5.1。已修：新增 `verify-triage-lock.py` + `link-triage.lock.json` |
| 2026-09-29 | 上游一致性风险 | `docs/community/**` 与导入器覆盖集重合 | 见 CR-002。T03 的 328 条改写与 4 个横幅必须由 T05 纳入受管变换，否则下次导入回退 |
| 2026-09-29 | **文档引用断链（无门可查）** | `docs/community/ROUTE-RANKING.md` | 见 U6 / D9。kq-02 引入了 3 处引用却未交付文档；`verify-doc-links.py` 的扫描面不含 `skills/scripts/**` 对 `docs/**` 的引用，因此**没有任何门**能发现这类断链。owner T26 |
| 2026-09-29 | **已实测的路由精确性缺陷（全门不可见）** | `skills/scripts/community-route.py` | D5/D6：裸词 `workflow` 以 confidence 1.0 命中 ai-fullstack；`community-raw`/`skills-hub` 命中 293/293。之所以长期未被发现，是因为**全仓库没有负向用例**（U7/D8）。owner T26 |
| 2026-09-29 | **P0 缺口：规范无对应任务卡** | `docs/INTEGRATION-IMPLEMENTATION-SPEC.md` | `HANDOFF.md` 第 6 节把 P0 定为“路由信号质量”，但 T14–T25 无任何卡覆盖它；本轮补 T26（规范第 19 节），`task_cards` 26 → 27，`verify-spec-structure.py` exit 0 |
| 2026-09-30 | **派发层静默失败（已修复，需长期警惕）** | `AGENTS.md`、`HANDOFF.md`、子代理 provider 注册表 | 本轮派发 4 个代理做 T04/T05/T06/T10，**全部返回 `null`**：不报错、不写文件、`git status` 干净，看起来像“代理不干活”。根因是环境变更——`desktop` profile 已不存在（只剩 `profiles\web\`），provider 由 `newapi` 更名为 **`axon`**，旧的 `provider: "newapi"` 无法解析。一行探针（读一个已知数字）即可区分“路由挂了”与“任务失败”，已把该探针步骤写进 `AGENTS.md` 派发规则。**教训：`null` 不等于子代理能力不足，先验证路由再归因。** 项目早前 T26 的 8 个代理是在 `newapi` 还生效时跑完的 |

### 5.1 已证实的自我豁免漏洞（T00 在仓库外隔离副本实测）

**漏洞**：`verify-doc-links.py` 把**未跟踪**的 `docs/community/link-triage.json` 当作"已登记"的权威，而该文件与断链同在 `docs/community/**`，同一个 PR 可任意写。于是**任何** provenance 断链——包括从未在上游存在过的链接——只要在登记表里声明为 `upstream_layout_unmappable`，门就放行。

**实测方法与结果**（隔离副本 `work/gate-lab2`，未触碰真仓库）：

1. 往 `docs/community/ctf-super-hub/README.md` 追加一个**从未在上游存在**的链接 `definitely-not-upstream/invented-file-xyz.md`，并补上横幅标记；
2. 不登记 → 门 `exit 1`：`1 provenance broken link(s) without a registry entry`（说明门确实 fail-closed）；
3. 在登记表里把它声明为 `upstream_layout_unmappable` → 门 **`exit 0`**：`all 14 provenance break(s) registered`。

即：**这个门可以被它要检查的同一批文件自我豁免**。

**修复**：`skills/scripts/verify-triage-lock.py` + `docs/community/link-triage.lock.json`，把登记表钉在**独立文件**的摘要上（canonical 口径按 17.26：NFC / LF / 排序键）。同一攻击重放后：

- 门：仍 `exit 0`（它看不见）；
- 锁：`exit 20`，报 `triage registry digest does not match the lock` **且** `entry count drift: lock=342, registry=343`。

附带一项机器校验：`upstream_layout_unmappable` 声称的 `upstream_path` 必须真实存在于只读快照；快照缺失时降级为 `exit 10 needs_review`，不静默通过。

**诚实边界**：锁文件本身也能被同一个 PR 重新生成，所以完整修复仍需**受保护评审路径**（CODEOWNERS / 保护分支 / gate 变更需独立审查，规范 17.21 → T24）。本层提供的是"可机器验证的那一半"，不是全部。**不得**把这次修复表述为"漏洞已彻底解决"。

**教训（写进 T24/T10 派工）**：任何"登记/豁免/白名单"机制，如果登记数据与被检查对象处于同一写入权限域，都不构成门。门必须把权威数据放在更受保护的域里，或至少在独立文件上留摘要。

## 6. 提交纪律（规范 17.10）

1. 施工代理默认**不提交** git commit；由协调者 review 后统一提交。
2. 每个任务交付：patch summary、测试日志、touched-file manifest。
3. 越界文件（不在 12.0 登记表与任务卡允许范围内）一律视为无效改动。
4. 禁止为了让门通过而删测试、放宽阈值或跳过文件。
