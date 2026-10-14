---
name: apk-reverse
description: APK 逆向：jadx/apktool 解包、改 smali/AndroidManifest、重打包、Frida hook。用于：APK 逻辑、装不上、去广告、查服务器、root 检测。
---

## ACTION REQUIRED（读完后立刻执行）

> 端点提取/Frida 自适应等社区对照：../references/community-security-skills.md；动态分析要先连上设备（真机开 USB 调试，或模拟器走 `references/emulator-lab.md`）。

1. `NOW`: 读 `../field-journal/precedent-reverse.md` —— 本机做过多轮的常规操作清单，直接照做，不要停在犹豫上
2. `NOW`: 确认当前任务是否命中本 skill 的适用范围
3. `NOW`: **查经验卡** —— `python skills/scripts/experience-card.py search "<你看到的症状>"`。
   命中就读那张卡的 `invariant` + `decision.action`，并**逐条对照** `scope.appliesWhen`
   与 `scope.stopsWhen`：少一条前提就停用；命中任一停止条件就停。
   历史卡**不替代**当前目标的实测证据。详见 `../experience-cards/INDEX.md`。
4. `NEXT`：**工具定位** —— 先载入探测层 `. C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1`（本机固定路径；万一这台机器还没建好、该文件不存在，改成从本文件往上两级的 `..\..\skills\scripts\lib\Bootstrap.ps1`），再 `Resolve-ReverseToolSpec -Name <id>`，按返回的 `Command` 调（完整路径，别依赖 cwd）。**`Get-Command` 返回空 ≠ 本机缺工具**（PATH 快照陷阱，见 `../references/env-selfcheck.md`）；四级探测全部 `Available=False` 才允许报缺。`../TOOLS.md` 是装法说明书，不是路径索引。禁止猜路径。
5. `NEXT`: 缺工具时调用 bootstrap，不要猜路径
6. `ACT`: 进入"工作流"第一步并执行，不要停在确认状态

# APK 逆向 CLI 作业规范

## 适用范围

当任务属于以下场景时优先使用本 skill：

- 分析 APK 的 Java 业务逻辑
- 定位登录、签名、风控、证书校验、root 检测
- 查看与修改 `AndroidManifest.xml`
- 查看与修改 smali
- 重打包 APK
- 用 Frida 做 Java/native 动态 Hook
- APK 内含 `.so` 时切到 native 分析

## 当前机器已验证可用的 CLI 工具

- `jadx` `1.5.5`
- `apktool` `3.0.2`
- `frida-ps` `17.9.6`
- `adb`
- `java`

## 优先使用脚本的场景

以下流程高频且参数容易出错，优先用 skill 自带脚本：

- 一次性完成 `jadx + apktool` 落盘并产出摘要：`scripts/decode.ps1`
- Frida 设备检查、进程列举、spawn/attach 注入：`scripts/frida-run.ps1`
- 重建、对齐、签名、安装 APK：`scripts/rebuild-sign-install.ps1`
- 快速抽取 Manifest 关键组件与权限：`scripts/manifest-summary.ps1`
- **真机一条龙**（doctor / inspect / install / run / log / shot / frida / info）：
  `scripts/apk-debug.ps1` —— 面向 agent 设计，**所有输出都是文本**，不需要看界面。
  静态拆包实测 80 MB 包 125 秒产出 8179 个 .java + 18423 个 .smali。
- **退出码契约自测**：`scripts/test-adb-exit-contract.ps1`（4 个退出码全覆盖，1 秒）
  —— 改动 `apk-debug.ps1` 的 `Adb` 后必须跑，否则 install 可能恒走失败分支。

- **模拟器一条龙**（夜神 / 雷电 / 蓝叠 / MuMu / MEmu / 官方 AVD）：
  `scripts/emulator-lab.ps1` —— 发现 / 连接 / 控制 / 抓包三层 / frida-server 部署 / 输入注入。
  **不预装模拟器**：装上之后本脚本自动认出来就能用，无需改代码。
  端口表、各家控制 CLI 语法、抓包三层的取舍见 `references/emulator-lab.md`。
- **模拟器能力层契约测试**：`scripts/test-emulator-lab.ps1`（不需要任何模拟器；
  含反例控制组证明判据真的会红）。改动 `emulator-lab.ps1` 的端口表或厂商解析后必须跑。
