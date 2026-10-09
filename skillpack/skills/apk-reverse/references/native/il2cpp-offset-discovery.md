# IL2CPP 偏移发现与指针链模式

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/apk-reverse/techniques/02-native/01-il2cpp-offset-discovery.md` + `02-native/02-pointer-chain-patterns.md`（本包未落地）（上游文件，未随本包落地）
> **什么时候用**：Unity IL2CPP 游戏，需要定位数据结构偏移和指针链，不依赖运行时 dump。

## 适用信号

- `lib/arm64-v8a/libil2cpp.so` 存在
- `assets/bin/Data/Managed/Metadata/global-metadata.dat` 存在
- jadx 中只有 stub 方法，无实际 C# 逻辑
- 已获取进程 PID 和模块基址，想找 Manager/Container/Entity 链路

## IL2CPP 关键结构

`global-metadata.dat` 包含完整的类型/方法/字符串映射，文件头 magic 为 `0xFAB11BAF`：

```
Metadata 文件头 → stringLiteralOffset/Cnt → stringLiteralData
                 → metadataStrings（类型名/方法名/字段名池）
                 → typeDefinitions（含字段偏移）
                 → methodDefinitions（方法 index → libil2cpp.so 中的函数地址）
```

## 前置

```powershell
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
$r = Resolve-ReverseToolSpec -Name 'apktool'; & $r.Command d target.apk -o out -f
```

结构体检见 `so-structure-audit.md`（先跑那个确认 ABI 和是否加固）。

## 步骤

### 1. 确认 IL2CPP 与版本

```powershell
$at = (Resolve-ReverseToolSpec -Name 'apktool').Command
& $at d target.apk -o out -f
Get-ChildItem out\lib -Recurse -Filter 'libil2cpp.so' | Select-Object FullName, Length
Get-ChildItem out\assets -Recurse -Filter 'global-metadata.dat' | Select-Object FullName, Length
```

### 2. 解析 global-metadata.dat 头（本机已验证）

```powershell
$r = Resolve-ReverseToolSpec -Name 'python'
& $r.Command -c @"
import struct, sys
d = open(sys.argv[1], 'rb').read(0x100)
magic = struct.unpack_from('<I', d, 0)[0]
print('magic      = 0x%08X' % magic)
print('IL2CPP     = %s' % (magic == 0xFAB11BAF))
ver = struct.unpack_from('<i', d, 4)[0]
print('version    = %d' % ver)
for i, name in enumerate(['stringLiteralOffset','stringLiteralSize',
                          'stringLiteralDataOffset','stringLiteralDataSize',
                          'stringOffset','stringSize']):
    off, size = struct.unpack_from('<ii', d, 8 + i*8)
    print('  %-22s off=0x%x size=0x%x' % (name, off, size))
"@ out\assets\bin\Data\Managed\Metadata\global-metadata.dat
```

判据：magic 必须等于 `0xFAB11BAF`，否则不是 IL2CPP metadata（或版本差异导致布局不同，先确认 Unity 版本）。

本机用构造的 metadata 头实测（正确 magic）：

```
magic      = 0xFAB11BAF
IL2CPP     = True
version    = 29
  stringLiteralOffset    off=0x2000 size=0x100
  stringLiteralSize      off=0x2100 size=0x800
  stringLiteralDataOffset off=0x2900 size=0x1000
  stringLiteralDataSize  off=0x3900 size=0x5000
  stringOffset           off=0x0 size=0x0
  stringSize             off=0x0 size=0x0
```

阴性对照（magic 写错成 `0xDEADBEEF`），`IL2CPP` 变 `False` 且字段全 0：

```
magic      = 0xDEADBEEF
IL2CPP     = False
version    = 0
  stringLiteralOffset    off=0x0 size=0x0
  ...
