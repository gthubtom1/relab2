# 进程内存读写检测与 Hook

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/apk-reverse/techniques/06-dynamic/01-memory-rw-hook.md`
> **什么时候用**：目标应用使用跨进程内存读取，需要检测并 Hook 这些调用；或在被调试进程侧监控自己的内存被谁读。

## 适用信号

- `strace -f` 追踪到大量 `process_vm_readv` 调用
- `/proc/pid/maps` 被频繁打开读取
- 内核模块 `ioctl` 命令号 ≥ 0x600（自定义魔数）
- 有未知进程/线程读写目标数据

## 三条内存读写路径

### 路径 1：syscall process_vm_readv/writev

```bash
# 检测
strace -e trace=process_vm_readv,process_vm_writev -p $PID
# 输出: process_vm_readv(12345, [...], 1, [...], 1, 0) = 8
```

```javascript
var p = Module.findExportByName("libc.so", "process_vm_readv");
if (p) Interceptor.attach(p, {
    onEnter: function (args) {
        var pid = args[0].toInt32();
        var remote = args[3];                     // remote_iov
        var addr = remote.readPointer();
        var len = remote.add(Process.pointerSize).readPointer();
        console.log("[readv] pid=" + pid + " addr=" + addr + " len=" + len);
    }
});
```

**注意 iovec 结构**：参数是「数组指针 + 数组长度」，每个 iovec 是 `{base, len}` 两个指针（64 位下 16 字节）。上面代码读的是**第一个** iovec；要遍历全部数组要按 `n * 16` 步进。

### 路径 2：/proc/pid/mem

```bash
# 谁在读？
lsof | grep "/proc/.*/mem"
# strace 可见模式
openat(AT_FDCWD, "/proc/12345/mem", O_RDONLY) = 3
lseek(3, 0x7A12345678, SEEK_SET) = 0x7A12345678    # 可疑: 直接 seek 到大地址
read(3, buf, 8) = 8
close(3)
```

**判别特征**：`lseek` 到一个明显是堆/栈的大地址，然后只读很少的字节 —— 这是指针链遍历的典型形态。

### 路径 3：ioctl 内核驱动（最难检测）

```c
int fd = socket(AF_INET, SOCK_DGRAM, 0);
ioctl(fd, 601, &copy_mem_struct);      /* 自定义 cmd=601 */
```

特征：`socket` + `ioctl` 组合，且 `ioctl` 命令号不在标准集合内（标准是 `_IO`/`_IOR`/`_IOW` 编码，有固定位模式）。魔数通常 ≥ 0x600。

```javascript
var ioctl = Module.findExportByName("libc.so", "ioctl");
Interceptor.attach(ioctl, {
    onEnter: function (args) {
        var cmd = args[1].toInt32();
        if (cmd >= 0x600)                       // 自定义魔数区间
            console.log("[ioctl] fd=" + args[0].toInt32() +
                        " cmd=" + cmd + " arg=" + args[2]);
    }
});
```

## 检测 pagemap 类路径

若目标走 `/proc/pid/pagemap` 做 VA→PA 转换（见 `../native/virt-phys-memory.md`），特征是：

```bash
# 反复 lseek 到 VPN*8 的偏移
strace -e trace=openat,lseek,read -p $PID | grep pagemap
```

## 判据

| 观察 | 结论 |
|---|---|
| `strace` 出现 `process_vm_readv(pid, ...)` | 走 syscall 路径 |
| `strace` 出现 `openat(.../proc/N/mem)` + 大偏移 `lseek` | 走 /proc/pid/mem 路径 |
| `ioctl` 命令号 ≥ 0x600 | 走内核驱动路径（最隐蔽） |
| hook 打出具体 addr/len 且内容有意义 | 已定位读写的数据结构 |

**外部可观测的判据**：`strace` 的系统调用行 或 hook 日志里的 `(pid, addr, len)` 三元组 —— 不是「看到 ioctl 调用」就算定位完成，要看到**读的是哪个地址**。

## 坑

- **`iovec` 在 64 位下每个 16 字节**（两个 `void*`），不要按 8 字节步进。
- **`process_vm_readv` 的第一个参数顺序**：`pid, local_iov, liovcnt, remote_iov, riovcnt, flags` —— remote 在**第 4 个参数**（下标 3），不是第 2 个。
- **`lsof` 在新内核/Android 上可能不存在**，用 `/proc/*/fd` 遍历替代。
- **`ioctl` hook 会看到大量无关的标准命令**（终端、网络），必须按命令号过滤，否则噪音淹没。
- **`/proc/pid/mem` 的 read 长度很小不代表是恶意**，可能是调试器自身。
- **本机无 Android 设备**：`strace`/Frida 部分**需真机/模拟器，本机未验证**；判别特征基于已知的 syscall 语义。

## 相关

- `../native/virt-phys-memory.md` —— pagemap VA→PA 转换
- `../native/so-structure-audit.md` —— so 侧确认是否有驱动交互代码
- `overlay-rendering-hook.md` —— 读取内存的另一类典型用途
