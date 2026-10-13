# keygen 实机验证闭环

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/pe-reverse/techniques/10-license-keygen/05-keygen-frida-verification-loop.md`（已适配本机工具链）
> **什么时候用**：keygen 写好了，`--verify` 自洽断言也过了。
> 但那只证明「算法复现正确」。**攻击成立的硬标准是：目标程序真实运行时接受生成的 key。**
>
> 本地 / lab 目标按项目 `scope.md` 直接套用。
>
> ★ **本篇的 Frida 脚本未在本机实跑验证**（`frida.exe` 与 Python `frida` 包在位，
> 但本轮未 attach 实机目标）。判据按「命令形态已验证，参数需按样本调整」处理。
> 需要**不依赖 Frida** 的验收路径时用步骤 4 的配置写入法。

## 适用信号

- keygen 已完成并通过自洽断言。
- 有官方 key 作为基线。
- 需要确认「目标真的接受生成的 key」，而不只是「公式对得上」。

## 前置

```powershell
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
$cdb   = (Resolve-ReverseToolSpec -Name 'cdbX64').Command
$r2    = (Resolve-ReverseToolSpec -Name 'r2').Command
$frida = (Resolve-ReverseToolSpec -Name 'frida').Command
$py    = (Resolve-ReverseToolSpec -Name 'pyre').Command
```

## 步骤

### 1. 五级验证（由弱到强）

| 层级 | 手段 | 说明 |
|---|---|---|
| L1 | keygen 自校验断言 | 算法自洽，**弱证据** |
| L2 | 官方 key 批量回归 | 还原正确性，**强证据** |
| L3 | **进程内替换** | 真实上下文校验通过，**核心验收** |
| L4 | 内存标志位监听 | 注册状态生效（非仅函数返回） |
| L5 | **重启保持** | 冷启动后仍为已注册 |

★ **停在 L1/L2 不算完成。** A 类机制尤其危险：
输入窗口校验（能过）+ 冷启动校验（真实判定）是两套独立机制，
只做 L3 会得出「已经成功」的错觉。

### 2. L3：进程内替换（核心验收）

**原理**：`Interceptor.replace` 校验函数会丢失原逻辑。
标准做法是**拦截输入 API，把官方 key 文本替换为自生成 key**，
让原校验函数在真实上下文处理我们的 key：

```python
# verify_swap.py
import frida, sys

TARGET    = "target.exe"
OFFICIAL  = "XXXXX-XXXXX-XXXXX-XXXXX"     # 官方基线 key
GENERATED = "YYYYY-YYYYY-YYYYY-YYYYY"     # keygen 输出

hook = """
Interceptor.attach(Module.findExportByName("user32.dll", "GetDlgItemTextW"), {
    onEnter(args) {
        var buf = args[2];
        var s = buf.readUtf16String(args[3].toInt32());
        if (s && s.indexOf("-") > 0) {
            args[2].writeUtf16String(GENERATED);
            console.log("[swap] official->generated");
        }
    }
});

Interceptor.attach(ptr(CHECK_ADDR), {
    onEnter(a)   { console.log("[check] enter key=" + a[0].readUtf8String()); },
    onLeave(r)   { console.log("[check] ret=" + r.toInt32()); }
});
"""

js = """
var GENERATED = "%s";
""" % GENERATED + hook

session = frida.attach(TARGET)
script = session.create_script(js)
script.load()
print("attached; now trigger activation in the UI...")
sys.stdin.read()
```

判定：日志出现 **`[check] ret=1`**，且**必须出现在未手动改动官方 key 的情况下**
（是脚本替换的）。

★ 若程序在启动时直接校验配置文件（无 UI），改为 hook `ReadFile` / `RegGetValueW`
替换读到的内容，思路一致。

### 3. L4：内存标志位监听

校验函数往往把结果写入**全局注册标志位**（如 `DAT_1422E9936`，0 = 已注册）。
监听它比监听函数返回值更接近真实判定：

```javascript
// ★ Frida 不支持数据断点，用轮询而非 Interceptor
var flag = ptr("0x1422E9936");
var timer = setInterval(function () {
    try {
        var v = flag.readU8();
        if (v === 0) { console.log("[flag] REGISTERED (0)"); clearInterval(timer); }
    } catch (e) {}
}, 200);
```

★ **标志位地址来源**：02 定位时记录校验函数写入的全局；或用 IDA/Ghidra
对校验结果的引用反查。**不要凭猜** —— 猜错地址会读到无关内存，得出「已注册」的错觉。

★ **用 cdb 的硬件断点做同样的事更可靠**（不需要猜轮询时机）：

```powershell
$cmds = "$env:TEMP\flag.txt"
@'
bu ntdll!NtQuerySystemInformation
g
ba 1 eip 0x00007ff6f44b1520
g
.echo ===FLAG_HIT===
q
'@ | Set-Content -Path $cmds -Encoding ASCII
```

### 4. ★ 配置写入激活（不依赖 Frida 的验收路径）

当校验在启动时读配置文件（如 `Preferences.json` 的三键
`Name` / `Email` / `Key`），且手工粘贴激活码会触发联网二次校验时，
**直接写配置是正确路径**：

```python
import json, shutil
from pathlib import Path

cfg = Path.home() / "AppData" / "Roaming" / "TargetApp" / "UserProfile" / "Settings" / "Preferences.json"

# ① 备份
shutil.copy2(cfg, cfg.with_suffix(".json.bak"))

