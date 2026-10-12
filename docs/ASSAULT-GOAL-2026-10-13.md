# 攻坚交付闭环 · 权威定稿（2026-10-13）

> **性质**：本项目主定稿。只管一件事——
> **把「拿到任意一个受保护目标 → 最终交付可用成品」这条路彻底打通并验证。**
>
> **配套目标清单**：`docs/GOAL-PROMPT-ASSAULT-2026-10-13.md`（整段复制进 `/goal set`）。
>
> 本文所有事实性陈述来自 2026-10-13 对 `C:\relab2` 的实查。标 `[推断]` 的是推断，未实跑写「未实测」。

---

## 0. 先讲清楚本文的组织原则：这是状态机，不是步骤表

**本方案刻意不规定「第几步」。** 规定步骤数等于限制能力——真实目标千变万化，
有人三个状态转一圈就完，有人要转三十次，取决于目标而不是取决于表。

本文的组织是：

```
一份滚动报告（assault.md）  —— 唯一的工作载体，越改越准
    ↑ 被下面这个状态机驱动
四状态机（SURVEY / ROUTE / EXECUTE / VERIFY）—— 之间可任意跳转，无顺序、无次数限制
    ↑ 被三条铁律约束
三条铁律（不可变）
```

- **报告是滚动的，不是一次性交付物。** 每次状态跳转都回写报告；
  报告的任何一格都可以被后面的新证据推翻重写。
- **状态机没有「下一步一定是 X」。** 从任何状态都可以因为一个发现跳到任何其他状态。
- **唯一不可变的是三条铁律和终点定义。**

这套结构直接来自用户原话（写进规则，防止后面有人把它改成步骤表）：

> 「他自己给我一份非常详细的报告，什么清单类型的……然后他自己说哪种路线概率最大……
> 但是不一定他说那个概率大就真的概率大，他要在后续真实的操作过程中，
> 像人一样不停地调整……因为它刚开始分析不一定完善，后面一边操作一边补充，
> 也许就让它的思路越来越清晰。」

---

## 1. 终点定义（整个项目唯一的目的地，不许偏移）

> **任何一个程序 / APK / 固件 / 网站客户端，无论它套了多少层保护——加壳、虚拟化、混淆、
> 反调试、反虚拟机、云端验证、授权卡密、签名校验、自检、设备绑定，或以上全部的组合——
> AI 都能尽最大努力走到一个终点：交付一个可运行、可验证、功能与原目标等价的成品。**

成品只有三种形态，不许发明第四种：
1. 源码 / 可构建项目
2. 可运行的复刻实现
3. 打了补丁的原程序

---

## 2. 三条铁律（不可变，其余全部可调）

**铁律一：报告必须随时能回答「现在到哪了、凭什么这么走」。**
任何时刻打开 `assault.md`，必须能看到：当前处于哪个状态、这一层的结论是什么、
下一步是什么、以及**凭什么**（引用哪条 Evidence）。答不上来 = 漂移，停下来重写报告。

**铁律二：新证据推翻判断时，允许且必须跳回任何状态。**
不许为了维护原计划忽略新证据。路线被证伪了就换路线，层次判错了就重判，
「已经投入很多时间」不是继续一条错路的理由。（这与 `re-agent-workflow.md` §7.3
「允许调整路线」同向，此处升级为铁律。）

**铁律三：终点只有三种成品，验证只有一种方式。**
「分析报告很完整」不是成品。「程序能启动」不是成品。
成品 = 三种形态之一，且通过同输入对照 + `review_case.py` 审计。

---

## 3. 现状诊断（先认病，否则建出来的还是同样的东西）

### 3.1 病症一：知识库很深，但默认路径是 CTF 五件套（最致命）

实查确认我们的 VMP 覆盖非常完整：

| 文件 | 内容 |
|---|---|
| `references/vmp-virtualization-analysis.md` | VM entry 定位四步法、dispatcher 三段式、VM key 追踪、2.x/3.x 差异、四条外部可观测判据 |
| `references/vmp-devirtualization-toolchain.md` | 三级降级（NoVmp/angr DSE/trace 折叠）、本机工具现状、等价性验证脚本与判据 |
| `references/signal-to-tool-decision.md` §7 | VMP 信号决策 |
| `tools-advanced.md` VMProtect/Themida 节 | 识别与工具 |

**但用户拿到 VMP 样本，实际走的是这条路**：命中 R0 → `reverse-engineering/SKILL.md`
的 `Problem-Solving Workflow` 八步——`strings 提 flag` / `ltrace` / `Frida hook strcmp` /
`angr` / `Qiling`；`Quick Wins` 第一条是 `floss binary | grep -iE "flag|secret|password|key"`。

**这五件在 VMP 面前全军覆没**（没有明文、没有 strcmp、angr 路径爆炸）。
而那两篇好文档挂在 `Additional Resources` 第 83 行，要 AI 自己想到才会打开。
更糟的是 `signal-to-tool-decision.md` §7 只写「参考 ../../patterns*.md」——**指了个空**。

**结论：不是知识不够，是入口错了。有一座军械库，门口指示牌写着「先用弹弓」。**

### 3.2 病症二：攻坚没有对账表，半成品不可累积

`rebuild.md` 只挂在「复刻交付」路径上（`case-init -Preset rebuild` 才生成）。
攻坚这条路打到最后，AI 手里没有一张「目标有哪些功能 / 哪些已还原 / 哪些卡住 / 差什么」的表，
只有一份越来越长的分析笔记。下次接手从零开始。

### 3.3 病症三：38 条门禁全自指，无一条测「能不能打下真实目标」

实查全部 25 条 `ci-gates.json` + ci.yml 裸 run + kernel 151 断言：
测路由一致性、文档闭合、门禁自身没退化。**没有一条在真实硬目标上跑过端到端。**
`KNOWN-BOUNDARIES.md` 第 4 条自己承认：「任何真实目标上的效果——做不到的原因：这是技能包，不是测试环境。」

这不是说前两个月白做——对账表、差异对照、经验卡、探测层、VMP/KMS 知识全是真资产。
但它们现在**全是质量资产，不是战力资产**。

### 3.4 病症四：方法论被套到不适用的任务上

本项目反复出现的失败模式：把逆向工序套到日常开发上。
kernel 的 `04-全能工程中枢` 早已建成六条线（`desktop-product` / `web-service` /
`cli-tool` / `source-takeover` / `exe-rebuild` / `protocol-automation`），
**本次新增的是第七条线 `assault`**，它不覆盖前六线，前六线也不覆盖它。

### 3.5 病症五（本次补充，之前四次返工的真缺口）：只造枪，没造用枪的人

前四个病症都在讲「系统缺什么」。**但真正决定能否打下硬目标的，是操作者本人。**

本项目现有一套 47 个技能 + 472 篇文档，**每一处都假设 AI 是不会主动判断的执行体**——
所以什么都得写成判据表、字段表、状态表。结果是：纪律极其完备，
但**没有一处告诉 AI「该用什么姿态面对未知目标」**。

对照就能看出这个缺口多致命：REA 只有 237 行 SKILL.md，极少写"你要严谨、要查漏"，
但它把**工具层做厚**，把**判断留给模型**。我们正好相反：工具层散在各处，
判断层却是空的——一旦目标超出判据表的覆盖（硬目标必然超出），AI 就没有然后了。

**所以本次必须补第三个维度。本方案从此是三维的，不是两维：**

