# Web CTF First 30 Minutes

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/ctf-website/checklists/web-ctf-first-30-min.md`（GPL-3.0）。原 frontmatter 的 `mcp_tools` 映射已剔除——本技能包未挂载 `run_ctf_tool` / `http_probe`，改用本地工具链。
> **能力域**：本文为技术能力说明，按项目 `scope.md` 直接套用。
> **什么时候用**：命中「见适用信号」这类信号时，把本文当打点清单读；命中即进「步骤」，命中不了就换主题。

## 适用信号

本篇是清单/索引类文档，正文直接以条目给出打点项（见「技术正文」首节）：

- Record URL, host, port, scheme, and challenge text.
- `curl -i -k <url>`: status, redirects, cookies, server headers.
- Check robots, sitemap, common static paths, source maps.
- Save JS bundle list and API route hints.
- Identify auth model: cookie, JWT, session id, localStorage, CSRF.
- Enumerate obvious routes manually before brute force.
- Inspect forms, hidden fields, JSON APIs, upload endpoints.
- Try method changes: `GET/POST/PUT/PATCH/DELETE/OPTIONS`.

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

1. -5 min: Baseline
2. -15 min: Surface Map
3. -25 min: Bug-Class Probes
4. -30 min: Decide Path

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

## 0-5 min: Baseline

- Record URL, host, port, scheme, and challenge text.
- `curl -i -k <url>`: status, redirects, cookies, server headers.
- Check robots, sitemap, common static paths, source maps.
- Save JS bundle list and API route hints.
- Identify auth model: cookie, JWT, session id, localStorage, CSRF.

## 5-15 min: Surface Map

- Enumerate obvious routes manually before brute force.
- Inspect forms, hidden fields, JSON APIs, upload endpoints.
- Try method changes: `GET/POST/PUT/PATCH/DELETE/OPTIONS`.
- Try content types: form, JSON, XML, multipart.
- Check state transitions: register -> login -> profile -> admin -> export.

## 15-25 min: Bug-Class Probes

- Reflected/stored sinks: XSS/HTML injection/CRLF.
- Backend errors: SQLi, NoSQLi, SSTI, template parse errors.
- URL fetchers: SSRF, redirect handling, DNS-only callbacks.
- File paths: traversal, upload extraction, include/import.
- Token logic: JWT alg/kid/jku, weak secret, unsigned tokens.
- Race/cache: duplicate coupon, reset token reuse, cache key mismatch.

## 25-30 min: Decide Path

- Pick the strongest signal, not the most familiar exploit class.
- Record dead ends with evidence.
- If frontend looks rich/obfuscated, switch to JSHook/browser runtime.
- If no signal, enumerate parameters and hidden routes with targeted wordlists.
