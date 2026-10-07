# T18 黄金路由评测（Golden Route）

Owner：T18。依据：规范 §18 T18 卡、§17.12 / §17.25，以及 wave 5 卡 L 的
[ROUTING-SIGNAL-U9.md](ROUTING-SIGNAL-U9.md) 结论。

目标：把"智能体以后能完美/快速/准确路由"变成**可回归的评测**，而不是再调一次规则。
本文件 + `skills/tests/golden-route.json` + `skills/scripts/test-golden-route.py`
就是那套评测；`skills/scripts/test-community-route.py` 里的 `golden_u9_pins()`
把其中 U9 钉子接进 CI（门数不变）。

## 1. 落地形态（三件，不多不少）

| 件 | 位置 | 说明 |
|---|---|---|
| 黄金数据集 | `skills/tests/golden-route.json` | 26 用例，每条含 cwd、运行时、依赖、期望 JSON/退出码、`why` 实测说明 |
| 评测跑器 | `skills/scripts/test-golden-route.py` | 走真实 CLI（含 exit code），报正向 + 负向 + U9 + handoff + budget；全过才 exit 0 |
| CI 钉子 | `skills/scripts/test-community-route.py :: golden_u9_pins` | 只加法：断言 6 个 U9 pin；既有断言一行未动 |

冻结遵守：未改 `routing-signals.json`、`community-route.py`、`registry.json`、
`community-raw/**`、`skills/config/*.json`；未删/未放宽任何既有断言；未动阈值；
未新增 CI 门（门数保持 20）。

## 2. 数据集：26 用例

所有用例统一：cwd=`D:\Project\skills-hub\integrated-skill-hub`，
运行时=`D:\EXE\python\python.exe`（先 `$env:PYTHONIOENCODING='utf-8'`），
依赖=标准库 only。调用形如
`python skills/scripts/community-route.py --hint "<hint>" [--source <s>] --json`。

### 2.1 正向必须命中（13）

| 用例 | hint | source | 期望 top | 状态/exit |
|---|---|---|---|---|
| golden-ctf-en | CTF APK smali | ctf-super-hub | ctf-reverse/SKILL.md | matched/0 |
| golden-ctf-cjk | 磁盘镜像 隐写分析 事件日志 证据恢复 | ctf-super-hub | ctf-forensics/SKILL.md | matched/0 |
| golden-ctf-crypto-mixed | Coppersmith LWE 格攻击 填充预言机 | ctf-super-hub | ctf-crypto/SKILL.md | matched/0 |
| golden-api-en | SQL injection login form | hack-skills | skills/sqli-sql-injection/SKILL.md | matched/0 |
| golden-api-cjk | 服务端请求伪造 | hack-skills | skills/ssrf-server-side-request-forgery/SKILL.md | matched/0 |
| golden-api-auth | JWT authentication | hack-skills | skills/api-auth-and-jwt-abuse/SKILL.md | matched/0 |
| golden-apk-en | frida android | — | skills/apk-reverse/SKILL.md（wrapper apk-reverse-community） | matched/0 |
| golden-delivery-en | CI CD pipeline 部署 | ai-fullstack-delivery | workflows/devops-engineer/skills/ci-cd-pipeline/SKILL.md | matched/0 |
| golden-delivery-cjk | 交付流程 需求评审 | — | workflows/fullstack-engineer/skills/e2e-feature-delivery/SKILL.md | matched/0 |
| golden-signal-tool | BloodHound DCSync shadow credentials | hack-skills | skills/active-directory-acl-abuse/SKILL.md | matched/0 |
| golden-desc-only | burp suite zap | — | 含 workflows/security-engineer/skills/web-vulnerability/SKILL.md | matched/0 |
| golden-kerberos | kerberos | — | skills/active-directory-kerberos-attacks/SKILL.md | matched/0 |
| golden-plural-pcaps | pcaps | hack-skills | 含 skills/traffic-analysis-pcap/SKILL.md | matched/0 |

中英文 × CTF/API/APK/Delivery 全覆盖；`golden-delivery-en` 同时是 U9 别名归属修复
（pipeline→188 ci-cd-pipeline 而非 RAG 记录）的正向守卫。

### 2.2 低置信度仍可达（2）+ 歧义（1）

| 用例 | hint | 期望 |
|---|---|---|
| golden-lowconf-mimikatz | mimikatz | needs_review/10，含 active-directory-acl-abuse，confidence=0.0（signal-only 按设计不买 confidence） |
| golden-lowconf-lattice | lattice（hack-skills） | needs_review/10，含 lattice-crypto-attacks |
| golden-ambiguous-jwt | JWT（无 filter） | needs_review/10，3 wrapper，reason=ambiguous_tie，candidates 非空；`--limit` 藏不住并列由既有门断言 |

### 2.3 错误输入正确拒绝（4）

| 用例 | hint | 期望 |
|---|---|---|
| golden-err-blank | 空白 | missing_input/21，missing_fields=["hint"] |
| golden-err-punct | !!! | missing_input/21 |
| golden-err-stopword | workflow | missing_input/21（兼 D5 修复锚点） |
| golden-err-overbudget | web api security | blocked/20，failure_reason=budget_exceeded，带 budget/required_action/confirmation（68 refs / 4 wrappers，拒收不截断） |

### 2.4 U9 登记项固化（6，期望行为而非缺陷）

