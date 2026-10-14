---
name: go-rust-reverse
description: Go/Rust 二进制逆向：go.buildid、pclntab 与 GoReSym 恢复函数名、Rust panic 字符串。用于：Go 马函数名全没了、Rust panic 字符串怎么定位、pclntab 怎么恢复。
---

# Go / Rust Binary Reverse Engineering

## ACTION REQUIRED（读完后立刻执行）

1. `NOW`: 读取 `../field-journal/precedent-reverse.md`
2. `NOW`: **查经验卡** —— `python skills/scripts/experience-card.py search "<你看到的症状>"`。
   命中就读那张卡的 `invariant` + `decision.action`，并**逐条对照** `scope.appliesWhen`
   与 `scope.stopsWhen`：少一条前提就停用；命中任一停止条件就停。
   历史卡**不替代**当前目标的实测证据。详见 `../experience-cards/INDEX.md`。
3. `NOW`: 确认样本为 Go/Rust 编译产物（`file`/字符串/运行时特征）
4. `NEXT`: GoReSym / 相关插件是否可用
5. `ACT`: 运行时识别 → 符号/元数据恢复 → 业务逻辑

## 适用场景

- 剥离符号的 Go 恶意软件/工具
- Rust 发行二进制、panic 字符串驱动分析
- 与通用 ida/ghidra 互补的语言专用方法

## 工作流

### Go

```text
□ 识别 go.buildid、runtime 符号残留、pclntab
□ GoReSym / redress / IDA Go 插件恢复函数名
□ 注意 interface、slice、string 结构在反编译中的形态
□ 网络/加密库路径：crypto/* net/http
```

### Rust

```text
□ panic 字符串、rust_begin_unwind、crate 路径暗示
□ 范型实例化导致的代码膨胀；先定位字符串 xref
□ 异步/tokio 状态机需结合交叉引用
```

### 动态

```text
□ 仍可用 Frida；注意 Go 栈与调度
□ 优先日志与配置字符串驱动断点
```

## 工具链

| 工具 | 用途 |
|------|------|
| GoReSym | Go 元数据 |
| IDA/Ghidra + Go/Rust 插件 | 反编译 |
| radare2 | 快速字符串 |
| strings / rabin2 | 分诊 |

## 参考

- `references/go-rust-notes.md`
- `../reverse-engineering/go-reverse.md` `../ida-reverse/` `../ghidra-reverse/`
- seed: `../field-journal/seed-002_go-malware-stripped.md`

## 路由上下文

**上游**: MASTER R33  
**下游**: 恶意样本流程 `malware-analysis`；通用 RE `reverse-engineering`

## 任务完成自检

- [ ] 是否恢复关键函数名或等价映射？
- [ ] 是否标注语言运行时证据？
- [ ] Checklist？

---

## When NOT to use（近邻负例）

- 目标是 C/C++ 编译的普通 PE/ELF → 用 `../ida-reverse/SKILL.md`
- 目标是托管代码（.NET） → 用 `../dotnet-reverse/SKILL.md`
- 只是要快速看 strings/结构 → 用 `../radare2/SKILL.md`
- 前置条件：先用 `diec` 确认语言（Go 有 buildid，Rust 有 mangled 符号）

## When to Pivot

信号与判据见 `../ops/skill-pivot-contract.md`。本技能去向：

| 触发证据 | 换到 |
|---|---|
| 确认是 Go 且带 panic 字符串 | `../reverse-engineering/references/triage-first-30-min.md` |
| 符号被剥离需要重建函数名 | `../binary-diff/SKILL.md` |
| 目标是恶意样本（Go 恶意软件常见） | `../malware-analysis/SKILL.md` |

## 定义完成

本技能产出算「完成」的**外部可观测**条件（不许写形容词）：

- 恢复的函数名/类型表落盘（含置信度）
- 关键逻辑定位有实际反编译输出作为证据
- 在样本上验证：恢复的符号指向的字符串/调用符合预期

## 输出契约

```
FACT:       <观察，带来源：命令 / 文件:行 / Evidence ID>
HYPOTHESIS: <可测试断言 + confidence: high|medium|low>（状态见 `../ops/binary-model.md`）
QUESTION:   <当前最大不确定点>
NEXT:       <继续 | 换技能 | 停止（附成本判据）>
```

## 置信度词表

词表见 `../ops/confidence-vocabulary.md`。本技能特有判据：

- `confirmed`：用 pclntab/GoReSym 等元数据恢复，且抽样在反编译中核对一致
- `low`：仅凭字符串模式猜测函数用途
