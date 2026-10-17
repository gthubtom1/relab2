#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""relab2-tools-mcp.py —— 把**本机工具链**暴露成 MCP 工具（stdio）。

为什么存在（2026-10-15）：
  本仓本地有几十个 CLI 工具（diec / floss / capa / pe-sieve / jadx / r2 / nmap / hashcat / frida …），
  现在只能靠模型**自己想起来**去 shell 里敲，还要自己拼路径。REA 的做法是把工具全包成 MCP 工具，
  模型一伸手就有；本仓目前只包了 4 个分析引擎（IDA/Ghidra/x64dbg/angr）。
  本服务器补上这一块，并且**不写死任何路径** —— 工具定位每次实时走探测层
  （`Bootstrap.ps1` 的 `Resolve-ReverseToolSpec`，四级递进），所以**换机自动适配**。

暴露的工具：
  · `local_tools`      —— 本机工具链**实时**清单（可用 / 缺件），永不过期
  · `run_tool`         —— 按 tool id 调用本机任一工具（路径由探测层解析）
  · `triage_target`    —— 一次跑完「第一眼」该跑的那几把刀，返回结构化摘要
  · `find_capability`  —— 按能力找工具（不按名字背清单）
  · `read_tool_output` —— 按 handle + 字节偏移**分页取回**原始输出（stdout/stderr 分流）

★ 2026-10-16 大输出改造（为什么必须改）：
  旧实现用 `subprocess.run(capture_output=True)` 把全部输出收进内存，再 `stdout[:20000]`、
  最后对**整段 JSON 字符串**切 `[:24000]`。实测：stdout 达到 20000 字符时序列化后是 24134 字符，
  切到 24000 必然产出**无法解析的 JSON**（`json.loads` 报 Unterminated string）——
  也就是说「越是需要它输出的场景，模型越拿不到可解析结果」。超时路径更糟：连已捕获的内容都不返回。
  现在改成：执行时把 stdout/stderr **分流写入本机受限存储**、边写边计字节与 SHA-256；
  返回体**先构造再按预算裁剪**，永远是合法 JSON；大输出给短预览 + 不可猜的 handle，
  用 `read_tool_output` 按字节偏移分页取回（base64，保真非 UTF-8 与 NUL）。
  存储有上限：超限**明确报限额**，不静默丢旧 handle；过期（默认 24h）才清理。

为什么不是「保证绝不丢」：
  存储有上限。超过单流/总量上限时是「明确终止 + 前缀可取回 + capture_complete=false」，
  不是完整。断电、外部删除、保留期结束都会影响取回。要长期留证，请走案例流程显式转存。

用法（宿主 mcp.json 注册成 stdio 服务器）：
  { "command": "<venv python>",
    "args": ["<仓根>/skillpack/skills/scripts/relab2-tools-mcp.py",
             "--skill-root", "<技能包根>", "--tool-root", "<工具根>"] }

自检（不起 MCP，验证捕获/分页/超时/非 UTF-8）：
  python relab2-tools-mcp.py --selftest

日志：%LOCALAPPDATA%\\reverse-skill\\tools-mcp\\tools-mcp.log
结果：%LOCALAPPDATA%\\reverse-skill\\tools-mcp\\results\\<handle>\\{stdout.bin,stderr.bin,meta.json}
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

# ★ 2026-10-17：MCP 传输栈**按需导入**，不在模块级硬失败。
#   起因：这几行原来是模块级无条件 import。CI 的 ubuntu runner 没装 mcp/anyio，
#   于是**任何** `import` 这个模块的路径都直接 ModuleNotFoundError —— 受害的是
#   **不需要 MCP 的三条路**：
#     · `relab2-tools-mcp.py --selftest`（捕获 / 分页 / 字节保真自检）
#     · `test-tool-recipes.py`（配方真跑）
#     · `test-new-tool-discovery.py`（能力发现 + 解析链）
#   三道门在 CI 上都以 traceback 红掉，而它们验的都不是传输层
#   （CI 原文只有 `stderr: Traceback (most recent call last):` 一行，看不出原因）。
#   现在：缺 MCP 栈时模块仍可导入，自检与门禁照跑；真要起服务器才报错并说清缺什么。
try:
    import anyio
    import mcp.types as types
    from mcp.server.lowlevel import Server
    from mcp.server.stdio import stdio_server
    _MCP_IMPORT_ERROR = ""
except ImportError as _mcp_exc:  # pragma: no cover - 取决于宿主是否装了 MCP 栈
    anyio = None
    types = None
    Server = None
    stdio_server = None
    _MCP_IMPORT_ERROR = f"{type(_mcp_exc).__name__}: {_mcp_exc}"

# 常用工具 id —— 覆盖四大战场。「没有的」当场报出来，不去猜。
KNOWN_TOOLS = [
    # 逆向 / 分析
    "diec", "die", "floss", "capa", "pe-sieve", "scyllahide",
    "idat", "ida", "ghidra", "ghidra_headless", "x64dbg", "x32dbg",
    "radare2", "r2", "rabin2", "ROPgadget", "ropper", "gdb", "cdb",
    # 移动
    "jadx", "apktool", "frida", "objection", "apksigner", "scrcpy",
    # 托管
    "dotnet", "de4dot", "ilspycmd",
    # 固件 / 解包
    "binwalk", "unblob", "upx", "7z",
    # 网络 / 抓包
    "nmap", "ncat", "nping", "tshark", "wireshark", "mitmdump", "mitmproxy", "httpx",
    # 口令 / 渗透
    "hashcat", "sqlmap", "nuclei", "ffuf", "burpsuite", "john", "yara",
    # 运行时
    "python", "java", "node", "npm", "go", "gcc", "jq", "ffmpeg", "git", "gh",
]

# ---------------------------------------------------------------- GUI / 启动器禁执行表
# ★ 2026-10-16 工具层逐条实测后补。`capability-index.py` 早就有 `GUI_HINTS` / `NEVER_EXEC`
#   两道闸，而 `run_tool` 这条路径**一道都没有** —— 实测 `run_tool('x64dbg', …)` 会去跑
#   `D:\Tools\cli\start-x64dbg-mcp.ps1`（项目自己的启动器），`ida` / `die` 会弹窗口。
#   键 = tool id（小写），值 = (为什么不能执行, 可照抄的 CLI 孪生或空串)。
_GUI_TOOL_IDS: dict[str, tuple[str, str]] = {
    "ida": ("IDA 图形界面", "idat"),
    "ida64": ("IDA 图形界面（同一 ida.exe）", "idat"),
    "ida83": ("IDA 8.3 图形界面", "idat"),
    "ida83-gui": ("IDA 8.3 图形界面", "idat"),
    "ghidra": ("Ghidra 图形启动器 ghidraRun.bat", "ghidra_headless"),
    "ghidrarun": ("Ghidra 图形启动器", "ghidra_headless"),
    "die": ("Detect-It-Easy 图形界面", "diec"),
    "wireshark": ("Wireshark 图形界面", "tshark"),
    "wshark": ("Wireshark 图形界面（别名）", "tshark"),
    "x64dbg": ("★ 探测层把它解析到 D:\\Tools\\cli\\start-x64dbg-mcp.ps1 —— 项目自己的启动器，不是调试器本体；跑它 = 拉起 GUI", ""),
    "x64dbg-gui": ("x64dbg 图形界面", ""),
    "x32dbg": ("x64dbg 的 32 位图形界面", ""),
    "x32dbg-gui": ("x64dbg 的 32 位图形界面", ""),
    "x96dbg": ("x64dbg 的启动选择器（图形）", ""),
    "dnspy": ("dnSpy 图形界面", "dnSpy.Console"),
    "jd-gui": ("jd-gui 图形反编译器", "jadx"),
    "jeb": ("JEB 图形界面", "jeb_wincon"),
    "androidkiller": ("AndroidKiller 图形界面", "apktool"),
    "gda": ("GDA 图形反编译器", "jadx"),
    "peid": ("PEiD 图形查壳器", "diec"),
    "autoeye64": ("AutoEye 图形查壳器", "diec"),
    "afpiunpack": ("AFPI Unpacker 图形界面（实测跑起来不返回）", "innoextract"),
    "imhex": ("ImHex 图形十六进制编辑器", ""),
    "pe-bear": ("PE-bear 图形界面", ""),
    "ollydbg": ("OllyDbg 图形界面", ""),
    "charles": ("Charles 图形抓包器", "mitmdump"),
    "fiddler": ("Fiddler 图形抓包器", "mitmdump"),
    "mitmweb": ("mitmproxy 的 web 界面", "mitmdump"),
    "scyllahide-profile": ("ScyllaHide 的配置项，不是可执行文件", "scyllahide"),
    "unpackers": ("工具根里的**目录**名字，不是可执行文件", "upx"),
    "pyre": ("python-venv 的解释器（语义含糊，禁走本通道）", "python"),
}


