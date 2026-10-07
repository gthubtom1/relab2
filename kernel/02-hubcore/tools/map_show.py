#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""总图分叉读。无 --id 只打目录；--id 才打开那一叉。空/毒表非零退出。不是运行核。"""
import argparse
import json
import sys
from pathlib import Path
from hub_ask import _read_feature_card as _read_card
from hub_memory import (load_memory, freshness, overview, card as memory_card,
                        resolve_node, impact, projection_gaps, LABELS, inherited_context)

POISON = ("已验证", "5 分钟", "5分钟", "清单很完善")


def _rows(text):
    rows = []
    for line in text.split("\n"):
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if not cells or set("".join(cells)) <= set("-: "):
            continue
        if cells[0] in ("功能名",):
            continue
        name = cells[0]
        if not name:
            continue
        use = cells[1] if len(cells) > 1 else ""
        now = cells[2] if len(cells) > 2 else ""
        card = cells[3] if len(cells) > 3 else ""
        rows.append((name, use, now, card))
    return rows


def _empty_msg(kind):
    if kind == "missing":
        return (
            "功能对照清单：没有表。新产品先讨论方案，不要向主人要功能表。"
            "旧项目先从源码、历史定档和原话恢复并标出证据缺口，只向主人核对无法恢复的决定。"
        )
    return (
        "功能对照清单：表在但没有真实行。新产品先讨论方案，不要向主人要功能表。"
        "旧项目先从已有材料恢复，不要让主人重新讲一遍。"
    )


def main():
    ap = argparse.ArgumentParser(description="总图分叉读；空则承认不记得")
    ap.add_argument("--product", required=True)
    ap.add_argument("--id", default="", help="只打开这一叉；不填则只打总图/功能名")
    ap.add_argument("--search", help="按功能名称、作用或当前方案找入口")
    ap.add_argument("--history", action="store_true", help="仅按需打开指定功能的历史")
    ap.add_argument("--drafts", action="store_true", help="展开指定功能尚未采用的想法")
    ap.add_argument("--check", action="store_true", help="检查声明材料与派生视图是否仍对应")
    ap.add_argument("--json", action="store_true", help="输出结构化当前视图")
    args = ap.parse_args()
    from hub_cmds import _is_hub_tree, _HUB_NOT_PRODUCT
    if _is_hub_tree(args.product):
        print(_HUB_NOT_PRODUCT, file=sys.stderr)
        return 2
    root = Path(args.product).resolve()
    try:
        model = load_memory(root)
        if model is not None:
            return show_memory(root, model, args)
    except (ValueError, TypeError, KeyError, OSError, UnicodeError) as exc:
        print(f"项目记忆不能可靠恢复：{exc}；保留原材料，不能把坏记录当空项目。", file=sys.stderr)
        return 2
    if args.search or args.history or args.drafts or args.json:
        print("这些入口需要持久项目记忆；旧表仍可按 --id 读取，迁移见 docs/PROJECT-MEMORY.md。")
        return 2
    print("旧式人工地图：尚不能判断总图、设计或实现位置是否已过期；修改前须对照相关材料。")
    print("这是给部长跑的，不要让主人敲命令。本命令不负责记得。有文件≠已验证。")
    print("禁止整仓重读。无 --id 只看目录；改哪再 --id 哪一叉。")
    feat = root / "FEATURES.md"
    if not feat.is_file():
        print(_empty_msg("missing"))
        return 1
    text = feat.read_text(encoding="utf-8-sig")
    rows = _rows(text)
    if not rows:
        print(_empty_msg("blank"))
        return 1
    blob = " ".join(x for row in rows for x in row)
    if any(p in blob for p in POISON):
        print("功能对照清单：不记得。过期毒表（格子里写了已验证/5分钟/完善）。打开即失败，改名作废，禁止下一场先读。")
        return 2
    want = (args.id or "").strip()
    if not want:
        mmap = root / "MAP.md"
        if mmap.is_file():
            body = mmap.read_text(encoding="utf-8-sig").strip()
            if body:
                print("--- 总图 MAP.md ---")
                print(body)
                print("--- 功能名目录（不是正文）---")
        else:
            print("总图：没有 MAP.md，下面只列功能名和作用。细则不要一次灌完。")
        for name, use, _now, _card in rows:
            print(f"- {name}｜作用：{use or '（空）'}")
        print("改哪一个：map_show.py --product ... --id 功能名")
        return 0
    hit = [r for r in rows if r[0] == want]
    if not hit:
        print(f"没有这一叉「{want}」。总图上现有：" + "、".join(r[0] for r in rows))
        return 3
    if len(hit) != 1:
        print(f"功能名「{want}」重复，不能判断当前是哪一行。")
        return 2
    name, use, now, card = hit[0]
    try:
        card_path, card_body = _read_card(root, hit[0])
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"功能记忆未就绪：{exc}")
        return 2
    print(f"这一叉：{name}")
    print(f"作用：{use or '（空）'}")
    print(f"现在人看见（申报，不是已验证）：{now or '（空）'}")
    print(f"--- {card_path.name} ---")
    print(card_body)
    return 0


def show_memory(root, model, args):
    if (args.history or args.drafts) and not args.id:
        raise ValueError("历史与草稿按指定功能 --id 展开，避免灌入整个项目")
    key = resolve_node(model, args.id) if args.id else None
    if args.history:
        records = [{"revision": event["revision"], "reason": event["reason"], "feature": event["nodes"][key]}
                   for event in model["history"] if key in event["nodes"]]
        print(json.dumps({"historical_only": True, "records": records}, ensure_ascii=False, indent=2))
        return 0
    states = freshness(root, model)
    gaps = projection_gaps(root, model)
    selected = [key] if key else [k for k, n in model["nodes"].items() if not n.get("replaced_by")]
    if args.search:
        query = args.search.casefold()
        selected = [k for k in selected if query in ' '.join(str(model['nodes'][k].get(f, ''))
                    for f in ('name', 'purpose', 'intent')).casefold() or any(
                    k in event['nodes'] and query in event['nodes'][k]['name'].casefold()
                    for event in model['history'])]
    bad = [k for k in selected if states[k]["state"] in ("stale", "missing", "unreviewed")]
    if args.json:
        print(json.dumps({"revision": model["revision"], "project": model["project"],
              "features": [{"feature": {f: v for f, v in model["nodes"][k].items() if args.drafts or f != 'drafts'},
                            "freshness": states[k], "consumers": impact(model, k),
                            "inherited_context": inherited_context(model, k)} for k in selected],
              "projection_gaps": gaps}, ensure_ascii=False, indent=2))
    else:
        print(f"持久项目记忆 revision={model['revision']}；当前视图，历史按需展开。")
        if key:
            print(memory_card(model, key, states[key], include_drafts=args.drafts))
        elif args.search:
            for k in selected:
                print(f"- {model['nodes'][k]['name']} ({k})：{model['nodes'][k]['purpose']}")
            if not selected:
                print("当前图中没有匹配项；从项目入口/相关代码调查后补图，不能推断功能不存在。")
        else:
            print(overview(model, states))
        if gaps:
            print("派生文件与共同来源不一致：" + "、".join(gaps) + "；先核对差异，再 --render；本次按持久记录导航。")
        if bad:
            print("待重新核对：" + "、".join(bad) + "。先读相关材料和实际消费者，再更新理解与验证。")
        print("只检查已声明材料/关系；新组件、外部环境和漏掉的消费者仍须工程调查。")
    return 2 if (bad and (key or args.check)) or (gaps and args.check) else 0


if __name__ == "__main__":
    sys.exit(main())
