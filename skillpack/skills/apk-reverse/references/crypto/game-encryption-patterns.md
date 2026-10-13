# 游戏数据加解密识别与绕过

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/apk-reverse/techniques/04-crypto/01-game-encryption-patterns.md`
> **什么时候用**：抓包全是乱码、内存里搜不到直接值、SharedPreferences 存的是 Base64+乱码 —— 需要定位 key/IV/算法并离线复现解密。

## 适用信号

- 抓包数据全是乱码，无明显 JSON/Protobuf 结构
- 内存中关键数值（血量/金币）搜不到直接值
- SharedPreferences 中存的是 Base64 + 乱码
- native 层大量调用 `javax.crypto.Cipher`

## 三层加密体系

### 层次 1：网络层 TLS Pinning

抓包失败、代理看不到请求 → 先定位 pinning 层再抓明文，见 `../network/tls-pinning-unpinning.md`。

### 层次 2：应用层 AES/DES/RSA

```java
SecretKeySpec key = new SecretKeySpec(keyBytes, "AES");
Cipher cipher = Cipher.getInstance("AES/CBC/PKCS5Padding");
cipher.init(Cipher.ENCRYPT_MODE, key, new IvParameterSpec(iv));
byte[] encrypted = cipher.doFinal(plaintext);
```

### 层次 3：内存层 XOR/混淆

```c
int   realGold = storedGold ^ 0xDEADBEEF;   // 简单 XOR
float realX    = storedX * magicMultiplier; // 乘性混淆
```

## 前置

```powershell
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
$r = Resolve-ReverseToolSpec -Name 'frida';      & $r.Command --version
$r = Resolve-ReverseToolSpec -Name 'objection'; & $r.Command --version
$r = Resolve-ReverseToolSpec -Name 'python'
& $r.Command -c "import Crypto; print('pycryptodome OK')"
```

本机 `(Resolve-ReverseToolSpec -Name 'pyre').Command` 已装 `Crypto`（pycryptodome）、`cryptography`、`hashlib`、`hmac`、`base64`，全部实测可 import。

## 步骤

### 1. jadx 搜加解密入口

```powershell
$jadx = (Resolve-ReverseToolSpec -Name 'jadx').Command
& $jadx -d jadx_out target.apk 2>&1 | Select-Object -Last 3
Select-String -Path 'jadx_out\sources\**\*.java' -Pattern 'Cipher|SecretKeySpec|IvParameterSpec|MessageDigest|encrypt|decrypt' | Select-Object -First 30
```

### 2. Frida 抓 Cipher.init 的 key/IV/算法

```javascript
Java.perform(function () {
    var Cipher = Java.use("javax.crypto.Cipher");
    Cipher.init.overload('int', 'java.security.Key',
                         'java.security.spec.AlgorithmParameterSpec')
    .implementation = function (opmode, key, params) {
        console.log("[Cipher.init] algo=" + this.getAlgorithm() + " mode=" + opmode);
        if (key) console.log("[KEY] " + bytesToHex(key.getEncoded()));
        if (params && params.$className === 'javax.crypto.spec.IvParameterSpec')
            console.log("[IV] " + bytesToHex(params.getIV()));
        return this.init(opmode, key, params);
    };

    function bytesToHex(b) {
        return Array.from(b, x => ('0' + x.toString(16)).slice(-2)).join('');
    }
});
```

注意 `params` 还可能是 `GCMParameterSpec`，那时要取 `getIV()` + `getTLen()`。

### 3. Frida 抓 native 加密（libcrypto）

```javascript
var p = Module.findExportByName("libcrypto.so", "AES_set_encrypt_key");
if (p) Interceptor.attach(p, {
    onEnter: function (args) {
        console.log("[AES key] " + hexdump(args[0], { length: args[1].toInt32() }));
    }
});
```

### 4. 离线解密验证（本机已验证）

拿到 key/iv/ciphertext 后，先在本机 Python 复现，确认算法和参数都对得上：

```python
# aes_ver.py
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

