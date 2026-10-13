# 加密模式识别（Crypto Patterns）

> **来源声明**：本文改编自外部仓库 `aoyunyang/spider-king-skill`（MIT License）的 `crypto-patterns.md`。原文为英文，此处译为中文并按本包六段式规范重排；技术术语保留英文原词并附中文，AI 检索时中英文均可命中。改编中修正了源文档一处**技术性错误**（见文末「源文档勘误」）。
>
> **什么时候用**：签名、加密、或某个 helper（辅助函数）的输出看起来「可疑」——名字像标准算法，行为却对不上。
>

> ★★ **本机 playwright 必须显式指定浏览器**（2026-10-10 实测）：
> `launch()` 默认启动会报 `Executable doesn't exist at %LOCALAPPDATA%\ms-playwright\chromium_headless_shell-1234\...`
> —— python 包期望 1234，本机装的是 **1243**，版本号对不上。
> **可用写法**：`p.chromium.launch(channel="msedge")`（实测能起、能渲染、能读 DOM），
> 或 `launch(executable_path=<显式路径>)`。照抄裸 `launch()` 一定失败。
> 

---

## 适用信号（Recognition signals）

### 「看起来标准」的 helper 名单

下列名字**全部不可信**，在固定样本对齐之前一律当作未验证标签：

`md5`、`sha1`、`sha256`、`sm3`、`btoa`、`atob`、`hmac`、`aes`、`rsa`、`sm2`、`sm4`、`ecdsa`、`ecdh`、`xxhash`、`murmurhash`

### 快速识别清单

- 长度是否匹配某个常见摘要尺寸
- 字母表是否匹配 hex / Base64 / URL-safe Base64，或某个自定义字母表
- 填充（padding）是否匹配某个标准编码器
- 输出是否随时间戳、页面、会话状态变化
- helper 是否读取 DOM、全局变量、或旁路脚本状态
- 输出是否是「摘要 + 短后缀摘要 / 校验位 / 版本片段」
- 某个 UUID、nonce（一次性随机数）、或会话值乍看标准，实际内嵌了定长片段、前缀、或校验派生片段
- 表面上的 key、iv（初始化向量）、seed（种子）、hash 输入，其实是对某个配置字段做了切片、拼接、裁剪、或加装饰，而不是直接使用
- 某个国密（national crypto）或教科书级摘要在固定输入上对不齐，但**位长又是对的**

### 「标准摘要家族」被魔改

把 `md5`、`sha*`、`sm3` 当作不可信标签，**直到固定样本对齐为止**。

**先定位实现，再按此顺序 diff（逐项对比）标准算法：**

1. IV 或初始链接值（initial chaining value）
2. 轮常量 / 消息常量，如 `Tj` / `K`
3. 字符串转字节或打包辅助函数，**含逐字节掩码**
4. 压缩步（compress step）中被替换掉模运算的掩码
5. expand（消息扩展）、`FF`/`GG`、`P0`/`P1`、padding（填充）、以及最终 hex 编码

**工作方法：**

1. 冻结一份抓到的 preimage（原像）和一份 wire 上的摘要
2. 搜索环境分支，例如
   `typeof X === "function" && String(X) === "function X() { [native code] }"`
3. 把 **browser 分支**的常量与辅助函数，**和 Node / fallback 分支分开记录**
4. **先移植 browser 分支**；不要把多个分支「平均」起来
5. 标准部分只在**各自**于固定样本上对齐后才保留

> **不要**把某一个 challenge 的常量提升为全局「魔改 SM3」配方。
> 要沉淀的是这份核对清单和对齐方法，**不是**那张一次性的 IV 表。

## 前置（Entry conditions）

1. **固定输入测试向量（fixed-input vector）**。至少一条：preimage + 期望输出。没有它，下面所有「对齐」都是自欺欺人。
2. **同一条会话链上的浏览器输出**。用于做 parity（对等性）比对。抓取手段见 `../observe/hook-techniques.md`。
3. **本机执行宿主**。移植 JS → Python 时的对照基准，二选一：
   - `node`（本机可用）：跑原始 JS 分支，直接拿它的输出当基准
     ```powershell
     & (Resolve-ReverseToolSpec -Name 'node').Command -e "console.log(require('crypto').createHash('md5').update('abc').digest('hex'))"
     ```
   - `python`（本机可用）：跑移植后的实现
     ```powershell
     & (Resolve-ReverseToolSpec -Name 'pyre').Command -c "import hashlib;print(hashlib.md5(b'abc').hexdigest())"
     ```
