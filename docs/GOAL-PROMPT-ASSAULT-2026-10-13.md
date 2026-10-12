
> 自含全部目标、判据、红线与状态机定义，不依赖外部上下文。
> **配套本地文档**：`C:\relab2\docs\ASSAULT-GOAL-2026-10-13.md` —— 权威定稿，
> 开工前通读，每阶段开头重读，完成后按 §9 追加记录。
> **姊妹篇（均已完成，不要重做）**：`docs/DELIVERY-GOAL-2026-10-12.md`（初逆复刻）、
> `docs/UPDATE-GOAL-2026-10-12.md`（版本更新）。

---

## 总目标（整个项目唯一的目的地，不许偏移）

> **任何一个程序 / APK / 固件 / 网站客户端，无论它套了多少层保护——加壳、虚拟化、混淆、
> 反调试、反虚拟机、云端验证、授权卡密、签名校验、自检、设备绑定，或以上全部的组合——
> AI 都能尽最大努力走到一个终点：交付一个可运行、可验证、功能与原目标等价的成品。**

分叉路可以有很多条（脱壳 / 动态 dump / 符号执行 / trace 折叠 / patch / 源码恢复 /
行为复刻 / hook 绕过 / 本地服务替代），**但终点只有一个**。

每一步动手前问一句：**「这一步是否让成品更近？」** 答不上来就是白做。

成品只有三种形态，不许发明第四种：
1. 源码 / 可构建项目
2. 可运行的复刻实现
3. 打了补丁的原程序

---

## 本文的组织原则：这是状态机，不是步骤表

**本方案刻意不规定「第几步」。** 规定步骤数等于限制能力——真实目标千变万化，
有人三个状态转一圈就完，有人要转三十次，取决于目标而不取决于表。

```
一份滚动报告（assault.md）  —— 唯一的工作载体，越改越准
    ↑ 被四状态机驱动
四状态机（SURVEY / ROUTE / EXECUTE / VERIFY）—— 之间可任意跳转，无顺序、无次数限制
    ↑ 被三条铁律约束
三条铁律（不可变）
```

- **报告是滚动的，不是一次性交付物。** 每次状态跳转都回写报告；
  报告的任何一格都可以被后面的新证据推翻重写。
- **状态机没有「下一步一定是 X」。** 从任何状态都可以因为一个发现跳到任何其他状态。
- **唯一不可变的是三条铁律和终点定义。**

这直接来自用户原话（防止后面有人把它改成步骤表）：

> 「他自己给我一份非常详细的报告，什么清单类型的……然后他自己说哪种路线概率最大……
> 但是不一定他说那个概率大就真的概率大，他要在后续真实的操作过程中，像人一样不停地调整……
> 因为它刚开始分析不一定完善，后面一边操作一边补充，也许就让它的思路越来越清晰。」

---

## 三条铁律（不可变，其余全部可调）

**铁律一：报告必须随时能回答「现在到哪了、凭什么这么走」。**
任何时刻打开 `assault.md`，必须能看到：当前处于哪个状态、这一层的结论是什么、
下一步是什么、以及**凭什么**（引用哪条 Evidence）。答不上来 = 漂移，停下来重写报告。

**铁律二：新证据推翻判断时，允许且必须跳回任何状态。**
不许为了维护原计划忽略新证据。路线被证伪了就换路线，层次判错了就重判。
「已经投入很多时间」不是继续一条错路的理由。

**铁律三：终点只有三种成品，验证只有一种方式。**
「分析报告很完整」不是成品。「程序能启动」不是成品。
成品 = 三种形态之一，且通过同输入对照 + `review_case.py` 审计。

---

## 攻坚者五条（本项目新增的第三维：操作者维度）

**这不是判据表，是姿态。** 前两维（系统、工具）决定装备好不好，这五条决定人行不行。
写在 `assault-entry.md` 第一屏，AI 动手前先读。

**第一条：分清搬运工和货物**
在壳层（L1）里花的每一分钟，都要问一句「我改的是搬运工还是货物」。
判定点几乎从不在 L1——壳是搬运工，业务逻辑才是货物。
停在壳层打转 = 项目没推进，无论做了多少工作。

