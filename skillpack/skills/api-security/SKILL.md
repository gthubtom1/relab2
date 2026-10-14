---
name: api-security
description: API 安全测试：REST/GraphQL/WebSocket 接口发现、JWT/OAuth、BOLA/IDOR/BFLA 越权。用于：接口越权、JWT 弱密钥、GraphQL 内省。
---
# API 安全测试

## ACTION REQUIRED（读完后立刻执行）

1. `NOW`: 读 `../field-journal/precedent-pentest.md` —— 本机做过多轮的常规操作清单，直接照做，不要停在犹豫上
2. `NOW`: **查经验卡** —— `python skills/scripts/experience-card.py search "<你看到的症状>"`。
   命中就读那张卡的 `invariant` + `decision.action`，并**逐条对照** `scope.appliesWhen`
   与 `scope.stopsWhen`：少一条前提就停用；命中任一停止条件就停。
   历史卡**不替代**当前目标的实测证据。详见 `../experience-cards/INDEX.md`。
3. `NOW`: 确认当前任务是否命中本 skill 的适用范围
5. `NEXT`：**工具定位** —— 先载入探测层 `. C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1`（本机固定路径；万一这台机器还没建好、该文件不存在，改成从本文件往上两级的 `..\..\skills\scripts\lib\Bootstrap.ps1`），再 `Resolve-ReverseToolSpec -Name <id>`，按返回的 `Command` 调（完整路径，别依赖 cwd）。**`Get-Command` 返回空 ≠ 本机缺工具**（PATH 快照陷阱，见 `../references/env-selfcheck.md`）；四级探测全部 `Available=False` 才允许报缺。`../TOOLS.md` 是装法说明书，不是路径索引。禁止猜路径。
6. `NEXT`: 缺工具时调用 bootstrap，不要猜路径
7. `ACT`: 按本卡的「工作流」挑**当下适用**的那一条动手；不要停在确认状态

> 覆盖 REST / GraphQL / WebSocket / SOAP 全协议
> 10 阶段方法论，从发现到 CI/CD 集成

## 适用场景

- REST API 安全测试（OpenAPI/Swagger 驱动或盲测）
- GraphQL 安全审计（内省、批查询、别名过载）
- WebSocket 安全测试
- JWT / OAuth 2.0 认证测试
- BOLA/IDOR/BFLA 授权漏洞检测
- API 限速绕过与 DoS 测试

## 10 阶段测试流程

### Phase 1: API 发现与侦察

```text
主动发现：
□ Vespasian: 无头浏览器爬取 → 自动生成 OpenAPI 3.0 / GraphQL SDL 规范
□ Entropy --discover: 从 robots.txt + JS 文件提取端点
□ Kiterunner / ffuf: 爆破未文档化的端点路径
□ 检查常见路径: /swagger.json, /openapi.json, /graphql, /api-docs

GraphQL 内省（三级尝试）：
  1. 标准内省查询
  2. 精简查询（绕过 WAF 全量封禁）
  3. 仅查 __schema { types { name } }（最小探测）
```

### Phase 2: 认证测试

```text
JWT 分析（jwt_tool / Burp）：
□ alg:none 攻击: 修改头部为 "alg":"none"，清空签名
□ 密钥混淆: RS256 公钥 → HS256 对称密钥
□ 弱 HMAC 密钥爆破: jwt_tool -C -d wordlist.txt
□ 过期/声明篡改: 修改 exp/iat/sub/role 声明
□ kid 注入: ../../etc/passwd → HMAC 签名绕过

OAuth 2.0：
□ redirect_uri 操控 → 授权码泄漏
□ CSRF via state 参数缺失
□ Token 在 Referer 头泄漏
□ PKCE 缺失检测

GraphQL 认证：
□ mutation 通过 GET 请求绕过认证（CSRF）
□ 批查询认证绕过
```

### Phase 3: 越权测试（BOLA/IDOR/BFLA）

```text
BOLA（对象级授权绕过）：
□ 遍历数字 ID: /user/1 → /user/2 → /user/3
□ 遍历 UUID
□ 遍历用户名/邮箱
□ Burp Autorize: 双会话重放对比

BFLA（功能级授权绕过）：
□ 普通用户执行管理员 API
□ HTTP 方法切换: GET → PUT → PATCH → DELETE
□ API 版本降级: /v2/admin → /v1/admin
□ 批量操作注入: {"users": [1,2,3]} → {"users": [1,2,3,admin_id]}

工具: Burp Autorize, AuthMatrix, Entropy (malicious_insider persona)
```

