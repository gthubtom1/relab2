# Tool Registry —— MCP 通道登记模板

> **这份表不回答「工具有没有」，只回答「MCP 通道走哪里」。**
> 工具装没装、装在哪，一律现查：`. ..\..\scripts\lib\Bootstrap.ps1`（相对本文件走，不用写死绝对路径；万一这台机器还没建好、该文件不存在，改成从本文件上一级的 `..\skills\scripts\lib\Bootstrap.ps1`）→
> `Resolve-ReverseToolSpec -Name <id>`，读它的 `Command` / `Available` / `Via`。
> `../TOOLS.md` §0 是**装法说明书（机器无关），不含本机探测结果**，不得当本机路径用；
> 单条 `Get-Command` 只是四级探测里的第 2 级，返回空不等于缺工具（见 `env-selfcheck.md`）。
>
> **本文件不缓存本机状态。** 端口、状态列都是**待实测**，不是事实。
> 历史上这里写过某台机器的「已装 / 未装 / 端口 13337 已验证」—— 那正是它腐烂的原因，已删除。
>
> 规则：**端口/地址 MUST 来自实测或本表登记，不得猜。**

---

## 0. 使用方式

```powershell
# 1. 这个 MCP server 在当前宿主里注册了吗？
#    pi: mcp({search:"<名字>"})    其余宿主: 用其原生 MCP 工具列表

# 2. 注册了但服务起没起？（HTTP 型 MCP 全是按需启动）
Test-ReverseTcpPort -Port <端口>     # 1 秒超时，不阻塞

# 3. 没起 → 自己按 §2 的启动方式拉起，再探活；不要要求用户手改 mcp.json
```

**「注册」和「在监听」是两件事。** 多数 HTTP 型 MCP 是 cold start，表现为该 server `failed` 或探活超时 —— 这是正常状态，不是故障。

---

## 1. 逆向方向 MCP 通道

| 通道 | 协议 | 端点 | 依赖 | 启动方式 |
|---|---|---|---|---|
| `idalib-mcp` | stdio | — | **IDA 本体** + `IDADIR` 环境变量指向它 | pip 装完直接注册即可，无需起服务 |
| `idapro` | streamable-http | `127.0.0.1:13337/mcp` | IDA GUI 内插件 | 打开 IDA 加载文件后自动监听；多实例端口递增，以 Output 窗口 `[MCP] port=` 日志为准 |
| `pyghidra-mcp` | streamable-http | `127.0.0.1:9111/mcp` | **JDK 21+** + Ghidra 本体 | 常驻守护，冷启 7–10 s，幂等；探活应报 `STATE: READY` |
| `x64dbg-mcp` | http（`.dp64`/`.dp32` 插件） | x64=`127.0.0.1:9094`，x32=`127.0.0.1:9095` | x64dbg + 插件 + Bearer token | 随 x64dbg / headless 启动，插件活在被调试进程里 |

### 三条已知坑（实测，非推测）

| 坑 | 表现 | 处置 |
|---|---|---|
| `IDADIR` 未设置 | `idalib-mcp` 找不到 IDA 本体 | `(Get-Command ida).Source` 探测，取其所在目录赋给 `$env:IDADIR` |
| **9095 不是控制口** | 向 9095 发 STOP 无应答 | 9095 是 **x32 的服务口**。x64dbg 无独立控制口，别向它发指令 |
| deferred 被误读为故障 | 工具表显示 0/N listening | 正常。按需 `mcp({connect:"…"})` 拉起即可 |

---

## 2. 浏览器 / 抓包方向 MCP 通道

| 通道 | 协议 | 装法 | 备注 |
|---|---|---|---|
| `playwright-mcp` | stdio (npx) | `npx -y playwright-mcp` | 首次需 `npx playwright install chromium` |
| `chrome-devtools` | stdio (npx) | `npx -y chrome-devtools-mcp@latest` | DOM/网络/性能/断点 |
| `jshook` | stdio (npx) | `npx -y @jshookmcp/jshook` | 冷启动，按 domain 激活工具 |
| `reqable-mcp` | stdio (npx) | `npx -y reqable-mcp-server` | **需另装 Reqable 桌面端**，走它本地 API |
| `anything-analyzer` | local-http | `http://localhost:23816/mcp` | 本地 HTTP 服务，需起 `pnpm dev` |

> **零日志 ≠ 故障。** deferred 的 MCP 从未被 spawn 就是这样，不要因此退回裸开 exe。

---

## 3. 远程 MCP

| 通道 | 端点 | 备注 |
|---|---|---|
| `xquik` | `https://xquik.com/mcp` | 需 OAuth + 外网可达。token 过期即 401，重走 OAuth 即可 |

---

## 4. 通道坏了怎么处置（固定顺序）

1. **先看注册**：宿主工具表里有没有这个 server。
2. **再看监听**：`Test-ReverseTcpPort`（1 s 超时）。
3. **再按 §1/§2 起服务**，然后重探活。
4. **还不行 → 报出来**：写明「哪个 server、探了什么、返回什么、已试过什么」。
5. **绝不**：让用户手改 `mcp.json`、猜端口、换个工具名字硬试。

---

## 5. 启停纪律

- **启停由 agent 自己完成**，不甩给用户。
- 收尾要停服务时，用**同一个启动入口**停，不要另找方式 kill。
- Ghidra 类先 `save` 再释放端口，否则分析结果丢失。

---

## 6. 新增通道

1. 在 `skillpack/skills/scripts/bootstrap-manifest.json` 的 `capabilities` 里加一条（`mcpNames` / `mcpUrl` / `mcpCommand` / `mcpArgs`）。
2. 在 `../TOOLS.md` §7 或 §8 补一行人读说明。
3. 在**本文件**登记端点与依赖。

**不要**在本文件写「已装 / 未装 / 版本」—— 那是会腐烂的东西。