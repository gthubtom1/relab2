# Cloudflare 绕过：寻找真实源服务器 IP

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/ctf-website/techniques/01-recon/cloudflare-bypass.md`（GPL-3.0）。原 frontmatter 的 `mcp_tools` 映射已剔除——本技能包未挂载 `run_ctf_tool` / `http_probe`，改用本地工具链。
> **能力域**：本文为技术能力说明，按项目 `scope.md` 直接套用。
> **什么时候用**：命中「Cloudflare / CF-Ray / CDN / 源站IP」这类信号时，把本文当打点清单读；命中即进「步骤」，命中不了就换主题。

## 适用信号

- Cloudflare
- CF-Ray
- CDN
- 源站IP
- origin IP
- DNS history
- SecurityTrails
- Censys

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

1. 源站候选评分
2. 方法 1：DNS 历史记录查询 — Cloudflare 代理之前，域名曾直接解析到源站 IP。
3. 方法 2：SSL 证书搜索 — 源服务器的 SSL 证书可能先于 Cloudflare 部署或被多个服务共用。
4. 方法 3：子域名爆破 + IP 探活 — 所有子域名不一定都经过 Cloudflare。
5. 方法 4：邮件头分析 — 目标发出的邮件可能暴露真实 IP。
6. 方法 5：Cloudflare 配置缺陷
7. Workers 滥用
8. Cache Poisoning / 绕过
9. Zone Transfer / AXFR
10. 方法 6：互联网存档
11. 方法 7：CDN 厂商 IP 段排除
12. 源站直连对比脚本

## 判据

判据必须是外部可观测的（状态码、响应字段、差分、落盘文件），不是「命令有输出」。

- **输入信号** — HTTP 响应头含 `Server: cloudflare` / `CF-Ray` / `CF-Cache-Status`
- **输入信号** — 访问返回 Cloudflare 的 JS Challenge / CAPTCHA 页面
- **输入信号** — 直接访问 IP 返回证书错误或不同页面
- **输入信号** — DNS 记录指向 Cloudflare IP 段（`104.*`, `172.67.*`, `162.158.*` 等）
- **输入信号** — 子域名解析到 Cloudflare 但主域名可能不经过
- **Evidence** — 保存 baseline 与单变量 probe 的完整请求、响应状态、关键响应头和正文摘要。
- **Evidence** — 将“响应差异”与服务端副作用分开记录；只有权限、状态、数据或 Flag 可重复变化才算确认。
- **Evidence** — 固定 session、输入、并发参数和时间窗口重放，记录成功响应、失败样本和下一跳。
- **Evidence** — 输出统一放入 `exports/ctf-website/<case>/`，凭据只用 `REDACTED` 占位，自动检索 `flag{}`、`CTF{}`、`DASCTF{}`。
- **Evidence** — `origin_candidates.json`: IP、来源、ASN、证书、端口、score、直连响应摘要。
- **Evidence** — 成功样本: `curl --resolve domain:443:ip https://domain/` 返回同站内容或进入更深业务错误。
- **Evidence** — 失败样本: IP 返回默认页、证书不匹配、body hash 完全不同、Cloudflare 段未排除。

## 坑

- 探针命令在**未本机验证**时不要当成既定事实跑；先用探测层确认 `Available=True`。
- 噪声排除：先固定 baseline（同 URL 同 token 跑 3 次），再只改一个变量做差分。
- 不要把「状态码 200」当命中——WAF/缓存/软 404 都返回 200，命中判据要落到具体业务字段。

## 相关

- 见本技能 `../../SKILL.md` 的 references 索引。

## 技术正文

> 以下为原库正文（保留全部技术细节与脚本），仅移除原 `MCP 工具映射` 章节并重写跨文档链接。

## 场景

目标站点使用了 Cloudflare CDN/WAF 保护，直接访问域名被 Cloudflare 拦截（JS Challenge / CAPTCHA / 5xx 盾）。需要绕过 Cloudflare 直接访问源服务器 IP，或利用 Cloudflare 配置缺陷穿透防护。

## 输入信号