# ② 读 → 改 → 写
data = json.loads(cfg.read_text(encoding="utf-8"))
data.setdefault("Settings", {})["ProLicense"] = {
    "Name":    "Pro User",
    "Email":   "user1234@example.com",
    "Key":     GENERATED_KEY,
}
cfg.write_text(json.dumps(data, indent=2), encoding="utf-8")

# ③ ★ 复读校验：三键一致
chk = json.loads(cfg.read_text(encoding="utf-8"))
assert chk["Settings"]["ProLicense"]["Key"] == GENERATED_KEY
print("OK - config written and read back")
```

★ **写入前先结束目标进程** —— 否则退出时内存数据会覆盖配置。
★ **写完必须复读** —— 只看 `write_text` 没抛异常是不够的，
目标可能用别的编码/格式再读回来。

### 5. 硬件指纹绑定处理

若 key 与机器绑定（派生自注册表 `MachineGuid` / 磁盘序列号）：

```python
# keygen 增加 --guid 参数：算法还原时把指纹当显式输入，不当常数
ap.add_argument("--guid", metavar="GUID")
# 生成时按还原算法对指定指纹计算
```

验证绑定关系被正确复现的方法：
```
换一台机器 / 改 MachineGuid 后，同一 key 必须 FAIL
```
★ **这条是「绑定真的被复现了」的硬证据**，也是「key 其实不绑定机器」的否证。

### 6. L5：重启保持

**这是唯一能暴露 A+C 双机制的判据。** 操作：
```
1. 结束目标进程
2. 写入生成的 key（配置写入法或 GUI 粘贴）
3. 重新启动目标
4. 观察：试用标记消失？功能菜单解锁？状态页显示已授权？
```

★ **重启两次以上** —— 有些实现第一次启动写入状态、第二次启动才生效，
单次「看起来通过」不能排除侥幸。

## 判据

1. ★★★ **L3 通过：日志出现 `[check] ret=1` 且是在替换生效的情况下**。
   判据形态：同一份日志里同时有 `[swap] official->generated` 和 `[check] ret=1`。
   **两个标记都要有，且顺序正确（swap 在前）。**
   ★ 本篇 Frida 脚本未在本机实跑验证 —— 判据形态已确认，参数需按样本调整。
2. ★★★ **L5 通过：重启后仍为已注册**。判据形态：重启两次，每次都显示已授权。
   **这是唯一能暴露双机制的判据** —— 只做 L3 会得出「已经成功」的错觉。
3. ★★ **L4 的标志位值与函数返回值一致且自洽**。
   判据形态：`[flag] REGISTERED (0)` 出现在 `[check] ret=1` 之后。
   ★ **地址不能猜** —— 猜错会读到无关内存得出假阳性。
4. ★★ **配置写入路径有「备份 → 写 → 复读」的完整证据**。判据形态：
   ```
   OK - config written and read back
   ```
   且备份文件存在。**只看不抛异常不够。**
5. **L2 官方 key 回归 VALID**。判据形态：`keygen.py --verify "<官方key>"` 输出 `VALID`。
   **L2 不成立就没有资格谈 L3。**

## 坑

1. ★★★ **停在 L1/L2 不算完成**。自洽断言和官方 key 回归都只证明
   「算法复现正确」，不证明「目标接受」。**必须做 L3（进程内替换）**
   和 **L5（重启保持）**。
2. ★★★ **只做 L3 不做 L5 会漏掉双机制**。A 类目标常有
   「输入窗口校验 + 冷启动校验」两套独立机制。只做 L3 会得出「已经成功」的错觉。
3. ★★★ **写配置前必须结束目标进程**。目标退出时会用内存数据覆盖配置，
   你的写入被静默丢弃 —— 症状是「写进去了但重启后没用」。
4. ★★ **Frida 旧版本 API 不同**。`Memory.readUtf16String(ptr)` 已改为
   `ptr.readUtf16String(n)`。**本机 Frida 版本需先确认**（`frida --version`）。
5. ★★ **Frida 不支持数据断点**。标志位监听必须用**轮询**，
   写 `Interceptor.attach` 到数据地址会失败或无效果。
6. ★ **标志位地址不能猜**。猜错会读到无关内存，得出「已注册」的假阳性。
   用 IDA/Ghidra 反查校验结果的引用，不要凭感觉。
7. ★ **「写配置没抛异常」≠ 配置生效**。目标可能用别的编码读回，
   或有配置文件完整性校验。**必须复读 + 重启验证。**
8. ★ **硬件绑定场景下，同一 key 在本机通过不代表绑定被复现**。
   换机器/改 GUID 后必须 FAIL。**这条是绑定关系的否证。
   （原稿此处漏了句号，修正。）**
9. **Frida attach 到已调试的进程会失败**。先关掉调试器再 attach。
10. **写配置路径需要知道目标的用户配置目录**。
    从 `Procmon` 抓（见 `../procmon-patterns.md`）比猜可靠得多。

## 相关

- `license-keygen-03-key-algorithm-recovery.md` — 上一步：还原算法
- `license-keygen-04-signature-chain-pubkey-swap.md` — B 类路线做完也来这里验收
- `license-keygen-06-cloud-license-hook.md` — D 类路线的验收形态
- `license-keygen-07-self-ref-convergence.md` — C 类路线做完也来这里验收
- `../procmon-patterns.md` — 找配置文件的真实路径
- `../debugger-breakpoints.md` — 不依赖 Frida 的验收手段