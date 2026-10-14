---
name: x64dbg-reverse
description: x64dbg 动态调试与 MCP 自动化：断点、单步、内存读写、反汇编、穿越反调试。用于：挂调试器即退出、抓运行期明文、下断校验点、改内存。
---

# x64dbg 动态调试技能

动态调试的**唯一入口**。它管"让它真的跑起来、并且停在你想看的地方"。
静态怎么读代码不归它；壳与反调试的**判定方法论**在 `reverse-engineering`。

## ACTION REQUIRED（读完后立刻执行）

1. `NOW`：**查经验卡** —— `python skills/scripts/experience-card.py search "<你看到的症状>"`。
2. `NOW`：**工具定位** —— 先载入探测层 `. $SK\skillpack\skills\scripts\lib\Bootstrap.ps1`，再 `Resolve-ReverseToolSpec -Name 'x64dbg'` 取 `Command`。**`Get-Command` 返回空 ≠ 缺工具**（见 `../references/env-selfcheck.md`）。
3. `ACT`：**起服务** —— `powershell -NoProfile -ExecutionPolicy Bypass -File <本技能>/scripts/start.ps1`。
   端点与依赖的事实源是 `../references/tool-registry.md` 的 `x64dbg-mcp` 行；**本文件不写死端口之外的路径**。
4. `ACT`：**先看目录再动手** —— `powershell -NoProfile -ExecutionPolicy Bypass -File ../scripts/mcp-status.ps1`，
   三列＝注册了哪些／谁在监听／怎么起。`closed` 就按它给的命令起，起完重跑确认 `LISTEN`。

## 为什么必须有这一篇

x64dbg-MCP-Server 是**活在被调试进程里的插件**，没有独立服务进程：

- x64dbg 没跑 → 9094 必然拒连 → 所有 `x64dbg_*` MCP 工具全部失败。
- **HTTP 型 MCP 平时关着是设计**，不是故障（见 `../references/tool-registry.md` §1）。
- 宿主在连不上时**只是把工具从工具表里拿掉**，不会告诉你"该起服务了" —— 所以这一步必须由你主动做。

## 工作流

| 步 | 做什么 | 关键点 |
|---|---|---|
| 1 | 起 x64dbg（9094 监听） | `scripts/start.ps1`；幂等，已在听则立即返回 0 |
| 2 | 载入目标 | 优先**让 x64dbg 自己启动目标**（插件随进程创建注入 ScyllaHide） |
| 3 | 设异常处理 | 受保护目标会**主动抛 `0xC0000005` 驱动自校验**；先把它设成 pass/ignore，否则一步一停 |
| 4 | 下断 | 校验点、解密后缓冲区读断点（硬件读断点看"谁读它"）、API 断点 |
| 5 | 读写内存 | MCP 的 `WriteMemToAddress` 对只读页**可能不落地**；进程外 `VirtualProtectEx + WriteProcessMemory`（`scripts/patchmem.py`）更可靠 |
| 6 | 收尾 | 停调试会话、关 x64dbg、复原 IFEO/代理等系统改动 |

## 已知坑（实测，不是推测）

| 坑 | 表现 | 处置 |
|---|---|---|
| **附加式调试会被反调试当场杀掉** | `AttachProcess` 后目标立刻退出 | ScyllaHide **只在进程创建时**注入；用 x64dbg 自己 LoadBinary，或用 IFEO 让 shell 启动时进入调试会话（父进程仍是 explorer） |
| **`headless.exe` 起不了 MCP** | 端口始终不监听 | 动态调试一律拉 **GUI x64dbg**（插件随进程加载，9094 才监听）；`headless` 只适合一次性批处理 |
| **9095 不是控制口** | 向 9095 发指令无应答 | 9095 是 **x32 的服务口**；x64 只有 9094 |
| **MCP 写内存"成功"但读回没变** | `WriteMemToAddress` 报 Success，`ReadMemory` 仍是原字节 | `.text` 是 RX，写不落地；改用 `scripts/patchmem.py`（进程外放开页保护再写），并用**独立于调试器的** `ReadProcessMemory` 复核 |
| **token 变了/401** | MCP 返回 401 Unauthorized | token 是**每个 x64dbg 实例自己的**，读 `release\x64\mcp_config.json` 的 `AuthToken`（宿主侧对应 `X64DBG_MCP_TOKEN`） |
| **保护器代码不在文件里** | 断点命中的地址不在任何模块范围内 | 保护器在**私有可执行区**（运行期生成/解密）；先 `GetMemoryMap` 找 RWX / R-X 私有页，再在那些页上下断 |