### Phase 4: GraphQL 专项

```text
内省泄漏 → 信息暴露检测
别名过载 → 100+ 别名 DoS
批查询 → 10+ 同时查询 DoS
字段重复 → __typename × 500
指令过载 → 递归 @skip/@include
循环查询 → 深度嵌套内省递归
字段建议 → 错误消息信息泄漏
GraphiQL/Playground 暴露 → IDE 公开风险
GET 突变 → CSRF 风险
追踪/调试模式 → 元数据泄漏

工具: FireTail, Escape DAST, api.sh (Phases 1-3)
```

### Phase 5: REST 输入验证

```text
□ HTTP 方法切换: GET→POST→PUT→DELETE→OPTIONS→PATCH
□ Content-Type 篡改: JSON→XML→multipart
□ NoSQL 注入: {"username": {"$gt": ""}}
□ SSRF via URL 参数: webhook URL/头像 URL/导入 URL
□ XXE in XML 端点
□ 参数污染: /api?role=user&role=admin
□ 批量赋值: 向请求体添加 is_admin: true
```

### Phase 6: 业务逻辑与差分测试

```text
□ Entropy compare: diff v1 vs v2 API → 状态码变化/字段删除/延迟回归
□ 多角色工作流测试: admin/user/readonly 权限矩阵
□ 优惠券/积分/价格操控
□ 竞态条件: 并发请求测试 TOCTOU
```

### Phase 7: WebSocket 测试

```text
□ 端点发现
□ 消息注入（注入 payload、原型污染）
□ 超大消息处理
□ 类型混淆
□ 跨站点 WebSocket 劫持（CSWH）
```

### Phase 8: 限速与 DoS

```text
□ 限速绕过 via 头部: X-Forwarded-For, X-Real-IP
□ 路径变体: /api/ → /api → /Api/ → /API/
□ Slowloris 低带宽耗尽
□ GraphQL 批查询深度嵌套 DoS
□ IP 轮换测试（ProxyCat 代理池）
```

### Phase 9: 数据暴露

```text
□ 响应过度暴露: 对比 API 返回 vs UI 展示
□ 分页枚举: ?page=1&limit=10000
□ 错误消息信息泄漏: 堆栈跟踪/内部路径/SQL 错误
□ GraphQL 嵌套遍历访问越权数据
□ OpenAPI 规范暴露敏感端点
```

### Phase 10: CI/CD 集成

```text
□ Entropy --ci --watch: spec 变更时自动重跑
□ Escape DAST: 按严重度阈值自动阻断构建
□ 发现持久化为回归测试
□ StackHawk（开发者优先、ZAP 内核）
```

## 工具链

| 工具 | 用途 | 获取 |
|------|------|------|
| Vespasian | 流量 → OpenAPI/GraphQL 规范 | GitHub: praetorian-inc/vespasian |
| Entropy | LLM 生成攻击场景，5 personas | GitHub: arjinexe/entropy-chaos |
| Escape DAST | 业务逻辑安全测试 | escape.tech |
| api.sh | 8 阶段全协议攻击管道 | GitHub: Sharon-Needles/api |
| FireTail | GraphQL 12 专项测试 | firetail.ai |
| jwt_tool | JWT 全面测试 | GitHub: ticarpi/jwt_tool |
| Burp Autorize | 双会话授权对比 | Burp BApp Store |

## 参考

- `references/rest-graphql-testing.md` — REST + GraphQL 深度测试
- `references/jwt-oauth-testing.md` — JWT + OAuth 安全测试

## 任务完成自检（声称完成前 MUST 通过）

- [ ] 我是否执行了工作流中的每一步（而不是只阅读）？
- [ ] 我是否走了**探测层四级递进**（`Resolve-ReverseToolSpec`）定位实际路径（而不是只跑一条 `Get-Command` 查空就报缺工具、也不是拿 `../TOOLS.md` 里的装法当路径猜）？
- [ ] 我是否产出了可复现证据（命令/脚本/截图/报告）？
- [ ] 我是否完成并回写了 RULES 要求的 Checklist 项？

