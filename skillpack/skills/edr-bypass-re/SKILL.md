---
name: edr-bypass-re
description: 红队 EDR 绕过：unhook、direct syscall、AMSI/ETW 绕过、反射加载 implant。用于：Defender 老杀我马、unhook 过 EDR、AMSI/ETW 怎么处理。
---

## ACTION REQUIRED（读完后立刻执行）

1. `NOW`: 读 `../field-journal/precedent-reverse.md` —— 本机做过多轮的常规操作清单，直接照做，不要停在犹豫上
2. `NOW`: **查经验卡** —— `python skills/scripts/experience-card.py search "<你看到的症状>"`。
   命中就读那张卡的 `invariant` + `decision.action`，并**逐条对照** `scope.appliesWhen`
   与 `scope.stopsWhen`：少一条前提就停用；命中任一停止条件就停。
   历史卡**不替代**当前目标的实测证据。详见 `../experience-cards/INDEX.md`。
3. `NOW`: 确认当前任务是否命中本 skill 的适用范围
5. `NEXT`：**工具定位** —— 先载入探测层 `. C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1`（本机固定路径；万一这台机器还没建好、该文件不存在，改成从本文件往上两级的 `..\..\skills\scripts\lib\Bootstrap.ps1`），再 `Resolve-ReverseToolSpec -Name <id>`，按返回的 `Command` 调（完整路径，别依赖 cwd）。**`Get-Command` 返回空 ≠ 本机缺工具**（PATH 快照陷阱，见 `../references/env-selfcheck.md`）；四级探测全部 `Available=False` 才允许报缺。`../TOOLS.md` 是装法说明书，不是路径索引。禁止猜路径。
6. `NEXT`: 缺工具时调用 bootstrap，不要猜路径
7. `ACT`: 按本卡的「工作流」挑**当下适用**的那一条动手；不要停在确认状态

# EDR 绕过：从防御方实现逆向到红队绕过

> 运行边界：本地 / 隔离 lab / 自有资产 —— 按项目 `scope.md` 直接执行。

## 适用范围

红队 / 对抗模拟向目标主机投递 implant 并躲避现代 EDR 时使用本 skill。

1. **红队 / Purple team / 对抗演练** — 客户希望评估 SOC 与 EDR 的真实检测能力
2. **自研 implant / C2 框架研发** — 开发针对自家产品测试的载荷，需要绕过自家或目标 EDR
3. **EDR 产品评估** — 客观评测某款 EDR 的检测覆盖
4. **CTF / 攻防演练的 Windows 端突破** — 比赛中需要在加固主机上稳定执行

**不适用场景**：

- 杀毒厂商对自家产品做完整 RE 给客户出商业评估报告（找厂商正式合作）
- 对生产环境 / 第三方系统**实际投放**（本卡只做本地 / 隔离 lab 研究）
- 普通病毒木马的免杀（本 skill 关注红队 OPSEC，不教恶意代码写法）

### 与其他 skill 的分工

| 场景 | 用什么 |
|------|--------|
| 全链路攻防（从外网打到域控） | `attack-chain/` |
| 内网横向 / AD 攻击 | `../pentest-tools/references/network-attack-defense.md` |
| 在某个特定主机上要过 EDR 投递 implant | **本 skill** |
| 单纯静态免杀（混淆 / 加壳） | `malware-analysis/`（反向视角） |

`attack-chain` 关注完整 kill chain，本 skill 只聚焦 **EDR 这一个对手** 的内部机制和针对性绕法。

## 核心原理

```text
EDR 的四个主要监控面               红队的对策
─────────────────────              ─────────────────────
用户态 ntdll hook       ◄──►   unhook (Peruns Fart / fresh ntdll)
                                  间接 syscall / Hell's Gate
                                  hardware breakpoint Blindside

kernel callback         ◄──►   call stack spoof
(Ps/Cm/Ob 系列)                   走合法触发链（不直接绕，配合上游隐身）

ETW telemetry           ◄──►   EtwEventWrite patch
(Microsoft-Windows-Threat-          NtTraceControl 关 provider
 Intelligence 等)                  AmsiContext 同步处理

AMSI 扫描               ◄──►   AmsiScanBuffer patch (mov eax,0x80070057; ret)
(amsi.dll)                       hardware breakpoint 旁路
                                  reflective 加载副本 amsi.dll
```

关键认知：

