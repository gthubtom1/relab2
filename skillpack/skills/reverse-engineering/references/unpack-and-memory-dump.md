# PE 脱壳与内存 Dump

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/pe-reverse/05-crypto-unpack/01-pe-unpack-dump.md`（已适配本机工具链）
> **什么时候用**：`diec` 报出壳签名，或节区名异常（`UPX0`/`.aspack`/`.vmp0`），或入口点不在 `.text`。静态看不到真实代码，需要在壳解密完成后 dump 出展开的内存镜像。

## 适用信号

- `diec` 输出 `UPX(…)` / `ASPack(…)` / `VMProtect(…)` / `Themida` 等壳签名。
- 节区名异常：`UPX0`/`UPX1`/`.aspack`/`.vmp0`/`.themida`。
- **入口点不在 `.text`**（`iS` 里 EP 落在 UPX0 之类的节）。
- 导入表极简 —— 只剩 `LoadLibraryA`/`GetProcAddress` 等少数几个。
- `.text` 节熵值极高（接近 8.0），说明是压缩/加密数据而非代码。

## 前置

```powershell
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
$diec   = (Resolve-ReverseToolSpec -Name 'diec').Command
$upx    = (Resolve-ReverseToolSpec -Name 'upx').Command
$r2     = (Resolve-ReverseToolSpec -Name 'r2').Command
$pesis  = (Resolve-ReverseToolSpec -Name 'pe-sieve').Command
$procdmp= (Resolve-ReverseToolSpec -Name 'procdump').Command
$cdb    = (Resolve-ReverseToolSpec -Name 'cdbX64').Command
```

## 壳行为模型

```
正常 PE 加载：
  loader → 映射 PE → 填充 IAT → 跳到 EntryPoint（原始代码）→ 正常执行

加壳 PE 加载：
  loader → 映射 PE → 填充 IAT（只有壳自己需要的几个）→ 跳到 EntryPoint（壳代码）
         → 壳解密原始节区 → VirtualProtect 改页属性
         → 重建 IAT → 跳到 OEP（Original Entry Point）→ 原始代码执行
```

**关键**：解壳后**代码在内存里是展开的，但磁盘文件还是压缩的**。所以必须 dump 内存。

## 步骤

### 1. 判定壳类型

```powershell
& $diec -j .\sample.exe
```

实测（未加壳的 notepad.exe）：

```json
{
    "detects": [
        {
            "filetype": "PE64",
            "offset": "0",
            "parentfilepart": "Header",
            "size": "200704",
            "values": [
                { "type": "linker",    "name": "Microsoft Linker",
                  "string": "Linker: Microsoft Linker(14.16.27412)",
                  "version": "14.16.27412" },
                { "type": "compiler",  "name": "Microsoft Visual C/C++",
                  "string": "Compiler: Microsoft Visual C/C++(19.16.27412)[C++]",
                  "version": "19.16.27412" },
                { "type": "tool",      "name": "Microsoft Visual Studio",
                  "string": "Tool: Microsoft Visual Studio(2017, 15.9)",
                  "version": "2017, 15.9" },
                { "type": "debug data","name": "Records",
                  "string": "Debug data: Records[codeview, pogo, repro]" }
            ]
        }
    ]
}
```

**没有壳时的样子就是判据基线**：`values` 里只有 `linker`/`compiler`/`tool`/`debug data`。一旦出现 `packer` 类型的条目，或 `diec -j` 报出 `UPX`/`ASPack`/`VMProtect`，就是壳。

对有壳样本再加两个交叉验证：

```powershell
# 入口点落在哪个节
& $r2 -2 -qc 'iI~baddr; iS; q' .\packed.exe
# EP 落在 .text 之外的节 = 加壳信号
```

### 2. UPX：直接脱（最省事）

```powershell
# 先看能不能脱
& $upx -t .\packed.exe
# 脱壳
& $upx -d .\packed.exe -o .\unpacked.exe
# 列信息
& $upx -l .\packed.exe
```

本机 UPX 版本（实测 `-V`）：

```
UPX 5.2.1       Markus Oberhumer, Laszlo Molnar & N. Reiser   Aug 27th 2026
NRV data compression library 0.84
UCL data compression library 1.03
```

判据：`upx -t` 报 `NotPackedException` 或 `CantPackException` = **不是 UPX 或改过头了**，走步骤 3。实测本机 UPX 5.2.1 的 `upx -d` 成功脱过一个样本（54111 → 41311 → 脱回 54111）。

> ★ `-o` 必须给新文件名，UPX **不覆盖输入**。

### 3. 运行时 dump（通用方法）

#### 3a. cdb + OEP 断点（本机可脚本化）

```powershell
$exe  = 'C:\path\to\packed.exe'
$cdb  = "$env:LOCALAPPDATA\Microsoft\WindowsApps\cdbX64.exe"
$log  = "$env:TEMP\cdb_unpack.txt"
$cmds = "$env:TEMP\c_unpack.txt"

