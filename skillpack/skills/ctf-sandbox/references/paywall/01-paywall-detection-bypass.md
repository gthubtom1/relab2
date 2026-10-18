# Paywall 检测与绕过总览

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/ctf-website/techniques/23-paywall-bypass/01-paywall-detection-bypass.md`（GPL-3.0）。原 frontmatter 的 `mcp_tools` 映射已剔除——本技能包未挂载 `run_ctf_tool` / `http_probe`，改用本地工具链。
> **能力域**：本文为技术能力说明，按项目 `scope.md` 直接套用。
> **什么时候用**：命中「见适用信号」这类信号时，把本文当打点清单读；命中即进「步骤」，命中不了就换主题。

## 适用信号

本篇是清单/索引类文档，正文直接以条目给出打点项（见「技术正文」首节）：

- Metered paywall: N 篇免费后封锁 (计数器通常在 Cookie/LocalStorage)
- Hard paywall: 立即要求订阅 (需 UA 伪装或内容提取)
- Freemium: 部分 Premium 内容隐藏 (CSS + Script + JSON-LD)
- Dynamic paywall: ML 驱动的动态拦截策略 (阈值模型可被时序操控)
- AMP paywall: Google AMP 页面部分隐藏内容 (amp-access 标签)
- Registration wall: 需注册但内容免费 (CSRF + 自动注册)
- Cookie wall: GDPR 弹窗 + 阅读计数 (清除 Cookie 重置)
- DOM 中出现 paywall overlay 模态框 (`div.paywall`, `#gateway-content`, `.meter`, `#piano_*`)

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

1. **攻击链** — [02-http-header-manipulation](02-http-header-manipulation.md) — UA/Referer/Cookie 伪装
2. **攻击链** — [03-network-rule-blocking](03-network-rule-blocking.md) — declarativeNetRequest 脚本拦截
3. **攻击链** — [04-content-extraction](04-content-extraction.md) — JSON-LD/Next.js/archive.is 提取
4. **攻击链** — [05-dom-css-manipulation](05-dom-css-manipulation.md) — DOM/CSS 操作与 storage
5. **攻击链** — [js-runtime](../../../js-reverse/references/web-runtime/js-runtime.md) — JS Hook 与运行时修改
6. **攻击链** — [version-fingerprinting](../../../attack-chain/references/recon/version-fingerprinting.md) — CMS 平台指纹
7. **攻击链** — [cloudflare-bypass](../../../attack-chain/references/recon/cloudflare-bypass.md) — CDN 源站绕过

## 判据

判据必须是外部可观测的（状态码、响应字段、差分、落盘文件），不是「命令有输出」。

- **输入信号** — DOM 中出现 paywall overlay 模态框 (`div.paywall`, `#gateway-content`, `.meter`, `#piano_*`)
- **输入信号** — `<script>` 加载 pianola.io / tinypass.com / poool.fr / sophi.io / wallkit.net / axate.io 等 paywall SDK
- **输入信号** — Googlebot UA 请求同一 URL 返回更长的响应体 (检查 UA 差异化)
- **输入信号** — `document.cookie` 中存在 `pw_*` / `pay_*` / `meter_*` / `article_limit` / `blaize_*` / `TDNotesRead` 等标记
- **输入信号** — `<script type="application/ld+json">` 或 `<script id="__NEXT_DATA__">` 中包含完整正文但 DOM 中被截断
- **输入信号** — HTTP 响应头 `x-paywall-*` / `x-metered-*` / `x-article-access` / `x-cache-status` 等标记
- **输入信号** — `<link rel="amphtml">` 存在，AMP 版本包含完整内容但 canonical 页面隐藏
- **输入信号** — Google webcache / archive.is / textise dot iitty 中存有完整内容
- **输入信号** — `localStorage` 中 `articleViews` / `meterReads` / `pw_*` / `piano_*` 等计数键
- **输入信号** — `<meta generator="Ghost">`, `<link href="https://substackcdn.com">` 等 CMS 指纹
- **输入信号** — `<div id="issuem-leaky-paywall-*">`, `span#hmn-logo` 等出版集团后端标记
- **输入信号** — `window.Fusion.globalContent.content_restrictions` / `isPremium` 等 JS 运行时变量
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

