---
name: reverse-skill-router
description: Routes reverse engineering, exploitation, penetration testing, malware, mobile, firmware, browser automation, documentation, and security tasks to the appropriate specialist skill. Use when a task spans modules or the correct reverse-skill entrypoint is unclear.
---
# Reverse Engineering Skills Master Control

本目录收录了一系列逆向工程相关的技能模块，每个子目录是一个独立模块，内含 `SKILL.md` 描述其适用场景、工具链和工作流程。

## 第一屏 · 目标形态 → 第一个动作（直通表）

> 拿到东西先看这一屏，**先做表里的第一个动作，再谈别的**。这里只给「第一动」，不给流程；
> 走完第一动之后换不换技能、换什么，由那张卡自己的判据说话（完整决策树见
> `reverse-engineering/references/signal-to-tool-decision.md`）。

| 拿到的东西 | 第一个动作（先做这个） |
|---|---|
| Windows PE（.exe/.dll/.sys） | `diec -d -e -j` 查壳/熵/编译器 → 判 L0–L4 层次（`reverse-engineering/references/assault-entry.md`） |
| Linux ELF / .so | `file` + `readelf -h -S`（或 `rabin2 -I`）；Go/Rust 先恢复符号（`go-rust-reverse/`） |
| .NET 托管程序集 | `ilspycmd` / `dnSpy.Console` 直接反编译（`dotnet-reverse/`） |
| APK / DEX | `jadx -d out` + `apktool d`；native 逻辑再切 `.so`（`apk-reverse/`） |
| Mach-O / IPA | `file` + `otool -l`；先看 `codesign -dv`（`macos-reverse/`） |
| JS / Electron / 前端包 | 解 `asar`、在 CDP 里看 network；签名在 JS 里 → `js-reverse/` / `web-protocol-reverse/` |
| 固件镜像（.bin/.img/ROM） | `binwalk` 或 `unblob` 先解出文件系统，再谈仿真（`firmware-pentest/`） |
| 抓包（.pcap/.har/.saz） | 按域名 + 状态码 + `sign/token/auth` 过滤，先出请求清单（`protocol-reverse/` / `web-protocol-reverse/`） |
| 源码在手 | `code-audit/` 读源码；不要进二进制路线 |
| 桌面客户端（Electron/Qt/.NET GUI） | 先画信任边界表（`thick-client/`） |
| 只有网络资产（域名/IP） | 先被动侦察 + 指纹（`pentest-tools/`），再谈漏洞面 |

**工具在手边（取用优先级：MCP 通道 > CLI 孪生 > GUI）**：
`idalib-mcp`（stdio，装好即用）/ `idapro`（http `127.0.0.1:13337`，起 `<技能包根>\skills\ida-reverse\scripts\start.ps1`）/
`pyghidra-mcp`（stdio，或 http `127.0.0.1:9111`）/ `x64dbg-mcp`（http `127.0.0.1:9094`，启动命令 `mcp-status.ps1` 会打印）。
没有 MCP 时用 CLI 孪生（`idat`/`analyzeHeadless`/`r2`/`diec`…，路径走探测层 `Resolve-ReverseToolSpec -Name <id>`）；GUI 是同步阻塞的最后手段。
**只在真要用某个通道时才启动它**；只有观测到阻塞（通道 `closed` / 工具报错 / 拿不到结果）才去诊断或唤醒 —— 不做事前自检。

## 路由执行契约（点火时要跑，按顺序）

读完本文件后，不允许只回复“已读/已理解”。点火四步照下面跑（每一步都是**动作**，不是确认）：

1. `NOW`：跑平台原生 router（Windows `scripts/master-route.ps1`；Linux/macOS/Kali `scripts/master-route.sh`），从 `config/routing.json` 定 PRIMARY；疑难再读 `routing.md` 三轴附录。
2. `NOW`：平台原生 `case-init` 落地当前分析项目的 `work/<case>/scope.md` —— 记录目标、网络档、产出物（本包不设目标授权门；产物一律落调用者项目，见 `../RULES_zh.md`）。本地离线样本使用 `offline-sample` preset + explicit sample。
3. `ACT`：立即打开 PRIMARY `SKILL.md` 执行 ACTION REQUIRED。
4. `NEXT`：工具路径**当场探测本机** —— 唯一入口是探测层。先按仓内相对路径 dot-source `..\scripts\lib\Bootstrap.ps1`（即 `<技能包根>\skills\scripts\lib\Bootstrap.ps1`），然后 `Resolve-ReverseToolSpec -Name <工具id>`（`env → PATH → 别名表 → 工具根递归` 四级递进，返回 `Available`/`Command`/`Via`，调用前自动自愈 PATH 与 `DOTNET_ROOT`）。
   **当前部署在 `C:\relab2`（工具根 `D:\Tools`），但这不是约定**（2026-10-10 修正）：2026-10-10 全项目审查给 30 个入口脚本去掉了硬编码 `C:\relab2\...`，全部改成按 `$PSScriptRoot` 逐级上溯定位；`relab2-root.ps1` 也会在多个常见位置里找仓根。**所以换机可以 clone 到任何位置，命令里不要写死路径。**
   （若某台机器上相对路径找不到：设 `REVERSE_SKILL_ROOT` 指向技能包根 / 仓库根 / skills 根——探测层三种写法都认。都没有就把情况报出来问人，不许自己找地方新建一份。）
   - ⚠️ **`Get-Command <id>` 返回空 ≠ 本机缺该工具**（2026-10-08 实测事故：工具整体迁目录后注册表已更新，但 agent 进程仍持有启动时的旧 PATH 快照，`Get-Command` 对 `diec`/`r2`/`idat`/`ghidraRun` 全部返回空，agent 据此误判「本机缺工具」并直接停手，实际工具全都在）。**排除办法见 `references/env-selfcheck.md`。**
   - 只有当**四级探测全部 `Available=False`**、且已排除「PATH 快照」「环境变量错位（如 `IDADIR`/`DOTNET_ROOT` 指向死目录时 exe 静默失败）」「GUI/CLI 孪生选错」三种情况后，才允许报「本机缺该工具」。禁止伪造路径。
   - `TOOLS.md` / `.json` 只说「干什么用 / 怎么装」，**不含本机探测结果**，不得当本机事实直接用。工具定位永远以探测层返回的 `Command` 为准；**没有探测过就不要拼路径**。缺工具 → 平台原生 bootstrap（仅 manifest）。
   > ⚠️ 本项目**不含 `toolreg/` 注册层**：没有 `registry.py resolve`、没有 `capabilities.json`、没有 `toolreg.ps1 build`。这些命令在本项目不存在，**不要执行**。
