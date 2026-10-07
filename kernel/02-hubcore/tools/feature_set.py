#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""覆盖当前功能表一行。只认最新。不写已验证。不是运行核。"""
import argparse
import sys
from pathlib import Path
from hub_io import _inside_no_links
from hub_memory import apply_update, decode, render_memory, JOURNAL

STUB = """# 当前功能表（只认最新）

没有「已验证」列。看见/当前是另一只眼。

| 功能名 | 作用是什么 | 现在人看见（申报） | 卡片 |
|---|---|---|---|
"""


def _parse(text):
    pre, table, post = [], [], []
    in_table = False
    seen_table = False
    header = None
    for line in text.split("\n"):
        s = line.strip()
        if s.startswith("|"):
            in_table = True
            seen_table = True
            cells = [c.strip() for c in s.strip("|").split("|")]
            if header is None:
                header = cells
                table.append(line)
                continue
            if set("".join(cells)) <= set("-: "):
                table.append(line)
                continue
            table.append(line)
            continue
        if in_table and seen_table:
            in_table = False
            post.append(line)
        elif not seen_table:
            pre.append(line)
        else:
            post.append(line)
    return pre, header or ["功能名", "作用是什么", "现在人看见（申报）", "卡片"], table, post


def _data_rows(table_lines):
    out = []
    for line in table_lines:
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not cells or cells[0] in ("功能名",) or set("".join(cells)) <= set("-: "):
            continue
        if not cells[0]:
            continue
        out.append(cells)
    return out


def main():
    ap = argparse.ArgumentParser(description="覆盖一行功能（只认最新，不写已验证）")
    ap.add_argument("--product", required=True)
    ap.add_argument("--apply", help="更新项目记忆的 JSON 文件；字段见 docs/PROJECT-MEMORY.md")
    ap.add_argument("--render", action="store_true", help="从持久记录重建派生视图，不刷新材料核对")
    ap.add_argument("--id", help="旧式功能名；新项目记忆使用 --apply")
    ap.add_argument("--use", default=None, dest="use", help="作用是什么；省略则保留原值")
    ap.add_argument("--now", help="现在人看见（申报）")
    args = ap.parse_args()
    from hub_cmds import _is_hub_tree, _HUB_NOT_PRODUCT
    if _is_hub_tree(args.product):
        print(_HUB_NOT_PRODUCT, file=sys.stderr)
        return 2
    if args.apply or args.render:
        if (args.apply and args.render) or args.id or args.use is not None or args.now:
            ap.error("--apply/--render 不能与旧式行修改混用")
        try:
            if args.apply:
                model = apply_update(args.product, decode(Path(args.apply).read_text(encoding="utf-8-sig")))
            else:
                model = render_memory(args.product)
            print(f"项目记忆 revision={model['revision']}；总图和卡片已由共同来源生成。业务完成仍查 state work。")
            return 0
        except (OSError, UnicodeError, ValueError, TypeError, KeyError) as exc:
            print(f"项目记忆未更新/视图未齐备：{exc}", file=sys.stderr)
            return 2
    if not args.id or args.now is None:
        ap.error("旧式修改需要 --id 与 --now；新记忆用 --apply")
    if (Path(args.product) / JOURNAL).exists():
        print("本项目已使用持久记忆，请通过 --apply 更新同一功能 ID；不能另写一份功能表。", file=sys.stderr)
        return 2
    if (not args.id.strip() or args.id in (".", "..")
            or any(c in args.id for c in '/\\:*?"<>|\r\n\v\f\x1c\x1d\x1e\x85\u2028\u2029')
            or any(c in (args.use or '') + args.now for c in '|\r\n\v\f\x1c\x1d\x1e\x85\u2028\u2029')):
        print("拒绝：功能名须是单个文件名，表格字段不能含换行或竖线。", file=sys.stderr)
        return 2
    if "已验证" in args.id or "已验证" in (args.use or '') or "已验证" in args.now:
        print("拒绝：不能把「已验证」写进功能表。", file=sys.stderr)
        return 2
    root = Path(args.product).resolve()
    try:
        feat = _inside_no_links(root, "FEATURES.md")
    except ValueError as exc:
        print(f"拒绝：{exc}", file=sys.stderr)
        return 2
    if feat.is_file():
        text = feat.read_text(encoding="utf-8-sig")
    else:
        text = STUB
    pre, header, table_lines, post = _parse(text)
    rows = _data_rows(table_lines)
    if len([cells for cells in rows if cells[0] == args.id]) > 1:
        print("拒绝：已有同名功能不止一行，先核对现状。", file=sys.stderr)
        return 2
    replaced = False
    new_cells = [args.id, args.use or '', args.now, f"features/{args.id}.md"]
    for i, cells in enumerate(rows):
        if cells[0] == args.id:
            purpose = args.use if args.use is not None else (cells[1] if len(cells) > 1 else '')
            new_cells = [args.id, purpose, args.now, *(cells[3:] or [f"features/{args.id}.md"])]
            rows[i] = new_cells
            replaced = True
            break
    if not replaced:
        rows.append(new_cells)
    ncol = max(len(header), 4)
    def fmt(cells):
        pad = cells + [""] * (ncol - len(cells))
        return "| " + " | ".join(pad[:ncol]) + " |"
    sep = "|" + "|".join(["---"] * ncol) + "|"
    body = [fmt(header), sep] + [fmt(r) for r in rows]
    out = "\n".join(pre).rstrip() + "\n\n" + "\n".join(body) + "\n"
    if post:
        out += "\n" + "\n".join(post).rstrip() + "\n"
    feat.write_text(out, encoding="utf-8")
    print(f"已覆盖功能「{args.id}」。请按实际观察同步卡片，再用 map_show --id 核对；本命令不证明业务已通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
