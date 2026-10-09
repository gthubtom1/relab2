# Smali 代码注入与 DEX 修改

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/apk-reverse/techniques/01-dex-java/01-smali-injection.md`
> **什么时候用**：需要往目标 APK 注入 Java 层代码（加载 native 库、插桩日志、改逻辑），通过修改 smali 字节码实现。

## 适用信号

- 已 `apktool d` 解包
- 需要在 Activity/Service/Application 生命周期插入代码
- 目标是 Java/Kotlin 层逻辑修改

## Smali 基础速查

| Java | Smali |
|---|---|
| `String s = "hello"` | `const-string v0, "hello"` |
| `int a = 5` | `const/4 v0, 0x5` |
| `System.out.println(s)` | `invoke-virtual {v0}, Ljava/io/PrintStream;->println(Ljava/lang/String;)V` |
| `new Intent()` | `new-instance v0, Landroid/content/Intent;` |
| `if (x == 0) {}` | `if-eqz v0, :cond_0` |
| `return x` | `return v0` |

## 前置

```powershell
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
$apktool = (Resolve-ReverseToolSpec -Name 'apktool').Command
& $apktool d target.apk -o decoded -f
```

本技能包自带 `scripts/rebuild-sign-install.ps1` 做「重建→对齐→签名→安装」闭环。

## 步骤

### 1. 注入点选择

#### Application.attachBaseContext（最早，早于所有 Activity）

```smali
.class public Lmyapp/MyApplication;
.super Landroid/app/Application;

.method protected attachBaseContext(Landroid/content/Context;)V
    .locals 1
    # 注入: 加载 native lib
    const-string v0, "inject"
    invoke-static {v0}, Ljava/lang/System;->loadLibrary(Ljava/lang/String;)V
    # 继续原始逻辑
    invoke-super {p0, p1}, Landroid/app/Application;->attachBaseContext(Landroid/content/Context;)V
    return-void
.end method
```

#### MainActivity.onCreate（界面入口）

```smali
.method protected onCreate(Landroid/os/Bundle;)V
    .locals 2
    new-instance v0, Ljava/lang/Thread;
    new-instance v1, Lmyapp/InjectRunnable;
    invoke-direct {v1}, Lmyapp/InjectRunnable;-><init>()V
    invoke-direct {v0, v1}, Ljava/lang/Thread;-><init>(Ljava/lang/Runnable;)V
    invoke-virtual {v0}, Ljava/lang/Thread;->start()V
    invoke-super {p0, p1}, Landroid/app/Activity;->onCreate(Landroid/os/Bundle;)V
    return-void
.end method
```

#### static 代码块（类加载时）

```smali
.method static constructor <clinit>()V
    .locals 1
    const-string v0, "inject"
    invoke-static {v0}, Ljava/lang/System;->loadLibrary(Ljava/lang/String;)V
    return-void
.end method
```

### 2. 修改现有 vs 新增 smali 文件

```powershell
# 方式1: 修改现有 smali（小改动）
notepad decoded\smali\com\target\MainActivity.smali
# 方式2: 新增 smali 类（推荐，隔离性好）
#   decoded\smali\com\inject\InjectHelper.smali
```

### 3. 重建（本机已验证）

```powershell
& $apktool b decoded -o rebuilt-unsigned.apk
```

本机实测输出：

```
I: Using Apktool 3.0.3 on demo.apk with 8 threads
I: Smaling smali folder into classes.dex...
I: Building resources with aapt2...
I: Building apk file...
I: Built apk into: C:\...\demo-unsigned.apk
```

### 4. 验证字节码（本机已验证）

重建后用 `dexdump` 确认注入的指令真的进了 dex：

```powershell
$ddexdump = 'D:\Tools\android-sdk\build-tools\34.0.0\dexdump.exe'
& $ddexdump -d unz\classes.dex
```

实测输出（能看到 `const-string v0, "inject"` 和 `System.loadLibrary`）：

```
Processing 'unz/classes.dex'...
Opened 'unz/classes.dex', DEX version '035'
  Virtual methods   -
    #0              : (in Lcom/revlab/demo/DemoActivity;)
      name          : 'onCreate'
      type          : '(Landroid/os/Bundle;)V'
      code          : 9 16-bit code units