- **已沉淀的可复用规则（经验卡）**：动手前先查
  `python skills/scripts/experience-card.py search "<症状>"`；
  命中就对照 `appliesWhen` / `stopsWhen` 再用，别硬套。新经验用 `new` 沉淀。

以下一行命令保持直接调用，不单独封装：

- `adb devices`
- `adb logcat`
- `frida-ps -U`
- `jadx --version`
- `apktool --version`

## 自带脚本

### `scripts/decode.ps1`

用途：

- 统一跑 `jadx` 和 `apktool`
- 默认在原 APK 同目录创建任务输出目录
- 输出 `package`、`java_files`、`smali_dirs`、`so_files` 等摘要
- 兼容 `jadx` 部分反编译错误但仍然有可用产物的情况

示例：

```powershell
pwsh -File "<skill-root>\apk-reverse\scripts\decode.ps1" -ApkPath "D:\DOWNLOAD\app.apk" -Clean
pwsh -File "<skill-root>\apk-reverse\scripts\decode.ps1" -ApkPath "D:\DOWNLOAD\app.apk" -Name demo -SkipJadx
```

### `scripts/frida-run.ps1`

用途：

- 统一 Frida 的设备、进程、spawn/attach 入口
- 避免手写参数时混淆 `-f`、`-n`、`-U`

示例：

```powershell
pwsh -File "<skill-root>\apk-reverse\scripts\frida-run.ps1" -ListDevices
pwsh -File "<skill-root>\apk-reverse\scripts\frida-run.ps1" -Usb -ListProcesses
pwsh -File "<skill-root>\apk-reverse\scripts\frida-run.ps1" -Usb -Spawn -Package com.example.app -ScriptPath "D:\hooks\test.js"
```

### `scripts/rebuild-sign-install.ps1`

用途：

- `apktool b` 重建 APK
- `zipalign` 对齐
- `apksigner` 签名与验签
- 可选直接 `adb install`

示例：

```powershell
pwsh -File "<skill-root>\apk-reverse\scripts\rebuild-sign-install.ps1" -ProjectDir "C:\work\apktool_out" -Clean
pwsh -File "<skill-root>\apk-reverse\scripts\rebuild-sign-install.ps1" -ProjectDir "C:\work\apktool_out" -Install -Reinstall -DeviceSerial "127.0.0.1:7555"
```

说明：

- 默认生成并复用调试 keystore
- 默认输出到 `ProjectDir` 同目录，便于和原始包、解包目录放在一起

### `scripts/manifest-summary.ps1`

用途：

- 抽取包名
- 列权限
- 列 activity/service/receiver/provider
- 标出主启动 activity

示例：

```powershell
pwsh -File "<skill-root>\apk-reverse\scripts\manifest-summary.ps1" -ManifestPath "C:\work\apktool_out\AndroidManifest.xml"
```

如果要分析 `.so`、`lib/arm64-v8a/*.so`、`lib/armeabi-v7a/*.so`，再结合：

- `ida-reverse`
- `radare2`

## 工具分工

### `jadx`

用于：

- Java 反编译阅读
- 包名、类名、方法名搜索
- 先从高层逻辑理解 APK

常用命令：

```bash
jadx -d jadx_out app.apk
jadx --single-class com.example.LoginActivity -d jadx_out app.apk
jadx --deobf -d jadx_out app.apk
```

### `JEB Pro`（可选商业工具）

用于：

- Android DEX / APK / ARM 的交叉验证与深度反编译
- 在 JADX 输出不完整或混淆较重时补充静态分析
- 对同一目标的类、方法与调用关系进行第二工具链校验

边界：

- JEB Pro 是商业软件，必须由用户自行取得并安装有效许可证；本包不会下载、破解或规避许可。
- 仅在 ``../TOOLS.md`` 已确认本机 JEB 可用时调用；否则继续使用 `jadx`、`apktool`、Ghidra、IDA 或 radare2。
- 第三方 JEB MCP bridge 不是本包依赖。安装前必须按 `../ops/skill-supply-chain.md` 审阅源码、权限、网络行为和版本，再由用户明确确认注册。

### `apktool`

用于：

- 解包 APK
- 查看和修改 `AndroidManifest.xml`
- 查看和修改 smali
- 重建 APK

常用命令：

