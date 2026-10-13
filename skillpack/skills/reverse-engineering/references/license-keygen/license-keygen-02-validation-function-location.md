# 许可证校验函数定位

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/pe-reverse/techniques/10-license-keygen/02-validation-function-location.md`（已适配本机工具链）
> **什么时候用**：已按 01 判为本地校验（A/B/C 类），需要找到那个「输入 key → 返回真/假」的函数。
> 找到它 = 拿到全部算法。本篇是「静态信号 → xrefs 反查 → 动态确认」三步定位法。
>
> 本地 / lab 目标按项目 `scope.md` 直接套用。

## 适用信号

- 注册码输入控件（编辑框 + 按钮）。
- `Invalid key` / `Thank you` / `注册成功` 类字符串。
- 授权相关导入调用点（字符串比较、加密库）。
- `GetDlgItemTextW` / `RegGetValueW` / `ReadFile` 之后有一个返回布尔的调用。

## 前置

```powershell
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
$r2    = (Resolve-ReverseToolSpec -Name 'r2').Command
$floss = (Resolve-ReverseToolSpec -Name 'floss').Command
$cdb   = (Resolve-ReverseToolSpec -Name 'cdbX64').Command
$frida = 'D:\EXE\python\Scripts\frida.exe'
```

## 步骤

### 第一步：静态信号收集

#### 1.1 字符串信号（最高优先级）

```powershell
& $floss .\target.exe | Select-String -Pattern `
  'license|serial|regist|invalid|thank you|expired|trial|activat'
```

出现以下字符串时，**它们的 xrefs 指向的代码就是定位起点**：

| 信号字符串 | 含义 | 攻击价值 |
|---|---|---|
| `Invalid license key` / `Invalid serial` | 失败分支弹窗文案 | **直接指向失败路径尾端，反查调用者 = 校验函数** |
| `Thank you` / `Registration successful` | 成功分支文案 | 同上，成功路径 |
| `License expired` / `trial` / `30-Day` | 期限 / 试用判定 | 指向**第二个**校验（冷启动判定）→ 见 C 类信号 |
| `name=` / `email=` / `key=` | license 文件 / 注册表键名 | 指向配置读写与校验的交界 |

★ **「License expired / trial」类字符串是 C 类（自引用）的强信号** ——
它意味着有一个独立的、启动时执行的期限判定。记下来。

**反查动作**：在 IDA / Ghidra 里对该字符串地址做 xrefs → 得到引用它的函数 →
沿调用图向上找「接收 key、返回真/假」的节点，通常只隔 0~2 层。

```powershell
# r2 里找字符串引用（形态需按样本调整）
& $r2 -2 -qc 'izz~Invalid' .\target.exe
& $r2 -2 -qc '/ Invalid license key; q' .\target.exe
```

#### 1.2 导入表信号

```powershell
& $r2 -2 -qc 'ii' .\target.exe | Select-String -Pattern `
  'GetDlgItemText|GetWindowText|lstrcmp|CompareString|memcmp|RegGetValue|RegOpenKeyEx'
```

| 导入 | 含义 |
|---|---|
| `GetDlgItemTextW/A`、`GetWindowTextW/A` | 注册窗口读取输入 → **断点设这里最快** |
| `lstrcmpW`、`CompareStringW`、`memcmp` | 逐字节比较点（常量表比对常见） |
| `bcrypt.dll`、`advapi32` Crypt\*、OpenSSL | B 类签名链迹象 |
| `RegGetValueW`、`RegOpenKeyExW` | 授权读注册表 |

★ **优先断 `GetDlgItemTextW`**：它命中时栈回溯能直接看到按钮回调，
再往下一层就是校验函数。这比纯静态快一个数量级。

### 第二步：动态确认（最快路径，推荐先做）

#### 2.1 输入 API 断点 + 栈回溯

```powershell
$cmds = "$env:TEMP\lic.txt"
@'
bu ntdll!NtQuerySystemInformation
g
.echo ===READY===
q
'@ | Set-Content -Path $cmds -Encoding ASCII
```

★ **cdb 上不要写 `bp user32.GetDlgItemTextW`** —— 实测 `kernel32!X` 形态因
forwarder 断不上（见 `../debugger-breakpoints.md` 判据 1）。
**GUI 目标最实用的替代是 x64dbg**：本机 x64dbg 在位，MCP 通道
`x64dbg-automate-mcp` 已握手，用 `set_breakpoint` 传 `user32.GetDlgItemTextW`，
命中后用 `read_memory` 看输出缓冲区 + 栈回溯。

**x64dbg 命令行的等价写法**（GUI 操作）：
```
Ctrl+G user32.GetDlgItemTextW     → 跳到导出
F2                                 → 下断
运行到用户点「激活」按钮
命中后：Stack 窗口看调用者；r rcx/r8 看 hWnd 和缓冲区地址
```

#### 2.2 Frida 栈回溯（无 GUI 调试器时）

```javascript
// hook 输入 API，打印栈回溯
Interceptor.attach(Module.findExportByName("user32.dll", "GetDlgItemTextW"), {
    onEnter(args) {
        var buf = args[2];
        var s = buf.readUtf16String(args[3].toInt32());
        if (s && s.length > 4) {
            console.log("[input] " + s);
            console.log(Thread.backtrace(this.context, Backtracer.ACCURATE)
                .map(DebugSymbol.fromAddress).join("\n"));
        }
    }
});
```

回溯里的模块内地址就是按钮回调链，顺着反查即得校验函数。

★ **Frida 脚本在本机未实跑验证**（`frida.exe` 与 Python `frida` 包都在位，
但本轮未 attach 实机目标）。判据按「命令形态已验证，参数需按样本调整」处理。

#### 2.3 探针分化（确认校验语义）

对候选函数下断，用**正确 key 和错误 key 各跑一次**，对比参数与返回值：

```
正确 key:   f(key_ok)   → 返回 1
错误 key:   f(key_bad)  → 返回 0
其余参数相同
```

★ **若两次调用的参数完全一致、仅返回值不同**，说明**没有隐藏状态依赖**。
若有 RNG / 时间 / 线程局部队列，调用结果会不可复现 —— 见
`license-keygen-03-key-algorithm-recovery.md` 的「非确定性校验陷阱」。

### 校验函数的三个形态特征（确认没找错）

1. **入参是「内容」而非「控件」**：参数是 key 字符串/长度，不是 `HWND`
   → 说明已脱离 UI 层，是纯逻辑校验。**还原它 = 还原算法。**
2. **单点返回零一**：函数体末尾 `test eax,eax / jz` 、`setne al; ret`
   → 布尔校验语义。
3. **内部有常量表 / 魔数**：CRC 表、XOR 常量、字符集串
   （`0123456789ABCDEFGHJKMNPQRSTUVWXYZ`）、大整数（公钥）。

### ★ 双机制信号（发现两个校验函数 → C 类）

**定位过程中最重要的一个岔路口**：

```
输入窗口校验（点「激活」时跑，弹 "Thank you"）
        vs
