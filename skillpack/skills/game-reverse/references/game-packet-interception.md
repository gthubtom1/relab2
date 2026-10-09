# 封包观测：协议结构还原、TLS 边界与作弊特征检测

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/general/techniques/cheating/02-packet-interception.md`（已适配本机工具链，视角改为防守）
> **什么时候用**：你在分析一个受保护的游戏客户端的网络层；抓包只能看到长度看不到内容；
> 需要判断流量是否加密、加密在哪一层；需要还原协议结构（魔数/操作码/长度/序列号/校验）；
> 要写规则检测「客户端发包间隔异常」「重放包」这类作弊特征。

> **授权边界**：抓包与协议还原用于**自有客户端、授权测试环境、CTF，或网络层防御研究**。
> 对第三方商业游戏做流量注入、重放、MITM 需要产品厂商书面授权。
> 下面所有重放/修改代码块**只在你自己的测试服务端上跑**。

## 视角说明

这一篇的重点不是「怎么改包」，而是「**从网络层能观测到什么、怎么把观测变成检测规则**」。
核心洞察：

> **网络层是反作弊唯一真正可信的观测面。** 客户端内存、渲染、hook 全部可被篡改；
> 但包在网络上留下的痕迹（时序、大小、序列、重复）改不掉 —— 除非你连时序一起伪造。
> 所以「防封包作弊」的主力永远是**服务端权威 + 序列/时序一致性校验**，客户端 hook 只是延缓。

## 适用信号

- 客户端与服务器通信，抓包能看到 `tcp.len` 但 `tcp.payload` 为空/乱码 → 已加密。
- 服务端因为「序列跳变」「时间戳异常」踢人 → 存在序列/时序校验。
- 客户端进程里有 `ws2_32.dll` / `winhttp.dll` / `wininet.dll` 导入，或自研 TLS 库。
- 目标用了证书固定（cert pinning）或内嵌 CA 根证书。
- 需要判断某个 UDP 报文是不是心跳、哪个字节是操作码。
- 想统计「某个操作码的调用频率」用于行为检测。

## 前置

```powershell
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
$tshark = (Resolve-ReverseToolSpec -Name 'wireshark').Command   # D:\Tools\Wireshark\tshark.exe
$r2     = (Resolve-ReverseToolSpec -Name 'r2').Command
$cdb    = (Resolve-ReverseToolSpec -Name 'cdbX64').Command
$capa   = (Resolve-ReverseToolSpec -Name 'capa').Command
$mitm   = (Resolve-ReverseToolSpec -Name 'mitmdump').Command
$py     = 'D:\EXE\python\python.exe'    # scapy 2.8.0 / dpkt / cryptography 均已装
```

本机实测基线：

```
TShark (Wireshark) 4.6.8 (v4.6.8-0-ge677bf052328).
scapy 2.8.0  /  dpkt ok  /  cryptography ok
```

## 步骤

### 1. 抓包：确认「你到底看到了什么」

```powershell
& $tshark -i <iface> -f 'tcp port <PORT>' -a duration:60 -w .\cap.pcap
```

★ **本机坑**：`tshark -D` 列出的是中文网卡名（`本地连接* 10`、`WLAN`、`以太网`…），
而且**多条 `-i` 会启动 extcap 并报 `ciscodump ... Missing parameter: --remote-host`**。
单接口抓包在本机可用（实测 rc=0，pcap 468 字节），但 `0 packets captured` 时先怀疑过滤式或接口选错。

读包：

```powershell
& $tshark -r .\cap.pcap -T fields -e frame.number -e tcp.srcport -e tcp.dstport -e tcp.len -e tcp.payload
```

实测（scapy 造的 `synth.pcap`）：

```
1	51000	17779	4	 	70696e67
2	17779	51000	80	deadbeef01020010aaaa...aaaa	deadbeef01020010aaaa...aaaa
```

★ **两个字段名坑**：
- `data.data` 在 TCP 段上**是空的**；要用 `tcp.payload` 或 `tcp.segment_data`。
- `-e tcp.payload` 会把十六进制**重复输出两遍**（ASCII + raw 两列），解析时取前半段。

**判读**：`tcp.len` 有值但 `tcp.payload` 空 = 你只看到长度（被加密或被过滤）；有值 = 拿到了应用层字节。

### 2. 判断是否加密：熵 + 结构重复性

```python
import math
def H(d):
    if not d: return 0.0
    f = [0]*256
    for b in d: f[b] += 1
    return -sum((c/len(d))*math.log2(c/len(d)) for c in f if c)

