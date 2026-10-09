---
name: ghidra-reverse
description: Ghidra逆向 — 当用户没IDA想用免费工具看二进制，或说“用Ghidra帮我反编译这个”“批量headless怎么跑”“字符串交叉引用在哪”时使用。Use when Ghidra decompile, cross-refs, headless analysis.
---

# Ghidra Reverse Engineering

## ACTION REQUIRED（读完后立刻执行）

1. `NOW`: 读取 `../field-journal/precedent-reverse.md`
2. `NOW`: 确认需要 **Ghidra**（无 IDA / 偏好开源 / 批量 headless）
3. `NOW`（MCP 通道必备）: 拉起常驻 HTTP 服务（~8 s 冷启）——**启动方式与前置条件按 `../references/tool-registry.md` 的 `pyghidra-mcp` 端点行取**（`启动方式` = 常驻守护，冷启 7–10 s，幂等；`端点` = `127.0.0.1:9111/mcp`；`依赖` = `JDK 21+` + Ghidra 本体；Ghidra 本体路径用探测层 `Resolve-ReverseToolSpec -Name 'ghidraRun'` 的 `Command` 取（`Get-Command` 只是四级探测的第 2 级，返回空不等于缺工具，见 `../references/env-selfcheck.md`）。本项目无 `toolreg/`，该端点文档即事实源），再按该端点探活确认 READY 且 `Tool Count : 20`；本会话看不到 `ghidra` 工具时先 `/mcp reconnect ghidra`。**不要要求用户改 `mcp.json`，服务由 agent 自己起。**
4. `NEXT`: 读 `../TOOLS.md` 查 ghidra / ghidra-mcp 路径
5. `NEXT`: 缺工具 → bootstrap `ghidra-mcp`（若 manifest 支持）或按手动步骤装 Ghidra
6. `ACT`: 导入样本 → 自动分析 → 导出关键函数反编译
7. `DONE`: 静态分析收尾按同一来源（`../references/tool-registry.md` 的 `pyghidra-mcp` 端点行）停守护（先经 MCP `save` 落盘，再释放 9111/9112 端口，避免残留 JVM）

## 适用场景

- 无 IDA 许可证时的主逆向入口
- 批量 headless 分析 / CI 中反编译
- Ghidra 脚本（Java/Python Jython/PyGhidra）自动化
- 与 `binary-diff` / `patch-diff-exploit` 的 ghidriff 联动

## 与 IDA 分工

| 需求 | 优先 |
|------|------|
| 已有 IDA MCP 深挖 | `ida-reverse/` |
| 开源 / 批量 / 教学 | **本 skill** |
| 仅 CLI 快速侦察 | `radare2/` |

## 工作流

### 1. 智能体首选：pyghidra-mcp（20 个开箱即用工具，HTTP 常驻守护）

**这是可选通道，不是默认前提。** 新机环境不保证已装，**用之前先探测当前机器**：宿主 MCP 列表里有没有 `ghidra`，或对 `mcp_endpoints.ghidra.url` 探活。**没有就走 §2 的 `analyzeHeadless`**（本技能的主路径，不依赖任何 MCP）。

已注册且探活通的时候，按下述方式使用基于 PyGhidra 的 **streamable-http** MCP 服务：

- **传输形式**：常驻 HTTP 守护，端点 `http://127.0.0.1:9111/mcp`（受控口 9112）。
  改用 HTTP 而非 stdio 的原因：stdio 模式要给宿主每次启动加冷启（拉 Python + JVM + Ghidra），HTTP 守护可复用。
  **冷启与响应耗时随机器而变，用前现测，不要引用任何历史数字。**
