# TOOLS.md · 工具清单与装法

> **本文件是说明书，不是索引。**
> 它只回答三个问题：某工具干什么用、哪个 skill 要它、装它要跑什么命令。
> **它不记录本机状态、不缓存路径、不判定通过与否。** 那些是 agent 自己的活。
>
> **这份表永远不完整，而且没关系。** 缺了某个工具，按 [TOOL-CHAIN.md 第 3 节](../TOOL-CHAIN.md)
> 的标准动作自己找、自己装、自己补一行就行 —— 不需要谁来维护这份清单。
> 表格格式见 [TOOL-CHAIN.md 第 4.3 节](../TOOL-CHAIN.md)。
> **★ 版本号与 🟢 标记是「写这份文档那天的承诺」，不是「现在这台机器的事实」。**
> 本文件会随机器变化而失真（实测过：标🟢 的 jadx / Wireshark 在多台机器上都不存在）。
> **任何一条在使用前都要用探测层现场复核**，查不到就是没装 —— 绝不能因为标了 🟢 就跳过探测。
> 见 [TOOL-CHAIN.md](../TOOL-CHAIN.md) 第 2 节。

---

## 0. 定位规则（每次都适用）

需要某工具时，按这三步走，**不要跳步，也不要因为第 1 步查空就断定没装**：

```powershell
# 1. 走探测层（唯一正确入口，内含四级递进 + PATH/DOTNET_ROOT 自愈）
#    探测层自定位（本文件在 skills\ 下）：相对本文件载入，不需要任何环境变量
. .\scripts\lib\Bootstrap.ps1   # 相对本文件（skillpack/skills/TOOLS.md）走，不用写死绝对路径；万一这台机器还没建好、该文件不存在，改为从仓库根起算的 skillpack\skills\scripts\lib\Bootstrap.ps1
$r = Resolve-ReverseToolSpec -Name <工具id>
$r.Available; $r.Command; $r.Via

# 2. Available=True -> 用 $r.Command 的完整路径调用（别依赖 cwd）
# 3. Available=False -> 查本文件的表找装法，装完回到第 1 步复验
```

**四条硬规矩：**

1. **不许猜路径。**
2. **不许把探测到的路径写回本文件或任何文档。** 路径只活在当次会话里 —— 换台电脑它就不成立，写下来就是埋雷。
3. **装完必须复验。** 装完不跑第 1 步，等于没装。
4. **注意：`Get-Command <id>` 返回空 != 本机缺该工具。** 2026-10-08 实测事故：工具整体迁目录后注册表已更新，
   但**已运行的进程仍持有启动时的旧 PATH 快照**（指向已删除目录），`Get-Command` 对 `diec`/`r2`/`idat`/
   `ghidraRun` 全部返回空，据此误判「本机缺工具」并停手 —— 实际工具全都在。**单条 `Get-Command` 只是四级里的
   第 2 级，必须走完探测层；环境自检见 `references/env-selfcheck.md`。**

**★ 不知道工具 id 怎么办？—— 按「能力」问，不要背清单。**

上面第 1 步是按**工具名**找。换台电脑、装的是别的同类软件、名字你根本没见过时，按名字是问不出来的。
这时改用**能力发现**（运行时扫描本机：先按规则归类，规则认不出的再跑一次 `--help` 抓关键词兜底）：

```powershell
# 按能力问本机有谁能干这件事
python C:\relab2\skillpack\skills\scripts\capability-index.py --find firmware-unpack   # 谁能解固件
python C:\relab2\skillpack\skills\scripts\capability-index.py --find portscan          # 谁能扫端口
python C:\relab2\skillpack\skills\scripts\capability-index.py --list-capabilities      # 能力词表
python C:\relab2\skillpack\skills\scripts\capability-index.py --scan                    # 换机后重建索引
```

