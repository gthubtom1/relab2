---
name: code-review
description: 逐行评审 diff：判断改动是否提升 code health、是否足够小自包含，按设计/功能/复杂度/测试给结论。用于：帮我审这个 PR、这段改动能不能合。
---

# 代码评审（Code Review）

本技能管**评审一份已有改动**：读 diff、逐行判断、给出 approve / 要求修改 / 要求拆分的结论。它依据的判据是 code health（后续维护者能否更省力），不是作者是否听话，也不是风格是否与某个人一致。

它不负责验证"我自己写的对不对"，也不负责安全面——那两条各有专门技能，见下方负例。

## 判据（本技能的核心）

**总则**

- 若改动**确实提升 code health** → 应当 approve。判据是"新的代码比旧的好"，不是"已经完美"——没有完美代码，只有更好的代码；不要因为"还能更好"而阻塞。
- 若一条意见只是**个人偏好**且不损 code health → 不阻塞，最多标 `Nit:`。技术事实（正确性、性能、可读性代价）优先于口味。
- 若改动**大到无法高效审**（一次做多件事、混入无关重构、缺上下文） → 可直接拒，并说明拆分方式；这是正当理由，不是刁难。
- 若改动**自包含**（一次一件事、~100 行量级、测试随同、不破构建、重构与行为变更分开） → 正常逐行审。
- 若评审已经卡住（作者已响应，结论仍未给出） → **不让 CL 挂着**：及时给结论，拖着本身就是 code health 的损失。

**逐维清单**（每维都问，权重不同）

- **Design（最重要）**：改动是否放在正确的位置、是否与既有抽象一致？**特别警惕 over-engineering** —— 只解决现在已知要解决的问题，不为想象的未来加抽象、配置或泛化；多余的抽象层、为单一实现准备的接口、用不到的开关，都是要挡的。
- **Functionality**：作者本意是让代码按新方式工作吗？用户会不会受损（边界、错误路径、破坏既有行为）？有并发的地方会不会死锁 / 竞态？
- **Complexity**：这段代码现在读得懂吗？别人将来改它要付多大代价？能否用更少的代码达成同样的事？
- **Tests**：测试是否**和这次改动在同一个 CL**？测试会**因坏代码失败**吗（还是永远绿的装饰）？断言是否简单、有用、直指行为？
- **Naming**：名字是否让调用点自解释。
- **Comments**：注释解释 **why**（约束、非显然的取舍），而不是复述 what 的代码译文；过期注释按缺陷处理。
- **Style**：与所在文件 / 项目现状一致即可；非关键项标 `Nit:`，不阻塞。
- **Consistency**：不与同目录既有约定打架；要改约定就整批改，不在一处分叉。
- **Docs**：改了 build / test / 接口 / 发布行为时，对应文档是否随之更新 —— 详见 `../docs-changelog/SKILL.md`。
- **Every Line**：逐行看过再下结论；没读到的行不发表意见，也不假装读过。
- **Context**：先看改动周围的既有代码与更高层目标，再判定"更好"是否成立 —— 局部更"优雅"但偏离整体方向的改动不算提升。

**边界判断**

- 若把本评审当**主要 bug 门禁** → 认知有误：现代 code review 的主要产出是 maintainability 与知识共享，bug 拦截交给测试与自动化门禁（CI / 静态分析 / 模糊测试）。发现 bug 就报，但不要用"漏了 bug"否定评审形式本身。
- 若改动引入的是**安全**缺陷（鉴权缺失、注入、密钥硬编码、依赖问题） → 转 `../code-audit/SKILL.md`，不在本技能里做安全结论。
- 若作者**反复不接受同一个技术事实** → 记录分歧与两侧判据，升级给决策者，不无限循环。

**可测判据（下结论前必须过得去的四条）**

- 每条意见都能指到具体 `file:line`，并写清它对**下一个改这段代码的人**的代价（多花多久、会漏改哪一处、回滚会不会连带）；指不到行的意见不写。
- 结论只有三种：approve / 要求修改 / 要求拆分；每个阻塞项都要归到 Design / Functionality / Complexity / Tests / 自包含 之一，"我觉得"不构成阻塞。
- 测试永远绿的改动（只加 snapshot、没有断言、断言不随坏代码变红）按"这次没带测试"处理，不看它显示几个 pass。
- `git diff --stat` **>400 行**或文件数 **>10** 时逐行审的产出不可信 → 直接要求拆分，不逐行走个过场。

## When NOT to use（近邻负例）

- 要验证**自己刚做的改动**对不对（跑测试、对照行为）→ 用 `../verify-done/SKILL.md`
- 要审的是**安全面**（注入 / 鉴权 / 密钥 / 依赖）→ 用 `../code-audit/SKILL.md`
- 审的是**交付形态**（PR 描述、验证证据、CI 状态）而非代码本身 → 用 `../pr-ship/SKILL.md`
- 要审的是 case 证据包而非代码 → 用 `../case-review/SKILL.md`
- 要确认的是"测试到底有没有真的失败过"（红绿证据），而不是评审这份 diff → 用 `../write-tests/SKILL.md`
- 这份 diff 自己就是从一份说不清的需求里长出来的（验收点写不出）→ 先 `../req-clarify/SKILL.md`，评审只会把歧义固化

