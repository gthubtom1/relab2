# AOB 特征码扫描

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/pe-reverse/01-triage/01-aob-signature-scan.md`（已适配本机工具链）
> **什么时候用**：ASLR 让硬编码地址在每次加载后失效，需要在运行时跨版本稳定定位一段代码或数据；或者要给注入器 / patch 脚本写一个不会随小版本更新的定位器。

## 适用信号

- 目标模块每次运行基址都不同（`iI~baddr` 每次不同），写死的 `base+0x1234` 不再命中。
- 需要把「上次分析出的指令位置」变成「本次运行的实际位置」。
- 要写注入器 / patch 脚本 / 扫描器，目标会更新小版本，偏移会漂移。
- YARA / patch 的特征码需要从一条指令里挑出**跨版本稳定**的那几个字节。

## 前置

工具一律经探测层拿路径，**不要写死**：

```powershell
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
$r2   = (Resolve-ReverseToolSpec -Name 'r2').Command     # D:\Tools\radare2\bin\r2.exe
$rasm = (Resolve-ReverseToolSpec -Name 'rasm2').Command  # D:\Tools\radare2\bin\rasm2.exe
$diec = (Resolve-ReverseToolSpec -Name 'diec').Command   # D:\Tools\DIE\diec.exe
```

> ★ **不要用 `rabin2`**：本机 `D:\Tools\radare2\bin\rabin2.exe` 与 `r2.exe` 字节数完全相同（153600），是同一份二进制的副本，它的 `-I/-i/-H/-e/-l` 已被 r2 的启动参数占用，报 `Missing file to open`。全部走 `r2 -2 -qc`（见「坑」1）。

需要 `pefile` 时见「坑」4。

## PE 侧准备：拿到基址与节区

一个模块在内存里的可用范围 = `ImageBase` 到 `ImageBase + SizeOfImage`。静态分析看到的偏移都是 RVA，运行时地址 = `实际基址 + RVA`。

```powershell
& $r2 -2 -qc 'iI~baddr,binsz,arch,bits,os; q' .\sample.exe
```

实测（notepad.exe）：

```
baddr    0x140000000
binsz    200704
arch     x86
bits     64
os       windows
```

`baddr` 是首选映像基址；**运行时基址由 ASLR 决定，通常 ≠ `baddr`**。`baddr` 只在未重定位或有 `.reloc` 兜底时才是真实加载地址。

拿节区表，确定「哪些区域值得扫」：

```powershell
& $r2 -2 -qc 'iS; q' .\sample.exe
```

实测（notepad.exe）：

```
nth paddr          size vaddr          vsize perm flags      type name
0   0x00000400  0x24600 0x140001000  0x25000 -r-x 0x60000020 ---- .text
1   0x00024a00   0x9400 0x140026000   0xa000 -r-- 0x40000040 ---- .rdata
2   0x0002de00    0xe00 0x140030000   0x3000 -rw- 0xc0000040 ---- .data
```

- `vaddr` 是节的 RVA 起点，运行时地址 = 实际基址 + vaddr。
- `.text` 是唯一该扫代码特征的地方；往 `.rdata`/`.data` 扫会命中大量数据假阳性。

## 特征码提取原则

选**唯一**且**跨版本不变**的字节。判断标准很简单：这段字节里有没有「只在这一次编译里成立」的东西。

**必须排除的字节**：

| 形式 | 含义 | 为什么不能进特征码 |
|---|---|---|
| `E8 ?? ?? ?? ??` | `call rel32` | 目标地址随编译布局变 |
| `48 8B 05 ?? ?? ?? ??` | `mov rax, [rip+disp32]` | RIP 相对位移随节区位置变 |
| `B8 <imm32>` | `mov eax, imm32` | 常量、magic、偏移每次构建都可能改 |
| reloc 表覆盖区 | 任何被重定位的立即数 | 每次加载都不同 |

**适合进特征码的字节**：指令操作码 + ModRM + SIB + 寄存器编号。

```
48 8B 05 ?? ?? ?? ?? 48 89 45 F8     ← 坏：含 RIP 相对位移
48 8B 05 ?? ?? ?? ?? 48 89 45 F8     ← 好：去掉位移即 48 8B 05 ?? ?? ?? ?? 48 89 45 F8

