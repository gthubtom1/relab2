# -*- coding: utf-8 -*-
"""磁盘、哈希、锁、登记表。不是第二套命令行。"""
import hashlib
import json
import os
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
HUB_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = HUB_ROOT / "templates"


def _default_registry():
    """源仓出厂空表不许被产品 init 写脏。开发目录默认写到本机用户目录。"""
    override = os.environ.get("HUB_REGISTRY")
    if override:
        return Path(override)
    agents = HUB_ROOT / "AGENTS.md"
    try:
        text = agents.read_text(encoding="utf-8")
    except OSError:
        text = ""
    if "<hub>" in text:
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        root = Path(base) / "hubcore" if base else Path.home() / ".hubcore"
        return root / "registry.json"
    return HUB_ROOT / "registry.json"


REGISTRY = _default_registry()
KIND_TO_KEY = {
    "anchor": "anchors", "patch": "patches", "access": "access",
    "function-map": "function_map", "test": "tests",
    "license": "license", "ui": "ui", "build": "build",
    "spec": "spec", "arch": "arch", "module": "modules",
    "dossier": "dossier", "checklist": "checklists",
    "follow": "follow", "cover": "cover",
}
RECORD_KINDS = list(KIND_TO_KEY.keys()) + ["replay-order"]
# 按主人那句话的形态：有源码原创 → 接手源码 → 无源码二开最后，避免默认抄第一项。
PRODUCT_TYPES = ["desktop-product", "web-service", "cli-tool", "source-takeover", "protocol-automation", "exe-rebuild"]
MANIFEST_LABELS = {
    "spec": "需求", "arch": "架构决定", "modules": "模块", "anchors": "锚点",
    "patches": "补丁", "access": "访问证据", "function_map": "功能授权地图",
    "tests": "测试", "license": "授权", "ui": "UI映射", "build": "打包",
    "dossier": "首次档案", "replay_order": "重放顺序", "checklists": "施工核对清单",
    "follow": "跟上判断", "cover": "客户路径",
}
MANIFEST_KEYS = tuple(MANIFEST_LABELS)
CONTRACT_SCHEMA = 3
CANDIDATE_ROLES = ("upstream", "working", "access", "core", "ui", "regressed", "licensed", "release")
PHYSICAL_RECEIPT_VERSION = 2
PHYSICAL_RECEIPT_EVENT = "physical_probe"
PHYSICAL_CHECK_KINDS = frozenset({
    "process", "business", "ui", "install", "update", "rollback", "handoff",
})
PHYSICAL_RECEIPT_REQUIRED_FIELDS = (
    "receipt_version", "check_id", "probe_kind", "product_root", "fp", "phase_id",
    "n", "epoch", "cand_sha", "candidate_paths", "result", "stage", "observed",
    "spec_sha", "command_sha", "probe_nonce", "sandbox_id", "nonce", "generated_by",
)
def die(msg, code=1):
    print(msg)
    sys.exit(code)
def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
def _empty_manifest():
    return {key: [] for key in MANIFEST_KEYS}
def _validate_manifest(data):
    for key in MANIFEST_KEYS:
        if key in data and not isinstance(data[key], list):
            die(f"manifest.{key} 类型不对：应为数组，实际 {type(data[key]).__name__}。", 2)
    return data
def read_json(path, default=None, soft=False, expect=dict):
    p = Path(path)
    if not p.exists():
        return default
    try:
        data = json.loads(p.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, UnicodeDecodeError, OSError) as e:
        if soft:
            print(f"  ⚠ 登记表读不动（{p} 坏了：{e}）——本次按空表处理，身份检查降级。")
            return default
        die(f"文件读不动/不是合法 JSON：{p}\n  {e}\n  （被手改坏了？修正它，或删掉让 state 重建）", 2)
    if expect is not None and not isinstance(data, expect):
        got = "null" if data is None else type(data).__name__
        if soft:
            print(f"  ⚠ 登记表类型不对（{p} 顶层应是对象、实际是 {got}）——本次按空表处理，身份检查降级。")
            return default
        die(f"文件类型不对：{p}\n  顶层应是 JSON 对象，实际是 {got}。"
            f"\n  （被手改坏了？修正它，或删掉让 state 重建）", 2)
    return data
def read_text_utf8(path, what="文件"):
    p = Path(path)
    try:
        return p.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        die(f"找不到{what}：{p}", 2)
    except UnicodeDecodeError:
        die(f"{what}不是 UTF-8：{p}\n  用记事本请另存为 UTF-8。", 2)
    except OSError as e:
        die(f"读不了{what}：{p}\n  {e}", 2)
def write_json(path, data):
    path = Path(path)
    tmp = path.with_suffix(path.suffix + f".tmp{os.getpid()}")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for i in range(100):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if i == 99:
                try:
                    tmp.unlink()
                except OSError:
                    pass
                raise
            time.sleep(0.03)