## When to Pivot

信号与判据见 `../ops/skill-pivot-contract.md`。本技能去向：

| 触发证据 | 换到 |
|---|---|
| `git diff --stat` 显示改动 **>400 行**或文件数 **>10**，作者一句话说不清这次在做什么 | 拒审并要求拆分；拆法见 `../implement-feature/SKILL.md` |
| diff 里出现与标题无关的重构（改名 / 移动 / 重排格式占了 diff 一半以上） | 要求先把纯重构拆成独立 CL 再回来审行为变更 |
| diff 命中注入 / 鉴权 / 密钥 / 反序列化面（新增 `eval(`、拼 SQL、硬编码 token） | `../code-audit/SKILL.md` |
| CI 报绿，但同一条命令本地跑出来**零输出 + rc=0**（假绿特征） | 先按 `../field-journal/2026-10-13_windowsapps-python3-stub-false-green.md` 的口径判，再决定信不信；验证归 `../verify-done/SKILL.md` |
| 改动动了 build / test / 接口 / 发布行为，diff 里**没有**对应的文档改动 | `../docs-changelog/SKILL.md` |
| 同一技术事实来回**两轮**，作者仍未给出新证据 | 记录两侧判据，升级给决策者，停止往返 |
| 待审的是我自己刚写完的那份改动 | `../verify-done/SKILL.md` |
| 待审的是交付形态（PR 描述 / 验证证据 / CI 状态），代码本身没毛病 | `../pr-ship/SKILL.md` |
| 改动碰的是崩溃路径或协议帧，光读 diff 判不了真假 | 先用 `cdb -z <dump>` / `tshark -i <iface> -f "tcp port <p>"` 复跑一次再判；要读懂没源码的 native 件 → `../reverse-engineering/SKILL.md` |

## 真实用例（本仓已发生，照着踩过的坑问）

- `../field-journal/2026-10-13_windowsapps-python3-stub-false-green.md` —— 本机 `python3` 是 0 字节的 App Execution Alias：rc=0、零输出，**205 条回归用例整体假绿**。审一份"CI 全绿"的 diff 前先问：绿的是哪条命令、它跑的是真解释器吗。
- `../field-journal/2026-08-14_windows-powershell-native-exit-code-pr-review.md` —— 引导脚本 PR 里 `git rev-parse ... | Select-Object -First 1` 之后读 `$LASTEXITCODE` 得到 `-1`，合法 checkout 被 fail-closed 分支误拒。审 PowerShell 改动先看退出码是在管道**前**还是**后**取的。

## 工具链（本机实测入口）

| 工具 | 本机怎么调 | 接给谁 |
|---|---|---|
| `git diff` / `git diff --stat` / `git log -p --follow <file>` | `git` 在本机 PATH 上（`Get-Command git` 有结果，本机实测） | 先量规模与历史：`--stat` 超阈值直接转上面的拆分分支；`log -p` 看这行以前为什么这么写 |
| `curl` | 系统自带的 `curl.exe`（本机 `command -v curl` 有结果；仓里 `scripts/bootstrap-reverse.sh` 也用它下载） | 改动涉及 HTTP 面时，改动前后各打一次同一请求，比状态码与响应体，而不是只读 diff 想象 |
| `cdb` | 探测层现查：`. ../scripts/lib/Bootstrap.ps1` → `Resolve-ReverseToolSpec -Name 'cdb'`（TOOLS.md §2 登记的 WinDbg 控制台版） | 作者声称修了崩溃 → `cdb -z <dump>` 看栈帧是否与其描述一致 |
| `tshark` | TOOLS.md §5 登记（GUI `Wireshark` 的 CLI 孪生，禁止拉 GUI）；本机没装时走探测层确认后再按 TOOLS.md 取 | 协议 / 握手面改动，抓一次 loopback 对比帧 |
| 探测层通则 | `. ../scripts/lib/Bootstrap.ps1` → `Resolve-ReverseToolSpec -Name <id>`，读 `Available` / `Command` / `Via` | 上表任何一条用前先定位，拿到 `Command` 就用完整路径调用；单条 `Get-Command` 返回空 ≠ 本机缺该工具 |

## 定义完成

本技能产出算「完成」的**外部可观测**条件（不许写形容词）：

- 对 diff 里的每个 hunk 都给过判断，或明确写出"未读到此 hunk"
- 结论是 approve / 要求修改 / 要求拆分三选一，并附判据来源（哪一维、什么证据）
- 无因个人风格偏好而阻塞的项；阻塞项均可归到 Design / Functionality / Complexity / Tests / 自包含 之一

## 输出契约

```
FACT:       <观察，带来源：命令 / 文件:行 / Evidence ID>
HYPOTHESIS: <可测试断言 + confidence: high|medium|low>（状态见 ../ops/binary-model.md）
QUESTION:   <当前最大不确定点>
NEXT:       <继续 | 换技能 | 停止（附成本判据）>
```

## 置信度词表

词表见 `../ops/confidence-vocabulary.md`。本技能特有判据：

- `confirmed`：已逐行读过 diff，且结论中每条阻塞项都能指到具体 file:line
- `low`：只看了 PR 描述或 diff 摘要、未读改动上下文就断言"新的更好"
