# iv8 运行时速查（iv8 Runtime Cheatsheet）

> **来源声明**：本文改编自外部仓库 `aoyunyang/spider-king-skill`（MIT License）的 `iv8-runtime-cheatsheet.md`。原文为英文，此处译为中文并按本包六段式规范重排；技术术语保留英文原词并附中文，AI 检索时中英文均可命中。**方法论部分（时间控制、netLog 出网捕获、wrapNative、watch_apis、probe-then-patch 顺序）全部保留**；具体 API 形态一律按本机事实重新标注，并**新增一整节本机可执行的替代路径**。
>
> **什么时候用**：在 `embedded-browser-runtime-playbook.md` 已经论证「本地嵌入式宿主是正确的交付形态」之后。
>
> ## ⚠️ 本机状态：**本机没有 `iv8`**
>
> **`iv8` 是社区运行时，PyPI 上不存在该发行版。**
>
> - 本机实测：`D:\Tools` 与 `(Resolve-ReverseToolSpec -Name 'pyre').Command`（`pip` 环境）**均无此包**
> - 本文**每一个**涉及 `iv8` 具体 API 的地方，都标注了：
>   > ⚠ 本机无 iv8（本机实测：`D:\Tools` 与 Python 环境均无此包）。以下 API 形态供具备该运行时时参考，**未在本机验证**。
> - **不要**把「装 iv8」当成唯一出路 —— 本文下半部分给出了**本机现在就能跑的替代路径**（`node` + `vm` + 自建 stub，以及 `playwright`），两者都已在本机实测跑通。

> ★★ **本机 playwright 必须显式指定浏览器**（2026-10-10 实测）：
> `launch()` 默认启动会报 `Executable doesn't exist at %LOCALAPPDATA%\ms-playwright\chromium_headless_shell-1234\...`
> —— python 包期望 1234，本机装的是 **1243**，版本号对不上。
> **可用写法**：`p.chromium.launch(channel="msedge")`（实测能起、能渲染、能读 DOM），
> 或 `launch(executable_path=<显式路径>)`。照抄裸 `launch()` 一定失败。
> 
>
> **本机可用工具链**（实测确认）：

| 能力 | 本机路径 | 状态 |
|---|---|---|
| Node.js | `(Resolve-ReverseToolSpec -Name 'node').Command` v24.20.0 | ✅ 可用 |
| Python | `(Resolve-ReverseToolSpec -Name 'pyre').Command` 3.12.0 | ✅ 可用 |
| Playwright | `playwright`（Python 包） | ✅ 包可用，⚠ 见下方浏览器路径说明 |
| Chromium | `$env:LOCALAPPDATA\ms-playwright\<playwright 浏览器>\chrome-win64\chrome.exe` | ✅ 已存在，需显式 `executable_path` |
| `tshark` | `(Resolve-ReverseToolSpec -Name 'tshark').Command` 4.6.8 | ✅ 可用 |
| `mitmdump` | `(Resolve-ReverseToolSpec -Name 'mitmdump').Command` | ✅ 可用 |

> ⚠ **Playwright 本机使用注意**（实测）：`playwright` 包虽在，但**未执行过 `playwright install`**，默认查找会失败。
> 必须显式传 `executable_path` 指向已存在的 <playwright 浏览器> 可执行文件，见下方替代路径 B。

---

## 适用信号（Recognition signals）

源文档给出的是 `iv8` 的**最佳适配场景**，这些判断**与运行时无关**，换成本机 `node` / `playwright` 同样成立：

- 需要先有宿主状态，才会产出**某一个具体产物**的 bootstrap 脚本
- probe（探针）链上，`navigator`、`document.cookie`、定时器、或请求 hook 会改变输出的场景
- **本地出网捕获**能揭示决定性 URL、body、headers、或出站 `Cookie` 的场景
- **窄的宿主表面缺口**：`canvas`、WebGL、布局（layout）、或 `Function.prototype.toString`

**反信号（不要用本地宿主）：**

