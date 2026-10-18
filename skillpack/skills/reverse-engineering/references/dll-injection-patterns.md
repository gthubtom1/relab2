# DLL 注入模式与远程内存操作

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/pe-reverse/techniques/04-dynamic-analysis/01-dll-injection.md` + `kb/pe-reverse/techniques/04-dynamic-analysis/03-external-memory-rw.md`（已适配本机工具链）
> **什么时候用**：需要在目标进程地址空间里执行自定义代码（注入 DLL），或从外部进程读写目标内存。
> 两者共用同一组底层原语（`OpenProcess` / `VirtualAllocEx` / `WriteProcessMemory`），
> 所以合在一篇 —— 注入篇讲「把代码送进去并执行」，本篇的前半段讲共同原语。
>
> **与已有文档的分工**：
> - `anti-debug-bypass.md` — ScyllaHide 注入（注入的**目的是绕过检测**）。
> - `manual-map-injection.md` — 手工实现 Windows Loader（注入的**目的是不留在模块列表**）。
> - 本篇 — 经典 `CreateRemoteThread` + `LoadLibrary` 三件套，以及**外部只读不注入**的读写路线。

## 适用信号

- 目标进程已启动，需要在它内部执行自己的代码。
- 已编译好目标架构的 DLL，想验证它在目标里的行为。
- 目标有反注入检测，需要先跑通基线再换手法。
- 只想**读**目标内存（不改、不执行）—— 走「外部读写」路线，比注入轻得多。

## 前置

```powershell
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
$cdb  = (Resolve-ReverseToolSpec -Name 'cdb').Command
$inj  = (Resolve-ReverseToolSpec -Name 'scyllahide').Command  # InjectorCLIx64.exe
$py   = (Resolve-ReverseToolSpec -Name 'pyre').Command
```

## 步骤

### 1. 找 PID（按进程名）

```python
import ctypes, ctypes.wintypes as wt
from pathlib import Path
import subprocess, json

# 方式 A：wmic（最省事，本机可用）
out = subprocess.run(["wmic", "process", "where", "name='target.exe'",
                      "get", "ProcessId", "/value"],
                     capture_output=True, text=True)
pids = [l.split("=", 1)[1].strip() for l in out.stdout.splitlines()
        if l.startswith("ProcessId=")]

# 方式 B：CreateToolhelp32Snapshot（代码内，不依赖外部命令）
k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.CreateToolhelp32Snapshot.restype = wt.HANDLE
k32.CreateToolhelp32Snapshot.argtypes = [wt.DWORD, wt.DWORD]

TH32CS_SNAPMODULE, TH32CS_SNAPPROCESS = 0x8, 0x2

class PROCESSENTRY32(ctypes.Structure):
    _fields_ = [("dwSize", wt.DWORD), ("cntUsage", wt.DWORD),
                ("th32ProcessID", wt.DWORD), ("th32DefaultHeapID", ctypes.c_size_t),
                ("th32ModuleID", wt.DWORD), ("cntThreads", wt.DWORD),
                ("th32ParentProcessID", wt.DWORD), ("pcPriClassBase", ctypes.c_long),
                ("dwFlags", wt.DWORD), ("szExeFile", wt.WCHAR * 260)]

def get_pid(name):
    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    pe = PROCESSENTRY32(); pe.dwSize = ctypes.sizeof(pe)
    res = []
    if k32.Process32FirstW(snap, ctypes.byref(pe)):
        while True:
            if pe.szExeFile.lower() == name.lower():
                res.append(pe.th32ProcessID)
            if not k32.Process32NextW(snap, ctypes.byref(pe)):
                break
    k32.CloseHandle(snap)
    return res
