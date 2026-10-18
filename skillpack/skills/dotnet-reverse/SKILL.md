---
name: dotnet-reverse
description: .NET/C# 托管程序逆向：dnSpy/ILSpy 反编译、de4dot 脱 ConfuserEx 混淆、IL patch 改判断。用于：C# 能反编译吗、ConfuserEx 怎么脱、dnSpy 怎么改判断。
license: MIT
compatibility: Requires a filesystem-based code agent or CLI with shell access, Windows host preferred (dnSpyEx 是 Windows GUI)；Linux/macOS 可用 ILSpy/de4dot CLI + mono/dotnet runtime。
allowed-tools: Bash Read Write Edit Glob Grep Task WebFetch WebSearch
metadata:
  user-invocable: "false"
---

# .NET / C# 逆向作业规范

## ACTION REQUIRED（读完立刻执行）

1. `NOW`: **查经验卡** —— `python skillpack/skills/scripts/experience-card.py search "<你看到的症状>"`。
   命中就读那张卡的 `invariant` + `decision.action`，并**逐条对照** `scope.appliesWhen`
   与 `scope.stopsWhen`：少一条前提就停用；命中任一停止条件就停。
   历史卡**不替代**当前目标的实测证据。详见 `../experience-cards/INDEX.md`。
2. `NOW`: 用 DIE/`file`/CLR 头确认目标是 .NET 托管（否则 SWITCH 到 `ida-reverse/` / `reverse-engineering/`）
3. `NOW`: 若疑似混淆 → 先 `de4dot` 脱壳，产出 `*-clean.exe`，保留原始样本
4. `NEXT`: dnSpyEx（或 dnSpy MCP / `ilspycmd`）静态：C# 浏览 + **IL 视图**看关键判断
5. `ACT`: 需要明文/C2 时动态调试；需要改逻辑时 **IL patch** 优先于 C# 重编译
6. 阶段结束给用户 3–6 项下一步菜单（含导出报告）

## 适用范围

当任务属于以下场景时优先使用本 skill：

- 识别并逆向 .NET / C# 编译产物（托管 PE / .exe / .dll）
- 分析红队 Sharp* 工具链（Rubeus、SharpHound、SharpShell 等）
- 脱混淆 ConfuserEx / SmartAssembly / Babel / Eazfuscator / .NET Reactor 等壳
- 逆向 .NET loader / info-stealer / RAT 的解密与 C2 逻辑
- 对 C# 程序做 patch（改判断、改常量、keygen）
- 分析 IL2CPP 之前的 Mono/Unity 托管层（注意：IL2CPP 编译后是 native，走 `reverse-engineering/` + seed-014）

如果目标是纯 native 二进制（C/C++/Go/Rust 编译、无 CLR），请改用 `reverse-engineering/`、`ida-reverse/` 或 `radare2/`。

## 核心原则

- **先识别再下手**：先确认是 .NET 托管程序（PE 头 CLR + `#~` / `#Strings` 流 + mscoree `_CorExeMain`），再决定走 dnSpy 而非 IDA
- **IL 优先于 C#**：dnSpyEx 的 C# 反编译器会丢失/扭曲信息（编译器生成的状态机、async/await、yield），关键判断与 patch 必须切到 **IL 编辑器**，C# 视图只用于快速浏览
- **de4dot 先行**：遇到混淆器先 `de4dot` 脱一轮再做静态分析，否则字符串/控制流全是乱的
- **MCP 联动**：环境里若注册了 dnSpy MCP（`dnspy_*` 工具），优先走 MCP 面做 decompile / IL inspection，避免来回切 GUI
- **证据化输出**：脱混淆产物、提取的配置/C2/key、patch diff 都要落盘

## 工具链映射

