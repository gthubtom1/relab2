# 托管清单 — 把这个包放到你自己的 GitHub 之前

> **给仓库主人看的**，不是给 AI 看的。代号：Hosting checklist。

## 0. 先做一个判断：**公开还是私有？**

本包**合并了 5 个上游开源技能包**的正文（`community-raw/` 是原文存档，`skills/community/` 是适配层）。
它的**再分发状态是"未批准"**：

- `LICENSE` 只覆盖本仓库自身的框架部分；
- `NOTICE` 列出各上游来源；
- `docs/COMMUNITY-LICENSE-MATRIX.md` 里多条来源的 `license_status` 是 **review-required**（例如 hack-skills）；
- `scripts/verify-release-gate.py --release` 在本仓树上**按设计 exit 20**（等于"不许发布"）。

⇒ **建议：托管为私有仓库**（自己多台电脑同步完全够用）。
要公开，先做 §3 的许可处理；不要因为"看起来是开源合集"就直接公开。

## 1. 必须改的地方（不改会指向别人的仓库 / 误导读者）

| 位置 | 现在写的是 | 改成 |
|---|---|---|
| `README.md` 安装段 | `<this repository's URL>`（占位） | 你的仓库 URL |
| `README.md` 顶部 badge | `github.com/zhaoxuya520/reverse-skill` 的 release / stars / forks / issues 徽章 | 你的仓库地址（或删掉这几行） |
| `README.md` 的 Tutorial / 项目网站链接 | `reverse.apivix.com` | 保留（那是上游项目网站，属出处信息）或删掉 |
| `README.md` 的 release 徽章 | v1.0.1 | 与你仓库根 `VERSION` 文件一致 |

`README_zh.md` / `README-kali.md` 里如有同样的 URL，照改。

## 2. 必须保留的地方（合规与出处）

- `LICENSE`、`NOTICE`、`docs/COMMUNITY-LICENSE-MATRIX.md`、`docs/COMMUNITY-ISSUE-TRIAGE.md`
- `community-raw/` 里各上游包**自带的**许可证与 README（不要删）
- `skills/community/registry.json` 的来源字段（`source` / `source_path` / `license_status`）

## 3. 要公开时的许可处理（三选一）

1. **只公开框架**：把 `community-raw/` 与 `skills/community/` 排除在公开仓库之外
   （43 个核心技能不受影响，但 293 个社区技能不可用）；
2. **逐包确认**：对 `docs/COMMUNITY-LICENSE-MATRIX.md` 里每个 `review-required` 的来源，
   去上游仓库核对许可证并更新矩阵；
3. **保留全部但标清出处**：只在你能接受"许可未澄清"的风险时采用，且必须在 README 顶部写明
   出处与再分发状态。

改完任何一项，跑 `python scripts/verify-release-gate.py`（**不带** `--release`）应保持 exit 0。

## 4. 不要提交的东西

`.gitignore` 已覆盖大部分，推送前再确认一遍：

- `work/`（本机产生的案例/实验数据，可能含真实目标信息）
- `reports/`（报告产物）
- `skillpack/skills/TOOLS.md` / `skills/`TOOLS.md`（按机器生成）
- `.candidates/`、`*.keystore`、`implementation-notes.md`

自查：`git status --porcelain` 为空；`git ls-files | Select-String "work/|reports/"` 为空。

**另一类**：文档里残留的**本机路径**（如 `C:\Users\<你的用户名>\...`、`(Resolve-ReverseToolSpec -Name 'pyre').Command\...`）。
它们不是密钥，但会泄漏你的环境。

> **私有库可跳过本条。** 本仓库已确认是**私有、自用**（2026-10-02 仓库主人确认），
> 不做公开分发，那么这条路径清洗**不是发布门**，可以整条跳过；下面的自查命令仅在
> 将来要公开时才需要跑。

公开前对 `HANDOFF.md`、`CLAUDE.md`、`docs/*.md` 过一遍：

```powershell
git ls-files | Select-String -Pattern '\.md$' | ForEach-Object { $_ } |
  Select-String -Pattern 'C:\\Users\\|D:\\EXE\\|/Users/'
```

（`HANDOFF.md` 是**交接文档**，历史上记录过本机环境；如果不想公开它，删掉它不影响包的功能。）

## 5. 推之前最后三条自查

```bash
python skills/tests/run-ci-gates.py --runner python      # 期望 total=21 ok=21（清单共 23 门：21 个 python 门 + 2 个 powershell 门由 CI 单独跑）
powershell -NoProfile -ExecutionPolicy Bypass -File skills/scripts/verify-routing-coherence.ps1   # 期望 ALL PASSED（没有 .sh 版本）
python scripts/verify-release-gate.py                    # 本地模式 exit 0
```

## 6. 别人 clone 之后会发生什么（安全确认，**含一条必须处理的例外**）

- **不会自动跑任何东西**：安装、工具索引、依赖安装全部要用户显式执行（包内有同意门，见 `README_AI.md` §0）。
- `.github/workflows/**` 只在 GitHub Actions 里运行，做的是仓库自检（回归、路由、契约），不含密钥、
  不自动合并代码、不自动回写仓库内容。
- ⚠️ **例外，公开托管前必须处理**：`auto-merge-journal.yml` 是本仓**唯一带写权限**的工作流
  （`contents: write` + `pull-requests: write`），它会自动合并 `skills/field-journal/` 的手记 PR。
  独立审查（2026-10-02，`work/round1-verify/review/X3.md`）实测：它的内容门是**九道英文 grep 黑名单**，
  **一句纯中文提示注入即可同时绕过它和 `scan-leaks.ps1`**（两道关卡同时放行）。
  它的写作用域审查记录在 `docs/CI-TRUST-BOUNDARY.md`，`skills/tests/verify-gate-wiring.py` 会检查该记录是否存在。
  **建议：公开托管时直接停用这个工作流**（对这个 43 技能的核心包价值很低），
  或至少把 `CODEOWNERS` 的占位符换成真实账号并开启 required reviews。
