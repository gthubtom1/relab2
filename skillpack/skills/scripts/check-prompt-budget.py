#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校验每个技能 SKILL.md 的 frontmatter `description` 是否满足"可被检索"的形状。

背景：宿主会把 description 预载进系统提示，作为**选择该技能的唯一信号**。
所以它必须是：单行、带"用于：/不要用于："、长度可控、不是 YAML 块标量。

规则（全部硬性）：
  1. 存在 `description:` 且**单行**（不能是 `|` / `>` / `|-` / `>-` 块标量）
  2. 长度（UTF-8 字节）在 40..220 之间
  3. 含 `用于：`（正向触发场景）
  4. 不含换行、不含未转义的 `"` 造成的 YAML 破坏（用未加引号的 plain scalar）
  5. 不含 `务必使用此技能` / `Ensure to use this skill`（老式"抢触发"话术）
  6. 总量 ≤ `--max-total-bytes`（默认 16000 B；超了 exit 20。标定依据见常量上方的注释）

★ 为什么**不要** `不要用于：`（anti-example）—— 这是实测结论，不是口味：
  2026-10-14，同一批 93 条自然说法、同一套 46 技能菜单、只换 description 文本，让模型盲选：
    改前（含抢触发话术的长描述） 88/93 = 94.6%
    改后（三段式 + anti-example）  86/93 = 92.5%   ← 没涨，掉了 2 例
  逐条看差异只有 4 例，其中 **3 例是 anti-example 把模型"推"错了邻居**
  （`windows-ad` 写"全链→attack-chain"→ 模型真的去选了 attack-chain；
    `web-protocol-reverse` 写"JS→js-reverse"→ 模型真的去选了 js-reverse）。
  也就是说：在 220 B 的预算里，点名邻居是**吸引子**而不是排斥项，净效果 ≤ 0。
  消歧该由 `route-scope.md` 的候选全集（+ SYMPTOM-INDEX）承担，那两处是**按当前节点**给候选，
  比一段永远常驻的静态反例更准、也更便宜。
  （要复跑这个实验：`skills/tests/experiments/desc-ab/` 下有 runner 与两份报告（含三个菜单的结果）。）

★ 为什么有"总量预算"这一档：这些 description 会被宿主**预载进系统提示，每轮都付费**。
  单个达标 ≠ 全局划算。2026-10-14 基线：57 技能 = 10388 B ≈ 3.5K tokens（两段式）。
  上限 16000 B 的标定依据（宿主真实预算换算）见文件内 MAX_TOTAL_BYTES 上方注释。

用法：
    python skills/scripts/check-skill-descriptions.py
    python skills/scripts/check-skill-descriptions.py --json
    python skills/scripts/check-prompt-budget.py --max-total-bytes 16000