5. 结论用 Evidence→Finding→Path。报告/journal 是 SHOULD，除非用户要交付物。

**身份**：见 `ops/IDENTITY.md`（轻量路由包 + 工具自举 + journal；**不是** Z3r0 式平台）。

如果路由无法命中，必须先联网补充方法论并提议新增 skill，禁止硬塞到不匹配模块。

## COMMAND DISCIPLINE（命令执行纪律，与路由契约同级 MUST）

> **本节是命令纪律的唯一事实源。** 卡片（`<本仓库>/kernel/04-console/cards/guest/全能专精指引.md`）
> 只是**指向本文件**的路由指针，它不承载纪律内容、不重复本节；如两者冲突，**以本文件为准**。
> `../指引卡.md`（本包未落地） 同样只是指针。
> ⚠️ 不要再去引仓库外的旧副本（`<开发根>\hubcore\04-console\cards\guest\`）：那份 §1 写的是「必须在隔离虚拟机执行，严禁在宿主机拉起」，与本包「单机·无跨机假设」**完全相反**。
> 事故背景：2026-10-04 会话 `01a107ea` 两次无响应停顿，根因是本包 `die.exe` 漏登记导致拉起 GUI 版（弹窗、零 stdout、进程不退）。工具执行是**同步阻塞**的：命令不返回，模型不会运行、不会有任何 token 产出，终端计时器继续走。**没有模型能察觉自己的命令卡住**，因此约束必须前置到命令本身。

### 本包特有（硬门）

1. **工具路径只认本机实测值**，且**必须走探测层四级递进**（`Resolve-ReverseToolSpec`，见 ACTION REQUIRED 第 4 条）—— 单条 `Get-Command <id>` 返回空**不构成「缺工具」**，PATH 快照过期时它会对所有工具返回空（2026-10-08 实测）；装法查 `TOOLS.md`。`运行模式=GUI` 的工具**禁止经 bash 执行**，必须换成 CLI 孪生（例：`die.exe`→`diec`、`x64dbg.exe`→控制台 headless、`Wireshark.exe`→`tshark`、`ida.exe`→`idat`）或该工具的 MCP 通道；注意 PATH 里 GUI 版常与 CLI 版并存，探测可能返回 GUI，**用前先确认 `Command` 的文件名是 CLI 孪生**。找不到 CLI 孪生时（如 PE-bear、jeb-pro、scylla），该工具只能由人在桌面侧操作，MUST NOT 由 agent 拉起。
2. **`TOOLS.md` 是装法说明书（机器无关），不是路径索引**：它只说「干什么用 / 哪个 skill 要 / 装法 / 许可」，**不含本机路径，也没有生成器 —— 直接手改**。本项目不维护任何工具状态文件：工具定位是运行时探测，所以不存在「索引过期」的问题，也不存在刷新步骤。
3. **首次使用某工具前先跑该行「验证命令」列**，确认路径与版本，再进入实际调用。不得凭目录名猜可执行文件名（`die`/`diec`、`Wireshark`/`tshark` 就是同名不同物的现成教训）。
4. **大结果不进上下文**：工具输出超过约 50 KB（或 >500 行）时，先落盘再读 —— 重定向到 `work/<case>/raw/<name>.txt`（或工具自带的 `-o/--json > file`），然后用 `read` 分页取需要的段。**不要把整块 JSON / 全量扫描日志 / 反汇编全量 dump 灌进上下文**：上下文被灌满的下一站就是「忘了最初的目标」。先看摘要行（头尾 + 计数），再按需下钻。

### GitHub 访问（硬门）

**查 GitHub 上的任何东西 —— 仓库、文件、目录、提交历史、issue、PR、release、Actions 日志 —— 一律走 `gh` CLI。** 禁止用网页抓取，也禁止裸 `curl` 打 `api.github.com`。

- **本机已装且已登录**（账号 `gthubtom1`）。路径靠探测层取：`(Resolve-ReverseToolSpec -Name 'gh').Command`，**别写死**。
- **换机第一件事**：跑 `gh auth status`。不自证就 `gh auth login` —— 凭据在主人手里。登录态存在 `%APPDATA%\GitHub CLI\hosts.yml`，**不进仓库**，所以新机器必须重新登一次。
- **私有仓库只有 `gh` 拿得到**：网页对私有仓库一律 404，裸 `curl` 无 token 同样 401/404 —— **那不代表「这个仓库不存在」，不要据此下结论**。
- **网络栈更稳**：本包已有实测记录（见 `TOOLS.md` 的 yara-rules 行）—— `git clone` 在部分网络下 TLS 握手被切断、`urllib` 同样失败，而 **`gh` 的 HTTP 栈可用**。抓取远端仓库内容优先 `gh`。
- **常用动作**：
  ```
  gh repo list                                                    # 有哪些仓库（含私有）
  gh api "repos/<owner>/<repo>/git/trees/HEAD?recursive=1" --jq '.tree[] | .path'
  gh api "repos/<owner>/<repo>/contents/<path>" --jq '.content' | base64 -d > <本地文件>
  gh search code "<关键字>"                                        # 搜代码
  gh pr view <N> · gh issue list · gh release list · gh run view <id> --log
  ```
- ⚠️ Windows / git-bash 下 `base64 -d` 出来的正文可能带 `\r`，比对前先 `tr -d '\r'`；否则会出现「每行都不同」的假差异。

### 通用八条

4. **每条 shell 必须带 `timeout`**：取值按本包 `默认 timeout` 列（探查 30s / 分析 120s / 构建 600s）。宁可短超时后重试，不可长超时后干等。
5. **GUI / 交互式二进制禁入 bash**。已实测的替换关系：`die.exe` → `diec.exe -d -e -j <file>`；`wireshark.exe` → `tshark.exe`；`ida.exe` → `idalib-mcp` 或 `pyghidra-mcp` / `analyzeHeadless`；`x64dbg.exe` → **走 x64dbg MCP，不要用 headless**。
   > ⚠️ **`headless.exe` 不能当 x64dbg 的 CLI 孪生用**。三组对照实测：快目标 2.1s 退出、慢目标（Sleep 60s）**同样 2.1s** 退出、不带目标 0.3s —— command loop 没命令就自杀，`MCP listening` → `MCP server stopped` 中间只有 **2.1 秒**窗口，`-cf` 脚本也是空壳（不执行）。**唯一可靠通道是 MCP**：拉 GUI x64dbg（插件活在被调试进程里），再走 80 个 MCP 工具。
   **这些 CLI 孪生的真实路径一律走探测层 `Resolve-ReverseToolSpec`** —— 注意 `x64dbg-headless` 这个名字在多数机器上**不存在**，正确写法是 `Resolve-ReverseToolSpec -Name 'x64dbg'`。确需 GUI 观察才起在交互式桌面会话里，禁经管道/服务方式拉起。
6. **一条命令只做一件事**：链式 `&&`/`;`/`|` ≤ 8 段，不跨主机、不跨路径体系。Git-Bash 下 `/tmp` 实为 `C:\tmp`，与 Windows 路径混写必错。
7. **长操作后台 + 轮询**，禁止同步阻塞：大构建、批量解包、首次拉包、大批量传输、长时间分析一律后台起进程再轮询产物。
8. **快慢命令不得同批并行**：一条无界命令会扣住整轮并行调用中已完成的兄弟结果。
9. **远程通道（ssh / scp）仅在确实跨机时适用**：必带 `-o ConnectTimeout=15` 并加 `</dev/null`（bash）或 `-n`；本机单机流程不使用。
10. **动态调试在本机进行**：调试器、内存注入、驱动加载、未受控样本一律**在本机直接运行**，不需要「先搬到别处再跑」。本机若本身就是虚拟机，它自己就是隔离体 —— **不要再套一层「必须在隔离环境里执行」的判断，你就在你的工作环境里。**

### 逆向工具已知物理陷阱与避坑守则（MUST NOT 踩坑）

1. **rabin2 / radare2 多路复用陷阱（先验再用）**：
   Windows 上 `rabin2.exe` 与 `radare2.exe` 常是**同一份多路复用二进制**（`rabin2` 只是 `radare2` 的入口名）。
   正常发行版靠 `argv[0]` 分发，`rabin2 -x` 正常按 rabin2 跑；**但被打包/改名过的构建可能丢掉分发**，
   此时参数会被当 r2 脚本解析，未知样本有被直接执行的风险。
   **铁律：先验一次再用，验不过就换等价写法。**
   - **验**：`rabin2 -v` 必须回显出 **rabin2 自己的版本行**；回显不对、或命令挂住 → 不许用它。
   - **永远安全的等价写法**：文件信息 `radare2 -q -c 'iI' <文件>`、节区 `-c 'iS'`、
     导入 `-c 'ii'`、导出 `-c 'iE'`、字符串 `-c 'iz'`（或 `floss <文件>`）。
   - 本机实测（2026-10-09，radare2 6.2.0）：`rabin2 -v` 回显正确、`rabin2 -I <文件>` 未执行目标 ——
     本机可直接用 rabin2，但**换机器后仍要先跑那一步 `-v`**。
2. **x64dbg headless 管道剥除空格陷阱**：
   `x64dbg` 无头版（`headless.exe`）命令行管道会剥除传入参数中的空格，导致多参数命令解析断裂。
   **铁律**：动态调试下断点、读写内存、单步等操作，一律通过 `x64dbg MCP` (JSON-RPC) 交互，禁止经 stdin 裸塞带空格的复杂字符串命令。
3. **Ghidra analyzeHeadless 挂死陷阱**：
   Ghidra `analyzeHeadless` 必须预先创建 project 目录，若目录不存在或遇脚本错误，批处理可能会 pause 挂死。
   **铁律**：必须预先 `mkdir` 创建项目目录，且命令末尾必须加 `< nul` 重定向 stdin 防止 pause 挂死（例如 `cmd /c "analyzeHeadless.bat ... < nul"`）。优先推荐直接使用 `pyghidra-mcp`（20 工具；**端点按 `references/tool-registry.md` 里 `pyghidra-mcp` 那一行取，表里只有「传输方式 / 端点 / 前置依赖 / 备注」四列，没有 `command` 列；启动方式由本机四级探测得出，不要写死脚本名** —— 实测全仓与本机都没有 `start-ghidra-mcp.bat`）。
4. **dnSpy.Console IL 模式建工程陷阱**：
   `dnSpy.Console` 在 IL 模式下不支持 `-o`（创建工程目录），若带 `-o` 会直接报错抛异常。
   **铁律**：反编译 IL 必须使用 `--md <token>` 输出到标准输出（例如 `dnSpy.Console.exe target.dll --il --md 0x06000001`）。
5. **.NET ilspycmd 运行环境陷阱**：
   `ilspycmd.exe` 为 .NET tool，若未设置 `DOTNET_ROOT` 会因找不到 runtime 退出。
   **铁律**：调用前必须确保环境变量 `DOTNET_ROOT` 指向本机 .NET runtime 根，路径靠探测、不写死：先 `(Get-Command dotnet -ErrorAction SilentlyContinue).Source` 拿到 `dotnet.exe` 真实路径，取其所在目录作为 `DOTNET_ROOT`，再设 `$env:DOTNET_ROOT = <该目录>`。**禁止在文档或命令里写死任何绝对盘符路径（`X:\...` 形式），一律改为探测式表述或占位符。**
6. **工具「无输出 / 超时」≠「该事件没发生」（MUST NOT 当否证）**：
   Frida/调试器**静默、超时、hook 被目标自擦除抹掉**时，只能得出「**未知**」，**不能**读成「该路径未发生」。
   **铁律**：静默/超时的结论只能是 `未观测到（unobserved）`，要下"没发生"必须换一个**不依赖该工具**的独立判据复测；
   并把"哪次超时、超时多久"记进证据。同理：**命令回显 ≠ 命中**（cdb 会把命令回显写进日志）。
   （2026-10-13 实弹：Frida 4 次超时被读成"该路径未发生"、命令回显被统计成"API 命中"，两次都翻转结论。）
7. **地址/偏移类测量必须复核（MUST）**：
   运行时地址 `VA = 模块 base + RVA`，**动手前复核**（差一位 → 完全相反的结论）；二进制字段/节表偏移
   解析后**用第二种方式交叉验证**（r2 `iS` vs pefile vs 手工），单一解析器的输出不算定论。
   （2026-10-13 实弹：手算 VA 少进一位得"全局全程 NULL"、PE 节表字段偏移标错、VA→文件偏移减错。）
8. **非 ANSI 路径陷阱（工具 + 中文/空格路径）**：
   部分 CLI（`r2`/`rabin2` 等）对**含中文的路径参数**解析失败。**铁律**：case 目录名、样本别名
   尽量用 **ASCII**；必须用中文目标时，建一个 ASCII 别名/软链（junction）再喂给工具，别把中文路径直接传给 CLI。
   （2026-10-13 实弹：中文 case 目录 `assault-测试exe` 让 rabin2 解析失败，被迫另建 ASCII junction 才能开工。）

### 卡死识别（可判定信号）

**终端计时器持续上涨 + token 计数静止 = 卡在命令层，不是在推理层。** 处置：Ctrl-C 中断并改路线；此类中断让回合以 error 终止，**不会自愈**，必须由用户发「继续」恢复。本机装有 `cmd-guard` 扩展时，`/stall` 可打印当前命令、耗时、注入记录与分类处方。

## EXECUTION ENVIRONMENT（运行环境）

> 架构（2026-10-05 起）：**单机 · 无跨机假设**。你只操作自己运行所在的这一台机器，不存在宿主↔客户机的跨设备控制。
> **技能包根与工具根：当前这台机器是 `C:\relab2` 与 `D:\Tools`，但**不要**当约定写死**（2026-10-10 修正）。30 个入口脚本已改成按 `$PSScriptRoot` 上溯定位，`relab2-root.ps1` 也会在多个常见位置找仓根，换机可以 clone 到任何路径。用相对路径或 `REVERSE_SKILL_ROOT`，别拼绝对路径。
> 但**工具具体在哪个子目录**不靠声明 —— `winget` 装的进 `C:\Program Files\`、pip 的进用户 `Scripts\`、SDK 的进 `%LOCALAPPDATA\`，所以工具的**具体路径**一律用探测层现场求，不要自己拼子目录。
> 正确做法：用探测层 —— dot-source `. C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1`（配置好的机器；若不存在则从本文件往上两级找 `scripts\lib\Bootstrap.ps1`），调 `Resolve-ReverseToolSpec -Name <工具id>`，它按 `env` → `PATH` → 别名表（仓内 `scripts/lib/toolmap.default.json`，本机 `D:\Tools\_map.json` 可覆盖）→ 工具根递归 四级递进，返回 `Available` / `Command` / `Via`。
> `Via=scan` 的可信度最低（靠文件名扫出来的），用之前先实跑一次版本输出确认身份。四级说明见 `TOOLS.md` §0；MCP 通道见 `references/tool-registry.md`。

### 运行环境选择（MUST）
- 纯静态工作（反编译、脱壳识别、字符串、binary diff、脚本测试）→ 直接在本机执行。
- 动态工作（运行未受控样本、断点、内存读取、反调试对抗、驱动加载）→同样**直接在本机执行**。
- 简单 CLI（`diec` / `7z` / `tshark` 读 pcap）→ 本机直接执行。
- 不存在「分析侧 / 动态侧」之分；边界由这台机器自身保证。

### 本机运行纪律（MUST）
- 未受控未知二进制、加壳对抗、内存注入、驱动加载类目标，一律在本机运行。
- **不要要求、也不要执行「先建快照 / 还原点」**：建工作机、打快照、恢复快照是**人的活**，不是 agent 的能力（规则 4）。agent 侧代替「快照」的动作只有三条：产物先落盘并校验哈希、只从工作副本上跑样本、不改写原始样本。
- 跨设备通道（ssh / scp / 共享文件夹 / VM 控制器）已不在工作流中；工具与文件都在本机，直接用本机路径。

### 能力优先级（MUST）
**能用 MCP 用 MCP → 能用无头/CLI 用 CLI → 都不行才开 GUI 观察 → GUI 严禁经 bash 同步启动**

1. **已生效的 MCP 资产（智能体首选通道）**：
   - **ghidra / pyghidra-mcp**：提供 20 个静态分析与反编译工具（`import_binary`, `decompile_function`, `search_symbols_by_name`, `list_imports`, `gen_callgraph` 等）。**按需启动，没有常驻守护**：做 Ghidra 静态分析前先由 agent 自己拉起 —— 端点按 `references/tool-registry.md` 里 `pyghidra-mcp` 那一行取（该表四列＝传输方式 / 端点 / 前置依赖 / 备注；前置＝JDK 21+ 与 Ghidra 本体），**启动方式用四级探测现场求**（`Resolve-ReverseToolSpec -Name 'pyghidra-mcp'`；Ghidra 本体路径用 `-Name 'ghidraRun'`），冷启 7–10 s，幂等；用前按该端点探活（`STATE: READY`）再用，收尾用**同一入口**停。**不得假设某个固定盘符下的 `start-ghidra-mcp.bat` 存在。**
   - **x64dbg-mcp**：HTTP `http://127.0.0.1:9094/`，基于 Bearer Token（由环境变量 `X64DBG_MCP_TOKEN` 动态注入）。提供 80 个动态调试工具（断点、单步、寄存器、读写内存、反汇编、符号搜索、调用栈）。**服务默认不监听**：动态调试前先起 x64dbg —— 端点按 `references/tool-registry.md` 里 `x64dbg-mcp` 那一行取（四列＝传输方式 / 端点 / 前置依赖 / 备注；前置＝x64dbg + 插件 + Bearer token）；**注意 9095 是 x32 的服务口而非控制口**（`bootstrap-manifest.json` 明确 x64=9094 / x32=9095），向 9095 发指令会打到 x32 server 或无人应答。启动方式与插件位置由四级探测现场求（插件活在被调试进程里，9094 才监听），收尾用同一入口停。**不得假设某个固定盘符下的 `start-mcp.bat` 存在。**
   - **MCP 启停纪律（硬门）**：本机 HTTP 型 MCP 全是「按需启动」，注册 ≠ 已监听。启动/关闭由 agent 用上述 .bat 自行完成，**严禁要求用户手工编辑 `mcp.json`、严禁把启停动作甩给人**；服务未起仅表现为该 server `failed`，先跑对应 start 脚本并 `/mcp reconnect <server>` 再定位别的问题。
   - **idalib-mcp / idapro**：IDA Pro 无头 stdio 及 GUI 插件通道（72 个工具）。
   - **jshook / reqable-mcp / playwright-mcp / chrome-devtools**：前端与网络/浏览器分析 MCP 服务。
