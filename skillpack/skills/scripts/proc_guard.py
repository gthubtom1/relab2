#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""proc_guard：测试进程的生命周期管理（启动、并发上限、超时、收尸、全局清扫）。

为什么需要（主人指出）：
    之前每个测试各自 `Start-Process` / `subprocess.Popen`，没有全局登记，
    于是靶机程序会同时跑起 10 个；工具用完后也没有统一的关闭点。

设计：
    1. **登记制**：每个进程启动即写进 registry（JSON），退出即删除。
       进程崩溃/脚本被杀也不会丢账 —— 下次 `--sweep` 能扫到。
    2. **并发上限**：同类目标默认 1 个。超限时先等（可配），等不到就杀最老的。
    3. **硬超时**：到点先 terminate，宽限 2s 后 kill。
    4. **收尸**：`finally` 里一定 kill，不留后台。
    5. **全局清扫**：`--sweep <root>` 杀掉任何**映像路径**落在该目录下的进程，
       不依赖 registry（registry 丢了也能清）。

用法：
    python proc_guard.py --list
    python proc_guard.py --sweep C:\\relab2\\work\\_benchmark\\samples
    python proc_guard.py --run --timeout 8 -- <exe> [args...]
"""
from __future__ import annotations

import argparse
import io
import json
import os
import signal
import subprocess
import sys
import threading
import time
from typing import Any

HERE = os.path.dirname(os.path.abspath(__file__))
REGISTRY = os.path.join(HERE, ".procs.json")
DEFAULT_MAX = 1
GRACE_SECONDS = 2.0
_local = threading.local()


# ---------------- registry ----------------

class _FileLock:
    """跨进程/跨线程的文件锁（O_CREAT|O_EXCL + 重试）。

    ★ 自测抓到的 bug：5 个线程同时 run 时，都写同一个 .procs.json.tmp，
      后写的把先写的句柄顶掉 -> PermissionError，且登记丢失 -> 进程泄漏。
    """

    def __init__(self, path: str, timeout: float = 10.0):
        self.path = path + ".lock"
        self.timeout = timeout
        self.fd = None

    def __enter__(self):
        depth = getattr(_local, "depth", 0)
        if depth > 0:
            _local.depth = depth + 1
            return self
        deadline = time.time() + self.timeout
        while True:
            try:
                self.fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(self.fd, str(os.getpid()).encode())
                _local.depth = 1
                return self
            except FileExistsError:
                # 陈旧锁：持有者已死或超过 30s
                try:
                    if time.time() - os.path.getmtime(self.path) > 30:
                        os.unlink(self.path)
                        continue
                except OSError:
                    pass
                if time.time() > deadline:
                    raise TimeoutError("lock timeout: %s" % self.path)
                time.sleep(0.005)

    def __exit__(self, *exc):
        depth = getattr(_local, "depth", 1)
        if depth > 1:
            _local.depth = depth - 1
            return False
        _local.depth = 0
        if self.fd is not None:
            try:
                os.close(self.fd)
            except OSError:
                pass
            try:
                os.unlink(self.path)
            except OSError:
                pass
            self.fd = None
        return False


def _load() -> dict[str, Any]:
    if not os.path.isfile(REGISTRY):
        return {"procs": {}}
    try:
        with io.open(REGISTRY, "r", encoding="utf-8") as f:
            d = json.load(f)
        if not isinstance(d, dict):
            return {"procs": {}}
        d.setdefault("procs", {})
        return d
    except Exception:  # noqa: BLE001
        return {"procs": {}}


def _save(d: dict[str, Any]) -> None:
    with _FileLock(REGISTRY):
        tmp = "%s.tmp.%d" % (REGISTRY, os.getpid())
        with io.open(tmp, "w", encoding="utf-8", newline="\n") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
        os.replace(tmp, REGISTRY)


def _mutate(fn):
    """在锁内做 read-modify-write。"""
    with _FileLock(REGISTRY):
        d = _load()
        fn(d)
        tmp = "%s.tmp.%d" % (REGISTRY, os.getpid())
        with io.open(tmp, "w", encoding="utf-8", newline="\n") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
        os.replace(tmp, REGISTRY)


def _alive(pid: int) -> bool:
    """Windows: OpenProcess 探测；其他平台: kill(pid,0)。"""
    if os.name == "nt":
        try:
            import ctypes
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            h = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if not h:
                return False
            code = ctypes.c_ulong(0)
            ok = ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(code))
            ctypes.windll.kernel32.CloseHandle(h)
            return bool(ok) and code.value == 259  # STILL_ACTIVE
        except Exception:  # noqa: BLE001
            return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _kill(pid: int, tree: bool = True) -> None:
    if os.name == "nt":
        # /T 连子进程一起收；/F 强制
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                       capture_output=True, check=False)
    else:
        try:
            if tree:
                os.killpg(os.getpgid(pid), signal.SIGKILL)
            else:
                os.kill(pid, signal.SIGKILL)
        except OSError:
            pass


def _reap_registry(verbose: bool = False) -> int:
    """清掉 registry 里已经死掉的条目。返回清理条数。"""
    d = _load()
    dead = [k for k, v in d["procs"].items() if not _alive(int(v["pid"]))]
    for k in dead:
        if verbose:
            print("  reap (dead) %s pid=%s" % (k, d["procs"][k]["pid"]))
        del d["procs"][k]
    if dead:
        _save(d)
    return len(dead)


# ---------------- 并发控制 ----------------

def _enforce_limit(group: str, limit: int, verbose: bool = False) -> None:
    d = _load()
    live = [(k, v) for k, v in d["procs"].items()
            if v.get("group") == group and _alive(int(v["pid"]))]
    if len(live) < limit:
        return
    # 超过上限：按启动时间从老到新杀，直到降到 limit-1
    live.sort(key=lambda kv: kv[1].get("started", 0))
    excess = len(live) - (limit - 1)
    victims = [k for k, _ in live[:excess]]
    for k in victims:
        pid = d["procs"].get(k, {}).get("pid")
        if pid is None:
            continue
        if verbose:
            print("  limit(%d) exceeded for %s -> kill %s pid=%s" % (limit, group, k, pid))
        _kill(int(pid))

    def _del(dd):
        for k in victims:
            dd["procs"].pop(k, None)
    _mutate(_del)


# ---------------- 运行 ----------------

def run(argv: list[str], timeout: float = 8.0, group: str = "default",
        limit: int = DEFAULT_MAX, cwd: str | None = None,
        stdin_data: bytes | None = None) -> dict[str, Any]:
    """跑一个进程，带并发上限 / 硬超时 / 一定收尸。返回 {rc, stdout, stderr, timed_out}。"""
    _reap_registry()

    # ★ 临界区：check limit 与 spawn 必须在同一把锁里。
    #   自测抓到：只锁 registry 写、不锁 check->spawn，5 个线程会同时通过检查 -> 并发不受限。
    with _FileLock(REGISTRY):
        _enforce_limit(group, limit)
        started = time.time()
        p = subprocess.Popen(argv, cwd=cwd, stdin=subprocess.PIPE if stdin_data is not None else None,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        key = "%s:%d" % (os.path.basename(argv[0]), p.pid)

        def _add(d):
            d["procs"][key] = {"pid": p.pid, "group": group, "started": started, "argv": argv}
        _mutate(_add)

    timed_out = False
    try:
        out, err = p.communicate(input=stdin_data, timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        p.terminate()
        try:
            out, err = p.communicate(timeout=GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            _kill(p.pid)
            try:
                out, err = p.communicate(timeout=GRACE_SECONDS)
            except subprocess.TimeoutExpired:
                out, err = b"", b""
    finally:
        # ★ 无条件收尸（含子进程树）。自测抓到过泄漏：只在 poll() is None 时才 kill 不够，
        #   因为 taskkill /T 还要收孙子进程，且 registry 写失败时也要保证杀。
        _kill(p.pid)
        try:
            p.wait(timeout=GRACE_SECONDS)
        except Exception:  # noqa: BLE001
            pass

        def _del(d):
            d["procs"].pop(key, None)
        try:
            _mutate(_del)
        except Exception:  # noqa: BLE001
            pass

    return {
        "rc": p.returncode,
        "stdout": (out or b"").decode("utf-8", "replace"),
        "stderr": (err or b"").decode("utf-8", "replace"),
        "timed_out": timed_out,
        "elapsed": round(time.time() - started, 3),
        "pid": p.pid,
    }


# ---------------- 全局清扫 ----------------

def sweep(root: str, verbose: bool = True) -> int:
    """杀掉任何映像路径落在 root 下的进程（不依赖 registry）。"""
    root_abs = os.path.abspath(root).lower()
    killed = 0
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes
            TH32CS_SNAPPROCESS = 0x2
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            MAX_PATH = 260

            class PROCESSENTRY32(ctypes.Structure):
                _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                            ("th32ProcessID", wintypes.DWORD), ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
                            ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                            ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", ctypes.c_long),
                            ("dwFlags", wintypes.DWORD), ("szExeFile", ctypes.c_char * MAX_PATH)]

            k32 = ctypes.windll.kernel32
            snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
            if snap == -1:
                return 0
            pe = PROCESSENTRY32()
            pe.dwSize = ctypes.sizeof(PROCESSENTRY32)
            ok = k32.Process32First(snap, ctypes.byref(pe))
            while ok:
                pid = pe.th32ProcessID
                if pid not in (0, 4):
                    h = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
                    if h:
                        buf = ctypes.create_unicode_buffer(1024)
                        size = wintypes.DWORD(1024)
                        if k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
                            path = buf.value.lower()
                            if path.startswith(root_abs):
                                if verbose:
                                    print("  sweep kill pid=%d %s" % (pid, buf.value))
                                _kill(pid)
                                killed += 1
                        k32.CloseHandle(h)
                ok = k32.Process32Next(snap, ctypes.byref(pe))
            k32.CloseHandle(snap)
        except Exception as exc:  # noqa: BLE001
            print("  sweep error: %s" % exc)
    else:
        for pid in os.listdir("/proc"):
            if not pid.isdigit():
                continue
            try:
                exe = os.readlink("/proc/%s/exe" % pid)
            except OSError:
                continue
            if exe.lower().startswith(root_abs):
                if verbose:
                    print("  sweep kill pid=%s %s" % (pid, exe))
                _kill(int(pid))
                killed += 1
    # registry 里指向该 root 的条目也一并清
    d = _load()
    for k, v in list(d["procs"].items()):
        argv = " ".join(v.get("argv") or []).lower()
        if root_abs in argv:
            del d["procs"][k]
    _save(d)
    return killed


# 长驻 GUI 工具：必须显式关闭，不能"用完还开着"
TOOL_PATTERNS = [
    "x64dbg", "x32dbg", "ida64", "ida", "ghidra", "ghidraRun", "java",  # java 只在带 ghidra 时算
    "dnSpy", "ilspycmd", "jadx", "jadx-gui", "frida", "frida-server",
    "Wireshark", "tshark", "binwalk", "radare2", "r2", "cutter",
    "pe-sieve", "capa", "floss", "de4dot", "dnSpy.Console",
]


def sweep_tools(all_users: bool = False, verbose: bool = True) -> int:
    """关掉本机上的长驻分析工具。

    all_users=False 时只杀**本 registry 登记过**的（安全）；
    all_users=True 时按进程名匹配（更彻底，但可能误杀用户自己开着的）。
    """
    killed = 0
    d = _load()
    tracked = {int(v["pid"]) for v in d["procs"].values()}
    try:
        import ctypes
        from ctypes import wintypes
        TH32CS_SNAPPROCESS = 0x2
        MAX_PATH = 260

        class PROCESSENTRY32(ctypes.Structure):
            _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                        ("th32ProcessID", wintypes.DWORD), ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
                        ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                        ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", ctypes.c_long),
                        ("dwFlags", wintypes.DWORD), ("szExeFile", ctypes.c_char * MAX_PATH)]

        k32 = ctypes.windll.kernel32
        snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        if snap == -1:
            return 0
        pe = PROCESSENTRY32()
        pe.dwSize = ctypes.sizeof(PROCESSENTRY32)
        ok = k32.Process32First(snap, ctypes.byref(pe))
        while ok:
            pid = pe.th32ProcessID
            name = pe.szExeFile.decode("latin1", "replace")
            hit = any(name.lower().startswith(p.lower()) for p in TOOL_PATTERNS)
            if hit and (all_users or pid in tracked):
                # java 只在命令行含 ghidra 时才算工具进程
                if name.lower().startswith("java"):
                    h = k32.OpenProcess(0x1000, False, pid)
                    cmd = ""
                    if h:
                        buf = ctypes.create_unicode_buffer(1024)
                        size = wintypes.DWORD(1024)
                        if k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
                            cmd = buf.value.lower()
                        k32.CloseHandle(h)
                    if "ghidra" not in cmd:
                        ok = k32.Process32Next(snap, ctypes.byref(pe))
                        continue
                if verbose:
                    print("  tool sweep kill pid=%d %s" % (pid, name))
                _kill(pid)
                killed += 1
            ok = k32.Process32Next(snap, ctypes.byref(pe))
        k32.CloseHandle(snap)
    except Exception as exc:  # noqa: BLE001
        print("  tool sweep error: %s" % exc)
    if killed:
        def _clear(dd):
            for k in [k for k, v in dd["procs"].items() if int(v["pid"]) in tracked]:
                dd["procs"].pop(k, None)
        _mutate(_clear)
    return killed


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--list", action="store_true", help="列出 registry 里的活进程")
    ap.add_argument("--reap", action="store_true", help="清掉 registry 里已死的条目")
    ap.add_argument("--sweep", metavar="ROOT", help="杀掉映像路径在 ROOT 下的所有进程")
    ap.add_argument("--sweep-tools", action="store_true", help="关掉本 registry 登记过的长驻分析工具")
    ap.add_argument("--sweep-tools-all", action="store_true", help="按进程名关掉所有长驻分析工具（可能误杀）")
    ap.add_argument("--run", action="store_true", help="跑一个进程（用 -- 分隔命令）")
    ap.add_argument("--timeout", type=float, default=8.0)
    ap.add_argument("--group", default="default")
    ap.add_argument("--limit", type=int, default=DEFAULT_MAX)
    args, rest = ap.parse_known_args(argv)
    if rest and rest[0] == "--":
        rest = rest[1:]

    if args.reap:
        n = _reap_registry(verbose=True)
        print("reaped %d dead entries" % n)
        return 0

    if args.sweep:
        n = sweep(args.sweep)
        print("swept %d process(es) under %s" % (n, args.sweep))
        return 0

    if args.sweep_tools or args.sweep_tools_all:
        n = sweep_tools(all_users=args.sweep_tools_all)
        print("swept %d tool process(es)" % n)
        return 0

    if args.list:
        d = _load()
        live = [(k, v) for k, v in d["procs"].items() if _alive(int(v["pid"]))]
        print("registry entries: %d (live %d)" % (len(d["procs"]), len(live)))
        for k, v in live:
            print("  %-40s pid=%-8s group=%-12s argv=%s" % (k, v["pid"], v.get("group"), " ".join(v.get("argv") or [])[:80]))
        return 0

    if args.run:
        if not rest:
            print("ERROR: --run needs a command after --")
            return 2
        r = run(rest, timeout=args.timeout, group=args.group, limit=args.limit)
        print(json.dumps({k: r[k] for k in ("rc", "timed_out", "elapsed", "pid")}, ensure_ascii=False))
        if r["stdout"]:
            print("--- stdout ---")
            print(r["stdout"])
        if r["stderr"]:
            print("--- stderr ---")
            print(r["stderr"])
        return 0

    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