## 改编参考索引（open-reverselab `kb/ctf-website`）

> 下列 reference 改编自 `LING71671/open-reverselab` 的 `kb/ctf-website/`（GPL-3.0）。
> 每篇统一为「适用信号 / 前置 / 步骤 / 判据 / 坑 / 相关」+ 完整技术正文，
> 「前置」含**本机实测**的工具状态表——照抄原库裸命令前先看那张表。
> **能力域**：本文为技术能力说明，按项目 `scope.md` 直接套用。

### `references/api-attacks/` — API 发现与密钥泄露（2 篇）

- `references/api-attacks/01-api-discovery-leak.md`
- `references/api-attacks/02-api-key-leak.md`

### `references/auth/` — 认证与会话（Host 头、LDAP 注入）（2 篇）

- `references/auth/host-header.md`
- `references/auth/ldap-injection.md`

### `references/client/` — 客户端面（admin bot / CORS / CSRF / postMessage / WebSocket）（4 篇）

- `references/client/admin-bot-xss.md`
- `references/client/cors-csrf.md`
- `references/client/postmessage.md`
- `references/client/websocket.md`

### `references/cors-csp/` — CSP 绕过与 XS-Leaks 侧信道（2 篇）

- `references/cors-csp/01-csp-bypass.md`
- `references/cors-csp/02-xs-leaks-browser-sidechannels.md`

### `references/dos/` — 拒绝服务（应用层、资源耗尽、放大、H2 CONTINUATION、TLS/DNS/缓存/API/DB）（15 篇）

- `references/dos/01-valkey-resp-dos.md`
- `references/dos/index.md`
- `references/dos/01-application-layer-dos.md`
- `references/dos/02-resource-exhaustion.md`
- `references/dos/03-amplification-drdos.md`
- `references/dos/04-redos.md`
- `references/dos/05-http2-continuation.md`
- `references/dos/06-tcp-state-exhaustion.md`
- `references/dos/07-dns-dos.md`
- `references/dos/08-tls-exhaustion.md`
- `references/dos/09-cache-cdn-dos.md`
- `references/dos/10-api-abuse.md`
- `references/dos/11-cloud-container-dos.md`
- `references/dos/12-ssrf-dos.md`
- `references/dos/13-database-dos.md`

### `references/file-attacks/` — 反序列化、文件上传、XXE、LFI（2 篇）

- `references/file-attacks/deserialization.md`
- `references/file-attacks/file-upload-xxe-lfi.md`

### `references/idor/` — 越权（IDOR 枚举、BAC 业务逻辑）（2 篇）

- `references/idor/01-idor-enumeration.md`
- `references/idor/02-bac-business-logic.md`

### `references/infra/` — 基础设施（HTTP/2、竞态与请求走私、缓存欺骗）（3 篇）

- `references/infra/http2-attacks.md`
- `references/infra/race-cache-smuggling.md`
- `references/infra/web-cache-deception.md`

### `references/injection/` — 注入类（GraphQL、gRPC/Protobuf、HPP/CRLF、原型污染、ReDoS、SSTI）（6 篇）

- `references/injection/graphql.md`
- `references/injection/grpc-protobuf.md`
- `references/injection/hpp-crlf.md`
- `references/injection/prototype-pollution.md`
- `references/injection/redos-timing.md`
- `references/injection/ssti.md`

### `references/jwt/` — JWT 攻击专题（alg:none / 算法混淆 / 弱密钥 / kid / jku / claim / 窃取重放 / CVE / 工具链）（11 篇）

- `references/jwt/00-overview.md`
- `references/jwt/01-alg-none.md`
- `references/jwt/02-algorithm-confusion.md`
- `references/jwt/03-weak-key-bruteforce.md`
- `references/jwt/04-kid-injection.md`
- `references/jwt/05-jku-x5u-abuse.md`
- `references/jwt/06-claim-missing.md`
- `references/jwt/07-theft-replay.md`
- `references/jwt/08-cve-library.md`
- `references/jwt/09-toolchain-operations.md`
- `references/jwt/index.md`

### `references/mass-assignment/` — 批量赋值与参数篡改（2 篇）

