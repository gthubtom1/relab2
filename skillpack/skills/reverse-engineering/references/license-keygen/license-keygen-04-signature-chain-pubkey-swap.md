# 签名链校验与公钥替换

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/pe-reverse/techniques/10-license-keygen/04-signature-chain-pubkey-swap.md`（已适配本机工具链）
> **什么时候用**：已判为 B 类 —— key/license 文件由厂商私钥签名，客户端内嵌公钥验签。
> 直接还原「签名算法」不可行（私钥不在客户端），**但攻击面在公钥本身**。
>
> ⚠️ 仅适用于你拥有或已获书面授权的软件。见 `README.md`。

## 适用信号

- 二进制内有大整数常量 / 32B Ed25519 公钥 / PGP 公钥环。
- 密码库导入：`bcrypt.dll`（`BCryptVerifySignature`）、OpenSSL、
  Java 侧 BouncyCastle（`bcpg` / `bcprov` jar）、自实现 `modPow` 例程。
- license 属性文本（`name=...`、`email=...` + 签名块）。
- **改 key 任一字符 → 校验失败，且错误文案是「签名无效」而非「格式错误」**。

## 前置

```powershell
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
$r2   = (Resolve-ReverseToolSpec -Name 'r2').Command
$floss = (Resolve-ReverseToolSpec -Name 'floss').Command
$py   = 'D:\EXE\python\python.exe'    # pefile
& $py -m pip show cryptography       # 公钥/私钥生成
```

★ 若 `cryptography` 未安装：`& 'D:\EXE\python\python.exe' -m pip install cryptography`。

## 步骤

### 1. 确认签名现场并定位公钥（三选一）

**（a）按调用链**：`license-keygen-02` 定位到校验函数后走验签分支，
看它把哪个缓冲区交给验签 API —— **该缓冲区通常就是公钥 blob 的起始地址**。

**（b）按特征常量**：
```
Ed25519 公钥  = 恰 32 字节
PGP 公钥环    = 以 99 02（public key packet）开头
RSA-2048      = 256 字节模数，且附近常见 01 00 01（e=0x10001）
```

```powershell
$r2 = (Resolve-ReverseToolSpec -Name 'r2').Command
& $floss .\target.exe | Select-String -Pattern 'BEGIN PGP PUBLIC KEY'
& $r2 -2 -qc '/x 9902; q' .\target.exe            # PGP 公钥环
& $r2 -2 -qc '/x 010001; q' .\target.exe          # RSA 指数
```

**（c）按反编译常量**：在 IDA/Ghidra 里搜定长大数组引用
（`DEF` 大数组 + 传给验签函数）。

★ **提取**：用 `pefile` 定位文件偏移并 dump 出原始字节。

```python
import pefile

pe = pefile.PE("target.exe")
for s in pe.sections:
    n = s.Name.rstrip(b"\x00").decode(errors="ignore")
    if n in (".rdata", ".data"):
        data = s.get_data()
        off = data.find(b"\x99\x02")
        if off != -1:
            rva = s.VirtualAddress + off
            fo  = s.PointerToRawData + off
            print("PGP ring at RVA=0x%x file_off=0x%x in %s" % (rva, fo, n))
            open("pubring.bin", "wb").write(data[off:off + 1195])
            break
```

### 2. 生成自持密钥对

```python
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey)
from cryptography.hazmat.primitives import serialization

priv = Ed25519PrivateKey.generate()
pub = priv.public_key().public_bytes(
    serialization.Encoding.Raw, serialization.PublicFormat.Raw)
print("pubkey (%d bytes) = %s" % (len(pub), pub.hex()))
priv_pem = priv.private_bytes(
    serialization.Encoding.PEM,
    serialization.PrivateFormat.PKCS8,
    serialization.NoEncryption())
open("priv.pem", "wb").write(priv_pem)
```

| 算法 | 生成方式 | 公钥长度 |
|---|---|---|
| Ed25519 | `Ed25519PrivateKey.generate()` | 32 B |
| RSA-2048 | `rsa.generate_private_key(65537, 2048)` | 256 B（模数） |
| PGP | OpenPGP 库生成主钥 + 签名子钥 | 主钥 + 子钥各一段 |

★ **公钥必须与目标同尺寸、同格式**才有直接替换价值。
DER SubjectPublicKeyInfo 和裸模数是两种不同布局，**长度相同不代表格式相同**。

### 3. 公钥替换 patch

```python
import shutil

def swap_pubkey(src: str, dst: str, offset: int, old_len: int,
                new_pub: bytes) -> int:
    """同尺寸替换。返回实际写入的字节数。"""
    assert len(new_pub) <= old_len, "same-size swap preferred"
    shutil.copyfile(src, dst)
    with open(dst, "r+b") as f:
        f.seek(offset)
        f.write(new_pub)
    return len(new_pub)
```

| 场景 | 替换方式 | 注意 |
|---|---|---|
| 原生 PE（`.data`/`.rdata` 内公钥数组） | 按偏移写新公钥 | 尺寸一致最稳；变长需 `VirtualAlloc` + 改指针 |
| Java jar（`License.class` 内数组） | 方法级字节码 patch | 只改 `getPublicKey()` 返回数组，**不要改类名/结构** |
| 多版本兼容 | patch 前先备份原始文件 | 回滚 = 换回备份 |

★ **务必在副本上操作**（`shutil.copyfile`）。改原始文件一旦没留备份就不可逆。

### 4. 签发合法授权

```python
# Ed25519
signature = priv.sign(props_text.encode())      # 64 字节
open("license.sig", "wb").write(signature)

