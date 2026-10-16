# REA（rea-agents）接入实测记录

> 2026-10-16 · 本机 Windows 10.0.18363 x64 · Node v22.23.3 · npm 10.9.9
>
> 一句话结论：**REA 已真装进本机（npm 全局，6.5.0），它的 MCP stdio 服务器在本机起得来、
> `tools/list` 返回 207 个工具 + 6 个 prompt、`tools/call` 真能跑出带 Evidence 的结果。**
> 但**原生二进制反编译这一路在本机不可用** —— 它要外部 provider（Ghidra 12.1.x / IDA / Hopper），
> 三个都没配；本机现成的 Ghidra 是 12.0.2，**版本不够**。

本文件的每一条都是**实跑输出**，不是照抄上游 README。原始返回落在 `%TEMP%` 旁的
烟雾输出目录（见 §3.6 的哈希），可原样重跑复核。

---

## 1. 安装（实际命令 + 输出）

```text
$ npm i -g rea-agents
npm warn deprecated prebuild-install@7.1.3: No longer maintained. Please contact the author of the relevant native addon; alternatives are available.

added 147 packages in 60s
```

```text
$ npm ls -g rea-agents
D:\Tools\runtime\node\node-v22.23.3-win-x64
└── rea-agents@6.5.0
```

- 落点：`D:\Tools\runtime\node\node-v22.23.3-win-x64\node_modules\rea-agents`
  （本机 npm 前缀 = node 目录，`npm prefix -g` 同时给出 `node.exe` 与 `rea.cmd`）
- 包元数据（读 `<落点>\package.json`）：`name=rea-agents` `version=6.5.0` `license=MIT`
  `bin={"rea":"scripts/rea.mjs","rea-agents":"scripts/rea.mjs"}`
  `engines={"node":"^22.19.0 || ^24.11.0 || >=26.0.0"}` → 本机 `v22.23.3` **满足**
- 版本自证：`D:\Tools\runtime\node\node-v22.23.3-win-x64\rea.cmd --version` → `6.5.0`
- ★ **坑（记下来，换机必踩）**：装出来的 `rea.cmd` 在 **node 目录**里，而本机 `PATH` 指向的是
  `D:\Tools\cli`（一堆 .cmd shim 的目录）→ **`where rea` 找不到**，`rea` 不是一条能直接敲的命令。
  所以登记进宿主时**不能写裸 `rea`**，要写绝对路径（见 §5）。

没走成但没必要的路：`git clone` / codeload 曾被报告超时（历史上）；本次**全程只用 npm ，
一次装成**，未动用 `gh api` 拉源码 + `npm ci` 的备用路线。

---

## 2. MCP 启动方式（命令 + 参数 + env）

### 2.1 服务器就是一条子命令

```text
$ rea --help | grep -i mcp
  mcp          Register as MCP server (add, doctor)
  --mcp                               Start as MCP stdio server

$ rea mcp --help
rea mcp — Register as MCP server
Usage: rea mcp <command>
Commands:
  add     Register as MCP server
  doctor  Validate MCP server startup and tool listing
```

★ 这里有个**容易看岔**的地方：`rea mcp --help` 只列了 `add` / `doctor` 两个**子命令**，
**没有列「什么都不带」**——但官方 MCP Registry 条目写的就是 `npx -y rea-agents@<version> mcp`，
即 `mcp` 后面**不带子命令**时自己就是那条 stdio 服务器。本机实测证实（§3 起得来且回包）。

### 2.2 三种等价启动形态

| 形态 | 命令 | 本机是否用 |
|---|---|---|
| 官方 registry（包运行器） | `npx -y rea-agents@6.5.0 mcp`（Windows 上官方建议包一层 `cmd.exe /d /c`） | 否 —— 依赖网络/缓存与 PATH |
| 全局 bin shim | `<node 目录>\rea.cmd mcp` | 否 —— `rea` 不在 PATH（§1 的坑） |
| **直连解释器** | `<node.exe> <rea-agents>\scripts\rea.mjs mcp` | ★ **是** —— 写进宿主的形态 |

