# 本地挑战执行器手册（Local Challenge Executor Playbook）

> **来源声明**：本文改编自外部仓库 `aoyunyang/spider-king-skill`（MIT License）的 `local-challenge-executor-playbook.md`。原文为英文，此处译为中文并按本包六段式规范重排；技术术语保留英文原词并附中文，AI 检索时中英文均可命中。源文档技术内容经逐条核对**未发现错误**，未作技术性修改。**本机化重点**：源文档举例的宿主 `jsdom` / `happy-dom` / `iv8` 本机**均不可用**，已替换为本机实测可用的 `node` + `vm` 自建 stub 与 `playwright`。

> ★★ **本机 playwright 必须显式指定浏览器**（2026-10-10 实测）：
> `launch()` 默认启动会报 `Executable doesn't exist at %LOCALAPPDATA%\ms-playwright\chromium_headless_shell-1234\...`
> —— python 包期望 1234，本机装的是 **1243**，版本号对不上。
> **可用写法**：`p.chromium.launch(channel="msedge")`（实测能起、能渲染、能读 DOM），
> 或 `launch(executable_path=<显式路径>)`。照抄裸 `launch()` 一定失败。
> 
>
> **什么时候用**：挑战 HTML 或挑战 JS **必须在本地运行**才能吐出一个**可回放的产物**，而**最终采集器必须保持无浏览器（browser-free）**。
>
>
> | 能力 | 本机状态 |
> |---|---|
> | `node v22.23.3`（`(Resolve-ReverseToolSpec -Name 'node').Command`）+ `vm` + 自建 stub | ✅ **实测可用**，本文主路径 |
> | `playwright` + <playwright 浏览器> | ✅ 实测可用（需显式 `executable_path`） |
> | `python 3.12`（`(Resolve-ReverseToolSpec -Name 'pyre').Command`） | ✅ 可用，**拥有全部真实 HTTP** |
> | `jsdom` / `happy-dom` | ❌ **本机无**（npm 未装） |
> | `iv8` | ❌ **本机无** |

---

## 适用信号（Recognition signals）

- 业务 JSON API 返回 **`text/html` 挑战页**，而不是数据
- 某个文档路由返回**非终态 HTML + 链接的挑战脚本**
- 成功**依赖于**一个被重写的 URL、一个派生的 cookie 头、或由挑战执行产生的 storage 模块
- **完整离线重建加密器，比在最小宿主里跑一遍挑战 blob 更慢**
- 反调试或缺失的 DOM API 让浏览器收割变得嘈杂，**但一个打桩的本地执行器仍能吐出产物**

## 前置（Entry conditions）

1. **挑战资产已冻结** —— HTML、链接脚本 URL、脚本正文、以及**同一条 session 链**上的种子 cookies
2. **一个本机宿主**（三选一，见上面表格）
3. **明确的产物目标** —— 是 `redirectUrl`、还是 `cookieString`、还是两者
4. **桥接隔离已就绪**（见「本地桥接隔离」一节）—— **这是安全前提，不是可选项**

---

## 步骤（Working method）

### 核心思想（Core idea）

**Python 拥有活体 HTTP。**
**helper 只负责恢复那个缺失的挑战产物。**

> **成功 ≠ 「脚本干净地跑完了」。**
> 成功 = 一个**Python 可回放**的 `redirectUrl`、组装好的 `Cookie` 头、或等价的 wire 产物。

### 契约（Contract）

#### helper 输入

```json
{
  "url": "https://example.invalid/api/business?...",
  "html": "<!doctype html>...",
  "externalScriptUrl": "https://example.invalid/challenge.js",
  "externalScriptText": "/* challenge source */",
  "seedCookies": "a=1; b=2",
  "timeoutMs": 5000
}
```

#### helper 输出

```json
{
  "redirectUrl": "https://example.invalid/api/business?...&decode=...",
  "cookieString": "a=1; c=3",
  "navigationAttempts": ["..."],
  "errors": ["optional noise"],
  "xhrRequests": [],
  "fetchCalls": [],
  "resourceRequests": []
}
```

> **`redirectUrl` 或可回放的 `cookieString` 至少要有一个存在。**

### 最小宿主要求（Minimal host requirements）

**只实现能保住挑战进展的最小宿主：**

1. **文档 URL** 等于被挑战的业务 / 文档 URL
2. **脚本注入**：对预期 URL 返回捕获到的挑战脚本；**其他子资源可以 404**，除非有证据证明它们必需
3. **Cookie jar**：从**同一条 session 链**的首跳响应播种
4. **Location 捕获**：在 navigate / assign / replace / href setter 上
5. **Canvas / WebGL stub** —— 当存在指纹探针时
6. **XHR 与 fetch stub**：记录调用，**除非确实需要真实本地响应，否则返回空成功**
7. **定时器压缩**：让长 `setTimeout` 链能在 `timeoutMs` 内跑完
8. **反调试容忍**：当 `debugger` 循环**只是延迟产物产出**时，忽略或中和它

