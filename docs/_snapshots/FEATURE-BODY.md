> ⚠️ **这是一份「生成快照」，不是现状。** 由下列命令在某个时间点生成，仓库一变它就过期。
> **读之前先重跑对应命令**：线路树 `feature-tree.py` · 功能图 `feature-graph.py [--body]` ·
> 逐树杈核验 `verify-leaves.py`。权威说明见 `docs/PROJECT-MAP.md`。

---

AI 身体图 —— 所有类型节点 + 跨类型边（身体各部分该是通的）
========================================================================
  节点 798 · 边 4670
  各类节点: {'kernel': 36, '其它': 268, '知识': 305, '技能': 63, '脚本': 26, '经验卡': 11, '门禁': 1, '工具': 88}
  跨类型边种类: kernel→其它, kernel→工具, 其它→工具, 其它→知识, 其它→脚本, 技能→其它, 技能→工具, 技能→知识, 技能→脚本, 知识→其它, 知识→工具, 知识→脚本, 经验卡→其它, 经验卡→工具, 脚本→其它, 脚本→工具, 门禁→其它, 门禁→工具, 门禁→脚本
  孤岛 9 个（断开的部分）: {'kernel': 3, '其它': 5, '知识': 0, '技能': 0, '脚本': 0, '经验卡': 0, '门禁': 0, '工具': 1}
    kernel/04-console/cards/hub/01-敏捷逆向攻坚.md
    kernel/04-console/cards/暂时不用/grok46-小码酱.md
    kernel/04-console/cards/暂时不用/富江-deepseek.md
    skillpack/skills/scripts/check-card-drift.py
    skillpack/skills/scripts/parse-skill-frontmatter.py
    skillpack/skills/scripts/t25-case-lifecycle-lab.py
    skillpack/skills/scripts/test-workflow-title-safety.ps1
    skillpack/skills/scripts/verify-doc-auto-install.py
    tool:7z
