# 物理门协议（physical-gates v1）

## 目的

`state confirm` 不能再把模型自己填写的自然语言当成运行结果。需要真实运行的阶段，在产品自己的 `.hub/physical-gates.json` 声明机器检查；`state probe` 在当前产品目录内执行检查命令，对 stdout/stderr、退出码、结构化 JSON 和文件状态做断言，然后把收据写入 `.hub/ledger.jsonl`。

运行核对探针设置强制执行一次性沙箱环境，覆盖 APPDATA、LOCALAPPDATA、USERPROFILE、HOME、TEMP/TMP 及常见 XDG 路径，并删除继承的令牌/密码类环境变量。探针必须回显本次运行注入的 `probe_context`，包括候选哈希、候选路径、一次性 nonce、沙箱标识和 `observed_from_candidate: true`；普通通过收据缺任一项都无效。探针超时本身不能算通过，也不能配置 `timeout_is_pass`；超时算一次真失败（可当 RED）。机器没看成、超时、误判、探针命令没跑起来、红探针其实已经通过、或自动化没点到时，由主人用亲手看见的原话登记 `state accept-seen --check <这一项>`，再重新跑该检查；不能让启发式把整单永远卡住。AI 写「符合要求」「可以打包」不能过。硬编码 365 天这种机器写下的作弊数字不能靠这句话洗白。一次只覆盖这一项检查。原始 stdout/stderr 和完整 JSON 不写入账本。

这套机制针对的是“模型没有真做，却靠 `--evidence` 关键词过门”的事故。它不是密码学可信执行环境：探针脚本、产品文件和本地账本仍在本地操作者控制下。因而规则是：只要不能证明探针实际运行并且收据仍绑定当前材料，就 fail-closed；不能把物理门描述成防住恶意本地管理员。

## 命令

```text
python tools/state.py status  --product <产品目录>
python tools/state.py probe   --product <产品目录> --phase <阶段 id> --check <检查 id> --red
python tools/state.py probe   --product <产品目录> --phase <阶段 id> --check <检查 id>
python tools/state.py accept-seen --product <产品目录> --phase <阶段 id> --check <检查 id> --quote "<主人原话>"
python tools/state.py accept-closed --product <产品目录> --phase <阶段 id> --quote "<主人原话>"
python tools/state.py confirm --product <产品目录> --stop-point "<停点名>" --evidence "<人能复核的描述>"
python tools/state.py gate    --product <产品目录>
```

`probe` 只能针对当前阶段、当前候选运行；必须先用 `state probe --red` 证明当前检查在未实现状态下失败，再用普通 `state probe` 取得 GREEN。GREEN 必须引用阶段、合同、epoch、配置、命令一致的有效 RED。RED 可以来自当前候选登记或其真实祖先登记，RED 的路径集合必须与该祖先登记一致，GREEN 则绑定当前路径集合；修复可改变字节或增减模块。重复哈希按登记事件的有效时间段区分，旁支后来的 RED 不能借回旧分支。它不会接受 `--evidence`，也不会接受调用者传入的 `result=pass`。通过或失败都会留一条收据；失败收据永远不能满足 confirm。超时也是一次真失败，可以当 RED；不能配置超时算通过。

机器没看成、超时、误判、探针没跑起来、红探针其实已经通过、或自动化没点到时，不要把整单卡住。主人亲手测过这一项之后，用白话说看见了什么；由工程方登记 `state accept-seen --check <检查 id> --quote "主人看见了什么"`，再重新跑该检查。不要把 python 命令甩给主人。`accept-closed` 是常闭这一项的快捷写法；若机器误把闪屏/报错窗当成主窗口，原话写不是主程序、是闪屏或报错即可。不要写「符合要求」「可以打包」。硬编码 365 天（数字或同值字符串）不能洗白。一句话不能跳过全部机器门；每项检查分开登记。能修好探针命令就先修；修不好且主人已经亲手测过的，登记这一项，不要卡死整单。

## 配置结构

配置文件必须位于产品根 `.hub/physical-gates.json`，顶层为：

