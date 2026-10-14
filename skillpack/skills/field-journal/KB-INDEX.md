# 知识库症状索引（KB-INDEX）—— 手上出现某个现象时，直接定位该读哪篇

> **这是什么**：把外部知识库 `LING71671/open-reverselab` 改编进技能包后落地的全部技术文档，按**症状 / 信号**（不是文件名、不是目录）重新编成的一张检索表。
> AI 遇到任务时是**按现象找文档**，不是按目录翻 —— 所以本表左列是「我看到了什么」，右列是「读哪篇」。

> **怎么用**：先看 §1 铁律 → 在 §2 按现象对行 → 对上就 `read` 那一篇。
>
> **什么时候该回读本表**（八类触发信号：迷茫 / 换完技能 / 结论矛盾 / 文档和本机对不上 …）见
> [`../ops/kb-consult-contract.md`](../ops/kb-consult-contract.md) —— 它不是“开局读一次”，是**反复回读**。
> 对不上就往上翻到所属板块的总入口（每节开头都有一行「板块入口」）。

| 板块 | 技能目录 | 技术正文数 |
|---|---|---|
| PE / 二进制逆向 | `../reverse-engineering/` | 61 |
| Web / API 安全 | `../api-security/` | 72 |
| 数据库注入 | `../database-security/` | 10 |
| Web 攻击链与 CVE 实证 | `../attack-chain/` | 18 |
| Web-CTF 比赛与付费墙 | `../ctf-sandbox/` | 11 |
| 云 / K8s / CI-CD | `../cloud-k8s/` | 9 |
| 身份联邦（OAuth / SAML） | `../identity-federation/` | 5 |
| 供应链 | `../supply-chain-security/` | 3 |
| 邮件安全 | `../email-security/` | 2 |
| Web JS 运行时 | `../js-reverse/` | 15 |
| **技术正文合计** | — | **206** |

> 统计口径：排除 `../SKILL.md` / `../ops/README.md` / `../ctf-sandbox/references/index.md` 这类入口文件，只数技术正文。
> 全技能包 md 总数 625 篇（含全部索引与入口）。

## 1. 用这张表的铁律

1. **左列是现象，不是文件名**。心里先描述「我看到了什么」，再去 §2 对行。
2. **先读板块入口再读正文**。每节开头那行「板块入口」是总览，先花 10 秒看它，能省掉十几次错误检索。
3. **判据在正文里，不在索引里**。本表只负责「读哪篇」；「怎么算成功」以那篇的 §判据 为准（要求外部可观测：状态码、差分、断点命中、落盘文件哈希）。
4. **命中两篇就读两篇**。这些文档是攻击链的环节，不是互斥选项。
5. **对不上任何一行 = 记一条 case**。本表是活的，新症状没被收录时，把它写进 `field-journal/` 并回填到对应板块末尾。

## 2. PE / 二进制逆向（20 篇）

> **板块入口**：[`../reverse-engineering/SKILL.md`](../reverse-engineering/SKILL.md)

**技术正文** — `references/`