### 2.3 必需 env：**没有**

本机以 `env=None`（干净继承父进程环境）起服务器，`initialize` / `tools/list` / `tools/call`
全部正常。**空环境即可**，没有「必需 env」。

可选的调优环境变量（上游文档，均**未设**）：`REA_MCP_INPUT_SCHEMA_PROFILE`、
`REA_MCP_OUTPUT_SCHEMA_PROFILE`、`REA_MCP_MAX_RESPONSE_BYTES`。§5 的注册条目会**保留**宿主
已有配置里这些 `REA_*` 覆盖，不会被覆盖掉。

### 2.4 ★ 为什么直连 node.exe 而不是 .cmd

Windows 实测（本机）：

```text
$ python -c "import subprocess; subprocess.run(['npm','root','-g'])"
FileNotFoundError [WinError 2] 系统找不到指定的文件。
```

CreateProcess **不能直接起 `.cmd`**（`D:\Tools\cli\npm.cmd` 就是这样被打回的）。
两种正解：包一层 `cmd.exe /d /c ...`，或**直连解释器**。宿主 spawn 一条 stdio 服务器时，
后者才是稳的 —— 安静、无 shell、无 PATH 依赖。

---

## 3. 跑通一次真实调用（原始返回）

烟雾脚本：`skillpack/skills/references/rea-mcp-smoke.py`（新文件）。
它用**官方 `mcp` Python SDK**（本机 `mcp==1.30.0`）的 `stdio_client` 起服务器，
跑 `tools/list` + 一次 `tools/call`，把**原始返回**写盘。用法：

```text
python skillpack/skills/references/rea-mcp-smoke.py --out-dir <目录> \
    [--node <node.exe>] [--rea-mjs <rea.mjs>] [--tool <工具名>] [--args '<JSON>']
```

### 3.1 `initialize`（原始）

```json
{
  "serverInfo": { "name": "rea", "title": null, "version": "6.5.0",
                  "websiteUrl": null, "icons": null },
  "protocolVersion": "2025-11-25",
  "capabilities": ["completions", "prompts", "tools"]
}
```

### 3.2 `tools/list`（原始摘要）

```text
== tools/list == count=207
first20: ["annotate_native_function","inspect_native_load_image","inspect_native_data_type",
 "inspect_native_instruction","resolve_native_call_targets","address_name","comment",
 "current_address","current_procedure","current_document","goto_address","inline_comment",
 "list_bookmarks","list_documents","list_names","list_procedures","list_segments",
 "list_strings","next_address","prev_address"]
```

- **207 个工具**（全名 + 每个工具的描述 + `inputSchema` 落在 `<out-dir>/tools-list.json`）。
- `prompts/list` = **6 个**：`investigate_feature`、`compare_application_versions`、
  `verify_reconstruction`、`trace_crash`、`audit_residual_unknowns`、`prepare_bounded_process_capture`。

REA 自带的同一件事（`rea mcp doctor`，原始）：

```text
healthy: true
adapter: production-stdio
server:
  name: rea
  version: 6.5.0
  protocol_version: 2025-11-25
inventory:
  tools:
    expected: 207
    observed: 207
    missing: []
    unexpected: []
    duplicates: []
  prompts:
    expected: 6
    observed: 6
    missing: []
    unexpected: []
    duplicates: []
identity:
  expected_package_version: 6.5.0
  observed_package_version: 6.5.0
  expected_catalog_digest: 405725e736ec8dc8483435b970acbf20f9f26b9f1fd25203b992f5ab4cd2a4f4
  observed_catalog_digest: 405725e736ec8dc8483435b970acbf20f9f26b9f1fd25203b992f5ab4cd2a4f4
request_flow:
  tool: binary_session
  ok: true
checks[5]{name,ok,detail}:
  initialize,true,rea@6.5.0; protocol=2025-11-25
  "inventory:tools",true,expected=207 observed=207 missing=none unexpected=none duplicates=none
  "inventory:prompts",true,expected=6 observed=6 missing=none unexpected=none duplicates=none
  server-identity,true,package=6.5.0; catalog=405725e736ec8dc8483435b970acbf20f9f26b9f1fd25203b992f5ab4cd2a4f4
  request-flow,true,binary_session target-free request
diagnostics:
  stderr: ""
  stderr_bytes: 0
  stderr_truncated: false
```

