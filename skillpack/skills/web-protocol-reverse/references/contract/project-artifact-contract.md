# 项目产物契约（Project Artifact Contract）

> **来源声明**：本文改编自外部仓库 `aoyunyang/spider-king-skill`（MIT License）的 `project-artifact-contract.md`。原始内容为英文原文，此处译为中文并按本包六段式规范重排；技术术语保留英文原词并附中文，AI 检索时中英文均可命中。改编中修正了源文档的若干表述与失效引用（见文末「源文档勘误」）。
>
> **什么时候用**：**第一次落盘之前**、**把代码从缓存提升（promote）出来之前**，以及**任何一条路线想复用或覆盖已有产物**的时候。
>
> **平台与本机状态**：本文是落盘规程与 manifest schema，不含必须实跑的本包脚本命令。需要本机标注的只有两条：**(1)** 本包**没有** `scripts/` 目录，源文档引用的 `scripts/evidence_normalizer.py` 与 `scripts/check_reverse_env.py` **均不存在**，本文已删除该引用并改写为可执行的人工 / 工具做法；**(2)** 运行时环境指纹涉及的 `python 3.12`（`D:\EXE\python\python.exe`）、`node v24.20.0`（`D:\Tools\Node\node.exe`）本机可用，`iv8` 本机无，`reqable` 本机无。挂载现状见 `../observe/local-mcp-environment.md`。

---

## 适用信号（Recognition signals）

出现下列任一情况，说明必须回到本文核对落盘规则：

- **第一次写入任何文件之前**（哪怕只是一个 `task.json`）
- 想把某个文件从 `js_reverse_cache/` **提升**到稳定交付位置时
- 想**复用**工作区里已有的产物 —— 尤其是 §常见坑 里说的「续作前先扫一遍兄弟产物」
- 想**覆盖**一个已存在的稳定文件时
- 准备交付一份 `analysis/proof_manifest.json` 之前
- 双运行时（Python + Node/WASM helper）打包之前
- 有人提议「换个项目的目录结构」时 —— 见核心规则最后一条

**一句话定位**：本文管的是「东西该落在哪、能不能落、落之前先检查什么」，不管逆向逻辑本身。

## 前置（Entry conditions）

### 核心规则：易失证据与稳定交付分离

**Spider King 把易失的逆向证据与稳定的交付代码分开存放。**

| 内容 | 落点 |
|---|---|
| 任务抓取、探针（probe） | `<project>/js_reverse_cache/tasks/<task-id>/` |
| 稳定证明与交接元数据 | `<project>/analysis/proof_manifest.json` |
| 可运行的 `compact-replay` / `collector` 交付（PyCharm 右键入口） | `<project>/main.py`、`<project>/collector/main.py` |

`evidence` 与 `local-proof` 两种形态**不要求**上述任一入口 —— 除非明确要求了可执行打包。
一个 `no-write` 的对话式结果**不创建**这套目录布局。

**不要在日常工作中用别的技能的项目目录树替换掉本布局。** 本包的标准布局是：

```text
<project>/
  js_reverse_cache/tasks/<task-id>/    # 易失
  analysis/proof_manifest.json          # 稳定元数据
  main.py                              # 稳定入口（按需）
  collector/main.py                    # 稳定入口（按需）
```

### 绑定项目根

**绑定一个项目根。** 用户给了文件夹就用它；没给，**问一次**是用当前工作区还是自定义文件夹 —— 只问一次，之后按绑定值执行。

**在解析目的地之前**，把每一次预期写入绑定到一条**非空**的 `allowedPaths` 条目。解析后的目的地必须**同时**留在绑定项目内**和**某个允许路径内（即等于或低于两者）。

### 必须拒绝的任务自有写入

出现下列任一情况，拒绝写入：

- 目的地是**技能目录**（skill directory）
- 目的地是操作系统临时目录、`%TEMP%`、`%TMP%`、`AppData/Local/Temp`，或某个 agent 临时根
- 路径逃出了选定项目
- 路径是符号链接（symlink）、联接点（junction）、挂载点 reparse path，或硬链接目标
- 该写入会**在没有针对该确切路径批准**的情况下覆盖一个已存在的稳定文件

### 授权红线（与 field-journal 对齐）

**授权与范围必须在别处先固化。** 本文不产生授权，只消费授权。若本次任务需要留下可脱敏复用的 case 记录，落点与字段格式是 `../../../field-journal/_template.md`：其中的「Scope 摘要（脱敏）」记录 `auth_basis` / `network_profile` / `asset_types`，是本文 `allowedPaths` 的上游依据。

