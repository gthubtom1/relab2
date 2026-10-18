# 05-tests 实跑结果
> **这是一份带日期的验收快照，反映的是那一天的状态，不是现状。**
> 里面的数字（如文件大小、段数）**不要再引用**——那之后规则又改过好几轮。
> 要看现在是什么，读 [`01-design/当前实测基线.md`](../01-design/当前实测基线.md)。



> 跑法：`cd kernel/05-tests && python run_all.py`
> 退出码：0 = 全绿，3 = 有红项，2 = 环境没准备好。
> 下面「自动段」里的每一个数字都来自实跑，`run_all.py` 每次跑完会重写它；手写分析在自动段之后，不会被覆盖。
> 原始控制台输出另存 `LAST-RUN.txt`；ctxiso 崩过的 stderr 另存 `LAST-STDERR.log`。

<!-- BEGIN AUTO-RUN -->

> 本段由 `python run_all.py` 自动生成，数字全部来自实跑，不要手改。
> 生成时间：2026-10-19 01:57:08　·　Python 3.14.3

## 一句话总判定

| 项 | 结果 |
|---|---|
| 场景数 | 9（全套 1–9） |
| 断言 | 151 条，151 通过，0 红 |
| 有红的场景 | 无 |
| 真仓库零改动（层 1） | 是 |
| 退出码 | 0 |
| 总用时 | 10538.5 ms |

## 场景 1　普通新任务：不会因为历史记录自动加载大量无关内容

用时 268.1 ms，12/12 条断言通过。

| 判定 | 断言 | 实际数字 | 实际输出 |
|---|---|---|---|
| 通过 | 1.1 pack 成功 | bytes=`2320`；ms=`89.7` | rc=0 |
| 通过 | 1.2 预算硬顶 | bytes=`2320`；budget=`6000`；headroom=`3680` | 配置 pack_budget_bytes=6000 |
| 通过 | 1.3 包自报的 budget 与配置一致 | budget=`6000` | — |
| 通过 | 1.4 无 README.md 正文片段 | shingles=`781`；hits=`0`；sample=`` | 比对 781 个 30 字 shingle，命中 0 个 |
| 通过 | 1.4 无 01-design/当前实测基线.md 正文片段 | shingles=`524`；hits=`0`；sample=`` | 比对 524 个 30 字 shingle，命中 0 个 |
| 通过 | 1.5 出现长期资料的索引行（不是正文） | rows_in_pack=`16`；listed=`['00-ANALYSIS/01-真实系统分析.md', '00-ANALYSIS/02-污染链实测.md', '00-ANALYSIS/03-审计结论.md', '00-ANALYSIS/README.md', '01-design/历史-接入点（三层结构时代）.md']` | 包里列了 16 份：00-ANALYSIS/01-真实系统分析.md、00-ANALYSIS/02-污染链实测.md、00-ANALYSIS/03-审计结论.md、00-ANALYSIS/README.md、01-design/历史-接入点（三层结构时代）.md |
| 通过 | 1.5b 索引行字段齐全（路径+大小+行数+一行用途） | index_rows=`16`；max_index_rows_per_kind=`10` | 共 16 行索引，逐行四段齐全（每类上限 10，三类相加） |
| 通过 | 1.6 索引行的一行用途确实来自各文件首行 | matched=`16`；rows=`16` | 16/16 份的一行用途对得上首行 |
| 通过 | 1.7 omitted 写清没展开什么 + 怎么取 | omitted=`1` | project 资料还有 47 份未列（全量：`ctxiso archive list --kind project`，那是索引不是正文） |
| 通过 | 1.8 【本包刻意不含】段存在 | — | 找到该段，含 5 行 |
| 通过 | 1.9 无账本事件正文 | ledger_bytes=`4172520`；sampled=`240`；shingle=`4948`；hits=`0` | 抽样 240 条长事件 / 4948 个 60 字片段，命中 0 |
| 通过 | 1.10 无 observed/assertions 等 JSON 键 | hits=`0` | 命中：无 |

> 真仓库 doc 表共 63 份资料；pack 只按 pack_max_index_rows=10 每类列 10 行，所以 omitted 里必然有内容（见 1.7）

## 场景 2　连续任务：当前任务状态能正确延续，不累积回灌

用时 290.1 ms，8/8 条断言通过。

| 判定 | 断言 | 实际数字 | 实际输出 |
|---|---|---|---|
| 通过 | 2.1 第一次意图正确 | line_len=`17` | 【任务意图】  给主人解释载入流程 |
| 通过 | 2.2 第二次意图正确 | line_len=`34` | 【任务意图】  查清 state status 为什么会回灌历史缺口 |
| 通过 | 2.3 两个意图互不串 | — | 包1 含意图2=False，包2 含意图1=False |
| 通过 | 2.3b 两次都只有一个【任务意图】行 | — | — |
| 通过 | 2.4 两包大小之差 < 预算一半 | bytes1=`2320`；bytes2=`2343`；diff=`23`；limit=`3000` | 预算一半 = 3000 |
| 通过 | 2.5 两次都在预算内 | bytes1=`2320`；bytes2=`2343`；budget=`6000` | — |
| 通过 | 2.6 除意图行外两次包逐字节相同（无累积回灌） | same_bytes=`True` | 长度 2271 vs 2271 |
| 通过 | 2.7 两次 indexed_events 相同（同一份索引，没被重灌） | events=`0`；doc_count=`63`；ms1=`93.4`；ms2=`88.0` | — |

## 场景 3　自动记录：工作过程仍然能正常保存，没有被关掉

用时 1577.6 ms，14/14 条断言通过。

