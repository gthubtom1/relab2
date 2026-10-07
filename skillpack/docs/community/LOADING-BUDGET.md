# 加载预算（T11 / 规范 17.25）

执行位置：`skills/scripts/community-route.py`（`MAX_WRAPPER_CANDIDATES` /
`MAX_TOTAL_REFERENCES` / `REFERENCE_LIMIT`）；wrapper 加载指令见
`skills/community/{ctf-hub,hack-hub,delivery,apk-extension}/SKILL.md` 的
`Loading budget` 段。

## 1. 预算数值（全部可在本仓库重跑复算）

| 项 | 值 | 说明 |
|---|---|---|
| 单次初筛 wrapper 上限 | 5（`MAX_WRAPPER_CANDIDATES`） | 规范 17.25"registry 初筛最多返回 5 个 wrapper"；`--limit` 越界（<1 或 >5）直接 exit 2 |
| 单次查询 reference 总数上限 | 50（`MAX_TOTAL_REFERENCES`） | 命中总数（截断前）在各 wrapper 求和；超预算停止并报告，不静默截断 |
| 每 wrapper 初次展示 | 3（`REFERENCE_LIMIT`，不动） | 产品决策，`test-route-ranking.py` 钉死为 3；第 4 个起走二级加载 |
| 置信度门 | 0.35（`MIN_CONFIDENCE`，不动） | `confidence = best_score / hint 词数`，低于此值为 `low_confidence` |
| 并列模糊带 | 0.20（`NEAR_TIE_DELTA`，不动） | 首尾 wrapper 分差 ≤20% 为 `ambiguous_tie` |

超预算行为：`status=blocked` / `failure_reason=budget_exceeded` / exit 20，
payload 带 `budget{total_references, wrapper_candidates, requested_limit,
effective_limit}`、`required_action`（收窄 hint 或按 `--source` 分查）与
`confirmation`（报出收窄后的 hint 与 `--source` 取值，等人工确认）。

17.25 其余项（单 reference 字符数/总上下文预算、route 与脚本最大耗时、
artifact/日志大小上限、取消与中断行为）超出本仓库只读查询器的执行面，
记为 policy manifest 变更请求（见 §3），不由本卡虚构数值。

## 2. 测量（改前现状，复算命令见 §4）

- 普通 hint 命中总数：`kerberos` → 1；`CTF APK smali` → 24；
  `SSRF metadata endpoint access` → 30（3 个 wrapper，各展示 3 个，
  27 个被静默吞掉，exit 0）。
- 截断位置：`_wrapper_result` 内 `shown = references[:REFERENCE_LIMIT]`
 （`community-route.py:843`），`REFERENCE_LIMIT` 当时值 3。
- 上限检查：无。`--limit` 任意整数均被接受（`max(1, limit)`），候选总数无任何检查。
- `confidence`：`min(1.0, best_score / len(hint_terms))`（`community-route.py:849`），
  输出 `confidence` + `minimum_confidence=0.35`；`ambiguity` 即 `ambiguous_tie`
 （分差 ≤20%）与 `profile_unresolved`，`--limit` 生效前先判歧义（`lookup` 末尾）。
- 阈值安全边际：57 个诱饵/正向用例的 hint 命中总数最大 42（`融合`），
  全部 < 50，故 50 不触碰任何既有守卫；`web api security`（68）与
  长混合 hint（70）超预算。

## 3. Policy manifest 变更请求（登记，非本卡执行）

请求 T02 / policy manifest owner 落地：

1. 把 `max_wrapper_candidates=5`、`max_total_references=50`、
   `reference_limit_per_wrapper=3` 写入 policy manifest（schema 或等价清单），
   并在黄金测试中断言三值。
2. 17.25 剩余预算（单 reference 字符数、总上下文预算、各脚本最大耗时与大小上限、
   取消/超时/中断行为）需有执行面的 owner 认领数值，本卡只提需求不编数字。

## 4. 复算

```text
$env:PYTHONIOENCODING='utf-8'
D:\EXE\python\python.exe skills/scripts/community-route.py --hint "kerberos" --json            # exit 0
D:\EXE\python\python.exe skills/scripts/community-route.py --hint "web api security" --json   # exit 20 budget_exceeded
D:\EXE\python\python.exe skills/scripts/community-route.py --hint "kerberos" --limit 0        # exit 2
D:\EXE\python\python.exe skills/scripts/community-route.py --hint "kerberos" --limit 9        # exit 2
D:\EXE\python\python.exe skills/scripts/test-community-route.py      # exit 0
D:\EXE\python\python.exe skills/scripts/test-route-ranking.py        # exit 0
D:\EXE\python\python.exe skills/scripts/test-community-decoys.py     # exit 0（9 条具名 over-trigger 为既有登记）
D:\EXE\python\python.exe skills/scripts/verify-routing-signals.py --check   # exit 0
D:\EXE\python\python.exe skills/scripts/test-routing-signals.py      # exit 0
```
