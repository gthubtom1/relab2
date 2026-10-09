# 24-database — 数据库攻击技术

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/ctf-website/techniques/24-database/README.md`（GPL-3.0）。原 frontmatter 的 `mcp_tools` 映射已剔除——本技能包未挂载 `run_ctf_tool` / `http_probe`，改用本地工具链。
> **授权范围**：仅限 CTF 靶场 / AWD 赛场 / 已签署授权的测试环境。任何真实第三方目标、真实凭据、真实支付/生产流量都禁止套用本文流程。
> **什么时候用**：命中「见适用信号」这类信号时，把本文当打点清单读；命中即进「步骤」，命中不了就换主题。

## 适用信号

本篇是清单/索引类文档，正文直接以条目给出打点项（见「技术正文」首节）：

- 刚接触数据库攻击 → [00-overview.md](00-overview.md)
- 发现 SQL 注入点 → [01-sqli-fundamentals.md](01-sqli-fundamentals.md)
- WAF 拦截了注入 → [02-sqli-advanced.md](02-sqli-advanced.md)
- MongoDB/Redis 未授权 → [03-nosql-injection.md](03-nosql-injection.md)
- 发现了 .env 或 config.php → [04-config-exposure.md](04-config-exposure.md)
- 想找数据库备份文件 → [05-backup-log-leak.md](05-backup-log-leak.md)
- 打发卡/电商平台 → [06-card-platform.md](06-card-platform.md)
- 拿到混合 dump/日志/短码列表 → [07-data-cleaning.md](07-data-cleaning.md)

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

## 步骤

本篇正文以条目式打点清单为主，按顺序执行下列条目：

1. 刚接触数据库攻击 → [00-overview.md](00-overview.md)
2. 发现 SQL 注入点 → [01-sqli-fundamentals.md](01-sqli-fundamentals.md)
3. WAF 拦截了注入 → [02-sqli-advanced.md](02-sqli-advanced.md)
4. MongoDB/Redis 未授权 → [03-nosql-injection.md](03-nosql-injection.md)
5. 发现了 .env 或 config.php → [04-config-exposure.md](04-config-exposure.md)
6. 想找数据库备份文件 → [05-backup-log-leak.md](05-backup-log-leak.md)
7. 打发卡/电商平台 → [06-card-platform.md](06-card-platform.md)
8. 拿到混合 dump/日志/短码列表 → [07-data-cleaning.md](07-data-cleaning.md)

## 判据

判据必须是外部可观测的（状态码、响应字段、差分、落盘文件），不是「命令有输出」。

- 复现同一请求两次，状态码 + 响应体 hash 必须稳定；不稳定说明是噪声源（时间戳/随机数/缓存），先校准 baseline。
- 判为命中的最低门槛：同一 session 下**只有被测变量不同**，业务字段（身份/订单状态/flag）发生可复现变化。

## 坑

- 探针命令在**未本机验证**时不要当成既定事实跑；先用探测层确认 `Available=True`。
- 噪声排除：先固定 baseline（同 URL 同 token 跑 3 次），再只改一个变量做差分。
- 不要把「状态码 200」当命中——WAF/缓存/软 404 都返回 200，命中判据要落到具体业务字段。

## 相关

- 见本技能 `../../SKILL.md` 的 references 索引。

## 技术正文

> 以下为原库正文（保留全部技术细节与脚本），仅移除原 `MCP 工具映射` 章节并重写跨文档链接。

## 文档索引

| 文件 | 内容 | 难度 |
|------|------|------|
| [00-overview.md](00-overview.md) | 数据库攻击全景、证据路由与决策树 | 进阶 |
| [01-sqli-fundamentals.md](01-sqli-fundamentals.md) | SQL 注入上下文、DBMS 指纹、盲注抽取 | 进阶 |
| [02-sqli-advanced.md](02-sqli-advanced.md) | 高级 SQLi：WAF绕过、二阶、OOB | 进阶 |
| [03-nosql-injection.md](03-nosql-injection.md) | NoSQL：Mongo 参数解析、Redis/ES/CouchDB | 进阶 |
| [04-config-exposure.md](04-config-exposure.md) | 配置泄露：.env/config.php/默认凭证 | 基础 |
| [05-backup-log-leak.md](05-backup-log-leak.md) | 备份候选生成、日志提取、dump 解析 | 进阶 |
| [06-card-platform.md](06-card-platform.md) | 发卡平台实战：CDK泄露+IDOR+XSS | 综合 |
| [07-data-cleaning.md](07-data-cleaning.md) | 泄露 dump 抽取、聚类、锚点映射与结构化输出 | 进阶 |

## 快速入口

- 刚接触数据库攻击 → [00-overview.md](00-overview.md)
- 发现 SQL 注入点 → [01-sqli-fundamentals.md](01-sqli-fundamentals.md)
- WAF 拦截了注入 → [02-sqli-advanced.md](02-sqli-advanced.md)
- MongoDB/Redis 未授权 → [03-nosql-injection.md](03-nosql-injection.md)
- 发现了 .env 或 config.php → [04-config-exposure.md](04-config-exposure.md)
- 想找数据库备份文件 → [05-backup-log-leak.md](05-backup-log-leak.md)
- 打发卡/电商平台 → [06-card-platform.md](06-card-platform.md)
- 拿到混合 dump/日志/短码列表 → [07-data-cleaning.md](07-data-cleaning.md)