| 用例 | U9 结论 | 黄金断言 |
|---|---|---|
| u9-governance-word-governance | 不可修（义项碰撞，真 DeFi 领域词） | matched/0，top=skills/defi-attack-patterns/SKILL.md |
| u9-governance-word-wrapper | 不可修（真 PHP stream wrapper 领域词） | matched/0，top=skills/path-traversal-lfi/SKILL.md |
| u9-alias-delivery-cjk | wrapper 层不可修；reference 层已归位 215 | **分层断言**：reference_top=workflows/fullstack-engineer/skills/e2e-feature-delivery/SKILL.md（U9 修复保持），wrapper_top=ai-fullstack-delivery（单 wrapper 内 29 候选，任何排序都无法卸任，不许用停词删掉刚归位的正确 top） |
| u9-hypernym-endpoint-top | 不可修（11 候选描述并列，重排只搬红点） | matched/0，top=skills/401-403-bypass-techniques/SKILL.md |
| u9-hypernym-application-top | 不可修（14 候选，裸词无所属答案） | matched/0，top=skills/android-pentesting-tricks/SKILL.md |
| u9-absence-s3-bucket | 正确行为（语料无 S3 能力，不得编造关键词） | needs_review/10，0 wrapper，0 candidate |

任一 pin 的 top/status 移动 → 黄金变红，**必须先 consciously 修订 U9**，不许只改本文件跟随。

## 3. 本轮实测报告（2026-10-01，树上真实跑出）

黄金跑器（`test-golden-route.py`，exit 0）：

```text
positive routed:        13/13 = 1.0000
low-confidence present: 2/2  = 1.0000
ambiguous held:         1/1  = 1.0000
error input refused:    4/4  = 1.0000  （3 missing_input + 1 budget blocked）
U9 pins hold:           6/6  = 1.0000
handoff complete:       26/26          （分状态 4.7 字段逐条校验）
within context budget:  26/26          （预截断计数，见 §4）
```

诱饵集对照（`test-community-decoys.py --report`，未动）：

```text
decoy cases:    25/30 = 0.8333   (gate >= 0.50)
positive cases: 27/27 = 1.0000
combined:       52/57 = 0.9123   (gate >= 0.75)
5 条具名 over-trigger 与 U9 登记的 5 条一致（交付字已归位 215，wrapper 层仍登记）。
```

质量结论**不是**单一命中率，而是并列的五句话：正向 13/13 全中且无错误拒绝；
错误输入 4/4 正确拒绝（含超预算拒收）；歧义/低置信 3/3 保持 needs_review
（`needs_review` 一条未删）；U9 登记 6/6 按期望行为钉住；handoff 与 budget 26/26。

## 4. Ambiguity 与 context budget（对 T11）

预算（`LOADING-BUDGET.md` §1）：`MAX_WRAPPER_CANDIDATES=5` /
`MAX_TOTAL_REFERENCES=50` / `REFERENCE_LIMIT=3`；`MIN_CONFIDENCE=0.35` /
`NEAR_TIE_DELTA=0.20` 不动。

测量方法：取 payload `budget.total_references` / `budget.wrapper_candidates`
（**预截断**计数值——展示层每 wrapper 只给 3 个，数展示数会让预算检查恒真，
此处特意不用）。

- 26 用例中 25 个 admitted 用例全部在预算内； admitted 高水位为
  `golden-delivery-en`（CI CD pipeline 部署）：预截断 31 refs / 1 wrapper
 （预算 50 refs / 5 wrappers，展示层只给 3 条）。单 wrapper 内候选多是别名折叠
  的正常形态，预算看的是总量不是展示数。
- 唯一超预算的是 `golden-err-overbudget`（68 refs / 4 wrappers），引擎行为为
  blocked + budget_exceeded + exit 20，并给出收窄指引与人工确认项——**拒收不断尾**，
  符合 T11 超预算行为定义。
- Ambiguity：`golden-ambiguous-jwt` 3 wrapper 置信 1.0 并列，
  reason=ambiguous_tie，`--limit=1` 藏不住（既有门断言）；歧义判定在 `--limit`
  生效前，调用方无法靠取 1 条掩盖并列。

## 5. 复现

```text
$env:PYTHONIOENCODING='utf-8'
D:\EXE\python\python.exe skills/scripts/test-golden-route.py
D:\EXE\python\python.exe skills/scripts/test-community-route.py
D:\EXE\python\python.exe skills/scripts/test-community-decoys.py --report
D:\EXE\python\python.exe skills/scripts/test-route-ranking.py
D:\EXE\python\python.exe skills/scripts/verify-routing-signals.py --check
D:\EXE\python\python.exe skills/tests/run-ci-gates.py --runner python
```

## 6. 危险样本掩码自检

本卡数据集的 hint 全是良性路由词（工具名、技术名词、中文领域词、标点与超预算
长 hint），不含云密钥/私钥/注入句/PE-ELF 魔数/明文端点/symlink 目标——掩码条款
空真。交付前仍跑全树扫描自检（见回报 ACCEPTANCE）。

## 7. 还不能下结论的维度（诚实登记）

1. **真错输入**：测了空白/纯标点/停用词/超预算四类并全部定案；**typo、大小写
   抖动、中英混写错词、对抗式长 hint**（除 web api security 这一条外）尚未建
   golden，用例缺口记在这里，不声称"错误输入已覆盖"。
2. **Hint 空间覆盖**：26 用例相对全部 hint 空间是抽样；`ai` 之外的 7 个
   short_token 字面、`ctf-super-hub` 等来源标识字面仍无 golden 用例
   （继承 ROUTE-RANKING §8 的已知缺口）。
3. **性能/UX 侧**：本卡只钉"路由对错"，单次查询耗时、展示截断后的二级加载
   体验未进入黄金断言（属 T11 执行面，数值 owner 另认）。
4. **U9 pin 的方向性**：5 条 pin 的是"当前 over-trigger 的 top 是谁"；若未来
   出现有 relevance 模型的排序方案，正确动作是修订 U9 + 同步 pin，不是调参
   让 pin 变绿——pin 的失败信息里已写明这条。
