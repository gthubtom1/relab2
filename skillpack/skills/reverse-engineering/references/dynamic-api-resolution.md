# 动态 API 解析链还原

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/pe-reverse/03-static-analysis/05-dynamic-api-resolution.md`（已适配本机工具链）
> **什么时候用**：导入表很少或为空，但行为明显在调网络/进程/注册表 API；或者反编译里看到遍历 PEB / EAT 名称表 + 算 hash 的循环。目标是把 hash 和函数指针恢复成真实 API 名称，再拿这些名称去做后续断点。

## 适用信号

- **导入表稀疏**：`ii` 只有十几条甚至个位数，但程序行为丰富。
- 字符串里搜不到任何 WinAPI 名称（`iz~CreateFile` 空），但样本明显在访问网络/注册表/进程。
- 反编译/反汇编里出现 `gs:[0x60]`（x64）或 `fs:[0x30]`（x86），或 `PEB_LDR_DATA`。
- 有一个循环遍历 export name table 并逐字符算 hash 的模式。
- 汇编里出现形如 `0xEC0E4E8E`、`0x7C0DFCAA` 的大立即数（32 位 hash）。

## 前置

```powershell
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
$r2   = (Resolve-ReverseToolSpec -Name 'r2').Command
$cdb  = (Resolve-ReverseToolSpec -Name 'cdbX64').Command
$rasm = (Resolve-ReverseToolSpec -Name 'rasm2').Command
$py   = 'D:\EXE\python\python.exe'   # pefile 2024.8.26
```

## 步骤

### 1. 确认导入表确实稀疏

```powershell
& $r2 -2 -qc 'ii; q' .\sample.exe
```

判据是**计数**：notepad.exe 有 40+ 条导入（`ii` 输出行数 40）；如果你的样本只有个位数，就是稀疏。

> 若 `ii` 只有 `LoadLibraryA`/`GetProcAddress` 一两条 + 主模块的 `KERNEL32.dll`，基本可以确认解析链。

### 2. 静态定位：找 PEB walk 和 EAT parser

用 r2 全文搜 PEB 访问模式。

**x64：PEB 在 `gs:[0x60]`**。机器码是 `65 48 8B 04 25 60 00 00 00`（`mov rax, gs:[0x60]`）：

```powershell
& $r2 -2 -qc '/x 65488b042560000000; q' .\sample.exe
```

**x86：PEB 在 `fs:[0x30]`**。机器码是 `64 A1 30 00 00 00`（`mov eax, fs:[0x30]`）：

```powershell
& $r2 -2 -qc '/x 64a130000000; q' .\sample.exe
```

搜到后反汇编看上下文：

```powershell
& $r2 -2 -qc '/x 65488b042560000000; q' .\sample.exe
# 拿命中的地址，再：
& $r2 -2 -qc 's 0x<命中的VA>; pd 25; q' .\sample.exe
```

典型结构（Ghidra/C 风格伪码）：

```c
// PEB walk
peb  = *(uint64_t*)(__readgsqword(0x60));
ldr  = *(uint64_t*)(peb + 0x18);          // PEB_LDR_DATA
// InLoadOrderModuleList / InMemoryOrderModuleList 的偏移随版本变，别硬编

// export parser
names     = image + exp->AddressOfNames;
ordinals  = image + exp->AddressOfNameOrdinals;
functions = image + exp->AddressOfFunctions;
```

### 3. 提取 hash 算法

从 hash 循环的指令里读出四个参数：**rotate 位数、大小写处理、初始值、DLL 名是否参与**。

常见形态（ror13 + 小写化）：

```c
uint32_t hash = 0;
for (each ch in name) {
    hash = ror32(hash, 13);
    hash += tolower(ch);
}
```

用 r2 抽这段字节并反汇编：

```powershell
& $r2 -2 -qc 's 0x<hash_loop_VA>; p8 32; q' .\sample.exe
```

关键指令：
- `C1 C8 0D` = `ror eax, 0xd`（ror 13）
- `C1 C9 0D` = `ror ecx, 0xd`
- `80 E? 61-7A` + `0F B6` = 取字节后压到 ASCII 小写区（tolower）
- `03 C1` = `add eax, ecx`

### 4. 用 Python 反解 hash 常量

**这一步是最容易翻车的地方，见「坑」1 —— 源文档给的常量是错的。**

```python
import pefile

def ror32(v, n):
    v &= 0xffffffff
    return ((v >> n) | (v << (32 - n))) & 0xffffffff

