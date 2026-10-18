---
name: implement-feature
description: 小步实现功能：一次只解决一件事，复用仓库既有 pattern，不建第二套约定，不破构建。用于：按已定方案写代码、加个小功能。
---

# 小步实现（Small-Step Implementation）

本技能管「已经知道要改什么，怎么把它改进去还不伤仓库」：一次只解决一件事，写法向仓库既有模式靠齐，构建不被搞坏。它不负责澄清需求、也不负责切功能边界——那两件事定不下来时，写代码只会把不确定性固化进 diff。判断入口只有一句：**这个改动，我能不能用一句话描述？** 不能，就是太大了。

## 判据（本技能的核心）

- 若一次改动同时解决两件事（加功能 + 顺手重构 / 修 bug + 改格式 / 换依赖 + 改行为）→ 拆成两个提交；重构与 feature 分开，回滚才能干净。
- 改动规模：**~100 行量级算合适；接近 1000 行算过大** → 过大就先回 `../design-slice/SKILL.md` 重切，而不是硬写。
- 写代码前必须**先搜仓库**：同类模块怎么写、命名/错误处理/日志/配置/测试脚手架长什么样 → 有既有 pattern 就照抄它；若发现自己在建第二套约定（第二个 HTTP 客户端、第二套错误类型、第二个配置加载器）→ 停，先问是不是该扩既有那套。
- 测试与实现**同 CL**（同一个改动里一起交）；若仓库确实没有测试基建，则至少给一条可重跑的验证命令 —— 「我本地跑过」不算。
- 不破构建：提交前该仓库的 build / typecheck / lint 必须过；为了让自己新代码过关而放宽既有检查（加 skip / 关规则 / 降严格度）→ 停，那不是修好了。
- **不写你无法验证的代码**（If you can't verify it, don't ship it）：本机跑不到的路径（缺环境/缺凭据/缺硬件/需线上）要么造出可跑的验证，要么显式标注未验证并给出回退行为。
- 若写到一半发现改不动的原因其实是需求没定清 → 换 `../req-clarify/SKILL.md`；是边界没切好 → 换 `../design-slice/SKILL.md`；不要边猜边写。
- 若改动开始牵动无关模块 / 需要大范围改签名 → 说明切片切错了，回 `../design-slice/SKILL.md` 重切，不要靠 shim 兼容层硬推。

**可测判据（提交前必须过得去的三条）**

- 这次 diff 能用一句话说清（"加 X"或"改 Y 的行为"）；说不清就是还没切好，先回 `../design-slice/SKILL.md`。
- build / typecheck / lint 要贴**原始输出**（命令 + 末尾几行），"我本地跑过"不算证据；跑不了就写清是哪一项跑不了、为什么。
- 新增依赖必须写进 PR 描述，并跑一次 `git diff` 确认锁文件漂移是**有意**带进来的，不是顺手夹带的。

## When NOT to use（近邻负例）

- 要修的是既有代码的缺陷、行为不变只求正确 → 用 `../fix-bug/SKILL.md`
- 只是一次性验证技术可行性、写完就扔 → 用 `../spike/SKILL.md`
- 需求或验收标准还没定 → 用 `../req-clarify/SKILL.md`
- 边界与接口契约还没定 → 用 `../design-slice/SKILL.md`
- 要证明"这个需求真的做完了"，而不是把它写出来 → 用 `../verify-done/SKILL.md`
- 要改的是既有第三方依赖的行为，而不是自家代码 → 用 `../supply-chain-security/SKILL.md`
- 前置条件型：仓库当前构建就是红的（非本次改动引起）→ 先记录基线失败，再决定是否继续

## When to Pivot

信号与判据见 `../ops/skill-pivot-contract.md`。本技能去向：