# PGP 清文签名：按目标验签端规范做规范化
#   - 属性文本行序固定
#   - 行尾统一 (\r\n 或 \n)
#   - 无尾随空白
```

★★ **规范化是对齐的关键**。清文签名先规范化属性文本，
**任何字节差异（行尾、行序、尾随空白、编码 BOM）都会导致验签失败**。
**做法：先用「提取的公钥 + 官方 license 样本」复刻验证端行为，再生成自己的。**

### 5. 天花板：库级完整性自检

部分目标对**库文件**做 SHA-256 白名单（对 `bcpg.jar`、`bcprov.jar`、jna 等
整文件哈希比对）—— 直接改库文件会触发自检失败。三种绕过策略：

**策略 1：避开库，打宿主**（首选）
被白名单覆盖的是「整个库文件」，但**宿主程序自身文件往往不在白名单**
（自检代码运行后即放弃）→ 只 patch 宿主内的公钥数组/验签调用，库保持原样
→ 白名单哈希不变。

**策略 2：先改后算**
若宿主也在白名单，提取白名单计算逻辑（哈希表位置），patch 后同步更新表中对应哈希。

**策略 3：验签置空**
把验签函数入口改为恒真（`mov eax,1; ret`），**同时保留调用面**（不删符号）
—— 被反射调用的场景保持接口兼容。

```powershell
$rasm = (Resolve-ReverseToolSpec -Name 'rasm2').Command
& $rasm -a x86 -b 64 -s 0x0 "mov eax, 1"
# b801000000
& $rasm -a x86 -b 64 -s 0x0 "ret"
# c3
```

★ **「验签置空」的字节要经过反汇编回环验证**（见 `../disasm-jit-asm.md` 判据 3）。
`mov eax,1; ret` 是 6 字节 `b8 01 00 00 00 c3`。
**patch 前必须确认这 6 字节在指令边界上**（用 capstone 算 detourSize）。

### 6. 确认补丁生效（双向证据）

```
替换前：官方 key → 验签 TRUE
替换后：官方 key → 验签 FALSE   ← 证明公钥真的换了
        自签发 key → 验签 TRUE   ← 证明新公钥/私钥对匹配
```

★ **两个方向都要测**。只测「自签 key 通过」无法排除「本来任何 key 都通过」
（验签被置空了）；只测「官方 key 失败」无法排除「程序崩了」。

## 判据

1. ★★★ **公钥 blob 被成功提取且长度/格式与算法匹配**。判据形态：
   `pubkey (32 bytes) = <hex>` 且长度等于算法公钥标准长度。
   **长度不对 = 定位错了**，继续找。
2. ★★★ **双向验证通过**。判据形态：
   ```
   替换前：官方 key -> TRUE
   替换后：官方 key -> FALSE，自签 key -> TRUE
   ```
   **两行都要有。** 只测一个方向无法排除「验签被置空」或「程序崩了」。
3. ★★ **补丁后程序接受自签授权、功能解锁、重启保持**。判据形态：行为可观测
   （试用标记消失、功能菜单解锁）。**这是最终的验收判据**，
   前面的都只是中间证据。
4. **完整性自检未触发**。判据形态：patch 后程序正常启动、**没有**弹出完整性错误、
   `Procmon` 里没有异常的自校验失败事件。
   若用了策略 1（只改宿主），判据是「库文件哈希未变」。
5. **原始文件已备份**。判据形态：同目录下有 `*.orig` 副本，字节数与原文件一致。
   **没有备份的 patch 不可逆。**

## 坑

1. ★★★ **私钥不在客户端** —— 这就是为什么「还原签名算法」这条路在 B 类上走不通。
   客户端只有公钥，**验签是单向的**。攻击面只有公钥本身。
2. ★★★ **只测「自签 key 通过」无法排除验签被置空**。必须同时测「官方 key 失败」。
3. ★★★ **清文签名的字节级规范化**。行尾（`\r\n` vs `\n`）、行序、
   尾随空白、BOM —— 任何差异都导致验签失败。
   **先用官方样本复刻验证端的规范化行为。**
4. ★★ **公钥长度相同不代表格式相同**。DER SubjectPublicKeyInfo 和裸模数
   都是 256 字节但布局完全不同。先 dump 出前 16 字节看结构：
   `30 82 ...` = DER；`00 01 00 01` 开头 = 裸 RSA 模数。
5. ★★ **patch 宿主而非库**（策略 1）是绕开完整性白名单的首选。
   库文件被白名单覆盖的概率远高于宿主可执行文件。
6. ★ **变长替换需要改指针**。新公钥比旧的短，数组后面会多出残留字节 ——
   某些实现按固定长度读，会把残留字节也算进签名输入。
   **同尺寸替换最稳。**
7. ★ **Java class 文件有结构校验**。改常量池里的字节可能破坏 class 结构。
   **只改 `getPublicKey()` 返回的数组内容，不改类名/字段/方法数。**
8. **「验签置空」的 6 字节可能切在指令中间**。用 capstone 算 detourSize。
9. **本机无 MSVC**。需要编译工具时用 `D:\Tools\runtime\mingw64\bin\gcc.exe`。
10. **`cryptography` 包需要单独安装**，不保证在 `D:\EXE\python` 里预装。

## 相关

- `license-keygen-01-mechanism-classification.md` — 上一步：确认是 B 类
- `license-keygen-02-validation-function-location.md` — 定位验签调用点
- `license-keygen-05-keygen-verification-loop.md` — 下一步：实机验收
- `../code-patching.md` — patch 的字节级操作与指令边界判定
- `../disasm-jit-asm.md` — `mov eax,1; ret` 的字节生成与验证
- `../aob-signature-scan.md` — 给公钥/验签函数做特征码