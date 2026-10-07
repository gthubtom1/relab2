# 社区来源与许可证矩阵

机器可读事实源是 `skills/community/registry.json`；本文只解释口径与未决项。
数字口径见文末「复算」一节，可用 `scripts/validate-integration.py` 与
`scripts/verify-release-gate.py` 独立复算。

## 来源矩阵

| 来源 | 基线提交 | license_declared | license_status | 适配条数 | 融合策略 | 分发结论 |
|---|---|---|---|---:|---|---|
| `zhaoxuya520/reverse-skill` | `cab634bd855fc287f6e420c1f36fd1a6b9245960` | MIT（含 GPLv3 sidecar 声明） | 主框架，不在 `sources[]` | — | 保留上游 LICENSE 与第三方说明 | 随本仓库 LICENSE 分发 |
| `asdfgh1445/ctf-super-hub` | `16926d6d4216183995693e9c7936c042eb7f2fae` | `NOASSERTION` | `review-required` | 35 | CTF hub + namespaced skills | **仅 local-only**（17.29(6)） |
| `yaklang/hack-skills` | `6fbf0bc8d5c71830d62543a308d8744606c43d7c` | `MIT` | `review-required` | 103 | Web/API/主机安全 hub | **仅 local-only**（17.29(4) notice 未携带 commit/url） |
| `zhaoxuya520/AI-Fullstack-Delivery-Workflow` | `ab96b897d719941219ab3b3badb47cd6fda3e0eb` | `NONE` | `missing-license` | 154 | 交付 workflow 适配层 | **仅 local-only**；公开分发前必须补授权或移除 |
| `newliver666/apk-reverse` | `7b6c6932a95f03d778e81e5e1a2cbf6f62dc97fd` | `MIT` | `verified` | 1 | APK capability extension | 许可证一项已清；仍受 17.28 attestation 阻断 |

## 许可证状态计数（skill 口径）

| license_status | 条数 | 是否阻断再分发 |
|---|---:|---|
| `missing-license` | 154 | 是 |
| `review-required` | 138 | 是 |
| `verified` | 1 | 否（但 17.28 attestation 仍阻断） |
| 合计 | 293 | — |

`maturity` 分布：`unverified` 154、`partial` 139、`verified` 0。

`verify-release-gate.py` 的 skill 级阻断计数（R15）为 `missing-license` 154 +
`review-required` 138 + `unverified` 154 = **446**，与
`validate-integration.py --release` 的 `skill_scoped=446` 一致。

## CR-004：为什么 292 不是回归

WORK-BOARD 的 CR-004 记录：T02 把 hack-skills 的历史描述
`MIT-with-third-party-provenance-review` 改成 4.1 合法枚举值 `review-required`。
该字符串既不在 4.1 枚举内、也不在旧校验器的阻断集合内，所以旧校验器对它**静默
放行**。改成 `review-required` 之后，103 条 hack-skills skill 首次被纳入许可证
审查计数，warning 由 189 升到 292。

- 189 → 292 是**收紧**（更多内容进入审查范围），不是漏检回归。
- 292 是 **skill 口径**（`skills[]` 中 `license_status ∈ {missing-license,
  review-required}` 的条数）；298 是 source(6) + skill(292) 的合计。两个数都对，
  但引用时必须写清口径。
- 校验器把两类发现分开打印（`source_scoped=` / `skill_scoped=`），复算 292 时
  不要从 298 里减。

## 17.29 再分发判定

`license_status` 本身不足以支持再分发，判定还需同时满足：

1. **组合兼容性**：并入许可证并集 `["MIT", "NOASSERTION", "NONE"]`，目标分发许可
   `MIT`，结论 **undetermined**（`NOASSERTION`/`NONE` 无可判定结论）。
2. **传递依赖**：4 个 snapshot 内非 registry skill 记录的 collateral 文件共 794
   （ai-fullstack 489 / apk-reverse-source 113 / ctf-super-hub 129 / hack-skills 63），
   独立许可证记录为 0。当前 snapshot 内**未发现**二进制、字体、归档、数据集文件，
   聚合 digest 见 `verify-release-gate.py` 的 `transitive_inventory`。
3. **NOTICE 一致性**：根 `NOTICE` 已建并逐条列出 4 个 source；各 source notice
   仍缺 `source_url` 与锁定提交（`verify-release-gate.py` R10，6 条）。
4. **17.28 attestation**：4/4 source 的 `tree_digest` / `source_manifest` 均为
   `null`，锁定提交不等于内容证明。
5. **已知 CVE 扫描记录**：不存在（R17）。

结论：本仓库当前是 **local-only integration candidate**，不是可公开分发的发布物。

## 使用规则

- `community-raw/` 是来源快照，不等于已获得新的再分发许可。
- `registry.json` 中的 `license_status` 是机器可读门；`missing-license`、
  `review-required`、`mixed` 与 `unverified` 均不得进入发布候选。
- 适配过程中只增加统一合同、索引和路径修复，不删除上游版权和第三方通知。
- 未知来源不改标：`NOASSERTION` 必须保留原样，不能替换成 `MIT` 让门变绿。
- 门失败时门是对的。需要改判定，先用测量证明门错了，再改门（WORK-BOARD 规则）。

## 复算

```powershell
$env:PYTHONIOENCODING='utf-8'
python scripts\validate-integration.py                 # exit 0, skill_scoped=292
python scripts\validate-integration.py --release       # exit 20, skill_scoped=446
python scripts\verify-release-gate.py                  # exit 0, findings=472
python scripts\verify-release-gate.py --release        # exit 20
python scripts\verify-release-gate.py --json           # 完整报告
```
