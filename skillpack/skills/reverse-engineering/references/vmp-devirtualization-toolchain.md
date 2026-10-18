# VMP 去虚拟化工具链（Devirtualization）

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/pe-reverse/05-crypto-unpack/03-vmp-devirtualization-toolchain.md`（已适配本机工具链）
> **什么时候用**：已按 `vmp-virtualization-analysis.md` 定位到 VM entry 与 dispatcher，但 handler 数量多、mutation 重，纯手工还原不可行。需要用自动化工具把「handler 序列」还原成高层指令或中间表示。

## 适用信号

- 已确认 VMP 2.x/3.x，**且拿到 VM entry 地址表**（缺这一条不要进本篇）。
- 目标函数是**纯函数**（输入输出可枚举、无系统调用副作用）—— 这是符号执行路线的必要条件。
- 单步一个被保护函数要走几百个 handler 循环，手工跟踪已经失去耐心。
- 被保护函数调外部 API（call handler 跳到 `VirtualAlloc` 等）→ 静态 devirt 会失败，需动态 trace 兜底。

## 本机环境现状（务必先读）

本机**没有** C++ 工具链形态的 NoVmp / VTIL / Triton。实测两个解释器的库情况
（2026-10-14，逐包 `importlib.util.find_spec`）：

```
=== (Resolve-ReverseToolSpec -Name 'pyre').Command      # 带全部逆向库的那个
  pefile YES  capstone YES  lief no   angr YES  unicorn YES
  qiling YES  z3 YES        yara YES  dnfile no  triton no

=== (Resolve-ReverseToolSpec -Name 'python').Command    # 探测层默认解析到的
  pefile YES  capstone YES  lief no   angr YES  unicorn YES
  qiling no   z3 YES        yara no   dnfile no  triton no
```

版本（`pyre` 实测）：`angr 9.2.213` · `z3 4.13.0` · `unicorn 2.1.2` ·
`capstone 5.0.6` · `pefile 2024.8.26` · `yara 4.5.4`。

**唯一可用的 DSE 栈是 `pyre` 的 `angr`**（实测 `9.2.213`）。

```powershell
& (Resolve-ReverseToolSpec -Name 'pyre').Command -c "
import capstone, pefile, angr, unicorn
print('capstone', capstone.__version__); print('pefile', pefile.__version__)
print('angr', angr.__version__);         print('unicorn', unicorn.__version__)"
# 实测输出（2026-10-14）:
#   capstone 5.0.6 / pefile 2024.8.26 / angr 9.2.213 / unicorn 2.1.2
```

> ★ **`triton` 装不上**。PyPI 的 `triton` 包名和 OpenAI GPU 编译器冲突，源文档说「需源码构建」—— 本机没做，别按那条路规划。
>
> ★ **不是每个 venv 都有逆向库**：只装了 agent 运行时依赖（`pyghidra` / `mcp` / `onnxruntime`）的 venv
> 能跑 `python --version`，但 `pefile` 都 import 不出来。**要用库一律走别名 `pyre`**（见 §上一节）。

## 三级降级策略

```
第 1 级: 静态 devirtualization (NoVmp + VTIL)
         快, 适合 VMP 2.x / 3.0-3.5 x64; 3.8+ 大概率失败 → 降级
         ⚠ 本机未安装, 需人工编译 (VS + git submodule)

第 2 级: 符号执行 DSE (angr —— 本机可用)
         以 VM entry 寄存器为符号输入跑解释器, 求解后化简为表达式
         适合纯函数; 性能开销大

第 3 级: trace 语义折叠 (PIN + 模式匹配, VMHunt 思路)
         记录 VM 循环指令 trace, 按 handler 指纹折叠为高层指令
         适合任何函数, 但人工校对量大
