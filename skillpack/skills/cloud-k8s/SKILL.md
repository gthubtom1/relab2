---
name: cloud-k8s
description: Cloud/container/K8s security assessment — 当用户要查云元数据SSRF/IAM越权/容器逃逸/K8s RBAC，或说"帮我看看这个存储桶是不是公开的""容器能不能逃逸""集群RBAC配得对不对"时使用。Use when assessing metadata SSRF, IAM misconfig, container escape and cluster RBAC.
---

# Cloud / Container / Kubernetes Security

## ACTION REQUIRED（读完后立刻执行）

1. `NOW`: 读取 `../field-journal/precedent-pentest.md` — 云/K8s 测试按 `scope.md` 直接执行
2. `NOW`: **查经验卡** —— `python skills/scripts/experience-card.py search "<你看到的症状>"`。
   命中就读那张卡的 `invariant` + `decision.action`，并**逐条对照** `scope.appliesWhen`
   与 `scope.stopsWhen`：少一条前提就停用；命中任一停止条件就停。
   历史卡**不替代**当前目标的实测证据。详见 `../experience-cards/INDEX.md`。
3. `NOW`: case-init + scope；明确账号边界、禁止破坏性操作
4. `NOW`: 确认是云元数据/容器/K8s/IAM，而非普通 Web 扫（后者 `pentest-tools/`）
5. `NEXT`: `../TOOLS.md`；kubectl/aws/gcloud 等多为手动安装
6. `ACT`: 从「身份与暴露面」开始，禁止默认全网扫描

## 适用场景

- 云元数据 SSRF（169.254.169.254 / IMDS）
- IAM 过度权限、公开存储桶、错误安全组
- Docker/containerd 逃逸路径评估
- Kubernetes RBAC、Secrets、Admission、供应链镜像
- 容器镜像漏洞（可联动 `supply-chain-security/`）

## 工作流

### Phase 1 — 身份与边界

```text
□ 当前身份：云 AK/SK、K8s SA、节点 SSH？
□ 范围：单账号 / 单 cluster / 单 namespace
□ 网络档：authorized_target_only
```

### Phase 2 — 云控制面

```bash
# 示例（按厂商替换；MUST 在授权账号内）
aws sts get-caller-identity
aws s3 ls
# Azure / GCP 对应 identity 命令
```

```text
□ 公开桶 / 错误 ACL
□ 元数据：IMDSv1 vs v2；SSRF 链
□ 角色可扮演（PassRole）与横向
```

### Phase 3 — 容器

```text
□ 是否 privileged / hostPath / hostNetwork
□ capabilities（SYS_ADMIN 等）
□ 可写宿主机路径 → 逃逸候选
□ 镜像历史与已知 CVE → Trivy
```

### Phase 4 — Kubernetes

```bash
kubectl auth can-i --list
kubectl get pods,secrets,svc -A
kubectl get clusterrolebindings
```

```text
□ SA token 挂载与权限
□ 危险 admission webhook 缺失
□ etcd / dashboard 暴露
□ 网络策略是否默认放行
```

## 工具链

| 工具 | 用途 | 自举 |
|------|------|------|
| kubectl | 集群交互 | 手动 |
| trivy | 镜像/IaC | bootstrap `trivy` 若可用 |
| kube-bench / kubeaudit | CIS/配置 | 手动 |
| pacu / scoutsuite | 云审计（授权） | 手动 |
| nuclei | 已知云漏洞模板 | bootstrap nmap/nuclei 生态 |

## 参考

- `references/k8s-cloud-checklist.md`
- CTF 对照：`../../CTF-Sandbox-Orchestrator/competition-agent-cloud/`
- `../supply-chain-security/` `../pentest-tools/`

## 路由上下文

**上游**: MASTER R23  
**下游**: 拿到节点 shell → `attack-chain` / `windows-ad`；镜像漏洞 → supply-chain  
**MUST NOT**: 未授权扫公有云其他租户

## 任务完成自检

- [ ] 是否限定在授权账号/cluster？
- [ ] 发现是否含复现与影响？
- [ ] 是否避免破坏性操作？
- [ ] 报告 / journal？
## 改编参考索引（open-reverselab `kb/ctf-website`）

> 下列 reference 改编自 `LING71671/open-reverselab` 的 `kb/ctf-website/`（GPL-3.0）。
> 每篇统一为「适用信号 / 前置 / 步骤 / 判据 / 坑 / 相关」+ 完整技术正文，
> 「前置」含**本机实测**的工具状态表——照抄原库裸命令前先看那张表。
> **能力域**：本文为技术能力说明，按项目 `scope.md` 直接套用。

### `references/attack-paths/` — 云原生攻击路径（IAM、CI/CD、容器逃逸、K8s RBAC、Serverless、Terraform）（8 篇）

- `references/attack-paths/aws-iam-privesc.md`
- `references/attack-paths/ci-cd-pipeline.md`
- `references/attack-paths/container-runtime-escape.md`
- `references/attack-paths/github-actions-abuse-paths.md`
- `references/attack-paths/k8s-rbac-attack-paths.md`
- `references/attack-paths/kubernetes-container.md`
- `references/attack-paths/serverless-lambda.md`
- `references/attack-paths/terraform-state-secrets.md`

### `references/` — 根目录


