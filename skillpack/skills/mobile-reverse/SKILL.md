---
name: mobile-reverse
description: Android/iOS 逆向与安全测试：APK/IPA 分析、jadx/apktool/smali、Frida/objection 插桩、SSL pinning 与 root/越狱绕过、OWASP MASTG。用于：分析 APK/IPA、绕证书校验与加固。
---
# Mobile Reverse Engineering

## ACTION REQUIRED（读完后立刻执行）

1. `NOW`: 读 `../field-journal/precedent-reverse.md` —— 本机做过多轮的常规操作清单，直接照做，不要停在犹豫上
2. `NOW`: **查经验卡** —— `python skillpack/skills/scripts/experience-card.py search "<你看到的症状>"`。
   命中就读那张卡的 `invariant` + `decision.action`，并**逐条对照** `scope.appliesWhen`
   与 `scope.stopsWhen`：少一条前提就停用；命中任一停止条件就停。
   历史卡**不替代**当前目标的实测证据。详见 `../experience-cards/INDEX.md`。
3. `NOW`: 确认当前任务是否命中本 skill 的适用范围
5. `NEXT`：**工具定位** —— 先载入探测层 `. <仓根>\skillpack\skills\scripts\lib\Bootstrap.ps1`（**优先用相对路径**：从本卡往上两级 `..\..\skills\scripts\lib\Bootstrap.ps1`；本机 `C:\relab2\...` 只是备选，**别把绝对路径写进新文档**），再 `Resolve-ReverseToolSpec -Name <id>`，按返回的 `Command` 调（完整路径，别依赖 cwd）。**`Get-Command` 返回空 ≠ 本机缺工具**（PATH 快照陷阱，见 `../references/env-selfcheck.md`）；四级探测全部 `Available=False` 才允许报缺。`../TOOLS.md` 是装法说明书，不是路径索引。禁止猜路径。
6. `NEXT`: 缺工具时调用 bootstrap，不要猜路径
7. `ACT`: 按本卡的「工作流」挑**当下适用**的那一条动手；不要停在确认状态

> Android + iOS 统一逆向方法论
> Frida / Objection / OWASP MSTG / SSL Pinning Bypass

## 适用场景

- Android APK 逆向与安全测试
- iOS IPA 逆向与安全测试
- 移动应用运行时动态插桩
- SSL Pinning / Root 检测 / 越狱检测绕过
- 移动端加密算法提取（AES/RSA/HMAC 密钥）
- 移动应用渗透测试（OWASP MASTG）
- 非 Root/越狱环境下的应用测试

## 四阶段工作流

### Phase 1: 信息收集

```text
Android：
□ APK 获取（Google Play / APKMirror / adb pull）
□ Manifest 分析: 权限、导出组件、Intent Filter、backup 标志
□ androguard: androguard analyze APK → 组件/权限/签名
□ APKLeaks: 硬编码 API Key / Token / Secret 扫描
□ 加固检测: 是否加壳（360/腾讯/梆梆/爱加密）

iOS：
□ IPA 获取（App Store / ipatool / Apple Configurator）
□ 解密 App Store 二进制: frida-ios-dump / Clutch
□ Info.plist 分析: ATS 配置、URL Scheme、Queries Schemes
□ class-dump: 导出 ObjC 类结构
□ 加固检测: 是否使用 Swift/ObjC 混淆
```

### Phase 2: 静态分析

```text
跨平台：
□ JADX-GUI: APK → Java 源码（Android）
□ Ghidra / Hopper: .so / Mach-O 反编译
□ radare2 / Cutter: CLI 快速侦察

Android 专项：
□ apktool d app.apk → smali 代码 + 资源
□ dex2jar: DEX → JAR → JD-GUI
□ smali/baksmali: Dalvik 字节码修改

iOS 专项：
□ class-dump: 导出 ObjC 头文件
□ Swift 符号恢复: swift-demangle
□ dsymutil: 调试符号提取
□ otool -L: 查看动态库依赖
□ jtool2: Mach-O 分析
```

### Phase 3: 动态分析

```text
Frida — 通用动态插桩：
□ frida-ps -U: 列出设备进程
□ frida-trace -U -i "open*" com.app: 追踪函数调用
□ 自定义 Hook 脚本: 修改参数/返回值、调用私有方法

Objection — Frida 增强层（无需写脚本）：
□ objection -g "com.app" explore
□ android root disable / ios jailbreak disable
□ android sslpinning disable / ios sslpinning disable
□ android keystore list / ios keychain dump
□ env / ls / sqlite connect

Frida Gadget（免 Root/越狱）：
□ 注入 frida-gadget.so / FridaGadget.dylib 到 APK/IPA
□ 重新签名 → 安装 → 无需设备权限即可 Hook
□ objection patchapk --source app.apk（全自动）
```

