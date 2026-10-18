# 云端授权识别与 hook 替代路径

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/pe-reverse/techniques/10-license-keygen/06-cloud-license-frida-hook.md`（已适配本机工具链）
> **什么时候用**：目标激活时必发包、断网即失败 —— **D 类云端校验**。
> 此时「写个 keygen」不成立：客户端**没有可复刻的校验公式**，授权有效性由厂商服务器判定。
>
> 本地 / lab 目标按项目 `scope.md` 直接套用。
>
> ★ **本篇的 Frida 脚本未在本机实跑验证**。判据按「命令形态已验证，参数需按样本调整」处理。

## 适用信号

- 激活流程必然发包（`POST .../verify/{Order}` 类）。
- **断网激活失败或降级**（提示网络错误）—— 这是 D 类的确证。
- License Code 仅「格式面」检查，无算法校验错误提示语义。
- 离线激活证书为 RSA 签名、私钥在服务端。

## 前置

```powershell
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
$r2    = (Resolve-ReverseToolSpec -Name 'r2').Command
$cdb   = (Resolve-ReverseToolSpec -Name 'cdbX64').Command
$frida = (Resolve-ReverseToolSpec -Name 'frida').Command
$py    = (Resolve-ReverseToolSpec -Name 'pyre').Command
$pm    = '<工具根>\<分类>\<工具名>\Procmon64.exe'
$tshark = (Resolve-ReverseToolSpec -Name 'tshark').Command
```

## 步骤

### 1. ★ 建立「keygen 不可行」的证据链（三条，缺一不可）

```
1. Procmon / 抓包确认激活请求发出且响应决定状态
2. 反编译确认客户端「证书验签」只有公钥、无私钥材料
3. 修改 License Code 单字符，客户端不产生算法级错误（只有格式错误）
   → 不存在本地公式
```

**证据 1 的采集**：

```powershell
# 断网实验（判定的关键一步）
New-NetFirewallRule -DisplayName "TEMP-OFFLINE-TEST" -Direction Outbound `
    -Action Block -All -Profile Any
# → 运行激活流程
# → 失败 = D 类
Remove-NetFirewallRule -DisplayName "TEMP-OFFLINE-TEST"
```

```powershell
# 抓包确认请求形态（本机未装 Npcap，2026-10-18 复核；用 mitmdump 代理抓 HTTP，或先装 Npcap）
& $tshark -i <接口> -Y "http" -T fields -e ip.dst -e http.host -e http.request.uri
```

★ **注意一个例外**：若**公钥内嵌**且程序接受「离线激活证书」，
则 **B 类公钥替换仍可行**（转 `license-keygen-04`）——
「云校验」并非自动等于「无解」，取决于是否存在可替换的本地信任锚。

### 2. 侦察本地信任锚

```python
from pathlib import Path

state_dir = Path.home() / "AppData" / "Local" / "TargetApp" / "License"
if state_dir.exists():
    for p in sorted(state_dir.iterdir()):
        d = p.read_bytes()
        print("%-40s size=%6d head=%s" % (p.name, len(d), d[:16].hex()))
```

找三类东西：
- **授权状态文件**（缓存、证书、会话数据）
- **内嵌公钥**（`.rdata` 里的定长 blob，见 04 步骤 1）
- **授权查询函数的调用面**（每次启动/功能触发都走的地方）

### 3. 路径一：本地状态伪造

分析状态文件三要素：**格式**（明文/加密 BLOB/二进制）、
**字段**（激活标志、许可证内容、机器标识）、
**写入时机**（哪个函数在激活成功后写它）。

**构造「已激活」状态**：
- **明文 / 结构简单**：直接构造同构文件
- **加密 BLOB**：hook 编码函数，让程序自己「帮我们加密」——
  把伪造内容送入编码器，拦截其输出，落盘

```javascript
// hook 写文件 API，抓「活跃写入者」并改写内容
Interceptor.attach(Module.findExportByName("kernel32.dll", "WriteFile"), {
    onEnter(args) {
        var buf = args[1];
        var len = args[2].toInt32();
        if (len > 0 && len < 65536) {
            var head = buf.readByteArray(Math.min(len, 16));
            console.log("[write] len=" + len + " fd=" + args[0]);
        }
    }
});
```

★ 用 cdb 做同样的事更直接（不需要猜地址）：

