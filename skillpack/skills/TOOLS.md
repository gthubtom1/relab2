# TOOLS.md · 工具清单与装法

> **本文件是说明书，不是索引。**
> 它只回答三个问题：某工具干什么用、哪个 skill 要它、装它要跑什么命令。
> **它不记录本机状态、不缓存路径、不判定通过与否。** 那些是 agent 自己的活。
>
> **这份表永远不完整，而且没关系。** 缺了某个工具，按 [TOOL-CHAIN.md 第 3 节](../TOOL-CHAIN.md)
> 的标准动作自己找、自己装、自己补一行就行 —— 不需要谁来维护这份清单。
> 表格格式见 [TOOL-CHAIN.md 第 4.3 节](../TOOL-CHAIN.md)。

---

## 0. 定位规则（每次都适用）

需要某工具时，按这三步走，**不要跳步，也不要跳过第 1 步直接装**：

```powershell
# 1. 先问操作系统「有没有、在哪」—— 这一条就够了，不需要任何注册表
(Get-Command <工具id> -ErrorAction SilentlyContinue).Source

# 2. 有值 → 直接用。没问题。
# 3. 无值 → 查本文件的表，找到装法，装完回到第 1 步复验
```

**三条硬规矩：**

1. **不许猜路径。** 没查到就是没装，不是「可能在某个地方」。
2. **不许把探测到的路径写回本文件或任何文档。** 路径只活在当次会话里 —— 换台电脑它就不成立，写下来就是埋雷。
3. **装完必须复验。** 装完不跑第 1 步，等于没装。

### 工具根与四级定位

工具根 **`D:\Tools\`**（可用 `REVERSE_TOOL_ROOT` 覆盖）。绿色软件解压到
`D:\Tools\<分类>\<工具名>\`；pip/npm 类进各自 venv，不占这个目录。

**但光靠一条 `Get-Command` 找不到全部** —— 商业工具在子目录里、目录名也不等于工具名
（`disasm\IDA_Pro_v8.3_Portable\` 里才是 `ida`）。所以完整探测是**四级递进，命中即停**：

| 级 | 手段 | 命中来源标记 | 可信度 |
|---|---|---|---|
| 1 | 环境变量（同名大写变量指向全路径） | `env` | 最高 |
| 2 | `Get-Command` 查 PATH | `PATH` | 高 |
| 3 | `D:\Tools\_map.json` 的显式别名 | `map` | 高 |
| 4 | 工具根递归找同名可执行文件（浅路径优先） | `scan` | **最低，需确认身份** |

脚本里直接用探测层，不要自己写查找：

```powershell
. C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1
$r = Resolve-ReverseToolSpec -Name 'idat'
$r.Available   # 有没有
$r.Command     # 在哪（用完整路径调用，不要依赖 cwd）
$r.Via         # 从哪找到的 —— scan 的要留意身份
```

**注意：这是约定，不是保证。** `winget` 装的进 `C:\Program Files\`，pip 的进用户 `Scripts\`，
SDK 的进 `%LOCALAPPDATA%`。**第 1 步的探测对所有工具都必做**，包括「我记得它装在 D:\Tools\」的。

工具根 `D:\Tools` 由私有仓库 `https://github.com/gthubtom1/relab-tools.git` 整包解压而来，
里面只放**网上拿不到**的那些（商业付费 / 官方下架 / 中文小众）。
本文件下面这些则是**网上免费能下**的，按装法现场安装。

### `D:\Tools\_map.json` —— 声明探测不出来的东西

有些关系**探测不出来，只能声明**：目录名 ≠ 工具名、同名多份要指定哪份、
以及**要排除的陷阱**（例：`IDA_Pro_v8.3_Portable\python311\python.exe` 是 IDA 自带的裸 Python，
没有 pip 包 —— 误命中它，你的脚本就跑在没有依赖的解释器上）。

