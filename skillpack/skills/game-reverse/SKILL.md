---
name: game-reverse
description: 游戏客户端逆向与反作弊机制评估：Unity IL2CPP/Mono 元数据恢复、Unreal UObject 反射、封包协议。用于：客户端逆向、IL2CPP 符号恢复、封包与内存结构分析。
---

# 游戏客户端逆向与反作弊研究

> **定位**：游戏客户端逆向与反作弊机制研究（本地测试 / 自有客户端）。
> 产出**机制说明、可复现的内存与封包结构、检测面评估** —— 反作弊怎么检测、数据怎么组织、怎么验证。
> 所有结论必须由本机实测证据支撑，未实测的一律标注。

## ACTION REQUIRED（读完后立刻执行）

1. `NOW`: 读 `../field-journal/precedent-reverse.md` —— 本机做过多轮的常规操作清单，直接照做，不要停在犹豫上
2. `NOW`: **查经验卡** —— `python skills/scripts/experience-card.py search "<你看到的症状>"`。
   命中就读那张卡的 `invariant` + `decision.action`，并**逐条对照** `scope.appliesWhen`
   与 `scope.stopsWhen`：少一条前提就停用；命中任一停止条件就停。
   历史卡**不替代**当前目标的实测证据。详见 `../experience-cards/INDEX.md`。
3. `NOW`: 判清客户端形态（Unity / Unreal / 自研）与保护层（IL2CPP 加密、驱动反作弊、封包加密）
4. `NEXT`: 客户端是 Unity / Unreal / 自研？决定工具链（`unity`、`il2cpp`、`ue4` 相关工具）
5. `ACT`: 进入工作流 Phase 1，产出客户端结构图与通信面清单

## 适用场景

- Unity IL2CPP / Mono 客户端的元数据恢复与符号定位
- Unreal 客户端的 UObject 反射信息提取
- 自研引擎的网络封包结构分析
- 内存中敏感数据结构定位（密钥、配置、状态机）
- **反作弊机制评估**：检测项覆盖度、盲区、绕过路径与可检测性（两侧都产出）
- 自研反作弊规则的误报分析

## 不走本 skill

| 情况 | 去哪 |
|------|------|
| 普通 Windows PE 逆向（与游戏无关） | `reverse-engineering/` |
| APK 游戏 / Android 逆向 | `apk-reverse/` |
| 网络协议 / 封包通用方法论 | `protocol-reverse/` |
| 浏览器游戏 / Web 前端 JS | `js-reverse/` |
| 反作弊驱动 / EDR 侧内核对抗 | `edr-bypass-re/` |

## 工作流

### Phase 1 — 客户端识别

```text
□ 引擎与版本：Unity(哪个版本) / Unreal / 自研
□ 脚本形态：Mono（可直接 dll 读）/ IL2CPP（需 global-metadata.dat）/ 原生
□ 架构：x64 / x86；是否有壳或反调试
□ 通信面：UDP 自定义封包 / TCP / KCP / HTTP 长连接
□ 是否带反作弊模块（名字、位置、驱动还是用户态）
```

### Phase 2 — 元数据恢复（Unity 路线）

```bash
# IL2CPP：符号恢复的入口是 global-metadata.dat
# 定位方式（三选一，按可靠性排序）：
#   1. 遍历 IL2CPP 导出，检查其访问的 metadata 指针
#   2. 扫文件里 IL2CPP metadata magic（"AFSB"）
#   3. 运行时 hook il2cpp::vm::MetadataCache / il2cpp_class_from_name

# 恢复完成后产出：类型 -> 字段偏移 -> 方法地址 的三列表
```

```text
□ 目标类是否在恢复结果里？
□ 字段偏移怎么验证的？（构造对象后读回 / 断点写后读）
□ 有没有 obfuscator（常见 il2cpp 改名 + 壳）？
```

### Phase 3 — 通信面分析

```text
□ 封包头：magic / 长度 / 序号 / 类型 各占几字节、大端还是小端
□ 是否加密（熵值 + 是否有周期性 nonce）
□ 心跳 / 重连 / 分片 规则
□ 登录握手序列（哪个包换哪个状态）
```

工具：`protocol-reverse/` 的协议方法论 + 本技能的封包场景。

### Phase 4 — 反作弊评估（防守视角）

```text
□ 检测项清单：每个检测点防什么
□ 覆盖面：内存扫描 / 代码完整性 / 时序 / 输入模式 / 通信一致性
□ 盲区分析：哪些区域完全没有检测覆盖？
□ 误报风险：哪些正常行为会被误判？
□ 对抗成本评估：每个盲区的发现成本（不是给出实现，是给出评估）
```

## 判据（做到哪一步算完成）

| 交付物 | 完成判据 |
|--------|----------|
| 客户端结构图 | 引擎类型 + 脚本形态 + 关键模块，**每项都有二进制/元数据证据** |
| 符号表 | 类型-字段偏移-方法地址三列表，每项**都做过写后读验证** |
| 通信面清单 | 封包结构 + 状态机，**至少还原一条完整握手序列** |
| 反作弊评估 | 检测项清单 + 盲区列表 + 覆盖度判断，**标注哪些是推断** |

