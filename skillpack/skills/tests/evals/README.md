# 技能触发率 eval 集

> **为什么需要**：本包此前的门全是格式/一致性门。没有任何门回答
> 「**这个技能在被需要时会不会被选中**」——而那正是「每次说改好了、下次真实做又出问题」的核心。
>
> 依据（Anthropic Agent Skills 规范）：每个技能准备约 20 条 query
> （8–10 **正例** + 8–10 **近邻负例**），每条跑 3 次算触发率；
> **正例 ≥0.5 通过 / 负例 <0.5 通过**。
>
> ★ **负例必须是「近邻」**：共享关键词但需求不同。
> 弱负例（"今天天气怎么样"）测不出任何东西 —— 检查器会因此报错。

---

## 文件格式

每个技能一个文件：`skills/tests/evals/<skill-name>.yaml`

```yaml
skill: ida-reverse          # 必须是 skills/<name>/SKILL.md 存在的技能
positive:                   # ≥8 条：这个技能**应该**被选中
  - 反编译这个 exe 看看校验函数
  - 这个 dll 的导出函数都是干什么的
  - 用 IDA 看一下这个 so 的 main
  # ...（≥8）
negative:                   # ≥8 条：**近邻** —— 共享关键词但该用别的技能
  - 这个 exe 带 VMP 壳，脱壳失败，要做出成品     # → assault-entry（共享「exe/逆向」）
  - 这个 app 抓包看签名怎么算                    # → js-reverse（共享「逆向」）
  - 这个 .NET 程序反编译出来全是乱码             # → dotnet-reverse（共享「反编译」）
  # ...（≥8）
```

## 怎么跑

```bash
# 结构检查（不需要模型调用，可进 CI）
python skills/tests/test-trigger-rate.py

# 实跑触发率（花钱，默认 non-blocking）
python skills/tests/test-trigger-rate.py --run --limit 10
python skills/tests/test-trigger-rate.py --run --only ida-reverse
```

## 检查器会查什么

1. 目标技能存在
2. 正例 ≥8、负例 ≥8
3. 每条负例**确实近邻**（与目标技能或同域技能的关键词共享至少一个词）
4. 实跑时：正例触发率 ≥0.5、负例触发率 <0.5

## 覆盖现状

见 `test-trigger-rate.py` 的输出 `eval sets=N`。
**覆盖是渐进的**：新增/修改技能时应同时补它的 eval 集。