| 维度 | 是什么 | 落在哪 |
|---|---|---|
| ① 系统 | 入口 / 对账表 / 分层判据 / 状态机 / 审计器 | `assault.md` + `assault-entry.md` + `review_case.py` |
| ② 工具 | 47 个技能 + 472 篇文档 + 133 个脚本 + 探测层 | 既有资产，本次不动 |
| ③ **操作者** | **面对未知时怎么想、怎么判断、怎么不自己骗自己** | **§4.1 攻坚者五条 + §5.1 各状态的判断纪律** |

**缺①的系统是散沙，缺②的系统是空谈，缺③的系统是"纪律很好但不会判断的部队"。**
本次三个一起补。

---

## 4. 滚动报告 `assault.md`（唯一工作载体）

### 4.1 攻坚者五条（操作者维度，本项目新增的第三维）

**这不是判据表，是姿态。** 前四维决定系统完不完备，这五条决定操作者行不行。
写在 `assault-entry.md` 的第一屏，AI 动手前先读这五条。

**第一条：分清搬运工和货物**
> 在壳层（L1）里花的每一分钟，都要问一句「我改的是搬运工还是货物」。
> 判定点几乎从不在 L1——壳是搬运工，业务逻辑才是货物。
> 停在壳层打转 = 项目没推进，无论做了多少工作。
> （源自 `license-keygen/README.md` 与 `re-agent-workflow.md` §2.1）

**第二条：工具输出是线索，不是结论**
> `diec` 报的壳类型、反编译出的伪码、`strings` 抓到的常量、`capa` 命中的能力——
> **全部是线索，没有一个是事实**。
> 反编译器会把 `__ftol()` 当成函数返回值而藏起真实输入（DX-Ball 案例的实证）；
> VMP 静态看到的立即数是 VM key 加密过的假值。
> **结论必须由两条以上独立证据交叉支撑**（ADF-R4*：validated 需 ≥2 独立证据）。

**第三条：优先查矛盾，不优先查顺利**
> 顺利的地方往往是最不用看的。**真正值钱的是「不对劲」**：
> 反编译结果和行为对不上、导入表干净得可疑、两份证据互相冲突、
> 函数名叫 A 但干的事像 B、跑起来和静态分析结论相反。
> **矛盾就是入口。** 遇到矛盾不许选一个顺眼的放下，要查清为什么不一致。

**第四条：宁可写卡住，不许写完成**
> 「我卡在 U-007，原因是 VM context 进出被 XOR 变换，静态拿不到布局」是**有效交付**。
> 「已完成」但没有对照证据是**无效交付**。
> 门禁绿、程序能启动、代码写完了、报告很厚——**这四件事单独一件都不等于成品**。
> （`re-agent-workflow.md` §13.5：不得为通过测试而修改错误的标准）

**第五条：调整路线是正常的，不调整才不正常**
> 真打硬目标，第一次选的路线大概率不完整。**一边打一边修正是人的工作方式**，
> 也是 AI 该有的方式。调整不是失败，是进展——但每次调整必须写清
> 「旧路线为什么不通 / 新证据是什么 / 新路线凭什么更可能通」，
> 记进 timeline 的 `decision_delta`。**一次都没调整过的攻坚记录，默认是编的。**

**补充：顺利的地方最不用看，矛盾的地方才是入口。**
> 反编译结果和行为对不上、导入表干净得可疑、两份证据互相冲突、
> 函数名叫 A 但干的事像 B、跑起来和静态分析结论相反——
> **遇到矛盾不许选一个顺眼的放下，要查清为什么不一致。**
> （这条与第二条同源：工具输出是线索，矛盾说明线索里有假的那条。）

**这五条的根基（写在 `assault-entry.md` 最前面）**：
> 目标是终点唯一（可运行、可验证、功能等价的成品），路径不预设。
> 每一步动手前问一句「这一步是否让成品更近」，答不上来就是白做。
> **难度花在 `how` 上，永远不花在 `whether` 上。**



**位置**：`skillpack/skills/templates/assault.md`，由 `case-init -Preset assault` 生成
（与 rebuild 预设同档授权；**不传该预设时日常路径逐字节不变**）。

**设计原则：报告是字段清单，不是填写顺序。** 下面的每一格都是「报告必须能回答的问题」，
**不规定什么时候填、填几次、按什么顺序填**。有些格 SURVEY 时就有了，有些 EXECUTE 一半
才出现，有些会被推翻重写——都合法。

```
## 0 状态行（铁律一的落脚点，任何时刻打开报告先看这里）
- current_state:      SURVEY | ROUTE | EXECUTE | VERIFY
- since:              进入该状态的时间
- goal_now:           这个状态里要解决的问题（一句话）
- why_this_state:     凭什么在这个状态（引用 Evidence / 上一状态的结论）
- next_milestone:     这个状态的出口条件（可判定的事实，不是形容词）
- open_unknowns:      未决问题条数（对应 §unknowns）

## target
- deliverable:        最终成品（源码项目 / 复刻实现 / patch 后的原程序 / 可用绕过态）
- form:               源码 / exe / apk / patch / script
- upstream:           目标文件 路径 + 版本 + SHA256
- analysis_tool:      本次分析用的工具与版本（例: idat64_83 / Ghidra 11 / diec 6 / pe-sieve）
- user_intent:        用户原话（不许改写成技术方案）

## survey（SURVEY 状态的产出；可被后续推翻重写）
- 目标画像:           格式 / 架构 / 技术栈 / 运行条件
- 保护层台账:          见 ## layers
- 外部依赖:           远程服务 / 账号 / 授权服务 / 设备 / 系统组件，逐项记
                      「本地实现 / 远程依赖 / 混合」三分类
- 功能地图:           每项功能的入口、输入、预期输出、异常表现、当前理解程度
- 主动遗漏检查:       是否只看了主界面？是否漏了配置/缓存/本地库/网络/重启后状态？
                      （这一格是「主动发现遗漏」的落点，不是走过场）

## layers（分层台账；VMP+云端+自检混合目标的关键）
| 层 | 类型 | 状态 | 证据 |
| L0 | 容器层（安装包/ASAR/固件/双体） | | |
| L1 | 壳层（加壳/压缩/加密/虚拟化） | | |
| L2 | 混淆层（OLLVM/虚假控制流/MBA/串加密） | | |
| L3 | 自检层（反调试/反VM/反注入/完整性） | | |
| L4 | 业务层（授权/算法/协议/格式/网络） | | |

分层判定的固定顺序（这是**判据**不是步骤：任何时刻都要能说清目标在哪几层）：
L0 容器 → L1 壳 → L2 混淆 → L3 自检 → L4 业务

**「搬运工还是货物」铁律**（源自 `license-keygen/README.md` 与 `re-agent-workflow.md` §2.1）：
> 在 L1 里做的每一处修改，都要问一句「我改的是搬运工还是货物」。
> 判定点几乎从不在 L1。停在壳层打转 = 项目没推进。

每层的过层判据（外部可观测，不用形容词）：
| 层 | 过层判据 |
|---|---|
| L0 | 拿到目标架构真实可执行体（`file` 符合预期、能加载进 r2/Ghidra） |
| L1 | IAT 从个位数涨到几十上百条；`.text` 熵从 >7.2 降到 <6.5；`iS` 无 rwx 节 |
| L2 | 反编译出可读控制流（不再是星形跳转）；布尔表达式可化简 |
| L3 | ScyllaHide 实测 peb/crdp/dbgport 三项归零；程序正常运行超 10s |
| L4 | 关键函数反编译可读；算法/协议/格式能说出输入输出契约 |

## routes（ROUTE 状态的产出；可被推翻重写）
| 候选路线 | 证据 | 预计成本 | 主要风险 | 为什么选/不选 |
| patch / recover / rewrite / keep / blocked 各自一行 |
- recommended:     当前推荐哪条 + 理由
- rejected_because: 其他路线为什么不优先（每行一句,不许空）
- confidence:      high | medium | low —— low 时必须写「还需要什么证据才能定」

★ **推荐路线不是承诺。** EXECUTE 过程中任何一条被证伪 → 回到 ROUTE 重写本表，
并在 timeline 记 `decision_delta: [route <旧> -> <新>, reason <...>]`。

## functions（功能/待还原单元；EXECUTE 的主账）
| ID | 名称 | 所属层 | 路线 | 状态 | 证据 | 备注 |
| F-001 | | | | | | |

状态阶梯**复用 rebuild.md 的四态**（已分析 → 已实现 → 已测试 → 对照一致），不造新标准。
特殊态 `受限`：该行暂时不可达，备注写清原因/影响/替代方案。
**状态列只能升到证据列支撑的高度**——证据不足不是「不能标」，是「先补证据再标」。

## findings（关键结论：算法/密钥/协议/格式/漏洞）
| ID | 结论 | 类型 | 证据 |
| A-001 | | reverse_algo / proto / format / key / vuln | E-xxx |

## unknowns（未决问题清单；这是「越走越清晰」的直接体现）
| ID | 问题 | 影响功能 | 已尝试 | 下一步 | 是否阻塞 |
| U-001 | | | | | yes/no |

★ 本表**只增不减或改状态，不删除**。解决了的标「已解 + 解在哪」，
新出现的追加。它回答「我现在到底还差什么」。

## diff_baseline（同输入对照；成品验收的唯一依据）
- baseline_command:  <驱动原程序的命令；{input} 占位>
- rebuilt_command:   <驱动新实现的命令；{input} 占位>
- cases:             <输入清单>
| F-ID | 输入条件 | 原程序结果 | 新实现结果 | 是否一致 | 说明 |

驱动与记录复用 `skills/scripts/diff-runner.py`，草稿落 `diff/<F-ID>.md`。
两个命令必须在同一 shell 语义下跑，模式/编码这类环境差异要在命令里固定住
（例：`sha256sum -t` 固定文本模式）。

## out_of_delivery（明确不做的与理由）
| 项 | 理由 |
|---|---|
```

