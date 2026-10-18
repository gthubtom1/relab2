# -*- coding: utf-8 -*-
"""hubcore 自包含安装包的共享库。

被 03-bundle/ 下的 pack / install / uninstall / verify 共用；也会原样装进
<宿主家目录>/hub/，让 uninstall.py 与 verify.py 在装机后脱离源仓独立运行。

硬约束：本文件不得出现任何开发目录路径、远端地址或本机绝对路径。
只有标准库。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import threading
import uuid
from contextlib import contextmanager
from pathlib import Path

PACKAGE_NAME = "hubcore"
PACKAGE_VERSION = "1.0.0"

MANIFEST_NAME = "install-manifest.json"
META_NAME = "bundle-meta.json"
PKG_DIRNAME = "hub"          # 装进宿主家目录时，包树叫 hub/
BACKUP_DIRNAME = ".backups"
STATE_DIRNAME = ".state"

MARKER_BEGIN = "# >>> hubcore hub >>>"
MARKER_END = "# <<< hubcore hub <<<"

# CORE.md 的硬上限。**权威值在这里**——03-bundle 的 pack / install / verify 和
# 02-hubcore 的 build_hubcore 四道闸都从这里读，不要再各自写死 3000。
#
# 为什么从 3000 提到 4000：实测加第 12 块底线（「动手」——治"主人说继续、
# AI 回一句『好的我开始了』就停手"）之后 CORE.md 是 3,438 B，硬套 3000 只能靠
# 删底线来腾，**那是拿功能换字节**。主人的口径是「不能为了压缩大小导致功能不完善」，
# 所以该动的是这个预算，不是底线。剩下的 562 B 余量是给以后再加底线用的。
# 旧中枢 36,685 B -> 现在最大的一份常驻件是**标记块（24 KB 级，见 MARKER_BUDGET）**；
# CORE.md 3,952 B 只是首读件，不再物理常驻。别再拿 3,438 B / 降 90.6% 当现状。
CORE_BUDGET = int(os.environ.get("HUBCORE_CORE_BUDGET", "4000"))

# 标记块的字节上限。**它现在内联整份规则**（见 marker_block 的 docstring），
# 所以这个数是「整套规则 + 指针行」的上限，不是几条短句的上限。
#
# 2026-09-28 推翻了原来的设计：原先标记块只装 11 句压缩短句（1,353 B），
# 把细则推到 CORE.md / AGENTS.md 里，指针指过去让模型自己跳。
# **那个设计是围绕"省 token"建的，而主人从没要求过省 token**——只要求效果最好。
# 代价是实测出来的：指针是裸文件名，模型可能压根不去读那一跳。
# 所以现在改成：**规则全文内联，不赌模型会不会跳。**
#
# 预算按实测定：AGENTS.md 约 21 KB，加定界与指针行，最坏路径下留 20% 余量。
# 这个数只用于「装的时候拦一下异常膨胀」，**不是设计目标**——
# 规则该写多长就多长，不要为了凑这个数删底线。
MARKER_BUDGET = int(os.environ.get("HUBCORE_MARKER_BUDGET", "32000"))

# 底线自检：12 块，每块的关键短语。装包时逐条比对，缺一条就拒绝装。
# 这是机器证明「底线真的每轮都在」，不靠嘴说。
#
# 2026-09-28：短语全部改成**规则全文里的真实措辞**。
# 原来那套短语是照着「11 句压缩短句」写的，规则一融合成全文就全对不上了——
# 自检会误报「缺底线」，而实际上底线一个字没少。**判据必须跟着被测对象改。**
BOTTOM_LINES = (
    ("角色", ("掌舵", "没有编程基础的普通人")),
    ("选线", ("六套工作流", "workflows/")),
    ("三步判断", ("推演实际使用", "最值得先查", "据事实改变安排")),
    ("证据", ("永远不是物理证据", "探针没过＝没完成")),
    ("点头", ("工程方的活",)),
    # 「动手」治的是「主人说继续，AI 回一句『好的我开始了』然后什么都不做」。
    # 装了外部底模时更明显：底模常写「每条消息都要交个 deliverable」，
    # 而一句「好的我开始了」确实是个文本交付物。
    ("动手", ("行动指令", "现在调工具", "回话不能代替动手")),
    # 「找东西」治的是「主人说文件名，智能体从用户根目录开始翻，翻不到就在
    # <用户目录>\ 新建一个同名文件」——主人原话的需求被交到了别处。
    # 2026-09-28 在 PI 真机上实测到的。
    ("找东西", ("先在当前工作目录找", "找不到")),
    ("保存≠读取", ("保存过", "该进上下文", "带意图")),
    ("定档", ("轻量", "先讨论方案", "高风险")),
    ("换班", ("WORK-HANDOFF.md", "接班")),
    ("诚实", ("未验证", "全测完")),
    ("危险动作", ("危险动作", "密钥", "确认")),
)

_POINTER_TAIL = ("工具 hub\\tools\\，按需读 hub\\ctxiso\\，"
                 "一键卸 hub\\uninstall.py --host-home <家目录>。"
                 "本块最后定论；前面的卡片只在不与本块冲突处生效。")


def bottom_line_gaps(text: str):
    """逐块查底线短语。返回 [(块名, 缺哪些短语)]，全在则返回 []。"""
    gaps = []
    for name, phrases in BOTTOM_LINES:
        missing = [p for p in phrases if p not in text]
        if missing:
            gaps.append((name, missing))
    return gaps


def _rule_text() -> str:
    """中枢本体那份规则全文（AGENTS.md）。标记块内联的就是它。

    读的是**装好的包**里那份——装出来的和源仓的必须同源；找不到才退回源仓
    （开发时直接跑打包器会走到这条）。
    """
    here = Path(__file__).resolve().parent
    for cand in (here / "dist" / "hubcore" / "AGENTS.md",
                 here.parent / "02-hubcore" / "AGENTS.md"):
        try:
            text = cand.read_text(encoding="utf-8")
        except OSError:
            continue
        # 去掉顶部标题和引言：标记块自己就是入口，全文再声明一遍
        #「本文件是唯一的常驻提示词」会让人以为块里装的只是摘要。
        lines = text.splitlines()
        if lines and lines[0].startswith("# "):
            lines = lines[1:]
        while lines and (not lines[0].strip() or lines[0].lstrip().startswith(">")):
            lines = lines[1:]
        body = "\n".join(lines).strip("\n")
        if body:
            return body
    raise SystemExit("读不到中枢规则全文（02-hubcore/AGENTS.md）。先跑 pack.py 生成。")


def marker_block(host_home='', rule_text='') -> str:
    """写进宿主入口文件的那一块——**内联规则全文**，不再是指针 + 压缩短句。

    2026-09-28 推翻原来的三层设计。原来是「标记块 11 句短句 → 指针 →
    CORE.md → AGENTS.md」，赌模型会顺着指针跳。实测的问题是**它可能不跳**，
    而当初这么设计的理由写的是"省 token"——**主人从没要求过省 token**，
    只要求效果最好。省字节换来的风险是自己造的，所以改成全文内联，不赌那一跳。

    host_home 非空时，首行给出中枢在该宿主里的真实位置（只指宿主家目录内部）。
    指针行末尾那句「本块最后定论」是优先级声明：底模和指引卡是主人随时会换的，
    写在前面几段都可能自带一套「以我为准」的措辞，这一句把裁决权收回来。
    """
    tail = _POINTER_TAIL
    if host_home:
        base = str(host_home).replace("/", "\\").rstrip("\\")
        head = "本机中枢在 " + base + "\\hub\\：" + tail
    else:
        head = "本机中枢在 hub\\：" + tail
    text = rule_text if rule_text else _rule_text()
    return "\n".join((MARKER_BEGIN, head, text, MARKER_END)) + "\n"

# ---------------------------------------------------------------- 路径 / 哈希

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_bytes(path: Path) -> bytes:
    return Path(path).read_bytes()


BOM = b"\xef\xbb\xbf"


def decode(data: bytes) -> str:
    """宿主原文件按字节原样进出。带 BOM 就带 BOM 回来，不替主人改编码。"""
    if data.startswith(BOM):
        return data[len(BOM):].decode("utf-8", "replace")
    return data.decode("utf-8", "replace")


def has_bom(data: bytes) -> bool:
    return data.startswith(BOM)


def encode(text: str, bom: bool = False) -> bytes:
    """decode 的逆操作。bom=True 时补回 UTF-8 BOM——宿主原文件有没有 BOM，装卸都不能改。"""
    return (BOM if bom else b"") + text.encode("utf-8")


# ---------------------------------------------------------------- 原子写盘

def atomic_write_bytes(path: Path, data: bytes) -> None:
    path = Path(path)
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
    key = hashlib.sha256(os.path.normcase(str(Path(host_home).resolve())).encode("utf-8")).hexdigest()[:32]
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


def atomic_write_text(path: Path, text: str) -> None:
    atomic_write_bytes(path, encode(text))


def rmtree_quiet(path: Path) -> None:
    shutil.rmtree(path, ignore_errors=True)


# ---------------------------------------------------------------- 标记块

def _line_re(literal):
    # 行尾容忍一个 \r：主人用任何 Windows 编辑器把入口文件存成 CRLF 之后，
    # 原来的 “[ \t]*$” 会因那个 \r 匹配不上——装得上、卸不掉，卸回还会静默说
    # 「本来就没有标记块」。这是只在真机 CRLF 文件上发作的洞。
    return re.compile(r"^[ \t]*" + re.escape(literal) + r"[ \t]*\r?$", re.M)


# BEGIN 允许前面挂一个 BOM：带 BOM 的入口文件里，第一行在字节上是
# 「BOM + 标记」，不认它就当没装过。find_marker_blocks 会把 BOM 排除在块外。
_BEGIN_RE = re.compile(r"^﻿?[ \t]*" + re.escape(MARKER_BEGIN) + r"[ \t]*\r?$", re.M)
_END_RE = _line_re(MARKER_END)


def _expected_body_lines():
    return {l.strip() for l in marker_block().splitlines() if l.strip()}


def marker_body_fingerprint(block_text) -> str:
    """标记块里「规则正文」那一截的指纹：剥掉 BEGIN / 指针行 / END，逐行 strip、丢空行，拼起来算 sha256。

    为什么要这一手：装了**中枢内核卡**时，块里的规则正文是那张卡，不是包里的 AGENTS.md。
    只靠「包含包内规则全文」认块，自己写的块会认不出来 —— 卸回就摘不掉，永远残留在宿主文件里。
    装的时候把指纹记进安装清单，卸的时候拿它认块。
    """
    lines = [l.strip() for l in str(block_text or "").splitlines()]
    return sha256_bytes("\n".join(l for l in lines[2:-1] if l).encode("utf-8"))


def installed_manifest(host_home) -> dict:
    """宿主家里那份安装清单（没装过 / 读不出来就是空 dict）。"""
    p = Path(host_home) / PKG_DIRNAME / MANIFEST_NAME
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def installed_marker_body_sha(host_home) -> str:
    """上次装的时候写进去的标记块正文指纹。没装过 / 旧清单没记过就是空串（退回包内规则全文判定）。"""
    return str((installed_manifest(host_home).get("entry_file") or {}).get("marker_body_sha256") or "")


def installed_hub_card(host_home) -> str:
    """上次装的标记块正文是不是来自一张中枢内核卡。是就返回卡名，否则空串。"""
    ent = installed_manifest(host_home).get("entry_file") or {}
    return str((ent.get("hub") or {}).get("name") or "")


def classify_marker_block(block_text, body_sha=""):
    """这一块是不是中枢自己写的？顺带数出块里有几行不是我们写的。

    判据（两条都要满足才算「我们的块」）：
      1. BEGIN / END 各自**独占一行**；
      2. 第二行是指针行「本机中枢在 …」。

    为什么必须这么严：主人完全可能在自己的说明文里抄一对
        # >>> hubcore hub >>>
        # <<< hubcore hub <<<
    来写「以后卸载就删这两行之间」。那一对**不是我们的块**，
    装和卸都必须原样留着——动它就是删主人的原文。
    这不是假想：验收实测过，主人抄了这两行之后第一次装就把原文毁了。
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
    # 路线一：装了中枢内核卡 —— 块里的正文是**那张卡**，包里那份 AGENTS.md 当然对不上。
    # 这时认块靠清单里记着的正文指纹（我们自己写进去的，比全文包含判定更硬）。
    if body_sha and marker_body_fingerprint(block_text) == body_sha:
        return True, "", 0
    # 路线二：默认块。规则允许主人在自己的块里加说明，但必须包含本版本完整规则正文，
    # 否则一个“本机中枢在 …”的伪造小块就能骗过卸载器。
    it = iter(body)
    ours = all(any(candidate == want for candidate in it) for want in expected)
    if not ours:
        return False, "规则正文不完整——这不是中枢写的块", 0
    # 指针行（第 2 行）带宿主家目录，逐台机器都不一样，不参与「是不是我们写的」比对。
    # 只比下面 11 块底线正文。
    foreign = sum(1 for l in lines[2:-1] if l and l not in expected_set)
    return True, "", foreign


