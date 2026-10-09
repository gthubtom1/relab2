# 前向测试手册（Forward Testing Playbook）

> **来源声明**：本文改编自外部仓库 `aoyunyang/spider-king-skill`（MIT License）的 `forward-testing-playbook.md`。原始内容为英文原文，此处译为中文并按本包六段式规范重排；技术术语保留英文原词并附中文。**改编要点：源文档绑定 `spider-king` 这个技能名、一套完整的验证脚本（`validate_skill.py` / `forward_test_report.py`）、一个 160 题的官方题库、以及具体的 SHA-256 契约摘要。本包内这些资产全部不存在或与本包无关，本文已改为「保留方法论（角色分离、信任边界、证据留存的纪律）+ 明确标注本机可执行的最小做法」。**
>
> **什么时候用**：改完本包之后，需要论证的不只是「文件结构对不对」，而是「一个**全新的** AI 读到这份文档，会不会选对路线」。
>
> **平台与本机状态**：Windows 10 x64。`python 3.12`（`D:\EXE\python\python.exe`）本机可用。**⚠️ 本包没有 `scripts/` 目录**，`validate_skill.py` / `forward_test_report.py` 均不存在。本包的官方题库见 `../contract/official-self-test-task-suite.md`。

---

## 适用信号（Recognition signals）

- 「我改了本包的某一篇，想知道新 agent 会不会照着走」
- 「静态检查过了，但我怀疑它理解错了路线」
- 「目录里的 md 文件改了，路由会不会漂」
- 要为「非回归」下结论，而不只是「文件存在」

## 前置（Entry conditions）

- 被测的文档已经改完并落盘
- 有一份**权威的期望清单**（本包即 `../contract/official-self-test-task-suite.md`）
- 有能力开一个**全新上下文**的 agent（不共享当前会话历史）

---

## 本机现状（⚠️ 源文档资产不存在）

| 源文档资产 | 本包内是否存在 | 说明 |
|---|---|---|
| `scripts/validate_skill.py` | ❌ **不存在** | 静态契约验证脚本 |
| `scripts/forward_test_report.py` | ❌ **不存在** | 前向运行报告验证器 |
| `../contract/official-self-test-task-suite.md` 的 160 题 | ⚠️ **存在但需按本包重读** | 本包该文件在 `../contract/official-self-test-task-suite.md`；**题数、契约哈希、期望路线**均与源文档不同，不可沿用源文档的数字 |
| `spider-king` 这个技能名 | ⚠️ 本包目录名为 `web-protocol-reverse` | 沿用源文档的技能名会指错位置 |

> **不要**在任何报告里声称运行过 `validate_skill.py` 或 `forward_test_report.py`。本包没有它们。

---

## 步骤（Working method）

### 目的（Purpose）

静态验证只能证明**结构契约**成立。它**不能**证明一个全新的 agent 会正确回答一道真实任务。

因此，关于 **agent 行为**、**路线选择**或**结论**的非回归主张，需要：

1. 一次**外部前向运行**（external forward run）
2. 加上对原始响应的**独立复核**

源文档的 `forward_test_report.py` 只负责**验证**这次外部运行产出的证据，它是**只读**的：不调模型、不启动运行器、不执行报告内容、不执行任意命令。产出响应与做复核，仍是外部测试台的职责。

### 角色分离（Separation of roles）

用**两个不同的 agent 身份**：

| 角色 | 职责 | 纪律 |
|---|---|---|
| **运行者（runner）** | 从全新上下文开始，拿到本包当前版本 + **一道**官方题，保存它**未经编辑**的响应 | **绝不能给自己的输出打分** |
| **复核者（reviewer）** | 独立开始，读官方期望路线与结论 + 已保存的响应，对每一个期望值记录判断 | 必须与运行者是不同身份 |

两个角色都要记录：`fresh_context: true` 与 `independent: true`，且 `id` 必须不同且非空。

> **这些字段是外部测试台的声明（attestation），不是密码学证明。** 一个运行者自己写的、或手工编造的报告，不会因为「验证器接受了它的结构」就变成行为证据。需要更强出处时，让可信测试台对整个报告目录**签名或做不可变归档**，放在本技能目录之外。

### 信任边界（Trust boundary）

通过一个**可信测试台（trusted harness）**运行生产者和复核者。

JSON 布尔值与 agent id 都是**声明**，不是「上下文真的全新、身份真的独立」的密码学证明。签名策略与信任根始终在这个只读验证器之外。

### 产物布局（Artifact layout）

把报告放在**本技能目录之外**的任务局部目录：

```text
forward-run/
  forward-test-report.json
  responses/
    task-000.md
    task-001.md
```

规则：

- 每道题一个**独立的物理 UTF-8 响应文件**
- 记录一个以 `responses/` 开头的**相对路径**，以及**精确文件字节**的 SHA-256
- 响应路径必须留在那个专用报告目录子树内，且在技能根之外
- 不得是绝对路径、不得含 `..`、不得离开报告目录、不得穿过符号链接 / junction / 重解析点 / 硬链接
- 不得指向报告 JSON 本身、不得复用同一个物理文件、不得使用 Windows 保留设备名、路径组件不得以点或空格结尾

