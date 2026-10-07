"""压缩契约：上下文被压缩以后，留在里面的是什么。

现有系统里没有这一层（hubdock 全库无 summar*/compact*/trim* 实现），
所以压缩由宿主自己做，宿主总结的是"当时上下文里的一切"——
包括插头、包括那次 status 的缺口长文，于是历史被二次固化。

本模块只做一件事：把"该活下来什么"变成一份可签的清单。
    活下来：当前任务、当前阶段、当前目标、当前阻塞、已确认决策、下一步、必须守的约束。
    不活下来：历史事件正文、收据正文、旧资料正文——它们留在盘上，按需取回。
取回方式写进 dropped.json，压缩后不必重新总结历史。
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from . import paths, store

FIELDS = ("intent", "stage", "goal", "next", "blockers",
          "confirmed_decisions", "constraints")


def contract(product: Path) -> dict:
    return {
        "survivor_fields": list(paths.load_config()["survivor_fields"]),
        "rule": [
            "压缩后必须保留且只保留 survivor_fields 里的东西。",
            "历史事件正文、探针收据正文、旧版本资料正文不进入压缩摘要。",
            "被丢掉的不是删除：只写进 dropped.json 的指针，需要时按指针取回。",
            "取回任何一份被丢掉的资料，都要带读取意图。",
        ],
    }


def build(product: Path, state: dict, *, note: str = "") -> dict:
    """state: {'intent':..,'stage':..,'goal':..,'next':..,'blockers':[..],
              'confirmed_decisions':[..],'constraints':[..]}"""
    fields = [f for f in FIELDS if str(state.get(f) or "").strip()]
    missing = [f for f in FIELDS if f not in fields]
    lines = ["# 压缩后存活集（ctxiso）", "",
             f"生成：{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}"]
    if note:
        lines.append(f"说明：{note}")
    lines.append("")
    for f in fields:
        v = state[f]
        if isinstance(v, (list, tuple)):
            lines.append(f"## {f}")
            lines.extend("- " + str(x) for x in v)
        else:
            lines.append(f"## {f}")
            lines.append(str(v))
        lines.append("")
    if missing:
        lines.append("> 本次没填的存活字段：" + "、".join(missing)
                     + "。压缩后这几项会是空的，别用别的东西补。")
    paths.survivor_path(product).write_text("\n".join(lines) + "\n", encoding="utf-8")

    # 掉出去的：只记指针，不复制内容
    con = store.connect(product)
    try:
        total = con.execute("SELECT COUNT(*) c FROM ledger").fetchone()["c"]
        kinds = {r["kind"]: r["c"] for r in con.execute(
            "SELECT kind, COUNT(*) c FROM ledger GROUP BY kind ORDER BY c DESC")}
        doc_total = con.execute("SELECT COUNT(*) c, COALESCE(SUM(size),0) s FROM doc").fetchone()
    finally:
        con.close()
    dropped = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "dropped": [
            {"what": "账本历史事件", "count": total, "by_kind": kinds,
             "how": "ctxiso query --kind <kind> --limit 50",
             "note": "索引在 state/index.sqlite，正文仍在 .hub/ledger.jsonl，未删"},
            {"what": "长期资料正文", "count": doc_total["c"], "bytes": doc_total["s"],
             "how": "ctxiso archive list --kind <kind> 然后 ctxiso read --intent ..",
             "note": "文件一个没动，只是这一轮没读"},
        ],
        "survivor_fields": fields,
    }
    paths.dropped_path(product).write_text(
        json.dumps(dropped, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "survivor_fields": fields, "missing": missing,
            "survivor_path": str(paths.survivor_path(product)),
            "dropped_path": str(paths.dropped_path(product)),
            "dropped_counts": {d["what"]: d["count"] for d in dropped["dropped"]}}


def load_survivor(product: Path) -> dict:
    p = paths.survivor_path(product)
    if not p.is_file():
        return {}
    text = p.read_text(encoding="utf-8")
    out, cur = {}, None
    for line in text.splitlines():
        if line.startswith("## "):
            cur = line[3:].strip()
            out[cur] = []
        elif cur and line.strip():
            out[cur].append(line.strip())
    return out
