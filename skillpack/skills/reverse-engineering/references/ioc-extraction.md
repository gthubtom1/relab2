# IOC 提取与分级

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/pe-reverse/techniques/06-ioc-extraction/01-ioc-extraction.md`（已适配本机工具链）
> **什么时候用**：分析完目标 PE，需要产出可入库的威胁指标（C2 地址、文件路径、注册表键、互斥体、UA），
> 交给检测工程（YARA / Sigma / TI 平台）。
>
> **与已有文档的分工**：
> - `procmon-patterns.md` — **采集端**（拿到 CSV）。本篇是**消费端**（从 CSV + 静态分析里提指标）。
> - `yara-rule-writing.md` — 把本篇的指标变成检测规则。
> - `persistence-startup-chain.md` — 持久化类指标的专项展开。
>
> **原则**：**每个 IOC 必须带证据等级**。「strings 里出现过」不等于「这是 C2」。
> 一份 30 条的 confirmed 列表远比 200 条 possible 的有用。

## 适用信号

- 静态分析（反编译/字符串/导入）已完成，需要汇总指标。
- 有 Procmon CSV（见 `procmon-patterns.md`）可以交叉验证静态猜测。
- 要写 YARA / Sigma 规则，或往 TI 平台推送。

## 前置

```powershell
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
$r2 = (Resolve-ReverseToolSpec -Name 'r2').Command
$floss = (Resolve-ReverseToolSpec -Name 'floss').Command   # 静态+栈+解码三路字符串
$py  = (Resolve-ReverseToolSpec -Name 'pyre').Command
```

★ **`floss` 比裸 `strings` 强**：它会做栈字符串解码、API hash 反解。
静态 `iz` 只能看到明文。

## 步骤

### 1. 提取候选（floss 三路）

```powershell
& $floss .\sample.exe                    # 全部（静态+栈+解码）
& $floss --only static .\sample.exe       # 只静态字符串
& $floss --only decoded .\sample.exe     # 只解码字符串（栈构造的）
& $floss --only stack .\sample.exe       # 只栈字符串
```

或者用 r2：

```powershell
& $r2 -2 -qc 'izz~http' .\sample.exe          # 大小写不敏感全字符串
& $r2 -2 -qc 'izz~mutex' .\sample.exe
```

★ `floss` 输出里的地址形态是 `0x0007ff...`，用于后续定位引用。

### 2. 按类别正则提取

```python
# ioc_extract.py
import re, sys, json, collections

data = open(sys.argv[1], "rb").read()

def strings(b, minlen=4):
    cur = bytearray()
    for ch in b:
        if 32 <= ch < 127:
            cur.append(ch)
        else:
            if len(cur) >= minlen:
                yield cur.decode("ascii")
            cur = bytearray()

RE_DOMAIN = re.compile(r"\b(?:[a-zA-Z0-9-]+\.){1,}[a-zA-Z]{2,}\b")
RE_IP     = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
RE_URL    = re.compile(r"https?://[^\s\"'<>]+")
RE_PATH   = re.compile(r"[A-Za-z]:\\[^\s\"'<>|*?]{3,}")
RE_UNI    = re.compile(r"(?:[A-Za-z]:\\|%[A-Z]+%\\)[^\s\x00]{3,}", re.I)
RE_REG    = re.compile(r"(?:HKEY_[A-Z_]+|HK(?:LM|CU|CR|U|CC)|SOFTWARE)\\?[^\s\x00]{2,}", re.I)
RE_MUTEX  = re.compile(r"(?:Global\\|Local\\|\\\\\.\\pipe\\)[^\s\x00]{2,}", re.I)
RE_UA     = re.compile(r"(?:User-Agent|Content-Type)\s*:\s*[^\r\n]{4,}", re.I)
RE_B64    = re.compile(r"\b[A-Za-z0-9+/]{40,}={0,2}\b")
RE_EMAIL  = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")

CATS = [
    ("url",    RE_URL),
    ("domain", RE_DOMAIN),
    ("ip",     RE_IP),
    ("email",  RE_EMAIL),
    ("path",   RE_PATH),
    ("upath",  RE_UNI),      # %APPDATA% 之类的展开路径
    ("regkey", RE_REG),
    ("mutex",  RE_MUTEX),
    ("ua",     RE_UA),
    ("b64",    RE_B64),
]

out = collections.defaultdict(set)

for s in strings(data, 4):
    for name, rx in CATS:
        if rx.search(s):
            out[name].add(s if name in ("ua", "path", "upath", "b64")
                          else (rx.search(s).group(0)))

