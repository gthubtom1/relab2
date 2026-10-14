# Kubernetes RBAC 攻击路径

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/ctf-website/techniques/10-cloud/k8s-rbac-attack-paths.md`（GPL-3.0）。原 frontmatter 的 `mcp_tools` 映射已剔除——本技能包未挂载 `run_ctf_tool` / `http_probe`，改用本地工具链。
> **能力域**：本文为技术能力说明，按项目 `scope.md` 直接套用。
> **什么时候用**：命中「Kubernetes / RBAC / SelfSubjectAccessReview / RoleBinding」这类信号时，把本文当打点清单读；命中即进「步骤」，命中不了就换主题。

## 适用信号

- Kubernetes
- RBAC
- SelfSubjectAccessReview
- RoleBinding
- ClusterRoleBinding
- pods/exec
- secrets/get
- serviceaccounts/token

## 前置

- 前置：目标可达；测试时段与限速已约定（打快了会把自己变成 DoS）。
- 工具定位走探测层，别猜路径：

```powershell
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
$r = Resolve-ReverseToolSpec -Name '<toolid>'   # 例：sqlmap / httpx / ffuf / curl / python
& $r.Command <参数>                                # 永远用完整路径，不依赖 cwd
```

- Python 解释器用探测层的 `python`。
- 本文脚本默认只读、只打点；扩大范围前先回到 scope 确认。

## 步骤

本文正文按下列小节顺序推进，**每一步的完整命令与脚本在「技术正文」对应小节里**（这类文档以代码体 + 表格为主，按小节读比按 bullet 读快）：

1. Pod 内身份确认 — 如果能访问 API，继续做 SelfSubjectRulesReview 或逐项 SelfSubjectAccessReview。
2. 权限探针
3. 高价值权限解释

## 判据

判据必须是外部可观测的（状态码、响应字段、差分、落盘文件），不是「命令有输出」。

- **输入信号** — `/var/run/secrets/kubernetes.io/serviceaccount/token` 存在
- **输入信号** — 环境变量中有 `KUBERNETES_SERVICE_HOST`
- **输入信号** — kubeconfig 泄露，包含 `client-certificate-data` 或 bearer token
- **输入信号** — API 返回 `Forbidden` 但暴露了当前 user/group
- **输入信号** — `kubectl auth can-i` 对部分 verbs 返回 yes

## 坑

- 探针命令在**未本机验证**时不要当成既定事实跑；先用探测层确认 `Available=True`。
- 噪声排除：先固定 baseline（同 URL 同 token 跑 3 次），再只改一个变量做差分。
- 不要把「状态码 200」当命中——WAF/缓存/软 404 都返回 200，命中判据要落到具体业务字段。

## 相关

- 见本技能 `../../SKILL.md` 的 references 索引。

## 技术正文

> 以下为原库正文（保留全部技术细节与脚本），仅移除原 `MCP 工具映射` 章节并重写跨文档链接。

## 场景

已经获得 Pod 内命令执行、泄露的 kubeconfig，或 SSRF 能访问 Kubernetes API。目标是判断当前身份在 namespace 和 cluster 维度能做什么，并找出从低权限到读 secret、exec、创建 workload 或云凭证访问的最短路径。

## 输入信号

- `/var/run/secrets/kubernetes.io/serviceaccount/token` 存在
- 环境变量中有 `KUBERNETES_SERVICE_HOST`
- kubeconfig 泄露，包含 `client-certificate-data` 或 bearer token
- API 返回 `Forbidden` 但暴露了当前 user/group
- `kubectl auth can-i` 对部分 verbs 返回 yes

## Pod 内身份确认

```bash
TOKEN=/var/run/secrets/kubernetes.io/serviceaccount/token
CA=/var/run/secrets/kubernetes.io/serviceaccount/ca.crt
API=https://kubernetes.default.svc

curl --cacert "$CA" -H "Authorization: Bearer $(cat $TOKEN)" \
  "$API/api"
```

如果能访问 API，继续做 `SelfSubjectRulesReview` 或逐项 `SelfSubjectAccessReview`。

## 权限探针

```python
# k8s_rbac_probe.py - RBAC 可打权限矩阵
import json
import os
import requests

TOKEN_PATH = "/var/run/secrets/kubernetes.io/serviceaccount/token"
CA_PATH = "/var/run/secrets/kubernetes.io/serviceaccount/ca.crt"
API = "https://kubernetes.default.svc"

CHECKS = [
    ("", "pods", "list"),
    ("", "pods", "create"),
    ("", "pods/exec", "create"),
    ("", "secrets", "get"),
    ("", "configmaps", "list"),
    ("", "serviceaccounts/token", "create"),
    ("apps", "deployments", "patch"),
    ("rbac.authorization.k8s.io", "rolebindings", "create"),
    ("rbac.authorization.k8s.io", "clusterrolebindings", "create"),
]

def can_i(group, resource, verb, namespace="default"):
    token = open(TOKEN_PATH, encoding="utf-8").read().strip()
    body = {
        "apiVersion": "authorization.k8s.io/v1",
        "kind": "SelfSubjectAccessReview",
        "spec": {"resourceAttributes": {
            "namespace": namespace,
            "group": group,
            "resource": resource,
            "verb": verb,
        }},
    }
    r = requests.post(
        f"{API}/apis/authorization.k8s.io/v1/selfsubjectaccessreviews",
        headers={"Authorization": f"Bearer {token}"},
        json=body,
        verify=CA_PATH,
        timeout=5,
    )
    status = r.json().get("status", {})
    print(f"{verb:8s} {group or 'core':30s} {resource:28s} allowed={status.get('allowed')}")

for item in CHECKS:
    can_i(*item)
```

## 高价值权限解释

| 权限 | 攻击意义 | 验证方式 |
|---|---|---|
| `secrets/get` | 读取凭证、token、数据库密码 | 下一跳打 DB、云凭证或镜像仓库 |
| `pods/exec create` | 进入其他 Pod，横向读取业务环境变量 | 下一跳挑高权限 Pod 或业务后端 |
| `pods/create` | 创建自控 Pod、挂载 SA、尝试 hostPath | 下一跳 privileged/hostPath/IRSA |
| `serviceaccounts/token create` | 为其他 SA 签发 token | 下一跳切换身份重跑权限矩阵 |
| `rolebindings/create` | 在 namespace 内扩大权限 | 下一跳绑定 edit/admin |
| `clusterrolebindings/create` | 集群级接管 | 下一跳绑定 cluster-admin |

## 攻击链

```text
Pod RCE → SA token → can-i secrets/get → 读业务 secret → DB/Flag
Pod RCE → can-i pods/exec → exec 到高权限 Pod → 读云凭证
Pod RCE → can-i pods/create → 创建挂载高权限 SA 的 Pod → secrets/list
Leaked kubeconfig → rolebinding create → 绑定 edit/admin → namespace 接管
K8s service account → IRSA → AWS AssumeRoleWithWebIdentity → 云资源访问
```

## Evidence

记录: 当前 namespace、service account 名、`can-i` 检查矩阵、允许的高价值权限、下一跳 pod/secret/rolebinding、成功返回码。
