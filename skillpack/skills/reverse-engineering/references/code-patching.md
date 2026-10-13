# 代码 Patch 与字节修改

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/pe-reverse/08-patch/01-code-patching.md`（已适配本机工具链）
> **什么时候用**：已定位到要改的具体地址和字节，需要把改动写进磁盘文件或运行时内存，并**验证改动生效且没改坏别的东西**。改完的二进制必须跑一次 —— 这是本篇的硬规矩。

## 适用信号

- 已定位到需要修改的目标地址（反调试分支、校验结果、常量）。
- 要禁用某个功能（NOP 掉函数体 / 把条件跳转改成恒真）。
- 要改常量（乘数、magic、超时值）。
- 要 hook 函数返回值（强制返回 TRUE/FALSE）。
- 分析用的临时改动（跳过完整性校验让它跑起来）。

## 前置

```powershell
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
$r2    = (Resolve-ReverseToolSpec -Name 'r2').Command
$rasm  = (Resolve-ReverseToolSpec -Name 'rasm2').Command
$cdb   = (Resolve-ReverseToolSpec -Name 'cdbX64').Command
$py    = 'D:\EXE\python\python.exe'   # pefile 2024.8.26
```

## 核心原则

```text
① 定位 → ② 确认原始字节 → ③ 备份/复制 → ④ 改 → ⑤ 读回校验 → ⑥ 跑一下看行为
                                                        ↑                    ↑
                                              少了⑤ = 改到了错的地方   少了⑥ = 破坏性损坏
```

**⑤ 和 ⑥ 都不能省。** 我实测中就是靠 ⑥ 抓到了一次偏移算错 —— 见「坑」3。

## 步骤

### 1. 定位并抽出原始字节

```powershell
$r2 = 'D:\Tools\radare2\bin\r2.exe'
& $r2 -2 -qc 'aaa; afl~CheckBranch; s sym.CheckBranch; pdf; q' .\ptgt2.exe
```

实测输出（完整函数反汇编）：

```
 27: sym.CheckBranch (uint32_t arg1);
|           0x140001440      55             push rbp
|           0x140001441      4889e5         mov rbp, rsp
|           0x140001444      894d10         mov dword [var_10h], ecx   ; arg1
|           0x140001447      837d1000       cmp dword [var_10h], 0
|       ,=< 0x14000144b      7507           jne 0x140001454
|       |   0x14000144d      b8c8000000     mov eax, 0xc8              ; 200
|       ,==< 0x140001452      eb05           jmp 0x140001459
|       ||   ; CODE XREF from sym.CheckBranch @ 0x14000144b(x)
|       |`-> 0x140001454      b864000000     mov eax, 0x64              ; 'd' ; 100
|       |    ; CODE XREF from sym.CheckBranch @ 0x140001452(x)
|       `--> 0x140001459      5d             pop rbp
|           0x14000145a      c3             ret
```

抽原始字节：

```powershell
& $r2 -2 -qc 's sym.CheckBranch; p8 27; q' .\ptgt2.exe
# 实测: 554889e5894d10837d10007507b8c8000000eb05b8640000005dc3
```

**动手前必须确认原始字节**。patch 的第一步永远是「我知道我要改的那几个字节长什么样」。

### 2. 确认节区可写

```powershell
& $r2 -2 -qc 'iS; q' .\ptgt2.exe
```

`perm` 列没有 `w`（如 `-r-x`）就是不可写。**磁盘文件无所谓**（文件权限和节区权限无关），但**运行时内存必须先 `VirtualProtect`**。

### 3. Patch（磁盘文件）

用 `pefile` 的 `set_bytes_at_offset` + `write`，实测完整流程：

```python
import pefile, shutil, hashlib

src = "ptgt2.exe"
dst = "ptgt2_patched.exe"

