# CTF Website 渗透测试知识库 — Web 攻击全表面 118 篇

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/ctf-website/README.md`（GPL-3.0）。原 frontmatter 的 `mcp_tools` 映射已剔除——本技能包未挂载 `run_ctf_tool` / `http_probe`，改用本地工具链。
> **能力域**：本文为技术能力说明，按项目 `scope.md` 直接套用。
> **什么时候用**：命中「见适用信号」这类信号时，把本文当打点清单读；命中即进「步骤」，命中不了就换主题。

## 适用信号

本篇是清单/索引类文档，正文直接以条目给出打点项（见「技术正文」首节）：

- [完整技术索引](../index.md)
- [Web 攻击网](../attack-network.md)
- [前 30 分钟 Checklist](../checklists/web-ctf-first-30-min.md)
- [支付攻击技术目录](../../../api-security/references/payment/index.md)

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

本篇正文以条目式打点清单为主，按顺序执行下列条目：

1. [完整技术索引](../index.md)
2. [Web 攻击网](../attack-network.md)
3. [前 30 分钟 Checklist](../checklists/web-ctf-first-30-min.md)
4. [支付攻击技术目录](../../../api-security/references/payment/index.md)

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

Web CTF / 网站攻防技术库，共 **26 类、118 篇正文**。

## 入口

- [完整技术索引](../index.md)
- [Web 攻击网](../attack-network.md)
- [前 30 分钟 Checklist](../checklists/web-ctf-first-30-min.md)
- [支付攻击技术目录](../../../api-security/references/payment/index.md)

## 流程

```text
Recon → Fingerprint → kb_router → 多路径攻击脚本 → 服务端副作用/Flag 验证 → 证据落盘
```

```powershell
python scripts/ctf-website/kb_router.py "<发现的信号>"
python scripts/misc/kb_doc_audit.py
```

技术文档要求可运行示例、工作流、证据闭环和 MCP 工具映射。

写作口径统一为：入口信号、打点脚本、路径分叉、下一跳、成功标志和 Evidence。每篇文章都要能被 Agent 直接拿来执行一轮路径推进。
