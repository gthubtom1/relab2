# START-HERE · 唯一入口

> **如果你是 AI 智能体，把这份文档从头读到尾，再动手。**
> 读完你应该知道：能做什么、从哪读起、工具路径怎么查、什么不能做。
>
> ## ⛔ 先记一条硬禁令：有一个目录【不许读】
>
> **`_归档-禁读-历史文档/`** —— **一个字都不要读。**
> 那是前几轮 AI 自己写的方案、施工清单、复盘、"完成状态"报告。它们描述的是**当时那个版本**的项目，
> 与现在的代码**不一致**；读了会把"已经作废的计划"当成当前事实、把"当时自称完成"当成已完成。
> 主人为这个病吃过很多次亏（"每次都说完成了，一用就出问题"）。
> 那个目录是留给**人**的存档，不是资料。权威入口只有本文件 + `环境初始化.md`。

---

## ★ 如果这台电脑是新开的（环境是空的）

> **你是来「建设」环境的，不是来「检查」环境的。**
> 主人的期待是你自己发现缺口、自己补上，不用他提醒。
> 停下来问「要不要装 X」通常会得到「对，早该装了」—— 这说明你没做完。

**第 0 步 · 拿到技能包**

```powershell
# 约定落址 C:\relab2（卡片与各手册都按它举例），但**路径可以随便定**；
# 手册里所有 `<仓根>` 都指你实际 clone 的那个目录。
git clone https://github.com/gthubtom1/relab2.git C:\relab2
cd C:\relab2
```

clone 完**在这个目录下开一个新的智能体会话** —— 之后读到的一切都在这里。

**第 0.5 步 · 一条命令问「这台机器现在能不能干活」**

```powershell
# 先看它要干什么（一个字都不改）
powershell -NoProfile -ExecutionPolicy Bypass -File .\relab2.ps1 setup -DryRun
# 真跑：仓根定位 → 环境变量 → 技能挂载（幂等，可反复跑）
powershell -NoProfile -ExecutionPolicy Bypass -File .\relab2.ps1 setup
# 一条命令报就绪度，退出码 0 = 就绪
powershell -NoProfile -ExecutionPolicy Bypass -File .\relab2.ps1 doctor
```

`doctor` 逐项报：仓根 / 环境变量 / selfcheck / **MCP 通道**（注册了几条、哪条是懒启、后端在不在监听）/ 技能挂载 /
技能卡数 / 门禁清单 / 破甲卡 / 要求门 R1–R13 / **行为门实跑**（上次什么时候跑的、过没过）/ **GitHub CLI 登录**。
**它就是「换机 = 一条命令」的那条命令。**

> ⚠️ 它只证明「**本机配置**就绪」，**不证明「能力」就绪** —— 能力只由真实验收证明。

**第 1 步 · 读 [`环境初始化.md`](环境初始化.md) ★ 这是你最重要的一份文档**

**先看它的 §11「换机适配面」** —— 那是**完整清单**（§11.1 必改 / §11.2 清旧状态 / §11.3 自动适配 /
§11.4 永远不动 / §11.5 第一天顺序 / §11.6 三个坑 / §11.7 新组件），照它过一遍再动手。
> 这里**不再列出 §11 的分组表** —— 分组的权威写法就是 §11 本身，抄一份在这里只会两边各自漂移。

其余章节是验收与排查手册：§1 四步入口链 / §2 摸底四件 / §4 工具怎么被找到 /
§5 宿主接入与 MCP / §7 验收门 / §10 路径纪律。

需要**建设**一台空机（不是适配，是从零装）→ 读 [`环境建设.md`](环境建设.md)。

**第 1.5 步 · 确认这台机器上没有「不该常驻的东西」→ 见 [`环境初始化.md`](环境初始化.md) §11.1-D**