```json
{
  "toolRoot": "D:\\Tools",
  "aliases": {
    "idat": { "prefer": ["disasm\\IDA_Pro_v8.3_Portable\\idat.exe"], "note": "headless 版" },
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

---

## 2. 逆向 · Windows / 原生

| 工具 | 干什么 | 谁要它 | 装法 | 许可 |
|---|---|---|---|---|
| **DIE** (`diec`) | 查壳、判文件类型、识别编译器 | re-triage, ghidra-static | GitHub DIE releases → `D:\Tools\die\` | 🟢 |
| **capa** | 能力识别（加密/网络/注入分支） | ghidra-static, malware-analysis | GitHub releases → `D:\Tools\capa\`，rules 一并放 `D:\Tools\capa\rules\` | 🟢 |
| **FLOSS** | 提取静态/混淆/字符串（.NET 加 `--language dotnet`） | ghidra-static, dotnet-reverse | GitHub releases → `D:\Tools\floss\` | 🟢 |
| **radare2** (`r2`/`rabin2`/`rasm2`) | CLI 侦察、反汇编、patch | radare2 skill | GitHub radare2 releases → `D:\Tools\radare2\` | 🟢 |
| **7-Zip** | 解压样本、解包 | 全局 | `winget install --source winget --accept-source-agreements --accept-package-agreements --disable-interactivity 7zip.7zip` | 🟢 |
| **UPX** | UPX 加/脱壳 | re-unpack | GitHub releases → `D:\Tools\upx\` | 🟢 |
| **IDA Pro** | 反编译主力 | ida-reverse | **商业**，自己买 | 🔴 |
| **Ghidra** | 开源反编译主力（无 IDA 时主入口） | ghidra-reverse | GitHub releases → `D:\Tools\ghidra\`，需 JDK 21 | 🟢 |
| **x64dbg** | Windows 动态调试 | ghidra-static, re-dynamic | GitHub snapshots → `D:\Tools\x64dbg\` | 🟢 |
| **Binary Ninja** | 商业反编译 | binary-ninja-reverse | **商业** | 🔴 |
| **WinDbg (`cdb`)** | crash dump 分析 | ghidra-static | Windows SDK Debugging Tools | 🟢 |
| **pe-sieve** | 注入/inline hook 扫描 | vuln-audit, malware-analysis | GitHub releases → `D:\Tools\pe-sieve\` | 🟢 |

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

---

## 3. 逆向 · .NET

| 工具 | 干什么 | 装法 | 许可 |
|---|---|---|---|
| **ilspycmd** | .NET 反编译主通道 | `dotnet tool install -g ilspycmd` | 🟢 |
| **dnSpyEx** | IL 级调试/补丁 | GitHub dnSpyEx releases → `D:\Tools\dnSpyEx\`（含 `dnSpy.Console.exe`） | 🟢 |
| **de4dot-cex** | .NET 脱混淆 | GitHub de4dot-cex → `D:\Tools\de4dot\` | 🟢 |

> **IL 模式铁律**：`dnSpy.Console` 在 `--il` 模式下**不支持 `-o`**（会抛异常）。必须用 `--md <token>` 输出到标准输出。

---

## 4. 逆向 · APK / Android

| 工具 | 干什么 | 装法 | 许可 |
|---|---|---|---|
| **jadx** | DEX→Java，APK 反编译第一源 | GitHub jadx releases → `D:\Tools\jadx\` | 🟢 |
| **apktool** | 资源完整还原 + 回编译 | GitHub Apktool jar + `apktool.bat` 包装 → `D:\Tools\apktool\` | 🟢 |
| **Android SDK platform-tools** (`adb`) | 装机/驱动/截图 | `winget install --source winget --accept-source-agreements --accept-package-agreements --disable-interactivity Google.PlatformTools` | 🟢 |
| **apksigner / zipalign** | 重签名 / 对齐 | 随 Android SDK build-tools，`sdkmanager "build-tools;35.0.0"` | 🟢 |
| **apkanalyzer / aapt2** | 官方 smali 反汇编、资源解析 | 随 SDK cmdline-tools / build-tools | 🟢 |
| **frida-tools** (`frida` / `frida-ps`) | 动态插桩 | `pip install frida-tools` | 🟢 |
| **objection** | Frida 自动化 | `pip install objection` | 🟢 |
| **androguard** | DEX 解析（交叉验证） | `pip install androguard` | 🟢 |
| **JEB Pro** | 商用反编译 | **商业** | 🔴 |

> **frida 版本铁律**：Android 端的 `frida-server` 版本必须与本机 `frida` **严格一致**，不匹配直接连不上。
> **不手写解析器**：DEX/AXML/Manifest 事实一律用官方工具，拿不到就报「工具缺失」，不要自己撸解析器顶上。

---

## 5. 网络 · 协议 · 抓包

| 工具 | 干什么 | 装法 | 许可 |
|---|---|---|---|
| **Wireshark/tshark** | pcap 协议分层、`--export-objects` 提取 | 官方安装包（7z 免安装）→ `D:\Tools\wireshark\` | 🟢 |
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
| **yara** | 规则匹配 | `winget install --source winget --accept-source-agreements --accept-package-agreements --disable-interactivity VirusTotal.YARA` | 🟢 |
| **binwalk** | 固件提取 | `cargo install binwalk`（无 winget 无预编译） | 🟡 |

> **pip 类工具装进 venv**，别污染系统 Python。建议一个 `D:\Tools\pyrev-venv\`，`D:\Tools\pyrev-venv\Scripts\` 加 PATH。
> **angr 会把 z3-solver 钉到 4.13**（从 5.x 降级，angr 硬依赖）。两者共存无冲突，别手动升 z3。

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

| 通道 | 端点 | 启停 |
|---|---|---|
| **idalib-mcp** | stdio | 装完直接注册；依赖 `IDADIR` 指向 IDA 本体 |
| **idapro** | `127.0.0.1:13337` | 插件在 IDA GUI 内自动监听 |
| **pyghidra-mcp** | `127.0.0.1:9111/mcp` | 常驻 HTTP 守护，冷启 7-10s，**按需起** |
| **x64dbg-mcp** | `127.0.0.1:9094`（x64）/ 9095（x32） | 随 x64dbg/headless 启动，**按需起**；带 Bearer token |

> **注册 ≠ 已监听。** HTTP 型 MCP 全是按需启动，服务未起只表现为该 server `failed`。
> **端口必须实测确认，不得猜。** 尤其 **9095 是 x32 的服务口不是控制口**，别向它发 STOP。
> **启停由 agent 自己完成**，不要要求用户手改 `mcp.json`。

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