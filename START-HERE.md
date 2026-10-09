# START-HERE · 唯一入口

> **如果你是 AI 智能体，把这份文档从头读到尾，再动手。**
> 读完你应该知道：能做什么、从哪读起、工具路径怎么查、什么不能做。

---

## ★ 如果这台电脑是新开的（环境是空的）

> **你是来「建设」环境的，不是来「检查」环境的。**
> 主人的期待是你自己发现缺口、自己补上，不用他提醒。
> 停下来问「要不要装 X」通常会得到「对，早该装了」—— 这说明你没做完。

**第 0 步 · 拿到技能包**

```powershell
git clone https://github.com/gthubtom1/relab2.git C:\relab2
cd C:\relab2
```

clone 完**在这个目录下开一个新的智能体会话** —— 之后读到的一切都在这里。

**第 1 步 · 读 [`环境建设.md`](环境建设.md) ★ 这是你最重要的一份文档**

它包含：
- §0 你要做的事（主人的工作模式：不主动提醒，要你自己补）
- §1 红线（尤其「报告后直接装」vs「停下来问」的区别）
- §3 基础环境要装什么（Python/Git/Node/.NET/JDK/7z/Go/Npcap + MinGW）
- §4 逆向工具链（免费必装 / pip venv / `_map.json` 登记 / 商业工具）
- §5 验收门（造真样本端到端，不是"工具能探测到"就算完）
- §6 **已知机器级坑**（调试器 / 脚本调用 / 样本设计，全部真机实测过）

**第 2 步 · 定位包根 + 摸底自检**

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\relab2-root.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\selfcheck.ps1
```

> 这两个脚本是**换机专用的**，不要手工重做它们已经做的事。
> 它们也是「工具明明装了、却说没有」这类**假 MISSING** 的排查入口。
> ⚠️ `selfcheck` 退出码 0 **只代表已登记的都正常，不代表该有的都有** —— 继续第 3 步。

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
| **② 能力路由层** | agent **会做什么** —— 50 个技能的方法论与工具用法 | `skillpack/skills/SKILL.md` | 是 |
| **③ 物理兜底层** | agent **卡住时有人拉它一把** —— 补 timeout、拦 GUI 二进制 | `extensions/pi/cmd-guard/README.md` | 否（仅 pi 宿主） |

③ 是 **pi 专有扩展**，换别的宿主就没有这层，①②照样完整可用 ——
所以行为卡片里不声称依赖它。它读本包的 `TOOL-CHAIN.md` 派生 GUI 拦截名单，
文档改了拦截自动跟着改，不用改代码。

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
powershell -NoProfile -ExecutionPolicy Bypass -Command ". 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'; Resolve-ReverseToolSpec -Name 'idat'"

# 若本会话里已经 dot-source 过，就直接调（用「不带扩展名」的工具 id）：
#   $r = Resolve-ReverseToolSpec -Name 'idat'
# $r.Available   # 有没有
# $r.Command     # 在哪（用完整路径调用，不要依赖 cwd）
# $r.Via         # 从哪找到的：env / PATH / map / scan

# 只想快速问一句「装没装」（注意：这一条只是四级里的第 2 级，返回空不等于没装，见下表）
(Get-Command <工具id> -ErrorAction SilentlyContinue).Source
```

**★ 换机必踩的坑**（都实测复现过，不是理论）：

| 现象 | 真因 | 怎么办 |
|---|---|---|
| 「在此系统上禁止运行脚本」 | 执行策略 `Restricted` | 加 `-ExecutionPolicy Bypass`，**别当成工具缺失** |
| 明明装了却报 `Available=False` | 用了 `-Name 'xxx.exe'` | 用不带扩展名的 id：`'idat'`→True，`'idat.exe'`→False |
| `Via=PATH` 指向一个陌生/废弃目录 | 第 2 级 `Get-Command` 会返回 PATH 里任何东西 | **当它不存在**，继续走第 3、4 级 |
| **`Get-Command` 对所有工具同时返回空** | **进程持有启动时的旧 PATH 快照**：工具迁过目录、注册表已更新，但**已运行的进程不会自动刷新环境** | 比对进程 PATH 与注册表 PATH；探测层已内置自愈，走 `Resolve-ReverseToolSpec` 即自动修复。**绝不能就此判定「本机缺工具」** |
| **exe 找得到却跑不起来、静默无输出** | **环境变量指向死目录**（`IDADIR`/`DOTNET_ROOT`/`JAVA_HOME`/`GHIDRA_INSTALL_DIR`） | 探测式修正：`$env:DOTNET_ROOT=(Get-Command dotnet).Source.Replace('\dotnet.exe','')` |
| **探测返回 GUI 版**（`die.exe`/`ida.exe`/`Wireshark.exe`/`x64dbg.exe`） | PATH 里 GUI 与 CLI 并存，**PATH 级命中早于 `_map.json` 级** | 确认文件名是 CLI 孪生：`diec`/`idat`/`tshark`/`headless` |
| python 命令指向的 venv 里没有 `angr`/`z3` | venv 目录进了 PATH，抢走全局 `python` | 用系统解释器绝对路径调用 |

**为什么不能只靠 `Get-Command`**：商业工具（IDA / JEB）躺在
`D:\Tools\disasm\IDA Pro 9.3\` 里，目录名不等于工具名，不在 PATH 上。
所以完整探测是四级递进 —— 见 `TOOL-CHAIN.md` 第 2 节。

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
     （慢目标 60s 也只撑 2.1s），`-cf` 脚本是空壳。x64dbg 只能用 MCP（`x64dbg-automate-mcp`），
     或人在桌面侧手开 GUI。详见 `环境建设.md` §6.7
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
  详见 `环境建设.md` §0.2 与 §门5
- **卡片载入是「写文件」，不是「改模型」**
- 报告里的 `x/x` 必须带分母定义，未通过项逐条列出，不许用「已完成」覆盖