现代新闻/内容网站的 Paywall 是客户端+服务端混合的访问控制系统。绕过 paywall 本质上是利用网站为搜索引擎爬虫保留的 SEO 后门——Googlebot 需要索引全文内容，因此 paywall 必须对特定 User-Agent/Referer 放行。攻击面横跨 HTTP 头、DOM、Cookie、脚本加载和第三方服务。

```
攻击目标:
  - Metered paywall: N 篇免费后封锁 (计数器通常在 Cookie/LocalStorage)
  - Hard paywall: 立即要求订阅 (需 UA 伪装或内容提取)
  - Freemium: 部分 Premium 内容隐藏 (CSS + Script + JSON-LD)
  - Dynamic paywall: ML 驱动的动态拦截策略 (阈值模型可被时序操控)
  - AMP paywall: Google AMP 页面部分隐藏内容 (amp-access 标签)
  - Registration wall: 需注册但内容免费 (CSRF + 自动注册)
  - Cookie wall: GDPR 弹窗 + 阅读计数 (清除 Cookie 重置)
```

该扩展**自称**覆盖大量站点（第三方宣传数字，仓库内无证据文件，**不要当事实引用**）；实际支持面需自行抽验。

## 输入信号

- DOM 中出现 paywall overlay 模态框 (`div.paywall`, `#gateway-content`, `.meter`, `#piano_*`)
- `<script>` 加载 pianola.io / tinypass.com / poool.fr / sophi.io / wallkit.net / axate.io 等 paywall SDK
- Googlebot UA 请求同一 URL 返回更长的响应体 (检查 UA 差异化)
- `document.cookie` 中存在 `pw_*` / `pay_*` / `meter_*` / `article_limit` / `blaize_*` / `TDNotesRead` 等标记
- `<script type="application/ld+json">` 或 `<script id="__NEXT_DATA__">` 中包含完整正文但 DOM 中被截断
- HTTP 响应头 `x-paywall-*` / `x-metered-*` / `x-article-access` / `x-cache-status` 等标记
- `<link rel="amphtml">` 存在，AMP 版本包含完整内容但 canonical 页面隐藏
- Google webcache / archive.is / textise dot iitty 中存有完整内容
- `localStorage` 中 `articleViews` / `meterReads` / `pw_*` / `piano_*` 等计数键
- `<meta generator="Ghost">`, `<link href="https://substackcdn.com">` 等 CMS 指纹
- `<div id="issuem-leaky-paywall-*">`, `span#hmn-logo` 等出版集团后端标记
- `window.Fusion.globalContent.content_restrictions` / `isPremium` 等 JS 运行时变量

---

## 方法 1: Paywall 平台指纹识别

### 原理

不同 CMS 和 paywall 服务在 DOM 中留下独特的"指纹"，通过检测这些标记可以自动匹配合适的绕过策略。

### Paywall 平台指纹表