```

**每一级失败立即降级，不要在上一级死磕。**

## 第 1 级：静态 devirt（NoVmp / NoVmpy）—— 本机需人工安装

| 工具 | 来源 | 状态 |
|---|---|---|
| NoVmp | `github.com/can1357/NoVmp` | 2021 后停更；对 VMP 3.8+ 大概率失效 |
| NoVmpy | `github.com/wallds/NoVmpy` | Python 移植，2025 仍有提交 |
| VTIL-Core | `github.com/vtil-project/VTIL-Core` | 活跃（2026-07），NoVmp 依赖 |

```powershell
git clone --recursive https://github.com/can1357/NoVmp
# Visual Studio 打开 NoVmp.sln，编译 Release x64
NoVmp.exe <sample.exe> <function_rva>
# 输出 <sample>.devirt.exe + <sample>.devirt.ll (LLVM IR)
```

**失败特征**（出现任一即降级到第 2 级）：输出与原始行为不符 / 崩溃 / 空 IR。

> 本机**没有**预编译的 NoVmp，`D:\Tools` 下也**没有** VS。走这条路的成本（下载 + 编译 + 对 VMP 版本的适配）通常高于直接上第 2 级。**先评估再决定。**

## 第 2 级：符号执行 DSE（本机可跑）

**原理**：以 VM entry 处寄存器为符号值，让 VMP 解释器在符号引擎中执行。handler 展开后的表达式被求解化简，得到「输入寄存器 → 输出寄存器」的语义公式。

**关键约束**：**只对纯函数做 DSE**。VM context 在 3.x 进出被变换，**符号化起点选在 dispatcher 入口而非函数入口更稳**。执行前先过反调试（ScyllaHide / patch 自检）。

最小可跑骨架（本机 `angr` 实测可用）：

```python
import logging
logging.disable(logging.CRITICAL)          # angr 默认日志噪音极大

from angr import Project

proj = Project("sample.exe", auto_load_libs=False)
print("entry:", hex(proj.entry))
print("arch:", proj.arch.name)

# 实测输出:
#   entry: 0x1400013f0
#   arch: AMD64

state = proj.factory.entry_state(
    add_options={proj.unicorn_plugin.UUNICORN}   # 用 unicorn 后端加速具体执行
)
sm = proj.factory.simulation_manager(state)
```

实际用于 VMP devirt 的骨架（在真实样本上要补三件事）：

```python
import logging; logging.disable(logging.CRITICAL)
from angr import Project

proj = Project("vmp_sample.exe", auto_load_libs=False)
state = proj.factory.blank_state(addr=vm_entry_rva)   # ← 符号化起点：dispatcher 入口

# 1. 把 VM context / 通用寄存器符号化
for reg in state.regs.arch_regs:
    state.regs.write(reg, getattr(state.regs, reg))    # concretize 后逐个符号化

# 2. 跑到 VM exit（= vm_entry 的 ret 目标）
simgr = proj.factory.simulation_manager(state)

# 3. 在 VM exit 处取输出寄存器的符号表达式，化简
#    —— 这一步是 devirt 的核心产出

# ⚠ 实际项目里要 handle：VM context 读写、handler 表跳转、字节码解密
#    这三块是全部工程量所在，不是上面 5 行能覆盖的
```

**angr 的真实局限（必须写进项目计划）**：
- VMP 的 dispatcher 是**间接跳转表**，angr 每次分叉到不同 handler，路径爆炸。
- handler 有 mutation 混淆，angr 的 VEX lifter 可能反汇编失败。
- VM context 在 3.x 被加密，符号化时无法直接建模。

所以第 2 级实际是**「angr 做局部求解 + 人工补 handler 语义」**，不是全自动。

## 第 3 级：trace 语义折叠（VMHunt 思路，本机无工具）

思路来自 `github.com/s3team/VMHunt`（CCS'18，2018 停更，仅参考思路）：

```
1. 记录 VM 循环内全部指令 trace → (内存地址, 指令字节) 序列
   ⚠ 本机无 PIN / DynamoRIO；可用 cdb 的单步 trace 或 angr 的 VEX trace 替代
