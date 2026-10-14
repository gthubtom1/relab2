---
name: supply-chain-security
description: 供应链安全评估：SBOM、SCA 依赖漏洞与可达性、CI/CD 管道审计、容器镜像。用于：审依赖许可、查组件 CVE、测 GitHub Actions 信任边界。
---
# Supply Chain Security Testing

## ACTION REQUIRED（读完后立刻执行）

1. `NOW`: 读 `../field-journal/precedent-pentest.md` —— 本机做过多轮的常规操作清单，直接照做，不要停在犹豫上
2. `NOW`: **查经验卡** —— `python skills/scripts/experience-card.py search "<你看到的症状>"`。
   命中就读那张卡的 `invariant` + `decision.action`，并**逐条对照** `scope.appliesWhen`
   与 `scope.stopsWhen`：少一条前提就停用；命中任一停止条件就停。
   历史卡**不替代**当前目标的实测证据。详见 `../experience-cards/INDEX.md`。
3. `NOW`: 确认当前任务是否命中本 skill 的适用范围
5. `NEXT`：**工具定位** —— 先载入探测层 `. C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1`（本机固定路径；万一这台机器还没建好、该文件不存在，改成从本文件往上两级的 `..\..\skills\scripts\lib\Bootstrap.ps1`），再 `Resolve-ReverseToolSpec -Name <id>`，按返回的 `Command` 调（完整路径，别依赖 cwd）。**`Get-Command` 返回空 ≠ 本机缺工具**（PATH 快照陷阱，见 `../references/env-selfcheck.md`）；四级探测全部 `Available=False` 才允许报缺。`../TOOLS.md` 是装法说明书，不是路径索引。禁止猜路径。
6. `NEXT`: 缺工具时调用 bootstrap，不要猜路径
7. `ACT`: 按本卡的「工作流」挑**当下适用**的那一条动手；不要停在确认状态

> SBOM / SCA / CI/CD 管道 / 依赖溯源
> 法规驱动：美国行政令 SBOM、中国国标、EU CRA

## 适用场景

- 软件供应链安全评估
- 开源依赖漏洞扫描与验证
- CI/CD 管道安全审计
- 容器镜像安全分析
- 第三方组件合规审查
- 构建产物溯源与完整性验证

## 六层供应链治理框架

```text
Layer 1: 源码信任评估 → 上游仓库/维护者/发布历史审查
Layer 2: 构建管道集成 → CI/CD 安全门禁、签名验证
Layer 3: 制品分发完整性 → 签名、校验和、SBOM 附加
Layer 4: 运行时保护 → 容器扫描、准入控制
Layer 5: 持续监控 → CVE 实时追踪、漏洞可达性分析
Layer 6: 事件响应 → 供应链攻击应急、回滚策略
```

## 工作流

### 1. SBOM 生成与审计

```text
生成 SBOM：
□ CycloneDX 格式: cdxgen → bom.json
□ SPDX 格式: sbom-tool generate
□ Syft: syft <image|dir> -o spdx-json

审计要点：
□ 是否存在未知/未授权的依赖
□ 是否存在已废弃/停止维护的包
□ 许可证冲突检测
□ 直接依赖 vs 传递依赖清单
□ 每个组件的发布时间线和维护者状态
```

### 2. 软件组成分析（SCA）

```bash
# OSV-Scanner（免费、Google 维护）
osv-scanner scan -r . --format json

# OWASP Dependency-Track（企业级持续监控）
docker run -p 8080:8080 dependencytrack/apiserver
# → 上传 SBOM → 自动匹配 NVD/OSV/GitHub Advisory

# Snyk（商业）
snyk test --all-projects
snyk monitor  # 持续监控

# Trivy（容器 + 依赖 + IaC）
trivy fs .          # 文件系统扫描
trivy image nginx   # 容器镜像
trivy config .      # IaC 配置
```

### 3. 漏洞可达性验证

```text
SCA 告警 ≠ 实际风险！大多数 SCA 工具只有 ~15% 的告警是实际可达的。

验证步骤：
1. 用 Dependency-Track 或 Trivy 获取 CVE 列表
2. 筛选 CVSS ≥ 7.0 的漏洞
3. 对有 PoC 的 CVE 做可达性分析
   - Code Property Graph 切片: 追踪用户输入到漏洞函数的路径
   - DEPTEX 方法: EPD (Execution Path Dominance) + LLM 语义验证
4. 在隔离环境中验证 PoC
5. 对可达的漏洞按实际影响排序修复优先级
```

工具参考：
- CodeQL: GitHub 代码查询 → 数据流分析
- Snyk Code: 可达性标记
- DEPTEX: LLM 辅助上下文感知风险评估

### 4. CI/CD 管道安全