```powershell
@'
bu ntdll!NtWriteFile
g
.echo ===WRITE_HIT===
r rcx rdx r8 r9
q
'@ | Set-Content -Path "$env:TEMP\wf.txt" -Encoding ASCII
```

### 4. ★ 路径二：授权查询面 hook（推荐）

**hook「查询函数」而非「激活函数」** —— 查询每次启动/功能触发都走，一次 hook 全覆盖；
激活只在首次调用。

```python
# 云端 hook 模板
import frida, sys

LICENSE_QUERY = "0x140045000"      # 反编译定位的查询函数

js = """
Interceptor.attach(ptr("%s"), {
    onEnter(args) {
        console.log("[lic] query arg0=" + args[0] + " arg1=" + args[1]);
        this.state = args[0];       // 可能是指向输出结构的指针
    },
    onLeave(retval) {
        retval.replace(ptr(1));     // 情况A：返回布尔 -> 置 1
        // 情况B：填充输出结构 -> 此处写"已激活"字段
        console.log("[lic] forced activated");
    }
});
""" % LICENSE_QUERY

session = frida.spawn(["target.exe"])     # ★ spawn 而非 attach
pid = session.pid
script = session.create_script(js)
script.load()
session.resume()
print("spawned pid=%d" % pid)
sys.stdin.read()
```

★ **必须用 `frida.spawn` 而不是 `frida.attach`** —— 授权状态在启动早期读取，
`attach` 会错过初始化窗口。**spawn 模式下要在 `resume()` 之前 `load()` 脚本。**

★ **可能有多进程**：部分目标在工作进程（非主进程）做授权查询 →
对所有匹配进程注入。

### 5. 路径三：试用状态重置

若目标只锁定「试用期」，重置本地试用状态可循环试用：

```powershell
# 侦察 → 备份 → 清理 → 重启
$state = "$env:APPDATA\TargetApp\state.dat"
Copy-Item $state "$state.bak"          # ① 备份（必须）
Remove-Item $state                     # ② 清理
# ③ 重启目标 → 恢复满额试用
```

若状态在注册表：
```powershell
reg query "HKCU\Software\TargetApp" /s     # ① 找出状态键
reg export "HKCU\Software\TargetApp" state.reg   # ② 备份
reg delete "HKCU\Software\TargetApp" /f        # ③ 清理
```

★ **清理前确认目标进程已退出**；多组件目标（主程序 + 插件）需要清全部状态点。
★ **备份是必须的** —— 状态文件可能是机器指纹的来源，删了无法恢复。

### 6. ★ 没有有效凭据时怎么办（先判据，别急着 hook）

> **2026-10-14 补。来源：一次真实受保护目标攻坚（换肤 6.9），用户明确「我没有卡密」。**

上面 §3–§5 的路径都默认「你能看到服务端交互」或「能触发出请求」。**没有有效凭据时，
请求根本不会发出** —— 这是最容易把人困住的地方。按下面四步走，不要跳：

| 步 | 判据（可观察） | 动作 |
|---|---|---|
| **① 判 thick / thin client** | 客户端自己做完所有处理 vs 全靠服务端 | **thick** → 本地 patch 就够（最好的情况）；**thin** → 本地 patch 到不了目的，只能 piggyback 或重实现服务端（**常常不可行**） |
| **② 判判断点在本地还是服务端** | 授权结论由本地布尔/标志/存档决定，还是服务端返回 | 本地 → 走 **§3 状态伪造 / §5 试用重置**；服务端 → 走 ③ |
| **③ 本地可改则 patch / skip** | 能否找到「调用的那行 / 切 UI 的那行 / 存档里的那个值」 | `skip`：让校验方法根本不调用，成功路径永远执行；`patch`：改存储的结果（本地 bool / PlayerPrefs / 存档 / 重放旧响应） |
| **④ 都不可行 → 判「成本不可接受」并停止** | 服务端做实质校验且客户端无可改点 | **这是一条合格的结论**，不是失败。写明：卡在哪、试过什么、为什么不可行（`assault-entry.md`：宁可写卡住，不许写完成） |

**★★★ 最容易犯的错：把「零外连」当成「纯本地校验」的证据。**

实测：错格式的凭据**在本地格式关就被拦截**（弹「请输入正确的订阅码」），
服务端分支**从未执行过**。所以：
- 抓包「零外连」**只能**证明「这次没发包」，**不能**证明「它是纯本地校验」
- 要证明本地/服务端，必须**先过本地格式关**（patch 掉格式检查，或伪造一个格式合法的凭据），
  再看有没有外连
