# 虚拟地址 → 物理地址转换

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/apk-reverse/techniques/02-native/05-virt-phys-memory.md`
> **什么时候用**：需要绕过进程隔离，从内核/驱动级直接读写目标进程的物理内存 —— 通过 `/proc/pid/pagemap` 完成 VA→PFN 转换。

## 适用信号

- 代码里有 `/proc/%d/pagemap` 路径拼接
- 出现 `lseek` + `read` 8 字节的操作组合
- 位运算 `& (1<<63)` 检查页面存在位
- 变量名包含 `pfn` / `page_offset` / `v_pageIndex`

## 页表遍历原理

```
虚拟地址 (64-bit)
│
├── 页内偏移 (bits 0-11, 4KB 页) → page_offset
│
└── 虚拟页号 (VPN, bits 12+) → v_page_index
    │
    └→ /proc/pid/pagemap[v_page_index * 8]
       │
       └── 64-bit 页表项
           ├── bit 63        : 页面存在位 (Page Present)
           ├── bits 0-54     : 物理页帧号 (PFN)
           └── bits 55-62    : 软件标志（部分内核用 soft-dirty/page-ref 等）
```

## 前置

```powershell
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
$adb = (Resolve-ReverseToolSpec -Name 'adb').Command
& $adb shell su -c 'ls -la /proc/self/pagemap'
& $adb shell su -c 'zcat /proc/config.gz | grep CONFIG_PROC_PAGE_MONITOR'
```

**权限位应为 `-r--------`（仅 owner 可读）**，且需要 `CONFIG_PROC_PAGE_MONITOR=y`。读别人的进程还要满足 ptrace 权限或 root。

## 步骤

### 1. VA → PA 转换实现

```c
uint64_t virt_to_phys(pid_t pid, uint64_t vaddr) {
    long page_size = sysconf(_SC_PAGESIZE);        /* 通常 4096 */

    uint64_t v_page_index = vaddr / page_size;     /* 虚拟页号 */
    uint64_t page_offset  = vaddr % page_size;     /* 页内偏移 */
    uint64_t item_offset  = v_page_index * sizeof(uint64_t);  /* pagemap 每项 8 字节 */

    char path[64];
    snprintf(path, sizeof(path), "/proc/%d/pagemap", pid);
    int fd = open(path, O_RDONLY);
    if (fd < 0) return 0;

    if (lseek(fd, item_offset, SEEK_SET) < 0) { close(fd); return 0; }

    uint64_t pte = 0;
    if (read(fd, &pte, sizeof(pte)) != sizeof(pte)) { close(fd); return 0; }
    close(fd);

    if (!(pte & (1ULL << 63))) return 0;           /* 页面不在物理内存 */

    uint64_t pfn = pte & ((1ULL << 55) - 1);       /* PFN 在 bits 0-54 */
    return pfn * (uint64_t)page_size + page_offset;
}
```

### 2. 批量读取

```c
bool phys_read(mem_request_t *req) {
    uint64_t va = req->vaddr, end = req->vaddr + req->size, copied = 0;
    while (va < end) {
        uint64_t pa = virt_to_phys(req->pid, va);
        if (!pa) {                                  /* 页面被换出 */
            va = ((va / PAGE_SIZE) + 1) * PAGE_SIZE;
            continue;
        }
        size_t remain = PAGE_SIZE - (va % PAGE_SIZE);
        size_t to_read = (req->size - copied < remain) ? req->size - copied : remain;
        /* 通过 /dev/mem 或内核驱动直接读物理地址 */
        /* pwrite(fd_mem, req->buffer + copied, to_read, pa); */
        va += to_read;
        copied += to_read;
    }
    return copied == req->size;
}
```

### 3. 检测 pagemap 路径（用户态侧）

```bash
strace -e trace=openat,lseek,read -p $PID | grep pagemap
```

反复 `lseek` 到 `VPN*8` 的偏移再读 8 字节，就是 VA→PA 转换的指纹。

## 实战要点

1. **PFN 位宽随内核变化**（48-bit vs 55-bit），先确认 `uname -r`。
2. **KPTI/KASLR**：物理地址布局随机化，但 VA→PA 的**映射关系不变**，转换本身仍然成立。
3. **大页（HugePage）**：2MB/1GB 大页的 pagemap 条目编码不同，需额外处理。
4. **效率**：缓存 PFN→物理地址映射，避免反复读 pagemap。

## 判据

| 观察 | 结论 |
|---|---|
| `/proc/self/pagemap` 可读且位为 `-r--------` | 有 pagemap 权限 |
| `zcat /proc/config.gz` 含 `CONFIG_PROC_PAGE_MONITOR=y` | 内核支持 |
| strace 中出现 `lseek(...VPN*8)` + `read(fd, ..., 8)` | 走了 pagemap 路径 |
| 提取的 PTE bit63 为 1 | 该页在物理内存中，可转换 |

**外部可观测的判据**：strace 的 **`lseek` 偏移值等于 `VPN*8`** 且 read 长度为 8 —— 不是「看到 lseek 就算」。

## 坑

- **现代内核默认对非特权用户清零 PFN**：`pte` 会是 0，要 root。
- **bit 62~55 的 soft-dirty/page-ref 位被误当 PFN 会算出错误物理地址** —— 严格按 `bits 0-54` 取。
- **页面被换出时 bit63=0**，返回 0 表示「不在物理内存」，不是「转换失败」，调用方要区分。
- **大页条目编码不同**，直接按 4KB 算会错位。
- **每读一页都要 `open/lseek/read/close`** 的话开销极大，生产代码应保持 fd 打开只做 lseek。
- **本机无 Android 设备**：页表转换与物理读**需真机/模拟器 + root，本机未验证**；原理与判据基于已知的内核 ABI。

## 相关

- `kernel-procfs-driver.md` —— 驱动内部正是做这件事
- `../dynamic/memory-rw-hook.md` —— 用户态侧检测这些读写
- `so-structure-audit.md` —— 定位 so 中的 pagemap 调用点
