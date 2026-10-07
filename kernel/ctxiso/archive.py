"""按需读取：知道文件存在 ≠ 读正文。

读正文必须带意图，且每次读都留收据。没有意图就没有正文。
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from . import paths, store


class IntentRequired(Exception):
    pass


def _receipt(product: Path, row: dict) -> None:
    p = paths.receipt_path(product)
    with p.open("a", encoding="utf-8") as fh:      # 写在自己的 state/ 下
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_history(product: Path, name: str | None = None) -> list[dict]:
    """读读取收据流水。name 保留只为兼容旧调用；现在一律返回全部。"""
    p = paths.receipt_path(product)
    if not p.is_file():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


# ---------------------------------------------------------------- 索引视图
def list_docs(product: Path, *, kind=None, limit=50) -> dict:
    """只列元数据。调用方永远拿不到正文。"""
    con = store.connect(product)
    try:
        rows = store.docs(con, kind=kind, limit=limit)
        kinds = store.doc_kinds(con)
        return {
            "kinds": kinds,
            "total_bytes": sum(r["size"] for r in rows),
            "rows": [dict(r) for r in rows],
            "note": "以上只是索引（路径/类型/大小/行数/摘要/哈希）。正文要用 ctxiso read 显式取。",
        }
    finally:
        con.close()


def find(product: Path, query: str, *, limit=20) -> list[dict]:
    """按文件名/用途找资料。返回的是"去哪读"，不是"读到了什么"。"""
    q = query.casefold()
    con = store.connect(product)
    try:
        hits = []
        for r in con.execute("SELECT * FROM doc").fetchall():
            blob = (r["path"] + " " + (r["one_line"] or "") + " " + r["kind"]).casefold()
            if q in blob:
                hits.append(dict(r))
        hits.sort(key=lambda d: (q not in d["path"].casefold(), -d["size"]))
        return hits[:limit]
    finally:
        con.close()


# ---------------------------------------------------------------- 显式读取
def read(product: Path, *, target: str, intent: str, scope: str = "",
         reason: str = "", chunk: int = 0, force: bool = False) -> dict:
    """带意图读一份资料。scope 支持 'L10:40' 行段或 'N' 字节偏移。"""
    if not intent.strip():
        raise IntentRequired("没有意图就不给正文。先说清为什么现在需要它。")
    cfg = paths.load_config()
    cap = int(cfg["hard_read_cap_bytes"])
    # 目标必须在产品内，且必须在索引里（避免顺手读到不该读的东西）
    p = (product / target).resolve()
    try:
        p.relative_to(product)
    except ValueError:
        raise IntentRequired("目标在产品目录之外，拒绝读。")
    if not p.is_file():
        raise IntentRequired(f"没有这个文件：{target}")
    size = p.stat().st_size
    chunk_size = chunk or int(cfg["read_chunk_bytes"])
    truncated = False
    reason = ""
    if size > cap and not force:
        chunk_size = min(chunk_size, cap)
        truncated = True
        reason = f"文件 {size} B 超过硬顶 {cap} B"
    mode = "rb"
    with p.open(mode) as fh:                          # 只读
        raw = fh.read(chunk_size)
    # 只按硬顶判断是不够的：文件比硬顶小、但比一次分块大时，也会被截一刀，
    # 而收据却说 truncated=false —— 收据撒谎比读少了更糟。
    if len(raw) < size:
        if not truncated:
            truncated = True
            reason = f"一次只取 {len(raw)} B / 共 {size} B（分块 {chunk_size} B）"
    text = raw.decode("utf-8", "replace")
    line_from, line_to = None, None
    if scope.startswith("L"):
        try:
            seg = scope[1:].replace("-", ":").split(":")
            line_from = int(seg[0])
            line_to = int(seg[1]) if len(seg) > 1 and seg[1] else None
        except ValueError:
            raise IntentRequired("scope 写法是 L10:40 或 L10")
        all_lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        end = line_to if line_to else line_from
        text = "\n".join(all_lines[line_from - 1:end])
        truncated = truncated or (line_to is not None and line_to < len(all_lines))
    receipt = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "target": target, "intent": intent, "scope": scope, "reason": reason,
        "bytes_read": len(text.encode("utf-8")), "file_bytes": size,
        "truncated": truncated, "sha8": None,
    }
    import hashlib
    # 没有 hashlib.sha8（只有 sha1/sha256/…/sha512）。用 sha256 截前 8 位。
    receipt["sha8"] = hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]
    _receipt(product, receipt)
    return {"receipt": receipt, "text": text}


def compare(product: Path, *, base: str, head: str, intent: str,
            unit: str = "line") -> dict:
    """版本对比：读两份资料只回差异摘要，不回全文。"""
    if not intent.strip():
        raise IntentRequired("版本对比同样要意图：这次要比什么、为什么比。")
    import difflib
    a = (product / base).read_text(encoding="utf-8", errors="replace").splitlines()
    b = (product / head).read_text(encoding="utf-8", errors="replace").splitlines()
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    added = removed = 0
    hunks = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        added += j2 - j1
        removed += i2 - i1
        if len(hunks) < 20:
            hunks.append({"op": tag, "base": f"L{i1+1}-{i2}", "head": f"L{j1+1}-{j2}",
                          "sample": (b[j1] if j1 < j2 and tag != "delete" else a[i1])[:120]})
    _receipt(product, {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        "target": f"{base} vs {head}", "intent": intent,
                        "scope": "diff", "reason": "", "bytes_read": 0,
                        "file_bytes": len(a) + len(b), "truncated": False, "sha8": None})
    return {"base": base, "head": head, "base_lines": len(a), "head_lines": len(b),
            "added": added, "removed": removed, "similarity": round(sm.ratio(), 4),
            "hunks": hunks, "hunks_truncated": len(hunks) >= 20}
