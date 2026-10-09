# VMP 脱壳与语义还原（Dump/Trace/Recovery）

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/apk-reverse/techniques/07-packer/04-vmp-dump-trace-recovery.md`
> **什么时候用**：已按 `vmp-dex2c-detection.md` 判定为 VMP/dex2c，需要拿到被虚拟化方法的真实语义。

## 适用信号

- BlackDex / frida-dexdump 产出的 dex 中，目标方法仍无 CodeItem（只剩 stub）
- so 内存在 dispatch 大循环（用 `find-vm-dispatch.py` 确认，score ≥ 3）
- RegisterNatives 动态绑定的方法名与 `Java_com_*` 命名规则不符
- trace 中可见重复的「取指 → 分发 → 执行」模式

## 前置结论：VMP 下 dump 必然失败

被虚拟化的方法在 dex 里**没有可 dump 的 CodeItem**，自定义字节码存在于 so 数据段。所以正确路线是：

```
dump 摸底 → 确认仍无 CodeItem（判定 VMP） → trace 解释器 → 语义还原
```

不要在 dump 工具上反复重试。**需真机/模拟器，本机未验证**（本机无 Android 设备，动态部分标注见各节）。

## 步骤

### 1. dump 摸底工具对比

| 工具 | 原理 | 适用 | 维护状态 |
|---|---|---|---|
| frida-dexdump | 内存模糊搜索 dex 特征 dump | 抽取壳/普通壳快检 | 2023 已归档，仍可用 |
| BlackDex | DexFile cookie 定位，免刷机，深度脱壳回填抽取指令 | 抽取壳主力 | 可用 |
| FART | ART 主动调用 + 解释器插桩 dump CodeItem | 抽取壳深度还原 | 有 frida 版 |
| Youpk | 改 ROM 主动调用，强制 switch 解释器插桩 | 抽取壳最强，仅 Pixel 1 刷机 | 早期 |

这些都是**外部工具**，不在本技能包内；需自行获取。

### 2. dump 失效的判定（外部可观测）

```
判据：jadx 打开 dump 出来的 dex，目标方法仍是 nop / native stub，
      并且 dexdump 显示该方法无 code 区段。
```

本机 `dexdump` 对一个真实解包样本的输出，可直接对照看 `code` 字段与 `insns size`：

```
$ D:\Tools\android-sdk\build-tools\34.0.0\dexdump.exe -d classes.dex
Processing 'classes.dex'...
Opened 'classes.dex', DEX version '035'
Class #0            -
  Class descriptor  : 'Lcom/revlab/demo/DemoActivity;'
  Access flags      : 0x0001 (PUBLIC)
  Superclass        : 'Landroid/app/Activity;'
  Direct methods    -
    #0              : (in Lcom/revlab/demo/DemoActivity;)
      name          : '<init>'
      type          : '()V'
      access        : 0x10001 (PUBLIC CONSTRUCTOR)
      code          : 4 16-bit code units
      registers     : 1
0001d8:  |[0001d8] com.revlab.demo.DemoActivity.<init>:()V
0001e8: 7010 0000 0000  |0000: invoke-direct {v0}, Landroid/app/Activity;.<init>:()V
0001ee: 0e00            |0003: return-void
      catches       : (none)
```

**VMP 判据**：`code` 为空 / `insns size` 为 0，而方法仍然存在且被调用 —— 即「有方法、无指令」。这是 dump 类工具拿不到东西的直接证据。

### 3. 主路线：unidbg 指令 trace

> unidbg（zhkl0228/unidbg，Java）是外部工具，需自行引入依赖；本机未安装、未验证。

思路：在 unidbg 中加载 so → 定位 dispatch 入口 → 开 instruction trace → 记录「字节码地址 + handler 跳转」序列。

```java
// unidbg 配置骨架
AndroidEmulator emulator = AndroidEmulatorFactory.createARM64Emulator();
VM vm = emulator.createDalvikVM();
DalvikVM64 dalvikVM = (DalvikVM64) vm;
dalvikVM.setVerbose(false);