000200: 1a00 0800                              |0000: const-string v0, "inject"
000204: 7110 0400 0000                         |0002: invoke-static {v0}, Ljava/lang/System;.loadLibrary:(Ljava/lang/String;)V
00020a: 6f20 0100 3200                         |0005: invoke-super {v2, v3}, Landroid/app/Activity;.onCreate:(Landroid/os/Bundle;)V
000210: 0e00                                   |0008: return-void
```

**这是「注入确实写进 dex 了」的外部可观测证据**，比「apktool b 没报错」强得多。

### 5. 对齐 + 签名（本机已验证）

```powershell
$zipalign  = (Resolve-ReverseToolSpec -Name 'zipalign').Command
$apksigner = (Resolve-ReverseToolSpec -Name 'apksigner').Command
& $zipalign -f -p 4 rebuilt-unsigned.apk rebuilt-aligned.apk
& $apksigner sign --ks debug.keystore --ks-pass pass:android `
    --key-pass pass:android --ks-key-alias androiddebugkey `
    --out rebuilt-signed.apk rebuilt-aligned.apk
```

验证：

```powershell
& $apksigner verify --verbose --print-certs rebuilt-signed.apk
```

本机实测输出：

```
Verifies
Verified using v1 scheme (JAR signing): true
Verified using v2 scheme (APK Signature Scheme v2): true
Verified using v3 scheme (APK Signature Scheme v3): true
Number of signers: 1
Signer #1 certificate DN: CN=Android Debug, O=Android, C=US
Signer #1 certificate SHA-256 digest: 65f08f446618c38b814679ba4a0220355957811fe231d7ced80fd6b17f2df926
```

### 6. 安装

```powershell
$adb = (Resolve-ReverseToolSpec -Name 'adb').Command
& $adb install -r rebuilt-signed.apk
```

## 判据

| 观察 | 结论 |
|---|---|
| `apktool b` 输出 `Built apk into:` | smali 汇编通过 |
| `dexdump -d` 能看到注入的指令 | 注入确实进了 dex |
| `apksigner verify` 输出 `Verifies` + 各 scheme 为 true | 签名有效 |
| `adb install` 返回 `Success` 且应用能启动 | 端到端可用 |

**外部可观测的判据**：`dexdump` 的反汇编行 + `apksigner verify` 的 `Verifies` —— 不是「构建成功」就算完成。

## 坑

- **寄存器冲突**：注入代码用的 `vN` 可能与原始代码冲突 → 从大号开始用（`v10+`），并同步调大 `.locals`。
- **`.locals` 要够**：加了几个局部变量就得加多少，否则寄存器越界，`apktool b` 会报寄存器错误。
- **label 重复**：注入段的 label 名不能与原文件重复。
- **try-catch 边界**：在 smali 里改 try 块要同步更新 `.catch` 指令。
- **apktool 3.x 的 `apktool.yml` 数字不能加引号**：`versionCode: '1'` 会抛 `NumberFormatException`。
- **重打包后签名必变**：目标有签名校验会闪退，见 `../patch-repack/signature-integrity-bypass.md`。
- **多 dex 应用**：`apktool d` 会生成 `smali/`、`smali_classes2/`……注入后要确认落到正确的那个。
- **本机无 Android 设备**：安装与运行部分**需真机/模拟器，本机未验证**；apktool/dexdump/zipalign/apksigner 链路已验证。

## 相关

- `../patch-repack/so-injection-repack.md` —— 注入 native 库
- `../patch-repack/signature-integrity-bypass.md` —— 重打包后的完整性检查
- `entry-point-tracing.md` —— 选对注入点（同目录）