body = bytes.fromhex('deadbeef') + b'\x01\x02\x00\x10' + bytes([0xaa])*72
print('H(payload)=', round(H(body), 3))
print('H(magic)=', round(H(body[:4]), 3))
```

实测输出：

```
H(payload)= 0.769 H(magic)= 2.0
```

★ **重要修正**：上游给的经验区间（明文 4.0–5.5 / 压缩 7.0–8.0 / 加密 7.5–8.0）
**只在数据量足够大时才成立**。上面这个 80 字节包（大量重复 `0xAA`）熵只有 0.769 ——
**小样本 + 强重复 = 低熵，即使语义上「像加密」**。
所以熵值判据必须配一个最小样本量（建议 > 512 字节），否则直接用「结构重复性」判据：

| 观察 | 结论 |
|------|------|
| 同一偏移在连续包里字节完全不变 | 固定头（版本/魔数） |
| 偏移 X 在连续包里 +1 或 +N | 序列号 |
| 载荷每次都不同但长度总在 {小集合} | 枚举型操作码/信令 |
| 长串无任何重复、无可读 ASCII | 大概率加密或压缩 |

### 3. 定位协议头字段（长度/序列号/魔数）

```python
import struct
from collections import Counter

def analyze_packets(pkts):
    for off in range(0, 8):                       # 尝试每个偏移当 u16 魔数
        vals = {struct.unpack_from('<H', p, off)[0] for p in pkts if len(p) > off+1}
        if len(vals) == 1:
            print(f"constant u16 @ {off}: 0x{vals.pop():04x}")
    for off in range(2, 16):                      # 尝试每个偏移当长度字段
        for p in pkts:
            if off + 2 <= len(p):
                v = struct.unpack_from('<H', p, off)[0]
                if v == len(p):
                    print(f"length field @ {off} = {v}")
                    break
    # 序列号：统计每个偏移上「相邻包差值」的众数
    for off in range(2, 16):
        diffs = [struct.unpack_from('<I', pkts[i], off)[0] - struct.unpack_from('<I', pkts[i-1], off)[0]
                 for i in range(1, len(pkts))
                 if off + 4 <= len(pkts[i]) and off + 4 <= len(pkts[i-1])]
        c = Counter(diffs)
        if c and c.most_common(1)[0][1] >= len(diffs) * 0.8:
            print(f"seq field @ {off}, modal delta = {c.most_common(1)[0][0]}")
```

**判读**：一个偏移在 ≥80% 的相邻包差值相同且恒定 → 这是序列号或计数器（**作弊检测的核心锚点**）。

### 4. 找客户端的网络 API（哪些原语可被 hook / 哪些痕迹可被检测）

```powershell
& $r2 -2 -qc 'ii; q' .\GameClient.exe | Select-String 'WS2_32|winhttp|wininet|ssl|curl'
```

实测（`kbgame_probe.exe`）：

```
1   0x1400084d0 NONE FUNC WS2_32.dll                            socket
2   0x1400084d8 NONE FUNC WS2_32.dll                            send
3   0x1400084e0 NONE FUNC WS2_32.dll                            recv
```

capa 侧（实测命中）：

```
│ COMMUNICATION         │ Socket Communication::Receive Data [C0001.006]      │
│                       │ Socket Communication::Send Data [C0001.007]         │
```

★ **导入名大小写敏感**：实测 DLL 名是 `WS2_32.dll`（大写），过滤写 `ws2_32` 一个都匹配不到。

用 cdb 确认 `send`/`recv` 的真实调用点与参数（自研 wrapper 之外的一手证据）：

```powershell
@'
bu WS2_32!send
bu WS2_32!recv
g
.echo ===SEND===
r rcx
r rdx
r r8
kv 6
g
.echo ===RECV===
r rcx
r rdx
kv 6
q
'@ | Set-Content -Path "$env:TEMP\net.txt" -Encoding ASCII

& $cdb -cf "$env:TEMP\net.txt" 'C:\relab2\work\kbgame_probe.exe'
```

x64 参数：`send(SOCKET s /*rcx*/, const char* buf /*rdx*/, int len /*r8d*/, int flags /*r9d*/)`。
命中时 `kv` 会回溯到调用者模块 —— 这就是「这个程序真的在用 Winsock」的一手证据。

实测输出（`kbgame_probe.exe`，节选）：

```
0:000> bu WS2_32!send
0:000> bu WS2_32!recv
0:000> bl
 0 e 00007ffb`63d22320     0001 (0001)  0:**** WS2_32!send
 1 e 00007ffb`63d31d90     0001 (0001)  0:**** WS2_32!recv
