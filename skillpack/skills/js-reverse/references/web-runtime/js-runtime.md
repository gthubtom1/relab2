# JS Runtime / Browser Reversing

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/ctf-website/techniques/07-client/js-runtime.md`（GPL-3.0）。原 frontmatter 的 `mcp_tools` 映射已剔除——本技能包未挂载 `run_ctf_tool` / `http_probe`，改用本地工具链。
> **授权范围**：仅限 CTF 靶场 / AWD 赛场 / 已签署授权的测试环境。任何真实第三方目标、真实凭据、真实支付/生产流量都禁止套用本文流程。
> **什么时候用**：命中「JS逆向 / AST去混淆 / WebAssembly / runtime hook」这类信号时，把本文当打点清单读；命中即进「步骤」，命中不了就换主题。

## 适用信号

- JS逆向
- AST去混淆
- WebAssembly
- runtime hook
- 浏览器逆向
- Babel
- CryptoJS
- webpack

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

1. **`main.*.js` / `app.*.js`** — 搜 `baseURL`, `axios`, `fetch`, `/api/`
2. **`vendor.*.js`** — 搜 `CryptoJS`, `subtle`, `protobuf`, `wasm`
3. **source map** — 下载 `.map`，按 sourcesContent 检索
4. **dynamic chunk** — hook script append/import
5. **Worker** — hook `new Worker`、`postMessage`

## 判据

判据必须是外部可观测的（状态码、响应字段、差分、落盘文件），不是「命令有输出」。

- **命中样本** — 请求参数与签名输入同步出现
- **失败样本** — sign 在服务端生成
- **命中样本** — 找到 API path 和 crypto 模块
- **失败样本** — chunk 加载前 hook 太晚
- **命中样本** — key/iv/plain/cipher 出现
- **失败样本** — 调用在 Worker/WASM 内
- **命中样本** — 调试不中断，逻辑继续
- **失败样本** — 检测在闭包里自校验
- **命中样本** — 导出函数和输入输出可复现
- **失败样本** — indirect table 混淆未定位
- **命中样本** — worker 脚本 URL/消息可见
- **失败样本** — CSP/COOP 影响调试

## 坑

- 探针命令在**未本机验证**时不要当成既定事实跑；先用探测层确认 `Available=True`。
- 噪声排除：先固定 baseline（同 URL 同 token 跑 3 次），再只改一个变量做差分。
- 不要把「状态码 200」当命中——WAF/缓存/软 404 都返回 200，命中判据要落到具体业务字段。

## 相关

- 见本技能 `../../SKILL.md` 的 references 索引。

## 技术正文

> 以下为原库正文（保留全部技术细节与脚本），仅移除原 `MCP 工具映射` 章节并重写跨文档链接。

JS Runtime 逆向不是把 bundle 从头读完，而是先把请求、签名、加密、状态和 WASM 的关键边界打出来，再决定是动态复现、AST 静态还原，还是直接劫持 runtime oracle。

## 输入信号

| 信号 | 立即动作 | 命中样本 | 失败样本 |
|---|---|---|---|
| bundle 里有 `sign/token/nonce/timestamp` | hook fetch/XHR 与签名函数 | 请求参数与签名输入同步出现 | sign 在服务端生成 |
| Webpack/Vite chunk 分裂 | 提取 chunk map、source map、动态 import | 找到 API path 和 crypto 模块 | chunk 加载前 hook 太晚 |
| CryptoJS/WebCrypto | hook encrypt/decrypt/sign/importKey | key/iv/plain/cipher 出现 | 调用在 Worker/WASM 内 |
| `debugger`/console 检测 | hook timer/toString/Function | 调试不中断，逻辑继续 | 检测在闭包里自校验 |
| WASM 模块 | dump bytes、exports、memory | 导出函数和输入输出可复现 | indirect table 混淆未定位 |
| Worker/Service Worker | hook Worker 构造和 postMessage | worker 脚本 URL/消息可见 | CSP/COOP 影响调试 |

## 工作流

```text
抓 HTML 与所有 JS chunk
  → 导航前注入 runtime hook
  → 触发关键业务动作并保存请求/响应/console
  → 定位签名/crypto/WASM/worker 模块
  → AST 还原或直接复现算法
  → 用 Python/Node 重放 API，记录成功和失败样本