退出码：0 全过／1 形状有问题／20 总量超预算（常驻上下文负债）
"""
from __future__ import annotations

import argparse
import glob
import io
import json
import os
import re
import sys

MIN_BYTES, MAX_BYTES = 40, 220
# ★★ 总量预算的标定依据（2026-10-14 重新标定，不是无声放宽）
#
# 宿主侧的真实约束（实测/公开 Issue 数据）：
#   - Anthropic Issue #11045：元数据预算约 15,500–16,000 **字符**；每技能约 109 字符固定开销
#     （XML 标签 / name / location）；63 技能时只有 42 能进系统提示，超限**静默隐藏且无警告**。
#   - 本包 57 技能：57 × 109 ≈ 6,213 字符 固定开销。
#   - 剩给 description 内容的字符额度：15,500 − 6,213 ≈ 9,287 字符。
#
# 换算到本脚本的"字节"口径（中文 UTF-8 ≈ 3 B/字）：
#   9,287 字符 × 3 ≈ 27,861 B —— 这是硬上限，不是可以随便用的额度。
#
# 取 16,000 B 的理由：
#   16,000 B ≈ 5,333 字符内容 + 6,213 字符开销 ≈ 11,546 字符 < 15,500 → 留 ~25% 余量。
#   同时仍比"每技能 220 B × 57 = 12,540 B"宽松，不会因为加几个技能就撞墙。
#
# 为什么原来定 10,000：那是按"只算 content、且按 47 技能"拍的保守值。
# 现在技能数涨到 57 且要补日常开发域，必须按宿主真实预算重推，否则门会逼着人
# 把有意义的 description 砍成噪声（形状达标、触发失效）—— 那正是上一轮已证伪的方向。
MAX_TOTAL_BYTES = 16000
ROUTE_SCOPE_BUDGET = 1000  # route-scope.md 固定注入段的上限（每次点火读一次，不是每轮）
BANNED = ("务必使用此技能", "Ensure to use this skill", "MUST use this skill")
REQUIRE_ANTI = False  # 见下：anti-example 已实测无收益且会反噬，默认不再要求


def check(path: str) -> list[str]:
    raw = io.open(path, "r", encoding="utf-8-sig", errors="replace").read()
    m = re.match(r"^---\s*\n(.*?)\n---", raw, re.S)
    if not m:
        return ["no frontmatter"]
    fm = m.group(1)
    dm = re.search(r"^description:[ \t]*(.*)$", fm, re.M)
    if not dm:
        return ["no description field"]
    val = dm.group(1).strip()
    errs: list[str] = []

    # 1. 块标量 / 多行
    if val in ("|", ">", "|-", ">-", "|+", ">+", "|2", ">2", "|2-", ">2-"):
        errs.append("description is a YAML block scalar (must be single line)")
    if val.startswith("|") or val.startswith(">"):
        errs.append("description starts with block indicator")
    # 2. 长度
    n = len(val.encode("utf-8"))
    if n < MIN_BYTES:
        errs.append(f"too short ({n} bytes < {MIN_BYTES})")
    if n > MAX_BYTES:
        errs.append(f"too long ({n} bytes > {MAX_BYTES})")
    # 3. 结构：必须给出正向触发场景
    if "用于：" not in val:
        errs.append("missing `用于：`")
    if REQUIRE_ANTI and "不要用于：" not in val:
        errs.append("missing `不要用于：`")
    # 4. YAML 破坏（plain scalar 里出现 ": " 或 " #" 会出问题）
    if re.search(r":\s", val):
        errs.append("plain scalar contains ': ' (quote it or remove)")
    if re.search(r"\s#", val):
        errs.append("plain scalar contains ' #' (quote it or remove)")
    # 5. 老式抢触发话术
    for b in BANNED:
        if b in val:
            errs.append(f"contains legacy trigger phrase: {b}")
    return errs


def _extract_section(path: str, start_pat: str, stop_pat: str, ps: bool) -> list[str]:
    """从两个写入器里抠出「固定注入段」的**渲染后**文本。

    ps=True  → master-route.ps1 的 `[void]$sb.AppendLine('...')`
    ps=False → master-route.sh  的 `"...",`
    返回渲染行列表（已去掉引号与转义）。
    """
    out: list[str] = []
    inside = False
    for line in io.open(path, encoding="utf-8-sig").read().splitlines():
        if not inside:
            if re.search(start_pat, line):
                inside = True
            else:
                continue
        if re.search(stop_pat, line):
            break
        if ps:
            m = re.search(r"\[void\]\$sb\.AppendLine\('(.*)'\)\s*$", line)
            if m:
                out.append(m.group(1))
        else:
            m = re.search(r'^\s*"(.*)",\s*$', line)
            if m:
                out.append(m.group(1).replace('\\"', '"'))
    return out


def check_route_scope(root: str) -> list[str]:
    """route-scope.md 的固定段：两份写入器必须渲染出**同样的字节**，且总量受预算约束。

    它每次点火都会被写出来、由 agent 读一次 —— 不是每轮付费，但也不能无声膨胀。
    （对比：description 是**每轮**都在系统提示里，所以那一条的预算才是硬的。）
    """
    errs: list[str] = []
    ps = os.path.join(root, "scripts", "master-route.ps1")
    sh = os.path.join(root, "scripts", "master-route.sh")
    if not (os.path.isfile(ps) and os.path.isfile(sh)):
        return ["route-scope 固定段检查跳过：找不到 master-route.ps1/.sh"]
    try:
        a = _extract_section(ps, r"## 怎么用这份路由", r"## Notes", ps=True)
        b = _extract_section(sh, r"## 怎么用这份路由", r"## Notes", ps=False)
    except Exception as e:  # noqa: BLE001
        return [f"route-scope 固定段抽取失败：{e}"]
    if not a or not b:
        return ["route-scope 固定段为空（抽取标记可能已被改动）"]
    if a != b:
        errs.append("route-scope 固定段两侧不一致：master-route.ps1 与 .sh 渲染结果不同")
    n = len("\n".join(a).encode("utf-8"))
    if n > ROUTE_SCOPE_BUDGET:
        errs.append(f"route-scope 固定段 {n} B > 预算 {ROUTE_SCOPE_BUDGET} B（每次点火都要读一次）")
    return errs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--max-total-bytes", type=int, default=MAX_TOTAL_BYTES,
                    help=f"所有 description 的 UTF-8 字节总量上限（默认 {MAX_TOTAL_BYTES}）；超出 exit 20")
    ap.add_argument("--root", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ap.add_argument("--skip-route-scope", action="store_true",
                    help="跳过 route-scope.md 固定段的检查（只查 description）")
    args = ap.parse_args()

    # ★ 2026-10-15 审计 P3：以前只看一层，嵌套技能（community/* 等 6 个）不被统计。
    #   register-skills.ps1 已改递归，这里必须同口径。
    paths = sorted(glob.glob(os.path.join(args.root, "**", "SKILL.md"), recursive=True))
    bad: dict[str, list[str]] = {}
    sizes: list[tuple[int, str]] = []
    for p in paths:
        errs = check(p)
        name = os.path.basename(os.path.dirname(p))
        if errs:
            bad[name] = errs
        else:
            raw = io.open(p, "r", encoding="utf-8-sig", errors="replace").read()
            dm = re.search(r"^description:[ \t]*(.*)$", raw, re.M)
            sizes.append((len(dm.group(1).strip().encode("utf-8")), name))

    total = sum(s for s, _ in sizes)
    over_budget = total > args.max_total_bytes
    rs_errs = [] if args.skip_route_scope else check_route_scope(args.root)
    if args.json:
        print(json.dumps({
            "checked": len(paths), "ok": len(sizes), "bad": bad,
            "description_total_bytes": total, "approx_tokens": total // 3,
            "max_total_bytes": args.max_total_bytes, "over_budget": over_budget,
            "largest": sorted(sizes, reverse=True)[:5],
            "route_scope_errors": rs_errs,
            "route_scope_budget_bytes": ROUTE_SCOPE_BUDGET,
        }, ensure_ascii=False, indent=2))
    else:
        print(f"checked={len(paths)} ok={len(sizes)} bad={len(bad)}")
        print(f"description 合计 {total} 字节 ≈ {total // 3} tokens"
              f"  （预算上限 {args.max_total_bytes} B，用 {total / args.max_total_bytes:.0%}）")
        if bad:
            print("\n有问题：")
            for name, errs in sorted(bad.items()):
                print(f"  {name}: {'; '.join(errs)}")
        if rs_errs:
            print("\nroute-scope.md 固定段：")
            for e in rs_errs:
                print(f"  {e}")
        else:
            print(f"route-scope.md 固定段：OK（两侧一致，≤ {ROUTE_SCOPE_BUDGET} B）")
        if over_budget:
            print(f"\nBLOCKED: 常驻预算超限 —— {total} B > {args.max_total_bytes} B。")
            print("  这些 description 每轮对话都要付费。加技能/加字数前先做取舍：")
            print("  ① 真需要这么长吗 ② 是不是该合并/退役某个技能")
            print("  ③ 确实要加，就先上调 --max-total-bytes 并在 PR 里写清为什么值这么多常驻 token")
    if bad or rs_errs:
        return 1
    return 20 if over_budget else 0


if __name__ == "__main__":
    sys.exit(main())