0:000> g
Breakpoint 0 hit
WS2_32!send:
00007ffb`63d22320 48895c2408      mov     qword ptr [rsp+8],rbx
0:000> r rcx
rcx=ffffffffffffffff
0:000> r rdx
rdx=00007ff74a94400a
0:000> r r8
r8=0000000000000002
0:000> kv 4
... WS2_32!send
... kbgame_probe+0x14ab
... kbgame_probe+0x10c7
```

`r8=2` 正是这个样本传给 `send` 的报文长度（源码里 `const char* msg = "hp"; send(s, msg, 2, 0);`）——
**寄存器值与源码语义一致**，参数解析才算坐实。`rcx=0xFFFFFFFFFFFFFFFF` 是 `INVALID_SOCKET`
（这个样本没先 `connect()`），但 `kv` 依然回溯到调用者模块，**证据照样成立**：
断在 API 入口，不需要调用成功。

### 5. TLS 边界：证书固定怎么被检测

现代客户端**不用**系统信任库做校验时会自己校验 —— 这本身就是**可检测特征**：

| 现象 | 说明 |
|------|------|
| 客户端进程内有独立证书校验逻辑，且不看系统证书库 | 内嵌 CA / pinning |
| 抓到的是 TLS 会话，抓不到应用层明文 | 至少 TLS 层加密 |
| TLS 握手后流量长度分布很窄（固定大小分组） | 可能是分组加密（record 填充） |
| 同一会话反复失败握手 | 客户端拒绝了系统 CA（pinning 的副作用） |

用 `r2` 在客户端里找校验函数（防守视角：这类函数是**行为检测的锚点**）：

```powershell
& $r2 -2 -qc 'ii~CertVerifyCertificateChainPolicy,CertGetCertificateChain,WinVerifyTrust,SSL_CTX_set_verify; q' .\GameClient.exe
```

命中 `CertGetCertificateChain` / `WinVerifyTrust` / `CertVerifyCertificateChainPolicy` =
客户端自己做证书校验，而不是靠 Schannel 默认路径 —— **pinning 的判定线索**。
（`gRPC`/`mbedtls` 静态链接的客户端则要找 `mbedtls_ssl_conf_verify` 之类符号，
或 `ssl_parse_certificate` 附近的字符串。）

### 6. 防守侧：把网络面观测写成检测规则

**服务端检测向量**（这是反作弊真正在做的事，也是你研究时应复现的清单）：

| 向量 | 观测量 | 规则形态 |
|------|--------|----------|
| 序列连续性 | 相邻包序列差值分布 | 出现跳跃/回退 → 丢包/重放 |
| 时间戳一致性 | 客户端时间戳 vs 服务器接收时间 | 偏差超阈值 → 时间操控 |
| 时序分布 | 相邻包间隔的均值/方差 | 方差异常低（机器重放）或异常高（缓冲） |
| 操作码频率 | 单位时间内某操作码计数 | 频率超出人类可能范围 → 自动瞄准/连发 |
| 大小一致性 | 同一操作码的包长分布 | 长度分布突变 → 协议版本不一致 |
| 重复包 | 完全相同的载荷重复出现 | 重放检测（需要 nonce） |
| 一致性 | 客户端声称的位置 vs 服务端物理模拟 | 位置跳变超速度上限 → 改包 |

写成可执行的检测器（自建 pcap 上跑）：

```python
import struct, statistics
def seq_gaps(pkgts, off):
    seqs = [struct.unpack_from('<I', p, off)[0] for p in pkgts if off+4 <= len(p)]
    return [b-a for a, b in zip(seqs, seqs[1:])]
def interarrival(ts):
    return [b-a for a, b in zip(ts, ts[1:])]

# 规则：间隔标准差 < 1ms 且均值 < 5ms → 机器重放（非人类输入）
ia = interarrival(ts_list)
if ia and statistics.pstdev(ia) < 1.0 and statistics.mean(ia) < 5.0:
    alert("machine-paced traffic")
# 规则：序列差值出现非 +1 的跳变 → 丢包/插入
gaps = seq_gaps(pkgts, 4)
if any(g != 1 for g in gaps):
    alert(f"seq discontinuity: {sorted(set(gaps))}")
```

### 7. 自建服务端上的重放（**仅限自有/授权环境**）

```python
from scapy.all import rdpcap, sendp, Raw
pkts = rdpcap("cap.pcap")
raw = bytes(pkts[7][Raw])
# 只在你自己的服务端上重放；改 seq/checksum 后服务端应拒绝
sendp(pkts[7], iface="lo", verbose=False)
```

