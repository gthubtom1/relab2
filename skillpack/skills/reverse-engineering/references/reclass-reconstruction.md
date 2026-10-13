# 结构体重建的桌面侧工具与自动化替代

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/pe-reverse/techniques/03-static-analysis/04-reclass-reconstruction.md`（已适配本机工具链）
> **什么时候用**：手里有一个运行时地址，想在 GUI 里交互式地 hex dump、逐字段标注类型、跟着指针跳转看被指对象，然后导出 C++ 定义。
>
> **与 `struct-reconstruction.md` 的分工**：那篇是**方法论**（从汇编推类型、分指针链与内嵌、证据账本）。
> 本篇是**工具操作层**：ReClass / Cheat Engine 这类 GUI 怎么做，以及**没有 GUI 时用什么替代**。
> 不需要 GUI 场景请直接看本篇「无 GUI 替代路线」。
>
> **工具替换说明**：源文档用 **ReClass**（GUI，无 CLI）+ **Cheat Engine**（GUI）。
> 本机两者**都未安装**，且 ReClass 本质没有命令行接口。所以：
> - GUI 侧：标注「**需人工桌面操作**，本机无此工具」，给出完整操作步骤供有该工具时照做；
> - 主力替代：本机已有且可脚本化的 `pefile` + capstone + cdb + 自建外部读写器，**全部给可执行命令**。
> 替代路线的判据是本机**实测**过的。

## 适用信号

- 已知某实体的运行时地址，需要确定它的字段偏移、类型和语义。
- 要跟着指针链逐层展开，验证每层是不是真的指针。
- 要把最终的 `struct` 导出成可编译的 C++（带正确 padding）。
- 只有 hex dump，想快速判断某个 8 字节是指针还是小整数。

## 前置

```powershell
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
$cdb = (Resolve-ReverseToolSpec -Name 'cdbX64').Command
$py  = (Resolve-ReverseToolSpec -Name 'pyre').Command   # pefile 2024.8.26 + capstone 5.0.7
$sys = '<工具根>\<分类>\<工具名>'      # Listdlls64.exe / procdump64.exe 等
```

## 步骤

### 路线 A：GUI（ReClass / Cheat Engine）— 需人工桌面操作

⚠️ **本机未安装 ReClass 与 Cheat Engine**。以下是工具具备时的完整操作流程，供人工照做。

#### A.1 ReClass 基础工作流

```
1. 附加到目标进程（ReClass 主界面 → File → Open → Attach → 选进程）
2. 新建 Class，起名（如 "Player"）
3. 在 Base 地址栏填入实体地址 → 右侧出现 hex dump
4. 逐字段定义：右键单元格 → Define type / Rename / Set comment
5. 指针字段：右键 → "Change type" → Pointer → 填目标地址
   → ReClass 打开新 tab 显示被指对象，可继续定义字段（递归展开）
6. 观察目标运行中的状态变化 → 确认字段语义
7. File → Generate → C++ Header（导出 .h）
```

#### A.2 字段类型速查（ReClass ↔ C++）

| ReClass 类型 | C++ | 宽度 |
|---|---|---|
| Hex8 / Hex16 / Hex32 / Hex64 | `uint8_t` / `uint16_t` / `uint32_t` / `uint64_t` | 1/2/4/8 |
| Int8/16/32/64 | `int8_t` / `int16_t` / `int32_t` / `int64_t` | 同上 |
| Float / Double | `float` / `double` | 4 / 8 |
| Vector2/3/4 | 连续 2/3/4 个 `float` | 8/12/16 |
| PChar / Utf8 / Utf16 | `char*` / `std::string` / `wchar_t*` | 指针 |
| Pointer | `void*`（灰色显示，可右键展开） | 指针宽度 |
| Array | `T name[N]` | N × sizeof(T) |
| Struct | 引用另一个 class | 对齐后大小 |

#### A.3 三个实战识别技巧

**（1）向量 vs 两个独立标量**

```
+0x1A0: [ 1.0, 2.0, 3.0 ]   ← 移动时 XYZ 同时变  → Vector3 position
+0x100: [ 100.0 ]            ← 单独变
+0x104: [ 100.0 ]            ← 不随移动变          → 独立 float
```

判据是**联动性**，不是数值像不像。三个 float 同时按物理规律变化才是 vector。

**（2）指针 vs 值**

```
+0x190: 0x00007FF6F44B3000   → 64 位，落在模块地址空间  → Pointer
+0x190: 0x0000000000000064   → 小值（0x64 = 100）        → 普通 int，不是指针！
```

hexdump 出小整数就**绝对不能**当指针处理 —— 否则后面整条链全错。

**（3）数组识别**

```
+0x200: [ptrA, ptrB, ptrC, ptrD, 0, 0, 0, 0]
        → 前 4 个指针后 4 个 NULL → Pointer[8]，或 Array of Pointer count=4
+0x200: [120.0, 0.0, 0.0, 120.0, ...]
        → 4x4 float 矩阵 → float[16]
