# Native SO 静态分析基线

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/apk-reverse/techniques/02-native/01-il2cpp-offset-discovery.md` + `02-native/02-pointer-chain-patterns.md`（本包未落地）（上游文件，未随本包落地）（结构体检部分为新增）
> **什么时候用**：APK 里带 `lib/*.so`，需要确认架构/符号/JNI 入口/构造函数，并开始找偏移和指针链。

## 适用信号

- `lib/arm64-v8a/libil2cpp.so` 或 `libUE4.so` 存在（游戏类）
- jadx 中只有 stub 方法，逻辑全在 native
- APK 体积大、OBB、引擎类应用
- 需要从 so 找加密、校验、协议封包入口

## 前置

```powershell
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
$r = Resolve-ReverseToolSpec -Name 'apktool'; & $r.Command --version
$r = Resolve-ReverseToolSpec -Name 'r2';      & $r.Command -v
$r = Resolve-ReverseToolSpec -Name 'python';  & $r.Command -V
```

Python 库（capstone 5.0.6 / lief 1.0.0 / pyelftools 0.33）都在 `(Resolve-ReverseToolSpec -Name 'pyre').Command`；`(Resolve-ReverseToolSpec -Name 'pyre').Command` 是空的，不要在那里找。

## 步骤

### 1. 提取 so

```powershell
$at = (Resolve-ReverseToolSpec -Name 'apktool').Command
& $at d target.apk -o target_apktool -f
Get-ChildItem target_apktool\lib -Recurse -Filter *.so |
  Select-Object @{n='ABI';e={$_.Directory.Name}}, Name, Length
```

同一游戏常有多 ABI（`armeabi-v7a` / `arm64-v8a`），**偏移在不同 ABI 下不同**，必须先确定目标设备跑哪个 ABI。

### 2. SO 全量体检（推荐第一步）

```powershell
$r = Resolve-ReverseToolSpec -Name 'python'
& $r.Command 'C:\relab2\skillpack\skills\apk-reverse\scripts\so-structure-audit.py' `
    target_apktool\lib\arm64-v8a\libil2cpp.so --jni
```

本机对真实 ARM32 Android SO 的实测输出（节区已截断）：

```
file      : libhgl.so
size      : 533452 bytes
class     : ELF32
machine   : ARM32
type      : ET_DYN
entry     : 0x10ac0
stripped  : yes

-- sections --
  <null>               SHT_NULL         --- addr=0x0       size=0x0
  .hash                SHT_HASH         -A- addr=0x94      size=0x28ec
  .dynsym              SHT_DYNSYM       -A- addr=0x2980    size=0x6320
  .text                SHT_PROGBITS     -AX addr=0x10aa0   size=0x16b0
  ... 其余 127 个节区省略

-- init_array / fini_array (构造函数 & 反调试入口) --
  .init_array[0] = 0x0005352c

-- build-id --
  (无 GNU build-id)

-- exports -- 1443 条
  (无 JNI_*/JNI_OnLoad 导出 -> 高度可能用 RegisterNatives 动态注册)

-- imports -- 75 条
  __aeabi_cfcmpeq
  ...
```

这个 SO 是 1443 个导出、75 个导入的正常游戏渲染库（`qglAPI_gl*` 命名可见），**不是加固件** —— 判断依据是导入/导出数量和符号可读性，不是「so 很大」。

### 3. DiE 初判编译器/壳

```powershell
$diec = (Resolve-ReverseToolSpec -Name 'diec').Command
& $diec -b $SO_PATH
```

输出格式（本机实测）：

```
ELF32
    Operation system: Android[ARM, 32-bit, DYN]
