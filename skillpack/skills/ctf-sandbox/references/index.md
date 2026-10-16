# Web CTF技术库

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/ctf-website/techniques/README.md`（GPL-3.0）。原 frontmatter 的 `mcp_tools` 映射已剔除——本技能包未挂载 `run_ctf_tool` / `http_probe`，改用本地工具链。
> [WARN] **落地状态**：本文正文出现的 `scripts/ctf-website/…`、`scripts/misc/…` 是**上游 `LING71671/open-reverselab` 仓库的路径**，未随本包落地（本包没有这两个目录）；照抄会直接报「文件不存在」。技术内容仍可用；要跑等价动作请从上游仓库取脚本，或自备实现。
> **能力域**：本文为技术能力说明，按项目 `scope.md` 直接套用。
> **什么时候用**：命中「见适用信号」这类信号时，把本文当打点清单读；命中即进「步骤」，命中不了就换主题。

## 适用信号

本篇是清单/索引类文档，正文直接以条目给出打点项（见「技术正文」首节）：

- [`../../attack-chain/references/recon/captcha-bypass.md`](../../attack-chain/references/recon/captcha-bypass.md) — 验证码绕过技术与自动化
- [`../../attack-chain/references/recon/cloudflare-bypass.md`](../../attack-chain/references/recon/cloudflare-bypass.md) — Cloudflare 绕过：寻找真实源服务器 IP
- [`../../attack-chain/references/recon/fofa-hunting.md`](../../attack-chain/references/recon/fofa-hunting.md) — FOFA 资产测绘与漏洞狩猎
- [`../../attack-chain/references/recon/recon-routing.md`](../../attack-chain/references/recon/recon-routing.md) — Recon & 路由绕过
- [`../../attack-chain/references/recon/version-fingerprinting.md`](../../attack-chain/references/recon/version-fingerprinting.md) — 版本指纹识别
- [`../../api-security/references/auth/host-header.md`](../../api-security/references/auth/host-header.md) — Host Header 攻击
- [`../../api-security/references/jwt/00-overview.md`](../../api-security/references/jwt/00-overview.md) — JWT 攻击全景
- [`../../api-security/references/jwt/01-alg-none.md`](../../api-security/references/jwt/01-alg-none.md) — JWT `alg: none` 无签名绕过

## 前置

- 前置：目标可达；测试时段与限速已约定（打快了会把自己变成 DoS）。
- 工具定位走探测层，别猜路径：

```powershell
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
$r = Resolve-ReverseToolSpec -Name '<toolid>'   # 例：sqlmap / httpx / ffuf / curl / python
& $r.Command <参数>                                # 永远用完整路径，不依赖 cwd
```

- Python 解释器用探测层的 `python`。
- 本文脚本默认只读、只打点；扩大范围前先回到 scope 确认。

## 步骤

本文正文按下列小节顺序推进，**每一步的完整命令与脚本在「技术正文」对应小节里**（这类文档以代码体 + 表格为主，按小节读比按 bullet 读快）：

1. -recon — 信息收集（5）
2. -auth — 认证与会话（14）
3. -injection — 注入（7）
4. -ssrf — SSRF 与跳转（2）
5. -deserialization — 反序列化（1）
6. -file-attacks — 文件攻击（1）
7. -client — 客户端安全（6）
8. -infra — 基础设施（3）
9. -cve — CVE 工作流（3 + 6 实战）
10. -dos — 拒绝服务（2）
11. -cloud — 云原生（8）
12. -supply-chain — 供应链（1）
13. -payment — 支付业务逻辑（10）
14. -signature — 签名实现（7）

## 判据

判据必须是外部可观测的（状态码、响应字段、差分、落盘文件），不是「命令有输出」。

- 复现同一请求两次，状态码 + 响应体 hash 必须稳定；不稳定说明是噪声源（时间戳/随机数/缓存），先校准 baseline。
- 判为命中的最低门槛：同一 session 下**只有被测变量不同**，业务字段（身份/订单状态/flag）发生可复现变化。

## 坑

- 探针命令在**未本机验证**时不要当成既定事实跑；先用探测层确认 `Available=True`。
- 噪声排除：先固定 baseline（同 URL 同 token 跑 3 次），再只改一个变量做差分。
- 不要把「状态码 200」当命中——WAF/缓存/软 404 都返回 200，命中判据要落到具体业务字段。

## 相关

- 见本技能 `../SKILL.md` 的 references 索引。

## 技术正文

> 以下为原库正文（保留全部技术细节与脚本），仅移除原 `MCP 工具映射` 章节并重写跨文档链接。

Web CTF / 网站攻防技术库。按信号路由到可复现的攻击路径、验证闭环和 MCP 工具。

## 完整目录（26 类 / 118 篇）

### 01-recon — 信息收集（5）

- [`../../attack-chain/references/recon/captcha-bypass.md`](../../attack-chain/references/recon/captcha-bypass.md) — 验证码绕过技术与自动化
- [`../../attack-chain/references/recon/cloudflare-bypass.md`](../../attack-chain/references/recon/cloudflare-bypass.md) — Cloudflare 绕过：寻找真实源服务器 IP
- [`../../attack-chain/references/recon/fofa-hunting.md`](../../attack-chain/references/recon/fofa-hunting.md) — FOFA 资产测绘与漏洞狩猎
- [`../../attack-chain/references/recon/recon-routing.md`](../../attack-chain/references/recon/recon-routing.md) — Recon & 路由绕过
- [`../../attack-chain/references/recon/version-fingerprinting.md`](../../attack-chain/references/recon/version-fingerprinting.md) — 版本指纹识别

### 02-auth — 认证与会话（14）

- [`../../api-security/references/auth/host-header.md`](../../api-security/references/auth/host-header.md) — Host Header 攻击
- [`../../api-security/references/jwt/00-overview.md`](../../api-security/references/jwt/00-overview.md) — JWT 攻击全景
- [`../../api-security/references/jwt/01-alg-none.md`](../../api-security/references/jwt/01-alg-none.md) — JWT `alg: none` 无签名绕过
- [`../../api-security/references/jwt/02-algorithm-confusion.md`](../../api-security/references/jwt/02-algorithm-confusion.md) — JWT 算法混淆 (Algorithm Confusion)
- [`../../api-security/references/jwt/03-weak-key-bruteforce.md`](../../api-security/references/jwt/03-weak-key-bruteforce.md) — JWT 弱 HMAC 密钥爆破
- [`../../api-security/references/jwt/04-kid-injection.md`](../../api-security/references/jwt/04-kid-injection.md) — JWT `kid` 参数注入
- [`../../api-security/references/jwt/05-jku-x5u-abuse.md`](../../api-security/references/jwt/05-jku-x5u-abuse.md) — JWT `jku` / `x5u` 密钥源劫持
- [`../../api-security/references/jwt/06-claim-missing.md`](../../api-security/references/jwt/06-claim-missing.md) — JWT Claim 验证缺失 & Token 混用
- [`../../api-security/references/jwt/07-theft-replay.md`](../../api-security/references/jwt/07-theft-replay.md) — JWT 窃取、重放与持久化
- [`../../api-security/references/jwt/08-cve-library.md`](../../api-security/references/jwt/08-cve-library.md) — JWT 依赖库漏洞 (CVE)
- [`../../api-security/references/jwt/09-toolchain-operations.md`](../../api-security/references/jwt/09-toolchain-operations.md) — JWT 工具链、操作流程与结果矩阵
- [`../../api-security/references/auth/ldap-injection.md`](../../api-security/references/auth/ldap-injection.md) — LDAP Injection
- [`../../identity-federation/references/oauth-saml/oauth-sso.md`](../../identity-federation/references/oauth-saml/oauth-sso.md) — OAuth 2.0 / OIDC 攻击实战
- [`../../identity-federation/references/oauth-saml/saml-attacks.md`](../../identity-federation/references/oauth-saml/saml-attacks.md) — SAML 2.0 攻击

### 03-injection — 注入（7）

- [`../../api-security/references/injection/graphql.md`](../../api-security/references/injection/graphql.md) — GraphQL 攻击实战
- [`../../api-security/references/injection/grpc-protobuf.md`](../../api-security/references/injection/grpc-protobuf.md) — gRPC / Protobuf 攻击
- [`../../api-security/references/injection/hpp-crlf.md`](../../api-security/references/injection/hpp-crlf.md) — HPP / CRLF Injection / Header Injection
- [`../../api-security/references/injection/prototype-pollution.md`](../../api-security/references/injection/prototype-pollution.md) — Prototype Pollution (原型链污染)
- [`../../api-security/references/injection/redos-timing.md`](../../api-security/references/injection/redos-timing.md) — ReDoS & 时序攻击
- [`../../database-security/references/sqli/sqli-nosqli.md`](../../database-security/references/sqli/sqli-nosqli.md) — SQLi & NoSQLi (数据库注入高阶实战)
- [`../../api-security/references/injection/ssti.md`](../../api-security/references/injection/ssti.md) — SSTI (Server-Side Template Injection)

### 04-ssrf — SSRF 与跳转（2）

- [`../../api-security/references/ssrf/open-redirect.md`](../../api-security/references/ssrf/open-redirect.md) — Open Redirect & Redirect Chain Attacks
- [`../../api-security/references/ssrf/ssrf.md`](../../api-security/references/ssrf/ssrf.md) — SSRF (Server-Side Request Forgery)

### 05-deserialization — 反序列化（1）

- [`../../api-security/references/file-attacks/deserialization.md`](../../api-security/references/file-attacks/deserialization.md) — Deserialization Vulnerabilities

### 06-file-attacks — 文件攻击（1）

- [`../../api-security/references/file-attacks/file-upload-xxe-lfi.md`](../../api-security/references/file-attacks/file-upload-xxe-lfi.md) — File Upload / XXE / LFI / Path Traversal

### 07-client — 客户端安全（6）

- [`../../api-security/references/client/admin-bot-xss.md`](../../api-security/references/client/admin-bot-xss.md) — Admin Bot / XSS 实战
- [`../../api-security/references/client/cors-csrf.md`](../../api-security/references/client/cors-csrf.md) — CORS / CSRF 高级攻击
- [`../../js-reverse/references/web-runtime/js-runtime.md`](../../js-reverse/references/web-runtime/js-runtime.md) — JS Runtime / Browser Reversing
- [`../../api-security/references/client/postmessage.md`](../../api-security/references/client/postmessage.md) — PostMessage / 跨域通信攻击
- [`../../js-reverse/references/web-runtime/web-crypto-abuse.md`](../../js-reverse/references/web-runtime/web-crypto-abuse.md) — Web Crypto API 滥用
- [`../../api-security/references/client/websocket.md`](../../api-security/references/client/websocket.md) — WebSocket 攻击实战

### 08-infra — 基础设施（3）

- [`../../api-security/references/infra/http2-attacks.md`](../../api-security/references/infra/http2-attacks.md) — HTTP/2 攻击
- [`../../api-security/references/infra/race-cache-smuggling.md`](../../api-security/references/infra/race-cache-smuggling.md) — Race Condition / Cache Poisoning / Request Smuggling
- [`../../api-security/references/infra/web-cache-deception.md`](../../api-security/references/infra/web-cache-deception.md) — Web Cache Deception

### 09-cve — CVE 工作流（3 + 6 实战）

- [`../../attack-chain/references/cve-case-studies/cve-correlation-graph.md`](../../attack-chain/references/cve-case-studies/cve-correlation-graph.md) — CVE Correlation Graph（CVE 关联网）
- [`../../attack-chain/references/cve-case-studies/cve-workflow.md`](../../attack-chain/references/cve-case-studies/cve-workflow.md) — CVE Workflow For World-Class Web CTF
- [`../../attack-chain/references/cve-case-studies/multi-cve-chain-playbook.md`](../../attack-chain/references/cve-case-studies/multi-cve-chain-playbook.md) — Multi-CVE Chain Playbook（多 CVE 组合联合利用）
- [`../../attack-chain/references/cve-case-studies/01-browser-sandbox-escape.md`](../../attack-chain/references/cve-case-studies/01-browser-sandbox-escape.md) — Blink UAF → 渲染进程沙箱逃逸（CVE-2026-2441）
- [`../../attack-chain/references/cve-case-studies/02-redis-zipmap-rce.md`](../../attack-chain/references/cve-case-studies/02-redis-zipmap-rce.md) — Redis RESTORE zipmap 长度前缀不一致（CVE-2026-25243）
- [`../../attack-chain/references/cve-case-studies/03-cpanel-caldav-traversal.md`](../../attack-chain/references/cve-case-studies/03-cpanel-caldav-traversal.md) — cPanel CalDAV 预认证路径穿越（CVE-2026-29205）
- [`../../attack-chain/references/cve-case-studies/04-nezha-path-traversal-jwt.md`](../../attack-chain/references/cve-case-studies/04-nezha-path-traversal-jwt.md) — Nezha Monitoring 路径遍历 + JWT 伪造（CVE-2026-53519）
- [`../../attack-chain/references/cve-case-studies/05-litellm-privesc.md`](../../attack-chain/references/cve-case-studies/05-litellm-privesc.md) — LiteLLM API Key 生成 + 角色自提权（CVE-2026-47101）
- [`../../attack-chain/references/cve-case-studies/06-nginx-rewrite-heapoverflow.md`](../../attack-chain/references/cve-case-studies/06-nginx-rewrite-heapoverflow.md) — NGINX rewrite set 缓冲区长度错配堆溢出（CVE-2026-42945）

### 11-dos — 拒绝服务（2）

- [`../../api-security/references/dos/01-valkey-resp-dos.md`](../../api-security/references/dos/01-valkey-resp-dos.md) — Valkey RESP 协议预认证 DoS（CVE-2026-27623）
- [`../../api-security/references/infra/http2-attacks.md`](../../api-security/references/infra/http2-attacks.md) — HTTP/2 HPACK 索引引用放大 + 流控停滞（CVE-2026-49975）

### 10-cloud — 云原生（8）

- [`../../cloud-k8s/references/attack-paths/aws-iam-privesc.md`](../../cloud-k8s/references/attack-paths/aws-iam-privesc.md) — AWS IAM 权限枚举与提权路径
- [`../../cloud-k8s/references/attack-paths/ci-cd-pipeline.md`](../../cloud-k8s/references/attack-paths/ci-cd-pipeline.md) — CI/CD Pipeline 攻击
- [`../../cloud-k8s/references/attack-paths/container-runtime-escape.md`](../../cloud-k8s/references/attack-paths/container-runtime-escape.md) — 容器运行时逃逸打点
- [`../../cloud-k8s/references/attack-paths/github-actions-abuse-paths.md`](../../cloud-k8s/references/attack-paths/github-actions-abuse-paths.md) — GitHub Actions 滥用路径
- [`../../cloud-k8s/references/attack-paths/k8s-rbac-attack-paths.md`](../../cloud-k8s/references/attack-paths/k8s-rbac-attack-paths.md) — Kubernetes RBAC 攻击路径
- [`../../cloud-k8s/references/attack-paths/kubernetes-container.md`](../../cloud-k8s/references/attack-paths/kubernetes-container.md) — Kubernetes & 容器逃逸
- [`../../cloud-k8s/references/attack-paths/serverless-lambda.md`](../../cloud-k8s/references/attack-paths/serverless-lambda.md) — Serverless / Lambda 攻击
- [`../../cloud-k8s/references/attack-paths/terraform-state-secrets.md`](../../cloud-k8s/references/attack-paths/terraform-state-secrets.md) — Terraform State 与 IaC 凭证泄露

### 11-supply-chain — 供应链（1）

- [`../../supply-chain-security/references/repos/dependency-confusion.md`](../../supply-chain-security/references/repos/dependency-confusion.md) — Dependency Confusion & 供应链攻击

### 12-payment — 支付业务逻辑（10）

- [`../../api-security/references/payment/payment-bypass.md`](../../api-security/references/payment/payment-bypass.md) — Payment Bypass — 支付绕过深度技术手册
- [`../../api-security/references/payment/payment-callback-async.md`](../../api-security/references/payment/payment-callback-async.md) — Payment Callback & Async Attack — 支付回调与异步攻击深度手册
- [`../../api-security/references/payment/payment-digital-goods.md`](../../api-security/references/payment/payment-digital-goods.md) — Payment Digital Goods & IAP — 虚拟商品/内购攻击手册
- [`../../api-security/references/payment/payment-email-bounce-idor.md`](../../api-security/references/payment/payment-email-bounce-idor.md) — 退信滥用 + 订单号授权绕过窃取卡密
- [`../../api-security/references/payment/payment-logic.md`](../../api-security/references/payment/payment-logic.md) — Payment Logic Attacks — 支付类 Web CTF 技术手册
- [`../../api-security/references/payment/payment-php.md`](../../api-security/references/payment/payment-php.md) — PHP Payment Attacks — PHP 支付专项攻击手册
- [`../../api-security/references/payment/payment-race-lost-update.md`](../../api-security/references/payment/payment-race-lost-update.md) — Payment Race / Lost Update — 余额扣减丢失更新
- [`../../api-security/references/payment/payment-subscription.md`](../../api-security/references/payment/payment-subscription.md) — Payment Subscription — 订阅/定期付款攻击深度手册
- [`../../api-security/references/payment/platform-fingerprints.md`](../../api-security/references/payment/platform-fingerprints.md) — PHP 发卡/电商平台指纹库
- [`../../api-security/references/payment/ticket-rush-api-reversing.md`](../../api-security/references/payment/ticket-rush-api-reversing.md) — Ticket Rush API Reversing — 票务抢购状态机、Token 与风控参数

### 13-signature — 签名实现（7）

- [`../../api-security/references/jwt/00-overview.md`](../../api-security/references/signature/00-overview.md) — Signature Forgery — 签名伪造与验证绕过全景手册
- [`../../api-security/references/signature/01-algorithm.md`](../../api-security/references/signature/01-algorithm.md) — Signature Algorithm Attacks — 签名算法降级/混淆/None 攻击深度手册
- [`../../api-security/references/signature/02-implementation.md`](../../api-security/references/signature/02-implementation.md) — Signature Implementation Bugs — 签名实现缺陷深度手册
- [`../../api-security/references/signature/03-key-attacks.md`](../../api-security/references/signature/03-key-attacks.md) — Key Attacks — 签名密钥攻击深度技术手册
- [`../../api-security/references/signature/04-canonicalization.md`](../../api-security/references/signature/04-canonicalization.md) — Canonicalization Attacks — 签名规范化绕过
- [`../../api-security/references/signature/05-length-extension.md`](../../api-security/references/signature/05-length-extension.md) — Hash Length Extension 攻击 — 深度技术手册
- [`../../api-security/references/signature/06-replay-nonce.md`](../../api-security/references/signature/06-replay-nonce.md) — Replay / Nonce / Timestamp — 重放攻击深度技术手册

### 14-idor — IDOR/越权（2）

- [`../../api-security/references/idor/01-idor-enumeration.md`](../../api-security/references/idor/01-idor-enumeration.md) — IDOR 深度枚举与利用 — 水平/垂直越权实战方法论
- [`../../api-security/references/idor/02-bac-business-logic.md`](../../api-security/references/idor/02-bac-business-logic.md) — 功能级访问控制缺失 (BAC) — 垂直越权与业务逻辑绕过

### 15-mass-assignment — 批量赋值（2）

- [`../../api-security/references/mass-assignment/01-mass-assignment.md`](../../api-security/references/mass-assignment/01-mass-assignment.md) — 批量赋值与属性注入深度利用手册
- [`../../api-security/references/mass-assignment/02-parameter-tampering.md`](../../api-security/references/mass-assignment/02-parameter-tampering.md) — 参数篡改全链 — 价格/数量/优惠券/竞态深度攻击

### 16-rate-limit — 速率限制（2）

- [`../../api-security/references/rate-limit/01-rate-limit-bypass.md`](../../api-security/references/rate-limit/01-rate-limit-bypass.md) — 速率限制绕过 — IP 轮换、Header 操纵与应用层绕过
- [`../../api-security/references/rate-limit/02-brute-force-tactics.md`](../../api-security/references/rate-limit/02-brute-force-tactics.md) — 高级暴力破解 — 凭证喷洒、MFA 疲劳、Hash 策略

### 17-api-attacks — API 攻击（2）

- [`../../api-security/references/api-attacks/01-api-discovery-leak.md`](../../api-security/references/api-attacks/01-api-discovery-leak.md) — API 发现与信息泄露 — Swagger、GraphQL、Source Map 与移动端提取
- [`../../api-security/references/api-attacks/02-api-key-leak.md`](../../api-security/references/api-attacks/02-api-key-leak.md) — API 密钥泄露与利用 — GitHub Dorking、客户端密钥链、云服务滥用

### 18-cors-csp-advanced — 浏览器隔离进阶（2）

- [`../../api-security/references/cors-csp/01-csp-bypass.md`](../../api-security/references/cors-csp/01-csp-bypass.md) — CSP 绕过全技术栈
- [`../../api-security/references/cors-csp/02-xs-leaks-browser-sidechannels.md`](../../api-security/references/cors-csp/02-xs-leaks-browser-sidechannels.md) — XS-Leaks 浏览器侧信道攻击

### 19-dns-email — DNS/邮件（2）

- [`../../attack-chain/references/recon/01-subdomain-takeover.md`](../../attack-chain/references/recon/01-subdomain-takeover.md) — 子域名接管深度
- [`../../email-security/references/auth-records/02-email-spoofing.md`](../../email-security/references/auth-records/02-email-spoofing.md) — 邮件伪造与 SPF / DKIM / DMARC

### 20-oauth-deep — OAuth 深入（2）

- [`../../identity-federation/references/oauth-saml/01-oauth-attack-chains.md`](../../identity-federation/references/oauth-saml/01-oauth-attack-chains.md) — OAuth 2.0 攻击全链
- [`../../identity-federation/references/oauth-saml/02-session-fixation-attacks.md`](../../identity-federation/references/oauth-saml/02-session-fixation-attacks.md) — Session 固定与 SSO 劫持

### 21-mobile-bridge — 移动 Web 桥接（2）

- [`../../mobile-reverse/references/web-bridge/01-webview-attacks.md`](../../mobile-reverse/references/web-bridge/01-webview-attacks.md) — WebView 攻击全技术
- [`../../mobile-reverse/references/web-bridge/02-cordova-reactnative.md`](../../mobile-reverse/references/web-bridge/02-cordova-reactnative.md) — 跨平台框架攻击面 — Cordova / React Native / Flutter / Electron

### 22-dos — DoS/DDoS（13）

- [`../../api-security/references/dos/01-application-layer-dos.md`](../../api-security/references/dos/01-application-layer-dos.md) — Application-Layer DoS
- [`../../api-security/references/dos/02-resource-exhaustion.md`](../../api-security/references/dos/02-resource-exhaustion.md) — Resource Exhaustion & Algorithm Complexity Attacks
- [`../../api-security/references/dos/03-amplification-drdos.md`](../../api-security/references/dos/03-amplification-drdos.md) — Amplification / DRDoS Attacks
- [`../../api-security/references/dos/04-redos.md`](../../api-security/references/dos/04-redos.md) — ReDoS — 正则表达式拒绝服务
- [`../../api-security/references/dos/05-http2-continuation.md`](../../api-security/references/dos/05-http2-continuation.md) — HTTP/2 CONTINUATION Flood & H2/H3 高级攻击
- [`../../api-security/references/dos/06-tcp-state-exhaustion.md`](../../api-security/references/dos/06-tcp-state-exhaustion.md) — TCP 协议栈状态耗尽
- [`../../api-security/references/dos/07-dns-dos.md`](../../api-security/references/dos/07-dns-dos.md) — DNS 拒绝服务攻击
- [`../../api-security/references/dos/08-tls-exhaustion.md`](../../api-security/references/dos/08-tls-exhaustion.md) — TLS/SSL 握手耗尽
- [`../../api-security/references/dos/09-cache-cdn-dos.md`](../../api-security/references/dos/09-cache-cdn-dos.md) — 缓存 / CDN 拒绝服务
- [`../../api-security/references/dos/10-api-abuse.md`](../../api-security/references/dos/10-api-abuse.md) — API 滥用拒绝服务
- [`../../api-security/references/dos/11-cloud-container-dos.md`](../../api-security/references/dos/11-cloud-container-dos.md) — 云原生 / 容器拒绝服务
- [`../../api-security/references/dos/12-ssrf-dos.md`](../../api-security/references/dos/12-ssrf-dos.md) — SSRF 驱动的拒绝服务
- [`../../api-security/references/dos/13-database-dos.md`](../../api-security/references/dos/13-database-dos.md) — 数据库层拒绝服务

### 23-paywall-bypass — Paywall 分析（5）

- [`paywall/01-paywall-detection-bypass.md`](paywall/01-paywall-detection-bypass.md) — Paywall 检测与绕过总览
- [`paywall/02-http-header-manipulation.md`](paywall/02-http-header-manipulation.md) — HTTP 请求头伪装
- [`paywall/03-network-rule-blocking.md`](paywall/03-network-rule-blocking.md) — Network 规则拦截 — 阻止 Paywall 脚本加载
- [`paywall/04-content-extraction.md`](paywall/04-content-extraction.md) — 内容提取 — JSON-LD / Next.js / archive.is
- [`paywall/05-dom-css-manipulation.md`](paywall/05-dom-css-manipulation.md) — DOM / CSS / Storage 操作

## 文档质量基线

每篇正文必须包含：H1 标题、可运行示例、工作流/攻击链、Evidence、MCP 工具映射，并且本地 Markdown 链接必须可解析。

## 实战写法

每篇文章按“入口信号 → 打点脚本 → 路径分叉 → 下一跳 → 成功标志 → Evidence → MCP 工具映射”组织。正文优先回答三个问题：从哪个请求/响应/源码信号进入、用什么脚本或工具把路径打通、成功后跳到哪条更高价值路径。

记录证据时写可复现字段：URL、method、关键 header、payload 变量、状态码、响应差异、时间窗口、listener 日志、flag/凭证/配置所在位置。不要把结尾写成泛泛的报告结论；如果需要表达服务端约束，也放在“路径是否还能成立”的技术语境里。

```powershell
python scripts/misc/kb_doc_audit.py
```

## Web 攻击网与路由

- [攻击网](attack-network.md) — 多入口、多分叉到 Flag 的决策图。
- `kb-index.json` — `kb_router.py` 使用的信号映射。
- `python scripts/ctf-website/kb_router.py "<signal>"` — 按新信号检索。
