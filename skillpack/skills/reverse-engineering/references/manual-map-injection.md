# 手动映射注入（Manual Map）

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/pe-reverse/techniques/04-dynamic-analysis/06-manual-map-injection.md`（已适配本机工具链）
> **什么时候用**：`LoadLibrary` 注入会被发现（模块列表、加载通知、完整性自检），需要在**不调用 `LoadLibrary`** 的前提下把 DLL 映射进目标进程。
>
> **本质**：手工实现 Windows Loader 的七个动作 —— 拷 PE 头、拷节区、处理重定位、填 IAT、跑 TLS、调 `DllMain`。
>
> **与 `dll-injection-patterns.md` 的分工**：那篇是经典 `LoadLibrary` 路线（简单、兼容性最好、**模块列表里看得见**）。
> 本篇追求「不留痕」。**能用前者就别用后者** —— 手动映射的兼容性问题（异常处理表、CRT 初始化、延迟导入）多得多。

## 适用信号

- 目标有 `LdrRegisterDllNotification` 回调，会枚举模块列表。
- 目标做模块完整性自检（扫 PEB `Ldr` 链表 vs 磁盘文件哈希）。
- DLL 不需要被其他模块 `GetProcAddress` 找到（否则手动映射后模块不在列表里，`GetModuleHandle` 找不到）。

## 前置

```powershell
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
$r2  = (Resolve-ReverseToolSpec -Name 'r2').Command
$cdb = (Resolve-ReverseToolSpec -Name 'cdbX64').Command
$py  = 'D:\EXE\python\python.exe'    # pefile 2024.8.26
$sys = 'D:\Tools\Sysinternals'       # Listdlls64.exe（验证模块列表里没有它）
```

★ 本机有 gcc（`D:\Tools\runtime\mingw64\bin\gcc.exe`），需要编译 loader 时可用。

## 步骤

### 1. 七个动作（缺一不可）

```
1. 读 DLL 文件到本地缓冲区
2. 目标进程分配 VirtualAllocEx(size >= SizeOfImage)
3. 拷 PE 头（SizeOfHeaders）
4. 拷各节区到对应 RVA
5. 处理重定位（delta != 0 时）
6. 解析导入表 → 目标进程内 LoadLibrary 依赖 → 填 IAT
7. TLS 回调 → DllMain(DLL_PROCESS_ATTACH)
```

★ **第 6 步是绝大多数手写 loader 的漏洞所在**。源文档示例里写的是
`LoadLibraryA(dllName)` + `GetProcAddress` —— 但**那是外部进程的调用**！
要拿到目标进程里加载的依赖 DLL 句柄，必须把这段代码放进**目标进程**执行，
或者改走目标进程的 `LdrLoadDll`。

### 2. 读 PE 结构（本地解析）

```python
import pefile

pe = pefile.PE("mydll.dll")
dos  = pe.DOS_HEADER
nt   = pe.NT_HEADERS
opt  = opt_header = pe.OPTIONAL_HEADER

print("e_lfanew       = 0x%x" % dos.e_lfanew)
print("Machine        = 0x%04x (%s)"
      % (nt.FILE_HEADER.Machine,
         "x64" if nt.FILE_HEADER.Machine == 0x8664 else "x86"))
print("ImageBase      = 0x%x" % opt.ImageBase)
print("SizeOfImage    = 0x%x" % opt.SizeOfImage)
print("SizeOfHeaders  = 0x%x" % opt.SizeOfHeaders)
print("EntryPoint RVA = 0x%x" % opt.AddressOfEntryPoint)
print("NumberOfSections = %d" % nt.FILE_HEADER.NumberOfSections)

for s in pe.sections:
    print("  %-10s VA=0x%05x raw=0x%05x rawsz=0x%x vsz=0x%x"
          % (s.Name.rstrip(b"\x00").decode(errors="ignore"),
             s.VirtualAddress, s.PointerToRawData,
             s.SizeOfRawData, s.Misc_VirtualSize))

