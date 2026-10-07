"""保险箱：就一件事 —— 把宿主入口文件原样存一份，要退的时候原样换回来。

    %LOCALAPPDATA%\\HubCoreConsole\\safebox\\<宿主 id>\\<入口文件名>.<时间戳>.bak
    %LOCALAPPDATA%\\HubCoreConsole\\safebox\\<宿主 id>\\home.txt        （锁的时候家在哪儿，一行）

- **锁定**：把当前入口文件整份存成一份 .bak。逐字节复制，不算哈希、不改编码、不写索引。
- **比对**：现在这份 vs 最近那份 .bak，逐行说哪儿不一样。
- **恢复**：把那份 .bak 逐字节写回入口文件，**然后把 .bak 用掉**（换回 md）。

一家**永远只有一份 .bak**：再按一次「锁定」就把它覆盖。要再退就先重新锁定。**凭据一概不碰**：本模块只读入口文件这一个文件，
只往保险箱目录里写那一个字节流，不进门目录里别的文件（不碰 skills、不碰会话、不碰 cursor 那些）。

不用装包里的任何东西，也不 import 03-bundle。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _safebox_root() -> Path:
    """保险箱落在 %LOCALAPPDATA%，不落在产品夹里。

    里面存的是宿主入口文件的全字节副本，一次 git add -A / 一次打包发出去就带走了。
    产品夹里不放别人的东西，这是硬规矩。
    """
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    fresh = Path(base) / "HubCoreConsole" / "safebox"
    legacy = HERE / "safebox"
    if legacy.is_dir() and not fresh.exists():
        try:
            fresh.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(legacy), str(fresh))
        except OSError:
            return legacy
    return fresh


SAFEBOX = _safebox_root()

sys.path.insert(0, str(HERE))
import hosts as hosts_mod  # noqa: E402

KEEP = 1          # 每家只留一份：再按一次「锁定」就把它覆盖掉
HOME_NOTE = "home.txt"


# ---------------------------------------------------------------- 小工具

def _host_row(host_id: str) -> dict:
    return hosts_mod.get_host(host_id) or {}


def _entry_of(host_id: str):
    """(家目录, 入口文件名)。"""
    row = _host_row(host_id)
    home = Path(row.get("home") or "")
    entry = str(row.get("entry") or "AGENTS.md")
    return home, entry


def _flatten(entry: str) -> str:
    """入口文件名拍平成一个文件名用（windsurf 的入口在子目录里）。"""
    return entry.replace("\\", "/").replace("/", "__")


def _split(name: str):
    """<入口>.<tag>.bak -> (入口, tag)。认不出来返回 ('', '')。"""
    if not name.endswith(".bak"):
        return "", ""
    body = name[:-4]
    if "." not in body:
        return "", ""
    entry, tag = body.rsplit(".", 1)
    return entry.replace("__", "/"), tag


def _tag() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def atomic_write_bytes(path: Path, data: bytes) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-", suffix=".swap")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, str(path))
    finally:
        if os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass


@contextmanager
def _host_operation_lock(home: Path):
    """和安装/卸载共用同一把跨进程宿主锁。"""
    key = hashlib.sha256(os.path.normcase(str(Path(home).resolve())).encode("utf-8")).hexdigest()[:32]
    path = Path(tempfile.gettempdir()) / ("hubcore-operation-" + key + ".lock")
    fh = open(path, "a+b")
    try:
        if os.name == "nt":
            import msvcrt
            fh.seek(0, os.SEEK_END)
            if fh.tell() == 0:
                fh.write(b"0")
                fh.flush()
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        fh.close()
        raise RuntimeError("这家宿主已有装卸或保险箱操作在进行，请稍后再试。") from exc
    try:
        yield
    finally:
        try:
            if os.name == "nt":
                import msvcrt
                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        finally:
            fh.close()


def _with_host_lock(host_id: str):
    row = _host_row(host_id)
    return _host_operation_lock(Path(row["home"])) if row and row.get("home") else None


# ---------------------------------------------------------------- 目录与列举

def _snap_dir(host_id: str) -> Path:
    return SAFEBOX / host_id


def _bak_files(host_id: str):
    d = _snap_dir(host_id)
    if not d.is_dir():
        return []
    return sorted((p for p in d.glob("*.bak") if p.is_file()), key=lambda p: p.name)


def _prune(host_id: str, keep: int = KEEP):
    """只留最新 keep 份。这里 keep 恒为 1：备份就是一个 .bak，再锁就覆盖。"""
    files = _bak_files(host_id)
    gone = []
    for p in (files[:-keep] if keep > 0 else files):
        try:
            p.unlink()
            gone.append(p.name)
        except OSError:
            pass
    return gone


def latest(host_id: str):
    """最近那一份 .bak（Path），没有就 None。"""
    files = _bak_files(host_id)
    return files[-1] if files else None


def _stale_home_guard(host_id: str, snap=None) -> str:
    """锁的那份是在另一个家目录拍的？是就返回一句人话，否则空串。

    锁的时候把家目录写进 home.txt（一行）。家目录被改过（手加的宿主改了路径）
    还拿着旧备份去恢复，恢复的就不是这一家的东西了 —— 所以这里拦住。
    """
    d = _snap_dir(host_id)
    note = d / HOME_NOTE
    if not note.is_file():
        return ""
    try:
        was = note.read_text(encoding="utf-8").strip()
    except OSError:
        return ""
    if not was:
        return ""
    now = str(_entry_of(host_id)[0])
    if os.path.normcase(was) != os.path.normcase(now):
        return "保险箱是给 %s 拍的，这家家目录现在是 %s，先重新锁定。" % (was, now)
    return ""


def list_snapshots(host_id: str = "") -> dict:
    """某一家 / 全部宿主的保险箱清单。tag 就是文件名里那个时间戳。"""
    out = []
    if host_id:
        dirs = [_snap_dir(host_id)]
    else:
        dirs = sorted(p for p in SAFEBOX.iterdir() if p.is_dir()) if SAFEBOX.is_dir() else []
    for d in dirs:
        for p in _bak_files(d.name):
            entry, tag = _split(p.name)
            try:
                size = p.stat().st_size
                at = datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            except OSError:
                size, at = 0, ""
            out.append({"tag": tag, "host": d.name, "entry": entry, "path": str(p),
                        "bytes": size, "at": at, "stage": "锁定时",
                        "files": 1, "top": 1, "skills": 0})
    return {"ok": True, "host": host_id, "snapshots": out}


# ---------------------------------------------------------------- 三动作

def take(host_id: str) -> dict:
    """锁定保险箱：把入口文件整份存成一份 .bak。"""
    ctx = _with_host_lock(host_id)
    if ctx is None:
        return {"ok": False, "host": host_id, "error": "没有这家智能体。"}
    with ctx:
        return _take_unlocked(host_id)


def _take_unlocked(host_id: str) -> dict:
    home, entry = _entry_of(host_id)
    if not str(home) or not home.is_dir():
        return {"ok": False, "host": host_id, "error": "这家家目录不在：%s" % home}
    src = home / entry
    if not src.is_file():
        return {"ok": False, "host": host_id,
                "error": "入口文件不在（%s\\%s），没什么可锁的。" % (home, entry)}
    data = src.read_bytes()
    # 先清掉旧的那一份：一家只留一个 .bak，再点就是覆盖。
    gone = _prune(host_id, keep=0)
    tag = _tag()
    dst = _snap_dir(host_id) / ("%s.%s.bak" % (_flatten(entry), tag))
    atomic_write_bytes(dst, data)
    atomic_write_bytes(_snap_dir(host_id) / HOME_NOTE, str(home).encode("utf-8"))
    say = "已存 %s（%d 字节）→ %s" % (entry, len(data), dst.name)
    if gone:
        say = "覆盖了旧的那一份（%s）；%s" % (gone[-1], say)
    return {"ok": True, "host": host_id, "tag": tag, "path": str(dst),
            "bytes": len(data), "sha256": _sha(data), "stage": "锁定时",
            "files": 1, "top": 1, "skills": 0, "say": say}


def compare(host_id: str) -> dict:
    """比对：现在这份 vs 最近那份 .bak。有差异不是失败，是清单。"""
    ctx = _with_host_lock(host_id)
    if ctx is None:
        return {"ok": False, "host": host_id, "error": "没有这家智能体。"}
    with ctx:
        return _compare_unlocked(host_id)


def _text(data: bytes) -> str:
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("utf-8", "replace")


def _line_diffs(old: str, new: str, limit: int = 8):
    import difflib
    a, b = old.splitlines(), new.splitlines()
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b).get_opcodes():
        if op == "equal":
            continue
        for k in range(i1, min(i2, i1 + 3)):
            out.append("第 %d 行 少了/变了：%s" % (k + 1, a[k].strip()[:70]))
        for k in range(j1, min(j2, j1 + 3)):
            out.append("第 %d 行 现在多出：%s" % (k + 1, b[k].strip()[:70]))
        if len(out) >= limit:
            break
    return out[:limit]


def _compare_unlocked(host_id: str) -> dict:
    home, _entry = _entry_of(host_id)
    kept = latest(host_id)
    if kept is None:
        return {"ok": False, "host": host_id, "same": None, "diffs": [],
                "error": "还没锁过，没得比。先按「锁定保险箱」。"}
    kept_entry, tag = _split(kept.name)
    old = kept.read_bytes()
    cur = home / kept_entry
    diffs = []
    if not cur.is_file():
        diffs.append("入口文件 %s 现在不在（存的那份 %d 字节）" % (kept_entry, len(old)))
    else:
        new = cur.read_bytes()
        if new != old:
            diffs.append("入口文件 %s：存的那份 %d 字节 → 现在 %d 字节"
                         % (kept_entry, len(old), len(new)))
            diffs.extend(_line_diffs(_text(old), _text(new)))
    stale = _stale_home_guard(host_id)
    if stale:
        diffs.append(stale)
    same = not diffs
    return {"ok": True, "host": host_id, "tag": tag, "same": same, "diffs": diffs,
            "say": "和 %s（%s）%s" % (kept_entry, tag, "逐字节一样" if same
                                     else "有 %d 处不一样" % len(diffs))}


def restore(host_id: str) -> dict:
    """恢复：把最近那份 .bak 逐字节写回入口文件。.bak 不消耗，能反复退。"""
    ctx = _with_host_lock(host_id)
    if ctx is None:
        return {"ok": False, "host": host_id, "error": "没有这家智能体。"}
    with ctx:
        return _restore_unlocked(host_id)


def _restore_unlocked(host_id: str) -> dict:
    stale = _stale_home_guard(host_id)
    if stale:
        return {"ok": False, "host": host_id, "error": stale}
    home, _entry = _entry_of(host_id)
    if not str(home) or not home.is_dir():
        return {"ok": False, "host": host_id, "error": "这家家目录不在：%s" % home}
    kept = latest(host_id)
    if kept is None:
        return {"ok": False, "host": host_id, "error": "还没锁过，没得恢复。"}
    kept_entry, tag = _split(kept.name)
    data = kept.read_bytes()
    dst = home / kept_entry
    before = dst.read_bytes() if dst.is_file() else b""
    # 恢复 = 把那份 bak 换回 md：先写回入口文件，再把 bak 用掉。
    # 于是「备份」是一次性的一个文件，按你说的来（要再退就先重新锁定）。
    atomic_write_bytes(dst, data)
    try:
        kept.unlink()
    except OSError:
        pass
    return {"ok": True, "host": host_id, "tag": tag, "path": str(dst),
            "bytes": len(data), "consumed": True,
            "say": "已把 %s 换回 %s 那一版（%d → %d 字节）。备份用掉了，要再退就先重新锁定。"
                   % (kept_entry, tag, len(before), len(data))}


# ---------------------------------------------------------------- CLI

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="safebox.py", description="宿主入口文件保险箱（锁/比/退）")
    ap.add_argument("action", choices=["snapshot", "verify", "restore", "list"])
    ap.add_argument("--host", default="", help="宿主 id")
    ap.add_argument("--all", action="store_true", help="全部宿主")
    args = ap.parse_args(argv)
    if args.action == "list":
        print(json.dumps(list_snapshots(args.host), ensure_ascii=False, indent=1))
        return 0
    if not args.host:
        print("要指名 --host <id>。", file=sys.stderr)
        return 2
    res = {"snapshot": take, "verify": compare, "restore": restore}[args.action](args.host)
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
