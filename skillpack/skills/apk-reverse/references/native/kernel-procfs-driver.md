# 内核驱动注入：proc 节点读写

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/apk-reverse/techniques/02-native/04-kernel-procfs-driver.md`
> **什么时候用**：应用使用 Linux 内核驱动（`.ko`）通过 `/proc` 节点实现跨进程内存读写 —— Android 平台最高权限的读写方式，能绕过 SELinux/seccomp。

## 适用信号

- `lsmod` 或 `/proc/modules` 中出现未知模块名
- `/proc/` 下出现非标准节点名（如 `/proc/wanbai`、`/proc/CheckMe`）
- dmesg 有「Driver initialized」或厂商签名
- 应用执行了 `insmod` 命令

## 前置

```powershell
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
$adb = (Resolve-ReverseToolSpec -Name 'adb').Command
& $adb devices
& $adb shell su -c 'uname -r'          # 内核版本，决定用哪个 .ko
& $adb shell su -c 'cat /proc/modules'
& $adb shell su -c 'ls -la /proc | head -50'
```

## 步骤

### 1. 自解压 shell 注入脚本

```bash
#!/system/bin/sh
# 环境检查、root 检查 ...
# 关键: 从脚本自身提取 .ko
sed "1,/^#BY x Kitten x 离/d" "$0" > /data/tmpf
chmod u+x /data/tmpf
insmod /data/tmpf
if [ $? -eq 0 ]; then
    echo "驱动加载成功"
    rm /data/tmpf
    dmesg -C                      # 清空内核日志防止检测
else
    echo "驱动加载失败, 5秒后重启"
    sleep 5; reboot
fi
exit 0
#BY x Kitten x 离
# ↓ 此处开始是 .ko 二进制数据, shell 不会执行 ↓
```

这里的边界是**标记行**而不是行号，比 `$LINENO` 方案更稳：`sed "1,/标记/d"` 按内容匹配，插入注释不会破坏边界。提取手法见 `../packer/self-extracting-payload.md`。

### 2. 驱动 proc 节点创建

```c
/* 内核模块核心: 创建 /proc 节点供用户态读写 */
static struct proc_dir_entry *proc_entry;

static ssize_t proc_read(struct file *file, char __user *buf,
                         size_t len, loff_t *offset) {
    /* 接收用户态传来的 COPY_MEMORY 结构
     * → walk page tables → read physical memory → copy_to_user */
    return len;
}

static ssize_t proc_write(struct file *file, const char __user *buf,
                          size_t len, loff_t *offset) {
    /* 接收 COPY_MEMORY 结构 → walk page tables → write physical memory */
    return len;
}

static struct file_operations proc_fops = {
    .owner = THIS_MODULE,
    .read  = proc_read,
    .write = proc_write,
};

static int __init driver_init(void) {
    proc_entry = proc_create("driver_name", 0666, NULL, &proc_fops);
    printk("/proc/driver_name created\n");
    return 0;
}
```

### 3. 用户态通过 /proc 节点调用

```c
/* 打开 proc 节点, 写入读请求, 再读结果 */
int fd = open("/proc/driver_name", O_RDWR);
struct copy_memory cm;
cm.pid = target_pid;
cm.addr = 0x7A12345678;
cm.buffer = output_buf;
cm.size = 8;
write(fd, &cm, sizeof(cm));      /* 发送读请求 */
read(fd, &cm, sizeof(cm));       /* 读取结果 */
/* output_buf 现在含目标进程 addr 处的 8 字节 */
close(fd);
```

**用户态协议完全自定义** —— 结构体布局、命令语义、返回值都是驱动作者定义的，要靠反汇编 so 里的 `ioctl`/`read`/`write` 调用反推。

### 4. 检测 proc 节点

```powershell
& $adb shell su -c 'ls -la /proc | Select-String -NotMatch "^\s*[cd]|^total|^d.*\s\.$|^d.*\s\.\.$"'
& $adb shell su -c 'cat /proc/modules'
& $adb shell su -c 'dmesg | Select-String -Pattern "initialized|created"'
```

标准 `/proc` 节点都是已知名字，**不在已知清单里的就是可疑节点**。

## 驱动隐藏技术

```c
/* 1. 不注册到 sysfs（避免在 /sys/module 中可见） */
/* 2. 随机化 proc 节点名: /proc/a7f3b2c1 */
/* 3. 使用合法驱动名伪装: /proc/sched_debug 等 */
/* 4. 定时清理 dmesg: system("dmesg -c > /dev/null"); */
```

## 多内核版本适配

```bash
kernel=$(uname -r | cut -d. -f1,2)
case "$kernel" in
    4.9.*)  ko_file=driver_4.9.ko  ;;
    4.14.*) ko_file=driver_4.14.ko ;;
    4.19.*) ko_file=driver_4.19.ko ;;
    5.4.*)  ko_file=driver_5.4.ko  ;;
    5.10.*) ko_file=driver_5.10.ko ;;
    5.15.*) ko_file=driver_5.15.ko ;;
    6.1.*)  ko_file=driver_6.1.ko  ;;
    6.6.*)  ko_file=driver_6.6.ko  ;;
    *) exit 1 ;;
esac
insmod $ko_file
```

实战中会预备多个内核版本的 `.ko`，运行时按 `uname -r` 选择。

## 判据

| 观察 | 结论 |
|---|---|
| `/proc/modules` 有非常规模块名 | 存在内核驱动 |
| `/proc/` 下有不在标准清单的节点 | 驱动创建了自定义节点 |
| 节点权限是 `0666` 且可 `read`/`write` | 内存读写通道 |
| dmesg 被清空（无任何内核日志） | 主动隐藏行为 |

**外部可观测的判据**：`ls /proc` 的**节点清单** + `cat /proc/modules` 的**模块名** —— 不是「权限很大就觉得是驱动」。

## 坑

- **`.ko` 必须匹配内核版本和架构**，符号版本（` vermagic`）不对会 `insmod` 失败。
- **`proc_create` 的权限 0666 意味着任何进程可访问**，这是最明显的检测线索。
- **`/proc/<pid>/mem` 和 `/proc/<pid>/maps` 的访问受 ptrace 权限约束**，而驱动走页表遍历绕过了这一层 —— 这是它比 syscall 路径隐蔽的根本原因。
- **内核版本的 `vermagic` 要在 so 里能对上**，反汇编时先看 `.modinfo` 节区。
- **`dmesg -C` 需要 root**，且新内核有 `kernel.dmesg_restrict` 限制。
- **本机无 Android 设备**：驱动加载与 proc 交互**需真机/模拟器 + root，本机未验证**。

## 相关

- `virt-phys-memory.md` —— 驱动内部的页表遍历原理
- `../dynamic/memory-rw-hook.md` —— 从用户态侧检测这些读写
- `../packer/self-extracting-payload.md` —— `.ko` 的自解压提取
