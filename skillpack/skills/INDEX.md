# reverse-skill 技能导航索引

> 本文件由 `skills/scripts/extract-summaries.ps1` 自动生成，**请勿手改**。
> 修改摘要请编辑对应模块 `SKILL.md` 的 frontmatter `description`，然后重跑脚本。

## 模块总览

| 模块 | 摘要 |
|------|------|
| [api-security](api-security/SKILL.md) | API 安全测试：REST/GraphQL/WebSocket 接口发现、JWT/OAuth、BOLA/IDOR/BFLA 越权。用于：接口越权、JWT 弱密钥、GraphQL 内省。 |
| [apk-reverse](apk-reverse/SKILL.md) | APK 逆向：jadx/apktool 解包、改 smali/AndroidManifest、重打包、Frida hook。用于：APK 逻辑、装不上、去广告、查服务器、root 检测。 |
| [attack-chain](attack-chain/SKILL.md) | 多阶段攻击链编排：侦察、初始访问、提权、横向、影响评估。用于：完整渗透、外网打到域控、HW 演练、webshell 下一步。 |
| [binary-diff](binary-diff/SKILL.md) | 二进制差分/符号迁移：旧版符号迁到新版、更新后找偏移、内核缺 PDB。用于：更新后地址变了、新版 PDB 下不到、旧版函数名迁移。 |
| [binary-ninja-reverse](binary-ninja-reverse/SKILL.md) | Binary Ninja 逆向：HLIL/MLIL/LLIL 数据流、xrefs、类型与重命名、Python API。用于：点名 BN 看函数逻辑、跟调用链、与 IDA/Ghidra/radare2 交叉验证。 |
| [browser-automation](browser-automation/SKILL.md) | 浏览器/桌面 GUI 自动化：Playwright/agent-browser 点击/填表/截图/登录；OpenReverse 操作 Windows GUI。用于：填表、爬页面、登录截图、提交 payload。 |
| [browser-extension-reverse](browser-extension-reverse/SKILL.md) | 浏览器扩展逆向：crx/xpi 解包、manifest 权限、service_worker、content script、流量与 IOC。用于：插件是否偷数据、后台干了什么、权限给多了。 |
| [case-review](case-review/SKILL.md) | case 包只读审查：scope 就绪度、Evidence 链可追溯、artifact SHA-256、rebuild/update 表核对。用于：交报告前审 case、证据链全不全、复核哈希。 |
| [cloud-k8s](cloud-k8s/SKILL.md) | 云/容器/K8s 安全评估：元数据 SSRF、IAM 越权、公开桶、容器逃逸、K8s RBAC。用于：云元数据 SSRF、容器逃逸、集群 RBAC。 |
| [code-audit](code-audit/SKILL.md) | 白盒源码审计：PR/差分审查、Semgrep/CodeQL/Bandit/gosec SAST、注入点、鉴权缺失。用于：审代码注入、PR 合前过安全、IDOR/多租户。 |
| [code-review](code-review/SKILL.md) | 逐行评审 diff：判断改动是否提升 code health、是否足够小自包含，按设计/功能/复杂度/测试给结论。用于：帮我审这个 PR、这段改动能不能合。 |
| [community-apk-extension](community/apk-extension/SKILL.md) | APK 逆向能力扩展入口。用于：拿到新版 apk-reverse 的 doctor、capability matrix、DEX/Dart/native、Frida、重打包和证据脚本时，接回 canonical apk-reverse 的 case 与工具门。 |
| [community-ctf-hub](community/ctf-hub/SKILL.md) | CTF 任务分诊与教学适配层。用于：要自动分流、头脑风暴、比赛切题和题解输出，接到 skill 的 scope、case、证据与 CTF sandbox 流程时。 |
| [community-delivery-workflow](community/delivery/SKILL.md) | 全栈交付编排适配层。用于：按目标、输入、角色工作流、验收与文档沉淀推项目，并在安全/逆向阶段交还 skill 路由时。 |
| [community-hack-hub](community/hack-hub/SKILL.md) | Web/API/主机/应用安全专题适配层。用于：把 hack-skills 的分类与深度 playbook 接到可执行路由、授权 scope、case 证据和报告合同时。 |
| [ctf-sandbox](ctf-sandbox/SKILL.md) | CTF/AWD 靶场入口：case-init 门禁 + sidecar orchestrator 选竞赛子技能。用于：打 CTF、AWD、比赛切题、靶场题、pwn 怎么做、环境跑起来。 |
| [database-security](database-security/SKILL.md) | 数据库安全评估：0.0.0.0 绑定、弱口令、权限过大、危险功能（xp_cmdshell/UDF）、NoSQL 注入。用于：库是否暴露、被脱库、Redis 写文件提权。 |
| [design-slice](design-slice/SKILL.md) | 把新功能切成端到端最薄闭环再横向扩张：先跑通一条最小链路，接口先定契约，不先搭大架构。用于：不知从哪切、要 walking skeleton。 |
| [diagram-generator](diagram-generator/SKILL.md) | 把笔记或代码画成 Mermaid/PlantUML 文本图（流程图、时序图、架构图、ER 图）。用于：帮我画个流程图、时序图怎么画、Mermaid 架构图。 |
| [digital-forensics](digital-forensics/SKILL.md) | 数字取证与应急响应（IR）：内存转储 Volatility、E01 磁盘时间线、PCAP 溯源、IOC 提炼。用于：看 mem.dmp、电脑中招怎么溯源、PCAP 有啥异常。 |
| [docs-changelog](docs-changelog/SKILL.md) | 让代码改动与 README、文档、changelog 保持同步，避免文档 stale 或留下孤儿说明。用于：改了接口要不要更新文档、补个 changelog、文档跟代码对不上了。 |
| [docs-generator](docs-generator/SKILL.md) | 把逆向/渗透/CTF 结论写成技术文档并落盘（渗透测试报告、CTF writeup、README、API 文档）。用于：帮我写份渗透测试报告、出个 writeup、补个 README。 |
| [dotnet-reverse](dotnet-reverse/SKILL.md) | .NET/C# 托管程序逆向：dnSpy/ILSpy 反编译、de4dot 脱 ConfuserEx 混淆、IL patch 改判断。用于：C# 能反编译吗、ConfuserEx 怎么脱、dnSpy 怎么改判断。 |
| [edr-bypass-re](edr-bypass-re/SKILL.md) | 红队 EDR 绕过：unhook、direct syscall、AMSI/ETW 绕过、反射加载 implant。用于：Defender 老杀我马、unhook 过 EDR、AMSI/ETW 怎么处理。 |
| [email-security](email-security/SKILL.md) | 邮件安全与钓鱼分析：Received 链、SPF/DKIM/DMARC 校验、BEC 欺诈。用于：这封邮件是钓鱼吗、帮我查下 SPF 配对没、BEC 诈骗长啥样。 |
| [firmware-pentest](firmware-pentest/SKILL.md) | 固件/IoT 渗透链：binwalk/unblob 解包文件系统、QEMU/Firmadyne 仿真、bootloader 解密。用于：路由器固件能解开吗、binwalk 解不出文件系统、QEMU 跑起固件。 |
| [fix-bug](fix-bug/SKILL.md) | 修 bug 先复现再改、修根因不压症状，并留下先红后绿的回归测试。用于：这 bug 怎么修、测试挂了、报错怎么复现、修完又犯。 |
| [game-reverse](game-reverse/SKILL.md) | 游戏客户端逆向与反作弊机制评估：Unity IL2CPP/Mono 元数据恢复、Unreal UObject 反射、封包协议。用于：客户端逆向、IL2CPP 符号恢复、封包与内存结构分析。 |
| [ghidra-reverse](ghidra-reverse/SKILL.md) | Ghidra 逆向：反编译、交叉引用、analyzeHeadless 批量反编译、PyGhidra 脚本。用于：没 IDA 想用免费工具、用 Ghidra 帮我反编译、批量 headless 怎么跑。 |
| [go-rust-reverse](go-rust-reverse/SKILL.md) | Go/Rust 二进制逆向：go.buildid、pclntab 与 GoReSym 恢复函数名、Rust panic 字符串。用于：Go 马函数名全没了、Rust panic 字符串怎么定位、pclntab 怎么恢复。 |
| [hardware-security](hardware-security/SKILL.md) | 硬件/嵌入式接口安全：UART/JTAG/SWD 调试口发现、root shell 获取、拆机提取 SPI/NOR Flash。用于：UART 口在哪、JTAG 能连上吗、Flash 怎么 dump。 |
| [ida-reverse](ida-reverse/SKILL.md) | IDA Pro 静态逆向：反汇编、反编译、交叉引用、定位校验与密码逻辑。用于：看 exe/dll、反汇编 so/elf、找注册算法、样本静态分析。 |
| [identity-federation](identity-federation/SKILL.md) | 联邦身份与 SSO 鉴权测试：SAML 断言篡改、OIDC/OAuth2 错配、redirect_uri/state/PKCE 缺陷、token 混淆。用于：测 SSO、SAML 签名、IdP/SP 元数据。 |
| [implement-feature](implement-feature/SKILL.md) | 小步实现功能：一次只解决一件事，复用仓库既有 pattern，不建第二套约定，不破构建。用于：按已定方案写代码、加个小功能。 |
| [js-reverse](js-reverse/SKILL.md) | 前端 JS 逆向：定位签名/加密参数与风控字段、Hook 采样、本地补 Node 环境（js-reverse_*、CDP、jshookmcp）。用于：还原 sign/token、追踪 XHR/Fetch/WebSocket。 |
| [kernel-exploit](kernel-exploit/SKILL.md) | Linux 内核漏洞根因与利用链：CVE 复盘、OOB/UAF 原语推导、SMEP/SMAP/KASLR/KPTI 绕过、补丁差分。用于：查内核 CVE 根因、审计驱动源码。 |
| [llm-security](llm-security/SKILL.md) | LLM/AI Agent 安全测试：prompt injection（直接/间接）、越狱与编码绕过、工具滥用越权、记忆投毒。用于：测 ChatBot/RAG、红队 Agent 工具调用、garak/PyRIT。 |
| [macos-reverse](macos-reverse/SKILL.md) | macOS/Mach-O 逆向：codesign 签名与 Hardened Runtime、ObjC/Swift 符号恢复、dylib/.app 分析、TCC，工具 otool/jtool2。用于：分析 Mach-O 签名装载、恢复 ObjC 类结构。 |
| [malware-analysis](malware-analysis/SKILL.md) | 恶意样本分析（静态/动态/行为）：查壳脱壳与 IAT 修复、C2 与持久化、IOC 提取、YARA/Sigma 规则、沙箱编排、反调试。用于：判定 exe/dll/sys/宏样本。 |
| [mobile-reverse](mobile-reverse/SKILL.md) | Android/iOS 逆向与安全测试：APK/IPA 分析、jadx/apktool/smali、Frida/objection 插桩、SSL pinning 与 root/越狱绕过、OWASP MASTG。用于：分析 APK/IPA、绕证书校验与加固。 |
| [ot-ics](ot-ics/SKILL.md) | OT/ICS 工控安全评估：Purdue 分区、PLC/RTU/SCADA 暴露面、Modbus/DNP3/S7/EtherNet/IP 识别、被动优先只读。用于：评估工控环境、镜像流量解析协议。 |
| [patch-diff-exploit](patch-diff-exploit/SKILL.md) | N-day 补丁差分到利用：before/after 二进制对齐符号，BinDiff/ghidriff/Diaphora 差分，从新增检查反推 bug class（OOB/UAF/溢出）并写 PoC。用于：有 CVE 无 PoC、闭源驱动补丁还原。 |
| [pentest-tools](pentest-tools/SKILL.md) | 主动渗透工具链：子域名、Nmap/Masscan 端口扫描、Nuclei 漏洞扫描、SQLi/XSS/SSRF 与 SQLMap/FFUF 爆破、Hashcat 口令破解。用于：授权扫描主机与 Web。 |
| [src-hunter](pentest-tools/src-hunter/SKILL.md) | 实战 SRC/众测/bug bounty 漏洞挑战工作流。用于：5 阶段方法论 + 19 类攻击 playbook + 结构化 payload + WAF/EDR 绕过变体、真实漏洞案例库。 |
| [pr-ship](pr-ship/SKILL.md) | 用最小、可审的 PR 交付改动，并附作者自己的验证证据与完整描述。用于：帮我把这个改动提成 PR、要开 PR 了、把这个 feature 交付出去。 |
| [protocol-reverse](protocol-reverse/SKILL.md) | 自定义协议逆向：TCP/UDP 帧布局还原、protobuf/gRPC 解码、WebSocket/MQTT 分析、PCAP 还原状态机。用于：有 PCAP 要还协议、未知 protobuf 恢复。 |
| [pwn-chain](pwn-chain/SKILL.md) | 漏洞点到可用 exploit 的利用链：栈溢出、堆/tcache、ROP/ret2libc、kernel pwn、pwntools。用于：CTF pwn 远程打不通、已知漏洞点写 exploit、绕 SMEP/SMAP/KASLR。 |
| [radare2](radare2/SKILL.md) | radare2/r2 命令行二进制分析：反汇编、交叉引用、strings/imports、patch、r2pipe/rabin2/rasm2/radiff2。用于：r2 CLI 分析 exe/dll/so/elf/apk/dex/wasm、定位函数。 |
| [radio-sdr](radio-sdr/SKILL.md) | RF/SDR 信号研究：调制识别、GNU Radio/URH/Inspectrum 解调、屏蔽室重放。用于：非 Wi-Fi 射频（RTL-SDR/HackRF IQ）、ADS-B/遥控/传感器协议。 |
| [req-clarify](req-clarify/SKILL.md) | 把模糊需求收敛成可判定的验收标准（Given-When-Then、含负例与边界），信息不足先问不猜。用于：需求含糊、验收写不出、开工前定 spec。 |
| [dsl-vm-reverse](reverse-engineering/dsl-vm-reverse/SKILL.md) | JS 自定义 DSL/VM 解释器逆向。用于：分析 IIFE 或 switch opcode 分发器、提取指令表、恢复字节码语义、捕获 VM 状态时。 |
| [reverse-engineering](reverse-engineering/SKILL.md) | 通用逆向方法论：triage→static→dynamic，判壳/混淆/虚拟化、custom VM、anti-debug。用于：搞不清样本怎么跑、加固挡路、调试器一用就退。 |
| [spike](spike/SKILL.md) | 跑一次性原型验证可行性或比较方案，产出 go/no-go 结论与证据而非可合并代码。用于：先验证一下行不行、比较两个方案、做个技术选型原型。 |
| [supply-chain-security](supply-chain-security/SKILL.md) | 供应链安全评估：SBOM、SCA 依赖漏洞与可达性、CI/CD 管道审计、容器镜像。用于：审依赖许可、查组件 CVE、测 GitHub Actions 信任边界。 |
| [thick-client](thick-client/SKILL.md) | 桌面厚客户端测试：信任边界、凭证存储、IPC/命名管道、流量与更新校验。用于：Electron/Qt/WinForms/WPF、%APPDATA% 硬编码密钥、DLL 劫持、更新器降级。 |
| [threat-hunting](threat-hunting/SKILL.md) | 威胁狩猎与检测工程：SIEM/EDR 假说查询、Sysmon 事件关联、Sigma/YARA 规则。用于：找 LOTL 横向、IOC 落地检测规则、验证规则。 |
| [threat-intelligence](threat-intelligence/SKILL.md) | OSINT 与威胁情报：公开来源 IOC 富化、campaign 与威胁组织画像、仿冒诈骗线索、Xquik 公开 X/Twitter 检索。用于：IOC 归属、情报包准备。 |
| [verify-done](verify-done/SKILL.md) | 给 agent 一个自己可跑、返回 pass/fail 的 check，并用独立 context 复核需求。用于：怎么确认改好了、做完了没有、跑一遍验证、核对需求逐条。 |
| [web-protocol-reverse](web-protocol-reverse/SKILL.md) | 敌意 Web 客户端还原成不依赖浏览器的采集器：sign/token/cookie、challenge、WebSocket/GraphQL/protobuf、WebAssembly。用于：403/412/429、HAR 离线复现、可重放采集器。 |
| [wifi-wireless](wifi-wireless/SKILL.md) | Wi-Fi 安全评估：监听模式、WPA/WPA2 握手/PMKID、aircrack/hashcat 口令评估、流氓 AP 检测。用于：airmon-ng/airodump-ng 抓包、802.11 管理帧。 |
| [windows-ad](windows-ad/SKILL.md) | AD/Windows 身份攻击：Kerberos(Kerberoast/AS-REP)、ADCS ESC1-ESC8、BloodHound、NTLM relay、域内提权。用于：域渗透身份枚举、impacket/certipy/nxc、pass-the-hash。 |
| [write-tests](write-tests/SKILL.md) | 判断该不该写测试、写只测行为不测实现的测试，不强制覆盖率数字。用于：要不要写测试、测试怎么写、测行为还是测实现、测试总在改。 |
| [x64dbg-reverse](x64dbg-reverse/SKILL.md) | x64dbg 动态调试与 MCP 自动化：断点、单步、内存读写、反汇编、穿越反调试。用于：挂调试器即退出、抓运行期明文、下断校验点、改内存。 |