```

## 0. Bundle 路由矩阵

| 入口 | 目标 | 工具/动作 |
|---|---|---|
| `main.*.js` / `app.*.js` | 路由、API client、状态管理 | 搜 `baseURL`, `axios`, `fetch`, `/api/` |
| `vendor.*.js` | crypto/lib/framework gadget | 搜 `CryptoJS`, `subtle`, `protobuf`, `wasm` |
| source map | 还原源码路径和函数名 | 下载 `.map`，按 sourcesContent 检索 |
| dynamic chunk | 登录后/点击后逻辑 | hook script append/import |
| Worker | 签名、加密、WASM | hook `new Worker`、`postMessage` |

## 1. 导航前总 hook

```javascript
(() => {
  const enc = v => {
    if (v instanceof ArrayBuffer) return Array.from(new Uint8Array(v)).map(b=>b.toString(16).padStart(2,"0")).join("");
    if (ArrayBuffer.isView(v)) return Array.from(new Uint8Array(v.buffer, v.byteOffset, v.byteLength)).map(b=>b.toString(16).padStart(2,"0")).join("");
    try { return typeof v === "string" ? v : JSON.stringify(v); } catch { return String(v); }
  };
  const oldFetch = window.fetch;
  window.fetch = async function(input, init = {}) {
    const url = String(input && input.url || input);
    console.log("[fetch:req]", url, enc(init.headers || {}), enc(init.body || ""));
    const r = await oldFetch.apply(this, arguments);
    r.clone().text().then(t => console.log("[fetch:resp]", url, r.status, t.slice(0, 1200))).catch(()=>{});
    return r;
  };
  const open = XMLHttpRequest.prototype.open;
  const send = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function(method, url) {
    this.__rt_method = method; this.__rt_url = url;
    return open.apply(this, arguments);
  };
  XMLHttpRequest.prototype.send = function(body) {
    console.log("[xhr:req]", this.__rt_method, this.__rt_url, enc(body || ""));
    this.addEventListener("load", () => console.log("[xhr:resp]", this.__rt_url, this.status, String(this.responseText).slice(0, 1200)));
    return send.apply(this, arguments);
  };
  const oldWorker = window.Worker;
  window.Worker = function(url, opts) {
    console.log("[worker:new]", url, opts || "");
    return new oldWorker(url, opts);
  };
})();
```

## 2. crypto / sign 打点

```javascript
(() => {
  const show = x => {
    try { return JSON.stringify(x); } catch { return String(x); }
  };
  if (window.crypto && crypto.subtle) {
    for (const n of ["importKey","generateKey","deriveKey","encrypt","decrypt","sign","verify"]) {
      const o = crypto.subtle[n].bind(crypto.subtle);
      crypto.subtle[n] = async (...a) => {
        console.log("[subtle:req]", n, a.map(show));
        const r = await o(...a);
        console.log("[subtle:ret]", n, r && r.algorithm, r && r.usages);
        return r;
      };
    }
  }
  const names = ["sign","getSign","makeSign","encrypt","decrypt","encode","decode"];
  for (const k of names) {
    if (typeof window[k] === "function") {
      const o = window[k];
      window[k] = function(...a) {
        console.log("[fn:req]", k, a.map(show));
        const r = o.apply(this, a);
        console.log("[fn:ret]", k, show(r));
        return r;
      };
    }
  }
})();
```

成功样本：同一次业务请求里同时记录到 `params/raw/timestamp/nonce/key/iv/sign`。失败样本：只有密文或签名结果，没有输入；需要 hook 更早或找 Worker/WASM。

## 3. AST 去混淆脚手架

```javascript
#!/usr/bin/env node
const fs = require("fs");
const parser = require("@babel/parser");
const traverse = require("@babel/traverse").default;
const generate = require("@babel/generator").default;
const t = require("@babel/types");

const code = fs.readFileSync(process.argv[2], "utf8");
const ast = parser.parse(code, {sourceType: "unambiguous"});