```json
{
  "version": 1,
  "checks": {
    "<check-id>": {
      "kind": "process|business|ui|install|update|rollback|handoff",
      "command": ["<产品根内的普通文件>", "<参数>"],
      "cwd": ".",
      "stdin": "<可选输入>",
      "timeout_sec": 15,
      "expect": {
        "exit_code": 0,
        "stdout_contains": ["<可选字符串>"],
        "stdout_not_contains": ["<可选字符串>"],
        "stderr_contains": ["<可选字符串>"],
        "stderr_not_contains": ["<可选字符串>"],
        "json": {"<字段>": "<期望值>"},
        "json_not": {"<禁止出现的字段值>"},
        "files": [
          {"path": "<产品根内文件>", "exists": true, "min_size": 1}
        ]
      }
    }
  }
}
```

约束：命令、工作目录和文件断言都必须在产品根内，不能经过符号链接/junction，不能放在产品根 `TEMP/`；命令使用 `shell=False`；超时范围为 0.1–120 秒；输出有长度上限；未知断言字段直接拒绝。`.bat/.cmd` 等需要 shell 的脚本不应作为探针命令。

`json` 是结构化 JSON 的子集断言；`json_not` 用于拒绝静态或危险值。两者都只在探针实际输出的 JSON 上判断。例如，授权数据流可以拒绝静态 365 天：

```json
{
  "json": {
    "dynamic": true,
    "device_code": "DEVICE_FROM_TEST_PLATFORM",
            "expiry_seconds": 86400,
            "verify_interval_seconds": 60,
            "mid_run_closed": true,
            "kicked_closed": true,
            "solo_still_open": true,
            "rate_limited_closed": false,
            "periodic_verify": true
        },
  "json_not": {
    "dynamic": false
  }
}
```

上面例子里 `86400` 是这张卡还剩多久，`60` 是测试/验收默认再问间隔；两者不能对调、不能相等、也不能只差一两秒。`cache_until` / `next_verify_at` 只决定何时再问，不能写成核心到期。探针最长 120 秒；验证间隔更长时，不能靠探针超时证明 `solo_still_open`，改用对人测两段：先只有一台、等过间隔还开着，再第二台挤第一台，第一台下一次验证内停。不要 20 秒硬刷。

对 `exe-rebuild`，运行核对以下 check 有额外最低要求：

- `core_entry` 必须用 JSON 断言 `main_opened: true`。只输出“窗口亮了”或“pass”不算真进主功能。
- `ui_regression` 必须用 JSON 断言 `ui_ok: true`。配置缺这项、或探针报 `ui_ok: false`，物理门失败；只输出“窗口亮了”或“pass”不算界面回归。
- `core_closed` 必须用 JSON 断言 `main_opened: false`。只输出“授权失败”或“已拦截”不算。运行核会真跑候选（不按文件大小跳过）：看见主窗口或打印 `MAIN_OPENED` 算进了主功能；进程马上退出且没有主窗口，算关上。真跑了仍没法自动判断、或机器可能把闪屏/报错窗误判成主窗口时，不能当失败永远卡住，也不能让 AI 写「符合要求」过门；须主人用看见关上了的原话登记 `state accept-closed`（或 `accept-seen --check core_closed`），再重新跑本检查。硬编码 365 天不能靠这句话洗白。其他机器门不能一起跳过。
- `license_dataflow` 必须用 JSON 断言 `dynamic: true`、非空 `device_code`（二开必填；原创按形态观察核心/主命令/收费门实际用到的值）、数值 `expiry_seconds`（**卡还剩多久**，禁止 `cache_until` / `next_verify_at` / 20 秒 / 60 秒再问间隔，且必须大于 `verify_interval_seconds`；两套钟不准改混：到期靠 `expires_at` 本地关，挤机下一次验证内停）、`verify_interval_seconds`、`mid_run_closed: true`（真卡过期才停，不能缩短核心到期冒充）、`kicked_closed: true` 或 `kick_closed: true`（卡仍有效，但第二台挤掉第一台 / `DEVICE_NOT_BOUND` 后，由启动器在下一次 verify 内停主程序）、`solo_still_open: true`（只有一台时，开着超过验证间隔，主程序还在）、`rate_limited_closed: false`（`RATE_LIMITED` / 暂时失败不是停机）、`periodic_verify: true`。探针应对着核心实际收到并使用的值，而不是只看启动器 API 返回值；静态设备码、硬编码 365 天、把验证间隔塞进核心或标题栏倒计时、用到一半仍开着、被挤掉仍开着、单机没人挤却自己关、只 activate 不再问、`RATE_LIMITED` 当停，必须让探针失败。一句「激活/验证/解绑都要」不能代替这些观察。桌面/命令行/网站/接手在主人当面写下「接自己的授权」之后，从打包/预发/发布候选起也会套同一套 `license_dataflow`；这场不接不套。网站观察的是停服务，不是关软件。

