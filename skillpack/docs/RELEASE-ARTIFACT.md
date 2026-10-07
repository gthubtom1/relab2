# Release artifact / SBOM / 审批（T16，规范 17.15 / 17.21 / 17.29）

Owner：T16。写入范围：`scripts/build-release-candidate.py`、
`scripts/verify-release-approval.py`、`schemas/release-candidate.json`、
`schemas/release-approval.json`、`.github/workflows/release.yml`、本文档。
未触碰：`scripts/verify-release-gate.py`、`scripts/validate-integration.py`
（只复用，不放宽）、`skills/community/**`、`community-raw/**`、
`skills/config/*.json`、`.github/workflows/ci.yml`、NOTICE（归 T04）。

当前结论（2026-10-01 实测）：本仓库是 **local-only integration candidate**，
只能出 local-only 候选，不能进入 redistributable 发布。两道既有发布门
（`validate-integration.py --release`、`verify-release-gate.py --release`）
均为 exit 20，这是预期结果，不是待修的门。

## 1. 候选构成

`scripts/build-release-candidate.py build --out-dir <仓库外目录>` 产出：

```
<out>/candidate-manifest.json   成员清单 + sha256 + 登记表/锁摘要 + 门 pin + 回滚目标
<out>/sbom.json                 组件清单（见 §2）
<out>/checksums.sha256          上面两个文件的逐行 sha256
```

`--out-dir` 落在仓库树内会被拒（exit 20），真仓库保持只读；
lab 夹具才允许 `--allow-in-tree`。`--distribution` 只有 `local-only` 可发射，
任何别的值直接 exit 20（见 §5 第一条）。

manifest 关键字段（完整定义见 `schemas/release-candidate.json`）：

- `registry_digest` / `registry_counts`（sources / skills / excluded，全部从登记表推导，无硬编码）；
- `members`：`skills/community/registry.json`、`skills/community/source-lock.json`、
  `NOTICE`、`LICENSE`、`VERSION` 各自的 sha256；
- `gate_pins`：五道门脚本的 sha256（含本脚本与审批脚本自身）；
- `rollback_target`：`{type: git-commit, commit: HEAD, prior_version: VERSION 内容}`；
- `content_id`：与墙钟无关的候选标识（见 §3），审批绑定的是它，不是文件哈希。

## 2. SBOM 形态

`sbom.json` 是最小化 CycloneDX 1.5 形状（`bomFormat` / `specVersion` /
`metadata` / `components` / `vulnerabilities`），纯标准库生成，不联网、
不装包。`components` = 5 条 source + 293 条 skill，许可证字段**只复述登记表
自己的声明**，登记表写不出 SPDX 值的一律 `NOASSERTION`。这份 SBOM 永远洗不白
一棵 local-only 树：它的作用是让 downstream 看清现状，不是放行依据。

`vulnerabilities` 为空数组，且附带 `vulnerabilities_note`：空 = **未扫描**，
不是"无 CVE"。CVE 扫描需要联网，本环境禁止联网，见 §5。

## 3. 审批流程

1. 请求人本地（或 CI 干跑）构建候选，得到 `content_id`（同一棵树重复构建
   结果一致，`created_at` 与解释器版本不参与计算）。
2. 请求人把 `content_id` 交给第二人审查；第二人确认后离线签发审批记录
   （格式见 `schemas/release-approval.json`）：`decision=approved`、
   `requester ≠ approver`、`content_id`、`gate_pins`、`rollback_target`、
   `approved_at`（UTC RFC 3339）。**审批记录不提交进仓库**，随发布过程
   （tag / environment）保管，`release.yml` 以输入传入，缺省即拒。
3. 发布时 `scripts/verify-release-approval.py --candidate-dir <out>
   --approval <记录>` 逐项重算，全绿（exit 0）才允许继续；任一项失败
   exit 20，无降级通过。
4. 平台侧（离线不可验证，如实声明）：`.github/workflows/release.yml` 是
   `workflow_dispatch` 手动触发 + `environment: release-approval`，job 在
   无批准时根本不启动；分支保护 / required checks / CODEOWNERS 见
   `.github/CODEOWNERS` 与 `docs/CI-TRUST-BOUNDARY.md`（owner T24，本卡只引用）。

