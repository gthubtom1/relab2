# ops — reverse-skill 作战契约层

Z3r0 启发、**本包形态**实现：

| 文件 | 用途 |
|------|------|
| [IDENTITY.md](IDENTITY.md) | 我们是谁 / 不做平台 |
| [scope-contract.md](scope-contract.md) | 启动 scope + network_profile |
| [evidence-finding-path.md](evidence-finding-path.md) | 证据链 |
| [role-map.md](role-map.md) | 角色→skill + 交接 |
| [timeline-workitem.md](timeline-workitem.md) | 时间线与覆盖 |
| [sandbox-profile.md](sandbox-profile.md) | 工具对照 |
| [skill-supply-chain.md](skill-supply-chain.md) | Agent Skill/MCP 供应链安全（AST10 精简） |
| [kb-consult-contract.md](kb-consult-contract.md) | **什么时候回读知识库**（八类触发信号；它不是“开局读一次”，是反复回读） |
| [case-review/](../case-review/) | Evidence 图完整性审查与报告交接 |

相关 references（非孤儿，从本 hub / MASTER / SKILL 可达）：

- `../references/community-security-skills.md` — 社区 skill 生态对照  
- `../references/domain-coverage-map.md` — 本包领域覆盖  
- `../attack-chain/references/lifecycle-checklist.md` — 攻击链阶段门闩  
- `../reverse-engineering/references/re-agent-workflow.md` — RE 四阶段  
- `../pentest-tools/references/recon-pipeline.md` — 授权侦察 + Evidence 门  

- 脚本：`../scripts/case-init.ps1`
- 校验：`../scripts/verify-routing-coherence.ps1`（含 ops 契约检查）
- 审查：`../case-review/scripts/review_case.py`（只读 Evidence 图检查）

## 机器契约（JSON Schema，`../../schemas/`）

ops 里的契约是给人和模型读的；**给脚本 / CI 读的冻结契约**在 `../../schemas/`。
索引、支持的校验关键字子集与解释决定见 [`../../schemas/README.md`](../../schemas/README.md)；
每条契约的**真实调用方**（谁 load、谁校验）见下表 —— 不存在「只有 schema、没有读者」的契约。

| 契约 | 管什么 | 谁读 / 谁校验 |
|------|--------|---------------|
| [`../../schemas/auth-profile.json`](../../schemas/auth-profile.json) | 单 case 授权事实（`work/<case>/auth-profile.json` 的形态：批准人 / 目标 / 动作 / 时限 / 证明） | `../scripts/verify-auth-profile.py`（照规则逐条判，缺字段 / 过期 / 占位证明一律 exit 20，**从不填默认值**） |
| [`../../schemas/case-attestation.json`](../../schemas/case-attestation.json) | 可离线复核的授权凭证（`work/<case>/attestation.json`） | `../scripts/verify-auth-profile.py`（重算 digest 链，复制来的 `ready_for_act` 不认；`--issue-attestation` 产出） |
| [`../../schemas/canonical-base-lock.json`](../../schemas/canonical-base-lock.json) | canonical base（`reverse-skill` 母框架）source 记录的 T21 扩展字段 | `../../scripts/verify-canonical-base-lock.py`（`--require-signatures` 真树 exit 20 = 无签名不得进 redistributable） |
| [`../../schemas/community-handoff-input.json`](../../schemas/community-handoff-input.json) | HandoffInput（wrapper 入参） | `../scripts/test-contract-v2.py`（`load_schema`）、`../scripts/community-route.py`、`../community/registry.json` 各 wrapper 的 `input_schema` |
| [`../../schemas/community-handoff-output.json`](../../schemas/community-handoff-output.json) | HandoffOutput（wrapper 出参） | `../scripts/test-contract-v2.py`（`load_schema`）、`../scripts/community-route.py`、`../community/registry.json` 各 wrapper 的 `output_schema` |
| [`../../schemas/carrier-manifest.json`](../../schemas/carrier-manifest.json) | carrier manifest（4.0 表，T23；producer 仍缺） | `../scripts/test-contract-v2.py`（`load_schema`） |
| [`../../schemas/community-routing-signals.json`](../../schemas/community-routing-signals.json) | 社区路由信号表（T26） | `../scripts/verify-routing-signals.py`、`../scripts/test-routing-signals.py` |
| [`../../schemas/release-candidate.json`](../../schemas/release-candidate.json) | 发布候选（候选目录自己声明的 schema） | `../../scripts/build-release-candidate.py`（写 `"schema": "schemas/release-candidate.json"`）、`../../scripts/verify-release-approval.py` |
| [`../../schemas/release-approval.json`](../../schemas/release-approval.json) | 人工放行记录（`release-approvals/`） | `../../scripts/verify-release-approval.py`、仓根 `.github/workflows/release.yml`（`environment: release-approval` 闸门；注意**不在** `skillpack/.github/`） |

> `auth-profile.json` / `case-attestation.json` 在 schema 层是**形态声明**：没有脚本去 load 这两个 schema 文件，
> 规则由 `verify-auth-profile.py` 直接实现 —— 所以「schema 里写了、门禁没实现」这种漂移不可能发生。