那一条给了现成命令（**按 Action 查，不要按名字查** —— `-match 'ida'` 会误命中 Windows 自带的 License Validation）。
**应该输出空**：本包不注册任何计划任务 / 看门狗 / 开机自启；MCP 一律**按需启动**，端口平时关着是设计，不是故障。
见到遗留任务先报给主人，别自己删也别让它继续跑（它会周期性弹窗，而且指的多半是上一台机器的路径）。

**第 2 步 · 定位包根 + 摸底自检 → 见 [`环境初始化.md`](环境初始化.md) §1.2–§1.3**

`relab2-root.ps1`（定位包根）与 `selfcheck.ps1`（摸底自检）的命令与判据在那边 ——
这两个脚本是**换机专用的**，不要手工重做它们已经做的事；它们也是「工具明明装了、却说没有」这类**假 MISSING** 的排查入口。
⚠️ `selfcheck` 退出码 0 **只代表已登记的都正常，不代表该有的都有** —— 继续第 3 步。

**第 3 步 · 按 [`环境建设.md`](环境建设.md) §3-§4 把缺的装上**

装每个东西之前**先说清楚装什么、为什么、有什么副作用，然后直接装** —— 不要停下来等批准。
只有这四种情况才真停下来问：商业许可、账号登录、需要管理员且你没有、装了两条路都不通。

**第 4 步 · 按 [`环境建设.md`](环境建设.md) §5 验收**

造一个带唯一标记的测试样本，走完「查壳 → 脱壳 → 静态 → 反编译 → 动态调试 → 反反调试」，
每一步都要有外部可观测的证据。

**做完再回到这里正式干活。**

## 0. 这是什么

一个**以文档为主**的逆向工程技能包。两层是必读，第三层是给特定宿主的可选加固：

| 层 | 解决什么 | 入口 | 必需 |
|---|---|---|---|
| **① 行为卡片层** | agent **怎么做事** —— 身份、纪律、输出契约 | `kernel/04-console/cards/guest/全能专精指引.md` | 是 |
| **② 能力路由层** | agent **会做什么** —— 63 张技能卡（57 个顶层技能目录 + 6 个嵌套卡）的方法论与工具用法（★ 真值由 `skills/tests/check-readme-scale.py` 现算并写进 `README.md` §规模 的 scale 行 —— 这类数**手写必腐烂**，别在这里改数） | `skillpack/skills/SKILL.md` | 是 |
| **③ 物理兜底层** | agent **卡住时有人拉它一把** —— 补 timeout、拦 GUI 二进制 | `extensions/pi/cmd-guard/README.md` | 否（仅 pi 宿主） |

③ 是 **pi 专有扩展**，换别的宿主就没有这层，①②照样完整可用 ——
所以行为卡片里不声称依赖它。它读本包的 `TOOL-CHAIN.md` 派生 GUI 拦截名单，
文档改了拦截自动跟着改，不用改代码。

---

## 0.6 想知道"项目由哪些层组成、怎么核验" → 读 [`docs/PROJECT-MAP.md`](docs/PROJECT-MAP.md)

那是**十五层功能线路**的权威说明（入口/技能/路由/工具/MCP/门禁/工作流/换机/**知识库**/
kernel 行为层/经验卡/社区/扩展/契约/依赖），每层都给了**核验命令**。

**核验工具箱的完整清单（8 条命令 + 每条回答什么）就在那份文件的 §2** —— 本节不再抄第二份，
抄出来的第二份一定会各自漂移。

> ⚠️ `docs/_snapshots/` 里是**生成快照**（会过期，读前先重跑命令）；**现状**永远以跑命令为准。

---

## 0.5 想确认「项目是不是做完了」先看这里

**别说"已完成"——用命令核验**（这几条谁绿才算谁完成；文档里的形容词一律不算证据）：

