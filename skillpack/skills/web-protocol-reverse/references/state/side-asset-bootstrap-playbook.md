# 旁路资产引导手册（Side Asset Bootstrap Playbook）

> **来源声明**：改编自 `aoyunyang/spider-king-skill`（MIT License）的 `side-asset-bootstrap-playbook.md`。英文原文译为中文，术语保留英文原词并附中文，按本包六段式规范重排。
>
> **什么时候用**：真正决定签名（signer）或解码（decoder）逻辑的，是一个不起眼的小资产，而不是那个吵吵闹闹的主 bundle。
>

> ★★ **本机 playwright 必须显式指定浏览器**（2026-10-10 实测）：
> `launch()` 默认启动会报 `Executable doesn't exist at %LOCALAPPDATA%\ms-playwright\chromium_headless_shell-1234\...`
> —— python 包期望 1234，本机装的是 **1243**，版本号对不上。
> **可用写法**：`p.chromium.launch(channel="msedge")`（实测能起、能渲染、能读 DOM），
> 或 `launch(executable_path=<显式路径>)`。照抄裸 `launch()` 一定失败。
> 

---

## 适用信号（Recognition signals）

- 一个很小的旁路脚本、`.wasm`、字体文件或 challenge JS 就能改变请求行为
- 主 bundle 噪声极大，但真正控制签名器或解码器的是一个小资产
- 首次响应返回可执行 JS、偏移量（offset）或下一请求所需的资产
- 字体是动态生成的，字符映射（glyph map）不静态存在
- 同一响应既种 cookie 又返回可执行代码

## 前置（Entry conditions）

1. **一份资产清单**。先把目标站点加载的所有资源列一遍，而不是只盯着主脚本。本机做法：
   ```powershell
   # 从已抓的 pcap 里列出全部被拉取的 JS / wasm / 字体
   & (Resolve-ReverseToolSpec -Name 'tshark').Command -r flow.pcapng -Y "http.request.uri matches \"\\.(js|wasm|ttf|otf|woff2)(\\?|$)\"" -T fields -e http.request.full_uri -e http.content_length
   ```
   或用 mitmproxy 实时流式看：`(Resolve-ReverseToolSpec -Name 'mitmdump').Command -p 8899`。
2. **按体积排序的能力感**。小资产往往体积小、命名无语义 —— 这正是它容易被漏掉的原因。排序后从最小的可疑项开始。
3. **本地解码手段**。字体用 Python 的 `fontTools` 本机可用；WASM 用 `wasmtime` 或 Node 内建 `WebAssembly`。`iv8` 本机无，不作为前提。
4. **适用面**：目标是你能直连的 Web 客户端。

## 步骤（Steps）

### 核心规则

**小旁路资产经常携带整个秘密。**

这不是修辞。反向的成本与体积常常严重倒挂：主 bundle 的混淆是"让人看不出来里面是什么"，而旁路资产只是"没人注意它"。

### 优先早查的资产类别

- `.wasm` 签名器
- 旁路脚本，例如 `/offset` 这类无语义端点
- 服务端返回的 JS bootstrap 载荷
- 动态字体或字形映射（glyph map）
- 既种 cookie 又返回可执行代码的响应

### 工作法

1. **定位哪个资产改变了下一个请求的状态**。判据不是"这个文件长得可疑"，而是"把它去掉/换掉，下一个请求就变了"。
2. **本地执行或模拟（emulate）该资产**。
3. **把产出的 cookie、全局变量（globals）、密钥或映射带进下一个请求**。
4. **把资产步骤保留为本地 helper，而不是浏览器依赖**。

第 4 步是交付底线：旁路资产可以是"必须先本地跑一遍的小函数"，但不能是"必须开着浏览器"。

### 本机落地示例

```powershell
# 取回候选 wasm 并本地求值接口
curl.exe -o side.wasm "https://<target>/<side-asset>"     # 仅限已授权目标
# 用 node 枚举导出，定位签名函数
& (Resolve-ReverseToolSpec -Name 'node').Command -e "const m=new WebAssembly.Module(require('fs').readFileSync('side.wasm'));console.log(WebAssembly.Module.exports(m))"
```

字体类资产用 Python 本地解码，不要开浏览器渲染：

```powershell
& (Resolve-ReverseToolSpec -Name 'pyre').Command -c "from fontTools.ttLib import TTFont; f=TTFont('cmap.woff2'); print(f.getBestCmap())"
```

> 上面的命令形态是通用用法，**未在任何具体目标上实跑验证**；目标 URL 与资产路径按你自己的 case 记录确定。

## 判据（Verification criteria）

满足以下**全部 4 条**才算走通：

1. **点名了具体是哪个资产**在控制下一个请求的状态，不是「大概是某个 JS」
2. 该资产在**本地**执行/解码成功，产出物可被采集器读取
3. 产出物（cookie / global / key / mapping）被带进下一个请求，并且**下一个请求的行为因此改变**
4. 资产步骤是**本地 helper / decoder**，最终路径**不依赖浏览器**

第 4 条是「是否属于协议契约」的判定：旁路资产如果只是保护壳，绕过它仍要依赖浏览器，那它就不是协议契约的一部分。

## 常见坑（Common traps）

- 过度逆向主 bundle，同时忽略了一个几十字节的旁路资产
- 把 bootstrap JS 当噪声跳过
- 在浏览器里渲染字体，而不是在本地解码
- 找到旁路资产后就交付，忘了确认它是否真的改变下一个请求
- 把旁路资产的产出物硬编码，而不是保留本地执行步骤 —— 资产会变，会过期
- 旁路资产版本随机化后，继续用旧脚本硬打（需重新获取 bootstrap 资产，见 `challenge-artifact-harvest-playbook.md`）

## 相关（Related）

- `cookie-provenance-playbook.md` —— 第 4 类「本地构造器」写入方即本文场景
- `server-js-cookie-bootstrap-playbook.md` —— 载荷在响应体里而非独立端点的邻近形态
- `challenge-artifact-harvest-playbook.md` —— 版本随机化时如何重新获取 bootstrap 资产
- `../crypto/opaque-runtime-profile-playbook.md` —— WASM / 混淆运行时的剖析规程
- `../crypto/pattern-atlas.md` —— 常见签名器与封装（packer）模式索引
- `../../../js-reverse/SKILL.md` —— 需要静态 AST 时的 JS 逆向工具链（本机 npm AST 工具未安装，需先装）
- `../../../radare2/SKILL.md` —— WASM / 二进制初筛

---

## 源文档勘误（改编时修正）

源文档极短（全文 35 行），内容正确但有三处不足：

1. **无「前置」段**。原文假定「列出资产」是显然的，实际上这正是最容易漏的一步。本文补了该段与本机 `tshark` 命令。
2. **无 Verification checklist**。原文只有一句 `Delivery rule`。本文把该句拆成 4 条可检验判据，其中第 1 条（点名具体资产）与第 3 条（产出物确实改变下一个请求）是原文隐含但未写出的。
3. **无目录、无交叉引用**。本文补齐并指向本包实际路径。