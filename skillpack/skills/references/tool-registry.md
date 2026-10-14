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
| `idapro` | streamable-http | `127.0.0.1:13337/mcp` | IDA GUI 内插件 | **按需**：用到时跑 `<技能包根>\skills\ida-reverse\scripts\start.ps1`，健康则复用、没人听才起。**没有常驻、没有计划任务**；多实例端口递增，以 Output 窗口 `[MCP] port=` 日志为准 |
| `pyghidra-mcp` | stdio（本机 omp）或 streamable-http | stdio 无端点；HTTP 形态 `127.0.0.1:9111/mcp` | **JDK 21** + Ghidra 本体 | **按需**：stdio 由宿主按会话拉起；HTTP 形态冷启 7–10 s。**不要设成常驻服务** |
| `x64dbg-mcp` | http（`.dp64`/`.dp32` 插件） | x64=`127.0.0.1:9094`，x32=`127.0.0.1:9095` | x64dbg + 插件 + Bearer token | **按需**：插件活在被调试进程里，进程不在端口就不在。拉起方式见该技能自己的文档 |
| `relab2-tools` | stdio | — | Python（`mcp` SDK） | **宿主按会话自动拉起**。把**本机工具链**暴露给模型：`local_tools`（实时清单）/ `run_tool`（按 id 调工具，路径走探测层）/ `triage_target` / `find_capability`（按能力找工具）。实现见 `skills/scripts/relab2-tools-mcp.py` |

> **★ 上表是「通道本体」。本包出厂时**把 `idapro` 与 `x64dbg-mcp` 注册成
> **stdio·懒启动代理**（`skills/scripts/mcp-lazy-http.py`）—— 这是为了治「模型不主动按开关」的病：
> 代理让**工具常驻可见**，而**后端只在被调用时才由代理拉起**，所以那两个通道**不需要人先起服务**。
> 代理自身是 stdio，宿主按会话拉起；它 args 里那个 `http://…` 只是**它要去拉起的后端端点**。
> 换机后要改的是 args 里的 `--launcher` 路径与（x64dbg 的）Bearer token，**不是**去改通道形态。
> **怎么验**：`relab2.ps1 doctor`，或单跑 `powershell -File skills/scripts/mcp-status.ps1`
> （后者会把这两条报成 `stdio·懒启`）。

> **★ 全部按需。** 本包**不注册任何计划任务、不装任何看门狗、不做开机自启**。
> 端口平时关着是**设计**，不是故障。理由：常驻保活会①每分钟弹 cmd 窗口 ②换机后必然指错路径 ③
> 让「这个服务是本次会话起的还是上次留下的」变得无法回答。
> 换机后第一件事：确认新机器上也没有这类东西 ——
> `Get-ScheduledTask | ? { ($_.Actions.Arguments + $_.Actions.Execute) -match 'relab2|ida-reverse|watchdog|reverse-skill' }`
> （**按 Action 查，别按名字查**：`-match 'ida'` 会误命中 Windows 自带的 `License Validation`）。

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
- **全部按需。** 用到才起，用完就停。**绝不**注册计划任务、看门狗、开机自启、常驻守护 ——
  这类东西会把「本会话起的」和「上次留下的」混成一团，换机后还会指错路径。
- 收尾要停服务时，用**同一个启动入口**停，不要另找方式 kill。
- Ghidra 类先 `save` 再释放端口，否则分析结果丢失。

---

## 6. 新增通道

1. 在 `skillpack/skills/scripts/bootstrap-manifest.json` 的 `capabilities` 里加一条（`mcpNames` / `mcpUrl` / `mcpCommand` / `mcpArgs`）。
2. 在 `../TOOLS.md` §7 或 §8 补一行人读说明。
3. 在**本文件**登记端点与依赖。

**不要**在本文件写「已装 / 未装 / 版本」—— 那是会腐烂的东西。