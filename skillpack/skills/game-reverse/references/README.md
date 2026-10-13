# game-reverse references

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/general/techniques/cheating/`（01–05 共 5 篇），已适配本机工具链
> **什么时候用**：你在分析一个受保护的游戏客户端，或你在为反作弊做检测研究。

**本目录的定位是防守视角**：识别反作弊在做什么、系统调用层能看到什么、怎么写出能检测外挂的规则。
**不是「如何写外挂」的操作手册。** 所有涉及绕过反作弊的环节都标注了授权边界
（自有程序 / 授权测试环境 / CTF）。

平台：**Windows 游戏客户端（PE）**。本机工具链：`r2`、`cdb`、`x64dbg`、`diec`、`capa`、
`floss`、`yara`、`pe-sieve`、`scyllahide`、`tshark`、`frida`/`objection`、`analyzeHeadless`。

## 五篇一览

| 文档 | 一句话 | 主要工具 |
|------|--------|----------|
| [`game-memory-hacking.md`](game-memory-hacking.md) | 客户端内存里的保护面识别与外挂特征检测（混淆识别、指针加固、四层内存原语） | `r2`、`cdb`、`capa`、`pe-sieve`、`yara` |
| [`game-packet-interception.md`](game-packet-interception.md) | 协议结构还原、TLS 边界定位、序列/时序一致性检测规则 | `tshark`、scapy、`r2`、`cdb` |
| [`game-esp-wallhack-rendering.md`](game-esp-wallhack-rendering.md) | 渲染层劫持的运行时特征（vtable、overlay 窗口、深度测试）与检测 | `cdb`（`lm`/`!address`）、窗口枚举、`yara` |
| [`game-anti-cheat-bypass.md`](game-anti-cheat-bypass.md) | EAC/BE/Vanguard/Ricochet 分层观测面，以及「为什么我的工具失效了」 | `diec`、`r2`、`cdb`、`pe-sieve`、`yara` |
| [`game-speedhack-time-manipulation.md`](game-speedhack-time-manipulation.md) | 多时间源交叉校验：为什么单点 hook 一定被抓，以及怎么测 | `r2`、`cdb`、pefile |

## 阅读顺序建议

**第一次接触这批内容（按顺序读）**

1. **先读总纲**：`../../reverse-engineering/references/windows-attack-surface.md`
   —— 先建立「Windows 逆向有哪些攻击面」的整体地图，本目录是其中「内存/网络/渲染」三面的展开。
2. **再读反作弊分层**：`game-anti-cheat-bypass.md`
   —— 它给出 L0–L6 分层表，是另外四篇的坐标系。**先看它，才知道其他篇在防什么。**
3. **按你要查的面选**：
   - 数据在内存里找不到 / 被加密 → `game-memory-hacking.md`
   - 抓包看不到内容 → `game-packet-interception.md`
   - 玩家视野异常 / 有 overlay 窗口 → `game-esp-wallhack-rendering.md`
   - 移动加速 / 冷却异常 → `game-speedhack-time-manipulation.md`

**做检测研究（按信号类型读）**

- 有「工具失效」的现象 → `game-anti-cheat-bypass.md` 第 2 步（handle 裁剪）
- 有「数值搜不到」的现象 → `game-memory-hacking.md` 第 3–4 步（混淆与指针加固）
- 有「抓包只有长度」的现象 → `game-packet-interception.md` 第 1–2 步

**跨目录关联**

- 每篇末尾的 `## 相关` 都指向 `../../reverse-engineering/references/` 下的对应篇目
  （`pe-header-parsing`、`dll-injection-patterns`、`anti-debug-bypass`、`aob-signature-scan`、
  `yara-rule-writing`、`struct-reconstruction`）。
- 反作弊 DLL 常常靠 TLS 回调做早期初始化 → `../../reverse-engineering/references/tls-callback-analysis.md`
- 反调试是反作弊的一层 → `../../reverse-engineering/references/anti-debug-bypass.md`