| 症状 / 信号（我看到了什么） | 文档 | 是什么 |
|---|---|---|
| x64dbg/cdb 附加后目标立刻退出，或什么都不发生。 | [anti-debug-bypass.md](../reverse-engineering/references/anti-debug-bypass.md) | 反调试检测与绕过 |
| 目标模块每次运行基址都不同（iI~baddr 每次不同），写死的 base+0x1234 不再命中。 | [aob-signature-scan.md](../reverse-engineering/references/aob-signature-scan.md) | AOB 特征码扫描 |
| 已定位到需要修改的目标地址（反调试分支、校验结果、常量）。 | [code-patching.md](../reverse-engineering/references/code-patching.md) | 代码 Patch 与字节修改 |
| 样本里有 256 字节 / 1024 字节的整齐常量表，不确定是什么 | [crypto-algorithm-identification.md](../reverse-engineering/references/crypto-algorithm-identification.md) | 算法盲识别：从字节特征反推加密/哈希/编码算法 |
| 密文长度 == 明文长度（流密码 / XOR / 替换） | [custom-obfuscation-reverse.md](../reverse-engineering/references/custom-obfuscation-reverse.md) | 自定义混淆/加密还原方法论 |
| 目标 PE 已加载，需要在某个 WinAPI 上观察参数与返回值。 | [debugger-breakpoints.md](../reverse-engineering/references/debugger-breakpoints.md) | 调试器断点策略（cdb / x64dbg） |
| 已拿到某地址的原始字节，需要知道它到底是几条指令、边界在哪。 | [disasm-jit-asm.md](../reverse-engineering/references/disasm-jit-asm.md) | 反汇编与机器码生成（capstone / rasm2 / r2） |
| 目标进程已启动，需要在它内部执行自己的代码。 | [dll-injection-patterns.md](../reverse-engineering/references/dll-injection-patterns.md) | DLL 注入模式与远程内存操作 |
| 导入表稀疏：ii 只有十几条甚至个位数，但程序行为丰富。 | [dynamic-api-resolution.md](../reverse-engineering/references/dynamic-api-resolution.md) | 动态 API 解析链还原 |
| 拿到的不是文件而是内存镜像（.dmp、pe-sieve 的输出、VirtualAlloc dump 出来的 buffer）。 | [pe-header-parsing.md](../reverse-engineering/references/pe-header-parsing.md) | PE 头解析与节区定位 |
| 连续多次抓包拿到同一接口返回的「随机」字段 | [prng-cracking.md](../reverse-engineering/references/prng-cracking.md) | PRNG 破解：从输出恢复内部状态与种子 |
| 已知某实体的运行时地址，需要确定它的字段偏移、类型和语义。 | [reclass-reconstruction.md](../reverse-engineering/references/reclass-reconstruction.md) | 结构体重建的桌面侧工具与自动化替代 |
| 「我看到一个可疑进程在跑，但不知道该上什么工具」 | [signal-to-tool-decision.md](../reverse-engineering/references/signal-to-tool-decision.md) | 按信号选工具决策树 |
| 反编译/反汇编里同一个基址被多种偏移访问：*(int*)(a+0x36C)、*(float*)(a+0x378)、*(char)(a+0x268)。 | [struct-reconstruction.md](../reverse-engineering/references/struct-reconstruction.md) | 内存结构体逆向重建 |
| 程序在 main/WinMain/入口点之前就退出、静默结束或弹错误框。 | [tls-callback-analysis.md](../reverse-engineering/references/tls-callback-analysis.md) | TLS Callback 定位与早期执行链 |
| 样本刚落地，来源不明或来源可疑，需要先定「值不值得深挖 / 有多难」 | [triage-first-30-min.md](../reverse-engineering/references/triage-first-30-min.md) | 拿到样本的前 30 分钟（Triage Checklist） |
| diec 输出 UPX(…) / ASPack(…) / VMProtect(…) / Themida 等壳签名。 | [unpack-and-memory-dump.md](../reverse-engineering/references/unpack-and-memory-dump.md) | PE 脱壳与内存 Dump |
| 已确认 VMP 2.x/3.x，且拿到 VM entry 地址表（缺这一条不要进本篇）。 | [vmp-devirtualization-toolchain.md](../reverse-engineering/references/vmp-devirtualization-toolchain.md) | VMP 去虚拟化工具链（Devirtualization） |
| diec 输出 VMProtect(3.x) / VMProtect(2.x) 签名。 | [vmp-virtualization-analysis.md](../reverse-engineering/references/vmp-virtualization-analysis.md) | VMP 虚拟化原理与 VM Entry 定位 |
| 已完成一个样本的静态分析，提取到了独特字符串、字节序列、导入表组合。 | [yara-rule-writing.md](../reverse-engineering/references/yara-rule-writing.md) | YARA 规则编写（逆向视角） |

## 3. Web / API 安全（74 篇）

> **板块入口**：[`../api-security/SKILL.md`](../api-security/SKILL.md)　·　目录总览：[api-security/references/dos/index.md](../api-security/references/dos/index.md)

**API 发现与密钥泄露** — `references/api-attacks/`

| 症状 / 信号（我看到了什么） | 文档 | 是什么 |
|---|---|---|
| API discovery | [01-api-discovery-leak.md](../api-security/references/api-attacks/01-api-discovery-leak.md) | API 发现与信息泄露 — Swagger、GraphQL、Source Map 与移动端提取 |
| API key leak | [02-api-key-leak.md](../api-security/references/api-attacks/02-api-key-leak.md) | API 密钥泄露与利用 — GitHub Dorking、客户端密钥链、云服务滥用 |

**认证头攻击** — `references/auth/`

| 症状 / 信号（我看到了什么） | 文档 | 是什么 |
|---|---|---|
| Host header | [host-header.md](../api-security/references/auth/host-header.md) | Host Header 攻击 |
| LDAP | [ldap-injection.md](../api-security/references/auth/ldap-injection.md) | LDAP Injection |

**客户端** — `references/client/`

| 症状 / 信号（我看到了什么） | 文档 | 是什么 |
|---|---|---|
| XSS | [admin-bot-xss.md](../api-security/references/client/admin-bot-xss.md) | Admin Bot / XSS 实战 |
| CORS | [cors-csrf.md](../api-security/references/client/cors-csrf.md) | CORS / CSRF 高级攻击 |
| postMessage | [postmessage.md](../api-security/references/client/postmessage.md) | PostMessage / 跨域通信攻击 |
| WebSocket | [websocket.md](../api-security/references/client/websocket.md) | WebSocket 攻击实战 |

**CORS / CSP / XS-Leaks** — `references/cors-csp/`

| 症状 / 信号（我看到了什么） | 文档 | 是什么 |
|---|---|---|
| CSP bypass | [01-csp-bypass.md](../api-security/references/cors-csp/01-csp-bypass.md) | CSP 绕过全技术栈 |
| XS-Leaks | [02-xs-leaks-browser-sidechannels.md](../api-security/references/cors-csp/02-xs-leaks-browser-sidechannels.md) | XS-Leaks 浏览器侧信道攻击 |

**HTTP 基础设施** — `references/infra/`

| 症状 / 信号（我看到了什么） | 文档 | 是什么 |
|---|---|---|
| HTTP/2 | [http2-attacks.md](../api-security/references/infra/http2-attacks.md) | HTTP/2 攻击 |
| race condition | [race-cache-smuggling.md](../api-security/references/infra/race-cache-smuggling.md) | Race Condition / Cache Poisoning / Request Smuggli |
| web cache deception | [web-cache-deception.md](../api-security/references/infra/web-cache-deception.md) | Web Cache Deception |

