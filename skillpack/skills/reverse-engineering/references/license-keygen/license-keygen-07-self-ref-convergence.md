# 自引用签名与迭代收敛

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/pe-reverse/techniques/10-license-keygen/07-self-referencing-signature-convergence.md`（已适配本机工具链）
> **什么时候用**：目标存在**两套独立授权判定** —— 输入窗口校验（弹 "Thank you"）
> 与冷启动自引用校验（真实授权判定）。
> 表面看必须还原签名算法，但这类机制存在一个捷径：**对切片位置的局部不变性**。
>
> 本地 / lab 目标按项目 `scope.md` 直接套用。
>
> ★ **本篇的 Frida 脚本未在本机实跑验证**。判据按「命令形态已验证，参数需按样本调整」处理。

## 适用信号

- 找到**两个**独立校验函数（输入校验 + 冷启动校验）—— 见 `license-keygen-02` 的双机制信号。
- 输入窗口校验通过，但**重启后仍是试用状态**。
- 冷启动时程序根据 key 自身某切片重新计算签名串，
  要求「程序算的切片 == key 里的切片」。
- key 中存在一段与「由 key 前部字段派生」等价的签名切片。

## 前置

```powershell
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
$r2    = (Resolve-ReverseToolSpec -Name 'r2').Command
$cdb   = (Resolve-ReverseToolSpec -Name 'cdbX64').Command
$frida = 'D:\EXE\python\Scripts\frida.exe'
$py    = 'D:\EXE\python\python.exe'
```

## 步骤

### 1. 收敛定理（为什么一次就够）

设程序计算 `X = GEN(name, code, version, ...)`，判定条件：

```
fc90 = ENCODE(code[pos : pos+W])      # key 自身切片编码
fc88 = ENCODE(X[pos : pos+W])         # 签名串同位切片编码
激活判定: fc88 == fc90                # ★ 只比较同位切片
```

若 `GEN` 对输入 `code` 的 `pos` 处 `W` 字符变化**局部不变**
（即 `X[pos:pos+W]` 不随 `code[pos:pos+W]` 改变，只随其余输入决定），则：

```
1. 写入任意占位 key（其 pos 切片为任意值）
2. 冷启动 → 程序算出确定的 X
3. 把 X[pos:pos+W] 回填到 key 的同位
4. 下次启动：fc90 == fc88 恒成立，且 X 不变
```

★ **关键步骤是验证局部不变性，而非还原 `GEN`。**

### 2. 定位 `pos` 计算逻辑

反编译中常见形态：

```c
pos = 11 + (date % 91) / 9;        // 日期派生 —— 位置每天变
// 或
pos = 15;                          // 常量位置
```

同时定位 `ENCODE` 与切片宽度 `W`（4 字符最常见）：
找 `code[pos:pos+W]` 参与比较的现场。

★ **日期派生切片必须在同一天完成抓取和回填** —— 过了午夜 `pos` 就变了，
昨天的回填全部作废。**记录抓取当天的日期。**

### 3. ★ 验证局部不变性（必做，两次抓取）

**这一步不能跳。** 只有两次抓取的 `X[pos:pos+W]` 相同，才说明「一次收敛」成立。

```python
# capture_x.py —— 抓取程序计算的签名串 X
import frida, sys, json

HOOK_ADDR = "0x14066CFEC"       # ENCODE(X[...]) 比较点或 X 生成函数

js = """
Interceptor.attach(ptr("%s"), {
    onLeave(retval) {
        var x = retval.toInt32();
        console.log(JSON.stringify({x: x, hex: "0x" + (x >>> 0).toString(16)}));
    }
});
""" % HOOK_ADDR

session = frida.spawn(["target.exe"])
script = session.create_script(js)
script.load()
session.resume()
# 等待冷启动计算完成
```

**两次抓取流程**：

| 步骤 | 操作 | 记录 |
|---|---|---|
| 1 | 写入占位 key #1（`pos` 切片 = `AAAA`） | key1 全文 |
| 2 | 冷启动，抓取 X#1 | `X1[pos:pos+W]` |
| 3 | 写入占位 key #2（`pos` 切片 = `BBBB`） | key2 全文 |
| 4 | 冷启动，抓取 X#2 | `X2[pos:pos+W]` |
| 5 | **比较** | `X1[pos:pos+W] == X2[pos:pos+W]` ? |

★ **若两次的切片不同 → 局部不变性不成立** → 本篇的捷径无效，
回到 `license-keygen-03` 完整还原 `GEN`。
**这个否证实验本身就是有价值的结论** —— 省掉了完整逆向的时间。

### 4. 回填

```python
def backfill(key: str, x_slice: str, pos: int, width: int) -> str:
    """把 x_slice 回填到 key 的 pos..pos+width。"""
    return key[:pos] + x_slice + key[pos + width:]

# 抓取
x_slice = x1_str[pos : pos + W]

