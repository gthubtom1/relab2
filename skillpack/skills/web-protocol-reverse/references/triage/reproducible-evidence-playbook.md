# 可复现证据手册（Reproducible Evidence Playbook）

> **来源声明**：本文改编自外部仓库 `aoyunyang/spider-king-skill`（MIT License）的 `reproducible-evidence-playbook.md`。原始内容为英文原文，此处译为中文并按本包六段式规范重排；技术术语保留英文原词并附中文。**改编要点：源文档假定四个 `scripts/*.py` 存在（`evidence_normalizer.py`、`transcript_diff.py`、`practice_lab.py`、`forward_test_report.py`），本包内没有 `scripts/` 目录，这四个脚本一个都不存在。本文已逐个标注并给出本机可用的替代做法。**
>
> **什么时候用**：
>
> - 一条经验应当**跨目标**存活时
> - 成功与失败的会话链在最后一个请求上**看起来一模一样**时
> - 需要把真实抓包落盘、但**不能连可复用秘密一起发布**时
>
> **平台与本机状态**：Windows 10 x64。`python 3.12`（`D:\EXE\python\python.exe`）、`mitmdump`（`D:\EXE\python\Scripts\mitmdump.EXE`）、`tshark`（`D:\Tools\Wireshark\tshark.exe`）本机可用。**本包无 `scripts/` 目录**，见下方「脚本可用性对照表」。

---

## 适用信号（Recognition signals）

- 「成功和失败两条链，最后一个请求的哈希一样」
- 「我想把这次的抓包分享出去，但里面有 cookie」
- 「这个经验值得沉淀成手册，但怎么证明它不是偶然」
- 「上次那条经验，下次用不上了」

## 前置（Entry conditions）

- **一条成功 transcript** 和 **一条失败 transcript**（同一会话假设下）
- 原始抓包：HAR 或 transcript JSON
- 一个任务本地的**高熵 HMAC 密钥**（用于让样本保持可关联，又不泄露内容）

---

## 脚本可用性对照表（⚠️ 本机现状）

| 源文档脚本 | 本包内是否存在 | 本机替代做法 |
|---|---|---|
| `scripts/evidence_normalizer.py` | ❌ **不存在** | 见下面「规范化证据」一节的替代三步 |
| `scripts/transcript_diff.py` | ❌ **不存在** | 见「找第一处分歧」一节的替代 diff 方法 |
| `scripts/practice_lab.py` | ❌ **不存在** | 见「本地演练靶场」一节的说明 |
| `scripts/validate_skill.py` / `scripts/forward_test_report.py` | ❌ **不存在** | 见 `./forward-testing-playbook.md` 的本机化说明 |

> **不要在任何报告或聊天里声称运行过这四个脚本。** 本包没有它们。

---

## 步骤（Working method）

### 核心规则（Core rule）

**不要仅凭文字就把一条实践经验「升级」为可复用经验。**

一条可复用经验需要：

- 一个最小工件，或一个**确定性生成器**
- 一个预期的成功 oracle（成功基准）
- 一个**决定性的负控**（negative control）
- 一个明确的失败边界
- **没有**活的凭据、cookie、token 或账号数据

### 先规范化证据（Normalize evidence first）

> **本机替代**：本包没有 `evidence_normalizer.py`。下面是等效的三步手工流程，用本机可用工具即可完成。

```powershell
# 第一步：把 wire 抓包落盘
D:\EXE\python\Scripts\mitmdump.EXE --listen-port 8899 --save-stream-file flow.mitm
# 或直接读已有 pcap
D:\Tools\Wireshark\tshark.exe -r flow.pcapng -Y "http.request" -T fields -e frame.number -e http.request.method -e http.request.full_uri
```

```powershell
# 第二步：生成高熵任务本地 HMAC 密钥，写入任务本地文件（不要写在命令行参数里）
D:\EXE\python\python.exe -c "import secrets; k=secrets.token_hex(32); open('task_hmac_key.txt','w').write(k); print('wrote task_hmac_key.txt, hex chars =',len(k))"

# 在当前 shell 会话里指向它（`$env:` 不会传给子进程，必须在父 shell 设置）
$env:EVIDENCE_HMAC_KEY = (Get-Content -Raw task_hmac_key.txt).Trim()
```

```powershell
# 第三步：自己写一个小规范化脚本，落盘到任务目录
#   js_reverse_cache/tasks/<task-id>/normalize_evidence.py
#   产出 analysis/proof_manifest.json（按键 HMAC-SHA-256 指纹，不含原文）
D:\EXE\python\python.exe js_reverse_cache\tasks\<task-id>\normalize_evidence.py capture.har evidence.json --hmac-key-env EVIDENCE_HMAC_KEY
```

