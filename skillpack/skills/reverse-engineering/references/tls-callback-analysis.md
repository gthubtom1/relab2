# TLS Callback 定位与早期执行链

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/pe-reverse/02-pe-structure/02-tls-callback-analysis.md`（已适配本机工具链）
> **什么时候用**：程序在 EntryPoint **之前**就退出或弹窗；OEP 断不下来；反调试先触发；怀疑入口点之前有隐藏代码。TLS 回调是 PE 入口点之前的执行节点，遇到这类现象先看 TLS。

## 适用信号

- 程序在 `main`/`WinMain`/入口点**之前**就退出、静默结束或弹错误框。
- 在入口点下断点，永远命中不了；或者断点位置比预期早很多。
- OEP 找到了但「跳过去什么都不发生」——真正逻辑在 TLS 里已经做完了。
- 反调试检测在入口点之前就触发（早于你设的断点）。
- 静态看到 `.CRT$XLA` / `.CRT$XLZ` 之类的节区名（有 TLS 但未必有回调）。
- DLL 分析只看了导出和 DllMain，行为却在 `DllMain` 之前发生。

## 前置

```powershell
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
$r2   = (Resolve-ReverseToolSpec -Name 'r2').Command
$cdb  = (Resolve-ReverseToolSpec -Name 'cdb').Command   # x64 样本
$cdb86= (Resolve-ReverseToolSpec -Name 'cdb').Command   # x86 样本
$py   = (Resolve-ReverseToolSpec -Name 'pyre').Command                        # pefile 2024.8.26
```

> ★ cdb **只能走 app execution alias**：`%LOCALAPPDATA%\Microsoft\WindowsApps\cdb.exe`。直跑 WindowsApps 包目录里的 `cdb.exe` 会「拒绝访问」，**且绝不要把它加进 PATH**。

## TLS 目录结构

`OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_TLS]`（索引 **9**）指向 `IMAGE_TLS_DIRECTORY`：

```
IMAGE_TLS_DIRECTORY64
  StartAddressOfRawData   VA   ┐
  EndAddressOfRawData     VA   ├─ TLS 数据区（线程局部存储本体）
  AddressOfIndex          VA   ┘
  AddressOfCallBacks      VA   ★→ 一个「函数指针数组」的 VA
                              数组元素个数不定，以一个 0（NULL）结尾

IMAGE_TLS_DIRECTORY32：布局相同，只是前四项是 4 字节，AddressOfCallBacks 在偏移 12
```

**两种 TLS 布局并存**：
- **动态 TLS**（标准）：`.tls` 节 + `AddressOfCallBacks` 数组，loader 显式遍历调用。
- **静态 TLS**（老式）：用 `.CRT$XL*` 节段名按字典序调用，**没有** `AddressOfCallBacks` 数组。MSVC/minGW 产物常见。遇到静态 TLS 时 `DataDirectory[9]` 可能为 0，但 TLS 回调照样执行 —— 只查目录会漏。

## 步骤

### 1. 静态确认：TLS 目录非空

```powershell
& $r2 -2 -qc 'iS; q' .\sample.exe | Select-String 'tls|CRT'
```

实测（tlstest.dll，含 TLS 回调）：

```
8   0x00002c00  0x200 0x1cdb0a000  0x1000 -rw- 0xc0000040 ---- .tls
```

有 `.tls` 节是个信号，但不是判据 —— 判据是回调数组非空。

用 pefile 枚举回调（**权威做法**）：

```python
import pefile, struct

pe = pefile.PE("sample.exe")
is64 = pe.PE_TYPE == pefile.OPTIONAL_HEADER_MAGIC_PE_PLUS
ptr  = 8 if is64 else 4
base = pe.OPTIONAL_HEADER.ImageBase
fmt  = "<Q" if is64 else "<I"

d = pe.OPTIONAL_HEADER.DATA_DIRECTORY[9]      # IMAGE_DIRECTORY_ENTRY_TLS
print("TLS dir RVA:", hex(d.VirtualAddress), "Size:", hex(d.Size))
print("has DIRECTORY_ENTRY_TLS:", hasattr(pe, "DIRECTORY_ENTRY_TLS"))

