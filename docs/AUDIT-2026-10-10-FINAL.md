# 2026-10-10 全项目终审报告

> 范围：`C:\relab2` 整个仓库（2860 个跟踪文件，skillpack 2112 + kernel 558 + _archive 120）。
> 方法：18 路子代理并行只读审查 + **每一条都由主控实跑复现**。
> 原则：**静态检查发现不了真问题，只有实跑能。** 所有"修好了"都有退出码作证。

---

## 一、这一轮最重要的发现

### 六个门禁此前全是「从未真正工作过」的状态

它们报绿，但内部从来没检查过东西：

| 门禁 | 之前的真实状态 | 根因 |
|---|---|---|
| `verify-doc-links.py` | 164 处断链看不见，一直报绿 | `ROOT` 少上溯一层，规则表 glob 全部落空 |
| `test-ci-negative-controls.py` | 6 条负控里 5 条抛 `FileNotFoundError` | 同一个 `ROOT` 错误 |
| `test-bootstrap-supply-chain.ps1` | 本机从未通过 | JSON 被 `git` 的 stderr 污染 |
| `test-client-neutral-bootstrap.ps1` | 本机从未通过 | `Set-StrictMode` 下读未定义变量会抛错 |
| `test-routing.ps1 -Quick` | 直接崩溃 | 2 条 benchmark 缺 `quick` 字段 |
| `audit-doc-code.py` | 未闭合围栏 / 大写 `.MD` / `~~~` 全逃过扫描 | 抽取器只认顶格反引号 |

**现在每一个都真在工作**，而且都有负控证明它们退化了会被抓到。

### 第二重要的是：门禁的「假绿」比「假红」危险得多

假红会被立刻发现，假绿不会。本轮抓到 6 个假绿入口，全部实测复现：