```text
安全检查点：
□ 代码提交 → pre-commit hook: gitleaks (密钥扫描)
□ PR 阶段 → SCA 扫描 (Trivy/OSV-Scanner)
□ 构建阶段 → 制品签名 (cosign)
□ 推送阶段 → SBOM 附加 (syft + attest)
□ 部署阶段 → 准入控制 (OPA/Kyverno + 镜像扫描)
□ 运行时 → 持续漏洞监控 (Dependency-Track)

管道自身安全：
□ Pipeline as Code 审计（GitHub Actions / GitLab CI 配置注入）
□ Runner 隔离（防止恶意构建突破容器）
□ 密钥管理（Actions Secrets / Vault，禁止硬编码）
□ 第三方 Action 审查（锁定 commit SHA，非 tag）
```

### 5. 容器镜像安全

```bash
# Dockerfile 审计
hadolint Dockerfile

# 镜像扫描（多层：OS + 应用依赖 + 配置）
trivy image --severity HIGH,CRITICAL nginx:latest

# 最小基础镜像
# 优先: distroless → alpine → slim → 避免 latest
docker scout quickview nginx:latest

# 镜像签名
cosign sign --key cosign.key myimage:tag
cosign verify --key cosign.pub myimage:tag
```

### 6. 第三方依赖审查

```text
新增依赖 Checklist：
□ 维护状态：最近 6 个月有提交？维护者活跃度？
□ 安全历史：过去有无被植入恶意代码？
□ 依赖树：引入后新增多少传递依赖？
□ 许可证：与项目许可证兼容？
□ 替代方案：有无更安全的替代（Snyk Advisor / Socket.dev 评分）？

风险评估矩阵：
  高维护 × 低依赖数 × 兼容许可证 → 低风险
  低维护 × 高依赖数 × 许可证冲突 → 高风险
```

## 工具链

| 工具 | 用途 | 调用口径 |
|------|------|------|
| `Syft` | SBOM 生成（SPDX / CycloneDX） | `Syft <image\|dir> -o spdx-json > sbom.json` |
| `cdxgen` | 容器/源码 CycloneDX SBOM | `cdxgen -o bom.json .` |
| `trivy` | 依赖 + 镜像 + IaC + secret 扫描 | `trivy fs --scanners vuln,secret .`；镜像用 `trivy image --severity HIGH,CRITICAL <img>` |
| `osv-scanner` | OSV.dev 生态查询（Google 维护） | `osv-scanner scan -r . --format json` |
| `Gitleaks` | 提交历史 / 工作区密钥扫描 | `gitleaks detect --source . -v` |
| `Cosign` | 制品签名与验签（验发布完整性） | `cosign verify --key cosign.pub <image>` |
| `Snyk` | 商业 SCA + 可达性标记 | `snyk test --all-projects` |
| `CodeQL` | 数据流切片，用来判 CVE 可达性 | 建库后跑 dataflow 查询，命中才叫可达 |
| Dependency-Track | 持续监控 + 组件时间线 | 上传 SBOM → 看新 CVE 命中与组件维护者变更 |
| `hadolint` | Dockerfile 审计 | `hadolint Dockerfile` |
| `curl` | 拉 registry / advisory / GitHub API 元数据，核对发布者与 tarball 时间 | `curl -sSf https://registry.npmjs.org/<pkg>` |
| `kubectl` | 验准入控制是否真拦得住未签名/高危镜像 | `kubectl apply -f badimage.yaml`，看是否被 Kyverno/OPA 拒 |
| `yara` | 扫包内 payload（postinstall 释放的二进制/混淆脚本） | `yara rules.yar node_modules/` |
| `nuclei` | 扫暴露在公网的私有 registry / CI runner 面板 | `nuclei -u https://registry.internal -t exposures/` |
| `hashcat` | 验证窃得的 CI secret/hash 是不是真能用（别只看到就上报） | `hashcat -m 1400 ci_ntlm.txt` |

**工具定位走探测层，不走猜**：`. C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1` 之后
`Resolve-ReverseToolSpec -Name syft` / `-Name trivy`，按返回的 `Command` 调（完整路径，别赖 cwd）。
链上是 `pip`/`npm`/`go` 装的小工具时，先确认它在 PATH 快照之外还能被解析到 —— `Get-Command` 查空不代表没装。
MCP 相关通道登记在 `../references/tool-registry.md`（只记端点与启动方式，状态一律现查）。

## 参考

- `references/sbom-sca-methodology.md` — SBOM + SCA 方法论
- `references/cicd-pipeline-security.md` — CI/CD 管道安全审计

## 任务完成自检（声称完成前 MUST 通过）

