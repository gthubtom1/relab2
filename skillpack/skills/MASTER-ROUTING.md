# reverse-skill PRIMARY 快路径

> `scripts/master-route.ps1` 与 `scripts/master-route.sh` 必须保持相同路由契约；平台只改变执行入口，不改变 routing semantics。

## 执行契约

```text
1. 先路由后动手
2. 输出 PRIMARY 路径 + 一句话依据
3. case-init / scope.md（ops/scope-contract）— auth 未 granted 禁止对目标 ACT
4. 指定 lead + specialist 角色（ops/role-map）
5. 立即打开 PRIMARY 的 SKILL.md → ACTION REQUIRED
6. 工具路径只认实测（`(Get-Command …)`）；缺则 bootstrap（仅 manifest 能力）
7. 过程追加 timeline / workitems；结论走 Evidence→Finding→Path
8. 未命中 → 读 routing.md 全表或提议新 skill
```

### Windows

```powershell
powershell -File skills\scripts\master-route.ps1 -Hint "<用户任务>"
# 默认写出当前项目的 work/route/latest/route-scope.md（历史自动归档到 work/route/<hash>/，不删除）；从其他目录调用时显式指定项目根
powershell -File skills\scripts\master-route.ps1 -Hint "<用户任务>" -ProjectRoot "C:\path\to\analysis-project"
powershell -File skills\scripts\case-init.ps1 -Hint "<用户任务>" -CaseName "my-case"
# case 默认写入当前项目的 work/<case>/；-PackageRoot 保持兼容，-ProjectRoot 优先级更高
powershell -File skills\scripts\case-init.ps1 -Hint "<用户任务>" -CaseName "my-case" -ProjectRoot "C:\path\to\analysis-project"
# 一次成型可 ACT（授权 + 目标 + 网络档）：
powershell -File skills\scripts\case-init.ps1 -Hint "<任务>" -CaseName "my-case" -AuthGranted -TargetUrl "https://target/" -NetworkProfile authorized_target_only
# 本地离线样本：
powershell -File skills\scripts\case-init.ps1 -Hint "offline apk" -CaseName "my-sample" -Preset offline-sample -Sample ".\app.apk"
# 冒烟：verify + 脚本解析 + 路由矩阵（含中文 Hint）
powershell -File skills\scripts\smoke.ps1
# ACT 前轻量 scope 门禁（未就绪 exit 2；-Force 为兼容参数，不能绕过硬门）
powershell -File skills\scripts\case-guard.ps1 -CaseRoot work\my-case
# Evidence 追加
powershell -File skills\scripts\append-evidence.ps1 -CaseRoot work\my-case -Id E-001 -Title "..." -ReproCommand "..."
python skills/case-review/scripts/review_case.py work/<case> --verify-hashes --strict
```

### Linux / macOS / Kali

不要求为了核心 route/case 流程安装 PowerShell：

```bash
bash skills/scripts/master-route.sh --hint "<用户任务>"
bash skills/scripts/master-route.sh --hint "<用户任务>" --project-root "/path/to/analysis-project"
bash skills/scripts/case-init.sh --hint "<用户任务>" --case-name "my-case"
bash skills/scripts/case-init.sh --hint "<用户任务>" --case-name "my-case" --project-root "/path/to/analysis-project"
# 本地离线样本：
bash skills/scripts/case-init.sh --hint "offline apk" --case-name "my-sample" --preset offline-sample --sample ./app.apk
# ACT 前轻量 scope 门禁（--force 为兼容参数，不能绕过硬门）：
bash skills/scripts/case-guard.sh --case-root work/my-sample
# 路由 parity：
bash skills/scripts/test-routing.sh
bash skills/scripts/test-bootstrap-manifest.sh
python skills/case-review/scripts/review_case.py work/<case> --verify-hashes --strict   # Windows（Linux/macOS/Kali 用 python3）
```

## 作战契约（ops）