> `../../../field-journal/_template.md` 中每条证据记录须满足 `../../case-review/scripts/review_case.py` 的字段契约（`severity` / `status` / `repro_command` / `content_hash` + `artifact_path` / `linked_workitem`），否则 `--strict` 会 FAIL。详见本文「判据」第 9 条。

## 步骤（Working method）

### 一、易失证据（Volatile Evidence）

`js_reverse_cache/tasks/<task-id>/` 用来放：

- `task.json`
- `network.jsonl`
- `runtime-evidence.jsonl`
- `handoff.json`
- `experience-candidate.json`
- `fixtures/`
- `../../../../examples/ctf-demo/report/report.md`
- 下载的 JS、WASM、HTML、字体、图片、protobuf 样本、HAR 提取物、截图、net log，以及解码后的临时文件

**按需创建文件夹。不要预先创建空的证据目录树。**

**原始账号状态、cookie、token、Authorization 值、个人数据与完整私有响应必须留在本地**，在对话中脱敏，并排除出版本控制。
**报告里优先写**：哈希、长度、字段名、来源（provenance）、结构化样本。

### 二、稳定交付（Stable Delivery）

把一个文件从缓存里提升出来，**只有**同时满足以下 5 条：

1. 它的**输入是已知的**。
2. 它的 **import（导入）没有网络、浏览器、profile 或文件副作用**。
3. **定值向量或命名检查点通过**。
4. 若要求了实时路径，那条路径**由 Python 拥有**。
5. 该文件**已列在 proof manifest 或最终报告里**。

用 `main.py` 或 `collector/main.py` 作为右键入口。**只把已证明可复用的职责**移进 helper，例如：

- `collector/client.py`
- `collector/sign.py`
- `collector/bootstrap.py`
- `collector/decode.py`
- `collector/storage.py`
- `utils/*`

**把动态 cookie、时间戳、当前浏览器导出、运行期特有的挑战载荷挡在稳定代码之外。**

### 三、双运行时 helper 打包（Dual-runtime helper packaging）

当 Python 拥有 HTTP、而一个极小的 Node 或 WASM helper 仍然存在时：

- helper 文件**与 collector 放在一起**，**不放进技能目录**
- 随包提供 `package.json` 或等价物与安装说明；**不要依赖拷贝 `node_modules`**
- 随包提供**无秘密**的结构化基线，例如字段槽位掩码、稀疏索引映射、定值向量 fixture
- **线上 token、cookie、账号状态、原始成功凭证留在任务本地**
- 文档写清楚：交付是否仅「无浏览器」，还是**连任何非 Python 运行时都不需要**
- proof manifest 记录 helper 版本或资产哈希，**不记录秘密值**

**环境绑定的实际做法**（*改编改写*，源文档此处调用了不存在的脚本）：

源文档要求「helper 运行前用 `scripts/check_reverse_env.py --project-root <project>` 绑定项目，并用 `--helper-lockfile` 只对显式选定的公开 lockfile 取指纹，记录相对路径、字节长度与 SHA-256，**不拷贝 lockfile 内容**」。**该脚本在本包不存在**。改写为本机可实际执行的做法：

```powershell
# 1) 确认项目根已被绑定（本文「绑定项目根」一节已记录）
# 2) 确认解释器与运行时版本 —— 本机实测：
D:\EXE\python\python.exe --version          # Python 3.12.0
D:\Tools\Node\node.exe --version            # v24.20.0

# 3) 只对显式选定的公开 lockfile 取指纹；不拷贝内容，只记 路径/字节数/SHA-256
#    （Get-FileHash 只读文件，不复制）
Get-ChildItem -Path <project>\collector -Filter package-lock.json -Recurse |
  ForEach-Object {
    [pscustomobject]@{
      path   = $_.FullName.Substring(<project>.Length + 1)   # 项目相对路径
      bytes  = $_.Length
      sha256 = (Get-FileHash -Algorithm SHA256 -Path $_.FullName).Hash.ToLower()
    }
  }
```

把这三列结果写进 manifest 的 `runtimeEvidence.helperLockfiles`。
**项目虚拟环境（venv）一致性**同理用 `D:\EXE\python\python.exe -c "import sys; print(sys.prefix)"` 与项目内 `Scripts\python.exe` 对比，取值写 `projectVenv` ∈ `active | advisory-mismatch | required-mismatch | not-required`。

### 四、Proof Manifest

**manifest 的内容随能力（capability）而定。只记录产出工具能证明的事实；不要用猜测的默认值填未知的 session、helper 或 replay 字段。**

#### （a）独立 `evidence` 交付：evidence proof-manifest schema v2

