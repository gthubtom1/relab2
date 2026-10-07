# Customer-skin E2E（T23，规范 17.18 / 17.20）

Owner：T23。写入范围：`tests/e2e/**`（新目录）、本文档。未触碰卡 N / O / P
文件、T16 脚本与 schema、`scripts/adapt-community.py`（全程只读，未调用）。

核心命题：**开发 checkout 通过不能替代 release bundle 通过**。本卡把这句话
变成可执行的测试，而不是再声明一遍。

## 1. bundle 怎么来

T16 候选（manifest + sbom + checksums）是 digest-only，不可运行，不能当 E2E
目标。可运行的客户 bundle 定义为：checkout 树的文件拷贝（去掉 `.git`、缓存、
导入器 staging），放在仓库外：

- 导出：`python tests/e2e/customer-skin-e2e.py` 自动把仓库根拷贝到
  `D:/Project/skills-hub/work/t23-lab/bundle`（忽略 `.git`、`__pycache__`、
  `.candidates`、`*.pyc`；实测 2115 文件）。
- 自举证明：F07 用 **bundle 自己的脚本拷贝**以 `--root <bundle>` 重新跑
  T16 `build` + `check`，证明 bundle 自给自足，不依赖 checkout。
- lab 与产物一律在仓库外 `D:/Project/skills-hub/work/t23-lab/`：
  `bundle/`、`bundle-broken/`（负向突变拷贝）、`candidate/`、`oldcase/`、
  `e2e-report.json`、`e2e-run.log`。

## 2. 每条 fixture 怎么跑（全部 cwd=bundle，离线，无安装）

运行器：`tests/e2e/customer-skin-e2e.py [--lab DIR] [--no-export] [--fixtures ...]`。
每条打印 cwd / runtime / 依赖 / 期望 JSON / stdout / stderr / 退出码。
runtime 实测：`python 3.12.0 (Windows/AMD64)`，依赖一律标准库。

| fixture | 皮 | 命令（cwd=bundle） | 期望 | 实测（2026-10-01） |
|---|---|---|---|---|
| F01 discovery | 递归扫描==INDEX==manifest，无 raw 泄漏 | `audit-discovery-surface.py` | exit 0 | exit 0（46 canonical + 4 wrapper = 50，raw 暴露 0） |
| F02 route | 社区路由真实命中 | `community-route.py --hint "ctf pwn binary exploitation" --json` | exit 0 + matched + matches[0].id=wrapper-* | exit 0，wrapper-ctf-super-hub |
| F03 wrapper | 四 wrapper + 48 路由 | 内联检查 4 SKILL.md + routing.json | 0 缺失，routes=48 | exit 0 |
| F04 case/integration | 适配边界 | `validate-integration.py` | exit 0 | exit 0（298 license-review 警告，非阻断） |
| F05 artifact | 来源包自检 | `verify-community-bundle.py` | 0（或 10 且具名 no-.git） | exit 10，no-.git 具名（诚实降级） |
| F06 report/gates | 发布门双态 | `verify-release-gate.py` 与 `--release` | 0 / 20 | 0 / 20（红即正确） |
| F07 candidate | bundle 自举 T16 | bundle 内 `build-release-candidate.py build --root bundle` + `check` | build 0（或 10）+ check 0 | build 10（no-.git）+ check 0 |
| F08 upgrade→rollback | VERSION bump 后路由仍通，回滚字节一致 | 改 bundle 内 VERSION → route → 恢复 → route + sha256 对比 | 升级通，回滚一致且通 | 全过（含 sha256 恢复一致） |
| F09 old-case | 旧布局被识别+指引，不静默迁移 | lab 内旧式 scope.json(0.9)+assets/evidence/reports 平行根 | recognized，指引发出 | 通过 |
| F10 no-tool | 缺工具=明确指引，不猜路径 | tool-index 缺席（gitignored，不发货）+ bootstrap-manifest 能力 | 指引源=manifest，无猜测路径 | 通过 |
| F11 signature | 无签名/无批准如实拒绝 | `--distribution redistributable`；无 approval 验门 | 20 / 20 | 20 / 20 |
| FNEG 负向 | checkout 绿 ≠ bundle 绿 | lab 拷贝删一 wrapper：checkout 对照 0，坏包探针与 audit 非零 | 差异被抓到 | 抓到（0 vs 非零/非零） |

总况：**12/12 通过，runner exit 0**（见 `t23-lab/e2e-report.json`）。

## 3. upgrade / rollback 说明

F08 是**文件级模拟**（bundle 内 VERSION bump → 验证 → 字节恢复），不是真实
安装器升级。刻意不用 `scripts/adapt-community.py` 的 promote 路径：
生产记录下各 scope 的 promote 当前全被拒（exit 20，见 IMPORTER-LIFECYCLE §7），
那是特性工作（具名阻断），不是可用的升级通道；本卡只读未调它。

## 4. 已在本地验证 vs 未验证（DEVIATIONS，本卡最重要的产出之一）

已验证：上表 F01–F11、FNEG，全部是真 bundle 拷贝上的真实退出码。

未验证（及为什么）：

- D1 真实 runner（GitHub release.yml 的 ubuntu runner）：本环境无该 runner，
  release.yml 只做静态合规阅读，未执行。T16 同款诚实声明。
- D2 真实安装器升级/回滚：本仓库没有安装器产物，F08 只是 VERSION 文件级模拟；
  真实"旧版本→新版本→回滚"的安装语义无处可跑。
- D3 Windows PowerShell 5.1 / bash / macOS / no-git 以外的平台：只在当前
  Windows + Python 3.12 跑过；文档不声明其他平台已验证。
- D4 签名/信任根/轮换/撤销：未实现（T16 D1），本卡只断言"如实拒绝"（F11）。
- D5 CVE 扫描：未实现且禁网，SBOM 空数组=未扫描（T16 D3）。

## 5. 复跑

```powershell
$env:PYTHONIOENCODING='utf-8'
D:\EXE\python\python.exe tests\e2e\customer-skin-e2e.py
```

全绿 exit 0；任一 fixture 失败则 exit 1，逐条块保留现场。
`--fixtures F01,F02,FNEG` 可跑子集（仍先重导出，保证与树一致）。