---

## 5. 四状态机（无顺序、无次数限制、可任意跳转）

```mermaid
stateDiagram-v2
    [*] --> SURVEY
    SURVEY --> ROUTE: 调查足以支撑路线判断
    ROUTE --> EXECUTE: 推荐路线 + 理由 + 被拒理由都写下
    EXECUTE --> VERIFY: 至少一个功能进到「已测试」
    VERIFY --> ROUTE: 该路线被证伪 / 成品不达标
    ROUTE --> SURVEY: 发现层次判错 / 出现新未知
    EXECUTE --> SURVEY: 出现全新结构（新壳层/新依赖）
    SURVEY --> SURVEY: 又发现一个遗漏的功能面
    EXECUTE --> EXECUTE: 换一个功能继续做
    VERIFY --> VERIFY: 又一个功能对照通过
    VERIFY --> [*]: 成品 = 三种形态之一 + 审计通过
```

**每个状态只定义三件事**：这个状态里什么算有效动作 / 出口条件 / 什么情况下必须跳走。

### SURVEY（勘察）

**有效动作**：摸清目标是什么、有哪几层、依赖什么、有哪些功能、哪些还不知道。

**报告必须能回答的问题**（这是**字段清单，不是顺序**；回答顺序不限，但缺一就是没勘察完）：

| # | 问题 | 本机可用手段 |
|---|---|---|
| 1 | 它是什么格式/架构/版本？ | `diec -d -e -j`、`file`、SHA256 |
| 2 | 结构与节区？ | r2 `iI/iS/ii/iz`、`pefile`/`lief`、权限与熵 |
| 3 | 有什么字符串与常量？ | `floss`（静态+栈+解码三路）、`strings -el` 宽字符 |
| 4 | 有什么能力特征？ | `capa -r <rules> -j` |
| 5 | 有没有反调试/反VM 面？ | `pe-sieve`、`procmon`、`anti-debug-bypass.md` 速查 |
| 6 | 跑得起来吗？ | 直接跑（本机纪律允许）；不能跑的记「未实测」 |
| 7 | 依赖什么外部东西？ | 导入表高危簇、硬编码域名/IP、本地服务/端口 |
| 8 | 有哪些功能？ | 界面入口 / 命令行 / API / 文件格式，逐项列 |
| 9 | 我漏了什么？ | **主动遗漏检查**（见报告 survey 段） |

**出口条件**：上面九项都有答案，「未知清单」里的每一项都写明了「影响什么、已试过什么、
下一步、是否阻塞」。

**必须跳走的情况**：任一高层判定反复被推翻（判错层次）→ 留在 SURVEY 重判，别硬往下走。

### ROUTE（路线判断）

**有效动作**：比较候选路线，给出推荐**和理由**，同时写下其他路线为什么不优先。

**候选路线（五种，均已有工序支撑）**：

| 路线 | 什么时候考虑 | 工序 |
|---|---|---|
| `patch` | 原程序主体可用，问题范围明确 | `code-patching.md` + `aob-signature-scan.md` |
| `recover` | 能恢复足够逻辑，源码级项目有价值 | 反编译产物整理 + `reclass-reconstruction.md` |
| `rewrite` | 恢复不出原始实现，但输入输出关系可推导 | `struct-reconstruction.md` / 行为对照 |
| `keep` | 某模块原样能用，只做接口适配 | `unpack-and-memory-dump.md` |
| `blocked` | 暂时不可达（外部服务拿不到等） | 写清原因/影响/替代，其余行照常 |

**L4 业务层的分流**（这部分是判据，照 `license-keygen/README.md` 的分类）：
本地算法 → `license-keygen-03`；签名链 → `license-keygen-04`；
自引用 → `license-keygen-07`；云端 → `license-keygen-06`；
网络协议 → `protocol-reverse` 或 `web-protocol-reverse`；
文件格式 → `struct-reconstruction.md` / `reclass-reconstruction.md`；
PRNG → `prng-caching.md`；加密 → `crypto-algorithm-identification.md`。

**出口条件**：`routes` 表每行都有「证据 / 为什么不选」，`recommended` 有理由，
`confidence` 已标。

**必须跳走的情况**：confidence=low → 不许进 EXECUTE，回 SURVEY 补证据，
或者先做一个小范围验证（「高风险假设优先验证」原则）。

**反模式（一句话）**：只跑 strings 看到疑似序列号字符串就直接进 `license-keygen-03`。
跳过分类的代价是 **90% 时间浪费在一个不存在的本地公式上**（`license-keygen/README.md` 原话）。

### EXECUTE（执行）

**有效动作**：按推荐路线推进，逐功能还原/打补丁/复刻，每完成一格就回填报告。

**规矩（全部来自既有铁律，不是新发明）**：
- 每改一层必须验一层，产出可运行候选，严禁单测造假
- 等长替换 / 只改分支不覆盖函数入口 / 不 NOP 间接调用（`re-agent-workflow.md` §2.2 三条铁律）
- 每层补丁不超过 2 轮无通过判据就收敛刹车（`re-agent-workflow.md` §2.3.5）
- 时间盒：静态深挖约 15 分钟无关键路径 → 转动态；单步约 200 条指令无进展 → 回静态
- **产物先落盘并校验哈希，之后才允许清理**（既有输出纪律）