```powershell
python skillpack/skills/tests/run-ci-gates.py          # 全量门禁：应 blocked=0 failed=0
python skillpack/skills/tests/verify-leaves.py         # 逐树杈：每片叶子都要有入口
python skillpack/skills/tests/full-simulation.py --full # 逐线路真跑（含 MCP 真起）
python skillpack/skills/tests/test-tool-recipes.py     # 工具调用配方真跑
```

剩下的边界（Linux/macOS 未实跑、vendored 内容未逐测、
GPL 分发待拍板等）全部记在 [`docs/KNOWN-BOUNDARIES.md`](docs/KNOWN-BOUNDARIES.md)。
**一条命令列全**：`.\relab2.ps1 known`（加 `-Json` 出结构化；**条数以它实际输出为准，别写死**）。

那份文档专门回答「**哪些事这个项目做不到，以及为什么**」——
是为了让接手的人（或 agent）不必反复撞同一堵墙，
也不会把「环境限制」误判成「项目没做完」。

---

## 1. 怎么开始干活

```text
① 读 skillpack/skills/SKILL.md          ← 主入口，含路由契约与命令纪律
② 跑 .\skillpack\skills\scripts\master-route.ps1 选当前阶段的技能（PRIMARY）
③ 打开 PRIMARY 的 SKILL.md，照它的 ACTION REQUIRED 做
④ **每推进到一个阶段，重新跑一遍 ②** —— 一个程序各阶段要的东西不同（有没有壳决定走脱壳还是直接静态、
   静态看不出东西就转动态），别在第一个阶段选定的技能里死磕到底
⑤ 报告用 Evidence → Finding → Path
```

Windows：`powershell -ExecutionPolicy Bypass -File .\skillpack\skills\scripts\master-route.ps1 -Hint "<任务描述>"`
Linux/macOS/Kali：`./skillpack/skills/scripts/master-route.sh`

---

## 2. 工具路径怎么查（本包唯一的路径规则）

**本包没有工具注册表。路径只能现场探测。**

```powershell
# ★ 载入探测层必须带 -ExecutionPolicy Bypass
#   （全新 Windows 默认 Get-ExecutionPolicy = Restricted，不带必被拒 —— 这不是工具缺失）
powershell -NoProfile -ExecutionPolicy Bypass -Command ". .\skillpack\skills\scripts\lib\Bootstrap.ps1; Resolve-ReverseToolSpec -Name 'idat'"

# 若本会话里已经 dot-source 过，就直接调（用「不带扩展名」的工具 id）：
#   $r = Resolve-ReverseToolSpec -Name 'idat'
# $r.Available   # 有没有
# $r.Command     # 在哪（用完整路径调用，不要依赖 cwd）
# $r.Via         # 从哪找到的：env / PATH / map / scan

# 只想快速问一句「装没装」（注意：这条只是四级探测里的第 2 级，返回空 ≠ 没装 —— 四级表见 TOOL-CHAIN.md §2）
(Get-Command <工具id> -ErrorAction SilentlyContinue).Source
```

**★ 换机必踩的坑（7 类现象 → 真因 → 处置）→ 见 [`环境初始化.md`](环境初始化.md) §2 与 §4**

那张速查表（执行策略 `Restricted` / 假 `Available=False` / `Via=PATH` 指向废弃目录 /
`Get-Command` 对所有工具同时返回空 / exe 静默无输出 / 探测返回 GUI 版 / venv 抢走 `python`）
**权威版在换机手册里**，本节不再复制第二份 —— 复制出来的第二份一定会各自漂移。

