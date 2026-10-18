# 反作弊架构：分层观测面与检测锚点

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/general/techniques/cheating/04-anti-cheat-bypass.md`（已适配本机工具链，视角改为防守）
> **什么时候用**：你在识别一个未知反作弊属于哪一类（EAC / BattlEye / Vanguard / Ricochet）；
> 需要知道它每一层能观测到什么；你在为它做检测规则；你在解释「为什么我的分析工具失效了」。

> **能力域**：反作弊机制的观测面分析。本地 / lab / 自有资产按项目 `scope.md` 直接执行。

## 视角说明

上游原文是一篇「怎么绕过 EAC/BattlEye/Vanguard/Ricochet」的清单。本篇改写为**防守视角**，
把「绕过方法」这一列整个换掉，换成「**这一层能观测到什么信号、你怎么据此写规则**」。

核心洞察：

> **反作弊的每一层保护都对应一组系统调用级观测点。**
> 你在做逆向时觉得「工具莫名其妙失效」，几乎总是因为撞上了下面某一层。
> 知道分层结构，才能解释现象、才能判断「我看到的是保护生效，还是我自己的 bug」。

## 适用信号

- 目标进程附加后 `OpenProcess` 返回 `ACCESS_DENIED`，或成功后 `ReadProcessMemory` 静默失败。
- `pe-sieve` / 模块枚举里出现了**不属于任何已知发行方**的驱动。
- 目标程序启动时检查虚拟机、调试器、已知黑名单进程/驱动，然后自行退出。
- 驱动加载被要求开启测试签名模式（`bcdedit /set testsigning on`）。
- 目标进程内存在**自己遍历 PEB / 手动解析 EAT** 的代码（说明它也防同类手法）。
- 目标进程里出现 `Microsoft-Windows-Kernel-Process` 等 ETW provider 的订阅。

## 前置

```powershell
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
$r2      = (Resolve-ReverseToolSpec -Name 'r2').Command
$diec    = (Resolve-ReverseToolSpec -Name 'diec').Command
$capa    = (Resolve-ReverseToolSpec -Name 'capa').Command
$cdb     = (Resolve-ReverseToolSpec -Name 'cdb').Command
$peSieve = (Resolve-ReverseToolSpec -Name 'pe-sieve').Command
$scylla  = (Resolve-ReverseToolSpec -Name 'scyllahide').Command
$yara    = (Resolve-ReverseToolSpec -Name 'yara').Command
$py      = (Resolve-ReverseToolSpec -Name 'pyre').Command
```

## 分层观测面（本文主体）

| 层 | 机制 | **可观测信号（防守方视角）** | 逆向时的现象 |
|----|------|------------------------------|--------------|
| **L0 启动前置** | TPM 2.0 / Secure Boot 校验 | 启动链校验失败 → 拒绝加载 | 需要特定硬件/固件配置才启动 |
| **L1 内核驱动** | `ObRegisterCallbacks` handle 裁剪 | `OpenProcess` 成功但 `PROCESS_VM_READ/WRITE` 位被抹 → `NtReadVirtualMemory` 返 `STATUS_ACCESS_DENIED` | **静默拒绝**，不报错，最难察觉 |
| **L1' 内核驱动** | `PsSetCreateProcessNotifyRoutine` / `...Thread...` / `...LoadImage...` | 进程/线程/镜像创建全量事件 | 任何注入都在这里留痕 |
| **L1'' 内核驱动** | 内核内存完整性校验（定时 CRC/哈希） | 代码段被改 → DPC 例程/定时器上报 | 修改内核代码后随机蓝屏或被踢 |
| **L2 内核内存监控** | 周期性扫描已知作弊特征码 | 扫描到特征 → 上报 | 「没做坏事也被封」= 误报 |
| **L3 用户态 DLL** | 进程内检测 DLL（`EasyAntiCheat_EOS.dll`、`BEClient.dll` 等） | DLL 在游戏进程里，capa 会给它打上可疑分类 | 游戏进程里出现它 = 反作弊附加成功 |
| **L4 渲染/窗口** | 扫描 vtable、枚举 overlay 窗口 | 见 `game-esp-wallhack-rendering.md` | — |
| **L5 ETW** | 订阅系统调用事件流 | `Microsoft-Windows-Kernel-Process` 等 provider 有活动消费者 | 系统调用被记录后上报 |
| **L6 服务端** | 行为分析（K/D、命中率、视角回溯） | 服务端拒绝/回滚/延迟封禁 | 「不封号只封战绩」= 服务端 ML |

## 步骤

### 1. 静态识别：这是不是反作弊组件

```powershell
& $diec .\EasyAntiCheat.sys        # 内核驱动，看有没有壳
& $r2 -2 -qc 'ii; q' .\GameClient.exe | Select-String 'Anti|BattlEye|EOS|vgk|Ricochet'
```

capa 侧的反作弊信号（实测可跑，本机自建样本对照）：

```
│ EXECUTION                           │ Shared Modules [T1129]                │
│ COMMUNICATION         │ Socket Communication::Send Data [C0001.007]         │
```

反作弊二进制通常额外带：`Allocate Memory [C0007]`（分配可执行页做注入）、
大量 `PsSet*NotifyRoutine` 相关导入（内核侧）、自校验用的高熵节区。

内核侧判定（`diec`）：

- 报 VMProtect/Themida/自研壳 → 强保护，静态分析基本无效，必须动态。
- 报「驱动体积 2–3 MB + 高熵」→ 大概率是商业反作弊驱动（体积是其特征之一）。

### 2. 动态：确认 handle 裁剪是否生效（L1，最常见也最容易误判）

```powershell
@'
bu KERNEL32!OpenProcess
g
.echo ===OPENPROC===
r rcx
r rdx
r r8
kv 6
g
.echo ===END===
q
'@ | Set-Content -Path "$env:TEMP\openproc.txt" -Encoding ASCII