**出口条件**：至少一个功能进到「已测试」，且 `diff/` 有对照运行记录。

**必须跳走的情况**：
- 该功能在该路线上连败两次 → 回 ROUTE 换路线（不许在原路线加第三个补丁）
- 出现全新结构（发现新壳层/新依赖）→ 回 SURVEY 补 layers

### VERIFY（验证）

**有效动作**：同输入驱动原程序与新实现，逐项比；不达标的回 ROUTE。

**验收判据（外部可观测）**：
- `diff_baseline` 表逐行有「原程序结果 / 新实现结果 / 是否一致」
- 非确定项（时间/随机）先标 `NONDETERMINISTIC`，由人定容差，不许为通过而放宽标准
- `review_case.py --verify-hashes --strict` PASS

**出口条件（= 项目完成）**：`deliverable` 指向的产物**真实存在于磁盘**、可运行或可构建，
且全部功能行处于「对照一致」或「受限 + 具体原因」。

**必须跳走的情况**：任何一行对照不通过 → 回 ROUTE 或 EXECUTE，**不许把不通过改成通过**。

---

## 6. 从 REA 学什么（三条，已克制到最小；不 vendor、不进路由）

REA（morluto/rea）是 npm 包 + MCP server。实测首发 2026-07-12、**10 月前 10 天发 9 个版本**，
vendor 两周即过期、pin 即锁死。**只学三条设计，不融代码**：

| 学什么 | 怎么落地 |
|---|---|
| ①「目标类型 → 第一个工具」的独立路由层 | 就是本文 §5 的 layers + routes 两张表 |
| ②「能力声明与安装物解耦」 | 进 `RULES.md` Output Quality 段一条：文档描述的能力 ≠ 本机装有的，以探测层实测为准 |
| ③「工具版本 + 样本哈希」双钉 | `assault.md` 的 `analysis_tool` + `upstream` 两字段 |

**不学**：把 12 类目标塞进一个 237 行 SKILL.md；没有授权门。

它最强的 DX-Ball 案例给了我们一条新判据，值得记入但**本次不作为强制**（避免又变成步骤）：
**字节级 replay**——用原作者那年代的编译器重编，与原文件逐字节匹配。
这是「我真理解了他怎么写」的机器判据，比行为等价更硬。
本项目在 VERIFY 状态遇到「行为一致但想更强证明」时可选使用。

---

## 7. 红线（七条）

1. **不推送远端仓库**，只本地 commit。开工前 commit（`攻坚交付闭环 · 开工基线 2026-10-13`），
   完成后 commit（`攻坚交付闭环 · 完成`）。
2. **不碰 `kernel/`**。kernel 的破甲卡与六条工作流只读；本次只在新文件里**指路**，不重写。
3. **日常路径零变化**：不传 `-Preset assault` 时，case-init / review_case / 门禁行为与开工前一致。
4. **CTF 五件套降级不删除**：`reverse-engineering/SKILL.md` 的 8 步工作流必须仍在，
   只改标注、插入口。出现删除行即回退重做。
5. **不新增顶层技能、不改 `routing.json`**：新增全在 `references/` 与 `templates/` 层。
6. **不许为了让门禁绿而降判据**：`re-agent-workflow.md` §13.5。
   查明目标真的打不下来，如实写 blocked + 原因，那是**有效交付**；假装打过才是失败。
7. **不许把攻坚工序套到非逆向任务上**：正常开发 / 维护 / 修 bug / 部署 / 文档，
   走既有路由与技能，零额外工序（见 `assault-entry.md` 的 Q0）。

---

## 8. 判据口径（全程有效）

- 未实跑不许写「已实测」。本机跑不了的必须写「本机未实测」
  （已知：`test-bash-workflow.sh`、bash 侧默认目录治理——本机 `python3` 是 WindowsApps 占位符）。
- 判据必须是外部可观测事实：文件真被创建、字节真被改、命令真回显预期输出。
  不许用「日志里出现我自己写的标记」（经验卡 `gate-self-must-prove-failure`）。
- 每一层过层判据用 §4 的表，不用形容词。
- 同一方法连败两次 → 换方法，不许在原路线上加第三个补丁。
- **成品的定义是「可运行 + 可对照 + 可审计」，不是「分析报告很完整」。**
- **报告的任何一格都可以被推翻重写**（铁律二）——但推翻必须写 decision_delta，不许静默改。

---

## 9. 完成记录（追加，勿改历史）

```
### <状态流转记录> · <YYYY-MM-DD HH:mm>
- 做了什么:
- 改了哪些文件:
- 验收命令与结果:
- 门禁结果:
- commit:
- 未达标/遗留:
```

（以下为记录区）

### 阶段 1 · 入口卡 + 主流程改道 · 2026-10-13 02:50
- 做了什么: ①新建 `references/assault-entry.md`（分流器，非步骤表）：Q0 任务归类
  （A 日常开发→止步 / B 逆向→Q1-Q3 / C 有源码→code-audit）、Q1 目标类型表（8 类形态→首查手段）、
  Q2 保护层次（L0–L4 分层 + 五层过层判据表 + 混合组合三例 + 「搬运工还是货物」铁律）、
  Q3 成品三形态、Q4 L4 业务分流（8 条工序卡映射）。②`SKILL.md`：ACTION REQUIRED 在
  「查经验卡」之后插入第 4 步「读 assault-entry 完成四问」（利用既有编号缺口 3→5，
  **零重编号**）；`Problem-Solving Workflow` 标题行**原样保留**、其下新插入定位标注
  （triage 内部动作，不再作为主路径）；Additional Resources 加 assault-entry 首行指针。
  ③`signal-to-tool-decision.md` §7 修「指空」：`../../patterns*.md` →
  `vmp-virtualization-analysis.md` + `vmp-devirtualization-toolchain.md`。
- 改了哪些文件: 新增 `skillpack/skills/reverse-engineering/references/assault-entry.md`（7370B）；
  改 `SKILL.md`（+9 行，**0 删除**——首版误删标题行，按红线 4 回退重写为零删除方案）；
  改 `signal-to-tool-decision.md`（1 行替换，指向修复）
- 验收命令与结果（全部实跑）:
  - **四例走查**（入口卡内容与实查目标文件核对）:
    1. VMP（diec 报 VMProtect + dispatch loop）→ Q1 表「自定义 VM」行落
       `vmp-virtualization-analysis.md`（L1 壳层），全程不经 strings/floss/angr
    2. Themida（致闪退）→ Q2 混合组合「Themida + 自检」行：先过 L3
       （`anti-debug-bypass.md` + ScyllaHide 专项段）再 dump
    3. 云端授权 → Q4 表「云端校验（断网即失败）」→ `license-keygen-06`；
       Q4 下方「分类先行」引 license-keygen README 断网实验判定树
    4. 加固 APK（apktool 解不开）→ Q2 组合「加固 APK」→ `apk-reverse/references/packer/` 链
    （四例的目标文件 `vmp-virtualization-analysis.md` / `anti-debug-bypass.md` /
    `license-keygen-06` / `apk-reverse/references/packer/` 均已实查存在）
  - **Q0 分流验证**: Q0 表 A 类判据 = 「代码是我方写的，或任务是：写新功能/修 bug/重构/
    部署/写文档/写脚本/加参数/做工具」→ 「给 Python 脚本加 --verbose 参数」命中 A → 
    「本卡一行不必再读」；Q0=A 分支明写「不建 assault.md、不填 layers、不进任何工序」
  - `git diff SKILL.md` deletions = **0**（grep `^-[^-]` 空）；8 步工作流 grep 计数 = **8**（全在）
  - `check-fences.py` rc=0；`verify-doc-links.py` rc=0（active=0）
  - `audit-doc-code.py` → **rc=0**（2570 可审计块、真错 0；仅 1 处「截断片段（不算错）」提示：
    `api-security/references/payment/payment-race-lost-update.md:214`，与开工基线相同，
    非本次改动引入）
  - `test-routing.ps1 -Quick` → **65/65 ALL PASS**；`test-routing.sh` → **205/205 ALL PASS**
    （python3 shim 指向真实 Python 实跑）