traverse(ast, {
  BinaryExpression(path) {
    const ev = path.evaluate();
    if (ev.confident && ["string","number","boolean"].includes(typeof ev.value)) {
      path.replaceWith(t.valueToNode(ev.value));
    }
  },
  MemberExpression(path) {
    const prop = path.node.property;
    if (path.node.computed && t.isStringLiteral(prop)) {
      path.node.computed = false;
      path.node.property = t.identifier(prop.value);
    }
  },
  IfStatement(path) {
    const ev = path.get("test").evaluate();
    if (ev.confident && typeof ev.value === "boolean") {
      path.replaceWith(ev.value ? path.node.consequent : (path.node.alternate || t.emptyStatement()));
    }
  }
});

fs.writeFileSync(process.argv[3] || "deobfuscated.js", generate(ast, {comments:false}).code);
```

## 4. Webpack chunk 抽取

```javascript
(() => {
  const scripts = [...document.scripts].map(s => s.src).filter(Boolean);
  console.log("[scripts]", scripts);
  const oldAppend = Element.prototype.appendChild;
  Element.prototype.appendChild = function(n) {
    if (n && n.tagName === "SCRIPT") console.log("[script:append]", n.src || n.textContent.slice(0, 120));
    return oldAppend.call(this, n);
  };
  for (const k of Object.keys(window)) {
    if (/webpackJsonp|webpackChunk|__LOADABLE_LOADED_CHUNKS__/.test(k)) console.log("[webpack-global]", k, window[k]);
  }
})();
```

## 5. WASM 打点

```javascript
(() => {
  const oldInstantiate = WebAssembly.instantiate;
  WebAssembly.instantiate = async function(src, imports) {
    const bytes = src instanceof ArrayBuffer ? new Uint8Array(src) : null;
    if (bytes) {
      console.log("[wasm:bytes]", bytes.length);
      window.__wasm_dump = Array.from(bytes);
    }
    const r = await oldInstantiate.apply(this, arguments);
    const inst = r.instance || r;
    console.log("[wasm:exports]", Object.keys(inst.exports));
    for (const [name, fn] of Object.entries(inst.exports)) {
      if (typeof fn === "function") {
        inst.exports[name] = new Proxy(fn, {
          apply(target, self, args) {
            console.log("[wasm:req]", name, args);
            const out = Reflect.apply(target, self, args);
            console.log("[wasm:ret]", name, out);
            return out;
          }
        });
      }
    }
    return r;
  };
})();
```

## 6. 签名复现骨架

```python
#!/usr/bin/env python3
import argparse
import hashlib
import hmac
import json
import time

def canonical(params):
    return "&".join(f"{k}={params[k]}" for k in sorted(params))

def sign(params, secret, algo="sha256"):
    raw = canonical(params)
    digest = hmac.new(secret.encode(), raw.encode(), getattr(hashlib, algo)).hexdigest()
    return raw, digest

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--params", required=True, help="JSON params from hook")
    ap.add_argument("--secret", required=True)
    ap.add_argument("--algo", default="sha256")
    args = ap.parse_args()
    params = json.loads(args.params)
    params.setdefault("timestamp", str(int(time.time())))
    raw, sig = sign(params, args.secret, args.algo)
    print(json.dumps({"raw": raw, "sign": sig, "params": {**params, "sign": sig}}, ensure_ascii=False))

if __name__ == "__main__":
    main()
```

判定：复现脚本生成的 `sign/token` 与浏览器 hook 结果一致，才进入 API 重放；不一致时回到 canonicalization、编码、timestamp、nonce、salt。

## 攻击链

```text
bundle/chunk 枚举
  → runtime hook 捕获请求和 crypto 输入
  → AST 还原签名/加密模块
  → Python/Node 复现算法
  → 重放 API 或生成 payload
  → 转支付、JWT、签名、WebCrypto、WASM 下一跳
```

## Evidence

| 项 | 记录内容 |
|---|---|
| bundle 来源 | HTML、script URL、chunk map、source map、hash |
| runtime 日志 | fetch/XHR/WS、Worker、crypto、WASM 的输入输出 |
| 静态还原 | AST 脚本、还原前后片段、关键函数名 |
| 复现结果 | canonical string、secret/key、timestamp/nonce、签名值 |
| 成功样本 | 复现签名后 API 接受、flag/订单/token/权限数据返回 |
| 失败样本 | hook 太晚、签名不一致、nonce 过期、服务端二次校验 |
| 下一跳 | crypto 转 `web-crypto-abuse`；支付转 `12-payment`；签名转 `13-signature` |