```
未闭合的 HTML 注释      -> 从开注释那行到文件末全部逃过链接审计
散文里提及 <!--         -> 被当成开注释（RESULT.md:76，162 行逃过）
异类围栏互闭合          -> ~~~ 关闭 ``` 块，整块连同语法错消失（模糊测试 9% 假绿）
textwrap.dedent 空操作  -> 块内有一行顶格就变空操作，假红
扫到 0 个文件时报绿      -> 门禁在空目录上假装通过
ci-gates 负控够不着裸 run 门禁 -> 三个门禁不在清单里
```

---

## 二、方法论：这轮学到了什么

### 1. 「读代码觉得没问题」不是证据

`setup.ps1:24` 我改过（换掉了硬编码路径），**但后来 `git checkout` 回滚时把修复一起丢了**，
两路子代理（PowerShell 代理 + 换机代理）**各自独立发现了同一个问题**。主控隔离复现：

```
把 lib/PsModulePathInit.ps1 临时改名
→ . : 无法将"C:\relab2\...PsModulePathInit.ps1"项识别为 cmdlet
→ 脚本继续跑，rc=0
```

这就是这轮要消灭的失败模式本身：**自愈静默失效 + 刷一屏红字**。

### 2. 批量替换必须逐个实跑

30 个 ps1 的路径替换，我只验了语法。实跑 28 个后发现 4 个真回归：

- `param(...)` 不是第一条语句（PowerShell 直接拒绝执行）
- 扫描根算错一层（`check-fences` 默认根变成 `C:\skillpack\skills`）
- 修复脚本误判，把自愈逻辑删了
- 批量替换的双 BOM

**语法通过 ≠ 能跑。**

### 3. 负控自己写错也会变红

我给「缩进围栏内混顶格行」写的负控期望"必须抓出"，
但那个用例的内容**本身就是合法 Python**。修好后它正确放行 → 负控 NG。
我改的是**期望值**不是判据。负控自己写错也红，这本身是负控在工作。

### 4. 门禁退化必须专门测

把 5 个门禁**故意改弱**，验证负控能不能发现：

| 注入的退化 | 负控反应 |
|---|---|
| `TRUNCATE_MSG` 改回含 `invalid \S+` | rc=1 抓到 |
| 抽取器改回只认小写 `.md` | rc=1 抓到 |
| `_acceptance` 跳过前缀改错 | rc=1 抓到 |
| StrictMode 改回不安全写法 | rc=1 抓到 |
| 负控自身 `ROOT` 改回 `parents[2]` | rc=1 抓到 |

---

## 三、修复清单（全部有实跑证据）

### 换机链路

| # | 修复 | 证据 |
|---|---|---|
| 1 | 30 个 ps1 硬编码 `C:\relab2` → `$PSScriptRoot` 逐级上溯 | 28 个逐个实跑 |
| 2 | `setup.ps1` 加 `-DryRun` | 原先一次测试调用就把 User 级变量永久改成假路径 |
| 3 | `setup.ps1` 传播 selfcheck 退出码 | 原先自检 FAIL 也打印「初始化完成」rc=0 |
| 4 | `selfcheck.ps1` 参数优先级倒置 | 环境变量压过显式参数，参数形同虚设 |
| 5 | 三个变量包进函数作用域 | 文档教用户 dot-source 进交互会话，原先会污染 |
| 6 | 工具根是「文件」时不再报「路径不存在」 | 诊断指错方向 |
| 7 | 变量隔离后 7 个依赖门禁复验 | 全部 rc=0 |

### 门禁自身

| # | 修复 | 证据 |
|---|---|---|
| 8 | `verify-doc-links` ROOT 3→4 层 + 4 个 glob 加前缀 | 断链 164 → active=0 |
| 9 | 跳过 HTML 注释块（对齐 kernel 规则 R2） | 归档的旧原文不是活引用 |
| 10 | 跳过 `_acceptance/` 证据快照 | 改掉就毁掉「补丁修好了什么」的凭据 |
| 11 | 注释判据收紧为**行首块级** | 散文里的 `<!--` 曾让 162 行逃过审计 |
| 12 | `audit-doc-code` 围栏同字符类才闭合 | 模糊测试 9% 假绿 |
| 13 | `audit-doc-code` dedent 改按围栏缩进量硬剥 | `textwrap.dedent` 公共前缀为空会变空操作 |
| 14 | 未闭合报告保留语言标记 | CI 原本打「语言=(无)」 |
| 15 | `check-fences` 扫 0 个文件时报错 | 原先在空目录上假装通过 |

### 数据与文档

| # | 修复 | 证据 |
|---|---|---|
| 16 | `link-triage.json` 341 file + 328 resolves_to 统一前缀 | 全部指向真实存在的文件 |
| 17 | `routing.json` 补 SMB/CIFS/Spnego 路由 | `cifs spnego 漏洞` 原来落 R0 |
| 18 | 根 `LICENSE` 补 GPL-3.0 改编声明 | `NOTICE` 引用它但文件不存在 |
| 19 | README/START-HERE 数字对齐 | 48→51 路由、182→199 用例、卡片 42、技能 50 |
| 20 | 修 `skillpack/README` 空安装表 | 用户被要求跑一条不存在的命令 |
| 21 | 澄清三个 GitHub 地址关系 | 本仓 / skillpack 上游 / kernel 上游 |
| 22 | `kernel/CORE.md` 3000→4000 字节 | 代码是 4000；且它引的仓内路径会让打包器拒绝产物 |
| 23 | 补 `.gitignore` 漏的 `*/.hub/`、IDA 产物、令牌 | 32 个 `.id0/.nam` 曾裸奔 |

### kernel

| # | 修复 | 证据 |
|---|---|---|
| 24 | 场景 1/2 补前置 `index` | `pack` 只读索引库，`state/` 被 gitignore；删掉索引库复跑仍绿 |
| 25 | 148 条断言接进 `ci.yml` | 此前从未被任何 job 调用 |

---

## 四、当前状态（全部当前实跑）

```
全链路门禁          19 / 19 通过
selfcheck           通过 7 / 失败 0 / 提醒 0，工具链 25 / 25
路由回归            199 / 199
自然说法基准        93 / 93
CI 负控             7 条全 PASS，baseline green
文档代码负控        25 常规 + 8 对抗，漏报 0 / 误报 0 / 绕过 0
kernel 场景套件     151 / 151（进场的 144/148）
ps1 语法            54 / 54
BOM 门禁            0 问题（含双 BOM 检查）
换机旅程            中文+空格路径全新副本：rc=0，7/0/0
pwsh 7 vs PS 5.1    输出逐行相同
工作区              干净（已提交）
```

---

## 五、诚实列出：还没解决的

### 1. 三个门禁的负控覆盖不足

`check-fences.py` / `audit-doc-code.py` / `test-audit-doc-code-negctl.py`
不在 `ci-gates.json` 的 23 个清单里，只在 `ci.yml` 以裸 `run:` 调用。
后果：`test-ci-negative-controls.py` 的 7 条负控**够不着它们**。

> 为什么没塞进清单：那个清单是 **skillpack 内部门禁**的登记，
> `script` 路径按 skillpack 根解析（`run-ci-gates.py:58`），
> 而这些脚本在仓根另一层。硬塞会破坏 resolve 语义，
> 也会让 `verify-gate-wiring` 的「清单↔workflow 对撞」失真。
> 三个脚本已有**独立**的负控（`test-audit-doc-code-negctl.py` 的 8 个对抗用例），
> 但 `check-fences.py` **一个负控都没有**。

### 2. `negctl` 的第 7 条负控不具区分度

`broken-kernel-active-link` 注入断链后门禁确实转红了，
但 `default-active` 的 `**` 兜底规则会吸收任何路径，
所以它**分不清「ROOT 修好了」和「ROOT 又坏了」**。
一个断言在两种相反状态下都成立的负控，不是负控。

### 3. 许可证方案未决（需要你拍板）

仓库含 **220 篇 GPL-3.0 改编内容**（`LING71671/open-reverselab`），
`skillpack/LICENSE` 声明 MIT。`NOTICE` 正确记录了两个来源的许可范围，
根 `LICENSE` 也已加免责声明，但**分发方案本身没定**。

| 方案 | 后果 |
|---|---|
| A 整体转 GPL-3.0 | 合法最稳，不能再以 MIT 分发 |
| B 隔离 GPL 内容 | 知识库少 220 篇 |
| C 保持现状 | 私有不对外分发技术上不触发义务 |

**当前状态是 C**，但 `plugin.json` 的 `"license": "MIT"` 仍不准确。

### 4. 覆盖不到的地方

- Linux / macOS 下的实际行为（本机只有 Windows；CI 有 ubuntu runner 但我没跑过）
- `community-raw/` 1089 个文件（占全仓 38%）逐个功能测试
- 任何真实目标上的效果
- `07-kernel-sweep/` 约 190 个一次性调试脚本的功能正确性

---

## 六、这一轮最重要的一条经验

> **门禁必须能验证门禁自己，而且要验证「门禁退化时能被抓住」。**

这轮出现 6 次「门禁覆盖不到自己」：

1. `verify-doc-links` 的规则表 globs 全落空 → 164 处断链看不见
2. `test-ci-negative-controls` 的 `ROOT` 错一层 → 5/6 条负控在崩
3. `test-p0-friction` 测一条会崩的 StrictMode 路径 → 从未通过
4. 我自己的负控写错了期望值 → NG（负控自己写错也红）
5. 三个门禁不在清单里 → 负控够不着
6. `negctl` 第 7 条负控不具区分度 → 断言在两种状态下都成立

真正抓到问题的不是这六个门禁本身，而是：
**`test-audit-doc-code-negctl.py`（33 个用例）、`test-ci-negative-controls.py`（7 条）、
以及临时写的门禁退化注入测试。**

**没有负控的门禁只是装饰。**