`content_id` 绑定保证：批准后树上任何成员被改一位，重算即不匹配，exit 20；
批准后任何门脚本被改，`gate_pins` 即漂移，exit 20（实测见 §6）。

## 4. 回滚目标

`rollback_target.commit` 即构建时的仓库 HEAD。审批门用 `git cat-file -e`
验证其可解析（有 `.git` 时）；无 `.git` 的复制体 exit 10 并具名（沿用
`SOURCE-BUNDLE.md` §5 的降级语义，不静默放过）。回滚 = 回到该 commit
（含登记表、NOTICE、schema 一起回去，不单拎文件）。

## 5. 有意未实现清单（DEVIATIONS，本卡最重要的产出之一）

| # | T16 要求 | 现状 | 为什么现在做不了 |
|---|---|---|---|
| D1 | 可验证签名（signer / trust root / key id / 时间 / 轮换 / 撤销） | 未实现。T21 已如实登记 `signature.present=false` | 密钥管理与信任根需要线下仪式与分发渠道，本环境只有离线仓库；伪造签名记录等于伪造信任，直接违反 17.15 |
| D2 | redistributable 发布 | 被拒。构建脚本拒发、审批门拒批（均为 exit 20） | D1 未实现 ⇒ 17.15 禁止任何 redistributable；且 17.29 阻断（R13/R14/R15/R16/R17/R19）一个都没清零 |
| D3 | 已知 CVE 扫描（工具 + 库版本记入 manifest） | 未实现，无扫描记录，不伪造 | 扫描需要联网更新漏洞库，本环境禁止联网；R17 保持 open，SBOM 空数组已标注"未扫描" |
| D4 | 传递依赖逐文件许可证记录（R19） | 未实现，只产出附带摘要的清单 | 登记表 schema（owner T02）没有逐文件许可证字段，本卡不能代写登记表；`verify-release-gate.py` 已如实报 R19 |
| D5 | 上游快照跨机器可复核 | 降级：复制体无 `../upstream` 时只能核格式与记录值 | 快照在仓库外（只读），见 `docs/community/SOURCE-BUNDLE.md` §5；候选 manifest 如实记录，不假装自包含 |
| D6 | 组合许可证兼容结论（R13） | `undetermined`（并集含 `NOASSERTION` / `NONE`） | 154 条 `missing-license` 等未清零（owner T02/T04），本卡无权改标；改标即伪装 redistributable |
| D7 | 真实 runner 上的 release 流程 | 未验证，只做静态合规（只读权限、无 secret、全 SHA pin） | CI runner 不在本环境执行；文档明确写"未验证"，不列为已验证能力（17.30 同款诚实） |

## 6. 负向对照（lab 实测，真非零退出）

| 对照 | 命令要点 | exit |
|---|---|---|
| 未批准就发布 | 审批门不传 `--approval` | 20 |
| 无签名却宣称 redistributable | 构建 `--distribution redistributable`；或审批记录写 redistributable | 20 |
| 候选清单被篡改一位 | `sbom.json` 第 200 字节翻一位后 `check` | 20（恢复后回 0） |
| PR 自改 gate 后沿用旧批准 | lab 内给 `verify-release-gate.py` 追加一行注释后重验 | 20（`git checkout` 恢复） |
| 自批准（requester == approver） | 审批记录两字段填同一人 | 20 |
| 未知参数 | 任一新脚本传 `--bogus-flag` | 2 |

## 7. 验证（真仓库只读）

```powershell
$env:PYTHONIOENCODING='utf-8'
D:\EXE\python\python.exe scripts\build-release-candidate.py build --out-dir <仓库外> --requester <人>
D:\EXE\python\python.exe scripts\verify-release-approval.py --candidate-dir <上> --approval <记录>
D:\EXE\python\python.exe scripts\verify-release-gate.py            # exit 0
D:\EXE\python\python.exe scripts\verify-release-gate.py --release  # exit 20（预期）
D:\EXE\python\python.exe scripts\validate-integration.py           # exit 0
```

`--release` / `--distribution redistributable` / 无批准三条 exit 20 是设计态：
门是对的，不要改门去追绿。
