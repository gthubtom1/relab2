---
name: thick-client
description: 桌面厚客户端测试：信任边界、凭证存储、IPC/命名管道、流量与更新校验。用于：Electron/Qt/WinForms/WPF、%APPDATA% 硬编码密钥、DLL 劫持、更新器降级。
---

# Thick Client Security Testing

## ACTION REQUIRED（读完后立刻执行）

1. `NOW`: 读取 `../field-journal/precedent-pentest.md`
2. `NOW`: **查经验卡** —— `python skills/scripts/experience-card.py search "<你看到的症状>"`。
   命中就读那张卡的 `invariant` + `decision.action`，并**逐条对照** `scope.appliesWhen`
   与 `scope.stopsWhen`：少一条前提就停用；命中任一停止条件就停。
   历史卡**不替代**当前目标的实测证据。详见 `../experience-cards/INDEX.md`。
3. `NOW`: 确认目标是 **桌面厚客户端**（Win/macOS/Linux GUI 或服务伴生），非纯 Web
4. `NOW`: case-init；安装包来源与测试账号写入 scope
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

## 工具链

| 工具 | 用途 |
|------|------|
| Process Monitor / API Monitor | 行为 |
| Burp / mitmproxy | 流量 |
| dnSpy / IDA / Ghidra | 逆向 |
| Sysinternals | Windows 面 |
| asar / nexe 检测 | Electron |

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
- 目标是 Android/iOS 应用 → 用 `../apk-reverse/SKILL.md`
- 目标是 Electron 渲染进程里的 JS 逻辑，不涉及本地能力 → 用 `../js-reverse/SKILL.md`
- 前置条件：先画**信任边界表**（进程/用户/文件/网络的每一处跨界），再挑最有价值的一处深挖

## When to Pivot

信号与判据见 `../ops/skill-pivot-contract.md`。本技能去向：

| 触发证据 | 换到 |
|---|---|
| 更新器校验可降级/可替换 | `../supply-chain-security/SKILL.md` |
| 本地存储发现可复用凭据，要打服务端 | `../api-security/SKILL.md` |
| IPC/命名管道权限过宽，可被低权进程利用 | `../windows-ad/SKILL.md` |

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
- `low`：仅静态看到一个 API 名就推断信任关系
