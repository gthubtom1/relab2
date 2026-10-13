# 许可证机制分类与路线选择

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/pe-reverse/techniques/10-license-keygen/01-license-mechanism-classification.md`（已适配本机工具链）
> **什么时候用**：拿到一个软件，**动手之前的第一个决策不是「怎么破解」，而是「它属于哪类机制」**。
> 四类机制的成本从「半小时写个 keygen」到「keygen 不可行、必须换路径」不等。先分类，再选武器。
>
> 本地 / lab 目标按项目 `scope.md` 直接套用；先分类再选武器。

## 适用信号

- 激活窗口 / 注册码输入框（「输入注册码」「激活」「Thank you」弹窗语义）。
- license 文件（明文属性文本、PGP 清文签名、加密 BLOB）。
- 注册表 / 配置文件中的授权键（`Name` / `Email` / `Key` 三段式很常见）。
- 试用模式（`30-Day Trial`、剩余天数、功能锁定）。
- 激活时是否发包、有验证 URL。

## 前置

```powershell
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
$r2    = (Resolve-ReverseToolSpec -Name 'r2').Command
$floss = (Resolve-ReverseToolSpec -Name 'floss').Command
$py    = 'D:\EXE\python\python.exe'    # pefile
$pm    = 'D:\Tools\Sysinternals\Procmon64.exe'
```

## 步骤

### 1. ★ 先做断网实验（决定 A/B/C vs D）

**这一步决定后面所有工作是否有意义，成本 2 分钟。**

```
断网（拔网线 / 防火墙全出站 DROP）→ 运行激活流程
  ├─ 仍能激活成功        → 本地校验（A/B/C 之一）
  │                        网络请求可能只是格式校验或遥测
  └─ 失败 / 提示网络错误  → D 云端校验
                             keygen 基本不可行，转 06
```

★ **必须真的断网**，不是「我印象里好像要联网」。用 Windows 防火墙临时全出站规则：

```powershell
# 临时封出站（测完记得删）
New-NetFirewallRule -DisplayName "TEMP-OFFLINE-TEST" -Direction Outbound `
    -Action Block -All -Profile Any
# 测完删除
Remove-NetFirewallRule -DisplayName "TEMP-OFFLINE-TEST"
```

### 2. 四分类总览

```
许可证校验机制
├── A 纯本地算法校验   → 武器: keygen（还原公式）/ 逻辑 patch
├── B 签名链校验       → 武器: 公钥替换 + 自签名 / 逻辑 patch
├── C 自引用签名嵌入   → 武器: 迭代收敛（写入→抓取→回填）
└── D 云端校验         → 武器: Frida hook / 状态伪造 / 试用重置（无 keygen）
```

### 3. A 类：纯本地算法校验

校验函数完全在客户端：输入 key + 用户名/邮箱 → 输出布尔。

**特征**：
- 无签名算法现场（无大整数模幂、无密码库调用，纯位运算 / CRC / 自定义哈希）。
- key 中携带校验串（CRC 截断、校验位）与字段位（版本号、授权类型、期限）。
- 同一 key 在任意机器验证结果一致，或有确定性硬件绑定（注册表 `MachineGuid` 派生）。

**典型弱点**：**只有部分字段参与校验**（例如 192 字符中仅 19 字符被校验）、
校验值截断（25-bit CRC）、无 RSA 签名 → **可由邮箱/用户名完全推导 key**。

**路线** → `license-keygen-03-key-algorithm-recovery.md`

### 4. B 类：签名链校验

key 或 license 文件带**数字签名**（Ed25519 / RSA / DSA / PGP 清文签名），公钥内嵌在程序中。

**特征**：
- 二进制中存在公钥 blob（Ed25519 32B、RSA 模数 128~256B、PGP 公钥环）。
- 导入 / 调用密码库：`bcrypt.dll`、OpenSSL、BouncyCastle、自实现签名例程。
- **改 key 任一字符 → 校验失败**（签名覆盖全部内容，与 A 类的「部分校验」相反）。
- 验证流程固定：提取属性 → 验签 → 比对属性字段。

**路线** → `license-keygen-04-signature-chain-pubkey-swap.md`

### 5. C 类：自引用签名嵌入

key 的一部分由程序**启动时根据 key 自身切片重新计算**（自我引用）。

**特征**：
- **冷启动时重算授权状态**（不是仅在输入时校验一次）。
- key 中存在一段与「由 key 前部字段派生」等价的签名切片。
- 输入窗口校验（通过）与启动校验（真实判定）是**两套独立机制**。

**路线** → `license-keygen-07-self-ref-convergence.md`

**★ 定位到两个独立校验函数时立刻怀疑 C 类** —— 见 02 的「双机制信号」。

### 6. D 类：云端校验

key 有效性由厂商服务器判定。

**特征**：
- 激活流程必然发包，断网失败或降级。
- 客户端**没有可复刻的校验公式**（License Code 仅做格式面检查）。
- 离线激活证书为服务端私钥签名，客户端只有验签公钥。
- 授权状态存本地文件 → 可备份 / 修改 / 重置试用。