```

★ **`OpenProcess` 之前先确认目标还活着**。实测踩过：进程已退出时 `OpenProcess` 返回
`WinError 87 参数错误`，看起来像权限/架构问题，其实是 PID 过期。
判据是 `Get-Process -Id <pid>` 能查到。

### 2. 注入三件套（经典 `CreateRemoteThread` + `LoadLibraryA`）

**核心思路**：`LoadLibraryA` 的地址在**所有进程里相同**（同一会话，同一 ASLR 基址规则），
所以外部进程可以直接把它当线程入口用。

```python
# injector.py —— 纯 ctypes 版，参数形态已验证，注入需按样本调整
import ctypes, ctypes.wintypes as wt

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.OpenProcess.restype      = wt.HANDLE
k32.OpenProcess.argtypes      = [wt.DWORD, wt.BOOL, wt.DWORD]
k32.VirtualAllocEx.restype    = ctypes.c_void_p
k32.VirtualAllocEx.argtypes   = [wt.HANDLE, ctypes.c_void_p, ctypes.c_size_t,
                                 wt.DWORD, wt.DWORD]
k32.WriteProcessMemory.restype = wt.BOOL
k32.WriteProcessMemory.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                   ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
k32.CreateRemoteThread.restype = wt.HANDLE
k32.CreateRemoteThread.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_size_t,
                                   ctypes.c_void_p, ctypes.c_void_p,
                                   wt.DWORD, ctypes.POINTER(wt.DWORD)]

PROCESS_CREATE_THREAD  = 0x0002
PROCESS_VM_OPERATION   = 0x0008
PROCESS_VM_WRITE       = 0x0020
PROCESS_QUERY_INFO     = 0x0400
MEM_COMMIT, MEM_RESERVE, MEM_RELEASE = 0x1000, 0x2000, 0x8000
PAGE_READWRITE, PAGE_EXECUTE_READWRITE = 0x04, 0x40

def inject(pid, dll_path):
    h = k32.OpenProcess(PROCESS_CREATE_THREAD | PROCESS_VM_OPERATION |
                        PROCESS_VM_WRITE | PROCESS_QUERY_INFO, False, pid)
    if not h:
        raise ctypes.WinError(ctypes.get_last_error())
    print("1) OpenProcess OK")

    path = dll_path.encode() + b"\x00"
    remote = k32.VirtualAllocEx(h, None, len(path),
                                MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE)
    if not remote:
        raise ctypes.WinError(ctypes.get_last_error())
    print("2) VirtualAllocEx -> %s" % hex(remote))

    n = ctypes.c_size_t()
    if not k32.WriteProcessMemory(h, remote, path, len(path), ctypes.byref(n)):
        raise ctypes.WinError(ctypes.get_last_error())
    print("3) WriteProcessMemory wrote %d bytes (dll path)" % n.value)

    k32.GetModuleHandleA.restype = ctypes.c_void_p
    k32.GetModuleHandleA.argtypes = [ctypes.c_char_p]
    k32.GetProcAddress.restype   = ctypes.c_void_p
    k32.GetProcAddress.argtypes = [ctypes.c_void_p, ctypes.c_char_p]

    # ★ 关键：LoadLibraryA 在本进程解析，再当成线程入口传给远程线程
    loadlib = k32.GetProcAddress(k32.GetModuleHandleA(b"kernel32.dll"),
                                 b"LoadLibraryA")
    print("4) LoadLibraryA @ %s (same address in target)" % hex(loadlib))

    tid = wt.DWORD()
    th = k32.CreateRemoteThread(h, None, 0,
                                ctypes.c_void_p(loadlib),
                                ctypes.c_void_p(remote), 0, ctypes.byref(tid))
    if not th:
        raise ctypes.WinError(ctypes.get_last_error())
    print("5) CreateRemoteThread OK tid=%d" % tid.value)

    k32.WaitForSingleObject.restype = wt.DWORD
    k32.WaitForSingleObject.argtypes = [wt.HANDLE, wt.DWORD]
    k32.WaitForSingleObject(th, 0xFFFFFFFF)

    # 读回线程退出码 = LoadLibraryA 的返回值（模块基址，低 32 位）
    code = wt.DWORD()
    k32.GetExitCodeThread(th, ctypes.byref(code))
    print("6) LoadLibraryA returned module base = 0x%x" % code.value)
    return code.value