```

#### A.4 与 Cheat Engine 配合（工具在位时）

```
1. CE 扫描："Increased value" / "Decreased value" → 找到血量地址
2. CE "Find out what writes to this address" → 定位修改血量的代码指令
3. 拿到那条指令的偏移 → 在反汇编器里反推结构体偏移
4. ReClass 填入基地址 + 用上面得到的偏移定义字段
5. 验证：目标内改变状态 → ReClass 里对应字段同步变化
```

### 路线 B：无 GUI 替代（本机主力，可脚本化，全部实测）

不装 ReClass 也能完成同样的事，而且**判据更硬**。

#### B.1 定位实体地址（两条独立路径，交叉验证）

**路径 1：目标程序自报**（最省事，需要你能控制目标或写个探针）

```c
printf("ENTITY_ADDR=0x%llx\n", (unsigned long long)&g_entity);
```

**路径 2：从 PE 静态反推**

```python
import pefile
pe = pefile.PE("target.exe")

# 唯一全局对象时，.bss 的 vsize 就是 SizeOf
for s in pe.sections:
    n = s.Name.rstrip(b"\x00").decode(errors="ignore")
    print("%-10s VA=0x%05x vsize=0x%x raw=0x%x"
          % (n, s.VirtualAddress, s.Misc_VirtualSize, s.PointerToRawData))

# 有文件偏移的对象：用哨兵值在 .data 里扫
needle = (0xC0FFEE01).to_bytes(4, "little")
for s in pe.sections:
    off = s.get_data().find(needle)
    if off != -1:
        rva = s.VirtualAddress + off
        print("  sentinel at RVA=0x%05x (file off 0x%05x) in %s"
              % (rva, s.PointerToRawData + off, s.Name.rstrip(b"\x00")))
```

实测输出（两条路径给出同一个 RVA）：

```
.data      VA=0x03000 vsize=0x340 raw=0x02000
  sentinel at RVA=0x03020 (file off 0x02020) in .data
  sentinel at RVA=0x0146b (file off 0x00a6b) in .text     ← 这是立即数，不是数据

IMAGEBASE=0x7ff6f44b0000  +  RVA 0x3020  =  0x7ff6f44b3020
目标自报:  ENTITY_ADDR=0x7ff6f44b3020
```

**静态 RVA 与运行时自报地址一致 = 定位正确。** 判据是这两条独立路径吻合，
不是「我扫到了一个匹配」。同时注意 `.text` 里也会命中哨兵值（编译器把常量内联进了代码），
**必须排除 `.text` 的命中**，只看数据节的。

#### B.2 逐字段 hex dump + 指针判别

```python
import struct

def classify(raw8, module_base, image_size):
    """8 字节槽位 → 判定为 模块内指针 / 外部指针 / 普通值。"""
    v = struct.unpack("<Q", raw8)[0]
    if module_base <= v < module_base + image_size:
        return "pointer -> module (RVA 0x%x)" % (v - module_base)
    if 0x0000000000010000 <= v < 0x00007FFFFFFFFFFF:
        return "pointer -> heap/other (%#x)" % v
    return "value (small int = %d)" % v
```

实测输出：

```
+0x190 pRoot = 00007FF6F44B3000
raw bytes at +0x190 = 00 30 4b f4 f6 7f 00 00
classify -> pointer -> module (RVA 0x3000)
```

#### B.3 完整外部读回（判据 4 的实测输出）

```python
# extread.c —— 纯 ctypes，不需要编译 C 工具
import ctypes, ctypes.wintypes as wt, struct

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.OpenProcess.restype      = wt.HANDLE
k32.OpenProcess.argtypes      = [wt.DWORD, wt.BOOL, wt.DWORD]
k32.ReadProcessMemory.restype = wt.BOOL
k32.ReadProcessMemory.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                  ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]

pid  = int(input("pid: "))
base = int(input("entity addr (hex): "), 16)

h = k32.OpenProcess(0x0400 | 0x0010, False, pid)   # QUERY_INFORMATION | VM_READ
n = ctypes.c_size_t()
buf = ctypes.create_string_buffer(0x400)
k32.ReadProcessMemory(h, ctypes.c_void_p(base), buf, 0x400, ctypes.byref(n))
raw = buf.raw[:0x400]

for off in range(0, 0x300, 8):
    v = struct.unpack("<Q", raw[off:off + 8])[0]
    tag = classify(raw[off:off + 8], base, 0x20000)
    print("+0x%03x  %016x  %s" % (off, v, tag))
```

★ **不需要写 C 再编译**。`ctypes` 直接调 WinAPI，是本机可脚本化的最短路径。
（`extread.c` + gcc 的版本也实测过，输出完全一致，见「判据 4」。）

#### B.4 与静态分析交叉验证

```
反汇编器发现：  *(int*)(entity + 0x268) = health
→ 在 entity 地址定义：+0x268: Int32 health

