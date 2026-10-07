"""极简本地控制台服务。只用标准库，只绑 127.0.0.1。

四个接口，一个页面：列出智能体、载入、卸载、看状态。
没有任何技能、副插件、AI 接口、授权、云端相关的东西。
"""

from __future__ import annotations

import hashlib
import hmac
import json
import mimetypes
import os
import re
import secrets
import socket
import subprocess
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import bundle_locator
import hosts as hosts_mod
import safebox as safebox_mod

__version__ = "0.1.0"

BOM = b"\xef\xbb\xbf"
WEB_DIR = Path(__file__).resolve().parent / "web"
# 卡片正文上限，和打包器 03-bundle/_bundle_lib.py 的 BASE_BUDGET 同一个数。
# 在这里就拦：页面存的时候给一句人话，别等装的时候才失败。
# 卡片正文上限，和打包器 03-bundle/_bundle_lib.py 的 BASE_BUDGET 同一个数——
# 那边是权威（装了会拦），这里只是提前给一句人话。两边读同一个环境变量，改一处就够。
CARD_MAX_BYTES = int(os.environ.get("HUBCORE_BASE_BUDGET", "40000"))
LOOPBACK = frozenset({"127.0.0.1", "::1", "::ffff:127.0.0.1"})
BIND_HOST = "127.0.0.1"
TOKEN = secrets.token_urlsafe(24)

_MAX_BODY = 64 * 1024
_mutate_lock = threading.Lock()

# 只有这三个静态文件会发出去。不做目录遍历，不发别的东西。
_STATIC = {
    "/": "index.html",
    "/index.html": "index.html",
    "/app.js": "app.js",
    "/style.css": "style.css",
}
_MIME = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
}


# ---------------------------------------------------------------- 外发防护

def _is_loopback_url(url: str) -> bool:
    try:
        parts = urllib.parse.urlsplit(url)
    except ValueError:
        return False
    if parts.scheme not in ("http", "https"):
        return False
    host = (parts.hostname or "").strip("[]").lower()
    if host in LOOPBACK:
        return True
    return host in ("localhost", "ip6-localhost")


def _carries_credentials(url: str) -> bool:
    parts = urllib.parse.urlsplit(url)
    if parts.username or parts.password:
        return True
    return "@" in (parts.netloc or "").split("]")[-1]


class _NoCredentialRedirect(urllib.request.HTTPRedirectHandler):
    """带凭据的跳转一律拒绝，目标不在环回也拒绝。控制台不跟随任何跳转。"""

    max_redirections = 0

    @staticmethod
    def _deny(newurl: str, code: int, headers, fp):
        raise urllib.error.HTTPError(newurl, code, "控制台不跟随跳转", headers, fp)

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102
        if _carries_credentials(newurl) or getattr(req, "headers", None):
            raise urllib.error.HTTPError(newurl, code, "拒绝带凭据跟随跳转", headers, fp)
        if not _is_loopback_url(newurl):
            self._deny(newurl, code, headers, fp)
        self._deny(newurl, code, headers, fp)

    def _http_error_30x(self, req, fp, code, msg, headers):
        # 不解析 Location 就先停，省掉一次对外解析。
        self._deny(str(getattr(req, "full_url", "")), code, headers, fp)

    http_error_301 = _http_error_30x
    http_error_302 = _http_error_30x
    http_error_303 = _http_error_30x
    http_error_307 = _http_error_30x
    http_error_308 = _http_error_30x


# 全进程唯一的出网口子。装上这个 handler 之后，任何 urllib 调用都出不去环回。
# 控制台本身没有出网需求；这里是给它留的死闸：将来谁加代码也过不去。
LOOPBACK_OPENER = urllib.request.build_opener(_NoCredentialRedirect)


def safe_open(url: str, timeout: float = 5.0):
    """唯一允许的取数入口。目标不在环回直接拒绝，连解析都不往下走。"""
    if not _is_loopback_url(url):
        raise urllib.error.URLError("只允许环回地址")
    return LOOPBACK_OPENER.open(url, timeout=timeout)


# ---------------------------------------------------------------- 响应工具

def _safe_public(text: str, fallback: str) -> str:
    """错误文案不许带盘符路径、traceback、仓库名。"""
    clean = " ".join(str(text or "").split())
    bad = (":\\", ":/", "\\\\", "Traceback", "hub-dock", "临时项目", "context-isolation")
    if not clean or any(mark in clean for mark in bad):
        return fallback
    return clean[:400]


def _write(handler: BaseHTTPRequestHandler, raw: bytes) -> bool:
    """客户端半路走了（刷新页面、关标签）不该在终端甩一屏 traceback。"""
    try:
        handler.wfile.write(raw)
        return True
    except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
        return False


def _send_json(handler: BaseHTTPRequestHandler, code: int, payload: dict) -> None:
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    try:
        handler.send_response(code)
        handler.send_header("Content-Type", "application/json; charset=utf-8")
        handler.send_header("Content-Length", str(len(raw)))
        handler.send_header("Cache-Control", "no-store")
        handler.send_header("X-Content-Type-Options", "nosniff")
        handler.send_header("Referrer-Policy", "no-referrer")
        handler.end_headers()
    except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
        return
    _write(handler, raw)


COOKIE_NAME = "hubtok"


def _token_from_cookie(handler: BaseHTTPRequestHandler) -> str:
    raw = handler.headers.get("Cookie") or ""
    for part in raw.split(";"):
        name, _, value = part.strip().partition("=")
        if name == COOKIE_NAME:
            return value.strip()
    return ""


def _send_file(handler: BaseHTTPRequestHandler, name: str, *, set_cookie: bool = False) -> None:
    target = (WEB_DIR / name).resolve()
    if WEB_DIR.resolve() not in target.parents or not target.is_file():
        handler.send_error(404, "Not Found")
        return
    raw = target.read_bytes()
    mime = _MIME.get(target.suffix) or mimetypes.guess_type(target.name)[0] or "application/octet-stream"
    try:
        handler.send_response(200)
        handler.send_header("Content-Type", mime)
        handler.send_header("Content-Length", str(len(raw)))
        handler.send_header("Cache-Control", "no-store")
        handler.send_header("X-Content-Type-Options", "nosniff")
        handler.send_header("Referrer-Policy", "no-referrer")
        if set_cookie:
            # 会话 Cookie：关掉浏览器就没了；服务重启令牌变了它也自动失效。
            # 这样页面地址干净到只剩端口，主人不用带 ?t=… 后缀。
            handler.send_header(
                "Set-Cookie", f"{COOKIE_NAME}={TOKEN}; Path=/; SameSite=Strict; HttpOnly"
            )
        handler.send_header(
            "Content-Security-Policy",
            "default-src 'none'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; base-uri 'none'; form-action 'none'",
        )
        handler.end_headers()
    except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
        return
    _write(handler, raw)