| 文档 | 用途 |
|------|------|
| `ops/IDENTITY.md` | 我们是路由包，不是 Z3r0 平台 |
| `ops/scope-contract.md` | 启动门槛 |
| `ops/evidence-finding-path.md` | 证据链 |
| `case-review/SKILL.md` | Evidence 图审查与报告交接 |
| `ops/role-map.md` | 角色→skill |
| `ops/timeline-workitem.md` | 时间线与覆盖 |
| `ops/sandbox-profile.md` | 工具对照 |
| `ops/skill-supply-chain.md` | 安装外部 skill/MCP 的安全门闩 |
| `references/community-security-skills.md` | 社区 skill 生态（借鉴不并库） |
| `reverse-engineering/references/re-agent-workflow.md` | RE：triage→static→dynamic→synthesis |
| `pentest-tools/references/recon-pipeline.md` | 授权侦察流水线 + 证据门 |

## 优先级（高 → 低）

> 顺序必须与 `config/routing.json` 的 `priority` 数组一致。改路由只改 JSON，再改本表。`verify-routing-coherence.ps1` 会解析本表。

> R46–R49 是社区路由：`master-route.ps1` / `master-route.sh` 只给出 wrapper 入口
> （`skills/community/<hack-hub|ctf-hub|delivery|apk-extension>/SKILL.md`（本包未落地）），293 条适配明细必须另跑
> `python skills/scripts/community-route.py --hint "<同一句话>"` 才拿得到。
> 主框架输出 `confidence: low` / R0 / "No strong keyword hit" 时改走社区侧；
> 社区侧 `matched` 可用，`needs_review` 需确认，中文 `no_match`（0 候选）换英文关键词重查，
> `blocked`（budget_exceeded，exit 20）收窄重查。

| ID | 条件 | PRIMARY |
|----|------|---------|
| **R4** | DSL VM / fireye / 自定义 opcode VM | `reverse-engineering/dsl-vm-reverse/` |
| **R49** | APK capability extension / doctor / DEX-Dart-native advanced tooling | `community/apk-extension/` |
| **R1** | APK / smali / jadx / apktool | `apk-reverse/` |
| **R2** | IPA / iOS / Objection / MobSF / mobile | `mobile-reverse/` |
| **R3** | JS 签名 / 前端加密 / jshook / CDP | `js-reverse/` |
| **R30** | 浏览器扩展逆向 | `browser-extension-reverse/` |
| **R31** | macOS / Mach-O | `macos-reverse/` |
| **R33** | Go / Rust 二进制 | `go-rust-reverse/` |
| **R5** | .NET / dnSpy / de4dot / ConfuserEx | `dotnet-reverse/` |
| **R9** | 恶意样本 / YARA / 沙箱 | `malware-analysis/` |
| **R21** | 协议 / Protobuf / PCAP 协议 | `protocol-reverse/` |
| **R22** | Ghidra / 开源反编译 | `ghidra-reverse/` |
| **R45** | Binary Ninja / Binja / HLIL / MLIL / Binary Ninja MCP | `binary-ninja-reverse/` |
| **R6** | IDA / 反编译 / 反汇编深挖 | `ida-reverse/` |
| **R7** | radare2 / r2 | `radare2/` |
| **R8** | 固件 / binwalk / IoT / EMBA | `firmware-pentest/` |
| **R34** | 硬件调试口 / UART/JTAG | `hardware-security/` |
| **R28** | OT / ICS / 工控 | `ot-ics/` |
| **R17** | pwn / ROP / 堆栈利用 | `pwn-chain/` |
| **R16** | N-day / 补丁差分 | `patch-diff-exploit/` |
| **R18** | EDR / 免杀 / syscall | `edr-bypass-re/` |
| **R24** | Windows / AD / Kerberos / AD CS | `windows-ad/` |
| **R37** | 联邦身份 SAML/OIDC | `identity-federation/` |
| **R23** | 云 / 容器 / K8s | `cloud-k8s/` |
| **R35** | 数据库安全 | `database-security/` |
| **R25** | 取证 / 内存转储 / 时间线 | `digital-forensics/` |
| **R44** | OSINT / 威胁情报 / 公开 X IOC 补充 | `threat-intelligence/` |
| **R36** | 邮件 / 钓鱼分析 | `email-security/` |
| **R29** | Wi-Fi / 无线渗透 | `wifi-wireless/` |
| **R38** | RF / SDR 研究 | `radio-sdr/` |
| **R32** | 厚客户端安全 | `thick-client/` |
| **R26** | 代码审计 / SAST / Semgrep | `code-audit/` |
| **R27** | 威胁狩猎 / 检测工程 / 蓝队 | `threat-hunting/` |
| **R10** | 攻击链 / 红队 / 横向 / 完整渗透 | `attack-chain/` |
| **R46** | Web 专项注入 / 请求走私 / XXE / SSTI / 原型污染等 | `community/hack-hub/` |
| **R11** | Nmap / Nuclei / SQLMap / SRC / 渗透工具 | `pentest-tools/` |
| **R12** | API / GraphQL / BOLA / JWT 攻击 | `api-security/` |
| **R13** | SBOM / Trivy / 供应链 | `supply-chain-security/` |
| **R14** | LLM / Prompt 注入 / Agent 安全 | `llm-security/` |
| **R15** | bindiff / 符号迁移 / PDB | `binary-diff/` |
| **R19** | 浏览器/桌面自动化 | `browser-automation/` |
| **R40** | Case / Evidence 图审查 | `case-review/` |
| **R47** | CTF 社区入口 / 头脑风暴 / 题解体验 | `community/ctf-hub/` |
| **R20** | 报告 / writeup | `docs-generator/` |
| **R39** | 图表 / Mermaid / Graphviz / PlantUML / 架构图 | `diagram-generator/` |
| **R48** | 全栈交付 / 工作流编排 / 交付验收 | `community/delivery/` |
| **R41** | CTF / AWD / 靶场（单入口，不展开 40 个子技能） | `ctf-sandbox/` |
| **R50** | 浏览器端 JS 协议逆向 → 纯 Python 采集器 | `web-protocol-reverse/` |
| **R51** | 游戏客户端逆向 / 反作弊机制评估 | `game-reverse/` |
| **R52** | Linux 内核漏洞 / 利用链 / 缓解绕过 | `kernel-exploit/` |
| **R0** | 通用逆向 / 反调试 / OLLVM / 未知二进制 | `reverse-engineering/` |

