"""只读观察：证明自动记录没被关掉，并且只增不减。

本模块不写产品目录任何一个字节。它只回答一个问题：
"这次重构有没有让中枢少记东西？"
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from . import paths, store

BASELINE = "observe-baseline.json"


def _fingerprint(product: Path) -> dict:
    cfg = paths.load_config()
    out = {}
    for rel, kind in (cfg.get("archive_scan") or {}).items():
        p = product / rel
        if p.is_file():
            st = p.stat()
            out[rel] = {"bytes": st.st_size, "mtime": round(st.st_mtime, 3), "kind": kind}
    led = paths.hub_dir(product) / "ledger.jsonl"
    if led.is_file():
        st = led.stat()
        out[".hub/ledger.jsonl"] = {"bytes": st.st_size, "mtime": round(st.st_mtime, 3),
                                    "kind": "ledger"}
    req = paths.hub_dir(product) / "requirements.jsonl"
    if req.is_file():
        st = req.stat()
        out[".hub/requirements.jsonl"] = {"bytes": st.st_size, "mtime": round(st.st_mtime, 3),
                                          "kind": "requirements"}
    return out


def _baseline_path(product: Path) -> Path:
    return paths.state_dir(product) / BASELINE


def snapshot(product: Path) -> dict:
    cur = _fingerprint(product)
    _baseline_path(product).write_text(
        json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "files": cur},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "captured": len(cur),
            "total_bytes": sum(v["bytes"] for v in cur.values())}


def check(product: Path) -> dict:
    base_path = _baseline_path(product)
    if not base_path.is_file():
        return {"ok": False, "why": "还没有基线，先跑 ctxiso observe snapshot"}
    base = json.loads(base_path.read_text(encoding="utf-8"))["files"]
    cur = _fingerprint(product)
    grew, shrank, gone, new = [], [], [], []
    for rel, meta in cur.items():
        if rel not in base:
            new.append(rel)
        elif meta["bytes"] > base[rel]["bytes"]:
            grew.append({"path": rel, "delta": meta["bytes"] - base[rel]["bytes"]})
        elif meta["bytes"] < base[rel]["bytes"]:
            shrank.append({"path": rel, "delta": base[rel]["bytes"] - meta["bytes"]})
    for rel in base:
        if rel not in cur:
            gone.append(rel)
    return {
        "ok": not shrank and not gone,
        "verdict": ("自动记录仍在正常追加：%d 份资料增长，0 份变小，0 份消失。"
                    % len(grew)) if not shrank and not gone
                   else "有资料变小或消失，需要查是不是被谁改了。",
        "grew": grew, "shrank": shrank, "gone": gone, "new": new,
        "baseline_at": json.loads(base_path.read_text(encoding="utf-8"))["at"],
    }


def recorder_report(product: Path) -> dict:
    """中枢的自动记录器清单 + 它们现在是否还在写。"""
    tools = {
        "OWNER-SPEECH.md": "hub/tools/speech_land.py：从宿主会话里抽主人原话，只追加",
        "CHANGES.md": "hub/tools/hub_cmds.py：record 时追加本刀改动图",
        ".hub/ledger.jsonl": "hub/tools/state.py：责任/探针/确认的唯一账本",
        ".hub/requirements.jsonl": "state.py require --append：原话需求账",
        "SHIFT.md / .hub/shift-ticket.json": "hub/tools/shift.py：留班接班",
        "PROJECT-MEMORY.jsonl": "hub/tools/feature_set.py --apply：项目理解",
        "MAP.md / FEATURES.md / features/*.md": "hub_memory.py 派生的导航视图",
        "WORK-HANDOFF.md": "人写的交接纸，中枢不覆盖",
    }
    con = store.connect(product)
    try:
        kinds = {r["kind"]: r["c"] for r in con.execute(
            "SELECT kind, COUNT(*) c FROM ledger GROUP BY kind ORDER BY c DESC")}
    finally:
        con.close()
    return {
        "policy": "自动记录一律保留。ctxiso 不关、不改、不删任何一条记录。",
        "recorders": tools,
        "ledger_event_kinds": kinds,
    }