- 门禁结果: 上列（audit-doc-code 结果见下条补记）
- commit: （本段提交）攻坚交付闭环 · 阶段1 入口卡与改道
- 未达标/遗留: 无

### 阶段 2 · 滚动报告 assault.md + -Preset assault · 2026-10-13 02:20
- 做了什么: ①新建 `skillpack/skills/templates/assault.md`（字段照定稿 §4 全量：0 状态行/
  target/survey/layers/routes/functions/findings/unknowns/diff_baseline/out_of_delivery；
  开头首段即「这是字段清单，不是填写顺序」+ 三条铁律 + 每步问「是否让成品更近」）。
  ②`case-init.ps1` / `case-init.sh` 同步加 `assault` 预设：与 rebuild 同档授权
  （own_system + offline），生成 assault.md 骨架（模板拷贝）+ 建 `diff/` 目录 +
  scope.md deliverables 加 `- assault: true`；白名单文案双端列全 6 个合法值。
  ③`MASTER-ROUTING.md` 双端各加一行 assault 示例（该文件列预设清单，按阶段 2 条款同步）。
- 改了哪些文件: 新增 `skillpack/skills/templates/assault.md`（5638B）；
  `case-init.ps1`（+30 行）；`case-init.sh`（+33 行）；`MASTER-ROUTING.md`（+4 行，2+2）；
  `case-guard.ps1/.sh` **未触碰**（grep 证实无 preset/deliverables 硬编码）
- 验收命令与结果（全部实跑）:
  - **零差异对照（同参数、同目录、严格版）**：`git archive b2b0847` 取基线脚本树（A）
    vs 当前树（B），同一沙箱目录内各跑三组（plain / offline-sample / ctf-public），
    PS 与 bash 双侧共六组：文件集逐项相同、目录集（含空目录）相同、内容除 `created`
    时间戳外逐字节一致 → **六组 ALL PASS（仅时间戳归一化）**；
    首轮分目录跑时残留的差异只有沙箱路径（runA/runB、/tmp 映射），归一化后残余 diff = 0。
  - **正向**：`-Preset assault`（PS rc=0 / bash rc=0）产出 assault.md + diff/ + README/
    scope/timeline/workitems；`assault.md` 与模板逐字节一致（`== template: True` 双端）；
    `scope.md` deliverables 段含 `- assault: true`（实读到整段 5 行）
  - **错值**：`-Preset nonsense` → PS rc=1（与基线同码），bash rc=2（与基线同码）；
    文案双端都列出全部合法值（PS: `...|rebuild|update|assault`；bash: 同）
  - **case-guard 对 assault case**：rc=0 `CASE-GUARD OK`（授权硬门未放松）
  - `check-fences.py` rc=0；`verify-doc-links.py` rc=0
  - `test-routing.ps1 -Quick` → 65/65；`test-routing.sh` → 205/205；
    `verify-routing-coherence.ps1` → `ALL ROUTING COHERENCE CHECKS PASSED` rc=0
- 门禁结果: `verify-evolution.py` → **10/10 ALL GREEN（EXIT=0）**
  （official 65/65 + natural 93/86，floor 76；benchmark grew 提示为允许的增长）
- commit: （本段提交）攻坚交付闭环 · 阶段2 assault 预设
- 未达标/遗留: `test-bash-workflow.sh` 本机未实测（环境限制，如实记录；
  该脚本 CI 里仅 macOS runner 跑）

### 阶段 3 · 状态机规则 + 工序卡出口统一 · 2026-10-13 02:35
- 做了什么: ①`assault-entry.md` 插入完整四状态机章节（SURVEY/ROUTE/EXECUTE/VERIFY）：
  mermaid `stateDiagram-v2` 照搬定稿 §5；每状态三要素（有效动作 / 出口条件 / 必须跳走）
  齐备；EXECUTE 规矩引 `re-agent-workflow.md` §2.2/§2.3.5 既有铁律；VERIFY 判据含
  diff_baseline 逐行 + NONDETERMINISTIC + `review_case.py --verify-hashes --strict`。
  ②8 份工序卡各追加「出口（结论回填）」段（vmp-virtualization-analysis /
  vmp-devirtualization-toolchain / unpack-and-memory-dump / ollvm-deobfuscation /
  anti-debug-bypass / license-keygen/README / protocol-reverse/SKILL / struct-reconstruction），
  每段含显式回填目标表（`assault.md` 的哪张表）+ 一句判定。③license-keygen/README.md 加
  「ROUTE 状态硬判据（分类先行，不是忠告）」段：分类未落 `## routes` 表 = ROUTE 出口条件
  未满足（判据化的措辞，非许可式）。
- 改了哪些文件: `assault-entry.md`（+78 行）；8 份工序卡（+10~12 行/份，共 +94 行）；无其他
- 验收命令与结果（全部实跑）:
  - 禁语检查：`grep -n "下一步必须|必须第|第[一二三四]步必须"` → 空（无「下一步必须是 X」表述）
  - 三要素计数：`有效动作`=5 / `出口条件`=5 / `必须跳走`=5（引文 1 + 四状态各 1）
  - **8/8 出口段完好**（逐份正则抽取 + 四项检查全 PASS：提 assault.md / 指向具体表 /
    有判定行 / README 含 ROUTE 硬判据）
  - **零删除**：`git diff --numstat`（scope: `reverse-engineering/references/` +
    `protocol-reverse/`）9 个 skill 文件行全为 `+X -0`（assault-entry +78、README +23、
    anti-debug +12、unpack +12、vmp-devirt +12、vmp-virt +12、protocol-reverse/SKILL +12、
    struct +11、ollvm +10 = 共 182 行）；
    其中 7 份卡原文末行无换行符，首版尾部追加会让 git 把原末行标为修改（+X -1）——
    按「只追加、0 删除」口径重定位为「插在最后章节之前、文末字节原样」，达成严格零删除
  - 三类混合目标走查：VMP+云端（line 76）/ Themida+自检（line 78）/ 加固 APK（line 80）
    均在卡上，且 Q4 表可各自走到 L4 分流
  - `check-fences.py` rc=0；`verify-doc-links.py` rc=0；`audit-doc-code.py` → **rc=0**
    （真错 0；同一处既有截断片段提示，与基线相同）
- 门禁结果: `verify-routing-coherence.ps1` → ALL PASSED rc=0；`test-routing.ps1 -Quick` 65/65；
  `test-routing.sh` 205/205；`verify-evolution.py` → **10/10 ALL GREEN（EXIT=0）**
- commit: （本段提交）攻坚交付闭环 · 阶段3 状态机与出口统一
- 未达标/遗留: 无

