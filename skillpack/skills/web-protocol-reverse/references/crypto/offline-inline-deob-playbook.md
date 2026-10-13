# 离线内联反混淆手册（Offline Inline-Deob Playbook）

> **来源声明**：本文改编自外部仓库 `aoyunyang/spider-king-skill`（MIT License）的 `offline-inline-deob-playbook.md`。原文为英文，此处译为中文并按本包六段式规范重排；技术术语保留英文原词并附中文，AI 检索时中英文均可命中。源文档技术内容经核对**未发现错误**，未作技术性修改。
>
> **什么时候用**：
> - 浏览器 DevTools 或 `js-reverse` 因为反调试代码变得不稳定
> - 页面把大段逻辑**内联**在 HTML 里，而不是从外部文件加载
> - 签名依赖一个 packed（打包）载荷，例如 `eval(atob(...))`
> - 一个「标准」哈希和页面内结果对不上，**尽管函数名看着眼熟**
> - 某个请求参数含**异常分隔符**或 Unicode 分隔符
> - 一个 obfuscator.io 类 bundle 需要先在本地还原字符串表，签名器才可读
>

> ★★ **本机 playwright 必须显式指定浏览器**（2026-10-10 实测）：
> `launch()` 默认启动会报 `Executable doesn't exist at %LOCALAPPDATA%\ms-playwright\chromium_headless_shell-1234\...`
> —— python 包期望 1234，本机装的是 **1243**，版本号对不上。
> **可用写法**：`p.chromium.launch(channel="msedge")`（实测能起、能渲染、能读 DOM），
> 或 `launch(executable_path=<显式路径>)`。照抄裸 `launch()` 一定失败。
> 

---

## 适用信号（Recognition signals）

见顶部「什么时候用」的六条 —— 它们既是**进入条件**，也是**本文涉及范围的完整清单**。

## 前置（Entry conditions）

1. **完整的 HTML 快照**。第一条动作就是保存全文；不要在「在线反复戳」和「离线还原」之间来回横跳。
2. **一个能执行 JS 的本机宿主**：
   ```powershell
   & (Resolve-ReverseToolSpec -Name 'node').Command -v
   ```
3. **提取 HTML 与脚本的工具**。本机两条都可用：
   ```powershell
   # 方式一：用 playwright 取渲染后 DOM（能拿到运行时注入的脚本）
   # ⚠ 本机必须显式 executable_path，且 goto() 真实 origin 而非 set_content
   # 方式二：纯静态解析 —— python 内置 html.parser，无需装包
   & (Resolve-ReverseToolSpec -Name 'pyre').Command -c "from html.parser import HTMLParser; print('html.parser ok')"
   ```

---

## 步骤（Working method）

### 1. 什么时候该停止与线上页面缠斗（When to stop fighting the live page）

出现下列任一情况，就**转离线提取**，而不是继续反复戳线上运行时：

- debugger 循环，或 `setInterval(debugger, ...)`
- 反调试代码造成的 console 洪水
- MCP 求值调用反复超时
- 页面加载之后逆向工具断连
- 某个浏览器家族起不来，因为另一个已经占用了 profile 目录

**回退路径：**

1. 保存完整 HTML
2. 抽取所有内联脚本
3. 保存相关的外部资产
4. 本地反混淆并测试

> **如果只有一个浏览器工具家族能占用目标**，那就让它负责 wire 证据，
> 然后用 `node` 或 Python **离线**完成静态还原。
> **不要**为了仪式感再造第二个活浏览器。

### 2. 先抽取页面结构（Extract the page structure first）

**在解码任何东西之前**，先记录：

1. script 标签数量
2. 内联脚本的顺序
3. 外部脚本的顺序
4. 页面是否在 packed 代码运行**之前**就 monkey-patch（猴子补丁）了 `$.ajax`、`fetch` 或 XHR

> **不要假设 script 数量只是装饰性的。**
> 有些页面从下列值派生偏移量：
> - `$('script').length`
> - DOM 节点计数
> - 元素属性
> - query 串标志
>
> **这些值可以直接改变解码后的载荷。**

### 3. 内联载荷还原模式（Inline payload recovery pattern）

**常见序列：**

1. 一个巨大的编码字符串被赋给 `window.a`
2. 一个循环用**基于索引的偏移量**变换每个字符
3. 结果变成一个 base64 字符串
4. `atob(...)` 产出第二阶段脚本
5. `eval(...)` 运行真正的逻辑

**推荐工作流：**

1. 抽取编码字符串与 decoder
2. 在本地**复现完全一致的偏移数学**
3. 恢复 base64 载荷
4. base64 解码得到第二阶段源码
5. **只隔离**回放所需的签名器或加密段