def sha256(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()

# --- 定位：AOB 找唯一命中 ---
AOB = bytes.fromhex("eb05b8640000005dc3")   # jmp +5 ; mov eax,100 ; pop rbp ; ret
data = pefile.PE(src).__data__

hits, i = [], 0
while True:
    i = data.find(AOB, i)
    if i < 0:
        break
    hits.append(i)
    i += 1

# ★ 唯一性是硬判据
assert len(hits) == 1, f"期望唯一命中，实际 {len(hits)} 处 → 特征码不够唯一"

h = hits[0]
imm_off = h + 3            # eb(1) 05(1) b8(1) → imm32 从 +3 开始
orig = data[imm_off:imm_off+4]
print("AOB context :", data[h:h+10].hex(" "))
print("orig immediate:", orig.hex(" "), "=", int.from_bytes(orig, "little"))

# --- 备份 ---
shutil.copyfile(src, dst)

# --- 改 ---
new = (9999).to_bytes(4, "little")
pe = pefile.PE(dst)
pe.set_bytes_at_offset(imm_off, new)
pe.write(dst)
pe.close()

# --- ⑤ 读回校验 ---
chk = pefile.PE(dst).__data__[imm_off:imm_off+4]
assert chk == new, "写回校验失败"
print("after         :", chk.hex(" "), "=", int.from_bytes(chk, "little"))
print("verify        : PASS")
print("sha256 before :", sha256(src))
print("sha256 after  :", sha256(dst))
```

实测输出：

```
AOB hits: ['0xa52']
AOB context : eb 05 b8 64 00 00 00 5d c3 55
orig immediate: 64 00 00 00 = 100
after         : 0f 27 00 00 = 9999
verify        : PASS
sha256 before : 22416fb46adeb2086d0e6d4cf209b0efb31f41f066a54e68702154b5f9370e1c
sha256 after  : 130fbd88074171b8a73f7e0c96731e63afa7b69fabfcb385589e583a02eb9d43
```

### 4. ⑥ 行为验证（不能省）

```powershell
Write-Host '=== 原版 ==='
& .\ptgt2.exe
Write-Host '=== 改后 ==='
& .\ptgt2_patched.exe
```

实测输出：

```
=== 原版 ===
CheckBranch(0)   = 200 (expect 200)
CheckBranch(7)   = 100 (expect 100)

=== 改后 ===
CheckBranch(0)   = 200 (expect 200)
CheckBranch(7)   = 9999 (expect 100)     ← 改动了
```

★ **改动只在预期的那一路生效**（`CheckBranch(0)` 不变、`CheckBranch(7)` 变），说明改对了位置和语义。

## 常见 Patch 模式

用 `rasm2` 拿准确的机器码（**注意 bits 影响短跳偏移**）：

```powershell
$rasm = 'D:\Tools\radare2\bin\rasm2.exe'

& $rasm -a x86 -b 64 'jne 0x7'      # -> 7505
& $rasm -a x86 -b 64 'mov eax, 9999'# -> b80f270000
& $rasm -a x86 -b 32 'jz 0x5'       # -> 7403   ★ 和 x64 不同
& $rasm -a x86 -b 64 'mov rax, 1; ret'
```

### 模式 1：NOP 填充（禁用函数）

```
原始: FF 15 <disp32>     call qword ptr [rip+disp32]   （6 字节，IAT 调用）
改后: 90 90 90 90 90 90                                   （6 × NOP）
```

### 模式 2：强制条件分支

```
74 05  (jz  +5)      →  EB 05  (jmp +5)     强制走成功分支
75 10  (jne +0x10)   →  90 90 (NOP NOP)    强制不跳过
0F 84 xx xx xx xx (jz rel32)  →  90 90 90 90 90 90   （6 字节 NOP）
0F 85 xx xx xx xx (jne rel32) →  E9 xx xx xx xx 90   （转成 rel32 jmp + 1 NOP 填充）
```

★ 短跳（`7x`）改 1 字节，长跳（`0F 8x`）改 6 字节 —— **改错长度会吃掉后面的指令**。

### 模式 3：立即数修改

```
B8 64 00 00 00      mov eax, 100
B8 0F 27 00 00      mov eax, 9999
```

本篇步骤 3 就是这个模式的完整实测。**偏移按 opcode 宽度算**：`B8` 占 1 字节所以 imm32 在 `+1`；`C7 05 <disp32> <imm32>` 要跳过 1+4 字节。

### 模式 4：函数返回值劫持

```python
# x86: 强制返回 1
RETURN_TRUE_X86 = bytes.fromhex("b801000000c3")          # mov eax,1 ; ret
# x64: 强制返回 1
RETURN_TRUE_X64 = bytes.fromhex("48c7c001000000c3")      # mov rax,1 ; ret
```

实测 `rasm2 -a x86 -b 64 'mov rax, 1; ret'` → `48c7c001000000c3`，与上式一致。

### 模式 5：运行时 patch（VirtualProtect）

`.text` 默认 RX，运行时写要先改页保护：

```python
import ctypes
from ctypes import wintypes

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.VirtualProtect.restype = wintypes.BOOL
k32.VirtualProtect.argtypes = [wintypes.LPVOID, ctypes.c_size_t,
                               wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]

PAGE_EXECUTE_READWRITE = 0x40
k32.VirtualAlloc.restype = wintypes.LPVOID
k32.VirtualAlloc.argtypes = [wintypes.LPVOID, ctypes.c_size_t,
                             wintypes.DWORD, wintypes.DWORD]
MEM_COMMIT = 0x1000
MEM_RESERVE = 0x2000

def write_protected(addr: int, payload: bytes) -> bool:
    """改页保护 → 写入 → 恢复原保护"""
    old = wintypes.DWORD()
    if not k32.VirtualProtect(ctypes.c_void_p(addr), len(payload),
                              PAGE_EXECUTE_READWRITE, ctypes.byref(old)):
        return False
    ctypes.memmove(addr, payload, len(payload))
    tmp = wintypes.DWORD()
    k32.VirtualProtect(ctypes.c_void_p(addr), len(payload),
                       old.value, ctypes.byref(tmp))
    return True

def write_jmp(addr: int, dst: int) -> bool:
    """5 字节 rel32 jmp: E9 <rel32>，rel32 = dst - addr - 5"""
    rel = dst - addr - 5
    return write_protected(addr, b"\xe9" + rel.to_bytes(4, "little", signed=True))
```

**本机 cdb 的等价操作**（无需编译注入器）。cdb 写内存的**正确命令是 `e`**（edit）：

```powershell
$cmds = "$env:TEMP\patch_cdb.txt"
@'
bu ntdll!LdrpDoDebuggerBreak
g
.echo ===BEFORE===
db 0x<模块基址>+1454 L5
e  0x<模块基址>+1454 b8 0f 27 00 00
.echo ===AFTER===
db 0x<模块基址>+1454 L5
u  0x<模块基址>+1454 L3
q
'@ | Set-Content -Path $cmds -Encoding ASCII

& $cdb -cf $cmds .\sample.exe
```

实测输出（`ptgt2.exe` 的 `CheckBranch` 里把 `mov eax, 100` 改成 `mov eax, 9999`）：

```
0:000> db 0x00007ff670001454 L5
00007ff6`70001454  b8 64 00 00 00                                   .d...
0:000> e 0x00007ff670001454 b8 0f 27 00 00
0:000> db 0x00007ff670001454 L5
00007ff6`70001454  b8 0f 27 00 00                                   ..'..
```

★ **`e` 后面是「地址 + 字节列表」，字节之间用空格**（`e 0xADDR b8 0f 27 00 00`），**不要连成一串十六进制**（`e 0xADDR b80f270000` 不认）。

★ **`eb` 不是「写字节」**。实测 `eb 0xADDR 90` 的行为是**在 `0xADDR` 处下断点并把首字节替换成 `90`** —— 实测 `db` 前后对比：写前 `b8 64 00 00 00`，写后 `90 64 00 00 00`（首字节确实变成了 `90`，因为 `eb` 就是软断点的实现）。想写就用 `e`。

★ **`.w` 在本机 cdb 上不可用**。实测 `.w 0xADDR b8 0f 27 00 00` 报 `Syntax error`，`.w -r:0 -m:0xb8 ...` 也报 `Syntax error`。用 `e`。

## 防御性检查（patch 前）

**永远先确认目标处还是原始字节** —— 否则你可能 patch 了一个已经被别的 hook 改过的地址：

```python
EXPECTED = bytes.fromhex("eb05b8640000005dc3")   # 你认定的原始字节

if data[h:h+len(EXPECTED)] == EXPECTED:
    # 还是原始代码，安全 patch
    pass
else:
    raise RuntimeError(f"目标已被修改：实际 {data[h:h+len(EXPECTED)].hex(' ')}")
```

这在样本有自校验、或者你自己已经 hook 过一次时是救命的。

## 逻辑 patch vs 公钥替换（场景取舍）

| 维度 | 逻辑 patch（改跳转/返回值） | 公钥替换 patch（换内嵌公钥） |
|---|---|---|
| 目标 | 校验分支 / 校验函数返回值 | 内嵌公钥数组 |
| 改动面 | 1~6 字节，函数级 | 公钥 blob，需同尺寸或改指针 |
| 签名机制 | 绕过验签 | 保持验签语义（自签授权通过） |
| 完整性自检风险 | 低（代码改动小） | 中（改数据；库级白名单需方法级补丁） |
| 可辩护性 | 逻辑后门 | 信任锚替换 |
| 适用 | 快速验证 / 应急 | 需要「合法 key」长期使用 |

**判定**：目标有公钥信任锚且无库级完整性自检 → 优先公钥替换（一次 patch 永久有效）；目标有库级 SHA-256 白名单 → 逻辑 patch 或方法级补丁。

## 判据

patch 成功的**外部可观测**判据，四条全过才算数：

1. **唯一性**：`AOB hits` 恰好 1 处。0 处 = 特征码错；≥2 处 = 不唯一，必须加长或限定节区。脚本里 `assert len(hits) == 1` 就是判据。
2. **读回一致**：重新打开改后的文件，目标偏移的字节 == 预期新字节。实测 `after: 0f 27 00 00 = 9999` + `verify: PASS`。
3. **行为改变且仅此一处**：实测 `CheckBranch(0)` 仍 200（未受影响）、`CheckBranch(7)` 从 100 变 9999。**只改了对的那一路**。
4. **二进制没被破坏**：改后文件能正常启动、能跑完、没崩。我第一次算错偏移时，改后的 exe **直接不输出任何东西就退出**（exit code 1）—— 这就是「结构性损坏」的表现，和「逻辑改动」截然不同。

补充：记录 patch 前后的 SHA256（实测两行都打印了），以便写进 `REVERSE-MAP.md`（本包未落地）。

### ★★ 硬约束（判据 3 "行为改变" 的验证方式）

**验证 patch 是否让控制流到达某处时，判据必须是原子 `@rip` + ≥3 轮稳定性**：
- cdb 用 `bp <addr> ".printf \"rip=%p\\n\", @rip; g"` 取**原子值**；不许把"日志里出现我自设的标记"当命中（回显也算命中）。
- 目标自翻页（`PAGE_NOACCESS`）时，断点可能被吞或报 `0n998`（**移除失败，不是命中**）。见
  `anti-debug-bypass.md` §8 与经验卡 `experience-cards/cdb-noaccess-breakpoint-is-not-hit.json`。
- **单轮命中/未命中都不定论**；运行时地址 `base+RVA` 必复核。

## 坑

1. ★★ **立即数偏移要数 opcode 宽度**。`B8 <imm32>` 的 imm32 在 **+1**（`B8` 只 1 字节）。我第一次按 +2 写，patch 出来的 exe **直接崩溃**（把 `5d c3` 即 `pop rbp; ret` 吃掉了半个 `imm32`），`ptgt2_patched.exe` 无输出、exit code 1。**判据 ⑥（跑一下）是唯一能抓住这类错误的方法。**
2. ★ **`pefile.get_offset_from_rva` 对某些二进制不可靠**。实测它把 ptgt2.exe 的 RVA `0x1454` 映到文件偏移 `0xa54`（按节表手工换算 `.text` `Raw=0x600` + `0x1454-0x1000=0x454` → `0xa54`，数字一致），但**读回的字节与 r2 反汇编对不上**。**所以优先用「原始文件内 AOB 搜索」定位，不要信 `get_offset_from_rva` 一个数就动手。**
3. ★ **`pe.write()` 会重写整个文件**，checksum、overlay、签名都可能变。patch 后必须重新验证文件结构（`pefile` 能重新打开、`r2 iI` 正常）。
4. ★ **短跳 vs 长跳的 patch 长度不同**。`7x` 改 1 字节，`0F 8x` 改 6 字节。改错长度吃掉相邻指令。
5. ★ **`rasm2` 的短跳偏移按 bits 变**。实测 `-b 64 'jne 0x7'` → `7505`，`-b 32 'jz 0x5'` → `7403`。混用会写错跳转目标。
6. **`FF 15`（call [rip+disp]）的 disp32 是 RIP 相对的**，patch 掉这条调用前要确认没有后续指令依赖 flags。
7. ★★ **cdb 写内存用 `e`，不是 `eb` 也不是 `.w`**。实测：`e 0xADDR b8 0f 27 00 00` 正确写入；`eb 0xADDR 90` 是**下软断点**（会把首字节换成 `90`，副作用）；`.w` 直接 `Syntax error`。字节之间必须空格分隔。
8. **cdb 断点必须在 `g` 之前下**；**命令串必须 `-cf <文件>`**（内联带引号经 cmd 会被转义坏，`Win32 error 0n2`）。
9. **`bu <addr> C "命令"` 在 cdb 里报错**（实测 `Couldn't resolve error`）。命令要换行分隔。
10. **`.text` 的 `perm` 无 `w`**，磁盘 patch 不受影响，但**运行时 patch 必须 `VirtualProtect(PAGE_EXECUTE_READWRITE)`**，否则 `Access Violation`。
11. **有代码完整性自检的样本 patch 后会自毁**。先确认有没有 CRC/hash 自检（见 `dynamic-api-resolution.md` 的 hash 循环识别），有的话要先 patch 自检本身。
12. **别在原始样本上直接改**。永远 `shutil.copyfile` 到新文件再改，原样本保持可复现。
13. ★★ **动态验证 patch 是否生效，判据必须是原子 `@rip` + ≥3 轮稳定性；单轮命中/未命中都不能定论。**
   patch 后常靠 cdb 断点验证控制流是否到达某处——但若目标会运行时翻页（`PAGE_NOACCESS`），
   断点可能被页翻吞掉或报 `0n998`（**那是移除失败，不是命中**）。详见经验卡
   `cdb-noaccess-breakpoint-is-not-hit` 与 `anti-debug-bypass.md` §8。运行时地址一律 `base+RVA` 复核。

## 相关

- `aob-signature-scan.md` — patch 前用 AOB 定位，以及偏移算术的坑（坑 1 的出处）
- `pe-header-parsing.md` — 节区 `perm` 与 RVA/文件偏移换算
- `anti-debug-bypass.md` — patch 反调试分支（模式 1/2 的实战）
- `unpack-and-memory-dump.md` — 有壳样本先脱壳再 patch
- `vmp-devirtualization-toolchain.md` — 虚拟化代码 patch 前的 devirt
- `yara-rule-writing.md` — patch 后把新字节喂给 YARA 做检测规则
- `../SKILL.md` — 总体流程