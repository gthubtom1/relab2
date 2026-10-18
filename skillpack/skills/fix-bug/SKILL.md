---
name: fix-bug
description: 修 bug 先复现再改、修根因不压症状，并留下先红后绿的回归测试。用于：这 bug 怎么修、测试挂了、报错怎么复现、修完又犯。
---

# 修 Bug（Fix Bug）

本技能管「从一条失败现象到一个不再复发的修复」。它不产出新功能，也不重写架构。判断的核心只有两条：动手前有没有一条可重复的失败路径；收尾时那条路径是否由红转绿。改不动就如实说卡住，不许用假修冒充修好。

## 判据（本技能的核心）

- 改代码**之前**：手里必须有一条可重复的失败路径 —— 一个测试、一条命令、一段最小脚本。复现不出来 → 先缩小输入面、隔离环境，直到能重复失败；这一步没做完就不许动生产代码。
- 现象偶尔才出现（时序/并发/缓存/GC）→ 先设法把它变成确定性失败（固定时钟、放大并发、注入次序）；确实做不到 → 记为「不可稳定复现」，按 `low` 处理并写明。
- 动手时问：改的是**根因**还是症状？以下任一都是压症状，不算修复 —— suppress 警告、对特定输入 if-else 特判、空 `try/except` 绕过、放宽断言、把测试 `skip` 掉。
- 收尾时回归测试必须**先证红再证绿** —— 修复前失败、修复后通过。只看见「现在绿了」不等于修好了（可能是你把断言删了）。
- 定位靠删减而非靠猜：注释掉一半、二分输入、加日志。能观察到「从哪一步开始不对」即定位成功。
- 同一处小问题连续纠错两次仍不对 → **停下，`/clear` 重开**，用这两轮学到的信息重写 prompt（带上失败现象 + 已排除项），不要在同一上下文里继续磨。
- 根因在依赖或上游、本地改不动 → 写「卡住 + 具体原因 + 已排除项」，**不许假修**（不要用看着能过的 patch 蒙混）。
- 修复过程中顺手看到邻近的真 bug → 单独记下另开，不在本次修复里顺手改（避免回归测试与无关改动混在一起）。
- 想改的是行为本身而非让它正确 → 那多半是需求变更，不是 bug → 转功能实现，别顺手改语义。

**可测判据（判定"修好了"之前必须过得去的四条）**

- 失败路径要在**同一进程里各跑两次**都红，才算可重复；只红过一次的先按偶发处理，别急着写修复。
- 回归测试要能指出"改回哪一行会让它重新变红"；指不出来的是装饰，不是回归测试。
- 同一条失败路径要在干净环境或另一个进程里也复现一次，才算排除"只有我这个会话里坏"。
- `git diff` 里修复的净增行数 **>50 行**且与根因说明对不上 → 停下，那多半是在顺手做别的，拆成单独一件事。

## When NOT to use（近邻负例）

- 要加的是新功能/新行为，不是修既有行为 → 用 `../implement-feature/SKILL.md`
- 要动的是结构而行为不变（重构）→ 用 `../implement-feature/SKILL.md`
- 还没确认这是 bug，只是在验证需求做没做完 → 用 `../verify-done/SKILL.md`
- 失败来自构建/依赖/环境，而不是代码逻辑 → `../ops/rebuild-gates.md`
- 失败是"这次需求本来就该长这样"，只是旧行为要改 → `../req-clarify/SKILL.md`
- 手里的失败只在别人的机器/CI 上出现，本地一条命令都复现不了 → `../supply-chain-security/SKILL.md` 先看环境与依赖差异

## When to Pivot

信号与判据见 `../ops/skill-pivot-contract.md`。本技能去向：

