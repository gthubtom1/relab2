---
name: binary-ninja-reverse
description: Binary Ninja 逆向：HLIL/MLIL/LLIL 数据流、xrefs、类型与重命名、Python API。用于：点名 BN 看函数逻辑、跟调用链、与 IDA/Ghidra/radare2 交叉验证。
---

# Binary Ninja reverse engineering

Use Binary Ninja when the user explicitly selects it, when its ILs materially help data-flow analysis, or when IDA/Ghidra/radare2 results need an independent cross-check.

## Start safely

1. Confirm the repository case scope is ready before acting on a target.
2. Check `../TOOLS.md` for `binaryninja`; Binary Ninja is commercial software and must be installed manually with a valid Vector 35 license.
3. Work on a copy when applying patches or saving database changes.
4. Record imports/exports, entry points, architecture, and file hash before promoting findings.

## Choose the integration

- **GUI or Python API:** preferred when Binary Ninja is already open or the user wants direct interactive analysis.
- **Community MCP bridge:** use only when explicitly requested and after reviewing the third-party plugin boundary. Keep the Binary Ninja HTTP listener on `127.0.0.1:9009`; do not enable network exposure by default.
- **Fallback:** use `ghidra-reverse`, `ida-reverse`, or `radare2` when Binary Ninja is unavailable or its license/API cannot open the target.