（该输出落盘 `rea mcp doctor > rea-doctor.txt`，SHA-256
`13ecf2c7434d3da835285bf44a76cf5f53251025396eb838b7600a9886eb619e`，可原样重跑比对。）

### 3.3 `tools/call` ①：`binary_session`（成功，目标无关）

请求：`tools/call name="binary_session" arguments={}` — 原始返回（截断展示，完整见
`<out-dir>/call-binary_session.json`）：

```json
{
  "meta": { "provenance": { "untrusted_content": true, "source": "analysis_target" } },
  "content": [ { "type": "text", "text": "{\"result\":{\"open\":false,\"capabilities\":[…]" } ],
  "structuredContent": null,
  "isError": false
}
```

`text` 解出来的关键内容（同一份原始返回内）：

```json
{ "open": false,
  "server_identity": {
    "package": { "name": "rea-agents", "version": "6.5.0",
                 "root_path": "D:\\Tools\\runtime\\node\\node-v22.23.3-win-x64\\node_modules\\rea-agents",
                 "build_commit": null },
    "server":  { "name": "rea", "version": "6.5.0",
                 "command_path": "…\\rea-agents\\scripts\\rea.mjs" },
    "sdk": { "server": "2.3.1", "client_test": "2.3.1", "core": "2.3.1" },
    "negotiated_protocol_version": "2025-11-25",
    "catalog": { "counts": { "cli_commands": 153, "mcp_tools": 207, "mcp_prompts": 6 },
                 "digests": { "combined_sha256": "405725e736ec8dc8483435b970acbf20f9f26b9f1fd25203b992f5ab4cd2a4f4" } }
  },
  "analysis_provider_binding": null,
  "analysis_provider_candidates": [
    { "provider": { "id": "ghidra", "name": "Ghidra" },
      "availability": { "status": "unavailable", "code": "not_configured",
        "reason": "Set GHIDRA_INSTALL_DIR to an extracted Ghidra 12.1.x release directory." } },
    { "provider": { "id": "hopper", "name": "Hopper" },
      "availability": { "status": "unavailable", "code": "unsupported_host",
        "reason": "Hopper integration is not supported on win32." } },
    { "provider": { "id": "ida", "name": "IDA" },
      "availability": { "status": "unavailable", "code": "not_configured",
        "reason": "Set REA_IDA_MCP_CONFIG to an upstream IDA MCP JSON registration." } }
  ]
}
```

`server_identity.catalog.digests.combined_sha256` 与 `rea mcp doctor` 报的
`catalog_digest` **一字不差** —— 两条独立通道互相印证同一个目录。

### 3.4 `tools/call` ②：`inspect_pe_resources`（成功，真出 Evidence）

请求：`{"path":"C:\\Windows\\System32\\notepad.exe"}` — 原始返回（截断）：

```json
{
  "meta": { "provenance": { "untrusted_content": true, "source": "analysis_target" } },
  "content": [ { "type": "text", "text": "{\"evidence_id\":\"ev_44c53af6c8eeaccf8f2bc1b0648be961fe6cc108879f847565c81b6ccdfbdfab\",\"subject\":{\"name\":\"notepad.exe\",\"digest\":{\"sha256\":\"40a4597b73c6b5a42e72ff9ddc4828aa861bb656f23a491096b68625841a8503\"},\"local_path\":\"C:\\\\Windows\\\\System32\\\\notepad.exe\",\"format\":\"pe\",\"architecture\":null},\"provider\":{\"id\":\"rea-pe-resources\",\"name\":\"REA PE resource parser\",\"version\":\"1\"},\"predicate_type\":\"rea.analysis\",\"operation\":\"inspect_pe_resources\",…" } ],
  "structuredContent": null,
  "isError": false
}
```

