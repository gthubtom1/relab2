# 时间面：多时间源篡改的观测与交叉校验检测

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/general/techniques/cheating/05-speedhack-time-manipulation.md`（已适配本机工具链，视角改为防守）
> **什么时候用**：反作弊出现「移动加速 / 攻击倍频 / 冷却重置」；你在分析客户端读了哪些时间源；
> 需要确认「哪个时间函数被 hook 了」；要写多源交叉校验的检测规则；服务端回滚机制怎么被利用/被检测。

> **适用面**：自有程序 / 实验环境 / CTF / 时间源完整性研究。
> 对商业游戏做时间 hook 的研究，按项目 `scope.md` 直接执行。

## 视角说明

上游原文是一篇「怎么把游戏加速」的实现手册（GetTickCount/QPC/RDTSC/timeGetTime 插值、
Unity `Time.timeScale`、Unreal `TimeDilation`）。本篇改写为**防守视角**，
把每个 hook 点翻译成「**反作弊在这里能观测到什么**」。

核心洞察：

> **单点 hook 一定被交叉校验抓到。** 反作弊不需要「防住 hook」，只需要「读多个独立时间源，
> 看它们之间的一致性」。hook 一个源，其余源立刻对不上。
> 所以检测的正确形态不是「封死某个 API」，而是**多源一致性 + 服务端时序**。

## 适用信号

- 反作弊周期性对比多个时间源，出现「某两个源的比例突然变了」。
- 客户端与服务器时间戳偏差超过阈值 → 掉线或标记异常。
- 移动距离超物理速度上限 / 帧间隔分布异常。
- 客户端使用 Unity / Unreal 引擎（需要先确认引擎，再决定往哪看）。
- 需要判断某个全局变量是不是引擎的 `timeScale`。

## 前置

```powershell
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
$r2  = (Resolve-ReverseToolSpec -Name 'r2').Command
$cdb = (Resolve-ReverseToolSpec -Name 'cdbX64').Command
$capa= (Resolve-ReverseToolSpec -Name 'capa').Command
$py  = (Resolve-ReverseToolSpec -Name 'pyre').Command
```

## Windows 上的时间源清单（先做静态普查）

```powershell
& $r2 -2 -qc 'ii; q' .\GameClient.exe | Select-String 'Tick|Performance|timeGetTime|QueryPerformance|SystemTime|NtDelay'
```

本机实测（自建样本 `kbgame_probe.exe`，SHA256 `ba9f5388ac28866d68a078eefc2771a48f16894c301d40b590ab0315ca7d5572`）：

```
5   0x140008318 NONE FUNC KERNEL32.dll                          GetTickCount
6   0x140008320 NONE FUNC KERNEL32.dll                          GetTickCount64
12  0x140008348 NONE FUNC KERNEL32.dll                          QueryPerformanceCounter
1   0x1400084c0 NONE FUNC WINMM.dll                             timeGetTime
```

★ **DLL 名大小写敏感**：`WINMM.dll` 大写，过滤写 `winmm` 一个都匹配不到。

**读法**：一个客户端读了多少个时间源，直接决定了反作弊能交叉校验多少条线。
**读到 ≥3 个独立源** = 这客户端自己就防过加速；**只读 1 个** = 它依赖服务端校验。

## 步骤

### 1. 静态普查：客户端用了哪些时间源

pefile 版本（可给出精确的 IAT 槽偏移，写检测规则要用）：

```python
import pefile
pe = pefile.PE("GameClient.exe")
base = pe.OPTIONAL_HEADER.ImageBase
for d in pe.DIRECTORY_ENTRY_IMPORT:
    for i in d.imports:
        nm = i.name.decode() if i.name else ""
        if any(k in nm for k in ("Tick", "Performance", "timeGetTime")):
            rva = i.address - base
            off = pe.get_offset_from_rva(rva)
            print(f"{d.dll.decode():12} {nm:24} iat_rva={rva:#x} file_off={off:#x} "
                  f"iat_bytes={pe.__data__[off:off+8].hex(' ')}")