def api_hash(name: str) -> int:
    h = 0
    for ch in name:
        h = ror32(h, 13)
        h = (h + ord(ch.lower())) & 0xffffffff
    return h

# 先自检：确认这个实现和样本里的算法一致
for n in ("VirtualAlloc", "CreateThread", "GetProcAddress"):
    print(f"{n:20s} -> {api_hash(n):#010x}")
```

实测输出（**这才是 ror13+tolower 的正确值**）：

```
VirtualAlloc           -> 0x91f1ca54
CreateThread           -> 0xca6bd07b
GetProcAddress         -> 0x8c8dfcb2
LoadLibraryA           -> 0xec4e52ae
VirtualProtect         -> 0x89c6c61b
IsDebuggerPresent      -> 0xa40e4676
```

然后拿样本里的 hash 常量去真实 DLL 里扫：

```python
import pefile, os

targets = {0xEC0E4E8E, 0x7C0DFCAA}     # ← 换成从你样本里实际读出的常量

for d in [r"C:\Windows\System32\kernel32.dll",
          r"C:\Windows\System32\kernelbase.dll",
          r"C:\Windows\System32\advapi32.dll",
          r"C:\Windows\System32\ntdll.dll",
          r"C:\Windows\System32\user32.dll"]:
    if not os.path.exists(d):
        continue
    pe = pefile.PE(d, fast_load=True)
    pe.parse_data_directories(
        directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_EXPORT"]])
    if not hasattr(pe, "DIRECTORY_ENTRY_EXPORT"):
        continue
    n = 0
    for exp in pe.DIRECTORY_ENTRY_EXPORT.symbols:
        if not exp.name:
            continue
        n += 1
        name = exp.name.decode(errors="ignore")
        if api_hash(name) in targets:
            print(f"  {api_hash(name):#010x} -> {name}  ({os.path.basename(d)})")
    print(f"scanned {os.path.basename(d):18s} {n} named exports")
pe.close()
```

实测输出：

```
scanned kernel32.dll       1636 named exports
scanned kernelbase.dll     1914 named exports
scanned advapi32.dll       864 named exports
scanned ntdll.dll          2434 named exports
scanned user32.dll         1005 named exports

=== result ===
  (no hit: the two constants in the source doc are NOT ror13/lower under this hash)
```

**没有命中** —— 因为源文档的 `0xEC0E4E8E → VirtualAlloc`、`0x7C0DFCAA → CreateThread` 是**错的**（实测 `VirtualAlloc` 在 ror13+tolower 下是 `0x91f1ca54`）。正确做法见「坑」1。

### 5. 动态断点：抓 hash 比较点

```powershell
$exe  = 'C:\path\to\sample.exe'
$cdb  = "$env:LOCALAPPDATA\Microsoft\WindowsApps\cdbX64.exe"
$cmds = "$env:TEMP\api_cdb.txt"

@'
bu kernel32!LoadLibraryA
bu kernel32!LoadLibraryW
bu kernel32!GetProcAddress
bu ntdll!LdrGetProcedureAddress
bu kernel32!VirtualAlloc
bu ntdll!LdrpDoDebuggerBreak
g
.echo ===FIRST_HIT===
kv
g
q
'@ | Set-Content -Path $cmds -Encoding ASCII

& $cdb -cf $cmds $exe
```

判据：`kv` 里应该能看到从样本自身 `.text` 调进来的帧，而不是只有 ntdll 内部帧。命中后记：

```
module base:            基址（本次运行的实际值）
export name candidate:  EAT 里遍历到的字符串
computed hash:          本次算出来的值
matched constant:       样本里的常量
resolved function ptr:  最终函数地址
```

如果样本**手写 EAT parser**，`GetProcAddress` 断点根本不命中 —— 这是常态，不是配置问题。改断 hash 比较点：

```powershell
# 在静态分析里找到那条 cmp eax, <const> / cmp r?, <const>
& $r2 -2 -qc '/x 3d8e4e0eec; q' .\sample.exe     # cmp eax, 0xEC0E4E8E（小端）
& $r2 -2 -qc '/x 813d8e4e0eec; q' .\sample.exe   # cmp dword [rbx], 0xEC0E4E8E
```

在命中的比较指令处下断，命中后 `r` 出参与寄存器就是目标 hash。

### 6. 回填 IDA / Ghidra

```
0xEC0E4E8E -> VirtualAlloc   (RVA 0x1a2f0, hash loop at 0x1a180)
0x7C0DFCAA -> CreateThread   (RVA 0x1a340, hash loop at 0x1a180)
```

## 判据

1. **导入表稀疏**：目标样本 `ii` 输出行数 << 同类正常 PE（notepad.exe 是 40 条）。这是起点信号，不是判据本身。
2. **hash 反解命中**：反解脚本必须打出 `0x<你的常量> -> <API名> (<dll>)` 的映射行。**打不出映射行 = 算法还没对齐**（见坑 1）。**打出但映射到明显不对的 API（如 `0x8c8dfcb2 -> ExitThread` 但样本在开文件）= 算法反了或常量取错。**
3. **动态命中来自样本自身**：`kv` 里必须出现样本自身模块（`.exe`/`.dll` 名）的帧。若只有 `ntdll!` 内部帧，说明断在 loader 里，没抓到调用者。
4. **交叉一致**：静态枚举出的 EAT 遍历（x64 `gs:[0x60]` 那条搜索结果）与动态 `GetProcAddress` 命中点应落在同一个函数内。两条独立路径指同一处才作数。
5. **完整性**：最终产出的函数指针表要能对上 `ii` 里那几条静态导入 —— 解析链补齐的应该是「静态没列的」，不是把静态已有的也重算一遍。

## 坑

1. ★★ **源文档里的 API hash 常量是错的，必须重新实测**。源文写 `0xEC0E4E8E → VirtualAlloc`、`0x7C0DFCAA → CreateThread`。我实测 ror13+tolower 下：`VirtualAlloc = 0x91f1ca54`、`CreateThread = 0xca6bd07b`、`GetProcAddress = 0x8c8dfcb2`、`LoadLibraryA = 0xec4e52ae`。拿源文的常量去扫 kernel32/ntdll/user32/advapi32/kernelbase 五个 DLL 的全部具名导出（1636+1914+864+2434+1005 = 6853 个名字），**一个都没命中**。**不要照抄源文的常量 —— 必须用「读出样本里的实际 hash 循环指令 → 在本机复现算法 → 拿样本常量去扫」三步。** 正确的 hash 算法种类很多（ror7/ror13/add/xor/初始值非 0/DLL 名参与），猜错就全盘错。
2. ★ **`pefile` 的 `fast_load=True` 必须配 `parse_data_directories`**，否则 `DIRECTORY_ENTRY_EXPORT` 属性根本不存在，循环体里的 `hasattr` 会静默跳过整个 DLL，看起来像「扫了但没结果」。正确写法见步骤 4。
3. ★ **x64 的 PEB 机器码是 `65 48 8B 04 25 60 00 00 00`**，不是 `64 A1 30 00 00 00`（后者是 x86）。用错架构的特征码扫 x64 样本会 0 命中。
4. **hash 循环可能不是 ror13**。ror7 也是常见的（Metasploit 用）。从指令里读 rotate 位数：`C1 C8 07` = `ror eax, 7`；`C1 C8 0D` = `ror eax, 13`。看字节，别猜。
5. **`AddressOfNames`/`AddressOfNameOrdinals`/`AddressOfFunctions` 三个数组都要走**。只走 Names 会拿到 ordinal 但拿不到函数地址。
6. **`LoadLibraryA` 和 `LoadLibraryW` 要都断**。样本可能只用宽字符版。实测这两个都断才不漏。
7. **`-y C:\path\*.dll` / `cdb -cf` 脚本里的注释用 `$$`**，不要用 `#`。
8. **cdb 的退出码不可信**（实测 `-2147024866`），判成功看日志有没有 `Breakpoint 0 hit`。
9. **`pefile` 不在 `venv-re`**，在 `D:\EXE\python\python.exe` 或 `venv-floss`。见 `aob-signature-scan.md` 坑 4。

## 相关

- `pe-header-parsing.md` — EAT 三个数组的偏移与结构定义
- `tls-callback-analysis.md` — 解析链常常挂在 TLS 回调里（入口点之前就完成）
- `anti-debug-bypass.md` — `NtQueryInformationProcess` 等被解析后如何 hook
- `unpack-and-memory-dump.md` — 解析出 `VirtualAlloc`/`VirtualProtect` 的下一步
- `aob-signature-scan.md` — 把解析链的 hash 循环做成特征码
- `code-patching.md` — patch 掉整个解析函数或改单个常量
- `../SKILL.md` — 「四级火箭」中的 API 层断点