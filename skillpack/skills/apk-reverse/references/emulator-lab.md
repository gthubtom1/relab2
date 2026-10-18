> ⚠️ **2026-10-18 复核：本机当前 `adb devices` 为空、无模拟器在跑**（`LDPlayer` 进程未启动）。
> 本文记录的「雷电 14 实测」是**当时那一轮**的状态，不是现在。要用先自己起模拟器再验。

# 安卓模拟器能力层（第三方模拟器 · 夜神 / 雷电 / 蓝叠 / MuMu / MEmu / 官方 AVD）

> **一句话**：真机是首选，模拟器是**唯一能随时拿到 Android 12+/13/14 环境**的路。
> 本包已经把能力层铺好 —— 模拟器装上以后 `emulator-lab.ps1` 自动认出来就能用，不需要改代码。
>
> **配套脚本**：`scripts/emulator-lab.ps1`（发现 / 连接 / 控制 / 抓包 / 动态调试 / 测试）
> **什么时候读**：需要 Android 12+ 环境、装不上包、要抓模拟器里的包、或要在模拟器上动态调试时。

---

## 适用信号（Recognition signals）

出现下列任一情况，说明该走模拟器而不是真机：

- 设备 SDK 低于 APK 的 minSdk，装不上（见经验卡 `android-minsdk-gate-is-not-bypassable`）
- 手机 USB 线常掉线，做不了长时间动态调试
- 需要**同时**跑多个 Android 版本对比行为
- 样本带模拟器检测，需要正是在模拟器上复现它（而不是绕过它）
- 自动化测试要一台机器上开 N 个实例

## 前置（Entry conditions）

**只有 adb 是硬前置。** 其余（tcpdump / mitmproxy / frida）缺失时脚本会点名说缺什么。

