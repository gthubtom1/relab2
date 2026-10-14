---
name: cloud-k8s
description: 云/容器/K8s 安全评估：元数据 SSRF、IAM 越权、公开桶、容器逃逸、K8s RBAC。用于：云元数据 SSRF、容器逃逸、集群 RBAC。
---

# Cloud / Container / Kubernetes Security

## ACTION REQUIRED（读完后立刻执行）

> **手上只有"现象"、不知道该读哪一篇？** 本技能的技术正文有症状索引：先按现象查 [`../field-journal/KB-INDEX.md`](../field-journal/KB-INDEX.md)（现象 → 该读哪一篇技术文档），再读那一篇。**别按目录翻。** **什么时候该回读**（迷茫 / 换完技能 / 文档和本机对不上 …）见 [`../ops/kb-consult-contract.md`](../ops/kb-consult-contract.md) —— 它不是"开局读一次"，是**反复回读**。（来源与改编规则见同目录 `KB-SOURCES.md`）

1. `NOW`: 读 `../field-journal/precedent-pentest.md` —— 本机做过多轮的常规操作清单，直接照做，不要停在犹豫上
2. `NOW`: **查经验卡** —— `python skills/scripts/experience-card.py search "<你看到的症状>"`。
   命中就读那张卡的 `invariant` + `decision.action`，并**逐条对照** `scope.appliesWhen`
   与 `scope.stopsWhen`：少一条前提就停用；命中任一停止条件就停。
   历史卡**不替代**当前目标的实测证据。详见 `../experience-cards/INDEX.md`。
3. `NOW`: case-init 建案（目标账号/cluster、产出物落 `work/<case>/`）
4. `NOW`: 确认是云元数据/容器/K8s/IAM，而非普通 Web 扫（后者 `pentest-tools/`）
5. `NEXT`: `../TOOLS.md`；kubectl/aws/gcloud 等多为手动安装
6. `ACT`: 从「身份与暴露面」开始——先确认当前凭据是谁、能到哪，比一上来全网扫信噪比高得多

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
□ 网络档：默认只读枚举；会改配置/建资源的动作先落快照与回滚点
```

### Phase 2 — 云控制面

```bash
# 示例（按厂商替换；先看清当前凭据指向哪个账号）
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

| 工具 | 干什么 | 真实调用口径 |
|------|--------|--------------|
| `kubectl` | 集群对象与权限枚举 | `kubectl auth can-i --list`、`kubectl get pods,secrets,svc -A -o json`；SA token 在 `/var/run/secrets/kubernetes.io/serviceaccount/` |
| `trivy` | 镜像/IaC/K8s 已知 CVE | `trivy image --severity HIGH,CRITICAL <img>`；结果只作入口线索，命中后要能在镜像里指出对应文件 |
| `Syft` | 镜像 SBOM（比 trivy 更全的包清单） | `syft <img> -o json`，与 trivy 报告对账，找出 trivy 漏报的包 |
| `aws` / `gcloud` / `az` | 控制面身份与授权 | `aws sts get-caller-identity`、`gcloud auth list` —— 先落盘"当前主体是谁"再谈能到哪 |
| `curl` | IMDS / SSRF 探针 | `curl -s -m 2 http://169.254.169.254/latest/meta-data/iam/security-credentials/`；HTTP 200 且回显临时凭据 ⇒ IMDSv1 可达（强制 v2 会 401） |
| `nmap` / `masscan` | 暴露的 6443 / 10250 / 2379 | `nmap -p 6443,10250,2379 --open <cidr>`；2379 匿名可列 key 即 etcd 裸奔 |
| `nuclei` | dashboard / 组件暴露模板 | `nuclei -u <k8s-dashboard-url> -t http/exposures/`；模板命中 ≠ 已利用 |
| `ffuf` | dashboard / API 路由枚举 | 只有 200 且 `Content-Type: application/json` 才算真暴露面 |

探测层（唯一路径入口）：`. <仓根>\skillpack\skills\scripts\lib\Bootstrap.ps1` → `Resolve-ReverseToolSpec -Name kubectl`。
`Get-Command kubectl` 返回空 ≠ 本机没装（PATH 快照会过期）。
容器里带的是 stripped 原生二进制（sidecar/agent/Operator）时，静态分析走 `idapro` / `pyghidra` MCP：
**要用到哪个通道时才**跑 `powershell -NoProfile -ExecutionPolicy Bypass -File skillpack\skills\scripts\mcp-status.ps1`
看"注册了哪些 / 谁在监听 / 怎么起"三列——HTTP 型平时 `closed` 是设计，要用的按它给的命令起，起完重跑确认 `LISTEN`（不做事前自检）。

