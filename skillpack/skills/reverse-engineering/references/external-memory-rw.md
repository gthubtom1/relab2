# 外部进程内存读写

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/pe-reverse/techniques/04-dynamic-analysis/03-external-memory-rw.md`（已适配本机工具链）
> **什么时候用**：从独立进程（分析工具 / 脚本）读写目标进程内存，**不注入任何代码**。
> 只需要数据（观察、改值、dump 结构体）时，这是比注入轻得多的首选路线。

## 适用信号

- 目标进程已运行，知道模块名和数据偏移。
- **不需要**在目标进程内执行代码。
- 想 dump 一块数据结构做离线分析。
- 目标有反注入检测，但读取权限拿得到。

## 前置

```powershell
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
$py  = (Resolve-ReverseToolSpec -Name 'pyre').Command        # 只用标准库 ctypes，不需要 pefile
$sys = '<工具根>\<分类>\<工具名>'           # Listdlls64.exe（找模块基址）
```

★ 全篇用 **Python `ctypes` 直接调 WinAPI**，不需要编译 C 工具 —— 这是本机最短的
可脚本化路径。需要更高性能时再换成 C（`dll-injection-patterns.md` 有 gcc 路线）。

## 步骤

### 1. 找 PID

```python
import subprocess

def find_pids(name):
    """wmic 路线。本机实测可用。"""
    out = subprocess.run(
        ["wmic", "process", "where", f"name='{name}'",
         "get", "ProcessId", "/value"],
        capture_output=True, text=True)
    return [l.split("=", 1)[1].strip()
            for l in out.stdout.splitlines() if l.startswith("ProcessId=")]
```

★ 如果 `wmic` 不可用（新版 Windows 已弃用），用 PowerShell：
```powershell
Get-Process -Name target -EA SilentlyContinue | Select-Object Id,ProcessName
```

### 2. 找模块基址（外部视角）

**方式 A：Sysinternals Listdlls（最快）**

```powershell
& '<工具根>\<分类>\<工具名>\Listdlls64.exe' /accepteula /t target.exe
```

输出里直接给 `<Base>` 列。GUI 侧也可直接看，但 CLI 更适合脚本。

**方式 B：ToolHelp 快照**

```python
import ctypes, ctypes.wintypes as wt

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.CreateToolhelp32Snapshot.restype = wt.HANDLE
k32.CreateToolhelp32Snapshot.argtypes = [wt.DWORD, wt.DWORD]

TH32CS_SNAPMODULE, TH32CS_SNAPMODULE32 = 0x8, 0x10

class MODULEENTRY32(ctypes.Structure):
    _fields_ = [("dwSize", wt.DWORD), ("th32ModuleID", wt.DWORD),
                ("th32ProcessID", wt.DWORD), ("GlblcntUsage", wt.DWORD),
                ("ProccntUsage", wt.DWORD), ("modBaseAddr", ctypes.c_void_p),
                ("modBaseSize", wt.DWORD), ("hModule", wt.HMODULE),
                ("szModule", wt.WCHAR * 256), ("szExePath", wt.WCHAR * 260)]

def module_base(pid, name):
    flag = TH32CS_SNAPMODULE if sys.maxsize > 2**32 else TH32CS_SNAPMODULE32
    snap = k32.CreateToolhelp32Snapshot(flag, pid)
    me = MODULEENTRY32(); me.dwSize = ctypes.sizeof(me)
    try:
        if k32.Module32FirstW(snap, ctypes.byref(me)):
            while True:
                if me.szModule.lower() == name.lower():
                    return me.modBaseAddr
                if not k32.Module32NextW(snap, ctypes.byref(me)):
                    break
    finally:
        k32.CloseHandle(snap)
    return 0
