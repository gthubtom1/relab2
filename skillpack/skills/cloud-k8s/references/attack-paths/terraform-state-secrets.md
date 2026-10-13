# Terraform State 与 IaC 凭证泄露

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/ctf-website/techniques/10-cloud/terraform-state-secrets.md`（GPL-3.0）。原 frontmatter 的 `mcp_tools` 映射已剔除——本技能包未挂载 `run_ctf_tool` / `http_probe`，改用本地工具链。
> **能力域**：本文为技术能力说明，按项目 `scope.md` 直接套用。
> **什么时候用**：命中「Terraform / tfstate / IaC / backend」这类信号时，把本文当打点清单读；命中即进「步骤」，命中不了就换主题。

## 适用信号

- Terraform
- tfstate
- IaC
- backend
- state file
- terraform plan
- cloud secret
- S3 backend
- CI artifact

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

1. 泄露文件探测
2. State 快速拆解
3. 后端配置分析 — 后端配置本身不一定是凭证，但它给出云账号、bucket、路径和环境命名。结合泄露 IAM 凭证时，可快速定位 state 存储位置。

## 判据

判据必须是外部可观测的（状态码、响应字段、差分、落盘文件），不是「命令有输出」。

- **输入信号** — Web 目录或 artifact 中出现 `terraform.tfstate`
- **输入信号** — Git 仓库包含 `backend "s3"`、`backend "azurerm"`、`backend "gcs"`
- **输入信号** — CI 日志包含 `terraform plan` / `terraform output`
- **输入信号** — `*.tfvars`、`.terraform.lock.hcl`、`crash.log` 暴露
- **输入信号** — state JSON 中出现 `sensitive_values` 或 provider credential

## 坑

- 探针命令在**未本机验证**时不要当成既定事实跑；先用探测层确认 `Available=True`。
- 噪声排除：先固定 baseline（同 URL 同 token 跑 3 次），再只改一个变量做差分。
- 不要把「状态码 200」当命中——WAF/缓存/软 404 都返回 200，命中判据要落到具体业务字段。

## 相关

- 见本技能 `../../SKILL.md` 的 references 索引。

## 技术正文

> 以下为原库正文（保留全部技术细节与脚本），仅移除原 `MCP 工具映射` 章节并重写跨文档链接。

## 场景

目标暴露了 `.tfstate`、`terraform.tfvars`、`.terraform/`、CI artifact 或 plan 输出。Terraform state 常保存资源 ID、连接串、明文 output、随机密码结果和云资源依赖关系，是从源码泄露走向云资源访问的重要桥。

## 输入信号

- Web 目录或 artifact 中出现 `terraform.tfstate`
- Git 仓库包含 `backend "s3"`、`backend "azurerm"`、`backend "gcs"`
- CI 日志包含 `terraform plan` / `terraform output`
- `*.tfvars`、`.terraform.lock.hcl`、`crash.log` 暴露
- state JSON 中出现 `sensitive_values` 或 provider credential

## 泄露文件探测

```python
# terraform_leak_probe.py - 只探测公开路径，不爆破
import requests

COMMON = [
    "/terraform.tfstate",
    "/terraform.tfstate.backup",
    "/.terraform/terraform.tfstate",
    "/terraform.tfvars",
    "/prod.tfvars",
    "/crash.log",
]

def probe(base):
    for path in COMMON:
        url = base.rstrip("/") + path
        r = requests.get(url, timeout=5)
        if r.status_code == 200 and ("terraform" in r.text.lower() or "resources" in r.text[:500]):
            print("[hit]", url, len(r.text))

probe("https://target.example")
```

## State 快速拆解

```python
# tfstate_paths.py - 拆 state，找下一跳资源和敏感字段
import json
from pathlib import Path

SENSITIVE_KEYS = ("password", "secret", "token", "key", "credential", "connection_string")

state = json.loads(Path("terraform.tfstate").read_text(encoding="utf-8"))
for res in state.get("resources", []):
    rtype = res.get("type")
    name = res.get("name")
    for inst in res.get("instances", []):
        attrs = inst.get("attributes", {})
        hits = [k for k in attrs if any(s in k.lower() for s in SENSITIVE_KEYS)]
        if hits:
            print(f"[sensitive-field] {rtype}.{name}: {hits}")
        if rtype in ("aws_iam_role", "aws_lambda_function", "aws_s3_bucket", "kubernetes_secret"):
            print(f"[resource] {rtype}.{name}")
```

## 后端配置分析

```hcl
terraform {
  backend "s3" {
    bucket = "example-tfstate"
    key    = "prod/terraform.tfstate"
    region = "us-east-1"
  }
}
```

后端配置本身不一定是凭证，但它给出云账号、bucket、路径和环境命名。结合泄露 IAM 凭证时，可快速定位 state 存储位置。

## 攻击链

```text
Git leak → backend config → S3 tfstate → output password → DB/Flag
CI artifact → terraform plan → resource topology → API Gateway/Lambda/S3 目标定位
tfstate → aws_iam_role / policy → PassRole 边 → IAM 提权
tfvars leak → provider credential → sts:GetCallerIdentity → 云资源枚举
```

## Evidence

记录: 泄露文件路径、state serial/lineage、资源类型统计、敏感字段名、output 名称、backend 位置、可直接访问的云资源。
