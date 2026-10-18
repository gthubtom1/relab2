---
name: code-audit
description: 白盒源码审计：PR/差分审查、Semgrep/CodeQL/Bandit/gosec SAST、注入点、鉴权缺失。用于：审代码注入、PR 合前过安全、IDOR/多租户。
---

# Source Code Security Audit

## ACTION REQUIRED（读完后立刻执行）

1. `NOW`: 读 `../field-journal/precedent-pentest.md` —— 本机做过多轮的常规操作清单，直接照做，不要停在犹豫上
2. `NOW`: **查经验卡** —— `python skillpack/skills/scripts/experience-card.py search "<你看到的症状>"`。
   命中就读那张卡的 `invariant` + `decision.action`，并**逐条对照** `scope.appliesWhen`
   与 `scope.stopsWhen`：少一条前提就停用；命中任一停止条件就停。
   历史卡**不替代**当前目标的实测证据。详见 `../experience-cards/INDEX.md`。
3. `NOW`: 确认有**源码/仓库访问**（无源码二进制 → 转 RE skill）
4. `NOW`: 明确语言栈与范围（目录/服务/PR diff）
5. `NEXT`: `../TOOLS.md`；semgrep 等
6. `ACT`: 威胁建模草图 → 自动扫描 → 人工验证

## 适用场景

- 白盒审计、PR/差分安全审查
- Semgrep / CodeQL / Bandit / gosec 等 SAST
- 危险 API、注入点、鉴权缺失、加密误用
- 与 `supply-chain-security/` 分工：本 skill 偏**自有代码逻辑**，供应链偏依赖与管道

## 工作流

### 1. 范围与威胁模型

```text
□ 信任边界：用户输入、文件、反序列化、SSRF、鉴权中间件
□ 高价值资产：鉴权、支付、管理端、密钥处理
```

### 2. 自动扫描

```bash
semgrep --config auto .
# 或项目规则包
semgrep --config p/owasp-top-ten .
```

### 3. 人工验证（MUST）

```text
□ 每个 SAST 命中：可达性？可利用性？误报？
□ 鉴权：IDOR/越权、缺校验、错误的多租户隔离
□ 注入：SQL/命令/模板/LDAP
□ 加密：硬编码密钥、ECB、自定义 crypto
```

### 4. 产出

```text
Finding：位置 + 数据流 + PoC + 修复建议
可选 ATT&CK / CWE 编号
```

## 工具链与工具联动

| 工具 | 语言 / 场景 | 本机怎么调 · 输出接到哪 |
|------|-----------|----------------------|
| Semgrep | 多语言快速规则 | `semgrep --config auto .` 只是候选集；每条命中进人工可达性跟踪（见下方判据），误报要写明停在哪一段 |
| CodeQL | 深数据流（需建库） | 建库耗时高，只在 Semgrep 口径不够、需要跨函数污点链时上；结论同样要过人工跟踪 |
| Bandit | Python | `bandit -r <pkg>`，命中先看是否走的是 `eval/subprocess` 可控参数 |
| gosec / staticcheck | Go | 重点看 `exec.Command`、`text/template` 与 `database/sql` 拼接 |
| SpotBugs / FindSecBugs | Java | 反序列化与 XXE 命中优先级最高，先看 `ObjectInputStream` 上游 |
| 路径探测 | 全工具 | `. <仓根>\skillpack\skills\scripts\lib\Bootstrap.ps1` → `Resolve-ReverseToolSpec -Name <id>`；semgrep/codeql 不在本机 toolmap 里，走四级探测，全 `Available=False` 才按 `../TOOLS.md` 自装，禁止猜路径。`Get-Command` 查空 ≠ 缺工具 |
| 运行时确认 | 定位到 sink 后 | `sqlmap -u "url?id=1" --batch` 或 `curl` 手搓 payload 验证可达性；也可让 `nuclei` 的模板面兜一遍已知 CVE。活环境用 `../pentest-tools/SKILL.md` |
| 报文面复现 | Web 缺陷 | `Burp`（`../pentest-tools/references/burpsuite-mcp-guide.md`）改包重放；硬编码密钥用 `curl` 打真实端点，200/提权成立才算 confirmed |
| 二进制依赖 | 依赖里带 `.so`/`.dll`/WASM | `rabin2 -i` 先看导入表与版本字符串，再 `analyzeHeadless`（Ghidra 无头）反编译比对；同源缺陷按版本差定位转 `../binary-diff/SKILL.md` |
| 依赖与管道 | SBOM / 构建链 | `Syft` 出 SBOM → `trivy` 扫漏洞；这条线归 `../supply-chain-security/SKILL.md`，本卡只做边界交接 |
| 样本特征 | 仓库/产物落盘后 | `yara` 扫产出的二进制或可疑样本，特征命中才算「确有同族载荷」 |
| 原生崩溃 | 内存类缺陷确认 | `gdb`（Linux）/ `cdb`（Windows）看崩溃点与可控寄存器，判定是否真能控制执行流 |

## 参考

