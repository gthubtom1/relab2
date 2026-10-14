# 置信度词表（全包唯一事实源）

> **用途**：所有 SKILL.md 的 `## 置信度词表` 段指向本文件，各技能只列**特有判据**，不复制本表。
> 来源：hackersifu 的 confidence vocabulary + 本项目 ADF-R1/R4*。

---

## 词表

| 词 | 可观测标准 |
|---|---|
| `confirmed` | **≥2 条相互独立的证据**（最好 1 静态 + 1 动态）；动态判据跑 **≥3 轮**、用原子值 |
| `high` | 1 条强证据，且无反面证据；未做交叉验证 |
| `medium` | 1 条证据，来源单一或有已知局限 |
| `low` | **纯推断**。标注者 MUST 在标 `validated` 前安排动态验证 |
| `contextual` | 仅在本案例上下文成立，不可外推 |
| `speculative` | 未验证的不寻常主张，一律先标此（ADF-R3） |

## 硬规则

1. `validated` 状态要求 `confirmed` 或 `high`；单条证据 MUST NOT 静默升级（ADF-R4*）
2. `low` 进入结论前 MUST 补一条独立证据，或显式写 `residual_risk` + 待人工确认
3. 阴性证据（查过且不存在）同样要记录，标 `E-negative-evidence`（ADF-R6）

## 各技能的用法

SKILL.md 里只写本技能**特有**的判据，例如：

```markdown
## 置信度词表

词表见 `../ops/confidence-vocabulary.md`。本技能特有判据：
- `low`：仅有 diec 输出、未做节区/导入交叉验证
- `confirmed`：脱壳后 `r2 -qc 'ii'` 导入项从个位数涨到几十上百，**且** `iS` 无 rwx 节
```