## 参考

- `references/k8s-cloud-checklist.md`
- CTF 对照：`../../CTF-Sandbox-Orchestrator/competition-agent-cloud/`
- `../supply-chain-security/` `../pentest-tools/`

## 路由上下文

**上游**: MASTER R23  
**下游**: 拿到节点 shell → `attack-chain` / `windows-ad`；镜像漏洞 → supply-chain

## 任务完成自检

- [ ] 结论是否绑定到具体账号/cluster 与凭据来源？
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



---

## When NOT to use（近邻负例）

- 目标是自建机房的裸机/虚拟机，不涉及云元数据、容器编排或托管 IAM → 用 `../pentest-tools/SKILL.md`
- 目标只是一个应用层 HTTP 接口，SSRF 之外没有云身份面 → 用 `../api-security/SKILL.md`
- 要审的是构建流水线/制品来源，而非运行时集群 → 用 `../supply-chain-security/SKILL.md`
- 逃逸已拿到宿主 root，接下来是内网横向与域控 → 用 `../attack-chain/SKILL.md`
- 目标只是跑在 K8s 上的应用代码缺陷（非 RBAC/配置/逃逸面） → 用 `../code-audit/SKILL.md`
- 集群里的托管数据库问题是弱口令/权限过大，而非集群本身 → 用 `../database-security/SKILL.md`

## When to Pivot

信号与判据见 `../ops/skill-pivot-contract.md`。本技能去向：

| 触发证据 | 换到 |
|---|---|
| `aws sts get-caller-identity`（或 `gcloud auth list`）返回的账号/项目与预期不符，说明手上凭据不是你以为的那条 | 先顺凭据来源链（CI 变量 / 实例角色 / 共享 key）查清它从哪来，链上有横向再转 `../attack-chain/SKILL.md` |
| `curl -m 2` 打 IMDS 直接回显 IAM 临时凭据（IMDSv1 可达，未强制 v2 token） | 评估该角色可扮演链后转 `../attack-chain/SKILL.md` |
| 容器内 `capsh --print` 出现 `cap_sys_admin`，或 `mount` 显示 hostPath / runc 卷可写 | `../kernel-exploit/SKILL.md` 做逃逸面验证 |
| CI runner 的 pipeline 变量或未保护分支可被本命名空间内的 SA 写入 | `../supply-chain-security/SKILL.md` |
| `kubectl auth can-i --list` 连续两次（间隔 >2 分钟）对同一 verb 都返回 `Forbidden`，且期间 RBAC 对象未变 | 别硬试（会刷审计告警）；换 SA（`kubectl get sa -A`）或换 namespace 面，或转 `../attack-chain/SKILL.md` 找别的入口 |
| `trivy image` 报出容器内 stripped 原生二进制的缺陷，且该二进制有私有 RWX 段 | 走 `idapro` / `pyghidra` MCP 静态，或转 `../reverse-engineering/SKILL.md` |
| 暴露的 2379(etcd) / 10250(kubelet)，`nmap` 显示匿名可读（etcd v3 未鉴权，5 分钟内可枚举出 >100 个 key） | 用匿名面拉 pod/secret 清单，横向转 `../attack-chain/SKILL.md` |

## 定义完成

本技能产出算「完成」的**外部可观测**条件（不许写形容词）：

- IAM 权限矩阵落盘（主体 × 动作 × 资源），每条有实测证据
- 逃逸/越权的 PoC 命令落盘并可重放
- 修复建议对应到具体配置项（不是泛泛而谈）

## 输出契约

```
FACT:       <观察，带来源：命令 / 文件:行 / Evidence ID>
HYPOTHESIS: <可测试断言 + confidence: high|medium|low>（状态见 `../ops/binary-model.md`）
QUESTION:   <当前最大不确定点>
NEXT:       <继续 | 换技能 | 停止（附成本判据）>
```

## 置信度词表

词表见 `../ops/confidence-vocabulary.md`。本技能特有判据：

- `confirmed`：权限提升链每一跳都有 API 返回实测（不是策略文档推断）
- 硬判据：`sts get-caller-identity` 的主体与你预期不符时，凭据来源链没落盘之前，任何"可扮演到 X"的结论只能记 `low`
- `low`：仅凭 IAM policy JSON 静态推断可达，未实际调用
