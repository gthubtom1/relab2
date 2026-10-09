# HTTP 请求头伪装

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/ctf-website/techniques/23-paywall-bypass/02-http-header-manipulation.md`（GPL-3.0）。原 frontmatter 的 `mcp_tools` 映射已剔除——本技能包未挂载 `run_ctf_tool` / `http_probe`，改用本地工具链。
> **授权范围**：仅限 CTF 靶场 / AWD 赛场 / 已签署授权的测试环境。任何真实第三方目标、真实凭据、真实支付/生产流量都禁止套用本文流程。
> **什么时候用**：命中「见适用信号」这类信号时，把本文当打点清单读；命中即进「步骤」，命中不了就换主题。

## 适用信号

本篇是清单/索引类文档，正文直接以条目给出打点项（见「技术正文」首节）：

- `curl -s -o /dev/null -w '%{size_download}' -H "User-Agent: Googlebot/2.1" URL` 响应体 > Chrome UA 响应体 2-10 倍
- Google Web Cache (`webcache.googleusercontent.com`) 中存在完整内容
- AMP 版本 (`<link rel="amphtml">`) 对 UA 敏感度低
- Cookie 中存在 `articleReads` / `meterCount` / `pw_session` 等计数器
- 响应头 `vary: User-Agent` → 确认服务器根据 UA 动态渲染
- 刷新页面后 Cookie 累积 → 阅读计数器递增
- 响应头 `x-cache: HIT` 出现在 CDN 层 → CDN 可能缓存了无 paywall 版本
- [01-paywall-detection-bypass](01-paywall-detection-bypass.md) — 平台指纹识别

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

1. **攻击链** — [01-paywall-detection-bypass](01-paywall-detection-bypass.md) — 平台指纹识别
2. **攻击链** — [03-network-rule-blocking](03-network-rule-blocking.md) — 脚本拦截
3. **攻击链** — [04-content-extraction](04-content-extraction.md) — 内容提取
4. **攻击链** — [js-runtime](../../../js-reverse/references/web-runtime/js-runtime.md) — JS 运行时 Hook

## 判据

判据必须是外部可观测的（状态码、响应字段、差分、落盘文件），不是「命令有输出」。

- **输入信号** — `curl -s -o /dev/null -w '%{size_download}' -H "User-Agent: Googlebot/2.1" URL` 响应体 > Chrome UA 响应体 2-10 倍
- **输入信号** — Google Web Cache (`webcache.googleusercontent.com`) 中存在完整内容
- **输入信号** — AMP 版本 (`<link rel="amphtml">`) 对 UA 敏感度低
- **输入信号** — Cookie 中存在 `articleReads` / `meterCount` / `pw_session` 等计数器
- **输入信号** — 响应头 `vary: User-Agent` → 确认服务器根据 UA 动态渲染
- **输入信号** — 刷新页面后 Cookie 累积 → 阅读计数器递增
- **输入信号** — 响应头 `x-cache: HIT` 出现在 CDN 层 → CDN 可能缓存了无 paywall 版本
- **Evidence** — 保存 baseline 与单变量 probe 的完整请求、响应状态、关键响应头和正文摘要。
- **Evidence** — 将“页面可见变化”与服务端内容授权分开记录；只有正文差分、状态变化或 Flag 可重复出现才算确认。
- **Evidence** — 固定浏览器 profile、UA、Cookie、Storage、脚本拦截规则和执行时序重放，记录成功响应、失败样本和下一跳。
- **Evidence** — 输出统一放入 `exports/ctf-website/<case>/`，凭据使用 `REDACTED` 占位并自动检索常见 Flag 格式。

## 坑

- 探针命令在**未本机验证**时不要当成既定事实跑；先用探测层确认 `Available=True`。
- 噪声排除：先固定 baseline（同 URL 同 token 跑 3 次），再只改一个变量做差分。
- 不要把「状态码 200」当命中——WAF/缓存/软 404 都返回 200，命中判据要落到具体业务字段。

## 相关

- 见本技能 `../../SKILL.md` 的 references 索引。

## 技术正文

> 以下为原库正文（保留全部技术细节与脚本），仅移除原 `MCP 工具映射` 章节并重写跨文档链接。

## 场景

许多 paywall 系统对搜索引擎爬虫完全放行——`User-Agent: Googlebot` 的请求直接返回无 paywall 的完整内容，这是 SEO 的必然结果。通过在请求级别（而非 DOM 级别）伪装 HTTP 头，使服务器将请求识别为 Googlebot / Bingbot / Facebook Crawler。

```
Chrome UA 请求:
  → 服务器: "未登录且无 seat 许可 → 返回截断 + paywall overlay"
  → 响应体: ~10KB (含遮罩层 DOM)