def find_marker_blocks(text, body_sha=""):
    """找出所有成对标记。返回 [{start,end,ours,why,foreign}]，end 含块后那一个换行。

    body_sha 是安装清单里记着的正文指纹（装了中枢内核卡时靠它认块），空串就只按包内规则全文判。
    """
    blocks = []
    pos = 0
    while True:
        mb = _BEGIN_RE.search(text, pos)
        if not mb:
            return blocks
        me = _END_RE.search(text, mb.end())
        nested = _BEGIN_RE.search(text, mb.end())
        if nested and (me is None or nested.start() < me.start()):
            # 孤立/嵌套 BEGIN 不能吞掉后面的真实块；从内层 BEGIN 重新配对。
            pos = nested.start()
            continue
        if not me:
            pos = mb.end()          # 没有配对的 END：当残块，跳过，不动它
            continue
        start = mb.start()
        if text[start] == "﻿":
            start += 1               # BOM 不属于标记块，摘块时必须留着它
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


def strip_marker(text, body_sha=""):
    """只摘中枢自己写的块。宿主持别的标记行原样保留。

    返回 (剩余文本, 报告dict)：
      removed / kept_foreign / others_kept / foreign_lines / why
    出现多个「我们的块」时**只摘最上面一个**，其余保留并报出来——不许无声无息全删。
    """
    blocks = find_marker_blocks(text, body_sha)
    ours = [b for b in blocks if b["ours"]]
    rep = {"ours_total": len(ours), "removed": 0,
           "kept_foreign": len(blocks) - len(ours), "foreign_lines": 0,
           "others_kept": 0, "why": [b["why"] for b in blocks if not b["ours"]]}
    if not ours:
        return text, rep
    b = ours[0]                      # 只摘最上面那一个
    text = text[:b["start"]] + text[b["end"]:]
    rep["removed"] = 1
    rep["foreign_lines"] = b["foreign"]
    rep["others_kept"] = len(ours) - 1
    return text, rep