`normalized_result`（同一份返回内）含 `artifact{path,sha256,bytes=181248}`、`format=pe32-plus`、
`machine=34404`、资源目录 `directories[]`、`resources[]`、`coverage`、`limitations` ——
即**一次真实的静态 PE 分析，产出带证据 ID 与目标哈希的 Evidence 记录**。

### 3.5 「诚实的失败」也要留证（边界）

不装样子：本机**没配 provider** 时，相关工具是**明确报错**、不是静默返回空。

```json
// tools/call list_architectures {}
{ "isError": true,
  "content": [ { "type": "text", "text": "{\"error\":{\"code\":\"target_unavailable\",\"category\":\"unavailable\",\"message\":\"No app is open. Ask the user which app to investigate, then call open_binary with its local path.\",\"retryable\":false}}" } ] }
```

```json
// tools/call inspect_binary_layout {"path":"C:\\Windows\\System32\\notepad.exe"}
{ "isError": true,
  "content": [ { "type": "text", "text": "{\"error\":{\"code\":\"capability_unavailable\",\"category\":\"unsupported_provider\",\"message\":\"The initial real-verified pwntools artifact profile supports Linux x64 only.\",\"details\":{\"provider_id\":\"pwntools-elf\",\"operation\":\"inspect_binary_layout\"}}}" } ] }
```

第二条直接点名 `provider_id=pwntools-elf`、只支持 Linux x64 —— 这就是「Windows 上原生
二进制布局/反编译走不通」的**原始证据**，不是推断。

### 3.6 返工可复核（字节稳定 + 哈希）

同一命令跑两遍，落盘原始返回**逐字节一致**（含 Evidence ID）：

| 文件 | SHA-256 |
|---|---|
| `tools-list.json` | `4d68f8691f6d1e0e5bc4302946e4a98d75100cb415a1bdb6fa01f04111b51953` |
| `call-inspect_pe_resources.json` | `4babcbc66e9f4272f0ee9171091ac30dc1d2a70acdafa636906301362d922706` |
| `summary.json` | `11eb5fca1b153f73e5228154fbb7bf4d7ac755acf557904189b0d09e31fc5fde` |

---

## 4. 能力矩阵：**本机真的能用什么、不能用什么（含原因）**

数据源：上面那次 `binary_session` 原始返回里的 `tool_availability.groups[]`
（76 组、207 个工具，逐组带 `available` 与 `reason`）。

**总账：30 组可用（77 个工具） / 46 组不可用（130 个工具）。**

不可用的四类原因（组数）：

| reason | 组数 | 含义 | 本机为什么 |
|---|---|---|---|
| `target_required` | 20 | 工具没问题，**得先 `open_binary` 一个目标** | 尚未开目标（不是装错） |
| `provider_missing` | 12 | 这类分析**要一个 REA 侧没装/没配的引擎** | 见下「不可用」表 |
| `provider_unavailable` | 8 | 引擎在，但**本机缺外部依赖** | adb / apktool / jadx / sqlite 等没接上 |
| `unsupported_host` | 6 | **平台就不支持** | macOS 原生工具、Hopper（win32）、原生 UI 场景 |

### ✅ 本机**零 provider 即可用**（真能出结果）

- **静态 JS / Electron / Web**：`analyze_javascript_application`、`analyze_web_bundle`、
  `export_web_scripts`、`inspect_web_network_capture`、`trace_web_module_imports`、
  `trace_web_source_location`、`capture_browser_scenario`、`capture_electron_scenario`、
  `inspect_electron_page`、`inspect_electron_fuses`、`observe_javascript_runtime` …
