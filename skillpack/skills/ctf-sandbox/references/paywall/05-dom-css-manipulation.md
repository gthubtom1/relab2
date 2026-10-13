# DOM / CSS / Storage 操作

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/ctf-website/techniques/23-paywall-bypass/05-dom-css-manipulation.md`（GPL-3.0）。原 frontmatter 的 `mcp_tools` 映射已剔除——本技能包未挂载 `run_ctf_tool` / `http_probe`，改用本地工具链。
> **能力域**：本文为技术能力说明，按项目 `scope.md` 直接套用。
> **什么时候用**：命中「见适用信号」这类信号时，把本文当打点清单读；命中即进「步骤」，命中不了就换主题。

## 适用信号

本篇是清单/索引类文档，正文直接以条目给出打点项（见「技术正文」首节）：

- `position: fixed` / `z-index: 9999` 的 overlay 覆盖在正文上方
- `overflow: hidden` 导致正文被截断
- `body` / `html` 上有 `overflow: hidden` 类 (禁止滚动)
- DOM 中存在带 `class*="paywall"` / `id*="gateway"` / `class*="meter"` 的元素
- `article` / `.article-body` 的 `max-height: 200px` 样式
- `window.getComputedStyle(el).display === 'none'` 隐藏正文
- `MutationObserver` 可监听 overlay 的动态注入
- `localStorage` 中 `piano_*` / `meter_*` / `articleViews` 键值在页面加载后更新

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

1. **攻击链** — [01-paywall-detection-bypass](01-paywall-detection-bypass.md) — Paywall 类型识别
2. **攻击链** — [02-http-header-manipulation](02-http-header-manipulation.md) — HTTP 头伪装
3. **攻击链** — [03-network-rule-blocking](03-network-rule-blocking.md) — 脚本拦截
4. **攻击链** — [04-content-extraction](04-content-extraction.md) — 内容提取
5. **攻击链** — [admin-bot-xss](../../../api-security/references/client/admin-bot-xss.md) — DOM Clobbering / MutationObserver 通用技巧
6. **攻击链** — [js-runtime](../../../js-reverse/references/web-runtime/js-runtime.md) — JS 运行时 Hook

## 判据

判据必须是外部可观测的（状态码、响应字段、差分、落盘文件），不是「命令有输出」。

- **输入信号** — `position: fixed` / `z-index: 9999` 的 overlay 覆盖在正文上方
- **输入信号** — `overflow: hidden` 导致正文被截断
- **输入信号** — `body` / `html` 上有 `overflow: hidden` 类 (禁止滚动)
- **输入信号** — DOM 中存在带 `class*="paywall"` / `id*="gateway"` / `class*="meter"` 的元素
- **输入信号** — `article` / `.article-body` 的 `max-height: 200px` 样式
- **输入信号** — `window.getComputedStyle(el).display === 'none'` 隐藏正文
- **输入信号** — `MutationObserver` 可监听 overlay 的动态注入
- **输入信号** — `localStorage` 中 `piano_*` / `meter_*` / `articleViews` 键值在页面加载后更新
- **输入信号** — `document.body.classList` 在 paywall 触发后新增 `no-scroll` / `paywall-active` 类
- **输入信号** — `sessionStorage` 中临时会话标记阻止内容加载
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

当 paywall 的正文已在 DOM 中（只是被 CSS 隐藏或 JS 截断），可以通过 DOM 操作直接移除遮罩层、恢复滚动、删除截断节点。同时，LocalStorage/SessionStorage 中的阅读计数器需要定时清除以防止 meter 累积。

```
Paywall DOM 结构典型模式:
  <div id="app">
    <article>完整正文 (2000 字)</article>
    <div class="paywall-overlay">    ← 遮罩层: position:fixed; z-index:9999
      <div class="paywall-modal">
        "You've read 3 of 3 free articles. Subscribe now."
      </div>
    </div>
    <div class="body-truncated">     ← 截断标记: max-height:200px; overflow:hidden
      <article>...</article>
    </div>
  </div>