- 字段能塌缩成 Base64 / hex / JSON / SHA / HMAC / AES 等**手写即可在 Python 验证**的标准链
- 流程**每次请求**都仍需要真实渲染、手势、挑战图片、canvas 熵、WebGL 行为、或活的浏览器状态

## 前置（Entry conditions）

### 前置 0：先确认你真的需要「嵌入式宿主」

`embedded-browser-runtime-playbook.md` 的进入 / 退出判据：

**进入**（三者必须**全部**成立）：
1. 在固定输入上，**trivial（平凡）的 Python 重写或一个极小 JS helper 已经不够**
2. 剩下的不匹配**确实依赖宿主可见语义**（`navigator`、`document.cookie`、定时器、解析器顺序、或原生表面探针）
3. 运行时**能把一个具体产物交回 Python** 做真实 HTTP 回放

**任一条为假** → 留在 Python 或一个极小的本地 helper。

**退出**：一旦拿到**一个**决定性产物就停：

- cookie 字符串
- token
- 签名后的 URL
- 导航目标 / 重定向 URL
- 封装后的 body
- 解码后的载荷
- 一个稳定的 getter

> **如果这一点之后流程仍需要真实渲染、手势、或持续的页面状态，那么嵌入式宿主不是最终路径。**

### 前置 1：最小环境起步

用**能证明你在乎的那个分支**的最小环境开路：

- `location`
- `navigator.userAgent`
- 时间 / locale 相关时才加 timezone

> **不要**在 probe 链证明它们重要之前，就仪式性地堆几百个指纹字段。

**关于高熵宿主输入的重要纪律：**

canvas、WebGL、computed style、系统颜色、屏幕尺寸、`deviceMemory`、`hardwareConcurrency`、字体、音频等等，是**溯源产物（provenance artifacts）**，**不是可移植常量**。

另一台机器 / 另一个浏览器 profile 的缓存，可以当**对照 fixture（夹具）**，但**不是合法的运行时输入** —— 除非你明确把最终采集器归类为 snapshot-driven（快照驱动），**并且**报告了捕获范围。

### 前置 2：⚠ iv8 原语清单（未在本机验证）

> ⚠ 本机无 iv8（本机实测：`D:\Tools` 与 Python 环境均无此包）。以下 API 形态供具备该运行时时参考，**未在本机验证**。

源文档教程中提到、值得记住的 `iv8` 原语：

- `JSContext(environment=..., config=..., time_mode=...)`
- `__iv8__.page.load(snapshot)`
- `document.documentElement.innerHTML = ...`
- `__iv8__.eventLoop.sleep / advance / drain`
- `ctx.add_resource(...)`
- `__iv8__.netLog.entries`
- `__iv8__.wrapNative(fn, name)`
- `with_devtools(..., watch_apis=[...])`

**这些方法名请当作「记忆锚点」，不要当作本机可用 API。** 本机对应能力见下方「替代路径」两节。

## 步骤（Working method）

### 一、方法论部分（全部保留，与运行时无关）

#### 1. 选择正确的加载路径（load path）

**用「整页加载」形态**（iv8 的 `page.load(snapshot)`）当：

- inline 或 external 脚本**必须执行**
- 生命周期事件（lifecycle events）有意义
- 请求 hook 或解析器顺序有意义
- HTML 响应、headers 与资源映射是 bootstrap 契约的一部分

**用「纯 DOM 插入」形态**（如 `innerHTML`）当：

- 你只需要 HTML 里的结构或常量
- 不需要脚本执行
- 你想要**最廉价**的宿主表面

**规则：**

- 产物依赖生命周期或自发请求 → 倾向**整页加载**
- 只要解析就够 → **不要**付生命周期那笔成本

#### 2. 时间控制（Time control）

需要快速、确定性的 bootstrap 时，**默认逻辑时间**（源文档：`time_mode="logical"`）。

只在以下情况改用真实墙钟时间（源文档：`time_mode="system"`）：

