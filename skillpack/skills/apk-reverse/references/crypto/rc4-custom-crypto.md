# 自定义对称加密：RC4 与组合模式

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/apk-reverse/techniques/04-crypto/02-rc4-custom-crypto.md`
> **什么时候用**：数据是随机字节但长度与明文一致（流加密特征），代码里没有标准库调用，需要从算法层面识别 RC4 并逆推密钥。

## 适用信号

- 数据呈现随机字节但**长度与明文一致**（排除块加密：块加密密文会是 16 的倍数且有 padding）
- 代码中有 256 字节的 S-Box 初始化循环
- 字符串中出现 `rc4` / `ksa` / `prga` 字样
- 加密函数接收 key + data，**无 IV 参数**

## RC4 算法结构

```c
// 特征1: KSA（Key Scheduling Algorithm）—— 256 字节 S 盒初始化
void rc4_ksa(const char *key, int key_len, unsigned char *S) {
    for (int i = 0; i < 256; i++) S[i] = i;      // S 盒初值 0..255
    int j = 0;
    for (int i = 0; i < 256; i++) {
        j = (j + S[i] + key[i % key_len]) % 256;  // key 参与 j 计算
        unsigned char t = S[i]; S[i] = S[j]; S[j] = t;
    }
}

// 特征2: PRGA（Pseudo-Random Generation Algorithm）—— 逐字节 XOR
void rc4_crypt(unsigned char *S, const char *in, int len, char *out) {
    int i = 0, j = 0;
    for (int n = 0; n < len; n++) {
        i = (i + 1) % 256;
        j = (j + S[i]) % 256;
        unsigned char t = S[i]; S[i] = S[j]; S[j] = t;
        out[n] = in[n] ^ S[(S[i] + S[j]) % 256];
    }
}
```

**静态识别要点**：256 次循环 + 反复 swap 两个 S 元素 + 对数据做 XOR + 边界检查里出现常数 256。

## 前置

```powershell
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
$r = Resolve-ReverseToolSpec -Name 'frida';     & $r.Command --version
$r = Resolve-ReverseToolSpec -Name 'python'
& $r.Command -V
```

## 步骤

### 1. Python 复现（先验证算法本身，本机已验证）

```python
def rc4_crypt(data: bytes, key: bytes) -> bytes:
    S = list(range(256))
    j = 0
    for i in range(256):                       # KSA
        j = (j + S[i] + key[i % len(key)]) % 256
        S[i], S[j] = S[j], S[i]
    i = j = 0
    out = bytearray()
    for b in data:                             # PRGA
        i = (i + 1) % 256
        j = (j + S[i]) % 256
        S[i], S[j] = S[j], S[i]
        out.append(b ^ S[(S[i] + S[j]) % 256])
    return bytes(out)
```

**必须用标准测试向量验证**，否则「能跑通」不代表实现正确。本机实测：

```
ciphertext: 8553be70ed84a1c940a7df
roundtrip : b'hello world'
symmetric : True
KAT       : BBF316E8D940AF0AD3
expect    : BBF316E8D940AF0AD3
```

其中 `KAT` 是 RFC 6229 的已知答案测试：`key="Key"`、`plaintext="Plaintext"` → `BBF316E8D940AF0AD3`。**实现输出与该常量一致才算 RC4 写对了**；往返对称只证明自洽，不证明是 RC4。

### 2. 静态定位 RC4 函数

```powershell
$py = (Resolve-ReverseToolSpec -Name 'python').Command
& $py 'C:\relab2\skillpack\skills\apk-reverse\scripts\so-structure-audit.py' `
    libgame.so --strings 4 --grep rc4
```

或在 IDA/r2 里搜常数 `0x100`（256）紧邻 `cmp` 的循环。

### 3. Frida hook 抓 key 与数据

函数名未知时按地址 hook：

```javascript
var target = Module.findBaseAddress("libgame.so").add(RC4_FUNC_OFF);
Interceptor.attach(target, {
    onEnter: function (args) {
        this.data = args[0];            // 按实际 ABI 顺序调整
        this.key  = args[1];
        this.len  = args[2].toInt32();
        console.log("[RC4] key = " + hexdump(this.key, { length: 16 }));
        console.log("[RC4] len = " + this.len);
    },
    onLeave: function (ret) {
        console.log("[RC4] out = " +
            hexdump(this.data, { length: Math.min(this.len, 64) }));
    }
});
```

AArch64 下参数在 `x0/x1/x2`，`args[0..2]` 即对应；若目标函数被混淆，实参顺序会变，**先确认反编译的参数顺序再 hook**。

### 4. 确认密钥来源

| 来源 | 特征 |
|---|---|
| 硬编码 | key 在 so 的 `.rodata`，`strings` 或交叉引用能直接看到 |
| 服务器下发 | 每次会话不同，抓两次对比 |
| 派生（md5 等） | key == md5(某响应/时间戳)，用两次样本验证假设 |

## 常见加密组合

| 模式 | 特征 | 密钥来源 |
|---|---|---|
| `RC4(key)` | 单层流加密 | 硬编码 / 服务器下发 |
| `RC4(md5(response))` | 动态密钥 | 上次请求响应的 md5 |
| `RC4(key)` + Base64 | 加密后编码 | 硬编码 |
| `XOR(const)` + `RC4(key)` | 两层加密 | 固定 key |
| `AES-CBC(data, key1)` + `RC4(data, key2)` | 混合 | 双密钥 |

## 请求签名复现

```python
import hashlib, base64, json

def forge_sign(params: dict, secret: str) -> str:
    raw = "&".join(f"{k}={params[k]}" for k in sorted(params))
    raw += f"&secret={secret}"          # 或 appkey
    return hashlib.md5(raw.encode()).hexdigest()

def encrypt_params(params: dict, key: bytes) -> str:
    ct = rc4_crypt(json.dumps(params).encode(), key)
    return base64.b64encode(ct).decode()
```

## 判据

| 观察 | 结论 |
|---|---|
| 实现输出匹配 RFC 6229 KAT `BBF316E8D940AF0AD3` | RC4 实现正确 |
| 密文长度 == 明文长度且无块对齐 | 流加密（RC4/XOR 家族） |
| Python 用抓到的 key 解出可读 JSON/Protobuf | key 与算法均确认 |
| 同一 key 两次会话解出不同结果 | 密文带 nonce/时间戳，或 key 是动态派生 |

**外部可观测的判据**：KAT 常量比对 + 解出合法结构，不是「往返对称」就算对。

## 坑

- **往返对称 ≠ RC4 正确**：任何 XOR 流都能往返，必须用 KAT 常量。
- **S 盒每次调用都要重新初始化**：复用已初始化的 S 盒会得到错误结果。
- **KSA 里的 signed/unsigned 不影响结果**：`(j + S[i] + key[i % key_len]) % 256` 即使 key 按 `signed char` 提升为负值，取模后结果与 `unsigned char` 完全一致（本机用 key=`ff81c0` 实测 KSA 输出逐字节相同）。真正要注意的是**没有取模的场合**：魔改 RC4 里若有 `if (S[i] == key[j])` 这类比较，signed/unsigned 会改变分支走向。
- **Frida `args[]` 顺序**在 AArch64/Thumb 下都按 x0..xN，但被混淆的目标可能打乱实参。
- **本机无 Android 设备**：Frida hook 部分**需真机/模拟器，本机未验证**；Python 复现与 KAT 验证已实测。

## 相关

- `game-encryption-patterns.md` —— 标准库加密（AES/DES）的识别
- `../native/jni-register-natives-tracing.md` —— 自定义加密常在 native，先定位入口
