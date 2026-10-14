# 失败 → 技能 回归表

> **这一层是打破「每次说改好了、下次真实做又出问题」的机械核心。**
>
> 没有这张表，「改好了」不可证伪 —— 只能验证形状，不能验证行为。
> 同行全部有：transilience 用「跑 benchmark → 找失败 → 诊断缺哪技术 → 写进技能 → 再跑」
> 迭代 ~15 轮把 CTF benchmark 打到 104/104；trailofbits 每技能带 graders；
> 上游 zhaoxuya520 有 175 条路由回归。本包此前 26 个门**全是格式/一致性门，0 行为门**。
>
> 建立日期：2026-10-14。

---

## 怎么用

1. **每完成一个真实项目，就加一条 case。** 不是"有空再加"——是交付的组成部分。
2. 每条 case 必填 `task_verbatim`（用户原话）与 `known_failures`（这次哪里卡了）。
3. `expect_chain` 是「期望的链路」，`known_failures` 是「实际发生的偏差」。
   **两者不写成"应该"和"实际"的对立，而是「下次该走到哪」与「这次走到了哪」。**
4. 跑 `python skills/tests/run-regression.py` 得到偏差 diff。

## 字段契约

```yaml
id: case-NNN-<短名>
date: YYYY-MM-DD
task_verbatim: <用户原话，不改写>
constraint: <用户明确声明的硬约束，含"我没有 X">
expect_chain: [<技能名或 references 路径>]   # 期望链路
expect_deliverable: <成品形态：路径 + 可运行/可构建的最小命令>
known_failures:                              # 这次实际发生的偏差
  - <一条一句，写"发生了什么"，不写"应该怎样">
lesson_refs: [<案例报告章节 / ADF 条目 / commit>]
status: open | resolved                       # resolved = 已改技能且复测通过
```

## 与门的关系

| 门 | 测什么 |
|---|---|
| `test-routing-e2e` | 对每条 case 跑 `master-route` + 让模型给"下一步用哪个技能"，比对 `expect_chain` |
| `test-trigger-rate` | 不依赖 case：每技能 8 正 + 8 近邻负例，各跑 3 次算触发率 |
| `test-assault-behavior` | 取一条真实 case 的 prompt，开新会话跑，按 `expect_*` 判分 |

---

## case 清单

| id | 日期 | 域 | status |
|---|---|---|---|
| `case-001-换肤6.9` | 2026-10-13 | 逆向·受保护目标 | open |
| `case-002-prng-upx` | 2026-10-13 | 逆向·脱壳+复刻 | open |
| `case-003-ctf-demo` | 2026-10-11 | CTF·pwn | resolved |

（新增 case 按编号递增，见 `cases/` 目录。）