未命中强关键词 → PRIMARY=`R0`，并提示打开 `routing.md`（歧义附录，不是第二套路由器）。
主框架 `low` / R0 时，用同一句话另跑 `python skills/scripts/community-route.py --hint "<同一句话>"`
查社区侧（R46–R49 的明细只在这里可见）。

## 边界

| 任务 | 处理 |
|------|------|
| 纯 CTF 多类型编排 | PRIMARY `ctf-sandbox/` → sidecar `../CTF-Sandbox-Orchestrator/` |

## 附：社区 wrapper 读表补注（只读文档，不改路由）

> 本附录只给读表者补线索，不改变上表顺序与任何路由逻辑。与 `config/routing.json` 不一致时以 JSON 为准。

- R46 / R47 / R49 正面判据：三条边界的**可操作判据 + 三包实际覆盖的完整清单**写在 `routing.md` 的「R46 / R47 / R49 正面判据（读表者照着判）」一节，判据依据全部是 `community/registry.json` 里的真实记录名。就地速查——
- **R46 vs R47**：两包 web 主题同名（sqli/xss/csrf/idor/ssrf/rce/business-logic/open-redirect/path-traversal/upload/info-disclosure/auth-jwt 各有一条），**主题判不了**。① 有 ctf/比赛/靶机/flag/这道题/新手/题解 语境 → R47；② 拿字典试路径 / 批量看存活 / 爬全站 / 指纹模板批量扫 / 丢给工具自动跑（`strix-ffuf` `strix-httpx` `strix-katana` `strix-nuclei` `strix-sqlmap` `strix-quick` `strix-standard`，**R46 的 103 条里没有任何对应记录**）→ R47；③ 题面**没有任何强锚点**（客户 / 这个站 / 这台机器 / 线上 / 内网 等**带所有权或环境**的词），只有服务器 / 接口 / 页面 / 登录 / 上传 这类**弱载体词**时不作数（弱载体词**不足以开 R46 也不足以关 F2**，走 ④），若连弱载体词都没有、只给了一个待分析的附件、样本或身份线索 → 按题型进 R47 的 `ctf-*` 专项（设备/交换机自己的取证不算，仍归 R46）；④ 其余按语气：待做的测试（试试/看看会不会/得确认影响）→ R47，已观察到的现象（居然…了/结果不对/读到了不该读的）→ R46；**同句两侧标记冲突时以收尾分句的动作为准（观察在前、下一步待做在后 → R47）**；④ 判 R46 但题面无强锚点时**不给默认方向**——既不默认 R47、也不默认 R46，改为补齐语境三问（详见 `routing.md`）：① 你自己的系统 / 资产 vs 别人递来的题目 / 样本 / 靶场，② 确认有没有问题 / 修掉 vs 证明能被利用 / 把利用链走通，③ 有没有比赛 / 靶场 / flag / writeup / 评分 / 新手入门语境（③ 有 → R47；③ 无 → 用 ①②）——**三问补不齐就标 `uncertain`、补问一句交回用户**，不许拿"缺强锚点"当理由硬猜 R47（实测 `work/readtable-mask2/`：这条兜底实际触发 27 次、判错 19、判对 8、准确率 29.6%，低于抛硬币；把默认方向翻成 R46 只是把"19 错 8 对"翻成"19 对 8 错"，净 +11 条全部来自迎合那批答案键的默认值、不是新信息，故撤掉）；⑤ **四条都不命中**同样标 `uncertain` 补问交回用户，不硬猜。**逐字型（F2 / F3 / P2）可按字面匹配；F4 是语境型，必须人工读语境，机械匹配会失效**（实测 F4 真实转化率 2/7）。
- **R49 vs R46 / R1**：切分轴是**"改的是谁的东西"**，不是"有没有反调试"。「我改完这个包还要装回去吗」要 → **R49**（重签名 / 重打包 / dex 字节级改写 / 摘广告摘SDK / 瘦身裁功能 / 改完装不上被拦 / 一改就崩 / 真机运行时观察 / 服务端认不认包）；只是要证明别人的 App 能被绕、不改包 → **R46**（`android-pentesting-tricks` / `ios-pentesting-tricks` / `mobile-ssl-pinning-bypass` 共 3 条）；只读静态分析（权限/组件/反编译 manifest）→ **R1**。R49 那 1 条记录 `-293` 的 `legacy_description` 明写拥有 `analyze their runtime and server-side behaviour`、`Frida hooking`、`anti-tamper`、`repack pitfalls`——旧文档"APK 反调试一律归 R46"的说法与此冲突，已按上述轴改正。**注意：真机/动态插桩下看它运行时干了啥、"挂上调试就装乖、要找检测点在哪"按 P2 判 R49**（原文 `analyze their runtime` + `Frida hooking` + `anti-tamper`）——`cases.json` 里那批 `expect_note` 声称的"R49 不覆盖 anti-debug / startup callbacks"已核实为错（该记录自带 `../community-raw/apk-reverse-source/references/detection-and-anti-analysis.md`），勿据此推翻 P2。
- R46 主题词表（“Web 专项…等”的“等”字展开，条目均可在 registry adapted_path 找到，**16 族 103 条逐族完整清单见 routing.md**）：反调试与保护绕过、混淆与虚拟机逆向、格式化串/堆/栈溢出与 ROP、浏览器漏洞、内核与容器逃逸、系统提权横移、macOS 进程注入与防护绕过、移动与桌面客户端渗透、AD 与 Kerberos、云与 K8s、协议与流量、密码与加密、合约与链（DeFi 攻击模式、智能合约漏洞）、内存取证与隐写、LLM、供应链（依赖混淆 / 源码管理）、侦察与业务逻辑。
- R48 边界：命中条件是交付编排语境（目标/排期/验收/跨角色工作流；覆盖模型训练/RAG/评测、产品、设计系统、security-engineer、devops/sre、数据分析、QA）。delivery 内 security-engineer 分支只做编排与验收，安全/逆向/渗透与真实部署动作交还 canonical。纯单点检测无交付动词不进 R48。
- 易混一句话：残留痕迹加样本/沙箱语境优先 R9，主机/磁盘/时间线还原走 R25；托管/.NET 暗示先判 R5，未点名混淆二进制走 R0；新手/组队/题解汇总走 R47，具体做题走 R41。

## 读序

```text
RULES.md → MASTER-ROUTING.md → PRIMARY SKILL.md
  → (可选) routing.md 三轴 / field-journal
  → `TOOLS.md` → bootstrap → ACT
```