# ★ 2026-10-16 工具层实测发现的**真缺陷**：PowerShell 往管道写 stdout 时用的是
#   `[Console]::OutputEncoding`（本机 cp936/GBK），而这边一律按 UTF-8 解码 ——
#   于是**凡是路径里带非 ASCII 的工具，解析结果全长成乱码**：`os.path.exists()` 为假、
#   `run_tool` 直接 WinError 2（"系统找不到指定的文件"），而工具其实好好的。
#   实测：`ctx.resolve('dexdump')` 返回
#   `D:\Tools\android\Android????????_v2.2\lib\dexdump.exe`（存在性 False），
#   同一条路径在 PowerShell 里逐字完好 —— 纯粹的管道编码事故。
#   本机 57 条预探测 id 恰好全在 ASCII 路径下，所以它此前一直没露头；
#   探到 `Android逆向助手_v2.2` 这类目录就立刻现形（aapt / dexdump / zipalign / dex2jar 全中）。
#   修法：在两段探测脚本最前面把控制台编码钉成 UTF-8（`$false` = 不带 BOM），
#   与本包 `mcp-status.ps1` / `register-skills.ps1` 的处理同源。实测修完 exists=True。
_PS_UTF8 = ("[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false);"
            "[Console]::InputEncoding=[System.Text.UTF8Encoding]::new($false);")

PROBE_PS = _PS_UTF8 + r"""
$ErrorActionPreference='Continue'
. "{bootstrap}"
$ids = @({ids})
$out = @()
foreach ($id in $ids) {{
  $r = $null
  try {{ $r = Resolve-ReverseToolSpec -Name $id -ErrorAction Stop }} catch {{ }}
  if ($r -and $r.Available) {{
    $out += [pscustomobject]@{{ id=$id; ok=$true; via=("" + $r.Via); cmd=("" + $r.Command) }}
  }} else {{
    $out += [pscustomobject]@{{ id=$id; ok=$false; via=''; cmd='' }}
  }}
}}
$out | ConvertTo-Json -Compress
"""

# ---------------------------------------------------------------- 有界保留的参数
# 契约（2026-10-16）：单次每流上限、总量上限、保留期、预览与分页大小。
# 全部可用环境变量覆盖，方便夹具调小（验收用小额度不必写 32 MiB）。
STREAM_CAP = int(os.environ.get("REL2_TOOLS_STREAM_CAP", 32 * 1024 * 1024))
TOTAL_CAP = int(os.environ.get("REL2_TOOLS_TOTAL_CAP", 256 * 1024 * 1024))
TTL_SECONDS = int(os.environ.get("REL2_TOOLS_TTL", 24 * 3600))
PREVIEW_BYTES = int(os.environ.get("REL2_TOOLS_PREVIEW", 1024))
PAGE_BYTES_DEFAULT = 8192
PAGE_BYTES_MAX = 65536
LIST_PAGE_DEFAULT = 200
LIST_PAGE_MAX = 2000
# `local_tools` / `find_capability` 的"小结果原样返回"阈值
TEXT_BUDGET = int(os.environ.get("REL2_TOOLS_TEXT_BUDGET", 16000))

_HANDLE_RE = re.compile(r"^[0-9a-f]{32}$")
_NEW_PROCESS_GROUP = 0x00000200 if os.name == "nt" else 0


def _paginate_lines(text: str, offset: int, limit: int) -> tuple[dict, str]:
    """按行分页。返回 (分页元数据, 本页正文)。"""
    lines = text.splitlines()
    total = len(lines)
    off = max(0, int(offset or 0))
    lim = max(1, min(int(limit or LIST_PAGE_DEFAULT), LIST_PAGE_MAX))
    page = lines[off:off + lim]
    nxt = off + lim if off + lim < total else None
    meta = {"offset": off, "limit": lim, "total_lines": total,
            "next_offset": nxt, "truncated": nxt is not None}
    return meta, "\n".join(page)


