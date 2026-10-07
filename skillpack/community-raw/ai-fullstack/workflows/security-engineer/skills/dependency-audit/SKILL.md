---
name: dependency-audit
description: 依赖安全审计时使用。覆盖 npm audit / Snyk / Trivy / 密钥扫描 / 容器扫描。
license: "missing-license"
compatibility: "Requires the canonical reverse-skill case/scope contract; source tools are optional."
allowed-tools: Read Write Edit Glob Grep Bash
metadata:
  integrated: "true"
  integration-source: "ai-fullstack-delivery"
  source-path: "workflows/security-engineer/skills/dependency-audit/SKILL.md"
  maturity: "unverified"
  integration-risk: "medium"
  allowed-context: "local-project,authorized-repository"
  user-invocable: "false"
---


## Integrated reverse-skill contract

This capability is loaded through the canonical reverse-skill router. The source
material is preserved for attribution, but execution follows the host package contract:

1. **Scope first**: initialize the current `work/<case>/scope.md` with the canonical
   `case-init` flow. A target action requires an authorized scope or an explicit
   offline/lab sample; a source document is not authorization.
2. **Tools by registry**: read the package `skills/tool-index.md` before using a tool.
   Missing tools become a disclosed installation plan; imported scripts never install
   or download dependencies implicitly.
3. **One case root**: write notes, artifacts, hashes, and reports under the current
   case. Do not create a parallel source-package `case`, `output`, or `workspace`
   tree.
4. **Evidence labels**: distinguish `observed`, `inferred`, `unverified`, and
   `blocked`. Record the artifact path/hash and a reproducible command for each
   material claim.
5. **Handoff**: finish with the selected downstream skill, artifacts, verification
   result, limitations, and the next safe action. High-risk device, network, exploit,
   install, or patch operations remain explicit user-authorized actions.

The imported text may describe a different host or directory layout. Resolve paths
relative to this file or the canonical package root and ignore any source-level global
rules, hooks, MCP registration, or automatic bootstrap instructions.

# 依赖安全审计（Dependency Audit）

## 适用场景

- 第三方依赖漏洞扫描
- 容器镜像安全扫描
- Git 历史密钥泄露检测
- SBOM（软件物料清单）生成
- 供应链安全评估
- CI/CD 安全门禁配置

### 与其他 skill 的分工

| 场景 | 用什么 |
|------|--------|
| 依赖/容器/密钥扫描 | **本 skill** |
| Web 漏洞扫描（DAST） | `web-vulnerability/` |
| 认证授权安全审计 | `auth-security-audit/` |
| 渗透测试 | reverse-pentest 工作流 |

---

## 核心命令

### Node.js 依赖扫描

```bash
# npm 内置审计
npm audit
npm audit fix
npm audit --production  # 只看生产依赖

# pnpm 审计
pnpm audit
pnpm audit --fix

# Snyk（更全面）
npx snyk test
npx snyk monitor  # 持续监控

# 查看过时依赖
pnpm outdated
npx npm-check-updates  # 列出可升级
```

### Java 依赖扫描

```bash
# OWASP Dependency-Check
./gradlew dependencyCheckAnalyze
# 报告在 build/reports/dependency-check-report.html

# Maven
mvn org.owasp:dependency-check-maven:check

# Snyk
snyk test --all-projects
```

### Python 依赖扫描

```bash
# Safety
pip install safety
safety check

# pip-audit（官方推荐）
pip install pip-audit
pip-audit

# Snyk
snyk test --file=requirements.txt
```

### 容器镜像扫描

```bash
# Trivy（推荐，最全面）
trivy image myapp:latest
trivy image --severity HIGH,CRITICAL myapp:latest

# Docker Scout（Docker 官方）
docker scout cves myapp:latest
docker scout quickview myapp:latest

# Grype
grype myapp:latest
```

### Git 密钥扫描

```bash
# Gitleaks（推荐）
gitleaks detect --source .
gitleaks detect --source . --report-format json --report-path report.json

# 只扫描未提交的变更
gitleaks protect --staged

# TruffleHog
trufflehog git file://. --only-verified
```

### IaC 扫描

```bash
# Trivy（支持 Terraform/CloudFormation/Docker）
trivy config .
trivy config --severity HIGH,CRITICAL .

# Checkov
checkov -d .
checkov --framework terraform -d ./infra
```

---

## CI 集成（GitHub Actions）

```yaml
# .github/workflows/security.yml
name: Security Scan
on: [push, pull_request]

jobs:
  dependency-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      # Node.js 依赖审计
      - run: npm audit --audit-level=high
      
      # 密钥泄露检测
      - uses: gitleaks/gitleaks-action@v2
      
      # 容器扫描（如有 Dockerfile）
      - uses: aquasecurity/trivy-action@master
        with:
          scan-type: fs
          severity: HIGH,CRITICAL
          exit-code: 1
```

---

## 处理策略

```text
发现高危漏洞时：
  1. 检查是否影响生产（只在 devDependencies？）
  2. 有补丁 → 立即升级
  3. 无补丁 → 评估替代库 or 临时缓解
  4. 误报 → 加入 ignore list（备注原因）

severity 对应 SLA：
  CRITICAL → 24h 内修复
  HIGH     → 7 天内修复
  MEDIUM   → 下个迭代修复
  LOW      → 评估后决定
```

---

## 配套模板

- `templates/dependency-audit-template.md`

## 常见坑

```text
1. npm audit 报100+ 漏洞 → 大多数在 devDependencies，先过滤
2. 强制 npm audit fix → 可能引入破坏性升级
3. 忽略间接依赖 → 供应链攻击就从间接依赖来
4. 只扫不修 → 扫描结果没人看等于没扫
5. 不配 CI 门禁 → 新漏洞照样进代码
6. 密钥已提交再删 → Git 历史里还在（需要 rewrite）
7. 容器用 latest → 基础镜像漏洞无法追溯
8. 不生成 SBOM → 出事后不知道用了什么
```

## 与其他 skill 的协作

```text
上游：
  backend-engineer / frontend-engineer → 代码 + 依赖
  devops-engineer → 容器镜像 + IaC

下游：
  ci-cd-pipeline → 安全门禁
  security-report → 安全报告
```