对 `package_install` / `update_flow` / `handoff` / `business_flow` / `command_flow`，运行核同样写死最低 JSON 观察，不能只报 `result: pass`：

- `package_install` 必须用 JSON 断言 `installed: true`。配置缺这项、或探针报 `installed: false`，物理门失败。
- `update_flow` 必须用 JSON 断言 `updated: true`。配置缺这项、或探针报 `updated: false`，物理门失败。
- `handoff` 必须用 JSON 断言 `handed_off: true`。配置缺这项、或探针报 `handed_off: false`，物理门失败。
- `business_flow` 必须用 JSON 断言 `business_ok: true`。配置缺这项、或探针报 `business_ok: false`，物理门失败。
- `command_flow` 必须用 JSON 断言 `command_ok: true`。配置缺这项、或探针报 `command_ok: false`，物理门失败。

对其余默认门，运行核同样写死最低 JSON 观察，不能只报 `result: pass`：

- `clean_install` 必须用 JSON 断言 `clean_installed: true`。配置缺这项、或探针报 `clean_installed: false`，物理门失败。
- `update_rollback` 必须用 JSON 断言 `rollback_ok: true`。配置缺这项、或探针报 `rollback_ok: false`，物理门失败。
- `staging_business` 必须用 JSON 断言 `staging_ok: true`。配置缺这项、或探针报 `staging_ok: false`，物理门失败。
- `migration_backup` 必须用 JSON 断言 `migration_ok: true`。配置缺这项、或探针报 `migration_ok: false`，物理门失败。
- `safety_net` 必须用 JSON 断言 `safety_ok: true`。配置缺这项、或探针报 `safety_ok: false`，物理门失败。
- `change_regression` 必须用 JSON 断言 `regression_ok: true`。配置缺这项、或探针报 `regression_ok: false`，物理门失败。
- `release_candidate` 必须用 JSON 断言 `candidate_ok: true`。配置缺这项、或探针报 `candidate_ok: false`，物理门失败。
- `release_rollback` 必须用 JSON 断言 `release_rolled_back: true`。配置缺这项、或探针报 `release_rolled_back: false`，物理门失败。
- `baseline_repro` 必须用 JSON 断言 `baseline_ok: true`。配置缺这项、或探针报 `baseline_ok: false`，物理门失败。

为了减少只打印固定 JSON 的夹具式探针，真实项目应让探针启动候选、驱动真实输入、读取核心可观察输出或进程/UI 状态，并在测试平台返回不同到期值时重复验证。探针脚本不能只是 `print('{"result":"pass"}')`。

运行核现在要求每个物理探针输出 JSON 对象中的 `probe_context`，其内容必须原样回显运行核为本次运行注入的 `check`、当前候选哈希、候选相对路径清单、一次性 nonce 和沙箱标识，并带 `observed_from_candidate: true`。这让固定输出不能复用；它仍不是恶意本地操作者无法伪造的可信执行环境，真实项目探针仍必须自行启动当前候选并读取真实观察结果。

探针必须先以 `state probe --red` 运行出真实失败收据，再以普通 `state probe` 运行成功；普通 GREEN 没有对应的同阶段、同合同/epoch、同配置/命令及候选血缘上的有效 RED 时，运行核拒绝登记通过；GREEN 仍严格绑定当前候选，收据用 `red_receipt_n` 指向具体失败记录。超时本身不能当 GREEN，也不能配置“超时算通过”；超时可以当合法 RED。红探针其实已经通过（程序可能已经是对的）、探针命令没跑起来、机器没看成、超时、误判或自动化没点到时，主人用 `accept-seen` 登记这一项亲手看见的结果后再跑 GREEN，可代替那一次失败红。收据只保存哈希、长度、白名单结构化字段和文件摘要，不保存原始 stdout/stderr 或完整授权响应。

## 需求防丢清单的机器记录

长需求先逐条用 `state require --append "主人原话"` 写入需求账本；动代码前用 `state record --kind checklist --phase <当前阶段> --data-file <checklist.json>` 记录每项：`requirement_id`、原话 `verbatim_intent`、落地文件 `files`、物理检查 `checks`、计划/已验证状态 `status` 和（对有物理门的阶段）对应收据序号 `receipt_refs`。当前阶段确认时，运行核会拒绝缺清单、漏需求、未关闭项或失效物理收据引用。清单示例见 `templates/checklist.v1.example.json`。

