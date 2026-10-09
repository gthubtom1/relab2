# AWS IAM 权限枚举与提权路径

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/ctf-website/techniques/10-cloud/aws-iam-privesc.md`（GPL-3.0）。原 frontmatter 的 `mcp_tools` 映射已剔除——本技能包未挂载 `run_ctf_tool` / `http_probe`，改用本地工具链。
> **授权范围**：仅限 CTF 靶场 / AWD 赛场 / 已签署授权的测试环境。任何真实第三方目标、真实凭据、真实支付/生产流量都禁止套用本文流程。
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

- 授权：目标在 scope 内（`case-init.ps1` 已 grant），测试时段与限速已约定。
- 工具定位走探测层，别猜路径：

```powershell
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
$r = Resolve-ReverseToolSpec -Name '<toolid>'   # 例：sqlmap / httpx / ffuf / curl / python
& $r.Command <参数>                                # 永远用完整路径，不依赖 cwd
```

- Python 解释器用探测层的 `python`（本机逆向库集中在 `D:\EXE\python\python.exe`，`venv-re` 是空壳，别去那里找库）。
- 本文脚本默认只读、只打点；扩大范围前先回到 scope 确认。
- 本文涉及的工具与本机实际状态（探测层 `Resolve-ReverseToolSpec` 于 2026-10-10 实测）：

| 工具 | 本机状态 | 本机命令 / 替代方案 |
|---|---|---|
| `playwright` | ✅ 已验证 | `& (Resolve-ReverseToolSpec -Name 'playwright').Command ...` → `D:\Tools\Node\playwright.cmd` |
| `objection` | ✅ 已验证 | `& (Resolve-ReverseToolSpec -Name 'objection').Command ...` → `D:\EXE\python\Scripts\objection.exe` |
| `subfinder` | ✅ 已验证 | `& (Resolve-ReverseToolSpec -Name 'subfinder').Command ...` → `D:\Tools\subfinder\subfinder.exe` |
| `gobuster` | ✅ 已验证 | `& (Resolve-ReverseToolSpec -Name 'gobuster').Command ...` → `D:\Tools\gobuster\gobuster.exe` |
| `mitmdump` | ✅ 已验证 | `& (Resolve-ReverseToolSpec -Name 'mitmdump').Command ...` → `D:\EXE\python\Scripts\mitmdump.exe` |
| `binwalk` | ✅ 已验证 | `& (Resolve-ReverseToolSpec -Name 'binwalk').Command ...` → `C:\Users\toti\.cargo\bin\binwalk.exe` |
| `openssl` | ✅ 已验证 | `& (Resolve-ReverseToolSpec -Name 'openssl').Command ...` → `C:\Program Files\Git\usr\bin\openssl.exe` |
| `katana` | ✅ 已验证 | `& (Resolve-ReverseToolSpec -Name 'katana').Command ...` → `D:\Tools\katana\katana.exe` |
| `nuclei` | ✅ 已验证 | `& (Resolve-ReverseToolSpec -Name 'nuclei').Command ...` → `D:\Tools\nuclei\nuclei.exe` |
| `python` | ✅ 已验证 | `& (Resolve-ReverseToolSpec -Name 'python').Command ...` → `D:\EXE\python\python.exe` |
| `sqlmap` | ✅ 已验证 | `& (Resolve-ReverseToolSpec -Name 'sqlmap').Command ...` → `D:\Tools\sqlmap\sqlmap.py` |
| `tshark` | ✅ 已验证 | `& (Resolve-ReverseToolSpec -Name 'tshark').Command ...` → `D:\Tools\Wireshark\tshark.exe` |
| `frida` | ✅ 已验证 | `& (Resolve-ReverseToolSpec -Name 'frida').Command ...` → `D:\EXE\python\Scripts\frida.exe` |
| `httpx` | ✅ 已验证 | `& (Resolve-ReverseToolSpec -Name 'httpx').Command ...` → `D:\Tools\httpx\httpx.exe` |
| `naabu` | ✅ 已验证 | `& (Resolve-ReverseToolSpec -Name 'naabu').Command ...` → `D:\Tools\naabu\naabu.exe` |
| `curl` | ✅ 已验证 | `& (Resolve-ReverseToolSpec -Name 'curl').Command ...` → `C:\WINDOWS\system32\curl.exe` |
| `dnsx` | ✅ 已验证 | `& (Resolve-ReverseToolSpec -Name 'dnsx').Command ...` → `D:\Tools\dnsx\dnsx.exe` |
| `ffuf` | ✅ 已验证 | `& (Resolve-ReverseToolSpec -Name 'ffuf').Command ...` → `D:\Tools\ffuf\ffuf.exe` |
| `nmap` | ✅ 已验证 | `& (Resolve-ReverseToolSpec -Name 'nmap').Command ...` → `D:\Tools\nmap\nmap.exe` |
| `node` | ✅ 已验证 | `& (Resolve-ReverseToolSpec -Name 'node').Command ...` → `D:\Tools\Node\node.exe` |
| `adb` | ✅ 已验证 | `& (Resolve-ReverseToolSpec -Name 'adb').Command ...` → `D:\Tools\android\AndroidKiller_fix\bin\adb\adb.exe` |
| `git` | ✅ 已验证 | `& (Resolve-ReverseToolSpec -Name 'git').Command ...` → `C:\Program Files\Git\cmd\git.exe` |
| `interactsh-client` | 未安装 | OOB 通道需自备回显服务（授权环境内的 VPS + `python -m http.server`）；本机无此工具 |
| `nuclei-templates` | 随 nuclei 提供 | `nuclei -t <模板目录>`；模板需联网 `-update-templates` |

- 上表中标「未安装」的工具**不要照抄原库的裸命令**：`Get-Command` 查空就下结论是错的，
  但四级探测 `Available=False` 是结论——此时按替代方案手写脚本，或先装再跑。


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