### 4. 字符串表与 rotate IIFE 还原

当保存下来的资产是**单行**或字符串表密集时：

1. **任何改写之前**，先保存原始文件字节
2. 用**括号感知（brace-aware）的匹配**抽取字符串数组函数、decoder 函数、rotate IIFE —— 必须**尊重转义引号**
3. **只在本地**运行那一层 decoder，dump 出「索引 → 字符串」映射
4. **分两遍**改写：
   - 第一遍**展开 member-map 对象**
   - 第二遍**替换 `decoder(hex)` 调用点**
5. **归一化 hex 键**：若 dump 用 `"c7"`，则用它匹配源码里的 `0xc7`（去掉 `0x` 前缀）
6. 需要按行阅读时再 beautify（美化）；**单行文件让朴素行号完全无用**
7. **一旦** preimage、helper、或 wrapper 边界已经可恢复，**就停**

> ⚠ 若通过「JSON 序列化的文件路径」写出了求值工具的输出，
> **必须先 JSON 解码**，再把该文件当 JavaScript 源码处理。

### 5. 旧式哈希警告（Legacy hash warning）

**不要假设** `md5`、`sha1`、`sm3` 或类似名字意味着标准库等价。

**需要验证的事项：**

- 自定义的 `chrsz` 或字符串宽度设置
- 自定义的字符串 → 字（word）转换
- 小端 vs 大端的假设
- 被 patch 的常量或被改动的轮数
- hex 编码顺序
- 由**原生函数检查**选出的、环境相关的常量表

> **若页面自带自包含的哈希实现，先保留那个实现。**
> **只有**在固定输入上证明输出确实匹配之后，才替换为标准库版本。

详见 `crypto-patterns.md` 的「标准摘要家族被魔改」。

### 6. Unicode 分隔符安全（Unicode delimiter safety）

**请求值含异常分隔符时，把它们保持显式。**

**做法：**

- 用 `\\u4e28` 这样的转义，而不是粘贴一个显示字形
- 在生成的 JS 与 Python 输出里**使用转义字符串**
- **不要**信任终端或 shell 的显示来做正确性判断

**为什么重要：**

- console 输出可能把该字符替换成 `?` 或另一个字形
- 复制粘贴的值可能被编码**静默破坏**
- **一个正确的哈希 + 一个坏掉的分隔符，仍然会服务端校验失败**

---

## 判据（Verification checklist）

只有满足以下**全部 5 条**，才可以说「这个页面离线还原完了」：

1. **完整 HTML 与所有内联 / 外部脚本都已落盘**，且**原始字节快照保留**
2. **第二阶段源码已恢复** —— `eval(atob(...))` 的载荷已被解出为可读源码
3. **回放所需的最小切片已隔离** —— 签名器 / 加密段可独立调用
4. **隔离出来的实现产出与原页面一致的签名值** —— 用固定输入向量验证，**不是**「看起来对」
5. **Unicode 分隔符已显式验证** —— 含分隔符的请求值**真的**被服务端接受过一次

> ⚠ **不构成完成**的典型情形：
> - 「美化完了，能读了」 —— 读得懂 ≠ 能 replay（见 `obfuscation-guide.md` 的判据）
> - 「`eval` 能跑出结果」 —— 但结果没和原页面比对过
> - **花费超过协议 replay 所需的去混淆量**（违反本文核心约束）

---

## 常见坑（Common traps）

- 在找到真实请求之前就把整个 bundle 美化（例外：单行文件导致搜索完全不可用）
- 忽略内联脚本和旁路资产
- 丢失原始变量名，导致后续无法 diff
- **只替换 hex 字面量，漏掉 `decoder(map.key)` 形态**
- 把 dump 键（如 `"c7"`）当成与源码记号（`0xc7`）不匹配
- 把逗号表达式的返回值读成 `void`，而真实值是右侧那个调用
- **把整个浏览器当交付形态**，而不是把隔离出来的 `signer.js` 当交付形态
- 直接把工具输出当源码用，**忘了先 JSON 解码**
- 通过终端复制含 Unicode 分隔符的值

## 相关（Related）

- `obfuscation-guide.md` —— 第 4 步的完整展开，含本机 `node` harness 骨架
- `crypto-patterns.md` —— 第 5 步之后的算法核对（含 ROTL / 位宽陷阱）
- `../observe/anti-debug-playbook.md` —— 第 1 步「停止缠斗」的判定与绕过手段
- `../observe/hook-techniques.md` —— 断连前该抢哪些证据
- `../../../js-reverse/references/local-rebuild.md` —— 还原之后的本地重建
- `../deliver/pure-python-rebuild-playbook.md` —— 判据第 4 条之后的移植路径