BASE_BEGIN = "# >>> hubcore base >>>"
BASE_END = "# <<< hubcore base <<<"

# 底模上限。底模是主人自己整套心智（含越狱框架），按主人实际使用的一整份留余量：
# 主人那份实测 35,775 字节。留到 40,000 装得下且还有改动空间。
# 唯一的理由是"主人要能把自己那份原样装进去"——不是鼓励把底模写大。
# 底模每轮都注入，写大直接吃回标记块省下来的 token；超了先问"能不能砍"，别问"能不能调大"。
BASE_BUDGET = int(os.environ.get("HUBCORE_BASE_BUDGET", "40000"))


def render_base_block(name: str, hosts_note: str, content: str) -> str:
    """底模卡片渲染成入口文件里的块。顺序固定：标记块 / 底模块 / 原文。"""
    head = "底模：" + name + ("（" + hosts_note + "）" if hosts_note else "")
    body = content.strip("\n")
    fingerprint = sha256_bytes(body.encode("utf-8"))
    return "\n".join((BASE_BEGIN, head, "指纹：" + fingerprint, body, BASE_END)) + "\n"


def strip_base_block(text: str):
    """只摘中枢自己写的底模块。返回 (剩余文本, 摘掉个数)。"""
    import re as _re
    b_re = _re.compile(r"^\ufeff?[ \t]*" + _re.escape(BASE_BEGIN) + r"[ \t]*\r?$", _re.M)
    e_re = _re.compile(r"^[ \t]*" + _re.escape(BASE_END) + r"[ \t]*\r?$", _re.M)
    out = text
    removed = 0
    pos = 0
    while True:
        mb = b_re.search(out, pos)
        if not mb:
            break
        me = e_re.search(out, mb.end())
        nested = b_re.search(out, mb.end())
        if nested and (me is None or nested.start() < me.start()):
            pos = nested.start()
            continue
        if not me:
            pos = mb.end()
            continue
        start = mb.start()
        if out[start:start + 1] == "\ufeff":
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


