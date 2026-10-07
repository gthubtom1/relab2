"""外置中枢控制台的启动器。

    python run.py            起服务并打开浏览器
    python run.py --no-open  只起服务
    python run.py --port N   指定端口（默认 0 = 自动挑一个空闲端口）

服务只绑 127.0.0.1。别的机器连不上。
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import server as console  # noqa: E402


def open_browser(url: str) -> bool:
    startfile = getattr(os, "startfile", None)
    if startfile is None:
        return False
    try:
        startfile(url)
        return True
    except OSError:
        return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="外置中枢 · 极简控制台")
    parser.add_argument("--no-open", action="store_true", help="只起服务，不开浏览器")
    parser.add_argument("--port", type=int, default=0, help="0 = 自动挑一个空闲端口")
    args = parser.parse_args(argv)

    httpd, port = console.make_server(args.port)

    # 页面地址就只剩端口：进页面时服务端会下发会话 Cookie，不用带 ?t=… 后缀。
    page = f"http://127.0.0.1:{port}/"
    print(f"已启动（只听本机）：{page}", flush=True)
    print(f"页面地址（直接打开就行，不用加任何后缀）：{page}", flush=True)
    print("Ctrl+C 关掉。", flush=True)

    if not args.no_open:
        if not open_browser(page):
            print("没打开浏览器，手动把上面那行地址粘到地址栏。", flush=True)
        else:
            print("已在浏览器打开。", flush=True)

    try:
        httpd.serve_forever(poll_interval=0.4)
    except KeyboardInterrupt:
        print("\n收工，端口已让出来。", flush=True)
    finally:
        httpd.shutdown()
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