& $cdb -cf "$env:TEMP\openproc.txt" 'C:\path\to\GameClient.exe'
```

x64 参数：`OpenProcess(DWORD dwDesiredAccess /*edx*/, BOOL bInherit /*ecx*/, DWORD pid /*r8d*/)`。

★ **关键判读**：`r rdx` 就是调用方**请求的**访问掩码。要确认裁剪，
把请求掩码与事后从 handle 反查到的实际掩码对比（后者需内核视角，用户态查不到，
所以现象上就是「Open 成功但 RPM 失败」）。

本机实测（自建样本，无反作弊，`r2 ii` 已确认导入 `OpenProcess`）：

```
11  0x140008340 NONE FUNC KERNEL32.dll                          OpenProcess
```

用 cdb 断到它（本机样本 `kbgame_probe.exe`）：

```
bu KERNEL32!OpenProcessStub   ← ★ 见坑 1，必须用 Stub
```

★ **断点名的 forwarder 坑（本文最重要的一条坑）**：
`bu KERNEL32!OpenProcess` 直接报
`Couldn't resolve error at 'KERNEL32!OpenProcess'` —— **不是 forwarder**
（pefile 实测 kernel32.dll 的 forwarder 全为 None），真实原因是公开 PDB 里
只有 `KERNEL32!OpenProcessStub`，没有裸名 `OpenProcess`。符号真身在
`KERNEL32!OpenProcessStub`。**`bl` 显示绑定成功 ≠ 断点会命中**，
判据只能看日志里的 `Breakpoint 0 hit`。用 `x kernel32!*OpenProcess*` 枚举候选。
（本机实测能命中的同类：`KERNEL32!GetTickCountKernel32`、`KERNEL32!QueryPerformanceCounterStub`、
`KERNEL32!ReadProcessMemoryStub`、`WINMM!timeGetTimeStub`、`KERNELBASE!GetTickCount`。）

### 3. 内核侧：进程/线程/镜像创建监控（L1'）

反作弊一旦 `PsSetCreateProcessNotifyRoutine`，**任何进程创建都会经过它的回调**。
这是最可靠的检测锚点之一，因为**它无法被绕过而不被发现**。

在你的分析流程里表现为：新建进程/线程时行为异常（被拒、延迟、进程被杀）。

驱动侧识别（只读，不做对抗）：

```powershell
& $diec .\vgk.sys            # 或 BEDaisy.sys / EasyAntiCheat.sys
& $r2 -2 -qc 'ii~PsSet,ObRegister,CmRegister; q' .\vgk.sys
```

命中 `PsSetCreateProcessNotifyRoutine` / `PsSetCreateThreadNotifyRoutine` /
`PsSetLoadImageNotifyRoutine` / `ObRegisterCallbacks` / `CmRegisterCallback`
→ **这个驱动注册了对应回调**，是该层的确认。