| 判定 | 断言 | 实际数字 | 实际输出 |
|---|---|---|---|
| 通过 | 3.1 记录器清单 8 项都在 | recorders=`8` | 共 8 项，缺 无 |
| 通过 | 3.2 策略写明自动记录一律保留 | — | 自动记录一律保留。ctxiso 不关、不改、不删任何一条记录。 |
| 通过 | 3.3 state.py 完整流程跑通（init→plan→require→work→leave） | steps_ok=`7`；steps=`7` | init=0 \| plan=0 \| require=0 \| work --define=0 \| work --enter=0 \| work --leave=0 \| record=0 |
| 通过 | 3.4 账本被真的追加了 | ledger_bytes=`1097` | 1097 字节 / 4 条事件 |
| 通过 | 3.5 原话账被真的追加了 | req_bytes=`235`；req_id=`REQ-001` | {"requirement_id": "REQ-001", "verbatim_intent": "演示产品每次开工都要把主人原话追加进账本，不许覆盖旧记录", "status": "captured", "ts": "2026-10-18 |
| 通过 | 3.6 快照覆盖到被观测文件 | files=`8` | 指纹覆盖 8 个文件 |
| 通过 | 3.7 追加动作真的写进去了 | req_bytes=`458` | require=0 work--enter=0 |
| 通过 | 3.8 observe check ok=true | rc=`0` | 自动记录仍在正常追加：4 份资料增长，0 份变小，0 份消失。 |
| 通过 | 3.8b 退出码 0 | rc=`0` | — |
| 通过 | 3.9 shrank 为空 | — | [] |
| 通过 | 3.10 gone 为空 | — | [] |
| 通过 | 3.11 至少一条 grew | grew=`4` | grew=['OWNER-SPEECH.md', 'CHANGES.md', '.hub/ledger.jsonl', '.hub/requirements.jsonl'] |
| 通过 | 3.12 没有 new（被观测文件快照时就已存在） | — | [] |
| 通过 | 3.13 账本里 work_enter 出现两次（进入两次都是追加） | work_enter=`2` | work_enter 计数=2 |

> 假产品目录：05-tests/TEMP/fake-auto（测完随 TEMP 一起删）
> 真仓库 .hub/ 全程没被写：见 RESULT.md 的保护区指纹比对

## 场景 4　历史查询：用户明确需要过去资料时能找到并按需读取

用时 763.0 ms，22/22 条断言通过。

| 判定 | 断言 | 实际数字 | 实际输出 |
|---|---|---|---|
| 通过 | 4.0 假产品索引成功 | indexed=`3` | — |
| 通过 | 4.1 archive list 无任何文件正文 | shingles=`1820`；hits=`0`；sample=`` | 比对 1820 个 30 字 shingle（3 个文件），命中 0 |
| 通过 | 4.1b 返回体里最长命中正文行 = 0 | longest_line=`0` | 命中最长行 0 字符（门槛 0） |
| 通过 | 4.1c 返回体远小于源文件总量 | out_bytes=`1043`；src_bytes=`25524`；ratio=`0.04086` | 返回 1043 字节 / 源 25524 字节 = 0.0409 |
| 通过 | 4.2 索引里找得到两版规格和原话 | rows=`3` | 命中 ['OWNER-SPEECH.md', 'docs/history/spec-v1.md', 'docs/history/spec-v2.md'] |
| 通过 | 4.3 每行只有元数据字段 | — | 字段集合 ['kind', 'lines', 'mtime', 'one_line', 'path', 'sha', 'size'] |
| 通过 | 4.4 read 无 --intent 退出码 2 | rc=`2` | {'ok': False, 'refused': True, 'why': '没有意图就不给正文。先说清为什么现在需要它。'} |
| 通过 | 4.4b refused 为真 | — | {'ok': False, 'refused': True, 'why': '没有意图就不给正文。先说清为什么现在需要它。'} |
| 通过 | 4.4c 拒绝时不回正文 | — | 拒绝体里没有 ok=true |
| 通过 | 4.5 read --intent 成功 | rc=`0`；crashed=`False` | rc=0 stdout 前 120 字='{\n  "ok": true,\n  "receipt": {\n    "ts": "2026-10-18T17:57:00Z",\n    "target": "docs/history/spec-v1.md",\n    "intent": ' |
| 通过 | 4.5b 正文真的回来了 | text_chars=`4157` | — |
| 通过 | 4.7 compare --intent 成功 | rc=`0` | rc=0 stdout 前 120 字='{\n  "base": "docs/history/spec-v1.md",\n  "head": "docs/history/spec-v2.md",\n  "base_lines": 125,\n  "head_lines": 131,\n  ' stderr='' |
| 通过 | 4.7b 返回里有差异摘要字段 | added=`129`；removed=`123`；similarity=`0.0156` | added=129 removed=123 similarity=0.0156 hunks=2 |
| 通过 | 4.7c compare 不回两份全文 | hits=`0`；sample=`` | 比对 1461 个 shingle，命中 0 |
| 通过 | 4.7d compare 返回体远小于两份全文 | out_bytes=`486`；full_bytes=`19725` | 486 字节 vs 全文 19725 字节 = 0.0246 |
| 通过 | 4.6 reads.jsonl 留有收据（target/intent/bytes/sha8 齐全） | receipts=`2`；read_receipts=`1`；cmp_receipts=`1` | 共 2 条收据（read 1 条 + compare 1 条）；最后一条 target=docs/history/spec-v1.md vs docs/history/spec-v2.md |
| 通过 | 4.6b read 确实多写了一条收据 | read_receipts=`1` | reads.jsonl 里有 1 条 target=docs/history/spec-v1.md 的收据 |
| 通过 | 4.6c read 收据的 sha8 是 8 位十六进制 | sha8=`d8ca77b4` | sha8='d8ca77b4' |
| 通过 | 4.6d read 收据字段齐全且自洽（bytes_read ≤ file_bytes、target/intent 对得上） | missing=`0`；consistent=`True`；bytes_read=`10001`；file_bytes=`10001` | 缺字段 无；bytes_read=10001 file_bytes=10001 truncated=False target=docs/history/spec-v1.md |
| 通过 | 4.6e 同内容再读一次，sha8 稳定 | sha_first=`d8ca77b4`；sha_again=`d8ca77b4` | 第一次 'd8ca77b4'，第二次 'd8ca77b4' |
| 通过 | 4.6f 内容不同的文件，sha8 不同 | sha_v1=`d8ca77b4`；sha_v2=`94f3f732` | v1='d8ca77b4' v2='94f3f732' |
| 通过 | 4.8 目标在产品外被拒 | rc=`2` | {'ok': False, 'refused': True, 'why': '目标在产品目录之外，拒绝读。'} |

> 假产品目录：05-tests/TEMP/fake-hist

## 场景 5　项目更新：第二版来了要能对比第一版、快速定位变化

用时 674.4 ms，15/15 条断言通过。

| 判定 | 断言 | 实际数字 | 实际输出 |
|---|---|---|---|
| 通过 | 5.0 假产品索引成功 | indexed=`8`；events=`24`；ledger_bytes=`73564` | rc=0 |
| 通过 | 5.1 compare 不带 --intent 退出码 2 | rc=`2` | {'ok': False, 'refused': True, 'why': '版本对比同样要意图：这次要比什么、为什么比。'} |
| 通过 | 5.1b refused 为真 | — | {'ok': False, 'refused': True, 'why': '版本对比同样要意图：这次要比什么、为什么比。'} |
| 通过 | 5.2 纯改：added=1 removed=1 hunks=1 | added=`1`；removed=`1`；hunks=`1` | added=1 removed=1 hunks=1 op=['replace'] |
| 通过 | 5.3 纯加：added=1 removed=0 | added=`1`；removed=`0` | added=1 removed=0 op=['insert'] |
| 通过 | 5.4 纯删：added=0 removed=1 | added=`0`；removed=`1` | added=0 removed=1 op=['delete'] |
| 通过 | 5.5 换序：内容多重集不变（没有一行丢失或被改写） | base_lines=`9`；head_lines=`9` | base 9 行 / head 9 行 |
| 通过 | 5.5b 换序：added == removed > 0（纯搬移的指纹） | added=`1`；removed=`1`；similarity=`0.8889` | added=1 removed=1 similarity=0.8889 |
| 通过 | 5.6 similarity 都在 (0,1] 且四组互不相同 | sim_a-modify=`0.8571`；sim_b-append=`0.9333`；sim_c-remove=`0.9231`；sim_d-reorder=`0.8889` | {'a-modify': 0.8571, 'b-append': 0.9333, 'c-remove': 0.9231, 'd-reorder': 0.8889} |
| 通过 | 5.7 compare 不回两份全文 | — | 4 组比较，输出里一个 30 字正文 shingle 都没有 |
| 通过 | 5.7b 每条 hunk 都带 base/head 行号 + ≤120 字的一行样本 | — | 样本例：{'op': 'replace', 'base': 'L4-4', 'head': 'L4-4', 'sample': '- F3 打印与传真'} |
| 通过 | 5.8 每次 compare 都留收据 | receipts=`4` | reads.jsonl 共 4 条，全部是 compare 写的 |
| 通过 | 5.8b 收据的 target 是「base vs head」，intent 非空 | sha8=`None` | docs/history/feat-a-modify-base.md vs docs/history/feat-a-modify-head.md |
| 通过 | 5.9 archive find 命中 8 份版本资料 | hits=`8` | 命中 8 条 |
| 通过 | 5.9b find 只给位置，不给正文 | hits=`8` | 每条字段 ['kind', 'lines', 'mtime', 'one_line', 'path', 'sha', 'size']；无正文 shingle |

> 四组差异的数字是手算的：纯改/纯加/纯删各只动一行，difflib 必然给 1 个 replace / 1 个 insert / 1 个 delete；换序组用「行多重集不变 + added==removed」两条独立性质判，不依赖 difflib 怎么打破平局。

## 场景 6　上下文压缩：压缩后不会把整个历史项目塞回当前上下文

用时 449.5 ms，19/19 条断言通过。

| 判定 | 断言 | 实际数字 | 实际输出 |
|---|---|---|---|
| 通过 | 6.1 存活字段正好 7 个 | fields=`7` | ['intent', 'stage', 'goal', 'next', 'blockers', 'confirmed_decisions', 'constraints'] |
| 通过 | 6.2 规则写明历史正文不进摘要 | — | ['历史事件正文、探针收据正文、旧版本资料正文不进入压缩摘要。'] |
| 通过 | 6.3 规则写明丢掉的是指针不是删除 | — | ['被丢掉的不是删除：只写进 dropped.json 的指针，需要时按指针取回。'] |
| 通过 | 6.4 规则写明取回要带意图 | — | ['取回任何一份被丢掉的资料，都要带读取意图。'] |
| 通过 | 6.4b 没有任何一条规则要求重新总结历史 | offending=`0` | [] |
| 通过 | 6.5 假产品历史已索引 | ledger_bytes=`2780320`；events=`800` | 账本 2780320 字节 / 800 条 |
| 通过 | 6.6 生成 SURVIVOR.md | path=`state/c4c3db4f53eb/SURVIVOR.md`；survivor_bytes=`551` | — |
| 通过 | 6.6b 生成 dropped.json | path=`state/c4c3db4f53eb/dropped.json`；dropped_bytes=`729` | — |
| 通过 | 6.7 存活集正好是传进去的 7 个字段 | fields=`7` | ['intent', 'stage', 'goal', 'next', 'blockers', 'confirmed_decisions', 'constraints'] |
| 通过 | 6.8 SURVIVOR.md < 2000 字节 | bytes=`523`；limit=`2000` | — |
| 通过 | 6.9 SURVIVOR.md 不含任何探针名 / 事件 kind | hits=`0` | 命中 无 |
| 通过 | 6.9b SURVIVOR.md 不含 OWNER-SPEECH / CHANGES 内容 | shingles=`1836`；hits=`0`；sample=`` | 比对 1836 个 shingle，命中 0 |
| 通过 | 6.9c SURVIVOR.md 不含账本事件正文 | hits=`0` | 抽样 200 条 / 4684 个 50 字片段，命中 0 |
| 通过 | 6.9d SURVIVOR.md 不含任何账本事件时间戳 | ledger_ts=`60`；hit_ts=`0`；iso_in_survivor=`1` | 账本里有 60 个不同 ts，命中 0 个；SURVIVOR.md 里的 ISO 时间戳共 1 个 |
| 通过 | 6.10 dropped.json 每项都带 what/count/how | — | 账本历史事件(800)→ctxiso query --kind <kind> --limit 50; 长期资料正文(2)→ctxiso archive list --kind <kind> 然后 ctxiso read --intent .. |
| 通过 | 6.10b dropped.json 里没有正文 | hits=`0` | 比对 1836 个 shingle，命中 0 |
| 通过 | 6.11 账本那项带取回命令 ctxiso query --kind <kind> --limit 50 | how=`ctxiso query --kind <kind> --limit 50`；ledger_count=`800` | ctxiso query --kind <kind> --limit 50 |
| 通过 | 6.12 资料那项带取回命令（list + read --intent） | how=`ctxiso archive list --kind <kind> 然后 ctxiso read --intent ..`；doc_count=`2` | ctxiso archive list --kind <kind> 然后 ctxiso read --intent .. |
| 通过 | 6.13 dropped.json 体积很小（只有指针） | bytes=`700`；limit=`4000` | — |

> 6.x 的规则文字来自 ctxiso/compact.py:27-32；02-hubcore/AGENTS.md §9.2.5 写的是「压缩不是重新总结历史」，两处是同一条规则的不同措辞，所以断言按语义（不进入摘要 + 按指针取回）判，不按字面判
> 6.x 的 --state 跑在 TEMP 假产品上：真仓库 800 条事件的假账只用于证明「历史再多也不回流」，避免往真仓库的侧车状态目录里写 SURVIVOR.md

## 场景 7　大量历史文件：资料越来越多也不会每次自动读一大片

用时 3198.8 ms，14/14 条断言通过。

| 判定 | 断言 | 实际数字 | 实际输出 |
|---|---|---|---|
| 通过 | 7.0 假产品造好了 | files=`2001`；bytes=`24655620`；ledger_bytes=`16413620`；make_ms=`933.6` | 2001 文件 / 24655620 字节（历史文件 2000×4096 B，账本 5000 事件 / 16413620 字节） |
| 通过 | 7.1 index 耗时 < 15000 ms | elapsed_ms=`885.4`；ledger_ms=`489.1`；ledger_read_bytes=`16413620` | 整条命令（含解释器启动 + 文档扫描 + 账本增量） |
| 通过 | 7.2 索引库远小于源（比值 < 10%） | index_bytes=`1576960`；src_bytes=`24655620`；ratio=`0.063959`；shrink=`15.6` | 索引 1576960 字节 / 源 24655620 字节 = 0.06396 |
| 通过 | 7.3 索引 doc 表有 2000 行 | doc_rows=`2000`；history_rows=`2000` | {'history': 2000} |
| 通过 | 7.3b 100 文件的对照产品也索引好了 | indexed=`100`；ms=`645.9` | — |
| 通过 | 7.4 2000 文件下 pack ≤ 预算 | bytes=`2661`；budget=`6000`；pack_ms=`100.4` | — |
| 通过 | 7.4b 100 文件下 pack ≤ 预算 | bytes=`2658`；budget=`6000`；pack_ms=`95.5` | — |
| 通过 | 7.4c 两个产品的索引行数一样多（比较才公平） | listed_2000=`10`；listed_100=`10` | 2000 文件列 10 行，100 文件列 10 行 |
| 通过 | 7.5 包里的索引行数 ≤ pack_max_index_rows × 类别数 | listed_rows=`10`；max_rows=`10` | — |
| 通过 | 7.6 其余资料进 omitted，并写明怎么取 | omitted=`1` | history 资料还有 1990 份未列（全量：`ctxiso archive list --kind history`，那是索引不是正文） |
| 通过 | 7.6b omitted 里的份数算得对 | — | 期望 1990 份未列 |
| 通过 | 7.7 2000 文件 vs 100 文件，包大小差 < 500 B | bytes_2000=`2661`；bytes_100=`2658`；diff=`3`；limit=`500` | 2661 B vs 2658 B，差 3 B |
| 通过 | 7.8 第二次 index 账本 read_bytes = 0（增量） | first_read_bytes=`16413620`；second_read_bytes=`0`；attempts=`1`；first_ms=`885.4`；second_ms=`356.1` | 第1次 read_bytes=0 new_events=0 356.1ms　（第一次全量 read_bytes=16413620 字节） |
| 通过 | 7.8b 第二次 index 没有新增事件 | new_events=`0` | — |

> 7.8 允许跑两次取最后一次：同机别的进程也会跑 ctxiso index，撞同一份索引库时 read_bytes 可能不为 0。增量逻辑本身是对的（store.refresh_ledger 按 meta.ledger_cursor seek 到新增字节）。本轮跑了 1 次：第1次 read_bytes=0 new_events=0 356.1ms
> 文档索引每次都会重算全部 2000 个文件的 sha 与行数（refresh_docs 没有按 mtime 短路），所以第二次账本 read_bytes=0 但整条命令仍要 356.1 ms

## 场景 8　长期项目维护：跑很久以后仍能按需取回必要信息

用时 1029.1 ms，16/16 条断言通过。

| 判定 | 断言 | 实际数字 | 实际输出 |
|---|---|---|---|
| 通过 | 8.1 核心：index+pack+archive list 三步后，读取收据仍是 0 条 | reads_after_meta=`0` | index rc=0 pack rc=0 list rc=0；reads.jsonl 不存在，实际 0 条 |
| 通过 | 8.1b 侧车自报 read_receipts = 0 | read_receipts=`0` | ctxiso status 自报 0（rc=0） |
| 通过 | 8.2 archive list 列出全部 4 份长期资料 | rows=`4` | 命中 ['CHANGES.md', 'OWNER-SPEECH.md', 'PROJECT-MEMORY.jsonl', 'WORK-HANDOFF.md'] |
| 通过 | 8.2b 只给元数据，没有正文 | shingles=`5275`；hits=`0` | 比对 5275 个 30 字 shingle，命中 0 |
| 通过 | 8.2c 数据型 jsonl 的用途摘要是「数据文件，无人读标题」 | — | ['（数据文件，无人读标题）'] |
| 通过 | 8.3 archive find 能按关键词命中 | hits=`1` | 命中 ['OWNER-SPEECH.md'] |
| 通过 | 8.4 读到改动图，且里面确实有指向 OWNER-SPEECH 第 30 行的那一条 | changes_chars=`14797` | 改动图 14797 字；含引用=True 含原话=True |
| 通过 | 8.4b 按 scope 精确取回第 30 行 | speech_chars=`40` | 取回 40 字：'第 030 句：主人说过的一句关键原话：把导出改成先落盘再通知，通知失败不许吞。' |
| 通过 | 8.4c 改动图里的引用与 OWNER-SPEECH 原文逐字相同 | key_chars=`32` | 两边都含同一句原话 |
| 通过 | 8.5 一次取回被上限截断（truncated=true 且 bytes_read ≤ cap） | file_bytes=`322553`；bytes_read=`65538`；truncated=`True`；cap=`262144` | 文件 322553 字节，本次只取回 65538 字节，truncated=True，cap=262144 |
| 通过 | 8.5b 没有一次把整份原话吞进来 | bytes_read=`65538`；file_bytes=`322553` | 65538 < 322553 |
| 通过 | 8.5c pack 也没把原话正文带进去 | bytes=`1671`；budget=`6000` | — |
| 通过 | 8.6 dropped.json 给了资料取回指针 | how=`ctxiso archive list --kind <kind> 然后 ctxiso read --intent ..`；count=`4` | ctxiso archive list --kind <kind> 然后 ctxiso read --intent .. |
| 通过 | 8.6b 按指针能列出被丢出去的资料位置 | rows=`2` | ['OWNER-SPEECH.md', 'CHANGES.md'] |
| 通过 | 8.6c 压缩后取回的内容与原始逐字一致（sha8 对得上） | sha_before=`8a89cba3`；sha_after=`8a89cba3` | 压缩前 sha8=8a89cba3，压缩后 sha8=8a89cba3；文本相同=True |
| 通过 | 8.6d 全程 4 次带意图读取，收据一条不少 | receipts=`4` | reads.jsonl 共 4 条 |

> 8.1 是本场景的核心：3 步元数据操作后 reads.jsonl 必须还是 0 条——「保存了不等于被读回去」这条纪律的机器证明。

## 场景 9　新旧系统并存：新开发系统没有破坏原来的中枢

用时 2287.4 ms，31/31 条断言通过。

| 判定 | 断言 | 实际数字 | 实际输出 |
|---|---|---|---|
| 通过 | 9.1 真仓库 guard check：ok=true | guard_ok=`True` | 中枢原有 24 个受控文件全部逐字节未变。 |
| 通过 | 9.1b changed 为空 | changed=`0` | [] |
| 通过 | 9.1c missing 为空 | — | [] |
| 通过 | 9.1d 非 append-only 的改动为空 | baseline_at=`2026-10-18T17:54:20Z` | [] |
| 通过 | 9.1e guard snapshot/check 基线自洽：changed/missing 都空 | guarded=`24`；guard_ok=`True` | 受控 24 个文件：中枢原有 24 个受控文件全部逐字节未变。 |
| 通过 | 9.1f guard 能抓出真改动（不是空转） | caught=`['02-hubcore/CORE.md']`；restored=`True` | 改一个字后 changed=['02-hubcore/CORE.md'] / ok=False；改回去后 ok=True |
| 通过 | 9.2 本轮测试没有把仓库弄脏（与跑前基线比，只算新增；别人的改动不计） | lines=`0`；baseline=`120`；raw=`` | 跑前已有 120 行（别人改动，不计）· 本轮新增 0 行：[] |
| 通过 | 9.3 旧系统 state.py 全流程跑通（init→plan→require→work→status） | steps_ok=`5`；steps=`5` | init=0 \| plan=0 \| require=0 \| work --define=0 \| status=0 |
| 通过 | 9.3b status 输出含 MISSION 与当前阶段/下一步 | out_chars=`1022`；has_mission=`True` | ---------------------------------------- \| 产品：fake-old　类型：cli-tool \| 路径：<kernel>\05-tests\TEMP\fake-old-system \| MISSION r1：让演示产品的导出失败原因一眼看得见 \| 可观察成功：导出命令失败时退出码非 0 且把原因打在标准错误上 \| 当前路线：先收原话，再用 state work 累积责任 \| 源码档：这个产品文件夹 |
| 通过 | 9.4 白名单之外的 UNKNOWN 写句柄数为 0 | calls=`19`；suspect=`0`；unregistered=`0` | 扫了 19 个写句柄，自动认不出落点的 0 个，其中未登记 0 个。白名单： |
| 通过 | 9.4b 白名单里没有过期条目（每条都还挂在真实调用点上） | stale=`0` | 过期：无 |
| 通过 | 9.4c 白名单每一条都写了「写到哪里、为什么安全」 | entries=`12` | 12 条，最短说明 26 字 |
| 通过 | 9.4d 没有任何一个写句柄指向产品目录（hub/ 与 .hub/） | touches_product=`0` | [] |
| 通过 | 9.4e 写句柄只落在侧车自己的 state 目录（外加 pack --out 这一处按需） | state_writes=`18` | state 18 处；caller opt-in 1 处；白名单 0 处 |
| 通过 | 9.4f 唯一的「按调用方指定路径写」是 pack --out，且默认不触发 | opt_in=`1` | [('cli.py:L80', "Path(a.out).write_text(res['text'], encoding='utf-8')")] |
| 通过 | 9.4g 运行时证明：整套场景跑完，guard 仍报 changed 为空（见 9.1/9.1b） | — | 场景 9 是整套的最后一个，9.1/9.1b 就是跑完之后的复查结果 |
| 通过 | 9.4h 反向断言：故意写进 hub/ 的句柄会被扫描器抓出来 | caught=`1`；kind=`UNKNOWN`；in_whitelist=`False` | 注入到 TEMP 副本的 hub/INJECTED.md，扫描器判定 kind=UNKNOWN touches_product=True 白名单里=False |
| 通过 | 9.5 打包产物已装进假宿主家目录的 hub/ | files=`91` | 91 个文件；顶层 ['AGENTS.md', 'CORE.md', 'ctxiso', 'docs', 'registry.json', 'templates', 'tools', 'uninstall.py', 'workflows'] |
| 通过 | 9.5b 装出来的东西搜不到源仓路径 / context-isolation / github.com / http:// / user-skills | scanned=`91`；hits=`0`；real_hits=`0`；whitelisted=`0` | 扫了 91 个文件，命中 0 处；白名单排除 0 处 |
| 通过 | 9.5c 每一处命中都在明明白白的白名单里（不许静默跳过） | whitelist=`0` | 无 |
| 通过 | 9.5d 02-hubcore 已被临时改名（源树此刻不在原位） | renamed=`True` | 改名成功=True；02-hubcore 在原位=False |
| 通过 | 9.5e 假宿主里 python hub/tools/state.py --help 成功 | rc=`0`；ms=`192.9` | usage: state.py [-h]                 {init,plan,status,gate,work,probe,accept-closed,accept-seen,confirm,attempt,reopen,record,require,verif |
| 通过 | 9.5f 假宿主里 python hub/ctxiso/cli.py status --product <假产品> 成功 | rc=`0`；ms=`102.4` | {   "ok": true,   "product": "<kernel>\\05-tests\\TEMP\\fake-home-prod",   "state_dir": "<kernel>\\05-tests\\TEMP\\fake-home\\hub\\.state\\5 |
| 通过 | 9.5g 假宿主里 python -m ctxiso status --product <假产品> 成功 | rc=`0`；ms=`90.3` | {   "ok": true,   "product": "<kernel>\\05-tests\\TEMP\\fake-home-prod",   "state_dir": "<kernel>\\05-tests\\TEMP\\fake-home\\hub\\.state\\5 |
| 通过 | 9.5h 02-hubcore 名字已改回来（try/finally + 重试 + atexit 兜底） | restored=`True`；leftover=`False` | 回到原位=True；残留改名目录=False；回滚函数返回=True |
| 通过 | 9.5i 新包的状态写在包内 .state/（不落在源仓任何地方） | state_in_pkg=`True`；children=`['573ca44604cb']` | 包内 .state/ = True |
| 通过 | 9.5j check_dist_sync.py 退出 0（产物与源码同源） | rc=`0`；checked=`91` | 产物是当前源码构建出来的 |
| 通过 | 9.5k 产物里的 ctxiso/cli.py 内容与源码树一致（换行归一化后） | sha_src=`7dc0479c`；sha_dist=`7dc0479c`；same=`True`；raw_bytes_src=`11051`；raw_bytes_dist=`11349` | 归一化后 源码 sha8=7dc0479c / 产物 sha8=7dc0479c；原始字节 源码=11051 产物=11349（差 298 是 pack.py 把 LF 转成 CRLF，不是内容漂移） |
| 通过 | 9.5l 产物里没有打包工具（只有运行期要用的东西） | leaked=`0`；checked=`6` | 进包了：无，一个都没有 |
| 通过 | 9.5m 出货件里没有运行期残留（.state/ 与 __pycache__/） | scanned=`dist/hubcore`；residue=`0` | 扫 03-bundle/dist/hubcore（出货件本身）：无 |
| 通过 | 9.5m2 残留确实是运行期产生的（装前无 → 跑完才有），不是随包发出的 | dist_clean=`True`；at_install=`False`；runtime_state=`True` | 出货件 无；刚装好时 .state=False；跑完 9.5f/9.5g 后 .state=True |

> 9.5 用的是打包器的产物 03-bundle/dist/hubcore，91 个文件；包内 .state/ 落在 05-tests/TEMP/ 下，跑完随 TEMP 一起删。

## 保护区指纹比对（三层）

| 层 | 范围 | 被改 | 新增 | 消失 | 判红 |
|---|---|---|---|---|---|
| 1 硬保护区 | 中枢本体（`02-hubcore/` 的规则与运行核）、仓根文件 | 0 | 0 | 0 | **是** |
| 2 本项目内 | `ctxiso/`、`00-ANALYSIS/`、`01-design/` | 0 | 0 | 0 | 否（E/F 分区，别人在改） |
| 3 别人分区 | `03-bundle/`、`04-console/`、`06-verify/` | 1 | 0 | 0 | 否（T1/T2 同时开工） |

跑前取指纹 453 个文件，跑后 453 个。

层3 别人分区 本轮观察到的变化（不是本测试夹具写的）：
- `03-bundle/bundle-meta.json`

## 跑完删掉了什么

- `05-tests/TEMP/` 整个目录：已删
- 侧车状态目录里本轮假产品的格子 `<hubcore>/state/<key>/`：46577448868b, 524715d835b4, 99c34664221f, c2277428a875, c4c3db4f53eb, dd52b67c7351, f34784f003ed, f831c3d84ce2

跑完 `<hubcore>/state/` 现有内容：`5c1c28ba7880, b8b4b57a808e`

<!-- END AUTO-RUN -->





































































































































## 手写分析（不会被 run_all.py 覆盖）

### 一句话

**以顶部自动段为准**（`run_all.py` 每次跑完重写，数字是最近一次实跑）。
2026-10-18 这一轮复跑了多次：中途出现过 146/1 红（9.5j：源码改了未重打 `dist/`）与
一次场景挂起（`selftest` 与 `run_all` 并发跑互删 `TEMP/`，非产品缺陷）→
重打 `dist/` 且串行执行后 **147 条断言 / 147 通过 / 0 红 / 退出码 0**。
此前手写段写的是「152 条 / 151 通过 / 1 红 / 退出码 3」，那条红是
`03-bundle/dist/hubcore/.state/` 混进出货件（F2）——`pack.py` 复制时已排除 `.state/`，
9.5m / 9.5m2 实测通过，**已转绿**，手写段随之对齐。

断言的条数是**条件式生成**的（例如 9.1 在侧车无基线时只 `note` 不 `check`、场景 5 在 `compare`
提前 return 时后面整段不生成），实测到过 120 / 138 / 147 / 151 四种总数。
**别拿条数当回归基线，看「0 红」和每个场景的 X/X 通过。**

> 另一条实测坑：**跑 `run_all.py` 时别同时改仓库。** 9.2 的判据是「跑前基线 vs 跑后只算新增」，
> 别人并发写文件会被记成「本轮新增」（这正是它要抓的东西，不是测试缺陷，但会制造假红）。

> 注意：9.5j（产物与源码同源）会在**源码改动尚未重打 `dist/`** 时红——
> 那是护栏按设计工作，处置是重跑 `python 03-bundle/pack.py`，不是改测试。

这套测试到目前为止一共抓出 **5 个真缺陷**（`archive.py` 的 `hashlib.sha8`、
`cli.py` 的 `read_history` 少传参数、`pack.py` 的 `omitted` 少报份数、
产物忘了重打、产物混入 `.state/`），**五个全部已修**（第五个见 F2）。

---

## A. 9.4 的具名白名单（12 条，每条都写了写到哪里、为什么安全）

键是「文件::所在函数」，不用行号——统筹改 `ctxiso/` 时行号会漂，函数名不会。
规则和 `03-bundle/verify.py` 一样：**白名单之外多出一个写法就红，白名单里少了东西也红。**

| # | 调用点 | 实际写到哪 | 为什么安全 |
|---|---|---|---|
| 1 | `archive.py::_receipt` | `paths.receipt_path()` = `state/<key>/reads.jsonl` | 整套设计里唯一「记录读了什么」的地方，append 写自己盘上的收据，产品目录一个字节不动 |
| 2 | `archive.py::list_docs` | `state/<key>/index.sqlite`（SELECT） | 只开索引库做只读查询 |
| 3 | `archive.py::find` | 同上 | 同上；find 按约定只返回位置不给正文 |
| 4 | `cli.py::cmd_query` | 同上 | 同上；query 按约定只出摘要行 |
| 5 | `cli.py::cmd_status` | 同上 | 读 `indexed_events` / `doc_kinds` 等统计 |
| 6 | `compact.py::build` | 同上（后面写的是 `survivor_path()` / `dropped_path()`，已由自动分类单独识别） | 只开索引库数事件数 |
| 7 | `observe.py::recorder_report` | 同上 | 只开索引库数各类记录器的事件数 |
| 8 | `pack.py::build` | 同上 | 只开索引库读索引；产品目录全是 `open('rb')` 读 |
| 9 | `paths.py::state_dir` | `STATE_DIR/<产品key>/` | 建的是侧车自己的状态目录，不是产品目录 |
| 10 | `store.py::refresh_ledger` | `state/<key>/index.sqlite` | 账本本体只以 `open('rb')` 读，从不写 |
| 11 | `store.py::stats` | `state/<key>/` | 只开索引库读统计 |
| 12 | `store.py::refresh_docs` | `state/<key>/index.sqlite` 的 `doc` 表 | 被扫的资料一律 `open('rb')` 读，不写 |

**实测**：19 个写句柄调用点 → 自动分类认不出落点的 0 个 → 白名单实际用掉 0 处
（分类器这轮已经能自己认全了，白名单退成第二道保险）。
`9.4b` 断言白名单里没有过期条目，`9.4c` 断言每条说明 ≥ 20 字（实测最短 26 字）。

**唯一一个「写调用方指定的路径」是 `cli.py` 的 `pack --out`**，默认不触发，
单独列在 `9.4f`，不允许混进白名单。

### B. 反向断言：白名单不是摆设（9.4h）

把 `ctxiso/` 复制到 `TEMP/ctxiso-mutant/`，往副本的 `archive.py` 追加一个
故意写进产品目录的函数：

```python
def _test_injected_write(product):
    (paths.hub_dir(product) / 'INJECTED.md').write_text('x', encoding='utf-8')
```

用同一个扫描器扫这份副本，真实输出：

```
[PASS] 9.4h 反向断言：故意写进 hub/ 的句柄会被扫描器抓出来
  — 注入到 TEMP 副本的 hub/INJECTED.md，扫描器判定 kind=UNKNOWN
    touches_product=True 白名单里=False
  caught=1  kind=UNKNOWN  in_whitelist=False
```

**三个信号同时变**：被识别成新的调用点、`kind=UNKNOWN`、`touches_product=True`、
且不在白名单里。9.4d（没有写句柄指向产品目录）在真源码上是绿的，加上这条就证明：
只要有人真往 `hub/` 写，测试立刻红。

---

## C. 抓出来并已修掉的缺陷（前两轮）

1. **`ctxiso/archive.py:118` 用了 `hashlib.sha8`** —— Python 标准库没有这个算法，
   `read --intent` 每一次都崩在 `AttributeError`。带意图读正文是整套设计里唯一的
   正文取回阀，这条路从建库起就没通过。已改成 `hashlib.sha256(...).hexdigest()[:8]`。
2. **`ctxiso/cli.py:167` 调 `archive.read_history(p)` 少传 `name`** —— 必填参数没给，
   `ctxiso status` 从建库起就没能工作过。已修。
3. **`ctxiso/pack.py` 的 `omitted` 少报历史份数** —— `store.docs(con, limit=500)`
   先截断再拿「截断后还剩几行」当总数，2000 份说成「还有 490 份未列」。
   少报比多报危险。已改成总数走 `GROUP BY` 的真实计数。

---

## D. 我自己写错、已经改掉的断言

1. **6.9d 误判**：第一版写「SURVIVOR.md 不含任何 ISO 时间戳」，把
   `compact.build` 写的合法一行「生成：<时间戳>」判成了历史回流。
   改成「不含账本里出现过的任何 `ts`」，并同时报出账本 ts 数 / 命中数 / SURVIVOR 里的 ISO 数
   （实测 60 / 0 / 1）。
2. **7.7 的对照做废重做**：一开始没给 `fake-small` 跑 `index`。
   `pack` 只读索引库、自己不扫目录，不索引就一行索引行都没有，对照包只有 437 字节。
   **那个红是我自己造出来的。** 补上 `index` 之后 2661 B vs 2658 B，**差 3 字节**。
3. **8.4b 行号错位**：`KEY` 原话被写到了文件第 30 行之外（内容行号和文件行号差 1），
   `--scope L30:30` 取回的是填充句。改成按文件行号构造。
4. **8.5 原话文件不够大**：74 KB < `hard_read_cap_bytes`（262,144 B），
   永远不会触发 `truncated`。把填充行加长到 322,553 B，才真正测到上限。
5. **8.6d 收据数写死成 5**：实际是 4 次带意图读取。改成按实际次数判。
6. **9.4c 白名单说明太短**：三条原因不到 20 字。已补写，阈值 20 字。
7. **保护区分层划错**：第一版把 `00-ANALYSIS/`、`01-design/`、`02-hubcore/` 划进
   「判红」层，T5 和统筹写文档就误报。已按 `SPEC-自包含安装.md` §2 改成三层。
8. **`shutil.rmtree` 遇文件锁直接崩**：改成带重试的 `rmtree_force`。

---

## E. 一次真事故：`02-hubcore` 被留在改名状态

第一版 9.5d 的回滚写在 `finally` 里，用的是
`if renamed and hidden.is_dir() and not src_dir.exists(): src_dir.rename(hidden)`。
**这条回滚在一次运行里失败了**，`02-hubcore` 被留在
`02-hubcore.RENAMED-BY-05tests` 状态——统筹那边整整几分钟读不到这个目录。
我手工 `Rename-Item` 改回来了（67 个文件、`AGENTS.md` 在位）。

原因：守卫条件刚判断完，紧接着的 `rename` 报 `FileNotFoundError`——
中间有别的进程碰过这个目录，守卫的判断和实际动作之间不是一个原子。

**改法**（现在生效）：
- 改名和回滚都走 `_swap()`，6 次重试、递增间隔；
- `finally` 之外再挂一个 `atexit` 兜底；
- `run_all.py` 启动时先自愈：发现 `02-hubcore.RENAMED-BY-05tests` 存在而
  `02-hubcore` 不存在，先改回来再开跑（本轮实测触发过一次自愈，打印「[自愈]」）；
- 9.5h 断言回滚结果，`leftover` 单独报出来。

**这一条我不打算"改进断言绕过去"。** 改别人正在用的目录是本套测试里风险最高的动作，
所以保留这条断言，同时把三道兜底都补上。

---

## F. 打包链的两条红（两条都已修）

### F1（9.5j）护栏已生效：抓到过一次「忘了重打」，统筹重打后转绿

这条断言在**本轮中途红过一次**，抓到的正是统筹说的第 3 条 bug 的当下形态：

```
rc=3｜检查了 91 个｜内容不同的 1 个：['ctxiso/__init__.py']｜该有却没有的 0 个
verdict=产物过期：0 个文件该有却没有、1 个内容不同
```

改了 `ctxiso/__init__.py`（加了「不在自己目录里写字节码」那条、
把状态目录那句改成「包内 `state/` 下」），**源码树是绿的，`dist/` 里还是改之前的版本**。
护栏指名道姓说了是哪一份。统筹重跑 `pack.py` 之后，本轮最后一次实跑：

```
[PASS] 9.5j check_dist_sync.py 退出 0 — 产物是当前源码构建出来的  rc=0  checked=91
```

**这条断言以后会一直挡住"忘了重打包"**，不用再靠人记得。

> 跑它的过程中还撞见过 `check_dist_sync.py` 的更早一版报
> `why=重新构建失败，产物新鲜度无从判断`——`pack.py` 改写 `ctxiso/__init__.py` 的
> **锚点是旧版第 3 条原文**（`3. 本包所有状态写在 work/context-isolation/state/ 下，不写进 .hub/。`），
> 素材一改版锚点就断，**`pack.py` 当时根本重建不出来**。统筹随后修好了锚点。
> 这条根因值得单独记一笔：**打包器用"旧文本锚点"改写素材，素材一改版就会静默断链。**
> 建议改成按标记结构（例如 docstring 条目序号）匹配，
> 或匹配失败时给出"素材行号 + 期望内容"，而不是只报 `找不到：'3。'`。

### F2（9.5m，已转绿）`dist/` 里混进了运行期残留

```
03-bundle\dist\hubcore\.state\ad09fb308a9b\index.sqlite
```

`.state/<产品key>/index.sqlite` 里的 `ad09fb308a9b` 是**真仓库的产品 key**。
说明有人（或看门狗、或 `check_dist_sync.py`）在 `dist/` 目录里对着真仓库跑过一次
`ctxiso`，状态目录就落在了产物树里。`pack.py` 复制时没排除 `.state/`，
于是这份运行期残留会被一起装进每一台机器。

**这正好是 9.5b 那条禁词扫描抓不到的一类问题**：它不含任何源仓路径，
所以"搜不到 `D:\`、`context-isolation`、`github.com`"是绿的，但它是货。
我为此加了 9.5m：产物里不许出现 `.state/` 与 `__pycache__/`。

**处置**：`pack.py` 复制时排除 `.state/`（`check_dist_sync.py` 的 `SKIP_DIST` 里
已经有 `"state"`，打包器这边漏了），然后重跑一次 `pack.py`。
本轮**没有代改**——`03-bundle/` 是 T1 的分区。

> **2026-10-18 复核：已修并转绿。** `pack.py` 现在在建包末尾显式
> `for state_dir in out.rglob(L.STATE_DIRNAME): rmtree_quiet(...)`（`pack.py:335-339`），
> `check_dist_sync.py` 的 `_files()` 也按**相对路径**排除 `__pycache__`/`.state`。
> 自动段 9.5m「出货件里没有运行期残留」`residue=0`、9.5m2「残留确实是运行期产生的」
> 三条子判据（出货件 无 / 刚装好 .state=False / 跑完 .state=True）全部通过。

---

## G. 9.5k 的一个坑：产物和源码的字节永远不一样

第一版 9.5k 写的是「产物里的 `ctxiso/cli.py` 与源码树 sha 相同」，直接红了：

```
源码 sha8=7dc0479c  产物 sha8=dd3a19d1
```

查下来是**无害的**：`pack.py` 复制时把 **LF 换成了 CRLF**。
源码 11,051 B / 298 个 LF，产物 11,349 B / 298 个 CRLF，正好差 298 字节；
`Compare-Object` 逐行比 298 行**完全相同**；换行归一化后 sha 都是 `7dc0479c`。

**这一条我判成「我的断言写错了」而不是代码有 bug**：
byte-level sha 相等在有换行转换的打包链上永远不可能成立，判它红是噪声。
改成**换行归一化后比 sha**（仍然能抓住「忘了重打包」），并在同一行里
把原始字节数和差值都打出来，让换行转换这件事显式可见而不是被藏起来。
判断依据：如果 9.5k 归一化后仍然红，那才是真漂移。

顺带解释了统筹为什么把 `check_dist_sync.py` 改成「重新构建一份再比」而不是
「拿 dist 和源码逐字节比」——后者会永远红。这个改法是对的。

---

## H. 未确认 / 本轮没做

- **`check_dist_sync.py` 对 `bundle-meta.json` 声明的「故意不进包」清单处理**：
  早一版它把 `tools_excluded` 里声明排除的 19 个文件（`own_skill.py`、
  `skill_pull.py`、17 个 `test_*.py`）报成 `missing_in_dist`，一度把看门狗弄成常红。
  本轮跑时它已经改成「重新构建再比」，这条不复现。但**排除清单这件事本身**
  仍建议在 `check_dist_sync.py` 里显式读 `bundle-meta.json`，否则以后再加排除项会重演。
- **场景 9.5 的独立运行只在假宿主里验过，没在真宿主家目录验过**——真宿主家目录
  属于主人的机器，不在 `05-tests/` 的写入范围内。
- **没有联网，没有 git 写操作。** `git status --porcelain` 是只读的；9.2 那条判的是
  「与跑前基线比，**本轮测试新增** 0 行」（别人的未提交改动不计，见 `test_scenarios.py` 的
  `TEMP/.git-status-before` 逻辑），自动段实测 `lines=0`。

---

## I. 写盘纪律的实际执行情况

| 项 | 结果 |
|---|---|
| 只在 `05-tests/` 下建文件 | 是：`run_all.py`、`test_scenarios.py`、`SCENARIOS.md`、`RESULT.md`、`LAST-RUN.txt`、`LAST-STDERR.log`、`.gitignore` |
| 假产品位置 | 全部在 `05-tests/TEMP/`（11 个目录名，见 `test_scenarios.FAKE_PRODUCT_NAMES`），跑完整个目录删掉 |
| **层 1 硬保护区（判红）** | `02-hubcore/CORE.md`、`02-hubcore/AGENTS.md`、`02-hubcore/workflows`、`02-hubcore/docs`、`02-hubcore/tools`、仓根所有文件 —— 被改 0 / 新增 0 / 消失 0 |
| 层 2 本项目内（只报） | `ctxiso/`、`00-ANALYSIS/`、`01-design/` |
| 层 3 别人分区（只报） | `03-bundle/`、`04-console/`、`06-verify/` |
| 真仓库 `.hub/` | 一个字节没动 |
| `ctxiso/` | 一个字节没动（被测对象，全程只读） |
| `02-hubcore` | 临时改名一次，**try/finally + 重试 + atexit + 下次启动自愈**四道兜底，本轮回滚成功 |

**唯一落在 `05-tests/` 之外的写盘，是被测代码自己的状态目录**
`kernel/state/<产品key>/`——`ctxiso/paths.py:11` 把 `STATE_DIR`
写死在那里。跑完按 `FAKE_PRODUCT_NAMES` 算出的 key 把本套测试的格子全删了
（**只删 TEMP 下面产品的 key，绝不碰真仓库那一格 `5c1c28ba7880`**，
也不碰统筹自己手工验证时留下的格子——那些格子里记的是 `BIG.md` / "验证截断标记"，
一看就不是本套测试造的）。需要留证据就加 `--keep-state`。

所有子进程都带 `PYTHONDONTWRITEBYTECODE=1`：不然 `python -m ctxiso` 和 `state.py`
会在 `ctxiso/__pycache__/`、`02-hubcore/tools/__pycache__/` 里写 `.pyc`，那也算改动保护区。
