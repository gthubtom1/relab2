# EVOLUTION-CHECKLIST — 融进新技能包后的可执行自检

> 跑 `python scripts/verify-evolution.py` 可自动检查其中 10 项（默认约 1.3 分钟；`--full` 再跑全量 182 与 smoke）。
> 该脚本**已接进 CI 门清单**（`skills/tests/ci-gates.json` 的 `verify-evolution` 门，blocking_exits 20/21/30），
> 所以它不再是"想起来才跑"的东西 —— 红了就阻塞集成门集合。

来源：上游 `AI-Fullstack` 的 `EVOLUTION.md` 10 问 Checklist（任务完成后自检"表要不要更新"）。
区别：上游靠自觉，本文件每条都给出**验证方法**（跑哪个命令 / 看哪个文件），跑不出绿就不算过。

用法：融进一个新技能包（或新增 `skills/<new>/SKILL.md`）后，从上到下逐条勾选。
命令均在仓库根执行；`exit 0` 为过，`exit 10` 为"需人工确认"（按命令说明处理），`exit 20` 为阻塞。

- [ ] 1. 新的可复用经验沉淀了吗？（上游第 1 问）落点：对应技能的 `SKILL.md` / `references/`。验：`(Resolve-ReverseToolSpec -Name 'pyre').Command skills/scripts/verify-doc-links.py --json` 应 `exit 0`（文档链不断，无死链）。
- [ ] 2. 新的常见坑写进症状/门禁了吗？（上游第 2 问）落点：`SKILL.md` 症状段或门禁段。验：`(Resolve-ReverseToolSpec -Name 'pyre').Command skills/scripts/verify-routing-signals.py --check` 应 `exit 0`（信号层 fail-closed，无静默放行）。
- [ ] 3. 新任务类型/关键词进主路由了吗？（上游第 3 问）落点：`skills/config/routing.json`（唯一事实源）。验：`(Resolve-ReverseToolSpec -Name 'pyre').Command -c "import json;json.load(open('skills/config/routing.json',encoding='utf-8'));print('routing.json ok')"` 应打印 ok；再跑 `powershell -NoProfile -ExecutionPolicy Bypass -File skills/scripts/master-route.ps1 -Hint "<新包的代表性说法>"` 看 PRIMARY 是否命中新路由（未命中走入口文档"禁止硬塞"三步，不改期望硬凑）。
- [ ] 4. 社区层能查到吗？（上游第 3 问的社区侧）落点：`skills/community/registry.json`。验：`(Resolve-ReverseToolSpec -Name 'pyre').Command skills/scripts/community-route.py --hint "<新包的代表性说法>"` 应 `exit 0`（matched）或 `exit 10`（needs_review，读清 review_reason）；`exit 20` 则按提示收窄重查（一次一词或加 `--source` 分查）。
- [ ] 5. 新工具/命令登记了吗？（上游第 4 问）落点：`skillpack/skills/TOOLS.md`（生成件）与 `skills/scripts/bootstrap-manifest.json`。验：`powershell -NoProfile -ExecutionPolicy Bypass -File skills/scripts/verify-doc-facts.ps1` 应 `exit 0`（文档事实表与 manifest 一致）。
- [ ] 6. 可复用模板/长期参考放对地方了吗？（上游第 5、6 问）落点：`templates/` / `references/`（按技能目录结构）。验：`(Resolve-ReverseToolSpec -Name 'pyre').Command skills/scripts/verify-doc-links.py --json` 应 `exit 0`（模板/引用的文档链不断）。辅助：`powershell -NoProfile -ExecutionPolicy Bypass -File skills/scripts/extract-summaries.ps1 -Check` 发现 `SKILL.md` 前言与索引漂移时报 `CHECK INDEX.md out of date`（本轮基线即此状态，`exit 1`，既有——`skills/INDEX.md` 自 0a36a65 未重生成，本卡未动任何 `SKILL.md`；重生成索引另起改动，本卡只记录不修）。
- [ ] 7. 可自动化步骤脚本化了吗？（上游第 7 问）落点：`skills/scripts/`。验：`powershell -NoProfile -ExecutionPolicy Bypass -File skills/scripts/smoke.ps1` 应 `exit 0`（verify + parse + quick route 全过）。
- [ ] 8. 工作流步骤/输入输出变了吗？协作关系影响到别的流了吗？（上游第 8、9 问）落点：`skills/MASTER-ROUTING.md`、`skills/routing.md`（只读视图）、wrapper 注册信息。验：`powershell -NoProfile -ExecutionPolicy Bypass -File skills/scripts/verify-routing-coherence.ps1` 应 `exit 0`（表与 JSON 不漂移）。
- [ ] 9. 形成全局规则了吗？spec 结构还合法吗？（上游第 10 问）落点：`RULES.md`（行为链真相源）；动 spec 则同步 `docs/INTEGRATION-IMPLEMENTATION-SPEC.md`。验：`(Resolve-ReverseToolSpec -Name 'pyre').Command skills/scripts/verify-spec-structure.py` 应 `exit 0`（编号连续、无重复标题、无悬空引用）。
- [ ] 10. 双基准没退化、全门还绿吗？（收口）验：`powershell -NoProfile -ExecutionPolicy Bypass -File skills/scripts/test-routing.ps1`（182 例）与 `powershell -NoProfile -ExecutionPolicy Bypass -File skills/scripts/test-routing-natural.ps1`（86 例）通过数不低于融包前；再跑 `(Resolve-ReverseToolSpec -Name 'pyre').Command skills/tests/run-ci-gates.py --runner python` 全绿。失败是信号：修包不改期望（natural 基准的 hint 刻意避开专属关键词，见其 meta 说明）。