| 能力 | 首选 | 备注 |
|------|------|------|
| 智能体无头反编译 | **ilspycmd** | 首选无头反编译（需先设 `$env:DOTNET_ROOT`：用 `(Get-Command dotnet -ErrorAction SilentlyContinue).Source` 探测，取其所在目录），输出可直接 grep/read |
| 智能体 IL 检查 | **dnSpy.Console** | CLI 检查 IL 与方法元数据；**禁止带 `-o` 参数**，必须用 `--md <token>` |
| 字符串与混淆提取 | **FLOSS** | `floss.exe --language dotnet target.exe`，支持 .NET 字符串解码 |
| 脱混淆 | **de4dot** | ConfuserEx 全家桶、SmartAssembly 等主流壳的默认解 |
| 混淆器识别 | **Detect It Easy (diec)** | CLI 检测壳类型与 CLR 特征，避免启动 GUI 版 |
| 编程化操作 IL | **dnlib** | 写 C# 脚本批量改 metadata / 字符串解密器 |
| 人工交互观察 | **dnSpyEx GUI** | 仅供人工在桌面侧交互观察，**严格禁止经 bash 自动化拉起** |

> 前置：Windows 主机装 dnSpyEx + de4dot（choco 或 release）；Linux/macOS 用 `ilspycmd` + `dotnet runtime`。详见 `references/sharp-tools.md` 的安装矩阵。

## 六阶段工作流

### 1. Identify（识别 .NET）

确认目标是托管程序，别把 native PE 当 .NET 分析：

```powershell
# Windows
file target.exe                       # "PE32 executable ... for MS Windows" 不够
# 关键：看有没有 CLR
powershell -c "[System.Reflection.AssemblyName]::GetAssemblyName('target.exe')"
# 或
dnSpyEx 直接拖进去 —— 能打开就是托管

# 通用
strings target.exe | grep -iE "mscoree|_CorExeMain|mscorlib|System\\."
```

**.NET 识别标志：**
- PE 头 `Data Directory[14]` (CLR Runtime Header) 非零
- `mscoree.dll` 导入 / `_CorExeMain` 入口
- `#~`、`#Strings`、`#US`、`#GUID`、`#Blob` metadata 流
- `mscorlib` / `System.Private.CoreLib` 字符串

**NativeAOT 例外：** 编译成 native，没有 CLR 头，但有 `System.Private.CoreLib` 字符串和重构过的类型元数据 —— 这类走 `reverse-engineering/`（IDA/r2），本 skill 仅做识别提示。

### 2. Detect（检测混淆器）

```powershell
# DIE 快速识别
diec target.exe                        # Detect It Easy CLI
# 或拖进 dnSpyEx，看是否大量乱码类名 / 控制流变形
```

常见混淆器 → 脱壳策略（详见 `references/obfuscators.md`）：

| 混淆器 | 特征 | de4dot 处理 |
|--------|------|------------|
| ConfuserEx (1.0.0 / 2.x) | `<module>` anti-tamper、控制流变形、字符串加密 | `de4dot target.exe` 通常自动识别 |
| SmartAssembly | `circular`/`string encoding`、资源压缩 | `de4dot target.exe` |
| Babel.NET | 方法体加密、控制流 | `de4dot target.exe` |
| Eazfuscator.NET | 字符串/资源加密 | `de4dot`，部分版本需手动 |
| .NET Reactor | anti-tamper + necrobit | `de4dot`，新版可能失败需手动 |

### 3. Deobfuscate（脱混淆）

```powershell
# de4dot 默认自动识别大多数壳
de4dot target.exe -o target-clean.exe

# 指定类型（自动识别失败时）
de4dot --type cfze target.exe          # ConfuserEx
de4dot --type sa target.exe            # SmartAssembly

# 多层混淆 / de4dot 报 unknown
de4dot --detect target.exe             # 看它识别成什么
# 可能要先 patch anti-tamper 再 de4dot（见 references/obfuscators.md）
```

产出：`target-clean.exe`，后续分析用它。**保留原始样本**做对照。

### 4. Static Analyze（无头 CLI 与静态分析）

**智能体优先使用无头 CLI 分析，避免 GUI 阻塞：**

1. **提取 .NET 专用字符串（FLOSS）**：
   ```powershell
   floss --language dotnet target-clean.exe | grep -iE "flag|password|key|token|c2"
   ```

2. **完整工程反编译（ilspycmd 首选）**：
   ```powershell
   # DOTNET_ROOT 靠探测，不写死：resolve dotnet -> path -> 取所在目录
   $dotnetExe = (Get-Command dotnet -ErrorAction SilentlyContinue).Source
   $env:DOTNET_ROOT = Split-Path -Parent $dotnetExe
   ilspycmd target-clean.exe -p -o ./decompiled_src/
   ```
   反编译后直接使用 `grep` / `read` 工具在 `decompiled_src/` 源码树中定位关键校验。

