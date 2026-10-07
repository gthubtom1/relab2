# CAPABILITY-REPORT — 这套包到底能干什么（2026-10-02 实测）

> 这份是**对外可引用的能力结论**。所有数字都由协调者在真树与**仓库外 clone** 上独立复算过；
> 每个数字下面都写了复算命令。争议项一律"如实登记"，不粉饰。

## 1. 四把尺子（同一个包，四种问法）

| 尺子 | 规模 | 成绩 | 量的是什么 |
|---|---|---|---|
| 官方基准 `skills/tests/routing-benchmark.json` | 182 | **182/182 = 100%** | 照文档用词问能不能路由对 |
| 自然说法基准 `skills/tests/routing-benchmark-natural.json` | 86 | **76/86 = 88.4%** | 随口说人话能不能路由对 |
| 300 条大样本（**仓库外**：`…\work\natural-300\cases.json`） | 300 | **297/300 = 99.0%**（canonical 100/100、community 197/200） | 覆盖全部技能的调优集 |
| **组外新说法（hold-out）**（**仓库外**：`…\work\round1-verify\holdout-100.json`） | 100 | **26.0%**（干净子集 29.6%；community **9.8%**） | **换了说法还认不认得** |

> ⚠️ **后两把尺子的题集与复算脚本不在这个仓库里**（`work/` 被 `.gitignore` 忽略，且里面可能含本机数据）。
> 所以从别人的 clone / 你的 GitHub 上**只能复算前两把尺子**；要复算 297/300 与 26.0%，
> 需要本地那套 `work/round1-verify/measure300.py`、`holdout-measure.py`（脚本清单见 §5）。
> 这两行的数字是本机独立复算并逐条留证的，**不是从仓库里读出来的**。

### 三条必须同时说出口的话

1. **官方基准的 100% 不是"命中率"**：实测 **178/182（97.8%）** 的题目直接命中它自己那条路由的 `must` 正则
   —— 那是"照答案问"，只证明回归不退化。
2. **300 条的 99.0% 是"同一批字面"的成绩**。换成同技能的**新说法**（另造 100 条，与原题面最长公共连续汉字 ≤5），
   正则路掉到 **26.0%**；把"读表盲判认为语义没变"的 81 条单独拿出来，也只有 **29.6%**（社区侧 **10.6%**）。
   分离实验证明**语义漂移不是主因**（盲判与答案键一致 81/100），**桥不泛化才是**。
3. **读表路比正则路更能认新说法**：同一批新说法上，**只读入口文档**的盲判与答案键一致率 **81%**，
   远高于正则路的 26%。（这与库内 U27 记录的"正则 47% vs 读表 97%"同型。）

## 2. 结论：两条路各自该用在哪

| 场景 | 用哪条路 | 依据 |
|---|---|---|
| 说法与文档/词表里的说法接近 | **正则路**（`master-route.ps1` / `community-route.py`） | 单次 43ms、离线、可复算；调优集 99.0% |
| 说法是新的、口语的、跨术语的 | **读表路**（`MASTER-ROUTING.md` / `routing.md` / `SYMPTOM-INDEX*.md`） | 新说法上 81% vs 26% |
| 两条都没把握 | `AGENTS.md` 的"**未命中三步**"：先补问 → 判边缘（标 `needs_review`）→ 提示新能力，**禁止硬塞** | 上游 5 包一致做法 |

**不要做的事**（已实测是假收益）：调 `MIN_CONFIDENCE`（净收益 −17）；为下一批说法再补一轮词表
（那是把过拟合往后挪一批）；为凑分破坏 CTF 入口设计。

## 3. 质量面（本轮实测）

- **门**：**真树 `total=21 ok=21 non_blocking=0 skipped=0 blocked=0 failed=0`**（清单 23 门；
  `--runner python` 实跑 21 = 23 − 2 个 `runtime: powershell` 门：`test-routing`、`verify-routing-coherence`，它们由 CI 单独跑）。
  clone 里 `total=21 ok=17 non_blocking=3 skipped=1 blocked=0 failed=0`，差异的 4 项（3 个 `exit 10` + 1 个 `SKIP`）全是**已登记的缺快照降级**。
- **`scripts/verify-evolution.py`**：10 项机器门（文档链、信号层 fail-closed、路由入口、社区可达、工具清单、
  registry 一致性、脚本清单、路由一致性、规范结构、双基准），**已接进 CI**。
  它在 `skills/tests/ci-gates.json` 里的 `blocking_exits` 是 `[20, 21, 30]`，含义按脚本自己的约定：
  **20 = 有检查失败（阻塞）、21 = 缺必需输入（阻塞）、30 = 子检查崩溃/超时（阻塞）**；`0` = 全绿。
- **机器保障**：`docs/EVOLUTION-CHECKLIST.md`（10 条）+ 上面那个脚本 + `skills/SYMPTOM-INDEX*.md` + `AGENTS.md` 未命中三步。

## 4. 已知边界与待裁决（都不是"没人做"，是"需要 owner 决定"）