> **命令里的 `<task-id>` 是占位符，请替换成你实际的 task-id。上面这一步在本机未实跑过（脚本需自写），标注为「未在本机验证」。**

**规范化后的包必须保留**：

- 有序的会话链步骤
- 请求方法与 URL 形态
- **有序且允许重复**的请求/响应头
- body 字节长度，以及**带密钥**的 HMAC-SHA-256 指纹
- 重定向与响应状态
- 状态写入及其作用面
- 一个**带密钥**的源工件指纹

**公开默认包**保留结构字段名、作用域、顺序、长度、以及稳定的 HMAC 指纹。它**去掉**原始 body，以及**不带密钥**的源或 body 哈希 —— 因为低熵密码、PIN、OTP 可以被拿去对公开的 SHA-256 做穷举。

已知的敏感字段与可识别的敏感值会被化名（pseudonymize）。但清单本身**故意要求发布前复核**，而不是声称任意输入都天然无秘密。

> **原始抓包只保留在任务本地被忽略的秘密存储里。**

**关于密钥传递**：用高熵、任务本地的密钥。优先用「环境变量」或「密钥文件」；把密钥直接写在命令行参数里会出现在进程列表中，**只用于一次性测试**。

**只有**当本地分析明确需要比对原始 source/body 时，才加「包含原始哈希」开关。**该开关会写出不带密钥的 SHA-256，因此绝不能用于公开包或发布清单。**

### 找第一处分歧（Find the first divergence）

> **本机替代**：本包没有 `transcript_diff.py`。下面是等效做法。

当最终请求相同、但验收结果不同时，**按顺序**比对整条链：

```powershell
# 用 tshark 列出成功链与失败链的有序请求，逐行人工/脚本比对
D:\Tools\Wireshark\tshark.exe -r success.pcapng  -Y "http.request" -T fields -e frame.number -e http.request.method -e http.request.full_uri > success_reqs.txt
D:\Tools\Wireshark\tshark.exe -r failure.pcapng  -Y "http.request" -T fields -e frame.number -e http.request.method -e http.request.full_uri > failure_reqs.txt

# 第一处不同出现在第 N 行 —— 从那里开始查
D:\EXE\python\python.exe -c "import sys;a=open('success_reqs.txt',encoding='utf-8').read().splitlines();b=open('failure_reqs.txt',encoding='utf-8').read().splitlines();[print('FIRST DIVERGENCE at line',i+1,'\n  OK :',a[i],'\n  BAD:',b[i],'\n  break') for i,(x,y) in enumerate(zip(a,b)) if x!=y] or print('no divergence in common prefix')"
```

**从报告出的第一处分歧开始查。** 在调后面的 signer、body 或 verifier 字段之前，先查**写入方**和**第一个下游消费者**。

> **不要**为了让 diff 更小就去排序头列表，或把重复的头合并成字典。

一个更早的 `Set-Cookie`、重定向、sidecar 响应、计数器或存储写入上的差异，**足以解释失败**，即使最后的 body 哈希完全相同。

### 本地演练靶场（Exercise the local practice lab）

> **本机现状：本包没有 `practice_lab.py`。**

源文档用的是一个确定性回环服务，四个离线用例覆盖：精确 body 字节与重复头顺序、同会话 challenge 与 bootstrap 状态、有序前缀 + Base64 + zlib + JSON 响应解码、以及会切换路由族的分页。

**本机替代做法**（同样有效，且不必依赖不存在的脚本）：

1. **自己在任务目录下搭一个最小回环服务**（标准库 `http.server` 即可），四个用例照上面四条实现
2. 每个用例**必须同时包含一个正向 oracle 和一个负控**
3. **只通过正向路径是不够的** —— 一个弱校验器能让坏逻辑看起来是对的

```powershell
# 自建靶场（脚本需自写，以下命令未在本机验证）
D:\EXE\python\python.exe js_reverse_cache\tasks\<task-id>\practice_lab.py --self-test
```

> **不需要开浏览器**。这个靶场是确定性夹具（fixture），不是活目标。

### 存一张经验卡（Deposit an experience card）

用 `../contract/experience-card-schema.md` 作为权威的机器可读契约。在调查过程中，下面这块精简笔记可以先留在 `../../../../examples/ctf-demo/report/report.md` 里：

```text
症状：
最初错误的假设：
决定性证据：
单变量实验：
第一处分歧的状态迁移：
正向 oracle：
负控：
最终不变量：
失败边界：
夹具或生成器路径与哈希：
```