The reviewed community integration is [`fosdickio/binary_ninja_mcp`](https://github.com/fosdickio/binary_ninja_mcp), GPL-3.0, plugin metadata version `1.1.0`, minimum Binary Ninja build `4000`. The repository is not an official Vector 35 component. This skill was checked against commit `8c5134ee46e2bf44f9a4d846bd971c3e39b3e306` on 2026-09-03.

Install the Binary Ninja side through its Plugin Manager or from the reviewed source. For the MCP stdio bridge, pin the published bridge version rather than using an unbounded package:

```text
npx -y binary-ninja-mcp@1.0.0 --host 127.0.0.1 --port 9009
```

Register that command only in the MCP client the user selected. The bridge is not ready until Binary Ninja is running, a binary is open, and the localhost plugin endpoint responds.

## Analysis workflow

1. Enumerate open binaries and select the intended view.
2. Capture binary status, entry points, segments, imports, exports, and representative strings.
3. Follow call sites and cross-references before interpreting a function in isolation.
4. Use HLIL for readable logic, MLIL SSA for data flow, and LLIL/disassembly when lifting loses instruction-level behavior.
5. Apply names, comments, and types incrementally; keep the original addresses in evidence.
6. Treat byte patches, prototype changes, and saved-file writes as mutations. Perform them only when requested and preserve the original artifact.
7. Cross-check high-impact conclusions with a second evidence source or another disassembler.

Useful MCP capability families include binary/view selection, `list_imports`, `list_exports`, `list_strings`, `decompile_function`, `get_il`, callers/callees, cross-references, types, comments, renames, and byte patching. Discover the live tool list instead of assuming every upstream function is present.

## Output

Report concrete addresses, function names, IL level, supporting strings/imports, confidence, and reproduction steps. Keep the Evidence → Finding → Path chain used by the rest of the repository.

---

## When NOT to use（近邻负例）

- 要 Hex-Rays 质量伪代码、FLIRT/Lumina 签名识别 → `../ida-reverse/SKILL.md`
- 无 BN 许可证、要免费反编译或批量 headless/CI → `../ghidra-reverse/SKILL.md`
- 只要 CLI 秒级看 strings/段/导入 → `../radare2/SKILL.md`
- 没装 BN（商业许可）/ 插件端点没起 → 留在本卡无意义：改用 `../ghidra-reverse/SKILL.md`、`../ida-reverse/SKILL.md` 或 `../radare2/SKILL.md`
- `diec` 报 VMP/Themida，或 `list_strings` 只有壳字样、函数计数极低 → `../reverse-engineering/references/assault-entry.md`
- 要寄存器值、断点、运行期内存 → `../x64dbg-reverse/SKILL.md`
- 目标实为 .NET / APK / 浏览器 JS → `../dotnet-reverse/SKILL.md` / `../apk-reverse/SKILL.md` / `../js-reverse/SKILL.md`
- 只想用社区 MCP bridge 自动跑而没审插件边界 → 不做：本卡要求先 review 第三方插件边界与 127.0.0.1:9009 白名单
- 结论想直接标 `confirmed` 但没有第二来源 → 不算完成

## When to Pivot

信号与判据见 `../ops/skill-pivot-contract.md`。本技能去向：

| 触发证据 | 换到 |
|---|---|
| BN 打不开目标（license / API 报错）、`127.0.0.1:9009` 插件端点不响应 | `../ghidra-reverse/SKILL.md` / `../ida-reverse/SKILL.md` / `../radare2/SKILL.md` |
| `diec` 报 VMP/Themida，或 HLIL 里大量 `IllegalInstruction`/不可辨识跳板、函数计数异常低 | `../reverse-engineering/references/assault-entry.md` |
| MLIL SSA lift 丢指令级行为（信号量漂移、自修改、SEH），必须看 LLIL/反汇编 → 本卡 §Analysis workflow 第 4 步；仍丢 → `../ghidra-reverse/SKILL.md` 交叉 |
| 静态 BN 结论与 x64dbg 动态读数矛盾（信号 3） | `../x64dbg-reverse/SKILL.md` 仲裁 |
| 同一假设连续两次无新证据（信号 4） | `../ops/analysis-decision-framework.md` R2/R43 |
| 要找两个版本间的同一函数 / 新偏移 | `../binary-diff/SKILL.md` |
| 目标实为 .NET / APK / JS | `../dotnet-reverse/SKILL.md` / `../apk-reverse/SKILL.md` / `../js-reverse/SKILL.md` |
| 已定位可达漏洞要写利用 | `../pwn-chain/SKILL.md` |

## 定义完成

本技能产出算"完成"的**外部可观测**条件（不许写形容词）：

- 目标以**独立副本**打开并被记录：入口点、段、imports/exports、strings、sha256 已入证据（`list_imports`/`list_exports`/`list_strings` 任一通道的输出）
- 关键函数按 IL 层记录：`get_il` 对同一函数有 HLIL/MLIL 两条记录，且 `decompile_function` 输出中原始地址保留
- 重命名落盘：`rename_function` / `set_comment` 后再次 `decompile_function` 可见新名；**已 patched 或保存过数据库时，`.bndb` 文件 mtime 更新且原文件未被覆盖**
- 可运行最小命令（自验通道仍通）：
  - `npx -y binary-ninja-mcp@1.0.0 --host 127.0.0.1 --port 9009` 起 bridge，且 `http://127.0.0.1:9009` 有响应
  - `list_project_binaries` / `list_exports` 至少一条非空
- 功能对照一致：高影响结论（如"该校验在本地完成"）有 BN 之外的第二来源（IDA/Ghidra 反编译或动态证据），否则标 `residual_risk`

## 输出契约

```
FACT:       <观察，带来源（命令 / 文件:行 / Evidence ID）>
HYPOTHESIS: <可测试断言 + confidence: high|medium|low>  （状态见 ../ops/binary-model.md）
QUESTION:   <当前最大不确定点>
NEXT:       <继续 | 换技能 | 停止（附成本判据）>
```

本技能填写示例：

```
FACT:       HLIL@0x1142 decompile：LICENSE 分支调 sub_11F0（sha256 → memcmp）；
            list_imports 有 BCryptOpenAlgorithmProvider（E-imports）
HYPOTHESIS: H-004 密钥由 BCrypt 派生后常驻栈上，sub_11F0 为比较函数
            confidence: medium，evidence_ids: [E-002, E-003]
QUESTION:   HLIL 的 var_18 与 MLIL SSA 的 eax 是否同一存储（lifting 分歧点）
NEXT:       继续（MLIL SSA 跟值；需运行动态值 → x64dbg-reverse）
```

## 置信度词表

词表见 `../ops/confidence-vocabulary.md`。本技能特有判据：

- `confirmed`：BN 的 HLIL/MLIL SSA 结论与第二独立来源一致（IDA/Ghidra 反编译，或 x64dbg 寄存器/内存 ≥3 轮同值），且 HLIL↔LLIL 反汇编在关键指令上能对上
- `high`：BN HLIL + MLIL SSA + `list_imports`/`list_strings` 锚点三者自洽，未做跨 lift 或跨工具验证
- `low`：**仅** HLIL，未与 LLIL/反汇编核对 —— lifting 在自修改代码、SEH、volatile 访问上会错
- `low`：BN 版本未过最低 build `4000`（本卡已 review commit `8c5134ee`），该版本下 IL API 形态可能不同，一切结构断言按此降级
- `contextual`：patched 后保存的 `.bndb` 里的地址，只对该副本有效