- [ ] 我是否执行了工作流中的每一步（而不是只阅读）？
- [ ] 我是否走了**探测层四级递进**（`Resolve-ReverseToolSpec`）定位实际路径（而不是只跑一条 `Get-Command` 查空就报缺工具、也不是拿 `../TOOLS.md` 里的装法当路径猜）？
- [ ] 我是否产出了可复现证据（命令/脚本/截图/报告）？
- [ ] 我是否完成并回写了 RULES 要求的 Checklist 项？

## 改编参考索引（open-reverselab `kb/ctf-website`）

> 下列 reference 改编自 `LING71671/open-reverselab` 的 `kb/ctf-website/`（GPL-3.0）。
> 每篇统一为「适用信号 / 前置 / 步骤 / 判据 / 坑 / 相关」+ 完整技术正文，
> 「前置」含**本机实测**的工具状态表——照抄原库裸命令前先看那张表。
> **能力域**：本文为技术能力说明，按项目 `scope.md` 直接套用。

### `references/repos/` — 依赖混淆与供应链投毒（1 篇）

- `references/repos/dependency-confusion.md`

### `references/` — 根目录



---

## When NOT to use（近邻负例）

- 要审的是自家业务源码的逻辑漏洞（不是依赖与构建） → 用 `../code-audit/SKILL.md`
- 要打的是运行时集群/容器逃逸（已进到 pod 里） → 用 `../cloud-k8s/SKILL.md`
- 要逆向的是拿到的单个二进制样本本体 → 用 `../reverse-engineering/SKILL.md`
- 可疑包确认会执行后，要做族属/行为分析而不是继续查依赖 → 用 `../malware-analysis/SKILL.md`
- CI 被打了，要按攻击链复盘横向路径 → 用 `../attack-chain/SKILL.md`
- 目标是浏览器扩展的权限/更新面 → 用 `../browser-extension-reverse/SKILL.md`
- 依赖漏洞的落点其实在 Web 应用请求处理层 → 用 `../api-security/SKILL.md`

## When to Pivot

信号与判据见 `../ops/skill-pivot-contract.md`。本技能去向：

| 触发证据 | 换到 |
|---|---|
| 包里有 `postinstall`/`preinstall`，且 `npm i` 与 `npm i --ignore-scripts` 后行为不同（多出进程/文件/外连） | 执行体已确认：`../malware-analysis/SKILL.md` |
| 构建产物与源码不一致：`trivy` 读出的组件版本 ≠ lock 文件锁的版本，同一次构建内两处对不上 | 从二进制面重判：`../binary-diff/SKILL.md` |
| CI 日志/环境里露出可用的 `GITHUB_TOKEN`/`AWS_*`/OIDC 断言，且 3 分钟内能提升到更高权限 | 已进攻击面：`../attack-chain/SKILL.md` |
| SBOM 与实装对不上，换 `Syft` 与 `cdxgen` 两个生成器、连查 2 次仍对不上 | 落证据（两份 SBOM + 镜像 digest）后转 `../binary-diff/SKILL.md` 从镜像层/二进制核对 |
| `trivy fs` 报的 CVE 全落在未被引用的传递依赖里，调用链可达性为 0 | 不是漏洞，写进报告交 `../docs-generator/SKILL.md`，别硬造 PoC |
| 依赖树里出现 typosquat 同名包（如 `requsts`/`lodahs`）且其 install 脚本会外连 | 立刻 `../malware-analysis/SKILL.md`，并交 `../threat-intelligence/SKILL.md` 做家族归属 |
| 私有 registry 未鉴权可匿名 push，能覆盖内部团队正在用的包 | 这是投毒入口不是漏洞清单：交 `../attack-chain/SKILL.md` 评估影响面 |

## 定义完成

本技能产出算「完成」的**外部可观测**条件（不许写形容词）：

- SBOM 落盘（含版本与直接/传递依赖标记），并记下生成器与镜像 digest（对不上时可回溯）
- 每条 CVE 有可达性判定（不只列版本）：有源码/反编译调用链证据才算 `confirmed`，只有版本号匹配记 `low`
- CI 审计的每条发现对应到 workflow 文件的具体行（`文件:行` 形式）
- SBOM 与实装冲突时以二进制/镜像层内容为准，不以任一生成器的输出为准

## 输出契约

```
FACT:       <观察，带来源：命令 / 文件:行 / Evidence ID>
HYPOTHESIS: <可测试断言 + confidence: high|medium|low>（状态见 `../ops/binary-model.md`）
QUESTION:   <当前最大不确定点>
NEXT:       <继续 | 换技能 | 停止（附成本判据）>
```

## 置信度词表

词表见 `../ops/confidence-vocabulary.md`。本技能特有判据：

- `confirmed`：可达性结论有实际调用链证据（源码或反编译）
- `low`：仅按版本号匹配 CVE 未判可达性
