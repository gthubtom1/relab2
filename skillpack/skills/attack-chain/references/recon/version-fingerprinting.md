# 版本指纹识别

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/ctf-website/techniques/01-recon/version-fingerprinting.md`（GPL-3.0）。原 frontmatter 的 `mcp_tools` 映射已剔除——本技能包未挂载 `run_ctf_tool` / `http_probe`，改用本地工具链。
> **能力域**：本文为技术能力说明，按项目 `scope.md` 直接套用。
> **什么时候用**：命中「fingerprint / 版本识别 / Server header / favicon hash」这类信号时，把本文当打点清单读；命中即进「步骤」，命中不了就换主题。

## 适用信号

- fingerprint
- 版本识别
- Server header
- favicon hash
- JS framework
- Wappalyzer
- CVE lookup
- technology stack

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

1. 一句话原则
2. 置信度矩阵 — 指纹至少要两个独立来源交叉：例如 laravel_session + .env 路径 + composer.lock，或 JSESSIONID + Spring 错误栈 + /actuator。
3. 速查指纹矩阵
4. 锁文件探测
5. 从报错推断版本
6. Swagger/OpenAPI 暴露
7. 指纹 → CVE 联动
8. Wappalyzer 级指纹数据库
9. 快速扫描集成
10. 指纹归并与下一跳
11. 工作流 — 建立 HTTP baseline → 枚举路由/参数/版本信号 → 交叉验证指纹 → kb_router 选技术分支 → 最小 probe → 证据落盘。

## 判据

判据必须是外部可观测的（状态码、响应字段、差分、落盘文件），不是「命令有输出」。

- **输入信号** — Header、cookie、HTML meta、JS bundle、favicon、错误页出现产品或框架痕迹
- **输入信号** — `package-lock.json`, `composer.lock`, `go.sum`, `requirements.txt` 可读
- **输入信号** — API 文档、sourcemap、静态资源路径暴露版本号
- **输入信号** — 错误页包含栈帧、模块路径、依赖版本或默认主题
- **Evidence** — 保存 baseline 与单变量 probe 的完整请求、响应状态、关键响应头和正文摘要。
- **Evidence** — 将“响应差异”与服务端副作用分开记录；只有权限、状态、数据或 Flag 可重复变化才算确认。
- **Evidence** — 固定 session、输入、并发参数和时间窗口重放，记录成功响应、失败样本和下一跳。
- **Evidence** — 输出统一放入 `exports/ctf-website/<case>/`，凭据只用 `REDACTED` 占位，自动检索 `flag{}`、`CTF{}`、`DASCTF{}`。
- **Evidence** — `fingerprints.json`: source、product、version、confidence、raw evidence。
- **Evidence** — `fingerprint-next-hop.json`: 产品/版本、置信度、关联 CVE/KB 文档、复测结果。
- **Evidence** — 成功样本: 两个以上独立信号指向同一产品/版本，且对应端点/行为可复测。
- **Evidence** — 失败样本: Header 与应用行为冲突、静态资源缓存旧版本、CDN 默认错误页误导。

## 坑

- 探针命令在**未本机验证**时不要当成既定事实跑；先用探测层确认 `Available=True`。
- 噪声排除：先固定 baseline（同 URL 同 token 跑 3 次），再只改一个变量做差分。
- 不要把「状态码 200」当命中——WAF/缓存/软 404 都返回 200，命中判据要落到具体业务字段。

## 相关

- 见本技能 `../../SKILL.md` 的 references 索引。

## 技术正文

> 以下为原库正文（保留全部技术细节与脚本），仅移除原 `MCP 工具映射` 章节并重写跨文档链接。

## 一句话原则

> 不要信前端注释，信运行时行为。从 header → HTML → JS → 错误 → 文件 递进收束。

## 输入信号

- Header、cookie、HTML meta、JS bundle、favicon、错误页出现产品或框架痕迹
- `package-lock.json`, `composer.lock`, `go.sum`, `requirements.txt` 可读
- API 文档、sourcemap、静态资源路径暴露版本号
- 错误页包含栈帧、模块路径、依赖版本或默认主题

## 0. 置信度矩阵

| 证据 | 置信度 | 用法 | 失败样本 |
|------|--------|------|----------|
| lockfile / package manifest | 高 | 直接提依赖版本 | 构建产物不是当前部署 |
| 错误栈 module path | 高 | 精确框架/库版本 | 错误页被代理替换 |
| JS sourcemap | 高 | 还原源码和 API | sourcemap 过期 |
| favicon hash | 中 | 产品族识别 | 多产品共用默认图标 |
| Header `Server` | 中 | Web server 粗指纹 | CDN/反代覆盖 |
| HTML 注释/meta | 低 | 辅助线索 | 模板未更新 |
| Wappalyzer 单点命中 | 低 | 作为候选 | 同类前端库误判 |

指纹至少要两个独立来源交叉：例如 `laravel_session` + `.env` 路径 + `composer.lock`，或 `JSESSIONID` + Spring 错误栈 + `/actuator`。

## 速查指纹矩阵

```python
# fingerprinter.py — 一键收集所有指纹
import requests, hashlib, re