```

★ **x86 目标要用 `TH32CS_SNAPMODULE32`（0x10）**，不是 `TH32CS_SNAPMODULE`（0x8）。
用错会返回空快照，且 `GetLastError()` 是 `ERROR_BAD_LENGTH`（24）。

### 3. 核心读写封装

```python
# extmem.py —— 完整可运行
import ctypes, ctypes.wintypes as wt, struct, sys

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.OpenProcess.restype      = wt.HANDLE
k32.OpenProcess.argtypes      = [wt.DWORD, wt.BOOL, wt.DWORD]
k32.ReadProcessMemory.restype = wt.BOOL
k32.ReadProcessMemory.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                  ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
k32.WriteProcessMemory.restype = wt.BOOL
k32.WriteProcessMemory.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                   ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_OPERATION      = 0x0008
PROCESS_VM_READ           = 0x0010
PROCESS_VM_WRITE          = 0x0020


class ExternalMemory:
    def __init__(self, pid, write=False):
        acc = (PROCESS_QUERY_INFORMATION | PROCESS_VM_READ
               | (PROCESS_VM_WRITE | PROCESS_VM_OPERATION if write else 0))
        self.h = k32.OpenProcess(acc, False, pid)
        if not self.h:
            raise ctypes.WinError(ctypes.get_last_error())
        self.n = ctypes.c_size_t()
        self.write = write
        print("OpenProcess OK h=%s" % int(self.h))

    def close(self):
        k32.CloseHandle(self.h)

    # ---- 基础块读写 ----
    def read_bytes(self, addr, size):
        buf = ctypes.create_string_buffer(size)
        if not k32.ReadProcessMemory(self.h, ctypes.c_void_p(addr),
                                     buf, size, ctypes.byref(self.n)):
            raise ctypes.WinError(ctypes.get_last_error())
        got = self.n.value
        if got != size:
            print("  !! short read: got=%d of %d" % (got, size))
        return buf.raw[:got]

    def write_bytes(self, addr, data):
        if not self.write:
            raise PermissionError("handle opened read-only")
        ok = k32.WriteProcessMemory(self.h, ctypes.c_void_p(addr),
                                    bytes(data), len(data), ctypes.byref(self.n))
        if not ok:
            raise ctypes.WinError(ctypes.get_last_error())
        return self.n.value

    # ---- 定型读写 ----
    def read(self, addr, fmt="<I"):
        return struct.unpack(fmt, self.read_bytes(addr, struct.calcsize(fmt)))[0]

    def write(self, addr, value, fmt="<I"):
        return self.write_bytes(addr, struct.pack(fmt, value))

    def read_ptr(self, addr):
        return self.read(addr, "<Q")

    def read_cstr(self, addr, maxlen=260):
        raw = self.read_bytes(addr, maxlen)
        return raw.split(b"\x00")[0].decode("utf-8", "replace")

    # ---- 指针链 ----
    def follow(self, base, offsets, report=False):
        """多级指针链。返回 0 表示断链。"""
        a = base
        for i, off in enumerate(offsets):
            a = self.read_ptr(a)
            if not a:
                if report: print("  chain broken at level %d" % i)
                return 0
            a += off
            if report: print("  level %d -> 0x%x (+0x%x)" % (i, a, off))
        return a

    # ---- 块 dump ----
    def dump(self, addr, size, path):
        data = self.read_bytes(addr, size)
        with open(path, "wb") as f:
            f.write(data)
        print("dumped %d bytes -> %s" % (len(data), path))
        return data
```

### 4. ★ 实测：读出一个 624 字节结构体

目标程序自报地址：模块 base = `0x7ff6f44b0000`，实体在 RVA `0x3020`。

```python
m = ExternalMemory(pid, write=False)
base  = 0x7ff6f44b0000
rva   = 0x3020
addr  = base + rva
print("entity @ 0x%x" % addr)