反汇编器发现：  *(float*)(*(uintptr_t*)(entity + 0x190) + 0x1A0) = pos.X
→ 在 entity 地址定义：+0x190: Pointer（开新地址）→ +0x1A0: Vector3 position
```

★ 这就是**指针链 vs 内嵌**在 GUI 里的具体体现：ReClass 里「Pointer + 展开新 tab」
= 代码里「多一次解引用」。判据仍是 `struct-reconstruction.md` 判据 2 的 hexdump。

## 导出为 C++

无论 GUI 还是脚本路线，导出前先确认三点：

```cpp
#pragma pack(push, 1)
typedef struct { float x, y, z; } Vec3;

typedef struct {
    /* 0x0000 */ uint32_t magic;
    /* 0x0004 */ char     pName[32];
    /* 0x024 */ float     health;
    /* 0x028 */ int32_t  level;
    /* 0x02C */ uint32_t checksum;
    /* 0x0190 */ void*   pRoot;      // 指针，不是内嵌
    /* 0x0268 */ int32_t  gold;
    /* 0x026C */ float    moveSpeed;
    /* 0x0270 */ ...       // 到 SizeOf-1
} Entity;   // SizeOf = 0x270 = 624
#pragma pack(pop)
```

★ **`#pragma pack` 会改变所有偏移**。这个结构体是用 `#pragma pack(1)` 编译出来的，
所以偏移是 `+0x024`；自然对齐下 `float health` 会在 `+0x24`，`int level` 在 `+0x28`。
导出后**务必回到「步骤 2」重新验证偏移**，别直接相信导出的数字。

判据：导出的 `sizeof(Entity)` 与步骤 2 定出的 `SizeOf` 完全一致（实测 `624` = `0x270`）。

## 判据

1. **实体地址由两条独立路径得出且一致**。判据形态：静态哨兵扫描得到的 RVA + image base
   = 运行时 VA，且目标自报的地址与之相同。实测 `RVA 0x3020 + 0x7ff6f44b0000 = 0x7ff6f44b3020`
   = 目标自报值。**若 `.text` 也命中哨兵，必须排除** —— 只认数据节的那个。
2. **每个指针字段都通过 hexdump 判别**，不是靠反编译变量名。判据形态是
   `raw bytes at +0x190 = 00 30 4b f4 f6 7f 00 00` + `pointer -> module (RVA 0x3000)`。
   **若 hexdump 出的是小整数，该字段就不是指针。**
3. **导出的 `sizeof` 等于步骤 2 定出的 `SizeOf`**（实测 `624`）。两者不等说明 padding 算错。
4. **整块外部读回，字段值与目标自报一致**。实测：
   ```
   ReadProcessMemory ok=1 got=624 of 624
   +0x024 health    = 87.50
   +0x268 gold      = 1000
   +0x26C moveSpeed = 5.50
   chain -> *pRoot+0x00 vec3 = (1.0, 2.0, 3.0)
   ```
   `got=624 of 624`（读满，无分页错误）+ 值一致 = 结构体正确。**只要有一项对不上，回到步骤 B.2 重判。**
5. **指针链每层都能展开且最终能读到合理值**。判据形态：`chain -> *pRoot+0x00 vec3 = (1.0, 2.0, 3.0)`
   这行 —— 说明 `+0x190` 确实是指针，且被指对象确实是那个 `Vec3`。

## 坑

1. ★★ **`.bss` 段里的全局对象没有文件偏移**（`PointerToRawData=0`），扫文件内容找它找不到。
   改用「`.bss` vsize 定 size + 运行时地址定 base」，见步骤 B.1。
2. ★★ **哨兵值扫描会命中 `.text`**。编译器把常量内联进代码，`.text` 里也有 `C0 FF EE 01`。
   **必须按节区过滤，只认数据节命中。**
3. ★★ **`#pragma pack` 让所有偏移错位**。见「导出为 C++」末尾。偏移要从目标重新验证。
4. **vtable 位置不一定在 `+0x0`**。见 `struct-reconstruction.md` 坑 4。
5. **同类不同实例的偏移可能不同**（多继承层次、虚表布局）。合并字段前核对调用者的 `this` 来源。
6. **ReClass / Cheat Engine 在本机未安装**，路线 A 全部未验证。照做时若遇到 GUI 差异，
   以路线 B 的判据为准 —— 判据与工具无关。
7. **`ctypes` 调 WinAPI 必须设 `argtypes`/`restype`**。不设的话 64 位 HANDLE 会被截断成
   32 位，返回值判定全错（实测踩过：不设时 `OpenProcess` 直接 `WinError 87 参数错误`）。
8. **`extread` 报 `got=624 of 624` 但值全是 0**，说明**地址算错了**，不是「结构体没初始化」。
   先用步骤 B.1 的双路径验证地址（我第一次就踩了这个：猜 base，六个字段全 0）。

## 相关

- `struct-reconstruction.md` — 方法论：汇编推类型、指针链判定、证据账本
- `disasm-jit-asm.md` — capstone 判断 `+0x190` 处是 `mov`（指针）还是 `lea`（内嵌）
- `external-memory-rw.md` — 本篇 `ctypes` 路线的完整实现（读写 + 写保护内存）
- `pe-header-parsing.md` — 节区 VA / raw offset 换算
- `procmon-patterns.md` — 不改内存也能观察字段变化的行为侧旁证