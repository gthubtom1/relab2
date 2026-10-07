# CROSS-REVIEW WAVE12（T13 对抗性交叉复核）

复核者：T13（对抗性复核，不是开发者）。复核对象冻结为三提交：
`29825b7`（T04/T05/T06/T10）、`8f0571b`（U11/T11/T12+T14/T24）、`7a1d453`（CR-T24-01）。
复核在仓库外快照 `D:\Project\skills-hub\work\t13-clone`（HEAD=`7a1d453`，工作树干净）执行；
证据脚本在 `D:\Project\skills-hub\work\t13-evidence/`；负向对照在
`work/t13-neg-a`、`work/t13-neg-c`（均为 scratch 拷贝，真树零修改）。
Python 一律 `D:\EXE\python\python.exe`，先 `$env:PYTHONIOENCODING='utf-8'`。

## 1. 门基线（复算）

`skills/tests/run-ci-gates.py --runner python`（clone）：`total=15 ok=13
non_blocking=2 blocked=0 failed=0`，exit 0。与 wave3-briefs 的 clone 预测一致。
两个非阻断：`verify-triage-lock`(10，快照缺席降级)、`verify-community-banner`(10，15 缺 banner)。
真树为 `total=15 ok=14 non_blocking=1`（只有 banner）。

## 2. 四条 dry-run（route → wrapper → 入口，真实执行）

链路定义：route=`skills/community/registry.json` 的 `wrappers[]` 记录；
wrapper=`skills/community/<hub>/SKILL.md` 的 ACTION REQUIRED；
入口=`skills/scripts/community-route.py --hint … --source … --json`。

| # | source | hint | route | wrapper | entry exit | status/matches |
|---|---|---|---|---|---|---|
| D1 | ctf-super-hub | ctf pwn heap exploit rop | wrapper-ctf-super-hub → ctf-hub/SKILL.md 存在 | ACTION REQUIRED（case-init 先行） | 0 | matched / 1 wrapper，total_refs=13，展示 3 |
| D2 | hack-skills | web sql injection pentest burp | wrapper-hack-skills → hack-hub/SKILL.md 存在 | 同上 | 0 | matched / total_refs=17，展示 3 |
| D3 | ai-fullstack-delivery | delivery service worker queue retry backoff deploy rollback canary narrow query xyzzy | wrapper-ai-fullstack-delivery → delivery/SKILL.md 存在 | 同上 | 10 | needs_review / total_refs=34 |
| D4 | apk-reverse-community | apk reverse smali jadx android | wrapper-apk-reverse-community → apk-extension/SKILL.md 存在 | 同上 | 0 | matched / total_refs=1，展示 1 |

D3 备注：通用 hint（`fullstack delivery workflow deploy pipeline`）得
`blocked/budget_exceeded` exit 20（total_refs=154 > 50，见 §4 P1-3）。
`adapt-community.py inspect --source apk-reverse-community` 在无快照时
exit 21（missing_input，JSON 走 stderr），行为诚实。

复算：`D:\Project\skills-hub\work\t13-evidence\dryrun.py`。

## 3. 三条负向测试（全部真实失败/真实非零）

- NEG-A（安全门）：`t13-neg-a` 拷贝内植入
  `community-raw/hack-skills/sqli-sql-injection/creds-planted.md`
 （含 `AKIA…EXAMPLE` 形，AKIA 后接 16 位大写字母数字，示例值已掩码断开）→ `verify-repository-security.py` 报
  `FAIL … 1 issue(s)` / `credential-shaped secret aws-access-key-id x1:
  …creds-planted.md`，exit 1（`t13-evidence/neg-a-exit.txt` 第一行 `exit=1`）。
  附带方法学发现：该门有 `.git` 时读 index blob（`git show :path`），工作树植入
  不可见（首轮 exit 0）；去 `.git` 走 working-tree 回退后即命中。
  CI 扫的是已提交树，故不构成漏检洞，但 lab 复现须知此语义。
- NEG-B（路由/预算）：`--limit 0` 与 `--limit 9` 均 exit 2
 （`--limit must be 1..5`）；通用 delivery hint exit 20 budget_exceeded；
  分次累积 `34（delivery窄）+17（hack）=51 > 50`，单次均未阻断——预算无跨调用累加器（stateless CLI，既定设计，见 §5）。
- NEG-C（provenance/许可证）：`t13-neg-c` 内把 source-lock 首条
  pinned/resolved 改 `0…0` → `verify-source-attestation.py --snapshot-root
  D:/Project/skills-hub/upstream` exit 20
 （`snapshot HEAD '16926d…' != resolved_commit '000…0'`）；同拷贝内伪造
  triage 豁免条目 + `--write-lock` 重生锁 → `verify-triage-lock.py` 只给
  exit 10（见 §4 P1-1）。

## 4. P0/P1 阻断清单（单独成段）

**P1-1（triage 降级即免检通道，owner：T24/协调者）。**
现象：伪造 `upstream_layout_unmappable` 条目并重生 lock 后，
无快照环境（含 CI）下 `verify-triage-lock.py` exit 10 而非 20。
复现：`t13-evidence/neg_c_triage.py`（registry 342→343 条 + `--write-lock`）。
证据：`unmappable 14 (machine-checked 0)` + `NEEDS_REVIEW … 1 item(s)`，exit 10。
影响：digest 锁只防单文件改；双文件攻击在 CI（恒无快照）下恒为绿色构建的 exit 10。
真树当前 13/13 条在真实快照下全过（exit 0），故是未来 PR 通道问题，不是现网污染。
建议：给脚本加 `--snapshot-root`（对齐 attestation 校验器）；CI 至少对 lock 文件本身的变更要求 CODEOWNERS 复核。

