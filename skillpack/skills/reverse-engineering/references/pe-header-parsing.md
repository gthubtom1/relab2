# PE 头解析与节区定位

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/pe-reverse/02-pe-structure/01-pe-header-parsing.md`（已适配本机工具链）
> **什么时候用**：手上只有裸字节（内存 dump、shellcode 载体的宿主模块）或需要程序化获取模块的完整内存布局 —— 节区范围、导入导出表、RVA↔文件偏移换算。这是后面所有 AOB 扫描、TLS、脱壳、patch 的地基。

## 适用信号

- 拿到的不是文件而是**内存镜像**（`.dmp`、`pe-sieve` 的输出、`VirtualAlloc` dump 出来的 buffer）。
- 要判断「某个地址落在哪个节区」，从而决定能不能 patch、能不能执行。
- 要枚举导入表找 API，或枚举导出表找入口。
- 要做 RVA ↔ 文件偏移 ↔ 虚拟地址（VA）三向换算。
- 怀疑节区表被改过（重叠、熵异常），需要拿真实映射而不是信节名。

## 前置

```powershell
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
$r2   = (Resolve-ReverseToolSpec -Name 'r2').Command
$rasm = (Resolve-ReverseToolSpec -Name 'rasm2').Command
$diec = (Resolve-ReverseToolSpec -Name 'diec').Command
$py   = (Resolve-ReverseToolSpec -Name 'pyre').Command   # 有 pefile 2024.8.26 + capstone 5.0.7
```

> ★ `rabin2` 不可用，理由见 `aob-signature-scan.md` 坑 1。

## PE 结构速查

```
文件 / 内存镜像布局：
┌──────────────────────┐ ← 偏移 0：DOS_HEADER，e_magic = "MZ" (0x5A4D)
│  IMAGE_DOS_HEADER    │
│  e_lfanew (偏移0x3C) ─┼──→ NT 头偏移
├──────────────────────┤ ← IMAGE_NT_HEADERS，Signature = "PE\0\0" (0x00004550)
│  FileHeader          │  Machine=0x8664(x64) / 0x14C(x86)，NumberOfSections
│  OptionalHeader      │  Magic=0x20b(PE32+)/0x10b(PE32)，ImageBase，AddressOfEntryPoint
│                      │  DataDirectory[16]，第 9 项 = TLS，第 1 项 = Import，第 0 项 = Export
├──────────────────────┤ ← SECTION_HEADER[0 .. N-1]
│  IMAGE_SECTION_HEADER│  .text / .rdata / .data / .reloc / .vmp0 ...
│  VirtualAddress      │  RVA（运行时相对基址偏移）
│  PointerToRawData    │  文件偏移
│  Misc.VirtualSize    │  运行时占用大小
├──────────────────────┤ ← IMAGE_IMPORT_DESCRIPTOR[]
│  节区数据            │
├──────────────────────┤ ← IMAGE_EXPORT_DIRECTORY
│  Import Directory    │
├──────────────────────┤ ← Export Directory
└──────────────────────┘
```

**关键常量**（不要凭记忆，用前核对）：

| 字段 | 值 |
|---|---|
| `IMAGE_DOS_SIGNATURE` / `e_magic` | `0x5A4D`（"MZ"） |
| `IMAGE_NT_SIGNATURE` / `Signature` | `0x00004550`（"PE\0\0"） |
| PE32 Optional Header `Magic` | `0x10B` |
| PE32+ Optional Header `Magic` | `0x20B` |
| Machine `AMD64` | `0x8664` |
| Machine `I386` | `0x014C` |
| `IMAGE_DIRECTORY_ENTRY_EXPORT` | `0` |
| `IMAGE_DIRECTORY_ENTRY_IMPORT` | `1` |
| `IMAGE_DIRECTORY_ENTRY_TLS` | `9` |
| `IMAGE_ORDINAL_FLAG64` | `0x8000000000000000` |
| `IMAGE_ORDINAL_FLAG32` | `0x80000000` |

## 步骤

### 1. 一次性看全 PE 基础信息

```powershell
& $r2 -2 -qc 'iI; q' .\sample.exe
```

实测（notepad.exe）关键字段：

```
arch     x86
baddr    0x140000000
bits     64
bintype  pe
class    PE32+
os       windows
machine  AMD 64
subsys   Windows GUI
canary   true
pic      true
nx       true
relocs   false
signed   false
dbg_file notepad.pdb
overlay  false
```

`pic true` = 启用了 ASLR（等价于 `IMAGE_DLLCHARACTERISTICS_DYNAMIC_BASE`）。`relocs false` = 没有 `.reloc`，此时基址不可改 —— 对 AOB 扫描是好消息。

### 2. 节区表

```powershell
& $r2 -2 -qc 'iS; q' .\sample.exe
```

实测（notepad.exe）：

```
nth paddr          size vaddr          vsize perm flags      type name
0   0x00000400  0x24600 0x140001000  0x25000 -r-x 0x60000020 ---- .text
1   0x00024a00   0x9400 0x140026000   0xa000 -r-- 0x40000040 ---- .rdata
2   0x0002de00    0xe00 0x140030000   0x3000 -rw- 0xc0000040 ---- .data
3   0x0002ec00   0x1200 0x140033000   0x2000 -r-- 0x40000040 ---- .pdata
4   0x0002fe00    0x200 0x140035000   0x1000 -rw- 0xc0000040 ---- .didat
5   0x00030000    0xc00 0x140036000   0x1000 -r-- 0x40000040 ---- .rsrc
6   0x00030c00    0x400 0x140037000   0x1000 -r-- 0x42000040 ---- .reloc
```

列的含义：
- `paddr` = 文件偏移（`PointerToRawData`）
- `vaddr` = RVA（`VirtualAddress`）
- `size` / `vsize` = 原始数据大小 / 运行时大小（`SizeOfRawData` / `Misc.VirtualSize`）
- `perm` = `-r-x` 可读可执行不可写；这是判断「能否直接写」的第一依据

> `perm` 无 `w` 的节区写不进去，patch 前必须 `VirtualProtect` —— 见 `code-patching.md`。

### 3. 导入表

```powershell
& $r2 -2 -qc 'ii; q' .\sample.exe
```

实测（notepad.exe）前几行：

```
nth vaddr       bind type lib                                       name
1   0x1400268b8 NONE FUNC KERNEL32.dll                              GetProcAddress
2   0x1400268c0 NONE FUNC KERNEL32.dll                              CreateMutexExW
3   0x1400268c8 NONE FUNC KERNEL32.dll                              AcquireSRWLockShared
9   0x1400268f0 NONE FUNC KERNEL32.dll                              IsDebuggerPresent
10  0x140026900 NONE FUNC KERNEL32.dll                              GlobalFree
```

★ **`ii` 的 `vaddr` 列就是 IAT 槽位地址**，patch / hook 时直接可用。

### 4. 导出表

```powershell
& $r2 -2 -qc 'iE; q' .\sample.exe
```

实测（tlstest.dll，前 8 行）：

```
nth paddr      vaddr       bind   type size lib         name                              demangled
1   0x00000942 0x1cdb01342 GLOBAL FUNC 0    tlstest.dll Answer
0   0x00000600 0x1cdb01000 GLOBAL FUNC 0                _CRT_INIT
1   0x00000800 0x1cdb01200 GLOBAL FUNC 0                DllMainCRTStartup
2   0x000008e0 0x1cdb012e0 GLOBAL FUNC 0                atexit
5   0x00000910 0x1cdb01310 GLOBAL FUNC 0                tls_cb0
6   0x0000091e 0x1cdb0131e GLOBAL FUNC 0                tls_cb1
7   0x0000092c 0x1cdb0132c GLOBAL FUNC 0                DllMain
8   0x00000942 0x1cdb01342 GLOBAL FUNC 0                Answer
```

★ **`iE` 会把符号表里的所有符号都列出来**（`_CRT_INIT`、`atexit`、`__gcc_register_frame` 之类），不只真正的 `__declspec(dllexport)`。判断「这个符号是不是对外 API」要看 `type` 列 —— `tlstest.dll!Answer` 有库名（真导出），`atexit` 没有（只是符号表项）。

### 5. RVA ↔ 文件偏移 ↔ VA 三向换算

```python
import pefile

