# Web Crypto API 滥用

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/ctf-website/techniques/07-client/web-crypto-abuse.md`（GPL-3.0）。原 frontmatter 的 `mcp_tools` 映射已剔除——本技能包未挂载 `run_ctf_tool` / `http_probe`，改用本地工具链。
> **能力域**：本文为技术能力说明，按项目 `scope.md` 直接套用。
> **什么时候用**：命中「Web Crypto API / Math.random / PRNG / RSA」这类信号时，把本文当打点清单读；命中即进「步骤」，命中不了就换主题。

## 适用信号

- Web Crypto API
- Math.random
- PRNG
- RSA
- CryptoJS
- extractable
- V8 XorShift128
- JWK
- AES-GCM

## 前置

- 授权：目标在 scope 内（`case-init.ps1` 已 grant），测试时段与限速已约定。
- 工具定位走探测层，别猜路径：

```powershell
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
$r = Resolve-ReverseToolSpec -Name '<toolid>'   # 例：sqlmap / httpx / ffuf / curl / python
& $r.Command <参数>                                # 永远用完整路径，不依赖 cwd
```

- Python 解释器用探测层的 `python`。
- 本文脚本默认只读、只打点；扩大范围前先回到 scope 确认。

## 步骤

本文正文按下列小节顺序推进，**每一步的完整命令与脚本在「技术正文」对应小节里**（这类文档以代码体 + 表格为主，按小节读比按 bullet 读快）：

1. 工作流
2. 运行时 hook — 成功样本：console 输出 key format、algorithm、usages、iv/nonce、明密文样本。失败样本：hook 太晚，crypto 调用已完成；需要导航前注入。
3. 模式与 nonce 判定矩阵
4. JWK / key_ops 差分 — 判定：如果前端信任用户可控 JWK 的 key_ops/ext/alg，常能把“只能加密”的 key handle 扩成可导出或可 wrap 的材料。
5. Math.random token 预测 — 这段用于题面自写 PRNG 或时间戳种子模型。若目标是现代 V8 Math.random()，要收集连续输出并用专门状态恢复脚本；hook 的 Evidence 仍是相同的：连续 random、生成位置、token 拼接…
6. RSA/JWE 材料抽取

## 判据

判据必须是外部可观测的（状态码、响应字段、差分、落盘文件），不是「命令有输出」。

- **命中样本** — JWK/raw/passphrase/usage 可见
- **失败样本** — key 来自硬件或服务端不可见
- **命中样本** — 固定明文产生可识别模式
- **失败样本** — 每次随机 IV 且 key 不可控
- **命中样本** — token 可预测或 nonce 重复
- **失败样本** — 使用 `crypto.getRandomValues`
- **命中样本** — 非导出 key 被 wrap/decrypt/export
- **失败样本** — 浏览器拒绝 usage 组合
- **命中样本** — keystream/认证差异可利用
- **失败样本** — nonce 服务端生成且唯一
- **命中样本** — 弱 modulus 或公私钥混用
- **失败样本** — modulus 强且只用于公钥加密
- **命中样本** — 密文块重复
- **失败样本** — CBC/CTR/GCM 随 IV 改变

## 坑

- 探针命令在**未本机验证**时不要当成既定事实跑；先用探测层确认 `Available=True`。
- 噪声排除：先固定 baseline（同 URL 同 token 跑 3 次），再只改一个变量做差分。
- 不要把「状态码 200」当命中——WAF/缓存/软 404 都返回 200，命中判据要落到具体业务字段。

## 相关

- 见本技能 `../../SKILL.md` 的 references 索引。

## 技术正文

> 以下为原库正文（保留全部技术细节与脚本），仅移除原 `MCP 工具映射` 章节并重写跨文档链接。

Web Crypto 题目优先看“谁生成 key、谁持有 key、key_ops 允许什么、nonce/iv 是否复用、密文 oracle 是否可控”。标准 AES/RSA 本身通常不是突破口，突破口在前端封装和状态管理。

## 输入信号

| 信号 | 立即动作 | 命中样本 | 失败样本 |
|---|---|---|---|
| `crypto.subtle.importKey/generateKey/deriveKey` | hook 参数与返回 key handle | JWK/raw/passphrase/usage 可见 | key 来自硬件或服务端不可见 |
| `CryptoJS.AES.encrypt` | 测 ECB/CBC/CTR、salt、passphrase | 固定明文产生可识别模式 | 每次随机 IV 且 key 不可控 |
| `Math.random()` 生成 token/key/nonce | 收集连续输出和种子线索 | token 可预测或 nonce 重复 | 使用 `crypto.getRandomValues` |
| JWK 中 `extractable/key_ops` 可控 | 改 key_ops/import 参数 | 非导出 key 被 wrap/decrypt/export | 浏览器拒绝 usage 组合 |
| AES-GCM/CTR nonce 可控 | 重放相同 nonce 明文对 | keystream/认证差异可利用 | nonce 服务端生成且唯一 |
| JWE/RSA modulus 泄露 | 提取 `n/e/kid/x5c` | 弱 modulus 或公私钥混用 | modulus 强且只用于公钥加密 |

## 工作流

```text
定位 crypto 调用
  → hook import/generate/derive/encrypt/decrypt/sign/verify
  → 抽 key 参数、usage、iv/nonce、明密文样本
  → 跑模式/PRNG/JWK/nonce 差分
  → 复现加解密或签名 oracle
  → 转 JWT、签名、支付或客户端状态链