2. **已验证通过的 CLI / 无头工具（第二首选）**：
   - 侦察识别：`diec.exe -d -e -j <file>`（DIE CLI）、`capa.exe -r <规则路径> -j <目标>`（能力与恶意行为匹配）、`floss.exe <目标>`（提取静态/混淆/解密字符串，.NET 带 `--language dotnet`）。
   - 静态反解：`ilspycmd <dll> -p -o <outdir>`（.NET 反编译，前置 `DOTNET_ROOT`，按上文铁律由本机 `Get-Command dotnet` 探测得出）、`dnSpy.Console.exe <dll> --md <token>`（IL 检查）、`radare2.exe -q -c 'iI' <file>`（r2 CLI 分析）。
   - 动态排查：`cdb.exe -z <dump> -c "!analyze -v; q"`（WinDbg 命令行 crash dump 分析）、`pe-sieve.exe /pid <PID>`（进程注入与 inline hook 扫描）。
   - 仿真与约束求解：`python` 专精库 `angr`（符号执行）、`qiling`（OS 级仿真执行）、`z3`（Z3-solver 约束求解）、`lief`（PE/ELF 头部注入修改）、`objection`（Frida 自动化）。
3. **GUI 观察（末选，禁入 bash）**：
   - GUI（如 x64dbg GUI、PE-bear、Scylla、dnSpy GUI、Ghidra GUI）仅供人工在桌面侧交互观察，**禁止由智能体经由 bash 管道直接拉起**。

