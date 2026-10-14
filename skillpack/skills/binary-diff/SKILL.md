---
name: binary-diff
description: 二进制差分/符号迁移：旧版符号迁到新版、更新后找偏移、内核缺 PDB。用于：更新后地址变了、新版 PDB 下不到、旧版函数名迁移。
---

# 跨版本符号迁移 (Binary Diff)

## ACTION REQUIRED（读完后立刻执行）

1. `NOW`: 读 `../field-journal/precedent-reverse.md` —— 本机做过多轮的常规操作清单，直接照做，不要停在犹豫上
2. `NOW`: **查经验卡** —— `python skills/scripts/experience-card.py search "<你看到的症状>"`。
   命中就读那张卡的 `invariant` + `decision.action`，并**逐条对照** `scope.appliesWhen`
   与 `scope.stopsWhen`：少一条前提就停用；命中任一停止条件就停。
   历史卡**不替代**当前目标的实测证据。详见 `../experience-cards/INDEX.md`。
3. `NOW`: 确认当前任务是否命中本 skill 的适用范围
5. `NEXT`：**工具定位** —— 先载入探测层 `. C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1`（本机固定路径；万一这台机器还没建好、该文件不存在，改成从本文件往上两级的 `..\..\skills\scripts\lib\Bootstrap.ps1`），再 `Resolve-ReverseToolSpec -Name <id>`，按返回的 `Command` 调（完整路径，别依赖 cwd）。**`Get-Command` 返回空 ≠ 本机缺工具**（PATH 快照陷阱，见 `../references/env-selfcheck.md`）；四级探测全部 `Available=False` 才允许报缺。`../TOOLS.md` 是装法说明书，不是路径索引。禁止猜路径。
6. `NEXT`: 缺工具时调用 bootstrap，不要猜路径
7. `ACT`: 按本卡「怎么走（判据，不是流程）」挑**当下适用**的一格动手；不要停在确认状态

## 适用范围

当任务属于以下场景时使用本 skill：

1. **内核/驱动缺 PDB** — 有旧版 ntoskrnl.exe 的符号，新版 PDB 被微软下架，需要用旧版符号推导新版非导出函数地址
2. **程序更新后符号迁移** — 曾经逆向过某个程序，程序更新了，不想重新逆一遍，用旧版结果批量迁移
3. **保护机制更新** — 旧版有完整逆向结果，新版需要快速定位同一函数的新偏移
4. **任何"有旧版符号 + 新版无符号"的二进制对比场景**

### 与其他 skill 的分工

| 场景 | 用什么 |
|------|--------|
| 从零开始逆向一个二进制 | `ida-reverse/` 或 `radare2/` |
| 有旧版结果，迁移到新版 | **本 skill** |
| 两个完全不同的二进制对比 | BinDiff / Diaphora（传统工具） |

### 核心优势

相比传统方案：

| 方案 | 200 个函数成本 | 时间 | 准确率 |
|------|--------------|------|--------|
| 人工开两个 IDA 窗口对比 | 免费但耗命 | 数小时 | 高 |
| BinDiff 自动匹配 | 免费 | 快 | 中（结构变化大时失效） |
| 完全交给 Agent（CC/Codex） | 50-100 元 | 慢 | 高 |
| **本 skill（LLM 批量比对）** | **~1 元** | **~10 秒/函数** | **高** |

## 核心原理

```text
旧版函数（有符号）          新版同一函数（无符号）
    ↓                              ↓
导出反汇编 + 伪代码          导出反汇编 + 伪代码
    ↓                              ↓
    └──────── LLM 结构化比对 ────────┘
                    ↓
         输出 YAML（符号映射表）
                    ↓
         程序化解析 → 批量应用到新版 IDB
```

关键点：
- prompt 是固定模板，程序化填充
- 输入输出格式确定，程序化解析
- LLM 只负责"看两段代码，找出对应关系"这一步
- 时间成本和 token 成本极低

## Prompt 模板

### 标准比对 Prompt

```text
I have disassembly outputs and procedure code of the same function.

This is the function for reference:

**Disassembly for Reference**
```c
{disasm_for_reference}
```

**Procedure code for Reference**
```c
{procedure_for_reference}
```

This is the function you need to reverse-engineering:

**Disassembly to reverse-engineering**
```c
{disasm_code}
```

**Procedure code to reverse-engineering**
```c
{procedure}
```

What you need to do is to collect all references to "{symbol_name_list}" in the function you need to reverse-engineering and output those references as YAML.

Example:
```yaml
found_vcall: # This is for indirect call to virtual function or virtual function pointer fetching.
  - insn_va: '0x180777700' # Always be the instruction with displacement offset
    insn_disasm: call [rax+68h] # Always be the instruction with displacement offset
    vfunc_offset: '0x68'
    func_name: ILoopMode_OnLoopActivate
  - insn_va: '0x180777778' # Always be the instruction with displacement offset
    insn_disasm: mov rax, [rax+80h] # Always be the instruction with displacement offset
    vfunc_offset: '0x80'
    func_name: INetworkMessages_GetNetworkGroupCount

