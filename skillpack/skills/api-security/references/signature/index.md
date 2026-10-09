# 13-signature — 签名伪造与验证绕过

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/ctf-website/techniques/13-signature/README.md`（GPL-3.0）。原 frontmatter 的 `mcp_tools` 映射已剔除——本技能包未挂载 `run_ctf_tool` / `http_probe`，改用本地工具链。
> **授权范围**：仅限 CTF 靶场 / AWD 赛场 / 已签署授权的测试环境。任何真实第三方目标、真实凭据、真实支付/生产流量都禁止套用本文流程。
> **什么时候用**：命中「见适用信号」这类信号时，把本文当打点清单读；命中即进「步骤」，命中不了就换主题。

## 适用信号

本篇是清单/索引类文档，正文直接以条目给出打点项（见「技术正文」首节）：

- JWT 签名: [02-auth/jwt/](../jwt/)
- OAuth state/signature: [02-auth/oauth-sso.md](../../../identity-federation/references/oauth-saml/oauth-sso.md)
- SAML XML Signature: [02-auth/saml-attacks.md](../../../identity-federation/references/oauth-saml/saml-attacks.md)
- 支付回调签名: [12-payment/payment-callback-async.md](../payment/payment-callback-async.md)
- PHP 签名绕过: [12-payment/payment-php.md](../payment/payment-php.md)

## 前置

- 授权：目标在 scope 内（`case-init.ps1` 已 grant），测试时段与限速已约定。
- 工具定位走探测层，别猜路径：

```powershell
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
$r = Resolve-ReverseToolSpec -Name '<toolid>'   # 例：sqlmap / httpx / ffuf / curl / python
& $r.Command <参数>                                # 永远用完整路径，不依赖 cwd
```

- Python 解释器用探测层的 `python`（本机逆向库集中在 `D:\EXE\python\python.exe`，`venv-re` 是空壳，别去那里找库）。
- 本文脚本默认只读、只打点；扩大范围前先回到 scope 确认。

## 步骤

本文正文按下列小节顺序推进，**每一步的完整命令与脚本在「技术正文」对应小节里**（这类文档以代码体 + 表格为主，按小节读比按 bullet 读快）：

1. 快速查找
2. 跨文件引用

## 判据

判据必须是外部可观测的（状态码、响应字段、差分、落盘文件），不是「命令有输出」。

- 复现同一请求两次，状态码 + 响应体 hash 必须稳定；不稳定说明是噪声源（时间戳/随机数/缓存），先校准 baseline。
- 判为命中的最低门槛：同一 session 下**只有被测变量不同**，业务字段（身份/订单状态/flag）发生可复现变化。

## 坑

- 探针命令在**未本机验证**时不要当成既定事实跑；先用探测层确认 `Available=True`。
- 噪声排除：先固定 baseline（同 URL 同 token 跑 3 次），再只改一个变量做差分。
- 不要把「状态码 200」当命中——WAF/缓存/软 404 都返回 200，命中判据要落到具体业务字段。

## 相关

- 见本技能 `../../SKILL.md` 的 references 索引。

## 技术正文

> 以下为原库正文（保留全部技术细节与脚本），仅移除原 `MCP 工具映射` 章节并重写跨文档链接。

> 签名 = 信任的数学表达。打破它 = 伪造信任。

## 快速查找

| 你发现了 | 去看 |
|---|---|
| `sign_type=MD5` / `alg=none` / 空签名 | [01-algorithm.md](01-algorithm.md) |
| `strcmp` / `==` vs `===` / magic hash / PHP type juggling | [02-implementation.md](02-implementation.md) |
| 弱密钥 / 硬编码密钥 / 密钥在 JS 里 / .env 泄露 | [03-key-attacks.md](03-key-attacks.md) |
| 参数顺序不同签名不同 / XML parse差异 / URL编码差异 | [04-canonicalization.md](04-canonicalization.md) |
| MD5/SHA1/SHA2 签名 / 知道 `sign = hash(secret + data)` | [05-length-extension.md](05-length-extension.md) |
| 重放 / nonce 复用 / timestamp 过期绕过 | [06-replay-nonce.md](06-replay-nonce.md) |
| 不确定是哪类 / 想做全覆盖 | [00-overview.md](00-overview.md) |

## 跨文件引用

- JWT 签名: [02-auth/jwt/](../jwt/)
- OAuth state/signature: [02-auth/oauth-sso.md](../../../identity-federation/references/oauth-saml/oauth-sso.md)
- SAML XML Signature: [02-auth/saml-attacks.md](../../../identity-federation/references/oauth-saml/saml-attacks.md)
- 支付回调签名: [12-payment/payment-callback-async.md](../payment/payment-callback-async.md)
- PHP 签名绕过: [12-payment/payment-php.md](../payment/payment-php.md)