### 攻坚四阶段执行状态机（Agent Execution Pipeline）

凡进入逆向攻坚任务，必须依循以下四阶状态机推进：

- **阶段一：目标侦察与保护层排查 (Recon & Triage)**
  - 动作：调用 `diec.exe -d -e -j` 检测架构与加壳；调用 `floss.exe` 提取静态与解码字符串；调用 `capa.exe -r <rules> -j <target>` 识别加密、网络与恶意能力分支。
  - 产出：明确 Entry Point、编译器/混淆类型、加密/哈希特征与初步脱壳路线。
- **阶段二：动静反解与关键逻辑定位 (Disassembly & Logic Trace)**
  - 动作：优先调用 `pyghidra-mcp`（20 tools；**端点按 `references/tool-registry.md` 的 `pyghidra-mcp` 行取，启动方式用四级探测现场求，不要写死脚本名**；实测全仓与本机都不存在 `start-ghidra-mcp.bat` 这个文件）或 `idalib-mcp` / `idapro` 反编译关键函数；C#/.NET 目标调用 `ilspycmd` 或 `dnSpy.Console --md`；CLI 侦察调用 `radare2.exe -q -c 'iI'`。
  - 产出：定位关键校验分支、文件偏移（File Offset）、内存虚拟地址（VA）与核心调用流。
