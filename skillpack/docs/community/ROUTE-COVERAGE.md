# 卡 Z — 社区路由关键词覆盖补齐（R46–R49）

改动只加不改：`skills/config/routing.json` 里 R46/R47/R48/R49 各新增一条 `keywords`，
既有模式、fallback 逻辑、其他路由、阈值一律未动。前车之鉴见
`docs/community/ROUTING-SIGNAL-U9.md`（`融合` 56/154 框式连接词，占比 36%，零区分度）。

## Lead 症状前后对照（同一句话，改前/改后）

```text
# 改前 2026-10-01（HEAD 实测）
powershell -File skills\scripts\master-route.ps1 -Hint "公司要上 CI/CD 交付流程"
  -> PRIMARY -> skills/reverse-engineering/SKILL.md   Label: General reverse-engineering | confidence: low
  -> route-scope.md: primary R0, secondary (none), NOTE: No strong keyword hit
# 改后（本卡）
powershell -File skills\scripts\master-route.ps1 -Hint "公司要上 CI/CD 交付流程"
  -> PRIMARY -> skills/community/delivery/SKILL.md   Label: Full-stack delivery workflow | confidence: high
```

社区路由同一句话改前改后一致（`matched / confidence 1.0 / e2e-feature-delivery`），
证明根因在 R48 关键词表，不在脚本。

对照组改后复测全对：`frida 脱壳安卓 APK`→R1(high)、`SQL 注入登录框怎么打`→R11(high)、
`分析一个加密勒索样本`→R9(high)、`burp 抓包改包`→R3(medium)。

## R46 新增说法与语料依据（`community/hack-hub`，103 记录）

| 说法 | 依据记录（hack-skills slug） | 计数 |
|---|---|---|
| `csrf` / `跨站请求伪造` | `csrf-cross-site-request-forgery`、`strix-csrf` | 2/103 |
| `xslt injection` / `xslt 注入` | `xslt-injection` | 1/103 |
| `open redirect` / `开放重定向` | `strix-open-redirect` | 1/103 |
| `不安全文件上传` / `文件上传漏洞` | `upload-insecure-files`、`strix-insecure-file-uploads` | 2/103 |
| `websocket 安全` | `websocket-security` | 1/103 |
| `反序列化` / `deserializ` | `deserialization-insecure` | 1/103 |
| `表达式注入` / `expression language injection` | `expression-language-injection` | 1/103 |
| `jndi 注入` / `jndi injection` | `jndi-injection` | 1/103 |
| `csp 绕过` | `csp-bypass-advanced` | 1/103 |
| `参数污染` / `parameter pollution` / `hpp` | `http-parameter-pollution` | 1/103 |

拒绝（见 DEVIATIONS）：`nosql`（SQLi 家族归 R11，加进 R46 会因优先级 R46>R11 抢走整个家族）、
`path-traversal`（裸词泛，跨多域）、`type-juggling`（单记录冷词，用户无此说法证据）。

## R47 新增说法与语料依据（`community/ctf-hub`，35 记录）

| 说法 | 依据记录（ctf-super-hub） | 计数 |
|---|---|---|
| `strix` | 21 条 `strix-*`（`strix-sql-injection`…`strix-xss`） | 21/35 |
| `solve challenge` / `挑战调度` | `solve-challenge`（CTF 挑战调度器） | 1/35 |
| `头脑风暴` / `brainstorm` / `自动分流`（mustAll 要求 CTF 语境） | `brainstorming`（触发名，直书头脑风暴）、`ctf-beginner-hub`（自动分流/头脑风暴再分流） | 2/35 |

拒绝：裸 `头脑风暴`/`新手入口`（无 CTF 语境时会吸走通用产品头脑风暴与 onboarding，
`普通头脑风暴会议怎么开` 已验证仍走 R0/low，属登记缺口）；裸 `ctf`（归 R41 靶场，R47 note 原意如此）。

## R48 新增说法与语料依据（`community/delivery`，154 记录）