**第二条：工具输出是线索，不是结论**
`diec` 报的壳类型、反编译出的伪码、`strings` 抓到的常量、`capa` 命中的能力——
**全部是线索，没有一个是事实**。反编译器会把 `__ftol()` 当成返回值而藏起真实输入
（DX-Ball 实证）；VMP 静态看到的立即数是 VM key 加密过的假值。
**结论必须由两条以上独立证据交叉支撑**（ADF-R4*：validated 需 ≥2 独立证据）。

**第三条：优先查矛盾，不优先查顺利**
顺利的地方最不用看。真正值钱的是「不对劲」：反编译结果和行为对不上、
导入表干净得可疑、两份证据互相冲突、函数名叫 A 但干的事像 B。
**矛盾就是入口。** 遇到矛盾不许选一个顺眼的放下，要查清为什么不一致。

**第四条：宁可写卡住，不许写完成**
「我卡在 U-007，原因是 VM context 进出被 XOR 变换」是**有效交付**。
「已完成」但没有对照证据是**无效交付**。
门禁绿、程序能启动、代码写完了、报告很厚——**这四件单独一件都不等于成品**。

**第五条：调整路线是正常的，不调整才不正常**
真打硬目标，第一次选的路线大概率不完整。一边打一边修正是人的工作方式。
调整不是失败，是进展——但每次必须写清「旧路线为什么不通 / 新证据是什么 /
新路线凭什么更可能通」，记进 timeline 的 `decision_delta`。
**一次都没调整过的攻坚记录，默认是编的。**

**五条的根基**：目标是终点唯一（可运行、可验证、功能等价的成品），路径不预设。
每一步动手前问「这一步是否让成品更近」，答不上来就是白做。
**难度花在 `how` 上，永远不花在 `whether` 上。**

---

## 先认病（理解为什么要做，不要只执行）

**病症零：方法论被套到不适用的任务上。**
本项目建的所有东西**只对「受保护目标攻坚」这一类任务生效**。
日常开发 / 写新功能 / 修 bug / 做工具 / 写脚本 / 部署 / 写文档——
**该触发什么技能就触发什么技能，该用什么工具就用什么工具，一套多余工序都不该加。**

kernel 的 `04-全能工程中枢` 早已建成六条线，各自有完整流程：
`desktop-product`（原创桌面软件）/ `web-service` / `cli-tool` /
`source-takeover`（接手有源码仓库）/ `exe-rebuild`（无源码商业二开）/ `protocol-automation`。
**本次新增第七条线 `assault`：任意受保护目标 → 等价成品。**
它不覆盖前六线，前六线也不覆盖它；前六线本次一行不动。

**病症一：我们的 VMP 知识非常深，但默认路径是 CTF 五件套。**

实查：`references/vmp-virtualization-analysis.md`（VM entry 定位四步法 + dispatcher 三段式 +
四条外部可观测判据）与 `references/vmp-devirtualization-toolchain.md`（三级降级 + 等价性验证）
质量很高。**但用户拿到 VMP 样本时，R0 主 SKILL.md 的 `Problem-Solving Workflow` 是**：

```
1. strings 提取 flag → 2. ltrace/strace → 3. Frida hook strcmp/memcmp → 4. angr → 5. Qiling
```

`Quick Wins` 第一条：`floss binary | grep -iE "flag|secret|password|key"`。
**这五件在 VMP 面前全军覆没**，而那两篇好文档挂在 `Additional Resources` 第 83 行，
`signal-to-tool-decision.md` §7 还只写「参考 patterns*.md」——**指了个空**。
结论：**不是知识不够，是入口错了。有一座军械库，门口指示牌写着「先用弹弓」。**

**病症二：攻坚没有对账表。** `rebuild.md` 只挂在「复刻交付」路径上，
攻坚这条路打到最后没有一张「目标有哪些功能 / 哪些已还原 / 哪些卡住 / 差什么」的表，
半成品不可累积，下次从零开始。

**病症三：38 条门禁全自指。** 测路由一致性、文档闭合、门禁自身没退化，
**没有一条在真实硬目标上跑过端到端**。`KNOWN-BOUNDARIES.md` 第 4 条自己承认：
「任何真实目标上的效果——做不到的原因：这是技能包，不是测试环境。」