**注入** — `references/injection/`

| 症状 / 信号（我看到了什么） | 文档 | 是什么 |
|---|---|---|
| GraphQL | [graphql.md](../api-security/references/injection/graphql.md) | GraphQL 攻击实战 |
| gRPC | [grpc-protobuf.md](../api-security/references/injection/grpc-protobuf.md) | gRPC / Protobuf 攻击 |
| HPP | [hpp-crlf.md](../api-security/references/injection/hpp-crlf.md) | HPP / CRLF Injection / Header Injection |
| prototype pollution | [prototype-pollution.md](../api-security/references/injection/prototype-pollution.md) | Prototype Pollution (原型链污染) |
| ReDoS | [redos-timing.md](../api-security/references/injection/redos-timing.md) | ReDoS & 时序攻击 |
| SSTI | [ssti.md](../api-security/references/injection/ssti.md) | SSTI (Server-Side Template Injection) |

**SSRF / 开放重定向** — `references/ssrf/`

| 症状 / 信号（我看到了什么） | 文档 | 是什么 |
|---|---|---|
| open redirect | [open-redirect.md](../api-security/references/ssrf/open-redirect.md) | Open Redirect & Redirect Chain Attacks |
| SSRF | [ssrf.md](../api-security/references/ssrf/ssrf.md) | SSRF (Server-Side Request Forgery) |

**越权（IDOR / BAC）** — `references/idor/`

| 症状 / 信号（我看到了什么） | 文档 | 是什么 |
|---|---|---|
| IDOR | [01-idor-enumeration.md](../api-security/references/idor/01-idor-enumeration.md) | IDOR 深度枚举与利用 — 水平/垂直越权实战方法论 |
| BAC | [02-bac-business-logic.md](../api-security/references/idor/02-bac-business-logic.md) | 功能级访问控制缺失 (BAC) — 垂直越权与业务逻辑绕过 |

**批量赋值 / 参数篡改** — `references/mass-assignment/`

| 症状 / 信号（我看到了什么） | 文档 | 是什么 |
|---|---|---|
| mass assignment | [01-mass-assignment.md](../api-security/references/mass-assignment/01-mass-assignment.md) | 批量赋值与属性注入深度利用手册 |
| parameter tampering | [02-parameter-tampering.md](../api-security/references/mass-assignment/02-parameter-tampering.md) | 参数篡改全链 — 价格/数量/优惠券/竞态深度攻击 |

**限流绕过 / 凭证喷洒** — `references/rate-limit/`

| 症状 / 信号（我看到了什么） | 文档 | 是什么 |
|---|---|---|
| rate limit bypass | [01-rate-limit-bypass.md](../api-security/references/rate-limit/01-rate-limit-bypass.md) | 速率限制绕过 — IP 轮换、Header 操纵与应用层绕过 |
| credential spraying | [02-brute-force-tactics.md](../api-security/references/rate-limit/02-brute-force-tactics.md) | 高级暴力破解 — 凭证喷洒、MFA 疲劳、Hash 策略 |

**文件攻击 / 反序列化** — `references/file-attacks/`

| 症状 / 信号（我看到了什么） | 文档 | 是什么 |
|---|---|---|
| deserialization | [deserialization.md](../api-security/references/file-attacks/deserialization.md) | Deserialization Vulnerabilities |
| file upload | [file-upload-xxe-lfi.md](../api-security/references/file-attacks/file-upload-xxe-lfi.md) | File Upload / XXE / LFI / Path Traversal |

**JWT 攻击** — `references/jwt/`

| 症状 / 信号（我看到了什么） | 文档 | 是什么 |
|---|---|---|
| JWT | [00-overview.md](../api-security/references/jwt/00-overview.md) | JWT 攻击全景 |
| alg:none | [01-alg-none.md](../api-security/references/jwt/01-alg-none.md) | JWT `alg: none` 无签名绕过 |
| 算法混淆 | [02-algorithm-confusion.md](../api-security/references/jwt/02-algorithm-confusion.md) | JWT 算法混淆 (Algorithm Confusion) |
| HMAC | [03-weak-key-bruteforce.md](../api-security/references/jwt/03-weak-key-bruteforce.md) | JWT 弱 HMAC 密钥爆破 |
| kid | [04-kid-injection.md](../api-security/references/jwt/04-kid-injection.md) | JWT `kid` 参数注入 |
| jku | [05-jku-x5u-abuse.md](../api-security/references/jwt/05-jku-x5u-abuse.md) | JWT `jku` / `x5u` 密钥源劫持 |
| Claim | [06-claim-missing.md](../api-security/references/jwt/06-claim-missing.md) | JWT Claim 验证缺失 & Token 混用 |
| token窃取 | [07-theft-replay.md](../api-security/references/jwt/07-theft-replay.md) | JWT 窃取、重放与持久化 |
| CVE | [08-cve-library.md](../api-security/references/jwt/08-cve-library.md) | JWT 依赖库 CVE 与指纹路由 |
| jwt_tool | [09-toolchain-operations.md](../api-security/references/jwt/09-toolchain-operations.md) | JWT 工具链、操作流程与结果矩阵 |
| 见下方「技术正文」的条目式打点清单（本文档正文以清单为主，无结构化信号表）。 | [index.md](../api-security/references/jwt/index.md) | JWT 攻击技术库 |