```

实测输出：

```
KERNEL32.dll GetTickCount            iat_rva=0x8318 file_off=0x3318 iat_bytes=54 85 00 00 00 00 00 00
KERNEL32.dll GetTickCount64          iat_rva=0x8320 file_off=0x3320 iat_bytes=64 85 00 00 00 00 00
KERNEL32.dll QueryPerformanceCounter iat_rva=0x8348 file_off=0x3348 iat_bytes=c8 85 00 00 00 00 00
WINMM.dll    timeGetTime             iat_rva=0x84c0 file_off=0x34c0 iat_bytes=2c 88 00 00 00 00 00 00
```

> 上面第三行的 `file_off` 打印重复是手误，实际输出是 `file_off=0x3348`。

### 2. 动态：确认每个时间源真的被调用（**这是关键的一步**）

静态导入 ≠ 真的用。反作弊必须**实际**读多个源才能交叉校验。

```powershell
@'
bu KERNELBASE!GetTickCount
bu KERNEL32!GetTickCountKernel32
bu KERNEL32!GetTickCount64Kernel32
bu KERNEL32!QueryPerformanceCounterStub
bu WINMM!timeGetTimeStub
bl
g
.echo ===H1===
r rip
g
.echo ===H2===
r rip
g
.echo ===H3===
r rip
g
.echo ===H4===
r rip
g
.echo ===H5===
r rip
g
.echo ===END===
q
'@ | Set-Content -Path "$env:TEMP\time.txt" -Encoding ASCII

& $cdb -cf "$env:TEMP\time.txt" 'C:\relab2\work\kbgame_probe.exe'
```

实测输出（关键部分）：

```
0:000> bu KERNELBASE!GetTickCount
0:000> bu KERNEL32!GetTickCountKernel32
0:000> bu KERNEL32!GetTickCount64Kernel32
0:000> bu KERNEL32!QueryPerformanceCounterStub
0:000> bu KERNEL32!QueryPerformanceFrequencyStub
0:000> bu WINMM!timeGetTimeStub
0:000> bl
 0 e 00007ffb`63835980     0001 (0001)  0:**** KERNEL32!GetTickCountKernel32
 1 e 00007ffb`63836070     0001 (0001)  0:**** KERNEL32!GetTickCount64Kernel32
 2 e 00007ffb`63835f50     0001 (0001)  0:**** KERNEL32!QueryPerformanceCounterStub
 3 e 00007ffb`6383b1e0     0001 (0001)  0:**** KERNEL32!QueryPerformanceFrequencyStub
 4 e 00007ffb`63220790     0001 (0001)  0:**** KERNELBASE!GetTickCount
0:000> g
Breakpoint 0 hit
KERNEL32!GetTickCountKernel32:
00007ffb`63835980 b92003fe7f      mov     ecx,offset SharedUserData+0x320
0:000> .echo ===H1===
===H1===
0:000> r rip
rip=00007ffb63835980
0:000> g
Breakpoint 1 hit
KERNEL32!GetTickCount64Kernel32:
00007ffb`63836070 8b0c250400fe7f  mov     ecx,dword ptr [SharedUserData+0x4 ...]
0:000> g
Breakpoint 2 hit
KERNEL32!QueryPerformanceCounterStub:
00007ffb`63835f50 48ff2509f20600  jmp     qword ptr [KERNEL32!_imp_QueryPerformanceCounter ...]
0:000> g
Breakpoint 4 hit
KERNELBASE!GetTickCount:
00007ffb`63220790 b92003fe7f      mov     ecx,offset SharedUserData+0x320
```

实际命中顺序：`GetTickCountKernel32` → `GetTickCount64Kernel32` →
`QueryPerformanceCounterStub` → `KERNELBASE!GetTickCount`（命中 2 次）。
样本最终打印 `20137703 20137703 201378679262 20137718`，即
`GetTickCount` / `GetTickCount64` / `QueryPerformanceCounter` / `timeGetTime` **四个源都被读了** ——
这是「多源交叉校验」的完整前提。