★ 判据是**服务端是否接受**。真实反作弊服务端会做序列 + nonce + 时序三重校验，
所以「本地重放能发出去」不等于「能骗过服务端」。

## 判据

1. **协议已还原**：至少识别出 **3 个**字段并各有两个独立证据。
   证据 A = 静态结构（跨包不变/规律变化）；证据 B = 动态（客户端代码里对该字段的使用，
   cdb 命中 `WS2_32!send` 且 `kv` 能回溯到具体函数）。只有证据 A 的字段**标记为「推测」**。
2. **加密边界已定位**：要么抓到了应用层明文（`tcp.payload` 非空且有可读结构），
   要么确认了加密起点（TLS 握手之后 / 某个固定偏移之后全部高熵且无重复）。
   判据输出形式：`tshark -T fields -e tcp.payload` 在加密点之前**有值**、之后**全空或高熵**。
3. **序列/时序锚点已确认**：某偏移在 ≥80% 相邻包上差值恒定（统计输出 `modal delta`），
   且时间戳字段的偏差分布能区分「人」与「机器重放」（标准差量级差异）。
4. **capa 分类命中**：`Socket Communication::Send Data [C0001.007]` /
   `Receive Data [C0001.006]` 同时出现（本机实测命中）。
5. **客户端真在发包**：cdb 日志出现 `Breakpoint 0 hit` 于 `WS2_32!send`，
   且 `kv` 里有客户端自身模块帧。

## 坑

1. ★ **`data.data` 在 TCP 段上是空的**，用 `tcp.payload` 或 `tcp.segment_data`。
   而且 `-e tcp.payload` 会输出**两遍**（ASCII + raw），解析时取前半段。
2. ★ **上游的熵值区间在小样本上完全失效**。实测 80 字节强重复包熵只有 0.769。
   熵判据必须 >512 字节样本，or 改用「结构重复性」判据。
3. ★★ **`/x` 返回空先查字节序，别当成「r2 坏了」**（2026-10-10 本机实测复核）：
   同一份含目标字节的样本上 `/x 7ffe0320`、`/x 6a006801`、AES S-box 前缀
   **全部正常命中**。唯一返回空的是 `/x 2003fe7f` —— 文件里是 `7f fe 03 20`，
   而 `2003fe7f` 是**字节序写反**。通配符实测：`7ffe03..` 命中、`7ffe03??` 空。
   另：`-qc '/x ...; q'` 里的 `;` 会截断命令，参数串只放一条。
   **`/x` 是可用的 AOB 检索工具，不必绕开它。**
4. **`tshark -D` 网卡名是中文**，多条 `-i` 会触发 extcap 报错
   （`ciscodump ... Missing parameter: --remote-host`）并导致 0 包。
5. **导入名大小写敏感**：`WS2_32.dll` / `WINMM.dll` / `KERNEL32.dll`。
6. **cdb 断点必须下在 `g` 之前**；`bu kernel32!X` 会 `Couldn't resolve error`
   （PDB 里只有 `*Stub` 别名，不是 forwarder），
   `bl` 显示绑定成功**不等于**会命中 —— 判据只看 `Breakpoint 0 hit`。
7. **cdb 命令文件每行一条、扁平，结尾必须有 `q`**；`r rcx rdx r8` 写成一行报 `Syntax error`。
8. **重放实验不要在公网/他人服务端做**。所有重放/修改代码只对你自己的测试端跑。
9. **TLS 会话抓不到不等于应用层没加密** —— 可能还有应用层加密叠在 TLS 之上。
   两层都要分别确认边界。
10. **「包长固定」不能证明是加密**。固定长度的信令包（心跳/保活）本来就是这样。
    要看载荷内容是否可读/高熵。
11. **`pefile` 的 `i.struct_iat.get_file_offset()` 抛 `AttributeError`**，
    用 `pe.get_offset_from_rva(imp.address - ImageBase)`。
12. **抓包时游戏可能用 QUIC/UDP 而不是 TCP**。tshark 里 `-f 'udp port N'`，字段用 `udp.payload`。

## 相关

- `game-memory-hacking.md` — 客户端侧的篡改面（与本文的「网络侧是唯一可信面」互为对照）
- `game-anti-cheat-bypass.md` — 反作弊在网络/行为层用什么观测
- `game-speedhack-time-manipulation.md` — 时间戳一致性校验的攻与防
- `../../reverse-engineering/references/pe-header-parsing.md` — 追客户端网络 API 的基础
- `../../reverse-engineering/references/dynamic-api-resolution.md` — 若客户端运行时解析 socket API
- `../../reverse-engineering/references/aob-signature-scan.md` — 把协议结构常量做成特征码