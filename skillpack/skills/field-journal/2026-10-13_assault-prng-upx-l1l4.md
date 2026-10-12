# 2026-10-13 UPX 壳 + PRNG 算法双层目标的攻坚闭环首跑（L1+L4）

## 场景分类

逆向工程（受保护目标攻坚 · assault 四状态机首次端到端实跑）

## 目标概述

以一个自造真实样本（MinGW 编译的 PRNG 探针，UPX 5.21 加壳）为目标，按
`assault-entry.md` 四状态机（SURVEY→ROUTE→EXECUTE→VERIFY）完整走一遍：
过 L1（壳）与 L4（算法）两层，产出可运行复刻实现，并以同输入对照 + 严格审计收尾。
目的：验证「攻坚交付闭环」这条新路径从入口卡到审计器的全链路。

## Scope 摘要（脱敏）

- auth_basis: 自造样本（own_system），offline
- network_profile: offline
- asset_types: [自造 PE64 样本（UPX 打包）, 反汇编产物, 对照记录]
- preset: assault

## 角色

- lead_role: lead
- specialists: [cre（勘察）, impl（实现）, ver（验证）]

## 完整执行链路

1. SURVEY：`diec` 报 `Packer: UPX(5.21)[NRV, brute]`；r2 `iS` 见 UPX0/UPX1/UPX2 三节区
   （UPX0 为 rwx 空节）—— L1 确认。L2/L3 判为不适用（解包后无混淆/自检面）。
2. SURVEY（L1 过层）：`upx -d` 解包 54854B；解包产物与打包程序的 mode0 输出均与原版
   逐字节一致 → L1 过层。解包产物 vs 原版二进制差 85 字节（UPX1 metadata/checksum 区），
   行为不受影响 —— 记为 U-001「已解」，不阻塞。
3. ROUTE：五条候选路线对照（patch/recover/rewrite/keep/blocked），选 `rewrite`——
   两个 LCG 的常量已可从反汇编直接读出，Python 复刻最小可用。confidence=high。
4. EXECUTE（L4）：r2 `aaa` + `pdf main` —— mode0 = MSVCRT rand（srand(12345)）；
   mode1 = Knuth MMIX 64-bit LCG（三个 movabs 常量：seed/乘数/增量）→ L4 过层。
5. EXECUTE：写 `build/prng_rebuilt.py` 复刻两个序列；裸跑自证两模式与原程序一致。
6. VERIFY：`diff-runner.py --assault` 同输入驱动对照，逐字节判定 → 两功能「对照一致」。
7. VERIFY：`review_case.py --verify-hashes --strict` → PASS（0 error / 0 warning）。

## 本跑真实卡点（下次的地图）

| # | 卡点 | 现象 | 修法 | 沉淀 |
|---|------|------|------|------|
| 1 | `diff-runner.py` 的 `input=` 前缀剥离缺口 | assault 模式首跑，新实现收到字面量 `'input=0'` 崩（ValueError）；rebuild/assault 解析分支未剥前缀（只有 update 分支剥过） | 三处解析统一剥离；重跑后 stdout 79B=79B 字节一致 | 经验卡 `diff-runner-input-prefix-only-stripped-in-update-mode` |
| 2 | 报告格式需按审查器字段 | report/analysis.md 首版缺 `evidence_ids`/`status`/`confidence`/`location` 等字段被 13 条 error 拦下 | 照 `work/rebuild-sha256sum/report/report.md` 的 finding/path 模板改写 | 无需新卡（既有模板可用） |
| 3 | `| head` 截断长 stdout 的伪错误 | `python prng_rebuilt.py 1 \| head -3` 报 `OSError: Errno 22`——是管道提前关闭，不是脚本问题 | 重定向到文件再读；判据改为「无管道干净跑」 | 无需新卡（通用 shell 常识，记录在案） |

## Evidence 链摘要（脱敏）

| E-id | severity | status | source_type | 可复用命令模式 | 关联 Finding |
|------|----------|--------|-------------|----------------|--------------|
| E-001 | info | validated | command | `upx -d {sample}; 对比解包前后 stdout` | F-001/F-002 |
| E-002 | info | validated | static | `r2 -2q -c "aaa; s {main_addr}; pdf; q" {unpacked}` | F-001 |
| E-003 | info | validated | static | 同上（movabs 常量区） | F-002 |
| E-004 | info | validated | command | `python skillpack/skills/scripts/diff-runner.py work/assault-<target> --assault --function F-001` | F-001/F-002 |
| E-005 | info | validated | command | `python work/assault-<target>/build/prng_rebuilt.py 0\|1` | F-001/F-002 |

## 成品与审计

- deliverable: `build/prng_rebuilt.py`（Python 复刻，双模式；deliverable_present=yes）
- 两层过层证据：L1（E-001）+ L4（E-002/E-003）
- 路线调整记录：decision_delta 见 case timeline（工具修复不算路线调整，route 保持 rewrite）
- 审计：`review_case.py --verify-hashes --strict` PASS；assault 审计四项检查全绿

## 可复用准则

1. **加新模式后先做「三支解析一致性」对照**——同一行喂 rebuild/assault/update 三种模式，
   行为必须对齐（本次的坑）。
2. **UPX 往返产物与原版差几十字节属已知非确定性**（metadata/checksum 区），判据看行为
   不看字节——但要留 85 字节差异的完整记录，不许静默略过。
3. **壳层工具链的 stdout 会骗人**：本次 rabin2.exe 在 6.2.0 里是转发壳，直接跑会进
   交互模式（「No cookie is also a cookie」横幅）——判据改用 `r2 -2q -c '...'` 批处理模式。
