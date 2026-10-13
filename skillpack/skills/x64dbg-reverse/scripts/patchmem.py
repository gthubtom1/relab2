#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""patchmem.py —— 进程外改内存（自动放开页保护 + 写入后复核）。

什么时候用它而不是调试器的写内存：
  目标 `.text` 是 RX（PAGE_EXECUTE_READ）时，某些调试器/MCP 的写接口**报成功但不落地**。
  进程外 `VirtualProtectEx + WriteProcessMemory` 走内核路径，稳；写完立刻用
  `ReadProcessMemory` 复核，**回显 ≠ 命中**。

用法：
    python patchmem.py <pid> <hexaddr>:<hexbytes> [<hexaddr>:<hexbytes> ...]
    python patchmem.py <pid> --read <hexaddr> <size>
例：
    python patchmem.py 6224 0x7FF679C6FA00:909090909090 0x7FF679C6FA31:9090

退出码：0 全部写入且复核一致／1 有写入失败或复核不一致／2 参数/进程访问出错
"""
from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

k = ctypes.WinDLL("kernel32", use_last_error=True)
k.OpenProcess.restype = wintypes.HANDLE
k.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
k.ReadProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
k.WriteProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
k.VirtualProtectEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_size_t, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
k.CloseHandle.argtypes = [wintypes.HANDLE]

PROCESS_ALL = 0x1F0FFF
PAGE_EXECUTE_READWRITE = 0x40


def open_proc(pid: int):
    h = k.OpenProcess(PROCESS_ALL, False, pid)
    if not h:
        print(f"ERROR: OpenProcess({pid}) 失败 err={ctypes.get_last_error()}"
              f" —— 进程不在？权限不够（试提权）？", file=sys.stderr)
        sys.exit(2)
    return h


def read_mem(h, addr: int, size: int) -> bytes:
    buf = ctypes.create_string_buffer(size)
    got = ctypes.c_size_t(0)
    if not k.ReadProcessMemory(h, ctypes.c_void_p(addr), buf, size, ctypes.byref(got)) or got.value != size:
        return b""
    return buf.raw[:size]


def write_mem(h, addr: int, data: bytes) -> tuple[bool, bytes]:
    n = len(data)
    old = wintypes.DWORD(0)
    ok = bool(k.VirtualProtectEx(h, ctypes.c_void_p(addr), n, PAGE_EXECUTE_READWRITE, ctypes.byref(old)))
    wrote = ctypes.c_size_t(0)
    ok_w = bool(k.WriteProcessMemory(h, ctypes.c_void_p(addr), data, n, ctypes.byref(wrote)))
    if ok:  # 恢复原保护（失败不致命，但要说出来）
        k.VirtualProtectEx(h, ctypes.c_void_p(addr), n, old.value, ctypes.byref(old))
    back = read_mem(h, addr, n)
    return (ok and ok_w and wrote.value == n and back == data), back


def main() -> int:
    a = sys.argv[1:]
    if len(a) < 2:
        print(__doc__)
        return 0
    pid = int(a[0], 0)
    h = open_proc(pid)

    if a[1] == "--read":
        addr = int(a[2], 0)
        size = int(a[3], 0)
        b = read_mem(h, addr, size)
        print(b.hex() if b else "(读取失败)")
        return 0 if b else 1

    rc = 0
    for spec in a[1:]:
        if ":" not in spec:
            print(f"ERROR: 参数格式应为 <hexaddr>:<hexbytes>，得到 {spec!r}", file=sys.stderr)
            rc = 2
            continue
        sa, sb = spec.split(":", 1)
        addr = int(sa.strip(), 0)
        data = bytes.fromhex(sb.strip().replace(" ", ""))
        before = read_mem(h, addr, len(data))
        ok, back = write_mem(h, addr, data)
        print(f"{addr:#x}  before={before.hex() or '(读失败)'}  wrote={data.hex()}  after={back.hex() or '(读失败)'}  {'OK' if ok else 'FAIL'}")
        if not ok:
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
