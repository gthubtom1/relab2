---
name: code-audit
description: 白盒源码审计：PR/差分审查、Semgrep/CodeQL/Bandit/gosec SAST、注入点、鉴权缺失。用于：审代码注入、PR 合前过安全、IDOR/多租户。
---

# Source Code Security Audit

## ACTION REQUIRED（读完后立刻执行）

1. `NOW`: 读取 `../field-journal/precedent-pentest.md` 或代码审计授权
2. `NOW`: **查经验卡** —— `python skills/scripts/experience-card.py search "<你看到的症状>"`。
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

## 工具链

| 工具 | 语言/场景 |
|------|-----------|
| Semgrep | 多语言快速规则 |
| CodeQL | 深数据流（GitHub） |
| Bandit | Python |
| gosec / staticcheck | Go |
| SpotBugs / FindSecBugs | Java |

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
- [ ] 是否限定在授权仓库范围？
- [ ] Checklist？

---

## When NOT to use（近邻负例）

- 手里只有二进制/APK，没有源码 → 用 `../reverse-engineering/SKILL.md`
- 要看的是运行时行为（网络/文件/内存），源码看不到 → 用 `../malware-analysis/SKILL.md`
- 要审的是依赖与构建链，不是自家源码 → 用 `../supply-chain-security/SKILL.md`
- 前置条件：先建 `scope.md` 记下审的是哪个版本/哪个 commit，否则结论无法复现

## When to Pivot

信号与判据见 `../ops/skill-pivot-contract.md`。本技能去向：

| 触发证据 | 换到 |
|---|---|
| SAST 报出 taint 路径，需要在运行时确认可达 | `../pentest-tools/SKILL.md` |
| 发现硬编码密钥/证书，要验证可否利用 | `../attack-chain/SKILL.md` |
| 发现 CI 配置里注入点 | `../supply-chain-security/SKILL.md` |

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