```

绕过的关键是**识别 + 移除 overlay + 恢复正文容器样式**。

## 输入信号

- `position: fixed` / `z-index: 9999` 的 overlay 覆盖在正文上方
- `overflow: hidden` 导致正文被截断
- `body` / `html` 上有 `overflow: hidden` 类 (禁止滚动)
- DOM 中存在带 `class*="paywall"` / `id*="gateway"` / `class*="meter"` 的元素
- `article` / `.article-body` 的 `max-height: 200px` 样式
- `window.getComputedStyle(el).display === 'none'` 隐藏正文
- `MutationObserver` 可监听 overlay 的动态注入
- `localStorage` 中 `piano_*` / `meter_*` / `articleViews` 键值在页面加载后更新
- `document.body.classList` 在 paywall 触发后新增 `no-scroll` / `paywall-active` 类
- `sessionStorage` 中临时会话标记阻止内容加载

---

## 方法 1: CSS 注入 — 隐藏 Paywall + 恢复正文

### 原理

最轻量的绕过方式：通过 `<style>` 标签注入 CSS，强制隐藏 paywall overlay 和恢复正文的可见性。适用于 paywall 仅通过 CSS 实现（无 JS 截断）的简单场景。

### 代码: CSS 注入与样式操控

```javascript
// contentScript.js — 通用 CSS/样式操作函数

function hideDOMStyle(selector, id = 1) {
  let style = document.querySelector('head > style#ext' + id);
  if (!style && document.head) {
    let sheet = document.createElement('style');
    sheet.id = 'ext' + id;
    sheet.innerText = selector + ' {display: none !important;}';
    document.head.appendChild(sheet);
  }
}

function addStyle(css, id = 1) {
  let style = document.querySelector('head > style#add' + id);
  if (!style && document.head) {
    let sheet = document.createElement('style');
    sheet.id = 'add' + id;
    sheet.innerText = css;
    document.head.appendChild(sheet);
  }
}

// 使用示例 — 从 cs_code 规则调用
// cs_code: [
//   { hide_elem: ".paywall-overlay, #piano-overlay, .modal-subscribe" },
//   { add_style: "body { overflow: auto !important; }" },
//   { add_style: ".article-body { max-height: none !important; }" },
//   { rm_class: "body.no-scroll|no-scroll" }
// ]
```

### 代码: cs_code 规则引擎

```javascript
// contentScript.js — cs_code 规则 DSL 引擎
// 允许通过声明式配置操作 DOM，无需为每个站点写 JS

function cs_code_elems(elems) {
  for (let elem of elems) {
    if (elem.add_style) {
      // 注入 CSS 规则
      addStyle(elem.add_style);
    }
    else if (elem.hide_elem) {
      // 通过 CSS 隐藏指定选择器
      hideDOMStyle(elem.hide_elem);
    }
    else if (elem.rm_elem_wait) {
      // 等待动态元素出现后移除
      let tagName = elem.rm_elem_wait.match(/^\w+/)[0].toUpperCase();
      waitDOMElement(elem.rm_elem_wait, tagName, removeDOMElement, true);
    }
    else if (elem.cond) {
      // 条件匹配: 对匹配的元素执行操作
      let first = true;
      let elem_dom = document.querySelectorAll(elem.cond);
      for (let item of elem_dom) {
        // 移除元素
        if (elem.rm_elem)
          removeDOMElement(item);
        // 移除 CSS 类 (多类: 逗号分隔)
        if (elem.rm_class) {
          let rm_class = elem.rm_class.split(/[,|]/).map(x => x.trim());
          item.classList.remove(...rm_class);
        }
        // 移除 HTML 属性
        if (elem.rm_attrib) {
          let rm_attribs = elem.rm_attrib.split('|');
          for (let rm_attrib of rm_attribs)
            item.removeAttribute(rm_attrib);
        }
        // 设置属性 (格式: "attr|value")
        if (elem.set_attrib && elem.set_attrib.includes('|')) {
          let [attrib, value] = elem.set_attrib.split('|');
          item.setAttribute(attrib, value);
        }
        // 递归处理子元素
        if (first && elem.elems) {
          first = false;
          cs_code_elems(elem.elems);
        }
      }
    }
  }
}

// 触发入口 — background.js 发送 cs_code 规则到 content script
if (bg2csData.cs_code) {
  window.setTimeout(function () {
    cs_code_elems(bg2csData.cs_code);
  }, 1000);
}
```

### 代码: sites.js 中 cs_code 配置示例

```javascript
// 示例 1: CSS 显示内容 + 移除 Class + 移除属性
"Los Angeles Times": {
  domain: "latimes.com",
  cs_code: [
    {
      cond: "div.paywall",
      rm_attrib: "style",             // 移除内联样式
      set_attrib: "data-active|false", // 修改属性
      rm_class: "metered-content"     // 移除 metered class
    }
  ]
},

// 示例 2: 移除遮罩 + 恢复滚动 + 移除特定元素
"Business Insider": {
  domain: "businessinsider.com",
  cs_code: [
    { add_style: "body { overflow: auto !important; position: static !important; }" },
    { hide_elem: "div.bi-paywall, .tp-modal, .tp-backdrop" },
    { add_style: ".article-content { max-height: none !important; height: auto !important; }" },
    {
      cond: "div.tp-container-inner",
      rm_elem: 1,                     // 完全删除 Piano 容器
    }
  ]
},