3. **单个方法 IL 字节码检查（dnSpy.Console）**：
   **避坑铁律**：`dnSpy.Console` 在 IL 模式下不支持 `-o`（创建工程目录参数），带 `-o` 会直接抛错。必须使用 `--md <token>` 输出到标准输出：
   ```powershell
   # 提取指定 Metadata Token 的方法 IL
   dnSpy.Console.exe target-clean.exe --il --md 0x06000001
   ```

4. **复杂界面人工审查（dnSpyEx GUI）**：
   若需人工观察控件事件或复杂类型流，由用户在桌面端手动启动 `dnSpy.exe`，禁止由智能体经 bash 同步拉起。

### 5. Dynamic（动态调试）

dnSpyEx 调试器：附加进程 / 启动调试，在关键方法下断点，观察运行时：
- 解密后的明文字符串（很多混淆器的字符串在运行时才解密）
- C2 地址、配置解密结果
- 异常驱动的控制流（anti-debug 常用 `try/catch` 隐藏真实路径）

> .NET 动态调试比 native 友好得多 —— 能直接看到对象值、字符串内容。优先动态而非死磕静态。

### 6. Patch（按需修改）

```text
dnSpyEx → 右键方法 → Edit Method (C#) 或 Edit IL
  - 改判断：ldc.i4.0 → ldc.i4.1（false→true）
  - 改常量：直接编辑字符串/数字
  - 删除校验：nop 掉整段
File → Save Module → 替换原文件
```

**IL patch 可靠性 > C# patch**：C# 重编译可能失败（缺引用、语法不对），IL 编辑几乎不会失真。详见 `references/common-workflow.md`。

## 触发场景路由

用户说这些时进入本 skill：
- ".NET / C# 二进制逆向" / "C# 程序反编译"
- "dnSpy 分析" / "dnSpyEx patch"
- "ConfuserEx / SmartAssembly / Babel 脱混淆 / 脱壳"
- "Sharp* 工具分析"（Rubeus / SharpHound / SharpShell）
- ".NET malware / loader / info-stealer 逆向"
- "C# 程序 patch / keygen / 修改判断"

## 何时切出

- IL2CPP 编译的 Unity 游戏 → `reverse-engineering/` + `../field-journal/seed-014_unity-il2cpp-reverse.md`（IL2CPP 是 native，不走 dnSpy）
- NativeAOT 产物 → `reverse-engineering/`（同上，native）
- 纯 native PE（无 CLR）→ `reverse-engineering/` / `ida-reverse/`
- 需要符号/函数批量迁移到别的版本 → `binary-diff/`
- 需要画攻击路径 / 调用链图 → `diagram-generator/`

## 路由上下文

**上游入口**: `SKILL.md`（总控）、`../routing.md`
**下游出口**:
- IL2CPP / NativeAOT（native）→ `reverse-engineering/`
- 深度 native .so/.dll 段分析 → `ida-reverse/` / `radare2/`
- 需要 AI 直接操作 dnSpy → 注册并联动 dnSpy MCP（见 `references/sharp-tools.md`）

**同级关联模块**:
- `../reverse-engineering/languages-compiled.md`（.NET 简介指向本模块）
- `apk-reverse/`（Xamarin/MAUI Android 逆向可切回本模块看 C# 层）

## 参考文档

- [references/obfuscators.md](references/obfuscators.md) — ConfuserEx / SmartAssembly / Babel / Eazfuscator / .NET Reactor 脱混淆详解 + anti-tamper 绕过
- [references/common-workflow.md](references/common-workflow.md) — 完整工作流、IL patch 可靠性、字符串解密器提取、状态机识别
- [references/sharp-tools.md](references/sharp-tools.md) — 红队 Sharp* 工具分析、工具安装矩阵、dnSpy MCP 集成、社区资源索引

## 任务完成自检

- [ ] 是否确认过 CLR / 托管身份（或已 SWITCH 出本 skill）？
- [ ] 混淆样本是否先 de4dot / 等价脱壳再深分析？
- [ ] 关键逻辑是否用 IL 视图验证（而非只看 C# 伪代码）？
- [ ] 产物（clean 样本 / 配置 / patch diff）是否落盘且可复现？
- [ ] 是否提供了下一步菜单或报告出口？

