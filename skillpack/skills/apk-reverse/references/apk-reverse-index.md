# APK 逆向篇目索引

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/apk-reverse/README.md` + `../../ops/README.md`（上游文件，未随本包落地）
> **什么时候用**：需要找 APK 逆向的具体技法文档时，先从这里选分类和篇目。

## 标准工作流

```text
APK 哈希/Manifest
  → jadx / apktool 静态分析
    → Java / Native 调用链
      → Frida 动态验证
        → crypto / network / dex dump
          → Patch / 重打包
            → 安装验活
```

不确定走哪条路时，先看 `attack-network.md` 的分叉决策图。

## 目录

### dex-java — DEX / Java（2）

- `dex-java/entry-point-tracing.md` — 启动链追踪、exported 组件暴露面
- `dex-java/smali-injection.md` — Smali 注入与 DEX 修改（含重建/签名全链路）

### native — Native / SO（5）

- `native/so-structure-audit.md` — **SO 体检基线**：架构、符号、JNI 入口、构造函数
- `native/jni-register-natives-tracing.md` — RegisterNatives 追踪与 native 入口还原
- `native/il2cpp-offset-discovery.md` — Unity IL2CPP 偏移发现与指针链
- `native/ue4-offset-hunting.md` — UE4 引擎偏移发现
- `native/kernel-procfs-driver.md` — 内核驱动 proc 节点读写
- `native/virt-phys-memory.md` — 虚拟地址 → 物理地址转换（pagemap）

### crypto — 加密（2）

- `crypto/game-encryption-patterns.md` — 三层加密识别与 key/IV 提取
- `crypto/rc4-custom-crypto.md` — 自定义 RC4 与组合模式

### network — 网络（3）

- `network/tls-pinning-unpinning.md` — TLS Pinning 定位与绕过
- `network/game-protocol-hook.md` — 协议 Hook 与封包分析
- `network/license-verification-bypass.md` — 在线验证系统分析与绕过

### dynamic — 动态插桩（3）

- `dynamic/memory-rw-hook.md` — 进程内存读写检测与 Hook
- `dynamic/overlay-rendering-hook.md` — Overlay 渲染与 ImGui 检测
- `dynamic/touch-input-hook.md` — 触摸输入 Hook 与注入分析

### packer — 壳与混淆（5）

- `packer/obfuscation-detection.md` — 编译期混淆检测（OLLVM / UPX / 字符串加密）
- `packer/self-extracting-payload.md` — 自解压 payload 提取
- `packer/vmp-dex2c-detection.md` — **VMP/dex2c 形态判定**（先看这个）
- `packer/vmp-dump-trace-recovery.md` — VMP 脱壳与语义还原
- `packer/vmp-anti-debug-bypass.md` — 反调试检测与绕过

### patch-repack — Patch / 重打包（2）

- `patch-repack/so-injection-repack.md` — Native SO 注入与重打包
- `patch-repack/signature-integrity-bypass.md` — 签名与完整性检查绕过

### 索引

- `attack-network.md` — 分叉决策图（不知道走哪条路时先看）

## 配套脚本

本技能包 `scripts/` 下：

| 脚本 | 用途 | 状态 |
|---|---|---|
| `smali-stub-ratio.py` | 统计 smali 空壳率，判定是否加固 | 本机已验证 |
| `find-vm-dispatch.py` | 扫 ARM/ARM64 so 的解释器 dispatch 特征 | 本机已验证 |
| `so-structure-audit.py` | so 节区/符号/build-id/构造函数体检 | 本机已验证 |
| `decode.ps1` / `frida-run.ps1` / `rebuild-sign-install.ps1` / `manifest-summary.ps1` | 原有的解包/动态/重建/Manifest 封装 | — |

脚本依赖 `capstone` / `pyelftools`，一律用 `D:\EXE\python\python.exe` 跑：

```powershell
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
$r = Resolve-ReverseToolSpec -Name 'python'
& $r.Command 'C:\relab2\skillpack\skills\apk-reverse\scripts\find-vm-dispatch.py' libtarget.so
```

## 写作规范

每篇按 **适用信号 → 前置 → 步骤 → 判据 → 坑 → 相关** 组织。

- **判据必须外部可观测**：「日志出现 `Breakpoint 0 hit`」是判据，「有输出」不是；「`apksigner verify` 输出 `Verifies`」是判据，「构建成功」不是。
- **命令要能真跑**：不确定的标注「未在本机验证」。
- **不编造常量**：示例偏移要明确标注是示例值。
- **本机无 Android 设备**：所有 Frida hook / adb / dumpsys / 安装运行部分均标注「需真机/模拟器，本机未验证」，不编造运行结果。

## 快速自检清单

- [ ] 记下 APK 的 SHA256 / 包名 / 版本 / ABI
- [ ] `aapt2 dump badging` 拿到包名与 LAUNCHER activity
- [ ] `so-structure-audit.py` 体检所有 so（确认 ABI、是否加固、是否有 JNI 导出）
- [ ] `smali-stub-ratio.py` 确认 Java 层是否被掏空
- [ ] 被掏空 → `packer/vmp-dex2c-detection.md` 判形态
- [ ] 动态分析前先过 `packer/vmp-anti-debug-bypass.md`
- [ ] 每次 patch 后按 `patch-repack/signature-integrity-bypass.md` 复验