**病症四：只造枪，没造用枪的人（本次补充，前几次返工的真缺口）。**
项目有 47 个技能 + 472 篇文档，**每一处都假设 AI 是不会主动判断的执行体**——
所以什么都写成判据表、字段表、状态表。结果是纪律极其完备，
但**没有一处告诉 AI「该用什么姿态面对未知目标」**。
REA 只有 237 行 SKILL，极少写"你要严谨"，因为它把工具层做厚、把判断留给模型；
我们正好相反：工具散在各处，判断层是空的。一旦目标超出判据表覆盖（硬目标必然超出），
AI 就没有然后了。
**所以本次补第三个维度「操作者」——见上面「攻坚者五条」。**
本方案从此三维：① 系统（入口/对账表/状态机/审计器）② 工具（47技能+472文档+133脚本）
③ 操作者（面对未知怎么想、怎么不自己骗自己）。**缺①是散沙，缺②是空谈，缺③是
"纪律很好但不会判断的部队"。**

所以本次要做四件事：**建入口、建对账表、通工序、立操作者姿态，最后真打一次。**

---

## 四个阶段（顺序执行；判据未达成的阶段不许标记完成）

> 注意：**阶段是建设顺序，不是运行时步骤。** 建设完成后，
> AI 面对真实目标时走的是上面那套四状态机，不按阶段表走。

### 阶段 1 · 入口卡 + 主流程改道（**本项目的胜负手**）

**背景**：不改这一条，后面全白建——AI 依然从弹弓开始。

**做什么**
1. 新增 `skillpack/skills/reverse-engineering/references/assault-entry.md`。
   它的第一屏（AI 动手前第一眼看到的）必须是**攻坚者五条**，不是判据表：
   搬运工与货物 / 工具输出是线索不是结论 / 优先查矛盾 / 宁可写卡住不许写完成 /
   调整路线是正常的。**判据表放后面，姿态放最前**——
   顺序反了就等于把「军训手册」当「作战条令」。
   然后才是分流器四问：

   - **Q0 这是哪类任务？**
     - A. 正常开发 / 维护 / 写代码 / 修 bug / 部署 / 写文档
       → 走既有路由与技能，**本卡到此为止，一行不必往下读**
     - B. 逆向 / 破解 / 分析一个**不是我写的**目标
       （PE/ELF/APK/IPA/.NET/固件/JS/Web客户端）→ 进 Q1-Q3
     - C. 已拿到源码，要读懂 / 改它 / 复刻它
       → 走 `code-audit` / 复刻路径（`DELIVERY-GOAL-2026-10-12.md`）
   - Q1 这是什么类型的目标？
   - Q2 它套了几层保护？（按定稿 §4 的 L0–L4 分层表逐层判）
   - Q3 用户要的成品是哪种？

   Q0=A 时对日常任务**零影响**。附一行指针：kernel `04-全能工程中枢` 已管六条线，
   本次不重写、不替代。

   卡里还要放三张**判据表**（不是步骤表）：
   - **分层判定顺序**：L0 容器 → L1 壳 → L2 混淆 → L3 自检 → L4 业务
   - **每层过层判据**（外部可观测）：
     | 层 | 过层判据 |
     |---|---|
     | L0 | 拿到目标架构真实可执行体（`file` 符合预期、能加载进 r2/Ghidra） |
     | L1 | IAT 从个位数涨到几十上百条；`.text` 熵从 >7.2 降到 <6.5；`iS` 无 rwx 节 |
     | L2 | 反编译出可读控制流（不再是星形跳转）；布尔表达式可化简 |
     | L3 | ScyllaHide 实测 peb/crdp/dbgport 三项归零；程序正常运行超 10s |
     | L4 | 关键函数反编译可读；算法/协议/格式能说出输入输出契约 |
   - **L4 分流**：本地算法→`license-keygen-03`；签名链→`license-keygen-04`；
     自引用→`license-keygen-07`；云端→`license-keygen-06`；
     网络协议→`protocol-reverse` 或 `web-protocol-reverse`；
     文件格式→`struct-reconstruction.md` / `reclass-reconstruction.md`；
     PRNG→`prng-caching.md`；加密→`crypto-algorithm-identification.md`

   必须写死的铁律（源自 `license-keygen/README.md`）：
   > **在 L1 里做的每一处修改，都要问一句「我改的是搬运工还是货物」。**
   > 判定点几乎从不在 L1。停在壳层打转 = 项目没推进。

