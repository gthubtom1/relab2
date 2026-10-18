# 反汇编与机器码生成（capstone / rasm2 / r2）

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/pe-reverse/techniques/03-static-analysis/02-disasm-jit-asm.md`（已适配本机工具链）
> **什么时候用**：需要把字节解码成可读汇编，或把汇编意图变成精确的机器码 —— hook 跳板、syscall stub、shellcode 构造、指令边界判定。
>
> **工具替换说明**：源文档用 Zydis（解码）+ Xbyak（生成），**本机都没装**。已全部替换为：
> - 解码 → `(Resolve-ReverseToolSpec -Name 'pyre').Command` + `import capstone`（capstone 5.0.6，实测可用）
> - 汇编 → `rasm2 -a x86 -b 64 -s 0x0 "<asm>"`（radare2 套件自带）
> - 大段反汇编 → `r2 -qc 'pd N'`
>
> **与 `aob-signature-scan.md` 的分工**：那篇做「字节模式 → 在大二进制里定位」；本篇做「给定地址/字节 ↔ 汇编文本」的双向转换，是那篇的编解码原语。

## 适用信号

- 已拿到某地址的原始字节，需要知道它到底是几条指令、边界在哪。
- 要构造跳板/stub，需要精确控制生成的机器码。
- hook 前必须确认「覆盖 5 字节」不会切断某条指令。
- 需要验证一段 shellcode 的字节是否等价于预期的汇编。

## 前置

```powershell
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
$r2   = (Resolve-ReverseToolSpec -Name 'r2').Command      # (Resolve-ReverseToolSpec -Name 'r2').Command
$rasm = (Resolve-ReverseToolSpec -Name 'rasm2').Command  # (Resolve-ReverseToolSpec -Name 'rasm2').Command
$py   = (Resolve-ReverseToolSpec -Name 'pyre').Command                        # capstone 5.0.6
```

★ **`rasm2` 必须带 `-s 0x0`**。不带 `-s` 时 stdout 为空、exit code 却是 0 —— 极易误判成「汇编失败」。

## 步骤

### 1. rasm2：汇编 → 字节（本机实测形态）

```powershell
& $rasm -a x86 -b 64 -s 0x0 "mov r10, rcx"
& $rasm -a x86 -b 64 -s 0x0 "mov eax, 0x18"
& $rasm -a x86 -b 64 -s 0x0 "syscall"
& $rasm -a x86 -b 64 -s 0x0 "ret"
& $rasm -a x86 -b 64 -s 0x0 "sub rsp, 0x28"
& $rasm -a x86 -b 64 -s 0x0 "xor r8, r8"
& $rasm -a x86 -b 64 -s 0x0 "jne 0x7"
& $rasm -a x86 -b 64 -s 0x0 "mov eax, 9999"
```

实测输出：

```
4989ca
b818000000
0f05
c3
4883ec28
4d31c0
7505
b80f270000
```

★ `-s 0x0` 是起始地址。**相对跳转的偏移随 `-s` 变化** —— `jne 0x7` 在 `-s 0x0` 下是 `7505`；
若地址不同必须重算。绝不能把这里的偏移抄到别处用。

★ `-b 32` 与 `-b 64` 对短跳转给出不同结果。实测 `rasm2 -a x86 -b 32 'jz 0x5'` → `7403`，与 x64 结果不同，别混用。

### 2. capstone：字节 → 汇编（主力解码器）

单条指令：

```python
from capstone import Cs, CS_ARCH_X86, CS_MODE_64

md = Cs(CS_ARCH_X86, CS_MODE_64)
md.detail = True        # 想要操作数类型信息（.operands / .op_size）必须开

for ins in md.disasm(data, base_addr):
    print("0x%x (+%d) len=%d  %s %s"
          % (ins.address, ins.address - base_addr, ins.size,
             ins.mnemonic, ins.op_str))
```

连续一段（decode-loop，遇到非法字节输出 `db` 并前进 1 字节，不中断）：

```python
def disasm_range(data, base, length=None):
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    if length is not None:
        data = data[:length]
    out, offset = [], 0
    while offset < len(data):
        got = False
        for ins in md.disasm(data[offset:offset + 15], base + offset):
            out.append("0x%x (+%d) len=%d  %s %s"
                       % (ins.address, ins.address - base, ins.size,
                          ins.mnemonic, ins.op_str))
            offset += ins.size
            got = True
            break
        if not got:
            out.append("db 0x%02x" % data[offset])   # 非法/数据字节
            offset += 1
    return out
