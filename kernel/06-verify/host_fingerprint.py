"""真家目录只读指纹：给「旧系统一字节未动」出可复现的证据。

    python 06-verify/host_fingerprint.py --out 06-verify/TEMP/fp-before.json
    python 06-verify/host_fingerprint.py --out 06-verify/TEMP/fp-after.json --compare 06-verify/TEMP/fp-before.json

只读：只 stat + 读哈希，一个字节都不写。只认控制台 hosts.py 列出的那几家家目录，
别的目录不碰（不进 %USERPROFILE% 根目录乱扫）。

不 import 打包器，也不 import 控制台服务，只 import 04-console/hosts.py 的识别表。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

CTXISO = Path(__file__).resolve().parent.parent
CONSOLE = CTXISO / "04-console"
sys.path.insert(0, str(CONSOLE))

import hosts as hosts_mod  # noqa: E402

# 扫哪些子目录进指纹：宿主家目录顶层的这些扩展名 / 固定名。
# 不递归进 .git、node_modules、缓存、venv —— 那些本来就在自己变，量了只会淹没真信号。
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv",
             "target", "dist", "build", ".next", ".cache"}
SKIP_SUFFIX = {".pyc", ".pyo", ".log", ".tmp", ".lock", ".sqlite", ".sqlite3", ".db"}


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def scan_tree(root: Path) -> dict:
    """家目录全量清单：相对路径 -> {size, sha256}。目录本身只记存在，不记哈希。"""
    files: dict[str, dict] = {}
    dirs = 0
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root).as_posix()
        if any(part in SKIP_DIRS for part in p.relative_to(root).parts):
            continue
        if p.is_symlink():
            files[rel] = {"type": "symlink", "target": str(p.readlink())}
            continue
        if p.is_dir():
            dirs += 1
            continue
        if p.suffix.lower() in SKIP_SUFFIX:
            continue
        try:
            files[rel] = {"size": p.stat().st_size, "sha256": digest(p)}
        except OSError as exc:
            files[rel] = {"error": type(exc).__name__}
    return {"files": files, "dirs": dirs}


def collect() -> dict:
    hosts_mod.invalidate_cache()
    out: dict = {"skipped_dirs": sorted(SKIP_DIRS), "skipped_suffixes": sorted(SKIP_SUFFIX), "hosts": {}}
    for row in hosts_mod.list_hosts():
        if not row.get("exists") or row.get("fixture"):
            continue
        home = Path(row["home"])
        entry = row["entry"]
        entry_path = home / entry
        out["hosts"][row["id"]] = {
            "name": row["name"],
            "home": str(home),
            "entry": entry,
            "entry_exists": entry_path.is_file(),
            "entry_sha256": digest(entry_path) if entry_path.is_file() else None,
            "tree": scan_tree(home),
        }
    return out


def compare(before: dict, after: dict) -> dict:
    changed: list[dict] = []
    missing: list[str] = []
    added: list[str] = []
    only_before = sorted(set(before["hosts"]) - set(after["hosts"]))
    only_after = sorted(set(after["hosts"]) - set(before["hosts"]))
    for hid in sorted(set(before["hosts"]) & set(after["hosts"])):
        a, b = before["hosts"][hid], after["hosts"][hid]
        if a["entry_sha256"] != b["entry_sha256"]:
            changed.append({"host": hid, "file": a["entry"], "kind": "entry",
                            "before": a["entry_sha256"], "after": b["entry_sha256"]})
        fa, fb = a["tree"]["files"], b["tree"]["files"]
        for rel in sorted(set(fa) - set(fb)):
            missing.append(f"{hid}/{rel}")
        for rel in sorted(set(fb) - set(fa)):
            added.append(f"{hid}/{rel}")
        for rel in sorted(set(fa) & set(fb)):
            if fa[rel] != fb[rel]:
                changed.append({"host": hid, "file": rel, "kind": "file",
                                "before": fa[rel], "after": fb[rel]})
    return {
        "ok": not (changed or missing or added or only_before or only_after),
        "changed": changed, "missing": missing, "added": added,
        "host_gone": only_before, "host_new": only_after,
        "hosts_compared": sorted(set(before["hosts"]) & set(after["hosts"])),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="真家目录只读指纹（装前/装后逐字节对比）")
    ap.add_argument("--out", required=True, help="指纹 JSON 落盘路径")
    ap.add_argument("--compare", default="", help="跟另一份指纹比；给了就打印差异并据此定退出码")
    args = ap.parse_args(argv)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    now = collect()
    out_path.write_text(json.dumps(now, ensure_ascii=False, indent=1), encoding="utf-8")

    total_files = sum(len(h["tree"]["files"]) for h in now["hosts"].values())
    total_bytes = sum(f.get("size", 0) for h in now["hosts"].values() for f in h["tree"]["files"].values())
    print("家目录 %d 个，文件 %d 个，合计 %d 字节" % (len(now["hosts"]), total_files, total_bytes))
    for hid, h in sorted(now["hosts"].items()):
        print("  %-9s 入口 %-22s %s  文件 %d"
              % (hid, h["entry"], (h["entry_sha256"] or "-")[:12], len(h["tree"]["files"])))
    print("指纹已写：%s" % out_path)

    if not args.compare:
        return 0

    before = json.loads(Path(args.compare).read_text(encoding="utf-8"))
    diff = compare(before, now)
    print()
    print("对比 %s -> %s" % (args.compare, out_path))
    print("  比了 %d 个家目录" % len(diff["hosts_compared"]))
    print("  改了 %d 处 / 少了 %d 个 / 多了 %d 个 / 家目录消失 %d / 新出现 %d"
          % (len(diff["changed"]), len(diff["missing"]), len(diff["added"]),
             len(diff["host_gone"]), len(diff["host_new"])))
    for item in diff["changed"][:10]:
        print("    改：%s/%s" % (item["host"], item["file"]))
    for rel in diff["missing"][:10]:
        print("    少：%s" % rel)
    for rel in diff["added"][:10]:
        print("    多：%s" % rel)
    print("判定：", "一字节未动" if diff["ok"] else "有变化")
    return 0 if diff["ok"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