- HTTP 响应头含 `Server: cloudflare` / `CF-Ray` / `CF-Cache-Status`
- 访问返回 Cloudflare 的 JS Challenge / CAPTCHA 页面
- 直接访问 IP 返回证书错误或不同页面
- DNS 记录指向 Cloudflare IP 段（`104.*`, `172.67.*`, `162.158.*` 等）
- 子域名解析到 Cloudflare 但主域名可能不经过

## 0. 源站候选评分

| 证据 | 加分 | 命中样本 | 失败样本 |
|------|------|----------|----------|
| 历史 A 记录不在 CDN 段 | +3 | 旧 IP 直连返回同站标题 | IP 已下线 |
| 证书 SAN/CN 含目标域 | +3 | `--resolve` 后 TLS 证书匹配 | 共享证书/旧证书 |
| 子域名同 ASN/同证书 | +2 | `api/dev/admin` 指向非 CDN | 只是第三方服务 |
| 直连 body hash 接近 | +4 | 标题、静态资源路径一致 | 默认 nginx/tomcat 页 |
| 直连出现更具体错误 | +2 | 绕过 CF 后进应用错误 | WAF 仍在源站 |
| IP 端口暴露管理面 | +3 | 80/443/8080/8443 有同站痕迹 | 蜜罐或共享主机 |

## 方法 1：DNS 历史记录查询

Cloudflare 代理之前，域名曾直接解析到源站 IP。

```bash
# SecurityTrails DNS 历史
curl -s "https://api.securitytrails.com/v1/history/<domain>/dns/a" \
  -H "APIKEY: <key>" | jq '.records[].values[].ip'

# DNSDumpster
# 在线: https://dnsdumpster.com/

# ViewDNS.info
curl -s "https://viewdns.info/iphistory/?domain=<domain>"

# CRT.sh 证书透明度日志（SSL证书曾暴露IP）
curl -s "https://crt.sh/?q=%25.<domain>&output=json" | jq -r '.[].name_value' | sort -u
```

## 方法 2：SSL 证书搜索

源服务器的 SSL 证书可能先于 Cloudflare 部署或被多个服务共用。

```bash
# Censys 搜索
censys search "services.tls.certificates.leaf_data.subject.common_name:<domain>" 

# Shodan
shodan search "ssl.cert.subject.CN:<domain>"

# FOFA
# 查询: cert="<domain>" && !"cloudflare"

# Censys CLI
censys ipv4 "services.tls.certificates.leaf_data.names:<domain>"
```

## 方法 3：子域名爆破 + IP 探活

所有子域名不一定都经过 Cloudflare。

```bash
# 子域名爆破
ffuf -w subdomains.txt -u https://FUZZ.<domain> -mc 200,301,403

# 提取子域名解析的 IP
for sub in $(cat subs.txt); do
  dig +short $sub.<domain>
done | sort -u > all_ips.txt

# 对每个 IP 测试直接访问
while read ip; do
  curl -s -k --resolve <domain>:443:$ip https://<domain> | head
done < all_ips.txt
```

## 方法 4：邮件头分析

目标发出的邮件可能暴露真实 IP。

```
分析条件：
1. 注册/找回密码 → 触发邮件发送
2. 查看邮件原始头 → Received: from mail.<domain> ([1.2.3.4])
3. SPF 记录中的 ip4 段
```

```bash
dig TXT <domain> | grep spf
# "v=spf1 ip4:1.2.3.4 ip4:5.6.7.8 -all"
# 这些可能是源站 IP 或出口 IP
```

## 方法 5：Cloudflare 配置缺陷

### Workers 滥用
```bash
# Cloudflare Workers 可做反向代理，但配置不当会暴露内部服务
# 探测: workers.dev 子域名
ffuf -w words.txt -u https://<name>.<sub>.workers.dev
```

### Cache Poisoning / 绕过
```bash
# 利用 header 绕过缓存
curl -H "CF-Connecting-IP: 127.0.0.1" https://target.com/admin
curl -H "X-Forwarded-For: 127.0.0.1" https://target.com/admin
curl -H "X-Originating-IP: 127.0.0.1" https://target.com/admin内部端点
```

### Zone Transfer / AXFR
```bash
# 尝试 DNS 域传送
dig AXFR <domain> @ns1.<domain>
```