pe  = pefile.PE("sample.exe")
base = pe.OPTIONAL_HEADER.ImageBase
ep_rva = pe.OPTIONAL_HEADER.AddressOfEntryPoint

print(hex(base), hex(ep_rva))
print("EP file offset:", hex(pe.get_offset_from_rva(ep_rva)))

# 反向：文件偏移 -> RVA
for s in pe.sections:
    if s.PointerToRawData <= ep_rva < s.PointerToRawData + s.SizeOfRawData:
        print("in section:", s.Name.decode(errors="ignore").rstrip("\x00"))
        break

# 判断某地址落在哪个节区
def section_of(base, va):
    rva = va - base
    for s in pe.sections:
        if s.VirtualAddress <= rva < s.VirtualAddress + s.Misc_VirtualSize:
            return s.Name.decode(errors="ignore").rstrip("\x00")
    return None

print(section_of(base, base + 0x1000))   # -> '.text'
```

实测（notepad.exe）：

```
Magic: 0x20b 0x20b=PE32+ 0x10b=PE32
ImageBase: 0x140000000
EntryPoint RVA: 0x23bd0
e_lfanew: 0x100
EP file offset: 0x22fd0
```

> ★ `get_offset_from_rva` 对带 COFF 长节名的二进制（mingw 产物里那些 `/4` `/19` `/45` 节）会给出**误导性结果**。实测它把 ptgt2.exe 的 RVA `0x1454` 映到偏移 `0xa54`，而按节表手工换算应是 `0xa54`（`Raw=0x600` + `RVA 0x1454-0x1000=0x454` → `0x600+0x454=0xa54`）—— 数字一致但**读回的字节与 r2 反汇编对不上**。**永远用「按节表手工换算 + 读回字节比对」双重确认**。

### 6. 手动解析（无 pefile 时的兜底）

```python
import struct