**P1-2（attestation 无门执行，U10 重演，owner：T12/T10）。**
现象：`scripts/verify-source-attestation.py` 与 `verify-community-bundle.py`
不在 `ci-gates.json`（17 门无此二者）且 `ci.yml` 未直接调用；`verify-gate-wiring.py`
只查“已列门是否被调用”，不管“未列脚本”，故 4 条 attestation 在 CI 内永不执行。
复现：`ci-gates.json` 门 id 清单无 `attestation/bundle/release`；`grep .github` 仅命中注释行。
证据：快照缺席时 attestation exit 10（静态声明）；有快照时 4/4 live（含 digest 重算）exit 0——机制有效但无人调用。
影响：`source-lock.json` 的 digest 是纸面资产；上游快照被替换后 CI 不会报警。
建议：把 attestation（快照缺席按 exit 10 登记为非阻断）接入 manifest + wiring 校验。

**P1-3（delivery 通用查询无恢复路径，owner：T11/T02）。**
现象：`--hint "fullstack delivery workflow deploy pipeline" --source
ai-fullstack-delivery` exit 20（154 refs > 50）。此时已用 `--source` 过滤，
SKILL.md/LOADING-BUDGET.md 写的恢复动作（“用 --source 重查/分查”）空转；
payload 不给收窄建议，用户只能靠猜更窄的词。
复现：`t13-evidence/delivery-blocked.txt`（`failure_reason=budget_exceeded`）。
影响：可用性死角（fail-closed 过度）；不是越权洞（单次响应确未泄漏超量）。
建议：超预算时仍返回 top-3 + 明确收窄建议，或在 `required_action` 内给候选窄化词。

**P1-4（promote 拒绝检查是全树、写入是分源，单源 promote 结构性无解，owner：T05/协调者）。**
现象：`adapt-community.py` 拒绝检查循环全部 SOURCES（L1274–1286），而实际写入
按候选携带源分源执行（L1328–1340）。单源候选（如 apk t13probe，verify exit 0）
`promote --dry-run` exit 20，`unregistered_count=1004`——其中绝大部分是候选
根本不会写的他源文件。
复现：t13-neg-c 上 import/verify/promote 三连（见 §6）。
影响：与“全量 302 未登记差异拒绝”叠加后，promote 无任何可走路径：
全量走不通（302），单源走不通（全树检查）。是设计（fail-closed）也是死锁；
解锁需 owner 逐类登记变换（目前仅 `t09-load-instruction-neutralize` 一条）。
建议：拒绝检查按候选 `sources` 收敛到分源；给 222 条非 license 漂移定 owner 与登记时限。

**P0：无。** 现网四链路可走、release 双门均阻断（`--release` exit 20，
source_scoped=6 skill_scoped=446 total=452，与 MATRIX 一致；release-gate
472 findings），未发现可利用的执行面绕过。

## 5. 被证伪/降级的疑点（同样是复核产出）

- banner 15 缺件：逐条确认为 `docs/community/**` 纯文档（delivery 8、apk 2、ctf 5；
  hack 0），raw 293 SKILL 合同缺失 0、`AI LOAD INSTRUCTION` 回潮 0。确是文档问题，
  但 `THIRD_PARTY_NOTICES.md`/`SECURITY.md` 无 banner 仍有来源混淆风险——留作非阻断同意项。
- 预算绕过：单次响应不可绕（超 50 即 exit 20）；分次累积（51>50）是文档化的 L2 行为，
  无跨调用状态即无跨调用预算——设计如此，不定为漏洞。
- U3 正则漏 `## 6.`：`insecure-source-code-management:193`、
  `websocket-security:179` 两处属实；`request-smuggling:345` 的 `## 12.` 与
  同文件 `## 0.` 共存，不新增缺口。口径差解释成立。
- T24 17.19：README*/CLAUDE.md 无 `RED_TEAM/BLUE_TEAM/AI LOAD INSTRUCTION/`
  可执行残留；`community-raw` 全树该串 0 命中。0 残留成立。
- NOTICE vs MATRIX vs 门：MATRIX 口径（skill 154/138/1=293；release 446+6=452；
  local 292+6=298）与双门输出逐数一致；NOTICE 4 源逐条一致；NOTICE“4/4 缺
  attestation”指 registry sources[] 的 16 个 null（已登记状态），与
  source-lock.json 有 digest 不矛盾——但正是 P1-2 的根子（两处事实源，门只读其一）。

## 6. 测量一览（皆可重跑）

- 门：clone `15/13/2/0/0` exit 0；真树 `15/14/1/0/0`（brief 值，本卡复算 clone 侧）。
- dry-run refs：13 / 17 / 34（窄）·154（通用，blocked）/ 1；累计 34+17=51>50。
- release：validate local exit 0（292+6=298）；--release exit 20（446+6=452）；
  release-gate local exit 0（472 findings）。
- attestation：有快照 4/4 live exit 0；篡改后 exit 20；无快照 exit 10。
- triage：真树+真快照 13/13 exit 0；伪造+重锁后 exit 10（machine-checked 0）。
- promote：apk 单源 verify exit 0 → promote --dry-run exit 20（unregistered 1004）。

## 7. release 结论（可反驳的具体断言）

本仓库在 `7a1d453` 是 **local-only integration candidate**，不是可公开分发的发布物：
`validate-integration.py --release` 与 `verify-release-gate.py --release` 均以
exit 20 阻断（452/472 项），与 MATRIX/NOTICE 口径一致——该阻断是门的正确行为。
在 P1-1（triage 双文件伪造在 CI 只得 exit 10）、P1-2（attestation 永不被 CI 执行）、
P1-4（promote 无可走路径）关闭前，任何“可发布”断言都会被本报告 §4 的复现命令反驳。