class Ctx:
    def __init__(self, args: argparse.Namespace) -> None:
        self.skill_root = args.skill_root
        self.tool_root = args.tool_root
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        self.state = Path(base) / "reverse-skill" / "tools-mcp"
        self.state.mkdir(parents=True, exist_ok=True)
        self.log_file = self.state / "tools-mcp.log"
        self.results = self.state / "results"
        self.results.mkdir(parents=True, exist_ok=True)
        # 探测表落盘缓存：让「新进程第一次问」不再重付 25s 全额代价（见 probe() 注释）
        self.probe_cache = self.state / "probe-cache.json"
        self._cache: tuple[float, dict[str, dict]] | None = None

    def log(self, msg: str) -> None:
        try:
            with self.log_file.open("a", encoding="utf-8") as f:
                f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")
        except OSError:
            pass

    # ------------------------------------------------------------ 探测层
    def _bootstrap(self) -> Path | None:
        for cand in (
            Path(self.skill_root) / "skills" / "scripts" / "lib" / "Bootstrap.ps1",
            Path(self.skill_root) / "skillpack" / "skills" / "scripts" / "lib" / "Bootstrap.ps1",
        ):
            if cand.exists():
                return cand
        return None

    def probe(self, ttl: int = 600) -> dict[str, dict]:
        """实时探测本机工具链。结果带 TTL 缓存，避免每次都跑 5–25 秒的四级递进。

        ★ 2026-10-16 工具层实测补：**结果同时落盘**。此前缓存只在内存里，于是
        「本进程第一次问」每次都要重付全额代价 —— 实测 57 条 id 走完四级递进要 **25.0 s**，
        而调用方的 MCP 客户端超时是 30 s：`local_tools(refresh=true)` 当场超时
        （本次审计真踩到，见 report-tools.md）。工具装上/卸下是低频事件，
        10 分钟新鲜度和内存缓存同义，没有额外的新鲜度损失。
        """
        if self._cache and (time.time() - self._cache[0]) < ttl:
            return self._cache[1]
        if ttl > 0:
            disk = self._load_disk_cache(ttl)
            if disk is not None:
                self._cache = (time.time(), disk)
                return disk
        bs = self._bootstrap()
        if not bs:
            self.log(f"Bootstrap.ps1 not found under {self.skill_root}")
            return {}
        ids = ",".join(f"'{i}'" for i in KNOWN_TOOLS)
        script = PROBE_PS.format(bootstrap=str(bs).replace("\\", "\\\\"), ids=ids)
        try:
            p = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
        except (OSError, subprocess.TimeoutExpired) as e:
            self.log(f"probe failed: {e!r}")
            return {}
        raw = (p.stdout or "").strip()
        try:
            data = json.loads(raw)
        except ValueError:
            self.log(f"probe output not JSON: {raw[:300]!r}")
            return {}
        if isinstance(data, dict):
            data = [data]
        table = {d["id"]: d for d in data if isinstance(d, dict) and d.get("id")}
        self._cache = (time.time(), table)
        ok = sum(1 for d in table.values() if d.get("ok"))
        self.log(f"probe: {ok}/{len(table)} available")
        self._save_disk_cache(table)
        return table

    # ------------------------------------------------------------ 探测结果落盘缓存
    # 只缓存「探测表」本身（id/via/cmd/ok），不缓存判定；写入用同名临时文件再替换，
    # 任何一步失败都只是「这次没缓存上」，绝不改变探测结果 —— 缓存不是事实源。
    def _load_disk_cache(self, ttl: int) -> dict[str, dict] | None:
        try:
            d = json.loads(self.probe_cache.read_text(encoding="utf-8"))
            if time.time() - float(d.get("at") or 0) >= ttl:
                return None
            if not d.get("ids"):
                return None
            table = d["table"]
            if not isinstance(table, dict) or not table:
                return None
            self.log(f"probe: 用落盘缓存（{len(table)} 条，{int(time.time() - d['at'])}s 前）")
            return table
        except (OSError, ValueError, TypeError, AttributeError):
            return None

    def _save_disk_cache(self, table: dict[str, dict]) -> None:
        try:
            tmp = self.probe_cache.with_suffix(".tmp")
            tmp.write_text(json.dumps({"at": time.time(), "ids": list(KNOWN_TOOLS),
                                       "table": table}, ensure_ascii=False), encoding="utf-8")
            tmp.replace(self.probe_cache)
        except OSError as e:  # scan-ok: 落盘缓存是 best-effort；失败只意味着下次还得冷跑一遍，探测结果本身不受影响
            self.log(f"probe cache write failed: {e!r}")

    # ------------------------------------------------------------ 结果存储
    def _sweep(self) -> int:
        """清掉过期目录，返回**未过期**结果占用的总字节数（不含日志）。"""
        now = time.time()
        total = 0
        for d in self.results.iterdir():
            if not d.is_dir() or not _HANDLE_RE.fullmatch(d.name):
                continue
            try:
                age = now - d.stat().st_mtime
            except OSError:
                continue
            if age > TTL_SECONDS:
                shutil.rmtree(d, ignore_errors=True)
                self.log(f"sweep: drop expired {d.name}")
                continue
            for f in d.iterdir():
                try:
                    if f.is_file():
                        total += f.stat().st_size
                except OSError:
                    pass
        return total

    def _preview(self, path: Path) -> str:
        try:
            with path.open("rb") as f:
                raw = f.read(PREVIEW_BYTES)
        except OSError:
            return ""
        return raw.decode("utf-8", "replace")

    def _drain(self, pipe, path: Path, info: dict) -> None:
        """把一路管道有界写盘；超上限后继续 drain（避免写端堵塞死锁）但不再落盘。"""
        digest = hashlib.sha256()
        written = 0
        capped = False
        try:
            with path.open("wb") as f:
                while True:
                    chunk = pipe.read(65536)
                    if not chunk:
                        break
                    room = STREAM_CAP - written
                    if room > 0:
                        keep = chunk[:room]
                        f.write(keep)
                        digest.update(keep)
                        written += len(keep)
                        if len(keep) < len(chunk):
                            capped = True
                    else:
                        capped = True
        except OSError:
            pass
        finally:
            try:
                pipe.close()
            except OSError:
                pass
        info["bytes"] = written
        info["sha256"] = digest.hexdigest()
        info["capped"] = capped

    @staticmethod
    def _kill_tree(proc: subprocess.Popen) -> None:
        """终止**整棵进程树**。`Popen.kill()` 只杀直接子进程，孙进程会留下。"""
        if os.name == "nt":
            try:
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                               capture_output=True, timeout=20)
                return
            except (OSError, subprocess.TimeoutExpired):
                pass
        try:
            proc.kill()
        except OSError:
            pass

    def _capture(self, cmd: str, argv: list[str], timeout: int) -> dict:
        """执行 + 分流有界捕获。返回结构化状态（不含 handle 的拼装）。"""
        handle = uuid.uuid4().hex
        hdir = self.results / handle
        hdir.mkdir(parents=True, exist_ok=True)
        stdout_path = hdir / "stdout.bin"
        stderr_path = hdir / "stderr.bin"
        info: dict = {"stdout": {"bytes": 0, "sha256": "", "capped": False},
                      "stderr": {"bytes": 0, "sha256": "", "capped": False}}
        started = time.time()
        try:
            proc = subprocess.Popen([cmd, *argv], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    stdin=subprocess.DEVNULL, creationflags=_NEW_PROCESS_GROUP)
        except OSError as e:
            shutil.rmtree(hdir, ignore_errors=True)
            return {"status": "spawn_error", "exit": None, "handle": None,
                    "error": f"{type(e).__name__}: {e}", "duration_s": 0.0}
        threads = {}
        for name, pipe, path in (("stdout", proc.stdout, stdout_path),
                                 ("stderr", proc.stderr, stderr_path)):
            t = threading.Thread(target=self._drain, args=(pipe, path, info[name]), daemon=True)
            t.start()
            threads[name] = t
        timed_out = False
        try:
            code = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            self._kill_tree(proc)
            try:
                code = proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                code = None
        for t in threads.values():
            t.join(timeout=15)
        duration = round(time.time() - started, 3)
        # capture_complete 只看"进程是否自然结束 + 有没有触到上限"，
        # 与"是否展示被截"完全是两回事（预览永远是有界的，那不算不完整）。
        capped = info["stdout"]["capped"] or info["stderr"]["capped"]
        complete = (not timed_out) and (not capped) and code is not None
        if timed_out:
            status = "timeout"
        elif code != 0:
            status = "exit_nonzero"
        elif capped:
            status = "capped"
        else:
            status = "ok"
        meta = {
            "handle": handle, "command": cmd, "argv": argv,
            "started": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(started)),
            "duration_s": duration, "status": status, "exit": code,
            "capture_complete": complete,
            "streams": {k: {"bytes": v["bytes"], "sha256": v["sha256"],
                            "capped": v["capped"]} for k, v in info.items()},
        }
        try:
            tmp = hdir / "meta.json.tmp"
            tmp.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
            tmp.replace(hdir / "meta.json")
        except OSError as e:
            self.log(f"meta write failed {handle}: {e!r}")
        return {"status": status, "exit": code, "handle": handle, "duration_s": duration,
                "capture_complete": complete,
                "stdout": {"bytes": info["stdout"]["bytes"], "sha256": info["stdout"]["sha256"],
                           "preview": self._preview(stdout_path)},
                "stderr": {"bytes": info["stderr"]["bytes"], "sha256": info["stderr"]["sha256"],
                           "preview": self._preview(stderr_path)},
                "stream_cap": STREAM_CAP}

    def read_page(self, handle: str, stream: str, offset: int, length: int) -> dict:
        if not isinstance(handle, str) or not _HANDLE_RE.fullmatch(handle):
            return {"ok": False, "error": "handle 形状不对（应为 32 位十六进制）。不接受路径。"}
        if stream not in ("stdout", "stderr"):
            return {"ok": False, "error": "stream 只能是 'stdout' 或 'stderr'。"}
        hdir = (self.results / handle).resolve()
        # 双保险：解析后必须仍在 results 目录内（防符号链接/穿越）
        if hdir.parent != self.results.resolve():
            return {"ok": False, "error": "handle 越界。"}
        path = hdir / f"{stream}.bin"
        meta_path = hdir / "meta.json"
        if not path.is_file():
            expired = hdir.is_dir()
            return {"ok": False,
                    "error": ("该 handle 的结果已被清理（过期或容量回收）。重新调用工具即可再取。"
                              if expired else
                              "没有这个 handle：可能拼写有误，或它来自另一次 MCP 服务/另一台机器。"),
                    "handle": handle, "stream": stream}
        total = path.stat().st_size
        off = max(0, int(offset or 0))
        lim = max(1, min(int(length or PAGE_BYTES_DEFAULT), PAGE_BYTES_MAX))
        with path.open("rb") as f:
            f.seek(min(off, total))
            raw = f.read(lim)
        nxt = off + len(raw)
        sha = ""
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            sha = (meta.get("streams", {}).get(stream, {}) or {}).get("sha256", "")
        except (OSError, ValueError) as e:
            # ★ 2026-10-16（D5）：原来静默 pass —— 调用方拿到的是 sha256=""，
            #   和"文件本来就没有摘要"长得一模一样。留日志，别让失败伪装成正常。
            self.log(f"read_page: meta 不可用（{meta_path.name}）：{e}")
        return {"ok": True, "handle": handle, "stream": stream,
                "offset": off, "length": len(raw), "total_bytes": total,
                "eof": nxt >= total, "next_offset": None if nxt >= total else nxt,
                "sha256": sha, "encoding": "base64",
                "data_base64": base64.b64encode(raw).decode("ascii")}

    # ------------------------------------------------------------ 调用配方（唯一事实源）
    def load_recipes(self) -> dict:
        """读 `skills/config/tool-recipes.json` —— 「这个工具该怎么调」的唯一事实源。

        ★ 2026-10-16：以前参数散在三处（TOOLS.md / 本文件 / 技能卡），谁也不知道谁对。
        根因实例：本文件写 `diec --extended`（错）、TOOLS.md 写 `-d -e -j`（对），
        错参数的后果是进程**永不返回**，一条 triage 卡满 240s 超时。
        找不到配置文件就返回 {}，调用方用内置兜底 —— MCP 不该因为少一个 json 起不来。
        """
        for cand in (Path(self.skill_root) / "skills" / "config" / "tool-recipes.json",
                     Path(self.skill_root) / "skillpack" / "skills" / "config" / "tool-recipes.json"):
            try:
                return json.loads(cand.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
        self.log("tool-recipes.json 没找到 —— triage 用内置兜底参数")
        return {}

    def _triage_plan(self, path: str) -> list[tuple[str, list[str]]]:
        """triage 跑哪几步、每步什么参数 —— 从配方表取（`triage.*` 那几条），缺表时内置兜底。"""
        plan: list[tuple[str, list[str]]] = []
        for r in (self.load_recipes().get("recipes") or []):
            if not isinstance(r, dict) or not str(r.get("id") or "").startswith("triage."):
                continue
            args = [path if a in ("{target}", "{pe}") else a for a in (r.get("args") or [])]
            plan.append((str(r.get("tool") or ""), args))
        if plan:
            return plan
        # 兜底：配置文件缺失也要能干活（MCP 不该因为少一个 json 起不来）
        return [("diec", ["-d", "-e", "-j", path]), ("r2", ["-q", "-c", "iI;q", path]),
                ("floss", [path]), ("capa", ["-q", path])]

    # ------------------------------------------------------------ 工具解析
    # ★ 2026-10-16：以前 `run_tool` 只查 KNOWN_TOOLS 预探测表（57 条硬编码 id）——
    #   「能力发现认得出的工具却调不动」：换台机器装了名字没见过的同类软件，
    #   find_capability 可能认出来，run_tool 仍报「本机没有可用工具」。
    #   现在改成链式解析：预探测表 → 探测层按名实时解析 → 能力索引里的扫描结果。
    #   tool_id 仍然**不接受路径** —— 路径必须来自本机探测/索引，不许模型自带。
    _TOOL_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,63}$")
    PROBE_ONE_PS = _PS_UTF8 + r"""
$ErrorActionPreference='Continue'
. "{bootstrap}"
$r = $null
try {{ $r = Resolve-ReverseToolSpec -Name '{name}' -ErrorAction Stop }} catch {{ }}
if ($r -and $r.Available) {{
  [pscustomobject]@{{ id='{name}'; ok=$true; via=("" + $r.Via); cmd=("" + $r.Command) }} | ConvertTo-Json -Compress
}} else {{
  [pscustomobject]@{{ id='{name}'; ok=$false; via=("" + $r.Via); cmd='' }} | ConvertTo-Json -Compress
}}
"""

    def _resolve_by_probe(self, tool_id: str) -> tuple[str | None, str]:
        """按名单个问探测层（四级递进：env → PATH → 别名表 → 工具根递归）。"""
        bs = self._bootstrap()
        if not bs:
            return None, "Bootstrap.ps1 找不到（--skill-root 指错？）"
        script = self.PROBE_ONE_PS.format(bootstrap=str(bs).replace("\\", "\\\\"), name=tool_id)
        try:
            p = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        except (OSError, subprocess.TimeoutExpired) as e:
            return None, f"探测层调用失败：{type(e).__name__}"
        try:
            d = json.loads((p.stdout or "").strip() or "{}")
        except ValueError:
            return None, "探测层输出不是 JSON"
        if isinstance(d, list):
            d = d[0] if d else {}
        if d.get("ok") and d.get("cmd"):
            return str(d["cmd"]), ""
        return None, f"探测层没找到（via={d.get('via') or 'n/a'}）"

    def _index_lookup(self, tool_id: str) -> str | None:
        """在能力索引里按**精确名字**（忽略 .exe 等扩展名）找路径。

        只做精确匹配：索引里那些规则扫出来的同义词不做模糊命中，
        否则 `run_tool('pip')` 可能落到某个能力项的邻居上。"""
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        for cand in (Path(base) / "reverse-skill" / "capabilities" / "capabilities.json",
                     self.state.parent / "capabilities" / "capabilities.json"):
            try:
                idx = json.loads(cand.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            want = tool_id.lower()
            for _cap, lst in (idx.get("capabilities") or {}).items():
                for e in lst or []:
                    if not isinstance(e, dict):
                        continue
                    pth = str(e.get("path") or "")
                    if not pth:
                        continue
                    if str(e.get("tool") or "").lower() == want or Path(pth).stem.lower() == want:
                        return pth
        return None

    def resolve(self, tool_id: str) -> tuple[str | None, str, str]:
        """返回 (cmd, via, why)。"""
        if not tool_id:
            return None, "", "tool_id 为空"
        if any(ch in tool_id for ch in ("/", "\\", ":")):
            return None, "", "tool_id 必须是工具名，不是路径 —— 路径一律由本机探测层解析"
        if not self._TOOL_ID_RE.fullmatch(tool_id):
            return None, "", "工具名含不允许的字符（只允许字母/数字/._+-）"
        ent = self.probe().get(tool_id) or {}
        if ent.get("ok") and ent.get("cmd"):
            return ent["cmd"], f"probe:{ent.get('via') or 'unknown'}", ""
        cmd, why = self._resolve_by_probe(tool_id)
        if cmd:
            return cmd, "bootstrap", ""
        hit = self._index_lookup(tool_id)
        if hit:
            return hit, "capability-index", ""
        return None, "", why or "探测层与能力索引里都没有这个名字"

    # ------------------------------------------------------------ 执行
    def run(self, tool_id: str, argv: list[str], timeout: int) -> dict:
        # ★ 2026-10-16 工具层实测补的闸：**GUI / 启动器一律不许经本通道执行**。
        #   与 `capability-index.py` 的 `GUI_HINTS` / `NEVER_EXEC` 同源纪律
        #   （那边的由来：help 探测撞上 `nmap\Uninstall.exe`，直接弹出卸载向导）。
        #   实测缺口：本文件此前**一道这类闸都没有** —— `run_tool('x64dbg', …)` 会拉起
        #   `D:\Tools\cli\start-x64dbg-mcp.ps1`（项目自己的启动器，不是调试器本体），
        #   `run_tool('ida', …)` / `run_tool('die', …)` 会弹 GUI 窗口，而
        #   `KNOWB-BOUNDARIES` 第 9 条第 8 项正是为这一类事故写的。这里补上，
        #   并在报错里直接给出**可照抄的 CLI 替身**。
        gui = _GUI_TOOL_IDS.get(tool_id.lower())
        if gui:
            reason, twin = gui
            return {"ok": False, "status": "gui_tool", "capture_complete": True,
                    "exit": None, "command": None, "resolved_via": "gui-guard", "argv": list(argv),
                    "error": (f"`{tool_id}` 是 GUI / 启动器，**本通道不执行它**（会弹窗或拉起 GUI）：{reason}。"
                              + (f"需要的话用 CLI 孪生 `{twin}`。" if twin else
                                 "本机没有可替代的命令行形态。")),
                    "gui_reason": reason, "cli_twin": twin or None}
        cmd, via, why = self.resolve(tool_id)
        if not cmd:
            return {"ok": False, "status": "missing_tool", "capture_complete": True,
                    "error": f"本机没有可用工具 '{tool_id}'：{why}。"
                             f"用 local_tools 看已知清单，或用 find_capability 按能力找。",
                    "available": sorted(k for k, v in self.probe().items() if v.get("ok"))}
        total = self._sweep()
        if total >= TOTAL_CAP:
            return {"ok": False, "status": "quota", "capture_complete": False,
                    "error": (f"结果缓存已占 {total} 字节（上限 {TOTAL_CAP}）。"
                              f"不删未过期的旧结果；请等过期（{TTL_SECONDS}s）或手动清理 "
                              f"{self.results} 后重试。")}
        cap = self._capture(cmd, list(argv), timeout)
        status = cap["status"]
        if status == "spawn_error":
            out = {"ok": False, "status": "spawn_error", "exit": None,
                   "error": cap["error"], "command": cmd}
            self.log(f"run {tool_id} spawn_error {cap['error'][:80]}")
            return out
        so, se = cap["stdout"], cap["stderr"]
        shown_stdout = so["preview"]
        out = {
            "ok": status in ("ok", "capped"),
            "status": status,
            "exit": cap["exit"],
            "command": cmd,
            "resolved_via": via,
            "argv": list(argv),
            "duration_s": cap["duration_s"],
            "capture_complete": cap["capture_complete"],
            "handle": cap["handle"],
            "stdout": shown_stdout,
            "stderr": se["preview"],
            "stdout_bytes": so["bytes"],
            "stderr_bytes": se["bytes"],
            "stdout_sha256": so["sha256"],
            "stderr_sha256": se["sha256"],
            "truncated_preview": bool(so["bytes"] > len(shown_stdout) or se["bytes"] > len(se["preview"])),
            "read_with": "read_tool_output(handle, stream, offset, length)",
        }
        if status == "timeout":
            out["error"] = f"超时（{timeout}s）——已终止整棵进程树；上面是超时前已捕获的部分。"
        elif status == "capped":
            out["error"] = f"输出超过单流上限（{STREAM_CAP} 字节/流），已停止落盘，只保留前缀。"
        self.log(f"run {tool_id} rc={cap['exit']} status={status} "
                 f"out={so['bytes']}B err={se['bytes']}B handle={cap['handle']}")
        return out


def build_server(ctx: Ctx) -> Server:
    server: Server = Server("relab2-tools")

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return [
            types.Tool(
                name="local_tools",
                description=("本机工具链的**实时**清单（可用 / 缺件 + 实际路径 + 从哪找到的）。"
                             "任何「本机有没有 X 工具」的问题都走这里 —— 不要猜、不要读缓存表。"),
                inputSchema={"type": "object", "properties": {
                    "refresh": {"type": "boolean", "description": "true = 忽略缓存重新探测（约 5–25s）"},
                    "offset": {"type": "integer", "description": "可用清单分页起点（条目序号），默认 0"},
                    "limit": {"type": "integer", "description": "每页条目数，默认 200"}}},
            ),
            types.Tool(
                name="ensure_tool",
                description=(
                    "★ **缺工具时自己装** —— 不需要问人。流程：探测是否已装 → 查 bootstrap-manifest → "
                    "从**公开源**下载（GitHub Release zip / winget / pip，manifest 里带 assetSha256 的会校验）"
                    "→ 解压到工具根 → 刷新 PATH → 写工具路由(_map.json aliases) → 真跑 verifyCommand 确认。"
                    "幂等：已装直接返回 already=true，不会重复下载。"
                    "装不了的（商业授权/需人工）会返回 manualInstallHint + docsUrl，而不是假装成功。"
                    "示例：tool_id='jadx'。"
                ),
                inputSchema={"type": "object", "properties": {
                    "tool_id": {"type": "string", "description": "能力名（bootstrap-manifest.json 的 capabilities[].name）"},
                    "dry_run": {"type": "boolean", "description": "true = 只报会怎么装，不真下载"}},
                    "required": ["tool_id"]},
            ),
            types.Tool(
                name="run_tool",
                description=("调用本机任一已登记工具。路径由探测层实时解析（换机自动适配），"
                             "不需要也不允许自己拼路径。示例：tool_id='diec', args=['-d','-e','-j','C:/x.exe']。"
                             "★ **每个工具的合法参数形态在 `skills/config/tool-recipes.json`** —— "
                             "参数写错不是报错，是**进程永不返回**（实测 `diec --extended` 卡满 240s、"
                             "还留下 ghost 进程）；拿不准就先跑 "
                             "`python skills/tests/test-tool-recipes.py --list` 看已登记形态。"
                             "★ 输出超过预览（1 KiB）时返回得是 `stdout`/`stderr` 的前缀预览 + "
                             "`handle`；原始字节用 `read_tool_output` 按字节偏移分页取回，不要以为预览就是全文。"),
                inputSchema={"type": "object", "properties": {
                    "tool_id": {"type": "string", "description": "工具 id，如 diec / floss / capa / jadx / r2 / nmap"},
                    "args": {"type": "array", "items": {"type": "string"}, "description": "命令行参数数组"},
                    "timeout_s": {"type": "integer", "description": "超时秒数，默认 180"}},
                    "required": ["tool_id"]},
            ),
            types.Tool(
                name="triage_target",
                description=("对目标做「第一眼」三连：格式/壳（diec）→ 关键字符串（floss）→ 能力命中（capa）。"
                             "本机缺哪把刀就跳过哪一步并在结果里注明，不报错。"
                             "每一步都带自己的 handle 与 stderr 字数；大输出用 read_tool_output 取回。"),
                inputSchema={"type": "object", "properties": {
                    "path": {"type": "string", "description": "目标文件路径"},
                    "timeout_s": {"type": "integer", "description": "每一步的超时秒数，默认 180"}},
                    "required": ["path"]},
            ),
            types.Tool(
                name="find_capability",
                description=("按**能力**找本机工具 —— 「谁能解固件」「谁能抓包」「谁能反编译」。"
                             "能力索引是运行时扫描出来的（按规则 + help 关键词归类），"
                             "所以**换机、换一批名字没见过的新工具**也认得出（见 capability-index.py --selftest-help）。"
                             "结果超过预算时按行分页，返回 total_lines / next_offset。"),
                inputSchema={"type": "object", "properties": {
                    "capability": {"type": "string", "description": "能力 id，如 firmware-unpack / capture / static-decompile；留空则列全表"},
                    "rescan": {"type": "boolean", "description": "true = 强制重建索引（慢）"},
                    "offset": {"type": "integer", "description": "分页起点（行号），默认 0"},
                    "limit": {"type": "integer", "description": "每页行数，默认 200"}}},
            ),
            types.Tool(
                name="read_tool_output",
                description=("按 **字节偏移** 分页取回某个 handle 的原始 stdout/stderr。"
                             "返回 base64（保真非 UTF-8 字节与 NUL），带 next_offset / eof / sha256。"
                             "handle 只在本机本通道有效；不接受任何文件路径。"),
                inputSchema={"type": "object", "properties": {
                    "handle": {"type": "string", "description": "run_tool / triage_target 返回的 handle"},
                    "stream": {"type": "string", "enum": ["stdout", "stderr"], "description": "取哪一路"},
                    "offset": {"type": "integer", "description": "从零开始的**字节**偏移，默认 0"},
                    "length": {"type": "integer", "description": f"本次最多取多少字节，默认 {PAGE_BYTES_DEFAULT}，上限 {PAGE_BYTES_MAX}"}},
                    "required": ["handle", "stream"]},
            ),
        ]

    def _cap_index(args: list[str], timeout: int = 300) -> tuple[int, str]:
        """在同一目录下直接 import capability-index.py，**不起子进程** ——
        子进程会把 stdio 管道一起带进去，在 MCP 服务器里极易把调用拖住（2026-10-15 实测）。
        找不到索引时按需重建。"""
        try:
            import importlib.util
            here = Path(__file__).resolve().parent
            spec = importlib.util.spec_from_file_location("capindex", here / "capability-index.py")
            mod = importlib.util.module_from_spec(spec)          # type: ignore[arg-type]
            spec.loader.exec_module(mod)                         # type: ignore[union-attr]
        except Exception as e:                                   # noqa: BLE001
            return 2, f"加载 capability-index 失败：{e}"

        want_scan = "--scan" in args
        find = None
        if "--find" in args:
            i = args.index("--find")
            find = args[i + 1] if i + 1 < len(args) else None
        if want_scan or mod.load() is None:
            # ★ 2026-10-15：以前这里写的是 probe_help=False —— 等于把「规则认不出的新工具
            #   也能被认出来」这条**唯一卖点**关掉了（审计实测：help_probes=0、unknown=4537）。
            #   现在打开；预算只花在工具根里的候选上（见 capability-index.build）。
            idx = mod.build(probe_help=True)
            mod.state_dir().joinpath("capabilities.json").write_text(
                json.dumps(idx, ensure_ascii=False, indent=1), encoding="utf-8")
        else:
            idx = mod.load()
        if find is None:
            lines = [f"扫描 {idx['candidates']} 个候选，未知 {idx['unknown_count']} 个"]
            for c, lst in idx["capabilities"].items():
                lines.append(f"  {c:18s} {len(lst):3d} 个  e.g. "
                             + ", ".join(x["tool"] for x in lst[:4]))
            return 0, "\n".join(lines)
        lst = idx["capabilities"].get(find) or []
        if not lst:
            return 1, f"本机没有能做「{find}」的工具。"
        return 0, "\n".join(f"  {x['tool']:22s} {x['why']:26s} {x['path']}" for x in lst)

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> types.CallToolResult:
        def _text(payload: str, is_error: bool = False) -> types.CallToolResult:
            return types.CallToolResult(isError=is_error,
                                        content=[types.TextContent(type="text", text=payload)])

        if name == "local_tools":
            table = await anyio.to_thread.run_sync(
                lambda: ctx.probe(ttl=0 if arguments.get("refresh") else 600))
            ok = sorted(k for k, v in table.items() if v.get("ok"))
            no = sorted(k for k, v in table.items() if not v.get("ok"))
            off = max(0, int(arguments.get("offset") or 0))
            lim = max(1, min(int(arguments.get("limit") or LIST_PAGE_DEFAULT), LIST_PAGE_MAX))
            page = ok[off:off + lim]
            nxt = off + lim if off + lim < len(ok) else None
            body = {
                "可用": [{"id": k, "via": table[k]["via"], "cmd": table[k]["cmd"]} for k in page],
                "缺件": no,
                "统计": f"{len(ok)}/{len(table)} 可用",
                "定位方式": "Bootstrap.ps1 → Resolve-ReverseToolSpec（env → PATH → 别名表 → 工具根递归）",
            }
            if nxt is not None or off:
                body["分页"] = {"offset": off, "limit": lim, "total": len(ok), "next_offset": nxt}
            return _text(json.dumps(body, ensure_ascii=False, indent=1))

        if name == "ensure_tool":
            return _text(json.dumps(
                await anyio.to_thread.run_sync(lambda: _ensure_tool(arguments, ctx)),
                ensure_ascii=False, indent=1))

        if name == "run_tool":
            res = await anyio.to_thread.run_sync(
                lambda: ctx.run(arguments.get("tool_id", ""), list(arguments.get("args") or []),
                                int(arguments.get("timeout_s") or 180)))
            # 不再对序列化结果切片：上面已经把每路输出收成有界预览，整体必然合法可解析。
            return _text(json.dumps(res, ensure_ascii=False, indent=1), is_error=not res.get("ok"))

        if name == "triage_target":
            path = arguments.get("path", "")
            tmo = int(arguments.get("timeout_s") or 180)
            # ★ 2026-10-16：参数不再写死在函数里 —— 从 `skills/config/tool-recipes.json` 读（唯一事实源）。
            #   起因：这里原来写 `diec --extended`，而 `TOOLS.md:195` 写的是 `-d -e -j`；
            #   错参数的后果不是报错，是 `diec.exe` **永不返回**（只刷 libpng 警告），一条 triage 卡满 240s。
            #   两边各写一份就必然对不上 —— 现在只有一份，且有 `test-tool-recipes.py` 真跑它。
            plan = self._triage_plan(path)
            out: dict = {"target": path, "steps": []}
            for tid, argv in plan:
                r = await anyio.to_thread.run_sync(lambda t=tid, a=argv: ctx.run(t, a, tmo))
                out["steps"].append(_step_view(tid, r))
            out["读法"] = ("diec 的 JSON 给的是**线索**（entropy/编译器/壳的判读）；r2 的 `iI` 给**格式事实**"
                           "（PE/ELF、位数、canary、PIE）。要判壳看两者交叉，或按信号换刀（见 "
                           "reverse-engineering/references/signal-to-tool-decision.md）。"
                           "★ 每步参数来自 skills/config/tool-recipes.json；调 diec 只能用 `-d -e -j`，"
                           "参数写错它会挂死（见 KNOWN-BOUNDARIES 第 9 条）。"
                           "每一步都有 handle，大输出用 read_tool_output 翻页取回；"
                           "capa 很慢（分钟级），它慢是正常的，不是卡住。")
            return _text(json.dumps(out, ensure_ascii=False, indent=1))

        if name == "find_capability":
            cap = (arguments.get("capability") or "").strip()
            off = max(0, int(arguments.get("offset") or 0))
            lim = max(1, min(int(arguments.get("limit") or LIST_PAGE_DEFAULT), LIST_PAGE_MAX))
            if arguments.get("rescan") or not cap:
                rc, full = await anyio.to_thread.run_sync(
                    lambda: _cap_index(["--scan", "--no-help-probe"]))
                if rc != 0 and not cap:
                    return _text(f"扫描失败：{full[:2000]}", is_error=True)
            else:
                rc, full = await anyio.to_thread.run_sync(lambda: _cap_index(["--find", cap]))
            if len(full.encode("utf-8")) <= TEXT_BUDGET:
                body = full or f"本机没有能做「{cap}」的工具。"
                return _text(body, is_error=(rc != 0))
            meta, page = _paginate_lines(full, off, lim)
            payload = page + "\n\n" + json.dumps({"分页": meta}, ensure_ascii=False)
            return _text(payload, is_error=(rc != 0))

        if name == "read_tool_output":
            res = await anyio.to_thread.run_sync(
                lambda: ctx.read_page(arguments.get("handle", ""),
                                      arguments.get("stream", ""),
                                      int(arguments.get("offset") or 0),
                                      int(arguments.get("length") or PAGE_BYTES_DEFAULT)))
            return _text(json.dumps(res, ensure_ascii=False, indent=1), is_error=not res.get("ok"))

        return _text(f"未知工具名：{name}", is_error=True)

    return server


def _ensure_tool(arguments: dict, ctx) -> dict:
    """缺工具时自动装 —— 只走公开源，幂等，装完自注册。

    步骤（每一步都可单独观察）：
      1. probe() 看本机是否已有 -> already=true 直接返回（**不重复下载**）
      2. 读 bootstrap-manifest.json 找这个能力 -> 没有就如实报「manifest 未收录」
      3. canAutoInstall=false -> 返回 manualInstallHint + docsUrl（商业授权/需人工，**不假装成功**）
      4. 真跑 bootstrap-reverse.ps1 -Capability <name>（它负责 GitHub Release 下载 + sha256 校验 +
         解压 + PATH 刷新；manifest 里 assetSha256 为空时它自己算并提示补录）
      5. 重新 probe -> 仍然缺就如实报失败原因（不吞）
      6. 装上了但 _map.json 里没有别名 -> 补一条（否则换机会落到第 4 级 scan）
    """
    import subprocess, hashlib, json as _json, os as _os
    tid = (arguments.get("tool_id") or "").strip()
    dry = bool(arguments.get("dry_run"))
    if not tid:
        return {"ok": False, "reason": "缺少 tool_id"}

    # 1 已装？
    table = ctx.probe(ttl=0)
    hit = table.get(tid)
    if hit and hit.get("ok"):
        return {"tool": tid, "already": True, "ok": True,
                "via": hit.get("via"), "cmd": hit.get("cmd"),
                "note": "本机已有，未重复下载"}

    # 2 manifest
    here = _os.path.dirname(_os.path.abspath(__file__))
    mf = _os.path.join(here, "bootstrap-manifest.json")
    try:
        with open(mf, encoding="utf-8") as f:
            manifest = _json.load(f)
    except Exception as exc:
        return {"tool": tid, "ok": False, "reason": "读不到 bootstrap-manifest.json: %s" % exc}
    caps = manifest.get("capabilities") or []
    cap = next((c for c in caps if c.get("name") == tid), None)
    if cap is None:
        return {"tool": tid, "ok": False,
                "reason": "bootstrap-manifest.json 里没有这个能力",
                "known": sorted(c.get("name") for c in caps if c.get("name"))}

    # 3 能不能自动装
    if not cap.get("canAutoInstall"):
        return {"tool": tid, "ok": False, "auto": False,
                "reason": "该能力不能自动安装（商业授权 / 需人工）",
                "manualInstallHint": cap.get("manualInstallHint"),
                "docsUrl": cap.get("docsUrl")}

    if dry:
        return {"tool": tid, "dry_run": True, "plan": {
            "bootstrapKind": cap.get("bootstrapKind"),
            "repo": cap.get("repo"), "releaseTag": cap.get("releaseTag"),
            "assetRegex": cap.get("assetRegex"), "installDir": cap.get("installDir"),
            "verifyCommand": cap.get("verifyCommand"),
            "assetSha256": (cap.get("assetSha256") or "")[:16] + "..."}}

    # 4 真装
    bs = _os.path.join(here, "bootstrap-reverse.ps1")
    if not _os.path.isfile(bs):
        return {"tool": tid, "ok": False, "reason": "找不到 bootstrap-reverse.ps1"}
    t0 = _os.times()
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", bs,
             "-Capability", tid, "-SkipRefresh"],
            capture_output=True, text=True, errors="replace", timeout=900,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        rc, out, err = r.returncode, r.stdout or "", r.stderr or ""
    except subprocess.TimeoutExpired:
        return {"tool": tid, "ok": False, "reason": "bootstrap 超时（900s）"}
    except Exception as exc:
        return {"tool": tid, "ok": False, "reason": "bootstrap 启动失败: %s" % exc}

    # 5 复验：**两个来源都算数**
    #   ① 探测层 probe()（只在 KNOWN_TOOLS 里的 id 才覆盖）
    #   ② bootstrap 自己的 JSON 结论（status=installed + tool_path 存在）
    #   ★ 2026-10-18 实测：`agent-browser` 已经装在 D:\Tools\cli\agent-browser.cmd，
    #     bootstrap 也报 `status: installed`，但它**不在 KNOWN_TOOLS 里** ——
    #     只信 probe() 会把「装好了」误判成「缺」。所以两条都要看。
    table2 = ctx.probe(ttl=0)
    hit2 = table2.get(tid)
    ok = bool(hit2 and hit2.get("ok"))
    cmd_path = (hit2 or {}).get("cmd")
    via = (hit2 or {}).get("via")
    if not ok:
        # 从 bootstrap 的 stdout 里抠出最后那个 JSON 块
        blob = out.strip()
        j = blob.rfind("{")
        if j >= 0:
            try:
                bj = _json.loads(blob[j:])
                if bj.get("status") == "installed" and bj.get("tool_path") and _os.path.exists(bj["tool_path"]):
                    ok = True
                    cmd_path = bj["tool_path"]
                    via = "bootstrap"
            except Exception:
                pass
    res = {"tool": tid, "ok": ok, "bootstrap_exit": rc,
           "cmd": cmd_path, "via": via,
           "stdout_tail": out.strip().splitlines()[-8:],
           "stderr_tail": err.strip().splitlines()[-8:] if err.strip() else []}
    if not ok:
        res["reason"] = "bootstrap 跑完但既探测不到、也没有 status=installed 的结论（见 stdout/stderr）"
        return res

    # 6 补 _map.json 别名（装上了但路由表没有 -> 换机会落到第 4 级 scan）
    try:
        root = _os.environ.get("REVERSE_TOOL_ROOT") or r"D:\Tools"
        mpath = _os.path.join(root, "_map.json")
        if _os.path.isfile(mpath):
            with open(mpath, encoding="utf-8") as f:
                m = _json.load(f)
            al = m.setdefault("aliases", {})
            if tid not in al:
                cmd = res.get("cmd") or ""
                rel = _os.path.relpath(cmd, root).replace("\\", "/") if cmd else ""
                al[tid] = {"exec": _os.path.basename(cmd) if cmd else tid,
                           "prefer": [rel] if rel else [],
                           "note": "由 ensure_tool 自动登记（%s）" % cap.get("bootstrapKind")}
                with open(mpath, "w", encoding="utf-8") as f:
                    _json.dump(m, f, ensure_ascii=False, indent=2)
                res["registered_in_toolmap"] = True
            else:
                res["registered_in_toolmap"] = "already"
    except Exception as exc:
        res["toolmap_warning"] = "写 _map.json 失败：%s" % exc

    return res