```bash
apktool d app.apk -o apktool_out
apktool b apktool_out -o rebuilt.apk
```

### `frida`

用于：

- 动态观察 Java 方法调用
- Hook native 导出函数
- 绕过 root 检测、证书校验、调试检测

常用命令：

```bash
frida-ps -U
frida -U -f com.example.app -l hook.js
frida-trace -U -f com.example.app -j '*!*certificate*'
```

### `adb`

用于：

- 设备连接
- 安装 APK
- 查看日志
- 拉取文件

常用命令：

```bash
adb devices
adb install -r app.apk
adb shell pm list packages
adb logcat
adb pull /data/local/tmp/file .
```

## 推荐工作流

### 1. Triage

先确定 APK 大致构成，不急着改包或 Hook。

建议动作：

1. 用 `jadx -d jadx_out app.apk` 导出 Java 代码
2. 用 `apktool d app.apk -o apktool_out` 导出 smali 和资源
3. 先看：
   - `AndroidManifest.xml`
   - 主 `package`
   - `application`、`activity`、`service`、`receiver`
   - `lib/` 目录里是否有 `.so`
4. Issue #65 威胁形态速查（授权样本/设备；详见 `../reverse-engineering/references/nonpe-format-cookbook.md` §7–8）：
   - 透明/隐藏图标（AU）：`aapt dump badging` + manifest theme/label/icon → `E-android-hidden-icon-manifest`
   - Magisk/脚本格机特征与远程 curl|sh（AR/AS）→ 特征与 URL 入证，**不执行**破坏命令
   - 持久化路径（AT）：`service.d` / `priv-app` 等 → `E-android-persistence`

### 2. Java 逻辑观察

优先从 `jadx_out` 读：

- `MainActivity`
- `Application`
- 登录、网络、加密、风控相关类
- 第三方 SDK 初始化类

常见关键词：

- `login`
- `sign`
- `encrypt`
- `cipher`
- `token`
- `root`
- `certificate`
- `trust`
- `okhttp`
- `retrofit`
- `webview`

如果 Java 代码可读，先在这里定位业务逻辑。

### 3. Smali 与资源层确认

当 `jadx` 结果不完整、混淆重、或需要实际 patch 时，切到 `apktool_out`：

- 看 `smali*/`
- 看 `res/values/strings.xml`
- 看 `AndroidManifest.xml`

优先 patch：

- `android:exported`
- 调试标记
- root 检测返回值
- 登录验证逻辑
- 证书校验分支

### 4. 重建与安装

修改后：

```bash
apktool b apktool_out -o rebuilt.apk
```

或者直接用脚本闭环：

```powershell
pwsh -File "<skill-root>\apk-reverse\scripts\rebuild-sign-install.ps1" -ProjectDir "apktool_out" -Install -Reinstall -DeviceSerial "127.0.0.1:7555"
```

说明：

- 本 skill 只保证 `apktool` 重建链路
- 若后续需要正式安装到设备，通常还需要签名流程
- 如果任务进入签名/对齐，补充 `apksigner` / `zipalign`

### 5. 动态 Hook

静态分析不足时，用 Frida：

- Hook 登录函数
- Hook `OkHttp` / `Retrofit` / `WebView` 关键点
- Hook `javax.crypto`、`MessageDigest`
- Hook root 检测函数
- Hook SSL pinning 逻辑

原则：

- 先 Hook Java 层，再看是否需要 native Hook
- 先打印参数与返回值，再决定是否主动修改返回值

建议：

- 简单一次性命令直接用 `frida-*`
- 需要稳定复用的注入流程优先走 `scripts/frida-run.ps1`

### 6. Native `.so` 分流

如果 APK 中包含关键 `.so`：

- 用 `apktool` 或 `jadx` 找到 `lib/**/*.so`
- 若只是导出符号、字符串、快速 triage，可用 `radare2`
- 若要长期深入分析、反编译、改名、类型恢复，用 `ida-reverse`

遇到这些信号要尽快切 native：

- Java 层只是 JNI 包装
- 核心签名逻辑不在 Java
- `System.loadLibrary()` 后关键逻辑消失
- 证书校验/风控在 `.so` 中

## 输出要求

最终至少说明：

- 入口组件与关键类
- 关键逻辑在 Java、smali 还是 `.so`
- 已确认的敏感点：登录、签名、root、SSL、WebView、JNI
- 如果做了 patch，说明改了什么
- 如果做了 Hook，说明 Hook 了哪个类/方法/导出函数