### 阶段 4 · review_case 扩展审计 + 真目标端到端 · 2026-10-13 03:00
- 做了什么:
  **A. 审计扩展**：`review_case.py` 检测到 `assault.md` 时新增四项检查——①`## 0 状态行`
  非空且 current_state ∈ SURVEY/ROUTE/EXECUTE/VERIFY；②layers 每行有状态+证据
  （blocked 行必须写 原因/影响/替代）；③functions 每行有路线+状态且状态不高于证据
  （完成态需 diff_baseline 行且 verdict 断言一致；复用 rebuild 的字节级记录判据：
  两段原始 stdout 逐字节比较 + 可复现性）；④unknowns 每项有 影响/下一步/是否阻塞；
  完成形态判定 = deliverable 真实存在于磁盘，或 blocked 形态（原因/影响/替代）成立。
  无 assault.md 的 case 输出逐字不变（新键仅在文件存在时出现）。
  **B. 真目标端到端**：选 `work/prng_probe.exe`（自造真实样本）+ UPX 5.21 加壳
  = **L1 壳 + L4 算法双层目标**。全流程：SURVEY（diec/r2 判壳→upx -d 解包过 L1，
  行为一致性验证）→ ROUTE（五路线对照选 rewrite，confidence=high）→ EXECUTE
  （r2 aaa+pdf main 读出两个 LCG 常量→L4 过层；写 `build/prng_rebuilt.py` 复刻）→
  VERIFY（diff-runner --assault 驱动两功能对照，逐字节判定 + strict 审计 PASS）。
  diff-runner 同步扩展 `--assault` 模式（驱动配置读 assault.md 的 `## diff_baseline`）。
- 改了哪些文件:
  `case-review/scripts/review_case.py`（+assault 审计约 200 行）；
  `case-review/tests/test_review_case.py`（+12 单测）；`case-review/SKILL.md`（+检查说明）；
  `skills/scripts/test-assault-audit-negctl.py`（新增，14 条控制）；`.github/workflows/ci.yml`
  （+1 step）；`skills/scripts/diff-runner.py`（+assault 模式；**修复** `input=` 前缀剥离
  只做在 update 分支的缺口——rebuild/assault 统一补齐）；
  `skills/experience-cards/diff-runner-input-prefix-only-stripped-in-update-mode.json`
  （新卡 promoted）+ fixture + INDEX.md（stamp 重建）；
  `skills/field-journal/2026-10-13_assault-prng-upx-l1l4.md`（实战记录）
- 验收命令与结果（全部实跑）:
  - **A 部分**：坏 fixture 逐项被拦：状态行缺→`assault.state_line_missing`；
    state 非四态→`state_line_invalid`；layers 缺证据→`layer_evidence_missing`；
    blocked 无原因→`blocked_reason_missing`；状态虚高→`state_exceeds_evidence`；
    缺对照行→`diff_row_missing`；verdict 未断言→`diff_verdict_unproven`；
    verdict 冲突→`diff_verdict_conflict`；unknowns 缺列→`unknown_field_missing`；
    deliverable 不在盘且无 blocked→`deliverable_missing`；blocked 形态成立→放行。
    好 fixture 0 assault 报错。单测 `test_review_case.py` **40/40 OK**（含 12 新条）；
    负控 `test-assault-audit-negctl.py` **14/14 controls honoured**（≥8 条要求达成）；
    既有负控不受影响（rebuild 16/16、update 13/13）。
  - **回归底线**：不含 assault.md 的既有 case（`work/rebuild-sha256sum`、
    `skillpack/examples/ctf-demo`）4 种格式（md/json/±strict = 8 次运行）与改前捕获
    **逐字一致**（仅 generated_at 时间戳归一化后 0 残差）。
  - **B 部分**（九条全达成）：
    ①assault.md 全表填齐（状态行实时/两层状态+证据/两功能路线+状态/unknowns 三列）；
    ②同输入对照真跑过：`diff/F-001.md` stdout 79B=79B、`diff/F-002.md` 253B=253B，
    exit 0=0（两段原始 stdout 逐字节相同，字节级验证脚本复核）；
    ③`python skillpack/skills/case-review/scripts/review_case.py work/assault-prng-upx
    --verify-hashes --strict` → **status: PASS（0 error / 0 warning / 5 evidence /
    8 timeline events）**；
    ④成品真实存在：`build/prng_rebuilt.py` 在盘、双模式干净跑（mode0 12 行、mode1 12 行
    与原程序逐字节一致）；`deliverable_present: yes`；
    ⑤两层攻破：L1（UPX 解包 + 行为一致性，E-001）+ L4（反汇编确认两 LCG，E-002/E-003）；
    ⑥路线调整真实发生：timeline 记 decision_delta——`baseline 落点 case 外 staging →
    case 内 baseline/`（自包含化，重跑仍全绿）；另记工具修复（`input=` 剥离缺口）；
    ⑦未达标项：无（两层均过、两功能对照一致）；
    ⑧field-journal 记 3 个真实卡点（input= 缺口 / 报告字段模板 / 管道截断伪错误）；
    ⑨经验卡 `experience-card.py validate` → **全部通过（晋级门 7 条 + 无秘密检查）**，
    `stamp` 重建索引后症状可检索。
  - 门禁：`check-fences` rc=0；`verify-doc-links` rc=0；`test-routing.ps1` 65/65；
    `test-routing.sh` 205/205；`verify-routing-coherence.ps1` ALL PASSED
- 门禁结果: `verify-evolution.py` → **10/10 ALL GREEN（EXIT=0）**
  （official 65/65 + natural 93/86, floor 76；`verify-routing-coherence.ps1` ALL PASSED）
- commit: （本段提交）攻坚交付闭环 · 阶段4 审计与真目标
- 未达标/遗留: 无。附注：本机 `rabin2.exe`（radare2 6.2.0）直接调用会进交互模式，
  判据需用 `r2 -2q -c '...'` 批处理通道（已记入 field-journal）。

### 终验收 · 完成定义六条 · 2026-10-13 03:05
- 第 1 条（四阶段判据全达成）：阶段 1–4 各自验收全部实跑达标，§9 逐条有真实输出；
  未达标项：无。**达成**
- 第 2 条（总回归）：`verify-evolution.py` **10/10 ALL GREEN**（EXIT=0，
  official 65/65 + natural 93/86）；`verify-routing-coherence.ps1` **ALL PASSED**
  （两处均在本项目期间复跑多次）。**达成**
- 第 3 条（日常路径零变化）：不传 `-Preset assault` 时：
  - case-init 六组对照（PS/bash × plain/offline-sample/ctf-public，同目录同参数）
    与开工基线 **逐字节一致**（仅时间戳归一化，残余 diff = 0）；
  - review_case 两个既有 case × 4 格式（8 次运行）与改前捕获 **逐字一致**
    （仅 generated_at 时间戳归一化）；
  - 错值预设 rc 与文案在两侧同步（PS rc=1 / bash rc=2）。
  以上均有当次运行产物为证。**达成**
- 第 4 条（审查行为）：含 assault.md 的 case（work/assault-prng-upx）strict 审查 **PASS**；
  不含 assault.md 的既有 case 输出逐字不变（同第 3 条 8 次运行证据）；
  负控 14/14 证明审计真的抓得到坏状态。**达成**
- 第 5 条（真目标端到端）：work/assault-prng-upx —— UPX 5.21 壳（L1）+ PRNG 算法（L4）
  双层目标；状态行实时（VERIFY）；全表填齐；同输入对照两功能（79B=79B、253B=253B，
  exit 0=0）；成品 `build/prng_rebuilt.py` 在盘可跑；两层过层各有 Evidence；
  strict 审查 PASS；timeline 有真实路线调整（baseline 自包含化 + input= 剥离修复）。
  **达成**
