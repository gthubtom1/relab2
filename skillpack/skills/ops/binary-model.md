# BinaryModel —— 假设状态机（全包唯一事实源）

> **用途**：任何需要"形成假设并验证"的任务（逆向/渗透/取证/修 bug）共用。
> **解决的问题**：现在只有 `## unknowns`（未决清单），**没有"假设被否证"这个状态** —— 这是重复走同一条死路的机制原因。
> 来源：criticic/reagent 的 BinaryModel（Observations → Hypotheses → Findings）。

---

## 状态机

```
Observations  原始观察，不可变，带 Evidence ID
    ↓
Hypotheses   可测试断言
   状态: proposed → testing → confirmed | rejected
   字段: id / statement / confidence / evidence_ids / rejected_reason
    ↓
Findings     仅 confirmed 进入，带证据链 + 位置
```

### 字段契约

```markdown
### H-{nnn}
- statement: <可测试的断言，不是描述>
- status: proposed | testing | confirmed | rejected
- confidence: high | medium | low | contextual
- evidence_ids: [E-001, E-002]
- rejected_reason: <status=rejected 时 MUST 填写：哪条证据否证了它>
```

---

## 硬规则

1. **`rejected` 不许删除、不许改写 statement。** 出废卷前先查有没有已 rejected 的同款假设。
2. `confirmed` 需 ≥2 独立证据（ADF-R4*）。
3. 每条 Hypothesis MUST 写成**可证伪**形式（"X 在本地完成校验"可证伪；"它可能有防护"不可证伪）。
4. 阶段切换 / 收工前 MUST 陈述当前假设并三选一：**continue / switch / stop**（ADF-R2）。
5. Findings 落 `## functions` / `## diff_baseline`，Hypotheses 落 `## hypotheses`。

---

## 报告骨架片段

```markdown
## hypotheses

### H-001
- statement: 程序拒绝被非 shell 父进程拉起
- status: confirmed
- confidence: high
- evidence_ids: [E-011, E-012]

### H-002
- statement: 卡密校验完全在本地完成
- status: rejected
- confidence: n/a
- evidence_ids: [E-014]
- rejected_reason: 点 LOGIN（错格式）零外连不能证明纯本地；格式关先拦住，
  服务端分支未执行过 → 假设不可证。改为 H-003。
```

**H-002 这种"被否证的假设"正是过去丢失的东西。** 它让人不再第二次提出同一个假设。