| 触发证据 | 换到 |
|---|---|
| 复现脚本跑 **15 分钟**还是做不出确定性失败（时序 / 并发 / 缓存 / GC） | 记为「不可稳定复现」，按 `low` 写明已排除的环境项，不硬改 |
| 同一处连续**两次**改完仍报同样的错 | `/clear` 重开，带上失败现象 + 已排除项重写，不在同一上下文里磨 |
| 缩小输入面的"改一行 → 跑一次"循环超过 **30 分钟**仍无进展 | 停手，把已缩到的边界写下，换 `../design-slice/SKILL.md` 想清楚这段到底在做什么 |
| 修好了这条测试，但需求的验收点仍对不上 | `../verify-done/SKILL.md` |
| 根因落在依赖版本漂移 / 锁文件对不上（`package-lock.json`、`go.sum`、`requirements.txt`） | `../supply-chain-security/SKILL.md` |
| 同一输入**返回**同一越权 / 注入回显，看起来是可被利用的缺陷 | `../code-audit/SKILL.md` |
| 崩溃只留下 dump，栈里地址落在没有源码的 native 二进制里 | 先 `cdb -z <dump>` / `gdb -batch -ex bt <core>` 看栈；要读懂那个二进制再 `../reverse-engineering/SKILL.md` |
| 多台主机的日志里出现同一条失败的同一种模式 | `../digital-forensics/SKILL.md` |
| 复现命令**退出**码为 0 却什么都没输出 | 先换掉占位解释器再判（本机 `python3` 是 stub，见 journal），别把"没复现出来"记成"没有这个 bug" |

## 真实用例（本仓已发生，照着踩过的坑问）

- `../field-journal/2026-10-13_windowsapps-python3-stub-false-green.md` —— 复现脚本若走 `python3`，本机命中的是 0 字节 App Execution Alias：rc=0、零输出。看起来"跑通了"，实际一行都没执行；先把解释器换成真身再谈复现。
- `../field-journal/2026-07-18_gin-juice-client-friction.md` —— Windows 自带 `curl.exe` 遇到 URL 里的 `[]` 报 `bad range in position`；复现 HTTP 面必须加 `--globoff`。命令报错不等于被测代码有问题，先分清是工具咬了自己。

## 工具链（本机实测入口）

| 工具 | 本机怎么调 | 接给谁 |
|---|---|---|
| `git bisect run <复现命令>` / `git log -p -- <file>` | `git` 在本机 PATH 上（`Get-Command git` 有结果，本机实测） | 二分定位引入点；`log -p` 看这行最近几次改动与当时意图 |
| `cdb` | `Resolve-ReverseToolSpec -Name 'cdb'` 现查（TOOLS.md §2 的 WinDbg 控制台版） | `cdb -z <dump>` 先判崩溃栈在自家代码还是第三方 dll |
| `gdb` | `Resolve-ReverseToolSpec -Name 'gdb'` 现查（本机探测有结果）；查不到才按 TOOLS.md 自装 | `gdb -batch -ex bt -ex "info registers" <bin> <core>` 看有没有可控寄存器，决定是不是内存类缺陷 |
| `curl --globoff` | 系统自带 `curl.exe`（本机 `command -v curl` 有结果） | 复现 HTTP 面失败；`--globoff` 的坑见上面那篇 journal |
| `python`（不是 `python3`） | 本机实测在 PATH 上；`python3` 是 stub | 跑最小复现脚本，或跑仓库门 `../skills/tests/verify-project-requirements.py`（仓根下即 `skillpack/skills/tests/...`） |
| 探测层通则 | `. ../scripts/lib/Bootstrap.ps1` → `Resolve-ReverseToolSpec -Name <id>` | 上表路径用前先复核（`Available` / `Command` / `Via`）；探到的路径只活在本次会话，别写回文档 |

## 定义完成

本技能产出算「完成」的**外部可观测**条件：

- 一条回归测试（或脚本），修复前失败、修复后通过 —— 两次运行的输出都在案
- 根因说明：写清「哪一行/哪个条件导致现象」，而不是「改了 XX 就好了」
- diff 里无 suppress/特判/空 catch 绕过（可逐行核对）
- 若未修好：落盘「卡住 + 原因 + 已排除项」

## 输出契约

```
FACT:       <观察，带来源：命令 / 文件:行 / Evidence ID>
HYPOTHESIS: <可测试断言 + confidence: high|medium|low>（状态见 ../ops/binary-model.md）
QUESTION:   <当前最大不确定点>
NEXT:       <继续 | 换技能 | 停止（附成本判据）>
```

## 置信度词表

词表见 `../ops/confidence-vocabulary.md`。本技能特有判据：

- `confirmed`：同一失败路径修复前红、修复后绿，各复现一次（最好在干净环境或不同进程各跑一次）
- `low`：仅从代码推断根因，未能构造出可重复的失败路径