```

## 0. 运行时 hook

```javascript
(() => {
  const enc = x => {
    if (x instanceof ArrayBuffer) return Array.from(new Uint8Array(x)).map(b=>b.toString(16).padStart(2,"0")).join("");
    if (ArrayBuffer.isView(x)) return Array.from(new Uint8Array(x.buffer, x.byteOffset, x.byteLength)).map(b=>b.toString(16).padStart(2,"0")).join("");
    try { return JSON.stringify(x); } catch { return String(x); }
  };
  for (const name of ["importKey","generateKey","deriveKey","encrypt","decrypt","sign","verify","wrapKey","unwrapKey"]) {
    const orig = crypto.subtle[name].bind(crypto.subtle);
    crypto.subtle[name] = async (...args) => {
      console.log("[subtle:req]", name, args.map(enc));
      const r = await orig(...args);
      console.log("[subtle:ret]", name, r && (r.type || r.constructor.name), r && r.algorithm, r && r.usages);
      return r;
    };
  }
  const oldRandom = Math.random;
  Math.random = function() {
    const v = oldRandom();
    console.log("[math.random]", v);
    return v;
  };
})();
```

成功样本：console 输出 key format、algorithm、usages、iv/nonce、明密文样本。失败样本：hook 太晚，crypto 调用已完成；需要导航前注入。

## 1. 模式与 nonce 判定矩阵

| 变体 | 操作 | 命中样本 | 失败样本 |
|---|---|---|---|
| ECB 检测 | 三个相同明文块 | 密文块重复 | CBC/CTR/GCM 随 IV 改变 |
| CBC 固定 IV | 同明文重复加密 | 第一块密文相同 | IV 每次随机 |
| CTR/GCM nonce 复用 | 同 nonce 加密两段明文 | XOR 可消去 keystream | nonce 唯一 |
| passphrase KDF | 改 salt/iteration | key 可重算 | PBKDF 参数不可见 |
| key_ops 扩张 | JWK 加 `wrapKey/decrypt` | 能 wrap/export raw key | importKey 拒绝 |

```python
#!/usr/bin/env python3
import argparse
import base64
from collections import Counter

def chunks(b, n=16):
    return [b[i:i+n] for i in range(0, len(b), n)]

def decode(s):
    for fn in (bytes.fromhex, lambda x: base64.b64decode(x + "=" * (-len(x) % 4))):
        try:
            return fn(s)
        except Exception:
            pass
    raise SystemExit("cipher must be hex or base64")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cipher")
    ap.add_argument("--block", type=int, default=16)
    args = ap.parse_args()
    b = decode(args.cipher.strip())
    c = chunks(b, args.block)
    dup = [k.hex() for k, v in Counter(c).items() if v > 1]
    print({"blocks": len(c), "duplicate_blocks": dup, "guess": "ECB-like" if dup else "CBC/CTR/GCM/stream-like"})