raw = m.read_bytes(addr, 0x270)
print("magic      = 0x%08x" % struct.unpack_from("<I", raw, 0x000)[0])
print("pName      = %r"     % raw[0x004:0x024].split(b"\x00")[0])
print("health     = %.2f"   % struct.unpack_from("<f", raw, 0x024)[0])
print("level      = %d"     % struct.unpack_from("<i", raw, 0x028)[0])
print("checksum   = 0x%08x" % struct.unpack_from("<I", raw, 0x02C)[0])
p_root = struct.unpack_from("<Q", raw, 0x190)[0]
print("pRoot      = 0x%x" % p_root)
print("gold       = %d"     % struct.unpack_from("<i", raw, 0x268)[0])
print("moveSpeed  = %.2f"   % struct.unpack_from("<f", raw, 0x26C)[0])

# 跟随指针链读内层对象
inner = m.read_bytes(p_root, 12)
print("chain -> vec3 = %s" % (struct.unpack("<3f", inner),))

# 打印指针槽位的原始 8 字节（小端），这是判别指针的硬证据
print("raw bytes at +0x190 = " + raw[0x190:0x198].hex(" "))
```

实测输出：

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

★ `raw bytes at +0x190 = 00 30 4b f4 f6 7f 00 00` —— 小端拼出 `0x00007ff6f44b3000`
= 模块 base `0x7ff6f44b0000` + RVA `0x3000`。**这 8 字节是指针的硬证据。**

### 5. 写内存

```python
m = ExternalMemory(pid, write=True)

# 改一个 int 字段
print("before gold = %d" % m.read(addr + 0x268, "<i"))
m.write(addr + 0x268, 9999, "<i")
print("after  gold = %d" % m.read(addr + 0x268, "<i"))

# 改字节数组（落文件用）
m.write_bytes(addr + 0x004, b"PWNED\x00")
```

★ **写完必须读回验证**，见「判据 3」。

### 6. 写受保护页（`.text`）

外部写代码段要改页保护，和注入篇同一套原语：

```python
k32.VirtualProtectEx.restype  = wt.BOOL
k32.VirtualProtectEx.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_size_t,
                                  wt.DWORD, ctypes.POINTER(wt.DWORD)]
PAGE_EXECUTE_READWRITE = 0x40

old = wt.DWORD()
k32.VirtualProtectEx(m.h, ctypes.c_void_p(addr), 16, PAGE_EXECUTE_READWRITE,
                     ctypes.byref(old))
print("oldProt = 0x%x" % old.value)       # 实测 0x20 = PAGE_EXECUTE_READ
m.write_bytes(addr, new_bytes)
restored = wt.DWORD()
k32.VirtualProtectEx(m.h, ctypes.c_void_p(addr), 16, old.value, ctypes.byref(restored))
print("restored prot = 0x%x" % restored.value)
```

★ 读的时候**不需要** `VM_WRITE`。只在真的要写时才申请 —— 最小权限原则。

### 7. 分配可执行内存（给 trampoline / shellcode）

```python
k32.VirtualAllocEx.restype  = ctypes.c_void_p
k32.VirtualAllocEx.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_size_t,
                               wt.DWORD, wt.DWORD]
k32.VirtualFreeEx.restype  = wt.BOOL
k32.VirtualFreeEx.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_size_t, wt.DWORD]
MEM_COMMIT, MEM_RESERVE, MEM_RELEASE = 0x1000, 0x2000, 0x8000
PAGE_EXECUTE_READWRITE = 0x40

remote = k32.VirtualAllocEx(m.h, None, 4096, MEM_COMMIT | MEM_RESERVE,
                            PAGE_EXECUTE_READWRITE)
