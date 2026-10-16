---
name: browser-extension-reverse
description: 浏览器扩展逆向：crx/xpi 解包、manifest 权限、service_worker、content script、流量与 IOC。用于：插件是否偷数据、后台干了什么、权限给多了。
---

# Browser Extension Reverse Engineering

## ACTION REQUIRED（读完后立刻执行）

1. `NOW`: 读 `../field-journal/precedent-reverse.md` —— 本机做过多轮的常规操作清单，直接照做，不要停在犹豫上
2. `NOW`: **查经验卡** —— `python skills/scripts/experience-card.py search "<你看到的症状>"`。
   命中就读那张卡的 `invariant` + `decision.action`，并**逐条对照** `scope.appliesWhen`
   与 `scope.stopsWhen`：少一条前提就停用；命中任一停止条件就停。
   历史卡**不替代**当前目标的实测证据。详见 `../experience-cards/INDEX.md`。
3. `NOW`: 确认目标是**浏览器扩展**（crx/xpi/解压目录），不是普通网页 JS（普通 → `js-reverse/`）
4. `NEXT`: 解压扩展；读 manifest
5. `ACT`: 权限面 → 后台脚本 → 网络/存储钩子

## 适用场景

- Chrome/Edge MV2/MV3 扩展分析
- Firefox 扩展
- 恶意扩展 IOC、供应链扩展投毒调查
- 扩展实现的签名/加密/代理逻辑还原

## 工作流

### 1. 包体

```text
□ crx 解压 / 从 profile 取扩展目录
□ manifest.json：permissions、host_permissions、background、content_scripts
□ 评估过度权限（<all_urls>、webRequest、debugger）
```

### 2. 逻辑

```text
□ service_worker / background 入口
□ content_script 注入点与世界（isolated）
□ chrome.storage / IndexedDB 密钥
□ 与 `js-reverse` 相同：Observe 网络与消息传递（runtime.sendMessage）
```

### 3. 动态

```text
□ 开发者模式加载解压目录
□ chrome://extensions 检查错误
□ DevTools 附加 service worker
□ 必要时 Frida/浏览器 CDP（jshookmcp）
```

## 工具链

| 工具 | 用途 |
|------|------|
| 解压/jq | manifest |
| Chrome DevTools | worker 调试 |
| js-reverse 工具链 | 深度 JS |
| YARA | 恶意扩展规则 |

## 参考

- `references/extension-analysis.md`
- `../js-reverse/` `../malware-analysis/`

## 路由上下文

**上游**: MASTER R30  
**下游**: 复杂混淆 JS → `js-reverse`；投毒调查 → supply-chain / malware

## 任务完成自检

- [ ] 是否列出权限面与入口脚本？
- [ ] 是否还原关键数据流？
- [ ] Checklist？
---

## When NOT to use（近邻负例）

- 目标是普通网页 JS（无 crx/xpi、无 manifest）→ `../js-reverse/`
- 目标是恶意网站本身（挂马、钓鱼页）而非浏览器扩展 → `../email-security/`（若来自邮件）、`../web-protocol-reverse/SKILL.md`
- APK/Electron 桌面端才是目标（不是浏览器扩展运行时）→ `../apk-reverse/`、`../reverse-engineering/languages-platforms.md`
- 需要的是 UI 自动化装/点扩展 → `../browser-automation/`
- 目标是已入侵环境的取证（扩展只是其中一个 artifact）→ `../digital-forensics/`
- 目标是签名/加密算法在扩展外部的服务端实现 → `../web-protocol-reverse/SKILL.md`
- 目标是 Service Worker 之外的原生二进制（helper exe/node 可执行）→ `../reverse-engineering/`，本卡只分析解压出的脚本与 manifest

## When to Pivot

信号与判据见 `../ops/skill-pivot-contract.md`。本技能去向：

| 触发证据 | 换到 |
|---|---|
| 解压出重度混淆 JS（webpack bundle、JSVMP） | `../js-reverse/`（方法见 `../js-reverse/references/ast-deobfuscation.md`） |
| 扩展逻辑走向 native（自带 node binary、helper 进程） | `../reverse-engineering/references/assault-entry.md` |
| C2/数据外传面成主任务（域名/IP 落点、投递链） | `../malware-analysis/SKILL.md` + `../protocol-reverse/SKILL.md`（私有帧时） |
| 供应链投毒 / 商店上架的恶意版本 | `../supply-chain-security/` |
| 规则化检测（扩展家族 YARA） | `../threat-hunting/` |
| 浏览器 CDP/jshookmcp 深度调试是唯一路径 | `../js-reverse/`（该卡持有 MCP 执行面） |

## 定义完成

本技能产出算"完成"的**外部可观测**条件（不许写形容词）：

- 解压产物路径落盘（`manifest.json`、background/service_worker 入口、content_scripts 列表），`jq` 或等价命令输出附在报告
- 权限面清单逐条列出且每条给一句判断依据：`permissions` + `host_permissions` + `optional_permissions` 中危险项（`<all_urls>`、`webRequest`、`debugger`、`nativeMessaging`、`cookies`、`tabs`）各命中哪个脚本
- 数据流还原：至少一条 `source → 处理 → 出口` 链路（如表单输入 → content script → background fetch），每跳有文件:行 或运行时捕获
- IOC 清单（域名/URL/存储 key/消息 type）每条带 Evidence ID 与来源（静态字符串或 DevTools/Frida 捕获）
- 恶意结论有运行时或行为证据；仅静态可疑项显式标注 `推断`，不许写成"已确认窃取"
- 若需 DevTools 附加 service worker：附一次实际捕获记录或写"运行时未验证"

## 输出契约

```
FACT:       <观察，带来源（命令 / 文件:行 / Evidence ID）>
HYPOTHESIS: <可测试断言 + confidence: high|medium|low>  （状态见 ../ops/binary-model.md）
QUESTION:   <当前最大不确定点>
NEXT:       <继续 | 换技能 | 停止（附成本判据）>
```

## 置信度词表

词表见 `../ops/confidence-vocabulary.md`。本技能特有判据：

- `confirmed`：静态（manifest 权限 + 脚本代码路径）与运行时（DevTools 网络 / storage 捕获）双证据；或同一 IOC 在两种独立来源（代码常量 + 实际请求）各出现一次且一致
- `low`：仅凭权限列表或变量名推断外传（`webRequest` 存在 ≠ 在偷数据）；或只看到一个 base64 字符串就判定 C2
