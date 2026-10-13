# 融合架构评审与决策

## 结论

以 `reverse-skill`（基线提交 `cab634bd855fc287f6e420c1f36fd1a6b9245960`）作为唯一主框架。它已经提供统一的路由事实源、平台路由脚本、scope/case 门禁、Evidence→Finding→Path 证据链、工具索引、field-journal 和回归门。

`ctf-super-hub` 的 CTF 分类和新手双模式入口作为 CTF 领域适配层；`hack-skills` 作为 Web/API/主机安全专题适配层；`AI-Fullstack-Delivery-Workflow` 作为交付编排与验收适配层；新版 `apk-reverse` 作为 APK 专业能力增强层。它们不保留并行的全局规则、主路由或 case 根目录。

## 对外部方案的采纳

外部方案提出的七层模型（入口、规则、路由、技能、工具、Case/证据、知识沉淀）是正确的；“能力迁移而不是文件搬家”、统一 `work/<case>`、所有新增能力必须登记路由和工具依赖，也作为本项目的设计原则。

## 必须补上的硬门

1. **来源与许可证**：每个迁入技能保留源仓库、提交哈希、原路径、许可证状态和适配状态。没有许可证的仓库只进入本地适配区，不能被宣称为可再分发。
2. **版本与回退**：融合清单锁定上游提交；上游更新先生成新的候选清单，不能覆盖已验证版本。
3. **命名空间与冲突**：外部技能暂存于 `skills/community/<source>/`，由 canonical wrapper 进入主路由；同名技能、重复关键词和不同安全假设不能靠复制覆盖。
4. **工作流边界**：全栈交付工作流不是安全技能，只有在用户明确提出交付/工程任务时才由独立路由进入；它不能改变安全路由的 scope 门，也不能把普通开发任务强行放入渗透流程。
5. **能力成熟度**：文档存在不等于能力已验证。导入注册表区分 `verified`、`partial`、`unverified`、`blocked`，并将工具、设备、网络和平台限制写入输出。
6. **命令与链接门**：对导入内容做路径、内部链接、脚本参数、秘密、固定机器路径和隐式下载检查。已知漂移必须在 registry 中记录并在发布门前修复或显式隔离。
7. **客户端边界**：不把任何外部包的 `AGENTS.md`、hooks、MCP 或全局配置自动写入用户目录；主包仍保持 client-neutral。
8. **真实接缝验证**：文件存在、单仓库测试通过都不能证明融合成功，至少要验证“任务提示→主路由→wrapper→下游技能→统一 case 输出”的链路。

## 当前已知风险

- `AI-Fullstack-Delivery-Workflow` 没有仓库级许可证，且审计记录显示部分 nested/private 路径失效；本融合包保留其本地来源和风险标记，不把它标为可分发内容。
- `apk-reverse` 的结构检查和引用检查较强，但其文档中仍有 `tests/run_tests.py -q` 与脚本参数不一致的命令漂移；该命令在适配层中标为待修复，不作为成功证据。
- `ctf-super-hub` 含混合许可证和未完全核对的第三方 Strix 来源；保留 `THIRD_PARTY_NOTICES.md`，不会把未知来源改写成 MIT。
- `hack-skills` 内容覆盖广且和现有 API、Web、AD、Pwn 技能有大量重叠；采用 hub + registry 的二级选择，避免把 100 多个主题直接塞入顶层优先级。

## 复核新增的缺口

这一轮按真实调用链复核了“主路由 → wrapper → 社区目录 → 下游能力”，发现七层模型还需要加上“发现/发布生命周期”两层。它们不是目录整理问题，而是会直接影响智能体选择能力和发布安全的运行契约。