## 方法 6：互联网存档

```bash
# Wayback Machine 中的旧 IP
curl -s "https://web.archive.org/cdx/search/cdx?url=*.<domain>&output=json&fl=original" | jq -r '.[][]' | grep -oP '\d+\.\d+\.\d+\.\d+' | sort -u

# Common Crawl
# 在线: https://commoncrawl.org/
```

## 方法 7：CDN 厂商 IP 段排除

```bash
# Cloudflare IP ranges
curl -s https://www.cloudflare.com/ips-v4

# 从已知 IP 中排除 CDN IP，余下的可能是源站
grep -v -F -f cloudflare_ips.txt all_ips.txt > candidate_ips.txt
```

## 8. 源站直连对比脚本

```python
import hashlib
import json
import requests

def body_hash(text):
    return hashlib.sha256(text[:4096].encode(errors="ignore")).hexdigest()[:16]

def fetch(url, host=None, ip=None):
    headers = {}
    target = url
    if host and ip:
        headers["Host"] = host
        scheme = "https" if url.startswith("https") else "http"
        target = f"{scheme}://{ip}/"
    r = requests.get(target, headers=headers, timeout=8, verify=False, allow_redirects=False)
    return {
        "status": r.status_code,
        "len": len(r.text),
        "hash": body_hash(r.text),
        "title": (r.text.split("<title>", 1)[1].split("</title>", 1)[0] if "<title>" in r.text else "")[:120],
        "server": r.headers.get("Server", ""),
        "location": r.headers.get("Location", ""),
    }

def compare_origin(domain, ips):
    base = fetch(f"https://{domain}/")
    rows = []
    for ip in ips:
        try:
            direct = fetch(f"https://{domain}/", host=domain, ip=ip)
        except Exception as e:
            rows.append({"ip": ip, "error": str(e)})
            continue
        score = 0
        if direct["hash"] == base["hash"]:
            score += 4
        if direct["title"] and direct["title"] == base["title"]:
            score += 3
        if direct["status"] in (200, 301, 302, 401, 403, 500):
            score += 1
        rows.append({"ip": ip, "score": score, "base": base, "direct": direct})
    print(json.dumps(sorted(rows, key=lambda x: x.get("score", 0), reverse=True), ensure_ascii=False, indent=2))
```

## 工具清单

| 工具 | 用途 |
|------|------|
| CloudFlair | 基于 Censys 的源站 IP 发现 |
| CloudUnflare | 多方法组合探测 |
| Shodan / Censys / FOFA | 证书/服务搜索 |
| SecurityTrails | DNS 历史 |
| dnsdumpster | DNS 可视化 + 历史记录 |
| crt.sh | 证书透明度日志 |
| ffuf | 子域名爆破 |
| tcpdump / Wireshark | 抓包分析 |

## 攻击链

```
1. 确认目标经过 Cloudflare → 记录 CF-Ray / Server header
2. DNS 历史 → 查询 SecurityTrails/DNSDumpster 旧 A 记录
3. SSL 证书 → Censys/Shodan/crt.sh 搜索证书关联 IP
4. 子域名枚举 → 爆破子域名 → 提取所有解析 IP
5. 排除 CDN IP 段 → 余下 IP 逐一测试直连
6. 找到源站 IP → curl --resolve 验证 → 绕过 Cloudflare WAF
```

## Evidence

- 保存 baseline 与单变量 probe 的完整请求、响应状态、关键响应头和正文摘要。
- 将“响应差异”与服务端副作用分开记录；只有权限、状态、数据或 Flag 可重复变化才算确认。
- 固定 session、输入、并发参数和时间窗口重放，记录成功响应、失败样本和下一跳。
- 输出统一放入 `exports/ctf-website/<case>/`，凭据只用 `REDACTED` 占位，自动检索 `flag{}`、`CTF{}`、`DASCTF{}`。
- `origin_candidates.json`: IP、来源、ASN、证书、端口、score、直连响应摘要。
- 成功样本: `curl --resolve domain:443:ip https://domain/` 返回同站内容或进入更深业务错误。
- 失败样本: IP 返回默认页、证书不匹配、body hash 完全不同、Cloudflare 段未排除。
