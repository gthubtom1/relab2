# 签名与完整性检查绕过

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/apk-reverse/techniques/08-patch-repack/02-signature-integrity-bypass.md`
> **什么时候用**：APK patch/repack 后启动失败、功能锁定或闪退，需要定位签名证书、包体 hash、classes.dex hash、so hash、installer 来源、Play Integrity 检查点。

## 入口信号

```text
repack 后安装成功但启动闪退
logcat: signature mismatch / integrity failed / invalid channel
jadx:  getPackageInfo(..., GET_SIGNATURES|GET_SIGNING_CERTIFICATES)
jadx:  MessageDigest.getInstance("SHA-256")
native: open/read classes.dex 或 lib*.so 后计算 hash
网络: 启动请求携带 sign_hash / cert_md5 / channel
```

先定位检查点，再选择 Java hook、smali patch、native patch 或签名参数重算。

## 前置

```powershell
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
$apksigner = (Resolve-ReverseToolSpec -Name 'apksigner').Command
$frida = (Resolve-ReverseToolSpec -Name 'frida').Command
```

## 步骤

### 1. 先取原始签名摘要（这是要伪造回的目标值）

```powershell
& $apksigner verify --verbose --print-certs original.apk
```

本机实测输出格式（对自建样本）：

```
Verifies
Verified using v1 scheme (JAR signing): true
Verified using v2 scheme (APK Signature Scheme v2): true
Verified using v3 scheme (APK Signature Scheme v3): true
Number of signers: 1
Signer #1 certificate DN: CN=Android Debug, O=Android, C=US
Signer #1 certificate SHA-256 digest: 65f08f446618c38b814679ba4a0220355957811fe231d7ced80fd6b17f2df926
Signer #1 certificate SHA-1 digest: 06c61b56ce07211cf6d70d092868b51ff66d53b8
Signer #1 certificate MD5 digest: facef22f4d2c4feac3367d5931cec001
```

**这张表就是白名单基线**：重打包后要伪造回的就是这些值。

### 2. 静态定位

```powershell
$jadx = (Resolve-ReverseToolSpec -Name 'jadx').Command
& $jadx -d jadx_out target.apk 2>&1 | Select-Object -Last 3
Select-String -Path 'jadx_out\sources\**\*.java' -Pattern 'GET_SIGNATURES|GET_SIGNING_CERTIFICATES|SigningInfo|getInstallerPackageName|MessageDigest|SHA-256|integrity|signature' |
  Select-Object -First 40

$apktool = (Resolve-ReverseToolSpec -Name 'apktool').Command
& $apktool d target.apk -o decoded -f
Select-String -Path 'decoded\smali\**\*.smali' -Pattern 'signature|digest|hash|classes\.dex|base\.apk|sourceDir' |
  Select-Object -First 40