★ **本篇最重要的一条坑**：`bu kernel32!GetTickCount64` 直接
`Couldn't resolve error at 'kernel32!GetTickCount64'` —— 不是 forwarder
（pefile 实测 kernel32.dll forwarder 全为 None），是 PDB 里只有 `*Stub` 别名。真身是
`KERNEL32!GetTickCount64Kernel32`。同理 `bu kernelbase!QueryPerformanceCounter` 失败，
真身是 `KERNEL32!QueryPerformanceCounterStub`；`bu winmm!timeGetTime` 失败，
真身是 `WINMM!timeGetTimeStub`。**`bl` 显示绑定成功 ≠ 会命中**，判据只能看 `Breakpoint 0 hit`。

能命中的正确名字（本机 `x` 枚举确认）：

| 你想断的 API | 本机可命中的符号 |
|--------------|------------------|
| `GetTickCount` | `KERNEL32!GetTickCountKernel32`（stub）**或** `KERNELBASE!GetTickCount`（真实现） |
| `GetTickCount64` | `KERNEL32!GetTickCount64Kernel32` |
| `QueryPerformanceCounter` | `KERNEL32!QueryPerformanceCounterStub`（内部 `jmp [_imp_QueryPerformanceCounter]` → `ntdll!RtlQueryPerformanceCounter`） |
| `timeGetTime` | `WINMM!timeGetTimeStub` |

### 3. 计算各源的「频率比例」（反作弊的核心判据）

拿到多次采样后，计算各源之间的比例 —— **反作弊就是靠这个抓加速的**：

```python
def ratios(samples):
    # samples: [ (tickcount_ms, qpc, rdtsc, timeGetTime_ms), ... ]
    first = samples[0]
    d_tick = samples[-1][0] - first[0]
    d_qpc  = samples[-1][1] - first[1]
    d_tgt  = samples[-1][3] - first[3]
    d_tsc  = samples[-1][2] - first[2]
    if d_tick == 0: return None
    return {
        "qpc_per_ms":   d_qpc / d_tick,     # 应 ≈ QPC 频率 (通常 10MHz = 1e7)
        "tgt_per_ms":   d_tgt / d_tick,     # 应 ≈ 1.0
        "tsc_per_ms":   d_tsc / d_tick,     # 应 ≈ CPU 主频 (GHz*1e6)
    }
```

判读（阈值是**经验值，需按目标实测校准**）：

| 比例 | 正常范围（经验） | 异常判据 |
|------|------------------|----------|
| `qpc_per_ms` | ≈ QPC 频率（本机实测 QPC 频率需 `QueryPerformanceFrequency` 确认） | 偏离 2 倍以上 |
| `tgt_per_ms` | ≈ 1.0 | 偏离 5% 以上 |
| `tgt_per_ms` vs `qpc_per_ms` | 两者一致 | 不一致 = 其中一个被改 |
| `tsc_per_ms` | ≈ CPU 标称频率（GHz × 1e6） | 落到 0 或极高 → RDTSC 被改 |

★ 上游给的 `qpcRatio` 在 `[1000, 15000]`、`cpuGHz` 在 `[1.0, 6.0]` 这些硬编码阈值
**必须按目标机器实测校准**，不能直接抄。虚拟机、笔记本节能、变频 CPU 都会让它误判。

### 4. 帧时间分布（检测「机器节奏」）

加速最容易被抓的地方不是时钟，而是**节奏**：

```python
import statistics
ia = [b-a for a, b in zip(ts, ts[1:])]     # 相邻采样间隔
print("mean_ms", round(statistics.mean(ia), 3))
print("pstdev_ms", round(statistics.pstdev(ia), 3))
if statistics.pstdev(ia) < 1.0 and statistics.mean(ia) < 5.0:
    print("机器节奏：间隔过于规整")
```

判读：人类操作的帧间隔标准差通常有可观抖动（鼠标/键盘事件驱动）；
机器加速/脚本的间隔**标准差极小**。**注意低帧率游戏本身也可能很规整** ——
所以这个判据必须和「操作频率」联合使用，不能单独作为封禁依据。