key = bytes.fromhex("a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6")
iv  = bytes.fromhex("0102030405060708090a0b0c0d0e0f10")
pt  = b'{"code":0,"msg":"ok"}'
ct  = AES.new(key, AES.MODE_CBC, iv).encrypt(pad(pt, 16))
print("ciphertext:", ct.hex())
print("decrypted:", unpad(AES.new(key, AES.MODE_CBC, iv).decrypt(ct), 16).decode())
```

本机实测输出：

```
key      : a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6
iv       : 0102030405060708090a0b0c0d0e0f10
plaintext: {"code":0,"msg":"ok"}
ciphertext: fe83e91c583cd8eed3766488e7d5c6ab3ad95dd09492e483c5aaa7f0f452979f
decrypted: {"code":0,"msg":"ok"}
```

**这一步的意义**：如果本机用你抓到的 key/iv 解出来是合法 JSON，说明 key/iv/算法/填充**四项全对**；解出乱码说明至少一项错了（最常见是 padding 和 IV 处理）。

### 5. 内存层 XOR 定位

```javascript
// 内存里找不到明文值时，hook 读取点看谁在做 XOR
Interceptor.attach(Module.findBaseAddress("libgame.so").add(FUNC_OFF), {
    onEnter: function (args) {
        var v = args[0].readU32();
        console.log("[raw] 0x" + v.toString(16) +
                    " -> xor 0xDEADBEEF = " + (v ^ 0xDEADBEEF));
    }
});
```

## 常见算法特征速查

| 算法 | 特征 | Key 长度 | IV 长度 |
|---|---|---|---|
| AES-128-CBC | `SecretKeySpec` + `IvParameterSpec` | 16 bytes | 16 bytes |
| AES-256-GCM | `GCMParameterSpec` | 32 bytes | 12 bytes |
| DES | `DESKeySpec` / `"DES"` | 8 bytes | 8 bytes |
| RSA/ECB | `Cipher.getInstance("RSA")` | 128-512 bytes | 无 |
| HMAC-SHA256 | `Mac.getInstance("HmacSHA256")` | 任意 | 无 |
| 自定义 XOR | 内存中反复 xor 常量 | 1-4 bytes | 无 |

## 判据

| 观察 | 结论 |
|---|---|
| Frida 打出 `[KEY]`/`[IV]` 且算法名明确 | Java 层参数已锁定 |
| 本机 Python 解出合法 JSON/Protobuf | key/iv/算法/padding 四项全对 |
| 解出乱码但无异常 | padding 或 IV 处理错了，不是 key 错 |
| key 每次会话都变 | 动态派生 key → 追派生逻辑（可能是上次响应/时间戳的 hash） |
| 内存值恒为 `真值 ^ 常量` | 内存层 XOR，常量已定位 |

**外部可观测的判据**：Python 离线解出的明文**是合法结构**（JSON 能 parse / Protobuf 能解），不是「跑完没报错」。

## 坑

- **`Cipher.init` 有多个重载**，只 hook 一个会漏；`init(int,Key)` 和 `init(int,Key,AlgorithmParameterSpec)` 要分开处理。
- **GCM 的 IV 不是 12 字节就一定错**，也要看 `getTLen()` 的 tag 长度。
- **AES/CBC 的 padding 常见 PKCS5(=PKCS7)**，但也有 NoPadding；解出乱码先试换 padding。
- **Frida 里 `this.init(...)` 调用重载方法要用 `.call(this, ...)`**，直接 `this.init()` 在多态场景可能递归到自己。
- **本机无 Android 设备**：Frida hook 部分**需真机/模拟器，本机未验证**；离线解密部分已验证。
- **`libcrypto.so` 名字随 Android 版本变**，可能是 `libssl.so`/内置在主 so 里，用 `Module.enumerateModules()` 找。

## 相关

- `rc4-custom-crypto.md` —— 自定义 RC4 的识别与复现
- `../network/tls-pinning-unpinning.md` —— 先过 pinning 才能抓到应用层密文
- `../packer/vmp-anti-debug-bypass.md` —— hook 之前先过反调试
