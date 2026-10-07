"""ctxiso 命令行。全部子命令都只读产品目录，只有 state/ 是自己写的。

  ctxiso index   --product P              增量索引账本 + 长期资料元数据
  ctxiso pack    --product P --intent ... 生成有预算的当前任务包
  ctxiso archive list|find --product P    只看索引，不给正文
  ctxiso read    --product P --target ... 带意图取正文（留收据）
  ctxiso compare --product P --base .. --head ..   版本差异摘要
  ctxiso query   --product P --kind ..    查历史事件（只出摘要行）
  ctxiso compact --product P --state JSON 生成压缩存活集 + 掉出指针
  ctxiso observe snapshot|check|recorders  自动记录有没有被关掉
  ctxiso guard   snapshot|check           中枢原有文件有没有被动过
  ctxiso status  --product P              索引与包的一次性体检
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from . import archive, compact, guard, observe, pack, paths, store
except ImportError:
    # 直接跑 `python ctxiso/cli.py ...` 时没有包上下文，相对导入会 ImportError。
    # 而这恰恰是提示词里写着、Agent 最自然会试的那条命令——两种姿势都得能用。
    import importlib
    import os
    _pkg = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _pkg not in sys.path:
        sys.path.insert(0, _pkg)
    archive = importlib.import_module("ctxiso.archive")
    compact = importlib.import_module("ctxiso.compact")
    guard = importlib.import_module("ctxiso.guard")
    observe = importlib.import_module("ctxiso.observe")
    pack = importlib.import_module("ctxiso.pack")
    paths = importlib.import_module("ctxiso.paths")
    store = importlib.import_module("ctxiso.store")

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


def _out(obj, as_json=True):
    if as_json:
        print(json.dumps(obj, ensure_ascii=False, indent=2))
    else:
        print(obj)


def cmd_index(a):
    p = paths.product_root(a.product)
    led = store.refresh_ledger(p, force=a.force)
    doc = store.refresh_docs(p)
    st = store.stats(p)
    # 产品还没建账（没有 .hub/ledger.jsonl）是正常状态，不是失败——
    # 长期项目刚起步就是这样。文档索引成功就该算成功。
    no_ledger = not led.get("ok") and led.get("why") == "没有 ledger.jsonl"
    broken = bool(led.get("ok") is False and not no_ledger)
    ok = not st["duplicated"] and doc.get("ok") and not broken
    res = {"ok": ok,
           "ledger": dict(led, status="该产品还没有 .hub/ledger.jsonl，本轮只索引文档"
                           if no_ledger else None) if no_ledger else led,
           "docs": doc, "stats": st}
    if st["duplicated"]:
        res["why"] = (f"索引里有 {st['duplicated']} 条重复行（同一行被索引了不止一次）。"
                      f"跑一次 `ctxiso index --force --product {p}` 重建。")
    elif broken:
        res["why"] = "账本存在但读不动，先修账本或看 stderr。"
    _out(res)
    return 0 if ok else 3


def cmd_pack(a):
    p = paths.product_root(a.product)
    res = pack.build(p, intent=a.intent or "", stage=a.stage or "", budget=a.budget or 0)
    if a.out:
        Path(a.out).write_text(res["text"], encoding="utf-8")
        res["written"] = a.out
        res.pop("text", None)
    if not a.json:
        print(res.get("text", ""), end="")
        for o in res.get("omitted", []):
            print("（未展开）" + o)
        return
    _out(res)


def cmd_archive(a):
    p = paths.product_root(a.product)
    if a.archive_cmd == "list":
        _out(archive.list_docs(p, kind=a.kind, limit=a.limit))
    else:
        _out({"query": a.query, "hits": archive.find(p, a.query, limit=a.limit),
              "note": "命中只是位置。要正文用 ctxiso read --intent ..."})


def cmd_read(a):
    p = paths.product_root(a.product)
    try:
        res = archive.read(p, target=a.target, intent=a.intent or "", scope=a.scope or "",
                           reason=a.reason or "", chunk=a.chunk, force=a.force)
    except archive.IntentRequired as exc:
        _out({"ok": False, "refused": True, "why": str(exc)}, False)
        return 2
    if a.json:
        r = res["receipt"]
        _out({"ok": True, "receipt": r, "text": res["text"]})
    else:
        print(res["text"])
    return 0


def cmd_compare(a):
    p = paths.product_root(a.product)
    try:
        res = archive.compare(p, base=a.base, head=a.head, intent=a.intent or "")
    except archive.IntentRequired as exc:
        _out({"ok": False, "refused": True, "why": str(exc)}, False)
        return 2
    _out(res)


def cmd_query(a):
    p = paths.product_root(a.product)
    con = store.connect(p)
    try:
        rows = store.events(con, kind=a.kind, ident=a.ident, phase=a.phase, limit=a.limit)
        _out({"query": {"kind": a.kind, "ident": a.ident, "phase": a.phase},
              "count": len(rows),
              "note": "只出摘要行，不出收据正文。",
              "rows": [dict(r) for r in rows]})
    finally:
        con.close()


def cmd_compact(a):
    p = paths.product_root(a.product)
    if a.contract_only:
        _out(compact.contract(p))
        return
    if a.show:
        _out(compact.load_survivor(p))
        return
    if not a.state:
        _out({"ok": False, "why": "要给 --state '{...}'，或用 --contract-only / --show"},
             False)
        return 2
    try:
        st = json.loads(a.state)
    except ValueError as exc:
        _out({"ok": False, "why": f"--state 不是合法 JSON：{exc}"}, False)
        return 2
    _out(compact.build(p, st, note=a.note or ""))


def cmd_observe(a):
    p = paths.product_root(a.product)
    if a.observe_cmd == "snapshot":
        _out(observe.snapshot(p))
    elif a.observe_cmd == "check":
        r = observe.check(p)
        _out(r)
        return 0 if r.get("ok") else 3
    else:
        _out(observe.recorder_report(p))


def cmd_guard(a):
    p = paths.product_root(a.product)
    if a.guard_cmd == "snapshot":
        _out(guard.snapshot(p))
        return
    r = guard.check(p)
    _out(r)
    if not r.get("ok"):
        return 3


def cmd_status(a):
    p = paths.product_root(a.product)
    con = store.connect(p)
    try:
        body = {
            "ok": True,
            "product": str(p),
            "state_dir": str(paths.state_dir(p)),
            "ledger_index": store.stats(p),
            "doc_kinds": store.doc_kinds(con),
            "read_receipts": len(archive.read_history(p)),
            "survivor_present": paths.survivor_path(p).is_file(),
            "policy": "本侧车只读产品目录；保存不等于读取。",
        }
    finally:
        con.close()
    _out(body)


def build_parser():
    ap = argparse.ArgumentParser(prog="ctxiso", description="中枢上下文隔离侧车（只读产品）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def P(sp):
        # --product 放在子命令前后都行；在 main 里统一校验。
        sp.add_argument("--product", default="")
        return sp

    def Pleaf(sp):
        # SUPPRESS 很关键：argparse 的子解析器会用默认值覆盖父层已解析的值。
        # 不加的话 `guard --product X snapshot` 会被 leaf 的默认 "" 冲掉。
        sp.add_argument("--product", default=argparse.SUPPRESS)
        return sp

    p = P(sub.add_parser("index", help="增量索引账本与资料元数据"))
    p.add_argument("--force", action="store_true")
    p.set_defaults(fn=cmd_index)

    p = P(sub.add_parser("pack", help="生成有预算的当前任务包"))
    p.add_argument("--intent", default="")
    p.add_argument("--stage", default="")
    p.add_argument("--budget", type=int, default=0)
    p.add_argument("--out", default="")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_pack)

    p = P(sub.add_parser("archive", help="长期资料索引（不给正文）"))
    asub = p.add_subparsers(dest="archive_cmd", required=True)
    q = Pleaf(asub.add_parser("list")); q.add_argument("--kind"); q.add_argument("--limit", type=int, default=50)
    f = Pleaf(asub.add_parser("find")); f.add_argument("query"); f.add_argument("--limit", type=int, default=20)
    p.set_defaults(fn=cmd_archive)

    p = P(sub.add_parser("read", help="带意图读取正文"))
    p.add_argument("--target", required=True)
    p.add_argument("--intent", default="")
    p.add_argument("--scope", default="")
    p.add_argument("--reason", default="")
    p.add_argument("--chunk", type=int, default=0)
    p.add_argument("--force", action="store_true")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_read)

    p = P(sub.add_parser("compare", help="两版资料差异摘要"))
    p.add_argument("--base", required=True)
    p.add_argument("--head", required=True)
    p.add_argument("--intent", default="")
    p.set_defaults(fn=cmd_compare)

    p = P(sub.add_parser("query", help="查历史事件摘要"))
    p.add_argument("--kind"); p.add_argument("--ident"); p.add_argument("--phase")
    p.add_argument("--limit", type=int, default=50)
    p.set_defaults(fn=cmd_query)

    p = P(sub.add_parser("compact", help="压缩存活集"))
    p.add_argument("--state", default="", help="JSON: intent/stage/goal/next/blockers/...")
    p.add_argument("--note", default="")
    p.add_argument("--show", action="store_true")
    p.add_argument("--contract-only", action="store_true")
    p.set_defaults(fn=cmd_compact)

    p = P(sub.add_parser("observe", help="自动记录观察"))
    osub = p.add_subparsers(dest="observe_cmd", required=True)
    Pleaf(osub.add_parser("snapshot")); Pleaf(osub.add_parser("check")); Pleaf(osub.add_parser("recorders"))
    p.set_defaults(fn=cmd_observe)

    p = P(sub.add_parser("guard", help="中枢原有文件未被改动"))
    gsub = p.add_subparsers(dest="guard_cmd", required=True)
    Pleaf(gsub.add_parser("snapshot")); Pleaf(gsub.add_parser("check"))
    p.set_defaults(fn=cmd_guard)

    p = P(sub.add_parser("status", help="侧车体检"))
    p.set_defaults(fn=cmd_status)
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    # argparse 把叶子子命令的 --product 写在同一个 dest 上，
    # 所以 `guard snapshot --product X` 和 `guard --product X snapshot` 都能取到。
    if not getattr(args, "product", ""):
        print("缺 --product <产品根>", file=sys.stderr)
        return 2
    try:
        rc = args.fn(args)
    except SystemExit:
        raise
    except FileNotFoundError as exc:
        print(f"找不到：{exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"文件系统忙，本次未完成（可能有杀软/索引器临时锁）：{exc}", file=sys.stderr)
        return 2
    return rc or 0


if __name__ == "__main__":
    sys.exit(main())