## 禁止事项

- 不要一开始就盲目改 smali
- 不要在没看 manifest 和主入口前就写 Hook
- 不要把 Java 反编译不完整直接等同于“逻辑不可分析”
- 不要在 `.so` 明显承载核心逻辑时继续死磕 Java 层

## 快速命令备忘

```bash
# 反编译 Java
jadx -d jadx_out app.apk

# 解包 APK
apktool d app.apk -o apktool_out

# 重建 APK
apktool b apktool_out -o rebuilt.apk

# 设备与进程
adb devices
frida-ps -U

# 启动并注入
frida -U -f com.example.app -l hook.js
```

---

## 路由上下文

**上游入口**: `SKILL.md`（总控）、`../routing.md`
**下游出口**:
- 核心逻辑在 `.so` → `ida-reverse/` 或 `radare2/`
- 需动态 Hook/验证 → `../reverse-engineering/tools-dynamic.md`（Frida 章节）
- 通用逆向方法论 → `SKILL.md`

**同级关联模块**: `reverse-engineering/`（.so 分析和 Frida 进阶用法）

---

## 按需自举（On-Demand Bootstrap）

本 skill 的入口脚本已接入统一自举系统。缺少工具时不会直接报错，也不会自动安装：只生成安装计划，获用户显式批准后才安装（`autoInstall=false`）。

### 自动化能力边界