## 目录树

```
skills/api-security/SKILL.md/
skills/apk-reverse/SKILL.md/
skills/attack-chain/SKILL.md/
skills/binary-diff/SKILL.md/
skills/binary-ninja-reverse/SKILL.md/
skills/browser-automation/SKILL.md/
skills/browser-extension-reverse/SKILL.md/
skills/case-review/SKILL.md/
skills/cloud-k8s/SKILL.md/
skills/code-audit/SKILL.md/
skills/code-review/SKILL.md/
skills/community/apk-extension/SKILL.md/
skills/community/ctf-hub/SKILL.md/
skills/community/delivery/SKILL.md/
skills/community/hack-hub/SKILL.md/
skills/ctf-sandbox/SKILL.md/
skills/database-security/SKILL.md/
skills/design-slice/SKILL.md/
skills/diagram-generator/SKILL.md/
skills/digital-forensics/SKILL.md/
skills/docs-changelog/SKILL.md/
skills/docs-generator/SKILL.md/
skills/dotnet-reverse/SKILL.md/
skills/edr-bypass-re/SKILL.md/
skills/email-security/SKILL.md/
skills/firmware-pentest/SKILL.md/
skills/fix-bug/SKILL.md/
skills/game-reverse/SKILL.md/
skills/ghidra-reverse/SKILL.md/
skills/go-rust-reverse/SKILL.md/
skills/hardware-security/SKILL.md/
skills/ida-reverse/SKILL.md/
skills/identity-federation/SKILL.md/
skills/implement-feature/SKILL.md/
skills/js-reverse/SKILL.md/
skills/kernel-exploit/SKILL.md/
skills/llm-security/SKILL.md/
skills/macos-reverse/SKILL.md/
skills/malware-analysis/SKILL.md/
skills/mobile-reverse/SKILL.md/
skills/ot-ics/SKILL.md/
skills/patch-diff-exploit/SKILL.md/
skills/pentest-tools/SKILL.md/
skills/pentest-tools/src-hunter/SKILL.md/
skills/pr-ship/SKILL.md/
skills/protocol-reverse/SKILL.md/
skills/pwn-chain/SKILL.md/
skills/radare2/SKILL.md/
skills/radio-sdr/SKILL.md/
skills/req-clarify/SKILL.md/
skills/reverse-engineering/dsl-vm-reverse/SKILL.md/
skills/reverse-engineering/SKILL.md/
skills/spike/SKILL.md/
skills/supply-chain-security/SKILL.md/
skills/thick-client/SKILL.md/
skills/threat-hunting/SKILL.md/
skills/threat-intelligence/SKILL.md/
skills/verify-done/SKILL.md/
skills/web-protocol-reverse/SKILL.md/
skills/wifi-wireless/SKILL.md/
skills/windows-ad/SKILL.md/
skills/write-tests/SKILL.md/
skills/x64dbg-reverse/SKILL.md/
```

## 路由

PRIMARY 路由由 `skills/config/routing.json`（唯一事实源）驱动，用 `master-route.ps1 -Hint "<任务>"` 分诊。
歧义场景读 `skills/routing.md` 全矩阵；CTF 多类型任务走 `CTF-Sandbox-Orchestrator/`。

## 症状 / 知识库索引

上面这张表按**模块**查。遇到「用户描述了一个现象，不知道该读哪篇技术文档」，用这两张表：

| 表 | 用途 | 什么时候读 |
|---|---|---|
| [SYMPTOM-INDEX.md](SYMPTOM-INDEX.md) | 用户口述的现象 → 进哪个技能 | 路由**没命中**时；以及**任务中途**拿到新证据 / 工具报错 / 结论矛盾 / 任务进入新域时**回读** |
| [field-journal/KB-INDEX.md](field-journal/KB-INDEX.md) | 现象 → 读哪篇**技术文档**（以 KB-INDEX 自己的合计为准） | 已进技能，但不确定该读 `references/` 里的哪一篇 |

知识库来源、改编规则、以及「源文档被本机实测推翻」的 27 条清单见 [field-journal/KB-SOURCES.md](field-journal/KB-SOURCES.md)。