## 施工前立靶（探针先行 TDD 原则）

在通用开发中，模型容易在写代码时注意力漂移，遗漏之前讨论好的边界和细节，甚至自写宽松单测自圆其说。为防止“开会满分、做事实习生”，推行探针先行原则：

1. **先立靶再开枪**：进入需要真实运行的阶段，在修改业务代码前，必须先在 `.hub/physical-gates.json` 配置机器断言（含反向否定断言，如 `json_not` 拒绝静态默认值、拒绝无效退出码）；
2. **初始状态必须为失败（RED）**：代码未完成时，运行 `state probe` 必须真实报错，证明探针具有真实的物理鉴别力，而非无脑放行的空壳；
3. **完成代码跑成成功（GREEN）**：业务代码改完后，`state probe` 跑绿；机器没看成、超时、误判、探针没跑起来、红探针其实已经通过、或自动化没点到时，须主人 `accept-seen` 登记亲手看见的结果后再跑该检查。探针未通过前严禁向主人宣称做好了。不能配置超时算通过，也不能用「符合要求」过门。硬编码 365 天不能洗白。

## 探针与测试的沙箱隔离

严禁探针脚本或单元测试直接读写主机的真实生产配置路径（如 `%APPDATA%`、`%LOCALAPPDATA%` 或用户个人家目录）。

1. 探针涉及配置文件或本地存储读写时，必须将运行环境重定向到产品根的临时沙箱目录（如通过环境变量重定向到 `TEMP/` 或系统临时目录）；
2. 测试过程产生的文件必须在测试结束后清理，严禁在测试中用假卡密、假设备码覆盖用户真实保存在电脑上的凭证。

## 收据绑定与失效

通过收据至少包含：

- `n`：账本分配的正整数序号；confirm 只能引用这条真实收据；
- `product_root`：产品根绝对路径；
- `fp`：当前合同指纹；
- `phase_id` 和 `epoch`：当前阶段及重开或新尝试后的物理证据代数；
- `cand_sha`、`candidate_paths`：运行时当前候选哈希和产品根内相对路径清单；
- `spec_sha`：整个 `physical-gates.json` 当前哈希；
- `command_sha`：实际执行 argv（Python 探针包含当前解释器）和命令文件哈希；
- `probe_nonce`、`sandbox_id`、`stage`：本次运行的一次性探针上下文、临时沙箱标识和 RED/GREEN 阶段；
- GREEN 的 `red_receipt_n`：必须指向签发当时可用的真实 RED；缺引用、引用不存在或 RED 损坏均拒绝。旧 GREEN 缺该引用须重新取证，不能手工补字段；
- `probe_kind`、`observed`、随机 `nonce`、`generated_by=state`。`observed` 只允许安全白名单字段、哈希、长度和文件摘要，不保存原始 stdout/stderr 或完整授权响应。

因此以下任何变化都会让旧收据失效：

1. 换候选或改候选文件；
2. `state reopen` / 新 attempt 使物理阶段 epoch 改变；manifest 事实使用只受 reopen 影响的 artifact epoch。
3. mission、阶段定义或上游变更使合同指纹改变；
4. 修改探针配置、命令参数、命令文件位置或命令脚本；
5. 收据为失败、缺字段、绑定错路径或不在当前阶段；同一对象的最新失败立即挡住旧成功，不能跳过失败往前捞一条 PASS。

`attempt` 的边界要分清：它会让确认和机器收据重新取证，但不会凭空抹掉仍绑定同一候选、同一合同的访问/功能地图等事实；否则 `--reconfirm` 会被迫重复录入未发生变化的事实。后续包装阶段增加业务/授权复验，是为了防止“授权或实现测过 A、实际打包 B”。

`confirm` 会在事件里记录 `physical_receipt_ns`，把每个检查绑定到具体账本序号；`state gate` 和后续构建门会重新校验引用的收据仍然有效。缺少引用、引用不存在或引用与当前收据不一致都会 fail-closed。这只是可审计引用，不是给文字证据开后门。

## 各产品线的默认门

已知产品类型的高风险阶段有运行核默认物理门。合同里可以增加检查，不能用 `physical_checks=[]` 关闭默认门；旧合同缺字段也按默认门处理。