## 脚本

| 脚本 | 用途 |
|---|---|
| `scripts/start.ps1` | 幂等起 x64dbg（9094 监听）；已在听直接返回 |
| `scripts/xdbg.py` | x64dbg MCP 客户端（从 `mcp_config.json` 读 token；`python xdbg.py <Tool> '<json>'`） |
| `scripts/patchmem.py` | 进程外改内存（自动放开页保护），用于 `.text` 等只读页 |
| `../scripts/mcp-status.ps1` | 三列目录：注册/监听/怎么起（**要用这个通道时先看**；不做事前自检） |

## 交付要求

- 动态结论要**原子值 + 多轮稳定**：单轮命中不算；地址/偏移复核后再写进结论。
- **回显 ≠ 命中**；工具静默/超时只算"没观测到"，不算"没发生"。
- 收尾把系统改动复原（IFEO、代理、注入的 DLL、残留调试进程），并在报告里写明复原核对结果。

---

## When NOT to use（近邻负例）

- 只要静态读代码逻辑、看交叉引用、出伪代码 → `../ida-reverse/SKILL.md`（无许可 → `../ghidra-reverse/SKILL.md`、`../radare2/SKILL.md`）
- 静态结论要靠第二个独立反编译器交叉 → `../binary-ninja-reverse/SKILL.md`
- 目标是 APK（要 smali / manifest / 抓 APP 协议）→ `../apk-reverse/SKILL.md`，本卡的 Windows x32/x64 断点模型不适用
- 逻辑实际在浏览器 JS/WASM 里 → `../js-reverse/SKILL.md`
- 目标实为 .NET → `../dotnet-reverse/SKILL.md`
- 需要同时改启动参数 + 多种 hook 且目标跨桌面端 → 评估后按 `../reverse-engineering/tools-dynamic.md` 选 Frida，别硬用断点
- 壳 / 反调试的**判定方法论**在 `../reverse-engineering/`，先判定再执行；本卡不回答"这是哪种保护"
- 前置条件缺位：`scripts/start.ps1` 后 9094 仍 `closed`、`headless.exe` 起不来 MCP（本卡已知坑）→ 换 GUI x64dbg 重试；`9095` 无应答是因为它是 x32 服务口，不要反复向它发指令；401 就读 `release\x64\mcp_config.json` 的 `AuthToken`
- `AttachProcess` 后目标立刻退出 → 不要反复 attach，改让 x64dbg 自己 LoadBinary 或走 IFEO（ScyllaHide 只在进程创建时注入）

## When to Pivot

信号与判据见 `../ops/skill-pivot-contract.md`。本技能去向：

| 触发证据 | 换到 |
|---|---|
| `diec` 报 VMP/Themida/VMProtect；或断点命中地址落在**私有 RWX 区**、不在任何模块范围 | `../reverse-engineering/references/assault-entry.md` |
| 目标进程被反调试杀掉（`AttachProcess` 后立刻退出、`IsDebuggerPresent` 命中）且 ScyllaHide 不足 | `../reverse-engineering/` 反调试绕过方法论 |
| 静态断点解释不了壳/混淆，需要连续数据流 → 等 `analyzeHeadless`/伪代码口径 | `../ghidra-reverse/SKILL.md` 或 `../ida-reverse/SKILL.md` |
| 需 Frida 类非侵入 hook / 改参数不改寄存器流 | `../reverse-engineering/tools-dynamic.md` |
| `WriteMemToAddress` 上报 Success 但读回未变（`.text` 是 RX） | 用本卡 `scripts/patchmem.py`；再失败说明保护器在动校验 → `../reverse-engineering/references/assault-entry.md` |
| 目标实为 .NET / APK / 浏览器 JS | `../dotnet-reverse/SKILL.md` / `../apk-reverse/SKILL.md` / `../js-reverse/SKILL.md` |
| 已确认可利用的 crash/溢出要写利用链 | `../pwn-chain/SKILL.md` |
| 同一假设连续两轮动态读数无新证据（信号 4） | `../ops/analysis-decision-framework.md` R2/R43 |