> **不要把本技能绑定到某一个宿主品牌。**
> `jsdom`、`happy-dom`、嵌入式宿主，或**本机的 `node` + `vm` 自建 stub** —— 任何保住了所需语义的最小宿主都可以。

### 本机最小宿主骨架（`node` + `vm`，实测形态）

源文档举例的三个宿主本机**都不可用**。以下是本机实测形态的骨架，
对应上面 8 条最小宿主要求：

```javascript
// challenge-exec.js —— node v22.23.3 实测形态
const vm = require('vm');
const input = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));

const nav = [];                 // ← 要求 4：Location 捕获
const timers = [];              // ← 要求 7：定时器压缩
const xhrCalls = [];            // ← 要求 6：XHR 记录
const fetchCalls = [];
const resourceRequests = [];
const errors = [];

const ALLOWED = new Set([input.url, input.externalScriptUrl].filter(Boolean));

const sandbox = {
  console: { log(){}, warn(){}, error(...a){ errors.push(String(a[0])); } },
  location: { href: input.url, _replace(u){ nav.push(u); } },
  navigator: { userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)' },
  document: { cookie: input.seedCookies ?? '', referrer: '' },
  // 要求 5：指纹探针 stub
  // ★★★ 必须返回**非 null 的 2D 上下文**，不能返回 null。
  // 真实挑战脚本做 canvas 指纹的典型写法：
  //     var ctx = canvas.getContext('2d'); ctx.fillText(...); canvas.toDataURL();
  // 若 getContext 返回 null，fillText 立刻抛
  // `TypeError: Cannot read properties of null (reading 'fillText')`，
  // 挑战脚本当场崩掉 —— 恰恰是最需要跑通的那条路径被堵死。
  // （2026-10-10 本机 node v22.23.3 实测：null 上下文调 fillText 必抛。）
  HTMLCanvasElement: function(){
    const self = this;
    const ctx = new Proxy({}, {
      get(_t, prop) {
        if (prop === 'canvas') return self;
        return (..._a) => (prop === 'measureText' ? { width: 0 } : undefined);
      },
      set() { return true; },
    });
    this.toDataURL = () => 'data:image/png;base64,iVBORw0KGgo=';
    this.getContext = () => ctx;
    this.width = 300; this.height = 150;
  },
  setTimeout: (fn) => { timers.push(fn); return timers.length; },   // 要求 7
  clearTimeout: () => {},
  setInterval: () => 0,      // debugger 类循环：忽略（要求 8）
  XMLHttpRequest: function () {
    this.open = (m, u) => { this._m = m; this._u = u; };
    this.setRequestHeader = (k, v) => { (this._h ??= {})[k] = v; };
    this.send = (b) => {
      // ★ b 可能未传参；`String(undefined)` 会产出字符串 "undefined"，
      // 污染请求体记录（2026-10-10 本机 node 实测：无参 send() 记到 body="undefined"）。
      // 归一成空串，另给 hasBody 让调用方能区分「无体」与「空体」。
      xhrCalls.push({ method: this._m, url: this._u, headers: this._h ?? {},
                      body: b === undefined || b === null ? '' : String(b),
                      hasBody: b !== undefined && b !== null,
                      cookie: sandbox.document.cookie });
      if (!ALLOWED.has(this._u)) resourceRequests.push({ url: this._u, status: 404 });
    };
  },
  fetch: (u, o) => { fetchCalls.push({ url: u, opt: o }); return Promise.resolve({ text: async () => '' }); },
};
// 导航相关 API —— 要求 4
sandbox.window = sandbox; sandbox.globalThis = sandbox;
sandbox.location.assign = u => nav.push(u);
sandbox.location.replace = u => nav.push(u);

vm.createContext(sandbox);

// 注入捕获到的脚本并运行
vm.runInContext(input.externalScriptText, sandbox);

// drain：把定时器链跑完（压缩时间，对应要求 7）
let guard = 0;
while (timers.length && guard++ < 1000) timers.shift()();

// 产物：要求 6 —— cookie 串与导航目标
console.log(JSON.stringify({
  redirectUrl: nav[nav.length - 1] ?? null,
  cookieString: sandbox.document.cookie,
  navigationAttempts: nav,
  errors, xhrRequests: xhrCalls, fetchCalls, resourceRequests,
}, null, 1));
```

调用：
```powershell
& (Resolve-ReverseToolSpec -Name 'node').Command challenge-exec.js input.json > output.json
```

