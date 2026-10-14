# AWS IAM 权限枚举与提权路径

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/ctf-website/techniques/10-cloud/aws-iam-privesc.md`（GPL-3.0）。原 frontmatter 的 `mcp_tools` 映射已剔除——本技能包未挂载 `run_ctf_tool` / `http_probe`，改用本地工具链。
> **能力域**：本文为技术能力说明，按项目 `scope.md` 直接套用。
> **什么时候用**：命中「AWS / IAM / STS / AssumeRole」这类信号时，把本文当打点清单读；命中即进「步骤」，命中不了就换主题。

## 适用信号

- AWS
- IAM
- STS
- AssumeRole
- PassRole
- policy simulation
- IRSA
- metadata
- 云凭证
- 权限提升

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

1. 身份确认 — 输出重点看三件事：Account、Arn、UserId。如果 ARN 是 assumed-role/.../botocore-session-，下一跳追 role trust；如果是 user，下一跳查 attached…
2. 权限打点
3. 常见提权边
4. iam:PassRole + lambda:CreateFunction
5. sts:AssumeRole — 检查点是 trust policy。只要当前 principal 命中 Principal 或 Condition，这条边就能继续走。
6. CloudFormation / ECS / SSM 间接执行

## 判据

判据必须是外部可观测的（状态码、响应字段、差分、落盘文件），不是「命令有输出」。

- **输入信号** — 响应中出现 `AccessKeyId`、`SecretAccessKey`、`SessionToken`
- **输入信号** — `AWS_ACCESS_KEY_ID` / `AWS_SESSION_TOKEN` 出现在环境变量
- **输入信号** — SSRF 可访问 `169.254.169.254`
- **输入信号** — Pod 中存在 projected service account token，且注解指向 `eks.amazonaws.com/role-arn`
- **输入信号** — CI/CD 日志或 artifact 泄露云凭证

## 坑

- 探针命令在**未本机验证**时不要当成既定事实跑；先用探测层确认 `Available=True`。
- 噪声排除：先固定 baseline（同 URL 同 token 跑 3 次），再只改一个变量做差分。
- 不要把「状态码 200」当命中——WAF/缓存/软 404 都返回 200，命中判据要落到具体业务字段。

## 相关

- 见本技能 `../../SKILL.md` 的 references 索引。

## 技术正文

> 以下为原库正文（保留全部技术细节与脚本），仅移除原 `MCP 工具映射` 章节并重写跨文档链接。

## 场景

目标已经拿到一组临时 AWS 凭证，来源可能是 SSRF 打到 metadata、Lambda 环境变量、CI/CD runner 环境变量、K8s IRSA token 交换结果，或者泄露的 `~/.aws/credentials`。下一步不是盲扫资源，而是先确认身份、边界和可利用权限。

## 输入信号

- 响应中出现 `AccessKeyId`、`SecretAccessKey`、`SessionToken`
- `AWS_ACCESS_KEY_ID` / `AWS_SESSION_TOKEN` 出现在环境变量
- SSRF 可访问 `169.254.169.254`
- Pod 中存在 projected service account token，且注解指向 `eks.amazonaws.com/role-arn`
- CI/CD 日志或 artifact 泄露云凭证

## 身份确认

```bash
export AWS_ACCESS_KEY_ID="ASIAEXAMPLE"
export AWS_SECRET_ACCESS_KEY="EXAMPLE_SECRET"
export AWS_SESSION_TOKEN="EXAMPLE_SESSION"
export AWS_DEFAULT_REGION="us-east-1"

aws sts get-caller-identity
aws iam get-user 2>$null || true
```

输出重点看三件事：`Account`、`Arn`、`UserId`。如果 ARN 是 `assumed-role/.../botocore-session-*`，下一跳追 role trust；如果是 user，下一跳查 attached policy、inline policy 和 access key 年龄。

## 权限打点

```python
# iam_probe.py - 身份确认 + 可用权限打点
import boto3

def probe_identity():
    sts = boto3.client("sts")
    ident = sts.get_caller_identity()
    print("[identity]", ident["Arn"], ident["Account"])
    return ident

def simulate_actions(principal_arn: str):
    iam = boto3.client("iam")
    actions = [
        "iam:PassRole",
        "sts:AssumeRole",
        "lambda:UpdateFunctionCode",
        "lambda:CreateFunction",
        "ecs:RegisterTaskDefinition",
        "ecs:RunTask",
        "cloudformation:CreateStack",
        "ssm:SendCommand",
        "secretsmanager:GetSecretValue",
        "s3:GetObject",
        "dynamodb:Scan",
    ]
    resp = iam.simulate_principal_policy(
        PolicySourceArn=principal_arn,
        ActionNames=actions,
        ResourceArns=["*"],
    )
    for item in resp.get("EvaluationResults", []):
        print(item["EvalActionName"], item["EvalDecision"])

if __name__ == "__main__":
    ident = probe_identity()
    if ":assumed-role/" not in ident["Arn"]:
        simulate_actions(ident["Arn"])
```

## 常见提权边

### iam:PassRole + lambda:CreateFunction

```text
已有权限: iam:PassRole 指向高权限 role + lambda:CreateFunction/UpdateFunctionCode
效果: 创建或更新 Lambda，让函数以高权限 role 运行
证据: CloudTrail 中 CreateFunction/UpdateFunctionCode + iam:PassedToService=lambda.amazonaws.com
```

### sts:AssumeRole

```bash
aws sts assume-role \
  --role-arn arn:aws:iam::111122223333:role/LabAdminRole \
  --role-session-name reverselab-session
```

检查点是 trust policy。只要当前 principal 命中 `Principal` 或 `Condition`，这条边就能继续走。

### CloudFormation / ECS / SSM 间接执行

```text
cloudformation:CreateStack + iam:PassRole → 创建高权限资源
ecs:RunTask + taskRoleArn → 以 task role 读 secrets
ssm:SendCommand → 对已托管实例执行命令
```

## 攻击链

```text
SSRF → metadata credential → sts:GetCallerIdentity → policy simulation → s3/secrets 读取 → Flag
CI/CD env leak → AWS credential → iam:PassRole + Lambda → 高权限 role → 数据访问
K8s IRSA token → AssumeRoleWithWebIdentity → pod role → ECR/S3/SecretsManager
Lambda RCE → env credential → sts:AssumeRole → 跨账号资源访问
```

## Evidence

记录: 凭证来源、`sts:GetCallerIdentity` 输出、允许的关键 action、策略模拟结果、下一跳 role/resource、访问资源的最小证明。
