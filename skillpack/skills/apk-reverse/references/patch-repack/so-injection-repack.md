# Native SO 注入与 APK 重打包

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/apk-reverse/techniques/08-patch-repack/01-so-injection-repack.md`
> **什么时候用**：需要把自定义 `.so` 注入目标 APK，让代码在目标进程空间内运行（插桩、功能注入、行为监控）。

## 适用信号

- 目标 APK 已有 native 库
- 需要在目标进程上下文执行代码
- 静态修改（重打包）比动态注入更稳定

## 前置

```powershell
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
$apktool = (Resolve-ReverseToolSpec -Name 'apktool').Command
$zipalign = (Resolve-ReverseToolSpec -Name 'zipalign').Command
$apksigner = (Resolve-ReverseToolSpec -Name 'apksigner').Command
$adb = (Resolve-ReverseToolSpec -Name 'adb').Command
```

本技能包自带 `scripts/rebuild-sign-install.ps1` 完成「重建→对齐→签名→安装」。

## 步骤

### 1. APK 解包

```powershell
& $apktool d target.apk -o decoded -f
```

目录结构：

```
decoded/
├── AndroidManifest.xml
├── apktool.yml
├── res/
├── smali/
└── lib/
    ├── arm64-v8a/
    ├── armeabi-v7a/
    └── x86_64/
```

### 2. 放置注入 so

```powershell
# 必须覆盖全部目标架构，否则运行在别的 ABI 上会 UnsatisfiedLinkError
Copy-Item libinject.so decoded\lib\arm64-v8a\
Copy-Item libinject.so decoded\lib\armeabi-v7a\
```

若目标 manifest 未声明 `android:extractNativeLibs="true"`，按需在 `AndroidManifest.xml` 的 `<application>` 上补上。

### 3. Smali 层注入 loadLibrary

```smali
.method protected onCreate(Landroid/os/Bundle;)V
    .locals 1
    const-string v0, "inject"
    invoke-static {v0}, Ljava/lang/System;->loadLibrary(Ljava/lang/String;)V
    # ... 原始代码
.end method
```

### 4. 注入 so 的入口实现

```c
#include <jni.h>
#include <pthread.h>

/* constructor 早于 JNI_OnLoad 执行，适合做早期 hook */
__attribute__((constructor))
static void init(void) {
    /* hook dlopen/dlsym 等早期操作 */
}

JNIEXPORT jint JNI_OnLoad(JavaVM *vm, void *reserved) {
    JNIEnv *env;
    (*vm)->GetEnv(vm, (void **)&env, JNI_VERSION_1_6);
    pthread_t t;
    pthread_create(&t, NULL, main_loop, NULL);
    return JNI_VERSION_1_6;
}

void *main_loop(void *arg) {
    sleep(3);                 /* 等目标初始化完再动 */
    /* hook / 读写 / 注入逻辑 */
    return NULL;
}
```

### 5. 重建 + 对齐 + 签名（本机已验证）

```powershell
& $apktool b decoded -o rebuilt-unsigned.apk
& $zipalign -f -p 4 rebuilt-unsigned.apk rebuilt-aligned.apk
& $apksigner sign --ks debug.keystore --ks-pass pass:android `
    --key-pass pass:android --ks-key-alias androiddebugkey `
    --out rebuilt-signed.apk rebuilt-aligned.apk
& $apksigner verify --verbose --print-certs rebuilt-signed.apk
```

本机实测签名验证输出：

```
Verifies
Verified using v1 scheme (JAR signing): true
Verified using v2 scheme (APK Signature Scheme v2): true
Verified using v3 scheme (APK Signature Scheme v3): true
Number of signers: 1
Signer #1 certificate DN: CN=Android Debug, O=Android, C=US
Signer #1 certificate SHA-256 digest: 65f08f446618c38b814679ba4a0220355957811fe231d7ced80fd6b17f2df926
```

**记录这张 SHA-256 摘要** —— 它就是后面 `signature-integrity-bypass.md` 里要伪造回原值的那个东西。

### 6. 安装

```powershell
& $adb install -r rebuilt-signed.apk
```

## 对抗完整性校验

```c
/* 常见: 检测 APK 签名变化后闪退 */
/* 绕过1: Frida hook PackageManager.getPackageInfo */
/* 绕过2: native hook __system_property_get 返回假签名 */
/* 绕过3: 注入 lib 里直接 patch 校验函数 */
#include <sys/mman.h>
void bypass_integrity_check(void) {
    void *addr = base + 0x12345;
    mprotect((void *)((long)addr & ~0xFFF), 0x1000,
             PROT_READ | PROT_WRITE | PROT_EXEC);
    *(uint32_t *)addr = 0xD65F03C0;    /* arm64: RET */
}
```

## 常见坑

1. **架构不匹配**：arm64 的 so 注入 armeabi-v7a 进程会 `UnsatisfiedLinkError` → 编译全部架构。
2. **签名校验**：目标检测签名后闪退 → 定位校验函数先 bypass。
3. **SELinux 限制**：某些路径无法 `dlopen` → 放 `/data/local/tmp/` 或走 APK lib 目录。
4. **linker namespace**：Android 7+ 限制 `dlopen` 来源 → 注入到 APK 自己的 lib 目录内最稳。

## 判据

| 观察 | 结论 |
|---|---|
| `apktool b` 输出 `Built apk into:` | 打包成功 |
| `apksigner verify` 输出 `Verifies` 且 v1/v2/v3 均 true | 签名有效 |
| `adb install` 返回 `Success` | 安装成功 |
| 启动后 logcat 出现注入 so 的日志且应用不崩 | 注入生效 |

**外部可观测的判据**：`apksigner verify` 的 `Verifies` 行 + 安装后 logcat 里**注入代码自己的日志行** —— 不是「装上了」就算注入成功。

## 坑

- **必须覆盖所有 ABI**：漏一个架构会导致随机崩溃（取决于设备选哪个 ABI）。
- **`mprotect` 前要对页对齐**：`addr & ~0xFFF`。
- **`.init_array` 的 constructor 比 `JNI_OnLoad` 早**，要在最早期做事就用 constructor。
- **注入后签名变了**，目标几乎一定会做完整性检查，见 `signature-integrity-bypass.md`。
- **本机无 Android 设备**：安装与运行部分**需真机/模拟器，本机未验证**；apktool/zipalign/apksigner 链路已验证。

## 相关

- `signature-integrity-bypass.md` —— 重打包后的签名/哈希检查
- `../dex-java/smali-injection.md` —— Java 层注入
- `../native/jni-register-natives-tracing.md` —— 注入库注册自己的 native 方法
