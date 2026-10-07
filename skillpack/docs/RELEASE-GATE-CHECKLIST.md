# Release Gate Checklist — 许可证 / 来源 / 再分发

> 配套文档：`docs/RELEASE-CHECKLIST.md`（版本号、CHANGELOG、tag 流程）与
> `docs/COMMUNITY-LICENSE-MATRIX.md`（许可证口径与计数）。
> 本文只覆盖**许可证、来源证明、再分发资格**。事实源是
> `skills/community/registry.json`；判定由两个脚本执行，不由本文替代。

## 0. 当前状态（2026-10-01 实测）

本仓库当前是 **local-only integration candidate**。两个 release 门都以退出码
20 阻断，这是**预期结果**，不是待修的门。

| 门 | 命令 | 当前 exit | 当前结论 |
|---|---|---:|---|
| 适配边界 | `python scripts\validate-integration.py` | 0 | 通过，292 条 skill 口径许可证审查 warning（非阻断） |
| 适配边界（发布） | `python scripts\validate-integration.py --release` | 20 | 阻断，452 条（source 6 + skill 446） |
| 再分发 | `python scripts\verify-release-gate.py` | 0 | 472 条 provenance 记录，非阻断 |
| 再分发（发布） | `python scripts\verify-release-gate.py --release` | 20 | 阻断，472 条 |
| 未知参数 | `python scripts\validate-integration.py --bogus-flag` | 2 | argparse 报错 |
| 未知参数 | `python scripts\verify-release-gate.py --bogus` | 2 | argparse 报错 |

## 1. 发版前必须逐条跑

```powershell
$env:PYTHONIOENCODING='utf-8'          # 否则 CJK 输出乱码
python scripts\validate-integration.py            # 必须 exit 0
python scripts\verify-release-gate.py             # 必须 exit 0
python scripts\verify-release-gate.py --json      # 存档用报告
```

- [ ] 两条 local-only 门都 exit 0
- [ ] `--json` 报告已存档，`registry_digest` 与上版比对
- [ ] `content_hash: verified=293/293`（若 skill 数变化则按新总数复算）
- [ ] `findings: skill_scoped=292` 未被静默改动（口径见矩阵文档）
- [ ] 任何数字变化都能指出是 registry 变化还是门被放宽

## 2. 尝试发布再分发时

```powershell
python scripts\validate-integration.py --release
python scripts\verify-release-gate.py --release
```

两条都必须 exit 0 才能进入发布候选。**当前二者均为 exit 20**，因此本仓库
不具备公开再分发资格。允许的处置只有两种：

- [ ] 承认并保持 `local-only`（把发布物限制为内部/授权环境使用），在 NOTICE 中
      如实声明
- [ ] 逐项清零第 3 节未决项后重跑

**不允许**的处置：改门、改阈值、加白名单、放宽枚举、删除 finding。

## 3. 阻断项清零清单（17.29）

每项都有对应门代码，清零后该代码计数归零。

- [ ] **R15 = 0** — 293 条 skill 记录全部脱离 `missing-license` /
      `review-required` / `unverified`。现状 446 条（154 + 138 + 154）。
- [ ] **R14 = 0** — 4 个 source 各自脱离阻断状态。现状 11 条。
- [ ] **R13 = 0** — 组合许可兼容性结论从 `undetermined` 变为 `compatible`。
      现状并集 `["MIT","NOASSERTION","NONE"]`。清除 `NOASSERTION`/`NONE` 或取得
      书面授权，**不得**直接改标成 MIT。
- [ ] **R09P = 0** — `ai-fullstack-delivery` 的 `notice_file` 仍为 `null`。
- [ ] **R10 = 0** — 6 条 notice 与 registry 的 `source_url` / 锁定提交不一致。
- [ ] **R16 = 0** — 4/4 source 缺 `tree_digest` / `source_manifest`（17.28 离线
      attestation）。
- [ ] **R17 = 0** — 无已知 CVE 扫描记录（工具与库版本需记入 release manifest）。
- [ ] **R19 = 0** — 794 个 collateral 文件无独立许可证记录。现状 snapshot 内无
      二进制/字体/归档/数据集，但记录数为 0。
- [ ] **R18 = 0** — 根 `NOTICE` 必须存在且逐条列出所有 source id。

## 4. 结构性错误（两模式都阻断）

以下不是许可证问题，**local-only 模式同样 exit 20**，出现即数据损坏：

| 代码 | 含义 |
|---|---|
| R01 | `sources[]` 缺失或为空 |
| R02 | `commit` 不是 40 位 hex（17.28） |
| R03 | `license_status` 超出 4.1 枚举 |
| R04 | `distribution` 超出 4.2 枚举 |
| R05 | `maturity` 超出 4.1 枚举 |
| R06 | 4.1 准入：`redistributable` 必须是 `verified` |
| R07 | skill 记录没有 path |
| R08 | 重复 / 缺失的 registry path |
| R09 | `notice_file` 指向不存在的路径 |
| R11 | `stats` 与其声称计数的数组不一致 |
| R12 | `content_hash` 漂移 |
| R20 | 应项化的 source 没有 snapshot |

## 5. 退出码

沿用 4.7 冻结表，不得新增并列状态。

| exit | 含义 | 本卡实际使用 |
|---:|---|---|
| 0 | ok | local-only 无结构性错误 |
| 2 | usage | argparse；未知参数**必须**非零退出 |
| 10 | needs_review | 保留未用（`validate-integration` 的 warning 有意留在 0） |
| 20 | blocked | release 模式下任一 17.29 发现，或任一模式下的结构性错误 |

`validate-integration.py` 的 292 条 warning **故意保持 exit 0**：WORK-BOARD
CR-004 记录 189→292 是有意收紧，把它升级为 10 会在不增加任何阻断力的前提下改动
已记录的门结论。阻断力在 `--release`。

## 6. 改动本清单时的纪律

- 门失败时门是对的，直到用测量证明相反。报冲突，不要改门。
- 新增检查必须同时给出会失败的输入和真实非零退出码；只见过「通过」不算证据。
- 每个数字都要能被协调者独立复算，不写估算值。