found_call: # This is for direct call to non-virtual regular function.
  - insn_va: '0x180888800'
    insn_disasm: call sub_180999900
    func_name: CLoopMode_RegisterEventMapInternal
  - insn_va: '0x180888880'
    insn_disasm: call sub_180555500
    func_name: CLoopMode_SetSystemState

found_funcptr: # This is for non-virtual regular function pointer.
  - insn_va: '0x180666600' # Must load/reference the function pointer target address
    insn_disasm: lea rdx, sub_15BC910 # Must load/reference the function pointer target address
    funcptr_name: CLoopMode_OnClientPollNetworking

found_gv: # This is for reference to global variable.
  - insn_va: '0x180444400'
    insn_disasm: mov rcx, cs:qword_180666600 # Must load/reference the global variable
    gv_name: g_pNetworkMessages
  - insn_va: '0x180333300'
    insn_disasm: lea rax, unk_180222200 # Must load/reference the global variable
    gv_name: s_EventManager

found_struct_offset: # This is for reference to struct offset. NOTE THAT virtual function pointer should not be here! virtual function pointer should ALWAYS be in found_vcall !
  - insn_va: '0x1801BA12A' # Always be the instruction with displacement offset
    insn_disasm: mov rcx, [r14+58h] # Always be the instruction with displacement offset
    offset: '0x58'
    size: 8
    struct_name: CResourceService
    member_name: m_pEntitySystem
```

If nothing found, output an empty YAML. DO NOT output anything other than the desired YAML. DO NOT collect unrelated symbols.
```

### 变量说明

| 变量 | 来源 | 说明 |
|------|------|------|
| `{disasm_for_reference}` | 旧版 IDA 导出 | 有符号的反汇编 |
| `{procedure_for_reference}` | 旧版 IDA 导出 | 有符号的伪代码 |
| `{disasm_code}` | 新版 IDA 导出 | 无符号的反汇编 |
| `{procedure}` | 新版 IDA 导出 | 无符号的伪代码 |
| `{symbol_name_list}` | 从旧版提取 | 需要在新版中定位的符号列表 |

## 怎么走（判据，不是流程）

先看**手上已经有什么证据**，再决定动哪一格。没有任何一条要求你按顺序做完；
任何一格的条件不成立（比如新版其实带了部分符号），直接跳到适用的那一格。

| 手上的东西 | 该做的 | 做完会得到什么（可观察） |
|---|---|---|
| 旧版有符号 + 新版无符号 | 两边都加载进 IDB；先找**两版都有的同一个锚点**（导出函数名 / 唯一字符串引用 / 已知常量） | 一对能对上的锚点地址 |
| 有锚点 | 从旧版导出锚点的反汇编 + 伪代码（**带符号名**）；从新版导出同一锚点（**无符号**） | 两份可对齐的文本 |
| 两份文本在手 | 填 prompt 模板调 LLM（大函数切分；量大的用便宜模型，超大的切贵模型） | 一份 YAML 符号映射 |
| 有映射结果 | 批量应用到新版 IDB（`idapro_rename` / IDAPython 脚本） | 新版里符号已可读 |
| 已迁移的函数 | **它们自己变成新锚点** → 进函数体内继续比对内部调用 | 覆盖率上升 |

> ⚠️ 别把它当成流程：锚点找不着就先补侦察，映射结果对不上就先查是不是拿错了版本 ——
> 判据对不上时，正确答案是**换一格**，不是硬把这一格做完。

### 锚点选择策略

| 锚点类型 | 可靠性 | 说明 |
|---------|--------|------|
| 导出函数 | 最高 | 名字不变，地址可能变 |
| 字符串引用 | 高 | 字符串内容不变，引用位置可能变 |
| 常量/魔数 | 中 | 特征值不变 |
| 代码模式 | 中 | 函数结构相似但地址全变 |

### 批量处理建议

- 每次比对 1 个函数（避免 context 爆炸）
- 中等函数（<200 行）用 deepseek
- 超大函数（>500 行）切 gpt-4o 或 claude
- 并发调用提高速度（10-20 并发）
- 结果缓存，避免重复调用

## 输出格式

### YAML 输出的 5 种符号类型

