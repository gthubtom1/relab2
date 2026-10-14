---
name: go-rust-reverse
description: Go/Rust 二进制逆向：go.buildid、pclntab 与 GoReSym 恢复函数名、Rust panic 字符串。用于：Go 马函数名全没了、Rust panic 字符串怎么定位、pclntab 怎么恢复。
---

# Go / Rust Binary Reverse Engineering

## ACTION REQUIRED（读完后立刻执行）

1. `NOW`: 读 `../field-journal/precedent-reverse.md` —— 本机做过多轮的常规操作清单，直接照做，不要停在犹豫上
2. `NOW`: **查经验卡** —— `python skills/scripts/experience-card.py search "<你看到的症状>"`。
   命中就读那张卡的 `invariant` + `decision.action`，并**逐条对照** `scope.appliesWhen`
   与 `scope.stopsWhen`：少一条前提就停用；命中任一停止条件就停。
   历史卡**不替代**当前目标的实测证据。详见 `../experience-cards/INDEX.md`。
3. `NOW`: 确认样本为 Go/Rust 编译产物（`file`/字符串/运行时特征）
4. `NEXT`: GoReSym / 相关插件是否可用
5. `ACT`: 运行时识别 → 符号/元数据恢复 → 业务逻辑

## 适用场景

- 剥离符号的 Go 恶意软件/工具（`gopclntab` / `moduledata` 仍在文件里，函数名可自恢复）
- Rust 发行二进制：panic 字符串、`rust_begin_unwind`、crate 路径可当锚点
- gomobile 产物（APK/IPA 里的 `libgojni.so`）中的 Go 运行时
- 与通用 `../ida-reverse/` `../ghidra-reverse/` 互补的语言专用方法

## 指纹判据（先认语言，再谈符号）

| 看到的读数 | 判定 | 接着要拿到的证据 |
|---|---|---|
| `go.buildid` 魔数在，或字符串里成片 `runtime.` / `internal/abi` / `type:.` | Go | `go version -m <file>` 读出模块表与 `-ldflags`（`-s -w` 是否打掉了符号） |
| `.gopclntab` 节区名或 `moduledata` 结构残留 | Go 且函数表可恢复（Go 1.2+ 函数表随二进制走，裁的只是名字） | 恢复后清点：拿到的函数名数 vs `go tool nm` 行数，差一个量级说明只提了半边 |
| 字符串出现 `src/…/lib.rs`、`crate/`、`called \`Result::unwrap()\``、`index out of bounds` | Rust；panic 文本就是锚点 | 先 xref panic 串，再顺着 call 树往业务走；`RUST_BACKTRACE=1` 若能跑，栈里直接给文件:行 |
| `diec` 报 MSVC/GCC + C++ RTTI，且全样本 0 处 `runtime.` | 不是本卡 | 见「When NOT to use」 |
| `.gopclntab` 段熵 >7.4、节区名被抹、入口在解压 stub 里 | 已加壳，函数表不可直读 | 见「When to Pivot」脱壳一行 |

Go 侧形态学：`interface` 是 (itab, data) 双字、`slice` 是 (ptr,len,cap) 三字、字符串是 (ptr,len) 二字 ——
反编译器吐出的 `*(a + 8)` 多半正是这三样的成员，别当成自研结构。
Rust 侧形态学：单态化会让同一逻辑在 `.text` 里出现 N 份；先按 panic 串聚类，再挑引用最多的那份逆。

## 工具链

| 工具 | 用途 | 定位方式 |
|---|---|---|
| `diec` | 第一刀：判语言/壳（Go buildid、Rust mangled、`.NET`） | 探测 id `diec`（toolmap 有 `die`→`diec` 的 CLI 孪生别名） |
| GoReSym / redress | 提 `gopclntab`+`moduledata` → 函数名、类型、接口表 | 单文件工具，缺则退回 `go tool nm` |
| `go tool nm` / `go tool objdump` / `go version -m` | 有 Go 工具链时的符号清点与 buildinfo | 探测 id `go` |
| `rabin2` | `-zz` 字符串、`-I` 壳/节区、`-s` 符号一次出完，快过 GUI | 探测 id `rabin2`（r2 套件自带） |
| `radare2` | `r2 -A` 追 xref、改函数名后回写项目 | 探测 id `radare2` |
| `idat`（IDA CLI） | 大样本（>50 MB）批量交叉引用、Go/Rust 插件反编译 | 探测 id `idat`；GUI 版不是它，别拿 GUI 跑批 |
| `Ghidra` + `analyzeHeadless` | 批量脚本：一次导出 N 个函数伪代码，喂给比对/命名流程 | 探测 id `ghidra_headless`（headless 入口） |
| `frida` | 动态：Go 栈与 goroutine 调度会让「按名字下断点」错位，优先 hook 配置读取点与 panic 前一刻 | 探测 id `frida`；与目标侧 frida-server 版本必须严格一致 |
| `gdb` | Linux 侧读 goroutine 栈（`runtime.g0` / `g` 结构、`runtime.morestack` 帧） | 探测 id `gdb` |
| `x64dbg`（MCP `127.0.0.1:9094`） | Windows 侧动态；**MCP 端口只活在 GUI 实例里，headless 起不来**，按 `../x64dbg-reverse/` 的入口拉 GUI | 探测 id `x64dbg` |
| `cdb` | 无 GUI 环境下的 Windows 调试兜底（脚本可复现） | 探测 id `cdb` |

