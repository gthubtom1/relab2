# reverse-skill 技能导航索引

> 本文件由 `skills/scripts/extract-summaries.ps1` 自动生成，**请勿手改**。
> 修改摘要请编辑对应模块 `SKILL.md` 的 frontmatter `description`，然后重跑脚本。

## 模块总览

| 模块 | 摘要 |
|------|------|
| [api-security](api-security/SKILL.md) | API 安全测试：REST/GraphQL/WebSocket 接口发现、JWT/OAuth、BOLA/IDOR/BFLA 越权。用于：接口越权、JWT 弱密钥、GraphQL 内省。不要用于：JS 签名→web-protocol-reverse；前端→js-reverse；扩展→browser-extensio... |
| [apk-reverse](apk-reverse/SKILL.md) | APK 逆向：jadx/apktool 解包、改 smali/AndroidManifest、重打包、Frida hook。用于：APK 逻辑、装不上、去广告、查服务器、root 检测。不要用于：IPA→mobile-reverse；.NET→dotnet-reverse；带壳→reverse-engineeri... |
| [attack-chain](attack-chain/SKILL.md) | 多阶段攻击链编排：侦察、初始访问、提权、横向、影响评估。用于：完整渗透、外网打到域控、HW 演练、webshell 下一步。不要用于：端口/SQLi→pentest-tools；APK→apk-reverse；域渗透→windows-ad；只写报告→docs-generator。 |
| [binary-diff](binary-diff/SKILL.md) | 二进制差分/符号迁移：旧版符号迁到新版、更新后找偏移、内核缺 PDB。用于：更新后地址变了、新版 PDB 下不到、旧版函数名迁移。不要用于：从零逆向→ida-reverse/radare2；加壳→reverse-engineering；N-day 差分→patch-diff-exploit。 |
| [binary-ninja-reverse](binary-ninja-reverse/SKILL.md) | Binary Ninja 逆向：HLIL/MLIL/LLIL 数据流、xrefs、类型与重命名、Python API。用于：点名 BN 看函数逻辑、跟调用链、与 IDA/Ghidra/radare2 交叉验证。不要用于：IDA→ida-reverse；Ghidra→ghidra-reverse；radare2→r... |
| [browser-automation](browser-automation/SKILL.md) | 浏览器/桌面 GUI 自动化：Playwright/agent-browser 点击/填表/截图/登录；OpenReverse 操作 Windows GUI。用于：填表、爬页面、登录截图、提交 payload。不要用于：签名/CDP→js-reverse；抓包→web-protocol-reverse；扩展→br... |
| [browser-extension-reverse](browser-extension-reverse/SKILL.md) | 浏览器扩展逆向：crx/xpi 解包、manifest 权限、service_worker、content script、流量与 IOC。用于：插件是否偷数据、后台干了什么、权限给多了。不要用于：网页 JS→js-reverse；自动化→browser-automation；网页协议→web-protocol-r... |
| [case-review](case-review/SKILL.md) | case 包只读审查：scope 就绪度、Evidence 链可追溯、artifact SHA-256、rebuild/update 表核对。用于：交报告前审 case、证据链全不全、复核哈希。不要用于：渗透/逆向→pentest-tools/ida-reverse；写报告→docs-generator；样本→m... |
| [cloud-k8s](cloud-k8s/SKILL.md) | 云/容器/K8s 安全评估：元数据 SSRF、IAM 越权、公开桶、容器逃逸、K8s RBAC。用于：云元数据 SSRF、容器逃逸、集群 RBAC。不要用于：Web/漏扫→pentest-tools；镜像管道→supply-chain-security；数据库→database-security；横向→attac... |
| [code-audit](code-audit/SKILL.md) | 白盒源码审计：PR/差分审查、Semgrep/CodeQL/Bandit/gosec SAST、注入点、鉴权缺失。用于：审代码注入、PR 合前过安全、IDOR/多租户。不要用于：无源码二进制→reverse-engineering；依赖/CI→supply-chain-security；接口越权→api-secu... |
| [community-apk-extension](community/apk-extension/SKILL.md) | APK 逆向能力扩展入口。把新版 apk-reverse 的 doctor、capability matrix、DEX/Dart/native、Frida、重打包和证据脚本接到 canonical apk-reverse 的统一 case 与工具门。 |
| [community-ctf-hub](community/ctf-hub/SKILL.md) | CTF 任务的友好分诊与教学适配层。把自动分流、头脑风暴、比赛和题解输出接到 reverse-skill 的 scope、case、证据和 CTF sandbox 流程。 |
| [community-delivery-workflow](community/delivery/SKILL.md) | 全栈软件交付编排适配层。按目标、输入、角色工作流、验收和文档沉淀推进项目，并在安全/逆向阶段交还 canonical reverse-skill 路由。 |
| [community-hack-hub](community/hack-hub/SKILL.md) | Web、API、主机和应用安全专题适配层。将 hack-skills 的分类和深度 playbook 接到 reverse-skill 的可执行路由、授权 scope、case 证据和报告合同。 |
| [ctf-sandbox](ctf-sandbox/SKILL.md) | CTF/AWD 靶场入口：case-init 门禁 + sidecar orchestrator 选竞赛子技能。用于：打 CTF、AWD、比赛切题、靶场题、pwn 怎么做、环境跑起来。不要用于：题型已明确（pwn→pwn-chain；APK→apk-reverse）；真实外网→attack-chain。 |
| [database-security](database-security/SKILL.md) | 数据库安全评估：0.0.0.0 绑定、弱口令、权限过大、危险功能（xp_cmdshell/UDF）、NoSQL 注入。用于：库是否暴露、被脱库、Redis 写文件提权。不要用于：源码注入→code-audit；云 RDS/K8s→cloud-k8s；OS 命令横向→attack-chain。 |
| [diagram-generator](diagram-generator/SKILL.md) | 把笔记或代码画成 Mermaid/PlantUML 文本图（流程图、时序图、架构图、ER 图）。用于：帮我画个流程图、时序图怎么画、Mermaid 架构图。不要用于：报告/writeup→docs-generator；二进制逆向→ida-reverse。 |
| [digital-forensics](digital-forensics/SKILL.md) | 数字取证与应急响应（IR）：内存转储 Volatility、E01 磁盘时间线、PCAP 溯源、IOC 提炼。用于：看 mem.dmp、电脑中招怎么溯源、PCAP 有啥异常。不要用于：样本本体→malware-analysis；主动扫描→pentest-tools；协议还原→protocol-reverse。 |
| [docs-generator](docs-generator/SKILL.md) | 把逆向/渗透/CTF 结论写成技术文档并落盘（渗透测试报告、CTF writeup、README、API 文档）。用于：帮我写份渗透测试报告、出个 writeup、补个 README。不要用于：只要图表→diagram-generator；审报告证据链→case-review。 |
| [dotnet-reverse](dotnet-reverse/SKILL.md) | .NET/C# 托管程序逆向：dnSpy/ILSpy 反编译、de4dot 脱 ConfuserEx 混淆、IL patch 改判断。用于：C# 能反编译吗、ConfuserEx 怎么脱、dnSpy 怎么改判断。不要用于：native PE→ida-reverse；APK→apk-reverse；JS→js-re... |
| [edr-bypass-re](edr-bypass-re/SKILL.md) | 已授权红队 EDR 绕过：unhook、direct syscall、AMSI/ETW 绕过、反射加载 implant。用于：Defender 老杀我马、unhook 过 EDR、AMSI/ETW 怎么处理。不要用于：全链路打域控→attack-chain；木马免杀→malware-analysis；内网 AD ... |
| [email-security](email-security/SKILL.md) | 邮件安全与钓鱼分析：Received 链、SPF/DKIM/DMARC 校验、BEC 欺诈。用于：这封邮件是钓鱼吗、帮我查下 SPF 配对没、BEC 诈骗长啥样。不要用于：附件样本本体→malware-analysis；OAuth/令牌→identity-federation；检测规则→threat-hunting。 |
| [firmware-pentest](firmware-pentest/SKILL.md) | 固件/IoT 渗透链：binwalk/unblob 解包文件系统、QEMU/Firmadyne 仿真、bootloader 解密。用于：路由器固件能解开吗、binwalk 解不出文件系统、QEMU 跑起固件。不要用于：单个 ELF→ida-reverse；APK/boot.img→apk-reverse；UART... |
| [game-reverse](game-reverse/SKILL.md) | 游戏客户端逆向与反作弊机制评估：Unity IL2CPP/Mono 元数据恢复、Unreal UObject 反射、封包协议。用于：客户端逆向、IL2CPP 符号恢复、封包与内存结构分析。不要用于：APK→apk-reverse；浏览器 JS→js-reverse；内核对抗→edr-bypass-re。 |
| [ghidra-reverse](ghidra-reverse/SKILL.md) | Ghidra 逆向：反编译、交叉引用、analyzeHeadless 批量反编译、PyGhidra 脚本。用于：没 IDA 想用免费工具、用 Ghidra 帮我反编译、批量 headless 怎么跑。不要用于：已有 IDA 深挖→ida-reverse；CLI 侦察→radare2；符号迁移→binary-diff。 |
| [go-rust-reverse](go-rust-reverse/SKILL.md) | Go/Rust 二进制逆向：go.buildid、pclntab 与 GoReSym 恢复函数名、Rust panic 字符串。用于：Go 马函数名全没了、Rust panic 字符串怎么定位、pclntab 怎么恢复。不要用于：普通 C/C++→ida-reverse；APK→apk-reverse；.NET→... |
| [hardware-security](hardware-security/SKILL.md) | 硬件/嵌入式接口安全：UART/JTAG/SWD 调试口发现、root shell 获取、拆机提取 SPI/NOR Flash。用于：UART 口在哪、JTAG 能连上吗、Flash 怎么 dump。不要用于：固件解包与仿真→firmware-pentest；固件内二进制→ida-reverse；工控协议→ot-... |
| [ida-reverse](ida-reverse/SKILL.md) | IDA Pro 静态逆向：反汇编、反编译、交叉引用、定位校验与密码逻辑。用于：看 exe/dll、反汇编 so/elf、找注册算法、样本静态分析。不要用于：APK→apk-reverse；.NET→dotnet-reverse；带壳/反调试→先 reverse-engineering。 |
| [identity-federation](identity-federation/SKILL.md) | 联邦身份与 SSO 授权测试：SAML 断言篡改、OIDC/OAuth2 错配、redirect_uri/state/PKCE 缺陷、token 混淆。用于：测 SSO、SAML 签名、IdP/SP 元数据。不要用于：JWT/API→api-security；AD 域→windows-ad；云 IdP→cloud... |
| [js-reverse](js-reverse/SKILL.md) | 前端 JS 逆向：定位签名/加密参数与风控字段、Hook 采样、本地补 Node 环境（js-reverse_*、CDP、jshookmcp）。用于：还原 sign/token、追踪 XHR/Fetch/WebSocket。不要用于：exe/so→ida-reverse；APK/iOS→mobile-revers... |
| [kernel-exploit](kernel-exploit/SKILL.md) | Linux 内核漏洞根因与利用链：CVE 复盘、OOB/UAF 原语推导、SMEP/SMAP/KASLR/KPTI 绕过、补丁差分。用于：查内核 CVE 根因、审计驱动源码。不要用于：用户态→pwn-chain；符号迁移→binary-diff；IoT 内核→firmware-pentest。 |
| [llm-security](llm-security/SKILL.md) | LLM/AI Agent 安全测试：prompt injection（直接/间接）、越狱与编码绕过、工具滥用越权、记忆投毒。用于：测 ChatBot/RAG、红队 Agent 工具调用、garak/PyRIT。不要用于：Web/API→api-security；样本分析→malware-analysis；模型逆向... |
| [macos-reverse](macos-reverse/SKILL.md) | macOS/Mach-O 逆向：codesign 签名与 Hardened Runtime、ObjC/Swift 符号恢复、dylib/.app 分析、TCC，工具 otool/jtool2。用于：分析 Mach-O 签名装载、恢复 ObjC 类结构。不要用于：iOS IPA→mobile-reverse；Win... |
| [malware-analysis](malware-analysis/SKILL.md) | 恶意样本分析（静态/动态/行为）：查壳脱壳与 IAT 修复、C2 与持久化、IOC 提取、YARA/Sigma 规则、沙箱编排、反调试。用于：判定 exe/dll/sys/宏样本。不要用于：单函数定位→ida-reverse；macOS→macos-reverse；SIEM 狩猎→threat-hunting。 |
| [mobile-reverse](mobile-reverse/SKILL.md) | Android/iOS 逆向与安全测试：APK/IPA 分析、jadx/apktool/smali、Frida/objection 插桩、SSL pinning 与 root/越狱绕过、OWASP MASTG。用于：分析 APK/IPA、绕证书校验与加固。不要用于：原生 PE/ELF→ida-reverse；网页... |
| [ot-ics](ot-ics/SKILL.md) | OT/ICS 工控安全评估：Purdue 分区、PLC/RTU/SCADA 暴露面、Modbus/DNP3/S7/EtherNet/IP 识别、被动优先只读。用于：评估工控环境、镜像流量解析协议。不要用于：内网渗透→pentest-tools；固件解包→firmware-pentest；协议还原→protocol... |
| [patch-diff-exploit](patch-diff-exploit/SKILL.md) | N-day 补丁差分到利用：before/after 二进制对齐符号，BinDiff/ghidriff/Diaphora 差分，从新增检查（OOB/UAF/溢出）反推 bug class 并写 PoC。用于：有 CVE 无 PoC、闭源驱动补丁还原。不要用于：符号迁移→binary-diff；利用链→pwn-ch... |
| [pentest-tools](pentest-tools/SKILL.md) | 主动渗透工具链：子域名、Nmap/Masscan 端口扫描、Nuclei 漏洞扫描、SQLi/XSS/SSRF 与 SQLMap/FFUF 爆破、Hashcat 口令破解。用于：授权扫描主机与 Web。不要用于：逆向→ida-reverse；JS 签名→js-reverse；浏览器自动化→browser-auto... |
| [src-hunter](pentest-tools/src-hunter/SKILL.md) | 实战 SRC / 众测 / Bug bounty 漏洞挖掘工作流 skill。包含：5 阶段方法论（intake → recon → enum → hunt → report）、19 个攻击类 playbook（SQLi/XSS/RCE/SSRF/IDOR/CSRF/Path Traversal/File Upl... |
| [protocol-reverse](protocol-reverse/SKILL.md) | 自定义协议逆向：TCP/UDP 帧布局还原、protobuf/gRPC 解码、WebSocket/MQTT 分析、PCAP 还原状态机。用于：有 PCAP 要还协议、未知 protobuf 恢复。不要用于：HTTP 签名→js-reverse；Web token 重放→web-protocol-reverse；固... |
| [pwn-chain](pwn-chain/SKILL.md) | 漏洞点到可用 exploit 的利用链：栈溢出、堆/tcache、ROP/ret2libc、kernel pwn、pwntools。用于：CTF pwn 远程打不通、已知漏洞点写 exploit、绕 SMEP/SMAP/KASLR。不要用于：判壳→reverse-engineering；静态分析→ida-reve... |
| [radare2](radare2/SKILL.md) | radare2/r2 命令行二进制分析：反汇编、交叉引用、strings/imports、patch、r2pipe/rabin2/rasm2/radiff2。用于：r2 CLI 分析 exe/dll/so/elf/apk/dex/wasm、定位函数。不要用于：GUI 伪代码→ida-reverse；APK→apk... |
| [radio-sdr](radio-sdr/SKILL.md) | 授权 RF/SDR 信号研究：调制识别、GNU Radio/URH/Inspectrum 解调、屏蔽室重放。用于：非 Wi-Fi 射频（RTL-SDR/HackRF IQ）、ADS-B/遥控/传感器协议。不要用于：Wi-Fi→wifi-wireless；固件→firmware-pentest；软件逆向→rever... |
| [dsl-vm-reverse](reverse-engineering/dsl-vm-reverse/SKILL.md) | Reverse JavaScript-based custom DSL/VM interpreters, non-standard WASM-like runtimes, and risk-control engines. Use when analyzing IIFE or switch-based opcod... |
| [reverse-engineering](reverse-engineering/SKILL.md) | 通用逆向方法论：triage→static→dynamic，判壳/混淆/虚拟化、custom VM、anti-debug。用于：搞不清样本怎么跑、加固挡路、调试器一用就退。不要用于：写 exploit→pwn-chain；IDA→ida-reverse；APK→apk-reverse；.NET→dotnet-re... |
| [supply-chain-security](supply-chain-security/SKILL.md) | 供应链安全评估：SBOM、SCA 依赖漏洞与可达性、CI/CD 管道审计、容器镜像。用于：审依赖许可、查组件 CVE、测 GitHub Actions 信任边界。不要用于：应用渗透→pentest-tools；样本逆向→reverse-engineering；云 K8s→cloud-k8s。 |
| [thick-client](thick-client/SKILL.md) | 桌面厚客户端测试：信任边界、凭证存储、IPC/命名管道、流量与更新校验。用于：Electron/Qt/WinForms/WPF、%APPDATA% 硬编码密钥、DLL 劫持、更新器降级。不要用于：Web/API→code-audit；APK→apk-reverse；内网横向→attack-chain。 |
| [threat-hunting](threat-hunting/SKILL.md) | 威胁狩猎与检测工程：SIEM/EDR 假说查询、Sysmon 事件关联、Sigma/YARA 规则。用于：找 LOTL 横向、IOC 落地检测规则、验证规则。不要用于：样本分析→malware-analysis；取证→digital-forensics；情报收集→threat-intelligence。 |
| [threat-intelligence](threat-intelligence/SKILL.md) | 授权 OSINT 与威胁情报：公开来源 IOC 富化、campaign 与威胁组织画像、仿冒诈骗线索、Xquik 公开 X/Twitter 检索。用于：IOC 归属、情报包准备。不要用于：私有数据收集、样本分析→malware-analysis、落地规则→threat-hunting。 |
| [web-protocol-reverse](web-protocol-reverse/SKILL.md) | 敌意 Web 客户端还原成不依赖浏览器的采集器：sign/token/cookie、challenge、WebSocket/GraphQL/protobuf、WebAssembly。用于：403/412/429、HAR 离线复现、可重放采集器。不要用于：APK→apk-reverse；小程序→mobile-rev... |
| [wifi-wireless](wifi-wireless/SKILL.md) | 授权 Wi-Fi 安全评估：监听模式、WPA/WPA2 握手/PMKID、aircrack/hashcat 口令评估、流氓 AP 检测。用于：airmon-ng/airodump-ng 抓包、802.11 管理帧。不要用于：非 Wi-Fi RF→radio-sdr；网卡固件→hardware-security；域... |
| [windows-ad](windows-ad/SKILL.md) | 授权 AD/Windows 身份攻击：Kerberos(Kerberoast/AS-REP)、ADCS ESC1-ESC8、BloodHound、NTLM relay、域内提权。用于：域渗透身份枚举、impacket/certipy/nxc、pass-the-hash。不要用于：全链→attack-chain；客... |

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
skills/community/apk-extension/SKILL.md/
skills/community/ctf-hub/SKILL.md/
skills/community/delivery/SKILL.md/
skills/community/hack-hub/SKILL.md/
skills/ctf-sandbox/SKILL.md/
skills/database-security/SKILL.md/
skills/diagram-generator/SKILL.md/
skills/digital-forensics/SKILL.md/
skills/docs-generator/SKILL.md/
skills/dotnet-reverse/SKILL.md/
skills/edr-bypass-re/SKILL.md/
skills/email-security/SKILL.md/
skills/firmware-pentest/SKILL.md/
skills/game-reverse/SKILL.md/
skills/ghidra-reverse/SKILL.md/
skills/go-rust-reverse/SKILL.md/
skills/hardware-security/SKILL.md/
skills/ida-reverse/SKILL.md/
skills/identity-federation/SKILL.md/
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
skills/protocol-reverse/SKILL.md/
skills/pwn-chain/SKILL.md/
skills/radare2/SKILL.md/
skills/radio-sdr/SKILL.md/
skills/reverse-engineering/dsl-vm-reverse/SKILL.md/
skills/reverse-engineering/SKILL.md/
skills/supply-chain-security/SKILL.md/
skills/thick-client/SKILL.md/
skills/threat-hunting/SKILL.md/
skills/threat-intelligence/SKILL.md/
skills/web-protocol-reverse/SKILL.md/
skills/wifi-wireless/SKILL.md/
skills/windows-ad/SKILL.md/
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