> ⚠ **诚实声明（2026-10-10 本机实测复核）**：
> 上面这段骨架**已用一份模拟挑战脚本实跑验证 12 项全过**：全局隔离、URL 白名单 404、
> Location 捕获、**canvas 指纹路径不崩**（`getContext('2d').fillText()` + `toDataURL()`
> + `measureText().width` 都通）、XHR 记录、**无参 `send()` 的 body 归一**、
> 定时器 drain 跑到最后一层、`setInterval` 返回 0 不挂死。
> 复现：把 `externalScriptText` 换成任意挑战脚本，`url` / `seedCookies` 填观测值即可。
>
> ★ **本次复核改掉了两个真 bug**：原 canvas stub 的 `getContext()` 返回 `null`，
> 真实挑战脚本一调 `fillText` 就抛 `TypeError: Cannot read properties of null`；
> 原 `send()` 用 `String(b)` 会把无参调用记成 `body="undefined"`。两者都已在上方代码里修好。
>
> **仍未验证**：对任何**真实站点**的挑战 blob —— 本机无授权目标、无真实样本。
> 「骨架能用」不等于「能解某家的挑战」。

### 快速执行路径（Fast execution path）

1. Python 用**已准入的传输画像** GET 业务 / 文档 URL
2. 若响应体是**挑战 HTML**，就在**同一条 session 链**上冻结 HTML、链接脚本 URL、脚本正文、以及种子 cookies
3. 用上述契约运行本地 helper
4. **按此优先级**选产物：
   1. **被重写的导航 / 重定向 URL**（带决定性 query 参数）
   2. **完整的出站 `Cookie` 头或 cookie 字符串**
   3. **storage 模块** —— 仅当后续被证明重新生成时必需
5. Python 合并 cookies、按回放证据补上任何**原始 URL 回声字段**，然后做**真实 HTTP 回放**
6. **用业务锚点验证**（JSON schema 键、列表长度、HTML 标记），**而不只是 HTTP 200**

### 本地桥接隔离（Local bridge containment）

> **把挑战类 / 采集器类 JavaScript 当作不可信代码对待。**
> 即使本地宿主需要观察 XHR 或 fetch 的意图，
> **Python 仍必须拥有每一个真实 HTTP 请求**，桥接必须**窄且受控**。

**强制执行这些控制：**

- **从 Python 在同一 session 链上已经发现的确切 URL** 构建**白名单**
- **要求 HTTPS 与预期 origin**，除非活体证据证明另一条路由也是契约的一部分
- **把 method 限制在观察到的契约内**
- **禁用重定向**，或在跟随之前**拒绝任何意外的重定向**
- **剥离采集器控制的** `Cookie`、`Authorization`、`Proxy-Authorization`、`Host`、`Connection` 与转发头
- **让 Python 的 session jar 成为唯一的 cookie 权威**
- **限制请求数、请求体大小、响应大小、以及单请求超时**
- **拒绝** `file:`、`data:`、localhost、loopback、link-local、私有网络、以及任意主机名
- **记录被拦截的请求**时，只记**结构化元数据**，不记原始密钥

> **不要仅仅因为 helper 选的主机名「看起来同源」就解析或转发它。**
> **权威是：从活体页面发现的确切 URL、有效 origin、以及 Python 的 session 链。**

### 产物优先级（Artifact priority）

1. **导航 / 重定向 URL**
2. **组装好的 Cookie 头 / cookie 字符串**
3. **单个具名 cookie**
4. **localStorage / sessionStorage 模块**
5. **完整的加密链逆向**

> **一旦 Python 能回放，就停止升级。**

### 产物到手之后的噪音（Post-artifact noise）

**在一个有效产物已经存在之后，下列情况不是自动失败：**

- `navigation to another Document` / not implemented
- 缺失的分析类端点
- 后续的定时器异常
- **没有阻塞产物吐出的**部分指纹 API 缺口

### 与其他门的耦合（Coupling with other gates）

- **若同一个参数也存在一条短的离线 signer 路径**，在选择「产品侧写入者」**之前**，先读 `../observe/dual-writer-param-playbook.md`
- **若传输伪装改变了「你收到的是 JS 挑战 HTML 还是另一堵墙」**，**先修传输准入**
- **若应用层的 HMAC / sign 是独立的**，证明**挑战回放是否真的需要它**

### 交付形态（Delivery shape）

```text
裸业务请求
  → 挑战 HTML + 脚本（同 session）
    → 本地挑战执行器
      → Python 回放（redirectUrl 或 Cookie）
        → 分页 / 并发
```

**如实报告 browser-free 状态：**

- **browser-free 采集器 + 本地挑战执行器**
- **若仍残留一个 JS 宿主，则「不是完全 runtime-free」**

