"""定位 03-bundle 打包器，并且只用子进程调它。

控制台不 import 打包器代码：打包器还在写、接口可能变。子进程 + 明确命令行是
唯一稳定的耦合面。打包器不在或文件不齐，一律报「打包器未就绪」，绝不静默成功。
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

CONSOLE_DIR = Path(__file__).resolve().parent
# 04-console -> kernel，03-bundle 就在旁边。
REPO_ROOT = CONSOLE_DIR.parent
BUNDLE_DIRNAME = "03-bundle"
SOURCE_DIRNAME = "hubcore"

NOT_READY = "打包器未就绪"


def _env_override() -> Path | None:
    """自测用：只认一个环境变量，且必须落在本控制台 TEMP 里。"""
    raw = os.environ.get("HUBCONSOLE_BUNDLE_DIR", "").strip()
    if not raw:
        return None
    temp_root = (CONSOLE_DIR / "TEMP").resolve()
    try:
        target = Path(raw).resolve()
    except OSError:
        return None
    if target == temp_root or temp_root in target.parents:
        return target
    return None


def bundle_dir() -> Path:
    override = _env_override()
    if override is not None:
        return override
    return REPO_ROOT / BUNDLE_DIRNAME


def install_script() -> Path:
    return bundle_dir() / "install.py"


def uninstall_script() -> Path:
    return bundle_dir() / "uninstall.py"


def source_dir() -> Path:
    return bundle_dir() / "dist" / SOURCE_DIRNAME


def readiness() -> dict:
    root = bundle_dir()
    install = install_script()
    uninstall = uninstall_script()
    src = source_dir()
    missing: list[str] = []
    if not install.is_file():
        missing.append(install.name)
    if not uninstall.is_file():
        missing.append(uninstall.name)
    if not src.is_dir():
        missing.append(f"dist/{SOURCE_DIRNAME}")
    return {
        "ready": not missing,
        "reason": NOT_READY if missing else "",
        "missing": missing,
        "bundle_dir": str(root),
        "source_dir": str(src),
        "file_count": sum(1 for p in src.rglob("*") if p.is_file()) if src.is_dir() else 0,
        "total_kb": round(sum(p.stat().st_size for p in src.rglob("*")
                              if p.is_file()) / 1024.0, 1) if src.is_dir() else 0.0,
    }


def require(script: Path) -> Path:
    """载入/卸载前的硬门：打包器不齐就当场停。"""
    if not script.is_file():
        raise BundleNotReady(f"{NOT_READY}：缺 {script.name}（{bundle_dir()}）")
    return script


class BundleNotReady(RuntimeError):
    """打包器没就绪。控制台自己产生的，不带任何系统路径细节。"""


def _argv_install(host_home: Path, base_path: str = "", guest_path: str = "",
                  hub_path: str = "", entry_name: str = "", allow_running: bool = False,
                  with_marker: bool = True, replace_origin: bool = False) -> list[str]:
    argv = [
        sys.executable,
        str(install_script()),
        "--source",
        str(source_dir()),
        "--host-home",
        str(host_home),
    ]
    if base_path:
        argv += ["--base", str(base_path)]
    if guest_path:
        argv += ["--guest", str(guest_path)]
    if hub_path:
        argv += ["--hub", str(hub_path)]
    if entry_name:
        argv += ["--entry", str(entry_name)]
    if allow_running:
        argv += ["--allow-running"]
    if not with_marker:
        argv += ["--no-marker"]
    if replace_origin:
        argv += ["--replace-origin"]
    return argv


def _argv_uninstall(host_home: Path) -> list[str]:
    return [
        sys.executable,
        str(uninstall_script()),
        "--host-home",
        str(host_home),
        "--yes",
    ]


def _run(argv: list[str], cwd: Path, timeout: int) -> int:
    # stdio 用 inherit：沙箱下拿子进程管道会 EPERM，而且主人本来就要看打包器的输出。
    return subprocess.call(argv, cwd=str(cwd), timeout=timeout)


def run_install(host_home: Path, timeout: int = 900, base_path: str = "",
                guest_path: str = "", hub_path: str = "", entry_name: str = "",
                allow_running: bool = False, with_marker: bool = True,
                replace_origin: bool = False) -> dict:
    script = require(install_script())
    if not source_dir().is_dir():
        raise BundleNotReady(f"{NOT_READY}：缺 dist/{SOURCE_DIRNAME}")
    for label, cand in (("底模卡片", base_path), ("指引卡片", guest_path), ("中枢卡片", hub_path)):
        if cand and not Path(cand).is_file():
            raise BundleNotReady(f"{label}不在了：{Path(cand).name}（先重建卡片再装）")
    if hub_path and not with_marker:
        raise BundleNotReady("中枢卡是靠标记块写进去的：勾了中枢就不能关掉它。")
    if not (with_marker or base_path or guest_path):
        raise BundleNotReady("三段都没选，没什么可写的。先选一段。")
    argv = _argv_install(host_home, base_path, guest_path, hub_path, entry_name,
                         allow_running, with_marker, replace_origin)
    code = _run(argv, bundle_dir(), timeout)
    return {"argv": argv, "returncode": code, "ok": code == 0}


def run_uninstall(host_home: Path, timeout: int = 600) -> dict:
    script = require(uninstall_script())
    argv = _argv_uninstall(host_home)
    code = _run(argv, bundle_dir(), timeout)
    return {"argv": argv, "returncode": code, "ok": code == 0}