**为什么不能只靠 `Get-Command`**：商业工具（IDA / JEB）躺在
`D:\Tools\disasm\IDA Pro 9.3\` 里，目录名不等于工具名，不在 PATH 上。
所以完整探测是四级递进 —— 正本见 `TOOL-CHAIN.md` §2。

**环境自检手册**：`skillpack/skills/references/env-selfcheck.md` —— 换机、PATH 漂移、
「查不到工具」时的完整排查流程与 10 分钟自检清单。**排查前先读它，别从零试。**

**缺工具时不用问人**：照 `TOOL-CHAIN.md` 第 3 节的标准动作自己接上
（自己查 → 自己装 → 自己登记）。`TOOLS.md` 里没有，不代表不能用。

**硬规矩：**
完整版见 `kernel/04-console/cards/guest/全能专精指引.md` §4，摘要：
1. **没有单一安装根。** 约定落址 `D:\Tools\`，但 `winget` 装进 `C:\Program Files\`、
   pip 装进用户 `Scripts\`、SDK 装进 `%LOCALAPPDATA%`。**约定是约定，不是保证** ——
   探测对所有工具都必做，包括「我记得它装在 D:\Tools\」的。
2. **本项目不维护工具索引文件。** 工具定位是**运行时探测**，不落盘、不缓存——
   所以不存在「索引过期」这个问题，也不需要任何刷新步骤。
3. **不许把探测到的路径写进任何文档。** 路径只活在当次会话里。
4. **MCP 端点事实源是 `skillpack/skills/references/tool-registry.md`**。
5. **MCP 装了 ≠ 宿主知道。** 必须注册进宿主配置（`Get-PiMcpConfigPath` / `Get-ClaudeMcpConfigPath` / `Get-CodexConfigPath`）。

---

## 3. 命令执行纪律（MUST）

完整版见 `kernel/04-console/cards/guest/全能专精指引.md` §4，摘要：

1. **每条 shell 必带 timeout**：探查 30s / 分析 120s / 构建 600s。
2. **GUI / 交互式二进制禁入 bash**。这类程序弹窗等输入、零 stdout、进程永不退出 —— 同步等它 = 模型全程不出 token 且不自愈。
   - 已实测替换：`die.exe`→`diec`、`Wireshark.exe`→`tshark`、`ida.exe`→`idat64`/`pyghidra-mcp`/`analyzeHeadless`
   - ⚠️ **`x64dbg.exe` → 走 MCP，不要用 headless**：实测 headless 的 command loop 无命令即自杀
     （慢目标 60s 也只撑 2.1s），`-cf` 脚本是空壳。x64dbg 只能用 MCP（`x64dbg-mcp`）：先跑
      `x64dbg-reverse/scripts/start.ps1`（它把 headless 归一成 GUI 并**脱离父 shell** 拉起；起不来就 `exit 2`），
      失败或没有桌面会话时**才**由人在桌面侧手开 GUI。详见 `环境建设.md` §6.7
   - 无 CLI 孪生的（PE-bear、Scylla、010 Editor 等）**只能人工在桌面侧操作，agent 不得拉起**
3. **一条命令只做一件事**：链式 `&&`/`;`/`|` ≤ 8 段。
4. **长操作后台 + 轮询**，禁止同步阻塞。
5. **快慢命令不得同批并行**。
6. **动态调试在本机进行** —— 不需要「先搬到别处」。

> 卡死判据：终端计时器持续上涨 + token 计数静止 = 卡在命令层，立刻 Ctrl-C，别等。

---

## 4. 边界（如实，不美化）

- **不跨设备**：不 SSH、不连远程 MCP 端点、不碰共享文件夹
- **不管理虚拟机**：建工作机 / 打快照是人的活
- **工具装之前先报告，然后直接装**：官方免费软件直接装，不要反复停下来问。
  只有四类才需要停下来：商业许可 / 账号登录 / 需要管理员而你没有 / 装了两条路都不通。
  详见 `环境建设.md` §0.2 与 §1「R4 的正确理解」，以及 §5 的「攒问题，最后一次问完」（★ 环境建设的门号与
  `环境初始化.md` §7 的门号是**两套**，别混）。
- **卡片载入是「写文件」，不是「改模型」**
- 报告里的 `x/x` 必须带分母定义，未通过项逐条列出，不许用「已完成」覆盖