- **阶段三：动态追踪与断点取证 (Dynamic Trace & Debugging)**
  - 动作：遇强混淆或反调试，**拉起 GUI x64dbg**（`Resolve-ReverseToolSpec -Name 'x64dbg-gui'` 或本模块的按需启动脚本）配合 `x64dbg-mcp` HTTP API（80 tools）下断点抓取内存明文；使用 `cdb.exe` 分析 crash dump；调用 `pe-sieve.exe /pid <PID>` 扫描 inline hook；Frida/objection 动态插桩。
    > ⚠️ 不要用 `headless.exe`：它的 command loop 无命令即自杀，MCP 窗口只有 2.1 秒（见 §通用八条第 5 条）。
  - 产出：抓取运行时解密密钥、明文通信数据、动态导出函数与跳转判断值。
- **阶段四：仿真验证与资产固化 (Emulation & Crystallization)**
  - 动作：跨架构或复杂反分析时使用 `qiling` 框架仿真执行；约束路径分支使用 `angr` / `z3` 求解；二进制修补使用 `lief` 打补丁；算法使用 Python 独立脚本还原并对账验证。
  - 产出：在项目根目录生成标准化 `REVERSE-MAP.md`（本包未落地），沉淀函数偏移、特征码、密钥算法与复验指令。