2. 改 `skillpack/skills/reverse-engineering/SKILL.md`：ACTION REQUIRED 第 1 步（查经验卡）
   之后插入「读 assault-entry 完成四问」；`Problem-Solving Workflow` 的 8 步
   标题改为「triage 内部动作（不再作为主路径）」。
3. 修 `signal-to-tool-decision.md` §7：现在只写「参考 ../../patterns*.md」是**指空**，
   改为指向 `vmp-virtualization-analysis.md` 与 `vmp-devirtualization-toolchain.md`。

**动哪些文件**
- 新增 `skillpack/skills/reverse-engineering/references/assault-entry.md`
- 改 `skillpack/skills/reverse-engineering/SKILL.md`
- 改 `skillpack/skills/reverse-engineering/references/signal-to-tool-decision.md`

**验收判据**
- **入口卡第一屏是攻坚者五条**（五条齐备且在最前），判据表在其后——
  这条单独作为一项验收，顺序错即不通过
- 入口卡四问 + 三张判据表齐备，无缺项
- **关键验证（四例，各写一遍走查记录）**：
  1. VMP：`diec 报 VMProtect 3.x` + `.vmp0` 节 + 反编译全 dispatch loop
     → 落到 `vmp-virtualization-analysis.md` 的 VM entry 定位四步法，
     **中途不经过 strings/floss/angr 那五步**
  2. Themida：致闪退 → 先 `anti-debug-bypass.md` + ScyllaHide 专项段，再 dump
  3. 云端授权：`license-keygen-01` 断网实验判 D 类 → 落 `license-keygen-06`，不进算法还原
  4. 加固 APK：`apktool` 解不开 → 落 `apk-reverse` 的 dump dex 链
- **Q0 分流验证（本阶段最重要）**：给入口卡喂一个**非逆向任务**
  （例：「帮我给这个 Python 脚本加个 --verbose 参数」），
  Q0 必须判 A 并就此止步，不得出现 assault.md / layers / 工序字样
- `git diff reverse-engineering/SKILL.md` 显示「插入 + 改标注」，**8 步工作流仍在，无删除行**
- `check-fences.py` / `verify-doc-links.py` / `audit-doc-code.py` 全绿

**风险**：中。改 R0 主路径，必须复跑 `test-routing` 与 `verify-evolution`。
**红线：CTF 五件套降级不删除。**

### 阶段 2 · 滚动报告 `assault.md` + `-Preset assault`

**做什么**
1. 新增 `skillpack/skills/templates/assault.md`，字段照定稿 §4 全量：
   `## 0 状态行` / `## target` / `## survey` / `## layers` / `## routes` /
   `## functions` / `## findings` / `## unknowns` / `## diff_baseline` / `## out_of_delivery`
   **模板开头必须写一句：「这是字段清单，不是填写顺序」**——防止有人把它读成步骤表。
2. `case-init.ps1` / `case-init.sh` 加 `assault` 预设：与 rebuild 同档授权
   （owner-operated 本地样本 + offline），生成 assault.md 骨架 + 建 `diff/` 目录。

**动哪些文件**
- 新增 `skillpack/skills/templates/assault.md`
- 改 `skillpack/skills/scripts/case-init.ps1` + `case-init.sh`
- 改 `skillpack/skills/MASTER-ROUTING.md`（若列预设清单；**不动 routing.json**）

**验收判据**
- 不带 `-Preset assault` 时 `case-init` 产物与改前**逐字节一致**
  （方法：`git show <基线commit>:<脚本>` 取改前版本，干净副本上同参数同目录各跑三组对比）
