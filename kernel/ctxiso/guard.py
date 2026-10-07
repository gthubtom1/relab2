"""不干扰校验：证明本次开发没碰过中枢原有文件。

手段是对"中枢本体"取指纹并存基线，之后任何时候都能回答一句
"旧系统还是原来那份吗"。指纹只读，不写产品目录。
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from . import paths

GUARD_PATHS = [
    # 上一版中枢的清单（hub/、start.bat、.hub/ 那一堆）全删了——
    # 本仓独立之后那些文件根本不存在，守着一份不存在的清单等于空转。
    # 现在守**本仓自己的承重件**：中枢本体的两套规则与运行核、打包器的闸门。
    "02-hubcore/CORE.md", "02-hubcore/AGENTS.md", "02-hubcore/MANIFEST.json",
    "02-hubcore/build_hubcore.py",
    "02-hubcore/tools/state.py", "02-hubcore/tools/hub_cmds.py",
    "02-hubcore/tools/hub_flow.py", "02-hubcore/tools/hub_io.py",
    "02-hubcore/tools/hub_work.py", "02-hubcore/tools/hub_memory.py",
    "02-hubcore/tools/hub_ask.py", "02-hubcore/tools/hub_wording.py",
    "02-hubcore/tools/hub_gates.py", "02-hubcore/tools/hub_assertions.py",
    "02-hubcore/tools/map_show.py", "02-hubcore/tools/map_freeze.py",
    "02-hubcore/tools/shift.py", "02-hubcore/tools/speech_land.py",
    "02-hubcore/tools/feature_set.py",
    "03-bundle/_bundle_lib.py", "03-bundle/install.py", "03-bundle/uninstall.py",
    "03-bundle/pack.py", "03-bundle/verify.py",
]
BASE = "guard-baseline.json"


def _sha(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        while True:
            b = fh.read(1 << 20)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def fingerprint(product: Path) -> dict:
    out = {}
    for rel in GUARD_PATHS:
        p = product / rel
        if p.is_file():
            out[rel] = {"sha256": _sha(p), "bytes": p.stat().st_size}
    return out


def _base_path(product: Path) -> Path:
    return paths.state_dir(product) / BASE


def snapshot(product: Path) -> dict:
    fp = fingerprint(product)
    _base_path(product).write_text(
        json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "files": fp},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "guarded": len(fp),
            "bytes": sum(v["bytes"] for v in fp.values())}


def check(product: Path) -> dict:
    bp = _base_path(product)
    if not bp.is_file():
        return {"ok": False, "why": "还没有基线，先跑 ctxiso guard snapshot"}
    base = json.loads(bp.read_text(encoding="utf-8"))
    cur = fingerprint(product)
    changed, missing, added = [], [], []
    for rel, meta in base["files"].items():
        if rel not in cur:
            missing.append(rel)
        elif cur[rel]["sha256"] != meta["sha256"]:
            changed.append(rel)
    for rel in cur:
        if rel not in base["files"]:
            added.append(rel)
    # 账本是 append-only，自动记录本来就会让它变；单独归类不算"被改"
    append_only = {".hub/ledger.jsonl", ".hub/requirements.jsonl",
                   ".hub/manifest.json", "OWNER-SPEECH.md", "CHANGES.md"}
    hard_changed = [c for c in changed if c not in append_only]
    ok = not missing and not hard_changed
    return {
        "ok": ok,
        "verdict": ("中枢原有 %d 个受控文件全部逐字节未变。" % len(base["files"]))
                   if ok else
                   ("有 %d 个受控文件被改、%d 个消失。" % (len(hard_changed), len(missing))),
        "baseline_at": base["at"],
        "changed": changed, "changed_excluding_append_only": hard_changed,
        "missing": missing, "added": added,
        "note": "OWNER-SPEECH/CHANGES/ledger/manifest/requirements 是自动记录产物，"
                "增长属正常，不计为改动。",
    }