4. **一个已知答案向量（KAT）**，用于区分「我实现错了」和「目标本来就魔改了」。
   本机 `node` 的 OpenSSL 后端带 SM3，可直接当权威基准：
   ```powershell
   & (Resolve-ReverseToolSpec -Name 'node').Command -e "console.log(require('crypto').createHash('sm3').update('abc').digest('hex'))"
   # 输出（本机实测）：66c7f0f462eeedd9d1f2d46bdc10e4e24167c4875cf2f7a2297da02b8f4ba8e0
   ```
   这条「标准 SM3 输出」是**本机实测值**，可作为你魔改实现的差分基准。

## 步骤（Working method）

### A. 固定输入校验循环（Fixed-input validation loop）

当请求签名同时依赖 method（方法）和 body 序列化时，固定样本**必须把这两者一并冻结**。

> **一个能在「regenerate（重新生成）」路由上通过的签名，不能证明它在「first-create（首次创建）」上也成立** —— 如果 method 或 body 的放置方式不同。

签名器（signer）必须覆盖**真实的方法**和**真实上线的那份序列化 query 或 body**。

1. 冻结一个极小输入，例如 `"abc"`
2. 冻结一个真实输入，例如抓到的 timestamp（时间戳）
3. 比对 browser 输出与 local 输出
4. **比对中间字符串**，而不只是最终摘要

### B. 跨运行时移植循环（Cross-runtime porting loop）

把 JS 逻辑移植到 Python 或其他运行时时：

1. 冻结同一份 config blob（配置块）、timestamp、nonce、UUID 来源、以及 fingerprint vector（指纹向量）
2. **先**比对归一化（normalization）输出 —— 紧凑 JSON、切片后的 key material、加前缀的 payload、或校验输入
3. **只有中间形态对齐后**，才比对最终的 cookie / token / sign 输出
4. 在信任线上流量之前，**保留一条确定性 parity 向量**
5. 当存在 browser-only 分支时，**先在本地复现该分支**，再把常量移植进 Python

### C. JS → Python 位宽陷阱（bitwidth traps）

把 JS 摘要搬进 Python 时反复出现的移植失败：

- `>>> 0` → Python 的 `& 0xFFFFFFFF`；**在 JS 会强制成 uint32 的每一步算术之后**都要加掩码
- **`ROTL(x, n)` 必须先做 `n %= 32`**，且 **`x` 必须先掩码成无符号 32 位**
  朴素写法 `((x << n) | (x >> (32 - n)))` 的真实失败点是：
  - `n > 32` 时 Python 抛 `ValueError: negative shift count`
  - `x` 为**负数**（尚未 `& 0xFFFFFFFF`）时，右移是算术右移，结果全错
  - ⚠ **源文档声称它在 `n == 0` 时会坏掉，这是错的**，详见文末「源文档勘误」
- `~x & z`（`z` 为有界正数）通常无需特判，最后补一次 `& 0xFFFFFFFF` 即可
- 逐字节掩码（如 `& 0xfe`）必须作用于**每一个输出字节**，不能只作用于第一个码元
- **「先掩码还是先移位」的顺序很关键**：严格保留页面里的 `sum & mask` 与 `(sum >>> 0) & mask` 的区别

本机最小自检（两条命令，diff 为空才算过）：

```powershell
# Node 侧（原始 JS 分支）
& (Resolve-ReverseToolSpec -Name 'node').Command -e "console.log(require('crypto').createHash('sha256').update('abc').digest('hex'))"
# Python 侧（你的移植）
& (Resolve-ReverseToolSpec -Name 'pyre').Command -c "import hashlib;print(hashlib.sha256(b'abc').hexdigest())"
```

两者都应输出 `ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad`。

### D. RSA 密文编码属于协议契约的一部分

登录页或 bootstrap（引导）页下发 RSA modulus（模数）与 exponent（指数）时：

1. 解析**当前页面**的值；不要假设它们永远不变
2. 用页面采用的 padding 方案加密，legacy（传统）形式常见为 **PKCS#1 v1.5**
3. **按页面原样编码密文**，再放进 wire 字段

