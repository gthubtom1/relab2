# Hub Vocabulary / Semantic Contract

Normative meanings for AI-facing and user-facing Hub terms. Shorthand alone is invalid.
Owner of definitions: Hub root docs. Rename requires compatibility note here.

Compatibility (2026-09-12): `update (maintainer)` 仍是吃新上游，现与「吃新上游」并列，旧技能里的英文名继续有效。`update (customer)` 仍是发给客户的那份更新，现与「客户路径更新」并列。`function_map` 仍是授权分界，没有改成功能相册。

| Term| Exact meaning| Required context| Forbidden interpretations| Observable acceptance|
|------|---------------|------------------|---------------------------|------------------------|
| candidate| Exact file set + content hashes + role + parent_sha (non-upstream) + revert recipe| product `.hub` + live files| “the EXE we talked about”; any unhashed path| `state candidate --show` matches on-disk SHA|
| upstream| Unmodified owner-supplied baseline bytes| baseline lock| patched/working tree called upstream| baseline sha in contract|
| access / development_probe| Reversible candidate that reaches mission.success in isolation| phase 1-access| window open, static string, raw upstream, launcher-only start| access artifact + role=access + human/core observation|
| core| Protected primary product surface after upstream auth boundary| after access| any visible chrome without permit| function_map + core role candidate|
| core_permit_bridge| Shipping control that allows/denies protected core under our auth| licensed/release| development probe left in ship build| three basics plus kick-stop and solo-still-open: valid opens, invalid/expired-on-entry does not, mid-run card expiry shuts down; kicked/`DEVICE_NOT_BOUND` stops; one machine past verify interval still open. revoked/offline only if this-run contract adds them|
| authorization| Upstream or own gate that blocks a capability| function_map boundaries| “login UI exists”| entry_gate / action_gate / continuous / public / unknown tagged|
| function_map| Map of capabilities → auth class| after access; **not** the owner boundary stop| feature wishlist; treating this as 产品边界确认；**不是**「现在人看见哪些功能」的相册；**不是**功能对照清单| `functions` + `authorization_boundaries` substantive|
| 产品边界| 主人点头：逻辑分离 / 物理分离 / 这场只换皮（SKIP）| exe-rebuild `2-boundary`；旧四格合同没有这一格| AI 代决物理拆；function-map 当边界完成；「测中枢随便改」当分离完成| `arch.decision` 写清三选一或 SKIP|
| package / distribution| Installer or portable of the **exact** tested candidate; customer overlay-update is a **separate** stop| exe-rebuild `5-pack`; overlay is `6-update`| ZIP; stub launcher; swallowing upgrade/rollback into first-pack receipts as story-complete| build artifact binds candidate sha + clean-install receipt|
| update (maintainer) / 吃新上游| 无源码、有源码、原创后期都要跟上新版本。先打开上一份冻本和功能表/改动图，**逐条分析**还能认还是新门。清单要用来对，不是答案。变动少：按清单再核对后搬。授权或架构位置大变：当新门重做，不许照抄旧补丁| 碰新样本、打补丁、打包、上架、发自己的下一版之前| 旧偏移/旧脚本交差；照抄清单；声明不用核对；用「打开冻本」代替三句；让主人再讲改了哪些皮；客户已装点更新冒充吃上游| 三句写得出且同时判断还能认和新门；认不出不许硬打旧补丁|
| 改动图| 我们动过的每一刀：稳定编号、作用、怎么找到（当前）、曾经失效的找法勿删、大约位置、改成了什么。活本从第一刀累积。施工对照上一份已发给客户的冻本；找门读活图；第一版冻本不是第 4 次施工图| 动刀当天写；定档冻本须带上| 只写功能名；只写地址；旧脚本跑一遍；只读第一版全文；只读夹里最新试冻| 下一版能再认出或标新门；认不出不许硬打旧补丁|
| update (customer) / 客户路径更新| 已经发给客户的旧版，客户在自己电脑的**软件里**点更新：查出、人确认、按这条产品的更新路走完，卡密和数据还在。接了社区授权平台时：带当前版本号问平台，有新版才提示，点了用系统浏览器打开平台给的网盘网址，就是这条路| 向人报「更新做成了」必须是这条路| 开发机再装一次；另装一个文件夹；平台后台能下但软件里没走过；工作目录能点或新装一份能用就说更新做成了；和吃新上游焊成一次交差；没接平台却发明开浏览器顶原来的站内下载| 客户那台已装旧版的电脑上，软件里那条路走通|
| complete / 交付| 东西交到人手里，下一任能接着干。冻本和功能表还对得上这一版| 交付验收 / 运维交接| 只交一个包；功能表和冻本对不上还说交完了| 人点头 + 冻本功能表仍对得上当前文件|
| clean install / 首次安装| 干净机装的是打包时冻住的那一版，不是开发机后来改过的| 桌面/命令行 `5-install`| 开发机启动过了；功能表改了还拿旧包交差| 干净机主流程 + 冻本功能表仍对得上|
| data migration / 数据迁移| 对照上一份数据怎么放：哪些字段还能迁、哪些是新门；向前迁、备份、失败能回| 网站 `5-data`；桌面/命令行更新格| 只换脚本交差；迁移退出 0；找不到旧字段还硬套旧脚本| `follow` 三句判断 + 迁移/备份/回滚复验|
| evidence_level| `structure` \| `host` \| `product` \| `human`| confirm/record| promoting structure to product| access/core require product or human|
| BLOCKED| Hard stop with evidence + ≥2 different-layer routes after hypotheses were tried and not falsified| attempt --blocked| DIE packer tag, missing skill row, 20-minute clock, or “swap tools” counted as a new route| status shows block; confirm refuses|
| observability| Can see the gate’s inputs/outputs/side effects when the refuse happens| reverse triage| unpacked file on disk; “restore observability” as a work package / unpack chapter| stated layer of the refuse, not a DIE label|
| isolation (execution)| Run surface is not the owner’s daily OS, profile, secrets, or installed apps| before executing unknown binaries| same-machine 产品根 `TEMP\\`, shared AppData, same-machine elevation| owner-confirmed isolated host/VM, or this-run accept of host risk|
| observation-gate| Target refuses to run (or stays down) when analysis tools are present| before license-gate experiments| treating it as the license gate, as single-instance, or as 740/inject failure without a paired contrast| one bare-run vs tools-present contrast written down|
| 核心可用| Owner stop: same candidate, entry gate + write-action gate + primary function actually work| exe-rebuild 1-access| “window opened”; “测中枢 / 接着往下做”; download hang written into evidence as not blocking| owner said 可以 after seeing those three。残余缺口对人说/写 STATUS，不要把 UNVERIFIED/未验证 写进 --evidence|
| 给别人的包| 刚验过的那一版安装包/便携包；覆盖更新/官方改道是另一步；客户包不依赖本机 PATH 里的 Python| exe-rebuild `5-pack`（旧合同仍可能叫 3-ship，但不要为过旧门去 record）| ZIP；「不深入」；平台下载链接冒充覆盖更新；把覆盖更新 SKIP 写进本行当完成；Inno/启动器调用开发机 PATH 里的 python| 安装收据 + 哈希；不依赖本机 Python。覆盖/官方更新不能靠本行 SKIP 算过|
| 互攻| 一拿到程序、还没开工具就 3–4 路独立写层、切入、相反预测、是否绕路（分析第一步就要派，不是等补丁前）| exe-rebuild 逆向；难度可加轮| 当成停点等人评完再动手；投票同一叙事；评比推翻「只动许可判定」；「互攻同意」当 confirm 证据；拖到补丁前才派人；和出口审查混成一套| 有区分性实验或止损；不能代替自己触发写动作|
| 出口审查| 高风险收尾：同一本 review 里按四顶帽子走（程序→产品→测试→发布）→ 人话总结 → 批评手打报告（写的人不能给自己过，也不能自己宣布完成）→ 有洞就改再审。独立来自原话/客户皮/探针，不是再派几路| 授权/发布/迁移/删除/生产；主人不放心一份产出| 轻量小修走全套；只扫清单；`state` 绿当完成；一轮打完自动下一轮；另开四本专家技能；清单过了就 `gh release`；开审查子代理当交叉；只戴帽子就当走过出口| 真洞留下并改；CLEAN 须写出打过哪些点与假设，仍不能说彻底没问题|
| 四审| 同一本 review 里的四顶帽子：程序审→产品审→测试审→发布审。写代码的人不能自己宣布完成。帽子是同一路依次戴，不是四路人| 高风险出口必须按顺序走完；一刀复核把四顶碰到即可| 另开四本技能；一顶一路子代理；轻量也走四审；装/升/退清单过了就发 Release；四顶一轮灌完整份中枢| 出口走完四顶并走批评手；发布审不是自动 `gh release`|
| 覆盖更新| 软件里下、有进度、弹出安装、默认旧路径盖成**同一个**软件| exe-rebuild `6-update` 的客户路径那一段；是客户路径更新的一种做法，不是吃新上游| 写进 `5-pack`/`3-ship` 当完成；平台能下 ZIP；另装一个文件夹；拿覆盖更新代替三句对照；拿覆盖更新说已经吃完新上游| 覆盖成真同一个软件，或该项 SKIP（仅本格）；未验证对人说、不进 --evidence；官方更新失败或进三条通道|
| 功能对照清单 / 当前功能表| 贯穿全程，流程里早就预设，不该等提醒。每个能看见的功能一行，只认最新一版；写改的是什么功能、**作用是什么**，不能只写二进制。人能看见功能那天就写。进 Git，跟产品夹走。原话流水是另一份只追加的纸，不许合成一份。授权页、到期、更新、购买、联系做了就要有行| 所有产品线；主流程刚能用就出生，这就是原创基线的一半；定档/发版冻本须带上；二开另对照「我们的 vs 原件」| `.hub` 里的 function_map / dossier / checklist；只写二进制/哈希；施工自己写「已验证」；把中间改错的旧行当当前；用新总结覆盖旧行；新产品第一天向主人要功能表（应先听一句写成方案给人认窗）；旧场表空却说「我记得 / 清单很完善」；等到打包才补第一行| 表上能指到每个功能的作用；图标改左只留左；更新时能对照功能和位置，而不是整仓重读|
| 测中枢 / 测试中枢 / 不深入 / 跳过| Scope cut for this test only| any confirm| using them to turn a stop green; 「测试中枢」≠ 须写成「测中枢」才拦| 本项 `SKIP` **且** 该格允许（产品边界确认 / 覆盖更新与官方更新确认）；`UNVERIFIED`/`未验证` 对人说、不进 --evidence；其它格 confirm 仍拒|
| 可以跑| This-run permission to start this file in this folder| before executing unknown binaries| standing authorization for all later knives, elevation, Program Files, or “isolation is done”| one target, one file, known no execution-isolation|
| 测试孪生| 我们自己的授权平台的一份测试部署（同一合同，不是正式租户）| 按产品形态测过三种基础、被挤掉会停、没人挤不会自己关之后，接到正式平台之前。桌面有窗/二开启动器才要通用授权页已改成这个产品的样子| 正式 VPS「先试一下」；WSL2 测平台被说成样本已真隔离；空孪生没有对照产品就声称不影响别人；桌面/二开拿没改过的通用页直接接孪生；命令行/网站为过关先改或另造授权页再接孪生；只测三种基础就接孪生| 清单上的合同用例过了，含单机还开着和被挤会停；对照产品记录/配置哈希不变|
| 正式接线| 按测试孪生清单，只改正式机上本产品的记录| after 测试孪生| 在已有其他软件的正式机上当第一现场；一次点头覆盖以后所有产品| backup + diff of this product only + this-run owner 可以|
| 三种基础（收费授权）| ①卡密对且没过期才放行后面的程序/服务；②卡密无效或一进来就过期则不要放行；③用着用着过期了则停掉后面的程序/服务。桌面有窗才另测藏页/关页（附加，不能交差、不能顶第一种）；命令行/无窗口不造页、对才放行主命令；网站走站点收费门，不要关软件。三种基础不能吞掉购买/联系/更新，也不能吞掉第四种| 接自己的授权之后、连正式之前；按产品形态测| 用藏页/关页顶第一种基础；只测断网就算闭环；只拦启动器；脚本直开核心；桌面/二开拿没改过的通用页直接接；命令行必须造授权窗；网站按关软件交差；只测三种基础就算授权做完；只测对错到期就算授权做完；把验证间隔写成核心到期倒计时| 三句都能真看见，但不能单独交差|
| 第四种（被挤掉/解绑）| 卡仍有效，但这台 `DEVICE_NOT_BOUND` / 被另一台挤掉 / 已解绑时必须停。旧电脑必须再调 verify，下一次验证内停，不是当场秒关。桌面/二开停主程序，命令行停主命令，网站停服务（不要关软件）。机器观察 `kicked_closed=true`| 接了自己的授权之后；先测「没人挤不会自己关」，再测这一种，不能事后补一句| 只测到期；还没等过间隔就上第二台；第二台开着、第一台还开着；把解绑写成进门时调了接口；宽限当成多台同时登录；把当场停写成必须秒关；靠 20 秒硬刷看见挤机| 先只有一台等过间隔还开着，再第二台挤掉第一台后，第一台下一次验证内停|
| 卡还剩多久| 交给核心的 `expiry_seconds` 是这张卡还剩多少秒，必须大于每一个再问/缓存间隔（`verify_interval_seconds` / `cache_until` / `cache_seconds` / `next_verify_at`），也不能贴着间隔（差 2 秒内）。禁止把 `cache_until` / `next_verify_at` / 20 秒 / 默认验收 60 秒塞进核心或标题栏倒计时| 接了社区授权、要过 `license_dataflow` 时| 用 20 秒、21 秒或 60 秒间隔过动态到期门；`cache_until` / `next_verify_at` 跟到期写成同一个数；缩短核心到期冒充 `mid_run_closed`；硬编码 365 天；把验证间隔写成核心到期倒计时| 核心/标题栏倒计时跟卡剩余走；再问间隔另记|
| 两套钟| 卡到期 `expires_at`：激活时写进票，启动器交给主程序本地倒计时，到点关，这是对的，不要改成「到期也必须再问才关」。挤机 / 解绑 / 撤销 / 阻断：只改平台绑定，旧电脑必须再调 verify，下一次验证内停。`cache_until` / `next_verify_at` 只决定何时再问，不是主程序能开多久| 接了社区授权、写到期或挤机时| 给核心的可用时长跟验证租约走；核心租约=验证窗口；到期也必须再问才关；把再问间隔塞进核心/标题栏到期；靠 20 秒硬刷看见挤机| 到期本地关；被挤后下一次验证内停；单机超过间隔还开着|
| 没人挤不会自己关| 只有一台时，开着超过验证间隔，主程序必须还在。机器观察 `solo_still_open=true`。必须先测这一段，再测第四种| 接了自己的授权之后；先于被挤掉会停| 单机没人挤却关了还当挤机验收；watch 只有 `RATE_LIMITED` 没有挤机 stop；先上第二台再回头看单机| 等过验证间隔，这一台还开着|
| 限流不是停机| `RATE_LIMITED`、暂时失败不是停机条件。`rate_limited_closed=false`| 接了自己的授权、看 watch / 探针时| 把限流、暂时失败写成挤机或到期停| 限流时主程序还在，被挤掉才停|
| 挤机开关 / 宽限 / 最大设备数| 挤机开关：已售跟着变，第二台进来第一台要停。最大设备数、断网宽限：已售不跟。宽限是暂时问不到平台时怎么处理，**不是**允许多台同时登录| 写授权说明、对接文档、测第四种时| 把宽限说成可以两台一起开；把最大设备数当成已售跟着变；把三者写成同一件事| 能分开指到：谁跟着已售变、谁不跟、被挤掉的那台停了没有|
| 通用授权页定制| 把共用的授权页改成这个产品的名字和样子，主人看过这一页再接线| 若接自己的授权，且是桌面有窗/二开启动器| 拿没改过的通用页直接接正式或孪生；命令行/网站为过关先改这一页；在产品根另写一套卡密协议顶替母版| 主人能认出这是这个产品的页|
| 授权 A / 社区授权接口| 接了社区授权平台时一次做全：激活/验证/解绑，而且验证是开着还要周期性问，不是进门写了三个接口；被挤掉后，旧电脑必须再调 verify，下一次验证内停；设备码 `缩写-XXXX-XXXX-XXXX-XXXX`；购买网址和联系字跟这张卡的下游，原文原样，空则不显示/点了没反应，不准自己编、不加「QQ」、不准传下游编号；更新带当前版本号问平台，有新版才提示，点了打开网盘；测试只用 `ceshi1`、新发卡、先打测试站；测试/验收间隔默认 60 秒，不要 20 秒硬刷；已售卡锁快照；没点头不要打正式站；主程序不直连平台；软件侧交对接文档，平台侧只登记不改程序| 接了自己的授权之后；桌面走授权页，命令行走主命令，网站走站点收费门| 三种基础吞掉购买/联系/更新或第四种；只测对错到期就算授权做完；一句激活/验证/解绑都要交差；只 activate 不再问；另写一套协议；改平台程序；发明 QQ 前缀；没新版也弹窗；平台能下但软件里没走过；把验证间隔写成核心到期倒计时| 接口表上的项都能指到真实行为；空就是空；先只有一台等过间隔还开着，再被挤掉的那台下一次 verify 内停|
| 原创基线| 人能看见主功能那天锁住的功能对照清单 + 总图 + 改动图 + 这一版 `work/vX`。发出去冻进 `freeze/vX`。以后改功能对照这份位置| 原创/接手/二开都要；主流程刚能用就锁| 等到打包才补第一行；只认 git 没有版本夹；整仓重读当对照；把 TEMP 里的草稿当基线| 下一版能按冻本找到功能和位置，认不出标新门|
| 一版一目录 / work/vX| 每一版一个工作目录（`work/v1.0.1`、`work/v1.0.2`）；不要在同一盘文件上把下一版闷头叠上去。Git 定档还要，不能代替版本夹。乱堆的无名副本仍禁止| 原创和二开都这样| 把 `work/vX` 丢进 TEMP；只靠 git 就说版本齐了；在同一盘文件上叠下一版| 能指到这一版工作拷贝，下一版是新目录|
| 白话| 先说人听得懂的：做到什么、还缺什么、下一步看哪；一次只说一扇窗、一个键；机械项自己跑；主功能给人话清单等人测；做不到当场说| any user-facing stop| 只丢术语/刀号/CLEAN；听不懂还接着往下；「人话锁层」当交差；一次丢三件事；两句互相吞掉| 主人能复述下一步要点哪|
| 开工目录| 要留下的（源码、当前工作拷贝、数据、秘密、包）和可整夹删除的分开；产品里可扔掉的只进产品根 `TEMP/`| any new or takeover project start| 根目录一锅炖；先堆再想；把各版补丁/包丢进 `TEMP/`；派人去「找不找得到文件夹」当复核| README 写清两堆各放哪；产品 `.gitignore` 忽略 `/TEMP/`|
| TEMP| 产品根下唯一可整夹扔掉的夹：解包、日志、草稿、测试垃圾、分析过程件。整夹可删。不是系统自带的临时目录| 任何会堆过程件的产品任务| 各版补丁、界面候选、给别人的包、原始样本、`.hub` 账本、`work/vX` 工作拷贝、`freeze/` 冻本进这里；另起第二套临时垃圾夹| 成品或定档之后可以整夹删掉而不丢主功能；`work/vX` 是要留下的这一版工作拷贝，不是 TEMP。工具吃不消中文/空格路径时，另开产品外短 ASCII 工作区、用完就删，那不是第二套 TEMP 相册|
| 轻量| 问答 / 错别字 / 已有产品上的局部 bug / 已点名的单文件小修：直接做 + 验证，不 `init`、不走产品停点、不建 STATUS。已有产品改一处文案/按钮/局部样式仍轻量| 任务分档；定义在 AGENTS「先分档」| 把新产品 / 以后要卖 / 整页或多文件 UI / 改 AGENTS、词汇表或活技能正文（错别字除外） / 改中枢运行核（错别字除外） / 二开 / 发布 / 迁移说成轻量；一句里轻量+新产品只做轻量| 相关验证已跑，并说清没验什么|
| 标准| 先讨论方案。已有产品才：产品目录短 STATUS + `state status` 核身份 + 测试 + 回退点；不必走完停点 confirm。局部一处按钮/文案不是标准。新产品还没有产品文件夹时先讨论方案，不要先核身份。指认文件夹（不是中枢源仓根、也不是源仓里的子夹）之后再 init，有产品账才核身份。无账但夹里已有源码：按接手谈方案，不跑产品 status、不问档。空文件夹不要跑 status、不要问「是这一档吗」；谈清再 init| 产品任务；不是中枢根 `STATUS.md`| 用中枢根 STATUS 当产品进度；新产品没文件夹或空文件夹就跑 status / 问「是这一档吗」；无账有源码就跑产品 status；把中枢源仓根或源仓里的子文件夹指成产品夹（夹里已有合同也不算）；把一处文案抬成标准；命令行接授权就造窗| 已有产品：目录有短 STATUS，身份已对人复述。新产品：方案已讲清并指认文件夹（不是中枢源仓根、也不是源仓里的子夹）后再 init；空文件夹/无账有源码不跑 status、不问「是这一档吗」|
| 高风险| EXE 二开 / 授权 / 发布 / 迁移 / 删除 / 生产：完整停点 + 人工 confirm + 独立复核| 产品任务| 「子代理说没问题」当过门| 停点有 evidence，主人点了头|
| 本场不接授权| 主人选了不接自己的收费授权；写进 spec/arch 的产品决定| 原创桌面/网站/命令行/接手，问过接不接之后。**无源码二开没有「可以不接」**，走授权页启动器| 用 confirm 的 SKIP 点绿需求格或打包格；默认免费也不问；把「不要套二开」理解成不许问授权或不许做授权页；无源码二开写成这场不接；把没源码的核心当载荷再套一层启动器抄到原创/接手| `spec.acceptance` / `arch.decision` 写清本场不接；仍走改界面 + 打包|
| 源码档 / 定档| git 上已经钉住的那一版源码（可打标签）；A 定档后再做 B| 已有产品账的产品文件夹；`state status` 印出。有账才去看，不要靠「有 git」去跑 status| 把 `candidate` / `--bless` 当功能相册；凭聊天记忆拿旧代码改；没提交就说已定档；无账有 git 就当已有产品去核身份| status 源码档与磁盘 git HEAD 一致；下一刀改的是这一档之后的当前文件|
| 候选包 / bless| 打好的程序/包的指纹 + last-good 包备份| 构建/发布格| 当成功能 A/B/C 的源码档| `candidate --show` 对得上磁盘哈希|
| 掌舵| 中枢管大方向、停点、账本、物理门、能不能交货；不是全场唯一裁判，也不管死细活用哪本书| 产品线选择与阶段推进| 只靠中枢 22 本判定全程；细活也只准中枢自己干| 这场抱哪条产品线、验没验过、能不能打包说得清|

## Anti-drift rule

Before freezing wording in AGENTS, skills, templates, state messages, or phase goals: check this table. Ambiguous “处理好 / 可用 / 接入 / 按需 / 发布 / 分发 / 更新” without inputs/outputs/acceptance **blocks** the affected route until rewritten.