# ---------------------------------------------------------------- 业务动作

def _step(name: str, ok: bool, detail: str = "") -> dict:
    return {"name": name, "ok": bool(ok), "detail": detail}


def _package_info() -> dict:
    return bundle_locator.readiness()


# ---------------------------------------------------------------- 底模卡片
# 卡片只活在控制台自己的 cards/ 里，永不进包（包的禁词门见了路径与技能字样就红）。
# 安装器只收一个卡片文件路径；卡片内容是主人自己写的，控制台只验格式不审内容。

def is_valid_card_name(name: str) -> bool:
    r"""放开卡名限制：支持任何中英文、符号、括号、中括号、加号、点号。
    仅拦截真实的 Windows 非法文件名字符(\ / : * ? " < > |)、控制字符与路径穿越(..)。
    """
    if not name or not isinstance(name, str) or len(name) > 80:
        return False
    invalid_chars = set('\\/:*?"<>|\0\r\n')
    if any(c in invalid_chars or ord(c) < 32 for c in name):
        return False
    if ".." in name:
        return False
    stem = name.split(".")[0].upper()
    reserved = {"CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4",
                "COM5", "COM6", "COM7", "COM8", "COM9", "LPT1", "LPT2",
                "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"}
    if stem in reserved:
        return False
    return True

CARDS_DIR = Path(__file__).resolve().parent / "cards"
# 卡片池按层分家。每个槽位只读自己那一个子夹：
#   hub/   中枢内核卡      base/  底模卡      guest/  客套指引卡
# 池子外面的（cards/ 根、_park/、_archive/、_pending/）一个字都不读 ——
# 不想用的卡「挪出子夹」就等于停用，卡不丢，想用了挪回来就恢复。
CARD_POOLS = ("hub", "base", "guest")


def _pool_dir(kind: str) -> Path:
    return CARDS_DIR / kind


def _pool_of(path: Path) -> str:
    """这张卡躺在哪个池子里。不在三个池子里的返回空串。"""
    try:
        rel = path.resolve().relative_to(CARDS_DIR.resolve())
    except (OSError, ValueError):
        return ""
    if len(rel.parts) == 2 and rel.parts[0] in CARD_POOLS:
        return rel.parts[0]
    return ""


def _card_path(card_id: str, kind: str = "") -> Path | None:
    """卡片 id 就是文件名（不带 .md）。指名了哪一层就先找哪一层，再按三个池子找。
    只认三个池子：根目录和 _park/ 里的卡等于停用。越界的一律当没有，绝不跟出去。"""
    if not is_valid_card_name(card_id):
        return None
    order = ([kind] if kind in CARD_POOLS else []) + [k for k in CARD_POOLS if k != kind]
    for k in order:
        pool = _pool_dir(k)
        cand = (pool / (card_id + ".md")).resolve()
        if pool.resolve() in cand.parents and cand.is_file():
            return cand
    return None


def parked_cards() -> int:
    """池子外面停着多少张卡（cards/ 根 + _park/ 的 .md）。页面拿它提示「那些没在读」。"""
    if not CARDS_DIR.is_dir():
        return 0
    n = sum(1 for _ in CARDS_DIR.glob("*.md"))
    park = CARDS_DIR / "_park"
    if park.is_dir():
        n += sum(1 for _ in park.glob("*.md"))
    return n


def _card_body(text: str, stem: str = "") -> str:
    """卡片正文：整个文件原样返回，一个字不改、不剥头、不裁段。

    卡片没有格式要求。底模 / 指引 / 中枢三层一视同仁：文件里是什么，
    注进上下文的就是什么。手写的成品提示词、你粘进来的别人的提示词、
    没有任何结构的纯文本 —— 一律原样用。

    stem 参数只为兼容旧调用，读的这套逻辑已经用不到它。
    """
    return str(text or "").strip("\n")


def _parse_card(text: str, stem: str = "") -> dict:
    """只统计，不判断。这张卡没有「格式对不对」这回事。"""
    body = _card_body(text, stem)
    preview = ""
    for line in body.splitlines():
        text_line = line.strip()
        if text_line:
            preview = text_line[:60]
            break
    return {"name": stem, "kind": "base", "hosts": "", "chars": len(body),
            "preview": preview, "bytes": len(body.encode("utf-8"))}


def _meta_path(kind: str) -> Path:
    return _pool_dir(kind) / "_meta.json"