### Phase 4: 网络分析

```text
□ Burp Suite: 拦截 HTTP/HTTPS，修改请求/响应
□ mitmproxy: 脚本化代理（Python API）
□ Wireshark: PCAP 抓包分析
□ 证书安装: Android 用户证书 → 系统证书（Magisk + MoveCert）
□ SSL Pinning 绕过: Frida/Objection/Xposed/SSL Kill Switch 2
□ WebSocket / gRPC 流量分析
```

## 常见绕过速查

### SSL Pinning

```bash
# Objection（最简）
objection -g "com.app" explore
android sslpinning disable

# Frida 通用脚本
frida -U -l ssl_pinning_bypass.js -f com.app

# Xposed（Android）
TrustMeAlready 模块 → 全局禁用证书校验
```

### Root / 越狱检测

```bash
# Objection
android root disable
ios jailbreak disable

# Frida 自定义（多层检测）
Java.perform(function() {
    var RootBeer = Java.use("com.scottyab.rootbeer.RootBeer");
    RootBeer.isRooted.implementation = function() { return false; };
    // 额外绕过: Magisk su 检测、frida-server 检测、/proc/self/maps 检测
});
```

### 反调试

```bash
# Android
frida -U -l anti_debug_bypass.js -f com.app
# 绕过: ptrace(TracerPid)、/proc/self/status、isDebuggerConnected()

# iOS
# 绕过: PT_DENY_ATTACH、sysctl CTL_KERN/KERN_PROC/KERN_PROC_PID
frida -U -l ios_anti_debug.js -f com.app
```

## 移动端加密提取

```javascript
// Android — Hook Cipher.getInstance 获取密钥+算法
Java.perform(function() {
    var Cipher = Java.use("javax.crypto.Cipher");
    Cipher.getInstance.overload('java.lang.String').implementation = function(algo) {
        console.log("[Cipher] Algorithm: " + algo);
        return this.getInstance(algo);
    };
    Cipher.init.overload('int', 'java.security.Key').implementation = function(mode, key) {
        console.log("[Cipher] Key: " + bytesToHex(key.getEncoded()));
        return this.init(mode, key);
    };
});

// iOS — Hook CCCrypt
Interceptor.attach(Module.findExportByName("libcommonCrypto.dylib", "CCCrypt"), {
    onEnter: function(args) {
        console.log("CCCrypt op: " + args[0] + " alg: " + args[1]);
        console.log("Key: " + hexdump(args[3], { length: args[4].toInt32() }));
    }
});
```

## 工具链

| 工具 | 平台 | 用途 |
|------|:--:|------|
| JADX-GUI | A | Java 反编译 |
| apktool | A | APK 解包/重建 |
| Ghidra | A+I | 多架构反编译 |
| Hopper | I | iOS 专用反汇编 |
| Frida | A+I | 动态插桩 |
| Objection | A+I | Frida REPL 增强 |
| MobSF | A+I | 自动化 SAST+DAST |
| class-dump | I | ObjC 类导出 |
| frida-ios-dump | I | IPA 解密 |
| jtool2 | I | Mach-O 分析 |
| Burp Suite | A+I | HTTP 拦截 |
| mitmproxy | A+I | 脚本化代理 |

> A=Android, I=iOS

## 参考

- `references/frida-objection-deep.md` — Frida + Objection 深度用法
- `references/ios-reverse-guide.md` — iOS 逆向专项
- `references/anti-detection-bypass.md` — Root/越狱/反调试/SSL Pinning 绕过

## 任务完成自检（声称完成前 MUST 通过）

- [ ] 我是否执行了工作流中的每一步（而不是只阅读）？
- [ ] 我是否走了**探测层四级递进**（`Resolve-ReverseToolSpec`）定位实际路径（而不是只跑一条 `Get-Command` 查空就报缺工具、也不是拿 `../TOOLS.md` 里的装法当路径猜）？
- [ ] 我是否产出了可复现证据（命令/脚本/截图/报告）？
- [ ] 我是否完成并回写了 RULES 要求的 Checklist 项？

## 改编参考索引（open-reverselab `kb/ctf-website`）

