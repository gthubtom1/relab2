"""路径与配置。本包唯一的写盘位置是 DEV_ROOT/state/。"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

PKG = Path(__file__).resolve().parent
DEV_ROOT = PKG.parent                    # 本仓里是 kernel/（不是旧的 work/context-isolation/）
STATE_DIR = DEV_ROOT / "state"
CONFIG_PATH = PKG / "config.json"

_DEFAULT = {
    "pack_budget_bytes": 6000,
    "pack_max_gap_items": 12,
    "pack_max_index_rows": 10,
    "pack_max_one_line": 110,
    "hard_read_cap_bytes": 262144,
    "read_chunk_bytes": 65536,
    "ledger_summary_max": 160,
    "one_line_scan_bytes": 4096,
    "archive_scan": {},
    "archive_scan_dirs": {},
    "archive_ignore_globs": ["**/.git/**", "**/__pycache__/**", "**/TEMP/**"],
    "survivor_fields": ["intent", "stage", "goal", "next", "blockers",
                        "confirmed_decisions", "constraints"],
}


def load_config() -> dict:
    cfg = dict(_DEFAULT)
    try:
        cfg.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        pass
    cfg.pop("_comment", None)
    return cfg


def product_root(raw: str) -> Path:
    p = Path(raw).expanduser().resolve()
    if not p.is_dir():
        raise SystemExit(f"产品目录不存在：{p}")
    return p


def hub_dir(product: Path) -> Path:
    return product / ".hub"


def product_key(product: Path) -> str:
    """产品标识：路径的 sha1 前 12 位，跨机器稳定，不含盘符以外的可变部分。"""
    return hashlib.sha1(str(product).encode("utf-8")).hexdigest()[:12]


def state_dir(product: Path) -> Path:
    d = STATE_DIR / product_key(product)
    d.mkdir(parents=True, exist_ok=True)
    return d


def db_path(product: Path) -> Path:
    return state_dir(product) / "index.sqlite"


def receipt_path(product: Path) -> Path:
    return state_dir(product) / "reads.jsonl"


def survivor_path(product: Path) -> Path:
    return state_dir(product) / "SURVIVOR.md"


def dropped_path(product: Path) -> Path:
    return state_dir(product) / "dropped.json"


def ensure_state_root() -> Path:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    return STATE_DIR


def env_off(product: Path) -> bool:
    """显式关闭开关：设 CTXISO_OFF=1 时 pack 退化为空包，不做任何读取。"""
    return os.environ.get("CTXISO_OFF", "") == "1"