| 类型 | 含义 | 关键字段 |
|------|------|---------|
| `found_vcall` | 虚函数调用（间接 call） | `vfunc_offset`, `func_name` |
| `found_call` | 直接函数调用 | `insn_va`, `func_name` |
| `found_funcptr` | 函数指针引用 | `insn_va`, `funcptr_name` |
| `found_gv` | 全局变量引用 | `insn_va`, `gv_name` |
| `found_struct_offset` | 结构体偏移引用 | `offset`, `struct_name`, `member_name` |

### 解析后的应用动作

```text
found_call → idapro_rename(addr=call_target, name=func_name)
found_vcall → idapro_set_comments(addr=insn_va, comment="vcall: {func_name} @ +{offset}")
found_funcptr → idapro_rename(addr=funcptr_target, name=funcptr_name)
found_gv → idapro_rename(addr=gv_addr, name=gv_name)
found_struct_offset → idapro_set_comments(addr=insn_va, comment="{struct_name}.{member_name}")
```

## 典型场景示例

### 场景 1：ntoskrnl.exe 缺 PDB

```text
已有：ntoskrnl.exe 10.0.26100.2000 + 完整 PDB
目标：ntoskrnl.exe 10.0.26100.2605（PDB 被下架）
需求：定位 PspSetCreateProcessNotifyRoutine 的新地址

步骤：
1. 两个版本都加载到 IDA
2. 找到导出函数 PsSetCreateProcessNotifyRoutine（两个版本都有）
3. 旧版中它调用了 PspSetCreateProcessNotifyRoutine（有符号）
4. 新版中它调用了 sub_140822108（无符号）
5. LLM 一眼看出：sub_140822108 = PspSetCreateProcessNotifyRoutine
6. 批量应用
```

### 场景 2：应用更新后迁移

```text
已有：target.exe v1.0 的完整逆向结果（200+ 函数已命名）
目标：target.exe v1.1（所有符号丢失）
需求：批量迁移 200 个函数名

步骤：
1. 从旧版导出所有已命名函数的反汇编+伪代码
2. 在新版中通过导出函数/字符串找到对应锚点
3. 批量调用 LLM 比对
4. 解析 YAML，批量 rename
5. 迭代深入
```

## LLM 选择建议

| 模型 | 适合场景 | 成本 | 速度 |
|------|---------|------|------|
| DeepSeek V3 | 中小函数（<200 行），批量处理 | 极低 | 快 |
| GPT-4o | 超大函数，复杂控制流 | 中 | 快 |
| Claude Sonnet | 中大函数，需要推理 | 中 | 快 |
| Claude Opus | 极复杂函数，需要深度理解 | 高 | 慢 |

推荐策略：默认 DeepSeek，遇到 context 超限或结果不准时自动升级。

## 注意事项

- **不要把整个二进制丢给 LLM** — 一次只比对一个函数
- **锚点必须可靠** — 如果锚点本身就对错了，后续全部白费
- **结果需要人工抽检** — LLM 不是 100% 准确，关键符号要验证
- **缓存中间结果** — 避免重复调用浪费 token
- **注意 context 限制** — 超大函数（>1000 行反汇编）需要拆分或用大 context 模型

---

## 按需自举（On-Demand Bootstrap）

> 缺工具时只生成安装计划，获用户显式批准后才安装；不得自动安装或自动联网（`autoInstall=false`）。

### 工具依赖

| 工具 | 用途 | 批准后可安装 |
|------|------|-----------|
| IDA Pro | 导出反汇编/伪代码 | ✗（商业软件） |
| Python | 脚本执行、API 调用 | ✓ |
| PyYAML | 解析 LLM 返回的 YAML | ✓（pip install pyyaml） |
| LLM API | 执行比对 | 需要 API key |

### 说明

本 skill 的核心不依赖重型工具安装，主要依赖：
- IDA Pro 已有（用 `ida-reverse/` skill 管理）
- Python + requests/httpx（调 API）
- 一个 LLM API endpoint

---

## 路由上下文

**上游入口**: `SKILL.md`（总控）、`../routing.md`
**触发条件**: 有旧版符号/逆向结果，需要迁移到新版本
**下游出口**:
- 需要先打开二进制 → `ida-reverse/`
- 需要快速侦察确认版本差异 → `radare2/`

**同级关联模块**: `ida-reverse/`（数据导出和符号应用都通过 IDA）

## 任务完成自检（声称完成前 MUST 通过）

- [ ] 我是否执行了工作流中的每一步（而不是只阅读）？
- [ ] 我是否走了**探测层四级递进**（`Resolve-ReverseToolSpec`）定位实际路径（而不是只跑一条 `Get-Command` 查空就报缺工具、也不是拿 `../TOOLS.md` 里的装法当路径猜）？
- [ ] 我是否产出了可复现证据（命令/脚本/截图/报告）？
- [ ] 我是否完成并回写了 RULES 要求的 Checklist 项？

---

## 工具与通道（本机口径）

