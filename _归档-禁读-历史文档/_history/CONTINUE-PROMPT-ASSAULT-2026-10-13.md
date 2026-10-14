# 续打提示词 · 实弹攻坚（复制给实弹对话）

> 用法：把下面 **```** 之间的整段复制，粘贴进那个实弹对话，然后让它继续。

```
接着干活。你是谁、在哪、停在哪，先自己查清楚再说：

【1. 先自检现状，别重做】
- cd C:\relab2，读 work/assault-测试exe/assault.md（§0 状态行 + 各表）、FEATURES.md、
  analysis/PAYLOAD-FRONTIER.md、analysis/GATE-ANALYSIS.md、docs/PROJECT-GAPS.md。
- 你上一轮停在：门栓已绕过 + payload 入口已被进入（原子 @rip 5/5 稳定），
  但 payload 执行即连续 #AV → fail-fast，卡点 = U-003（payload 崩因/语义）。
- 以你自查为准；若与我写的不符，按你的自查走。

【2. 项目这三处刚补了机制，这轮必须用上】
- assault-entry.md 新增「主人可见性」（关键点四句话汇报，见下第 5 条）；
- assault-entry.md 新增「宿主/环境依赖」判据（无/可模拟/硬依赖 三档）；
- anti-debug-bypass.md 新增 §8「运行时自翻页」专项；code-patching.md 坑 13
  （动态判据必须原子 @rip + ≥3 轮，单轮不算数）。
先读这三处，再动手。

【3. 先判宿主依赖，别再用「依赖外部游戏」当假设】
用 assault-entry.md 的「宿主/环境依赖」三档判：本目标 check2 只做
QueryFullProcessImageNameW（拿路径）——这是「可模拟依赖」档，不是「硬依赖」。
U-005「payload 需真实游戏内存」已作废（证据被污染）。所以：
- 不许拿「要真游戏才能测」当借口少做；
- 造 stub 进程喂饱门栓（你上轮已做过 fake_riot），继续推进；
- 只有真判到「硬依赖」（读宿主内存/私有接口）才可报「需主人决策口径」。

【4. 接着打 payload（U-003）——用反篡改专项手法，别再被页翻骗】
- 目标会把 .text/.ace0 翻成 PAGE_NOACCESS 反篡改，你的断点会被吞/报 0n998。
- 手法（anti-debug-bypass.md §8）：① 在 VirtualProtect→NOACCESS 调用点下断，
  命中瞬间把该页 dump 出来（此时还可读）；② 或 patch 掉那次翻页，让它永不翻页；
  ③ 或 hook VirtualProtect/NtProtectVirtualMemory 记录翻页地图；
  ④ 载荷要调的系统 API（如 WinHttp*）下断，避开被翻页区。
- 一切断点结论 = 原子 @rip + ≥3 轮稳定性；单轮命中/未命中都不采信（经验卡
  cdb-noaccess-breakpoint-is-not-hit）。运行时地址一律 base+RVA 复核。

【5. 汇报纪律（主人是零基础，只看关键点四句话）】
- 不每步都报。只在四个关键点报：定完路线准备开打 / 卡住或要停 / 成品出来 / 需要主人给东西。
- 报就四句大白话：① 现在到哪了 ② 成品到没到（到了=什么样子；没到=还差哪步）
  ③ 要不要主人给东西 ④ 下一步干什么。不许术语、不许堆文件路径。
- 同步把这四句更新进 assault.md 的 §0 状态行（磁盘上的那份永远最新）。

【6. 态度（红线，不许松）】
- 验收线只有一条：成品出来了没有（所有功能正常、主人可直接使用）。
- 不许写「打不穿也算完成」；真判定无路可走，也要写成「卡在 U-003，为什么，
  已尝试什么」，而不是「基本达成」。默认目标必须打穿。

【7. 收尾（走到哪算哪，但必须留痕）】
- 更新 assault.md（状态行 + functions + unknowns + diff_baseline）、FEATURES.md（逐项）。
- 在 docs/ASSAULT-GOAL-2026-10-13.md 追加 §9d（本轮记录）。
- 更新 docs/PROJECT-GAPS.md（不足报告：暴露的体系问题 + 需主人决策项）。
- 本地 commit，不推远端（红线）。kernel/ 不许动。
```

（本文件是提示词留档，复制上面代码块即可。）