Googlebot UA 请求:
  → 服务器: "爬虫需要索引 → 返回完整内容"
  → 响应体: ~50KB (完整文章 HTML)
```

Chrome Extension 通过 Manifest V3 的 `declarativeNetRequest` API 在请求发出前修改头；外部脚本则通过 Python requests / curl 实现。

## 输入信号

- `curl -s -o /dev/null -w '%{size_download}' -H "User-Agent: Googlebot/2.1" URL` 响应体 > Chrome UA 响应体 2-10 倍
- Google Web Cache (`webcache.googleusercontent.com`) 中存在完整内容
- AMP 版本 (`<link rel="amphtml">`) 对 UA 敏感度低
- Cookie 中存在 `articleReads` / `meterCount` / `pw_session` 等计数器
- 响应头 `vary: User-Agent` → 确认服务器根据 UA 动态渲染
- 刷新页面后 Cookie 累积 → 阅读计数器递增
- 响应头 `x-cache: HIT` 出现在 CDN 层 → CDN 可能缓存了无 paywall 版本

---

## 方法 1: Chrome Extension declarativeNetRequest — modifyHeaders

### 原理

Manifest V3 的 `declarativeNetRequest.updateSessionRules()` 允许在**网络层**声明式修改请求头。规则生效早于任何页面 JS，比 content script 更底层。

### 架构

```
background.js (service worker)
  │
  ├─ sites.js → 读取站点配置
  │
  ├─ set_rules() → initSetRules() + 遍历启用的站点
  │    │
  │    └─ addRules(domain, rule)
  │         │
  │         ├─ rule.useragent        → modifyHeaders: UA + Referer + XFF
  │         ├─ rule.referer          → modifyHeaders: Referer
  │         ├─ rule.headers_custom   → modifyHeaders: 自定义 header
  │         ├─ rule.random_ip        → modifyHeaders: X-Forwarded-For
  │         ├─ rule.block_regex      → block: 阻止 paywall 脚本加载
  │         ├─ rule.block_js_inline  → modifyHeaders: CSP injection
  │         ├─ rule.allow_cookies    → 标记不清除 cookie
  │         └─ rule.amp_redirect     → redirect: AMP 版本跳转
  │
  └─ update_session_rules(sesRules, sesRuleIds) → 提交到浏览器
