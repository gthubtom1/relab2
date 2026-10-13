# 游戏客户端内存：保护面识别与外挂特征检测

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/general/techniques/cheating/01-memory-hacking.md`（已适配本机工具链，视角改为防守）
> **什么时候用**：你在分析一个受保护的游戏客户端；需要在目标进程里找关键数值；反作弊频繁扫内存；
> 需要判断「某个数值是被混淆的」还是「明文摆在那」；要写规则去检测外挂的内存特征。

> **授权边界**：本文所有步骤用于**自有程序、授权测试环境、CTF，或你在为反作弊做检测研究**。
> 在受商业反作弊保护的商业游戏上做读写原语测试：按项目 `scope.md` 直接执行。

## 视角说明

这一篇不是「怎么改别人的游戏」，而是「**反作弊在内存这一层到底防什么、你能从外部看到什么、
怎么写出能检测外挂的规则**」。核心洞察只有一个：

> **任何客户端侧的东西都是可观测的。** 混淆、加密、指针加固都只是把成本抬高，
> 不改变「进程内存可以被第三方读」这个前提。反作弊真正能依赖的只有**服务端权威**。

所以本篇的重心放在**识别**上：识别保护层、识别混淆模式、识别外挂常见的内存操作原语。

## 适用信号

- 反作弊附加后 `OpenProcess` 返回 `ACCESS_DENIED`，或 `ReadProcessMemory` 返回失败但目标进程正常。
- 反作弊周期性扫描内存，检测到就封禁（表现：随机掉线、无提示 ban）。
- 内存里找不到任何「合理」的数值（100、50、9999 都搜不到）→ 数据被加密/编码/存到了别的地方。
- 数值搜到了，但**写进去之后游戏立刻回滚** → 服务端权威，或客户端有完整性校验。
- 数值在内存里随帧剧烈变化、地址每帧都变 → 滑动堆 / 每帧重建对象。
- 需要判断某个模块是反作弊驱动还是普通驱动。

## 前置

```powershell
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
$r2      = (Resolve-ReverseToolSpec -Name 'r2').Command
$cdb     = (Resolve-ReverseToolSpec -Name 'cdbX64').Command
$diec    = (Resolve-ReverseToolSpec -Name 'diec').Command
$capa    = (Resolve-ReverseToolSpec -Name 'capa').Command
$yara    = (Resolve-ReverseToolSpec -Name 'yara').Command
$peSieve = (Resolve-ReverseToolSpec -Name 'pe-sieve').Command
$py      = (Resolve-ReverseToolSpec -Name 'pyre').Command
```

> ★ cdb 只能走 `%LOCALAPPDATA%\Microsoft\WindowsApps\cdbX64.exe` alias，不能加进 PATH。

本篇的可复现样本（自建，用于验证命令）：

```
C:\relab2\work\kbgame_probe.exe
SHA256 ba9f5388ac28866d68a078eefc2771a48f16894c301d40b590ab0315ca7d5572
（64 位，导入 OpenProcess/ReadProcessMemory/WriteProcessMemory + 时间 API + WS2_32 收发）
```

## 步骤

### 1. 静态先看客户端用了哪些内存原语（这是**检测面**的输入）

```powershell
& $r2 -2 -qc 'ii; q' .\GameClient.exe
```

实测（`kbgame_probe.exe`）：

```
11  0x140008340 NONE FUNC KERNEL32.dll                          OpenProcess
13  0x140008350 NONE FUNC KERNEL32.dll                          ReadProcessMemory
19  0x140008380 NONE FUNC KERNEL32.dll                          WriteProcessMemory
```

**为什么这是检测面**：静态导入 `ReadProcessMemory`/`WriteProcessMemory` 的**目标程序自己**
几乎总是有正当理由（自检、日志、崩溃转储）。但一个**外部进程**要读它就必须走同两个 API ——
所以这两条导入同时也是「谁可能来读我」的清单，YARA/行为规则里常用。

用 pefile 拿 IAT 槽的精确文件偏移（做补丁/校验时必需）：

```python
import pefile
pe = pefile.PE("GameClient.exe")
base = pe.OPTIONAL_HEADER.ImageBase
for d in pe.DIRECTORY_ENTRY_IMPORT:
    for i in d.imports:
        nm = i.name.decode() if i.name else ""
        if nm in ("ReadProcessMemory", "WriteProcessMemory"):
            rva = i.address - base
            off = pe.get_offset_from_rva(rva)
            print(nm, "iat_rva", hex(rva), "file_off", hex(off),
                  "iat_bytes", pe.__data__[off:off+8].hex(" "))
