# 专家角色 → Skill 映射（无多 Agent 服务器）

> 角色代号灵感来自 Z3r0 专家队；**实现方式**是 reverse-skill 路由与交接协议，不是进程编排。

## 角色表

| Code | 名称（可本地化） | 职责 | PRIMARY / 工具 skill |
|------|------------------|------|----------------------|
| **lead** | Lead / 总指挥 | 拆任务、定 scope、阶段门控、汇总报告 | `attack-chain/` 或当前 PRIMARY hub；结束 → `docs-generator/` |
| **cie** | 情报收集 | 资产发现、暴露面、关系 | `pentest-tools/`（recon）；浏览器 → `browser-automation/`；云面 → `cloud-k8s/` |
| **cpe** | 渗透验证 | 扫描、利用验证、影响确认 | `pentest-tools/`；API → `api-security/`；AD → `windows-ad/`；无线 → `wifi-wireless/`；库 → `database-security/`；SSO → `identity-federation/`；OT → `ot-ics/` |
| **cre** | 逆向分析 | 二进制/固件/移动/前端逻辑 | `ida-reverse/` `ghidra-reverse/` `binary-ninja-reverse/` `radare2/` `apk-reverse/` `mobile-reverse/` `macos-reverse/` `js-reverse/` `browser-extension-reverse/` `dotnet-reverse/` `go-rust-reverse/` `firmware-pentest/` `hardware-security/` `malware-analysis/` `protocol-reverse/` `thick-client/` `reverse-engineering/` |
| **cae** | 代码审计 | 源码/依赖/供应链 | `code-audit/` + `supply-chain-security/` |
| **cbe** | 蓝队/取证 | 狩猎、检测、IR 伪影 | `threat-hunting/` `digital-forensics/` |
| **cce** | 密码学 | 算法/协议/密钥误用 | `reverse-engineering` 模式文档 |
| **llm** | AI 安全 | Prompt/Agent | `llm-security/` |
| **doc** | 文档官 | 报告/writeup/图 | `docs-generator/` + `diagram-generator/` |
| **impl** | 实现 | 调查→编码/修改的唯一入口（复刻交付路径） | 当前 PRIMARY + `rebuild.md` 对账表（`ops/rebuild-gates.md` 闸门①） |
| **ver** | 验收 | 跑差异测试与完成度审计；唯一有权把功能状态改成「已通过约定测试」的角色 | `case-review/scripts/review_case.py` + `scripts/diff-runner.py` + `ops/rebuild-gates.md` 闸门② |

## Lead 强制协议

```text
1. 输出 PRIMARY（master-route）+ lead_role=lead
2. 写 scope.md（ops/scope-contract）
3. 指定 specialist_roles[] 与 handoff 条件
4. 每阶段结束：更新 timeline + workitems；决定继续/换角色/出报告
5. 禁止跳过 scope 直接 cpe 扫生产
6. 复刻 case（scope deliverables 含 rebuild: true）必须显式指定 impl 或 ver 角色
```

## impl / ver 进入与退出条件（复刻交付路径）

可判定的事实陈述，与 `ops/rebuild-gates.md` 两道闸门一一对应：

| 角色 | 进入条件（全部为事实） | 退出条件 | 判定者 |
|------|------------------------|----------|--------|
| **impl** | ① `rebuild.md` 的 functions 表目标行非空（入口/预期输出/验收条件三列已填）；② 这些行在 acceptance 表状态为「已分析」且证据列非空（E-xxx / notes / diff 记录路径）；③ 关键假设按 ADF-R4* 达到 validated 门槛（≥2 条独立证据） | 目标行的实现落到运行路径（状态升到「已实现」），或转 `ver` 做验收 | lead 按闸门①核对 |
| **ver** | 收到「已实现」的行 + `diff/` 存在对照运行记录；或需做完成度审计（rebuild.md 有任一「已测试」以上状态的行） | 该行状态定为「对照一致」或「受限 + 具体原因」；产出交回 lead | ver 是唯一有权改「已通过约定测试」状态的角色 |

## 交接（Handoff）规则

| 从 → 到 | 触发 | 交付物 |
|---------|------|--------|
| lead → cie | 需要资产面 | scope + 已知域名/IP |
| cie → cpe | 有存活面/服务 | assets 列表 + 端口/URL |
| cpe → cre | 需逆向校验/客户端逻辑 | 样本路径 + 可疑点 |
| cre → cpe | 还原出协议/密钥/校验 | 算法说明 + 复现命令 |
| any → doc | 阶段或任务完成 | Evidence/Finding/Path 草稿 |
| any → lead | 阻塞/越权/换路径 | timeline 备注 + blocked 原因 |
| cre → impl | 调查足够：目标行已分析且证据回填（闸门①成立） | `rebuild.md` 已分析行 + 证据引用 |
| impl → ver | 实现完成待验收：目标行进运行路径（状态「已实现」） | 变更落点 + `diff/` 对照草稿 |
| ver → lead | 通过或明确未达标 | 行状态（对照一致 / 受限+原因）+ 审计输出 |

## 单人 Agent 怎么用（特色）

不必真起 6 个 Agent：

```text
同一会话内：
  [lead] 规划
  [cie] 执行侦察 skill
  [cpe] 切换 pentest-tools
  …
输出时用角色前缀标签，方便 timeline 检索：
  [cpe] nuclei high findings → E-003
```

## 与 master-route 关系

- `master-route` 定 **PRIMARY skill**  
- `role-map` 定 **谁在当前阶段负责**（可写在 scope.md）  
- 多阶段任务 PRIMARY 常为 `attack-chain/`，由 lead 再分发  

## MUST NOT

- 不要假设存在 Z3r0 会话 API  
- 不要为角色启动超出 `scope.md` 范围的额外扫描  
