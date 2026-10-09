# reverse-skill 技能导航索引

> 本文件由 `skills/scripts/extract-summaries.ps1` 自动生成，**请勿手改**。
> 修改摘要请编辑对应模块 `SKILL.md` 的 frontmatter `description`，然后重跑脚本。

## 模块总览

| 模块 | 摘要 |
|------|------|
| [api-security](api-security/SKILL.md) | API security assessment — 当用户要测REST/GraphQL/WebSocket接口的认证鉴权越权限流问题，或说"这个接口有没有越权""帮我测下登录token安不安全""graphql能不能内省"时使用。Use when testing API discovery, JWT/OAuth ... |
| [apk-reverse](apk-reverse/SKILL.md) | APK reverse — 当用户要解包反编译APK/改smali/重打包/用Frida动态hook，或说"这个apk装不上""想把广告去掉""看看它连了哪些服务器"时使用。Use when unpacking, decompiling, patching, re-signing an APK or hookin... |
| [attack-chain](attack-chain/SKILL.md) | Multi-stage attack-path orchestration — 当用户要做完整渗透/从外网打到域控/规划攻击路径，或说"帮我做一次完整渗透""拿到webshell下一步怎么办""从这个漏洞能打到什么程度"时使用。Use when planning recon, initial access, pr... |
| [binary-diff](binary-diff/SKILL.md) | 跨版本符号迁移与二进制差分 — 当用户手里有旧版符号要迁到新版/程序更新后找新偏移/内核缺PDB推导，或说"更新后函数地址变了""新版PDB下不到了""帮我把旧版函数名迁过来"时使用。Use when migrating symbols across versions or diffing binaries. |
| [binary-ninja-reverse](binary-ninja-reverse/SKILL.md) | Binary Ninja reverse engineering — 当用户点名用Binary Ninja看HLIL/MLIL数据流/查交叉引用，或说"用BN看下这个函数逻辑""帮我跟一下这个调用链""IDA结果对不上来交叉验证下"时使用。Use when inspecting HLIL/MLIL/LLIL, x... |
| [browser-automation](browser-automation/SKILL.md) | 统一自动化入口 — 当用户要自动打开网页点点填表爬取截图/自动登录，或说"帮我自动填下这个表单""把这个页面内容爬下来""自动登录后截图看看"时使用。Use when automating browser clicks, forms, scraping, screenshots or desktop GUI apps. |
| [browser-extension-reverse](browser-extension-reverse/SKILL.md) | Browser extension reverse engineering — 当用户要分析浏览器插件/查恶意扩展/看manifest权限，或说"这个插件是不是在偷数据""帮我看看它后台干了什么""扩展权限是不是给多了"时使用。Use when analyzing manifests, background wo... |
| [case-review](case-review/SKILL.md) | Case package review — 当用户要交报告前审一遍case包/查证据链完整性，或说"帮我审下这个case能不能交""证据到结论链条全不全""交报告前过一遍"时使用。Use when reviewing scope readiness, Evidence-Finding-Path traceabil... |
| [cloud-k8s](cloud-k8s/SKILL.md) | Cloud/container/K8s security assessment — 当用户要查云元数据SSRF/IAM越权/容器逃逸/K8s RBAC，或说"帮我看看这个存储桶是不是公开的""容器能不能逃逸""集群RBAC配得对不对"时使用。Use when assessing metadata SSRF, IA... |
| [code-audit](code-audit/SKILL.md) | Source-code security review — 当用户要白盒审代码/审PR差分/跑Semgrep找注入点，或说"帮我审下这段代码有没有注入""PR合之前过一遍安全""看看鉴权是不是漏了"时使用。Use when reviewing source, SAST scans, dangerous APIs ... |
| [community-apk-extension](community/apk-extension/SKILL.md) | APK 逆向能力扩展入口。把新版 apk-reverse 的 doctor、capability matrix、DEX/Dart/native、Frida、重打包和证据脚本接到 canonical apk-reverse 的统一 case 与工具门。 |
| [community-ctf-hub](community/ctf-hub/SKILL.md) | CTF 任务的友好分诊与教学适配层。把自动分流、头脑风暴、比赛和题解输出接到 reverse-skill 的 scope、case、证据和 CTF sandbox 流程。 |
| [community-delivery-workflow](community/delivery/SKILL.md) | 全栈软件交付编排适配层。按目标、输入、角色工作流、验收和文档沉淀推进项目，并在安全/逆向阶段交还 canonical reverse-skill 路由。 |
| [community-hack-hub](community/hack-hub/SKILL.md) | Web、API、主机和应用安全专题适配层。将 hack-skills 的分类和深度 playbook 接到 reverse-skill 的可执行路由、授权 scope、case 证据和报告合同。 |
| [ctf-sandbox](ctf-sandbox/SKILL.md) | CTF/AWD sandbox entry — 当用户说要打CTF/做靶场题/比赛切题，或说"来道CTF题""靶场这个pwn怎么做""比赛环境跑起来"时使用。Use when handling CTF, AWD or range tasks via the sidecar orchestrator. |
| [database-security](database-security/SKILL.md) | Database security assessment — 当用户要查数据库是否对外暴露、有弱口令或权限过大，或说“数据库好像被脱库了”“Redis能写文件提权吗”“这个账号权限是不是太大了”时使用。Use when database exposure, weak password, authz review. |
| [diagram-generator](diagram-generator/SKILL.md) | Generate diagrams from notes or code — 当用户想把流程、架构或表结构画出来，或说“帮我画个流程图”“这个时序图怎么画”“给我个Mermaid架构图”时使用。Use when flowchart, sequence diagram, architecture diagram. |
| [digital-forensics](digital-forensics/SKILL.md) | Digital forensics and IR — 当用户要分析内存转储、磁盘时间线或可疑流量，或说“这个mem.dmp帮我看看”“电脑中招了怎么溯源”“PCAP里有啥异常”时使用。Use when memory dump, disk timeline, PCAP triage. |
| [docs-generator](docs-generator/SKILL.md) | Write technical docs and reports — 当用户做完逆向或渗透要落盘成报告，或说“帮我写份渗透测试报告”“出个CTF writeup”“补个README和API文档”时使用。Use when write report, documentation, writeup. |
| [dotnet-reverse](dotnet-reverse/SKILL.md) | .NET/C#逆向 — 当目标是.NET程序、被混淆了或要改逻辑，或说“这个C#程序能反编译吗”“ConfuserEx怎么脱”“dnSpy怎么改判断”时使用。Use when .NET decompile, deobfuscation, IL patch. |
| [edr-bypass-re](edr-bypass-re/SKILL.md) | EDR绕过研究 — 当已授权红队要在EDR驻守主机上投递载荷，或说“Defender老杀我马怎么办”“怎么做unhook过EDR”“ETW和AMSI怎么处理”时使用。Use when EDR bypass, unhook, syscall in authorized test. |
| [email-security](email-security/SKILL.md) | Email security review — 当用户收到可疑邮件或要查域名邮箱配置，或说“这封邮件是钓鱼吗”“帮我查下SPF配对没”“BEC诈骗长啥样”时使用。Use when phishing analysis, SPF/DKIM/DMARC check. |
| [firmware-pentest](firmware-pentest/SKILL.md) | 固件/IoT渗透链 — 当用户拿到一份固件想解包仿真挖洞，或说“这个路由器固件能解开吗”“binwalk解不出文件系统”“想用QEMU跑起这个固件”时使用。Use when firmware extraction, emulation, IoT audit. |
| [ghidra-reverse](ghidra-reverse/SKILL.md) | Ghidra逆向 — 当用户没IDA想用免费工具看二进制，或说“用Ghidra帮我反编译这个”“批量headless怎么跑”“字符串交叉引用在哪”时使用。Use when Ghidra decompile, cross-refs, headless analysis. |
| [go-rust-reverse](go-rust-reverse/SKILL.md) | Go/Rust逆向 — 当目标是Go或Rust编译的、符号被剥了，或说“这个Go马函数名全没了”“Rust panic字符串怎么定位”“pclntab怎么恢复”时使用。Use when Go Rust stripped binary, runtime recovery. |
| [hardware-security](hardware-security/SKILL.md) | Hardware interface research — 当用户能摸到板子想找调试口提镜像，或说“这个UART口在哪”“JTAG能连上吗”“Flash怎么dump出来”时使用。Use when UART JTAG discovery, firmware extraction. |
| [ida-reverse](ida-reverse/SKILL.md) | IDA Pro 逆向分析辅助技能。当用户提到逆向、反编译、分析二进制/PE/ELF/APK/DLL/SO、破解、找密码、漏洞分析、病毒分析、firmware 固件分析，或需要分析 exe/dll/so/elf/macho/sys 等文件时，务必使用此技能。 |
| [identity-federation](identity-federation/SKILL.md) | Use for authorized assessment of federated identity systems including SAML, OIDC, OAuth2 flows, SSO misconfiguration, and token confusion issues. |
| [js-reverse](js-reverse/SKILL.md) | 在使用 js-reverse-mcp 做前端 JavaScript 逆向时使用，适用于签名链路定位、页面观察取证、运行时采样、本地补环境复现与证据化输出。优先适配当前环境里的 js-reverse_* 工具，需要更强的浏览器/CDP/Hook 面时联动 jshookmcp。 |
| [web-protocol-reverse](web-protocol-reverse/SKILL.md) | 浏览器端 JS 协议逆向 → 纯 Python 采集器（cookie 溯源 / JSVMP / 去浏览器依赖） | 改编自 spider-king-skill (MIT) |
| [llm-security](llm-security/SKILL.md) | Use for authorized security assessment of LLM applications and AI agents, including prompt injection, tool abuse, RAG exposure, memory poisoning, and model s... |
| [macos-reverse](macos-reverse/SKILL.md) | Use for authorized macOS and Mach-O reverse engineering including codesign, Objective-C/Swift recovery, endpoint security surfaces, and Apple platform malwar... |
| [malware-analysis](malware-analysis/SKILL.md) | Use when analyzing suspected malware through static, dynamic, and behavioral techniques, including IOC extraction, YARA or Sigma rules, sandboxing, and anti-... |
| [mobile-reverse](mobile-reverse/SKILL.md) | Use for authorized Android or iOS application reverse engineering and security testing, including APK or IPA analysis, runtime instrumentation, SSL pinning, ... |
| [ot-ics](ot-ics/SKILL.md) | Use for authorized OT/ICS security assessment covering Purdue model zoning, PLC/SCADA exposure, industrial protocol discovery, and safe passive-first evaluat... |
| [patch-diff-exploit](patch-diff-exploit/SKILL.md) | N-day 补丁差分到利用。从厂商发布的补丁里反推漏洞点、写 PoC、做成可用的攻击模块。 |
| [pentest-tools](pentest-tools/SKILL.md) | 主动渗透测试工具链。覆盖信息收集、端口扫描、漏洞扫描、Web 渗透、SQL 注入、目录爆破、密码破解等场景。 |
| [src-hunter](pentest-tools/src-hunter/SKILL.md) | 实战 SRC / 众测 / Bug bounty 漏洞挖掘工作流 skill。包含：5 阶段方法论（intake → recon → enum → hunt → report）、19 个攻击类 playbook（SQLi/XSS/RCE/SSRF/IDOR/CSRF/Path Traversal/File Upl... |
| [protocol-reverse](protocol-reverse/SKILL.md) | Use for authorized reverse engineering of custom binary protocols, Protobuf/gRPC, WebSocket frames, and PCAP-driven protocol recovery. |
| [pwn-chain](pwn-chain/SKILL.md) | 从逆向走到可用利用 (Working Exploit) 的全链路工程化方法。 |
| [radare2](radare2/SKILL.md) | Use this skill whenever the user wants to analyze binaries with radare2/r2 from the command line, including reverse engineering, disassembly, function analys... |
| [radio-sdr](radio-sdr/SKILL.md) | Use for authorized RF/SDR security research including signal identification, replay feasibility study in shielded labs, and wireless protocol analysis outsid... |
| [dsl-vm-reverse](reverse-engineering/dsl-vm-reverse/SKILL.md) | Reverse JavaScript-based custom DSL/VM interpreters, non-standard WASM-like runtimes, and risk-control engines. Use when analyzing IIFE or switch-based opcod... |
| [reverse-engineering](reverse-engineering/SKILL.md) | Provides reverse engineering techniques. Use when the main job is to understand how a compiled, obfuscated, packed, or virtualized target works before exploi... |
| [supply-chain-security](supply-chain-security/SKILL.md) | Use for software supply-chain security assessment covering SBOM, SCA, CI/CD pipelines, container images, build integrity, dependency provenance, and vulnerab... |
| [thick-client](thick-client/SKILL.md) | Use for authorized security testing of desktop thick clients including local storage, update channels, IPC, traffic, and client-side trust boundaries. |
| [threat-hunting](threat-hunting/SKILL.md) | Use for blue-team threat hunting, detection engineering with Sigma/YARA, SIEM query design, and incident detection validation. |
| [threat-intelligence](threat-intelligence/SKILL.md) | Use for authorized OSINT and cyber threat intelligence that enriches IOCs, campaigns, impersonation, scams, or threat actors from public sources. Includes bo... |
| [wifi-wireless](wifi-wireless/SKILL.md) | Use for authorized wireless security assessment including Wi-Fi capture, WPA handshake analysis, rogue AP detection research, and lab-only deauth testing. |
| [windows-ad](windows-ad/SKILL.md) | Use for authorized Active Directory and Windows identity attacks including Kerberos, AD CS, BloodHound paths, NTLM relay, and domain privilege escalation res... |

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
skills/ghidra-reverse/SKILL.md/
skills/go-rust-reverse/SKILL.md/
skills/hardware-security/SKILL.md/
skills/ida-reverse/SKILL.md/
skills/identity-federation/SKILL.md/
skills/js-reverse/SKILL.md/
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
skills/wifi-wireless/SKILL.md/
skills/windows-ad/SKILL.md/
```

## 路由

PRIMARY 路由由 `skills/config/routing.json`（唯一事实源）驱动，用 `master-route.ps1 -Hint "<任务>"` 分诊。
歧义场景读 `routing.md` 全矩阵；CTF 多类型任务走 `CTF-Sandbox-Orchestrator/`。

## 症状 / 知识库索引

上面这张表按**模块**查。遇到「用户描述了一个现象，不知道该读哪篇技术文档」，用这两张表：

| 表 | 用途 | 什么时候读 |
|---|---|---|
| [SYMPTOM-INDEX.md](SYMPTOM-INDEX.md) | 用户口述的现象 → 进哪个技能 | `master-route` 报 `confidence: low` / PRIMARY=R0 / "No strong keyword hit" |
| [field-journal/KB-INDEX.md](field-journal/KB-INDEX.md) | 现象 → 读哪篇技术文档（153 篇） | 已进技能，但不确定该读 `references/` 里的哪一篇 |

知识库来源、改编规则、以及「源文档被本机实测推翻」的 27 条清单见 [field-journal/KB-SOURCES.md](field-journal/KB-SOURCES.md)。