> **这张笔记还不是被提升的卡片。** 把一次性的发现放在任务局部的 `experience-candidate.json`；**只有在经过两个独立任务、且所有 schema 门都过了之后**才提升。只有当同一个操作在重复案例中一直有用时，才加一篇通用手册或一个确定性脚本。

---

## 判据（Completion criteria）

只有以下**全部**成立，才可以说「这条经验已经落库」：

1. **夹具无秘密**：没有凭据、cookie、token、账号数据
2. **负控因为「预期的那个原因」而失败** —— 不是因为别的地方坏了
3. **正向 oracle 从一次干净运行中通过**
4. **明确写出了失败边界**
5. **已记录的包 SHA-256 与清单 SHA-256 与实际落盘文件一致**

**另外三条本机纪律：**

6. **没有运行过 `evidence_normalizer.py` / `transcript_diff.py` / `practice_lab.py` / `forward_test_report.py`**（本包内不存在这四个脚本）—— 报告里不得出现它们的「实测输出」
7. **所有带 HMAC 指纹的证据包都用了高熵任务本地密钥**，且密钥本身没有被写进报告
8. **原始抓包只在任务本地**，公开包不含不带密钥的 source/body 哈希

判据的反例（**以下情况算没落库**）：

- 负控失败了，但原因是网络超时
- 只有正向 oracle 通过，没有负控
- 报告里出现了「按 `practice_lab.py` 自测通过」这种无法验证的断言（本机无此脚本）
- 公开包里带了不带密钥的 SHA-256，而 body 里有低熵秘密

## 常见坑（Common traps）

- **只有正向 oracle**。弱校验器会让坏逻辑看起来对。
- **负控因为错误的原因失败**。这比没有负控更危险。
- **为了让 diff 更小而排序/合并头**。你会丢掉真实差异。
- **把不带密钥的 SHA-256 放进公开包**。低熵秘密可被穷举。
- **HMAC 密钥写在命令行参数里**。进程列表可见。
- **把一次性的发现直接提升为手册**。先经两个独立任务 + schema 门。
- **混淆 artifact-led 证据复用与 live 验收**。前者不能证明「线上现在还这样」。

## 相关（Related）

- `./minimal-verifiable-facts-playbook.md` —— 把经验压成 5–15 条可复检事实
- `./forward-testing-playbook.md` —— 行为类主张的外部前向运行（本包内相关验证脚本同样不存在）
- `./positive-sample-hygiene-playbook.md` —— oracle 本身的可信度分级
- `./troubleshooting-playbook.md` —— 「成功与失败链最后一步看着一样」的实际排查
- `./verifier-replay-playbook.md` —— transcript 清单与下游消费者契约
- `../contract/experience-card-schema.md` —— 经验卡的机器可读契约
- `../contract/project-artifact-contract.md` —— `analysis/proof_manifest.json` 的落盘约定

---

## 源文档勘误与本机化改动

1. **⚠️ 四个脚本在本包内全部不存在**。源文档的「Normalize evidence first」「Find the first divergence」「Exercise the local practice lab」「Validation」四节分别调用 `evidence_normalizer.py`、`transcript_diff.py`、`practice_lab.py`、`forward_test_report.py`。**本包没有 `scripts/` 目录**。已在开头加「脚本可用性对照表」，并在每一节给出本机可执行的替代做法。
2. **⚠️ 替代做法中标注「未在本机验证」**：第三步的 `normalize_evidence.py` 与演练靶场的 `practice_lab.py` 都需要用户自己写。给出的命令行**没有在本机实跑过**，已明确标注。
3. **源文档的 HMAC 论证被强化保留**。原文说低熵密码/PIN/OTP 可以被拿去对公开 SHA-256 做穷举 —— 这是本文最有价值的安全论据，已原样保留并加粗。
4. **源文档 `--include-raw-hashes` 与 `--hmac-key` 的警告已保留**，但按本机情形做了措辞调整（本包无对应脚本）。
5. **交叉引用路径失效**：源文档引用 `../contract/experience-card-schema.md`，实际在 `references/contract/`。已改为 `../contract/experience-card-schema.md`。
6. **源文档 `--proof-manifest` 一段（schema v2）已略去**。因为该 schema 属于那个不存在的脚本的输出格式，保留会诱导读者去找不存在的文件。取而代之的是保留了「记录包路径 + 包 SHA-256 + 清单路径 + 清单写入后 SHA-256」这一**行为要求**（判据第 5 条）。
7. **源文档缺判据段**（只有 `## Completion gate` 一句）。已扩写为完整判据段（5 + 3 条），并把「不得声称运行过不存在的脚本」写成硬性本机纪律。