```

### 3. Java 层打点

```javascript
Java.perform(function () {
    const PM = Java.use("android.app.ApplicationPackageManager");
    PM.getPackageInfo.overload("java.lang.String", "int")
    .implementation = function (pkg, flags) {
        const r = this.getPackageInfo(pkg, flags);
        // GET_SIGNATURES=0x40, GET_SIGNING_CERTIFICATES=0x08000000
        if ((flags & 0x40) || (flags & 0x08000000))
            console.log("[sig] getPackageInfo pkg=" + pkg +
                        " flags=0x" + flags.toString(16));
        return r;
    };

    const MD = Java.use("java.security.MessageDigest");
    MD.getInstance.overload("java.lang.String")
    .implementation = function (alg) {
        console.log("[digest] getInstance " + alg);
        return this.getInstance(alg);
    };
});
```

配合堆栈定位调用者：

```javascript
function printStack(tag) {
    const Exception = Java.use("java.lang.Exception");
    const Log = Java.use("android.util.Log");
    console.log(tag + "\n" + Log.getStackTraceString(Exception.$new()));
}
```

### 4. Native 层文件 hash 打点

```javascript
["open", "openat", "read", "fopen"].forEach(function (name) {
    const p = Module.findExportByName(null, name);
    if (!p) return;
    Interceptor.attach(p, {
        onEnter(args) {
            const path = (name === "openat")
                ? args[1].readCString()
                : args[0].readCString();
            if (path && (path.indexOf("base.apk") >= 0 ||
                         path.indexOf("classes.dex") >= 0 ||
                         path.indexOf(".so") >= 0))
                console.log("[file] " + name + " " + path);
        }
    });
});
```

若进入 `SHA256_Update` / `MD5_Update`，继续 hook 长度和调用者：

```javascript
["SHA256_Update", "MD5_Update"].forEach(function (name) {
    const p = Module.findExportByName(null, name);
    if (!p) return;
    Interceptor.attach(p, {
        onEnter(args) {
            console.log("[hash] " + name + " len=" + args[2] +
                        " caller=" + this.returnAddress);
        }
    });
});
```

## 路径分叉

| 检查类型 | 打点动作 | 下一跳 |
|---|---|---|
| APK 签名证书 | hook `getPackageInfo` / `SigningInfo` | 返回原证书摘要，或 patch 比较分支 |
| `classes.dex` hash | hook `MessageDigest` / native hash | 重新计算白名单或 patch 结果 |
| SO hash | hook `open/read` + `SHA256_Update` | IDA 定位校验函数，patch 返回值 |
| Installer 来源 | hook `getInstallerPackageName` | 返回期望 installer |
| Play Integrity | 定位 nonce/request token | 网络验证或响应处理路径 |

## Smali patch 模式

```smali
# 原始: if-eqz v0, :cond_fail
# 修改: 强制进入 pass 分支
const/4 v0, 0x1
if-nez v0, :pass
```

记录 patch：

```text
file   : smali_classes*/com/vendor/Guard.smali
method : checkSignature()Z
old    : if-eqz v0, :cond_fail
new    : const/4 v0, 0x1
effect : repack 后启动进入主界面
```

## 判据

| 观察 | 结论 |
|---|---|
| `[sig] getPackageInfo flags=0x40` 出现 | Java 层签名校验点已定位 |
| `[digest] getInstance SHA-256` + 堆栈类名 | hash 校验点已定位 |
| `[file] openat .../base.apk` | native 侧在读包体算 hash |
| patch 后复验启动成功且功能可用 | 绕过生效 |

**外部可观测的判据**：hook 日志里出现具体的 flags 值/路径/类名，配合 patch 前后**启动行为差异**（闪退 → 正常进入），不是「脚本跑通就算过」。

## 坑

- **`getPackageInfo` 有多个重载**（`int` / `PackageInfoFlags`），只 hook 一个会漏。
- **`GET_SIGNATURES=0x40` 在新版本被废弃**，应用可能改用 `GET_SIGNING_CERTIFICATES=0x08000000`；两个都要 hook。
- **v2/v3 签名确实可以没有 `META-INF`**，但 `apksigner verify` 默认判定会因此报 `Missing META-INF/MANIFEST.MF` —— 那是**校验器按 minSdk 要求 v1**，不是签名坏了。本机实测：对 `--v1-signing-enabled false --v2-signing-enabled true` 签出的 APK（条目只有 `AndroidManifest.xml`/`classes.dex`/`resources.arsc` 三个），直接 verify 报 `DOES NOT VERIFY / ERROR: Missing META-INF/MANIFEST.MF`；加 `--min-sdk-version 24` 后通过：
  ```
  Verifies
  Verified using v1 scheme (JAR signing): false
  Verified using v2 scheme (APK Signature Scheme v2): true
  Verified using v3 scheme (APK Signature Scheme v3): true
  ```
  结论：**在 `META-INF` 里找不到签名文件，先看 verify 的 scheme 行再下结论**，别默认「没签」。
- **伪造 hash 要返回完整摘要而不是前缀**，截断比较的话反而会暴露。
- **`SHA256_Update` 的 `len` 参数是 `size_t`**（64 位），打印时注意类型。
- **重打包必改签名**：每次重打包后重新取 `apksigner verify` 的摘要作为新基线。
- **本机无 Android 设备**：hook 与复验部分**需真机/模拟器，本机未验证**；`apksigner verify` 取基线摘要已验证。

## 相关

- `so-injection-repack.md` —— 注入 so 后必然触发完整性检查
- `../dex-java/smali-injection.md` —— smali patch 的语法细节
- `../network/license-verification-bypass.md` —— 校验结果影响在线验证
