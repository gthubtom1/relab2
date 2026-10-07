# START-HERE · 唯一入口

> **如果你是 AI 智能体，把这份文档从头读到尾，再动手。**
> 读完你应该知道：能做什么、从哪读起、工具路径怎么查、什么不能做。

---

## ★ 如果这台电脑是新开的（环境是空的）

**第 0 步 · 先把技能包拿到本机。** 主人会给你仓库地址：

```powershell
git clone https://github.com/gthubtom1/relab2.git C:\relab2
cd C:\relab2
```

clone 完就**在这个目录下开一个新的智能体会话** —— 之后你读到的一切都在这里。

**第 1 步 · 读 [`环境初始化.md`](环境初始化.md)。** 它只给判断依据，不给固定步骤：
摸底要看什么、基础环境装什么、工具从哪来、什么时候该停下来问主人。

读完按自己的判断走，做完再回到这里正式干活。

**两个仓库**

- `https://github.com/gthubtom1/relab2.git` —— 本技能包，就是你现在 clone 的这个，一开始就要有
- `https://github.com/gthubtom1/relab-tools.git` —— 商业付费/已下架的便携工具（9 卷 7z，770 MB），装工具时才拉

---

## 0. 这是什么

一个**只含两层**的逆向工程技能包：

| 层 | 解决什么 | 入口 |
|---|---|---|
| **① 行为卡片层** | agent **怎么做事** —— 身份、纪律、输出契约 | `kernel/04-console/cards/guest/全能专精指引.md` |
| **② 能力路由层** | agent **会做什么** —— 43 个技能的方法论与工具用法 | `skillpack/skills/SKILL.md` |

---

## 1. 怎么开始干活

```text
① 读 skillpack/skills/SKILL.md          ← 主入口，含路由契约与命令纪律
② 跑 scripts/master-route.ps1 选 PRIMARY 技能
③ 打开 PRIMARY 的 SKILL.md，照它的 ACTION REQUIRED 做
④ 报告用 Evidence → Finding → Path
```

Windows：`powershell -ExecutionPolicy Bypass -File .\skillpack\skills\scripts\master-route.ps1`
Linux/macOS/Kali：`./skillpack/skills/scripts/master-route.sh`

---

## 2. 工具路径怎么查（本包唯一的路径规则）

**本包没有工具注册表。路径只能现场探测。**

```powershell
# 最省事：用探测层（env -> PATH -> D:\Tools\_map.json 别名 -> 工具根递归）
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
$r = Resolve-ReverseToolSpec -Name 'idat'
$r.Available   # 有没有
$r.Command     # 在哪（用完整路径调用，不要依赖 cwd）
$r.Via         # 从哪找到的：env / PATH / map / scan

# 只想快速问一句「装没装」：
(Get-Command <工具id> -ErrorAction SilentlyContinue).Source
```

**为什么不能只靠 `Get-Command`**：商业工具（IDA / JEB）躺在
`D:\Tools\disasm\IDA_Pro_v8.3_Portable\` 里，目录名不等于工具名，不在 PATH 上。
所以完整探测是四级递进 —— 见 `skillpack/skills/TOOLS.md` §0 的表格。

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
   - 已实测替换：`die.exe`→`diec`、`Wireshark.exe`→`tshark`、`ida.exe`→`idalib-mcp`/`pyghidra-mcp`/`analyzeHeadless`、`x64dbg.exe`→**控制台 headless**（首选）
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
- **不自动装工具**：有安装器（`skillpack\skills\scripts\bootstrap-reverse.ps1` + `bootstrap-manifest.json`），
  但装之前要先报给用户并获得同意；商业许可的工具不自动下载
- **卡片载入是「写文件」，不是「改模型」**
- 报告里的 `x/x` 必须带分母定义，未通过项逐条列出，不许用「已完成」覆盖