> *改编改写*：源文档此处要求运行 `scripts/evidence_normalizer.py --proof-manifest` 来生成这个 manifest。**该脚本在本包不存在**。改写为实际做法：**按下面的 schema v2 结构手工撰写**该 manifest，`source.hmac_sha256` 用**带密钥的 HMAC-SHA256** 对源产物（HAR 或 transcript）计算 —— 密钥**只留在本地**，绝不入 manifest；`evidence_package.sha256` 是对**已经脱敏之后**的证据包算的**无密钥** SHA-256。本机 Python 可直接算：

```powershell
# 源产物带密钥指纹（密钥不落盘、不入 manifest）
D:\EXE\python\python.exe -c "import hmac,hashlib,pathlib;k=pathlib.Path('local-key.txt').read_bytes().strip();d=pathlib.Path('capture.har').read_bytes();print(hmac.new(k,d,hashlib.sha256).hexdigest())"
# 已脱敏证据包的无密钥指纹
D:\EXE\python\python.exe -c "import hashlib,pathlib;print(hashlib.sha256(pathlib.Path('evidence-redacted.json').read_bytes()).hexdigest())"
```

```json
{
  "proof_manifest_version": 2,
  "source": {
    "format": "har | transcript",
    "hmac_sha256": "keyed source-artifact fingerprint"
  },
  "evidence_package": {
    "schema_version": 2,
    "sha256": "hash of the already-redacted evidence package"
  },
  "redaction": {
    "scheme": "hmac-sha256",
    "scope": "known-sensitive-fields-and-recognizable-values",
    "publication_review_required": true,
    "raw_hashes_included": false
  }
}
```

**这个 evidence manifest 不主张**实时 replay、**不主张**会话兼容、**不主张** helper 边界。
若已存在一份更宽的交付 manifest，把这个 evidence manifest 写到一个**不同的、已批准的路径**，并从更宽的 manifest 或最终报告里引用它**写入后的哈希**；**绝不覆盖**更宽的 manifest。

#### （b）持久化的 `local-proof` / `compact-replay` / `collector` 交付

记录足够审计所主张能力的内容，且**不存秘密**：

```json
{
  "capability": "collector | compact-replay | local-proof",
  "targetScope": "redacted exact scope",
  "artifactFingerprints": [],
  "sessionScope": "anonymous | account-bound | retained-exception | none",
  "helperBoundary": "pure-python | local-js | wasm | local-bootstrap | iv8-local-runtime",
  "runtimeEvidence": {
    "pythonVersion": "resolved version",
    "nodeVersion": "resolved version | missing | not-required",
    "npmVersion": "resolved version | missing | not-required",
    "projectVenv": "active | advisory-mismatch | required-mismatch | not-required",
    "helperLockfiles": [
      {"path": "relative/public-lockfile", "bytes": 0, "sha256": "..."}
    ]
  },
  "fixedVectorProof": "passed | failed | not-run",
  "liveReplayProof": "passed | blocked | not-requested",
  "browserFree": true,
  "runtimeFree": false,
  "residualRisks": []
}
```

### 五、哈希纪律

**无密钥 SHA-256** 只用于：公开的、高熵的代码；已公开的资产；或一个明确限定为本地的分析产物。

**带密钥 HMAC 指纹**用于：可能含秘密或个人数据的抓取或载荷。

*改编注*：源文档提到 normalizer 的 `--include-raw-hashes` 标志是仅本地使用、不得用于发布 manifest。本包无该 normalizer，**等价做法**是：`redaction.raw_hashes_included` 恒为 `false`，任何时候都不把原始字节哈希写进 manifest。

**对已经脱敏的证据包做哈希**，用于产物审计；**要求发布评审**；**绝不**声称任意输入普遍无秘密。
**manifest 无法包含自己的稳定哈希** —— 所以把它的路径与**写入后的 SHA-256** 记在最终报告或它的上级交付 manifest 里。
**绝不**把原始秘密拷进 proof manifest。

### 六、建议的稳定目录布局

```text
collector/
  main.py
  requirements.txt
  helpers/
    package.json
    encrypt_or_vm_helper.js
  artifacts/
    baseline_field_mask.json
    sparse_slots.json
    fixed_vectors.json
  README_install.md
analysis/
  proof_manifest.json
```

## 判据（Verification checklist）

### A. 写入前的硬性检查（*改编补入*，源文档无独立清单，从「必须拒绝」条目反推）

