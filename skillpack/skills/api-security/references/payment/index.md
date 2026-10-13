# 12-payment — 支付、订单与票务业务逻辑

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/ctf-website/techniques/12-payment/README.md`（GPL-3.0）。原 frontmatter 的 `mcp_tools` 映射已剔除——本技能包未挂载 `run_ctf_tool` / `http_probe`，改用本地工具链。
> **能力域**：本文为技术能力说明，按项目 `scope.md` 直接套用。
> **什么时候用**：命中「见适用信号」这类信号时，把本文当打点清单读；命中即进「步骤」，命中不了就换主题。

## 适用信号

- 见下方「技术正文」的条目式打点清单（本文档正文以清单为主，无结构化信号表）。

## 前置

- 授权：目标在 scope 内（`case-init.ps1` 已 grant），测试时段与限速已约定。
- 工具定位走探测层，别猜路径：

```powershell
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
$r = Resolve-ReverseToolSpec -Name '<toolid>'   # 例：sqlmap / httpx / ffuf / curl / python
& $r.Command <参数>                                # 永远用完整路径，不依赖 cwd
```

- Python 解释器用探测层的 `python`。
- 本文脚本默认只读、只打点；扩大范围前先回到 scope 确认。

## 步骤

1. 本篇为索引/概览文档，按下方「技术正文」中给出的路由表选具体专题。

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

| 信号 | Technique |
|---|---|
| 通用订单/金额/状态机 | [payment-logic.md](payment-logic.md) |
| 参数篡改、类型混淆、零元购 | [payment-bypass.md](payment-bypass.md) |
| 回调、异步、幂等与竞态 | [payment-callback-async.md](payment-callback-async.md) |
| 余额/quota 共享行写入、Lost Update、乐观锁冲突 | [payment-race-lost-update.md](payment-race-lost-update.md) |
| 订单邮件退信、游客查询与卡密 IDOR | [payment-email-bounce-idor.md](payment-email-bounce-idor.md) |
| 支付平台/CMS/网关指纹 | [platform-fingerprints.md](platform-fingerprints.md) |
| PHP 支付实现 | [payment-php.md](payment-php.md) |
| 订阅与续费 | [payment-subscription.md](payment-subscription.md) |
| 数字商品/IAP | [payment-digital-goods.md](payment-digital-goods.md) |
| 抢票、project/screen/SKU、prepare/create、ptoken/ctoken | [ticket-rush-api-reversing.md](ticket-rush-api-reversing.md) |

白盒参考源码固定在 `../../sources/`，Technique 只保留可复用模型和验证步骤。