def _step_view(tool_id: str, r: dict) -> dict:
    """把一次执行压成 triage 的一步：状态、退出码、预览、handle —— 三步各留各的。"""
    if r.get("status") == "missing_tool":
        return {"tool": tool_id, "status": "missing_tool", "ok": False,
                "error": r.get("error"), "handle": None}
    step = {"tool": tool_id, "status": r.get("status"), "ok": r.get("ok"),
            "exit": r.get("exit"), "duration_s": r.get("duration_s"),
            "capture_complete": r.get("capture_complete"),
            "stdout": r.get("stdout", ""), "stderr": r.get("stderr", ""),
            "stdout_bytes": r.get("stdout_bytes"), "stderr_bytes": r.get("stderr_bytes"),
            "handle": r.get("handle"),
            "read_with": "read_tool_output(handle, 'stdout'|'stderr', offset, length)"}
    if r.get("error"):
        step["error"] = r["error"]
    return step


async def _serve(server: Server) -> None:
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


# ---------------------------------------------------------------- 自检（夹具等价）
def _selftest() -> int:
    """不起 MCP 的等价夹具：大 stdout / 大 stderr / 超时 / 非二进制保真 / 分页拼回 / handle 校验。

    这些用例存在的理由：改之前「大输出返回坏 JSON」没有任何测试在看，
    而它正是模型最需要输出的场景。测试必须直接断言字节级一致，不是"看起来跑通了"。
    """
    fails: list[str] = []
    # skill_root 指向真实的 skillpack（含 skills/scripts/lib/Bootstrap.ps1），
    # 这样解析链用例能真的走一遍探测层。
    ns = argparse.Namespace(skill_root=str(Path(__file__).resolve().parents[2]), tool_root="")
    ctx = Ctx(ns)

    def check(cond: bool, why: str) -> None:
        if not cond:
            fails.append(why)

    py = sys.executable

    # 1) 大 stdout（3 MiB，全是 'A'）+ 大 stderr（1 MiB，'b'）—— 分流、字节数、sha256、分页拼回
    big = ("import sys;sys.stdout.write('A'*3145728);sys.stderr.write('b'*1048576)")
    r = ctx._capture(py, ["-c", big], 120)
    check(r["status"] == "ok", f"1) 状态应为 ok，实际 {r['status']}")
    check(r["stdout"]["bytes"] == 3145728, f"1) stdout 字节数错：{r['stdout']['bytes']}")
    check(r["stderr"]["bytes"] == 1048576, f"1) stderr 字节数错：{r['stderr']['bytes']}")
    h = r["handle"]
    expect = hashlib.sha256(b"A" * 3145728).hexdigest()
    check(r["stdout"]["sha256"] == expect, "1) stdout sha256 与原始字节不符")
    check(r["capture_complete"] is True, "1) 未触上限时应报 capture_complete=true")
    got = bytearray()
    off = 0
    while True:
        page = ctx.read_page(h, "stdout", off, 65536)
        if not page.get("ok"):
            fails.append(f"1) 分页取回失败：{page.get('error')}")
            break
        got += base64.b64decode(page["data_base64"])
        if page["eof"]:
            break
        off = page["next_offset"]
    check(hashlib.sha256(bytes(got)).hexdigest() == expect,
          "1) 逐页拼回后 sha256 与原始字节不符（取回不完整或有损）")
    check(len(got) == 3145728, f"1) 拼回长度错：{len(got)}")
    check(b"\x00" not in bytes(got[:16]), "1) 意外注入 NUL")

    # 2) 非 UTF-8 / 含 NUL 的字节保真
    nz = "import sys;sys.stdout.buffer.write(bytes([0,255,254,1,2,3])+b'\\xff\\xfe\\x80')"
    r2 = ctx._capture(py, ["-c", nz], 60)
    page = ctx.read_page(r2["handle"], "stdout", 0, 4096)
    raw = base64.b64decode(page["data_base64"])
    check(raw == bytes([0, 255, 254, 1, 2, 3]) + b"\xff\xfe\x80",
          f"2) 非 UTF-8 字节未保真：{raw!r}")

    # 3) 非零退出仍保留已捕获内容
    r3 = ctx._capture(py, ["-c", "import sys;print('before');sys.exit(7)"], 60)
    check(r3["status"] == "exit_nonzero", f"3) 非零退出状态错：{r3['status']}")
    check(r3["exit"] == 7, f"3) 退出码错：{r3['exit']}")
    check(b"before" in base64.b64decode(ctx.read_page(r3["handle"], "stdout", 0, 4096)["data_base64"]),
          "3) 非零退出时未保留已捕获输出")

    # 4) 超时：保留已捕获前缀、状态为 timeout、且不遗留子进程
    r4 = ctx._capture(py, ["-c", "import sys,time;print('partial',flush=True);time.sleep(60)"], 3)
    check(r4["status"] == "timeout", f"4) 超时状态错：{r4['status']}")
    check(r4["capture_complete"] is False, "4) 超时必须报 capture_complete=false")
    check(b"partial" in base64.b64decode(ctx.read_page(r4["handle"], "stdout", 0, 4096)["data_base64"]),
          "4) 超时未保留已捕获前缀")

    # 4b) 进程树终止：父进程起一个长眠孙进程，超时后孙进程也必须死
    #     ★ 只在 Windows 上验（用 tasklist 查进程）：Linux CI 上没有 tasklist，
    #       在这里无条件调用会让本门在 CI 上误红 —— 宁可打印"跳过"，也不要假红。
    if os.name == "nt":
        tree = ("import subprocess,sys,time;"
                "p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(120)']);"
                "print('child',p.pid,flush=True);time.sleep(120)")
        r5 = ctx._capture(py, ["-c", tree], 3)
        child_pid = None
        try:
            txt = base64.b64decode(ctx.read_page(r5["handle"], "stdout", 0, 4096)["data_base64"]).decode()
            child_pid = int(txt.split()[1])
        except Exception:  # noqa: BLE001
            fails.append("4b) 没拿到孙进程 pid（夹具本身失败）")
        if child_pid:
            time.sleep(0.8)
            out = subprocess.run(["tasklist", "/FI", f"PID eq {child_pid}"], capture_output=True,
                                 text=True, errors="replace", timeout=30).stdout
            check(str(child_pid) not in out, f"4b) 超时后孙进程 {child_pid} 仍存活（进程树未杀）")
    else:
        print("  · 进程树终止用例跳过（非 Windows：走 kill() 分支，无 tasklist 可查）")

    # 5) handle 校验：路径穿越、错误形状、不存在的 handle 都必须拒绝且不读文件
    for bad in ("../../windows/win.ini", "c:\\windows\\win.ini", "not-a-handle", "0" * 31):
        res = ctx.read_page(bad, "stdout", 0, 16)
        check(res.get("ok") is False, f"5) 非法 handle 未被拒绝：{bad}")
    res = ctx.read_page("f" * 32, "stdout", 0, 16)
    check(res.get("ok") is False and "没有这个 handle" in res.get("error", ""),
          "5) 不存在的 handle 未给出明确错误")

    # 6) 单流上限：触上限时必须 capped + capture_complete=false，但仍可取出前缀
    old = globals()["STREAM_CAP"]
    globals()["STREAM_CAP"] = 4096
    try:
        r6 = ctx._capture(py, ["-c", "import sys;sys.stdout.write('C'*100000)"], 60)
        check(r6["stdout"]["bytes"] <= 4096, f"6) 未遵守单流上限：{r6['stdout']['bytes']}")
        check(r6["capture_complete"] is False, "6) 触上限时必须报 capture_complete=false")
        check(r6["status"] == "capped", f"6) 触上限状态应为 capped，实际 {r6['status']}")
        pg = ctx.read_page(r6["handle"], "stdout", 0, 8192)
        check(pg.get("ok") and len(base64.b64decode(pg["data_base64"])) == 4096,
              "6) 前缀应按实际落盘字节取回")
    finally:
        globals()["STREAM_CAP"] = old

    # 7) 预览有界 + 返回体仍是合法 JSON（这就是旧实现坏掉的那条）
    r7 = ctx._capture(py, ["-c", "print('x'*50000)"], 60)
    view = {"ok": True, "stdout": r7["stdout"]["preview"], "stderr": r7["stderr"]["preview"],
            "stdout_bytes": r7["stdout"]["bytes"], "handle": r7["handle"]}
    serialized = json.dumps(view, ensure_ascii=False, indent=1)
    try:
        json.loads(serialized)
        ok_json = True
    except ValueError:
        ok_json = False
    check(ok_json, "7) 大输出下返回体不是合法 JSON")
    check(len(r7["stdout"]["preview"].encode("utf-8")) <= PREVIEW_BYTES,
          "7) 预览未按上限收敛")

    # 8) 解析链：**表外**的本机工具也必须调得动（旧实现只认 57 条硬编码 id，认出来也调不动）
    #    ★ 只在有探测层的平台上跑这段（探测层是 PowerShell）；其它平台打印"跳过"而不是假绿/假红 ——
    #      夹具在 Linux CI 上跑时不该因为"没有 powershell"而红。
    if os.name == "nt" and shutil.which("powershell"):
        shown = False
        for probe_id in ("tasklist", "where", "xcopy", "curl", "git"):
            c, via, why = ctx.resolve(probe_id)
            if c:
                check(probe_id not in KNOWN_TOOLS,
                      f"8) 用例本身失效：{probe_id} 已在 KNOWN_TOOLS 里，证明不了链式解析")
                print(f"  · 表外工具解析成功：{probe_id} → via={via}")
                shown = True
                break
        if not shown:
            check(False, "8) 表外工具一个都解析不出来 —— 链式解析没生效（旧行为是只查硬编码表）")
        # 路径型 tool_id 必须被拒（路径只能由本机探测层给出）
        for bad in ("../../evil.exe", r"C:\Windows\System32\cmd.exe", "/bin/sh"):
            c, _via, _why = ctx.resolve(bad)
            check(c is None, f"8) 路径型 tool_id 未被拒：{bad}")
    else:
        print("  · 解析链用例跳过：本机没有 powershell（探测层不可用）")

    if fails:
        print("relab2-tools-mcp 自检: FAIL")
        for f in fails:
            print("  ✗", f)
        return 1
    print("relab2-tools-mcp 自检: PASS（大输出分流/字节+sha256/分页拼回/非 UTF-8 保真/"
          "非零退出/超时前缀/进程树终止/handle 校验/单流上限/预览有界且合法 JSON）")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="把本机工具链暴露成 MCP 工具")
    ap.add_argument("--skill-root", default=os.environ.get("REVERSE_SKILL_ROOT", ""),
                    help="技能包根（含 skills/scripts/lib/Bootstrap.ps1）")
    ap.add_argument("--tool-root", default=os.environ.get("REVERSE_TOOL_ROOT", ""))
    ap.add_argument("--selftest", action="store_true",
                    help="跑捕获/分页/超时/字节保真的等价夹具后退出（不起 MCP）")
    a = ap.parse_args()
    if a.selftest:
        return _selftest()
    if _MCP_IMPORT_ERROR:
        print(f"relab2-tools-mcp: 起不了 MCP 服务器 —— 缺少传输栈（{_MCP_IMPORT_ERROR}）。"
              f"装好依赖后再起；`--selftest` 不需要它，可以先跑它验捕获/分页。",
              file=sys.stderr)
        return 1
    ctx = Ctx(a)
    ctx.log(f"start skill_root={ctx.skill_root!r} tool_root={ctx.tool_root!r}")
    try:
        anyio.run(_serve, build_server(ctx))
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
