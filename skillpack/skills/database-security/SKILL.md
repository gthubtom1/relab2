---
name: database-security
description: 数据库安全评估：0.0.0.0 绑定、弱口令、权限过大、危险功能（xp_cmdshell/UDF）、NoSQL 注入。用于：库是否暴露、被脱库、Redis 写文件提权。
---

# Database Security Assessment

## ACTION REQUIRED（读完后立刻执行）

> **手上只有"现象"、不知道该读哪一篇？** 本技能的技术正文有症状索引：先按现象查 [`../field-journal/KB-INDEX.md`](../field-journal/KB-INDEX.md)（现象 → 该读哪一篇技术文档），再读那一篇。**别按目录翻。** **什么时候该回读**（迷茫 / 换完技能 / 文档和本机对不上 …）见 [`../ops/kb-consult-contract.md`](../ops/kb-consult-contract.md) —— 它不是"开局读一次"，是**反复回读**。（来源与改编规则见同目录 `KB-SOURCES.md`）

1. `NOW`: 读 `../field-journal/precedent-pentest.md` —— 常规操作清单，直接照做；生产库先只读，写/删前打快照
2. `NOW`: **查经验卡** —— `python skills/scripts/experience-card.py search "<你看到的症状>"`。
   命中就读那张卡的 `invariant` + `decision.action`，并**逐条对照** `scope.appliesWhen`
   与 `scope.stopsWhen`：少一条前提就停用；命中任一停止条件就停。
   历史卡**不替代**当前目标的实测证据。详见 `../experience-cards/INDEX.md`。
3. `NOW`: 记录实例与账号权限（只读还是可写）；写/删前先打快照、记原值
4. `NEXT`: 客户端工具路径
5. `ACT`: 暴露面 → 认证 → 授权 → 配置 → 利用链验证（安全）

## 适用场景

- 数据库未授权/弱口令/错误绑定 0.0.0.0
- 权限过大、危险功能（xp_cmdshell、COPY PROGRAM、UDF）
- 横向：从应用账号到 DBA
- NoSQL 注入与 Redis 写文件等

## 工作流

```text
□ 网络暴露与 TLS
□ 账号角色与 grantee
□ 敏感表访问控制
□ 危险配置：file_priv、xp_cmdshell、load_file
□ 审计日志是否开启
□ 备份与快照权限
```

## 工具链

| 工具 | 干什么 | 真实调用口径 |
|------|--------|--------------|
| 官方 CLI（`mysql`/`psql`/`redis-cli`/`mongosh`） | 连接与权限枚举 | `SHOW GRANTS FOR CURRENT_USER();`、`SELECT @@secure_file_priv, @@plugin_dir;`、`psql \du+` |
| `sqlmap` | 注入验证（仅对已确认参数） | `sqlmap -u <url> --batch --risk 2 --level 3`；先手工确认注入类型再交给它，别一上来全量跑 |
| `nmap` | 端口与库指纹 | `nmap -p 3306,5432,6379,27017,1433 -sV <host>` |
| `nuclei` | 已知暴露/未授权模板 | `nuclei -u <host> -t network/`；模板命中只作入口线索，不作定论 |
| `hashcat` | 弱口令与哈希复现 | `hashcat -m 1731 <hash> <wl>`（MSSQL）、`-m 3200`（bcrypt）；命中即拿到口令等价物 |
| `impacket` | MSSQL 认证/中继 | `mssqlclient.py` 确认可登录后再谈权限边界 |
| `curl` | REST/管理 API（ES、CouchDB、ClickHouse HTTP 口） | `curl -s http://<host>:9200/_cat/indices` |
| `Burp` | 经应用接口到达库的注入面 | 与 `../api-security/SKILL.md` 共用同一代理与请求记录 |

探测层（唯一路径入口）：`. C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1` → `Resolve-ReverseToolSpec -Name sqlmap`。
`Get-Command sqlmap` 返回空 ≠ 本机没装（PATH 快照会过期）。云托管库一律先看实例的公开端点与控制面，再看引擎。

## 参考

- `references/db-misconfig-checklist.md`
- `../pentest-tools/` `../cloud-k8s/`

## 路由上下文

**上游**: MASTER R35  
**下游**: 获 OS 命令 → attack-chain；云托管 → cloud-k8s

## 任务完成自检

- [ ] 写/删操作是否都留有原值或快照回退？
- [ ] 是否区分配置问题与可利用链？
- [ ] Checklist？
## 改编参考索引（open-reverselab `kb/ctf-website`）