print(json.dumps({k: sorted(v) for k, v in out.items()}, indent=2))
```

★ **必须做白名单过滤**。裸正则会捞到大量误报：
```
192.168.x.x / 10.x.x.x / 127.x.x.x / 0.0.0.0     ← 私有/保留段，一律排除
*.microsoft.com / *.windows.com / *.verisign.com  ← 公共 CA，排除
Mozilla/5.0 (Windows NT ...)                      ← 默认 UA，不算 IOC
crt.w3.org / schemas.microsoft.com                 ← XML 命名空间
vcruntime140.dll / api-ms-win-*                    ← CRT/系统 DLL 名
```

★ **实测误报样例**（对本机一个正常 x64 程序跑上面的脚本）：
```
{
  "reg": [
    "SOFTWARE_PREFETCHING_BENEFICIAL"     ← 误报：MinGW/ucrt 的环境变量名，不是注册表键
  ],
  "path": [
    "C:\\buildroot\\x86_64-1520-posix-seh-ucrt-rt_v13-rev0\\build\\gcc-15.2.0\\x86_64-w64-mingw32\\libgcc"
                                          ← 误报：编译器的构建路径，不是目标行为
  ]
}
```
两条都是编译器/运行时留下的**构建元数据**，与目标行为无关。
**过滤判据**：路径落在编译器/SDK 目录下（`mingw`、`buildroot`、`Visual Studio`）→ 排除；
注册表键不以 `HKEY_`/`HKLM\SOFTWARE\`/`HKCU\` 开头 → 排除。

### 3. ★ 交叉验证：有没有代码引用这个 IOC

**这是分级的主要依据。** 一个字符串「存在于二进制里」只能证明它被写进去了，
不能证明它被用了。

```python
# 用 r2 找引用
import subprocess

def find_xrefs(r2, binary, needle):
    """needle 必须在同一行（无空格）时有效。"""
    r = subprocess.run([r2, "-2", "-qc",
                        f"/ {needle}; q", binary],
                       capture_output=True, text=True)
    return [l for l in r.stdout.splitlines() if "0x" in l]

for host in ["evil-c2.example.com", "45.67.89.123"]:
    for x in find_xrefs(r2, r".\sample.exe", host):
        print("%-24s -> %s" % (host, x.strip()))
```

或者在 IDA/Ghidra 里对该字符串地址做 xrefs —— 更可靠，因为工具会建交叉引用数据库。

★ **有 xref → Confirmed；无 xref 但在可疑函数附近 → Probable；无 xref 且位置随机 → Possible。**

### 4. 与行为数据交叉验证

```python
import csv

STATIC = {"45.67.89.123"}                 # 静态提取的
BEHAVIOR = set()

with open(r"C:\path\cap.csv", newline="", encoding="utf-8", errors="replace") as f:
    for row in csv.DictReader(f):
        if "target" not in (row.get("Process Name") or "").lower():
            continue
        if (row.get("Operation") or "").startswith("TCP"):
            op = (row.get("Operation") or "")
            path = (row.get("Path") or "")
            if path and op:
                BEHAVIOR.add(path)

print("static  :", sorted(STATIC))
print("behavior:", sorted(BEARHAVIOR))
print("confirmed by BOTH sources: %d" % len(STATIC & BEHAVIOR))
```

★ **两个独立来源都指向同一个值 = Confirmed。** 静态有、行为无 → 可能未触发/未使用。

### 5. Procmon 数据的实操形态（接 `procmon-patterns.md`）

实测输出里，剔除 CRT 噪音后目标自己的事件长这样：

```
 1  Process Start
 1  Load Image          C:\relab2\_kbverify\target.exe
 1  Load Image          C:\Windows\System32\ntdll.dll
 1  Load Image          C1-Windows\System32\kernel32.dll
 1  CreateFile          <仓根>
 1  WriteFile           C:\relab2\_kbverify\peek.dat
 1  QueryNameInformationFile
 2  Thread Create