```

### 代码: 核心 header 规则构建

```javascript
// background.js — add_session_rule() 核心
function add_session_rule(domain, rule) {
  let header_rule = {};

  if (rule.useragent || rule.headers_custom || rule.referer || rule.referer_custom || rule.random_ip) {
    header_rule = {
      id: ++rule_id,
      priority: 1,
      action: {
        type: "modifyHeaders",
        requestHeaders: []
      },
      condition: {
        urlFilter: "||" + domain,
        resourceTypes: ["main_frame", "sub_frame", "xmlhttprequest", "script"]
      }
    };

    let mobile = navigator.userAgent.toLowerCase().includes('mobile');

    // 1. Cookie 清除
    if (!allow_cookies.includes(domain)) {
      header_rule.action.requestHeaders.push({
        header: "Cookie", operation: "set", value: ""
      });
    }

    // 2. User-Agent 伪装
    if (rule.useragent === 'googlebot') {
      let ua = mobile ? userAgentMobileG : userAgentDesktopG;
      header_rule.action.requestHeaders.push(
        { header: "User-Agent", operation: "set", value: ua },
        { header: "Referer", operation: "set", value: "https://www.google.com/" },
        { header: "X-Forwarded-For", operation: "set", value: "66.249.66.1" }
      );
    } else if (rule.useragent === 'bingbot') {
      let ua = mobile ? userAgentMobileB : userAgentDesktopB;
      header_rule.action.requestHeaders.push(
        { header: "User-Agent", operation: "set", value: ua }
      );
    } else if (rule.useragent === 'facebookbot') {
      header_rule.action.requestHeaders.push(
        { header: "User-Agent", operation: "set", value: userAgentDesktopF }
      );
    } else if (rule.useragent_custom) {
      header_rule.action.requestHeaders.push(
        { header: "User-Agent", operation: "set",
          value: use_useragent_custom_obj[domain] }
      );
    }

    // 3. 自定义 HTTP Header 注入
    if (rule.headers_custom) {
      for (let header in use_headers_custom_obj[domain]) {
        header_rule.action.requestHeaders.push({
          header: header, operation: "set",
          value: use_headers_custom_obj[domain][header]
        });
      }
    }

    // 4. Referer 伪装
    if (!rule.useragent) {
      if (rule.referer === 'google') {
        header_rule.action.requestHeaders.push(
          { header: "Referer", operation: "set", value: "https://www.google.com/" }
        );
      } else if (rule.referer === 'facebook') {
        header_rule.action.requestHeaders.push(
          { header: "Referer", operation: "set", value: "https://www.facebook.com/" }
        );
      } else if (rule.referer === 'twitter') {
        header_rule.action.requestHeaders.push(
          { header: "Referer", operation: "set", value: "https://t.co/" }
        );
      } else if (rule.referer_custom) {
        header_rule.action.requestHeaders.push(
          { header: "Referer", operation: "set",
            value: use_referer_custom_obj[domain] }
        );
      }
    }

    // 5. X-Forwarded-For IP 伪装
    if (rule.random_ip) {
      let val = rule.random_ip === 'eu' ? randomIP(185, 185) : randomIP();
      header_rule.action.requestHeaders.push(
        { header: "X-Forwarded-For", operation: "set", value: val }
      );
    }
  }

  if (header_rule.action.requestHeaders.length)
    push_session_rule(header_rule, rule_id);
}
```

### UA 字符串定义

```javascript
// background.js — 爬虫 UA 常量
const userAgentDesktopG = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)";
const userAgentMobileG  = "Chrome/137.0.7151.119 Mobile Safari/537.36 (compatible ; Googlebot/2.1 ; +http://www.google.com/bot.html)";
const userAgentDesktopB = "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)";
const userAgentMobileB  = "Chrome/137.0.7151.119 Mobile Safari/537.36 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)";
const userAgentDesktopF = 'facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)';
```

### 会话规则提交

```javascript
// 构建规则数组后一次性提交到浏览器内核
function update_session_rules(rules, rule_ids) {
  ext_api.declarativeNetRequest.updateSessionRules({
    addRules: rules,
    removeRuleIds: rule_ids
  });
}
```

---

## 方法 2: 站点规则声明式配置

### 原理

sites.js 中每个站点的绕过配置是声明式的 JSON-like 结构。扩展启动/站点变更时遍历这些配置生成对应的 network rules。

### 代码: sites.js 规则字段说明

```javascript
// sites.js 中每个站点的规则 schema:
{
  domain: "example.com",         // 站点域名
  group: ["a.com", "b.com"],    // 同组站点列表 (共享规则)
  allow_cookies: 1,              // 是否保留 Cookie (不清除)
  remove_cookies: 1,             // 页面加载后清除 Cookie (旧计数器)
  remove_cookies_select_drop: ["pw_counter", "meter"],  // 只删除指定的 Cookie
  remove_cookies_select_hold: ["session_id"],           // 保留这些，删除其余
  useragent: "googlebot",        // UA 伪装: googlebot | bingbot | facebookbot
  useragent_custom: "Custom/1.0",// 自定义 UA 字符串
  headers_custom: {              // 自定义 HTTP 头
    "X-Forwarded-Proto": "https"
  },
  referer: "google",             // Referer 伪装: google | facebook | twitter
  referer_custom: "https://t.co/",  // 自定义 Referer
  random_ip: 1,                  // 随机 XFF IP (1=全局, 'eu'=欧洲段)
  block_regex: /\.poool\.fr\//,  // 阻止匹配的 paywall 脚本
  block_regex_general: /\.piano\.io\//,  // 全局脚本阻止 (排除已禁站点)
  block_js: 1,                   // 阻止目标域的所有 JS
  block_js_ext: 1,               // 阻止外部 JS (允许同源)
  block_js_inline: /nytimes\.com\/.+\.html/,  // 内联 JS + CSP 放行
  amp_unhide: 1,                 // AMP 页面内容解除隐藏
  amp_redirect: "url_pattern",   // 重定向到 AMP 版本
  cs_all_frames: 1,              // content script 注入所有 iframe
  ld_json: "selector|key",       // JSON-LD 内容提取
  ld_json_next: "selector|key",  // Next.js __NEXT_DATA__ 提取
  ld_archive_is: "sel1|sel2",    // archive.is 内容获取
  add_ext_link: "selector|link", // 添加外部链接 (archive.is/Google)
}
```

### 典型配置示例

```javascript
// 示例 1: Googlebot UA 即足够
"Aftenposten.no": {
  domain: "aftenposten.no",
  allow_cookies: 1,
  useragent: "googlebot"
},

