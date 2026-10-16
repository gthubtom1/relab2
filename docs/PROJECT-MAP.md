# 项目功能地图与核验入口（PROJECT-MAP）

> **这是权威说明，稳定不变**；它回答三件事：
> ① 这个项目由哪些**层**组成；② 每一层用什么命令**核验**；③ **生成快照**放在哪、怎么刷新。
>
> ⚠️ 所有带数字的实测快照都在 `docs/_snapshots/` —— 那些**会过期**，读之前先重跑对应命令。
> 本文件**不写任何会腐烂的数字**，只写"怎么测"。

---

## 1. 十五层功能线路

| # | 层 | 里面是什么 | 核验方式 |
|---|---|---|---|
| 1 | **入口层** | `relab2.ps1` 的三个对外子命令：`doctor` / `setup` / `update` | `feature-tree.py` 清点 + `full-simulation.py --layer entry` 真跑 |
| 2 | **技能层** | 57 张顶层技能卡（+6 嵌套），每张是"该怎么做"的方法论 | frontmatter 可解析 + 路由指向 + `verify-project-requirements.py` |
| 3 | **路由层** | `config/routing.json` 的关键字规则 → 目标技能 | `verify-routing-coherence.ps1`（含真实原话基准） |
| 4 | **工具层** | 探测层能解析的工具 id + 33 类能力 + **调用配方** | `test-tool-recipes.py`（**真跑**每条配方）+ `test-new-tool-discovery.py`（虚构工具也要认得出） |
| 5 | **MCP 层** | 宿主注册的通道（含 REA 经**筛选桥**） | `full-simulation.py --layer mcp`（真起、报工具数） |
| 6 | **门禁层** | `tests/ci-gates.json` 里的每道门 | `run-ci-gates.py`（一次跑完、汇总 blocked/failed） |
| 7 | **工作流层** | 案例生命周期：`case-init` → `append-evidence` → `review_case` → `diff-runner` | `full-simulation.py --layer workflow` |
| 8 | **换机层** | `环境初始化.md` §11 的适配面与验收门 | `doctor` + `selfcheck-newmachine.ps1`（**分战场分母**） |
| 9 | **知识库层** | **209 篇技术正文** + `field-journal/KB-INDEX.md`（现象→文档的症状索引）+ 上游溯源 | `verify-leaves.py`（每篇有没有入口）+ `doctor` 的知识库项 |
| 10 | **kernel 行为层** | 中枢本体：卡片池 / 工作台 / 自检 / 验证 / 隔离运行 | `feature-tree.py` 清点 + `kernel/05-tests/run_all.py` |
| 11 | **经验卡层** | 仓级共享经验（跨技能），每张是一次真实踩坑的沉淀 | `experience-card.py search/validate` + `test-experience-card.py` |
| 12 | **社区层** | vendored 第三方技能源 + 我们的 wrapper（4 个） | `test-community-route.py` / `test-community-decoys.py` |
| 13 | **扩展层** | 宿主侧加固（`extensions/pi/cmd-guard`） | 该扩展自己的 README |
| 14 | **契约/模板层** | `templates/` + `schemas/` + `ops/`（跨技能共用的契约与方法） | `verify-leaves.py`（每个都有入口）+ `test-contract-v2.py` |
| 15 | **依赖层** | 跑这些脚本真正要的运行时与包 | `feature-tree.py`（会报 python / node / **mcp 版本** / venv） |

---

## 2. 核验工具箱（逐层可复核）

| 命令 | 它回答 |
|---|---|
| `python skillpack/skills/tests/feature-tree.py` | 项目的**完整线路树**（十五层，从真实文件推导） |
| `python skillpack/skills/tests/verify-leaves.py` | **逐树杈核验**：每片叶子有没有入口（存在但没人指向 = 断） |
| `python skillpack/skills/tests/feature-graph.py` | **功能可达图**：技能间指向、**跨战场边**、孤岛 |
| `python skillpack/skills/tests/feature-graph.py --body` | **AI 身体图**：技能/知识/经验卡/契约/脚本/kernel/门禁/工具**全部类型**节点 + 跨类型边 |
| `python skillpack/skills/tests/full-simulation.py --full` | **逐线路真跑**（入口命令、卡、路由、工具、MCP、门禁、工作流） |
| `python skillpack/skills/tests/test-tool-recipes.py` | 工具的**调用配方真跑**（参数错会 HANG → 必红） |
| `python skillpack/skills/tests/scan-defect-classes.py` | **缺陷类型扫描**（文档命令行 / 跨 shell 混流 / 路径 / 退出码 / 静默吞异常 / 超时 / 从未真跑） |
| `python skillpack/skills/tests/run-ci-gates.py` | 全量门禁（含上面这些，见 `ci-gates.json`） |