### 4. ETW 层（L5）：系统调用痕迹

ETW 订阅 `Microsoft-Windows-Kernel-Process` 等 provider 后，
`ReadProcessMemory`/`OpenProcess` 等系统调用会进事件流。

判定「客户端是否订阅了 ETW」（防守方视角：这个订阅本身就是可疑行为）：

```powershell
# 用 logman 列 ETW 会话（只读枚举）
logman query -ets
```

★ 本机**未验证该命令返回内容**（需系统有活动的 ETW 会话）。
静态侧替代：`r2 -qc 'ii~EtwEventWrite,TraceEvent,StartTrace; q' .\GameClient.exe` 静态看是否主动写事件。

### 5. PatchGuard / KPP 层（为什么改内核会蓝屏）

x64 Windows 的 Kernel Patch Protection 定期校验 SSDT/IDT/GDT/内核模块/系统进程。

对逆向者的实际影响：**不要改内核代码段**。改了的外部现象是随机蓝屏（BUGCHECK），
而不是任何可捕获的错误码。这是「内核层分析」的红线。

★ 本机**未做内核修改实验**（红线，不验证）。

### 6. 识别是哪一类反作弊（对照表）

| 特征 | EAC | BattlEye | Vanguard | Ricochet |
|------|-----|----------|----------|----------|
| 启动前置 | 无 | 无 | TPM 2.0 + Secure Boot 必需 | 无 |
| 内核驱动 | `EasyAntiCheat.sys` | `BEDaisy.sys`（体积大、频繁更新 hash） | `vgk.sys`（Hyper-V/VTL1 运行） | 内核组件 + 云端 ML |
| 更新节奏 | 随游戏版本 | 每 2–3 天新 hash（极快） | 随系统 | 随游戏版本 |
| 处置风格 | 立即封禁 | 立即封禁 | 立即封禁 + 硬件门槛 | **延迟封禁**（收数据 → 云端 ML → 批量处置） |
| 主要观测面 | handle/线程/模块 | handle/内存扫描/CRC | hypervisor + 内核完整性 | 行为特征（视角/命中率/瞬时转身） |

★ **「延迟封禁」是 Ricochet 的识别特征**：你作弊了当场没反应，
但一周后批量封——这说明它**不在客户端拦你，而是在收数据**。

### 7. 防守侧：写检测规则

**规则 A（模块存在性）**：进程列表里出现
`EasyAntiCheat.exe` / `EasyAntiCheat_EOS.dll` / `BEDaisy.sys` / `vgk.sys`
→ 该进程被 L3 附加。

**规则 B（异常 RPC 访问）**：任一**非声明**进程调用 `NtReadVirtualMemory`/`NtWriteVirtualMemory`，
目标进程带 L3 标记 → 高置信度外挂。

**规则 C（行为）**：位置跳变超物理速度上限 / 命中率显著高于同段位玩家 /
视角瞬时 180° 多次 → 服务端 ML 特征。

**规则 D（YARA，静态识别反作弊二进制本身）**：

```yara
rule eac_eos_artifact
{
    meta:
        description = "识别 EAC 用户态注入 DLL"
    strings:
        $s1 = "EasyAntiCheat_EOS" ascii wide
        $s2 = "EasyAntiCheat.sys" ascii wide
    condition:
        any of them
}
```

★ 本机实测：`yara64.exe` 对单串规则能正常命中；
复合规则要**逐条加串**验证（一次堆多条容易因 `ascii wide` 组合过严而全不命中，见
`../../reverse-engineering/references/windows-attack-surface.md` 与 `../../reverse-engineering/references/yara-rule-writing.md`）。

## 判据

「反作弊的某一层生效」必须满足：

1. **静态**：对应组件/导入**确实存在**。判据命令输出里出现该组件名或回调注册 API 名
   （`r2 -qc 'ii~PsSet,ObRegister; q'` 命中 = 注册了该回调；`diec` 报强壳 = 静态面被封）。
2. **动态**：该层的**拒绝/上报行为真的发生了**，而不是「理论上会」。
   L1 的判据：`OpenProcess` 成功但 `ReadProcessMemory` 失败/返 `STATUS_ACCESS_DENIED`
   （外部可复现）。L4 的判据见 `game-esp-wallhack-rendering.md` 判据。
