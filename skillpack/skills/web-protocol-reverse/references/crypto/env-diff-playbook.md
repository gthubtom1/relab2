# 环境差分手册（Environment-Diff Playbook）

> **来源声明**：本文改编自外部仓库 `aoyunyang/spider-king-skill`（MIT License）的 `env-diff-playbook.md`。原文为英文，此处译为中文并按本包六段式规范重排；技术术语保留英文原词并附中文，AI 检索时中英文均可命中。源文档技术内容经核对**未发现错误**，未作技术性修改。**本机化重点**：抓包与重放一律改用本机 **tshark / mitmproxy**（源文档提到的 `reqable` 本机无），并给出本机命令。
>
> **什么时候用**：
> - 目标跳转到**不同域名**或一个**包装页（wrapper page）**
> - **同一个固定输入**下，浏览器输出与本地输出不一致
> - 明显补丁都打过了，**Node 或 Python 仍与线上页面不同**
> - 请求看着对，但**服务端仍不接受**，或**本地解码仍失败**
>

> ★★ **本机 playwright 必须显式指定浏览器**（2026-10-10 实测）：
> `launch()` 默认启动会报 `Executable doesn't exist at %LOCALAPPDATA%\ms-playwright\chromium_headless_shell-1234\...`
> —— python 包期望 1234，本机装的是 **1243**，版本号对不上。
> **可用写法**：`p.chromium.launch(channel="msedge")`（实测能起、能渲染、能读 DOM），
> 或 `launch(executable_path=<显式路径>)`。照抄裸 `launch()` 一定失败。
> 

---

## 核心规则（Core rule）

> **环境不匹配是证据，不是向自动化投降的理由。**

这句话是整篇的立场声明：**差异本身就是定位信息**。它不该让你放弃自动化，而该让你**往上一层缩小范围**。

## 适用信号（Recognition signals）

- 落地页**可能是个包装页**，而不是真正的业务逻辑
- 同一固定输入，**两边输出对不齐**
- 明知签名器代码没问题，**输出仍然不同** —— 说明差异在**环境**而非**算法**
- 请求字段看着都对，**但服务端不接受**
- 响应**形状看着对**，但**解析出来的数据是错的**

## 前置（Entry conditions）

1. **一条成功样本 + 一条失败样本**。差分没有基线就是空谈。
2. **wire 可见性**。本机两条路：
   ```powershell
   # 方式一：mitmproxy 实时观察/改写（本机可用）
   & (Resolve-ReverseToolSpec -Name 'mitmdump').Command --listen-port 8899 --save-stream-file flow.mitm
   # 方式二：tshark 离线读 pcap（本机可用）
   & (Resolve-ReverseToolSpec -Name 'tshark').Command -r flow.pcapng -Y "http.request" -T fields -e http.request.full_uri
   ```
   ⚠ 源文档语境里的 `reqable` / HAR **本机无**，用上面两条替代。
3. **完整重定向链可记录**。
4. **两个可对照的执行环境**：浏览器 / 本地（`node` 或 Python）。

---

## 步骤（Working method）

### 1. 重定向与包装页分诊（Redirect and wrapper-page triage）

**在逆任何签名器之前**，先确认落地页**是不是一个包装页（wrapper）**：

1. **记录完整重定向链**
2. 对比**初始页**、**最终页**、与**真实网络请求**三者
3. 检查最终页是否**重写了**：
   - 请求路径
   - 头（headers）
   - body 字段
   - cookies
4. **把「兼容性页面 / 迁移页面」当作包装页**，而不是规范的业务逻辑

本机做法（读出重定向链）：
```powershell
# 直接跟一次重定向，看最终落点（本机可用）
curl -s -o /dev/null -w "final=%{url_effective} code=%{http_code} redirects=%{num_redirects}\n" -L -A "<你的UA>" "<入口URL>"
```

### 2. **永远分成四层**

1. **传输层 wrapper 逻辑**（transport wrapper logic）
2. **核心签名器或编码器逻辑**（signer / encoder）
3. **响应解码器逻辑**（response decoder）
4. **服务端接受条件**（server acceptance conditions）

> **不要**因为哈希算对了，就认为**整个协议**都对了。

这四层必须**分别**验证。哈希对而「服务端接受条件」不满足，是最常见的误判。

### 3. 标准 vs 被 patch 的工作流（Standard-vs-patched workflow）

当某个 helper 看着像 MD5、SHA、AES、HMAC、或 Base64，**行为却怪**：

1. 在**固定输入**上抓一条浏览器输出
2. 在**相同固定输入**上跑本地 helper
3. **四层对比**：
   - 最终输出
   - **输入归一化**（input normalization）
   - **字节转换**（byte conversion）
   - **中间值**
4. **检查从属 helper**，而不只是顶层函数

**被 patch 的强信号：**

- 标准库**持续**不一致
- **最后一轮之前**，中间缓冲区就已经分叉
- **旁路 helper** 做了自定义掩码、字节交换、或字母表翻译

详见 `crypto-patterns.md`。

### 4. 收缩策略（Narrowing strategy）

**逐层减少问题：**

