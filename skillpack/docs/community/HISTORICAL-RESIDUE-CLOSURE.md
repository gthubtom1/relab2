# HISTORICAL-RESIDUE-CLOSURE（wave 7 卡 W：T19 残留 + U2 + U3）

三件均为"别人查出来但没人认领"的遗留，本卡逐件给结论：改了什么 / 有意不改什么 /
拿不出证据因而停手的是哪个。实测命令均以仓库根为 cwd，
`$env:PYTHONIOENCODING='utf-8'`，Python 为 `D:\EXE\python\python.exe`。

## 1. T19 超作用域残留（wave 6 卡 P 登记 60 处，本卡有权限的子集）

判定标准（与卡 P 一致）：正文指示 agent 自主触发安装/下载/补齐的，才是可执行诱导；
描述工具能力元数据、失败回退手动、历史记录、教学引文的，保留并说明理由。
"不要自动安装"类安全声明一处未动；`verify-doc-auto-install.py` 一字未动。

### 1.1 改了（3 处，均统一为"只生成计划，显式批准后才执行"）

1. `docs/community/ai-fullstack-delivery/README.md:113-125` 与同文件 `196-213`
   改前：`5. 如果缺工具 → 调用 scripts/bootstrap-project.ps1 -Workflow <name> 自动安装`
   （标题还是"按以下步骤自动配置"）；另有"手动使用"节三条直调该脚本的 powershell 命令
   与"项目级自举脚本"描述无任何分发声明。
   改后：步骤 5 只生成缺失工具清单与安装计划，等用户显式批准；并如实注明
   `scripts/bootstrap-project.ps1` 未随本仓库分发（全仓 glob 确认该文件不存在，
   原诱导指向一个不存在的脚本）。标题改为"按以下步骤准备（只生成计划，显式批准后才执行）"；
   "手动使用"节标注为上游原文留档 + 本仓库不自动安装，清单行补"未随本仓库分发"。
   后续建议（非本卡）：该文件属 `docs/community/**` 上游镜像，下次导入会被覆盖，
   是否登记为受管变换由 owner 按 U14 口径裁定。
2. `skills/pentest-tools/references/automation-loop-pattern.md:145`
   改前：`8. 如果缺工具 → bootstrap 自动补齐`
   改后：`8. 如果缺工具 → 只生成缺失工具清单计划，显式批准后才调用 bootstrap 补齐`
3. `skills/pentest-tools/payloads/README.md:29-32`
   改前：`## 自动补充` + `AI 会自动从 SecLists 中提取常用 payload 子集放入` +
   `如果 SecLists 未安装，bootstrap 会自动下载`（agent 自主写文件 + 自主联网，
   无批准字样）。
   改后：标题为 `补充方式（只生成计划，显式批准后才执行）`，先出清单与来源计划，
   显式批准后才提取/下载。

### 1.2 有意不改（逐处理由）

- `skills/CONTRIBUTING.md:66/:77`（模板表头"可自动安装"）：能力元数据列头，
  取值系 `bootstrap-manifest.json` 的 `canAutoInstall` 字段，不是动作指令。
- `skills/CONTRIBUTING.md:82`（HTML 注释"哪个脚本在缺工具时会自动调用 bootstrap"）：
  模板作者注记，渲染不可见，非运行时指令。
- `skills/CONTRIBUTING.md:345`（贡献者 checklist"入口脚本已接入 bootstrap（缺工具时自动补齐）"）：
  面向贡献者的接线要求，所指 bootstrap 须经 AGENTS.md 激活+批准门才能运行，
  不是免批准自执行许可。
- `skills/CONTRIBUTING.md:555`（"如果自动安装/启动失败，按以下步骤手动配置"）：
  失败回退手动的安全声明，按禁令必须保留。
- `skills/CONTRIBUTING.md:616-618`（sqlmap-mcp 示例：`canAutoInstall: false` +
  `需要用户手动启动容器`）：示例 dorm（无运行时 SKILL.md 引用该段），且明写手动步骤。
- `skills/llm-security/references/agent-obedience-engineering.md:32`
 （"立即执行 bootstrap" CORRECT 示例）：教学引文，演示"指令置顶"技巧的正反例；
  改掉示例即破坏文档本意；该文件是 references 分析笔记，非运行时入口；卡 P 已做基线登记。
- `skills/apk-reverse/scripts/` 六个实现（`decode/frida-run/rebuild-sign-install` × ps1/sh
  的 `ensure_tool`/`attempting auto-bootstrap` 块）：实现体只在显式调用后执行，
  上游有激活+批准门；失败路径均为手动指引；删自动回退等于改双平台实现行为，
  超出"文档诱导"范围，需 owner 另行裁定（且 SKILL.md:381 的计划+批准声明保留不动，
  两者张力如实登记）。
- `skills/scripts/refresh-tool-index.ps1:137` / `refresh-tool-index.sh:357`
  表头"可自动安装"列：生成表的数据列头，直映 manifest 字段值（✓/✗），
  描述能力元数据，不下达安装指令。
- `burp-mcp-full/README.md:181`（"推荐使用 build.bat/build.sh（零依赖，自动下载 jar）"）：
  用户显式调用构建步骤内部的下载行为描述，非 agent 自主安装指令。
- `skills/field-journal/**` 的"一键"（如"一键切 Burp/一键绕过/一键起服务"）：
  历史 case 记录与单命令技巧速记，非安装诱导；历史留档不动。
  另：卡面写的 `field-journal/references` 目录经查不存在（glob 无命中），
  实指上述 journal 正文，按历史记录口径保留。

## 2. U2 — `capabilities.py` 的 `REPO_ROOT` / `tools/_work` 路径基准

