# 开工词 — 融合一个新技能包（整段复制给 AI 即可）

> 这份是 [MERGE-GUIDE.md](MERGE-GUIDE.md) 的入口。手册是**唯一判据来源**；本词只做两件事：
> 说清任务、说清不许干什么。**不要凭本词里的任何描述代替实跑**。

---

**任务**：把新技能包 `<新包地址（仓库 URL）>` 融合进 `D:\Project\skills-hub\integrated-skill-hub`，
新包短名 `<新包短名>`（它会成为 `source_id`），全程按 `docs/MERGE-GUIDE.md` 执行。

## 硬约束（每条都对应手册章节）

1. **不许破坏现有基准**：`test-routing.ps1` 必须 **182/182**、`test-routing-natural.ps1` 必须 **≥76/86**（§7 回归）。
2. **不许为变绿改测试**：不许删断言、降阈值、放宽匹配、跳过文件（§9.1、§13）。
3. **每步落盘**：没落盘等于没做；写入一律在 `D:\Project\skills-hub\work\<卡名>-lab\`（仓库外）（坑 #8）。
4. **每个数字独立复算**：子代理的自述不算数，要在真树或 lab 里复现出同一个数（§13）。
5. **危险动作只在 lab 副本**：`import`（非 dry-run）/ `promote` / `rollback` 一律不在真仓库上跑（§5、坑 #7）。
6. **顺序铁律**：先登记导入器四表 → 再 pin 上游 HEAD → 最后 `import`，否则 exit 21（§5.0、§5.1）。
7. **收尾按 §12.5 验证协议**跑完 1–6 步，并按 **§10 clone 复核**把 1–3 在仓库外的 clone 里重跑一遍。
8. **有题库时必须补跑"组外新说法"**（hold-out）：不许只报调优集成绩（§12.5 第 5 步、坑 #17）。

## 回报格式（七个标题，缺一即为交接不清）

`STATUS / TOUCHED / ACCEPTANCE / NEGATIVE CONTROLS / MEASUREMENT / DEVIATIONS / UNFINISHED`
——每个命令贴 exit code 与关键行；`ACCEPTANCE` 逐条对 §12.5 的 1–6 步。

## 先做什么（三行，按序）

1. 读 `docs/MERGE-GUIDE.md` 全文（§1 流程总览 + §11 坑清单 + §12.5 验证协议）。
2. 侦察新包：先按 §2 把它**只读 clone** 到 `D:\Project\skills-hub\upstream\<新包短名>`（必须是 git 仓库），
   再答 §3 四问（技能集合还是另一个框架 / 技能数 / 许可 / 成熟度）。
3. **先把策略决策写下来再动手**（§4：A canonical 并入 / B 社区通道（默认）/ C 排除），
   落盘 `work/<本次融合名>/DECISION.md`，然后才进 §5。

---

**如果哪一步的实测与手册写的不一致，先报事实，别照着错前提硬做。**
