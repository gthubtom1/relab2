# PORTABLE.md · 换机工具清单

> **原则**：只留「商业许可 / 付费才提供 / 中文小众难找」的。GitHub 和 winget 一键可得的，换机时现场装。
> **现状**：`D:\Tools` 共 1.26 GB / 7 项，拷贝即用。
> **来源**：`C:\CTFReBox52\T00Ls`（吾爱破解工具包，绿色版）

---

## 1. `D:\Tools` 里有什么（拷贝这部分就行）

| 工具 | 体积 | 为什么留 |
|---|---|---|
| **IDA Pro 8.3 Portable** | 677 MB | **商业付费**，技能包引用 346 次，逆向主力 |
| **JEB Decompiler 3.19.1 Pro** | 373 MB | **商业付费**，APK 原生 smali + 混淆识别，jadx 覆盖不了 |
| `pack\Unpackers\` | 143 MB | 脱壳工具全套（Themida脱壳机/AutoEye/InnoExtractor…），**付费服务才给 Themida 脱壳机** |
| `android\AndroidKiller_fix` | 56 MB | 加固脱壳，已停更，网上找不到原件 |
| `android\Android逆向助手_v2.2` | 16 MB | 中文实操工具 |
| `android\搞机工具箱11.0.1` | 14 MB | 含 adb 1.0.41 |
| `disasm\GDA4.11.exe` | 6 MB | DEX 分析器，官网已下架 |

---

## 2. 换机三步

### 第 1 步 · 拷贝

```powershell
robocopy <旧机>\D:\Tools\ D:\Tools\ /E /MT:8
```

### 第 2 步 · 装运行时（一条命令）

```powershell
winget install Python.Python.3.12
winget install Git.Git
winget install OpenJS.NodeJS.LTS
winget install Microsoft.DotNet.SDK.8
winget install Microsoft.OpenJDK.21
winget install Google.PlatformTools      # adb 正式版
winget install 7zip.7zip
```

### 第 3 步 · 装逆向工具链

```powershell
# Python 生态（自动化方向，技能包 §6）
pip install capstone unicorn lief z3-solver qiling yara-python
pip install frida-tools objection
pip install "angr"                       # 注意：会把 z3 钉到 4.13，别手动升 z3

# APK 方向（技能包引用最高的四个）
winget install --id Google.PlatformTools
# jadx  : GitHub releases zip → D:\Tools\android\jadx，bin 加 PATH
# apktool: GitHub Apktool jar + 自建 apktool.bat 包装
# apksigner/zipalign: 装 Android SDK build-tools

# 反编译/动态（无 IDA 时的开源替代）
# Ghidra : GitHub releases → D:\Tools\disasm\ghidra，需 JDK 21
# x64dbg : GitHub snapshots → D:\Tools\debug\x64dbg
# DIE    : GitHub releases → D:\Tools\pe\die，用 diec.exe（CLI）
# dnSpyEx: GitHub releases → D:\Tools\dotnet（商用替代品是 .NET Reactor 之类）

# 协议方向（技能包只认 tshark）
winget install Wireshark.Wireshark        # 装 Npcap 驱动

# .NET 方向
dotnet tool install -g ilspycmd
```

---

## 3. 验证（装完跑一遍）

```powershell
java -version                  # 期望 21.x
adb version                    # 期望 1.0.4x
jadx --version                 # 期望 1.5.x
java -jar apktool.jar --version
tshark -v                      # 期望 TShark 4.6.x
D:\Tools\disasm\IDA Pro 9.3\idat.exe -A <脚本> <样本>   # 无头模式，勿用 -h
```
（历史：此行原为 8.3 路径，2026-10-10 删除 8.3 后改为当前唯一的 9.3 路径。）

Python 生态验证：
```powershell
python -c "import capstone, unicorn, lief, z3, qiling, angr; print('OK')"
```

---

## 4. 三条纪律

1. **GUI 二进制禁经 bash 同步启动** —— 弹窗等输入、零 stdout、进程永不退出。
   IDA/JEB/Ghidra/x64dbg/dnSpy/010 等 GUI 一律只能人工在桌面侧操作。
2. **IDA 无头模式**：`idat.exe` 只认 `-A` + 脚本，**`-h` 会挂住**。
3. **`D:\Tools` 里的都是 GUI 或付费工具** —— 能自动化的只有 JEB 的 `jeb_wincon.bat`。

---

## 5. 被删掉的（源目录还在，随时可补）

`C:\CTFReBox52\T00Ls` 仍保留全量（4.1 GB）。如果以后需要某工具，从那里补：

| 想补什么 | 从哪取 |
|---|---|
| Ghidra / x64dbg / DIE / dnSpy / jadx / Wireshark 等 | `T00Ls\` 对应分类目录 |
| 010 Editor（138 MB） | `T00Ls\Editors\010 Editor` |
| Sysinternals / Sandboxie | `T00Ls\Anti Rootkit\` `T00Ls\Star\` |
| hashcat / CyberChef | `T00Ls\Cryptography\` |
| PE 系列 12 个（PE-bear/CFF/LordPE/PEiD…） | `T00Ls\PEtools\` |
| PE 壳样本（Themida/UPX/VMP，448 MB） | `T00Ls\PackerAndUnpackers\Packers\` |
| CTF 笔记 409 篇 | `T00Ls\Note\` ← **建议单独备份到网盘，比工具值钱** |

---

## 6. 体积账

| | |
|---|---|
| 云盘同步（D:\Tools） | **1.26 GB** |
| 换机现场安装 | 约 2 GB（winget/pip/GitHub） |
| 保留源目录（可选） | 4.1 GB @ `C:\CTFReBox52` |