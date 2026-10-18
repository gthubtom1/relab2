# IDA ↔ reverse-skill 对接（可移植）

本页是通用步骤，不含某台机器的绝对路径。本机就绪报告留在仓库根目录的 `LOCAL-READINESS.md`（本包未落地）（已 gitignore）。

## 目标形态

| 项 | 约定 |
|----|------|
| IDA 安装目录 | 环境变量 `IDADIR`（目录内有 `ida.exe` 或 `ida.dll`） |
| HTTP MCP | `http://127.0.0.1:13337/mcp` |
| 客户端服务器名 | 只留 **`idapro`**（不要同时注册 `ida-pro-mcp`） |
| 启动 | `scripts/start.ps1`（`--unsafe`，无 `?ext=dbg`） |
| 开库 | 大文件优先 `scripts/open.ps1`，不要经部分客户端直调 `idb_open` |

两个 MCP 名字指向同一 13337 会把工具注册两遍，并和 idalib worker 抢端口。

## 安装

```powershell
# ★ 先探测、再设 —— 不要凭印象填路径
powershell -NoProfile -ExecutionPolicy Bypass -Command ". '<技能包根>\skillpack\skills\scripts\lib\Bootstrap.ps1'; Resolve-ReverseToolSpec -Name 'idat'"
# 把返回的 Command 去掉末尾的 \idat.exe，那才是 IDADIR：
#   返回 <工具根>\disasm\IDA Pro <版本>\idat.exe  →  IDADIR = <工具根>\disasm\IDA Pro <版本>

setx IDADIR "<上面探测出来的目录>"

# start.ps1 的 IDADIR 解析顺序：env → User/Machine 持久变量 → 卸载表 → 常见根下一层的 IDA* 目录（版本无关）。
# 实测：清空 $env:IDADIR 后 start.ps1 仍解析到 D:\Tools\disasm\IDA Pro 9.3 并返回 OK:69:reuse。
# 所以 IDADIR 不是必须设；设它只是为了在多个 IDA 并存时指定用哪个。

# 必须用 mrexodia/ida-pro-mcp，不要装 PyPI 的 ida-mcp
python -m pip install "git+https://github.com/mrexodia/ida-pro-mcp.git"

# 激活 idalib（路径按本机 IDA 调整）
python "<IDADIR>\idalib\python\py-activate-idalib.py" -d "<IDADIR>"

# 装插件 + 客户端配置
python -m ida_pro_mcp --install --transport streamable-http --scope global
```

## 按需启动（★ 无后台常驻）

**没有任何计划任务、没有看门狗、没有开机自启。** 13337 平时就是关着的 —— 这是设计，不是故障。

`type: http` 的 MCP 条目不会代为拉起进程。**要用的时候自己起，用完让它自己退。**

| 脚本 | 作用 |
|------|------|
| `scripts/start.ps1` | **按需启动的唯一入口**。健康则 `OK:<n>:reuse` 并刷新 last-healthy；端口在听但 RPC 超时视为忙，**不杀**；只在无人监听、缺 `py_eval`、或 tools/list 连续失败超过 3 分钟（且无 `opening.lock`）时替换 managed supervisor；**永不杀 `ida.exe`** |
| `scripts/recover.ps1` | 立刻 `-Force` 重启 supervisor（不杀 `ida.exe`）。HTTP 客户端把 `idapro` 标成 error 时用这个 |
| `scripts/start-gui.ps1` | idalib license 失败时开 GUI 插件 |
| `scripts/open.ps1` | HTTP 直调 `idb_open`，绕过部分客户端 schema 校验 |

日志：`%LOCALAPPDATA%\reverse-skill\ida-mcp\supervisor.log`。

```powershell
# 用到 IDA 工具时才跑这一条 —— 它自己判断该起还是该复用
powershell -NoProfile -ExecutionPolicy Bypass -File "<技能包根>\skills\ida-reverse\scripts\start.ps1"
powershell -NoProfile -ExecutionPolicy Bypass -File "<技能包根>\skills\ida-reverse\scripts\open.ps1" -Path "C:\path\to\target.exe" -TimeoutSeconds 600
```

> ⚠️ **不要注册计划任务。** 曾经有过一个每分钟跑 `watchdog.ps1` 的保活任务
> （`reverse-skill-ida-mcp`），它会**每分钟弹一次 cmd 窗口**，且换机后必然指错路径。
> 已删除。**换机时第一件事是确认这台机器上也没有这种东西**：
> ```powershell
> Get-ScheduledTask | ? { ($_.Actions.Arguments + $_.Actions.Execute) -match 'relab2|ida-reverse|watchdog|reverse-skill' } | Select TaskName,State
> ```
> **输出应为空。** 见 `环境初始化.md` §11「换机适配面」。

GUI 占用 13337 但一时没回包时，`start.ps1` 输出 `WARN:gui_busy` 并退出，避免把正在分析的 IDA 干掉。

## 用完就关

IDA 分析做完了就放掉，别让它占着 13337 和几百 MB 内存：

```powershell
# 先 save 再释放，否则分析结果丢失
# 然后按 start.ps1 的同一入口停，不要另找方式 kill
```

`IDA` 是重型进程。**保持「用时起、用完退」**，不要为了「省一次启动」把它常驻 ——
常驻换来的是一台永远有残余进程的机器，而下一次会话根本不知道上一个实例是什么状态。

## 客户端

全部指向 Streamable HTTP：`http://127.0.0.1:13337/mcp`，服务器名 `idapro`。

改配置后必须新开会话。Cursor 在启动时若端口未监听，事后把服务拉起来也**不会自动重连**，需要在 MCP 面板手动刷新。

## 已知注意点

1. System32 文件：`open.ps1` 会复制到临时路径（输出带 `(temp copy)`）
2. `idb_open` 勿经部分客户端 MCP 直调
3. `start.ps1` 优先 `python -m ida_pro_mcp.idalib_supervisor`，比 `.cmd` 包装更稳
4. 正式安装与桌面便携包并存时，以 `IDADIR` 为准
5. 不要加 `?ext=dbg`（默认不暴露调试器工具）
