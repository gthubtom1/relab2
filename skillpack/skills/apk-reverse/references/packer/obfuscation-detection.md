# 编译期混淆检测与识别

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/apk-reverse/techniques/07-packer/01-obfuscation-detection.md`
> **什么时候用**：APK 里的 native lib 被编译期混淆保护（字符串加密、控制流平坦化、常量隐藏），静态分析时函数逻辑不可读。

## 适用信号

- `strings` 输出 so 里几乎无可读字符串
- 反编译后函数体巨大、分支密集
- 反编译结果充满 `*(uint*)(&DAT_xxxx ^ mask)` 模式
- 节区名异常或入口点可疑
- `find-vm-dispatch.py` 报「未发现 dispatch」，但 so 明显被混淆过

## 常见混淆类型

### 1. oxorany：编译期 XOR 常量加密

```cpp
// 源码调用 oxorany(常量) 会在编译期被 XOR 加密，运行时内联解密
// 静态看到的是加密值
*(int*)(local_buf + 0x10) = 0x3C7A9B2D ^ 0x5A3C1F7E;
```

识别：
- 反编译中 XOR 立即数占比异常高（> 40%）
- 函数开头有固定解密循环
- 字符串被拆成字节数组 + 运行时拼接

### 2. OLLVM/Arkari：控制流平坦化

```
- 函数开头有大 switch 分发器
- 每个基本块分配 case id，块末尾跳回 switch
- 控制流图呈星型收敛到单一分发块
```

### 3. UPX / 壳变种

```powershell
$diec = (Resolve-ReverseToolSpec -Name 'diec').Command
& $diec -b $SO_PATH
$upx = (Resolve-ReverseToolSpec -Name 'upx').Command
& $upx -t $SO_PATH
```

魔改 UPX 特征：magic 不再以 `UPX!` 开头、解压 stub 被混淆、节区名改通用名但压缩比例异常。

### 4. 字符串表加密

```
- .rodata 中字符串在链接后被 XOR/Cipher 加密
- .init_array 中有解密函数先于 main 执行
- 识别: .init_array 中函数引用了 .rodata 大量地址
```

## 前置

```powershell
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
$r = Resolve-ReverseToolSpec -Name 'diec'; & $r.Command -b $SO_PATH
$r = Resolve-ReverseToolSpec -Name 'r2';   & $r.Command -qc 'iI' $SO_PATH
```

## 步骤

### 1. DiE 初判

```powershell
$diec = (Resolve-ReverseToolSpec -Name 'diec').Command
& $diec -b $SO_PATH
```

本机对一个真实 ARM32 Android SO 的输出格式：

```
ELF32
    Operation system: Android[ARM, 32-bit, DYN]
```

### 2. r2 看节区与 ELF 概览

```powershell
$r2 = (Resolve-ReverseToolSpec -Name 'r2').Command
& $r2 -qc 'iI' $SO_PATH 2>$null
& $r2 -qc 'iS~init_array' $SO_PATH 2>$null
```

本机实测输出（真实 SO）：

```
arch     arm
baddr    0x0
binsz    527889
bintype  elf
class    ELF32
endian   little
machine  ARM
os       android
pic      true
stripped true
va       true

72  0x0006bfe0  0x4 0x0006bfe0  0x4 -rw-  0x3  INIT_ARRAY .init_array
```

注意 `2>$null`：本机 r2 对某些样本会向 stderr 输出告警。

### 3. 节区与 `.init_array` 全量扫描

```python
# init_array.py —— 列出构造函数（反调试/解密入口常在这里）
from elftools.elf.elffile import ELFFile
import sys

p = sys.argv[1]
with open(p, 'rb') as f:
    e = ELFFile(f)
    w = 8 if e.elfclass == 64 else 4
    for s in e.iter_sections():
        if s.name in ('.init_array', '.fini_array'):
            d = s.data()
            for i in range(0, len(d) - w + 1, w):
                print('  %s[%d] = 0x%08x'
                      % (s.name, i // w, int.from_bytes(d[i:i+w], 'little')))
```

本机实测（真实 ARM32 SO，条数很少 → 说明解密逻辑不在构造函数里，需另找）：

```
  .init_array[0] = 0x0005352c
```

用 `D:\EXE\python\python.exe` 运行（本机逆向库都在这个解释器）。

### 4. 动态 dump 解密后的 so（Frida）

```javascript
// lib 加载完成后 dump 整段内存
var lib = Process.findModuleByName("libtarget.so");
var data = Memory.readByteArray(lib.base, lib.size);
send({ name: lib.name, size: lib.size }, data);
```

### 5. IDA 分析 so

```powershell
$idat = (Resolve-ReverseToolSpec -Name 'idat64_83').Command
& $idat -A -S"<script.py>" -L"<log.txt>" -o"<out.i64>" $SO_PATH
```

脚本必须以 `idc.qexit(0)` 结尾并先 `idaapi.auto_wait()`；`idat64.exe` 才是 64 位版（`idat.exe` 是 32 位）。

## 判据

| 观察 | 结论 |
|---|---|
| DiE 报 UPX/packer | 走脱壳路线，dump 后重新静态分析 |
| `strings` 几乎无输出 + `.init_array` 非空 | 存在编译期字符串加密 |
| 控制流图呈星型 | OLLVM 控制流平坦化 |
| `find-vm-dispatch.py` 无候选但代码难读 | 非 VMP，是编译期混淆 |

**外部可观测的判据**：`diec -b` 输出里的 packer/compiler 字段、r2 `iI` 的 `stripped`/`pic` 字段、`iS~init_array` 的条目行 —— 而不是「反编译看起来很乱」。

## 坑

- **`UPX!` magic 被改后 `upx -d` 会直接失败**，别反复试，改用运行时 dump。
- **r2 的 `/x` 通配符是 `.` 不是 `?`**，且 `search.from/to` 无效。
- **rabin2 在本机是坏副本**，用 `r2 -qc` 代替。
- **`.init_array` 为空不代表没有初始化逻辑**：可能放在 `.ctors` 或 `.preinit_array`，或由 `JNI_OnLoad` 触发。
- **IDA headless：`idat.exe` 是 32 位**，分析 64 位 SO 必须用 `idat64.exe`。
- **capstone/elftools 在 `D:\EXE\python\python.exe`**，不要在 `venv-re` 里找（那是空的）。

## 相关

- `vmp-dex2c-detection.md` —— VMP 判定（与编译期混淆是不同形态）
- `../native/so-structure-audit.md` —— so 节区/符号/导入导出全量体检