- `-Preset assault` 生成 assault.md + diff/；scope.md deliverables 加 `assault: true`
- 错值预设仍 exit 2（bash）/ exit 1（PS），文案列出全部合法值
- `test-routing.ps1 -Quick` 65/65、`test-routing.sh` 205/205、`verify-routing-coherence.ps1` 全绿

**风险**：中低。两脚本必须同步。`test-bash-workflow.sh` 本机跑不了 →
如实记「本机未实测」，不许写成通过。

### 阶段 3 · 状态机规则 + 工序卡出口统一

**做什么**
1. 在 `assault-entry.md` 里写清**四状态机**（SURVEY / ROUTE / EXECUTE / VERIFY）：
   每个状态只定义「有效动作 / 出口条件 / 必须跳走的情况」三件事，
   **不规定顺序、不规定次数、不规定每状态必须几步**。
   配一张 `mermaid stateDiagram-v2`（定稿 §5 有，照搬）。
2. 给**已有**工序卡补统一出口段（**只追加，正文一行不改**）：
   `vmp-virtualization-analysis.md`、`vmp-devirtualization-toolchain.md`、
   `unpack-and-memory-dump.md`、`ollvm-deobfuscation.md`、`anti-debug-bypass.md`、
   `license-keygen/README.md`、`protocol-reverse/SKILL.md`、`struct-reconstruction.md`
   —— 每篇末尾加「出口：结论回填 `assault.md` 的哪张表」。
3. 把 `license-keygen/README.md` 的「先分类再进工序」从忠告升级为 ROUTE 状态的硬判据。

**动哪些文件**
- 改 `skillpack/skills/reverse-engineering/references/assault-entry.md`（+状态机）
- 改上述 8 份既有文档（只追加出口段）

**验收判据**
- 状态机四状态各有三要素（有效动作/出口条件/必须跳走），且**没有任何「下一步必须是X」的表述**
- 8 份工序卡出口段都在，`git diff` 只有新增行、0 删除
- 三类混合目标（VMP+云端 / Themida / 加固 APK）在卡上能各自走到 L4 分流
- 文档门禁三件套全绿

**风险**：低。纯文档追加。

### 阶段 4 · review_case 扩展审计 + 真目标端到端跑通

**做什么**（两件事合并成一个阶段，因为它们互为前提）

**A. `review_case.py` 检测到 `assault.md` 时加四项**：
1. `## 0 状态行` 非空且 current_state ∈ 四状态之一
2. `layers` 每行有状态+证据；`blocked` 行必须有原因/影响/替代
3. `functions` 每个 F-ID 有路线+状态，**状态不得高于证据**（复用既有判据）
4. `unknowns` 每项有「影响 / 下一步 / 是否阻塞」三列；
   **完成形态判定**：`deliverable` 指向的产物**真实存在于磁盘**，
   且 diff_baseline 有对照证据；否则只许「blocked + 具体原因」

同步：`case-review/tests/` 补 fixture；`case-review/SKILL.md` 说明新检查；
新增 `test-assault-audit-negctl.py` 并接进 `.github/workflows/ci.yml`
（照 `test-rebuild-audit-negctl.py` 与 ci.yml:466 的既有写法）。

**B. 真实硬目标端到端跑通**（**这是整个项目的最终验收，前面全是准备**）

选型标准（按优先级，**不许虚构目标**）：
1. 本机已有真实样本优先（不引入新下载、不碰未授权目标）
2. 保护层次丰富（至少两层，理想 L1 壳 + L4 授权，或 L2 混淆 + L4 协议）
3. 有可对照的原程序行为（能跑出基线）

候选池（开工时按本机实际选一个，把选择理由写进 §9 记录）：
- `work/` 下历史真实样本（kbconfig_probe.exe / kbgame_probe.exe / crypto_probe.exe 等自造样本）
- 系统自带真实程序（作目标类型演练）
- 用户另行指定的目标

流程：入口四问 → SURVEY → ROUTE → EXECUTE → VERIFY，需要时任意跳回。

**动哪些文件**
- 改 `skillpack/skills/case-review/scripts/review_case.py`
- 改 `skillpack/skills/case-review/tests/`、`case-review/SKILL.md`
- 新增 `skillpack/skills/scripts/test-assault-audit-negctl.py`
- 改 `.github/workflows/ci.yml`
- `work/assault-<target>/`（gitignored 运行时产物）
- `skillpack/field-journal/` 追加实战记录（脱敏）