- **EDR 不是黑盒** — 关键 hook / callback / provider 都能用 IDA + windbg 逆出来
- **绕过技术要组合使用** — 单独一个 unhook 解决不了 ETW 告警，单独 AMSI patch 解决不了 syscall hook
- **顺序很重要** — 先 ETW patch → 再 AMSI patch → 再 unhook；顺序错了 EDR 先收到 unhook 告警
- **现代 EDR 已经把 ETW + kernel callback 当主战场**，单纯用户态 unhook 早已不够

## 判据与手法（**不是任务流程**）

> ★ **下面四节的编号只是分组，不是执行顺序。** 真实动手时按**当前证据**选一条做，
> 拿到新证据就换（见 `../ops/skill-pivot-contract.md`）。固化顺序会让模型在本不该
> 走这一步的时候硬走 —— 那正是本项目要避免的。

### 识别目标主机的 EDR

```powershell
# 列出常见 EDR / AV 驱动
Get-Service | Where-Object {$_.Name -match 'CSAgent|SentinelAgent|elasticendpoint|esets|ekrn|MsMpEng|wdsvc|cyserver|sysmon|aswbidsagent'}

# 列出加载的 minifilter
fltmc filters

# 列出已注册的内核 callback（需 windbg + 内核调试 / 或用 PChunter / DRVHV）
# !object \Callback
# !pnpcallback / Process / Thread / Image
```

EDR 指纹表见 `references/hook-survey.md` 顶部。

### 从 EDR DLL 提 hook 表

1. attach 到一个被注入 EDR 用户态组件的进程（任何已落地进程）
2. 在 windbg 中 dump 当前 `ntdll.dll` 的 `.text` 段
3. 与磁盘上干净的 `C:\Windows\System32\ntdll.dll` 做 diff
4. 不一致的地方就是 hook 点

或者直接用 `pe-sieve`：

```powershell
pe-sieve64.exe /pid 1234 /shellc 3 /modules 3 /dir hooks_dump
```

详细方法见 `references/hook-survey.md`。

### 选绕过技术组合（按 hook 表与检测面选，不是按顺序）