- 目标**检查真实流逝时间**
- PoW（工作量证明）或时间戳差值依赖墙钟语义

**推荐流程：**

1. 加载页面或脚本
2. **只推进你能证明必要的那个时间量**
3. 产物或出网边界一稳定，**立刻**收割

有用的动作（⚠ 以下为 iv8 形态，**未在本机验证**）：
- `sleep(ms)` —— 推进逻辑时间并 flush 排队工作
- `drain()` —— 时间不再前进时用
- `advance(total, step)` —— 需要帧粒度推进时用

#### 3. 让网络留在本地（Keep network local）

社区 `iv8` 应被当作**纯本地 bootstrap**。

**推荐回放形态：**

1. JavaScript bootstrap 在本地宿主里跑
2. **检查本地出网日志**，找出决定性的 URL、body、headers、出站 `Cookie`、或其他被 wrapper 改写过的请求字段
3. **Python 发真实网络请求**
4. **只有**当本地运行时必须继续时，才注入已捕获的响应
5. **把最终产物提取回 Python**

> **如果出网时的 `Cookie` 头与 `document.cookie` 或客户端自管的 jar 不同，回放时以出网记录为准**，把存储状态只当作产生那个 wire 结果的一个输入。

**不要**让本地宿主悄悄接管真实业务 HTTP。

#### 4. 只补「最小的、可信的面」（Patch the smallest faithful surface）

**按此顺序递进：**

1. 环境字段：`location`、`navigator`、timezone
2. 窄的属性适配器：`Object.defineProperty`
3. **看起来像原生的 shim**（iv8 形态：`__iv8__.wrapNative(...)`）
4. 针对**确切**宿主表面的定向探针或 wrapper

源文档给出的、**可推广**的常见例子：

- `MessageChannel`
- `SharedArrayBuffer`
- `navigator.connection`
- `PerformanceObserver.supportedEntryTypes`
- 特定的 `document.createElement` 分支

**`btoa` 替换前的强制测试向量**（源文档给的，正确，本机已验证其成立）：

测试向量：`btoa("\x00\xffAz")` 必须等于 `"AP9Beg=="`；**`0xff` 以上的码元必须被拒绝**，而不是做 UTF-8 编码。

本机验证：
```powershell
& (Resolve-ReverseToolSpec -Name 'node').Command -e "console.log(Buffer.from([0x00,0xff,0x41,0x7a]).toString('base64'))"
# AP9Beg==   （本机实测）
```

> **规则**：宿主实现通过这个向量就**保留它**。
> **只有**在一条固定的正向向量或拒绝向量**证明**了不匹配之后，才动手 patch。

**规则：**

- **补恰好缺失的那个面**
- 反射（reflection）重要时，让形状**看起来像原生**
- 如果某个实例 hook 被绕过了，**上移到共享边界**，而不是继续加一次性 stub

#### 5. 先探针，后打补丁（Probe before you patch）

**发现缺失表面的高价值手段：**

- 聚焦的 API 访问探针（iv8 形态：`with_devtools(..., watch_apis=[...])`）
- 包在 `window`、`navigator`、`document`、或某个窄宿主对象外的 `Proxy`
- 对 `canvas`、WebGL、layout、或描述符读取的本地 wrapper

**以下属于「证据面」，不是默认插桩对象：**

- `Object.keys`
- `Reflect.ownKeys`
- 描述符读取（descriptor reads）
- `Function.prototype.toString`
- `document.cookie`
- `canvas.toDataURL`
- `getComputedStyle`

> 如果 cookie、storage、script 标签、或资源映射**几乎不改变输出**，
> 那么**怀疑原生表面缺口**，而不是去回放更多 bootstrap。

### 二、替代路径 A：**`node` + `vm` + 自建 stub（本机实测可用）★ 首选**

这是本机对应 `iv8` 全部能力的**可执行替代**。**本机实测跑通**，见下方实测记录。

#### A.1 能力对照表