```

**注意字段步长是 4 字节不是 8**：metadata 头里 `offset`/`size` 都是 `int32` 连续排列，按 `<ii` 每 8 字节取一对是对的，但如果你按 `struct.unpack_from('<ii', d, 8 + i*8)` 之外的方式解析，后面几项会整体错位。

### 3. 模块基址

见 `so-structure-audit.md` 的 `/proc/pid/maps` 解析代码。

### 4. 偏移发现的实战模式

```c
// 三指针链定位示例（数值需按目标版本实测确认）
long libbase  = get_module_base(pid, "libil2cpp.so");
long staticR  = libbase + STATIC_REGION_OFF;   // .data/.bss 静态区偏移
long root     = *(long*)(staticR + 0x4BCB0);    // 第1跳: 静态指针
long level2   = *(long*)(root + 0xB0);          // 第2跳: 管理器对象
long level3   = *(long*)(level2 + 0x50);        // 第3跳: 容器
long arrayHead= *(long*)(level3 + 0xA0);        // 第4跳: 数组头
// 遍历: arrayHead[i * 0x20] = 玩家对象指针
```

**这些数值是示例，不是可直接用的偏移** —— 必须在你自己的样本上用下面的方法确认。

### 5. 偏移交叉验证

```
静态：r2/IDA 找到访问模式 → 记下 obj+0xXXXX 与数组步长
动态：Frida 逐级 readPointer，直到读到有意义的数据
常见规律：血量 int 在 +0x360~0x380；名字 char* 在 +0x260~0x280
```

### 6. 内存读取的两种路径

```c
// 用户态 syscall（通用，受权限限制）
ssize_t pvm_read(pid_t pid, uintptr_t addr, void *buf, size_t len) {
    struct iovec l[1] = {{buf, len}};
    struct iovec r[1] = {{(void*)addr, len}};
    return syscall(__NR_process_vm_readv, pid, l, 1, r, 1, 0); // arm64=270
}

// 内核驱动 ioctl（绕过 seccomp/SELinux/anti-debug）
class c_driver {
    int fd;
    enum { OP_READ_MEM=601, OP_WRITE_MEM=602, OP_MODULE_BASE=603 };
    bool read(uintptr_t a, void *b, size_t n) {
        COPY_MEMORY cm = {pid, a, b, n};
        return ioctl(fd, OP_READ_MEM, &cm) == 0;
    }
};
```

### 7. 指针链封装与遍历

```c
uintptr_t getZZ(uintptr_t addr) { uintptr_t v=0; driver->read(addr,&v,sizeof v); return v; }

// 五级链
long obj = getZZ(getZZ(getZZ(getZZ(base+0x4BCB0)+0xB0)+0x50)+0xA0);

// 数组遍历
for (int i=0;i<count;i++){
    uintptr_t e = getZZ(arrayHead + (i*0x20));   // 步长 = sizeof(entry)
    if (!e) continue;                            // 空指针保护
    int hp = getDword(e + 0x36C);
}
```

## 常见偏移规律

| 引擎 | 对象基类偏移特征 | 常见步长 |
|---|---|---|
| Unity IL2CPP | 静态区指针 → Manager → List → Item | 0x8 / 0x10 / 0x20 |
| UE4 | AActor→RootComponent→RelativeLocation | 0x8 |
| Cocos2d | CCObject→m_pComponent→m_sPosition | 0x4 |

## 实战技巧

1. **偏移在 ±0x4 误差内**：int 在 4 字节边界，指针在 8 字节边界。
2. **区分数组步长和结构体偏移**：数组用 `i*sizeof(entry)`，字段用固定偏移。
3. **指针过空保护**：每次 `getZZ` 后判 `if (!ptr) continue;`。
4. **特征码替代硬偏移**：版本更新时用特征码，不要硬编码。

## 判据

| 观察 | 结论 |
|---|---|
| magic == 0xFAB11BAF 且字段偏移自洽 | IL2CPP metadata 解析成功 |
| 逐级 readPointer 读到合法对象（非 0、非野指针） | 该跳偏移正确 |
| 数组遍历出现重复且有意义的数据 | 步长正确 |
| 读出全 0 或随机值 | 该跳偏移错误，回到上一级 |

**外部可观测的判据**：magic 值 + 逐级解引用得到「合法指针 + 合理数据」，不是「偏移看起来合理」。

## 坑

- **`global-metadata.dat` 布局随 IL2CPP 版本差异大**：先确认 Unity 版本再套字段偏移。
- **静态区偏移随版本更新变化**：不要跨版本复用。
- **`libil2cpp.so` 被混淆/加壳后函数边界模糊**：先跑 `so-structure-audit.md` 和 `../packer/obfuscation-detection.md`。
- **`process_vm_readv` 的 syscall 号因架构而异**：arm64=270，x86_64=310。
- **本机无 Android 设备**：指针链/跨进程读部分**需真机/模拟器，本机未验证**；静态 metadata 解析部分已验证。
- **`rabin2` 本机是坏副本**，用 `r2 -qc`。

## 相关

- `so-structure-audit.md` —— SO 结构体检基线
- `ue4-offset-hunting.md` —— UE4 偏移规律
- `jni-register-natives-tracing.md` —— native 入口还原