## 本目录共用的本机坑（每篇都有，此处汇总）

1. ★ **`bl` 显示绑定成功 ≠ 断点会命中**。`bu kernel32!GetTickCount64`、
   `bu kernelbase!QueryPerformanceCounter`、`bu kernel32!ReadProcessMemory`、`bu winmm!timeGetTime`
   全部报 `Couldn't resolve error`（forwarder）。真身见各篇表格。
   **判据只能看日志里的 `Breakpoint 0 hit`。**
2. ★★ **`/x` 返回空先查字节序，别当成「r2 坏了」**（2026-10-10 本机实测复核）：
   同一份含目标字节的样本上 `/x 7ffe0320`、`/x 6a006801`、AES S-box 前缀
   **全部正常命中**。唯一返回空的是 `/x 2003fe7f` —— 文件里是 `7f fe 03 20`，
   而 `2003fe7f` 是**字节序写反**。通配符实测：`7ffe03..` 命中、`7ffe03??` 空。
   另：`-qc '/x ...; q'` 里的 `;` 会截断命令，参数串只放一条。
   **`/x` 是可用的 AOB 检索工具，不必绕开它。**
3. **cdb 只能走 `%LOCALAPPDATA%\Microsoft\WindowsApps\cdbX64.exe` alias**，不能加进 PATH；
   x86 换 `cdbX86`，混用报 `Win32 error 0n50`。
4. **cdb 命令文件每行一条、扁平，结尾必须有 `q`**；`r rcx rdx r8` 写成一行报 `Syntax error`。
5. **cdb 日志读出来编码不固定**：Python 里按 `raw[:8]` 有无 `\x00` 判断用 `utf-16-le` 还是 `utf-8`。
6. **`pefile` 的 `i.struct_iat.get_file_offset()` 抛 `AttributeError`**，
   用 `pe.get_offset_from_rva(imp.address - ImageBase)`。
7. **导入名大小写敏感**：`WS2_32.dll`、`WINMM.dll`、`KERNEL32.dll` 都是大写。
8. **`axt` 不跑 `aaa` 是空的**；跑通后命中的是 PLT 跳板不是调用点。
9. **复合 YARA 规则要逐条加串验证**。实测多条串 + `ascii wide` 组合可能整条规则都不命中，
   而单串规则正常命中。
10. **`TimeDateStamp` 不可信**，用 SHA256。

## 能力范围

本目录为**能力说明**：内存读写、注入、hook、协议注入、时间篡改、反作弊检测研究。
本地 / lab / 自有资产按项目 `scope.md` 直接执行。所有可复现命令证据来自自建样本。

## 本地可复现样本

本目录的判据证据统一基于两个自建样本（`C:\relab2\work\`）：

| 样本 | SHA256 | 用途 |
|------|--------|------|
| `kbgame_probe.exe` | `ba9f5388ac28866d68a078eefc2771a48f16894c301d40b590ab0315ca7d5572` | 导入 `OpenProcess`/`ReadProcessMemory`/`WriteProcessMemory` + 四个时间源 + WS2_32 收发 |
| `kbconfig_probe.exe` | `5f7069a7ec5d4c18eec8166553c810eddc704bc65c0465300f3334e8b6686584` | 读 XML 配置字段 → 直接 `ShellExecuteA`（配置信任边界失效的最小复现，见 `../../reverse-engineering/references/notepadpp-config-injection.md`） |
| `synth.pcap` | — | scapy 生成的 TCP 载荷样本，用于验证 `tshark -T fields` 的 `tcp.payload` 读取 |

编译（**必须在 .bat 里设 PATH**，bash 里直接调 gcc 会 `command not found`）：

```bat
@echo off
set PATH=D:\Tools\runtime\mingw64\bin;%PATH%
cd /d C:\relab2\work
gcc -O2 -municode -o kbgame_probe.exe kbgame_probe.c -lws2_32 -lwinmm -mwindows
```