## 定义完成

本技能产出算"完成"的**外部可观测**条件（不许写形容词）：

- 服务在听：`mcp-status.ps1` 三列显示 x64dbg-mcp 为 `LISTEN`（9094）；`GetDebugState` 返回 loaded=true
- 目标是被调试器自己启动的：`GetThreads`/`GetMemoryMap` 的镜像路径 == 目标路径（**不是** attach 结果，附件式会被反调试杀）
- 动态证据原子化：断点处值（寄存器/内存/返回缓冲）≥3 轮相同，每轮记录 `EvalExpression`/`ReadMemory` 的原始输出
- 内存改写证据：`scripts/patchmem.py` 写入后，用**独立于调试器**的 `ReadProcessMemory` 复核，前后字节组 + 原 sha256 落盘
- 可运行最小命令（自验通道仍通）：
  - `powershell -NoProfile -ExecutionPolicy Bypass -File <本技能>/scripts/start.ps1` → 退出码 0
  - `python scripts/xdbg.py GetDebugState '{}'` → 返回当前调试状态
  - `python scripts/xdbg.py SetBreakpoint '{"address":"kernel32:CreateFileA"}'` → Success
- 系统改动复原：IFEO / 代理 / 注入 DLL / 残留调试进程均已复原，并把 `reg query` / `tasklist` 的核对输出写进报告

## 输出契约

```
FACT:       <观察，带来源（命令 / 文件:行 / Evidence ID）>
HYPOTHESIS: <可测试断言 + confidence: high|medium|low>  （状态见 ../ops/binary-model.md）
QUESTION:   <当前最大不确定点>
NEXT:       <继续 | 换技能 | 停止（附成本判据）>
```

本技能填写示例：

```
FACT:       xdbg.py RunToAddress 停在 0x7FF6A2001234（E-007），ReadMemory 32B 三
            轮回显同一"key=..."明文（E-008）；GetMemoryMap 显示该页在私有 RX 区
HYPOTHESIS: H-005 明文 key 在加密前于该缓冲常驻，可由该地址读断点复现
            confidence: high，evidence_ids: [E-007, E-008]
QUESTION:   该明文是最终值还是中间轮（后续是否被二次变换）
NEXT:       换技能 → reverse-engineering 判断是否有自定义变换；否则停止
```

## 置信度词表

词表见 `../ops/confidence-vocabulary.md`。本技能特有判据：

- `confirmed`：动态读数被**静态口径印证**（断点处寄存器值与 IDA/Ghidra 反编译推导一致）且 ≥3 轮同值；或两处独立来源（如 API 断点 + 内存读断点）给出同一明文
- `high`：单轮但多通道动态证据一致（寄存器 + 内存 + 字符串），且工具 `Success` 之外有实际回显
- `low`：只有工具回显、没有**原子值**（回显 ≠ 命中，见本卡交付要求）；或目标只在被保护器操控的私有 RWX 页运行，地址不稳定
- `low`：`WriteMemToAddress` 报 Success 但未用独立 `ReadProcessMemory` 复核
- `low`：attach 方式采样时出现瞬时退出 —— 该轮采样只说明"进程死过一次"，不说明逻辑不执行
- `contextual`：token/端口/内存页地址均为**本 x64dbg 实例**属性，换实例须重新取一次

