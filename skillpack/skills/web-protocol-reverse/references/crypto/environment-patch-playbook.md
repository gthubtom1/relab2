# 环境补丁手册（Environment Patch Playbook）

> **来源声明**：本文改编自外部仓库 `aoyunyang/spider-king-skill`（MIT License）的 `environment-patch-playbook.md`。原文为英文，此处译为中文并按本包六段式规范重排；技术术语保留英文原词并附中文，AI 检索时中英文均可命中。源文档技术内容经逐条核对**未发现错误**，未作技术性修改。**本机化重点**：原文提到的浏览器 hook，本机给出了 **playwright 的对应写法**（本机实测可用）。

> ★★ **本机 playwright 必须显式指定浏览器**（2026-10-10 实测）：
> `launch()` 默认启动会报 `Executable doesn't exist at %LOCALAPPDATA%\ms-playwright\chromium_headless_shell-1234\...`
> —— python 包期望 1234，本机装的是 **1243**，版本号对不上。
> **可用写法**：`p.chromium.launch(channel="msedge")`（实测能起、能渲染、能读 DOM），
> 或 `launch(executable_path=<显式路径>)`。照抄裸 `launch()` 一定失败。
> 
>
> **什么时候用**：抽出来的逻辑在本地运行时**能跑**，但**输出仍与页面对不上**。
>

---

## 适用信号（Recognition signals）

### 常见的不匹配来源（Common mismatch sources）

**缺全局（missing globals）类：**
- 缺失的全局对象
- **不同的 user agent 分支**
- **DOM 派生的常量**
- 文本编码假设
- `Date.now()` 或随机数的精度差异
- 调度器、定时器、或微任务的差异
- **环境表面、polyfill、hook、init、trigger 之间的加载顺序错误**

**宿主对象契约类（host-object contract）：**
- 被旁路脚本 patch 的 helper 函数
- **被原型重写、重绑定、或 wrapper 替换绕过的实例级 hook**
- 只在稍后从 cookie、storage、或某个缓存对象里消费的**异步 bootstrap 状态**
- **未实现的原生表面**，例如 `canvas`、WebGL、布局度量、或样式计算 —— 它们会**悄悄压扁**指纹或验证器载荷
- **宿主对象契约不匹配**：描述符（descriptor）、原型链、构造函数 identity、枚举（enumeration）、原生形态函数表面
- **返回的子对象形状不匹配**：方法存在，但它**产出的对象与浏览器契约不同**
- **生命周期语义缺口**：活动集合（live collection）、索引槽位（indexed slots）、attach / detach 行为、或「只在 attach 期间才应存在」的对象
- **JS 引擎 / 宿主版本漂移**，改变内建可用性、原生函数自有属性列表、或构造函数表面
- 因**宿主 API 返回 null** 而导致的**结构性缩短输出** —— 而不是业务逻辑错了

### 快速判别线索

| 现象 | 最可能的类别 |
|---|---|
| 产物**明显更短**、字段缺失 | **原生表面缺口**（`canvas` / WebGL / layout 返回 null） |
| 只在**某些 `j` 值或某些页**失败 | 位宽 / 顺序问题，不是宿主 |
| 名字都在，但行为靠**描述符 / `ownKeys` / `instanceof`** 分支 | **宿主对象契约**，不是缺全局 |
| 运行时**克隆或重绑定**了 helper | 你的 hook **位置太低** |
| cookie / storage / 脚本注入**几乎不改变输出** | 真正探测的是**原生表面** |

## 前置（Entry conditions）

1. **固定输入向量** —— 同一组输入下的页面输出与本地输出，两者都要有。
2. **宿主分类的前置判断**（见下面「步骤」第 1 步）—— **先分类，再动手**。
3. **本机执行宿主**：
   ```powershell
   & (Resolve-ReverseToolSpec -Name 'node').Command -v   # v24.20.0
   ```
   需要真实 DOM / canvas / 原生 `toString` 时升级到 playwright（本机实测可启动，见顶部说明）。
4. **加载顺序契约已画出来** —— 环境表面 → polyfill → hook → init → trigger，这四者的顺序**本身就是契约**。

---

## 步骤（Working method）

源文档 15 步**全部保留**，按执行顺序重排。

### 1. **先分类缺口**

三选一：

- **缺失表面（missing surface）** —— 根本没有这个 API
- **加载顺序契约（load-order contract）** —— 都有，但顺序错了
- **宿主对象契约不匹配（host-object contract mismatch）** —— 名字在，形状 / 描述符 / 生命周期不对

### 2. 在**相同固定输入**上比对 helper 输出

### 3. **先比结构度量，再追语义**

长度、重复块、字段是否存在 —— 这些比语义便宜得多。