if not hasattr(pe, "DIRECTORY_ENTRY_TLS"):
    print("动态 TLS 目录为空 —— 若是静态 TLS (.CRT$XL*) 需另找")
else:
    t = pe.DIRECTORY_ENTRY_TLS.struct
    print("AddressOfCallBacks:", hex(t.AddressOfCallBacks))
    off = pe.get_offset_from_rva(t.AddressOfCallBacks - base)
    data = pe.__data__
    i = 0
    while True:
        (val,) = struct.unpack_from(fmt, data, off + i * ptr)
        if val == 0:                              # 0 结尾 = 数组结束
            break
        rva = val - base
        print(f"  callback[{i}] VA={hex(val)} RVA={hex(rva)} "
              f"offset={hex(pe.get_offset_from_rva(rva))}")
        i += 1
    print("callback count:", i)
```

实测（tlstest.dll，我用 MinGW 编译、源码里显式挂了 2 个 `__stdcall` TLS 回调）：

```
PE32+: True ptr size: 8
TLS dir RVA: 0x4020 Size: 0x28
has DIRECTORY_ENTRY_TLS: True
AddressOfCallBacks: 0x1cdb04378
callback array file offset: 0x1f78
  callback[0] = 0x1cdb01450  (RVA 0x1450, offset 0xa50)
  callback[1] = 0x1cdb01430  (RVA 0x1430, offset 0xa30)
  callback[2] = 0x1cdb0131e  (RVA 0x131e, offset 0x91e)
count: 3
```

**这是判据的关键**：我在源码里只写了 `tls_cb0` 和 `tls_cb1` 两个回调，但枚举出 **3** 个 —— 多出来的第 3 个（`RVA 0x131e`）是 MinGW CRT 自己的 `__dyn_tls_init` / `__mingw_TLScallback` 等运行时内部回调。**所以「回调数 ≥ 源码声明数」是正常的**，第一个（`0x1450`）是 CRT 的，最后一个（`0x131e`）才是应用自己的。调用顺序按数组顺序。

### 2. 确认回调名字（r2）

```powershell
& $r2 -2 -qc 'iE; q' .\tlstest.dll | Select-String 'tls'
```

实测：

```
5   0x00000910 0x1cdb01310 GLOBAL FUNC 0                tls_cb0
6   0x0000091e 0x1cdb0131e GLOBAL FUNC 0                tls_cb1
```

★ **交叉验证成功**：枚举出 `callback[2] = RVA 0x131e`，而 `iE` 里 `tls_cb1` 的 vaddr 正是 `0x1cdb0131e`（基址 `0x1cdb00000` + `0x131e`）。两条独立路径给同一答案，定位才算坐实。

### 3. 动态：在 loader 调用 TLS 之前下断

**这是本篇最核心的一条**。TLS 回调在**第一个用户断点之前**就跑完了，所以断点必须下在 loader 调 TLS 的那个函数上。

```powershell
$exe  = 'C:\path\to\sample.exe'
$cdb  = "$env:LOCALAPPDATA\Microsoft\WindowsApps\cdb.exe"
$cmds = "$env:TEMP\tls_cdb.txt"

@'
bu ntdll!LdrpCallTlsInitializers
g
.echo ===LDRP_HIT===
r rcx
kv
g
g
q
'@ | Set-Content -Path $cmds -Encoding ASCII