| 触发证据 | 换到 |
|---|---|
| `git diff --stat` 显示这次要跨 **3 个以上模块**（>5 个文件）或 diff 已经 **>1000 行** | 回 `../design-slice/SKILL.md` 重切，不硬写 |
| 需求验收写不出（说不出"什么输出算做完"） | `../req-clarify/SKILL.md` |
| 连续**两次**构建 / 测试不绿，且报错读不通 | 停下，把原始报错原样贴出来，不继续盲改 |
| 发现动的是一处既有缺陷，而不是在加功能 | `../fix-bug/SKILL.md` |
| 提交前 `../skills/tests/run-ci-gates.py` 报非零，但说不清是哪道门红的 | 先分清假绿 / 环境 / 真红（假绿的坑见 journal）再决定继续，不许放宽既有检查过关 |
| 新增依赖后锁文件出现**没有**在 PR 描述里写明的版本漂移 | `../supply-chain-security/SKILL.md` |
| 新代码要补测试脚手架（仓库里还没有能跑这类测试的基建） | `../write-tests/SKILL.md` |
| 接口签名已被别处调用，改它开始牵动无关模块 | 回 `../design-slice/SKILL.md` 重切，不靠 shim 兼容层硬推 |

## 真实用例（本仓已发生，照着踩过的坑问）

- `../field-journal/2026-08-08_pr-value-triage-and-safe-integration.md` —— 集成别人的改动前，先按"文档 / 执行代码"分层，再看冲突面与改动规模：大型 PR 看着高价值，但主线已演进时只能先 rebase 再专项测试。这一刀该不该现在合，本卡与 `../pr-ship/SKILL.md` 一起判。
- `../field-journal/2026-10-13_windowsapps-python3-stub-false-green.md` —— 构建脚本里写 `python3` 时，本机拿到的是 0 字节 stub：rc=0、零输出。绿色可能什么都没跑，别拿它当"构建过了"。

## 工具链（本机实测入口）

| 工具 | 本机怎么调 | 接给谁 |
|---|---|---|
| `git diff --stat` / `git status --short` / `git log -p -- <file>` | `git` 在本机 PATH 上（`Get-Command git` 有结果，本机实测） | 先量这次的文件面与历史写法；超阈值转上面的切片分支 |
| `python`（不是 `python3`） | 本机实测在 PATH 上；`python3` 是 stub | 跑仓库门 `../skills/tests/run-ci-gates.py`（门清单在 `../skills/tests/ci-gates.json`）、`../skills/tests/verify-project-requirements.py` |
| CI 日志 | `.github/workflows/ci.yml`（路由回归 + 结构一致性 + 供应链 pin + 冒烟） | 本地过不了、CI 却绿（或反过来）时，逐 job 对齐再下结论 |
| `curl` | 系统自带 `curl.exe`（本机 `command -v curl` 有结果） | 新接口冒烟：`curl -sS -o /dev/null -w "%{http_code}" <url>` |
| `tshark` | TOOLS.md §5 登记（GUI `Wireshark` 的 CLI 孪生，禁止拉 GUI） | 新链路跑起来后抓一次帧，确认真的发出去/收回来，而不是看着代码像通 |
| `cdb` | `Resolve-ReverseToolSpec -Name 'cdb'` 现查（TOOLS.md §2 的 WinDbg 控制台版） | 新代码在 Windows 上崩在 native 层时看栈 |
| 探测层通则 | `. ../scripts/lib/Bootstrap.ps1` → `Resolve-ReverseToolSpec -Name <id>` | 上表路径先复核再调用（拿到 `Command` 就用它的完整路径，别依赖 cwd） |

## 定义完成

本技能产出算「完成」的**外部可观测**条件（不许写形容词）：

- build / typecheck / lint **通过**，贴出命令与原始输出（或明确记录「受限 + 具体原因」）
- 改动自包含：能用一句话描述这次 diff，且不含无关文件
- 复用既有 pattern：能指出复用了哪个既有文件/模块的写法
- 测试与实现同 CL；无未验证代码，或未验证处已显式标注并给出回退

## 输出契约

```
FACT:       <观察，带来源：命令 / 文件:行 / Evidence ID>
HYPOTHESIS: <可测试断言 + confidence: high|medium|low>（状态见 ../ops/binary-model.md）
QUESTION:   <当前最大不确定点>
NEXT:       <继续 | 换技能 | 停止（附成本判据）>
```

## 置信度词表

词表见 `../ops/confidence-vocabulary.md`。本技能特有判据：

- `confirmed`：build/test 命令的原始输出通过，且改动能在既有文件里指出所复用的 pattern
- `high`：本机跑通，但只在一个平台/一种输入上验证过
- `low`：代码写完但未运行；或验证依赖本机不具备的环境
- `speculative`：为跑通而假设的、未在代码或文档中被确认的既有行为
