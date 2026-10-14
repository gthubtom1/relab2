---
name: database-security
description: 数据库安全评估：0.0.0.0 绑定、弱口令、权限过大、危险功能（xp_cmdshell/UDF）、NoSQL 注入。用于：库是否暴露、被脱库、Redis 写文件提权。
---

# Database Security Assessment

## ACTION REQUIRED（读完后立刻执行）

1. `NOW`: 读取 precedent-pentest；**生产库禁止破坏性语句** unless 明确允许
2. `NOW`: **查经验卡** —— `python skills/scripts/experience-card.py search "<你看到的症状>"`。
   命中就读那张卡的 `invariant` + `decision.action`，并**逐条对照** `scope.appliesWhen`
   与 `scope.stopsWhen`：少一条前提就停用；命中任一停止条件就停。
   历史卡**不替代**当前目标的实测证据。详见 `../experience-cards/INDEX.md`。
3. `NOW`: scope 写清实例、账号权限、是否允许写/删
4. `NEXT`: 客户端工具路径
5. `ACT`: 暴露面 → 认证 → 授权 → 配置 → 利用链验证（安全）

## 适用场景

- 数据库未授权/弱口令/错误绑定 0.0.0.0
- 权限过大、危险功能（xp_cmdshell、COPY PROGRAM、UDF）
- 横向：从应用账号到 DBA
- NoSQL 注入与 Redis 写文件等（授权环境）

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

| 工具 | 用途 |
|------|------|
| 官方 CLI | 连接与枚举 |
| sqlmap | 注入验证（授权） |
| nuclei | 已知暴露模板 |
| 云 RDS 控制台审计 | 配置 |

## 参考

- `references/db-misconfig-checklist.md`
- `../pentest-tools/` `../cloud-k8s/`

## 路由上下文

**上游**: MASTER R35  
**下游**: 获 OS 命令 → attack-chain；云托管 → cloud-k8s

## 任务完成自检

- [ ] 是否避免未授权写删？
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