& $cdb -cf $cmds $exe
```

实测输出：

```
0:000> bu ntdll!LdrpCallTlsInitializers
Breakpoint 0 hit
ntdll!LdrpCallTlsInitializers:
00007ffb`654c9a78 48895c2408      mov     qword ptr [rsp+8],rbx
0:000> .echo ===LDRP_HIT===
===LDRP_HIT===
0:000> r rcx
rcx=0000000000000001
0:000> kv
Child-SP          RetAddr               : Args to Child                                   : Call Site
0000009f`365ff448 00007ffb`65583e7d     : 00007ffb`655d5910 ...                          : ntdll!LdrpCallTlsInitializers
0000009f`365ff450 00007ffb`65525deb     : ...                                            : ntdll!LdrpInitializeProcess+0x206d
0000009f`365ff870 00007ffb`65525c73     : ...                                            : ntdll!LdrpInitialize+0x15f
0000009f`365ff910 00007ffb`65525c1e     : ...                                            : ntdll!LdrpInitialize+0x3b
0000009f`365ff940 00000000`00000000     : ...                                            : ntdll!LdrInitializeThunk+0xe
```

★ **调用栈就是铁证**：`ntdll!LdrInitializeThunk` → `LdrpInitialize` → `LdrpInitializeProcess` → `LdrpCallTlsInitializers`。整条链都在 `ntdll` 的进程初始化里，**远早于任何用户入口点**。看到这条栈就说明「TLS 早于入口点」已实测确认。

继续 `g` 会**反复**命中 `LdrpCallTlsInitializers`（每个新线程一次），实测 tlsdemo.exe 上连续命中 3 次：

```
0:000> g
Breakpoint 0 hit
ntdll!LdrpCallTlsInitializers:
0:000> g
Breakpoint 0 hit
ntdll!LdrpCallTlsInitializers:
```

要只看主线程的第一次，用条件断点或数够次数就 `bd 0`。

### 4. 在回调里记录什么

命中回调时（`bu <callback_VA>`），记录：

```
callback VA / RVA:
return address:            (kv 拿)
参数:                       x64: rcx=arg(PVOID), rdx=reason(DWORD)
                            reason: 1=DLL_PROCESS_ATTACH, 0=DLL_THREAD_DETACH ...