> 动手前先定位工具与通道：`. <仓根>\skillpack\skills\scripts\lib\Bootstrap.ps1` 之后 `Resolve-ReverseToolSpec -Name <id>`（返回的 `Command` 是完整路径，别依赖 cwd）；
> 通道用 `powershell -NoProfile -ExecutionPolicy Bypass -File skillpack\skills\scripts\mcp-status.ps1` 看三列（注册了哪些 / 谁在监听 / 怎么起）。**注册 ≠ 在监听**。

| 环节 | 工具与调用口径 |
|---|---|
| 认两个版本 | `diec -d -e -j <bin>` 判编译器与版本；`rabin2 -I` 核导入表是不是同一套 |
| 导符号与伪代码 | `idat -A <bin>` 批处理；`analyzeHeadless.bat <proj> t -import <bin>` 出 Ghidra 工程；`radare2 -A -q -c 'afl'` 快速函数表 |
| 传统差分做对照 | `bindiff`、`diaphora.py`（IDA 内，SQLite）、`ghidriff <a> <b>`、`radiff2 -C <a> <b>` —— 结构变化大时它们先失效，这时才轮到本卡的 LLM 逐函数比对 |
| Go/Rust 自身的元数据 | `GoReSym` 恢复函数名（Go 的 .gopclntab）；Rust 靠 panic 字符串定位 |
| 把结果写回 IDB | `idapro` MCP（`127.0.0.1:13337`，用前 `ida-reverse/scripts/start.ps1`），或 IDA 内的 `idat` 脚本 |

## When NOT to use（近邻负例）

- 要的是从补丁差异反推漏洞并写利用，不只是迁符号 → 用 `../patch-diff-exploit/SKILL.md`
- 只有单个版本，没有对照对象 → 用 `../reverse-engineering/SKILL.md`
- 目标是 .NET 程序，符号在托管元数据里更直接 → 用 `../dotnet-reverse/SKILL.md`
- 目标是 APK / DEX 字节码 → 用 `../apk-reverse/SKILL.md`
- 目标是 macOS Mach-O（符号表/OC 元数据处理不同）→ 用 `../macos-reverse/SKILL.md`
- 目标是 Go/Rust，自身元数据能直接恢复函数名、不必逐函数比对 → 用 `../go-rust-reverse/SKILL.md`
- 工程前置（不是许可）：两个二进制需同源（否则符号匹配无意义）—— 先验 `.text` 相似度

## When to Pivot

信号与判据见 `../ops/skill-pivot-contract.md`。本技能去向：

| 触发证据 | 换到 |
|---|---|
| 同名函数的调用图里出现旧版没有的新增子函数，疑似安全修复 | `../patch-diff-exploit/SKILL.md` |
| 目标版本的符号被剥离，节区里已找不到 pclntab / 导出表 | `../ida-reverse/SKILL.md`，无 IDA 走 `../ghidra-reverse/SKILL.md` |
| 目标是 Go，函数名可在 .gopclntab / moduledata 自恢复（Go 版本自带） | `../go-rust-reverse/SKILL.md` |
| 同一函数两轮 LLM 比对仍对不上（一方被内联、一方拆成 sub_） | 换匹配面：改用数据引用 / 字符串交叉，而不是函数签名 |
| 两个版本 `.text` 相似度 <0.5、导出表几乎为空 | 换对照对象（重取同编译器版本），别硬迁 |
| 迁移结论要写进交付，但只有单一特征支持（仅字节相似） | 回 `../ida-reverse/SKILL.md` 抽样交叉验证 |

## 定义完成

本技能产出算「完成」的**外部可观测**条件（不许写形容词）：

- 匹配结果表落盘（旧地址 → 新地址 → 置信度）
- 未匹配项单独列出并说明原因
- 在目标版本上验证：迁移后的符号指向的函数与预期一致（抽样 ≥3 个）
- **每条 `confirmed` 映射至少要有 2 条相互独立的证据**（调用图 + 字符串/常量/结构体偏移）；只靠字节相似度或单轮 LLM 输出一律标 `low`
- 未匹配项不许硬凑：要么写清原因（内联 / 函数拆分 / 新增），要么留白，不许塞一个「看着像」的名字

## 输出契约

```
FACT:       <观察，带来源：命令 / 文件:行 / Evidence ID>
HYPOTHESIS: <可测试断言 + confidence: high|medium|low>（状态见 `../ops/binary-model.md`）
QUESTION:   <当前最大不确定点>
NEXT:       <继续 | 换技能 | 停止（附成本判据）>
```

## 置信度词表

词表见 `../ops/confidence-vocabulary.md`。本技能特有判据：

- `confirmed`：匹配有多特征交叉（调用图 + 字符串 + 常量），且抽样验证通过
- `low`：仅凭字节相似度匹配