- `references/mass-assignment/01-mass-assignment.md`
- `references/mass-assignment/02-parameter-tampering.md`

### `references/payment/` — 支付业务逻辑（绕过、回调、虚拟商品、订阅、竞态、PHP、指纹）（11 篇）

- `references/payment/index.md`
- `references/payment/payment-bypass.md`
- `references/payment/payment-callback-async.md`
- `references/payment/payment-digital-goods.md`
- `references/payment/payment-email-bounce-idor.md`
- `references/payment/payment-logic.md`
- `references/payment/payment-php.md`
- `references/payment/payment-race-lost-update.md`
- `references/payment/payment-subscription.md`
- `references/payment/platform-fingerprints.md`
- `references/payment/ticket-rush-api-reversing.md`

### `references/rate-limit/` — 限速绕过与暴力破解（2 篇）

- `references/rate-limit/01-rate-limit-bypass.md`
- `references/rate-limit/02-brute-force-tactics.md`

### `references/signature/` — 签名伪造（算法、实现、密钥、规范化、长度扩展、重放 nonce）（8 篇）

- `references/signature/00-overview.md`
- `references/signature/01-algorithm.md`
- `references/signature/02-implementation.md`
- `references/signature/03-key-attacks.md`
- `references/signature/04-canonicalization.md`
- `references/signature/05-length-extension.md`
- `references/signature/06-replay-nonce.md`
- `references/signature/index.md`

### `references/ssrf/` — SSRF 与开放重定向（2 篇）

- `references/ssrf/open-redirect.md`
- `references/ssrf/ssrf.md`

### `references/` — 根目录



---

## 本技能硬判据

- **BOLA 要用成对请求**：同一资源用「原身份」和「目标身份」各发一次，两个请求除 `Authorization`/Cookie 外逐字节相同（同 URL、同 body、同 header 顺序）。只有「A 成功 + B 也成功」才算越权；单次成功可能只是公开资源。
- **越权判据要换身份而不是换 ID**：`/user/1 → /user/2` 只是枚举；把**同一** ID 换成另一个身份的令牌重放，才能区分「对象级授权缺失」与「对象本来公开」。
- **签名归属判据**：参数能被客户端算出来（断点**看到**明文入参、JS 内可复现）→ 归 `../js-reverse/SKILL.md`；参数由服务端 challenge/nonce 派生且一次性 → 归 `../web-protocol-reverse/SKILL.md` 的协议重放面。两边都不沾的，才留在本卡。
- **限流归属判据**：`429` 由边缘返回（响应头带 `cf-ray`/`server: nginx`）且换 `X-Forwarded-For` 无效 → 限流在网关；若换头即绕过 → 限流在应用，属本卡 `references/rate-limit/01-rate-limit-bypass.md`。

## 工具链与工具联动

| 环节 | 本机怎么调 | 输出接到哪 |
|---|---|---|
| 通道目录 | `powershell -NoProfile -ExecutionPolicy Bypass -File skillpack\skills\scripts\mcp-status.ps1`：注册 / LISTEN / 怎么起三列 | Burp（`9876`）、Reqable 等 HTTP 型平时 `closed` 是**设计**，用到再起；起完重跑确认 `LISTEN` |
| 路径探测 | `. C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1` → `Resolve-ReverseToolSpec -Name httpx` | `Get-Command` 查空 ≠ 缺工具；`jwt_tool`/`semgrep` 这类不在 toolmap 里的，一律走四级探测，全 `Available=False` 才按 `../TOOLS.md` 自装，禁止猜路径 |
| 端点发现 | `ffuf -u target/FUZZ -w <词表>` 爆未文档化路径；`nuclei` 只当入口发现用（命中降级为待验证） | 端点进接口清单，接 `references/api-attacks/01-api-discovery-leak.md` |
| 认证面 | `python jwt_tool.py <JWT> -C -d <词表>`（弱 HMAC 爆破）、`-X k -pk pub.pem`（算法混淆）、`-I -pc role -pv admin`（声明篡改） | 改完令牌必须用**成对请求**在 Burp Repeater 复跑，见 `references/jwt-oauth-testing.md` |
| 授权面 | Burp Autorize 双会话重放对比；越权用配对请求（原身份 + 目标身份） | 结果写进鉴权矩阵，每条 Finding 挂 ≥1 evidence_id |
| 注入与报文面 | `sqlmap -u "url?id=1" --batch`（参数化 SQLi）；`curl --globoff` 手搓边界报文 | 注入细节转 `references/injection/`；报文层走私/缓存见 `references/infra/` |
| 抓包复核 | Reqable MCP（断点 + 重放）、`tshark`（WebSocket/HTTP2 帧） | 只用来看「服务端到底收到了什么」，不替代配对请求 |

