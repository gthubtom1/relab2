#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test-diff-runner-parse-negctl.py —— `cases:` 写法的负控（K1 防复发）。

为什么有这个负控（2026-10-16 真事故）
-------------------------------------
`work/_full-audit/report-e2e.md` 的 K1 是本轮唯一的「**照文档做就会卡死**」项：

  `skills/templates/assault.md` 原来把 `diff_baseline` 的 cases 写成**单行文本**
  （`- cases: <输入清单>` 带反引号），而 `diff-runner.py` 的 `parse_assault()` 只认
  **嵌套列表**（`- F-001 | input=…`）。于是按模板填完直接报
  `ERROR: no input given and assault.md lists none for F-001`、RC=2。
  `templates/rebuild.md` 给的是嵌套列表示例 —— 两个人走同一条工具，一个能跑一个卡死。

K1 已修（模板改成嵌套列表，与 rebuild.md 一致）。**但修完没有任何门在守护它**：
`test-assault-audit-negctl.py` 验的是 `review_case.py` 的滚动报告审计，它
**不调 diff-runner**，其 `ASSAULT_TEMPLATE` 里也**从不构造 `- cases:` 块**。

本负控补的就是这个洞：直接 import `diff-runner.py` 的 `parse_assault()`，
喂**两种写法**，断言「嵌套列表解析出 cases」且「单行文本解析不出 cases（= 就是那个坑）」。
一旦有人把模板改回单行文本、或把解析器改成只认别的形态，本负控立刻判红。

判据：
  1. 嵌套列表写法 → `cases` 非空，且值正确（去 `input=` 前缀与反引号）
  2. 单行文本写法 → `cases` 为空（**证明模板的旧写法确实解析不了**）
  3. 真实模板 `templates/assault.md` → `parse_assault` 能解析出它的示例 cases
     （模板与解析器口径一致的**持续**保证，不靠人眼看）

用法：python skillpack/skills/scripts/test-diff-runner-parse-negctl.py
退出码：0 全部通过；1 有断言失败。
"""
from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
DIFF_RUNNER = HERE / "diff-runner.py"
TEMPLATE = HERE.parent / "templates" / "assault.md"


def load_diff_runner():
    """按文件路径加载 diff-runner.py（它不在 import path 上）。"""
    spec = importlib.util.spec_from_file_location("relab2_diff_runner", DIFF_RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {DIFF_RUNNER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


NESTED = """\
# assault

## diff_baseline

- baseline_command: `./orig {input}`
- rebuilt_command: `./new {input}`
- cases:
  - F-001 | input=`0`
  - F-002 | input=`1`

## out_of_delivery

| 项 | 理由 |
|----|------|
| x | y |
"""

SINGLE_LINE = """\
# assault

## diff_baseline

- baseline_command: `./orig {input}`
- rebuilt_command: `./new {input}`
- cases: `<输入清单>`

## out_of_delivery

| 项 | 理由 |
|----|------|
| x | y |
"""


def parse_with(module, text: str):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "assault.md").write_text(text, encoding="utf-8")
        return module.parse_assault(root)


def main() -> int:
    problems: list[str] = []
    module = load_diff_runner()

    # ① 嵌套列表 —— 必须解析出 cases（这是模板现在的写法）
    nested = parse_with(module, NESTED)
    cases = nested["cases"] if nested else None
    if not cases:
        problems.append("嵌套列表写法解析出 0 条 case（模板现在就是这么写的）")
    else:
        got = [c[0] for c in cases]
        vals = [c[1] for c in cases]
        if got != ["F-001", "F-002"]:
            problems.append(f"嵌套列表 case id 解析错：{got}")
        if vals != ["0", "1"]:
            problems.append(f"嵌套列表 input 值解析错（应剥掉 input= 与反引号）：{vals}")

    # ② 单行文本 —— 必须解析不出（这就是 K1 那个坑：旧模板写法）
    single = parse_with(module, SINGLE_LINE)
    single_cases = single["cases"] if single else None
    if single_cases:
        problems.append(
            "单行文本写法竟然解析出了 case —— 要么解析器被改宽了（需复核 K1 的坑是否复发），"
            f"要么本负控的坏样本不再是坏样本：{single_cases}"
        )

    # ③ 真实模板 —— parse_assault 必须能解析出它的示例 cases（口径一致的持续保证）
    if not TEMPLATE.is_file():
        problems.append(f"找不到模板：{TEMPLATE}")
    else:
        real = parse_with(module, TEMPLATE.read_text(encoding="utf-8-sig"))
        real_cases = real["cases"] if real else None
        if not real_cases:
            problems.append(
                "真实 templates/assault.md 的 cases 解析出 0 条 —— 模板写法与 "
                "parse_assault 的口径又分家了（这正是 K1 的形态，改回去就会卡死）"
            )
        elif not all(c[1] for c in real_cases):
            problems.append(f"真实模板的 case 有空的 input 值：{real_cases}")

    for p in problems:
        print(f"FAIL {p}")
    if problems:
        print(f"\n{len(problems)} problem(s)")
        return 1
    print("OK   嵌套列表 → 解析出 cases")
    print("OK   单行文本 → 解析不出（K1 的坑仍在被识别）")
    print("OK   真实 templates/assault.md → 与 parse_assault 口径一致")
    print("\n3/3 controls honoured")
    return 0


if __name__ == "__main__":
    sys.exit(main())