- **启停（agent 自理，全程不需要用户改配置文件）**：
- **起**：`mcp_endpoints.ghidra.command` 给出的启动器（可带样本路径预导入）。**冷启耗时现测**；该启动器设计为幂等（已在跑时应快速返回）
  - **查**：对 `mcp_endpoints.ghidra.url`（`http://127.0.0.1:9111/mcp`）探活，期望 READY / `Tool Count : 20`
  - **停**：同一启动器的停止模式（内部先调 MCP `save` 保存工程，再释放端口）
  - **一行切换**：同一启动器的 `on|off` 模式
  - 工程目录由 `mcp_endpoints.ghidra.package_path` / 环境变量决定，落盘位置随安装而变，查注册表为准；服务没起时 `pi` 里该 server 会显示 failed —— 这是**启动状态**问题，不是配置错误，别去翻 json。
  - **以上四条都不许写死盘符**：端点表里没有就明说「本机无预置守护启动器」，改用 `analyzeHeadless`（见 §2）或让用户手工起服务，不要编一个 `C:\...` 路径。
- **核心工具（实测 20 个全可用）**：
  - `import_binary`：导入目标文件（异步排队，导入后名称形如 `/LicenceCheck.exe-ead7cd`，用 `list_project_binaries` 查真名再传 `binary_name`）
  - `decompile_function`：反编译指定名称或地址的函数
  - `search_symbols_by_name` / `search_code`：符号与反编译伪 C 检索
  - `list_imports` / `list_exports` / `list_xrefs`：导入表、导出表、交叉引用
  - `search_strings`（字符串索引未就绪时会要求稍后重试）、`read_bytes`、`disassemble`
  - `gen_callgraph`：MermaidJS 调用拓扑图
  - `list_project_binaries` / `list_project_binary_metadata` / `save` / `delete_project_binary`
  - `rename_function` / `rename_variable` / `set_variable_type` / `set_function_prototype` / `set_comment`
- **使用规范**：AI 优先直接调用上述 MCP 工具，全程无头，零 GUI 弹窗风险；不要用 stdio 手搓（会重复付冷启）。

### 2. 无头批量批处理：Headless CLI (analyzeHeadless)

适用于批量反编译、CI 自动化或离线脚本处理：

**必须遵守的避坑铁律**：
1. **预先建好 project 目录**：Ghidra analyzeHeadless 不会自动递归创建父目录，缺失会导致初始化报错退出。
2. **命令尾部必须追加 `< nul`**：Windows 批处理若遇内部错误会执行 `pause` 等待回车，导致模型同步阻塞卡死。追加 `< nul` 彻底切断输入挂死风险。

```bash
# Ghidra 安装根与工程目录都靠探测，不写死（下面第 4 行是 Windows 调用，其余为 POSIX shell）
GHIDRA_HOME=$(dirname "$(command -v ghidraRun)")   # 例如 <探测到的目录>/ghidra_12.0.2_PUBLIC
GHIDRA_PROJ="${GHIDRA_PROJ:-$PWD/ghidra_proj}"
mkdir -p "$GHIDRA_PROJ"

# analyzeHeadless 执行（尾部必须加 < nul）
cmd /c "$GHIDRA_HOME\support\analyzeHeadless.bat $GHIDRA_PROJ temp_proj -import sample.bin -postScript ExportDecomp.py < nul"
```

### 3. GUI 人工观察（ghidraRun）

- 图形启动器：`(Get-Command ghidraRun -ErrorAction SilentlyContinue).Source` 读到的路径（GUI，会弹窗；自动化一律用上面的 `analyzeHeadless`）
- **纪律约束**：禁止经 bash 自动化管道调用（会弹窗且不返回），仅限用户在桌面端手动双击打开进行复杂图形审查。

## 工具链

| 工具 | 用途 | 自举 |
|------|------|------|
| Ghidra | 反编译主工具 | 手动 release / 包管理器 |
| ghidra-mcp | AI 桥 | bootstrap 能力名 `ghidra-mcp` |
| ghidriff | 补丁差分 | 见 `patch-diff-exploit` |

## 参考

- `references/ghidra-cheatsheet.md`
- `../ida-reverse/` `../radare2/` `../binary-diff/`

## 路由上下文

**上游**: MASTER R22  
**下游**: 动态验证 → Frida/GDB；利用 → `pwn-chain`  
**同级**: `ida-reverse`（商业深挖）

## 任务完成自检

- [ ] 是否基于真实 Ghidra/`../TOOLS.md` 路径？
- [ ] 是否标注函数地址与重命名？
- [ ] 是否有可复现步骤？
- [ ] Checklist / journal？