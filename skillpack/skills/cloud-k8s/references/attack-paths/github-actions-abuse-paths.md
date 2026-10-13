# GitHub Actions 滥用路径

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/ctf-website/techniques/10-cloud/github-actions-abuse-paths.md`（GPL-3.0）。原 frontmatter 的 `mcp_tools` 映射已剔除——本技能包未挂载 `run_ctf_tool` / `http_probe`，改用本地工具链。
> **能力域**：本文为技术能力说明，按项目 `scope.md` 直接套用。
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

- Python 解释器用探测层的 `python`。
- 本文脚本默认只读、只打点；扩大范围前先回到 scope 确认。

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