**支付** — `references/payment/`

| 症状 / 信号（我看到了什么） | 文档 | 是什么 |
|---|---|---|
| 见下方「技术正文」的条目式打点清单（本文档正文以清单为主，无结构化信号表）。 | [index.md](../api-security/references/payment/index.md) | 12-payment — 支付、订单与票务业务逻辑 |
| Payment Bypass | [payment-bypass.md](../api-security/references/payment/payment-bypass.md) | Payment Bypass — 支付绕过深度技术手册 |
| payment callback | [payment-callback-async.md](../api-security/references/payment/payment-callback-async.md) | Payment Callback & Async Attack — 支付回调与异步攻击深度手册 |
| IAP | [payment-digital-goods.md](../api-security/references/payment/payment-digital-goods.md) | Payment Digital Goods & IAP — 虚拟商品/内购攻击手册 |
| 退信 | [payment-email-bounce-idor.md](../api-security/references/payment/payment-email-bounce-idor.md) | 退信滥用 + 订单号授权绕过窃取卡密 |
| Payment Logic | [payment-logic.md](../api-security/references/payment/payment-logic.md) | Payment Logic Attacks — 支付类 Web CTF 技术手册 |
| PHP | [payment-php.md](../api-security/references/payment/payment-php.md) | PHP Payment Attacks — PHP 支付专项攻击手册 |
| lost update | [payment-race-lost-update.md](../api-security/references/payment/payment-race-lost-update.md) | Payment Race / Lost Update — 余额扣减丢失更新 |
| subscription | [payment-subscription.md](../api-security/references/payment/payment-subscription.md) | Payment Subscription — 订阅/定期付款攻击深度手册 |
| platform fingerprint | [platform-fingerprints.md](../api-security/references/payment/platform-fingerprints.md) | PHP 发卡/电商平台指纹库 |
| ticket rush | [ticket-rush-api-reversing.md](../api-security/references/payment/ticket-rush-api-reversing.md) | Ticket Rush API Reversing — 票务抢购状态机、Token 与风控参数 |

**签名伪造** — `references/signature/`

| 症状 / 信号（我看到了什么） | 文档 | 是什么 |
|---|---|---|
| signature forgery | [00-overview.md](../api-security/references/signature/00-overview.md) | Signature Forgery — 签名伪造与验证绕过全景手册 |
| algorithm downgrade | [01-algorithm.md](../api-security/references/signature/01-algorithm.md) | Signature Algorithm Attacks — 签名算法降级/混淆/None 攻击深度手 |
| implementation bugs | [02-implementation.md](../api-security/references/signature/02-implementation.md) | Signature Implementation Bugs — 签名实现缺陷深度手册 |
| key attack | [03-key-attacks.md](../api-security/references/signature/03-key-attacks.md) | Key Attacks — 签名密钥攻击深度技术手册 |
| canonicalization | [04-canonicalization.md](../api-security/references/signature/04-canonicalization.md) | Canonicalization Attacks — 签名规范化绕过 |
| length extension | [05-length-extension.md](../api-security/references/signature/05-length-extension.md) | Hash Length Extension 攻击 — 深度技术手册 |
| replay attack | [06-replay-nonce.md](../api-security/references/signature/06-replay-nonce.md) | Replay / Nonce / Timestamp — 重放攻击深度技术手册 |
| JWT 签名: [02-auth/jwt/](../api-security/references/jwt/) | [index.md](../api-security/references/signature/index.md) | 13-signature — 签名伪造与验证绕过 |

**DoS** — `references/dos/`