if __name__ == "__main__":
    main()
```

## 2. JWK / key_ops 差分

```javascript
async function jwkDiff(jwk) {
  const variants = [
    {...jwk, ext: true, key_ops: ["encrypt","decrypt","wrapKey","unwrapKey"]},
    {...jwk, extractable: true, key_ops: ["encrypt","decrypt","sign","verify"]},
    {...jwk, alg: "A256GCM", key_ops: ["encrypt","decrypt"]},
  ];
  for (const v of variants) {
    try {
      const k = await crypto.subtle.importKey("jwk", v, {name:"AES-GCM"}, true, v.key_ops || ["encrypt"]);
      console.log("[jwk-hit]", v, k.usages, await crypto.subtle.exportKey("jwk", k));
    } catch (e) {
      console.log("[jwk-miss]", v, String(e));
    }
  }
}
```

判定：如果前端信任用户可控 JWK 的 `key_ops/ext/alg`，常能把“只能加密”的 key handle 扩成可导出或可 wrap 的材料。

## 3. Math.random token 预测

```python
#!/usr/bin/env python3
import argparse
import random
import string

ALPH = string.ascii_letters + string.digits

def gen(seed, n, length):
    r = random.Random(seed)
    for _ in range(n):
        yield "".join(r.choice(ALPH) for _ in range(length))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--known")
    ap.add_argument("--start", type=int, required=True)
    ap.add_argument("--end", type=int, required=True)
    ap.add_argument("--length", type=int, default=16)
    args = ap.parse_args()
    for seed in range(args.start, args.end + 1):
        toks = list(gen(seed, 3, args.length))
        if not args.known or args.known in toks:
            print(seed, toks)

if __name__ == "__main__":
    main()
```

这段用于题面自写 PRNG 或时间戳种子模型。若目标是现代 V8 `Math.random()`，要收集连续输出并用专门状态恢复脚本；hook 的 Evidence 仍是相同的：连续 random、生成位置、token 拼接规则。

## 4. RSA/JWE 材料抽取

```python
#!/usr/bin/env python3
import argparse
import base64
import json

def b64json(part):
    part += "=" * (-len(part) % 4)
    return json.loads(base64.urlsafe_b64decode(part.encode()))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("jwe_or_jwk")
    args = ap.parse_args()
    s = args.jwe_or_jwk
    if "." in s:
        h = b64json(s.split(".", 1)[0])
        print(json.dumps({"header": h, "kid": h.get("kid"), "alg": h.get("alg"), "enc": h.get("enc"), "jku": h.get("jku")}, indent=2))
    else:
        jwk = json.loads(s)
        print(json.dumps({k: jwk.get(k) for k in ("kty","kid","alg","use","key_ops","n","e","x","y","k")}, indent=2))

if __name__ == "__main__":
    main()
```

## 攻击链

```text
前端 crypto hook
  → 抽 key/iv/nonce/plain/cipher
  → 模式、PRNG、JWK、nonce 单变量差分
  → 复现 encrypt/decrypt/sign oracle
  → 伪造 token/signature 或解出 flag payload
```

## Evidence

| 项 | 记录内容 |
|---|---|
| 调用点 | JS 文件、函数名、hook 日志、调用顺序 |
| key 材料 | format、algorithm、usages、extractable、JWK/raw/derived 参数 |
| 明密文样本 | plaintext、ciphertext、iv/nonce/tag、编码方式 |
| 判定结果 | ECB/CBC/CTR/GCM、nonce 是否复用、PRNG 是否可预测 |
| 成功样本 | 复现解密、伪造签名/token、预测下一 token、导出 raw key |
| 失败样本 | hook 未覆盖、nonce 唯一、key 不可见、导入 schema 拒绝 |
| 下一跳 | JWT 转 `02-auth/jwt`；签名转 `13-signature`；支付 token 转 `12-payment` |
