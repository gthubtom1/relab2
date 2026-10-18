"""索引库：把 26 MB 的 .hub/ledger.jsonl 变成一条可查的元数据索引。

> **本仓当前没有 `.hub/`，索引为空是正常状态。** 下面这组数字是**上一版中枢**的实测值，
> 留在这里是为了说明「为什么索引要增量做」；`ctxiso status --product <仓根>` 现在会报
> `ledger_bytes: 0, indexed_events: 0`，那不是索引坏了。

关键约束（实测依据，见 00-ANALYSIS/02-污染链实测.md）：
  ledger.jsonl = 26,029,540 B / 1,118 条事件，单条 physical_probe 约 23 KB，
  因为事件里内嵌了 observed.json（30+ 个 null 键）、assertions 数组、
  candidate_paths（30 条）和 work_bindings（逐文件 sha）。

所以本模块做三件事：
  1. 增量读：只 seek 到游标读新增字节，刷新成本 O(新增) 而不是 O(26 MB)。
  2. 只留元数据：白名单字段 + 截断摘要。收据正文、observed、assertions、
     candidate_paths、work_bindings 一律不进索引。
  3. 落 SQLite：后续 pack/compact/query 走索引查询，不再碰大文件。
"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from . import paths

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT);
CREATE TABLE IF NOT EXISTS ledger(
    seq     INTEGER PRIMARY KEY,
    off     INTEGER NOT NULL,
    len     INTEGER NOT NULL,
    kind    TEXT NOT NULL,
    ident   TEXT,
    phase   TEXT,
    ts      TEXT,
    result  TEXT,
    summary TEXT
);
CREATE INDEX IF NOT EXISTS ix_ledger_kind  ON ledger(kind);
CREATE INDEX IF NOT EXISTS ix_ledger_ident ON ledger(ident);
CREATE INDEX IF NOT EXISTS ix_ledger_phase ON ledger(phase);
CREATE TABLE IF NOT EXISTS doc(
    path     TEXT PRIMARY KEY,
    kind     TEXT NOT NULL,
    size     INTEGER NOT NULL,
    mtime    REAL NOT NULL,
    lines    INTEGER,
    sha      TEXT,
    one_line TEXT
);
CREATE INDEX IF NOT EXISTS ix_doc_kind ON doc(kind);
"""


def connect(product: Path) -> sqlite3.Connection:
    # WAL + busy_timeout：看门狗心跳和人工操作会同时开库。
    # 原来用默认 rollback journal + 立即失败，并发时表现为
    # 「rc=1、输出为空」——看起来像命令坏了，其实是撞锁。
    con = sqlite3.connect(str(paths.db_path(product)), timeout=30.0)
    con.row_factory = sqlite3.Row
    try:
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA synchronous=NORMAL")
        con.execute("PRAGMA busy_timeout=30000")
    except sqlite3.DatabaseError:
        # WAL 不可用（网络盘/只读夹）不该让整条命令死掉，退回默认模式。
        pass
    con.executescript(SCHEMA)
    return con


def _get(con, key, default=None):
    row = con.execute("SELECT v FROM meta WHERE k=?", (key,)).fetchone()
    return row["v"] if row else default


def _set(con, key, val):
    con.execute("INSERT INTO meta(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v",
                (key, str(val)))


# ---------------------------------------------------------------- 摘要提取
# 只取标量白名单。任何 list/dict 都不进索引——那正是体积与污染的来源。
_SCALAR_WHITELIST = ("ts", "kind", "check_id", "phase_id", "phase", "result",
                     "stage", "verification_mode", "epoch", "stop_point",
                     "role", "id", "from_phase", "hypothesis_key", "product_id",
                     "type", "revision", "n")

# 明确不取：体积大且与"当前任务"无关
_DROP = ("observed", "assertions", "candidate_paths", "work_bindings",
         "evidence", "items", "json", "files", "receipt", "manifest")


def _ident(ev: dict) -> str:
    for k in ("check_id", "id", "stop_point", "role", "from_phase"):
        v = ev.get(k)
        if isinstance(v, str) and v:
            return v[:80]
    items = ev.get("items")
    if isinstance(items, list) and items:
        return "batch:" + ",".join(str(i.get("id", "")) for i in items[:4]
                                   if isinstance(i, dict))[:80]
    return ""