// 示例 2: Googlebot UA + Referer + 随机 IP
"Haaretz Group": {
  domain: "###_il_haaretz_group",
  group: ["haaretz.com", "haaretz.co.il", "themarker.com"],
  allow_cookies: 1,
  useragent: "googlebot",
  referer: "google",
  random_ip: 1
},

// 示例 3: 仅清除特定 Cookie (metered paywall)
"Ámbito": {
  domain: "ambito.com",
  remove_cookies_select_drop: ["TDNotesRead"]
},

// 示例 4: 脚本阻止 + Cookie 清除
"Adweek": {
  domain: "adweek.com",
  remove_cookies_select_drop: ["blaize_session"],
  block_regex: /\.adweek\.com\/wp-content\/plugins\/adw-zephr\//
},

// 示例 5: 自定义 Header + Fetch 拦截
"The Economist": {
  domain: "economist.com",
  allow_cookies: 1,
  useragent: "googlebot",
  referer: "google"
  // resourceTypes 额外包含: stylesheet, image, media
}
```

---

## 方法 3: Cookie 选择性清除

### 原理

Metered paywall 的阅读计数器一般存储在 Cookie 中。有时需要清除所有 Cookie 重置计数，有时只需删除特定键（因为其他 Cookie 包含登录态或 CSRF token）。

### 代码: Cookie 操作函数

```javascript
// background.js — 获取所有与 domain 相关的 cookie
function remove_cookies_fn(domain, after_load) {
  if (remove_cookies_select_drop[domain]) {
    // 模式 A: 只删除黑名单中的 cookie (drop list)
    let drop_list = remove_cookies_select_drop[domain];
    drop_list.forEach(name => {
      ext_api.cookies.remove({ url: 'https://' + domain + '/', name: name });
    });
  } else if (remove_cookies_select_hold[domain]) {
    // 模式 B: 保留白名单中的 cookie (hold list), 删除其余
    let hold_list = remove_cookies_select_hold[domain];
    ext_api.cookies.getAll({ domain: domain }, function(cookies) {
      cookies.forEach(cookie => {
        if (!hold_list.includes(cookie.name)) {
          ext_api.cookies.remove({
            url: 'https://' + domain + '/', name: cookie.name
          });
        }
      });
    });
  } else {
    // 模式 C: 无选择 → 交由 header_rule 的 Cookie: "" 处理
    // (在请求层清空，不修改存储)
  }
}
```

---

## 方法 4: Python/curl 外部脚本 — 完整请求伪装

### 原理

在非浏览器环境中，通过构造完整的 HTTP 请求头集合模拟 Googlebot。需要同时处理 UA、Referer、XFF、Accept-Language 和 Cookie Jar。

### 代码: Python 完整示例

```python
"""paywall_bypass_headers.py — 请求级别 Paywall 绕过"""
import requests
from random import randint, choice

# UA 变体库
UA_GOOGLEBOT_DESKTOP = (
    "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
)
UA_GOOGLEBOT_MOBILE = (
    "Chrome/137.0.7151.119 Mobile Safari/537.36 "
    "(compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
)
UA_BINGBOT = (
    "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)"
)
UA_FACEBOOK = "facebookexternalhit/1.1"

# Googlebot 常用 IP 段
GOOGLEBOT_IPS = [
    "66.249.66.1", "66.249.66.32", "66.249.66.64",
    "66.102.9.1", "66.102.9.32", "64.233.173.1",
]

def random_ip():
    """生成随机公网 IP (非私有段)"""
    while True:
        ip = f"{randint(1,255)}.{randint(0,255)}.{randint(0,255)}.{randint(1,254)}"
        # 排除私有段: 10.x, 172.16-31.x, 192.168.x, 127.x
        if not (ip.startswith(('10.', '172.16.', '172.17.', '172.18.',
                                '172.19.', '172.2', '172.30.', '172.31.',
                                '192.168.', '127.'))):
            return ip