索引落在 `%LOCALAPPDATA%\reverse-skill\capabilities\`（**机器状态，不入库**），换机后第一次调用会自动重建。
**要点：装了什么就认什么，不需要谁去登记。** 所以「新增一个工具就打个补丁」这种做法是不需要的。
（MCP 里同名能力叫 `find_capability`，见 `references/tool-registry.md` §1 的 `relab2-tools` 通道。）

### 工具根与四级定位

工具根 **`D:\Tools\`**（可用 `REVERSE_TOOL_ROOT` 覆盖）。绿色软件解压到
`D:\Tools\<分类>\<工具名>\`；pip/npm 类进各自 venv，不占这个目录。

**但光靠一条 `Get-Command` 找不到全部** —— 商业工具在子目录里、目录名也不等于工具名
（`IDA Pro 9.3\` 里才是 `idat`）。所以完整探测是**四级递进，命中即停**：

| 级 | 手段 | 命中来源标记 | 可信度 |
|---|---|---|---|
| 1 | 环境变量（同名大写变量指向全路径） | `env` | 最高 |
| 2 | `Get-Command` 查 PATH | `PATH` | 高 |
| 3 | `D:\Tools\_map.json` 的显式别名 | `map` | 高 |
| 4 | 工具根递归找同名可执行文件（浅路径优先） | `scan` | **最低，需确认身份** |

脚本里直接用探测层，不要自己写查找：

```powershell
. .\scripts\lib\Bootstrap.ps1   # 相对本文件（skillpack/skills/TOOLS.md）走，不用写死绝对路径；万一这台机器还没建好、该文件不存在，改为从仓库根起算的 skillpack\skills\scripts\lib\Bootstrap.ps1
$r = Resolve-ReverseToolSpec -Name 'idat'
$r.Available   # 有没有
$r.Command     # 在哪（用完整路径调用，不要依赖 cwd）
$r.Via         # 从哪找到的 —— scan 的要留意身份
```

> **「探测到」不等于「能执行」—— 两类必须再确认的情况（2026-10-08 实测）：**
>
> - **环境变量错位**：工具装在非默认位置时 exe 找得到但跑不起来，症状多为**静默无输出**，看着像工具坏了。
>   `IDADIR` 错位时 `idat.exe` 零输出；`DOTNET_ROOT` 错位时 ilspycmd 报「You must install .NET」。
>   **修法：探测式取值，不写死路径** —— `$env:DOTNET_ROOT = (Get-Command dotnet).Source.Replace('\dotnet.exe','')`，
>   或直接读 `Resolve-ReverseToolSpec -Name 'dotnet'` 返回的 `Command`，取它所在目录。
> - **GUI 混入**：PATH 里 GUI 版与 CLI 版并存，**PATH 级（第 2 级）命中早于 `_map.json` 级（第 3 级）**，
>   所以探测可能返回 GUI 而你毫无察觉。拿到 `Command` 后先看文件名是不是 CLI 孪生：
>   `die`→`diec`、`ida`→`idat`、`Wireshark`→`tshark`、`x64dbg`→`headless`。
>   机制是 `_map.json` 的 `deny` 段把 GUI 路径挡掉后才会回落；需要 GUI 的人工场景用
>   `x64dbg-gui` / `x32dbg-gui` 显式键。

**注意：这是约定，不是保证。** `winget` 装的进 `C:\Program Files\`，pip 的进用户 `Scripts\`，
SDK 的进 `%LOCALAPPDATA%`。**第 1 步的探测对所有工具都必做**，包括「我记得它装在 D:\Tools\」的。

工具根 `D:\Tools` 由私有仓库 `https://github.com/gthubtom1/relab-tools.git` 整包解压而来，
里面只放**网上拿不到**的那些（商业付费 / 官方下架 / 中文小众）。
本文件下面这些则是**网上免费能下**的，按装法现场安装。

### `D:\Tools\_map.json` —— 声明探测不出来的东西

有些关系**探测不出来，只能声明**：目录名 ≠ 工具名、同名多份要指定哪份、
以及**要排除的陷阱**（例：`IDA Pro 9.3\python311\python.exe` 是 IDA 自带的裸 Python，
没有 pip 包 —— 误命中它，你的脚本就跑在没有依赖的解释器上）。

```json
{
  "toolRoot": "D:\\Tools",
  "aliases": {
    "idat": { "prefer": ["IDA Pro 9.3\\idat.exe"], "note": "headless 版" },
    "adb":  { "prefer": ["android\\AndroidKiller_fix\\bin\\adb\\adb.exe"], "note": "两处都有" }
  },
  "deny": [
    { "toolIds": ["python"],
      "pathPatterns": ["*IDA_Pro*\\python*"],
      "reason": "IDA 自带的裸 Python，没有 pip 包" }
  ]
}
```