```

★ **每次喂给 capstone 的切片必须 ≥ 15 字节**（x64 最长指令 15）。喂太短会在指令中间失败，
你的 decode-loop 会误输出 `db 0x..` 并把字节当数据 —— 这是 hook 边界算错的头号原因。

### 3. r2：大批量反汇编（看上下文用）

```powershell
# 从某地址反汇编 25 条
& $r2 -2 -qc 's 0x00007ff6f44b3020; pd 25; q' .\target.exe
# 打印原始字节
& $r2 -2 -qc 's 0x00007ff6f44b3020; p8 32; q' .\target.exe
```

`pd` 适合快速浏览；需要精确边界/类型判断时回到 capstone。

### 4. ★ 用反汇编确定 Hook 安全边界（本机实测）

hook 覆盖 ≥5 字节（`JMP rel32`）是硬要求，但**必须落在指令边界上**。
naive「取前 5 字节」会在变长指令中间截断，产生非法指令流。

```python
# hookbd.py — 实测脚本
import pefile
from capstone import Cs, CS_ARCH_X86, CS_MODE_64

md = Cs(CS_ARCH_X86, CS_MODE_64)
md.detail = True

def detour_size(data, base, minimum=5):
    """逐条累加指令长度，直到覆盖 >= minimum 字节。"""
    total, n = 0, 0
    for ins in md.disasm(data, base):
        print("  0x%x (+%d) len=%d  %s %s"
              % (ins.address, ins.address - base, ins.size,
                 ins.mnemonic, ins.op_str))
        total += ins.size
        n += 1
        if total >= minimum:
            break
    return total, n