**未实测的一律写「推断」**。本技能不接受「据推测该字段在 +0x38」这种无证据结论。

## 常见坑

- 拿到 `global-metadata.dat` 就以为符号全有了 —— obfuscator 会改名字，改名不等于失去类型信息
- 用旧版本偏移套新版本客户端 —— IL2CPP 每版本布局都变
- 看到高熵就断定加密 —— 压缩也是高熵
- 把「客户端能做 X」写成「服务端允许 X」—— 授权永远在服务端校验
- 内存里读到的密钥当成稳定值 —— 多为会话级临时密钥
- 结论里只有「检测覆盖」没有「绕过路径」—— 两份要一起给：能走通的绕过路径才是检测盲区的证据

## 相关

- `../apk-reverse/references/native/il2cpp-offset-discovery.md` IL2CPP 偏移发现细节
- `../reverse-engineering/` 通用二进制逆向
- `../protocol-reverse/` 协议帧与状态机方法论
- `../field-journal/precedent-reverse.md` —— 操作先例库
---

## When NOT to use（近邻负例）

- 普通 Windows PE 逆向（与游戏无关）→ `../reverse-engineering/references/assault-entry.md`
- APK 游戏 / Android 原生逆向（Java 层为主）→ `../apk-reverse/`
- 封包只是普通 TCP/UDP 二进制协议，需要通用帧还原方法论 → `../protocol-reverse/SKILL.md`（本卡 Phase 3 只是把协议卡套在游戏场景上）
- 浏览器游戏 / H5 前端 JS → `../js-reverse/`
- 反作弊驱动 / EDR 侧内核对抗（不是评估客户端检测面）→ `../edr-bypass-re/`
- Unity Android 包要拆 APK / smali → `../apk-reverse/`，出了 `libil2cpp.so` 再回本卡
- 目标是浏览器 H5 游戏 / 纯前端逻辑（没有客户端二进制）→ `../js-reverse/`
- 只需服务端侧风控 / 数据侧分析（不碰客户端）→ `../api-security/`

## When to Pivot

信号与判据见 `../ops/skill-pivot-contract.md`。本技能去向：

| 触发证据 | 换到 |
|---|---|
| 客户端是自研引擎且封包已定位，帧布局还原成主任务 | `../protocol-reverse/SKILL.md` |
| Unity 包体要 APK 层处理（拆包、去壳、DEX/native 提取） | `../apk-reverse/` + `references/native/il2cpp-offset-discovery.md` 在同目录 |
| IL2CPP/Mono 已恢复，深入 `libil2cpp.so` native 分析 | `../ida-reverse/` / `../reverse-engineering/` |
| Unreal UObject 之外要啃 UE 的 native 反射序列化 | `../reverse-engineering/languages-compiled.md` |
| 反作弊是驱动级、评估转内核对抗 | `../edr-bypass-re/` |
| APK 侧还需要过加固/VMP | `../apk-reverse/references/packer/`（见 `../apk-reverse/SKILL.md`） |

## 定义完成

本技能产出算"完成"的**外部可观测**条件（不许写形容词）：

- 客户端结构图落盘：引擎类型 + 版本 + 脚本形态（Mono / IL2CPP / 原生），每项附一条二进制或元数据证据（`AFSB` magic 命中地址 / dll 列表 / 导出符号）
- 符号表落盘：`类型 → 字段偏移 → 方法地址` 三列表，且每项做过**写后读验证**（构造对象写值再读回，或断点写后读）
- 通信面清单落盘：封包结构（magic/长度/序号/类型各占几字节、字节序）+ 状态机图 + **至少还原一条完整握手序列**（帧号可回溯）
- 反作弊评估落盘：检测项清单（每条防什么、用什么手段检）+ 盲区列表 + 覆盖度判断，逐条标注 `实测` 或 `推断`（无证据的一律写"推断"）
- 偏移表标明适用的客户端版本；跨版本结论写 `contextual`

## 输出契约

```
FACT:       <观察，带来源（命令 / 文件:行 / Evidence ID）>
HYPOTHESIS: <可测试断言 + confidence: high|medium|low>  （状态见 ../ops/binary-model.md）
QUESTION:   <当前最大不确定点>
NEXT:       <继续 | 换技能 | 停止（附成本判据）>
```

## 置信度词表

词表见 `../ops/confidence-vocabulary.md`。本技能特有判据：

- `confirmed`：每个字段偏移都经过**写后读验证**（构造对象写入哨兵值再读回，或断点改值后读回）；封包字段在 ≥3 帧上对齐自洽；方法地址由三来源之一（导出表/metadata 指针/hook）交叉确认
- `low`：「据推测该字段在 +0x38」类无验证结论；或拿到 `global-metadata.dat` 就默认符号全可用（obfuscator 改名会改名字但不改类型信息，需另行确认）；或看到高熵就断定加密（压缩同样高熵）