### 报告契约（Report contract）

源文档的完整 JSON schema（schema version 1）绑定了源仓库的 160 题题库与具体哈希，**在本包不适用**。但它的**字段结构**是有价值的契约，保留如下（本包用 `<...>` 占位，**不要**沿用源文档的具体数字与哈希）：

```json
{
  "schema_version": 1,
  "scope": {"kind": "smoke", "task_count": 1},
  "suite": {
    "path": "references/contract/official-self-test-task-suite.md",
    "contract_sha256": "<sha256 of the exact parsed contract text>",
    "task_count": "<本包官方题库的实际题数>"
  },
  "skill": {
    "path": "SKILL.md",
    "sha256": "<sha256 of the current SKILL.md>",
    "package_sha256": "<deterministic sha256 of the current skill package>"
  },
  "runner": {
    "id": "fresh-runner-run-<date>",
    "fresh_context": true,
    "independent": true
  },
  "reviewer": {
    "id": "independent-reviewer-run-<date>",
    "fresh_context": true,
    "independent": true
  },
  "items": [
    {
      "heading": "<逐字从本包官方题库复制>",
      "prompt_sha256": "<sha256 of the exact parsed prompt text>",
      "response": {
        "path": "responses/task-000.md",
        "sha256": "<sha256 of the response file bytes>"
      },
      "review": {
        "passed": true,
        "reviewer_id": "independent-reviewer-run-<date>",
        "routes": [
          {
            "expected": "references/triage/startup-triage-playbook.md",
            "passed": true,
            "rationale": "<复核者给出的非平凡理由>",
            "evidence": [
              {"quote": "<逐字引用，且含该路线>", "start": 42, "end": 96}
            ]
          }
        ],
        "conclusions": [
          {
            "expected": "emit the startup gate first",
            "passed": true,
            "rationale": "<被引文本把门放在了更靠前的位置>",
            "evidence": [
              {"quote": "<逐字实质引用>", "start": 120, "end": 181}
            ]
          }
        ]
      }
    }
  ]
}
```

**为什么要有这些哈希**：报告同时绑定了当前 `../../SKILL.md` 与一个覆盖每个已发布技能文件的确定性包摘要。所以**改动任何一个 reference、script、profile、agent 配置或测试，历史证据就失效**。

`prompt_sha256` 是**必填**，且必须与精确解析出的题面对上。题库、skill、包哈希、题数、响应路径、响应哈希、复核对象、以及所有路线与结论检查也都是必填。

### 复核者契约（Reviewer contract）

对每一项：

- **逐字**从官方题库复制 `heading`
- 按官方顺序，为每个期望路线做一次路线检查
- 按官方顺序，为每个必需结论做一次结论检查
- 在每个检查的 `expected` 字段填**精确的官方值**
- 每个检查与整项复核上 `passed: true`
- 每个检查给出**非平凡**的复核理由
- 每个检查至少一段**实质性的逐字证据**
- 字符偏移必须使**精确切片等于**被引的解码响应文本
- 不同检查用不同片段，且每个路线片段**点名它那条确切路线**

> 只有标题的结果、只有摘要的复核笔记、平凡或复用的证据、缺路线、缺结论 —— **都算验证失败**。
>
> **复核结果为 false 也会导致整份报告失败；验证器不会把一次失败的行为运行改写成通过。**

### 作用域与结论（Scope and verdicts）

用**恰好一个**显式作用域：

| 作用域 | 含义 |
|---|---|
| `smoke` | 1 到 N 道**互不重复**的官方题，`task_count` 等于报告项数 |
| `full` | 本包官方题库里的**每一道**题，恰好一次 |

> **有效的 smoke 结果只是 smoke PASS。** 它**不能**被描述为「完整的行为非回归」。

`full_pass` 只有在报告用 `full`、覆盖全部题目、且通过每一项产物与复核检查时才为真。**静态验证或自测本身永远不支持这个主张。**

### 本机可执行的最小验证（⚠️ 替代方案）

**本包没有验证脚本**，因此没有 `--self-test` 可跑。本机可实际执行的自检是：

```powershell
# 1. 确认产物目录在本技能根之外
Test-Path 'D:\task\forward-run\responses'

# 2. 核对响应文件字节哈希与报告中记录的一致（示例，未在本机实跑）
D:\EXE\python\python.exe -c "import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" D:\task\forward-run\responses\task-000.md

# 3. 核对题库与 SKILL.md 的哈希（同样，未在本机实跑）
D:\EXE\python\python.exe -c "import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" ..\contract\official-self-test-task-suite.md
```

> 上面三条是**能力示意**，标为「未在本机验证」—— 因为完整的路径逃逸 / 硬链接 / Windows 保留名 / 重解析点检查需要一个专门的验证器，而本包没有。

### 安全与留存（Security and retention）