| 防御点 | 推荐绕法 |
|--------|---------|
| ntdll inline hook | indirect syscall + 动态 SSN (Halo's Gate) |
| ETW-TI provider | EtwEventWrite head patch |
| AMSI（PowerShell / .NET） | AmsiScanBuffer patch 或 HWBP |
| kernel callback | call stack spoof + 走 legit gadget |
| Sysmon ProcessCreate | PPID spoof + unbacked memory |

### 在 implant 中实现

代码骨架见 `references/unhook-techniques.md` 与 `references/telemetry-blinding.md`。

### 验证：在本地隔离环境里过一遍（信号：implant 已经能在测试机上跑起来）

```powershell
# 在隔离环境部署目标 EDR 试用版（Defender 默认即可起步）
# 启用 Sysmon + olaf-config
sysmon64.exe -i sysmonconfig.xml

# 跑 implant，看是否触发以下告警源：
#   - Defender AMSI
#   - ETW-TI
#   - Sysmon Event ID 1/7/8/10
#   - EDR 控制台
```

### 投递形态（信号：本地不告警了，才轮到想怎么落地）

- 文件落地路径用合法软件目录
- PPID spoof 到 explorer.exe
- 配合 `attack-chain` 中的 initial access 节

## 典型场景

### 场景 1：投递 cobalt-strike-alike beacon 过 Defender + Sysmon

```text
目标：Windows 11 Enterprise + Defender (云查杀开) + Sysmon (olaf 配置)
要求：beacon 落地后能 callback 且不触发任何告警

组合拳：
  1. shellcode 加密存储，运行时解密
  2. AMSI patch（如果走 PowerShell 投递）
  3. EtwEventWrite patch（消 ETW-TI）
  4. 间接 syscall + Halo's Gate（消 ntdll hook 告警）
  5. PPID spoof 到 explorer.exe
  6. sleep 阶段用 Ekko / Foliage 加密自身内存
```

### 场景 2：在已落地的低权限 shell 上做 EDR sleep mask

```text
前置：已经通过 phishing 拿到 medium IL shell，EDR 正在监控
风险：长时间驻留容易被内存扫描发现 beacon 特征

解法：
  1. 不再申请新 RWX 内存
  2. sleep 期间用 Ekko：
       - WaitForSingleObjectEx + CreateTimerQueueTimer
       - 在定时器里加密自身 .text + 把堆栈刷成全 0
  3. wake 时用 ROP 还原
  4. 配合 call stack spoof 让 RtlCaptureStackBackTrace 看不到信标地址
```

## 按需自举（On-Demand Bootstrap）

> 缺工具时只生成安装计划，获用户显式批准后才安装；不得自动安装或自动联网（`autoInstall=false`）。

### 工具依赖

| 工具 | 用途 | 批准后可安装 |
|------|------|-----------|
| pe-sieve | 检测进程中的 hook / 注入 | ✓ |
| API Monitor v2 | 动态观察 API 调用与 hook | 半自动（手动下载） |
| SysWhispers3 | 生成直接 / 间接 syscall stub | ✓（git clone + python） |
| Hell's Gate POC | 动态 SSN 解析参考实现 | ✓（git clone） |
| windbg + IDA | 静态逆 EDR DLL / 内核 callback | ✗（自己装） |
| Sysmon + olaf config | 本地验证环境 | ✓ |

### 自举命令（计划模板：须先披露副作用并获用户显式批准后才执行）

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "&lt;SKILL_ROOT&gt;\skills\scripts\bootstrap-reverse.ps1" -Capability @('pe-sieve','syswhispers3','sysmon') -StartServices
```

## 路由上下文

**上游入口**：

- `reverse-engineering/` — 需要先理解 EDR DLL / 驱动的实现
- `attack-chain/` — 决定在 kill chain 的哪个阶段引入本 skill

**同级关联**：

- `../pentest-tools/references/network-attack-defense.md` — 内网横向时如何与本 skill 联动
- `malware-analysis/` — 反向视角，看检测方怎么写规则
- `field-journal/` — 每次实战后回写经验

**下游交付**：

- 生成报告时引用 MITRE ATT&CK **T1562 (Impair Defenses)**、T1562.001 (Disable or Modify Tools)、T1562.006 (Indicator Blocking)、T1055 (Process Injection)、T1027 (Obfuscated Files or Information)

## 投放纪律（技术）

- 演练投放前先把回滚手段备好（快照 / 卸载脚本 / 隔离网段），被查杀时能一键收场
- 生产环境投放前先拿到该环境的 EDR 日志导出与蓝队联系方式 —— 这是给「被查杀后怎么办」留证据，不是请求许可
- 拿不到 EDR 控制台时，用本机 Defender 的 `Get-MpThreatDetection` / 事件日志侧证命中与拦截
- 所有报告中真实目标信息脱敏（IP / 主机名 / 域名 / 凭证占位）

## 参考资料

- 详细 hook 调研：`references/hook-survey.md`
- unhook / syscall 技术：`references/unhook-techniques.md`
- ETW / AMSI / 反取证：`references/telemetry-blinding.md`
- MITRE ATT&CK T1562：<https://attack.mitre.org/techniques/T1562/>

## 任务完成自检（声称完成前 MUST 通过）

- [ ] 我是否执行了工作流中的每一步（而不是只阅读）？
- [ ] 我是否走了**探测层四级递进**（`Resolve-ReverseToolSpec`）定位实际路径（而不是只跑一条 `Get-Command` 查空就报缺工具、也不是拿 `../TOOLS.md` 里的装法当路径猜）？
- [ ] 我是否产出了可复现证据（命令/脚本/截图/报告）？
- [ ] 我是否完成并回写了 RULES 要求的 Checklist 项？

---

## 工具与通道（本机口径）

> 动手前先定位工具与通道：`. <仓根>\skillpack\skills\scripts\lib\Bootstrap.ps1` 之后 `Resolve-ReverseToolSpec -Name <id>`（返回的 `Command` 是完整路径）；
> 通道用 `powershell -NoProfile -ExecutionPolicy Bypass -File skillpack\skills\scripts\mcp-status.ps1` 看三列（注册了哪些 / 谁在监听 / 怎么起）。
> **注册 ≠ 在监听** —— `x64dbg-mcp` 是活在被调试进程里的插件，进程不在端口就不在；要动态调试就先起，起完重跑确认 `LISTEN`（`9095` 是 x32 的服务口，别向它发控制指令）。

| 环节 | 工具与调用口径 |
|---|---|
| 首轮甄别载荷 | `diec -d -e -j <file>` 查壳/编译器/熵；`capa <file>` 看加密/注入/网络能力分支 |
| 扫 hook 与注入 | `pe-sieve64.exe /pid <pid> /shellc 3 /modules 3 /dir hooks_dump`；输出里的私有 RWX 页是重点 |
| 动态断点逆 hook | `x64dbg` + `x64dbg-mcp`（x64 在 `127.0.0.1:9094`；`headless.exe` 起不了 MCP，一律拉 GUI） |
| 静态逆 EDR 组件 | `idat -A`、`analyzeHeadless.bat <proj> t -import <dll>`、`radare2 -A` / `rabin2 -I` |
| 崩溃与内存取证 | WinDbg `cdb -z <dump>`；`procdump` 抓内存；内存取证 `Volatility` |
| 检测侧对照 | `yara <rule.yar> <file>`（不吃目录，整库靠 `*_index.yar`）、`sigma` 规则；本机 Defender 用 `Get-MpThreatDetection` + 事件日志侧证命中与拦截 |

## When NOT to use（近邻负例）

- 只是要分析样本行为、不涉及交付躲避 → 用 `../malware-analysis/SKILL.md`
- 目标是 Linux 主机上的规避（内核面才是主战场）→ 用 `../kernel-exploit/SKILL.md`
- 目标机根本没有 EDR/AV 驻守，常规投递即可 → 用 `../pentest-tools/SKILL.md`
- 要打的是完整 kill chain，单机规避只是一环 → 用 `../attack-chain/SKILL.md`
- 端点是 macOS 的 EndpointSecurity/EDR 组件 → 用 `../macos-reverse/SKILL.md`
- 检测面其实在浏览器 JS/WASM 里（绕过点在客户端脚本而非主机）→ 用 `../js-reverse/SKILL.md`
- 工程前置（不是许可）：载荷投递前先把回滚手段备好（快照 / 卸载脚本 / 隔离网段），EDR 拦下来是常态

## When to Pivot

信号与判据见 `../ops/skill-pivot-contract.md`。本技能去向：

| 触发证据 | 换到 |
|---|---|
| 载荷落地即被 Defender 静态报毒（`Get-MpThreatDetection` 有记录、`diec` 报已知壳或熵异常） | `../reverse-engineering/SKILL.md` 定位特征落点 |
| 要反推 EDR 用户态 hook 的字节改写（活进程 `.text` 与磁盘副本对不上） | `../x64dbg-reverse/SKILL.md` 下断点比对 |
| `pe-sieve` 输出里出现私有 RWX 页或注入模块（内存扫描命中） | `../malware-analysis/SKILL.md` 做内存取证与 IOC |
| 同一条绕过链两次实测仍被拦，事件日志里同一签名再次命中 | 换通道（direct syscall → 回调 / 间接调用），并在报告写证据 |
| 绕过在 ≥2 个 EDR 产品上表现不一致（一家拦一家放） | `../malware-analysis/SKILL.md` 从检测规则侧反查 |
| 已落地且日志出现多条告警，任务转入横向 | `../attack-chain/SKILL.md` |
| 目标主机没有 EDR/AV 驻守，无需对抗 | `../pentest-tools/SKILL.md` |

## 定义完成

本技能产出算「完成」的**外部可观测**条件（不许写形容词）：

- 载荷在目标环境 **≥3 轮**投放成功（不是一次偶然）
- 记录具体绕过项（unhook/直接系统调用/AMSI/ETW）与对应证据
- 检测侧对照：给出该载荷的检测规则（Sigma/YARA）并验证可触发
- **睡眠期内存状态要有读数**：`pe-sieve` 扫描该进程输出里不再出现私有 RWX 页/注入模块，才算 sleep mask 成立；有命中就不算
- **每条绕过链要有反证**：写清"哪条检测规则从命中变为不命中"（或反之），只凭"没报错"不算过

## 输出契约

```
FACT:       <观察，带来源：命令 / 文件:行 / Evidence ID>
HYPOTHESIS: <可测试断言 + confidence: high|medium|low>（状态见 `../ops/binary-model.md`）
QUESTION:   <当前最大不确定点>
NEXT:       <继续 | 换技能 | 停止（附成本判据）>
```

## 置信度词表

词表见 `../ops/confidence-vocabulary.md`。本技能特有判据：

- `confirmed`：多轮投放稳定且检测侧规则能命中（攻防都有证据）
- `low`：单轮成功，未确认是否为白名单放行