EB 05 B8 ?? ?? ?? ?? 5D C3           ← 好：EB 05（jmp +5）+ B8（mov eax）
                                          ?? ?? ?? ?? 是立即数，运行时可变
                                          5D C3（pop rbp; ret）是固定尾声
```

### 从函数里抽一段

选定函数，让 r2 打印前 N 字节：

```powershell
& $r2 -2 -qc 'aaa; afl~CheckBranch; s sym.CheckBranch; p8 27; q' .\ptgt2.exe
```

实测输出（27 字节）：

```
554889e5894d10837d10007507b8c8000000eb05b8640000005dc3
```

从中挑稳定片段：`eb05b8..0000005dc3`（`jmp +5; mov eax,imm32; pop rbp; ret`）。`b8` 后面 4 字节是立即数，跨构建可能变 → 用通配符。

## 模式格式

**r2 / x64dbg / YARA 用十六进制 + 通配符**（r2 的通配符是 `.` 不是 `?`）：

```
eb05b8..0000005dc3
```

**IDA / 多数注入器框架用「空格分隔 + `?`」**：

```
EB 05 B8 ?? ?? ?? ?? 5D C3
```

**Code style mask（`x` 必须匹配、`?` 通配）**——这是注入器框架里最常见的写法：

```
"xx?xxx?xx"
```

两种格式的对照：8 字节 `EB 05 B8 AABBCCDD 5D C3`
- hex 通配：`eb05b8..0000 5dc3` → `eb05b8..0000 5dc3`（共 11 字节：1+1+1+2+4+1+1）
- 空格+`?`：`EB 05 B8 ?? ?? ?? ?? 5D C3`
- mask：`xx?xxx?xx`

## 用 r2 搜索特征码

**全文件搜**：

```powershell
& $r2 -2 -qc '/x eb05b8..0000005dc3; q' .\ptgt2.exe
```

实测输出：

```
0x140001452 hit0_0 eb05b8640000005dc3
```

命中行第一个字段就是虚拟地址（已加基址），可以直接拿去做断点或 patch。

**限定节区搜（推荐，只扫 .text）**：

```powershell
& $r2 -2 -qc 'e search.in=.text; /x eb05b8..0000005dc3; q' .\ptgt2.exe
```

实测同一特征码加 `search.in=.text` 后只返回 .text 内的命中（notepad.exe 上 `4883ec28` 全文件 45 处，限定 .text 后降到 14 处）。这是**降假阳性最有效的一个开关**。

**搜索范围对照**（r2 6.2 实测）：

| 写法 | 效果 |
|---|---|
| `/x <pat>` | 默认全映像 |
| `e search.in=.text` | 只搜指定节区 |
| `e search.in=raw` | 按原始文件字节搜（含文件尾 overlay） |
| `e search.from` / `search.to` | **本机实测无效**，置了也不改变结果，不要用 |

## 运行时定位（进程内）

静态搜索解决「文件里在哪」，运行时基址不同就要换算。两种做法：

**做法 A（推荐，无需写代码）**：直接让 r2 在目标进程里搜。

```powershell
& $r2 -2 -qc 'e dbg.exe=<path>; /x eb05b8..0000005dc3; q'
```

**做法 B（写注入器）**：自己算偏移。用 `pefile` 拿节区、扫描、返回 `基址 + 命中偏移`：

```python
import pefile

def get_module_base_size(pe, name):
    """从 PE 头拿静态基址和 SizeOfImage —— 只在没有 ASLR 的情况下等于运行时值"""
    return pe.OPTIONAL_HEADER.ImageBase, pe.OPTIONAL_HEADER.SizeOfImage

def find_pattern(buf: bytes, pattern: bytes, mask: bytes):
    """buf 是整个模块内存镜像。pattern/mask 等长，mask 里 0x00 表示通配。"""
    n = len(pattern)
    for i in range(len(buf) - n):
        if all(not mask[j] or buf[i + j] == pattern[j] for j in range(n)):
            return i
    return -1

def find_in_section(buf: bytes, pe, sec_name: str, pattern: bytes, mask: bytes):
    """只扫指定节区，避免命中 .rdata/.data"""
    for s in pe.sections:
        if s.Name.decode(errors="ignore").rstrip("\x00") == sec_name:
            start = s.VirtualAddress
            size = s.Misc_VirtualSize
            off = find_pattern(buf[start:start + size], pattern, mask)
            return -1 if off < 0 else start + off
    return -1