@'
bu kernel32!VirtualProtect
bu kernel32!VirtualAlloc
bu ntdll!LdrpDoDebuggerBreak
g
.echo ===AT_FIRST_STOP===
r rip
r rcx
r rdx
r r8
g
.echo ===AFTER_VIRTUALPROTECT===
r rip
g
q
'@ | Set-Content -Path $cmds -Encoding ASCII

& $cdb -logo $log -cf $cmds $exe *> $null
Get-Content $log | Select-String -NotMatch 'Nuget|Repository|Extension|Path validation|ModLoad'
```

**脱壳的黄金时机是 `VirtualProtect` 被改回只读之后** —— 那一刻解密已完成、OEP 还没跳。断在 `VirtualProtect` 返回后 dump，IAT 完整性最好。

#### 3b. pe-sieve（最省心，注入/自解包专用）

`pe-sieve` 专门扫运行中进程的注入、替换、shellcode、inline hook、IAT hook。

```powershell
$pesis = 'D:\Tools\pe-sieve\pe-sieve64.exe'

# 基本扫描
& $pesis /pid <PID>

# 强制读取不可读页（配合自解壳）
& $pesis /pid <PID> /refl

# 扫非可执行页（找藏起来的 shellcode）
& $pesis /pid <PID> /data 3

# 扫 IAT hook
& $pesis /pid <PID> /iat 3

# 检测加密区（找壳的解密缓冲）
& $pesis /pid <PID> /obfusc 3
```

本机版本（实测）：

```
Version:  0.4.1.1 (x64)
Built on: Sep 13 2025
```

`/help` 实测可用参数：

| 参数 | 含义 |
|---|---|
| `/pid <整数>` | 目标 PID（十进制，或 `0x` 前缀十六进制）**必填** |
| `/quiet` | 只打摘要，不打 stdout 日志 |
| `/refl` | 先做进程 reflection，强制读取不可访问页 |
| `/dnet 0..4` | .NET 进程扫描策略 |
| `/mignore <list>` | 跳过指定模块（`;` 分隔，如 `kernel32.dll;user32.dll`） |
| `/data 0..5` | 是否扫非可执行页（`3`=always，`4`/`5` 含不可访问页） |
| `/iat 0..3` | IAT hook 扫描（`3`=unfiltered 全报） |
| `/obfusc 0..3` | 加密区检测（`3`=any，强/弱加密都查） |

判据：输出目录里出现 `*_unpacked.exe`（注入的完整 PE）或 `*_shellcode.bin`（挖出的 shellcode）。

#### 3c. procdump（保底）

```powershell
$procdmp = 'D:\Tools\Sysinternals\procdump.exe'

# 全内存 dump（-ma = full dump with all sections）
& $procdmp -ma <PID> C:\dumps\target.dmp
# 本机版本
& $procdmp /? | Select-Object -First 1
# ProcDump v12.01 - Sysinternals process dump utility
```

`.dmp` 用 cdb/x64dbg 打开；要做成 PE 用 pe-sieve 的 `/refl` 或自己按节表 carve。

### 4. IAT 修复

**问题**：dump 出来的 PE 里 IAT 可能不完整 —— 壳自己解析 API 并填到自定义位置，和原始 PE 的 IAT 布局不同。

**三条路**：

1. **不修**（推荐起步）：把 dump 当 raw binary 分析。r2 用 `r2 -n raw` 加载，或 Ghidra 选 raw 导入。不修也能做大部分静态分析。
2. **Scylla（GUI）**：IAT Autosearch → Get Imports → Dump → Fix Dump。**仅人工桌面侧**，无 CLI 孪生，agent 不能自动跑。
3. **手工重建**：从运行中进程把真实 IAT 内容拷回 dump 文件。

**判据**：看导入表能不能出得来 ——

```powershell
& $r2 -2 -qc 'ii; q' .\dumped.exe | Measure-Object -Line
```

dumped 文件的导入行数 >> 壳文件的导入行数（notepad.exe 基线 40 条），说明 IAT 已重建。

### 5. 把 dump 重新解析

**dump 是内存镜像，节区 `PointerToRawData` 常常是无效的**（dump 时所有节的 paddr 可能是 0 或重叠）。必须按 `VirtualAddress` 重新展开：

```python
import pefile

