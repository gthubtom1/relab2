# JNI RegisterNatives 追踪与 Native 入口还原

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/apk-reverse/techniques/02-native/06-jni-register-natives-tracing.md`
> **什么时候用**：要把「Java native 方法名」映射到「SO 内真实函数地址」，再沿调用者/被调用者走到 crypto、license、packet、anti-tamper 节点。

## 入口信号

```text
jadx:  native byte[] encrypt(byte[] in)
jadx:  System.loadLibrary("guard")
logcat: UnsatisfiedLinkError / JNI DETECTED ERROR
so:    只导出 JNI_OnLoad，没有 Java_com_* 符号
strings: Java_com_vendor_app_Sign_sign
```

## 前置

```powershell
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
$r = Resolve-ReverseToolSpec -Name 'apktool'; & $r.Command d target.apk -o out -f
$r = Resolve-ReverseToolSpec -Name 'python'
& $r.Command 'C:\relab2\skillpack\skills\apk-reverse\scripts\so-structure-audit.py' out\lib\arm64-v8a\libguard.so --jni
```

## 步骤

### 1. 静态定位

```powershell
$jadx = (Resolve-ReverseToolSpec -Name 'jadx').Command
& $jadx -d jadx_out target.apk 2>&1 | Select-Object -Last 3
Select-String -Path 'jadx_out\sources\**\*.java' -Pattern 'native |loadLibrary|JNI' | Select-Object -First 30

$py = (Resolve-ReverseToolSpec -Name 'python').Command
& $py 'C:\relab2\skillpack\skills\apk-reverse\scripts\so-structure-audit.py' `
    out\lib\arm64-v8a\*.so --jni --strings 5 --grep 'sign|encrypt|verify|token|packet'
```

如果导出表**只有 `JNI_OnLoad`**，说明用动态注册 → 下一步 hook `RegisterNatives`。

本机在真实 SO 上验证了这一判据：`libhgl.so` 有 1443 个导出但**零个 `Java_*`/`JNI_OnLoad`**，脚本直接报：

```
-- exports -- 1443 条
  (无 JNI_*/JNI_OnLoad 导出 -> 高度可能用 RegisterNatives 动态注册)
```

### 2. 追踪 SO 加载

```javascript
// hook dlopen/android_dlopen_ext，记录加载路径与基址
var dlopen = Module.findGlobalExportByName("dlopen");
Interceptor.attach(dlopen, {
    onLeave: function (ret) {
        var mod = Process.findModuleByAddress(ret);
        if (mod) console.log("[dlopen] " + mod.name + " base=" + mod.base);
    }
});
```

attach 只能观察 attach 之后的加载；要捕获启动期（`Application.attachBaseContext` 之前）的加载，**必须用 spawn 模式**：

```powershell
$frida = (Resolve-ReverseToolSpec -Name 'frida').Command
& $frida -U -f com.target.app -l hook.js
```

### 3. hook RegisterNatives

```javascript
var RN = Module.findGlobalExportByName("RegisterNatives");
Interceptor.attach(RN, {
    onEnter: function (args) {
        var clazz    = args[1];       // jclass
        var methods  = args[2];       // JNINativeMethod*
        var nMethods = args[3].toInt32();
        var env = Java.vm.getEnv();
        var name = env.getClassName(clazz);
        console.log("[RN] class=" + name + " n=" + nMethods);
        for (var i = 0; i < nMethods; i++) {
            var p = methods.add(i * Process.pointerSize * 3);
            var mName   = p.readPointer().readCString();
            var mSig    = p.add(Process.pointerSize).readPointer().readCString();
            var mFn     = p.add(Process.pointerSize * 2).readPointer();
            var mod = Process.findModuleByAddress(mFn);
            var rva = mod ? mFn.sub(mod.base) : ptr(0);
            console.log("  " + name + "->" + mName + mSig +
                        " @ " + mFn + " rva=0x" + rva + " (" +
                        (mod ? mod.name : "?") + ")");
        }
    }
});
```

