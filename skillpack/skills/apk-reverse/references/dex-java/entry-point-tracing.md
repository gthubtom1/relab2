# 入口点追踪与组件分析

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/apk-reverse/techniques/03-manifest/01-entry-point-tracing.md`
> **什么时候用**：拿到一个未知 APK，要追出完整启动链（Application → Activity → native 加载），并找出 exported 组件的暴露面。

## 适用信号

- AndroidManifest.xml 已解码
- 需要理解启动后执行的完整路径
- 需要找出隐藏的 Receiver/Service

## 前置

```powershell
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
$aapt2  = (Resolve-ReverseToolSpec -Name 'aapt2').Command
$apktool = (Resolve-ReverseToolSpec -Name 'apktool').Command
$jadx = (Resolve-ReverseToolSpec -Name 'jadx').Command
```

本技能包自带 `scripts/manifest-summary.ps1` 做组件抽取，优先用它。

## 步骤

### 1. aapt 提取 Manifest 组件（本机已验证）

```powershell
& $aapt2 dump badging target.apk
```

本机对一个自建样本的实测输出：

```
package: name='com.revlab.demo' versionCode='1' versionName='1.0'
sdkVersion:'21'
targetSdkVersion:'34'
uses-permission: name='android.permission.INTERNET'
application-label:'RevLabDemo'
application: label='RevLabDemo' icon=''
launchable-activity: name='com.revlab.demo.DemoActivity'  label='' icon=''
main
supports-screens: 'small' 'normal' 'large' 'xlarge'
```

关键字段：`package:` 是包名，`launchable-activity:` 是 LAUNCHER 入口，`uses-permission:` 是权限清单。

### 2. aapt dump xmltree 看组件树

```powershell
& $aapt2 dump xmltree target.apk AndroidManifest.xml
```

实测输出（注意 `exported` 的编码形式）：

```
N: android=http://schemas.android.com/apk/res/android
  E: manifest (line=2)
    A: android:versionCode(0x0101021b)=(type 0x10)0x1
    A: package="com.revlab.demo" (Raw: "com.revlab.demo")
    E: uses-sdk (line=0)
      A: android:minSdkVersion(0x0101020c)=(type 0x10)0x15
      A: android:targetSdkVersion(0x01010270)=(type 0x10)0x22
    E: uses-permission (line=4)
      A: android:name(0x01010003)="android.permission.INTERNET"
    E: application (line=5)
      A: android:label(0x01010001)=@0x7f010000
      E: activity (line=6)
        A: android:name(0x01010003)="com.revlab.demo.DemoActivity"
        A: android:exported(0x01010010)=(type 0x12)0xffffffff
        E: intent-filter (line=7)
          E: action (line=8)
            A: android:name(0x01010003)="android.intent.action.MAIN"
          E: category (line=9)
            A: android:name(0x01010003)="android.intent.category.LAUNCHER"
```

**`android:exported` 的编码**：`(type 0x12)0xffffffff` 表示 `true`（布尔真存为全 1），`0x0` 表示 `false`。`0x10` 是整型，`0x12` 是布尔型。

### 3. apktool 解包看 smali

```powershell
& $apktool d target.apk -o decoded -f
Select-String -Path 'decoded\smali\**\*.smali' -Pattern 'loadLibrary' | Select-Object -First 20
```

本机实测的解包目录结构（注意 apktool 会自动下载 framework 到 `%LOCALAPPDATA%\apktool\framework`）：

```
decoded
decoded/AndroidManifest.xml
decoded/apktool.yml
decoded/original
decoded/original/AndroidManifest.xml
decoded/original/META-INF
decoded/res
decoded/smali
```

### 4. jadx 读 Java 启动链

```powershell
& $jadx -d jadx_out target.apk 2>&1 | Select-Object -Last 3
```

jadx 只输出进度行，成功时最后是 `INFO  - done`。产物：

```
jadx_out/sources/com/revlab/demo/DemoActivity.java
jadx_out/sources/com/revlab/demo/R.java
```

### 5. 标准启动顺序

```java
Application.attachBaseContext()      // 最早期，加固/反作弊 SDK 常在这里
→ Application.onCreate()
  → initThirdPartySDK()
  → System.loadLibrary("xxx")      // native 加载入口
    → .init_array（构造函数先于 JNI_OnLoad）
    → JNI_OnLoad（RegisterNatives 注册）
```

### 6. Native 加载追踪

```powershell
Get-ChildItem decoded\lib -Recurse -Filter *.so | Select-Object FullName, Length
```

smali 里搜到的典型结果：

```
smali/com/target/GameApp.smali: System.loadLibrary("cocos2djs")
smali/com/target/GameApp.smali: System.loadLibrary("NativeProtect")
```

加载顺序：`cocos2djs` 先，`NativeProtect` 后 —— 后者通常是反调试/加固。

### 7. exported 组件暴露面

```powershell
& $aapt2 dump xmltree target.apk AndroidManifest.xml |
  Select-String 'android:exported.*0xffffffff' -Context 6,0
```

检查点：

- **exported Provider** → 可能泄露数据
- **exported Service** → 可被外部启动执行
- **exported Receiver** → 可被外部广播触发
- **intent-filter** → 隐式启动入口

导出的 ContentProvider 若无权限保护，外部应用可直接 `content://<pkg>.provider/...` 读取。

## 判据

| 观察 | 结论 |
|---|---|
| `aapt2 dump badging` 有 `launchable-activity:` | 定位到启动 Activity |
| xmltree 里 `exported=(type 0x12)0xffffffff` | 该组件对外导出，属暴露面 |
| smali 中 `loadLibrary` 出现在 `attachBaseContext` | 加固层早于业务层，先过它 |
| `lib/` 下有多个 so 且命名带 Protect/Shell | 存在加固层 |

**外部可观测的判据**：`aapt2 dump badging` 的 `launchable-activity` 行 + xmltree 的 `exported` 属性编码 —— 不是「看 manifest 猜」。

## 坑

- **`aapt2 dump badging` 不显示 `android:exported`**，要 `dump xmltree` 才看得到。
- **`exported=true` 编码成 `0xffffffff`**，正则匹配 `true` 是无效的。
- **`aapt2 link` 需要 `android.jar`**：本机 `D:\Tools\android-sdk\build-tools\34.0.0\lib\android.jar` **不存在**，自建 APK 要用 apktool 的 `b` 命令（apktool 自带 aapt2）。
- **apktool 3.x 的 `apktool.yml` 里数字不能加引号**：写 `versionCode: '1'` 会抛 `NumberFormatException`，必须写 `versionCode: 1`。
- **jadx 可能部分反编译失败但仍有产物**，不要因为报错就丢弃输出目录。
- **多 dex 要看 `smali/`、`smali_classes2/`……** 全套，`Select-String -Path '**\*.smali'` 才能覆盖。

## 相关

- `../native/so-structure-audit.md` —— 拿到 so 后做结构体检
- `../packer/vmp-dex2c-detection.md` —— 判断是否加固/虚拟化
- `../patch-repack/signature-integrity-bypass.md` —— exported/installer 相关的完整性检查