```
第三方服务:
  Piano/Tinypass    → script[src*="tinypass.com"], script[src*="piano.io"], div#piano_*
  Poool             → script[src*=".poool.fr/"], script[src*="poool.js"]
  Sophi             → script[src*=".sophi.io/"], div[class*="sophi"]
  Axate/Agate       → script[src*=".axate.io/"], script[src*=".agate.io/"]
  Wallkit           → script[src*=".wallkit.net"], link[href$=".wallkit.net"]
  Leaky Paywall(WP) → script[src*="/leaky-paywall"], div[id^="issuem-leaky-paywall-"]
  Zephr/Blaize      → script[src*="zephr"], script[src*="blaize"]
  Memberstack       → script[data-memberstack-app]

CMS 平台:
  Substack    → link[href^="https://substackcdn.com/"]
  Ghost       → meta[name="generator"][content^="Ghost"] (不含 SteadyHQ)
  Medium      → link[href*=".medium.com/"]
  beehiiv     → meta[property="og:image"][content*="beehiiv"]
  WordPress   → /wp-content/ + Leaky Paywall / Zephr 插件标记

出版集团后端 (按国家/地区):
  Gannett(USA)         → link[href*="/gannett_net.js"], footer a[href^="https://www.gannett.com"]
  Hearst(USA)          → script[src*="/treg.hearstnp.com/"]
  Lee Enterprises(USA) → script[src*=".townnews.com/leetemplates.com/"]
  McClatchy(USA)       → link[href^="https://mcclatchy-d.openx.net"]
  MNG(USA)             → link[id^="dfm-accuweather-"], footer a[href^="https://www.medianewsgroup.com"]
  Postmedia(CA)        → script[src*=".postmedia.digital/"]
  TownNews(USA)        → meta[name="tncms-access-version"]
  CNHI(USA)            → script[src*="-cnhi-pw.newsmemory.com"]
  BridgeTower(USA)     → script[src="https://cdn.blueconic.net/bridgetowermedia.js"]
  News Corp(AU)        → 付费墙 URL: */subscribe/*?dest=*
  DPG Media(NL)        → block_regex: "temptation\\.{domain}\\/"
  Mediahuis(NL/BE)     → script 中 /pmgnews/ 路径
  Reach PLC(UK)        → footer a[href="https://jobs.reachplc.com/jobs"]
  Newsquest(UK)        → footer a[href^="https://www.newsquest.co.uk/"]
  Haymarket(UK)        → footer a[href^="http://www.haymarket.com"]
  Delinian(UK)         → footer a[href^="https://www.delinian.com/privacy-policy"]
  Madsack(DE)          → link[href*=".rndtech.de/"]
  Ippen Media(DE)      → header a[href^="https://www.ippen.media"]
  CH Media(CH)         → script[src^="https://static.data.chmedia.ch/"]
  Tamedia(CH)          → div#__next li > a[href^="https://jobs.tamedia.ch/"]
  Kaleva Media(FI)     → head[prefix*=".kalevamedia.fi/"]
  Groupe Ebra(FR)      → 特定 domain 模式
  Groupe Infopro(FR)   → 含 group 成员 domain
  Vocento(ES)          → 含 group 成员 domain
  Prensa Ibérica(ES)   → link[href*="/estaticos-cdn."]
  Bonnier News(SE)     → footer a[href*=".bonniernews.se/cookiepolicy"]
```

### 代码: 页面指纹采集 (contentScript_once.js)

```javascript
// 发送给 background 进行规则匹配
window.setTimeout(function () {
  let hostname = window.location.hostname.replace(/^www\./, '');
  let group, nofix;

  if (document.querySelector('head > link[href*=".medium.com/"]'))
    group = '###_medium';
  else if (document.querySelector('head > meta[property="og:image"][content*="beehiiv"]')) {
    group = '###_beehiiv';
    nofix = 1;
  } else if (document.querySelector('head > meta[name="generator"][content^="Ghost"]')
             && !document.querySelector('script[src^="https://steadyhq.com/"]')) {
    group = '###_ghost';
    nofix = 1;
  } else if (document.querySelector('div[id^="issuem-leaky-paywall-"]'))
    group = '###_wp_leaky_paywall';
  else if (document.querySelector('head > link[href^="https://substackcdn.com/"]')) {
    group = '###_substack_custom';
    nofix = 1;
  } else if (hostname.match(/^thelocal\.(at|ch|com|de|dk|es|fr|it|no|se)$/))
    group = '###_eu_thelocal';
  // ... 更多国家/地区的 DOM 签名检测
  else if (hostname.endsWith('.com')) {
    if (document.querySelector('footer a[href^="https://www.valnetinc.com"]'))
      group = '###_ca_valnet';
    else if (document.querySelector('head > meta[property][content^="https://cdn.forumcomm.com/"]'))
      group = '###_usa_forum_comm';
    else if (document.querySelector('footer a[href^="https://www.delinian.com/privacy-policy"]'))
      group = '###_uk_delinian';
  }

  if (group) {
    console.log(group);
    ext_api.runtime.sendMessage({
      request: 'custom_domain',
      data: { domain: getCookieDomain(hostname), group: group, nofix: nofix }
    });
  }
}, 1000);
```