| `iv8` 能力 | 本机替代 | 本机状态 |
|---|---|---|
| `JSContext(environment=...)` | `vm.createContext(sandbox)` + 自建 sandbox 对象 | ✅ 实测可用 |
| `page.load(snapshot)` | `vm.runInContext(src, sandbox)` 执行捕获的脚本 | ✅ 实测可用 |
| `innerHTML` 插入 | 需要真实 DOM 时改走 playwright，或用轻量 DOM shim | ✅（playwright 侧） |
| `eventLoop.sleep/advance/drain` | **自建定时器队列 + 手动 drain** | ✅ 实测可用 |
| `add_resource(...)` | 在 stub 的 `XMLHttpRequest.send` / `fetch` 里按 URL 返回预置响应 | ✅ 实测可用 |
| **`netLog.entries`** | **自建 `netLog` 数组，在 stub 里 push 出网记录** | ✅ 实测可用 |
| `wrapNative(fn, name)` | 手写一个 `toString` 抛错的包装器，见 A.3 | ✅ 可实现 |
| `watch_apis=[...]` | `Proxy` 包住目标宿主对象，见 A.4 | ✅ 实测可用 |

#### A.2 骨架（本机实测跑通）

下面这段是**本机实测**能工作的最小形态 —— 它建立上下文、自建定时器队列、stub XHR 并**记录出网**（对应 `netLog`）：

```javascript
// harness.js —— node v22.23.3 实测可跑
const vm = require('vm');

const netLog = [];              // 对应 __iv8__.netLog.entries
const timers = [];              // 对应 eventLoop 队列

const sandbox = {
  console,
  // ---- 时间控制：逻辑时间，自建队列 ----
  setTimeout: (fn) => { timers.push(fn); return timers.length; },
  clearTimeout: () => {},
  setInterval: () => 0,         // 长 setInterval 通常只是噪音，可先 stub 掉
  queueMicrotask: (fn) => timers.push(fn),
  // ---- 宿主表面：只补最小必要面 ----
  document: { cookie: '' },
  navigator: { userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)' },
  location: { href: 'https://example.invalid/a' },
  atob: s => Buffer.from(s, 'base64').toString('binary'),
  btoa: s => Buffer.from(s, 'binary').toString('base64'),
  // ---- 出网捕获：对应 netLog ----
  XMLHttpRequest: function () {
    this.open = (method, url) => { this._m = method; this._u = url; };
    this.setRequestHeader = (k, v) => { (this._h ??= {})[k] = v; };
    this.send = (body) => {
      netLog.push({                       // ← 这就是你要的出网记录
        method: this._m, url: this._u,
        headers: this._h ?? {},
        body: String(body),
        cookie: sandbox.document.cookie,  // document.cookie 与出站头的差异要看这里
      });
    };
  },
  fetch: (url, opt) => {
    netLog.push({ method: opt?.method ?? 'GET', url, headers: opt?.headers ?? {}, body: opt?.body });
    return Promise.resolve({ text: () => Promise.resolve('ok'), json: () => Promise.resolve({}) });
  },
};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;

vm.createContext(sandbox);

// 1) 加载捕获的脚本
vm.runInContext(fs.readFileSync('challenge.js', 'utf8'), sandbox);

// 2) drain：把排队的定时器跑完（对应 iv8 的 drain/sleep）
while (timers.length) { timers.shift()(); }

// 3) 收割产物
console.log(JSON.stringify(netLog, null, 1));
```

运行：
```powershell
& (Resolve-ReverseToolSpec -Name 'node').Command harness.js
```

**本机实测记录**（`node v22.23.3`，用一个自造的挑战片段验证 harness 本身）：

```
pending timers: 1
[["open","POST","/api/sig"],["send","T=1&sign=deadbeef"]]
cookie: a=1
```

含义：定时器队列正确捕获并 drain 了 1 个任务；XHR stub 正确记录了 `open`/`send`；`document.cookie` 写入正确。