| 症状 / 信号（我看到了什么） | 文档 | 是什么 |
|---|---|---|
| Web 服务器 (Nginx, Apache, IIS) | [01-application-layer-dos.md](../api-security/references/dos/01-application-layer-dos.md) | Application-Layer DoS |
| Valkey | [01-valkey-resp-dos.md](../api-security/references/dos/01-valkey-resp-dos.md) | Valkey RESP 协议：预认证断言失败 DoS（CVE-2026-27623） |
| Web 应用服务器 (Java/Python/PHP/Node.js) | [02-resource-exhaustion.md](../api-security/references/dos/02-resource-exhaustion.md) | Resource Exhaustion & Algorithm Complexity Attacks |
| 缺乏 BCP38 源认证的网络中的任意目标 | [03-amplification-drdos.md](../api-security/references/dos/03-amplification-drdos.md) | Amplification / DRDoS Attacks |
| 单请求响应时间异常增长 (正常 50ms → 攻击时 30s+)，但请求体仅几十字节 | [04-redos.md](../api-security/references/dos/04-redos.md) | ReDoS — 正则表达式拒绝服务 |
| 单连接上出现大量 HEADERS 帧后跟 CONTINUATION 但无 END_HEADERS 标志 | [05-http2-continuation.md](../api-security/references/dos/05-http2-continuation.md) | HTTP/2 CONTINUATION Flood & H2/H3 高级攻击 |
| SYN queue (半连接队列) | [06-tcp-state-exhaustion.md](../api-security/references/dos/06-tcp-state-exhaustion.md) | TCP 协议栈状态耗尽 |
| 权威 DNS 服务器: 无法解析目标域 → 网站"消失" | [07-dns-dos.md](../api-security/references/dos/07-dns-dos.md) | DNS 拒绝服务攻击 |
| 验证证书链 (可选, 很多客户端跳过) | [08-tls-exhaustion.md](../api-security/references/dos/08-tls-exhaustion.md) | TLS/SSL 握手耗尽 |
| 源站: 绕过 CDN 直打 (Origin Shield 失效) | [09-cache-cdn-dos.md](../api-security/references/dos/09-cache-cdn-dos.md) | 缓存 / CDN 拒绝服务 |
| 攻击请求看起来合法 (有效 token、正常参数) | [10-api-abuse.md](../api-security/references/dos/10-api-abuse.md) | API 滥用拒绝服务 |
| Kubernetes ResourceQuota 中 requests.cpu / requests.memory 使用率接近 100% | [11-cloud-container-dos.md](../api-security/references/dos/11-cloud-container-dos.md) | 云原生 / 容器拒绝服务 |
| 源 IP 是目标服务器自身 → 内部防火墙不对其限速 | [12-ssrf-dos.md](../api-security/references/dos/12-ssrf-dos.md) | SSRF 驱动的拒绝服务 |
| 查询层面: 慢查询注入 / 死锁构造 / 全表扫描 | [13-database-dos.md](../api-security/references/dos/13-database-dos.md) | 数据库层拒绝服务 |
| [01-valkey-resp-dos.md](../api-security/references/dos/01-valkey-resp-dos.md) — Valkey RESP 协议预认证 DoS（CVE-2026-27623） | [index.md](../api-security/references/dos/index.md) | DoS 拒绝服务技术库 |

## 4. 数据库注入（10 篇）

> **板块入口**：[`../database-security/SKILL.md`](../database-security/SKILL.md)　·　目录总览：[database-security/references/sqli/index.md](../database-security/references/sqli/index.md)

**references/sqli** — `references/sqli/`

| 症状 / 信号（我看到了什么） | 文档 | 是什么 |
|---|---|---|
| [[sqli-nosqli]] — SQL/NoSQL 注入 | [00-overview.md](../database-security/references/sqli/00-overview.md) | Database Attack Surface — 数据库攻击全景与决策树 |
| [[sqli-nosqli]] — SQL/NoSQL 注入 | [01-sqli-fundamentals.md](../database-security/references/sqli/01-sqli-fundamentals.md) | SQL Injection Core — SQL 注入基础与全类型覆盖 |
| [[01-sqli-fundamentals]] — SQL 注入基础 | [02-sqli-advanced.md](../database-security/references/sqli/02-sqli-advanced.md) | Advanced SQLi & WAF Bypass — 高级注入与绕过技术 |
| [[01-sqli-fundamentals]] — SQL 注入基础 | [03-nosql-injection.md](../database-security/references/sqli/03-nosql-injection.md) | NoSQL Injection — NoSQL 注入攻击 |
| DOCUMENT_ROOT（网站根目录） | [04-config-exposure.md](../database-security/references/sqli/04-config-exposure.md) | Database Config Exposure — 数据库配置泄露 |
| 完整 SQL 语句（包括 INSERT 的敏感数据） | [05-backup-log-leak.md](../database-security/references/sqli/05-backup-log-leak.md) | Database Backup & Log Leak — 数据库备份与日志泄露 |
| 用响应长度、<br/> 数量、CDK 正则命中数判断是否全库渲染。 | [06-card-platform.md](../database-security/references/sqli/06-card-platform.md) | Card-Selling Platform Exploitation — 自动发卡平台攻击手册 |
| 数据行：符合预期格式（长度/字符集/前缀） | [07-data-cleaning.md](../database-security/references/sqli/07-data-cleaning.md) | Database Dump Cleaning — 泄露数据清洗方法论 |
| 刚接触数据库攻击 → [00-overview.md](../api-security/references/jwt/00-overview.md) | [index.md](../database-security/references/sqli/index.md) | 24-database — 数据库攻击技术 |
| SQLi | [sqli-nosqli.md](../database-security/references/sqli/sqli-nosqli.md) | SQLi & NoSQLi (数据库注入高阶实战) |

## 5. Web 攻击链与 CVE 实证（16 篇）

> **板块入口**：[`../attack-chain/SKILL.md`](../attack-chain/SKILL.md)　·　目录总览：[attack-chain/references/cve-case-studies/index.md](../attack-chain/references/cve-case-studies/index.md)

**references/cve-case-studies** — `references/cve-case-studies/`