def fingerprint_all(target: str) -> dict:
    r = requests.get(target, timeout=10)
    results = {}

    # 1. HTTP Headers
    results["server"] = r.headers.get("Server", "")
    results["x_powered_by"] = r.headers.get("X-Powered-By", "")
    results["x_generator"] = r.headers.get("X-Generator", "")
    results["set_cookie"] = r.headers.get("Set-Cookie", "")

    # 2. HTML meta tags
    meta_gen = re.findall(r'<meta[^>]*name="generator"[^>]*content="([^"]*)"', r.text)
    results["generator_meta"] = meta_gen

    # 3. JS bundle 特征 (正则扫版本号)
    js_patterns = {
        "jquery": r'jQuery v(\d+\.\d+\.\d+)',
        "react": r'React v(\d+\.\d+\.\d+)',
        "vue": r'Vue\.js v(\d+\.\d+\.\d+)',
        "angular": r'Angular v(\d+\.\d+\.\d+)',
        "bootstrap": r'Bootstrap v(\d+\.\d+\.\d+)',
        "webpack": r'webpack v?(\d+\.\d+\.\d+)',
        "next": r'next@(\d+\.\d+\.\d+)',
        "nuxt": r'nuxt@(\d+\.\d+\.\d+)',
    }
    results["js_frameworks"] = {}
    for name, pat in js_patterns.items():
        m = re.search(pat, r.text)
        if m:
            results["js_frameworks"][name] = m.group(1)

    # 4. 静态文件 hash → 版本
    FAVICON_HASHES = {
        "b3c1cb2d4672b757886b2b56cbf5f3fa": "Apache Tomcat",
        "9c7e1d563d9c2a91e2e7e0b1f0c9a5e3": "Spring Boot (default)",
        "d41d8cd98f00b204e9800998ecf8427e": "Empty file (many)",
    }
    fav = requests.get(target + "/favicon.ico")
    if fav.status_code == 200:
        h = hashlib.md5(fav.content).hexdigest()
        results["favicon_hash"] = h
        if h in FAVICON_HASHES:
            results["favicon_product"] = FAVICON_HASHES[h]

    # 5. 错误页指纹
    r_err = requests.get(target + "/nonexistent_404_test", allow_redirects=False)
    results["404_status"] = r_err.status_code
    results["404_server"] = r_err.headers.get("Server", "")

    return results
```

## 锁文件探测

```python
# 常见版本锁文件
LOCK_FILES = [
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "composer.lock", "Gemfile.lock", "Pipfile.lock",
    "poetry.lock", "requirements.txt", "go.sum",
    "Cargo.lock", "pubspec.lock", "packages.lock.json",
    ".npmrc", ".yarnrc",
]

def probe_lock_files(target: str):
    for lf in LOCK_FILES:
        r = requests.get(f"{target}/{lf}")
        if r.status_code == 200 and len(r.text) > 50:
            print(f"[!] Found: {lf} ({len(r.text)} bytes)")
            # 从 lock 文件解析版本
            if lf.endswith(".json"):
                try:
                    data = r.json()
                    deps = data.get("dependencies", {}) or data.get("packages", {})
                    for pkg, info in list(deps.items())[:10]:
                        ver = info if isinstance(info, str) else info.get("version", "?")
                        print(f"    {pkg}: {ver}")
                except: pass
```

## 从报错推断版本

```python
# 故意触发异常，从报错提取版本
ERROR_PROBES = [
    # Spring Boot
    ("/api/../admin", "actuator"),
    # Django
    ("/admin/login/?next=/x", "django"),
    # Laravel
    ("/nonexistent_route_404_test", "laravel"),
    # Express
    ("/%FF%FF", "express"),
    # Flask (debug)
    ("/console", "werkzeug"),
    # PHP
    ("/index.php/..%5c..%5c", "php"),
]

def error_fingerprint(target: str):
    for path, hint in ERROR_PROBES:
        r = requests.get(target + path)
        text = r.text[:2000]

        # 框架特征正则
        patterns = {
            "Spring Boot": r"org\.springframework",
            "Django": r"django\.(core|http|urls)",
            "Laravel": r"laravel|Illuminate\\",
            "Express": r"at .*?node_modules/express",
            "Flask/Werkzeug": r"Werkzeug|werkzeug",
            "PHP": r"PHP (Fatal|Warning|Parse|Notice)",
            "Tomcat": r"Apache Tomcat/([\d.]+)",
            "Jetty": r"Jetty\(([\d.]+)",
            "Struts": r"struts2|org\.apache\.struts",
            "Thymeleaf": r"org\.thymeleaf",
        }
        for fw, pat in patterns.items():
            m = re.search(pat, text, re.I)
            if m:
                print(f"  {path}: {fw} → {m.group(0)[:80]}")

        # 精确版本号提取
        versions = re.findall(r'([\w.-]+)[/ ](\d+\.\d+\.\d+)', text)
        for name, ver in versions[:5]:
            print(f"    {name}: {ver}")