1. 浏览器里的活页面
2. 隔离出来的页面 helper + 其直接依赖
3. **带最小环境补丁**的本地运行时
4. 实践可行的话，**纯 Python 重实现**

**每一层都用同一个固定输入测试，并保留同一批中间值。**

**目标：找到「仍能复现线上输出的最小本地环境」。**

> 这一层的判据是**最小性**：不是「能不能跑」，而是「删掉哪一块它就不对了」。

### 5. 首选交付形态（Preferred delivery shapes）

**选能接受的最少交接：**

#### A. 纯 Python

逻辑**完全理解**且易于移植时用。

#### B. Python + 隔离的 JS helper

当：

- **HTTP 客户端应当留在 Python**
- **那个确切的 helper** 在 JS 里已经稳定
- **今天移植只会增加风险、没有实际收益**

#### C. Python + 极小的本地补丁面

当：

- **某个 helper** 仍需要一个小型打过补丁的运行时
- 运行时是**本地、显式、不依赖浏览器会话**的
- **所有输入输出都可固定样本验证**

#### 永不接受：

- **以浏览器驱动的回放作为最终交付**
- **把页面上下文的 `fetch` 当作采集器**
- **把隐藏的 profile 状态算作协议的一部分**

---

## 判据（Verification checklist）

**只有满足以下全部 5 条**，才可以说「环境不匹配已解决」：

1. **最小的本地运行时**在**固定输入**上复现了线上 helper 输出
2. **最终请求成功至少两次**
3. **任何解码步骤**在一条**抓到的原始 payload** 上复现了线上结果
4. **最终采集器不依赖浏览器自动化**
5. **残留的本地补丁面被显式记录下来**

### 分层归因判据（本文特有的自检）

在宣布「解决」之前，**先对四层逐层签收**：

| 层 | 签收标准 | 常见误判 |
|---|---|---|
| 1 传输层 wrapper | wrapper 的改写逻辑已被重建，且输出与线上一致 | 以为 wrapper 只是「转发的」 |
| 2 签名器 / 编码器 | 固定输入上逐字节对齐 | 以为「哈希对」= 层 1 也对 |
| 3 响应解码器 | 在抓到的原始 payload 上复现 | 形状对了就认为解码对了 |
| 4 服务端接受条件 | 真实回放**至少两次**成功 | 以为「本地跑通」= 服务端接受 |

> ⚠ **四层必须各自独立签收。**
> 任何一层「顺带看起来没问题」，都不能代替它的单独验证。

> ⚠ **不构成完成**的典型情形：
> - 「本地能跑出格式正确的结果」
> - 「解码不报错了」
> - 「响应字段都在」—— 字段名对齐 ≠ 值对齐

---

## 常见坑（Common traps）

- **跳过第 1 步（包装页分诊）就开始逆签名器** —— 逆了半天，逆的是包装逻辑
- **把「哈希算对了」当成「协议对了」** —— 四层里还有三层没验
- 只比**最终输出**，不比**输入归一化 / 字节转换 / 中间值** —— 于是找不到分叉点
- **只看顶层 helper**，不看**从属 helper**（真正被 patch 的常在下一层）
- **在第 4 层失败时仍继续打环境补丁** —— 那其实是服务端接受条件问题
- **把「本地解码失败」当成「抓的 payload 不对」** —— 先分清是解码层还是抓包层
- 误信终端 / shell 显示来判断参数值 —— 见 `offline-inline-deob-playbook.md` 的 Unicode 分隔符一节
- **把浏览器 profile 的状态写进最终交付**，让采集器依赖隐式环境

---

## 源文档勘误（改编时修正）

1. **【失效交叉引用，已修正】** 源文档第 6 节「Network sanity checks」之前的正文没有指向其他 playbook，但本文补入了本包实际路径的交叉引用（`crypto-patterns.md`、`offline-inline-deob-playbook.md` 等），**均为同包实际存在的文件**，非编造。

2. **【术语澄清，未改结论】** 源文档第 5 节把交付形态分为 A/B/C 三类，并列出「Never accept」清单。改编时**保留全部三类与全部禁止项**，仅在判据段补上了源文档没有的**「四层归因自检表」** —— 这是把源文档第 2 节（分四层）的隐含要求**显式化为可签收的判据**。
   ⚠ 该表是**改编时新增的验收结构**，不是源文档原有内容。

---

## 相关（Related）

- `environment-patch-playbook.md` —— 本篇定位「**怎么找到差异**」，那篇讲「**怎么补上**」（15 步方法 + 边界选择规则）
- `iv8-runtime-cheatsheet.md` —— 本机可执行的本地宿主（`node` + `vm` / `playwright`，均附实测输出）
- `crypto-patterns.md` —— 第 3 步「标准 vs 被 patch」的算法核对
- `../observe/transport-wrapper-playbook.md` —— 第 1 层「传输层 wrapper」的展开
- `../deliver/response-decode-playbook.md` —— 第 3 层「响应解码器」的展开
- `../deliver/pure-python-rebuild-playbook.md` —— 交付形态 A（纯 Python）
- `../deliver/delivery-gate-playbook.md` —— 判据第 4、5 条的交付门
- `../state/cookie-provenance-playbook.md` —— 第 1 层里 cookies 被重写的排查