**路线** → `license-keygen-06-cloud-license-hook.md`

★ **注意**：若**公钥内嵌**且程序接受「离线激活证书」，则 B 类公钥替换仍可能可行
（见 04）——「云校验」并非自动等于「无解」，取决于是否存在可替换的本地信任锚。

### 7. 特征扫描（分类的证据）

```powershell
$floss = (Resolve-ReverseToolSpec -Name 'floss').Command
$r2    = (Resolve-ReverseToolSpec -Name 'r2').Command

# 激活相关信号
& $floss .\target.exe | Select-String -Pattern `
  'license|serial|regist|activat|trial|expire|invalid|thank you|unlock'

# 密码库导入（B 类信号）
& $r2 -2 -qc 'ii' .\target.exe | Select-String -Pattern `
  'bcrypt|ncrypt|CryptVerify|OpenSSL|BouncyCastle'

# URL / 端点（D 类信号）
& $floss .\target.exe | Select-String -Pattern 'https?://'
```

★ **`floss` 的解码通道要开**（默认）—— 激活相关字符串常在栈上构造，
裸 `strings` 看不到。

### 8. 判定决策树

```
激活时是否发包？
├─ 是 → 断网重试
│       ├─ 仍能激活  → A/B/C（本地为主，网络请求可能只是格式校验）
│       └─ 断网失败  → D 云端校验 → 转 06
└─ 否 → 本地校验
        ├─ key 含可解析字段（类型/期限/CRC）→ A → 03
        ├─ 二进制有公钥 blob / 密码库调用   → B → 04
        ├─ 冷启动重算 + key 自我引用        → C → 07
        └─ 无法命名 → 按 02 定位校验函数后再归类
```

## 判据

1. ★★★ **断网实验做过了，且结果记录在案**。判据形态：断网后激活成功的截图/输出，
   或防火墙规则存在的证据。**「我印象里好像要联网」不算判据。**
2. **分类有具体的代码/数据证据，不是感觉**。判据形态：
   - A：反编译里是位运算 + CRC，**没有**大整数模幂
   - B：导入表有 `bcrypt`/`OpenSSL`，或 `.rdata` 里有定长公钥 blob
   - C：找到**两个**独立校验函数（输入校验 + 冷启动校验）
   - D：断网失败 + 反编译里只有验签公钥、无本地公式
   **「说不清是哪类」说明证据不足，回到断网实验和特征扫描。**
3. ★ **「改 key 一个字符就失败」是区分 A 和 B 的关键实验**。
   判据形态：改动后错误信息不同 —— A 类通常报「格式错误 / 校验和不匹配」，
   B 类报「签名无效 / 验证失败」。**错误文案是分类的重要证据。**
4. **能说出「如果我判错了，下一步会浪费什么」**。判据形态：判成 A 但实际是 D →
   会花几天还原一个不存在的公式。**判类时把风险写出来。**

## 坑

1. ★★★ **跳过分类直接写 keygen**。这是最贵的弯路 —— 90% 的时间会花在
   还原一个根本不存在的本地公式上。先分类能省几小时到几天。
2. ★★★ **把 D 类（云端）当 A 类硬啃**。云端校验时客户端**没有可复刻的公式**，
   私钥不在客户端。硬啃的结果是「还原出一个永远返回 false 的本地检查」。
3. ★★ **「改一个字符就失败」不足以区分 A 和 B**。A 类如果校验覆盖全部字符，
   表现也一样。**必须看错误文案 + 反编译里有没有验签调用。**
4. ★★ **A 类与 C 类可能同时存在**：输入时校验（能过）+ 冷启动校验（真实判定）。
   只看输入窗口会得出「已经成功」的错觉。**必须重启验证**（见 05 的 L5）。
5. ★ **「有网络请求」不等于「云端校验」**。遥测、崩溃上报、字体 CDN 都会发包。
   **判据是断网后激活是否失败**，不是有没有流量。
6. **公钥 blob 的长度只是线索**。Ed25519 恰 32B、RSA-2048 模数 256B，
   但 `[u;128]` 编译的椭圆曲线公钥是 64B，其他曲线 32/48B。
   **结合导入表判断，不要只看长度。**
7. **`floss` 打开 decode 通道会显著变慢**。大样本先跑 `--only static` 快速筛，
   确定是许可证相关后再跑完整 decode。
8. **本机没有 MSVC**。要编译验证工具时用 `D:\Tools\runtime\mingw64\bin\gcc.exe`。

## 相关

- `license-keygen-02-validation-function-location.md` — 下一步：定位校验函数
- `license-keygen-03-key-algorithm-recovery.md` — A 类路线
- `license-keygen-04-signature-chain-pubkey-swap.md` — B 类路线
- `license-keygen-06-cloud-license-hook.md` — D 类路线
- `license-keygen-07-self-ref-convergence.md` — C 类路线
- `README.md` — 七篇的顺序与关系图
- `../procmon-patterns.md` — 断网实验的封出站做法与流量观察