```

## Swagger/OpenAPI 暴露

```bash
# 常见 API 文档路径
for path in /swagger-ui.html /api-docs /v2/api-docs /v3/api-docs \
  /api/swagger /openapi.json /api/openapi.json /swagger.json \
  /docs /api/docs /redoc /api/redoc; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "$TARGET$path")
  [[ $code == "200" ]] && echo "[!] $path ($code)"
done
```

## 指纹 → CVE 联动

```bash
# 拿到产品和版本后，直接查 CVE
python scripts/ctf-website/cve_lookup.py --product "spring-boot" --version "2.7.0"
python scripts/ctf-website/cve_lookup.py --product "django" --version "4.1"
```

## Wappalyzer 级指纹数据库

```python
# 扩充指纹 — 按响应特征匹配
WAPP_FINGERPRINTS = {
    # Cookie 特征
    "JSESSIONID":            "Java (Tomcat/Jetty/Spring)",
    "PHPSESSID":             "PHP",
    "laravel_session":       "Laravel",
    "csrftoken":             "Django",
    "ASP.NET_SessionId":     "ASP.NET",
    "_rails_session":        "Ruby on Rails",
    "PLAY_SESSION":          "Play Framework (Scala/Java)",
    "ring-session":          "Ring/Clojure",
    # HTML meta
    '<meta name="generator" content="WordPress': "WordPress",
    '<meta name="generator" content="Drupal': "Drupal",
    '<meta name="generator" content="Joomla': "Joomla",
    # JS 全局变量
    "window.__NEXT_DATA__":  "Next.js",
    "window.__NUXT__":       "Nuxt.js",
    "window.__INITIAL_STATE__": "Vue SSR / Nuxt",
    "ReactDOM.render":       "React (SPA)",
    "angular.module":        "AngularJS",
    "ng-version":            "Angular",
    # 文件路径
    "/wp-content/":          "WordPress",
    "/sites/default/":       "Drupal",
    "/static/version":       "Magento",
    "/skin/frontend/":       "Magento",
    "/shopify/":             "Shopify",
}
```

## 快速扫描集成

```bash
# 一键指纹收集
python3 fingerprinter.py https://target.com > fingerprints.json

# nuclei 模板扫描
nuclei -u https://target.com -t technologies/ -o tech_report.json

# whatweb 批量
whatweb https://target.com -a 3 --log-json=whatweb.json

# wappalyzer CLI
wappalyzer https://target.com

# 从 JS bundle 提取依赖
curl -s https://target.com/main.js | grep -oP '"[^"]+"' | grep -E '^"[@a-z]' | sort -u
```

## 指纹归并与下一跳

```python
import json
import re
from collections import defaultdict

NEXT_HOP = {
    "Laravel": ["04-config-exposure", "payment-php", "deserialization"],
    "Spring": ["ssti", "grpc-protobuf", "kubernetes-container"],
    "WordPress": ["payment-php", "file-upload-xxe-lfi"],
    "Magento": ["payment-php", "graphql"],
    "Redis": ["03-nosql-injection", "ssrf"],
    "phpMyAdmin": ["04-config-exposure", "01-sqli-fundamentals"],
}

def merge_fingerprints(items):
    scores = defaultdict(int)
    evidence = defaultdict(list)
    for item in items:
        src = item.get("source", "")
        text = json.dumps(item, ensure_ascii=False)
        weight = 3 if re.search(r"lock|error|sourcemap", src, re.I) else 1
        for product in NEXT_HOP:
            if re.search(product, text, re.I):
                scores[product] += weight
                evidence[product].append(item)
    return [
        {"product": p, "score": s, "next": NEXT_HOP[p], "evidence": evidence[p][:3]}
        for p, s in sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    ]
```

## 工作流

建立 HTTP baseline → 枚举路由/参数/版本信号 → 交叉验证指纹 → `kb_router` 选技术分支 → 最小 probe → 证据落盘。


## Evidence

- 保存 baseline 与单变量 probe 的完整请求、响应状态、关键响应头和正文摘要。
- 将“响应差异”与服务端副作用分开记录；只有权限、状态、数据或 Flag 可重复变化才算确认。
- 固定 session、输入、并发参数和时间窗口重放，记录成功响应、失败样本和下一跳。
- 输出统一放入 `exports/ctf-website/<case>/`，凭据只用 `REDACTED` 占位，自动检索 `flag{}`、`CTF{}`、`DASCTF{}`。
- `fingerprints.json`: source、product、version、confidence、raw evidence。
- `fingerprint-next-hop.json`: 产品/版本、置信度、关联 CVE/KB 文档、复测结果。
- 成功样本: 两个以上独立信号指向同一产品/版本，且对应端点/行为可复测。
- 失败样本: Header 与应用行为冲突、静态资源缓存旧版本、CDN 默认错误页误导。