冷启动校验（程序启动时跑，决定真实授权状态）
```

**这是两个独立函数** → 机制是 C 类（自引用），
直接转 `license-keygen-07-self-ref-convergence.md`，**不要先去做算法还原**。

判别方法：搜 `License expired` / `trial` / `startup` 附近的代码，
看有没有一个不依赖任何输入、直接读配置文件/注册表判定的函数。

## 判据

1. ★★★ **找到的函数通过了「探针分化」实验**。判据形态：正确 key 返回 1、
   错误 key 返回 0、其余参数相同。**「这个函数看起来像」不是判据。**
2. ★★ **函数符合三个形态特征**。至少满足前两条（入参是内容、返回布尔）。
   **若入参是 HWND，你找到的是 UI 回调不是校验函数** —— 再往里找一层。
3. ★★ **用官方公开 key（若可得）做了基线**：`f(官方key) = TRUE` 必须成立。
   这是后续算法还原正确性的**校准基准**，没有它就无法判断还原是否正确。
4. **记录了函数的地址与形态特征**。判据形态：RVA + 函数前 16 字节的特征码。
   有了特征码，样本升级后能重新定位（见 `../aob-signature-scan.md`）。
5. ★ **确认了有几个校验函数**。判据形态：明确回答「1 个」还是「2 个」。
   **发现 2 个 → C 类**，改变整条路线。

## 坑

1. ★★★ **cdb 上 `kernel32!X` / `user32!X` 断不上**（PDB 里只有 `*Stub` 别名，不是 forwarder）。
   实测 `bu kernel32!GetTickCount64` → `Couldn't resolve error at ...`。
   **x64dbg 的 `user32.X` 语法可以**（它有自己的符号解析），但 cdb 不行。
   两个工具的符号规则不一样，别混用。
2. ★★★ **UI 回调 ≠ 校验函数**。`GetDlgItemTextW` 的调用者是按钮回调，
   按钮回调里可能还调了格式检查、长度检查、日志写入。**校验函数通常在再往下一层。**
   判据是形态特征 1（入参是内容不是 HWND）。
3. ★★ **「License expired」类字符串意味着冷启动判定**。看到它就说明有第二套机制，
   别急着做算法还原 —— 先按 07 试收敛（20 分钟能出结果），不行再回来。
4. ★★ **校验可能有隐藏状态**（时间、RNG、会话标志）。
   **判据：同一 key 连续调用两次结果是否一致。** 不一致 = 有非确定性输入，
   还原算法前要先锁定污染源。
5. ★ **x64dbg 断在 `user32.X` 但界面显示「已绑定」不代表会命中**。
   判据要看实际停下来没有。
6. **Frida 的 `Memory.readUtf16String` 在旧版本 Frida 上已被
   `readUtf16String` 指针方法取代**。本机 frida 版本需确认后再用。
7. **`floss` 的 decode 通道在 GUI 程序上会产出大量与许可证无关的栈字符串**。
   先 `--only static` 筛出候选，再对候选做 decode。
8. **样本有多个校验函数时**（比如同时校验订阅和单买），要分清哪个是当前激活路径。
   用断点的调用栈判断。

## 相关

- `license-keygen-01-mechanism-classification.md` — 上一步：分类
- `license-keygen-03-key-algorithm-recovery.md` — 下一步：A 类还原算法
- `license-keygen-07-self-ref-convergence.md` — 发现双机制时转这里
- `../debugger-breakpoints.md` — cdb 断点的正确形态与判据
- `../../tools-dynamic.md` — x64dbg / Frida 通用用法与 MCP 通道
- `../aob-signature-scan.md` — 把找到的函数做成特征码以便复用