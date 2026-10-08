# cmd-guard（pi 宿主专用 · 可选层）

**读本文件前先知道一件事：这一层是可选的。**
行为卡片层和能力路由层不依赖它，换任何别的宿主（Claude Code / Codex / Cursor / dsh…）
这个目录直接忽略即可，本技能包照样完整可用。

---

## 它解决什么

**命令卡住时，agent 自己发现不了。**

pi 的 `bash` / `powershell` 工具的 `timeout` 是可选的，不传就无限等；
命令执行期间 agent 不在运行、没有任何代码在跑，所以它**没有机会**察觉自己卡住了。
「终端计时器一直涨 + token 计数静止」= 卡在命令，不是卡在推理。这类卡死**不会自愈**。

光在文档里写「记得传 timeout」管不住 —— 那是提示词，不是物理保证。
这一层就是那道物理保证。

---

## 三个文件

| 文件 | 作用 |
|---|---|
| `cmd-guard.ts` | 扩展本体。补 timeout、拦 GUI 二进制、ssh 有界化、卡死状态栏 |
| `cmd-guard.rules.json` | 规则。改完 30 秒内自动生效，或 `/guard reload` |
| `cmd-guard.rules.vm.json` | 客户机 / VM 变体（`blockGui: false`）。要用时复制成 `cmd-guard.rules.json` |
| `smoke-cmd-guard.mjs` | 自测，26 条断言 |

---

## ★ 它和本包的关系：读 `TOOL-CHAIN.md`，不改代码

GUI 拦截清单**不是硬编码在插件里的**，是从本包里的 [`TOOL-CHAIN.md`](../../../skillpack/TOOL-CHAIN.md) 派生的：

```
TOOL-CHAIN.md 里写   `foo.exe`→`foo-cli`
                    ↓
cmd-guard 下次调用就拦 foo.exe，并告诉 agent 改用 foo-cli
```

所以：

- **加工具不用碰插件。** 文档加一行，拦截跟着变。
- **文档删了，拦截自动消失。** 不存在「清单过时」。
- 找不到文档时只退到内置兜底表，并**明说**「★未找到 TOOL-CHAIN.md」——
  静默降级是这个插件唯一能犯的错，不让它发生。

探测顺序：环境变量 `RELAB_SKILL_ROOT` / `REVERSE_SKILL_ROOT` → 从插件所在目录往上找
含 `TOOL-CHAIN.md` 的层 → `C:\relab2` / `C:\relab`。装在 `~/.pi/agent/extensions/` 时
靠环境变量或后两个候选。**换机不用改配置。**

---

## 装 & 验

```powershell
# 复制到 pi 家目录
copy extensions\pi\cmd-guard\cmd-guard.ts        "$env:USERPROFILE\.pi\agent\extensions\"
copy extensions\pi\cmd-guard\cmd-guard.rules.json "$env:USERPROFILE\.pi\agent\extensions\"

# 自测（用 pi 自己的 jiti 加载，和 pi 真实加载路径一致）
node extensions\pi\cmd-guard\smoke-cmd-guard.mjs
```

启动 pi 后用 `/guard` 确认规则来源。显示「★未找到 TOOL-CHAIN.md」就说明这台机器上
技能包不在已知位置 —— 设 `RELAB_SKILL_ROOT` 指向本包根。不处理也能用，只是少了文档派生。

彻底关闭：设 `CMD_GUARD=0` 后重启 pi；或 `/guard off`（本次会话）。

---

## 完整文档在哪

**权威文档在插件仓库**（那边才是 cmd-guard 的主场，含更多宿主相关说明与版本记录）：

<https://github.com/gthubtom1/agent-plugins/tree/main/plugins/pi/cmd-guard>

本目录是技能包内的**同一份副本**，改的时候两个仓库一起改，否则换机会拿到旧版。

---

## 与本包的纪律对应

| [`TOOL-CHAIN.md`](../../../skillpack/TOOL-CHAIN.md) 纪律 | 本插件怎么落地 |
|---|---|
| 不许猜路径 | 拦截理由里直接给出 `Get-Command` 与四级递进的查法 |
| 工具链是协议不是清单 | 拦截名单从文档派生，加工具不用改代码 |
| 命令挂死就中断换路子 | 底栏实时显示已跑多久 / 静默多久，`/stall` 给处置处方 |
| 如实报告 | 降级时明说「★未找到 TOOL-CHAIN.md」，不假装一切正常 |