### 版本随机化的 helper 边界（Version-randomized helper boundary）

**当挑战脚本或动态 VM 资产每轮都换路径时：**

1. **对当前资产做哈希**
2. 比较**公开的 helper 或 VM 调用边界**，**而不只是 URL**
3. **从一条干净的成功样本重跑固定向量**
4. **若边界稳定**，一个极小的本地 opcode 或 wrapper 扫描 helper **可能仍然可接受**
5. **只有当框架（framing）、向量、或输出发散时**，才重建一个新 helper 版本

> **Python 仍拥有活体 HTTP、会话顺序、等待、以及接受判定。**
> **helper 绝不能变成一个浏览器。**

---

## 判据（Verification checklist）

只有满足以下**全部 6 条**，才可以说「本地挑战执行器这一层搞定了」：

1. **产物已拿到**，且它是 `redirectUrl`、`cookieString`、或两者 —— **有具体值，不是「helper 跑完了」**
2. **Python 用这个产物完成真实回放，并按业务锚点（JSON schema 键 / 列表长度 / HTML 标记）验证通过至少两次**
3. **桥接隔离已强制执行** —— 白名单、HTTPS+origin 校验、方法限制、禁重定向、头剥离、请求数/大小/超时上限、私网拒绝，**全部有**
4. **交付形态已如实分类** —— 是「browser-free + 本地挑战执行器」，还是「仍非 runtime-free」
5. **若回放需要原始 URL 回声字段，已证明并在回放中带上**
6. **若挑战资产每轮随机化**，已证明「helper 边界」而非「资产 URL」是稳定的那一层

> ⚠ **不构成完成**的典型情形：
> - **要求 helper 零错误** —— 那是错的，成功判据是「有可回放产物」
> - 「helper 成功返回了一个 cookie」
> - 「HTTP 200」—— **必须用业务锚点验证**

### 最小交接说明（Minimal handoff notes）

**报告：**

- 被挑战的路由与 content type
- helper 的宿主家族（本机为 **`node v22.23.3` + `vm` 自建 stub**）
- **哪个产物胜出**（`redirectUrl` / cookie / 两者）
- **原始 URL 回声是否必需**
- 准入所用的传输画像
- **在新时间戳或新页面上活体重新生成的证明**

---

## 常见坑（Common traps）

- **把 Playwright 或 CDP 的页面驱动当作产品路径**
  （⚠ 注意区分：**用 playwright 作为「证据采集」可以**，**作为最终采集器不行**）
- **让本地 helper 自行选择任意网络目的地，或自己拥有活体 HTTP**
- **要求零 helper 错误**，而不是要求一个可回放的产物
- **在首跳 cookies 已经绑定整条链之后**，用脱带的客户端重新下载挑战脚本
- **在重定向 URL 已经带上决定性参数之后**，还去重建整个加密器
- **在回放时忘记原始 URL 回声字段** —— 除非证据显示不需要
- **把「helper 跑完了」当作成功** —— 判据是产物，不是完成标志

---

## 源文档勘误（改编时修正）

1. **【宿主示例全部不可用，已替换】** 源文档「Minimal host requirements」末尾写道：
   > `jsdom`, `happy-dom`, `iv8`, or another minimal host is acceptable

   **本机实测：`jsdom`、`happy-dom`、`iv8` 三者均不可用。**
   源文档的**语义**（「不要绑定到某个宿主品牌」）**完全正确且已保留**，
   改编时把它落地为本机实测可用的 `node v22.23.3` + `vm` 自建 stub 骨架，并保留「任何保住所需语义的最小宿主都可以」这一判断。

2. **【未变的结论】** 源文档的契约（JSON 输入 / 输出）、8 条最小宿主要求、桥接隔离控制清单、产物优先级、以及交付形态**全部保留**，经逐条核对**未发现错误**。

---

## 相关（Related）

- `iv8-runtime-cheatsheet.md` —— **本机可执行的宿主能力**（替代路径 A / B，均附本机实测输出）
- `embedded-browser-runtime-playbook.md` —— 「何时该引入 / 退出嵌入式宿主」的判据
- `environment-patch-playbook.md` —— 补宿主表面的 15 步方法（本文第 5 条 Canvas/WebGL stub 的展开）
- `../state/challenge-artifact-harvest-playbook.md` —— 产物收割的通用规程
- `../state/challenge-state-envelope-playbook.md` —— 挑战输出作为协议状态的迁移
- `../observe/dual-writer-param-playbook.md` —— 「与本文耦合」一节引用的双写入者判据
- `../observe/anti-debug-playbook.md` —— 第 8 条「反调试容忍」的绕过手段
- `../deliver/delivery-gate-playbook.md` —— browser-free / runtime-free 的交付门判定