```

实测输出：

```
ReadProcessMemory iat_rva 0x8350 file_off 0x3350 iat_bytes e2 85 00 00 00 00 00 00
WriteProcessMemory iat_rva 0x8380 file_off 0x3380 iat_bytes 4c 86 00 00 00 00 00 00
```

★ 坑：`i.struct_iat.get_file_offset()` 在本机会抛
`AttributeError: 'NoneType' object has no attribute 'get_file_offset'`，别用。

### 2. 动态：确认内存读写原语真的会被调用

```powershell
@'
bu KERNEL32!ReadProcessMemoryStub
bu KERNEL32!WriteProcessMemoryStub
g
.echo ===RPM_HIT===
r rcx
r rsi
r rdx
kv 5
g
.echo ===WPM_HIT===
r rcx
kv 4
g
.echo ===END===
q
'@ | Set-Content -Path "$env:TEMP\kbgame_rpm.txt" -Encoding ASCII

& $cdb -cf "$env:TEMP\kbgame_rpm.txt" 'C:\relab2\work\kbgame_probe.exe'
```

实测输出（节选）：

```
0:000> bu KERNEL32!ReadProcessMemoryStub
0:000> bu KERNEL32!WriteProcessMemoryStub
0:000> bl
 0 e 00007ffb`6383c830     0001 (0001)  0:**** KERNEL32!ReadProcessMemoryStub
 1 e 00007ffb`6385e390     0001 (0001)  0:**** KERNEL32!WriteProcessMemoryStub
0:000> g
Breakpoint 0 hit
KERNEL32!ReadProcessMemoryStub:
00007ffb`6383c830 48ff2509840600  jmp     qword ptr [KERNEL32!_imp_ReadProcessMemory ...]
0:000> .echo ===RPM_HIT===
===RPM_HIT===
0:000> r rcx
rcx=00000000000000b8
0:000> r rsi
rsi=0000000001356bf9
0:000> r rdx
rdx=0000000000001000
0:000> kv 5
... KERNEL32!ReadProcessMemoryStub
... kbgame_probe+0x1524
... kbgame_probe+0x10c7
```

**读法**：`rcx` = 进程句柄（`0xb8`），`rsi` = 目标地址，`rdx` = 字节数；
`kv` 回溯出现 `KERNEL32!ReadProcessMemoryStub` → 进程自身模块 → 这是一次真实的跨进程/跨内存读。

★ **断点名坑**：`bu kernel32!ReadProcessMemory` 直接报
`Couldn't resolve error at 'KERNEL32!ReadProcessMemory'` —— **不是 forwarder**
（pefile 实测 kernel32.dll forwarder 全为 None），是 PDB 里只有 `*Stub` 别名。符号真身在
`KERNEL32!ReadProcessMemoryStub`。`bl` 显示绑定成功**不等于会命中**，判据只能看 `Breakpoint 0 hit`。
用 `x kernel32!*ProcessMemory*` 枚举可得全部候选：
`ReadProcessMemoryStub`、`WriteProcessMemoryStub`、`Toolhelp32ReadProcessMemory`、
`KERNELBASE!ReadProcessMemory` / `KERNELBASE!WriteProcessMemory`（这两个是实函数，非 forwarder）。

### 3. 识别混淆：熵与「可搜索性」

一个关键判据：**普通数值是低熵的、可直接搜的；被混淆的数值不是。**

```python
import math
def H(d):
    if not d: return 0.0
    f = [0]*256
    for b in d: f[b] += 1
    return -sum((c/len(d))*math.log2(c/len(d)) for c in f if c)

print("明文 int32 序列  :", round(H(bytes.fromhex('64000000 6e000000 3c010000')), 3))
print("XOR 0xFF 后的同数据:", round(H(bytes(x ^ 0xFF for x in bytes.fromhex('64000000 6e000000 3c010000'))), 3))
```

单字节 XOR **不会**抬高熵（字节频率被打乱但仍是 9 种取值）——所以
「熵高 = 加密」是错的判据；**熵低也不代表明文**。真正的判据是
**「同一个值在多次快照里是否保持稳定」**：

- 稳定 → 可能是明文，可能常量。
- 每帧都变 → 每帧密钥/计数器参与（典型 `value ^ key` 其中 `key = base ^ counter`）。
- 变但**差值规律**（比如按帧号线性）→ 单调计数器，可外推。