## When NOT to use（近邻负例）

- 要还原的是浏览器里 JS 算出的签名/加密参数，目标是把采集器搬出浏览器 → `../web-protocol-reverse/SKILL.md`
- 要审的是源码仓库里的注入与鉴权缺失（白盒、有 commit 可绑）→ `../code-audit/SKILL.md`
- 目标是原生客户端逻辑本身（exe/so/APK 内的算法与校验）→ `../ida-reverse/SKILL.md` 或 `../mobile-reverse/SKILL.md`
- 登录态由 SAML/OIDC/OAuth2 联邦签发，问题在断言/令牌交换而非接口自身 → `../identity-federation/SKILL.md`
- 已拿到越权凭据，下一步是内网横向与域控路径 → `../attack-chain/SKILL.md`
- 目标是 LLM/Agent 的提示注入与工具调用滥用 → `../llm-security/SKILL.md`
- 只是对 Web 服务器做 CVE/配置广扫，还没锁定任何接口 → `../pentest-tools/SKILL.md`

## When to Pivot

信号与判据见 `../ops/skill-pivot-contract.md`。本技能去向：

| 触发证据 | 换到 |
|---|---|
| 断点或代理里**看到**签名/加密参数的明文入参，且本地能复算 | `../js-reverse/SKILL.md` |
| 接口**返回** `403/412/429` 且响应体带 challenge / nonce / 风控 token 字段 | `../web-protocol-reverse/SKILL.md` |
| 响应含 `SAMLResponse` 或 `id_token`，本地**没有**可改签的 JWT | `../identity-federation/SKILL.md` |
| 越权响应里**出现**内网地址（`10.`/`172.16.`/`192.168.` 或容器 DNS 名）且可达 | `../attack-chain/SKILL.md` |
| 同一接口连换 **3 次** 参数（对象/角色/版本各一次）响应**没有**任何差异 | 换请求面：BOLA 改用**成对**请求（原身份 + 目标身份）；仍无差异则换侧信道 `../web-protocol-reverse/SKILL.md` |
| 同一 IP 登录/验证码接口 **≥5 次**失败即被锁（`429` 或账号锁定），且换头无效 | 限流在网关：转 `../cloud-k8s/SKILL.md` 看边缘层，或 `../web-protocol-reverse/SKILL.md` 换客户端指纹 |
| 抓包**显示**请求由原生客户端发出（无浏览器 `User-Agent` 特征、TLS 指纹非浏览器） | `../mobile-reverse/SKILL.md` |
| 端点其实是 gRPC/protobuf 或 WebSocket 二进制帧，HTTP 工具测不动 | `../protocol-reverse/SKILL.md` |
| 报错**返回**堆栈/内部路径，且能定位到具体源码文件 | `../code-audit/SKILL.md` |

## 定义完成

本技能产出算「完成」的**外部可观测**条件（不许写形容词）：

- 每个 Finding 有 `evidence_ids`（≥1），`validated` 的 ≥2 条独立证据
- 越权/缺陷的复现命令落盘，且在同一环境可重放
- 报告含接口清单 + 鉴权矩阵（谁能调什么）

## 输出契约

```
FACT:       <观察，带来源：命令 / 文件:行 / Evidence ID>
HYPOTHESIS: <可测试断言 + confidence: high|medium|low>（状态见 `../ops/binary-model.md`）
QUESTION:   <当前最大不确定点>
NEXT:       <继续 | 换技能 | 停止（附成本判据）>
```

## 置信度词表

词表见 `../ops/confidence-vocabulary.md`。本技能特有判据：

- `confirmed`：同一条越权同时有「请求 A 成功 / 请求 B（换身份）成功」两条实测
- `low`：仅凭响应字段命名推断权限模型，未实际换身份验证
