# Android 反调试检测与绕过（VMP 场景）

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/apk-reverse/techniques/07-packer/05-vmp-anti-debug-bypass.md`
> **什么时候用**：对加固应用做动态分析（trace 解释器、dump 内存）时，Frida/调试器一挂上就闪退或卡死。

## 适用信号

- Frida attach/spawn 后进程立即退出，或界面卡死
- 启动时有第二个进程（守护进程）互相 ptrace
- logcat 出现 `tracerpid` / `frida` / `detected` 字样
- 无 hook 时正常，一旦 `/proc/self/maps` 出现 frida 相关映射就退出
- 反汇编看到大量 `open("/proc/self/status")`、`ptrace`、`clock_gettime` 调用

## 检测手段与绕过对照

| 检测手段 | 原理 | 绕过 |
|---|---|---|
| TracerPid | 读 `/proc/self/status` 的 `TracerPid:`，非 0 = 被调试 | hook `open`/`read` 伪造内容；或 spawn 早注入让检测点发生在注入之后 |
| ptrace 双进程守护 | 守护进程 ptrace 主进程，检测自身/对方是否被附加 | 杀/停守护进程；或 patch ptrace 返回值 |
| `/proc/self/maps` 检测 | 扫 maps 找 frida-agent / gadget 字符串 | frida-server 改名/换端口；maps hook 过滤 |
| frida 默认端口扫描 | 连 27042 探测 frida-server | `frida-server -l 0.0.0.0:xxxxx` 换端口 |
| 时间差检测 | 两次 `clock_gettime(CLOCK_MONOTONIC)` 采样差过大 | hook clock_gettime 固定返回值；硬断不停在检测区 |
| syscall 直读 | 绕过 libc 直接 syscall 读状态 | 需 root + kprobe，或定制 ROM |
| 反 unidbg/模拟器 | 检测 syscall 指纹、时间单调性 | unidbg `setTime`/hook 处理；成本高，优先真机 |

## 前置

```powershell
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
$r = Resolve-ReverseToolSpec -Name 'frida'
& $r.Command --version        # (Resolve-ReverseToolSpec -Name 'frida').Command
$r = Resolve-ReverseToolSpec -Name 'objection'
& $r.Command --version        # (Resolve-ReverseToolSpec -Name 'objection').Command
$r = Resolve-ReverseToolSpec -Name 'adb'
& $r.Command devices
```

本技能包自带 `scripts/frida-run.ps1` 统一设备/进程/spawn 入口，优先用它而不是手拼参数。

## 步骤

### 1. frida-server 换端口 + spawn 早注入

```bash
# 设备侧
adb shell "su -c '/data/local/tmp/frida-server -l 0.0.0.0:28999 &'"
# 桌面侧：spawn 模式，早于 Application 创建注入
frida -H 127.0.0.1:28999 -f com.target.app -l bypass.js
```

spawn 模式下 Frida 在 `Application` 创建前注入，能覆盖 `attachBaseContext` 阶段的检测。

### 2. TracerPid 伪造

```javascript
// bypass.js —— hook open/read 伪造 /proc/self/status 的 TracerPid
var openPtr = Module.findExportByName("libc.so", "open");
var readPtr = Module.findExportByName("libc.so", "read");
var hitOpen = false;

Interceptor.attach(openPtr, {
    onEnter: function (args) { this.path = args[0].readCString(); }
});
Interceptor.attach(readPtr, {
    onEnter: function (args) {
        if (this.path && this.path.indexOf("status") !== -1) hitOpen = true;
    },
    onLeave: function (ret) {
        if (!hitOpen) return;
        var buf = args[1];
        var data = buf.readUtf8String(Math.min(ret.toInt32(), 512));
        if (data && data.indexOf("TracerPid:") !== -1) {
            data = data.replace(/TracerPid:\s*\d+/, "TracerPid:\t0");
            buf.writeUtf8String(data);
        }
        hitOpen = false;
    }
});
```

更稳的做法是只 hook `fopen`/`fgets`（应用常用 `ifstream`/`fgets` 读 status），按实际实现调整。

### 3. ptrace 双进程守护

```
1. 启动应用 → 观察进程树：主进程 + 守护进程（通常低权限/不同 uid）
2. adb shell ps -A | grep <pkg> 确认守护进程 pid
3. 方案 A：su -c "kill -9 <守护pid>" 后立即 attach 主进程
   （部分壳主进程也会自检守护存活，需同时 patch）
4. 方案 B：Frida 早注入后 hook ptrace，伪造失败返回
5. 方案 C：定制 ROM 在系统层对目标进程豁免 ptrace 检测
```

方案 B 的 hook：

```javascript
Interceptor.attach(Module.findExportByName("libc.so", "ptrace"), {
    onEnter: function (args) { this.req = args[0].toInt32(); },
    onLeave: function (ret) {
        // PTRACE_ATTACH=16, PTRACE_TRACEME=0
        if (this.req === 16 || this.req === 0) ret.replace(-1);
    }
});
```

### 4. 时间检测

```javascript
Interceptor.attach(Module.findExportByName("libc.so", "clock_gettime"), {
    onEnter: function (args) { this.clk = args[0].toInt32(); },
    onLeave: function (ret) {
        // CLOCK_MONOTONIC = 1
        if (this.clk === 1) { /* 写固定时间戳，消除单步/断点延迟特征 */ }
    }
});
```

## 判据

| 观察 | 结论 |
|---|---|
| logcat 出现 `[bypass] TracerPid hit` 之类输出 | 检测点被覆盖 |
| 无 hook 闪退、加 hook 后稳定运行 | 绕过生效 |
| 守护进程 pid 存在且被杀后主进程不再自检退出 | ptrace 守护已处理 |

**外部可观测的判据**：进程从「attach 即退」变成「attach 后保持存活并能继续 trace」；不是「脚本加载成功就算过」。未被绕过的检测点必须列为剩余风险，不能默认全过。

## 坑

- **spawn 与 attach 的顺序陷阱**：attach 只能观察 attach 之后的注册/调用，捕获 `JNI_OnLoad` 的启动期注册必须用 spawn。
- **`Module.findExportByName` 在模块未加载时返回 NULL**：直接 `Interceptor.attach(NULL)` 会抛异常，脚本要判空。
- **`ret.replace()` 必须在 `onLeave`**：在 `onEnter` 改返回值无效。
- **`clock_gettime` hook 会影响 Frida 自身计时**，过度伪造可能让目标逻辑异常，只针对 `CLOCK_MONOTONIC` 且按需使用。
- **本机无 Android 真机/模拟器**：以上绕过脚本在本机**未验证**，需在你的设备上实测并记录每个检测点的 bypass 与前后行为差异。

## 相关

- `vmp-dex2c-detection.md` —— 判定是否需要 trace 路线
- `vmp-dump-trace-recovery.md` —— 绕过之后走 trace 还原
- `../frida-bypass-kit.md` —— 现成的四合一绕过框架