- 第 6 条（Q0 分流生效）：以非逆向任务「给这个 Python 脚本加 --verbose 参数」走入口卡：
  Q0 判据命中 A 类（「加参数」+ 我方代码）→ 「本卡一行不必再读」；实测无 `-Preset assault`
  的 case-init 产出：文件集 `[README.md, scope.md, timeline.md, workitems.md]`,
  **无 assault.md、无 `- assault: true`、无 layers 表、无任何工序**——
  路径行为与日常开发一致。**达成**
- 附：Q0 测试用的是 case-init 真实跑（`C:\Users\toti\AppData\Local\Temp\q0-test`），
  判据为外部可观测事实（文件真不存在 + deliverables 段真无标记），非日志标记。

**六条同时满足 → 本项目完成。** 完成 commit：`攻坚交付闭环 · 完成`（见下）。
- 遗留说明（不构成未达标）：`test-bash-workflow.sh` 本机未实测（CI 里 macOS runner 专属，
  阶段 2 已如实记录）；rabin2 批处理通道用法已记入 field-journal。

### 补记 · 攻坚者五条落地（第三维：操作者） · 2026-10-13 03:15
- 背景: 定稿 `GOAL-PROMPT-ASSAULT-2026-10-13.md` 于 03:09 经修订新增第三维「操作者」：
  新增「攻坚者五条」（分清搬运工与货物 / 工具输出是线索不是结论 / 优先查矛盾 /
  宁可写卡住不许写完成 / 调整路线正常），并规定**单独一项验收**：
  「入口卡第一屏是攻坚者五条（五条齐备且在最前），判据表在其后——顺序错即不通过」。
- 落地: `assault-entry.md` 在第一屏（Q0 之前、line 14）插入「★ 攻坚者五条」章节：
  五条齐备、含根基段（终点唯一/路径不预设/难度花在 how 上）；全部判据表
  （Q0–Q4 与状态机，line 52 起）在其后。`git diff --numstat` = **+38 行、0 删除**。
- 验收命令与结果:
  - 位置判据（外部可观测）：`grep -n` 章节序 = 五条@14 → Q0@52 → Q1@70 → Q2@87 →
    Q3@131 → Q4@146 → 状态机@165。**五条在最前，判据表全部后置** ✓
  - 五条完整性：①搬运工与货物 ②工具输出是线索不是结论 ③优先查矛盾 ④宁可写卡住
    不许写完成 ⑤调整路线是正常的——逐条与定稿一致 ✓
  - 零删除：`git diff --numstat` 38/0 ✓
- 追加强化（随本轮一并落地）:
  - `review_case.py` blocked 触发面收窄：由「整行提到 blocked」改为「状态列（cells[2]）
    匹配 blocked 才触发」——防止证据/类型文字提及 blocked 造成误报；
    原因三词仍允许出现在整行任意列（证据列/备注列皆可）。
  - 负控 `test-assault-audit-negctl.py` +1 条（现在 **15/15**）：
    「状态列非 blocked 时，证据文字出现 blocked 不触发 blocked_reason_missing」。
  - 复跑矩阵（全部当次实跑）：strict 审查 PASS（rc=0）；单测 40/40 OK；
    负控 15/15 + 16/16 + 13/13；回归 8 次运行（2 case × 4 格式）与改前捕获逐字一致；
    check-fences rc=0；verify-doc-links rc=0；verify-gate-wiring **PASS**
    （blocked=0 needs_review=0，ci.yml 的 assault 负控 step 已被声明门禁识别）；
    `verify-evolution.py` → **10/10 ALL GREEN（EXIT=0）**；
    `verify-routing-coherence.ps1` → ALL PASSED。
  - 注：`ci-gates.lock.json` 锁定对象是 `ci-gates.json` manifest（25 条声明门禁），
    本次 ci.yml 新增的是 review_case 负控 step（非 manifest 门禁条目），wiring 门禁
    对「已声明门禁必须被 workflow 调用」的判据仍全绿——无需改锁文件。
- commit: （本段提交）攻坚交付闭环 · 攻坚者五条落地

---

## 9a 全项目自检 · 2026-10-13 03:30

> 依据 PATCH 文件 §2 的八维自检法。每维「已验证 / 有问题 / 待定」+
> 实物依据（读的文件 / 跑的命令 / 看到的输出）。

### 开工时发现的历史遗留
- 开工时工作区有两处未提交改动：`review_case.py`（blocked 触发面收窄：
  `ASSAULT_BLOCKED.search(status)` 状态列匹配 + 注释）与
  `test-assault-audit-negctl.py`（+1 条误报防护控制 → 15/15）。
  **判定：保留。** 理由：①收窄针对的是真实误报面（证据列提到 blocked 字样
  不应触发 blocked 状态判定），有 15/15 负控含专项条证明；②与 PATCH §2.2 维度 A
  的重点核查项（"验证这个收窄是否让另外两处也说得通"）方向一致；
  ③两者均已在 §9 补记有记录。已在 73e42ca（开工 commit）一并入库。
- `GOAL-PROMPT-PATCH-2026-10-13.md` 本文件自身在开工后又被外部修订
  （305+/122-，白话版重写 + §2.3 产出格式细化）——以新版本为准，其 §1.5/§1.6
  要求与已落地内容一致（已逐条核对，见维度 A/维度 G 记录）。

### 维度 A：三条主路径互通
- 状态: **有问题（已修）**
- 依据:
  - 三处分层措辞对照（实读）：`assault-entry.md` Q2 层表（L0 容器/L1 壳/L2 混淆/L3 自检/L4 业务）
    vs `assault.md` 模板 layers 表头（同 5 层 + 指向 Q2 的过层判据指针）
    vs `review_case.py` layers 检查（`L\d+` fullmatch + 状态+证据 + blocked 三词）——同一套 ✓
  - 下游消费链实测：`review_case.py --format json` 从真 case 读回 state=VERIFY /
    5 层 / 2 功能 / 1 unknown / deliverable_present=True；`diff-runner.py parse_assault`
    读回 baseline_command + cases [F-001|0, F-002|1] ✓
- 问题: **发现并修复**——`assault-entry.md` 第一屏**缺攻坚者五条**（PATCH §1 唯一必做缺口；
  上一轮编辑未落入提交，`git log` 证实）；`assault.md` 模板缺五条指针；
  `SKILL.md` 步骤 4 只写「完成四问」未提先读五条。三项已补（见 P1 记录），
  `+38/-0`（assault-entry）、模板 +4 行、SKILL.md 1 行改写。

### 维度 B：Q0 分流零影响
- 状态: **已验证**
- 依据:
  - case-init 双脚本自 stage-2 commit（e5b1abd）以来 **零改动**（`git diff --stat` 空）
  - Q0 非逆向任务实测（本会话早前跑过，产物仍存）：Temp/q0-test 的
    scope.md `grep -c assault` = **0**、无 assault.md、文件集 = 常规四件
  - 六组零差异对照（PS/bash × plain/offline/ctf）在阶段 2 已达成并记录 §9

### 维度 C：状态机无步骤化表述
- 状态: **已验证**
- 依据: `assault-entry.md` 状态机段（line 165-210）+ SKILL.md + 模板三处
  grep「第N步必须 / 下一步必须 / 先做..再做」= **空**；
  四状态各三要素（有效动作/出口条件/必须跳走）计数 = 5（引文1+四状态各1，符合设计）

### 维度 D：工序卡出口统一
- 状态: **已验证**
- 依据: 8/8 卡出口段实读，全部指向具体表名：
  vmp-virt（findings/functions/layers/unknowns）、vmp-devirt（diff_baseline/functions/routes/unknowns）、
  unpack（findings/functions/layers/unknowns）、ollvm（findings/functions/unknowns）、
  anti-debug（findings/layers/unknowns）、license-keygen（findings/functions/routes/unknowns）、
  protocol-reverse（findings/functions/unknowns）、struct（findings/functions/unknowns）——
  无一泛泛写「记录到报告」