| 工具 | 批准后可安装 | 安装方式 | 说明 |
|------|-----------|---------|------|
| jadx | ✓ | GitHub Release ZIP | 批准后下载解压到 `%USERPROFILE%\Tools\jadx\` |
| apktool | ✓ | GitHub Release JAR + wrapper | 批准后下载 jar 并生成 bat 到 `%USERPROFILE%\Tools\apktool\` |
| JEB Pro | ✗ | 用户手动安装并提供有效许可证 | 可选的 Android / ARM 交叉验证工具；第三方 MCP bridge 需单独审计 |
| frida / frida-ps | ✓ | pip install frida-tools | 需要 Python 已安装 |
| adb | ✓ | winget / fallback path | 批准后安装 Android Platform-Tools |
| zipalign | ✗ | 需手动安装 Android Build-Tools | `sdkmanager "build-tools;35.0.0"` |
| apksigner | ✗ | 需手动安装 Android Build-Tools | 同上 |

### 自举触发点

- `scripts/decode.ps1`：缺 jadx 或 apktool 时获批准后调用 `bootstrap-reverse.ps1`
- `scripts/rebuild-sign-install.ps1`：缺 adb 或 apktool 时获批准后调用 bootstrap
- `scripts/frida-run.ps1`：当前仍为手动检查（frida 通常已通过 pip 安装）

### 自举失败时

如果自动安装失败，脚本会抛出明确错误并附带手动安装链接。常见原因：
- 网络不通（GitHub API / PyPI 不可达）
- winget 不可用（Windows 版本过低）
- Java 未安装（apktool 依赖 JDK）

## 任务完成自检（声称完成前 MUST 通过）

- [ ] 我是否执行了工作流中的每一步（而不是只阅读）？
- [ ] 我是否走了**探测层四级递进**（`Resolve-ReverseToolSpec`）定位实际路径（而不是只跑一条 `Get-Command` 查空就报缺工具、也不是拿 `../TOOLS.md` 里的装法当路径猜）？
- [ ] 我是否产出了可复现证据（命令/脚本/截图/报告）？
- [ ] 我是否完成并回写了 RULES 要求的 Checklist 项？
- [ ] 若命中隐藏图标/格机/持久化线索：是否按 U–AV cookbook 记录 E-android-* Evidence？

---

## When NOT to use（近邻负例）

- iOS IPA / Mach-O / .app bundle 分析（不需要 APK 链路）→ `../mobile-reverse/SKILL.md`（Android+iOS 统一方法论）或 `../macos-reverse/SKILL.md`
- 目标是 APK 里的 `.so`，且 Java 层只是 JNI 包装、`System.loadLibrary` 后逻辑消失 → `../ida-reverse/` / `../radare2/`，不要继续死磕 Java 层
- 目标是普通 Windows PE / ELF，与 Android 无关 → `../reverse-engineering/references/assault-entry.md`
- `apktool d` 解不开（加固壳把 dex 加密了）→ `references/packer/` 链（`vmp-dex2c-detection.md` 先行），不要反复重跑 `apktool`
- 只是想知道某条 HTTP 请求的 sign/token 怎么在浏览器外复现（无 APK 主体任务）→ `../web-protocol-reverse/SKILL.md`
- 手头只有 `classes.dex` / smali、没有完整 APK → 仍是本 skill 范围，但**不要**用 `rebuild-sign-install.ps1` 声称"重打包完成"（无 APK 可重建）→ 停在 `apktool`+`jadx` 分析，成品形态改为"可安装 APK"不可达并在报告写明
- 设备都没连上（`adb devices` 为空）→ 先接设备（模拟器走 `references/emulator-lab.md`、真机开 USB 调试）；设备接上前只做静态，静态结论不许冒充运行时结论

## When to Pivot

信号与判据见 `../ops/skill-pivot-contract.md`。本技能去向：

| 触发证据 | 换到 |
|---|---|
| 关键逻辑确认在 `.so`（JNI 包装、签名/风控/证书校验在 native） | `../ida-reverse/`（长期深入）或 `../radare2/`（快速侦察） |
| `apktool` 报 unsupported / 解出的 dex 是空壳，Java 层无业务代码 | `references/packer/vmp-dex2c-detection.md` → 确认形态后再 `vmp-dump-trace-recovery.md` |
| 需求变成"iOS 也要一份"或目标其实是 IPA | `../mobile-reverse/SKILL.md` |
| 目标是浏览器端协议、APK 只是其中一环 | `../web-protocol-reverse/SKILL.md` |
| 重打包后功能不一致，根因在服务端校验/风控评分 | `../web-protocol-reverse/SKILL.md`（服务端依赖面） |
| APK 本身被判定为恶意样本（隐藏图标、格机脚本、持久化路径） | `../malware-analysis/SKILL.md` + `../reverse-engineering/references/nonpe-format-cookbook.md` §7–8 |

## 定义完成

本技能产出算"完成"的**外部可观测**条件（不许写形容词）：

- `<工作目录>/<包名>-rebuilt.apk` 真实存在（`rebuild-sign-install.ps1` 输出路径），且 `apksigner verify --print-certs` 返回 0
- 同一 APK 可安装：`adb install -r <rebuilt.apk>` 退出码 0，`adb shell pm list packages | findstr <包名>` 命中
- patch 逐条可对照：`diff -r apktool_out_orig/smali apktool_out/smali` 输出中每一处改动都对应报告里的一条 patch 意图，无未列出的差异
- 功能对照：受改动影响的流程在原包与重打包包上各跑一次（日志/Hook 输出各一份），行为一致；不一致则写"受限 + 具体原因"
- Frida Hook 结果落盘：Hook 脚本路径 + 运行日志（含捕获的参数/返回值样本），可复跑

## 输出契约

```
FACT:       <观察，带来源（命令 / 文件:行 / Evidence ID）>
HYPOTHESIS: <可测试断言 + confidence: high|medium|low>  （状态见 ../ops/binary-model.md）
QUESTION:   <当前最大不确定点>
NEXT:       <继续 | 换技能 | 停止（附成本判据）>
```

APK 实例常用写法：
- FACT: `E-apk-manifest` — `manifest-summary.ps1 -ManifestPath apktool_out/AndroidManifest.xml` 输出主入口 `com.example.app/.MainActivity`
- HYPOTHESIS: "sign 在 `com.example.crypto.Signer.nativeSign()` 里计算，Java 层无实现" — confidence: medium，证据 `E-jadx-001`（jadx 输出只有 native 声明）
- QUESTION: native 里是本地算法还是服务端下发？（决定是否需 `../web-protocol-reverse/SKILL.md`）

## 置信度词表

词表见 `../ops/confidence-vocabulary.md`。本技能特有判据：

- `confirmed`：同一结论在 **jadx 反编译的 Java 层** 与 **smali 层** 各看到一次（或 Java + Frida 运行时 Hook 各一次），且两处指向同一类/方法
- `low`：仅有 `jadx` 反编译结果、混淆或反编译失败导致 smali 未交叉核对；或只凭 `aapt dump badging` 的权限列表推断行为