**编码陷阱：**

- 页面可能要求 hex、Base64、URL-safe Base64，或另一套字母表
- 2048 位 RSA 密文是 **256 字节**；hex 是 **512 字符**，而标准 Base64 更短（256 字节 → 344 字符，含 `=` 填充）
- 编码写错常常表现为**假业务错误**，例如「密码错误」或「系统异常」

**固定输入方法：**

1. 冻结 modulus、exponent、明文密码或占位符、以及页面的密文
2. **先对齐编码与字母大小写，再去怀疑账号**
3. 把验证过的编码器**放在采集器的登录路径旁边**

### E. 签名、密钥交换与国密格式

> **把「原语名字」和「wire 表示」当作两条独立的断言。**
> 一个叫 `sm2` 的字段，可能是签名，也可能是公钥密文 —— 二者结构完全不同。

#### SM2 与 SM4

- **区分 SM2 签名与 SM2 公钥密文**。一对签名整数**不是** `C1C3C2` 或 `C1C2C3` 密文
- 记录：SM2 曲线、公钥前缀与点编码、签名时的 user-id 输入、密文分量顺序、最终 hex/Base64 外框
- SM4 需冻结：mode（模式）、key 字节、IV、padding、明文编码、输出字母表。
  `ECB` vs `CBC`、零填充 vs PKCS#7、文本 key vs 解码后的 key 字节 —— 这些是**互相独立的维度**
- 要求：一条该原语的**公开已知答案向量**，加一条该应用**抓到的 envelope（封套）向量**

#### ECDSA 与 ECDH

- **ECDSA** 记录：曲线、是否对消息摘要签名（message vs prehash）、哈希算法、nonce 是确定性还是随机、是否做 low-S 归一化、wire 上是 ASN.1 DER 还是定长裸 `r || s`
- **ECDH** 记录：曲线、公钥压缩 / 非压缩编码、对端密钥校验、共享密钥位宽、KDF、salt/info/context、以及**下游密钥实际取的是哪一段切片**
- **共享密钥一致 ≠ 封套一致**。KDF 输出、nonce/IV 构造、认证数据（authenticated data）、tag 位置、密文编码 —— 必须分别比对

#### 非密码学哈希家族

对 xxHash、MurmurHash 及类似校验和（checksum），需冻结：算法变体、seed、输入字节、有符号 / 无符号解释、位宽、字节序、雪崩输出（avalanche output）、最终文本编码。

> **不要从一个「长得像校验和」的字段推断出密码学真实性保证。**

#### 混合封套核对清单

当 payload 把对称加密与 RSA、SM2、ECDH 或其他密钥包装（key wrapper）组合时，**拆开并逐项验证**：

1. 归一化后的明文字节
2. 生成或派生出的 content key（内容密钥）
3. nonce 或 IV
4. 密文与认证 tag
5. 被包装的密钥，或临时公钥（ephemeral public key）
6. 分量顺序与长度前缀
7. 最终的 JSON / protobuf / hex / Base64 / 自定义字母表封套

> **密钥与抓到的密文只在任务内使用（task-local）。** 只提升「布局」与「验证方法」。

## 判据（Verification checklist）

只有满足以下**全部 6 条**，才可以说「加密这块搞懂了」：

1. **每个 helper 的标准部件 vs 魔改部件已逐项分类** —— 上面 C 节的 5 项 diff（IV / 轮常量 / 字符串打包 / 压缩掩码 / expand+填充+hex）**都有明确结论**，不是「看着像标准」
2. **存在至少一条固定输入 parity 向量**：browser / node 输出与本地输出**逐字节相同**，且在**至少一个中间值**上也相同
3. **跨运行时移植有确定性 parity 向量**，且向量**固化进了采集器**（不是跑一次就丢的临时值）
4. **RSA / SM2 / ECDSA 的 wire 表示已确认**：字母表、字母大小写、分量顺序、点编码 —— 是**对齐后**确认的，不是「加密那步对了就算」
5. **每个原语都有一条公开已知答案向量**通过（用来证明你的实现本身没写错），**外加**一条应用封套向量通过
6. **真实请求 replay 至少成功两次**，用的是采集器自己生成的值，不是从浏览器复制的样本

> **反过来说**：只做到「函数名对上了」「能跑出 32 位 hex」「加密步骤没报错」，**都不算完成**。

