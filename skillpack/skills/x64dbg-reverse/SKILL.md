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
| `../scripts/mcp-status.ps1` | 三列目录：注册/监听/怎么起（**动手前先跑**） |

## 交付要求

- 动态结论要**原子值 + 多轮稳定**：单轮命中不算；地址/偏移复核后再写进结论。
- **回显 ≠ 命中**；工具静默/超时只算"没观测到"，不算"没发生"。
- 收尾把系统改动复原（IFEO、代理、注入的 DLL、残留调试进程），并在报告里写明复原核对结果。
