# 2026-10-11 安卓模拟器能力层 + 经验卡体系落地

## 场景分类

APK 逆向 / 环境能力层 / 工具链建设

## 目标概述

两件事一起落地：

1. **模拟器能力层**：真机 adb 常掉线且设备 SDK 不可控（实测 Android 11 装不上 minSdk 31 的包），
   所以预制「接任何模拟器都能控制 / 抓包 / 动态调试 / 测试」的能力层，**先不安装模拟器**。
2. **经验卡体系**：`references/contract/experience-card-schema.md` 定义了完整的经验卡 schema
   与晋级门，但晋级目标目录从未建立；补上目录、工具、门禁与首批卡片。

## Scope 摘要（脱敏）

- auth_basis: 用户自有真机 + 公开下载的第三方 APK
- network_profile: offline（静态与设备侧能力验证未走外网）
- asset_types: [本地工具链, 用户真机]

## 角色

- lead_role: lead
- specialists: []

## 完整执行链路

1. 读 `docs/HANDOFF-2026-10-11.md` + `$TEMP/finalgates3.log`（14/36 绿后进程被杀，非测试失败）
2. 点火路由层 → PRIMARY = `skills/apk-reverse/SKILL.md`
3. 读探测层 `lib/Bootstrap.ps1`（`Resolve-ReverseToolSpec` / `Test-ReverseTcpPort`）与
   `verify-repository-security.py` 的规则集，确认新脚本的硬约束：
   - 端口探测必须走 `Test-ReverseTcpPort`（自写 `TcpClient` 会触发 `tcp-client-health-probe`）
   - 可执行源里不得出现 `http://<域名>`（`127.0.0.1` / `localhost` 在白名单）
   - `.ps1` 带非 ASCII 必须有 UTF-8 BOM
   - 文档里的 ```json 块会被 `json.loads` 严格校验
4. 从 MAA1999/M9A 官方文档取各家端口表，从 MuMu / Nox / LDPlayer 官方帮助页取控制 CLI 语法
5. 写 `emulator-lab.ps1`（1176 行，18 个动作），写 `references/emulator-lab.md`
6. 写 `experience-card.py`（new/search/validate/stamp）+ 4 张卡 + 3 个 fixture
7. 写两道契约测试（各带反例控制组），登记进 `ci-gates.json` + `ci.yml` + lock

## Evidence 链摘要（脱敏）

| E-id | severity | status | source_type | 可复用命令模式 | 关联 Finding |
|---|---|---|---|---|---|
| E-001 | info | observed | command | `emulator-lab.ps1 doctor` 零安装实跑：10 项工具全通 | F-001 |
| E-002 | info | observed | command | `test-emulator-lab.ps1` 22 用例全过，含 2 条反例证明判据会红 | F-002 |
| E-003 | info | observed | command | `test-experience-card.py` 8 类坏卡全部转红 | F-003 |
| E-004 | info | observed | command | `verify-gate-wiring.py --write-lock` 后 blocked=0 needs_review=0 | F-004 |

## 踩坑记录

| 问题 | 原因 | 解决方案 | 耗时 |
|---|---|---|---|
| `emulator-lab.ps1` 首次解析 11 处语法错 | `PUT >N` 插入的多行数组参数里，反引号续行被吞，`-NativeArgs @(...)` 断成两半 | 改成 `@(` 紧跟同行的单行数组 | 5 min |
| `doctor` 跑到 avdmanager 整个脚本死掉 | `avdmanager --version` 不存在，它把用法写 stderr；全局 `ErrorActionPreference='Stop'` 把正常 stderr 包成 `NativeCommandError` | 新增 `Invoke-VersionProbe`（Start-Process + 两流分文件），探针改用 `list avd` | 10 min |
| `bs` → bluestacks 解析失败 | 档案里只写了 `Key='bstk'`，`Get-VendorProfile` 的 StartsWith 匹配不到 `bs` | 加显式别名表（含中文「雷电/夜神/蓝叠」），被契约测试的用例抓出来 | 5 min |
| 契约测试崩在「无法覆盖变量 HOME」 | `$HOME` 是 PowerShell 只读变量（用户主目录），拿它当局部变量直接抛异常 | 改名 `$keyHomeCode` | 2 min |
| 反例控制组第一次跑不出来 | 副本放 `%TEMP%`，探测层上溯找不到 `Bootstrap.ps1`，`..\..\scripts\...` 解析成 `C:\..\..\...` | 副本放到仓内 gitignore 的 `/work/` 下 | 10 min |
| 4 张卡初版 validate 全红 | ① fixture 路径按 `skillpack/` 解析却写成仓库根相对；② 一张卡只有 1 次复现 | 加 `resolve_ref()` 按仓库根解析；补第二次独立复现 | 5 min |
| `emulator-lab.ps1` 用 Bash 语法探测失败 | Bash 不吃 PowerShell 语法；`/d/EXE/python/python.exe` 也不是有效路径 | 探针落盘成 .ps1 再 `-File` 跑；Python 用 PATH 里的 `D:\EXE\python\python.exe` | 3 min |

## 工具链发现

- 探测层已覆盖：`adb` / `tshark` / `dumpcap` / `mitmproxy` 12.2.3 / `frida` 17.17.0 /
  `frida-ps` / `objection` 1.12.5 / `emulator` 37.2.12（build 16428233）/ `avdmanager` / `scrcpy` 4.1
- `avdmanager` 没有 `--version`；`emulator -version` 有
- 本机 `.android/avd` 里已有 1 个 AVD 定义（官方 emulator 起不来，见 TOOLS.md §4.1）


## 关键命令

```powershell
# 模拟器能力层（零安装即可用）
.\skillpack\skills\apk-reverse\scripts\emulator-lab.ps1 doctor
.\skillpack\skills\apk-reverse\scripts\emulator-lab.ps1 scan
.\skillpack\skills\apk-reverse\scripts\emulator-lab.ps1 connect -Auto

# 经验卡
python .\skillpack\skills\scripts\experience-card.py search "stderr 中断 退出码"
python .\skillpack\skills\scripts\experience-card.py validate
```

## 对本包的改进建议

- 各家模拟器端口表 / 控制 CLI 语法已固化进 `emulator-lab.ps1` 的 `$script:VendorProfiles`，
  由 `test-emulator-lab.ps1` 守住；换新模拟器只需加一条档案
- `apk-debug.ps1` 的 `kill-server` 现在会重连 13 个常见模拟器端点

## 可复用的模式/脚本片段

- **经验卡体系**：`skills/experience-cards/*.json` + `skills/scripts/experience-card.py`
  （`new` / `search` / `validate` / `stamp`），判据唯一来源是
  `web-protocol-reverse/references/contract/experience-card-schema.md`
- **门禁自带反例控制组**：`test-experience-card.py` 造 8 类坏卡逐个验证转红；
  `test-emulator-lab.ps1` 把脚本副本改坏再验证判据变化

## 进化动作

- [x] 更新了子 skill 文档（apk-reverse/SKILL.md、TOOLS.md §4.1/§4.6/§4.7、INDEX.md）
- [x] 新增了 pitfalls 记录（4 张经验卡）
- [x] 登记了两道新门禁（ci-gates.json + ci.yml + lock）
- [ ] 无需更新路由矩阵（R1 已覆盖 `模拟器` 关键词）

## 环境信息

- OS: Windows 10 企业版 19045 (x64) · PS 5.1 · ACP 936 · 16 GB RAM
- 工具版本: frida 17.17.0 / mitmproxy 12.2.3 / objection 1.12.5 / adb 1.0.41 / tshark 4.6.8
- 目标平台/版本: 模拟器**未安装**（本轮刻意不装）；真机 Android 11 / SDK 30 在线

## 脱敏要求

本文件不含真实域名、账号、token。真机序列号与用户名未写入。

## 索引同步

`field-journal/_index.md` 的「APK / Android 逆向」小节 + 累计统计 + KB-INDEX 已同步。