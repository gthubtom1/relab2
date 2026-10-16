# 失败 → 技能 回归表

> **这一层是打破「每次说改好了、下次真实做又出问题」的机械核心。**
>
> 没有这张表，「改好了」不可证伪 —— 只能验证形状，不能验证行为。
> 同行全部有：transilience 用「跑 benchmark → 找失败 → 诊断缺哪技术 → 写进技能 → 再跑」
> 迭代 ~15 轮把 CTF benchmark 打到 104/104；trailofbits 每技能带 graders；
> 上游 zhaoxuya520 有 175 条路由回归。本包此前 26 个门**全是格式/一致性门，0 行为门**。
>
> 建立日期：2026-10-14。

---

## 怎么用

1. **每完成一个真实项目，就加一条 case。** 不是"有空再加"——是交付的组成部分。
2. 每条 case 必填 `task_verbatim`（用户原话）与 `known_failures`（这次哪里卡了）。
3. `expect_chain` 是「期望的链路」，`known_failures` 是「实际发生的偏差」。
   **两者不写成"应该"和"实际"的对立，而是「下次该走到哪」与「这次走到了哪」。**
4. 跑 `python skills/tests/run-regression.py` 得到偏差 diff。

## 字段契约

```yaml
id: case-NNN-<短名>
date: YYYY-MM-DD
task_verbatim: <用户原话，不改写>
constraint: <用户明确声明的硬约束，含"我没有 X">
expect_chain: [<技能名或 references 路径>]   # 期望链路
expect_deliverable: <成品形态：路径 + 可运行/可构建的最小命令>
known_failures:                              # 这次实际发生的偏差
  - <一条一句，写"发生了什么"，不写"应该怎样">
lesson_refs: [<案例报告章节 / ADF 条目 / commit>]
status: open | resolved                       # resolved = 已改技能且复测通过
```

## 与门的关系

| 门 | 测什么 |
|---|---|
| `test-routing-e2e` | 对每条 case 跑 `master-route` + 让模型给"下一步用哪个技能"，比对 `expect_chain` |
| `test-trigger-rate` | 不依赖 case：每技能 8 正 + 8 近邻负例，各跑 3 次算触发率 |
| `test-assault-behavior` | 取一条真实 case 的 prompt，开新会话跑，按 `expect_*` 判分 |

---

## case 清单

| id | 日期 | 域 | status |
|---|---|---|---|
| `case-001-换肤6.9` | 2026-10-13 | 逆向·受保护目标 | open |
| `case-002-prng-upx` | 2026-10-13 | 逆向·脱壳+复刻 | resolved（正控） |
| `case-003-ctf-demo` | 2026-10-11 | CTF·pwn | resolved |
| `case-004-cf-access-sibling-subdomain-cookie-poisoning` | 2026-05-25 | 渗透·配置错误 + 代理协议面 | open |
| `case-005-windowsapps-python3-stub-false-green` | 2026-10-13 | 修 bug·假绿（0 字节别名） | open |
| `case-006-fix-bug-pwsh-host-and-r2-fallback` | 2026-08-17 | 修 bug·pwsh 宿主入口 + r2 回退（层层掩盖） | resolved |
| `case-007-pentest-mass-assignment` | 2026-05-16 | 渗透·Swagger 未授权 + Mass Assignment | open |
| `case-008-pentest-rate-limit-bypass` | 2026-05-26 | 渗透·XFF 限速绕过 | open |

（新增 case 按编号递增，见 `cases/` 目录。）

---

## 取证域：为什么现在空着，以及补上它要满足什么

**缺口不是"少写一条记录"，是本仓没有能当证据的真实取证素材。** 现有两条 pcap 都不够格：

| 产物 | 实际是什么 | 为什么不能当 case 素材 |
|---|---|---|
| `work/synth.pcap`（248B） | scapy 造的 TCP 载荷样本，用途是验证 `tshark -T fields` 能读出 `tcp.payload`（见 `../game-reverse/references/game-packet-interception.md`、`../reverse-engineering/references/windows-attack-surface.md`） | 工具夹具，不是案件 |
| `work/probe.pcap`（468B） | dumpcap 在本机 loopback 上抓的 `tcp port 17777` 共 10 包 | 日志里没有任何一次分析引用它 —— 孤儿产物，没有"谁因为什么分析它" |

`field-journal/` 现存 22 篇真实项目记录里，**取证域（内存转储 / E01 时间线 / IOC 追踪 / IR）一篇都没有**；`seed-002`、`seed-011` 是种子模板，不算真实项目。硬凑会直接违反本表"必须来自真实项目"的立表前提。

### 准入条件（可判定）

补 `case-006`（编号已为此预留）时，**必须能指到一份真实证据本体**，下列四类至少命中一类：

| 证据形态 | 合格样例 | 现状 |
|---|---|---|
| 内存转储 | `*.dmp` / `*.raw` / `*.vmem` + 采集命令 + SHA256 | 无 |
| 磁盘镜像 / 时间线 | `.E01` / `.dd`，或落地文件时间线导出 | 无 |
| 真实案件 PCAP | 带上下文（采集点、目标、协议）的抓包，非夹具 | 无（两条 pcap 都是夹具 / 孤儿） |
| 工具产物 | Volatility 插件输出、`tshark` 统计导出、`log2timeline` 输出 | 无 |

### 落 case 时必填的字段（照上表五条 case 的字段风格）

| 字段 | 取证域的具体要求 |
|---|---|
| `id` | `case-006-<短名>`（编号已预留） |
| `date` / `domain` | `domain: forensics`（本表四战场之一，见 `../ops/binary-model.md`） |
| `task_verbatim` | 用户原话；日志没留原话时照 `case-007`/`case-008` 的写法**标注来源**，不许改写 |
| `constraint` | 证据只读 + 保全哈希 + 时区 + chain of custody（对齐 `../digital-forensics/SKILL.md` §1 保全清单） |
| `expect_chain` | 至少含 `digital-forensics`、`digital-forensics/references/forensics-triage.md`、`ops/evidence-finding-path.md`、`docs-generator`、`case-review` |
| `expect_deliverable` | 成品形态 + 落点 + 最小复现命令（如 `vol -f mem.dmp windows.pslist`，或 `tshark -r case.pcap -T fields -e <字段>`） |
| `known_failures` | **必须非空**：时区/采集命令没记导致时间线不可用、哈希未复核导致证据与结论脱节、工具版本差异导致插件输出不可比 —— 这三类是取证域最常见的真实失败。`run-regression.py` 只在显式写"正控/无"时才放行空 `known_failures`，**取证 case 不走这条豁免** |
| `lesson_refs` | 日志路径 + Volatility/tshark 输出文件 + 证据哈希清单 |
| `status` | 首次落盘只能 `open`；同一案件证据链复测通过后才改 `resolved` |