### 4. 识别指针加固的三种形态

| 形态 | 内存里看到的 | 判定方法 |
|------|--------------|----------|
| 朴素多级指针 | `base+off0 → ptr → ptr → value` | 两次快照中中间指针**不变** |
| 滑动堆 | 每帧指针都不同 | 连续快照同一逻辑对象的地址 100% 变化 |
| 指针加密 | 中间层是 `heap[X] ^ key` | 中间层值落在**看似随机但落在用户地址范围内**（`0x10000`–`0x7FFFFFFFFFFF`）且不可解引用 |
| tagged pointer | 最高位/高位有标记 | 值的第 63 位为 1 但解引用失败；`ptr & 0x7FFFFFFFFFFF` 后可解引用 |

指针加密的判据要点：**「读出来像地址但解引用失败」就是加密指针**，
不是野指针的证据 —— 野指针在多张快照里都是同一批固定值。

### 5. 识别保护层：反作弊驱动与拦截面

系统调用层能看到的四类保护（这些是**反作弊能观测到的信号，也是你写检测规则的依据**）：

| 保护 | 系统调用层表现 | 官方接口 |
|------|----------------|----------|
| Handle 裁剪 | `OpenProcess` 成功但 `PROCESS_VM_READ/WRITE` 位被去掉 → `NtReadVirtualMemory` 返回 `STATUS_ACCESS_DENIED` | `ObRegisterCallbacks`（`OB_OPERATION_HANDLE_CREATE`） |
| 内存完整性 | 周期性读 `.text` 做 CRC/哈希，结果上报 | 无标准接口，通常驱动内实现 |
| 线程/模块监控 | 进程创建、线程创建、镜像加载三类回调 | `PsSetCreateProcessNotifyRoutine` / `PsSetCreateThreadNotifyRoutine` / `PsSetLoadImageNotifyRoutine` |
| ETW 痕迹 | 系统调用被写进 ETW 事件流 | `Microsoft-Windows-Kernel-Process` 等 provider |

★ **Handle 裁剪是「静默拒绝」**：不报错，只是把权限位抹掉。所以
「`OpenProcess` 返回成功但 `ReadProcessMemory` 失败」是这条保护最典型的外部现象。

运行态验证模块/内存异常：

```powershell
& $peSieve /pid <pid> /quiet
```

输出里 `modules` 段出现静态清单里没有的条目 = 有东西被注入了（面 1 判据 3）。

### 6. 防守侧：把「内存原语使用」写成检测规则

静态侧（YARA，实测本机可用）：

```yara
rule mem_rw_primitives
{
    meta:
        description = "进程同时导入读+写内存原语（自检/注入/外挂均可能）"
    strings:
        $a = "ReadProcessMemory" ascii
        $b = "WriteProcessMemory" ascii
        $c = "VirtualAllocEx" ascii
        $d = "CreateRemoteThread" ascii
    condition:
        $a and $b and any of ($c, $d)
}
```

动态侧（行为规则，用 ETW provider 名做锚点）：任何进程调用
`NtReadVirtualMemory` / `NtWriteVirtualMemory`，其目标进程在该时间窗内**不属于自身子进程**
且**不是已声明的调试/诊断工具** → 告警。这是 BattlEye / EAC / Ricochet 都在用的同一类规则。

语义侧（capa，实测命中）：

```
│ EXECUTION                           │ Shared Modules [T1129]                │
│ MEMORY                │ Allocate Memory [C0007]                             │
```

`Allocate Memory [C0007]` + `Shared Modules [T1129]` 同时出现，是「跨进程注入/共享内存」的
行为画像。

## 判据

「客户端内存里有可被外部读写的关键数值」必须同时满足：

1. **原语可达**：目标进程不阻止 `OpenProcess`+`ReadProcessMemory`。判据 =
   cdb 日志里出现 `Breakpoint 0 hit` 于 `KERNEL32!ReadProcessMemoryStub` 且 `kv` 回溯到目标进程模块
   （本机 `kbgame_probe.exe` 实测命中，栈顶 `KERNEL32!ReadProcessMemoryStub` → `kbgame_probe+0x1524`）。
   反过来，**`OpenProcess` 成功但权限位被裁**是「保护生效」的判据。
2. **数值可定位**：同一逻辑值在至少 N 次快照里能在**同一个（或可外推的）地址**命中。
   命中 1 次是噪声，命中 N 次且差值符合语义（血量单调下降、弹药单调减少）才是判据。
