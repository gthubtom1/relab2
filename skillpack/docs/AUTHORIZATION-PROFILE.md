# Authorization profile (T15, spec 17.4)

状态：T15 交付文档。规范唯一真相源是
`docs/INTEGRATION-IMPLEMENTATION-SPEC.md` 17.4；本文件只写本卡的落地。

## 核心命题

**授权不能是一段可复制的文本。** `scope.md` 里的
`ready_for_act: true` 是一个英文单词，任何代理、任何注入载荷都能打出它。
本卡让 `ready_for_act` 依赖**可重新算出的事实**：

* `work/<case>/auth-profile.json` —— 谁批准、批准了什么（目标白名单、
  动作权限）、有效期、以什么形式证明，外加执行约束
  （filesystem/network egress、人工确认、timeout/retry/request/resource
  limit）。形状见 `schemas/auth-profile.json`。
* `work/<case>/attestation.json` —— 可离线复核的授权事实：
  case_id、target digest、profile、risk、expiry、nonce、issuer、
  binding。形状见 `schemas/case-attestation.json`。

门校验器：`skills/scripts/verify-auth-profile.py`
（只读验证；仅 `--issue-attestation` 在 case 目录内写一个文件）。
退出码按 4.7：`0` 放行、`20` 阻断、`2` 用法错误。

## 判定规则（缺任何一项即 BLOCKED，不填默认值）

1. scope 硬门（与 `case-guard.ps1` 同口径，不放宽）：
   `auth.status=granted`、`evidence_of_auth` 非占位符、
   `ready_for_act=true`、`in_scope.assets` 非空、
   `network_profile.mode` 已选。
2. 缺 `auth-profile.json` 即拒（缺 proof）。
3. `case_id` 三处（scope / auth-profile / attestation）必须一致；
   外来证明、复制来的 attestation 在此被拒。
4. `expires_at <= now` 即拒（过期授权）。
5. `target_allowlist` 为空即拒（空白名单）。
6. `--action` 不在 `allowed_actions` 即拒（超范围动作）；
   危险动作（`exploit_validate`、`payload_execute`、`credential_use`、
   `active_scan`、`data_exfil`）即使在列、无 `human_confirmations`
   记录也拒（未批准危险动作）。
7. `execution_profile` 缺字段即拒；`offline` 配了 egress 即拒；
   非 offline 的 egress 落在白名单外即拒；
   `max_runtime_s` / `max_requests` / `max_artifact_bytes` 非正整数即拒。
8. attestation 三处重算：`target_digest` 对白名单重算、
   `binding` 对七元组重算、`expires_at` / `issuer` / `profile` 对
   auth-profile 与 scope 交叉核对。任何一处对不上即拒——
   这就是"复制文本过不了门"的机制所在。

`--force` 为兼容参数，与 `case-guard -Force` 一致：
**永不绕过**以上任何硬门。

## 与既有脚本的关系（复用，不重复造）

| 既有脚本 | 关系 |
|---|---|
| `skills/scripts/case-init.ps1` | 复用：仍是 `scope.md` 唯一合法生产者；本卡未改它 |
| `skills/scripts/case-guard.ps1` | 复用：仍是 canonical scope 门；本卡在其**之上**叠加 17.4 检查，不替代、不放宽，`-Force` 语义一致 |
| `skills/scripts/verify-path-and-target.py` (T22) | 分工：T22 拥有逐请求路径/目标强制；本卡只查 egress"已声明且一致"，不重复实现 |
| `scripts/verify-release-approval.py` (T16) | 复用其信任模型：身份由审批流程保障，记录承载可复核断言，门负责重验 |

## 用法

```powershell
# 发证明（批准者在授权时执行一次）
& (Resolve-ReverseToolSpec -Name 'pyre').Command skills/scripts/verify-auth-profile.py --case-root work/<case> --issue-attestation --risk medium

# 每次 ACT 前重验
& (Resolve-ReverseToolSpec -Name 'pyre').Command skills/scripts/verify-auth-profile.py --case-root work/<case> --action recon
```

## 负向 fixture

`tests/auth/t15-f*.json` + 驱动 `tests/auth/test-auth-profile.py`
（lab 在仓库外的 `D:/Project/skills-hub/work/T15-lab`，
主机名掩码断开存放）。六类各一：过期、空白名单、超范围动作、
未批准危险动作、缺 proof、纯文本 ready（另加 `--force` 不绕过、
双正向对照）。