def _read_meta(kind: str) -> dict:
    """卡片自己的元数据（目前只有 hosts 备注）。读不出来就当没有 —— 元数据
    丢了不影响卡片本身能不能用。"""
    try:
        data = json.loads(_meta_path(kind).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_meta(kind: str, meta: dict) -> None:
    try:
        _meta_path(kind).write_bytes(
            json.dumps(meta, ensure_ascii=False, indent=1).encode("utf-8"))
    except OSError:
        pass


def list_cards() -> list[dict]:
    """只扫 hub/ base/ guest/ 三个池子，放哪个池子就是哪一层的卡（池子说了算）。
    根目录、_park/、_archive/、_pending/ 是停车位：挪出去＝停用，挪回来＝启用。"""
    rows = []
    for kind in CARD_POOLS:
        pool = _pool_dir(kind)
        if not pool.is_dir():
            continue
        meta = _read_meta(kind)
        for p in sorted(pool.glob("*.md")):
            try:
                info = _parse_card(p.read_text(encoding="utf-8"), p.stem)
            except (OSError, ValueError):
                # ValueError 含 UnicodeDecodeError：一张手放的 GBK 卡就能让整页瘫掉
                continue
            info["id"] = p.stem
            # 层只看它躺在哪个池子里，卡片自己声明什么都不算。
            info["kind"] = kind
            info["declared"] = ""
            info["hosts"] = str(meta.get(p.stem) or "")[:200]
            rows.append(info)
    return rows


def read_card(card_id: str, kind: str = "") -> dict:
    """看卡/改卡：回正文全文。只在主人点名要的时候给，不进 /api/status。

    没有格式检查：文件能读出来就给你，一字不改。"""
    target = _card_path(card_id, kind)
    if target is None:
        return {"ok": False, "error": "没有这张卡。"}
    try:
        body = _card_body(target.read_text(encoding="utf-8"), target.stem)
    except (OSError, ValueError):
        return {"ok": False, "error": "这张卡读不出来（文件不是 UTF-8 文本？）。"}
    pool = _pool_of(target)
    return {"ok": True, "id": target.stem, "kind": pool, "declared": "",
            "bytes": len(body.encode("utf-8")),
            "hosts": str(_read_meta(pool).get(target.stem) or "")[:200],
            "content": body}


def _delimiter_in(text: str) -> str:
    """正文里有没有整行等于中枢的定界行。

    定界行是中枢标记块的护栏。别人的成品提示词里出现它，卸回就会把那一段
    当成“我们的块”只截一半，卡片的后半截留在主人的原文里当指令被读。
    """
    marks = ("# >>> hubcore hub >>>", "# <<< hubcore hub <<<",
             "# >>> hubcore base >>>", "# <<< hubcore base <<<",
             "# >>> hubcore guest >>>", "# <<< hubcore guest <<<")
    for line in str(text or "").splitlines():
        if line.strip() in marks:
            return line.strip()
    return ""


def save_card(name: str, hosts_note: str, content: str, kind: str = "base") -> dict:
    name = (name.strip() if isinstance(name, str) else "")
    hosts_note = (hosts_note.strip()[:200].replace("\r", " ").replace("\n", " ")
                  if isinstance(hosts_note, str) else "")
    content = (content.strip("\n") if isinstance(content, str) else "")
    kind = kind if kind in ("base", "guest", "hub") else "base"
    if not is_valid_card_name(name):
        return {"ok": False, "error": "卡名不能含 \\ / : * ? \" < > | 等非法字符，80字内。"}
    if not content:
        return {"ok": False, "error": "正文是空的，不存。"}
    if "\x00" in content:
        return {"ok": False, "error": "正文含 NUL 字节，不存。"}
    # 不拦正文内容：NUL 和大小这两条留着的理由不是格式，是「空卡没意义」
    # 和「每轮都注入，太大拖上下文」。除此之外正文一个字都不审。
    size = len(content.encode("utf-8"))
    if size > CARD_MAX_BYTES:
        return {"ok": False, "error": "正文 %d 字节，超过上限 %d 字节（每轮都注入，"
                "太大拖上下文），拆小再存。" % (size, CARD_MAX_BYTES)}
    pool = _pool_dir(kind)
    pool.mkdir(parents=True, exist_ok=True)
    target = (pool / (name + ".md")).resolve()
    if pool.resolve() not in target.parents:
        return {"ok": False, "error": "卡名不合法。"}
    # 别的池子里有同名卡：两边同名会让「用这张」指不准，先拦住。
    clash = [k for k in CARD_POOLS if k != kind and (_pool_dir(k) / (name + ".md")).is_file()]
    if clash:
        return {"ok": False, "error": "同名的卡已经在 %s/ 里了。两个池子同名会指不准，"
                                      "先把那张挪走或改个名字。" % clash[0]}
    existed = target.is_file()
    # 落盘的是你给的原文，不注入任何卡头。哪一层由池子说了算（用 kind），
    # hosts 备注存进 _meta.json，都不混进正文。
    #
    # 存卡片必须 binary 写，且正文先归一到 LF。write_text() 在 Windows 上
    # 会把每个 \n 翻成 \r\n —— 正文里本来就有的 \r\n 于是变成 \r\r\n，
    # 每个空行多一个换行。实测：35,775 字节的底模存完再装，空行全部翻倍，
    # 「原样存、一个字不改」当场不成立。
    target.write_bytes((content.replace("\r\n", "\n").replace("\r", "\n") + "\n")
                       .encode("utf-8"))
    meta = _read_meta(kind)
    if hosts_note:
        meta[name] = hosts_note
    else:
        meta.pop(name, None)
    _write_meta(kind, meta)
    return {"ok": True, "id": name, "kind": kind, "existed": existed}


def delete_card(card_id: str, kind: str = "") -> dict:
    target = _card_path(card_id, kind)
    if target is None:
        return {"ok": False, "error": "没有这张卡。"}
    pool = _pool_of(target)
    target.unlink()
    meta = _read_meta(pool)
    if meta.pop(card_id, None) is not None:
        _write_meta(pool, meta)
    return {"ok": True, "id": card_id, "kind": pool}


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    import tempfile
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


def _entry_file(row: dict) -> Path:
    return Path(row["home"]) / (row.get("entry") or "AGENTS.md")


def _direct_text(base_id: str, guest_id: str, hub_id: str):
    """直写：按顺序把选中的几层拼成一份文本 —— 底模 → 指引 → 中枢。

    没别的：不写定界标记、不种 hub/ 树、不记清单。写进去的就是你选的那几层，
    顺序就是页面上那一列的顺序（底模在最上，中枢在最下）。
    """
    parts, names = [], []
    for kind, cid, label in (("base", base_id, "底模"),
                             ("guest", guest_id, "指引"),
                             ("hub", hub_id, "中枢")):
        if not cid:
            continue
        card = _card_path(cid, kind)
        if card is None:
            return "", [], "没有这张卡：%s/ 子夹里没有「%s」" % (kind, cid)
        try:
            raw = card.read_text(encoding="utf-8")
        except OSError:
            return "", [], "这张卡读不出来：%s" % cid
        # 不做任何格式判断：文件读得出来就整段拼进去，一个字不改。
        parts.append("# ==================== %s：%s ====================\n%s\n"
                     % (label, cid, _card_body(raw, card.stem)))
        names.append("%s %s" % (label, cid))
    return "".join(parts), names, ""


def _safebox_gate(host_id: str, row: dict):
    """写之前先把这一家的入口文件保底。返回 (steps, error)。"""
    steps = []
    if row.get("fixture"):
        return steps, ""
    kept = safebox_mod.latest(host_id)
    if kept is not None:
        steps.append(_step("保险箱", True, "已经有一份备份（%s），不覆盖" % safebox_mod._split(kept.name)[1]))
        return steps, ""
    backup = safebox_mod.take(host_id)
    if not backup.get("ok"):
        steps.append(_step("保险箱", False, str(backup.get("error") or "没做成")))
        return steps, "备份没做成，这次不写。按上面那行原因处理后再来。"
    steps.append(_step("保险箱", True, str(backup.get("say") or "")[:90]))
    return steps, ""


def _do_load_direct(host_id: str, row: dict, base_id: str, guest_id: str, hub_id: str,
                    steps: list) -> dict:
    """直写：拼好 → 整份替换入口文件。原来的内容清空（原字节已进保险箱）。"""
    text, names, err = _direct_text(base_id, guest_id, hub_id)
    if err:
        steps.append(_step("拼文本", False, err))
        return {"ok": False, "host_id": host_id, "mode": "direct", "steps": steps, "error": err}
    if not text:
        steps.append(_step("拼文本", False, "一层都没选"))
        return {"ok": False, "host_id": host_id, "mode": "direct", "steps": steps,
                "error": "一层都没选，没东西可写。先把要写的层打开、选一张卡。"}
    steps.append(_step("拼文本", True, " → ".join(names)))
    gate, gate_err = _safebox_gate(host_id, row)
    steps.extend(gate)
    if gate_err:
        return {"ok": False, "host_id": host_id, "mode": "direct", "steps": steps, "error": gate_err}
    entry = _entry_file(row)
    before = entry.read_bytes() if entry.is_file() else b""
    bom = before.startswith(BOM)
    body = (BOM if bom else b"") + text.encode("utf-8")
    try:
        _atomic_write_bytes(entry, body)
    except OSError as exc:
        steps.append(_step("替换入口文件", False, "写不进去：%s" % exc))
        return {"ok": False, "host_id": host_id, "mode": "direct", "steps": steps,
                "error": "写不进去：%s。原文件没动。" % exc}
    after = entry.read_bytes()
    ok = after == body
    steps.append(_step("替换入口文件", ok, "%s：%d → %d 字节%s"
                       % (entry.name, len(before), len(after),
                          "（原来是空的，这次新建）" if not before else "（原来那份已存进保险箱）")))
    return {"ok": ok, "host_id": host_id, "mode": "direct", "steps": steps,
            "error": "" if ok else "写完了但字节对不上，先别用这一家。",
            "entry": str(entry), "bytes": len(after),
            "say": "写好了：%s → %s（%d 字节）" % (" + ".join(names), entry.name, len(after))}


def do_load(host_id: str, base_id: str = "", guest_id: str = "", hub_id: str = "",
            with_marker: bool = True, replace_origin: bool = False,
            mode: str = "install") -> dict:
    """把勾好的几段写进这一家的入口文件。

    replace_origin=True 走覆盖模式：入口文件里原本的文字整段丢弃（原字节由打包器存进
    hub/.backups/，卸回时合并还原）。**页面默认送 true**（宿主原文那颗开关默认开着）；
    这里的缺省 false 是给自测和命令行留的保守值——不显式说，就不动主人的原文。
    """
    steps: list[dict] = []
    row = hosts_mod.get_host(host_id)
    if row is None:
        return {"ok": False, "host_id": host_id, "steps": steps, "error": "没有这家智能体。"}
    if row["running"]:
        steps.append(_step("检查运行态", False, "运行中，不准盖"))
        return {"ok": False, "host_id": host_id, "steps": steps, "error": "运行中，不准盖。"}
    if not row["running_known"]:
        steps.append(_step("检查运行态", False, "运行状态读不到，先关掉这家再试"))
        return {"ok": False, "host_id": host_id, "steps": steps, "error": "运行状态读不到，先关掉这家再试。"}
    steps.append(_step("检查运行态", True, "空闲"))

    if mode != "direct":
        # 直写不叫打包器（它只是拼文本 + 整份替换），所以这一道门对它不适用。
        ready = _package_info()
        if not ready["ready"]:
            steps.append(_step("定位打包器", False,
                               f"{bundle_locator.NOT_READY}：缺 {'、'.join(ready['missing'])}"))
            return {"ok": False, "host_id": host_id, "steps": steps,
                    "error": f"{bundle_locator.NOT_READY}。"}
        steps.append(_step("定位打包器", True, ready["bundle_dir"]))

    if not row["exists"]:
        try:
            home_path = Path(row["home"]).expanduser().resolve()
            if home_path.parent.is_dir():
                home_path.mkdir(parents=True, exist_ok=True)
                row["exists"] = True
                steps.append(_step("准备家目录", True, f"自动创建宿主家目录：{home_path}"))
            else:
                steps.append(_step("检查家目录", False, f"{row['home']} 不在"))
                return {"ok": False, "host_id": host_id, "steps": steps, "error": "这家智能体还没装过，没有家目录可写。"}
        except OSError:
            steps.append(_step("检查家目录", False, f"{row['home']} 不在"))
            return {"ok": False, "host_id": host_id, "steps": steps, "error": "这家智能体还没装过，没有家目录可写。"}
    steps.append(_step("检查家目录", True, row["home"]))

    if mode == "direct":
        # 直写：选中的几层按顺序拼一份，整份替换入口文件。不叫打包器、不种 hub/ 树。
        # （页面默认走这条；API 缺省 install 是给自测和「完整安装」留的。）
        return _do_load_direct(host_id, row, base_id, guest_id, hub_id, steps)

    base_argv = ""
    if base_id:
        card = _card_path(base_id, "base")
        if card is None:
            steps.append(_step("找底模卡片", False, f"base/ 池里没有这张卡：{base_id}"))
            return {"ok": False, "host_id": host_id, "steps": steps,
                    "error": "base/ 池里没有这张卡。它停用了？挪回 base/ 就能用。"}
        try:
            size = len(card.read_bytes())
        except OSError:
            size = 0
        steps.append(_step("找底模卡片", True, f"{base_id}（{size} 字节，原文注入）"))
        base_argv = str(card)

    guest_argv = ""
    if guest_id:
        card = _card_path(guest_id, "guest")
        if card is None:
            steps.append(_step("找指引卡片", False, f"guest/ 池里没有这张卡：{guest_id}"))
            return {"ok": False, "host_id": host_id, "steps": steps,
                    "error": "guest/ 池里没有这张卡。它停用了？挪回 guest/ 就能用。"}
        steps.append(_step("找指引卡片", True, f"{guest_id}（原文注入）"))
        guest_argv = str(card)

    hub_argv = ""
    if hub_id:
        card = _card_path(hub_id, "hub")
        if card is None:
            steps.append(_step("找中枢卡片", False, f"hub/ 池里没有这张卡：{hub_id}"))
            return {"ok": False, "host_id": host_id, "steps": steps,
                    "error": "hub/ 池里没有这张卡。它停用了？挪回 hub/ 就能用。"}
        if not with_marker:
            steps.append(_step("找中枢卡片", False, "中枢卡要靠标记块写进去：勾了中枢就不能关掉它"))
            return {"ok": False, "host_id": host_id, "steps": steps,
                    "error": "中枢卡要靠标记块写进去：勾了中枢就不能关掉它。"}
        steps.append(_step("找中枢卡片", True, f"{hub_id}（原文注入，就是标记块的正文）"))
        hub_argv = str(card)

    steps.append(_step("宿主原文", True,
                       "覆盖模式：原有文本整段丢弃（原字节进备份，卸回时合并还原）"
                       if replace_origin else "保留，跟在我们的几段前面"))

    # 写之前先把这一家的「配置面」拍进保险箱。拍不成本次就不写：
    # 没有可退的那一份，就不许往真人家里落笔。这是第一道服务端的门，
    # 页面上的按钮亮不亮不算（前端门禁只是给人看的）。
    # 已经有保险箱就不覆盖：主人手里那一版是**基准**，不是每次载入的产物。
    # 每次载入都重拍，等于悄悄把基准换成"这次之前的样子"——第一次之后基准就永远丢了，
    # 而主人要点「恢复」时想退的正是最开始那一版。要换基准自己按「锁定保险箱」。
    # 自测的 fixture 宿主例外：它整个家就在 TEMP 里，扔了也不心疼。
    stale = safebox_mod._stale_home_guard(host_id)
    if stale:
        steps.append(_step("备份保险箱", False, stale))
        return {"ok": False, "host_id": host_id, "steps": steps,
                "error": "保险箱对应的家目录已变化，先重新锁定后再载入。"}
    gate, gate_err = _safebox_gate(host_id, row)
    steps.extend(gate)
    if gate_err:
        return {"ok": False, "host_id": host_id, "steps": steps, "error": gate_err}

    try:
        result = bundle_locator.run_install(Path(row["home"]), base_path=base_argv,
                                            guest_path=guest_argv, hub_path=hub_argv,
                                            with_marker=with_marker,
                                            replace_origin=replace_origin,
                                            # 运行态这一道上面已经过了（运行中、读不出的都当场拒了）。
                                            # 打包器自己那份探针只认同名 exe，认不出 node 承载的宿主
                                            # （pi / claude / gemini 都是 node 起的），会把空闲的当「读不出」直接拒装。
                                            # 结论文由控制台下——它按命令行认进程，比那一份准。
                                            allow_running=True)
    except bundle_locator.BundleNotReady as exc:
        steps.append(_step("调用打包器", False, _safe_public(exc, bundle_locator.NOT_READY)))
        return {"ok": False, "host_id": host_id, "steps": steps, "error": bundle_locator.NOT_READY}
    except subprocess.TimeoutExpired:
        steps.append(_step("调用打包器", False, "超时了，可能只写了一半"))
        return {"ok": False, "host_id": host_id, "steps": steps,
                "error": "打包器超时，可能只写了一半。点「恢复」把刚才那一版找回来。"}
    detail = f"退出码 {result['returncode']}" \
        + ("" if with_marker else "（没写中枢标记块）") \
        + ("（覆盖原文）" if replace_origin else "（保留原文）") \
        + (f"（底模 {base_id}）" if base_id else "") \
        + (f"（指引 {guest_id}）" if guest_id else "") + (f"（中枢 {hub_id}）" if hub_id else "")
    steps.append(_step("调用打包器", result["ok"], detail))
    if not result["ok"]:
        return {"ok": False, "host_id": host_id, "steps": steps, "error": "打包器没有成功收工，看上面的输出。"}

    after = hosts_mod.get_host(host_id) or {}
    entry_ok = bool(after.get("entry_ok"))
    note = str(after.get("entry_note") or "")
    if entry_ok:
        steps.append(_step("核对入口文件", True, f"{after.get('entry')} · {note}"))
    else:
        steps.append(_step("核对入口文件", False, f"{after.get('entry')} · {note}"))
    steps.append(_step("核对落盘", True, f"常驻 {after.get('core_kb', 0)} KB，{after.get('file_count', 0)} 个文件")
                  if after.get("installed") else
                  _step("核对落盘", False, "没找到装好的痕迹，请手工核对"))
    return {
        "ok": bool(after.get("installed")) and entry_ok,
        "host_id": host_id,
        "steps": steps,
        "error": "" if (after.get("installed") and entry_ok)
                 else ("打包器跑完了，但入口文件里没看到中枢写的那几段：" + (note or "请手工核对")),
    }


def do_unload(host_id: str, mode: str = "install") -> dict:
    steps: list[dict] = []
    row = hosts_mod.get_host(host_id)
    if row is None:
        return {"ok": False, "host_id": host_id, "steps": steps, "error": "没有这家智能体。"}
    if row.get("running") or row.get("running_known") is False:
        steps.append(_step("检查运行态", False, "运行中或运行状态未知，不能卸载"))
        return {"ok": False, "host_id": host_id, "steps": steps,
                "error": "先关掉这家智能体，确认运行态可读后再卸载。"}
    steps.append(_step("检查运行态", True, "空闲"))
    if mode == "direct":
        # 直写的退路只有一条：把保险箱里那一份换回来。装了几层都在这条路上退。
        steps.append(_step("检查备份", True, "直写模式：按保险箱那份还原入口文件"))
        res = safebox_mod.restore(host_id)
        steps.append(_step("恢复入口文件", bool(res.get("ok")), str(res.get("say") or res.get("error") or "")))
        return {"ok": bool(res.get("ok")), "host_id": host_id, "mode": "direct", "steps": steps,
                "error": "" if res.get("ok") else str(res.get("error") or "恢复没成。"),
                "say": res.get("say") or ""}

    if not row["installed"]:
        steps.append(_step("检查安装痕迹", False, "这家本来就没装"))
        return {"ok": False, "host_id": host_id, "steps": steps, "error": "这家本来就没装，卸不了。"}
    steps.append(_step("检查安装痕迹", True, f"常驻 {row['core_kb']} KB，{row['file_count']} 个文件"))

    ready = _package_info()
    if not ready["ready"]:
        steps.append(_step("定位打包器", False, f"{bundle_locator.NOT_READY}：缺 {'、'.join(ready['missing'])}"))
        return {"ok": False, "host_id": host_id, "steps": steps, "error": f"{bundle_locator.NOT_READY}。"}
    steps.append(_step("定位打包器", True, ready["bundle_dir"]))

    try:
        result = bundle_locator.run_uninstall(Path(row["home"]))
    except bundle_locator.BundleNotReady as exc:
        steps.append(_step("调用打包器", False, _safe_public(exc, bundle_locator.NOT_READY)))
        return {"ok": False, "host_id": host_id, "steps": steps, "error": bundle_locator.NOT_READY}
    except subprocess.TimeoutExpired:
        steps.append(_step("调用打包器", False, "超时了，可能只摘了一半"))
        return {"ok": False, "host_id": host_id, "steps": steps,
                "error": "打包器超时，可能只摘了一半。点「比对」看还差什么。"}
    steps.append(_step("调用打包器", result["ok"], f"退出码 {result['returncode']}"))
    if not result["ok"]:
        return {"ok": False, "host_id": host_id, "steps": steps, "error": "打包器没有成功收工，看上面的输出。"}

    after = hosts_mod.get_host(host_id) or {}
    steps.append(_step("核对残余", not after.get("installed"), "干净" if not after.get("installed") else "还有东西留着"))
    return {
        "ok": not after.get("installed"),
        "host_id": host_id,
        "steps": steps,
        "error": "" if not after.get("installed") else "跑完了但还有残余，请手工核对。",
    }


def _card_body_sha(name: str) -> str:
    """卡片正文当前字节的 sha。和打包器 manifest 里记的是同一个算法。"""
    p = _card_path(name)
    if p is None or not p.is_file():
        return ""
    try:
        body = _card_body(p.read_text(encoding="utf-8"), p.stem)
    except (OSError, ValueError):
        return ""
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def with_card_drift(row: dict) -> dict:
    """卡片改过但没重装，页面必须看得出来。

    manifest 记了装进去那一刻的卡片正文字节；拿它和现在磁盘上的比：
    不一致 = 你改了卡、但智能体还在跑旧文本。
    """
    out = dict(row)
    for kind in ("base", "guest", "hub"):
        want = str(row.get(f"{kind}_card_sha") or "")
        name = str(row.get(f"{kind}_name") or "")
        if not want:
            out[f"{kind}_drift"] = ""
            continue
        now = _card_body_sha(name) if name else ""
        if not now:
            out[f"{kind}_drift"] = "卡没了"
        else:
            out[f"{kind}_drift"] = "你改过，没重装" if now != want else ""
    return out


def build_status(deep: bool = False) -> dict:
    rows = [with_card_drift(r) for r in hosts_mod.list_hosts(deep=deep)]
    agg = hosts_mod.totals()
    return {
        "ok": True,
        "version": __version__,
        "package": _package_info(),
        "installed_ids": agg["installed_ids"],
        "counts": {
            "hosts_total": agg["hosts_total"],
            "hosts_present": agg["hosts_present"],
            "hosts_installed": agg["hosts_installed"],
            "hosts_scanned": agg["hosts_scanned"],
            "hosts_custom": agg["hosts_custom"],
            "core_kb": agg["core_kb"],
            "file_count": agg["file_count"],
        },
        "process_probe_known": hosts_mod.probe_known(),
        "scan": hosts_mod.scan_report(deep=deep),
        "cards": list_cards(),
        "cards_parked": parked_cards(),
        "hosts": [
            {
                "id": row["id"],
                "name": row["name"],
                "installed": row["installed"],
                "core_kb": row["core_kb"],
                "file_count": row["file_count"],
            }
            for row in rows
        ],
    }


# ---------------------------------------------------------------- 请求处理

class Handler(BaseHTTPRequestHandler):
    server_version = f"hubconsole/{__version__}"
    sys_version = ""
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):  # noqa: D102 - 不把令牌写进终端
        line = fmt % args
        # 请求行里可能挂着 ?t=令牌，别原样进终端（黑窗口会被截图、被复制）。
        line = re.sub(r"([?&]t=)[^ &\"]+", r"\1<已隐去>", line)
        sys.stderr.write("hub-console: " + line + "\n")

    # -- 鉴权 ---------------------------------------------------------------
    def _client_is_local(self) -> bool:
        try:
            return self.client_address[0] in LOOPBACK
        except (IndexError, TypeError):
            return False

    def _token_ok(self) -> bool:
        given = self.headers.get("X-Token") or ""
        if given and hmac.compare_digest(given, TOKEN):
            return True
        cookie = _token_from_cookie(self)
        if cookie and hmac.compare_digest(cookie, TOKEN):
            return True
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
        value = (query.get("t") or [""])[0]
        return bool(value) and hmac.compare_digest(value, TOKEN)

    def _host_ok(self) -> bool:
        """Host 头必须就是本机这个端口。

        不校验 Host 的话，攻击者把 evil.test 的 A 记录指到 127.0.0.1，
        浏览器拿到的就是控制台自己的源（同源），Cookie 也发得出去。
        这是本地服务被网页接管的标准路子，必须堵。
        """
        try:
            port = int(self.server.server_address[1])
        except (TypeError, ValueError, IndexError):
            return False
        host = (self.headers.get("Host") or "").strip().lower()
        return host in ("127.0.0.1:%d" % port, "localhost:%d" % port, "[::1]:%d" % port)

    def _authed(self) -> bool:
        if not self._client_is_local() or not self._host_ok():
            return False
        if self._token_ok():
            return True
        # 浏览器同源来路：Sec-Fetch-Site 是浏览器强制字段，网页里的 JS 伪不了。
        # 以前这里看 Origin/Referer——那两个头本地程序自己就能填，等于没门。
        return (self.headers.get("Sec-Fetch-Site") or "").strip().lower() == "same-origin"

    def _deny(self) -> None:
        _send_json(self, 403, {"ok": False, "error": "只听本机，且要带令牌。"})

    # -- GET ---------------------------------------------------------------
    def do_GET(self):  # noqa: N802
        if not self._client_is_local():
            self.send_error(403, "Forbidden")
            return
        if not self._host_ok():
            self.send_error(403, "Forbidden")
            return
        path = urllib.parse.urlsplit(self.path).path
        if path.startswith("/api/"):
            if not self._authed():
                return self._deny()
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            flag = lambda key: (query.get(key) or [""])[0]  # noqa: E731
            if path == "/api/hosts":
                want_all = bool(flag("all"))
                deep = bool(flag("deep"))
                return _send_json(self, 200, {
                    "ok": True,
                    "hosts": [with_card_drift(r)
                              for r in hosts_mod.list_hosts(include_missing=want_all, deep=deep)],
                })
            if path == "/api/status":
                return _send_json(self, 200, build_status(deep=bool(flag("deep"))))
            if path == "/api/scan":
                return _send_json(self, 200, {"ok": True,
                                               "scan": hosts_mod.scan_report(deep=bool(flag("deep")))})
            if path == "/api/cards":
                return _send_json(self, 200, {"ok": True, "cards": list_cards()})
            if path == "/api/card":
                return _send_json(self, 200, read_card((flag("id") or "").strip(),
                                                       (flag("kind") or "").strip()))
            if path == "/api/safebox":
                host_id = (flag("host_id") or "").strip()
                if host_id and hosts_mod.get_host(host_id) is None:
                    return _send_json(self, 404, {"ok": False, "error": "没有这家智能体。"})
                return _send_json(self, 200, safebox_mod.list_snapshots(host_id))
            return _send_json(self, 404, {"ok": False, "error": "没有这个接口。"})
        # app.js / style.css 不含任何秘密，本机回环直接发：浏览器加载它们时带不上凭据。
        if path in ("/app.js", "/style.css"):
            name = _STATIC.get(path)
            if not name:
                self.send_error(404, "Not Found")
                return
            _send_file(self, name)
            return
        name = _STATIC.get(path)
        if not name:
            self.send_error(404, "Not Found")
            return
        # 页面外壳（index.html）对本机来路直接放行，顺手发一个会话 Cookie。
        # 主人打开的地址就只剩端口；后面所有 /api/ 用这个 Cookie 过闸。
        if name == "index.html":
            return _send_file(self, name, set_cookie=True)
        if not self._authed():
            return self._deny()
        _send_file(self, name)

    # -- POST --------------------------------------------------------------
    def _read_json(self) -> tuple[dict | None, tuple[int, dict] | None]:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return None, (400, {"ok": False, "error": "长度不对。"})
        if length < 0 or length > _MAX_BODY:
            return None, (413, {"ok": False, "error": "请求太大。"})
        try:
            data = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None, (400, {"ok": False, "error": "内容不对。"})
        if not isinstance(data, dict):
            return None, (400, {"ok": False, "error": "内容不对。"})
        return data, None

    def do_POST(self):  # noqa: N802
        if not self._client_is_local():
            self.send_error(403, "Forbidden")
            return
        if not self._host_ok():
            self.send_error(403, "Forbidden")
            return
        if not self._authed():
            return self._deny()
        path = urllib.parse.urlsplit(self.path).path

        # 名单三件：手加一家、从名单拿掉一家、点名别再列一家。
        # 「扫不到」不是死路——主人自己填家目录也能用。
        if path in ("/api/hosts/add", "/api/hosts/remove", "/api/hosts/ignore",
                    "/api/hosts/unignore"):
            data, err = self._read_json()
            if err:
                return _send_json(self, err[0], err[1])
            hosts_mod.invalidate_cache()
            if path == "/api/hosts/add":
                res = hosts_mod.add_custom(data.get("name") or "", data.get("home") or "")
            elif path == "/api/hosts/remove":
                res = hosts_mod.remove_custom(str(data.get("id") or ""))
            else:
                home = str(data.get("home") or "").strip()
                if not home:
                    res = {"ok": False, "error": "少一个家目录。"}
                elif path == "/api/hosts/ignore":
                    hosts_mod.ignore_host(home)
                    res = {"ok": True, "home": home}
                else:
                    res = hosts_mod.unignore_host(home)
            return _send_json(self, 200 if res.get("ok") else 400, res)

        if path == "/api/hosts/kill":
            data, err = self._read_json()
            if err:
                return _send_json(self, err[0], err[1])
            host_id = str(data.get("id") or data.get("host_id") or "").strip()
            if not host_id:
                return _send_json(self, 400, {"ok": False, "error": "少一个智能体 id。"})
            if not _mutate_lock.acquire(blocking=False):
                return _send_json(self, 409, {"ok": False, "error": "还有一个动作在跑，等它完。"})
            try:
                res = hosts_mod.kill_host_processes(host_id)
            except Exception as exc:  # noqa: BLE001
                sys.stderr.write(f"hub-console: kill 出错 {type(exc).__name__}\n")
                res = {"ok": False, "error": "本机服务出了点问题，看终端。"}
            finally:
                _mutate_lock.release()
            return _send_json(self, 200 if res.get("ok") else 400, res)

        if path == "/api/safebox":
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                return _send_json(self, 400, {"ok": False, "error": "长度不对。"})
            if length < 0 or length > _MAX_BODY:
                # 不读完 body 也不关连接：同一条连接上的下一个请求会从残留的 body 开始解析。
                self.close_connection = True
                return _send_json(self, 413, {"ok": False, "error": "请求太大。"})
            try:
                data = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            except (json.JSONDecodeError, UnicodeDecodeError):
                return _send_json(self, 400, {"ok": False, "error": "内容不对。"})
            if not isinstance(data, dict):
                return _send_json(self, 400, {"ok": False, "error": "内容不对。"})
            host_id = data.get("host_id") or ""
            action = data.get("action") or ""
            if not isinstance(host_id, str) or not isinstance(action, str):
                return _send_json(self, 400, {"ok": False, "error": "少 host_id 或 action。"})
            host_id, action = host_id.strip(), action.strip()
            if hosts_mod.get_host(host_id) is None:
                return _send_json(self, 404, {"ok": False, "error": "没有这家智能体。"})
            fn = {"snapshot": safebox_mod.take, "verify": safebox_mod.compare,
                  "restore": safebox_mod.restore}.get(action)
            if fn is None:
                return _send_json(self, 400, {"ok": False, "error": "action 只能是 snapshot / verify / restore。"})
            if not _mutate_lock.acquire(blocking=False):
                return _send_json(self, 409, {"ok": False, "error": "还有一个动作在跑，等它完。"})
            hosts_mod.invalidate_cache()
            try:
                res = fn(host_id)
            except Exception as exc:  # noqa: BLE001
                sys.stderr.write(f"hub-console: safebox {action} 出错 {type(exc).__name__}\n")
                res = {"ok": False, "error": "本机服务出了点问题，看终端。"}
            finally:
                hosts_mod.invalidate_cache()
                _mutate_lock.release()
            return _send_json(self, 200 if res.get("ok") else 400, res)
        if path in ("/api/cards", "/api/cards/delete"):
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                return _send_json(self, 400, {"ok": False, "error": "长度不对。"})
            if length < 0 or length > _MAX_BODY:
                # 不读完 body 也不关连接：同一条连接上的下一个请求会从残留的 body 开始解析。
                self.close_connection = True
                return _send_json(self, 413, {"ok": False, "error": "请求太大。"})
            try:
                data = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            except (json.JSONDecodeError, UnicodeDecodeError):
                return _send_json(self, 400, {"ok": False, "error": "内容不对。"})
            if not isinstance(data, dict):
                return _send_json(self, 400, {"ok": False, "error": "内容不对。"})
            try:
                if path == "/api/cards/delete":
                    card_id = data.get("id") or ""
                    if not isinstance(card_id, str):
                        return _send_json(self, 400, {"ok": False, "error": "少一个 id。"})
                    res = delete_card(card_id.strip(), str(data.get("kind") or "").strip())
                else:
                    if not isinstance(data.get("name"), str) or not isinstance(data.get("content"), str):
                        return _send_json(self, 400, {"ok": False, "error": "少名字或少正文。"})
                    kind = data.get("kind") or "base"
                    if not isinstance(kind, str) or kind not in ("base", "guest"):
                        return _send_json(self, 400, {"ok": False, "error": "kind 只能是 base 或 guest。"})
                    res = save_card(data.get("name"), data.get("hosts") or "", data.get("content"), kind)
            except Exception as exc:  # noqa: BLE001
                sys.stderr.write(f"hub-console: cards 出错 {type(exc).__name__}\n")
                res = {"ok": False, "error": "本机服务出了点问题，看终端。"}
            return _send_json(self, 200 if res.get("ok") else 400, res)
        if path not in ("/api/load", "/api/unload"):
            return _send_json(self, 404, {"ok": False, "error": "没有这个接口。"})
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return _send_json(self, 400, {"ok": False, "error": "长度不对。"})
        if length < 0 or length > _MAX_BODY:
            self.close_connection = True
            return _send_json(self, 413, {"ok": False, "error": "请求太大。"})
        try:
            data = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            return _send_json(self, 400, {"ok": False, "error": "内容不对。"})
        host_id = data.get("host_id") if isinstance(data, dict) else None
        if not isinstance(host_id, str) or not host_id.strip():
            return _send_json(self, 400, {"ok": False, "error": "少一个 host_id。"})
        host_id = host_id.strip()
        base_id = ""
        guest_id = ""
        hub_id = ""
        with_marker = True
        replace_origin = False
        # 写法：direct = 直写（选中的几层拼一份，整份替换入口文件，不走打包器）；
        #       install = 完整安装（叫打包器，另外把 hub/ 那棵树也写进去）。
        mode = "install"
        if path == "/api/load":
            raw_base = data.get("base_id") or ""
            if not isinstance(raw_base, str):
                return _send_json(self, 400, {"ok": False, "error": "底模 id 不对。"})
            base_id = raw_base.strip()
            raw_guest = data.get("guest_id") or ""
            if not isinstance(raw_guest, str):
                return _send_json(self, 400, {"ok": False, "error": "指引 id 不对。"})
            guest_id = raw_guest.strip()
            raw_hub = data.get("hub_id") or ""
            if not isinstance(raw_hub, str):
                return _send_json(self, 400, {"ok": False, "error": "中枢 id 不对。"})
            hub_id = raw_hub.strip()
            if "with_marker" in data:
                raw_marker = data.get("with_marker")
                if not isinstance(raw_marker, bool):
                    # bool("false") 是 True —— 字符串假值会当真，把 11 块底线写进去。
                    return _send_json(self, 400, {"ok": False,
                                                   "error": "with_marker 只能是 true/false。"})
                with_marker = raw_marker
            if "mode" in data:
                raw_mode = data.get("mode")
                if not isinstance(raw_mode, str) or raw_mode not in ("direct", "install"):
                    return _send_json(self, 400, {"ok": False,
                                                   "error": "mode 只能是 direct / install。"})
                mode = raw_mode
            if "replace_origin" in data:
                raw_origin = data.get("replace_origin")
                if not isinstance(raw_origin, bool):
                    return _send_json(self, 400, {"ok": False,
                                                   "error": "replace_origin 只能是 true/false。"})
                replace_origin = raw_origin
        if path == "/api/unload" and "mode" in data:
            raw_mode = data.get("mode")
            if not isinstance(raw_mode, str) or raw_mode not in ("direct", "install"):
                return _send_json(self, 400, {"ok": False, "error": "mode 只能是 direct / install。"})
            mode = raw_mode
        if not _mutate_lock.acquire(blocking=False):
            return _send_json(self, 409, {"ok": False, "error": "还有一个动作在跑，等它完。"})
        try:
            hosts_mod.invalidate_cache()
            if path == "/api/load":
                payload = do_load(host_id, base_id, guest_id, hub_id, with_marker,
                                  replace_origin, mode)
            else:
                payload = do_unload(host_id, mode)
        except Exception as exc:  # noqa: BLE001 - 页面不许看到 traceback
            sys.stderr.write(f"hub-console: {type(exc).__name__} in {path}\n")
            payload = {"ok": False, "host_id": host_id, "steps": [], "error": "本机服务出了点问题，看终端。"}
        finally:
            hosts_mod.invalidate_cache()
            _mutate_lock.release()
        _send_json(self, 200 if payload.get("ok") else 400, payload)


# ---------------------------------------------------------------- 启动

def make_server(port: int = 0) -> tuple[ThreadingHTTPServer, int]:
    httpd = ThreadingHTTPServer((BIND_HOST, port), Handler)
    httpd.daemon_threads = True
    return httpd, int(httpd.server_address[1])


def console_url(port: int) -> str:
    return f"http://{BIND_HOST}:{port}"


def is_loopback_bind(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.3)
        return sock.connect_ex((BIND_HOST, port)) == 0