```

★ **`Process Profiling` 和 `Control\Nls\*` 注册表访问要排除** ——
那是 Procmon 自己的内部事件和 CRT 初始化，不是目标行为。

★ **`Load Image` 只有 4 个模块**（自己 + ntdll + kernel32 + KernelBase）是个强信号：
说明没有加密壳、没有隐藏加载。**若出现几十个 `Load Image` 指向可疑路径，
或 `Load Image` 出现在你注入之后（是你自己注入的），要分清。**

### 6. 分级与输出

```json
{
  "sample": {
    "sha256": "<样本 SHA256>",
    "arch": "x64",
    "image_base": "0x140000000"
  },
  "iocs": [
    {
      "value": "45.67.89.123",
      "type": "ip-dst",
      "confidence": "confirmed",
      "evidence": "静态 xref @ 0x140001234 + Procmon TCP Connect SUCCESS",
      "tags": ["c2", "tcp/443"]
    },
    {
      "value": "Global\\MalwareMutex_2026",
      "type": "mutex",
      "confidence": "probable",
      "evidence": "仅 strings 命中，无 xref；位于 CreateMutexW 调用点附近",
      "tags": ["mutex", "singleton"]
    },
    {
      "value": "https://cdn.example.com/a.dat",
      "type": "url",
      "confidence": "possible",
      "evidence": "二进制中存在，无引用证据",
      "tags": []
    }
  ]
}
```

★ **每条 IOC 必须带 `evidence` 字段**。没有证据字段的 IOC 无法被复核、无法被复用。

## 判据

1. ★★ **每条 IOC 有明确的证据来源和等级**。判据形态：JSON 里每条都有 `confidence` +
   `evidence` 字段，且 `evidence` 里含具体地址（`0x1400...`）或 Procmon 行。
   **没有 evidence 的条目不能进库。**
2. ★★ **有 xref 的条目标为 Confirmed**。判据形态是 r2 的 `/ <字符串>` 输出里有 `0x` 地址行，
   或 IDA/Ghidra 的 xref 列表非空。**「在 strings 里出现过」只能标 Possible。**
3. **误报被过滤**。判据形态：提取结果里**没有**私有 IP 段（`192.168.*` / `10.*` / `127.*`）、
   **没有**公共 CA 域名（`*.microsoft.com` 等）、**没有**默认 UA。
   实测形态是过滤后的列表里只剩目标真正使用的值。**若列表里有 `192.168.1.1`，说明白名单没做。**
4. **行为数据交叉验证有结果**。判据形态：`confirmed by BOTH sources: N`，N > 0 时才说明
   静态提取的东西真的被用了。**N == 0 不一定是错**（目标可能没触发网络分支），
   但要在报告里写明。
5. **`Load Image` 数量与静态分析结论一致**。判据形态：模块数少（4 个左右）+ 静态无壳
   → 一致；模块数异常多 → 要回静态分析找动态加载点。

## 坑

1. ★★★ **`strings` 里的东西不是自动的 IOC**。CRT 字符串（`vcruntime140.dll`、
   `api-ms-win-*`、`schemas.microsoft.com`、`http://www.w3.org/...`、默认 UA）占误报的大头。
   **必须做白名单过滤。**
2. ★★★ **混淆样本里 `strings` 几乎无用**。用 `floss`（栈字符串解码）而不是裸 strings。
3. ★★ **「有 xref」不等于「被执行路径引用」**。字符串在只读数据段的 `.rdata`，任何代码都可能
   引用它；xref 存在只证明「被引用过」，不证明「在主路径上」。
   **要看调用图位置** —— 是否在网络/持久化函数里。
4. ★★ **`Path` 列含逗号时用 `awk -F,` 切 CSV 会切错**。用 Python `csv.DictReader`。
   见 `procmon-patterns.md` 坑 5。
5. **裸 `strings` 的最小长度**。默认 4 太短，会捞出大量碎片。用 `floss` 或设 `-n 6`。
6. **IP 正则会捞到版本号**（`1.2.3.4` 形式的文件版本）。看上下文判断是不是地址。
7. **加密的 C2 配置不在 strings 里**。需要先解密（见 `../crypto-decode-tools.md`）。
8. **base64 blob 可能是普通资源**（图片、证书）。别把所有长 base64 都当可疑。
9. **同一个 IOC 在不同样本里值不同**（C2 域名前轮换）。不要只用一个样本的 IOC 做检测。
10. **样本 SHA256 必须记在 IOC 记录里**，否则无法回溯是哪个样本、哪个版本提取的。

## 相关

- `procmon-patterns.md` — CSV 采集端
- `persistence-startup-chain.md` — 持久化类 IOC 专项
- `yara-rule-writing.md` — 把指标变成检测规则
- `aob-signature-scan.md` — 从 IOC 字符串反查引用它的代码位置
- `vmp-devirtualization-toolchain.md` — 配置藏在 VMP 里时的解包路线
- `../crypto-decode-tools.md` — 加密配置解密后再提取