### 4. 找到**第一个发散的中间值**

### 5. 若 cookie / storage / script / resource 注入**几乎不改变输出**，去查**究竟哪些宿主 API 被探测**

### 6. **记录决定性方法调用的实参和返回的子对象形状**，不只是属性读取

当这些调用门控后续分支时，属性 get 是不够的。

### 7. **分层稳定环境**

- **第一层**：基础 DOM、BOM、以及显然的标量值
- **第二层**：描述符、原型链、构造函数 identity、枚举、以及返回对象形状
- **第三层**：高熵指纹表面 —— `canvas`、WebGL、音频、字体、布局、样式 —— **只有证据证明它们重要之后**才动

### 8. 若名字都在，但探针**分支在描述符 / `ownKeys` / `instanceof` / 构造函数检查 / 原生形态函数上**，**先补契约，而不是继续加全局**

### 9. 若探针依赖**活动集合、索引槽位持久性、或 attach/detach 迁移**，**在原型边界上补生命周期契约**，而不是返回静态占位符

### 10. 若某个本地引擎版本在宿主契约上**显著更接近**，**先锁定那个版本**，而不是去重写更多业务逻辑

### 11. 若 hook 消失、产物仍为空、或行为**只在 bundle 加载之后**才变，先证明**环境表面、polyfill、hook、init、trigger 是不是加载顺序错了**

### 12. **只补最小的那个缺失表面 / 权威边界**，且下游代码绕不过它

### 13. 若运行时稍后**只读一个服务端下发的 cookie、storage 值、token、或缓存 blob**，先测**注入一个已验证样本**能否把异步 bootstrap 从热路径上移走

### 14. **让结构性失败继续传播**；只抑制**你能论证的那一个**可恢复错误类

### 15. **把补丁限制在 helper 运行时局部**，而不是拖进一整个浏览器依赖

## 判据（Verification checklist）

### 先记住这句话

> **「加载成功」只是一个里程碑。**
> 一个不再抛异常的 helper，**仍然**可能吐出一个空的、降级的、或结构性错误的产物。

### 上线回放之前，必须做（源文档 Verification rule）

1. **在「你打算交付的那套」补丁环境、hook 位置、与加载顺序下，重跑决定性产物**

2. **按结构优先**比对固定输入的浏览器输出与本地输出：
   长度、前缀、分段数、字段是否存在、编码、或发出的头与 body

3. **对 hook 驱动的运行时，把顺序当作契约的一部分**：

   ```
   环境表面 / 假传输原语
     → 目标 bundle
       → 捕获 hook 或观察边界
         → init 或 config
           → trigger
   ```

4. 若目标的 polyfill 或 wrapper **替换了你的早期 hook**，把 hook **移到那次替换之后**，或**上移到一个每次调用都必须穿过的稳定边界**

### 完整判据（6 条，全部满足才算搞定）

1. **缺口已被归类**，且分类有证据
2. **第一层与第二层环境已稳定** —— 描述符、原型链、构造函数 identity、枚举、返回对象形状
3. **加载顺序契约被显式验证** —— 四层顺序写下来了，且按该顺序重跑通过
4. **hook 位置在下游绕不过的边界上**，且有证据证明目标无法绕过
5. **固定输入的浏览器输出与本地输出按结构一致** —— 长度、前缀、字段、编码
6. **真实回放成功至少两次**

> ⚠ **不构成完成**的典型情形：
> - 「helper 加载不报错了」
> - 「异常变少了」
> - 「cookie / token 形状看着合理」
> - **把结构性缩短的产物当成答案质量问题**（那是环境证据）

---

## 本机参考路径：playwright 侧的 hook 写法

> 原文提到「浏览器 hook」但未给代码。本节给出**本机 playwright 的对应写法**。
> 下方代码形态在本机实测跑通（对本地静态服务），**但目标 hook 本身未在本机验证**。

### ⚠ 本机前置（实测）

```python
# 本机 playwright 未执行过 `playwright install`，默认查找失败。
EXE = r'$env:LOCALAPPDATA\ms-playwright\<playwright 浏览器>\chrome-win64\chrome.exe'
# 且必须 goto() 真实 origin —— set_content() 后写 document.cookie 会抛
# SecurityError: Access is denied for this document（本机实测）
```

### 形态 1：在**原型边界**上打补丁（对应「边界选择规则」）

这是源文档「优先原型方法，而不是实例」的本机落地：

```javascript
// 在页面加载前注入（playwright 的 add_init_script 形态）
XMLHttpRequest.prototype.open = new Proxy(XMLHttpRequest.prototype.open, {
  apply(target, thisArg, [method, url]) {
    window.__egress = window.__egress || [];
    window.__egress.push({ method, url, at: 'open' });
    return Reflect.apply(target, thisArg, [method, url]);
  },
});
```