Module mod = emulator.loadLibrary(new File("libtarget.so"), true);

// 只 trace 解释器所在地址范围，避免噪音爆炸
emulator.getMemory().addInstructionTrace(mod.base + 0x1000, mod.base + 0x2000);

// 调用目标方法 → 导出 trace
```

trace 中的 dispatch 形态（本机用 keystone+capstone 实际汇编出的 ARM64 dispatch 桩反汇编结果，与之逐条对应）：

```
0x1000  stp      x29, x30, [sp, #-0x20]!
0x1004  mov      x29, sp
0x1008  mov      x3, x0
0x100c  ldrb     w5, [x3]
0x1010  and      w5, w5, #0xff
0x1014  adr      x6, #0x2058
0x101c  ldr      x7, [x6, x5, lsl #3]
0x1020  br       x7
```

含义：`x3` 是字节码指针 → `ldrb` 取 opcode → `and` 掩码 → `ldr` 从跳转表按 `opcode<<3` 取 handler 地址 → `br` 分发。

### 4. 副路线：Frida Stalker trace dispatch（真机）

```javascript
var base = Module.findBaseAddress("libtarget.so");
var start = base.add(DISPATCH_START), end = base.add(DISPATCH_END);

Stalker.follow(Process.getCurrentThreadId(), {
    events: { call: true },
    onReceive: function (events) {
        var ev = Stalker.parse(events, { annotate: true });
        ev.forEach(function (e) {
            if (e[0] === 'call' &&
                e[1].compare(start) >= 0 && e[1].compare(end) <= 0)
                console.log(e[1].sub(base).toString(16), e[2]);
        });
    }
});
```

Stalker 开销大（解释器循环高频触发），先用 `onCallSummary` 做热度统计缩小 handler 范围，再对热点 handler 单独跟。

### 5. 语义还原：handler 映射表

```
1. 从 trace 提取全部 handler 入口地址（dispatch 跳转目标去重）
2. 对每个 handler 静态分析：观察其读写的虚拟寄存器/内存槽位
3. 建立映射表：handler 地址 → 语义（mov_imm / add_reg / jmp_rel / call_native / ret）
4. 把字节码流按映射表翻译为高层伪代码
5. 用输入输出等价性验证还原正确性
```

映射表示例：

```
0x00 0x01 0x2A  →  handler@0x7f40 (mov reg0, imm=0x2A)  →  reg0 = 42
0x00 0x02 0x10  →  handler@0x7f60 (add reg0, imm=0x10)  →  reg0 += 16
0x00 0x03 0x14  →  handler@0x7f80 (jmp_rel 0x14)        →  pc += 0x14
```

## 判据

| 观察 | 结论 |
|---|---|
| dump 后 `dexdump` 显示 `code` 为空但方法存在 | VMP 确认，dump 路线终止 |
| `find-vm-dispatch.py` 报 `[score>=3]` 区间 | so 内有解释器，trace 路线可行 |
| trace 中 handler 被反复调用且地址集中 | dispatch 入口定位成功 |
| 还原伪代码与原方法输入输出一致 | 还原正确 |

**外部可观测的判据**：trace 文件中同一 handler 地址出现多次调用；映射表条目能对上一条真实字节码（而不是「看起来像解释器」）。

## 坑

- **unidbg / BlackDex / FART / Youpk 都是外部工具**，不在本技能包内，本机未安装、未验证。
- **Stalker 跟全指令流会打爆内存**：必须限定地址范围。
- **`frida-dexdump` 已 2023 归档**，可能不兼容新版 Frida（17.x 系列本机已验证可用）。
- **dex2c 还原没有成熟开源还原器**：截至 2026-08 社区确认，只有加固侧参考实现和文章，实践要靠「trace + handler 映射」手工还原。
- **等价性验证不能省**：映射表是猜的，必须拿输入输出对比过。

## 相关

- `vmp-dex2c-detection.md` —— 前置的形态判定
- `vmp-anti-debug-bypass.md` —— trace 前必须先过反调试
- `../native/jni-register-natives-tracing.md` —— 找被保护方法的 native 入口