3. **交叉一致**：静态识别与动态现象指向**同一层**。例如静态看到 `ObRegisterCallbacks`
   注册（L1），动态确实表现为「Open 成功 / Read 失败」（L1）——**两条独立路径同层 = 坐实**。

**不能作为判据的**：
- 「装了这个游戏感觉卡」—— 主观。
- 「进程里有 EasyAntiCheat_EOS.dll 所以我在被监控」—— DLL 存在只说明**附加成功**，
  不说明某次具体操作被记录了。要证明记录，需要第 2 条的拒绝行为或服务端响应。

## 坑

1. ★ ★ **cdb 断点 `*Stub` 别名坑（本目录最高频的坑）**：`bu KERNEL32!OpenProcess` /
   `bu kernel32!GetTickCount64` / `bu kernelbase!QueryPerformanceCounter` 全部
   `Couldn't resolve error`。**`bl` 显示绑定成功不等于会命中**——
   判据只能看日志里的 `Breakpoint 0 hit`。用 `x <dll>!*<name>*` 枚举真身。
2. ★★ **`/x` 返回空先查字节序，别当成「r2 坏了」**（2026-10-10 本机实测复核）：
   同一份含目标字节的样本上 `/x 7ffe0320`、`/x 6a006801`、AES S-box 前缀
   **全部正常命中**。唯一返回空的是 `/x 2003fe7f` —— 文件里是 `7f fe 03 20`，
   而 `2003fe7f` 是**字节序写反**。通配符实测：`7ffe03..` 命中、`7ffe03??` 空。
   另：`-qc '/x ...; q'` 里的 `;` 会截断命令，参数串只放一条。
   **`/x` 是可用的 AOB 检索工具，不必绕开它。**
3. **`axt` 不跑 `aaa` 是空的**；跑通后命中的是 PLT 跳板不是调用点。
4. **`pefile` 的 `i.struct_iat.get_file_offset()` 抛 `AttributeError`**，
   用 `pe.get_offset_from_rva(imp.address - ImageBase)`。
5. **导入名大小写敏感**：`WS2_32.dll`、`WINMM.dll`、`KERNEL32.dll` 是大写。
6. **cdb 命令文件每行一条、扁平，结尾必须有 `q`**；`r rcx rdx r8` 写成一行报 `Syntax error`。
7. **`ObRegisterCallbacks` 的裁剪是静默的**：「Open 成功 / Read 失败」不是你的 bug，是保护生效。
8. **反作弊扫描是周期性的**，「这一刻扫不到」不等于不存在。任何「单次扫描干净 → 安全」的结论都不成立。
9. **BattlEye 驱动 hash 每 2–3 天就变**。基于具体 hash 的 YARA 规则**寿命只有几天**，
   必须用行为/字符串组合，不要用具体 hash。
10. **内核驱动有强保护**（`diec` 报 VMProtect/Themida）。静态分析收效极低，
    不要在这上面耗时间——转动态。
11. **不要在生产/他人机器上修改内核代码段**，PatchGuard 会随机蓝屏（无错误码，只有 BUGCHECK）。
12. **`logman query -ets` 的输出本机未验证**。ETW 相关结论优先走静态（导入/字符串），
    动态部分标注为待验证。
13. **「延迟封禁」（Ricochet）容易被误判为「我的检测没生效」**——
    实际上是它在收数据。评估检测效果要按周计，不是按分钟。

## 相关

- `game-memory-hacking.md` — L1 handle 裁剪在内存面的具体表现
- `game-esp-wallhack-rendering.md` — L4 渲染层的完整检测清单
- `game-packet-interception.md` — L6 服务端层的观测面
- `game-speedhack-time-manipulation.md` — 时间源篡改与多源交叉校验
- `README.md` — 本目录五篇的定位与阅读顺序
- `../../reverse-engineering/references/pe-header-parsing.md` — 驱动 PE 结构分析基础
- `../../reverse-engineering/references/anti-debug-bypass.md` — ScyllaHide 四层反反调试手段
- `../../reverse-engineering/references/tls-callback-analysis.md` — 反作弊 DLL 早期初始化的观测
- `../../reverse-engineering/references/yara-rule-writing.md` — 第 7 步规则的完整写法