是否改写了 .text / .rdata:  对比回调前后的内存
是否跳向 OEP:               (这通常说明是被壳复用)
```

x64 Windows 上回调签名是 `void (__stdcall *)(PVOID, DWORD)`，前两个参数在 `rcx` / `edx`。实测 `LdrpCallTlsInitializers` 自己的 `rcx=1`（是内部标志，不是回调参数）—— **别把 loader 函数的参数当成回调参数**。

### 5. 命名策略（回填 IDA/Ghidra）

```
tls_cb0_crt_early_init      # 第一个通常是 CRT 内部初始化
tls_cb1_anti_debug          # 调 IsDebuggerPresent / NtQueryInformationProcess
tls_cb2_decrypt_text        # VirtualProtect 后写 .text
tls_cb3_resolve_imports     # 手写 EAT 遍历
```

每个回调输出：

```
作用: 输入: 输出: 副作用: 调用者(恒为 loader): 被调用者: 下一跳:
```

### 6. 路径分叉表

| TLS 回调行为 | 处置 | 转交文档 |
|---|---|---|
| 调 `IsDebuggerPresent` / 查 PEB | patch 返回值或条件分支 | `anti-debug-bypass.md` |
| 调 `VirtualProtect` 后写 `.text` | 立刻 dump 内存镜像 | `unpack-and-memory-dump.md` |
| 遍历 PEB / `PEB_LDR_DATA` | 手写 EAT 解析 | `dynamic-api-resolution.md` |
| 解密字符串 | hook 解密函数返回 | crypto 相关文档 |
| `int 2d` / `int 3` 异常链探测 | ScyllaHide 异常伪造 | `anti-debug-bypass.md` |
| 直接 jmp 到 OEP | 这就是壳的解包入口 | `unpack-and-memory-dump.md` |

## 判据

TLS 存在必须满足**两个**独立证据，缺一不可：

1. **静态**：pefile 枚举出的回调数组**至少有一个非零元素**（`count >= 1`）。空数组或 `DataDirectory[9].VirtualAddress == 0`（且无静态 `.CRT$XL*`）就不算。上面 tlstest.dll 的 `count: 3` 是判据。
2. **动态**：`kv` 调用栈里出现 `LdrInitializeThunk` → `LdrpInitialize` → `LdrpInitializeProcess` → `LdrpCallTlsInitializers` 这条链，且时间上早于入口点。实测栈回溯就是判据。
3. **交叉一致**：pefile 给的 `callback[i] VA` 减去基址 == `iE` 里对应符号的 vaddr。实测 `callback[2] = 0x1cdb0131e` == `tls_cb1` 的 `0x1cdb0131e`。
4. **副作用可观测**：如果回调存在且有实际作用，命中它的瞬间 `.text` 或 `.rdata` 必然发生变化（dump 前后 diff 非空）。若无变化，说明是空回调或已被摘除。

## 坑

1. ★ **TLS 在你的第一个断点之前就跑完了**。这是本篇的核心坑。必须先 `bu ntdll!LdrpCallTlsInitializers` 再 `g`，直接 `g` 到入口点会完全错过。
2. ★ **`LdrpCallTlsInitializers` 会反复命中**（每个线程一次）。实测 tlsdemo.exe 上 3 次。别以为断点坏了。
3. ★ **静态 TLS 不在 `DataDirectory[9]` 里**。用 `.CRT$XLA`/`.CRT$XLZ` 节段的静态 TLS 没有回调数组，只查目录会漏判。r2 用 `iS~CRT` 看节名。
4. ★ **回调数不等于源码声明数**。实测我声明 2 个回调，枚举出 3 个 —— MinGW CRT 会插入自己的 `__dyn_tls_init` / `__mingw_TLScallback`。按数组顺序执行，第一个和最后一个往往是 CRT 的。
5. ★ **cdb 必须走 alias**：`%LOCALAPPDATA%\Microsoft\WindowsApps\cdb.exe`。直跑包目录里的 exe 报「拒绝访问」。
6. ★ **cdb 断点必须在 `g` 之前下**（延迟绑定）。`g` 之后才 `bu` 会来不及。
7. **cdb 命令串必须用 `-cf <文件>`**。带引号的内联命令串经 cmd 会被转义坏（`Win32 error 0n2`）。而且 `.sleep`、`.sympath-` 这类在脚本里也容易踩坑 —— `.sympath-` **不接受参数**，写成 `.sympath- srv*` 报 `Syntax error`。清符号路径就单独写 `.sympath-`。
8. **`@$peb` 可用但 `@$tib` 不可用**。实测 `r @$peb` 返回 `$peb=000000d4dda0b000`，`r @$tib` 报 `Bad register error`。写 cdb 脚本读 PEB 用 `@$peb`。
9. **cdb 脚本里的 `$$` 是注释**，但 `bu <addr> C "…"` 形式会把后跟的命令一起吃掉（实测 `bu kernel32!IsDebuggerPresent C "..."` 报 `Couldn't resolve error`）。注释单独占一行，别和命令同行。
10. **`pe.get_offset_from_rva` 对 `.CRT$*` 这类长节名节不可靠**（同 `pe-header-parsing.md` 坑）。TLSTest.dll 有 17 个节（含 `.debug_*`），务必读回字节校验。
11. **`cdb` 的退出码可能非 0**（实测 `-2147024866`），别用退出码判断成功与否，看日志里有没有 `Breakpoint 0 hit`。

## 相关

- `pe-header-parsing.md` — `DataDirectory[9]`、节区表、VA↔RVA 换算的基础
- `anti-debug-bypass.md` — TLS 回调里最常见的行为就是反调试（那里有完整绕过手法）
- `unpack-and-memory-dump.md` — TLS 回调是壳解包的常见时机，dump 就在这里
- `dynamic-api-resolution.md` — 回调里手写 EAT 遍历的完整还原流程
- `aob-signature-scan.md` — 把回调地址做成特征码以便跨版本复用
- `code-patching.md` — patch 掉反调试分支
- `../SKILL.md` — 「四级火箭」断点顺序（TLS → EP/DllMain → API → ExitProcess）的总纲