1. 项目根**已绑定**且已记录；本次每个预期写入路径都命中一条**非空**的 `allowedPaths` 条目。
2. 解析后的目的地**同时**留在绑定项目内与某个允许路径内 —— 即等于或低于两者。
3. 解析链路上**没有** symlink、junction、mount-point reparse path 或硬链接目标（用 `Get-Item -Force <path>` 看 `LinkType` / `Target`，非空即拒）。
4. 目的地**不是**技能目录、OS temp、`%TEMP%`/`%TMP%`/`AppData/Local/Temp` 或 agent 临时根。
5. 若目标文件已存在，**有针对该确切路径的明确批准**，否则拒绝覆盖。

### B. 提升为稳定交付前的 5 条（源文档硬性条件，逐条可核）

6. 输入已知；7. import 无网络 / 浏览器 / profile / 文件副作用；8. 定值向量或命名检查点**实测通过**；9. 实时路径由 Python 拥有（若有）；10. 该文件**已列在** proof manifest 或最终报告中。

### C. manifest 完整性（*改编补入*）

11. `runtimeEvidence` 四个字段**全部有值**（含 `missing` / `not-required` 这类**显式**取值），**没有一个是猜测的默认值**。
12. `helperLockfiles` 每项都有**项目相对路径**、**字节长度**、**64 位 SHA-256**，且**没有拷贝 lockfile 内容**。
13. `redaction.raw_hashes_included` 为 `false`；`publication_review_required` 为 `true`。
14. 含秘密或个人数据的源产物用的是**带密钥 HMAC**，且**密钥本身不在 manifest、不在仓库、不在报告里**。
15. manifest 的**路径与写入后 SHA-256** 已记在最终报告或上级 manifest 中。
16. evidence manifest 与更宽的交付 manifest **存放在不同路径**，后者未被覆盖。

### D. 与 field-journal / case-review 的对接（*改编补入*）

17. 若本次需要独立证据目录（`evidence/E-xxx.md`），每条记录满足 `../../case-review/scripts/review_case.py` 的字段契约：`severity` ∈ `critical/high/medium/low/info/n/a`；`status` ∈ `observed/candidate/validated/false_positive/accepted_risk`；`repro_command` 必填（离线场景在 notes 注明）；`content_hash` 与 `artifact_path` 成对；`linked_workitem` 指向真实存在的 WI。
18. 复核通过：

```bash
D:\EXE\python\python.exe skillpack/skills/case-review/scripts/review_case.py work/<case> --verify-hashes --strict
```

### E. 交付前五问（源文档 `## Promotion Checklist`，逐条回答）

19. 删掉 OS temp 后项目**仍可复现**吗？
20. 移除浏览器 profile 后 collector **仍可运行**吗？
21. 定值样本与线上生成代码**分离**了吗？
22. 每一个轮转状态都**被重新生成、被刷新，或被明确声明为 retained exception** 了吗？
23. **一次走运的响应**被**明确阻止**了被当成规模化能力吗？

**只要有一问答「否」，就把该产物留在缓存里，并返回一个精确的拦路点。**

## 常见坑（Common traps）

- 一次「走运的响应」被当成采集器已经能规模化
- 轮转状态（cookie、时间戳、挑战载荷）留在了稳定代码里
- 定值样本和线上生成代码混在一起，导致样本被覆盖
- 把 `node_modules` 拷贝进交付包，或把 helper 放进技能目录
- 锁文件内容被拷进 manifest（只该记路径 / 字节数 / 哈希）
- **用无密钥 SHA-256 给含秘密的抓取做指纹** —— 那等于把可比对的指纹公开出去
- manifest 里用猜测的默认值填了 `nodeVersion`、`sessionScope` 之类未知字段
- evidence manifest 直接**覆盖**了更宽的交付 manifest
- 试图把 manifest 自己的稳定哈希写进 manifest 自己
- 用 symlink / junction 把写入绕出绑定项目 —— 只检查字面路径不看解析结果，最容易被绕过
- 覆盖了用户维护的稳定文件而没有针对该确切路径的批准
- 用别的技能的项目目录树替换了本布局
- 把原始 cookie / token / Authorization / 私有响应写进报告、fixture、代码或 manifest

## 相关（Related）