---

## 方法 2: Cookie 域探测

### 原理

浏览器 Cookie 可在不同域级别设置。Paywall 系统常在父域写 Cookie 跨子域生效。需要从子域向父域逐级遍历探测准确的有效域。

### 代码: Cookie 域遍历探测

```python
# Python 版本 — 用于爬虫
def cookie_domain_sweep(hostname: str, session) -> str:
    """从子域向父域遍历，找到 cookie 有效域"""
    parts = hostname.split('.')
    test_key = f'_gd{hash(hostname)}'

    for n in range(len(parts) - 1):
        domain = '.'.join(parts[-(1+n):])
        session.cookies.set(test_key, '1', domain=domain)
        # 验证 cookie 是否成功被域接受
        if session.cookies.get(test_key, domain=domain) == '1':
            # 清理探测 cookie
            session.cookies.clear(domain=domain, name=test_key)
            return domain
    return hostname
```

```javascript
// JS 版本 — 用于浏览器扩展
function getCookieDomain(hostname) {
  let parts = hostname.split('.');
  let str = '_gd' + Date.now();
  let domain = hostname;
  let n = 0;
  while (n < parts.length - 1 && document.cookie.indexOf(str + '=' + str) === -1) {
    domain = parts.slice(-1 - (++n)).join('.');
    document.cookie = str + "=" + str + ";domain=" + domain + ";";
  }
  document.cookie = str + "=;expires=Thu, 01 Jan 1970 00:00:01 GMT;domain=" + domain + ";";
  return domain;
}
```

---

## 攻击链

```
1. 指纹 → 平台识别
   DOM 选择器 + <meta>/<link>/<script> 标签 → 确定 CMS + Paywall 服务

2. 分层绕过 (按优先级)
   UA 伪装 + Cookie 清除 → 服务器直接返回全文 (最强方式)
   ↓ 不适用
   脚本拦截 → 阻止 paywall SDK 加载，正文自然可见
   ↓ 不适用
   JSON-LD 提取 → 从 <script> JSON 中恢复完整正文
   ↓ 不适用
   archive.is 代理 → 从外部缓存获取完整内容
   ↓ 不适用
   DOM/CSS 操作 → 移除 overlay，恢复正文可见

3. 持久化
   localStorage.clear() + sessionStorage.clear() → 重置阅读计数器
   定时清除 Cookie → 防止计数器累积
```

### 关联技术

- [02-http-header-manipulation](02-http-header-manipulation.md) — UA/Referer/Cookie 伪装
- [03-network-rule-blocking](03-network-rule-blocking.md) — declarativeNetRequest 脚本拦截
- [04-content-extraction](04-content-extraction.md) — JSON-LD/Next.js/archive.is 提取
- [05-dom-css-manipulation](05-dom-css-manipulation.md) — DOM/CSS 操作与 storage
- [js-runtime](../../../js-reverse/references/web-runtime/js-runtime.md) — JS Hook 与运行时修改
- [version-fingerprinting](../../../attack-chain/references/recon/version-fingerprinting.md) — CMS 平台指纹
- [cloudflare-bypass](../../../attack-chain/references/recon/cloudflare-bypass.md) — CDN 源站绕过

## Evidence

- 保存 baseline 与单变量 probe 的完整请求、响应状态、关键响应头和正文摘要。
- 将“页面可见变化”与服务端内容授权分开记录；只有正文差分、状态变化或 Flag 可重复出现才算确认。
- 固定浏览器 profile、UA、Cookie、Storage、脚本拦截规则和执行时序重放，记录成功响应、失败样本和下一跳。
- 输出统一放入 `exports/ctf-website/<case>/`，凭据使用 `REDACTED` 占位并自动检索常见 Flag 格式。