模拟器本身**必须已经启动**，且厂商设置里的「ADB 调试 / 远程连接」已打开。
模拟器装在 `D:\Program Files\<厂商>\` 或 `C:\Program Files\<厂商>\` 下是常态 ——
不在工具根、也不在 PATH，所以探测层通常认不出厂商 CLI；这时走「手动起 + `connect -Auto`」。

> **2026-10-11 实测补充（雷电 14；安装路径由探测层现查，不要写死）**：
>
> | 事实 | 值 |
> |---|---|
> | adb 端口 | **2222**（不是雷电 9 的 5555-5561） |
> | adb 别名 | `emulator-5554`（真实端口 2222 也会注册成这个别名） |
> | 控制 CLI | `ldconsole.exe`，`list2` 格式与 9 一致 |
> | 进程名 | `dnplayer.exe`（UI）+ `Ld9BoxSVC.exe`（服务）+ `Ld9BoxHeadless.exe`（虚拟机） |
> | `adb root` | **不可用**（production build，`adbd cannot run as root`） |
> | 系统 | Android 14 / SDK 34 / x86_64，abilist 含 arm64-v8a |
> | tcpdump / curl | 自带；busybox 没有 |
>
> 两条由此得出的规则：
> 1. **端口必须扫** —— 版本不同端口就变，装在非默认目录时更会变。
> 2. **`emulator-NNNN` 与 `127.0.0.1:NNNN` 是两种形式**：前者是 adb 给雷电的别名
>    （别名里的数字是 console 端口减一，与真实 adb 端口无关），后者是真实 TCP 端口，
>    蓝叠用后者。早期版本一律按尾部数字猜厂商，把雷电 14 的 `emulator-5554`
>    判成了蓝叠 —— 已按形式判定修掉。

---

## 步骤（Working method）

### 一、选型：真机优先，模拟器补位

| 方案 | 电脑内存 | 启动 | 抗 APP 检测 | 能拿到 Android 12+ | agent 全自动 |
|---|---|---|---|---|---|
| **真机（首选）** | **0** | 秒开 | **是** | 看手机 | 是 |
| 第三方模拟器 | 1.5–3 GB 常驻 | 30–120 秒 | 否 | **是** | 是（本脚本） |
| 官方 AVD | 2 GB | 1–5 分钟 | 否 | 是 | 是（本脚本） |

> 不要为了跑模拟器去开 Windows「虚拟机平台」（HypervisorPlatform / WHPX）：
> 需要管理员 + 重启，且**会削弱 WinDbg 内核调试能力**。第三方模拟器（MuMu / 雷电 / 夜神）
> 自己带虚拟化引擎，不依赖 WHPX —— 这是它们相对官方 AVD 的实际优势。

### 二、接上模拟器（三步，不猜）

```bash
# 1. 手动启动模拟器（或用厂商 CLI，见下）
# 2. 在模拟器设置里打开「ADB 调试 / 远程连接」
# 3. 一条命令接管
powershell -File scripts/emulator-lab.ps1 connect -Auto
```

`connect -Auto` 的发现走**三条独立路径**并合并去重，任何一条命中即可：

| 路径 | 手段 | 覆盖 |
|---|---|---|
| a | 厂商管理 CLI 自报端口 | MuMu 走 `MuMuManager.exe info -v all` 拿 JSON，最准 |
| b | 已开端口扫描 | 雷电 / 夜神 / MEmu / 蓝叠的多开实例 |
| c | `adb devices` 已有条目 | 已连过一次的实例 |

**为什么必须三路都要**：端口写死的脚本换个模拟器就废（每家不同、多开会变、用户能自己改）。

### 三、各家控制接口与端口

端口表来自 MAA1999/M9A 官方文档（MAA 同时支持这些模拟器，维护者把各家端口
编成了一张表）；CLI 语法来自各家官方帮助页。**这张表只用来缩小扫描范围，
不作为判据** —— 真端口以运行时探测为准。

| 厂商 | adb 端口 | 控制 CLI | 启停语法 |
|---|---|---|---|
| MuMu 模拟器 12 | `16384` `16416` `16448` `16480` `16512` `16544` `16576` | `MuMuManager.exe` | `control -v <i> launch\|shutdown\|restart` |
| 雷电 LDPlayer 9 | `emulator-5554` / `5555` `5557` `5559` `5561` | `ldconsole.exe` | `launch --index <i>` / `quit --index <i>` / `reboot --index <i>` |
| 夜神 Nox | `62001` `62025` `62065` | `NoxConsole.exe` | `launch -index <i>` / `quit -index <i>` / `reboot -index <i>` |
| MEmu | `21503` `21505` | `memuc.exe` | `start -i <i>` / `stop -i <i>` / `restart -i <i>` |
| 蓝叠 | `5555` `5556` `5565` `5575` `5585` `5595` | 无官方实例 CLI | 只能 `HD-Player.exe --instance <name>`，实例名不猜 |
| 官方 AVD | `emulator-5554`（console 端口减一） | `emulator.exe` | `-avd <name>` |

蓝叠没有可脚本化的实例启停接口：脚本会直接报「需手动起」，**不猜实例名**。

### 四、装包前先对画像

```bash
# 一次读完 API 级别 / ABI / root / 抓包工具现状
powershell -File scripts/emulator-lab.ps1 profile
```

`profile` 读 `ro.build.version.sdk` 与 `ro.product.cpu.abi`。这两个数决定两件事：
装不装得上（minSdk），以及 frida-server 该推哪个架构的包。

### 五、抓包：三层，按需要选

| 层 | 命令 | 拿到什么 | 代价 |
|---|---|---|---|
| ① 设备侧 | `emulator-lab.ps1 pcap tcpdump` | 设备内全量包（含回环） | 设备需有 tcpdump |
| ② PC 侧 | `emulator-lab.ps1 iflist` → `pcap dumpcap -Interface <n>` | 虚拟网卡上的包，不动设备 | 需先认接口 |
| ③ 解密 | `emulator-lab.ps1 proxy on -Port 8080` | **HTTP(S) 明文** | 需装 CA + 改全局代理 |

②的接口名要先看：

```bash
powershell -File scripts/emulator-lab.ps1 iflist
```

模拟器流量走本机虚拟网卡（`\Device\NPF_{…}` / VMware / vEthernet 之类），
不指定就抓到物理网卡 —— 表现为「抓了半天什么都没有」。

### 六、mitm CA：用户证书不够用

Android 7+ 起，**app 默认不信任用户安装的 CA**，只认系统证书。这是抓包最常见的坑。

系统证书的文件名是 CA 证书的 **MD5 指纹**，每两字节一段、点分隔、全大写：

```bash
# 1) 生成（证书落在 ~/.mitmproxy/）
mitmproxy --listen-port 8080

# 2) 推并算出系统证书文件名
powershell -File scripts/emulator-lab.ps1 cert install -Serial 127.0.0.1:16384

