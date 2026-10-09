# TLS Pinning 定位与 Unpinning

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/apk-reverse/techniques/05-network/03-tls-pinning-unpinning.md`
> **什么时候用**：装了代理 CA 但 App 仍拒绝连接，logcat 报 `SSLHandshakeException` / `Certificate pinning failure`。

## 入口信号

```text
logcat: javax.net.ssl.SSLPeerUnverifiedException: Certificate pinning failure
logcat: Trust anchor for certification path not found
jadx:  okhttp3.CertificatePinner.check
jadx:  X509TrustManager.checkServerTrusted
native: SSL_get_verify_result / X509_verify_cert / SSL_set_custom_verify
抓包:   代理 CA 已安装但 App 仍拒绝连接
```

**第一轮目标不是「全局绕过」，而是确定校验落在哪一层**：Java OkHttp、系统 TrustManager、Cronet，还是 native TLS。

## 前置

```powershell
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
$frida = (Resolve-ReverseToolSpec -Name 'frida').Command
$objection = (Resolve-ReverseToolSpec -Name 'objection').Command
```

本技能包已有 `../frida-bypass-kit.md` 提供现成四合一绕过脚本，先试它。

## 步骤

### 1. 静态定位

```powershell
$jadx = (Resolve-ReverseToolSpec -Name 'jadx').Command
& $jadx -d jadx_out target.apk 2>&1 | Select-Object -Last 3
Select-String -Path 'jadx_out\sources\**\*.java' -Pattern 'CertificatePinner|checkServerTrusted|TrustManager|SSLSocketFactory|HostnameVerifier|Cronet|pin' |
  Select-Object -First 40

$apktool = (Resolve-ReverseToolSpec -Name 'apktool').Command
& $apktool d target.apk -o decoded -f
Select-String -Path 'decoded\**\*.xml' -Pattern 'network_security_config|usesCleartextTraffic'
```

Native 层继续看 SO：

```powershell
$py = (Resolve-ReverseToolSpec -Name 'python').Command
& $py 'C:\relab2\skillpack\skills\apk-reverse\scripts\so-structure-audit.py' `
    decoded\lib\arm64-v8a\*.so --strings 5 --grep 'cert|pin|sha256|ssl|boringssl|cronet'
```

### 2. Java 层打点脚本

```javascript
Java.perform(function () {
    const CertificatePinner = Java.use("okhttp3.CertificatePinner");
    CertificatePinner.check.overload("java.lang.String", "java.util.List")
    .implementation = function (host, peerCerts) {
        console.log("[pin] CertificatePinner.check host=" + host +
                    " certs=" + peerCerts.size());
        return;                                  // 直接放行
    };

    const TrustManagerImpl = Java.use("com.android.org.conscrypt.TrustManagerImpl");
    TrustManagerImpl.verifyChain.implementation = function (chain, anchors, host, ...) {
        console.log("[pin] TrustManagerImpl.verifyChain host=" + host);
        return chain;
    };
});
```

`verifyChain` 的参数个数随 Android 版本变化，用 `...` 兜住或按实际版本查签名。

### 3. Native 层打点脚本

```javascript
["SSL_get_verify_result", "X509_verify_cert", "SSL_set_custom_verify"].forEach(function (name) {
    const p = Module.findExportByName(null, name);
    if (!p) return;
    Interceptor.attach(p, {
        onEnter() { this.name = name; console.log("[tls] enter " + name); },
        onLeave(ret) {
            console.log("[tls] leave " + this.name + " ret=" + ret);
            if (this.name === "SSL_get_verify_result") ret.replace(0);   // X509_V_OK
            if (this.name === "X509_verify_cert") ret.replace(1);         // 成功
        }
    });
});
```

### 4. Cronet 特例

```javascript
Java.perform(function () {
    const Builder = Java.use("org.chromium.net.CronetEngine$Builder");
    Builder.enablePublicKeyPinningBypassForLocalTrustAnchors.implementation = function (v) {
        console.log("[cronet] force local trust anchor bypass");
        return this.enablePublicKeyPinningBypassForLocalTrustAnchors(true);
    };
});
```

### 5. network_security_config 路线

如果 pinning 配置在 XML 而不是代码里，可以直接改配置而不 hook：

```xml
<!-- decoded/res/xml/network_security_config.xml -->
<network-security-config>
    <base-config cleartextTrafficPermitted="true">
        <trust-anchors>
            <certificates src="system" />
            <certificates src="user" />   <!-- 信任用户 CA -->
        </trust-anchors>
    </base-config>
</network-security-config>
```

同时 `AndroidManifest.xml` 的 `<application>` 要有 `android:networkSecurityConfig="@xml/network_security_config"`。

## 路径分叉

| 入口 | 打点动作 | 下一跳 |
|---|---|---|
| OkHttp `CertificatePinner` | hook `check()` 返回 | 抓 HTTP API / license verify |
| 自定义 `TrustManager` | hook `checkServerTrusted()` | 提取请求签名参数 |
| `network_security_config` | 加 user CA 或改 smali | 重打包复验 |
| Cronet | hook Builder / native verify | HTTP/2/gRPC 流量解析 |
| Native OpenSSL/BoringSSL | hook `SSL_get_verify_result` | IDA 定位调用者 |

## 判据

| 观察 | 结论 |
|---|---|
| `[pin] CertificatePinner.check host=... certs=N` | OkHttp 层 pinning 已定位 |
| 代理里能看到原始请求/响应 | 绕过成功 |
| logcat 有 host 与证书链长度，App 不再握手退出 | Java 层绕过生效 |
| `[tls] enter X509_verify_cert` 有输出 | 校验在 native，需走 native 路线 |

**外部可观测的判据**：**代理里真的能看到请求** + logcat 不再报握手失败 —— 不是「hook 没抛异常」。

## 坑

- **objection 的 pinning 绕过是「插件」不是 CLI 子命令**：本机 `objection --help` 实测顶层 `Commands:` 只有 `api` / `patchapk` / `patchipa` / `run` / `signapk` / `start` / `version`，**没有 `sslpinning`**。正确用法是进交互控制台：
  ```bash
  objection -g com.target.app          # 进入控制台
  [+] sslpinning disable               # 控制台内命令
  ```
  或走 `patchapk` 路线（用 frida-gadget 改包重签，见 `../patch-repack/so-injection-repack.md`）。

- **`CertificatePinner.check` 有两个重载**（单个 `X509Certificate` 和 `List`），只 hook 列表版会漏。
- **`verifyChain` 参数个数随 Android 版本变**（有的版本有 ocsp/sct 参数），硬编码参数个数会注册失败。
- **Cronet 不走系统 TrustManager**，Java 层 hook 全部无效，必须走 Cronet 自己的 builder。
- **BoringSSL 的符号可能被 strip 或改名**，`Module.findExportByName` 返回 NULL 是常态，要按 so 逐个试。
- **`network_security_config` 改了要重打包重签**，且目标可能同时做完整性校验，见 `../patch-repack/signature-integrity-bypass.md`。
- **本机无 Android 设备**：全部 hook/代理部分**需真机/模拟器，本机未验证**。

## 相关

- `../frida-bypass-kit.md` —— 现成四合一绕过脚本
- `game-protocol-hook.md` —— 过了 pinning 之后抓明文
- `../patch-repack/signature-integrity-bypass.md` —— 改配置后重打包触发完整性检查
