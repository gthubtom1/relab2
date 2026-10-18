# 责任核 v1：AI 怎样使用，机器究竟检查什么

适用代码：`tools/hub_work.py`、`tools/hub_assertions.py`、`tools/hub_cmds.py`、`tools/hub_flow.py`。这是现行接口说明。产品思考与完整工作方式见 [OPERATING-MODEL](OPERATING-MODEL.md)，那次验证记录属于旧项目，没随本系统带过来；本系统里以当前这次跑出来的实物证据为准。本文件供工程方使用，不要求零基础用户填写 JSON。

## 默认行为与兼容

新 `state init` 建 schema 3 合同。所有阶段的 `status` 与 `confirm` 使用累积责任，早期阶段只检查已到期责任；未来安装等责任可以先声明，不能提前算完成。`state work --check` 检查全部声明责任；`gate --scope delivery` 还检查完整阶段和原物理门。`gate` 默认 `--scope package`，只检查构建/授权阶段及此前的责任和原打包前置条件，不把尚未打出的包要求成已经安装。

schema 1/2 保留中间阶段的旧协议，便于恢复现场；**旧合同也不能在 package/delivery 出口绕过责任核**。迁移时先保留原账，再捕获实际来源、定义仍有效责任、取得当前观察。`work --define` 会立即启用新判定，不伪造历史收据，不要求用 `init --force` 清空原项目。schema 3 不是用户可选的“严格模式”。本地人若任意改合同/账本或绕开 CLI，属于尚未实现的宿主执行边界。

根源仓不作为产品建账。所有以下命令针对真实产品根；测试必须使用系统临时目录和独立 `HUB_REGISTRY`。

## 从来源到责任

`tools/speech_land.py` 按用户消息事件把原话追加到 `OWNER-SPEECH.md`，来源身份和正文哈希被保留。`state require --append "完整原话" --id R1 --source speech:<事件摘要>` 建立分类映射；`--kind` 为 requirement、decision 或 question。有效要求必须分解；问题不假扮程序行为。**已经落地而尚未归类的来源事件会阻止整单责任闭合**。

手工捕获普通需求仍被接受，来源会如实保留；它不代表宿主已认证用户身份。决定必须关联已有 `speech:` 原话，正文完全相符。用 `--kind decision` 加任意 reason 不再足以撤回责任或改策略。这里绑定的是可核查来源，不是密码学签名；同账户能编辑全部文件时仍不能防任意伪造。

一条原话可以分成多项责任；`sources.quote` 必须确实出现在该条原话里。机器能发现缺来源和缺分解关系，**不能证明一句复合原话已经语义完整地分解**。独立工程复核仍需沿并列条件、否定条件、时间、消费者和旧能力逐项核对。

计划文件的最小形态：

```json
{
  "version": 1,
  "items": [{
    "id": "export",
    "outcome": "用户选定位置的 CSV 能被下游读回中文名称和金额",
    "sources": [{"requirement_id": "R1", "quote": "导出中文 CSV"}],
    "phase": "2-impl",
    "files": ["app/quote.py", "checks/export_probe.py"],
    "consumer": "独立 CSV 读取程序，读取用户选择的文件",
    "depends_on": [],
    "evidence": [{"kind": "probe", "check": "command_flow", "assertions": ["csv-content"]}]
  }]
}
```

`state work --define <文件>` 累积更新，同次没有出现的旧项仍保留。不能填 status/done/verified/deferred。输入文件不是真值，正式定义以只追加的账本事件为准。

`files` 是真实相关文件，允许在实现前缺失，但缺失不能完成。使用产品相对路径，拒目录概括、父路径、账本、Git、TEMP、ADS 和链接。候选本身始终另有强制绑定，不能只声明一份说明书替代程序。尚未发现的依赖不会自动被系统识别；工程方要通过构建、调用与真实观察补齐。

## 原话与方案变化

纯工程调整用 `change_note` 说明理由，不要求用户批准换人、移文件等技术维护。若修订依据是用户决定，用 `change_source` 引用已落地的决定。读取和使用旧证据时也重核这个来源；删除决定行、改正文或改依赖都会使旧结论无法继续使用。原证据策略和原话片段不能原地删减。确实退出某项业务范围，用 `work --withdraw <ID> --source <决定ID>`，它显示 withdrawn，不显示 satisfied。

合并/拆分先定义新承担者，再依据决定撤回旧项；有其它责任依赖旧项时必须重新接好依赖，不能留下悬空关系。每次修订留历史，不以一个新 JSON 覆盖全部目标。机器并不代用户判定决定语义是否确实同意范围减少。

## 从实际观察到结论

物理检查仍位于 `.hub/physical-gates.json`。在原 `expect` 外增加 `assertions`：

