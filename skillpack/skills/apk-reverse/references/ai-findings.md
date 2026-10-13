# APK 逆向实战经验记录

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/apk-reverse/ai-findings/README.md`
> **什么时候用**：本次分析踩了坑、发现了可复用打法时，按本文的格式记录一条，避免重复踩坑。

## 何时必须记录一条 finding

- 发现一个可复用的 APK 分析路径、Hook 模式、工具组合或排障方法。
- 某工具在特定 APK / Android 版本下失败、弹窗或阻塞，并找到了稳定替代或 safe probe。
- 某类 APK 的指纹能稳定触发某个 crypto / unpack / 加固逆向流程。
- 一条路径被证据排除，能避免以后重复尝试。

## 记录格式

```text
时间:     YYYY-MM-DD
触发条件: 什么信号让你想到用这条经验
结论:     具体怎么做的
证据:     可复现的命令与真实输出（hook 日志行、脚本输出、偏移表）
复用:     下次遇到同类信号直接跳到哪一步
关键词:   k1, k2, k3
置信度:   高 / 中 / 低
```

## 本机已验证的经验（2026-10）

以下条目均在本机实跑验证过，输出可直接复现。

### F-001 `aapt2 link` 无法自建 APK，要用 apktool

- **触发**：想用 `aapt2 link -o app.apk` 造最小测试 APK。
- **结论**：`<工具根>\<分类>\<工具名>\build-tools\34.0.0\lib\android.jar` **不存在**，`aapt2 link` 报 `Unable to open '...android.jar': No such file or directory` + `error: failed to open APK: I/O error.`，无法产出 APK。
- **证据**：
  ```
  ziparchive W 10-10 00:26:47  2792 13300] Unable to open
    'D:/Tools/android-sdk/build-tools/34.0.0/lib/android.jar': No such file or directory
  error: failed to open APK: I/O error.
  ```
- **复用**：自建/最小 APK 一律用 `apktool b`（apktool 自带 aapt2）。参考 `dex-java/smali-injection.md`。
- **关键词**：aapt2, apktool, android.jar, 造样本
- **置信度**：高

### F-002 apktool 3.x 的 `apktool.yml` 数字不能加引号

- **触发**：手写 `apktool.yml` 后 `apktool b`。
- **结论**：`versionCode: '1'` 会抛 `java.lang.NumberFormatException: For input string: "'1'"`；必须写 `versionCode: 1`。
- **证据**：
  ```
  Exception in thread "main" java.lang.NumberFormatException: For input string: "'1'"
      at brut.androlib.meta.VersionInfo.readItem(SourceFile:102)
      at brut.apktool.Main.main(SourceFile:70)
  ```
- **复用**：手写 yml 时所有数值字段不加引号。
- **关键词**：apktool, apktool.yml, NumberFormatException
- **置信度**：高

### F-003 `$LINENO` 自解压：sed 行必须是 shell 头的最后一行

- **触发**：分析 shell 尾部嵌入 gzip payload 的样本。
- **结论**：边界算错时 `gzip -cd` **直接失败退出**（不是静默产出垃圾），因为错位后的前缀不是合法 gzip 流。
- **证据**（9 行 shell 头样本）：
  ```
  head.sh lines = 9  -> 边界应从第 10 行开始
  正确: 解压成功  len 93 magic b'\x7fELF' marker True
  错误(边界设 7): 解压失败(退出码 1)
  ```
- **复用**：先 `grep -n LINENO` 找 sed 行，再数 shell 头实际行数，边界 = 头行数 + 1。
- **关键词**：self-extracting, LINENO, gzip, sed, payload
- **置信度**：高

### F-004 `wc -l` 漏算无换行结尾的最后一行

- **触发**：数 shell 头部行数算 payload 边界。
- **结论**：对无结尾换行的文件，`wc -l` 比实际行数**少 1**。实测三行无换行结尾文件：`wc -l`=2、`grep -c ''`=3、`awk 'END{print NR}'`=3。
- **证据**：见 `packer/self-extracting-payload.md` 的「坑」一节。
- **复用**：数行数统一用 `awk 'END{print NR}'`。
- **关键词**：wc -l, 行数, 边界
- **置信度**：高

### F-005 r2 的 `~` 过滤不支持 `^`/`$` 锚点

- **触发**：想用 r2 精确过滤出 `.text` 节。
- **结论**：`iS~^\.text$` 输出**为空**；`iS~.text$` 仍会连 `ARM.text` / `.debug_frame$$$ARM.text` 一起带出。
- **证据**：
  ```
  == iS~.text ==
  7   0x00010aa0  ...  PROGBITS   .text
  8   0x00012150  ...  PROGBITS   ARM.text
  80  0x0006e5d8  ...  PROGBITS   .debug_frame$$$ARM.text
  == iS~^\.text ==
  (空)
  ```
- **复用**：把 `iS` 输出交给外部 awk 精确匹配（`$NF == ".text" { print }`），只命中真正的 `.text`。
- **关键词**：radare2, iS, 正则, 锚点
- **置信度**：高

### F-006 pyelftools 的 `e_machine` 返回字符串

- **触发**：写 so 结构分析脚本时做架构映射。
- **结论**：`elf.header["e_machine"]` 返回 **`'EM_ARM'`** 这样的**字符串**，不是整数 `0x28`；`int()` 转换会抛 `ValueError: invalid literal for int() with base 10: 'EM_ARM'`。
- **复用**：映射表用字符串键 `{"EM_ARM": "ARM32", "EM_AARCH64": "ARM64", ...}`。
- **关键词**：pyelftools, elftools, e_machine, ELF
- **置信度**：高

### F-007 objection 没有 `sslpinning` 这个 CLI 子命令

- **触发**：想用 `objection -g <pkg> sslpinning disable` 一把绕过 pinning。
- **结论**：本机 `objection --help` 顶层 `Commands:` 只有 `api` / `patchapk` / `patchipa` / `run` / `signapk` / `start` / `version`，**没有 `sslpinning`**。
- **复用**：进交互控制台 `objection -g com.target.app` 后再执行 `sslpinning disable`；或走 `patchapk` 路线。
- **关键词**：objection, sslpinning, pinning, CLI
- **置信度**：高

### F-008 `apksigner verify` 对 v2-only 签名会误报失败

- **触发**：用 `--v1-signing-enabled false` 签名后 `verify` 失败。
- **结论**：报 `DOES NOT VERIFY / ERROR: Missing META-INF/MANIFEST.MF`。这是**校验器按 minSdk 要求 v1**，不是签名坏了。加 `--min-sdk-version 24` 后即 `Verifies`。
- **证据**：
  ```
  # 默认
  DOES NOT VERIFY
  ERROR: Missing META-INF/MANIFEST.MF
  # 加 --min-sdk-version 24
  Verifies
  Verified using v1 scheme (JAR signing): false
  Verified using v2 scheme (APK Signature Scheme v2): true
  ```
- **复用**：在 `META-INF` 里找不到签名文件时，先看 verify 的 scheme 行再下结论。
- **关键词**：apksigner, v1, v2, v3, META-INF, 签名
- **置信度**：高

### F-009 RC4 的 signed/unsigned 不影响 KSA 结果

- **触发**：怀疑 RC4 实现的 key 用 `signed char` 会算错。
- **结论**：`(j + S[i] + key[i % key_len]) % 256` 即使 key 按 `signed char` 提升为负值，取模后与 `unsigned char` **逐字节相同**（用 key=`ff81c0` 实测 KSA 输出无差异）。signedness 只在**没有取模**的比较/移位处才有影响。
- **复用**：不必为这个改 Python 复现；但魔改 RC4 里有 `S[i] == key[j]` 这类比较时要留意。
- **关键词**：RC4, KSA, signed char, unsigned
- **置信度**：高

### F-010 本机无 Android 设备

- **触发**：所有需要 Frida attach / adb / dumpsys / 安装运行的部分。
- **结论**：本机 `adb devices` 无设备，无法执行任何动态验证。所有 Frida 脚本、hook 判据、注入/加载流程均标注「需真机/模拟器，本机未验证」。
- **复用**：动态分析结论必须标注未验证，并要求在目标设备上复验后补记录。
- **关键词**：环境, adb, frida, 未验证
- **置信度**：高

## 待补经验（需真机/模拟器）

以下方向一旦在真机上跑通，应按上面的格式补充：

- Frida `RegisterNatives` hook 的实际输出格式（类名 + 签名 + RVA）
- `find-vm-dispatch.py` 在真实加固 so 上的命中情况
- Stalker trace 解释器 dispatch 的实际输出
- 各家加固（爱加密/梆梆/乐固）的实际 so 特征组合
