# YARA 规则编写（逆向视角）

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/pe-reverse/07-yara-sigma/01-yara-rule-writing.md`（已适配本机工具链）
> **什么时候用**：分析完一个样本后，把它的独特特征沉淀成规则，用于后续同类样本的快速分类和家族识别。

## 适用信号

- 已完成一个样本的静态分析，提取到了独特字符串、字节序列、导入表组合。
- 需要在样本库里批量扫同类变种。
- 要交付检测规则（YARA 供 EDR/扫描器，Sigma 供 SIEM）。
- 已有规则对改版样本漏报，需要演进规则。

## 前置

```powershell
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
$yara  = (Resolve-ReverseToolSpec -Name 'yara').Command    # D:\Tools\yara\yara64.exe
$r2    = (Resolve-ReverseToolSpec -Name 'r2').Command
$floss = (Resolve-ReverseToolSpec -Name 'floss').Command
$procdmp = (Resolve-ReverseToolSpec -Name 'procdump').Command
```

本机 YARA 版本（实测 `--version`）：**4.5.4**。

## YARA 规则结构

```yara
import "pe"

rule SampleFamily_Detector
{
    meta:
        author      = "analyst"
        description = "Detects SampleFamily RAT v2.x"
        date        = "2026-10"
        hash        = "a1b2c3d4e5f6..."
        severity    = "medium"

    strings:
        // 字符串特征
        $str1 = "C2PanelPassword" ascii wide
        $str2 = "svchost_helper.exe" ascii
        $str3 = "/api/upload.php" ascii

        // 十六进制特征（唯一指令序列）
        $code1 = { 48 8B 05 ?? ?? ?? ?? 48 89 45 F8 48 8B 45 F8 48 8B 40 10 }
        $code2 = { 55 8B EC 83 EC 08 53 56 57 8B 7D 08 }

        // 正则
        $re1  = /[a-f0-9]{32}-[0-9]{4}-[0-9a-f]{8}-[a-f0-9]{16}/   // UUID

    condition:
        uint16(0) == 0x5A4D and      // MZ 头
        filesize < 500KB and
        2 of ($str*) and             // 至少 2 个字符串匹配
        $code1 and                    // 必须匹配唯一指令序列
        any of ($code2) and           // 任一特征码变体
        $re1                          // 必须匹配 UUID 格式串
}
```

★ **`import "pe"` 必须写在文件最开头，且在 `rule` 之前。** 少了它，所有 `pe.*` 字段报 `undefined identifier "pe"`。写成 `rule` 之后、`{` 之前会报 `syntax error, unexpected <meta>, expecting '{'`。

## 提取优质特征

### PE 结构特征

```yara
import "pe"

rule PE_Struct_Heuristic
{
    condition:
        uint16(0) == 0x5A4D and
        uint32(uint32(0x3C)) == 0x00004550 and      // PE\0\0
        pe.number_of_sections >= 3 and
        pe.sections[0].name == ".text" and
        pe.sections[1].name == ".rdata"
}
```

★ **`pe.sections[i].name` 是精确字符串比较，不是前缀匹配**。对 notepad.exe 实测 `pe.sections[0].name == ".text"` 和 `pe.sections[0].name matches /^\.text/` **两者都命中**（因为名字正好就是 `.text`）。但节名带后缀（如 `.text$mn`）时 `==` 会失效，要用 `matches /^\.text/`。

### 导入表特征

```yara
import "pe"

rule Injection_Trio
{
    condition:
        uint16(0) == 0x5A4D and
        pe.imports("KERNEL32.dll", "VirtualAllocEx") and
        pe.imports("KERNEL32.dll", "WriteProcessMemory") and
        pe.imports("KERNEL32.dll", "CreateRemoteThread")
}

rule AntiDebug_Imports
{
    condition:
        uint16(0) == 0x5A4D and
        pe.imports("KERNEL32.dll", "IsDebuggerPresent") and
        pe.imports("ntdll.dll", "NtQueryInformationProcess")
}
```

> ★ **DLL 名大小写敏感**。notepad.exe 里的 DLL 名是大写 `KERNEL32.dll`（实测 `pe.imports("KERNEL32.dll", "IsDebuggerPresent")` 命中，而小写 `"kernel32.dll"` 会漏）。**以 r2 `ii` 输出的原始大小写为准**。

### 字符串特征

```yara
strings:
    // 独特字符串
    $c2   = "https://evil-c2.example.org/api/beacon" ascii
    $ua   = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)" ascii
    $mtx  = "Global\\AV_Update_Check_Mutex" ascii wide
    $cmd  = "cmd.exe /c " ascii wide
    // 变异安全的路径片段（不用绝对路径）
    $path = "\\AppData\\Roaming\\" ascii