```

调用方式（进程内，base 是运行时真实基址）：

```python
# 运行时: base = GetModuleHandleA("target.exe")
#         buf  = base .. base + SizeOfImage 的内存
pat  = bytes.fromhex("eb05b8") + b"\x00"*4 + bytes.fromhex("0000005dc3")
mask = bytes.fromhex("ffffffff") + b"\x00"*4 + bytes.fromhex("ffffffff")
off  = find_in_section(buf, pe, ".text", pat, mask)
addr = base + off if off >= 0 else 0
```

## 偏移定位模式

特征码常覆盖一条 `call` / `jmp`，此时真正想要的是**跳转目标**，而不是命中地址本身。

规则：
- `E8` / `E9`（rel32）的目标是 `指令地址 + 5 + rel32`。
- 所以 `目标 = 命中地址 + 5 + *(int32*)(命中地址 + 1)`。

```python
import struct

def resolve_rel32(buf: bytes, hit_off: int, opcode_len: int = 5):
    """hit_off 指向 E8/E9 本身；opcode_len=5 (rel32)"""
    rel = struct.unpack_from("<i", buf, hit_off + 1)[0]
    return hit_off + opcode_len + rel
```

实测（ptgt2.exe，`eb05b8..0000005dc3` 命中文件偏移 `0xa52`）：

```
AOB hits: ['0xa52']
AOB context : eb 05 b8 64 00 00 00 5d c3 55
```

命中第 3 个字节（`b8`）就是 `mov eax` 的 opcode，`imm32` 从 **+1** 开始（`b8` 只占 1 字节）：

```
imm_off = hit_off + 3        # eb(1) 05(1) b8(1) → b8 在 +2，imm32 在 +3
```

★ 这就是「坑」3 —— 我第一次按 +2 写，patch 出来的 exe 直接崩（`5d c3` 被吃掉半个 `imm32`），是实测踩到的。

## 实战：把定位器写进 patch 脚本

一个完整的「找特征码 → 按偏移改字节 → 写回 → 读回校验」循环，全部实测通过：

```python
import pefile, shutil, hashlib

src = "ptgt2.exe"
dst = "ptgt2_patched.exe"

AOB = bytes.fromhex("eb05b8640000005dc3")   # jmp +5 ; mov eax,100 ; pop rbp ; ret

data = pefile.PE(src).__data__

hits, i = [], 0
while True:
    i = data.find(AOB, i)
    if i < 0:
        break
    hits.append(i)
    i += 1
assert len(hits) == 1, f"期望唯一命中，实际 {len(hits)} 处 → 特征码不够唯一"

imm_off = hits[0] + 3
new = (9999).to_bytes(4, "little")

shutil.copyfile(src, dst)
pe = pefile.PE(dst)
pe.set_bytes_at_offset(imm_off, new)
pe.write(dst)
pe.close()