| 产品线| 默认检查|
|---|---|
| exe-rebuild| `1-access: core_entry`；`3-ui: ui_regression`；`4-license: core_closed, license_dataflow`；`5-pack: package_install, core_closed, license_dataflow`；`6-update: update_flow, core_closed, license_dataflow`；`7-handoff: handoff, core_closed, license_dataflow`|
| desktop-product| `2-impl/3-build: business_flow`；`4-package: package_install, business_flow`；`5-install: clean_install, business_flow`；`6-update: update_rollback, business_flow`；`7-handoff: handoff, business_flow`|
| web-service| `2-impl/3-build: business_flow`；`4-staging: staging_business`；`5-data: migration_backup, business_flow`；`6-release: release_rollback, business_flow`；`7-ops: handoff, business_flow`|
| cli-tool| `2-impl/3-build: command_flow`；`4-package: package_install, command_flow`；`5-install: clean_install, command_flow`；`6-update: update_rollback, command_flow`；`7-handoff: handoff, command_flow`|
| source-takeover| `1-baseline: baseline_repro`；`3-safety: safety_net`；`4-change: change_regression`；`5-build: release_candidate`；`6-release: release_rollback, release_candidate`；`7-handoff: handoff, release_candidate`|
| protocol-automation| `1-env-traffic: traffic_boundary`；`4-protocol-verify: causality_proof`；`5-automate: automation_run`；`6-test-regression: automation_run`；`7-handoff: delivery_clean, handoff`|

桌面/命令行/网站/接手默认表没有 `license_dataflow`：这场不接就不套。主人当面写下「接自己的授权」之后，从打包/预发/发布候选起必须加 `license_dataflow`（卡还剩多久、被挤掉停、没人挤不会自己关、`RATE_LIMITED` 不是停）。

protocol-automation 这 5 道门有现成样板：`templates/physical-gates.protocol-automation.example.json`（拷进产品根 `.hub/physical-gates.json`，命令换成产品自己的探针）。每道门要观察什么、什么算不合格，见 `workflows/protocol-automation.md` 的「物理门要观察什么」一节：`traffic_ok` / `causality_ok` / `automation_ok` / `clean_ok` / `handed_off` 五个字段必须是 true，只打印 `result=pass` 不算过。

exe-rebuild 只有「有 2-license 和 3-ship、且没有 2-boundary」才按旧四格阶段名单校验。合同里已经有 2-boundary 时走现行标准阶段（可额外带旧 id）；夹着或挂在末尾的 2-license/3-ship 作废，不能当下一格。

纯需求/架构阶段没有默认运行门，但仍须满足对应 `spec`/`arch` 制品和主人点头。自定义产品类型或阶段没有默认门时，skill 必须明确写出为什么不需要运行检查；不能用“测试绿”一笔带过。
构建、包装、安装、发布和交付阶段会重复验证主业务（exe-rebuild 还会重复验证核心常闭与动态授权数据流），所以新候选不能借用旧候选的业务收据。

## 打包与发布边界

- `record --kind build`、`candidate --bless --role release`、`confirm` 和 `state gate` 都会检查它们适用的前置物理收据。需要先有产物才能运行的 `package_install`、`clean_install`、`update_rollback`、`handoff` 等门，属于打包后的后置门。
- `package_install` 不能只检查 `MZ`、文件存在或固定大小；应执行真实安装器，在干净目录/环境中安装并首次启动，检查包内主程序仍是已验证候选。在它通过前，磁盘上的包只能算未验证测试输入，不能称为正式分发包。
- `state gate` 是账本门，不是操作系统级执行沙箱。它不能阻止直接在任意终端调用 ISCC、NSIS、zip、容器发布工具或 `gh`。因此文档和交付记录不得把账外产物称为正式候选；真正的打包仍必须遵守 AGENTS 的危险动作确认。
- 真实发布前仍需主人确认、独立审查、安装/升级/回滚验证；收据齐全不等于已经发布。

## 尚待拆分的复验语义

当前运行核仍要求每个物理阶段取得 RED，祖先追溯解决的是“真实修复换哈希后不能继续”。它没有完整解决“候选已正确，只在后续安装/交付阶段复验”的语义。后续须将新增/修复断言的缺陷基线与当前候选验收分开，并绑定工作项、断言版本及真实负例；不能允许任意切模式绕过 RED，也不能让探针按 `HUB_PROBE_STAGE` 直接打印失败制造证据。此项见审计报告的剩余实施项。