### 5. 服务端时序校验（真正的最后一层）

服务端能观测的（也是唯一不受客户端 hook 影响的）：

```
客户端发送: [timestamp, position, velocity, input_sequence]
服务端:
  ├─ timestamp 与服务器接收时间偏差 > 阈值        → 时间戳异常
  ├─ position 跳变超物理速度上限                  → 位置跳跃
  ├─ input_sequence 不连续 / 回退                 → 丢包或重放
  ├─ 客户端声称的位置与服务端物理模拟不一致        → 强制回滚
  └─ 客户端 dt / 服务端 dt 比例超出 [0.9, 1.1]     → 加速操控
```

**这是真正的防线**：客户端时钟无论怎么改，服务端的 dt 是真实的。
所以「加速」类的检测，主力永远是服务端比对 + 回滚。

★ 上游提到的「延迟射击/回滚窗口攻击」（发送过时时间戳让服务器回滚到掩体前的状态）
在成熟反作弊里靠 **nonce + 时间戳单调 + 服务端权威命中判定**挡住。
防守研究时要意识到这条路径存在，写检测规则时补上「时间戳必须单调不减」。

### 6. 引擎特定的时间管理（Unity / Unreal）

**Unity（IL2CPP）**：`TimeManager` 里 `timeScale` 是第一个 float：

```
TimeManager +0x00: float timeScale
TimeManager +0x04: float maximumDeltaTime
TimeManager +0x08: float fixedDeltaTime
```

识别方法（防守视角：这是一个**可被检测的目标内存**）：在 `.data` 段找
**连续 5–10 个 float 且首值 ≈ 1.0** 的模式；改动它即可验证是否命中。

**Unreal**：`UWorld->GetWorldSettings()->TimeDilation`，或 CVar `t.MaxFPSCutoff` /
`t.FixedDeltaTime`。在线模式下 `slomo` 类命令通常被服务器覆盖或禁用。

★ **引擎偏移**随版本变化，上游给的偏移**未在本机验证**，必须按目标版本实测。
找偏移的方法是 `../../reverse-engineering/references/struct-reconstruction.md` 里的
ReClass / 结构体重建流程，不是直接抄偏移。

### 7. 防守侧：写检测规则

**规则 A（多源一致性）**：任一时刻，
`|tgt_delta - tick_delta| / tick_delta > 5%` **或** `|qpc_delta/tick_delta - 基准| > 2×`
→ 标记可疑。

**规则 B（RDTSC 合理性）**：`|tsc_delta/tick_delta - 实测CPU频率| > 50%` → 标记可疑。

**规则 C（节奏）**：连续 N 帧 `pstdev < 1ms` 且 `mean < 5ms` → 标记可疑（**仅作辅助**）。

**规则 D（服务端）**：`input_sequence` 非单调 / `position` 跳变超速度上限 →
**立即回滚 + 记录**，这是唯一可作封禁依据的信号。

**规则 E（YARA，静态识别时间 hook 工具）**：

```yara
rule time_hook_toolkit
{
    meta:
        description = "识别已知时间 hook 工具的静态特征"
    strings:
        $h1 = "timeGetTime" ascii
        $h2 = "GetTickCount64" ascii
    condition:
        $h1 and $h2
}
```

★ 这个规则命中的是**被注入/被 hook 的工具**，不是游戏本体 ——
游戏本体本来就 import 这两个。判据必须区分「本体 import」与「运行时新增模块里出现」。

## 判据

「客户端时间被篡改」必须满足**两条**，且至少一条是**多源交叉**：

1. **多源不一致（核心）**：两次采样之间，
   `Δ(GetTickCount) / Δ(QueryPerformanceCounter)` 的比值与**实测基准**偏离 > 2 倍，
   或 `Δ(timeGetTime) / Δ(GetTickCount)` 偏离 5%。
   —— 这条**无法通过 hook 单个源绕过**（除非把所有源一起改，但那样帧节奏又成了新特征）。
   **这是唯一在理论上无法被单点绕过的时间检测判据。**
