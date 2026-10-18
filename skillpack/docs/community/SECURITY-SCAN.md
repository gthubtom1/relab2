# SECURITY-SCAN（T06 安全与 vendor 信任扫描）

守卫：`skills/scripts/verify-repository-security.py`（540 行，标准库 only）。
只报告，不洗白：vendored 样例一律不动，发现即记录。

## 1. 现状（基线，2026-10-01 实测，真树 exit 0）

```text
NOTE verify-repository-security: provenance notice_file is empty for source ai-fullstack-delivery (license_declared='NONE', license_status='missing-license')
OK verify-repository-security: tracked=1753 executable_sources=157 binary_like=1 agent_entries=4 symlinks=0 vendored_router_files=70 vendored_router_occurrences=71 vendored_router_digest=274b3e9a51fc injection_shapes=12 secrets=0 provenance_advisories=1
```

- 运行：`(Resolve-ReverseToolSpec -Name 'pyre').Command skills/scripts/verify-repository-security.py`（cwd=仓库根，`PYTHONIOENCODING=utf-8`），exit 0。
- `registry.json` 只读：前轮已证运行期间逐字节未变；本轮未写该文件。
- 覆盖门类：Git index（`ls-files -s`，无 `.git` 时回退 working-tree）→
  agent 入口合同（4 根文件 + 同意标记 + execute-on-read 中英文形）/
  可执行源危险模式（7 类，2 处预期命中列白）/
  二进制（后缀 + 伪装魔数 ELF/PE/Mach-O/zip/gzip，gradle-wrapper.jar 单哈希列白）/
  伪装二进制 / symlink（`120000` 越界判定）/ 可执行源内 `http://` 明文端点 /
  5 类高置信秘密 / vendored 二级路由 digest 钉死 / provenance（registry 拥有关系 + https + 40 位 sha + notice 跟踪性）/
  GitHub Action 全 SHA 钉死 / payload 语料哈希钉死。

## 2. 缺口清单（已知边界，非漏洞，改动需重审）

1. 秘密仅 5 种高置信形状；通用 `password = ...` 散文故意不匹配（src-hunter 参考语料 11 处均为文档）。
2. 明文端点仅统计可执行后缀内的 `http://<dotted-host>`；模板/命名空间/无点 host 不计。
3. 二进制列白仅 1 个哈希；新增二进制默认 `unreviewed` 失败（fail-closed，符合预期）。
4. 路由 digest 扫描限定 `community-raw/` + `skills/community/` 下 `.md`/`.txt`；`docs/` 迁移记录逐字引用 vendor 标记，属文档而非入口， by design 排除。
5. 任何被跟踪 symlink 先报 `tracked symlink requires review`（严格），再做越界判定。
6. OK 行内 `symlinks=0` 为字面量（ cosmetic），真实计数由错误行强制执行。

## 3. U3 核实（二级路由段，我方口径 vs 守卫口径）

- 守卫口径（`ROUTER_SEGMENT_PATTERNS`，`^## 0. RELATED ROUTING` + `**LOAD FIRST**` + `cross-load`，限 roots/后缀）：
  70 文件 / 71 出现 / digest `274b3e9a51fc…`。任何增删改写 fail-closed（C4 已证）。
- 我方独立复算（字面子串，全 `community-raw/hack-skills` 工作树，不限标题级别）：
  `RELATED ROUTING` 72 文件 / `LOAD FIRST` 1 文件（`prototype-pollution-advanced/SKILL.md:50`）/
  `cross-load` 0 出现。
- 口径差解释：72 vs 70 的 2 文件差是 `insecure-source-code-management`（`## 6.`）与
  `websocket-security`（`## 6.`）的非 `0.` 级标题，不在守卫正则内；其余 70 文件一致，
  `prototype-pollution-advanced` 贡献 2 次（标题 + LOAD FIRST），71 次吻合。无矛盾。
- 结论：二级路由面被 digest 钉死，未改写；与 WORK-BOARD U3（归 T19）一致。

## 4. U4 核实（`AI LOAD INSTRUCTION` 残留，我方口径 vs WORK-BOARD）

- 我方口径（字面子串计数，全仓库除 `.git`，2026-10-01）：
  共 26 处 / 6 文件——`docs/INTEGRATION-IMPLEMENTATION-SPEC.md` 5、
  `docs/WORK-BOARD.md` 4、`docs/community/PATH-CLEANUP.md` 11、
  `skills/scripts/verify-community-banner.py` 4、
  `docs/community/IMPORTER-LIFECYCLE.md` 1、`skills/tests/ci-gates.json` 1；
  **`community-raw/hack-skills` 内 0 处**。
- WORK-BOARD U4 行称“残留 11 处（SPEC 5 / WORK-BOARD 2 / 守卫 4）”——已过时：
  (a) WORK-BOARD 自身现为 4 处非 2 处；(b) 未计 `docs/community/*` 的 12 处与 `ci-gates.json` 1 处。
- 性质结论与 WORK-BOARD 一致：残留全部是反向说明（守卫脚本用该字符串做禁用断言；
  文档引用它记录“131→0”清理史），vendored 内容里无可执行加载指令。口径差仅在计数范围，不在定性。

## 5. 负向对照（每类一次扫描，真实非零退出）

基线（`work/t06-lab/plain` 副本）：exit 0，同第 1 节 OK 行。 artefact 植入后即删，cleanup 复绿 exit 0。