# 回填
key_new = backfill(key1, x_slice, pos, W)

# 写入
import re
from pathlib import Path
KEYFILE = Path.home() / "AppData" / "Roaming" / "TargetApp" / "key.ini"
cfg = KEYFILE.read_text(encoding="utf-8")
KEYFILE.write_text(re.sub(r"(?m)^Code=.*", f"Code={key_new}", cfg),
                   encoding="utf-8")
print("backfilled pos=%d width=%d slice=%r" % (pos, W, x_slice))
```

★ **写入前结束目标进程**（见 `license-keygen-05` 坑 3）。

### 5. 验证

```
1. 重启目标
2. 观察：标题栏试用标记消失？状态位 == 0（已注册）？
3. ★ 再重启一次（排除「单次侥幸」）
```

## 两类典型形态

| 形态 | 特征 | 收敛策略 |
|---|---|---|
| **日期派生切片** | `pos = f(date)`，位置每天变 | 记录抓取日期；抓取与回填、验证**在同一天完成** |
| **固定切片** | `pos` 是常量（如 15） | 一次收敛，长期有效 |

## 与「完整还原 GEN」的取舍

| 路径 | 成本 | 风险 |
|---|---|---|
| **迭代收敛（本篇）** | 约 20 分钟，无需理解算法 | 依赖局部不变性成立；日期派生需当日完成 |
| 完整还原 GEN | 数天，需处理强混淆 | 通用、可生成任意 key |

★ **先验收敛（20 分钟），失败再考虑完整还原。**
步骤 3 的两次抓取本身就是收敛可行性的判据，成本极低。

## 判据

1. ★★★ **局部不变性成立**：两次不同占位切片的 `X[pos:pos+W]` **完全相同**。
   判据形态：一张对照表，两次抓取的切片值一致。
   **这是本篇唯一的可行性前提。** 不成立就别继续，走 `license-keygen-03`。
2. ★★★ **回填后冷启动标志位 == 0（已注册）、试用标记消失**。
   判据形态：重启后的 UI 状态 + 内存标志位值。
3. ★★ **重启两次以上保持**。判据形态：连续两次冷启动都是已注册状态。
   **只重启一次不能排除侥幸。**
4. ★★ **日期派生的 pos 已知且当天完成**。判据形态：记录了抓取当天的日期
   和当时算出的 `pos` 值。**跨天必须重做。**
5. **回填前后的 key 全文差异已记录**。判据形态：一份 before/after 对照，
   差异**只在 `pos..pos+W` 这个窗口内**。
   **若差异出现在别处 = 回填逻辑写错了。**

## 坑

1. ★★★ **跳过「局部不变性验证」直接回填**。如果 `X` 会随 key 的该切片变化，
   回填进去的值下次启动就失效 —— 表现为「第一次成功，第二次又不行了」。
   **两次抓取的成本是 5 分钟，跳过它的代价是几小时。**
2. ★★★ **日期派生切片跨天失效**。`pos = 11 + (date % 91) / 9` 意味着
   **每天 pos 都在变**。昨天回填的 key 今天必然失败。
   **抓取、回填、验证必须在同一天完成，并记录日期。**
3. ★★ **切片宽度 W 猜错**。常见是 4，但也有 2、8、16。
   猜错的表现是「回填了但判定仍失败」。
   **从反编译里确认切片宽度，别猜。**
4. ★★ **回填位置算错**。`pos` 是从 0 还是从 1 开始？是字节偏移还是字符偏移？
   搞错会填到错误的位置。**判据 5（差异只在窗口内）能抓住这个。**
5. ★ **写入前目标进程还在运行** → 退出时用内存数据覆盖，**回填被静默丢弃**。
   症状是「写进去了但重启后没用」。
6. ★ **X 的切片可能是二进制不是可打印字符**。若是十六进制串，需按目标的编码规则
   （base32 / hex / 自定义字符集）转换后再回填。
7. ★ **程序可能有多个 `X`**（比如同时算授权和订阅）。hook 点要选对 ——
   以「被用于判定」的那个为准，不是随便一个生成点。
8. **hook 点选错会导致抓到无关值**。判据是「两次抓取稳定且回填后生效」。
9. **本篇的 Frida 脚本未在本机实跑验证**。判据形态已确认，参数需按样本调整。
10. **`frida.spawn` 后必须先 `load()` 再 `resume()`**。顺序反了会错过冷启动的计算。

## 相关

- `license-keygen-02-validation-function-location.md` — 双机制信号从哪来
- `license-keygen-03-key-algorithm-recovery.md` — 收敛失败时的完整还原路线
- `license-keygen-05-keygen-verification-loop.md` — L3/L5 验收的通用形态
- `license-keygen-01-mechanism-classification.md` — C 类的特征描述
- `../procmon-patterns.md` — 找 `key.ini` 这类配置文件的真实路径