```

★ **`GetExitCodeThread` 返回的就是 `LoadLibraryA` 的返回值**（模块基址，低 32 位）。
非零 = DLL 已加载。这是「注入成功」最直接的判据。详见「判据」。

**注入的 DLL 侧必须做线程委派**（否则死锁）：

```c
static HMODULE g_hSelf = NULL;

BOOL WINAPI DllMain(HINSTANCE hinstDLL, DWORD fdwReason, LPVOID lpvReserved) {
    if (fdwReason == DLL_PROCESS_ATTACH) {
        g_hSelf = (HMODULE)hinstDLL;
        DisableThreadLibraryCalls(hinstDLL);   /* 避免每次线程进入都回调 */
        CreateThread(NULL, 0, MainThread, NULL, 0, NULL);  /* 重活交给它 */
    }
    return TRUE;
}

DWORD WINAPI MainThread(LPVOID) {
    /* 这里才安全：hook、读写、UI、等待目标模块加载 */
    while (!GetModuleHandleA("target.dll")) Sleep(50);  /* 等目标模块 */
    /* ... 主逻辑 ... */
    return 0;
}

void EjectSelf(void) {
    FreeLibraryAndExitThread(g_hSelf, 0);  /* 卸载自己并结束当前线程 */
}
```

★ `DllMain` 里**不能**做：调 `LoadLibrary`、等需要 loader lock 的 API、调
`WaitForSingleObject` 等刚创建的线程 —— 会死锁。

### 3. 外部读写（不注入）

只在需要读/写数据、不需要执行代码时用。比注入轻得多，检测面小得多。

```python
# extmem.py —— 纯 ctypes 外部读写
import ctypes, ctypes.wintypes as wt, struct

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.OpenProcess.restype      = wt.HANDLE
k32.OpenProcess.argtypes      = [wt.DWORD, wt.BOOL, wt.DWORD]
k32.ReadProcessMemory.restype = wt.BOOL
k32.ReadProcessMemory.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                  ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
k32.WriteProcessMemory.restype = wt.BOOL
k32.WriteProcessMemory.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                   ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]

PROCESS_VM_READ, PROCESS_VM_WRITE, PROCESS_VM_OPERATION = 0x0010, 0x0020, 0x0008

class ExtMem:
    def __init__(self, pid, write=False):
        acc = 0x0400 | 0x0010 | (0x0020 | 0x0008 if write else 0)
        self.h = k32.OpenProcess(acc, False, pid)
        if not self.h:
            raise ctypes.WinError(ctypes.get_last_error())
        self.n = ctypes.c_size_t()
        self.write = write

    def read(self, addr, size):
        buf = ctypes.create_string_buffer(size)
        if not k32.ReadProcessMemory(self.h, ctypes.c_void_p(addr),
                                     buf, size, ctypes.byref(self.n)):
            raise ctypes.WinError(ctypes.get_last_error())
        return buf.raw[:self.n.value]

    def write(self, addr, data):
        ok = k32.WriteProcessMemory(self.h, ctypes.c_void_p(addr),
                                    bytes(data), len(data), ctypes.byref(self.n))
        if not ok:
            raise ctypes.WinError(ctypes.get_last_error())
        return self.n.value

    def read_ptr(self, addr):
        return struct.unpack("<Q", self.read(addr, 8))[0]

    def follow(self, base, offsets):
        """多级指针链解析。返回 0 表示断链。"""
        a = base
        for off in offsets:
            a = self.read_ptr(a)
            if not a:
                return 0
            a += off
        return a
