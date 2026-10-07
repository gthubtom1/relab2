<!-- link-triage: reference-only -->
> **来源留档（source archive）——不是本仓库的执行规则。**
>
> 本文件是上游仓库的原样留档，仅用于溯源与对照。**不要按本文件执行任何 install / bootstrap 或发布命令**；
> 本包 `autoInstall=false`，运行任何仓库脚本都需要用户事先明确批准（见 `AGENTS.md`）。

# Tool Index

本文件记录全栈交付工作流常见工具。具体项目执行时，应以当前项目实际技术栈为准。

## 自举机制

每个工作流目录下有 `TOOLS.md`（机器可读工具索引），AI 可直接解析。

缺少工具时只生成安装计划，获用户显式批准后才执行（`autoInstall=false`）：

> 上游原命令 `scripts/bootstrap-project.ps1 -Workflow <workflow-name>` 未随本仓库分发，
> 本包内无可调用的自动入口；按下面的工具清单走手动计划处理。

工具清单：`scripts/bootstrap-manifest.json`

### 各工作流 `TOOLS.md` 位置

| 工作流 | 路径 |
|--------|------|
| frontend-engineer | `workflows/frontend-engineer/`TOOLS.md` |
| backend-engineer | `workflows/backend-engineer/`TOOLS.md` |
| database-engineer | `workflows/database-engineer/`TOOLS.md` |
| devops-engineer | `workflows/devops-engineer/`TOOLS.md` |
| api-designer | `workflows/api-designer/`TOOLS.md` |
| automation-qa | `workflows/automation-qa/`TOOLS.md` |
| qa-engineer | `workflows/qa-engineer/`TOOLS.md` |
| security-engineer | `workflows/security-engineer/`TOOLS.md` |
| sre-operations | `workflows/sre-operations/`TOOLS.md` |
| data-analyst | `workflows/data-analyst/`TOOLS.md` |
| ai-ml-engineer | `workflows/ai-ml-engineer/`TOOLS.md` |
| fullstack-engineer | `workflows/fullstack-engineer/`TOOLS.md` |
| product-manager | `workflows/product-manager/`TOOLS.md` |
| project-manager | `workflows/project-manager/`TOOLS.md` |
| ui-ux-designer | `workflows/ui-ux-designer/`TOOLS.md` |
| technical-writer | `workflows/technical-writer/`TOOLS.md` |
| reverse-pentest | `workflows/reverse-pentest/reverse-skill-private/skills/`TOOLS.md` |

---

## Frontend

| 工具 | 作用 |
|---|---|
| Node.js | JavaScript/TypeScript 运行环境 |
| npm / pnpm / yarn | 包管理 |
| Vite / Webpack / Next.js | 构建与开发服务器 |
| React / Vue / Angular | 前端框架 |
| TypeScript | 类型系统 |
| Playwright / Cypress | 浏览器 E2E 测试 |
| Chrome DevTools | 浏览器调试 |
| ESLint / Prettier | 代码质量与格式化 |

## Backend

| 工具 | 作用 |
|---|---|
| Node.js / Python / Go / Java | 后端运行时 |
| Express / NestJS / FastAPI / Spring Boot / Gin | 后端框架 |
| curl / HTTPie | 接口调试 |
| Postman / Apifox | API 调试与集合管理 |
| OpenAPI / Swagger | API 契约与文档 |
| Redis | 缓存与队列辅助 |

## Database

| 工具 | 作用 |
|---|---|
| PostgreSQL / MySQL / SQLite | 关系型数据库 |
| Redis | 缓存、计数器、会话、轻量队列 |
| Prisma / TypeORM / Sequelize / SQLAlchemy / Flyway / Liquibase | ORM 与迁移 |
| pgAdmin / DBeaver / DataGrip | 数据库 GUI |

## QA & Automation

| 工具 | 作用 |
|---|---|
| Jest / Vitest | JS/TS 单元测试 |
| Pytest | Python 测试 |
| JUnit | Java 测试 |
| Playwright / Cypress | E2E 测试 |
| k6 / JMeter | 性能测试 |
| GitHub Actions / GitLab CI | CI 自动化测试 |

## DevOps & SRE

| 工具 | 作用 |
|---|---|
| Docker / Docker Compose | 容器化与本地编排 |
| Kubernetes | 容器编排 |
| Nginx / Caddy | 反向代理与静态服务 |
| GitHub Actions / GitLab CI | CI/CD |
| Prometheus / Grafana | 指标监控 |
| Loki / ELK / OpenSearch | 日志系统 |
| Sentry | 应用错误监控 |

## Security / Reverse / Pentest

安全、逆向、渗透工具详见逆向/渗透工作流内部的工具索引：

```text
工具索引：workflows/reverse-pentest/reverse-skill-private/`skillpack/skills/TOOLS.md`
```

常见类别：

| 工具 | 作用 |
|---|---|
| Burp Suite / ZAP | Web 代理与漏洞验证 |
| Nmap / Masscan | 端口与服务识别 |
| sqlmap | SQL 注入验证 |
| Nuclei | 漏洞模板扫描 |
| jadx / apktool / Frida | APK 逆向与动态分析 |
| IDA / Ghidra / radare2 | 二进制逆向 |
| Playwright / Chrome DevTools | 浏览器侧证据和自动化 |

## Docs & Diagram

| 工具 | 作用 |
|---|---|
| Markdown | 文档标准格式 |
| Mermaid | 流程图、时序图、架构图 |
| Graphviz / PlantUML | 复杂图表 |
| MkDocs / Docusaurus / VitePress | 文档站点 |