| # | 事项 | 现状与证据 |
|---|---|---|
| 1 | 300 条里最后 **3 条**（N131/N180/N213）关不掉 | 桥已成立、记录已进候选，但同 wrapper 内同 rank 记录按 path 破平把它们挤出 `references[:3]`；要救只能改 `REFERENCE_LIMIT` 或破平规则（机制改动） |
| 2 | 读表侧 **F4 兜底**（"无强锚点 → 改判 R47"）已撤掉（见 §4.1） | 两个口径都要看清：**引用** F4 的 36 条判定里 17 对 / 19 错（47%）；其中**实际触发这条兜底改判**的 27 条是 8 对 / 19 错（**29.6%**）。三种口径（判 ctf / 判 hack / 弃权）分别得 269 / ≈270 / 丢 17 条正确，**没有赢家**；且 N171 与 N273 几乎是同一道题却分属两个包 ⇒ **答案键带噪声**，不是文档单方面的错 |
| 3 | `signals` schema `maxItems=128` 已顶满 | **上界实验**：给 28 条缺口各注入一条必然命中的信号，**28/28 都能进 references** ⇒ 提额可再关若干条；改 schema 属机制改动 |
| 4 | 泛化差距 | 见 §1；改进方向是语义匹配（上游 5 包都没上向量，本包也没有），**当前用读表路覆盖** |
| 5 | 本仓是 **local-only candidate，不可 redistributable** | 签名/trust root/轮换/SBOM 等 T16/T21 项如实登记为未实现 |

### 4.1 四项待裁决项的决策记录（2026-10-02）

| # | 项 | 决定 | 依据 |
|---|---|---|---|
| 1 | F4 兜底（"无强锚点 → 判 R47"） | **撤掉默认方向**：改成"补齐语境三问；补不齐就 `uncertain` 交回用户" | 实测触发 27 次、判错 19、判对 8（准确率 **29.6%**，低于抛硬币）；把默认方向翻成 R46 只是把"19 错 8 对"翻成"19 对 8 错"，**收益全部来自迎合一批已知带噪声的答案键**，不是新信息 |
| 2 | 最后 3 条缺口（N131/N180/N213）的破平规则 | **不改** `REFERENCE_LIMIT`、不改 `_reference_sort_key` | 改动的全部收益是"在自己出的 300 条上从 99.0% 到 100.0%"；hold-out 证明真实瓶颈是泛化（社区侧 10.6%），不是这 3 条。为考卷满分动引擎是典型假收益 |
| 3 | `signals` schema `maxItems=128` 提额 | **不提** | 上界实验（注入必中信号 → 28/28）证明的是"给定题面写规则就一定能救"，而那正是抄题；hold-out 显示新说法不在任何规则里，提额只会让"补规则"这条过拟合路径更顺手 |
| 4 | 泛化差距（26% vs 99%） | **不上语义匹配/向量**；两条路的用法不变（正则快速路径 + 读表兜底），并把边界写进包内文档 | 上游 5 包都没有向量/语义检索（U22 已盘点），读表路在新说法上已有 81%；对 336 技能这个规模，向量属过度工程。要做的是**让使用者知道边界**，不是继续堆词表 |

四项都已落地或明确不做：第 1 项有具体文档改动（`skills/routing.md` 的 F4 段 + `MASTER-ROUTING.md` 同口径同步），其余三项按"登记 + 说明理由"处理。

**第 1 项改动后的读数注意**：本报告提到的读表侧数字（第一轮 91.0% 无索引 / 97.7% 有索引；第二轮 87.3% → 94.0% 同段对照；
第二轮全集 269/300 = 89.7%）都是**撤掉默认方向之前**的实测，完整来源见 `docs/WORK-BOARD.md` 的 U30/U33 两条与
`work/readtable-mask/REPORT.md`、`work/readtable-mask2/`（**均在仓库外**）。
撤掉之后，无强锚点的题面不再落进 R47，而是**三问能答就判、答不出就标 `uncertain` 交回用户**，
所以"判对数"会下降、"弃权数"会上升 —— **本轮没有重跑读表盲测，因此不给出改动后的新数字**。
拿读表数字对外时，请连这句话一起说。

## 5. 复算命令（任何人可跑）
```bash
export PYTHONIOENCODING=utf-8        # Windows PowerShell: $env:PYTHONIOENCODING='utf-8'
# ① 双基准（仓库内，任何人可复算）
powershell -NoProfile -ExecutionPolicy Bypass -File skills/scripts/test-routing.ps1          # 182/182
powershell -NoProfile -ExecutionPolicy Bypass -File skills/scripts/test-routing-natural.ps1  # 76/86
bash skills/scripts/test-routing.sh                                                          # Linux/macOS 版
# ② 全门（清单 23 = 21 个 python 门 + 2 个 powershell 门；--runner python 实跑 21）
python skills/tests/run-ci-gates.py --runner python
# ③ 融新包的自检
python scripts/verify-evolution.py
```

**只有 ① 与 ②③ 能在别人的 clone 上复算。** §1 后两行的 300 条与 hold-out 用的是**仓库外**的题集与脚本
（`<本地工作区>\work\natural-300\cases.json`、`<本地工作区>\work\round1-verify\measure300.py`、
`holdout-measure.py`），它们被 `.gitignore` 排除、不在仓库里；本机复核命令形如：

```bash
python "<本地工作区>/work/round1-verify/measure300.py"       # → canonical 100/100、community 197/200、总 297/300
python "<本地工作区>/work/round1-verify/holdout-measure.py"  # → 26/100
```