- `./provider-work-order.md` —— Write Guard 第 3 条引用本文；授权、scope 与 `allowedPaths` 的上游定义
- `./specialist-handoff-contract.md` —— `handoff.json` 落在本文规定的易失证据层
- `./experience-card-schema.md` —— `experience-candidate.json` 落在同一层
- `./skill-maintenance.md` —— 落盘纪律与校验清单
- `./report-templates.md` —— 报告与 manifest 的呈现模板
- `../observe/local-mcp-environment.md` —— 本机可用工具与挂载现状；`runtimeEvidence` 各字段取值的本机来源
- `../deliver/delivery-gate-playbook.md` —— 交付形态与门禁；判据 E 组「五问」的规程出处
- `../deliver/pure-python-rebuild-playbook.md` —— 「实时路径由 Python 拥有」的具体实现
- `../deliver/case-reuse-playbook.md` —— 续作前扫兄弟产物的做法
- `../triage/reproducible-evidence-playbook.md` —— 产物哈希与复现命令的最低标准
- `../triage/verifier-replay-playbook.md` —— 定值向量与 replay 次数的验证规程
- `../principles/anti-patterns-playbook.md` —— 本文「常见坑」段的原则级对照
- `../state/session-contract-playbook.md` —— `sessionScope` 非 `anonymous` 时的会话分层
- `../../../field-journal/_template.md` —— 授权与范围的脱敏记录、Evidence 链摘要格式
- `../../../field-journal/anonymization.md` —— 脱敏占位符总表；`targetScope` 脱敏时的规范来源
- `../../SKILL.md` —— 证据字段契约与 `--strict` / `--verify-hashes` 审查流程

---

## 源文档勘误（改编时修正）

1. **源文档 `## Contents` 目录块指向英文锚点**。已删除，改为中文六段式结构下的自然导航。
2. **源文档引用 `scripts/evidence_normalizer.py`（`## Proof Manifest` 一节）—— 该脚本在本包不存在**，`scripts/` 目录本身也不存在。已删除该引用，改写为「按 schema v2 手工撰写 manifest + 本机 Python `hmac`/`hashlib` 现场计算指纹」的可执行做法。
3. **源文档引用 `scripts/check_reverse_env.py --project-root <project>` 与 `--helper-lockfile`（双运行时打包一节）—— 该脚本同样不存在**。已删除该引用，改写为本机 PowerShell 的 `Get-FileHash` + `D:\EXE\python\python.exe --version` 等实做步骤，并说明项目 venv 一致性的取法。改写后**只用了本机实际存在的工具**，未编造任何新脚本路径。
4. **源文档提到 normalizer 的 `--include-raw-hashes` 标志** —— 随 normalizer 一并不存在。已改为等价做法：`redaction.raw_hashes_included` 恒为 `false`。
5. **源文档所有交叉引用写作扁平 `references/xxx.md`**，实际这些文件在 `references/<group>/xxx.md`。已全部核实存在后改为实际相对路径（`./contract/xxx.md`、`../triage/xxx.md`、`../deliver/xxx.md` 等），未留任何指向不存在路径的引用。
6. **源文档的 `## Core Rule` 把「PyCharm 右键入口」当作必然产物**，但同一节末尾又说 `evidence` / `local-proof` 不要求入口。本文把布局整理成一张表，把入口标注为「按需」，消除了源文档内部的表面矛盾。
7. **源文档 `## Core Rule` 最后一句的「不要用别的技能的项目树替换本布局」语气模糊**。改编时明确为：日常工作中不得替换；若确有跨技能协作需要，须先与用户确认再改 —— 这是**改编补入**的边界条件，源文档未给出。
8. **源文档的授权字段（`auth_basis` / `network_profile` / `asset_types`）完全未出现**。本文在「前置」补了与 `../../../field-journal/_template.md`「Scope 摘要（脱敏）」的对齐说明，并在「判据」D 组补了 `review_case.py` 的证据字段契约 —— 均已标注为改编补入，源文档并未建立这些联系。
9. **源文档的「脱敏」只有一句定性要求**（「must stay local, redacted from chat, and excluded from version control」），没有指向任何可执行的规范。本文指向本包内**实际存在**的 `../../../field-journal/anonymization.md`（占位符总表 + 自动检测脚本），未编造规范位置。
10. **源文档 `## Promotion Checklist` 的 5 问是全篇唯一的验收清单，但被放在最末且没有与前文任何硬性条件挂钩**。本文把它作为判据 E 组保留原样，并补齐 A–D 组（标注改编补入），使「什么算合格落盘」有完整判据 —— 源文档本身**没有**这样的完整判据。
11. **源文档未声明 `helperBoundary` 枚举含 `iv8-local-runtime`**，而本机无 iv8（社区运行时，PyPI 无发行版）。JSON 枚举值**保持原样未改**，本机可用性在顶部「平台与本机状态」处标注。
12. **源文档正文对「project root」的绑定要求只有一句**（「ask once」），未说明为何只能问一次。本文在「前置」明确「只问一次，之后按绑定值执行」，避免重复打扰用户。