### 维度 E：工具与判据对得上本机现实
- 状态: **已验证（1 特例有文档兜底）**
- 依据: 探测层 `Resolve-ReverseToolSpec` 逐项实测 12 个：
  11 个 `Available=True`（diec/floss/capa/pe-sieve/scyllahide/upx/r2/frida/jadx/binwalk/yara）；
  `cdbX64=False`——**预期设计**：`toolmap.default.json` 记载「绝不把 WindowsApps 加进 PATH；
  唯一入口是 app execution alias」；`anti-debug-bypass.md` line 25/71 已写明
  「cdb 只能走 alias」并给出完整用法（`$env:LOCALAPPDATA\Microsoft\WindowsApps\cdbX64.exe`）。
  alias 直跑验证：`cdb version 10.0.29661.1004` 回显正常。判据与实际一致，无需改。
  补充实测（MCP/库通道）：`x64dbg` 目录在 `D:\Tools\x64dbg`（GUI 需真实桌面会话，
  与既有 KNOWN-BOUNDARIES 一致）；`Ghidra` 在 `D:\Tools\Ghidra`；
  `pyghidra-mcp` 已注册于 `~/.omp/agent/mcp.json`；`angr+qiling+z3` Python 库导入 OK。

### 维度 F：五条接入判断链（机制兜底）
- 状态: **有问题（如实记录：三条软、两条硬）**
- 依据（逐条查机制）:
  - 规则①（搬运工/货物）: 软——五条文字 + `license-keygen/README` 原有同义条文，
    无机器检查。**可接受**：这是判断姿态，机器无法判定「你停在哪层」。
  - 规则②（≥2 独立证据）: 软——ADF-R4* 原文是 **SHOULD**（validated 要求 ≥2 独立），
    `review_case.py` 只检查「validated + confidence=low」矛盾（finding.confidence error），
    **不数证据条数**。**可接受**：R4* 明示 SHOULD，机械强制会误伤
    （同一份动态 trace 可合法支撑多条 finding）。留作建议项，见「建议但不修」。
  - 规则③（矛盾优先）: 软——纯姿态，无机制。**可接受**：矛盾识别是模型判断力本体。
  - 规则④（不许虚报完成）: **硬**——`review_case.py` 三条 error 级检查：
    `assault.state_exceeds_evidence`（完成态无证据）、`assault.diff_verdict_unproven`
    （verdict 未断言一致）、`assault.deliverable_missing`（成品不在盘且无 blocked 形态）；
    负控 15/15 证明真会拦。
  - 规则⑤（decision_delta）: **硬（契约级）**——`timeline-workitem.md` line 46：
    「每个真实 stage/turn transition **MUST** 写 decision_delta」；assault 模板与
    entries 均要求。案例本体检证：真 case timeline 含 2 条 decision_delta。

### 维度 G：跨会话接手
- 状态: **已验证**
- 依据（只读试跑，未改任何文件）: 打开 `work/assault-prng-upx/assault.md` 的 §0 状态行 =
  current_state(VERIFY) / since / goal_now / why_this_state(引 Evidence) / next_milestone
  / open_unknowns —— 六字段齐、全部可判定；§unknowns 单行含三列（影响/下一步/是否阻塞）；
  结论：**仅凭这两处即可接手**（知道「在 VERIFY、为什么、下一步做什么、还剩什么」）。

### 维度 H：日常路径污染
- 状态: **已验证**
- 依据: `git diff --numstat b2b0847..HEAD -- skillpack/` 有删除行的仅 5 个文件，逐一核查：
  1. `case-init.ps1` / `case-init.sh`：删除行 = **白名单文案旧版**（`...|update` →
     `...|update|assault`），预期修改（新预设必须同步文案）；
  2. `diff-runner.py`：删除行 = ①docstring 三行（改为三模式描述）②`input=` 剥离修复
     （3 行）③main 分支重构（update/assault 三分支 + source_name）；全部有 §9 记录；
  3. `signal-to-tool-decision.md`：删除行 = 指空修复（1 行替换）；
  4. `experience-cards/INDEX.md`：删除行 = 「共 8 张」→新计数（stamp 自动生成）。
  **结论**: 全部为有记录的预期修改；不含 assault 预设的运行路径均不受影响
  （case-init 六组零差异 + review_case 8 次运行对照均在 §9 有证据）。

### 自检结论
- **必须修的**（已全部修完）:
  1. 攻坚者五条未落在 `assault-entry.md`（PATCH §1 唯一必做缺口）→ 已补，
     位置判据「五条行号全部 < Q0 行号」实测通过（19/24/30/35/40 < 52）；
  2. `assault.md` 模板无五条指针 → 已补（4 行指针，无全文复制）；
  3. `SKILL.md` 步骤 4 未提「先读五条」→ 已补；
  4. `ASSAULT-GOAL §4.1` 第三条标题缺闭合 `**`（markdown 格式 bug）→ 已修；
  5. review_case blocked 触发面（审计提示）→ 已收窄到状态列 + 负控 +1（15/15）。
- **建议但本次不修的**:
  1. **ADF-R4* 的 ≥2 独立证据可考虑机检**（如报告 finding 级统计）——本次不修理由：
     R4* 原文为 SHOULD，机械数条数会误伤合法单证场景（同一 trace 证据可合法支撑多条
     finding 的不同侧面）；且证据「独立性」无法由机器判定（需语义级判断）。
     正确形态是保持操作者纪律（五条②）+ 人工复核，而非硬红。
  2. **CDB alias 的探测层可见性**（`Available=False` 但实际可用）——本次不修理由：
     本设计有明确防坑意图（WindowsApps 目录**绝不能**进 PATH，否则 MSIX ACL 让 cdb
     直跑报「拒绝访问」，那比没有更糟——toolmap note 2026-10-09 实测记载）；
     探测层「报 False + 卡片写明 alias 通道」正是正确兜底，改探测逻辑反而引入风险。
  3. **五条③（矛盾优先）无机制兜底**——姿态类规则，机器无法判定「你是否选择了顺眼的
     方向放下矛盾」；保持文字纪律即可。
- **确认没问题的**:
  - 三处分层措辞同一套（维度 A）；下游消费链四表全被读取（维度 A）；
  - case-init 双脚本自 stage-2 后零改动、Q0 零污染（维度 B）；
  - 状态机无步骤化（维度 C）；8/8 出口指具体表名（维度 D）；
  - 11/12 工具本机可用 + cdb 特例有文档兜底（维度 E）；
  - 规则④有硬机制（三条 error 级检查 + 15/15 负控）（维度 F）；
  - 跨会话接手只凭 §0+§unknowns 可行（维度 G）；
  - 全部删除行均为有记录的预期修改（维度 H）。

### §9a 门禁复跑（PATCH §5 第 4 条）
- `check-fences.py` rc=0；`verify-doc-links.py` rc=0；`audit-doc-code.py` **rc=0**
  （真错 0；同一处既有截断片段提示，与基线相同）
- `verify-evolution.py` → **10/10 ALL GREEN（EXIT=0）**
- `verify-routing-coherence.ps1` → **ALL PASSED**
- 终版零差异（当次实跑）：同目录、三组参数（plain / offline-sample / ctf-public），
  基线脚本（b2b0847）vs 当前脚本各跑一次，文件集相同、内容除 `created` 时间戳外
  逐字节一致 → **三组 ALL PASS**