def build_bypass_headers(
    ua: str = "googlebot_desktop",
    referer: str = "https://www.google.com/",
    xff: str = None,
) -> dict:
    """构造绕过 paywall 的完整 HTTP 请求头"""
    ua_map = {
        "googlebot_desktop": UA_GOOGLEBOT_DESKTOP,
        "googlebot_mobile": UA_GOOGLEBOT_MOBILE,
        "bingbot": UA_BINGBOT,
        "facebook": UA_FACEBOOK,
    }
    headers = {
        "User-Agent": ua_map.get(ua, ua),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Cache-Control": "no-cache",
        "DNT": "1",
        "Upgrade-Insecure-Requests": "1",
    }
    if referer:
        headers["Referer"] = referer
    if xff:
        headers["X-Forwarded-For"] = xff
    return headers


def fetch_article(url: str, use_cookies: bool = False) -> tuple[int, str]:
    """获取文章 (Googlebot 模式) — 返回 (状态码, 响应文本)"""
    session = requests.Session() if use_cookies else requests

    # 使用 Googlebot UA + 随机 Googlebot IP
    headers = build_bypass_headers(
        ua="googlebot_desktop",
        referer="https://www.google.com/",
        xff=choice(GOOGLEBOT_IPS),
    )

    resp = session.get(url, headers=headers,
                       cookies={}, timeout=30, allow_redirects=True)
    return resp.status_code, resp.text


# 验证: 对比 Chrome UA vs Googlebot UA 响应体长度
if __name__ == "__main__":
    url = "https://www.ft.com/content/abc123"

    # 普通 Chrome UA
    chrome_resp = requests.get(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 Chrome/137.0.0.0 Safari/537.36"
    })
    # Googlebot UA
    _, bot_html = fetch_article(url)

    print(f"Chrome UA   body: {len(chrome_resp.text):>8} bytes")
    print(f"Googlebot UA body: {len(bot_html):>8} bytes")
    print(f"Ratio: {len(bot_html) / max(len(chrome_resp.text), 1):.1f}x")
```

---

## 攻击链

```
1. 探测
   curl -I -H "User-Agent: Googlebot/2.1" URL
   → 对比响应体大小: Googlebot > Chrome → UA 放行确认
   → 检查 vary: User-Agent 响应头 → 动态渲染确认
   → 检查 Google Web Cache 是否存在 → 爬虫索引确认

2. UA 伪装
   → Googlebot (首选, 最广支持)
   → Bingbot (备用, Amazon/Apple News 等特定场景)
   → Facebookbot (社交 paywall 专用)
   → 自定义 UA (特定网站需求)
   → 同时改 Referer + XFF (增强可信度)

3. Cookie 管控
   → 请求级: header_rule Cookie: "" (完全清空)
   → 存储级: remove_cookies_select_drop (精确删除)
   → 存储级: remove_cookies_select_hold (保留白名单)

4. 如果 UA 伪装不够
   → 添加随机 XFF IP (绕过 IP 级速率限制)
   → 添加自定义 Header (X-Forwarded-Proto, X-Is-Crawler)
   → 跳转到 [03-network-rule-blocking](03-network-rule-blocking.md) 阻止 paywall 脚本
   → 跳转到 [04-content-extraction](04-content-extraction.md) 从 JSON/archive.is 提取
```

### 关联技术

- [01-paywall-detection-bypass](01-paywall-detection-bypass.md) — 平台指纹识别
- [03-network-rule-blocking](03-network-rule-blocking.md) — 脚本拦截
- [04-content-extraction](04-content-extraction.md) — 内容提取
- [js-runtime](../../../js-reverse/references/web-runtime/js-runtime.md) — JS 运行时 Hook

## Evidence

- 保存 baseline 与单变量 probe 的完整请求、响应状态、关键响应头和正文摘要。
- 将“页面可见变化”与服务端内容授权分开记录；只有正文差分、状态变化或 Flag 可重复出现才算确认。
- 固定浏览器 profile、UA、Cookie、Storage、脚本拦截规则和执行时序重放，记录成功响应、失败样本和下一跳。
- 输出统一放入 `exports/ctf-website/<case>/`，凭据使用 `REDACTED` 占位并自动检索常见 Flag 格式。
