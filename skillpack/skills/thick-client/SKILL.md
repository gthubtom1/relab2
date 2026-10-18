---
name: thick-client
description: 桌面厚客户端测试：信任边界、凭证存储、IPC/命名管道、流量与更新校验。用于：Electron/Qt/WinForms/WPF、%APPDATA% 硬编码密钥、DLL 劫持、更新器降级。
---

# Thick Client Security Testing

## ACTION REQUIRED（读完后立刻执行）

1. `NOW`: 读取 `../field-journal/precedent-pentest.md`
2. `NOW`: **查经验卡** —— `python skillpack/skills/scripts/experience-card.py search "<你看到的症状>"`。
   命中就读那张卡的 `invariant` + `decision.action`，并**逐条对照** `scope.appliesWhen`
   与 `scope.stopsWhen`：少一条前提就停用；命中任一停止条件就停。
   历史卡**不替代**当前目标的实测证据。详见 `../experience-cards/INDEX.md`。
3. `NOW`: 确认目标是 **桌面厚客户端**（Win/macOS/Linux GUI 或服务伴生），非纯 Web
4. `NOW`: case-init 建案；记录安装包来源、版本与测试账号
5. `NEXT`: 工具（Burp 上游代理、进程监控、逆向工具）
6. `ACT`: 信任边界图 → 本地面 → 网络面 → 更新/供应链

## 适用场景

- C/S 架构客户端、Electron/Qt/.NET WinForms/WPF
- 本地配置/凭证存储、IPC、命名管道
- 客户端强制校验绕过研究（授权）
- 自动更新通道与代码签名验证

## 工作流

### 1. 建边界

```text
□ 进程树、子进程、驱动/服务
□ 监听端口与出站域名
□ 本地敏感路径：%APPDATA%、Keychain、注册表
```

### 2. 本地攻击面

```text
□ 明文配置、硬编码密钥、调试开关
□ DLL 劫持/搜索顺序（Windows）
□ 数据库文件（SQLite）权限与加密
□ IPC：谁可连接？是否鉴权？
```

### 3. 网络面

```text
□ 系统代理 / 应用自定义 TLS
□ 证书钉扎 → 联合 mobile/js 方法学或 Frida
□ API 越权：客户端隐藏的管理接口
```

### 4. 逆向验证

```text
□ .NET → dotnet-reverse；原生 → ida/ghidra；Electron → asar + js-reverse
```

## 参考

- `references/thick-client-checklist.md`
- `../dotnet-reverse/` `../ida-reverse/` `../js-reverse/` `../api-security/`

## 路由上下文

**上游**: MASTER R32  
**下游**: 纯协议 `protocol-reverse`；供应链更新 `supply-chain-security`

## 任务完成自检

- [ ] 是否画出信任边界？
- [ ] 本地+网络面是否都覆盖？
- [ ] Checklist？

---

## When NOT to use（近邻负例）

- 目标是纯 Web 应用/API → 用 `../api-security/SKILL.md`
- 目标是 Android/iOS 应用 → 用 `../apk-reverse/SKILL.md` / `../mobile-reverse/SKILL.md`
- 目标是 Electron 渲染进程里的 JS 逻辑，不涉及本地能力 → 用 `../js-reverse/SKILL.md`
- 只拿到一个安装包要逆向它的保护壳/反调试 → 用 `../reverse-engineering/references/assault-entry.md`
- 目标是浏览器扩展（不是桌面程序）→ 用 `../browser-extension-reverse/SKILL.md`
- 要审的是安装包的构建链与依赖来源 → 用 `../supply-chain-security/SKILL.md`
- 前置条件：先画**信任边界表**（进程/用户/文件/网络的每一处跨界），再挑最有价值的一处深挖

## When to Pivot

信号与判据见 `../ops/skill-pivot-contract.md`。本技能去向：