- **.NET 托管静态**（`rea-dotnet-static`，3/3 组可用）：`inspect_managed_artifact`、
  `inspect_managed_members`、`inspect_managed_native_boundaries`。
- **产物/结构静态解析**（`rea-artifact-graph`，2/3 组可用）：`extract_artifact`、
  `inspect_artifact`、`decode_interface_builder`、`inspect_keyed_archive`、`trace_dylib_resolution`。
- **PE 静态**：`inspect_pe_resources`（§3.4 实测成功）。
- **Go / Rust 二进制指纹**：`inspect_go_binary`、`inspect_rust_binary`。
- **Flutter/Dart**：`identify_flutter_build`、`inspect_dart_aot`。
- **抓包文件**：`inspect_pcap_capture`、`inspect_pcap_client`。
- **Frida 运行时**：`list_frida_devices`、`list_frida_processes`、`start_frida_session`、
  `instrument_with_frida`、`load_frida_script` …（本机组可用）。
- **Evidence 模型本身**：`get_evidence_bundle`、`list_unknowns`、`record_unknown`、
  `export_evidence_bundle`、`evaluate_reconstruction_coverage`、`binary_session`、
  `open_binary`、`close_binary`、比较/版本差异一组。

### ❌ 本机不可用（含**原始原因**）

| 能力 | 原因（REA 原话 / 代码） |
|---|---|
| **原生二进制反编译/布局**（`decompile`、`analyze_function`、`inspect_binary_layout`、`inspect_native_*`、xrefs…） | provider 全缺：`ghidra` → `not_configured`「Set `GHIDRA_INSTALL_DIR` to an extracted **Ghidra 12.1.x** release directory」；`hopper` → `unsupported_host`「Hopper integration is **not supported on win32**」；`ida` → `not_configured`「Set `REA_IDA_MCP_CONFIG`…」。另 `inspect_binary_layout` 实测落到 `pwntools-elf`（Linux x64 only）。**本机现成 Ghidra 是 12.0.2，版本不够**，这是本次不可用的**主因**。 |
| Android（`inspect_android_*`、`decode_android_resources`、`install_adb_package`…） | `provider_missing` / `provider_unavailable`：需**调用方自带 JADX / Apktool / adb**，本机没接到 REA 上。 |
| 固件（`extract_firmware`、`inspect_firmware_regions`） | `provider_missing`：Binwalk / Unblob **只在 Linux**。 |
| 信号/SDR（`decode_signal_recording`…） | `provider_missing`：需调用方自带 sigrok。 |
| JEB（`list_jeb_units`…） | `provider_missing`：需调用方起 JEB 并给 `REA_JEB_MCP_URL`。 |
| WASM / EVM / SQLite / 通用 packet | `provider_missing` / `provider_unavailable`。 |
| macOS 原生工具（`inspect_macho`、`inspect_plist`、`inspect_signature`、`demangle_swift`、`list_architectures`） | `unsupported_host`：需 macOS/Xcode。 |
| 原生 UI 场景 / 进程捕获（`capture_native_ui_scenario`、`capture_process_scenario`、`observe_native_ui`） | `unsupported_host`。 |
| `inspect_asset_catalog` | `unsupported_host`：需 macOS `assetutil`。 |

---

## 5. 接进本仓：`register-mcp.py` 的第 6 条通道

改动**只加不动逻辑**（新函数 + 一个新分支），文件：`skillpack/skills/scripts/register-mcp.py`。

- 新增 `find_rea_entry()`：先 `cmd.exe /d /c npm root -g` 拿全局根 → 认
  `<root>/rea-agents/scripts/rea.mjs` → 取同级 `node.exe`（或 `REA_NODE`）→
  **`--version` 实跑验真**（`6.5.0`）→ 返回
  `{"command":"<node.exe>","args":["<rea.mjs>","mcp"]}`；任一步不成立就返回 `None`。
