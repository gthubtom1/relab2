# 经验卡症状索引（自动生成，勿手工编辑）

> 由 `skills/scripts/experience-card.py stamp` 重建。手工改这里会在下次 stamp 被覆盖。
> 机器检索直接用 `python skills/scripts/experience-card.py search "<症状>"`，比读本表准。

## 怎么用

1. 动手前先 `search` 你的症状；命中就读那张卡的 `invariant` 与 `decision.action`。
2. **对照 `scope.appliesWhen` 逐条查**——少一条就停，别硬套。
3. **出现任一 `scope.stopsWhen` 条件就停用这张卡**，不要因为「以前这么干过」就继续。
4. 历史卡**不替代**当前目标的实测证据；它只替你省掉从零摸索。
5. 没命中不是「没有经验」，而是可以沉淀：用 `new` 建一张候选，晋级门见
   `skills/web-protocol-reverse/references/contract/experience-card-schema.md`。

## 卡片（共 5 张）

| 症状 / 信号（我看到了什么） | 卡 | 规则 | 技能 |
|---|---|---|---|
| INSTALL_FAILED_OLDER_SDK | [android-minsdk-gate-is-not-bypassable](android-minsdk-gate-is-not-bypassable.json) | 当 adb install 报 INSTALL_FAILED_OLDER_SDK（APK minSdk=N，设备 sdk=M<N），这不是操作问题而是系统层拒绝：Android… | `apk-reverse` |
| 元素个数算成 1 | [ps51-convertfrom-json-top-level-array](ps51-convertfrom-json-top-level-array.json) | 在 Windows PowerShell 5.1 上，`$x | ConvertFrom-Json` 处理顶层 JSON 数组时返回的是一个「数组对象」而非枚举出的元素；`@(… | `apk-reverse` |
| 函数明明写了变量，调用方看不到 | [powershell-script-scope-does-not-follow-callstack](powershell-script-scope-does-not-follow-callstack.json) | PowerShell 里 $script:X 里的 script 指**定义该函数的那个脚本块**，不随调用栈走；因此把函数体抽成字符串或 ScriptBlock、在外部执行时… | `apk-reverse` |
| 外部探针永远读到空 | [powershell-script-scope-does-not-follow-callstack](powershell-script-scope-does-not-follow-callstack.json) | PowerShell 里 $script:X 里的 script 指**定义该函数的那个脚本块**，不随调用栈走；因此把函数体抽成字符串或 ScriptBlock、在外部执行时… | `apk-reverse` |
| 报错里有两个看不懂的数字 | [android-minsdk-gate-is-not-bypassable](android-minsdk-gate-is-not-bypassable.json) | 当 adb install 报 INSTALL_FAILED_OLDER_SDK（APK minSdk=N，设备 sdk=M<N），这不是操作问题而是系统层拒绝：Android… | `apk-reverse` |
| 日志里有我的标记就以为程序跑到了那里 | [gate-self-must-prove-failure](gate-self-must-prove-failure.json) | 断言成功与否只能依赖三类外部可观测事实：文件真的被创建、字节真的被改、伪代码真的包含目标逻辑。命令回显（.echo / Write-Host 打在日志里的标记）会与程序自身输出… | `reverse-engineering` |
| 红色 NativeCommandError 文字，内容其实是正常信息 | [ps-native-stderr-breaks-strict-mode](ps-native-stderr-breaks-strict-mode.json) | 在 ErrorActionPreference='Stop' 的脚本里调用原生 exe 时，该 exe 写到 stderr 的任何一行（包括进度信息与正常诊断）都会被 Powe… | `apk-reverse` |
| 脚本在调用某个 exe 的那一行直接死掉，退出码 1 | [ps-native-stderr-breaks-strict-mode](ps-native-stderr-breaks-strict-mode.json) | 在 ErrorActionPreference='Stop' 的脚本里调用原生 exe 时，该 exe 写到 stderr 的任何一行（包括进度信息与正常诊断）都会被 Powe… | `apk-reverse` |
| 输出里出现 System.Object[] | [ps51-convertfrom-json-top-level-array](ps51-convertfrom-json-top-level-array.json) | 在 Windows PowerShell 5.1 上，`$x | ConvertFrom-Json` 处理顶层 JSON 数组时返回的是一个「数组对象」而非枚举出的元素；`@(… | `apk-reverse` |
| 门禁一直绿但功能是坏的 | [gate-self-must-prove-failure](gate-self-must-prove-failure.json) | 断言成功与否只能依赖三类外部可观测事实：文件真的被创建、字节真的被改、伪代码真的包含目标逻辑。命令回显（.echo / Write-Host 打在日志里的标记）会与程序自身输出… | `reverse-engineering` |

## 分工（别混）

| | 经验卡（本目录） | field-journal |
|---|---|---|
| 形态 | 结构化 JSON，可被程序消费 | 散文 Markdown |
| 内容 | 一条**可判定**的规则 | 一次任务的**现场** |
| 数量 | 少（几十张），每张都有 fixture + 正负 oracle | 多（按任务累积） |
| 谁读 | `experience-card.py search` | 人读的回顾 |

> 经验卡的判据（晋级门 7 条 / 消费规则 / 退役判据）唯一来源：
> `skills/web-protocol-reverse/references/contract/experience-card-schema.md`。
> 本目录只放**已晋级**的卡；候选留在任务本地。
