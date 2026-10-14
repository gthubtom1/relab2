#!/usr/bin/env python3
"""给 SKILL.md 批量追加 5 段结构件（L1.1 / L1.3）。

用法：
    python add-structure-sections.py [--dry-run] [--only <skill>]

设计要点：
- 定制内容在 SPECS dict 里（key = 技能名），缺省走 DEFAULT_TEMPLLATE
- 幂等：已有 `## When NOT to use` 的技能跳过
- 不改 description / frontmatter / 既有正文
- 引用统一用相对路径，指向三份契约源
"""
from __future__ import annotations
import argparse
import io
import os
import sys

SKILLS_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PIVOT_LINK = "../ops/skill-pivot-contract.md"
CONF_LINK = "../ops/confidence-vocabulary.md"
MODEL_LINK = "../ops/binary-model.md"
ASSAULT = "../reverse-engineering/references/assault-entry.md"
ADF = "../ops/analysis-decision-framework.md"


def build_sections(name: str, spec: dict) -> str:
    """按模板拼出 5 段。spec 的键：
    not_use: [(负例描述, 去向路径)]   —— 至少 2 条，第 3 条可空
    pivot:   [(触发证据, 去向路径)]   —— 至少 2 条
    dod:     [外部可观测条件]         —— 至少 2 条
    conf:    (confirmed 描述, low 描述)
    dod_note / extra: 可选附加行
    """
    not_use = spec.get("not_use", [])
    pivot = spec.get("pivot", [])
    dod = spec.get("dod", [])
    conf = spec.get("conf", ("", ""))

    out = ["\n---\n", "## When NOT to use（近邻负例）\n"]
    for desc, dest in not_use:
        out.append(f"- {desc} → 用 `{dest}`")
    if spec.get("not_use_pre"):
        out.append(f"- {spec['not_use_pre']}")
    out.append("")
    out.append("## When to Pivot\n")
    out.append(f"信号与判据见 `{PIVOT_LINK}`。本技能去向：\n")
    out.append("| 触发证据 | 换到 |")
    out.append("|---|---|")
    for trig, dest in pivot:
        out.append(f"| {trig} | `{dest}` |")
    out.append("")
    out.append("## 定义完成\n")
    out.append("本技能产出算「完成」的**外部可观测**条件（不许写形容词）：\n")
    for d in dod:
        out.append(f"- {d}")
    out.append("")
    out.append("## 输出契约\n")
    out.append("```")
    out.append("FACT:       <观察，带来源：命令 / 文件:行 / Evidence ID>")
    out.append(f"HYPOTHESIS: <可测试断言 + confidence: high|medium|low>（状态见 `{MODEL_LINK}`）")
    out.append("QUESTION:   <当前最大不确定点>")
    out.append("NEXT:       <继续 | 换技能 | 停止（附成本判据）>")
    out.append("```\n")
    out.append("## 置信度词表\n")
    out.append(f"词表见 `{CONF_LINK}`。本技能特有判据：\n")
    out.append(f"- `confirmed`：{conf[0]}")
    out.append(f"- `low`：{conf[1]}")
    if spec.get("extra"):
        out.append("")
        out.append(spec["extra"])
    out.append("")
    return "\n".join(out)


def insert_before_related(path: str, block: str) -> bool:
    """把 block 插到 `## 相关` 之前；没有则追加到末尾。返回是否真的写入了。"""
    with io.open(path, encoding="utf-8-sig") as f:
        txt = f.read()
    if "## When NOT to use" in txt:
        return False
    marker = "\n## 相关\n"
    idx = txt.find(marker)
    if idx >= 0:
        new = txt[:idx] + block + txt[idx + 1:]
    else:
        if not txt.endswith("\n"):
            txt += "\n"
        new = txt + block
    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(new)
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only", default="")
    ap.add_argument("--root", default=SKILLS_ROOT)
    args = ap.parse_args()

    # 延迟导入 SPECS，避免 --help 时报错
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from structure_specs import SPECS  # noqa: E402

    names = [args.only] if args.only else sorted(SPECS)
    changed, skipped, missing = [], [], []
    for name in names:
        p = os.path.join(args.root, name, "SKILL.md")
        if not os.path.isfile(p):
            missing.append(name)
            continue
        spec = SPECS[name]
        block = build_sections(name, spec)
        if args.dry_run:
            print(f"[dry-run] would add {block.count(chr(10)):3d} lines -> {name}")
            continue
        if insert_before_related(p, block):
            changed.append(name)
        else:
            skipped.append(name)
    if not args.dry_run:
        print(f"changed={len(changed)} skipped={len(skipped)} missing={len(missing)}")
        if skipped:
            print("  skipped(已有): " + " ".join(skipped))
        if missing:
            print("  missing: " + " ".join(missing))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