1. **原始 `SKILL.md` 仍可被发现**：社区目录保留了 293 个上游 `SKILL.md`，`skills/INDEX.md` 也把它们逐项列出。`user-invocable: false` 不能替代客户端级的发现隔离；某些客户端仍会递归扫描这些文件，绕过 wrapper 的授权和下游选择。最终结构应把上游正文作为 reference/vendor 数据，只有四个 wrapper 进入可执行发现面，或实现明确的 wrapper-only discovery gate。
2. **二级匹配的基础门已补上，但仍不是事实源**：`community-route.py` 现在有别名归一化、最低置信度、并列冲突和 `needs_review`，并以 wrapper-only 路径返回结果；新增回归覆盖 JWT、中文 SSRF、CTF APK 和歧义输入。剩余问题是 wrapper/downstream 元数据仍硬编码在脚本，未进入 registry，也没有端到端 handoff fixture。主路由 48/48 通过仍不能证明下游链可靠。
3. **wrapper 到下游仍是 prose-only**：四个 wrapper 有文字映射，但 registry 没有 wrapper 记录、允许的下游集合、handoff 输入输出 schema 或链路 fixture。应把这些关系机器化，并测试“route id → wrapper → registry match → canonical downstream”至少一条真实 dry-run。
4. **来源文档链接没有完成清洗**：启用无 Git 工作树回退后，链接检查发现 342 个导入文档链接仍按上游根目录解析（主要在 `docs/community`，另有社区技能引用未复制的脚本）。需要把它们修成融合后的路径，或明确标为 provenance-only 并从 active capability 入口排除；不能让 registry 返回一个打不开的下一步。
5. **高级 APK 能力仍在旁路目录**：`skills/community/apk-reverse-source/` 有 capability matrix、references 和脚本，但 canonical `skills/apk-reverse/` 仍是另一套旧入口。R49 只是扩展 wrapper，不能替代把能力矩阵、证据摘要、doctor/preflight 和按需脚本接入 canonical APK 的单一入口，否则 APK 任务会产生两套事实源。
6. **成熟度和许可证还没有发布硬门**：验证器对 189 个社区条目只输出 warning 并以 0 退出；`missing-license`、`review-required` 和 `unverified` 内容仍可能进入打包候选。应区分 local-only 与 redistributable，并让发布检查在存在不可分发条目时失败。
7. **版本/回退账本尚未落地**：registry 记录了五个上游提交哈希，但融合目录本身不是 Git 仓库，没有集成基线提交、生成器版本、变更 diff、升级候选和回退点。上游更新后无法可靠判断哪些适配文件需要重建。
8. **加载成本没有门**：293 个正文和全量索引会增加上下文噪声。应默认只加载 wrapper、registry 摘要和命中的少量 reference，把完整正文变成显式二级加载；同时给 registry 查询设置结果上限、置信度和冲突提示。
9. **R49 首步曾经断链**：APK wrapper 原来把 `known-limitations.md` 写成 source 根目录路径，实际文件在 `evidence/known-limitations.md`；这类入口路径必须有可执行 fixture，不能只靠结构检查。wrapper 路径已修正，但社区 APK 正文仍引用 canonical 目录中不存在的 `doctor.py`、`capabilities.py` 和证据摘要，说明高级能力尚未真正并入 canonical APK。
10. **R48 交付流程仍有删除后的引用**：适配后的 workflow 仍引用已排除的 `reverse-skill-private/`，并调用未迁入的 `scripts/bootstrap-project.ps1`。只要按文档执行到 bootstrap 或安全工作流分支就会失败；交付 wrapper 还没有定义普通本地项目如何完成 case 输入而不被安全目标门误拦。
11. **导入器本身会原地覆盖**：`adapt-community.py` 没有 `--help`、dry-run、候选输出或原子切换；重复调用会直接覆盖适配树和 registry。应先写候选目录，执行清洗/验证后再提升为已验证快照，并保留 source digest 和回退点。
12. **来源快照不随融合目录交付**：五个 clone 目前在 `<开发根>\upstream/`，而 `integrated-skill-hub/` 自身没有 `upstream/`。单独移动或打包融合目录后只能看到 URL/commit，不能离线复核来源。需要明确“构建输入”边界，或随 release 提供不可执行的 source bundle/digest。
13. **安全验证器也依赖 Git**：已为本地副本增加工作树回退，但当前安全门会把我们运行验证时生成的 `__pycache__` 当未审查二进制；发布前应清理生成物并让 `.gitignore`/扫描规则明确区分临时缓存与交付文件。没有 Git 的目录不能再直接 traceback。
14. **社区工作流的边界说明放在末尾不够强**：`WORKFLOW.md` 前部仍有 bootstrap/安全动作指导，适配合同只是追加到文件末尾；模型按顺序读取时可能先执行旧规则。安全/交付边界必须置于文件顶部，或将原文降级为 docs-only reference 后再由 wrapper 提供唯一动作入口。

这些缺口不否定 `reverse-skill` 作为母架构的选择；它们说明“七层融合流程”还必须补成“发现隔离 → 路由选择 → wrapper handoff → 能力执行 → 证据产出 → 许可证/版本发布”的闭环。

## 验收标准

- 所有五个源仓库在 `upstream/` 保持完整 clone。
- 融合包的顶层规则和 route SSoT 仍只有一套。
- 新增 wrapper、registry、路由 benchmark 和适配文档均可在干净目录中定位。
- Windows 与 Linux 路由入口语义一致。
- 至少完成 CTF、Web/API、全栈交付、APK 四条 wrapper 链路的 dry-run；高风险工具动作仍需 scope 和显式授权。
- wrapper-only discovery 不暴露未适配的 raw `SKILL.md`；社区查询具有最低置信度和 `needs_review` 分支。
- 每个 wrapper 有机器可读的下游集合、输入/输出 handoff schema 和至少一个端到端 fixture。
- active capability 的内部链接、脚本参数和路径扫描为零未分类阻断；provenance-only 文档被明确隔离。
- 发布检查会阻止没有许可证、许可证未核对或成熟度为 `unverified` 的条目进入分发候选；融合基线可回退到锁定的提交。
- R49 的 doctor/capability/evidence 首步、R48 的 workflow/bootstrap 首步在适配后路径上可执行；不存在的 source-relative 引用为零。
- 导入器支持 dry-run、候选快照、source digest、原子提升和回退；误调用不会直接重写已验证目录。
- 融合目录可在没有 `.git` 的副本中完成文档与安全边界校验，且不会把生成缓存当作交付内容。