```

实测输出（外部读一个 624 字节的结构体）：

```
OpenProcess OK h=0000000000000094
ReadProcessMemory ok=1 got=624 of 624
+0x000 magic     = 0xc0ffee01
+0x004 pName     = "actor#0042"
+0x024 health    = 87.50
+0x028 level     = 42
+0x02C checksum  = 0x12345678
+0x190 pRoot     = 00007FF6F44B3000  <-- pointer, NOT inline
+0x268 gold      = 1000
+0x26C moveSpeed = 5.50
chain -> *pRoot+0x00 vec3 = (1.0, 2.0, 3.0)
raw bytes at +0x190 = 00 30 4b f4 f6 7f 00 00
```

★ `raw bytes at +0x190 = 00 30 4b f4 f6 7f 00 00` 是**小端 8 字节 = `0x00007ff6f44b3000`**
= 目标 image base `0x7ff6f44b0000` + RVA `0x3000`。**这是「这个槽位是指针」的硬证据**，
比反编译里的变量名可靠。判别代码见 `struct-reconstruction.md` 步骤 3。

### 4. 内部 vs 外部

| | 外部（不注入） | 内部（注入 DLL） |
|---|---|---|
| 读写方式 | `ReadProcessMemory` / `WriteProcessMemory` | 直接指针解引用 |
| 权限模型 | 独立进程，可独立运行 | 目标进程内运行 |
| 性能 | 每次读一次 syscall | 直接内存访问，极快 |
| 检测面 | 低（正常 API） | 高（DLL 在模块列表里） |
| 能改执行流 | 否 | 能（hook / 改代码） |
| 适合 | 只读数据、做雷达/分析 | hook、注入逻辑、改行为 |

**决策规则**：只需读数据 → 外部；需要执行代码或改控制流 → 内部注入。

### 5. 改受保护内存（外部也要改页保护）

外部写 `.text` 段同样要先改页保护：

```python
MEM_COMMIT, MEM_RESERVE = 0x1000, 0x2000
MEM_RELEASE, PAGE_EXECUTE_READWRITE = 0x8000, 0x40

k32.VirtualProtectEx.restype  = wt.BOOL
k32.VirtualProtectEx.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_size_t,
                                  wt.DWORD, ctypes.POINTER(wt.DWORD)]

old = wt.DWORD()
addr, n = 0x7ff6f44b1440, 5
k32.VirtualProtectEx(h, ctypes.c_void_p(addr), 5, PAGE_EXECUTE_READWRITE,
                     ctypes.byref(old))