`JNINativeMethod` 是三个指针的数组：`{ name, signature, fnPtr }`，所以步长是 `pointerSize * 3`。字符串读取建议限长（如 256 字节），失败标 unresolved 而不是中断整次观察。

### 4. 关键点：ASLR 归一化

运行时 VA 不能直接当静态地址用：

```text
module base <= runtime VA < module base + module size
RVA       =  runtime VA - runtime base
静态地址   =  Ghidra/IDA image base + RVA
```

**RVA 只在同一二进制内有效**：必须核对 SO 的完整路径、架构、SHA256 或 build ID。路径相同不代表内容相同；hash/架构/地址范围不一致时保留 `unresolved`，不要强行关联。

在 IDA/Ghidra 里按这个顺序建立候选命名：

```text
JNI_OnLoad
  -> candidate_register_native_methods
     -> candidate_native_sign
        -> candidate_native_encrypt_packet
```

### 5. 参数/返回值打点

```javascript
Interceptor.attach(NATIVE_ADDR, {
    onEnter: function (args) { console.log("[native] enter"); this.a2 = args[2]; },
    onLeave: function (ret)  { console.log("[native] ret=" + ret); }
});
```

Java 层入参再往上追一层：

```javascript
Java.perform(function () {
    var C = Java.use("com.vendor.app.NativeBridge");
    C.sign.implementation = function (data) {
        console.log("[java] sign len=" + data.length);
        var out = this.sign(data);
        console.log("[java] sign ret len=" + out.length);
        return out;
    };
});
```

### 6. IDA 分析 so

```powershell
$idat = (Resolve-ReverseToolSpec -Name 'idat64_83').Command
& $idat -A -S"<script.py>" -L"<log.txt>" -o"<out.i64>" $SO_PATH
```

脚本必须以 `idc.qexit(0)` 结尾并先 `idaapi.auto_wait()`。

## 路径分叉

| 发现 | 下一跳 |
|---|---|
| `sign(String, byte[])` | 请求签名、重放、参数篡改 |
| `encrypt` / `decrypt` | `../crypto/game-encryption-patterns.md` 抓 key/IV |
| `checkLicense` | `../network/license-verification-bypass.md` |
| `checkSignature` / `checkRoot` | `../patch-repack/signature-integrity-bypass.md` |
| `pack` / `unpack` | 协议字段还原 |

## 判据

| 观察 | 结论 |
|---|---|
| hook 输出打印出 `class->name+sig @ VA rva=0x...` | 注册映射已建立 |
| `rva` 落在该 so 的映射范围内且换算后命中 IDA 函数入口 | 地址归一化正确 |
| SO 的 SHA256/build ID 与 IDA 里导入的不一致 | 保留 unresolved，不要关联 |
| 只在 spawn 模式下才捕获到注册 | 启动期注册，attach 模式注定看不到 |

**外部可观测的判据**：日志里同时出现 **Java class 名 + 方法名 + JNI 签名 + 所属模块 + RVA** 五元组 —— 只有 VA 没有 class 名，无法区分不同类的同名方法。

## 坑

- **`JNINativeMethod` 数组步长是 12 字节（64 位）**，用 `pointerSize` 算，不要写死。
- **`RegisterNatives` 在 `libart.so`**，不在 libc；`Module.findGlobalExportByName` 才能找到。
- **`JNI_OnLoad` 早于 attach**：不 spawn 就只能看到 attach 之后的注册。
- **同一个 native 方法可能被多次注册**（热修复、多 class 复用），要按 class 名去重。
- **本机无 Android 设备**：第 2~5 步的 Frida 部分**需真机/模拟器，本机未验证**；第 1 步的静态导出判据已用真实 SO 验证。

## 相关

- `so-structure-audit.md` —— 导出/导入体检（`--jni` 直接判是否动态注册）
- `../crypto/game-encryption-patterns.md` —— 加密入口参数提取
- `../patch-repack/so-injection-repack.md` —— 注入自己的 so