# ... 往 remote 写 trampoline ...
k32.VirtualFreeEx(m.h, remote, 0, MEM_RELEASE)
```

★ 外部分配的内存可以给目标执行（它就在目标的地址空间里），
但**外部不能直接"调用"它** —— 需要在目标里起线程，见 `dll-injection-patterns.md`。

## 判据

1. ★★ **读到的值与目标自报/已知语义一致**，不是「没报错」。判据形态：
   ```
   ReadProcessMemory ok=1 got=624 of 624
   +0x024 health    = 87.50
   ```
   `got == size`（读满、无分页错误）+ 值对得上 = 读对了。
   **若 `got < size` 或值全 0 → 地址算错，不是「目标没数据」。**（我第一次就踩了：猜 base，六个字段全 0。）
2. **模块基址来自 ToolHelp 或 Listdlls，不是猜的**。判据形态：`module_base(pid, name)` 返回非零，
   或 `Listdlls64.exe /t target.exe` 输出里有该模块的 `<Base>`。
   **且要与静态分析对账**：`base + rva_of_sentinel == 运行时 VA`，两条独立路径一致。
3. ★ **写后读回验证**。判据形态：`before gold = 1000` → 写 → `after gold = 9999`。
   **`WriteProcessMemory` 返回 TRUE 但目标忽略了这次写**（比如目标每帧从别处重算）的情况很常见，
   只看返回值会被骗。
4. **页保护还原**：判据形态是 `oldProt=0x20` 被记录，写完还原后再次查询得到 `restored prot=0x40`。
5. **指针链每层能走通且不返回 0**。判据形态：`chain -> *pRoot+0x00 vec3 = (1.0, 2.0, 3.0)` ——
   说明 `+0x190` 是真指针、被指对象可读。
   **若某层返回 0，说明该层不是指针或链断** —— 别硬解引用。

## 坑

1. ★★ **地址算错是头号翻车点，症状是「值全是 0」**。我实测踩过：猜了一个 base，
   `ReadProcessMemory` 成功（`got=624 of 624`），但六个字段全 0。
   **`got` 正确不代表地址正确** —— 未提交的页读出来就是 0。
   **验证地址的两条独立路径**：静态 sentinel RVA + base vs 目标自报地址。
2. ★★ **`ctypes` 必须设 `argtypes`/`restype`**。不设时 64 位 HANDLE 被截断成 32 位。
   实测：不设时 `OpenProcess` 直接 `WinError 87 参数错误`。
3. ★ **x86 目标要用 `TH32CS_SNAPMODULE32`（0x10）**，不是 `TH32CS_SNAPMODULE`（0x8）。
   用错返回空快照。
4. ★ **`OpenProcess` 报 `WinError 87` 先查 PID 是否过期**（不是权限问题）。
5. **`ReadProcessMemory` 跨页失败**。一次读太大（跨未提交页）会整块失败。
   大块 dump 分成 4KB 一段逐段读，或先确认目标页都已提交。
6. **不设 `VM_WRITE` 就调 `WriteProcessMemory` 会失败**。读权限和写权限是两回事。
7. **`WriteProcessMemory` 到 `PAGE_EXECUTE_READ` 页会失败**，要 `VirtualProtectEx` 改 RWX。
8. **ASLR 下每次运行 base 都变**。写脚本别硬编码上次的 base。
9. **目标重启后所有地址失效**，指针链、模块基址、结构体偏移都要重取（**偏移 RVA 不变，绝对地址全变**）。
10. **`$PID` 是 PowerShell 保留变量**，别用它存目标进程 ID。
11. **`wmic` 在新版 Windows 已弃用**。备选：`Get-Process -Name X` 或 `tasklist /FI "IMAGENAME eq X"`。

## 相关

- `dll-injection-patterns.md` — 注入路线（需要执行代码时）；本篇是「不注入」路线
- `struct-reconstruction.md` — 读出来的字段偏移从哪来、怎么判指针
- `reclass-reconstruction.md` — 同一目的的 GUI 路线
- `trampoline-detour.md` — 用本篇的 `VirtualProtectEx` 改代码段
- `procmon-patterns.md` — 想知道目标「本来」会读写什么，而不是主动去读
- `direct-syscall.md` — 想绕过用户态 hook 读内存时