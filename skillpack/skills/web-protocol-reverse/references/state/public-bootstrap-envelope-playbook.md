# 公开引导信封手册（Public Bootstrap Envelope Playbook）

> **来源声明**：改编自 `aoyunyang/spider-king-skill`（MIT License）的 `public-bootstrap-envelope-playbook.md`。英文原文译为中文，术语保留英文原词并附中文，按本包六段式规范重排。
>
> **什么时候用**：页面公开可见，但成功 replay 仍依赖某个 bootstrap（引导）响应、入口路由 cookie，或一层加密的外层信封（outer envelope）。
>
> **平台与本机状态**：`python 3.12`、`curl_cffi`、`tshark 4.6.8`、`mitmdump`、`playwright` 本机可用。`iv8` 与 `reqable` 本机无；凡涉及处已就地标注替代方案。

> ★★ **本机 playwright 必须显式指定浏览器**（2026-10-10 实测）：
> `launch()` 默认启动会报 `Executable doesn't exist at %LOCALAPPDATA%\ms-playwright\chromium_headless_shell-1234\...`
> —— python 包期望 1234，本机装的是 **1243**，版本号对不上。
> **可用写法**：`p.chromium.launch(channel="msedge")`（实测能起、能渲染、能读 DOM），
> 或 `launch(executable_path=<显式路径>)`。照抄裸 `launch()` 一定失败。
> 

---

## 适用信号（When to route here）

出现下列任一症状，走公开引导信封路线：

- 首页或列表页公开，但裸 replay 会失败，**除非先访问一次入口路由**
- 早期端点返回的是公钥、config blob、nonce 种子或一段短字符串，**而不是业务数据**
- 业务请求 post 的是 `{"param":"..."}` 这样的包装体，**而不是可见的表单字段**
- 列表 API 匿名可用，但详情（detail）或提交（submit）API 仍被拒
- UI 上显示一个分类，**而空过滤值返回的是另一个结果集**

## 前置（Entry conditions）

1. **匿名会话能力**。全程不登录，只用匿名 cookie。这一类目标的价值就在于「不需要账号」，前置自然满足。
2. **wire 可见性**（判据依赖）。本机两条路：
   ```powershell
   # mitmproxy 实时观察匿名链路
   D:\EXE\python\Scripts\mitmdump.EXE -p 8899 -w public.mitm
   # tshark 离线读 pcap
   D:\Tools\Wireshark\tshark.exe -r public.pcapng -Y "http.response.code" -T fields -e frame.number -e http.response.code -e http.content_type
   ```
   `reqable` 本机无，HAR 导出路径不适用，改用上面两条。
3. **一条成功 + 一条失败的匿名样本**，用于固定入口路由的作用。
4. **授权边界**：仅在有权访问的目标上操作。

## 步骤（Steps）

### 核心思想

**公开不等于未签名。**

匿名访问、bootstrap 状态、传输信封、权限边界 —— 这是契约里**四个互相独立**的层。把它们混为一谈，就会得出「这页公开，裸请求就行」的错误结论。

### 快速执行路径

1. **冻结公开入口路由**
   记录哪个首个 GET 会种 cookie、触发重定向、或产生可缓存的 bootstrap 状态。

2. **冻结 bootstrap 产物（artifact）**
   保存 bootstrap 端点返回的确切公钥、config blob、nonce 种子或包装元数据（wrapper metadata）。

3. **冻结一条好的业务请求**
   保存 headers、cookies、body、外层包装形态，以及响应形态。

4. **恢复信封构建顺序（envelope build order）**
   逐段证明，不要一次猜：
   - 原始业务载荷
   - **确切的 JSON 序列化形态**
   - 摘要（digest）或签名输入
   - 时间戳 / nonce 注入
   - 最终包装对象
   - 加密或编码
   - 外层字段名，例如 `param`

5. **让隐藏状态显式化**
   把 category、mode、tab、page、sort 这些值变成**显式的协议字段**，而不是依赖 UI 默认值。UI 上「当前就是这个 tab」不代表请求里不需要显式传。

