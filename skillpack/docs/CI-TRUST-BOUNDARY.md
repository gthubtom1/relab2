# CI 信任边界（T24）

owner：T24。依据：规范第 19 节 T24 卡、第 17.30 / 17.31 / 17.32 节、
第 17.20 节（统一 runner）、第 17.21 节（gate 可信执行根）。

本文是 `auto-merge-journal.yml` 的 write scope 的**独立审查记录**
（17.31 要求的那一份），也是平台验证状态与遥测声明的唯一口径。
与本文冲突的旧执行说明以本文为准；本文改动即信任边界改动，
需独立审查（见 §7）。

## 1. Workflow 权限清单（实测：读 workflow 文本）

| workflow | 顶层 permissions | job 级 write | secret | 网络 | 执行仓库脚本 |
|---|---|---|---|---|---|
| `ci.yml` | `contents: read` | 无 | 无（gate job 零 secret） | 无（默认关闭；需联网的 job 不存在） | 只跑门脚本；不跑 `community-raw/`、`skills/community/`、`docs/community/` 下任何脚本 |
| `macos-bash-compat.yml` | `contents: read` | 无 | 无 | 无 | 同上（只做 `bash -n` 与已登记的回归脚本） |
| `auto-merge-journal.yml` | `contents: read`（默认） | `validate-and-merge` job：`contents: write` + `pull-requests: write` | 仅自动 `GITHUB_TOKEN`（`GH_TOKEN` 环境透传，无自建 secret） | 需要（`gh pr diff/merge/comment` 调 GitHub API；见 §3 审查） | 不执行：只做白名单校验（路径/数量/大小/格式/敏感模式）后调 `gh pr merge --auto --squash` |

以上四列由 `skills/tests/verify-gate-wiring.py` 做机器复核
（vendor 执行、secret、SHA pin、顶层 permissions）。
第三方 Action 全部 pin 到 40 位 commit SHA（`actions/checkout`、
`gradle/actions/wrapper-validation`）。

## 2. 门禁统一入口（17.20）

CI 的集成门只有一个入口：`skills/tests/run-ci-gates.py --runner python`，
清单是 `skills/tests/ci-gates.json`（**23 门 = 21 个 python 门 + 2 个 `runtime: powershell` 门**；`--runner python` 实跑 21），清单本身被
`skills/tests/ci-gates.lock.json` 做 digest 锁定。
`verify-gate-wiring.py` 交叉证明"清单里的每个门都有 workflow 调用"。

### 2.1 生成物新鲜度只有一道 CI 步骤在守（2026-10-02 实测登记）

`skills/INDEX.md` 是**生成物**（`extract-summaries.ps1` 从全部 `SKILL.md` 生成）。
CI 里检查它新鲜度的只有 `.github/workflows/ci.yml` 的
`extract-summaries.ps1 -Check` 一步，**21 个 python 门里没有任何一个检查它**。

实测证据（本次独立复核）：把 `INDEX.md` 弄到过期后重跑
`run-ci-gates.py --runner python` 仍是 `total=21 ok=21 failed=0`、exit 0；
只有 `-Check` 报 `[CHECK] INDEX.md out of date` 并 exit 1。

⇒ 结论（如实登记，不改门）：**"门全绿"不等于"生成物同步"**。改过任何 `SKILL.md` 的
frontmatter/描述后，必须单独跑 `extract-summaries.ps1 -Check`；本地绿而 CI 红，
第一个要查的就是这一步。本卡已重生成一次 `INDEX.md`，该步现为 exit 0
（重生成前后发现面均为 46 canonical + 4 wrapper = 50，`community-raw` 出现 0 次）。

## 3. auto-merge write scope 独立审查记录（17.31）

被审查对象：`.github/workflows/auto-merge-journal.yml` 的
`validate-and-merge` job（`contents: write`、`pull-requests: write`）。

审查结论：**保留，理由如下**（审查人：T24，2026-10-01，wave 2 卡 D）：

1. 该 workflow 不是 gate job，不参与任何门的通过/失败判定；
   它的写操作不改变 gate 脚本、门清单、锁文件或任何受保护路径。
2. 触发面被路径限定：只对 `skills/field-journal/**` 下 `.md` 文件的 PR 生效；
   系统文件（`CONTRIBUTE-BACK.md`、`_template.md`）与非 journal 文件直接阻断。
3. 合并前有机器校验：单 PR 最多 5 个文件、单文件 50KB 上限、首行 `#` 标题格式、
   可疑注入/可执行链接/疑似真实 key 与真实 IP 模式阻断；任一失败即 `valid=false`
   且只评论不合并。
4. 最小权限：只有 `contents` + `pull-requests` 写，没有 `id-token: write`，
   没有自建 secret，没有生产环境；顶层默认已收紧为 `contents: read`，
   后续新增 job 默认只读。
5. 残留风险（如实登记）：`gh pr merge --auto` 的最终生效仍依赖 GitHub 侧规则；
   本仓库从未在真实 runner 上执行过该 workflow（见 §4），GitHub 是否接受
   这份 YAML **未验证**。

已知文字滞后：`verify-gate-wiring.py`（owner T10）的 NEEDS_REVIEW 文案仍写
"审查记录不存在"，那是本记录落地之前的文字。本记录落地后该门仍报 exit 10
（注册非阻断），因为 T24 不得改 T10 的脚本把门改绿；已向协调者提交变更请求：
请 T10 侧把本记录识别为有效记录，或更新文案指向本节。**门保持 exit 10，
不是 exit 0——问题在记录里解决，不在门里掩盖。**