# 3) 升级成系统证书（模拟器一般有 adb root）
adb -s 127.0.0.1:16384 root
adb -s 127.0.0.1:16384 remount
# 把 /data/local/tmp/mitm-ca.cer 复制到 /system/etc/security/cacerts/<上面的文件名>，chmod 644
```

模拟器大多预置 root（`adb root` 直接成功），所以这条路径比在真机上容易得多。

### 七、动态调试：frida-server 三个坑

1. **版本铁律**：设备端 `frida-server` 与本机 `frida` 版本必须完全一致，差一位就「连不上」。
2. **推送姿势**：Android 端的 frida-server 是裸 ELF，没有可执行位标记，
   必须 **gzip 压缩后推、再在设备上 gunzip** —— 直接 push 出来的文件跑不了。
3. **多设备时 `-U` 会挂错设备**：模拟器多开 + 真机插着就是 5 台在线，
   必须 `adb -s <serial> forward tcp:27042 tcp:27042` 后用 `-H 127.0.0.1:27042`。

脚本把这三件事都封好了：

```bash
powershell -File scripts/emulator-lab.ps1 frida deploy -Server <frida-server 路径>
powershell -File scripts/emulator-lab.ps1 frida check
```

### 八、输入注入与自动化

模拟器的输入注入有三条路，本包只用第一条（通用、无依赖）：

| 方式 | 速度 | 兼容 | 说明 |
|---|---|---|---|
| `adb shell input` | 慢 | 最好 | 本脚本 `tap` / `swipe` / `text` / `key` 走这条 |
| minitouch | 快 | Android 10+ 在 SELinux Enforcing 下不可用 | 走 evdev |
| 厂商 CLI | 快 | 仅自家 | MuMu 有 `control ... tool cmd`，夜神有 `call.input` |

`input text` 只认 `%s` 表示空格，**不支持中文与 emoji** —— 中文输入要走 IME
（`adb shell input keyevent` 逐字，或 ADBKeyboard）。这是 `input` 的固有限制，不是脚本缺陷。

## 判据（Verification checklist）

判「模拟器这条链路真的通了」，只看外部可观测事实：

- [ ] `adb devices` 里出现目标序列号，且状态是 `device`（不是 `offline` / `unauthorized`）
- [ ] `profile` 读出的 `ro.build.version.sdk` **≥** APK 的 minSdk
- [ ] 装包后 `adb shell pm path <pkg>` 能打出路径（不是只看 install 的退出码）
- [ ] `frida-ps -H 127.0.0.1:27042 -a` 能列出目标进程
- [ ] 抓包产出的 pcap 文件**真的落盘且非空**，再用 `pcap tshark -Out <file>` 解析出条目

**不算通过**：脚本打印了「已连接」（可能连了个空设备）、「helper 加载成功」、
`frida-server` 进程在但端口没监听、pcap 文件存在但 0 字节。

## 坑（Common traps）

- **写死端口**：MuMu 16384 换个多开实例就是 16416，写死必然连不上。
- **设备里写 `127.0.0.1`**：那指设备自己。模拟器里指向宿主机要用 `10.0.2.2`（QEMU NAT）
  或本机局域网 IP。抓不到包十次有八次是这个。
- **`kill-server` 之后忘了重连**：`adb kill-server` 会丢掉所有 `connect` 过的模拟器连接，
  必须重新 `adb connect`。
- **并行跑 adb**：本机有 6 个 adb.exe，daemon 全监听 5037，版本不同互相踢。
  adb 相关操作**一律串行**。
- **多设备不指定序列号**：`adb -s` 漏了就会装到真机上。本脚本检测到多台时直接报错，不猜。
- **蓝叠实例名靠猜**：`HD-Player.exe --instance` 的实例名必须在模拟器设置里确认，脚本不猜。
- **在 AVD 上用 `-U`**：`frida -U` 在多设备时行为不确定，显式 `-H` 转发端口。

## 相关（Related）

- `scripts/emulator-lab.ps1` —— 本文档的脚本形态
- `../references/packer/self-extracting-payload.md` —— 脱壳后的 dex 落地路径
- `../references/dynamic/` —— 动态 hook 的三种落点
- `../../../field-journal/2026-10-11_android-emulator-lab-and-contract-tests.md` —— 落地现场
- `../../experience-cards/android-minsdk-gate-is-not-bypassable.json` —— minSdk 边界
- `../../TOOLS.md` §4 —— 装法与工具登记