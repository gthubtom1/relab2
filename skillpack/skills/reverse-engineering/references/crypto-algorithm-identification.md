# 算法盲识别：从字节特征反推加密/哈希/编码算法

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/general/techniques/crypto/01-algorithm-identification.md`
> **什么时候用**：拿到一段不认识的二进制 blob / `.rdata` / 内存 dump / 抓包里的密文段，**不跑代码、只看字节**，就要回答「这是 AES 还是 CRC-32 还是 Base64 还是 SHA-256」。

配套工具：`skills/reverse-engineering/scripts/algo_identify.py`（纯标准库，无需 pefile）。

## 适用信号

- 样本里有 **256 字节 / 1024 字节的整齐常量表**，不确定是什么
- 逆向到一段 `.rdata`，里面有「看着像密码常量」的东西
- 想快速判定「这玩意儿用的是 SHA-256 还是 MD5」
- 拿到了 4 字节/8 字节 magic，想确认是 zlib 还是 gzip
- 想知道某段密文是标准算法加密还是自定义 XOR
- 怀疑是白盒 AES（T-box 查找表），但拿不到 `.fbs`/`.proto`

## 前置

```powershell
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
$diec = (Resolve-ReverseToolSpec -Name 'diec').Command
$r2   = (Resolve-ReverseToolSpec -Name 'r2').Command
```

★ **解释器用 `D:\EXE\python\python.exe`**。`algo_identify.py` 只依赖标准库，任何解释器都能跑，
但本机统一用这一个，免得踩 `venv-re` 是空环境的坑。

```powershell
$py = 'D:\EXE\python\python.exe'
$ai = 'C:\relab2\skillpack\skills\reverse-engineering\scripts\algo_identify.py'
```

| 用途 | 工具 | 说明 |
|---|---|---|
| 常量指纹扫描 | `algo_identify.py` | 本篇主力，纯标准库 |
| 先确认有没有壳 | `diec` | 有壳的话常量被压缩，必须先脱壳再扫 |
| 节表与段信息 | `pefile`（在 `D:\EXE\python\python.exe`） | 段熵、raw offset |
| 常量命中后找引用 | `r2` | `axt @ <偏移>` 看谁引用了这张表 |

## 步骤

### 步骤 0：直接扫（90% 的情况到这里就结束）

```powershell
& $py $ai .\sample.exe
```

实测（自建样本 `crypto_probe.exe`，内嵌 AES 正/逆 S-box + MD5 IV + SHA-256 K +
ChaCha20 常量 + CRC-32 表，MinGW gcc `-O2` 编译）：

```
==============================================================================
algo_identify — crypto_probe.exe
size   : 55909 bytes
sha256 : 8d6f8933c663c72b1e168d54a21bc056fab5dc7aae31abdf494c446184029246
entropy: 4.6959  [#######################.................]  TEXT (plaintext, strings)
magic  : pe_mz
pe     : machine=0x8664 image_base=0x140000000
  .text     rva=0x1000     vsize=0x1ab0     raw=0x600      size=0x1c00     entropy=5.891
  .rdata    rva=0x4000     vsize=0xd38      raw=0x2400     size=0xe00      entropy=6.549
  ...
==============================================================================

命中 11 项（阈值 0.55）：

[1] AES_InvSbox（256 字节替换表）   置信度 0.99
    范围   : crypto_probe.exe!.rdata
    依据   : 命中 S-box 前 16 字节，且全 256 项通过双射 + 最大差分均匀度 <= 4 校验
    偏移   : 0x4560

[2] AES_Sbox（256 字节替换表）   置信度 0.99
    依据   : 命中 S-box 前 16 字节，且全 256 项通过双射 + 最大差分均匀度 <= 4 校验
    偏移   : 0x4660

[3] ChaCha20/Salsa20   置信度 0.98
    依据   : "expand 32-byte k" / "expand 16-byte k" 常量串出现
    偏移   : 0x4420

[4] CRC-32 (IEEE 802.3, reflected)   置信度 0.97
    依据   : 1024 字节反射查表（反射多项式 0xedb88320）；匹配 252/256 项（其余为手抄笔误，按近似命中）
    偏移   : 0x4020

[5] AES_Rijndael   置信度 0.95
    依据   : FIPS 197 AES S-box 前 16 字节；GF(2^8) 双射，最大差分均匀度 4/256；
             前缀 637c777bf26b6fc53001672bfed7ab76 精确命中
    偏移   : 0x4660

[7] SHA256   置信度 0.92
    依据   : SHA-256 前 8 个轮常数（质数立方根小数部分前 32-bit），共 64 个；
             前缀 982f8a4291443771cffbc0b5a5dbb5e9 精确命中
    偏移   : 0x4440

[8] MD5   置信度 0.90
    依据   : 初始向量 67452301 efcdab89 98badcfe 10325476 在数据中出现
    偏移   : 0x4540
```

**样本只嵌了 6 种常量（2 张 AES 表 + MD5 + SHA-256 + ChaCha + CRC），全部命中，无漏报。**

### 步骤 1：读懂「偏移」那一栏

★ **输出里的偏移是 RVA（相对映像基址的虚拟地址），不是文件偏移。**

工具在 PE 分支按节区扫描，`偏移` 栏报的是该节内 blob 的 RVA：

```
RVA = 文件偏移 - 该节 PointerToRawData + 该节 VirtualAddress
```

换算示范（本机实测，gcc -O0 自建样本 `.rdata` raw=0x2200 rva=0x4000）：

```
python find 得到 AES S-box 文件偏移 = 0x2200
RVA = 0x2200 - 0x2200 + 0x4000 = 0x4000     ← 工具输出就是 0x4000，完全一致
```

★★ **同一个工具在不同模式下语义不同**（这是个真实的坑）：

| 模式 | `偏移` 栏含义 | 用途 |
|------|---------------|------|
| 默认（PE 解析成功） | **RVA** | 喂给 IDA / r2 用虚拟地址定位 |
| `--no-pe` | **文件绝对偏移** | 喂给 `python open(f,'rb').seek(off)` |

**判据**：不管它报的是什么，你都必须用自己的方式独立验一次，见步骤 2。
想同时要 VA（带映像基址），自己加 `ImageBase`；本工具默认不给 VA，这对 PE 来说是正确选择。

### 步骤 2：★ 独立交叉验证（这一步不能省）

工具命中只是「像」。必须用一条**独立路径**确认。三个独立验法，任选其一：

```powershell
# 验法 A：python 直接在文件里 find 前缀，确认字节真的在那里
& $py -c "d=open(r'.\sample.exe','rb').read(); print(hex(d.find(bytes.fromhex('637c777bf26b6fc53001672bfed7ab76'))))"
```

实测（同一份 `crypto_probe.exe`，本机真实输出）：

```
0x2a20
```

> ★ 注意：**这个值必须和你自己样本的 `python find` 对得上**。
> 上面的 `0x2a20` 来自当时那份样本；换算 RVA 要用该样本自己的节区参数：
> `RVA = 文件偏移 - 该节 raw + 该节 rva`。
> 换样本就得重算 —— **文件偏移和 RVA 不是同一个数，别拿旧值对照新样本**。

```powershell
# 验法 B：r2 找引用，看哪段代码用了这张表
& $r2 -2 -qc '/x 637c777bf26b6fc53001672bfed7ab76' '.\sample.exe'
```

★★ **r2 的 `/x` 通配符是 `.` 不是 `?` / `??`**（本机实测：`/x 7ffe03..` 命中，
`/x 7ffe03??` 返回空）。**而且字节必须按文件里的实际顺序写**：

| 写法 | 含义 | 本机实测 |
|------|------|----------|
| `/x 7ffe0320` | 文件里确实是 `7f fe 03 20` | [OK] 命中 |
| `/x 2003fe7f` | 字节序写反 | [FAIL] 返回空 |

★★ **别在 `-qc` 的单引号串里塞 `; q`** —— `;` 会被 r2 当命令分隔符，把 `/x` 截断。
`-qc` 已经隐含执行完退出，要多条命令就分开给 `-c`：

```powershell
& $r2 -2 -qc '/x 637c777bf26b6fc53001672bfed7ab76' '.\sample.exe'   # 单条，推荐
& $r2 -2 -c '/x 637c777bf26b6fc53001672bfed7ab76' -c 'q' '.\sample.exe'  # 显式退出
```

```powershell
# 验法 C：在命中位置直接 dump 那块内存（把 $off 换成你验法 A 得到的文件偏移）
& $r2 -2 -qc "s $off; px 32" '.\sample.exe'
```

`637c777bf26b6fc5...` —— **这就是 FIPS 197 的 AES S-box 前 16 字节**，字节对上了。

### 步骤 3：分节区扫（定位到具体是哪个节）

工具已经自动按节区切分并给出「范围」列。想手动切：

```powershell
& $py $ai .\sample.exe --entropy   # 附带滑动窗口熵轮廓
& $py $ai .\sample.exe --json      # 机器可读
& $py $ai .\sample.exe --no-pe      # 当纯 blob 扫（内存 dump 用）
& $py $ai .\sample.exe --no-verify-aes   # 跳过 AES 256 项数学校验，快，但会漏报截断的表
& $py $ai .\sample.exe --min-score 0.7    # 提高阈值，只看高置信度
```

`--no-pe` 对**内存 dump** 是必须的 —— dump 里没有 DOS/NT 头，PE 解析会直接失败。

### 步骤 4：四层方法论（按侵入性递增）

| 层次 | 方法 | 需要 | 适用 |
|---|---|---|---|
| L1 静态特征 | S-box / 哈希常量 / CRC 表 / magic 匹配 | 纯二进制 | 标准算法（AES/SHA/CRC/zlib） |
| L2 统计特征 | 滑动窗口熵 | 纯二进制 | 区分 加密 vs 压缩 vs 明文 |
| L3 结构特征 | 白盒查找表扫描 | 纯二进制 | Chow WB-AES 等 |
| L4 差分/行为 | 已知明文 XOR、Kasiski | 多段密文 | 自定义 XOR / 流密码 |

工具实现了 L1/L2/L3。L4 见 `custom-obfuscation-reverse.md`。

### 步骤 5：CRC 查表的近似匹配（本轮实测修好的部分）

**原始做法是 `crc32_table in data` —— 要求 1024 字节全等。太脆。**

实测踩坑：自建样本里的 CRC-32 表是从网上抄的，**256 项里错了 4 项**：

```
mismatched entries: [38, 42, 168, 242]  count 4
  38  mine=d20d85fc ref=d20d85fd
  42  mine=dbbbbc9d ref=dbbbc9d6
  168 mine=d80d2b8a ref=d80d2bda
```

只要错 1 项，`tbl in data` 就永远匹配不上 → **明明有 CRC 表却零命中**。

改成**按项计数**：先取参考表，用锚点（表中第 64/128/192 项）做 `bytes.find` 快速定位，
只在命中的位置展开 256 项逐个比对，`>=252/256` 即算命中。实测输出：

```
[4] CRC-32 (IEEE 802.3, reflected)   置信度 0.97
    依据   : 1024 字节反射查表（反射多项式 0xedb88320）；匹配 252/256 项（其余为手抄笔误，按近似命中）
```

**性能**：改之前的朴素实现（每 16 字节槽全量比对 256 项）在 2.2 MB 文件上要 **19.2 秒**；
加锚点预筛后 **0.32 秒**，提速约 60 倍，且命中结果不变。

### 步骤 6：AES S-box 的数学校验（比前缀匹配可靠）

前缀命中可能是巧合，但**数学性质不会骗人**：

1. **双射**：256 项互不相同
2. **最大差分均匀度 ≤ 4**：对任意 Δx≠0，输出差分 `{S(x) ^ S(x^Δx)}` 的最大重数 ≤ 4

```python
def verify_aes_sbox(sbox: bytes) -> bool:
    if len(sbox) != 256 or len(set(sbox)) != 256:   # 性质 1：双射
        return False
    for dx in range(1, 256):                        # 性质 2：差分均匀度
        counts = {}
        for x in range(256):
            dy = sbox[x] ^ sbox[x ^ dx]
            counts[dy] = counts.get(dy, 0) + 1
        if max(counts.values()) > 4:
            return False
    return True
```

这是 AES S-box 与 AES 逆 S-box **都**满足的性质（逆 S-box 在 GF(2^8) 上同样是仿射 + 求逆）。
所以工具输出里 `[1] AES_InvSbox` 和 `[2] AES_Sbox` 置信度都是 0.99 —— 两者靠
**前缀**区分，靠**性质**确认「确实是 AES」。

### 步骤 7：哈希轮常数的立即数形态（源码化实现专用）

编译器把 `0x428a2f98` 编成 `mov eax, imm32`，**不落在 `.rdata`**，逐字节前缀匹配抓不到。
工具额外扫可执行节的小端 4 字节立即数。实测：

```
[9] SHA-256   置信度 0.90
    依据   : 源码化实现特征：命中 4/4 个32-bit 轮常数立即数
             ['0x428a2f98', '0x71374491', '0xb5c0fbcf', '0xe9b5dba5']
    偏移   : 0x4440, 0x4444, 0x4448, 0x444c
```

★ `-O2` 会把循环向量化 / 公共子表达式消除，64 个轮常数可能**只剩 1 个**被发射。
所以工具允许「只命中 1 个」也给结论，但置信度压到 0.70 并在依据里标注「弱信号」。

### 步骤 8：白盒查找表（弱信号，必须人工确认）

Chow WB-AES 把 9~10 轮的 T-box **连续排布**（40 张 1024 字节的表背靠背）。
所以判据是「同一 blob 内出现 **≥6 张等间距**、每张 256 项几乎全互异的表」，
而不是「有一张乱序表」。这样才不会把普通 `.rdata` 误判成白盒。

置信度只给 0.60/0.55。**看到白盒结论必须去代码里确认真的在做查表**，别直接采信。

## 判据

「某算法被使用」必须满足**两条独立证据**，缺一不可：

1. **指纹命中**：脚本 stdout 出现 `命中 N 项` 且条目里包含目标算法名。
   实测样本里 6 个常量全部出现在 `[1]`..`[11]` 中。
2. **独立交叉验证**：用**另一条路径**确认字节真的在文件里：
   - `python -c "d=open(f,'rb').read(); print(hex(d.find(bytes.fromhex('<前缀>'))))"` 返回非 -1，**且**
   - `r2 px 32 @ <该偏移>` 出来的字节与参考常量逐字节一致（实测 AES S-box
     `63 7c 77 7b f2 6b 6f c5 30 01 67 2b fe d7 ab 76`）。

只有第 1 条 = 工具的判断；只有第 2 条 = 你碰巧找到了字节。**两条齐了才算坐实。**

置信度的读法（实测值）：

| 置信度 | 含义 | 例子 |
|---|---|---|
| 0.99 | 数学性质验证通过 | `AES_Sbox（256 字节替换表）` |
| 0.97~0.98 | 近似全表匹配 / 精确常量串 | `CRC-32`、`ChaCha20/Salsa20` |
| 0.90~0.95 | 精确前缀命中 | `AES_Rijndael`、`SHA256`、`MD5` |
| 0.60~0.75 | 弱信号，**必须人工确认** | `expand 32-byte k`、`MD5 iv_le` |

**退出码**：`0` = 有命中，`1` = 无命中，`2` = 文件不存在/分析失败。
可用退出码做批处理门禁。

## 坑

1. ★ **`偏移` 栏的口径随模式变化，必须自己验一次**。默认（PE）模式报 **RVA**，
   `--no-pe` 模式报**文件绝对偏移** —— 同名不同义。
   换算：`RVA = 文件偏移 - 该节 PointerToRawData + 该节 VirtualAddress`。
   **别把工具的偏移直接喂给 `open(f,'rb').seek(off)`**，先 `python find` 拿真文件偏移。
   （本条此前写成「两者差 0x40、工具不可信」，那是误判：工具算的 RVA 是对的，
   已于 2026-10-10 实测复核纠正。）
2. ★ **CRC 表必须近似匹配，不能全等**。手抄的 CRC 表错 1 项就全表失配（实测错 4 项）。
   要求 `>=252/256` 项吻合，且要在依据里写明「匹配 N/256 项」。
3. ★ **`/x` 返回空先查字节序，不是查「r2 坏了」**。本机实测（2026-10-10 复现）：
   同一份含目标字节的样本上，`/x 7ffe0320`、`/x 637c777bf26b6fc53001672bfed7ab76`、
   `/x 6a006801` **全部正常命中**。唯一返回空的是 `/x 2003fe7f` ——
   因为文件里是 `7f fe 03 20`，而 `2003fe7f` 是**字节序写反**。
   通配符实测：`7ffe03..` 命中，`7ffe03??` 空。
   另注：`-qc '/x ...; q'` 里的 `;` 会把命令截断，参数串只放一条命令。
   **`/x` 是可用的 AOB 工具，别因为一次失败就换 yara/pefile。**
4. ★ **`-O2` 会把常量表折叠掉**。自建样本第一版把 `MD5_IV[0]^...` 这样的表达式直接
   写在 `main` 里，gcc 算出常量后**整张表被链接器丢弃**，脚本扫了 0 项：

   ```
   MD5_IV_le       -> NOT FOUND
   expand 32-byte k -> NOT FOUND
   ```

   修法：`__attribute__((noinline))` 包一层、或写到 `volatile`、
   或让索引混入运行时值（`i ^ argc`）。改完再 `find` 确认常量真的在文件里。
   **这是自建验证样本时的第一大坑 —— 样本里没有，不是工具没找到。**
5. **轮常数指纹必须按小端存**。规范写 `0x428a2f98`，x86 内存里是 `98 2f 8a 42`。
   照抄规范的大端十六进制串会一个字节都匹配不上。
6. **IV 只有 4 字节，误命中概率不低**。MD5 的 4 个 IV 字共 16 字节，随机数据偶然命中的
   概率约 `2^-128`（整组），但**单看某一个 32-bit 字**就是 `2^-32`。
   工具对此只给 0.70，并在依据里明说「需结合上下文」。
7. **SHA-3/Keccak 的初始状态全 0**，没法用固定向量检测，只能靠轮常数
   `0x0000000000000001` —— 这是**极弱信号**（8 字节 0 + 1 到处都是）。看到就当噪声。
8. **有壳先脱壳**。UPX/VMProtect 会把 `.rdata` 压成高熵段，指纹全扫不到。
   先 `upx -d` 或按 `unpack-and-memory-dump.md` 在内存里 dump。
9. **熵高不等于加密**。`.text` 5.8~6.5、`import table` 3.4 都是正常值；
   整节 > 7.2 才是可疑。样本整体熵 4.70 属于「含大量明文字符串的正常 PE」。
10. **`--no-verify-aes` 会漏报**。它跳过 256 项数学校验，只做前缀匹配 —— 被截断的表
    （比如只嵌了 128 项的紧凑实现）会漏。排查漏报时先去掉这个开关再跑一次。
11. **白盒结论永远要人工确认**。置信度 0.60/0.55 是设计上的低分，不是 bug。

## 相关

- `custom-obfuscation-reverse.md` — 标准算法识别不出来时的黑盒/灰盒/白盒/符号四层方法
- `prng-cracking.md` — 另一类「常量指纹」：PRNG 参数（LCG 的 a/c/m、MT19937）
- `unpack-and-memory-dump.md` — 有壳导致指纹扫不到时的前置
- `pe-header-parsing.md` — 节区表、raw/rva 换算（理解输出偏移口径的基础）
- `aob-signature-scan.md` — 把命中的常量做成特征码，跨版本复用
- `yara-rule-writing.md` — 把常量指纹固化成 YARA 规则做全量扫描
- `triage-first-30-min.md` — 把本篇排进 triage 流程的位置
- `../SKILL.md` — 总纲