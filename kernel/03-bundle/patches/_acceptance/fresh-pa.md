## 调度矩阵（工作流管路，方法书管能力）

本系统只带下列方法书；需要更深的领域能力时，这一格停在方法书能给的位置，把证据写进账本，不要假装已经解决。

表里写的是「要哪一类能力」，以及**本系统里真实存在的哪一本能给这个能力**。所有方法书默认遵守公共品质 `../docs/methods/INVARIANTS.md`：文件存在、路径命中、退出码 0、单测绿、探针自己写死 `true`，都只是线索，不是结论。

| 阶段 / 场景 | 需要哪一类能力 | 打开哪个文件 |
|---|---|---|
| `0-spec` 业务理解 | 规划类：把一次协议研究拆成可验证的小步，先定动作边界与成功标志再动手 | `../docs/methods/planning.md` |
| `1-env-traffic` 流量捕获 | 浏览器自动化类（真实页面里跑、观察请求与响应）+ 逆向类（定包、定判定在哪一层） | `../docs/methods/browser-automation.md`<br>`../docs/methods/reverse-engineering.md` |
| `2-discovery` 差异分析 | 逆向类：请求重放、正反流量差异、提取候选变化字段 | `../docs/methods/reverse-engineering.md` |
| `3-solve-re` 算法攻坚 | 逆向类（无源码二进制判定 / 移动 App 抓包脱壳 / 算法复现）；同一猜法反复没证据就换可复用路线 | `../docs/methods/reverse-engineering.md`<br>`../docs/methods/mobile-reverse.md`<br>`../docs/methods/research-reuse.md` |
| `4-protocol-verify` 因果验证 | 逆向类（跑破坏性对照拿 RED/GREEN）+ 排障类（定因，不猜着改） | `../docs/methods/reverse-engineering.md`<br>`../docs/methods/debugging-troubleshooting.md` |
| `5-automate` 自动化实现 | 软件集成类（把驱动引擎接成能跑的工程）+ 浏览器自动化类 + 集成类（多部分拼成一个可交付物） | `../docs/methods/software-integration.md`<br>`../docs/methods/browser-automation.md`<br>`../docs/methods/project-integration.md` |
| `6-test-regression` 健壮性 | 排障类（限流、风控阻断、凭据刷新的根因）+ 审查类（对抗式复核，写的人不能给自己过） | `../docs/methods/debugging-troubleshooting.md`<br>`../docs/methods/review.md` |
| `7-handoff` 目标环境交付 | 发布就绪类（能跑、能停、能回滚）+ 安全审计类（明文凭据一票否决）+ 数据存储类（配置与状态外置、坏了能恢复） | `../docs/methods/release-readiness.md`<br>`../docs/methods/security-audit.md`<br>`../docs/methods/data-storage.md` |

**矩阵的边界，先说清楚，别事后才发现：**

- `3-solve-re` 是最吃紧的一格。原书写的是「逆向类（JS / APK / 原生 / 反调试）」，靠外部库兜底；本系统只剩两本：`reverse-engineering` 管无源码 Windows 二进制的层判定、控制流、授权门/校验门定位、最小可回退探针候选，`mobile-reverse` 管安卓 App 的抓包脱壳、mitmproxy 明文、过 SSL Pinning、Frida 动态 Hook。**前端 JS 混淆还原、反调试/反虚拟机、动态 Hook 追踪具体参数，没有对应的方法书。** 这一格就停在两本能给的位置：能判定在哪一层、能出可回退的最小探针候选，就把 Hook 日志、反混淆产物、复现脚本和剩下的未知变量写进 `EXPERIMENTS.jsonl` 的 `remaining_unknowns`，用「证据在账本里、路线没走完」交账。**不许把「方法书没覆盖」写成「已解决」。**
- `1-env-traffic` 和 `5-automate` 里的浏览器自动化，落在 `browser-automation`（网页动作目录 → 状态机、登录保持、填表点击上传下载、翻页抓取、无痕、多标签、CDP 监听与卡顿）。它不覆盖移动端 App 的明文流量，那部分只在 `mobile-reverse` 里。
- `0-spec` 只有 `planning` 能用；本系统没有「从零做产品」那几本，这里也不该用。
- `project-init`、`ui-design`、`packaging`、`performance-optimization`、`windows-environment` 在这条线上没有对应格，别为了凑数打开。确实撞上 Windows 中文空格路径、编码乱码、权限/UAC、服务与注册表时，才单独点 `windows-environment`。

**能力格之外的四条硬约束（照旧，不因为换书而松）：**

- **流量边界**：每次采集先写明「这次实验为了验证哪一个业务动作」，采完立刻闭合窗口，原始流量进 `TEMP/traffic/<session_id>/`，脱敏提炼物进 `artifacts/`。禁止无边界长抓。物理门 `traffic_boundary` 观察 `traffic_ok: true`。
- **因果对照**：「同时发生」不等于因果。删掉或篡改关键参数 → 服务端必须拒绝（RED）；带正确参数 → 业务通过（GREEN）；两次实验除该参数外条件一致。物理门 `causality_proof` 观察 `causality_ok: true`。
- **发现优先**：不预设「找 Token、找签名、找时间戳」。协议要素由实际实验动态发现，置信度按 Observed → Hypothesis → Candidate → Validated → Final 逐级晋升。
- **无硬编码凭据**：交付到目标环境时，Token、Cookie、Password、密钥全部外置为环境变量或配置参数，交付说明写明要配哪些变量。物理门 `delivery_clean` 观察 `clean_ok: true`；探针必须真去扫交付物，不许把 `true` 写死。

**能让人点就让人点。** 正常业务验证（图形验证码、短信、人脸、人工确认）优先请用户点完再继续——省时间，也避免把人力几分钟能做完的事变成几小时的逆向任务。只有用户明确要求、且属于已授权的本地工程标的时，才转成技术攻坚。