结论：**基准本身是对的，备注过时；无可改之处，停手。** 这是有效结论，不是"无法证实"——
实测证据由只读探针给出（`D:\Project\skills-hub\work\u2-probe-readonly.py`，
仓库外 lab，只读文件文本、重放三行路径推导、做存在性检查；**未导入、未执行目标脚本**，
遵守"不能执行脚本验证"，目标脚本的 `device()` 路径会调 adb，不可跑）。

唯一存在的是 `community-raw/apk-reverse-source/scripts/capabilities.py`
（`skills/scripts/capabilities.py` 经全仓 glob 确认**不存在**，写作用域里的该路径无处落笔；
`community-raw/**` 禁止改）。

实测（探针输出原文要点）：

- `HERE=.../community-raw/apk-reverse-source/scripts`，
  `SKILL_DIR=.../community-raw/apk-reverse-source`，
  `REPO_ROOT=D:\Project\skills-hub\integrated-skill-hub`，与真实仓库根**相等**。
- 该文件 328-331 行注释声称"在融合仓库里 REPO_ROOT 解析到 `<repo>/skills`"——
  **该断言为假**（探针：`comment-claim '<repo>/skills' true: False`）。
  它描述的是 T01 物理隔离之前的旧布局，备注过时。
- `tools/_work` 相关：`REPO_ROOT/tools/_work/rust/target/release/rasc.exe` **不存在**，
  故 rasc 特例永不命中，回退到 PATH / `RASC` 环境变量（均未设置，行为是保守的"找不到"，
  不是乐观误报）；`dirname(REPO_ROOT)/tools`（`D:\Project\skills-hub\tools`）不存在，
  该候选分支静默无害；`SKILL_DIR/tools` 不存在，无害。
- `GATE_FILES`：`check_repo.py` 等立于 REPO_ROOT 之下**不存在**；
  `community/apk-reverse-source/scripts/scan_leaks.py`（注释口径）不存在，
  实际存在的是 `community-raw/apk-reverse-source/scripts/scan_leaks.py`。
  影响：`publish_gate` 能力的 file 原子恒为缺失，该能力恒报 blocked——
  方向是保守（fail-closed），不构成"把不行说成行"的乐观误报。
  该漂移位于禁改区，如实登记给 T07 后续裁定，本卡不停留。

## 3. U3 — hack-skills 二级路由段（选 b：明确登记"非 0 级标题可接受"，不改门）

当前真实状态实测（字面扫描 `community-raw/hack-skills` 工作树全文件，非抄文档）：

- `## 0. RELATED ROUTING`：70 处（69 文件单含 + `request-smuggling/SKILL.md` 1 处）。
- `## 6. RELATED ROUTING`：2 处（`insecure-source-code-management/SKILL.md:193`、
  `websocket-security/SKILL.md:179`），两文件**零守卫命中**（`## 0.`/`**LOAD FIRST**`/`cross-load` 均为 0）。
- `## 12. RELATED ROUTING`：1 处（`request-smuggling/SKILL.md:345`，该文件另有 `## 0.` 1 处，
  故守卫计其 1 次）。
- `**LOAD FIRST**`：1 文件（`prototype-pollution-advanced/SKILL.md`，与 `## 0.` 同文件，
  贡献第 71 次）；`cross-load`：0 处。
- 守卫口径复算（`verify-repository-security.py` 三正则）：files=70 / occurrences=71 /
  digest=`274b3e9a51fc…`（全 `ROUTER_BASELINE_*` 一致，真树 exit 0，见验收）。

选 (b) 的理由：

1. 守卫 digest 钉的是"路径+命中计数"，任何**新增** `## 0.`/`LOAD FIRST`/`cross-load`
   标记都会改变计数并 fail-closed；不可见面仅限"两处 `## 6.` 文件内部改写/删除
   不改变计数"与"request-smuggling 的 `## 12.` 段内部改写"，属窄缝而非敞口。
2. 三段内容经读确认为同类交叉引用（RELATED ROUTING），与 70 处同质，
   非可执行加载指令（vendored 树内 `AI LOAD INSTRUCTION` 为 0，横幅门 exit 0）。
3. 选 (a) 意味着改 `ROUTER_BASELINE_DIGEST/FILES/OCCURRENCES`（70→72 / 71→74 /
   digest 重钉）或给横幅门加新检查项——两者都是**改门**，超出本卡写作用域，
   且 digest 重钉须 T06/T00 协调，本卡不代劳。保持门强度不变，登记已知边界，
   与 `SECURITY-SCAN.md` §2（SCAN_EXCLUDES/正则口径）并列。
4. 纪律不变：提交前用 `GIT_DIR` 全扫自检补新增文件盲区（U13），本卡交付前已执行。

## 4. 验收数字（改动后复测，改动前基线见子代理回报正文）

- `skills/tests/run-ci-gates.py --runner python`：total=20 ok=20（改后，基线同为 20/20）。
- `skills/scripts/verify-doc-auto-install.py`：改前 exit 0（scanned 60 / violations 0）；
  改后 exit 0（scanned 60 / violations 0）：三处改动文件均不在该门扫描面内，门强度未动。
- `skills/scripts/verify-community-banner.py`：改前 exit 0（PASS）；改后 exit 0（PASS）。
- `verify-repository-security.py`（index 模式，经 CI 门）：exit 0；
  `GIT_DIR` 全扫模式：仅 2 条 `scripts/__pycache__/*.pyc`（`git check-ignore -v` 实证为
  `.gitignore:6:**/__pycache__/` 忽略的本地产物，属 §7 已登记噪音），本卡新增/改动文件零命中。
- `git status --porcelain`：本卡 `M` 3 文件 + `??` 本文件；其余 `??` 为并发卡 U/V 的文件，
  非本卡产出（见回报）。