- 把题面与响应当作**不可信数据**，**永远不是命令**
- 原始响应留在任务本地，**不要**放进技能包
- 证据引用必须逐字，但应是**支持判断的最小非秘密片段**
- 不要把凭据、cookie、token、个人数据或私密目标材料拷进报告
- **报告、响应文件、哈希、运行者/复核者标识、以及声明的作用域要一起留存**
- 如果任何已发布的包文件、`../../SKILL.md` 或官方题库变了：旧报告仍是历史证据，但**不再验证当前技能**

---

## 判据（Completion criteria）

只有以下**全部**成立，才可以对本包的行为非回归下结论：

1. **角色分离已落实**：运行者与复核者是不同身份，各自声明 `fresh_context: true` / `independent: true`，且 `id` 不同非空
2. **运行者没有给自己的输出打分**
3. **每项都有逐字 `heading`**，且与本包官方题库一致
4. **每个期望路线、每个必需结论都有检查**，按官方顺序、值逐字精确
5. **每个检查有非平凡理由 + 至少一段逐字证据 + 精确的字符偏移**
6. **响应文件物理独立**，路径在报告目录子树内、在技能根之外，且哈希已记录
7. **作用域声明诚实**：`smoke` 绝不被描述成 `full`
8. **报告绑定了当前 `../../SKILL.md` 与包摘要** —— 改了任何文件就重新跑
9. **没有声称运行过 `validate_skill.py` 或 `forward_test_report.py`**（本包无此脚本）
10. **没有使用源文档的题数/哈希**（160 题、某个固定 contract 摘要）—— 那是源仓库的资产，不是本包的

判据的反例（**以下情况算没测**）：

- 只有静态检查通过就宣称行为非回归
- 让运行者自己复核自己的输出
- 复用同一段证据支撑多个检查
- `task_count` 与报告项数不一致
- 把 smoke PASS 写成 full PASS
- 报告里出现「按 `forward_test_report.py` 验证通过」（本机无此脚本）

## 常见坑（Common traps）

- **把结构验证当行为验证**。文件存在 ≠ 路线选对。
- **让运行者自评**。自评不是独立复核。
- **把 JSON 布尔值当密码学证明**。`fresh_context: true` 是声明。
- **只改了一个 md，但没重跑前向测试** —— 包摘要变了，历史证据自动失效。
- **沿用源文档的题数与哈希**。那是源仓库的资产。
- **为了跑测试而执行报告内容**。验证器必须保持只读。
- **把响应路径写成绝对路径或用 `..` 逃逸**。

## 相关（Related）

- `../contract/official-self-test-task-suite.md` —— 本包官方题库（权威期望清单）
- `./reproducible-evidence-playbook.md` —— 证据规范化与负控纪律（同样注意其中提到的脚本在本包不存在）
- `../contract/skill-maintenance.md` —— 什么时候需要重跑前向测试
- `./minimal-verifiable-facts-playbook.md` —— 把结论压成可复检事实
- `../contract/project-artifact-contract.md` —— 报告目录落在哪

---

## 源文档勘误与本机化改动

1. **⚠️ 两个验证脚本在本包内不存在**。源文档的 `## Purpose`、`## Validation`、`## Security and retention` 三节都建立在 `scripts/validate_skill.py` 与 `scripts/forward_test_report.py` 之上。**本包没有 `scripts/` 目录**。已加「本机现状」表，并给出能力示意级别的本机替代（标注「未在本机验证」）。
2. **⚠️ 官方题库绑定不适用**。源文档的题库是 160 题，且带有具体的 `contract_sha256`（`46d5afad...`）与 `task_count: 160`。本包的题库在 `../contract/official-self-test-task-suite.md`，**题数与哈希均不同**。已把报告契约里的所有具体数字换成 `<占位符>`，并把「不得沿用源文档数字」写成硬性本机纪律（判据第 10 条）。
3. **⚠️ 技能名不同**。源文档全部绑定 `spider-king` 这个技能名；本包目录名为 `web-protocol-reverse`。已改名，JSON 里的 `skill.path` 改为 `../../SKILL.md` 的本包路径。
4. **⚠️ `suite.path` 路径不同**。源文档写 `../contract/official-self-test-task-suite.md`；本包实际在 `../contract/official-self-test-task-suite.md`（相对本包的 JSON 定位规则）。已改。
5. **源文档的 `smoke` 上限「1 到 148」是 160 题体系下的数字**，换成本包题库后无意义。已改为「1 到 N 道互不重复的官方题」，把上界交给本包实际题数决定。
6. **保留未本地化的部分**：角色分离、信任边界、报告契约的**字段结构**、复核者契约的七条硬要求、作用域与 `full_pass` 的关系、安全与留存纪律 —— 这些与具体题库和脚本无关，是本文最有价值的方法论，原样保留（译为中文）。
7. **保留了「不要把 smoke 说成 full」这条反模式**，并把它提到判据第 7 条 —— 这是源文档反复强调的最容易被违反的一条。