### 端口与地址（MUST）
端口/地址 MUST 来自 Tool Registry（`references/tool-registry.md`）或实测发现，**禁止猜**。

### 输出纪律（MUST）
产物（`REVERSE-MAP.md`（本包未落地） / 分析脚本 / dump / patched 样本 / pcap / 日志）**MUST 先落盘到工作目录并校验哈希**，之后才允许清理；不得在产物落盘前删除工作目录或覆盖原始样本。
**失败分支**：落盘或哈希校验失败 → 停下报告，不许继续下一步，也不许「先清理再说」。

## 指令语义级别（RFC 2119）

- `MUST`：必须执行，违背即任务失败。
- `MUST NOT`：禁止执行，违背即安全违规。
- `SHOULD`：原则上要做，不做必须说明原因。
- `MAY`：可选动作。
## 当前模块

| 模块 | 目录 | 适用场景 |
|------|------|---------|
| **通用逆向** | `reverse-engineering/` | GDB / Frida / angr / Unicorn / Qiling / 反分析对抗 / 全语言平台逆向 / CTF 模式库 |
| **APK 逆向** | `apk-reverse/` | Android APK 解包、jadx 反编译、smali 修改、Frida Hook、重打包签名安装 |
| **.NET / C# 逆向** | `dotnet-reverse/` | 托管 PE 逆向、dnSpyEx + de4dot 脱混淆（ConfuserEx/SmartAssembly/Babel）、IL patch、Sharp* 红队工具分析、dnSpy MCP 联动 |
| **IDA Pro 逆向** | `ida-reverse/` | IDA Pro MCP HTTP 服务器（72 个工具）：反编译、反汇编、数据流追踪、交叉引用 |
| **前端 JS 逆向** | `js-reverse/` | 浏览器端签名定位、加密参数分析、运行时采样、Node 补环境复现；优先用现有 `js-reverse_*`，需要更强的浏览器/CDP/Hook 面时接入 jshookmcp，但前提是先把该 MCP server 下载/注册并启用 |
| **radare2 分析** | `radare2/` | CLI 二进制侦察、反汇编、patch：r2 / rabin2 / rasm2 / radiff2 |
| **CTF 入口** | `ctf-sandbox/` | 单 PRIMARY；下游仍在 sidecar `../CTF-Sandbox-Orchestrator/` |
| **CTF 社区适配** | `community/ctf-hub/` | 自动/头脑风暴/教学输出，最终落到 canonical CTF downstream |
| **Web 专项适配** | `community/hack-hub/` | Hack Skills 的专题知识，复用 API/渗透/AD/云等 canonical 模块 |
| **交付工作流适配** | `community/delivery/` | 全栈角色编排与验收；安全动作回到本路由 |
| **APK 能力扩展** | `community/apk-extension/` | 新版 APK capability/doctor/脚本分组，普通 APK 仍走 `R1` |
| **技术文档编写** | `docs-generator/` | 任务完成后自动生成逆向报告、渗透报告、CTF writeup、签名逆向报告 |
| **Evidence 图审查** | `case-review/` | 校验 scope、Evidence→Finding→Path 可追溯性、workitems、timeline 与 artifact hash |
| **浏览器与桌面自动化** | `browser-automation/` | 浏览器操作（Playwright）+ Windows 桌面应用操作（OpenReverse UIA/CUA）+ 网络观察 |
| **跨版本符号迁移** | `binary-diff/` | 有旧版符号迁移到新版、缺 PDB 推导、程序更新后批量迁移函数名 |
| **N-day 补丁差分→利用** | `patch-diff-exploit/` | 从厂商补丁定位漏洞点、写 PoC、N-day 武器化（与 binary-diff 分工：本 skill 偏攻击侧） |
| **RE→利用链** | `pwn-chain/` | 从逆向走到可用 exploit：栈/堆/内核 pwn、pwntools、libc-database、CTF 到真实远程的稳定化 |
| **固件渗透链** | `firmware-pentest/` | OWASP FSTM 九阶段：提取→EMBA 自动化→Firmadyne/QEMU 仿真→AFL++ fuzz→实机利用 |
| **EDR 绕过逆向** | `edr-bypass-re/` | 红队场景：逆向 EDR 的 hook 表/ETW/AMSI → 直接 syscall / Hell's Gate / 硬件断点 / call stack spoof |
| **渗透测试工具链** | `pentest-tools/` | Nmap/Nuclei/SQLMap/FFUF/Hashcat/Pentest Swarm 等 20+ 渗透工具，通过 MCP 暴露给 AI |
| **图表生成** | `diagram-generator/` | 从自然语言生成 Mermaid/Graphviz/PlantUML 图表（攻击路径图、数据流图、架构图、状态机） |
| **攻击链编排** | `attack-chain/` | 多阶段攻击路径规划与执行的总指挥；完整渗透、HW 演练、从外网打到域控等跨阶段任务从这里开始 |
| **LLM/AI 安全测试** | `llm-security/` | OWASP LLM + ASI Top 10：Prompt 注入、工具滥用、记忆投毒、Agent 劫持、系统提示词提取、**Agent 服从性工程** |
| **API 安全测试** | `api-security/` | REST/GraphQL/WebSocket 全协议：BOLA/IDOR、JWT/OAuth 攻击、10 阶段方法论 |
| **供应链安全** | `supply-chain-security/` | SBOM/SCA/CI-CD 管道：依赖扫描、容器安全、构建完整性、漏洞可达性验证 |
| **移动逆向工程** | `mobile-reverse/` | Android + iOS：Frida/Objection 动态插桩、SSL Pinning/Root/越狱检测绕过、OWASP MASTG |
| **恶意软件分析** | `malware-analysis/` | 样本分析六阶段、YARA/Sigma、反分析检测、沙箱编排 |
| **DSL 虚拟机逆向** | `reverse-engineering/dsl-vm-reverse/` | JS 自定义指令集 VM（IIFE + switch-case opcode）；风控/验证码引擎等 |
| **作战契约 ops** | `ops/` | Scope / 证据链 / 角色 / 时间线 / 身份 / skill 供应链安全 |
| **社区 skill 对照** | `references/community-security-skills.md` | 外部安全 skill 索引与借鉴规则（禁止盲装） |
| **Skill 供应链** | `ops/skill-supply-chain.md` | 外部 skill/MCP 安装门闩（AST10 精简） |
| **RE 阶段门闩** | `reverse-engineering/references/re-agent-workflow.md` | triage→static→dynamic→synthesis |
| **侦察管线** | `pentest-tools/references/recon-pipeline.md` | 流水线 + 证据门（命中≠验证） |
| **协议逆向** | `protocol-reverse/` | 自定义二进制协议 / Protobuf / gRPC / PCAP 帧布局 |
| **Ghidra 逆向** | `ghidra-reverse/` | 开源反编译、headless、Ghidra MCP（无 IDA 时主入口） |
| **Binary Ninja 逆向** | `binary-ninja-reverse/` | HLIL/MLIL/LLIL、Python API，以及可选的社区 MCP/localhost HTTP 集成 |
| **云 / 容器 / K8s** | `cloud-k8s/` | IMDS/IAM、容器逃逸面、Kubernetes RBAC |
| **Windows / AD** | `windows-ad/` | Kerberos、AD CS、BloodHound、中继与域路径 |
| **数字取证** | `digital-forensics/` | 内存/磁盘时间线、PCAP 溯源、IR 保全 |
| **代码审计 / SAST** | `code-audit/` | Semgrep/CodeQL、白盒、危险 API 与鉴权审查 |
| **威胁情报 / OSINT** | `threat-intelligence/` | 公开来源 IOC 补充、活动关联、独立核验与情报交接 |
| **威胁狩猎** | `threat-hunting/` | 假说驱动狩猎、Sigma 检测工程、蓝队验证 |
| **OT / ICS 工控** | `ot-ics/` | Purdue 分区、PLC/SCADA、被动优先评估 |
| **Wi-Fi / 无线** | `wifi-wireless/` | 无线评估、握手/PMKID、先收后发纪律 |
| **浏览器扩展逆向** | `browser-extension-reverse/` | Chrome/Firefox 扩展、MV3 worker、权限面 |
| **macOS / Mach-O** | `macos-reverse/` | 签名、ObjC/Swift、LaunchAgent、macOS 样本 |
| **厚客户端** | `thick-client/` | 桌面 C/S、本地存储、IPC、更新通道 |
| **Go / Rust 逆向** | `go-rust-reverse/` | 剥离符号 Go/Rust、pclntab、panic 字符串 |
| **硬件调试接口** | `hardware-security/` | UART/JTAG/SWD、只读提取、交接固件 |
| **数据库安全** | `database-security/` | MySQL/PG/MSSQL/Mongo/Redis 暴露与配置 |
| **邮件安全** | `email-security/` | 钓鱼拆解、SPF/DKIM/DMARC、BEC |
| **联邦身份** | `identity-federation/` | SAML/OIDC/OAuth SSO 流与错配 |
| **RF / SDR** | `radio-sdr/` | 射频研究、先收后发 |