---

## When NOT to use（近邻负例）

- 目标是纯 native PE/ELF（无 CLR 头、无 metadata 流）→ `../reverse-engineering/references/assault-entry.md`、`../ida-reverse/`、`../radare2/`
- IL2CPP 编译后的 Unity 游戏（`global-metadata.dat` + `libil2cpp.so`，已是 native）→ `../game-reverse/` + `../field-journal/seed-014_unity-il2cpp-reverse.md`，dnSpy 打不开它
- NativeAOT 产物（无 CLR 头，但有 `System.Private.CoreLib` 字符串）→ `../reverse-engineering/`，本 skill 只做识别提示
- 目标是 APK 里的 Xamarin/MAUI 托管 dll → 先 `../apk-reverse/SKILL.md` 取包，再回到本 skill 看 C# 层
- 目标只是 APK 的 Java/Kotlin 层（非托管）→ `../apk-reverse/SKILL.md` / `../mobile-reverse/SKILL.md`
- 要做跨版本符号迁移 / 偏移推导 → `../binary-diff/SKILL.md`
- 要画调用链/攻击路径图 → `../diagram-generator/`
- de4dot 已成功但仍读不懂控制流（混淆残留、状态机型）→ 仍在本 skill，读 `references/common-workflow.md`，不要换 IDA

## When to Pivot

信号与判据见 `../ops/skill-pivot-contract.md`。本技能去向：

| 触发证据 | 换到 |
|---|---|
| Phase 1 无 CLR 头（`Data Directory[14]` 为 0、无 mscoree 导入） | `../ida-reverse/` / `../radare2/` / `../reverse-engineering/references/assault-entry.md` |
| 判定 IL2CPP 或 NativeAOT（native） | `../reverse-engineering/` + `../field-journal/seed-014_unity-il2cpp-reverse.md` |
| 需要 dnSpy IL 检查但 dnSpy.Console `--md` 持续报错、且 `ilspycmd` 输出不完整 | `../ghidra-reverse/`（CLR 元数据可反编译）交叉验证；仍失败则记 E-tool-gap 停止静态 |
| 目标实为恶意 .NET 样本，需求是 C2/持久化/IOC/YARA | `../malware-analysis/SKILL.md` |
| 目标需跨版本符号迁移 | `../binary-diff/SKILL.md` |

## 定义完成

本技能产出算"完成"的**外部可观测**条件（不许写形容词）：

- `target-clean.exe`（de4dot 产物路径）存在，且 `diec target-clean.exe` 的混淆器字段不再是原混淆器名（或记录 de4dot 报 `unknown` 的具体输出）
- `ilspycmd -p -o ./decompiled_src/` 产出目录可用 `grep` 定位到目标方法；`dnSpy.Console.exe target-clean.exe --il --md 0x0600XXXX` 有完整 IL 输出
- patch 类成品：`ldc.i4.0 → ldc.i4.1` 等改动的 IL 前后字节已落盘，`Save Module` 后的文件路径 + 一条运行命令（`dotnet target-patched.dll` 或 `target-patched.exe`）实际执行成功
- 关键判断在 **IL 视图** 下核对过（不是只看 C# 伪码），IL 片段贴进报告
- 若C# 重编译路径被选为成品：项目文件 + `dotnet build` 退出码 0，并说明为何不用 IL patch

## 输出契约

```
FACT:       <观察，带来源（命令 / 文件:行 / Evidence ID）>
HYPOTHESIS: <可测试断言 + confidence: high|medium|low>  （状态见 ../ops/binary-model.md）
QUESTION:   <当前最大不确定点>
NEXT:       <继续 | 换技能 | 停止（附成本判据）>
```

## 置信度词表

词表见 `../ops/confidence-vocabulary.md`。本技能特有判据：

- `confirmed`：**IL 视图**与**运行时值**双证据 —— IL 里看到的分支字节，与 dnSpyEx 调试器命中断点时读到的对象/字符串值一致（≥2 处独立锚点）
- `low`：仅凭 C# 反编译伪码下结论（已知失真：async/await、yield、编译器生成状态机在 C# 视图里被改写）；或 de4dot 未跑就先下字符串结论