pe = pefile.PE("dumped.exe")   # pefile 支持从内存映射解析
for s in pe.sections:
    nm = s.Name.decode(errors="ignore").rstrip("\x00")
    print(f"{nm:10s} VA={hex(s.VirtualAddress):10s} VS={hex(s.Misc_VirtualSize):10s} "
          f"Raw={hex(s.PointerToRawData):10s} RS={hex(s.SizeOfRawData):10s} "
          f"perm={hex(s.Characteristics)}")
```

## 判据

脱壳成功，三个**外部可观测**的条件：

1. **壳签名消失**：把 dump 交给 `diec`，`values` 里不再有 `packer` 类型条目（对比步骤 1 的 notepad 基线：只有 linker/compiler/tool/debug data）。同时 `upx -t dumped.exe` 应报 `NotPackedException`。
2. **导入表重建**：`ii` 的行数显著增加（dump 前个位数 → dump 后几十条），且能看出真实功能 API（网络/文件/注册表）。
3. **代码可反编译**：dump 后 `aaa` 能识别出函数（`afl` 返回非 0；基线 notepad.exe 是 336 个函数），且目标函数不再是 `sub_XXXX` 垃圾。
4. **行为一致**：原始样本和 dump 后样本对同一输入行为一致（对解壳后二次分析而言通常通过跑一遍看是否崩溃来判）。

## 坑

1. ★ **dump 出来的东西不是合法 PE 文件**。内存镜像的节区头、`PointerToRawData` 都不可信。直接 `r2 file` 打开可能报错或节区错位 —— 用 pefile 从内存映射解析，或按 `VirtualAddress` 手工展开成文件布局。
2. ★ **dump 时机不对 = IAT 是空的**。必须在壳解密完成之后、OEP 执行之前或刚执行时 dump。太早（`VirtualAlloc` 刚分配）拿到的是未解密缓冲区。
3. ★ **`upx -d` 不覆盖原文件**，必须 `-o out.exe`。且 `-t` 先测能不能脱。
4. ★ **pe-sieve 的 `/pid` 是必填**，没有默认值。且 `/refl` 会做进程 reflection，**对自保护进程可能失败或超时**。
5. **`pe-sieve` 输出目录在当前工作目录**，agent 跑之前先 `cd` 到专门的目录，别污染工作区。
6. **`.dmp` 是 minidump/full dump 格式**，不是 PE。要么用 cdb 直接开，要么 carve。要 carve 完整 PE 用 pe-sieve 的 `/refl`。
7. **Themida/VMProtect 的 dump 时机极难抓**，它们有反 dump（`NtSetInformationThread(ThreadHideFromDebugger)`、对 dump 句柄设 `FILE_FLAG_NO_BUFFERING` 等）。这类走 `vmp-devirtualization-toolchain.md` 而不是硬 dump。
8. **X64dbg headless 会自杀**（command loop 空转即退），**不能用 `-d` 命令行跑**。GUI + MCP 才是 x64dbg 的正确用法。
9. **`cdb` 命令串必须 `-cf <文件>`**（内联带引号被 cmd 转义坏）。断点必须在 `g` 之前下。
10. **ProcDump v12.01 的 `-ma` 需要管理员权限**扫受保护进程。


## 出口（结论回填）

回填位置：滚动报告 `assault.md`（`-Preset assault` 生成）的对应表。

- dump 产物（磁盘文件 + SHA256）→ `## functions` 相关行的证据（L1 过层证据）
- IAT 重建结果（导入表条数变化）→ `## layers` L1 行证据
- dump 里的关键字符串 / 常量 → `## findings`（如需）
- dump 不完整、缺节区等情况 → `## unknowns`（注明影响）

判定：dump 不是终点——**dump 之后的真代码分析才是**。拿到 dump 就回状态机继续。

## 相关

- `pe-header-parsing.md` — dump 后重新解析节区布局
- `tls-callback-analysis.md` — 很多壳把解包逻辑放在 TLS 回调里（比入口点更早）
- `vmp-virtualization-analysis.md` — VMProtect 的虚拟化分析（dump 之后的下一步）
- `vmp-devirtualization-toolchain.md` — dump 之后如何还原虚拟化的函数
- `anti-debug-bypass.md` — dump 前必须先过反调试，否则进程先死了
- `aob-signature-scan.md` — 在 dump 里扫特征码找解包逻辑
- `dynamic-api-resolution.md` — 壳的 IAT 重建就是一条解析链
- `../SKILL.md` — 总体流程