- `references/sast-review-checklist.md`
- `../supply-chain-security/` `../api-security/` `../llm-security/`（Agent 代码）

## 路由上下文

**上游**: MASTER R26  
**角色**: `../ops/role-map.md` cae  
**下游**: 依赖漏洞 → supply-chain；运行时验证 → pentest-tools

## 任务完成自检

- [ ] 是否人工验证而非只贴扫描器输出？
- [ ] 是否含修复建议？
- [ ] 结论是否绑定到具体仓库与 commit/版本？
- [ ] Checklist？

---

## 本技能硬判据

- **污点三段判据**：一条注入 Finding 成立要同时有 ① source 可控的证据（HTTP 入参 / 文件 / 环境变量的具体落点）② 净化缺失或可绕（要写清 sanitizer 函数名与绕过方式）③ sink 的真实执行路径（不是死代码、不被 feature flag 关掉）。缺任一段就降为 suspected，不许写成 confirmed。
- **误报判据（两轮即停）**：同一 sink 人工跟踪**两轮**都停在「参数不可控」或「sink 不可达」，就标 false-positive 并写明停在哪一段，不要为凑数把它留在 Findings 里。
- **修复判据**：修复点要落在公共封装层，否则同一 CWE 会在 **≥3 处**复发；验收方式是原 PoC 复跑不再成立，且既有测试仍绿。
- **可达性优先于数量**：一个已证实可达的 sink 比二十条 grep 命中值钱；报告里按「已证实 / 未证实 / 已排除」三档分列。

## When NOT to use（近邻负例）

- 手里只有二进制/APK，没有源码 → `../reverse-engineering/SKILL.md`
- 要看的是运行时行为（网络/文件/内存），源码里看不到 → `../malware-analysis/SKILL.md`
- 要审的是依赖、SBOM、构建链与发布管道，不是自家代码逻辑 → `../supply-chain-security/SKILL.md`
- 只有两个版本的二进制、没有改前源码，要从补丁差推缺陷 → `../binary-diff/SKILL.md`
- 目标面是 LLM/Agent 的提示注入、工具白名单与 RAG 投毒 → `../llm-security/SKILL.md`
- 已定位 sink，要在活环境确认可达与可利用 → `../pentest-tools/SKILL.md`
- 逻辑实际在前端 JS（签名、加解密、越权判断）而不在服务端源码 → `../js-reverse/SKILL.md`
- 审的是移动端反编译产物（smali / IPA）→ `../mobile-reverse/SKILL.md`

## When to Pivot

信号与判据见 `../ops/skill-pivot-contract.md`。本技能去向：

| 触发证据 | 换到 |
|---|---|
| SAST 报出 taint 路径，人工跟踪**两轮**仍证不出可达（source 不可控或 sink 不可达） | 停静态，转运行时：`../pentest-tools/SKILL.md` |
| 发现硬编码密钥/证书，且用 `curl` 带该凭据打真实端点**返回** 200 或权限提升 | `../attack-chain/SKILL.md`（把密钥变成立足点，再评估横向） |
| 注入点落在 CI 配置/构建脚本（`.github/workflows`、`Makefile`、`Dockerfile`） | `../supply-chain-security/SKILL.md` |
| 二进制依赖里**发现**同源缺陷（同一 CVE 家族），源码侧没有对应代码 | `../binary-diff/SKILL.md`（按版本差定位） |
| 同一 CWE 在 **≥3 处**重复（同一个不安全封装被到处调用） | 抽公共修复点，并把模式写成自定义 Semgrep 规则；口径见 `references/sast-review-checklist.md` |
| 跟踪数据流时**发现**入口指向第三方组件而非自有代码 | `../supply-chain-security/SKILL.md` |
| 源码里带出二进制（`.so`/`.dll`/WASM），缺陷在其内部 | `../reverse-engineering/SKILL.md` 或 `../binary-diff/SKILL.md` |
| 审到 Agent/LLM 调用链（prompt 拼接、工具白名单缺失） | `../llm-security/SKILL.md` |
| 差分只有二进制、拿不到改前源码 | `../binary-diff/SKILL.md` |

## 定义完成

本技能产出算「完成」的**外部可观测**条件（不许写形容词）：

- Findings 表每行有 `location`（file:line）与 `evidence_ids`
- 每条 Finding 有最小复现（单测/脚本/请求）
- 修好后的验证：原 PoC 不再成立，且既有测试仍绿

## 输出契约

```
FACT:       <观察，带来源：命令 / 文件:行 / Evidence ID>
HYPOTHESIS: <可测试断言 + confidence: high|medium|low>（状态见 `../ops/binary-model.md`）
QUESTION:   <当前最大不确定点>
NEXT:       <继续 | 换技能 | 停止（附成本判据）>
```

## 置信度词表

词表见 `../ops/confidence-vocabulary.md`。本技能特有判据：

- `confirmed`：污点路径从 source 到 sink 完整走通，且有可执行 PoC
- `low`：仅 grep 到危险 API 调用，未确认参数可控/可达