**验收判据**

A 部分：
- 坏 fixture 每个都必须报错：状态行缺 / layers 缺证据 / functions 状态虚高 /
  unknowns 缺列 / **deliverable 指向的文件不存在却未标 blocked**
- 好 fixture 0 报错
- **回归底线**：不含 assault.md 的既有 case（`work/rebuild-sha256sum`、
  `skillpack/examples/ctf-demo`）三格式输出与改前**逐字一致**
- `python skillpack/skills/case-review/tests/test_review_case.py` 全绿
- `python skillpack/skills/scripts/test-assault-audit-negctl.py` 全绿（≥8 条）

B 部分（**全都要，缺一即未完成**）：
1. `assault.md` 全表填齐：状态行实时、layers 每行状态+证据、functions 每行路线+状态、
   findings 每条绑 Evidence、unknowns 每项三列
2. 同输入对照**真的跑过**：diff_baseline 逐行有「原程序结果 / 新实现结果 / 是否一致」
3. `python skillpack/skills/case-review/scripts/review_case.py work/assault-<target>
   --verify-hashes --strict` **PASS**
4. 成品真实存在：`deliverable` 指向的文件在盘上、可运行或可构建
5. **至少攻破两层保护**（L1+L4 或 L2+L4），有对应 Evidence
6. **报告里能看到至少一次真实的路线调整**（decision_delta：旧路线→新路线+理由）——
   这是铁律二的证明；一次都没调整过，说明这份报告是编的
7. 未达标项如实写「未达标 + 原因 + 已尝试 + 下一步」，**不许粉饰**
8. field-journal 记下本次真实卡点（这是下次的地图）
9. 沉淀至少 1 张经验卡，`python skillpack/skills/scripts/experience-card.py validate` 通过

**风险**：中。门禁脚本 + 真实目标双重风险。本仓有 6 个假绿前科 → **负控不是可选项**。
真实目标**必须允许失败**：发现工序有洞就如实记洞，回对应阶段补；
**不许为了让门禁绿而降判据**。

---

## 从 REA 学什么（三条，已克制到最小；**不 vendor、不进路由**）

REA（morluto/rea）是 npm 包 + MCP server，实测首发 2026-07-12、10 月前 10 天发 9 个版本，
vendor 两周即过期、pin 即锁死。**只学三条设计，不融代码**：

1. **「目标类型 → 第一个工具」独立路由层** → 就是本项目的 layers + routes 两张判据表
2. **「能力声明与安装物解耦」** → 进 `RULES.md` Output Quality 段一条：
   文档描述的能力 ≠ 本机装有的，以探测层实测为准
3. **「工具版本 + 样本哈希」双钉** → `assault.md` 的 `analysis_tool` + `upstream` 两字段

**不学**：把 12 类目标塞进一个 237 行 SKILL.md；没有授权门。

它的 DX-Ball 案例有一条可选进阶判据，**本次不作为强制**（避免又变成步骤）：
**字节级 replay**——用原作者那年代的编译器重编，与原文件逐字节匹配。
行为一致后想更强证明时可选用。

---

## 全程红线（每阶段开工前自检）

1. **不推送远端仓库**，只本地 commit。开工前 commit（`攻坚交付闭环 · 开工基线 2026-10-13`），
   完成后 commit（`攻坚交付闭环 · 完成`）。
2. **不碰 `kernel/`**。kernel 的破甲卡与六条工作流只读，不写。
3. **日常路径零变化**：不传 `-Preset assault` 时，case-init / review_case / 门禁行为与开工前一致。
4. **CTF 五件套降级不删除**：`reverse-engineering/SKILL.md` 的 8 步工作流必须仍在，
   只改标注、插入口。出现删除行即回退重做。
5. **不新增顶层技能、不改 `routing.json`**：新增全在 `references/` 与 `templates/` 层。
6. **不许为了让门禁绿而降判据**。查明目标真的打不下来，如实写 blocked + 原因，
   那是**有效交付**；假装打过才是失败。
