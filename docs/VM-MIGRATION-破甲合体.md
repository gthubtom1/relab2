# 迁移到虚拟机 · 搬运 + 接入 + 自检清单

> 给主人手动操作。目标：把本项目搬到你的 Windows 虚拟机，**不装新软件**，用 VM 里已有的工具接进 MCP、统一定位；跑一次自检，出"真缺件清单"由主人决定装不装。
> 写作：2026-10-13。作者：小代码酱。

---

## 0. 先说清两件事（避免又走偏）

1. **红/绿灯是"环境差"，不是"代码差"**
   同一个辅助：**VM 里绿灯（连上服务器）、本机红灯（连不上，0xC000023E）**。
   → **服务器/程序都没坏，是本机环境让它不肯连**。所以**要去 VM 里分析**（VM 才是"正常环境"）。
2. **本项目本体很小**：清掉过程垃圾后 **约 510 MB**（其中 .git 22M + skillpack 38M + kernel 7M + docs 0.5M + work 实弹案 398M）。
   真正该带走的**项目本体 ≈ 68 MB**；`work/` 里是实弹抓的过程数据，**可带可不带**（VM 里重新分析会生成新的）。

---

## 1. 搬运：带什么 / 不带什么

| 带走 | 路径 | 说明 |
|---|---|---|
| ✅ **项目本体** | `C:\relab2\skillpack\` | 技能包（38M）|
| ✅ | `C:\relab2\kernel\` | 中枢卡（7M）|
| ✅ | `C:\relab2\docs\` | 文档/评估/提示词（0.5M）|
| ✅ | `C:\relab2\*.md`、`START-HERE.md` 等根文件 | |
| ✅ | `C:\relab2\.git\` | 版本库（22M）——**建议带**，VM 里也能看历史 |
| ⚠️ 可选 | `C:\relab2\测试exe.exe`、`work\assault-测试exe\` | 分析目标 + 实弹产物（398M）。**VM 里本来有那个辅助**，可只带 `测试exe.exe` 一个，产物不带 |
| ❌ 不带 | 那些已删的过程垃圾（已清，2.6G→510M）| |

**打包方式（选一个）**：
- 简单：整个 `C:\relab2` 压成 zip 拷过去（510M，可接受）；
- 干净：只压 `skillpack kernel docs *.md .git`（~68M）。

---

## 2. 放哪 / 路径怎么统一

**本项目已做过"换机自适应"**：脚本**按自身位置向上找仓根**（`$PSScriptRoot` 上溯），**不写死 `C:\relab2`**。所以：
- **放哪都行**，只要整个项目结构不变（别把 `skillpack/` 拆出来）。
- **推荐**：VM 里也放 `C:\relab2`（和本机一致，省心）。
- 若放别处（如 `D:\relab2`）——**也能跑**，脚本自适应；但要注意下面"工具根"。

**唯一需要你设的环境变量**（工具根）：
```powershell
# 本机工具根是 D:\Tools。VM 里工具装哪，就指哪。
$env:REVERSE_TOOL_ROOT = '<VM 里的工具根>'    # 若 VM 工具也放 D:\Tools 就不用改
```
探测层默认工具根就是 `D:\Tools`（见 `Bootstrap.ps1`）。**VM 里工具放哪，把 `REVERSE_TOOL_ROOT` 指过去即可。**

---

## 3. 接入：以"当前电脑上的软件"为准（不额外装）

> 原则：**只用 VM 里已有的工具，把它们接进探测层/MCP，不新装。**

### 3.1 先跑自检（关键第一步）
```powershell
cd <项目根>            # 例：C:\relab2
powershell -NoProfile -ExecutionPolicy Bypass -File .\selfcheck.ps1
```
（这是仓库根的封装入口，自动解析技能包根/工具根再调 `skillpack\skills\scripts\selfcheck-newmachine.ps1`。
若没有 `selfcheck.ps1`，直接调 `skillpack\skills\scripts\selfcheck-newmachine.ps1 -SkillRoot <仓根> -ToolRoot <工具根>`。）

它**只测不改**：不装东西、不改环境变量。会告诉你：工具根、技能包根、哪些工具**Available=False**。

### 3.2 用探测层逐个复核（唯一正确入口）
```powershell
. <仓根>\skillpack\skills\scripts\lib\Bootstrap.ps1
$r = Resolve-ReverseToolSpec -Name <工具id>    # 例：idat / r2 / cdb / tshark
$r.Available; $r.Command; $r.Via
```
`Available=True` → 用 `$r.Command` 的完整路径调用。`False` → 进第 4 节缺件清单。

### 3.3 接入 MCP（把 VM 里已有的接上）
本项目用 1 个 MCP（可扩展）：
- `pyghidra-mcp`（Ghidra 无头反编译，20 工具）。配置文件：`~/.omp/agent/mcp.json`
  ```json
  "pyghidra-mcp": {
    "command": "<VM 里的>\runtime\venv-re\Scripts\pyghidra-mcp.exe",
    "env": { "JAVA_HOME": "<VM 的 JDK>", "GHIDRA_INSTALL_DIR": "<VM 的 Ghidra 根>", "PYTHONUNBUFFERED": "1" }
  }
  ```
  **VM 里没装 pyghidra-mcp / Ghidra / JDK → 这条 MCP 就空着，不影响其他工具用。**

- 其它 MCP（`idapro` / `ida-pro-mcp` / `angr-mcp` / `x64dbg-automate-mcp`）**按需接**：VM 里装了哪个就配哪个，**不装的就不配**。

---

## 4. 缺件清单（"真的必须装"才列，主人决定）

> **原则**：只有"某个正在做的任务真的需要、且 VM 里探测为 False"的，才列。
> 下表是**本机有、分析这个游戏辅助会真正用到**的；VM 里缺哪个，主人再决定装不装。

| 用途 | 工具 | 为什么需要（针对本目标）| 装法提示 |
|---|---|---|---|
| **抓包（最高优先）** | `tshark`（Wireshark 命令行）| 查"红灯=连不上哪个服务器"——**这是当前第一要务** | 装 Wireshark（含 Npcap）|
| 网络层 | Npcap 服务 | tshark 抓包依赖 | 随 Wireshark 装 |
| 动态调试 | `cdb`（WinDbg 命令行）| 追 UAF / 断点 | winget Microsoft.WinDbg |
| 静态反汇编 | `r2`/`rabin2`（radare2）| 常规反汇编/节区/字符串 | 解压 radare2 |
| 反编译 | `idat`（IDA）**或** `analyzeHeadless`（Ghidra）| 读关键函数 | VM 里 IDA 有就用 IDA；没有就用 Ghidra（免费）|
| 查壳/熵 | `diec`（Detect It Easy CLI）| 判壳/编译器 | 解压 DIE |
| 反反调试 | `scyllahide` | 反调试对抗 | 解压 ScyllaHide |
| 字符串 | `floss` | 混淆字符串还原 | pip 装 flare-floss |
| 规则匹配 | `yara` | 特征/反调试规则 | 解压 yara |

**"可装可不装"**（VM 里没有也不阻塞当前目标）：jadx/apktool/adb（Android，本目标用不上）、frida（对本目标"自翻页敏感"，反而不好用）、angr/qiling（符号执行，重）、binwalk（固件）。

---

## 5. 分析路线（搬过去之后干什么）——见另一份提示词

搬运+自检完成后，用 `docs/CONTINUE-PROMPT-ASSAULT-v2.md` 那段，让实弹对话在 **VM 里**继续（抓包 → 判 A/B/C → 卡密）。

---

## 6. 一句话

**搬 68M 本体到 VM → 设 `REVERSE_TOOL_ROOT` → 跑 `selfcheck.ps1` → 按缺件清单只装"真需要"的（首推 tshark）→ 用 v2 提示词在 VM 里续打。**