2. 按 handler 边界切分 trace: dispatcher 跳转目标即 handler 起点
3. 对每个 handler 片段做符号执行/模式匹配, 得到该 handler 的语义
   (mov x, imm / add r, c / jmp label / call api …)
4. 折叠: 把连续 handler 序列翻译为高层指令流, 人工校对
5. 验证: 同一输入分别跑原始样本与还原代码, 比较输出
```

用本机 cdb 采集 handler trace（作为 PIN 的替代）：

```powershell
$exe  = 'C:\path\to\vmp_sample.exe'
$cdb  = "$env:LOCALAPPDATA\Microsoft\WindowsApps\cdb.exe"
$cmds = "$env:TEMP\vmp_trace.txt"

@'
bu ntdll!LdrpDoDebuggerBreak
g
.echo ===AT_VM_ENTRY===
.echo Enable trace: gu /t:0x400
g
.echo ===AFTER_TRACE===
q
'@ | Set-Content -Path $cmds -Encoding ASCII

& $cdb -cf $cmds $exe
```

`gu /t:0x400` 打开调用 trace，把每条经过的指令记进 cdb 日志。**样本量大时日志会非常大，先用 `ft`/`tr` 控制条数。**

## 结果验证（输入输出等价性）

无论哪一级还原，**必须**做等价性验证：

```python
# 对比原始与还原结果的输入输出
test_vectors = [0, 1, -1, 7, 0x7FFFFFFF, 0x80000000, 0xFFFFFFFF, 0x12345678]

for v in test_vectors:
    orig_out = run_original(v)      # 在原始样本里调被保护函数
    dev_out  = run_devirt(v)        # 跑还原后的函数/IR
    assert orig_out == dev_out, f"mismatch on {v:#x}: {orig_out} != {dev_out}"

print("devirtualization verified on", len(test_vectors), "vectors")
```

**验证失败 = 还原不完整**（漏了某个 handler 语义 / VM key 解错 / 字节码错位）。回到对应级别修正，不要继续往上走。

`run_original` 的实现（本机可行路径）：

```powershell
# cdb 里调被保护函数并读返回值
$cmds = "$env:TEMP\devirt_verify.txt"
@'
bu ntdll!LdrpDoDebuggerBreak
g
.echo ===CALL_VM_FN===
bu <被保护函数VA> C "r rcx; g; r rax"
g
q
'@ | Set-Content -Path $cmds -Encoding ASCII