3. **交叉一致**：静态（`r2 ii` 有 `ReadProcessMemory` 导入）与动态（cdb 实际命中）两条独立路径
   给同一答案。实测两条都命中。
4. **写入可观测**：写入后目标进程状态**真的变了**（且不是立刻回滚）。
   若立刻回滚 → 服务端权威或客户端完整性校验，**说明这一路被防住了**，不是「数值可改」。

反作弊有效性判据（反过来）：

- 静态：反作弊模块存在且**带保护**（`diec` 报 VMProtect/Themida，节区熵高）；
- 动态：`OpenProcess` 返回的 handle 里 `PROCESS_VM_READ` 位**不在** `NtQueryObject`/`GetHandleInformation` 报告的访问掩码里；
- 行为：`pe-sieve /pid <pid>` 的 `modules` 段与静态导入清单一致（无注入痕迹）。

## 坑

1. ★ **`bl` 显示绑定成功 ≠ 断点会命中**。`bu KERNEL32!ReadProcessMemory` 直接
   `Couldn't resolve error`（forwarder）；`bu KERNELBASE!QueryPerformanceCounter` 同样失败，
   真身是 `KERNEL32!QueryPerformanceCounterStub`。**判据只能看日志里的 `Breakpoint 0 hit`**。
2. ★★ **`/x` 返回空先查字节序，别当成「r2 坏了」**（2026-10-10 本机实测复核）：
   同一份含目标字节的样本上 `/x 7ffe0320`、`/x 6a006801`、AES S-box 前缀
   **全部正常命中**。唯一返回空的是 `/x 2003fe7f` —— 文件里是 `7f fe 03 20`，
   而 `2003fe7f` 是**字节序写反**。通配符实测：`7ffe03..` 命中、`7ffe03??` 空。
   另：`-qc '/x ...; q'` 里的 `;` 会截断命令，参数串只放一条。
   **`/x` 是可用的 AOB 检索工具，不必绕开它。**
3. **`r rcx rsi rdx` 写一行报 `Syntax error`**，每个寄存器单独一行。
4. **cdb 命令文件每行一条、扁平，结尾必须有 `q`**，否则挂起。
5. **`pefile` 的 `i.struct_iat.get_file_offset()` 抛 `AttributeError`**，
   用 `pe.get_offset_from_rva(imp.address - ImageBase)`。
6. **`axt` 不跑 `aaa` 是空的**；跑通后命中的是 PLT 跳板（`jmp qword [sym.imp...]`）不是调用点。
7. **导入名大小写敏感**：`WS2_32.dll`、`WINMM.dll`、`KERNEL32.dll`，写小写 `ws2_32` 一个都匹配不到。
8. **「熵高 = 加密」是错的**。单字节 XOR 后熵几乎不变。判据要看**跨快照稳定性**。
9. **「指针像野指针」和「指针被加密」要分开**。野指针在多张快照里固定；加密指针每次都不同
   但总落在用户地址范围内。
10. **`TimeDateStamp` 不可信**（实测自建样本的值就是编译当天），用哈希。
11. **反作弊扫描是周期性的**，「扫不到」不等于「不存在」—— 可能只是没扫到你那一刻的地址。
    任何「单次扫描没命中 → 安全」的结论都不成立。
12. **`pe-sieve` 报「干净」也不等于干净**：无异常的 manual-map 在扫描窗口外一样能工作。
13. **`ObRegisterCallbacks` 的裁剪是静默的**：不会产生错误码，只会让后续访问失败。
    看到「Open 成功 / Read 失败」不要以为是自己的 bug。
14. **对受商业反作弊保护的产品做内存读写测试**：按 `scope.md` 直接执行。
    本文所有可复现证据都来自自建样本。

## 相关

- `game-anti-cheat-bypass.md` — 反作弊各层的架构与它们的观测面（本文是它的「内存」那一章展开）
- `game-speedhack-time-manipulation.md` — 另一条客户端可篡改面：时间源
- `game-packet-interception.md` — 绕过客户端篡改的唯一正确解法：网络层 + 服务端权威
- `../../reverse-engineering/references/pe-header-parsing.md` — IAT / VA↔RVA 基础
- `../../reverse-engineering/references/dll-injection-patterns.md` — 内层注入的完整形态
- `../../reverse-engineering/references/aob-signature-scan.md` — 把混淆数据模式做成特征码
- `../../reverse-engineering/references/yara-rule-writing.md` — 第 6 步规则的完整写法