> ⚠ **诚实声明**：以上验证的是 **harness 骨架本身**（上下文创建、定时器 drain、XHR stub 出网记录、cookie 读写），
> **不是**对任何真实目标的验证 —— 本机没有跑过真实 challenge bundle。

#### A.3 `wrapNative` 的本机实现

`iv8` 的 `wrapNative(fn, name)` 目的是让 `Function.prototype.toString` 返回 `[native code]`。`node` 里手写等价物：

```javascript
function wrapNative(fn, name) {
  const shim = function (...args) { return fn.apply(this, args); };
  Object.defineProperty(shim, 'name', { value: name, configurable: true });
  Object.defineProperty(shim, 'toString', {
    value: () => `function ${name}() { [native code] }`,
    configurable: true, writable: true,
  });
  // 让 Function.prototype.toString.call(shim) 也返回 native 形态
  Object.defineProperty(Function.prototype, 'toString', {
    ...Object.getOwnPropertyDescriptor(Function.prototype, 'toString'),
  });
  return shim;
}
```

> ⚠ 上面对 `Function.prototype.toString` 的处理只是**提示性写法**，实际是否需要覆盖 `Function.prototype.toString.call(shim)`，
> **取决于你的目标用哪种方式检查原生性**（`.toString()` 直接调用 vs `Function.prototype.toString.call()`）。
> **本机未对具体目标验证这一点** —— 目标用哪种检查法，是 `probe` 阶段要确定的第一件事。

#### A.4 `watch_apis` 的本机实现（Proxy 探针）

```javascript
function watchApis(target, names, log) {
  return new Proxy(target, {
    get(t, prop, recv) {
      if (names.includes(String(prop))) log.push({ api: String(prop), at: 'get' });
      const v = Reflect.get(t, prop, recv);
      return typeof v === 'function' ? v.bind(t) : v;
    },
  });
}
```

> ⚠ **别把探针当默认插桩**：只有在**你确实不知道哪个宿主表面是决定性的**时才上 Proxy。
> 目标经常对 `Proxy` 敏感（`Function.prototype.toString`、`ownKeys`、descriptor 检查），探针本身可能改变行为。

### 三、替代路径 B：**`playwright`（真浏览器语义，本机实测可用）★ 需要真实 DOM 时**

当轻量 harness **证不了**（需要真实 canvas / WebGL / 布局 / 真实定时器语义）时升级到本机 playwright。

#### B.1 本机启动形态（⚠ 必须显式 `executable_path`）

本机实测：`playwright` 1.62.0 包在，但**未跑过 `playwright install`**，默认查找失败。必须显式指路径：

```python
# pw_harness.py —— 本机实测可启动、可执行 JS
from playwright.sync_api import sync_playwright

EXE = r'$env:LOCALAPPDATA\ms-playwright\<playwright 浏览器>\chrome-win64\chrome.exe'

with sync_playwright() as p:
    b = p.chromium.launch(headless=True, executable_path=EXE, args=['--no-sandbox'])
    pg = b.new_page()
    pg.goto('https://example.invalid/')     # 必须是真实 origin，见 B.3
    print(pg.evaluate('navigator.userAgent'))
    b.close()
```

**本机实测记录**（对本地 `http://127.0.0.1:8731` 起的静态服务）：

```
title= pw-ok
ua_prefix= Mozilla/5.0 (Windows NT 10.0; Win64; x64) App
cookie= 'a=1'
isNativeToString= function getBoundingClientRect() { [native code] }
```

结论：<playwright 浏览器> 可用；JS 求值可用；`document.cookie` 可用；**原生 `toString` 形态天然正确**（这正是 `iv8` 要用 `wrapNative` 手工模拟的东西）。

#### B.2 用 `page.route` 做「出网捕获」（对应 `netLog`）

**本机实测可用**，这是 playwright 侧的 `netLog` 等价物 —— 它能捕获**被 wrapper 改写之后**的最终请求：