// 示例 3: 复杂多步 DOM 操作
"Site with multi-layer paywall": {
  domain: "example.com",
  cs_code: [
    // 步骤 1: 恢复 body 滚动
    { add_style: "html, body { overflow: auto !important; height: auto !important; }" },
    // 步骤 2: 移除付费弹窗
    { hide_elem: "#subscription-modal, .paywall-backdrop, .dynamic-paywall" },
    // 步骤 3: 恢复正文容器
    { add_style: "#article-body, .post-content { max-height: none !important; display: block !important; }" },
    // 步骤 4: 条件移除 — 只在有 paywall 类时操作
    {
      cond: "article.paywalled",
      rm_class: "paywalled",
      rm_attrib: "style"
    }
  ]
}
```

---

## 方法 2: MutationObserver — 动态元素监听

### 原理

许多 paywall 是**动态注入**的——页面加载后延迟 1-3 秒通过 JS 创建 overlay DOM。使用 `MutationObserver` 监听 DOM 变化，在 overlay 出现的瞬间移除它。

### 代码: MutationObserver 移除与属性监听

```javascript
// contentScript.js — 通用 MutationObserver

function waitDOMElement(selector, tagName = '', callback, multiple = false) {
  new window.MutationObserver(function (mutations) {
    for (let mutation of mutations) {
      for (let node of mutation.addedNodes) {
        if (!tagName || (node.tagName === tagName)) {
          if (node.matches(selector)) {
            callback(node);
            if (!multiple)
              this.disconnect();
          }
        }
      }
    }
  }).observe(document, {
    subtree: true,
    childList: true
  });
}

function waitDOMAttribute(selector, tagName = '', attributeName = '', callback, multiple = false) {
  let targetNode = document.querySelector(selector);
  if (!targetNode)
    return;
  new window.MutationObserver(function (mutations) {
    for (let mutation of mutations) {
      if (mutation.target.attributes[attributeName]) {
        callback(mutation.target);
        if (!multiple)
          this.disconnect();
      }
    }
  }).observe(targetNode, {
    attributes: true,
    attributeFilter: [attributeName]
  });
}

// contentScript_once_var.js — 使用示例
// 等待 paywall 节点出现 → 立即删除
waitDOMElement('div.paywall', 'DIV', removeDOMElement, true);
waitDOMElement('#piano-overlay', 'DIV', removeDOMElement, true);

// 监听 body class 变化 (如添加 .no-scroll)
waitDOMAttribute('body', 'BODY', 'class', function (el) {
  el.classList.remove('no-scroll', 'paywall-active', 'overflow-hidden');
  el.style.overflow = 'auto';
}, true);
```

---

## 方法 3: localStorage / sessionStorage 清除

### 原理

Metered paywall 的阅读计数器通常存储在 `localStorage` 或 `sessionStorage` 中。清除这些值可以重置计数器。需要在**页面加载前**和**加载后**两个时间点都执行清除。

### 代码: Storage 清除

```javascript
// contentScript.js — localStorage / sessionStorage 清除

function clearLocalStorage(bg2csData = '') {
  let excluded_domains = [
    'britannica.com', 'nationalreview.com', 'thecritic.co.uk'
  ].concat(usa_mcc_domains);

  if (bg2csData && bg2csData.cs_clear_lclstrg &&
      !matchDomain(excluded_domains)) {
    // 全清
    window.localStorage.clear();
    window.sessionStorage.clear();
  }

  // 选择性清除 — 只清 paywall 相关键
  // (通过 background.js 的 remove_cookies_select_drop 逻辑推断)
  let paywall_keys = [
    'articleViews', 'meterReads', 'meterCount',
    'pw_views', 'piano_views', 'piano_id',
    'tp_session', 'tp_views',
    'poool_access', 'poool_widget',
    'sophi_tracker',
    'blaize_session', 'zephr_session',
    'wp_leaky_paywall', 'issuem_lp',
  ];
  for (let key of paywall_keys) {
    localStorage.removeItem(key);
    sessionStorage.removeItem(key);
  }
}

