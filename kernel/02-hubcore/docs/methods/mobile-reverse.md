---
name: mobile-reverse
description: 安卓 App 的抓包、脱壳与动态逆向：模拟器起环境、mitmproxy 抓明文、过 SSL Pinning、Frida 动态 Hook。要分析手机 App 的接口/协议/加密、抓不到包、App 检测代理或证书绑定、要脱壳或内存里找关键参数时用。Windows 本机 EXE 走 reverse-engineering，不要拿这本顶。
purpose: 用「模拟器 + 强制全局代理 + 系统证书 + Frida」这条固定流水线拿到明文流量，而不是跟 App 的防护硬碰
use_when: 主人给一个安卓 App 要分析接口/协议/加密、要抓手机包、要复现某 App 的请求、要脱壳或 Hook；或抓包时报错断网、只能看到 CONNECT 看不到明文、App 检测到代理。iOS 不在本册范围。
phase: reverse-engineering, protocol-automation
needs: [本机工具探测四级顺序（docs/methods/windows-environment.md）, adb，frida，mitmproxy]
---

# 移动端逆向与抓包

对主人先白话：环境起没起来、包抓到没有、卡在哪一层。一次只报一步。

本 skill 管**安卓 App 怎么拿到明文流量、怎么过防护**。Windows 无源码 EXE 走 `reverse-engineering`；协议本身的因果对照走 `protocol-automation`。三本不要互相顶。

## 先记住

**先探测，不要假设已装。** 工具在哪、能不能调起来，**按 `docs/methods/windows-environment.md`「找工具 / 文件」的四级顺序探测**（环境变量 → 当前会话能调到的命令 → 已知安装位置 → 全盘检索），命中即停，四级全空就**如实报缺**（工具名 + 已试过的四级），让主人决定装不装、装哪、什么来源。**不要静默装，也不要因为「以前装过」就说装好了。**

本机实测状态（2026-10-18，换机后必须重测，别引用这行当现状）：

| 要找的东西 | 实测 |
|---|---|
| `ldconsole` / `dnplayer`（雷电模拟器 9） | `where` 两级都返回「找不到文件」；全盘 `-iname "ldconsole*"` 也为空 → **缺** |
| 工具根下的 `android`（探测到的候选位置） | 只有 `AndroidKiller_fix`、`Android逆向助手_v2.2`、`jadx`、`scrcpy`、`搞机工具箱11.0.1` |
| `setup_device.py` / `unpinning.js` / `start-frida.bat` | 在该 `android` 目录下递归找 → **一个都不存在** |

**结论：本机目前没有可用的「模拟器 + 一键注入」链路。** 要跑这套流水线，先按四级探测确认（或报缺让主人装）；**不要**照下面「三步起手」直接敲命令然后报一个看不懂的 `FileNotFoundError`。

**路径不要写死进任何文档、不要提交进源树**。清单是本机的，换机器就换一份。

## 为什么用这套

多数安卓 App 抓不到包，不是抓包工具不行，是**三层各挡一道**：

| 挡在哪| 表现| 对应解|
|---|---|---|
| App 不走系统 WiFi 代理| 面板里一条都没有| **ProxyDroid**（iptables 强制全局）|
| Android 7.0+ 不信任用户证书| 大量 TLS 握手失败| **系统级 CA 证书**推入只读库|
| SSL Pinning（证书绑定）| 一开代理就断网/报错| **Frida + unpinning.js**|

三层是**递进**的：先按顺序把能拿的拿到，**卡在哪一层再上下一层**，不要一上来就 Frida。

## 三步起手（上次见到时的形状，本机当前缺件，先探测再照抄）

> 下面三条命令是按「装好之后」的样子写的，**不是本机现状**：`ldconsole`、`setup_device.py`、
> `unpinning.js`、`start-frida.bat` 在本机都探测不到（见上表）。照抄之前先确认这几个真的在；
> 不在就先把缺件报给主人，不要硬跑。

**第一步：起模拟器和抓包面板**

- 模拟器：`ldconsole launch --index 0`（命令行，可脚本化）；GUI 是 `dnplayer.exe`
- 什么都不用配，脚本已经把代理端口（8080）和面板一起拉起来了

**第二步：一键把抓包环境注入模拟器**

```
python <android-tools>/setup_device.py
```

它一条命令做完三件：连模拟器 → 推系统只读根证书 → 装 ProxyDroid → 布署 frida-server。
**跑完这一步，模拟器里普通 App 的 HTTPS 流量就应该明文出现在面板上了。**

**第三步：装目标 App 开抓**

- 装：`ldconsole installapp --index 0 --filename <apk路径>`
- 打开它，回面板看流量
- **看得到明文就到此为止**，不要再往下走

## 抓不到包，按这个顺序排查

1. **面板一条都没有** → 代理没生效。确认 ProxyDroid 装了并打开总开关，填的是本机 IP + 8080。
2. **只有 CONNECT，没有明文** → 证书没被信任。重跑 `setup_device.py`；或确认系统分区是可读写的（这台模拟器已开）。
3. **一开代理 App 就断网/转圈/报证书错** → **SSL Pinning**。这是唯一该上 Frida 的时候：
   ```
   start-frida.bat
   frida -U -f <包名> -l <android-tools>/unpinning.js
   ```
   通杀 OkHttp3 / TrustManager 这类主流框架。
4. **Frida 挂了或被检测到** → 换 spawn 模式（`-f` 而不是 `-n`）、改端口、或先停一下看是不是 App 有反调试。**这是新的一层，按 `debugging-troubleshooting` 立假设再动手，不要盲试参数。**

## 边界（这些不是本册的活）

- **改 App 本身的行为**（补丁、重打包）→ 走 `reverse-engineering` 的探针规矩，先出最小可回退候选。
- **真实账号的敏感数据**：抓到就是抓到了，**不要往任何仓库、任何文档里贴令牌和密码**，只留结构。参照 `security-audit`。
- **让模拟器常驻**：用完自己关（`ldconsole quit --index 0`），别留一堆后台进程占内存。
- **重工具要有界**：Frida 脚本可能一直刷日志，输出落盘，主对话只留摘要。
- **找不到工具**：按 `docs/methods/windows-environment.md`「找工具 / 文件」的四级顺序走完。确需安装时，先给主人官方来源、命令、位置、影响和回退，**不要静默装**；查到的路径要实跑一次才算数，禁止伪造路径。

## 那场会话留下的东西

`<android-tools>/README.md` 是当时装环境时写的三步操作指引，和这册说的是同一件事——**手册讲操作，这册讲什么时候该用它**。两者对不上时以这册为准，并回头修正手册。