```python
seen = []
def handle(route, request):
    seen.append({
        'method': request.method,
        'url': request.url,
        'headers': dict(request.headers),   # ← 已含 X-Sign 等自定义头
        'post': request.post_data,
    })
    route.fulfill(status=200, content_type='application/json', body='{"ok":1}')

with sync_playwright() as p:
    b = p.chromium.launch(headless=True, executable_path=EXE, args=['--no-sandbox'])
    pg = b.new_page()
    pg.route('**/api/collect', handle)
    pg.goto('http://127.0.0.1:8731/xhr.html')
    pg.wait_for_timeout(700)
    b.close()
```

**本机实测捕获到**（页面里是 `xhr.open("POST","/api/collect"); setRequestHeader("X-Sign","deadbeef"); send("T=1&sign=deadbeef")`）：

```json
{
 "method": "POST",
 "url": "http://127.0.0.1:8731/api/collect",
 "headers": {
  "content-type": "text/plain;charset=UTF-8",
  "origin": "http://127.0.0.1:8731",
  "referer": "http://127.0.0.1:8731/xhr.html",
  "x-sign": "deadbeef"
 },
 "post": "T=1&sign=deadbeef"
}
```

> ✅ **`x-sign` 头与 POST body 都被正确捕获** —— 这正是「wrapper 改写后决定性字段」的直接证据。

#### B.3 ⚠ 本机踩过的两个坑

1. **`set_content` 没有可用 origin**：`pg.set_content(...)` 之后执行 `document.cookie='a=1'` 会抛
   `SecurityError: Access is denied for this document`（本机实测）。
   **解决**：用 `pg.goto()` 走一个真实 origin（本地起个静态服务即可）。
2. **默认 chromium 查找失败**：报 `Looks like Playwright was just installed or updated`。
   **解决**：显式 `executable_path`（见 B.1）。

## 判据（Verification checklist）

只有满足以下**全部 6 条**，才可以说「本地宿主这一层搞定了」：

1. **你能事先说出「我要收割的那一个产物」是什么** —— cookie / token / 签名 URL / 导航目标 / 封装 body / 解码载荷 / 稳定 getter。
   说不出 → **你大概还不需要本地宿主**
2. **该产物已在本地复现**，并用**固定输入**与线上样本比对通过
3. **真实 HTTP 由 Python 拥有** —— 本地宿主**没有**接管任何真实业务请求
4. **最小环境补丁清单已写下**：补了哪些面、**省略了哪些默认值**
5. **定时器模式与每一次显式的推进/推进量都已记录**
6. **固定输入校验证明本地输出与线上样本一致**（不是「跑通了」，是**逐字节一致**）

> ⚠ **交付形态必须如实分类**（三选一）：
> - **browser-free**（无浏览器）：✅ 可以
> - **browser-free 但非 runtime-free**（无浏览器但仍依赖本地 JS 宿主）：**必须明说**
> - **runtime-free**（连本地宿主都去掉）：只有当那条明文要求「把运行时也去掉」时才需要追求
>
> **如果用户明确要求移除运行时，却把「browser-free 的中间态」当最终完成交付 —— 这是错的。**

### 快速决策线索（Fast decision cues）

| 情况 | 该做什么 |
|---|---|
| 生命周期或资源执行之后本地输出才变化 | 用**整页加载**形态 |
| 需要重新获取链接的 bootstrap 资产或 runner 脚本 | 用**同一 session、同一有效 origin、同样发现它的 header** |
| 需要的值已经在 DOM 里、脚本不增加价值 | 用**纯 DOM 插入** |
| 反射或 `[native code]` 检查重要 | 做**原生形态 shim**（见 A.3 / 或直接用 playwright） |
| 运行时**已经发出**真实封装请求 | 读**出网日志**（见 A.2 / B.2） |
| 运行时需要本地响应才能继续，但 Python 仍要拥有真实 HTTP | **注入预置响应** |
| **仍然不知道**哪个宿主表面是决定性的 | 上 **Proxy 探针**（见 A.4） |
| —— | **只用一个本地宿主，直到一个决定性产物稳定到足以 Python 回放为止** |