> 下列 reference 改编自 `LING71671/open-reverselab` 的 `kb/ctf-website/`（GPL-3.0）。
> 每篇统一为「适用信号 / 前置 / 步骤 / 判据 / 坑 / 相关」+ 完整技术正文，
> 「前置」含**本机实测**的工具状态表——照抄原库裸命令前先看那张表。
> **能力域**：本文为技术能力说明，按项目 `scope.md` 直接套用。

### `references/web-bridge/` — WebView / Cordova / React Native / Flutter / Electron 桥接攻击面（2 篇）

- `references/web-bridge/01-webview-attacks.md`
- `references/web-bridge/02-cordova-reactnative.md`

### `references/` — 根目录



---

## When NOT to use（近邻负例）

- 目标只是 Android APK、不涉及 iOS，且需要 apktool 重建 / smali patch / adb 一条龙 → `../apk-reverse/SKILL.md`（Android 专项 CLI 规范比本卡更细）
- 目标是 iOS IPA 的 Mach-O / codesign / Hardened Runtime / TCC 深度分析 → `../macos-reverse/SKILL.md`
- 目标是 APK 里的 `.so`，Java 层只是 JNI 包装 → `../ida-reverse/` / `../radare2/`
- 目标是浏览器前端的 sign/token/cookie（没有 App 侧任务）→ `../js-reverse/`；要脱离浏览器复现 → `../web-protocol-reverse/`
- 目标是自研引擎游戏的封包/内存结构（不是通用移动 App 渗透）→ `../game-reverse/` + `../protocol-reverse/`
- 只做 Web 层渗透 / API 越权，原生 App 只是背景 → `../api-security/`
- 设备都没接上（无真机、无模拟器、`frida-ps -U` 为空）→ 先接设备（模拟器见 `../apk-reverse/references/emulator-lab.md`）；不要凭静态分析编造运行时结论

## When to Pivot

信号与判据见 `../ops/skill-pivot-contract.md`。本技能去向：

| 触发证据 | 换到 |
|---|---|
| 核心逻辑确认在 native `.so`（JNI 包装、`System.loadLibrary` 后关键逻辑消失） | `../ida-reverse/`（长期深入）或 `../radare2/`（快速侦察） |
| iOS 侧需要 codesign 公证 / Hardened Runtime / TCC / ObjC runtime 深度 | `../macos-reverse/SKILL.md` |
| Android 专项需要重打包 / smali patch / 模拟器一条龙 | `../apk-reverse/SKILL.md` |
| App 服务端依赖面成主任务（接口被 403/412/429、签名 challenge、需要 browser-free 采集器） | `../web-protocol-reverse/SKILL.md` |
| App 通信是自定义二进制帧 / protobuf / 有 PCAP 要还原状态机 | `../protocol-reverse/SKILL.md` |
| 判定为恶意样本（供应链投毒、隐藏图标、持久化 path） | `../malware-analysis/SKILL.md` + `../supply-chain-security/` |
| signing / 证书链本身是目标（不是绕过它） | `../identity-federation/SKILL.md` |

## 定义完成

本技能产出算"完成"的**外部可观测**条件（不许写形容词）：

- Phase 1–4 的产物各有一份落盘文件（manifest 摘要、静态结论、Hook 脚本 + 运行日志、抓包或请求记录），路径写进报告
- Frida / Objection 绕过结论可复现：Hook 脚本路径 + 在同一次会话内重跑的输出一致（SSL pinning 绕过需 ≥2 个不同请求被成功解密）
- 密钥提取类结论：算法名 + 模式 + padding + key/iv 字节（脱敏）+ 一条可独立运行的解密命令
- MASTG 检查项逐条标注 `pass` / `fail` / `not-tested` 三项之一，每项附证据 ID；`not-tested` 须写原因（工具缺 / 授权缺 / 环境不可达）
- 若未在真机执行：报告显式写"运行时结论未验证"，只保留静态可观察项

## 输出契约

```
FACT:       <观察，带来源（命令 / 文件:行 / Evidence ID）>
HYPOTHESIS: <可测试断言 + confidence: high|medium|low>  （状态见 ../ops/binary-model.md）
QUESTION:   <当前最大不确定点>
NEXT:       <继续 | 换技能 | 停止（附成本判据）>
```

## 置信度词表

词表见 `../ops/confidence-vocabulary.md`。本技能特有判据：

- `confirmed`：同一绕过/提取在 **两种独立手段** 下都成立（如 objection `android sslpinning disable` + 自写 Frida Hook 各抓到一次明文），且钩到的明文与服务端响应字节一致
- `low`：只跑了一条通用 bypass 脚本且未见应用行为变化就宣称"已绕过"；或仅凭 Frida 无报错推断成功（未验证捕获到的参数/返回值非空）