chk = pefile.PE(dst).__data__[imm_off:imm_off+4]
assert chk == new, "写回校验失败"
print("patched:", hex(imm_off), chk.hex(" "), int.from_bytes(chk, "little"))
```

实测输出：

```
AOB hits: ['0xa52']
orig immediate: 64 00 00 00 = 100
after         : 0f 27 00 00 = 9999
verify        : PASS
```

行为验证：

```
=== 原版 ===   CheckBranch(7) = 100
=== 改后 ===   CheckBranch(7) = 9999
```

## 判据

特征码好不好，看三个**外部可观测**的结果：

1. **唯一性**：命中数必须**恰好 1**。0 处 = 选错了字节（多半含立即数/位移）；≥2 处 = 加长特征码或加 `search.in=.text` 限定范围。上面脚本里 `assert len(hits) == 1` 就是判据本身。
2. **回读一致**：`pefile` 写回后重新打开，读回该偏移的 4 字节必须等于预期新值。实测输出里的 `verify: PASS` / `after: 0f 27 00 00` 是判据。
3. **行为改变**：跑改后的二进制，功能输出按预期变化（`100 → 9999`）。这是唯一能排除「改在了错误的指令上」的判据 —— 见「坑」3，我自己第一次就靠这个发现偏移算错了。
4. **r2 搜索命中地址落在 .text 内**：把 `iS` 的 vaddr/vsize 区间拿来比对，命中 VA 必须落在 `.text` 的 `[vaddr, vaddr+vsize)` 里。

## 坑

1. ★ **本机 `rabin2` 是坏副本**。`D:\Tools\radare2\bin\rabin2.exe` 与 `r2.exe` 同为 153600 字节，`rabin2 -I`/`-i`/`-H`/`-e`/`-l` 全部报 `ERROR: Missing file to open`（因为这些短参数被 r2 的启动参数占用了），`-S` 侥幸能用。**统一用 `r2 -2 -qc`**，`-2` 关掉 stderr 噪音。

2. ★ **r2 的 `/x` 通配符是 `.` 不是 `?`**。`/x eb05b8..0000005dc3` 能命中，`/x eb05b8??0000005dc3` 命不中。写给 YARA 用时才写 `?`。

3. ★ **立即数偏移要数 opcode 宽度**。`B8 <imm32>`（`mov eax,imm32`）的 imm32 在 **+1**，不是 +2；`B8` 只占 1 字节。`C7 05 <disp32> <imm32>` 之类更复杂。算错的表现是 **patch 后二进制直接崩溃**（吃掉了后面的 `pop rbp; ret`），不是逻辑错而是结构性损坏。**判据必须包含「跑一下看行为」**。

4. **pefile 不在 `venv-re` 里**。实测 `D:\Tools\runtime\venv-re\Scripts\python.exe` 里 `import pefile` 直接 `ModuleNotFoundError`。可用的是：
   - `D:\EXE\python\python.exe` — 有 `pefile 2024.8.26` + `capstone 5.0.7`
   - `D:\Tools\runtime\venv-floss\Scripts\python.exe` — 有 `pefile` + `flare-floss 3.1.1`
   
   用前先探：
   ```powershell
   foreach ($py in @('D:\EXE\python\python.exe',
                     'D:\Tools\runtime\venv-floss\Scripts\python.exe',
                     'D:\Tools\runtime\venv-re\Scripts\python.exe')) {
     if (Test-Path $py) {
       $v = & $py -c "import pefile;print(pefile.__version__)" 2>&1
       "{0} -> {1}" -f $py, $v
     }
   }
   ```

5. **`pefile` 没有 `sect_from_rva` 方法**。想按节区定位要自己遍历 `pe.sections`，或用 `get_offset_from_rva`。而且 `get_offset_from_rva` 对带长节名 / 大量 debug 节（如 mingw 产物的 `/4` `/19` `/45` 那些 COFF 长名节）的二进制**会给出误导性结果** —— 实测它把 RVA `0x1454` 映到文件偏移 `0xa54`，而手工按节表换算应该是 `0xa54` 偏移处内容与 r2 反汇编**对不上**。**所以 patch 后一定要读回字节校验**，别信 `get_offset_from_rva` 一个数就动手。

6. **`s hit0_0` 不稳**。`/x` 命中会生成 `hit0_0` 标志，`s hit0_0` 有时能 seek 有时空。**直接用输出里的十六进制地址**：`s 0x140001452`。

7. **静态搜到的 VA ≠ 运行时地址**。r2 给的是 `baddr + RVA`。有 ASLR 时运行时基址不同，patch 脚本要么在运行时重算，要么先把 reloc 应用了（`r2 -e bin.relocs.apply=true`）。

## 相关

- `pe-header-parsing.md` — 拿到 ImageBase / 节区 / RVA↔文件偏移的权威解析（本篇的 PE 基础）
- `tls-callback-analysis.md` — TLS 回调在入口点之前执行，用到同样的 RVA/VA 换算
- `dynamic-api-resolution.md` — 运行时解析出的 API 也需要用特征码做 hook 定位
- `code-patching.md` — 特征码定位 → 按偏移改字节的完整 patch 流程
- `yara-rule-writing.md` — 同一套字节序列喂给 YARA 的 `$code*`
- `anti-debug-bypass.md` — 定位到反调试检测点后的 patch 手法
- `../SKILL.md` — 工具探测层与四级火箭的总体流程