GUEST_BEGIN = "# >>> hubcore guest >>>"
GUEST_END = "# <<< hubcore guest <<<"


def render_guest_block(name: str, content: str) -> str:
    """技能指引卡渲染成入口文件里的块。成品文本原样粘，一个字不改，只套定界。"""
    head = "技能指引：" + name
    body = content.strip("\n")
    fingerprint = sha256_bytes(body.encode("utf-8"))
    return "\n".join((GUEST_BEGIN, head, "指纹：" + fingerprint, body, GUEST_END)) + "\n"


def strip_guest_block(text: str):
    """只摘中枢自己写的技能指引块（第二行须是「技能指引：」）。返回 (剩余文本, 摘掉个数)。"""
    import re as _re
    b_re = _re.compile(r"^\ufeff?[ \t]*" + _re.escape(GUEST_BEGIN) + r"[ \t]*\r?$", _re.M)
    e_re = _re.compile(r"^[ \t]*" + _re.escape(GUEST_END) + r"[ \t]*\r?$", _re.M)
    out = text
    removed = 0
    pos = 0
    while True:
        mb = b_re.search(out, pos)
        if not mb:
            break
        me = e_re.search(out, mb.end())
        nested = b_re.search(out, mb.end())
        if nested and (me is None or nested.start() < me.start()):
            pos = nested.start()
            continue
        if not me:
            pos = mb.end()
            continue
        start = mb.start()
        if out[start:start + 1] == "\ufeff":
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
        if len(nonempty) < 2 or not nonempty[0][1].startswith("技能指引：") \
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