## 统一入口

遇到逆向、CTF、抓包、前端签名、APK 改包、二进制分析类任务时，先按这个顺序进入：

1. 平台原生 router（Windows `scripts/master-route.ps1`；Linux/macOS/Kali `scripts/master-route.sh`）→ PRIMARY（`config/routing.json`）
2. 平台原生 `case-init` → `pentest-tools/templates/scope.md`
3. 打开 PRIMARY `SKILL.md`
4. 疑难时读 `routing.md`；需要本机工具路径时**走探测层**：`. ..\scripts\lib\Bootstrap.ps1`（相对本文件） → `Resolve-ReverseToolSpec -Name <工具id>`（`Get-Command` 只是其中一级，返回空不等于缺工具，见 `references/env-selfcheck.md`；`TOOLS.md` 是装法说明书，不是路径索引）

社区适配层只在 `R46`–`R49` 或 canonical 专项 wrapper 已选中后按需读取：
`skills/community/registry.json` 是 provenance/maturity/risk 目录，
`python skills/scripts/community-route.py --hint "..." --json` 只做只读二级初筛，
不会替代主路由、case 建档或 PRIMARY 技能。

## 工作思路

这些模块可以按需组合使用：

1. **拿到一个目标** → 先看文件类型，选对应的分析工具
2. **快速捡漏** → strings / `radare2.exe -q -c 'iz'` / ltrace 看看有没有直接线索
   （要用 rabin2 之前先跑 `rabin2 -v` 验一次 argv[0] 分发，理由见上文陷阱 1；
   验不过就统一用 `radare2 -q -c '...'` 的等价写法。）
3. **深入分析** → 如果需要反编译→IDA；需要动态 Hook→Frida；需要符号执行→angr
4. **一条路走不通就换一条** → 静态分析不行就动态，Java 层不行就看 so，页面观察不够就断点

