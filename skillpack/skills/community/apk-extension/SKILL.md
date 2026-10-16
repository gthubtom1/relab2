---
name: community-apk-extension
description: APK 逆向能力扩展入口。用于：拿到新版 apk-reverse 的 doctor、capability matrix、DEX/Dart/native、Frida、重打包和证据脚本时，接回共云 apk-reverse 的 case 与工具门。
---

# Community APK capability adapter

## ACTION REQUIRED

1. `NOW`: 确认 APK、设备/ABI、root/Frida/ADB、目标行为和交付形态，先走
   `SKILL.md` 的 scope 与 control-build gates。
2. `NEXT`: 读取 `skillpack/community-raw/apk-reverse-source/evidence/capability-matrix.json`
   和 `../../../community-raw/apk-reverse-source/evidence/known-limitations.md`；`partial`
   要先声明缺口，`blocked` 直接停在边界说明。
3. `NEXT`: 通过 canonical `../../TOOLS.md` 和 doctor/preflight 检查工具状态。
   不执行源仓库的隐式安装、固定机器路径、debug keystore 或未授权设备命令。
4. `ACT`: 仅在 case、设备和动作授权就绪后使用按需脚本组：baseline/doctor、DEX/Dart、
   APK packaging、native、Frida、protocol 或 governance；每步保留 zero-change 对照。
5. `DONE`: 保存 artifact path/hash、安装/启动和目标行为直接观察、回归结果、设备状态、
   evidence strength 和 remaining limitations。文档命令漂移不能作为通过证据。

## Script groups

| 组 | 适配目录 |
|---|---|
| baseline / doctor | `skillpack/community-raw/apk-reverse-source/` |
| DEX / Dart | `skillpack/community-raw/apk-reverse-source/` |
| packaging / install | `skillpack/community-raw/apk-reverse-source/` |
| native / ELF | `skillpack/community-raw/apk-reverse-source/` |
| Frida / dynamic | `skillpack/community-raw/apk-reverse-source/` |
| protocol / service | `skillpack/community-raw/apk-reverse-source/` |
| governance / leak scan | `skillpack/community-raw/apk-reverse-source/` |

这只是新版能力的适配入口；普通 APK 任务仍优先由 `R1` canonical `apk-reverse`
承载，避免两个 APK 主入口争抢同一提示。

## Loading budget（T11 / 规范 17.25）

- 单次初筛最多返回 5 个 wrapper（`--limit` 取值 1..5，越界直接 exit 2）。
- 单次查询命中的 adapted reference 总数上限 50；超预算时停止并报告
  `blocked` / `budget_exceeded`（exit 20），不静默截断。
- 每个 wrapper 初次只展示 3 个 reference（`REFERENCE_LIMIT=3`，产品决策，不得单方面调大）；
  第 4 个起是二级加载：用 `--source apk-reverse-community` 重查、逐条人工确认后再读正文。
- 置信度 `confidence = best_score / hint 词数`，低于 0.35 为 `low_confidence`；
  首尾 wrapper 分差 ≤20% 为 `ambiguous_tie`，两者都进 `needs_review`。
- 超预算后的确认格式：报出收窄后的 hint 与 `--source` 取值，等人工确认后再查。
- 完整数字与 policy manifest 变更请求见 `../../../docs/community/LOADING-BUDGET.md`。