condition:
    3 of them
```

`ascii wide` 双写是关键 —— 同一字符串在 PE 里可能是 ASCII 也可能是 UTF-16LE（尤其通过宽字符 API 的那些）。

### 代码特征（AOB）

```yara
strings:
    $rc4_init = {
        48 89 5C 24 08      // mov [rsp+8], rbx
        48 89 74 24 10      // mov [rsp+0x10], rsi
        57                  // push rdi
        48 83 EC 20         // sub rsp, 0x20
        48 8B F1            // mov rsi, rcx
        48 8B FA            // mov rdi, rdx
    }
    $inject_stub = {
        55                  // push ebp
        8B EC               // mov ebp, esp
        6A 00               // push 0
        68 [4]              // push dllPath (4-byte 占位)
        68 [4]              // push LoadLibraryA
        FF 55 08             // call [ebp+8]
    }
condition:
    any of ($rc4_init, $inject_stub)
```

YARA 的通配符是 `?`，`[4-8]` 是长度范围。取字节序列用 r2（注意 r2 用 `.`，YARA 用 `?`）：

```powershell
& $r2 -2 -qc 'aaa; s sym.CheckBranch; p8 27; q' .\ptgt2.exe
# 实测: 554889e5894d10837d10007507b8c8000000eb05b8640000005dc3
```

再手挑稳定片段、改写成 YARA 格式。

## 实战规则示例

```yara
import "pe"

rule HackTool_DLL_Injector_Generic
{
    meta:
        description = "Generic DLL injector using CreateRemoteThread pattern"
        severity    = "medium"
        author      = "analyst"
        date        = "2026-10"

    strings:
        $s1 = "InjectDLL" ascii nocase
        $s2 = "CreateRemoteThread" ascii
        $code1 = { 8B 45 ?? 50 FF 15 ?? ?? ?? ?? 8B 4D ?? 51 FF 15 ?? ?? ?? ?? }

    condition:
        uint16(0) == 0x5A4D and
        filesize < 200KB and
        (2 of ($s*)) and
        $code1
}
```

**从样本提取 AOB 的实操流程**：

```powershell
$r2 = 'D:\Tools\radare2\bin\r2.exe'
# 1. 定位目标函数
& $r2 -2 -qc 'aaa; afl~inject; q' .\sample.exe
# 2. 抽字节
& $r2 -2 -qc 's sym.inject; p8 32; q' .\sample.exe
# 3. 自己在样本里验证唯一性
& $r2 -2 -qc '/x <你改写好的YARA模式，.替?>; q' .\sample.exe
#    命中数必须恰好 1
```

★ **YARA 里的 `?` 在 r2 验证时要换成 `.`**，反过来 r2 的 `.` 在 YARA 里要换成 `?`。

## 测试规则

```powershell
$yara = 'D:\Tools\yara\yara64.exe'

# 单文件
& $yara rule.yara .\sample.exe
# 输出: SampleFamily_Detector sample.exe

# 递归 + 显示匹配的字符串
& $yara -r -s rule.yara C:\samples\
# 输出:
#   SampleFamily_Detector C:\samples\injector_v2.exe
#   0x1f2:$code1: 8B 45 08 50 FF 15 ...