| 触发证据 | 换到 |
|---|---|
| 本地存储里挖出 token/refresh token，**换一台干净机 5 分钟内仍能认证成功**（可复用凭据） | `../api-security/SKILL.md` 打服务端面（本地那点只是入口） |
| 装好自签 CA 后握手仍失败 / Frida hook 抛 pinning 异常 | Electron 走 `../js-reverse/SKILL.md`；原生走 `../mobile-reverse/` 的 Frida 方法学或 `../reverse-engineering/` 动态面 |
| 客户端是托管 .NET（CLR 目录非零 / `mscoree` 导入 / `#~` 元数据流） | `../dotnet-reverse/SKILL.md` |
| Electron `app.asar` 解开后业务逻辑在原生模块或 `bytenode` 字节码里 | `../reverse-engineering/references/assault-entry.md` |
| 更新器接受旧版本安装包 / 无签名校验直接替换（旧包 2 分钟内能装且能启动） | `../supply-chain-security/SKILL.md` |
| 低权进程能连上命名管道/本地环回端口且拿到数据（两次权限探测一致） | `../windows-ad/SKILL.md` |
| 界面只是壳，需求其实是还原私有协议帧 | `../protocol-reverse/SKILL.md` |
| 目标根本不是桌面程序（无本地进程/无安装包） | `../api-security/SKILL.md` 或 `../web-protocol-reverse/SKILL.md` |

## 工具链（真调用口径）

| 工具 | 干什么 | 真实调用口径 |
|---|---|---|
| Process Monitor | 文件/注册表/进程行为 | 先按进程名过滤，再按 Operation 收窄；`%APPDATA%` 读写是凭证面第一站 |
| Sysinternals（`handle64`/`accesschk`） | 句柄与 ACL | `handle64.exe <pid>` 看管道/文件句柄；`accesschk64.exe -w \\.\pipe\<name>` 看谁能写 |
| `sqlite3` | 本地库 | 直接开库读 schema；权限结论要附 `icacls` 输出 |
| `mitmdump` / Burp | 流量 | Electron：`--proxy-server=127.0.0.1:8899`；自定义 TLS 先看证书钉扎再决定是否 Frida |
| Frida / objection | 运行时 hook | 桌面脚本与移动端不同，先 `frida-ps -U`/`-f <exe>` 验证注入；钉扎脚本按目标家族选 |
| `dnSpy.Console` / `ilspycmd` | .NET 反编译 | `ilspycmd -o out <assembly>`；`dnSpy.Console --md` 报错时换 ilspycmd 交叉 |
| `idat` / `analyzeHeadless` / `rabin2` | 原生逆向 | 探测层定位后按完整路径调；`analyzeHeadless` 适合批量 |
| `asar`（`npx @electron/asar`） | Electron 解包 | `asar extract app.asar out/`；解出的 JS 交 `../js-reverse/` |
| 通道自检 | MCP | `mcp-status.ps1` 三列（注册/监听/怎么起）；IDA(x64dbg) 联动要起 `idapro`(13337)/`x64dbg`(9094) |

路径唯一入口：`. <仓根>\skillpack\skills\scripts\lib\Bootstrap.ps1` → `Resolve-ReverseToolSpec -Name <id>`；
`Get-Command` 查空 ≠ 缺工具。

硬判据：

- 「可复用凭据」= **换干净机/换用户后仍能认证成功**；本机自己登自己的，只是会话不是凭据
- 信任边界表每行写三件事：跨了哪条边界、谁做校验、校验在哪一侧；说不清校验侧 = 未证实
- 「未加密」也是结论：要附打开文件看到的可读字段或 hex 证据，不是「看起来没加密」

## 定义完成

本技能产出算「完成」的**外部可观测**条件（不许写形容词）：

- 信任边界表落盘（进程/用户/文件/网络的每一处跨界）
- 每处发现配最小复现命令或 PoC 脚本路径
- 凭据存储位置与加密方式有实测结论（含「未加密」这一结论的证据）

## 输出契约

```
FACT:       <观察，带来源：命令 / 文件:行 / Evidence ID>
HYPOTHESIS: <可测试断言 + confidence: high|medium|low>（状态见 `../ops/binary-model.md`）
QUESTION:   <当前最大不确定点>
NEXT:       <继续 | 换技能 | 停止（附成本判据）>
```

## 置信度词表

词表见 `../ops/confidence-vocabulary.md`。本技能特有判据：

- `confirmed`：客户端行为在两次以上干净环境复现，且与服务端交互抓包吻合
- 硬判据：任何「信任边界可绕过」的结论，要在**另一台干净机**或**另一用户**下复现一次才算数（本机同用户不算）
- `low`：仅静态看到一个 API 名就推断信任关系