- `build_entries()` 末尾加 ⑥ 分支：`find_rea_entry()` 有值才登记（并**保留宿主已有的 `REA_*` env 覆盖**）；
  没值则 `notes.append("rea：找不到 node.exe + rea-agents/scripts/rea.mjs —— 跳过（没装：npm i -g rea-agents）")`
  —— 与既有「找不到就跳过并报出来」的约定一致。
- 顺带把 3 处「5 条」的**文案**改成「6 条」（docstring / argparse description），
  并补了一段指向本文件的说明。**没有**改任何别的分支逻辑。

`--dry-run` 实测输出：

```text
$ python skillpack/skills/scripts/register-mcp.py --skill-root C:/relab2 --dry-run
=== 注册 MCP 通道（宿主 omp）===
  技能包根 C:\relab2
  工具根   D:\Tools
    · pyghidra-mcp
    · angr-mcp
    · relab2-tools
    · idapro
    · x64dbg-mcp
    · rea
  [干跑] C:\Users\Administrator\.omp\agent\mcp.json 将更新：['rea']
```

`--json` 实测输出：

```json
{"entries": ["pyghidra-mcp", "angr-mcp", "relab2-tools", "idapro", "x64dbg-mcp", "rea"], "notes": []}
```

宿主现状（**未改**）：`C:\Users\Administrator\.omp\agent\mcp.json` 的 `mcpServers`
= `[pyghidra-mcp, x64dbg-mcp, idapro, angr-mcp, relab2-tools]`，**还没有 `rea`**。
干跑显示「只差 rea 一条」，真要写就一条命令（**本任务只要求干跑，未执行真写**）：

```text
python skillpack/skills/scripts/register-mcp.py --skill-root C:/relab2
```

★ 写之前要想清楚的一点：这是 **+207 个工具**的通道，宿主每次会话都会有这 207 个工具常驻
上下文 —— 属**宿主预算决策**，不是技术能不能的问题。

### 新增/改动的文件

| 文件 | 动作 |
|---|---|
| `skillpack/skills/scripts/register-mcp.py` | **改**：+`find_rea_entry()`、+`_run_capture()`、+⑥ 分支、文案 5→6 条 |
| `skillpack/skills/references/rea-integration.md` | **新**：本文件 |
| `skillpack/skills/references/rea-mcp-smoke.py` | **新**：MCP stdio 烟雾脚本（§3） |

---

## 6. 没做到 / 卡在哪（如实）

1. **宿主 `mcp.json` 没真写 `rea`**。任务只要求「加条目 + 确认 `--dry-run` 不报错」，
   没要求改宿主配置；而且写进去 = 宿主常驻 +207 工具，属预算决策。干跑已证明**只差这一条**。
   可复核：现在读 `mcpServers` 仍无 `rea`。
2. **原生二进制分析（decompile / 函数 / xref / layout）在本机不可用**。卡点明确、不是配置手误：
   REA 要 **Ghidra 12.1.x**（本机 12.0.2，不够），Hopper **win32 不支持**，IDA 未配
   `REA_IDA_MCP_CONFIG`。要打通，得先落一份 12.1.x 并设 `GHIDRA_INSTALL_DIR`（**本次未做**）。
3. **Android / 固件 / SDR / JEB / WASM / SQLite 不可用** —— 都要调用方自带外部工具并接到 REA 上，
   本次没接。原因已在 §4 逐条列出（含 REA 原始 `reason`）。
4. **没做**：`rea setup`（会改宿主 agent 配置 + 可能装 Hopper，属有副作用的外部动作，未获明确授权）；
   `npx` 形态未单独验证（改用直连 node.exe，理由见 §2.4）。
5. `npm i -g` 期间只有一条 `prebuild-install@7.1.3` 弃用告警，**无其它错误**。
