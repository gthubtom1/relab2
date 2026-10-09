# 自解压 Payload 与脚本嵌入

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/apk-reverse/techniques/07-packer/02-self-extracting-payload.md`
> **什么时候用**：APK 里的脚本或二进制把 payload（`.so`/`.ko`/可执行文件）嵌在自身尾部，运行时自解压执行后自毁。

## 适用信号

- shell 脚本大小异常（> 100KB 的非压缩脚本）
- 脚本末尾出现 ELF header 特征（`\x7FELF`）
- 文件被 `gzip -cd` 管道解码后执行
- 临时目录中出现随机文件名后立即消失

## 模式 1：Shell + 二进制嵌入

```bash
#!/system/bin/sh
folders=($(find /data/ -maxdepth 1 -mindepth 1 -type d))
random_folder="${folders[RANDOM % ${#folders[@]}]}"
unique_name="$(date +%s | sha256sum | base64 | head -c 32)"

# 关键: LINENO 定位脚本自身, sed 截取尾部二进制
sed -n "$((LINENO+1)),$ p" < "$0" | gzip -cd > "${random_folder}/$unique_name"
chmod 700 "${random_folder}/$unique_name"
(sleep 5; rm -f "${random_folder}/$unique_name") 2>/dev/null &
"${random_folder}/$unique_name" ${1+"$@"}
exit $?
# ↓ LINENO 行以下全是被 gzip 压缩的二进制数据 ↓
<compressed binary data>
```

技巧拆解：

| 技巧 | 作用 |
|---|---|
| `$LINENO` | 当前行号，精确定位 script/data 边界 |
| `sed -n "$((LINENO+1)),$ p"` | 从下一行截到文件末尾 |
| `gzip -cd` | 解压到 stdout 并管道到文件 |
| 随机目录 + 随机文件名 | 躲避路径扫描 |
| `sleep 5; rm -f` | 延时自毁，确保进程已启动 |

## 步骤：手动提取 payload

**核心是找对边界行号。**

### 1. 定位边界

```bash
grep -n 'LINENO\|sed -n' payload.sh
```

### 2. 从边界之后提取并解压

```bash
LAST=$(wc -l < head.sh)          # shell 头部的总行数
tail -n +$((LAST+1)) payload.sh | gzip -cd > extracted.bin
```

### 3. 确认产物

```bash
file extracted.bin        # 期望 ELF 32-bit / ELF 64-bit
```

### 本机实测证据

构造一个 9 行 shell 头 + gzip payload 的自解压脚本，实测输出：

```
=== 文件大小 ===
-rwxrwxrwx 1 somebody somegroup 471 Oct 10 00:31 payload.sh
=== LINENO 边界（head 部分行数）===
head.sh lines = 9  -> 边界应从第 10 行开始
=== 提取验证 ===
-rwxrwxrwx 1 somebody somegroup 93 Oct 10 00:31 extracted.bin
--- magic ---
len 93 magic b'\x7fELF' ELF64
marker found: True
```

**边界算错会怎样**（同一个样本，故意把边界设为第 7 行而不是第 10 行）：

```
--- 错误示范：假定 LINENO 是 6，7,$ p 从第7行开始 ---
解压失败(退出码 1)
--- 正确做法：sed 行必须是 head 的最后一行，从下一行开始取 ---
解压成功
len 93 magic b'\x7fELF' marker True
```

**判据**：解出的文件前 4 字节必须是 `7f 45 4c 46`（`\x7fELF`），且长度 > 0。`gzip -cd` 退出码非 0 = 边界错了（gzip 会报 CRC/格式错，不是静默产出垃圾）。`elf_class` 只能到 ELF32/ELF64，用真实 `file` 或读 e_ident 第 4 字节判断。

## 模式 2：C Header 嵌入（.ko 驱动）

```c
/* dev4.14.117.ko.h */
#ifndef DEV_KO_H
#define DEV_KO_H
unsigned char dev_ko[] = {
    0x7f, 0x45, 0x4c, 0x46, 0x02, 0x01, 0x01, 0x00,
    /* ... 整个 .ko 文件作为字节数组嵌入 ... */
};
unsigned int dev_ko_len = 24680;
#endif
```

```c
#include "dev4.14.117.ko.h"

void load_driver(void) {
    char path[256];
    sprintf(path, "/data/local/tmp/driver_%d.ko", getpid());
    FILE *fp = fopen(path, "wb");
    fwrite(dev_ko, 1, dev_ko_len, fp);
    fclose(fp);
    chmod(path, 0600);
    init_module(path, "");   /* syscall finit_module */
    unlink(path);            /* 加载后立即删除 */
}
```

提取方式：在 so 里搜 `0x7f, 0x45, 0x4c, 0x46` 字节序列起点，到 `dev_ko_len` 为止。

## 模式 3：编译产物加密包装

```bash
#!/bin/bash
AA="libs/arm64-v8a/target.so"
count=1
mz="SC.sh"

# 生成自解压包装 + 压缩原始 so 并追加
echo 'folders=($(find /data/...)); ...; sed -n "$((LINENO+1)),$ p" < "$0" | gzip -cd > ...' > "$count$mz"
gzip < "$AA" >> "$count$mz"
```

## 判据

| 观察 | 结论 |
|---|---|
| `grep -n LINENO` 命中 + 文件尾部有大段高熵数据 | 自解压 payload |
| `tail -n +N ... \| gzip -cd` 退出码 0 且产物 magic = `7f 45 4c 46` | 提取成功 |
| `gzip -cd` 退出码非 0 | 边界行号算错，重数 shell 头行数 |
| 提取产物可被 `diec -b` 解析 | 是真 ELF，可转 so 分析 |

**外部可观测的判据**：`gzip -cd` 的退出码 + 产物前 4 字节 —— 不是「解压出东西了」就算成功（边界偏移可能产出部分可解压的垃圾）。

## 坑

- **`$LINENO` 依赖 sed 行是 shell 头的最后一行**：中间插入注释会整体偏移，必须实数行数。
- **`wc -l` 会漏算无换行结尾的最后一行**：对无结尾换行的文件实测 `wc -l`=2、`grep -c ''`=3、`awk 'END{print NR}'`=3，边界算错就会多取/少取一行。用 `awk 'END{print NR}'` 或 `grep -c ''` 数行数。
- **`gzip -cd` 对边界错位可能仍返回 0**：如果错位后前缀恰好也是合法 gzip 流，务必校验 magic。
- **`chmod 700` 之后立刻执行再删**，提取时不需要保持权限，用 Python 写文件即可。
- **`.ko` 驱动嵌入用 `0x7f,0x45,0x4c,0x46` 作为起点搜索**，但 so 里可能多处出现该序列，取第一处通常对，需用 `dev_ko_len` 交叉验证长度。

## 相关

- `vmp-dex2c-detection.md` —— 提取出 ELF 后判断是否加固/虚拟化
- `obfuscation-detection.md` —— 提取后的 so 混淆形态识别
- `../native/so-structure-audit.md` —— so 结构体检