| 症状 / 信号（我看到了什么） | 文档 | 是什么 |
|---|---|---|
| Blink UAF | [01-browser-sandbox-escape.md](../attack-chain/references/cve-case-studies/01-browser-sandbox-escape.md) | Blink UAF：CSSFontFeatureValuesMap 迭代器悬空指针（CVE-2026 |
| Redis RCE | [02-redis-zipmap-rce.md](../attack-chain/references/cve-case-studies/02-redis-zipmap-rce.md) | Redis/Valkey RESTORE：zipmap 长度前缀步长不一致（CVE-2026-252 |
| cPanel | [03-cpanel-caldav-traversal.md](../attack-chain/references/cve-case-studies/03-cpanel-caldav-traversal.md) | cPanel CalDAV 预认证路径穿越（CVE-2026-29205） |
| Nezha Monitoring | [04-nezha-path-traversal-jwt.md](../attack-chain/references/cve-case-studies/04-nezha-path-traversal-jwt.md) | Nezha Monitoring：路径遍历 + JWT 伪造管理员接管（CVE-2026-53519 |
| LiteLLM | [05-litellm-privesc.md](../attack-chain/references/cve-case-studies/05-litellm-privesc.md) | LiteLLM：API Key 生成绕过角色限制 + 自提权（CVE-2026-47101） |
| NGINX | [06-nginx-rewrite-heapoverflow.md](../attack-chain/references/cve-case-studies/06-nginx-rewrite-heapoverflow.md) | NGINX rewrite 模块：set 缓冲区长度错配堆溢出（CVE-2026-42945） |
| CVE correlation | [cve-correlation-graph.md](../attack-chain/references/cve-case-studies/cve-correlation-graph.md) | CVE Correlation Graph（CVE 关联网） |
| CVE workflow | [cve-workflow.md](../attack-chain/references/cve-case-studies/cve-workflow.md) | CVE Workflow For World-Class Web CTF |
| Board: boards/ctf-website/README.md | [index.md](../attack-chain/references/cve-case-studies/index.md) | CVE 技术库（Web / 内核 / 本地） |
| CVE chain | [multi-cve-chain-playbook.md](../attack-chain/references/cve-case-studies/multi-cve-chain-playbook.md) | Multi-CVE Chain Playbook（多 CVE 组合联合利用） |

**references/recon** — `references/recon/`

| 症状 / 信号（我看到了什么） | 文档 | 是什么 |
|---|---|---|
| subdomain takeover | [01-subdomain-takeover.md](../attack-chain/references/recon/01-subdomain-takeover.md) | 子域名接管深度 |
| CAPTCHA | [captcha-bypass.md](../attack-chain/references/recon/captcha-bypass.md) | 验证码绕过技术与自动化 |
| Cloudflare | [cloudflare-bypass.md](../attack-chain/references/recon/cloudflare-bypass.md) | Cloudflare 绕过：寻找真实源服务器 IP |
| FOFA | [fofa-hunting.md](../attack-chain/references/recon/fofa-hunting.md) | FOFA 资产测绘与漏洞狩猎 |
| Header Fuzzing | [recon-routing.md](../attack-chain/references/recon/recon-routing.md) | Recon & 路由绕过 |
| fingerprint | [version-fingerprinting.md](../attack-chain/references/recon/version-fingerprinting.md) | 版本指纹识别 |

## 6. Web-CTF 比赛与付费墙（15 篇）

> **板块入口**：[`../ctf-sandbox/SKILL.md`](../ctf-sandbox/SKILL.md)　·　目录总览：[ctf-sandbox/references/checklists/index.md](../ctf-sandbox/references/checklists/index.md)

**技术正文** — `references/`

| 症状 / 信号（我看到了什么） | 文档 | 是什么 |
|---|---|---|
| 见下方「技术正文」的条目式打点清单（本文档正文以清单为主，无结构化信号表）。 | [attack-network.md](../ctf-sandbox/references/attack-network.md) | Web 攻击网 |
| [01-recon/captcha-bypass.md](../attack-chain/references/recon/captcha-bypass.md) — 验证码绕过技术与自动化 | [index.md](../ctf-sandbox/references/index.md) | Web CTF技术库 |

**references/checklists** — `references/checklists/`

| 症状 / 信号（我看到了什么） | 文档 | 是什么 |
|---|---|---|
| 见下方「技术正文」的条目式打点清单（本文档正文以清单为主，无结构化信号表）。 | [attack-matrix.md](../ctf-sandbox/references/checklists/attack-matrix.md) | Web CTF Attack Matrix |
| Full request and response. | [evidence.md](../ctf-sandbox/references/checklists/evidence.md) | Evidence Checklist |
| 开题先读 web-ctf-first-30-min.md。 | [index.md](../ctf-sandbox/references/checklists/index.md) | Web CTF Checklists AI Usage |
| Record URL, host, port, scheme, and challenge text. | [web-ctf-first-30-min.md](../ctf-sandbox/references/checklists/web-ctf-first-30-min.md) | Web CTF First 30 Minutes |

**references/kb-index** — `references/kb-index/`

| 症状 / 信号（我看到了什么） | 文档 | 是什么 |
|---|---|---|
| [完整技术索引](../ctf-sandbox/references/kb-index/index.md) | [index.md](../ctf-sandbox/references/kb-index/index.md) | CTF Website 渗透测试知识库 — Web 攻击全表面 118 篇 |

**references/payloads** — `references/payloads/`

| 症状 / 信号（我看到了什么） | 文档 | 是什么 |
|---|---|---|
| payload 需要结合目标上下文，不要盲打。 | [index.md](../ctf-sandbox/references/payloads/index.md) | Web CTF Payload Knowledge AI Usage |
| 见下方「技术正文」的条目式打点清单（本文档正文以清单为主，无结构化信号表）。 | [web-payload-seeds.md](../ctf-sandbox/references/payloads/web-payload-seeds.md) | Web Payload Seeds |

