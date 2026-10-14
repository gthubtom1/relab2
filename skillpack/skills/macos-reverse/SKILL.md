---
name: macos-reverse
description: macOS/Mach-O 逆向：codesign 签名与 Hardened Runtime、ObjC/Swift 符号恢复、dylib/.app 分析、TCC，工具 otool/jtool2。用于：分析 Mach-O 签名装载、恢复 ObjC 类结构。
---

# macOS / Mach-O Reverse Engineering

## ACTION REQUIRED（读完后立刻执行）

1. `NOW`: 读 `../field-journal/precedent-reverse.md` —— 本机做过多轮的常规操作清单，直接照做，不要停在犹豫上
2. `NOW`: **查经验卡** —— `python skills/scripts/experience-card.py search "<你看到的症状>"`。
   命中就读那张卡的 `invariant` + `decision.action`，并**逐条对照** `scope.appliesWhen`
   与 `scope.stopsWhen`：少一条前提就停用；命中任一停止条件就停。
   历史卡**不替代**当前目标的实测证据。详见 `../experience-cards/INDEX.md`。
3. `NOW`: 确认目标为 macOS/Mach-O/App bundle（iOS IPA → `mobile-reverse/`）
4. `NEXT`: `../TOOLS.md`；jtool2/lldb 等
5. `ACT`: 签名与装载信息 → 静态 → 动态（lldb/Frida）

## 适用场景

- Mach-O 可执行文件 / dylib / framework
- .app bundle、LaunchAgent/Daemon
- Objective-C / Swift 符号与 runtime
- 公证/签名、Hardened Runtime、TCC 相关行为分析
- macOS 恶意软件静态/动态分析（联合 malware-analysis）

## 工作流

### 1. 包体与签名

```bash
file target
codesign -dv --verbose=4 target
spctl -a -vv target 2>&1
otool -L target
```

### 2. 静态

```text
□ class-dump / swift-demangle / Hopper / Ghidra / IDA
□ 字符串与 XPC 服务名、TCC 敏感 API
□ LC_LOAD_dylib 依赖与 rpath
```

### 3. 动态

```text
□ lldb / Frida
□ fs_usage / log stream 观察
□ 网络：联合 protocol-reverse 或代理
```

## 工具链

| 工具 | 用途 |
|------|------|
| otool / nm / codesign | 系统自带 |
| Hopper / Ghidra / IDA | 反编译 |
| class-dump / dsdump | ObjC |
| Frida / lldb | 动态 |
| jtool2 | Mach-O |

## 参考

- `references/macho-triage.md`
- `../mobile-reverse/`（iOS） `../ghidra-reverse/` `../malware-analysis/`

## 路由上下文

**上游**: MASTER R31  
**下游**: iOS → mobile-reverse；通用样本 → malware-analysis

## 任务完成自检

- [ ] 是否记录签名/Hardened Runtime 状态？
- [ ] 是否有地址级/符号级结论？
- [ ] Checklist？
---

## When NOT to use（近邻负例）

- 目标是 iOS IPA（不是 macOS 二进制）→ `../mobile-reverse/SKILL.md`
- 目标是 macOS 上运行的 .NET 托管程序（有 CLR 头）→ `../dotnet-reverse/SKILL.md`
- 目标只是普通 ELF/PE、恰好在 macOS 宿主上分析 → `../reverse-engineering/references/assault-entry.md`
- 目标是 iOS 上的 Android 侧协议/封包还原 → `../protocol-reverse/SKILL.md`
- 重点是证书链本身（信任锚、吊销、固定证书绕过之外的 PKI 分析）→ `../identity-federation/SKILL.md`
- 目标是 macOS 恶意样本全流程（行为/沙箱/YARA/IOC）→ `../malware-analysis/SKILL.md`（本卡只做 Mach-O 专项）
- 无 macOS 环境却要做 TCC/entitlement 运行时结论 → 静态可做，运行时 MUST 有真机或授权 VM；不要拿 Linux 假 macOS 结论冒充

## When to Pivot

信号与判据见 `../ops/skill-pivot-contract.md`。本技能去向：

| 触发证据 | 换到 |
|---|---|
| 判定目标实为 iOS IPA（Info.plist / embedded.mobileprovision） | `../mobile-reverse/SKILL.md` |
| 二进制是 .NET 托管（mono 嵌入或 CLR 头） | `../dotnet-reverse/SKILL.md` |
| 恶意样本行为分析成主任务（C2/持久化/IOC/YARA） | `../malware-analysis/SKILL.md` |
| 网络协议还原（ObjC 层之外的自定义帧） | `../protocol-reverse/SKILL.md` |
| 需要 Ghidra/r2/IDA 深挖 Mach-O 函数体 | `../ghidra-reverse/`、`../radare2/`、`../ida-reverse/` |
| 签名校验被绕过仍是目标本身（不是替换签名） | 回到本卡 §1（codesign/spctl 是判据不是手段） |

## 定义完成

本技能产出算"完成"的**外部可观测**条件（不许写形容词）：

- `codesign -dv --verbose=4 <target>` 输出落盘：Authority/CDHash/TeamIdentifier/entitlements 已读；`spctl -a -vv` 的 accepted/rejected 明确记录
- `otool -L <target>` 依赖表 + `otool -l` 的 LC_* 段清单落盘（rpath / LC_LOAD_DYLIB / LC_CODE_SIGNATURE 位置）
- 符号级结论：地址级（函数地址 + 所属 dylib/exe）或符号级（demangle 后的 ObjC selector / Swift mangled name）至少一种，落到报告
- 动态结论（lldb/Frida）有会话记录可复跑；未执行运行时则显式写"运行时未验证"
- 引用链：每条结论可回溯到一段命令输出 / 一段 Hopper/Ghidra 反编译片段

## 输出契约

```
FACT:       <观察，带来源（命令 / 文件:行 / Evidence ID）>
HYPOTHESIS: <可测试断言 + confidence: high|medium|low>  （状态见 ../ops/binary-model.md）
QUESTION:   <当前最大不确定点>
NEXT:       <继续 | 换技能 | 停止（附成本判据）>
```

## 置信度词表

词表见 `../ops/confidence-vocabulary.md`。本技能特有判据：

- `confirmed`：静态签名信息（`codesign -dv` / `otool -l`）与运行时行为（lldb 断点命中、Frida Hook 捕获）对同一断言各给一次独立证据
- `low`：只凭 stripped 二进制里残留字符串命名推断符号用途；或看到 entitlements 列了某权限就断言运行时一定生效（TCC 可能仍拒绝）
