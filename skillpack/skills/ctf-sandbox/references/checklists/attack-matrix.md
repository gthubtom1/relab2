# Web CTF Attack Matrix

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/ctf-website/checklists/attack-matrix.md`（GPL-3.0）。原 frontmatter 的 `mcp_tools` 映射已剔除——本技能包未挂载 `run_ctf_tool` / `http_probe`，改用本地工具链。
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

1. **Login** — SQLi/NoSQLi, timing, default creds, password reset
2. **JWT** — alg/kid/jku, weak secret, claim trust
3. **Upload** — extension confusion, MIME, polyglot, zip slip, parser SSRF
4. **URL import** — SSRF, redirect, DNS, IPv6, internal names
5. **Template preview** — SSTI, include/import, sandbox escape
6. **Search/filter** — SQLi/NoSQLi, regex DoS, prototype pollution
7. **GraphQL** — introspection, batching, field auth
8. **WebSocket** — replay, IDOR, sequencing, race
9. **Admin bot** — XSS, CSP bypass, cookie exfil via allowed channel
10. **Cache/proxy** — unkeyed header, host poison, request smuggling
11. **Export/report** — SSRF, local file, XSS in renderer
12. **Source maps** — API endpoints, secrets, route names, old code

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

Use this after the first 30-minute baseline to avoid tunnel vision.

| Surface | If You See | Try |
|---|---|---|
| Login | username/password JSON | SQLi/NoSQLi, timing, default creds, password reset |
| JWT | bearer or cookie JWT | alg/kid/jku, weak secret, claim trust |
| Upload | image/pdf/archive | extension confusion, MIME, polyglot, zip slip, parser SSRF |
| URL import | image/webhook/link preview | SSRF, redirect, DNS, IPv6, internal names |
| Template preview | email/report/theme | SSTI, include/import, sandbox escape |
| Search/filter | q/sort/order | SQLi/NoSQLi, regex DoS, prototype pollution |
| GraphQL | `/graphql` | introspection, batching, field auth |
| WebSocket | realtime app | replay, IDOR, sequencing, race |
| Admin bot | URL submission | XSS, CSP bypass, cookie exfil via allowed channel |
| Cache/proxy | `X-Cache` | unkeyed header, host poison, request smuggling |
| Export/report | PDF/HTML render | SSRF, local file, XSS in renderer |
| Source maps | `.map` files | API endpoints, secrets, route names, old code |

Rule: if a path has no developer-plausible route to the secret, pivot.