// background.js — 调度执行策略 (多时间点)
// 每个 tab 执行 5 次，间隔 200ms
var tab_runs = 5;
for (let n = 0; n < tab_runs; n++) {
  setTimeout(function () {
    if (n < 1) {
      // 第一次: 注入 content script + library
      ext_api.scripting.executeScript({
        target: { tabId: tabId, allFrames: use_cs_all_frames },
        files: [lib_file, "contentScript.js", cs_local_file],
        injectImmediately: true,
        world: script_world
      }).catch(err => false);
    }
    // 每次: 清除 Cookie (页面加载后)
    if (rc_domain_enabled) {
      remove_cookies_fn(rc_domain, true);
    }
  }, n * 200);
}
```

### 代码: cs_local 文件 (按语言的站点特定 DOM 操作)

```javascript
// cs_local/contentScript_en.js (部分)
// 约 270KB，包含 ~400 个站点的特定 DOM 操作规则

// 这个文件在 contentScript.js 之后加载，覆盖默认行为

// 示例: Bloomberg
cs_default_bloomberg = function (bg2csData) {
  // 移除 paywall overlay
  document.querySelectorAll(
    '.paywall, #graphics-paywall, .lede-paywall'
  ).forEach(el => el.remove());

  // 恢复滚动
  document.body.style.overflow = 'auto';
  document.documentElement.style.overflow = 'auto';

  // 显示被隐藏的段落
  document.querySelectorAll(
    '.body-content p, .article-body p'
  ).forEach(el => {
    el.style.display = 'block';
    el.style.maxHeight = 'none';
  });
};

// 示例: Wall Street Journal
cs_default_wsj = function (bg2csData) {
  // WSJ paywall 使用 CSS class 切换
  document.querySelectorAll(
    '[class*="snippet"], [class*="truncated"]'
  ).forEach(el => {
    el.classList.remove(...Array.from(el.classList)
      .filter(c => c.includes('snippet') || c.includes('truncated')));
  });

  document.querySelectorAll('.wsj-snippet-login, .wsj-snippet-pitch')
    .forEach(el => el.remove());
};

// 示例: Business Insider — 复杂的多选择器移除
cs_default_bi = function (bg2csData) {
  let selectors = [
    '.paywall-notification', '.tp-modal', '.tp-backdrop',
    '.tp-active', '.bi-paywall', '.subscription-upsell',
    '[class*="paywall"]', '[id*="paywall"]',
  ];
  selectors.forEach(sel => {
    document.querySelectorAll(sel).forEach(el => el.remove());
  });

  // 恢复文章高度
  document.querySelectorAll('.article-content, .post-content')
    .forEach(el => {
      el.style.maxHeight = 'none';
      el.style.height = 'auto';
      el.style.overflow = 'visible';
    });
};
```

---

## 方法 4: Python 自动化 — Playwright/Puppeteer DOM 操作

### 适用于需要 JS 渲染的单页应用

```python
"""playwright_paywall_dom.py — 浏览器自动化 DOM 操作"""
from playwright.sync_api import sync_playwright

