# 拿到样本的前 30 分钟（Triage Checklist）

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/general/techniques/methodology/01-reverse-checklist-first-30-min.md`（GPL-3.0），工具链全部换成本机实测命令。
> **什么时候用**：手里刚拿到一个未知二进制，需要在 **30 分钟内** 建立完整初始信息集、判断保护强度、锁定关键入口，并**产出下一步动态分析可以直接用的断点计划**。
> **不负责**：脱壳本体（见 `re-agent-workflow.md` §1.2）、VM 去虚拟化（见 `../../patterns*.md`）、Go/JS/.NET 深度（见各专项 skill）。本篇只做 **triage 阶段**，做完把结论交给下游。

---

## 适用信号

命中以下任意一条就读本篇：

- 样本刚落地，来源不明或来源可疑，需要先定「值不值得深挖 / 有多难」
- 需要在正式开 IDA/Ghidra 之前先摸清结构：节区、导入、字符串、入口
- 上游给了个「帮我看下这个 exe」但没人说过它是不是加壳、是不是 .NET、有没有网络行为
- 需要一份**能交给下一个 agent 接着干**的 triage 交付物

不适用（直接跳走）：

| 情况 | 去哪 |
|------|------|
| 已经知道是纯 APK | `../SKILL.md` / `../SKILL.md` |
| 已经拿到解包后的内存 dump | 直接跳本文档 §6 |
| 是 CTF 且已经告诉你 flag 在哪 | `pwn-chain/` 或 `../patterns-ctf.md` |

---

## 前置

### 工具探测层（唯一取路径的方式）

```powershell
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
```

之后所有工具都走 `$r = Resolve-ReverseToolSpec -Name '<id>'` 取 `$r.Command`，**用完整路径调用，不依赖 cwd**。

| 用途 | 工具 id | 本机解析到（2026-10-09 实测，仅供 sanity check，**不要写死**） |
|------|---------|------|
| 查壳 / 判编译器 | `diec` | `(Resolve-ReverseToolSpec -Name 'diec').Command` |
| 二进制概览 / 节区 / 导入 / 字符串 | `r2` | `(Resolve-ReverseToolSpec -Name 'r2').Command` |
| 混淆字符串还原 | `floss` | `D:\Tools\cli\floss.cmd` |
| 能力识别 / ATT&CK 映射 | `capa` | `(Resolve-ReverseToolSpec -Name 'capa').Command` |
| 自动脱壳 | `upx` | `(Resolve-ReverseToolSpec -Name 'upx').Command` |
| Ghidra 无头 | `analyzeHeadless` | `(Resolve-ReverseToolSpec -Name 'analyzeHeadless').Command` |
| IDA 无头 | `idat` | `(Resolve-ReverseToolSpec -Name 'idat').Command` |
| 动态调试（x64） | `cdb` | `%LOCALAPPDATA%\Microsoft\WindowsApps\cdbX64.exe` |
| 反反调试注入器 | `scyllahide` | `(Resolve-ReverseToolSpec -Name 'scyllahide').Command` |
| 注入 / hook 扫描 | `pe-sieve` | `(Resolve-ReverseToolSpec -Name 'pe-sieve').Command` |
| YARA 规则匹配 | `yara` | `(Resolve-ReverseToolSpec -Name 'yara').Command` |
| Python 专精库（pefile / lief / angr / capstone / z3 / dnfile / yara） | `python` | `(Resolve-ReverseToolSpec -Name 'pyre').Command` |
| .NET 反编译 | `ilspycmd` / `de4dot` / `dnSpy.Console` / `Confuser.CLI` | 见探测层 |

### 案件建档

动手前 MUST 完成（`../../MASTER-ROUTING.md` + `../../ops/scope-contract.md`）：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File 'C:\relab2\skillpack\skills\scripts\master-route.ps1' `
  -Hint "<用户原话>" -OutDir $out
powershell -NoProfile -ExecutionPolicy Bypass -File 'C:\relab2\skillpack\skills\scripts\case-init.ps1' `
  -Hint "<同上>" -ProjectRoot "<工作区>" -Preset offline-sample `
  -Sample "<样本绝对路径>" -NetworkProfile offline -ReadyForAct
