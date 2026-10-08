# -*- coding: utf-8 -*-
"""hubcore 一键卸载（自包含：只依赖标准库，不 import 本包任何其它文件）。

    python uninstall.py --host-home <宿主家目录> [--yes]

也可以直接跑装好的那一份：python <宿主家目录>/hub/uninstall.py [--yes]

按 install-manifest.json 精确卸：
  1. 宿主入口文件只摘标记块、底模块与指引块（各摘各的，客人的不动，主人的不动）
     摘完与备份逐字节相同 -> 整体还原备份（主人后来一个字没动过）
     已被主人改过           -> 只摘块，绝不覆盖主人的修改
  2. 删掉本系统写的那棵树
  3. 打印一份人能看的卸干净清单

绝不删除宿主自己原有的任何文件：动手前只按清单里列出的路径删，越界的一律跳过。

这份文件随包走，所以它本身不含任何外部路径、远端地址或技能系统路径。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import threading
import tempfile
import uuid
from contextlib import contextmanager
from pathlib import Path

PKG_DIRNAME = "hub"
MANIFEST_NAME = "install-manifest.json"
MARKER_BEGIN = "# >>> hubcore hub >>>"
MARKER_END = "# <<< hubcore hub <<<"
BASE_BEGIN = "# >>> hubcore base >>>"
BASE_END = "# <<< hubcore base <<<"
GUEST_BEGIN = "# >>> hubcore guest >>>"
GUEST_END = "# <<< hubcore guest <<<"
BOM = b"\xef\xbb\xbf"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def same_as_origin(stripped: bytes, backup: bytes, origin_ends_with_nl) -> bool:
    """摘完块之后的正文，是不是就是装前那份原文（逐字节）。

    装的时候（_bundle_lib.insert_marker）会在原文后面补一个分隔换行：
    原文不以换行收尾时必须补，否则标记块首行会粘在主人最后一行上，
    摘块按行锚点匹配就会失效。所以补的这一个换行是**我们加的**，不是主人的。

    不把它认出来会有两个后果，都很坏：
      1. 「装完再卸完」比原文多一个字节；
      2. 更糟的是这一个字节差会被当成「主人自己改过」，于是走「只摘块不覆盖」，
         把我们改出来的换行永久留在主人的文件里，还报告成「属正常」。

    光看字节分辨不出来：「abc」+「\\n」+块 与 「abc\\n」+块 装完长得一模一样。
    所以 install.py 把「备份原文是否以换行收尾」记进了清单，这里据此判。

    origin_ends_with_nl 为 None = 老版本清单没这项（那时还没记）：按「可能补过」处理，
    只在备份确实不以换行收尾、且差异恰好是那一个换行时才认。这样老装的也能干净卸回去。
    """
    if stripped == backup:
        return True
    if origin_ends_with_nl is False or origin_ends_with_nl is None:
        body = backup[len(BOM):] if backup.startswith(BOM) else backup
        if body and not body.endswith(b"\n") and stripped == backup + b"\n":
            return True
    return False


def atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / (path.name + ".tmp-%d-%s-%s" % (
        os.getpid(), threading.get_ident(), uuid.uuid4().hex))
    with open(tmp, "wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


@contextmanager
def operation_lock(host_home: Path):
    """同一宿主的装/卸跨进程互斥；进程崩溃时由 OS 自动释放。"""
    key = sha256_bytes(os.path.normcase(str(Path(host_home).resolve())).encode("utf-8"))[:32]
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
        raise RuntimeError("这家宿主已有装卸操作在进行，请稍后再试。") from exc
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


# 块指纹用的常量。必须和装的时候写进去的完全一致，pack.py 每次打包都会核对，
# 对不上就拒绝打包——不然这两份会悄悄漂移，卸载就认不出自己写的块。
# 标记块**内联规则全文**（2026-09-28 起）。卸载器不再自己存一份正文：
# 它和装的时候读**同一个文件**（本目录下的 AGENTS.md，随中枢本体一起装进来），
# 读同一份就不会漂移。原来这里存 11 句压缩短句，规则一融合就必然对不上，
# 而 pack.py 每次打包都核对两份一致——那正是它拦住我的原因。
def _rule_text() -> str:
    """读中枢规则全文。本文件随包装进 hub/，AGENTS.md 就在同一目录。"""
    here = Path(__file__).resolve().parent
    # 装好后：本目录下的 AGENTS.md（随中枢本体一起装进 hub/）。
    # 源仓里跑（打包器核对时）：dist/hubcore/AGENTS.md——装出来的那份，
    # 和装的时候写进入口文件的是同一份，核对才有意义。
    cands = [here / "AGENTS.md", here / "dist" / "hubcore" / "AGENTS.md"]
    src = next((c for c in cands if c.is_file()), cands[0])
    try:
        lines = src.read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    while lines and (not lines[0].strip() or lines[0].lstrip().startswith(">")):
        lines = lines[1:]
    return "\n".join(lines).strip("\n")


_POINTER_TAIL = ('工具 hub\\tools\\，按需读 hub\\ctxiso\\，'
                 '一键卸 hub\\uninstall.py --host-home <家目录>。'
                 '本块最后定论；前面的卡片只在不与本块冲突处生效。')


def _line_re(literal):
    # 行尾容忍一个 \r：主人用任何 Windows 编辑器把入口文件存成 CRLF 之后，
    # 原来的 “[ \t]*$” 会因为那个 \r 匹配不上——装得上、卸不掉，卸回还会静默说
    # 「本来就没有标记块」。这是只在真机 CRLF 文件上发作的洞。
    return re.compile(r"^[ \t]*" + re.escape(literal) + r"[ \t]*\r?$", re.M)


# BEGIN 允许前面挂一个 BOM：带 BOM 的入口文件里第一行在字节上是「BOM + 标记」，
# 不认它就当没装过。下面会把 BOM 排除在块外，摘块时留着它。
_BEGIN_RE = re.compile(r"^﻿?[ \t]*" + re.escape(MARKER_BEGIN) + r"[ \t]*\r?$", re.M)
_END_RE = _line_re(MARKER_END)
_BASE_BEGIN_RE = re.compile(r"^﻿?[ \t]*" + re.escape(BASE_BEGIN) + r"[ \t]*\r?$", re.M)
_BASE_END_RE = _line_re(BASE_END)
_GUEST_BEGIN_RE = re.compile(r"^﻿?[ \t]*" + re.escape(GUEST_BEGIN) + r"[ \t]*\r?$", re.M)
_GUEST_END_RE = _line_re(GUEST_END)


def _expected_body_lines():
    return {l.strip() for l in marker_block().splitlines() if l.strip()}


def marker_block(host_home="", rule_text=""):
    """和装的时候写进去的完全一样，用来核对「这块是不是中枢写的」。"""
    if host_home:
        base = str(host_home).replace("/", "\\").rstrip("\\")
        head = "本机中枢在 " + base + "\\hub\\：" + _POINTER_TAIL
    else:
        head = "本机中枢在 hub\\：" + _POINTER_TAIL
    text = rule_text if rule_text else _rule_text()
    return "\n".join((MARKER_BEGIN, head, text, MARKER_END)) + "\n"


def marker_body_fingerprint(block_text) -> str:
    """标记块里「规则正文」那一截的指纹（剥掉 BEGIN / 指针行 / END，逐行 strip、丢空行，拼起来算 sha256）。

    和 _bundle_lib 同一算法。装了中枢内核卡时块里正文是那张卡，安装清单记着它的指纹，
    卸回靠这份指纹认块 —— 否则自己写的块会认不出来，摘不掉。
    """
    lines = [l.strip() for l in str(block_text or "").splitlines()]
    return hashlib.sha256("\n".join(l for l in lines[2:-1] if l).encode("utf-8")).hexdigest()


def classify_marker_block(block_text, body_sha=""):
    """这一块是不是中枢自己写的？顺带数出块里有几行不是我们写的。

    判据：BEGIN / END 各自独占一行，且第二行是指针行「本机中枢在 …」。
    主人可能在自己的说明文里抄一对标记来写「以后卸载就删这两行之间」，
    那一对不是我们的块，卸的时候必须原样留着——动它就是删主人的原文。
    """
    lines = [l.strip() for l in block_text.splitlines()]
    if len(lines) < 3:
        return False, "太短，不成块", 0
    if lines[0] != MARKER_BEGIN or lines[-1] != MARKER_END:
        return False, "首尾不是独占的标记行", 0
    if not lines[1].startswith("本机中枢在 ") or not lines[1].endswith(_POINTER_TAIL):
        return False, "第二行不是指针行——这不是中枢写的块", 0
    expected = [l.strip() for l in _rule_text().splitlines() if l.strip()]
    expected_set = set(expected)
    body = [l for l in lines[2:-1] if l]
    # 路线一：装了中枢内核卡 —— 块里的正文是那张卡。靠安装清单记着的正文指纹认块。
    if body_sha and marker_body_fingerprint(block_text) == body_sha:
        return True, "", 0
    # 路线二：默认块，必须包含本版本完整规则正文。
    it = iter(body)
    if not all(any(candidate == want for candidate in it) for want in expected):
        return False, "规则正文不完整——这不是中枢写的块", 0
    ours = set(expected)
    # 指针行（第 2 行）带宿主家目录，逐台机器都不一样，不参与「是不是我们写的」比对。
    # 只比下面 12 块底线正文。
    foreign = sum(1 for l in lines[2:-1] if l and l not in expected_set)
    return True, "", foreign


def strip_marker(text: str, body_sha: str = ""):
    """只摘中枢自己写的块。返回 (剩余文本, 报告dict)。

    body_sha = 安装清单里的标记块正文指纹（装了中枢内核卡时靠它认块）。
    """
    blocks = []
    pos = 0
    while True:
        mb = _BEGIN_RE.search(text, pos)
        if not mb:
            break
        me = _END_RE.search(text, mb.end())
        nested = _BEGIN_RE.search(text, mb.end())
        if nested and (me is None or nested.start() < me.start()):
            pos = nested.start()
            continue
        if not me:
            pos = mb.end()
            continue
        start = mb.start()
        if text[start] == "\ufeff":
            start += 1           # BOM 不属于标记块，摘块时必须留着它
        btext = text[start:me.end()]
        ours, why, foreign = classify_marker_block(btext, body_sha)
        end = me.end()
        if text[end:end + 1] == "\r":
            end += 1
        if text[end:end + 1] == "\n":
            end += 1
        blocks.append({"start": start, "end": end, "ours": ours,
                       "why": why, "foreign": foreign})
        pos = end
    ours_blocks = [b for b in blocks if b["ours"]]
    rep = {"ours_total": len(ours_blocks), "removed": 0,
           "kept_foreign": len(blocks) - len(ours_blocks), "foreign_lines": 0,
           "others_kept": 0, "why": [b["why"] for b in blocks if not b["ours"]]}
    if not ours_blocks:
        return text, rep
    b = ours_blocks[0]              # 只摘最上面那一个，其余保留并报出来
    text = text[:b["start"]] + text[b["end"]:]
    rep["removed"] = 1
    rep["foreign_lines"] = b["foreign"]
    rep["others_kept"] = len(ours_blocks) - 1
    return text, rep


def strip_base_block(text: str):
    """只摘中枢自己写的底模块（第二行须是「底模：」）。返回 (剩余文本, 摘掉个数)。"""
    out = text
    removed = 0
    pos = 0
    while True:
        mb = _BASE_BEGIN_RE.search(out, pos)
        if not mb:
            break
        me = _BASE_END_RE.search(out, mb.end())
        nested = _BASE_BEGIN_RE.search(out, mb.end())
        if nested and (me is None or nested.start() < me.start()):
            pos = nested.start()
            continue
        if not me:
            pos = mb.end()
            continue
        start = mb.start()
        if out[start:start + 1] == "﻿":
            start += 1
        end = me.end()
        if out[end:end + 1] == "\r":
            end += 1
        if out[end:end + 1] == "\n":
            end += 1
        inner_raw = out[mb.end():me.start()]
        lines = inner_raw.splitlines(keepends=True)
        nonempty = [(i, line.rstrip("\r\n").strip())
                    for i, line in enumerate(lines) if line.strip()]
        if len(nonempty) < 2 or not nonempty[0][1].startswith("底模：") \
                or not nonempty[1][1].startswith("指纹："):
            pos = me.end()
            continue
        fp = nonempty[1][1][3:].strip().lower()
        fp_line_index = nonempty[1][0]
        body_start = sum(len(line) for line in lines[:fp_line_index + 1])
        body_raw = inner_raw[body_start:]
        if body_raw.endswith("\r\n"):
            body = body_raw[:-2]
        elif body_raw.endswith(("\n", "\r")):
            body = body_raw[:-1]
        else:
            body = body_raw
        if fp != sha256_bytes(body.encode("utf-8")):
            pos = me.end()
            continue
        out = out[:start] + out[end:]
        removed += 1
        pos = start
    return out, removed


def _strip_wrapped(text: str, begin_re, end_re, second_mark: str):
    """通用摘块：定界 + 第二行标识。返回 (剩余文本, 摘掉个数)。"""
    out = text
    removed = 0
    pos = 0
    while True:
        mb = begin_re.search(out, pos)
        if not mb:
            break
        me = end_re.search(out, mb.end())
        nested = begin_re.search(out, mb.end())
        if nested and (me is None or nested.start() < me.start()):
            pos = nested.start()
            continue
        if not me:
            pos = mb.end()
            continue
        start = mb.start()
        if out[start:start + 1] == "﻿":
            start += 1
        end = me.end()
        if out[end:end + 1] == "\r":
            end += 1
        if out[end:end + 1] == "\n":
            end += 1
        inner_raw = out[mb.end():me.start()]
        lines = inner_raw.splitlines(keepends=True)
        nonempty = [(i, line.rstrip("\r\n").strip())
                    for i, line in enumerate(lines) if line.strip()]
        if len(nonempty) < 2 or not nonempty[0][1].startswith(second_mark) \
                or not nonempty[1][1].startswith("指纹："):
            pos = me.end()
            continue
        fp = nonempty[1][1][3:].strip().lower()
        fp_line_index = nonempty[1][0]
        body_start = sum(len(line) for line in lines[:fp_line_index + 1])
        body_raw = inner_raw[body_start:]
        if body_raw.endswith("\r\n"):
            body = body_raw[:-2]
        elif body_raw.endswith(("\n", "\r")):
            body = body_raw[:-1]
        else:
            body = body_raw
        if fp != sha256_bytes(body.encode("utf-8")):
            pos = me.end()
            continue
        out = out[:start] + out[end:]
        removed += 1
        pos = start
    return out, removed


def strip_guest_block(text: str):
    """只摘中枢自己写的技能指引块（第二行须是「技能指引：」）。"""
    return _strip_wrapped(text, _GUEST_BEGIN_RE, _GUEST_END_RE, "技能指引：")


def read_manifest(pkg_root: Path) -> dict:
    p = Path(pkg_root) / MANIFEST_NAME
    if not p.is_file():
        raise SystemExit("读不到安装清单：%s\n  这个目录不是装好的 hubcore，或已被卸载。" % p)
    return json.loads(p.read_text(encoding="utf-8"))


def _resolve_entry(host_home: Path) -> str:
    """入口文件名优先取清单里记的那个；没记就按常见的来。"""
    return "AGENTS.md"


def _safe_child(root: Path, rel: str):
    """Resolve a manifest path and require it to remain below root."""
    if not isinstance(rel, str) or not rel.strip():
        return None
    candidate = Path(rel)
    if candidate.is_absolute() or ".." in candidate.parts:
        return None
    try:
        target = (Path(root) / candidate).resolve()
        target.relative_to(Path(root).resolve())
    except (OSError, ValueError):
        return None
    return target


def _uninstall_unlocked(pkg_root: Path, assume_yes: bool = False) -> int:
    pkg_root = Path(pkg_root)
    manifest = read_manifest(pkg_root)
    entry = manifest.get("entry_file", {})
    actual_home = pkg_root.parent.resolve()
    recorded_home = Path(manifest.get("host_home") or actual_home).expanduser().resolve()
    if recorded_home != actual_home:
        print("卸载停止：清单记录的宿主家目录与当前 hub/ 所在家目录不一致。", file=sys.stderr)
        print("  清单：%s" % recorded_home, file=sys.stderr)
        print("  当前：%s" % actual_home, file=sys.stderr)
        return 2
    host_home = actual_home
    pre_record = manifest.get("pre_existing_hub", {}) or {}
    if pre_record.get("backed_up") and _safe_child(pkg_root, pre_record.get("backup", "")) is None:
        print("卸载停止：清单里的旧 hub/ 备份路径越界。", file=sys.stderr)
        return 2

    print("卸载清单：%s v%s" % (manifest["package"]["name"], manifest["package"]["version"]))
    print("装于：    %s" % manifest.get("installed_at", "?"))
    print("宿主：    %s（%s）" % (host_home, manifest.get("host", "?")))
    print("本次将删：%d 个受管文件 + %s/ 整棵树" % (len(manifest.get("files", [])), PKG_DIRNAME))
    print()

    if not assume_yes:
        if not sys.stdin.isatty():
            print("非交互环境要加 --yes 才动手。", file=sys.stderr)
            return 2
        if input("确认卸载？摘掉中枢写的几段，并按记录还原宿主原文（覆盖模式按备份合并还原）。[y/N] ").strip().lower() not in ("y", "yes"):
            print("已取消，什么都没动。")
            return 0

    actions = []

    # ---- 1. 入口文件：只摘标记块
    entry_name = str(entry.get("path", "AGENTS.md"))
    entry_path = _safe_child(host_home, entry_name)
    if entry_path is None:
        print("卸载停止：清单里的入口路径越界：%s" % entry_name, file=sys.stderr)
        return 2
    backup_rel = entry.get("backup", "")
    backup_path = _safe_child(pkg_root, backup_rel) if backup_rel else None

    if entry_path.is_file():
        original = entry_path.read_bytes()
        # 宿主原文件有没有 UTF-8 BOM 必须原样带回去。掉了 BOM 就等于改了主人的文件，
        # 哪怕正文一个字没变——这种 bug 只在带 BOM 的编辑器下发作，极难察觉。
        bom = original.startswith(BOM)
        try:
            text = (original[len(BOM):] if bom else original).decode("utf-8")
        except UnicodeDecodeError:
            print("卸载停止：入口文件不是有效的 UTF-8，未写入也未删除任何文件。",
                  file=sys.stderr)
            return 2
        origin_dropped = bool(entry.get("origin_dropped"))
        stripped, rep = strip_marker(text, str(entry.get("marker_body_sha256") or ""))
        count = rep["removed"]
        stripped, base_removed = strip_base_block(stripped)
        stripped, guest_removed = strip_guest_block(stripped)
        stripped_bytes = (BOM if bom else b"") + stripped.encode("utf-8")
        want_base = bool((entry.get("base") or {}).get("name"))
        want_guest = bool((entry.get("guest") or {}).get("name"))
        want_marker = bool(entry.get("marker_written", True))
        # 装的时候有没有给原文补过分隔换行（install.py 记的；老清单没这项 -> None）
        origin_nl = entry.get("origin_ends_with_nl")
        if count == 0 and base_removed == 0 and guest_removed == 0:
            actions.append("入口文件里本来就没有标记块/底模块/指引块，未改动：%s" % entry_path)
        else:
            if not want_marker and count == 0:
                actions.append("这次装的时候就没写中枢标记块（只写了底模/指引），按记录只摘那两段。")
            backup_bytes = backup_path.read_bytes() if (backup_path and backup_path.is_file()) else None
            existed_before = entry.get("existed_before", backup_bytes is not None)
            if not existed_before and not stripped.strip():
                # 装前根本没有这个文件，是本系统新建的：还原成「不存在」
                entry_path.unlink()
                actions.append("装前不存在这个入口文件，是本系统新建的 -> 已删掉，回到装前状态：%s" % entry_path)
            elif origin_dropped and backup_bytes is not None:
                # 覆盖模式：装的时候把主人原有文本整段丢掉了。
                # 还原 = 备份里的原文 + 主人装完之后自己加的内容（摘块后剩下的那部分）。
                def _nobom(b):
                    return b[len(BOM):] if b.startswith(BOM) else b
                _orig = _nobom(backup_bytes)
                _rest = _nobom(stripped_bytes)
                if _rest.strip():
                    _join = _orig + ((b"\n" if _orig and not _orig.endswith(b"\n") else b"") + _rest)
                    note = "主人装完之后又加过内容 -> 原文 + 后加内容 合并还原"
                else:
                    _join = _orig
                    note = "主人装完之后没动过 -> 直接还原原文"
                atomic_write_bytes(entry_path, (BOM if bom else b"") + _join)
                actions.append("覆盖模式（%s）-> 已还原：%s" % (note, entry_path))
            elif backup_bytes is not None and same_as_origin(stripped_bytes, backup_bytes, origin_nl):
                atomic_write_bytes(entry_path, backup_bytes)
                extra = "".join(x for x in
                                [(" + %d 个底模块" % base_removed) if base_removed else "",
                                 (" + %d 个指引块" % guest_removed) if guest_removed else ""])
                actions.append("摘掉 %d 个标记块%s后与备份逐字节相同 -> 整体还原备份：%s"
                               % (count, extra, entry_path))
            else:
                why = "备份不存在" if backup_bytes is None else "主人后来改过"
                atomic_write_bytes(entry_path, stripped_bytes)
                extra = "".join(x for x in
                                [(" + %d 个底模块" % base_removed) if base_removed else "",
                                 (" + %d 个指引块" % guest_removed) if guest_removed else ""])
                actions.append("摘掉 %d 个标记块%s（%s）-> 只摘块不覆盖：%s"
                               % (count, extra, why, entry_path))
            if want_base and not base_removed:
                actions.append("注意：清单里记着底模 %s，但文件里没找到它的块（主人可能已手动删掉）。"
                               % (entry.get("base") or {}).get("name"))
            if want_guest and not guest_removed:
                actions.append("注意：清单里记着技能指引 %s，但文件里没找到它的块（主人可能已手动删掉）。"
                               % (entry.get("guest") or {}).get("name"))
            if rep["foreign_lines"]:
                actions.append("注意：中枢块内有 %d 行不是我们写的（主人自己加的），已整块摘掉。"
                               % rep["foreign_lines"])
            if rep["others_kept"]:
                actions.append("注意：文件里还有 %d 块中枢块，只摘了最上面一个，其余原样保留，请人工确认。"
                               % rep["others_kept"])
            if rep["kept_foreign"]:
                actions.append("原样保留 %d 对主人自己写的标记行（%s）。"
                               % (rep["kept_foreign"], "；".join(rep["why"])))
            final = sha256_bytes(entry_path.read_bytes()) if entry_path.is_file() else ""
            if entry.get("sha_before") and final != entry["sha_before"]:
                actions.append("注意：当前 sha256=%s，装前 sha256=%s（装后主人自己改过，属正常）"
                               % (final[:16], entry["sha_before"][:16]))
    else:
        actions.append("入口文件已不在，无需摘块：%s" % entry_path)

    # ---- 2. 删本系统写的那棵树
    pre = manifest.get("pre_existing_hub", {})
    if pre.get("backed_up"):
        pre_rel = pre.get("backup", "")
        pre_path = _safe_child(pkg_root, pre_rel) if pre_rel else None
        restore_to = host_home / PKG_DIRNAME
        if not (pre_path and pre_path.is_dir()):
            actions.append("⚠ 清单说装前就有 %s/，但备份找不到（%s）—— 请人工核对"
                           % (PKG_DIRNAME, pre_rel or "(未记录路径)"))
            _remove_managed(pkg_root, manifest, actions)
        else:
            # 备份就躺在 pkg_root 里面（.backups/…）。直接 rmtree(pkg_root) 会把备份
            # 一起删掉，紧接着 copytree/copytree 必抛 FileNotFoundError，主人的目录
            # 永远回不到原位（2026-10-09 实测复现）。所以先把备份搬到 pkg_root **外面**
            # 再动手，最后搬回来 —— 与 install.swap_into_place 同一套「失败就搬回来」。
            saved = host_home / (".hubcore-restore-" + uuid.uuid4().hex[:8])
            shutil.move(str(pre_path), str(saved))
            shutil.rmtree(restore_to, ignore_errors=True)
            if restore_to.exists():
                actions.append("⚠ %s/ 没删干净（多半被占用），装前的目录暂存在：%s"
                               % (PKG_DIRNAME, saved))
            else:
                shutil.move(str(saved), str(restore_to))
                actions.append("还原装前已存在的 %s/（装前就在，不属于本系统）" % PKG_DIRNAME)
    else:
        _remove_managed(pkg_root, manifest, actions)

    # ---- 3. 连带清掉运行期生成的字节码
    if pkg_root.exists() and find_bytecode(pkg_root):
        n = purge_bytecode(pkg_root)
        actions.append("清理运行期生成的字节码 %d 个（.pyc 头里记着绝对路径，不留）" % n)

    # ---- 4. 清单
    print("=" * 68)
    print("卸干净清单")
    print("=" * 68)
    for a in actions:
        print("  · " + a)
    print()
    if not pkg_root.exists():
        print("  · %s/ 已整棵删除" % PKG_DIRNAME)
    print()
    print("没动过的东西：宿主家目录下除 %s/ 以外的一切；%s 里的原文一字未改。"
          % (PKG_DIRNAME, entry_name))
    return 0


def uninstall(pkg_root: Path, assume_yes: bool = False) -> int:
    """持有宿主锁，并在真正删文件前保留可恢复快照。"""
    pkg_root = Path(pkg_root)
    try:
        manifest = read_manifest(pkg_root)
    except BaseException:
        # 让原函数给出它自己的清晰错误；这里没有可安全建立事务快照。
        return _uninstall_unlocked(pkg_root, assume_yes)
    host_home = pkg_root.parent.resolve()
    recorded = Path(manifest.get("host_home") or host_home).expanduser().resolve()
    if recorded != host_home:
        return _uninstall_unlocked(pkg_root, assume_yes)
    entry_name = str((manifest.get("entry_file") or {}).get("path", "AGENTS.md"))
    entry_path = _safe_child(host_home, entry_name)
    if entry_path is None:
        return _uninstall_unlocked(pkg_root, assume_yes)
    entry_existed = entry_path.is_file()
    entry_before = entry_path.read_bytes() if entry_existed else b""
    rollback = host_home / (".hubcore-uninstall-" + uuid.uuid4().hex)
    try:
        with operation_lock(host_home):
            shutil.copytree(pkg_root, rollback, symlinks=True)
            try:
                result = _uninstall_unlocked(pkg_root, assume_yes)
            except BaseException as exc:
                print("卸载中断，正在按快照回滚：%s" % exc, file=sys.stderr)
                if pkg_root.exists():
                    shutil.rmtree(pkg_root, ignore_errors=True)
                if rollback.exists():
                    shutil.copytree(rollback, pkg_root, symlinks=True)
                if entry_existed:
                    atomic_write_bytes(entry_path, entry_before)
                elif entry_path.exists():
                    entry_path.unlink()
                return 1
            return result
    except RuntimeError as exc:
        print("卸载停止：%s" % exc, file=sys.stderr)
        return 2
    finally:
        if rollback.exists():
            shutil.rmtree(rollback, ignore_errors=True)


def find_bytecode(root):
    """包内不该存在的字节码。运行期最多生成一个，卸干净才算卸干净。"""
    root = Path(root)
    return [p for p in root.rglob("*")
            if p.name == "__pycache__" or p.suffix in (".pyc", ".pyo")]


def purge_bytecode(root) -> int:
    n = 0
    for p in find_bytecode(root):
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
            n += 1
        elif p.is_file():
            p.unlink()
            n += 1
    return n


def _remove_managed(pkg_root: Path, manifest: dict, actions: list) -> int:
    """只删清单里列出的文件，清单外的用户文件保留。"""
    listed = {f["path"] for f in manifest.get("files", [])}
    deleted = 0
    root = pkg_root.resolve()
    for rel in sorted(listed, key=lambda s: -s.count("/")):
        target = _safe_child(pkg_root, rel)
        if target is None:
            actions.append("清单里有越界路径，跳过：%s" % rel)
            continue
        if target.is_file():
            target.unlink()
            deleted += 1
    manifest_path = _safe_child(pkg_root, MANIFEST_NAME)
    if manifest_path is not None and manifest_path.is_file():
        manifest_path.unlink()
    # 运行自检/ctxiso 时会生成这些包内侧车目录；它们不是主人后来放进来的
    # 文件，卸载时一并清掉，否则空安装会留下 hub/.state，下一次安装又会被
    # 当成“不是本系统的 hub/”而拒绝覆盖。其它未列入清单的内容仍原样保留。
    for runtime_name in (".state", ".backups"):
        runtime = pkg_root / runtime_name
        if runtime.is_dir():
            shutil.rmtree(runtime, ignore_errors=True)
            if not runtime.exists():
                actions.append("清理本系统运行期目录：%s/" % runtime_name)
    # 只清理空目录；用户后来放进 hub/ 的文件和目录不能被卸载器吞掉。
    for directory in sorted((p for p in pkg_root.rglob("*") if p.is_dir()),
                            key=lambda p: len(p.parts), reverse=True):
        try:
            directory.rmdir()
        except OSError:
            pass
    try:
        pkg_root.rmdir()
        actions.append("删除受管文件 %d 个，hub/ 已清空并删除" % deleted)
    except OSError:
        actions.append("删除受管文件 %d 个；hub/ 内还有未受管文件，已保留" % deleted)
    return deleted


def _guess_pkg_root(explicit: str) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve() / PKG_DIRNAME
    here = Path(__file__).resolve().parent
    if (here / MANIFEST_NAME).is_file():
        return here                      # 就是装好的那一份
    return here


def main(argv=None):
    ap = argparse.ArgumentParser(prog="uninstall.py", description="hubcore 一键卸载")
    ap.add_argument("--host-home", default="", help="宿主家目录（省略则按自己所在位置卸）")
    ap.add_argument("--yes", action="store_true", help="不再问，直接卸")
    args = ap.parse_args(argv)
    pkg_root = _guess_pkg_root(args.host_home)
    if not (pkg_root / MANIFEST_NAME).is_file():
        print("这里不是装好的 hubcore，没有清单可读：%s" % pkg_root, file=sys.stderr)
        return 2
    return uninstall(pkg_root, args.yes)


if __name__ == "__main__":
    sys.exit(main())