| 编号 | 植入 | exit | 决定性报错原文 |
|---|---|---|---|
| C1 | `community-raw/hack-skills/AGENTS.md`（raw entrypoint + must-run-after-read） | 1 | `raw agent entrypoint under client discovery root (unescaped instruction surface): community-raw/hack-skills/AGENTS.md`（另带 `unregistered vendored agent entry file`、`prompt-injection shape must-run-after-read x1`） |
| C2 | `community-raw/hack-skills/sqli-sql-injection/creds.md`（`AKIA…EXAMPLE`，AKIA 后接 16 位大写字母数字，示例值已掩码断开） | 1 | `credential-shaped secret aws-access-key-id x1: community-raw/hack-skills/sqli-sql-injection/creds.md` |
| C3 | `skills/ops/vendor-injection.md`（可执行指令行） | 1 | `prompt-injection shape must-run-after-read x1 (baseline 0): skills/ops/vendor-injection.md` |
| C4 | `community-raw/hack-skills/new-raw-skill/SKILL.md`（`## 0. RELATED ROUTING` + LOAD FIRST） | 1 | `vendored second-level router surface changed; re-review required: files=71 (baseline 70) occurrences=73 (baseline 71) digest=f118454e92a2… (baseline 274b3e9a51fc…)` |
| C5 | scratch  git-index 仓库 `120000 skills/ops/escape.md → ../../../../etc/passwd` | 1 | `symlink escapes repository root: skills/ops/escape.md -> ../../../../etc/passwd`（另 8 行为 scratch 空仓缺件连带错，见 `work/t06-lab/c5-symlink-result.txt`） |
| C6 | `skills/ops/fetch.ps1`（明文 `http://vendor-cdn.example.net/dropper.zip`） | 1 | `cleartext http endpoint in executable source: skills/ops/fetch.ps1:1: vendor-cdn.example.net` |
| C7 | `skills/ops/stub.md`（`MZ…` PE 头挂文本后缀） | 1 | `disguised binary content (pe-dos) behind text suffix: skills/ops/stub.md` |
| C8 | `community-raw/unknown-vendor/SKILL.md`（无 registry 拥有者） | 1 | `vendored raw root has no registry owner: community-raw/unknown-vendor/` |

真树复绿：`integrated-skill-hub` 根再跑一次，exit 0，OK 行同第 1 节。

注：`negative_controls.py` 的 `symlink_control()` 误调 plain 树脚本路径（ROOT≠scratch，空扫 exit 0），
C5 以修正调用路径的重跑为准，判定逻辑未动；其余 C1–C4/C6–C8 由该脚本一次跑通（`CONTROLS_FAILED=0`）。

## 6. 未关闭项

1. `provenance_advisories=1`：`ai-fullstack-delivery` 无 notice 文件（advisory 非致命，license 缺失待上游补）。
2. `negative_controls.py` 的 C5 调用路径 bug 留给后人修（lab 文件，不影响守卫本身）。
3. 完整 15 门回归由协调者统一跑，本卡只覆盖安全门。

## 7. 提交前自检（新增文件盲区，WAVE12 登记）

1. 盲区机制：门在有 `.git` 时走 `git ls-files -s`，只扫 index 已跟踪文件。
   新增文件在 `git add`/提交进 index 前扫描不可见（提交前绿、提交后红）。
   T06（本文件 C2）与 WAVE12（`docs/community/CROSS-REVIEW-WAVE12.md`
   掩码前字面量命中 `aws-access-key-id`）是同一个坑两次。本节为该盲区的
   登记处，后续同类事件追加到此处，不改门。
2. 自检命令（cwd=仓库根，先 `$env:PYTHONIOENCODING='utf-8'`）：
   ```powershell
   $env:PYTHONIOENCODING='utf-8'
   $env:GIT_DIR='D:\__no_such_git_dir__'
   & (Resolve-ReverseToolSpec -Name 'pyre').Command skills\scripts\verify-repository-security.py
   Remove-Item Env:\GIT_DIR
   ```
   原理：`GIT_DIR` 指向不存在路径迫使 `rev-parse --is-inside-work-tree` 失败，
   门走 `os.walk` 回退，扫描工作树全部文件（含未跟踪新增）。
   `Remove-Item Env:\GIT_DIR` 必须执行，否则后续 git 命令共用该坏变量会失败。
   本卡实测该开关有效：lab 副本（无 `.git`，同属回退路径）正常扫描并命中植入。
3. 噪音与判读：该模式如实扫到平时不可见的本地产物——例如
   `skills/scripts/__pycache__/*.pyc`（被 `**/__pycache__/` 忽略、
   不会提交，报 `unreviewed tracked binary-like file`，已用
   `git check-ignore -v` 实证）。判读：先 `git check-ignore -v <path>`；
   被 ignore 的本地产物忽略；lab 副本里的人工植入逐条归因到所属对照；
   只有将要 `git add` 的新增路径命中才算真问题。
   不要为消噪给 `docs/` 开 `SCAN_EXCLUDES`。
   另注意：门读的是 index 内容，工作树改完后需 `git add`/提交进 index，
   真树门才会变绿（本卡工作树已修，index 仍是旧 blob，待协调者收口提交）。
4. 为什么不改门：门读 index blob 是刻意设计
   （防杀软隔离工作树载荷后悄悄脱离审查）；给 `docs/` 豁免等于把真实检查
   变成 fail-open 盲区。正确修法沿用 T06：掩码断开
   （`AKIA…EXAMPLE`＋“AKIA 后接 16 位大写字母数字，示例值已掩码断开”，
   读者仍可看出是 AWS key 形状的负向对照证据）＋提交前用人走全扫模式补测。