```

两条命令各 **timeout 30s**；退出码 2 = 配置或技能缺失 → **停下来报**，不要自己找地方重建技能包。

### 环境变量（整篇复用）

```powershell
$S    = '<样本绝对路径>'
$Out  = Join-Path $env:TEMP ("triage-" + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $Out -Force | Out-Null
$r2   = (Resolve-ReverseToolSpec -Name 'r2').Command
$diec = (Resolve-ReverseToolSpec -Name 'diec').Command
```

**全程只读 `$S`**。任何补丁、dump、脱壳产物写到 `$Out`，原件与派生文件分离（见文末「证据闭环」）。

---

## 步骤

### §0（0–5 分钟）固定样本身份

**做什么**：先给样本一个不可逆 ID 和不可变基线。后面所有结论都挂在这个 ID 上。

```powershell
# SHA256（首选）
try {
  $h = (Get-FileHash -Algorithm SHA256 -LiteralPath $S).Hash
} catch {
  # 实测坑：这台机器上 Microsoft.PowerShell.Utility 模块可能未加载，Get-FileHash 不存在
  $sha = [System.Security.Cryptography.SHA256]::Create()
  $fs  = [System.IO.File]::OpenRead($S)
  $h   = (($sha.ComputeHash($fs) | ForEach-Object { $_.ToString('x2') }) -join '')
  $fs.Close()
}
$h

# 大小 + 时间戳
$fi = Get-Item -LiteralPath $S
"{0:N0} bytes | {1}" -f $fi.Length, $fi.LastWriteTimeUtc

# 文件类型 / 壳 / 编译器（一次性拿全）
& $diec -j $S | Tee-Object -FilePath "$Out\die.json"
```

**判据**：

- `$h` 是 64 位十六进制小写串，且和 `certutil -hashfile $S SHA256` 输出一致（两条独立路径对账）。
- `$Out\die.json` 存在且能 `ConvertFrom-Json`，`detects[0].filetype` 字段**非空**（如 `PE64` / `PE32` / `ELF64` / `Mono/.Net assembly`）。
- 大小落在预期区间就心里有数：`< 100 KB` 多半是 shellcode loader / stub；`100 KB–2 MB` 正常编译产物；`> 10 MB` 多半带大量资源或完整引擎。

**规模判断**：0–5 分钟这段不该超过 2 分钟。超了就说明在跟工具搏斗，记下来走 §7 的坑表。

---

### §1（0–10 分钟）保护强度：节区 + 熵

**做什么**：判断「能不能直接静态分析」还是「必须先脱壳」。这两个数字决定后面 20 分钟的走法。

```powershell
# 节区表（权限 + 名称）
& $r2 -qc 'iS' $S 2>$null | Tee-Object -FilePath "$Out\sections.txt"

# 头信息（位数 / 编译器时间戳 / PDB 路径 / 入口点 baddr）
& $r2 -qc 'iI' $S 2>$null | Tee-Object -FilePath "$Out\info.txt"

# 熵值：整文件 + 每节区
$py = (Resolve-ReverseToolSpec -Name 'python').Command
& $py -c @"
import pefile, math, sys
p = sys.argv[1]
data = open(p,'rb').read()
pe = pefile.PE(p)
def ent(b):
    if not b: return 0.0
    c = [0]*256
    for x in b: c[x] += 1
    n = len(b)
    return -sum(v/n*math.log2(v/n) for v in c if v)
print('%.4f  whole-file  %d bytes' % (ent(data), len(data)))
for s in pe.sections:
    print('%.4f  %-8s  raw=%d  vsize=%d' % (ent(s.get_data()), s.Name.rstrip(b'\x00').decode('latin1'), s.SizeOfRawData, s.Misc_VirtualSize))
"@ $S | Tee-Object -FilePath "$Out\entropy.txt"
```

**判据**：

- `sections.txt` 里 `.text` 权限**不是** `r-x`，或者出现了 `UPX0/UPX1/.vmp0/.themida` 这类节名 → 加壳，进入 §1 分支。
- `entropy.txt` 里 `.text` **> 7.0** → 代码段是压缩/加密/虚拟化产物，不能当源码读。
- `entropy.txt` 里 `.rsrc` **> 7.5** → 资源段里塞了加密 payload（常见于安装包、游戏资源、藏 payload 的样本）。
- `.data` 高熵 → 变量区里嵌了加密数据。
- 参考锚点（实测自本机 `C:\Windows\System32\notepad.exe`）：

  ```text
  6.3093  whole-file  200704 bytes
  6.2747  .text     raw=148992  vsize=148623   ← 未加壳编译产物落在 6.2–6.6
  5.9296  .rdata    raw=37888   vsize=37512
  1.8068  .data     raw=3584    vsize=10008    ← 稀疏未初始化，熵天然低，不是「没加密」
  ```

**决策**：

```text
.text 可读 + 熵 < 7.0 + 导入表正常  → 直接进 §2 导入锚点
.text 高熵 / 节名可疑 / 入口在末节  → 有壳 → 查 die.json 里的 packer 字段，走 upx / 动态 dump
```

有壳时：

```powershell
$upx = (Resolve-ReverseToolSpec -Name 'upx').Command
# 先备份副本再脱，原件不动
Copy-Item $S "$Out\unpacked.exe" -Force
& $upx -d "$Out\unpacked.exe"
```

**判据（UPX 分支）**：`upx -d` 退出码 0，且副本体积**变小**、节区名恢复成 `.text/.rdata/...`。失败（`NotPackedException`）说明不是真 UPX 或已被二次加工 → 记 Evidence，转 `re-agent-workflow.md` §1.2。

---

### §2（5–15 分钟）导入锚点与可疑 API 聚类

**做什么**：这是 `re-agent-workflow.md` §1.1 的**硬门** —— 没记录导入锚点就不许进动态分析。

```powershell
# 导入表（-qc 单命令静默，不进交互）
& $r2 -qc 'ii' $S 2>$null | Tee-Object -FilePath "$Out\imports.txt"

# 导出表（DLL / SYS 必须并列记，不能只记导入）
& $r2 -qc 'iE' $S 2>$null | Tee-Object -FilePath "$Out\exports.txt"

# 入口点
& $r2 -qc 'ie' $S 2>$null | Tee-Object -FilePath "$Out\entry.txt"

# 跨 DLL 快速过滤示例：只看网络面
& $r2 -qc 'ii~WS2' $S 2>$null
& $r2 -qc 'ii~winhttp' $S 2>$null
```

**判据**：

- `imports.txt` 非空，且能指出**具体 DLL 名 + 具体函数名**（不是「有很多导入」这种废话）。
- `entry.txt` 至少有一行 `paddr / vaddr / type`，即 OEP 落在哪个节区。
- DLL / SYS 样本：`exports.txt` 必须非空，否则记 `quality=missing`，不能默默跳过。

**可疑 API 聚类**（grep `imports.txt`，命中即记 Evidence）：

| 簇 | 命中函数 | 指向 |
|----|----------|------|
| 注入 | `CreateRemoteThread` + `WriteProcessMemory` + `VirtualAllocEx` | 进程注入 |
| 手动映射 | `NtUnmapViewOfSection` / `LdrLoadDll` | 反射加载 / 隐藏模块 |
| 内存读写 | `ReadProcessMemory` / `WriteProcessMemory` | 读写他进程内存 |
| 全局钩子 | `SetWindowsHookEx` | 劫持输入 / 注入 DLL |
| 动态解析 | `GetProcAddress` + `LoadLibrary*` | **壳或混淆的典型指纹** |
| 加密 | `CryptAcquireContext` / `BCrypt*` / `CertOpenStore` | 密码学调用 |
| 网络 | `WSAStartup` / `InternetOpen*` / `WinHttp*` | 外联能力 |
| 持久化 | `RegSetValue*` / `CreateService*` / 计划任务相关 | 驻留 |
| 文件 | `CreateFile*`（尤其 `\\.\` 设备路径）/ `WriteFile` | 落盘 / 驱动通信 |
| 反调试 | `IsDebuggerPresent` / `NtQueryInformationProcess` / `OutputDebugString*` | 反分析 |

**干净导入表警告（MUST 提醒）**：如果 `imports.txt` 只有 `kernel32` / `ntdll` 几个基础调用 + `LoadLibrary` + `GetProcAddress`，**高度怀疑动态解析**。在 Evidence 注明，并 SHOULD 转动态抓内存 API —— **禁止**凭静态 IAT 断言「无网络能力 / 无文件能力」。

**托管代码（.NET）走等价锚点**（没有传统 IAT）：

```powershell
$ilspy = (Resolve-ReverseToolSpec -Name 'ilspycmd').Command
& $ilspy $S -o "$Out\il" | Out-Null
# 或者看 ConfuserEx 特征
$conf = (Resolve-ReverseToolSpec -Name 'Confuser.CLI').Command
& $conf $S -d "$Out\deconf" 2>&1 | Select-Object -Last 10
```

**判据（.NET 分支）**：`$Out\il` 下出现 `.cs` 文件，且能看到 `System.Net.Sockets` / `System.Security.Cryptography` 等命名空间引用 —— 这就是「等价锚点」，语义槽仍是 `E-imports`。

---

### §3（10–20 分钟）字符串与能力画像

**做什么**：字符串给线索（URL、PDB 路径、错误信息），capa 给结构化的能力判断。两路交叉。

```powershell
# 路线 A：r2 内置字符串提取，支持 utf16le，能定位到节区
& $r2 -qc 'izz~http' $S 2>$null | Tee-Object -FilePath "$Out\str-net.txt"
& $r2 -qc 'izz~.pdb'  $S 2>$null | Tee-Object -FilePath "$Out\str-pdb.txt"
& $r2 -qc 'izz~\\\\'   $S 2>$null   # 反斜杠路径 / 设备路径

# 路线 B：floss —— 专门对付混淆字符串，能跑静态/栈/解码三路
$floss = (Resolve-ReverseToolSpec -Name 'floss').Command
& $floss $S 2>$null | Out-File -Encoding utf8 "$Out\floss.txt"

# 能力识别 + ATT&CK 映射（可 -r 只跑某条规则，快很多）
$capa = (Resolve-ReverseToolSpec -Name 'capa').Command
& $capa -q -r 'create file' -r 'create process' -r 'anti-debug/evasion' $S 2>$null |
  Tee-Object -FilePath "$Out\capa.txt"
```

**判据**：

- `str-pdb.txt` 非空 → **PDB 路径是最高价值线索**，直接给出开发者构建路径和原始文件名。下一步去符号服务器拉对应 PDB，能省掉整个 §4。
- `str-net.txt` 里出现具体域名/IP（不是文档链接） → 记入 C2 候选，进 §6 断点计划。
- `capa.txt` 里出现 `T1129`（动态 API 解析）/ `B0046`（native API）/ `C0007`（反调试）等 namespace 条目 → 有具体能力名，不是「可能有点反调试」。
- `floss.txt` 行数明显多于 `r2 -qc izz` 的命中数 → 样本有栈构造/编码字符串，混淆等级上调。

**字符串 → 交叉引用（优先级）**：

| 优先级 | 关键词 | 定位什么 |
|--------|--------|----------|
| 高 | `http://` `https://` `.onion` `192.168.` `10.0.` | C2 / 更新服务器 / 配置拉取 |
| 高 | `.pdb` | 符号服务器 / 开发者路径 |
| 高 | `CreateFile` `\\.\` `\Device\` `\??\` | 设备访问 / 驱动通信 |
| 高 | `RSA` `AES` `HMAC` `-----BEGIN` | 内嵌密钥或证书 |
| 中 | `registry` `HKLM` `Run` | 持久化位置 |
| 中 | 错误串（`invalid license` / `bad password`） | 鉴权分支所在函数 |
| 低 | 版权、版本、公司名 | 归属判断 |

---

### §4（15–25 分钟）静态定位：入口与关键函数

**做什么**：triage 的最后一块 —— 把「这是个什么」变成「我要去看哪几个函数」。

```powershell
# 入口点附近的反汇编（r2，最快）
& $r2 -qc 'pd 30 @ entry0' $S 2>$null | Tee-Object -FilePath "$Out\oep.txt"

# Ghidra 无头，全量分析（耗时随样本大小变化，triage 阶段可先跳过）
$gh = (Resolve-ReverseToolSpec -Name 'analyzeHeadless').Command
$proj = Join-Path $Out 'ghidra_proj'
cmd /c "`"$gh`" `"$proj`" tmp -import `"$S`" -deleteProject < nul" 2>&1 |
  Tee-Object -FilePath "$Out\ghidra.log"
```

> `analyzeHeadless` 必须走 `cmd /c` 并在尾部接 `< nul`，否则命令挂在控制台输入上不返回 —— 见 `../../ghidra-reverse/SKILL.md`。

**入口点判读**：

```text
entry → jmp <其他地址>          典型的 CRT 跳转壳，往后 1~2 层找 mainCRTStartup
entry → pushad (0x60) + ...     UPX / VMP 壳 stub
entry → call + pop              位置无关代码（PIC），pop 出的就是模块基址
entry 落在最后一个可写可执行节   壳 stub，真 OEP 在别处
```

**Main / 真实入口定位顺序**（未加壳 PE）：

1. 从 entry 反向回溯调用链，找到 `mainCRTStartup` → `main` / `wWinMain`
2. 搜字符串引用：`GetModuleHandle` + `GetCommandLineA/W` 的 xref
3. 有 PDB → 直接看符号（见 §3 判据）
4. DLL 样本优先看导出表（§2 已记）—— 注入型 DLL 的逻辑几乎总在 `DllMain` 或某个导出上

**判据（§4 完成的标准）**：

- `$Out\oep.txt` 非空，且你能**一句话说清**入口是 CRT / 壳 stub / PIC
- 至少锁定 **3 个**下一步要看的函数地址（VA + 一句话理由），例如：
  - `0x140001234` — 引用了 `http://` 字符串，负责建连
  - `0x140005678` — 引用了 AES S-box 常量，负责解密配置
  - `DllMain @ 0x140009abc` — 注入入口，做线程创建
- 三个地址里至少一个能被 `r2 -qc 'pd 20 @ 0x...'` 反汇编出有意义的指令（不是垃圾/跳转迷宫）

---

### §5（20–25 分钟）能力收敛：一句话定性

**做什么**：把前 25 分钟的碎片压成一句可证伪的判断。这句话进证据链。

```text
格式：<类型> / <保护强度> / <能力面> / <最强信号>

例 1：原生 PE64 / 无壳 / 网络+落盘+自删 / 导入表 3 个 WS2 函数 + 硬编码
       C2 域名 "xxx[.]top" 在 .rdata + CreateFileW("C:\Users\%TEMP%\a.tmp")
例 2：.NET 托管 / ConfuserEx 高强度混淆 / 仅反射加载 / 导入表被清空，
       所有能力藏在混淆后的字符串里，必须先 de4dot + Confuser.CLI
例 3：原生 PE32 / VMP 虚拟化 / 不可静态 / .text 熵 7.6，IAT 只有
       LoadLibrary + GetProcAddress → 必须动态 dump
```

**判据**：这句话里每个名词都能指回前面某一个 Evidence 文件（`die.json` / `sections.txt` / `entropy.txt` / `imports.txt` / `exports.txt` / `str-*.txt` / `floss.txt` / `capa.txt` / `oep.txt`）。指不回去的名词删掉。

---

### §6（25–30 分钟）产出：动态分析断点计划 ★

**这是本篇最重要的交付物。** 它是 §3 动态分析阶段的**直接输入**，不是笔记。

#### 6.1 cdb 命令文件模板（本机实测可跑）

**铁律三条**：

1. **命令串必须写进 `-cf <文件>`**。`-c "bp ...; g; ..."` 经 cmd 转义必坏（实测 `Win32 error 0n2`）。
2. **断点必须在 `g` 之前下**。`g` 之后再 `bp` 等于什么都没设（实测：先 `g` 的版本 HIT 计数为假命中 —— 那是 cdb 回显你输入的命令行，不是命中）。
3. **`g` 只写一次**。命中后 cdb 从 `g` 的**下一行**继续执行命令文件。

```powershell
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
$dbg = (Resolve-ReverseToolSpec -Name 'cdb').Command

$cf = Join-Path $Out 'cdb-plan.txt'
@(
  'sxe ld:kernel32.dll'                 # 在 kernel32 加载事件上停，好下模块级断点
  'bp ntdll!NtCreateFile'               # ★ 见下方「断点选谁」——必须实测选择
  'g'                                   # 只 g 一次
  '.echo ===MARK_HIT==='
  'k10'                                 # 调用栈，判断是谁调的
  'r rcx rdx r8 r9'
  '.echo ===MARK_DONE==='
  'q'
) -join "`r`n" | Set-Content -Path $cf -Encoding ASCII

& $dbg -cf $cf -o $S *> (Join-Path $Out 'cdb.log')
```

**读日志（实测坑：cdb 日志是 UTF-16LE，直接 `Select-String` 会当二进制）**：

```powershell
$t = [System.IO.File]::ReadAllText((Join-Path $Out 'cdb.log'), [System.Text.Encoding]::Unicode)
($t -split "`r?`n") | Select-String -Pattern 'Breakpoint 0 hit|MARK_HIT|MARK_DONE|^\w+!\w+'
```

**断点选谁（实测结论，不是抄的）**：

用 `C:\Windows\System32\findstr.exe fonts C:\Windows\win.ini` 做靶子，实测三档结果：

| 断点 | 结果 |
|------|------|
| `bp kernel32!CreateFileW` | `bl` 里显示 `0 e ... KERNEL32!CreateFileW`，但 `g` 之后**不命中**（走到 `ntdll!NtTerminateProcess`）—— kernel32 是 forwarder，符号落在一句 `jmp` 上 |
| `bp kernelbase!CreateFileW` | `bl` 显示绑定，**同样不命中** |
| `bp ntdll!NtCreateFile` | 命中。日志出现 `Breakpoint 0 hit` + `ntdll!NtCreateFile:` |

结论：**`ntdll!NtXxx` 层最稳**，`kernel32` / `kernelbase` 层要看具体符号是不是 forwarder。`bl` 里出现 ≠ 会命中，**必须以日志里的 `Breakpoint 0 hit` 为判据**。

**参数寄存器与 `da` vs `du`**（实测）：

- x64 Windows 调用约定：第 1 参数 `rcx`，第 2 `rdx`，第 3 `r8`，第 4 `r9`，5 起 `[rsp+0x28]`
- `da @rcx` 按 ASCII 解、**每行地址步进 0x20**；`du @rcx` 按 UTF-16 解、步进 0x40
- 在 `kernel32!CreateFileW` 上 `da @rcx` 能读出宽路径 —— 但那是这个具体函数碰巧指针指向可读区域，**别当规律**
- 在 `ntdll!NtCreateFile` 上 `da @rdx` 和 `du @rdx` 都读出一片 `????????` —— 因为**传进去的是 `UNICODE_STRING` 结构指针，不是裸字符串指针**。正确姿势：`dt @rdx`（或 `dps @rdx L4`）先看结构里的 Length/Buffer，再用 Buffer 指针去 `du`
- 看到满屏 `????` 先别怀疑内存，先问自己「我读的是裸指针还是结构体」

**命中判据（唯一可信）**：日志里出现 `Breakpoint 0 hit`，且下一行是目标符号名 + 反汇编。**不要**用自己 `.echo` 的命令回显（`0:000> .echo ===MARK_HIT===`）当命中证据 —— 那只是回显。

#### 6.2 断点计划表（照 §5 的结论填，交付物长这样）

| # | 目的 | 断点符号 | 层 | 命中后要拿什么 | 依据 |
|---|------|----------|----|---------------|------|
| 1 | 抓文件落地 | `ntdll!NtCreateFile` | ntdll | `k10` + 打开的路径 | `imports.txt` 有 `CreateFile*`；`str-*.txt` 有 `.tmp` / `\\.\` |
| 2 | 抓外联目标 | `ws2_32!connect` / `winhttp!WinHttpConnect` | 模块 | `du @rcx` 主机名、`r8` 端口 | `str-net.txt` 有域名；`imports.txt` 有 WS2 |
| 3 | 抓解密明文 | 定位到的函数 `0x140005678` | 目标模块 | `dump` 入参缓冲 + 返回后出参 | §4 锁定的 AES 函数 |
| 4 | 反反调试 L3 | `ntdll!NtQueryInformationProcess` | ntdll | 看 `ProcessDebugPort`(7) 返回 | `capa.txt` 命中 `anti-debug` |
| 5 | 反反调试 L1 兜底 | — | — | 注入 ScyllaHide 后重跑，见 6.3 | 同上 |
| 6 | 确认注入行为 | `ntdll!NtWriteVirtualMemory` | ntdll | 目标进程基址 + 大小 | `imports.txt` 有注入簇 |

**交付判据**：

- 表里每一行都能指回 §1–§5 的某个 Evidence
- 第 1 行**已经用靶子程序实测过能命中**（不是「理论上能」）
- 每个断点都写明了「命中后取什么」，不只是「断在哪」

#### 6.3 动态工具怎么选（本机现状）

| 情况 | 选谁 | 怎么调 |
|------|------|--------|
| 脚本化、可无人值守、要出可归档日志 | **cdb** | `& $dbg -cf <cmdfile> -o <exe>`，日志 UTF-16 |
| 需要交互式单步、内存 dump、IAT 重建 | **x64dbg + MCP** | 走 `xd://mcp__x64dbg_automate_mcp_*`，**agent 不得拉 GUI** |
| 目标 32 位 | `cdbX86` | 只能调 32 位目标；混用报 `Win32 error 0n50`，那是架构不对不是工具坏 |
| 反反调试 L1 | `scyllahide` | `& $sh -p <pid>`（`InjectorCLIx64.exe`），跑完再挂调试器 |
| 确认注入 / inline hook | `pe-sieve` | `& $ps /pid <pid>` |
| 静态查壳补充 | `yara` | `& $yara <rule.yar> $S` |

> `x64dbg headless` 会自杀（command loop 空转即退），只能用 GUI + MCP，详见 `../../references/tool-registry.md`。

---

### §7 产出物清单

30 分钟到点时，工作区里应该至少有：

```text
triage-<ts>/
├── die.json          # 文件类型 / packer / 编译器
├── info.txt          # 位数 / 时间戳 / PDB / baddr
├── sections.txt      # 节区 + 权限
├── entropy.txt       # 整文件 + 每节区熵
├── imports.txt       # ★ 硬门：E-imports
├── exports.txt       # DLL/SYS 必填
├── entry.txt         # OEP
├── oep.txt           # 入口前 30 条反汇编
├── str-net.txt / str-pdb.txt
├── floss.txt         # 混淆字符串
├── capa.txt          # 能力 + ATT&CK
├── ghidra.log        # 无头分析日志
├── cdb-plan.txt      # ★ 断点命令文件
├── cdb.log           # ★ 断点实测日志（含 Breakpoint 0 hit）
└── triage.md         # §5 那句定性 + 三个函数地址 + 断点计划表
```

`triage.md`（本包未落地） 模板：

```markdown
# Triage — <文件名>
- SHA256: <hash>    |  <N> bytes  |  <mtime>
- 类型: PE64 / 原生 / .NET / APK / ELF ...
- 保护: 无壳 | UPX | VMP | Themida | ConfuserEx | 未知（quality=unreadable）
- 一句话定性: <§5 那句>

## 锚点
- imports: <锚点摘要，引用 imports.txt>
- exports: <DLL/SYS 才填>
- OEP: <VA>（<落在哪个节区>）

## 下一步三个函数
1. 0x… — 理由
2. 0x… — 理由
3. 0x… — 理由

## 动态断点计划
（§6.2 那张表）

## 未解决
- <明确列出还卡住的点>
```

---

## 常见误判

```text
1. 误判加壳
   Delphi / Go / Rust 产物的节区特征看着像壳
   → 判据：die.json 里 packer 字段为空 + 导入表项数多 ⇒ 未加壳

2. 混淆代码误判为加密
   OLLVM 控制流平坦化会把 .text 熵顶到 7+
   → 判据：反汇编里能看到规整的 dispatcher + switch ⇒ 是混淆不是加密数据

3. .data 低熵误判为「没加密」
   .data 天然稀疏（实测 notepad.exe 的 .data 只有 1.81）
   → 判据：看 .data 的 raw size vs vsize 差距，差 3 倍以上说明有 BSS 大空洞

4. 干净导入表当成「良性」
   只有 LoadLibrary + GetProcAddress 也可能是壳
   → 判据：必须记 `import_quality=suspicious_clean` 并转动态，禁止下「无能力」结论

5. VM 保护漏判
   VMP 后 .text 高熵但导入表「还在」（是壳伪造的）
   → 判据：die.json 有 VMProtect + .text > 7.2 → 只能动态 dump

6. .NET 判成原生
   IL2CPP / NativeAOT 编译后没有 .NET metadata，但逻辑是 C#
   → 判据：`capa.txt` 里没有 CLR 相关命中，但字符串有 IL2CPP/Assembly 相关词
```

---

## 坑（本机实测，非推测）

### cdb

| 坑 | 表现 | 处置 |
|----|------|------|
| 必须 `-cf` 文件 | `-c "bp ...; g"` → `Win32 error 0n2`（cmd 转义坏） | 命令写进文件，`-cf <path>` |
| 断点顺序 | `g` 之后 `bp` 完全无效 | 所有 `bp` 写在 `g` 之前，只 `g` 一次 |
| `bl` 显示 ≠ 会命中 | kernel32/kernelbase 的 forwarder 符号会显示但永不触发 | 以日志里的 `Breakpoint 0 hit` 为唯一判据；优先 `ntdll!NtXxx` |
| 日志编码 | cdb 输出是 UTF-16LE，`Select-String` 报「非 UTF-8」 | `[System.IO.File]::ReadAllText($log, [Text.Encoding]::Unicode)` |
| 只走 app execution alias | 直跑 WindowsApps 里的 `cdb.exe` → 「拒绝访问」 | 用探测层 `cdb`，别把它加进 PATH |
| 架构不匹配 | `cdbX86` 调 64 位目标 → `Win32 error 0n50` | 32 位样本去 `%SystemRoot%\SysWOW64\` 找 |
| `da` vs `du` | 满屏 `????` | 裸 ASCII 指针用 `da`；UTF-16 用 `du`；结构体指针先 `dt` 再取 Buffer |

### IDA / Ghidra headless

| 坑 | 表现 | 处置 |
|----|------|------|
| IDA 脚本不退出 | `idat64.exe -A -B -S<script> <file>` 挂住不返回 | 脚本结尾必须有 `idc.qexit(0)`，入口处 `idaapi.auto_wait()` |
| Ghidra 挂控制台 | `analyzeHeadless` 跑完不返回 | 走 `cmd /c`，尾部 `< nul` |
| IDA license | `idat`（9.4）可能无 license 直接 exit 1 | 用 `idat64`（8.3 便携版）作兜底 |

### 探测层与 shell

| 坑 | 表现 | 处置 |
|----|------|------|
| `Get-FileHash` 不存在 | 这台机器上 `Microsoft.PowerShell.Utility` 未加载 | 用 `[System.Security.Cryptography.SHA256]::Create()` 兜底，或 `certutil -hashfile` |
| `Get-AuthenticodeSignature` 不存在 | `Microsoft.PowerShell.Security` 模块加载失败；探测层也无 `signtool`（实测 `Available=False`） | `Import-Module Microsoft.PowerShell.Security` 重试；仍失败就改看 PE 证书表 `r2 -qc 'iH~certificate'`，并记 `quality=unavailable` |
| r2 的 reloc 警告 | stderr 打印 `WARN: Relocs has not been applied`；配合 `2>&1` 会变成 `NativeCommandError` 记录污染输出 | 一律 `2>$null`，需要 stderr 时单独抓 |
| `rabin2` 在重定向下会卡 | `-I` 偶发进入交互 prompt（实测 `-- No cookie is also a cookie`） | **用 `r2 -qc` 代替 `rabin2`**；确实要用就加超时 |
| 脚本执行策略 | `. Bootstrap.ps1` 报「禁止运行脚本」 | 用 `powershell -NoProfile -ExecutionPolicy Bypass -File <脚本>` |
| 脚本里的 `$` 被吃掉 | 从 bash 拼 `-Command "... $_ ..."` 时变量被外层 shell 展开 | 复杂脚本一律写 `.ps1` 文件再 `-File` 执行 |

### capa

| 坑 | 表现 | 处置 |
|----|------|------|
| 官方 exe 被 Defender 隔离 | 装不上 | 用 PyPI 版；本机已装 `capa.bat` 9.4.0 |
| 全量扫描很慢 | 大文件几分钟起 |  triage 阶段用 `-r '<规则名>'` 挑着跑，全量留给后面 |

---

## 证据与验证闭环

- 固定输入样本、SHA256、工具版本和全部参数，先保存未处理 baseline。
- 每个假设至少绑定一个可观察量：已知明密文对、协议字段、状态转移、时间分布、偏移或重放输出。
- §6.2 的断点计划里**至少第一行实测命中过**，并把 `cdb.log` 一起归档 —— 没实测的断点只是猜测。
- 原始样本留在原处，所有派生文件写进 `$Out`，`triage.md`（本包未落地） 里记录每一步的转换链。
- 结论沉淀到 `REVERSE-MAP.md`（本包未落地）（特征码 ≥16 字节带 `??`），供程序更新后复用。

---

## 相关

- `re-agent-workflow.md` — 主工作流门闩，§1 Triage 的完整版、IAT 修复铁律
- `../anti-analysis.md` — 反调试/反分析菜谱 A–T
- `../kernel-driver-reverse.md` — 样本是 `.sys` 时
- `ollvm-deobfuscation.md` — 熵高且是控制流平坦化时
- `nonpe-format-cookbook.md` — 样本不是 PE 时（U–AV / AW–DN）
- `ai-assisted-re.md` — 语义恢复 / 神经反编译
- `signal-to-tool-decision.md` — **不知道下一步该用哪个工具时看这篇**
- `../../ghidra-reverse/SKILL.md` — Ghidra 无头正确姿势
- `../../ops/scope-contract.md` — 案件建档