def insert_marker(text: str, host_home="", base_block="", guest_block="",
                  with_marker: bool = True, marker_block_text: str = "",
                  keep_origin: bool = True, strip_body_sha: str = "") -> str:
    """先摘掉中枢自己写的旧块（标记块 + 底模块 + 指引块）再插新块，重复安装幂等。
    宿主的原文一个字不动；keep_origin=False 走覆盖模式，整段丢掉（丢的那份在 .backups/ 里）。

    顺序是刻意选的：**标记块永远写最后**（原文 / 底模块 / 指引块 / 标记块）。
    底模是主人随时会换的一整套心智，指引块是别人的成品——两者都可能自带一套
    「以我为准」的措辞。标记块写最后，它就是入口文件里的最后一段定论，
    与主人换哪张底模、哪张指引卡无关（这是「和任何底模兼容」的实现方式，
    不靠往标记块里加字——它 1,200 B 已经打满，一字节余量都没有）。
    摘块仍按位置无关的逐块扫描，所以顺序变了不影响幂等与「装完再卸完逐字节相同」。

    with_marker=False 时只写底模与指引两段（三段都可以单独选）。

    marker_block() 本身已经以换行结尾，strip_marker() 又正好吃掉标记块后面那一个换行，
    所以这里**只能直接拼接**：多补一个换行、或把原文开头的空行 lstrip 掉，
    都会让「装完再卸完」和原文差一个字节——实测就是这么发现的。

    ⚠️ 但下面那个「补换行」的循环是**有代价的**，别当成无害的排版处理：
    它给主人的原文补出来的那个换行是**我们加的**，strip_marker() 不认识它
    （「abc」+\"\\n\"+块 与 「abc\\n」+块 装完字节完全一样，光看文件分辨不出来）。
    所以 install.py 把「备份原文是否以换行收尾」记进清单的 entry_file.origin_ends_with_nl，
    uninstall.py 的 same_as_origin() 据此把这个换行认出来并还原。
    两边必须一起改：只改一边，就是「装完再卸完多一个字节，且被误报成主人自己改过」。
    """
    # strip_body_sha：上一次装进去的那块（可能装了中枢内核卡）的正文指纹，
    # 不传的话重装会把旧块当成「主人自己抄的标记行」留在文件里，越装越多。
    stripped, _ = strip_marker(text, strip_body_sha)
    stripped, _ = strip_base_block(stripped)
    stripped, _ = strip_guest_block(stripped)
    # with_marker=False 就是「这次不写中枢段」：调用方哪怕把中枢卡正文递进来，也不许落笔。
    block = marker_block_text if (with_marker and marker_block_text) \
        else (marker_block(host_home) if with_marker else "")
    # keep_origin=False = 覆盖模式：宿主原有文本整段丢弃，只留我们写的三段。
    # 原有那份很可能本身也是一套中枢规则，留着就是两套规则打架。
    # 丢弃的内容在装前的 hub/.backups/ 里逐字节存着，卸回时按清单的 origin_dropped 合并还原。
    head = stripped if keep_origin else ""
    parts = [p for p in (head, base_block, guest_block) if p]
    if block:
        # 标记块在最末，但它自己以换行结尾；前面任何一段若不以换行收尾就补一个，
        # 否则两段会粘成一行（摘块按行锚点匹配，粘行会让下一次卸不干净）。
        for i, p in enumerate(parts):
            if not p.endswith("\n"):
                parts[i] = p + "\n"
        parts.append(block)
    elif not parts:
        return stripped
    return "".join(parts)