# 重定位表是否存在
reloc_dir = opt.DATA_DIRECTORY[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_BASERELOC"]]
print("RelocDir VA=0x%x Size=0x%x" % (reloc_dir.VirtualAddress, reloc_dir.Size))

# 导入表
import_dir = opt.DATA_DIRECTORY[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"]]
print("ImportDir VA=0x%x Size=0x%x" % (import_dir.VirtualAddress, import_dir.Size))
for e in getattr(pe, "DIRECTORY_ENTRY_IMPORT", []):
    print("  %-20s FirstThunk=0x%x OriginalFirstThunk=0x%x"
          % (e.dll.decode(), e.struct.FirstThunk,
             e.struct.OriginalFirstThunk))
```

★ **`e_lfanew` 是从 DOS 头到 NT 头的偏移**，不是绝对地址。混淆样本会把它藏起来
（见 `pe-header-parsing.md`）。取 `NT_HEADERS` 永远是 `base + e_lfanew`。

### 3. 拷头 + 拷节区

```python
data = open("mydll.dll", "rb").read()

# 拷头
headers = data[:opt.SizeOfHeaders]
n = write_remote(remote_base, headers)

# 拷节区
for s in pe.sections:
    if s.SizeOfRawData == 0:
        continue                      # .bss 之类无文件内容
    chunk = data[s.PointerToRawData : s.PointerToRawData + s.SizeOfRawData]
    write_remote(remote_base + s.VirtualAddress, chunk)
```

★ **节区之间有对齐间隙**（`VirtualAddress` 差 > `SizeOfRawData`）。那些字节必须**补零** ——
`VirtualAllocEx` 给的是零页，但如果你复用了已有内存就不是。显式补零最保险。

★ `.bss`（`SizeOfRawData == 0`）在文件里没有内容，但 `VirtualSize` 很大。
分配时按 `SizeOfImage` 走（它已经包含 `.bss`），不要按文件大小。

### 4. 处理重定位

```python
IMAGE_REL_BASED_HIGHLOW = 3
IMAGE_REL_BASED_DIR64    = 10

def apply_relocations(remote, data, delta):
    """在【远程进程】的映射内存上应用重定位。
    注意：这里必须对目标进程内存操作，外部只能先读出来算好再写回。
    """
    rva = opt.DATA_DIRECTORY[
        pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_BASERELOC"]].VirtualAddress
    size = opt.DATA_DIRECTORY[
        pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_BASERELOC"]].Size
    if not rva or not size or delta == 0:
        return 0

    off, count = 0, 0
    while off < size:
        page_rva, block_size = struct.unpack_from("<II", data, rva + off)
        if block_size == 0:
            break
        n_entries = (block_size - 8) // 2
        for i in range(n_entries):
            entry = struct.unpack_from("<H", data, rva + off + 8 + i * 2)[0]
            typ   = entry >> 12
            o     = entry & 0xFFF
            addr  = remote + page_rva + o
            if   typ == IMAGE_REL_BASED_DIR64:
                write_remote(addr, struct.pack("<q", read_remote(addr, 8) + delta)); count += 1
            elif typ == IMAGE_REL_BASED_HIGHLOW:
                write_remote(addr, struct.pack("<i", read_remote(addr, 4) + delta)); count += 1
        off += block_size
    return count
```

★ **`delta = remote_base - ImageBase`**。若 `VirtualAllocEx` 传 `NULL` 让系统选地址，
`delta` 几乎必然非零 —— **必须处理**。若能让 `VirtualAllocEx` 精确返回 `ImageBase`（传非 NULL 地址），
可以跳过重定位，但现代 Windows 上这常常失败，别指望。

★ 目标 DLL 必须有重定位表（`.reloc` 节）。用 `reloc -c` 之类选项剥离了重定位的 DLL
**无法手动映射**到别处 —— 这是硬限制。判据：步骤 2 打印的 `RelocDir VA=0x0` = 不可用。

### 5. 填 IAT（必须在目标进程内做）

```python
def fill_iat_in_target(image_base_in_target):
    """这段代码必须跑在【目标进程】里（作为 shellcode 或注入线程）。

    遍历导入描述符表，逐个解析并写入目标进程的 IAT。
    """

    remote = image_base_in_target
    rva  = opt.DATA_DIRECTORY[IMAGE_DIRECTORY_ENTRY_IMPORT].VirtualAddress
    off  = rva
    while True:
        ilt_rva, ts, fwd, name_rva, iat_rva = struct.unpack_from("<IIIII", mem, off)
        if name_rva == 0:
            break
        dll_name = read_cstr(remote + name_rva)

        # ★ 关键：用【目标进程】的 LdrLoadDll，不能用外部的 LoadLibraryA
        hmod = ldr_load_dll_in_target(dll_name)     # 见下

        # 遍历 ILT（OriginalFirstThunk），把解析结果写进 IAT（FirstThunk）
        p_ilt = remote + (ilt_rva or iat_rva)
        p_iat = remote + iat_rva
        while True:
            thunk = read_qword(p_ilt)
            if thunk == 0:
                break
            if thunk & (1 << 63):                    # 序号导入
                proc = ldr_get_proc_by_ordinal(hmod, thunk & 0xFFFF)
            else:
                hint_name_rva = thunk & 0x7FFFFFFF
                proc = ldr_get_proc_by_name(hmod, read_cstr(remote + hint_name_rva + 2))
            write_qword(p_iat, proc)
            p_ilt += 8; p_iat += 8
        off += 20
    return iat_rva
```

★ **`LdrGetProcedureAddress`** 是解析 IAT 的正确入口（它处理 forwarder 和 API set）。
直接调 `GetProcAddress` 在跨模块时可能失败。

### 6. 调 DllMain（shellcode）

```python
import struct
from capstone import Cs, CS_ARCH_X86, CS_MODE_64

def build_dllmain_shellcode(image_base, entry_point):
    """x64 调用 DllMain(imageBase, DLL_PROCESS_ATTACH=1, NULL) 的 shellcode。"""
    sc = bytearray()
    sc += bytes.fromhex("4883ec28")                             # sub rsp, 0x28
    sc += b"\x48\xb9" + struct.pack("<Q", image_base)          # mov rcx, imageBase
    sc += b"\x48\xc7\xc2" + struct.pack("<I", 1)               # mov rdx, 1 (ATTACH)
    sc += b"\x4d\x31\xc0"                                       # xor r8, r8
    sc += b"\x48\xb8" + struct.pack("<Q", entry_point)          # mov rax, entryPoint
    sc += b"\xff\xd0"                                           # call rax
    sc += b"\x48\x83\xc4\x28"                                   # add rsp, 0x28
    sc += b"\xc3"                                               # ret
    return bytes(sc)
```

**实测反汇编回环**（`D:\EXE\python\python.exe`，本机 capstone 5.0.7）：

```
48 83 ec 28 48 b9 20 30 4b f4 f6 7f 00 00 48 c7 c2 01 00 00 00
4d 31 c0 48 b8 00 31 4b f4 f6 7f 00 00 ff d0 48 83 c4 28 c3

   sub                    rsp, 0x28
   movabs                 rcx, 0x7ff6f44b3020
   mov                    rdx, 1
   xor                    r8, r8
   movabs                 rax, 0x7ff6f44b3100
   call                   rax
   add                    rsp, 0x28
   ret
```

★ `movabs` 是 capstone 对 `48 B9+r` 的助记符，不是特殊指令（见 `disasm-jit-asm.md` 坑 10）。

★ **`sub rsp, 0x28` 是必须的**：Windows x64 ABI 要求 32 字节 shadow space，
`call rax` 之前不给就会踩坏调用者的栈。

### 7. 跑起来

<!-- ▲ CTypes 调用片段（缺 import 与函数上下文，片段） -->
```python
sc_addr = VirtualAllocEx(h, None, len(sc), MEM_COMMIT|MEM_RESERVE, PAGE_EXECUTE_READWRITE)
WriteProcessMemory(h, sc_addr, sc, len(sc), &n)
tid = DWORD()
CreateRemoteThread(h, None, 0, sc_addr, None, 0, &tid)
WaitForSingleObject(th, INFINITE)
```

## 判据

1. ★★ **模块列表里没有这个 DLL**。判据形态：
   ```powershell
   & 'D:\Tools\Sysinternals\Listdlls64.exe' /accepteula /t target.exe |
     Select-String -Pattern 'mydll'
   ```
   **无输出 = 手动映射成功（对「不留痕」这个目标而言）。**
   有输出 = 走了 `LoadLibrary` 路线，或者 loader 之后自己把它登记了。
   **这是本篇唯一真正能证明「不留痕」的判据。**
2. **`DllMain` 真的执行了**。判据形态：在 `DllMain` 里写一个可观测副作用
   （建文件 / 注册表 / 网络请求），然后 `procmon-patterns.md` 的过滤器里能看到它，
   或直接检查文件/注册表存在。**「没崩」不等于「执行了」。**
3. **IAT 全部解析成功，无 NULL**。判据形态：扫描远程镜像的 IAT 区，
   每个 `FirstThunk` 条目都非零，且落在某个已加载模块的地址范围内。
   **IAT 里有 NULL = 第 5 步没做对**，后续调用该函数就会 access violation。
4. **重定位条数 > 0 且都落在有效地址上**。判据形态：`apply_relocations` 返回的 `count`，
   且 `delta != 0` 时 `count` 必须 > 0。**`delta != 0` 但 `count == 0` = 没应用重定位
   = 所有全局指针都指向错误位置。**
5. **目标原功能未被破坏**。判据形态：目标仍能正常完成它原本的工作
   （打印、文件、网络请求）。**手动映射破坏 CRT 初始化或异常处理表时，
   症状是「目标在特定错误路径崩溃」而不是「映射失败」** —— 很难查，先确认前四条。

## 坑

1. ★★ **源文档示例的 `ProcessImports` 用外部进程的 `LoadLibraryA`/`GetProcAddress` —— 这是错的**。
   那样拿到的是**外部进程**里的依赖模块句柄，写进目标进程的 IAT 会是**跨进程的野指针**。
   必须在目标进程内用 `LdrGetProcedureAddress` 解析。
2. ★★ **目标必须保留 `.reloc` 节**。剥掉重定位的 DLL（`reloc -c`）**无法映射到别处**。
   判据：步骤 2 打印 `RelocDir VA=0x0` = 这个 DLL 不能手动映射。
3. ★★ **`VirtualAllocEx` 传 `NULL` 时 `delta` 几乎必然非零**，必须处理重定位。
   `delta == 0` 只在「恰好分配到 `ImageBase`」时成立 —— 别指望。
4. ★ **节区对齐间隙必须补零**。复用已有内存时那些字节是脏数据。
5. **TLS 回调顺序**：手动映射必须**在 `DllMain` 之前**跑 TLS 回调，且顺序要正确。
   漏掉这一步，反调试 / 反注入逻辑放在 TLS 里就不会执行（也可能是好事，取决于目的）。
6. **异常处理表（`.pdata` / `.xdata`）不注册 = C++ 异常在映射区里会崩**。
   完整 loader 还要调 `RtlAddFunctionTable`。
7. **`DllMain` 的 loader lock 规则照样适用**。手动映射不改变这一点 —— 重活仍要 `CreateThread`。
8. **手动映射的 DLL 不会被后续的 `LoadLibrary` 找到**（不在模块列表）。
   如果目标代码 `GetModuleHandleA("mydll.dll")`，会返回 NULL。
9. **全局/静态初始化（CRT）不跑**。手动映射只调 `DllMain`，不跑 CRT 的 `_initterm`。
   用到 CRT 的 DLL 会出问题。
10. **本机只有 gcc，没有 MSVC**。需要编译 loader 时用
    `D:\Tools\runtime\mingw64\bin\gcc.exe`，命令形态：
    `gcc -O2 -o loader.exe loader.c -static -s`。
11. **x86/x64 混淆**。64 位 PE 只能映射进 64 位进程（例外是 wow64，复杂且本篇不覆盖）。

## 相关

- `dll-injection-patterns.md` — 经典 `LoadLibrary` 路线（**先试那个**）
- `disasm-jit-asm.md` — shellcode 字节构造与反汇编验证
- `pe-header-parsing.md` — `e_lfanew` / 节区表 / 重定位表的解析
- `procmon-patterns.md` — 判据 2 的行为侧证据（怎么看到 `DllMain` 的副作用）
- `trampoline-detour.md` — 映射进来的 DLL 典型动作就是 hook
- `direct-syscall.md` — 目标有用户态 hook 时，解析 IAT 可能被干扰