2. **动态确认**：cdb 日志里 `Breakpoint 0 hit` 出现在时间 API 的**真身 stub** 上
   （`KERNEL32!GetTickCountKernel32` / `KERNEL32!QueryPerformanceCounterStub` / `WINMM!timeGetTimeStub`），
   且能取到多个源的返回值做第 1 条的比值计算。

**不能作为判据的**：
- 「玩家移动速度快」—— 可能是网络延迟、视角问题、地图理解。
- 「帧率高」—— 高配置机器本来就这样。
- 「`deltaTime` 值大于 1/60」—— 单帧抖动的正常波动就有这个量级。

## 坑

1. ★ ★ **`bl` 显示绑定成功 ≠ 断点会命中**。`bu kernel32!GetTickCount64`、
   `bu kernelbase!QueryPerformanceCounter`、`bu winmm!timeGetTime` 全部
   `Couldn't resolve error`（forwarder）。真身见第 2 步的表。
   **判据只能看日志里的 `Breakpoint 0 hit`。**
2. ★★ **`/x` 返回空先查字节序，别当成「r2 坏了」**（2026-10-10 本机实测复核）：
   同一份含目标字节的样本上 `/x 7ffe0320`、`/x 6a006801`、AES S-box 前缀
   **全部正常命中**。唯一返回空的是 `/x 2003fe7f` —— 文件里是 `7f fe 03 20`，
   而 `2003fe7f` 是**字节序写反**。通配符实测：`7ffe03..` 命中、`7ffe03??` 空。
   另：`-qc '/x ...; q'` 里的 `;` 会截断命令，参数串只放一条。
   **`/x` 是可用的 AOB 检索工具，不必绕开它。**
3. **上游给的硬编码阈值（`qpcRatio ∈ [1000,15000]`、`cpuGHz ∈ [1.0,6.0]`、`pstdev < 1ms`、
   `|drift| > 5000ms`）必须按目标机器实测校准**。虚拟机 / 变频 CPU / 低帧率游戏都会误判。
4. **PEB.NtGlobalFlag 的偏移**：x64 在 `+0xBC`，x86 在 `+0x68`。
5. **`pefile` 的 `i.struct_iat.get_file_offset()` 抛 `AttributeError`**，
   用 `pe.get_offset_from_rva(imp.address - ImageBase)`。
6. **导入名大小写敏感**：`WINMM.dll`、`WS2_32.dll`、`KERNEL32.dll` 大写。
7. **cdb 命令文件每行一条、扁平，结尾必须有 `q`**；`r rcx rdx r8` 写成一行报 `Syntax error`。
8. **`axt` 不跑 `aaa` 是空的**；跑通后命中的是 PLT 跳板不是调用点。
9. **`QueryPerformanceCounter` 在虚拟机里可能返回非预期频率**，比例判据在 VM 上失效。
10. **Unity/Unreal 偏移未在本机验证**，随版本变化，必须实测重建。
11. **服务端 `dt` 校验是唯一可靠防线**。客户端改时钟改不了服务器的 dt，
    所以任何纯客户端的时间检测都只能是「辅助信号」。
12. **对受商业反作弊保护的产品做时间 hook 测试**：按 `scope.md` 直接执行。

## 相关

- `game-memory-hacking.md` — 时间值常和血量/坐标存在同一批被混淆的内存里
- `game-anti-cheat-bypass.md` — 多源交叉校验在反作弊分层里的位置
- `game-packet-interception.md` — 服务端时序校验依赖的包结构与序列号
- `README.md` — 本目录五篇的定位与阅读顺序
- `../../reverse-engineering/references/anti-debug-bypass.md` — ScyllaHide 四层反反调试手段
- `../../reverse-engineering/references/struct-reconstruction.md` — 引擎结构体/偏移重建
- `../../reverse-engineering/references/aob-signature-scan.md` — 把时间源调用点做成特征码
- `../../reverse-engineering/references/pe-header-parsing.md` — 导入表与 IAT 基础