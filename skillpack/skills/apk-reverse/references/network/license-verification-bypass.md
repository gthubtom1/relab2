# 在线验证系统分析与绕过

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/apk-reverse/techniques/05-network/02-license-verification-bypass.md`
> **什么时候用**：APK 启动时做在线许可证验证，未通过就闪退或锁功能。

## 适用信号

- 应用启动后弹窗或闪退
- 抓包看到启动时向特定域名发 API 请求
- jadx 里搜 `verify` / `license` / `activate` / `check`
- native 里有 `httppost` / `curl_easy_perform` 调用

## 三种常见验证模式

### 模式 1：API 签名验证（微验类）

```c
/* 流程: 收集设备信息 → RC4 加密 → POST API → 解析响应 */
char *appkey = "APPKEY";
char *rc4key = "RC4_KEY";
char *host   = "verify.example.com";

int verify(void) {
    int timestamp = (int)time(NULL);
    sprintf(payload, "%d%s%s", timestamp, appkey, extra);
    char *encrypted = Encrypt(payload, rc4key);      /* 常是 RC4 */
    char *response  = httppost(host, "api/?id=verify", url_params);
    char *plain     = Decrypt(response, rc4key);
    cJSON *json = cJSON_Parse(plain);
    return cJSON_GetObjectItem(json, "code")->valueint == 0;   /* 0=通过 */
}
```

绕过点：
- hosts / DNS 劫持 `verify.example.com` → 自建服务器返回 `{"code":0}`
- Frida hook `httppost` 返回伪造响应
- patch `appkey` + `rc4key` 为已知有效值

### 模式 2：包名/渠道/文件存在性验证

```c
/* 流程: 检查是否安装某应用 → 检查缓存文件 → 放行或跳转 */
int check_installed(void) {
    const char *pkgs[] = {
        "org.telegram.messenger",
        "org.telegram.messenger.web",
        /* ... 已知客户端包名 ... */
    };
    for (int i = 0; pkgs[i]; i++) {
        if (package_installed(pkgs[i])) {
            char path[1024];
            sprintf(path, "/data/data/%s/cache/%s", pkgs[i], CACHE_NAME);
            if (access(path, F_OK) == 0) return 1;      /* 验证通过 */
            am_start(pkgs[i], JOIN_URL);                /* 未加入则跳转 */
        }
    }
    return 0;
}
```

绕过点：
- 创建对应缓存文件
- Frida hook `access` 返回 0
- patch `check_installed` 恒返回 1

### 模式 3：网络连通性验证

```c
int check_network(void) {
    CURL *curl = curl_easy_init();
    curl_easy_setopt(curl, CURLOPT_URL, "http://www.baidu.com");
    CURLcode res = curl_easy_perform(curl);
    curl_easy_cleanup(curl);
    return (res == CURLE_OK);
}
```

## Frida 通用绕过模板

```javascript
// 1. hook httppost（API 验证）
var httppost = Module.findExportByName(null, "httppost");
if (httppost) Interceptor.attach(httppost, {
    onLeave: function (ret) {
        ret.replace(Memory.allocUtf8String('{"code":0,"msg":"ok"}'));
    }
});

// 2. hook access（文件存在性验证）
var accessPtr = Module.findExportByName(null, "access");
Interceptor.attach(accessPtr, {
    onEnter: function (args) {
        this.path = args[0].readCString();          // arm64: x0
    },
    onLeave: function (ret) {
        if (this.path && this.path.indexOf("cache/") >= 0) ret.replace(0);
    }
});

// 3. hook system（包名检查）
var systemPtr = Module.findExportByName(null, "system");
Interceptor.attach(systemPtr, {
    onEnter: function (args) {
        var cmd = args[0].readCString();
        if (cmd && cmd.indexOf("pm list packages") >= 0)
            args[0] = Memory.allocUtf8String("echo 'package:org.telegram.messenger'");
    }
});
```

AArch64 下第 1 个参数在 `x0`，`args[0]` 即对应；x86 是 `rdi`，Frida 已做统一抽象。

## 前置

```powershell
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
$frida = (Resolve-ReverseToolSpec -Name 'frida').Command
$adb = (Resolve-ReverseToolSpec -Name 'adb').Command
& $adb logcat -d | Select-String 'verify|license|fail|error'
```

## 判据

| 观察 | 结论 |
|---|---|
| logcat 有验证失败关键字 + 抓包有对应请求 | 验证点已定位 |
| `[httppost] 返回伪造 {"code":0}` 且应用不闪退 | 绕过生效 |
| 杀守护进程后主进程不再自检退出 | ptrace 守护已处理 |
| 改 hosts 后请求指向自建服务器并返回预期 JSON | 服务器侧绕过生效 |

**外部可观测的判据**：**应用不再闪退且目标功能可用** —— 不是「hook 脚本跑完没报错」。

## 坑

- **`httppost` 在 `libmain.so` 而非 libc**，要按模块逐个 `Module.enumerateExports()` 找。
- **`ret.replace()` 必须在 `onLeave`**，`onEnter` 里改无效。
- **伪造响应的 JSON 结构要匹配真实响应**，应用可能校验字段数量或长度。
- **`access` hook 会影响目标全部文件访问**，务必按路径过滤，否则应用会误判文件存在。
- **`system()` hook 要注意它可能在多线程被调用**，改 `args[0]` 后原命令不会执行。
- **本机无 Android 设备**：全部 hook 部分**需真机/模拟器，本机未验证**。

## 相关

- `../crypto/rc4-custom-crypto.md` —— 验证常用 RC4，先复现算法
- `tls-pinning-unpinning.md` —— 代理抓不到请求时先过 pinning
- `../patch-repack/signature-integrity-bypass.md` —— 改包后触发完整性检查