print("oldProt = 0x%x" % old.value)
k32.WriteProcessMemory(h, ctypes.c_void_p(addr), jmp_bytes, 5, ctypes.byref(n))
k32.VirtualProtectEx(h, ctypes.c_void_p(addr), 5, old.value, ctypes.byref(n))
```

★ **记下 `oldProt` 并在写完还原**。还原时 `VirtualProtectEx` 的「新保护」参数传 `old.value`，
「旧保护」出参丢弃。判据见「判据 3」。

### 6. 注入检查清单

```
1. 架构匹配：64 位 DLL 只能注入 64 位 进程 —— 注入前先看目标 PE 头
2. 权限：PROCESS_CREATE_THREAD | VM_OPERATION | VM_WRITE 都必须开
3. 路径：必须是绝对路径，或 DLL 在目标的搜索路径里
4. 依赖：DLL 的依赖库必须在目标可访问位置（用 LoadLibrary 全路径预检）
5. DllMain 时限：DllMain 必须极短，重活交给 CreateThread
6. 目标存活：OpenProcess 失败先查 PID 是否过期
```

## 判据

1. ★★ **注入成功的判据是 `GetExitCodeThread` 返回非零**（= `LoadLibraryA` 返回的模块基址）。
   判据形态：`6) LoadLibraryA returned module base = 0x7ff7xxxxxxx`。
   **零 = 加载失败**（路径错 / 依赖缺失 / 架构不匹配）。
   次级判据：注入后用
   `Get-Process -Id <pid> | Select-Object -ExpandProperty Modules |
    Where-Object ModuleName -eq 'your.dll'`
   能查到该模块 —— 但**这个查得到反而说明模块在列表里**（手动映射要避免的，见 `manual-map-injection.md`）。
2. ★★ **外部读写的判据是「读回的值与目标自报的值一致」**，而不是「没报错」。
   实测形态：
   ```
   ReadProcessMemory ok=1 got=624 of 624
   +0x024 health    = 87.50
   ```
   `got=624 of 624`（读满，无分页错误）+ 值对得上 = 读对了。
   **若 `got < size` 或值全是 0，说明地址算错**（我第一次就踩了这个：猜 base，全 0）。
3. ★★ **页保护被正确改回**。判据形态：`VirtualProtectEx` 打印的 `oldProt=0x20`
   （`PAGE_EXECUTE_READ`），写完还原后再次 `VirtualProtectEx` 拿到 `restored prot=0x40`。
   **实测完整往返**：
   ```
   2) VProtEx  : oldProt=0x20
   3) detour   : e9 54 85 00 00 38 e8 15 02 00 00 48 8d 1d ce 1b
   4) restored : 56 53 48 83 ec 38 e8 15 02 00 00 48 8d 1d ce 1b
   ```
   第 4 行与「写之前」逐字节相同 = 保护恢复正确。
4. **指针槽位判别通过 hexdump**：判据形态是 8 字节小端拼出的值落在
   **已知模块 base + RVA** 区间内。实测 `00 30 4b f4 f6 7f 00 00` → `pointer -> module (RVA 0x3000)`。
   **若 hexdump 出的是小整数（如 `64 00 00 00 ...`），该槽位不是指针。**
5. **目标进程在操作前后都存活**。判据形态：`Get-Process -Id <pid>` 在注入前后都能查到。
   **进程中途消失 = 注入的代码崩了目标**，不是「注入成功」。

## 坑

1. ★★ **`OpenProcess` 报 `WinError 87 参数错误` 先查 PID 是不是过期**。
   我实测踩了：目标已退出，`OpenProcess` 仍返回 `WinError 87`，看起来像权限或架构问题。
   **先 `Get-Process -Id <pid>` 确认存活再排查别的。**
2. ★★ **`ctypes` 调 WinAPI 必须设 `argtypes`/`restype`**。不设时 64 位 HANDLE 被截断成 32 位。
   实测：不设时 `OpenProcess` 直接抛 `WinError 87`。这是「参数错误」最常见的真因。
3. ★★ **`$PID` 是 PowerShell 的保留自动变量**。在脚本里把进程 PID 赋给 `$PID` 会得到错误值。
   实测踩过：`$PID = (Start-Process ... | Select Id)` → 拿到别的 PID → 后续全错。
   **用 `$proc`、`$target`、`$targetPid` 等非保留名。**
4. ★ **架构必须匹配**：64 位 DLL 只能注入 64 位目标。用 `pefile` 先看 `OPTIONAL_HEADER.Magic`
   （`0x20b` = x64，`0x10b` = x86）。
5. **`VirtualAllocEx` 的 size 参数类型要设对**，否则 64 位 size 被截断。
6. **`LoadLibraryA` 的地址在同会话所有进程中相同**，所以能直接当远程线程入口。
   **但跨会话 / 跨用户可能不同** —— 那时要在目标里现场解析。
7. **`DllMain` 里 `CreateThread` 后不能 `WaitForSingleObject` 该线程** —— 会死锁。
8. **`FreeLibraryAndExitThread` 会同时卸载 DLL 并结束线程**，不能只调其一。
9. **`DisableThreadLibraryCalls` 应该在 `DllMain` 里调**，否则每次新建线程都会回调 `DllMain`。
10. **注入成功 ≠ 检测不到**。模块列表会多一项。规避见 `manual-map-injection.md`。

## 相关

- `manual-map-injection.md` — 手工实现 Loader，DLL 不进模块列表
- `naked-function-hook.md` — 注入后的典型动作：hook
- `external-memory-rw.md` — 外部读写与结构体重建的完整细节
- `anti-debug-bypass.md` — ScyllaHide 注入（另一种注入目的）
- `trampoline-detour.md` — 注入后改执行流的标准手法
- `procmon-patterns.md` — 注入行为的外部可观测痕迹（`Load Image` / `CreateRemoteThread`）
- `struct-reconstruction.md` — 外部读取的结构体偏移从哪来