- 判据要写成「**过格式关之后**零外连」，而不是「输入随便什么串零外连」

**无凭据时的具体切入路线（实战）**：
1. **找判断点**：搜字符串/方法名（`ValidateLicense`、`IsPremiumUnlocked`、报错文案、
   `/validate-license` URL、`premium_unlocked` 这类键名）；IL2CPP 构建还能翻 metadata
2. **本地格式关能不能单独绕过**：它往往是一个纯字符串/正则检查 → 单点 patch 就能过
3. **过了格式关再抓包**：此时才可能看到真实协议
4. **完全拿不到协议时**：改判定点（§3）比复刻协议划算得多 —— **不要在没有协议的情况下
   硬写「服务端响应复刻器」**，那是在猜

**判据（本节的出口）**：能回答「这是 thick 还是 thin」「判断点在本地还是服务端」
「我卡在格式关还是服务端」，三问都有实测证据。答不出 → 还在 §6 里，不许进 §3–§5。

## 判据

1. ★★★ **三条「不可行」证据齐全**。判据形态：一条断网失败记录 + 一条反编译确认
   （只有公钥无私钥）+ 一条「改单字符只报格式错」的实验结果。
   **缺任何一条都可能是 A/B 类误判。**
2. ★★★ **hook 后状态页显示已授权、功能解锁**。判据形态：日志出现
   `[lic] forced activated` **且** UI 标题栏试用标记消失 **且** 功能菜单可点。
   **只有日志行不够** —— hook 的返回值可能没被真正消费。
3. ★★ **状态伪造路径：重启后仍有效**。判据形态：重启两次，状态页都显示已授权。
   **只重启一次可能是巧合**。
4. ★★ **试用重置：剩余天数恢复到满额**。判据形态：重置前后各记录一次剩余天数。
   **必须有前后对照**，「看起来是新装的」不算。
5. **spawn 模式下 hook 在初始化前生效**。判据形态：脚本里没有任何
   「查询已经发生过」的日志 —— 若第一条日志就是结果而非 query，说明 attach 太晚。

## 坑

1. ★★★ **`frida.attach` 会错过启动期的授权检查**。必须用
   `frida.spawn` + `script.load()` + `session.resume()` 的顺序。
   **顺序反了（先 resume 后 load）也会漏。**
2. ★★★ **「云校验」不自动等于「无解」**。若公钥内嵌且程序接受离线激活证书，
   **B 类公钥替换仍可行**。**判 D 类之前先确认有没有本地信任锚。**
3. ★★★ **hook 的是「查询面」不是「激活面」**。查询每次启动/功能触发都走；
   激活只在首次调用 —— hook 激活函数会漏掉重启后的检查。
4. ★★ **「改单字符只报格式错误」是关键的否证实验**。若改单字符后报
   「签名无效」，那是 B 类（本地验签），不是 D 类。**文案是分类依据。**
5. ★★ **hook 返回值改了但没人消费**。若程序把结果缓存到文件，
   下次启动仍读文件 —— **必须同时处理状态的持久化**（路径一）。
6. ★ **多进程目标只注入主进程 = 无效**。授权查询可能在工作进程。
7. ★ **删状态文件前必须备份**。状态文件可能含机器指纹来源，删了不可恢复。
8. ★ **Procmon 抓不到 direct syscall 的网络调用**。如果目标用 direct syscall
   发请求，Procmon 和 API 层 hook 都看不到 —— 需要 `pcap` 层抓包。
9. **Frida 旧版本 API 不同**（`Memory.readUtf16String` → `ptr.readUtf16String`）。
   本机版本需先 `frida --version` 确认。
10. **断网实验会留下防火墙规则**。测试完务必 `Remove-NetFirewallRule`，
    否则后续所有网络测试都失败，症状极具迷惑性。

## 相关

- `license-keygen-01-mechanism-classification.md` — 上一步：确认是 D 类（断网实验）
- `license-keygen-04-signature-chain-pubkey-swap.md` — 有本地信任锚时转这里
- `license-keygen-05-keygen-verification-loop.md` — L3/L5 验收的通用形态
- `../procmon-patterns.md` — 找状态文件路径、观察网络行为
- `../direct-syscall.md` — 目标用 direct syscall 时为什么 Procmon 看不到
- `../debugger-breakpoints.md` — 不依赖 Frida 的 hook 手段