6. **分离权限边界**
   列表、详情、提交三条路由**各自独立测试**。列表成功不证明详情或提交也是公开的。

### 高价值检查项

- 摘要算在**原始业务载荷**上还是**包装后载荷**上？
- JSON 必须紧凑（compact）、键序稳定（key-stable），还是保留非 ASCII？
- 时间戳精度：秒、毫秒、还是有自定义偏移？
- RSA 或类似加密对长载荷是否**分块（chunking）**？
- bootstrap 产物是绑会话、绑页面，还是跨请求可复用？
- cookie 来自入口路由、bootstrap 路由，还是**两者都有**？

## 判据（Verification criteria）

以下 8 项**全部**要在交付说明里显式写出来，缺一项都不算完成：

1. **真实入口路由**（哪条首个 GET 是必须的）
2. **真实 bootstrap 端点**
3. **确切的信封构建顺序**（上面第 4 步那七段的顺序，逐段有证据）
4. **限定匿名会话的 cookie 或 header**
5. **必须显式传的分类（category）与分页字段**
6. **列表与详情的权限边界**（明确哪条公开、哪条不公开）

外加两条可执行判据：

7. 从**冷启动**（全新会话、无 cookie）出发，只按交付说明的步骤，能拿到真实业务响应
8. **最终路径不含浏览器依赖**

> 源文档的 `Minimal handoff notes` 只列了 6 项交接说明。本文补充第 7、8 条为可执行判据 —— 因为「交接说明写清楚了」不等于「照着真能跑通」，必须有一次冷启动复现。

## 常见坑（Common traps）

- 对 Python `dict` 的 `repr()` 求摘要，而不是对**确切序列化的 JSON** 求摘要
- 页面在注入时间戳**之前**做摘要，你却在注入**之后**做
- 用 pretty JSON，而不是 compact JSON
- 忘记 RSA 包装长载荷时的**分块**
- 假定空分类字段与可见 tab 等价
- 只证明了公开列表，就宣称详情访问也解决了
- 直接裸请求，没先走入口路由
- 把 bootstrap 产物当成业务响应去解析
- 摘要算对了，但 JSON 键序不稳定 —— 键序本身就是签名输入的一部分

## 相关（Related）

- `challenge-state-envelope-playbook.md` —— 与本文同源的姊妹篇，处理**挑战驱动**的同一信封族
- `server-js-cookie-bootstrap-playbook.md` —— bootstrap 以可执行 JS 形式返回的形态
- `cookie-provenance-playbook.md` —— 入口路由 cookie 的写入方溯源
- `../observe/transport-wrapper-playbook.md` —— 传输层包装与外层字段的对应关系
- `../observe/structured-transport-playbook.md` —— 结构化传输封装
- `../crypto/pattern-atlas.md` —— RSA 分块、紧凑序列化等常见模式索引
- `../deliver/pure-python-rebuild-playbook.md` —— 判据第 8 条的无浏览器交付形态
- `../contract/report-templates.md` —— 判据 6 项交接说明的落盘模板

---

## 源文档勘误（改编时修正）

1. **源文档的 `Delivery guidance` 有一条自相矛盾的风险**。原文写「only if Python port is not yet cheaper」—— 即先出 JS helper 再移植 Python。但本文判据第 8 条要求最终路径无浏览器依赖。两者可以共存（helper 是本地进程而非浏览器），改编时明确「本地 helper ≠ 浏览器依赖」这一区分，避免读者误读。
2. **源文档的 `High-value checks` 与 `Minimal handoff notes` 有重复**（都涉及 cookie 来源与权限边界）。本文保留两者但角色分开：`High-value checks` 是**要验证的问题**，`Minimal handoff notes` 是**要写下来的交付项**。
3. **源文档 `Fast execution path` 第 4 步的顺序是「原始载荷 → 序列化 → 摘要输入 → 注入 → 包装 → 加密」**，但源文档的 `Common traps` 同时又警告「页面可能在注入后才摘要」。这两处不矛盾（顺序随站点而异），但源文档没有点明它，读者容易误以为顺序是普适的。本文在判据第 3 条中要求「逐段有证据」，正是为此。