## 4. 平台矩阵（17.30：只写实测，见不到 job 的不写"支持"）

| 平台 | CI job | 实测状态 |
|---|---|---|
| Windows（`windows-latest`，含 Windows PowerShell 5.1 步骤） | `ci.yml` routing-tests 矩阵项 | **未验证**：workflow 从未在真实 runner 上执行（无 `act`、无网络、无 `gh`），GitHub 是否接受该 YAML 未验证；唯一实测是 Windows PowerShell 5.1 + CPython 3.12.0 的本地门禁 |
| Ubuntu（`ubuntu-latest`） | `ci.yml` routing-tests / integration-gates / sh-syntax 等 | **未验证**：同上。本地 12 个 python 门"无 Windows 专属代码"是阅读结论，不是 Linux 实测结论 |
| macOS（`macos-latest`） | 仅 `macos-bash-compat.yml`（且只在 `.sh` 变更时触发，做 `bash -n` 与有限回归） | **未验证**：从未实测；`docs/platforms/macos.md` 与 README 的 macOS 命令是"脚本存在"，不是"已验证" |
| no-git / 离线 | 无独立 job | 未验证 |

macOS / POSIX 与 Unicode 细节（17.30 逐条状态）：

- NFD 归一化：无 CI job，无 fixture，**未验证**。
- 大小写不敏感冲突检测：`verify-repository-security.py` 覆盖仓库内部分检查，
  macOS 真机行为**未验证**。
- umask / 可执行位：`.sh` 可执行位随 git 保留；新建 case 权限显式设定**无门覆盖**，
  登记为后续项（非本卡范围）。
- Windows 保留名 / 路径长度 / symlink-junction 拒绝：部分由现有安全门覆盖，
  跨平台真机行为**未验证**。
- 行尾与编码：写入 LF + UTF-8 无 BOM、读取容忍 CRLF/BOM 是仓库既定口径
 （`.gitattributes eol=lf`）；提交前后字节差异见 HANDOFF §2.1。
- 容器 `TZ` 未设置：无 job，**未验证**。

## 5. CI 沙箱信任边界（17.31 重述为执行口径）

1. CI 不执行社区脚本：gate job 的 `run:` 行不得引用
   `community-raw/`、`skills/community/`、`docs/community/`（机器门 enforcement）。
2. 不可信输入只做数据：PR diff 内容只进入校验器做解析/计数/比对，
   不进入可执行路径；`community-route.py` 在 gate 里以子进程跑的是仓库自有代码，
   不是 vendor 正文。
3. 缓存与产物：当前 workflow 无跨 job 缓存复用；构建产物追溯到 commit，
   runner 镜像 digest 追溯**无**（GitHub 托管镜像，由平台决定，离线不可验证，
   如实登记）。
4. PR 不得改 gate 自证通过：gate 清单有 digest 锁（删门即红）；
   完整的"PR 改 gate 需独立审查"依赖分支保护 + CODEOWNERS（见 §7），
   离线只能做到机器可验证的一半（见 WORK-BOARD §5.1 诚实边界）。

## 6. 遥测隐私声明（17.32）

1. 本仓库 CI 不收集遥测：三个 workflow 均无遥测上传步骤；"上传远端"默认关闭，
   且本仓库不存在开启它的开关——要加必须先披露副作用并获批（与
   `autoInstall=false` 同级）。
2. `field-journal` 是用户主动提交的修复手记，不是自动采集；`leak-scan` job
   对其做未脱敏 secret 扫描，命中即红。
3. 仓库内无 append-only 遥测管道、无固定遥测 schema：17.32 的哈希链/字段集合/
   关闭不降级等要求在"未来引入遥测时"才适用；引入前本节即完整声明，
   不虚构实现。

## 7. Protected gate 与 CODEOWNERS（17.21）

- `.github/CODEOWNERS` 声明：gate 脚本、门清单与锁、workflow、规范与协调板的
  reviewer 要求。注意：CODEOWNERS 文件名里的 owner 占位在接入真实 GitHub
  前必须替换；分支保护与 required checks 是平台侧配置，离线**无法验证**，
  不得声称已生效。
- Required checks 意图（待平台侧启用后核对）：`routing tests` 矩阵、
  `integration gates`（含接线自检）、`shell script syntax check`、
  `field-journal leak scan`、`case contract test`、`Gradle wrapper validation`、
  `version consistency`。

## 8. 本卡范围外的残留（已登记，未改）

- `docs/ARCHITECTURE.md:18,243` 的自动安装图示文字：文件不在 T24 白名单，
  转 T19 清洗。
- `docs/community/ai-fullstack-delivery/`TOOLS.md`:9`、
  `docs/community/ai-fullstack-delivery/README.md:122` 的自动安装句：
  `docs/community/**` 归 T03（已结束），转 T19。
- 各 `skills/*/SKILL.md` 的"可自动安装"工具表：技能正文归各自 owner，
  均为"缺工具时走批准后 bootstrap"的清单语义，不构成无条件执行指令；
  若 T19 要统一口径，由其执行。
- `kali/README-kali.md` 的一键安装段：Kali 面归其 owner，转 T19。