**references/paywall** — `references/paywall/`

| 症状 / 信号（我看到了什么） | 文档 | 是什么 |
|---|---|---|
| Metered paywall: N 篇免费后封锁 (计数器通常在 Cookie/LocalStorage) | [01-paywall-detection-bypass.md](../ctf-sandbox/references/paywall/01-paywall-detection-bypass.md) | Paywall 检测与绕过总览 |
| curl -s -o /dev/null -w '%{size_download}' -H "User-Agent: Googlebot/2.1" URL 响应体 > Chrome UA 响应体 2-10 倍 | [02-http-header-manipulation.md](../ctf-sandbox/references/paywall/02-http-header-manipulation.md) | HTTP 请求头伪装 |
| <script src="https://cdn.tinypass.com/..."> 或 *.piano.io/* 出现在页面 <head> 中 | [03-network-rule-blocking.md](../ctf-sandbox/references/paywall/03-network-rule-blocking.md) | Network 规则拦截 — 阻止 Paywall 脚本加载 |
| DOM 中存在 <script type="application/ld+json"> 且 JSON 包含 articleBody 字段 (比 DOM 中的文本长) | [04-content-extraction.md](../ctf-sandbox/references/paywall/04-content-extraction.md) | 内容提取 — JSON-LD / Next.js / archive.is |
| position: fixed / z-index: 9999 的 overlay 覆盖在正文上方 | [05-dom-css-manipulation.md](../ctf-sandbox/references/paywall/05-dom-css-manipulation.md) | DOM / CSS / Storage 操作 |

**references/workflow** — `references/workflow/`

| 症状 / 信号（我看到了什么） | 文档 | 是什么 |
|---|---|---|
| autopilot.rounds[] | [24h-loop-orchestration.md](../ctf-sandbox/references/workflow/24h-loop-orchestration.md) | 24h Loop Orchestration |

## 7. 云 / K8s / CI-CD（8 篇）

> **板块入口**：[`../cloud-k8s/SKILL.md`](../cloud-k8s/SKILL.md)

**references/attack-paths** — `references/attack-paths/`

| 症状 / 信号（我看到了什么） | 文档 | 是什么 |
|---|---|---|
| AWS | [aws-iam-privesc.md](../cloud-k8s/references/attack-paths/aws-iam-privesc.md) | AWS IAM 权限枚举与提权路径 |
| CI/CD | [ci-cd-pipeline.md](../cloud-k8s/references/attack-paths/ci-cd-pipeline.md) | CI/CD Pipeline 攻击 |
| container | [container-runtime-escape.md](../cloud-k8s/references/attack-paths/container-runtime-escape.md) | 容器运行时逃逸打点 |
| GitHub Actions | [github-actions-abuse-paths.md](../cloud-k8s/references/attack-paths/github-actions-abuse-paths.md) | GitHub Actions 滥用路径 |
| Kubernetes | [k8s-rbac-attack-paths.md](../cloud-k8s/references/attack-paths/k8s-rbac-attack-paths.md) | Kubernetes RBAC 攻击路径 |
| Kubernetes | [kubernetes-container.md](../cloud-k8s/references/attack-paths/kubernetes-container.md) | Kubernetes & 容器逃逸 |
| Serverless | [serverless-lambda.md](../cloud-k8s/references/attack-paths/serverless-lambda.md) | Serverless / Lambda 攻击 |
| Terraform | [terraform-state-secrets.md](../cloud-k8s/references/attack-paths/terraform-state-secrets.md) | Terraform State 与 IaC 凭证泄露 |

## 8. 身份联邦（OAuth / SAML）（4 篇）

> **板块入口**：[`../identity-federation/SKILL.md`](../identity-federation/SKILL.md)

**references/oauth-saml** — `references/oauth-saml/`

| 症状 / 信号（我看到了什么） | 文档 | 是什么 |
|---|---|---|
| OAuth | [01-oauth-attack-chains.md](../identity-federation/references/oauth-saml/01-oauth-attack-chains.md) | OAuth 2.0 攻击全链 |
| session fixation | [02-session-fixation-attacks.md](../identity-federation/references/oauth-saml/02-session-fixation-attacks.md) | Session 固定与 SSO 劫持 |
| OAuth | [oauth-sso.md](../identity-federation/references/oauth-saml/oauth-sso.md) | OAuth 2.0 / OIDC 攻击实战 |
| SAML | [saml-attacks.md](../identity-federation/references/oauth-saml/saml-attacks.md) | SAML 2.0 攻击 |

## 9. 供应链（1 篇）

> **板块入口**：[`../supply-chain-security/SKILL.md`](../supply-chain-security/SKILL.md)

**references/repos** — `references/repos/`

| 症状 / 信号（我看到了什么） | 文档 | 是什么 |
|---|---|---|
| dependency confusion | [dependency-confusion.md](../supply-chain-security/references/repos/dependency-confusion.md) | Dependency Confusion & 供应链攻击 |

## 10. 邮件安全（1 篇）

> **板块入口**：[`../email-security/SKILL.md`](../email-security/SKILL.md)

**references/auth-records** — `references/auth-records/`

| 症状 / 信号（我看到了什么） | 文档 | 是什么 |
|---|---|---|
| email spoofing | [02-email-spoofing.md](../email-security/references/auth-records/02-email-spoofing.md) | 邮件伪造与 SPF / DKIM / DMARC |

## 11. Web JS 运行时（2 篇）

> **板块入口**：[`../js-reverse/SKILL.md`](../js-reverse/SKILL.md)

**references/web-runtime** — `references/web-runtime/`

| 症状 / 信号（我看到了什么） | 文档 | 是什么 |
|---|---|---|
| JS逆向 | [js-runtime.md](../js-reverse/references/web-runtime/js-runtime.md) | JS Runtime / Browser Reversing |
| Web Crypto API | [web-crypto-abuse.md](../js-reverse/references/web-runtime/web-crypto-abuse.md) | Web Crypto API 滥用 |

## 12. 移动端 Web 桥（2 篇）

> **板块入口**：[`../mobile-reverse/SKILL.md`](../mobile-reverse/SKILL.md)

**references/web-bridge** — `references/web-bridge/`

| 症状 / 信号（我看到了什么） | 文档 | 是什么 |
|---|---|---|
| WebView | [01-webview-attacks.md](../mobile-reverse/references/web-bridge/01-webview-attacks.md) | WebView 攻击全技术 |
| Cordova | [02-cordova-reactnative.md](../mobile-reverse/references/web-bridge/02-cordova-reactnative.md) | 跨平台框架攻击面 — Cordova / React Native / Flutter / Elec |

## 13. 已落盘但未进 §2 症状表（补录于 2026-10-10）

> **本节曾被写成「待补板块 · 源库有、尚未落盘 · 68 篇」，并加粗提示读者
> 「不要当成技能包不支持」。这是错的 —— 那些文档当时大多已在盘上。**
> 本节已按 `os.path.isfile` 逐篇核实并改写为「已落盘」。


| 技能 | 篇数 | 文档 |
|---|---|---|
| `kernel-exploit/references/` | 5 | [cifswitch-nss-privesc](../kernel-exploit/references/cifswitch-nss-privesc.md) · [mm-null-ptrace-bypass](../kernel-exploit/references/mm-null-ptrace-bypass.md) · [page-cache-write-family](../kernel-exploit/references/page-cache-write-family.md) · [pintheft-io-uring-page-cache](../kernel-exploit/references/pintheft-io-uring-page-cache.md) · [slab-cross-cache](../kernel-exploit/references/slab-cross-cache.md) |
| `game-reverse/references/` | 6 | [README](../game-reverse/references/README.md) · [game-anti-cheat-bypass](../game-reverse/references/game-anti-cheat-bypass.md) · [game-esp-wallhack-rendering](../game-reverse/references/game-esp-wallhack-rendering.md) · [game-memory-hacking](../game-reverse/references/game-memory-hacking.md) · [game-packet-interception](../game-reverse/references/game-packet-interception.md) · [game-speedhack-time-manipulation](../game-reverse/references/game-speedhack-time-manipulation.md) |

**症状对照**（这些症状现在应读上面那几篇，不是「本包不支持」）：

| 症状 | 读哪篇 |
|---|---|
| 函数跳来跳去，控制流被拉平了 | `reverse-engineering/references/ollvm-deobfuscation.md` |
| 这个函数自己跳自己，是 trampoline 吗 | `reverse-engineering/references/trampoline-detour.md` |
| DLL 怎么注入别的进程 | `reverse-engineering/references/dll-injection.md`（若未落盘读 manual-map-injection） |
| 内存改了但磁盘文件没变 | `reverse-engineering/references/external-memory-rw.md` |
| 程序怎么开机自启 | `reverse-engineering/references/persistence-startup-chain.md` |
| 怎么从 IOC 判断是不是同一个团伙 | `reverse-engineering/references/ioc-extraction.md` |
| 游戏外挂怎么做的，我要自查 | `game-reverse/references/game-anti-cheat-bypass.md` |
| 游戏封包长什么样 | `game-reverse/references/game-packet-interception.md` |
| 内核提权漏洞怎么分析 | `kernel-exploit/references/pintheft-io-uring-page-cache.md` 等 5 篇 |


**仍未落盘**：§12 原表所列 `apk-reverse/techniques/` 25 篇与
`general/techniques/protocol/` 2 篇。上表所列 19 篇经核实**已存在**。
若后续仍有文档落盘，请同步更新本节，并把新篇按症状补进 §2。


## 14. 维护规则

- **新增一篇文档就要回填一行**到本表，格式：症状（用户口吻的观察句）→ 相对链接 → 一句话。
- **不要新增第二套索引**。板块内的小目录索引（`*/references/<sub>/index.md`）可以留，但**症状级检索只有本表一处**。
- **症状列写观察，不写主题名**。「JWT 攻击」不是症状，「解码后发现 header 里 alg 是 none」才是。
- 落盘位置变了（例如某篇从 `api-security` 挪到 `attack-chain`），**改本表的链接，不要新建目录**。
- 补齐板块后，删掉 §12 里对应的行，并把 §0 的数字改对。

---

来源、改编规则、以及「源文档被本机实测推翻」的 27 条清单，见同目录 [`KB-SOURCES.md`](KB-SOURCES.md)。

知识库技能级总览仍以各 `../SKILL.md` 为准；本表只解决「现象 → 读哪一篇」。