## 常见坑（Common traps）

- 在证明缺失分支之前就**塞满环境指纹**
- 把**另一台宿主**的 canvas / WebGL / 系统颜色 / 字体 / 设备 profile 缓存，当作**实时运行时输入**
- 在静态 DOM 解析就够的时候，用**整页加载**
- 用**全新的客户端或猜测的 origin** 去重新获取链接的 bootstrap 资产，而不是用**发现它们的那条 session 链**
- 在注入的已签发状态已经能解锁运行时的情况下，还去**回放整个异步 bootstrap**
- **不做回放验证**，就把同一个签名后缀 / header / token / `Cookie` 样本，用到页面、关键词、referer、时间戳、正文的各种变化上
- 拿到**一个 getter、一个 cookie、或一个出网边界**就够了，却还**留着宽泛的 harness**
- 把**宿主保真度缺口**误判成**签名器坏了** —— 特征是本地产物**明显更短**、或**结构上更干净** than 线上
- 让本地宿主变成**隐蔽的浏览器替身**，而不是一个**窄的宿主运行时**
- 把本地宿主当成**最终 HTTP 执行器**，而不是**本地 bootstrap 桥**

> ⚠ **本机补充的坑**（源文档未列，本机实测遇到）：
> - `pg.set_content()` 后写 `document.cookie` 会 `SecurityError` → 必须 `goto()` 真实 origin
> - playwright 未 `install` 时默认查找失败 → 必须显式 `executable_path`
> - `node` harness 里**忘记自建定时器队列**会导致 bootstrap 只跑一半 —— 这是最常见的静默失败
> - `btoa` 的 Latin-1 语义：宿主实现**必须**拒绝 `0xff` 以上的码元，不能偷偷做 UTF-8 编码

## 相关（Related）

- `embedded-browser-runtime-playbook.md` —— **先读这份**：进入 / 退出判据、「不要跨层跳跃」阶梯
- `jsvmp-analysis-playbook.md` —— 本地执行 vs 反虚拟化的取舍（源文档第 3 步）
- `environment-patch-playbook.md` —— 补宿主的详细方法；替代路径 A 的 stub 设计可参考其 `../../profiles/env-patch/`
- `local-challenge-executor-playbook.md` —— 把上面的能力**契约化**（JSON 输入 / 输出），用于挑战型目标
- `opaque-runtime-profile-playbook.md` —— 当本地产物依赖捕获的环境 / 不透明块时
- `../observe/hook-techniques.md` —— 浏览器侧 hook 的本机可行写法（配合 playwright 路径）
- `../deliver/delivery-gate-playbook.md` —— 「browser-free vs runtime-free」交付门的判定
- `../observe/anti-debug-playbook.md` —— 何时转离线

---

## 源文档改编说明（非勘误）

源文档通篇以 `iv8` 为**既定事实**。改编时做了三处**结构性**调整（均不改变方法论）：

1. **顶部加了本机状态警示块**，明确 `iv8` 本机不存在，并给出本机真实可用的替代工具链（含 playwright 需显式 `executable_path` 的本机实测注意事项）。
2. **每一处具体 API**（`JSContext`、`page.load`、`sleep/advance/drain`、`add_resource`、`netLog.entries`、`wrapNative`、`with_devtools(watch_apis=)`、`time_mode`）都加了 ⚠ 标注，说明**未在本机验证**，并在新章节给出**本机已实测的对应实现**。
3. **新增替代路径 A / B 两整节**，分别对应：
   - **A**：`node` + `vm` + 自建 stub —— 逐项对照 `iv8` 的 8 项能力，并给出**本机实测输出**
   - **B**：`playwright` —— 真浏览器语义 + `page.route` 出网捕获，并给出**本机实测捕获到的请求头与 body**

源文档的技术判断（时间控制策略、`netLog` 优先于 `document.cookie`、`btoa` 向量、probe-then-patch 顺序、边界选择）**全部保留**，且经核对**未发现错误**。