def _summary(ev: dict, limit: int) -> str:
    """人读的一行摘要。绝不序列化 observed/assertions 这类结构。"""
    kind = str(ev.get("kind") or "")
    bits = []
    if kind == "work_define":
        items = ev.get("items") or []
        bits.append("定义 %d 项：%s" % (
            len(items),
            "、".join(str(i.get("id", "")) for i in items[:5] if isinstance(i, dict))))
    elif kind == "physical_probe":
        obs = ev.get("observed")
        if isinstance(obs, dict) and isinstance(obs.get("assertions"), list):
            asserts = obs["assertions"]
            fails = [str(a.get("id", "")) for a in asserts
                     if isinstance(a, dict) and a.get("passed") is False]
            bits.append("%s/%s 断言 %d 过 %d 败" % (
                ev.get("check_id", "?"), ev.get("result", "?"),
                len(asserts), len(fails)))
            if fails:
                bits.append("(" + "、".join(fails[:6]) + ")")
        else:
            # 没带断言明细的那次，不要编一个"失败 0"出来冒充结论
            bits.append("%s/%s（该次未记录断言明细）" % (
                ev.get("check_id", "?"), ev.get("result", "?")))
    elif kind == "confirm":
        bits.append("确认 %s（fp=%s）" % (ev.get("stop_point", "?"), ev.get("fp", "?")))
    elif kind == "attempt":
        bits.append("尝试 %s：%s" % (ev.get("phase_id", "?"), str(ev.get("hypothesis", ""))[:60]))
    elif kind == "reopen":
        bits.append("从 %s 重开：%s" % (ev.get("from_phase", "?"), str(ev.get("reason", ""))[:60]))
    elif kind == "candidate":
        bits.append("候选 %s" % (ev.get("role", "working"),))
    else:
        for k in _SCALAR_WHITELIST:
            v = ev.get(k)
            if isinstance(v, (str, int, float, bool)) and str(v):
                bits.append("%s=%s" % (k, v))
                if len(bits) >= 4:
                    break
    out = "；".join(bits)
    return out[:limit]