**陷阱提示：`deny` 的路径模式必须前后都带 `*`。** PowerShell 的 `-like` 要求**整串匹配**，
`*\python3*\` 匹配不到 `...\python311\python.exe`（后面还有内容）。正确写法：`*\python3*`。

**新增商业工具、或工具换了版本目录时，改 `_map.json`。** 本文件只写装法，不写路径。

### 许可分级

| 标记 | 含义 | agent 该怎么做 |
|---|---|---|
| 🟢 自动 | 免费、命令行可装 | 生成安装计划 → 报给用户 → 获批后装 |
| 🟡 需自备 | 依赖你自己已有的软件（IDA/JEB 等） | 先确认宿主软件在不在，不在就问用户 |
| 🔴 商业 | 商业许可，**绝不自动下载** | 报给用户，说明去哪买，等用户装 |

---

## 1. 运行时与基础环境（一切的前提）

| 工具 | 干什么 | 装法 | 许可 |
|---|---|---|---|
| **Python 3.12+** | 绝大多数工具链的宿主 | `winget install --source winget --accept-source-agreements --accept-package-agreements --disable-interactivity Python.Python.3.12` | 🟢 |
| **Git** | 拉源码仓 | `winget install --source winget --accept-source-agreements --accept-package-agreements --disable-interactivity Git.Git` | 🟢 |
| **Node.js 20+** | jshook / playwright / reqable 的宿主 | `winget install --source winget --accept-source-agreements --accept-package-agreements --disable-interactivity OpenJS.NodeJS.LTS` | 🟢 |
| **.NET SDK 8** | ilspycmd / dnSpy.Console / de4dot 的宿主 | `winget install --source winget --accept-source-agreements --accept-package-agreements --disable-interactivity Microsoft.DotNet.SDK.8` | 🟢 |
| **JDK 21+** | jadx / apktool / Ghidra 的宿主 | `winget install --source winget --accept-source-agreements --accept-package-agreements --disable-interactivity Microsoft.OpenJDK.21` | 🟢 |
| **Go** | pentestswarm 等 | `winget install --source winget --accept-source-agreements --accept-package-agreements --disable-interactivity GoLang.Go` | 🟢 |
| **Rust（可选）** | binwalk 等 crates 工具 | `winget install --source winget --accept-source-agreements --accept-package-agreements --disable-interactivity Rustlang.Rustup` | 🟢 |
| **MSVC Build Tools** | 编译原生测试件 | Visual Studio Build Tools + C++ 工作负载 | 🟡 |

> **`DOTNET_ROOT` 铁律**：`ilspycmd` 是 .NET tool，跑之前必须先 `(Get-Command dotnet).Source` 取其所在目录赋给 `$env:DOTNET_ROOT`，否则它找不到 runtime 直接退出。**不要在文档里写死任何盘符。**

> **★ 原生编译会死在两个隐蔽的坑（与装没装 SDK 无关，文件通常都在盘上）**：
> 某些安装里 `vcvars64.bat` 设好的 `INCLUDE` **只含 MSVC 路径、不含 Windows SDK**，`rc.exe` 也不在 `PATH`。
> 于是编译报 `fatal error C1083: 无法打开包括文件 "crtdbg.h"` 或 `LINK : fatal error LNK1158: 无法运行 "rc.exe"` ——
> 看着像 SDK 缺失，实际是**编译环境没带上 SDK 路径**。处置：vcvars 之后手工补三样，再编。
>
> ```bat
> set "SDKV=10.0.26100.0"   :: 换成你机器上实际的 SDK 版本号
> set "SDK=C:\Program Files (x86)\Windows Kits\10"
> set "PATH=%SDK%\bin\%SDKV%\x64;%PATH%"
> set "INCLUDE=%INCLUDE%;%SDK%\Include\%SDKV%\ucrt;%SDK%\Include\%SDKV%\shared;%SDK%\Include\%SDKV%\um"
> set "LIB=%LIB%;%SDK%\Lib\%SDKV%\ucrt\x64;%SDK%\Lib\%SDKV%\um\x64"
> set "DISTUTILS_USE_SDK=1" & set "MSSdk=%SDKV%"
> ```
>
> 版本号从 `dir "%SDK%\Include"` 现查，别照抄。校验：`where cl` 与 `where rc.exe` 都要有结果。

---

## 2. 逆向 · Windows / 原生

| 工具 | 干什么 | 谁要它 | 装法 | 许可 |
|---|---|---|---|---|
| **DIE** (`diec`) | 查壳、判文件类型、识别编译器 | re-triage, ghidra-static | GitHub DIE releases → `<工具根>\<分类>\<工具名>\` | 🟢 |
| **capa** | 能力识别（加密/网络/注入分支） | ghidra-static, malware-analysis | GitHub releases → `<工具根>\<分类>\<工具名>\`，rules 一并放 `<工具根>\<分类>\<工具名>\rules\` | 🟢 |
| **FLOSS** | 提取静态/混淆/字符串（.NET 加 `--language dotnet`） | ghidra-static, dotnet-reverse | GitHub releases → `<工具根>\<分类>\<工具名>\` | 🟢 |
| **radare2** (`r2`/`rabin2`/`rasm2`) | CLI 侦察、反汇编、patch | radare2 skill | GitHub radare2 releases → `(Resolve-ReverseToolSpec -Name 'r2').Command 所在目录\` | 🟢 |
| **7-Zip** | 解压样本、解包 | 全局 | `winget install --source winget --accept-source-agreements --accept-package-agreements --disable-interactivity 7zip.7zip` | 🟢 |
| **UPX** | UPX 加/脱壳 | re-unpack | GitHub releases → `<工具根>\<分类>\<工具名>\` | 🟢 |
| **IDA Pro** | 反编译主力 | ida-reverse | **商业**，自己买 | 🔴 |
| **Ghidra** | 开源反编译主力（无 IDA 时主入口） | ghidra-reverse | GitHub releases → `<工具根>\<分类>\<工具名>idra\`，需 JDK 21 | 🟢 |
| **x64dbg** | Windows 动态调试 | ghidra-static, re-dynamic | GitHub snapshots → `<工具根>\<分类>\<工具名>\` | 🟢 |
| **Binary Ninja** | 商业反编译 | binary-ninja-reverse | **商业** | 🔴 |
| **WinDbg (`cdb`)** | crash dump 分析 | ghidra-static | Windows SDK Debugging Tools | 🟢 |
| **pe-sieve** | 注入/inline hook 扫描 | vuln-audit, malware-analysis | GitHub releases → `<工具根>\<分类>\<工具名>\` | 🟢 |

### GUI / CLI 孪生对照（**拉错会挂死**）

GUI 程序弹窗等输入、零 stdout、进程永不退出。**agent 不得经 bash 拉起 GUI**，必须换孪生：

| GUI 版 | agent 只能用 |
|---|---|
| `die.exe` | **`diec.exe`** `-d -e -j <file>` |
| `Wireshark.exe` | **`tshark.exe`** |
| `ida.exe` / `ida64.exe` | **`idat.exe`**（headless）或 Ghidra `analyzeHeadless` |
| `x64dbg.exe` | **控制台 headless 版** 或走 x64dbg MCP |
| `dnSpy.exe` | **`dnSpy.Console.exe`** |
| `radare2 -g` | `-g` 属 GUI，**禁用** |

无 CLI 孪生的（**PE-bear、Scylla、010 Editor、JEB**）：只能人工在桌面侧操作，agent 不得拉起。

> ★ **工具参数的唯一事实源是 `skills/config/tool-recipes.json`**：本文件与各技能卡里的命令示例（如 `diec` 用 `-d -e -j`、`capa` 必须带 `-q`）若与它不一致，**一律以配方为准**；用 `python skills/tests/test-tool-recipes.py --list` 列出全部已登记配方（去掉 `--list` 会把每条真跑一遍）。

---

## 3. 逆向 · .NET

| 工具 | 干什么 | 装法 | 许可 |
|---|---|---|---|
| **ilspycmd** | .NET 反编译主通道 | `dotnet tool install -g ilspycmd --version 9.1.0.7988`（**锁版本，见下**） | 🟢 |
| **dnSpyEx** | IL 级调试/补丁 | GitHub dnSpyEx releases → `<工具根>\<分类>\<工具名>\`（含 `dnSpy.Console.exe`） | 🟢 |
| **de4dot-cex** | .NET 脱混淆 | GitHub de4dot-cex → `<工具根>\<分类>\<工具名>\` | 🟢 |

> **★ ilspycmd 必须锁版本**：最新版（11.x）的 NuGet 包里**只有 `tools\net10.0\`**，需要 .NET 10。
> 装在 .NET 8 上会报 `工具的 NuGet 包中的设置文件无效: 在包中找不到设置文件 "DotnetToolSettings.xml"` ——
> **这个报错长得像下载损坏，其实是目标框架不匹配**，照着「清 NuGet 缓存重装」方向排查会白费时间。
> 装之前先 `dotnet --version` 看 SDK 几，再对照包里的 `tools\net*.0\` 目录。升到 .NET 10 之前一直用 9.1。

> **IL 模式铁律**：`dnSpy.Console` 在 `--il` 模式下**不支持 `-o`**（会抛异常）。必须用 `--md <token>` 输出到标准输出。

---

## 4. 逆向 · APK / Android

| 工具 | 干什么 | 装法 | 许可 |
|---|---|---|---|
| **jadx** | DEX→Java，APK 反编译第一源 | GitHub jadx releases → `<工具根>\<分类>\<工具名>\` | 🟢 |
| **apktool** | 资源完整还原 + 回编译 | GitHub Apktool jar + `apktool.bat` 包装 → `<工具根>\<分类>\<工具名>\`（本机登记用的是 `android\AndroidKiller_fix\bin\apktool\` 那份，已登记进 `_map.json`） | 🟢 |
| **Android SDK platform-tools** (`adb`) | 装机/驱动/截图 | `winget install ... Google.PlatformTools`，或 `sdkmanager "platform-tools"`。★ 见 §4.3 六个 adb 抢端口 | 🟢 |
| **scrcpy** | 投屏 + 自带能用的 adb | `winget install --id Genymobile.scrcpy --source winget` | 🟢 |
| **bundletool** | AAB/APKS 处理（分析 .apk 用不到） | jar + wrapper → `<工具根>\<分类>\<工具名>\`，见 §4.2 | 🟢 |
| **emulator** | 模拟器（**本包不建议**，见 §4.1） | `sdkmanager "emulator"` + `system-images;android-34;google_apis;x86_64` | 🟢 |
| **apksigner / zipalign** | 重签名 / 对齐 | 随 Android SDK build-tools，`sdkmanager "build-tools;35.0.0"` | 🟢 |
| **apkanalyzer / aapt2** | 官方 smali 反汇编、资源解析 | 随 SDK cmdline-tools / build-tools | 🟢 |
| **frida-tools** (`frida` / `frida-ps`) | 动态插桩 | `pip install frida-tools` | 🟢 |
| **objection** | Frida 自动化 | `pip install objection` | 🟢 |
| **androguard** | DEX 解析（交叉验证） | `pip install androguard` | 🟢 |
| **JEB Pro** | 商用反编译 | **商业** | 🔴 |

> **frida 版本铁律**：Android 端的 `frida-server` 版本必须与本机 `frida` **严格一致**，不匹配直接连不上。
> **不手写解析器**：DEX/AXML/Manifest 事实一律用官方工具，拿不到就报「工具缺失」，不要自己撸解析器顶上。

### 4.1 Android 动态调试：真机优先，模拟器补位

2026-10-11 实测结论。**两条路都要留**：真机打主力，模拟器补上真机给不了的东西。

| 方案 | 电脑内存 | 启动 | agent 全自动 | 抗 APP 检测 | 能拿到 Android 12+ | 代价 |
|---|---|---|---|---|---|---|
| **真机（首选）** | **0**（吃手机电池） | 秒开 | 是 | **是** | 看手机 | 手机 SDK 版本不可控（见 §4.3b） |
| **第三方模拟器** | 1.5–3 GB 常驻 | 30–120 秒 | 是 | 否 | **是** | 占内存；模拟器特征易被 APP 检测 |
| 官方 AVD | 2 GB | 1–5 分钟 | 是 | 否 | 是 | 需开 WHPX（见下），且**削弱 WinDbg 内核调试** |

本包的选择：**真机 + `apk-debug.ps1` 打底，模拟器 + `emulator-lab.ps1` 兜底**（见 §4.6）。
两个工具箱的动作——`inspect`（静态拆包）/ `install`（装机）/ `log`（抓日志）/ `frida`（动态插桩）
——全是命令行、输出全是文本，不需要 agent 去看任何图形界面。

**为什么必须留模拟器这条路**：真机版本不由你决定。2026-10-11 实测：80 MB 的包
minSdk 31（要 Android 12+），手上这台是 Android 11 → `INSTALL_FAILED_OLDER_SDK`，
手动点安装 / scrcpy 拖拽**都装不上**，这不是操作问题（详见 §4.3b）。
模拟器是你**唯一能随时拿到指定 Android 版本**的手段。

> 第三方模拟器（MuMu / 雷电 / 夜神）**自带虚拟化引擎，不依赖 Windows WHPX** ——
> 这是它们相对官方 AVD 的实际优势。不要为了跑官方 AVD 去开「虚拟机平台」
> （HypervisorPlatform）：需要管理员权限 + 重启，而且**会削弱 WinDbg 内核调试能力**。
> 本包的核心工作（PC 软件调试、游戏辅助测试）会直接受损。

> 经验卡 `android-minsdk-gate-is-not-bypassable` 记了这条边界的判据与三条出路。

### 4.2 一次装齐（真机链路）

```powershell
# SDK 组件
sdkmanager --sdk_root=<工具根>\<分类>\<工具名> "platform-tools"
sdkmanager --sdk_root=<工具根>\<分类>\<工具名> "emulator"
sdkmanager --sdk_root=<工具根>\<分类>\<工具名> "system-images;android-34;google_apis;x86_64"