def read_ledger(hub):
    f = hub / "ledger.jsonl"
    if not f.exists():
        return []
    out = []
    try:
        text = f.read_text(encoding="utf-8-sig")
    except (UnicodeDecodeError, OSError) as e:
        die(f"账本读不动：{f}（编码损坏 / 被占用 / 被改成目录？）\n  {e}\n  修正或删掉它再来。", 2)
    for i, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            die(f"账本坏了：{f} 第 {i} 行不是合法 JSON（并发/断电/手改？）。修正或删掉那一行再来。", 2)
        if not isinstance(obj, dict):
            die(f"账本坏了：{f} 第 {i} 行不是对象（{type(obj).__name__}）。修正那一行再来。", 2)
        out.append(obj)
    seq_path = hub / "ledger.seq"
    if seq_path.is_file() and out:
        try:
            seq = int(seq_path.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            die(f"账本序号文件坏了：{seq_path}。修正或删掉再来。", 2)
        max_n = max(_seq(e) for e in out)
        if max_n < seq:
            die("账本少了记录（有人删行？）。不能用删掉的失败去复活旧通过。", 3)
    return out
def _ledger_has_events(hub):
    f = hub / "ledger.jsonl"
    if not f.exists():
        return False
    try:
        return any(line.strip() for line in f.read_text(encoding="utf-8-sig").splitlines())
    except (OSError, UnicodeDecodeError):
        return True
def _lock_is_stale(lock, stale):
    try:
        return time.time() - lock.stat().st_mtime > stale
    except OSError:
        return False
@contextmanager
def _file_lock(target, timeout=10.0, stale=20.0):
    lock = Path(str(target) + ".lock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.time() + timeout
    while True:
        try:
            fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            try:
                os.write(fd, f"{os.getpid()} {now_iso()}".encode("utf-8"))
            finally:
                os.close(fd)
            break
        except FileExistsError:
            stolen = False
            if _lock_is_stale(lock, stale):
                steal = Path(str(lock) + f".stale{os.getpid()}")
                try:
                    os.replace(str(lock), str(steal))
                    try:
                        os.unlink(str(steal))
                    except OSError:
                        pass
                    stolen = True
                except OSError:
                    stolen = False
            if stolen:
                continue
            if time.time() > deadline:
                die(f"拿不到写锁（{lock} 被占用超过 {timeout}s）。"
                    f"若确认没有别的 state 进程在写，删掉这个 .lock 再重试。", 2)
            time.sleep(0.02)
    try:
        yield
    finally:
        try:
            lock.unlink()
        except FileNotFoundError:
            pass
def _seq(event):
    n = event.get("n", 0)
    if isinstance(n, bool):
        return 0
    if isinstance(n, int):
        return n
    try:
        return int(n)
    except (TypeError, ValueError):
        return 0
def append_ledger(hub, event):
    ledger = hub / "ledger.jsonl"
    with _file_lock(ledger):
        existing = read_ledger(hub)
        for e in existing:
            n = e.get("n", 0)
            if isinstance(n, bool) or not isinstance(n, int):
                die("账本序号 n 不是整数，不能再往里写。先修好 .hub/ledger.jsonl。", 2)
        nxt = max((_seq(e) for e in existing), default=0) + 1
        full = {"n": nxt, "ts": now_iso(), **event}
        line = (json.dumps(full, ensure_ascii=False) + "\n").encode("utf-8")
        fd = os.open(str(ledger), os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_BINARY", 0), 0o644)
        try:
            os.write(fd, line)
        finally:
            os.close(fd)
        (hub / "ledger.seq").write_text(str(nxt), encoding="utf-8")
    return full
def _linklike(path):
    return path.is_symlink() or bool(getattr(path, "is_junction", lambda: False)())
def _inside_no_links(product, rel):
    product = Path(product).resolve()
    p = Path(rel)
    p = p if p.is_absolute() else (product / rel)
    lexical = Path(os.path.abspath(p))
    try:
        relative = lexical.relative_to(product)
    except ValueError:
        raise ValueError(f"路径落在产品根之外：{lexical}") from None
    current = product
    for part in relative.parts:
        current /= part
        if current.exists() and _linklike(current):
            raise ValueError(f"路径含符号链接/junction：{current}")
    rp = lexical.resolve()
    try:
        rp.relative_to(product)
    except ValueError:
        raise ValueError(f"解析后路径落在产品根之外：{rp}") from None
    return rp
def _in_product_temp(product, path):
    try:
        rel = Path(path).resolve().relative_to(Path(product).resolve())
    except ValueError:
        return False
    return bool(rel.parts) and rel.parts[0].casefold() == "temp"
def _resolve_inside(product, rel, what):
    try:
        return _inside_no_links(product, rel)
    except ValueError as e:
        die(f"拒绝：{what}（{e}）。", 3)
def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()
def _candidate_manifest_sha(files):
    payload = json.dumps(files, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
def _scan_candidate_sources(product, raw_paths):
    product = Path(product).resolve()
    found = {}
    specs = []
    for raw in raw_paths:
        p = _inside_no_links(product, raw)
        if not p.exists():
            raise FileNotFoundError(f"候选文件/目录不存在：{p}")
        rel_source = p.relative_to(product).as_posix()
        if _in_product_temp(product, p):
            raise ValueError("产品根 TEMP/ 是临时夹，不能登记成候选")
        if p.is_dir():
            if p == product:
                raise ValueError("不能把整个产品根登记为候选（会把 .hub 状态和临时文件一起哈希）")
            specs.append({"path": rel_source, "kind": "dir"})
            targets = []
            for root, dirs, names in os.walk(p, followlinks=False):
                rootp = Path(root)
                safe_dirs = []
                for name in sorted(dirs):
                    dp = rootp / name
                    if _in_product_temp(product, dp):
                        continue
                    if _linklike(dp):
                        raise ValueError(f"候选目录内含符号链接目录：{dp}")
                    safe_dirs.append(name)
                dirs[:] = safe_dirs
                for name in sorted(names):
                    if name == ".env" or name.startswith(".env."):
                        continue
                    fp = rootp / name
                    if _in_product_temp(product, fp):
                        continue
                    targets.append(fp)
        else:
            specs.append({"path": rel_source, "kind": "file"})
            targets = [p]
        for f in targets:
            if f.name == ".env" or f.name.startswith(".env."):
                continue
            if _linklike(f):
                raise ValueError(f"候选清单内含符号链接文件：{f}")
            if not f.is_file():
                continue
            rel = f.resolve().relative_to(product).as_posix()
            found[rel] = {"path": rel, "sha256": sha256_file(f), "size": f.stat().st_size}
    files = [found[k] for k in sorted(found)]
    if not files:
        raise ValueError("候选文件清单为空")
    specs = [dict(x) for x in {x["path"]: x for x in specs}.values()]
    specs.sort(key=lambda x: x["path"])
    return files, specs
def _candidate_file_entries(product, raw_paths):
    try:
        return _scan_candidate_sources(product, raw_paths)
    except FileNotFoundError as e:
        die(str(e), 2)
    except (ValueError, OSError) as e:
        die(f"拒绝候选文件集：{e}（不跟随软链、不允许越出产品根）。", 3)
def _candidate_label(event):
    files = event.get("files")
    if isinstance(files, list):
        return f"{len(files)} 个文件"
    return str(event.get("path", ""))
def _candidate_content_shas(event):
    files = event.get("files")
    return {x.get("sha256") for x in files} if isinstance(files, list) else {event.get("sha256")}
def hub_of(product):
    return Path(product).resolve() / ".hub"
def _load_registry_for_write():
    """缺文件当空表。坏了或类型不对就停，禁止按空表盖写把别人的登记抹掉。"""
    if not REGISTRY.exists():
        return {"products": []}
    data = read_json(REGISTRY, default=None, soft=False, expect=dict)
    if not isinstance(data.get("products"), list):
        die("项目登记表 products 不是数组，不能按空表盖写（会丢掉已登记的产品）。"
            "先修好 registry.json，或删掉这个坏文件后再 init/rebind。", 3)
    return data
def _registry_upsert(product_id, path, ptype, product_uuid=None):
    REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    with _file_lock(REGISTRY):  # 读-改-写整体加锁，防并发 init 互相覆盖丢产品
        reg = _load_registry_for_write()
        reg.setdefault("products", [])
        reg["products"] = [r for r in reg["products"] if r.get("path") == path or Path(r.get("path", "")).exists()]
        for row in reg["products"]:
            if row.get("path") == path:
                row.update({"product_id": product_id, "type": ptype})
                if product_uuid:
                    row["product_uuid"] = product_uuid
                break
        else:
            reg["products"].append({"product_id": product_id, "path": path, "type": ptype, "product_uuid": product_uuid, "created": now_iso()})
        write_json(REGISTRY, reg)

CANDIDATE_BOUND_ARTIFACTS = {
    "access", "function_map", "tests", "license", "ui", "build", "dossier",
    "follow", "cover",
}
SKELETON_FIELDS = ("ts", "phase_id", "fp", "cand_sha", "epoch")
PRODUCT_EVIDENCE = frozenset({"product", "human"})
ARTIFACT_REQUIRED_FIELDS = {
    "anchors": ("how",),
    "access": ("method", "outcome", "evidence", "evidence_level",
               "entry_gate", "action_gate", "direct_launch", "revert"),
    "function_map": ("functions", "authorization_boundaries"),
    "tests": ("outcome", "evidence", "evidence_level"),
    "license": ("topology", "outcome", "updater_treatment", "evidence_level"),
    "build": ("artifact", "candidate_sha", "install_receipt"),
    "spec": ("acceptance",),
    "arch": ("decision",),
    "modules": ("name", "purpose"),
    "ui": ("outcome", "mapping"),
    "dossier": ("upstream_version", "transport", "auth_chain", "patch_sites",
                "own_page", "updater_kill", "pack_recipe", "entry_gate",
                "action_gate", "replay_steps", "reuse", "do_not_reuse",
                "data_roots", "ours_changed", "upstream_changed", "still_portable"),
    "follow": ("ours_changed", "upstream_changed", "still_portable"),
    "cover": ("outcome", "evidence"),
    "checklists": ("items",),
}