```json
[
  {"id": "csv-content", "path": "/actual/names", "op": "eq_path", "other_path": "/expected/names"},
  {"id": "wrong-input-refused", "path": "/invalid/rejected", "op": "eq", "value": true}
]
```

具名断言由运行核计算，不接受候选自报已通过 ID 的列表。支持 eq、ne、exists、type、eq_path、ne_path；JSON pointer 采用 `/` 与 `~0`/`~1`。缺字段不同于 null；bool、int、float 精确比较互不混用；无断言、重复 ID、重复 JSON 键、未知操作和非有限数拒绝。动态期望必须来自本轮独立输入/观察，不能让产品自己计算一份答案冒充实际消费者。

收据记录逐断言通过与安全失败原因、执行输出摘要、实际候选、阶段和检查绑定，以及所承担责任的定义、原话、文件和递归前置绑定。真实消费者的完整诊断需要由相应观察器保留；通用收据避免保存任意业务秘密。`consumer` 名字只定位用途，本身不能证明消费者被启动。

`probe --mode change` 是默认修复模式，需可追溯真实 RED→GREEN；`--mode baseline` 如实建立现状，不要求故意把正确程序弄坏；`--mode regression` 需要同检查定义的历史通过依据，并重新运行当前候选。基线通过证明当下行为，不证明某个假设就是根因。

后续阶段可以对新候选复验前面到期的同一责任。前面阶段的同名检查不能提前满足未来安装/交付责任。核验选最新相关观察，包括失败；不能绕到另一阶段找旧 PASS。

## 依赖和人工判断

`depends_on` 是责任依赖。循环、自依赖、悬空及依赖已撤回项都会拒绝。绑定递归包含前置的定义、来源和文件摘要，因此改 A 再只重验 A，B 不能自动恢复旧验收。外部数据库、设备、服务、运行账户和配置版本尚未被自动建成完整依赖图；需具体观察器声明适用条件。

`evidence` 可组合 `{"kind":"review"}`、`{"kind":"acceptance"}`。登记方式：`work --attest <ID> --kind review|acceptance --source <决定ID> --actor <实际评估者> --artifact <证据文件>`。文件、候选、责任、前置和阶段 epoch 变化会使登记失效。评估不能替代同一责任必需的 probe；评估者不能与 assignee 相同。**名字不同不是身份认证，文字文件存在不是独立实测**，真实评估仍由工程管理与宿主权限共同约束。

## 不中断总目标

`work --enter <ID>` 记录直接调用方；`work --leave` 只在此责任满足时正常返回。阻塞后 `--leave --pause` 可交回上层处理，但原责任仍 pending。正常返回也不替父工作宣布完成；所有有效责任均满足并且调用栈返回后，整单责任检查才通过。

`work --json` 是机器和新代理的派生视图，`work --check --phase <阶段>` 只检查到期范围。`status`、`recover`、`confirm` 与出口复用这个判定。查看发生在当下；磁盘里的 `resume.json` 是索引与快照，不能覆盖新状态。

`status/recover` 在 schema 3 或已经定义 work 的产品中共用 `engineering_next` 导航。它给出当前建议焦点、实际消费者、前置缺口、调用返回点和需要作出的工程判断；`recover` 将它存于 `engineering`，`next` 与现场 status 一致。有活调用时先处理该调用；已满足时准备向调用方交接并返回；范围外调用/依赖先核对阶段，不抢跑未来工作。损坏责任视图明确要求恢复，不按新产品补造计划。

导航不会替模型发现全部业务风险，也不写入“已思考”状态。模型须依现行工程循环，用实际项目材料将提示转成调查、设计和执行；不能仅打印导航便宣称主动思考生效。原责任、收据和授权限制继续有效。

## 这版没有保证什么

本轮已经运行的跨要求变化演练是一个报价 CLI，尚未构成所有桌面、网站、二开、安装、发布、更新和回滚的实测。现有六条产品线仍有原阶段与硬门；不会因为新责任字段出现就自动获得未知产品形态的观察能力。

中枢目前不能截获任意终端命令，也没有受限账户、可信宿主消息入口或生产凭据代理。要让危险操作在所有模型下都不能旁路，必须把真实操作收进有权限约束的执行器，并用错误动作实测拒绝；这需要独立的宿主集成范围。文档与本地 CLI 不能代替这一层。

<!-- hubcore: deadrefs-fixed-by 03-bundle/patches/apply_docs_audits_fix.py
     归档：下面每一行是本次改写前的原文（逐字保留；渲染时不可见）
     L3: 适用代码：`tools/hub_work.py`、`tools/hub_assertions.py`、`tools/hub_cmds.py`、`tools/hub_flow.py`。这是现行接口说明。产品思考与完整工作方式见 [OPERATING-MODEL](OPERATING-MODEL.md)，本轮实际验证见 [验证记录](audits/20260913-redesign/VALIDATION.md)。本文件供工程方使用，不要求零基础用户填写 JSON。
-->