def has_marker(text: str, body_sha: str = "") -> bool:
    """有没有中枢自己写的块。宿主持别的标记行不算。"""
    return any(b["ours"] for b in find_marker_blocks(text, body_sha))


def extract_marker_block(text: str, body_sha: str = ""):
    """取第一块「中枢自己写的」标记块的原文（verify 检查项 d 用）。没有则 None。"""
    for b in find_marker_blocks(text, body_sha):
        if b["ours"]:
            return text[b["start"]:b["end"]].rstrip("\r\n")
    return None


# ---------------------------------------------------------------- 清单

def manifest_path(pkg_root):
    return Path(pkg_root) / MANIFEST_NAME


def read_manifest(pkg_root: Path) -> dict:
    p = manifest_path(pkg_root)
    if not p.is_file():
        raise SystemExit("读不到安装清单：%s\n  这个目录不是装好的 hubcore，或已被卸载。" % p)
    return json.loads(p.read_text(encoding="utf-8"))


def write_manifest(pkg_root: Path, data: dict) -> None:
    atomic_write_text(manifest_path(pkg_root),
                      json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def list_package_files(pkg_root: Path):
    """包内全部受管文件（相对包根、正斜杠）。排除清单自身、备份、缓存、状态目录。"""
    pkg_root = Path(pkg_root)
    skip_dirs = {BACKUP_DIRNAME, "__pycache__", STATE_DIRNAME}
    out = []
    for path in sorted(pkg_root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(pkg_root)
        if rel.parts and rel.parts[0] in skip_dirs:
            continue
        if rel.as_posix() == MANIFEST_NAME:
            continue
        out.append(rel.as_posix())
    return out


def file_rows(pkg_root: Path):
    """清单里 files 段用的逐文件 sha 记录。"""
    pkg_root = Path(pkg_root)
    rows = []
    for rel in list_package_files(pkg_root):
        f = pkg_root / rel
        rows.append({"path": rel, "sha256": sha256_file(f), "bytes": f.stat().st_size})
    return rows


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + "Z"


def stamp() -> str:
    return time.strftime("%Y%m%d-%H%M%S", time.localtime()) + "-" + uuid.uuid4().hex[:10]


# ---------------------------------------------------------------- 引用分类

# 这些引用指向「主人那个产品目录里的东西」，不是包内文件。
# 账本 .hub/、原话流水 OWNER-SPEECH.md 这类，跑产品时才会被写出来。
PRODUCT_SIDE_REFS = frozenset({
    "CHANGES.md", "OWNER-SPEECH.md", "OWNER-STOPS.md", "WORK-HANDOFF.md",
    "FEATURES.md", "MAP.md", "STATUS.md", "SOURCE.md", "SURVIVOR.md",
    "EXPERIMENTS.jsonl", "PROJECT-MEMORY.jsonl", "TOOLING.md",
    "dropped.json", "resume.json", "physical-gates.json",
    "tools.json", "tools.local.json", "setup_device.py",
    "templates/memory-tree/CHANGES.md",
    "TEMP/", "work/vX", "TEMP",
})

# 本机/开发侧的东西：工具表、工具说明、以及素材的生成脚本本身。
# SKILL.md = 客人总控入口（随客人装，不随本包走）：包内正文提到它是指路，不是包内文件指针，故豁免。
HOST_LOCAL_REFS = frozenset({"TOOLING.md", "tools.json", "tools.local.json",
                            "build_hubcore.py", "SKILL.md"})

# 闸门自身的规则表：里面必然写着禁词本身。按打包判决这些不进包，
# 正常情况下一条都命中不到；留着是为了万一有人手工拷进包时能明着报出来。
GATE_FILES = frozenset({META_NAME})

# 只有这几个前缀下的引用才算「包内文件指针」，必须解析得到。
PACKAGE_PREFIXES = ("workflows/", "docs/", "templates/", "tools/", "ctxiso/")

_PATHISH = re.compile(r"^[A-Za-z0-9_.<][A-Za-z0-9_.<>/-]*\.(md|py|json|jsonl|mdc)$")
_BACKTICK = re.compile(r"`([^`\n]+?)`")


def iter_refs(text: str):
    """抽出正文里像文件路径的反引号引用。返回 [(raw_ref, line_no)]。"""
    for line_no, line in enumerate(text.splitlines(), 1):
        for raw in _BACKTICK.findall(line):
            ref = raw.strip()
            if _PATHISH.match(ref) or ref.endswith("/"):
                yield ref, line_no


def classify_ref(ref: str):
    """package=必须在包内解析 / product=产品侧 / host=本机侧 /
    dirref=目录约定 / placeholder=含占位符 / self=指回中枢根自己。"""
    if "<" in ref or ">" in ref:
        return "placeholder", "含占位符，不指向具体文件"
    if "..." in ref:
        return "placeholder", "省略号写法，不指向具体文件"
    if ref in PRODUCT_SIDE_REFS or ref.startswith(".hub/"):
        return "product", "产品目录里跑出来的东西，不随包走"
    if ref in HOST_LOCAL_REFS:
        return "host", "本机/开发侧的工具表或生成脚本，不随包走"
    if ref.rstrip("/") == PKG_DIRNAME:
        return "self", "指回中枢根自己，装好后就是 <宿主家目录>/hub/"
    if ref.endswith("/") and not ref.startswith(PACKAGE_PREFIXES):
        return "dirref", "目录约定，不是包内文件指针"
    return "package", "必须在包内解析到实际文件"


def scan_refs(pkg_root: Path):
    """扫包内每个文件里的相对引用。返回 [{file,line,ref,ok}]。

    FIX-20：读不出 / 非 UTF-8 的文件原来直接 `continue` —— 它既没被扫，
    也不在任何一份报告里，等于凭空消失。现在记成一条 `ok=None` 的条目，
    由调用方当**盲区**处理：既不算「通过」，也不谎称「死链」。
    """
    pkg_root = Path(pkg_root)
    text_exts = {".md", ".json", ".jsonl", ".py"}
    hits = []
    for rel in list_package_files(pkg_root):
        p = pkg_root / rel
        if p.suffix.lower() not in text_exts:
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            hits.append({"file": rel, "line": 0, "ref": "",
                         "ok": None, "why": "读不出，未扫描引用: %s" % type(e).__name__})
            continue
        for ref, line_no in iter_refs(text):
            kind, why = classify_ref(ref)
            if kind != "package":
                continue
            # 先按包根解；再按所在文件所在目录解（`../docs/...` 这类）
            here = (pkg_root / rel).parent
            cands = (pkg_root / ref, here / ref)
            hits.append({"file": rel, "line": line_no, "ref": ref,
                         "ok": any(c.is_file() or c.is_dir() for c in cands)})
    return hits


# ---------------------------------------------------------------- 自检用产品夹

def make_product_fixture(root: Path) -> Path:
    """造一个最小产品夹，让侧车真的有账本可体检。永远造在临时目录里。"""
    prod = Path(root) / "demo-product"
    hub = prod / ".hub"
    hub.mkdir(parents=True, exist_ok=True)
    events = [
        {"kind": "confirm", "phase_id": "1-access", "quote": "可以", "n": 1},
        {"kind": "record", "phase_id": "1-access", "record_kind": "spec", "n": 2},
    ]
    with open(hub / "ledger.jsonl", "w", encoding="utf-8") as fh:
        for e in events:
            fh.write(json.dumps(e, ensure_ascii=False) + "\n")
    (prod / "OWNER-SPEECH.md").write_text("# 原话\n一句一收。\n", encoding="utf-8")
    (prod / "CHANGES.md").write_text("# 改动图\n", encoding="utf-8")
    return prod


def run_child(argv, cwd, env=None):
    """跑一次子进程，stdio 直接继承。返回退出码。"""
    print("        $ " + " ".join(str(a) for a in argv))
    sys.stdout.flush()
    return subprocess.call([str(a) for a in argv], cwd=str(cwd), env=env)


def child_env(pkg_root: Path):
    env = dict(os.environ)
    env["PYTHONPATH"] = str(pkg_root) + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONIOENCODING"] = "utf-8"
    # 装出来的包里不该出现 .pyc（.pyc 头里的 co_filename 记着编译时的绝对源码路径）。
    # 这里的子进程也别再写一份出来。
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.pop("CTXISO_OFF", None)
    return env


def find_bytecode(root):
    """产物里不该存在的字节码。返回 [路径]。"""
    root = Path(root)
    return [p for p in root.rglob("*")
            if p.name == "__pycache__" or p.suffix in (".pyc", ".pyo")]


def purge_bytecode(root) -> int:
    n = 0
    for p in find_bytecode(root):
        if p.is_dir():
            rmtree_quiet(p)
            n += 1
        elif p.is_file():
            p.unlink()
            n += 1
    return n


# ---------------------------------------------------------------- 出货内容红线

# 装出来就不许再出现的字符串。pack.py 出厂前扫一遍，verify.py 装完再扫一遍，用同一张表。
FORBIDDEN = (
    "D:\\", "D:/", "临时项目", "context-isolation",
    "hub-dock", "github.com", "http://", "https://", "git@",
    "user-skills", ".agents/skills", ".agents\\skills", "skills-hub", "gthubtom1",
    "hub-lean",
)
# 127.0.0.1 是环回。抓包方法书里指的是本机 mitmproxy，不是远端地址。
LOOPBACK_ALLOWED = ("127.0.0.1", "localhost")

# 显式白名单：**有名有姓、有原因**。只放「不含任何路径与远端地址、且改了会改坏行为」的字面量。
# 新增任何一条都必须在这里显式登记并写清 why；为了让检查变绿而放宽规则，跟藏 bug 一样。
ALLOWLIST = (
    {
        "file": "tools/hub_ask.py",
        "word": "hub-lean",
        "why": "中枢自测环境检测 _is_hub_selftest() 的 5 个匹配字面量之一，"
               "与另外 4 个（hub-gold- / hub-field-tests / \\gold- / /gold-）成套。"
               "它不含任何路径或远端地址；改这个字面量会改坏「当前是不是中枢自测环境」的判定。",
    },
)

_ALLOW_KEYS = {(a["file"], a["word"]): a for a in ALLOWLIST}


def _only_loopback(line: str) -> bool:
    """这一行除了环回地址和标点，没有别的网址。"""
    rest = line
    for word in ("http://", "https://"):
        rest = rest.replace(word, "")
    for host in LOOPBACK_ALLOWED:
        rest = rest.replace(host, "")
    for ch in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-._:/\\ \t":
        rest = rest.replace(ch, "")
    return not rest


def scan_forbidden(pkg_root: Path, forbidden=None, allowlist=None):
    """扫包内每个文件的每一行。

    返回 (fails, allowlisted)：
      fails       = [(rel, lineno, word, line)]，任何非白名单命中都算红
      allowlisted = [(rel, lineno, word, line, why)]，白名单命中，逐条带原因
    两种结果分开报，不混成一句「全绿」。
    """
    forbidden = tuple(forbidden or FORBIDDEN)
    allow_keys = {(a["file"], a["word"]): a for a in (allowlist or ALLOWLIST)}
    fails, allowed, skipped = [], [], []
    for rel in list_package_files(pkg_root):
        p = Path(pkg_root) / rel
        if rel in GATE_FILES:
            skipped.append(rel)
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            # A file we cannot decode was NOT scanned for forbidden words. Counting it
            # as clean made the "N files, zero forbidden words" denominator a lie
            # (DESIGN-RULES rule 12: anything counted must also be judged). Record it
            # as skipped so the caller subtracts it from the denominator.
            skipped.append("%s  (不可读，未扫描禁词: %s)" % (rel, type(e).__name__))
            continue
        for line_no, line in enumerate(text.splitlines(), 1):
            for word in forbidden:
                if word not in line:
                    continue
                if word in ("http://", "https://") and _only_loopback(line):
                    continue
                entry = allow_keys.get((rel, word))
                row = (rel, line_no, word, line.strip()[:150])
                if entry:
                    allowed.append(row + (entry["why"],))
                else:
                    fails.append(row)
    return fails, allowed, skipped