```

### 4. r2 补充信息

```powershell
$r2 = (Resolve-ReverseToolSpec -Name 'r2').Command
& $r2 -qc 'iI' $SO_PATH 2>$null        # ELF 概览
& $r2 -qc 'iS' $SO_PATH 2>$null        # 节区（精确匹配见「坑」）
& $r2 -qc 'iE' $SO_PATH 2>$null | Select-String 'Java_|JNI_OnLoad'
```

### 5. 模块基址获取

运行时三种方式：

```c
// 方式1: /proc/pid/maps 解析（最常用）
long get_module_base(pid_t pid, const char *name) {
    char path[64]; sprintf(path, "/proc/%d/maps", pid);
    FILE *fp = fopen(path, "r");
    char line[512], perms[5], mpath[256];
    unsigned long start, end;
    while (fgets(line, sizeof(line), fp)) {
        if (sscanf(line, "%lx-%lx %4s %*s %*s %*s %255s", &start,&end,perms,mpath) == 4
            && strstr(mpath, name) && perms[0]=='r' && perms[2]=='x') {
            fclose(fp); return (long)start;
        }
    }
    fclose(fp); return 0;
}
// 方式2: syscall ioctl（需内核驱动）
// 方式3: dl_iterate_phdr 回调（SO 内自定位）
```

### 6. 跨进程内存读：两种路径

```c
// 用户态 syscall：通用但受 ptrace/权限限制
ssize_t pvm_read(pid_t pid, uintptr_t addr, void *buf, size_t len) {
    struct iovec l[1] = {{buf, len}};
    struct iovec r[1] = {{(void*)addr, len}};
    // syscall 号因架构而异: arm64=270, x86_64=310
    return syscall(__NR_process_vm_readv, pid, l, 1, r, 1, 0);
}
```

内核驱动路径（绕过 seccomp/SELinux/anti-debug）见 `../dynamic/memory-rw-hook.md`。

### 7. 指针链递归封装

```c
uintptr_t getZZ(uintptr_t addr) {   // 等价于 *(uintptr_t*)addr
    uintptr_t v = 0;
    driver->read(addr, &v, sizeof(v));
    return v;
}

// 数组遍历：固定步长
for (int i = 0; i < count; i++) {
    uintptr_t entity = getZZ(arrayHead + (i * 0x20));   // 步长 sizeof(entry)
    if (!entity) continue;                              // 空指针保护
    int hp = getDword(entity + 0x36C);
}
```

### 8. 偏移交叉验证（静态 + 动态）

```
静态：r2/IDA 里找到访问模式 → 记下 obj+0xXXXX 和数组步长
动态：Frida 逐级 readPointer 验证，直到读到有意义的数据
常见规律：血量 int 落在 +0x360~0x380；名字指针 char* 在 +0x260~0x280
```

## 判据

| 观察 | 结论 |
|---|---|
| `stripped=yes` 但 imports 数十条、符号可读 | 正常游戏 so，直接静态分析 |
| `stripped=yes` + imports 极少 + strings 空 | 强混淆/加固，转 `../packer/obfuscation-detection.md` |
| exports 无 `Java_*` / `JNI_OnLoad` | 动态注册，转 `jni-register-natives-tracing.md`（同目录） |
| `.init_array` 条目 > 3 | 逐条反查（解密/反调试入口） |
| 多 ABI 且偏移不通用 | 先定目标 ABI 再找偏移 |

**外部可观测的判据**：`so-structure-audit.py` 的 `exports -- N 条` / `imports -- N 条` / `stripped` 三行 —— 而不是「so 看起来挺大」。

## 坑

- **`rabin2` 在本机是坏副本**，用 `r2 -qc` 代替。
- **r2 `/x` 通配符是 `.` 不是 `?`**，`search.from/to` 无效；重定位样本要 `2>$null`。
- **r2 的 `~` 过滤不支持 `^`/`$` 锚点**：本机实测 `iS~^\.text$` 输出为空，`iS~.text$` 仍会连 `ARM.text` / `.debug_frame$$$ARM.text` 一起带出。要精确匹配节名，把 `iS` 输出交给外部 awk：
  ```bash
  echo '$NF == ".text" { print }' > filt.awk
  r2 -qc 'iS' lib.so 2>/dev/null | awk -f filt.awk
  ```
  实测输出（只命中真正的 `.text`）：
  ```
  7   0x00010aa0   0x16b0 0x00010aa0   0x16b0 -r-x 0x6   PROGBITS   .text
  ```
- **ARM32 的 `e_machine` 在 pyelftools 里返回字符串 `'EM_ARM'`**，不是整数 `0x28`；写映射表要用字符串键。
- **偏移不跨 ABI、不跨版本**：静态区偏移随版本更新变化，用特征码替代硬编码。
- **`getDword`/`getFloat` 的宽度要对齐**：int 在 4 字节边界，指针在 8 字节边界；偏移 ±4 误差先试对齐。
- **本机无 Android 设备**：以上指针链/跨进程读的部分**需真机/模拟器，本机未验证**。

## 相关

- `jni-register-natives-tracing.md` —— 动态注册的方法到 native 地址映射
- `ue4-offset-hunting.md` —— UE4 专属偏移规律
- `../dynamic/memory-rw-hook.md` —— 跨进程内存读写检测与 hook
- `../packer/obfuscation-detection.md` —— 强混淆 so 的处理