def bypass_paywall_dom(
    url: str,
    overlay_selectors: list[str],
    fix_css: str = "",
    clear_storage: bool = True,
) -> str:
    """使用 Playwright 移除 paywall overlay 并提取完整正文"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (compatible; Googlebot/2.1; "
                "+http://www.google.com/bot.html)"
            )
        )
        page = context.new_page()

        if clear_storage:
            # 清除 localStorage (重置阅读计数)
            page.goto(url, wait_until='domcontentloaded')
            page.evaluate("window.localStorage.clear()")
            page.evaluate("window.sessionStorage.clear()")

        page.goto(url, wait_until='networkidle')

        # 等待可能的动态 paywall 注入
        page.wait_for_timeout(2000)

        # 移除所有 overlay
        for sel in overlay_selectors:
            page.evaluate(f"""
                document.querySelectorAll('{sel}').forEach(el => el.remove());
            """)

        # 注入恢复 CSS
        if fix_css:
            page.evaluate(f"""
                let style = document.createElement('style');
                style.textContent = `{fix_css}`;
                document.head.appendChild(style);
            """)

        # 通用恢复规则
        page.evaluate("""
            // 恢复滚动
            document.body.style.overflow = 'auto';
            document.documentElement.style.overflow = 'auto';
            document.body.style.position = 'static';

            // 移除常见 no-scroll 类
            document.body.classList.remove(
                'no-scroll', 'paywall-active', 'overflow-hidden'
            );

            // 恢复被截断的正文
            document.querySelectorAll(
                '.article-body, .post-content, .entry-content, '
                '[class*="article"], [class*="post"]'
            ).forEach(el => {
                el.style.maxHeight = 'none';
                el.style.overflow = 'visible';
            });

            // 移除所有 paywall 相关的 DOM 元素
            document.querySelectorAll(
                '[class*="paywall"], [id*="paywall"], '
                '[class*="meter"], [class*="subscription"], '
                '[class*="upsell"], .tp-modal, .tp-backdrop, '
                '#piano_*, .piano-*, [class*="gateway"]'
            ).forEach(el => el.remove());
        """)

        page.wait_for_timeout(500)
        content = page.content()
        browser.close()
        return content


# 使用示例
if __name__ == '__main__':
    html = bypass_paywall_dom(
        url='https://www.washingtonpost.com/article/...',
        overlay_selectors=[
            '#paywall-overlay', '.paywall-notification',
            '.tp-modal', '.tp-backdrop',
        ],
        fix_css="""
            #article-body { max-height: none !important; }
            .paywall-gradient { display: none !important; }
        """,
        clear_storage=True,
    )
    print(f"Extracted HTML length: {len(html)} chars")
```

---

## 方法 5: 时序操控 — 在 paywall JS 执行前完成操作

### 原理

Paywall JS 通常在 `DOMContentLoaded` 后 1-3 秒执行。如果在 content script 中使用 `runAt: 'document_start'` + `injectImmediately: true`，可以在 paywall 脚本注入**之前**就挂载 MutationObserver 或清除 storage。

### 代码: 抢占式 execution

```javascript
// background.js — Manifest V3 调度
// document_start + injectImmediately → 在页面 JS 之前注入

ext_api.scripting.executeScript({
  target: {
    tabId: tabId,
    allFrames: use_cs_all_frames
  },
  files: [
    "lib/purify.min.js",      // 1. DOMPurify (安全清理)
    "contentScript.js",        // 2. 核心 DOM 操作
    "cs_local/contentScript_en.js"  // 3. 站点特定规则
  ],
  injectImmediately: true,    // 不等 document_idle
  world: script_world         // ISOLATED 或 MAIN
});

// 多时间点重复执行 (时序覆盖)
for (let n = 0; n < 5; n++) {
  setTimeout(function () {
    clearLocalStorage(bg2csData);
    if (!bg2csData.cs_block && typeof cs_default === 'function')
      cs_default(bg2csData);
  }, n * 200);  // 0, 200, 400, 600, 800ms → 覆盖整个 paywall 加载窗口
}

// MAIN world 注入 — 特殊站点需要访问页面 JS 作用域
if (matchUrlDomain([
  'businesspost.ie', 'hbr.org', 'la-croix.com', 'ouest-france.fr'
].concat(grouped_sites['###_fr_groupe_ebra']), url)) {
  script_world = "MAIN";
}
```

---

## 攻击链

```
1. CSS 层面 (最轻量)
   addStyle + hideDOMStyle → 隐藏 overlay + 恢复正文
   → 适用: paywall 仅通过 CSS 实现

2. DOM 层面
   removeDOMElement + MutationObserver → 动态监控并删除
   → 适用: JS 动态注入 overlay

3. Class/Attribute 层面
   rm_class + rm_attrib + set_attrib → 修改元素状态
   → 适用: paywall 通过 class/attribute 切换状态

4. Storage 层面
   localStorage.clear() + sessionStorage.clear()
   → 适用: meter paywall 计数器在 storage 中

5. 时序层面
   injectImmediately + 多次重试 (200ms × 5)
   → 适用: paywall JS 有不确定的执行时序

6. 如果以上都不够
   → 回退到 [02-http-header-manipulation](02-http-header-manipulation.md) (UA 伪装)
   → 回退到 [03-network-rule-blocking](03-network-rule-blocking.md) (脚本拦截)
   → 回退到 [04-content-extraction](04-content-extraction.md) (JSON 提取)
```

### 关联技术

- [01-paywall-detection-bypass](01-paywall-detection-bypass.md) — Paywall 类型识别
- [02-http-header-manipulation](02-http-header-manipulation.md) — HTTP 头伪装
- [03-network-rule-blocking](03-network-rule-blocking.md) — 脚本拦截
- [04-content-extraction](04-content-extraction.md) — 内容提取
- [admin-bot-xss](../../../api-security/references/client/admin-bot-xss.md) — DOM Clobbering / MutationObserver 通用技巧
- [js-runtime](../../../js-reverse/references/web-runtime/js-runtime.md) — JS 运行时 Hook

## Evidence

- 保存 baseline 与单变量 probe 的完整请求、响应状态、关键响应头和正文摘要。
- 将“页面可见变化”与服务端内容授权分开记录；只有正文差分、状态变化或 Flag 可重复出现才算确认。
- 固定浏览器 profile、UA、Cookie、Storage、脚本拦截规则和执行时序重放，记录成功响应、失败样本和下一跳。
- 输出统一放入 `exports/ctf-website/<case>/`，凭据使用 `REDACTED` 占位并自动检索常见 Flag 格式。