# 扫进程 dump
& $procdump -ma <PID> C:\dumps\target.dmp
& $yara rule.yara C:\dumps\target.dmp -s
```

## 规则演化

```
v1.0: 匹配原始样本 → 改版/加壳版本漏报
v1.1: 加入脱壳后代码特征 → 新版本改字符串则漏报
v2.0: 改为行为特征（导入表组合 + 代码模式）→ 覆盖更多变种
```

## 判据

规则好不好，看三个**外部可观测**的结果：

1. **阳性样本必须命中**：对目标样本 `yara rule.yara sample.exe` 必须**输出规则名**。实测：
   ```
   ReTest_Sections notepad.exe
   ReTest_Sec0Exact notepad.exe
   ReTest_Sec0Match notepad.exe
   ReTest_Imports notepad.exe
   ```
2. **阴性样本必须不命中**：`yara rule.yara sample.exe` 的退出码为 0 且**无规则名输出**。**注意「无输出」和「退出码非 0」是两件事** —— YARA 默认命中返回 0。
3. **同一条件下的自一致性**：`pe.imports("KERNEL32.dll", "IsDebuggerPresent")` 在 notepad.exe 上必须命中，且 `pe.entry_point == 0x22fd0`（**文件偏移**，实测成立）也命中 —— 这两个断言能验证你写的模块字段语义没搞错。
4. **误报率**：在 100+ 个无关样本上跑 `yara -r rule.yara C:\samples\clean\`，规则名输出行数应为 **0**。

## 坑

1. ★ **`import "pe"` 的位置**。必须是最开头的独立行，在任何 `rule` 之前。放在 `rule X` 和 `{` 之间会报 `syntax error, unexpected <meta>, expecting '{'`。
2. ★ **递归扫描会扫到规则文件自己**。实测 `yara -r -s test.yar .` 在规则目录里匹配到了 `ReTest_Negative .\test.yar` —— 因为规则源码里写着那个「不可能存在」的字符串。**扫描时把规则文件放在被扫目录之外**。
3. ★ **DLL 名大小写敏感**。`pe.imports("KERNEL32.dll", ...)` 命中，`"kernel32.dll"` 不命中。以 r2 `ii` 的原始大小写为准。
4. ★ **`pe.sections[i].name == ".text"` 是精确匹配**。带后缀（`.text$mn`）时改用 `matches /^\.text/`。
5. ★ **`pe.entry_point` 是文件偏移，不是 RVA**。实测 notepad.exe：RVA 是 `0x23bd0`，`pe.entry_point == 0x23bd0` **不命中**，而 `== 0x22fd0`（文件偏移）**命中**。这是个反直觉的坑。
6. **YARA 通配符 `?`，r2 通配符 `.`**。两边的模式不能直接互换。
7. **`nofunc` 检查要开**（`yara --print-nofunc-warnings`）。间接跳转的 `$code*` 容易报 "may slow down scanning"。
8. **退出码不反映命中与否**。YARA 4.x 命中返回 0。判据只能看**输出行**。
9. **capa / floss 的输出可以直接喂 YARA**：`capa -j` 给行为标签，`floss` 给静态/栈/解码字符串。用 `floss` 抓混淆字符串（明文字符串被加密时 YARA 字符串规则会漏）。
10. **`nocase` 会显著拖慢扫描**，大样本库上慎用。

## 相关

- `aob-signature-scan.md` — 从函数里抽字节序列做成 `$code*`（本篇的 AOB 来源）
- `pe-header-parsing.md` — `pe.*` 模块字段的语义来源（尤其 `entry_point` 是文件偏移）
- `unpack-and-memory-dump.md` — 加壳样本要先 dump 再提特征，否则特征在壳里
- `anti-debug-bypass.md` — 反调试 API 组合是最稳的 YARA 行为特征
- `dynamic-api-resolution.md` — 导入表稀疏样本的 YARA 要改用行为特征
- `../SKILL.md` — 总体流程