u = pefile.PE(r"C:\Windows\System32\user32.dll", fast_load=True)
u.parse_data_directories(directories=[
    pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_EXPORT"]])
for s in u.DIRECTORY_ENTRY_EXPORT.symbols:
    if s.name and s.name == b"MessageBoxW":
        rva, code = s.address, u.get_data(s.address, 0x40)
        print("user32!MessageBoxW rva=0x%x" % rva)
        print("first 16 bytes:", code[:16].hex(' '))
        t, n = detour_size(code, u.OPTIONAL_HEADER.ImageBase + rva)
        print("=> detourSize =", t, "(%d instructions)" % n)
        break
```

实测输出：

```
user32!MessageBoxW rva=0x7c760
first 16 bytes: 48 83 ec 38 45 33 db 44 39 1d c2 7b 03 00 74 2e
  0x18007c760 (+0) len=4  sub rsp, 0x38
  0x18007c764 (+4) len=3  xor r11d, r11d
=> detourSize = 7 (2 instructions)
```

**`detourSize = 7`，不是 5**。naive 方案会在 `xor r11d, r11d`（3 字节，跨 `+4..+6`）中间切断
第 5 字节 —— 那个字节是这条指令的一部分，改掉它整个函数体就崩。

★ **两条硬规则**：
1. `detourSize` 至少 5（`JMP rel32`），实际取「累加到 ≥5 的第一条指令边界」。
2. **绝不覆盖 RIP 相对指令 / 相对 CALL / 相对 JMP 的最后 5 字节**。x64 下 `E8/E9 xx xx xx xx`
   之后紧跟的字节在解码时是被当作指令流的一部分分析的，覆盖它会把整个函数解密/反混淆解错。
   `aob-signature-scan.md` 有对应的判定逻辑。

### 5. 手动字节构造（不依赖任何汇编器）

当只改一两个字节时，手工拼比调汇编器更可控：

```python
import struct

class Bytes:
    """小端字节拼装器。"""
    def __init__(self): self.d = bytearray()
    def db(self, *bs):
        for b in bs: self.d.append(b & 0xff)
        return self
    def dw(self, v): self.d += struct.pack("<H", v & 0xffff);  return self
    def dd(self, v): self.d += struct.pack("<I", v & 0xffffffff); return self
    def dq(self, v): self.d += struct.pack("<Q", v & 0xffffffffffffffff); return self
    def raw(self, b): self.d += bytes(b); return self

    def rel_jmp(self, dst, src):
        """rel32 = dst - src - 5，前提是这 5 字节最终写在 src。"""
        return self.db(0xE9).dd(dst - src - 5)

    def rel_call(self, dst, src):
        return self.db(0xE8).dd(dst - src - 5)

    def ptr(self):
        return bytes(self.d)
    def __len__(self):
        return len(self.d)
```

★ `rel_jmp`/`rel_call` 的 `src` 参数**必须是这段字节最终会被写入的地址**，不是构造时的
`base + len(...)`。写 trampoline 时 `src` 在 `WriteProcessMemory` 之前是未知的 ——
必须等拿到目标地址后再拼，或用两阶段：先占位、写入时再 patch 那 4 字节。

### 6. 生成后的自检（必做）

任何拼接/汇编出来的字节，落进内存前都要反汇编回来看一眼：

```python
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
md = Cs(CS_ARCH_X86, CS_MODE_64)

def show(bs, base=0):
    for ins in md.disasm(bs, base):
        print("   %-20s %s" % (ins.mnemonic, ins.op_str))
```

实测（`direct-syscall.md` 的 stub，SSN=0x18）：

```python
import struct
stub = b"\x4c\x8b\xd1" + b"\xb8" + struct.pack("<I", 0x18) + b"\x0f\x05\xc3"
print("syscall stub:", stub.hex(" "))
show(stub)
```

```
syscall stub: 4c 8b d1 b8 18 00 00 00 0f 05 c3 (11 bytes)
   mov                    r10, rcx
   mov                    eax, 0x18
   syscall
   ret
```

★ 「反汇编回来正好是你写的意思」= 判据通过。**不是**看字节长度对不对 —— 长度对但语义错
（寄存器选错、立即数大小端反了）是最常见的 bug，而它不会在长度上暴露。

实测（`manual-map-injection.md` 的 DllMain 调用 shellcode，41 字节）：

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

`movabs rcx, <64 位立即数>` 是 capstone 的 Intel 语法输出；用 AT&T 语法工具看会是
`movq $0x...,%rcx`。**看到 `movabs` 不用担心 —— 那只是 48 B9/48 B8 形式的助记符差异。**

## 判据

1. **`rasm2` 有输出字节**。判据形态：命令打印出非空 hex 串（如 `4989ca`）。
   **空输出 + exit 0 = 没带 `-s 0x0`**，不是「这条指令汇编不了」。
2. **hook 边界是「累加到 ≥5 的第一条边界」**，不是 5。判据形态：脚本打印的每条指令的
   `(+N) len=M` 累加值，以及最终的 `=> detourSize = T (n instructions)`。
   **实测 `user32!MessageBoxW` 的答案是 7 而不是 5** —— 若你的脚本算出 5，就是没在指令边界上停。
3. **生成字节反汇编回环正确**：判据形态是「反汇编出的助记符列表 == 你写的汇编列表」。
   实测输出 `mov r10,rcx / mov eax,0x18 / syscall / ret` 四行，
   **四行齐全且顺序正确 = PASS**。少一行（例如 `ret` 丢了）说明偏移算错，会导致调用返回到垃圾地址。
4. **capstone 切片 ≥15 字节**：判据形态是 decode-loop 没有输出非预期的 `db 0x..`。
   若在正常代码段频繁出现 `db 0x..`，先怀疑切片太短，再怀疑真的存在数据/跳转表。

## 坑

1. ★★ **`rasm2` 不带 `-s 0x0` 静默返回空**。exit code 是 0，极易误判。凡是「汇编不出来」，
   先把 `-s 0x0` 补上再排查别的。
2. ★★ **capstone 的 `md.disasm()` 必须在有 `detail=True` 时才填 `operands` / `op_size`**。
   没开就调 `ins.op_size(0)` 会静默返回 0（结构体重建篇的脚本依赖这个）。
3. ★★ **capstone 输入切片 <15 字节会在指令中间失败**。永远传 15 字节或更多。
4. ★ **`search.from/to` 在本机 r2 上无效**，跨段搜索请用 `/x` 一次搜完或换工具。见 `aob-signature-scan.md`。
5. **`/x` 的通配符是 `.` 不是 `?`**。`81 3d 8e 4e 0e ..` 这种写法才对。
6. **重定位样本上 r2 可能报错** → 加 `2>$null` 重跑。
7. **相对跳转的偏移和基址强绑定**。`rasm2 -s 0x1000` 下算出的 `jne` 偏移不能用在 `-s 0x0` 的地址上。
8. **`rabin2.exe` 在本机是坏副本**，别用；用 r2 内建命令代替。
9. **x86 与 x64 的相对跳转偏移不同**（实测 `jz 0x5` → x86 `7403` / x64 不同值）。混编时分别算。
10. **`movabs` 不是特殊指令**，是 capstone 对 `48 B8+r` 形式的助记符。别据此判断目标架构。

## 相关

- `struct-reconstruction.md` — 用 capstone 操作数类型推字段类型（本篇判据的下游）
- `trampoline-detour.md` — 本篇的 `detourSize` 判定在这里落地成完整 hook
- `direct-syscall.md` — stub 生成的实战模板
- `manual-map-injection.md` — DllMain 调用 shellcode 的字节构造
- `aob-signature-scan.md` — 把解码结果做成特征码
- `code-patching.md` — `rasm2` 出来的字节作为 patch 内容