# 许可必须**本人**点接受（法律条款，智能体不得代按），
# 或自己跑 sdkmanager --licenses 并逐条输入 y

# scrcpy（投屏 + 自带能用的 adb）
winget install --id Genymobile.scrcpy --source winget
```

`bundletool`（只处理 AAB/APKS，分析 `.apk` 用不到）：下载 `bundletool-all-*.jar`
到 `<工具根>\<分类>\<工具名>\`，同目录放一个调 `java -jar` 的 `bundletool.bat`
（**必须 GBK 编码 + CRLF**，否则 cmd 读 UTF-8 会把中文注释当命令执行）。

### 4.3 六个 adb 抢端口（本包实测踩过，最易误诊）

```
ERROR: cannot connect to daemon at tcp:5037
adb server version (32) doesn't match this client (41); killing...
```

**症状**：设备在 `adb devices` 里**时有时无**；查是空的，过一会儿又能查到。

**真因不是驱动没装**（2026-10-11 误诊过一次）。是机器上有**多个 `adb.exe`**，
daemon 全监听 5037，版本不同就互相 `killing`。第三方助手（AndroidKiller /
搞机工具箱）常自带旧版 1.0.32。

**处置**（不要删第三方助手里的文件，会破坏它们）：

```powershell
adb kill-server
Get-Process adb -ErrorAction SilentlyContinue | Stop-Process -Force
<工具根>\<分类>\<工具名>\platform-tools\adb.exe start-server
<工具根>\<分类>\<工具名>\platform-tools\adb.exe devices -l   # 设备应稳定出现
```

`apk-debug.ps1` 启动时会自动做这件事。

### 4.3b 设备 SDK 低于 APK 的 minSdk 就装不上（2026-10-11 实测撞到）

```
adb: failed to install app.apk: Failure [INSTALL_FAILED_OLDER_SDK:
  Failed parse during installPackageLI: /data/app/vmdl1317489361.tmp/base.apk
  (at Binary XML file line #7): Requires newer sdk version #31 (current version is #30)]
```

**症状**：`install` 秒失败，报错里有个看不懂的 `#31` / `#30`。

**先对这两个数**（aapt2 拿 APK 的，adb 拿设备的）：

```powershell
& '<工具根>\<分类>\<工具名>\build-tools\34.0.0\aapt2.exe' dump badging app.apk |
  Select-String "sdkVersion"
& '<工具根>\<分类>\<工具名>\platform-tools\adb.exe' shell getprop ro.build.version.sdk
```

`minSdk 31` = 要 Android 12；设备 `30` = Android 11 —— **差一个版本，且无法绕过**。

> **这不是操作问题。** 手动点安装、scrcpy 拖拽、任何方式都装不上：
> Android 11 没有 Android 12 的运行时，系统层面就拒绝。
> scrcpy 只是屏幕镜像 + 反向控制，安装包仍然走 adb 那条路。

三条出路：

| 方案 | 代价 |
|---|---|
| 刷一台 Android 12+ 的手机 | 最干净 |
| 官方模拟器 + Android 12 镜像 | 占 2 GB 内存，启动 1-5 分钟 |
| 换一个 `minSdk ≤ 设备SDK` 的 APK 来验证动态链路 | 立刻可做，验证的是链路本身 |

> **静态逆向完全不受影响。** jadx / apktool / aapt2 全离线，
> 80 MB 的包实测 125 秒出 8179 个 `.java` + 18423 个 `.smali`，
> 不需要任何设备。

### 4.4 用起来

```powershell
# 环境自检（每项实跑，不只查「装没装」）
.\skillpack\skills\apk-reverse\scripts\apk-debug.ps1 doctor

# 静态拆包：aapt2 权限 + apktool smali + jadx 源码 + 签名
.\skillpack\skills\apk-reverse\scripts\apk-debug.ps1 inspect -Apk app.apk

# 动态
.\skillpack\skills\apk-reverse\scripts\apk-debug.ps1 install -Apk app.apk
.\skillpack\skills\apk-reverse\scripts\apk-debug.ps1 run   com.example.app
.\skillpack\skills\apk-reverse\scripts\apk-debug.ps1 log   com.example.app
.\skillpack\skills\apk-reverse\scripts\apk-debug.ps1 shot  out.png
.\skillpack\skills\apk-reverse\scripts\apk-debug.ps1 frida com.example.app -s agent.js
```

> `frida` 挂的是**运行中的进程**：先 `run` 再 `frida`，否则脚本会直接告诉你「进程不在」。

### 4.5 工具箱自带的两道回归测试（2026-10-11 加）

`apk-debug.ps1` 改过两处**不影响功能、但会静默改变行为**的地方，
所以各配了一道必须真的跑才有意义的测试：

```powershell
# 1. Adb 退出码契约：install 的成败判据
.\skillpack\skills\apk-reverse\scripts\test-adb-exit-contract.ps1

# 2. 子进程捕获死锁：为什么这些脚本不能拿 capture_output=True 跑
python .\skillpack\skills\scripts\test-subprocess-capture-deadlock.py
```

| 测什么 | 不测会怎样 |
|---|---|
| 退出码 0/1/3/255 是否如实分支 | `Adb` 曾把退出码和 stdout 混在同一返回值里，`$rc -ne 0` 恒为真 → **install 永远报「安装失败」** |
| 管道捕获会不会挂 | 拿 `capture_output=True` 跑脚本永远等不到 EOF（adb daemon 持有管道写端），表现为「CPU=0、3 线程、无子进程」的假死 |

第二道门禁的第一用例是**控制组**：它真的去跑一次管道捕获并确认它会挂。
哪天它不挂了，说明根因不是管道，**这条门禁的前提就变了，必须重写而不是继续 PASS**。

### 4.6 安卓模拟器（夜神 / 雷电 / 蓝叠 / MuMu / MEmu / 官方 AVD）

**先不装模拟器也能用** —— 本包已经把能力层预制好，装上就自动认出来，不需要改代码。

```powershell
# 1. 自检：能力链 + 厂商 CLI + 已连设备（每项实跑）
.\skillpack\skills\apk-reverse\scripts\emulator-lab.ps1 doctor

# 2. 发现：厂商 CLI + 端口扫描 + adb devices 三路合并去重
.\skillpack\skills\apk-reverse\scripts\emulator-lab.ps1 scan

# 3. 连接：把发现的实例全接进 adb
.\skillpack\skills\apk-reverse\scripts\emulator-lab.ps1 connect -Auto

# 4. 画像：装包前先对 API 级别与 ABI
.\skillpack\skills\apk-reverse\scripts\emulator-lab.ps1 profile
```

| 能力 | 命令 | 说明 |
|---|---|---|
| 实例启停 | `emulator-lab.ps1 start -Vendor mumu -Index 0` | 走厂商 CLI（MuMu/雷电/夜神/MEmu）。蓝叠无官方 CLI，会明确报「需手动起」 |
| 输入注入 | `emulator-lab.ps1 tap <serial> <x> <y>` / `swipe` / `key home` / `text` | 走 `adb shell input`，任何设备通吃 |
| 截图 | `emulator-lab.ps1 shot out.png` | |
| 抓包 ①设备侧 | `emulator-lab.ps1 pcap tcpdump` | 全量包（含回环） |
| 抓包 ②PC 侧 | `emulator-lab.ps1 iflist` → `pcap dumpcap -Interface <n>` | 抓虚拟网卡，**不动设备** |
| 抓包 ③解密 | `emulator-lab.ps1 proxy on -Port 8080` + `cert install` | 改全局代理 + 装 CA，**HTTP(S) 明文** |
| 动态调试 | `emulator-lab.ps1 frida deploy -Server <路径>` / `frida check` | 自动 gzip 推 frida-server、校验版本、adb forward |

**端口表不写死**：MuMu 16384+/雷电 5555-5561/夜神 62001/MEmu 21503/蓝叠 5555+，
多开会变、版本会变、用户能自己改。脚本用「厂商 CLI 自报 + 端口扫描 + adb devices」
三路合并，任何一条命中即可。端口表与各家 CLI 语法见
[`apk-reverse/references/emulator-lab.md`](apk-reverse/references/emulator-lab.md)。

> `apk-debug.ps1` 启动时会重连常见的模拟器端点 —— `adb kill-server` 会把
> **所有 `adb connect` 过的设备**踢下线，包括模拟器（2026-10-11 实测踩到）。

### 4.7 经验卡：已沉淀的可复用规则（2026-10-11 建）

```powershell
# 动手前先查：按症状命中已沉淀的规则
python .\skillpack\skills\scripts\experience-card.py search "stderr 中断 退出码"

# 沉淀一条新经验（默认 candidate，不给证据就不能当经验消费）
python .\skillpack\skills\scripts\experience-card.py new my-rule --title "..." --symptom "..."

# 校验全部卡（晋级门 7 条 + 无秘密检查），并重建症状索引
python .\skillpack\skills\scripts\experience-card.py --today 2026-10-11 stamp
python .\skillpack\skills\scripts\experience-card.py validate
```

经验卡在 [`experience-cards/`](experience-cards/)：每张是一**条可判定的规则**
（什么条件下、做什么、怎么算成功），带 fixture 与正负 oracle。
与 `field-journal/` 的分工：**规则 vs 现场**，不合并（详见 `experience-cards/INDEX.md`）。

---

## 5. 网络 · 协议 · 抓包

| 工具 | 干什么 | 装法 | 许可 |
|---|---|---|---|
| **Wireshark/tshark** | pcap 协议分层、`--export-objects` 提取 | 官方安装包（7z 免安装）→ `<工具根>\<分类>\<工具名>\` | 🟢 |
| **Npcap** | 实时抓包驱动 | Wireshark 安装器内一并装，需管理员 | 🟢 |
| **mitmproxy** | HTTPS 中间人、addon | `pip install mitmproxy` | 🟢 |
| **Fiddler Classic/Everywhere** | Windows 侧抓包 | 官网下载 | 🟡 |
| **nmap** | 端口/服务扫描 | `winget install --source winget --accept-source-agreements --accept-package-agreements --disable-interactivity Insecure.Nmap` | 🟢 |

> **mitmproxy 根证书**：`%USERPROFILE%\.mitmproxy\mitmproxy-ca-cert.cer` —— **不要写死用户名**。
> **代理默认口**：`127.0.0.1:8080`。端口必须来自实测，不得猜。

---

## 6. 自动化 · 脚本 · 仿真

| 工具 | 干什么 | 装法 | 许可 |
|---|---|---|---|
| **angr** | 符号执行、自动探路 | `pip install angr` | 🟢 |
| **z3-solver** | SMT 约束求解 | `pip install z3-solver` | 🟢 |
| **capstone / unicorn** | 反汇编 / CPU 仿真 | `pip install capstone unicorn` | 🟢 |
| **lief** | PE/ELF 解析与打补丁 | `pip install lief` | 🟢 |
| **qiling** | OS 级仿真（含 Windows rootfs） | `pip install qiling` | 🟢 |
| **pwntools** | exp 编写、ROP | `pip install pwntools` | 🟢 |
| **frida-tools** | 见 §4 | `pip install frida-tools` | 🟢 |
| **sdenv** | jsdom 系补环境框架：伪造浏览器环境跑混淆 JS | `npm i sdenv`（需 Node ≥20.19.5 **+ node-gyp + MSVC C++ 生成工具**） | 🟢 |
| **rs-reverse** | 瑞数 VMP 纯算法逆向：`makecode` 还原动态代码 / `makecookie` 复现 cookie | `npm i -g rs-reverse`（Node ≥18） | 🟢 |
| **yara** | 规则匹配 | `winget install --source winget --accept-source-agreements --accept-package-agreements --disable-interactivity VirusTotal.YARA` | 🟢 |
| **yara-rules 库** | 通用规则集（反调试 / 加壳器 / 恶意样本 / CVE / 能力） | ★ **`yara` 不吃目录**，只能传单文件；整库靠根目录的 `*_index.yar`（内部用 `include` 串子目录）。装法：`gh api repos/Yara-Rules/rules/tarball/master > _repo.tar.gz` 后解压 —— `git clone` 在部分网络下 TLS 握手会被切断，`urllib` 同样失败，`gh` 的 HTTP 栈可用。解压后把索引文件当 `-r` 目标 | 🟢 |
| **binwalk** | 固件提取 | `cargo install binwalk`（无 winget 无预编译） | 🟡 |

> **pip 类工具装进 venv**，别污染系统 Python。建议一个 `<工具根>\runtime\<venv 名>\`，`<工具根>\runtime\<venv 名>\Scripts\` 加 PATH。
> **angr 会把 z3-solver 钉到 4.13**（从 5.x 降级，angr 硬依赖）。两者共存无冲突，别手动升 z3。
> **sdenv 原生编译铁律**：sdenv 带 `binding.gyp`，`npm i` 会触发 `node-gyp rebuild`。Windows 上必须有
> **Python + Visual Studio 的「使用 C++ 的桌面开发」工作负载**，否则安装直接失败 —— 这是先决条件，不是装完再补。
> Node 版本按上游实测：`v20.19.5` / `v22` / `v23` / `v24` / `v25` 可用，`v21.7.3` 不支持。

---

## 7. 浏览器 / JS 自动化（MCP 通道）

| 通道 | 能力 | 装法 |
|---|---|---|
| **playwright-mcp** | 浏览器快照/点击/填表 | `npx -y playwright-mcp`，需 `npx playwright install chromium` |
| **chrome-devtools** | DOM/网络/性能/断点 | `npx -y chrome-devtools-mcp@latest` |
| **jshook** | JS Hook、CDP 调试 | `npx -y @jshookmcp/jshook` |
| **reqable-mcp** | 抓包流量查询与回放 | `npx -y reqable-mcp-server`（需另装 Reqable 桌面端） |

> **MCP 通道清单不要在本文件维护。** 以宿主工具表为准：pi 用 `mcp({search:"…"})` 查，其余宿主用其原生列表。
> MCP 多为 **cold start（deferred）**，首次调用拉起 10-40 秒属正常，**不要因此退回裸开 exe**。

---

## 8. 逆向 MCP 通道（按需启停）

> **本表是"有哪几条通道、怎么起"，不是"本机注册了几条"。** 事实源 =
> `skills/scripts/register-mcp.py`（出厂 **6 条**）+ `references/tool-registry.md`（端点登记）；
> 本机注册数现查宿主 `mcp.json`（命令见 §8.1）。`idalib-mcp` 是**可选项，不在出厂 6 条里**。

| 通道 | 端点 | 启停 |
|---|---|---|
| **pyghidra-mcp** | stdio（本机 omp）或 `127.0.0.1:9111/mcp` | **按需启动，没有常驻守护**；HTTP 形态冷启 7–10s，幂等 |
| **angr-mcp** | stdio（`python -m angr.mcp`） | 宿主按会话自动拉起；走专用 `angr-mcp-venv`（别用普通 venv 的旧 angr） |
| **relab2-tools** | stdio | 宿主按会话自动拉起。把**本机工具链**给模型：`local_tools` / `run_tool` / `triage_target` / `find_capability` / `read_tool_output` |
| **rea** | stdio（经本仓桥 `skills/scripts/rea-bridge-mcp.py`） | 宿主拉起桥，后端由桥按需拉起；能力边界见 `references/rea-integration.md` |
| **idapro** | `127.0.0.1:13337` | 插件在 IDA GUI 内自动监听；**按需**，用 `ida-reverse/scripts/start.ps1` 拉起 |
| **x64dbg-mcp** | `127.0.0.1:9094`（x64）/ 9095（x32） | **按需**：插件活在被调试进程里，**必须拉 GUI x64dbg**；带 Bearer token |

> ⚠️ **`headless.exe` 起不了 x64dbg MCP。** 三组对照实测：快目标 2.1s 退出、慢目标（Sleep 60s）**同样 2.1s** 退出 ——
> command loop 无命令即自杀，`MCP listening` 到 `MCP server stopped` 只有 **2.1 秒**窗口，`-cf` 脚本也不执行。
> 动态调试一律拉 **GUI x64dbg**（插件随进程加载，9094 才监听）。

> **注册 ≠ 已监听。** HTTP 型 MCP 全是按需启动，服务未起只表现为该 server `failed`。
> **端口必须实测确认，不得猜。** 尤其 **9095 是 x32 的服务口不是控制口**，别向它发 STOP。
> **启停由 agent 自己完成**，不要要求用户手改 `mcp.json`。

### 8.1 `daily` / `full` 登记（★ 2026-10-16 更正：两模式已等价，旧的"裁剪 Schema"设计已下线）

> ⚠ **本节上一版写的是「`daily` 只留 pyghidra（20 工具）/ `full` 全 5 个（140+ 工具）」——
> 那两张表已经不成立了，两个数也都是错的。** 现行语义看 `switch-mcp.py` 源码：
> `2026-10-15：daily 与 full 已合并（懒启动代理上线后不再需要切来切去）`，
> 两者都走同一个 `merge_and_apply()`，**结果一致：把出厂 6 条通道全部登记进活跃配置**。
>
> 为什么废掉裁剪：旧版是「整份拷贝 `mcp.all.json` 覆盖 `mcp.json`」，
> 会把**只存在于活跃配置里的通道静默删掉**（本机实测被删的是 `rea`）——
> 那不是切模式，是删配置。现在改成合并语义：`mcp.all.json` 为准，
> `mcp.json` 独有的通道**一律保留**并回写进 `mcp.all.json`，两个文件不再漂移。

```powershell
.\skillpack\skills\scripts\switch-mcp.ps1 show    # 先看当前登记了哪几条（推荐第一步）
.\skillpack\skills\scripts\switch-mcp.ps1 daily   # 登记全部通道（幂等，不删任何通道）
.\skillpack\skills\scripts\switch-mcp.ps1 full    # 与 daily 等价
```

**当前登记数一律现查，不要背本节数字**：

```powershell
python -c "import json,os;p=os.path.expanduser('~/.omp/agent/mcp.json');print(list(json.load(open(p,encoding='utf-8'))['mcpServers'].keys()))"
```

全量登记时，**每次请求都要带全部通道的工具 Schema**（Token 是实打实的成本：
2026-10-11 按 5 通道口径实测 ~28,000~32,000，**6 通道后未复测 —— 引用前先重测**）。
目前**没有**脚本级开关可以少注入一部分通道；`show` 只报状态，不改配置。
切换后**要重开 agent 会话**才生效。

> **按需启停与"双模"是两件事。** §8 讲的是「MCP 服务进程要不要起」（端口成本），
> 本节讲的是「这次会话挂了几条通道的工具 Schema」（Token 成本）—— 都省，但省的不是同一份开销。
> 注意：**现在只有登记一个动作**，没有"只挂一部分"的档位；真要省 Token，得在宿主侧自己动手。

---

## 9. 什么时候该问用户

遇到下列情况，**停下来报告，不要自作主张**：

- 标 🔴 的商业工具（JEB / Binary Ninja / IDA）—— 不自动下载、不代购
- 需要管理员权限（Npcap 驱动、部分 SDK 组件）
- 装了两版以上仍失败 —— 报「装不上」，附已试命令与报错，**不要绕路猜路径**
- 工具存在但**身份可疑**（文件名对、版本资源被剥）—— 实跑一次版本输出确认后才能依赖

---

## 10. 新增工具

**判断改哪一处：**

| 工具来源 | 改哪 | 不改会怎样 |
|---|---|---|
| 网上免费能下（jadx / diec / r2…） | **只改本文件**：加一行（干什么 / 哪个 skill 要 / 装法 / 许可） | 智能体不知道有这个工具，不会去找 |
| 只能靠工具仓库（IDA / JEB / 已下架工具） | **两处都改**：文件进 `D:\Tools` 仓库 + `_map.json` 加别名 | 装上了但探测层认不出来 |
| 两者都有 | 两处都改，本文件标注「优先从工具仓库拿」 | — |

需要 MCP 通道的，再在 `references/tool-registry.md` 登记端点与依赖。

**不要**往任何文件写死本机绝对路径 —— 那正是本文件存在的理由要消灭的东西。
「目录名 → 工具名」的映射写 `D:\Tools\_map.json`，不要写这里。