**判定原则**：树干只是骨架，**要保证的是每一片叶子都能被走到**；
而"能走到"分两半 —— `verify-doc-links.py` 查"链接指向的东西在不在"，`verify-leaves.py` 查"**在的东西有没有入口**"。

---

## 3. 生成快照（会过期）

⚠️ 快照是**生成物**：下面 4 条命令每条都会**整份覆盖**对应的文件 —— 跑过才算刷新，读旧字节 = 读旧状态。

**4 条命令，一行一条，脚本自己写文件**（2026-10-16 起四份都支持 `--write-doc`）：

```powershell
python skillpack/skills/tests/feature-tree.py  --write-doc docs/_snapshots/FEATURE-TREE.md
python skillpack/skills/tests/feature-graph.py --write-doc docs/_snapshots/FEATURE-GRAPH.md
python skillpack/skills/tests/feature-graph.py --body --write-doc docs/_snapshots/FEATURE-BODY.md
python skillpack/skills/tests/verify-leaves.py      --write-doc docs/_snapshots/FEATURE-LEAVES.md
```

| 文件 | 由谁写 |
|---|---|
| `docs/_snapshots/FEATURE-TREE.md` | `feature-tree.py --write-doc <路径>` |
| `docs/_snapshots/FEATURE-GRAPH.md` | `feature-graph.py --write-doc <路径>` |
| `docs/_snapshots/FEATURE-BODY.md` | `feature-graph.py --body --write-doc <路径>` |
| `docs/_snapshots/FEATURE-LEAVES.md` | `verify-leaves.py --write-doc <路径>` |

`--write-doc` 由**脚本自己按 UTF-8 / 无 BOM / LF 写字节** —— **所以不要再 `>` 重定向**
（PowerShell 5.1 的裸 `>` 写出来是 **UTF-16LE + CRLF**，一次就把格式写坏；这三份快照全都是 UTF-8 / LF）。
不带 `--write-doc` 时行为不变（照旧 print 到 stdout，`--json` 分支不受影响）。

**两个坑（实测都踩得到）**：

1. **`--write-doc` 是「整份覆盖」：每份快照开头那 3 行横幅是手写的（脚本不产出）** —— 会被冲掉。
   **重跑前先备份头 3 行、跑完贴回**（横幅原文见任意一份现有快照的头部）。
   > ★ 待办（归维护者）：让横幅成为脚本输出的第一行 —— 那时 §3 就彻底没有「手写 vs 生成」两套来源了。
2. **`verify-leaves.py` 单跑要几分钟**（全仓扫叶子，不挂，就是慢）。别当成卡死中途掐掉。

> 实测（2026-10-16）：`--write-doc` 出来的**首行就是正文**（4/4：
> `feature-tree.py` -> `relab2 · 功能线路树（从真实文件推导）`、`feature-graph.py --write-doc` -> `# 功能可达图（技能 × 工具 × 知识）`、
> `feature-graph.py --body` -> `AI 身体图 —— …`、`verify-leaves.py` -> `逐树杈核验（叶子 = 能被真的走到）`）——
> **不要手工截掉头几行**，它们就是正文的第一行；**唯一例外是那 3 行手写横幅**（见上）。

每份快照头部都带横幅。**读它 = 读某个时间点的字节，不是现状。**

---

## 4. 与其它权威文档的关系

| 想知道 | 读哪份 |
|---|---|
| 怎么开始干活 / 入口链 | `START-HERE.md` |
| 换机适配 | `环境初始化.md`、`环境建设.md` |
| 已知边界与未闭环项 | `docs/KNOWN-BOUNDARIES.md` |
| 项目由哪些层组成、怎么核验 | **本文件** |
| 某层当前实测数字 | `docs/_snapshots/`（**先重跑命令**） |
| 需求与军规 | `docs/lcs-core/02-YG对本项目的终极需求与实战交付军规.md` |