def parse_pe(buf: bytes):
    if buf[0:2] != b"MZ":
        raise ValueError("not MZ")
    e_lfanew = struct.unpack_from("<I", buf, 0x3C)[0]
    if buf[e_lfanew:e_lfanew+4] != b"PE\0\0":
        raise ValueError("not PE")
    fh = e_lfanew + 4
    machine, nsec = struct.unpack_from("<HH", buf, fh)
    oh = fh + 20
    magic = struct.unpack_from("<H", buf, oh)[0]
    is64 = magic == 0x20B
    base = struct.unpack_from("<Q" if is64 else "<I", buf, oh + (24 if is64 else 28))[0]
    ep   = struct.unpack_from("<I", buf, oh + 16)[0]
    secs_off = oh + (112 if is64 else 96)
    secs = []
    for i in range(nsec):
        o = secs_off + i * 40
        name = buf[o:o+8].rstrip(b"\x00").decode(errors="ignore")
        vs, va, rs, ro = struct.unpack_from("<IIII", buf, o + 8)
        ch = struct.unpack_from("<I", buf, o + 36)[0]
        secs.append(dict(name=name, va=va, vs=vs, ro=ro, rs=rs, ch=ch))
    return dict(base=base, ep=ep, is64=is64, nsec=nsec, secs=secs)

import json
print(json.dumps(parse_pe(open("sample.exe","rb").read()), indent=2, default=str))
```

## 判据

1. **MZ / PE 签名双向确认**：`iI~bintype` 必须输出 `pe`；手动解析时 `buf[0:2]==b"MZ"` 且 `buf[e_lfanew:e_lfanew+4]==b"PE\0\0"` 两个断言都要过。
2. **节区表和 `pefile` 输出一致**：同一文件 r2 `iS` 的 7 个节（notepad.exe：`.text/.rdata/.data/.pdata/.didat/.rsrc/.reloc`）与 `pefile` 打印的节名/VA 逐行对得上。
3. **RVA 换算后能读回预期指令**：把 EP 的 RVA 换算成文件偏移，读回前 6 字节，用 `rasm2 -d` 反汇编应得到 `sub rsp, 0x28`（notepad.exe 实测 `4883ec28e827060000` → `sub rsp,0x28; call`）。
4. **`arch`/`bits` 与 MZ 区手动解析一致**：r2 说 `bits 64` 就手动解析必须出 `is64=True`；r2 说 `bits 32` 则 `is64=False`（x86 样本走 `%SystemRoot%\SysWOW64\*`）。
5. **地址落区判定正确**：`section_of(base, base+0x1000)` 对 notepad.exe 必须返回 `.text`（`.text` 从 RVA `0x1000` 起）。

## 坑

1. ★ **`rabin2` 在本机是坏副本**。`(Resolve-ReverseToolSpec -Name 'rabin2').Command` 与 `r2.exe` 文件大小完全相同（153600 字节），是同一份二进制的副本，`rabin2 -I/-i/-H/-e/-l` 全报 `Missing file to open`。统一走 `r2 -2 -qc`。
2. ★ **`iE` 输出远比预期长**，mingw 产物会把整个符号表都列出来（ptgt2.exe 的 `iE` 返回 74 行）。要过滤就 `iE~Answer` 或 `iE~tlstest`。
3. **`pe.get_section_by_rva` 不是稳定 API**；`pefile` 里没有 `sect_from_rva`。自己遍历 `pe.sections` 最可靠。
4. **`iI` 里 `dbg_file notepad.pdb` 直接泄露了原始 PDB 路径**，这是免费的线索，但要意识到它在告密样本里会指向构建机的用户名和目录。
5. **`.bss` 节 `paddr=0x00000000 / size=0x0`**（ptgt2.exe 实测）。只存在于内存，文件里没有内容 —— 用文件偏移换算时会越界或撞到别的节。
6. **`-2` 必须加**。r2 每次启动都往 stderr 打 `WARN: Relocs has not been applied`，会污染管道解析。

## 相关

- `aob-signature-scan.md` — 拿到节区后按节区限定做特征码扫描
- `tls-callback-analysis.md` — 本篇的 `DataDirectory[9]`（TLS）在运行时怎么用
- `dynamic-api-resolution.md` — 导入表稀疏时的替代解析路线
- `unpack-and-memory-dump.md` — 内存镜像的节区表与文件不同，必须重新解析
- `code-patching.md` — 节区 `perm` 与 `VirtualProtect` 的关系
- `../SKILL.md` — 工具探测层与总体流程