> **动手前先定位工具与通道。**
> `. <仓根>\skillpack\skills\scripts\lib\Bootstrap.ps1` → `Resolve-ReverseToolSpec -Name <id>`，用返回的 `Command` 全路径调（不要依赖 cwd）；
> **`Get-Command` 查空 ≠ 缺工具**（PATH 快照陷阱，见 `../references/env-selfcheck.md`），四级探测全 `Available=False` 才允许报缺。
> 通道另用 `powershell -NoProfile -ExecutionPolicy Bypass -File skillpack\skills\scripts\mcp-status.ps1` 看三列（注册了哪些 / 谁在监听 / 怎么起）：
> **注册 ≠ 在监听**，idapro（`127.0.0.1:13337`）与 x64dbg（`127.0.0.1:9094`）平时 `closed` 是按需设计，用到再起。

## 参考

- `references/go-rust-notes.md`
- `../reverse-engineering/go-reverse.md` `../ida-reverse/` `../ghidra-reverse/` `../radare2/`
- seed: `../field-journal/seed-002_go-malware-stripped.md`

## 路由上下文

**上游**: MASTER R33  
**下游**: 恶意样本流程 `malware-analysis`；通用 RE `reverse-engineering`

## 任务完成自检

- [ ] 语言判定有硬证据吗（buildid / pclntab / crate 路径），还是只看了字符串风格？
- [ ] 恢复的函数名有没有抽样核对（≥5 个看 xref 处的串与调用是否对得上）？
- [ ] 恢复表落盘了吗（含来源：pclntab / GoReSym / panic xref + 置信度）？
- [ ] 没走完探测层就报「本机没工具」了吗？

---

## When NOT to use（近邻负例）

- 目标是 C/C++ 编译的普通 PE/ELF（`diec` 报 MSVC/MinGW，全样本无 `runtime.` 痕迹）→ 用 `../ida-reverse/SKILL.md`
- 目标是 .NET 托管程序集（IL 元数据可直接读）→ 用 `../dotnet-reverse/SKILL.md`
- 只要一份 strings/节区/导入表概览，不打算恢复函数名 → 用 `../radare2/SKILL.md`
- 手里有该程序的旧版符号结果，新版只是整体位移 → 用 `../binary-diff/SKILL.md`
- 样本已定性为恶意、下一步要 IOC/家族归因而不是恢复函数名 → 用 `../malware-analysis/SKILL.md`
- 要逆的是 WASM 里的 Go（`GOOS=js` 产物，运行时表不在原生格式里）→ 用 `../reverse-engineering/SKILL.md`
- 静态已无路（自解密、逐函数校验），必须靠进程内实参才能推进 → 用 `../x64dbg-reverse/SKILL.md`

## When to Pivot

信号与判据见 `../ops/skill-pivot-contract.md`。本技能去向：

| 触发证据 | 换到 |
|---|---|
| `rabin2 -I` 显示 UPX/自解密 stub，`.gopclntab` 段熵 >7.4、函数表读不出来 | 先脱壳：`../reverse-engineering/references/assault-entry.md`，脱完回本卡 |
| 反编译栈帧里已无 `runtime.`、直呼 `malloc`/`pthread_`（越过 cgo 边界） | `../ida-reverse/SKILL.md`；本机 IDA 不可用则 `../ghidra-reverse/SKILL.md` |
| 出现带 `crate/` 的 panic 串，或 `RUST_BACKTRACE=1` 打出文件:行 | 留本卡 Rust 分支，以该 panic 位置为锚逆 call 树 |
| 同一函数两轮还原后仍读不出（名字有了，但拿不到任何串/调用佐证） | `../x64dbg-reverse/SKILL.md` 走动态取实参，或 `frida` hook 入口取参数 |
| 新版样本符号全无，手上却有旧版已恢复的函数名表要批量迁移 | `../binary-diff/SKILL.md` |
| 目标问题从「这个符号是谁」变成「它连了谁、落了什么盘」（出现 C2 域名、持久化路径串） | `../malware-analysis/SKILL.md` |
| 样本是 `libgojni.so`（gomobile 打入移动端 App），要看 App 侧调用 | `../mobile-reverse/SKILL.md` |
| `go tool nm`/GoReSym 在 >5 万符号的样本上跑满 30 秒仍拿不到 `main.` 前缀符号 | 换符号源：改用字符串+xref 驱动，别继续等工具 |

## 定义完成

本技能产出算「完成」的**外部可观测**条件（不许写形容词）：

- 恢复的函数名/类型表落盘，每条带来源（pclntab / GoReSym / panic xref）与置信度
- 关键逻辑定位有实际反编译输出（伪代码片段 + 地址）作为证据，不是「已定位」四个字
- 抽样自证：随机抽 ≥5 个恢复出的名字，其 xref 处的字符串或调用与名字语义一致
- Go 侧留下 `go version -m` 的模块表；Rust 侧留下 crate 路径清单

## 输出契约

```
FACT:       <观察，带来源：命令 / 文件:行 / Evidence ID>
HYPOTHESIS: <可测试断言 + confidence: high|medium|low>（状态见 `../ops/binary-model.md`）
QUESTION:   <当前最大不确定点>
NEXT:       <继续 | 换技能 | 停止（附成本判据）>
```

## 置信度词表

词表见 `../ops/confidence-vocabulary.md`。本技能特有判据：

- `confirmed`：函数名由 pclntab/GoReSym 等元数据恢复，且抽样 ≥5 个在反编译里核对一致
- `medium`：由唯一字符串锚点或调用图位置反推的名字，尚未交叉验证
- `low`：仅凭字符串模式（`main.` 前缀、`panic` 关键词）猜用途，或仅凭段名/节区猜语言
