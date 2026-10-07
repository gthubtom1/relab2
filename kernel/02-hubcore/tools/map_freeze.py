#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""定档时拷功能表，并放上空白对照栏。光拷不算核对。不是运行核。"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from hub_io import _inside_no_links, _file_lock
from map_show import _rows, _read_card
from hub_memory import load_memory, memory_gate_gap, JOURNAL, projections

CONTRAST = """# 我们的 vs 原件

定档时才填。空白纸不算核对。光拷自己的功能表不算已经核对过原件。

- **这一档名字 / git：**
- **对照的原件是哪一份：**

| 功能 | 原件人看见 | 我们现在人看见 | 作用还在吗 |
|---|---|---|---|
|  |  |  |  |
"""


def _has_rows(text):
    for line in text.splitlines():
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if not cells or cells[0] in ("功能名",) or set("".join(cells)) <= set("-: "):
            continue
        if cells[0]:
            return True
    return False


def main():
    ap = argparse.ArgumentParser(description="冻一份功能表 + 对照栏（对照还要人填）")
    ap.add_argument("--product", required=True)
    ap.add_argument("--id", required=True, help="这一档名字，例如 git 短哈希")
    args = ap.parse_args()
    from hub_cmds import _is_hub_tree, _HUB_NOT_PRODUCT
    if _is_hub_tree(args.product):
        print(_HUB_NOT_PRODUCT, file=sys.stderr)
        return 2
    root = Path(args.product).resolve()
    try:
        _inside_no_links(root, JOURNAL + '.lock')
        with _file_lock(_inside_no_links(root, JOURNAL)):
            return freeze_snapshot(root, args.id)
    except (OSError, UnicodeError, ValueError) as exc:
        print(f'拒绝冻结：{exc}', file=sys.stderr)
        return 2


def freeze_snapshot(root, name):
    if not re.fullmatch(r"[A-Za-z0-9\u4e00-\u9fff][A-Za-z0-9._\-\u4e00-\u9fff]*", name) or name.endswith("."):
        print("冻本名只能包含字母、数字、中文、点、横线和下划线，不能以点结尾。", file=sys.stderr)
        return 2
    feat = root / "FEATURES.md"
    if not feat.is_file():
        print("没有 FEATURES.md，不能冻。", file=sys.stderr)
        return 1
    text = feat.read_text(encoding="utf-8-sig")
    if not _has_rows(text):
        print("功能表没有真实行，不能冻。", file=sys.stderr)
        return 1
    try:
        contract_path = root / ".hub" / "contract.json"
        if contract_path.is_file():
            try:
                contract = json.loads(contract_path.read_text(encoding="utf-8-sig"))
            except (OSError, UnicodeError, json.JSONDecodeError):
                contract = {}
            if isinstance(contract, dict) and contract.get("type") == "exe-rebuild":
                from hub_ask import _change_map_gap
                gap = _change_map_gap(root)
                if gap:
                    raise ValueError(gap)
        model = load_memory(root)
        memory_issue = memory_gate_gap(root)
        if memory_issue:
            raise ValueError(memory_issue)
        feat = _inside_no_links(root, "FEATURES.md")
        dest = _inside_no_links(root, f"frozen/{name}")
        # Validate every referenced card before creating any snapshot files.
        rows = _rows(text)
        if len({row[0] for row in rows}) != len(rows):
            raise ValueError("功能名重复，不能冻结含糊的现状")
        payload = {"FEATURES.md": feat.read_bytes()}
        if model is not None:
            payload[JOURNAL] = _inside_no_links(root, JOURNAL).read_bytes()
            for relative in projections(model):
                payload[relative] = _inside_no_links(root, relative).read_bytes()
        for row in rows:
            path, _ = _read_card(root, row)
            relative = path.relative_to(root).as_posix()
            if not relative.startswith("features/"):
                raise ValueError("冻本的功能卡片须位于产品 features/ 内")
            payload[relative] = path.read_bytes()
        mmap = _inside_no_links(root, "MAP.md")
        if mmap.exists():
            payload["MAP.md"] = mmap.read_bytes()
        cmap = root / "CHANGES.md"
        if cmap.is_file():
            payload["CHANGES.md"] = _inside_no_links(root, "CHANGES.md").read_bytes()
        manifest = {"version": 1, "id": name, "map_included": "MAP.md" in payload,
                    "files": {rel: hashlib.sha256(data).hexdigest() for rel, data in payload.items()}}
        with _file_lock(dest):
            # Reusing a name must never blend a new table with an old comparison.
            dest.mkdir(parents=True, exist_ok=False)
            for relative, data in payload.items():
                target = dest / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
            (dest / "对照-我们的vs原件.md").write_text(CONTRAST, encoding="utf-8")
            (dest / "snapshot.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"拒绝冻结：{exc}。已有冻本不会覆盖；不完整的新目录不得用于交付。", file=sys.stderr)
        return 2
    print(f"文件已放到 {dest} 。对照栏仍空白。")
    print("这不算已经核对过原件。空白对照躺在夹里更危险。填完对照之前，不得当吃新上游的原料，不得让旧客户去点。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
