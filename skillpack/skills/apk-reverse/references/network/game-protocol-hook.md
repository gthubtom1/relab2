# 游戏协议 Hook 与封包分析

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/apk-reverse/techniques/05-network/01-game-protocol-hook.md`
> **什么时候用**：游戏用自定义协议（Protobuf/FlatBuffers/私有二进制），要 Hook 网络栈抓明文或分析协议结构。

## 适用信号

- Wireshark/tcpdump 抓到的 TCP/UDP 流是非标准格式
- 应用用了 OkHttp/Retrofit 或自定义 Socket
- 数据经加密后发送，需要在加密前/解密后下钩子
- 需要改造端口/封包层流量

## 前置

```powershell
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
$frida = (Resolve-ReverseToolSpec -Name 'frida').Command
$tshark = (Resolve-ReverseToolSpec -Name 'tshark').Command
& $tshark -v
```

## 步骤

### 1. Java 层 OkHttp Hook

```javascript
Java.perform(function () {
    // 同步调用
    var RealCall = Java.use("okhttp3.RealCall");
    RealCall.execute.implementation = function () {
        var req = this.request();
        console.log("[OkHttp] " + req.method() + " " + req.url().toString());
        var headers = req.headers();
        for (var i = 0; i < headers.size(); i++)
            console.log("  " + headers.name(i) + "=" + headers.value(i));
        var resp = this.execute();
        console.log("[OkHttp] code=" + resp.code());
        return resp;
    };

    // 异步调用（必须一起覆盖，否则漏掉大部分请求）
    RealCall.enqueue.implementation = function (callback) {
        console.log("[OkHttp ASYNC]", this.request().method(),
                    this.request().url().toString());
        return this.enqueue(callback);
    };
});
```

### 2. Response Body 抓取

```javascript
Java.perform(function () {
    var ResponseBody = Java.use("okhttp3.ResponseBody");
    ResponseBody.string.implementation = function () {
        var body = this.string();
        console.log("[Body]", body.substring(0, 500));
        return body;
    };
});
```

注意：`string()` 只能调一次（响应流已消费），重复 hook 要用 `bytes()` 或 `source()`。

### 3. Native 层 socket Hook

游戏常用 native socket 直接发包，绕过 Java 层：

```javascript
["send", "sendto", "write"].forEach(function (name) {
    var p = Module.findExportByName("libc.so", name);
    if (!p) return;
    Interceptor.attach(p, {
        onEnter: function (args) {
            var len = args[2].toInt32();
            if (len > 4 && len < 4096)      // 过滤噪声
                console.log("[" + name + "] len=" + len + "\n" +
                            hexdump(args[1], { length: Math.min(len, 256) }));
        }
    });
});

["recv", "recvfrom"].forEach(function (name) {
    var p = Module.findExportByName("libc.so", name);
    if (!p) return;
    Interceptor.attach(p, {
        onEnter: function (args) { this.buf = args[1]; },
        onLeave: function (ret) {
            var n = ret.toInt32();
            if (n > 0) console.log("[" + name + "] len=" + n + "\n" +
                                  hexdump(this.buf, { length: Math.min(n, 256) }));
        }
    });
});
```

### 4. 抓原始流量

```powershell
& $tshark -i any -f "tcp port 8000 or udp port 8000" -w capture.pcapng
& $tshark -r capture.pcapng -Y "tcp.len > 4" -T fields -e tcp.srcport -e tcp.len
```

### 5. Protobuf 协议逆向

```bash
# 有 .proto 定义
protoc --decode=GameMsg msg.proto < raw.bin
# 无 schema 尝试
protoc --decode_raw < raw.bin
```

## 常见自定义加密组合入口

| 形态 | 入口特征 |
|---|---|
| 纯 protobuf 无加密 | payload 直接是 protobuf wire format |
| protobuf + AES | 上层是 protobuf，字段是密文 |
| RC4 + Base64 | 长度 == 明文长度，尾部 `=` 补齐 |
| 私有二进制 | 需要从 `sendto` 的 buf 反推字段边界 |

## 判据

| 观察 | 结论 |
|---|---|
| `[OkHttp]` 日志出现完整 URL 和 header | Java 层明文已拿到 |
| `[sendto]`/`[recvfrom]` 有 dump 输出 | native 层明文已拿到 |
| `protoc --decode_raw` 能解出可读字段 | 是 protobuf |
| Java 和 native hook 都没有输出 | 数据走了 QUIC/gRPC 或自定义 native 加密，需找 `aioquic`/`grpc` |

**外部可观测的判据**：hook 日志里出现完整的请求行/响应体，或 hexdump 有非零内容 —— 不是「脚本加载成功」。

## 坑

- **`RealCall.execute` 与 `enqueue` 必须都 hook**，只 hook 同步会漏掉全部异步请求。
- **`ResponseBody.string()` 只能调一次**，第二次返回空。
- **OkHttp 版本不同类名不同**：OkHttp 3.x 是 `okhttp3.RealCall`，4.x 部分结构变了。
- **`sendto` 在 TLS 场景下 dump 的是密文**，先过 `../network/tls-pinning-unpinning.md`。
- **`recvfrom` 的数据在 `onLeave` 才能读**，长度取返回值。
- **QUIC (UDP 443) 不走 sendto**，要在 `nghttp3`/`quiche` 层 hook。
- **本机无 Android 设备**：全部 hook 部分**需真机/模拟器，本机未验证**；tshark 可在本机抓本机流量验证。

## 相关

- `tls-pinning-unpinning.md` —— 先过 pinning 才看得到明文
- `license-verification-bypass.md` —— 抓包后分析验证协议
- `../crypto/game-encryption-patterns.md` —— 抓到密文后定位算法
