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