Python 侧：
```python
pg.add_init_script(open('patch.js', encoding='utf-8').read())
pg.goto(REAL_URL)     # ⚠ 必须真实 origin
```

### 形态 2：在**出网边界**上观察（对应「请求出网、改写之后、真实 HTTP 之前」）

```python
def handle(route, request):
    # 这里是 wrapper 改写之后的最终形态 —— 最权威的观察点
    observed.append({'method': request.method, 'url': request.url,
                     'headers': dict(request.headers),
                     'post': request.post_data})
    route.continue_()      # 或 route.fulfill(...) 注入响应

pg.route('**/*', handle)
```

本机实测：`page.route` 能正确捕获**自定义头**（如 `x-sign`）与**完整 POST body** —— 见 `iv8-runtime-cheatsheet.md` B.2 的实测记录。

### 形态 3：用 **Proxy** 探针发现「究竟哪些 API 被探测」

对应源文档步骤 5 与「watch_apis」：

```javascript
window.__probe = [];
window.navigator = new Proxy(navigator, {
  get(t, p, r) { window.__probe.push(String(p)); return Reflect.get(t, p, r); }
});
```

```python
print(pg.evaluate('window.__probe'))   # 这就是「哪些宿主表面被探测」的答案
```

> ⚠ **探针本身会改变行为** —— 目标可能对 `Proxy` 敏感（`Function.prototype.toString`、`ownKeys`、descriptor 检查）。
> 探针只用于**发现**，确认之后要换成**真实形状的窄补丁**。

---

## 常见坑（Common traps）

- 运行时**克隆、重绑定或在上游替换**了方法，你去 patch 了一个对象实例
- 修完所有 undefined，却**忽略环境表面、polyfill、hook、init、trigger 之间的加载顺序**
- 签名器**只读一个已签发的 cookie / storage 槽 / token**，你却回放了整个异步 bootstrap
- 复制 cookie / storage / 脚本 / 资源快照，而运行时实际**分支在 `canvas`、WebGL、布局、样式、或原生描述符上**
- **只记录属性 get**，而决定性分歧藏在**方法实参**或**返回子对象的结构**里
- **真实分歧是描述符 / 原型 / 构造函数 / 原生表面形状**，你却在不断加全局
- **基础名称、描述符、返回对象契约还没稳定**，就直奔 `canvas` / WebGL / 音频 / 字体打补丁
- 用**静态值**填满宿主对象，而运行时检查的是**活动集合长度、索引槽位持久性、或 attach/detach 生命周期**
- 只需要一个全局值，却**把整个 DOM 都打了补丁**
- 把**明显更短的验证器 sidecar** 当成答案质量问题，而不是环境证据
- **在一个 JS 引擎版本下调试、却在另一个版本下交付**，且没有重跑固定输入对齐检查
- **因为 helper 加载不抛错就叫任务完成**
- **吞掉所有运行时错误**，从而掩盖递归、栈溢出、或损坏的 VM 状态
- **在检查环境敏感分支之前就去怪 crypto**

---

## 源文档勘误（改编时修正）

1. **【失效路径，已修正】** 源文档最后一节「Executable profile」指向
   `../../profiles/env-patch/index.md`。
   本包实际路径为 `../../profiles/env-patch/index.md`（本 skill 根目录下），原路径写法会指向不存在的 `references/references/`。已改为同包实际相对路径。
2. **【表述歧义，已澄清】** 源文档「Common traps」里有一条
   > patching the entire DOM when only one global value was needed
   与「Boundar‌y-selection rule」里的「patch the nearest stable boundary」有表面张力。
   两者其实不矛盾：前者说的是**别为一个小缺口引入整个 DOM 依赖**，后者说的是**hook 要打在每次调用必经的边界上**。改编时在判据段显式区分了这两件事。

---

## 相关（Related）

- `env-diff-playbook.md` —— 输出对不上时的**分层与收缩**路径（本文聚焦「怎么补」，那篇聚焦「怎么定位」）
- `iv8-runtime-cheatsheet.md` —— 替代路径 A（`node` + `vm` 自建 stub，本机实测）的 harness 骨架
- `opaque-runtime-profile-playbook.md` —— 当补丁仍需要捕获的环境块时
- `../../profiles/env-patch/index.md` —— 可执行的补环境诊断 profile（本包实际路径）
- `../../profiles/env-patch/references/loading-order.md` —— 加载顺序契约的展开
- `../../profiles/env-patch/references/browser-stubs.md` —— stub 形态参考
- `../../../js-reverse/references/env-patching.md` —— `js-reverse` 侧的补环境总览
- `../observe/hook-techniques.md` —— 浏览器 hook 的其他可行写法