## 下一步菜单模式（Next-Step Menu Pattern）

只有在 **genuine decision boundary**（存在两个或以上 materially different、evidence-supported 分支，且用户选择会改变下一动作）时，子 skill 才 `MUST` 提供 3-6 个编号选项。若下一步由 gate / Evidence 唯一决定，`MUST` 直接继续，并按 `ops/timeline-workitem.md` 只记录 `decision_delta` + `carry_forward_refs`；`MUST NOT` 为制造菜单而重新输出 unchanged route/scope/auth/context。

格式要求：
- 每个选项以数字编号（1-6 范围）
- 每个选项描述一项具体可执行的动作（不是抽象方向）
- 至少包含一个"导出报告/写 writeup"选项
- 至少包含一个"继续深入分析"或"换一种方法"选项
- 必要时包含一个"停止/暂停/询问其他问题"出口

示例：
```
## 建议下一步（选一个编号）

1. 对 sub_140001000 做深度反编译，还原算法
2. 用 Frida 动态 Hook 验证参数猜想
3. 导出当前已命名函数，生成符号迁移 YAML
4. 生成当前阶段的分析报告
5. 换 radare2 做轻量侦察对比
6. 暂停，我先确认前面的证据
```

## 目录是动态扩充的

本目录会持续增长。发现新的子目录时，读它的 `SKILL.md` 就能快速了解用途。

新增 skill 时，按 `CONTRIBUTING.md` 的标准流程操作，确保：
- 路由矩阵能正确分流
- bootstrap 系统能在获批后补齐依赖
- 新增工具已在 `TOOLS.md` 登记装法；若有孪生/无头对应关系，登记进仓内 `scripts/lib/toolmap.default.json`（机器位置不写，交给探测层现场求）

## 关联资源

- **流量抓包与代理逆向手册**: `protocol-reverse/references/traffic-proxy.md`（`mitmproxy` 证书与 8080 端点、Wireshark/Fiddler、Frida 证书绑定绕过）
- **装法说明书**: `TOOLS.md`（干什么用 / 哪个 skill 要 / 装法 / 许可。**不含本机路径**，也没有生成器 —— 直接手改）
- 本机还有 **anything-analyzer**（端口 23816）MCP 服务器，提供浏览器自动化、HTTP 捕获和 AI 分析能力
- 包根目录下的 `Readme.md`（本包未落地） 提供面向各代码 AI 客户端的通用安装与接入说明

## 按需自举

当 workflow 发现缺少工具时，不要直接报错，也不要自动安装：只生成安装计划（含准确命令及其安装/网络/服务/配置影响），获用户显式批准后才统一调用平台原生 bootstrap（`autoInstall=false`）：

Windows：
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "<skill-root>\scripts\bootstrap-reverse.ps1" -Capability @('工具名') -StartServices
```

Linux / macOS：
```bash
bash <skill-root>/scripts/bootstrap-reverse.sh 工具名 --start-services
```

Kali：
```bash
bash <package-root>/kali/scripts/bootstrap-reverse.sh 工具名 --start-services
```

支持的能力（以 `scripts/bootstrap-manifest.json` 为准）：jadx、apktool、jeb-pro、binaryninja、frida、frida-ps、idalib-mcp、pyghidra-mcp、reqable-mcp、jshookmcp、xquik-mcp、anything-analyzer、idapro、r2、rabin2、adb、agent-browser、ghidra-mcp、seclists、proxycat、burpsuite-mcp、nmap、pentestswarm、binwalk、yara、pwntools、bkcrack、dnspy、x64dbg-mcp

> JEB Pro 已登记为**手动许可安装**能力：bootstrap 只输出指引，绝不下载或规避商业许可。Reqable MCP 仅登记固定版本的官方运行时，仍需要用户自行安装 Reqable 桌面客户端。
>
> 清单中未登记的工具（如 unblob/EMBA 等）`MUST` 在 skill 文档中走手动安装步骤，禁止假装可 bootstrap。

自举完成后，工具定位仍为运行时探测，无需刷新；未披露并获批前不安装。

## 操作先例库（Precedent Files）

在执行任何逆向/渗透操作之前，按顺序 MUST 读取：

| 读序 | 文件 | 何时读 |
|------|------|--------|
| **#1** | `ops/scope-contract.md` + `case-init.ps1` | case 建档（目标/网络档/产出物）。`field-journal/precedent-auth.md` 不写 granted |
| **#2** | `field-journal/precedent-reverse.md` 或 `field-journal/precedent-pentest.md` | 按需 — AI 犹豫时才加载 |

**#1 前置，#2 懒加载。**

## 自动进化

每次完成逆向/渗透任务后，必须回写经验到 `field-journal/` 目录。详见 `../RULES.md` 的"任务完成后的硬性 Checklist"。

- 模板：`field-journal/_template.md`
- 索引：`field-journal/_index.md`
- 先例：`field-journal/precedent-auth.md` → `field-journal/precedent-reverse.md` → `field-journal/precedent-pentest.md`
- 新任务开始前先查索引和先例，复用已有经验

## 任务完成自检（声称完成前 MUST 通过）

- [ ] 我是否完成了路由三轴匹配（目标类型 + 用户意图 + 工具链）？
- [ ] 我是否在路由成功后读取了目标 skill 的 SKILL.md？
- [ ] 路由未命中时，我是否提议了新增 skill 而非强行匹配？
- [ ] 我是否走了**探测层四级递进**（`Resolve-ReverseToolSpec`）定位实际路径（而不是只跑一条 `Get-Command` 查空就报缺工具、也不是拿 `TOOLS.md` 里的装法当路径猜）？
- [ ] 我拿到的 `Command` 是 **CLI 孪生而非 GUI 版**（`diec`/`idat`/`tshark`/`headless`）？