# ---------------------------------------------------------------- 增量索引
def refresh_ledger(product: Path, *, force: bool = False) -> dict:
    """增量索引 .hub/ledger.jsonl。返回统计，不返回正文。"""
    cfg = paths.load_config()
    f = paths.hub_dir(product) / "ledger.jsonl"
    con = connect(product)
    try:
        if not f.is_file():
            _set(con, "ledger_missing", "1")
            return {"ok": False, "why": "没有 ledger.jsonl", "events": 0}
        size = f.stat().st_size
        cursor = 0 if force else int(_get(con, "ledger_cursor", 0) or 0)
        seq = int(_get(con, "ledger_seq", 0) or 0)
        if force or cursor > size:
            # force 重建，或账本被换短/重建过。必须同时清行和清序号，
            # 只把游标拨回 0 会让同一批事件在原序号之后再来一遍，数据静默翻倍。
            con.execute("DELETE FROM ledger")
            con.commit()
            _set(con, "ledger_seq", 0)
            cursor = 0
            seq = 0
        added = 0
        skipped = 0
        limit = int(cfg["ledger_summary_max"])
        t0 = time.perf_counter()
        with f.open("rb") as fh:            # 只读；本包永不写这个文件
            fh.seek(cursor)
            buf = b""
            off = cursor
            while True:
                chunk = fh.read(1 << 20)
                if not chunk:
                    break
                buf += chunk
                while True:
                    nl = buf.find(b"\n")
                    if nl < 0:
                        break
                    raw, buf = buf[:nl], buf[nl + 1:]
                    seq += 1
                    line_len = len(raw) + 1
                    off += line_len
                    text = raw.decode("utf-8", "replace").strip()
                    if not text:
                        continue
                    try:
                        ev = json.loads(text)
                    except ValueError:
                        skipped += 1
                        continue
                    if not isinstance(ev, dict):
                        skipped += 1
                        continue
                    con.execute(
                        "INSERT OR REPLACE INTO ledger(seq,off,len,kind,ident,phase,ts,result,summary)"
                        " VALUES(?,?,?,?,?,?,?,?,?)",
                        (seq, off - line_len, line_len,
                         str(ev.get("kind") or "(none)"), _ident(ev),
                         str(ev.get("phase_id") or ev.get("phase") or "") or None,
                         ev.get("ts"), ev.get("result"), _summary(ev, limit)))
                    added += 1
                    if added % 200 == 0:
                        con.commit()
            con.commit()
            _set(con, "ledger_cursor", off)
            _set(con, "ledger_seq", seq)
            _set(con, "ledger_size", size)
            _set(con, "ledger_indexed_at", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
            con.commit()
            if force:
                # SQLite 删行不缩文件。不 VACUUM 的话，索引库体积会一直虚高，
                # 让人以为索引比实际大一倍——这正是被复核挑出来的那条。
                con.isolation_level = None
                con.execute("VACUUM")
                con.isolation_level = ""
        elapsed = (time.perf_counter() - t0) * 1000
        return {"ok": True, "new_events": added, "skipped": skipped,
                "total_events": seq, "ledger_bytes": size,
                "read_bytes": size - cursor, "elapsed_ms": round(elapsed, 1)}
    finally:
        con.close()


def stats(product: Path) -> dict:
    con = connect(product)
    try:
        total = con.execute("SELECT COUNT(*) c FROM ledger").fetchone()["c"]
        # 同一行被索引两次时，off 会重复。distinct 数对不上就是索引坏了，
        # 必须当场报出来，不许"看起来有数据"就放过。
        distinct = con.execute("SELECT COUNT(DISTINCT off) c FROM ledger").fetchone()["c"]
        by_kind = {r["kind"]: r["c"] for r in con.execute(
            "SELECT kind, COUNT(*) c FROM ledger GROUP BY kind ORDER BY c DESC")}
        size = int(_get(con, "ledger_size", 0) or 0)
        db = paths.db_path(product)
        index_bytes = db.stat().st_size if db.is_file() else 0
        return {"indexed_events": total, "distinct_offsets": distinct,
                "duplicated": total - distinct,
                "ledger_bytes": size,
                "index_bytes": index_bytes,
                # 体积比（索引库 / 账本），用百分比。别再报"事件数/字节"那种
                # 长得像百分比其实不是的数——复核时被挑出来过。
                "size_ratio_pct": round(100.0 * index_bytes / size, 4) if size else None,
                "events_per_kb": round(total / (size / 1024.0), 3) if size else None,
                "by_kind": by_kind,
                "indexed_at": _get(con, "ledger_indexed_at")}
    finally:
        con.close()


def events(con, *, kind=None, ident=None, phase=None, limit=50, desc=True):
    sql = "SELECT * FROM ledger WHERE 1=1"
    args = []
    if kind:
        sql += " AND kind=?"; args.append(kind)
    if ident:
        sql += " AND ident=?"; args.append(ident)
    if phase:
        sql += " AND phase=?"; args.append(phase)
    sql += " ORDER BY seq %s LIMIT ?" % ("DESC" if desc else "ASC")
    args.append(limit)
    return con.execute(sql, args).fetchall()


def one(con, ident: str):
    return con.execute("SELECT * FROM ledger WHERE ident=? ORDER BY seq DESC LIMIT 1",
                       (ident,)).fetchone()


# ---------------------------------------------------------------- 文档索引
def _sha_and_lines(fh, size: int) -> tuple[str, int]:
    import hashlib
    h = hashlib.sha256()
    lines = 0
    left = size
    while left > 0:
        b = fh.read(min(1 << 20, left))
        if not b:
            break
        left -= len(b)
        h.update(b)
        lines += b.count(b"\n")
    return h.hexdigest(), lines


def _first_line(fh, cap: int) -> str:
    """取第一句人读的话当用途摘要。JSON 数据行不是用途，跳过。"""
    fh.seek(0)
    buf = fh.read(cap)
    for line in buf.split(b"\n"):
        s = line.decode("utf-8", "replace").strip().lstrip("#").strip()
        if not s or s.startswith("|") or s[0] in "{[":
            continue
        return s
    return "（数据文件，无人读标题）"


def refresh_docs(product: Path) -> dict:
    """索引长期资料的**元数据**。正文一律不进库。"""
    cfg = paths.load_config()
    con = connect(product)
    seen = set()
    count = 0
    try:
        targets = list((cfg.get("archive_scan") or {}).items())
        for d, kind in (cfg.get("archive_scan_dirs") or {}).items():
            base = product / d
            if base.is_dir():
                for p in sorted(base.rglob("*")):
                    if p.is_file():
                        targets.append((p.relative_to(product).as_posix(), kind))
        for rel, kind in targets:
            p = product / rel
            if not p.is_file():
                continue
            seen.add(rel)
            st = p.stat()
            with p.open("rb") as fh:          # 只读
                sha, lines = _sha_and_lines(fh, st.st_size)
                one_line = _first_line(fh, int(cfg["one_line_scan_bytes"]))[
                    : int(cfg["pack_max_one_line"])]
            con.execute(
                "INSERT INTO doc(path,kind,size,mtime,lines,sha,one_line) VALUES(?,?,?,?,?,?,?)"
                " ON CONFLICT(path) DO UPDATE SET kind=excluded.kind,size=excluded.size,"
                " mtime=excluded.mtime,lines=excluded.lines,sha=excluded.sha,one_line=excluded.one_line",
                (rel, kind, st.st_size, st.st_mtime, lines, sha, one_line))
            count += 1
        stale = [r["path"] for r in con.execute("SELECT path FROM doc").fetchall()
                 if r["path"] not in seen]
        for rel in stale:
            con.execute("DELETE FROM doc WHERE path=?", (rel,))
        con.commit()
        return {"ok": True, "indexed": count, "dropped": len(stale)}
    finally:
        con.close()


def docs(con, kind=None, limit=200):
    if kind:
        return con.execute("SELECT * FROM doc WHERE kind=? ORDER BY size DESC LIMIT ?",
                           (kind, limit)).fetchall()
    return con.execute("SELECT * FROM doc ORDER BY kind, size DESC LIMIT ?",
                       (limit,)).fetchall()


def doc_kinds(con) -> dict:
    return {r["kind"]: r["c"] for r in con.execute(
        "SELECT kind, COUNT(*) c FROM doc GROUP BY kind ORDER BY c DESC")}