## 常见坑（Common failure modes）

- 对被改过字母表的编码器，用了标准 Base64 库
- 对自定义的字符串→字（word）打包步骤，用了标准 MD5 / SM3
- 哈希**之前**的 URL 编码不匹配
- 时间戳精度错误
- 把页面或会话的隐藏状态混进了哈希输入
- 哈希函数本身对，但**用错了 JSON 序列化形式、条目顺序、或紧凑化规则**
- 在协议期望「有结构的本地 id」的地方，用了标准 UUID 或随机 hex
- 表面上的 key / iv 被直接使用，而页面其实先做了 slice（切片）、concat（拼接）、trim（裁剪）、或去壳（wrapper removal）
- 客户端其实用的是内嵌的兼容 id（compatibility id），你却去从当前文件字节重算 bundle / 版本哈希
- **仅仅因为名字匹配**就调用标准库摘要，而它的 IV、轮常量、或压缩掩码都被重写过
- Python 的 ROTL 或 uint32 截断只在部分页面、部分 `j` 值上失败（边界值没覆盖到）
- RSA **加密那步正确**，但密文用了错误的字母表或大小写编码

## 相关（Related）

- `../observe/patched-helper-playbook.md` —— helper 被 patch 的完整识别流程
- `offline-inline-deob-playbook.md` —— 先把 `eval(atob(...))` 这类内联 payload 还原出来，再谈加密
- `obfuscation-guide.md` —— 字符串表 / rotate IIFE 的还原顺序
- `pattern-atlas.md` —— 「标准 helper 被 patch」对应其中的 Pattern C
- `../deliver/pure-python-rebuild-playbook.md` —— 判据第 6 条的无浏览器交付形态
- `../triage/reproducible-evidence-playbook.md` —— 固定样本与可复现证据的采集规程
- `../../../js-reverse/references/ast-deobfuscation.md` —— 需要静态 AST 时（本机需先装解析器，见该文说明）

---

## 源文档勘误（改编时修正）

1. **【技术性错误，已修正】** 源文档「JS to Python bitwidth traps」一节声称：
   > `ROTL(x, n)` 必须在 `n == 0` 时当作恒等。朴素写法 `((x << n) | (x >> (32 - n)))` 会在 `n == 0` 时坏掉，因为 Python 的 `x >> 32` 是 `0`，而 JS 的 `x >>> 32` 等价于 `x >>> 0`。

   **这句话既自相矛盾，也是错的。**

   - **自相矛盾**：它自己已经指出 JS 的 `x >>> 32` **等价于** `x >>> 0`（即 `x` 本身）。既然右边等于 `x`，那么 `(x << 0) | x` 就等于 `x`，朴素写法在 `n == 0` 时**恰恰是正确的**。
   - **实测证伪**（本机 `python 3.12` / `node v24.20.0`）：
     ```
     python: x=0xF0000000, x>>32 == 0        → 朴素 rotl(n=0) == 0xf0000000 == x  ✅
     node  : x=0xF0000000, x>>>32 === x>>>0   → 朴素 rotl(n=0) === x              ✅
     ```
     两边都得到 `x`，没有任何分歧。

   **真实的失败点是另外两个**，已写入正文 C 节：
   - `n > 32` 时 Python 直接抛 `ValueError: negative shift count`（本机实测复现）
   - `x` 尚未 `& 0xFFFFFFFF` 而为负数时，Python 的右移是**算术右移**（符号扩展），结果全错。例如本机实测 `naive(-2147483648, 1)` 得到 `0xffffffff`，而正确答案是 `0x00000001`。

   **保留 `n %= 32` 的建议本身是对的**（它防的是第一个失败点），但**给出的理由是错的**。已按实测更正理由，并把「必须先掩码 x」补为显式要求。

> 本文其余算法描述经逐条核对，**未发现编造的常量或错误的算法表述**：
> - SM3 的 `P0`/`P1`（置换函数）、`FF`/`GG`（非线性布尔函数）、`Tj`/`K`（轮常量）用法均正确
> - 「2048 位 RSA 密文 256 字节 / hex 512 字符」数值正确（Base64 为 344 字符）
> - 「btoa/atob」「sm2 密文分量 `C1C3C2` / `C1C2C3`」的表述正确