& $cdb -cf $cmds .\vmp_sample.exe
```

判据：`r rax` 打印的返回值与还原代码在同一输入下的输出一致。

## 判据

每级结果的**外部可观测**判据：

**第 1 级（静态 devirt）**
- NoVmp 退出码 0，且生成了非空的 `<sample>.devirt.ll`。
- `lief` 解析 `.devirt.exe` 成功：`len(b.sections) > 0`、`optional_header.imagebase` 非 0。
- 加载 `.devirt.exe` 到 r2 后 `afl` 能识别函数（不是 0 个）。

**第 2 级（DSE）**
- angr `simulation_manager` 能跑到 VM exit（`simgr.active` 非空或 `deadended` 非空）。
- 输出寄存器的符号表达式**化简后不是原始输入寄存器的恒等变换** —— 恒等变换说明 devirt 什么都没做。
- 等价性验证脚本在全部 `test_vectors` 上打印 `devirtualization verified`。

**第 3 级（trace 折叠）**
- trace 能按 handler 边界切分成有限个片段（片段数 << 指令条数，否则说明没切对）。
- 折叠后的人工校对结果通过等价性验证。

**跨级通用的失败判据**：等价性验证里任何一条 `assert` 失败 = 本级失败，降级。

## 坑

1. ★★ **本机没有 NoVmp / VTIL / Triton**。源文档第 1、2 级依赖的 C++ 工具链**一个都没装**，`D:\Tools` 下也没有 Visual Studio。第 1 级要人工下载+编译，第 2 级的 Triton 路线**直接放弃**（PyPI 包名冲突，装不了）。
2. ★ **`python-venv` 里没有任何逆向库**。任务简报里写的「venv 里已有 pefile/capstone/lief/angr/unicorn/qiling/z3/dnfile/yara-python」**与实测不符** —— 实际这些全在 `(Resolve-ReverseToolSpec -Name 'pyre').Command`，`python-venv` 只有 `pefile` 都没有。用前先探：
   ```powershell
   & (Resolve-ReverseToolSpec -Name 'pyre').Command -c "import importlib.util as u; \
     [print(m, 'YES' if u.find_spec(m) else 'no') for m in ['pefile','capstone','lief','angr','unicorn','z3']]"
   ```
3. ★ **`claripy` 不能单独 import**（`from angr import *` 之后才可用作 `state.regs` 等 API）。写 DSE 脚本不要写 `import claripy` 开头。
4. ★ **angr 默认日志噪音极大**，会把有用的输出淹没。开脚本第一件事：
   ```python
   import logging; logging.disable(logging.CRITICAL)
   ```
5. ★ **符号化起点选 dispatcher 入口，不是函数入口**。VM context 在 3.x 进出被 XOR/ADD 变换，从函数入口符号化会直接建模失败。
6. ★ **只对纯函数做 DSE**。函数一旦调外部 API（`VirtualAlloc`/`CreateThread`），angr 就要建模那些 syscall，路径爆炸且结果不可信。
7. **VMP handler 变体数十个，每次重新加壳都变**（见 `vmp-virtualization-analysis.md` 坑 1）。第 3 级的「handler 指纹」**不能跨样本复用**。
8. **`gu /t:0x400` 的 trace 日志可能几百 MB**。先在 VM entry 处用 `gu /t:0x40` 试，确认粒度对了再放大。
9. **`bu <addr> C "命令"` 在 cdb 里会报错**（实测 `Couldn't resolve error`）。命令必须换行分隔。
10. **cdb 断点必须在 `g` 之前下**；**命令串必须 `-cf <文件>`**（内联带引号经 cmd 会被转义坏，`Win32 error 0n2`）。
11. **等价性测试向量要覆盖边界**：`0`、`-1`、`0x7FFFFFFF`、`0x80000000`、`0xFFFFFFFF` 这些会暴露 shift/符号扩展相关的手册错误。只测随机值会漏。
12. **NoVmp 的 star 数和适配性随时变**。文档里的维护状态是快照，落地前必须在你的样本上实测验证。


## 出口（结论回填）

回填位置：滚动报告 `assault.md`（`-Preset assault` 生成）的对应表。

- devirt 产物（可读函数 / 执行 trace）→ `## functions` 对应行证据（状态可升「已实现」）
- 三级降级中实际走通的路线（NoVmp / angr DSE / trace 折叠）→ `## routes` 的 patch/rewrite 行证据
- 等价性验证结果（devirt 后行为 vs 原行为）→ `## diff_baseline` 对应行草稿（`diff-runner.py`）
- 失败降级的原因（如符号执行爆路径）→ `## unknowns` 或 `## routes` 的 rejected_because

判定：devirt 产物必须过等价性验证才算进，「看起来像」不算。

## 相关

- `vmp-virtualization-analysis.md` — **前置篇**：VM entry / dispatcher / VM key 的定位（本篇的输入）
- `unpack-and-memory-dump.md` — VMP 外层 dump（devirt 前要先脱外层壳）
- `anti-debug-bypass.md` — 前置：过 VMP 自检，否则符号执行跑不起来
- `code-patching.md` — devirt 产物的验证与落地
- `aob-signature-scan.md` — handler 变体多时靠特征码定位
- `nonpe-format-cookbook.md` — angr/symbolic execution 的通用用法（非 PE 格式）
- `../SKILL.md` — 总体流程