7. **不许把攻坚工序套到非逆向任务上**：正常开发 / 维护 / 修 bug / 部署 / 文档，
   走既有路由与技能，零额外工序。kernel 的六条线**本次一行不动**。
8. **不许把状态机改成步骤表**：任何时刻都允许从任何状态跳任何状态。
   若发现自己在写「第 5 步必须是 X」，停下来重写成出口条件。

---

## 判据口径（全程有效）

- 未实跑不许写「已实测」。本机跑不了的必须写「本机未实测」
  （已知：`test-bash-workflow.sh`、bash 侧默认目录治理——本机 `python3` 是 WindowsApps 占位符）。
- 判据必须是外部可观测事实：文件真被创建、字节真被改、命令真回显预期输出。
  不许用「日志里出现我自己写的标记」（经验卡 `gate-self-must-prove-failure`）。
- 每一层过层判据用定稿 §4 的表，不用形容词。
- 同一方法连败两次 → 换方法，不许在原路线上加第三个补丁。
- **成品的定义是「可运行 + 可对照 + 可审计」，不是「分析报告很完整」。**
- **报告的任何一格都可以被推翻重写**，但推翻必须写 decision_delta，不许静默改。

---

## 每阶段必走的收尾动作

1. 跑该阶段「验收判据」列出的**每一条**，记录真实输出
2. 跑全量回归：`python skillpack/scripts/verify-evolution.py`（基线 10/10，开工前实测）
3. 在 `docs/ASSAULT-GOAL-2026-10-13.md` §9 追加该阶段完成记录（格式见该文件）
4. 本地 commit，message 写 `攻坚交付闭环 · 阶段N <名称>`
5. 才允许进入下一阶段

---

## 开工自检（第一回合必须逐条回答，再动手）

```
1. 基线确认：git status 是否干净？最近一次 commit hash 是什么？
2. 开工 commit：是否已按红线 1 提交开工基线？
3. 当前阶段：从阶段 1 开始（除非 docs/ASSAULT-GOAL-2026-10-13.md 的 §9 显示已有进度）。
4. 目的地对齐：我是否理解「终点只有一个——可运行、可验证、功能等价的成品」？
   本阶段产出是否让成品更近？（答不上来就是白做，停下来重想）
5. 任务分流：本阶段要做的改动，对「非逆向任务」是否零影响？验证方式是什么？
6. 日常路径保护：本阶段改动会不会影响不传 -Preset assault 时的行为？如何验证？
7. kernel 边界：本阶段清单里是否出现任何 kernel/ 路径？（出现即立刻移除）
8. CTF 五件套保护：本阶段是否出现对 reverse-engineering/SKILL.md 的删除行？（出现即回退）
9. 状态机保护：我是否在写「第 N 步必须是 X」？（是 → 改写成出口条件）
```

答案不齐不许开工。

---

## 完成的定义（六条同时满足才写「完成」）

1. 四个阶段验收判据全部达成，未达标项在定稿 §9 有如实记录
2. `verify-evolution.py` 10/10 全绿；`verify-routing-coherence.ps1` 全绿
3. 不传 `-Preset assault` 时，case-init / review_case / 门禁行为与开工前一致（有 diff 证据）
4. 含 assault.md 的 case 能被严格审查通过；不含 assault.md 的既有 case 输出逐字不变
5. **真目标端到端跑通**：状态行实时 + 全表填齐 + 同输入对照记录 + 成品在盘 +
   至少攻破两层保护 + strict 审查 PASS + **报告里至少一次真实路线调整**
6. **Q0 分流真的生效**：拿一个非逆向任务（如「给这个 Python 脚本加 --verbose 参数」）
   走一遍入口卡，Q0 判 A 并就此止步，全程不出现 assault.md / layers / 工序。
   写入定稿 §9 的记录里

**只有六条同时满足才写「完成」。缺任何一条，写「未完成 + 缺哪条 + 为什么 + 下一步」。**
**特别地：如果真实目标没打下来，本项目就是未完成**——如实写卡在哪一层、
哪道工序、已尝试什么、下一步是什么。
这个项目要治的病就是「分析一堆交不出成品」，不许自己犯。