| 说法 | 依据记录（ai-fullstack-delivery slug） | 计数 |
|---|---|---|
| `ci/cd`（`ci.?cd`） | `ci-cd-pipeline`、`ci-test-integration` | 2/154 |
| `交付流程` | `e2e-feature-delivery`（黄金集 `golden-delivery-cjk` 实证 交付流程→215） | 1/154（+社区 alias `delivery` 含 交付） |
| `devops` | `devops-engineer` 整目录技能 | 9+/154 |
| `pipeline` | `ci-cd-pipeline`、`rag-pipeline` | 2/154 |
| `dora` | `dora-metrics` | 1/154 |
| `milestone gate` / `里程碑门` | `milestone-gate` | 1/154 |
| `e2e feature` / `端到端交付` | `e2e-feature-delivery` | 1/154 |
| `prd` / `需求文档` / `用户故事` / `user story` | `prd-writing`、`user-story`（`product-manager` 目录） | 2/154 |

拒绝：裸 `交付`（U9 同源教训：29 候选同 wrapper 并列，无所属答案；`交付报告怎么写` 已验证仍走 R0，
不吸走报告域）；裸 `融合`（U9 STOPWORDS，36% 模板词）；`治理/governance` 类（U9 登记不可修）。

## R49 新增说法与语料依据（`community/apk-extension`，1 记录）

全部来自 `community-apk-reverse-community-293` 的 `keywords[]` 与 `legacy_description`
原文（`debloat, de-ad, patch, re-sign … smali or dex patching … repacking, ad or SDK
removal … surgical dex patching … anti-tamper`）：

| 说法 | 原文位置 |
|---|---|
| `debloat` / `de-ad` / `去广告` | `keywords[]` + desc 首句 |
| `sdk 移除` / `ad 移除` | desc `ad or SDK removal` |
| `re-sign` / `重签名` | `keywords[]` + desc 首句 |
| `dex patch` / `surgical dex` | desc `smali or dex patching`、`surgical dex patching` |
| `repack`（覆盖 repacking） | desc `repacking`（R1 只有中文 `重打包`，英文 `repack` 无归属，安全） |
| `anti-tamper` / `反篡改` | desc `anti-tamper` |

拒绝：裸 `patch`（会撞 R16 补丁差分）、裸 `frida`/`smali`/`重打包`（归 R1，
`frida 脱壳安卓 APK` 仍走 R1 已验证）、裸 `doctor`（无 APK 语境时泛，
既有 `apk.?doctor` 已覆盖 APK 场景，`doctor 预检工具链怎么跑` 登记为缺口）。

## 黄金集交叉用例（`skills/tests/golden-route.json`，26→39）

- `cross-fixed` ×4：每条路由一条（xslt / 头脑风暴 / CI-CD / re-sign），断言 master 与社区双侧。
- `cross-gap` ×4：只登记未修（bare 新手入口 / nosql 归 R11 / bare doctor / 文件上传社区中文无 token），
  断言当前行为，`why` 写明登记而非缺陷。
- `negative` ×5：S3→R23、架构图→R39、逆向报告→R0、LLM 提示词→R14、内存转储→R25，
  每个带 `master.not_in: [R46–R49]`。
- `test-golden-route.py` 新增 `call_master`（真跑 `master-route.ps1`，解析 `route-scope.md`，
  写系统临时目录，不污染仓库）与 `check_master`；既有断言零删减。

## 复现

```text
$env:PYTHONIOENCODING='utf-8'
powershell -NoProfile -ExecutionPolicy Bypass -File skills/scripts/master-route.ps1 -Hint "公司要上 CI/CD 交付流程" -OutDir work/cardZ-lab/after-cicd
& (Resolve-ReverseToolSpec -Name 'pyre').Command kills\scripts\test-golden-route.py
& (Resolve-ReverseToolSpec -Name 'pyre').Command kills\tests\run-ci-gates.py --runner python
```