> 下列 reference 改编自 `LING71671/open-reverselab` 的 `kb/ctf-website/`（GPL-3.0）。
> 每篇统一为「适用信号 / 前置 / 步骤 / 判据 / 坑 / 相关」+ 完整技术正文，
> 「前置」含**本机实测**的工具状态表——照抄原库裸命令前先看那张表。
> **能力域**：本文为技术能力说明，按项目 `scope.md` 直接套用。

### `references/sqli/` — SQL / NoSQL 注入与配置泄露、备份日志、dump 清洗（10 篇）

- `references/sqli/sqli-nosqli.md`
- `references/sqli/00-overview.md`
- `references/sqli/01-sqli-fundamentals.md`
- `references/sqli/02-sqli-advanced.md`
- `references/sqli/03-nosql-injection.md`
- `references/sqli/04-config-exposure.md`
- `references/sqli/05-backup-log-leak.md`
- `references/sqli/06-card-platform.md`
- `references/sqli/07-data-cleaning.md`
- `references/sqli/index.md`

### `references/` — 根目录



---

## When NOT to use（近邻负例）

- 目标是应用层注入点，尚未接触数据库直连或库凭据 → 用 `../api-security/SKILL.md`
- 目标是库内数据本身的取证/恢复/时间线 → 用 `../digital-forensics/SKILL.md`
- 目标是数据库所在主机的 OS 提权与横向 → 用 `../attack-chain/SKILL.md`
- 库是云托管（RDS/Cloud SQL/Atlas）而问题在云侧权限或网络策略 → 用 `../cloud-k8s/SKILL.md`
- Redis/Memcached 写文件之后的容器逃逸面 → 用 `../cloud-k8s/SKILL.md`
- 目标是缓存/消息中间件的协议缺陷（非存储引擎配置） → 用 `../protocol-reverse/SKILL.md`

## When to Pivot

信号与判据见 `../ops/skill-pivot-contract.md`。本技能去向：

| 触发证据 | 换到 |
|---|---|
| 弱口令可登录，且 `SHOW GRANTS` / `\du` 返回的输出里含 `FILE`/`SUPER`/`pg_execute_server_program` | 评估 UDF 或写文件到 OS 层的路径后转 `../attack-chain/SKILL.md` |
| MySQL `SELECT @@secure_file_priv` 返回空串、`@@plugin_dir` 可写（<1 秒的廉价查询即可确认） | 写 UDF / 落文件面转 `../attack-chain/SKILL.md` |
| Redis `config set dir/dbfilename` 写文件后 `SAVE` 返回 OK，且目标路径出现新文件 | 云托管型转 `../cloud-k8s/SKILL.md`（元数据/实例角色），自建型转 `../attack-chain/SKILL.md` |
| MSSQL `xp_cmdshell` 或 `COPY ... PROGRAM` 在 <2 秒内返回命令回显 | `../attack-chain/SKILL.md` 做 OS 层横向 |
| 数据面发现高价值数据（PII/密钥/备份），但外泄路径未落盘 | 先定证据链（`../case-review/SKILL.md`），外泄可行性转 `../attack-chain/SKILL.md` |
| 注入点位于 Web 参数、库凭据尚未到手 | `../api-security/SKILL.md` |
| 同一账号间隔 >5 分钟两次 `SHOW GRANTS` 返回的输出逐字不变，却仍被拒访问目标表 | 是对象级 ACL 而非角色缺失；换表/换 schema 面，别继续猜权限 |
| 库暴露公网且 `nmap -sV` 报出的服务版本已 4 年以上未更新 | 先按版本查已知未授权/提权 CVE，必要时转 `../patch-diff-exploit/SKILL.md` |

## 定义完成

本技能产出算「完成」的**外部可观测**条件（不许写形容词）：

- 连接矩阵落盘（实例 × 端口 × 可达性 × 认证方式）
- 权限清单有实测（`SHOW GRANTS` / `\du` 等实际输出）
- 每条结论附实际命令与返回

## 输出契约

```
FACT:       <观察，带来源：命令 / 文件:行 / Evidence ID>
HYPOTHESIS: <可测试断言 + confidence: high|medium|low>（状态见 `../ops/binary-model.md`）
QUESTION:   <当前最大不确定点>
NEXT:       <继续 | 换技能 | 停止（附成本判据）>
```

## 置信度词表

词表见 `../ops/confidence-vocabulary.md`。本技能特有判据：

- `confirmed`：权限过高结论有实际 SQL 执行证据（如能读他人 schema）
- 硬判据：任何"某账号能读/写某对象"的结论必须附实际 SQL 执行输出；只有配置文件或 `SHOW GRANTS` 列表、拿不出一次真实查询结果的，一律记 `low`
- `low`：仅凭端口开放推断存在弱口令
