# GitHub Actions 滥用路径

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/ctf-website/techniques/10-cloud/github-actions-abuse-paths.md`（GPL-3.0）。原 frontmatter 的 `mcp_tools` 映射已剔除——本技能包未挂载 `run_ctf_tool` / `http_probe`，改用本地工具链。
> **授权范围**：仅限 CTF 靶场 / AWD 赛场 / 已签署授权的测试环境。任何真实第三方目标、真实凭据、真实支付/生产流量都禁止套用本文流程。
> **什么时候用**：命中「GitHub Actions / pull_request_target / GITHUB_TOKEN / self-hosted runner」这类信号时，把本文当打点清单读；命中即进「步骤」，命中不了就换主题。

## 适用信号

- GitHub Actions
- pull_request_target
- GITHUB_TOKEN
- self-hosted runner
- workflow injection
- OIDC
- cache poisoning
- artifact leak

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

1. **关键利用分叉** — run: echo "${{ github.event.pull_request.title }}"

## 判据

判据必须是外部可观测的（状态码、响应字段、差分、落盘文件），不是「命令有输出」。

- **输入信号** — workflow 中出现 `pull_request_target`
- **输入信号** — `run:` 直接拼接 `${{ github.event.pull_request.title }}`
- **输入信号** — `permissions: write-all` 或未显式设置 permissions
- **输入信号** — `runs-on: self-hosted`
- **输入信号** — `id-token: write` 与云角色 trust policy 绑定
- **输入信号** — artifact/cache 被 release 或 deploy workflow 消费

## 坑

- 探针命令在**未本机验证**时不要当成既定事实跑；先用探测层确认 `Available=True`。
- 噪声排除：先固定 baseline（同 URL 同 token 跑 3 次），再只改一个变量做差分。
- 不要把「状态码 200」当命中——WAF/缓存/软 404 都返回 200，命中判据要落到具体业务字段。

## 相关

- 见本技能 `../../SKILL.md` 的 references 索引。

## 技术正文

> 以下为原库正文（保留全部技术细节与脚本），仅移除原 `MCP 工具映射` 章节并重写跨文档链接。

## 场景

项目使用 GitHub Actions 构建、测试、发布镜像或部署云资源。实战优先看三条线：PR 数据能否进 shell，runner 能否接触 secrets，OIDC 能否换云凭证。

## 输入信号

- workflow 中出现 `pull_request_target`
- `run:` 直接拼接 `${{ github.event.pull_request.title }}`
- `permissions: write-all` 或未显式设置 permissions
- `runs-on: self-hosted`
- `id-token: write` 与云角色 trust policy 绑定
- artifact/cache 被 release 或 deploy workflow 消费

## Workflow 入口打点

```python
# gha_workflow_paths.py - 找可打的 workflow 入口
from pathlib import Path
import re

ROOT = Path(".github/workflows")
DANGEROUS_CONTEXT = re.compile(r"\$\{\{\s*github\.event\.(pull_request|issue|comment|head_commit)")

for path in ROOT.glob("*.y*ml"):
    text = path.read_text(encoding="utf-8", errors="replace")
    findings = []
    if "pull_request_target" in text:
        findings.append("pull_request_target")
    if "self-hosted" in text:
        findings.append("self-hosted-runner")
    if "permissions: write-all" in text or "contents: write" in text:
        findings.append("broad-token-permission")
    if "id-token: write" in text:
        findings.append("oidc-token-enabled")
    if DANGEROUS_CONTEXT.search(text) and "run:" in text:
        findings.append("untrusted-context-in-run")
    if findings:
        print(path, findings)
```

## 关键利用分叉

### 不可信上下文进入 shell

```yaml
# PR title/body/branch name 进入 shell
- run: echo "${{ github.event.pull_request.title }}"
```

命中后下一跳：构造 PR title/body/branch，让 shell 解释分隔符、命令替换或换行。

```yaml
# payload 形态示例，按上下文调整引号闭合
title: 'ok"; id; env | sort; #'
```

### pull_request_target 误用

```text
pull_request_target 在 base repo 权限上下文运行。
危险组合: pull_request_target + checkout PR head + secrets/write token。
命中后下一跳: 改 PR 代码或 workflow 输入，让 base repo token/secrets 进入执行路径。
```

### OIDC 云角色信任过宽

```json
{
  "Condition": {
    "StringLike": {
      "token.actions.githubusercontent.com:sub": "repo:ORG/REPO:*"
    }
  }
}
```

命中后下一跳：从非预期 branch/environment 请求 OIDC token，换云临时凭证，再转 IAM 路径。

## 攻击链

```text
PR title injection → workflow shell → GITHUB_TOKEN write → 修改 release artifact
pull_request_target → checkout untrusted head → secrets 暴露 → 云部署接管
self-hosted runner → workspace 残留 → 后续 job 读取 secret/cache
OIDC trust 过宽 → 任意 branch 获取云临时凭证 → Terraform apply
```

## Evidence

记录: workflow 文件路径、触发事件、危险上下文行、token permissions、runner label、OIDC trust 条件、artifact/cache 生产者和消费者、成功命令输出。
