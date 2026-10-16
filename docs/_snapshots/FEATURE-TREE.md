> ⚠️ **这是一份「生成快照」，不是现状。** 由下列命令在某个时间点生成，仓库一变它就过期。
> **读之前先重跑对应命令**：线路树 `feature-tree.py` · 功能图 `feature-graph.py [--body]` ·
> 逐树杈核验 `verify-leaves.py`。权威说明见 `docs/PROJECT-MAP.md`。

---

relab2 · 功能线路树（从真实文件推导）
========================================================================
├─ 入口层（relab2.ps1 子命令 3 个）
│    doctor · setup · update
├─ 技能层（57 张卡）
│    api-security               API 安全测试：REST/GraphQL/WebSocket 接口发现、JWT/OAuth、BOLA/IDOR/BFL
│    apk-reverse                APK 逆向：jadx/apktool 解包、改 smali/AndroidManifest、重打包、Frida hoo
│    attack-chain               多阶段攻击链编排：侦察、初始访问、提权、横向、影响评估。用于：完整渗透、外网打到域控、HW 演练、webshell 下一
│    binary-diff                二进制差分/符号迁移：旧版符号迁到新版、更新后找偏移、内核缺 PDB。用于：更新后地址变了、新版 PDB 下不到、旧版函
│    binary-ninja-reverse       Binary Ninja 逆向：HLIL/MLIL/LLIL 数据流、xrefs、类型与重命名、Python API。用
│    browser-automation         浏览器/桌面 GUI 自动化：Playwright/agent-browser 点击/填表/截图/登录；OpenReve
│    … 其余 51 张
├─ 路由层（63 条规则）
│    R1   → apk-reverse/SKILL.md                     APK reverse
│    R2   → mobile-reverse/SKILL.md                  Mobile reverse (Android+iOS)
│    R3   → js-reverse/SKILL.md                      JS / frontend reverse
│    R4   → reverse-engineering/dsl-vm-reverse/SKILL.md DSL VM reverse
│    … 其余 59 条
├─ 工具层（预探测 id 57 · 能力 33 · 配方 9）
│    配方: triage.format, triage.fileinfo, triage.strings, triage.capabilities, pcap.parse, portscan.local, yara.version, apk.decompile, js.runtime
├─ MCP 层（宿主已注册 6 · 可注册 6）
│    已注册: pyghidra-mcp, x64dbg-mcp, idapro, angr-mcp, relab2-tools, rea
│    可注册: angr-mcp, idapro, pyghidra-mcp, rea, relab2-tools, x64dbg-mcp
├─ 门禁层（40 道）
│    verify-spec-structure            skills/scripts/verify-spec-structure.py
│    audit-discovery-surface          skills/scripts/audit-discovery-surface.py
│    verify-triage-lock               skills/scripts/verify-triage-lock.py
│    verify-community-banner          skills/scripts/verify-community-banner.py
│    … 其余 36 道
├─ 工作流层（6 个生命周期脚本）
│    case-init.ps1          skillpack/skills/scripts/case-init.ps1
│    append-evidence.ps1    skillpack/skills/scripts/append-evidence.ps1
│    master-route.ps1       skillpack/skills/scripts/master-route.ps1
│    review_case.py         skillpack/skills/case-review/scripts/review_case.py
│    diff-runner.py         skillpack/skills/scripts/diff-runner.py
│    experience-card.py     skillpack/skills/scripts/experience-card.py
├─ 换机层（适配面 True · 编号步骤 5 条）
│    技能包放在哪
│    智能体怎么读技能包
│    模型怎么连
│    文档里的「本机读数」不是配置。
│    宿主入口文件缺失 = 首次安装，不是错误。
├─ 知识库层（症状索引 True · 契约 True · 板块 10 · 技术正文 206 篇 · 本仓札记 51 篇）
│    PE / 二进制逆向                61 篇  → reverse-engineering
│    Web / API 安全              72 篇  → api-security
│    数据库注入                     10 篇  → database-security
│    Web 攻击链与 CVE 实证           18 篇  → attack-chain
│    Web-CTF 比赛与付费墙            11 篇  → ctf-sandbox
│    云 / K8s / CI-CD            9 篇  → cloud-k8s
│    上游: LING71671/open-reverselab`
├─ kernel 行为层（10 个模块）
│    00-ANALYSIS             4 文件  00-ANALYSIS · 三份分析的导航
│    01-design               5 文件  
│    02-hubcore             83 文件  
│    03-bundle             252 文件  
│    04-console             74 文件  外置中枢 · 工作台（04-console）
│    05-tests                6 文件  
│    06-verify              10 文件  
│    07-kernel-sweep       134 文件  
├─ 经验卡层（11 张 · 读取器 True）
│    android-minsdk-gate-is-not-bypassable
│    android-native-abi-decides-hookability
│    cdb-noaccess-breakpoint-is-not-hit
│    diff-runner-input-prefix-only-stripped-in-update-mode
│    diff-runner-mode-drift
├─ 社区层（vendored 1089 文件 · wrapper 4 个）
│    wrapper: apk-extension, ctf-hub, delivery, hack-hub
├─ 扩展层（1 个文件）
│    extensions/pi/cmd-guard
├─ 契约/模板层（templates 4 · schemas 10 · ops 15 · references 7）
└─ 依赖层
     python(系统)     3.14.3
     mcp SDK        1.30.0
     node.exe       v22.23.3
     工具根 venv       mcp ok
     mcp@python-venv 1.30.0 list_tools
     mcp@angr-mcp-venv 2.3.0 NO-list_tools
