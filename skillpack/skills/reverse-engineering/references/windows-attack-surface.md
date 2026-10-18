# Windows 逆向攻击面地图

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/windows/README.md` + `kb/windows/techniques/README.md`（合并改编，已适配本机工具链）
> **什么时候用**：拿到一个 Windows PE 样本但不知道该从哪下手；需要按「攻击面」而不是按「工具」来规划分析；要在动手前先确认自己会不会漏掉某一类入口。

本篇是索引型文档 —— 上游那两个 README 承载的就是「Windows 逆向有哪些攻击面」的目录信息，
这里改写成一张**可执行的地图**：每个攻击面对应哪个参考文档、什么现象会指向它、本机用什么工具。

## 适用信号

- 拿到一个 PE 样本，不知道从哪个入口下手（静态 / 动态 / 网络 / 配置 / 注入面）。
- 目标是**不是恶意软件但被入侵**的 Windows 程序（本地提权、配置劫持、DLL 侧加载）。
- 需要给团队新人一份「Windows 逆向有哪些方向」的清单，而不是某一条具体技巧。
- 分析到一半发现「这个行为不是代码里的」，怀疑来自配置、注册表、服务、计划任务、驱动。

## 攻击面分层总图

```text
┌─ 样本面 ────────────────────────────────────────────────┐
│ 1. 文件/PE 结构    PE 头、节区、TLS、导入导出、资源       │
│ 2. 代码保护        加壳、虚拟化、混淆、反调试             │
└─────────────────────────────────────────────────────────┘
┌─ 运行面 ────────────────────────────────────────────────┐
│ 3. 加载/注入       DLL 注入、AppInit、劫持、Manual Map    │
│ 4. 权限/凭据       服务、注册表、计划任务、令牌           │
│ 5. 配置面          ★ 本地配置目录劫持（CVE 类，见下篇）    │
└─────────────────────────────────────────────────────────┘
┌─ 观测面 ────────────────────────────────────────────────┐
│ 6. 网络/协议       抓包、协议结构、加密边界               │
│ 7. 内存数据        游戏/客户端内存里的关键数值（见 game- 批）│
└─────────────────────────────────────────────────────────┘
```

## 前置

```powershell
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
$r2    = (Resolve-ReverseToolSpec -Name 'r2').Command
$diec  = (Resolve-ReverseToolSpec -Name 'diec').Command
$capa  = (Resolve-ReverseToolSpec -Name 'capa').Command
$py    = (Resolve-ReverseToolSpec -Name 'pyre').Command          # pefile 2024.8.26 / yara 4.5.4
$cdb   = (Resolve-ReverseToolSpec -Name 'cdb').Command
```

> ★ cdb 只能走 `%LOCALAPPDATA%\Microsoft\WindowsApps\cdb.exe` alias，且**不能加进 PATH**。
> x86 样本换 `cdb`，混用报 `Win32 error 0n50`。

## 步骤

### 0. 先做初筛，定攻击面优先级

不要一上手就反汇编。先用两个工具把「这个样本是什么」定下来，再决定往哪个面钻：

```powershell
& $diec -j .\sample.exe
& $capa -q .\sample.exe
```

实测输出（自建的 `kbgame_probe.exe`，SHA256 `ba9f5388ac28866d68a078eefc2771a48f16894c301d40b590ab0315ca7d5572`）：

```
filetype: PE64   arch: amd64
│ EXECUTION                           │ Shared Modules [T1129]                │
│ COMMUNICATION         │ Socket Communication::Receive Data [C0001.006]      │
│                       │ Socket Communication::Send Data [C0001.007]         │
│ MEMORY                │ Allocate Memory [C0007]                             │
```

**读法**：capa 的 MBC 分类直接告诉你命中了哪些面（本例：共享模块 → 注入面；Socket 收发 → 网络面；
分配内存 → 内存/注入面）。这些分类名就是下面表格的入口。

### 1. 攻击面 → 参考文档映射

| # | 攻击面 | 典型现象（→ 适用信号） | 本机工具 | 参考文档 |
|---|--------|------------------------|----------|----------|
| 1 | **PE 结构** | 节区名异常、入口点在节区末尾、`DataDirectory[9]` 非空、导出名可疑 | `r2 -qc 'iS; iE; iI; q'`、pefile、`diec` | `pe-header-parsing.md` |
| 2 | **代码保护** | `diec` 报 UPX/VMProtect/Themida；节区熵高；入口点代码是跳转壳 | `diec`、`r2 -qc 'iS; q'` 看节区、capa（壳下命中率骤降是信号） | `triage-first-30-min.md`、`unpack-and-memory-dump.md`、`vmp-devirtualization-toolchain.md`、`vmp-virtualization-analysis.md`、`custom-obfuscation-reverse.md`、`ollvm-deobfuscation.md` |
| 3 | **反调试** | 调试器附加就退出、`PEB.BeingDebugged` 被查、INT3/异常链探测、检测到硬件断点 | `cdb`、`x64dbg`、`scyllahide` | `anti-debug-bypass.md`、`debugger-breakpoints.md` |
| 4 | **早期执行** | 入口点之前就有行为（退出/弹窗/解密） | `r2 -qc 'iS; q'` + pefile 枚举 TLS、cdb `bu ntdll!LdrpCallTlsInitializers` | `tls-callback-analysis.md` |
| 5 | **动态 API 解析** | 导入表极少但程序正常工作；PEB 遍历 EAT 的手写循环 | `r2 -qc 'ii; q'` 看导入数量、`dynamic-api-resolution.md` 的 EAT 遍历法 | `dynamic-api-resolution.md` |
| 6 | **代码补丁** | 需要改返回值、跳过分支、关掉校验 | `r2`、`x64dbg`、`capa` 定位、`code-patching.md` 落盘 | `code-patching.md`、`disasm-jit-asm.md` |
| 7 | **注入 / 加载劫持** | 出现了进程不该有的模块；DLL 搜索顺序被利用；Manual Map | `pe-sieve`（运行态模块/内存洞）、`r2 -qc 'ii; q'`、cdb `!peb !peb` 走 PEB_LDR_DATA | `dll-injection-patterns.md` |
| 8 | **结构体/偏移重建** | 满屏 `????`；需要还原 vtable / C++ 类布局；偏移要跨版本复用 | `reclass-reconstruction.md`、`struct-reconstruction.md`、`aob-signature-scan.md` | `struct-reconstruction.md`、`reclass-reconstruction.md`、`aob-signature-scan.md` |
| 9 | **密码算法识别** | 看到 S-box、常量 0x67452301/0xEFCDAB89、CBC/CTR 模式 | `capa`、`floss`、`prng-cracking.md` | `crypto-algorithm-identification.md`、`prng-cracking.md` |
| 10 | **网络 / 协议** | 抓包能看到或看不到明文；要还原协议结构；TLS 证书固定 | `tshark`、capa（Socket 分类） | `../../game-reverse/references/game-packet-interception.md` |
| 11 | **内存数据（游戏客户端）** | 关键数值在内存里但被加密/混淆；反作弊在扫内存 | `r2`、`cdb`、`capa` | `../../game-reverse/references/game-memory-hacking.md` |
| 12 | **配置面 / 本地提权** | ★ 程序读取一个可写的配置文件/目录并把里面的值当可执行路径 | `r2 -qc 'izz; q'` 找配置键名、`floss` 找 API、`yara` 批量定位 | **`notepadpp-config-injection.md`**（本目录） |
| 13 | **检测与 IOC** | 需要把结论固化成规则 | `yara` | `yara-rule-writing.md` |
| 14 | **YARA / 规则化** | 批量扫描样本库 | `yara`、yara-python | `yara-rule-writing.md` |

### 2. 配置面为什么必须单列

面 1–9 都是**代码里能看到的**，面 12 不是。上游 `license-keygen/README.md` 的整条 `techniques/`
目录目前只有一篇文档，正是这个原因：Windows 上的**本地提权/命令执行**一大半不来自
代码缺陷，而来自「程序信任了一个攻击者也能写的输入」。

典型三类输入通道：

| 通道 | 例子 | 静态怎么找 |
|------|------|------------|
| 配置文件 | `config.xml`、`.ini`、`.cfg`、`.json` | 字符串里出现键名 → 追到 `fopen/CreateFile` → 追到取值后的使用点 |
| 配置目录 | `-settingsDir=`、插件目录、`%APPDATA%` 子目录 | 命令行参数字符串 + `GetEnvironmentVariable` |
| 环境变量 | `PATH`、`APPDATA` | `GetEnvironmentVariable` / `SetDllDirectory` 的调用点 |

本机实测（`r2 -qc '/ commandLineInterpreter'`，自建复现样本）：

```
A=[0x140004025 hit0_0 ">rbopen failcommandLineInterpretername="%s">tag " 0x140004055 hit0_1 ">tag not foundcommandLineInterpreter = %sopenShe]
```

两个命中点：一个是**配置键名**（`0x140004025`），一个是**格式化输出串**（`0x140004055`）。
配置键名进 `.rdata` 就说明「这个程序按名字去读一个外部配置」—— 面 12 的入口出现了。
完整展开见 `notepadpp-config-injection.md`。

### 3. 按攻击面选工具的最小集

不要 16 个工具全带。按面选：

```powershell
# 面 1/4/5（结构与早期执行）—— 纯静态，最快
& $r2 -2 -qc 'iS; iE; ii; q' .\sample.exe

# 面 2（保护）—— 先定性再决定是否脱
& $diec .\sample.exe

# 面 3（反调试）—— 动态，用 cdb 打 Ldr 层而不是 API 层
# 见 anti-debug-bypass.md

# 面 12（配置）—— 字符串 + API 两头对齐
& $r2 -2 -qc 'izz~config; q' .\sample.exe
& $floss -only static .\sample.exe | Select-String 'CreateFile|ShellExecute|RegOpenKey'

# 面 13 —— 结论固化
& $yara -r .\rules.yar <样本目录>
```

## 判据

攻击面判定不能靠「我猜它是 DLL 侧加载」，必须有**外部可观测**的现象。合规定局：

1. **面 1/4（PE 结构 / 早期执行）**：pefile 枚举出的 `DataDirectory[9].VirtualAddress != 0` 且
   `DIRECTORY_ENTRY_TLS` 的回调数组 `count >= 1`；或者 cdb 日志里出现 `Breakpoint 0 hit` 于
   `ntdll!LdrpCallTlsInitializers`。上面 `kbgame_probe.exe` 就有 `.tls` 节（`.tls` RVA `0x9000`，
   SizeOfRawData 512）—— 有节区只是信号，**回调数组非空才是判据**。
2. **面 3（反调试）**：反调试逻辑**被实际触发过**的证据 —— 被 patch 的分支前后行为分叉、
   或者 `cdb` 日志里能看到目标调了 `IsDebuggerPresent`/`NtQueryInformationProcess`。
   「看到有 PEB 访问」不够，必须看到访问结果影响了控制流。
3. **面 7（注入）**：运行态模块列表里出现静态导入表没有的模块。判据命令：
   `pe-sieve64.exe /pid <pid>` 的输出里 `modules` 段多出条目；或 cdb 里
   `!peb` 走 `PEB_LDR_DATA.InLoadOrderModuleList` 的链表节点数 > 静态导入 DLL 数 + 显式 LoadLibrary 目标数。
4. **面 10（网络）**：tshark 对 pcap 的 `-T fields` 输出里 `tcp.payload` 列**非空且随帧号变化**。
   实测（scapy 生成的 `synth.pcap`）：
   ```
   1	4	 	70696e67
   2	80	deadbeef01020010aaaa...aaaa	deadbeef01020010aaaa...aaaa
   ```
   `tcp.payload` 有值 = 这一层抓到了应用层字节；列为空（只有 `tcp.len`）= 你只看到长度没看到内容。
5. **面 12（配置）**：**同一份输入，两份配置，行为可观测分叉**。本机实测（自建 `kbconfig_probe.exe`，
   SHA256 `5f7069a7ec5d4c18eec8166553c810eddc704bc65c0465300f3334e8b6686584`）：
   ```
   kbconfig_benign.xml -> commandLineInterpreter = cmd.exe | ShellExecute ret=000000000000002A
   kbconfig_evil.xml   -> commandLineInterpreter = calc.exe | ShellExecute ret=000000000000002A
   ```
   同一二进制、同一路径、同一调用，只因配置文件里的值不同就换了被执行程序 —— **这就是面 12 的判据**。
   配套静态证据：`r2 -qc 'izz; q'` 命中配置键名，`floss` 命中 `ShellExecuteA` / `SHELL32.dll`。
6. **面 13（YARA）**：规则在正样本上输出规则名，在负样本上无输出，且规则文件本身不被扫描命中。
   本机实测：`yara64.exe simple.yar kbconfig_probe.exe` → `out=[probe_marker .\kbconfig_probe.exe] rc=0`。

## 坑

1. ★ **`bl` 显示绑定成功 ≠ 断点会命中**。这是本目录最大的坑。实测：
   `bu kernel32!GetTickCount64` → `bl` 里没有这一条（报 `Couldn't resolve error`）；
   `bu kernelbase!QueryPerformanceCounter` → **同样 `Couldn't resolve error`**，
   因为公开 PDB 里只有 `kernel32!QueryPerformanceCounterStub` 这个名字（**不是 forwarder** —— pefile 实测
   kernel32.dll 里 `QueryPerformanceCounter` 的 forwarder 字段为 None，它就是本 DLL 的真导出）。判据必须看
   日志里的 `Breakpoint 0 hit`，不能看 `bl`。
   实测能命中的正确名字（`x kernel32!*` 枚举得到）：
   `KERNEL32!GetTickCountKernel32`、`KERNEL32!GetTickCount64Kernel32`、
   `KERNEL32!QueryPerformanceCounterStub`、`WINMM!timeGetTimeStub`、
   `KERNEL32!ReadProcessMemoryStub`、`KERNEL32!WriteProcessMemoryStub`。
   `KERNELBASE!GetTickCount` 是真实现（非 forwarder），也能命中（实测命中 2 次）。
2. ★ **`/x` 返回空先查字节序，不是 r2 的问题**（2026-10-10 本机实测复核）：
   同一份**确实含有这些字节**的样本上，`/x 6a006801`、AES S-box 前缀
   `637c777bf26b6fc53001672bfed7ab76` 全部**正常命中**。
   唯一返回空的是 `/x 2003fe7f` —— 文件里是 `7f fe 03 20`，`2003fe7f` 是**字节序写反**。
   通配符实测：`7ffe03..` 命中、`7ffe03??` 空（即 `.` 通配、`?` 不通配）。
   所以：**按文件实际字节顺序书写，`/x` 是可用的十六进制检索工具。**
   （此前本条曾断言 `/x` 在本机不可用，那是误判 —— 实为特征码字节序写反，已纠正。）
   另：`-qc '/x ...; q'` 里的 `;` 会截断命令，参数串只放一条；
   多条命令用 `-c '/x ...' -c 'q'` 分开给。
3. ★ **cdb 命令文件每行一条、扁平，结尾必须有 `q`**；`r rcx rsi rdx` 写成一行会报
   `Syntax error in 'r rcx rsi rdx'`（实测），每个寄存器单独一行。
4. **cdb 断点必须下在 `g` 之前**（延迟绑定），且断点日志读出来是 UTF-16LE/混合编码 ——
   用 Python `raw[:8]` 有 `\x00` 就按 `utf-16-le` 解，否则 `utf-8`。
5. **`axt` 在没跑 `aaa` 之前是空的**。实测 `axt @ 0x140008340`（OpenProcess 的 IAT 槽）无输出，
   加 `aaa` 后才有 `sym.wmain 0x1400014ec [CALL:--x] call qword [sym.imp.KERNEL32.dll_OpenProcess]`。
   注意即便如此，xref 命中的是 **PLT 跳板**（`0x1400029b0 jmp qword [...]`），不是调用点本身。
6. **`pefile` 的 `i.struct_iat.get_file_offset()` 会抛 `AttributeError`**（实测）——
   `struct_iat` 是 int 不是对象。用 `pe.get_offset_from_rva(imp.address - ImageBase)`。
7. **导入名大小写敏感**：r2 `ii` 输出里是 `WS2_32.dll` / `WINMM.dll` / `KERNEL32.dll`，
   过滤时写 `ws2_32`（小写）会一个都匹配不到。
8. **有 `.tls` 节 ≠ 有 TLS 回调**。MinGW 产物即使没有 TLS 回调也会有 `.tls` 节。
   判据是 `pe.DIRECTORY_ENTRY_TLS` 的回调数组非空，见 `tls-callback-analysis.md`。
9. **`TimeDateStamp` 不可信**。实测 `kbgame_probe.exe` 的 `TimeDateStamp=1791563983` 正好是
   当天编译时刻，但很多壳/构建系统会写 0 或任意值。**不要用它当判据**，用哈希。
10. **capa 在带壳样本上会大面积漏命中** —— 这是信号不是工具坏了。解壳后重跑再对比。
11. **`(Resolve-ReverseToolSpec -Name 'capa').Command` 在 `cmd` 里必须直接调，不能带 `cmd /c` 前缀再包一层引号**
    （实测 `cmd /c "\"...capa.bat\" file"` 报「不是内部或外部命令」）。用
    `subprocess.run(r'(Resolve-ReverseToolSpec -Name 'capa').Command sample.exe', shell=True)`。
    capa 输出是 UTF-8，**PowerShell 直接看是乱码**（936 码页），要按 UTF-8 解码再用 `│` 过滤。
12. **上游 README 里的 front-matter（`id`/`board`/`signals`/`mcp_tools`/`keywords`/`tags`/
    `last_updated`）是知识库自身的组织元信息**，不是技术内容，移植时一律丢弃。

## 相关

- `notepadpp-config-injection.md` — 本目录唯一的实战篇：配置信任边界失效 → 本地命令执行，
  含可在本机复现的最小样本
- `pe-header-parsing.md` — 面 1 的基础（`DataDirectory`、节区、VA↔RVA）
- `triage-first-30-min.md` — 面 2 的入口：拿到样本前 30 分钟该按什么顺序做什么
- `signal-to-tool-decision.md` — 「看到什么现象 → 用哪个工具」的查表
- `tls-callback-analysis.md` — 面 4 的完整还原流程
- `unpack-and-memory-dump.md` — 面 2 里「脱壳」这一支
- `dll-injection-patterns.md` — 面 7
- `yara-rule-writing.md` — 面 13，把结论固化成规则
- `../../game-reverse/references/README.md` — 面 10/11 的展开（游戏客户端专门篇目）